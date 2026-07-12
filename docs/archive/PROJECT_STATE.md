# Project State

Last updated: 2026-05-03

## How to read this document

Skim **§1–2** for product shape and deployment topology; **§4** for the exact request flow through UI → FastAPI → memory; **§6** as a route catalog; **§7** for known sharp edges.

## 1) What this project is

This repository is an **AI career hub** with two primary product flows:

1. **Job discovery** (ATS-aware search, ranking, SSE timeline, paginated results) plus **resume-aware fit signals** on job cards (**FastAPI** + **Vite React**).
2. **Resume tailoring** (**Supabase Edge Functions** for parse/tailor/DOCX) plus backend **PDF template** export.

It also ships supporting surfaces:

- Curated **AI resource** library with filters (`GET /api/v1/resources` and related routes).
- **Learning path** generation (stored in SQLite when generated via API).
- **Skill gap** analysis with resource recommendations.
- **Application** tracking (SQLite).

Strategic positioning (portfolio / roadmap) is captured separately in repo-level planning docs (e.g. Agentception 2.0 narrative); **this file describes the codebase as wired today**.

## 2) Runtime architecture

- **Frontend:** `ui/` — Vite + React + TypeScript, React Router, TanStack Query, theme (light/dark/system) via `ThemeProvider`.
- **Backend API:** `server/app.py` (FastAPI, async).
- **Local DB:** `data/agentception.db` — SQLite (`server/memory/sql_store.py`).
- **In-memory runtime state:** `server/memory/state_store.py` — RAG payloads, timelines, transient caches per `run_id`.
- **Optional cache:** Redis (`server/memory/redis_cache.py`) with **in-memory fallback** if Redis is unreachable.
- **External APIs / services** (typical integrations):
  - Tavily, Exa (search)
  - OpenAI / DeepSeek / Voyage (LLM + embeddings — see agents and `rag/match`)
  - Google Maps (geocoding in job/RAG pipeline)
  - Supabase (resume tailoring edge functions + client in `ui/src/lib/supabase.ts`)

### Default local ports

| Service  | URL                     |
|---------|--------------------------|
| Backend | `http://localhost:8000`  |
| Frontend| `http://localhost:8080`  |

Frontend dev proxy: `ui/vite.config.ts` proxies **`/api` → backend** so routes like `/api/templates` resolve on `:8000`.

### Frontend environment

- `VITE_BACKEND_URL` overrides the API base URL in `ui/src/lib/api.ts` (default `http://localhost:8000`).

## 3) Current structure (high-signal map)

```text
Agentception - Copy/
  server/
    app.py                 # FastAPI routes, SSE, orchestration
    schemas.py             # Pydantic models (RAG, learning paths, timelines, ...)
    learning_path_service.py
    resources_library.py
    db.py                  # SQLAlchemy models (alongside sqlite_store patterns)
    agents/                # RAG, job extract, writer, skill gaps, matchers, ...
    tools/                 # search, resume, PDF, JD fetch, geocode, ...
    memory/                # state_store, sql_store, redis_cache
    rag/                   # roles, embeddings/cosine helpers, discovery helpers
    templates/             # resume PDF templates
    alembic/               # migrations (alongside SQLite bootstrap in sql_store)
    tests/
  ui/
    src/
      App.tsx              # Routes + QueryClient + theme + toast providers
      main.tsx             # Mount + optional service worker
      pages/               # Index, TailorResume, Dashboard, Resources, ...
      components/          # Search, Timeline, JobCard, layouts, ui/*
      hooks/
      lib/                 # api.ts (FastAPI), supabase.ts, jobCardNormalization.ts
    vite.config.ts
    public/sw.js           # Service worker (best-effort register in main.tsx)
    supabase/migrations/   # Example SQL migrations (resume-related)
  ui/temp-frontend/        # Secondary Vite tree (sandbox / stale duplicate — not primary app path)
  data/
    agentception.db
    ai_resources.json
    seeds/roles.yaml
    uploads/
  docs/
    architecture.png
    architecture.mmd
    job-search-engineering.md
    job-search-flow-explained.md
  start.ps1
  start-backend.ps1
  start-frontend.ps1
  requirements.txt
  pyproject.toml
```

## 4) End-to-end workflows

### 4.1 Job search workflow (home / `pages/Index.tsx`)

