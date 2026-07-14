"""Privacy guardrails for committed synthetic resume fixtures.

Committed resume fixtures must be visibly synthetic and use reserved contact data.
This module intentionally does not offer a "redact a real resume" helper: replacing
an email address while retaining someone's identity and work history is not safe
anonymisation.
"""

from __future__ import annotations

import re

SYNTHETIC_NOTICE = "SYNTHETIC TEST FIXTURE - NOT A REAL PERSON"
SYNTHETIC_NAME = "Jordan Lee"
SYNTHETIC_EMAIL = "jordan.lee@example.com"
# NANPA reserves 555-0100 through 555-0199 for fictional use.
SYNTHETIC_PHONE = "+1 (202) 555-0147"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?:\+?1[\s.-]*)?\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}")
_RESERVED_555 = re.compile(
    r"(?:\+?1[\s.-]*)?\(?\d{3}\)?[\s.-]*555[\s.-]*01\d{2}"
)


def assert_synthetic_fixture_text(text: str) -> None:
    """Reject committed fixture text that is not clearly and safely synthetic."""
    if SYNTHETIC_NOTICE not in text:
        raise AssertionError("synthetic fixture notice is missing")
    if SYNTHETIC_NAME not in text:
        raise AssertionError("canonical synthetic identity is missing")
    if SYNTHETIC_EMAIL not in text:
        raise AssertionError("canonical example.com email is missing")
    if SYNTHETIC_PHONE not in text:
        raise AssertionError("canonical reserved 555 phone is missing")

    non_example_emails = [
        email for email in _EMAIL.findall(text) if not email.lower().endswith("@example.com")
    ]
    if non_example_emails:
        raise AssertionError(
            f"fixture contains {len(non_example_emails)} non-example.com email(s)"
        )

    phones = _PHONE.findall(text)
    non_reserved_phones = [phone for phone in phones if not _RESERVED_555.fullmatch(phone)]
    if non_reserved_phones:
        raise AssertionError(
            f"fixture contains {len(non_reserved_phones)} non-reserved phone number(s)"
        )
