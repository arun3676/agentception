"""Regression coverage for the first production-containment release."""

import asyncio
import time
from types import SimpleNamespace

import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from server import auth
from server.app import (
    ALLOWED_ORIGINS,
    _configured_origins,
    _validate_runtime_configuration,
    app,
)
from server.memory import sql_store


client = TestClient(app)


def test_exact_origin_parser_rejects_wildcards_and_paths():
    assert _configured_origins(
        "https://agentception.vercel.app,https://preview.example.com/",
        production=True,
    ) == ["https://agentception.vercel.app", "https://preview.example.com"]

    with pytest.raises(RuntimeError):
        _configured_origins("https://*.vercel.app", production=True)
    with pytest.raises(RuntimeError):
        _configured_origins("https://example.com/app", production=True)


def test_cors_allows_only_configured_exact_origins_without_credentials():
    allowed = ALLOWED_ORIGINS[0]
    headers = {
        "Origin": allowed,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    }
    response = client.options("/health/live", headers=headers)
    assert response.headers["access-control-allow-origin"] == allowed
    assert "access-control-allow-credentials" not in response.headers

    attacker = client.options(
        "/health/live",
        headers={**headers, "Origin": "https://attacker-controlled.vercel.app"},
    )
    assert "access-control-allow-origin" not in attacker.headers


def test_security_headers_cover_api_responses():
    response = client.get("/health/live", headers={"X-Forwarded-Proto": "https"})
    assert response.headers["content-security-policy"].startswith("default-src 'none'")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["strict-transport-security"].startswith("max-age=31536000")
    assert len(response.headers["x-request-id"]) == 32


def test_health_contract_does_not_expose_provider_or_key_state(monkeypatch):
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}

    monkeypatch.setattr(sql_store, "healthcheck", lambda: None)
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}

    def unavailable():
        raise OSError("private database detail")

    monkeypatch.setattr(sql_store, "healthcheck", unavailable)
    failed = client.get("/health/ready")
    assert failed.status_code == 503
    assert "private database detail" not in failed.text
    assert failed.json()["error"]["code"] == "service_not_ready"


def test_production_configuration_rejects_unsafe_modes_and_missing_search_keys(monkeypatch):
    for flag in (
        "MOCK_SEARCH",
        "RATE_LIMIT_DISABLED",
        "TAVILY_DISABLE_SSL_VERIFY",
        "DEBUG_DISCOVERY",
    ):
        monkeypatch.setenv(flag, "false")
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic-tavily-key")
    monkeypatch.setenv("EXA_API_KEY", "synthetic-exa-key")
    monkeypatch.setenv("MOCK_SEARCH", "true")
    with pytest.raises(RuntimeError, match="MOCK_SEARCH"):
        _validate_runtime_configuration(production=True)

    monkeypatch.setenv("MOCK_SEARCH", "false")
    monkeypatch.delenv("TAVILY_API_KEY")
    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        _validate_runtime_configuration(production=True)


def test_debug_paid_and_unsupported_beta_routes_are_not_registered():
    paths = set(app.openapi()["paths"])
    removed = {
        "/debug/memory/{run_id}",
        "/debug/exa",
        "/debug/pdf",
        "/debug/fitz",
        "/debug/matcher",
        "/test/enhanced-research",
        "/writer/outreach",
        "/audit/start",
        "/outcomes/log",
        "/save/add",
        "/api/fetch-job-description",
        "/api/v2/system/api-key-health",
        "/api/v2/system/usage",
        "/api/v2/career/reverse-engineer",
        "/api/v1/applications/refresh-listings",
        "/upload/resume",
        "/upload/resume/{token}",
        "/me",
        "/me/data",
        "/api/v1/applications",
        "/api/v1/applications/{application_id}",
        "/api/v1/learning-paths",
        "/api/v1/learning-paths/{path_id}",
        "/api/v1/learning-paths/generate",
        "/api/v1/company/brief",
        "/api/v1/study/interview-prep",
        "/api/v1/study/search",
        "/api/v1/skill-gaps/analyze",
    }
    assert not (paths & removed)


