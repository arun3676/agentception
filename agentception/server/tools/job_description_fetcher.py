from __future__ import annotations
import re, os, json
import httpx
from typing import Optional
from bs4 import BeautifulSoup

from .exa_search import exa_contents
from .tavily_search import tavily_extract
from .text_clean import strip_markdown


# ─── Tier 0: Snippet threshold ───
SNIPPET_MIN_CHARS = 300
RESULT_MIN_CHARS = 200
MAX_RESULT_CHARS = 5000
LLM_INPUT_MAX_CHARS = 2500


# ─── Utility ───

def _html_to_text(element) -> str:
    """Convert BeautifulSoup element to clean, readable text."""
    # Handle specific tags
    for tag in element.find_all(["p", "br", "li"]):
        tag.insert_after("\n")
    for tag in element.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.insert_after("\n\n")
    
    text = element.get_text(separator=" ")
    
    # Clean up
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&#x2F;", "/", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&apos;", "'", text)
    text = re.sub(r"&[a-z]+;", " ", text)  # any remaining entities → space
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    lines = [l.strip() for l in text.split("\n")]
    lines = [l for l in lines if l]
    
    return "\n".join(lines)[:MAX_RESULT_CHARS].strip()


def _markdown_to_text(markdown: str) -> str:
    """Strip markdown chrome from Tavily Extract output (images, links, headings)."""
    return strip_markdown(markdown, drop_blank_lines=True, max_chars=MAX_RESULT_CHARS)


