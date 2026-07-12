"""
CORE: Orchestrates the career readiness audit.

Flow:
  1. run_rag_company_search() — scrapes ~20 live JDs via existing RAG agent
  2. exa_portfolio_search()  — finds real engineer portfolios for benchmarking
  3. JobMarketAnalyzer()     — Perplexity live market signal (from learning-path data)
  4. LLM audit call          — sends [resume + JDs] → structured gap analysis
  5. LLM verdict call        — converts JSON → honest paragraph
  6. Store in readiness_audits table (Supabase)
  7. Emit SSE via existing TimelineBus
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Callable, Coroutine, Optional

from ..rag_companies import run_rag_company_search, get_rag_results
from ...tools.resume_store import get_text as get_resume_text, extract_resume_insights
from ...data.audit_prompts import AUDIT_PROMPT, VERDICT_PROMPT
from ...supabase_client import get_supabase_client
from ...memory.state_store import Memory, TimelineBus
from ...schemas import TimelineEvent

# Type alias for the SSE emitter
EmitFn = Callable[[Any], Coroutine[Any, Any, None]]


async def _call_llm(prompt: str, model: str = "gpt-4o-mini") -> str:
    """Call OpenAI-compatible LLM and return the response text. Retries on rate limit."""
    import httpx, asyncio

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                )
                if resp.status_code == 429:
                    wait = min(2 ** attempt * 5, 30)
                    print(f"[audit_engine] Rate limited (429), retrying in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait = min(2 ** attempt * 5, 30)
                print(f"[audit_engine] Rate limited (429), retrying in {wait}s...")
                await asyncio.sleep(wait)
                continue
            last_error = e
            break
        except Exception as e:
            last_error = e
            if attempt < 2:
                await asyncio.sleep(2)
                continue
            break
    raise RuntimeError(f"LLM call failed after 3 attempts: {last_error}")


async def run_audit(
    *,
    target_role: str,
    resume_token: Optional[str] = None,
    user_id: Optional[str] = None,
    city: str = "San Francisco",
    emit: Optional[EmitFn] = None,
    memory_store: Optional[Memory] = None,
) -> dict:
    """
    Run a full career readiness audit. Returns the audit result dict
    and stores it in Supabase.
    """
    run_id = str(uuid.uuid4())
    mem = memory_store or Memory()

    async def _emit(msg: str, agent: str = "Audit"):
        if emit:
            await emit(TimelineEvent(run_id=run_id, agent=agent, message=msg))

    # ── Step 1: Get resume text ──────────────────────────────────────
    resume_text = ""
    if resume_token:
        resume_text = get_resume_text(resume_token) or ""
        if resume_text:
            await _emit(f"📄 Resume loaded ({len(resume_text)} chars)")
        else:
            await _emit("⚠️ Resume token provided but no text found")

    insights = extract_resume_insights(resume_token) if resume_token else {}

    # ── Step 2: Discover companies + JDs via RAG ─────────────────────
    await _emit(f"🔍 Searching for {target_role} positions in {city}...")

    rag_run_id = str(uuid.uuid4())
    bus = TimelineBus()
    q = bus.ensure(rag_run_id)

    async def rag_emit(ev):
        # Forward RAG events to our audit timeline
        if isinstance(ev, TimelineEvent):
            await _emit(ev.message, agent="RAG")
        elif isinstance(ev, dict):
            await _emit(ev.get("message", str(ev)), agent="RAG")
        elif isinstance(ev, str):
            await _emit(ev, agent="RAG")

    await run_rag_company_search(
        run_id=rag_run_id,
        city=city,
        role=target_role,
        resume_token=resume_token,
        emit=rag_emit,
        multi_role=True,
        depth="standard",
        filters=None,
        offset=0,
        limit=20,
        memory_store=mem,
    )

    rag_doc = await get_rag_results(rag_run_id, offset=0, limit=20, memory_store=mem)
    companies = rag_doc.companies if rag_doc else []
    jd_count = len(companies)
    await _emit(f"✅ Found {jd_count} job descriptions")

    # ── Step 3: Build JD text for audit ──────────────────────────────
    jd_texts = []
    for c in companies:
        c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else {})
        name = c_dict.get("name", "Unknown")
        blurb = c_dict.get("blurb", "")
        tags = ", ".join(c_dict.get("tags", []))
        jd_texts.append(f"Company: {name}\nDescription: {blurb}\nSkills: {tags}")

    all_jds = "\n---\n".join(jd_texts) if jd_texts else "No job descriptions available."

    # ── Step 4: Market signal (lightweight — skip if unavailable) ────
    market_signal = "Market data not available for this run."
    try:
        from ...bridge import data_file
        market_file = data_file("job_market.json")
        if market_file:
            import json as _json
            with open(market_file, "r", encoding="utf-8") as f:
                market_data = _json.load(f)
            # Extract relevant role info
            for pillar in market_data.get("career_pillars", []):
                if target_role.lower() in pillar.get("name", "").lower():
                    market_signal = json.dumps(pillar, indent=2)
                    break
            await _emit("📊 Market signal loaded from learning-path data")
    except Exception as e:
        await _emit(f"⚠️ Market signal unavailable: {e}")

    # ── Step 5: LLM audit call ───────────────────────────────────────
    await _emit("🧠 Running AI audit (resume vs. JDs)...")

    audit_prompt = AUDIT_PROMPT.format(
        jd_count=jd_count,
        resume_text=resume_text[:8000] if resume_text else "No resume provided.",
        all_jds_concatenated=all_jds[:12000],
        perplexity_output=market_signal[:3000],
    )

    raw_audit_text = ""
    audit_data = None
    try:
        raw_audit_text = await _call_llm(audit_prompt, model="gpt-4o-mini")
    except Exception as e:
        await _emit(f"⚠️ AI audit model unavailable after retries: {e}. Using deterministic audit fallback.")
        resume_skills = []
        if isinstance(insights, dict):
            flat = insights.get("skills_flat") or insights.get("skills") or []
            if isinstance(flat, dict):
                for value in flat.values():
                    if isinstance(value, list):
                        resume_skills.extend(str(item).lower() for item in value)
            elif isinstance(flat, list):
                resume_skills = [str(item).lower() for item in flat]
        jd_lower = all_jds.lower()
        target_skills = [
            "python", "sql", "rag", "langchain", "langgraph", "fastapi",
            "docker", "kubernetes", "vector database", "llm", "evaluation",
            "cloud", "react", "typescript", "machine learning",
        ]
        missing = [
            skill for skill in target_skills
            if skill in jd_lower and not any(skill in resume_skill for resume_skill in resume_skills)
        ]
        matched = [
            skill for skill in target_skills
            if skill in jd_lower and any(skill in resume_skill for resume_skill in resume_skills)
        ]
        fallback_percentile = max(25, min(75, 45 + len(matched) * 4 - len(missing) * 3))
        audit_data = {
            "gaps": [{"skill": skill, "why_it_matters": "Appears in matched job descriptions."} for skill in missing[:8]],
            "undefendable_claims": [],
            "strengths": matched[:8] or ["Search returned relevant live roles for comparison."],
            "percentile_estimate": fallback_percentile,
            "gap_type": "skills" if missing else "positioning",
            "_fallback": "deterministic_llm_unavailable",
        }

    # Parse the JSON response
    try:
        # Strip markdown code fences if present
        if audit_data is None:
            clean = raw_audit_text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()
            audit_data = json.loads(clean)
    except json.JSONDecodeError:
        audit_data = {
            "gaps": [],
            "undefendable_claims": [],
            "strengths": [],
            "percentile_estimate": 50,
            "gap_type": "skills",
            "_raw": raw_audit_text,
        }

    gap_type = audit_data.get("gap_type", "skills")
    percentile = audit_data.get("percentile_estimate", 50)
    await _emit(f"📋 Audit complete — gap type: {gap_type}, percentile: {percentile}")

    # ── Step 6: Generate verdict paragraph ───────────────────────────
    await _emit("✍️ Writing verdict...")

    verdict_prompt = VERDICT_PROMPT.format(audit_json=json.dumps(audit_data, indent=2))
    try:
        verdict_text = await _call_llm(verdict_prompt, model="gpt-4o-mini")
    except Exception as e:
        await _emit(f"⚠️ Verdict model unavailable after retries: {e}. Using deterministic verdict fallback.")
        gaps = audit_data.get("gaps", []) if isinstance(audit_data, dict) else []
        strengths = audit_data.get("strengths", []) if isinstance(audit_data, dict) else []
        gap_names = [str(item.get("skill") or item) for item in gaps[:4]]
        strength_names = [str(item) for item in strengths[:4]]
        verdict_text = (
            f"You are around the {percentile}th percentile for this search based on the resume and {jd_count} matched job descriptions. "
            f"Your current strengths are {', '.join(strength_names) if strength_names else 'not yet clear from the resume text'}. "
            f"The highest-priority gaps are {', '.join(gap_names) if gap_names else 'positioning and sharper proof for the target role'}."
        )
    await _emit("✅ Verdict ready")

    # ── Step 7: Store in Supabase ────────────────────────────────────
    audit_record = {
        "target_role": target_role,
        "resume_token": resume_token,
        "jd_count": jd_count,
        "verdict_text": verdict_text,
        "gap_type": gap_type,
        "gap_details": {
            "gaps": audit_data.get("gaps", []),
            "undefendable_claims": audit_data.get("undefendable_claims", []),
        },
        "strengths": audit_data.get("strengths", []),
        "percentile": percentile,
        "raw_audit": audit_data,
    }

    if user_id:
        audit_record["user_id"] = user_id

    audit_id = None
    try:
        sb = get_supabase_client()
        if sb:
            result = sb.table("readiness_audits").insert(audit_record).execute()
            if result.data:
                audit_id = result.data[0]["id"]
                await _emit(f"💾 Audit saved to Supabase (id: {audit_id[:8]}...)")
    except Exception as e:
        await _emit(f"⚠️ Supabase save failed: {e} — data still in memory")

    # Store in memory as well (for SSE retrieval)
    full_result = {
        "audit_id": audit_id or str(uuid.uuid4()),
        "run_id": run_id,
        **audit_record,
        "companies": [c if isinstance(c, dict) else c.model_dump() for c in companies[:10]],
    }
    mem.set(f"audit:{run_id}", full_result)

    await _emit("🎉 Readiness audit complete!")
    return full_result
