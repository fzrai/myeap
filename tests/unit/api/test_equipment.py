"""Tests for Equipment API routes."""

import pytest
from fastapi.testclient import TestClient

from myeap.api.main import app
from myeap.api.routes.equipment import _equipment_store


@pytest.fixture
def client():
    """Create test client and clean store."""
    _equipment_store.clear()
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c
    _equipment_store.clear()


@pytest.fixture
def sample_equipment():
    """Sample equipment data."""
    return {
        "equipment_id": "EQ001",
        "name": "CVD Chamber 1",
        "equipment_type": "cvd",
        "host": "192.168.1.100",
        "port": 5000,
        "device_id": 1,
        "status": "IDLE",
        "manufacturer": "Applied Materials",
        "model": "Centura",
    }


class TestEquipmentList:
    """Test equipment listing."""

    def test_list_empty(self, client):
        """Test listing when no equipment exists."""
        response = client.get("/api/v1/equipment/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_data(self, client, sample_equipment):
        """Test listing equipment with data."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.get("/api/v1/equipment/")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["equipment_id"] == "EQ001"

    def test_list_with_type_filter(self, client, sample_equipment):
        """Test filtering by equipment type."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        client.post("/api/v1/equipment/", json={
            "equipment_id": "EQ002",
            "name": "Cleaner 1",
            "equipment_type": "cleaner",
        })

        response = client.get("/api/v1/equipment/?equipment_type=cvd")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["equipment_type"] == "cvd"

    def test_list_with_status_filter(self, client, sample_equipment):
        """Test filtering by status."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        client.post("/api/v1/equipment/", json={
            "equipment_id": "EQ002",
            "name": "Cleaner 1",
            "equipment_type": "cleaner",
            "status": "RUNNING",
        })

        response = client.get("/api/v1/equipment/?status=IDLE")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1

    def test_list_with_pagination(self, client, sample_equipment):
        """Test pagination."""
        for i in range(5):
            client.post("/api/v1/equipment/", json={
                "equipment_id": f"EQ{i:03d}",
                "name": f"Equipment {i}",
                "equipment_type": "cvd",
            })

        response = client.get("/api/v1/equipment/?limit=2&offset=0")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2

    def test_list_with_stats(self, client, sample_equipment):
        """Test equipment stats endpoint."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.get("/api/v1/equipment/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


class TestEquipmentCRUD:
    """Test equipment CRUD operations."""

    def test_create_equipment(self, client, sample_equipment):
        """Test creating equipment."""
        response = client.post("/api/v1/equipment/", json=sample_equipment)
        assert response.status_code == 201
        data = response.json()
        assert data["equipment_id"] == "EQ001"
        assert data["name"] == "CVD Chamber 1"
        assert data["status"] == "IDLE"

    def test_create_equipment_missing_id(self, client):
        """Test creating equipment without ID."""
        response = client.post("/api/v1/equipment/", json={"name": "No ID"})
        assert response.status_code == 400

    def test_create_equipment_duplicate(self, client, sample_equipment):
        """Test creating duplicate equipment."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.post("/api/v1/equipment/", json=sample_equipment)
        assert response.status_code == 409

    def test_get_equipment(self, client, sample_equipment):
        """Test getting equipment by ID."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.get("/api/v1/equipment/EQ001")
        assert response.status_code == 200
        data = response.json()
        assert data["equipment_id"] == "EQ001"
        assert data["name"] == "CVD Chamber 1"

    def test_get_equipment_not_found(self, client):
        """Test getting non-existent equipment."""
        response = client.get("/api/v1/equipment/NONEXIST")
        assert response.status_code == 404

    def test_update_equipment(self, client, sample_equipment):
        """Test updating equipment."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.put("/api/v1/equipment/EQ001", json={
            **sample_equipment,
            "name": "Updated CVD Chamber 1",
            "status": "RUNNING",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated CVD Chamber 1"
        assert data["status"] == "RUNNING"

    def test_update_equipment_not_found(self, client):
        """Test updating non-existent equipment."""
        response = client.put("/api/v1/equipment/NONEXIST", json={"name": "X"})
        assert response.status_code == 404

    def test_patch_equipment(self, client, sample_equipment):
        """Test partial update."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.patch("/api/v1/equipment/EQ001", json={
            "status": "MAINTENANCE",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "MAINTENANCE"
        assert data["name"] == "CVD Chamber 1"

    def test_patch_equipment_not_found(self, client):
        """Test partial update of non-existent equipment."""
        response = client.patch("/api/v1/equipment/NONEXIST", json={"status": "IDLE"})
        assert response.status_code == 404

    def test_delete_equipment(self, client, sample_equipment):
        """Test deleting equipment."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.delete("/api/v1/equipment/EQ001")
        assert response.status_code == 204

        response = client.get("/api/v1/equipment/EQ001")
        assert response.status_code == 404

    def test_delete_equipment_not_found(self, client):
        """Test deleting non-existent equipment."""
        response = client.delete("/api/v1/equipment/NONEXIST")
        assert response.status_code == 404


class TestEquipmentStatus:
    """Test equipment status endpoints."""

    def test_get_status(self, client, sample_equipment):
        """Test getting equipment status."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.get("/api/v1/equipment/EQ001/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "IDLE"
        assert "is_connected" in data

    def test_get_status_not_found(self, client):
        """Test getting status of non-existent equipment."""
        response = client.get("/api/v1/equipment/NONEXIST/status")
        assert response.status_code == 404


class TestEquipmentCommand:
    """Test equipment command endpoint."""

    def test_send_command(self, client, sample_equipment):
        """Test sending a command to equipment."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.post("/api/v1/equipment/EQ001/command", json={
            "command_type": "START_PROCESS",
            "parameters": {"recipe_id": "R001"},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["equipment_id"] == "EQ001"
        assert data["command_type"] == "START_PROCESS"
        assert data["status"] == "SENT"

    def test_send_command_not_found(self, client):
        """Test sending command to non-existent equipment."""
        response = client.post("/api/v1/equipment/NONEXIST/command", json={
            "command_type": "TEST",
        })
        assert response.status_code == 404


class TestEquipmentDetailedStats:
    """Test equipment detailed stats endpoint."""

    def test_get_detailed_stats(self, client, sample_equipment):
        """Test getting detailed equipment stats."""
        client.post("/api/v1/equipment/", json=sample_equipment)
        response = client.get("/api/v1/equipment/EQ001/stats/details")
        assert response.status_code == 200
        data = response.json()
        assert data["equipment_id"] == "EQ001"

    def test_get_detailed_stats_not_found(self, client):
        """Test detailed stats of non-existent equipment."""
        response = client.get("/api/v1/equipment/NONEXIST/stats/details")
        assert response.status_code == 404
