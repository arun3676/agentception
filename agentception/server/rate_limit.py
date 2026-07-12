from __future__ import annotations

"""Rate limiting.

Every expensive endpoint here spends real money on someone else's API — a job search
fans out to Tavily, Exa, Voyage and a JD fetch per result. Without a limit, one bored
visitor with a for-loop can drain the account, and a public demo is exactly where that
happens.

A token bucket per client, in-process. Deliberately not Redis: this app runs as a
single instance, and an in-memory limiter that works beats a distributed one that
isn't wired up. If it ever scales out, swap the store — the interface won't change.
"""

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from fastapi import HTTPException, Request

DISABLED = os.getenv("RATE_LIMIT_DISABLED", "false").lower() == "true"


@dataclass
class Bucket:
    capacity: int
    refill_per_second: float
    tokens: float = field(default=0.0)
    last: float = field(default_factory=time.monotonic)

    def take(self) -> tuple[bool, float]:
        """(allowed, seconds_until_next_token)"""
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.refill_per_second)
        self.last = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True, 0.0

        return False, (1.0 - self.tokens) / self.refill_per_second


class RateLimiter:
    def __init__(self, name: str, per_minute: int, burst: int | None = None):
        self.name = name
        self.per_minute = per_minute
        self.capacity = burst or per_minute
        self._buckets: dict[str, Bucket] = defaultdict(self._new_bucket)

    def _new_bucket(self) -> Bucket:
        return Bucket(
            capacity=self.capacity,
            refill_per_second=self.per_minute / 60.0,
            tokens=float(self.capacity),
        )

    def check(self, client: str) -> None:
        if DISABLED:
            return
        allowed, retry_after = self._buckets[client].take()
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {self.name}. Try again in {retry_after:.0f}s.",
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )


def client_key(request: Request) -> str:
    """Identify the caller: the signed-in user if there is one, else the source IP."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        # Don't parse the JWT here — the raw token is a stable enough key, and this
        # runs before auth on every request.
        return f"token:{hash(auth[7:]) & 0xFFFFFFFF}"

    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"ip:{ip}"


# Tiers by what the endpoint actually costs us.
search_limiter = RateLimiter("search", per_minute=6, burst=3)        # fans out to 4 paid APIs
llm_limiter = RateLimiter("ai", per_minute=12, burst=6)              # one LLM call
read_limiter = RateLimiter("read", per_minute=120, burst=30)         # database only


def limit(limiter: RateLimiter) -> Callable:
    """FastAPI dependency: `Depends(limit(search_limiter))`."""

    async def _dependency(request: Request) -> None:
        limiter.check(client_key(request))

    return _dependency
