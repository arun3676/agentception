# Agentception

[![CI](https://github.com/arun3676/agentception/actions/workflows/ci.yml/badge.svg)](https://github.com/arun3676/agentception/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-165%20passing-brightgreen)
![skill%20extraction%20F1](https://img.shields.io/badge/skill%20extraction%20F1-0.535-yellow)
![match%20AUROC](https://img.shields.io/badge/match%20AUROC-0.702%20(p%3D0.017)-yellow)
![resume%20parsing](https://img.shields.io/badge/resume%20parsing-0.964-brightgreen)

**Job search that tells you what's missing, then teaches it to you.**

Upload a resume → live postings pulled straight from applicant tracking systems, ranked
against you → the exact skills you're short on, named → curated material to learn each
one, without leaving the page.

---

## The problem

Job boards show you listings and wish you luck. The number that actually matters —
*why am I not getting callbacks?* — is the one nobody tells you.

So this app is built around one claim: **it can name the specific skills standing
between you and a job, and hand you the material to close them.** That claim is only
worth anything if it's measured, which is what most of the engineering here is about.

## What it does

| | |
|---|---|
| **Parse** | Layout-aware resume parsing (Reducto), with a local fallback. Handles multi-column templates and tables. |
| **Search** | Live postings from Greenhouse / Lever / Ashby / Workable — direct apply-pages, not aggregator spam, filtered to the last 45 days. |
| **Price** | Real posted salary, pulled from the posting's Schema.org `baseSalary` or its pay range. Never estimated — if a company doesn't post pay, we show nothing. |
| **Match** | Hybrid keyword + semantic (Voyage embeddings) score, **calibrated** into `strong / possible / stretch`, with a plain-English "why". |
| **Gap** | The skills the posting wants that your resume doesn't evidence, matched against an O*NET-derived taxonomy. |
| **Teach** | Each gap opens curated videos / articles / courses / docs, scoped to the role and your level. |
| **Track** | Log applications and outcomes; callback rate is computed, not decorative. |

## Measured quality

Everything below is reproduced offline on every push by `pytest evals/ -m eval`
against a committed golden set of **69 real job descriptions** (1,239 labelled skills)
and **39 labelled resume↔job pairs**. Full method, and its limitations, in
**[docs/EVALS.md](docs/EVALS.md)**.

| Metric | Value | |
|---|---|---|
| Skill extraction — F1 | **0.535** | precision 0.728 · recall 0.422 |
| Match ranking — AUROC | **0.702** | permutation **p = 0.017** |
| Resume parsing (production) | **0.964** | name · email · employer · skills, across 14 layouts |
| Resume parsing (fallback) | 0.714 | the local path, published rather than hidden |
| Study relevance (LLM judge) | **0.950** | nightly, not on every push |

The AUROC is quoted **with its p-value** on purpose. The first version of this eval
scored a prettier 0.750 — but at n=14, p was 0.066 and a *random* scorer reached 0.771
at the 95th percentile. The number was inside the noise. Expanding the set produced a
lower score that actually means something. **A metric you can't distinguish from chance
is not a metric.**

### What building the evals found

Every one of these was invisible without measurement, and every one had shipped:

1. **The "hybrid" matcher was silently keyword-only.** `except: return 0.0` around the
   Voyage call turned rate-limit 429s into "these documents are unrelated". Fixing it
   moved **AUROC 0.60 → 0.75**.
2. **The gap chips were recommending you learn "equity" and "offers".** Matching ran
   against a ~40-character search snippet instead of the real job description, so the
   "missing skills" were leftover words from the ad. Now it reads the actual posting.
3. **The skill vocabulary was the whole problem.** 77 hardcoded keywords capped recall
   at **0.365** — it could not name a skill it had never heard of. A `recall_ceiling`
   metric made that visible instead of guessable; replacing the vocabulary took F1
   from 0.405 → **0.535**.
4. **Truncating job text to save tokens cost more than it saved** (AUROC 0.75 → 0.60):
   an ATS posting opens with mission and benefits, so the first 2.5k chars are the part
   that *doesn't* carry hiring signal.
5. **The callback-rate feature never worked.** It read `status`; the database column is
   `application_status`, so every application counted as "applied" and the rate was
   pinned at 0% forever.

## Engineering notes

**Nothing is fabricated.** No salary without a posted one, no match score when the
match couldn't be assessed (`unknown` is a real, displayed outcome), no trust score
invented for a dashboard. The previous version returned a hardcoded `5.0` whenever
scoring failed, which the UI rendered as though it meant something.

**Paid calls are snapshotted, not mocked.** The semantic matcher (Voyage) and the
production resume parser (Reducto) cost money, so their outputs are committed and
replayed. CI runs the *real* code paths against *real* model outputs — offline,
deterministic, free. A cache miss raises rather than degrading, because a degraded path
shows up as a fake model regression. (It did: a phantom AUROC of 0.438.)

**Cost is attributable.** Every LLM call goes through one router (DeepSeek primary,
OpenAI fallback) that records provider, model, tokens, dollars, latency and *purpose* —
so "what's expensive?" is a query, not a guess. `GET /api/v2/system/usage`.

**Batching matters more than it looks.** Scoring jobs one-by-one meant one embedding
request per job; Voyage rate-limited them and a search took minutes. Embedding the
resume and all jobs in a single call made the same search take **20 seconds**.

**Fallbacks are decisions, not accidents.** Silent degradation is the recurring theme of
every bug above, so failures are now logged, surfaced, and — where it matters — raised.

## Architecture

```
                 React + TypeScript (Vite, Tailwind, shadcn/ui)
                                   │
                                   ▼
                         FastAPI  ·  server/
   ┌───────────────┬───────────────┼───────────────┬────────────────┐
   ▼               ▼               ▼               ▼                ▼
 auth.py       rate_limit.py   routers/        agents/          tools/
 Supabase      token bucket    v1 · v2 ·       job search       llm_router (cost)
 JWKS          per client      study           RAG discovery    skill_extractor
                                               outreach         match_calibration
                                                                salary · reducto
   │                                                                │
   └──────────────► SQLite (runs · applications · llm_calls) ◄──────┘

  external:  Reducto (parse) · Tavily + Exa (search) · Voyage (embeddings)
             DeepSeek → OpenAI (LLM, routed) · Supabase (auth)
```

## Repository layout

```
agentception/               The product
  server/                     FastAPI: routers, agents, tools, memory
  evals/                      Quality metrics + committed golden set   ← the interesting part
  ui/                         React frontend
  scripts/                    Golden-set builders, taxonomy builder, calibration fit
landing/                   Static marketing page
docs/                      EVALS.md · ENGINEERING_ROADMAP.md
```

The resume eval runs on real PDFs, which are personal documents and are **not published**.
They don't need to be: the parses are snapshotted into `evals/golden/` with contact details
pseudonymised (`evals/pii.py`), so CI reproduces every number without them. The redaction is
applied to both sides of every comparison, so the measured accuracy is identical either way.

## Quick start

```bash
# Backend — http://localhost:8000
cd agentception
cp .env.example .env          # fill in your API keys
pip install -r requirements.txt
python -m uvicorn server.app:app --reload --port 8000

# Frontend — http://localhost:8080
cd agentception/ui && npm install && npm run dev

# Landing page — http://localhost:4321
cd landing && python -m http.server 4321
```

## Tests

```bash
cd agentception
pytest                       # 165 unit tests. No network, no API keys, no spend.
pytest evals/ -m eval        # quality metrics vs the golden set (offline)
pytest evals/ -m judge       # LLM-as-judge (costs money; nightly in CI)
cd ui && npm run lint && npm run build
```

The unit suite runs with **no API keys set** — if a test starts needing one, it belongs
in `evals/`. Rebuilding the golden set is documented in [docs/EVALS.md](docs/EVALS.md).

## What's still weak

Stated because a reviewer will find them anyway:

- **Skill labels are unreviewed LLM output** (69 rows, `reviewed: false`). The labeller
  and the system under test are independent mechanisms, so it isn't circular — but it's
  silver, not gold.
- **Resume parsing is one person** in 14 layouts. It measures layout robustness, not
  generalisation across writers.
- **Match labels are weak supervision** from the posting's title; a proxy for fit, not
  fit itself.
- **Recall is still 0.42.** The taxonomy raised the ceiling to 0.572; closing the rest
  needs semantic (embedding) skill matching, not just a gazetteer.
- SQLite on a single instance. Fine at this size, and the wrong answer at ten.

Roadmap: [docs/ENGINEERING_ROADMAP.md](docs/ENGINEERING_ROADMAP.md).
