"""Precompute the embeddings the match eval needs, in one batched call.

Voyage rate-limits per request, so embedding 15 documents as 15 requests fights the
limiter and half of them fail. Embedding them as ONE request with a list of 15
inputs costs a single call and always succeeds. The result is committed so CI runs
the real hybrid matcher offline, for free, deterministically.

    python scripts/build_eval_embeddings.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from evals.embedding_cache import CACHE_PATH, _key  # noqa: E402
from evals.metrics import load_jd_text, load_match_pairs  # noqa: E402
from server.rag.match import _embed  # noqa: E402

RESUME_TEXT = ROOT / "evals" / "golden" / "resume_text.txt"
# Voyage's free tier caps *tokens per minute*, not just requests. A single
# 15-document batch blows through it, so pace deliberately — this is a one-off
# build, not a hot path.
BATCH = 3
PAUSE_SECONDS = 22


async def main() -> None:
    pairs = load_match_pairs()
    if not pairs:
        sys.exit("no match pairs — run scripts/build_match_pairs.py first")

    # Exactly the texts the eval will ask for, in the same form — so read the same
    # committed fixture it reads, not the PDF it was derived from. The cache is keyed
    # on the text, so re-extracting here would risk a key that never matches.
    resume_text = RESUME_TEXT.read_text(encoding="utf-8")

    texts = [resume_text] + [load_jd_text(p["jd_id"]) for p in pairs]
    # dedupe while preserving order
    seen, unique = set(), []
    for t in texts:
        if _key(t) not in seen:
            seen.add(_key(t))
            unique.append(t)

    print(f"embedding {len(unique)} unique documents in batches of {BATCH}...")

    cache: dict[str, list[float]] = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    todo = [t for t in unique if _key(t) not in cache]
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        vecs = await _embed(chunk)
        for text, vec in zip(chunk, vecs):
            cache[_key(text)] = vec
        # Persist incrementally: a rate-limit halfway through shouldn't throw away
        # the batches that already succeeded.
        CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
        print(f"  + {len(chunk)} vectors ({min(i + BATCH, len(todo))}/{len(todo)})")

        if i + BATCH < len(todo):
            await asyncio.sleep(PAUSE_SECONDS)

    # Remove vectors for inputs no longer referenced by the golden set. In
    # particular, this prevents embeddings derived from retired personal resume
    # fixtures from lingering after the source data is removed.
    referenced_keys = {_key(text) for text in unique}
    cache = {key: value for key, value in cache.items() if key in referenced_keys}
    CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")

    size_kb = CACHE_PATH.stat().st_size / 1024
    print(f"\n{len(cache)} vectors cached -> {CACHE_PATH.name} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    asyncio.run(main())
