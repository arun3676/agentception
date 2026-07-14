"""SSRF boundary tests for all server-side external URL fetching."""

import asyncio
import socket

import pytest

from server.tools.http_fetch import (
    UnsafeExternalUrl,
    _validated_shape,
    validate_public_http_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "https://user:password@example.com/",
        "http://127.0.0.1/",
        "http://[::1]/",
        "https://example.com:8443/",
        "https:///missing-host",
    ],
)
def test_external_url_shape_rejects_unsafe_destinations(url: str):
    with pytest.raises(UnsafeExternalUrl):
        _validated_shape(url)


def test_external_url_shape_removes_fragments_and_normalizes_path():
    normalized, hostname = _validated_shape("HTTPS://Example.COM#private-fragment")

    assert normalized == "https://Example.COM/"
    assert hostname == "example.com"


def test_dns_validation_rejects_any_private_resolution(monkeypatch):
    def fake_getaddrinfo(*_args, **_kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.4", 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UnsafeExternalUrl, match="non-public"):
        asyncio.run(validate_public_http_url("https://example.com/jobs"))


def test_dns_validation_allows_public_resolution(monkeypatch):
    def fake_getaddrinfo(*_args, **_kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    assert asyncio.run(validate_public_http_url("https://example.com/jobs")) == (
        "https://example.com/jobs"
    )
