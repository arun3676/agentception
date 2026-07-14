# Agentception application

This directory contains the FastAPI backend, Vite frontend, offline evaluations,
and deployment configuration. The repository-level [README](../README.md)
describes the current product posture and evidence rules.

## Active surface

The containment release supports anonymous role/location discovery and public
study resources. Resume upload, tailoring, saved personal data, outreach, and
experimental score/profile routes are intentionally unavailable until their
authenticated ownership and persistence contracts are rebuilt.

## Start locally

```powershell
python -m pip install uv==0.11.28
uv lock --check
uv sync --locked --group dev
Copy-Item .env.example .env
uv run uvicorn server.app:app --reload --port 8000
```

```powershell
npm --prefix ui ci
Copy-Item ui\.env.example ui\.env.local
npm --prefix ui run dev
```

The frontend runs on `http://localhost:8080` and the backend on
`http://localhost:8000`.

## Checks

```powershell
uv run --locked python -m compileall server
uv run --locked python -m pytest -q --strict-markers
uv run --locked python -m pytest evals -m eval -q --strict-markers
uv run --locked python scripts/check_repository_privacy.py
npm --prefix ui test
npm --prefix ui exec tsc -- -b
npm --prefix ui run lint
npm --prefix ui run build
npm --prefix ui run check:bundle
```

No normal test may require a paid provider or a real resume. Generate the
temporary synthetic PDF when a browser test needs an upload:

```powershell
uv run --locked python scripts/build_synthetic_resume_fixture.py --output tmp/pdfs/synthetic-resume.pdf
```

## Configuration boundaries

- The containment Vite build receives only `VITE_BACKEND_URL`.
- Supabase browser variables return only with the reviewed account foundation.
- Provider keys and Supabase secret/service credentials are Railway-only.
- `.env` and `.env.local` remain untracked.
- Production builds fail instead of silently targeting localhost.

The current SQLite/process-local workflow is temporary. Do not describe it as
durable or production-ready; the Postgres/worker migration is tracked as a
separate reviewed change.
