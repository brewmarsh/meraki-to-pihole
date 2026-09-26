from fastapi.testclient import TestClient

from app.app import app


def test_csrf_missing_header():
    client = TestClient(app, client=("127.0.0.1", 12345))
    response = client.post("/clear-log", json={"log": "sync"})
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF verification failed"}


def test_csrf_with_header():
    client = TestClient(app, client=("127.0.0.1", 12345))
    response = client.post("/clear-log", headers={"X-Requested-With": "XMLHttpRequest"}, json={"log": "sync"})
    assert response.status_code != 403
