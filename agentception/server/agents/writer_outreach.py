from __future__ import annotations
import os, textwrap, random, json
from typing import List, Dict, Any, Callable, Awaitable, Optional
import httpx
import re

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")


def _enforce_word_limit(text: str, max_words: int = 130) -> str:
    """Trim generated email bodies to the product word cap."""
    words = text.split()
    if len(words) <= max_words:
        return text
    trimmed = " ".join(words[:max_words]).rstrip(" ,;:-")
    if trimmed and trimmed[-1] not in ".!?":
        trimmed += "."
    return trimmed

# Import role_profile function to generate it if not in document
try:
    from ..rag.roles import role_profile
except ImportError:
    # Fallback if import fails
    def role_profile(role: str) -> Dict[str, Any]:
        return {"keywords": [], "value_props": [], "proofs": []}

TEMPLATE = textwrap.dedent("""\
You are an expert copywriter who writes short, sharp, professional outreach emails for experienced software and AI engineers.

Your job:
- Blend the candidate's resume highlights with the specific company and role.
- Sound confident, clear, and human.
- Make it easy for a busy hiring manager to say "yes" to a quick chat.

Hard rules:
- BODY must be under 130 words.
- Use normal email punctuation only. No emojis, no bullet symbols, no numbered citations, no brackets like [1] or (source).
- Do not mention any article names, blog titles, or news sources.
- Do not include any URLs or links.
- Do not say things like "according to the article" or "I saw in the source".
- Do not use markdown or formatting. Plain text only.

INPUT CONTEXT
- TARGET ROLE: {role} in {city}
- COMPANY: {company_name}
- COMPANY DESCRIPTION: {company_blurb}
- JOB TITLE: {job_title}
- JOB LOCATION: {job_location}
- JOB REQUIREMENTS (if any): {job_requirements}
- COMPANY-SPECIFIC INTELLIGENCE (if any): {intel_context}

- MY RESUME ROLE / HEADLINE: {resume_headline}
- MY KEY SKILLS: {resume_skills}
- MY EXPERIENCE SUMMARY: {resume_experience}
- MY RESUME HIGHLIGHTS: {resume_snip}

Your task:
Write a single cold outreach email that:
1) Opens by referencing something specific about the company, role, or problem space.
2) Connects that to the candidate's concrete strengths, projects, or impact.
3) Ends with a simple, low-friction call to action asking for a short call.

Output format (strict):
SUBJECT: <one concise subject line, max 12 words, reference role and company>

BODY:
<email body here in 3–5 short paragraphs, no more than 130 words total>
""")


def _get_field(obj: Any, *keys: str, default: Any = None) -> Any:
    """Helper to get field from dict or object, trying multiple key names."""
    if isinstance(obj, dict):
        for key in keys:
            if key in obj:
                return obj[key]
        return default
    else:
        # Try as object attributes
        for key in keys:
            value = getattr(obj, key, None)
            if value is not None:
                return value
        return default


