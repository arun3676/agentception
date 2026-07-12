from __future__ import annotations

import asyncio
import uuid
from typing import Optional
from urllib.parse import quote_plus

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..memory import sql_store
from ..learning_path_service import generate_learning_path
from ..schemas import LearningPathRequest
from ..tools.resume_parser import _parse_skills
from ..tools.resume_store import TECH_SKILLS_KEYWORDS, _extract_keywords
from ..agentception2 import _role_seed_skills, summarize_applications
from ..auth import User, require_user
from .cache import cached_search

router = APIRouter(prefix="/api/v1")

# Curated job boards surfaced alongside resource recommendations
JOB_BOARDS = [
    {"title": "Wellfound (AngelList Talent)", "url": "https://wellfound.com/jobs"},
    {"title": "Y Combinator Jobs", "url": "https://www.workatastartup.com/"},
    {"title": "Hacker News Who's Hiring", "url": "https://news.ycombinator.com/jobs"},
    {"title": "LinkedIn Jobs", "url": "https://www.linkedin.com/jobs/"},
    {"title": "Otta", "url": "https://otta.com/"},
    {"title": "Built In", "url": "https://builtin.com/jobs"},
]


# --------- Resources ---------

@router.get("/resources")
async def list_resources(
    q: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    cost: Optional[str] = None,
    tag: Optional[str] = None,
    featured: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
):
    items = sql_store.resources_list(
        query=q,
        category=category,
        difficulty=difficulty,
        cost=cost,
        tag=tag,
        featured=featured,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "count": len(items)}


@router.get("/resources/{resource_id}")
async def get_resource(resource_id: str):
    resource = sql_store.resources_get(resource_id)
    if not resource:
        raise HTTPException(404, "Resource not found")
    return resource


# --------- Learning paths ---------

# Learning paths are user-owned rows, so every route here derives the owner from
# the verified JWT. They previously took `user_id` from the query string / request
# body, which meant anyone could list, read, or write as any user — no token needed.

@router.get("/learning-paths")
async def list_learning_paths(user: User = Depends(require_user)):
    paths = sql_store.learning_path_list(user_id=user.id)
    return {
        "paths": [
            {
                "id": p["id"],
                "title": p["title"],
                "topic": p["topic"],
                "expertise_level": p["expertise_level"],
                "created_at": p["created_at"],
            }
            for p in paths
        ]
    }


@router.get("/learning-paths/{path_id}")
async def get_learning_path(path_id: str, user: User = Depends(require_user)):
    record = sql_store.learning_path_get(path_id, user_id=user.id)
    if not record:
        # 404 for both "no such path" and "not yours" — a 403 would confirm the
        # id exists, which is itself a leak.
        raise HTTPException(404, "Learning path not found")
    return record["path"] or record


@router.post("/learning-paths/generate")
async def create_learning_path(req: LearningPathRequest, user: User = Depends(require_user)):
    try:
        # The owner comes from the token. `req.user_id` is ignored on purpose —
        # trusting it would let a client file a path under someone else's id.
        path = generate_learning_path(req, user_id=user.id)
        return path.model_dump()
    except Exception as e:
        raise HTTPException(500, f"Failed to generate learning path: {e}")


# --------- Skill gaps ---------

class SkillGapBody(BaseModel):
    resume_text: str
    job_text: Optional[str] = None
    target_role: Optional[str] = None


def _extract_all_skills(text: str) -> list[str]:
    buckets = _parse_skills(text)
    # Section parsing can return sentence fragments on unlabeled resumes —
    # keep only short, name-like entries (real skills are 1-3 words)
    skills = {
        s for bucket in buckets.values() for s in bucket
        if len(s) <= 40 and len(s.split()) <= 3 and " and " not in s.lower()
    }
    skills.update(_extract_keywords(text.lower(), TECH_SKILLS_KEYWORDS))
    return sorted(skills)


def _match_resources(skill: str, catalogue: list[dict], fallback: list[dict]) -> list[dict]:
    needle = skill.lower()
    matches = [
        r for r in catalogue
        if needle in (r.get("title") or "").lower() or needle in (r.get("description") or "").lower()
    ][:3]
    return matches or fallback


