"""Tests for FDC API routes."""

import pytest
from fastapi.testclient import TestClient

from myeap.api.main import app
from myeap.api.routes.fdc import _faults, _fault_history


@pytest.fixture
def client():
    """Create test client and clean stores."""
    _faults.clear()
    _fault_history.clear()
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c
    _faults.clear()
    _fault_history.clear()


@pytest.fixture
def sample_fault_data():
    """Sample fault detection data."""
    return {
        "equipment_id": "EQ001",
        "fault_type": "temp_drift",
        "severity": "warning",
        "affected_parameters": ["temperature", "pressure"],
        "confidence": 0.85,
    }


class TestFaultDetection:
    """Test fault detection endpoint."""

    def test_detect_fault(self, client, sample_fault_data):
        """Test detecting a new fault."""
        response = client.post("/api/v1/fdc/detect", json=sample_fault_data)
        assert response.status_code == 201
        data = response.json()
        assert data["fault_type"] == "temp_drift"
        assert data["severity"] == "warning"
        assert data["equipment_id"] == "EQ001"
        assert data["status"] == "detected"
        assert data["category"] == "temperature"

    def test_detect_fault_missing_equipment(self, client):
        """Test detecting fault without equipment_id."""
        response = client.post("/api/v1/fdc/detect", json={"fault_type": "temp_drift"})
        assert response.status_code == 400

    def test_detect_fault_unknown_type(self, client):
        """Test detecting fault with unknown type."""
        response = client.post("/api/v1/fdc/detect", json={
            "equipment_id": "EQ001",
            "fault_type": "unknown_type",
        })
        assert response.status_code == 201
        assert response.json()["fault_type"] == "unknown"


