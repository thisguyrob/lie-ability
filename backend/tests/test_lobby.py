from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def create_lobby() -> tuple[str, str]:
    resp = client.post("/api/v1/lobbies", json={"roundCount": 3})
    assert resp.status_code == 201
    data = resp.json()
    return data["code"], data["hostToken"]


def join(code: str, name: str) -> dict:
    resp = client.post(
        f"/api/v1/lobbies/{code}/join", json={"nickname": name, "avatar": "🐍"}
    )
    assert resp.status_code == 200
    return resp.json()


def test_happy_flow() -> None:
    code, host_token = create_lobby()
    player = join(code, "Rob")
    token = player["playerToken"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get(f"/api/v1/lobbies/{code}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["players"][0]["nickname"] == "Rob"


def test_bad_jwt() -> None:
    code, _ = create_lobby()
    resp = client.get(
        f"/api/v1/lobbies/{code}", headers={"Authorization": "Bearer nope"}
    )
    assert resp.status_code == 401


def test_duplicate_nickname() -> None:
    code, _ = create_lobby()
    join(code, "Rob")
    resp = client.post(
        f"/api/v1/lobbies/{code}/join",
        json={"nickname": "Rob", "avatar": "🐍"},
    )
    assert resp.status_code == 409
