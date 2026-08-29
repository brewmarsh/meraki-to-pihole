from fastapi.testclient import TestClient

from app.app import app

client = TestClient(app, client=("127.0.0.1", 12345))


def test_csrf_protection_missing_header():
    # Attempting to POST without the X-Requested-With header should result in a 403 Forbidden
    response = client.post("/update-interval", json={"interval": 60})
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF verification failed"}


def test_csrf_protection_invalid_header():
    # Attempting to POST with an invalid X-Requested-With header should result in a 403 Forbidden
    response = client.post("/update-interval", json={"interval": 60}, headers={"X-Requested-With": "FetchAPI"})
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF verification failed"}


def test_csrf_protection_valid_header():
    # Attempting to POST with the correct X-Requested-With header should succeed
    response = client.post("/update-interval", json={"interval": 60}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 200
    assert response.json() == {"message": "Sync interval updated."}
