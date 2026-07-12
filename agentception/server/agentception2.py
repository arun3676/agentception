from __future__ import annotations

import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, HttpUrl


COMMON_SKILLS_BY_ROLE: dict[str, list[str]] = {
    "ai": ["Python", "RAG", "LLMs", "Vector Databases", "FastAPI", "Evaluation", "Prompt Engineering", "Embeddings"],
    "ml": ["Python", "PyTorch", "Model Evaluation", "Feature Engineering", "MLOps", "Experiment Tracking"],
    "data": ["SQL", "Python", "Data Modeling", "ETL", "Warehousing", "Analytics"],
    "full": ["TypeScript", "React", "FastAPI", "PostgreSQL", "API Design", "Testing"],
    "backend": ["Python", "FastAPI", "API Design", "PostgreSQL", "Redis", "Observability"],
    "frontend": ["TypeScript", "React", "Accessibility", "State Management", "Testing", "Design Systems"],
}

SYSTEM_PATTERNS = [
    "API design",
    "background jobs",
    "caching",
    "data pipelines",
    "observability",
    "security",
    "testing",
]

SOFT_SKILLS = ["communication", "ownership", "collaboration", "product thinking", "debugging"]

APPLICATION_OUTCOMES = ["applied", "ghosted", "rejected", "phone_screen", "onsite", "offer"]
APPLICATION_STORE: list[dict[str, Any]] = []


class CareerReverseEngineerRequest(BaseModel):
    target_role: str = Field(min_length=2, max_length=100)
    city: str = Field(default="Remote", max_length=100)
    dream_companies: list[str] = Field(default_factory=list, max_length=20)
    current_skills: list[str] = Field(default_factory=list, max_length=50)
    job_descriptions: list[str] = Field(default_factory=list, max_length=100)
    weeks: int = Field(default=12, ge=4, le=12)


class ProjectBriefRequest(BaseModel):
    target_role: str = Field(min_length=2, max_length=100)
    week: int = Field(default=1, ge=1, le=12)
    theme: Optional[str] = None
    skills: list[str] = Field(default_factory=list, max_length=20)
    project_title: Optional[str] = Field(default=None, max_length=120)


class SkillReceiptRequest(BaseModel):
    project_title: str = Field(min_length=2, max_length=120)
    skills: list[str] = Field(default_factory=list, max_length=30)
    github_url: Optional[HttpUrl] = None
    deployment_url: Optional[HttpUrl] = None
    commit_count: int = Field(default=0, ge=0, le=10000)
    checks_passed: bool = False
    code_quality_score: int = Field(default=70, ge=0, le=100)


