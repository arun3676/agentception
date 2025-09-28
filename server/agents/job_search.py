from __future__ import annotations
import re
from typing import List, Optional
from urllib.parse import urlparse
import asyncio # Import asyncio for gather

from ..schemas import CompanyIntel, JobPosting
from ..tools.exa_search import exa_search
from ..rag.roles import role_profile

# Debug flag for discovery process
DEBUG_DISCOVERY = True


ATS_DOMAINS = [
    "lever.co", "greenhouse.io", "boards.greenhouse.io", "ashbyhq.com",
    "jobs.ashbyhq.com", "workable.com", "smartrecruiters.com", "bamboohr.com",
    "myworkdayjobs.com", #"recruiting.paylocity.com", "recruiting.ultipro.com", # Less common, remove for now
]

BLOCKED_DOMAINS = ["ycombinator.com", "www.ycombinator.com"]


def _domain_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        return parsed.netloc or None
    except ValueError:
        # Handle cases where the URL is malformed and cannot be parsed
        if DEBUG_DISCOVERY: print(f"⚠️ Could not parse invalid URL: {url}")
        return None


def _role_synonyms(role: str, role_keywords: List[str]) -> List[str]:
    base = [role]
    r = role.lower()
    
    # Common role variations
    common_variations = [
        "engineer", "developer", "programmer", "architect",
        "specialist", "professional", "expert", "lead"
    ]
    
    # AI/ML specific variations
    if "ai engineer" in r:
        base += [
            # Direct matches
            "ai engineer", "artificial intelligence engineer",
            # ML variations
            "machine learning engineer", "ml engineer", "mlops engineer",
            "ai/ml engineer", "ml/ai engineer", "ai & ml engineer",
            # Specialized roles
            "applied scientist", "research engineer", "ai software engineer",
            "deep learning engineer", "computer vision engineer", "nlp engineer",
            # Senior/Lead variations
            "senior ai engineer", "senior machine learning engineer",
            "lead ai engineer", "lead ml engineer",
            # Other common variations
            "ai developer", "ml developer", "ai specialist",
            "machine learning developer", "ai application engineer"
        ]
        # Add keywords with common role variations
        for kw in role_keywords:
            if len(kw) >= 2:  # More permissive length check
                for var in common_variations:
                    base.append(f"{kw} {var}")
                    base.append(f"{var} {kw}")
    elif "data engineer" in r:
        base += ["data engineer", "analytics engineer", "etl engineer", "data warehouse engineer"]
    elif "full" in r and "stack" in r:
        base += ["full stack engineer", "full-stack engineer", "software engineer", "web developer"]
    elif "java" in r:
        base += ["java engineer", "backend engineer", "software engineer", "spring developer"]
    elif "data analyst" in r:
        base += ["data analyst", "analytics", "bi analyst", "business intelligence analyst"]
    
    # include keywords as loose synonyms
    for kw in role_keywords:
        if len(kw) >= 2:  # More permissive length check
            base.append(kw)
    
    # de-dup and clean
    out = []
    seen = set()
    for t in base:
        t = t.strip().lower()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    
    return out


def _extract_job_posting(rows: List[dict], terms: List[str], default_title: str) -> Optional[JobPosting]:
    for row in rows:
        text_chunks = [row.get("summary", "")] + row.get("highlights", [])
        joined = " ".join([chunk for chunk in text_chunks if chunk])
        low = joined.lower()
        title_low = row.get("title", "").lower()
        
        # Skip articles and non-job content - be less strict
        skip_words = [
            "towards data science", "article", "blog", "tutorial", "guide", "towardsdatascience",
            "raises", "seed round", "funding"
        ]
        if any(skip_word in title_low for skip_word in skip_words):
            if DEBUG_DISCOVERY: print(f"    🚫 Skipping article: {title_low[:50]}...")
            continue
        
        # Job-related keywords
        job_keywords = ["job", "role", "position", "apply", "careers", "hiring", "opportunity", "opening", "vacancy", "engineer", "developer", "scientist"]
        joby = any(w in low for w in job_keywords)
        
        # Check title first (higher confidence)
        title_match = any(term in title_low for term in terms)
        
        # Then check content
        content_match = any(term in low for term in terms)
        
        # More flexible matching logic
        if title_match or content_match or joby:
            title = row.get("title") or default_title
            snippet = joined[:500] or row.get("summary", "")[:500]
            if DEBUG_DISCOVERY: print(f"    ✅ Found matching job: {title}")
            return JobPosting(url=row.get("url", ""), title=title, snippet=snippet)
        elif DEBUG_DISCOVERY and (title_low or low):
            print(f"    ❌ No match in: {title_low[:100]} | {low[:100]}")
    return None


