from __future__ import annotations

"""Evidence-only public job discovery.

The containment product must not turn a search query into listing facts. This
module therefore keeps provider text as provider text, never fills a missing
title, employer, location, or description, and deduplicates only by canonical
job URL. Personal resume analysis and company-enrichment fallbacks do not belong
in the anonymous discovery path.
"""

import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field

from ..memory.state_store import Memory
from ..schemas import TimelineEvent
from ..tools.exa_search import exa_search
from ..tools.tavily_search import tavily_search


ATS_POSTING_HOSTS = frozenset(
    {
        "apply.workable.com",
        "boards.greenhouse.io",
        "jobs.ashbyhq.com",
        "jobs.lever.co",
        "job-boards.greenhouse.io",
        "myworkdayjobs.com",
        "wellfound.com",
    }
)
TRACKING_QUERY_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "ref",
        "source",
        "utm_campaign",
        "utm_content",
        "utm_medium",
        "utm_source",
        "utm_term",
    }
)
DEPTH_LIMITS = {"quick": 5, "standard": 10, "deep": 15}


class ProviderUnavailable(RuntimeError):
    """Raised when neither required discovery provider can return a response."""


class PublicJobPosting(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None
    location: str | None = None
    company: str | None = None
    source: str = "unavailable"
    observed_at: str | None = None
    description_origin: str = "unavailable"
    remote_policy: str = "unknown"
    listing_data_quality: str = "partial"


class HiringCompany(BaseModel):
    company_name: str | None = None
    homepage_url: str | None = None
    job_title: str | None = None
    job_url: str | None = None
    job_location: str | None = None
    job_source: str | None = None
    blurb: str | None = None
    salary: str | None = None
    job_posting: PublicJobPosting | None = None
    observed_at: str | None = None
    description_origin: str = "unavailable"
    remote_policy: str = "unknown"
    listing_data_quality: str = "partial"


class RAGDoc(BaseModel):
    run_id: str
    role: str
    location: str
    depth: str
    companies: list[HiringCompany] = Field(default_factory=list)
    total: int = 0
    pagination: dict[str, Any] = Field(default_factory=dict)


def canonical_job_url(raw_url: str) -> str | None:
    """Return a stable public HTTP(S) URL without tracking or fragments."""
    try:
        parsed = urlsplit(raw_url.strip())
        port = parsed.port
    except (TypeError, ValueError):
        return None

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or (port is not None and port not in {80, 443})
    ):
        return None

    hostname = parsed.hostname.rstrip(".").lower()
    if not any(hostname == allowed or hostname.endswith(f".{allowed}") for allowed in ATS_POSTING_HOSTS):
        return None

    netloc = hostname
    if port is not None and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"

    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS
        ),
        doseq=True,
    )
    return urlunsplit(
        (parsed.scheme.lower(), netloc, parsed.path.rstrip("/") or "/", query, "")
    )


