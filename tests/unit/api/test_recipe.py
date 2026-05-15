"""Tests for Recipe API routes."""

import pytest
from fastapi.testclient import TestClient

from myeap.api.main import app
from myeap.api.routes.recipe import _recipes


@pytest.fixture
def client():
    """Create test client and clean store."""
    _recipes.clear()
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c
    _recipes.clear()


@pytest.fixture
def sample_recipe():
    """Sample recipe data."""
    return {
        "name": "CVD Oxide Process",
        "equipment_type": "cvd",
        "version": "1.0.0",
        "description": "Standard CVD oxide deposition",
        "parameters": {
            "temperature": 400.0,
            "pressure": 5.0,
            "gas_flow_sio2": 100.0,
        },
        "steps": [
            {
                "step_id": "step_001",
                "name": "Purge",
                "duration": 30.0,
                "parameters": {"flow_rate": 500.0},
            },
            {
                "step_id": "step_002",
                "name": "Deposition",
                "duration": 120.0,
                "parameters": {"temperature": 400.0, "pressure": 5.0},
            },
        ],
        "created_by": "engineer1",
    }


class TestRecipeList:
    """Test recipe listing."""

    def test_list_empty(self, client):
        """Test listing when no recipes exist."""
        response = client.get("/api/v1/recipes/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_data(self, client, sample_recipe):
        """Test listing recipes with data."""
        client.post("/api/v1/recipes/", json=sample_recipe)
        response = client.get("/api/v1/recipes/")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1

    def test_list_with_type_filter(self, client, sample_recipe):
        """Test filtering by equipment type."""
        client.post("/api/v1/recipes/", json=sample_recipe)
        client.post("/api/v1/recipes/", json={**sample_recipe, "name": "Etch Recipe", "equipment_type": "etcher"})

        response = client.get("/api/v1/recipes/?equipment_type=cvd")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_status_filter(self, client, sample_recipe):
        """Test filtering by status."""
        client.post("/api/v1/recipes/", json=sample_recipe)
        response = client.get("/api/v1/recipes/?status=draft")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_search(self, client, sample_recipe):
        """Test search by name."""
        client.post("/api/v1/recipes/", json=sample_recipe)
        response = client.get("/api/v1/recipes/?search=oxide")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_with_search_no_match(self, client, sample_recipe):
        """Test search with no matches."""
        client.post("/api/v1/recipes/", json=sample_recipe)
        response = client.get("/api/v1/recipes/?search=nonexistent")
        assert response.status_code == 200
        assert len(response.json()) == 0


class TestRecipeCRUD:
    """Test recipe CRUD operations."""

    def test_create_recipe(self, client, sample_recipe):
        """Test creating a recipe."""
        response = client.post("/api/v1/recipes/", json=sample_recipe)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "CVD Oxide Process"
        assert data["status"] == "draft"
        assert data["version"] == "1.0.0"

    def test_create_recipe_with_id(self, client, sample_recipe):
        """Test creating a recipe with explicit ID."""
        recipe_data = {**sample_recipe, "id": "custom-recipe-id"}
        response = client.post("/api/v1/recipes/", json=recipe_data)
        assert response.status_code == 201
        assert response.json()["id"] == "custom-recipe-id"

    def test_get_recipe(self, client, sample_recipe):
        """Test getting recipe by ID."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/recipes/{recipe_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "CVD Oxide Process"

    def test_get_recipe_not_found(self, client):
        """Test getting non-existent recipe."""
        response = client.get("/api/v1/recipes/nonexistent")
        assert response.status_code == 404

    def test_update_recipe(self, client, sample_recipe):
        """Test updating recipe creates new version."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        response = client.put(f"/api/v1/recipes/{recipe_id}", json={
            **sample_recipe,
            "name": "Updated CVD Oxide Process",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated CVD Oxide Process"
        assert data["version"] == "1.0.1"
        assert data["parent_version_id"] == recipe_id

    def test_update_recipe_not_found(self, client):
        """Test updating non-existent recipe."""
        response = client.put("/api/v1/recipes/nonexistent", json={"name": "X"})
        assert response.status_code == 404

    def test_delete_recipe(self, client, sample_recipe):
        """Test deleting (archiving) recipe."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/recipes/{recipe_id}")
        assert response.status_code == 204

    def test_delete_recipe_not_found(self, client):
        """Test deleting non-existent recipe."""
        response = client.delete("/api/v1/recipes/nonexistent")
        assert response.status_code == 404


class TestRecipeWorkflow:
    """Test recipe workflow (approve, activate, upload)."""

    def test_approve_recipe(self, client, sample_recipe):
        """Test approving a recipe."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        response = client.post(f"/api/v1/recipes/{recipe_id}/approve?approver=admin1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "admin1"

    def test_approve_nonexistent_recipe(self, client):
        """Test approving non-existent recipe."""
        response = client.post("/api/v1/recipes/nonexistent/approve?approver=admin1")
        assert response.status_code == 404

    def test_activate_recipe(self, client, sample_recipe):
        """Test activating an approved recipe."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        # Approve first
        client.post(f"/api/v1/recipes/{recipe_id}/approve?approver=admin1")

        # Activate
        response = client.post(f"/api/v1/recipes/{recipe_id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    def test_activate_unapproved_recipe(self, client, sample_recipe):
        """Test activating a non-approved recipe."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        response = client.post(f"/api/v1/recipes/{recipe_id}/activate")
        assert response.status_code == 400

    def test_upload_recipe(self, client, sample_recipe):
        """Test uploading recipe to equipment."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        # Approve and activate
        client.post(f"/api/v1/recipes/{recipe_id}/approve?approver=admin1")
        client.post(f"/api/v1/recipes/{recipe_id}/activate")

        # Upload
        response = client.post(f"/api/v1/recipes/{recipe_id}/upload?equipment_id=EQ001")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UPLOADED"

    def test_upload_inactive_recipe(self, client, sample_recipe):
        """Test uploading inactive recipe."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        response = client.post(f"/api/v1/recipes/{recipe_id}/upload?equipment_id=EQ001")
        assert response.status_code == 400


class TestRecipeHistory:
    """Test recipe history and comparison."""

    def test_recipe_history(self, client, sample_recipe):
        """Test getting recipe history."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        # Create new version
        update_resp = client.put(f"/api/v1/recipes/{recipe_id}", json={
            **sample_recipe,
            "parameters": {"temperature": 450.0, "pressure": 5.0},
        })
        new_id = update_resp.json()["id"]

        response = client.get(f"/api/v1/recipes/{new_id}/history")
        assert response.status_code == 200
        history = response.json()
        assert len(history) == 2
        assert history[0]["id"] == recipe_id
        assert history[1]["id"] == new_id

    def test_compare_recipes(self, client, sample_recipe):
        """Test comparing two recipes."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id1 = create_resp.json()["id"]

        create_resp2 = client.post("/api/v1/recipes/", json={
            **sample_recipe,
            "name": "Different Recipe",
            "parameters": {"temperature": 500.0, "pressure": 10.0},
        })
        recipe_id2 = create_resp2.json()["id"]

        response = client.post(
            f"/api/v1/recipes/compare?recipe_id1={recipe_id1}&recipe_id2={recipe_id2}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "differences" in data
        assert data["difference_count"] > 0

    def test_compare_recipes_not_found(self, client, sample_recipe):
        """Test comparing with non-existent recipe."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/recipes/compare?recipe_id1={recipe_id}&recipe_id2=nonexistent"
        )
        assert response.status_code == 404


class TestRecipeCloneAndValidate:
    """Test recipe clone and validation."""

    def test_clone_recipe(self, client, sample_recipe):
        """Test cloning a recipe."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/recipes/{recipe_id}/clone?new_name=Cloned Recipe"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Cloned Recipe"
        assert data["version"] == "1.0.0"
        assert data["status"] == "draft"
        assert data["id"] != recipe_id

    def test_clone_nonexistent(self, client):
        """Test cloning non-existent recipe."""
        response = client.post("/api/v1/recipes/nonexistent/clone?new_name=X")
        assert response.status_code == 404

    def test_validate_recipe(self, client, sample_recipe):
        """Test validating a recipe."""
        create_resp = client.post("/api/v1/recipes/", json=sample_recipe)
        recipe_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/recipes/{recipe_id}/validate")
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "errors" in data
        assert "warnings" in data

    def test_validate_nonexistent(self, client):
        """Test validating non-existent recipe."""
        response = client.get("/api/v1/recipes/nonexistent/validate")
        assert response.status_code == 404
