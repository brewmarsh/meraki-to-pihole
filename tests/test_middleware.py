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

def test_ip_whitelist_x_forwarded_for_allowed():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": "192.168.1.0/24", "TESTING": "true", "TRUST_REVERSE_PROXY": "true"}):
        client = TestClient(app, client=("1.1.1.1", 12345))
        response = client.get("/health", headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.50"})
        assert response.status_code == 200

def test_ip_whitelist_x_forwarded_for_denied():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": "192.168.1.0/24", "TESTING": "true", "TRUST_REVERSE_PROXY": "true"}):
        client = TestClient(app, client=("192.168.1.1", 12345))
        response = client.get("/health", headers={"X-Forwarded-For": "192.168.1.50, 10.0.0.1"})
        assert response.status_code == 403

def test_ip_whitelist_x_forwarded_for_untrusted():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": "192.168.1.0/24", "TESTING": "true"}):
        client = TestClient(app, client=("10.0.0.1", 12345))
        response = client.get("/health", headers={"X-Forwarded-For": "192.168.1.50"})
        assert response.status_code == 403

def test_ip_whitelist_invalid_ip():
    with patch.dict(os.environ, {"ALLOWED_SUBNETS": "192.168.1.0/24", "TESTING": "true", "TRUST_REVERSE_PROXY": "true"}):
        client = TestClient(app, client=("1.1.1.1", 12345))
        response = client.get("/health", headers={"X-Forwarded-For": "not-an-ip"})
        assert response.status_code == 403
