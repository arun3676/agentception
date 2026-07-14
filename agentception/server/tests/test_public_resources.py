"""Public resource responses do not imply an unsupported review methodology."""

from fastapi.testclient import TestClient

from server.app import app
from server.memory import sql_store


def test_public_resource_contract_omits_internal_verified_and_popularity_flags(monkeypatch):
    private_row = {
        "id": "synthetic-resource",
        "title": "Synthetic documentation",
        "url": "https://example.com/docs",
        "verified": True,
        "upvotes": 999,
        "added_at": "2026-01-01",
        "updated_at": "2026-01-02",
        "featured": False,
    }
    monkeypatch.setattr(sql_store, "resources_list", lambda **_kwargs: [private_row])

    response = TestClient(app).get("/api/v1/resources")

    assert response.status_code == 200
    resource = response.json()["items"][0]
    assert {"verified", "upvotes", "added_at", "updated_at"}.isdisjoint(resource)
    assert resource["title"] == "Synthetic documentation"
