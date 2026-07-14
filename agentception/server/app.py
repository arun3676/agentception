from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
import pathlib
import sys
import uuid
from typing import Any, Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .schemas import TimelineEvent
from .memory.state_store import Memory, TimelineBus
from .memory import sql_store
from .auth import User, current_user
from .rate_limit import limit, search_limiter

logger = logging.getLogger(__name__)

# Keep Unicode startup and diagnostic logs safe when Windows redirects output to
# a file or launches the API without an interactive UTF-8 terminal.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# Load local development variables without logging paths or provider-key state.
env_path = pathlib.Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

class RagBody(BaseModel):
    city: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    depth: Literal["quick", "standard", "deep"] = "standard"

_PRODUCTION = os.getenv("APP_ENV", "development").strip().lower() == "production"


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _validate_runtime_configuration(*, production: bool) -> None:
    if not production:
        return

    unsafe_flags = (
        "MOCK_SEARCH",
        "RATE_LIMIT_DISABLED",
        "TAVILY_DISABLE_SSL_VERIFY",
        "DEBUG_DISCOVERY",
    )
    enabled = [name for name in unsafe_flags if _enabled(name)]
    if enabled:
        raise RuntimeError(f"Unsafe production configuration is enabled: {', '.join(enabled)}")

    missing = [name for name in ("TAVILY_API_KEY", "EXA_API_KEY") if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(f"Required production configuration is missing: {', '.join(missing)}")


_validate_runtime_configuration(production=_PRODUCTION)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Initialize the active store and static catalogue without blocking startup."""
    try:
        if sys.platform.startswith("win"):
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            except Exception:
                pass
        sql_store.init()
        logger.info("application data store initialized")

        from .resources_library import ensure_resources_seeded

        logger.info(
            "resource library initialized",
            extra={"resource_count": ensure_resources_seeded()},
        )
    except Exception:
        logger.warning("application startup initialization failed")
    yield


app = FastAPI(
    title="Agentception API",
    docs_url=None if _PRODUCTION else "/docs",
    redoc_url=None if _PRODUCTION else "/redoc",
    openapi_url=None if _PRODUCTION else "/openapi.json",
    lifespan=_lifespan,
)

from .routers.v1 import router as v1_router
from .routers.study import router as study_router
app.include_router(v1_router)
app.include_router(study_router)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid.uuid4().hex)


def _error_code(status_code: int, message: str) -> str:
    if status_code == 503 and message == "Service is not ready":
        return "service_not_ready"
    return {
        400: "invalid_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        408: "request_timeout",
        409: "conflict",
        422: "invalid_request",
        429: "rate_limited",
        500: "internal_error",
        502: "upstream_error",
        503: "service_unavailable",
        504: "upstream_timeout",
    }.get(status_code, f"http_{status_code}")


def _error_response(
    request: Request,
    *,
    status_code: int,
    message: str,
    field_errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {
        "code": _error_code(status_code, message),
        "message": message,
        "retryable": status_code in {408, 425, 429, 500, 502, 503, 504},
        "request_id": _request_id(request),
    }
    if field_errors:
        error["field_errors"] = field_errors
    return JSONResponse(status_code=status_code, content={"error": error})


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    if exc.status_code >= 500 and message not in {
        "Service is not ready",
        "Authentication service unavailable",
        "SUPABASE_URL is not configured",
    }:
        message = "The service could not complete the request"
    return _error_response(request, status_code=exc.status_code, message=message)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    field_errors = [
        {
            "field": ".".join(str(part) for part in error.get("loc", ()) if part != "body"),
            "message": str(error.get("msg") or "Invalid value"),
        }
        for error in exc.errors()
    ]
    return _error_response(
        request,
        status_code=422,
        message="Request validation failed",
        field_errors=field_errors,
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, _exc: Exception):
    logger.error("unhandled request error", extra={"request_id": _request_id(request)})
    return _error_response(
        request,
        status_code=500,
        message="The service could not complete the request",
    )

_LOCAL_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
)


def _configured_origins(raw: str | None, *, production: bool) -> list[str]:
    """Return exact browser origins; wildcard and path-based values are rejected."""
    values = [part.strip().rstrip("/") for part in (raw or "").split(",") if part.strip()]
    if not values:
        if production:
            raise RuntimeError("FRONTEND_ORIGINS must be configured in production")
        return list(_LOCAL_ORIGINS)

    origins: list[str] = []
    for value in values:
        parsed = urlsplit(value)
        if (
            "*" in value
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise RuntimeError(f"Invalid origin in FRONTEND_ORIGINS: {value!r}")
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in origins:
            origins.append(origin)
    return origins


# FRONTEND_ORIGIN remains a one-release compatibility alias for Railway.
_origin_setting = os.getenv("FRONTEND_ORIGINS") or os.getenv("FRONTEND_ORIGIN")
ALLOWED_ORIGINS = _configured_origins(_origin_setting, production=_PRODUCTION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Last-Event-ID"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if _PRODUCTION or request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

memory = Memory(); bus = TimelineBus()

# Removed unused /run endpoint

# Removed unused /test-agent and /subrun endpoints

# Removed unused /explore endpoint

@app.get("/timeline/{run_id}")
async def timeline(run_id: str):
    q = bus.get(run_id)
    if not q: raise HTTPException(404, "Unknown run_id")
    
    async def gen():
        try:
            # Send initial connection confirmation
            yield "data: " + json.dumps({"type": "connected", "run_id": run_id}) + "\n\n"
            
            while True:
                try:
                    # Set a timeout to prevent hanging
                    item = await asyncio.wait_for(q.get(), timeout=30.0)
                    
                    if item.get("type") == "end":
                        status = item.get("status", "failed")
                        yield "event: end\n" + "data: " + json.dumps({"status": status}) + "\n\n"
                        break
                    
                    # Ensure proper JSON serialization
                    data = json.dumps(item, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield "data: " + json.dumps({"type": "heartbeat", "run_id": run_id}) + "\n\n"
                    continue
                except Exception:
                    logger.warning("timeline stream failed")
                    yield "data: " + json.dumps({"type": "error", "message": "Timeline stream failed"}) + "\n\n"
                    break
                    
        except Exception:
            logger.warning("timeline stream terminated")
            yield "data: " + json.dumps({"type": "fatal_error", "message": "Timeline stream terminated"}) + "\n\n"
    
    return StreamingResponse(
        gen(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable proxy buffering
        }
    )

@app.get("/results/{run_id}")
async def results(
    run_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=5, ge=1, le=100),
):
    """Paginated job-search results for the UI.

    Returns {run_id, city, role, companies, pagination, ...} — the shape the
    frontend's getResults() expects. Companies come from the stored RAGDoc,
    sorted by score and sliced to the requested page.
    """
    from .agents.rag_companies import get_rag_results

    # Rehydrate from the database when this process didn't run the search — a
    # restart, or a second instance. Without this, results vanished on redeploy.
    if memory.get(f"ragdoc:{run_id}") is None:
        persisted = sql_store.search_run_get(run_id)
        if persisted is None:
            raise HTTPException(404, "No results found for this run_id")
        memory.set(f"ragdoc:{run_id}", persisted)

    rag_doc = await get_rag_results(run_id, offset=offset, limit=limit, memory_store=memory)
    payload = rag_doc.model_dump()

    # The containment API is anonymous discovery only. Internal ranking and
    # retired résumé/trust fields are not public evidence and must not escape in
    # the response, even when an old persisted run contains them.
    payload.pop("resume_insights", None)
    payload.pop("resume_excerpt", None)
    hidden_result_fields = {
        "score",
        "rank_score",
        "user_id",
        "email",
        "phone",
        "contact_info",
        "resume_text",
        "resume_token",
        "resume_insights",
        "resume_excerpt",
        "resume_match_score",
        "missing_skills",
        "trust_score",
        "trust_label",
        "trust_reasons",
        "match_band",
        "match_probability",
        "match_explanation",
        "is_expired",
        "days_old",
        "posted_at",
    }
    def public_result(value):
        if isinstance(value, dict):
            return {
                key: public_result(item)
                for key, item in value.items()
                if key not in hidden_result_fields
            }
        if isinstance(value, list):
            return [public_result(item) for item in value]
        return value

    payload["companies"] = [public_result(company) for company in payload.get("companies", [])]

    # RAGDoc stores the place as `location`; the frontend reads `city`.
    payload["city"] = payload.get("location", "")

    # Recompute pagination for THIS request — the stored value reflects the
    # offset the search ran at, not the page the UI just asked for.
    total = payload.get("total", len(payload.get("companies", [])))
    payload["pagination"] = {
        "offset": offset,
        "limit": limit,
        "total": total,
        "has_more": (offset + limit) < total,
    }
    return payload

@app.get("/health/live")
async def health_live():
    """Process liveness without provider, database, or key details."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(request: Request):
    """Return 503 when the active application store is unavailable."""
    try:
        sql_store.healthcheck()
    except Exception:
        logger.warning("readiness probe failed")
        return _error_response(
            request,
            status_code=503,
            message="Service is not ready",
        )
    return {"status": "ready"}


@app.get("/health", include_in_schema=False)
async def health():
    """One-release compatibility alias for process liveness."""
    return await health_live()

@app.post("/rag/companies", dependencies=[Depends(limit(search_limiter))])
async def rag_companies(
    body: RagBody,
    bg: BackgroundTasks,
    user: User = Depends(current_user),
):
    """
    RAG company discovery endpoint:
    1. Discover companies using role-aware Exa search
    2. Build comprehensive RAG document
    3. Store results for paginated reads
    4. Stream timeline updates
    """
    role = body.role.strip()
    city = body.city.strip()
    if not role or not city:
        raise HTTPException(422, "role and city are required")
    run_id = str(uuid.uuid4())
    q = bus.ensure(run_id)
    
    async def emit(ev):
        # Accept either TimelineEvent or plain string/dict and normalize
        try:
            if isinstance(ev, TimelineEvent):
                update = ev.model_copy(update={"event_id": ev.event_id or uuid.uuid4().hex})
                await q.put(update.model_dump())
            elif isinstance(ev, str):
                await q.put(TimelineEvent(run_id=run_id, agent="Writer", message=ev).model_dump())
            elif isinstance(ev, dict):
                # minimal dict with message
                msg = ev.get("message", str(ev))
                await q.put(TimelineEvent(run_id=run_id, agent=ev.get("agent", "Writer"), message=msg).model_dump())
            else:
                await q.put(TimelineEvent(run_id=run_id, agent="Writer", message=str(ev)).model_dump())
        except Exception:
            await q.put(TimelineEvent(run_id=run_id, agent="Search", message="Timeline update failed", level="error").model_dump())
    
    async def job():
        terminal_status = "failed"
        try:
            from .agents.rag_companies import run_rag_company_search
            
            # Run RAG company search workflow with multi-role search enabled.
            # Pass the shared `memory` so the full company list and the Load-More
            # cache land where /results can read them — without this
            # the agent writes them to a throwaway Memory() and only the first
            # page survives.
            doc = await run_rag_company_search(
                run_id=run_id,
                city=city,
                role=role,
                resume_token=None,
                emit=emit,
                multi_role=True,  # Enable multi-role search for better company coverage
                depth=body.depth,  # Pass depth parameter for resource limits
                memory_store=memory,
            )

            # run_rag_company_search already stored the FULL RAGDoc at
            # ragdoc:{run_id}; keep it intact so /results can paginate over every
            # result. Fall back to the returned first page only if it's missing.
            if not memory.get(f"ragdoc:{run_id}"):
                memory.set(f"ragdoc:{run_id}", doc)

            # Persist it. In-memory alone meant a restart threw away results the user
            # had already paid for in Tavily/Exa/Voyage calls.
            full = memory.get(f"ragdoc:{run_id}") or doc
            sql_store.search_run_save(
                run_id=run_id,
                user_id=None if user.is_anonymous else user.id,
                role=full.get("role") or role,
                city=full.get("location") or full.get("city") or city,
                doc=full,
            )
            
            await emit(TimelineEvent(
                run_id=run_id, 
                agent="RAG", 
                message="Search complete"
            ))
            terminal_status = "succeeded"
            
        except Exception:
            logger.warning("job search failed")
            await emit(TimelineEvent(
                run_id=run_id, 
                agent="RAG", 
                message="Search failed. Please try again.",
                level="error"
            ))
        finally:
            await q.put({"type": "end", "status": terminal_status})
    
    bg.add_task(job)
    return {"run_id": run_id, "status": "queued"}
