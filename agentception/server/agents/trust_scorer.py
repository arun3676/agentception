"""
Trust scoring for job postings.
Evaluates freshness, legitimacy, and data quality.
"""
import re
from typing import Tuple, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse

# ATS platforms (NOT companies)
ATS_PLATFORMS = {
    'ashbyhq', 'ashby', 'greenhouse', 'lever', 'workday', 'workable',
    'icims', 'jobvite', 'smartrecruiters', 'breezy', 'jazz', 'bamboohr',
    'recruitee', 'personio', 'teamtailor', 'fountain', 'jazzhr'
}

# Signals of stale/expired jobs
STALE_PATTERNS = [
    r'position\s+(?:has\s+been\s+)?filled',
    r'no\s+longer\s+(?:accepting|available)',
    r'this\s+job\s+(?:has\s+)?expired',
    r'application\s+closed',
    r'posting\s+(?:has\s+)?expired',
    r'role\s+(?:has\s+been\s+)?filled',
    r'we\'re\s+no\s+longer\s+hiring',
    r'this\s+position\s+is\s+closed',
]

# Garbage patterns in snippets
GARBAGE_PATTERNS = [
    r'\[Image\s*\d*:.*?\]',  # [Image 1: ...]
    r'\!\[.*?\]\(.*?\)',     # ![alt](url) markdown images
    r'https?://[^\s]+/api/images/[^\s]+',  # API image URLs
    r'data:image/[^;]+;base64,[^\s]+',     # Base64 images
    r'<img[^>]+>',           # HTML img tags
    r'\{[^}]+\}',            # JSON-like garbage
    r'org-theme-wordmark',   # Ashby image paths
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',  # UUIDs
]

# Date patterns to extract posting date
DATE_PATTERNS = [
    (r'posted\s+(\d+)\s+days?\s+ago', 'days'),
    (r'posted\s+(\d+)\s+hours?\s+ago', 'hours'),
    (r'posted\s+(\d+)\s+weeks?\s+ago', 'weeks'),
    (r'posted\s+(\d+)\s+months?\s+ago', 'months'),
    (r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', 'date'),  # MM/DD/YYYY
    (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})', 'month_date'),
]


def is_ats_platform(name: str) -> bool:
    """Check if name is an ATS platform, not a company."""
    if not name:
        return False
    name_lower = name.lower().strip()
    # Direct match
    if name_lower in ATS_PLATFORMS:
        return True
    # Partial match (e.g., "Ashbyhq" contains "ashby")
    for ats in ATS_PLATFORMS:
        if ats in name_lower or name_lower in ats:
            return True
    return False


def clean_snippet(text: str) -> str:
    """Remove garbage from snippet text."""
    if not text:
        return ""
    
    cleaned = text
    for pattern in GARBAGE_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.I)
    
    # Remove excessive whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Remove leading/trailing punctuation garbage
    cleaned = cleaned.strip('[](){}<>|•·-_=+')
    
    # If too short after cleaning, return empty
    if len(cleaned) < 20:
        return ""
    
    return cleaned


