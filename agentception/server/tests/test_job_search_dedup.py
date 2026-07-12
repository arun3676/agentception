"""Merging Tavily and Exa job hits without showing the same posting twice."""

from server.agents.job_search import ATS_POSTING_DOMAINS, _dedupe_hits_by_url
from server.agents.match import SearchHit


def hit(url: str, title: str = "t") -> SearchHit:
    return SearchHit(url=url, title=title, snippet="", score=1.0)


def test_collapses_trailing_slash_and_www_and_query_variants():
    hits = [
        hit("https://job-boards.greenhouse.io/weave/jobs/4274000009", "keep"),
        hit("https://job-boards.greenhouse.io/weave/jobs/4274000009/", "dup slash"),
        hit("https://www.job-boards.greenhouse.io/weave/jobs/4274000009", "dup www"),
        hit("https://jobs.lever.co/acme/abc?utm=x", "keep"),
        hit("https://jobs.lever.co/acme/abc?utm=y", "dup query"),
    ]
    out = _dedupe_hits_by_url(hits)
    assert [h.title for h in out] == ["keep", "keep"]


def test_keeps_the_first_occurrence():
    out = _dedupe_hits_by_url([hit("https://a.com/x", "first"), hit("https://a.com/x", "second")])
    assert len(out) == 1 and out[0].title == "first"


def test_drops_hits_with_no_url():
    out = _dedupe_hits_by_url([hit(""), hit("https://a.com/x")])
    assert [h.url for h in out] == ["https://a.com/x"]


def test_different_paths_on_the_same_host_are_distinct():
    out = _dedupe_hits_by_url([hit("https://a.com/x"), hit("https://a.com/y")])
    assert len(out) == 2


def test_ats_domains_are_apply_page_subdomains_not_marketing_sites():
    # Bare lever.co / greenhouse.io are marketing pages and pollute a precision search.
    assert "lever.co" not in ATS_POSTING_DOMAINS
    assert "greenhouse.io" not in ATS_POSTING_DOMAINS
    assert "jobs.lever.co" in ATS_POSTING_DOMAINS
    assert "boards.greenhouse.io" in ATS_POSTING_DOMAINS
