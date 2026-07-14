from __future__ import annotations
import os
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urljoin, urlunparse, parse_qs
import asyncio  # Import asyncio for gather
from dataclasses import dataclass

from ..schemas import CompanyIntel, JobPosting
from ..agents.match import smart_search, SearchHit
from ..tools.http_fetch import fetch_url_content
from ..rag.roles import role_profile

# Import company name validation
try:
    from .rag_companies import is_valid_company_name
except ImportError:
    # Fallback if import fails
    def is_valid_company_name(name: str) -> bool:
        if not name or len(name) < 2:
            return False
        return True

# Diagnostic output is opt-in and must remain disabled in production.
DEBUG_DISCOVERY = os.getenv("DEBUG_DISCOVERY", "false").lower() == "true"

# Feature flag: Use LLM-based normalization instead of rule-based extraction
USE_LLM_NORMALIZER = os.getenv("USE_LLM_NORMALIZER", "true").lower() == "true"

# Import normalizer only if enabled
if USE_LLM_NORMALIZER:
    try:
        from .job_result_normalizer import normalize_job_result
        LLM_NORMALIZER_AVAILABLE = True
    except ImportError:
        LLM_NORMALIZER_AVAILABLE = False
        print("⚠️ LLM normalizer not available, falling back to rule-based extraction")
else:
    LLM_NORMALIZER_AVAILABLE = False

# Primary allowlist for ATS and Job Boards
ALLOWED_JOB_DOMAINS = [
    # ATS Systems
    "lever.co",
    "jobs.lever.co",
    "greenhouse.io",
    "boards.greenhouse.io",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "workable.com",
    "apply.workable.com",
    "smartrecruiters.com",
    "bamboohr.com",
    "myworkdayjobs.com",
    "icims.com",
    "jazzhr.com",
    "jazz.co",
    "recruiting.paylocity.com",
    "recruiting.ultipro.com",
    "recruitee.com",
    "jobvite.com",
    "breezy.hr",
    "applytojob.com",
    "pinpointhq.com",
    "careers-page.com",
    "jobscore.com",
    "recruitify.com",
    "workday.com",
    
    # Quality Job Boards
    "indeed.com",
    "builtinnyc.com",
    "builtinsf.com",
    "builtin.com",
    "wellfound.com",
    "angel.co",
    "remotive.com",
    "arc.dev",
    "turing.com",
    "ziprecruiter.com",
    "hiringcafe.com",
    "jooble.org",
    "adzuna.com",
    "dice.com",
    "clearancejobs.com",
    "ycombinator.com",
    "ycombinator.com/jobs",
    "triplebyte.com",
    "hired.com",
    "techjobsasia.com",
    "glassdoor.com",
    "monster.com",
    "careerbuilder.com",
]

# Curated domains that we trust for high-signal startup/ATS postings
CURATED_JOB_DOMAINS = [
    # Modern job boards / startup boards
    "jobs.ashbyhq.com",
    "wellfound.com",
    "workatastartup.com",
    "ycombinator.com",
    "jobshq.com",

    # ATS hosts (these host lots of startup jobs)
    "lever.co",
    "jobs.lever.co",
    "greenhouse.io",
    "boards.greenhouse.io",
]

# Preferred job domains - prioritize these for quality job postings
PREFERRED_JOB_DOMAINS = [
    # ATS Systems (direct company job postings)
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "jobs.lever.co",
    "lever.co",
    "boards.greenhouse.io",
    "greenhouse.io",
    # Quality Job Boards
    "wellfound.com",
    "ycombinator.com/jobs",
    "builtinsf.com",
    "builtinnyc.com",
    "builtin.com",
]

# Aggregator domains (lower priority, prefer direct postings)
AGGREGATOR_DOMAINS = [
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "dice.com",
    "monster.com",
    "careerbuilder.com",
    "hiringcafe.com",
    "jooble.org",
    "adzuna.com",
]

# Domains we explicitly avoid (user requested)
EXCLUDED_JOB_DOMAINS = [
    "linkedin.com",
    "www.linkedin.com",
    "linkedin.com/jobs",
]

RECENCY_WINDOW_DAYS = 45

# URL / title fragments that usually indicate a generic listing/search page rather
# than a single job detail.
LISTING_PATTERNS = [
    "/jobs?",
    "/jobs-all",
    "/jobs/all",
    "/jobs/search",
    "/job-search",
    "/jobsearch",
    "/search-jobs",
    "/search?",
    "-jobs-",
    "-jobs-in-",
    " jobs in ",
]

# Maximum characters for second-hop extraction (when following links from listing pages).
SECOND_HOP_MAX_CHARS = 3500

# Legacy blocked domains (kept for compatibility)
_LEGACY_BLOCKED_DOMAINS = ["www.ycombinator.com/companies"]

# === URL PRE-FILTERING FOR LLM ===
# Domains to always reject before LLM classification
BLOCKED_DOMAINS_FOR_LLM = {
    # Job aggregators (we want direct company pages, not aggregators)
    'indeed.com', 'ziprecruiter.com', 'glassdoor.com', 'simplyhired.com',
    'monster.com', 'careerbuilder.com', 'jooble.org', 'talent.com', 'adzuna.com',
    # Social media
    'linkedin.com', 'facebook.com', 'twitter.com', 'reddit.com',
    'pinterest.com', 'instagram.com', 'tiktok.com',
    # Reference/content sites
    'wikipedia.org', 'youtube.com', 'quora.com', 'medium.com',
    'calendar.google.com', 'timeanddate.com',
    # Google properties (not job sites)
    'google.com', 'support.google.com', 'accounts.google.com',
    # Education platforms (NOT job sites)
    'tophat.com', 'coursera.com', 'udemy.com', 'edx.org',
    # E-commerce
    'amazon.com', 'ebay.com', 'walmart.com', 'target.com',
    # Developer tools (NOT job boards)
    'stackoverflow.com', 'github.com', 'gitlab.com', 'bitbucket.org',
    # News/media (NOT job sites)
    'news.ycombinator.com', 'techcrunch.com', 'wired.com', 'theverge.com',
    'forbes.com', 'businessinsider.com', 'bloomberg.com', 'cnbc.com',
    'nytimes.com', 'wsj.com', 'washingtonpost.com',
    # Staffing agencies (they list OTHER companies' jobs)
    'roberthalf.com', 'roberthalftechnology.com',
    'randstad.com', 'adecco.com', 'manpower.com',
    'kellyservices.com', 'spherion.com', 'hays.com',
    'cybercoders.com', 'teksystems.com', 'modis.com',
    'insight.com', 'apex.com', 'kforce.com',
}

# ATS domains to always accept (high quality)
QUALITY_ATS_DOMAINS = {
    'greenhouse.io', 'lever.co', 'ashbyhq.com', 'workday.com',
    'myworkdayjobs.com', 'smartrecruiters.com', 'icims.com',
    'jobvite.com', 'bamboohr.com', 'jazz.co', 'recruitee.com',
    'workable.com', 'breezy.hr', 'rippling.com'
}

# Quality job boards to always accept
QUALITY_JOB_BOARDS = {
    'ycombinator.com', 'workatastartup.com', 'wellfound.com',
    'builtinsf.com', 'builtin.com', 'angel.co', 'levels.fyi',
    'builtinnyc.com', 'remotive.com', 'arc.dev'
}

# === URL CLASSIFICATION FOR DIRECT POSTINGS VS LISTING PAGES ===

def classify_job_url(url: str) -> str:
    """
    Classify a URL as 'direct_posting', 'listing_page', or 'unknown'.
    
    Direct posting indicators:
    - Has job ID in path (e.g., /jobs/123, /j/abc123)
    - ATS subdomain pattern (company.lever.co, company.greenhouse.io)
    - Path contains specific job slug
    
    Listing page indicators:
    - Search query params (q=, query=, search=)
    - Pagination params (page=, p=, offset=)
    - Multiple location/role filters
    - Generic paths like /jobs, /careers, /search
    """
    if not url:
        return 'unknown'
    
    url_lower = url.lower()
    parsed = urlparse(url_lower)
    path = parsed.path
    query = parsed.query
    domain = parsed.netloc
    
    # === LISTING PAGE INDICATORS (check first) ===
    
    # Has search/filter query params
    listing_params = ['q=', 'query=', 'search=', 'keyword=', 'page=', 'p=', 
                      'offset=', 'filter=', 'sort=', 'location=', 'l=']
    if any(param in query for param in listing_params):
        return 'listing_page'
    
    # Generic listing paths
    listing_paths = [
        r'/jobs$', r'/jobs/$', r'/jobs\?', r'/careers$', r'/careers/$',
        r'/search', r'/results', r'/openings$', r'/positions$',
        r'/jobs-in-', r'/jobs/search', r'/job-search',
        r'/jobs/q-',  # Dice pattern
    ]
    for pattern in listing_paths:
        if re.search(pattern, path):
            return 'listing_page'
    
    # Aggregator domains are usually listing pages
    aggregator_domains = ['dice.com', 'indeed.com', 'ziprecruiter.com', 'glassdoor.com',
                         'monster.com', 'careerbuilder.com', 'simplyhired.com', 'linkedin.com']
    if any(agg in domain for agg in aggregator_domains):
        # Exception: Indeed viewjob URLs are direct
        if 'viewjob' in path or 'jk=' in query:
            return 'direct_posting'
        return 'listing_page'
    
    # === DIRECT POSTING INDICATORS ===
    
    # ATS with company subdomain (company.lever.co, company.greenhouse.io)
    ats_patterns = [
        r'^[a-z0-9-]+\.lever\.co',
        r'^[a-z0-9-]+\.greenhouse\.io',
        r'^[a-z0-9-]+\.ashbyhq\.com',
        r'^jobs\.[a-z0-9-]+\.com',  # jobs.company.com
        r'^careers\.[a-z0-9-]+\.com',  # careers.company.com
    ]
    for pattern in ats_patterns:
        if re.match(pattern, domain):
            return 'direct_posting'
    
    # Job ID in path (numeric or alphanumeric)
    job_id_patterns = [
        r'/jobs?/[a-f0-9-]{8,}',  # UUID-style
        r'/jobs?/\d{4,}',         # Numeric ID
        r'/j/[a-zA-Z0-9]+',       # Short ID
        r'/positions?/\d+',
        r'/openings?/\d+',
        r'/careers?/[a-z0-9-]+-\d+',  # slug-123 pattern
    ]
    for pattern in job_id_patterns:
        if re.search(pattern, path):
            return 'direct_posting'
    
    # Path looks like a specific role (not generic)
    if re.search(r'/jobs?/[a-z]+-[a-z]+-[a-z]+', path):  # e.g., /jobs/senior-devops-engineer
        return 'direct_posting'
    
    return 'unknown'


def extract_company_from_ats_url(url: str) -> Optional[str]:
    """
    Extract company name from ATS URL patterns.
    Returns None if can't extract (caller should try title extraction).
    """
    if not url:
        return None
    
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc
        path = parsed.path
        path_parts = [p for p in path.split('/') if p and p not in ['jobs', 'job', 'embed', 'j', 'apply', 'careers', 'positions']]
    except:
        return None
    
    company = None
    
    # Pattern 1: company.lever.co/job-id
    if '.lever.co' in domain:
        subdomain = domain.split('.lever.co')[0]
        if subdomain and subdomain not in ['jobs', 'www', 'careers', 'boards']:
            company = subdomain
    
    # Pattern 2: boards.greenhouse.io/company/jobs/123 or job-boards.greenhouse.io/company/...
    elif 'greenhouse.io' in domain:
        if path_parts:
            # First non-job path part is usually company
            company = path_parts[0]
    
    # Pattern 3: jobs.ashbyhq.com/company/job-id
    elif 'ashbyhq.com' in domain:
        if path_parts:
            company = path_parts[0]
    
    # Pattern 4: company.workable.com
    elif '.workable.com' in domain:
        subdomain = domain.split('.workable.com')[0]
        if subdomain and subdomain not in ['jobs', 'www', 'apply']:
            company = subdomain
    
    # Pattern 5: company.myworkdayjobs.com
    elif '.myworkdayjobs.com' in domain or 'myworkday.com' in domain:
        subdomain = domain.split('.')[0]
        if subdomain and subdomain not in ['www']:
            company = subdomain
    
    # Clean up and validate
    if company:
        # Convert slug to title case
        company = company.replace('-', ' ').replace('_', ' ').title()
        # Remove common suffixes
        for suffix in [' Inc', ' Llc', ' Corp', ' Ltd', ' Co']:
            if company.endswith(suffix):
                company = company[:-len(suffix)].strip()
        # Validate length
        if len(company) >= 2 and len(company) <= 50:
            return company
    
    return None


def is_direct_job_posting(url: str) -> bool:
    """Quick check if URL is a direct job posting."""
    return classify_job_url(url) == 'direct_posting'


def is_url_worth_processing(url: str) -> Tuple[bool, str]:
    """
    Pre-filter URLs before LLM classification.
    STRICT MODE: Block unknown domains by default to save LLM calls.
    Returns (should_process, reason)
    """
    if not url:
        return False, "empty URL"
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
        path = parsed.path.lower()
    except:
        return False, "invalid URL"
    
    # Block known aggregators/noise FIRST
    for blocked in BLOCKED_DOMAINS_FOR_LLM:
        if blocked in domain:
            return False, f"blocked domain: {blocked}"
    
    # Always accept quality ATS
    for ats in QUALITY_ATS_DOMAINS:
        if ats in domain:
            return True, f"quality ATS: {ats}"
    
    # Always accept quality job boards
    for board in QUALITY_JOB_BOARDS:
        if board in domain:
            return True, f"quality board: {board}"
    
    # Check URL path for job indicators
    job_path_indicators = ['/jobs/', '/careers/', '/job/', '/positions/', '/opening/', '/apply/', '/j/']
    if any(indicator in path for indicator in job_path_indicators):
        return True, "has job path indicator"
    
    # Check if domain looks like a company careers page
    if 'careers.' in domain or 'jobs.' in domain:
        return True, "careers/jobs subdomain"
    
    # STRICT DEFAULT: Unknown domains are BLOCKED (not verified by LLM)
    # This saves LLM calls and prevents garbage like tophat.com from getting through
    return False, f"unknown domain blocked: {domain}"

