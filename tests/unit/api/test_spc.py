"""Tests for SPC API routes."""

import pytest
from fastapi.testclient import TestClient

from myeap.api.main import app
from myeap.api.routes.spc import _charts, _data_points


@pytest.fixture
def client():
    """Create test client and clean stores."""
    _charts.clear()
    _data_points.clear()
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c
    _charts.clear()
    _data_points.clear()


@pytest.fixture
def sample_chart():
    """Sample chart data."""
    return {
        "chart_id": "CHART-001",
        "chart_type": "x_mr",
        "parameter_name": "temperature",
        "equipment_id": "EQ001",
        "limits": {
            "ucl": 450.0,
            "cl": 400.0,
            "lcl": 350.0,
        },
    }


class TestChartEndpoints:
    """Test SPC chart endpoints."""

    def test_list_charts_empty(self, client):
        """Test listing charts when empty."""
        response = client.get("/api/v1/spc/charts")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_chart(self, client, sample_chart):
        """Test creating a control chart."""
        response = client.post("/api/v1/spc/charts", json=sample_chart)
        assert response.status_code == 201
        data = response.json()
        assert data["chart_id"] == "CHART-001"
        assert data["chart_type"] == "x_mr"
        assert data["parameter_name"] == "temperature"

    def test_create_chart_duplicate(self, client, sample_chart):
        """Test creating duplicate chart."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.post("/api/v1/spc/charts", json=sample_chart)
        assert response.status_code == 409

    def test_get_chart(self, client, sample_chart):
        """Test getting chart by ID."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.get("/api/v1/spc/charts/CHART-001")
        assert response.status_code == 200
        assert response.json()["chart_id"] == "CHART-001"

    def test_get_chart_not_found(self, client):
        """Test getting non-existent chart."""
        response = client.get("/api/v1/spc/charts/NONEXIST")
        assert response.status_code == 404

    def test_update_chart(self, client, sample_chart):
        """Test updating chart."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.put("/api/v1/spc/charts/CHART-001", json={
            "chart_type": "x_bar_r",
            "limits": {"ucl": 500.0, "cl": 400.0, "lcl": 300.0},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["chart_type"] == "x_bar_r"

    def test_update_chart_not_found(self, client):
        """Test updating non-existent chart."""
        response = client.put("/api/v1/spc/charts/NONEXIST", json={"chart_type": "c"})
        assert response.status_code == 404

    def test_delete_chart(self, client, sample_chart):
        """Test deleting chart."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.delete("/api/v1/spc/charts/CHART-001")
        assert response.status_code == 204

    def test_delete_chart_not_found(self, client):
        """Test deleting non-existent chart."""
        response = client.delete("/api/v1/spc/charts/NONEXIST")
        assert response.status_code == 404

    def test_list_with_filters(self, client, sample_chart):
        """Test listing charts with filters."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        client.post("/api/v1/spc/charts", json={
            "chart_id": "CHART-002",
            "chart_type": "c",
            "equipment_id": "EQ002",
        })

        response = client.get("/api/v1/spc/charts?equipment_id=EQ001")
        assert response.status_code == 200
        assert len(response.json()) == 1

        response = client.get("/api/v1/spc/charts?chart_type=c")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestChartDataEndpoints:
    """Test SPC chart data endpoints."""

    def test_add_data_point(self, client, sample_chart):
        """Test adding a data point."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.post("/api/v1/spc/charts/CHART-001/data", json={
            "value": 400.5,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["chart_id"] == "CHART-001"
        assert data["data_point_count"] == 1
        assert data["violations"] == []

    def test_add_data_point_ucl_violation(self, client, sample_chart):
        """Test data point exceeding UCL."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.post("/api/v1/spc/charts/CHART-001/data", json={
            "value": 500.0,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["is_out_of_control"] is True
        assert len(data["violations"]) > 0

    def test_add_data_point_lcl_violation(self, client, sample_chart):
        """Test data point below LCL."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.post("/api/v1/spc/charts/CHART-001/data", json={
            "value": 300.0,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["is_out_of_control"] is True

    def test_add_data_point_no_violation(self, client, sample_chart):
        """Test normal data point."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.post("/api/v1/spc/charts/CHART-001/data", json={
            "value": 410.0,
        })
        assert response.status_code == 200
        assert response.json()["violations"] == []

    def test_add_data_point_missing_value(self, client, sample_chart):
        """Test adding data point without value."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.post("/api/v1/spc/charts/CHART-001/data", json={})
        assert response.status_code == 400

    def test_add_data_point_chart_not_found(self, client):
        """Test adding data to non-existent chart."""
        response = client.post("/api/v1/spc/charts/NONEXIST/data", json={"value": 100})
        assert response.status_code == 404

    def test_get_chart_data(self, client, sample_chart):
        """Test getting chart data points."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        client.post("/api/v1/spc/charts/CHART-001/data", json={"value": 400})
        client.post("/api/v1/spc/charts/CHART-001/data", json={"value": 410})

        response = client.get("/api/v1/spc/charts/CHART-001/data")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_chart_data_not_found(self, client):
        """Test getting data of non-existent chart."""
        response = client.get("/api/v1/spc/charts/NONEXIST/data")
        assert response.status_code == 404

    def test_chart_statistics(self, client, sample_chart):
        """Test getting chart statistics."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        for v in [400, 410, 395, 405, 402]:
            client.post("/api/v1/spc/charts/CHART-001/data", json={"value": v})

        response = client.get("/api/v1/spc/charts/CHART-001/statistics")
        assert response.status_code == 200
        data = response.json()
        assert data["data_point_count"] == 5
        assert "mean" in data
        assert "std" in data
        assert "min" in data
        assert "max" in data

    def test_chart_statistics_empty(self, client, sample_chart):
        """Test statistics with no data."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        response = client.get("/api/v1/spc/charts/CHART-001/statistics")
        assert response.status_code == 200
        data = response.json()
        assert data["data_point_count"] == 0
        assert data["mean"] is None

    def test_reset_chart_data(self, client, sample_chart):
        """Test resetting chart data."""
        client.post("/api/v1/spc/charts", json=sample_chart)
        client.post("/api/v1/spc/charts/CHART-001/data", json={"value": 400})
        client.post("/api/v1/spc/charts/CHART-001/data", json={"value": 410})

        response = client.post("/api/v1/spc/charts/CHART-001/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["reset"] is True
        assert data["previous_data_count"] == 2

        # Verify data is cleared
        data_resp = client.get("/api/v1/spc/charts/CHART-001/data")
        assert len(data_resp.json()) == 0

    def test_reset_chart_not_found(self, client):
        """Test resetting non-existent chart."""
        response = client.post("/api/v1/spc/charts/NONEXIST/reset")
        assert response.status_code == 404


class TestSPCMetadataEndpoints:
    """Test SPC metadata endpoints."""

    def test_list_chart_types(self, client):
        """Test listing supported chart types."""
        response = client.get("/api/v1/spc/chart-types")
        assert response.status_code == 200
        types = response.json()
        assert len(types) > 0
        values = [t["value"] for t in types]
        assert "x_mr" in values
        assert "x_bar_r" in values

    def test_list_spc_rules(self, client):
        """Test listing SPC rules."""
        response = client.get("/api/v1/spc/rules")
        assert response.status_code == 200
        rules = response.json()
        assert len(rules) > 0
        assert "rule_id" in rules[0]