def _provider_text(value: Any, *, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text[:limit] or None


def _company_from_ats_url(url: str) -> str | None:
    """Extract an employer slug only where the ATS URL defines that segment."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    slug: str | None = None
    if host in {"jobs.lever.co", "boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.ashbyhq.com"}:
        slug = parts[0] if parts else None
    elif host == "apply.workable.com":
        slug = parts[1] if len(parts) > 1 and parts[0].lower() == "j" else None
    if not slug or slug.lower() in {"jobs", "job", "careers", "apply"}:
        return None
    words = re.sub(r"[-_]+", " ", slug).strip()
    return words.title() if words else None


def _title_and_company(raw_title: Any, url: str) -> tuple[str | None, str | None]:
    title = _provider_text(raw_title, limit=180)
    company = _company_from_ats_url(url)
    if not title:
        return None, company

    # "Role at Employer" is provider-supplied evidence. Split it without
    # inventing either side; ATS URL evidence remains preferred for employer.
    match = re.match(r"^(.+?)\s+at\s+(.+)$", title, flags=re.IGNORECASE)
    if match:
        title = _provider_text(match.group(1), limit=180)
        company = company or _provider_text(match.group(2), limit=120)
    return title, company


def _remote_policy(title: str | None, snippet: str | None) -> str:
    evidence = f"{title or ''} {snippet or ''}"
    return "remote" if re.search(r"\b(remote|work from home|wfh)\b", evidence, re.IGNORECASE) else "unknown"


def _listing_quality(*, title: str | None, company: str | None, snippet: str | None) -> str:
    present = sum(bool(value) for value in (title, company, snippet))
    return "complete" if present == 3 else "partial" if present else "minimal"


def _to_company(row: dict[str, Any], *, provider: str, observed_at: str) -> HiringCompany | None:
    canonical_url = canonical_job_url(str(row.get("url") or ""))
    if not canonical_url:
        return None

    title, company = _title_and_company(row.get("title"), canonical_url)
    snippets = row.get("highlights") if isinstance(row.get("highlights"), list) else []
    raw_snippet = (
        row.get("content")
        or row.get("summary")
        or row.get("text")
        or " ".join(value for value in snippets if isinstance(value, str))
    )
    snippet = _provider_text(raw_snippet, limit=500)
    remote_policy = _remote_policy(title, snippet)
    quality = _listing_quality(title=title, company=company, snippet=snippet)
    origin = "provider_snippet" if snippet else "unavailable"
    homepage = f"{urlsplit(canonical_url).scheme}://{urlsplit(canonical_url).netloc}"

    posting = PublicJobPosting(
        url=canonical_url,
        title=title,
        snippet=snippet,
        company=company,
        source=provider,
        observed_at=observed_at,
        description_origin=origin,
        remote_policy=remote_policy,
        listing_data_quality=quality,
    )
    return HiringCompany(
        company_name=company,
        homepage_url=homepage,
        job_title=title,
        job_url=canonical_url,
        job_source=provider,
        blurb=snippet,
        job_posting=posting,
        observed_at=observed_at,
        description_origin=origin,
        remote_policy=remote_policy,
        listing_data_quality=quality,
    )


def _merge_provider_rows(
    rows: list[dict[str, Any]], *, provider: str, observed_at: str, seen: set[str]
) -> list[HiringCompany]:
    companies: list[HiringCompany] = []
    for row in rows:
        company = _to_company(row, provider=provider, observed_at=observed_at)
        if company is None or company.job_url in seen:
            continue
        seen.add(company.job_url)
        companies.append(company)
    return companies


async def _discover(role: str, city: str, *, limit: int) -> list[HiringCompany]:
    query = f'"{role}" "{city}" job opening'
    domains = sorted(ATS_POSTING_HOSTS)
    observed_at = datetime.now(timezone.utc).isoformat()
    seen: set[str] = set()
    companies: list[HiringCompany] = []
    tavily_failed = False
    exa_failed = False

    try:
        tavily_rows = await tavily_search(
            query,
            num_results=min(20, max(limit, 8)),
            search_depth="basic",
            include_domains=domains,
            include_raw_content=False,
        )
    except Exception:
        tavily_failed = True
        tavily_rows = []
    companies.extend(
        _merge_provider_rows(tavily_rows, provider="Tavily", observed_at=observed_at, seen=seen)
    )

    # Exa is the secondary discovery provider. It supplements sparse Tavily
    # results, but never changes or scores Tavily rows.
    if len(companies) < limit:
        try:
            exa_rows = await exa_search(
                query,
                include_domains=domains,
                num_results=min(20, max(limit, 8)),
                want_text=False,
                want_highlights=True,
            )
        except Exception:
            exa_failed = True
            exa_rows = []
        companies.extend(
            _merge_provider_rows(exa_rows, provider="Exa", observed_at=observed_at, seen=seen)
        )

    if not companies and tavily_failed and exa_failed:
        raise ProviderUnavailable("Job discovery providers are unavailable")
    return companies[:limit]


async def run_rag_company_search(
    run_id: str,
    city: str,
    role: str,
    resume_token: str | None,
    emit: Callable[[TimelineEvent], Awaitable[None]],
    multi_role: bool = False,
    depth: str = "standard",
    filters: dict[str, Any] | None = None,
    offset: int = 0,
    limit: int = 5,
    memory_store: Any = None,
    additional_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Run one anonymous role/location discovery without personal data."""
    del multi_role, filters, additional_roles
    if resume_token is not None:
        raise ValueError("Anonymous discovery does not accept resume data")

    memory = memory_store if memory_store is not None else Memory()
    result_limit = DEPTH_LIMITS.get(depth, DEPTH_LIMITS["standard"])
    await emit(
        TimelineEvent(
            run_id=run_id,
            agent="Search",
            message="Searching source listings",
            stage="discovery",
        )
    )
    companies = await _discover(role, city, limit=result_limit)
    await emit(
        TimelineEvent(
            run_id=run_id,
            agent="Search",
            message="Preparing returned listings",
            stage="normalization",
        )
    )

    document = RAGDoc(
        run_id=run_id,
        role=role,
        location=city,
        depth=depth,
        companies=companies,
        total=len(companies),
        pagination={
            "offset": offset,
            "limit": limit,
            "total": len(companies),
            "has_more": offset + limit < len(companies),
        },
    )
    serialized = document.model_dump()
    memory.set(f"ragdoc:{run_id}", serialized)
    return {
        "run_id": run_id,
        "role": role,
        "city": city,
        "companies": [company.model_dump() for company in companies[offset : offset + limit]],
        "pagination": document.pagination,
    }


async def get_rag_results(
    run_id: str,
    offset: int = 0,
    limit: int = 5,
    memory_store: Any = None,
) -> RAGDoc:
    """Return a source-order page from the stored discovery document."""
    memory = memory_store if memory_store is not None else Memory()
    raw = memory.get(f"ragdoc:{run_id}")
    if raw is None:
        raise ValueError(f"No RAGDoc found for run_id={run_id}")
    document = raw if isinstance(raw, RAGDoc) else RAGDoc(**raw)
    page = document.companies[offset : offset + limit]
    return document.model_copy(
        update={
            "companies": page,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": document.total,
                "has_more": offset + limit < document.total,
            },
        }
    )


def is_valid_company_name(name: str | None) -> bool:
    """Compatibility helper for inactive legacy discovery code."""
    normalized = (name or "").strip()
    return len(normalized) >= 2 and normalized.lower() not in {
        "jobs",
        "careers",
        "hiring",
        "lever",
        "greenhouse",
        "ashby",
        "workday",
    }
