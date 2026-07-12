"""The golden set must exist.

Every other eval uses `skipif` when its inputs are missing — which is right for a
laptop with a half-built golden set, and dangerous in CI, where a missing file
would turn the entire quality gate into a green skip. This test has no skip: if the
golden set isn't there, the build fails loudly and says which piece is missing.
"""

from __future__ import annotations

import json

import pytest

from evals.metrics import GOLDEN, JDS, load_jd_labels, load_match_pairs

MIN_JDS = 40
MIN_PAIRS = 25   # below this, AUROC can't be distinguished from chance

pytestmark = pytest.mark.eval


def test_golden_jds_present():
    labels = load_jd_labels()
    assert len(labels) >= MIN_JDS, (
        f"only {len(labels)} labelled JDs (need >= {MIN_JDS}). "
        f"Run: python scripts/build_golden_jds.py && python scripts/label_golden_jds.py"
    )
    missing = [r["id"] for r in labels if not (JDS / f"{r['id']}.txt").exists()]
    assert not missing, f"labelled JDs with no text file: {missing[:5]}"


def test_match_pairs_present_and_balanced():
    pairs = load_match_pairs()
    assert len(pairs) >= MIN_PAIRS, (
        f"only {len(pairs)} match pairs (need >= {MIN_PAIRS} for a meaningful AUROC). "
        f"Run: python scripts/build_match_pairs.py"
    )
    positives = sum(p["fit"] for p in pairs)
    negatives = len(pairs) - positives
    assert positives >= 8 and negatives >= 8, (
        f"unbalanced: {positives} positive / {negatives} negative"
    )


def test_embedding_cache_present():
    cache = GOLDEN / "embeddings.json"
    assert cache.exists(), (
        "embedding cache missing — the match eval would silently degrade to "
        "keyword-only. Run: python scripts/build_eval_embeddings.py"
    )


def test_production_resume_snapshot_present():
    """The resume PDFs themselves are private and never committed (see evals/pii.py).
    What CI replays is this snapshot, so this is the thing that must exist — asserting
    on the PDF folder instead would fail every clone that isn't the author's laptop."""
    snapshot = GOLDEN / "resume_parses.json"
    assert snapshot.exists(), (
        "production resume parses missing. Run: python scripts/build_resume_golden.py"
    )
    parses = json.loads(snapshot.read_text(encoding="utf-8"))
    assert len(parses) >= 5, f"only {len(parses)} resume templates snapshotted"


def test_resume_text_fixture_present():
    """The match eval scores against this. It used to read a PDF behind a skipif, so
    in CI the headline AUROC would have skipped and left the build green."""
    fixture = GOLDEN / "resume_text.txt"
    assert fixture.exists(), (
        "resume_text.txt missing — the match eval would skip and CI would pass with no "
        "AUROC at all. Run: python scripts/build_resume_text_fixture.py"
    )
    assert len(fixture.read_text(encoding="utf-8")) > 1000, "resume fixture is suspiciously short"
