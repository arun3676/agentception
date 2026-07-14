# Deployment and release safety

Agentception deploys manually after a reviewed pull request. Codex and CI do not
deploy, merge, or enter secret values.

## Current containment architecture

| Service | Root directory | Runtime |
|---|---|---|
| Vercel app | `agentception/ui` | Vite static build (`npm ci && npm run build`) |
| Railway API | `agentception` | FastAPI via Railpack and `railway.json` |
| Vercel landing | `landing` | Static files |

Both Vercel project roots set `git.deploymentEnabled` to `false`. Pushes and pull
requests must not create deployments; use an explicitly reviewed manual release.

The containment release supports public role/location discovery and the public
resource catalogue. Authentication, résumé upload, tailoring, saving, outcomes,
and personalized learning remain unavailable in the browser.

## Current environment contract

Vercel app:

```text
VITE_BACKEND_URL=https://<railway-api-host>
```

Railway API:

```text
APP_ENV=production
FRONTEND_ORIGINS=https://agentception.vercel.app
TAVILY_API_KEY=<platform secret>
EXA_API_KEY=<platform secret>
```

Railway uses the current `RAILPACK` builder, the `pyproject.toml`/`uv.lock`
dependency contract, and Python 3.11.15 from `runtime.txt`. Do not reintroduce a
Procfile, Nixpacks file, or a second Python dependency list.

`FRONTEND_ORIGINS` is a comma-separated list of exact origins. Wildcards,
credentials, paths, and attacker-created `*.vercel.app` origins are rejected.
Every authorized preview origin must be listed explicitly.

Production startup rejects `MOCK_SEARCH=true`, `RATE_LIMIT_DISABLED=true`,
`TAVILY_DISABLE_SSL_VERIFY=true`, `DEBUG_DISCOVERY=true`, and missing Tavily/Exa
keys. Those development flags default to false and must not be enabled on
Railway.

The audit found that the live Railway service was missing `TAVILY_API_KEY`; the
search release is blocked until an operator enters it in Railway's secret store.
Never paste a key into chat, a pull request, a screenshot, or a log.

The following names belong to later reviewed phases; the containment runtime does
not consume or enforce all of them yet:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
DATABASE_URL
MIGRATION_DATABASE_URL
PROVIDER_DAILY_BUDGET_USD
REDUCTO_API_KEY
VOYAGE_API_KEY
DEEPSEEK_API_KEY
OPENAI_API_KEY
```

Configuring a variable is not evidence that its feature is implemented. In
particular, scheduled paid judge evaluations remain disabled until
`PROVIDER_DAILY_BUDGET_USD` is enforced and reported by the application. The
manual judge workflow exposes only `DEEPSEEK_API_KEY`, and only to its paid test
step.

Health checks:

- `GET /health/live` proves that the API process is running and exposes no provider state.
- `GET /health/ready` returns 503 when the active application store cannot answer.
- Railway uses `/health/ready` from `railway.json`.

## Vercel security boundary

`agentception/ui/vercel.json` applies CSP, frame, content-type, referrer,
permissions, and HTTPS headers to the static app. The CSP permits the two Google
Fonts hosts used by `index.html`; it does not list Supabase or provider domains.

Vercel's static header configuration cannot substitute `VITE_BACKEND_URL` into a
header value. Until the stable Railway API origin is available in reviewed
deployment metadata, `connect-src` therefore permits HTTPS by scheme. Record the
real API origin and replace that scheme source with the exact origin before
calling the CSP least-privilege. Do not guess a Railway hostname or use a
`*.up.railway.app` wildcard.

## CI release gates

CI installs Python with `uv sync --locked` after `uv lock --check`; an outdated
lock fails instead of being ignored. It also runs backend tests, offline evals,
frontend tests/typecheck/lint/build, the bundle budget, deterministic local
Playwright tests, privacy and secret scans, Bandit, strict production-lock
dependency audits, and production CycloneDX SBOM exports for Python and npm.
Normal CI receives no provider keys.

## Manual containment release

1. Merge the reviewed containment PR only after privacy, backend, frontend, eval,
   dependency, and synthetic browser gates pass.
2. Complete the coordinated history rewrite in
   [PRIVACY_HISTORY_REWRITE.md](PRIVACY_HISTORY_REWRITE.md) before normal merges resume.
3. Enter or rotate secrets in the platform stores without exposing their values.
4. Confirm the Railway project uses Railpack, the reviewed root directory, and
   Python 3.11.15; deploy Railway and wait for strict readiness.
5. Deploy the Vercel UI, then the static landing project if it changed.
6. Run the synthetic desktop/mobile smoke test and verify console and network logs.
7. Roll back application revisions independently if the smoke test fails.

No résumé is uploaded during this containment smoke test because that production
surface is intentionally absent.

## Postgres migration gate for later releases

Database work is blocked until read-only access points at the Agentception
Supabase project. The currently connected Cork project is unrelated and must not
be inspected or changed.

Before any production-facing schema change:

1. Inventory the live schema, grants, RLS, buckets, migration history, backups,
   and connection mode without mutating them.
2. Classify each migration as additive, backfill, or destructive/locking.
3. Dry-run against a Supabase branch or disposable copy with lock and statement
   timeouts, ownership/RLS tests, row-count checks, and advisor checks.
4. Use `MIGRATION_DATABASE_URL` with direct connectivity or the session pooler.
   Never run migrations through transaction-pooler port 6543.
5. Use expand/backfill/contract across separate releases for incompatible changes.
6. Verify backup/PITR and write a forward-fix plan before the migration job runs.
7. Deploy manually in this order: migration job, Railway worker, Railway API and
   readiness, Vercel, synthetic smoke test.

The current SQLite/process-local implementation is not durable production
persistence. Do not claim otherwise, attach a new production database, or run a
migration until the correct project inventory is available.

## Configuration references

- [Railway configuration as code](https://docs.railway.com/config-as-code/reference)
- [Railpack Python and uv detection](https://railpack.com/languages/python/)
- [Vercel `vercel.json` reference](https://vercel.com/docs/project-configuration/vercel-json)
- [uv lock checking and locked sync](https://docs.astral.sh/uv/concepts/projects/sync/)
