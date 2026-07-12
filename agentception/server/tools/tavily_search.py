"""
Tavily Search Tool - For initial company discovery
Uses Tavily API for cost-effective web search, replacing Exa for broad searches.
"""

from __future__ import annotations
import os
import httpx
import asyncio
import random
from typing import List, Optional, Dict, Any

# Base Tavily endpoint
BASE = "https://api.tavily.com"

# Optional escape hatch for corporate proxies / MITM scanners that break TLS
DISABLE_SSL_VERIFY = os.getenv("TAVILY_DISABLE_SSL_VERIFY", "false").lower() == "true"

# Global concurrency throttle
TAVILY_MAX_CONCURRENCY = int(os.getenv("TAVILY_MAX_CONCURRENCY", "2"))
_TAVILY_SEM = asyncio.Semaphore(max(1, TAVILY_MAX_CONCURRENCY))

# Retry mechanism
MAX_RETRIES = 3
BASE_DELAY = 1.0


def _get_tavily_key() -> Optional[str]:
    """Get Tavily API key from environment"""
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        print("⚠️ TAVILY_API_KEY not found in environment variables")
        return None
    key = key.strip().strip('"').strip("'")
    if not key or len(key) < 10:
        print("⚠️ TAVILY_API_KEY appears to be invalid (too short)")
        return None
    return key


async def _robust_tavily_post(
    client: httpx.AsyncClient, 
    url: str, 
    headers: Dict[str, str], 
    json_data: Dict[str, Any], 
    attempt: int = 0
) -> Dict[str, Any]:
    """Robust POST with retry logic for rate limits and connection errors"""
    try:
        r = await client.post(url, headers=headers, json=json_data, timeout=60.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429 and attempt < MAX_RETRIES:
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
            print(f"⚠️ Tavily API rate limit hit (429). Retrying in {delay:.2f}s... (Attempt {attempt + 1}/{MAX_RETRIES})")
            await asyncio.sleep(delay)
            return await _robust_tavily_post(client, url, headers, json_data, attempt + 1)
        # Better error messages for other HTTP errors
        error_detail = ""
        try:
            error_body = e.response.json()
            error_detail = f" - {error_body.get('error', {}).get('message', str(error_body))}"
        except:
            error_detail = f" - {e.response.text[:200]}"
        raise RuntimeError(f"Tavily API HTTP error {e.response.status_code}{error_detail}") from e
    except httpx.ConnectError as e:
        # Connection errors - retry with exponential backoff
        if attempt < MAX_RETRIES:
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
            print(f"⚠️ Tavily API connection error. Retrying in {delay:.2f}s... (Attempt {attempt + 1}/{MAX_RETRIES})")
            print(f"   Error: {str(e)[:200]}")
            await asyncio.sleep(delay)
            return await _robust_tavily_post(client, url, headers, json_data, attempt + 1)
        raise RuntimeError(f"Tavily API connection failed after {MAX_RETRIES} attempts: {str(e)}") from e
    except httpx.TimeoutException as e:
        if attempt < MAX_RETRIES:
            delay = BASE_DELAY * (2 ** attempt)
            print(f"⚠️ Tavily API timeout. Retrying in {delay:.2f}s... (Attempt {attempt + 1}/{MAX_RETRIES})")
            await asyncio.sleep(delay)
            return await _robust_tavily_post(client, url, headers, json_data, attempt + 1)
        raise RuntimeError(f"Tavily API request timed out after {MAX_RETRIES} attempts") from e
    except Exception as e:
        raise RuntimeError(f"Tavily API error: {str(e)}") from e


async def tavily_search(
    query: str,
    *,
    num_results: int = 10,
    search_depth: str = "basic",  # "basic" or "advanced"
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    include_answer: bool = False,
    include_raw_content: bool = False,
) -> List[Dict[str, Any]]:
    """
    Search using Tavily API.
    
    Args:
        query: Search query string
        num_results: Number of results to return (default: 10, max: 20)
        search_depth: "basic" (faster, cheaper) or "advanced" (deeper, more expensive)
        include_domains: List of domains to restrict search to
        exclude_domains: List of domains to exclude
        include_answer: Include AI-generated answer (uses more credits)
        include_raw_content: Include full raw content (uses more credits)
    
    Returns:
        List of search results with: title, url, content, score, published_date
    """
    tavily_key = _get_tavily_key()
    if not tavily_key:
        raise RuntimeError("TAVILY_API_KEY missing")
    
    body: Dict[str, Any] = {
        "api_key": tavily_key,
        "query": query,
        "search_depth": search_depth,
        "max_results": min(num_results, 20),  # Tavily max is 20
    }
    
    if include_domains:
        body["include_domains"] = include_domains
    if exclude_domains:
        body["exclude_domains"] = exclude_domains
    if include_answer:
        body["include_answer"] = True
    if include_raw_content:
        body["include_raw_content"] = True
    
    headers = {"Content-Type": "application/json"}
    
    async with _TAVILY_SEM:
        # Use longer timeout and better connection settings
        timeout = httpx.Timeout(60.0, connect=30.0)  # 60s total, 30s to connect
        
        # Simple, reliable settings - trust_env handles proxy automatically
        async with httpx.AsyncClient(
            timeout=timeout,
            trust_env=True,  # Automatically use HTTP_PROXY/HTTPS_PROXY from env
            verify=not DISABLE_SSL_VERIFY,
            transport=httpx.AsyncHTTPTransport(
                http2=False,
                retries=1  # Retry once on connection failures
            )
        ) as client:
            if DISABLE_SSL_VERIFY:
                print("⚠️ Tavily SSL verification disabled via TAVILY_DISABLE_SSL_VERIFY=true")
            try:
                data = await _robust_tavily_post(client, f"{BASE}/search", headers, body)
            except Exception as e:
                # Provide helpful error message
                error_msg = str(e)
                if "API key" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
                    print(f"❌ Tavily API authentication error. Check TAVILY_API_KEY is set correctly.")
                elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    print(f"❌ Tavily API connection error. Check network connectivity and firewall settings.")
                else:
                    print(f"❌ Tavily API error: {error_msg}")
                raise
    
    # Transform Tavily response to match Exa format for compatibility
    results = []
    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),  # Tavily's content field
            "score": item.get("score", 0.0),  # Relevance score
            "published_date": item.get("published_date", ""),
            # Additional Tavily fields
            "raw_content": item.get("raw_content", ""),
        })
    
    if not results:
        print(f"⚠️ Tavily API returned no results for query: '{query}'")
    
    return results


