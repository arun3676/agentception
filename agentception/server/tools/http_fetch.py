from __future__ import annotations

import asyncio
import httpx
from typing import Optional

FETCH_TIMEOUT = 12.0
MAX_CONCURRENCY = 4
_FETCH_SEM = asyncio.Semaphore(MAX_CONCURRENCY)


async def fetch_url_content(url: str, *, max_chars: int = 4000) -> Optional[str]:
    """
    Lightweight HTTP GET helper to fetch raw text content from a URL.
    Replaces expensive exa_contents calls for second-hop extraction.
    """
    if not url:
        return None

    async with _FETCH_SEM:
        try:
            async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
                r = await client.get(url)
                if r.status_code >= 400:
                    return None
                text = r.text or ""
                if not text:
                    return None
                if max_chars and len(text) > max_chars:
                    return text[:max_chars]
                return text
        except Exception:
            return None

