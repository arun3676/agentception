# Server — FastAPI Backend

> TL;DR: Orchestrates multi-agent workflow (RAG → Research → Writer), streams timeline via SSE, persists results in SQLite.

## Quickstart

```bash
python -m venv .venv && .\.venv\Scripts\activate && pip install -r ..\requirements.txt
python -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
start http://localhost:8000/docs
```

## Key Endpoints
- `POST /rag/companies`
- `POST /writer/outreach`
- `GET /timeline/{run_id}` (SSE)
- `POST /save/add`, `GET /save/list`

## Env
Set in project `.env`:
```
EXA_API_KEY=...
DEEPSEEK_API_KEY=...
GOOGLE_MAPS_KEY=...
```

See root `README.md` for full docs and the architecture diagram.

