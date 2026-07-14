from __future__ import annotations

"""Supabase JWT verification for optional authenticated requests.

Anonymous job discovery remains public. When a bearer token is supplied, the API
accepts only asymmetric Supabase access tokens whose registered claims and signing
key can be verified against the project's public JWKS.
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from jwt import InvalidTokenError, PyJWK, PyJWKError

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
JWKS_TTL_SECONDS = 600
ALLOWED_JWT_ALGORITHMS = frozenset({"ES256", "RS256"})
ANONYMOUS_USER_ID = "anonymous"


@dataclass
class User:
    id: str
    email: Optional[str] = None
    is_anonymous: bool = False


_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


async def _jwks() -> dict[str, Any]:
    """Fetch and briefly cache the project's public signing keys."""
    now = time.time()
    if _jwks_cache["keys"] and now - _jwks_cache["fetched_at"] < JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]

    if not SUPABASE_URL:
        raise HTTPException(500, "SUPABASE_URL is not configured")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
            response.raise_for_status()
            keys = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Authentication service unavailable") from exc

    if not isinstance(keys, dict) or not isinstance(keys.get("keys"), list):
        raise HTTPException(503, "Authentication service unavailable")

    _jwks_cache.update(keys=keys, fetched_at=now)
    return keys


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def _select_signing_key(
    keys: dict[str, Any], *, kid: str, algorithm: str
) -> PyJWK | None:
    """Return the compatible verification key selected by an allowed header."""
    for candidate in keys.get("keys", []):
        if not isinstance(candidate, dict):
            continue
        if candidate.get("kid") != kid:
            continue
        if candidate.get("use", "sig") != "sig":
            continue
        if candidate.get("alg", algorithm) != algorithm:
            continue
        key_ops = candidate.get("key_ops")
        if key_ops is not None and (
            not isinstance(key_ops, list) or "verify" not in key_ops
        ):
            continue
        try:
            parsed = PyJWK.from_dict(candidate, algorithm=algorithm)
        except (PyJWKError, InvalidTokenError, TypeError, ValueError):
            return None
        if parsed.algorithm_name != algorithm:
            return None
        return parsed
    return None


async def _decode(token: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise HTTPException(401, "Malformed token") from exc

    algorithm = header.get("alg")
    if algorithm not in ALLOWED_JWT_ALGORITHMS:
        raise HTTPException(401, "Token uses an unsupported signing algorithm")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise HTTPException(401, "Token has no signing key id")

    keys = await _jwks()
    signing_key = _select_signing_key(keys, kid=kid, algorithm=algorithm)
    if signing_key is None:
        # A rotation may have occurred while the cached JWKS was valid. Refetch once.
        _jwks_cache["fetched_at"] = 0.0
        keys = await _jwks()
        signing_key = _select_signing_key(keys, kid=kid, algorithm=algorithm)
    if signing_key is None:
        raise HTTPException(401, "Token signed with an unknown key")

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience="authenticated",
            issuer=f"{SUPABASE_URL}/auth/v1",
            options={
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "strict_aud": True,
                "require": ["aud", "exp", "iat", "iss", "nbf", "sub"],
            },
        )
    except InvalidTokenError as exc:
        raise HTTPException(401, "Invalid token") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(401, "Invalid token")
    return claims


async def current_user(request: Request) -> User:
    """Return a verified user or the anonymous discovery identity."""
    token = _bearer(request)
    if not token:
        return User(id=ANONYMOUS_USER_ID, is_anonymous=True)

    claims = await _decode(token)
    return User(id=claims["sub"], email=claims.get("email"), is_anonymous=False)


async def require_user(user: User = Depends(current_user)) -> User:
    """Reject anonymous callers for a future private resource boundary."""
    if user.is_anonymous:
        raise HTTPException(401, "Sign in to use this endpoint")
    return user
