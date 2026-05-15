"""Alarm API routes.

Provides CRUD and lifecycle management endpoints for alarms.
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
from myeap.alarm.models import Alarm, AlarmDefinition, AlarmEscalationPolicy, AlarmSeverity, AlarmStatus, AlarmStatistics
from myeap.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# In-memory alarm stores
_active_alarms: Dict[str, Alarm] = {}
_alarm_definitions: Dict[str, AlarmDefinition] = {}
_alarm_history: List[Alarm] = []
_suppressed_codes: set = set()


def _alarm_to_dict(alarm: Alarm) -> Dict[str, Any]:
    """Convert Alarm to API response dict."""
    return alarm.to_dict()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_alarms(
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    include_history: bool = Query(False, description="Include cleared/history alarms"),
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List alarms with optional filtering.

    Args:
        equipment_id: Optional filter by equipment ID.
        severity: Optional filter by severity.
        status: Optional filter by status.
        include_history: Whether to include cleared/history alarms.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of alarm dictionaries.
    """
    if include_history:
        all_alarms = list(_active_alarms.values()) + list(_alarm_history)
    else:
        all_alarms = list(_active_alarms.values())

    if equipment_id:
        all_alarms = [a for a in all_alarms if a.equipment_id == equipment_id]
    if severity:
        all_alarms = [a for a in all_alarms if a.severity.value == severity]
    if status:
        all_alarms = [a for a in all_alarms if a.status.value == status]

    # Sort by severity priority then raised time
    all_alarms.sort(key=lambda a: (a.severity.priority, a.raised_at if a.raised_at else datetime.min))

    total = len(all_alarms)
    items = all_alarms[pagination.offset : pagination.offset + pagination.limit]

    result = []
    for alarm in items:
        d = alarm.to_dict()
        d["_total"] = total
        result.append(d)

    return result