def _format_intel(company: Dict[str, Any] | Any) -> str:
    """Formats the research intelligence into a string for the prompt.
    
    Supports both focused research (new) and enhanced research (old) formats.
    Returns intelligence without citations, sources, or article references
    to match the template requirements (no brackets, no sources mentioned).
    """
    intel = _get_field(company, "intel", default={})
    if not intel or not isinstance(intel, dict):
        return ""

    lines = []
    
    # Check if we have focused research data (new format - preferred)
    focused_research = intel.get("focused_research")
    if focused_research and isinstance(focused_research, dict):
        # Use focused research data - already clean, no citations
        ai_tech_focus = focused_research.get("AI_OR_TECH_FOCUS", "")
        if ai_tech_focus and ai_tech_focus != "none found":
            lines.append(f"AI/Tech focus: {ai_tech_focus}")
        
        recent_work = focused_research.get("RECENT_WORK", [])
        # Handle RECENT_WORK as list (new format) or string (old format)
        if isinstance(recent_work, list) and recent_work:
            # Join list items into a single string
            recent_work_text = " ".join(recent_work)
        elif isinstance(recent_work, str) and recent_work and "No specific" not in recent_work:
            recent_work_text = recent_work
        else:
            recent_work_text = ""
        
        if recent_work_text:
            # Clean up any remaining citation patterns just in case
            recent_work_clean = re.sub(r'\[.*?\]', '', recent_work_text)
            recent_work_clean = re.sub(r'\(.*?source.*?\)', '', recent_work_clean, flags=re.IGNORECASE)
            recent_work_clean = re.sub(r'according to.*?[,.]', '', recent_work_clean, flags=re.IGNORECASE)
            recent_work_clean = recent_work_clean.strip()
            if recent_work_clean:
                lines.append(f"Recent work: {recent_work_clean}")
        
        company_summary = focused_research.get("COMPANY_SUMMARY", "")
        if company_summary and len(company_summary) > 30:
            lines.append(f"Company: {company_summary}")
    
    # Also check for enhanced research data (old format - fallback or supplement)
    if not lines:  # Only use old format if we don't have focused research
        # Extract tech stack if available
        tech_stack = intel.get("tech_stack")
        if tech_stack:
            if isinstance(tech_stack, list):
                tech_stack_str = ", ".join(tech_stack)
            else:
                tech_stack_str = str(tech_stack)
            if tech_stack_str:
                lines.append(f"Tech stack: {tech_stack_str}")
        
        # Extract recent news/updates (without source citations)
        recent_news = intel.get("recent_news")
        if recent_news:
            # Remove any source citations or references
            news_text = str(recent_news)
            # Clean up common citation patterns
            news_text = re.sub(r'\[.*?\]', '', news_text)  # Remove [1], [source], etc
            news_text = re.sub(r'\(.*?source.*?\)', '', news_text, flags=re.IGNORECASE)
            news_text = re.sub(r'according to.*?[,.]', '', news_text, flags=re.IGNORECASE)
            news_text = news_text.strip()
            if news_text:
                lines.append(f"Recent developments: {news_text}")
        
        # Extract AI/tech focus from old format
        ai_tech_focus = intel.get("ai_tech_focus", "")
        if ai_tech_focus and ai_tech_focus != "none found":
            lines.append(f"AI/Tech focus: {ai_tech_focus}")
    
    # Extract additional info from both formats
    recent_work = intel.get("recent_work", "")
    if recent_work and "No specific" not in recent_work:
        recent_work_clean = re.sub(r'\[.*?\]', '', recent_work)
        recent_work_clean = re.sub(r'\(.*?source.*?\)', '', recent_work_clean, flags=re.IGNORECASE)
        if recent_work_clean.strip() and recent_work_clean.strip() not in [line for line in lines]:
            lines.append(f"Recent work: {recent_work_clean.strip()}")

    return "\n".join(lines)


