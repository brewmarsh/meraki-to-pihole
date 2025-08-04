from fastapi.testclient import TestClient

from app.app import app

client = TestClient(app)


def test_update_interval():
    # Given
    new_interval = "600"

    # When
    response = client.post("/update-interval", json={"interval": new_interval})

    # Then
    assert response.status_code == 200
    assert response.json() == {"message": "Sync interval updated."}
