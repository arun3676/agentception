from __future__ import annotations

"""Salary extraction.

Two sources, in order of trust:
1. Schema.org JobPosting `baseSalary` (a structured MonetaryAmount) — this is
   what the employer actually posted, so it's authoritative.
2. A pay range written into the snippet/description text ("$150K – $250K").

We never invent a number. If neither source has one, the job shows no salary.
"""

import json
import re
from typing import Optional


# "$150K", "$150,000", "$150k/yr", "150K-250K", "$150,000 - $200,000 a year"
_RANGE = re.compile(
    r"\$?\s*(\d{2,3}(?:,\d{3})?|\d{2,3})\s*[kK]?\s*"
    r"(?:-|–|—|to)\s*"
    r"\$?\s*(\d{2,3}(?:,\d{3})?|\d{2,3})\s*[kK]?"
    r"(?:\s*(?:/\s*(?:yr|year|hr|hour)|per\s+(?:year|hour)|a\s+(?:year|hour)))?",
)
_SINGLE = re.compile(
    r"\$\s*(\d{2,3}(?:,\d{3})?|\d{2,3})\s*[kK]\b"
    r"(?:\s*(?:/\s*(?:yr|year)|per\s+year|a\s+year))?",
)

# A range like 150-250 is only pay if the numbers are plausible salaries.
_MIN_ANNUAL = 20_000
_MAX_ANNUAL = 2_000_000


def _to_annual(raw: str) -> Optional[int]:
    """'150', '150,000', '150K' -> 150000. Bare 2-3 digit numbers are read as thousands."""
    digits = raw.replace(",", "").strip()
    if not digits.isdigit():
        return None
    value = int(digits)
    # "150" or "150K" both mean 150,000; a written-out "150000" stays as-is
    if value < 1000:
        value *= 1000
    return value


def _fmt(value: int) -> str:
    if value >= 1000 and value % 1000 == 0:
        return f"${value // 1000}K"
    return f"${value:,}"


def _plausible(lo: int, hi: int) -> bool:
    return _MIN_ANNUAL <= lo <= hi <= _MAX_ANNUAL


def extract_salary_from_text(text: Optional[str]) -> Optional[str]:
    """Find a pay range in free text and return a clean 'from–to' string."""
    if not text:
        return None

    for m in _RANGE.finditer(text):
        # A bare range like "200-500" is a headcount or years, not pay. Require a
        # currency ($) or a K/k unit somewhere in the match to treat it as salary.
        if "$" not in m.group(0) and "k" not in m.group(0).lower():
            continue
        lo, hi = _to_annual(m.group(1)), _to_annual(m.group(2))
        if lo and hi and _plausible(lo, hi):
            return f"{_fmt(lo)} – {_fmt(hi)}"

    m = _SINGLE.search(text)
    if m:
        value = _to_annual(m.group(1))
        if value and _MIN_ANNUAL <= value <= _MAX_ANNUAL:
            return _fmt(value)

    return None


def _format_monetary(base: dict) -> Optional[str]:
    """Render a Schema.org MonetaryAmount / QuantitativeValue into display text."""
    value = base.get("value", base)
    if not isinstance(value, dict):
        return None

    def num(key: str) -> Optional[int]:
        v = value.get(key)
        try:
            return int(float(v)) if v is not None else None
        except (TypeError, ValueError):
            return None

    lo, hi, exact = num("minValue"), num("maxValue"), num("value")
    unit = str(value.get("unitText", "")).upper()

    def annualize(n: int) -> int:
        # Postings quote hourly for some roles; normalize so the plausibility gate works
        return n * 2080 if unit == "HOUR" else n

    if lo and hi:
        lo, hi = annualize(lo), annualize(hi)
        return f"{_fmt(lo)} – {_fmt(hi)}" if _plausible(lo, hi) else None
    if exact:
        exact = annualize(exact)
        return _fmt(exact) if _MIN_ANNUAL <= exact <= _MAX_ANNUAL else None
    return None


def extract_salary_from_jsonld(html: Optional[str]) -> Optional[str]:
    """Pull `baseSalary` out of a page's Schema.org JobPosting JSON-LD."""
    if not html or "baseSalary" not in html:
        return None

    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(block.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        for obj in data if isinstance(data, list) else [data]:
            if not isinstance(obj, dict):
                continue
            base = obj.get("baseSalary")
            if isinstance(base, dict):
                out = _format_monetary(base)
                if out:
                    return out
    return None


def extract_salary(*, jsonld_html: Optional[str] = None, text: Optional[str] = None) -> Optional[str]:
    """Best available salary: authoritative JSON-LD first, then text."""
    return extract_salary_from_jsonld(jsonld_html) or extract_salary_from_text(text)