async def write_emails(ragdoc: Dict[str, Any], n: int = 5, emit: Callable[[Any], Awaitable[None]] | None = None) -> List[Dict[str,str]]:
    """
    Generate targeted outreach emails using compact context and small model
    
    Args:
        ragdoc: RAG document with companies, role profile, resume
        n: Number of emails to generate
        emit: Optional function to emit timeline events
        
    Returns:
        List of email dictionaries with company, subject, body, mailto
    """
    if emit:
        await emit(f"📧 Generating {n} outreach emails for run {ragdoc.get('run_id', 'unknown')}")
    
    # Extract role and location (RAGDoc uses 'location', not 'city')
    role = ragdoc.get("role", "Unknown Role")
    city = ragdoc.get("location") or ragdoc.get("city", "Unknown Location")
    
    # Get role profile - either from document or generate it
    prof = ragdoc.get("role_profile")
    if not prof:
        # Generate role profile if not in document
        prof = role_profile(role)
    
    # Handle resume data (optional fields)
    resume_insights = ragdoc.get("resume_insights", {}) or {}
    resume_headline = resume_insights.get("role") or role
    skills_raw = resume_insights.get("skills", [])
    if isinstance(skills_raw, dict):
        flat = []
        for v in skills_raw.values():
            flat.extend(v)
        skills_raw = flat
    resume_skills = ", ".join((resume_insights.get("skills_flat") or skills_raw)[:10]) if (resume_insights.get("skills_flat") or skills_raw) else ", ".join(prof.get("value_props", []))
    if resume_insights.get("experience_years") is not None:
        resume_experience = f"{resume_insights.get('experience_years')} years of experience"
    else:
        resume_experience = ", ".join(prof.get("proofs", []))
    resume_snippet = (ragdoc.get("resume_excerpt") or "")[:400]
    
    # Get companies list - handle both dict and object formats
    companies = ragdoc.get("companies", [])
    print(f"🔍 write_emails: Found {len(companies)} companies in RAG document")
    
    # Convert Pydantic models to dicts if needed
    companies_list = []
    for c in companies:
        if hasattr(c, 'model_dump'):  # Pydantic model
            companies_list.append(c.model_dump())
        elif hasattr(c, '__dict__'):  # Regular object
            companies_list.append(c.__dict__)
        elif isinstance(c, dict):  # Already a dict
            companies_list.append(c)
        else:
            print(f"⚠️ Unknown company type: {type(c)}, skipping")
    
    print(f"🔍 Converted {len(companies_list)} companies to dict format")
    
    # Filter companies that have a VALID name (not "Unknown Company", role names, etc.)
    invalid_names = {
        "unknown company", "unknown", "n/a", "null", "none", "",
        role.lower(),  # Don't allow the role name as a company name
        "ai engineer", "software engineer", "data engineer",  # Common role names that shouldn't be companies
        "dice", "indeed", "linkedin", "glassdoor", "ziprecruiter", "simplyhired", "jooble", "adzuna", "hiringcafe",  # Job board names
    }
    
    picks = []
    for i, c in enumerate(companies_list):
        # Debug: print company structure
        if i < 2:  # Only print first 2 for debugging
            company_keys = list(c.keys()) if isinstance(c, dict) else []
            print(f"🔍 Company {i} keys: {company_keys[:10]}")  # First 10 keys
        
        company_name = _get_field(c, "name", "company_name", default=None)
        # Handle empty string case and validate name
        if company_name and isinstance(company_name, str):
            company_name = company_name.strip()
            company_name_lower = company_name.lower()
            
            # Check if it's a valid company name (not in invalid list)
            if (company_name and 
                len(company_name) > 1 and 
                len(company_name) < 100 and
                company_name_lower not in invalid_names and
                not company_name_lower.startswith("http") and  # Not a URL
                not any(invalid in company_name_lower for invalid in ["job board", "job site", "careers page"]) and
                # Extra check for aggregator substrings
                not any(agg in company_name_lower for agg in ["indeed.com", "glassdoor.com", "ziprecruiter.com", "linkedin.com"])):
                
                picks.append(c)
                print(f"✅ Added company to picks: {company_name} ({len(picks)}/{n})")
                if len(picks) >= n:
                    break
            else:
                print(f"⚠️ Skipped invalid company name: '{company_name}' (too short, invalid, or matches role/board name)")
        else:
            # Debug: show what we actually found
            all_keys = list(c.keys()) if isinstance(c, dict) else []
            name_value = c.get("name") if isinstance(c, dict) else None
            company_name_value = c.get("company_name") if isinstance(c, dict) else None
            print(f"⚠️ Skipped company {i}: no valid name found. Keys: {all_keys[:5]}, name={name_value}, company_name={company_name_value}")
    
    print(f"🔍 Total companies selected for email generation: {len(picks)}")
    
    if len(picks) == 0:
        error_msg = f"No companies found with valid names in RAG document. Total companies: {len(companies)}"
        print(f"❌ {error_msg}")
        if emit:
            await emit(f"⚠️ {error_msg}")
        return []
    
    # Research companies using focused research agent (for email personalization)
    if emit:
        await emit(f"🔍 Researching {len(picks)} companies for email personalization...")
    
    from .focused_research_agent import FocusedResearchAgent
    import asyncio
    
    async def research_single_company(company: Dict[str, Any]) -> Dict[str, Any]:
        """Research a single company and add intel to company dict"""
        company_name = _get_field(company, "name", "company_name", default="Unknown Company")
        
        # Skip research if company name is invalid
        invalid_names = {"unknown company", "unknown", "n/a", "null", "none", "", role.lower()}
        if not company_name or company_name.lower().strip() in invalid_names:
            print(f"⚠️ Skipping research for invalid company name: '{company_name}'")
            if emit:
                await emit(f"⚠️ Skipping research for invalid company: '{company_name}'")
            return company  # Return as-is without research
        
        homepage = _get_field(company, "homepage", "homepage_url") or _get_field(company, "source_url", default="")
        
        if not homepage or homepage == "":
            # No homepage to research, return company as-is
            print(f"⚠️ No homepage URL for {company_name}, skipping research")
            return company
        
        try:
            # Get job URL if available
            job_posting = _get_field(company, "job_posting", default={})
            job_url = None
            if job_posting and isinstance(job_posting, dict):
                job_url = job_posting.get("url")
            
            async with FocusedResearchAgent(emit=emit) as research_agent:
                research_data = await research_agent.research_company(
                    company_name=company_name,
                    homepage_url=homepage,
                    target_role_title=role,
                    job_url=job_url
                )
                
                # Store research data in company dict under "intel" key
                # RECENT_WORK is now a list, so we need to handle it properly
                recent_work_list = research_data.get("RECENT_WORK", [])
                recent_work_text = " ".join(recent_work_list) if isinstance(recent_work_list, list) else str(recent_work_list)
                
                company["intel"] = {
                    "company_summary": research_data.get("COMPANY_SUMMARY", ""),
                    "recent_work": recent_work_text,  # Convert list to text for backward compatibility
                    "ai_tech_focus": research_data.get("AI_OR_TECH_FOCUS", ""),
                    "recent_news": recent_work_text,  # Use recent_work as recent_news
                    "tech_stack": research_data.get("AI_OR_TECH_FOCUS", ""),  # Use AI focus as tech stack indicator
                    "focused_research": research_data,  # Store full research data (with RECENT_WORK as list)
                    # Surface convenience fields
                    "best_contact_email": research_data.get("BEST_CONTACT_EMAIL", "unknown"),
                    "best_contact_name": research_data.get("BEST_CONTACT_NAME", "Hiring Manager")
                }
                
                # Update contact info if found
                contact_name = research_data.get("BEST_CONTACT_NAME", "Hiring Manager")
                contact_email = research_data.get("BEST_CONTACT_EMAIL", "unknown")
                
                if contact_email != "unknown":
                    # Remove guess marker if present
                    clean_email = contact_email.replace(" (guessed)", "").replace(" (Guessed)", "")
                    company["recipient_email"] = clean_email
                    company["contact_hint"] = clean_email
                
                if contact_name and contact_name != "Hiring Manager":
                    company["contact_name"] = contact_name
                
                print(f"✅ Research complete for {company_name}")
                return company
                
        except Exception as e:
            print(f"⚠️ Research failed for {company_name}: {e}")
            if emit:
                await emit(f"⚠️ Research failed for {company_name}: {str(e)[:100]}")
            return company  # Return company without research if it fails
    
    # Research all companies in parallel
    research_tasks = [research_single_company(company) for company in picks]
    picks = await asyncio.gather(*research_tasks, return_exceptions=True)
    
    # Filter out any exceptions and ensure we have valid companies
    valid_picks = []
    for pick in picks:
        if isinstance(pick, Exception):
            print(f"⚠️ Company research task failed: {pick}")
        elif isinstance(pick, dict):
            valid_picks.append(pick)
    
    picks = valid_picks[:n]  # Ensure we don't exceed n
    
    if emit:
        await emit(f"✅ Company research complete. Generating emails for {len(picks)} companies...")
    
    # Build resume summary for email (compact summary with 1-3 standout projects/skills)
    resume_summary_parts = []
    if resume_snippet:
        # Use first 2-3 sentences from resume excerpt
        sentences = re.split(r'[.!?]+', resume_snippet)
        resume_summary_parts.extend([s.strip() for s in sentences[:3] if len(s.strip()) > 20])
    
    if resume_skills:
        # Add top skills
        skills_list = resume_skills.split(", ")[:3]  # Top 3 skills
        resume_summary_parts.append(f"Key skills: {', '.join(skills_list)}")
    
    if resume_experience:
        resume_summary_parts.append(f"Experience: {resume_experience}")
    
    resume_summary_for_email = ". ".join(resume_summary_parts) if resume_summary_parts else f"{resume_headline} with experience in {role}."
    
    out = []

    for i, c in enumerate(picks):
        company_name = _get_field(c, "name", "company_name", default="Unknown Company")
        if emit:
            await emit(f"Drafting email {i+1}/{len(picks)} for {company_name}...")

        # Get job posting information
        job_posting = _get_field(c, "job_posting", default={})
        if job_posting and not isinstance(job_posting, dict):
            if hasattr(job_posting, "model_dump"):
                job_posting = job_posting.model_dump()
            elif hasattr(job_posting, "__dict__"):
                job_posting = job_posting.__dict__
            else:
                job_posting = {}
        
        # Extract job details
        job_title = job_posting.get("title") if isinstance(job_posting, dict) else None
        if not job_title:
            job_title = _get_field(c, "job_title") or role
        
        job_location = job_posting.get("location") if isinstance(job_posting, dict) else None
        if not job_location:
            job_location = _get_field(c, "job_location") or city
        
        job_url = None
        if isinstance(job_posting, dict):
            # CRITICAL: Prefer apply_url (specific job posting) over url (might be listing page)
            job_url = job_posting.get("apply_url") or job_posting.get("url")
        job_url = job_url or _get_field(c, "source_url")
        
        # Get company intel (focused research)
        company_intel = c.get("intel", {}).get("focused_research", {})
        if not company_intel or not isinstance(company_intel, dict):
            company_intel = {}
        
        # Generate email using spec format
        try:
            email_data = await write_email_spec_format(
                role=role,
                location=city,
                company_name=company_name,
                job_title=job_title,
                job_location=job_location,
                job_url=job_url,
                company_intel=company_intel,
                resume_summary=resume_summary_for_email,
                candidate_name="Your Name",  # Could be extracted from resume if available
                emit=emit
            )
            
            # Build email dict with new structure
            email_dict = {
                "company": company_name,
                "company_name": company_name,  # Also include for compatibility
                "job_title": job_title,
                "job_location": job_location,
                "job_url": job_url,
                "subject": email_data["subject"],
                "body": email_data["body"],
                "to_email": email_data["contact_email"],
                "to_name": email_data["contact_name"],
                "email_is_guess": email_data.get("email_is_guess", True),
                # Also include old fields for backward compatibility
                "mailto": email_data["contact_email"],
                "recipient_email": email_data["contact_email"]
            }
            
            # Validate email has content
            if not email_data["subject"] or not email_data["body"] or len(email_data["body"].strip()) < 10:
                print(f"⚠️ Email for {company_name} appears empty/invalid: subj='{email_data['subject'][:50]}', body_len={len(email_data['body'])}")
            
            out.append(email_dict)
            print(f"✅ Generated email {i+1}/{len(picks)} for {company_name}: subject='{email_data['subject'][:50]}...', body_len={len(email_data['body'])}")
            
        except Exception as e:
            if emit:
                await emit(f"⚠️ Email generation failed for {company_name}: {e}")
            print(f"❌ Email generation failed for {company_name}: {e}")
            # Continue to next company instead of failing completely

    print(f"🔍 Final email list: {len(out)} emails generated")
    for i, email in enumerate(out):
        print(f"  Email {i+1}: company={email.get('company')}, subject_len={len(email.get('subject', ''))}, body_len={len(email.get('body', ''))}")
    
    if emit:
        await emit(f"✅ Generated {len(out)} personalized emails.")
    return out


