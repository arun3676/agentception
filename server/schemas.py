from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any

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


class CompanyIntel(BaseModel):
    name: str
    homepage: Optional[str] = None
    source_url: str
    blurb: Optional[str] = None
    city: Optional[str] = None
    tags: List[str] = []
    contact_hint: Optional[str] = None  # email or careers link if found
    score: float = 0.0
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
