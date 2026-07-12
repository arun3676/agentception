"""
Apify integration layer for enhanced job URL extraction.

This module adds Apify actors on top of Tavily-based job search to:
1. Extract more job URLs from listing pages (BuiltIn, Wellfound, YC, aggregators)
2. Convert listing/aggregator results into direct ATS posting URLs

Strategy:
- FAST HTTP scraping by default (5-15 seconds)
- Apify Playwright only as fallback for JS-heavy sites (90+ seconds)

Actors used (fallback only):
- apify/playwright-scraper: Listing scraping + apply-link extraction
- bytepulselabs/greenhouse-job-scraper: Expand Greenhouse boards
- bytepulselabs/lever-job-scraper: Expand Lever boards
"""

from __future__ import annotations
import os
import re
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, urlunparse
from dataclasses import dataclass

# Import SearchHit from match module
from .match import SearchHit

# Import fast scraper (preferred method)
try:
    from .fast_scraper import (
        fast_extract_job_links,
        expand_listing_pages as fast_expand_listing_pages,
        smart_expand,
    )
    FAST_SCRAPER_AVAILABLE = True
except ImportError:
    FAST_SCRAPER_AVAILABLE = False
    print("⚠️ Fast scraper not available, will use Apify Playwright")

# Debug flag
DEBUG_APIFY = os.getenv("DEBUG_APIFY", "true").lower() == "true"

# Feature flag: Use fast HTTP scraping instead of Apify Playwright
USE_FAST_SCRAPER = os.getenv("USE_FAST_SCRAPER", "true").lower() == "true"

# Apify timeout settings
APIFY_TIMEOUT_SECONDS = 120  # Max wait time for actor runs
APIFY_POLL_INTERVAL = 3  # Seconds between status checks

# ATS detection patterns
ATS_PATTERNS = {
    "greenhouse": [
        r"boards\.greenhouse\.io/([^/]+)",
        r"greenhouse\.io/([^/]+)",
        r"([^/]+)\.greenhouse\.io",
    ],
    "lever": [
        r"jobs\.lever\.co/([^/]+)",
        r"lever\.co/([^/]+)",
    ],
}

# Job URL patterns for filtering
JOB_URL_PATTERNS = [
    r"/job[s]?/",
    r"/role[s]?/",
    r"/position[s]?/",
    r"/career[s]?/",
    r"/opening[s]?/",
    r"lever\.co/",
    r"greenhouse\.io/",
    r"ashbyhq\.com/",
    r"workday\.",
    r"myworkdayjobs\.com",
    r"smartrecruiters\.com",
    r"icims\.com",
    r"workable\.com",
]

# Sites that block scraping (403 errors) - skip these to save time
BLOCKED_SCRAPING_SITES = [
    'wellfound.com',
    'angel.co',
    'angellist.com',
]

# Tracking params to strip for URL canonicalization
TRACKING_PARAMS = [
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid",
]


def get_apify_client():
    """
    Get Apify client using APIFY_TOKEN from environment.
    Returns None if token is not available.
    """
    token = os.getenv("APIFY_TOKEN")
    if not token:
        if DEBUG_APIFY:
            print("⚠️ APIFY_TOKEN not found in environment")
        return None
    
    try:
        from apify_client import ApifyClient
        client = ApifyClient(token)
        if DEBUG_APIFY:
            print("✅ Apify client initialized")
        return client
    except ImportError:
        if DEBUG_APIFY:
            print("⚠️ apify-client package not installed. Run: pip install apify-client")
        return None
    except Exception as e:
        if DEBUG_APIFY:
            print(f"⚠️ Failed to initialize Apify client: {e}")
        return None


