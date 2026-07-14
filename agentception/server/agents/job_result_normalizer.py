from __future__ import annotations
import os
import json
import re
from typing import Dict, Any, Optional, Literal
import httpx
from urllib.parse import urlparse, unquote

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")

# Page kind types
PageKind = Literal["job_posting", "job_list_page", "company_page", "noise"]
RemoteType = Literal["onsite", "hybrid", "remote", "unspecified"]
SeniorityType = Literal[
    "intern", "junior", "mid", "senior", "staff", "lead", 
    "director", "principal", "unspecified"
]
EmploymentType = Literal[
    "full-time", "part-time", "contract", "internship", "unspecified"
]
ListType = Literal["job_list", "category_page", "company_careers", "other"]


def create_normalizer_prompt(
    role_title: str,
    target_location: str,
    search_query: str,
    url: str,
    title: str,
    snippet: str,
    raw_html: Optional[str] = None,
    experience_range: Optional[str] = None
) -> str:
    """
    Creates the comprehensive prompt for JOB_RESULT_NORMALIZER agent.
    
    This prompt follows the user's exact specification:
    - Classifies page type (job_posting, job_list_page, company_page, noise)
    - Extracts structured job information
    - Determines relevance based on role, location, recency
    - Returns strict JSON only (no markdown)
    """
    
    # Prepare input text - use snippet + title, raw_html is optional
    input_text = f"Title: {title}\n\nSnippet: {snippet}"
    if raw_html:
        # Limit HTML to first 2000 chars to avoid token bloat
        html_preview = raw_html[:2000] if len(raw_html) > 2000 else raw_html
        input_text += f"\n\nRaw HTML (preview): {html_preview}"
    
    prompt = f"""You are JOB_RESULT_NORMALIZER, a precise web-job-search parsing agent.

Your ONLY job:

Given a single search result (title, URL, snippet, maybe raw HTML) and the target role + location, you must:

1. Decide what kind of page this is.
2. If it's a job posting, extract a clean, structured JSON object.
3. If it's a listing/aggregator page, still return normalized info.
4. Mark clearly whether it is relevant or not.

You are NOT allowed to:
- Hallucinate companies or jobs that are not clearly present in the text.
- Invent locations or dates.
- Output anything except valid JSON.

PRIORITY RULES:
- STRONGLY prefer job postings from quality sites: Wellfound, Ashby, Lever, Greenhouse, BuiltIn, YC Jobs
- Aggregator sites (Indeed, Glassdoor, ZipRecruiter, Dice) should be marked as "noise" or "job_list_page" with relevant=False UNLESS they contain a direct link to a company's ATS/job posting page
- Reject aggregator listing/search pages - they require JavaScript and cannot be parsed for job descriptions
- If URL contains "indeed.com/viewjob", "glassdoor.com/job-listing", or similar aggregator patterns, mark as relevant=False
- Only mark aggregator URLs as relevant=True if they clearly link to a direct company job posting (e.g., redirect to lever.co, greenhouse.io)

--------------------------------------------------

INPUT DATA

--------------------------------------------------

Target Role: {role_title}
Target Location: {target_location}
Search Query: {search_query}
{f'Target Experience: {experience_range} years (filter for jobs matching this experience level)' if experience_range else ''}

Source:
  URL: {url}
  Title: {title}
  Snippet: {snippet}
{'' if not raw_html else f'  Raw HTML: [truncated preview provided]'}

--------------------------------------------------

OUTPUT FORMAT (STRICT JSON ONLY)

--------------------------------------------------

You MUST return **ONLY** a single JSON object, no markdown, no comments, no code blocks.

Top-level schema:

{{
  "kind": "job_posting" | "job_list_page" | "company_page" | "noise",
  "is_relevant": true | false,
  "confidence": 0.0-1.0,
  "reason": "short natural language justification",
  "job_posting": {{ ... }} | null,
  "listing_meta": {{ ... }} | null
}}

Details:

1) If this looks like a **single job posting**, set:
   - "kind": "job_posting"
   - Fill `job_posting` with as much as you can.
   - `listing_meta` should be null.

2) If this looks like a **listing / search results page** (many roles on one page), set:
   - "kind": "job_list_page"
   - Extract the **most promising single job posting on that page** (the one best matching role & location) into `job_posting`.
   - CRITICAL: You MUST extract a SPECIFIC job URL from the snippet/title/raw HTML.
   - Look for URLs like:
     * "https://jobs.ashbyhq.com/company/job-id" (Ashby)
     * "https://jobs.lever.co/company/job-id" (Lever)
     * "https://boards.greenhouse.io/company/jobs/12345" (Greenhouse)
     * "https://wellfound.com/company/jobs/12345" (Wellfound)
     * Any URL with "/job/", "/jobs/", "/careers/" followed by an ID
   - If you find a specific job URL, use it for `apply_url` (NOT the listing page URL).
   - If you cannot find a specific job URL, mark `is_relevant: false` and `confidence: 0.0` - we don't want listing pages.
   - Also fill `listing_meta`.

3) If this is a **company careers page** but no single clear job is visible in the snippet:
   - "kind": "company_page"
   - `job_posting`: null
   - `listing_meta`: you can still include the company + careers URL.

4) If it is clearly irrelevant (credit cards, loans, generic AI blog, etc.):
   - "kind": "noise"
   - "is_relevant": false
   - Both `job_posting` and `listing_meta` should be null.

--------------------------------------------------

job_posting OBJECT

--------------------------------------------------

When you do have a specific job posting (either direct page OR best item from a list), use:

"job_posting": {{
  "title": string | null,
  "company_name": string | null,
  "location": string | null,
  "remote_type": "onsite" | "hybrid" | "remote" | "unspecified",
  "role_title_match": 0.0-1.0,
  "location_match": 0.0-1.0,
  "posted_date_text": string | null,
  "is_recent_enough": true | false | null,
  "seniority": "intern" | "junior" | "mid" | "senior" | "staff" | "lead" | "director" | "principal" | "unspecified",
  "years_experience_required": string | null,  // e.g., "2-3 years", "5+ years", "0-1 years"
  "employment_type": "full-time" | "part-time" | "contract" | "internship" | "unspecified",
  "apply_url": string | null,
  "source_url": "{url}",
  "source_site": string | null,
  "skills": [string],
  "tech_stack": [string],
  "highlights": [string]
}}

Rules:
- Do NOT invent fields that aren't obviously implied.
- If you don't know a field, use null or [].
- `role_title_match` and `location_match` should be rough numeric scores based on your understanding of the snippet/title.
- `is_recent_enough` is your best guess:
  - true if clearly "posted X days ago", "posted this month", etc.
  - false if clearly "posted 1+ year ago".
  - null if no time information.
- `source_site`: Extract domain from URL (e.g., "builtinsf.com", "wellfound.com")
- `seniority`: Extract from job description (e.g., "junior", "mid-level", "senior", "principal")
- `years_experience_required`: Extract explicit experience requirements (e.g., "2-3 years", "5+ years", "0-1 years")
- **CRITICAL - COMPANY NAME EXTRACTION**: 
  - ALWAYS try to extract `company_name` from the title, snippet, or URL.
  - Common patterns: "Role at Company", "Company - Role", "Company | Role", "Company is hiring"
  - For listing pages, extract the company name from the FIRST/BEST matching job in the snippet.
  - If the snippet shows multiple jobs, pick the one that best matches the target role and location.
  - NEVER use "Unknown Company" - if you truly cannot find a company name, use null.
- **CRITICAL - SPECIFIC JOB URL EXTRACTION**:
  - For listing pages, ALWAYS try to extract a SPECIFIC job URL from the snippet/title.
  - Look for URLs like "https://company.com/jobs/12345" or "https://jobs.lever.co/company/abc123"
  - If you find a specific job URL in the snippet, use it for `apply_url` instead of the listing page URL.
  - The `apply_url` should point to the ACTUAL job posting, not the search results page.
{f'''
- EXPERIENCE FILTERING: Target experience is {experience_range} years. 
  - Mark "is_relevant": false if the job clearly requires significantly more or less experience.
  - For {experience_range} years: Accept "junior", "entry level", "1-3 years", "2+ years", "mid-level" but reject "senior", "staff", "principal", "5+ years", "8+ years".
  - Set confidence lower if experience doesn't match well.
''' if experience_range else ''}

--------------------------------------------------

listing_meta OBJECT

--------------------------------------------------

Only used when "kind" = "job_list_page" or "company_page".

"listing_meta": {{
  "list_type": "job_list" | "category_page" | "company_careers" | "other",
  "estimated_job_count": integer | null,
  "primary_role_family": string | null,
  "notes": string | null
}}

--------------------------------------------------

RELEVANCE DECISION

--------------------------------------------------

You MUST set `is_relevant` based on:

1) Role alignment:
   - Strong match if the job is clearly for the target role or close variant.
   - Example: target "AI Engineer":
       - titles like "AI Engineer", "Applied AI Engineer", "LLM Engineer", "AI/ML Engineer" → strong match.
       - titles like "Data Analyst", "Marketing Manager" → weak match.

2) Location / remote alignment:
   - Strong match if:
       - location contains target city or metro (e.g., "San Francisco", "Bay Area", "SF Bay Area")
       - OR it is clearly Remote and open to US candidates (if target is in US).

3) Recency:
   - If clearly stale ("posted 2 years ago"), you can still normalize it but mark:
       - job_posting.is_recent_enough = false
       - is_relevant can still be true if everything else matches, but keep confidence lower.

Final guidance:
- If role + location are obviously off AND page is clearly not a job, set:
  - "is_relevant": false
  - "kind": "noise"

--------------------------------------------------

STYLE RULES

--------------------------------------------------

- Output MUST be valid JSON ONLY. No markdown, no backticks, no explanations outside the JSON.
- Be conservative. When in doubt, mark fields as null instead of guessing.
- Keep `reason` short (1–3 sentences).
- This JSON will be parsed by a program. If you break the schema, the whole pipeline fails.

--------------------------------------------------

PAGE TO NORMALIZE

--------------------------------------------------

{input_text}

Now normalize this page and return ONLY valid JSON (no markdown, no code blocks, no explanations)."""
    
    return prompt


