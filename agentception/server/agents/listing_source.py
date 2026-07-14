from __future__ import annotations

ATS_PLATFORM_NAMES = frozenset(
    {
        "ashbyhq",
        "ashby",
        "greenhouse",
        "lever",
        "workday",
        "workable",
        "icims",
        "jobvite",
        "smartrecruiters",
        "breezy",
        "jazz",
        "bamboohr",
        "recruitee",
        "personio",
        "teamtailor",
        "fountain",
        "jazzhr",
    }
)


def is_ats_platform(name: str) -> bool:
    """Return whether a display name identifies an ATS rather than an employer."""
    normalized = (name or "").strip().lower()
    if not normalized:
        return False
    return normalized in ATS_PLATFORM_NAMES or any(
        platform in normalized or normalized in platform for platform in ATS_PLATFORM_NAMES
    )
