"""Recipe manager tests"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from myeap.recipe.models import (
    Recipe,
    RecipeStep,
    RecipeStatus,
    ValidationResult,
)
from myeap.recipe.manager import RecipeManager, get_recipe_manager
from myeap.recipe.validator import RecipeValidator
from myeap.recipe.version_control import VersionControl
from myeap.core.exceptions import RecipeError, ValidationError


def create_test_recipe(**kwargs) -> Recipe:
    """Create a test recipe with defaults"""
    defaults = {
        "name": "Test Recipe",
        "equipment_type": "cleaner",
        "version": "1.0.0",
        "created_by": "test_user",
        "steps": [
            RecipeStep(
                step_id="step_001",
                name="Preheat",
                duration=60.0,
                parameters={"temperature": 150.0},
            ),
        ],
    }
    defaults.update(kwargs)
    return Recipe(**defaults)


@pytest.fixture
def manager():
    """Create a recipe manager without DB (in-memory only)"""
    # Patch the metrics collector to avoid issues
    with patch('myeap.recipe.manager.metrics'):
        return RecipeManager(
            db_manager=None,
            secs_driver_manager={},
        )


class TestRecipeManager:
    """Recipe manager tests"""

    @pytest.mark.asyncio
    async def test_create_recipe(self, manager):
        """Test creating a recipe"""
        recipe = create_test_recipe()

        recipe_id = await manager.create_recipe(recipe, "test_user")

        assert recipe_id == recipe.id
        assert recipe.id in manager._recipes
        assert manager._recipes[recipe.id].status == RecipeStatus.DRAFT

    @pytest.mark.asyncio
    async def test_create_recipe_invalid(self, manager):
        """Test creating an invalid recipe"""
        # Create a recipe with invalid version format using model_construct
        recipe = Recipe.model_construct(
            name="Test",
            equipment_type="cleaner",
            version="1.0",  # Invalid: missing patch component
            created_by="test_user",
        )

        with pytest.raises(ValidationError):
            await manager.create_recipe(recipe)

    @pytest.mark.asyncio
    async def test_get_recipe(self, manager):
        """Test getting a recipe"""
        recipe = create_test_recipe()
        await manager.create_recipe(recipe, "test_user")

        retrieved = await manager.get_recipe(recipe.id)

        assert retrieved is not None
        assert retrieved.id == recipe.id
        assert retrieved.name == recipe.name

    @pytest.mark.asyncio
    async def test_get_recipe_not_found(self, manager):
        """Test getting non-existent recipe"""
        result = await manager.get_recipe("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_recipe_by_name(self, manager):
        """Test getting recipe by name"""
        recipe = create_test_recipe(name="Named Recipe")
        await manager.create_recipe(recipe, "test_user")

        retrieved = await manager.get_recipe_by_name("Named Recipe", "cleaner")

        assert retrieved is not None
        assert retrieved.name == "Named Recipe"

    @pytest.mark.asyncio
    async def test_list_recipes(self, manager):
        """Test listing recipes"""
        # Create multiple recipes
        for i in range(5):
            recipe = create_test_recipe(name=f"Recipe {i}")
            await manager.create_recipe(recipe)

        recipes = await manager.list_recipes()

        assert len(recipes) == 5

    @pytest.mark.asyncio
    async def test_list_recipes_with_filter(self, manager):
        """Test listing recipes with filters"""
        # Create recipes with different equipment types
        await manager.create_recipe(create_test_recipe(equipment_type="cleaner"))
        await manager.create_recipe(create_test_recipe(equipment_type="cvd"))

        recipes = await manager.list_recipes(equipment_type="cleaner")

        assert len(recipes) == 1
        assert recipes[0].equipment_type == "cleaner"

    @pytest.mark.asyncio
    async def test_update_recipe(self, manager):
        """Test updating a recipe creates new version"""
        recipe = create_test_recipe()
        await manager.create_recipe(recipe, "test_user")

        original_id = recipe.id
        original_version = recipe.version

        await manager.update_recipe(recipe.id, {"description": "Updated"}, "test_user")

        # Original should still exist
        original = manager._recipes.get(original_id)
        assert original is not None

        # Should have new version with incremented version
        updated_recipes = [r for r in manager._recipes.values() if r.parent_version_id == original_id]
        assert len(updated_recipes) == 1
        assert updated_recipes[0].version != original_version

    @pytest.mark.asyncio
    async def test_update_recipe_not_editable(self, manager):
        """Test updating non-editable recipe fails"""
        recipe = create_test_recipe(status=RecipeStatus.ACTIVE)
        manager._recipes[recipe.id] = recipe

        with pytest.raises(RecipeError, match="not editable"):
            await manager.update_recipe(recipe.id, {"description": "New"})

    @pytest.mark.asyncio
    async def test_delete_recipe(self, manager):
        """Test deleting (archiving) a recipe"""
        recipe = create_test_recipe()
        await manager.create_recipe(recipe, "test_user")

        await manager.delete_recipe(recipe.id, "test_user")

        # Should be archived
        assert manager._recipes[recipe.id].status == RecipeStatus.ARCHIVED

    @pytest.mark.asyncio
    async def test_approve_recipe(self, manager):
        """Test approving a recipe"""
        recipe = create_test_recipe()
        manager._recipes[recipe.id] = recipe

        await manager.approve_recipe(recipe.id, "approver_user")

        assert manager._recipes[recipe.id].status == RecipeStatus.APPROVED
        assert manager._recipes[recipe.id].approved_by == "approver_user"
        assert manager._recipes[recipe.id].approved_at is not None

    @pytest.mark.asyncio
    async def test_approve_recipe_wrong_status(self, manager):
        """Test approving already active recipe fails"""
        recipe = create_test_recipe(status=RecipeStatus.ACTIVE)
        manager._recipes[recipe.id] = recipe

        with pytest.raises(RecipeError, match="cannot be approved"):
            await manager.approve_recipe(recipe.id, "approver")

    @pytest.mark.asyncio
    async def test_activate_recipe(self, manager):
        """Test activating an approved recipe"""
        recipe = create_test_recipe(status=RecipeStatus.APPROVED)
        manager._recipes[recipe.id] = recipe

        await manager.activate_recipe(recipe.id, "activator")

        assert manager._recipes[recipe.id].status == RecipeStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_compare_recipes(self, manager):
        """Test comparing two recipes"""
        recipe1 = create_test_recipe(
            name="Recipe A",
            parameters={"temp": 150, "time": 100},
        )
        recipe2 = create_test_recipe(
            name="Recipe B",
            parameters={"temp": 175, "time": 100},
        )

        await manager.create_recipe(recipe1, "test")
        await manager.create_recipe(recipe2, "test")

        comparison = await manager.compare_recipes(recipe1.id, recipe2.id)

        assert "differences" in comparison
        assert comparison["difference_count"] > 0

        # Find the temp parameter difference
        temp_diff = next(
            (d for d in comparison["differences"] if d.get("name") == "temp"),
            None,
        )
        assert temp_diff is not None
        assert temp_diff["old_value"] == 150
        assert temp_diff["new_value"] == 175

    @pytest.mark.asyncio
    async def test_get_recipe_history(self, manager):
        """Test getting recipe version history"""
        recipe = create_test_recipe()
        await manager.create_recipe(recipe, "test")

        # Create update
        await manager.update_recipe(recipe.id, {"description": "Update 1"}, "test")

        history = await manager.get_recipe_history(recipe.id)

        # Should have at least 2 versions
        assert len(history) >= 1

    @pytest.mark.asyncio
    async def test_clone_recipe(self, manager):
        """Test cloning a recipe"""
        recipe = create_test_recipe()
        await manager.create_recipe(recipe, "test")

        clone_id = await manager.clone_recipe(recipe.id, "Cloned Recipe", "cloner")

        clone = manager._recipes.get(clone_id)
        assert clone is not None
        assert clone.name == "Cloned Recipe"
        assert clone.version == "1.0.0"
        assert clone.status == RecipeStatus.DRAFT
        assert clone.parent_version_id is None

    def test_convert_to_ppbody(self, manager):
        """Test converting recipe to PPBODY format"""
        recipe = create_test_recipe()
        ppbody = manager._convert_to_ppbody(recipe)

        assert b"RECIPE:Test Recipe" in ppbody
        assert b"VERSION:1.0.0" in ppbody
        assert b"TYPE:cleaner" in ppbody
        assert b"[PARAMETERS]" in ppbody
        assert b"[STEPS]" in ppbody

    def test_parse_ppbody(self, manager):
        """Test parsing PPBODY to recipe"""
        ppbody = b"""RECIPE:TestRecipe
VERSION:1.0.0
TYPE:cvd

[PARAMETERS]
temp=200
pressure=1.5

[STEPS]
STEP:1
  ID=step_001
  NAME=Heat
  DURATION=60.0
  temp=200
"""

        recipe = manager._parse_ppbody(ppbody, "test_user")

        assert recipe.name == "TestRecipe"
        assert recipe.equipment_type == "cvd"
        assert "temp" in recipe.parameters
        assert len(recipe.steps) == 1


class TestGetRecipeManager:
    """Test global recipe manager instance"""

    def test_get_recipe_manager_singleton(self):
        """Test getting global instance is singleton"""
        # Reset global instance
        import myeap.recipe.manager as manager_module
        manager_module._manager = None

        m1 = get_recipe_manager()
        m2 = get_recipe_manager()
        assert m1 is m2