async def run_actor(actor_id: str, run_input: dict, timeout: int = APIFY_TIMEOUT_SECONDS) -> List[dict]:
    """
    Run an Apify actor and return dataset items.
    
    Args:
        actor_id: Full actor ID (e.g., "apify/playwright-scraper")
        run_input: Input configuration for the actor
        timeout: Maximum seconds to wait for completion
    
    Returns:
        List of dataset items from the actor run
    """
    client = get_apify_client()
    if not client:
        return []
    
    try:
        if DEBUG_APIFY:
            print(f"🚀 Starting Apify actor: {actor_id}")
        
        # Run the actor (this is synchronous in apify-client, wrap in executor)
        loop = asyncio.get_event_loop()
        
        def _run_actor_sync():
            # Start the actor run
            run = client.actor(actor_id).call(run_input=run_input, timeout_secs=timeout)
            
            if not run:
                return []
            
            # Get dataset items
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                return []
            
            items = list(client.dataset(dataset_id).iterate_items())
            return items
        
        # Run in thread pool to not block async loop
        items = await loop.run_in_executor(None, _run_actor_sync)
        
        if DEBUG_APIFY:
            print(f"✅ Actor {actor_id} returned {len(items)} items")
        
        return items
        
    except Exception as e:
        if DEBUG_APIFY:
            print(f"⚠️ Apify actor {actor_id} failed: {e}")
        return []


def canonicalize_url(url: str) -> str:
    """
    Canonicalize URL by stripping tracking parameters and normalizing.
    """
    if not url:
        return ""
    
    try:
        parsed = urlparse(url)
        
        # Parse query params and filter out tracking
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered_params = {
                k: v for k, v in params.items() 
                if k.lower() not in TRACKING_PARAMS
            }
            new_query = urlencode(filtered_params, doseq=True) if filtered_params else ""
        else:
            new_query = ""
        
        # Rebuild URL without fragment
        canonical = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.params,
            new_query,
            ""  # No fragment
        ))
        
        return canonical
    except Exception:
        return url


def detect_ats_board(url: str) -> Optional[Dict[str, str]]:
    """
    Detect if URL is from a known ATS board and extract board URL.
    
    Args:
        url: URL to check
    
    Returns:
        Dict with 'type' and 'board_url' if ATS detected, None otherwise
    """
    if not url:
        return None
    
    url_lower = url.lower()
    
    # Check Greenhouse patterns
    for pattern in ATS_PATTERNS["greenhouse"]:
        match = re.search(pattern, url_lower)
        if match:
            company = match.group(1)
            # Clean company name (remove path segments)
            company = company.split("/")[0].split("?")[0]
            if company and len(company) > 1:
                return {
                    "type": "greenhouse",
                    "board_url": f"https://boards.greenhouse.io/{company}"
                }
    
    # Check Lever patterns
    for pattern in ATS_PATTERNS["lever"]:
        match = re.search(pattern, url_lower)
        if match:
            company = match.group(1)
            company = company.split("/")[0].split("?")[0]
            if company and len(company) > 1:
                return {
                    "type": "lever",
                    "board_url": f"https://jobs.lever.co/{company}"
                }
    
    return None


def _is_likely_job_url(url: str) -> bool:
    """Check if URL looks like a job posting URL."""
    if not url:
        return False
    
    url_lower = url.lower()
    
    # Check against job URL patterns
    for pattern in JOB_URL_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    
    return False


def _filter_job_urls(urls: List[str], max_urls: int = 50) -> List[str]:
    """Filter and dedupe job URLs."""
    seen = set()
    filtered = []
    
    for url in urls:
        canonical = canonicalize_url(url)
        if canonical and canonical not in seen:
            if _is_likely_job_url(canonical):
                seen.add(canonical)
                filtered.append(url)  # Return original URL
                if len(filtered) >= max_urls:
                    break
    
    return filtered