def _extract_domain_from_url(url: str) -> Optional[str]:
    """Extract domain from URL (e.g., 'builtinsf.com' from 'https://www.builtinsf.com/job/...')"""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc
        # Remove 'www.' prefix if present
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return None


def _extract_company_from_url(url: str, title: str, snippet: str) -> Optional[str]:
    """
    Extract company name from URL, title, or snippet.
    Handles common patterns like Indeed URLs, title patterns, etc.
    """
    if not url:
        return None
    
    url_lower = url.lower()
    
    # Pattern 1: Indeed URLs often have company name in the path
    # e.g., https://www.indeed.com/viewjob?jk=abc123&cmp=CompanyName
    if "indeed.com" in url_lower:
        # Try to extract from "cmp=" parameter
        cmp_match = re.search(r'[?&]cmp=([^&]+)', url, re.IGNORECASE)
        if cmp_match:
            company = cmp_match.group(1)
            # URL decode and clean
            company = unquote(company).replace('+', ' ').strip()
            if company and len(company) > 1 and len(company) < 100:
                return company
    
    # Pattern 2: Extract from title patterns
    # "Role at Company", "Company - Role", "Company | Role"
    if title:
        patterns = [
            r" at ([A-Z][a-zA-Z0-9\s&\-]+)(?:\s*[\|\-]|$)",  # "Role at Company"
            r"^([A-Z][a-zA-Z0-9\s&\-]+)\s*[\|\-]\s*",        # "Company | Role" or "Company - Role"
            r"^([A-Z][a-zA-Z0-9\s&\-]+)\s+is\s+hiring",      # "Company is hiring"
            r"([A-Z][a-zA-Z0-9\s&\-]+)\s*-\s*" + re.escape(title.split('-')[0].strip()) if '-' in title else None
        ]
        
        for pattern in patterns:
            if pattern:
                match = re.search(pattern, title)
                if match:
                    company = match.group(1).strip()
                    # Clean up common suffixes
                    company = re.sub(r"\s*(Jobs?|Careers?|Hiring|Openings?)\s*$", "", company, flags=re.IGNORECASE)
                    if company and len(company) > 1 and len(company) < 100:
                        return company
    
    # Pattern 3: Extract from snippet if it mentions a company
    if snippet:
        # Look for patterns like "Company is hiring" or "at Company"
        snippet_patterns = [
            r"([A-Z][a-zA-Z0-9\s&\-]+)\s+is\s+hiring",
            r"at\s+([A-Z][a-zA-Z0-9\s&\-]+)",
            r"([A-Z][a-zA-Z0-9\s&\-]+)\s+-\s+" + re.escape(title.split()[0]) if title else None
        ]
        
        for pattern in snippet_patterns:
            if pattern:
                match = re.search(pattern, snippet[:500])  # Check first 500 chars
                if match:
                    company = match.group(1).strip()
                    # Filter out common false positives
                    false_positives = ["job", "position", "role", "opening", "career", "hiring", "apply"]
                    if company.lower() not in false_positives and len(company) > 1 and len(company) < 100:
                        return company
    
    return None


