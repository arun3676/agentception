"""Build the resume<->JD fit pairs used to measure match-ranking AUROC.

Labelling is *weak supervision by role domain*. The single canonical input is a
synthetic composite profile, so the narrow question is whether the matcher ranks
in-domain postings above out-of-domain postings for that fixture.

  positive (fit=1): AI Engineer postings
  negative (fit=0): Frontend / DevOps postings
  excluded:         Backend / Data Engineer — genuinely ambiguous for this profile,
                    and a benchmark shouldn't punish a model for a judgement call.

    python scripts/build_match_pairs.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLDEN = ROOT / "evals" / "golden"
INDEX = GOLDEN / "jds" / "index.jsonl"
OUT = GOLDEN / "match_pairs.jsonl"

# The canonical synthetic resume fixture. No personal PDF is read by the eval.
RESUME = "synthetic-jordan-lee.pdf"

# Label from the POSTING'S OWN TITLE, not the query that surfaced it. Searching
# "AI Engineer" also returns "Senior Staff Security Engineer, AI" — a security role,
# not an AI/ML one. Labelling that a positive because of the query was injecting
# noise straight into the metric.
POSITIVE_TITLE = re.compile(
    r"\b(ai|ml|machine[\s-]?learning|llm|applied scientist|research engineer|"
    r"deep learning|nlp|genai|generative ai)\b",
    re.I,
)
NEGATIVE_TITLE = re.compile(
    r"\b(frontend|front[\s-]end|devops|site reliability|sre|mobile|ios|android|"
    r"design system|infrastructure|platform engineer|security)\b",
    re.I,
)


def classify(title: str) -> int | None:
    """1 = in-domain for an AI/ML engineer, 0 = out-of-domain, None = ambiguous.

    A title that trips both patterns ("AI Security Engineer") is genuinely
    ambiguous and is dropped — a benchmark shouldn't punish a model for a
    judgement call a human would also hesitate on.
    """
    pos, neg = bool(POSITIVE_TITLE.search(title)), bool(NEGATIVE_TITLE.search(title))
    if pos and not neg:
        return 1
    if neg and not pos:
        return 0
    return None


def main() -> None:
    index = [json.loads(l) for l in INDEX.read_text(encoding="utf-8").splitlines() if l.strip()]

    rows, dropped = [], 0
    for rec in index:
        fit = classify(rec["title"])
        if fit is None:
            dropped += 1
            continue
        rows.append({
            "resume": RESUME,
            "jd_id": rec["id"],
            "jd_role": rec["searched_role"],
            "jd_title": rec["title"],
            "fit": fit,
            "labeled_by": "weak-supervision:posting-title",
        })
    print(f"dropped {dropped} ambiguous titles")

    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    pos = sum(r["fit"] for r in rows)
    print(f"{len(rows)} pairs -> {OUT}  ({pos} positive / {len(rows) - pos} negative)")


if __name__ == "__main__":
    main()
