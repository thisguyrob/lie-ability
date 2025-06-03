from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_healthz() -> None:
    """/healthz should return 204."""
    response = client.get("/healthz")
    assert response.status_code == 204