1. User enters location, role, optional filters via `components/SearchForm.tsx`; optional resume upload uses `uploadResume()` → `POST /upload/resume` (`server/tools/resume_store.py`).
2. Search kickoff: `searchCompanies()` → `POST /rag/companies`; response includes **`run_id`**; heavy work runs in a **background task**.
3. **RAG pipeline** (`server/agents/rag_companies.py` → `run_rag_company_search()`):
   - Role profiles from `server/rag/roles.py`.
   - Search layer: `server/tools/search_router.py`, `tavily_search.py`, `exa_search.py`.
   - Job extraction / cleaning: `server/agents/job_search.py`, trust / ATS heuristics in `server/agents/trust_scorer.py`.
   - Retrieval / abstraction: **`server/agents/match.py`** (`smart_search`, `SearchHit`); semantic helpers from **`server/rag/match.py`** (`_embed`, `_cos` via Voyage) used where embeddings are needed (e.g. RAG aggregator + resume matching).
   - Resume-aware scoring / gaps: `server/tools/resume_job_matcher.py` (hybrid match + gap hints surfaced on cards).
   - Final ranked doc keyed as **`ragdoc:{run_id}`** (also pagination metadata on the stored document).
   - Auxiliary cache **`loadmore:{run_id}`** may be populated for legacy/experimental **`POST /rag/companies/load-more`** consumers.
4. **Live timeline:** `components/Timeline.tsx` → `createTimelineStream()` → **`GET /timeline/{run_id}`** (SSE).
5. **Results:**
   - `getResults(runId, offset, limit)` → **`GET /results/{run_id}?offset=&limit=`** — authoritative pagination over the cached RAG document (no new search calls).
   - **Polling fallback:** `Index.tsx` polls `getResults` every few seconds early in a run so partial results appear if the timeline alone is insufficient.
   - Normalization + sorting: `lib/jobCardNormalization.ts` → **`components/JobCard.tsx`**.
6. **Per-card UX (current):**
   - When a resume token exists and the backend attaches scores, **`MatchScoreBadge`** and **`GapReport`** (missing skills) render on the card.
   - **`TailorJobButton`** navigates to `/tailor-resume` with **router state** (`jobUrl`, `jobSnippet`, `jobTitle`, `company`, optional **`resumeId`** from Supabase) so the tailor wizard can skip or prefill steps.
7. **Outreach / emails:** Backend still supports **`POST /writer/outreach`** (`writer_outreach.py`), enrichment via **`focused_research_agent.py`**, artifacts under **`artifacts:{run_id}`**; **`GET /results/{run_id}`** merges valid emails into the payload when present. The **home page no longer emphasizes a unified outreach/email panel** (“emails removed from unified experience” in `Index.tsx`); **`generateEmails()`** remains in `lib/api.ts` for callers that need it. **`components/EmailCard.tsx`** exists for email UI reuse but is **not** wired into `Index.tsx` currently.

### 4.2 Expanding roles or cached batches (backend-first)

- **`POST /rag/companies/load-more-roles`**: expands related role variants (bounded total roles), continues search in background. **`loadMoreRoles()`** exists in **`ui/src/lib/api.ts`**; the **home page UI for “more roles” was removed** — call from another client/page if needed.
- **`POST /rag/companies/load-more`**: returns slices from **`loadmore:{run_id}`** cache. Primary UI pagination today uses **`GET /results`** offsets instead.

### 4.3 Resume tailoring workflow (`/tailor-resume`)

1. **`pages/TailorResume.tsx`** — multi-step wizard (upload → JD → tailor → download).
2. Parse resume / JD via **`ui/src/lib/supabase.ts`** (Edge Functions: `parse-resume`, `parse-job-description`).
3. Tailor via **`tailorResume()`** (Edge Function `tailor-resume`).
4. If user arrived from a job card with **`resumeId`**, UI can **start at step 2**; **`prefilledJobText`** can come from **`jobSnippet`**.
5. Export:
   - DOCX via Supabase **`generate-docx`**.
   - PDF via **`GET /api/templates`** / **`POST /api/generate-pdf`** (proxied `/api`), implemented in **`server/tools/resume_pdf_generator.py`**; UI pieces include **`ResumeDownload.tsx`**, **`TemplateSelector.tsx`**, **`TailoredResumeView.tsx`**.

**Deprecated / alternate path:** **`POST /api/tailor-resume-from-job`** and **`tailorResumeFromJob()`** in `api.ts` are marked deprecated in favor of the Supabase-first flow (`TailorJobButton` commentary).

### 4.4 Job description text helper

- **`fetchJobDescriptionText()`** in `lib/api.ts` → **`POST /api/fetch-job-description`** pulls JD text when possible, with snippet fallback (`server/tools/job_description_fetcher.py`).

### 4.5 AI resources, learning paths, skill gaps, applications