class TrustProfileRequest(BaseModel):
    username: str = Field(min_length=2, max_length=60, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    target_role: str = Field(min_length=2, max_length=100)
    verified_skills: list[str] = Field(default_factory=list, max_length=60)
    skill_receipts: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    learning_weeks_completed: int = Field(default=0, ge=0, le=52)
    applications: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    peer_reviews: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    public_fields: list[str] = Field(default_factory=lambda: ["skills", "projects", "trust_score"])


class ApplicationLogRequest(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=2, max_length=120)
    status: Literal["applied", "ghosted", "rejected", "phone_screen", "onsite", "offer"] = "applied"
    resume_version: Optional[str] = Field(default=None, max_length=120)
    ats_score: Optional[int] = Field(default=None, ge=0, le=100)
    included_cover_letter: bool = False
    portfolio_project_count: int = Field(default=0, ge=0, le=100)


class ApplicationRecommendationRequest(BaseModel):
    applications: list[ApplicationLogRequest] = Field(default_factory=list, max_length=200)


class CohortProfile(BaseModel):
    username: str = Field(min_length=2, max_length=60)
    target_role: str = Field(min_length=2, max_length=100)
    timezone: str = Field(default="UTC", max_length=80)
    skills: list[str] = Field(default_factory=list, max_length=60)
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    weekly_goal: Optional[str] = Field(default=None, max_length=200)


class CohortMatchRequest(BaseModel):
    target_profile: CohortProfile
    candidates: list[CohortProfile] = Field(default_factory=list, max_length=100)
    cohort_size: int = Field(default=6, ge=2, le=8)


def _normalise_skill(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).title()


def _role_seed_skills(role: str) -> list[str]:
    role_l = role.lower()
    for key, skills in COMMON_SKILLS_BY_ROLE.items():
        if key in role_l:
            return skills.copy()
    return ["Python", "TypeScript", "API Design", "Testing", "GitHub", "Deployment"]


def _extract_skill_graph(role: str, docs: list[str], current_skills: list[str]) -> dict[str, Any]:
    text = "\n".join(docs).lower()
    seed = _role_seed_skills(role)
    keywords = seed + [
        "React",
        "Next.js",
        "FastAPI",
        "Django",
        "PostgreSQL",
        "Redis",
        "Docker",
        "Kubernetes",
        "AWS",
        "OpenAI",
        "DeepSeek",
        "Voyage",
        "Tavily",
        "Exa",
        "Evaluation",
        "Security",
        "CI/CD",
    ]
    counts: Counter[str] = Counter()
    for skill in keywords:
        pattern = re.escape(skill.lower()).replace(r"\ ", r"[\s-]+")
        mentions = len(re.findall(rf"\b{pattern}\b", text))
        if mentions:
            counts[_normalise_skill(skill)] += mentions
    for skill in seed:
        counts[_normalise_skill(skill)] += 1

    hard_skills = [skill for skill, _ in counts.most_common(14)]
    current = {_normalise_skill(skill) for skill in current_skills}
    gaps = [skill for skill in hard_skills if skill not in current]
    systems = [pattern for pattern in SYSTEM_PATTERNS if pattern.lower() in text] or SYSTEM_PATTERNS[:5]
    soft = [skill.title() for skill in SOFT_SKILLS if skill in text] or ["Communication", "Ownership", "Collaboration"]
    evidence = [
        {"skill": skill, "mentions": counts.get(skill, 1)}
        for skill in hard_skills[:8]
    ]
    return {
        "hard_skills": hard_skills,
        "system_design_patterns": systems,
        "soft_skills": soft,
        "gaps": gaps,
        "evidence": evidence,
    }


def reverse_engineer_career(request: CareerReverseEngineerRequest) -> dict[str, Any]:
    graph = _extract_skill_graph(request.target_role, request.job_descriptions, request.current_skills)
    skills = graph["hard_skills"] or _role_seed_skills(request.target_role)
    weeks = []
    for idx in range(request.weeks):
        skill = skills[idx % len(skills)]
        supporting = skills[idx % len(skills): idx % len(skills) + 3] or skills[:3]
        week_number = idx + 1
        theme = f"{skill} for {request.target_role}"
        project = f"Build a {skill} proof project for {request.target_role}"
        if idx >= request.weeks - 3:
            project = f"Ship and document a recruiter-ready {skill} capstone"
        weeks.append({
            "week": week_number,
            "theme": theme,
            "learning_module": f"Study real {request.target_role} job requirements around {skill}.",
            "micro_project": project,
            "measurable_output": f"Public README, working demo, and 3 evidence bullets showing {skill}.",
            "skills": supporting,
            "success_criteria": [
                "Runs locally from README instructions",
                "Includes tests or a reproducible evaluation",
                "Has a public artifact URL or screenshot",
            ],
        })
    return {
        "phase": "career_reverse_engineer",
        "target_role": request.target_role,
        "city": request.city,
        "dream_companies": request.dream_companies,
        "source_summary": {
            "job_descriptions_analyzed": len(request.job_descriptions),
            "current_skills_count": len(request.current_skills),
            "generated_without_supabase": True,
        },
        "skill_graph": graph,
        "roadmap": weeks,
    }


def generate_project_brief(request: ProjectBriefRequest) -> dict[str, Any]:
    skills = request.skills or _role_seed_skills(request.target_role)[:4]
    title = request.project_title or f"Week {request.week}: {skills[0]} proof project"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]
    return {
        "id": f"brief_{uuid4().hex[:10]}",
        "title": title,
        "slug": slug,
        "target_role": request.target_role,
        "week": request.week,
        "problem_statement": f"Prove you can use {', '.join(skills[:3])} in a realistic {request.target_role} workflow.",
        "tech_stack": skills,
        "deliverables": [
            "GitHub repository with clean README",
            "Small working demo or API endpoint",
            "Test or evaluation output",
            "Short write-up explaining tradeoffs",
        ],
        "success_criteria": [
            "A recruiter can understand the project in under 60 seconds",
            "The demo works from documented steps",
            "The resume bullet cites a public artifact",
        ],
        "readme_template": [
            "# Project",
            "## Problem",
            "## Architecture",
            "## How to run",
            "## Evaluation",
            "## Recruiter proof",
        ],
    }


