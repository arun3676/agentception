from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .memory import sql_store

_seed_loaded = False


def _seed_path() -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, "data", "ai_resources.json")


def load_seed_resources() -> List[Dict[str, Any]]:
    seed_path = _seed_path()
    try:
        with open(seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


_seed_count = 0


def ensure_resources_seeded() -> int:
    """Idempotent. After the first call this is free — it used to run a COUNT(*)
    (opening a fresh SQLite connection) on every request that touched resources."""
    global _seed_loaded, _seed_count
    if _seed_loaded:
        return _seed_count

    count = sql_store.resources_count()
    if count == 0:
        seed = load_seed_resources()
        if seed:
            sql_store.resources_upsert_many(seed)
        count = sql_store.resources_count()

    _seed_loaded = True
    _seed_count = count
    return count
