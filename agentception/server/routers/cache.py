from __future__ import annotations

"""Read-through cache around the shared `search_cache` table.

Study material, company briefs and interview guides are all "expensive lookup,
stable answer, cache for a while". They differ only in engine name, TTL and how
to fetch — everything else was the same six lines in three endpoints.
"""

from typing import Any, Awaitable, Callable, Dict

from ..memory import sql_store


def _is_nonempty(payload: Dict[str, Any]) -> bool:
    return bool(payload)


async def cached_search(
    *,
    engine: str,
    subject: str,
    params: Dict[str, Any],
    ttl_seconds: int,
    fetch: Callable[[], Awaitable[Dict[str, Any]]],
    should_cache: Callable[[Dict[str, Any]], bool] = _is_nonempty,
) -> Dict[str, Any]:
    """Return a cached payload if present, otherwise `await fetch()` and store it.

    `should_cache` guards against caching an empty result from a failed upstream
    call, which would otherwise pin the failure for the whole TTL.
    """
    key = sql_store.compute_search_cache_key(engine, subject, params)

    cached = sql_store.search_cache_get(key)
    if cached:
        cached["cached"] = True
        return cached

    payload = await fetch()
    payload["cached"] = False

    if should_cache(payload):
        sql_store.search_cache_set(key, engine, subject, params, payload, ttl_seconds)
    return payload
