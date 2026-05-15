"""Equipment API routes.

Provides CRUD and management endpoints for equipment resources.
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
from myeap.core.exceptions import EquipmentError
from myeap.core.logging import get_logger
from myeap.device.equipment import Equipment, EquipmentStatus, EquipmentType
from myeap.device.registry import EquipmentRegistry

logger = get_logger(__name__)

router = APIRouter()

# In-memory storage (backed by EquipmentRegistry singleton)
_registry = EquipmentRegistry()
_equipment_store: Dict[str, Dict[str, Any]] = {}


def _dict_to_equipment(data: Dict[str, Any]) -> Equipment:
    """Convert dictionary to Equipment domain object."""
    return Equipment(
        equipment_id=data["equipment_id"],
        equipment_type=EquipmentType.from_string(data.get("equipment_type", "unknown")),
        name=data["name"],
        host=data.get("host", "unknown"),
        port=data.get("port", 5000),
        device_id=data.get("device_id", 0),
        status=EquipmentStatus(data.get("status", "UNKNOWN")),
        sub_status=data.get("sub_status"),
        manufacturer=data.get("manufacturer"),
        model=data.get("model"),
        serial_number=data.get("serial_number"),
        software_version=data.get("software_version"),
        capabilities=data.get("capabilities", {}),
        supported_recipes=data.get("supported_recipes", []),
        config=data.get("config", {}),
    )


def _equipment_to_dict(eq: Equipment) -> Dict[str, Any]:
    """Convert Equipment domain object to API response dict."""
    result = {
        "equipment_id": eq.equipment_id,
        "name": eq.name,
        "equipment_type": eq.equipment_type.value,
        "host": eq.host,
        "port": eq.port,
        "device_id": eq.device_id,
        "status": eq.status.value,
        "sub_status": eq.sub_status,
        "is_connected": eq.is_connected,
        "is_available": eq.is_available,
        "is_online": eq.is_online,
        "manufacturer": eq.manufacturer,
        "model": eq.model,
        "serial_number": eq.serial_number,
        "software_version": eq.software_version,
        "capabilities": eq.capabilities,
        "supported_recipes": eq.supported_recipes,
        "chambers": {
            k: v.to_dict() for k, v in eq.chambers.items()
        } if eq.chambers else {},
        "last_connected": eq.last_connected.isoformat() if eq.last_connected else None,
        "last_message": eq.last_message.isoformat() if eq.last_message else None,
    }
    return result


@router.get("/", response_model=List[Dict[str, Any]])
async def list_equipment(
    equipment_type: Optional[str] = Query(None, description="Filter by equipment type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List all equipment with optional filtering.

    Args:
        equipment_type: Optional filter by equipment type.
        status: Optional filter by equipment status.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of equipment dictionaries.
    """
    all_equipment = list(_equipment_store.values())

    if equipment_type:
        all_equipment = [
            e for e in all_equipment
            if e.get("equipment_type") == equipment_type
        ]
    if status:
        all_equipment = [
            e for e in all_equipment
            if e.get("status") == status
        ]

    # Sort by name
    all_equipment.sort(key=lambda e: e.get("name", ""))

    total = len(all_equipment)
    items = all_equipment[pagination.offset : pagination.offset + pagination.limit]

    for item in items:
        item["total"] = total

    return items


