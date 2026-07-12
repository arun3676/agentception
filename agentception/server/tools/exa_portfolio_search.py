"""
Exa-powered portfolio search for benchmarking.
Finds real engineer portfolios/GitHub profiles for a given role
so the audit can compare the user's work against actual practitioners.
"""
from __future__ import annotations

import os
from typing import List, Optional

import httpx

EXA_API_KEY = os.getenv("EXA_API_KEY", "")
EXA_BASE_URL = "https://api.exa.ai"


async def search_portfolios(
    role: str,
    skills: Optional[List[str]] = None,
    num_results: int = 5,
) -> List[dict]:
    """
    Search Exa for real engineer portfolios matching a role.
    Returns list of {title, url, snippet} dicts.
    """
    if not EXA_API_KEY:
        print("⚠️ EXA_API_KEY not set — portfolio search skipped")
        return []

    skill_text = f" {' '.join(skills[:3])}" if skills else ""
    query = f"{role} engineer portfolio github projects{skill_text}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{EXA_BASE_URL}/search",
                headers={"x-api-key": EXA_API_KEY},
                json={
                    "query": query,
                    "num_results": num_results,
                    "type": "neural",
                    "use_autoprompt": True,
                    "include_domains": ["github.com", "portfolio", "dev.to", "medium.com"],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("text", "")[:300],
                "published_date": r.get("publishedDate"),
            })
        return results

    except Exception as e:
        print(f"⚠️ Exa portfolio search failed: {e}")
        return []
