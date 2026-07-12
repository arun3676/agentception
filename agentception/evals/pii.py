"""Pseudonymisation for the committed resume golden set.

The resume eval runs on real PDFs belonging to a real person. The parse snapshot has
to be committed — CI has no Reducto key and no PDFs, so it replays the snapshot — but
a public repository is a bad place for a personal phone number and an email address
that spam crawlers will happily harvest.

So contact details are pseudonymised *before* they are written to the golden set, and
the same function is applied to any parse the tests score. Both sides of the
comparison get the identical transform, so **the measured accuracy is unchanged**: the
parser still has to find the email in the layout and pull it out whole. It just
reports a stand-in value when it does.

Fields that carry no personal risk — name, employer, location, skills — are left
alone. Pseudonymising those would make the eval unverifiable by a reader, which is a
real cost for no privacy gain: the name is on the repository owner's GitHub profile
and the employers are on their public CV.

`phone` is dropped rather than replaced because no test scores it.
"""

from __future__ import annotations

import re
from typing import Any

# A stand-in, not a real inbox. Deliberately obvious so nobody mistakes it for data.
PSEUDONYM_EMAIL = "arun.chukkala@example.com"

_DROP = ("phone", "portfolio", "linkedin", "github")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# International and US forms: +1 (555) 010-4477, 555-010-4477, (555) 010 4477.
_PHONE = re.compile(r"\+?\d{0,2}\s*\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}")


def redact_text(text: str) -> str:
    """Scrub contact details out of free resume text.

    The header line of a resume is the one place a phone number appears, and it
    carries no hiring signal — no skill, employer or date lives there — so removing
    it does not weaken what the match eval measures.
    """
    if not text:
        return text
    text = _EMAIL.sub(PSEUDONYM_EMAIL, text)
    return _PHONE.sub("[phone redacted]", text)


def redact_contact(parsed: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a structured parse with contact PII removed.

    Applied identically by `scripts/build_resume_golden.py` when snapshotting and by
    the resume eval when scoring the live fallback parser, so the snapshot and the
    live path stay comparable.
    """
    if not parsed:
        return parsed

    out = dict(parsed)

    contact = dict(out.get("contact") or {})
    if contact:
        if contact.get("email"):
            contact["email"] = PSEUDONYM_EMAIL
        for field in _DROP:
            contact.pop(field, None)
        out["contact"] = contact

    # The full resume body is snapshotted alongside the parse, and the contact header
    # line lives inside it.
    if out.get("raw_text"):
        out["raw_text"] = redact_text(out["raw_text"])

    return out
