from __future__ import annotations
import json, uuid, asyncio
import os
import sys
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
from .schemas import TimelineEvent
from .memory.state_store import Memory, TimelineBus
from .memory import sql_store
from .auth import User, current_user, require_user
from .rate_limit import limit, llm_limiter, search_limiter

# Keep Unicode startup and diagnostic logs safe when Windows redirects output to
# a file or launches the API without an interactive UTF-8 terminal.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# Load environment variables from .env file
import pathlib
env_path = pathlib.Path(__file__).parent.parent / ".env"
print(f"🔍 Looking for .env file at: {env_path}")
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env file from: {env_path}")
    print(f"🔑 TAVILY_API_KEY: {'SET' if os.getenv('TAVILY_API_KEY') else 'NOT SET'}")
    print(f"🔑 PERPLEXITY_API_KEY: {'SET' if os.getenv('PERPLEXITY_API_KEY') else 'NOT SET'}")
    print(f"🔑 EXA_API_KEY: {'SET' if os.getenv('EXA_API_KEY') else 'NOT SET'}")
    print(f"🔑 GOOGLE_MAPS_KEY: {'SET' if os.getenv('GOOGLE_MAPS_KEY') else 'NOT SET'}")
    print(f"🔑 DEEPSEEK_API_KEY: {'SET' if os.getenv('DEEPSEEK_API_KEY') else 'NOT SET'}")
else:
    print(f"⚠️ .env file not found at: {env_path}")
    # Try current directory as fallback
    load_dotenv()
    print(f"🔑 TAVILY_API_KEY: {'SET' if os.getenv('TAVILY_API_KEY') else 'NOT SET'}")
    print(f"🔑 GOOGLE_MAPS_KEY: {'SET' if os.getenv('GOOGLE_MAPS_KEY') else 'NOT SET'}")

class SaveBody(BaseModel):
    kind: Literal["event","housing","place"]
    item: dict

class RagBody(BaseModel):
    city: str
    # Optional: the UI's "detected from resume" default sends no role, and the
    # search derives it from resume_insights. Requiring it here 422'd that flow.
    role: str | None = None
    resumeToken: str | None = None
    depth: str = "standard"

class WriterBody(BaseModel):
    run_id: str
    n: int = 5

class AuditStartBody(BaseModel):
    target_role: str
    resume_token: str | None = None
    city: str = "San Francisco"
    user_id: str = "demo-user"

class OutcomeBody(BaseModel):
    user_id: str = "demo-user"
    audit_id: str | None = None
    company: str
    role: str
    outcome: Literal["ghosted", "rejected", "screen", "onsite", "offer"]

app = FastAPI(title="Agentception API")

from .routers.v1 import router as v1_router
from .routers.v2 import router as v2_router
from .routers.study import router as study_router
app.include_router(v1_router)
app.include_router(v2_router)
app.include_router(study_router)

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",   # Vite dev server (see ui/vite.config.ts)
    "http://127.0.0.1:8080",
    "https://*.vercel.app",    # Vercel preview + prod
]

# Any localhost port (dev) or Vercel deployment (prod)
_ORIGIN_REGEX = r"^(https://.*\.vercel\.app|http://(localhost|127\.0\.0\.1)(:\d+)?)$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = Memory(); bus = TimelineBus()

@app.post("/audit/start")
async def start_readiness_audit(body: AuditStartBody, bg: BackgroundTasks):
    run_id = str(uuid.uuid4())
    q = bus.ensure(run_id)

    async def emit(event):
        if isinstance(event, TimelineEvent):
            payload = event.model_dump()
            payload["run_id"] = run_id
        elif isinstance(event, dict):
            payload = {"run_id": run_id, "agent": event.get("agent", "Audit"), "message": event.get("message", str(event))}
        else:
            payload = {"run_id": run_id, "agent": "Audit", "message": str(event)}
        await q.put(payload)

    async def job():
        try:
            from .workers.readiness_tasks import start_audit_task
            result = await start_audit_task(
                target_role=body.target_role,
                resume_token=body.resume_token,
                user_id=body.user_id,
                city=body.city,
                emit=emit,
                memory_store=memory,
            )
            result["run_id"] = run_id
            memory.set(f"audit:{run_id}", result)
            sql_store.audit_save(
                audit_id=result["audit_id"], run_id=run_id, user_id=body.user_id,
                target_role=body.target_role, resume_token=body.resume_token or "",
                jd_count=result.get("jd_count", 0), verdict_text=result.get("verdict_text", ""),
                gap_type=result.get("gap_type", ""), gap_details=result.get("gap_details", {}),
                strengths=result.get("strengths", []), percentile=result.get("percentile", 0),
                raw_audit=result.get("raw_audit", {}), status="complete",
            )
        except Exception as exc:
            memory.set(f"audit_error:{run_id}", str(exc))
            await emit({"agent": "Audit", "message": f"Audit failed: {exc}"})
        finally:
            await q.put({"type": "end"})

    bg.add_task(job)
    return {"run_id": run_id}

