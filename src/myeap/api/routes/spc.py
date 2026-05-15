"""SPC (Statistical Process Control) API routes.

Provides endpoints for control chart management, data analysis,
and process capability calculations.
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
from myeap.spc.models import (
    ChartType,
    ChartStatistics,
    ControlLimits,
    DataPoint,
    ChartPoint,
)

logger = get_logger(__name__)

router = APIRouter()

# In-memory SPC stores
_charts: Dict[str, Dict[str, Any]] = {}
_data_points: Dict[str, List[DataPoint]] = {}


@router.get("/charts", response_model=List[Dict[str, Any]])
async def list_charts(
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    chart_type: Optional[str] = Query(None, description="Filter by chart type"),
    pagination: Pagination = Depends(),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List all control charts with optional filtering.

    Args:
        equipment_id: Optional filter by equipment ID.
        chart_type: Optional filter by chart type.
        pagination: Pagination parameters.
        user: Current authenticated user (optional).

    Returns:
        List of chart dictionaries.
    """
    all_charts = list(_charts.values())

    if equipment_id:
        all_charts = [c for c in all_charts if c.get("equipment_id") == equipment_id]
    if chart_type:
        all_charts = [c for c in all_charts if c.get("chart_type") == chart_type]

    total = len(all_charts)
    items = all_charts[pagination.offset : pagination.offset + pagination.limit]

    result = []
    for item in items:
        d = dict(item)
        d["_total"] = total
        result.append(d)

    return result