def prefilter_urls(results: List[dict]) -> Tuple[List[dict], List[dict]]:
    """
    Filter and classify search results before LLM processing.
    Returns (direct_postings, listing_pages) - process direct postings first.
    """
    direct_postings = []
    listing_pages = []
    blocked = []
    
    for result in results:
        url = result.get('url', '')
        
        # First check if URL should be blocked entirely
        should_process, reason = is_url_worth_processing(url)
        if not should_process:
            if DEBUG_DISCOVERY:
                print(f"    🚫 Pre-filter blocked: {url[:60]}... ({reason})")
            blocked.append(result)
            continue
        
        # Classify the URL
        classification = classify_job_url(url)
        result['_url_classification'] = classification
        result['_prefilter_reason'] = reason
        
        if classification == 'direct_posting':
            # Try to extract company from URL
            company = extract_company_from_ats_url(url)
            if company:
                result['_extracted_company'] = company
            direct_postings.append(result)
            if DEBUG_DISCOVERY:
                company_str = f" [{company}]" if company else ""
                print(f"    ✅ DIRECT POSTING{company_str}: {url[:60]}...")
        elif classification == 'listing_page':
            listing_pages.append(result)
            if DEBUG_DISCOVERY:
                print(f"    📋 Listing page (needs extraction): {url[:60]}...")
        else:
            # Unknown - treat as potential direct posting
            direct_postings.append(result)
            if DEBUG_DISCOVERY:
                print(f"    ❓ Unknown (will verify): {url[:60]}...")
    
    if DEBUG_DISCOVERY:
        print(f"    📊 Classification: {len(direct_postings)} direct, {len(listing_pages)} listings, {len(blocked)} blocked")
    
    return direct_postings, listing_pages

# Role-based site mappings (hybrid approach: predefined + dynamic)
# Maps role categories to their optimal job search sites
ROLE_SITE_MAPPINGS = {
    # AI/ML roles - startups and tech companies
    "ai_ml": {
        "sites": ["ycombinator.com/jobs", "builtinsf.com", "wellfound.com", "lever.co", "greenhouse.io"],
        "keywords": ["ai", "artificial intelligence", "machine learning", "ml", "deep learning", 
                    "nlp", "llm", "generative ai", "computer vision", "data science", "applied scientist",
                    "research engineer", "mlops", "ai/ml", "prompt engineer"]
    },
    # Backend/Java/Enterprise roles - traditional tech job boards
    "backend_enterprise": {
        "sites": ["dice.com", "indeed.com", "builtin.com", "lever.co", "greenhouse.io"],
        "keywords": ["java", "backend", "back-end", "spring", "microservices", "enterprise", 
                    "architect", "systems engineer", "platform engineer", "devops", "sre",
                    "site reliability", "infrastructure"]
    },
    # Full-Stack/Web Development roles - startup-friendly boards
    "fullstack_web": {
        "sites": ["wellfound.com", "builtinsf.com", "lever.co", "greenhouse.io", "remotive.com"],
        "keywords": ["full stack", "full-stack", "fullstack", "web developer", "software engineer",
                    "frontend", "front-end", "react", "node", "typescript", "javascript"]
    },
    # Data roles - analytics and data-focused boards
    "data": {
        "sites": ["builtin.com", "wellfound.com", "indeed.com", "lever.co", "greenhouse.io"],
        "keywords": ["data engineer", "data analyst", "analytics", "etl", "data warehouse",
                    "bi analyst", "business intelligence", "data platform", "big data", "spark", "airflow"]
    },
    # Security/Compliance roles - specialized boards
    "security": {
        "sites": ["clearancejobs.com", "dice.com", "indeed.com", "lever.co", "greenhouse.io"],
        "keywords": ["security", "cybersecurity", "infosec", "penetration", "compliance",
                    "soc analyst", "security engineer", "devsecops"]
    },
    # Product/Design roles - startup and product boards
    "product_design": {
        "sites": ["wellfound.com", "builtinsf.com", "builtin.com", "lever.co", "ashbyhq.com"],
        "keywords": ["product manager", "product owner", "ux", "ui", "designer", "product design",
                    "user experience", "user research"]
    },
    # Cloud/DevOps roles - tech-focused boards
    "cloud_devops": {
        "sites": ["dice.com", "builtin.com", "wellfound.com", "lever.co", "greenhouse.io"],
        "keywords": ["cloud", "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
                    "cloud engineer", "cloud architect", "devops"]
    }
}

# Cache for role-to-sites mapping
_role_sites_cache = {}


def get_optimal_sites_for_role(role: str, max_sites: int = 3) -> List[str]:
    """
    Get optimal job search sites for a given role using hybrid approach:
    1. Check predefined mappings first (fast)
    2. Fall back to keyword matching (dynamic)
    3. Default to general preferred domains
    
    Args:
        role: Job role title (e.g., "AI Engineer", "Java Developer")
        max_sites: Maximum number of sites to return (default 3 for efficiency)
    
    Returns:
        List of optimal domain names for searching this role
    """
    role_lower = role.lower()
    
    # Check cache first
    cache_key = f"{role_lower}:{max_sites}"
    if cache_key in _role_sites_cache:
        return _role_sites_cache[cache_key]
    
    # Step 1: Try exact keyword matching against predefined categories
    best_match = None
    best_score = 0
    
    for category, config in ROLE_SITE_MAPPINGS.items():
        keywords = config["keywords"]
        # Count how many keywords match the role
        score = sum(1 for kw in keywords if kw in role_lower)
        if score > best_score:
            best_score = score
            best_match = category
    
    # Step 2: If good match found, use those sites
    if best_match and best_score >= 1:
        sites = ROLE_SITE_MAPPINGS[best_match]["sites"][:max_sites]
        if DEBUG_DISCOVERY:
            print(f"🎯 Role '{role}' matched category '{best_match}' (score={best_score}) → sites: {sites}")
        _role_sites_cache[cache_key] = sites
        return sites
    
    # Step 3: Dynamic fallback - infer from role keywords
    # Use role_profile to get keywords for this role
    prof = role_profile(role)
    role_keywords = prof.get("keywords", [])
    
    if role_keywords:
        # Try matching role keywords against category keywords
        for category, config in ROLE_SITE_MAPPINGS.items():
            cat_keywords = set(config["keywords"])
            role_kw_set = set(kw.lower() for kw in role_keywords)
            overlap = cat_keywords & role_kw_set
            if len(overlap) >= 2:  # At least 2 keyword overlap
                sites = config["sites"][:max_sites]
                if DEBUG_DISCOVERY:
                    print(f"🎯 Role '{role}' dynamically matched '{category}' via keywords: {overlap}")
                _role_sites_cache[cache_key] = sites
                return sites
    
    # Step 4: Default fallback - use general preferred domains
    default_sites = PREFERRED_JOB_DOMAINS[:max_sites]
    if DEBUG_DISCOVERY:
        print(f"🎯 Role '{role}' using default sites: {default_sites}")
    _role_sites_cache[cache_key] = default_sites
    return default_sites


def clear_role_sites_cache():
    """Clear the role-to-sites cache (useful for testing)"""
    global _role_sites_cache
    _role_sites_cache = {}


async def search_curated_job_boards(
    role: str,
    location: str,
    *,
    max_results: int = 10,
    company_hint: Optional[str] = None
) -> List[SearchHit]:
    """
    Tavily query constrained to the curated ATS / high-signal job-board domains.
    Mirrors "Perplexity-style" retrieval: tight role/location query and whitelisted recall.
    """
    from ..tools.tavily_search import tavily_search

    query_parts = []
    if company_hint:
        query_parts.append(f'"{company_hint.strip()}"')
    if role:
        query_parts.append(f'"{role.strip()}"')
    if location:
        query_parts.append(f'"{location.strip()}"')

    query = " ".join(query_parts) or role or location or "jobs"

    tavily_results = await tavily_search(
        query,
        num_results=max_results,
        search_depth="basic",
        include_domains=CURATED_JOB_DOMAINS,
        exclude_domains=EXCLUDED_JOB_DOMAINS
    )

    hits: List[SearchHit] = []
    for result in tavily_results:
        hits.append(SearchHit(
            url=result.get("url", ""),
            title=result.get("title", "") or "No title",
            snippet=result.get("content", ""),
            score=float(result.get("score", 0.0)) * 100.0
        ))

    if DEBUG_DISCOVERY:
        target = f"{company_hint or ''} {role} {location}".strip()
        print(f"    🔍 Curated search '{query}' → {len(hits)} hits (target={target})")

    return hits


# Role variations map - maps primary roles to their variations
# Used for "Load 5 more roles" feature (up to 20 total roles)
ROLE_VARIATIONS_MAP = {
    # AI/ML roles - 15 variations for AI Engineer
    "AI Engineer": [
        "Machine Learning Engineer", "ML Engineer", "AI/ML Engineer",
        "Applied Scientist", "Research Engineer", "Deep Learning Engineer",
        "NLP Engineer", "LLM Engineer", "Generative AI Engineer",
        "Computer Vision Engineer", "MLOps Engineer", "AI Platform Engineer",
        "ML Infrastructure Engineer", "Prompt Engineer", "AI Researcher"
    ],
    "Machine Learning Engineer": [
        "AI Engineer", "ML Engineer", "AI/ML Engineer",
        "Applied Scientist", "Research Scientist", "Deep Learning Engineer",
        "Data Scientist", "MLOps Engineer", "Computer Vision Engineer",
        "NLP Engineer", "ML Platform Engineer", "AI Research Engineer",
        "Senior ML Engineer", "Staff ML Engineer", "Principal ML Engineer"
    ],
    
    # Full-Stack/Web Development roles
    "Full-Stack Developer": [
        "Software Engineer", "Full Stack Engineer", "Web Developer",
        "Application Developer", "Frontend Engineer", "Backend Engineer",
        "Software Developer", "Fullstack Developer", "MERN Developer",
        "MEAN Developer", "React Developer", "Node.js Developer",
        "TypeScript Developer", "JavaScript Developer", "Staff Engineer"
    ],
    "Software Engineer": [
        "Full-Stack Developer", "Backend Engineer", "Frontend Engineer",
        "Software Developer", "Application Developer", "Web Developer",
        "Platform Engineer", "Systems Engineer", "Full Stack Engineer",
        "Senior Software Engineer", "Staff Software Engineer", "Principal Engineer",
        "Development Engineer", "Programming Engineer", "SDE"
    ],
    
    # Java/Backend roles
    "Java Developer": [
        "Backend Engineer", "Java Engineer", "Spring Developer",
        "Software Engineer", "Backend Developer", "J2EE Developer",
        "Java Software Engineer", "Senior Java Developer", "Microservices Developer",
        "API Developer", "Platform Engineer", "Enterprise Developer",
        "Spring Boot Developer", "Kotlin Developer", "JVM Developer"
    ],
    
    # Data roles
    "Data Analyst": [
        "Business Analyst", "BI Analyst", "Business Intelligence Analyst",
        "Analytics Engineer", "Data Engineer", "SQL Analyst",
        "Reporting Analyst", "Insights Analyst", "Product Analyst",
        "Marketing Analyst", "Financial Analyst", "Quantitative Analyst",
        "Data Visualization Specialist", "Tableau Developer", "Power BI Developer"
    ],
    "Data Engineer": [
        "Analytics Engineer", "ETL Engineer", "Data Platform Engineer",
        "Data Pipeline Engineer", "Big Data Engineer", "Data Architect",
        "Data Warehouse Engineer", "Spark Developer", "Airflow Engineer",
        "Data Infrastructure Engineer", "Senior Data Engineer", "Staff Data Engineer",
        "Machine Learning Engineer", "DataOps Engineer", "Cloud Data Engineer"
    ],
    
    # DevOps/Cloud roles
    "DevOps Engineer": [
        "Site Reliability Engineer", "SRE", "Platform Engineer",
        "Cloud Engineer", "Infrastructure Engineer", "Release Engineer",
        "Build Engineer", "Automation Engineer", "Kubernetes Engineer",
        "AWS Engineer", "Azure Engineer", "GCP Engineer",
        "CI/CD Engineer", "DevSecOps Engineer", "Systems Engineer"
    ],
    "Cloud Engineer": [
        "DevOps Engineer", "Platform Engineer", "Infrastructure Engineer",
        "AWS Engineer", "Azure Engineer", "GCP Engineer",
        "Cloud Architect", "Solutions Architect", "SRE",
        "Site Reliability Engineer", "Kubernetes Engineer", "Cloud DevOps Engineer",
        "Cloud Platform Engineer", "Cloud Infrastructure Engineer", "Cloud Solutions Engineer"
    ],
    
    # Security roles
    "Cybersecurity Engineer": [
        "Security Engineer", "Information Security Engineer", "AppSec Engineer",
        "Application Security Engineer", "DevSecOps Engineer", "SOC Analyst",
        "Security Analyst", "Penetration Tester", "Security Architect",
        "Cloud Security Engineer", "Network Security Engineer", "Infosec Engineer",
        "Security Operations Engineer", "Threat Analyst", "Vulnerability Engineer"
    ],
    
    # Product/Design roles
    "Product Manager": [
        "Technical Product Manager", "Senior Product Manager", "Product Owner",
        "Associate Product Manager", "Staff Product Manager", "Principal PM",
        "Growth Product Manager", "Platform Product Manager", "Data Product Manager",
        "AI Product Manager", "Product Lead", "Director of Product",
        "Product Strategy Manager", "Product Operations Manager", "Technical PM"
    ],
    
    # Architecture roles
    "Software Architect": [
        "Solutions Architect", "Technical Architect", "Enterprise Architect",
        "Cloud Architect", "System Architect", "Application Architect",
        "Principal Engineer", "Staff Engineer", "Distinguished Engineer",
        "Technical Lead", "Engineering Manager", "Platform Architect",
        "Data Architect", "Security Architect", "Integration Architect"
    ]
}


