"""Tracking API routes.

Provides endpoints for carrier management, wafer tracking, and
traceability queries.
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
from myeap.core.logging import get_logger
from myeap.tracking.models import (
    Carrier as CarrierModel,
    CarrierStatus,
    CarrierType,
    Wafer as WaferModel,
    WaferEvent,
    WaferStatus,
)

logger = get_logger(__name__)

router = APIRouter()

# In-memory tracking stores
_carriers: Dict[str, CarrierModel] = {}
_wafers: Dict[str, WaferModel] = {}
_wafer_events: List[WaferEvent] = []


# ========== Carrier Endpoints ==========


@router.get("/carriers", response_model=List[Dict[str, Any]])
async def list_carriers(
    carrier_type: Optional[str] = Query(None, description="Filter by carrier type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    location: Optional[str] = Query(None, description="Filter by current location"),
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List all carriers with optional filtering.

    Args:
        carrier_type: Optional filter by carrier type.
        status: Optional filter by carrier status.
        location: Optional filter by current location.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of carrier dictionaries.
    """
    all_carriers = list(_carriers.values())

    if carrier_type:
        all_carriers = [c for c in all_carriers if c.carrier_type.value == carrier_type]
    if status:
        all_carriers = [c for c in all_carriers if c.status.value == status]
    if location:
        all_carriers = [c for c in all_carriers if c.current_location == location]

    all_carriers.sort(key=lambda c: c.created_at if c.created_at else datetime.min, reverse=True)

    total = len(all_carriers)
    items = all_carriers[pagination.offset : pagination.offset + pagination.limit]

    result = []
    for carrier in items:
        d = carrier.to_dict()
        d["_total"] = total
        result.append(d)

    return result


@router.get("/carriers/{carrier_id}", response_model=Dict[str, Any])
async def get_carrier(
    carrier_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get carrier by ID.

    Args:
        carrier_id: Carrier unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Carrier dictionary.

    Raises:
        HTTPException: 404 if carrier not found.
    """
    carrier = _carriers.get(carrier_id)
    if not carrier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carrier not found: {carrier_id}",
        )
    return carrier.to_dict()


@router.post("/carriers", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_carrier(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Register a new carrier.

    Args:
        data: Carrier creation data.
        user: Current authenticated user (operator+).

    Returns:
        Created carrier dictionary.

    Raises:
        HTTPException: 400 if validation fails, 409 if carrier ID exists.
    """
    carrier_id = data.get("carrier_id")
    if not carrier_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="carrier_id is required",
        )

    if carrier_id in _carriers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Carrier already exists: {carrier_id}",
        )

    try:
        carrier = CarrierModel(
            carrier_id=carrier_id,
            carrier_type=CarrierType.from_string(data.get("carrier_type", "foup")),
            capacity=data.get("capacity", 25),
            current_location=data.get("current_location"),
            current_position=data.get("current_position"),
            wafer_ids=data.get("wafer_ids", []),
            status=CarrierStatus.from_string(data.get("status", "idle")),
        )

        _carriers[carrier_id] = carrier

        logger.info("carrier_created", carrier_id=carrier_id, capacity=carrier.capacity)
        return carrier.to_dict()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/carriers/{carrier_id}", response_model=Dict[str, Any])
