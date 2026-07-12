"""
Background task wrappers for the readiness engine.
These are called from app.py route handlers via BackgroundTasks.
"""
from __future__ import annotations

from typing import Any, Callable, Coroutine, Optional

from ..agents.readiness.audit_engine import run_audit
from ..agents.readiness.decision_engine import decide_one_thing
from ..memory.state_store import Memory

EmitFn = Callable[[Any], Coroutine[Any, Any, None]]


async def start_audit_task(
    *,
    target_role: str,
    resume_token: Optional[str] = None,
    user_id: Optional[str] = None,
    city: str = "San Francisco",
    emit: Optional[EmitFn] = None,
    memory_store: Optional[Memory] = None,
) -> dict:
    """Run audit in background, return result dict."""
    result = await run_audit(
        target_role=target_role,
        resume_token=resume_token,
        user_id=user_id,
        city=city,
        emit=emit,
        memory_store=memory_store,
    )
    return result


async def start_one_thing_task(audit_result: dict) -> dict:
    """Decide the one-thing action from an audit result."""
    return await decide_one_thing(audit_result)