def extract_posting_age(text: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Extract posting age from text.
    Returns (days_old, posted_at_string)
    """
    if not text:
        return None, None
    
    text_lower = text.lower()
    
    for pattern, unit in DATE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            if unit == 'days':
                days = int(match.group(1))
                return days, f"{days} days ago"
            elif unit == 'hours':
                hours = int(match.group(1))
                return 0, f"{hours} hours ago"  # Same day
            elif unit == 'weeks':
                weeks = int(match.group(1))
                return weeks * 7, f"{weeks} weeks ago"
            elif unit == 'months':
                months = int(match.group(1))
                return months * 30, f"{months} months ago"
    
    return None, None


def is_job_expired(text: str, url: str = "") -> Tuple[bool, List[str]]:
    """
    Check if job appears to be expired/filled.
    Returns (is_expired, reasons)
    """
    if not text:
        return False, []
    
    text_lower = text.lower()
    reasons = []
    
    for pattern in STALE_PATTERNS:
        if re.search(pattern, text_lower):
            reasons.append("expired_language_detected")
            return True, reasons
    
    # Check for old posting dates
    days_old, _ = extract_posting_age(text)
    if days_old and days_old > 60:
        reasons.append(f"posted_{days_old}_days_ago")
        return True, reasons
    
    return False, reasons


def calculate_trust_score(
    company: str,
    title: str,
    snippet: str,
    url: str,
    source: str = ""
) -> Tuple[int, str, List[str]]:
    """
    Calculate trust score for a job posting.
    
    Returns: (score: 0-100, label: str, reasons: list)
    """
    score = 50  # Start neutral
    reasons = []
    
    # === POSITIVE SIGNALS ===
    
    # From known ATS domain (legitimate job board)
    parsed = urlparse(url) if url else None
    domain = parsed.netloc.lower() if parsed else ""
    
    ats_domains = ['lever.co', 'greenhouse.io', 'ashbyhq.com', 'workday.com', 'workable.com']
    if any(ats in domain for ats in ats_domains):
        score += 20
        reasons.append("ats_domain")
    
    # Has salary information
    if snippet and re.search(r'\$\d{2,3}[kK]|\$\d{3},\d{3}|\d{2,3}k\s*[-–]\s*\d{2,3}k', snippet):
        score += 10
        reasons.append("salary_listed")
    
    # Has location
    if snippet and re.search(r'(remote|hybrid|on-?site|[A-Z][a-z]+,\s*[A-Z]{2})', snippet):
        score += 5
        reasons.append("location_specified")
    
    # Recently posted
    days_old, posted_at = extract_posting_age(snippet)
    if days_old is not None:
        if days_old <= 7:
            score += 15
            reasons.append("posted_recently")
        elif days_old <= 30:
            score += 5
            reasons.append("posted_this_month")
        elif days_old > 60:
            score -= 20
            reasons.append("possibly_stale")
    
    # === NEGATIVE SIGNALS ===
    
    # Company name is ATS platform
    if is_ats_platform(company):
        score -= 30
        reasons.append("company_is_ats_platform")
    
    # Title contains ATS platform
    if title and is_ats_platform(title.split(' at ')[-1] if ' at ' in title else ''):
        score -= 20
        reasons.append("title_contains_ats")
    
    # Expired job signals
    is_expired, expired_reasons = is_job_expired(snippet, url)
    if is_expired:
        score -= 40
        reasons.extend(expired_reasons)
    
    # Garbage in snippet
    if snippet:
        original_len = len(snippet)
        cleaned = clean_snippet(snippet)
        if len(cleaned) < original_len * 0.5:
            score -= 15
            reasons.append("snippet_has_garbage")
    
    # Very short or missing snippet
    if not snippet or len(snippet) < 50:
        score -= 10
        reasons.append("minimal_description")
    
    # === DETERMINE LABEL ===
    score = max(0, min(100, score))  # Clamp to 0-100
    
    if score >= 70:
        label = "verified"
    elif score >= 40:
        label = "uncertain"
    else:
        label = "risky"
    
    return score, label, reasons


def enhance_job_data(job_data: dict) -> dict:
    """
    Enhance a job data dict with trust scoring and cleaned fields.
    Modifies and returns the dict.
    """
    company = job_data.get('company_name') or job_data.get('company') or ''
    title = job_data.get('job_title') or job_data.get('title') or ''
    snippet = job_data.get('blurb') or job_data.get('snippet') or ''
    url = job_data.get('job_url') or job_data.get('url') or ''
    source = job_data.get('job_source') or job_data.get('source') or ''
    
    # Calculate trust score
    trust_score, trust_label, trust_reasons = calculate_trust_score(
        company, title, snippet, url, source
    )
    
    # Check expiration
    is_expired, _ = is_job_expired(snippet, url)
    days_old, posted_at = extract_posting_age(snippet)
    
    # Clean the company name if it's an ATS platform
    clean_company = company
    if is_ats_platform(company):
        # Try to extract real company from title
        if ' at ' in title:
            potential_company = title.split(' at ')[-1].strip()
            if not is_ats_platform(potential_company):
                clean_company = potential_company
        elif ' @ ' in title:
            potential_company = title.split(' @ ')[-1].strip()
            if not is_ats_platform(potential_company):
                clean_company = potential_company
        else:
            clean_company = "Unknown Company"
    
    # Clean the title if it contains ATS platform
    clean_title = title
    for ats in ATS_PLATFORMS:
        clean_title = re.sub(rf'\s+at\s+{ats}\b', '', clean_title, flags=re.I)
        clean_title = re.sub(rf'\s+@\s+{ats}\b', '', clean_title, flags=re.I)
        clean_title = re.sub(rf'\b{ats}\s+[-–]\s+', '', clean_title, flags=re.I)
    clean_title = clean_title.strip(' -–|')
    
    # Clean snippet
    clean_snip = clean_snippet(snippet)
    
    # Update the dict
    job_data.update({
        'trust_score': trust_score,
        'trust_label': trust_label,
        'trust_reasons': trust_reasons,
        'is_expired': is_expired,
        'days_old': days_old,
        'posted_at': posted_at,
        'clean_company': clean_company,
        'clean_title': clean_title if clean_title else title,
        'clean_snippet': clean_snip if clean_snip else snippet[:200] if snippet else '',
    })
    
    # Also update primary fields if they were ATS platforms
    if is_ats_platform(company):
        job_data['company_name'] = clean_company
    
    return job_data
