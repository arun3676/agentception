from __future__ import annotations
import asyncio
import json
import logging
import os
import traceback
from typing import List, Dict, Any, Optional, Tuple, Set
from pydantic import BaseModel, Field

from ..schemas import TimelineEvent, CompanyIntel, JobPosting
from ..rag.roles import role_profile
from ..tools.resume_store import get_text as get_resume_text, extract_resume_insights
from .job_search import (
    check_job_availability, 
    parse_location, 
    format_location_phrase,
    _looks_like_listing_page,
    _second_hop_from_listing,
    get_optimal_sites_for_role  # Smart role-based site selection
)
from ..memory.state_store import Memory
from ..memory.redis_cache import (
    get_cached_search_results, 
    cache_search_results,
    get_cached_ats_query,
    cache_ats_query
)
from .match import smart_search, SearchHit
from ..rag.match import _embed, _cos  # Use existing embedding logic
from ..tools.resume_job_matcher import compute_match_score as hybrid_match, analyze_gaps
from .trust_scorer import enhance_job_data, is_ats_platform, clean_snippet

logger = logging.getLogger(__name__)

# Terms that invalidate a company name (as whole words, not substrings)
# This uses word boundary matching so "Basis Research" is valid but "Top Jobs" is not
INVALID_COMPANY_TERMS = {
    'simplyhired', 'indeed', 'linkedin', 'jobs', 'careers', 'hiring',
    'intern', 'internship', 'greenhouse', 'lever', 'workday', 'ashby',
    'apply', 'remote', 'ziprecruiter', 'glassdoor', 'talent', 'jooble',
    'monster', 'careerbuilder', 'dice', 'hired', 'angellist', 'wellfound',
    'top', 'best', 'find', 'browse', 'explore'
}

KNOWN_SHORT_COMPANIES = {'ibm', 'hp', 'ge', 'aws', 'gcp', 'meta', 'uber', 'lyft', 'arm', 'amd', 'nvidia'}

import re

def format_job_for_display(job_data: dict, searched_role: str) -> dict:
    """
    Format job data for clean, consistent display.
    Returns dict with clean_title, clean_company, summary, location, source_tag.
    
    If data is already pre-cleaned (is_pre_cleaned=True), just pass it through.
    """
    import re
    from urllib.parse import urlparse, unquote

    # === CHECK IF ALREADY PRE-CLEANED ===
    if job_data.get('is_pre_cleaned'):
        # Data already cleaned by extraction pipeline - just format for display
        company = job_data.get('company', '') or job_data.get('company_name', '')
        title = job_data.get('title', '') or job_data.get('job_title', '') or searched_role
        snippet = job_data.get('snippet', '') or job_data.get('blurb', '')
        location = job_data.get('job_location', '') or job_data.get('location', '')
        url = job_data.get('url', '') or job_data.get('job_url', '')
        is_remote = job_data.get('is_remote', False)
        
        # Determine source tag from URL
        source_tag = "Job Board"
        url_lower = url.lower()
        if 'lever.co' in url_lower:
            source_tag = "Lever"
        elif 'greenhouse.io' in url_lower:
            source_tag = "Greenhouse"
        elif 'ashbyhq.com' in url_lower or 'ashby' in url_lower:
            source_tag = "Ashby"
        elif 'workday' in url_lower:
            source_tag = "Workday"
        elif 'workable.com' in url_lower:
            source_tag = "Workable"
        
        # Format location display
        if is_remote or 'remote' in location.lower():
            location_display = "🌐 Remote"
        elif location:
            location_display = f"📍 {location}"
        else:
            location_display = "📍 See job posting"
        
        # Clean title of trailing "at" if present
        if title.endswith(' at'):
            title = title[:-3].strip()
        
        # Store display data
        job_data['display'] = {
            'title': title,
            'source_tag': source_tag,
            'company': company,
            'summary': snippet,
            'location': location_display,
        }
        job_data['job_title'] = title
        job_data['company_name'] = company
        job_data['job_location'] = location_display
        job_data['blurb'] = snippet
        
        return job_data

    # === ORIGINAL LOGIC FOR NON-PRE-CLEANED DATA ===
    ATS_PLATFORMS = {'ashbyhq', 'ashby', 'greenhouse', 'lever', 'workday',
                     'workable', 'icims', 'jobvite', 'bamboohr', 'jazz',
                     'job-boards', 'boards', 'jobs'}

    raw_title = job_data.get('job_title') or job_data.get('title') or searched_role
    raw_company = job_data.get('company_name') or job_data.get('company') or ''
    raw_snippet = job_data.get('blurb') or job_data.get('snippet') or ''
    raw_url = job_data.get('job_url') or job_data.get('url') or ''
    raw_location = job_data.get('job_location') or job_data.get('location') or ''
    is_remote = job_data.get('is_remote', False)
    is_local = job_data.get('is_local', False)

    # === STEP 1: Extract REAL company from URL FIRST ===
    extracted_company = ""
    source_tag = "Job Board"
    url_lower = raw_url.lower()
    
    try:
        parsed = urlparse(raw_url)
        domain = parsed.netloc.lower()
        path = parsed.path
        path_parts = [p for p in path.split('/') if p and len(p) > 1]
        
        # Ashby: jobs.ashbyhq.com/companyname/jobid
        if 'ashbyhq.com' in domain or 'ashby' in domain:
            source_tag = 'Ashby'
            if path_parts:
                extracted_company = path_parts[0]  # First path segment is company
        
        # Greenhouse: boards.greenhouse.io/companyname/jobs/id OR job-boards.greenhouse.io/companyname/id
        elif 'greenhouse.io' in domain:
            source_tag = 'Greenhouse'
            if path_parts:
                extracted_company = path_parts[0]  # First path segment is company
        
        # Lever: jobs.lever.co/companyname/jobid OR companyname.lever.co/jobid
        elif 'lever.co' in domain:
            source_tag = 'Lever'
            if domain.startswith('jobs.lever.co'):
                # jobs.lever.co/companyname/jobid - company is first path segment
                if path_parts:
                    extracted_company = path_parts[0]
            else:
                # companyname.lever.co/jobid - company is subdomain
                subdomain = domain.split('.lever.co')[0]
                if subdomain and subdomain not in ['jobs', 'www', 'careers']:
                    extracted_company = subdomain
        
        # Workable: companyname.workable.com/...
        elif '.workable.com' in domain:
            source_tag = 'Workable'
            subdomain = domain.split('.workable.com')[0]
            if subdomain and subdomain not in ['jobs', 'www', 'apply']:
                extracted_company = subdomain
        
        # Workday: company.wd5.myworkdayjobs.com/...
        elif 'workday' in domain or 'myworkdayjobs' in domain:
            source_tag = 'Workday'
            subdomain = domain.split('.')[0]
            if subdomain and subdomain not in ['jobs', 'www']:
                extracted_company = subdomain
                
    except Exception as e:
        print(f"    ⚠️ URL parse error: {e}")
    
    # === STEP 2: Clean extracted company name ===
    def clean_company_name(name: str) -> str:
        if not name:
            return ""
        name = unquote(name)
        name = name.replace('-', ' ').replace('_', ' ')
        # Smart title case
        words = []
        for w in name.split():
            upper = w.upper()
            if upper in ['AI', 'ML', 'IO', 'HR', 'IT', 'API', 'HQ', 'US', 'UK']:
                words.append(upper)
            elif len(w) <= 2:
                words.append(upper)
            else:
                words.append(w.capitalize())
        return ' '.join(words)
    
    clean_company = clean_company_name(extracted_company)
    
    # If extraction failed or got ATS name, try raw_company
    if not clean_company or clean_company.lower() in ATS_PLATFORMS:
        fallback = clean_company_name(raw_company)
        if fallback and fallback.lower() not in ATS_PLATFORMS:
            clean_company = fallback
    
    # If still ATS name, try extracting from title "Job at Company"
    if not clean_company or clean_company.lower() in ATS_PLATFORMS:
        if ' at ' in raw_title:
            potential = raw_title.split(' at ')[-1].strip()
            potential = potential.split(' - ')[0].split('|')[0].strip()
            potential_clean = clean_company_name(potential)
            if potential_clean and potential_clean.lower() not in ATS_PLATFORMS:
                clean_company = potential_clean
    
    # Final fallback - mark as unknown
    if not clean_company or clean_company.lower() in ATS_PLATFORMS:
        clean_company = f"Company via {source_tag}"

    # === STEP 3: Clean Job Title ===
    clean_title = raw_title or searched_role
    
    # Remove "at Company" suffix (including the company we just extracted)
    if ' at ' in clean_title:
        clean_title = clean_title.split(' at ')[0].strip()
    if ' @ ' in clean_title:
        clean_title = clean_title.split(' @ ')[0].strip()
    
    # Remove " - Company" suffix
    if ' - ' in clean_title:
        parts = clean_title.split(' - ')
        # Keep the part that looks like a job title
        role_keywords = ['engineer', 'manager', 'developer', 'analyst', 'designer', 
                        'architect', 'lead', 'senior', 'staff', 'principal', 'director',
                        'scientist', 'specialist', 'coordinator', 'cloud', 'data', 'python']
        for part in parts:
            if any(kw in part.lower() for kw in role_keywords):
                clean_title = part.strip()
                break
    
    # Remove ATS platform names from title
    for ats in ['Greenhouse', 'Lever', 'Ashby', 'Ashbyhq', 'Workday', 'Workable']:
        clean_title = re.sub(rf'\s*[-–@|]\s*{ats}\b', '', clean_title, flags=re.I)
        clean_title = re.sub(rf'\b{ats}\s*[-–@|]\s*', '', clean_title, flags=re.I)
    
    # If title is garbage, use searched role
    garbage_titles = ['jobs', 'careers', 'job', 'apply', 'hiring', 'positions', '']
    if clean_title.lower().strip() in garbage_titles:
        clean_title = searched_role
    
    clean_title = clean_title.strip(' -–|:')

    # === STEP 4: Generate Summary ===
    summary = ""
    if raw_snippet:
        snippet_clean = raw_snippet.replace('\n', ' ').strip()
        
        # Skip placeholder text
        if 'click to view' in snippet_clean.lower():
            snippet_clean = ""
        
        if snippet_clean:
            # Try to extract meaningful summary
            summary_patterns = [
                r"(?:we're |we are )?(?:looking for|seeking|hiring)[^.]{10,80}",
                r"(?:join|help|build)[^.]{10,80}",
                r"(?:responsible for|work on|develop)[^.]{10,80}",
            ]
            
            for pattern in summary_patterns:
                match = re.search(pattern, snippet_clean, re.I)
                if match:
                    summary = match.group(0).strip()
                    summary = summary[0].upper() + summary[1:] if summary else ""
                    break
            
            # Fallback: first sentence if long enough
            if not summary:
                sentences = snippet_clean.split('.')
                if sentences and len(sentences[0]) > 30:
                    summary = sentences[0].strip()
    
    # Truncate summary
    if summary and len(summary) > 120:
        summary = summary[:117] + "..."
    
    # Generate fallback summary from title
    if not summary:
        level = ""
        title_lower = clean_title.lower()
        if any(x in title_lower for x in ['senior', 'sr.', 'sr ']):
            level = "Senior "
        elif any(x in title_lower for x in ['staff', 'principal', 'lead']):
            level = "Staff "
        elif any(x in title_lower for x in ['junior', 'jr.', 'entry']):
            level = "Entry-level "
        
        # Extract role type from title
        role_words = clean_title.split()
        role_type = role_words[-1] if role_words else "professional"
        if role_type.lower() in ['engineer', 'developer', 'manager', 'analyst', 'designer']:
            summary = f"{level}{clean_title} opportunity at {clean_company}"
        else:
            summary = f"Hiring {level}{clean_title}"

    # === STEP 5: Format Location ===
    location_display = ""
    
    # Common location abbreviations
    LOCATION_ABBREVS = {
        'la': 'Los Angeles, CA', 'sf': 'San Francisco, CA', 'nyc': 'New York, NY',
        'dc': 'Washington, DC', 'chi': 'Chicago, IL', 'atl': 'Atlanta, GA',
        'sea': 'Seattle, WA', 'bos': 'Boston, MA', 'den': 'Denver, CO',
        'aus': 'Austin, TX', 'mia': 'Miami, FL', 'phx': 'Phoenix, AZ',
    }
    
    def expand_location(loc: str) -> str:
        """Expand abbreviated locations and clean up."""
        if not loc:
            return loc
        loc_lower = loc.lower().strip()
        # Check abbreviations
        if loc_lower in LOCATION_ABBREVS:
            return LOCATION_ABBREVS[loc_lower]
        # Title case if all lowercase and short
        if loc == loc.lower() and len(loc) < 20:
            return loc.title()
        return loc
    
    # Check explicit flags first
    if is_remote:
        location_display = "🌐 Remote"
    elif is_local and raw_location:
        location_display = f"📍 {expand_location(raw_location)}"
    elif raw_location and raw_location.lower() not in ['', 'none', 'n/a']:
        if 'remote' in raw_location.lower():
            location_display = "🌐 Remote"
        else:
            location_display = f"📍 {expand_location(raw_location)}"
    else:
        # Try to extract from snippet
        location_text = raw_snippet or ""
        loc_patterns = [
            r'((?:Austin|Denver|Miami|San Francisco|SF|New York|NYC|Seattle|Chicago|Boston|Atlanta|Los Angeles|LA)[,\s]*(?:TX|CO|FL|CA|NY|WA|IL|MA|GA)?)',
            r'(Remote|Hybrid|On-?site)',
        ]
        
        for pattern in loc_patterns:
            match = re.search(pattern, location_text, re.I)
            if match:
                loc = match.group(1).strip()
                if 'remote' in loc.lower():
                    location_display = "🌐 Remote"
                else:
                    location_display = f"📍 {loc}"
                break
    
    if not location_display:
        location_display = "📍 See job posting"

    # === STEP 6: Store display data ===
    job_data['display'] = {
        'title': clean_title,
        'source_tag': source_tag,
        'company': clean_company,
        'summary': summary,
        'location': location_display,
    }
    
    # Also update top-level fields for backward compatibility
    job_data['job_title'] = clean_title
    job_data['company_name'] = clean_company
    job_data['job_location'] = location_display
    job_data['blurb'] = summary

    return job_data


async def validate_job_url(url: str, timeout: float = 3.0) -> dict:
    """
    Quick validation of job URL to detect expired/removed jobs.
    Returns: {'exists': bool, 'reason': str}
    
    Checks for:
    - 404/410 status codes (job removed)
    - Redirect to careers page (job filled/expired)
    - "no longer available" text in response
    """
    import aiohttp
    
    if not url:
        return {'exists': False, 'reason': 'no_url'}
    
    # Known patterns that indicate expired jobs
    EXPIRED_PATTERNS = [
        'no longer available',
        'position has been filled',
        'job has been removed',
        'this job is closed',
        'expired',
        'not found',
        'does not exist',
        'no longer accepting',
        'position is no longer',
    ]
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, 
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; JobChecker/1.0)'}
            ) as response:
                # Check status code
                if response.status in [404, 410, 403]:
                    return {'exists': False, 'reason': f'status_{response.status}'}
                
                # Check if redirected to generic careers page
                final_url = str(response.url).lower()
                if any(p in final_url for p in ['/careers', '/jobs/', '/openings']) and 'job' not in final_url[-50:]:
                    # Redirected to listing page, not specific job
                    return {'exists': False, 'reason': 'redirect_to_listing'}
                
                # Quick check of response text for expired patterns, and grab the
                # posted salary from the same fetch (JSON-LD baseSalary is authoritative).
                salary = None
                if response.status == 200:
                    try:
                        text = await response.text()
                        text_lower = text[:5000].lower()  # Only check first 5KB
                        for pattern in EXPIRED_PATTERNS:
                            if pattern in text_lower:
                                return {'exists': False, 'reason': f'expired_text:{pattern[:20]}'}
                        from ..tools.salary import extract_salary
                        salary = extract_salary(jsonld_html=text, text=text[:8000])
                    except Exception:
                        pass  # If we can't read text, assume it exists

                return {'exists': True, 'reason': 'ok', 'salary': salary}
                
    except asyncio.TimeoutError:
        # Timeout - assume exists (don't penalize slow sites)
        return {'exists': True, 'reason': 'timeout'}
    except Exception as e:
        # Network error - assume exists
        return {'exists': True, 'reason': f'error:{str(e)[:30]}'}


