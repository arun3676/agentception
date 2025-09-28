from __future__ import annotations
import os, httpx, asyncio, random
from typing import List, Optional, Dict, Any

BASE = "https://api.exa.ai"

# --- Global concurrency throttle ---
EXA_MAX_CONCURRENCY = int(os.getenv("EXA_MAX_CONCURRENCY", "1"))
_EXA_SEM = asyncio.Semaphore(max(1, EXA_MAX_CONCURRENCY))

# --- Retry mechanism for Exa API calls ---
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds

async def _robust_exa_post(client: httpx.AsyncClient, url: str, headers: Dict[str, str], json_data: Dict[str, Any], attempt: int = 0) -> Dict[str, Any]:
    try:
        r = await client.post(url, headers=headers, json=json_data)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429 and attempt < MAX_RETRIES:
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5) # Exponential backoff with jitter
            print(f"⚠️ Exa API rate limit hit (429). Retrying in {delay:.2f}s... (Attempt {attempt + 1}/{MAX_RETRIES})")
            await asyncio.sleep(delay)
            return await _robust_exa_post(client, url, headers, json_data, attempt + 1)
        raise # Re-raise if not 429 or max retries reached


def _get_exa_key() -> Optional[str]:
    key = os.getenv("EXA_API_KEY")
    if not key:
        return None
    return key.strip().strip('"').strip("'")


async def exa_search(
    query: str,
    *,
    include_domains: Optional[List[str]] = None,
    num_results: int = 8,
    want_text: bool = False,
    want_highlights: bool = True,
) -> List[Dict[str, Any]]:
    """
    Calls POST /search.
    Key Exa knobs we use:
      - includeDomains: restrict to specific domains/paths (e.g. ['eventbrite.com/e','meetup.com/*'])
      - numResults   : HTTP expects camelCase (see OpenAPI)
      - text/highlights: return clean text or short snippets for ranking/RAG
    """
    exa_key = _get_exa_key()
    if not exa_key:
        raise RuntimeError("EXA_API_KEY missing")

    body: Dict[str, Any] = {
        "query": query,
        "type": "auto",
        "numResults": num_results,
    }
    if include_domains:
        body["includeDomains"] = include_domains
    # Exa puts these under either top-level flags or a contents block; keeping top-level for simplicity.
    if want_text:
        body["text"] = True
    if want_highlights:
        body["highlights"] = True

    headers = {"x-api-key": exa_key, "Content-Type": "application/json"}
    async with _EXA_SEM:
        async with httpx.AsyncClient(timeout=40, trust_env=False, transport=httpx.AsyncHTTPTransport(http2=False)) as client:
            data = await _robust_exa_post(client, f"{BASE}/search", headers, body)

    rows = []
    for it in data.get("results", []):
        rows.append({
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "date": it.get("publishedDate", ""),
            "highlights": it.get("highlights", []),
            "summary": it.get("summary", ""),
        })
    if not rows:
        print(f"⚠️ Exa API returned no results for query: '{query}'")
    return rows


async def exa_contents(urls: List[str], *, max_chars: int = 6000) -> List[Dict[str, Any]]:
    exa_key = _get_exa_key()
    if not exa_key:
        raise RuntimeError("EXA_API_KEY missing")
    body: Dict[str, Any] = {
        "urls": urls,
        "text": {"maxCharacters": max_chars, "includeHtmlTags": False}
    }
    headers = {"x-api-key": exa_key, "Content-Type": "application/json"}
    async with _EXA_SEM:
        async with httpx.AsyncClient(timeout=60, trust_env=False, transport=httpx.AsyncHTTPTransport(http2=False)) as client:
            data = await _robust_exa_post(client, f"{BASE}/contents", headers, body)
            return data.get("results", [])


