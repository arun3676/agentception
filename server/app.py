from __future__ import annotations
import json, uuid, asyncio
import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
from .schemas import TimelineEvent
from .memory.state_store import Memory, TimelineBus
from .memory import sql_store

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
    role: str
    resumeToken: str | None = None
    depth: str = "standard"

class WriterBody(BaseModel):
    run_id: str
    n: int = 5

app = FastAPI(title="Agentception API")

origins = [
    "http://localhost:3000",
    "https://*.vercel.app",   # Vercel preview + prod
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = Memory(); bus = TimelineBus()

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
async def results(run_id: str):
    """Get workflow results for preview, ensuring ragdoc is included."""
    data = memory.get(f"artifacts:{run_id}", None)
    if not data:
        # As a fallback, check if a ragdoc exists alone
        ragdoc = memory.get(f"ragdoc:{run_id}", None)
        if ragdoc:
            return {"ragdoc": ragdoc}
        raise HTTPException(404, "No results or RAG document found for this run_id")
    
    # Ensure ragdoc is included if it was created
    if "ragdoc" not in data:
        ragdoc = memory.get(f"ragdoc:{run_id}", None)
        if ragdoc:
            data["ragdoc"] = ragdoc
            
    # Clean up any non-serializable data if necessary (optional, but good practice)
    data.pop("extras", None)
    return data

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
    return {"status": "ok", "message": "Agentception API is running"}

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

@app.post("/upload/resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload and parse PDF resume, return token for RAG/Writer agents"""
    try:
        # Read the uploaded file
        data = await file.read()
        text = ""
        
        # Try multiple PDF parsing methods
        try:
            # Method 1: PyMuPDF (fitz)
            import fitz  # type: ignore
            doc = fitz.open(stream=data, filetype="pdf")
            text = "\n".join(page.get_text("text") for page in doc)
            doc.close()
            print(f"📄 PDF parsed with PyMuPDF (fitz)")
        except ImportError:
            print(f"⚠️ PyMuPDF not available, trying pypdf...")
            try:
                # Method 2: pypdf (fallback)
                import pypdf  # type: ignore
                import io
                reader = pypdf.PdfReader(io.BytesIO(data))
                text = "\n".join(page.extract_text() for page in reader.pages)
                print(f"📄 PDF parsed with pypdf")
            except ImportError:
                print(f"⚠️ pypdf not available, trying pdfplumber...")
                try:
                    # Method 3: pdfplumber (fallback)
                    import pdfplumber  # type: ignore
                    import io
                    with pdfplumber.open(io.BytesIO(data)) as pdf:
                        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                    print(f"📄 PDF parsed with pdfplumber")
                except ImportError:
                    raise Exception("No PDF parsing library available. Install PyMuPDF, pypdf, or pdfplumber.")
        
        if not text.strip():
            raise Exception("No text could be extracted from the PDF")
        
        # Store text and return token
        from .tools.resume_store import put_text
        token = put_text(text)
        
        print(f"📄 Resume uploaded: {file.filename}, {len(text)} characters extracted")
        return {"token": token, "chars": len(text), "filename": file.filename}
        
    except Exception as e:
        print(f"❌ Resume upload failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")

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

@app.post("/rag/companies")
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
            
            # Run RAG company search workflow with multi-role search enabled
            doc = await run_rag_company_search(
                run_id=run_id, 
                city=body.city, 
                role=body.role, 
                resume_token=body.resumeToken, 
                emit=emit,
                multi_role=True,  # Enable multi-role search for better company coverage
                depth=body.depth  # Pass depth parameter for resource limits
            )
            
            print(f"📄 RAG search completed, storing document with {len(doc.get('companies', []))} companies")
            
            # Store RAG document for Writer agent
            memory.set(f"ragdoc:{run_id}", doc)
            print(f"✅ Stored ragdoc:{run_id} in memory")
            
            # Also mirror to /results endpoint for UI rendering
            memory.set(f"artifacts:{run_id}", {
                "events": [], 
                "housing": [], 
                "places": [], 
                "emails": [], 
                "ragdoc": doc
            })
            print(f"✅ Stored artifacts:{run_id} in memory")
            
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
