from __future__ import annotations
import re, os, httpx, asyncio
from typing import List, Dict, Optional
from ..schemas import CompanyIntel
from ..tools.exa_search import exa_search, exa_contents
from .roles import role_profile
from .match import match_role_to_pages
from urllib.parse import urlparse

# Utility function for HTTP HEAD checks (moved from utils.http)
# async def head_ok(url: str) -> bool:
#     """Check if URL is accessible via HEAD request"""
#     try:
#         async with httpx.AsyncClient(timeout=5) as client:
#             response = await client.head(url)
#             return response.status_code < 400
#     except Exception:
#         return False

# High-signal domains for "new/startup": path filters supported (Exa changelog 2025-08-04)
# docs: includeDomains supports paths + subdomain wildcards
SIGNAL_DOMAINS = [
    "producthunt.com/posts",       # product pages
    "www.ycombinator.com/companies",  # YC directory profiles
    "wellfound.com/company",       # AngelList/Wellfound company profiles
    "techcrunch.com",              # news coverage (no strict path)
    "crunchbase.com/organization"  # public org pages (sometimes partial)
]

DEBUG_DISCOVERY = os.getenv("DEBUG_DISCOVERY", "true").lower() == "true"
DOMAIN_FILTER_ENABLED = os.getenv("DOMAIN_FILTER_ENABLED", "true").lower() == "true"
MIN_URLS_FOR_FILTERED_PASS = int(os.getenv("MIN_URLS_FOR_FILTERED_PASS", "6"))

def _clean_url(url: str) -> str:
    """Clean malformed URLs by removing trailing characters and fixing common issues."""
    if not url:
        return url
    
    # Remove markdown link syntax and trailing characters
    url = re.sub(r'\]\([^)]*\)$', '', url)
    url = re.sub(r'\[.*?\]', '', url)
    
    # Fix malformed URLs with ](URL pattern
    url = re.sub(r'\]\(([^)]+)', r'\1', url)
    
    # Remove trailing punctuation and whitespace
    url = url.strip().rstrip('.,;:!?)]')
    
    return url

def _domain_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or None

def _first_external_link_or_domain(text: str, source_url: str) -> str | None:
    """Extract first external link that's likely a company homepage, or derive from source_url if it's a YC page."""
    # Clean source URL first
    source_url = _clean_url(source_url)
    
    # If the source URL is a YC page, try to find a direct external link within its content first
    if "ycombinator.com/companies" in source_url:
        urls = re.findall(r"https?://[^\s)]+", text)
        for u in urls:
            # Clean the URL first
            cleaned_url = _clean_url(u)
            # Heuristic: skip YC, producthunt, wellfound, crunchbase links within a YC profile if we can find a non-matching one
            if not any(dom.split("/")[0] in cleaned_url for dom in ["producthunt.com", "ycombinator.com", "wellfound.com", "techcrunch.com", "crunchbase.com"]):
                # Further filter: ensure it's not a generic image or social media link
                if not re.search(r'\.(png|jpg|jpeg|gif|svg|pdf)$|twitter.com|linkedin.com|facebook.com', cleaned_url, re.IGNORECASE):
                    return cleaned_url.strip('/')

    # Fallback to source_url if no better external link is found or if it's not a YC page
    parsed_source = urlparse(source_url)
    if parsed_source.netloc and "ycombinator.com" not in parsed_source.netloc: # Directly use source_url if it's a good candidate
        return _clean_url(source_url).strip('/')
    
    # Last resort: Try to find a link from the page text, but be more selective
    urls = re.findall(r"https?://[^\s)]+", text)
    for u in urls:
        if not any(dom.split("/")[0] in u for dom in ["producthunt.com","ycombinator.com","wellfound.com","techcrunch.com","crunchbase.com"]):
             if not re.search(r'\.(png|jpg|jpeg|gif|svg|pdf)$|twitter.com|linkedin.com|facebook.com', u, re.IGNORECASE):
                    return _clean_url(u).strip('/')
    
    return None

