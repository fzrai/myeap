"""Recipe model tests"""

import pytest
from datetime import datetime

from myeap.recipe.models import (
    RecipeStatus,
    RecipeStep,
    Recipe,
    RecipeParameter,
    ParameterizedRecipe,
    ValidationResult,
)


class TestRecipeStatus:
    """Recipe status tests"""

    def test_status_values(self):
        """Test status enum values"""
        assert RecipeStatus.DRAFT.value == "draft"
        assert RecipeStatus.PENDING_APPROVAL.value == "pending_approval"
        assert RecipeStatus.APPROVED.value == "approved"
        assert RecipeStatus.ACTIVE.value == "active"
        assert RecipeStatus.ARCHIVED.value == "archived"


class TestRecipeStep:
    """Recipe step tests"""

    def test_create_step(self):
        """Test creating a recipe step"""
        step = RecipeStep(
            step_id="step_001",
            name="Preheat",
            duration=120.0,
            parameters={"temperature": 150.0, "pressure": 1.0},
        )
        assert step.step_id == "step_001"
        assert step.name == "Preheat"
        assert step.duration == 120.0
        assert step.parameters["temperature"] == 150.0

    def test_step_with_optional_fields(self):
        """Test step with optional transitions and endpoints"""
        step = RecipeStep(
            step_id="step_002",
            name="Process",
            duration=300.0,
            parameters={},
            transitions={"next_steps": ["step_003"]},
            endpoints=["chamber_01"],
        )
        assert step.transitions == {"next_steps": ["step_003"]}
        assert step.endpoints == ["chamber_01"]


class TestRecipe:
    """Recipe tests"""

    def test_create_recipe(self):
        """Test creating a recipe"""
        recipe = Recipe(
            name="Test Recipe",
            equipment_type="cleaner",
            version="1.0.0",
            created_by="test_user",
        )
        assert recipe.name == "Test Recipe"
        assert recipe.equipment_type == "cleaner"
        assert recipe.version == "1.0.0"
        assert recipe.status == RecipeStatus.DRAFT

    def test_recipe_with_steps(self):
        """Test recipe with steps"""
        steps = [
            RecipeStep(
                step_id="step_001",
                name="Preheat",
                duration=60.0,
                parameters={"temp": 100},
            ),
            RecipeStep(
                step_id="step_002",
                name="Clean",
                duration=300.0,
                parameters={"temp": 200, "time": 300},
            ),
        ]
        recipe = Recipe(
            name="Clean Recipe",
            equipment_type="cleaner",
            version="1.0.0",
            created_by="test_user",
            steps=steps,
        )
        assert len(recipe.steps) == 2
        assert recipe.total_duration == 360.0

    def test_version_validation(self):
        """Test version format validation"""
        with pytest.raises(ValueError, match="Version must be in format X.Y.Z"):
            Recipe(
                name="Test",
                equipment_type="cleaner",
                version="1.0",  # Invalid - only 2 parts
                created_by="test",
            )

        with pytest.raises(ValueError, match="Version must be in format X.Y.Z"):
            Recipe(
                name="Test",
                equipment_type="cleaner",
                version="invalid",  # Invalid - not numeric
                created_by="test",
            )

    def test_unique_step_ids(self):
        """Test that step IDs must be unique"""
        with pytest.raises(ValueError, match="unique step_ids"):
            Recipe(
                name="Test",
                equipment_type="cleaner",
                version="1.0.0",
                created_by="test",
                steps=[
                    RecipeStep(step_id="step_001", name="Step 1", duration=10.0),
                    RecipeStep(step_id="step_001", name="Step 2", duration=20.0),  # Duplicate
                ],
            )

    def test_total_duration(self):
        """Test total duration calculation"""
        recipe = Recipe(
            name="Test",
            equipment_type="cleaner",
            version="1.0.0",
            created_by="test",
            steps=[
                RecipeStep(step_id="s1", name="S1", duration=100.0),
                RecipeStep(step_id="s2", name="S2", duration=200.0),
                RecipeStep(step_id="s3", name="S3", duration=150.0),
            ],
        )
        assert recipe.total_duration == 450.0

    def test_is_editable(self):
        """Test is_editable property"""
        recipe = Recipe(
            name="Test",
            equipment_type="cleaner",
            version="1.0.0",
            created_by="test",
            status=RecipeStatus.DRAFT,
        )
        assert recipe.is_editable

        recipe.status = RecipeStatus.ACTIVE
        assert not recipe.is_editable

    def test_is_active(self):
        """Test is_active property"""
        recipe = Recipe(
            name="Test",
            equipment_type="cleaner",
            version="1.0.0",
            created_by="test",
            status=RecipeStatus.ACTIVE,
        )
        assert recipe.is_active

        recipe.status = RecipeStatus.APPROVED
        assert not recipe.is_active

    def test_get_step(self):
        """Test getting step by ID"""
        recipe = Recipe(
            name="Test",
            equipment_type="cleaner",
            version="1.0.0",
            created_by="test",
            steps=[
                RecipeStep(step_id="step_001", name="Step 1", duration=10.0),
                RecipeStep(step_id="step_002", name="Step 2", duration=20.0),
            ],
        )
        step = recipe.get_step("step_001")
        assert step is not None
        assert step.name == "Step 1"

        not_found = recipe.get_step("nonexistent")
        assert not_found is None

    def test_to_dict(self):
        """Test converting recipe to dictionary"""
        recipe = Recipe(
            name="Test Recipe",
            equipment_type="cleaner",
            version="1.0.0",
            created_by="test_user",
            description="A test recipe",
            parameters={"param1": 100, "param2": "value"},
            steps=[
                RecipeStep(step_id="step_001", name="Step 1", duration=60.0),
            ],
        )
        data = recipe.to_dict()

        assert data["name"] == "Test Recipe"
        assert data["equipment_type"] == "cleaner"
        assert data["version"] == "1.0.0"
        assert data["description"] == "A test recipe"
        assert data["parameters"]["param1"] == 100
        assert len(data["steps"]) == 1
        assert data["total_duration"] == 60.0


