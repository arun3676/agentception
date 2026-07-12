# Deployment

Three pieces, deployed separately:

| Piece | Host | Source |
|---|---|---|
| **API** | Railway | `agentception/` (FastAPI) |
| **App** | Vercel | `agentception/ui/` (Vite → static) |
| **Landing** | Vercel (2nd project) | `landing/` (static HTML) |

Both hosts are **already connected** to this repo. The monorepo restructure moved the
app from `./` to `./agentception/`, so each host needs its root directory updated once —
that is the whole migration.

---

## 1. Vercel — update the root directory (required, or the build fails)

The app build currently fails with:

```
The specified Root Directory "ui" does not exist.
```

Fix, in **Vercel → project `agentception` → Settings → Build & Deployment**:

| Setting | Old | **New** |
|---|---|---|
| Root Directory | `ui` | **`agentception/ui`** |

Framework preset **Vite**, build `npm run build`, output `dist`, install `npm ci` — all
already correct and also declared in `agentception/ui/vercel.json`.

### Environment variables (Vercel → Settings → Environment Variables)

Set these for **Production** *and* **Preview**. Anything the browser reads must be
prefixed `VITE_` — Vite inlines them at build time, so **changing one requires a
redeploy**, not just a restart.

| Variable | Value | Why |
|---|---|---|
| `VITE_BACKEND_URL` | `https://agentception1809.up.railway.app` | Without it the app calls its own origin and every request 404s. |
| `VITE_SUPABASE_URL` | your Supabase project URL | Auth. |
| `VITE_SUPABASE_ANON_KEY` | Supabase **anon/publishable** key | Auth. Safe to expose — it is designed to be public and is protected by row-level security. |

> **Never put a service-role key, or any of the API keys below, in a `VITE_*`
> variable.** They are compiled into the JavaScript bundle and readable by anyone who
> opens devtools.

`VITE_SUPABASE_DEFAULT_USER_ID` is read by `supabase.ts` and `VerdictLoop.tsx` but is a
local-development convenience. Leave it unset in production.

## 2. Landing page — a second Vercel project

`landing/` is plain HTML/CSS/JS with no build step.

- **New Project** → same repo
- **Root Directory:** `landing`
- **Framework preset:** Other
- **Build command:** none · **Output directory:** `.`
- No environment variables.

Point your apex domain at this one and the app at `app.<yourdomain>`.

## 3. Railway — update the root directory

Railway is **live** (`/health` returns 200), but it is building from the old layout.
In **Railway → service → Settings**:

| Setting | Value |
|---|---|
| Root Directory | **`agentception`** |
| Start command | `python -m uvicorn server.app:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

`railway.json`, `nixpacks.toml`, `Procfile` and `runtime.txt` (Python 3.11) already
declare this — they just moved down a directory with the app.

### Environment variables (Railway → Variables)

**Required — the product is broken without these:**

| Variable | Used by | What breaks without it |
|---|---|---|
| `TAVILY_API_KEY` | job search (primary) | No job results. |
| `EXA_API_KEY` | job search (ATS) + study material | No ATS postings, no study results. |
| `VOYAGE_API_KEY` | `rag/match.py` | Semantic matching. The matcher falls back to keyword-only — **this is the bug that shipped**; it now fails loudly instead of silently scoring 0.0. |
| `DEEPSEEK_API_KEY` | `llm_router.py` (primary LLM) | Gap analysis, summaries, outreach. |

**Strongly recommended:**

| Variable | Used by | Notes |
|---|---|---|
| `REDUCTO_API_KEY` | resume parsing | Falls back to the local regex parser — measurably worse (**0.964 → 0.714** field accuracy). |
| `OPENAI_API_KEY` | `llm_router.py` (fallback) | The second provider in the route. Your current key is out of quota; DeepSeek carries the load, but with no fallback a DeepSeek outage takes gap analysis down. |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | `server/auth.py` | JWT verification. Anonymous use still works without them; signed-in features don't. |

**Optional — safe to leave unset:**

`REDIS_URL` (cache; SQLite is used otherwise) · `AGENTCEPTION_DB` (SQLite path) ·
`SUPABASE_SERVICE_ROLE_KEY` (migrations + keep-alive only — **never expose to the
frontend**) · `RATE_LIMIT_DISABLED` (leave unset, i.e. limits on) · `PERPLEXITY_API_KEY`,
`APIFY_TOKEN`, `KIMI_API_KEY`, `GOOGLE_MAPS_KEY` (legacy paths, not in the main flow).

**Do NOT carry these over — nothing reads them.** They are leftovers from an earlier
version of this project and are dead weight in a secrets store:

```
CHEAP_MODEL           COHERE_API_KEY        EVENTBRITE_API_KEY     EVENTBRITE_CLIENT_SECRET
EVENTBRITE_PRIVATE_TOKEN   EVENTBRITE_PUBLIC_TOKEN   EVENTBRITE_TOKEN
FOURSQUARE_API_KEY    FOURSQUARE_CLIENT_ID  FOURSQUARE_CLIENT_SECRET
RAILWAY_URL           RERANK_MODEL          STRONG_MODEL
SUPABASE_PUBLISHABLE_KEY   SUPABASE_SECRET_API_KEY
```

## 4. CORS — add the Vercel domains

The API must allow the browser origin. In `agentception/server/app.py`, the allowed
origins list currently covers localhost and `*.vercel.app`. If you attach a custom
domain, add it there or requests will fail with an opaque CORS error that looks like
the backend is down.

---

## Known production gaps

**`/health` reports `"db": "unavailable"` in production right now.** That field pings
**Supabase**, not the SQLite app database — so it means Railway either has no
`SUPABASE_URL` / `SUPABASE_ANON_KEY` set, or they're wrong. Setting them is step 2
below. (The handler swallows the real reason in a bare `except: pass`, so the log won't
tell you which; worth fixing, it's the same silent-failure pattern the evals were built
to catch.)

**Railway's filesystem is ephemeral.** SQLite at `data/agentception.db` is wiped on
every redeploy — saved runs, applications and cost records do not survive. For a
portfolio demo that's arguably fine; for real users it isn't. Fix by attaching a
**Railway volume** and pointing `AGENTCEPTION_DB` at it, or by moving to Supabase
Postgres (`DATABASE_URL` is already read by `server/db.py`).

**Supabase auto-pauses after 7 days idle.** `.github/workflows/keep-alive.yml` pings
`/health` every 6 hours to prevent it.

---

## Order of operations

1. Merge the PR.
2. Railway → Root Directory `agentception`, add the four required keys → redeploy → check `/health`.
3. Vercel (app) → Root Directory `agentception/ui`, add the three `VITE_*` vars → redeploy.
4. Vercel (landing) → new project, Root Directory `landing`.
5. Open the app, upload a resume, run a search. If jobs return with salary and a match
   band, all four required keys are working.
