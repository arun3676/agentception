"""Contract checks for the committed, fully synthetic resume fixture.

These tests protect the offline parser fixture from schema drift and accidental PII.
They are not presented as a population-level parser accuracy measurement.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.pii import (
    SYNTHETIC_EMAIL,
    SYNTHETIC_NAME,
    assert_synthetic_fixture_text,
)
from evals.synthetic_resume import SYNTHETIC_FILENAME, render_resume_text
from server.tools.resume_ingest import structured_profile

SNAPSHOT = Path(__file__).resolve().parent / "golden" / "resume_parses.json"
STRUCTURED_PARSES: dict[str, dict] = (
    json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
)

EXPECTED_EMPLOYERS = {"northstar example labs", "sample analytics cooperative"}
EXPECTED_SKILLS = {"python", "sql"}

pytestmark = pytest.mark.eval


def _score(parsed: dict) -> dict[str, bool]:
    contact = parsed.get("contact", {})
    experience_blob = " ".join(
        f"{entry.get('company', '')} {entry.get('title', '')}"
        for entry in parsed.get("experience", [])
    ).lower()
    skills_blob = " ".join(
        skill
        for bucket in parsed.get("skills", {}).values()
        for skill in bucket
    ).lower()

    return {
        "name": contact.get("name", "").strip() == SYNTHETIC_NAME,
        "email": contact.get("email", "").strip().lower() == SYNTHETIC_EMAIL,
        "employers": all(employer in experience_blob for employer in EXPECTED_EMPLOYERS),
        "skills": all(skill in skills_blob for skill in EXPECTED_SKILLS),
    }


@pytest.mark.skipif(not STRUCTURED_PARSES, reason="refresh synthetic resume goldens")
def test_structured_snapshot_contract():
    assert set(STRUCTURED_PARSES) == {SYNTHETIC_FILENAME}
    failures = [
        field
        for parsed in STRUCTURED_PARSES.values()
        for field, valid in _score(parsed).items()
        if not valid
    ]
    assert not failures, f"synthetic structured fixture contract failed: {failures}"


def test_all_committed_resume_fixtures_are_visibly_synthetic():
    assert_synthetic_fixture_text(render_resume_text())
    assert_synthetic_fixture_text(
        json.dumps(STRUCTURED_PARSES, ensure_ascii=False)
    )


def test_local_parser_recognizes_synthetic_identity():
    parsed = structured_profile(render_resume_text()) or {}
    assert parsed.get("contact", {}).get("name") == SYNTHETIC_NAME
    assert parsed.get("contact", {}).get("email") == SYNTHETIC_EMAIL