def get_role_variations(role: str, exclude: Optional[List[str]] = None, max_variations: int = 15) -> List[str]:
    """
    Get role variations for "Load 5 more roles" feature.
    
    Args:
        role: Primary role to get variations for (e.g., "AI Engineer")
        exclude: List of roles to exclude (already searched)
        max_variations: Maximum number of variations to return (default 15 for 3x "Load 5 more")
    
    Returns:
        List of role variation titles, excluding already searched roles
    """
    exclude = exclude or []
    exclude_lower = set(r.lower() for r in exclude)
    
    # Add the primary role to exclusions
    exclude_lower.add(role.lower())
    
    # Step 1: Try exact match in ROLE_VARIATIONS_MAP
    role_title = role.strip().title()
    if role_title in ROLE_VARIATIONS_MAP:
        variations = ROLE_VARIATIONS_MAP[role_title]
        filtered = [v for v in variations if v.lower() not in exclude_lower]
        if DEBUG_DISCOVERY:
            print(f"🔄 Found {len(filtered)} variations for '{role}' (exact match)")
        return filtered[:max_variations]
    
    # Step 2: Try fuzzy matching (role contains a key or key contains role)
    role_lower = role.lower()
    for key, variations in ROLE_VARIATIONS_MAP.items():
        key_lower = key.lower()
        if key_lower in role_lower or role_lower in key_lower:
            filtered = [v for v in variations if v.lower() not in exclude_lower]
            if DEBUG_DISCOVERY:
                print(f"🔄 Found {len(filtered)} variations for '{role}' (fuzzy match via '{key}')")
            return filtered[:max_variations]
    
    # Step 3: Match by role category using keywords
    for category, config in ROLE_SITE_MAPPINGS.items():
        keywords = config["keywords"]
        if any(kw in role_lower for kw in keywords):
            # Find a matching role in ROLE_VARIATIONS_MAP from this category
            for key in ROLE_VARIATIONS_MAP.keys():
                key_lower = key.lower()
                if any(kw in key_lower for kw in keywords[:3]):  # Top 3 keywords
                    variations = ROLE_VARIATIONS_MAP[key]
                    filtered = [v for v in variations if v.lower() not in exclude_lower]
                    if DEBUG_DISCOVERY:
                        print(f"🔄 Found {len(filtered)} variations for '{role}' (category '{category}' via '{key}')")
                    return filtered[:max_variations]
    
    # Step 4: Fallback - use generic software engineering variations
    fallback_variations = ROLE_VARIATIONS_MAP.get("Software Engineer", [])
    filtered = [v for v in fallback_variations if v.lower() not in exclude_lower]
    if DEBUG_DISCOVERY:
        print(f"🔄 Using fallback variations for '{role}': {len(filtered)} roles")
    return filtered[:max_variations]


def get_next_roles_batch(primary_role: str, searched_roles: List[str], batch_size: int = 5) -> Tuple[List[str], bool]:
    """
    Get the next batch of roles to search for "Load 5 more" feature.
    
    Args:
        primary_role: The original role the user searched for
        searched_roles: List of roles already searched
        batch_size: Number of roles to return (default 5)
    
    Returns:
        Tuple of (list of next roles, has_more boolean)
    """
    MAX_TOTAL_ROLES = 20
    
    # Check if we've hit the limit
    total_searched = len(searched_roles)
    if total_searched >= MAX_TOTAL_ROLES:
        return [], False
    
    # Get all variations excluding already searched
    all_variations = get_role_variations(primary_role, exclude=searched_roles, max_variations=15)
    
    # Calculate how many we can return
    remaining_slots = MAX_TOTAL_ROLES - total_searched
    actual_batch_size = min(batch_size, remaining_slots, len(all_variations))
    
    next_roles = all_variations[:actual_batch_size]
    
    # Check if there are more after this batch
    remaining_variations = len(all_variations) - actual_batch_size
    future_slots = remaining_slots - actual_batch_size
    has_more = remaining_variations > 0 and future_slots > 0
    
    if DEBUG_DISCOVERY:
        print(f"📋 Next roles batch: {next_roles} (has_more={has_more}, total_searched={total_searched})")
    
    return next_roles, has_more


# State abbreviation to full name mapping
STATE_MAP = {
    "al": "alabama", "ak": "alaska", "az": "arizona", "ar": "arkansas", "ca": "california",
    "co": "colorado", "ct": "connecticut", "de": "delaware", "fl": "florida", "ga": "georgia",
    "hi": "hawaii", "id": "idaho", "il": "illinois", "in": "indiana", "ia": "iowa",
    "ks": "kansas", "ky": "kentucky", "la": "louisiana", "me": "maine", "md": "maryland",
    "ma": "massachusetts", "mi": "michigan", "mn": "minnesota", "ms": "mississippi", "mo": "missouri",
    "mt": "montana", "ne": "nebraska", "nv": "nevada", "nh": "new hampshire", "nj": "new jersey",
    "nm": "new mexico", "ny": "new york", "nc": "north carolina", "nd": "north dakota", "oh": "ohio",
    "ok": "oklahoma", "or": "oregon", "pa": "pennsylvania", "ri": "rhode island", "sc": "south carolina",
    "sd": "south dakota", "tn": "tennessee", "tx": "texas", "ut": "utah", "vt": "vermont",
    "va": "virginia", "wa": "washington", "wv": "west virginia", "wi": "wisconsin", "wy": "wyoming",
    "dc": "district of columbia"
}


@dataclass
class LocationPreference:
    city: str
    state: Optional[str] = None  # e.g. "TX"
    allow_remote: bool = False


def _normalize_state_token(token: str) -> Optional[str]:
    if not token:
        return None
    candidate = token.upper()
    if candidate in STATE_MAP:
        return candidate
    lower = token.lower()
    for abbr, full_name in STATE_MAP.items():
        if full_name == lower:
            return abbr.upper()
    return None


def parse_location(city_str: str) -> Optional[LocationPreference]:
    """
    Parse location string like "Austin, TX" or "San Francisco, CA" into LocationPreference.
    Returns None if parsing fails.
    """
    if not city_str or not city_str.strip():
        return None
    
    allow_remote = True  # default allow remote unless explicitly disallowed
    if re.search(r"\b(on[-\s]?site|onsite only|no remote)\b", city_str, re.IGNORECASE):
        allow_remote = False
    cleaned = re.sub(r"\b(remote|anywhere|global)\b", "", city_str, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return LocationPreference(city="Remote", state=None, allow_remote=True)
    
    # Try to parse "City, State" format
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if len(parts) >= 2:
        city = parts[0]
        state = _normalize_state_token(parts[1])
        return LocationPreference(city=city, state=state, allow_remote=allow_remote)
    
    # If no comma, try to extract state from end (e.g., "Austin TX")
    words = cleaned.split()
    if len(words) >= 2:
        last_word = words[-1]
        state = _normalize_state_token(last_word)
        if state:
            city = " ".join(words[:-1]).strip()
            return LocationPreference(city=city or cleaned, state=state, allow_remote=allow_remote)
    
    # Fallback: at least return city
    return LocationPreference(city=cleaned, state=None, allow_remote=allow_remote)


def format_location_phrase(pref: Optional[LocationPreference]) -> str:
    if not pref:
        return ""
    if pref.state:
        return f'"{pref.city}, {pref.state}"'
    return f'"{pref.city}"'


def compute_location_score(
    text: str,
    url: str,
    pref: Optional[LocationPreference],
) -> float:
    """
    Returns a multiplier in [0.0, 1.2] based on how well the job matches
    the preferred location.
    """
    if not pref:
        return 1.0  # No location preference, don't penalize
    
    # Combine text and URL for location checking
    combined_text = (text + " " + url).lower()
    city = pref.city.lower()
    state = pref.state.lower() if pref.state else None
    state_full = STATE_MAP.get(state, "") if state else ""
    
    if state:
        exact1 = f"{city}, {state}"
        exact2 = f"{city}, {state_full}" if state_full else ""
        if (exact1 and exact1 in combined_text) or (exact2 and exact2 in combined_text):
            return 1.2
        
        exact3 = f"{city} {state}"
        exact4 = f"{city} {state_full}" if state_full else ""
        if (exact3 and exact3 in combined_text) or (exact4 and exact4 in combined_text):
            return 1.2
    
    city_pattern = r'\b' + re.escape(city) + r'\b'
    city_match = bool(re.search(city_pattern, combined_text))
    
    state_match = False
    if state:
        state_pattern = r'\b' + re.escape(state) + r'\b'
        state_match = bool(re.search(state_pattern, combined_text))
        if not state_match and state_full:
            state_full_pattern = r'\b' + re.escape(state_full) + r'\b'
            state_match = bool(re.search(state_full_pattern, combined_text))
    
    if state and state_match and city_match:
        return 1.1
    if city_match:
        return 1.05 if not state else 1.0
    if state_match:
        return 0.9
    
    # Check for remote work
    remote_patterns = ["remote", "work from home", "wfh", "fully remote", "100% remote", "work remotely"]
    if pref.allow_remote and any(pattern in combined_text for pattern in remote_patterns):
        return 0.9
    
    # Default: heavily down-rank
    return 0.3


def _domain_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        return parsed.netloc or None
    except ValueError:
        if DEBUG_DISCOVERY: print(f"⚠️ Could not parse invalid URL: {url}")
        return None


def _text_within_recency_window(text: str, window_days: int = RECENCY_WINDOW_DAYS) -> bool:
    """
    Heuristic check to skip obviously stale postings.
    Returns False if the text clearly references a posting older than window_days.
    Otherwise returns True (cannot prove it's stale).
    """
    text_lower = text.lower()

    # Relative time patterns: "12 days ago", "3 weeks ago", etc.
    rel_pattern = re.findall(r'(\d+)\s+(hour|hours|day|days|week|weeks|month|months)\s+ago', text_lower)
    min_relative_days = None
    for num_str, unit in rel_pattern:
        try:
            num = int(num_str)
        except ValueError:
            continue
        if unit in ("hour", "hours"):
            days = max(num / 24.0, 0)
        elif unit in ("day", "days"):
            days = num
        elif unit in ("week", "weeks"):
            days = num * 7
        else:  # month(s)
            days = num * 30
        if min_relative_days is None or days < min_relative_days:
            min_relative_days = days
    if min_relative_days is not None:
        return min_relative_days <= window_days

    # Absolute dates like "March 12, 2024"
    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    date_pattern = re.findall(
        r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(20\d{2})',
        text_lower
    )
    today = datetime.utcnow().date()
    for month_str, day_str, year_str in date_pattern:
        month = month_map.get(month_str.lower())
        if not month:
            continue
        try:
            day = int(day_str)
            year = int(year_str)
            date_value = datetime(year, month, day).date()
        except ValueError:
            continue
        delta = (today - date_value).days
        if 0 <= delta <= window_days:
            return True
        if delta > window_days:
            return False

    # If no recency hints were found, assume acceptable (can't prove stale)
    return True


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
            "ai engineer", "artificial intelligence engineer",
            "machine learning engineer", "ml engineer", "mlops engineer",
            "ai/ml engineer", "applied scientist", "research engineer", 
            "deep learning engineer", "nlp engineer",
            "senior ai engineer", "lead ai engineer",
            "llm engineer", "generative ai engineer", "prompt engineer",
            "ai platform engineer", "ml infrastructure engineer"
        ]
    elif "machine learning engineer" in r or "ml engineer" in r:
        base += [
            "machine learning engineer", "ml engineer", "mlops engineer",
            "ai engineer", "applied scientist", "research scientist",
            "deep learning engineer", "computer vision engineer"
        ]
    elif "data engineer" in r:
        base += [
            "data engineer", "analytics engineer", "etl engineer", 
            "data warehouse engineer", "data platform engineer",
            "pipeline engineer", "big data engineer"
        ]
    elif "full" in r and "stack" in r:
        base += [
            "full stack engineer", "full-stack engineer", 
            "software engineer", "web developer",
            "fullstack developer", "application developer"
        ]
    elif "frontend" in r or "front-end" in r:
        base += [
            "frontend engineer", "front-end engineer",
            "ui engineer", "react developer", "javascript developer",
            "web developer"
        ]
    elif "backend" in r or "back-end" in r:
        base += [
            "backend engineer", "back-end engineer",
            "api engineer", "server engineer", "platform engineer"
        ]
    elif "java" in r:
        base += ["java engineer", "java developer", "backend engineer", "software engineer", "spring developer"]
    elif "data analyst" in r:
        base += ["data analyst", "analytics", "bi analyst", "business intelligence analyst", "business analyst"]
    
    # include keywords as loose synonyms
    for kw in role_keywords:
        if len(kw) >= 2:
            base.append(kw)
            # Add combinations with common variations for short keywords
            if len(kw.split()) == 1:
                for var in common_variations:
                    base.append(f"{kw} {var}")
    
    # de-dup and clean
    out = []
    seen = set()
    for t in base:
        t = t.strip().lower()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    
    return out


def _is_allowed_domain(url: str) -> bool:
    domain = _domain_from_url(url) or ""
    return any(d in domain for d in ALLOWED_JOB_DOMAINS)


def _is_preferred_domain(url: str) -> bool:
    """Check if URL is from a preferred quality job site"""
    domain = _domain_from_url(url) or ""
    return any(d in domain for d in PREFERRED_JOB_DOMAINS)


def _is_aggregator_domain(url: str) -> bool:
    """Check if URL is from an aggregator site (lower priority)"""
    domain = _domain_from_url(url) or ""
    return any(d in domain for d in AGGREGATOR_DOMAINS)


def _is_curated_domain(url: str) -> bool:
    domain = _domain_from_url(url) or ""
    return any(d in domain for d in CURATED_JOB_DOMAINS)