def is_valid_company_name(name: str) -> bool:
    """
    Validate company name using word boundaries (not substring matching).
    This fixes: "Basis Research" → VALID (search is not a standalone word)
    """
    if not name:
        return False
    
    name_clean = name.strip()
    name_lower = name_clean.lower()
    
    # Reject if too long (search result titles)
    if len(name_clean) > 50:
        print(f"    ⚠️ Rejected '{name}': too long")
        return False
    
    # Reject if too many words
    words = name_clean.split()
    if len(words) > 5:
        print(f"    ⚠️ Rejected '{name}': too many words ({len(words)})")
        return False
    
    # Check each word against invalid terms (word boundary matching)
    for word in words:
        word_lower = word.lower().strip('.,!?()[]{}')
        if word_lower in INVALID_COMPANY_TERMS:
            print(f"    ⚠️ Rejected '{name}': contains invalid term '{word_lower}'")
            return False
    
    # Reject if contains location patterns
    location_pattern = r',\s*[A-Z]{2}\s*$|san francisco|new york|los angeles|austin|seattle|boston|chicago|remote'
    if re.search(location_pattern, name_lower):
        print(f"    ⚠️ Rejected '{name}': contains location")
        return False
    
    # Reject year patterns
    if re.search(r'\b20[2-3][0-9]\b', name_lower):
        print(f"    ⚠️ Rejected '{name}': contains year")
        return False
    
    # Reject too short unless whitelisted
    if len(name_lower) < 3 and name_lower not in KNOWN_SHORT_COMPANIES:
        print(f"    ⚠️ Rejected '{name}': too short")
        return False
    
    print(f"    ✅ Valid company name: {name}")
    return True


# Patterns that indicate this is a search result title, not a company name
SEARCH_TITLE_PATTERNS = [
    r'\bjobs?\s+in\b',           # "jobs in", "job in"
    r'\bjobs?\s+for\b',          # "jobs for"
    r'\btop\s+\d+',              # "top 10", "top 5"
    r'\bbest\s+\d+',             # "best 10"
    r'\bfind\s+',                # "find careers"
    r'\bsearch\s+',              # "search jobs"
    r'\bhiring\s+now\b',         # "hiring now"
    r'\bopen\s+positions?\b',    # "open positions"
    r'\bcareer\s+opportunities\b',
    r'\bcareers?\s+at\b',        # "careers at" (listing page)
    r'\bjobs?\s+near\b',         # "jobs near"
    r',\s*[A-Z]{2}\s*$',         # ends with ", CA" or ", NY" (location suffix)
    r'\b\d{4}\b',                # contains year like 2024, 2025
]

PREFERRED_JOB_SITES = [
    {"name": "Wellfound", "site": "wellfound.com"},
    {"name": "YC Jobs", "site": "ycombinator.com/jobs"},
    {"name": "BuiltIn SF", "site": "builtinsf.com"},
    {"name": "BuiltIn NYC", "site": "builtinnyc.com"},
    {"name": "Ashby", "site": "ashbyhq.com"},
    {"name": "Lever", "site": "jobs.lever.co"},
    {"name": "Greenhouse Boards", "site": "boards.greenhouse.io"},
]


# UUID pattern - these are NOT job titles
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}[-\s]?[0-9a-f]{4}[-\s]?[0-9a-f]{4}[-\s]?[0-9a-f]{4}[-\s]?[0-9a-f]{12}$', re.I)

def is_id_not_title(text: str) -> bool:
    """Check if text is an ID (UUID, number) rather than a job title."""
    if not text:
        return True
    text = text.strip()
    # Numeric IDs
    if text.isdigit():
        return True
    # UUIDs (with or without dashes/spaces)
    if UUID_PATTERN.match(text.replace(' ', '-')):
        return True
    # Short hex strings that look like IDs
    if len(text) <= 16 and all(c in '0123456789abcdefABCDEF- ' for c in text):
        return True
    return False

def needs_llm_extraction(company: str, title: str, url: str) -> bool:
    """Return True if heuristic extraction is uncertain and needs LLM."""
    if not company or not title:
        return True
    
    # Check company quality
    ats_vendors = ['lever', 'greenhouse', 'ashby', 'workday', 'workable', 'icims', 'jobvite']
    if company.lower() in ats_vendors:
        return True
    
    if len(company) < 2 or company.lower() in ['jobs', 'careers', 'hiring']:
        return True

    # Check title quality - detect garbage patterns
    title_lower = title.lower().strip()
    
    garbage_title_patterns = [
        'job application for',
        'apply for',
        'hiring job application',
        'click to view',
        'view full job',
        'job opening at',
        'we are hiring',
        'now hiring',
        'jobs at',
        'careers at',
        'open positions',
        'job board',
    ]
    
    if any(pattern in title_lower for pattern in garbage_title_patterns):
        return True
    
    # Title is too short (likely just "Jobs" or similar)
    if len(title.strip()) < 5:
        return True

    # Title ends with " at" (incomplete parsing)
    if title_lower.endswith(' at'):
        return True
    
    # Title starts with company name (usually means bad parsing)
    if company and title_lower.startswith(company.lower()):
        return True
    
    # === NEW: Detect titles that look like company suffixes, not job roles ===
    company_suffix_patterns = [
        r'^(software|inc|llc|corp|corporation|ltd|limited|co|company|group|holdings|solutions|services|technologies|tech)[\.\s,]*$',
        r'^[\w\s]+,\s*(inc|llc|corp|ltd)\.?$',  # "Something, Inc."
        r'^the\s+[\w]+$',  # "The Company" without role
    ]
    for pattern in company_suffix_patterns:
        if re.match(pattern, title_lower):
            return True
    
    # Title doesn't contain any role-related keywords (likely garbage)
    role_keywords = ['engineer', 'developer', 'analyst', 'manager', 'designer', 'architect',
                     'lead', 'senior', 'staff', 'principal', 'director', 'scientist',
                     'specialist', 'coordinator', 'associate', 'intern', 'consultant',
                     'administrator', 'executive', 'officer', 'head', 'vp', 'vice president',
                     'product', 'data', 'software', 'marketing', 'sales', 'operations',
                     'finance', 'hr', 'human resources', 'recruiter', 'talent']
    
    has_role_keyword = any(kw in title_lower for kw in role_keywords)
    if not has_role_keyword:
        return True
    
    return False

JOB_ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string", "description": "Hiring company name, not the job board"},
        "title": {"type": "string", "description": "Clean job role/position without prefixes"},
        "location": {"type": "string", "description": "Job location or 'Remote'"},
        "description": {"type": "string", "description": "One-sentence professional summary of the role"},
        "is_remote": {"type": "boolean", "description": "True if remote/wfh job"}
    },
    "required": ["company", "title", "location", "description", "is_remote"],
    "additionalProperties": False
}

async def extract_with_llm(url: str, page_title: str, snippet: str) -> dict:
    """Call OpenAI with Structured Outputs for guaranteed schema."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(timeout=5.0)
    
    system_prompt = """You are a job posting parser. Extract clean, professional job information.

RULES:
1. company: The hiring company name (NOT "Lever", "Greenhouse", "Ashby" - those are job platforms)
2. title: The CLEAN job role. Remove prefixes like "Job Application for", "Apply for", "Hiring". 
   - Good: "Senior Product Manager", "ML Engineer", "Staff Designer"
   - Bad: "Job Application for Product Manager, AI at", "Hiring Job Application for..."
3. location: City, State OR "Remote". Not company HQ unless it's the job location.
4. description: A 1-sentence professional summary of what this role does. If snippet is garbage like "Click to view", generate a sensible description based on the job title.
5. is_remote: true if remote/wfh/anywhere mentioned"""

    user_prompt = f"""URL: {url}
Raw Title: {page_title}
Snippet: {snippet}

