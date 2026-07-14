# Current anonymous job-search flow

This document describes the containment implementation, not the proposed
Postgres worker architecture. The active public workflow is role/location
discovery only. It does not accept a resume, infer a user identity, tailor a
document, or create an application record.

## Browser request

The user supplies a supported role and a location. The Vite UI sends this public
request to FastAPI:

```http
POST /rag/companies
Content-Type: application/json

{
  "role": "Backend Engineer",
  "city": "Austin, TX",
  "depth": "standard"
}
```

FastAPI validates the fields, applies the current launch limiter, creates an
opaque `run_id`, and returns `202 Accepted`. That identifier is workflow state,
not an authentication or ownership token.

## Search execution

FastAPI currently starts the search as an in-process background task. Tavily is
the required primary discovery provider and Exa supports secondary discovery and
research. A missing required provider or transport failure must produce an
explicit failed state; it must not be converted into invented listings or a
successful empty result.

Provider hits pass through an evidence-only normalizer. It accepts only supported
public ATS URLs, keeps provider titles and excerpts as provider data, leaves
unknown location and description fields unavailable, and deduplicates only by a
canonical job URL. Tavily rows retain source order; Exa supplements a sparse
primary result without rescoring it. Transport failure from both providers is a
failed search, not a successful empty result.

The response exposes the provider, observation time, remote-policy status,
description origin, and listing-data quality. It strips retired resume-match,
trust, percentile, probability, and internal ranking fields. Source presence does
not prove that a listing is open, complete, local, or endorsed.

## Progress and results

The current UI uses:

```text
GET /timeline/{run_id}       server-sent progress events
GET /results/{run_id}        paginated result document
```

The terminal event is `succeeded` or `failed`; browser timers are not progress
evidence. The UI handles an error, timeout, or interrupted event stream as a
failure/degraded state rather than assuming completion.

Timeline delivery and background execution are still process-local. Some search
documents are also written to a local SQLite store. This design is not durable
across Railway restarts, multiple web replicas, or a failed worker. It does not
support leased jobs, ordered event replay with `Last-Event-ID`, or a separate
worker service yet.

## Public resource catalogue

The separate public study catalogue uses:

```text
GET /api/v1/study/pillars
GET /api/v1/resources
GET /api/v1/resources/{resource_id}
```

Catalogue inclusion is not a ranking, recommendation guarantee, or proof of
quality. Links are restricted to safe web schemes in the UI.

## Deliberately absent contracts

Resume upload, fit assessment, tailoring, exports, saved applications, private
learning plans, outreach, debug/provider health, usage, and experimental beta
routes are not production capabilities in this release. Their future `/api/v1`
contracts require authenticated ownership, private storage, retention/deletion,
and the reviewed Postgres workflow foundation first.

## Acceptance boundary

The deterministic Playwright suite mocks provider responses and proves browser
contract and state handling without spending provider credits. It does not prove
live provider quality. A release also requires a separately authorized synthetic
staging smoke test, provider-degradation checks, and restart recovery after the
durable worker architecture exists.
