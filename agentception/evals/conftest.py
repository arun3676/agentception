"""Eval-suite setup.

Evals are separate from unit tests: they measure model/heuristic *quality* against
a golden set rather than asserting code behaviour, they are slower, and the
judge-based ones cost money. `pyproject.toml` keeps them out of the default
pytest run; CI invokes them explicitly.
"""

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


def pytest_configure(config):
    config.addinivalue_line("markers", "eval: offline quality metric (runs in CI)")
    config.addinivalue_line("markers", "judge: LLM-as-judge metric (costs money; nightly)")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Collect every record_property() metric so we can emit one report at the end."""
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

    # MERGE, don't overwrite. The offline (`-m eval`) and judge (`-m judge`) suites
    # run separately — writing the whole dict each time meant whichever ran last
    # erased the other's metrics, so the report could never show both.
    existing: dict[str, float] = {}
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing.update(REPORT)

    out.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    lines = ["| metric | value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(existing.items())]
    (ROOT / "evals" / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n" + "\n".join(lines))
    print(f"\nwrote {out.name} + report.md")