class TestFaultList:
    """Test fault listing."""

    def test_list_empty(self, client):
        """Test listing when no faults exist."""
        response = client.get("/api/v1/fdc/faults")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_data(self, client, sample_fault_data):
        """Test listing faults."""
        client.post("/api/v1/fdc/detect", json=sample_fault_data)
        response = client.get("/api/v1/fdc/faults")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_equipment_filter(self, client):
        """Test filtering by equipment."""
        client.post("/api/v1/fdc/detect", json={"equipment_id": "EQ001", "fault_type": "temp_drift"})
        client.post("/api/v1/fdc/detect", json={"equipment_id": "EQ002", "fault_type": "pressure_drift"})

        response = client.get("/api/v1/fdc/faults?equipment_id=EQ001")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_severity_filter(self, client):
        """Test filtering by severity."""
        client.post("/api/v1/fdc/detect", json={"equipment_id": "EQ001", "severity": "critical"})
        client.post("/api/v1/fdc/detect", json={"equipment_id": "EQ002", "severity": "warning"})

        response = client.get("/api/v1/fdc/faults?severity=critical")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_category_filter(self, client):
        """Test filtering by category."""
        client.post("/api/v1/fdc/detect", json={"equipment_id": "EQ001", "fault_type": "temp_drift"})
        client.post("/api/v1/fdc/detect", json={"equipment_id": "EQ002", "fault_type": "pressure_drift"})

        response = client.get("/api/v1/fdc/faults?category=temperature")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_fault_stats(self, client, sample_fault_data):
        """Test fault statistics."""
        client.post("/api/v1/fdc/detect", json=sample_fault_data)
        response = client.get("/api/v1/fdc/faults/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["active_count"] == 1
        assert "by_severity" in data
        assert "by_category" in data


class TestFaultLifecycle:
    """Test fault lifecycle management."""

    def test_get_fault(self, client, sample_fault_data):
        """Test getting fault by ID."""
        create_resp = client.post("/api/v1/fdc/detect", json=sample_fault_data)
        fault_id = create_resp.json()["fault_id"]

        response = client.get(f"/api/v1/fdc/faults/{fault_id}")
        assert response.status_code == 200
        assert response.json()["fault_id"] == fault_id

    def test_get_fault_not_found(self, client):
        """Test getting non-existent fault."""
        response = client.get("/api/v1/fdc/faults/NONEXIST")
        assert response.status_code == 404

    def test_analyze_fault(self, client, sample_fault_data):
        """Test analyzing a fault."""
        create_resp = client.post("/api/v1/fdc/detect", json=sample_fault_data)
        fault_id = create_resp.json()["fault_id"]

        response = client.post(f"/api/v1/fdc/faults/{fault_id}/analyze")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "analyzing"
        assert "analysis_started_at" in data

    def test_analyze_fault_not_found(self, client):
        """Test analyzing non-existent fault."""
        response = client.post("/api/v1/fdc/faults/NONEXIST/analyze")
        assert response.status_code == 404

    def test_confirm_fault(self, client, sample_fault_data):
        """Test confirming a fault."""
        create_resp = client.post("/api/v1/fdc/detect", json=sample_fault_data)
        fault_id = create_resp.json()["fault_id"]

        response = client.post(f"/api/v1/fdc/faults/{fault_id}/confirm", json={
            "root_cause": "Heater PID drift",
            "confidence": 0.95,
            "recommendations": ["Replace heater element", "Recalibrate PID"],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
        assert data["root_cause"] == "Heater PID drift"
        assert data["confidence"] == 0.95

    def test_confirm_fault_not_found(self, client):
        """Test confirming non-existent fault."""
        response = client.post("/api/v1/fdc/faults/NONEXIST/confirm", json={})
        assert response.status_code == 404

    def test_resolve_fault(self, client, sample_fault_data):
        """Test resolving a fault."""
        create_resp = client.post("/api/v1/fdc/detect", json=sample_fault_data)
        fault_id = create_resp.json()["fault_id"]

        response = client.post(f"/api/v1/fdc/faults/{fault_id}/resolve")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"

        # Should be removed from active faults
        get_resp = client.get(f"/api/v1/fdc/faults/{fault_id}")
        assert get_resp.status_code == 404

    def test_resolve_fault_not_found(self, client):
        """Test resolving non-existent fault."""
        response = client.post("/api/v1/fdc/faults/NONEXIST/resolve")
        assert response.status_code == 404

    def test_dismiss_fault(self, client, sample_fault_data):
        """Test dismissing a fault."""
        create_resp = client.post("/api/v1/fdc/detect", json=sample_fault_data)
        fault_id = create_resp.json()["fault_id"]

        response = client.post(f"/api/v1/fdc/faults/{fault_id}/dismiss?reason=False+positive")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "dismissed"

    def test_dismiss_fault_not_found(self, client):
        """Test dismissing non-existent fault."""
        response = client.post("/api/v1/fdc/faults/NONEXIST/dismiss?reason=X")
        assert response.status_code == 404

    def test_include_resolved_in_list(self, client, sample_fault_data):
        """Test including resolved faults in listing."""
        create_resp = client.post("/api/v1/fdc/detect", json=sample_fault_data)
        fault_id = create_resp.json()["fault_id"]
        client.post(f"/api/v1/fdc/faults/{fault_id}/resolve")

        # Without include_resolved
        response = client.get("/api/v1/fdc/faults")
        assert response.status_code == 200
        assert len(response.json()) == 0

        # With include_resolved
        response = client.get("/api/v1/fdc/faults?include_resolved=true")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestFDCMetadataEndpoints:
    """Test FDC metadata endpoints."""

    def test_list_fault_types(self, client):
        """Test listing fault types."""
        response = client.get("/api/v1/fdc/fault-types")
        assert response.status_code == 200
        types = response.json()
        assert len(types) > 0
        values = [t["value"] for t in types]
        assert "temp_drift" in values
        assert "pressure_drift" in values

    def test_list_severities(self, client):
        """Test listing severity levels."""
        response = client.get("/api/v1/fdc/severities")
        assert response.status_code == 200
        sevs = response.json()
        assert len(sevs) > 0
        values = [s["value"] for s in sevs]
        assert "critical" in values
        assert "warning" in values
