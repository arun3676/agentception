from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
import re

class SearchQuery(BaseModel):
    q: str
    site: Optional[str] = None
    num: int = 10

class PlaceQuery(BaseModel):
    text: str
    location_bias: Optional[str] = "San Francisco, CA"
    max_results: int = 10

class HousingLead(BaseModel):
    title: str
    price: int
    url: str
    neighborhood: str
    distance_km: float
    notes: str = ""
    posted_at: Optional[str] = None   # e.g., '2025-09-01'

class EventItem(BaseModel):
    title: str
    date: str
    url: str
    area: str
    distance_km: float
    why_attend: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    duration_mins: Optional[int] = None

class OutreachEmail(BaseModel):
    company: str
    subject: str
    body_md: str
    contact_info: Optional[Dict[str, Any]] = None

class BudgetPlan(BaseModel):
    daily_budget_usd: int
    notes: str
    tips: List[str] = []

class MoveToSFParams(BaseModel):
    arrival_date: str = Field(default="2025-09-30")
    cash_usd: int = Field(default=3000)
    neighborhood_pref: str = Field(default="SoMa")
    max_rent_usd: int = Field(default=1400)
    min_rent_usd: int = Field(default=800)
    price_range: str = Field(default="1000-1500")  # Options: "800-1000", "1000-1500", "1500-2000", "2000-2500", "2500+"

class RunRequest(BaseModel):
    mode: Literal["wow", "real"]
    params: Optional[MoveToSFParams] = None

class TimelineEvent(BaseModel):
    run_id: str
    agent: str
    message: str
    payload: Optional[Dict[str, Any]] = None
    level: Literal["info", "warn", "error"] = "info"

from typing import Literal

class SubTaskParams(BaseModel):
    task: Literal["events_simple", "housing_simple"]
    city: str = "San Francisco"
    within_km: int = 8
    k: int = 5
    max_rent_usd: int = 1500

class SubRunRequest(BaseModel):
    params: SubTaskParams

class PlaceItem(BaseModel):
    name: str
    category: Optional[str] = None
    rating: Optional[float] = None
    address: Optional[str] = None
    lat: float
    lng: float
    url: Optional[str] = None
    distance_km: float = 0.0
    source: str = "fsq"
    duration_mins: Optional[int] = None

class ScoutSearchParams(BaseModel):
    location: str = "San Francisco, CA"
    types: List[Literal["events","housing"]] = ["events","housing"]
    radius_km: int = 8
    budget_usd: Optional[int] = 1500
    date_from: Optional[str] = None  # YYYY-MM-DD
    date_to: Optional[str] = None
    keywords: Optional[List[str]] = None

class ScoutExploreRequest(BaseModel):
    params: ScoutSearchParams

