"""Taxonomy-backed skill extraction."""

import pytest

from server.tools.skill_extractor import canonicalise, extract_skills, taxonomy_size


def test_taxonomy_is_loaded():
    # The keyword list this replaced had 77 entries and capped recall at 0.365.
    assert taxonomy_size() > 300


class TestExtractSkills:
    def test_finds_core_technologies(self):
        jd = "You will build services in Python and Go, deploy on Kubernetes, and use PostgreSQL."
        found = {s.lower() for s in extract_skills(jd)}
        assert {"python", "kubernetes", "postgresql"} <= found

    def test_finds_modern_ai_stack(self):
        jd = "Experience with RAG, LLM evaluation, PyTorch and vector databases required."
        found = {s.lower() for s in extract_skills(jd)}
        assert "rag" in found
        assert "pytorch" in found

    def test_canonicalises_aliases(self):
        found = {s.lower() for s in extract_skills("We run k8s and postgres in prod.")}
        assert "kubernetes" in found
        assert "postgresql" in found
        assert "k8s" not in found  # collapsed onto the canonical name

    def test_prefers_the_longest_match(self):
        found = extract_skills("Our pipelines run on Apache Airflow.")
        assert any("airflow" in s.lower() for s in found)

    @pytest.mark.parametrize(
        "sentence",
        [
            "The rest of the team works remotely.",     # 'rest' != REST
            "We want you to go to production quickly.",  # 'go' != Go
        ],
    )
    def test_common_english_words_are_not_skills(self, sentence):
        found = {s.lower() for s in extract_skills(sentence)}
        assert "rest" not in found
        assert "go" not in found

    def test_rest_api_still_matches_in_a_tech_context(self):
        found = {s.lower() for s in extract_skills("Build REST APIs, GraphQL endpoints, and gRPC services.")}
        assert "rest api" in found or "rest" in found

    def test_never_returns_job_ad_boilerplate(self):
        jd = "Full time. $180K - $250K. Offers Equity. Location: San Francisco. Great benefits."
        found = {s.lower() for s in extract_skills(jd)}
        assert not found & {"equity", "offers", "location", "benefits", "full time"}

    def test_empty_input(self):
        assert extract_skills("") == []


class TestCanonicalise:
    def test_maps_known_aliases(self):
        assert canonicalise(["k8s", "postgres"]) == ["Kubernetes", "PostgreSQL"]

    def test_passes_through_unknown_skills(self):
        assert canonicalise(["Fictional Framework"]) == ["Fictional Framework"]

    def test_dedupes(self):
        assert canonicalise(["k8s", "Kubernetes"]) == ["Kubernetes"]