@router.get("/stats", response_model=Dict[str, Any])
async def get_equipment_stats(
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get equipment statistics summary.

    Returns:
        Dictionary with equipment statistics.
    """
    all_equipment = list(_equipment_store.values())
    total = len(all_equipment)
    connected = sum(1 for e in all_equipment if e.get("is_connected"))
    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}

    for eq in all_equipment:
        eq_type = eq.get("equipment_type", "unknown")
        by_type[eq_type] = by_type.get(eq_type, 0) + 1
        eq_status = eq.get("status", "UNKNOWN")
        by_status[eq_status] = by_status.get(eq_status, 0) + 1

    return {
        "total": total,
        "connected": connected,
        "disconnected": total - connected,
        "by_type": by_type,
        "by_status": by_status,
    }


@router.get("/{equipment_id}", response_model=Dict[str, Any])
async def get_equipment(
    equipment_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get equipment by ID.

    Args:
        equipment_id: Equipment unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Equipment dictionary.

    Raises:
        HTTPException: 404 if equipment not found.
    """
    equipment = _equipment_store.get(equipment_id)
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment not found: {equipment_id}",
        )
    return equipment


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_equipment(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Register new equipment.

    Args:
        data: Equipment creation data.
        user: Current authenticated user (engineer+).

    Returns:
        Created equipment dictionary.

    Raises:
        HTTPException: 400 if equipment_id is missing or already exists.
    """
    equipment_id = data.get("equipment_id")
    if not equipment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="equipment_id is required",
        )

    if equipment_id in _equipment_store:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Equipment already exists: {equipment_id}",
        )

    eq_dict = {
        "equipment_id": equipment_id,
        "name": data.get("name", equipment_id),
        "equipment_type": data.get("equipment_type", "unknown"),
        "host": data.get("host", ""),
        "port": data.get("port", 5000),
        "device_id": data.get("device_id", 0),
        "status": data.get("status", "UNKNOWN"),
        "sub_status": data.get("sub_status"),
        "is_connected": data.get("is_connected", False),
        "is_available": data.get("is_available", False),
        "is_online": data.get("is_online", False),
        "manufacturer": data.get("manufacturer"),
        "model": data.get("model"),
        "serial_number": data.get("serial_number"),
        "software_version": data.get("software_version"),
        "capabilities": data.get("capabilities", {}),
        "supported_recipes": data.get("supported_recipes", []),
        "chambers": {},
        "last_connected": None,
        "last_message": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _equipment_store[equipment_id] = eq_dict

    # Also register in EquipmentRegistry
    try:
        eq = _dict_to_equipment(data)
        await _registry.register(eq, None)
    except Exception as e:
        logger.warning("registry_register_failed", error=str(e))

    logger.info("equipment_created", equipment_id=equipment_id)
    return eq_dict


@router.put("/{equipment_id}", response_model=Dict[str, Any])
async def update_equipment(
    equipment_id: str,
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Update equipment (full replacement).

    Args:
        equipment_id: Equipment unique identifier.
        data: Complete equipment data.
        user: Current authenticated user (engineer+).

    Returns:
        Updated equipment dictionary.

    Raises:
        HTTPException: 404 if equipment not found.
    """
    if equipment_id not in _equipment_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment not found: {equipment_id}",
        )

    existing = _equipment_store[equipment_id]
    existing.update({
        "name": data.get("name", existing["name"]),
        "equipment_type": data.get("equipment_type", existing["equipment_type"]),
        "host": data.get("host", existing.get("host", "")),
        "port": data.get("port", existing.get("port", 5000)),
        "device_id": data.get("device_id", existing.get("device_id", 0)),
        "status": data.get("status", existing["status"]),
        "sub_status": data.get("sub_status", existing.get("sub_status")),
        "is_connected": data.get("is_connected", existing.get("is_connected", False)),
        "manufacturer": data.get("manufacturer", existing.get("manufacturer")),
        "model": data.get("model", existing.get("model")),
        "serial_number": data.get("serial_number", existing.get("serial_number")),
        "software_version": data.get("software_version", existing.get("software_version")),
        "capabilities": data.get("capabilities", existing.get("capabilities", {})),
        "supported_recipes": data.get("supported_recipes", existing.get("supported_recipes", [])),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info("equipment_updated", equipment_id=equipment_id)
    return existing


@router.patch("/{equipment_id}", response_model=Dict[str, Any])
async def patch_equipment(
    equipment_id: str,
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Partially update equipment.

    Args:
        equipment_id: Equipment unique identifier.
        data: Partial equipment data to update.
        user: Current authenticated user (engineer+).

    Returns:
        Updated equipment dictionary.

    Raises:
        HTTPException: 404 if equipment not found.
    """
    if equipment_id not in _equipment_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment not found: {equipment_id}",
        )

    existing = _equipment_store[equipment_id]
    updatable = [
        "name", "equipment_type", "host", "port", "device_id",
        "status", "sub_status", "is_connected",
        "manufacturer", "model", "serial_number", "software_version",
        "capabilities", "supported_recipes",
    ]

    for key in updatable:
        if key in data:
            existing[key] = data[key]

    existing["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Sync status changes
    if "status" in data:
        existing["is_online"] = data["status"] != "OFFLINE"
        existing["is_available"] = data["status"] in ("IDLE", "PAUSED")

    logger.info("equipment_patched", equipment_id=equipment_id)
    return existing


@router.delete("/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_equipment(
    equipment_id: str,
    user: Dict[str, Any] = Depends(require_role("admin")),
) -> None:
    """Delete equipment.

    Args:
        equipment_id: Equipment unique identifier.
        user: Current authenticated user (admin only).

    Raises:
        HTTPException: 404 if equipment not found.
    """
    if equipment_id not in _equipment_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment not found: {equipment_id}",
        )

    del _equipment_store[equipment_id]
    logger.info("equipment_deleted", equipment_id=equipment_id)


@router.get("/{equipment_id}/status", response_model=Dict[str, Any])
async def get_equipment_status(
    equipment_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get equipment status.

    Args:
        equipment_id: Equipment unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Equipment status dictionary.

    Raises:
        HTTPException: 404 if equipment not found.
    """
    equipment = _equipment_store.get(equipment_id)
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment not found: {equipment_id}",
        )

    return {
        "equipment_id": equipment_id,
        "status": equipment.get("status", "UNKNOWN"),
        "sub_status": equipment.get("sub_status"),
        "is_connected": equipment.get("is_connected", False),
        "is_available": equipment.get("is_available", False),
        "is_online": equipment.get("is_online", False),
        "last_message": equipment.get("last_message"),
    }


@router.post("/{equipment_id}/command", response_model=Dict[str, Any])
async def send_command(
    equipment_id: str,
    command: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Send command to equipment.

    Args:
        equipment_id: Equipment unique identifier.
        command: Command data with 'command_type' and optional 'parameters'.
        user: Current authenticated user (operator+).

    Returns:
        Command execution result.

    Raises:
        HTTPException: 404 if equipment not found.
    """
    if equipment_id not in _equipment_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment not found: {equipment_id}",
        )

    command_type = command.get("command_type", "UNKNOWN")
    parameters = command.get("parameters", {})

    logger.info(
        "command_sent",
        equipment_id=equipment_id,
        command_type=command_type,
    )

    return {
        "equipment_id": equipment_id,
        "command_type": command_type,
        "parameters": parameters,
        "status": "SENT",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"Command '{command_type}' sent to equipment '{equipment_id}'",
    }


@router.get("/{equipment_id}/stats/details", response_model=Dict[str, Any])
async def get_equipment_detailed_stats(
    equipment_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get detailed equipment statistics.

    Args:
        equipment_id: Equipment unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Equipment statistics dictionary.

    Raises:
        HTTPException: 404 if equipment not found.
    """
    if equipment_id not in _equipment_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment not found: {equipment_id}",
        )

    eq = _equipment_store[equipment_id]

    return {
        "equipment_id": equipment_id,
        "name": eq.get("name"),
        "equipment_type": eq.get("equipment_type"),
        "status": eq.get("status"),
        "uptime_percent": 99.5,  # Placeholder
        "total_processed": 0,
        "avg_cycle_time": 0,
        "mttr": 0,  # Mean Time To Repair
        "mtbf": 0,  # Mean Time Between Failures
    }
