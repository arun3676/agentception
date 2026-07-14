"""Regressions for the two job-search bugs.

1. Anonymous discovery requires an explicit role; resume inference is private.
2. /results returned the artifacts wrapper (no top-level `companies`), so the UI
   rendered an empty results list even though the search succeeded.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from server.app import app, memory, RagBody
from server.agents.rag_companies import get_rag_results


def test_ragbody_requires_an_explicit_role():
    body = RagBody(city="San Francisco, CA", role="AI Engineer")
    assert body.role == "AI Engineer"
    assert body.city == "San Francisco, CA"

    with pytest.raises(Exception):
        RagBody(city="San Francisco, CA")


def _seed_ragdoc(run_id: str, companies):
    memory.set(f"ragdoc:{run_id}", {
        "run_id": run_id,
        "role": "AI Engineer",
        "location": "San Francisco, CA",
        "depth": "standard",
        "companies": companies,
        "total": len(companies),
        "pagination": {},
    })


def _company(name: str, score: float, salary=None):
    return {
        "company_name": name,
        "homepage_url": f"https://{name.lower()}.com",
        "job_title": "AI Engineer",
        "job_url": f"https://jobs.lever.co/{name.lower()}/1",
        "job_location": "San Francisco, CA",
        "score": score,
        "salary": salary,
    }


def test_get_rag_results_paginates_without_reordering_provider_results():
    run_id = "test-run-pagination"
    _seed_ragdoc(run_id, [
        _company("Acme", 0.5),
        _company("Beta", 0.9),
        _company("Gamma", 0.7),
    ])

    page = asyncio.run(get_rag_results(run_id, offset=0, limit=2, memory_store=memory))
    names = [c.company_name for c in page.companies]
    # Source/provider order is preserved; undisclosed score fields do not rank it.
    assert names == ["Acme", "Beta"]
    assert page.total == 3


def test_results_endpoint_returns_companies_and_city():
    run_id = "test-run-endpoint"
    _seed_ragdoc(run_id, [_company("Weave", 0.8, salary="$150K – $200K")])

    client = TestClient(app)
    resp = client.get(f"/results/{run_id}", params={"offset": 0, "limit": 5})
    assert resp.status_code == 200

    data = resp.json()
    # The frontend reads these exact top-level keys.
    assert data["city"] == "San Francisco, CA"
    assert data["role"] == "AI Engineer"
    assert len(data["companies"]) == 1
    assert data["companies"][0]["company_name"] == "Weave"
    assert data["companies"][0]["salary"] == "$150K – $200K"
    assert data["pagination"]["total"] == 1
    assert data["pagination"]["has_more"] is False


def test_results_endpoint_never_exposes_retired_personal_or_score_fields():
    run_id = "test-run-public-fields"
    company = _company("PublicOnly", 0.8)
    company.update(
        {
            "resume_match_score": 99,
            "missing_skills": ["private-gap"],
            "trust_score": 100,
            "trust_label": "verified",
            "trust_reasons": ["unsupported"],
            "match_band": "top",
            "match_probability": 0.99,
            "match_explanation": "private comparison",
            "is_expired": False,
            "days_old": 1,
            "posted_at": "2026-01-01",
            "display_data": {
                "title": "AI Engineer",
                "score": 0.98,
                "resume_excerpt": "private resume content",
                "email": "jordan.lee@example.com",
            },
            "job_posting": {
                "url": "https://jobs.lever.co/publiconly/1",
                "title": "AI Engineer",
                "snippet": "Source listing excerpt",
                "score": 0.98,
                "trust_score": 100,
                "trust_label": "verified",
                "trust_reasons": ["unsupported"],
                "posted_at": "2026-01-01",
                "is_expired": False,
                "days_old": 1,
            },
        }
    )
    _seed_ragdoc(run_id, [company])

    response = TestClient(app).get(f"/results/{run_id}")

    assert response.status_code == 200
    result = response.json()["companies"][0]
    forbidden = {
        "resume_match_score",
        "missing_skills",
        "trust_score",
        "trust_label",
        "trust_reasons",
        "match_band",
        "match_probability",
        "match_explanation",
        "is_expired",
        "days_old",
        "posted_at",
        "score",
        "rank_score",
        "user_id",
        "email",
        "phone",
        "contact_info",
        "resume_text",
        "resume_token",
        "resume_insights",
        "resume_excerpt",
    }
    assert forbidden.isdisjoint(result)
    assert forbidden.isdisjoint(result["job_posting"])
    if "display_data" in result:
        assert forbidden.isdisjoint(result["display_data"])


def test_results_endpoint_404_for_unknown_run():
    client = TestClient(app)
    assert client.get("/results/does-not-exist").status_code == 404
