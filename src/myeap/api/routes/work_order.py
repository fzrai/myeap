"""Work Order API routes.

Provides CRUD and workflow management endpoints for work orders.
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
from myeap.mes.models import WorkOrderMessage

logger = get_logger(__name__)

router = APIRouter()

# In-memory work order store
_work_orders: Dict[str, Dict[str, Any]] = {}


def _wo_to_dict(wo: Dict[str, Any]) -> Dict[str, Any]:
    """Standardize work order dict for API response."""
    return {
        "mes_id": wo.get("mes_id", ""),
        "lot_id": wo.get("lot_id", ""),
        "recipe_name": wo.get("recipe_name", ""),
        "wafer_count": wo.get("wafer_count", 0),
        "priority": wo.get("priority", 5),
        "equipment_id": wo.get("equipment_id"),
        "carrier_id": wo.get("carrier_id"),
        "slot_map": wo.get("slot_map"),
        "status": wo.get("status", "PENDING"),
        "progress": wo.get("progress", 0),
        "good_count": wo.get("good_count", 0),
        "reject_count": wo.get("reject_count", 0),
        "created_at": wo.get("created_at", datetime.now(timezone.utc).isoformat()),
        "started_at": wo.get("started_at"),
        "completed_at": wo.get("completed_at"),
        "metadata": wo.get("metadata", {}),
    }


@router.get("/", response_model=List[Dict[str, Any]])
async def list_work_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    lot_id: Optional[str] = Query(None, description="Filter by lot ID"),
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    mes_id: Optional[str] = Query(None, description="Filter by MES ID"),
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List work orders with optional filtering.

    Args:
        status: Optional filter by status.
        lot_id: Optional filter by lot ID.
        equipment_id: Optional filter by equipment ID.
        mes_id: Optional filter by MES ID.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of work order dictionaries.
    """
    all_wo = list(_work_orders.values())

    if status:
        all_wo = [w for w in all_wo if w.get("status") == status]
    if lot_id:
        all_wo = [w for w in all_wo if w.get("lot_id") == lot_id]
    if equipment_id:
        all_wo = [w for w in all_wo if w.get("equipment_id") == equipment_id]
    if mes_id:
        all_wo = [w for w in all_wo if w.get("mes_id") == mes_id]

    # Sort by priority then created_at (newest first)
    all_wo.sort(
        key=lambda w: (w.get("priority", 5), w.get("created_at", "")),
        reverse=False,
    )

    total = len(all_wo)
    items = all_wo[pagination.offset : pagination.offset + pagination.limit]

    result = []
    for wo in items:
        d = _wo_to_dict(wo)
        d["_total"] = total
        result.append(d)

    return result


@router.get("/{mes_id}", response_model=Dict[str, Any])
async def get_work_order(
    mes_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get work order by MES ID.

    Args:
        mes_id: MES work order ID.
        user: Current authenticated user (optional).

    Returns:
        Work order dictionary.

    Raises:
        HTTPException: 404 if work order not found.
    """
    wo = _work_orders.get(mes_id)
    if not wo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order not found: {mes_id}",
        )
    return _wo_to_dict(wo)


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_work_order(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Create a new work order.

    Args:
        data: Work order creation data.
        user: Current authenticated user (engineer+).

    Returns:
        Created work order dictionary.

    Raises:
        HTTPException: 400 if validation fails or 409 if MES ID exists.
    """
    mes_id = data.get("mes_id")
    if not mes_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mes_id is required",
        )

    if mes_id in _work_orders:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Work order already exists: {mes_id}",
        )

    wo = {
        "mes_id": mes_id,
        "lot_id": data.get("lot_id", ""),
        "recipe_name": data.get("recipe_name", ""),
        "wafer_count": data.get("wafer_count", 0),
        "priority": data.get("priority", 5),
        "equipment_id": data.get("equipment_id"),
        "carrier_id": data.get("carrier_id"),
        "slot_map": data.get("slot_map"),
        "status": "PENDING",
        "progress": 0,
        "good_count": 0,
        "reject_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "metadata": data.get("metadata", {}),
    }

    _work_orders[mes_id] = wo

    logger.info("work_order_created", mes_id=mes_id, lot_id=wo["lot_id"])
    return _wo_to_dict(wo)


@router.put("/{mes_id}", response_model=Dict[str, Any])
async def update_work_order(
    mes_id: str,
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Update a work order.

    Args:
        mes_id: MES work order ID.
        data: Work order update data.
        user: Current authenticated user (engineer+).

    Returns:
        Updated work order dictionary.

    Raises:
        HTTPException: 404 if work order not found.
    """
    if mes_id not in _work_orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order not found: {mes_id}",
        )

    wo = _work_orders[mes_id]
    updatable = [
        "lot_id", "recipe_name", "wafer_count", "priority",
        "equipment_id", "carrier_id", "slot_map", "status",
        "progress", "good_count", "reject_count", "metadata",
    ]

    for key in updatable:
        if key in data:
            wo[key] = data[key]

    logger.info("work_order_updated", mes_id=mes_id)
    return _wo_to_dict(wo)


@router.patch("/{mes_id}", response_model=Dict[str, Any])
async def patch_work_order(
    mes_id: str,
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Partially update a work order.

    Args:
        mes_id: MES work order ID.
        data: Partial work order data.
        user: Current authenticated user (operator+).

    Returns:
        Updated work order dictionary.

    Raises:
        HTTPException: 404 if work order not found.
    """
    if mes_id not in _work_orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order not found: {mes_id}",
        )

    wo = _work_orders[mes_id]
    updatable = [
        "lot_id", "recipe_name", "wafer_count", "priority",
        "equipment_id", "carrier_id", "slot_map", "status",
        "progress", "good_count", "reject_count", "metadata",
    ]

    for key in updatable:
        if key in data:
            wo[key] = data[key]

    logger.info("work_order_patched", mes_id=mes_id)
    return _wo_to_dict(wo)


