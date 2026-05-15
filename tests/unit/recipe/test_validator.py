"""Recipe validator tests"""

import pytest

from myeap.recipe.models import Recipe, RecipeStep, RecipeStatus
from myeap.recipe.validator import (
    RecipeValidator,
    VersionFormatRule,
    ParameterRangeRule,
    StepDurationRule,
    RequiredParametersRule,
    FdcLimitRule,
    DuplicateStepIdRule,
    StepTransitionRule,
)


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
            RecipeStep(
                step_id="step_002",
                name="Clean",
                duration=300.0,
                parameters={"temperature": 200.0},
            ),
        ],
    }
    defaults.update(kwargs)
    return Recipe(**defaults)


class TestVersionFormatRule:
    """Version format rule tests"""

    def test_valid_version(self):
        """Test valid version format"""
        rule = VersionFormatRule()
        recipe = create_test_recipe(version="1.2.3")
        result = rule.check(recipe)
        assert not result.is_error

    def test_invalid_version(self):
        """Test invalid version format"""
        rule = VersionFormatRule()
        # Use model_construct to bypass pydantic validation for testing
        recipe = Recipe.model_construct(
            name="Test",
            equipment_type="cleaner",
            version="1.2",  # Invalid - missing patch
            created_by="test",
        )
        result = rule.check(recipe)
        assert result.is_error
        assert "Invalid version format" in result.message


class TestParameterRangeRule:
    """Parameter range rule tests"""

    def test_valid_parameters(self):
        """Test valid parameter ranges"""
        rule = ParameterRangeRule()
        recipe = create_test_recipe(
            adjustable_parameters=["temp"],
            parameters={"temp": 150.0},
        )
        result = rule.check(recipe)
        # Should have warnings about missing range limits, but no errors
        assert not result.is_error


class TestStepDurationRule:
    """Step duration rule tests"""

    def test_valid_durations(self):
        """Test valid step durations"""
        rule = StepDurationRule()
        recipe = create_test_recipe()
        result = rule.check(recipe)
        assert not result.is_error

    def test_zero_duration(self):
        """Test zero duration warning"""
        rule = StepDurationRule()
        recipe = create_test_recipe(
            steps=[
                RecipeStep(step_id="s1", name="S1", duration=0.0),
            ]
        )
        result = rule.check(recipe)
        assert result.is_error
        assert "invalid duration" in result.message.lower()

    def test_short_duration_warning(self):
        """Test short duration warning"""
        rule = StepDurationRule()
        recipe = create_test_recipe(
            steps=[
                RecipeStep(step_id="s1", name="S1", duration=0.5),  # < 1 second
            ]
        )
        result = rule.check(recipe)
        assert result.is_warning
        assert "very short duration" in result.message.lower()

    def test_long_duration_warning(self):
        """Test long duration warning"""
        rule = StepDurationRule()
        recipe = create_test_recipe(
            steps=[
                RecipeStep(step_id="s1", name="S1", duration=7200.0),  # > 1 hour
            ]
        )
        result = rule.check(recipe)
        assert result.is_warning
        assert "very long duration" in result.message.lower()


class TestRequiredParametersRule:
    """Required parameters rule tests"""

    def test_valid_recipe(self):
        """Test valid recipe has no errors"""
        rule = RequiredParametersRule()
        recipe = create_test_recipe()
        result = rule.check(recipe)
        assert not result.is_error

    def test_empty_name(self):
        """Test empty recipe name error"""
        rule = RequiredParametersRule()
        recipe = create_test_recipe(name="")
        result = rule.check(recipe)
        assert result.is_error
        assert "name is required" in result.message.lower()

    def test_empty_equipment_type(self):
        """Test empty equipment type error"""
        rule = RequiredParametersRule()
        recipe = create_test_recipe(equipment_type="")
        result = rule.check(recipe)
        assert result.is_error
        assert "equipment type is required" in result.message.lower()

    def test_no_steps_warning(self):
        """Test warning for recipe without steps"""
        rule = RequiredParametersRule()
        recipe = create_test_recipe(steps=[])
        result = rule.check(recipe)
        assert result.is_warning
        assert "no steps" in result.message.lower()

    def test_step_without_name(self):
        """Test error for step without name"""
        rule = RequiredParametersRule()
        recipe = create_test_recipe(
            steps=[
                RecipeStep(step_id="s1", name="", duration=10.0),
            ]
        )
        result = rule.check(recipe)
        assert result.is_error