| Surface | UI | Backend |
|---------|-----|---------|
| Resources | `pages/Resources.tsx` | Listing + filters: **`GET /api/v1/resources`**; **`GET /api/v1/resources/{id}`**, **`.../categories`**, **`.../featured`**; bookmark/upvote **`POST`** routes exist (**`fetchResources`** is the primary UI caller today — bookmark/upvote not exposed on the Resources page). |
| Learning paths | `pages/LearningPaths.tsx` (`?topic=` supported) | **`POST /api/v1/learning-paths/generate`**; **`GET /api/v1/learning-paths/{path_id}`** and **`POST .../progress`** persist via `sql_store` — UI currently **generates only** via `createLearningPath()`. |
| Skill gaps | `pages/SkillGaps.tsx` | **`POST /api/v1/skill-gaps/analyze`** → `skill_gap_agent.py`. |
| Dashboard | `pages/Dashboard.tsx` | **`GET /api/v1/recommendations`**. |
| Applications | `pages/Applications.tsx` | **`POST /api/v1/applications`**, **`GET /api/v1/applications`**; **`PUT /api/v1/applications/{id}`** + **`updateApplicationStatus()`** in `api.ts` — **applications UI currently saves listings but does not call PUT** from the page. |

### 4.6 Match score API

- **`POST /api/compute-match-score`** — backend helper for structured resume-vs-job scoring (`resume_job_matcher`); **not currently invoked by the surveyed home/tailor pages** — useful for tooling or future UI.

### 4.7 Collab websocket (experimental)

- **`GET /ws/collab`** — WebSocket endpoint registered twice in `app.py` (see §7 duplicate routes).

---

## Important runtime keys (memory)

| Key | Purpose |
|-----|---------|
| `ragdoc:{run_id}` | Ranked jobs/companies payload + pagination totals |
| `artifacts:{run_id}` | Outreach emails and other writer artifacts |
| `error:{run_id}` | Failure diagnostics |
| `loadmore:{run_id}` | Optional batch cache for `POST /rag/companies/load-more` |

## 5) File responsibilities and connections

### 5.1 Top-level files

- `README.md`: high-level onboarding (note: some bullets still say Next.js historically; **`ui/` is Vite**).
- `PROJECT_DOCUMENTATION.md`: longer-form technical notes.
- `start.ps1` / `start-backend.ps1` / `start-frontend.ps1`: local dev orchestration (Windows-first).
- `requirements.txt`, `pyproject.toml`: Python dependencies.
- `.env`: API keys and feature flags.
- `check_mock_mode.py` / `enable_mock_mode.py`: mock search mode helpers.
- `test_openai_key.py`: credential smoke test.

### 5.2 Backend core (`server/`)

- `app.py`: routes (including debug/test), CORS, SQLite init, SSE timeline wiring.
- `schemas.py`: shared Pydantic types.
- `learning_path_service.py`: structured learning-path generation.
- `resources_library.py`: seed AI resources into SQLite from `data/ai_resources.json`.
- `db.py`: ORM definitions complementing sqlite access patterns.

### 5.3 Backend agents (`server/agents/`)

**Primary pipeline**

- `rag_companies.py` — orchestrator, caching, aggregation, pagination backing `get_rag_results`.
- `job_search.py` — listings, ATS patterns, listing-page second-hop helpers, **`get_optimal_sites_for_role`**, geographic phrasing (`parse_location`, etc.).
- `match.py` — **`smart_search`** / **`SearchHit`** abstraction (wired from `rag_companies` and `job_search`).
- `trust_scorer.py` — snippet/job trust and cleanup.
- `writer_outreach.py` — incremental outreach + artifact writes.
- `focused_research_agent.py` — targeted company intelligence for personalization.
- `semantic_matcher.py` — text overlap semantics for **`/api/v1/jobs/match`**.
- `skill_gap_agent.py` — skill gap analysis payloads for API.

**Secondary / auxiliary**

- `enhanced_research_agent.py`, Apify/fast scrapers, LangGraph orchestrator experiments, normalizers, test harnesses (`test_llm_extraction.py`, etc.) — not all are on the default user-click path.

### 5.4 Backend tools (`server/tools/`)

- `resume_store.py` — resume text + insight extraction for search/upload.
- `resume_job_matcher.py` — hybrid scoring + embeddings reuse (`rag.match`).
- `job_description_fetcher.py` — `/api/fetch-job-description`.
- `search_router.py`, `tavily_search.py`, `exa_search.py` — search providers.
- `geocode.py` — Maps helper.
- `resume_pdf_generator.py` — `/api/templates`, `/api/generate-pdf`.
- `http_fetch.py` — shared HTTP helpers.

### 5.5 Memory + persistence

- `state_store.py` — KV + timeline buses.
- `sql_store.py` — resources (+ bookmarks/upvotes tables), applications, saved learning paths, progress rows.
- `redis_cache.py` — optional Redis acceleration for search subsets with safe fallback.

### 5.6 RAG support (`server/rag/`)

- `roles.py` — YAML-driven role profiles / keywords for matching.
- `match.py` — **embedding helpers** (`_embed` / cosine) reused by matchers and hybrid resume scoring.