async def write_emails_incremental(
    ragdoc: Dict[str, Any], 
    n: int = 5, 
    emit: Callable[[Any], Awaitable[None]] | None = None,
    memory_store: Any = None,
    run_id: str = ""
) -> List[Dict[str,str]]:
    """
    Generate targeted outreach emails with incremental storage.
    Stores each email as it's generated so frontend can display them immediately.
    
    This is the same as write_emails but stores emails incrementally in memory.
    """
    # Use the regular write_emails function but intercept emails as they're generated
    # We'll modify the loop to store incrementally
    
    if emit:
        await emit(f"📧 Generating {n} outreach emails (will appear as ready)...")
    
    # Extract role and location
    role = ragdoc.get("role", "Unknown Role")
    city = ragdoc.get("location") or ragdoc.get("city", "Unknown Location")
    
    # Get role profile
    prof = ragdoc.get("role_profile")
    if not prof:
        prof = role_profile(role)
    
    # Handle resume data
    resume_insights = ragdoc.get("resume_insights", {}) or {}
    resume_headline = resume_insights.get("role") or role
    skills_raw = resume_insights.get("skills", [])
    if isinstance(skills_raw, dict):
        flat = []
        for v in skills_raw.values():
            flat.extend(v)
        skills_raw = flat
    resume_skills = ", ".join((resume_insights.get("skills_flat") or skills_raw)[:10]) if (resume_insights.get("skills_flat") or skills_raw) else ", ".join(prof.get("value_props", []))
    if resume_insights.get("experience_years") is not None:
        resume_experience = f"{resume_insights.get('experience_years')} years of experience"
    else:
        resume_experience = ", ".join(prof.get("proofs", []))
    resume_snippet = (ragdoc.get("resume_excerpt") or "")[:400]
    
    # Get companies list
    companies = ragdoc.get("companies", [])
    
    # Convert to dicts
    companies_list = []
    for c in companies:
        if hasattr(c, 'model_dump'):
            companies_list.append(c.model_dump())
        elif hasattr(c, '__dict__'):
            companies_list.append(c.__dict__)
        elif isinstance(c, dict):
            companies_list.append(c)
    
    # Filter companies with names
    picks = []
    for i, c in enumerate(companies_list):
        company_name = _get_field(c, "name", "company_name", default=None)
        if company_name and isinstance(company_name, str) and company_name.strip():
            picks.append(c)
            if len(picks) >= n:
                break
    
    if len(picks) == 0:
        if emit:
            await emit(f"⚠️ No companies found with valid names")
        return []
    
    # Research companies
    if emit:
        await emit(f"🔍 Researching {len(picks)} companies...")
    
    from .focused_research_agent import FocusedResearchAgent
    import asyncio
    
    async def research_single_company(company: Dict[str, Any]) -> Dict[str, Any]:
        company_name = _get_field(company, "name", "company_name", default="Unknown Company")
        homepage = _get_field(company, "homepage", "homepage_url") or _get_field(company, "source_url", default="")
        
        if not homepage or homepage == "":
            return company
        
        try:
            job_posting = _get_field(company, "job_posting", default={})
            job_url = None
            if job_posting and isinstance(job_posting, dict):
                job_url = job_posting.get("url")
            
            async with FocusedResearchAgent(emit=emit) as research_agent:
                research_data = await research_agent.research_company(
                    company_name=company_name,
                    homepage_url=homepage,
                    target_role_title=role,
                    job_url=job_url
                )
                
                recent_work_list = research_data.get("RECENT_WORK", [])
                recent_work_text = " ".join(recent_work_list) if isinstance(recent_work_list, list) else str(recent_work_list)
                
                company["intel"] = {
                    "company_summary": research_data.get("COMPANY_SUMMARY", ""),
                    "recent_work": recent_work_text,
                    "ai_tech_focus": research_data.get("AI_OR_TECH_FOCUS", ""),
                    "recent_news": recent_work_text,
                    "tech_stack": research_data.get("AI_OR_TECH_FOCUS", ""),
                    "focused_research": research_data,
                    "best_contact_email": research_data.get("BEST_CONTACT_EMAIL", "unknown"),
                    "best_contact_name": research_data.get("BEST_CONTACT_NAME", "Hiring Manager")
                }
                
                contact_email = research_data.get("BEST_CONTACT_EMAIL", "unknown")
                if contact_email != "unknown":
                    clean_email = contact_email.replace(" (guessed)", "").replace(" (Guessed)", "")
                    company["recipient_email"] = clean_email
                    company["contact_hint"] = clean_email
                
                return company
        except Exception as e:
            print(f"⚠️ Research failed for {company_name}: {e}")
            return company
    
    research_tasks = [research_single_company(company) for company in picks]
    picks = await asyncio.gather(*research_tasks, return_exceptions=True)
    
    valid_picks = []
    for pick in picks:
        if isinstance(pick, Exception):
            print(f"⚠️ Company research task failed: {pick}")
        elif isinstance(pick, dict):
            valid_picks.append(pick)
    
    picks = valid_picks[:n]
    
    if emit:
        await emit(f"✅ Research complete. Generating emails...")
    
    # Build resume summary
    resume_summary_parts = []
    if resume_snippet:
        sentences = re.split(r'[.!?]+', resume_snippet)
        resume_summary_parts.extend([s.strip() for s in sentences[:3] if len(s.strip()) > 20])
    if resume_skills:
        skills_list = resume_skills.split(", ")[:3]
        resume_summary_parts.append(f"Key skills: {', '.join(skills_list)}")
    if resume_experience:
        resume_summary_parts.append(f"Experience: {resume_experience}")
    
    resume_summary_for_email = ". ".join(resume_summary_parts) if resume_summary_parts else f"{resume_headline} with experience in {role}."
    
    out = []
    
    # Generate emails one by one and store incrementally
    for i, c in enumerate(picks):
        company_name = _get_field(c, "name", "company_name", default="Unknown Company")
        if emit:
            await emit(f"✍️ Generating email {i+1}/{len(picks)} for {company_name}...")
        
        # Get job posting information
        job_posting = _get_field(c, "job_posting", default={})
        if job_posting and not isinstance(job_posting, dict):
            if hasattr(job_posting, "model_dump"):
                job_posting = job_posting.model_dump()
            elif hasattr(job_posting, "__dict__"):
                job_posting = job_posting.__dict__
            else:
                job_posting = {}
        
        job_title = job_posting.get("title") if isinstance(job_posting, dict) else None
        if not job_title:
            job_title = _get_field(c, "job_title") or role
        
        job_location = job_posting.get("location") if isinstance(job_posting, dict) else None
        if not job_location:
            job_location = _get_field(c, "job_location") or city
        
        job_url = None
        if isinstance(job_posting, dict):
            # CRITICAL: Prefer apply_url (specific job posting) over url (might be listing page)
            job_url = job_posting.get("apply_url") or job_posting.get("url")
        job_url = job_url or _get_field(c, "source_url")
        
        company_intel = c.get("intel", {}).get("focused_research", {})
        if not company_intel or not isinstance(company_intel, dict):
            company_intel = {}
        
        # Generate email
        try:
            email_data = await write_email_spec_format(
                role=role,
                location=city,
                company_name=company_name,
                job_title=job_title,
                job_location=job_location,
                job_url=job_url,
                company_intel=company_intel,
                resume_summary=resume_summary_for_email,
                candidate_name="Your Name",
                emit=emit
            )
            
            email_dict = {
                "company": company_name,
                "company_name": company_name,
                "job_title": job_title,
                "job_location": job_location,
                "job_url": job_url,
                "subject": email_data["subject"],
                "body": email_data["body"],
                "to_email": email_data["contact_email"],
                "to_name": email_data["contact_name"],
                "email_is_guess": email_data.get("email_is_guess", True),
                "mailto": email_data["contact_email"],
                "recipient_email": email_data["contact_email"]
            }
            
            if not email_data["subject"] or not email_data["body"] or len(email_data["body"].strip()) < 10:
                print(f"⚠️ Email for {company_name} appears empty/invalid")
            
            out.append(email_dict)
            
            # Store incrementally in memory
            if memory_store and run_id:
                artifacts = memory_store.get(f"artifacts:{run_id}", {
                    "events": [],
                    "housing": [],
                    "places": [],
                    "emails": []
                })
                artifacts["emails"] = out.copy()  # Store current list
                memory_store.set(f"artifacts:{run_id}", artifacts)
                print(f"💾 Stored email {i+1}/{len(picks)} incrementally for {company_name}")
            
            if emit:
                await emit(f"✅ Email {i+1}/{len(picks)} ready for {company_name}")
            
            print(f"✅ Generated email {i+1}/{len(picks)} for {company_name}: subject='{email_data['subject'][:50]}...', body_len={len(email_data['body'])}")
            
        except Exception as e:
            if emit:
                await emit(f"⚠️ Email generation failed for {company_name}: {e}")
            print(f"❌ Email generation failed for {company_name}: {e}")
    
    if emit:
        await emit(f"✅ Generated {len(out)} personalized emails.")
    return out


