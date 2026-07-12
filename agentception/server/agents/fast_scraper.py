"""
Fast HTTP-based job link extraction from listing pages.
Replaces slow Apify Playwright scraper with simple HTML parsing.

Performance: 5-15 seconds vs 90+ seconds with Apify Playwright.
"""
from __future__ import annotations
import asyncio
from typing import List, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# ATS URL patterns to extract (high-quality job posting sources)
ATS_PATTERNS = [
    'greenhouse.io', 'lever.co', 'ashbyhq.com', 'workday.com',
    'myworkdayjobs.com', 'smartrecruiters.com', 'icims.com',
    'jobvite.com', 'jobs.lever.co', 'boards.greenhouse.io',
    'bamboohr.com', 'jazz.co', 'recruitee.com', 'workable.com',
    'breezy.hr', 'rippling.com'
]

# Quality job board patterns
JOB_BOARD_PATTERNS = [
    'wellfound.com', 'ycombinator.com', 'workatastartup.com',
    'builtinsf.com', 'builtin.com', 'builtinnyc.com',
    'angel.co', 'levels.fyi', 'remotive.com'
]

# Domains that require JavaScript rendering (use Apify for these)
JS_HEAVY_DOMAINS: Set[str] = set()  # Add domains that truly need JS if discovered

# Debug flag
DEBUG_SCRAPER = True


def is_job_link(url: str) -> bool:
    """Check if URL looks like a job posting link."""
    if not url:
        return False
    
    url_lower = url.lower()
    
    # Skip obvious non-job URLs
    skip_patterns = [
        'javascript:', 'mailto:', 'tel:', '#', 
        '.pdf', '.png', '.jpg', '.gif', '.css', '.js',
        'login', 'signin', 'signup', 'register', 'account',
        'privacy', 'terms', 'cookie', 'about-us', 'contact-us',
        'blog/', '/blog', 'news/', '/news', 'press/',
        'facebook.com', 'twitter.com', 'linkedin.com/company',
        'instagram.com', 'youtube.com'
    ]
    if any(skip in url_lower for skip in skip_patterns):
        return False
    
    # Check for ATS domains (always accept)
    for ats in ATS_PATTERNS:
        if ats in url_lower:
            return True
    
    # Check for quality job boards
    for board in JOB_BOARD_PATTERNS:
        if board in url_lower:
            # Make sure it's a job page, not homepage
            if '/jobs' in url_lower or '/job/' in url_lower or '/companies/' in url_lower:
                return True
    
    # Check for job path patterns
    job_patterns = ['/jobs/', '/job/', '/careers/', '/positions/', '/opening/', '/apply/', '/vacancy/']
    if any(pattern in url_lower for pattern in job_patterns):
        # Exclude pagination and filter URLs
        exclude_patterns = [
            'page=', 'filter=', 'sort=', 'search=', 
            '/jobs?', '/careers?', '/jobs#', 
            'offset=', 'limit=', 'category='
        ]
        if not any(excl in url_lower for excl in exclude_patterns):
            return True
    
    return False


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    if not url:
        return ""
    
    # Remove trailing slashes and fragments
    url = url.split('#')[0].rstrip('/')
    
    # Remove common tracking parameters
    tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'fbclid', 'gclid']
    parsed = urlparse(url)
    if parsed.query:
        from urllib.parse import parse_qs, urlencode
        params = parse_qs(parsed.query)
        # Remove tracking params
        cleaned_params = {k: v for k, v in params.items() if k.lower() not in tracking_params}
        if cleaned_params:
            clean_query = urlencode(cleaned_params, doseq=True)
            url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{clean_query}"
        else:
            url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    return url


