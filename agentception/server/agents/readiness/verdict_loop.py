"""
Verdict Loop: logs application outcomes and detects patterns.

- Reads application_outcomes for a user
- Requires min 5 outcomes before showing patterns
- Returns insight text + statistics
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Optional

from ...supabase_client import get_supabase_client

_LOCAL_OUTCOMES: list[dict] = []


async def _call_llm(prompt: str, model: str = "gpt-4o-mini") -> str:
    import httpx, asyncio
    api_key = os.getenv("OPENAI_API_KEY", "")
    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.5,
                    },
                )
                if resp.status_code == 429:
                    wait = min(2 ** attempt * 5, 30)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            if status == 429 and attempt < 2:
                await asyncio.sleep(min(2 ** attempt * 5, 30))
                continue
            last_error = e
    raise RuntimeError(f"LLM call failed after 3 attempts: {last_error}")


async def log_outcome(
    *,
    user_id: str,
    audit_id: Optional[str],
    company: str,
    role: str,
    outcome: str,
) -> dict:
    """Log a single application outcome. Supabase first, SQLite as durable fallback."""
    record = {
        "user_id": user_id,
        "company": company,
        "role": role,
        "outcome": outcome,
    }
    if audit_id:
        record["audit_id"] = audit_id

    try:
        sb = get_supabase_client()
        if sb:
            result = sb.table("application_outcomes").insert(record).execute()
            if result.data:
                return {"ok": True, "id": result.data[0]["id"]}
    except Exception as e:
        print(f"[verdict_loop] Failed to log outcome to Supabase: {e}")

    # Durable SQLite fallback
    try:
        from ...memory.sql_store import outcome_log
        outcome_id = str(uuid.uuid4())
        return outcome_log(
            outcome_id=outcome_id,
            user_id=user_id,
            company=company,
            role=role,
            outcome=outcome,
            audit_id=audit_id or "",
        )
    except Exception as e:
        print(f"[verdict_loop] SQLite fallback failed for outcome logging: {e}")

    # Last-resort in-memory fallback
    local_record = {
        **record,
        "id": str(uuid.uuid4()),
        "outcome_logged_at": datetime.utcnow().isoformat(),
        "storage": "local",
    }
    _LOCAL_OUTCOMES.append(local_record)
    return {"ok": True, "id": local_record["id"], "storage": "local"}


async def get_patterns(user_id: str) -> dict:
    """
    Analyze a user's application outcomes and return patterns.
    Requires at least 5 outcomes to generate meaningful insights.
    """
    outcomes: list[dict] = []
    sb = None
    try:
        sb = get_supabase_client()
        if sb:
            result = (
                sb.table("application_outcomes")
                .select("*")
                .eq("user_id", user_id)
                .order("outcome_logged_at", desc=True)
                .execute()
            )
            outcomes = result.data or []
    except Exception as e:
        print(f"Failed to fetch Supabase outcomes: {e}")

    # If Supabase empty or failed, try SQLite fallback
    if not outcomes:
        try:
            from ...memory.sql_store import outcomes_for_user
            outcomes = outcomes_for_user(user_id, limit=50)
        except Exception as e:
            print(f"Failed to fetch SQLite outcomes: {e}")

    # Last-resort: in-memory
    if not outcomes:
        outcomes = [
            item for item in reversed(_LOCAL_OUTCOMES)
            if item.get("user_id") == user_id
        ]

    if len(outcomes) < 5:
        return {
            "ready": False,
            "reason": f"Need at least 5 logged outcomes (you have {len(outcomes)}). Keep applying!",
            "outcomes_count": len(outcomes),
            "outcomes": outcomes,
        }

    # Compute statistics
    total = len(outcomes)
    stats = {}
    for o in outcomes:
        key = o.get("outcome", "unknown")
        stats[key] = stats.get(key, 0) + 1

    callback_rate = (stats.get("screen", 0) + stats.get("onsite", 0) + stats.get("offer", 0)) / total
    ghost_rate = stats.get("ghosted", 0) / total

    # Fetch latest audit for context
    audit_context = ""
    try:
        if sb:
            audit_result = (
                sb.table("readiness_audits")
                .select("verdict_text, gap_type, target_role")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if audit_result.data:
                audit_context = json.dumps(audit_result.data[0])
    except Exception:
        pass

    # Generate insight via LLM (with deterministic fallback)
    prompt = f"""Analyze these job application outcomes and give 1-2 paragraphs of actionable insight.

Stats: {json.dumps(stats)}
Callback rate: {callback_rate:.0%}
Ghost rate: {ghost_rate:.0%}
Total applications: {total}

Latest audit context: {audit_context}

Recent outcomes (newest first):
{json.dumps(outcomes[:10], default=str)}

Be direct. If ghosted rate is high, say why and what to fix.
If callbacks are good, suggest doubling down on what's working."""

    insight = ""
    try:
        insight = await _call_llm(prompt)
    except Exception as e:
        print(f"[verdict_loop] LLM insight generation failed: {e}, using deterministic fallback")
    
    if not insight or len(insight) < 20:
        # Deterministic fallback based on stats
        parts = []
        if ghost_rate > 0.6:
            parts.append(f"High ghost rate ({round(ghost_rate * 100)}%): your resume may not be passing ATS screens. Tailor your resume to each job's keywords and emphasize recent relevant experience.")
        elif ghost_rate > 0.3:
            parts.append(f"Moderate ghost rate ({round(ghost_rate * 100)}%). Consider adding more specific technical keywords and quantifying achievements.")
        if callback_rate > 0.3:
            parts.append(f"Strong callback rate ({round(callback_rate * 100)}%) — your profile resonates with employers. Keep targeting roles that match your core skills and consider negotiating timing.")
        elif callback_rate > 0:
            parts.append(f"Callback rate at {round(callback_rate * 100)}%. To improve, ensure your LinkedIn and resume highlight measurable impact and align with the job description's required skills.")
        else:
            parts.append(f"No callbacks yet out of {total} applications. Review your resume for ATS compatibility, expand your network, and consider applying to 5 more roles before analyzing patterns again.")
        if not parts:
            parts.append(f"Apply to more roles to generate meaningful patterns. Currently tracking {total} applications across {len(stats)} outcome types.")
        insight = " ".join(parts)
    
    return {
        "ready": True,
        "outcomes_count": total,
        "stats": stats,
        "callback_rate": round(callback_rate * 100, 1),
        "ghost_rate": round(ghost_rate * 100, 1),
        "insight": insight,
        "outcomes": outcomes[:20],
    }