async def _light_contacts(homepage: str) -> dict:
    """Light contact enrichment: single GET, small range, no recursion"""
    if not homepage: return {}
    try:
        # Removed range header as it can cause issues with some servers
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            r = await client.get(homepage)
            if r.status_code>=400: return {}
            h = r.text[:6000] # Read up to 6000 chars
            mail = re.search(r"mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", h)
            links = re.findall(r'href="([^"]+)"', h)
            careers = next((u for u in links if re.search(r"/careers|/jobs|/join", u, re.I)), None)
            return {"email": mail.group(1) if mail else None, "careers": careers}
    except Exception as e:
        if DEBUG_DISCOVERY: print(f"⚠️ Light contacts failed for {homepage}: {e}")
        return {}

def caps_by_depth(depth: str):
    """Return (num_results, top_contents, max_chars) based on depth mode"""
    return {"light": (15, 8, 6000), "standard": (30, 15, 9000), "deep": (45, 20, 12000)}.get(depth, (30, 15, 9000))

async def discover_companies(city: str, role: str, k: int = 12, depth: str = "standard") -> List[CompanyIntel]:
    """
    Discover companies in a city for a specific role using high-signal domains
    """
    if DEBUG_DISCOVERY: print(f"🔍 Discovering companies in {city} for {role} role (depth: {depth})...")
    
    prof = role_profile(role)
    role_terms = " ".join(prof.get("keywords", [])[:6]) or role
    if DEBUG_DISCOVERY: print(f"🎯 Using role terms: {role_terms}")
    
    q = f"{city} {role_terms} AI startup"
    if DEBUG_DISCOVERY: print(f"🔍 Initial search query: '{q}' in domains: {SIGNAL_DOMAINS}")
    
    num_results, top_contents, max_chars = caps_by_depth(depth)
    if DEBUG_DISCOVERY: print(f"🎯 Depth mode: {depth} (search: {num_results}, content: {top_contents}, chars: {max_chars})")
    
    try:
        # Pass 1: filtered by SIGNAL_DOMAINS unless disabled
        hits = await exa_search(
            q,
            include_domains=SIGNAL_DOMAINS if DOMAIN_FILTER_ENABLED else None,
            num_results=num_results,
            want_highlights=True
        )
        if DEBUG_DISCOVERY: print(f"📊 Found {len(hits)} initial hits from Exa (filtered={DOMAIN_FILTER_ENABLED})")
        
        # Fallback: broaden if not enough URLs
        if len(hits) < MIN_URLS_FOR_FILTERED_PASS:
            if DEBUG_DISCOVERY: print("🔁 Broadening: running unfiltered search...")
            broad_hits = await exa_search(q, include_domains=None, num_results=num_results, want_highlights=True)
            # Prefer union but keep order preference (filtered first)
            seen = set([h.get('url') for h in hits if h.get('url')])
            hits = hits + [h for h in broad_hits if h.get('url') and h['url'] not in seen]

        # Second fallback: query variant without "AI startup" tail if still weak
        urls_to_fetch = [h["url"] for h in hits if h.get("url")]
        if len(urls_to_fetch) < MIN_URLS_FOR_FILTERED_PASS:
            if DEBUG_DISCOVERY: print("🔁 Broadening: trying role+city query (no 'AI startup')...")
            q2 = f"{city} {role_terms}"
            more = await exa_search(q2, include_domains=None, num_results=num_results, want_highlights=True)
            seen = set(urls_to_fetch)
            hits = hits + [h for h in more if h.get("url") and h["url"] not in seen]
            urls_to_fetch = [h["url"] for h in hits if h.get("url")]
        
        if not urls_to_fetch:
            if DEBUG_DISCOVERY: print("❌ No URLs found in initial search results.")
            return []
        
        if DEBUG_DISCOVERY: print(f"📄 Fetching content for top {min(top_contents, len(urls_to_fetch))} URLs...")
        contents = await exa_contents(urls_to_fetch[:top_contents], max_chars=max_chars) if urls_to_fetch else []
        if DEBUG_DISCOVERY: print(f"📄 Successfully fetched {len(contents)} content pages.")
        
    except Exception as e:
        print(f"❌ Error during initial search/content fetch: {e}")
        return []

    pages = []
    for c in contents:
        if c.get("url") and c.get("text"):
            pages.append({"url": c["url"], "text": c["text"], "title": c.get("title", "")})

    try:
        matches = await match_role_to_pages(
            role_blob=f"{role}\nkeywords: {', '.join(prof.get('keywords',[]))}\nhooks: {', '.join(prof.get('hooks',[]))}\nvalue_props: {', '.join(prof.get('value_props',[]))}",
            pages=pages, role_keywords=prof.get("keywords",[])
        )
        if DEBUG_DISCOVERY: print(f"🎯 Voyage AI matcher: {len(matches)} matches")
    except Exception as e:
        if DEBUG_DISCOVERY: print(f"⚠️ Voyage AI matcher failed: {e}, using keyword fallback")
        matches = []
        for p in pages:
            text_low = (p.get("text","")[:1200]).lower()
            matched_kw = [kw for kw in prof.get("keywords", []) if kw.lower() in text_low]
            score = min(100.0, 20.0 + (len(matched_kw) * 15.0))  # 20-100 based on keyword matches
            matches.append({"url": p.get("url"), "match_score": score, "matched_keywords": matched_kw, "why": f"mentions: {', '.join(matched_kw[:4])}" if matched_kw else "basic match"})
        if DEBUG_DISCOVERY: print(f"🎯 Keyword fallback: {len(matches)} matches")
    
    m_by_url = {m["url"]: m for m in matches}

    results: List[CompanyIntel] = []
    
    processed_companies = set()

    # First pass: try to get canonical homepage and clean name
    initial_companies = []
    for item in contents:
        url = item.get("url")
        text = item.get("text","")
        title = item.get("title","")
        if not url: continue

        # --- Aggressive Company Name Cleaning ---
        # 1. Remove generic suffixes
        company_name_raw = re.sub(r'\s*\|?\s*(Y Combinator|Crunchbase).*$', '', title, flags=re.IGNORECASE).strip()
        # 2. Extract name from titles like "Careers at Acme Inc." or "Acme is hiring"
        name_match = re.search(r'(?:at|for|with)\s+([A-Z][\w\s&.-]+)', company_name_raw, flags=re.IGNORECASE)
        if name_match and len(name_match.group(1)) > 3:
             clean_company_name = name_match.group(1).strip()
        else:
            # 3. Fallback to the text before the first colon or dash
            clean_company_name = re.split(r'[:\-|–]', company_name_raw)[0].strip()

        if not clean_company_name: # Final fallback
            clean_company_name = title.split(" ")[0]

        # Try to find a better homepage, prioritizing direct company domains
        derived_homepage = _first_external_link_or_domain(text, url)
        if not derived_homepage: # Fallback to cleaned URL domain if no external link found
            parsed_url = urlparse(url)
            derived_homepage = f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.netloc else url
            if DEBUG_DISCOVERY: print(f"    Using parsed URL domain as homepage: {derived_homepage}")

        # If the derived homepage is still a YC or generic profile, try a dedicated Exa search for the homepage
        if derived_homepage and any(d in derived_homepage for d in ["ycombinator.com", "wellfound.com", "crunchbase.com"]):
            if DEBUG_DISCOVERY: print(f"  🔎 Refining homepage for '{clean_company_name}' from '{derived_homepage}'...")
            try:
                homepage_search_query = f'"{clean_company_name}" homepage official website'
                homepage_results = await exa_search(homepage_search_query, num_results=1, want_highlights=False)
                if homepage_results and homepage_results[0].get("url"):
                    potential_homepage = homepage_results[0]["url"].strip('/')
                    # Ensure it's not another generic profile
                    if not any(d in potential_homepage for d in ["ycombinator.com", "wellfound.com", "crunchbase.com"]):
                        derived_homepage = potential_homepage
                        if DEBUG_DISCOVERY: print(f"    ✅ Refined homepage to: {derived_homepage}")
                else:
                    if DEBUG_DISCOVERY: print(f"    ❌ No better homepage found for '{clean_company_name}'. Using '{derived_homepage}'.")
            except Exception as e:
                if DEBUG_DISCOVERY: print(f"    ⚠️ Homepage refinement failed for '{clean_company_name}': {e}")
        
        # CRITICAL FIX: Clean the final derived homepage URL
        derived_homepage = _clean_url(derived_homepage)
        
        initial_companies.append({
            "name": clean_company_name,
            "homepage": derived_homepage,
            "source_url": url,
            "blurb": item.get("summary", "") or text[:500],
            "full_text": text,
            "match_data": m_by_url.get(url, {"match_score":0,"matched_keywords":[],"why":""}),
            "original_title": title
        })

    if DEBUG_DISCOVERY: print(f"Found {len(initial_companies)} companies after initial parsing. Now enriching contacts...")

    # Process companies in parallel for contact enrichment
    contact_enrichment_tasks = []
    for company_data in initial_companies:
        # Ensure homepage is not None before adding to processed_companies set
        if company_data["homepage"] and company_data["homepage"] not in processed_companies: 
            contact_enrichment_tasks.append((company_data, _light_contacts(company_data["homepage"])))
            processed_companies.add(company_data["homepage"])
        else:
            if DEBUG_DISCOVERY: print(f"  Skipping duplicate or invalid homepage: {company_data['homepage']}")
    
    if not contact_enrichment_tasks:
        if DEBUG_DISCOVERY: print("❌ No unique homepages to enrich contacts for.")
        return []

    # Wait for all contact enrichment to complete
    enriched_results = await asyncio.gather(*[task[1] for task in contact_enrichment_tasks], return_exceptions=True)

    for i, contacts_result in enumerate(enriched_results):
        company_data = contact_enrichment_tasks[i][0]
        name = company_data["name"]
        homepage = company_data["homepage"]
        source_url = company_data["source_url"]
        blurb = company_data["blurb"]
        full_text = company_data["full_text"]
        match_data = company_data["match_data"]
        original_title = company_data["original_title"]

        contacts = {} # Default empty
        if not isinstance(contacts_result, Exception):
            contacts = contacts_result
        else:
            if DEBUG_DISCOVERY: print(f"⚠️ Contact enrichment failed for {name} ({homepage}): {contacts_result}")

        # Use actual blurb if available, otherwise fallback
        final_blurb = blurb
        if not final_blurb and full_text:
            b = re.search(r"(About\s+[^.\n]+[.\n]|[A-Z][^.]{40,200}\.)", full_text)
            final_blurb = b.group(0).strip() if b else full_text[:500]

        base_score = float(match_data["match_score"])
        
        # Add bonuses for source quality
        if "producthunt.com" in source_url:
            base_score += 1.0
        if "ycombinator.com" in source_url or "wellfound.com" in source_url:
            base_score += 0.8
        if contacts and (contacts.get("email") or contacts.get("careers")):
            base_score += 0.2
        
        company = CompanyIntel(
            name=name,
            homepage=homepage,
            source_url=source_url,
            blurb=final_blurb,
            city=city,
            tags=prof.get("keywords", [])[:5],
            contact_hint=contacts.get("email") or contacts.get("careers"),
            score=base_score,
            intel={"original_title": original_title, "full_text_preview": full_text[:500]}
        )
        
        results.append(company)
        if DEBUG_DISCOVERY: print(f"    ✅ Added company for job search: {name} (Homepage: {homepage}, Score: {base_score:.1f})")

    results.sort(key=lambda x: (-x.score, x.name.lower()))
    
    if DEBUG_DISCOVERY: print(f"🏆 Returning top {min(k, len(results))} companies out of {len(results)} discovered")
    for i, company in enumerate(results[:k]):
        if DEBUG_DISCOVERY: print(f"  {i+1}. {company.name} - Score: {company.score:.1f} - {company.homepage}")
    
    return results[:k]