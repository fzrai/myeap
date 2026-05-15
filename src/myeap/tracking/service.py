"""追溯服务模块

提供全面的追溯能力，包括正向追踪、反向追溯和影响分析。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from myeap.tracking.carrier import CarrierManager
from myeap.tracking.models import (
    Carrier,
    Wafer,
    WaferEvent,
    WaferStatus,
)
from myeap.tracking.wafer import WaferTracker


class TraceabilityService:
    """追溯服务

    提供全面的追溯能力：
    - 正向追踪：从原料到成品
    - 反向追溯：从成品到原料
    - 影响分析

    Attributes:
        tracker: 晶圆追踪器
        carrier_manager: 载具管理器
    """

    def __init__(
        self,
        tracker: WaferTracker,
        carrier_manager: CarrierManager,
    ):
        """初始化追溯服务

        Args:
            tracker: 晶圆追踪器实例
            carrier_manager: 载具管理器实例
        """
        self.tracker = tracker
        self.carriers = carrier_manager

    async def trace_forward(
        self,
        lot_id: str,
    ) -> Dict[str, Any]:
        """正向追踪

        从批次开始，追踪所有晶圆的完整处理路径。

        Args:
            lot_id: 批次ID

        Returns:
            追踪结果，包含时间线和各晶圆的详细路径
        """
        events = await self.tracker.trace_lot(lot_id)

        # 构建追踪树
        trace: Dict[str, Any] = {
            "lot_id": lot_id,
            "wafers": {},
            "timeline": [],
            "equipment_visits": {},
            "recipe_usage": {},
        }

        for event in sorted(events, key=lambda e: e.timestamp):
            # 添加到时间线
            trace["timeline"].append({
                "time": event.timestamp.isoformat(),
                "event": event.event_type,
                "wafer_id": event.wafer_id,
                "equipment": event.equipment_id,
                "recipe": event.recipe_name,
            })

            # 按晶圆分组
            if event.wafer_id not in trace["wafers"]:
                trace["wafers"][event.wafer_id] = []
            trace["wafers"][event.wafer_id].append({
                "event": event.event_type,
                "time": event.timestamp.isoformat(),
                "location": event.equipment_id,
                "chamber": event.chamber_id,
                "recipe": event.recipe_name,
                "duration": event.duration_seconds,
            })

            # 统计设备访问
            if event.equipment_id:
                if event.equipment_id not in trace["equipment_visits"]:
                    trace["equipment_visits"][event.equipment_id] = []
                trace["equipment_visits"][event.equipment_id].append({
                    "wafer_id": event.wafer_id,
                    "event": event.event_type,
                    "time": event.timestamp.isoformat(),
                })

            # 统计配方使用
            if event.recipe_name:
                if event.recipe_name not in trace["recipe_usage"]:
                    trace["recipe_usage"][event.recipe_name] = []
                trace["recipe_usage"][event.recipe_name].append({
                    "wafer_id": event.wafer_id,
                    "equipment": event.equipment_id,
                    "time": event.timestamp.isoformat(),
                })

        # 添加统计信息
        trace["summary"] = {
            "total_events": len(events),
            "total_wafers": len(trace["wafers"]),
            "equipment_count": len(trace["equipment_visits"]),
            "recipe_count": len(trace["recipe_usage"]),
        }

        return trace

    async def trace_backward(
        self,
        wafer_id: str,
    ) -> Dict[str, Any]:
        """反向追溯

        从单个晶圆回溯其完整的处理历史。

        Args:
            wafer_id: 晶圆ID

        Returns:
            追溯结果，包含晶圆的完整历史
        """
        wafer = await self.tracker.get_wafer(wafer_id)

        if not wafer:
            return {
                "wafer_id": wafer_id,
                "error": "Wafer not found",
            }

        trace: Dict[str, Any] = {
            "wafer_id": wafer_id,
            "lot_id": wafer.lot_id,
            "current_location": wafer.current_location,
            "current_status": wafer.status.value,
            "history": [],
            "equipment_path": [],
            "recipes_used": [],
        }

        # 从最新到最早排序
        for event in reversed(wafer.history):
            entry = {
                "time": event.timestamp.isoformat(),
                "event": event.event_type,
                "equipment": event.equipment_id,
                "chamber": event.chamber_id,
                "recipe": event.recipe_name,
                "result": event.result,
            }
            trace["history"].append(entry)

            # 记录设备路径
            if event.equipment_id and event.equipment_id not in trace["equipment_path"]:
                trace["equipment_path"].append(event.equipment_id)

            # 记录使用的配方
            if event.recipe_name and event.recipe_name not in trace["recipes_used"]:
                trace["recipes_used"].append(event.recipe_name)

        # 添加统计信息
        trace["summary"] = {
            "total_events": len(wafer.history),
            "equipment_count": len(trace["equipment_path"]),
            "recipe_count": len(trace["recipes_used"]),
        }

        return trace

    async def trace_by_lot(
        self,
        lot_id: str,
    ) -> Dict[str, Any]:
        """按批次追溯

        获取批次的完整追溯信息。

        Args:
            lot_id: 批次ID

        Returns:
            批次追溯结果
        """
        return await self.trace_forward(lot_id)

    async def trace_by_carrier(
        self,
        carrier_id: str,
    ) -> Dict[str, Any]:
        """按载具追溯

        获取载具及其装载晶圆的追溯信息。

        Args:
            carrier_id: 载具ID

        Returns:
            载具追溯结果
        """
        carrier = await self.carriers.get_carrier(carrier_id)

        if not carrier:
            return {
                "carrier_id": carrier_id,
                "error": "Carrier not found",
            }

        trace: Dict[str, Any] = {
            "carrier_id": carrier_id,
            "carrier_type": carrier.carrier_type.value,
            "status": carrier.status.value,
            "current_location": carrier.current_location,
            "wafer_count": len(carrier.wafer_ids),
            "wafers": [],
        }

        # 追溯每个晶圆
        for wafer_id in carrier.wafer_ids:
            wafer_trace = await self.trace_backward(wafer_id)
            trace["wafers"].append({
                "wafer_id": wafer_id,
                "lot_id": wafer_trace.get("lot_id"),
                "current_status": wafer_trace.get("current_status"),
                "events_count": wafer_trace.get("summary", {}).get("total_events", 0),
                "equipment_path": wafer_trace.get("equipment_path", []),
            })

        return trace

    async def impact_analysis(
        self,
        equipment_id: str,
        time_range: Tuple[datetime, datetime],
    ) -> Dict[str, Any]:
        """影响分析

        分析指定设备在指定时间范围内处理的所有晶圆和批次。

        Args:
            equipment_id: 设备ID
            time_range: 时间范围 (start, end)

        Returns:
            影响分析结果
        """
        affected_wafers = await self.tracker.find_affected_wafers(
            equipment_id,
            time_range,
        )

        # 统计受影响批次
        affected_lots = set()
        affected_equipment = set()
        recipes_used = []
        wafer_details = []

        for wafer_id in affected_wafers:
            wafer = await self.tracker.get_wafer(wafer_id)
            if wafer:
                affected_lots.add(wafer.lot_id)
                wafer_details.append({
                    "wafer_id": wafer_id,
                    "lot_id": wafer.lot_id,
                    "status": wafer.status.value,
                })

                # 收集设备和配方信息
                for event in wafer.history:
                    if event.equipment_id == equipment_id:
                        if event.recipe_name and event.recipe_name not in recipes_used:
                            recipes_used.append(event.recipe_name)

        # 获取该设备处理的晶圆详情
        wafer_events = []
        for wafer_id in affected_wafers:
            wafer = await self.tracker.get_wafer(wafer_id)
            if wafer:
                for event in wafer.history:
                    if event.equipment_id == equipment_id:
                        wafer_events.append({
                            "wafer_id": wafer_id,
                            "lot_id": event.lot_id,
                            "event_type": event.event_type,
                            "time": event.timestamp.isoformat(),
                            "recipe": event.recipe_name,
                            "chamber": event.chamber_id,
                            "duration": event.duration_seconds,
                        })

        # 按时间排序
        wafer_events.sort(key=lambda e: e["time"])

        return {
            "equipment_id": equipment_id,
            "time_range": {
                "start": time_range[0].isoformat(),
                "end": time_range[1].isoformat(),
            },
            "affected_wafers": affected_wafers,
            "affected_lots": list(affected_lots),
            "recipes_used": recipes_used,
            "total_wafers": len(affected_wafers),
            "total_lots": len(affected_lots),
            "wafer_details": wafer_details,
            "wafer_events": wafer_events,
        }

    async def trace_quality_issue(
        self,
        wafer_id: str,
    ) -> Dict[str, Any]:
        """质量追溯

        追溯晶圆的质量相关事件。

        Args:
            wafer_id: 晶圆ID

        Returns:
            质量追溯结果
        """
        wafer = await self.tracker.get_wafer(wafer_id)

        if not wafer:
            return {
                "wafer_id": wafer_id,
                "error": "Wafer not found",
            }

        trace: Dict[str, Any] = {
            "wafer_id": wafer_id,
            "lot_id": wafer.lot_id,
            "quality_events": [],
            "measurements": {},
        }

        # 收集质量相关事件
        for event in wafer.history:
            if event.measurements:
                trace["measurements"][event.event_type] = event.measurements
            if event.result or event.measurements:
                trace["quality_events"].append({
                    "time": event.timestamp.isoformat(),
                    "event": event.event_type,
                    "equipment": event.equipment_id,
                    "recipe": event.recipe_name,
                    "result": event.result,
                    "measurements": event.measurements,
                })

        # 添加统计信息
        trace["summary"] = {
            "total_events": len(wafer.history),
            "quality_events": len(trace["quality_events"]),
            "measurements_types": list(trace["measurements"].keys()),
        }

        return trace

    async def get_traceability_report(
        self,
        lot_ids: Optional[List[str]] = None,
        wafer_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """生成追溯报告

        Args:
            lot_ids: 批次ID列表
            wafer_ids: 晶圆ID列表

        Returns:
            追溯报告
        """
        report: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lots": [],
            "wafers": [],
        }

        # 追溯批次
        if lot_ids:
            for lot_id in lot_ids:
                lot_trace = await self.trace_forward(lot_id)
                report["lots"].append(lot_trace)

        # 追溯晶圆
        if wafer_ids:
            for wafer_id in wafer_ids:
                wafer_trace = await self.trace_backward(wafer_id)
                report["wafers"].append(wafer_trace)

        # 添加统计信息
        report["summary"] = {
            "total_lots": len(report["lots"]),
            "total_wafers": len(report["wafers"]),
        }

        return report

    async def verify_traceability_chain(
        self,
        wafer_id: str,
    ) -> Dict[str, Any]:
        """验证追溯链完整性

        检查晶圆的追溯链是否完整。

        Args:
            wafer_id: 晶圆ID

        Returns:
            验证结果
        """
        wafer = await self.tracker.get_wafer(wafer_id)

        if not wafer:
            return {
                "wafer_id": wafer_id,
                "valid": False,
                "error": "Wafer not found",
            }

        issues = []
        event_sequence = []

        # 检查事件序列
        expected_events = ["WAFER_LOADED"]
        for event in wafer.history:
            event_sequence.append(event.event_type)

        # 检查是否有断开的地方
        for i, event in enumerate(wafer.history):
            # 检查位置连续性
            if event.equipment_id:
                if i > 0:
                    prev_event = wafer.history[i - 1]
                    if prev_event.equipment_id and prev_event.equipment_id != event.equipment_id:
                        # 检查中间是否有移动事件
                        if event.event_type not in ["CARRIER_MOVED", "CARRIER_ARRIVED"]:
                            issues.append({
                                "type": "discontinuity",
                                "from": prev_event.equipment_id,
                                "to": event.equipment_id,
                                "event": event.event_type,
                            })

            # 检查工艺结束后的状态
            if event.event_type == "PROCESS_END":
                if i + 1 < len(wafer.history):
                    next_event = wafer.history[i + 1]
                    if next_event.event_type not in ["WAFER_UNLOADED", "PROCESS_START"]:
                        issues.append({
                            "type": "unexpected_sequence",
                            "current": event.event_type,
                            "next": next_event.event_type,
                        })

        return {
            "wafer_id": wafer_id,
            "valid": len(issues) == 0,
            "event_count": len(wafer.history),
            "issues": issues,
            "event_sequence": event_sequence,
        }
