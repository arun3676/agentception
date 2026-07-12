"""Resume parsing accuracy on the 14 real PDFs in resume/.

Two parsers are measured, because the product has two:

* **production** — Reducto (layout-aware). It's a paid network call, so its output
  is snapshotted into the golden set and replayed offline, exactly like the
  embedding cache. This is the number that reflects what users get.
* **fallback** — the local PyMuPDF + regex path, used when Reducto is unavailable.
  Reported, not gated, because it is measurably worse and pretending otherwise
  would hide a known limitation.

Scope, stated plainly: every PDF is the *same person's* resume in a different
layout, so this measures **layout robustness**, not generalisation across people.
Effective n is the number of distinct templates. Fixing that needs other people's
resumes, which we don't have and won't fabricate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.pii import PSEUDONYM_EMAIL, redact_contact
from server.tools.resume_ingest import extract_pdf_text_locally, structured_profile

RESUME_DIR = Path(__file__).resolve().parents[2] / "resume"
SNAPSHOT = Path(__file__).resolve().parent / "golden" / "resume_parses.json"

PDFS = sorted(RESUME_DIR.glob("*.pdf")) if RESUME_DIR.exists() else []
PRODUCTION_PARSES: dict[str, dict] = (
    json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
)

# Ground truth: the actual values. The first version of this test asserted
# `"@" in email`, which passes for any string containing an at-sign.
#
# The email is the pseudonym, not the real inbox: `redact_contact` is applied to the
# snapshot when it is built and to the live fallback parse below, so both sides of
# every comparison are transformed identically and the accuracy is the same number it
# would be on raw data. The parser still has to locate the address in the layout and
# extract it whole — it just reports a stand-in when it succeeds. See evals/pii.py.
EXPECTED_NAME = "arun kumar chukkala"
EXPECTED_EMAIL = PSEUDONYM_EMAIL
EXPECTED_EMPLOYERS = {"jefferies", "experian"}
EXPECTED_SKILLS = {"python", "sql"}

MIN_PRODUCTION_ACCURACY = 0.90

pytestmark = pytest.mark.eval


def _score(parsed: dict) -> dict[str, bool]:
    contact = parsed.get("contact", {})
    experience_blob = " ".join(
        f"{e.get('company', '')} {e.get('title', '')}" for e in parsed.get("experience", [])
    ).lower()
    skills_blob = " ".join(
        s for bucket in parsed.get("skills", {}).values() for s in bucket
    ).lower()

    return {
        "name": contact.get("name", "").strip().lower() == EXPECTED_NAME,
        "email": contact.get("email", "").strip().lower() == EXPECTED_EMAIL,
        "employer": any(e in experience_blob for e in EXPECTED_EMPLOYERS),
        "skills": all(s in skills_blob for s in EXPECTED_SKILLS),
    }


def _report(name: str, results: dict[str, dict[str, bool]], capsys) -> float:
    by_field: dict[str, list[bool]] = {}
    for fields in results.values():
        for field, ok in fields.items():
            by_field.setdefault(field, []).append(ok)

    checks = [ok for fields in results.values() for ok in fields.values()]
    accuracy = sum(checks) / len(checks) if checks else 0.0

    with capsys.disabled():
        print(f"\n  {name} ({len(results)} templates, one person)")
        for field, oks in by_field.items():
            print(f"    {field:<9} {sum(oks)}/{len(oks)}")
        print(f"  field accuracy: {accuracy:.3f}")

    return accuracy


@pytest.mark.skipif(not PRODUCTION_PARSES, reason="run scripts/build_resume_golden.py")
def test_production_parser_accuracy(record_property, capsys):
    """Reducto — the parser users actually hit. Replayed from the snapshot."""
    results = {name: _score(parsed) for name, parsed in PRODUCTION_PARSES.items()}
    accuracy = _report("production parser (Reducto, replayed)", results, capsys)

    failures = [
        f"{n}:{f}" for n, fields in results.items() for f, ok in fields.items() if not ok
    ]
    record_property("resume_field_accuracy", round(accuracy, 4))

    assert accuracy >= MIN_PRODUCTION_ACCURACY, (
        f"production parse accuracy {accuracy:.3f} below {MIN_PRODUCTION_ACCURACY}: {failures[:6]}"
    )


@pytest.mark.skipif(not PDFS, reason="no resume PDFs available")
def test_fallback_parser_accuracy_is_reported(record_property, capsys):
    """The local regex parser. Measured and published, deliberately NOT gated:
    it is known to be worse (it loses employer names entirely), and the honest move
    is to publish that gap rather than assert a floor it would fail."""
    results = {
        pdf.name: _score(
            redact_contact(structured_profile(extract_pdf_text_locally(pdf.read_bytes())) or {})
        )
        for pdf in PDFS
    }
    accuracy = _report("fallback parser (local regex)", results, capsys)
    record_property("resume_field_accuracy_fallback", round(accuracy, 4))

    # Only a sanity floor — it must not be completely broken.
    assert accuracy > 0.4, f"fallback parser has collapsed ({accuracy:.3f})"
