from __future__ import annotations

import copy
import hashlib
import time
from collections import OrderedDict
from typing import Any, Optional

# Containment-only process-local cache. It is bounded, expires entries, contains no
# connection fallback, and is deliberately not described as durable storage.
_MAX_ENTRIES = 512
_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()


def _prune(now: float) -> None:
    expired = [key for key, (expires_at, _) in _cache.items() if expires_at <= now]
    for key in expired:
        _cache.pop(key, None)
    while len(_cache) > _MAX_ENTRIES:
        _cache.popitem(last=False)


def make_cache_key(prefix: str, *args: object) -> str:
    key_data = ":".join(str(value).lower().strip() for value in args if value)
    digest = hashlib.sha256(key_data.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def cache_set(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    if ttl_seconds <= 0:
        return False
    now = time.monotonic()
    _prune(now)
    _cache[key] = (now + ttl_seconds, copy.deepcopy(value))
    _cache.move_to_end(key)
    _prune(now)
    return True


def cache_get(key: str) -> Optional[Any]:
    now = time.monotonic()
    _prune(now)
    cached = _cache.get(key)
    if cached is None:
        return None
    _cache.move_to_end(key)
    return copy.deepcopy(cached[1])


def cache_delete(key: str) -> bool:
    _cache.pop(key, None)
    return True


def cache_search_results(role: str, location: str, results: list, ttl_seconds: int = 1800) -> bool:
    return cache_set(make_cache_key("search", role, location), results, ttl_seconds)


def get_cached_search_results(role: str, location: str) -> Optional[list]:
    return cache_get(make_cache_key("search", role, location))


def cache_ats_query(query: str, results: list, ttl_seconds: int = 900) -> bool:
    return cache_set(make_cache_key("ats", query), results, ttl_seconds)


def get_cached_ats_query(query: str) -> Optional[list]:
    return cache_get(make_cache_key("ats", query))