@router.post("/charts", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_chart(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Create a new control chart.

    Args:
        data: Chart creation data with chart_id, chart_type, parameter, limits, etc.
        user: Current authenticated user (engineer+).

    Returns:
        Created chart dictionary.
    """
    import uuid as uuid_lib

    chart_id = data.get("chart_id", str(uuid_lib.uuid4()))

    if chart_id in _charts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chart already exists: {chart_id}",
        )

    chart_type = data.get("chart_type", "x_mr")
    limits = data.get("limits", {})

    chart = {
        "chart_id": chart_id,
        "chart_type": chart_type,
        "parameter_name": data.get("parameter_name", ""),
        "equipment_id": data.get("equipment_id"),
        "equipment_type": data.get("equipment_type"),
        "limits": limits,
        "sample_size": data.get("sample_size", 1),
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "data_point_count": 0,
    }

    _charts[chart_id] = chart
    _data_points[chart_id] = []

    logger.info("spc_chart_created", chart_id=chart_id, chart_type=chart_type)
    return chart


@router.get("/charts/{chart_id}", response_model=Dict[str, Any])
async def get_chart(
    chart_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get chart by ID.

    Args:
        chart_id: Chart unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Chart dictionary.

    Raises:
        HTTPException: 404 if chart not found.
    """
    chart = _charts.get(chart_id)
    if not chart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart not found: {chart_id}",
        )
    return chart


@router.put("/charts/{chart_id}", response_model=Dict[str, Any])
async def update_chart(
    chart_id: str,
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Update a control chart.

    Args:
        chart_id: Chart unique identifier.
        data: Chart update data.
        user: Current authenticated user (engineer+).

    Returns:
        Updated chart dictionary.

    Raises:
        HTTPException: 404 if chart not found.
    """
    chart = _charts.get(chart_id)
    if not chart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart not found: {chart_id}",
        )

    updatable = [
        "chart_type", "parameter_name", "equipment_id",
        "equipment_type", "limits", "sample_size", "enabled",
    ]

    for key in updatable:
        if key in data:
            chart[key] = data[key]

    chart["updated_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("spc_chart_updated", chart_id=chart_id)
    return chart


@router.delete("/charts/{chart_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chart(
    chart_id: str,
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> None:
    """Delete a control chart and its data.

    Args:
        chart_id: Chart unique identifier.
        user: Current authenticated user (engineer+).

    Raises:
        HTTPException: 404 if chart not found.
    """
    if chart_id not in _charts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart not found: {chart_id}",
        )

    del _charts[chart_id]
    _data_points.pop(chart_id, None)

    logger.info("spc_chart_deleted", chart_id=chart_id)


@router.post("/charts/{chart_id}/data", response_model=Dict[str, Any])
async def add_data_point(
    chart_id: str,
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role("operator")),
) -> Dict[str, Any]:
    """Add a data point to a control chart.

    Args:
        chart_id: Chart unique identifier.
        data: Data point with value, timestamp, etc.
        user: Current authenticated user (operator+).

    Returns:
        Analysis result with any SPC violations detected.

    Raises:
        HTTPException: 404 if chart not found, 400 if value missing.
    """
    chart = _charts.get(chart_id)
    if not chart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart not found: {chart_id}",
        )

    value = data.get("value")
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="value is required",
        )

    timestamp = data.get("timestamp")
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp)
        except ValueError:
            timestamp = datetime.now(timezone.utc)
    elif timestamp is None:
        timestamp = datetime.now(timezone.utc)

    dp = DataPoint(
        value=float(value),
        timestamp=timestamp,
        group_id=data.get("group_id"),
        quality=data.get("quality", "normal"),
    )

    points = _data_points.setdefault(chart_id, [])
    points.append(dp)
    chart["data_point_count"] = len(points)

    # Check against limits
    limits = chart.get("limits", {})
    violations = []

    if limits:
        ucl = limits.get("ucl")
        lcl = limits.get("lcl")
        if ucl is not None and value > ucl:
            violations.append({"rule": "UCL_EXCEEDED", "value": value, "ucl": ucl})
        if lcl is not None and value < lcl:
            violations.append({"rule": "LCL_EXCEEDED", "value": value, "lcl": lcl})

    result = {
        "chart_id": chart_id,
        "data_point": dp.to_dict(),
        "data_point_count": len(points),
        "violations": violations,
        "is_out_of_control": len(violations) > 0,
    }

    if violations:
        logger.warning("spc_violation", chart_id=chart_id, violations=violations)

    return result


@router.get("/charts/{chart_id}/data", response_model=List[Dict[str, Any]])
async def get_chart_data(
    chart_id: str,
    limit: int = Query(100, ge=1, le=10000, description="Max data points to return"),
    offset: int = Query(0, ge=0, description="Number of points to skip"),
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """Get data points for a chart.

    Args:
        chart_id: Chart unique identifier.
        limit: Maximum number of data points.
        offset: Offset for pagination.
        user: Current authenticated user (optional).

    Returns:
        List of data point dictionaries.

    Raises:
        HTTPException: 404 if chart not found.
    """
    if chart_id not in _charts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart not found: {chart_id}",
        )

    points = _data_points.get(chart_id, [])
    return [p.to_dict() for p in points[offset : offset + limit]]


@router.get("/charts/{chart_id}/statistics", response_model=Dict[str, Any])
async def get_chart_statistics(
    chart_id: str,
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get statistics for a control chart.

    Args:
        chart_id: Chart unique identifier.
        user: Current authenticated user (optional).

    Returns:
        Chart statistics dictionary.

    Raises:
        HTTPException: 404 if chart not found.
    """
    chart = _charts.get(chart_id)
    if not chart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart not found: {chart_id}",
        )

    points = _data_points.get(chart_id, [])
    if not points:
        return {
            "chart_id": chart_id,
            "data_point_count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
            "range": None,
            "violation_count": 0,
        }

    values = [p.value for p in points]
    n = len(values)
    mean_val = sum(values) / n
    variance = sum((v - mean_val) ** 2 for v in values) / (n - 1) if n > 1 else 0
    std_val = variance ** 0.5
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val

    # Median
    sorted_values = sorted(values)
    if n % 2 == 0:
        median = (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
    else:
        median = sorted_values[n // 2]

    return {
        "chart_id": chart_id,
        "data_point_count": n,
        "mean": round(mean_val, 4),
        "std": round(std_val, 4),
        "min": round(min_val, 4),
        "max": round(max_val, 4),
        "range": round(range_val, 4),
        "median": round(median, 4),
        "violation_count": 0,  # Could be calculated from violations
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/charts/{chart_id}/reset", response_model=Dict[str, Any])
async def reset_chart_data(
    chart_id: str,
    user: Dict[str, Any] = Depends(require_role("engineer")),
) -> Dict[str, Any]:
    """Reset all data points for a control chart.

    Args:
        chart_id: Chart unique identifier.
        user: Current authenticated user (engineer+).

    Returns:
        Chart with reset confirmation.

    Raises:
        HTTPException: 404 if chart not found.
    """
    chart = _charts.get(chart_id)
    if not chart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart not found: {chart_id}",
        )

    old_count = len(_data_points.get(chart_id, []))
    _data_points[chart_id] = []
    chart["data_point_count"] = 0

    logger.info("spc_chart_reset", chart_id=chart_id, previous_count=old_count)
    return {
        "chart_id": chart_id,
        "reset": True,
        "previous_data_count": old_count,
        "message": "Chart data reset successfully",
    }


@router.get("/chart-types", response_model=List[Dict[str, Any]])
async def list_chart_types(
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List all supported SPC chart types.

    Returns:
        List of chart type descriptions.
    """
    return [
        {"value": ct.value, "description": ct.description,
         "is_variable_chart": ct.is_variable_chart,
         "is_attribute_chart": ct.is_attribute_chart,
         "requires_group_size": ct.requires_group_size,
         "default_group_size": ct.default_group_size}
        for ct in ChartType
    ]


@router.get("/rules", response_model=List[Dict[str, Any]])
async def list_spc_rules(
    user: Dict[str, Any] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """List all SPC violation rules (Western Electric rules).

    Returns:
        List of SPC rule descriptions.
    """
    from myeap.spc.rules import get_default_rules

    rules = get_default_rules()
    return [
        {
            "rule_id": rule.value,
            "name": rule.name,
            "description": rule.description,
            "minimum_points": rule.minimum_points,
        }
        for rule in rules
    ]
