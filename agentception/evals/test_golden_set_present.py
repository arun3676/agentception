"""Fail loudly when any required offline evaluation fixture is missing."""

from __future__ import annotations

import json

import pytest

from evals.metrics import GOLDEN, JDS, load_jd_labels, load_match_pairs
from evals.pii import assert_synthetic_fixture_text
from evals.synthetic_resume import SYNTHETIC_FILENAME

MIN_JDS = 40
MIN_PAIRS = 25

pytestmark = pytest.mark.eval


def test_golden_jds_present():
    labels = load_jd_labels()
    assert len(labels) >= MIN_JDS, (
        f"only {len(labels)} labelled JDs (need >= {MIN_JDS}). "
        "Run: python scripts/build_golden_jds.py && python scripts/label_golden_jds.py"
    )
    missing = [record["id"] for record in labels if not (JDS / f'{record["id"]}.txt').exists()]
    assert not missing, f"labelled JDs with no text file: {missing[:5]}"


def test_match_pairs_present_and_balanced():
    pairs = load_match_pairs()
    assert len(pairs) >= MIN_PAIRS, (
        f"only {len(pairs)} match pairs (need >= {MIN_PAIRS} for a meaningful AUROC). "
        "Run: python scripts/build_match_pairs.py"
    )
    positives = sum(pair["fit"] for pair in pairs)
    negatives = len(pairs) - positives
    assert positives >= 8 and negatives >= 8, (
        f"unbalanced: {positives} positive / {negatives} negative"
    )


def test_embedding_cache_present():
    cache = GOLDEN / "embeddings.json"
    assert cache.exists(), (
        "embedding cache missing; the match eval would silently degrade to keyword-only. "
        "Run: python scripts/build_eval_embeddings.py"
    )


def test_synthetic_resume_snapshot_present():
    snapshot = GOLDEN / "resume_parses.json"
    assert snapshot.exists(), (
        "synthetic resume parse missing. Run: "
        "python scripts/build_synthetic_resume_fixture.py --goldens"
    )
    parses = json.loads(snapshot.read_text(encoding="utf-8"))
    assert set(parses) == {SYNTHETIC_FILENAME}
    assert_synthetic_fixture_text(json.dumps(parses, ensure_ascii=False))


def test_resume_text_fixture_present():
    fixture = GOLDEN / "resume_text.txt"
    assert fixture.exists(), (
        "resume_text.txt missing; the match eval would skip and CI would pass with no "
        "AUROC. Run: python scripts/build_synthetic_resume_fixture.py --goldens"
    )
    text = fixture.read_text(encoding="utf-8")
    assert len(text) > 1000, "resume fixture is suspiciously short"
    assert_synthetic_fixture_text(text)
