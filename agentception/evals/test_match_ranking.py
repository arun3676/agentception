"""Does the match score actually rank good fits above bad ones?

AUROC over resume<->JD pairs, plus a permutation test — because at this sample size
the AUROC alone is not evidence. A random scorer clears 0.60 roughly a quarter of
the time with 6 positives and 8 negatives, so the p-value is reported next to the
number and the honest reading is in docs/EVALS.md.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sklearn.metrics import roc_auc_score

from evals.embedding_cache import assert_cache_covers
from evals.metrics import auroc_permutation_test, load_jd_text, load_match_pairs
from server.tools.resume_job_matcher import compute_match_score
from server.tools.resume_store import extract_resume_insights, put_text

PAIRS = load_match_pairs()
# The extracted, contact-redacted resume text — committed, so this eval runs in CI.
# It used to read a PDF out of the private resume/ folder behind a skipif, which meant
# the headline metric would have vanished in CI while the build stayed green.
# Rebuild with scripts/build_resume_text_fixture.py.
RESUME_TEXT = Path(__file__).resolve().parent / "golden" / "resume_text.txt"

MIN_AUROC = 0.70  # current: 0.75. A coin flip is 0.50.

pytestmark = pytest.mark.eval


@pytest.fixture(scope="module")
def resume():
    text = RESUME_TEXT.read_text(encoding="utf-8")
    token = put_text(text)
    return text, extract_resume_insights(token) or {}


@pytest.fixture(autouse=True)
def _offline_embeddings(monkeypatch):
    """Serve embeddings from the committed cache: offline, reproducible, and still
    the real hybrid (keyword + semantic) scorer."""
    from evals.embedding_cache import cached_embed

    monkeypatch.setattr("server.tools.resume_job_matcher._embed", cached_embed)
    monkeypatch.setattr("server.tools.resume_job_matcher._get_voyage_key", lambda: "cached")


@pytest.mark.skipif(not PAIRS, reason="match pairs not built (scripts/build_match_pairs.py)")
def test_match_score_ranks_in_domain_jobs_higher(resume, record_property, capsys):
    resume_text, insights = resume

    # Fail loudly BEFORE scoring if the cache is incomplete. compute_match_score
    # swallows an embedding failure and silently falls back to keyword-only, so a
    # missing cache would otherwise surface as a fake *model* regression rather
    # than the missing *file* it actually is.
    assert_cache_covers([resume_text] + [load_jd_text(p["jd_id"]) for p in PAIRS])

    async def score_all():
        return await asyncio.gather(*[
            compute_match_score(resume_text, load_jd_text(p["jd_id"]), insights)
            for p in PAIRS
        ])

    results = asyncio.run(score_all())

    # Every pair must have used the semantic signal; if any fell back to keyword-only
    # the metric silently changes meaning.
    keyword_only = [p["jd_id"] for p, r in zip(PAIRS, results) if "semantic" not in r["signals"]]
    assert not keyword_only, f"semantic signal missing for {keyword_only} — metric is not comparable"

    scores = [r["match_score"] for r in results]
    labels = [p["fit"] for p in PAIRS]

    auroc = roc_auc_score(labels, scores)
    p_value, null_p95 = auroc_permutation_test(labels, scores)

    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    with capsys.disabled():
        print(f"\n  match AUROC (n={len(PAIRS)}): {auroc:.3f}  "
              f"(permutation p={p_value:.3f}, random scorer reaches {null_p95:.3f} at p95)")
        print(f"  in-domain  mean={sum(pos)/len(pos):.1f}  {[round(s,1) for s in sorted(pos, reverse=True)]}")
        print(f"  out-domain mean={sum(neg)/len(neg):.1f}  {[round(s,1) for s in sorted(neg, reverse=True)]}")
        if p_value > 0.05:
            print(f"  ! n={len(PAIRS)} is too small for this to be statistically significant")

    record_property("match_auroc", round(float(auroc), 4))
    record_property("match_auroc_pvalue", round(float(p_value), 4))

    assert auroc >= MIN_AUROC, (
        f"AUROC {auroc:.3f} below floor {MIN_AUROC} — the matcher cannot reliably "
        f"tell an in-domain job from an out-of-domain one (0.5 = random)"
    )
