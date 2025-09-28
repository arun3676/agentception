from __future__ import annotations
from typing import Dict, Any, Callable, Awaitable
from ..schemas import TimelineEvent, CompanyIntel, JobPosting
from ..rag.exa_company_discovery import discover_companies, DEBUG_DISCOVERY
from ..rag.roles import role_profile
from ..tools.resume_store import get_text as get_resume_text
from .enhanced_research_agent import EnhancedResearchAgent, IntelligenceType
from .job_search import check_job_availability
import asyncio


async def run_rag_company_search(
    run_id: str, 
    city: str, 
    role: str, 
    resume_token: str | None, 
    emit: Callable[[TimelineEvent], Awaitable[None]],
    multi_role: bool = True,
    depth: str = "standard"
) -> Dict[str, Any]:
    """
    Runs the full RAG pipeline:
    1. Geocodes city
    2. Discovers companies via Exa + semantic matching
    3. (Optional) Runs enhanced research for top N results
    4. Compiles a RAG document for the Writer agent
    """
    prof = role_profile(role)
    await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"Phase 1: Discovering {role}-aligned companies in {city} (depth: {depth})"))
    
    # 1. Discover companies
    # The discover_companies now returns CompanyIntel with refined homepage/name
    basic_companies = await discover_companies(city, role, k=20, depth=depth) # Get more initial companies
    await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"Found {len(basic_companies)} initial candidates. Now checking for job openings..."))

    # Phase 2: Check for job availability
    hiring_companies = []
    
    # Run checks in parallel
    async def check_company(company: CompanyIntel):
        try:
            if DEBUG_DISCOVERY: 
                await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"  Job check for: {company.name} (Homepage: {company.homepage})"))
            job_posting = await check_job_availability(company, role)
            if job_posting:
                company.job_posting = job_posting
                hiring_companies.append(company)
                await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"✅ Hiring: {role} at {company.name} - [Visit]({job_posting.url})"))
            else:
                await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"❌ Not hiring: {company.name}"))
        except Exception as e:
            # Log the error for the specific company but allow other checks to continue
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"⚠️ Error checking {company.name}: {e}"))

    # Check top 10 companies to balance speed and coverage
    await asyncio.gather(*[check_company(c) for c in basic_companies[:10]])

    await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"Found {len(hiring_companies)} companies with relevant job openings."))

    if not hiring_companies:
        await emit(TimelineEvent(run_id=run_id, agent="RAG", message="No companies with job openings found. Ending workflow."))
        return {"companies": []}


    # Phase 3: Run enhanced research on hiring companies
    researched_companies = hiring_companies
    
    # Determine research parameters from depth
    research_k, intel_types = 0, []
    if depth == "standard":
        research_k = 3
        intel_types = [IntelligenceType.RECENT_NEWS, IntelligenceType.TECH_STACK]
    elif depth == "deep":
        research_k = 5
        intel_types = [IntelligenceType.RECENT_NEWS, IntelligenceType.TECH_STACK, IntelligenceType.COMPETITIVE]

    if research_k > 0 and hiring_companies:
        companies_to_research = hiring_companies[:research_k]
        await emit(TimelineEvent(
            run_id=run_id, agent="RAG", 
            message=f"Phase 3: Running deep research on top {len(companies_to_research)} hiring companies..."
        ))
        try:
            # Convert CompanyIntel objects to dictionaries for enhanced research
            company_dicts = []
            for company in companies_to_research:
                company_dict = {
                    "name": company.name,
                    "homepage": company.homepage,
                    "source_url": company.source_url,
                    "blurb": company.blurb,
                    "city": company.city,
                    "tags": company.tags or [],
                    "contact_hint": company.contact_hint,
                    "score": company.score,
                    "job_posting": company.job_posting.model_dump() if company.job_posting else None,
                    "intel": company.intel # Pass existing intel if any
                }
                company_dicts.append(company_dict)
            
            agent = EnhancedResearchAgent(emit=emit, run_id=run_id)
            researched_companies = await agent.analyze_companies(company_dicts, intelligence_types=intel_types)
            
            # Convert back to CompanyIntel objects and merge with remaining companies
            enhanced_companies = []
            for company_dict in researched_companies:
                enhanced_company = CompanyIntel(
                    name=company_dict["name"],
                    homepage=company_dict["homepage"],
                    source_url=company_dict["source_url"],
                    blurb=company_dict.get("description", company_dict.get("blurb")),
                    city=company_dict["city"],
                    tags=company_dict.get("tags", []),
                    contact_hint=company_dict.get("contact_hint"),
                    score=company_dict["score"],
                    job_posting=JobPosting(**company_dict["job_posting"]) if company_dict.get("job_posting") else None,
                    # Add enhanced fields
                    competitors=company_dict.get("competitors", []),
                    funding_stage=company_dict.get("funding_stage"),
                    last_funding=company_dict.get("last_funding"),
                    key_people=company_dict.get("key_people", []),
                    tech_stack=company_dict.get("tech_stack", []),
                    market_position=company_dict.get("market_position"),
                    company_size=company_dict.get("company_size"),
                    growth_indicator=company_dict.get("growth_indicator"),
                    confidence_score=company_dict.get("confidence_score", 0.0),
                    data_sources=company_dict.get("data_sources", []),
                    last_updated=company_dict.get("last_updated"),
                    intel=company_dict.get("intel", {})
                )
                enhanced_companies.append(enhanced_company)
            
            # Merge back into original list
            merged_list = enhanced_companies + hiring_companies[research_k:]
            researched_companies = merged_list

        except Exception as e:
            await emit(TimelineEvent(run_id=run_id, agent="RAG", message=f"⚠️ Enhanced research failed: {e}. Falling back to basic info."))
            # Fallback to basic companies if research fails
            researched_companies = hiring_companies

    # 4. Compile RAG document
    resume = get_resume_text(resume_token) if resume_token else None
    doc = {
        "city": city, "role": role, "role_profile": prof,
        "companies": [c.model_dump() for c in researched_companies],
        "resume_excerpt": (resume[:2500] if resume else None)
    }
    await emit(TimelineEvent(run_id=run_id, agent="RAG", message="Phase 4: Compiled research document for Writer agent"))
    return doc
