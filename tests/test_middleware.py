import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.app import app

client = TestClient(app)


def test_ip_whitelist_allowed():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": "127.0.0.1/32"}):
        response = client.get("/", headers={"X-Forwarded-For": "127.0.0.1"})
        assert response.status_code == 200


def test_ip_whitelist_denied():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": "192.168.1.0/24"}):
        response = client.get("/", headers={"X-Forwarded-For": "1.1.1.1"})
        assert response.status_code == 403


def test_ip_whitelist_not_configured():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": ""}):
        response = client.get("/", headers={"X-Forwarded-For": "1.1.1.1"})
        assert response.status_code == 200