Extract the job information. Clean up the title and generate a professional description."""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "job_entity",
                "strict": True,
                "schema": JOB_ENTITY_SCHEMA
            }
        },
    )
    
    content = response.choices[0].message.content
    return json.loads(content) if content else {}

# === EXTRACTION LADDER ===
# In-memory cache for LLM extraction results (avoids repeated API calls during dev/testing)
_extraction_cache: Dict[str, dict] = {}

def clean_job_title(raw_title: str, company: str = "") -> str:
    """Clean garbage prefixes from job titles."""
    if not raw_title:
        return ""
    
    title = raw_title.strip()
    
    # Remove common garbage prefixes
    garbage_prefixes = [
        'job application for ',
        'apply for ',
        'hiring job application for ',
        'apply now: ',
        'hiring: ',
        'now hiring: ',
        'job opening: ',
        'open position: ',
        'we are hiring: ',
        'careers: ',
    ]
    
    title_lower = title.lower()
    for prefix in garbage_prefixes:
        if title_lower.startswith(prefix):
            title = title[len(prefix):]
            title_lower = title.lower()
    
    # Remove " at Company" or " @ Company" suffix
    if ' at ' in title:
        title = title.split(' at ')[0].strip()
    if ' @ ' in title:
        title = title.split(' @ ')[0].strip()

    # Remove incomplete trailing " at" / " @" from bad parsing
    title_lower = title.lower().strip()
    if title_lower.endswith(' at'):
        title = title[:-3].strip()
    if title_lower.endswith(' @'):
        title = title[:-2].strip()
    
    # Remove " - Company" but keep role-oriented part
    if ' - ' in title:
        parts = title.split(' - ')
        role_words = ['engineer', 'manager', 'developer', 'analyst', 'designer', 
                      'architect', 'lead', 'senior', 'staff', 'principal', 'director',
                      'scientist', 'specialist', 'product', 'data', 'software']
        for part in parts:
            if any(word in part.lower() for word in role_words):
                title = part.strip()
                break
    
    # Remove company name if it appears in title
    if company:
        title = re.sub(re.escape(company), '', title, flags=re.I).strip()
    
    # Clean up remaining artifacts
    title = re.sub(r'^[\s\-–|:]+', '', title)  # Leading punctuation
    title = re.sub(r'[\s\-–|:]+$', '', title)  # Trailing punctuation
    title = re.sub(r'\s+', ' ', title)  # Multiple spaces
    
    return title.strip()

async def extract_job_entities(url: str, page_title: str, snippet: str) -> dict:
    """
    Hybrid extraction: heuristics first, LLM only when uncertain.
    
    Ladder:
    1. Try regex/heuristics (free, fast)
    2. If uncertain → gpt-4o-mini with Structured Outputs
    3. If LLM fails → return heuristic result with needs_review=True
    """
    # Step 1: Heuristic extraction (existing function)
    company, title = extract_company_and_title(url, page_title)
    
    # Step 2: Check if we need LLM
    if not needs_llm_extraction(company, title, url):
        # Heuristics worked fine - but clean the title and generate proper description
        cleaned_title = clean_job_title(title, company)
        
        # Generate professional description (don't use raw snippet which may be garbage)
        description = ""
        snippet_lower = snippet.lower() if snippet else ""
        
        # Detect garbage snippet patterns
        garbage_snippet_patterns = [
            'click to view', 'apply now', 'view full', 'see more',
            'mid level', 'entry level', 'senior level',  # These are metadata, not descriptions
            'united states · apply', 'apply ·', '· apply',
            'on-site###', '###',  # Malformed data
        ]
        is_garbage_snippet = any(p in snippet_lower for p in garbage_snippet_patterns)
        
        if snippet and not is_garbage_snippet and len(snippet) > 50:
            # Try to extract a meaningful sentence from the snippet
            # Skip metadata-heavy snippets that start with location/level info
            if not re.match(r'^(mid|senior|entry|junior|staff|principal)\s*(level)?', snippet_lower):
                # Find first sentence that looks like a description
                sentences = re.split(r'[.!?]', snippet)
                for sent in sentences:
                    sent = sent.strip()
                    # Good sentence: 20+ chars, has verbs/nouns, not just metadata
                    if len(sent) > 20 and not re.match(r'^[\w\s,]+·', sent):
                        description = sent[:150]
                        if len(sent) > 150:
                            description = description.rsplit(' ', 1)[0] + '...'
                        break
        
        if not description:
            # Generate from title
            description = f"Seeking a {cleaned_title} to join the team"
        
        return {
            "company": company,
            "title": cleaned_title,
            "location": "",
            "description": description,
            "is_remote": 'remote' in snippet.lower() if snippet else False,
            "extraction_method": "heuristic"
        }
    
    # Step 3: Call LLM for uncertain cases (only if API key is set)
    if os.getenv("OPENAI_API_KEY"):
        try:
            llm_result = await extract_with_llm(url, page_title, snippet)
            llm_result["extraction_method"] = "llm"
            return llm_result
        except Exception as e:
            print(f"    ⚠️ LLM extraction failed: {e}")
    
    # Step 4: Fallback to heuristic with flag
    return {
        "company": company or "Unknown",
        "title": title or "Job Opening",
        "location": "",
        "description": snippet or "",
        "is_remote": False,
        "extraction_method": "heuristic_fallback",
        "needs_review": True
    }

async def extract_job_entities_cached(url: str, page_title: str, snippet: str) -> dict:
    """Cached version - essential for dev testing to avoid repeated LLM calls."""
    cache_key = url  # URL is unique enough
    
    if cache_key in _extraction_cache:
        result = _extraction_cache[cache_key].copy()
        result["from_cache"] = True
        return result
    
    result = await extract_job_entities(url, page_title, snippet)
    _extraction_cache[cache_key] = result
    return result

def extract_company_and_title(url: str, search_title: str = "", fallback_role: str = "") -> Tuple[str, str]:
    """
    Extract company name from URL, job title from search result title.
    
    URL paths often contain UUIDs/numeric IDs, NOT job titles.
    We get company from URL structure, but job title from search result.
    
    Returns: (company_name, job_title)
    """
    from urllib.parse import urlparse, unquote
    
    if not url:
        return "Unknown Company", fallback_role
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = unquote(parsed.path)
        path_parts = [p for p in path.split('/') if p and p.lower() not in 
                      ['jobs', 'job', 'embed', 'j', 'apply', 'careers', 'positions', 'posting', 'openings']]
    except:
        return "Unknown Company", fallback_role
    
    company = ""
    
    # === EXTRACT COMPANY FROM URL ===
    
    # Pattern 1: jobs.lever.co/company/jobid (most common)
    # Pattern 2: company.lever.co/jobid (subdomain style)
    if 'lever.co' in domain:
        if domain.startswith('jobs.lever.co'):
            # jobs.lever.co/companyname/jobid - company is first path segment
            if path_parts:
                company = path_parts[0]
        else:
            # company.lever.co/jobid - company is subdomain
            subdomain = domain.split('.lever.co')[0]
            if subdomain and subdomain.lower() not in ['jobs', 'www', 'careers', 'boards', 'job-boards']:
                company = subdomain
    
    # Pattern: boards.greenhouse.io/company/... or job-boards.greenhouse.io/company/...
    elif 'greenhouse.io' in domain:
        if path_parts:
            company = path_parts[0]  # First path segment is company
    
    # Pattern: jobs.ashbyhq.com/company/...
    elif 'ashbyhq.com' in domain:
        if path_parts:
            company = path_parts[0]
    
    # Pattern: company.workable.com/...
    elif '.workable.com' in domain:
        subdomain = domain.split('.workable.com')[0]
        if subdomain and subdomain.lower() not in ['jobs', 'www', 'apply']:
            company = subdomain
    
    # Pattern: builtinsf.com, builtinnyc.com, etc.
    elif 'builtin' in domain:
        # Company often in path or not extractable - will get from title
        pass
    
    # === CLEAN COMPANY NAME ===
    if company:
        company = unquote(company)
        company = company.replace('-', ' ').replace('_', ' ')
        # Smart title case (preserve acronyms)
        words = []
        for word in company.split():
            upper = word.upper()
            if upper in ['AI', 'ML', 'API', 'HR', 'IT', 'VP', 'CEO', 'CTO', 'NLP', 'IO', 'HQ']:
                words.append(upper)
            elif len(word) <= 2:
                words.append(upper)
            else:
                words.append(word.capitalize())
        company = ' '.join(words)
    
    # === EXTRACT JOB TITLE FROM SEARCH TITLE (not URL!) ===
    job_title = ""
    
    if search_title:
        title = search_title.strip()
        
        # Remove company name from title if we found it
        if company:
            title = re.sub(re.escape(company), '', title, flags=re.I).strip()
        
        # Remove ATS platform names
        for ats in ['Greenhouse', 'Lever', 'Ashby', 'Ashbyhq', 'Workday', 'Workable']:
            title = re.sub(r'\b' + ats + r'\b', '', title, flags=re.I)
        
        # Parse common patterns:
        
        # "Job Title at Company" or "Job Title @ Company"
        if ' at ' in title.lower():
            parts = re.split(r' at ', title, flags=re.I)
            job_title = parts[0].strip()
            # If no company yet, extract from "at Company" part
            if not company and len(parts) > 1:
                company = parts[-1].split(' - ')[0].split('|')[0].strip()
        
        elif ' @ ' in title:
            parts = title.split(' @ ')
            job_title = parts[0].strip()
            if not company and len(parts) > 1:
                company = parts[-1].split(' - ')[0].split('|')[0].strip()
        
        # "Company - Job Title" or "Job Title - Company"
        elif ' - ' in title:
            parts = [p.strip() for p in title.split(' - ')]
            # Find which part looks like a job title (has role keywords)
            role_keywords = ['engineer', 'manager', 'developer', 'analyst', 'designer', 
                           'architect', 'lead', 'senior', 'staff', 'principal', 'director',
                           'scientist', 'specialist', 'coordinator', 'associate', 'intern']
            for part in parts:
                if any(kw in part.lower() for kw in role_keywords):
                    job_title = part
                    break
            # If no match, use longest part as title
            if not job_title:
                job_title = max(parts, key=len)
        
        # "Company | Job Title"
        elif ' | ' in title:
            parts = [p.strip() for p in title.split(' | ')]
            for part in parts:
                if any(kw in part.lower() for kw in ['engineer', 'manager', 'developer']):
                    job_title = part
                    break
        
        # No separator - use whole title if it's not an ID
        if not job_title:
            cleaned = title.strip(' -|@:')
            if cleaned and not is_id_not_title(cleaned):
                job_title = cleaned
    
    # === FALLBACKS ===
    if not job_title or is_id_not_title(job_title):
        job_title = fallback_role
    
    if not company or company == "Unknown Company":
        # Try to extract from job_title if it has "at Company"
        if ' at ' in job_title.lower():
            parts = re.split(r' at ', job_title, flags=re.I)
            if len(parts) > 1:
                company = parts[-1].strip()
                job_title = parts[0].strip()
    
    # Final cleanup
    job_title = re.sub(r'\s+', ' ', job_title).strip(' -|@:')
    company = re.sub(r'\s+', ' ', company).strip() if company else "Unknown Company"
    
    # Clean the title before returning
    job_title = clean_job_title(job_title, company)
    
    return company, job_title


# Keep old function name as alias for backward compatibility
def extract_company_and_title_from_url(url: str) -> Tuple[str, str]:
    """Backward compatible wrapper - use extract_company_and_title instead."""
    return extract_company_and_title(url, "", "")


async def extract_job_title_from_text(snippet: str, page_title: str, fallback_role: str) -> str:
    """
    Extract actual job title from snippet or page title.
    Prioritizes snippet content over page title.
    """
    import re
    
    # Garbage titles to skip
    GARBAGE_TITLES = {'jobs', 'careers', 'job', 'career', 'openings', 'positions', 
                      'hiring', 'apply', 'join us', 'work with us', 'open roles'}
    
    # Check if page title is garbage
    title_lower = page_title.lower().strip() if page_title else ""
    is_garbage_title = (
        title_lower in GARBAGE_TITLES or
        title_lower.startswith('http') or
        len(title_lower) < 3 or
        'api/' in title_lower or
        '?mode=' in title_lower
    )
    
    # Try to extract from snippet first
    if snippet:
        # Pattern: Look for job title patterns in snippet
        patterns = [
            # "Senior Machine Learning Engineer" (common titles)
            r'((?:Senior|Staff|Lead|Principal|Junior|Entry[\s-]?Level|Chief|Head of)?\s*[A-Z][a-zA-Z\s]+(?:Engineer|Developer|Manager|Scientist|Analyst|Designer|Architect|Consultant))',
            # "Role: Title" or "Hiring: Title"
            r'(?:hiring|looking for|position|role|opportunity)[:\s]+([A-Z][a-zA-Z\s]+(?:Engineer|Developer|Manager|Scientist|Analyst))',
            # "We are hiring a Title"
            r'hiring\s+(?:a|an)\s+([A-Z][a-zA-Z\s]+(?:Engineer|Developer|Manager|Scientist|Analyst))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, snippet)
            if match:
                title = match.group(1).strip()
                # Validate: should be 2-6 words, no garbage
                words = title.split()
                if 2 <= len(words) <= 6 and title.lower() not in GARBAGE_TITLES:
                    return title
    
    # If page title is valid, use it
    if not is_garbage_title and page_title:
        # Clean up "X at Company" pattern
        if ' at ' in page_title:
            title = page_title.split(' at ')[0].strip()
            if title.lower() not in GARBAGE_TITLES:
                return title
        # Clean up "Company - Job Title"
        if ' - ' in page_title:
            parts = page_title.split(' - ')
            for part in parts:
                part = part.strip()
                if any(kw in part.lower() for kw in ['engineer', 'manager', 'developer', 'scientist', 'analyst']):
                    return part
        # Use page title if it looks like a job title
        if any(kw in title_lower for kw in ['engineer', 'manager', 'developer', 'scientist']):
            return page_title
    
    # Fallback to searched role
    return fallback_role


def is_job_listing_page(url: str, title: str) -> bool:
    """
    Check if URL is a generic listing page rather than a specific job posting.
    Returns True if should be skipped.
    """
    url_lower = url.lower() if url else ""
    title_lower = title.lower() if title else ""
    
    # URL patterns that indicate listing pages (not specific jobs)
    listing_url_patterns = [
        '/jobs?',           # Query string listings
        '/careers?',        # Career page queries
        '?mode=xml',        # API/XML feeds
        '?mode=json',       # API feeds
        '/v0/postings/',    # Lever API endpoint
        '/?%20',            # Malformed query strings
        '/jobs/',           # Often listing pages (though some ATS use this for jobs too, context matters)
        '?by=',             # Filter pages
        '?commitment=',     # Filter pages
        '?department=',     # Filter pages
        '?location=',       # Filter pages
        '&team=',           # Filter pages
        'jobs.ashbyhq.com/jobs', # Ashby listing root
        'boards.greenhouse.io/jobs', # Greenhouse listing root
    ]
    
    for pattern in listing_url_patterns:
        if pattern in url_lower:
            # Special case: /jobs/123 is valid, /jobs?location=SF is not
            if pattern == '/jobs/' and not any(c in url_lower for c in ['?', '&']):
                continue
            return True
    
    # Title patterns that indicate listing pages
    listing_title_patterns = [
        'jobs at',
        'careers at', 
        'open positions',
        'job openings',
        'current openings',
        'join our team',
        'work at',
    ]
    
    for pattern in listing_title_patterns:
        if pattern in title_lower:
            return True
    
    # Exact matches
    if title_lower.strip() in ['jobs', 'careers', 'job', 'apply', 'hiring']:
        return True
    
    return False


# --- Data Models ---

class SearchCandidate(BaseModel):
    name: str
    homepage: str
    source_url: str
    snippet: str
    score: float
    source_site: Optional[str] = None

class HiringCompany(BaseModel):
    company_name: str
    homepage_url: str
    job_title: Optional[str] = None
    job_url: Optional[str] = None
    job_location: Optional[str] = None
    job_source: Optional[str] = None
    job_type: str = "discovered"  # "discovered", "direct", or "job_board"
    score: float = 0.0
    rank_score: float = 0.0  # Computed ranking score after enrichment
    tags: List[str] = []
    blurb: Optional[str] = None
    job_posting: Optional[JobPosting] = None  # Optional enrichment from job_search
    resume_match_score: Optional[float] = None
    missing_skills: List[str] = []
    
    # Trust scoring fields
    trust_score: int = 50
    trust_label: str = "uncertain"  # verified | uncertain | risky
    trust_reasons: List[str] = []
    is_expired: bool = False
    
    # Clean display fields
    display_data: Optional[dict] = None  # {title, source_tag, company, summary, location}
    days_old: Optional[int] = None
    posted_at: Optional[str] = None
    
    # Clean display fields
    clean_company: Optional[str] = None
    clean_title: Optional[str] = None
    clean_snippet: Optional[str] = None

    # Posted pay range, e.g. "$150K – $250K". Real values only, never estimated.
    salary: Optional[str] = None

    # Calibrated match: a band a human can act on, plus why. `None` when the match
    # genuinely couldn't be assessed — never a fabricated placeholder score.
    match_band: Optional[str] = None          # strong | possible | stretch | unknown
    match_probability: Optional[float] = None
    match_explanation: Optional[str] = None

class RAGDoc(BaseModel):
    run_id: str
    role: str  # Primary role searched
    location: str
    depth: str
    companies: List[HiringCompany] = []
    total: int = 0
    pagination: Dict[str, Any] = {}  # Added for UI compatibility
    resume_insights: Dict[str, Any] = {}  # Resume insights extracted from uploaded resume
    resume_excerpt: str = ""  # First ~500 chars of resume text
    # New fields for "Load 5 more roles" feature
    searched_roles: List[str] = []  # List of all roles that have been searched
    total_roles_searched: int = 0  # Count of roles searched (max 20)
    has_more_roles: bool = True  # Whether more role variations are available

# --- Core Functions ---

async def discover_companies(
    role_name: str, 
    location: str, 
    depth: str,
    filters: Dict[str, Any] | None = None
) -> List[SearchCandidate]:
    """
    Discover job postings using targeted Tavily search on QUALITY job sites.
    
    Key improvements:
    1. Search quality job sites directly (Indeed, Glassdoor, Lever, Greenhouse)
    2. Filter out garbage titles BEFORE treating them as companies
    3. Use experience-aware queries when filters are provided
    """
    from urllib.parse import urlparse
    import re
    
    # Get role-optimized sites using smart hybrid approach
    # This returns 2-3 sites tailored to the specific role (e.g., AI Engineer -> YC Jobs, BuiltIn SF)
    role_optimized_sites = get_optimal_sites_for_role(role_name, max_sites=3)
    logger.info(f"🎯 Using role-optimized sites for '{role_name}': {role_optimized_sites}")
    
    # Quality job sites to search (fallback - now role-optimized)
    QUALITY_JOB_SITES = role_optimized_sites + [
        "lever.co",
        "greenhouse.io",
    ]
    
    # Garbage title patterns - skip these results entirely
    # Be conservative - only filter clear non-job content
    GARBAGE_TITLE_PATTERNS = [
        r"^i \d+ migliori",  # Italian product rankings
        r"download.*driver",  # Driver downloads
        r"hp.*support",  # HP support pages
        r"printer.*setup",  # Printer setup pages
        r"student.*login",  # Student portals
        r"top\s+\d+\s+best",  # "Top 10 best" (listicles)
        r"interview\s+questions",  # Interview prep pages
        r"resume\s+template",  # Resume templates
        r"how\s+to\s+become",  # "How to become a..." guides
        r"what\s+is\s+a\s+.*engineer",  # "What is a software engineer" explainers
    ]
    
    # Aggregator/Job Board domains to NEVER treat as hiring companies
    # These are job boards that list OTHER companies' jobs - they are not the employer
    AGGREGATOR_DOMAINS = [
        "indeed.com", "glassdoor.com", "linkedin.com", "ziprecruiter.com", 
        "simplyhired.com", "jooble.org", "adzuna.com", "hiringcafe.com",
        "dice.com", "careerbuilder.com", "monster.com",
        # BuiltIn family - job boards, NOT hiring companies
        "builtin.com", "builtinsf.com", "builtinnyc.com", "builtinla.com",
        "builtinaustin.com", "builtinboston.com", "builtinchicago.com",
        "builtincolorado.com", "builtinseattle.com",
        # Y Combinator job listings (we want the companies, not YC itself)
        "ycombinator.com", "workatastartup.com",
        # Wellfound is also an aggregator
        "wellfound.com", "angel.co",
    ]
    
    # Names that should NEVER be returned as company names
    INVALID_COMPANY_NAMES = [
        "built in", "builtin", "builtinsf", "builtinnyc", "builtinla",
        "ycombinator", "y combinator", "workatastartup", "wellfound",
        "indeed", "glassdoor", "linkedin", "ziprecruiter", "dice",
        "monster", "careerbuilder", "unknown", "unknown company",
        "angel.co", "angellist"
    ]

    def is_garbage_title(title: str) -> bool:
        """Check if a title is garbage (not a real job posting)."""
        if not title:
            return True
        title_lower = title.lower()
        for pattern in GARBAGE_TITLE_PATTERNS:
            if re.search(pattern, title_lower):
                return True
        return False
    
    def is_aggregator_url(url: str) -> bool:
        """Check if URL belongs to a known aggregator."""
        if not url: 
            return False
        url_lower = url.lower()
        return any(agg in url_lower for agg in AGGREGATOR_DOMAINS)
    
    def is_quality_job_url(url: str) -> bool:
        """Check if URL is from a quality ATS site (not an aggregator)."""
        if not url:
            return False
        url_lower = url.lower()
        # Only count ATS systems as quality (these have extractable company names)
        quality_ats = ["lever.co", "greenhouse.io", "ashbyhq.com", "workable.com", "smartrecruiters.com"]
        return any(site in url_lower for site in quality_ats)
    
    def extract_company_name(title: str, url: str) -> str:
        """Extract company name intelligently from title and URL."""
        if not title:
            return "Unknown Company"
        
        title_lower = title.lower()
        
        def is_valid_company_name(name: str) -> bool:
            """Check if extracted name is a valid company (not a job board)."""
            if not name or len(name) < 2:
                return False
            name_lower = name.lower().strip()
            # Reject job board names
            for invalid in INVALID_COMPANY_NAMES:
                if invalid in name_lower or name_lower in invalid:
                    return False
            return True
        
        # Pattern: "Role at Company" -> Company
        if " at " in title:
            parts = title.split(" at ")
            if len(parts) >= 2:
                company = parts[-1].split(" - ")[0].split("|")[0].strip()
                # Clean up common suffixes
                for suffix in ["Careers", "Jobs", "Hiring", "Job", "Career"]:
                    company = company.replace(suffix, "").strip()
                if is_valid_company_name(company):
                    return company
        
        # Pattern: "Company - Role" or "Company | Role"
        for sep in [" - ", " | ", " – "]:
            if sep in title:
                parts = title.split(sep)
                # First part is likely company if it doesn't contain role keywords
                candidate = parts[0].strip()
                role_words = ["engineer", "developer", "architect", "manager", "analyst", "designer", "scientist", "specialist"]
                if not any(rw in candidate.lower() for rw in role_words):
                    if is_valid_company_name(candidate):
                        return candidate
        
        # Try to extract from URL domain for ATS sites
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            
            # For ATS subdomains like "acme.greenhouse.io" or "acme.lever.co"
            if ".greenhouse.io" in domain or ".lever.co" in domain or ".ashbyhq.com" in domain:
                subdomain = domain.split(".")[0]
                if subdomain and subdomain not in ["jobs", "www", "boards", "careers", "apply"]:
                    candidate = subdomain.replace("-", " ").title()
                    if is_valid_company_name(candidate):
                        logger.debug(f"✅ Extracted company from ATS subdomain: {candidate}")
                        return candidate
            
            # For workable.com - company name is in path like workable.com/company-name/j/...
            elif "workable.com" in domain and "/j/" in path:
                path_parts = path.split("/")
                if len(path_parts) >= 2:
                    company_slug = path_parts[1]
                    if company_slug and company_slug not in ["j", "jobs", "apply"]:
                        candidate = company_slug.replace("-", " ").title()
                        if is_valid_company_name(candidate):
                            return candidate
            
            # For company career pages like "company.com/careers" - extract company from domain
            # But NOT for aggregator/job board sites
            elif domain and not any(agg in domain for agg in AGGREGATOR_DOMAINS):
                # Extract main domain (e.g., "careers.arm.com" -> "arm")
                domain_parts = domain.replace("www.", "").split(".")
                if len(domain_parts) >= 2:
                    main_part = domain_parts[-2]  # Second to last part
                    if main_part not in ["com", "io", "co", "ai", "dev", "org", "net"]:
                        candidate = main_part.replace("-", " ").title()
                        if is_valid_company_name(candidate):
                            return candidate
        except Exception as e:
            logger.debug(f"Failed to extract company from URL: {e}")
        
        # Last resort: If title looks like just a role (no company indicators), return Unknown
        # This prevents using the role name as company name
        role_indicators = ["engineer", "developer", "architect", "manager", "analyst", "scientist"]
        if any(indicator in title_lower for indicator in role_indicators) and " at " not in title_lower:
            return "Unknown Company"
        
        return "Unknown Company"
    
    # Build search query with experience-aware terms
    experience_range = filters.get("experience_range") if filters else None
    
    # Use generate_job_search_queries for better experience handling
    from .job_search import generate_job_search_queries
    
    if experience_range:
        # Use optimized query generation
        query_config = generate_job_search_queries(
            role_name=role_name,
            location=location,
            experience_range=experience_range,
            filters_json=filters
        )
        # Use primary query from optimized generation
        base_query = query_config["primary_query"]
        logger.info(f"🔍 Using experience-aware query: {base_query}")
    else:
        # Fallback to simple query if no experience filter
        location_clean = location.strip() if location else ""
        query_parts = [f'"{role_name}"']
        if location_clean:
            query_parts.append(f'"{location_clean}"')
        query_parts.append("jobs hiring apply")
        base_query = " ".join(query_parts)
    
    per_site_limit_map = {"quick": 3, "standard": 5, "deep": 8, "max": 10}
    per_site_limit = per_site_limit_map.get(depth, 5)

    hits_with_site: List[Tuple[str, SearchHit]] = []
    seen_urls: Set[str] = set()

    def record_hits(tag: str, hit_list: List[SearchHit]) -> None:
        for hit in hit_list:
            if not hit.url:
                logger.info(f"   ⚠️ Skipping hit with no URL")
                continue
            if hit.url in seen_urls:
                logger.info(f"   ⚠️ Skipping duplicate URL: {hit.url[:50]}")
                continue
            # CRITICAL: Skip garbage titles early (but log at INFO level for debugging)
            if is_garbage_title(hit.title):
                logger.info(f"   ⚠️ Skipping garbage title: {hit.title[:60]}")
                continue
            seen_urls.add(hit.url)
            hits_with_site.append((tag, hit))
            logger.info(f"   ✅ Recorded hit: {hit.title[:50]}...")

    # STRATEGY 1: Primary job search (most effective query format for Tavily)
    # Tavily doesn't support site: operators like Google, so use natural language
    primary_query = f'{role_name} jobs {location} hiring now apply'
    logger.info(f"🔍 Starting primary search: {primary_query}")
    try:
        primary_hits = await smart_search(primary_query, max_results=per_site_limit * 3)
        logger.info(f"🔍 Primary search returned {len(primary_hits)} raw hits")
        for hit in primary_hits:
            logger.info(f"   - Primary hit: {hit.title[:50]}... | {hit.url[:60]}...")
        record_hits("Primary", primary_hits)
        logger.info(f"🔍 After dedup, have {len(hits_with_site)} hits total")
    except Exception as e:
        logger.warning(f"🛰️ Primary search failed: {str(e)[:200]}")

    # STRATEGY 2: Company-focused search (finds companies hiring for this role)
    company_query = f'company hiring {role_name} {location}'
    if len(hits_with_site) < per_site_limit * 2:
        logger.info(f"🔍 Starting company search: {company_query}")
        try:
            company_hits = await smart_search(company_query, max_results=per_site_limit * 2)
            logger.info(f"🔍 Company search returned {len(company_hits)} raw hits")
            for hit in company_hits:
                logger.info(f"   - Company hit: {hit.title[:50]}... | {hit.url[:60]}...")
            record_hits("Company", company_hits)
            logger.info(f"🔍 After dedup, have {len(hits_with_site)} hits total")
        except Exception as e:
            logger.warning(f"🛰️ Company search failed: {str(e)[:200]}")

    # STRATEGY 3: Role-specific job boards (using role-optimized sites from config)
    if len(hits_with_site) < per_site_limit and role_optimized_sites:
        for site in role_optimized_sites[:2]:  # Only try top 2 sites
            site_clean = site.replace("/jobs", "").replace("jobs.", "")
            site_query = f'{role_name} {site_clean} jobs'
            logger.info(f"🔍 Starting site-specific search: {site_query}")
            try:
                site_hits = await smart_search(site_query, max_results=per_site_limit)
                logger.info(f"🔍 Site search ({site_clean}) returned {len(site_hits)} raw hits")
                for hit in site_hits:
                    logger.info(f"   - Site hit: {hit.title[:50]}... | {hit.url[:60]}...")
                record_hits(f"Site-{site_clean}", site_hits)
            except Exception as e:
                logger.warning(f"🛰️ Site search ({site_clean}) failed: {str(e)[:200]}")
    
    # STRATEGY 4: Exa fallback for ATS domains when Tavily results are thin
    async def exa_fallback_search() -> List[SearchHit]:
        try:
            from ..tools.exa_search import exa_search
        except Exception as e:
            logger.warning(f"🛰️ Exa import failed (skipping fallback): {e}")
            return []
        try:
            query = f'"{role_name}" "{location}" jobs'
            logger.info(f"🛰️ Exa fallback search: {query}")
            exa_results = await exa_search(
                query,
                include_domains=["lever.co", "greenhouse.io", "ashbyhq.com"],
                num_results=max(5, per_site_limit),
                want_highlights=True,
                want_text=False,
            )
            exa_hits: List[SearchHit] = []
            for res in exa_results:
                snippet = " ".join(res.get("highlights", []) or [])
                if not snippet:
                    snippet = res.get("text", "") or res.get("summary", "")
                exa_hits.append(
                    SearchHit(
                        url=res.get("url", ""),
                        title=res.get("title", ""),
                        snippet=snippet or "",
                        score=float(res.get("score", 0.0) or 0.0),
                    )
                )
            return exa_hits
        except Exception as e:
            logger.warning(f"🛰️ Exa fallback failed: {str(e)[:200]}")
            return []

    if len(hits_with_site) < max(3, per_site_limit // 2):
        exa_hits = await exa_fallback_search()
        if exa_hits:
            logger.info(f"🛰️ Exa fallback added {len(exa_hits)} hits")
            record_hits("Exa-ATS", exa_hits)

    logger.info(f"🔍 Final hit count after all strategies: {len(hits_with_site)}")

    if not hits_with_site:
        return []
    
    # === NEW APPROACH: Don't extract company from search titles ===
    # Only accept results from quality job sites and extract company from URL/subdomain
    # Company names from search titles like "Top AI Jobs in SF" are GARBAGE
    
    # Quality patterns for URLs we accept
    QUALITY_URL_PATTERNS = [
        'lever.co', 'greenhouse.io', 'ashbyhq.com', 'workday.com', 'myworkdayjobs.com',
        'smartrecruiters.com', 'icims.com', 'jobvite.com', 'workable.com', 'breezy.hr',
        'wellfound.com', 'ycombinator.com', 'workatastartup.com', 
        'builtinsf.com', 'builtinnyc.com', 'builtin.com'
    ]
    
    def is_quality_url(url: str) -> bool:
        """Check if URL is from a quality job site."""
        if not url:
            return False
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in QUALITY_URL_PATTERNS)
    
    def has_job_path(url: str) -> bool:
        """Check if URL has job-related path indicators."""
        if not url:
            return False
        path = urlparse(url).path.lower()
        job_indicators = ['/jobs/', '/careers/', '/job/', '/positions/', '/opening/', '/apply/', '/j/']
        return any(ind in path for ind in job_indicators)
    
    # Build candidates - ONLY from quality URLs, extract company from URL structure
    candidates = []
    for source_site, hit in hits_with_site:
        if not hit.url or not hit.url.startswith("http"):
            continue
        
        url = hit.url
        
        # Only accept quality job site URLs or URLs with job paths
        if not is_quality_url(url) and not has_job_path(url):
            logger.info(f"⏭️ Skipping non-job URL: {url[:60]}")
            continue
        
        # Extract company from URL structure ONLY (not from title)
        company_name, _ = extract_company_and_title_from_url(url)
        
        # If we can't extract company from URL, use placeholder
        # The actual company will be extracted later from the job posting itself
        if not company_name or company_name == "Unknown Company":
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower().replace("www.", "")
                # Use domain as placeholder - will be replaced during enrichment
                company_name = domain.split(".")[0].replace("-", " ").title()
            except:
                company_name = "Unknown Company"
        
        # Validate the extracted company name
        if not is_valid_company_name(company_name):
            logger.info(f"⏭️ Skipping invalid company from URL: {company_name} ({url[:50]})")
            continue
        
        # Extract homepage
        try:
            parsed = urlparse(url)
            homepage = f"{parsed.scheme}://{parsed.netloc}"
        except:
            homepage = url
        
        # Boost score for quality job sites
        score = hit.score
        if is_quality_url(url):
            score += 20.0
        
        logger.info(f"✅ Valid candidate from URL: {company_name} ({url[:50]})")
        candidates.append(SearchCandidate(
            name=company_name,
            homepage=homepage,
            source_url=url,
            snippet=hit.snippet or "",
            score=score,
            source_site=source_site
        ))
    
    logger.info(f"📊 Discovery produced {len(candidates)} candidates after filtering")
    return candidates

async def rerank_candidates(candidates: List[SearchCandidate], role_name: str, location: str, keywords: List[str], depth: str) -> List[SearchCandidate]:
    """
    Re-rank candidates using Voyage embeddings.
    """
    if not candidates:
        return []
        
    # Encode query
    query_text = f"{role_name} in {location} hiring for {', '.join(keywords)}"
    
    try:
        # Embed query
        query_vec = (await _embed([query_text]))[0]
        
        # Embed candidate snippets
        snippets = [f"{c.name}: {c.snippet}" for c in candidates]
        cand_vecs = await _embed(snippets)
        
        # Score
        for i, vec in enumerate(cand_vecs):
            sim = _cos(query_vec, vec)
            # Update score: blend with original search score (0-100)
            # Normalize sim (0-1) to 0-100
            semantic_score = sim * 100.0
            candidates[i].score = (candidates[i].score * 0.3) + (semantic_score * 0.7)
            
    except Exception as e:
        logger.warning(f"⚠️ Embedding re-rank failed: {e}. Using search scores.")
        # Fallback: keep original scores
        pass
        
    # Sort descending
    candidates.sort(key=lambda x: x.score, reverse=True)
    
    # Cut based on depth - target 8 for standard (efficiency optimization)
    cut_map = {"quick": 5, "standard": 8, "deep": 12, "max": 15}
    limit = cut_map.get(depth, 8)
    
    return candidates[:limit]

def _is_valid_job_posting(posting: JobPosting) -> bool:
    """
    Check if a job posting has minimum required fields to be considered valid.
    Very lenient - only requires title and URL.
    Location, company, source are all optional.
    """
    if not posting:
        return False
    try:
        # Minimum requirements: must have title and URL
        has_title = bool(getattr(posting, 'title', None))
        has_url = bool(getattr(posting, 'url', None))
        return has_title and has_url
    except Exception:
        return False


def _create_company_from_posting(
    posting: JobPosting,
    candidate: Optional[SearchCandidate] = None,
    location_hint: Optional[str] = None
) -> HiringCompany:
    """
    Create a HiringCompany from a JobPosting when we have a raw posting but no candidate.
    Very forgiving - uses whatever fields are available.
    """
    # Extract company name from posting if available, otherwise from candidate
    company_name = getattr(posting, 'company', None) or (candidate.name if candidate else "Unknown Company")
    
    # Extract URL - prefer posting URL, fallback to candidate homepage
    job_url = getattr(posting, 'url', None) or ""
    homepage_url = candidate.homepage if candidate else job_url
    
    # Extract location - optional, use "Not specified" if missing
    job_location = getattr(posting, 'location', None)
    if not job_location:
        job_location = location_hint if location_hint else "Not specified"
    
    # Extract source
    job_source = getattr(posting, 'source', None) or "direct"
    
    # Determine job type
    is_listing = getattr(posting, 'is_listing', False)
    is_ats = getattr(posting, 'is_ats', False)
    job_type = "job_board" if is_listing else ("direct" if is_ats else "discovered")
    
    # Extract score
    score = getattr(posting, 'score', 0.0) or (candidate.score if candidate else 0.0)
    
    return HiringCompany(
        company_name=company_name,
        homepage_url=homepage_url,
        job_title=getattr(posting, 'title', None),
        job_url=job_url,
        job_location=job_location,
        job_source=job_source,
        job_type=job_type,
        score=score,
        rank_score=score,  # Will be recomputed later
        blurb=getattr(posting, 'snippet', None) or (candidate.snippet if candidate else ""),
        job_posting=posting
    )


async def enrich_candidate_with_job_info(
    candidate: SearchCandidate, 
    role: str, 
    location: str,
    experience_range: Optional[str] = None
) -> HiringCompany:
    """
    Enrich a discovered candidate with job information.
    
    OPTIMIZATION: If candidate is already from a quality job site (Indeed, Greenhouse, etc.),
    use the discovery data directly WITHOUT doing another search. This saves API credits.
    """
    # Quality job sites - if discovery came from here, USE it directly
    QUALITY_JOB_SITES = [
        "indeed.com", "glassdoor.com", "lever.co", "greenhouse.io",
        "wellfound.com", "builtin.com", "ziprecruiter.com", "dice.com",
        "linkedin.com/jobs", "jobs.lever.co", "boards.greenhouse.io"
    ]
    
    def is_from_quality_site(url: str) -> bool:
        if not url:
            return False
        url_lower = url.lower()
        return any(site in url_lower for site in QUALITY_JOB_SITES)
    
    # OPTIMIZATION: If source URL is from a quality job site, check if it's a listing page
    # If it's a listing page (especially Indeed), extract individual job postings
    if is_from_quality_site(candidate.source_url):
        from .job_search import JobPosting, _looks_like_listing_page, _second_hop_from_listing
        from .match import smart_search
        
        # Check if this is a listing page
        is_listing = _looks_like_listing_page(candidate.source_url, candidate.name or "")
        
        if is_listing and "indeed.com" in candidate.source_url.lower():
            # Indeed listing page - extract individual job postings
            logger.debug(f"🔍 Indeed listing page detected, extracting individual jobs: {candidate.source_url[:60]}")
            
            try:
                # Strategy 1: Search for individual Indeed job postings (viewjob pages)
                # Indeed individual job URLs look like: indeed.com/viewjob?jk=...
                individual_query = f'"{role}" "{location}" site:indeed.com/viewjob'
                individual_hits = await smart_search(individual_query, max_results=3)
                
                if individual_hits:
                    # Use the first individual job posting found
                    best_hit = individual_hits[0]
                    
                    # Extract company name from the job posting title/snippet
                    # Pattern: "Software Architect at Company Name"
                    company_name = candidate.name  # Default to candidate name
                    title = role  # Default to role
                    
                    if " at " in best_hit.title:
                        parts = best_hit.title.split(" at ")
                        title = parts[0].strip()
                        company_name = parts[-1].split(" - ")[0].split("|")[0].strip()
                    elif " - " in best_hit.title:
                        parts = best_hit.title.split(" - ")
                        company_name = parts[0].strip()
                        title = parts[-1].split("|")[0].strip()
                    
                    # Extract location from snippet if available
                    job_location = location
                    if best_hit.snippet:
                        # Try to extract location from snippet
                        import re
                        loc_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})', best_hit.snippet)
                        if loc_match:
                            job_location = f"{loc_match.group(1)}, {loc_match.group(2)}"
                    
                    individual_posting = JobPosting(
                        url=best_hit.url,
                        title=title,
                        snippet=best_hit.snippet[:500] if best_hit.snippet else "",
                        location=job_location,
                        company=company_name,
                        source="Indeed",
                        is_ats=True,
                        is_listing=False,  # This is an individual job page
                        score=candidate.score + 20.0  # Boost for individual posting
                    )
                    
                    logger.debug(f"✅ Extracted individual Indeed job: {company_name} - {title}")
                    
                    return HiringCompany(
                        company_name=company_name,
                        homepage_url=candidate.homepage,
                        job_title=title,
                        job_url=best_hit.url,
                        job_location=job_location,
                        job_source="Indeed",
                        job_type="direct",
                        score=candidate.score + 20.0,
                        rank_score=candidate.score + 20.0,
                        blurb=best_hit.snippet[:500] if best_hit.snippet else candidate.snippet,
                        job_posting=individual_posting
                    )
                else:
                    # Strategy 2: Try second-hop extraction from listing page
                    logger.debug(f"⚠️ No individual jobs found via search, trying second-hop extraction")
                    row_dict = {
                        "url": candidate.source_url,
                        "title": candidate.name or role,
                        "summary": candidate.snippet or ""
                    }
                    role_terms = [t.lower() for t in role.split() if len(t) > 3]
                    detail_url, detail_title = await _second_hop_from_listing(row_dict, role_terms)
                    
                    if detail_url:
                        # Extract company from detail title
                        company_name = candidate.name
                        if " at " in (detail_title or ""):
                            company_name = detail_title.split(" at ")[-1].strip()
                        elif " - " in (detail_title or ""):
                            company_name = detail_title.split(" - ")[0].strip()
                        
                        detail_posting = JobPosting(
                            url=detail_url,
                            title=detail_title or role,
                            snippet=candidate.snippet[:500] if candidate.snippet else "",
                            location=location,
                            company=company_name,
                            source="Indeed",
                            is_ats=True,
                            is_listing=False,
                            score=candidate.score + 15.0
                        )
                        
                        return HiringCompany(
                            company_name=company_name,
                            homepage_url=candidate.homepage,
                            job_title=detail_title or role,
                            job_url=detail_url,
                            job_location=location,
                            job_source="Indeed",
                            job_type="direct",
                            score=candidate.score + 15.0,
                            rank_score=candidate.score + 15.0,
                            blurb=candidate.snippet,
                            job_posting=detail_posting
                        )
            except Exception as e:
                logger.warning(f"⚠️ Failed to extract individual jobs from Indeed listing: {e}")
                # Fall through to use listing page directly
        
        # Not a listing page, or extraction failed - use discovery result directly
        logger.debug(f"✅ Using discovery result directly (quality site): {candidate.source_url[:60]}")
        
        # Extract job title from the original search result title
        # Pattern: "Role at Company" -> Role
        title = candidate.snippet[:100] if candidate.snippet else role
        if " at " in candidate.name:
            # Candidate name is "Role at Company" format
            title = candidate.name.split(" at ")[0].strip()
        elif " - " in candidate.name:
            # Candidate name is "Role - Company" format
            title = candidate.name.split(" - ")[0].strip()
        else:
            # Use the role as title if we can't parse
            title = role
        
        # Create JobPosting directly from discovery
        direct_posting = JobPosting(
            url=candidate.source_url,
            title=title,
            snippet=candidate.snippet[:500] if candidate.snippet else "",
            location=location,  # Use search location
            company=candidate.name,
            source=candidate.source_site,
            is_ats=True,  # It's from a job site
            is_listing=is_listing,
            score=candidate.score
        )
        
        return HiringCompany(
            company_name=candidate.name,
            homepage_url=candidate.homepage,
            job_title=title,
            job_url=candidate.source_url,
            job_location=location,
            job_source=candidate.source_site,
            job_type="direct" if not is_listing else "job_board",
            score=candidate.score + 15.0,  # Boost for having direct job
            rank_score=candidate.score + 15.0,
            blurb=candidate.snippet,
            job_posting=direct_posting
        )
    
    # NOT from quality site - do enrichment search
    # Start with base HiringCompany from discovery
    base_company = HiringCompany(
        company_name=candidate.name,
        homepage_url=candidate.homepage,
        job_title=None,
        job_url=None,
        job_location=None,  # Will be set if available, but optional
        job_source=None,
        job_type="discovered",
        score=candidate.score,
        rank_score=candidate.score,  # Start with discovery score
        blurb=candidate.snippet,
        job_posting=None  # Will be set if job found
    )
    
    # Try to enrich with job information (best-effort, don't fail if this doesn't work)
    try:
        # Validate company name before making expensive API calls
        if not is_valid_company_name(candidate.name):
            print(f"    ⏭️ Skipping job search for invalid company: {candidate.name}")
            return base_company  # Return base company without job enrichment
        
        # Parse location preference
        loc_pref = parse_location(location)
        
        # Convert SearchCandidate to CompanyIntel object expected by check_job_availability
        company_obj = CompanyIntel(
            name=candidate.name,
            homepage=candidate.homepage,
            source_url=candidate.source_url,
            blurb=candidate.snippet,
            city=location,
            score=candidate.score
        )
        
        # Check jobs (always uses Tavily via check_job_availability)
        # This is optional - if it returns None or raises, we still keep the company
        # Now returns up to 5 job postings (list or single)
        posting_result = await check_job_availability(
            company_obj, 
            role, 
            location_pref=loc_pref, 
            max_results_per_company=5,
            experience_range=experience_range
        )
        
        # Handle both single JobPosting and List[JobPosting] results
        postings = []
        if posting_result:
            if isinstance(posting_result, list):
                postings = [p for p in posting_result if _is_valid_job_posting(p)]
            elif _is_valid_job_posting(posting_result):
                postings = [posting_result]
        
        # Use the first (best) posting for this company
        # If we have multiple postings, we could create multiple company entries, but for now use the best one
        if postings:
            posting = postings[0]  # Use the best one (first in sorted list)
            # Attach job posting as enrichment (safe - posting is already validated)
            try:
                base_company.job_posting = posting
            except Exception as e:
                logger.warning(
                    f"Failed to attach job_posting for {candidate.name} "
                    f"(posting title: {getattr(posting, 'title', 'N/A')}, "
                    f"posting url: {getattr(posting, 'url', 'N/A')}): {e}"
                )
            
            # Populate legacy fields with robust per-field error handling
            # Each field assignment is independent - one failure doesn't stop others
            
            # job_title: Use posting.title, fallback to None (already set)
            try:
                if hasattr(posting, 'title') and posting.title:
                    base_company.job_title = str(posting.title).strip()
            except Exception as e:
                logger.warning(
                    f"Failed to extract job_title for {candidate.name} "
                    f"(posting url: {getattr(posting, 'url', 'N/A')}): {e}"
                )
                # Keep default None
            
            # job_url: Use posting.url, fallback to None (already set)
            try:
                if hasattr(posting, 'url') and posting.url:
                    base_company.job_url = str(posting.url).strip()
            except Exception as e:
                logger.warning(
                    f"Failed to extract job_url for {candidate.name} "
                    f"(posting title: {getattr(posting, 'title', 'N/A')}): {e}"
                )
                # Keep default None
            
            # job_location: Use posting.location field directly (now a proper field, not a property)
            # LOCATION IS OPTIONAL - if missing, we still keep the posting
            try:
                # posting.location is now a proper field that defaults to None
                extracted_location = getattr(posting, 'location', None)
                
                # If not set, try the extract_location() helper method
                if not extracted_location and hasattr(posting, 'extract_location'):
                    try:
                        extracted_location = posting.extract_location()
                    except Exception:
                        extracted_location = None
                
                if extracted_location:
                    base_company.job_location = str(extracted_location).strip()
                else:
                    # Location is optional - use search location as hint, but don't require it
                    # Set to "Not specified" if we can't find it anywhere
                    base_company.job_location = location if location else "Not specified"
            except Exception as e:
                logger.debug(
                    f"Location extraction failed for {candidate.name} "
                    f"(posting title: {getattr(posting, 'title', 'N/A')}): {e}"
                )
                # Location is optional - set to search location or "Not specified"
                base_company.job_location = location if location else "Not specified"
            
            # job_source: Use posting.source field (now a proper field)
            try:
                # posting.source is now a proper field that defaults to None
                source = posting.source
                base_company.job_source = str(source).strip() if source else "direct"
            except Exception as e:
                logger.warning(
                    f"Failed to extract job_source for {candidate.name} "
                    f"(posting title: {getattr(posting, 'title', 'N/A')}): {e}"
                )
                base_company.job_source = "direct"
            
            # company_name: Update from posting.company if available and valid
            # This corrects any errors from initial discovery extraction
            try:
                posting_company = getattr(posting, 'company', None)
                if posting_company and posting_company.strip():
                    posting_company = posting_company.strip()
                    # Only update if it's not "Unknown Company" and not the role name
                    role_lower = role.lower()
                    if (posting_company.lower() != "unknown company" and 
                        posting_company.lower() != role_lower and
                        len(posting_company) > 2):
                        base_company.company_name = posting_company
                        logger.debug(
                            f"Updated company_name from posting: {candidate.name} -> {posting_company}"
                        )
            except Exception as e:
                logger.debug(
                    f"Failed to update company_name from posting for {candidate.name}: {e}"
                )
                # Keep original candidate.name
            
            # Also capture is_listing status if available (for debugging/analytics)
            try:
                if hasattr(posting, 'is_listing') and posting.is_listing:
                    # Mark as job_board type if it's a listing page
                    base_company.job_type = "job_board"
            except Exception:
                pass  # Non-critical, ignore errors
            
            # job_type: Mark as "direct" since we found a job posting
            base_company.job_type = "direct"
            
    except Exception as e:
        # Job enrichment failed - that's okay, we still return the discovered company
        logger.warning(f"Job enrichment failed for {candidate.name}: {e}")
        # Company is still valid - job_posting remains None
    
    return base_company

def compute_rank_score(company: HiringCompany, role: str, requested_location: str) -> float:
    """
    Compute a rank_score for a company based on discovery score and enrichment boosts.
    Higher score = better match.
    """
    # Start with discovery score
    rank_score = company.score
    
    # Boost: Has job posting (+10)
    job_posting = getattr(company, 'job_posting', None)
    if job_posting is not None:
        rank_score += 10.0
    
    # Boost: Role alignment in title (+5)
    role_lower = role.lower()
    company_name_lower = (company.company_name or "").lower()
    job_title_lower = (company.job_title or "").lower()
    
    # Check if role keywords appear in company name or job title
    role_keywords = role_lower.split()
    for keyword in role_keywords:
        if len(keyword) > 3:  # Skip short words like "AI"
            if keyword in company_name_lower or keyword in job_title_lower:
                rank_score += 5.0
                break  # Only boost once
    
    # Boost: Location match (+3) - OPTIONAL, doesn't penalize if missing
    if requested_location:
        req_loc_lower = requested_location.lower()
        # Safely get location - handle None, empty string, or "Not specified"
        job_loc = getattr(company, 'job_location', None)
        job_loc_lower = (job_loc or "").lower() if job_loc and job_loc != "Not specified" else ""
        blurb_lower = (company.blurb or "").lower()
        
        # Simple location matching - only boost if location is present and matches
        if job_loc_lower and (req_loc_lower in job_loc_lower or req_loc_lower in blurb_lower):
            rank_score += 3.0
        # Note: We don't penalize if location is missing - it's optional
    
    return rank_score

def apply_light_filtering(companies: List[HiringCompany]) -> List[HiringCompany]:
    """
    Apply light, defensive filters to remove obviously junk content.
    Does NOT filter based on job_posting presence, location, or other optional fields.
    Very forgiving - only drops clearly non-job content.
    """
    # Blocklisted domains/keywords for obviously non-job content
    blocklisted_domains = [
        "wikipedia.org",
        "tiktok.com",
        "youtube.com",
        "facebook.com",
        "twitter.com",
        "instagram.com",
        "reddit.com"
    ]
    
    blocklisted_keywords = [
        "exam",
        "syllabus",
        "admit card",
        "result",
        "seating arrangement",
        "what is",
        "how to",
        "tutorial",
        "course",
        ".pdf"
    ]
    
    filtered = []
    dropped_count = 0
    dropped_reasons = []
    
    for company in companies:
        drop_reason = None
        
        # Skip if homepage is in blocklist
        homepage_lower = (company.homepage_url or "").lower()
        if any(blocked in homepage_lower for blocked in blocklisted_domains):
            drop_reason = f"blocklisted domain: {homepage_lower}"
        
        # Skip if company name or blurb contains blocklisted keywords
        if not drop_reason:
            name_lower = (company.company_name or "").lower()
            blurb_lower = (company.blurb or "").lower()
            
            for keyword in blocklisted_keywords:
                if keyword in name_lower or keyword in blurb_lower:
                    drop_reason = f"blocklisted keyword: {keyword}"
                    break
        
        # Skip if URL ends with .pdf
        if not drop_reason and homepage_lower.endswith(".pdf"):
            drop_reason = "PDF file"
        
        if drop_reason:
            dropped_count += 1
            dropped_reasons.append(f"{company.company_name}: {drop_reason}")
            continue
        
        # Keep the company - location, job_posting, etc. are all optional
        filtered.append(company)
    
    if dropped_count > 0:
        logger.info(
            f"Filtered out {dropped_count} companies (obviously non-job content). "
            f"Kept {len(filtered)} companies."
        )
        if logger.isEnabledFor(logging.DEBUG):
            for reason in dropped_reasons[:5]:  # Log first 5 reasons
                logger.debug(f"  Dropped: {reason}")
    
    return filtered


def _deduplicate_companies(
    existing_companies: List[Dict[str, Any]], 
    new_companies: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Deduplicate companies by company name and homepage URL.
    
    Args:
        existing_companies: List of existing company dicts
        new_companies: List of new company dicts to merge
    
    Returns:
        Tuple of (merged_companies, added_count, duplicate_count)
    """
    # Build set of existing company identifiers for fast lookup
    existing_ids: Set[str] = set()
    
    for c in existing_companies:
        company_name = c.get("company_name", "").lower().strip()
        homepage = c.get("homepage_url", "").lower().strip().rstrip("/")
        
        if company_name and company_name != "unknown company":
            existing_ids.add(company_name)
        if homepage:
            # Also add normalized domain for better matching
            existing_ids.add(homepage)
            # Extract domain without protocol for fuzzy matching
            domain = homepage.replace("https://", "").replace("http://", "").replace("www.", "")
            existing_ids.add(domain)
    
    # Merge new companies, skipping duplicates
    merged = existing_companies.copy()
    added_count = 0
    duplicate_count = 0
    
    for new_c in new_companies:
        company_name = new_c.get("company_name", "").lower().strip()
        homepage = new_c.get("homepage_url", "").lower().strip().rstrip("/")
        homepage_domain = homepage.replace("https://", "").replace("http://", "").replace("www.", "")
        
        # Check if this is a duplicate
        is_duplicate = False
        if company_name and company_name != "unknown company" and company_name in existing_ids:
            is_duplicate = True
        elif homepage in existing_ids:
            is_duplicate = True
        elif homepage_domain in existing_ids:
            is_duplicate = True
        
        if is_duplicate:
            duplicate_count += 1
            continue
        
        # Add new company
        merged.append(new_c)
        added_count += 1
        
        # Update tracking sets
        if company_name and company_name != "unknown company":
            existing_ids.add(company_name)
        if homepage:
            existing_ids.add(homepage)
            existing_ids.add(homepage_domain)
    
    return merged, added_count, duplicate_count