def generate_skill_receipt(request: SkillReceiptRequest) -> dict[str, Any]:
    proof_points = 0
    proof_points += 25 if request.github_url else 0
    proof_points += 25 if request.deployment_url else 0
    proof_points += min(25, request.commit_count * 2)
    proof_points += 15 if request.checks_passed else 0
    proof_points += round(request.code_quality_score * 0.10)
    verification_score = max(0, min(100, proof_points))
    if verification_score >= 80:
        level = "verified"
    elif verification_score >= 50:
        level = "partial"
    else:
        level = "needs_more_proof"
    skills = request.skills or ["Project Delivery"]
    return {
        "id": f"receipt_{uuid4().hex[:10]}",
        "project_title": request.project_title,
        "skills": skills,
        "github_url": str(request.github_url) if request.github_url else None,
        "deployment_url": str(request.deployment_url) if request.deployment_url else None,
        "verification_score": verification_score,
        "verification_level": level,
        "proof_signals": {
            "commit_count": request.commit_count,
            "checks_passed": request.checks_passed,
            "code_quality_score": request.code_quality_score,
        },
        "resume_bullets": [
            f"Built {request.project_title} demonstrating {', '.join(skills[:3])} with verifiable public artifacts.",
            f"Shipped a recruiter-reviewable project with {request.commit_count} commits and a {request.code_quality_score}/100 quality score.",
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def render_trust_profile(request: TrustProfileRequest) -> dict[str, Any]:
    receipt_scores = [
        int(receipt.get("verification_score", 0))
        for receipt in request.skill_receipts
        if isinstance(receipt, dict)
    ]
    project_score = min(35, sum(score >= 50 for score in receipt_scores) * 10 + (sum(receipt_scores) / max(1, len(receipt_scores))) * 0.12)
    learning_score = min(20, request.learning_weeks_completed * 2)
    applications = request.applications
    response_count = sum(1 for app in applications if app.get("status") in {"phone_screen", "onsite", "offer"})
    application_score = min(15, response_count * 5)
    review_score = min(15, len(request.peer_reviews) * 3)
    skill_score = min(15, len(request.verified_skills) * 1.5)
    trust_score = round(project_score + learning_score + application_score + review_score + skill_score)
    trust_score = max(0, min(100, trust_score))
    return {
        "username": request.username,
        "public_url": f"/u/{request.username}",
        "name": request.name,
        "target_role": request.target_role,
        "trust_score": trust_score,
        "trust_label": "high-signal" if trust_score >= 75 else "building-proof" if trust_score >= 45 else "early-stage",
        "verified_skills": request.verified_skills,
        "projects": request.skill_receipts,
        "learning_trajectory": {
            "weeks_completed": request.learning_weeks_completed,
            "status": "consistent" if request.learning_weeks_completed >= 6 else "starting",
        },
        "application_stats": summarize_applications(applications),
        "public_fields": request.public_fields,
        "generated_without_supabase": True,
    }


def log_application(request: ApplicationLogRequest) -> dict[str, Any]:
    record = request.model_dump()
    record["id"] = f"app_{uuid4().hex[:10]}"
    record["created_at"] = datetime.now(timezone.utc).isoformat()
    APPLICATION_STORE.append(record)
    return record


def summarize_applications(applications: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(applications)
    if total == 0:
        return {"total": 0, "callback_rate": 0, "offer_rate": 0, "status_counts": {}}
    # Records from the DB use `application_status`; the in-memory/log path uses
    # `status`. Reading only `status` silently counted every row as "applied",
    # pinning callback_rate at 0 no matter what the user logged.
    status_counts = Counter(
        str(app.get("application_status") or app.get("status") or "applied")
        for app in applications
    )
    callbacks = sum(status_counts.get(status, 0) for status in ["phone_screen", "onsite", "offer"])
    return {
        "total": total,
        "callback_rate": round(callbacks / total, 3),
        "offer_rate": round(status_counts.get("offer", 0) / total, 3),
        "status_counts": dict(status_counts),
    }


def application_recommendations(request: ApplicationRecommendationRequest) -> dict[str, Any]:
    apps = [app.model_dump() for app in request.applications] or APPLICATION_STORE
    summary = summarize_applications(apps)
    recommendations = []
    if summary["total"] < 5:
        recommendations.append("Log at least 5 applications before trusting trend analysis.")
    cover_letter_apps = [app for app in apps if app.get("included_cover_letter")]
    cover_callbacks = summarize_applications(cover_letter_apps)["callback_rate"] if cover_letter_apps else 0
    all_callbacks = summary["callback_rate"]
    if cover_letter_apps and cover_callbacks >= all_callbacks:
        recommendations.append("Cover-letter applications are performing at or above your baseline; keep using targeted letters.")
    if any(app.get("portfolio_project_count", 0) < 2 for app in apps):
        recommendations.append("Attach at least 2 verified portfolio projects to applications for stronger proof.")
    if not recommendations:
        recommendations.append("Your loop has enough proof signals; focus on higher-quality role targeting.")
    return {
        "summary": summary,
        "k_anonymity_note": "Cohort benchmarks are hidden until at least 10 comparable applications exist.",
        "recommendations": recommendations,
    }


def _profile_similarity(left: CohortProfile, right: CohortProfile) -> float:
    left_skills = {skill.lower() for skill in left.skills}
    right_skills = {skill.lower() for skill in right.skills}
    overlap = len(left_skills & right_skills) / max(1, len(left_skills | right_skills))
    role_bonus = 0.30 if left.target_role.lower() == right.target_role.lower() else 0.0
    timezone_bonus = 0.15 if left.timezone.lower() == right.timezone.lower() else 0.0
    level_bonus = 0.15 if left.level == right.level else 0.0
    return min(1.0, overlap * 0.40 + role_bonus + timezone_bonus + level_bonus)


def match_cohort(request: CohortMatchRequest) -> dict[str, Any]:
    ranked = sorted(
        (
            {
                "profile": candidate.model_dump(),
                "match_score": round(_profile_similarity(request.target_profile, candidate), 3),
            }
            for candidate in request.candidates
            if candidate.username != request.target_profile.username
        ),
        key=lambda row: row["match_score"],
        reverse=True,
    )
    selected = ranked[: max(1, request.cohort_size - 1)]
    cohort = [request.target_profile.model_dump()] + [row["profile"] for row in selected]
    return {
        "cohort_id": f"cohort_{uuid4().hex[:10]}",
        "size": len(cohort),
        "target_profile": request.target_profile.model_dump(),
        "members": cohort,
        "matches": selected,
        "weekly_accountability_template": [
            "What did you ship this week?",
            "Which application or interview did it support?",
            "What proof artifact can peers review?",
        ],
        "mock_interview_plan": {
            "format": "async-first",
            "live_video_provider": "deferred",
            "feedback_sections": ["technical depth", "communication", "project evidence", "next practice target"],
        },
    }


async def check_api_keys() -> dict[str, Any]:
    from .tools.reducto_parser import check_reducto

    checks = {
        "tavily": await _check_tavily(),
        "exa": await _check_exa(),
        "deepseek": await _check_deepseek(),
        "openai": await _check_openai(),
        "voyage": await _check_voyage(),
        "reducto": await check_reducto(),
    }
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "cheap_model_policy": {
            "chat_primary": os.getenv("AGENTCEPTION_CHAT_MODEL", "deepseek-chat"),
            "openai_fallback": os.getenv("AGENTCEPTION_OPENAI_FALLBACK_MODEL", "gpt-4o-mini"),
            "embedding": os.getenv("AGENTCEPTION_EMBEDDING_MODEL", "voyage-3-lite"),
        },
        "checks": checks,
    }


async def _check_tavily() -> dict[str, Any]:
    key = _clean_key("TAVILY_API_KEY")
    if not key:
        return _missing("TAVILY_API_KEY")
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=True) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": "Agentception API key health check", "search_depth": "basic", "max_results": 1},
            )
        return _http_status(response)
    except Exception as exc:
        return _error(exc)


