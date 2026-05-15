"""Recipe Validator

This module provides validation rules for recipes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Any

from myeap.recipe.models import Recipe, RecipeStep, ValidationResult
from myeap.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationRuleResult:
    """Result of a single validation rule"""

    is_error: bool
    is_warning: bool
    message: str
    field: Optional[str] = None


class ValidationRule(ABC):
    """Base class for validation rules"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name"""
        raise NotImplementedError

    @abstractmethod
    def check(self, recipe: Recipe) -> ValidationRuleResult:
        """Check recipe against this rule

        Args:
            recipe: Recipe to validate

        Returns:
            ValidationRuleResult
        """
        raise NotImplementedError


class VersionFormatRule(ValidationRule):
    """Validate version format is X.Y.Z"""

    @property
    def name(self) -> str:
        return "version_format"

    def check(self, recipe: Recipe) -> ValidationRuleResult:
        import re

        pattern = r"^\d+\.\d+\.\d+$"
        if not re.match(pattern, recipe.version):
            return ValidationRuleResult(
                is_error=True,
                is_warning=False,
                message=f"Invalid version format: {recipe.version}. Expected X.Y.Z",
                field="version",
            )
        return ValidationRuleResult(
            is_error=False, is_warning=False, message="Version format is valid"
        )


class ParameterRangeRule(ValidationRule):
    """Validate parameter values are within specified ranges"""

    @property
    def name(self) -> str:
        return "parameter_range"

    def check(self, recipe: Recipe) -> ValidationRuleResult:
        errors = []
        warnings = []

        for param_name, param_value in recipe.parameters.items():
            # Check if parameter is in adjustable list
            if param_name in recipe.adjustable_parameters:
                # Should have min/max defined - warn if not
                if "min" not in str(param_value) and "max" not in str(param_value):
                    warnings.append(
                        f"Parameter '{param_name}' is adjustable but lacks range limits"
                    )

        if errors:
            return ValidationRuleResult(
                is_error=True,
                is_warning=False,
                message="; ".join(errors),
                field="parameters",
            )

        if warnings:
            return ValidationRuleResult(
                is_error=False,
                is_warning=True,
                message="; ".join(warnings),
                field="parameters",
            )

        return ValidationRuleResult(
            is_error=False, is_warning=False, message="Parameter ranges are valid"
        )


class StepDurationRule(ValidationRule):
    """Validate recipe step durations"""

    @property
    def name(self) -> str:
        return "step_duration"

    def check(self, recipe: Recipe) -> ValidationRuleResult:
        errors = []
        warnings = []

        for step in recipe.steps:
            # Check for zero or negative duration
            if step.duration <= 0:
                errors.append(
                    f"Step '{step.name}' (ID: {step.step_id}) has invalid duration: {step.duration}"
                )

            # Warn for very short steps (< 1 second)
            if 0 < step.duration < 1:
                warnings.append(
                    f"Step '{step.name}' has very short duration: {step.duration}s"
                )

            # Warn for very long steps (> 1 hour)
            if step.duration > 3600:
                warnings.append(
                    f"Step '{step.name}' has very long duration: {step.duration}s ({step.duration/3600:.1f}h)"
                )

        if errors:
            return ValidationRuleResult(
                is_error=True,
                is_warning=False,
                message="; ".join(errors),
                field="steps",
            )

        if warnings:
            return ValidationRuleResult(
                is_error=False,
                is_warning=True,
                message="; ".join(warnings),
                field="steps",
            )

        return ValidationRuleResult(
            is_error=False, is_warning=False, message="Step durations are valid"
        )


class RequiredParametersRule(ValidationRule):
    """Validate required parameters are present"""

    @property
    def name(self) -> str:
        return "required_parameters"

    def check(self, recipe: Recipe) -> ValidationRuleResult:
        errors = []

        # Check for empty recipe name
        if not recipe.name or not recipe.name.strip():
            errors.append("Recipe name is required")

        # Check for empty equipment type
        if not recipe.equipment_type or not recipe.equipment_type.strip():
            errors.append("Equipment type is required")

        # Check for empty steps
        if not recipe.steps:
            warnings = []
            warnings.append("Recipe has no steps defined")
            return ValidationRuleResult(
                is_error=False,
                is_warning=True,
                message="; ".join(warnings),
                field="steps",
            )

        # Check for steps without names
        for step in recipe.steps:
            if not step.name or not step.name.strip():
                errors.append(f"Step ID '{step.step_id}' has no name")

        if errors:
            return ValidationRuleResult(
                is_error=True,
                is_warning=False,
                message="; ".join(errors),
                field="metadata",
            )

        return ValidationRuleResult(
            is_error=False, is_warning=False, message="Required parameters are present"
        )


