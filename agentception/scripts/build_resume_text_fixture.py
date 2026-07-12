"""Commit the resume text the match eval scores against — redacted, no PDF.

The match eval used to read a PDF out of `resume/` at runtime, guarded by
`skipif(not RESUME_DIR.exists())`. Those PDFs are personal documents and are not
published, so in CI that guard would have quietly skipped the headline AUROC metric
and left the build green — the same silent-degradation failure the eval harness exists
to catch, this time in the harness itself.

The eval needs the resume *text*, not the document. So the text is extracted once,
scrubbed of contact details, and committed. CI then has everything it needs and the
skip can be deleted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.pii import PSEUDONYM_EMAIL, _EMAIL, _PHONE, redact_text  # noqa: E402
from server.tools.resume_ingest import extract_pdf_text_locally  # noqa: E402

RESUME_DIR = ROOT.parent / "resume"
PAIRS = ROOT / "evals" / "golden" / "match_pairs.jsonl"
OUT = ROOT / "evals" / "golden" / "resume_text.txt"


def main() -> None:
    first = json.loads(PAIRS.read_text(encoding="utf-8").splitlines()[0])
    pdf = RESUME_DIR / first["resume"]
    if not pdf.exists():
        sys.exit(f"{pdf} not found — this script needs the private resume/ folder")

    text = redact_text(extract_pdf_text_locally(pdf.read_bytes()))

    # Verify by pattern, never by literal. Asserting `"realname@gmail.com" not in text`
    # would put the very address we are scrubbing into a public source file.
    leaked_emails = {e for e in _EMAIL.findall(text) if e != PSEUDONYM_EMAIL}
    assert not leaked_emails, f"redaction missed {len(leaked_emails)} email(s)"
    assert not _PHONE.search(text), "redaction missed a phone number"

    OUT.write_text(text, encoding="utf-8")
    print(f"{pdf.name} -> {OUT.relative_to(ROOT)} ({len(text)} chars, redacted)")
    print("\n  NOTE: the embedding cache is keyed on this text. Re-run")
    print("  scripts/build_eval_embeddings.py so the match eval can replay it offline.")


if __name__ == "__main__":
    main()