async def _check_exa() -> dict[str, Any]:
    key = _clean_key("EXA_API_KEY")
    if not key:
        return _missing("EXA_API_KEY")
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=True) as client:
            response = await client.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": key, "Content-Type": "application/json"},
                json={"query": "Agentception API key health check", "type": "keyword", "numResults": 1},
            )
        return _http_status(response)
    except Exception as exc:
        return _error(exc)


async def _check_deepseek() -> dict[str, Any]:
    key = _clean_key("DEEPSEEK_API_KEY")
    if not key:
        return _missing("DEEPSEEK_API_KEY")
    try:
        async with httpx.AsyncClient(timeout=25, trust_env=True) as client:
            response = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": os.getenv("AGENTCEPTION_CHAT_MODEL", "deepseek-chat"),
                    "messages": [{"role": "user", "content": "Reply with ok."}],
                    "max_tokens": 3,
                    "temperature": 0,
                },
            )
        return _http_status(response)
    except Exception as exc:
        return _error(exc)


async def _check_openai() -> dict[str, Any]:
    key = _clean_key("OPENAI_API_KEY")
    if not key:
        return _missing("OPENAI_API_KEY")
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=True) as client:
            response = await client.get(
                "https://api.openai.com/v1/models/gpt-4o-mini",
                headers={"Authorization": f"Bearer {key}"},
            )
        return _http_status(response)
    except Exception as exc:
        return _error(exc)