### 5.7 Templates (`server/templates/resume_templates/`)

- `template_base.py`, `classic_serif.py`, `latex_modern.py`, `modern_minimal.py` — consumed by `resume_pdf_generator.py`.

### 5.8 Frontend (`ui/src/`)

- `App.tsx` — routes: `/`, `/dashboard`, `/resources`, `/learning-paths`, `/applications`, `/skill-gaps`, `/tailor-resume`, catch-all `*`.
- `lib/api.ts` — typed client for FastAPI + SSE timeline.
- `lib/supabase.ts` — Supabase + edge wrappers for tailor flow.

**Pages:** `Index`, `TailorResume`, `Dashboard`, `Resources`, `LearningPaths`, `SkillGaps`, `Applications`, `NotFound`.

**Notable components:** `SearchForm`, `Timeline`, `JobCard` (+ **`MatchScoreBadge`**, **`GapReport`**, **`TailorJobButton`**), tailor stack (`ResumeUpload`, `JobDescriptionInput`, **`TailoredResumeView`**, **`ResumeDownload`**, **`TemplateSelector`**), **`TopNav`**, `components/ui/*`, **`theme-provider`**, **`mode-toggle`**.

### 5.9 Frontend tooling

- `vite.config.ts` — port **8080**, **`lovable-tagger`** in dev mode, `@` → `src` alias.
- `public/sw.js` — service worker registration (non-fatal on failure).

## 6) API map (caller → route → backend hint)

| Method / path | Primary caller(s) | Backend |
|---------------|-------------------|---------|
| `POST /upload/resume` | `SearchForm.tsx` | `resume_store.py` |
| `POST /rag/companies` | `SearchForm.tsx` | `rag_companies.run_rag_company_search` |
| `GET /timeline/{run_id}` | `Timeline.tsx` | SSE timeline bus |
| `GET /results/{run_id}` | `Index.tsx` (`getResults`) | `get_rag_results` + artifact email merge |
| `POST /rag/companies/load-more` | _(no current UI)_ | Cached `loadmore:{run_id}` slices |
| `POST /rag/companies/load-more-roles` | `loadMoreRoles()` in `api.ts` _(unused by Index)_ | Extends roles + background search |
| `POST /writer/outreach` | `generateEmails()` available | `writer_outreach.py` |
| `POST /api/fetch-job-description` | `fetchJobDescriptionText()` | `job_description_fetcher.py` |
| `POST /api/tailor-resume-from-job` | Deprecated client helper | Alternate tailor path |
| `POST /api/compute-match-score` | _(no current UI)_ | `resume_job_matcher` |
| `GET /api/templates`, `POST /api/generate-pdf` | `ResumeDownload.tsx` → proxy | PDF templates |
| `GET /api/v1/resources` (+ subpaths) | `Resources.tsx`; `SkillGaps` recommendations | `sql_store` / library |
| `POST /api/v1/learning-paths/generate` | `LearningPaths.tsx` | `learning_path_service.py` |
| `GET /api/v1/learning-paths/{path_id}`, `POST .../progress` | _(API-ready; minimal UI)_ | `sql_store` |
| `POST /api/v1/skill-gaps/analyze` | `SkillGaps.tsx` | `skill_gap_agent.py` |
| `POST|GET /api/v1/applications`, `PUT .../{id}` | List/create used by `Applications.tsx` | `sql_store` |
| `GET /api/v1/recommendations` | `Dashboard.tsx` | Recommendation helper in `app.py` |
| `POST /api/v1/jobs/match` | _(API / tooling)_ | `semantic_matcher.py` |
| `POST /save/add`, `GET /save/list` | Saved items UX (if surfaced) | `sql_store` |
| Various `/debug/*`, `/health` | Ops / troubleshooting | Lightweight handlers |

Duplicate FastAPI registrations (maintenance hazard): **`/health`**, **`/debug/memory/{run_id}`**, **`POST /api/v1/jobs/match`**, **`/ws/collab`** appear **twice** in `server/app.py`.

## 7) Current operational notes

- **Primary happy path**: search → timeline → **`GET /results`** with offset pagination → job cards (+ optional tailor jump).
- **Redis**: Safe to omit locally; fallback cache prevents hard failures when Redis host is absent.
- **Google Maps**: Geocoding may return **`REQUEST_DENIED`** until billing / API enablement / key restrictions are fixed — affects location fidelity, not necessarily the rest of search.
- **Docker**: Still no checked-in **`Dockerfile` / `docker-compose.yml`** in this tree snapshot.
- **README drift**: Prefer this file + **`PROJECT_DOCUMENTATION.md`** for stack accuracy (Vite vs Next).
- **`ui/temp-frontend/`**: Treat as experimental duplicate unless you deliberately develop there.
