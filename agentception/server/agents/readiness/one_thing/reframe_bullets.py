"""
Rewrites undefendable resume bullets using GPT-4o with specific JD evidence.
Each bullet is rewritten to be honest, specific, and interview-ready.
"""
from __future__ import annotations

import json
import os
from typing import List

from ....data.audit_prompts import REFRAME_PROMPT


async def _call_llm(prompt: str, model: str = "gpt-4o-mini") -> str:
    import httpx
    api_key = os.getenv("OPENAI_API_KEY", "")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
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
        return {"original": "", "rewritten": text, "why_better": "Auto-parse failed"}


async def reframe_single_bullet(
    bullet: str,
    reason: str,
    skills: List[str],
    target_role: str,
) -> dict:
    """Reframe a single resume bullet."""
    prompt = REFRAME_PROMPT.format(
        original_bullet=bullet,
        reason=reason,
        skills=", ".join(skills),
        target_role=target_role,
    )
    resp = await _call_llm(prompt)
    return _parse_json(resp)


async def reframe_all_bullets(
    claims: List[dict],
    skills: List[str],
    target_role: str,
) -> List[dict]:
    """Reframe all undefendable bullets from the audit."""
    results = []
    for claim in claims[:5]:  # Cap at 5 to avoid API cost explosion
        bullet = claim.get("bullet", "")
        reason = claim.get("reason", "Not specific enough")
        if not bullet:
            continue
        reframed = await reframe_single_bullet(bullet, reason, skills, target_role)
        results.append(reframed)
    return results
