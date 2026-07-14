"""Fail CI when private resumes or test artifacts are tracked.

The current-tree check is safe to run on every pull request. ``--history`` is
reserved for the coordinated history-rewrite verification because the existing
repository history is known to contain private artifacts until that operation.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_NOTICE = "SYNTHETIC TEST FIXTURE - NOT A REAL PERSON"
SYNTHETIC_NAME = "Jordan Lee"
SYNTHETIC_EMAIL = "jordan.lee@example.com"
SYNTHETIC_PHONE_FRAGMENT = "555-01"

SOURCE_FIXTURE = "agentception/evals/fixtures/synthetic_resume.json"
TEXT_GOLDEN = "agentception/evals/golden/resume_text.txt"
PARSE_GOLDEN = "agentception/evals/golden/resume_parses.json"
SENSITIVE_GOLDENS = {TEXT_GOLDEN, PARSE_GOLDEN}

FORBIDDEN_PATH_PARTS = (
    "/e2e/screenshots/",
    "/playwright-report/",
    "/test-results/",
)
FORBIDDEN_E2E_SUFFIXES = {
    ".gif",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".trace",
    ".webm",
    ".zip",
}
FORBIDDEN_DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})", re.I)


def git(*args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=not binary,
    )
    return result.stdout


def validate_fixture_text(path: str, text: str, errors: list[str]) -> None:
    for required in (SYNTHETIC_NOTICE, SYNTHETIC_NAME, SYNTHETIC_EMAIL):
        if required not in text:
            errors.append(f"{path}: missing required synthetic fixture marker")
            break

    for domain in EMAIL_RE.findall(text):
        if domain.lower() not in {"example.com", "example.org", "example.net"}:
            errors.append(f"{path}: contains a non-example email domain")
            break


def validate_source_fixture(errors: list[str]) -> None:
    source = REPOSITORY_ROOT / SOURCE_FIXTURE
    if not source.is_file():
        errors.append(f"{SOURCE_FIXTURE}: canonical synthetic fixture is missing")
        return

    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        contact = data["contact"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        errors.append(f"{SOURCE_FIXTURE}: invalid fixture schema ({type(exc).__name__})")
        return

    if data.get("fixture_notice") != SYNTHETIC_NOTICE:
        errors.append(f"{SOURCE_FIXTURE}: synthetic notice is missing")
    if contact.get("name") != SYNTHETIC_NAME:
        errors.append(f"{SOURCE_FIXTURE}: unexpected fixture identity")
    if contact.get("email") != SYNTHETIC_EMAIL:
        errors.append(f"{SOURCE_FIXTURE}: email must use the reserved example domain")
    if SYNTHETIC_PHONE_FRAGMENT not in str(contact.get("phone", "")):
        errors.append(f"{SOURCE_FIXTURE}: phone must use a reserved 555-01xx number")

    validate_fixture_text(
        SOURCE_FIXTURE, json.dumps(data, ensure_ascii=True), errors
    )


def validate_tracked_path(path: str, errors: list[str]) -> None:
    normalized = "/" + path.replace("\\", "/").lower()
    suffix = Path(path).suffix.lower()

    if any(part in normalized for part in FORBIDDEN_PATH_PARTS):
        errors.append(f"{path}: generated browser artifact must not be tracked")
    if suffix in FORBIDDEN_DATABASE_SUFFIXES:
        errors.append(f"{path}: runtime database must not be tracked")
    if "/e2e/" in normalized and suffix in FORBIDDEN_E2E_SUFFIXES:
        errors.append(f"{path}: E2E binary artifacts must be generated at runtime")


def current_tree_errors() -> list[str]:
    errors: list[str] = []
    tracked_output = git("ls-files", "-z")
    assert isinstance(tracked_output, str)
    tracked = [path for path in tracked_output.split("\0") if path]

    for path in tracked:
        validate_tracked_path(path, errors)

    validate_source_fixture(errors)
    for path in SENSITIVE_GOLDENS:
        file_path = REPOSITORY_ROOT / path
        if not file_path.is_file():
            errors.append(f"{path}: synthetic golden is missing")
            continue
        validate_fixture_text(path, file_path.read_text(encoding="utf-8"), errors)

    return errors


def history_errors() -> list[str]:
    errors: list[str] = []
    objects_output = git("rev-list", "--objects", "--all")
    assert isinstance(objects_output, str)

    for line in objects_output.splitlines():
        object_id, separator, path = line.partition(" ")
        if not separator:
            continue

        path_errors: list[str] = []
        validate_tracked_path(path, path_errors)
        for error in path_errors:
            errors.append(f"history object {object_id[:12]}: {error}")

        if path not in SENSITIVE_GOLDENS:
            continue
        object_type = git("cat-file", "-t", object_id)
        assert isinstance(object_type, str)
        if object_type.strip() != "blob":
            continue
        content = git("cat-file", "blob", object_id, binary=True)
        assert isinstance(content, bytes)
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(
                f"history object {object_id[:12]}: {path} is not valid UTF-8 text"
            )
            continue
        blob_errors: list[str] = []
        validate_fixture_text(path, text, blob_errors)
        for error in blob_errors:
            errors.append(f"history object {object_id[:12]}: {error}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--history",
        action="store_true",
        help="also verify every reachable Git object after a coordinated rewrite",
    )
    args = parser.parse_args()

    errors = current_tree_errors()
    if args.history:
        errors.extend(history_errors())

    if errors:
        print("Repository privacy check failed:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1

    scope = "current tree and history" if args.history else "current tree"
    print(f"Repository privacy check passed ({scope}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