def _matches_curated_filters(normalized: dict, role: str, location: str) -> bool:
    job_data = normalized.get("job_posting", {}) if normalized else {}
    url = job_data.get("apply_url") or job_data.get("source_url") or ""
    if not url or not _is_curated_domain(url):
        return False

    title = (job_data.get("title") or "").lower()
    snippet = " ".join(job_data.get("highlights", [])) if job_data.get("highlights") else ""
    text_blob = f"{title} {snippet}".lower()

    role_tokens = [token for token in re.split(r"\W+", role.lower()) if len(token) >= 3]
    if role_tokens and not any(token in title for token in role_tokens):
        return False

    location = (location or "").strip().lower()
    if location:
        if location not in text_blob and "remote" not in text_blob and "anywhere" not in text_blob:
            return False

    return True


def _looks_like_listing_page(url: str, title: str) -> bool:
    url_low = (url or "").lower()
    title_low = (title or "").lower()

    if any(pat in url_low for pat in LISTING_PATTERNS):
        return True

    # Very generic SEO titles
    listing_title_patterns = [
        r".+\sjobs in\s.+",
        r"best .+ jobs",
        r"top .+ jobs",
        r"jobs at .+",
        r"careers at .+",
        r"open positions",
    ]
    return any(re.search(pat, title_low) for pat in listing_title_patterns)


def _looks_like_detail_page(url: str, title: str, terms: List[str]) -> bool:
    """
    Heuristic: treat URLs that look like a single posting as a detail page.
    """
    url_low = (url or "").lower()
    title_low = (title or "").lower()
    path = urlparse(url or "").path.lower()

    # Common ATS/job detail hints
    detail_hints = [
        "/jobs/", "/job/", "/careers/", "/position/", "/positions/", 
        "/openings/", "/opportunities/", "/o/", "/j/"
    ]
    if any(h in path for h in detail_hints):
        return True

    # If the title matches role terms and NOT listing patterns
    term_match = any(term in title_low for term in terms)
    listing_marker = " jobs" in title_low or "careers" in title_low
    
    if term_match and not listing_marker:
        return True

    return False


def _title_match_strength(title: str, terms: List[str]) -> int:
    """
    0 = No match
    1 = Partial match
    2 = Exact match (term is a substring of title)
    """
    title_low = (title or "").lower()
    if not title_low:
        return 0
        
    # Check for any term appearing in title
    for t in terms:
        if t in title_low:
            return 2
            
    return 0


def _clean_listing_title(title: str) -> str:
    if not title:
        return ""
    t = title.strip()
    # Drop common location suffixes following "jobs in ..."
    t = re.sub(r"\s+jobs in\s+.*$", "", t, flags=re.IGNORECASE)
    # Remove trailing "jobs" / "job openings"
    t = re.sub(r"\s+jobs?$", "", t, flags=re.IGNORECASE)
    return t.strip()


