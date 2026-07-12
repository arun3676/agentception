"""The Exa request body.

Exa silently ignores top-level `highlights`/`text` booleans and returns results
with no snippets. They must be nested under `contents`. This failure mode is
invisible at runtime, so it is pinned here.
"""

import asyncio

import pytest

from server.tools import exa_search as exa


@pytest.fixture
def captured(monkeypatch):
    """Capture the JSON body exa_search would POST, without hitting the network."""
    sent = {}

    async def fake_post(client, url, headers, json_data, attempt=0):
        sent.update(json_data)
        return {"results": []}

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(exa, "_robust_exa_post", fake_post)
    return sent


def search(**kwargs):
    return asyncio.run(exa.exa_search("q", **kwargs))


def test_highlights_go_inside_a_contents_block(captured):
    search(want_highlights=True)
    assert "highlights" not in captured, "top-level highlights is silently ignored by Exa"
    assert captured["contents"]["highlights"]["numSentences"] > 0


def test_text_goes_inside_a_contents_block(captured):
    search(want_text=True, want_highlights=False)
    assert "text" not in captured
    assert captured["contents"]["text"]["maxCharacters"] > 0


def test_no_contents_block_when_nothing_requested(captured):
    search(want_text=False, want_highlights=False)
    assert "contents" not in captured


def test_domains_and_date_filter_pass_through(captured):
    search(
        include_domains=["jobs.lever.co"],
        exclude_domains=["indeed.com"],
        start_published_date="2026-01-01",
    )
    assert captured["includeDomains"] == ["jobs.lever.co"]
    assert captured["excludeDomains"] == ["indeed.com"]
    assert captured["startPublishedDate"] == "2026-01-01"


def test_category_is_dropped_when_domains_are_set(captured):
    # Exa rejects the combination, so domains win.
    search(category="company", include_domains=["example.com"])
    assert "category" not in captured


def test_category_is_sent_when_no_domains_are_set(captured):
    search(category="company")
    assert captured["category"] == "company"


def test_result_rows_expose_text_and_score(monkeypatch):
    async def fake_post(client, url, headers, json_data, attempt=0):
        return {"results": [{"title": "T", "url": "https://x.com", "text": "body", "score": 0.7}]}

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(exa, "_robust_exa_post", fake_post)

    rows = asyncio.run(exa.exa_search("q"))
    assert rows[0]["text"] == "body"
    assert rows[0]["score"] == 0.7
