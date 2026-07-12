from __future__ import annotations
import os
import enum
import asyncio
import logging
import random
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

# Removed: from ..tools.exa_search import exa_search
from ..tools.tavily_search import tavily_search

# Configure logging
logger = logging.getLogger(__name__)

# Mock mode for testing without API calls
MOCK_SEARCH_MODE = os.getenv("MOCK_SEARCH", "false").lower() == "true"

class SearchProvider(enum.Enum):
    EXA = "exa"
    TAVILY = "tavily"

@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str
    score: float = 0.0


# Sample mock company data for realistic testing
MOCK_COMPANIES = [
    {"name": "Anthropic", "domain": "anthropic.com", "ats": "lever.co"},
    {"name": "OpenAI", "domain": "openai.com", "ats": "greenhouse.io"},
    {"name": "Scale AI", "domain": "scale.com", "ats": "lever.co"},
    {"name": "Cohere", "domain": "cohere.com", "ats": "ashbyhq.com"},
    {"name": "Hugging Face", "domain": "huggingface.co", "ats": "lever.co"},
    {"name": "Databricks", "domain": "databricks.com", "ats": "greenhouse.io"},
    {"name": "Stripe", "domain": "stripe.com", "ats": "greenhouse.io"},
    {"name": "Figma", "domain": "figma.com", "ats": "lever.co"},
    {"name": "Notion", "domain": "notion.so", "ats": "lever.co"},
    {"name": "Linear", "domain": "linear.app", "ats": "ashbyhq.com"},
    {"name": "Vercel", "domain": "vercel.com", "ats": "lever.co"},
    {"name": "Supabase", "domain": "supabase.com", "ats": "ashbyhq.com"},
    {"name": "Replit", "domain": "replit.com", "ats": "lever.co"},
    {"name": "Weights & Biases", "domain": "wandb.ai", "ats": "lever.co"},
    {"name": "Anyscale", "domain": "anyscale.com", "ats": "greenhouse.io"},
]


def _generate_mock_results(query: str, max_results: int) -> List[SearchHit]:
    """Generate realistic mock search results for testing."""
    # Extract role from query for realistic titles - comprehensive role detection
    role = "Software Engineer"
    query_lower = query.lower()
    
    # AI/ML roles (check specific first)
    if "llm engineer" in query_lower:
        role = "LLM Engineer"
    elif "applied scientist" in query_lower:
        role = "Applied Scientist"
    elif "research engineer" in query_lower:
        role = "Research Engineer"
    elif "ai engineer" in query_lower or "ml engineer" in query_lower:
        role = "AI Engineer"
    elif "machine learning" in query_lower:
        role = "Machine Learning Engineer"
    # Data roles (check specific first before generic "data engineer")
    elif "analytics engineer" in query_lower:
        role = "Analytics Engineer"
    elif "etl engineer" in query_lower:
        role = "ETL Engineer"
    elif "data platform engineer" in query_lower:
        role = "Data Platform Engineer"
    elif "data pipeline engineer" in query_lower:
        role = "Data Pipeline Engineer"
    elif "big data engineer" in query_lower:
        role = "Big Data Engineer"
    elif "data architect" in query_lower:
        role = "Data Architect"
    elif "data warehouse engineer" in query_lower:
        role = "Data Warehouse Engineer"
    elif "spark developer" in query_lower:
        role = "Spark Developer"
    elif "airflow engineer" in query_lower:
        role = "Airflow Engineer"
    elif "data infrastructure" in query_lower:
        role = "Data Infrastructure Engineer"
    elif "data engineer" in query_lower:
        role = "Data Engineer"
    # Full-stack and web roles
    elif "full stack" in query_lower or "fullstack" in query_lower:
        role = "Full Stack Engineer"
    elif "backend" in query_lower:
        role = "Backend Engineer"
    elif "frontend" in query_lower:
        role = "Frontend Engineer"
    elif "web developer" in query_lower:
        role = "Web Developer"
    # DevOps and Cloud roles
    elif "devops" in query_lower:
        role = "DevOps Engineer"
    elif "cloud engineer" in query_lower:
        role = "Cloud Engineer"
    elif "sre" in query_lower or "site reliability" in query_lower:
        role = "Site Reliability Engineer"
    elif "platform engineer" in query_lower:
        role = "Platform Engineer"
    # Security and enterprise roles
    elif "security engineer" in query_lower:
        role = "Security Engineer"
    elif "java developer" in query_lower or "java engineer" in query_lower:
        role = "Java Developer"
    
    # Shuffle companies to get variety
    companies = MOCK_COMPANIES.copy()
    random.shuffle(companies)
    
    hits = []
    for i, company in enumerate(companies[:max_results]):
        # Mix of ATS and direct URLs
        if i % 3 == 0:
            url = f"https://{company['name'].lower().replace(' ', '-').replace('&', '')}.{company['ats']}/{role.lower().replace(' ', '-')}"
        else:
            url = f"https://jobs.{company['ats']}/{company['name'].lower().replace(' ', '-')}/{role.lower().replace(' ', '-')}"
        
        hits.append(SearchHit(
            url=url,
            title=f"{role} at {company['name']}",
            snippet=f"{company['name']} is hiring a {role}. Join our team and work on cutting-edge technology. We offer competitive salary, equity, and great benefits.",
            score=85.0 - (i * 3) + random.uniform(-5, 5)
        ))
    
    print(f"🎭 MOCK_SEARCH: Generated {len(hits)} mock results for: {query[:50]}...")
    return hits


async def smart_search(
    query: str, 
    *, 
    max_results: int = 15, 
    provider_hint: Optional[SearchProvider] = None
) -> List[SearchHit]:
    """
    Unified search layer that uses Tavily (or mock data if MOCK_SEARCH=true).
    
    Note: Set MOCK_SEARCH=true in .env to test without API calls.
    """
    if MOCK_SEARCH_MODE:
        print(f"🎭 MOCK_SEARCH mode enabled - returning mock data for: {query[:50]}...")
        return _generate_mock_results(query, max_results)
    
    # Always use Tavily - ignore provider_hint and env vars
    print(f"🔍 smart_search using Tavily: {query} (max_results={max_results})")
    return await _search_tavily(query, max_results)

# Removed: async def _search_exa(...) - Exa functionality disabled

async def _search_tavily(query: str, max_results: int) -> List[SearchHit]:
    """Execute search using Tavily and normalize results"""
    # Tavily search returns: {title, url, content, score, raw_content...}
    results = await tavily_search(
        query, 
        num_results=max_results,
        search_depth="basic"
    )
    
    hits = []
    for r in results:
        hits.append(SearchHit(
            url=r.get("url", ""),
            title=r.get("title", "") or "No title",
            snippet=r.get("content", ""),
            score=float(r.get("score", 0.0)) * 100.0 # Convert 0-1 to 0-100 if needed
        ))
        
    return hits

