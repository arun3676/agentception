"""Fit the match-score calibration curve on the labelled golden pairs.

Isotonic regression: it only assumes the mapping is monotonic (a higher raw score
should never mean a *lower* probability of fit), which is the one thing we actually
believe. It fits no parametric shape, which is right when we have 39 points and no
theory about the curve.

The fitted curve is written to server/data/match_calibration.json so the API can
interpolate it at request time without shipping scikit-learn.

    python scripts/fit_match_calibration.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import numpy as np  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from evals.embedding_cache import cached_embed  # noqa: E402
from evals.metrics import load_jd_text, load_match_pairs  # noqa: E402

OUT = ROOT / "server" / "data" / "match_calibration.json"
RESUME_TEXT = ROOT / "evals" / "golden" / "resume_text.txt"


async def main() -> None:
    import server.tools.resume_job_matcher as matcher
    from server.tools.resume_store import extract_resume_insights, put_text

    # Score with the cached embeddings so this is reproducible and free.
    matcher._embed = cached_embed
    matcher._get_voyage_key = lambda: "cached"

    pairs = load_match_pairs()
    if not pairs:
        sys.exit("no match pairs — run scripts/build_match_pairs.py")

    resume_text = RESUME_TEXT.read_text(encoding="utf-8")
    insights = extract_resume_insights(put_text(resume_text)) or {}

    results = await asyncio.gather(*[
        matcher.compute_match_score(resume_text, load_jd_text(p["jd_id"]), insights)
        for p in pairs
    ])

    scores = np.array([r["match_score"] for r in results], dtype=float)
    labels = np.array([p["fit"] for p in pairs], dtype=int)

    auroc = roc_auc_score(labels, scores)
    print(f"{len(pairs)} pairs, AUROC={auroc:.3f}")

    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    iso.fit(scores, labels)

    # Sample the fitted function on a grid — the API interpolates this, so it never
    # needs scikit-learn at request time.
    grid = np.linspace(scores.min(), scores.max(), 24)
    probs = iso.predict(grid)
    curve = [[round(float(x), 3), round(float(y), 4)] for x, y in zip(grid, probs)]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "fitted_on": f"{len(pairs)} labelled resume<->JD pairs",
        "method": "isotonic regression",
        "auroc": round(float(auroc), 4),
        "raw_score_range": [round(float(scores.min()), 2), round(float(scores.max()), 2)],
        "curve": curve,
    }, indent=1), encoding="utf-8")

    print(f"\ncurve -> {OUT.relative_to(ROOT)}")
    print("  raw ->  P(fit)")
    for x, y in curve[::4]:
        print(f"  {x:5.1f} -> {y:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