async def extract_job_urls_from_listing_pages(
    listing_urls: List[str], 
    max_urls: int = 50
) -> List[str]:
    """
    Extract job URLs from listing pages.
    
    Strategy:
    1. Try fast HTTP scraping first (5-15 seconds)
    2. Fall back to Apify Playwright only if fast scraping fails or is disabled
    
    Args:
        listing_urls: List of listing page URLs to scrape
        max_urls: Maximum number of job URLs to return
    
    Returns:
        List of extracted job URLs (deduped)
    """
    if not listing_urls:
        return []
    
    # Filter out blocked sites that return 403 errors
    filtered_urls = []
    for url in listing_urls:
        url_lower = url.lower()
        if any(blocked in url_lower for blocked in BLOCKED_SCRAPING_SITES):
            if DEBUG_APIFY:
                print(f"    ⏭️ Skipping blocked site (403 expected): {url[:50]}...")
            continue
        filtered_urls.append(url)
    
    if not filtered_urls:
        if DEBUG_APIFY:
            print("⚠️ All listing URLs are from blocked sites, skipping extraction")
        return []
    
    listing_urls = filtered_urls
    
    # === FAST SCRAPING (preferred) ===
    if USE_FAST_SCRAPER and FAST_SCRAPER_AVAILABLE:
        if DEBUG_APIFY:
            print(f"🚀 Using fast HTTP scraping for {len(listing_urls)} listing pages")
        try:
            fast_results = await fast_expand_listing_pages(
                listing_urls[:10],  # Limit to 10 pages
                max_concurrent=5,
                max_links_per_page=max_urls // len(listing_urls[:10]) + 5
            )
            if fast_results:
                filtered = _filter_job_urls(fast_results, max_urls)
                if DEBUG_APIFY:
                    print(f"✅ Fast scraping extracted {len(filtered)} job URLs")
                return filtered
            else:
                if DEBUG_APIFY:
                    print("⚠️ Fast scraping returned no results, trying Apify fallback")
        except Exception as e:
            if DEBUG_APIFY:
                print(f"⚠️ Fast scraping failed: {e}, trying Apify fallback")
    
    # === APIFY FALLBACK ===
    client = get_apify_client()
    if not client:
        if DEBUG_APIFY:
            print("⚠️ Apify client not available, skipping listing extraction")
        return []
    
    # Prepare startUrls for playwright-scraper
    start_urls = [{"url": url} for url in listing_urls[:10]]  # Limit to 10 pages
    
    # Page function to extract job links
    # This runs in the browser context
    page_function = """
    async function pageFunction(context) {
        const { page, request } = context;
        
        // Wait for page to load
        await page.waitForLoadState('domcontentloaded');
        
        // Extract all links
        const links = await page.$$eval('a[href]', (anchors) => {
            const jobPatterns = [
                /\\/job[s]?\\//i,
                /\\/role[s]?\\//i,
                /\\/position[s]?\\//i,
                /\\/career[s]?\\//i,
                /\\/opening[s]?\\//i,
                /lever\\.co\\//i,
                /greenhouse\\.io\\//i,
                /ashbyhq\\.com\\//i,
                /workday\\./i,
                /myworkdayjobs\\.com/i,
                /smartrecruiters\\.com/i,
                /icims\\.com/i,
                /workable\\.com/i,
            ];
            
            return anchors
                .map(a => a.href)
                .filter(href => {
                    if (!href || href.startsWith('javascript:') || href.startsWith('#')) {
                        return false;
                    }
                    return jobPatterns.some(pattern => pattern.test(href));
                });
        });
        
        return {
            url: request.url,
            jobUrls: [...new Set(links)]  // Dedupe
        };
    }
    """
    
    run_input = {
        "startUrls": start_urls,
        "pageFunction": page_function,
        "proxyConfiguration": {"useApifyProxy": True},
        "maxRequestsPerCrawl": len(start_urls) * 2,
        "maxConcurrency": 5,
        "navigationTimeoutSecs": 30,
        "maxRequestRetries": 2,
    }
    
    try:
        items = await run_actor("apify/playwright-scraper", run_input, timeout=90)
        
        # Collect all job URLs from results
        all_job_urls = []
        for item in items:
            job_urls = item.get("jobUrls", [])
            all_job_urls.extend(job_urls)
        
        # Filter and dedupe
        filtered = _filter_job_urls(all_job_urls, max_urls)
        
        if DEBUG_APIFY:
            print(f"✅ Extracted {len(filtered)} job URLs from {len(listing_urls)} listing pages")
        
        return filtered
        
    except Exception as e:
        if DEBUG_APIFY:
            print(f"⚠️ Failed to extract job URLs from listings: {e}")
        return []


