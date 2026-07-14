"""Anonymous discovery must never manufacture listing facts."""

import asyncio

import pytest

from server.agents import rag_companies as discovery
from server.memory.state_store import Memory


def test_canonical_job_url_removes_tracking_but_keeps_distinct_postings():
    assert discovery.canonical_job_url(
        "https://jobs.lever.co/acme/job-1/?utm_source=test&team=platform#apply"
    ) == "https://jobs.lever.co/acme/job-1?team=platform"
    assert discovery.canonical_job_url("http://127.0.0.1/private") is None
    assert discovery.canonical_job_url("https://example.com/not-an-ats-job") is None


def test_provider_row_keeps_missing_facts_unavailable():
    result = discovery._to_company(
        {"url": "https://jobs.lever.co/acme/job-1", "title": "Backend Engineer"},
        provider="Tavily",
        observed_at="2026-07-13T00:00:00+00:00",
    )

    assert result is not None
    assert result.company_name == "Acme"
    assert result.job_location is None
    assert result.blurb is None
    assert result.job_title == "Backend Engineer"
    assert result.description_origin == "unavailable"
    assert result.listing_data_quality == "partial"


def test_discovery_deduplicates_only_by_canonical_url_and_uses_exa_second(monkeypatch):
    async def tavily(*_args, **_kwargs):
        return [
            {
                "url": "https://jobs.lever.co/acme/job-1?utm_source=tavily",
                "title": "Backend Engineer at Acme",
                "content": "Provider-supplied listing excerpt.",
            },
            {
                "url": "https://jobs.lever.co/acme/job-2",
                "title": "Platform Engineer at Acme",
                "content": "A different opening at the same employer.",
            },
        ]

    async def exa(*_args, **_kwargs):
        return [
            {
                "url": "https://jobs.lever.co/acme/job-1#duplicate",
                "title": "Backend Engineer at Acme",
                "highlights": ["Duplicate provider row."],
            },
            {
                "url": "https://jobs.ashbyhq.com/beta/job-3",
                "title": "Backend Engineer at Beta",
                "highlights": ["Secondary-provider listing excerpt."],
            },
        ]

    monkeypatch.setattr(discovery, "tavily_search", tavily)
    monkeypatch.setattr(discovery, "exa_search", exa)

    results = asyncio.run(discovery._discover("Backend Engineer", "Austin, TX", limit=5))

    assert [item.job_url for item in results] == [
        "https://jobs.lever.co/acme/job-1",
        "https://jobs.lever.co/acme/job-2",
        "https://jobs.ashbyhq.com/beta/job-3",
    ]
    assert [item.job_source for item in results] == ["Tavily", "Tavily", "Exa"]
    assert len([item for item in results if item.company_name == "Acme"]) == 2


def test_transport_failures_do_not_become_successful_empty_results(monkeypatch):
    async def unavailable(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(discovery, "tavily_search", unavailable)
    monkeypatch.setattr(discovery, "exa_search", unavailable)

    with pytest.raises(discovery.ProviderUnavailable):
        asyncio.run(discovery._discover("Backend Engineer", "Austin, TX", limit=5))


def test_run_persists_only_public_listing_data(monkeypatch):
    async def fake_discover(*_args, **_kwargs):
        return [
            discovery._to_company(
                {
                    "url": "https://jobs.lever.co/acme/job-1",
                    "title": "Backend Engineer at Acme",
                    "content": "Provider excerpt.",
                },
                provider="Tavily",
                observed_at="2026-07-13T00:00:00+00:00",
            )
        ]

    monkeypatch.setattr(discovery, "_discover", fake_discover)
    memory = Memory()
    events = []

    async def emit(event):
        events.append(event)

    response = asyncio.run(
        discovery.run_rag_company_search(
            run_id="synthetic-run",
            city="Austin, TX",
            role="Backend Engineer",
            resume_token=None,
            emit=emit,
            memory_store=memory,
        )
    )

    assert response["companies"][0]["job_url"] == "https://jobs.lever.co/acme/job-1"
    stored = memory.get("ragdoc:synthetic-run")
    assert "resume_insights" not in stored
    assert [event.stage for event in events] == ["discovery", "normalization"]
