from __future__ import annotations

from fastapi import APIRouter

from ..agentception2 import (
    ApplicationRecommendationRequest,
    CareerReverseEngineerRequest,
    CohortMatchRequest,
    ProjectBriefRequest,
    SkillReceiptRequest,
    TrustProfileRequest,
    application_recommendations,
    check_api_keys,
    generate_project_brief,
    generate_skill_receipt,
    match_cohort,
    render_trust_profile,
    reverse_engineer_career,
)

# Thin wrappers over the pure functions in agentception2.py.
# The Cohort / Trust Profile / Portfolio / Career pages these serve are still
# beta and stay out of the main nav, but the endpoints are live and tested.
router = APIRouter(prefix="/api/v2")


@router.get("/system/api-key-health")
async def api_key_health():
    return await check_api_keys()


@router.get("/system/usage")
async def system_usage(days: int = 7):
    """What the AI actually costs, and where it goes.

    Cost per provider, per model and — the useful one — per *purpose*, so
    "what is expensive?" is answerable, not just "how much did we spend?".
    """
    from ..tools.llm_router import usage_summary

    return usage_summary(days)


@router.post("/applications/recommendations")
async def recommend_applications(body: ApplicationRecommendationRequest):
    return application_recommendations(body)


@router.post("/career/reverse-engineer")
async def career_reverse_engineer(body: CareerReverseEngineerRequest):
    return reverse_engineer_career(body)


@router.post("/portfolio/project-brief")
async def project_brief(body: ProjectBriefRequest):
    return generate_project_brief(body)


@router.post("/portfolio/skill-receipt")
async def skill_receipt(body: SkillReceiptRequest):
    return generate_skill_receipt(body)


@router.post("/profile/trust")
async def trust_profile(body: TrustProfileRequest):
    return render_trust_profile(body)


@router.post("/cohort/match")
async def cohort_match(body: CohortMatchRequest):
    return match_cohort(body)