class TestRecipeParameter:
    """Recipe parameter tests"""

    def test_create_parameter(self):
        """Test creating a recipe parameter"""
        param = RecipeParameter(
            name="temperature",
            value=150.0,
            unit="C",
            min_value=0.0,
            max_value=300.0,
        )
        assert param.name == "temperature"
        assert param.value == 150.0
        assert param.unit == "C"

    def test_validate_value_within_range(self):
        """Test value validation within range"""
        param = RecipeParameter(
            name="temp",
            value=100.0,
            min_value=0.0,
            max_value=200.0,
        )
        assert param.validate_value(50.0)
        assert param.validate_value(100.0)
        assert param.validate_value(200.0)

    def test_validate_value_out_of_range(self):
        """Test value validation out of range"""
        param = RecipeParameter(
            name="temp",
            value=100.0,
            min_value=0.0,
            max_value=200.0,
        )
        assert not param.validate_value(-10.0)
        assert not param.validate_value(250.0)


class TestParameterizedRecipe:
    """Parameterized recipe tests"""

    def test_instantiate_recipe(self):
        """Test instantiating a recipe from template"""
        template = ParameterizedRecipe(
            template_id="tmpl_001",
            name="Temperature Recipe",
            base_recipe_id="base_001",
            parameter_definitions=[
                RecipeParameter(
                    name="temperature",
                    value=150.0,
                    unit="C",
                    min_value=100.0,
                    max_value=200.0,
                    adjustable=True,
                ),
                RecipeParameter(
                    name="duration",
                    value=300.0,
                    unit="s",
                    min_value=60.0,
                    max_value=600.0,
                    adjustable=True,
                ),
            ],
        )

        recipe = template.instantiate(
            parameter_values={"temperature": 175.0, "duration": 450.0},
            created_by="test_user",
        )

        assert recipe.name == "Temperature Recipe"
        assert recipe.created_by == "test_user"
        assert recipe.version == "1.0.0"
        assert recipe.parameters["temperature"]["value"] == 175.0
        assert recipe.parameters["duration"]["value"] == 450.0

    def test_instantiate_missing_params(self):
        """Test instantiation fails with missing parameters"""
        template = ParameterizedRecipe(
            template_id="tmpl_001",
            name="Test",
            base_recipe_id="base_001",
            parameter_definitions=[
                RecipeParameter(
                    name="required_param",
                    value=100.0,
                    adjustable=True,
                ),
            ],
        )

        with pytest.raises(ValueError, match="Missing required parameters"):
            template.instantiate(parameter_values={}, created_by="test")

    def test_instantiate_invalid_value(self):
        """Test instantiation fails with out-of-range value"""
        template = ParameterizedRecipe(
            template_id="tmpl_001",
            name="Test",
            base_recipe_id="base_001",
            parameter_definitions=[
                RecipeParameter(
                    name="temp",
                    value=150.0,
                    min_value=100.0,
                    max_value=200.0,
                    adjustable=True,
                ),
            ],
        )

        with pytest.raises(ValueError, match="out of range"):
            template.instantiate(
                parameter_values={"temp": 300.0},  # Above max
                created_by="test",
            )

    def test_get_parameter_names(self):
        """Test getting adjustable parameter names"""
        template = ParameterizedRecipe(
            template_id="tmpl_001",
            name="Test",
            base_recipe_id="base_001",
            parameter_definitions=[
                RecipeParameter(name="adjustable_1", value=100, adjustable=True),
                RecipeParameter(name="fixed_1", value=200, adjustable=False),
                RecipeParameter(name="adjustable_2", value=300, adjustable=True),
            ],
        )

        names = template.get_parameter_names()
        assert "adjustable_1" in names
        assert "adjustable_2" in names
        assert "fixed_1" not in names


class TestValidationResult:
    """Validation result tests"""

    def test_validation_result_valid(self):
        """Test valid validation result"""
        result = ValidationResult(valid=True)
        assert result.valid
        assert not result.has_errors
        assert not result.has_warnings

    def test_add_error(self):
        """Test adding errors"""
        result = ValidationResult(valid=True)
        result.add_error("Error 1")
        result.add_error("Error 2")

        assert not result.valid
        assert result.has_errors
        assert len(result.errors) == 2
        assert "Error 1" in result.errors

    def test_add_warning(self):
        """Test adding warnings"""
        result = ValidationResult(valid=True)
        result.add_warning("Warning 1")

        assert result.valid
        assert result.has_warnings
        assert len(result.warnings) == 1

    def test_merge(self):
        """Test merging validation results"""
        result1 = ValidationResult(valid=True)
        result1.add_error("Error 1")
        result1.add_warning("Warning 1")

        result2 = ValidationResult(valid=True)
        result2.add_error("Error 2")

        merged = result1.merge(result2)

        assert not merged.valid
        assert len(merged.errors) == 2
        assert len(merged.warnings) == 1