async def expand_jobs_from_ats_boards(
    urls: List[str],
    role_keywords: List[str],
    location_keywords: List[str],
    limit: int = 30
) -> List[dict]:
    """
    Expand job listings from detected ATS boards (Greenhouse, Lever).
    
    Args:
        urls: List of URLs that may contain ATS board references
        role_keywords: Keywords to filter job titles (e.g., ["AI", "Engineer", "ML"])
        location_keywords: Keywords to filter locations (e.g., ["San Francisco", "CA", "Remote"])
        limit: Maximum number of jobs to return
    
    Returns:
        List of normalized job objects: {title, company, location, url}
    """
    if not urls:
        return []
    
    client = get_apify_client()
    if not client:
        return []
    
    # Detect unique ATS boards from URLs
    boards = {}  # board_url -> type
    for url in urls:
        ats_info = detect_ats_board(url)
        if ats_info:
            board_url = ats_info["board_url"]
            if board_url not in boards:
                boards[board_url] = ats_info["type"]
    
    if not boards:
        if DEBUG_APIFY:
            print("⚠️ No ATS boards detected in URLs")
        return []
    
    if DEBUG_APIFY:
        print(f"🔍 Detected {len(boards)} ATS boards: {list(boards.keys())[:5]}")
    
    # Separate by ATS type
    greenhouse_boards = [url for url, t in boards.items() if t == "greenhouse"]
    lever_boards = [url for url, t in boards.items() if t == "lever"]
    
    all_jobs = []
    
    # Run Greenhouse scraper
    if greenhouse_boards:
        try:
            gh_input = {
                "urls": [{"url": url} for url in greenhouse_boards[:5]]  # Limit boards
            }
            gh_items = await run_actor("bytepulselabs/greenhouse-job-scraper", gh_input, timeout=90)
            
            for item in gh_items:
                job = {
                    "title": item.get("title") or item.get("jobTitle") or "",
                    "company": item.get("company") or item.get("companyName") or "",
                    "location": item.get("location") or "",
                    "url": item.get("url") or item.get("applyUrl") or "",
                    "source": "apify",
                    "ats": "greenhouse",
                }
                if job["url"]:
                    all_jobs.append(job)
            
            if DEBUG_APIFY:
                print(f"✅ Greenhouse scraper returned {len(gh_items)} jobs")
                
        except Exception as e:
            if DEBUG_APIFY:
                print(f"⚠️ Greenhouse scraper failed: {e}")
    
    # Run Lever scraper
    if lever_boards:
        try:
            lever_input = {
                "urls": [{"url": url} for url in lever_boards[:5]]
            }
            lever_items = await run_actor("bytepulselabs/lever-job-scraper", lever_input, timeout=90)
            
            for item in lever_items:
                job = {
                    "title": item.get("title") or item.get("jobTitle") or "",
                    "company": item.get("company") or item.get("companyName") or "",
                    "location": item.get("location") or "",
                    "url": item.get("url") or item.get("applyUrl") or "",
                    "source": "apify",
                    "ats": "lever",
                }
                if job["url"]:
                    all_jobs.append(job)
            
            if DEBUG_APIFY:
                print(f"✅ Lever scraper returned {len(lever_items)} jobs")
                
        except Exception as e:
            if DEBUG_APIFY:
                print(f"⚠️ Lever scraper failed: {e}")
    
    # Filter jobs by role and location keywords
    filtered_jobs = []
    role_keywords_lower = [kw.lower() for kw in role_keywords if kw]
    location_keywords_lower = [kw.lower() for kw in location_keywords if kw]
    
    for job in all_jobs:
        title_lower = (job.get("title") or "").lower()
        location_lower = (job.get("location") or "").lower()
        
        # Check role match (title contains any role keyword)
        role_match = not role_keywords_lower or any(
            kw in title_lower for kw in role_keywords_lower
        )
        
        # Check location match (location contains any location keyword OR is remote)
        location_match = not location_keywords_lower or any(
            kw in location_lower for kw in location_keywords_lower
        ) or "remote" in location_lower
        
        if role_match and location_match:
            filtered_jobs.append(job)
            if len(filtered_jobs) >= limit:
                break
    
    if DEBUG_APIFY:
        print(f"✅ Filtered to {len(filtered_jobs)} jobs matching role/location criteria")
    
    return filtered_jobs[:limit]


