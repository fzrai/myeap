"""Recipe API routes.

Provides CRUD and workflow management endpoints for recipes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from myeap.api.dependencies import (
    Pagination,
    get_optional_user,
    get_current_user,
    require_role,
)
from myeap.core.exceptions import RecipeError, ValidationError
from myeap.core.logging import get_logger
from myeap.recipe.models import Recipe, RecipeStatus, RecipeStep, ValidationResult
from myeap.recipe.manager import get_recipe_manager
from myeap.recipe.validator import get_validator

logger = get_logger(__name__)

router = APIRouter()

# In-memory recipe store
_recipes: Dict[str, Recipe] = {}


def _recipe_to_dict(recipe: Recipe) -> Dict[str, Any]:
    """Convert Recipe domain object to API response dict."""
    return recipe.to_dict()


def _dict_to_recipe(data: Dict[str, Any]) -> Recipe:
    """Convert API dict to Recipe domain object."""
    steps = []
    for step_data in data.get("steps", []):
        steps.append(RecipeStep(**step_data))

    return Recipe(
        id=data.get("id", ""),
        name=data.get("name", ""),
        equipment_type=data.get("equipment_type", ""),
        version=data.get("version", "1.0.0"),
        description=data.get("description"),
        parameters=data.get("parameters", {}),
        steps=steps,
        parent_version_id=data.get("parent_version_id"),
        status=RecipeStatus(data.get("status", "draft")),
        created_by=data.get("created_by", "unknown"),
        created_at=datetime.now(timezone.utc),
        approved_by=data.get("approved_by"),
        approved_at=datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") else None,
        fdc_limits=data.get("fdc_limits"),
        adjustable_parameters=data.get("adjustable_parameters", []),
    )


@router.get("/", response_model=List[Dict[str, Any]])
async def list_recipes(
    equipment_type: Optional[str] = Query(None, description="Filter by equipment type"),
    status: Optional[str] = Query(None, description="Filter by recipe status"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    search: Optional[str] = Query(None, description="Search by name"),
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List all recipes with optional filtering.

    Args:
        equipment_type: Optional filter by equipment type.
        status: Optional filter by recipe status.
        created_by: Optional filter by creator.
        search: Optional search by recipe name.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of recipe dictionaries.
    """
    all_recipes = list(_recipes.values())

    if equipment_type:
        all_recipes = [r for r in all_recipes if r.equipment_type == equipment_type]
    if status:
        all_recipes = [r for r in all_recipes if r.status.value == status]
    if created_by:
        all_recipes = [r for r in all_recipes if r.created_by == created_by]
    if search:
        search_lower = search.lower()
        all_recipes = [r for r in all_recipes if search_lower in r.name.lower()]

    # Sort by creation time, newest first
    all_recipes.sort(key=lambda r: r.created_at if r.created_at else datetime.min, reverse=True)

    total = len(all_recipes)
    items = all_recipes[pagination.offset : pagination.offset + pagination.limit]

    result = []
    for recipe in items:
        d = recipe.to_dict()
        d["_total"] = total
        result.append(d)

    return result


