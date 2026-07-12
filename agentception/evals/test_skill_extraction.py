"""How good is skill extraction, really?

Measures the live extractor against the labelled golden JDs. This is the number
Phase 3 (ESCO taxonomy) has to beat.

Read `vocabulary_ceiling` alongside recall: a whitelist extractor can only return
words that are in its whitelist, so recall is capped by vocabulary coverage. Without
that number, a vocabulary problem looks like an extraction problem.
"""

from __future__ import annotations

import pytest

from evals.metrics import (
    load_jd_labels,
    load_jd_text,
    micro_prf,
    normalise_all,
    prf,
    vocabulary_ceiling,
)
from server.tools.resume_job_matcher import analyze_gaps, extract_jd_skills

LABELS = load_jd_labels()

# Floors sit just under the current numbers, so a regression trips them — including
# a revert to the previous keyword-list extractor (F1 0.405, recall 0.263), which
# would now fail both the F1 and the recall gate. That is the point: the improvement
# is locked in, not just celebrated once.
#
# The precision floor is deliberately below the old extractor's 0.890. That extractor
# was precise because it was nearly blind — it could only name 77 skills, so it was
# rarely wrong and usually silent. Trading some precision for +60% recall is the right
# call for a gap-finder: failing to tell someone about a real gap is worse than
# listing one skill they already have.
MIN_F1 = 0.48
MIN_PRECISION = 0.65
MIN_RECALL = 0.35

pytestmark = pytest.mark.eval


@pytest.mark.skipif(not LABELS, reason="golden set not built (scripts/build_golden_jds.py)")
def test_skill_extraction_quality(record_property, capsys):
    pairs: list[tuple[set[str], set[str]]] = []
    per_doc: list[tuple[str, object]] = []

    for rec in LABELS:
        gold = normalise_all(rec["skills"])
        predicted = normalise_all(extract_jd_skills(load_jd_text(rec["id"])))
        pairs.append((predicted, gold))
        per_doc.append((rec["id"], prf(predicted, gold)))

    overall = micro_prf(pairs)

    # What recall could this extractor reach even if its matching were perfect?
    # (i.e. how much of the gold vocabulary does the taxonomy even contain)
    from server.tools.skill_extractor import _load_taxonomy

    vocab = normalise_all(_load_taxonomy()[0].keys())
    ceiling = vocabulary_ceiling([g for _, g in pairs], vocab)

    zero_recall = [jid for jid, m in per_doc if m.recall == 0.0]
    with capsys.disabled():
        print(f"\n  skill-extraction (micro, n={len(pairs)} JDs): {overall}")
        print(f"  vocabulary ceiling on recall: {ceiling:.3f} "
              f"(recall {overall.recall:.3f} = {overall.recall / ceiling:.0%} of what's reachable)")
        print(f"  JDs where extraction found nothing gold: {len(zero_recall)}/{len(per_doc)}")

    record_property("skill_extraction_f1", round(overall.f1, 4))
    record_property("skill_extraction_precision", round(overall.precision, 4))
    record_property("skill_extraction_recall", round(overall.recall, 4))
    record_property("skill_extraction_recall_ceiling", round(ceiling, 4))

    assert overall.f1 >= MIN_F1, f"F1 {overall.f1:.3f} below floor {MIN_F1}"
    assert overall.precision >= MIN_PRECISION, (
        f"precision {overall.precision:.3f} below floor {MIN_PRECISION} — "
        "the extractor is inventing skills the posting never asked for"
    )
    assert overall.recall >= MIN_RECALL, f"recall {overall.recall:.3f} below floor {MIN_RECALL}"


@pytest.mark.skipif(not LABELS, reason="golden set not built")
def test_gap_analysis_never_surfaces_job_ad_boilerplate(capsys):
    """The bug this guards against shipped: gaps were raw JD tokens, so the study
    drawer offered to teach the user "equity" and "offers".

    It runs through `analyze_gaps` (the path that had the bug), not just the
    extractor's whitelist — asserting against a whitelist it can't escape would be
    a test that cannot fail.
    """
    banned = {
        "equity", "offer", "employment", "location", "type", "fulltime", "salary",
        "benefit", "bonus", "remote", "onsite", "hybrid", "responsibility",
        "qualification", "requirement", "candidate", "applicant", "compensation",
    }
    resume_insights = {"skills_flat": ["Python"], "tech_stack": ["Python"]}

    offenders: list[str] = []
    for rec in LABELS:
        gaps = analyze_gaps(load_jd_text(rec["id"]), resume_insights)["missing_skills"]
        leaked = normalise_all(gaps) & banned
        if leaked:
            offenders.append(f"{rec['id']}: {sorted(leaked)}")

    with capsys.disabled():
        print(f"\n  gap analysis checked on {len(LABELS)} JDs — boilerplate leaks: {len(offenders)}")

    assert not offenders, f"gaps contained job-ad boilerplate: {offenders[:5]}"