async def _second_hop_from_listing(row: dict, terms: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Second-hop extraction for listing pages.
    CRITICAL: FILTER OUT LISTING PAGES - only return REAL JOB POSTINGS.
    
    ROOT CAUSE FIX: Now properly extracts URLs from <a href> tags in HTML,
    resolves relative URLs, and filters for actual job postings.
    """
    url = row.get("url", "")
    if not url:
        return None, None

    if DEBUG_DISCOVERY:
        print(f"    🔍 Performing second hop on: {url}")

    html_text = await fetch_url_content(url, max_chars=SECOND_HOP_MAX_CHARS)
    if not html_text:
        return None, None

    # CRITICAL FIX: Extract URLs from <a href> tags, not just raw text
    # This is the root cause - we were missing URLs that are in HTML attributes
    candidates = []
    
    # Method 1: Extract from <a href="..."> tags (most reliable)
    # Handle both single and double quotes
    href_patterns = [
        r'<a[^>]+href=["\']([^"\']+)["\']',  # Standard href="url"
        r'href=["\']([^"\']+)["\']',  # Just href="url" anywhere
    ]
    
    for pattern in href_patterns:
        matches = re.finditer(pattern, html_text, re.IGNORECASE)
        for match in matches:
            href = match.group(1).strip()
            if href:
                # Resolve relative URLs to absolute URLs
                absolute_url = urljoin(url, href)
                # Remove fragments and query params that might be tracking
                parsed = urlparse(absolute_url)
                # Keep query params but remove common tracking params
                query_parts = []
                if parsed.query:
                    for param in parsed.query.split('&'):
                        key = param.split('=')[0].lower()
                        # Keep job-related params, remove tracking
                        if key not in ['utm_source', 'utm_medium', 'utm_campaign', 'ref', 'source']:
                            query_parts.append(param)
                clean_query = '&'.join(query_parts) if query_parts else ''
                clean_url = urlunparse((
                    parsed.scheme, parsed.netloc, parsed.path,
                    parsed.params, clean_query, ''  # Remove fragment
                ))
                if clean_url not in candidates:
                    candidates.append(clean_url)
    
    # Method 2: Also extract absolute URLs from text (fallback)
    # But prioritize href tags
    text_urls = re.findall(r"https?://[^\s\"')<>\[\]]+", html_text)
    for text_url in text_urls:
        # Clean up common trailing characters
        text_url = text_url.rstrip('.,;:!?)')
        if text_url not in candidates:
            candidates.append(text_url)
    
    if DEBUG_DISCOVERY:
        print(f"    📋 Found {len(candidates)} candidate URLs in HTML")
    
    candidate_scores: List[Tuple[str, int]] = []

    for cand in candidates[:60]:  # Check more candidates now that we're finding them properly
        # Filter out garbage file types
        if re.search(r"\.(png|jpg|jpeg|gif|svg|pdf|css|js|ico|woff|woff2|ttf|eot)$", cand, re.IGNORECASE):
            continue
        if any(s in cand for s in ["twitter.com", "facebook.com", "youtube.com", "instagram.com", "linkedin.com"]):
            continue
        
        # Skip the source URL itself (the listing page)
        if cand == url or cand in url:
            continue
        
        # CRITICAL: Check if this is a listing page - FILTER IT OUT
        cand_low = cand.lower()
        is_listing_candidate = _looks_like_listing_page(cand, "")
        if is_listing_candidate:
            if DEBUG_DISCOVERY:
                print(f"    ⚠️ Filtering out listing page from second-hop: {cand[:60]}")
            continue  # Skip listing pages
            
        score = 0
        
        # Heavy bonus for preferred ATS domains (Ashby, Lever, Greenhouse, Wellfound)
        if _is_preferred_domain(cand):
            score += 20  # Increased priority for quality job sites
        
        # Bonus for allowed domains (other ATS systems)
        if _is_allowed_domain(cand):
            score += 8  # Increased bonus
        
        # Bonus for detail-like paths (REAL job postings)
        if _looks_like_detail_page(cand, "", terms):
            score += 10  # Increased bonus for detail pages
        
        # Bonus for job ID patterns (common in ATS URLs like /jobs/abc123xyz)
        # Look for patterns like /jobs/abc123 or /job/xyz789
        if re.search(r'/(?:job|jobs|career|careers|position|positions|opening|openings|opportunity|opportunities)/[a-z0-9\-]{6,}', cand_low):
            score += 8  # Strong indicator of job posting
        
        # Bonus for long alphanumeric IDs (common in ATS systems)
        if re.search(r'/[a-z0-9]{10,}', cand_low):  # Longer IDs are more likely job postings
            score += 5
        
        # Bonus for ATS-specific patterns
        ats_patterns = [
            "ashbyhq.com", "jobs.ashbyhq.com", "lever.co", "jobs.lever.co",
            "greenhouse.io", "boards.greenhouse.io", "wellfound.com/jobs",
            "ycombinator.com/jobs", "workable.com", "smartrecruiters.com"
        ]
        if any(pattern in cand_low for pattern in ats_patterns):
            score += 15  # Very strong indicator
        
        # Bonus for role terms in URL
        if any(t in cand_low for t in terms):
            score += 3
        
        # Penalize aggregator domains (Indeed, Glassdoor, etc.) - but less harshly
        # Sometimes aggregators link to real job postings
        if _is_aggregator_domain(cand):
            score -= 5  # Reduced penalty - might still be a valid link
        
        # Only consider candidates with positive score (real job postings)
        if score > 0:
            candidate_scores.append((cand, score))
            if DEBUG_DISCOVERY:
                print(f"    ✅ Candidate URL: {cand[:70]} (score: {score})")

    if not candidate_scores:
        if DEBUG_DISCOVERY:
            print(f"    ⚠️ No valid job postings found in second-hop (checked {len(candidates)} URLs)")
        return None, None

    # Sort by score and get best
    candidate_scores.sort(key=lambda x: x[1], reverse=True)
    best_url, best_score = candidate_scores[0]

    if DEBUG_DISCOVERY:
        print(f"    ✅ Second-hop found job posting: {best_url[:80]} (score: {best_score})")

    # Try to extract company name and better title from HTML around the URL
    best_title = _clean_listing_title(row.get("title", "")) or row.get("title", "")
    
    # Find the context around the best URL in the HTML
    url_index = html_text.find(best_url)
    if url_index >= 0:
        # Extract 300 chars before and after the URL for better context
        context_start = max(0, url_index - 300)
        context_end = min(len(html_text), url_index + len(best_url) + 300)
        context = html_text[context_start:context_end]
        
        # Try to extract job title from link text (between <a> and </a>)
        link_pattern = rf'<a[^>]*href=["\']?{re.escape(best_url)}["\']?[^>]*>(.*?)</a>'
        link_match = re.search(link_pattern, context, re.IGNORECASE | re.DOTALL)
        if link_match:
            link_text = re.sub(r'<[^>]+>', '', link_match.group(1)).strip()  # Remove HTML tags
            if link_text and len(link_text) > 5 and len(link_text) < 100:
                best_title = link_text
                if DEBUG_DISCOVERY:
                    print(f"    📝 Extracted title from link text: {best_title}")
        
        # Try to extract company name from context
        company_from_context = _extract_company_from_title(context[:200], best_url)
        if company_from_context and company_from_context.lower() not in ["unknown", "unknown company"]:
            # If we found a company, try to build a better title
            if best_title and company_from_context.lower() not in best_title.lower():
                # Title might be "Role at Company" format
                if " at " not in best_title.lower():
                    best_title = f"{best_title} at {company_from_context}"
    
    return best_url, best_title


def _extract_source_from_url(url: str) -> Optional[str]:
    """Extract a human-friendly source name from a URL."""
    if not url:
        return None
    url_lower = url.lower()
    
    source_map = {
        "linkedin.com": "LinkedIn",
        "indeed.com": "Indeed",
        "ziprecruiter.com": "ZipRecruiter",
        "glassdoor.com": "Glassdoor",
        "wellfound.com": "Wellfound",
        "angel.co": "AngelList",
        "lever.co": "Lever",
        "greenhouse.io": "Greenhouse",
        "ashbyhq.com": "Ashby",
        "workable.com": "Workable",
        "smartrecruiters.com": "SmartRecruiters",
        "bamboohr.com": "BambooHR",
        "myworkdayjobs.com": "Workday",
        "icims.com": "iCIMS",
        "jazzhr.com": "JazzHR",
        "ycombinator.com": "YC Jobs",
        "builtin.com": "BuiltIn",
        "builtinsf.com": "BuiltIn SF",
        "builtinnyc.com": "BuiltIn NYC",
        "dice.com": "Dice",
        "monster.com": "Monster",
        "careerbuilder.com": "CareerBuilder",
    }
    
    for domain, name in source_map.items():
        if domain in url_lower:
            return name
    return None


def _extract_company_from_title(title: str, url: str, snippet: str = "") -> Optional[str]:
    """
    Try to extract company name from title, URL, or snippet using common patterns.
    CRITICAL: For aggregator sites (Indeed, Glassdoor), extract company name from snippet/title.
    Returns None if no clear company can be identified.
    """
    if not title:
        title = ""
    
    combined_text = f"{title} {snippet}".strip()
    
    # Pattern 1: "Role at Company" or "Company - Role" or "Company | Role"
    patterns = [
        r" at ([A-Z][a-zA-Z0-9\s&\-\.]+)(?:\s*[\|\-]|$)",  # "Role at Company"
        r"^([A-Z][a-zA-Z0-9\s&\-\.]+)\s*[\|\-]\s*",        # "Company | Role" or "Company - Role"
        r"^([A-Z][a-zA-Z0-9\s&\-\.]+)\s+is\s+hiring",      # "Company is hiring"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            company = match.group(1).strip()
            # Clean up common suffixes
            company = re.sub(r"\s*(Jobs?|Careers?|Hiring|Openings?)\s*$", "", company, flags=re.IGNORECASE)
            # Filter out false positives
            if (company and len(company) > 1 and len(company) < 100 and
                not company.lower() in ["indeed", "glassdoor", "ziprecruiter", "job", "hiring", "search"]):
                return company
    
    # Pattern 2: Extract from aggregator snippets (Indeed/Glassdoor often have "Company Name" in snippet)
    # Look for patterns like "Upliftly Hybrid work" or "Company Name | Location"
    snippet_patterns = [
        r"^([A-Z][a-zA-Z0-9\s&\-\.]+?)(?:\s+\||\s+Hybrid|\s+Remote|\s+Contract|\s+\$)",  # "Company | ..." or "Company Hybrid"
        r"at\s+([A-Z][a-zA-Z0-9\s&\-\.]+?)(?:\s|$|,|\.)",  # "at Company"
        r"([A-Z][a-zA-Z0-9\s&\-\.]+?)\s+is\s+hiring",      # "Company is hiring"
    ]
    
    for pattern in snippet_patterns:
        match = re.search(pattern, combined_text)
        if match:
            company = match.group(1).strip()
            # Filter out false positives
            if (company and len(company) > 2 and len(company) < 50 and
                not company.lower() in ["indeed", "glassdoor", "ziprecruiter", "job", "hiring", "search", 
                                        "apply", "new", "often", "responds", "within", "day", "hour"]):
                return company
    
    # Pattern 3: Extract from URL parameters (Indeed uses ?cmp=CompanyName)
    if url:
        url_match = re.search(r'[?&]cmp=([^&]+)', url, re.IGNORECASE)
        if url_match:
            company = url_match.group(1)
            # URL decode
            try:
                from urllib.parse import unquote
                company = unquote(company).replace('+', ' ').strip()
            except:
                pass
            if company and len(company) > 2 and len(company) < 50:
                return company
    
    return None


def _extract_location_from_text(title: str, snippet: str, url: str) -> Optional[str]:
    """
    Extract location from title, snippet, or URL.
    Returns None if no location can be determined.
    Never raises exceptions.
    """
    try:
        text_parts = [title or "", snippet or "", url or ""]
        combined_text = " ".join(text_parts).lower()
        
        # Check for remote work indicators first
        remote_patterns = [
            r"\bremote\b", r"\bwork from home\b", r"\bwfh\b", 
            r"\bfully remote\b", r"\b100% remote\b", r"\bwork remotely\b"
        ]
        is_remote = any(re.search(pattern, combined_text, re.IGNORECASE) for pattern in remote_patterns)
        
        # Try to extract city, state pattern
        # Pattern 1: "City, State" or "City, ST" (e.g., "San Francisco, CA")
        city_state_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b'
        match = re.search(city_state_pattern, " ".join(text_parts), re.IGNORECASE)
        if match:
            city = match.group(1)
            state = match.group(2).upper()
            location_str = f"{city}, {state}"
            if is_remote:
                location_str += " (Remote)"
            return location_str
        
        # Pattern 2: Major cities
        major_cities = [
            ("san francisco", "CA"), ("new york", "NY"), ("los angeles", "CA"),
            ("chicago", "IL"), ("houston", "TX"), ("phoenix", "AZ"),
            ("austin", "TX"), ("seattle", "WA"), ("boston", "MA"),
            ("denver", "CO"), ("atlanta", "GA"), ("miami", "FL"),
        ]
        for city, state in major_cities:
            if city in combined_text:
                location_str = f"{city.title()}, {state}"
                if is_remote:
                    location_str += " (Remote)"
                return location_str
        
        # If remote but no location found
        if is_remote:
            return "Remote"
        
        return None
    except Exception:
        return None


def _convert_normalized_to_job_posting(
    normalized: dict,
    default_title: str
) -> Optional[JobPosting]:
    """
    Convert normalized LLM result to JobPosting schema.
    Helper function to bridge normalizer output with existing JobPosting format.
    CRITICAL: Clean snippets and extract company names properly.
    """
    if not normalized or not normalized.get("job_posting"):
        return None
    
    job_data = normalized["job_posting"]
    
    # CRITICAL: Prefer apply_url (specific job posting) over source_url (listing page)
    # apply_url should point to the actual job posting, not the search results page
    job_url = job_data.get("apply_url") or job_data.get("source_url") or ""

    # HARD FILTER: skip aggregator listing/search pages (e.g., ZipRecruiter/Indeed search pages)
    if job_url and _is_aggregator_domain(job_url) and _looks_like_listing_page(job_url, job_data.get("title", "")):
        if DEBUG_DISCOVERY:
            print(f"    ❌ Skipping aggregator listing page: {job_url[:80]}...")
        return None
    
    # If apply_url is missing or same as source_url, and it's a listing page, try to extract from snippet
    if not job_url or (job_url == job_data.get("source_url") and normalized.get("kind") == "job_list_page"):
        # This means we still have a listing page URL - try to extract specific job URL
        snippet = " | ".join(job_data.get("highlights", [])) if job_data.get("highlights") else ""
        if snippet:
            from .job_result_normalizer import _extract_specific_job_url_from_snippet
            specific_url = _extract_specific_job_url_from_snippet(snippet, job_url)
            if specific_url:
                job_url = specific_url
                print(f"✅ Extracted specific job URL in conversion: {specific_url[:80]}...")
    
    # CRITICAL: Clean snippet to remove aggregator noise
    raw_snippet = " | ".join(job_data.get("highlights", []))[:500] if job_data.get("highlights") else ""
    from .job_result_normalizer import _clean_snippet_for_display
    cleaned_snippet = _clean_snippet_for_display(raw_snippet)
    
    # CRITICAL: Extract company name from title/snippet if not provided by LLM
    company_name = job_data.get("company_name")
    if not company_name or company_name.lower() in ["indeed", "glassdoor", "ziprecruiter"]:
        # Try to extract from title and snippet
        title = job_data.get("title") or default_title
        company_name = _extract_company_from_title(title, job_url, raw_snippet)
    
    # Convert normalized data to JobPosting format
    # If the URL still looks like a listing page on an aggregator, drop it
    if job_url and _is_aggregator_domain(job_url) and _looks_like_listing_page(job_url, job_data.get("title", "")):
        if DEBUG_DISCOVERY:
            print(f"    ❌ Rejecting aggregator listing page URL after normalization: {job_url[:80]}...")
        return None

    return JobPosting(
        url=job_url,  # Use the best URL we found (specific job posting preferred)
        title=job_data.get("title") or default_title,
        snippet=cleaned_snippet,  # Use cleaned snippet
        location=job_data.get("location"),
        company=company_name,  # Use extracted company name
        source=job_data.get("source_site"),
        is_ats=_is_allowed_domain(job_url),  # Check if the final URL is from an ATS
        is_listing=normalized.get("kind") == "job_list_page" and job_url == job_data.get("source_url"),  # Only mark as listing if we couldn't extract specific URL
        score=normalized.get("confidence", 0.0) * 100.0  # Convert 0.0-1.0 to 0-100 scale
    )


async def _extract_job_posting_with_llm(
    rows: List[dict],
    role: str,
    location_pref: Optional[LocationPreference] = None,
    search_query: str = "",
    experience_range: Optional[str] = None,
    max_results: int = 5
) -> List[JobPosting]:
    """
    NEW: LLM-based job posting extraction using JOB_RESULT_NORMALIZER.
    This replaces rule-based scoring with intelligent LLM parsing.
    """
    if not rows or not LLM_NORMALIZER_AVAILABLE:
        return None
    
    # === PRE-FILTER URLs before LLM processing ===
    # This saves LLM calls by rejecting obvious garbage (Indeed, Wikipedia, calendars, etc.)
    if DEBUG_DISCOVERY:
        print(f"    🔍 Pre-filtering {len(rows)} results before LLM...")
    
    filtered_rows = prefilter_urls(rows)
    
    if DEBUG_DISCOVERY:
        print(f"    📊 {len(filtered_rows)}/{len(rows)} passed pre-filter")
    
    if not filtered_rows:
        if DEBUG_DISCOVERY:
            print("    ⚠️ All results filtered out - skipping LLM")
        return []
    
    location_str = f"{location_pref.city}, {location_pref.state}" if location_pref and location_pref.state else (location_pref.city if location_pref else "")
    
    if DEBUG_DISCOVERY:
        print(f"    🤖 Using LLM-based normalization (processing {len(filtered_rows)} results)...")
    
    normalized_results = []
    
    # Normalize each search result with LLM
    for row in filtered_rows:
        try:
            url = row.get("url", "")
            if not url:
                continue
            
            # Skip excluded domains (e.g., LinkedIn)
            domain = _domain_from_url(url) or ""
            if any(excluded in domain for excluded in EXCLUDED_JOB_DOMAINS):
                continue
            
            # CRITICAL: Skip aggregator listing pages - they're useless without specific job URLs
            # Indeed/ZipRecruiter listing pages can't be parsed (JavaScript-loaded content)
            if _is_aggregator_domain(url) and _looks_like_listing_page(url, row.get("title", "")):
                if DEBUG_DISCOVERY:
                    print(f"    ❌ Skipping aggregator listing page: {url[:60]}...")
                continue
            
            normalized = await normalize_job_result(
                role_title=role,
                target_location=location_str,
                search_query=search_query or f'"{role}" "{location_str}"',
                source={
                    "url": url,
                    "title": row.get("title", ""),
                    "snippet": row.get("summary", "") or " ".join(row.get("highlights", [])),
                    "raw_html": None  # Optional - can add later for better parsing
                },
                experience_range=experience_range
            )
            
            # Filter by experience if specified
            if experience_range and normalized.get("job_posting"):
                job_posting = normalized.get("job_posting", {})
                seniority = job_posting.get("seniority", "unspecified")
                years_exp = job_posting.get("years_experience_required", "")
                
                # Experience range mapping
                exp_ranges = {
                    "0-1": ["intern", "junior", "entry level"],
                    "1-3": ["junior", "mid", "entry level"],
                    "3-5": ["mid", "senior"],
                    "5-8": ["senior", "staff"],
                    "8+": ["senior", "staff", "lead", "principal", "director"]
                }
                
                # Check if seniority matches experience range
                allowed_seniorities = exp_ranges.get(experience_range, [])
                seniority_lower = seniority.lower() if seniority else ""
                
                # Also check years_experience_required
                years_match = False
                if years_exp:
                    years_lower = years_exp.lower()
                    if experience_range == "0-1" and any(x in years_lower for x in ["0", "1", "entry", "new grad"]):
                        years_match = True
                    elif experience_range == "1-3" and any(x in years_lower for x in ["1", "2", "3", "1-3", "2+"]):
                        years_match = True
                    elif experience_range == "3-5" and any(x in years_lower for x in ["3", "4", "5", "3-5", "4+"]):
                        years_match = True
                    elif experience_range == "5-8" and any(x in years_lower for x in ["5", "6", "7", "8", "5-8", "7+"]):
                        years_match = True
                    elif experience_range == "8+" and any(x in years_lower for x in ["8", "9", "10", "8+", "10+"]):
                        years_match = True
                
                # Reject if seniority doesn't match and no years match
                if seniority_lower not in [s.lower() for s in allowed_seniorities] and not years_match and seniority_lower != "unspecified":
                    if DEBUG_DISCOVERY:
                        print(f"    ❌ Filtered by experience: seniority={seniority}, years={years_exp}, required={experience_range}")
                    normalized["is_relevant"] = False
                    normalized["confidence"] = normalized.get("confidence", 0.0) * 0.3  # Heavily downrank
                    normalized["reason"] = f"Experience mismatch: requires {seniority} but target is {experience_range} years"
            
            # Log LLM classification
            if DEBUG_DISCOVERY:
                kind = normalized.get("kind", "unknown")
                relevant = normalized.get("is_relevant", False)
                conf = normalized.get("confidence", 0.0)
                print(f"    🤖 LLM classified: kind={kind}, relevant={relevant}, confidence={conf:.2f}, reason={normalized.get('reason', 'N/A')[:50]}")
            
            # Keep results that have job postings - RELAXED filtering to get more results
            # The LLM might mark something as "not relevant" but it could still be useful
            kind = normalized.get("kind", "")
            is_relevant = normalized.get("is_relevant", False)
            has_job = normalized.get("job_posting") is not None
            confidence = normalized.get("confidence", 0.0)
            
            # RELAXED CRITERIA: Keep if:
            # 1. Has job posting AND is relevant (best case)
            # 2. Has job posting AND is job_list_page (listing pages can still have good jobs)
            # 3. Has job posting AND confidence > 0.2 (lowered from 0.3 to get more results)
            # 4. Has job posting AND is NOT noise (even low confidence jobs are better than nothing)
            if has_job and kind != "noise":
                # Much more lenient - keep almost anything with a job posting
                if is_relevant or kind == "job_list_page" or confidence > 0.2 or kind == "job_posting":
                    normalized_results.append(normalized)
                    if DEBUG_DISCOVERY:
                        print(f"    ✅ Kept: kind={kind}, relevant={is_relevant}, confidence={confidence:.2f}")
                elif DEBUG_DISCOVERY:
                    # Log why we're filtering it out
                    reason = normalized.get("reason", "N/A")
                    print(f"    ⚠️ Filtered out: kind={kind}, relevant={is_relevant}, confidence={confidence:.2f}, reason={reason[:60]}")
            elif DEBUG_DISCOVERY:
                # No job posting extracted
                reason = normalized.get("reason", "N/A")
                print(f"    ⚠️ No job posting: kind={kind}, relevant={is_relevant}, reason={reason[:60]}")
                
        except Exception as e:
            if DEBUG_DISCOVERY:
                print(f"    ⚠️ LLM normalization failed for row: {e}")
            continue  # Continue with other results
    
    if not normalized_results:
        if DEBUG_DISCOVERY:
            print(f"    ⚠️ No relevant jobs found by LLM normalizer")
        return []

    # RELAXED: Don't require curated-domain filters - allow results from any allowed domain
    # Only filter out excluded domains (LinkedIn, etc.)
    filtered_results = []
    for n in normalized_results:
        job_data = n.get("job_posting", {}) if n else {}
        url = job_data.get("apply_url") or job_data.get("source_url") or ""
        
        # Skip excluded domains
        if url and any(excluded in url.lower() for excluded in EXCLUDED_JOB_DOMAINS):
            continue
        
        # Prefer curated domains but don't require them
        # Check if URL is from an allowed domain (much broader than curated)
        if url and _is_allowed_domain(url):
            filtered_results.append(n)
        elif url:  # Even if not in allowed domains, check if it's a valid job URL
            # Allow if it looks like a job posting URL
            url_lower = url.lower()
            job_indicators = ["/job/", "/jobs/", "/careers/", "/position/", "lever.co", "greenhouse.io", "ashbyhq.com", "wellfound.com"]
            if any(indicator in url_lower for indicator in job_indicators):
                filtered_results.append(n)
    
    if not filtered_results:
        if DEBUG_DISCOVERY:
            print(f"    ⚠️ LLM results filtered out (no valid domains)")
        return None

    normalized_results = filtered_results
    
    # Separate direct job postings from listing pages
    direct_postings = [n for n in normalized_results if n.get("kind") == "job_posting"]
    listing_pages = [n for n in normalized_results if n.get("kind") == "job_list_page"]
    
    # Return up to max_results - prefer direct postings, but include listing pages if needed
    results_to_return: List[JobPosting] = []
    seen_urls: set[str] = set()
    seen_domains: set[str] = set()

    def _can_add(job: JobPosting) -> bool:
        """Ensure we don't return duplicate URLs and prefer domain diversity."""
        url = job.url or ""
        domain = _domain_from_url(url) or ""
        if not url or url in seen_urls:
            return False
        if domain in seen_domains:
            return False
        seen_urls.add(url)
        seen_domains.add(domain)
        return True

    def _force_add(job: JobPosting) -> bool:
        """Add even if domain already seen, but avoid exact URL dupes."""
        url = job.url or ""
        if not url or url in seen_urls:
            return False
        seen_urls.add(url)
        # keep domains set unchanged to allow further uniqueness checks
        return True
    
    # First, add direct postings (up to max_results)
    direct_postings_sorted = sorted(direct_postings, key=lambda x: x.get("confidence", 0.0), reverse=True)
    # Pass 1: unique domains
    for n in direct_postings_sorted:
        job_posting = _convert_normalized_to_job_posting(n, role)
        if job_posting and job_posting.url and not job_posting.is_listing:  # Ensure we have a valid direct URL
            if _can_add(job_posting):
                results_to_return.append(job_posting)
                if DEBUG_DISCOVERY:
                    job = n.get("job_posting", {})
                    print(f"    ✅ LLM selected direct job posting: {job.get('title', 'N/A')} (confidence: {n.get('confidence', 0.0):.2f})")
            if len(results_to_return) >= max_results:
                break

    # Pass 2: if still short, allow same-domain direct postings
    if len(results_to_return) < max_results:
        for n in direct_postings_sorted:
            job_posting = _convert_normalized_to_job_posting(n, role)
            if job_posting and job_posting.url and not job_posting.is_listing:
                if _force_add(job_posting):
                    results_to_return.append(job_posting)
                    if DEBUG_DISCOVERY:
                        job = n.get("job_posting", {})
                        print(f"    ✅ LLM added extra direct posting (same domain allowed): {job.get('title', 'N/A')} (confidence: {n.get('confidence', 0.0):.2f})")
            if len(results_to_return) >= max_results:
                break
    
    # If we don't have enough yet, try to extract from listing pages (up to remaining slots)
    if len(results_to_return) < max_results and listing_pages:
        listing_pages_sorted = sorted(listing_pages, key=lambda x: x.get("confidence", 0.0), reverse=True)
        for n in listing_pages_sorted:
            # Try to extract specific job URL from listing page
            job_data = n.get("job_posting", {})
            source_url = job_data.get("source_url")
            apply_url = job_data.get("apply_url")
            
            # Check if apply_url is actually a specific job URL
            is_apply_url_valid = False
            if apply_url and apply_url != source_url:
                apply_url_lower = apply_url.lower()
                listing_indicators = ["/jobs?", "/search?", "/job-search", "-jobs-", "/jobs/all", "/q-", "viewjob?jk="]
                is_listing_url = any(indicator in apply_url_lower for indicator in listing_indicators)
                detail_indicators = ["/job/", "/jobs/", "/careers/", "/position/", "lever.co", "greenhouse.io", "ashbyhq.com"]
                is_detail_url = any(indicator in apply_url_lower for indicator in detail_indicators)
                is_apply_url_valid = (not is_listing_url) or is_detail_url or _is_preferred_domain(apply_url)
            
            if apply_url and is_apply_url_valid:
                # LLM found a valid specific job URL - use it!
                job_posting = _convert_normalized_to_job_posting(n, role)
                if job_posting and job_posting.url:
                    if _can_add(job_posting):
                        results_to_return.append(job_posting)
                        if DEBUG_DISCOVERY:
                            print(f"    ✅ LLM extracted valid specific job URL from listing: {apply_url[:80]}...")
            else:
                # Try second-hop extraction
                try:
                    row_dict = {
                        "url": source_url or apply_url,
                        "title": job_data.get("title", ""),
                        "summary": " ".join(job_data.get("highlights", [])) if job_data.get("highlights") else ""
                    }
                    role_terms = [t.lower() for t in role.split() if len(t) > 3]
                    detail_url, detail_title = await _second_hop_from_listing(row_dict, role_terms)
                    
                    if detail_url:
                        # Create job posting from second-hop
                        job_data_copy = job_data.copy()
                        job_data_copy["source_url"] = detail_url
                        job_data_copy["apply_url"] = detail_url
                        job_data_copy["title"] = detail_title or job_data.get("title", role)
                        
                        job_posting = _convert_normalized_to_job_posting({
                            "kind": "job_posting",
                            "is_relevant": True,
                            "confidence": n.get("confidence", 0.0),
                            "reason": "Extracted from listing page via second-hop",
                            "job_posting": job_data_copy,
                            "listing_meta": None
                        }, role)
                        
                        if job_posting and job_posting.url:
                            if _can_add(job_posting):
                                results_to_return.append(job_posting)
                                if DEBUG_DISCOVERY:
                                    print(f"    ✅ Second-hop extracted specific job URL: {detail_url[:80]}...")
                except Exception as e:
                    if DEBUG_DISCOVERY:
                        print(f"    ⚠️ Second-hop extraction failed: {e}")
            if len(results_to_return) >= max_results:
                break

        # Pass 2 for listings: allow same-domain if still short
        if len(results_to_return) < max_results:
            for n in listing_pages_sorted:
                job_posting = _convert_normalized_to_job_posting(n, role)
                if job_posting and job_posting.url:
                    if _force_add(job_posting):
                        results_to_return.append(job_posting)
                        if DEBUG_DISCOVERY:
                            job = n.get("job_posting", {})
                            print(f"    ✅ Added extra listing-derived posting (same domain allowed): {job.get('title', 'N/A')} (confidence: {n.get('confidence', 0.0):.2f})")
                if len(results_to_return) >= max_results:
                    break
    
    if DEBUG_DISCOVERY:
        print(f"    📊 Returning {len(results_to_return)} job postings (max requested: {max_results})")
    
    return results_to_return
    
    # If only listing pages available, try to extract specific job URL
    # CRITICAL: Prefer LLM-extracted specific URLs, fallback to second-hop
    if listing_pages:
        # Select best listing page
        best_listing = max(listing_pages, key=lambda x: x.get("confidence", 0.0))
        job_data = best_listing.get("job_posting", {})
        source_url = job_data.get("source_url")
        apply_url = job_data.get("apply_url")
        
        # CRITICAL FIX: Check if apply_url is actually a specific job URL
        # The LLM might have set apply_url to the listing page URL
        is_apply_url_valid = False
        if apply_url and apply_url != source_url:
            # Check if apply_url looks like a listing page (not a real job posting)
            apply_url_lower = apply_url.lower()
            listing_indicators = ["/jobs?", "/search?", "/job-search", "-jobs-", "/jobs/all", "/q-", "viewjob?jk="]
            is_listing_url = any(indicator in apply_url_lower for indicator in listing_indicators)
            
            # Also check if it looks like a detail page
            detail_indicators = ["/job/", "/jobs/", "/careers/", "/position/", "lever.co", "greenhouse.io", "ashbyhq.com"]
            is_detail_url = any(indicator in apply_url_lower for indicator in detail_indicators)
            
            # Valid if it's not a listing URL OR if it's from a preferred ATS domain
            is_apply_url_valid = (not is_listing_url) or is_detail_url or _is_preferred_domain(apply_url)
        
        if apply_url and is_apply_url_valid:
            # LLM found a valid specific job URL - use it directly!
            if DEBUG_DISCOVERY:
                print(f"    ✅ LLM extracted valid specific job URL: {apply_url[:80]}... (skipping second-hop)")
            return _convert_normalized_to_job_posting(best_listing, role)
        
        # If apply_url is None, invalid, or is a listing page, we need second-hop extraction
        listing_url = source_url or apply_url
        
        if listing_url and DEBUG_DISCOVERY:
            reason = "no apply_url" if not apply_url else "apply_url is listing page" if apply_url else "apply_url == source_url"
            print(f"    ⚠️ LLM found listing page: {job_data.get('title', 'N/A')} ({reason}) - attempting second-hop extraction...")
        
        # Try second-hop extraction to get specific job URL
        if listing_url:
            try:
                # Create a row dict for second_hop function
                row_dict = {
                    "url": listing_url,
                    "title": best_listing.get("job_posting", {}).get("title", ""),
                    "summary": best_listing.get("job_posting", {}).get("highlights", ["Listing page"])[0] if best_listing.get("job_posting", {}).get("highlights") else ""
                }
                
                # Extract role terms from the role string
                role_terms = [t.lower() for t in role.split() if len(t) > 3]
                
                # Perform second-hop extraction
                detail_url, detail_title = await _second_hop_from_listing(row_dict, role_terms)
                
                if detail_url:
                    if DEBUG_DISCOVERY:
                        print(f"    ✅ Second-hop extracted specific job URL: {detail_url[:80]}...")
                    
                    # Create new normalized result with the specific job URL
                    job_data = best_listing.get("job_posting", {}).copy()
                    job_data["source_url"] = detail_url
                    job_data["apply_url"] = detail_url
                    job_data["title"] = detail_title or job_data.get("title", role)
                    
                    # CRITICAL: Clean snippet and extract company name
                    raw_snippet = " | ".join(job_data.get("highlights", []))[:500] if job_data.get("highlights") else ""
                    from .job_result_normalizer import _clean_snippet_for_display
                    cleaned_snippet = _clean_snippet_for_display(raw_snippet)
                    job_data["highlights"] = [cleaned_snippet] if cleaned_snippet else []
                    
                    # Extract company name if not present
                    if not job_data.get("company_name") or job_data.get("company_name", "").lower() in ["indeed", "glassdoor", "ziprecruiter"]:
                        company_name = _extract_company_from_title(detail_title or job_data.get("title", ""), detail_url, raw_snippet)
                        if company_name:
                            job_data["company_name"] = company_name
                    
                    # Convert to JobPosting
                    return _convert_normalized_to_job_posting({
                        "kind": "job_posting",  # Now it's a direct posting
                        "is_relevant": True,
                        "confidence": best_listing.get("confidence", 0.0),
                        "reason": "Extracted from listing page via second-hop",
                        "job_posting": job_data,
                        "listing_meta": None
                    }, role)
                else:
                    if DEBUG_DISCOVERY:
                        print(f"    ⚠️ Second-hop extraction failed - no specific job URL found")
            except Exception as e:
                if DEBUG_DISCOVERY:
                    print(f"    ⚠️ Second-hop extraction error: {e}")
        
        # CRITICAL: Reject listing pages that don't have specific job URLs
        # We don't want to return Indeed/Glassdoor search pages - they're not useful
        # ESPECIALLY reject aggregator domains (Indeed, ZipRecruiter) - they use JavaScript and can't be parsed
        listing_url = source_url or apply_url
        if listing_url and _is_aggregator_domain(listing_url):
            if DEBUG_DISCOVERY:
                job = best_listing.get("job_posting", {})
                print(f"    ❌ Rejecting aggregator listing page (Indeed/ZipRecruiter/etc): {job.get('title', 'N/A')}")
            return None  # Never return aggregator listing pages - they're useless
        
        if DEBUG_DISCOVERY:
            job = best_listing.get("job_posting", {})
            print(f"    ❌ Rejecting listing page (no specific job URL): {job.get('title', 'N/A')}")
        return None  # Don't return listing pages without specific job URLs
    
    return None


async def _extract_job_posting(
    rows: List[dict], 
    terms: List[str], 
    default_title: str,
    location_pref: Optional[LocationPreference] = None,
    role: str = "",  # Added for LLM normalizer
    search_query: str = "",  # Added for LLM normalizer
    experience_range: Optional[str] = None  # Added for experience filtering
) -> Optional[JobPosting]:
    """
    ROBUST extraction logic that NEVER crashes and returns partial results:
    1. Prefers ALLOWED_JOB_DOMAINS but doesn't require them
    2. Accepts both detail pages AND listing pages
    3. Missing fields (location, company) are OK - we set them to None
    4. Only drops candidates that are clearly NOT job-related
    
    NEW: If USE_LLM_NORMALIZER is enabled, uses LLM-based parsing instead of rule-based scoring.
    """
    if not rows:
        return None
    
    # NEW: Try LLM-based normalization first if enabled
    if USE_LLM_NORMALIZER and LLM_NORMALIZER_AVAILABLE:
        try:
            llm_results = await _extract_job_posting_with_llm(
                rows=rows,
                role=role or default_title,
                location_pref=location_pref,
                search_query=search_query,
                experience_range=experience_range,
                max_results=5  # Get up to 5 results
            )
            if llm_results:
                if DEBUG_DISCOVERY:
                    print(f"    ✅ LLM normalizer found {len(llm_results)} results")
                # Return first result for backward compatibility, but caller can be updated to use all
                return llm_results[0] if len(llm_results) == 1 else llm_results
            # LLM processed everything and found nothing relevant
            # DON'T fall back to rule-based - LLM is smarter
            # Only fall back if LLM had an error
            if DEBUG_DISCOVERY:
                print(f"    ⚠️ LLM found no relevant jobs - returning None (no fallback)")
            return None  # Don't accept garbage via rule-based fallback
        except Exception as e:
            if DEBUG_DISCOVERY:
                print(f"    ⚠️ LLM normalization error: {e}, falling back to rule-based extraction")
                import traceback
                traceback.print_exc()
            # Only fall back to rule-based on LLM ERROR, not when LLM correctly says "no jobs"
    
    # OLD: Rule-based extraction (fallback ONLY when LLM is disabled or had an error)

    scored_rows: List[Tuple[float, dict]] = []
    
    # Role words for title checking (simple heuristic from terms)
    role_broad_words = []
    for t in terms:
        words = t.split()
        if len(words) > 0:
            role_broad_words.extend([w.lower() for w in words if len(w) > 3])
    role_broad_words = list(set(role_broad_words))

    for row in rows:
        try:
            text_chunks = [row.get("summary", "")] + row.get("highlights", [])
            joined = " ".join([chunk for chunk in text_chunks if chunk])
            low = joined.lower()
            title = row.get("title", "") or ""
            title_low = title.lower()
            url = row.get("url", "") or ""
            domain = _domain_from_url(url) or ""

            # Skip explicitly excluded domains (e.g., LinkedIn)
            if any(excluded in domain for excluded in EXCLUDED_JOB_DOMAINS):
                continue
            
            combined_text = f"{title} {joined}"
            if not _text_within_recency_window(combined_text):
                if DEBUG_DISCOVERY:
                    print(f"    ⏳ Skipping stale posting '{title[:40]}' ({url[:40]}...)")
                continue

            # --- 1. Critical Filters (only drop OBVIOUSLY non-job content) ---
            
            # A. File types
            if url.lower().endswith(".pdf") or "pdf" in title_low.split():
                continue
                
            # B. Irrelevant content blocks - STRICT filtering
            skip_words = [
                "what is", "how to", "tutorial", "guide", "course", "exam", 
                "syllabus", "salary", "resume", "interview questions", 
                "seating arrangement", "admit card", "result", "news",
                "download", "driver", "printer", "support community",
                "student login", "pricing", "features", "migliori",
                "best software", "top 10", "black friday", "product ranking"
            ]
            if any(sw in title_low for sw in skip_words):
                if DEBUG_DISCOVERY:
                    print(f"    ❌ Skipping (garbage content): {title[:50]}")
                continue
            
            # C. Non-job domains - skip entirely
            garbage_domains = [
                "hp.com", "microsoft.com/en-us/azure", "tophat.com", 
                "ilprodottomigliore.it", "support.", "community."
            ]
            if any(gd in url.lower() for gd in garbage_domains):
                if DEBUG_DISCOVERY:
                    print(f"    ❌ Skipping (garbage domain): {url[:50]}")
                continue

            # --- 2. Scoring Components (RELAXED - don't drop, just downrank) ---
            
            score = 0.0
            
            # A. Domain Check (heavily boost preferred domains, moderate boost for allowed, penalize aggregators)
            is_preferred = _is_preferred_domain(url)
            is_aggregator = _is_aggregator_domain(url)
            is_allowed = _is_allowed_domain(url)
            
            if is_preferred:
                score += 25.0  # Heavy boost for preferred quality sites (Wellfound, Ashby, BuiltIn, etc.)
            elif is_allowed and not is_aggregator:
                score += 10.0  # Boost for other trusted domains
            elif is_aggregator:
                score -= 5.0   # Penalize aggregators (Indeed, Glassdoor) - prefer direct postings
            else:
                score -= 2.0   # REDUCED penalty for unknown domains (was -5)
                
            # B. Hiring Signals (RELAXED - reduced penalty)
            hiring_signals = ["job", "career", "hiring", "apply", "position", "opening", "vacancy", "recruit", "work"]
            has_signal = any(s in title_low or s in low for s in hiring_signals)
            if has_signal:
                score += 2.0
            else:
                score -= 3.0  # REDUCED penalty (was -10)
            
            # C. Recency Signals (boost for recent postings)
            recency_signals = ["posted", "ago", "days ago", "hours ago", "new", "just posted", "recently", "today", "yesterday"]
            has_recency = any(s in low for s in recency_signals)
            if has_recency:
                score += 2.0
                
            # D. Title / Role Match
            title_role_match = _title_match_strength(title, terms)
            if title_role_match == 2:  # Exact term match
                score += 5.0
            elif title_role_match == 1:  # Partial match
                score += 2.0
            else:
                # Fallback: check for broad role words
                if any(w in title_low for w in role_broad_words):
                    score += 1.0
                else:
                    score -= 2.0  # REDUCED penalty (was -5)
            
            # E. Listing vs Detail - HEAVILY PENALIZE LISTING PAGES
            is_listing = _looks_like_listing_page(url, title)
            is_detail = _looks_like_detail_page(url, title, terms)
            is_aggregator = _is_aggregator_domain(url)
            
            if is_detail:
                score += 5.0  # Strong boost for direct job postings
            if is_listing:
                # CRITICAL: Aggregator listing pages are completely useless - reject them
                if is_aggregator:
                    if DEBUG_DISCOVERY:
                        print(f"    ❌ Rejecting aggregator listing page: {url[:60]}...")
                    continue  # Skip entirely - don't even consider them
                # Other listing pages lose 80% of their score (multiply by 0.2)
                score = score * 0.2
                if DEBUG_DISCOVERY:
                    print(f"    ⚠️ Listing page detected - score reduced to {score:.1f}")
                
            # F. Location (RELAXED - don't drop, just downrank)
            loc_mult = compute_location_score(joined + " " + title, url, location_pref)
            # REMOVED: hard drop for loc_mult < 0.3
            # Instead, just apply the multiplier
            
            if DEBUG_DISCOVERY and location_pref and loc_mult < 0.5:
                print(f"    📍 Low location match for '{title[:40]}' (loc_mult={loc_mult:.2f}) - keeping anyway")
            
            # Final Score Calculation
            final_score = score * max(loc_mult, 0.5)  # Floor at 0.5 to prevent zeroing out
            
            if DEBUG_DISCOVERY:
                print(
                    f"    · Candidate '{title[:50]}' ({url[:40]}...) "
                    f"[allowed={is_allowed}, signal={has_signal}, listing={is_listing}, match={title_role_match}, loc={loc_mult:.2f}] "
                    f"-> score={final_score:.1f}"
                )

            # STRICTER threshold: Only accept results with positive score
            # Negative scores mean it's likely garbage (no hiring signals, wrong domain, etc.)
            if final_score > 0:
                scored_rows.append((final_score, {
                    **row, 
                    "joined": joined, 
                    "is_listing": is_listing,
                    "is_allowed": is_allowed,
                    "domain": domain
                }))
            elif DEBUG_DISCOVERY:
                print(f"    ❌ Rejected (score too low): {title[:50]} -> {final_score:.1f}")
                
        except Exception as e:
            # NEVER crash on a single row - log and continue
            if DEBUG_DISCOVERY:
                print(f"    ⚠️ Error processing row: {e}")
            continue

    if not scored_rows:
        # No valid results found - return None instead of accepting garbage
        if DEBUG_DISCOVERY:
            print(f"    ❌ No valid job postings found (all results filtered out)")
        return None

    # Sort best-first
    scored_rows.sort(key=lambda x: x[0], reverse=True)
    
    # CRITICAL: Filter out listing pages - prefer direct job postings
    # Only use listing pages if NO direct postings are available
    direct_postings = [(score, row) for score, row in scored_rows if not row.get("is_listing", False)]
    listing_pages = [(score, row) for score, row in scored_rows if row.get("is_listing", False)]
    
    if direct_postings:
        # Use best direct posting
        best_score, best_row = direct_postings[0]
        if DEBUG_DISCOVERY:
            print(f"    ✅ Selected direct job posting (score: {best_score:.1f})")
    elif listing_pages:
        # Fallback to listing page only if no direct postings
        best_score, best_row = listing_pages[0]
        if DEBUG_DISCOVERY:
            print(f"    ⚠️ No direct postings found, using listing page (score: {best_score:.1f})")
    else:
        # Should not happen, but handle gracefully
        best_score, best_row = scored_rows[0]
    
    # Extract metadata for the posting
    title = best_row.get("title") or default_title
    url = best_row.get("url", "")
    raw_snippet = best_row.get("joined", "")[:500]
    is_listing = best_row.get("is_listing", False)
    is_allowed = best_row.get("is_allowed", False)
    
    # CRITICAL: Clean snippet to remove aggregator noise and extract role descriptions
    from .job_result_normalizer import _clean_snippet_for_display
    snippet = _clean_snippet_for_display(raw_snippet)
    
    # Try to extract location, company, source
    # CRITICAL: Pass snippet to company extraction for aggregator sites
    location = _extract_location_from_text(title, raw_snippet, url)
    company = _extract_company_from_title(title, url, raw_snippet)
    source = _extract_source_from_url(url)

    # If best result is a listing, try second hop to find REAL job postings
    if is_listing:
        if DEBUG_DISCOVERY:
            print("    ℹ️ Best candidate is a listing, attempting second-hop...")
        try:
            detail_url, detail_title = await _second_hop_from_listing(best_row, terms)
            if detail_url:
                # Create posting from the second hop with full metadata
                # CRITICAL: Clean snippet and extract company name properly
                from .job_result_normalizer import _clean_snippet_for_display
                cleaned_snippet = _clean_snippet_for_display(snippet) if snippet else ""
                company_name = _extract_company_from_title(detail_title or title, detail_url, snippet)
                
                return JobPosting(
                    url=detail_url,
                    title=detail_title or title,
                    snippet=cleaned_snippet,
                    location=_extract_location_from_text(detail_title or title, snippet, detail_url),
                    company=company_name,
                    source=_extract_source_from_url(detail_url),
                    is_ats=_is_allowed_domain(detail_url),
                    is_listing=False,  # Second hop found a detail page
                    score=best_score
                )
        except Exception as e:
            if DEBUG_DISCOVERY: 
                print(f"    ⚠️ Second hop failed: {e} - using listing page as fallback")
            # Continue with the listing page as the result (don't fail!)
            
    # Return the best match with all metadata populated
    # CRITICAL: If location is missing, default to user query location
    final_location = location
    if not final_location and location_pref:
        # Default to user query location if posting location is missing
        if location_pref.state:
            final_location = f"{location_pref.city}, {location_pref.state}"
        else:
            final_location = location_pref.city
    elif not final_location:
        # If no location_pref, use "Not specified"
        final_location = "Not specified"
    
    return JobPosting(
        url=url,
        title=title,
        snippet=snippet,
        location=final_location,  # Use default if missing
        company=company,
        source=source,
        is_ats=is_allowed,
        is_listing=is_listing,
        score=best_score
    )


async def check_job_availability(
    company: CompanyIntel, 
    role: str,
    location_pref: Optional[LocationPreference] = None,
    max_results_per_company: int = 5,  # Changed default to 5
    enable_exa: bool = False,  # Ignored - always uses Tavily
    experience_range: Optional[str] = None  # Added for experience filtering
) -> Optional[JobPosting] | List[JobPosting]:
    """
    Determine whether the company lists an opening for the given role.
    Uses a single consolidated Tavily search query with location and recency.
    """
    # Diagnostic: Show if LLM normalizer is enabled
    if DEBUG_DISCOVERY:
        normalizer_status = "✅ ENABLED" if (USE_LLM_NORMALIZER and LLM_NORMALIZER_AVAILABLE) else "❌ DISABLED"
        company_display = company.name if company and hasattr(company, 'name') else "None"
        print(f"🔍 check_job_availability for {company_display} - LLM Normalizer: {normalizer_status}")
    
    prof = role_profile(role)
    role_keywords = prof.get("keywords", []) or []
    synonyms = _role_synonyms(role, role_keywords)

    # === SMART QUERY BUILDING ===
    # Check if company name is valid before including in query
    has_valid_company = (
        company is not None and 
        hasattr(company, 'name') and 
        company.name and 
        is_valid_company_name(company.name)
    )
    
    if has_valid_company:
        # Valid company - include in query
        company_part = f'"{company.name}"'
        if DEBUG_DISCOVERY:
            print(f"    ✅ Valid company name: {company.name}")
    else:
        # Invalid/missing company - search by role+location only
        company_part = ""
        if DEBUG_DISCOVERY:
            company_name = company.name if company and hasattr(company, 'name') else "None"
            print(f"    ⚠️ Invalid/missing company name: '{company_name}' - searching by role+location only")
    
    role_part = f'"{synonyms[0]}"' if synonyms else f'"{role}"'
    
    # Simple location - just the city if available
    location_part = ""
    if location_pref and location_pref.city:
        location_part = f'"{location_pref.city}"'
    
    # Top 3 skills only
    skills = role_keywords[:3] if role_keywords else []
    skills_str = " ".join(skills) if skills else ""
    
    # Query format optimized for direct job postings:
    # If no valid company, add extra job-finding terms to improve results
    if has_valid_company:
        # With company: focused query
        query_parts = [company_part, role_part, location_part, skills_str, "apply", "hiring"]
    else:
        # Without company: broader role+location search with job board terms
        query_parts = [role_part, location_part, skills_str, "jobs", "hiring", "apply", "openings"]
    
    base_query = " ".join([p for p in query_parts if p and p.strip()])
    
    print(f"🔎 job_search.check_job_availability base_query={base_query}")
    
    try:
        # First, try role-specific domain searches using tavily_search directly with domain filtering
        from ..tools.tavily_search import tavily_search
        
        all_hits: List[SearchHit] = []
        
        # Get optimal sites for this role (hybrid predefined + dynamic approach)
        # Uses only 2-3 sites per role for efficiency
        optimal_sites = get_optimal_sites_for_role(role, max_sites=3)
        
        if DEBUG_DISCOVERY:
            print(f"    🎯 Using role-optimized sites for '{role}': {optimal_sites}")
        
        # Search optimal sites with parallel async calls for efficiency
        async def search_site(domain: str):
            try:
                if DEBUG_DISCOVERY:
                    company_display = company.name if has_valid_company else "(role+location)"
                    print(f"    🔍 Searching {domain} for {company_display} {role}...")
                
                # Use tavily_search with domain filtering - increased num_results to get more candidates
                tavily_results = await tavily_search(
                    base_query,
                    num_results=5,  # Increased from 2 to 5 to get more candidates
                    search_depth="basic",
                    include_domains=[domain],
                    exclude_domains=EXCLUDED_JOB_DOMAINS
                )
                
                # Convert Tavily results to SearchHit format
                hits = []
                for result in tavily_results:
                    hits.append(SearchHit(
                        url=result.get("url", ""),
                        title=result.get("title", "") or "No title",
                        snippet=result.get("content", ""),
                        score=float(result.get("score", 0.0)) * 100.0
                    ))
                
                if tavily_results and DEBUG_DISCOVERY:
                    print(f"    ✅ Found {len(tavily_results)} results from {domain}")
                
                return hits
            except Exception as e:
                if DEBUG_DISCOVERY:
                    print(f"    ⚠️ Site search failed for {domain}: {e}")
                return []
        
        # Run Tavily site searches and the Exa ATS search in parallel.
        # Exa reaches direct apply-pages that Tavily's domain crawl often misses.
        exa_location = ""
        if location_pref and location_pref.city:
            exa_location = f"{location_pref.city}, {location_pref.state}" if location_pref.state else location_pref.city

        tasks = [search_site(domain) for domain in optimal_sites]
        tasks.append(search_ats_with_exa(role, exa_location, num_results=8))
        site_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        for site_hits in site_results:
            if isinstance(site_hits, Exception):
                if DEBUG_DISCOVERY:
                    print(f"    ⚠️ A provider search failed: {site_hits}")
                continue
            all_hits.extend(site_hits)

        all_hits = _dedupe_hits_by_url(all_hits)

        # Early exit if enough quality results found (optimization)
        # Increased limit to get more candidates for filtering
        if len(all_hits) >= 3:
            hits = all_hits[:10]  # Increased from 5 to 10 to get more candidates
            if DEBUG_DISCOVERY:
                print(f"    ✅ Using {len(hits)} results from role-optimized sites (early exit)")
        elif all_hits:
            hits = all_hits[:10]  # Increased from 5 to 10
            if DEBUG_DISCOVERY:
                print(f"    ✅ Using {len(hits)} results from role-optimized sites")
        else:
            # Fallback to general search - but exclude aggregator domains
            if DEBUG_DISCOVERY:
                print(f"    ⚠️ No role-optimized results, falling back to general search")
            hits: List[SearchHit] = await smart_search(
                base_query,
                max_results=10  # Increased from 5 to 10
            )
            # Filter out aggregator listing pages from general search results
            filtered_hits = []
            for hit in hits:
                # Skip aggregator listing pages - they're useless
                if _is_aggregator_domain(hit.url) and _looks_like_listing_page(hit.url, hit.title):
                    if DEBUG_DISCOVERY:
                        print(f"    ❌ Filtered out aggregator listing: {hit.url[:60]}...")
                    continue
                filtered_hits.append(hit)
            hits = filtered_hits

        if not hits:
            curated_location = ""
            if location_pref:
                curated_location = f"{location_pref.city}, {location_pref.state}" if location_pref.state else location_pref.city
            # Only include company in curated search if valid
            if has_valid_company:
                curated_role = f"{company.name} {role}".strip()
                company_hint = company.name
            else:
                curated_role = role
                company_hint = None
            # Use company_hint variable below
            curated_hits = await search_curated_job_boards(
                role=curated_role or role,
                location=curated_location,
                max_results=8,
                company_hint=company_hint
            )
            if curated_hits:
                hits = curated_hits
                if DEBUG_DISCOVERY:
                    print(f"    ✅ Using curated job-board results ({len(hits)} hits)")
            else:
                secondary_hits = await search_curated_job_boards(
                    role=role,
                    location=curated_location,
                    max_results=8
                )
                if secondary_hits:
                    hits = secondary_hits
                    if DEBUG_DISCOVERY:
                        print(f"    ✅ Using role-only curated results ({len(hits)} hits)")
        
        # Convert SearchHit objects to dict format for _extract_job_posting
        rows = []
        for hit in hits:
            rows.append({
                "title": hit.title,
                "url": hit.url,
                "summary": hit.snippet,
                "highlights": [hit.snippet] if hit.snippet else []
            })
        
        print(f"🔎 job_search.check_job_availability hits={len(hits)}")
        
        # Build search query for LLM normalizer context
        search_query_parts = [company_part, role_part, location_part, skills_str, "jobs"]
        search_query = " ".join([p for p in search_query_parts if p and p.strip()])
        
        posting_result = await _extract_job_posting(
            rows, 
            synonyms, 
            f"{role}" + (f" at {company.name}" if has_valid_company else ""), 
            location_pref,
            role=role,  # Pass role for LLM normalizer
            search_query=search_query,  # Pass search query for LLM normalizer
            experience_range=experience_range  # Pass experience range for filtering
        )
        
        if posting_result:
            if isinstance(posting_result, list):
                print(f"🔎 job_search.check_job_availability selected {len(posting_result)} postings")
                # Return list if multiple, first if single for backward compatibility
                return posting_result if len(posting_result) > 1 else posting_result[0]
            else:
                print(f"🔎 job_search.check_job_availability selected: {posting_result.title} ({posting_result.url})")
                return posting_result
        else:
            print(f"🔎 job_search.check_job_availability no valid posting found")
            return None
            
    except Exception as e:
        print(f"⚠️ job_search.check_job_availability failed: {e}")
        return None


def _dedupe_hits_by_url(hits: List[SearchHit]) -> List[SearchHit]:
    """Merge results from multiple providers. The same posting can appear with
    different query strings or trailing slashes, so key on host + path."""
    seen: set[str] = set()
    unique: List[SearchHit] = []
    for hit in hits:
        if not hit.url:
            continue
        try:
            parsed = urlparse(hit.url)
            key = f"{parsed.netloc.lower().removeprefix('www.')}{parsed.path.rstrip('/').lower()}"
        except Exception:
            key = hit.url
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique


# Applicant tracking systems host the real "apply" pages. Subdomains matter:
# bare lever.co/greenhouse.io are marketing sites, not job boards.
ATS_POSTING_DOMAINS = [
    "jobs.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.ashbyhq.com",
    "apply.workable.com",
    "wellfound.com",
]

# Postings older than this are usually filled or expired
ATS_MAX_POSTING_AGE_DAYS = 45


async def search_ats_with_exa(role: str, location: str, num_results: int = 8) -> List[SearchHit]:
    """
    Precision ATS search using Exa (Lever / Greenhouse / Ashby / Workable).
    Exa's neural search responds better to natural language than boolean/quoted
    queries, so we phrase this as a sentence rather than keyword tokens.
    """
    try:
        from ..tools.exa_search import exa_search
    except Exception as e:
        print(f"🛰️ search_ats_with_exa: Exa import failed: {e}")
        return []

    query = f"{role} job opening in {location}" if location else f"{role} job opening"
    cutoff = (datetime.utcnow() - timedelta(days=ATS_MAX_POSTING_AGE_DAYS)).strftime("%Y-%m-%d")
    try:
        results = await exa_search(
            query,
            include_domains=ATS_POSTING_DOMAINS,
            num_results=num_results,
            want_highlights=True,
            want_text=False,
            start_published_date=cutoff,
        )
    except Exception as e:
        print(f"🛰️ search_ats_with_exa: Exa search failed: {e}")
        return []

    hits: List[SearchHit] = []
    for res in results:
        snippet = " ".join(res.get("highlights", []) or [])
        if not snippet:
            snippet = res.get("text", "") or res.get("summary", "")
        hits.append(
            SearchHit(
                url=res.get("url", ""),
                title=res.get("title", ""),
                snippet=snippet or "",
                score=float(res.get("score", 0.0) or 0.0),
            )
        )
    return hits


def generate_job_search_queries(
    role_name: str,
    location: str,
    experience_range: str,
    filters_json: Optional[dict] = None
) -> dict:
    """
    Generate optimized search queries for job search.
    
    This function acts as a job-research agent that creates a small set of
    search queries optimized to return current, relevant job postings from
    web search engines (Tavily/Exa).
    
    Args:
        role_name: Target role (e.g., "AI Engineer", "Software Architect")
        location: Location preference (e.g., "San Francisco, CA", "Remote", "Austin, TX")
        experience_range: One of "0-1", "1-3", "3-5", "5-8", "8+"
        filters_json: Optional dict with extra filters like:
            - remote_only: bool
            - tech_stack: List[str]
            - company_size: str
            - etc.
    
    Returns:
        JSON dict with:
            - primary_query: str
            - supporting_queries: List[str] (2-4 queries)
            - keywords_boost: List[str]
            - keywords_exclude: List[str]
    """
    # Parse filters
    filters = filters_json or {}
    remote_only = filters.get("remote_only", False)
    tech_stack = filters.get("tech_stack", [])
    company_size = filters.get("company_size")
    
    # Map experience range to seniority terms
    experience_mapping = {
        "0-1": ["intern", "new grad", "entry level", "junior", "0-1 years"],
        "1-3": ["entry level", "junior", "mid-level", "1-3 years", "2+ years"],
        "3-5": ["mid-level", "senior", "3-5 years", "4+ years"],
        "5-8": ["senior", "staff", "5-8 years", "7+ years"],
        "8+": ["senior", "staff", "principal", "lead", "8+ years"]
    }
    
    # Get seniority terms for this experience range
    seniority_terms = experience_mapping.get(experience_range, [])
    
    # For entry-level (0-1, 1-3), avoid high-level terms
    exclude_high_level = experience_range in ["0-1", "1-3"]
    
    # Build location phrase
    location_lower = location.lower()
    is_remote = "remote" in location_lower or remote_only
    
    # Parse location for query building
    location_phrase = location
    if is_remote and not remote_only:
        # If location contains "remote", keep it
        location_phrase = location
    elif remote_only:
        location_phrase = "Remote"
    else:
        # Use location as-is (e.g., "San Francisco, CA")
        location_phrase = location
    
    # Build primary query - high precision, focused on direct job postings
    primary_parts = []
    
    # Role with quotes for exact match
    primary_parts.append(f'"{role_name}"')
    
    # Location
    if location_phrase and location_phrase.lower() != "remote":
        primary_parts.append(f'"{location_phrase}"')
    elif is_remote:
        primary_parts.append("remote")
    
    # Add top seniority term (most relevant)
    if seniority_terms:
        primary_parts.append(seniority_terms[0])
    
    # Add job action terms to find actual postings
    primary_parts.extend(["jobs", "hiring", "apply"])
    
    # Add tech stack if provided (limit to top 2)
    if tech_stack:
        primary_parts.extend(tech_stack[:2])
    
    primary_query = " ".join(primary_parts)
    
    # Build supporting queries (2-4 complementary queries)
    supporting_queries = []
    
    # Query 1: Company-focused (find companies hiring for this role)
    if not is_remote:
        company_query_parts = [f'"{role_name}"', f'"{location_phrase}"', "careers", "hiring"]
        if seniority_terms:
            company_query_parts.append(seniority_terms[0])
        supporting_queries.append(" ".join(company_query_parts))
    
    # Query 2: ATS-focused (find direct job postings on ATS platforms)
    ats_query_parts = [f'"{role_name}"', "jobs", "apply now"]
    if location_phrase and not is_remote:
        ats_query_parts.append(f'"{location_phrase}"')
    elif is_remote:
        ats_query_parts.append("remote")
    if seniority_terms and len(seniority_terms) > 1:
        ats_query_parts.append(seniority_terms[1])  # Use second term for variety
    supporting_queries.append(" ".join(ats_query_parts))
    
    # Query 3: Experience-focused (emphasize experience level)
    if seniority_terms and len(seniority_terms) >= 2:
        exp_query_parts = [f'"{role_name}"', seniority_terms[1], "position", "opening"]
        if location_phrase and not is_remote:
            exp_query_parts.append(f'"{location_phrase}"')
        elif is_remote:
            exp_query_parts.append("remote")
        supporting_queries.append(" ".join(exp_query_parts))
    
    # Query 4: Tech stack focused (if tech stack provided)
    if tech_stack and len(tech_stack) > 2:
        tech_query_parts = [f'"{role_name}"', tech_stack[2], "job"]
        if location_phrase and not is_remote:
            tech_query_parts.append(f'"{location_phrase}"')
        elif is_remote:
            tech_query_parts.append("remote")
        if seniority_terms:
            tech_query_parts.append(seniority_terms[0])
        supporting_queries.append(" ".join(tech_query_parts))
    
    # Ensure we have at least 2 supporting queries
    if len(supporting_queries) < 2:
        # Fallback: role + location + "job opening"
        fallback_parts = [f'"{role_name}"', "job opening"]
        if location_phrase and not is_remote:
            fallback_parts.append(f'"{location_phrase}"')
        elif is_remote:
            fallback_parts.append("remote")
        supporting_queries.append(" ".join(fallback_parts))
    
    # Limit to 4 supporting queries max
    supporting_queries = supporting_queries[:4]
    
    # Build keywords_boost - important phrases that MUST appear
    keywords_boost = [
        role_name,
        location_phrase if location_phrase else "",
    ]
    
    # Add experience terms
    keywords_boost.extend(seniority_terms[:3])  # Top 3 seniority terms
    
    # Add job action keywords
    keywords_boost.extend(["careers", "jobs", "apply", "hiring", "position"])
    
    # Add tech stack keywords (if provided)
    if tech_stack:
        keywords_boost.extend(tech_stack[:3])
    
    # Remove empty strings and deduplicate
    keywords_boost = [kw for kw in keywords_boost if kw and kw.strip()]
    keywords_boost = list(dict.fromkeys(keywords_boost))  # Preserve order, remove dupes
    
    # Build keywords_exclude - phrases to downrank/avoid
    keywords_exclude = [
        "interview questions",
        "job description template",
        "salary guide",
        "bootcamp",
        "top 10 jobs",
        f"how much does a {role_name} make",
        "salary range",
        "career advice",
        "resume tips",
        "interview prep",
    ]
    
    # For entry-level, exclude high-level terms
    if exclude_high_level:
        keywords_exclude.extend([
            "principal",
            "director",
            "VP",
            "vice president",
            "head of",
            "chief",
            "executive"
        ])
    
    # Add generic listicle patterns
    keywords_exclude.extend([
        "best jobs",
        "top jobs",
        "highest paying",
        "career path",
        "job market",
    ])
    
    # Remove duplicates
    keywords_exclude = list(dict.fromkeys(keywords_exclude))
    
    return {
        "primary_query": primary_query,
        "supporting_queries": supporting_queries,
        "keywords_boost": keywords_boost,
        "keywords_exclude": keywords_exclude
    }
