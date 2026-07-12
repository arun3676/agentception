"""Calibrated, explainable match scores.

The point of this module is that we stop lying: no fabricated placeholder score, no
raw number presented as a qualification percentage, and "we couldn't assess this" is
a first-class answer.
"""

import pytest

from server.tools.match_calibration import (
    band_for,
    calibrate,
    calibrated_match,
    explain,
)


class TestCalibrate:
    def test_none_stays_none(self):
        # An unassessable job must never acquire a number on the way through.
        assert calibrate(None) is None

    def test_returns_a_probability(self):
        p = calibrate(45.0)
        assert p is not None and 0.0 <= p <= 1.0

    def test_is_monotonic(self):
        # Isotonic regression guarantees this; assert it, because a higher raw score
        # producing a *lower* fit probability would be nonsense the UI would show.
        probabilities = [calibrate(s) for s in range(0, 101, 5)]
        assert all(a <= b for a, b in zip(probabilities, probabilities[1:]))

    def test_clamps_out_of_range_scores(self):
        assert 0.0 <= calibrate(-10.0) <= 1.0
        assert 0.0 <= calibrate(999.0) <= 1.0


class TestBands:
    def test_unknown_when_no_probability(self):
        assert band_for(None) == "unknown"

    @pytest.mark.parametrize(
        "probability,expected",
        [(0.95, "strong"), (0.65, "strong"), (0.5, "possible"), (0.4, "possible"), (0.1, "stretch")],
    )
    def test_thresholds(self, probability, expected):
        assert band_for(probability) == expected


class TestExplain:
    def test_names_what_you_have_and_what_is_missing(self):
        text = explain("possible", ["Python", "Docker"], ["Kubernetes"], ["keyword", "semantic"])
        assert "Python" in text and "Kubernetes" in text

    def test_admits_when_only_keyword_matching_ran(self):
        text = explain("possible", ["Python"], [], ["keyword"])
        assert "keyword match only" in text

    def test_unknown_says_so_plainly(self):
        assert "Not enough" in explain("unknown", [], [], [])


class TestCalibratedMatch:
    def test_unassessable_job_reports_unknown(self):
        result = calibrated_match(None, [], [], [])
        assert result.band == "unknown"
        assert result.probability is None
        assert result.raw_score is None

    def test_serialises_for_the_api(self):
        payload = calibrated_match(50.0, ["Python"], ["Kubernetes"], ["keyword", "semantic"]).to_dict()
        assert set(payload) == {"raw_score", "probability", "band", "explanation"}
        assert payload["band"] in {"strong", "possible", "stretch", "unknown"}