# --- Direct Role Search (Phase 0) ---

async def direct_role_search(role: str, location: str, min_results: int = 5, max_results: int = 15) -> List[HiringCompany]:
    """
    FAST search with LOCATION FILTERING and CACHING:
    1. Check Redis cache first
    2. Search ATS platforms with location in query
    3. Filter results that match user's location
    4. Include Remote jobs as fallback
    5. Cache results for 30 minutes
    """
    from .job_search import extract_company_from_ats_url
    from urllib.parse import urlparse
    
    # === CHECK CACHE FIRST ===
    cached_results = get_cached_search_results(role, location)
    if cached_results:
        print(f"⚡ Cache HIT for '{role}' in '{location}' - {len(cached_results)} results")
        # Convert cached dicts back to HiringCompany objects
        return [HiringCompany(**r) if isinstance(r, dict) else r for r in cached_results[:max_results]]
    
    print(f"🔍 Cache MISS for '{role}' in '{location}' - searching...")
    
    results: List[dict] = []
    seen_urls: Set[str] = set()
    seen_companies: Set[str] = set()
    
    # Parse location for matching
    location_clean = location.strip().lower() if location else ""
    
    # Extract city and state for flexible matching
    location_parts = []
    if location_clean:
        # Handle "Austin, TX" or "Austin" or "TX"
        parts = [p.strip() for p in location_clean.replace(',', ' ').split()]
        location_parts = [p for p in parts if len(p) >= 2]
    
    # State abbreviations to full names
    STATE_MAP = {
        'tx': 'texas', 'ca': 'california', 'ny': 'new york', 'wa': 'washington',
        'ma': 'massachusetts', 'il': 'illinois', 'co': 'colorado', 'ga': 'georgia',
        'fl': 'florida', 'pa': 'pennsylvania', 'oh': 'ohio', 'nc': 'north carolina',
        'az': 'arizona', 'or': 'oregon', 'va': 'virginia', 'md': 'maryland',
        'nj': 'new jersey', 'ut': 'utah', 'mn': 'minnesota', 'tn': 'tennessee',
    }
    
    # Expand location parts with state full names
    expanded_location_parts = list(location_parts)
    for part in location_parts:
        if part in STATE_MAP:
            expanded_location_parts.append(STATE_MAP[part])
    
    def matches_location(text: str, is_remote_query: bool = False) -> tuple:
        """
        Check if text matches user's location.
        Returns (is_local_match, is_remote)
        """
        if not text:
            return False, False
        
        text_lower = text.lower()
        
        # Check for remote
        is_remote = any(term in text_lower for term in ['remote', 'work from home', 'wfh', 'anywhere'])

        if is_remote_query:
            return False, is_remote
        
        # Check for location match
        if not location_parts:
            return True, is_remote  # No location filter
        
        # Check if any location part matches
        is_local = any(part in text_lower for part in expanded_location_parts)
        
        return is_local, is_remote
    
    # === PHASE 1: ATS SEARCH WITH LOCATION ===
    print(f"🚀 Fast parallel search for '{role}' in '{location}'...")
    
    # Build queries WITH location
    ats_queries = [
        f'site:lever.co "{role}" "{location}" jobs',
        f'site:greenhouse.io "{role}" "{location}" jobs',
        f'site:ashbyhq.com "{role}" "{location}" jobs',
    ]
    
    # Also search for remote jobs as backup
    remote_queries = [
        f'site:lever.co "{role}" remote jobs',
        f'site:greenhouse.io "{role}" remote jobs',
    ]
    
    async def search_and_filter(query: str, is_remote_query: bool = False) -> List[dict]:
        """Search ATS platforms and filter by location."""
        hits = []
        try:
            raw_hits = await smart_search(query, max_results=8)
            print(f"    📥 Got {len(raw_hits)} raw hits from: {query[:50]}...")
            
            for hit in raw_hits:
                url = hit.url
                if not url or url in seen_urls:
                    continue
                
                # SKIP: Non-ATS URLs (Tavily sometimes returns wrong sites like StackOverflow)
                url_lower = url.lower()
                is_ats_url = any(ats in url_lower for ats in [
                    'lever.co', 'greenhouse.io', 'ashbyhq.com', 'ashby.com',
                    'workday.com', 'myworkdayjobs.com', 'workable.com',
                    'icims.com', 'jobvite.com', 'bamboohr.com', 'jazz.co'
                ])
                if not is_ats_url:
                    print(f"    ⏭️ Skipping non-ATS URL: {url[:50]}...")
                    continue
                
                # SKIP: Listing pages instead of job postings
                if is_job_listing_page(url, hit.title or ""):
                    print(f"    ⏭️ Skipping listing page: {hit.title[:30] if hit.title else url[:30]}...")
                    continue
                
                # === USE EXTRACTION LADDER (heuristics → LLM → fallback) ===
                extracted = await extract_job_entities_cached(url, hit.title or "", hit.snippet or "")
                company = extracted.get("company", "")
                job_title = extracted.get("title", "") or role
                extraction_method = extracted.get("extraction_method", "unknown")
                
                # Log extraction method for debugging
                if extraction_method == "llm":
                    print(f"    🤖 LLM extracted: {company} - {job_title[:30]}...")
                elif extraction_method == "heuristic_fallback":
                    print(f"    ⚠️ Heuristic fallback (needs review): {company}")
                elif extraction_method == "heuristic":
                    print(f"    📋 Heuristic: {company} - {job_title[:30]}...")
                
                # Final sanity check on title - detect garbage that slipped through
                title_lower = job_title.lower().strip()
                is_garbage_title = (
                    title_lower in ['jobs', 'careers', 'job', 'apply', 'unknown', 'job opening'] or
                    re.match(r'^(software|inc|llc|corp|corporation|ltd|limited|co|company)[\.,\s]*$', title_lower) or
                    re.match(r'^[\w\s]+,\s*(inc|llc|corp|ltd)\.?$', title_lower) or  # "Something, Inc."
                    len(title_lower) < 5 or
                    not any(kw in title_lower for kw in ['engineer', 'developer', 'analyst', 'manager', 'designer', 
                                                          'lead', 'senior', 'staff', 'director', 'scientist', 
                                                          'specialist', 'coordinator', 'associate', 'intern',
                                                          'product', 'data', 'software', 'marketing', 'sales'])
                )
                
                if is_garbage_title:
                    print(f"    ⚠️ Garbage title detected: '{job_title}' - using searched role: {role}")
                    job_title = role

                # Skip invalid companies
                if not company or company == "Unknown Company":
                    print(f"    ⏭️ No company extracted from: {url[:50]}...")
                    continue
                if not is_valid_company_name(company):
                    print(f"    ⏭️ Invalid company name: {company}")
                    continue
                
                # Skip duplicates
                company_key = company.lower().strip()
                if company_key in seen_companies:
                    continue
                
                # Check location match
                text_to_check = f"{hit.title} {hit.snippet}"
                is_local, is_remote = matches_location(text_to_check, is_remote_query=is_remote_query)
                
                if not is_local and not is_remote:
                    print(f"    ⏭️ Skipping (wrong location): {company}")
                    continue
                
                seen_urls.add(url)
                seen_companies.add(company_key)
                
                # Score with location boost
                score = hit.score
                if is_local:
                    score += 30
                    tag = "📍 Local"
                else:
                    score += 10
                    tag = "🌐 Remote"
                
                # Include the searched location for display
                job_location = location if is_local else "Remote"
                
                # Use LLM description if available
                description = extracted.get("description", "")
                extraction_method = extracted.get("extraction_method", "unknown")
                
                # If description is garbage or empty, generate a sensible one
                if not description or 'click to view' in description.lower() or len(description) < 20:
                    # Generate professional description from title
                    description = f"Seeking a {job_title} to join the team"
                    if is_remote:
                        description += " (Remote position)"

                hits.append({
                    'url': url,
                    'title': job_title,
                    'company': company,
                    'snippet': description,
                    'score': score,
                    'source': 'ats_direct',
                    'is_local': is_local,
                    'is_remote': is_remote,
                    'job_location': job_location,
                    'is_pre_cleaned': True,  # Flag to skip format_job_for_display re-processing
                    'extraction_method': extraction_method,
                })
                print(f"    ✅ {tag}: {company} - {job_title[:40]}...")
                
        except Exception as e:
            import traceback
            print(f"    ⚠️ Search error: {e}")
            traceback.print_exc()
        return hits
    
    # Run location-specific searches first (in parallel)
    print(f"🎯 Searching with location filter: {location}")
    location_results = await asyncio.gather(*[search_and_filter(q, False) for q in ats_queries])
    
    for hits in location_results:
        results.extend(hits)
    
    local_count = sum(1 for r in results if r.get('is_local'))
    remote_count = sum(1 for r in results if r.get('is_remote'))
    print(f"📊 Location search: {local_count} local, {remote_count} remote")
    
    # === PHASE 2: REMOTE FALLBACK (only if not enough results) ===
    if len(results) >= min_results:
        print(f"✅ Found {len(results)} results, skipping remote search")
    else:
        print(f"🌐 Adding remote jobs (need {min_results - len(results)} more)...")
        remote_results = await asyncio.gather(*[search_and_filter(q, True) for q in remote_queries])
        
        for hits in remote_results:
            results.extend(hits)
    
    # === PHASE 3: SORT AND DEDUPLICATE ===
    # Sort by: local first, then remote, then by score
    def sort_key(r):
        is_local = 2 if r.get('is_local') else 0
        is_remote = 1 if r.get('is_remote') else 0
        return (is_local, is_remote, r.get('score', 0))
    
    results.sort(key=sort_key, reverse=True)
    
    # Final dedup by company
    final_results = []
    final_companies = set()
    for r in results:
        company_key = r.get('company', '').lower()
        if company_key not in final_companies:
            final_companies.add(company_key)
            final_results.append(r)
    
    # Stats
    final_local = sum(1 for r in final_results if r.get('is_local'))
    final_remote = sum(1 for r in final_results if r.get('is_remote'))
    print(f"📊 Final results: {len(final_results)} total ({final_local} local, {final_remote} remote)")
    
    # === PHASE 4: Convert to HiringCompany objects with clean display ===
    hiring_companies: List[HiringCompany] = []
    
    # === STEP 0: Validate job URLs exist (batch check) ===
    print(f"🔍 Validating {min(len(final_results), max_results)} job URLs...")
    urls_to_check = [r.get('url', '') for r in final_results[:max_results]]
    validation_tasks = [validate_job_url(url, timeout=3.0) for url in urls_to_check]
    validation_results = await asyncio.gather(*validation_tasks)
    
    # Create lookup of valid URLs, plus any salary extracted during validation
    valid_urls = set()
    salary_by_url: Dict[str, str] = {}
    for url, result in zip(urls_to_check, validation_results):
        if result.get('exists', True):
            valid_urls.add(url)
            if result.get('salary'):
                salary_by_url[url] = result['salary']
        else:
            print(f"    ❌ Job no longer exists: {url[:60]}... ({result.get('reason', 'unknown')})")
    
    print(f"✅ {len(valid_urls)}/{len(urls_to_check)} jobs validated as active")
    
    for r in final_results[:max_results]:
        # Skip jobs that failed URL validation
        job_url = r.get('url', '')
        if job_url not in valid_urls:
            continue
        
        # === STEP 1: Format for display FIRST ===
        formatted = format_job_for_display(r, role)
        display = formatted.get('display', {})
        
        # Get cleaned values
        clean_title = display.get('title', role)
        clean_company = display.get('company', 'Unknown Company')
        clean_summary = display.get('summary', '')
        clean_location = display.get('location', location)
        source_tag = display.get('source_tag', 'Job Board')
        
        # === STEP 2: Skip ATS platform names ===
        if is_ats_platform(clean_company) or clean_company.startswith('Company via'):
            # Still couldn't extract real company - skip this result
            print(f"    ⏭️ Skipping (no real company): {clean_title[:40]}...")
            continue
        
        # === STEP 3: Build homepage URL ===
        try:
            parsed = urlparse(r['url'])
            homepage = f"{parsed.scheme}://{parsed.netloc}"
        except:
            homepage = r.get('url', '')
        
        # === STEP 3.5: Salary — authoritative JSON-LD from validation, else snippet ===
        from ..tools.salary import extract_salary_from_text
        salary = salary_by_url.get(job_url) or extract_salary_from_text(clean_summary) or extract_salary_from_text(r.get('snippet'))

        # === STEP 4: Create JobPosting ===
        job_posting = JobPosting(
            url=r['url'],
            title=clean_title,
            snippet=clean_summary[:500] if clean_summary else "",
            location=clean_location,
            company=clean_company,
            source=source_tag,
            is_ats=True,
            is_listing=False,
            score=r.get('score', 0),
            salary=salary,
        )

        # === STEP 5: Create HiringCompany with CLEAN values ===
        hiring_company = HiringCompany(
            company_name=clean_company,      # CLEAN company
            homepage_url=homepage,
            job_title=clean_title,           # CLEAN title
            job_url=r['url'],
            job_location=clean_location,     # CLEAN location
            job_source=source_tag,
            job_type="direct",
            score=r.get('score', 0),
            rank_score=r.get('score', 0),
            blurb=clean_summary,             # CLEAN summary
            job_posting=job_posting,
            clean_company=clean_company,
            clean_title=clean_title,
            clean_snippet=clean_summary,
            salary=salary,
            display_data=display             # Full display data
        )
        
        # === STEP 6: Trust scoring ===
        company_dict = hiring_company.model_dump()
        enhanced = enhance_job_data(company_dict)
        
        # Skip expired jobs
        if enhanced.get('is_expired'):
            print(f"    ⏭️ Skipping expired: {clean_company} - {clean_title[:30]}...")
            continue
        
        # Skip low trust
        if enhanced.get('trust_score', 50) < 30:
            print(f"    ⏭️ Skipping low trust ({enhanced.get('trust_score')}): {clean_company}")
            continue
        
        # Update trust fields
        hiring_company.trust_score = enhanced.get('trust_score', 50)
        hiring_company.trust_label = enhanced.get('trust_label', 'uncertain')
        hiring_company.trust_reasons = enhanced.get('trust_reasons', [])
        hiring_company.is_expired = enhanced.get('is_expired', False)
        
        hiring_companies.append(hiring_company)
        print(f"    ✅ Trust {hiring_company.trust_score}: {clean_company} - {clean_title[:35]}...")
    
    # === CACHE RESULTS ===
    if hiring_companies:
        cache_search_results(role, location, [c.model_dump() for c in hiring_companies], ttl_seconds=1800)
        print(f"💾 Cached {len(hiring_companies)} results for '{role}' in '{location}'")
    
    return hiring_companies


