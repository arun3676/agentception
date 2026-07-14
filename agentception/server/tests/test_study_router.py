"""The containment release exposes only the static career-pillar catalogue."""

from fastapi.testclient import TestClient

from server.app import app


def test_public_pillars_have_the_minimal_catalogue_shape():
    response = TestClient(app).get("/api/v1/study/pillars")

    assert response.status_code == 200
    pillars = response.json()["pillars"]
    assert pillars
    assert all(set(pillar) == {"key", "label", "keywords"} for pillar in pillars)
    assert all(isinstance(pillar["keywords"], list) for pillar in pillars)


def test_provider_backed_study_routes_are_not_implemented():
    client = TestClient(app)

    assert client.get("/api/v1/study/interview-prep?role=Engineer").status_code == 404
    assert client.post("/api/v1/study/search", json={"topic": "Python"}).status_code == 404