# ============================================================================
# NEW EMAIL GENERATION FUNCTION - FOLLOWS USER'S EXACT SPECIFICATIONS
# ============================================================================

EMAIL_TEMPLATE_SPEC = textwrap.dedent("""
You are Agentception's outreach brain.

You write short, natural cold emails from a candidate to a company about a specific role.

You receive:
- ROLE and LOCATION the candidate is targeting
- COMPANY_NAME and JOB_TITLE
- JOB_INFO: a short summary of the job or job posting if available
- COMPANY_INTEL: structured research about the company (summary, recent work, tech focus, best contact info)
- RESUME_SUMMARY: a compact summary of the candidate's experience and 1–3 standout projects/skills

Your job:
- Write an email that feels like a real human wrote it.
- Open with **something specific about the company or role**, not about the candidate.
- Use at least **one concrete detail** from COMPANY_INTEL.RECENT_WORK or COMPANY_INTEL.AI_OR_TECH_FOCUS
  in the first or second sentence (e.g. reference a recent product, blog theme, or initiative in plain language).
- Weave in 1–2 points from RESUME_SUMMARY that clearly match those company details.
- Keep it confident, friendly, and concise. No fluff.

Hard rules:
- Do NOT mention any sources, URLs, or article titles.
- Do NOT say "I read on your blog" or "I saw in an article". Just reference the work directly.
- No emojis, no markdown, no bullet points in the final email.
- Subject line should be short and specific to the role (ideally include the role and location or team).
- Body should be **3 short paragraphs max** plus an optional one-line closing sentence.
- Body must be **120 words or fewer**.

Return JSON only, with exactly this structure:

{
  "subject": "short subject line",
  "body": "plain-text email body, including greeting and sign-off, all in one string",
  "contact_email": "email to send to (may be guessed from COMPANY_INTEL)",
  "contact_name": "name used in greeting (e.g. 'Alex' or 'Hiring Manager')",
  "email_is_guess": true or false
}

If you have a strong candidate-specific contact (from COMPANY_INTEL), set email_is_guess to false.
Otherwise, set email_is_guess to true even if you provide a reasonable generic email.
""")