@router.post("/skill-gaps/analyze")
async def analyze_skill_gaps(body: SkillGapBody):
    if not body.resume_text.strip():
        raise HTTPException(400, "resume_text is required")

    resume_skills = _extract_all_skills(body.resume_text)

    if body.job_text and body.job_text.strip():
        target_skills = _extract_all_skills(body.job_text)
    else:
        target_skills = sorted(_role_seed_skills(body.target_role or "software engineer"))

    resume_lower = {s.lower() for s in resume_skills}
    missing_skills = [s for s in target_skills if s.lower() not in resume_lower]

    # One pass over the catalogue, then match every skill in memory — the previous
    # per-skill query re-read the whole ai_resources table once per missing skill.
    catalogue = sql_store.resources_list(limit=1000)
    fallback = sql_store.resources_featured(limit=3)
    recommendations = {
        skill: _match_resources(skill, catalogue, fallback)
        for skill in missing_skills[:6]
    }

    return {
        "analysis": {
            "resume_skills": resume_skills,
            "target_skills": target_skills,
            "missing_skills": missing_skills,
        },
        "recommendations": recommendations,
    }


# --------- Applications ---------

class ApplicationCreateBody(BaseModel):
    # No user_id. Ownership comes from the verified JWT; a body field that looks
    # like it sets the owner but is silently ignored is a trap for the next reader.
    company_name: str
    job_title: str
    job_url: str
    application_status: str = "applied"


class ApplicationUpdateBody(BaseModel):
    application_status: str


async def _check_listing(url: str) -> dict:
    """Check whether a public application URL still resolves; never infer hiring stage."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8.0, headers={"User-Agent": "AgentceptionJobCheck/1.0"}) as client:
            response = await client.get(url)
        closed = response.status_code in {404, 410}
        status = "closed" if closed else "open" if response.status_code < 400 else "unknown"
        return {"status": status, "checked_at": __import__("datetime").datetime.utcnow().isoformat(), "status_code": response.status_code}
    except Exception:
        return {"status": "unknown", "checked_at": __import__("datetime").datetime.utcnow().isoformat()}


@router.post("/applications")
async def create_application(body: ApplicationCreateBody, user: User = Depends(require_user)):
    record = sql_store.job_application_add(
        app_id=str(uuid.uuid4()),
        user_id=user.id,
        company_name=body.company_name,
        job_title=body.job_title,
        job_url=body.job_url,
        application_status=body.application_status,
    )
    return record


@router.get("/applications")
async def list_applications(user: User = Depends(require_user)):
    items = sql_store.job_applications_list(user_id=user.id)
    return {"items": items, "summary": summarize_applications(items)}


@router.put("/applications/{application_id}")
async def update_application(application_id: str, body: ApplicationUpdateBody, user: User = Depends(require_user)):
    record = sql_store.job_application_update_status(application_id, body.application_status, user_id=user.id)
    if not record:
        raise HTTPException(404, "Application not found")
    return record


@router.post("/applications/refresh-listings")
async def refresh_application_listings(user: User = Depends(require_user)):
    """Refresh public job-posting availability for saved applications.

    Recruiter-stage changes are intentionally left to the user unless an email or
    ATS integration is connected; public pages only expose whether a role is live.
    """
    apps = sql_store.job_applications_list(user_id=user.id)
    checks = await asyncio.gather(*[_check_listing(app["job_url"]) for app in apps]) if apps else []
    return {"items": [{"id": app["id"], **check} for app, check in zip(apps, checks)]}


# --------- Company intel ---------

_COMPANY_BRIEF_TTL = 24 * 3600


@router.get("/company/brief")
async def company_brief(name: str = Query(min_length=1, max_length=120)):
    """Short company intel card for a job result: what they do, recent news,
    where to apply. Tavily returns cleaned page content, so no scraping needed."""
    company = name.strip()

    from ..tools.tavily_search import tavily_search

    async def _search(query: str, **kwargs):
        try:
            return await tavily_search(query, **kwargs)
        except Exception as e:
            print(f"[CompanyBrief] search failed for '{query}': {e}")
            return []

    async def fetch() -> dict:
        overview_results, news_results = await asyncio.gather(
            _search(f"What does {company} do? company overview products", num_results=3),
            _search(f"{company} company news announcement funding", num_results=5),
        )
        return {
            "company": company,
            "overview": overview_results[0].get("content", "")[:600] if overview_results else "",
            "recent_news": [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")[:220]}
                for r in news_results[:4]
                if r.get("url")
            ],
            "careers_hint": f"https://www.google.com/search?q={quote_plus(company)}+careers",
        }

    return await cached_search(
        engine="company_brief",
        subject=company,
        params={},
        ttl_seconds=_COMPANY_BRIEF_TTL,
        fetch=fetch,
        should_cache=lambda p: bool(p["overview"] or p["recent_news"]),
    )


# --------- Recommendations ---------

@router.get("/recommendations")
async def recommendations(topic: Optional[str] = None):
    if topic:
        resources = sql_store.resources_list(query=topic, limit=12)
        if not resources:
            resources = sql_store.resources_featured(limit=12)
    else:
        resources = sql_store.resources_featured(limit=12)
    return {"resources": resources, "job_boards": JOB_BOARDS}
