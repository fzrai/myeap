"""FDC (Fault Detection and Classification) API routes.

Provides endpoints for fault detection, classification,
and fault lifecycle management.
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
from myeap.fdc.models import (
    Fault,
    FaultCategory,
    FaultSeverity,
    FaultStatus,
    FaultType,
)

logger = get_logger(__name__)

router = APIRouter()

# In-memory FDC stores
_faults: Dict[str, Fault] = {}
_fault_history: List[Fault] = []


def _fault_to_dict(fault: Fault) -> Dict[str, Any]:
    """Convert Fault to API response dict."""
    return fault.to_dict()


@router.get("/faults", response_model=List[Dict[str, Any]])
async def list_faults(
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    fault_type: Optional[str] = Query(None, description="Filter by fault type"),
    category: Optional[str] = Query(None, description="Filter by fault category"),
    include_resolved: bool = Query(False, description="Include resolved faults"),
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List faults with optional filtering.

    Args:
        equipment_id: Optional filter by equipment ID.
        severity: Optional filter by severity.
        fault_type: Optional filter by fault type.
        category: Optional filter by fault category.
        include_resolved: Whether to include resolved/dismissed faults.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of fault dictionaries.
    """
    if include_resolved:
        all_faults = list(_faults.values()) + list(_fault_history)
    else:
        all_faults = list(_faults.values())

    if equipment_id:
        all_faults = [f for f in all_faults if f.equipment_id == equipment_id]
    if severity:
        all_faults = [f for f in all_faults if f.severity.value == severity]
    if fault_type:
        all_faults = [f for f in all_faults if f.fault_type.value == fault_type]
    if category:
        all_faults = [f for f in all_faults if f.category.value == category]

    # Sort by severity priority then start time
    all_faults.sort(
        key=lambda f: (f.severity.priority, f.start_time if f.start_time else datetime.min)
    )

    total = len(all_faults)
    items = all_faults[pagination.offset : pagination.offset + pagination.limit]

    result = []
    for fault in items:
        d = fault.to_dict()
        d["_total"] = total
        result.append(d)

    return result


@router.get("/faults/stats", response_model=Dict[str, Any])
async def get_fault_statistics(
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get fault statistics.

    Args:
        equipment_id: Optional filter by equipment ID.
        user: Current authenticated user (optional).

    Returns:
        Fault statistics dictionary.
    """
    active_faults = list(_faults.values())
    if equipment_id:
        active_faults = [f for f in active_faults if f.equipment_id == equipment_id]

    by_severity: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    by_equipment: Dict[str, int] = {}
    by_status: Dict[str, int] = {}

    for fault in active_faults:
        sev = fault.severity.value
        by_severity[sev] = by_severity.get(sev, 0) + 1

        cat = fault.category.value
        by_category[cat] = by_category.get(cat, 0) + 1

        ft = fault.fault_type.value
        by_type[ft] = by_type.get(ft, 0) + 1

        eq = fault.equipment_id
        by_equipment[eq] = by_equipment.get(eq, 0) + 1

        st = fault.status.value
        by_status[st] = by_status.get(st, 0) + 1

    # Average fault duration
    durations = [f.duration for f in active_faults if f.duration is not None]
    avg_duration = round(sum(durations) / len(durations), 2) if durations else None

    return {
        "total_count": len(active_faults) + len(_fault_history),
        "active_count": len(active_faults),
        "history_count": len(_fault_history),
        "by_severity": by_severity,
        "by_category": by_category,
        "by_type": by_type,
        "by_equipment": by_equipment,
        "by_status": by_status,
        "avg_duration_seconds": avg_duration,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/faults/{fault_id}", response_model=Dict[str, Any])
async def get_fault(
    fault_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get fault by ID.

    Args:
        fault_id: Fault unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Fault dictionary.

    Raises:
        HTTPException: 404 if fault not found.
    """
    fault = _faults.get(fault_id)
    if not fault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fault not found: {fault_id}",
        )
    return fault.to_dict()