def _extract_role_description(snippet: str) -> Optional[str]:
    """
    Extract meaningful role description from snippet.
    Focuses on what the role is about, not aggregator noise.
    """
    if not snippet:
        return None
    
    # Look for role description patterns
    role_patterns = [
        # "We are seeking a [role] to..."
        r'(?:we\s+are\s+seeking|looking\s+for|hiring)\s+(?:an|a)?\s*([^.!?]{20,150}?)(?:\.|$|to\s+join|who)',
        # "Design and develop..." (action-oriented descriptions)
        r'(?:design|develop|build|create|implement|work\s+on)\s+([^.!?]{20,150}?)(?:\.|$)',
        # "As a [role], you will..."
        r'as\s+(?:an|a)\s+([^.!?]{15,120}?)(?:,\s*you|\.|$)',
        # "Join our team to..."
        r'join\s+our\s+team\s+to\s+([^.!?]{20,150}?)(?:\.|$)',
    ]
    
    for pattern in role_patterns:
        match = re.search(pattern, snippet, re.IGNORECASE)
        if match and match.group(1):
            desc = match.group(1).strip()
            # Clean up common prefixes/suffixes
            desc = re.sub(r'^(?:a|an|the)\b\s+', '', desc, flags=re.IGNORECASE)
            desc = re.sub(r'\s+to\s+(?:join|work|help).*$', '', desc, flags=re.IGNORECASE)
            if len(desc) >= 20 and len(desc) <= 200:
                return desc
    
    return None