async def update_carrier(
    carrier_id: str,
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Update carrier information.

    Args:
        carrier_id: Carrier unique identifier.
        data: Carrier update data.
        user: Current authenticated user (operator+).

    Returns:
        Updated carrier dictionary.

    Raises:
        HTTPException: 404 if carrier not found.
    """
    carrier = _carriers.get(carrier_id)
    if not carrier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carrier not found: {carrier_id}",
        )

    # Update mutable fields
    if "current_location" in data:
        carrier.current_location = data["current_location"]
    if "current_position" in data:
        carrier.current_position = data["current_position"]
    if "wafer_ids" in data:
        carrier.wafer_ids = data["wafer_ids"]
    if "status" in data:
        carrier.status = CarrierStatus.from_string(data["status"])

    logger.info("carrier_updated", carrier_id=carrier_id)
    return carrier.to_dict()


@router.delete("/carriers/{carrier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_carrier(
    carrier_id: str,
    user: Dict[str, Any] = Depends(require_role("admin")),
) -> None:
    """Delete a carrier.

    Args:
        carrier_id: Carrier unique identifier.
        user: Current authenticated user (admin only).

    Raises:
        HTTPException: 404 if carrier not found.
    """
    if carrier_id not in _carriers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carrier not found: {carrier_id}",
        )

    del _carriers[carrier_id]
    logger.info("carrier_deleted", carrier_id=carrier_id)


@router.post("/carriers/{carrier_id}/load", response_model=Dict[str, Any])
async def load_wafers_to_carrier(
    carrier_id: str,
    wafer_ids: List[str],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Load wafers into a carrier.

    Args:
        carrier_id: Carrier unique identifier.
        wafer_ids: List of wafer IDs to load.
        user: Current authenticated user (operator+).

    Returns:
        Updated carrier dictionary.

    Raises:
        HTTPException: 404 if carrier not found, 400 if capacity exceeded.
    """
    carrier = _carriers.get(carrier_id)
    if not carrier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carrier not found: {carrier_id}",
        )

    # Check capacity
    new_wafers = [w for w in wafer_ids if w not in carrier.wafer_ids]
    if len(carrier.wafer_ids) + len(new_wafers) > carrier.capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exceeds carrier capacity ({carrier.capacity}). "
            f"Current: {len(carrier.wafer_ids)}, New: {len(new_wafers)}",
        )

    carrier.wafer_ids.extend(new_wafers)
    carrier.status = CarrierStatus.LOADED

    logger.info("carrier_loaded", carrier_id=carrier_id, wafer_count=len(new_wafers))
    return carrier.to_dict()


@router.post("/carriers/{carrier_id}/unload", response_model=Dict[str, Any])
async def unload_wafers_from_carrier(
    carrier_id: str,
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Unload all wafers from a carrier.

    Args:
        carrier_id: Carrier unique identifier.
        user: Current authenticated user (operator+).

    Returns:
        Updated carrier dictionary.

    Raises:
        HTTPException: 404 if carrier not found.
    """
    carrier = _carriers.get(carrier_id)
    if not carrier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carrier not found: {carrier_id}",
        )

    unloaded = carrier.wafer_ids.copy()
    carrier.wafer_ids = []
    carrier.status = CarrierStatus.IDLE

    logger.info("carrier_unloaded", carrier_id=carrier_id, count=len(unloaded))
    return carrier.to_dict()


# ========== Wafer Endpoints ==========


@router.get("/wafers", response_model=List[Dict[str, Any]])
async def list_wafers(
    lot_id: Optional[str] = Query(None, description="Filter by lot ID"),
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    wafer_status: Optional[str] = Query(None, description="Filter by wafer status"),
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List wafers with optional filtering.

    Args:
        lot_id: Optional filter by lot ID.
        equipment_id: Optional filter by equipment ID.
        wafer_status: Optional filter by wafer status.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of wafer dictionaries.
    """
    all_wafers = list(_wafers.values())

    if lot_id:
        all_wafers = [w for w in all_wafers if w.lot_id == lot_id]
    if equipment_id:
        all_wafers = [w for w in all_wafers if w.current_location == equipment_id]
    if wafer_status:
        all_wafers = [w for w in all_wafers if w.status.value == wafer_status]

    all_wafers.sort(key=lambda w: w.wafer_id)

    total = len(all_wafers)
    items = all_wafers[pagination.offset : pagination.offset + pagination.limit]

    result = []
    for wafer in items:
        d = wafer.to_dict()
        d["_total"] = total
        result.append(d)

    return result


@router.get("/wafers/{wafer_id}", response_model=Dict[str, Any])
async def get_wafer(
    wafer_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get wafer by ID.

    Args:
        wafer_id: Wafer unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Wafer dictionary with full history.

    Raises:
        HTTPException: 404 if wafer not found.
    """
    wafer = _wafers.get(wafer_id)
    if not wafer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wafer not found: {wafer_id}",
        )
    return wafer.to_dict()


@router.post("/wafers", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register_wafer(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Register a new wafer.

    Args:
        data: Wafer registration data.
        user: Current authenticated user (operator+).

    Returns:
        Created wafer dictionary.
    """
    wafer_id = data.get("wafer_id")
    lot_id = data.get("lot_id")

    if not wafer_id or not lot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="wafer_id and lot_id are required",
        )

    if wafer_id in _wafers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Wafer already exists: {wafer_id}",
        )

    wafer = WaferModel(
        wafer_id=wafer_id,
        lot_id=lot_id,
        current_location=data.get("current_location"),
        current_carrier_id=data.get("current_carrier_id"),
        position=data.get("position"),
        status=WaferStatus.from_string(data.get("status", "in_carrier")),
    )

    _wafers[wafer_id] = wafer

    logger.info("wafer_registered", wafer_id=wafer_id, lot_id=lot_id)
    return wafer.to_dict()