def _extract_json_ld(soup) -> Optional[str]:
    """
    Extract job description from Schema.org JobPosting JSON-LD.
    This is the industry standard used by Google Jobs, LinkedIn, Indeed, etc.
    Most modern career sites embed JobPosting schema for SEO.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                # Find the JobPosting object in a list
                for item in data:
                    if isinstance(item, dict) and _is_job_posting(item):
                        result = _build_jd_from_schema(item)
                        if result:
                            return result
            elif isinstance(data, dict):
                if _is_job_posting(data):
                    result = _build_jd_from_schema(data)
                    if result:
                        return result
                # Some sites wrap JobPosting in a parent (e.g., WebPage with mainEntity)
                main = data.get("mainEntity") or data.get("about")
                if isinstance(main, dict) and _is_job_posting(main):
                    result = _build_jd_from_schema(main)
                    if result:
                        return result
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _is_job_posting(data: dict) -> bool:
    """Check if a JSON-LD object is a Schema.org JobPosting."""
    types = data.get("@type") or data.get("type") or ""
    if isinstance(types, str):
        return "jobposting" in types.lower()
    if isinstance(types, list):
        return any("jobposting" in str(t).lower() for t in types)
    return False


def _strip_html(value: str) -> str:
    """JobPosting.description is HTML-encoded markup in most ATS feeds."""
    if not value or "<" not in value:
        return value
    return _html_to_text(BeautifulSoup(value, "html.parser"))


def _build_jd_from_schema(item: dict) -> Optional[str]:
    """
    Build a clean job description from Schema.org JobPosting fields.
    Combines description, responsibilities, qualifications, skills, etc.
    """
    parts = []

    title = item.get("title") or item.get("name") or ""
    if title:
        parts.append(f"Title: {title}")

    # Core description
    desc = _strip_html(item.get("description") or item.get("employerOverview") or "")
    if desc and len(desc) > 50:
        parts.append(desc.strip())

    # Responsibilities
    resp = item.get("responsibilities") or ""
    if isinstance(resp, list):
        resp = "\n".join(f"- {r}" for r in resp)
    if resp and len(resp) > 30:
        parts.append(f"Responsibilities:\n{resp.strip()}")

    # Qualifications / Requirements
    qual = item.get("qualifications") or item.get("experienceRequirements") or ""
    if isinstance(qual, dict):
        # EducationalOccupationalCredential or OccupationalExperienceRequirements
        qual = qual.get("credentialCategory") or qual.get("monthsOfExperience") or ""
    if isinstance(qual, list):
        qual = "\n".join(f"- {q}" for q in qual)
    if qual and len(str(qual)) > 30:
        parts.append(f"Qualifications:\n{str(qual).strip()}")

    # Skills
    skills = item.get("skills") or ""
    if isinstance(skills, list):
        skills = "\n".join(f"- {s}" for s in skills)
    if skills and len(str(skills)) > 20:
        parts.append(f"Skills:\n{str(skills).strip()}")

    # Education requirements
    edu = item.get("educationRequirements") or ""
    if isinstance(edu, dict):
        edu = edu.get("credentialCategory") or ""
    if isinstance(edu, list):
        edu = "\n".join(f"- {e}" for e in edu)
    if edu and len(str(edu)) > 20:
        parts.append(f"Education:\n{str(edu).strip()}")

    if not parts:
        return None

    combined = "\n\n".join(parts)
    return combined[:MAX_RESULT_CHARS].strip()


def _extract_meta_tags(soup) -> Optional[str]:
    """
    Extract job description from meta tags.
    LinkedIn, Indeed, and many ATS systems populate og:description
    with a clean job summary.
    """
    # Priority order: og:description > twitter:description > meta description
    selectors = [
        ("meta", {"property": "og:description"}),
        ("meta", {"name": "twitter:description"}),
        ("meta", {"name": "description"}),
    ]

    for tag, attrs in selectors:
        elem = soup.find(tag, attrs=attrs)
        if elem:
            content = elem.get("content", "").strip()
            if content and len(content) > RESULT_MIN_CHARS:
                return content[:MAX_RESULT_CHARS]

    return None


def _is_multi_listing_page(text: str, soup=None) -> bool:
    """
    Detect if a page is an aggregate/multi-job listing page rather than
    a single job description. Returns True if the page looks like a careers
    index or job board listing page.
    """
    if not text:
        return False

    lowered = text.lower()

    # Phrases that strongly indicate a multi-listing index page
    aggregate_signals = [
        "view all jobs", "view all openings", "current openings",
        "open positions", "job openings", "careers at",
        "join our team", "we're hiring", "we are hiring",
        "browse jobs", "search jobs", "all departments",
        "available positions", "job listings", "career opportunities",
    ]
    aggregate_count = sum(1 for s in aggregate_signals if s in lowered)
    if aggregate_count >= 2:
        return True

    # Count how many distinct job title patterns appear
    # If many short job-like lines appear, it's probably an index
    common_title_patterns = [
        r"\bsoftware engineer\b", r"\bproduct manager\b", r"\bdesigner\b",
        r"\bdata scientist\b", r"\bdata engineer\b", r"\bml engineer\b",
        r"\bfrontend\b", r"\bbackend\b", r"\bfull[-\s]?stack\b",
        r"\bdevops\b", r"\bsre\b", r"\btech lead\b", r"\bstaff engineer\b",
        r"\bsenior\b.*\bengineer\b", r"\bjunior\b.*\bengineer\b",
        r"\bapply now\b", r"\blearn more\b",
    ]
    title_matches = sum(1 for pat in common_title_patterns if re.search(pat, lowered))
    if title_matches >= 4:
        return True

    # If the page has many short lines with "apply" links, it's an index
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    short_job_lines = [l for l in lines if 20 < len(l) < 100 and "apply" in l.lower()]
    if len(short_job_lines) >= 5:
        return True

    return False


def _quality_check(text: str) -> bool:
    """Check if extracted text looks like a real job description."""
    if not text or len(text) < RESULT_MIN_CHARS:
        return False
    # Must have some job-related keywords
    lowered = text.lower()
    indicators = ["experience", "skills", "work", "team", " engineer", "develop", "build", "design"]
    matches = sum(1 for i in indicators if i in lowered)
    return matches >= 1


# ─── Site-Specific Parsers ───

def _detect_site(url: str) -> str:
    """Detect job board from URL."""
    url_low = url.lower()
    if "greenhouse" in url_low or "boards.greenhouse" in url_low:
        return "greenhouse"
    if "lever.co" in url_low or "jobs.lever" in url_low:
        return "lever"
    if "ashbyhq.com" in url_low or "jobs.ashby" in url_low:
        return "ashby"
    if "myworkdayjobs.com" in url_low or "workday.com" in url_low:
        return "workday"
    return "generic"


def _extract_greenhouse(soup) -> str:
    """Extract from Greenhouse job pages."""
    # Try JSON-LD first (most reliable)
    result = _extract_json_ld(soup)
    if result and _quality_check(result):
        return result
    
    # Try the content div
    content = soup.find("div", id="content")
    if content:
        text = _html_to_text(content)
        if _quality_check(text):
            return text
    
    # Fallback to main content area
    main = soup.find("main") or soup.find("div", class_="body")
    if main:
        text = _html_to_text(main)
        if _quality_check(text):
            return text
    
    return ""


def _extract_lever(soup) -> str:
    """Extract from Lever job pages."""
    # Try posting page wrapper
    for cls in ["posting-page", "posting", "section-wrapper", "job-description"]:
        section = soup.find("div", class_=re.compile(cls, re.I))
        if section:
            text = _html_to_text(section)
            if _quality_check(text):
                return text
    
    # Try JSON-LD
    result = _extract_json_ld(soup)
    if result and _quality_check(result):
        return result
    
    return ""


def _extract_ashby(soup) -> str:
    """Extract from Ashby job pages."""
    # Ashby uses various container divs
    for selector in [
        soup.find("div", class_=re.compile(r"job-description|jobDescription|job-info", re.I)),
        soup.find("div", class_=re.compile(r"description|details-body", re.I)),
        soup.find("main"),
    ]:
        if selector:
            text = _html_to_text(selector)
            if _quality_check(text):
                return text
    
    # Try JSON-LD
    result = _extract_json_ld(soup)
    if result and _quality_check(result):
        return result
    
    return ""


def _extract_workday(soup) -> str:
    """Extract from Workday/MyWorkdayJobs."""
    for cls in ["job-description", "jobDescription", "description", "job-details"]:
        section = soup.find("div", class_=re.compile(cls, re.I))
        if section:
            text = _html_to_text(section)
            if _quality_check(text):
                return text
    return ""


def _extract_generic(soup) -> str:
    """Smart generic extraction for unknown job boards."""
    # Remove noise elements
    for tag_name in ["nav", "footer", "header", "aside", "script", "style", "form"]:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    
    # Remove elements with noise class/ID patterns
    noise_patterns = [
        re.compile(r"sidebar|related|similar|share|social|comment|nav|menu|footer|header|banner|cookie|tracking|advertisement|popup|modal", re.I),
    ]
    for element in soup.find_all(attrs={"class": True}):
        classes = " ".join(element.get("class", []))
        ids = element.get("id", "")
        if any(p.search(classes) or p.search(ids) for p in noise_patterns):
            element.decompose()
    
    # Find the largest text block (job descriptions are usually the longest content)
    body = soup.find("body") or soup
    candidates = []
    
    for tag in body.find_all(["div", "section", "article", "main"]):
        text = tag.get_text(separator=" ", strip=True)
        if len(text) > 150:
            # Score: prefer blocks with job-related terms and high text density
            lowered = text.lower()
            score = len(text)
            score += sum(20 for kw in [
                "experience", "requirements", "qualifications", "responsibilities",
                "about the role", "what you", "we are looking", "nice to have",
                "benefits", "skills", "years of",
            ] if kw in lowered)
            # Penalize short lines (likely nav/menu)
            lines = [l for l in text.split("\n") if l.strip()]
            if lines:
                avg_line = sum(len(l) for l in lines) / len(lines)
                if avg_line < 40:
                    score *= 0.3
            candidates.append((score, tag))
    
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_tag = candidates[0][1]
        text = _html_to_text(best_tag)
        if _quality_check(text):
            return text
    
    # Last resort: extract from body, stripping known noise
    full_text = _html_to_text(body)
    if _quality_check(full_text):
        return full_text
    
    return ""


# ─── LLM Extraction ───

async def _extract_with_llm(text: str) -> str:
    """Last-resort extraction of a job description from raw page text.

    Routed through llm_router, so the provider choice, the fallback and the cost are
    all recorded rather than being two hand-rolled try/excepts that swallowed a quota
    error and returned "" as if the page had simply been empty.
    """
    if not text or len(text) < 50:
        return ""

    from .llm_router import AllProvidersFailed, complete

    prompt = (
        "Extract only the job description from the following text. Include:\n"
        "- Role overview / About the role\n"
        "- Responsibilities\n"
        "- Requirements / Qualifications\n"
        "- Nice-to-haves (if present)\n\n"
        "Ignore navigation menus, footers, company descriptions, apply instructions, "
        "salary ranges, and boilerplate. Return only the job description, "
        "formatted cleanly with section breaks.\n\n"
        "Text:\n" + text[:LLM_INPUT_MAX_CHARS]
    )

    try:
        result = await complete(
            prompt,
            purpose="jd_extraction",
            system=(
                "You extract job descriptions from raw web page text. "
                "Return only the job description, formatted cleanly."
            ),
            max_tokens=800,
        )
    except AllProvidersFailed as e:
        print(f"[JD Fetcher] LLM extraction unavailable: {e}")
        return ""

    return result.text if len(result.text) > 100 else ""


# ─── Main Fetcher ───

async def fetch_job_description(job_url: str, snippet: Optional[str] = None) -> str:
    """
    Intelligent 8-tier job description extraction (cheapest first):
    Tier 0: Snippet sufficient (>300 chars) — free
    Tier 1: Schema.org JobPosting JSON-LD — free, most reliable (70%+ coverage)
    Tier 2: Meta tags (og:description, twitter:description) — free, clean
    Tier 3: Site-specific parsers (Greenhouse, Lever, Ashby, etc.) — free
    Tier 4: Smart generic extraction (BeautifulSoup + heuristics) — free
    Tier 5: Tavily Extract — paid, renders JS-heavy ATS pages
    Tier 6: Exa content extraction — paid (~$0.01/1k docs)
    Tier 7: LLM extraction (GPT-4o-mini) — paid (~$0.001/call)
    Tier 8: Return snippet or empty string — free
    """

    # ─── Tier 0: Snippet check ───
    if snippet and len(snippet) > SNIPPET_MIN_CHARS:
        text = snippet.strip()
        if _quality_check(text):
            return text[:MAX_RESULT_CHARS]

    if not job_url:
        return (snippet or "")[:MAX_RESULT_CHARS]

    site = _detect_site(job_url)
    html = ""
    text_for_llm = ""

    # ─── Fetch HTML once ───
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(job_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })
            if resp.status_code < 400 and resp.text:
                html = resp.text
    except Exception as e:
        print(f"[JD Fetcher] HTTP fetch failed for {job_url[:80]}: {e}")

    if not html:
        return (snippet or "")[:MAX_RESULT_CHARS]

    soup = BeautifulSoup(html, "html.parser")

    # ─── Multi-listing page detection ───
    # Reject aggregate pages (careers index, job boards) early
    body_text_preview = ""
    body = soup.find("body")
    if body:
        body_text_preview = body.get_text(separator=" ", strip=True)[:3000]
    if _is_multi_listing_page(body_text_preview, soup):
        print(f"[JD Fetcher] Detected multi-listing page, skipping extraction")
        return (snippet or "")[:MAX_RESULT_CHARS]

    result = ""

    # ─── Tier 1: Schema.org JobPosting JSON-LD ───
    # Industry standard. Most companies embed this for Google Jobs SEO.
    try:
        result = _extract_json_ld(soup)
        if result and _quality_check(result):
            print(f"[JD Fetcher] Extracted via Schema.org JobPosting JSON-LD ({len(result)} chars)")
            return result[:MAX_RESULT_CHARS]
    except Exception as e:
        print(f"[JD Fetcher] JSON-LD extraction failed: {e}")

    # ─── Tier 2: Meta tags ───
    # LinkedIn, Indeed, and many ATS systems populate og:description cleanly.
    try:
        result = _extract_meta_tags(soup)
        if result and _quality_check(result):
            print(f"[JD Fetcher] Extracted via meta tags ({len(result)} chars)")
            return result[:MAX_RESULT_CHARS]
    except Exception as e:
        print(f"[JD Fetcher] Meta tag extraction failed: {e}")

    # ─── Tier 3: Site-specific parsers ───
    parsers = {"greenhouse": _extract_greenhouse, "lever": _extract_lever, "ashby": _extract_ashby, "workday": _extract_workday}
    if site in parsers:
        try:
            result = parsers[site](soup)
            if _quality_check(result):
                print(f"[JD Fetcher] Extracted via {site} parser ({len(result)} chars)")
                return result[:MAX_RESULT_CHARS]
        except Exception as e:
            print(f"[JD Fetcher] {site} parser failed: {e}")

    # ─── Tier 4: Generic extraction ───
    try:
        result = _extract_generic(soup)
        if _quality_check(result):
            print(f"[JD Fetcher] Extracted via generic parser ({len(result)} chars)")
            return result[:MAX_RESULT_CHARS]
    except Exception as e:
        print(f"[JD Fetcher] Generic parser failed: {e}")

    # ─── Tier 5: Tavily Extract ───
    # Tavily renders the page server-side, so it succeeds on JS-heavy ATS pages
    # (Ashby, Workday) where the free HTML tiers above return nothing.
    try:
        print(f"[JD Fetcher] Trying Tavily Extract for {job_url[:80]}...")
        extracted = await tavily_extract([job_url])
        raw = extracted.get(job_url) or (next(iter(extracted.values())) if extracted else "")
        if raw:
            result = _markdown_to_text(raw)
            if _quality_check(result) and not _is_multi_listing_page(result):
                print(f"[JD Fetcher] Extracted via Tavily ({len(result)} chars)")
                return result[:MAX_RESULT_CHARS]
            text_for_llm = result
    except Exception as e:
        print(f"[JD Fetcher] Tavily Extract failed: {e}")

    # ─── Tier 6: Exa Content ───
    try:
        print(f"[JD Fetcher] Trying Exa for {job_url[:80]}...")
        exa_res = await exa_contents([job_url], max_chars=MAX_RESULT_CHARS)
        if exa_res and exa_res[0].get("text"):
            result = exa_res[0]["text"].strip()
            if _quality_check(result):
                print(f"[JD Fetcher] Extracted via Exa ({len(result)} chars)")
                return result[:MAX_RESULT_CHARS]
            # Even if quality check fails on raw Exa text, keep it for LLM
            text_for_llm = result
    except Exception as e:
        print(f"[JD Fetcher] Exa failed: {e}")

    # ─── Tier 7: LLM Extraction ───
    combined = text_for_llm if text_for_llm else (snippet or "")
    if not combined and html:
        combined = _html_to_text(soup)

    if len(combined) > 100:
        try:
            print(f"[JD Fetcher] Trying LLM extraction...")
            result = await _extract_with_llm(combined)
            if _quality_check(result):
                print(f"[JD Fetcher] Extracted via LLM ({len(result)} chars)")
                return result[:MAX_RESULT_CHARS]
        except Exception as e:
            print(f"[JD Fetcher] LLM extraction failed: {e}")

    # ─── Tier 8: Fallback ───
    if body:
        raw_text = _html_to_text(body)
        if len(raw_text) > RESULT_MIN_CHARS:
            print(f"[JD Fetcher] Falling back to raw body text ({len(raw_text)} chars)")
            return raw_text[:MAX_RESULT_CHARS]

    print("[JD Fetcher] All tiers exhausted, returning snippet/empty")
    return (snippet or "")[:MAX_RESULT_CHARS]