async def _check_voyage() -> dict[str, Any]:
    key = _clean_key("VOYAGE_API_KEY")
    if not key:
        return _missing("VOYAGE_API_KEY")
    try:
        async with httpx.AsyncClient(timeout=25, trust_env=True) as client:
            response = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": os.getenv("AGENTCEPTION_EMBEDDING_MODEL", "voyage-3-lite"), "input": ["health check"]},
            )
        return _http_status(response)
    except Exception as exc:
        return _error(exc)


def _clean_key(name: str) -> Optional[str]:
    value = os.getenv(name)
    if not value:
        return None
    value = value.strip().strip('"').strip("'")
    return value or None


def _missing(name: str) -> dict[str, Any]:
    return {"configured": False, "ok": False, "status": "missing", "env": name}


def _error(exc: Exception) -> dict[str, Any]:
    return {"configured": True, "ok": False, "status": "error", "error": str(exc)[:240]}


def _http_status(response: httpx.Response) -> dict[str, Any]:
    if response.status_code < 400:
        return {"configured": True, "ok": True, "status": "ok", "status_code": response.status_code}
    detail = response.text[:240]
    return {
        "configured": True,
        "ok": False,
        "status": "invalid_or_unavailable",
        "status_code": response.status_code,
        "error": detail,
    }


def score_to_percent(value: float) -> int:
    return max(0, min(100, math.floor(value * 100)))
