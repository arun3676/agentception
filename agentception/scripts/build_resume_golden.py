"""Snapshot the production resume parse (Reducto) for the eval golden set.

Reducto is the primary parser users actually hit, but it is a paid network call, so
CI can't run it. Snapshot its structured output once and commit it; the eval then
measures production parsing quality offline and for free — the same trick as the
embedding cache.

    python scripts/build_resume_golden.py
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

from evals.pii import redact_contact  # noqa: E402
from server.tools.reducto_parser import parse_resume_with_reducto  # noqa: E402

RESUME_DIR = ROOT.parent / "resume"
OUT = ROOT / "evals" / "golden" / "resume_parses.json"


async def main() -> None:
    pdfs = sorted(RESUME_DIR.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"no PDFs in {RESUME_DIR}")

    snapshot: dict[str, dict] = {}
    if OUT.exists():
        snapshot = json.loads(OUT.read_text(encoding="utf-8"))

    for pdf in pdfs:
        if pdf.name in snapshot:
            continue
        print(f"  parsing {pdf.name} ...")
        result = await parse_resume_with_reducto(pdf.read_bytes(), pdf.name)
        if not result:
            print("    ! Reducto returned nothing — skipping")
            continue
        # Redact before it ever touches disk — the golden set is committed to a
        # public repo, and the raw PDFs deliberately are not.
        snapshot[pdf.name] = redact_contact(result["structured"])
        OUT.write_text(json.dumps(snapshot, indent=1), encoding="utf-8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=1), encoding="utf-8")
    print(f"\n{len(snapshot)} resume parses -> {OUT.name} "
          f"({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    asyncio.run(main())