# --- Main Orchestrator ---

async def _fetch_job_descriptions(companies: List[HiringCompany], max_fetch: int = 10) -> List[str]:
    """Real job-description text for each company, in the same order.

    Matching and gap analysis are only as good as the text they read. The search
    snippet is a title plus a salary line, so we pull the actual posting (the
    fetcher already tries free tiers — JSON-LD, meta tags, ATS parsers — before
    spending anything). Any failure falls back to the snippet, so a slow or dead
    page degrades that one score instead of breaking the run.
    """
    from ..tools.job_description_fetcher import fetch_job_description

    def snippet_of(c: HiringCompany) -> str:
        jp = c.job_posting
        return f"{jp.title or ''} {jp.snippet or ''}".strip()

    async def one(c: HiringCompany) -> str:
        url = c.job_url or (c.job_posting.url if c.job_posting else "")
        fallback = snippet_of(c)
        if not url:
            return fallback
        try:
            text = await asyncio.wait_for(
                fetch_job_description(url, snippet=c.job_posting.snippet), timeout=20.0
            )
            # Keep the title in the text — it carries the role signal
            return f"{c.job_posting.title or ''}\n{text}".strip() if text else fallback
        except Exception as e:
            print(f"    ⚠️ JD fetch failed for {c.company_name}: {str(e)[:60]}")
            return fallback

    head, tail = companies[:max_fetch], companies[max_fetch:]
    fetched = await asyncio.gather(*[one(c) for c in head], return_exceptions=False)
    return list(fetched) + [snippet_of(c) for c in tail]