class JobPosting(BaseModel):
    """Represents a relevant job posting found on a company's career page."""
    url: str
    title: str
    snippet: Optional[str] = None
    
    # Location as an actual field (not computed property) - can be None
    location: Optional[str] = None
    
    # Additional fields for robust job tracking
    company: Optional[str] = None  # Company name if known
    source: Optional[str] = None   # e.g., "LinkedIn", "ZipRecruiter", "Indeed", "Lever"
    is_ats: bool = False           # True if from a known ATS system
    is_listing: bool = False       # True for "collection" pages (e.g., "AI Engineer jobs in SF")
    score: float = 0.0             # Ranking score from heuristics
    
    # === Trust scoring fields ===
    trust_score: int = Field(default=50, ge=0, le=100, description="0-100 trust score")
    trust_label: str = Field(default="uncertain", description="verified|uncertain|risky")
    trust_reasons: List[str] = Field(default_factory=list, description="Human-readable trust signals")
    posted_at: Optional[str] = Field(default=None, description="Posting date if extractable")
    is_expired: bool = Field(default=False, description="True if job appears stale/expired")
    days_old: Optional[int] = Field(default=None, description="Estimated age in days")
    
    # === Clean display fields ===
    clean_company: Optional[str] = Field(default=None, description="Verified company name (not ATS)")
    clean_title: Optional[str] = Field(default=None, description="Clean job title")
    clean_snippet: Optional[str] = Field(default=None, description="Snippet without garbage")

    # === Compensation ===
    salary: Optional[str] = Field(default=None, description="Posted pay range, e.g. '$150K – $250K'. Real values only.")
    
    def extract_location(self) -> Optional[str]:
        """
        Safely extracts a human-readable location string from the job posting.
        Searches title, snippet, and URL for location patterns.
        Returns the extracted location or self.location if already set.
        Never raises exceptions.
        
        NOTE: This is a helper method for enrichment. The `location` field
        itself should be used for storage.
        """
        # If location is already set, return it
        if self.location:
            return self.location
            
        try:
            # State abbreviation to full name mapping (for normalization)
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
            
            # Combine all text sources
            text_parts = []
            if self.title:
                text_parts.append(self.title)
            if self.snippet:
                text_parts.append(self.snippet)
            if self.url:
                text_parts.append(self.url)
            
            combined_text = " ".join(text_parts).lower()
            
            # Check for remote work indicators first
            remote_patterns = [
                r"\bremote\b", r"\bwork from home\b", r"\bwfh\b", 
                r"\bfully remote\b", r"\b100% remote\b", r"\bwork remotely\b",
                r"\bremote-friendly\b", r"\bremote first\b"
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
            
            # Pattern 2: "City State" (e.g., "San Francisco CA") - case insensitive
            city_state_no_comma = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+([A-Z]{2})\b'
            match = re.search(city_state_no_comma, " ".join(text_parts), re.IGNORECASE)
            if match:
                city = match.group(1)
                state = match.group(2).upper()
                location_str = f"{city}, {state}"
                if is_remote:
                    location_str += " (Remote)"
                return location_str
            
            # Pattern 3: Just city name (common cities)
            major_cities = [
                "san francisco", "new york", "los angeles", "chicago", "houston",
                "phoenix", "philadelphia", "san antonio", "san diego", "dallas",
                "austin", "seattle", "boston", "denver", "atlanta", "miami",
                "portland", "nashville", "detroit", "minneapolis"
            ]
            for city in major_cities:
                city_pattern = r'\b' + re.escape(city) + r'\b'
                if re.search(city_pattern, combined_text, re.IGNORECASE):
                    # Try to find state abbreviation nearby
                    state_abbrs = list(STATE_MAP.keys()) + [k.upper() for k in STATE_MAP.keys()]
                    # Look for state within 20 characters of city
                    city_match = re.search(city_pattern, " ".join(text_parts), re.IGNORECASE)
                    if city_match:
                        start_pos = max(0, city_match.start() - 20)
                        end_pos = min(len(" ".join(text_parts)), city_match.end() + 20)
                        nearby_text = " ".join(text_parts)[start_pos:end_pos]
                        for state_abbr in state_abbrs:
                            if re.search(r'\b' + re.escape(state_abbr) + r'\b', nearby_text, re.IGNORECASE):
                                location_str = f"{city.title()}, {state_abbr.upper()}"
                                if is_remote:
                                    location_str += " (Remote)"
                                return location_str
                    # Just city if no state found
                    location_str = city.title()
                    if is_remote:
                        location_str += " (Remote)"
                    return location_str
            
            # Pattern 4: Just state abbreviation
            state_abbrs = [k.upper() for k in STATE_MAP.keys()]
            for state_abbr in state_abbrs:
                state_pattern = r'\b' + re.escape(state_abbr) + r'\b'
                if re.search(state_pattern, " ".join(text_parts)):
                    location_str = state_abbr
                    if is_remote:
                        location_str += " (Remote)"
                    return location_str
            
            # If remote but no location found
            if is_remote:
                return "Remote"
            
            # No location found
            return None
            
        except Exception:
            # Never raise - return None on any error
            return None


class NormalizedJobPosting(BaseModel):
    """Structured job posting extracted by JOB_RESULT_NORMALIZER"""
    title: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    remote_type: Literal["onsite", "hybrid", "remote", "unspecified"] = "unspecified"
    role_title_match: float = 0.0  # 0.0-1.0
    location_match: float = 0.0    # 0.0-1.0
    posted_date_text: Optional[str] = None
    is_recent_enough: Optional[bool] = None
    seniority: Literal["intern", "junior", "mid", "senior", "staff", "lead", "director", "principal", "unspecified"] = "unspecified"
    employment_type: Literal["full-time", "part-time", "contract", "internship", "unspecified"] = "unspecified"
    apply_url: Optional[str] = None
    source_url: str
    source_site: Optional[str] = None
    skills: List[str] = []
    tech_stack: List[str] = []
    highlights: List[str] = []


class ListingMeta(BaseModel):
    """Metadata for job listing/aggregator pages"""
    list_type: Literal["job_list", "category_page", "company_careers", "other"] = "other"
    estimated_job_count: Optional[int] = None
    primary_role_family: Optional[str] = None
    notes: Optional[str] = None


class NormalizedJobResult(BaseModel):
    """Complete normalized result from JOB_RESULT_NORMALIZER"""
    kind: Literal["job_posting", "job_list_page", "company_page", "noise"]
    is_relevant: bool
    confidence: float = 0.0  # 0.0-1.0
    reason: str
    job_posting: Optional[NormalizedJobPosting] = None
    listing_meta: Optional[ListingMeta] = None


class JobNormalizerInput(BaseModel):
    """Input for job result normalizer"""
    role_title: str
    target_location: str
    search_query: str
    source: Dict[str, Any]  # Contains: url, title, snippet, raw_html (optional)


class CompanyIntel(BaseModel):
    name: str
    homepage: Optional[str] = None
    source_url: str
    blurb: Optional[str] = None
    city: Optional[str] = None
    tags: List[str] = []
    contact_hint: Optional[str] = None  # email or careers link if found
    recipient_email: Optional[str] = None  # Extracted career email address
    score: float = 0.0
    resume_match_score: float = 0.0  # Match score based on resume skills (0-100)
    job_posting: Optional[JobPosting] = None  # Relevant job posting if found
    intel: Optional[Dict[str, Any]] = None
    
    # Enhanced intelligence fields
    competitors: List[str] = []
    funding_stage: Optional[str] = None
    last_funding: Optional[str] = None
    key_people: List[Dict[str, str]] = []
    tech_stack: List[str] = []
    market_position: Optional[str] = None
    company_size: Optional[str] = None
    growth_indicator: Optional[str] = None
    confidence_score: float = 0.0
    data_sources: List[str] = []
    last_updated: Optional[str] = None


class AIResource(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    url: str
    category: Optional[str] = None
    tags: List[str] = []
    difficulty: Optional[str] = None
    cost: Optional[str] = None
    verified: bool = True
    upvotes: int = 0
    added_at: Optional[str] = None
    updated_at: Optional[str] = None
    featured: bool = False


class LearningPathRequest(BaseModel):
    # No user_id: ownership is derived from the verified JWT, never from the
    # request body. A client-supplied owner let anyone file a path under any id.
    topic: str
    expertise_level: str
    learning_style: str
    time_commitment: str
    goals: List[str] = []


class LearningResourceItem(BaseModel):
    id: Optional[str] = None
    title: str
    url: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []


class LearningMilestone(BaseModel):
    title: str
    description: str
    estimated_hours: int
    resources: List[LearningResourceItem]
    skills_gained: List[str]


class LearningPath(BaseModel):
    id: str
    title: str
    description: str
    topic: str
    expertise_level: str
    learning_style: str
    time_commitment: str
    goals: List[str]
    milestones: List[LearningMilestone]
    total_hours: int
    created_at: str