@router.get("/stats", response_model=Dict[str, Any])
async def get_alarm_statistics(
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get alarm statistics.

    Args:
        equipment_id: Optional filter by equipment ID.
        user: Current authenticated user (optional).

    Returns:
        Alarm statistics dictionary.
    """
    active = list(_active_alarms.values())
    if equipment_id:
        active = [a for a in active if a.equipment_id == equipment_id]

    by_severity: Dict[str, int] = {}
    by_equipment: Dict[str, int] = {}
    by_status: Dict[str, int] = {}

    for alarm in active:
        sev = alarm.severity.value
        by_severity[sev] = by_severity.get(sev, 0) + 1

        eq_id = alarm.equipment_id
        by_equipment[eq_id] = by_equipment.get(eq_id, 0) + 1

        st = alarm.status.value
        by_status[st] = by_status.get(st, 0) + 1

    # Calculate MTTA (Mean Time to Acknowledge)
    acknowledged = [a for a in active if a.is_acknowledged and a.acknowledged_at]
    mtta = None
    if acknowledged:
        total_ack_time = sum(
            (a.acknowledged_at - a.raised_at).total_seconds()
            for a in acknowledged
        )
        mtta = round(total_ack_time / len(acknowledged), 2)

    return {
        "total_count": len(active) + len(_alarm_history),
        "active_count": len(active),
        "history_count": len(_alarm_history),
        "suppressed_count": len(_suppressed_codes),
        "by_severity": by_severity,
        "by_equipment": by_equipment,
        "by_status": by_status,
        "mtta_seconds": mtta,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/definitions", response_model=List[Dict[str, Any]])
async def list_alarm_definitions(
    equipment_type: Optional[str] = Query(None, description="Filter by equipment type"),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List alarm definitions.

    Args:
        equipment_type: Optional filter by equipment type.
        user: Current authenticated user (optional).

    Returns:
        List of alarm definition dictionaries.
    """
    definitions = list(_alarm_definitions.values())
    if equipment_type:
        definitions = [d for d in definitions if d.equipment_type == equipment_type]
    return [d.to_dict() for d in definitions]


@router.post("/definitions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_alarm_definition(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Register a new alarm definition.

    Args:
        data: Alarm definition data.
        user: Current authenticated user (engineer+).

    Returns:
        Created alarm definition dictionary.
    """
    try:
        definition = AlarmDefinition(**data)
        _alarm_definitions[definition.alarm_code] = definition
        logger.info("alarm_definition_created", alarm_code=definition.alarm_code)
        return definition.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{alarm_id}", response_model=Dict[str, Any])
async def get_alarm(
    alarm_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get alarm by ID.

    Args:
        alarm_id: Alarm unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Alarm dictionary.

    Raises:
        HTTPException: 404 if alarm not found.
    """
    alarm = _active_alarms.get(alarm_id)
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alarm not found: {alarm_id}",
        )
    return alarm.to_dict()


@router.post("/raise", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def raise_alarm(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Raise a new alarm.

    Args:
        data: Alarm data with equipment_id, alarm_code, severity, etc.
        user: Current authenticated user (operator+).

    Returns:
        Created alarm dictionary.
    """
    import uuid as uuid_lib

    alarm_code = data.get("alarm_code", "UNKNOWN")
    equipment_id = data.get("equipment_id", "")
    if not equipment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="equipment_id is required",
        )

    # Check suppression
    if alarm_code in _suppressed_codes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alarm code '{alarm_code}' is currently suppressed",
        )

    # Get definition
    definition = _alarm_definitions.get(alarm_code)

    alarm = Alarm(
        id=str(uuid_lib.uuid4()),
        equipment_id=equipment_id,
        alarm_code=alarm_code,
        alarm_text=data.get("alarm_text", definition.default_text if definition else alarm_code),
        severity=AlarmSeverity(data.get("severity", "warning")),
        raised_at=datetime.now(timezone.utc),
        parameters=data.get("parameters"),
    )

    _active_alarms[alarm.id] = alarm

    logger.info(
        "alarm_raised",
        alarm_id=alarm.id,
        equipment_id=equipment_id,
        alarm_code=alarm_code,
        severity=alarm.severity.value,
    )

    return alarm.to_dict()


@router.post("/{alarm_id}/acknowledge", response_model=Dict[str, Any])
async def acknowledge_alarm(
    alarm_id: str,
    acknowledged_by: str = Query(..., description="Username of acknowledger"),
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Acknowledge an alarm.

    Args:
        alarm_id: Alarm unique identifier.
        acknowledged_by: Username of the person acknowledging.
        user: Current authenticated user (operator+).

    Returns:
        Updated alarm dictionary.

    Raises:
        HTTPException: 404 if alarm not found.
    """
    alarm = _active_alarms.get(alarm_id)
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alarm not found: {alarm_id}",
        )

    if alarm.is_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alarm already acknowledged",
        )

    alarm.status = AlarmStatus.ACKNOWLEDGED
    alarm.acknowledged_by = acknowledged_by
    alarm.acknowledged_at = datetime.now(timezone.utc)

    logger.info("alarm_acknowledged", alarm_id=alarm_id, by=acknowledged_by)
    return alarm.to_dict()


@router.post("/{alarm_id}/clear", response_model=Dict[str, Any])
async def clear_alarm(
    alarm_id: str,
    cleared_by: str = Query(..., description="Username of clearer"),
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Clear an alarm.

    Args:
        alarm_id: Alarm unique identifier.
        cleared_by: Username of the person clearing.
        user: Current authenticated user (operator+).

    Returns:
        Updated alarm dictionary.

    Raises:
        HTTPException: 404 if alarm not found.
    """
    alarm = _active_alarms.get(alarm_id)
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alarm not found: {alarm_id}",
        )

    if alarm.is_cleared:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alarm already cleared",
        )

    alarm.status = AlarmStatus.CLEARED
    alarm.cleared_by = cleared_by
    alarm.cleared_at = datetime.now(timezone.utc)

    # Move to history and remove from active
    _alarm_history.append(alarm)
    del _active_alarms[alarm_id]

    logger.info("alarm_cleared", alarm_id=alarm_id, by=cleared_by)
    return alarm.to_dict()


@router.post("/suppress", response_model=Dict[str, Any])
async def suppress_alarm(
    alarm_code: str = Query(..., description="Alarm code to suppress"),
    duration_seconds: Optional[int] = Query(None, ge=1, description="Suppression duration"),
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Suppress an alarm code.

    Args:
        alarm_code: Alarm code to suppress.
        duration_seconds: Optional duration in seconds.
        user: Current authenticated user (engineer+).

    Returns:
        Suppression result dictionary.
    """
    _suppressed_codes.add(alarm_code)

    result = {
        "alarm_code": alarm_code,
        "suppressed": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if duration_seconds:
        result["duration_seconds"] = duration_seconds

    logger.info("alarm_suppressed", alarm_code=alarm_code, duration=duration_seconds)
    return result


@router.delete("/suppress", response_model=Dict[str, Any])
async def unsuppress_alarm(
    alarm_code: str = Query(..., description="Alarm code to unsuppress"),
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Remove alarm suppression.

    Args:
        alarm_code: Alarm code to unsuppress.
        user: Current authenticated user (engineer+).

    Returns:
        Unsuppression result dictionary.
    """
    existed = alarm_code in _suppressed_codes
    _suppressed_codes.discard(alarm_code)

    logger.info("alarm_unsuppressed", alarm_code=alarm_code)
    return {
        "alarm_code": alarm_code,
        "suppressed": False,
        "was_suppressed": existed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
