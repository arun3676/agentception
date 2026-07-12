from __future__ import annotations

"""Turning a raw match score into something a human can act on.

A raw hybrid score of "43.9" means nothing to a job seeker. Worse, it *looks* like a
percentage, so it reads as "you are 44% qualified" — which is not what it measures.

Two jobs here:

1. **Calibrate.** Map the raw score onto the probability that a posting is actually
   in-domain, fitted on the labelled pairs in the eval golden set (isotonic
   regression, which needs no assumption about the shape of the curve). The fitted
   curve is committed as data, so production doesn't ship scikit-learn.
2. **Band.** Collapse that probability into three honest labels. Nobody can act on
   the difference between 61% and 64%.

If we have no signal (no semantic embedding, empty JD), we say so — `None` — rather
than inventing a number.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

_CURVE_PATH = Path(__file__).parent.parent / "data" / "match_calibration.json"

Band = Literal["strong", "possible", "stretch", "unknown"]

# Thresholds on the *calibrated probability*, not the raw score.
STRONG_MIN = 0.65
POSSIBLE_MIN = 0.40


@dataclass
class CalibratedMatch:
    raw_score: Optional[float]
    probability: Optional[float]
    band: Band
    explanation: str

    def to_dict(self) -> dict:
        return {
            "raw_score": self.raw_score,
            "probability": round(self.probability, 3) if self.probability is not None else None,
            "band": self.band,
            "explanation": self.explanation,
        }


@lru_cache(maxsize=1)
def _curve() -> Optional[list[tuple[float, float]]]:
    """The fitted (raw_score -> probability) step function, or None if never fitted."""
    if not _CURVE_PATH.exists():
        return None
    data = json.loads(_CURVE_PATH.read_text(encoding="utf-8"))
    return [(float(x), float(y)) for x, y in data["curve"]]


def calibrate(raw_score: Optional[float]) -> Optional[float]:
    """Raw hybrid score (0-100) -> probability the job is a genuine fit (0-1)."""
    if raw_score is None:
        return None

    curve = _curve()
    if not curve:
        # No fitted curve yet: fall back to a linear read of the raw score rather
        # than pretending to a precision we haven't earned.
        return max(0.0, min(1.0, raw_score / 100.0))

    # Piecewise-linear interpolation over the isotonic steps.
    if raw_score <= curve[0][0]:
        return curve[0][1]
    if raw_score >= curve[-1][0]:
        return curve[-1][1]

    for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
        if x0 <= raw_score <= x1:
            if x1 == x0:
                return y1
            t = (raw_score - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)

    return curve[-1][1]


def band_for(probability: Optional[float]) -> Band:
    if probability is None:
        return "unknown"
    if probability >= STRONG_MIN:
        return "strong"
    if probability >= POSSIBLE_MIN:
        return "possible"
    return "stretch"


def explain(
    band: Band,
    matched: list[str],
    missing: list[str],
    signals: list[str],
) -> str:
    """One sentence a human can act on. No numbers-as-authority."""
    if band == "unknown":
        return "Not enough of this posting could be read to assess the fit."

    lead = {
        "strong": "Strong fit",
        "possible": "Possible fit",
        "stretch": "A stretch",
    }[band]

    parts = [lead]
    if matched:
        parts.append(f"you already show {', '.join(matched[:3])}")
    if missing:
        parts.append(f"the posting also wants {', '.join(missing[:3])}")
    if "semantic" not in signals:
        parts.append("(keyword match only — deeper comparison unavailable)")

    return " — ".join(parts) + "."


def calibrated_match(
    raw_score: Optional[float],
    matched: list[str],
    missing: list[str],
    signals: list[str],
) -> CalibratedMatch:
    probability = calibrate(raw_score)
    band = band_for(probability)
    return CalibratedMatch(
        raw_score=raw_score,
        probability=probability,
        band=band,
        explanation=explain(band, matched, missing, signals),
    )
