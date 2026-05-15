"""Recipe Pydantic Models

This module defines all Pydantic models for recipe management.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class RecipeStatus(str, Enum):
    """Recipe status enumeration"""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RecipeStep(BaseModel):
    """Recipe step definition

    Represents a single step in a recipe with parameters,
    duration, and optional transitions/endpoints.
    """

    step_id: str = Field(..., description="Unique step identifier")
    name: str = Field(..., description="Step name")
    duration: float = Field(..., ge=0, description="Step duration in seconds")
    parameters: Dict[str, Union[float, int, str]] = Field(
        default_factory=dict, description="Step parameters"
    )
    transitions: Optional[Dict[str, Any]] = Field(
        default=None, description="State transitions for this step"
    )
    endpoints: Optional[List[str]] = Field(
        default=None, description="Target endpoints after step completion"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "step_id": "step_001",
                "name": "Preheat",
                "duration": 120.0,
                "parameters": {"temperature": 150.0, "pressure": 1.0},
            }
        }
    }


class Recipe(BaseModel):
    """Recipe model

    Represents a complete recipe with all parameters and steps.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Recipe ID")
    name: str = Field(..., description="Recipe name")
    equipment_type: str = Field(..., description="Equipment type")
    version: str = Field(..., description="Recipe version in X.Y.Z format")
    description: Optional[str] = Field(default=None, description="Recipe description")

    # Recipe content
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Recipe parameters"
    )
    steps: List[RecipeStep] = Field(default_factory=list, description="Recipe steps")

    # Version control
    parent_version_id: Optional[str] = Field(
        default=None, description="Parent recipe version ID"
    )
    status: RecipeStatus = Field(
        default=RecipeStatus.DRAFT, description="Recipe status"
    )

    # Metadata
    created_by: str = Field(..., description="Creator username")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    approved_by: Optional[str] = Field(default=None, description="Approver username")
    approved_at: Optional[datetime] = Field(default=None, description="Approval timestamp")

    # FDC limits
    fdc_limits: Optional[Dict[str, Any]] = Field(
        default=None, description="FDC (Fault Detection and Classification) limits"
    )

    # Adjustable parameters
    adjustable_parameters: List[str] = Field(
        default_factory=list, description="List of adjustable parameter names"
    )

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format X.Y.Z"""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Version must be in format X.Y.Z")
        for part in parts:
            if not part.isdigit():
                raise ValueError(f"Version parts must be numeric: {v}")
        return v

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: List[RecipeStep]) -> List[RecipeStep]:
        """Validate recipe steps have unique IDs"""
        if not v:
            return v
        step_ids = [step.step_id for step in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Recipe steps must have unique step_ids")
        return v

    @property
    def total_duration(self) -> float:
        """Calculate total recipe duration"""
        return sum(step.duration for step in self.steps)

    @property
    def is_editable(self) -> bool:
        """Check if recipe is in editable state"""
        return self.status in (RecipeStatus.DRAFT, RecipeStatus.PENDING_APPROVAL)

    @property
    def is_active(self) -> bool:
        """Check if recipe is active"""
        return self.status == RecipeStatus.ACTIVE

    def get_step(self, step_id: str) -> Optional[RecipeStep]:
        """Get step by ID"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "equipment_type": self.equipment_type,
            "version": self.version,
            "description": self.description,
            "parameters": self.parameters,
            "steps": [step.model_dump() for step in self.steps],
            "parent_version_id": self.parent_version_id,
            "status": self.status.value,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "fdc_limits": self.fdc_limits,
            "adjustable_parameters": self.adjustable_parameters,
            "total_duration": self.total_duration,
        }


class RecipeParameter(BaseModel):
    """Recipe parameter definition

    Defines a parameter with optional bounds and constraints.
    """

    name: str = Field(..., description="Parameter name")
    value: Union[float, int, str, bool] = Field(..., description="Parameter value")
    unit: Optional[str] = Field(default=None, description="Parameter unit")
    min_value: Optional[float] = Field(default=None, description="Minimum value")
    max_value: Optional[float] = Field(default=None, description="Maximum value")
    adjustable: bool = Field(default=True, description="Whether parameter is adjustable")
    description: Optional[str] = Field(default=None, description="Parameter description")

    def validate_value(self, value: Union[float, int, str, bool]) -> bool:
        """Validate value is within bounds"""
        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        return True


class ParameterizedRecipe(BaseModel):
    """Parameterized recipe template

    Represents a recipe template with configurable parameters.
    """

    template_id: str = Field(default_factory=str, description="Template ID")
    name: str = Field(..., description="Template name")
    base_recipe_id: str = Field(..., description="Base recipe ID")

    # Parameter definitions
    parameter_definitions: List[RecipeParameter] = Field(
        default_factory=list, description="Parameter definitions"
    )

    # Parameter constraints
    constraints: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional constraints"
    )

    def instantiate(
        self, parameter_values: Dict[str, Any], created_by: str
    ) -> Recipe:
        """Instantiate a concrete recipe from template

        Args:
            parameter_values: Dictionary of parameter name -> value
            created_by: Username of the creator

        Returns:
            Instantiated Recipe instance

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Validate all required parameters are provided
        missing_params = []
        for param_def in self.parameter_definitions:
            if param_def.adjustable and param_def.name not in parameter_values:
                missing_params.append(param_def.name)

        if missing_params:
            raise ValueError(f"Missing required parameters: {missing_params}")

        # Validate parameter values
        for param_def in self.parameter_definitions:
            if param_def.name in parameter_values:
                value = parameter_values[param_def.name]
                if not param_def.validate_value(value):
                    raise ValueError(
                        f"Parameter {param_def.name} value {value} "
                        f"out of range [{param_def.min_value}, {param_def.max_value}]"
                    )

        # Build recipe parameters
        recipe_params = {}
        for param_def in self.parameter_definitions:
            value = parameter_values.get(param_def.name, param_def.value)
            recipe_params[param_def.name] = {
                "value": value,
                "unit": param_def.unit,
            }

        # Create recipe instance (version will be set by manager)
        return Recipe(
            name=self.name,
            equipment_type="",  # Will be set based on base recipe
            version="1.0.0",
            parameters=recipe_params,
            steps=[],
            created_by=created_by,
        )

    def get_parameter_names(self) -> List[str]:
        """Get list of adjustable parameter names"""
        return [p.name for p in self.parameter_definitions if p.adjustable]


class ValidationResult(BaseModel):
    """Recipe validation result"""

    valid: bool = Field(..., description="Whether validation passed")
    errors: List[str] = Field(
        default_factory=list, description="Validation errors"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Validation warnings"
    )

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors"""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings"""
        return len(self.warnings) > 0

    def add_error(self, error: str) -> None:
        """Add an error message"""
        self.errors.append(error)
        self.valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message"""
        self.warnings.append(warning)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another validation result"""
        combined = ValidationResult(valid=self.valid and other.valid)
        combined.errors = self.errors + other.errors
        combined.warnings = self.warnings + other.warnings
        return combined


import uuid
