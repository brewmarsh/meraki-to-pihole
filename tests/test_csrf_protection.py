from fastapi.testclient import TestClient

from app.app import app

client = TestClient(app, client=("127.0.0.1", 12345))


def test_csrf_missing_header():
    response = client.post("/update-interval", json={"interval": 120})
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF check failed."}


def test_csrf_wrong_header():
    response = client.post("/update-interval", json={"interval": 120}, headers={"X-Requested-With": "Fetch"})
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF check failed."}


def test_csrf_valid_header():
    response = client.post("/update-interval", json={"interval": 120}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 200
