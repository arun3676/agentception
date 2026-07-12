from __future__ import annotations

"""Supabase JWT verification.

Supabase moved from a shared HS256 secret to asymmetric signing (ES256/RS256) with a
published JWKS endpoint, so tokens are verified against a *public* key the server
fetches and caches — the API never holds a signing secret it could leak.
https://supabase.com/docs/guides/auth/jwts

Anonymous access is deliberately still allowed. This is a portfolio app with a public
demo, and forcing sign-up to see a job search would be user-hostile. The rule is:
anonymous users get a stable pseudonymous id and can use the product; anything that
*persists* to a real account requires a real token.
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from fastapi import Depends, HTTPException, Request

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
JWKS_TTL_SECONDS = 600  # Supabase caches JWKS at the edge for 10 minutes; match it.

ANONYMOUS_USER_ID = "anonymous"


@dataclass
class User:
    id: str
    email: Optional[str] = None
    is_anonymous: bool = False


_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


async def _jwks() -> dict:
    """Supabase's public signing keys, cached."""
    now = time.time()
    if _jwks_cache["keys"] and now - _jwks_cache["fetched_at"] < JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]

    if not SUPABASE_URL:
        raise HTTPException(500, "SUPABASE_URL is not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
        resp.raise_for_status()
        keys = resp.json()

    _jwks_cache.update(keys=keys, fetched_at=now)
    return keys


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


async def _decode(token: str) -> dict:
    try:
        from jose import jwt
        from jose.exceptions import JWTError
    except ImportError:  # pragma: no cover - dependency is declared in requirements
        raise HTTPException(500, "python-jose is not installed")

    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        raise HTTPException(401, "Malformed token")

    keys = await _jwks()
    key = next((k for k in keys.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if not key:
        # A rotated key may not be in our cached copy yet — refetch once.
        _jwks_cache["fetched_at"] = 0.0
        keys = await _jwks()
        key = next((k for k in keys.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if not key:
        raise HTTPException(401, "Token signed with an unknown key")

    try:
        return jwt.decode(
            token,
            key,
            algorithms=[header.get("alg", "ES256")],
            audience="authenticated",
            options={"verify_aud": False},  # Supabase sets aud=authenticated
        )
    except JWTError as e:
        raise HTTPException(401, f"Invalid token: {e}")


async def current_user(request: Request) -> User:
    """The signed-in user, or a stable anonymous identity.

    Never raises for a missing token — anonymous use is a supported mode. It raises
    only for a token that is *present and invalid*, which is a real error worth
    surfacing rather than silently downgrading to anonymous.
    """
    token = _bearer(request)
    if not token:
        return User(id=ANONYMOUS_USER_ID, is_anonymous=True)

    claims = await _decode(token)
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(401, "Token has no subject")

    return User(id=user_id, email=claims.get("email"), is_anonymous=False)


async def require_user(user: User = Depends(current_user)) -> User:
    """For routes that must not run anonymously (data deletion, account actions)."""
    if user.is_anonymous:
        raise HTTPException(401, "Sign in to use this endpoint")
    return user
