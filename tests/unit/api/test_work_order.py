"""Tests for Work Order API routes."""

import pytest
from fastapi.testclient import TestClient

from myeap.api.main import app
from myeap.api.routes.work_order import _work_orders


@pytest.fixture
def client():
    """Create test client and clean store."""
    _work_orders.clear()
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c
    _work_orders.clear()


@pytest.fixture
def sample_work_order():
    """Sample work order data."""
    return {
        "mes_id": "WO-001",
        "lot_id": "LOT-1001",
        "recipe_name": "CVD Oxide",
        "wafer_count": 25,
        "priority": 3,
        "equipment_id": "EQ001",
    }


class TestWorkOrderList:
    """Test work order listing."""

    def test_list_empty(self, client):
        """Test listing when empty."""
        response = client.get("/api/v1/work-orders/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_data(self, client, sample_work_order):
        """Test listing with data."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.get("/api/v1/work-orders/")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_status_filter(self, client, sample_work_order):
        """Test filtering by status."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.get("/api/v1/work-orders/?status=PENDING")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_lot_filter(self, client, sample_work_order):
        """Test filtering by lot."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.get("/api/v1/work-orders/?lot_id=LOT-1001")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestWorkOrderCRUD:
    """Test work order CRUD."""

    def test_create(self, client, sample_work_order):
        """Test creating work order."""
        response = client.post("/api/v1/work-orders/", json=sample_work_order)
        assert response.status_code == 201
        data = response.json()
        assert data["mes_id"] == "WO-001"
        assert data["status"] == "PENDING"

    def test_create_duplicate(self, client, sample_work_order):
        """Test creating duplicate work order."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.post("/api/v1/work-orders/", json=sample_work_order)
        assert response.status_code == 409

    def test_create_missing_mes_id(self, client):
        """Test creating without mes_id."""
        response = client.post("/api/v1/work-orders/", json={"lot_id": "X"})
        assert response.status_code == 400

    def test_get(self, client, sample_work_order):
        """Test getting work order."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.get("/api/v1/work-orders/WO-001")
        assert response.status_code == 200
        assert response.json()["mes_id"] == "WO-001"

    def test_get_not_found(self, client):
        """Test getting non-existent work order."""
        response = client.get("/api/v1/work-orders/NONEXIST")
        assert response.status_code == 404

    def test_update(self, client, sample_work_order):
        """Test updating work order."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.put("/api/v1/work-orders/WO-001", json={
            **sample_work_order,
            "priority": 1,
        })
        assert response.status_code == 200
        assert response.json()["priority"] == 1

    def test_update_not_found(self, client):
        """Test updating non-existent work order."""
        response = client.put("/api/v1/work-orders/NONEXIST", json={"lot_id": "X"})
        assert response.status_code == 404

    def test_patch(self, client, sample_work_order):
        """Test partial update."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.patch("/api/v1/work-orders/WO-001", json={"priority": 9})
        assert response.status_code == 200
        assert response.json()["priority"] == 9

    def test_patch_not_found(self, client):
        """Test partial update of non-existent work order."""
        response = client.patch("/api/v1/work-orders/NONEXIST", json={"priority": 9})
        assert response.status_code == 404

    def test_delete(self, client, sample_work_order):
        """Test deleting work order."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.delete("/api/v1/work-orders/WO-001")
        assert response.status_code == 204

    def test_delete_not_found(self, client):
        """Test deleting non-existent work order."""
        response = client.delete("/api/v1/work-orders/NONEXIST")
        assert response.status_code == 404


class TestWorkOrderWorkflow:
    """Test work order workflow (start, complete, abort)."""

    def test_start_work_order(self, client, sample_work_order):
        """Test starting a work order."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.post("/api/v1/work-orders/WO-001/start")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "RUNNING"
        assert data["started_at"] is not None

    def test_start_already_running(self, client, sample_work_order):
        """Test starting already running work order."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        client.post("/api/v1/work-orders/WO-001/start")
        response = client.post("/api/v1/work-orders/WO-001/start")
        assert response.status_code == 400

    def test_complete_work_order(self, client, sample_work_order):
        """Test completing a work order."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        client.post("/api/v1/work-orders/WO-001/start")
        response = client.post("/api/v1/work-orders/WO-001/complete?good_count=20&reject_count=5")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["progress"] == 100
        assert data["good_count"] == 20

    def test_complete_not_running(self, client, sample_work_order):
        """Test completing non-running work order."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.post("/api/v1/work-orders/WO-001/complete?good_count=0&reject_count=0")
        assert response.status_code == 400

    def test_abort_work_order(self, client, sample_work_order):
        """Test aborting a work order."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        response = client.post("/api/v1/work-orders/WO-001/abort?reason=Equipment+error")
        assert response.status_code == 200
        assert response.json()["status"] == "ABORTED"

    def test_abort_not_found(self, client):
        """Test aborting non-existent work order."""
        response = client.post("/api/v1/work-orders/NONEXIST/abort?reason=X")
        assert response.status_code == 404

    def test_progress(self, client, sample_work_order):
        """Test getting work order progress."""
        client.post("/api/v1/work-orders/", json=sample_work_order)
        client.post("/api/v1/work-orders/WO-001/start")
        response = client.get("/api/v1/work-orders/WO-001/progress")
        assert response.status_code == 200
        data = response.json()
        assert data["mes_id"] == "WO-001"
        assert data["status"] == "RUNNING"

    def test_progress_not_found(self, client):
        """Test getting progress of non-existent work order."""
        response = client.get("/api/v1/work-orders/NONEXIST/progress")
        assert response.status_code == 404

    def test_list_by_lot(self, client):
        """Test listing work orders by lot."""
        client.post("/api/v1/work-orders/", json={"mes_id": "WO-001", "lot_id": "LOT-X", "wafer_count": 10})
        client.post("/api/v1/work-orders/", json={"mes_id": "WO-002", "lot_id": "LOT-X", "wafer_count": 10})
        client.post("/api/v1/work-orders/", json={"mes_id": "WO-003", "lot_id": "LOT-Y", "wafer_count": 10})

        response = client.get("/api/v1/work-orders/lot/LOT-X")
        assert response.status_code == 200
        assert len(response.json()) == 2
