"""
Decision engine: maps audit gap → one concrete action.

  gap_type == "ready"    → apply_now (generate outreach emails for top companies)
  gap_type == "framing"  → reframe_bullet (rewrite undefendable resume claims)
  gap_type == "skills"   → learn_module (14-day focused learning plan)
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Optional

from ...supabase_client import get_supabase_client
from ...data.audit_prompts import APPLY_NOW_PROMPT


async def _call_llm(prompt: str, model: str = "gpt-4o-mini") -> str:
    import httpx
    api_key = os.getenv("OPENAI_API_KEY", "")
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _parse_json(text: str) -> dict:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()
    if clean.startswith("json"):
        clean = clean[4:].strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"_raw": text}


async def decide_one_thing(audit_result: dict) -> dict:
    """
    Given a completed audit, produce the single best next action.
    Returns an action dict and stores it in Supabase.
    """
    gap_type = audit_result.get("gap_type", "skills")
    audit_id = audit_result.get("audit_id")

    if gap_type == "ready":
        action = await _handle_ready(audit_result)
    elif gap_type == "framing":
        action = await _handle_framing(audit_result)
    else:
        action = await _handle_skills(audit_result)

    # Store in Supabase
    action_record = {
        "audit_id": audit_id,
        "action_type": action["action_type"],
        "action_data": action.get("data", {}),
        "deadline_days": action.get("deadline_days", 14),
    }

    try:
        sb = get_supabase_client()
        if sb and audit_id:
            result = sb.table("one_thing_actions").insert(action_record).execute()
            if result.data:
                action["action_id"] = result.data[0]["id"]
    except Exception as e:
        print(f"⚠️ Failed to save action to Supabase: {e}")

    return action


async def _handle_ready(audit: dict) -> dict:
    """Generate apply-now action with company recommendations."""
    companies = audit.get("companies", [])[:5]
    strengths = audit.get("strengths", [])

    prompt = APPLY_NOW_PROMPT.format(
        audit_json=json.dumps({
            "gap_type": "ready",
            "percentile": audit.get("percentile", 80),
            "verdict_text": audit.get("verdict_text", ""),
        }),
        companies=json.dumps(companies[:5], default=str),
        strengths=json.dumps(strengths),
    )

    resp = await _call_llm(prompt)
    data = _parse_json(resp)

    return {
        "action_type": "apply_now",
        "data": data,
        "deadline_days": 7,
        "summary": "You're ready! Here are your top companies to target.",
    }


async def _handle_framing(audit: dict) -> dict:
    """Reframe undefendable resume bullets."""
    from .one_thing.reframe_bullets import reframe_all_bullets

    claims = audit.get("gap_details", {}).get("undefendable_claims", [])
    target_role = audit.get("target_role", "Software Engineer")
    skills = [s.get("skill", "") for s in audit.get("strengths", [])]

    reframed = await reframe_all_bullets(claims, skills, target_role)

    return {
        "action_type": "reframe_bullet",
        "data": {"reframed_bullets": reframed},
        "deadline_days": 3,
        "summary": f"Rewrite {len(claims)} resume bullets that won't hold up in interviews.",
    }


async def _handle_skills(audit: dict) -> dict:
    """Generate a 14-day learning module for the top gap skill."""
    from .one_thing.learning_module_generator import generate_learning_module

    gaps = audit.get("gap_details", {}).get("gaps", [])
    target_role = audit.get("target_role", "Software Engineer")

    # Pick the highest-frequency gap
    if gaps:
        sorted_gaps = sorted(gaps, key=lambda g: g.get("jd_frequency", 0), reverse=True)
        top_gap = sorted_gaps[0].get("skill", "Python")
    else:
        top_gap = "Python"

    module = await generate_learning_module(
        gap_skill=top_gap,
        target_role=target_role,
        current_level="beginner",
    )

    return {
        "action_type": "learn_module",
        "data": module,
        "deadline_days": 14,
        "summary": f"14-day sprint to close your '{top_gap}' gap.",
    }