@router.get("/{recipe_id}", response_model=Dict[str, Any])
async def get_recipe(
    recipe_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get recipe by ID.

    Args:
        recipe_id: Recipe unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Recipe dictionary.

    Raises:
        HTTPException: 404 if recipe not found.
    """
    recipe = _recipes.get(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id}",
        )
    return recipe.to_dict()


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_recipe(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Create a new recipe.

    Args:
        data: Recipe creation data.
        user: Current authenticated user (engineer+).

    Returns:
        Created recipe dictionary.

    Raises:
        HTTPException: 400 if validation fails.
    """
    import uuid as uuid_lib

    recipe_id = data.get("id") or str(uuid_lib.uuid4())

    try:
        recipe = _dict_to_recipe(data)
        recipe.id = recipe_id
        recipe.created_by = data.get("created_by", user.get("username", "unknown"))

        # Validate recipe
        validator = get_validator()
        validation = validator.validate(recipe)
        if validation.has_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(validation.errors),
            )

        recipe.status = RecipeStatus.DRAFT
        _recipes[recipe_id] = recipe

        logger.info("recipe_created", recipe_id=recipe_id, name=recipe.name)
        return recipe.to_dict()

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{recipe_id}", response_model=Dict[str, Any])
async def update_recipe(
    recipe_id: str,
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Update a recipe (creates a new version).

    Args:
        recipe_id: Recipe unique identifier.
        data: Recipe update data.
        user: Current authenticated user (engineer+).

    Returns:
        Updated recipe dictionary.

    Raises:
        HTTPException: 404 if recipe not found, 400 if not editable.
    """
    import uuid as uuid_lib

    old_recipe = _recipes.get(recipe_id)
    if not old_recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id}",
        )

    if not old_recipe.is_editable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recipe not editable. Status: {old_recipe.status.value}",
        )

    # Create new version based on updates
    new_id = str(uuid_lib.uuid4())

    # Increment version
    version_parts = old_recipe.version.split(".")
    new_patch = int(version_parts[2]) + 1
    new_version = f"{version_parts[0]}.{version_parts[1]}.{new_patch}"

    try:
        new_recipe = _dict_to_recipe(data)
    except Exception:
        # Use old recipe fields and apply updates
        new_data = old_recipe.to_dict()
        new_data.update(data)
        new_recipe = _dict_to_recipe(new_data)

    new_recipe.id = new_id
    new_recipe.version = new_version
    new_recipe.parent_version_id = recipe_id
    new_recipe.created_at = datetime.now(timezone.utc)
    new_recipe.created_by = data.get("created_by", user.get("username", "unknown"))
    new_recipe.status = RecipeStatus.DRAFT

    _recipes[new_id] = new_recipe

    # Archive old version
    old_recipe.status = RecipeStatus.ARCHIVED

    logger.info("recipe_updated", old_id=recipe_id, new_id=new_id, version=new_version)
    return new_recipe.to_dict()


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: str,
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> None:
    """Delete (archive) a recipe.

    Args:
        recipe_id: Recipe unique identifier.
        user: Current authenticated user (engineer+).

    Raises:
        HTTPException: 404 if recipe not found.
    """
    recipe = _recipes.get(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id}",
        )

    # Soft delete - archive
    recipe.status = RecipeStatus.ARCHIVED
    logger.info("recipe_archived", recipe_id=recipe_id)


@router.post("/{recipe_id}/upload", response_model=Dict[str, Any])
async def upload_recipe(
    recipe_id: str,
    equipment_id: str = Query(..., description="Target equipment ID"),
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Upload a recipe to equipment.

    Args:
        recipe_id: Recipe unique identifier.
        equipment_id: Target equipment ID.
        user: Current authenticated user (engineer+).

    Returns:
        Upload result dictionary.

    Raises:
        HTTPException: 404 if recipe not found, 400 if not active.
    """
    recipe = _recipes.get(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id}",
        )

    if not recipe.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only active recipes can be uploaded. Status: {recipe.status.value}",
        )

    logger.info(
        "recipe_uploaded",
        recipe_id=recipe_id,
        equipment_id=equipment_id,
    )

    return {
        "recipe_id": recipe_id,
        "equipment_id": equipment_id,
        "status": "UPLOADED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"Recipe '{recipe.name}' uploaded to equipment '{equipment_id}'",
    }


@router.post("/{recipe_id}/approve", response_model=Dict[str, Any])
async def approve_recipe(
    recipe_id: str,
    approver: str = Query(..., description="Approver username"),
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Approve a recipe.

    Args:
        recipe_id: Recipe unique identifier.
        approver: Approver username.
        user: Current authenticated user (engineer+).

    Returns:
        Approved recipe dictionary.

    Raises:
        HTTPException: 404 if recipe not found, 400 if not in approvable state.
    """
    recipe = _recipes.get(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id}",
        )

    if recipe.status not in (RecipeStatus.DRAFT, RecipeStatus.PENDING_APPROVAL):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recipe cannot be approved. Status: {recipe.status.value}",
        )

    recipe.status = RecipeStatus.APPROVED
    recipe.approved_by = approver
    recipe.approved_at = datetime.now(timezone.utc)

    logger.info("recipe_approved", recipe_id=recipe_id, approver=approver)
    return recipe.to_dict()


@router.post("/{recipe_id}/activate", response_model=Dict[str, Any])
async def activate_recipe(
    recipe_id: str,
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Activate an approved recipe.

    Args:
        recipe_id: Recipe unique identifier.
        user: Current authenticated user (engineer+).

    Returns:
        Activated recipe dictionary.

    Raises:
        HTTPException: 404 if recipe not found, 400 if not approved.
    """
    recipe = _recipes.get(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id}",
        )

    if recipe.status != RecipeStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recipe must be approved first. Status: {recipe.status.value}",
        )

    # Deactivate other active versions with same name
    for existing in _recipes.values():
        if (
            existing.name == recipe.name
            and existing.status == RecipeStatus.ACTIVE
            and existing.id != recipe_id
        ):
            existing.status = RecipeStatus.ARCHIVED

    recipe.status = RecipeStatus.ACTIVE

    logger.info("recipe_activated", recipe_id=recipe_id)
    return recipe.to_dict()