class FdcLimitRule(ValidationRule):
    """Validate FDC limits configuration"""

    @property
    def name(self) -> str:
        return "fdc_limits"

    def check(self, recipe: Recipe) -> ValidationRuleResult:
        warnings = []

        # FDC limits are optional
        if recipe.fdc_limits is None:
            return ValidationRuleResult(
                is_error=False,
                is_warning=True,
                message="No FDC limits defined for this recipe",
            )

        # Check FDC limits structure
        if not isinstance(recipe.fdc_limits, dict):
            return ValidationRuleResult(
                is_error=True,
                is_warning=False,
                message="FDC limits must be a dictionary",
                field="fdc_limits",
            )

        # Check for required FDC limit fields
        required_fields = ["limits"]
        for field in required_fields:
            if field not in recipe.fdc_limits:
                warnings.append(f"FDC limits missing recommended field: {field}")

        if warnings:
            return ValidationRuleResult(
                is_error=False,
                is_warning=True,
                message="; ".join(warnings),
                field="fdc_limits",
            )

        return ValidationRuleResult(
            is_error=False, is_warning=False, message="FDC limits are valid"
        )


class DuplicateStepIdRule(ValidationRule):
    """Validate step IDs are unique"""

    @property
    def name(self) -> str:
        return "duplicate_step_id"

    def check(self, recipe: Recipe) -> ValidationRuleResult:
        step_ids = [step.step_id for step in recipe.steps]
        duplicates = [sid for sid in step_ids if step_ids.count(sid) > 1]

        if duplicates:
            return ValidationRuleResult(
                is_error=True,
                is_warning=False,
                message=f"Duplicate step IDs found: {set(duplicates)}",
                field="steps",
            )

        return ValidationRuleResult(
            is_error=False, is_warning=False, message="Step IDs are unique"
        )


class StepTransitionRule(ValidationRule):
    """Validate step transitions are valid"""

    @property
    def name(self) -> str:
        return "step_transitions"

    def check(self, recipe: Recipe) -> ValidationRuleResult:
        errors = []
        step_ids = {step.step_id for step in recipe.steps}

        for step in recipe.steps:
            if step.transitions:
                for target in step.transitions.get("next_steps", []):
                    if target not in step_ids:
                        errors.append(
                            f"Step '{step.name}' transitions to unknown step: {target}"
                        )

        if errors:
            return ValidationRuleResult(
                is_error=True,
                is_warning=False,
                message="; ".join(errors),
                field="steps",
            )

        return ValidationRuleResult(
            is_error=False, is_warning=False, message="Step transitions are valid"
        )


class RecipeValidator:
    """Recipe validator

    Validates recipes against configurable rules.
    """

    def __init__(self):
        self.rules: List[ValidationRule] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load default validation rules"""
        self.rules = [
            VersionFormatRule(),
            RequiredParametersRule(),
            DuplicateStepIdRule(),
            StepDurationRule(),
            ParameterRangeRule(),
            FdcLimitRule(),
            StepTransitionRule(),
        ]

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule

        Args:
            rule: Validation rule to add
        """
        self.rules.append(rule)
        logger.info(f"Added validation rule: {rule.name}")

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a validation rule by name

        Args:
            rule_name: Name of rule to remove

        Returns:
            True if rule was removed
        """
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                logger.info(f"Removed validation rule: {rule_name}")
                return True
        return False

    def validate(self, recipe: Recipe) -> ValidationResult:
        """Validate a recipe

        Args:
            recipe: Recipe to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(valid=True)

        for rule in self.rules:
            try:
                rule_result = rule.check(recipe)
                if rule_result.is_error:
                    result.add_error(f"[{rule.name}] {rule_result.message}")
                    logger.debug(
                        "validation_error",
                        rule=rule.name,
                        message=rule_result.message,
                        recipe_id=recipe.id,
                    )
                elif rule_result.is_warning:
                    result.add_warning(f"[{rule.name}] {rule_result.message}")
                    logger.debug(
                        "validation_warning",
                        rule=rule.name,
                        message=rule_result.message,
                        recipe_id=recipe.id,
                    )
            except Exception as e:
                result.add_error(f"[{rule.name}] Validation error: {str(e)}")
                logger.error(
                    "validation_rule_error",
                    rule=rule.name,
                    error=str(e),
                    recipe_id=recipe.id,
                )

        if result.valid:
            logger.info("recipe_validated", recipe_id=recipe.id, valid=True)
        else:
            logger.warning(
                "recipe_validation_failed",
                recipe_id=recipe.id,
                error_count=len(result.errors),
            )

        return result

    def validate_parameter(
        self,
        param_name: str,
        param_value: Any,
        param_def: Optional[dict] = None,
    ) -> ValidationResult:
        """Validate a single parameter value

        Args:
            param_name: Parameter name
            param_value: Parameter value
            param_def: Optional parameter definition with min/max

        Returns:
            ValidationResult
        """
        result = ValidationResult(valid=True)

        if param_def:
            min_val = param_def.get("min_value")
            max_val = param_def.get("max_value")

            if min_val is not None and param_value < min_val:
                result.add_error(
                    f"Parameter '{param_name}' value {param_value} is below minimum {min_val}"
                )

            if max_val is not None and param_value > max_val:
                result.add_error(
                    f"Parameter '{param_name}' value {param_value} exceeds maximum {max_val}"
                )

        return result


# Global validator instance
_validator: Optional[RecipeValidator] = None


def get_validator() -> RecipeValidator:
    """Get global validator instance"""
    global _validator
    if _validator is None:
        _validator = RecipeValidator()
    return _validator
