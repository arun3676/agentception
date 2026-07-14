from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

FETCH_TIMEOUT = 12.0
MAX_CONCURRENCY = 4
MAX_REDIRECTS = 3
MAX_BODY_BYTES = 512 * 1024
_FETCH_SEM = asyncio.Semaphore(MAX_CONCURRENCY)
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_TEXT_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "application/json",
    "application/ld+json",
    "application/xhtml+xml",
)


class UnsafeExternalUrl(ValueError):
    """Raised when a URL could reach a non-public or unsupported destination."""


@dataclass(frozen=True)
class PublicFetchResponse:
    status_code: int
    url: str
    content_type: str
    body: bytes


def _validated_shape(url: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise UnsafeExternalUrl("Malformed external URL") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeExternalUrl("Only HTTP(S) external URLs are allowed")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeExternalUrl("External URL credentials and missing hosts are not allowed")
    if port is not None and port not in {80, 443}:
        raise UnsafeExternalUrl("External URL port is not allowed")

    hostname = parsed.hostname.rstrip(".").lower()
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise UnsafeExternalUrl("IP-literal external URLs are not allowed")

    normalized = urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            parsed.path or "/",
            parsed.query,
            "",
        )
    )
    return normalized, hostname


async def _require_public_dns(hostname: str) -> None:
    try:
        records = await asyncio.to_thread(socket.getaddrinfo, hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeExternalUrl("External host did not resolve") from exc

    addresses = {record[4][0].split("%")[0] for record in records}
    if not addresses:
        raise UnsafeExternalUrl("External host did not resolve")
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise UnsafeExternalUrl("External host resolves to a non-public address")


async def validate_public_http_url(url: str) -> str:
    """Validate URL shape and every currently resolved address without fetching."""
    normalized, hostname = _validated_shape(url)
    await _require_public_dns(hostname)
    return normalized


async def fetch_public_url(
    url: str,
    *,
    timeout: float = FETCH_TIMEOUT,
    max_body_bytes: int = MAX_BODY_BYTES,
) -> PublicFetchResponse:
    """Fetch bounded public text while revalidating each redirect destination."""
    if max_body_bytes < 1 or max_body_bytes > MAX_BODY_BYTES:
        raise ValueError(f"max_body_bytes must be between 1 and {MAX_BODY_BYTES}")

    current = url
    timeout_config = httpx.Timeout(timeout, connect=min(timeout, 5.0))
    async with _FETCH_SEM:
        async with httpx.AsyncClient(
            timeout=timeout_config,
            follow_redirects=False,
            trust_env=False,
            headers={
                "User-Agent": "Agentception-Listing-Reader/1.0",
                "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.8",
            },
        ) as client:
            for redirect_count in range(MAX_REDIRECTS + 1):
                current = await validate_public_http_url(current)
                async with client.stream("GET", current) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("Location")
                        if not location or redirect_count >= MAX_REDIRECTS:
                            raise UnsafeExternalUrl("External redirect limit exceeded")
                        current = urljoin(current, location)
                        continue

                    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    if content_type not in _TEXT_CONTENT_TYPES:
                        raise UnsafeExternalUrl("External response content type is not allowed")

                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        try:
                            declared_length = int(content_length)
                        except ValueError as exc:
                            raise UnsafeExternalUrl("External response length is invalid") from exc
                        if declared_length > max_body_bytes:
                            raise UnsafeExternalUrl("External response body is too large")

                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > max_body_bytes:
                            raise UnsafeExternalUrl("External response body is too large")
                        chunks.append(chunk)

                    return PublicFetchResponse(
                        status_code=response.status_code,
                        url=str(response.url),
                        content_type=content_type,
                        body=b"".join(chunks),
                    )

    raise UnsafeExternalUrl("External fetch could not be completed")


async def fetch_url_content(url: str, *, max_chars: int = 4000) -> Optional[str]:
    """Return bounded public text, or None for unsafe/unavailable destinations."""
    if not url or max_chars < 1:
        return None
    try:
        response = await fetch_public_url(url, max_body_bytes=min(MAX_BODY_BYTES, max_chars * 4))
    except (UnsafeExternalUrl, httpx.HTTPError, asyncio.TimeoutError):
        return None
    if response.status_code >= 400:
        return None
    return response.body.decode("utf-8", errors="replace")[:max_chars]
