"""Tests for Tracking API routes."""

import pytest
from fastapi.testclient import TestClient

from myeap.api.main import app
from myeap.api.routes.tracking import _carriers, _wafers, _wafer_events


@pytest.fixture
def client():
    """Create test client and clean stores."""
    _carriers.clear()
    _wafers.clear()
    _wafer_events.clear()
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c
    _carriers.clear()
    _wafers.clear()
    _wafer_events.clear()


@pytest.fixture
def sample_carrier():
    """Sample carrier data."""
    return {
        "carrier_id": "FOUP-001",
        "carrier_type": "foup",
        "capacity": 25,
    }


@pytest.fixture
def sample_wafer():
    """Sample wafer data."""
    return {
        "wafer_id": "WF-001",
        "lot_id": "LOT-001",
    }


class TestCarrierEndpoints:
    """Test carrier endpoints."""

    def test_list_empty(self, client):
        """Test listing carriers when empty."""
        response = client.get("/api/v1/tracking/carriers")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_carrier(self, client, sample_carrier):
        """Test creating a carrier."""
        response = client.post("/api/v1/tracking/carriers", json=sample_carrier)
        assert response.status_code == 201
        data = response.json()
        assert data["carrier_id"] == "FOUP-001"
        assert data["capacity"] == 25

    def test_create_carrier_duplicate(self, client, sample_carrier):
        """Test creating duplicate carrier."""
        client.post("/api/v1/tracking/carriers", json=sample_carrier)
        response = client.post("/api/v1/tracking/carriers", json=sample_carrier)
        assert response.status_code == 409

    def test_create_carrier_missing_id(self, client):
        """Test creating carrier without ID."""
        response = client.post("/api/v1/tracking/carriers", json={"capacity": 25})
        assert response.status_code == 400

    def test_get_carrier(self, client, sample_carrier):
        """Test getting carrier by ID."""
        client.post("/api/v1/tracking/carriers", json=sample_carrier)
        response = client.get("/api/v1/tracking/carriers/FOUP-001")
        assert response.status_code == 200
        assert response.json()["carrier_id"] == "FOUP-001"

    def test_get_carrier_not_found(self, client):
        """Test getting non-existent carrier."""
        response = client.get("/api/v1/tracking/carriers/NONEXIST")
        assert response.status_code == 404

    def test_update_carrier(self, client, sample_carrier):
        """Test updating carrier."""
        client.post("/api/v1/tracking/carriers", json=sample_carrier)
        response = client.put("/api/v1/tracking/carriers/FOUP-001", json={
            "current_location": "EQ001",
            "status": "at_equipment",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["current_location"] == "EQ001"
        assert data["status"] == "at_equipment"

    def test_update_carrier_not_found(self, client):
        """Test updating non-existent carrier."""
        response = client.put("/api/v1/tracking/carriers/NONEXIST", json={})
        assert response.status_code == 404

    def test_delete_carrier(self, client, sample_carrier):
        """Test deleting carrier."""
        client.post("/api/v1/tracking/carriers", json=sample_carrier)
        response = client.delete("/api/v1/tracking/carriers/FOUP-001")
        assert response.status_code == 204

    def test_delete_carrier_not_found(self, client):
        """Test deleting non-existent carrier."""
        response = client.delete("/api/v1/tracking/carriers/NONEXIST")
        assert response.status_code == 404

    def test_list_with_type_filter(self, client, sample_carrier):
        """Test listing with type filter."""
        client.post("/api/v1/tracking/carriers", json=sample_carrier)
        client.post("/api/v1/tracking/carriers", json={
            "carrier_id": "FOSB-001",
            "carrier_type": "fosb",
            "capacity": 13,
        })

        response = client.get("/api/v1/tracking/carriers?carrier_type=foup")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_load_wafers(self, client, sample_carrier):
        """Test loading wafers into carrier."""
        client.post("/api/v1/tracking/carriers", json=sample_carrier)
        response = client.post(
            "/api/v1/tracking/carriers/FOUP-001/load",
            json=["WF-001", "WF-002", "WF-003"],
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["wafer_ids"]) == 3
        assert data["status"] == "loaded"

    def test_load_wafers_exceed_capacity(self, client):
        """Test loading too many wafers."""
        client.post("/api/v1/tracking/carriers", json={
            "carrier_id": "SMALL-001",
            "carrier_type": "foup",
            "capacity": 2,
        })
        response = client.post(
            "/api/v1/tracking/carriers/SMALL-001/load",
            json=["WF-001", "WF-002", "WF-003"],
        )
        assert response.status_code == 400

    def test_unload_wafers(self, client, sample_carrier):
        """Test unloading wafers from carrier."""
        client.post("/api/v1/tracking/carriers", json=sample_carrier)
        client.post("/api/v1/tracking/carriers/FOUP-001/load", json=["WF-001"])
        response = client.post("/api/v1/tracking/carriers/FOUP-001/unload")
        assert response.status_code == 200
        assert response.json()["wafer_ids"] == []


class TestWaferEndpoints:
    """Test wafer endpoints."""

    def test_list_wafers_empty(self, client):
        """Test listing wafers when empty."""
        response = client.get("/api/v1/tracking/wafers")
        assert response.status_code == 200
        assert response.json() == []

    def test_register_wafer(self, client, sample_wafer):
        """Test registering a wafer."""
        response = client.post("/api/v1/tracking/wafers", json=sample_wafer)
        assert response.status_code == 201
        data = response.json()
        assert data["wafer_id"] == "WF-001"
        assert data["lot_id"] == "LOT-001"

    def test_register_wafer_missing_ids(self, client):
        """Test registering wafer without required fields."""
        response = client.post("/api/v1/tracking/wafers", json={})
        assert response.status_code == 400

    def test_register_duplicate_wafer(self, client, sample_wafer):
        """Test registering duplicate wafer."""
        client.post("/api/v1/tracking/wafers", json=sample_wafer)
        response = client.post("/api/v1/tracking/wafers", json=sample_wafer)
        assert response.status_code == 409

    def test_get_wafer(self, client, sample_wafer):
        """Test getting wafer by ID."""
        client.post("/api/v1/tracking/wafers", json=sample_wafer)
        response = client.get("/api/v1/tracking/wafers/WF-001")
        assert response.status_code == 200
        assert response.json()["wafer_id"] == "WF-001"

    def test_get_wafer_not_found(self, client):
        """Test getting non-existent wafer."""
        response = client.get("/api/v1/tracking/wafers/NONEXIST")
        assert response.status_code == 404

    def test_list_wafers_with_lot_filter(self, client, sample_wafer):
        """Test filtering wafers by lot."""
        client.post("/api/v1/tracking/wafers", json=sample_wafer)
        client.post("/api/v1/tracking/wafers", json={"wafer_id": "WF-002", "lot_id": "LOT-002"})

        response = client.get("/api/v1/tracking/wafers?lot_id=LOT-001")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_record_wafer_event(self, client, sample_wafer):
        """Test recording a wafer event."""
        client.post("/api/v1/tracking/wafers", json=sample_wafer)
        response = client.post("/api/v1/tracking/wafers/WF-001/events", json={
            "event_type": "PROCESS_START",
            "equipment_id": "EQ001",
            "recipe_id": "R001",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == "PROCESS_START"
        assert data["wafer_id"] == "WF-001"

    def test_record_event_wafer_not_found(self, client):
        """Test recording event for non-existent wafer."""
        response = client.post("/api/v1/tracking/wafers/NONEXIST/events", json={
            "event_type": "PROCESS_START",
        })
        assert response.status_code == 404

    def test_wafer_history(self, client, sample_wafer):
        """Test getting wafer history."""
        client.post("/api/v1/tracking/wafers", json=sample_wafer)
        client.post("/api/v1/tracking/wafers/WF-001/events", json={"event_type": "LOADED"})
        client.post("/api/v1/tracking/wafers/WF-001/events", json={"event_type": "PROCESS_END"})

        response = client.get("/api/v1/tracking/wafers/WF-001/history")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_events(self, client, sample_wafer):
        """Test listing all events."""
        client.post("/api/v1/tracking/wafers", json=sample_wafer)
        client.post("/api/v1/tracking/wafers/WF-001/events", json={"event_type": "LOADED"})
        client.post("/api/v1/tracking/wafers/WF-001/events", json={"event_type": "PROCESS_START"})

        response = client.get("/api/v1/tracking/events?wafer_id=WF-001")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_trace_lot(self, client):
        """Test lot traceability."""
        client.post("/api/v1/tracking/wafers", json={"wafer_id": "WF-001", "lot_id": "LOT-X"})
        client.post("/api/v1/tracking/wafers", json={"wafer_id": "WF-002", "lot_id": "LOT-X"})
        client.post("/api/v1/tracking/wafers/WF-001/events", json={"event_type": "PROCESS_START", "equipment_id": "EQ001"})

        response = client.get("/api/v1/tracking/trace/LOT-X")
        assert response.status_code == 200
        data = response.json()
        assert data["lot_id"] == "LOT-X"
        assert data["wafer_count"] == 2
        assert "EQ001" in data["equipment_involved"]
