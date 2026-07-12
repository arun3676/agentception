"""Salary extraction — only real posted pay, never invented."""

import pytest

from server.tools.salary import (
    extract_salary,
    extract_salary_from_jsonld,
    extract_salary_from_text,
)


class TestFromText:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("On-site. $150K - 250K, Offers Equity", "$150K – $250K"),
            ("Compensation: $150,000 - $200,000 a year", "$150K – $200K"),
            ("Salary range $180K-$240K/yr plus equity", "$180K – $240K"),
            ("$95,000 to $130,000 depending on experience", "$95K – $130K"),
            ("Base pay $220K per year", "$220K"),
        ],
    )
    def test_extracts_real_pay(self, text, expected):
        assert extract_salary_from_text(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "Join our team of engineers building the future",
            "Founded in 2015, we have 200-500 employees",   # headcount, no $/K
            "Series B, raised $50M in funding",              # funding, out of range
            "Work with 5-10 people on a small team",         # team size
            "Open 9-5, Monday to Friday",                    # hours
            "",
            None,
        ],
    )
    def test_ignores_non_salary_numbers(self, text):
        assert extract_salary_from_text(text) is None


class TestFromJsonLd:
    def _wrap(self, base: str) -> str:
        return f'<script type="application/ld+json">{{"@type":"JobPosting","baseSalary":{base}}}</script>'

    def test_min_max_range(self):
        html = self._wrap(
            '{"@type":"MonetaryAmount","currency":"USD","value":'
            '{"@type":"QuantitativeValue","minValue":160000,"maxValue":210000,"unitText":"YEAR"}}'
        )
        assert extract_salary_from_jsonld(html) == "$160K – $210K"

    def test_hourly_is_annualized(self):
        html = self._wrap(
            '{"@type":"MonetaryAmount","value":'
            '{"@type":"QuantitativeValue","value":75,"unitText":"HOUR"}}'
        )
        # 75 * 2080 = 156,000
        assert extract_salary_from_jsonld(html) == "$156K"

    def test_no_jsonld_returns_none(self):
        assert extract_salary_from_jsonld("<html><body>no schema here</body></html>") is None

    def test_malformed_jsonld_does_not_raise(self):
        assert extract_salary_from_jsonld('<script type="application/ld+json">{bad json</script>') is None


class TestExtractSalary:
    def test_jsonld_wins_over_text(self):
        html = (
            '<script type="application/ld+json">{"@type":"JobPosting","baseSalary":'
            '{"@type":"MonetaryAmount","value":{"@type":"QuantitativeValue",'
            '"minValue":160000,"maxValue":210000}}}</script>'
        )
        # text says a different range; JSON-LD is authoritative
        assert extract_salary(jsonld_html=html, text="pays $90K - $100K") == "$160K – $210K"

    def test_falls_back_to_text(self):
        assert extract_salary(jsonld_html="no schema", text="$120K - $160K") == "$120K – $160K"

    def test_none_when_nothing_found(self):
        assert extract_salary(jsonld_html="nope", text="nothing here") is None
