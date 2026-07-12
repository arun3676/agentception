"""Pure helpers behind /api/v1/study — pillar routing, bucketing, video IDs."""

import pytest

from server.routers.study import (
    _classify,
    _curated_picks,
    _to_item,
    resolve_pillar,
    youtube_video_id,
)


class TestResolvePillar:
    @pytest.mark.parametrize(
        "topic,expected",
        [
            ("vector databases", "ai_engineer"),
            ("kubernetes operators", "devops_engineer"),
            ("figma design systems", "ui_ux_designer"),
            ("kafka streaming pipelines", "data_engineer"),
            ("owasp penetration testing", "cybersecurity_analyst"),
            ("swiftui navigation", "mobile_developer"),
        ],
    )
    def test_routes_topic_to_its_career_track(self, topic, expected):
        assert resolve_pillar(topic, None)["key"] == expected

    def test_explicit_role_overrides_topic_keywords(self):
        # "docker" is a DevOps keyword, but the caller said they're a data scientist
        assert resolve_pillar("docker", "data_scientist")["key"] == "data_scientist"

    def test_role_label_is_accepted_as_well_as_key(self):
        assert resolve_pillar("anything", "Data Scientist")["key"] == "data_scientist"

    def test_unmatched_topic_falls_back_rather_than_raising(self):
        assert resolve_pillar("underwater basket weaving", None)["key"] in {
            p for p in ("ai_engineer",)
        }


class TestYoutubeVideoId:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=J7SbtOfbyMA", "J7SbtOfbyMA"),
            ("https://youtu.be/Yhv19le0sBw", "Yhv19le0sBw"),
            ("https://www.youtube.com/embed/abc123", "abc123"),
            ("https://www.youtube.com/shorts/xyz789", "xyz789"),
        ],
    )
    def test_extracts_id_from_every_url_shape(self, url, expected):
        assert youtube_video_id(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/@freecodecamp",   # channel, not a lesson
            "https://www.youtube.com/results?search_query=rag",
            "https://example.com/watch?v=nope",
            "not a url",
        ],
    )
    def test_returns_none_for_non_video_urls(self, url):
        assert youtube_video_id(url) is None


class TestClassify:
    def test_course_platforms_bucket_as_courses(self):
        assert _classify("https://www.coursera.org/learn/ml") == "courses"
        assert _classify("https://udemy.com/course/x") == "courses"

    def test_docs_subdomain_convention_is_generalized(self):
        assert _classify("https://docs.langchain.com/oss/python") == "docs"
        assert _classify("https://docs.pydantic.dev/latest/") == "docs"

    def test_known_doc_sites_that_break_the_convention(self):
        assert _classify("https://pytorch.org/docs/stable/") == "docs"
        assert _classify("https://kubernetes.io/docs/home/") == "docs"

    def test_everything_else_is_an_article(self):
        assert _classify("https://machinelearningmastery.com/pgvector/") == "articles"


class TestToItem:
    def test_drops_results_with_no_title_or_url(self):
        assert _to_item({"url": "https://x.com", "title": ""}) is None
        assert _to_item({"url": "", "title": "Something"}) is None

    def test_prefers_highlights_for_the_snippet(self):
        item = _to_item({
            "url": "https://x.com",
            "title": "T",
            "highlights": ["first sentence.", "second."],
            "summary": "ignored",
        })
        assert item["snippet"] == "first sentence. second."

    def test_falls_back_to_summary_then_text(self):
        item = _to_item({"url": "https://x.com", "title": "T", "summary": "sum"})
        assert item["snippet"] == "sum"


class TestCuratedPicks:
    def test_builds_a_pick_for_every_source_kind(self):
        level_data = {
            "youtube": ["Andrej Karpathy"],
            "reading": ["langchain.com"],
            "courses": ["coursera.org"],
        }
        picks = _curated_picks({}, level_data)
        kinds = {p["kind"] for p in picks}
        assert kinds == {"youtube_channel", "site", "course"}

    def test_channel_names_with_spaces_are_url_encoded(self):
        picks = _curated_picks({}, {"youtube": ["Two Minute Papers"]})
        assert "Two+Minute+Papers" in picks[0]["url"]

    def test_missing_source_fields_are_skipped(self):
        assert _curated_picks({}, {}) == []
