# FastAPI backend

The containment backend exposes anonymous role/location discovery, search status
and results, a public resource catalogue, and minimal health endpoints. Résumé,
writer/outreach, debug, provider-health, usage, and experimental beta routes are
not registered in production.

Start from `agentception/`:

```powershell
python -m pip install uv==0.11.28
uv lock --check
uv sync --locked --group dev
Copy-Item .env.example .env
uv run uvicorn server.app:app --reload --port 8000
```

Validate:

```powershell
uv run --locked python -m compileall server
uv run --locked python -m pytest -q --strict-markers
```

Production requires exact `FRONTEND_ORIGINS`, Tavily, and Exa configuration.
Secrets remain server-side. `/health/live` exposes process liveness;
`/health/ready` fails closed when the active store is unavailable.

Search jobs, events, and SQLite persistence still need the reviewed Postgres
worker migration. This module must not be described as restart-safe or horizontally
scalable until that work is complete.