@router.delete("/{mes_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_order(
    mes_id: str,
    user: Dict[str, Any] = Depends(require_role("admin")),
) -> None:
    """Delete a work order.

    Args:
        mes_id: MES work order ID.
        user: Current authenticated user (admin only).

    Raises:
        HTTPException: 404 if work order not found.
    """
    if mes_id not in _work_orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order not found: {mes_id}",
        )

    del _work_orders[mes_id]
    logger.info("work_order_deleted", mes_id=mes_id)


@router.post("/{mes_id}/start", response_model=Dict[str, Any])
async def start_work_order(
    mes_id: str,
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Start a work order.

    Args:
        mes_id: MES work order ID.
        user: Current authenticated user (operator+).

    Returns:
        Updated work order dictionary.

    Raises:
        HTTPException: 404 if work order not found, 400 if not in PENDING status.
    """
    if mes_id not in _work_orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order not found: {mes_id}",
        )

    wo = _work_orders[mes_id]
    if wo["status"] not in ("PENDING", "QUEUED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start work order. Status: {wo['status']}",
        )

    wo["status"] = "RUNNING"
    wo["started_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("work_order_started", mes_id=mes_id)
    return _wo_to_dict(wo)


@router.post("/{mes_id}/complete", response_model=Dict[str, Any])
async def complete_work_order(
    mes_id: str,
    good_count: int = Query(0, ge=0, description="Good wafer count"),
    reject_count: int = Query(0, ge=0, description="Reject wafer count"),
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Complete a work order.

    Args:
        mes_id: MES work order ID.
        good_count: Number of good wafers.
        reject_count: Number of rejected wafers.
        user: Current authenticated user (operator+).

    Returns:
        Updated work order dictionary.

    Raises:
        HTTPException: 404 if work order not found, 400 if not running.
    """
    if mes_id not in _work_orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order not found: {mes_id}",
        )

    wo = _work_orders[mes_id]
    if wo["status"] != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete work order. Status: {wo['status']}",
        )

    wo["status"] = "COMPLETED"
    wo["completed_at"] = datetime.now(timezone.utc).isoformat()
    wo["progress"] = 100
    wo["good_count"] = good_count
    wo["reject_count"] = reject_count

    # Calculate yield
    total = good_count + reject_count
    if total > 0:
        wo["yield_rate"] = round(good_count / total * 100, 2)

    logger.info("work_order_completed", mes_id=mes_id)
    return _wo_to_dict(wo)


@router.post("/{mes_id}/abort", response_model=Dict[str, Any])
async def abort_work_order(
    mes_id: str,
    reason: str = Query("Unknown", description="Abort reason"),
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Abort a work order.

    Args:
        mes_id: MES work order ID.
        reason: Reason for aborting.
        user: Current authenticated user (operator+).

    Returns:
        Updated work order dictionary.

    Raises:
        HTTPException: 404 if work order not found.
    """
    if mes_id not in _work_orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order not found: {mes_id}",
        )

    wo = _work_orders[mes_id]
    wo["status"] = "ABORTED"
    wo["completed_at"] = datetime.now(timezone.utc).isoformat()
    wo["abort_reason"] = reason

    logger.info("work_order_aborted", mes_id=mes_id, reason=reason)
    return _wo_to_dict(wo)


@router.get("/{mes_id}/progress", response_model=Dict[str, Any])
async def get_work_order_progress(
    mes_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get work order progress details.

    Args:
        mes_id: MES work order ID.
        user: Current authenticated user (optional).

    Returns:
        Work order progress dictionary.

    Raises:
        HTTPException: 404 if work order not found.
    """
    if mes_id not in _work_orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order not found: {mes_id}",
        )

    wo = _work_orders[mes_id]
    return {
        "mes_id": mes_id,
        "status": wo.get("status"),
        "progress": wo.get("progress", 0),
        "wafer_count": wo.get("wafer_count", 0),
        "good_count": wo.get("good_count", 0),
        "reject_count": wo.get("reject_count", 0),
        "yield_rate": wo.get("yield_rate"),
        "started_at": wo.get("started_at"),
        "estimated_completion": None,
    }


@router.get("/lot/{lot_id}", response_model=List[Dict[str, Any]])
async def get_work_orders_by_lot(
    lot_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """Get all work orders for a specific lot.

    Args:
        lot_id: Lot ID.
        user: Current authenticated user (optional).

    Returns:
        List of work order dictionaries for the lot.
    """
    lot_orders = [
        _wo_to_dict(wo)
        for wo in _work_orders.values()
        if wo.get("lot_id") == lot_id
    ]
    lot_orders.sort(key=lambda w: w.get("created_at", ""))
    return lot_orders
