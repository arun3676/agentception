"""Offline quality-evaluation setup and report generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

REPORT: dict[str, float] = {}
RETIRED_METRICS = {
    "resume_field_accuracy",
    "resume_field_accuracy_fallback",
    "study_relevance",
}


def pytest_configure(config):
    config.addinivalue_line("markers", "eval: offline quality metric (runs in CI)")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Collect numeric record_property metrics for the final report."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        for key, value in report.user_properties:
            if isinstance(value, (int, float)):
                REPORT[key] = value


def pytest_sessionfinish(session, exitstatus):
    if not REPORT:
        return

    out = ROOT / "evals" / "report.json"

    # Merge so a focused offline eval invocation does not erase metrics produced
    # by another offline module.
    existing: dict[str, float] = {}
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing.update(REPORT)
    for metric in RETIRED_METRICS:
        existing.pop(metric, None)

    out.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    lines = ["| metric | value |", "|---|---|"]
    lines += [f"| {key} | {value} |" for key, value in sorted(existing.items())]
    (ROOT / "evals" / "report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("\n" + "\n".join(lines))
    print(f"\nwrote {out.name} + report.md")