@router.post("/wafers/{wafer_id}/events", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def record_wafer_event(
    wafer_id: str,
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Record a wafer event.

    Args:
        wafer_id: Wafer unique identifier.
        data: Event data.
        user: Current authenticated user (operator+).

    Returns:
        Created event dictionary.

    Raises:
        HTTPException: 404 if wafer not found.
    """
    import uuid as uuid_lib

    wafer = _wafers.get(wafer_id)
    if not wafer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wafer not found: {wafer_id}",
        )

    event = WaferEvent(
        event_id=str(uuid_lib.uuid4()),
        wafer_id=wafer_id,
        lot_id=wafer.lot_id,
        event_type=data.get("event_type", "UNKNOWN"),
        equipment_id=data.get("equipment_id"),
        chamber_id=data.get("chamber_id"),
        carrier_id=data.get("carrier_id"),
        position=data.get("position"),
        recipe_id=data.get("recipe_id"),
        recipe_name=data.get("recipe_name"),
        duration_seconds=data.get("duration_seconds"),
        result=data.get("result"),
        measurements=data.get("measurements"),
    )

    wafer.add_event(event)
    _wafer_events.append(event)

    # Update wafer status based on event type
    if event.event_type in ("PROCESS_START", "CHAMBER_START"):
        wafer.status = WaferStatus.IN_PROCESS
        wafer.current_location = data.get("equipment_id", wafer.current_location)
    elif event.event_type in ("PROCESS_END", "CHAMBER_END"):
        wafer.status = WaferStatus.COMPLETED
    elif event.event_type == "PROCESS_ABORTED":
        wafer.status = WaferStatus.REJECTED

    logger.info(
        "wafer_event_recorded",
        wafer_id=wafer_id,
        event_type=event.event_type,
    )
    return event.to_dict()


@router.get("/wafers/{wafer_id}/history", response_model=List[Dict[str, Any]])
async def get_wafer_history(
    wafer_id: str,
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """Get wafer processing history.

    Args:
        wafer_id: Wafer unique identifier.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of wafer event dictionaries.

    Raises:
        HTTPException: 404 if wafer not found.
    """
    wafer = _wafers.get(wafer_id)
    if not wafer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wafer not found: {wafer_id}",
        )

    events = [e.to_dict() for e in wafer.history]
    return events


@router.get("/events", response_model=List[Dict[str, Any]])
async def list_events(
    wafer_id: Optional[str] = Query(None, description="Filter by wafer ID"),
    lot_id: Optional[str] = Query(None, description="Filter by lot ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List wafer events with optional filtering.

    Args:
        wafer_id: Optional filter by wafer ID.
        lot_id: Optional filter by lot ID.
        event_type: Optional filter by event type.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of wafer event dictionaries.
    """
    events = list(_wafer_events)

    if wafer_id:
        events = [e for e in events if e.wafer_id == wafer_id]
    if lot_id:
        events = [e for e in events if e.lot_id == lot_id]
    if event_type:
        events = [e for e in events if e.event_type == event_type]

    events.sort(key=lambda e: e.timestamp if e.timestamp else datetime.min, reverse=True)

    total = len(events)
    items = events[pagination.offset : pagination.offset + pagination.limit]

    result = []
    for event in items:
        d = event.to_dict()
        d["_total"] = total
        result.append(d)

    return result


@router.get("/trace/{lot_id}", response_model=Dict[str, Any])
async def trace_lot(
    lot_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Trace a lot's complete history.

    Args:
        lot_id: Lot ID to trace.
        user: Current authenticated user (optional).

    Returns:
        Traceability report with lot and wafer details.
    """
    lot_wafers = [w for w in _wafers.values() if w.lot_id == lot_id]
    lot_events = [e for e in _wafer_events if e.lot_id == lot_id]

    # Get involved equipment
    equipment_ids = set()
    for event in lot_events:
        if event.equipment_id:
            equipment_ids.add(event.equipment_id)

    return {
        "lot_id": lot_id,
        "wafer_count": len(lot_wafers),
        "event_count": len(lot_events),
        "equipment_involved": sorted(equipment_ids),
        "wafers": [
            {
                "wafer_id": w.wafer_id,
                "status": w.status.value,
                "current_location": w.current_location,
                "event_count": w.get_event_count(),
            }
            for w in lot_wafers
        ],
        "timeline": [e.to_dict() for e in sorted(lot_events, key=lambda e: e.timestamp)],
    }