@app.get("/audit/{run_id}/result")
async def readiness_audit_result(run_id: str):
    result = memory.get(f"audit:{run_id}") or sql_store.audit_get_by_run_id(run_id)
    if result:
        return result
    error = memory.get(f"audit_error:{run_id}")
    if error:
        raise HTTPException(500, error)
    raise HTTPException(404, "Audit is not complete yet")

@app.post("/audit/{audit_id}/one-thing")
async def readiness_one_thing(audit_id: str):
    audit = sql_store.audit_get(audit_id)
    if not audit:
        raise HTTPException(404, "Audit not found")
    from .workers.readiness_tasks import start_one_thing_task
    return await start_one_thing_task(audit)

@app.post("/outcomes/log")
async def create_outcome(body: OutcomeBody):
    from .agents.readiness.verdict_loop import log_outcome
    return await log_outcome(
        user_id=body.user_id, audit_id=body.audit_id, company=body.company,
        role=body.role, outcome=body.outcome,
    )

@app.get("/outcomes/patterns")
async def outcome_patterns(user_id: str = "demo-user"):
    from .agents.readiness.verdict_loop import get_patterns
    return await get_patterns(user_id)

@app.on_event("startup")
async def _startup():
    try:
        import sys, asyncio as _asyncio
        if sys.platform.startswith("win"):
            try:
                _asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())
            except Exception:
                pass
        sql_store.init()
        print("✅ SQLite initialized successfully")

        # Seed once here rather than defensively on every /resources request
        from .resources_library import ensure_resources_seeded
        print(f"✅ AI resource library ready ({ensure_resources_seeded()} resources)")
    except Exception as e:
        print(f"⚠️ SQLite init failed: {e}")
        # Continue anyway - don't let this break the server

# Removed unused /run endpoint

# Removed unused /test-agent and /subrun endpoints

# Removed unused /explore endpoint