class TestFdcLimitRule:
    """FDC limit rule tests"""

    def test_no_fdc_limits_warning(self):
        """Test warning when no FDC limits defined"""
        rule = FdcLimitRule()
        recipe = create_test_recipe(fdc_limits=None)
        result = rule.check(recipe)
        assert result.is_warning
        assert "No FDC limits defined" in result.message

    def test_valid_fdc_limits(self):
        """Test valid FDC limits"""
        rule = FdcLimitRule()
        recipe = create_test_recipe(
            fdc_limits={
                "limits": [
                    {"name": "temperature", "min": 100, "max": 200},
                ]
            }
        )
        result = rule.check(recipe)
        assert not result.is_error
        assert not result.is_warning

    def test_invalid_fdc_limits_structure(self):
        """Test invalid FDC limits structure"""
        rule = FdcLimitRule()
        # Use model_construct to bypass pydantic validation
        recipe = Recipe.model_construct(
            name="Test",
            equipment_type="cleaner",
            version="1.0.0",
            created_by="test",
            fdc_limits="not a dict",  # Invalid type
        )
        result = rule.check(recipe)
        assert result.is_error
        assert "must be a dictionary" in result.message


class TestDuplicateStepIdRule:
    """Duplicate step ID rule tests"""

    def test_unique_step_ids(self):
        """Test unique step IDs pass"""
        rule = DuplicateStepIdRule()
        recipe = create_test_recipe()
        result = rule.check(recipe)
        assert not result.is_error

    def test_duplicate_step_ids(self):
        """Test duplicate step IDs fail"""
        rule = DuplicateStepIdRule()
        # Use model_construct to bypass pydantic validation
        recipe = Recipe.model_construct(
            name="Test",
            equipment_type="cleaner",
            version="1.0.0",
            created_by="test",
            steps=[
                RecipeStep(step_id="step_001", name="Step 1", duration=10.0),
                RecipeStep(step_id="step_001", name="Step 2", duration=20.0),  # Duplicate
            ],
        )
        result = rule.check(recipe)
        assert result.is_error
        assert "Duplicate step IDs" in result.message


class TestStepTransitionRule:
    """Step transition rule tests"""

    def test_valid_transitions(self):
        """Test valid step transitions"""
        rule = StepTransitionRule()
        recipe = create_test_recipe(
            steps=[
                RecipeStep(
                    step_id="s1",
                    name="Step 1",
                    duration=10.0,
                    transitions={"next_steps": ["s2"]},
                ),
                RecipeStep(step_id="s2", name="Step 2", duration=20.0),
            ]
        )
        result = rule.check(recipe)
        assert not result.is_error

    def test_invalid_transition_target(self):
        """Test invalid transition target fails"""
        rule = StepTransitionRule()
        recipe = create_test_recipe(
            steps=[
                RecipeStep(
                    step_id="s1",
                    name="Step 1",
                    duration=10.0,
                    transitions={"next_steps": ["nonexistent"]},
                ),
            ]
        )
        result = rule.check(recipe)
        assert result.is_error
        assert "unknown step" in result.message.lower()


class TestRecipeValidator:
    """Recipe validator tests"""

    def test_validate_valid_recipe(self):
        """Test validating a valid recipe"""
        validator = RecipeValidator()
        recipe = create_test_recipe()
        result = validator.validate(recipe)

        assert result.valid
        assert len(result.errors) == 0

    def test_validate_invalid_recipe(self):
        """Test validating an invalid recipe"""
        validator = RecipeValidator()
        recipe = create_test_recipe(name="")  # Invalid: empty name
        result = validator.validate(recipe)

        assert not result.valid
        assert len(result.errors) > 0

    def test_add_rule(self):
        """Test adding a custom rule"""
        validator = RecipeValidator()
        initial_count = len(validator.rules)

        class CustomRule:
            @property
            def name(self):
                return "custom_rule"

            def check(self, recipe):
                from myeap.recipe.validator import ValidationRuleResult

                return ValidationRuleResult(False, False, "Custom rule passed")

        validator.add_rule(CustomRule())
        assert len(validator.rules) == initial_count + 1

    def test_remove_rule(self):
        """Test removing a rule"""
        validator = RecipeValidator()
        initial_count = len(validator.rules)

        removed = validator.remove_rule("version_format")
        assert removed
        assert len(validator.rules) == initial_count - 1

        # Try to remove non-existent rule
        removed = validator.remove_rule("nonexistent_rule")
        assert not removed

    def test_validate_parameter(self):
        """Test validating a single parameter"""
        validator = RecipeValidator()
        result = validator.validate_parameter(
            param_name="temperature",
            param_value=150.0,
            param_def={"min_value": 100.0, "max_value": 200.0},
        )
        assert result.valid

        # Test out of range
        result = validator.validate_parameter(
            param_name="temperature",
            param_value=250.0,
            param_def={"min_value": 100.0, "max_value": 200.0},
        )
        assert not result.valid
        assert len(result.errors) == 1
