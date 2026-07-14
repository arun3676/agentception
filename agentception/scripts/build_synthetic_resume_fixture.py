"""Build deterministic synthetic resume fixtures without reading private data.

Examples:
    python scripts/build_synthetic_resume_fixture.py --goldens
    python scripts/build_synthetic_resume_fixture.py --output test-results/fixtures/resume.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.synthetic_resume import (  # noqa: E402
    SYNTHETIC_FILENAME,
    build_structured_parse,
    load_synthetic_resume,
    render_resume_text,
)

GOLDEN = ROOT / "evals" / "golden"


def refresh_goldens() -> None:
    data = load_synthetic_resume()
    GOLDEN.mkdir(parents=True, exist_ok=True)
    (GOLDEN / "resume_text.txt").write_text(
        render_resume_text(data), encoding="utf-8"
    )
    (GOLDEN / "resume_parses.json").write_text(
        json.dumps({SYNTHETIC_FILENAME: build_structured_parse(data)}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print("refreshed synthetic resume text and structured golden")


def build_pdf(output: Path, template: str) -> None:
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    from server.tools.resume_pdf_generator import generate_pdf_from_template

    generated = generate_pdf_from_template(load_synthetic_resume(), template)
    reader = PdfReader(BytesIO(generated))
    writer = PdfWriter()
    for page in reader.pages:
        if (page.extract_text() or "").strip():
            writer.add_page(page)
    if not writer.pages:
        raise RuntimeError("synthetic PDF renderer produced no text-bearing pages")

    rendered = BytesIO()
    writer.write(rendered)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rendered.getvalue())
    print(f"wrote temporary synthetic PDF: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--goldens", action="store_true", help="refresh committed text/JSON goldens"
    )
    parser.add_argument("--output", type=Path, help="write an untracked synthetic PDF")
    parser.add_argument("--template", default="classic_serif")
    args = parser.parse_args()

    if not args.goldens and args.output is None:
        parser.error("choose --goldens and/or --output")
    if args.goldens:
        refresh_goldens()
    if args.output is not None:
        build_pdf(args.output.resolve(), args.template)


if __name__ == "__main__":
    main()