@app.get("/timeline/{run_id}")
async def timeline(run_id: str):
    q = bus.get(run_id)
    if not q: raise HTTPException(404, "Unknown run_id")
    
    async def gen():
        try:
            # Send initial connection confirmation
            yield "data: " + json.dumps({"type": "connected", "run_id": run_id}) + "\n\n"
            
            while True:
                try:
                    # Set a timeout to prevent hanging
                    item = await asyncio.wait_for(q.get(), timeout=30.0)
                    
                    if item.get("type") == "end":
                        yield "event: end\n" + "data: {\"status\": \"done\"}\n\n"
                        break
                    
                    # Ensure proper JSON serialization
                    data = json.dumps(item, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield "data: " + json.dumps({"type": "heartbeat", "run_id": run_id}) + "\n\n"
                    continue
                except Exception as e:
                    # Log error and send error event
                    yield "data: " + json.dumps({"type": "error", "message": str(e)}) + "\n\n"
                    break
                    
        except Exception as e:
            yield "data: " + json.dumps({"type": "fatal_error", "message": str(e)}) + "\n\n"
    
    return StreamingResponse(
        gen(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable proxy buffering
        }
    )

@app.get("/results/{run_id}")
async def results(run_id: str, offset: int = 0, limit: int = 5):
    """Paginated job-search results for the UI.

    Returns {run_id, city, role, companies, pagination, ...} — the shape the
    frontend's getResults() expects. Companies come from the stored RAGDoc,
    sorted by score and sliced to the requested page.
    """
    from .agents.rag_companies import get_rag_results

    # Rehydrate from the database when this process didn't run the search — a
    # restart, or a second instance. Without this, results vanished on redeploy.
    if memory.get(f"ragdoc:{run_id}") is None:
        persisted = sql_store.search_run_get(run_id)
        if persisted is None:
            raise HTTPException(404, "No results found for this run_id")
        memory.set(f"ragdoc:{run_id}", persisted)

    rag_doc = await get_rag_results(run_id, offset=offset, limit=limit, memory_store=memory)
    payload = rag_doc.model_dump()

    # RAGDoc stores the place as `location`; the frontend reads `city`.
    payload["city"] = payload.get("location", "")

    # Recompute pagination for THIS request — the stored value reflects the
    # offset the search ran at, not the page the UI just asked for.
    total = payload.get("total", len(payload.get("companies", [])))
    payload["pagination"] = {
        "offset": offset,
        "limit": limit,
        "total": total,
        "has_more": (offset + limit) < total,
    }
    return payload

# Removed unused /export endpoint

@app.get("/debug/memory/{run_id}")
async def debug_memory(run_id: str):
    """Debug endpoint to check what's stored in memory for a run_id"""
    ragdoc = memory.get(f"ragdoc:{run_id}", None)
    artifacts = memory.get(f"artifacts:{run_id}", None)
    return {
        "run_id": run_id,
        "ragdoc_exists": ragdoc is not None,
        "ragdoc_keys": list(ragdoc.keys()) if ragdoc else None,
        "artifacts_exists": artifacts is not None,
        "artifacts_keys": list(artifacts.keys()) if artifacts else None,
        "memory_keys": [k for k in memory.kv.keys() if run_id in k]
    }

@app.post("/test/enhanced-research")
async def test_enhanced_research():
    """Test endpoint for enhanced research agent"""
    from server.agents.enhanced_research_agent import EnhancedResearchAgent
    
    # Test with a single company
    test_company = {
        "name": "Brewit",
        "blurb": "Conversational data analytics for every team",
        "homepage": "https://brewit.ai",
        "city": "San Francisco",
        "source_url": "https://example.com",
        "tags": ["AI", "analytics"],
        "contact_hint": "careers@brewit.ai",
        "score": 0.85
    }
    
    async with EnhancedResearchAgent() as research_agent:
        results = await research_agent.analyze_companies([test_company])
        
    if results:
        enhanced_company = results[0]
        return {
            "test_company": test_company,
            "enhanced_data": {
                "name": enhanced_company.name,
                "competitors": enhanced_company.competitors,
                "funding_stage": enhanced_company.funding_stage,
                "last_funding": enhanced_company.last_funding,
                "tech_stack": enhanced_company.tech_stack,
                "market_position": enhanced_company.market_position,
                "company_size": enhanced_company.company_size,
                "growth_indicator": enhanced_company.growth_indicator,
                "confidence_score": enhanced_company.confidence_score,
                "data_sources": enhanced_company.data_sources
            }
        }
    else:
        return {"error": "Enhanced research failed"}


@app.get("/health")
async def health():
    """Health check endpoint — also pings Supabase to prevent auto-pause."""
    db_ok = False
    db_error = None
    try:
        from .supabase_client import SUPABASE_URL, get_supabase_client
        if not SUPABASE_URL:
            raise RuntimeError("SUPABASE_URL is not set")
        sb = get_supabase_client()
        if sb is None:
            raise RuntimeError("supabase client failed to initialise (missing key?)")
        # Any REST request touches PostgREST → Postgres, which resets the 7-day idle timer.
        sb.table("readiness_audits").select("id", count="exact").limit(1).execute()
        db_ok = True
    except Exception as e:
        # Truncated reason, never a bare pass — "unavailable" with no cause is
        # undebuggable (env? network? missing table?).
        db_error = str(e)[:160]
    body = {"status": "ok", "db": "connected" if db_ok else "unavailable", "message": "Agentception API is running"}
    if db_error:
        body["db_error"] = db_error
    return body

@app.get("/debug/memory/{run_id}")
async def debug_memory(run_id: str):
    """Debug endpoint to check if anything is stored for a run_id"""
    stored_data = memory.get(f"artifacts:{run_id}")
    all_keys = list(memory.kv.keys())
    
    # Show actual housing data
    housing_data = []
    if stored_data and "housing" in stored_data:
        housing_list = stored_data["housing"]
        for h in housing_list[:3]:  # Show first 3
            if hasattr(h, 'title'):
                housing_data.append({
                    "title": h.title,
                    "price": h.price,
                    "url": h.url,
                    "neighborhood": h.neighborhood
                })
    
    return {
        "run_id": run_id,
        "has_data": stored_data is not None,
        "data_keys": list(stored_data.keys()) if stored_data else None,
        "housing_count": len(stored_data.get("housing", [])) if stored_data else 0,
        "events_count": len(stored_data.get("events", [])) if stored_data else 0,
        "sample_housing": housing_data,
        "all_memory_keys": all_keys,
        "perplexity_key": "SET" if os.getenv("PERPLEXITY_API_KEY") else "NOT SET",
        "tavily_key": "SET" if os.getenv("TAVILY_API_KEY") else "NOT SET"
    }

# Removed unused debug/perplexity endpoint

@app.get("/debug/exa")
async def debug_exa():
    try:
        from .tools.exa_search import exa_search
        print("🔍 DEBUG: Testing Exa from FastAPI...")
        results = await exa_search("site:eventbrite.com/e AI meetup San Francisco", include_domains=["eventbrite.com/e"], num_results=1)
        return {
            "exa_working": True,
            "results_count": len(results),
            "first_result": results[0] if results else None,
            "exa_key": "SET" if os.getenv("EXA_API_KEY") else "NOT SET"
        }
    except Exception as e:
        print(f"🔍 DEBUG: Exa failed: {e}")
        return {"exa_working": False, "error": str(e), "exa_key": "SET" if os.getenv("EXA_API_KEY") else "NOT SET"}

# Removed unused debug/housing endpoint

# Removed unused /eval/run endpoint

@app.post("/save/add")
async def save_add(body: SaveBody):
    try:
        sql_store.save_add(body.kind, body.item)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/save/list")
async def save_list(kind: Optional[str] = None):
    try:
        return {"items": sql_store.save_list(kind)}
    except Exception as e:
        raise HTTPException(500, str(e))

def _resume_insights(token: str):
    from .tools.resume_store import extract_resume_insights
    try:
        return extract_resume_insights(token)
    except Exception as e:
        print(f"⚠️ Resume insights extraction failed: {e}")
        return None

@app.get("/me")
async def me(user: User = Depends(current_user)):
    """Who the caller is. Anonymous is a supported, first-class answer."""
    return {"user_id": user.id, "email": user.email, "anonymous": user.is_anonymous}


@app.delete("/me/data")
async def delete_my_data(user: User = Depends(require_user)):
    """Hard-delete everything tied to this account.

    Requires a real token — you cannot delete an account you aren't signed in to.
    This genuinely deletes rows; a privacy promise you don't implement is a lie.
    """
    deleted = sql_store.purge_user_data(user.id)
    from .tools.resume_store import forget_user

    forget_user(user.id)
    return {"deleted": deleted, "user_id": user.id}


@app.post("/upload/resume", dependencies=[Depends(limit(llm_limiter))])
async def upload_resume(file: UploadFile = File(...)):
    """Upload and parse PDF resume, return token for RAG/Writer agents"""
    try:
        from .tools.resume_store import put_text, put_profile
        from .tools.resume_ingest import parse_resume

        data = await file.read()
        parsed = await parse_resume(data, file.filename or "resume.pdf")
        text, structured = parsed["text"], parsed["structured"]

        token = put_text(text)
        if structured is not None:
            put_profile(token, structured)

        print(f"📄 Resume uploaded: {file.filename}, {len(text)} chars via {parsed['parser']}")
        return {
            "token": token,
            "chars": len(text),
            "filename": file.filename,
            "text_preview": text[:600],
            "insights": _resume_insights(token),
            "structured": structured,
            "parser": parsed["parser"],
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Resume upload failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")

@app.get("/upload/resume/{token}")
async def get_resume(token: str):
    """Fetch previously uploaded resume text + structured profile by token."""
    from .tools.resume_store import get_text, get_profile, put_profile
    from .tools.resume_ingest import structured_profile

    text = get_text(token)
    if not text:
        raise HTTPException(404, "Resume not found. Please upload again.")

    structured = get_profile(token)
    if structured is None:
        # Only reachable for tokens stored before the profile cache existed
        structured = structured_profile(text)
        if structured is not None:
            put_profile(token, structured)

    return {
        "token": token,
        "chars": len(text),
        "text_preview": text[:600],
        "insights": _resume_insights(token),
        "structured": structured,
    }

class FetchJDBody(BaseModel):
    job_url: str
    snippet: Optional[str] = None

@app.post("/api/fetch-job-description")
async def fetch_jd(body: FetchJDBody):
    """Fetch and extract a job description from a job posting URL."""
    from .tools.job_description_fetcher import fetch_job_description
    try:
        text = await fetch_job_description(body.job_url, body.snippet)
        return {"job_text": text}
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch job description: {e}")

@app.get("/debug/pdf")
async def debug_pdf():
    """Debug endpoint to test PDF parsing libraries"""
    import sys
    libraries = {}
    
    # Test PyMuPDF (fitz)
    try:
        import fitz
        libraries["PyMuPDF"] = {"available": True, "version": fitz.version}
    except ImportError as e:
        libraries["PyMuPDF"] = {"available": False, "error": str(e)}
    
    # Test pypdf
    try:
        import pypdf
        libraries["pypdf"] = {"available": True, "version": pypdf.__version__}
    except ImportError as e:
        libraries["pypdf"] = {"available": False, "error": str(e)}
    
    # Test pdfplumber
    try:
        import pdfplumber
        libraries["pdfplumber"] = {"available": True, "version": pdfplumber.__version__}
    except ImportError as e:
        libraries["pdfplumber"] = {"available": False, "error": str(e)}
    
    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "libraries": libraries
    }

@app.get("/debug/fitz")
async def debug_fitz():
    """Debug endpoint to test fitz import"""
    import sys
    try:
        import fitz
        return {
            "fitz_available": True,
            "fitz_version": fitz.version,
            "python_version": sys.version,
            "python_executable": sys.executable,
            "python_path": sys.path[:3]  # First 3 paths
        }
    except ImportError as e:
        return {
            "fitz_available": False,
            "error": str(e),
            "python_version": sys.version,
            "python_executable": sys.executable,
            "python_path": sys.path[:3]  # First 3 paths
        }

@app.get("/debug/matcher")
async def debug_matcher():
    """Debug endpoint to test matcher functionality"""
    import os
    return {
        "voyage_key_set": bool(os.getenv("VOYAGE_API_KEY")),
        "voyage_key_preview": os.getenv("VOYAGE_API_KEY", "")[:8] + "..." if os.getenv("VOYAGE_API_KEY") else "Not set",
        "fallback_mode": "Keyword matching will be used if Voyage AI is not available"
    }

@app.post("/rag/companies", dependencies=[Depends(limit(search_limiter))])
async def rag_companies(body: RagBody, bg: BackgroundTasks):
    """
    RAG company discovery endpoint:
    1. Discover companies using role-aware Exa search
    2. Build comprehensive RAG document
    3. Store results for Writer agent
    4. Stream timeline updates
    """
    run_id = str(uuid.uuid4())
    q = bus.ensure(run_id)
    
    async def emit(ev):
        # Accept either TimelineEvent or plain string/dict and normalize
        try:
            if isinstance(ev, TimelineEvent):
                await q.put(ev.model_dump())
            elif isinstance(ev, str):
                await q.put(TimelineEvent(run_id=run_id, agent="Writer", message=ev).model_dump())
            elif isinstance(ev, dict):
                # minimal dict with message
                msg = ev.get("message", str(ev))
                await q.put(TimelineEvent(run_id=run_id, agent=ev.get("agent", "Writer"), message=msg).model_dump())
            else:
                await q.put(TimelineEvent(run_id=run_id, agent="Writer", message=str(ev)).model_dump())
        except Exception as _e:
            # As a last resort, push a basic error message to the stream
            await q.put(TimelineEvent(run_id=run_id, agent="Writer", message=f"emit error: {_e}").model_dump())
    
    async def job():
        try:
            print(f"🚀 Starting RAG job for run_id: {run_id}")
            from .agents.rag_companies import run_rag_company_search
            
            # Run RAG company search workflow with multi-role search enabled.
            # Pass the shared `memory` so the full company list and the Load-More
            # cache land where /results and /writer can read them — without this
            # the agent writes them to a throwaway Memory() and only the first
            # page survives.
            doc = await run_rag_company_search(
                run_id=run_id,
                city=body.city,
                role=body.role or "",  # empty -> search derives role from the resume
                resume_token=body.resumeToken,
                emit=emit,
                multi_role=True,  # Enable multi-role search for better company coverage
                depth=body.depth,  # Pass depth parameter for resource limits
                memory_store=memory,
            )

            print(f"📄 RAG search completed, first page has {len(doc.get('companies', []))} companies")

            # run_rag_company_search already stored the FULL RAGDoc at
            # ragdoc:{run_id}; keep it intact so /results can paginate over every
            # result. Fall back to the returned first page only if it's missing.
            if not memory.get(f"ragdoc:{run_id}"):
                memory.set(f"ragdoc:{run_id}", doc)

            # Persist it. In-memory alone meant a restart threw away results the user
            # had already paid for in Tavily/Exa/Voyage calls.
            full = memory.get(f"ragdoc:{run_id}") or doc
            sql_store.search_run_save(
                run_id=run_id,
                user_id=None,
                role=full.get("role") or body.role or "",
                city=full.get("location") or full.get("city") or body.city,
                doc=full,
            )
            print(f"✅ ragdoc:{run_id} ready (memory + sqlite)")
            
            await emit(TimelineEvent(
                run_id=run_id, 
                agent="RAG", 
                message="🎉 RAG workflow complete - ready for Writer agent!"
            ))
            
        except Exception as e:
            print(f"❌ RAG job failed: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            await emit(TimelineEvent(
                run_id=run_id, 
                agent="RAG", 
                message=f"❌ RAG workflow failed: {str(e)}",
                level="error"
            ))
        finally:
            print(f"🏁 RAG job finished for run_id: {run_id}")
            await q.put({"type": "end"})
    
    bg.add_task(job)
    return {"run_id": run_id}