async def fast_extract_job_links(
    listing_url: str, 
    timeout: float = 15.0,
    max_links: int = 50
) -> List[str]:
    """
    Fast HTTP-based job link extraction from listing pages.
    No browser needed - just fetch HTML and parse links.
    
    Args:
        listing_url: URL of the listing page to scrape
        timeout: HTTP request timeout in seconds
        max_links: Maximum number of links to extract
    
    Returns:
        List of job posting URLs found on the page
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
        ) as client:
            if DEBUG_SCRAPER:
                print(f"    🚀 Fast scraping: {listing_url[:60]}...")
            
            resp = await client.get(listing_url)
            
            if resp.status_code != 200:
                if DEBUG_SCRAPER:
                    print(f"    ⚠️ HTTP {resp.status_code} for {listing_url[:50]}")
                return []
            
            # Parse HTML
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            job_links: List[str] = []
            seen_normalized: Set[str] = set()
            
            # Extract all links
            for a in soup.find_all('a', href=True):
                href = a['href']
                
                # Skip empty or anchor-only links
                if not href or href.startswith('#'):
                    continue
                
                # Convert relative URLs to absolute
                full_url = urljoin(listing_url, href)
                
                # Check if it's a job link
                if is_job_link(full_url):
                    # Normalize for deduplication
                    normalized = _normalize_url(full_url)
                    if normalized and normalized not in seen_normalized:
                        seen_normalized.add(normalized)
                        job_links.append(full_url)
                        
                        if len(job_links) >= max_links:
                            break
            
            if DEBUG_SCRAPER:
                print(f"    ✅ Extracted {len(job_links)} job links from {listing_url[:40]}...")
            
            return job_links
            
    except httpx.TimeoutException:
        if DEBUG_SCRAPER:
            print(f"    ⚠️ Timeout scraping {listing_url[:50]}")
        return []
    except httpx.ConnectError:
        if DEBUG_SCRAPER:
            print(f"    ⚠️ Connection error for {listing_url[:50]}")
        return []
    except Exception as e:
        if DEBUG_SCRAPER:
            print(f"    ❌ Error scraping {listing_url[:50]}: {e}")
        return []


async def expand_listing_pages(
    listing_urls: List[str], 
    max_concurrent: int = 5,
    max_links_per_page: int = 30
) -> List[str]:
    """
    Expand multiple listing pages concurrently.
    Returns all extracted job URLs, deduplicated.
    
    Args:
        listing_urls: List of listing page URLs to scrape
        max_concurrent: Maximum concurrent HTTP requests
        max_links_per_page: Maximum links to extract per page
    
    Returns:
        List of unique job posting URLs
    """
    if not listing_urls:
        return []
    
    if DEBUG_SCRAPER:
        print(f"🔍 Fast expanding {len(listing_urls)} listing pages...")
    
    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def scrape_with_limit(url: str) -> List[str]:
        async with semaphore:
            return await fast_extract_job_links(url, max_links=max_links_per_page)
    
    # Run all scraping tasks concurrently
    tasks = [scrape_with_limit(url) for url in listing_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Flatten and deduplicate
    all_links: List[str] = []
    seen_normalized: Set[str] = set()
    
    for result in results:
        if isinstance(result, list):
            for link in result:
                normalized = _normalize_url(link)
                if normalized and normalized not in seen_normalized:
                    seen_normalized.add(normalized)
                    all_links.append(link)
        elif isinstance(result, Exception):
            if DEBUG_SCRAPER:
                print(f"    ⚠️ Scraping error: {result}")
    
    if DEBUG_SCRAPER:
        print(f"✅ Fast expansion complete: {len(all_links)} unique job links")
    
    return all_links


async def smart_expand(
    listing_urls: List[str],
    apify_fallback: bool = False
) -> List[str]:
    """
    Smart expansion: Use fast HTTP scraping by default, Apify only for JS-heavy sites.
    
    Args:
        listing_urls: List of listing page URLs to expand
        apify_fallback: Whether to use Apify for JS-heavy sites (requires apify_jobs module)
    
    Returns:
        List of unique job posting URLs
    """
    if not listing_urls:
        return []
    
    fast_urls: List[str] = []
    js_urls: List[str] = []
    
    # Separate URLs by scraping method needed
    for url in listing_urls:
        try:
            domain = urlparse(url).netloc.lower()
            if any(js_domain in domain for js_domain in JS_HEAVY_DOMAINS):
                js_urls.append(url)
            else:
                fast_urls.append(url)
        except:
            fast_urls.append(url)  # Default to fast scraping
    
    results: List[str] = []
    
    # Fast scrape most URLs (this is the default path)
    if fast_urls:
        fast_results = await expand_listing_pages(fast_urls)
        results.extend(fast_results)
    
    # Apify only for JS-heavy sites (if enabled and any exist)
    if js_urls and apify_fallback:
        if DEBUG_SCRAPER:
            print(f"    🎭 Using Apify for {len(js_urls)} JS-heavy pages")
        try:
            from .apify_jobs import extract_job_urls_from_listing_pages
            apify_results = await extract_job_urls_from_listing_pages(js_urls, max_urls=30)
            results.extend(apify_results)
        except ImportError:
            if DEBUG_SCRAPER:
                print(f"    ⚠️ Apify module not available, skipping JS-heavy pages")
        except Exception as e:
            if DEBUG_SCRAPER:
                print(f"    ⚠️ Apify fallback failed: {e}")
    elif js_urls:
        # Try fast scraping anyway - might work for some "JS-heavy" sites
        if DEBUG_SCRAPER:
            print(f"    ℹ️ Attempting fast scrape on {len(js_urls)} potentially JS-heavy pages")
        js_results = await expand_listing_pages(js_urls)
        results.extend(js_results)
    
    # Final deduplication
    seen: Set[str] = set()
    unique_results: List[str] = []
    for url in results:
        normalized = _normalize_url(url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_results.append(url)
    
    return unique_results