def _extract_role_keywords(role: str) -> List[str]:
    """Extract keywords from role string."""
    if not role:
        return []
    
    # Split on common separators and filter short words
    words = re.split(r'[\s\-/,]+', role)
    keywords = [w for w in words if len(w) >= 2]
    
    # Add the full role as a keyword too
    keywords.insert(0, role)
    
    return keywords


def _extract_location_keywords(location: str) -> List[str]:
    """Extract keywords from location string."""
    if not location:
        return []
    
    keywords = []
    
    # Add full location
    keywords.append(location)
    
    # Split on comma for city/state
    parts = [p.strip() for p in location.split(",")]
    keywords.extend(parts)
    
    # Common location aliases
    location_lower = location.lower()
    if "san francisco" in location_lower or "sf" in location_lower:
        keywords.extend(["San Francisco", "SF", "Bay Area", "CA"])
    if "new york" in location_lower or "nyc" in location_lower:
        keywords.extend(["New York", "NYC", "NY"])
    if "los angeles" in location_lower or "la" in location_lower:
        keywords.extend(["Los Angeles", "LA", "CA"])
    if "remote" in location_lower:
        keywords.append("Remote")
    
    return list(set(keywords))


def _convert_urls_to_job_dicts(urls: List[str], role: str, source_url: str) -> List[dict]:
    """Convert extracted URLs to job dict format."""
    jobs = []
    for url in urls:
        # Try to extract title from URL
        title = role
        
        # Extract company from URL if possible
        ats_info = detect_ats_board(url)
        if ats_info:
            # Extract from ATS URL pattern
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) >= 2:
                # Usually: /company/job-title-slug
                title_slug = path_parts[-1]
                title = title_slug.replace("-", " ").title()
        
        jobs.append({
            "url": url,
            "title": title,
            "snippet": f"Job posting extracted from {source_url[:40]}...",
            "source": "fast_scraper",
        })
    
    return jobs


def _is_listing_page_url(url: str) -> bool:
    """Check if URL looks like a job listing/aggregator page."""
    if not url:
        return False
    
    url_lower = url.lower()
    
    listing_patterns = [
        r"builtin\w*\.com",
        r"wellfound\.com",
        r"ycombinator\.com/companies",
        r"workatastartup\.com",
        r"/jobs\?",
        r"/jobs/search",
        r"/search\?",
        r"-jobs-in-",
    ]
    
    return any(re.search(p, url_lower) for p in listing_patterns)