async def check_job_availability(company: CompanyIntel, role: str) -> Optional[JobPosting]:
    """Determine whether the company lists an opening for the given role, preferring real career sites."""
    prof = role_profile(role)
    role_keywords = prof.get("keywords", []) or []
    synonyms = _role_synonyms(role, role_keywords)

    domain = _domain_from_url(company.homepage or "")
    if DEBUG_DISCOVERY: print(f"\n--- Starting Job Check for: {company.name} (Homepage: {company.homepage}) ---")


    # Phase 1: Consolidated ATS domain search using company name and role synonyms
    # Combine all ATS site: queries into one to reduce API calls
    ats_site_queries = [f"site:{d}" for d in ATS_DOMAINS]
    # Construct a query that targets company name and role synonyms across all ATS sites
    combined_ats_query_parts = [f'"{company.name}"' if company.name else ''] + [f'"{s}"' for s in synonyms[:3]]
    combined_ats_query = " ".join(filter(None, combined_ats_query_parts + [f"({' OR '.join(ats_site_queries)}) job"])) # add 'job' to narrow down

    if combined_ats_query.strip():
        if DEBUG_DISCOVERY: print(f"  [Phase 1] ATS Query: {combined_ats_query}")
        try:
            rows = await exa_search(combined_ats_query, num_results=10, want_text=False, want_highlights=True) # Increased results for combined query
            if DEBUG_DISCOVERY: print(f"    - Found {len(rows)} results. Top hit: {rows[0]['title'] if rows else 'None'}")
            posting = _extract_job_posting(rows, synonyms, default_title=f"{role} role")
            if posting:
                if DEBUG_DISCOVERY: print(f"    ✅ SUCCESS: Found job posting '{posting.title}'")
                return posting
            elif DEBUG_DISCOVERY: print("    - No relevant posting found in results.")
        except Exception as e:
            print(f"⚠️ Consolidated ATS job search failed for {company.name}: {e}")


    # Phase 2: Site-scoped queries on the company's own domain (if not YC)
    if domain and domain not in BLOCKED_DOMAINS:
        # Combine multiple site-specific role queries into one
        site_query_parts = [f'site:{domain}'] + [f'"{s}"' for s in synonyms[:3]]
        combined_site_query = " ".join(filter(None, site_query_parts + [" (careers OR jobs OR hiring)"]))

        if combined_site_query.strip():
            if DEBUG_DISCOVERY: print(f"  [Phase 2] Site Query: {combined_site_query}")
            try:
                rows = await exa_search(combined_site_query, num_results=5, want_text=False, want_highlights=True)
                if DEBUG_DISCOVERY: print(f"    - Found {len(rows)} results. Top hit: {rows[0]['title'] if rows else 'None'}")
                posting = _extract_job_posting(rows, synonyms, default_title=f"{role} role")
                if posting:
                    if DEBUG_DISCOVERY: print(f"    ✅ SUCCESS: Found job posting '{posting.title}'")
                    return posting
                elif DEBUG_DISCOVERY: print("    - No relevant posting found in results.")
            except Exception as e:
                print(f"⚠️ Site job search failed for {company.name}: {e}")

    # Phase 3: Fallback broad web query by company name and role (no site restriction)
    fallback_query_parts = [f'"{company.name}"' if company.name else ''] + [f'"{s}"' for s in synonyms[:3]]
    combined_fallback_query = " ".join(filter(None, fallback_query_parts + [" (job OR position OR careers OR hiring)"]))

    if combined_fallback_query.strip():
        if DEBUG_DISCOVERY: print(f"  [Phase 3] Fallback Query: {combined_fallback_query}")
        try:
            rows = await exa_search(combined_fallback_query, num_results=5, want_text=False, want_highlights=True)
            if DEBUG_DISCOVERY: print(f"    - Found {len(rows)} results. Top hit: {rows[0]['title'] if rows else 'None'}")
            posting = _extract_job_posting(rows, synonyms, default_title=f"{role} role")
            if posting:
                if DEBUG_DISCOVERY: print(f"    ✅ SUCCESS: Found job posting '{posting.title}'")
                return posting
            elif DEBUG_DISCOVERY: print("    - No relevant posting found in results.")
        except Exception as e:
            print(f"⚠️ Fallback job search failed for {company.name}: {e}")

    # Phase 4: Job-board fallbacks (last resort)
    boards = [
        f'site:linkedin.com/jobs "{company.name}" ("{synonyms[0]}" OR "machine learning" OR "ai")',
        f'site:ycombinator.com/companies "{company.name}" (jobs OR hiring)',
        f'site:indeed.com "{company.name}" (engineer OR developer OR scientist)'
    ]
    for bq in boards:
        if DEBUG_DISCOVERY: print(f"  [Phase 4] Board Query: {bq}")
        try:
            rows = await exa_search(bq, num_results=5, want_text=False, want_highlights=True)
            posting = _extract_job_posting(rows, synonyms, default_title=f"{role} role")
            if posting:
                if DEBUG_DISCOVERY: print(f"    ✅ SUCCESS (board): {posting.title}")
                return posting
        except Exception as e:
            if DEBUG_DISCOVERY: print(f"    ⚠️ Board query failed: {e}")

    if DEBUG_DISCOVERY: print(f"--- Job Check for {company.name} complete. No jobs found. ---")
    return None
