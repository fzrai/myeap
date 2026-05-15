"""Tests for FastAPI app initialization, health, root, and metrics endpoints."""

import pytest
from fastapi.testclient import TestClient

from myeap.api.main import app


@pytest.fixture
def client():
    """Create test client with auth header."""
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c


class TestRootEndpoints:
    """Test root-level endpoints."""

    def test_root(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_health(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_metrics(self, client):
        """Test metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_openapi_json(self, client):
        """Test OpenAPI schema endpoint."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert data["info"]["title"] == "MyEAP"

    def test_docs_endpoint(self, client):
        """Test Swagger docs endpoint."""
        response = client.get("/docs")
        assert response.status_code == 200


class TestMiddleware:
    """Test middleware functionality."""

    def test_request_id_header(self, client):
        """Test that X-Request-ID is added to responses."""
        response = client.get("/health")
        assert "X-Request-ID" in response.headers

    def test_process_time_header(self, client):
        """Test that X-Process-Time is added to responses."""
        response = client.get("/health")
        assert "X-Process-Time" in response.headers

    def test_security_headers(self, client):
        """Test security headers are present."""
        response = client.get("/health")
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"


class TestSystemEndpoints:
    """Test system endpoints under /api/v1/system."""

    def test_system_health(self, client):
        """Test system health endpoint."""
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "api" in data["components"]

    def test_system_info(self, client):
        """Test system info endpoint."""
        response = client.get("/api/v1/system/info")
        assert response.status_code == 200
        data = response.json()
        assert data["app_name"] == "MyEAP"
        assert data["version"] == "0.1.0"

    def test_version_endpoint(self, client):
        """Test version endpoint."""
        response = client.get("/api/v1/system/version")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "0.1.0"

    def test_readiness_probe(self, client):
        """Test readiness probe."""
        response = client.get("/api/v1/system/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_liveness_probe(self, client):
        """Test liveness probe."""
        response = client.get("/api/v1/system/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_list_endpoints(self, client):
        """Test endpoints listing."""
        response = client.get("/api/v1/system/endpoints")
        assert response.status_code == 200

    def test_system_config_requires_admin(self):
        """Test that config endpoint requires admin."""
        # Use client without auth to verify auth is required
        no_auth_client = TestClient(app)
        response = no_auth_client.get("/api/v1/system/config")
        assert response.status_code == 401