@router.get("/{recipe_id}/history", response_model=List[Dict[str, Any]])
async def get_recipe_history(
    recipe_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """Get recipe version history.

    Args:
        recipe_id: Recipe unique identifier.
        user: Current authenticated user (optional).

    Returns:
        List of recipe versions from oldest to newest.
    """
    recipe = _recipes.get(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id}",
        )

    history = []
    current_id: Optional[str] = recipe_id

    while current_id:
        r = _recipes.get(current_id)
        if not r:
            break
        history.insert(0, r.to_dict())
        current_id = r.parent_version_id

    return history


@router.post("/compare", response_model=Dict[str, Any])
async def compare_recipes(
    recipe_id1: str = Query(..., description="First recipe ID"),
    recipe_id2: str = Query(..., description="Second recipe ID"),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Compare two recipes.

    Args:
        recipe_id1: First recipe ID.
        recipe_id2: Second recipe ID.
        user: Current authenticated user (optional).

    Returns:
        Comparison results with differences.

    Raises:
        HTTPException: 404 if either recipe not found.
    """
    recipe1 = _recipes.get(recipe_id1)
    recipe2 = _recipes.get(recipe_id2)

    if not recipe1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id1}",
        )
    if not recipe2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id2}",
        )

    differences = []

    # Compare parameters
    all_keys = set(list(recipe1.parameters.keys()) + list(recipe2.parameters.keys()))
    for key in sorted(all_keys):
        v1 = recipe1.parameters.get(key)
        v2 = recipe2.parameters.get(key)
        if v1 != v2:
            differences.append({
                "type": "parameter",
                "name": key,
                "old_value": v1,
                "new_value": v2,
            })

    # Compare steps
    step_ids1 = {s.step_id for s in recipe1.steps}
    step_ids2 = {s.step_id for s in recipe2.steps}

    for step in recipe2.steps:
        if step.step_id not in step_ids1:
            differences.append({
                "type": "step_added",
                "step_id": step.step_id,
                "name": step.name,
            })

    for step in recipe1.steps:
        if step.step_id not in step_ids2:
            differences.append({
                "type": "step_removed",
                "step_id": step.step_id,
                "name": step.name,
            })

    # Modified steps
    step_map1 = {s.step_id: s for s in recipe1.steps}
    step_map2 = {s.step_id: s for s in recipe2.steps}
    for step_id in step_ids1 & step_ids2:
        s1 = step_map1[step_id]
        s2 = step_map2[step_id]
        if s1.name != s2.name:
            differences.append({
                "type": "step_modified",
                "step_id": step_id,
                "field": "name",
                "old_value": s1.name,
                "new_value": s2.name,
            })
        if s1.duration != s2.duration:
            differences.append({
                "type": "step_modified",
                "step_id": step_id,
                "field": "duration",
                "old_value": s1.duration,
                "new_value": s2.duration,
            })

    return {
        "recipe1": {"id": recipe_id1, "name": recipe1.name, "version": recipe1.version},
        "recipe2": {"id": recipe_id2, "name": recipe2.name, "version": recipe2.version},
        "differences": differences,
        "difference_count": len(differences),
    }


@router.post("/{recipe_id}/clone", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def clone_recipe(
    recipe_id: str,
    new_name: str = Query(..., description="Name for cloned recipe"),
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Clone a recipe with a new name.

    Args:
        recipe_id: Source recipe ID.
        new_name: Name for the cloned recipe.
        user: Current authenticated user (engineer+).

    Returns:
        Cloned recipe dictionary.

    Raises:
        HTTPException: 404 if recipe not found.
    """
    import uuid as uuid_lib

    source = _recipes.get(recipe_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id}",
        )

    new_id = str(uuid_lib.uuid4())
    clone = source.model_copy(deep=True)
    clone.id = new_id
    clone.name = new_name
    clone.version = "1.0.0"
    clone.parent_version_id = None
    clone.status = RecipeStatus.DRAFT
    clone.created_at = datetime.now(timezone.utc)
    clone.created_by = user.get("username", "unknown")
    clone.approved_by = None
    clone.approved_at = None

    _recipes[new_id] = clone

    logger.info("recipe_cloned", source_id=recipe_id, clone_id=new_id, new_name=new_name)
    return clone.to_dict()


@router.get("/{recipe_id}/validate", response_model=Dict[str, Any])
async def validate_recipe(
    recipe_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Validate a recipe and return results.

    Args:
        recipe_id: Recipe unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Validation result with errors and warnings.

    Raises:
        HTTPException: 404 if recipe not found.
    """
    recipe = _recipes.get(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe not found: {recipe_id}",
        )

    validator = get_validator()
    result = validator.validate(recipe)

    return {
        "recipe_id": recipe_id,
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
    }