@app.post("/writer/outreach")
async def writer_outreach(body: WriterBody, bg: BackgroundTasks):
    """
    Generate targeted outreach emails using RAG document data
    
    Requires a completed RAG workflow (run_id from /rag/companies)
    Returns personalized emails for top companies
    """
    
    print(f"🔍 Writer endpoint called with run_id: {body.run_id}")
    print(f"🔍 Request body: {body}")
    
    # Retrieve RAG document from memory
    doc = memory.get(f"ragdoc:{body.run_id}", None)
    print(f"🔍 RAG document found: {doc is not None}")
    
    if not doc:
        print(f"❌ No RAG document found for run_id: {body.run_id}")
        print(f"🔍 Available memory keys: {[k for k in memory.kv.keys() if body.run_id in k]}")
        raise HTTPException(status_code=404, detail="No RAG document found for this run_id. Run /rag/companies first.")
    
    companies = doc.get("companies", [])
    print(f"🔍 Companies in RAG doc: {len(companies)}")
    
    if not companies:
        print(f"❌ No companies found in RAG document")
        print(f"🔍 RAG doc keys: {list(doc.keys())}")
        raise HTTPException(status_code=400, detail="No companies found in RAG document. Cannot generate emails.")
    
    print(f"📧 Generating {body.n} outreach emails for run {body.run_id}")
    print(f"   Role: {doc['role']}")
    print(f"   City: {doc['city']}")
    print(f"   Companies available: {len(doc['companies'])}")
    
    # Create a new run_id for the Writer workflow timeline
    run_id = str(uuid.uuid4())
    q = bus.ensure(run_id)
    
    async def emit(ev):
        # Accept either TimelineEvent or plain string/dict and normalize
        try:
            if isinstance(ev, TimelineEvent):
                await q.put(ev.model_dump())
            elif isinstance(ev, str):
                await q.put(TimelineEvent(run_id=run_id, agent="Writer", message=ev).model_dump())
            elif isinstance(ev, dict):
                # minimal dict with message
                msg = ev.get("message", str(ev))
                await q.put(TimelineEvent(run_id=run_id, agent=ev.get("agent", "Writer"), message=msg).model_dump())
            else:
                await q.put(TimelineEvent(run_id=run_id, agent="Writer", message=str(ev)).model_dump())
        except Exception as _e:
            # As a last resort, push a basic error message to the stream
            await q.put(TimelineEvent(run_id=run_id, agent="Writer", message=f"emit error: {_e}").model_dump())
    
    async def job():
        try:
            # Generate emails using Writer agent with timeline updates
            from .agents.writer_outreach import write_emails
            emails = await write_emails(doc, n=body.n, emit=emit)
            
            # Store emails in artifacts for UI display
            artifacts = memory.get(f"artifacts:{body.run_id}", {
                "events": [], 
                "housing": [], 
                "places": [], 
                "emails": []
            })
            artifacts["emails"] = emails
            memory.set(f"artifacts:{body.run_id}", artifacts)
            
            print(f"✅ Generated and stored {len(emails)} emails")
            
        except Exception as e:
            await emit(TimelineEvent(run_id=run_id, agent="Writer", message=f"❌ Email generation failed: {str(e)}"))
            print(f"❌ Writer outreach failed: {e}")
        finally:
            await q.put({"type":"end"})
    
    bg.add_task(job)
    return {"run_id": run_id}
