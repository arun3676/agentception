from fastapi.testclient import TestClient

from server.agentception2 import (
    ApplicationLogRequest,
    ApplicationRecommendationRequest,
    CareerReverseEngineerRequest,
    CohortMatchRequest,
    CohortProfile,
    ProjectBriefRequest,
    SkillReceiptRequest,
    TrustProfileRequest,
    application_recommendations,
    generate_project_brief,
    generate_skill_receipt,
    match_cohort,
    render_trust_profile,
    reverse_engineer_career,
)
from server.app import app


def test_career_reverse_engineer_builds_skill_graph_and_roadmap():
    result = reverse_engineer_career(
        CareerReverseEngineerRequest(
            target_role="AI Engineer",
            city="San Francisco",
            current_skills=["Python"],
            job_descriptions=[
                "AI Engineer role using RAG, FastAPI, vector databases, embeddings, evaluation, and observability."
            ],
        )
    )

    assert result["source_summary"]["generated_without_supabase"] is True
    assert "Rag" in result["skill_graph"]["hard_skills"]
    assert len(result["roadmap"]) == 12
    assert result["roadmap"][0]["success_criteria"]


def test_portfolio_receipt_scores_public_artifacts():
    brief = generate_project_brief(
        ProjectBriefRequest(target_role="AI Engineer", skills=["RAG", "FastAPI"], week=2)
    )
    receipt = generate_skill_receipt(
        SkillReceiptRequest(
            project_title=brief["title"],
            skills=brief["tech_stack"],
            github_url="https://github.com/example/rag-proof",
            deployment_url="https://rag-proof.example.com",
            commit_count=10,
            checks_passed=True,
            code_quality_score=88,
        )
    )

    assert receipt["verification_level"] == "verified"
    assert receipt["verification_score"] >= 80
    assert receipt["resume_bullets"]


def test_trust_profile_uses_receipts_learning_and_applications():
    receipt = generate_skill_receipt(
        SkillReceiptRequest(
            project_title="RAG proof",
            skills=["RAG"],
            github_url="https://github.com/example/rag-proof",
            deployment_url="https://rag-proof.example.com",
            commit_count=8,
            checks_passed=True,
            code_quality_score=80,
        )
    )
    profile = render_trust_profile(
        TrustProfileRequest(
            username="arun-2026",
            name="Arun",
            target_role="AI Engineer",
            verified_skills=["RAG", "FastAPI"],
            skill_receipts=[receipt],
            learning_weeks_completed=6,
            applications=[{"status": "phone_screen"}],
            peer_reviews=[{"rating": 5}],
        )
    )

    assert profile["public_url"] == "/u/arun-2026"
    assert profile["trust_score"] > 40
    assert profile["generated_without_supabase"] is True


def test_application_recommendations_and_cohort_matching():
    recommendations = application_recommendations(
        ApplicationRecommendationRequest(
            applications=[
                ApplicationLogRequest(
                    company="OpenAI",
                    role="AI Engineer",
                    status="phone_screen",
                    included_cover_letter=True,
                    portfolio_project_count=2,
                ),
                ApplicationLogRequest(
                    company="Scale AI",
                    role="ML Engineer",
                    status="applied",
                    portfolio_project_count=1,
                ),
            ]
        )
    )
    assert recommendations["summary"]["total"] == 2
    assert recommendations["recommendations"]

    cohort = match_cohort(
        CohortMatchRequest(
            target_profile=CohortProfile(
                username="arun",
                target_role="AI Engineer",
                timezone="America/Los_Angeles",
                skills=["RAG", "FastAPI"],
                level="intermediate",
            ),
            candidates=[
                CohortProfile(
                    username="maya",
                    target_role="AI Engineer",
                    timezone="America/Los_Angeles",
                    skills=["RAG"],
                    level="intermediate",
                )
            ],
        )
    )
    assert cohort["size"] == 2
    assert cohort["matches"][0]["match_score"] > 0.5


def test_agentception2_api_contracts():
    client = TestClient(app)

    career = client.post(
        "/api/v2/career/reverse-engineer",
        json={
            "target_role": "AI Engineer",
            "current_skills": ["Python"],
            "job_descriptions": ["RAG FastAPI vector databases"],
        },
    )
    assert career.status_code == 200
    assert len(career.json()["roadmap"]) == 12

    receipt = client.post(
        "/api/v2/portfolio/skill-receipt",
        json={
            "project_title": "RAG proof",
            "skills": ["RAG", "FastAPI"],
            "github_url": "https://github.com/example/rag-proof",
            "deployment_url": "https://rag-proof.example.com",
            "commit_count": 12,
            "checks_passed": True,
            "code_quality_score": 90,
        },
    )
    assert receipt.status_code == 200
    assert receipt.json()["verification_score"] >= 80