def _clean_snippet_for_display(snippet: str) -> str:
    """
    Clean job snippet to remove noise, numbers, and aggregator boilerplate.
    CRITICAL: Extract meaningful role descriptions instead of showing gibberish.
    Returns a clean 2-line professional summary focused on role description.
    """
    if not snippet:
        return ""
    
    cleaned = snippet.strip()
    
    # ── Pre-clean: strip multi-department lists that leak from job board pages ──
    dept_names = r'(Engineering|Product|Design|Sales|Marketing|Finance|Operations|Business\s+Operations|HR|Human\s+Resources|Legal|Data|Support|Growth|Customer\s+Success|Business\s+Development|Research|Security|Software)'
    separator = r'(?:Â·|·|•|/)'
    dept_patterns = [
        fr'{dept_names}\s*·\s*{dept_names}',
        fr'{dept_names}\s*·\s*$',
        fr'·\s*{dept_names}\s*·',
        r'&\s*\d+\s*(more|other)\s*(departments?|teams?|roles?)',
        r'and\s+\d+\s+(more|other)\s+(departments?|teams?|roles?)',
    ]
    dept_patterns.extend([
        fr'{dept_names}\s*(?:\u00b7|\u2022|/)\s*{dept_names}',
        fr'{dept_names}\s*(?:\u00b7|\u2022|/)\s*$',
        fr'(?:\u00b7|\u2022|/)\s*{dept_names}\s*(?:\u00b7|\u2022|/)',
        r'Multiple\s+departments?\s*[:\-]\s*',
    ])
    for pat in dept_patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        fr'{dept_names}\s*(?:\u00b7|\u2022|Â·)\s*[^.#\n]{{0,80}}\s*(?:\u00b7|\u2022|Â·)\s*(Full\s+time|Part\s+time|Contract|Hybrid|On-site|Remote)[^.#\n]*',
        ' ',
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r'#+\s*[^.#\n]{0,80}(Human Resources|Finance|Product Manager|Director|VP / Director)[^.#\n]*', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(Director of Human Resources|VP / Director of Finance|Product Manager)\b[^.#\n]*', ' ', cleaned, flags=re.IGNORECASE)
    # Remove leftover stray · characters and orphan department names
    cleaned = re.sub(r'\s*·\s*', ' ', cleaned)
    cleaned = re.sub(r'\s*(?:\u00b7|\u2022|/)\s*', ' ', cleaned)
    cleaned = re.sub(fr'^\s*{dept_names}\s+', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # ── Pre-clean: strip incomplete/truncated data patterns ──
    incomplete_patterns = [
        r';\s*Employment\s+Type\b.*?(?=\.|\n|$)',
        r';\s*Salary\b.*?(?=\.|\n|$)',
        r';\s*Job\s+Type\b.*?(?=\.|\n|$)',
        r';\s*Industry\b.*?(?=\.|\n|$)',
        r';\s*Seniority\s+level\b.*?(?=\.|\n|$)',
        r'Multiple\s+departments?\s*[:\-]\s*',
    ]
    for pat in incomplete_patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE)
    if re.fullmatch(r'[A-Z][A-Za-z .,-]{1,80}', cleaned) and not re.search(r'\b(engineer|developer|scientist|architect|manager|analyst|designer|lead|specialist)\b', cleaned, re.IGNORECASE):
        return ""
    if len(cleaned.split()) <= 4 and re.search(dept_names, cleaned, re.IGNORECASE) and not re.search(r'\b(engineer|developer|scientist|architect|manager|analyst|designer|lead|specialist)\b', cleaned, re.IGNORECASE):
        return ""
    if re.search(r'\bEmployment\s+Type\b', snippet, re.IGNORECASE) and len(cleaned.split()) <= 5:
        return ""
    if cleaned.count("Full time") >= 2 or cleaned.count("###") >= 2:
        candidate = _extract_role_description(cleaned)
        if candidate:
            return candidate
        return ""
    
    # First, try to extract meaningful role description
    role_desc = _extract_role_description(cleaned)
    if role_desc:
        cleaned = role_desc
    else:
        # If no role description found, clean the original snippet
        
        # Remove job count patterns: #549, 1288 jobs, etc.
        cleaned = re.sub(r'#\d+\s*', '', cleaned)
        cleaned = re.sub(r'\d+\s+(jobs?|positions?|openings?)\s+(available|in)', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\d+\s+(Ai|AI|Machine Learning|Software|Generative)\s+engineer\s+jobs', '', cleaned, flags=re.IGNORECASE)
        
        # Remove location repetition patterns
        cleaned = re.sub(r'([A-Z][a-z]+,\s*[A-Z]{2})\s*\+\s*[^.]*jobs?\s+in\s+\1', r'\1', cleaned)
        
        # Remove aggregator noise (CRITICAL: Remove "also searched for" patterns)
        aggregator_noise = [
            r'Visit\s+Indeed\s+for\s+employers',
            r'Apply\s+to\s+[^.]*\s+and\s+more!',
            r'on\s+Indeed\.com',
            r'on\s+Glassdoor',
            r'jobs\s+available\s+in',
            r'jobs\s+in\s+[^.]*on\s+',
            r'Profile\s+insights',
            r'Find\s+out\s+how\s+your\s+skills',
            r'also\s+searched\s+for',  # CRITICAL: Remove "also searched for" gibberish
            r'in\s+[A-Z][a-z]+,\s*[A-Z]{2}\s+also\s+searched',  # "in Austin, TX also searched"
            r'Robotics\s+Technologies\s+jobs',
            r'Autonomize\s+Al\s+jobs',
        ]
        for pattern in aggregator_noise:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove redundant phrases
        cleaned = re.sub(r'\s+jobs?\s+(available|in|on)', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+on\s+(Indeed|Glassdoor|Dice)\.com', '', cleaned, flags=re.IGNORECASE)
        
        # Extract first 2 meaningful sentences (professional summary)
        sentences = re.split(r'[.!?]+', cleaned)
        meaningful_sentences = []
        for sent in sentences:
            sent = sent.strip()
            # Skip very short sentences, noise, or sentences starting with numbers or #
            if (len(sent) > 20 and 
                not re.match(r'^\d+', sent) and 
                not sent.startswith('#') and
                'also searched' not in sent.lower()):
                meaningful_sentences.append(sent)
                if len(meaningful_sentences) >= 2:
                    break
        
        if meaningful_sentences:
            cleaned = '. '.join(meaningful_sentences)
            if not cleaned.endswith('.'):
                cleaned += '.'
        else:
            # Fallback: take first 200 chars and clean
            cleaned = cleaned[:200].strip()
            # Remove trailing incomplete words
            last_space = cleaned.rfind(' ')
            if last_space > 150:
                cleaned = cleaned[:last_space]
    
    # Remove repeated text (simple heuristic: if first 50 chars appear again)
    if len(cleaned) > 100:
        first50 = cleaned[:50]
        next_occurrence = cleaned.find(first50, 50)
        if next_occurrence > 0 and next_occurrence < len(cleaned) * 0.7:
            cleaned = cleaned[:next_occurrence]
    
    # Final cleanup: remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Limit to ~200 chars for 2-line display
    if len(cleaned) > 200:
        cleaned = cleaned[:200].rstrip()
        last_space = cleaned.rfind(' ')
        if last_space > 150:
            cleaned = cleaned[:last_space]
        cleaned += '…'
    
    return cleaned


def _extract_specific_job_url_from_snippet(snippet: str, source_url: str) -> Optional[str]:
    """
    Extract a specific job URL from snippet text.
    Looks for URLs that point to actual job postings, not listing pages.
    """
    if not snippet:
        return None
    
    # Find all URLs in snippet
    url_pattern = r'https?://[^\s<>"\'\)]+'
    urls = re.findall(url_pattern, snippet)
    
    if not urls:
        return None
    
    # Filter URLs to find job posting URLs (not listing pages)
    for url in urls:
        url_lower = url.lower()
        
        # Skip if it's clearly a listing page
        listing_indicators = ["/jobs?", "/search?", "/job-search", "-jobs-", "/jobs/all"]
        if any(indicator in url_lower for indicator in listing_indicators):
            continue
        
        # Prefer URLs that look like job postings (ATS systems and job detail pages)
        job_indicators = [
            "/job/", "/jobs/", "/careers/", "/position/", "/positions/",
            "/openings/", "/opportunities/", "/o/", "/j/", "/apply",
            "lever.co", "greenhouse.io", "ashbyhq.com", "workable.com",
            "jobs.ashbyhq.com", "jobs.lever.co", "boards.greenhouse.io",
            "wellfound.com/jobs", "ycombinator.com/jobs"
        ]
        
        # Check if URL is from a preferred ATS/job site
        is_preferred_site = any(indicator in url_lower for indicator in job_indicators)
        
        # Also check for job ID patterns (common in ATS URLs)
        has_job_id = bool(re.search(r'/[a-z0-9]{8,}', url_lower))  # Long alphanumeric IDs
        
        if is_preferred_site or has_job_id:
            # Make sure it's not the same as source_url
            if url != source_url:
                return url
    
    # If no specific job URL found, return None (don't use listing page)
    return None


async def normalize_job_result(
    role_title: str,
    target_location: str,
    search_query: str,
    source: Dict[str, Any],
    experience_range: Optional[str] = None
) -> Dict[str, Any]:
    """
    Normalize a single job search result using LLM-based parsing.
    
    Args:
        role_title: Target role (e.g., "AI Engineer")
        target_location: Target location (e.g., "San Francisco, CA")
        search_query: Original search query
        source: Dictionary with keys: url, title, snippet, raw_html (optional)
        
    Returns:
        Normalized JSON object with kind, is_relevant, job_posting, listing_meta, etc.
    """
    
    url = source.get("url", "")
    title = source.get("title", "")
    snippet = source.get("snippet", "")
    raw_html = source.get("raw_html")
    
    if not url:
        # Return minimal noise response if no URL
        return {
            "kind": "noise",
            "is_relevant": False,
            "confidence": 0.0,
            "reason": "Missing URL in source data",
            "job_posting": None,
            "listing_meta": None
        }
    
    # Create prompt
    prompt = create_normalizer_prompt(
        role_title=role_title,
        target_location=target_location,
        search_query=search_query,
        url=url,
        title=title,
        snippet=snippet,
        raw_html=raw_html,
        experience_range=experience_range
    )
    
    # Default fallback response (noise)
    fallback_response = {
        "kind": "noise",
        "is_relevant": False,
        "confidence": 0.0,
        "reason": "Failed to parse - treating as noise",
        "job_posting": None,
        "listing_meta": None
    }
    
    try:
        if not DEEPSEEK_KEY:
            print("⚠️ DEEPSEEK_API_KEY not set, returning fallback")
            return fallback_response
        
        # Call DeepSeek API with low temperature for consistent JSON output
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a JSON-only output agent. You must return ONLY valid JSON, no markdown, no code blocks, no explanations."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.1,  # Low temperature for consistent, structured output
                    "max_tokens": 2000   # Enough for full JSON response
                }
            )
            response.raise_for_status()
            result = response.json()
            text = result["choices"][0]["message"]["content"].strip()
        
        # Parse JSON from response
        # First, try to extract JSON if wrapped in markdown code blocks (sometimes models do this)
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            # Try to find JSON object in the text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group(0)
        
        # Parse the JSON
        normalized = json.loads(text)
        
        # Validate and normalize the response
        # Ensure source_url is always set in job_posting if it exists
        if normalized.get("job_posting") and isinstance(normalized["job_posting"], dict):
            job_posting = normalized["job_posting"]
            job_posting["source_url"] = url
            
            # Ensure source_site is set
            if not job_posting.get("source_site"):
                domain = _extract_domain_from_url(url)
                if domain:
                    job_posting["source_site"] = domain
            
            # POST-PROCESSING: Improve company name extraction
            # If company_name is missing or "Unknown Company", try to extract from URL or title
            company_name = job_posting.get("company_name")
            if not company_name or company_name.lower() in ["unknown company", "unknown", "n/a", "null"]:
                # Try to extract from URL (especially for Indeed, Dice, etc.)
                extracted_company = _extract_company_from_url(url, title, snippet)
                if extracted_company:
                    job_posting["company_name"] = extracted_company
                    print(f"✅ Extracted company name from URL/title: {extracted_company}")
            
            # POST-PROCESSING: Ensure apply_url points to specific job, not listing page
            apply_url = job_posting.get("apply_url")
            source_url = job_posting.get("source_url", url)
            
            # CRITICAL FIX: Always check if apply_url is a listing page, even if LLM set it
            # The LLM might have set apply_url to the listing page URL by mistake
            is_listing = normalized.get("kind") == "job_list_page"
            is_apply_url_listing = False
            if apply_url:
                # Check if apply_url looks like a listing page
                apply_url_lower = apply_url.lower()
                listing_indicators = ["/jobs?", "/search?", "/job-search", "-jobs-", "/jobs/all", "/q-", "viewjob?jk="]
                is_apply_url_listing = any(indicator in apply_url_lower for indicator in listing_indicators)
            
            # If apply_url is missing, same as source_url, or is a listing page, try to extract from snippet
            if not apply_url or apply_url == source_url or (is_listing and is_apply_url_listing):
                # Try to find specific job URL in snippet
                specific_url = _extract_specific_job_url_from_snippet(snippet, url)
                if specific_url:
                    job_posting["apply_url"] = specific_url
                    print(f"✅ Extracted specific job URL from snippet: {specific_url[:80]}...")
                elif is_listing:
                    # If we couldn't extract from snippet and it's a listing page,
                    # mark apply_url as None so second-hop extraction will be triggered
                    job_posting["apply_url"] = None
                    print(f"⚠️ Listing page detected but no specific URL in snippet - will trigger second-hop")
            
            # POST-PROCESSING: Clean snippet for professional display
            if job_posting.get("highlights"):
                # Clean each highlight
                cleaned_highlights = []
                for highlight in job_posting["highlights"]:
                    if isinstance(highlight, str):
                        cleaned = _clean_snippet_for_display(highlight)
                        if cleaned:
                            cleaned_highlights.append(cleaned)
                if cleaned_highlights:
                    job_posting["highlights"] = cleaned_highlights[:2]  # Keep only first 2
        
        return normalized
        
    except json.JSONDecodeError:
        return fallback_response
        
    except httpx.HTTPStatusError:
        return fallback_response
        
    except Exception:
        return fallback_response

