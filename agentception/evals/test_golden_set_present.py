"""The golden set must exist.

Every other eval uses `skipif` when its inputs are missing — which is right for a
laptop with a half-built golden set, and dangerous in CI, where a missing file
would turn the entire quality gate into a green skip. This test has no skip: if the
golden set isn't there, the build fails loudly and says which piece is missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.metrics import GOLDEN, JDS, load_jd_labels, load_match_pairs

RESUME_DIR = Path(__file__).resolve().parents[2] / "resume"

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
    snapshot = GOLDEN / "resume_parses.json"
    assert snapshot.exists(), (
        "production resume parses missing. Run: python scripts/build_resume_golden.py"
    )


def test_resume_pdfs_present():
    assert RESUME_DIR.exists(), f"resume/ folder not found at {RESUME_DIR}"
    pdfs = list(RESUME_DIR.glob("*.pdf"))
    assert len(pdfs) >= 5, f"only {len(pdfs)} resume PDFs found"