@router.post("/detect", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def detect_fault(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Report a new fault detection.

    Args:
        data: Fault detection data including equipment_id, fault_type, etc.
        user: Current authenticated user (operator+).

    Returns:
        Created fault dictionary.
    """
    import uuid as uuid_lib

    equipment_id = data.get("equipment_id", "")
    if not equipment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="equipment_id is required",
        )

    fault_type_str = data.get("fault_type", "unknown")
    severity_str = data.get("severity", "warning")

    try:
        fault_type = FaultType(fault_type_str)
    except ValueError:
        fault_type = FaultType.UNKNOWN

    try:
        severity = FaultSeverity(severity_str)
    except ValueError:
        severity = FaultSeverity.WARNING

    fault = Fault(
        fault_id=str(uuid_lib.uuid4()),
        fault_type=fault_type,
        severity=severity,
        equipment_id=equipment_id,
        chamber_id=data.get("chamber_id"),
        start_time=datetime.now(timezone.utc),
        status=FaultStatus.DETECTED,
        affected_parameters=data.get("affected_parameters", []),
        feature_vector=data.get("feature_vector"),
        root_cause=data.get("root_cause"),
        confidence=data.get("confidence", 0.0),
        recommendations=data.get("recommendations", []),
        metadata=data.get("metadata", {}),
    )

    _faults[fault.fault_id] = fault

    logger.info(
        "fault_detected",
        fault_id=fault.fault_id,
        fault_type=fault_type.value,
        severity=severity.value,
        equipment_id=equipment_id,
    )

    return fault.to_dict()


@router.post("/faults/{fault_id}/analyze", response_model=Dict[str, Any])
async def analyze_fault(
    fault_id: str,
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Analyze a fault (set root cause, recommendations, etc.).

    Args:
        fault_id: Fault unique identifier.
        user: Current authenticated user (engineer+).

    Returns:
        Analysis result dictionary.

    Raises:
        HTTPException: 404 if fault not found.
    """
    fault = _faults.get(fault_id)
    if not fault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fault not found: {fault_id}",
        )

    fault.status = FaultStatus.ANALYZING

    return {
        "fault_id": fault_id,
        "status": fault.status.value,
        "fault_type": fault.fault_type.value,
        "category": fault.category.value,
        "severity": fault.severity.value,
        "affected_parameters": fault.affected_parameters,
        "duration_seconds": fault.duration,
        "analysis_started_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/faults/{fault_id}/confirm", response_model=Dict[str, Any])
async def confirm_fault(
    fault_id: str,
    data: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Confirm a fault.

    Args:
        fault_id: Fault unique identifier.
        data: Optional confirmation data with root_cause and recommendations.
        user: Current authenticated user (engineer+).

    Returns:
        Confirmed fault dictionary.

    Raises:
        HTTPException: 404 if fault not found.
    """
    fault = _faults.get(fault_id)
    if not fault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fault not found: {fault_id}",
        )

    fault.status = FaultStatus.CONFIRMED
    if data:
        if "root_cause" in data:
            fault.root_cause = data["root_cause"]
        if "confidence" in data:
            fault.confidence = data["confidence"]
        if "recommendations" in data:
            fault.recommendations = data["recommendations"]

    logger.info("fault_confirmed", fault_id=fault_id, root_cause=fault.root_cause)
    return fault.to_dict()


@router.post("/faults/{fault_id}/resolve", response_model=Dict[str, Any])
async def resolve_fault(
    fault_id: str,
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Resolve a fault.

    Args:
        fault_id: Fault unique identifier.
        user: Current authenticated user (engineer+).

    Returns:
        Resolved fault dictionary.

    Raises:
        HTTPException: 404 if fault not found.
    """
    fault = _faults.get(fault_id)
    if not fault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fault not found: {fault_id}",
        )

    fault.resolve()

    # Move to history
    _fault_history.append(fault)
    del _faults[fault_id]

    logger.info("fault_resolved", fault_id=fault_id)
    return fault.to_dict()


@router.post("/faults/{fault_id}/dismiss", response_model=Dict[str, Any])
async def dismiss_fault(
    fault_id: str,
    reason: str = Query("No reason provided", description="Dismiss reason"),
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Dismiss a fault.

    Args:
        fault_id: Fault unique identifier.
        reason: Reason for dismissal.
        user: Current authenticated user (engineer+).

    Returns:
        Dismissed fault dictionary.

    Raises:
        HTTPException: 404 if fault not found.
    """
    fault = _faults.get(fault_id)
    if not fault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fault not found: {fault_id}",
        )

    fault.dismiss(reason)

    # Move to history
    _fault_history.append(fault)
    del _faults[fault_id]

    logger.info("fault_dismissed", fault_id=fault_id, reason=reason)
    return fault.to_dict()


@router.get("/fault-types", response_model=List[Dict[str, Any]])
async def list_fault_types(
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List all supported fault types.

    Returns:
        List of fault type descriptions.
    """
    return [
        {
            "value": ft.value,
            "category": FaultCategory.from_fault_type(ft).value,
        }
        for ft in FaultType
    ]


@router.get("/severities", response_model=List[Dict[str, Any]])
async def list_fault_severities(
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List all fault severity levels.

    Returns:
        List of severity level descriptions.
    """
    return [
        {"value": fs.value, "priority": fs.priority}
        for fs in FaultSeverity
    ]