async def apify_expand_search_hits(
    initial_hits: List[SearchHit],
    role: str,
    location: str,
    max_listing_urls: int = 5,
    max_expanded_jobs: int = 30
) -> List[SearchHit]:
    """
    Expand Tavily search hits using Apify for deeper job extraction.
    
    This function:
    1. Takes top N listing URLs from Tavily hits
    2. Runs extract_job_urls_from_listing_pages on them
    3. Runs expand_jobs_from_ats_boards on extracted URLs
    4. Converts everything to SearchHit format
    5. Returns merged, deduped hits
    
    Args:
        initial_hits: Original SearchHit list from Tavily
        role: Target role (e.g., "AI Engineer")
        location: Target location (e.g., "San Francisco, CA")
        max_listing_urls: Max listing pages to scrape
        max_expanded_jobs: Max jobs to return from ATS expansion
    
    Returns:
        Merged list of SearchHits (original + expanded), deduped by canonical URL
    """
    # Check if Apify is available
    client = get_apify_client()
    if not client:
        if DEBUG_APIFY:
            print("⚠️ Apify not available, returning original hits")
        return initial_hits
    
    if DEBUG_APIFY:
        print(f"🔄 Apify expanding {len(initial_hits)} initial hits for '{role}' in '{location}'")
    
    # Extract role and location keywords for filtering
    role_keywords = _extract_role_keywords(role)
    location_keywords = _extract_location_keywords(location)
    
    # Collect listing page URLs and ATS URLs from initial hits
    listing_urls = []
    ats_urls = []
    
    for hit in initial_hits:
        url = hit.url
        if not url:
            continue
        
        # Check if it's an ATS URL
        if detect_ats_board(url):
            ats_urls.append(url)
        # Check if it's a listing page
        elif _is_listing_page_url(url):
            listing_urls.append(url)
    
    if DEBUG_APIFY:
        print(f"📋 Found {len(listing_urls)} listing pages, {len(ats_urls)} ATS URLs")
    
    # Run both extraction tasks in parallel
    tasks = []
    
    # Helper for empty async result (Python 3.11+ compatible)
    async def _empty_list():
        return []
    
    # Task 1: Extract job URLs from listing pages
    if listing_urls:
        tasks.append(extract_job_urls_from_listing_pages(
            listing_urls[:max_listing_urls],
            max_urls=max_expanded_jobs
        ))
    else:
        tasks.append(_empty_list())
    
    # Task 2: Expand ATS boards
    all_urls_for_ats = ats_urls + listing_urls[:max_listing_urls]
    if all_urls_for_ats:
        tasks.append(expand_jobs_from_ats_boards(
            all_urls_for_ats,
            role_keywords=role_keywords,
            location_keywords=location_keywords,
            limit=max_expanded_jobs
        ))
    else:
        tasks.append(_empty_list())
    
    try:
        # Run tasks with timeout
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=APIFY_TIMEOUT_SECONDS
        )
        
        extracted_urls = results[0] if not isinstance(results[0], Exception) else []
        ats_jobs = results[1] if not isinstance(results[1], Exception) else []
        
        if isinstance(results[0], Exception) and DEBUG_APIFY:
            print(f"⚠️ Listing extraction failed: {results[0]}")
        if isinstance(results[1], Exception) and DEBUG_APIFY:
            print(f"⚠️ ATS expansion failed: {results[1]}")
            
    except asyncio.TimeoutError:
        if DEBUG_APIFY:
            print(f"⚠️ Apify expansion timed out after {APIFY_TIMEOUT_SECONDS}s")
        extracted_urls = []
        ats_jobs = []
    except Exception as e:
        if DEBUG_APIFY:
            print(f"⚠️ Apify expansion error: {e}")
        extracted_urls = []
        ats_jobs = []
    
    # Build result set with deduplication
    seen_urls = set()
    merged_hits = []
    
    # Add original hits first (preserve order)
    for hit in initial_hits:
        canonical = canonicalize_url(hit.url)
        if canonical and canonical not in seen_urls:
            seen_urls.add(canonical)
            merged_hits.append(hit)
    
    # Add hits from extracted URLs
    for url in extracted_urls:
        canonical = canonicalize_url(url)
        if canonical and canonical not in seen_urls:
            seen_urls.add(canonical)
            # Create SearchHit from URL
            merged_hits.append(SearchHit(
                url=url,
                title=f"{role} - Job Posting",  # Generic title
                snippet="Job posting extracted via Apify",
                score=70.0  # Moderate score for extracted URLs
            ))
    
    # Add hits from ATS jobs
    for job in ats_jobs:
        url = job.get("url", "")
        canonical = canonicalize_url(url)
        if canonical and canonical not in seen_urls:
            seen_urls.add(canonical)
            
            # Build title from job data
            title = job.get("title", role)
            company = job.get("company", "")
            if company and company not in title:
                title = f"{title} at {company}"
            
            # Build snippet
            location_str = job.get("location", "")
            ats_type = job.get("ats", "")
            snippet_parts = []
            if location_str:
                snippet_parts.append(f"Location: {location_str}")
            if ats_type:
                snippet_parts.append(f"Source: {ats_type.title()}")
            snippet = " | ".join(snippet_parts) if snippet_parts else "Job posting from ATS"
            
            merged_hits.append(SearchHit(
                url=url,
                title=title,
                snippet=snippet,
                score=75.0  # Slightly higher score for ATS jobs
            ))
    
    if DEBUG_APIFY:
        new_hits = len(merged_hits) - len(initial_hits)
        print(f"✅ Apify expansion complete: {len(initial_hits)} → {len(merged_hits)} hits (+{new_hits} new)")
    
    return merged_hits