async def run_rag_company_search(
    run_id: str,
    city: str,
    role: str,
    resume_token: str | None, 
    emit: Any, # Callable[[TimelineEvent], Awaitable[None]]
    multi_role: bool = True,
    depth: str = "standard",
    filters: Dict[str, Any] | None = None,
    offset: int = 0,
    limit: int = 5,
    memory_store: Any = None,
    additional_roles: List[str] | None = None  # NEW: Additional roles to search (for "Load 5 more" feature)
) -> Dict[str, Any]:
    """
    Orchestrates the RAG job search pipeline with caching and pagination.
    
    NEW: Supports additional_roles parameter for "Load 5 more roles" feature.
    When additional_roles is provided:
    1. Loads existing RAGDoc from cache
    2. Searches for each additional role
    3. Merges results (deduplicates by company name/homepage)
    4. Updates searched_roles and total_roles_searched
    """
    # FIRST LINE - must print immediately to confirm function is called
    print(f"🚀 run_rag_company_search STARTED: run_id={run_id}, role={role}, city={city}", flush=True)
    
    try:
        mem = memory_store if memory_store else Memory()
        doc_key = f"ragdoc:{run_id}"
        
        # 1. Try to load from cache
        cached_data = mem.get(doc_key)
        
        rag_doc = None
        rag_doc_dict = None

        # Resume insights (resume-first workflow)
        resume_insights: Dict[str, Any] = {}
        resume_excerpt: str = ""
        resume_text: str = ""
        if resume_token:
            try:
                resume_insights = extract_resume_insights(resume_token) or {}
                resume_text = get_resume_text(resume_token) or ""
                resume_excerpt = resume_text[:500] if resume_text else ""
            except Exception as e:
                logger.warning(f"⚠️ Failed to extract resume insights early: {e}")
        if cached_data:
            # If cached data is a dict (from storage), use it directly and ensure intel structure
            if isinstance(cached_data, dict):
                rag_doc_dict = cached_data.copy()  # Make a copy to avoid mutating original
                # Ensure intel structure exists in cached companies
                for company_dict in rag_doc_dict.get("companies", []):
                    if "intel" not in company_dict:
                        company_dict["intel"] = {}
                    if "focused_research" not in company_dict.get("intel", {}):
                        company_dict["intel"]["focused_research"] = {}
                # Try to convert to RAGDoc for validation (but we'll use dict for return)
                try:
                    rag_doc = RAGDoc(**rag_doc_dict)
                except:
                    pass # Invalid cache, re-run
            elif isinstance(cached_data, RAGDoc):
                rag_doc = cached_data
                rag_doc_dict = cached_data.model_dump()
                # Ensure intel structure exists
                for company_dict in rag_doc_dict.get("companies", []):
                    if "intel" not in company_dict:
                        company_dict["intel"] = {}
                    if "focused_research" not in company_dict.get("intel", {}):
                        company_dict["intel"]["focused_research"] = {}
                
        logger.info(f"🔍 run_rag_company_search: cached_data={bool(cached_data)}, rag_doc_dict={bool(rag_doc_dict)}, additional_roles={additional_roles}")
                
        if rag_doc_dict:
            # Check if we have additional_roles to search
            logger.info(f"📋 Cache found: {len(rag_doc_dict.get('companies', []))} companies, additional_roles={additional_roles}")
            
            if additional_roles and len(additional_roles) > 0:
                # "Load 5 more roles" mode - search additional roles and merge results
                logger.info(f"🔄 ENTERING additional_roles processing for {len(additional_roles)} roles")
                await emit(TimelineEvent(
                    run_id=run_id, 
                    agent="RAG", 
                    message=f"🔄 Loading {len(additional_roles)} additional role variations..."
                ))
                
                # Get existing companies and searched roles
                existing_companies = rag_doc_dict.get("companies", [])
                existing_searched_roles = rag_doc_dict.get("searched_roles", [role])
                
                # Search each additional role and collect new companies
                new_companies = []
                filters_dict = filters.model_dump() if hasattr(filters, 'model_dump') else (filters if filters else None)
                
                logger.info(f"🔄 Starting search for {len(additional_roles)} additional roles: {additional_roles}")
                
                for additional_role in additional_roles:
                    if additional_role.lower() in [r.lower() for r in existing_searched_roles]:
                        continue  # Skip already searched roles
                    
                    await emit(TimelineEvent(
                        run_id=run_id, 
                        agent="RAG", 
                        message=f"🔍 Searching for: {additional_role}..."
                    ))
                    
                    try:
                        # Discover companies for this role variation
                        role_candidates = await discover_companies(additional_role, city, depth, filters=filters_dict)
                        
                        if role_candidates:
                            await emit(TimelineEvent(
                                run_id=run_id, 
                                agent="RAG", 
                                message=f"📊 Found {len(role_candidates)} candidates for {additional_role}"
                            ))
                            
                            # Re-rank candidates
                            prof = role_profile(additional_role)
                            top_candidates = await rerank_candidates(role_candidates, additional_role, city, prof.get("keywords", []), depth)
                            
                            logger.info(f"📊 Re-ranked to {len(top_candidates)} top candidates for {additional_role}")
                            
                            # Enrich with job info (limit to top 5 for better coverage)
                            experience_range = filters_dict.get("experience_range") if filters_dict else None
                            enrichment_tasks = [enrich_candidate_with_job_info(c, additional_role, city, experience_range) for c in top_candidates[:5]]
                            enriched_results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)
                            
                            added_count = 0
                            for i, result in enumerate(enriched_results):
                                if isinstance(result, HiringCompany):
                                    result_dict = result.model_dump()
                                    result_dict["intel"] = {"focused_research": {}}
                                    new_companies.append(result_dict)
                                    added_count += 1
                                    logger.info(f"✅ Added company from {additional_role}: {result.company_name}")
                                elif isinstance(result, Exception):
                                    logger.warning(f"⚠️ Enrichment failed for candidate {i+1} in {additional_role}: {str(result)[:100]}")
                                    # Fallback: Add basic candidate info even if enrichment failed
                                    if i < len(top_candidates):
                                        candidate = top_candidates[i]
                                        fallback_company = HiringCompany(
                                            company_name=candidate.name,
                                            homepage_url=candidate.homepage,
                                            job_title=additional_role,
                                            job_url=candidate.source_url,
                                            job_location=city,
                                            job_source=candidate.source_site or "discovered",
                                            job_type="discovered",
                                            score=candidate.score,
                                            rank_score=candidate.score,
                                            blurb=candidate.snippet[:500] if candidate.snippet else "",
                                        )
                                        result_dict = fallback_company.model_dump()
                                        result_dict["intel"] = {"focused_research": {}}
                                        new_companies.append(result_dict)
                                        added_count += 1
                                        logger.info(f"✅ Added fallback company from {additional_role}: {candidate.name}")
                                elif result is None:
                                    logger.warning(f"⚠️ Enrichment returned None for candidate {i+1} in {additional_role}")
                                    # Fallback: Add basic candidate info
                                    if i < len(top_candidates):
                                        candidate = top_candidates[i]
                                        fallback_company = HiringCompany(
                                            company_name=candidate.name,
                                            homepage_url=candidate.homepage,
                                            job_title=additional_role,
                                            job_url=candidate.source_url,
                                            job_location=city,
                                            job_source=candidate.source_site or "discovered",
                                            job_type="discovered",
                                            score=candidate.score,
                                            rank_score=candidate.score,
                                            blurb=candidate.snippet[:500] if candidate.snippet else "",
                                        )
                                        result_dict = fallback_company.model_dump()
                                        result_dict["intel"] = {"focused_research": {}}
                                        new_companies.append(result_dict)
                                        added_count += 1
                                        logger.info(f"✅ Added fallback company (None result) from {additional_role}: {candidate.name}")
                                else:
                                    logger.warning(f"⚠️ Unexpected result type from enrichment: {type(result)}")
                            
                            logger.info(f"📊 Added {added_count} companies from {additional_role} (out of {len(enrichment_tasks)} candidates)")
                            
                            if added_count == 0:
                                logger.warning(f"⚠️ No companies added from {additional_role} - check enrichment logic")
                        
                        # Add to searched roles
                        existing_searched_roles.append(additional_role)
                        
                    except Exception as e:
                        logger.warning(f"Failed to search for role '{additional_role}': {e}")
                        await emit(TimelineEvent(
                            run_id=run_id, 
                            agent="RAG", 
                            message=f"⚠️ Could not search for {additional_role}: {str(e)[:50]}"
                        ))
                        existing_searched_roles.append(additional_role)  # Still mark as searched
                
                # Merge and deduplicate companies
                logger.info(f"📊 Collected {len(new_companies)} new companies from {len(additional_roles)} roles")
                
                if new_companies:
                    await emit(TimelineEvent(
                        run_id=run_id, 
                        agent="RAG", 
                        message=f"🔀 Merging {len(new_companies)} new companies with {len(existing_companies)} existing..."
                    ))
                    
                    # Use helper function for deduplication
                    existing_companies, added_count, duplicate_count = _deduplicate_companies(
                        existing_companies, new_companies
                    )
                    
                    logger.info(f"✅ After deduplication: {added_count} added, {duplicate_count} duplicates removed")
                    
                    await emit(TimelineEvent(
                        run_id=run_id, 
                        agent="RAG", 
                        message=f"✅ Added {added_count} unique companies (deduplicated {duplicate_count})"
                    ))
                else:
                    logger.warning(f"⚠️ No new companies found from {len(additional_roles)} additional roles!")
                    await emit(TimelineEvent(
                        run_id=run_id, 
                        agent="RAG", 
                        message=f"⚠️ No new companies found from additional role searches"
                    ))
                
                # Update RAGDoc in cache
                rag_doc_dict["companies"] = existing_companies
                rag_doc_dict["total"] = len(existing_companies)
                rag_doc_dict["searched_roles"] = existing_searched_roles
                rag_doc_dict["total_roles_searched"] = len(existing_searched_roles)
                
                # Check if more role variations available
                from .job_search import get_next_roles_batch
                _, has_more = get_next_roles_batch(role, existing_searched_roles, batch_size=5)
                rag_doc_dict["has_more_roles"] = has_more
                
                # Save updated RAGDoc
                print(f"💾 SAVING RAGDoc to cache: key={doc_key}, companies={len(existing_companies)}, roles={existing_searched_roles}", flush=True)
                mem.set(doc_key, rag_doc_dict)
                print(f"✅ RAGDoc SAVED to cache successfully", flush=True)
                
                await emit(TimelineEvent(
                    run_id=run_id, 
                    agent="RAG", 
                    message=f"🎉 Total: {len(existing_companies)} companies across {len(existing_searched_roles)} role variations"
                ))
                
                # Sort by rank_score for return
                existing_companies.sort(key=lambda x: x.get("rank_score", x.get("score", 0.0)), reverse=True)
                page = existing_companies[offset : offset + limit]
                
                return {
                    "run_id": run_id,
                    "role": role,
                    "city": city,
                    "companies": page,
                    "searched_roles": existing_searched_roles,
                    "total_roles_searched": len(existing_searched_roles),
                    "has_more_roles": has_more,
                    "pagination": {
                        "offset": offset,
                        "limit": limit,
                        "total": len(existing_companies),
                        "has_more": (offset + limit) < len(existing_companies)
                    }
                }
            
            # Cache hit - no additional roles to search, return cached data
            # Sort companies by rank_score or score (descending)
            companies_list = rag_doc_dict.get("companies", [])
            companies_list.sort(key=lambda x: x.get("rank_score", x.get("score", 0.0)), reverse=True)
            
            # Slice for pagination
            page = companies_list[offset : offset + limit]
            
            # Return compatible dict structure with new fields
            return {
                "run_id": rag_doc_dict.get("run_id", run_id),
                "role": rag_doc_dict.get("role", role),
                "city": rag_doc_dict.get("location", city),
                "companies": page,  # Already dicts with intel structure
                "searched_roles": rag_doc_dict.get("searched_roles", [role]),
                "total_roles_searched": rag_doc_dict.get("total_roles_searched", 1),
                "has_more_roles": rag_doc_dict.get("has_more_roles", True),
                "pagination": {
                    "offset": offset,
                    "limit": limit,
                    "total": rag_doc_dict.get("total", len(companies_list)),
                    "has_more": (offset + limit) < rag_doc_dict.get("total", len(companies_list))
                }
            }

        # 2. Cache Miss - Run Discovery
        # Build search role with resume-first priority (role from resume beats skills)
        effective_role = (resume_insights or {}).get("role") or role
        role_for_search = effective_role

        await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"🚀 Starting RAG company search run_id={run_id}, role={role_for_search}, location={city}, depth={depth}"))
        
        # === PHASE 0: DIRECT JOB SEARCH (no company constraints) ===
        # This is the PRIMARY search strategy - search job sites directly by role+location
        # Company-based search is only a SUPPLEMENT, not the main strategy
        await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"🎯 Phase 0: Direct role search for {role_for_search} in {city}..."))
        
        direct_results = await direct_role_search(role_for_search, city, min_results=5, max_results=20)
        
        if direct_results:
            # Log location distribution
            local_count = sum(1 for r in direct_results if r.job_location and r.job_location != "Remote")
            remote_count = sum(1 for r in direct_results if r.job_location == "Remote")
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"✅ Phase 0: Direct search found {len(direct_results)} results ({local_count} local, {remote_count} remote)"))
            
            # Split into first batch and cached batch
            first_batch = direct_results[:5]
            cached_batch = direct_results[5:]
            
            # Log location distribution in first batch
            local_in_first = sum(1 for r in first_batch if r.job_location and r.job_location != "Remote")
            remote_in_first = sum(1 for r in first_batch if r.job_location == "Remote")
            print(f"📋 First batch: {len(first_batch)} results ({local_in_first} local, {remote_in_first} remote)")
            
            # Cache extra results for "Load More" functionality
            if cached_batch:
                cache_key = f"loadmore:{run_id}"
                mem.set(cache_key, [c.model_dump() for c in cached_batch])
                print(f"💾 Cached {len(cached_batch)} results for Load More (key={cache_key})")
        else:
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"⚠️ Phase 0: Direct search found no results, falling back to company discovery"))
        
        # Phase 1: Discovery (Supplementary - finds additional companies)
        # SKIP if we already have enough ATS-direct results (saves API calls)
        filters_dict = filters.model_dump() if hasattr(filters, 'model_dump') else (filters if filters else None)
        
        if len(direct_results) >= 5:
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"⏭️ Phase 1: Skipping discovery (already have {len(direct_results)} ATS-direct results)"))
            candidates = []  # Skip discovery to save API calls
        else:
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"🔍 Phase 1: Discovering additional companies..."))
            candidates = await discover_companies(role_for_search, city, depth, filters=filters_dict)
        
        if not candidates and not direct_results:
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"⚠️ RAG: No candidates discovered for this role/location combo"))
            # Only return empty if BOTH direct search AND discovery found nothing
            empty_doc = RAGDoc(
                run_id=run_id, 
                role=role_for_search, 
                location=city, 
                depth=depth, 
                companies=[], 
                total=0,
                resume_insights=resume_insights,
                resume_excerpt=resume_excerpt,
                searched_roles=[role_for_search],
                total_roles_searched=1,
                has_more_roles=True  # Still has variations even with no results
            )
            mem.set(doc_key, empty_doc.model_dump())
            return {
                "run_id": run_id,
                "role": role_for_search,
                "city": city,
                "companies": [],
                "pagination": {"offset": offset, "limit": limit, "total": 0, "has_more": False}
            }
        
        # If no candidates but we have direct results, skip to merging phase
        if not candidates:
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"📊 Using {len(direct_results)} direct search results (no additional candidates found)"))
            candidates = []  # Empty list for the enrichment phase
        
        # Phase 2: Re-rank candidates
        await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"🎯 Phase 2: Re-ranking {len(candidates)} candidates..."))
        prof = role_profile(role_for_search)
        top_candidates = await rerank_candidates(candidates, role_for_search, city, prof.get("keywords", []), depth)
        
        await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"📊 Discovered {len(candidates)} candidates (top {len(top_candidates)} after re-rank)"))
        
        # Phase 2: Job Availability Enrichment (soft, best-effort)
        # SKIP enrichment if we have enough ATS-direct results (saves 9+ API calls per company!)
        annotated_companies = []
        enrichment_failures = []
        enriched_results = []
        
        if len(direct_results) >= 5 and len(top_candidates) == 0:
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"⏭️ Phase 2: Skipping enrichment (using {len(direct_results)} ATS-direct results)"))
            # Direct results will be added in the merge step below
        elif len(top_candidates) > 0:
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"💼 Phase 2: Enriching {len(top_candidates)} companies with job information (best-effort)..."))
            
            # Extract experience_range from filters
            experience_range = filters_dict.get("experience_range") if filters_dict else None
            
            # Enrich all candidates in parallel - all will be returned regardless of job search result
            enrichment_tasks = [enrich_candidate_with_job_info(c, role, city, experience_range) for c in top_candidates]
            enriched_results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)
            
            # Build annotated companies list from enrichment results
            for i, result in enumerate(enriched_results):
                candidate = top_candidates[i]
                if isinstance(result, HiringCompany):
                    annotated_companies.append(result)
                elif isinstance(result, Exception):
                    # If enrichment completely failed, log with full details for debugging
                    error_details = {
                        "company": candidate.name,
                        "homepage": candidate.homepage,
                        "source_url": candidate.source_url,
                        "error": str(result),
                        "error_type": type(result).__name__
                    }
                    enrichment_failures.append(error_details)
                    
                    logger.warning(
                        f"Enrichment failed for {candidate.name} (homepage: {candidate.homepage}, "
                        f"source: {candidate.source_url}): {result}"
                    )
                    
                    # Fallback: create company from candidate without job info
                    fallback_company = HiringCompany(
                        company_name=candidate.name,
                        homepage_url=candidate.homepage,
                        job_type="discovered",
                        score=candidate.score,
                        rank_score=candidate.score,
                        blurb=candidate.snippet,
                        job_posting=None
                    )
                    annotated_companies.append(fallback_company)
        else:
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"📊 No candidates to enrich, using direct results only"))
        
        # === MERGE DIRECT RESULTS WITH ENRICHED COMPANIES ===
        # Direct results are already high-quality (from Phase 0), add them first
        if direct_results:
            # Deduplicate by company name and job URL
            existing_urls = {c.job_url for c in annotated_companies if c.job_url}
            existing_names = {c.company_name.lower() for c in annotated_companies if c.company_name}
            
            added_from_direct = 0
            for direct_company in direct_results:
                # Skip if we already have this job URL or company
                if direct_company.job_url and direct_company.job_url in existing_urls:
                    continue
                if direct_company.company_name and direct_company.company_name.lower() in existing_names:
                    continue
                
                # Add direct result (these already have job_posting attached)
                annotated_companies.append(direct_company)
                added_from_direct += 1
                
                # Track for deduplication
                if direct_company.job_url:
                    existing_urls.add(direct_company.job_url)
                if direct_company.company_name:
                    existing_names.add(direct_company.company_name.lower())
            
            if added_from_direct > 0:
                await emit(TimelineEvent(
                    run_id=run_id,
                    agent="RAG",
                    message=f"✅ Merged {added_from_direct} direct search results with {len(annotated_companies) - added_from_direct} enriched companies"
                ))
        
        # Log enrichment summary
        successful_enrichments = len([c for c in annotated_companies if c.job_posting is not None])
        if enrichment_failures:
            await emit(TimelineEvent(
                run_id=run_id,
                agent="RAG",
                message=f"⚠️ {len(enrichment_failures)} enrichment failures (see logs for details). "
                       f"Successfully enriched {successful_enrichments}/{len(top_candidates)} companies."
            ))
        
        # Critical check: If zero companies were built, log clear warning
        if not annotated_companies and top_candidates:
            error_msg = (
                f"RAG: Discovered {len(candidates)} candidates (top {len(top_candidates)} after re-rank) "
                f"but 0 could be enriched into companies. Check JobPosting → Company mapping. "
                f"Enrichment failures: {len(enrichment_failures)}"
            )
            logger.error(error_msg)
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=error_msg, level="error"))
            
            # Still return fallback companies - don't crash
            await emit(TimelineEvent(
                run_id=run_id,
                agent="RAG",
                message=f"⚠️ Using fallback: Creating companies from discovery candidates without enrichment"
            ))
            # Create minimal companies from top candidates as fallback
            for candidate in top_candidates[:min(10, len(top_candidates))]:
                fallback = HiringCompany(
                    company_name=candidate.name,
                    homepage_url=candidate.homepage,
                    job_type="discovered",
                    score=candidate.score,
                    rank_score=candidate.score,
                    blurb=candidate.snippet,
                    job_posting=None
                )
                annotated_companies.append(fallback)
        
        # Phase 2.5: Ranking & Light Filtering
        await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"📊 Phase 2.5: Computing rank scores and applying light filtering..."))
        
        # Compute rank scores for all companies
        for company in annotated_companies:
            try:
                company.rank_score = compute_rank_score(company, role, city)
            except Exception as e:
                logger.warning(f"Failed to compute rank_score for {company.company_name}: {e}")
                # Keep original score if ranking fails
                company.rank_score = company.score
        
        # Apply light defensive filtering (removes only obvious junk)
        # This should be very forgiving - only drops clearly non-job content
        filtered_companies = apply_light_filtering(annotated_companies)
        
        # CRITICAL: If filtering removed everything but we had candidates, fall back to raw postings
        if not filtered_companies and annotated_companies:
            logger.warning(
                f"Light filtering removed all {len(annotated_companies)} companies. "
                f"Falling back to top {min(10, len(annotated_companies))} raw candidates."
            )
            await emit(TimelineEvent(
                run_id=run_id,
                agent="RAG",
                message=f"⚠️ Filtering removed all companies; using fallback: top {min(10, len(annotated_companies))} candidates"
            ))
            # Fallback: use top candidates by score, sorted by rank_score
            filtered_companies = sorted(annotated_companies, key=lambda x: x.rank_score, reverse=True)[:10]
        
        # Sort by rank_score descending
        filtered_companies.sort(key=lambda x: x.rank_score, reverse=True)
        
        # Keep top N based on depth
        cut_map = {"quick": 5, "standard": 10, "deep": 15, "max": 20}
        top_n = cut_map.get(depth, 10)
        ranked_companies = filtered_companies[:top_n]
        
        # Count companies with job postings for logging
        companies_with_jobs = sum(1 for c in ranked_companies if getattr(c, 'job_posting', None) is not None)
        
        await emit(TimelineEvent(
            run_id=run_id, 
            agent="RAG", 
            message=f"📊 Ranked {len(ranked_companies)} companies ({companies_with_jobs} with job postings)"
        ))
        
        # Phase 3: Research & Resume Matching (if needed)
        # For now, we'll use the ranked companies directly
        # If research/resume matching exists, it would go here
        researched_companies = ranked_companies  # Placeholder - can be enhanced later
        
        # Robust fallback: If we somehow lost all companies, fall back to top discovery candidates
        if not researched_companies and top_candidates:
            await emit(TimelineEvent(
                run_id=run_id, 
                agent="RAG", 
                message=f"⚠️ Fallback: Using top {min(5, len(top_candidates))} discovery candidates"
            ))
            # Create minimal companies from top candidates
            researched_companies = []
            for candidate in top_candidates[:5]:
                fallback = HiringCompany(
                    company_name=candidate.name,
                    homepage_url=candidate.homepage,
                    job_type="discovered",
                    score=candidate.score,
                    rank_score=candidate.score,
                    blurb=candidate.snippet,
                    job_posting=None
                )
                researched_companies.append(fallback)
        
        # Final check: If discovery found candidates, we MUST return something
        if not researched_companies and candidates:
            # Last resort fallback
            await emit(TimelineEvent(
                run_id=run_id, 
                agent="RAG", 
                message=f"⚠️ Last resort: Using top 3 discovery candidates"
            ))
            researched_companies = []
            for candidate in candidates[:3]:
                fallback = HiringCompany(
                    company_name=candidate.name,
                    homepage_url=candidate.homepage,
                    job_type="discovered",
                    score=candidate.score,
                    rank_score=candidate.score,
                    blurb=candidate.snippet,
                    job_posting=None
                )
                researched_companies.append(fallback)
        
        # Compute resume match scores for each job posting (hybrid: keyword + semantic).
        # Match against the REAL job description, not the search snippet — snippets are
        # ~40 chars ("AI Engineer · Full time"), which drove every score to the 0-match
        # floor and turned "missing skills" into words like "equity" and "offers".
        if resume_token and resume_text and researched_companies:
            companies_for_match: List[HiringCompany] = [
                c for c in researched_companies
                if getattr(c, "job_posting", None) and (c.job_posting.snippet or c.job_posting.title)
            ]

            job_texts = await _fetch_job_descriptions(companies_for_match)
            await emit(TimelineEvent(
                run_id=run_id, agent="RAG",
                message=f"📄 Read {sum(1 for t in job_texts if len(t) > 400)}/{len(job_texts)} full job descriptions for matching",
            ))

            # ONE embedding call for the whole batch. Scoring jobs one-by-one meant a
            # Voyage request per job, which rate-limited and turned a seconds-long
            # search into a minutes-long one.
            from ..tools.resume_job_matcher import compute_match_scores

            try:
                match_results = await compute_match_scores(resume_text, job_texts, resume_insights)
            except Exception as e:
                logger.warning(f"⚠️ Batch match scoring failed: {e}")
                match_results = []

            for comp, job_text, res in zip(companies_for_match, job_texts, match_results):
                if isinstance(res, dict):
                    comp.resume_match_score = res.get("match_score")
                    comp.match_band = res.get("match_band")
                    comp.match_probability = res.get("match_probability")
                    comp.match_explanation = res.get("match_explanation")
                    # analyze_gaps already ran inside compute_match_score
                    comp.missing_skills = res.get("missing_skills", [])
                else:
                    logger.warning(f"⚠️ Match scoring failed for {getattr(comp, 'company_name', 'unknown')}: {res}")

        # Phase 4: Cache results
        companies_with_jobs_final = sum(1 for c in researched_companies if getattr(c, 'job_posting', None) is not None)
        await emit(TimelineEvent(
            run_id=run_id, 
            agent="RAG", 
            message=f"🏆 Built {len(researched_companies)} hiring companies ({companies_with_jobs_final} with job postings); caching under {doc_key}"
        ))
        
        # Extract resume data if resume_token is provided
        if resume_token and resume_insights and resume_insights.get("skills_flat"):
            await emit(TimelineEvent(
                run_id=run_id,
                agent="RAG",
                message=f"✅ Extracted resume insights: role={resume_insights.get('role', 'N/A')}, skills={len(resume_insights.get('skills_flat', []) or resume_insights.get('skills', []))}"
            ))
        
        # Create RAGDoc with companies
        # Initialize searched_roles with the primary role (resume role if present)
        searched_roles = [role_for_search]
        
        # Check if more role variations are available
        from .job_search import get_next_roles_batch
        _, has_more_roles = get_next_roles_batch(role_for_search, searched_roles, batch_size=5)
        
        rag_doc = RAGDoc(
            run_id=run_id,
            role=role_for_search,
            location=city,
            depth=depth,
            companies=researched_companies,
            total=len(researched_companies),
            resume_insights=resume_insights,
            resume_excerpt=resume_excerpt,
            # New fields for "Load 5 more roles" feature
            searched_roles=searched_roles,
            total_roles_searched=1,
            has_more_roles=has_more_roles
        )
        
        # Convert to dict and ensure all companies have intel structure initialized
        # This allows the writer to know the structure exists and can populate it later
        rag_doc_dict = rag_doc.model_dump()
        for company_dict in rag_doc_dict.get("companies", []):
            if "intel" not in company_dict:
                company_dict["intel"] = {}
            if "focused_research" not in company_dict.get("intel", {}):
                company_dict["intel"]["focused_research"] = {}
        
        # Store the dict version (with intel structure) so it's available when loaded
        mem.set(doc_key, rag_doc_dict)
        
        # Phase 5: Return paginated results
        page = researched_companies[offset : offset + limit]
        
        # Convert companies to dicts and ensure intel structure exists
        companies_dicts = []
        for company in page:
            company_dict = company.model_dump()
            # Ensure intel structure exists
            if "intel" not in company_dict:
                company_dict["intel"] = {}
            if "focused_research" not in company_dict.get("intel", {}):
                company_dict["intel"]["focused_research"] = {}
            companies_dicts.append(company_dict)
        
        return {
            "run_id": run_id,
            "role": role_for_search,
            "city": city,
            "companies": companies_dicts,  # Dicts with intel structure
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": len(researched_companies),
                "has_more": (offset + limit) < len(researched_companies)
            }
        }

    except Exception as e:
        # Log error
        error_msg = f"RAG job failed for {run_id}: {e}"
        print(f"❌ {error_msg}")
        print(traceback.format_exc())
        await emit(TimelineEvent(run_id=run_id, agent="RAG", message=error_msg, level="error"))
        
        # Store empty fallback doc (with resume data if available)
        # Use previously extracted insights/excerpt if available
        
        fallback = RAGDoc(
            run_id=run_id, 
            role=role_for_search, 
            location=city, 
            depth=depth,
            resume_insights=resume_insights,
            resume_excerpt=resume_excerpt,
            searched_roles=[role_for_search],
            total_roles_searched=1,
            has_more_roles=True  # Still has variations even on failure
        )
        if memory_store:
            memory_store.set(f"ragdoc:{run_id}", fallback.model_dump())
            
        return {
            "run_id": run_id,
            "role": role_for_search,
            "city": city,
            "companies": [],
            "pagination": {
                "offset": offset, 
                "limit": limit, 
                "total": 0, 
                "has_more": False
            }
        }

