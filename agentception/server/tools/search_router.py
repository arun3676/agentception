from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .exa_search import exa_search
from .tavily_search import tavily_search


class SearchProvider(str, Enum):
    AUTO = "auto"
    TAVILY = "tavily"
    EXA = "exa"


def _include_domains_need_exa(include_domains: Optional[List[str]]) -> bool:
    if not include_domains:
        return False
    for domain in include_domains:
        if not domain:
            continue
        # Exa supports path-level filters like domain/path, Tavily struggles there.
        if "/" in domain.strip("/"):
            return True
    return False


def _env_force_exa() -> bool:
    return os.getenv("FORCE_EXA_ONLY", "false").lower() == "true"


async def smart_search(
    query: str,
    *,
    num_results: int = 8,
    include_domains: Optional[List[str]] = None,
    provider_hint: SearchProvider | str = SearchProvider.AUTO,
    want_text: bool = False,
    want_highlights: bool = True,
    search_depth: str = "basic",
    include_raw_content: bool = False,
) -> Tuple[SearchProvider, List[Dict[str, Any]]]:
    """
    Route a web search to Tavily (cheap) or Exa (precise) based on context.
    Returns the provider used along with rows shaped like exa_search output.
    """
    hint = SearchProvider(provider_hint) if not isinstance(provider_hint, SearchProvider) else provider_hint
    provider = hint

    if hint == SearchProvider.AUTO:
        provider = SearchProvider.TAVILY
        if _include_domains_need_exa(include_domains):
            provider = SearchProvider.EXA
        elif search_depth == "advanced":
            provider = SearchProvider.EXA
        elif _env_force_exa():
            provider = SearchProvider.EXA

    rows: List[Dict[str, Any]] = []
    if provider == SearchProvider.EXA:
        rows = await exa_search(
            query,
            include_domains=include_domains,
            num_results=num_results,
            want_text=want_text,
            want_highlights=want_highlights,
        )
        for row in rows:
            row["provider"] = "exa"
    else:
        tavily_results = await tavily_search(
            query,
            num_results=num_results,
            search_depth=search_depth,
            include_domains=include_domains,
            include_raw_content=include_raw_content or want_text,
        )

        tavily_rows: List[Dict[str, Any]] = []
        for item in tavily_results:
            tavily_rows.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "summary": item.get("content", ""),
                "highlights": [item.get("raw_content", "") or item.get("content", "")],
                "provider": "tavily",
                "score": item.get("score"),
            })

        # Quality check: fallback to Exa when Tavily is sparse or low-signal
        avg_score = 0.0
        valid_scores = [r["score"] for r in tavily_rows if isinstance(r.get("score"), (int, float))]
        if valid_scores:
            avg_score = sum(valid_scores) / len(valid_scores)
        fallback_needed = len(tavily_rows) < max(3, num_results // 3) or avg_score < 0.2

        if fallback_needed:
            exa_rows = await exa_search(
                query,
                include_domains=include_domains,
                num_results=num_results,
                want_text=want_text,
                want_highlights=want_highlights,
            )
            for row in exa_rows:
                row["provider"] = "exa"
            if exa_rows:
                provider = SearchProvider.EXA
                rows = exa_rows
            else:
                rows = tavily_rows
        else:
            rows = tavily_rows

    return provider, rows