async def apify_second_hop_extraction(
    listing_url: str,
    role: str,
    max_jobs: int = 10
) -> List[dict]:
    """
    Perform second-hop extraction on a listing page.
    
    This is called when the LLM normalizer classifies a page as job_list_page
    but the snippet contains job title information.
    
    Strategy:
    1. Try fast HTTP scraping first (preferred)
    2. Fall back to Apify if fast scraping fails
    
    Args:
        listing_url: URL of the listing page
        role: Target role for filtering
        max_jobs: Maximum jobs to extract
    
    Returns:
        List of job dicts: {url, title, snippet}
    """
    if DEBUG_APIFY:
        print(f"🔄 Second-hop extraction on: {listing_url[:60]}...")
    
    # === FAST SCRAPING (preferred) ===
    if USE_FAST_SCRAPER and FAST_SCRAPER_AVAILABLE:
        try:
            extracted_urls = await fast_extract_job_links(
                listing_url,
                timeout=15.0,
                max_links=max_jobs * 2
            )
            if extracted_urls:
                if DEBUG_APIFY:
                    print(f"✅ Fast second-hop extracted {len(extracted_urls)} URLs")
                # Convert to job dicts
                return _convert_urls_to_job_dicts(extracted_urls[:max_jobs], role, listing_url)
        except Exception as e:
            if DEBUG_APIFY:
                print(f"⚠️ Fast second-hop failed: {e}, trying Apify")
    
    # === APIFY FALLBACK ===
    client = get_apify_client()
    if not client:
        return []
    
    if DEBUG_APIFY:
        print(f"🎭 Apify second-hop fallback on: {listing_url[:60]}...")
    
    try:
        # Extract job URLs from the listing page
        extracted_urls = await extract_job_urls_from_listing_pages(
            [listing_url],
            max_urls=max_jobs * 2  # Get extra for filtering
        )
        
        if not extracted_urls:
            return []
        
        # Convert to job dicts
        role_keywords = _extract_role_keywords(role)
        jobs = []
        
        for url in extracted_urls[:max_jobs]:
            # Try to extract title from URL
            title = role
            url_lower = url.lower()
            
            # Extract company from URL if possible
            ats_info = detect_ats_board(url)
            if ats_info:
                # Extract from ATS URL pattern
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.split("/") if p]
                if len(path_parts) >= 2:
                    # Usually: /company/job-title-slug
                    title_slug = path_parts[-1]
                    title = title_slug.replace("-", " ").title()
            
            jobs.append({
                "url": url,
                "title": title,
                "snippet": f"Job posting extracted from {listing_url[:40]}...",
                "source": "apify",
            })
        
        if DEBUG_APIFY:
            print(f"✅ Second-hop extracted {len(jobs)} jobs")
        
        return jobs
        
    except Exception as e:
        if DEBUG_APIFY:
            print(f"⚠️ Second-hop extraction failed: {e}")
        return []