# --- Helper Functions ---

async def get_rag_results(run_id: str, offset: int = 0, limit: int = 5, memory_store: Any = None) -> RAGDoc:
    """
    Load cached RAGDoc from memory and apply pagination.
    Returns empty RAGDoc (no 404) if not found.
    """
    mem = memory_store if memory_store else Memory()
    doc_key = f"ragdoc:{run_id}"
    
    # Load from cache
    cached_data = mem.get(doc_key)
    
    rag_doc = None
    print(f"🔍 get_rag_results called: run_id={run_id}, cached_data={bool(cached_data)}", flush=True)
    
    if cached_data:
        print(f"📋 get_rag_results: Found cached data for {run_id}, type={type(cached_data)}", flush=True)
        
        # Convert dict to RAGDoc if needed
        if isinstance(cached_data, dict):
            num_companies = len(cached_data.get('companies', []))
            print(f"📋 Cached dict has {num_companies} companies, keys: {list(cached_data.keys())[:10]}", flush=True)
            try:
                # Ensure companies are HiringCompany objects
                companies_data = cached_data.get("companies", [])
                companies = []
                for i, c in enumerate(companies_data):
                    try:
                        if isinstance(c, dict):
                            companies.append(HiringCompany(**c))
                        elif isinstance(c, HiringCompany):
                            companies.append(c)
                    except Exception as ce:
                        print(f"⚠️ Failed to convert company {i}: {ce}", flush=True)
                
                # Build RAGDoc with proper types
                rag_doc = RAGDoc(
                    run_id=cached_data.get("run_id", run_id),
                    role=cached_data.get("role", ""),
                    location=cached_data.get("location", ""),
                    depth=cached_data.get("depth", "standard"),
                    companies=companies,
                    total=cached_data.get("total", len(companies)),
                    pagination=cached_data.get("pagination", {}),
                    resume_insights=cached_data.get("resume_insights", {}),
                    resume_excerpt=cached_data.get("resume_excerpt", ""),
                    searched_roles=cached_data.get("searched_roles", []),
                    total_roles_searched=cached_data.get("total_roles_searched", 0),
                    has_more_roles=cached_data.get("has_more_roles", True)
                )
                print(f"✅ get_rag_results: Successfully built RAGDoc with {len(companies)} companies", flush=True)
            except Exception as e:
                print(f"❌ get_rag_results: Failed to build RAGDoc from cache: {e}", flush=True)
                import traceback
                traceback.print_exc()
        elif isinstance(cached_data, RAGDoc):
            rag_doc = cached_data
            print(f"✅ get_rag_results: Using cached RAGDoc directly with {len(rag_doc.companies)} companies", flush=True)
    else:
        print(f"⚠️ get_rag_results: No cached data found for {run_id}", flush=True)
    
    # If not found, return empty RAGDoc (no 404)
    if not rag_doc:
        print(f"⚠️ get_rag_results: Returning empty RAGDoc for {run_id}", flush=True)
        return RAGDoc(
            run_id=run_id,
            role="",
            location="",
            depth="standard",
            companies=[],
            total=0
        )
    
    # Apply pagination by slicing companies
    # Note: We return the full RAGDoc but the caller can slice companies if needed
    # For consistency with the API, we'll create a copy with sliced companies
    all_companies = rag_doc.companies.copy()
    all_companies.sort(key=lambda x: x.score, reverse=True)  # Ensure sorted
    
    sliced_companies = all_companies[offset : offset + limit]
    
    # Return RAGDoc with sliced companies and updated total
    # IMPORTANT: Include all new fields for "Load 5 more roles" feature
    return RAGDoc(
        run_id=rag_doc.run_id,
        role=rag_doc.role,
        location=rag_doc.location,
        depth=rag_doc.depth,
        companies=sliced_companies,
        total=len(all_companies),  # Total count of all companies, not just this page
        pagination=rag_doc.pagination,
        resume_insights=rag_doc.resume_insights,
        resume_excerpt=rag_doc.resume_excerpt,
        searched_roles=rag_doc.searched_roles,
        total_roles_searched=rag_doc.total_roles_searched,
        has_more_roles=rag_doc.has_more_roles
    )