async def write_email_spec_format(
    role: str,
    location: str,
    company_name: str,
    job_title: str,
    job_location: str,
    job_url: Optional[str],
    company_intel: Dict[str, Any],
    resume_summary: str,
    candidate_name: str = "Your Name",
    emit: Callable[[Any], Awaitable[None]] | None = None
) -> Dict[str, Any]:
    """
    Generate a single outreach email following the spec-style prompt.
    
    Args:
        role: The role the candidate is targeting (e.g., "AI Engineer")
        location: Location (e.g., "San Francisco, CA")
        company_name: Company name
        job_title: Job title
        job_location: Job location
        job_url: Optional job posting URL
        company_intel: Dict with COMPANY_SUMMARY, RECENT_WORK (list), AI_OR_TECH_FOCUS,
                       BEST_CONTACT_NAME, BEST_CONTACT_EMAIL
        resume_summary: Compact summary of candidate's experience and standout projects/skills
        candidate_name: Name to sign the email with (default: "Your Name")
        emit: Optional function to emit timeline events
        
    Returns:
        Dict with:
        - subject: Email subject line
        - body: Plain-text email body (including greeting and sign-off)
        - contact_email: Email to send to
        - contact_name: Name used in greeting
        - email_is_guess: Boolean indicating if email is a guess
    """
    if emit:
        await emit(f"📧 Generating email for {company_name}...")
    
    # Extract company intel data
    company_summary = company_intel.get("COMPANY_SUMMARY", "")
    recent_work = company_intel.get("RECENT_WORK", [])
    # Handle RECENT_WORK as list or string
    if isinstance(recent_work, list):
        recent_work_text = " ".join(recent_work) if recent_work else ""
    else:
        recent_work_text = str(recent_work) if recent_work else ""
    
    ai_tech_focus = company_intel.get("AI_OR_TECH_FOCUS", "none found")
    contact_name = company_intel.get("BEST_CONTACT_NAME", "Hiring Manager")
    contact_email = company_intel.get("BEST_CONTACT_EMAIL", "unknown")
    
    # Build job info summary
    job_info_text = f"Job title: {job_title}"
    if job_location:
        job_info_text += f", Location: {job_location}"
    if job_url:
        job_info_text += f", URL: {job_url}"
    
    # Format company intel for prompt
    company_intel_text = f"""COMPANY_SUMMARY: {company_summary}
RECENT_WORK: {recent_work_text}
AI_OR_TECH_FOCUS: {ai_tech_focus}
BEST_CONTACT_NAME: {contact_name}
BEST_CONTACT_EMAIL: {contact_email}"""
    
    # Build prompt
    prompt = f"""{EMAIL_TEMPLATE_SPEC}

ROLE: {role}
LOCATION: {location}
COMPANY_NAME: {company_name}
JOB_TITLE: {job_title}
JOB_INFO: {job_info_text}

COMPANY_INTEL:
{company_intel_text}

RESUME_SUMMARY: {resume_summary}

Now generate the email and return ONLY valid JSON (no markdown, no code blocks, no explanations):
"""
    
    # Fallback values
    fallback_subject = f"{role} – {company_name}"
    fallback_body = f"""Hi {contact_name},

I'm interested in the {role} role at {company_name}. My background in {resume_summary[:100]} aligns well with your team's work.

Would you be open to a brief 15–20 minute chat next week to see if my background could be useful for your team?

Best,

{candidate_name}"""
    
    # Default values
    subject = fallback_subject
    body = fallback_body
    result_contact_email = contact_email if contact_email != "unknown" else "unknown"
    result_contact_name = contact_name if contact_name != "Hiring Manager" else "Hiring Manager"
    email_is_guess = True  # Default to guess unless we have a strong contact
    
    # Determine if email is a guess
    if contact_email != "unknown" and "@" in contact_email:
        # Check if it's a specific person's email (not generic)
        if " (guessed)" not in contact_email and contact_name != "Hiring Manager":
            email_is_guess = False
        else:
            email_is_guess = True
            # Clean guess marker
            result_contact_email = contact_email.replace(" (guessed)", "").replace(" (Guessed)", "")
    else:
        result_contact_email = "unknown"
    
    try:
        if not DEEPSEEK_KEY:
            raise ValueError("DEEPSEEK_API_KEY not set")
        
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.6,  # Slightly higher for more natural tone
                    "max_tokens": 600
                }
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        
        # Parse JSON from response (may be wrapped in markdown code blocks)
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        # Try to extract JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            json_str = json_match.group(0)
            email_data = json.loads(json_str)
        else:
            # Try parsing the whole text
            email_data = json.loads(text)
        
        # Extract fields from JSON
        subject = email_data.get("subject", fallback_subject)
        body = email_data.get("body", fallback_body)
        result_contact_email = email_data.get("contact_email", result_contact_email)
        result_contact_name = email_data.get("contact_name", result_contact_name)
        email_is_guess = email_data.get("email_is_guess", email_is_guess)
        
        # Replace placeholder name if present
        body = body.replace("<Your Name>", candidate_name)
        body = body.replace("Your Name", candidate_name)
        
        # Clean body - remove any markdown, URLs, job board references
        body = re.sub(r'https?://\S+', '', body)  # Remove URLs
        body = re.sub(r'\*\*([^*]+)\*\*', r'\1', body)  # Remove bold markdown
        body = re.sub(r'\*([^*]+)\*', r'\1', body)  # Remove italic markdown
        body = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', body)  # Remove markdown links
        body = re.sub(r'[-•]\s+', '', body)  # Remove bullet points
        body = re.sub(r'\n\n+', '\n\n', body)  # Normalize multiple newlines
        body = body.strip()
        
    except json.JSONDecodeError as e:
        if emit:
            await emit(f"⚠️ Failed to parse LLM JSON response: {e}")
        print(f"⚠️ JSON parse error: {e}, response: {text[:200] if 'text' in locals() else 'N/A'}")
    except Exception as e:
        if emit:
            await emit(f"⚠️ LLM generation failed: {e}. Using fallback.")
        print(f"❌ LLM generation failed: {e}")
    
    body = _enforce_word_limit(body, 130)

    # Build result
    result = {
        "subject": subject,
        "body": body,
        "contact_email": result_contact_email,
        "contact_name": result_contact_name,
        "email_is_guess": email_is_guess
    }
    
    if emit:
        await emit(f"✅ Email generated for {company_name}")
    
    return result
