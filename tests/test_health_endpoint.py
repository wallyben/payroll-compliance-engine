import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}
