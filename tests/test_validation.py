from pathlib import Path

from fastapi.testclient import TestClient

from app.app import app

client = TestClient(app)


def test_update_interval_valid():
    response = client.post("/update-interval", json={"interval": 120})
    assert response.status_code == 200
    assert response.json() == {"message": "Sync interval updated."}


def test_update_interval_invalid():
    response = client.post("/update-interval", json={"interval": "abc"})
    assert response.status_code == 422  # Unprocessable Entity


def test_clear_log_valid():
    log_file = Path('/app/logs/sync.log')
    log_file.parent.mkdir(exist_ok=True)
    log_file.touch()
    response = client.post("/clear-log", json={"log": "sync"})
    assert response.status_code == 200
    assert response.json() == {"message": "Sync log cleared."}


def test_clear_log_invalid():
    response = client.post("/clear-log", json={"log": "invalid"})
    assert response.status_code == 400
    assert response.json() == {"message": "Invalid log type."}

def test_clear_log_missing_log():
    response = client.post("/clear-log", json={})
    assert response.status_code == 422 # Unprocessable Entity
