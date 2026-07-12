"""On-disk embedding cache for the eval suite.

The match eval needs the *semantic* signal to be meaningful — measuring a
keyword-only matcher would understate the system and, worse, would silently
change what the metric means depending on whether an API key happened to be set.

So embeddings for the golden set are computed once and committed. CI then runs the
full hybrid matcher with no network and no spend, and the number is reproducible.
Delete the cache file to recompute (requires VOYAGE_API_KEY).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import List

CACHE_PATH = Path(__file__).resolve().parent / "golden" / "embeddings.json"

# The match eval embeds pairs with asyncio.gather. Without this, every concurrent
# call read the same cache, added its own entries, and wrote the whole dict back —
# so all but the last writer's entries were lost (a 15-vector cache persisted 2).
_LOCK = asyncio.Lock()


def _key(text: str) -> str:
    """Cache key = the text AND the embedder that produced the vector.

    Keying on the text alone is a trap: change EMBED_MODEL or EMBED_MAX_CHARS and
    every lookup still *hits*, silently serving vectors from the old embedder while
    production runs the new one — the eval would score a model you no longer ship,
    with no miss and no warning.
    """
    from server.rag import match as embedder

    fingerprint = f"{embedder.EMBED_MODEL}|{embedder.EMBED_MAX_CHARS}|{text}"
    return hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()


def _load() -> dict[str, List[float]]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def _save(cache: dict[str, List[float]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def assert_cache_covers(texts: List[str]) -> None:
    """Fail fast if any document is missing from the cache.

    Callers of the embedder swallow failures and fall back to keyword-only scoring,
    so without this a missing cache file shows up as a *model quality* regression
    instead of the *missing file* it actually is. Check before scoring, not during.
    """
    cache = _load()
    missing = [t for t in texts if _key(t) not in cache]
    if missing:
        raise AssertionError(
            f"{len(missing)} of {len(texts)} documents are not in the eval embedding "
            f"cache ({CACHE_PATH.name}). The metric would silently degrade to "
            f"keyword-only. Rebuild it:\n    python scripts/build_eval_embeddings.py"
        )


async def cached_embed(texts: List[str]) -> List[List[float]]:
    """Read-only drop-in for server.rag.match._embed, served from the committed cache.

    A miss RAISES. It does not quietly call the API and it does not return a
    zero vector — either would make the eval measure something other than what it
    reports (exactly the bug that made the "hybrid" matcher silently keyword-only).
    If you change the golden set, rebuild the cache:

        python scripts/build_eval_embeddings.py
    """
    async with _LOCK:
        cache = _load()

    missing = [t for t in texts if _key(t) not in cache]
    if missing:
        raise RuntimeError(
            f"{len(missing)} document(s) not in the eval embedding cache. "
            f"Run: python scripts/build_eval_embeddings.py"
        )

    return [cache[_key(t)] for t in texts]
