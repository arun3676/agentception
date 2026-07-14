"""Regressions for the matching / gap-analysis quality bugs.

Found by running the product end-to-end: matching ran against a ~40-char search
snippet, so scores collapsed to the 0-match floor and "missing skills" came back
as words like "equity", "offers" and "employment" — which then fed the study
drawer. These pin the corrected behaviour.
"""

from server.tools.resume_job_matcher import analyze_gaps, extract_jd_skills
from server.tools.resume_store import _display_skill

JD = """
Senior AI Engineer — San Francisco, CA. Full time. $180K – $250K. Offers Equity.

You will build retrieval-augmented generation systems in Python. We use PyTorch,
Kubernetes and Redis in production, and you'll own our vector database and NLP
evaluation pipeline. Experience with Go is a plus.
"""

RESUME_INSIGHTS = {"skills_flat": ["Python", "PyTorch"], "tech_stack": ["Python"]}


class TestExtractJdSkills:
    def test_finds_real_skills(self):
        skills = {s.lower() for s in extract_jd_skills(JD)}
        assert "python" in skills
        assert "kubernetes" in skills
        assert "redis" in skills

    def test_never_returns_job_ad_boilerplate(self):
        # The old implementation returned every unseen token in the posting.
        junk = {"equity", "offers", "employment", "location", "type", "full", "time"}
        assert not junk & {s.lower() for s in extract_jd_skills(JD)}


class TestAnalyzeGaps:
    def test_missing_skills_are_skills_the_resume_lacks(self):
        missing = {s.lower() for s in analyze_gaps(JD, RESUME_INSIGHTS)["missing_skills"]}
        assert "kubernetes" in missing
        assert "redis" in missing

    def test_skills_on_the_resume_are_not_reported_missing(self):
        missing = {s.lower() for s in analyze_gaps(JD, RESUME_INSIGHTS)["missing_skills"]}
        assert "python" not in missing
        assert "pytorch" not in missing

    def test_no_boilerplate_leaks_into_gaps(self):
        missing = {s.lower() for s in analyze_gaps(JD, RESUME_INSIGHTS)["missing_skills"]}
        assert "equity" not in missing
        assert "offers" not in missing


class TestSkillDisplayNames:
    def test_acronyms_are_not_title_cased(self):
        # "Nlp" / "Rag" / "Aws" on a skill chip looks broken
        assert _display_skill("nlp") == "NLP"
        assert _display_skill("rag") == "RAG"
        assert _display_skill("aws") == "AWS"
        assert _display_skill("postgresql") == "PostgreSQL"

    def test_unknown_words_still_title_case(self):
        assert _display_skill("docker") == "Docker"