EXTRACT_MAX_URLS = 20


async def tavily_extract(
    urls: List[str],
    *,
    extract_depth: str = "basic",
) -> Dict[str, str]:
    """
    Extract clean page content via Tavily's Extract API.

    Tavily fetches, renders and cleans the page server-side, which succeeds on
    many JS-heavy ATS pages where plain HTTP + BeautifulSoup returns nothing.
    Up to 20 URLs per call.

    Returns: {url: raw_content} for pages that extracted successfully.
    """
    tavily_key = _get_tavily_key()
    if not tavily_key:
        raise RuntimeError("TAVILY_API_KEY missing")

    urls = [u for u in urls if u][:EXTRACT_MAX_URLS]
    if not urls:
        return {}

    body = {"api_key": tavily_key, "urls": urls, "extract_depth": extract_depth}
    headers = {"Content-Type": "application/json"}

    async with _TAVILY_SEM:
        timeout = httpx.Timeout(90.0, connect=30.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            trust_env=True,
            verify=not DISABLE_SSL_VERIFY,
            transport=httpx.AsyncHTTPTransport(http2=False, retries=1),
        ) as client:
            data = await _robust_tavily_post(client, f"{BASE}/extract", headers, body)

    extracted: Dict[str, str] = {}
    for item in data.get("results", []):
        url, content = item.get("url", ""), item.get("raw_content", "")
        if url and content:
            extracted[url] = content

    failed = data.get("failed_results", [])
    if failed:
        print(f"⚠️ Tavily Extract failed for {len(failed)}/{len(urls)} URLs")

    return extracted


async def tavily_search_batch(
    queries: List[str],
    *,
    num_results: int = 10,
    search_depth: str = "basic",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Execute multiple Tavily searches in parallel.
    
    Args:
        queries: List of search queries
        num_results: Results per query
        search_depth: "basic" or "advanced"
    
    Returns:
        Dictionary mapping query to results
    """
    tasks = [
        tavily_search(q, num_results=num_results, search_depth=search_depth)
        for q in queries
    ]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)
    
    results_dict = {}
    for query, result in zip(queries, results_list):
        if isinstance(result, Exception):
            print(f"⚠️ Tavily search failed for '{query}': {result}")
            results_dict[query] = []
        else:
            results_dict[query] = result
    
    return results_dict

