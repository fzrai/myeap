"""Tests for Alarm API routes."""

import pytest
from fastapi.testclient import TestClient

from myeap.api.main import app
from myeap.api.routes.alarm import _active_alarms, _alarm_definitions, _alarm_history, _suppressed_codes


@pytest.fixture
def client():
    """Create test client and clean stores."""
    _active_alarms.clear()
    _alarm_definitions.clear()
    _alarm_history.clear()
    _suppressed_codes.clear()
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c
    _active_alarms.clear()
    _alarm_definitions.clear()
    _alarm_history.clear()
    _suppressed_codes.clear()


@pytest.fixture
def sample_alarm_data():
    """Sample alarm data."""
    return {
        "equipment_id": "EQ001",
        "alarm_code": "ALM-001",
        "alarm_text": "Temperature exceeds limit",
        "severity": "critical",
    }


@pytest.fixture
def sample_definition_data():
    """Sample alarm definition data."""
    return {
        "alarm_code": "ALM-001",
        "equipment_type": "cvd",
        "severity": "critical",
        "description": "Temperature exceeds upper limit",
        "default_text": "Temperature alarm",
        "suggested_action": "Check heater control",
    }


class TestAlarmList:
    """Test alarm listing."""

    def test_list_empty(self, client):
        """Test listing when no alarms exist."""
        response = client.get("/api/v1/alarms/")
        assert response.status_code == 200
        assert response.json() == []

    def test_raise_then_list(self, client, sample_alarm_data):
        """Test listing after raising alarm."""
        client.post("/api/v1/alarms/raise", json=sample_alarm_data)
        response = client.get("/api/v1/alarms/")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_equipment_filter(self, client):
        """Test filtering by equipment."""
        client.post("/api/v1/alarms/raise", json={"equipment_id": "EQ001", "alarm_code": "A1", "severity": "warning"})
        client.post("/api/v1/alarms/raise", json={"equipment_id": "EQ002", "alarm_code": "A2", "severity": "warning"})

        response = client.get("/api/v1/alarms/?equipment_id=EQ001")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_severity_filter(self, client):
        """Test filtering by severity."""
        client.post("/api/v1/alarms/raise", json={"equipment_id": "EQ001", "alarm_code": "A1", "severity": "critical"})
        client.post("/api/v1/alarms/raise", json={"equipment_id": "EQ002", "alarm_code": "A2", "severity": "warning"})

        response = client.get("/api/v1/alarms/?severity=critical")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_status_filter(self, client, sample_alarm_data):
        """Test filtering by status."""
        create_resp = client.post("/api/v1/alarms/raise", json=sample_alarm_data)
        alarm_id = create_resp.json()["id"]
        client.post(f"/api/v1/alarms/{alarm_id}/acknowledge?acknowledged_by=admin")

        response = client.get("/api/v1/alarms/?status=acknowledged")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestAlarmCRUD:
    """Test alarm CRUD operations."""

    def test_raise_alarm(self, client, sample_alarm_data):
        """Test raising a new alarm."""
        response = client.post("/api/v1/alarms/raise", json=sample_alarm_data)
        assert response.status_code == 201
        data = response.json()
        assert data["equipment_id"] == "EQ001"
        assert data["alarm_code"] == "ALM-001"
        assert data["severity"] == "critical"
        assert data["status"] == "raised"

    def test_raise_alarm_missing_equipment(self, client):
        """Test raising alarm without equipment_id."""
        response = client.post("/api/v1/alarms/raise", json={"alarm_code": "X"})
        assert response.status_code == 400

    def test_raise_suppressed_alarm(self, client, sample_alarm_data):
        """Test raising a suppressed alarm code."""
        _suppressed_codes.add("ALM-001")
        response = client.post("/api/v1/alarms/raise", json=sample_alarm_data)
        assert response.status_code == 409

    def test_get_alarm(self, client, sample_alarm_data):
        """Test getting alarm by ID."""
        create_resp = client.post("/api/v1/alarms/raise", json=sample_alarm_data)
        alarm_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/alarms/{alarm_id}")
        assert response.status_code == 200
        assert response.json()["id"] == alarm_id

    def test_get_alarm_not_found(self, client):
        """Test getting non-existent alarm."""
        response = client.get("/api/v1/alarms/nonexistent")
        assert response.status_code == 404

    def test_acknowledge_alarm(self, client, sample_alarm_data):
        """Test acknowledging an alarm."""
        create_resp = client.post("/api/v1/alarms/raise", json=sample_alarm_data)
        alarm_id = create_resp.json()["id"]

        response = client.post(f"/api/v1/alarms/{alarm_id}/acknowledge?acknowledged_by=admin")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "acknowledged"
        assert data["acknowledged_by"] == "admin"

    def test_acknowledge_already_acknowledged(self, client, sample_alarm_data):
        """Test acknowledging already acknowledged alarm."""
        create_resp = client.post("/api/v1/alarms/raise", json=sample_alarm_data)
        alarm_id = create_resp.json()["id"]

        client.post(f"/api/v1/alarms/{alarm_id}/acknowledge?acknowledged_by=admin")
        response = client.post(f"/api/v1/alarms/{alarm_id}/acknowledge?acknowledged_by=admin2")
        assert response.status_code == 400

    def test_clear_alarm(self, client, sample_alarm_data):
        """Test clearing an alarm."""
        create_resp = client.post("/api/v1/alarms/raise", json=sample_alarm_data)
        alarm_id = create_resp.json()["id"]

        response = client.post(f"/api/v1/alarms/{alarm_id}/clear?cleared_by=admin")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleared"
        assert data["cleared_by"] == "admin"

    def test_clear_alarm_not_found(self, client):
        """Test clearing non-existent alarm."""
        response = client.post("/api/v1/alarms/nonexistent/clear?cleared_by=admin")
        assert response.status_code == 404

    def test_alarm_stats(self, client):
        """Test alarm statistics endpoint."""
        client.post("/api/v1/alarms/raise", json={"equipment_id": "EQ001", "alarm_code": "A1", "severity": "critical"})
        client.post("/api/v1/alarms/raise", json={"equipment_id": "EQ001", "alarm_code": "A2", "severity": "warning"})

        response = client.get("/api/v1/alarms/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["active_count"] == 2
        assert "by_severity" in data
        assert "by_equipment" in data


class TestAlarmDefinitions:
    """Test alarm definition endpoints."""

    def test_list_definitions_empty(self, client):
        """Test listing definitions when empty."""
        response = client.get("/api/v1/alarms/definitions")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_definition(self, client, sample_definition_data):
        """Test creating alarm definition."""
        response = client.post("/api/v1/alarms/definitions", json=sample_definition_data)
        assert response.status_code == 201
        data = response.json()
        assert data["alarm_code"] == "ALM-001"

    def test_list_definitions(self, client, sample_definition_data):
        """Test listing alarm definitions."""
        client.post("/api/v1/alarms/definitions", json=sample_definition_data)
        response = client.get("/api/v1/alarms/definitions")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestAlarmSuppression:
    """Test alarm suppression endpoints."""

    def test_suppress_alarm(self, client):
        """Test suppressing alarm code."""
        response = client.post("/api/v1/alarms/suppress?alarm_code=ALM-001")
        assert response.status_code == 200
        assert response.json()["suppressed"] is True

    def test_unsuppress_alarm(self, client):
        """Test unsuppressing alarm code."""
        _suppressed_codes.add("ALM-001")
        response = client.delete("/api/v1/alarms/suppress?alarm_code=ALM-001")
        assert response.status_code == 200
        assert response.json()["suppressed"] is False

    def test_unsuppress_not_suppressed(self, client):
        """Test unsuppressing non-suppressed alarm code."""
        response = client.delete("/api/v1/alarms/suppress?alarm_code=ALM-XYZ")
        assert response.status_code == 200
        assert response.json()["was_suppressed"] is False
