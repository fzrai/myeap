"""Recipe Manager

This module provides the recipe management service.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Awaitable

from myeap.recipe.models import Recipe, RecipeStatus, RecipeStep, ValidationResult
from myeap.recipe.validator import RecipeValidator, get_validator
from myeap.recipe.version_control import VersionControl, get_version_control
from myeap.core.exceptions import RecipeError, ValidationError, EquipmentError
from myeap.core.logging import get_logger
from myeap.observability.metrics import get_metrics_collector

logger = get_logger(__name__)
metrics = get_metrics_collector()


class RecipeManager:
    """Recipe manager

    Responsible for:
    - Recipe CRUD operations
    - Recipe version management
    - Recipe upload/download to/from equipment
    - Recipe comparison
    - Recipe permission management
    - Audit logging
    """

    def __init__(
        self,
        db_manager: Optional[Any] = None,
        secs_driver_manager: Optional[Any] = None,
        validator: Optional[RecipeValidator] = None,
        version_control: Optional[VersionControl] = None,
    ):
        """Initialize recipe manager

        Args:
            db_manager: Database manager instance
            secs_driver_manager: SECS driver manager instance
            validator: Recipe validator (uses default if not provided)
            version_control: Version control (uses default if not provided)
        """
        self.db = db_manager
        self.drivers = secs_driver_manager or {}
        self.validator = validator or get_validator()
        self.version_control = version_control or get_version_control()

        # Recipe storage (in-memory fallback if no DB)
        self._recipes: Dict[str, Recipe] = {}

        # Callbacks
        self._on_recipe_created: Optional[Callable[[Recipe], Awaitable[None]]] = None
        self._on_recipe_updated: Optional[Callable[[Recipe], Awaitable[None]]] = None
        self._on_recipe_deleted: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_recipe_uploaded: Optional[
            Callable[[str, str], Awaitable[None]]
        ] = None

        logger.info("RecipeManager initialized")

    def set_callbacks(
        self,
        on_created: Optional[Callable[[Recipe], Awaitable[None]]] = None,
        on_updated: Optional[Callable[[Recipe], Awaitable[None]]] = None,
        on_deleted: Optional[Callable[[str], Awaitable[None]]] = None,
        on_uploaded: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> None:
        """Set recipe event callbacks

        Args:
            on_created: Called when recipe is created
            on_updated: Called when recipe is updated
            on_deleted: Called when recipe is deleted
            on_uploaded: Called when recipe is uploaded (recipe_id, equipment_id)
        """
        self._on_recipe_created = on_created
        self._on_recipe_updated = on_updated
        self._on_recipe_deleted = on_deleted
        self._on_recipe_uploaded = on_uploaded

    def _validate_recipe(self, recipe: Recipe) -> ValidationResult:
        """Validate recipe

        Args:
            recipe: Recipe to validate

        Raises:
            ValidationError: If validation fails
        """
        result = self.validator.validate(recipe)
        if not result.valid:
            raise ValidationError(
                f"Recipe validation failed: {'; '.join(result.errors)}"
            )
        return result

    async def _audit(
        self, action: str, recipe_or_data: Any, user: Optional[str] = None
    ) -> None:
        """Record audit log

        Args:
            action: Action type
            recipe_or_data: Recipe or data dict
            user: User performing action
        """
        if isinstance(recipe_or_data, Recipe):
            details = {
                "recipe_id": recipe_or_data.id,
                "recipe_name": recipe_or_data.name,
                "version": recipe_or_data.version,
            }
        else:
            details = recipe_or_data

        logger.info(
            "recipe_audit",
            action=action,
            user=user,
            details=details,
        )

    async def create_recipe(
        self, recipe: Recipe, created_by: Optional[str] = None
    ) -> str:
        """Create a new recipe

        Args:
            recipe: Recipe to create
            created_by: Username of creator

        Returns:
            Created recipe ID

        Raises:
            ValidationError: If recipe validation fails
        """
        # Validate recipe
        validation_result = self._validate_recipe(recipe)

        # Log warnings
        for warning in validation_result.warnings:
            logger.warning("recipe_validation_warning", recipe_id=recipe.id, warning=warning)

        # Assign ID and timestamps
        recipe.id = str(uuid.uuid4())
        recipe.created_at = datetime.utcnow()
        recipe.created_by = created_by or recipe.created_by
        recipe.status = RecipeStatus.DRAFT

        # Save to storage
        self._recipes[recipe.id] = recipe

        # Save to DB if available
        if self.db:
            await self.db.save_recipe(recipe)

        # Audit log
        await self._audit("created", recipe, created_by)

        # Callback
        if self._on_recipe_created:
            await self._on_recipe_created(recipe)

        logger.info(
            "recipe_created",
            recipe_id=recipe.id,
            recipe_name=recipe.name,
            version=recipe.version,
        )

        return recipe.id

    async def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        """Get recipe by ID

        Args:
            recipe_id: Recipe ID

        Returns:
            Recipe or None if not found
        """
        # Check memory first
        if recipe_id in self._recipes:
            return self._recipes[recipe_id]

        # Check DB
        if self.db:
            return await self.db.get_recipe(recipe_id)

        return None

    async def get_recipe_by_name(
        self, name: str, equipment_type: str, version: Optional[str] = None
    ) -> Optional[Recipe]:
        """Get recipe by name and equipment type

        Args:
            name: Recipe name
            equipment_type: Equipment type
            version: Optional specific version

        Returns:
            Recipe or None if not found
        """
        # Check DB
        if self.db:
            return await self.db.get_recipe_by_name(name, equipment_type, version)

        # Check memory
        for recipe in self._recipes.values():
            if (
                recipe.name == name
                and recipe.equipment_type == equipment_type
                and (version is None or recipe.version == version)
            ):
                return recipe

        return None

    async def list_recipes(
        self,
        equipment_type: Optional[str] = None,
        status: Optional[RecipeStatus] = None,
        created_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Recipe]:
        """List recipes with filters

        Args:
            equipment_type: Filter by equipment type
            status: Filter by status
            created_by: Filter by creator
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of recipes
        """
        # Get from DB
        if self.db:
            return await self.db.list_recipes(
                equipment_type=equipment_type,
                status=status,
                created_by=created_by,
                limit=limit,
                offset=offset,
            )

        # Filter from memory
        recipes = list(self._recipes.values())

        if equipment_type:
            recipes = [r for r in recipes if r.equipment_type == equipment_type]
        if status:
            recipes = [r for r in recipes if r.status == status]
        if created_by:
            recipes = [r for r in recipes if r.created_by == created_by]

        # Sort by creation time
        recipes.sort(key=lambda r: r.created_at, reverse=True)

        return recipes[offset : offset + limit]

    async def update_recipe(
        self,
        recipe_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None,
    ) -> bool:
        """Update recipe (creates new version)

        Args:
            recipe_id: Recipe ID to update
            updates: Dictionary of updates
            updated_by: Username of updater

        Returns:
            True if successful

        Raises:
            RecipeError: If recipe not found or not editable
        """
        old_recipe = await self.get_recipe(recipe_id)
        if not old_recipe:
            raise RecipeError(f"Recipe not found: {recipe_id}")

        if not old_recipe.is_editable:
            raise RecipeError(
                f"Recipe is not editable. Current status: {old_recipe.status.value}"
            )

        # Create new version
        new_version = self.version_control.increment_version(old_recipe.version)

        # Create new recipe with updates
        new_recipe = old_recipe.model_copy(deep=True)
        new_recipe.id = str(uuid.uuid4())
        new_recipe.version = new_version
        new_recipe.parent_version_id = recipe_id
        new_recipe.created_at = datetime.utcnow()
        new_recipe.created_by = updated_by or old_recipe.created_by

        # Apply updates
        for key, value in updates.items():
            if hasattr(new_recipe, key):
                setattr(new_recipe, key, value)

        # Validate new recipe
        self._validate_recipe(new_recipe)

        # Save new version
        self._recipes[new_recipe.id] = new_recipe
        if self.db:
            await self.db.save_recipe(new_recipe)

        # Audit log
        await self._audit(
            "updated",
            {
                "old_recipe_id": recipe_id,
                "new_recipe_id": new_recipe.id,
                "old_version": old_recipe.version,
                "new_version": new_version,
            },
            updated_by,
        )

        # Callback
        if self._on_recipe_updated:
            await self._on_recipe_updated(new_recipe)

        logger.info(
            "recipe_updated",
            old_recipe_id=recipe_id,
            new_recipe_id=new_recipe.id,
            new_version=new_version,
        )

        return True

    async def delete_recipe(self, recipe_id: str, deleted_by: Optional[str] = None) -> bool:
        """Delete recipe (soft delete - archives it)

        Args:
            recipe_id: Recipe ID to delete
            deleted_by: Username of deleter

        Returns:
            True if successful
        """
        recipe = await self.get_recipe(recipe_id)
        if not recipe:
            raise RecipeError(f"Recipe not found: {recipe_id}")

        # Archive instead of delete
        recipe.status = RecipeStatus.ARCHIVED
        self._recipes[recipe_id] = recipe

        if self.db:
            await self.db.update_recipe(recipe)

        await self._audit("deleted", recipe, deleted_by)

        if self._on_recipe_deleted:
            await self._on_recipe_deleted(recipe_id)

        logger.info("recipe_deleted", recipe_id=recipe_id)
        return True

    async def approve_recipe(
        self, recipe_id: str, approver: str
    ) -> bool:
        """Approve a recipe

        Args:
            recipe_id: Recipe ID to approve
            approver: Username of approver

        Returns:
            True if successful

        Raises:
            RecipeError: If recipe not found or not in approvable state
        """
        recipe = await self.get_recipe(recipe_id)
        if not recipe:
            raise RecipeError(f"Recipe not found: {recipe_id}")

        if recipe.status not in (RecipeStatus.DRAFT, RecipeStatus.PENDING_APPROVAL):
            raise RecipeError(
                f"Recipe cannot be approved. Current status: {recipe.status.value}"
            )

        recipe.status = RecipeStatus.APPROVED
        recipe.approved_by = approver
        recipe.approved_at = datetime.utcnow()

        self._recipes[recipe_id] = recipe
        if self.db:
            await self.db.update_recipe(recipe)

        await self._audit("approved", recipe, approver)

        logger.info("recipe_approved", recipe_id=recipe_id, approver=approver)
        return True

    async def activate_recipe(self, recipe_id: str, activated_by: str) -> bool:
        """Activate an approved recipe

        Args:
            recipe_id: Recipe ID to activate
            activated_by: Username of activator

        Returns:
            True if successful
        """
        recipe = await self.get_recipe(recipe_id)
        if not recipe:
            raise RecipeError(f"Recipe not found: {recipe_id}")

        if recipe.status != RecipeStatus.APPROVED:
            raise RecipeError(
                f"Recipe must be approved before activation. Current status: {recipe.status.value}"
            )

        # Deactivate other active versions with same name
        await self._deactivate_other_versions(recipe.name, recipe.equipment_type)

        recipe.status = RecipeStatus.ACTIVE

        self._recipes[recipe_id] = recipe
        if self.db:
            await self.db.update_recipe(recipe)

        await self._audit("activated", recipe, activated_by)

        logger.info("recipe_activated", recipe_id=recipe_id)
        return True

    async def _deactivate_other_versions(
        self, name: str, equipment_type: str
    ) -> None:
        """Deactivate other active versions of same recipe

        Args:
            name: Recipe name
            equipment_type: Equipment type
        """
        recipes = await self.list_recipes(
            equipment_type=equipment_type,
            status=RecipeStatus.ACTIVE,
        )

        for recipe in recipes:
            if recipe.name == name:
                recipe.status = RecipeStatus.ARCHIVED
                if self.db:
                    await self.db.update_recipe(recipe)

    async def upload_to_equipment(
        self, recipe_id: str, equipment_id: str
    ) -> bool:
        """Upload recipe to equipment

        Args:
            recipe_id: Recipe ID to upload
            equipment_id: Target equipment ID

        Returns:
            True if successful

        Raises:
            RecipeError: If recipe not found
            EquipmentError: If equipment/driver not available
        """
        recipe = await self.get_recipe(recipe_id)
        if not recipe:
            raise RecipeError(f"Recipe not found: {recipe_id}")

        if not recipe.is_active:
            raise RecipeError(
                f"Only active recipes can be uploaded. Current status: {recipe.status.value}"
            )

        driver = self.drivers.get(equipment_id)
        if not driver:
            raise EquipmentError(
                f"SECS driver not available for equipment: {equipment_id}",
                equipment_id=equipment_id,
            )

        # Convert to PPBODY format
        ppbody = self._convert_to_ppbody(recipe)

        # Send S7F23 (Process Program Send)
        await driver.send_process_program(recipe.name, ppbody)

        await self._audit(
            "uploaded",
            {
                "recipe_id": recipe_id,
                "equipment_id": equipment_id,
            },
        )

        if self._on_recipe_uploaded:
            await self._on_recipe_uploaded(recipe_id, equipment_id)

        logger.info(
            "recipe_uploaded",
            recipe_id=recipe_id,
            equipment_id=equipment_id,
        )

        return True

    async def download_from_equipment(
        self, equipment_id: str, recipe_name: str, downloaded_by: str
    ) -> Recipe:
        """Download recipe from equipment

        Args:
            equipment_id: Equipment ID
            recipe_name: Name of recipe to download
            downloaded_by: Username

        Returns:
            Downloaded recipe

        Raises:
            EquipmentError: If equipment/driver not available
        """
        driver = self.drivers.get(equipment_id)
        if not driver:
            raise EquipmentError(
                f"SECS driver not available for equipment: {equipment_id}",
                equipment_id=equipment_id,
            )

        # Send S7F3 (Process Program Request)
        reply = await driver.request_process_program(recipe_name)

        # Parse PPBODY
        recipe = self._parse_ppbody(reply, downloaded_by)

        # Save to storage
        self._recipes[recipe.id] = recipe
        if self.db:
            await self.db.save_recipe(recipe)

        await self._audit(
            "downloaded",
            {
                "recipe_id": recipe.id,
                "equipment_id": equipment_id,
                "recipe_name": recipe_name,
            },
            downloaded_by,
        )

        logger.info(
            "recipe_downloaded",
            recipe_id=recipe.id,
            equipment_id=equipment_id,
            recipe_name=recipe_name,
        )

        return recipe

    def _convert_to_ppbody(self, recipe: Recipe) -> bytes:
        """Convert recipe to PPBODY format

        Args:
            recipe: Recipe to convert

        Returns:
            PPBODY bytes
        """
        # Simple text format for PPBODY
        lines = []
        lines.append(f"RECIPE:{recipe.name}")
        lines.append(f"VERSION:{recipe.version}")
        lines.append(f"TYPE:{recipe.equipment_type}")
        lines.append("")

        # Parameters section
        lines.append("[PARAMETERS]")
        for key, value in recipe.parameters.items():
            lines.append(f"{key}={value}")
        lines.append("")

        # Steps section
        lines.append("[STEPS]")
        for i, step in enumerate(recipe.steps, 1):
            lines.append(f"STEP:{i}")
            lines.append(f"  ID={step.step_id}")
            lines.append(f"  NAME={step.name}")
            lines.append(f"  DURATION={step.duration}")
            for param_key, param_value in step.parameters.items():
                lines.append(f"  {param_key}={param_value}")
            lines.append("")

        return "\n".join(lines).encode("utf-8")

    def _parse_ppbody(self, ppbody: bytes, created_by: str) -> Recipe:
        """Parse PPBODY format to recipe

        Args:
            ppbody: PPBODY bytes
            created_by: Username

        Returns:
            Parsed recipe
        """
        content = ppbody.decode("utf-8")
        lines = content.strip().split("\n")

        name = ""
        equipment_type = ""
        parameters: Dict[str, Any] = {}
        steps: List[RecipeStep] = []
        current_section = ""
        current_step: Optional[Dict[str, Any]] = None

        for line in lines:
            line = line.strip()

            if line == "[PARAMETERS]":
                current_section = "parameters"
                continue
            elif line == "[STEPS]":
                current_section = "steps"
                continue
            elif line.startswith("RECIPE:"):
                name = line.split(":", 1)[1]
            elif line.startswith("TYPE:"):
                equipment_type = line.split(":", 1)[1]
            elif current_section == "parameters" and "=" in line:
                key, value = line.split("=", 1)
                try:
                    parameters[key] = float(value)
                except ValueError:
                    parameters[key] = value
            elif current_section == "steps":
                if line.startswith("STEP:"):
                    if current_step:
                        steps.append(RecipeStep(**current_step))
                    step_num = line.split(":")[1]
                    current_step = {
                        "step_id": f"step_{step_num}",
                        "name": "",
                        "duration": 0.0,
                        "parameters": {},
                    }
                elif current_step:
                    if line.startswith("  ") and "=" in line:
                        key, value = line.strip().split("=", 1)
                        if key == "ID":
                            current_step["step_id"] = value
                        elif key == "NAME":
                            current_step["name"] = value
                        elif key == "DURATION":
                            current_step["duration"] = float(value)
                        else:
                            try:
                                current_step["parameters"][key] = float(value)
                            except ValueError:
                                current_step["parameters"][key] = value

        # Add last step
        if current_step:
            steps.append(RecipeStep(**current_step))

        return Recipe(
            name=name,
            equipment_type=equipment_type,
            version="1.0.0",
            parameters=parameters,
            steps=steps,
            created_by=created_by,
        )

    async def compare_recipes(
        self, recipe_id1: str, recipe_id2: str
    ) -> Dict[str, Any]:
        """Compare two recipes

        Args:
            recipe_id1: First recipe ID
            recipe_id2: Second recipe ID

        Returns:
            Dictionary with comparison results
        """
        recipe1 = await self.get_recipe(recipe_id1)
        recipe2 = await self.get_recipe(recipe_id2)

        if not recipe1:
            raise RecipeError(f"Recipe not found: {recipe_id1}")
        if not recipe2:
            raise RecipeError(f"Recipe not found: {recipe_id2}")

        differences = []

        # Compare parameters
        all_keys = set(list(recipe1.parameters.keys()) + list(recipe2.parameters.keys()))
        for key in sorted(all_keys):
            v1 = recipe1.parameters.get(key)
            v2 = recipe2.parameters.get(key)
            if v1 != v2:
                differences.append(
                    {
                        "type": "parameter",
                        "name": key,
                        "old_value": v1,
                        "new_value": v2,
                    }
                )

        # Compare steps
        step_ids1 = {s.step_id for s in recipe1.steps}
        step_ids2 = {s.step_id for s in recipe2.steps}

        # Added steps
        for step in recipe2.steps:
            if step.step_id not in step_ids1:
                differences.append(
                    {"type": "step_added", "step_id": step.step_id, "name": step.name}
                )

        # Removed steps
        for step in recipe1.steps:
            if step.step_id not in step_ids2:
                differences.append(
                    {"type": "step_removed", "step_id": step.step_id, "name": step.name}
                )

        # Modified steps
        step_map1 = {s.step_id: s for s in recipe1.steps}
        step_map2 = {s.step_id: s for s in recipe2.steps}

        for step_id in step_ids1 & step_ids2:
            s1 = step_map1[step_id]
            s2 = step_map2[step_id]

            if s1.name != s2.name:
                differences.append(
                    {
                        "type": "step_modified",
                        "step_id": step_id,
                        "field": "name",
                        "old_value": s1.name,
                        "new_value": s2.name,
                    }
                )

            if s1.duration != s2.duration:
                differences.append(
                    {
                        "type": "step_modified",
                        "step_id": step_id,
                        "field": "duration",
                        "old_value": s1.duration,
                        "new_value": s2.duration,
                    }
                )

        return {
            "recipe1": {
                "id": recipe_id1,
                "name": recipe1.name,
                "version": recipe1.version,
            },
            "recipe2": {
                "id": recipe_id2,
                "name": recipe2.name,
                "version": recipe2.version,
            },
            "differences": differences,
            "difference_count": len(differences),
        }

    async def get_recipe_history(self, recipe_id: str) -> List[Recipe]:
        """Get recipe version history

        Args:
            recipe_id: Starting recipe ID

        Returns:
            List of recipes from oldest to newest
        """
        history = []
        current_id: Optional[str] = recipe_id

        while current_id:
            recipe = await self.get_recipe(current_id)
            if not recipe:
                break
            history.insert(0, recipe)
            current_id = recipe.parent_version_id

        return history

    async def clone_recipe(
        self, recipe_id: str, new_name: str, cloned_by: str
    ) -> str:
        """Clone a recipe with a new name

        Args:
            recipe_id: Source recipe ID
            new_name: Name for cloned recipe
            cloned_by: Username

        Returns:
            ID of cloned recipe
        """
        source = await self.get_recipe(recipe_id)
        if not source:
            raise RecipeError(f"Recipe not found: {recipe_id}")

        # Create clone
        clone = source.model_copy(deep=True)
        clone.id = str(uuid.uuid4())
        clone.name = new_name
        clone.version = "1.0.0"
        clone.parent_version_id = None
        clone.status = RecipeStatus.DRAFT
        clone.created_at = datetime.utcnow()
        clone.created_by = cloned_by
        clone.approved_by = None
        clone.approved_at = None

        # Save clone
        self._recipes[clone.id] = clone
        if self.db:
            await self.db.save_recipe(clone)

        await self._audit(
            "cloned",
            {"source_id": recipe_id, "clone_id": clone.id, "new_name": new_name},
            cloned_by,
        )

        logger.info("recipe_cloned", source_id=recipe_id, clone_id=clone.id)
        return clone.id


# Global manager instance
_manager: Optional[RecipeManager] = None


def get_recipe_manager() -> RecipeManager:
    """Get global recipe manager instance"""
    global _manager
    if _manager is None:
        _manager = RecipeManager()
    return _manager
