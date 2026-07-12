"""Regressions for the two job-search bugs.

1. The UI's "detected from resume" default sends no `role`; requiring it 422'd
   the whole resume-driven flow.
2. /results returned the artifacts wrapper (no top-level `companies`), so the UI
   rendered an empty results list even though the search succeeded.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from server.app import app, memory, RagBody
from server.agents.rag_companies import get_rag_results


def test_ragbody_role_is_optional():
    # The bug: role was required, so the no-role UI request failed validation.
    body = RagBody(city="San Francisco, CA")
    assert body.role is None
    assert body.city == "San Francisco, CA"


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


def test_get_rag_results_paginates_and_sorts():
    run_id = "test-run-pagination"
    _seed_ragdoc(run_id, [
        _company("Acme", 0.5),
        _company("Beta", 0.9),
        _company("Gamma", 0.7),
    ])

    page = asyncio.run(get_rag_results(run_id, offset=0, limit=2, memory_store=memory))
    names = [c.company_name for c in page.companies]
    # sorted by score desc, sliced to 2
    assert names == ["Beta", "Gamma"]
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


def test_results_endpoint_404_for_unknown_run():
    client = TestClient(app)
    assert client.get("/results/does-not-exist").status_code == 404
