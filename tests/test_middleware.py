import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.app import app


def test_ip_whitelist_allowed():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": "127.0.0.1/32", "TESTING": "true"}):
        client = TestClient(app, client=("127.0.0.1", 12345))
        response = client.get("/health")
        assert response.status_code == 200


def test_ip_whitelist_denied():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": "192.168.1.0/24", "TESTING": "true"}):
        client = TestClient(app, client=("1.1.1.1", 12345))
        response = client.get("/health")
        assert response.status_code == 403


def test_ip_whitelist_not_configured():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": "", "TESTING": "true"}):
        client = TestClient(app, client=("1.1.1.1", 12345))
        response = client.get("/health")
        assert response.status_code == 200