@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        ("get", "/api/v1/applications", {}),
        ("get", "/api/v1/learning-paths", {}),
        ("get", "/api/v1/company/brief?name=Example", {}),
        ("get", "/api/v1/study/interview-prep?role=Engineer", {}),
        ("post", "/api/v1/study/search", {"json": {"topic": "Python"}}),
        ("post", "/api/v1/skill-gaps/analyze", {"json": {"resume_text": "private"}}),
    ],
)
def test_private_and_paid_routes_are_not_implemented(method, path, kwargs):
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "Not Found",
        "retryable": False,
        "request_id": response.headers["x-request-id"],
    }


def test_validation_errors_use_the_safe_common_envelope():
    response = client.post(
        "/rag/companies",
        json={"role": "", "city": "Austin, TX", "depth": "unsupported"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["retryable"] is False
    assert error["request_id"] == response.headers["x-request-id"]
    assert {item["field"] for item in error["field_errors"]} == {"role", "depth"}


def test_result_pagination_is_bounded():
    response = client.get("/results/unknown?offset=-1&limit=1000")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_jwt_decode_uses_fixed_algorithms_and_validates_registered_claims(monkeypatch):
    captured = {}

    async def fake_jwks():
        return {"keys": [{"kid": "key-1", "alg": "ES256", "use": "sig"}]}

    monkeypatch.setattr(auth, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(auth, "_jwks", fake_jwks)
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda _token: {"kid": "key-1", "alg": "ES256"})
    monkeypatch.setattr(
        auth,
        "_select_signing_key",
        lambda *_args, **_kwargs: SimpleNamespace(key="public-key"),
    )

    def fake_decode(*args, **kwargs):
        captured.update(kwargs)
        return {"sub": "user-1"}

    monkeypatch.setattr(auth.jwt, "decode", fake_decode)
    assert asyncio.run(auth._decode("token"))["sub"] == "user-1"
    assert captured["algorithms"] == ["ES256"]
    assert captured["audience"] == "authenticated"
    assert captured["issuer"] == "https://project.supabase.co/auth/v1"
    assert captured["options"]["require"] == ["aud", "exp", "iat", "iss", "nbf", "sub"]
    assert captured["options"]["verify_nbf"] is True
    assert captured["options"]["strict_aud"] is True


def test_jwt_decode_rejects_header_selected_symmetric_algorithm(monkeypatch):
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda _token: {"kid": "key-1", "alg": "HS256"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth._decode("token"))
    assert exc.value.status_code == 401


def test_jwk_selection_enforces_signature_use_algorithm_and_key_ops(monkeypatch):
    parsed = SimpleNamespace(algorithm_name="RS256", key="public-key")
    monkeypatch.setattr(auth.PyJWK, "from_dict", lambda candidate, algorithm: parsed)

    candidates = {
        "keys": [
            {"kid": "wanted", "alg": "RS256", "use": "enc"},
            {"kid": "wanted", "alg": "RS256", "use": "sig", "key_ops": ["sign"]},
            {"kid": "wanted", "alg": "RS256", "use": "sig", "key_ops": ["verify"]},
        ]
    }

    assert auth._select_signing_key(candidates, kid="wanted", algorithm="RS256") is parsed


def test_real_rs256_token_requires_all_registered_claims(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk.update({"kid": "key-1", "alg": "RS256", "use": "sig"})

    async def fake_jwks():
        return {"keys": [public_jwk]}

    now = int(time.time())
    claims = {
        "aud": "authenticated",
        "exp": now + 60,
        "iat": now,
        "iss": "https://project.supabase.co/auth/v1",
        "nbf": now,
        "sub": "user-1",
    }
    monkeypatch.setattr(auth, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(auth, "_jwks", fake_jwks)

    token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "key-1"})
    assert asyncio.run(auth._decode(token))["sub"] == "user-1"

    missing_nbf = jwt.encode(
        {key: value for key, value in claims.items() if key != "nbf"},
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth._decode(missing_nbf))
    assert exc.value.status_code == 401
