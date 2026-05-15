"""晶圆追踪模块

提供晶圆的位置跟踪、工艺历史记录、追溯查询等功能。
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from myeap.tracking.models import (
    Wafer,
    WaferEvent,
    WaferStatus,
    ProcessResult,
    EventType,
)


class WaferTracker:
    """晶圆追踪器

    负责：
    - 晶圆位置跟踪
    - 工艺历史记录
    - 追溯查询
    - 腔体映射

    Attributes:
        db_manager: 数据库管理器 (可选，用于持久化)
    """

    def __init__(self, db_manager=None):
        """初始化晶圆追踪器

        Args:
            db_manager: 数据库管理器实例，用于持久化晶圆数据
        """
        self.db = db_manager
        self._wafers: Dict[str, Wafer] = {}
        self._lot_index: Dict[str, List[str]] = {}  # lot_id -> [wafer_ids]
        self._location_index: Dict[str, str] = {}  # location -> wafer_id
        self._equipment_index: Dict[str, List[str]] = {}  # equipment_id -> [wafer_ids]

    async def track_wafer(
        self,
        wafer_id: str,
        lot_id: str,
        carrier_id: Optional[str] = None,
        position: Optional[int] = None,
    ) -> Wafer:
        """追踪晶圆

        如果晶圆不存在，则创建新的晶圆记录。

        Args:
            wafer_id: 晶圆ID
            lot_id: 批次ID
            carrier_id: 载具ID (可选)
            position: 在载具中的位置 (可选)

        Returns:
            晶圆对象
        """
        # 检查内存缓存
        wafer = self._wafers.get(wafer_id)
        if not wafer and self.db:
            # 从数据库获取
            wafer = await self.db.get_wafer(wafer_id)

        if not wafer:
            # 创建新的晶圆记录
            wafer = Wafer(
                wafer_id=wafer_id,
                lot_id=lot_id,
                current_carrier_id=carrier_id,
                position=position,
                status=WaferStatus.IN_CARRIER,
            )

            # 更新批次索引
            if lot_id not in self._lot_index:
                self._lot_index[lot_id] = []
            self._lot_index[lot_id].append(wafer_id)

            # 如果有数据库，保存到数据库
            if self.db:
                await self.db.save_wafer(wafer)

        # 更新内存缓存
        self._wafers[wafer_id] = wafer

        # 更新载具索引
        if carrier_id:
            wafer.current_carrier_id = carrier_id
            wafer.position = position

        return wafer

    async def get_wafer(self, wafer_id: str) -> Optional[Wafer]:
        """获取晶圆

        Args:
            wafer_id: 晶圆ID

        Returns:
            晶圆对象，如果不存在则返回None
        """
        # 检查内存缓存
        wafer = self._wafers.get(wafer_id)
        if wafer:
            return wafer

        # 从数据库获取
        if self.db:
            wafer = await self.db.get_wafer(wafer_id)
            if wafer:
                self._wafers[wafer_id] = wafer

        return wafer

    async def update_wafer_location(
        self,
        wafer_id: str,
        location: str,
        carrier_id: Optional[str] = None,
        position: Optional[int] = None,
    ) -> bool:
        """更新晶圆位置

        Args:
            wafer_id: 晶圆ID
            location: 位置
            carrier_id: 载具ID
            position: 在载具中的位置

        Returns:
            是否成功更新
        """
        wafer = await self.get_wafer(wafer_id)
        if not wafer:
            return False

        # 从旧位置移除
        if wafer.current_location:
            # 从设备索引中移除
            if wafer.current_location in self._equipment_index:
                if wafer_id in self._equipment_index[wafer.current_location]:
                    self._equipment_index[wafer.current_location].remove(wafer_id)
            # 从位置索引中移除
            if self._location_index.get(wafer.current_location) == wafer_id:
                del self._location_index[wafer.current_location]

        # 更新位置
        wafer.current_location = location
        wafer.current_carrier_id = carrier_id
        wafer.position = position

        # 更新索引
        self._location_index[location] = wafer_id

        # 如果是设备位置，更新设备索引
        if location.startswith("EQ-"):
            if location not in self._equipment_index:
                self._equipment_index[location] = []
            if wafer_id not in self._equipment_index[location]:
                self._equipment_index[location].append(wafer_id)

        # 保存到数据库
        if self.db:
            await self.db.save_wafer(wafer)

        return True

    async def record_process_event(
        self,
        wafer_id: str,
        event: WaferEvent,
    ) -> None:
        """记录工艺事件

        Args:
            wafer_id: 晶圆ID
            event: 晶圆事件
        """
        wafer = self._wafers.get(wafer_id)
        if not wafer and self.db:
            wafer = await self.db.get_wafer(wafer_id)
            if wafer:
                self._wafers[wafer_id] = wafer

        if wafer:
            # 添加事件到历史
            wafer.history.append(event)

            # 更新索引
            if event.equipment_id:
                wafer.current_location = event.equipment_id
                self._location_index[event.equipment_id] = wafer_id
                if event.equipment_id not in self._equipment_index:
                    self._equipment_index[event.equipment_id] = []
                if wafer_id not in self._equipment_index[event.equipment_id]:
                    self._equipment_index[event.equipment_id].append(wafer_id)

            # 根据事件类型更新状态
            if event.event_type in (EventType.PROCESS_START, EventType.CHAMBER_START):
                wafer.status = WaferStatus.IN_PROCESS

            # 保存到数据库
            if self.db:
                await self.db.save_wafer(wafer)
                await self.db.save_wafer_event(event)

    async def record_wafer_loaded(
        self,
        wafer_id: str,
        lot_id: str,
        carrier_id: str,
        position: int,
        equipment_id: Optional[str] = None,
    ) -> WaferEvent:
        """记录晶圆装载事件

        Args:
            wafer_id: 晶圆ID
            lot_id: 批次ID
            carrier_id: 载具ID
            position: 位置
            equipment_id: 设备ID

        Returns:
            记录的事件
        """
        # 确保晶圆存在
        wafer = await self.get_wafer(wafer_id)
        if not wafer:
            wafer = await self.track_wafer(
                wafer_id=wafer_id,
                lot_id=lot_id,
                carrier_id=carrier_id,
                position=position,
            )

        event = WaferEvent(
            event_id=str(uuid.uuid4()),
            wafer_id=wafer_id,
            lot_id=lot_id,
            event_type=EventType.WAFER_LOADED,
            carrier_id=carrier_id,
            position=position,
            equipment_id=equipment_id,
            timestamp=datetime.now(timezone.utc),
        )

        await self.record_process_event(wafer_id, event)

        # 更新晶圆状态
        wafer = await self.get_wafer(wafer_id)
        if wafer:
            wafer.current_carrier_id = carrier_id
            wafer.position = position
            wafer.status = WaferStatus.IN_CARRIER

        return event

    async def record_process_start(
        self,
        wafer_id: str,
        lot_id: str,
        equipment_id: str,
        chamber_id: Optional[str] = None,
        recipe_id: Optional[str] = None,
        recipe_name: Optional[str] = None,
    ) -> WaferEvent:
        """记录工艺开始事件

        Args:
            wafer_id: 晶圆ID
            lot_id: 批次ID
            equipment_id: 设备ID
            chamber_id: 腔体ID
            recipe_id: 配方ID
            recipe_name: 配方名称

        Returns:
            记录的事件
        """
        event = WaferEvent(
            event_id=str(uuid.uuid4()),
            wafer_id=wafer_id,
            lot_id=lot_id,
            event_type=EventType.PROCESS_START,
            equipment_id=equipment_id,
            chamber_id=chamber_id,
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            timestamp=datetime.now(timezone.utc),
        )

        await self.record_process_event(wafer_id, event)

        # 更新晶圆状态
        wafer = await self.get_wafer(wafer_id)
        if wafer:
            wafer.status = WaferStatus.IN_PROCESS

        return event

    async def record_process_end(
        self,
        wafer_id: str,
        lot_id: str,
        equipment_id: str,
        duration_seconds: float,
        result: Optional[Dict] = None,
        measurements: Optional[Dict[str, float]] = None,
    ) -> WaferEvent:
        """记录工艺结束事件

        Args:
            wafer_id: 晶圆ID
            lot_id: 批次ID
            equipment_id: 设备ID
            duration_seconds: 持续时间
            result: 处理结果
            measurements: 质量数据

        Returns:
            记录的事件
        """
        # 确定状态
        status = "COMPLETED"
        wafer_status = WaferStatus.COMPLETED
        if result:
            status = result.get("status", "COMPLETED")
            if status == "FAILED":
                wafer_status = WaferStatus.REJECTED

        event = WaferEvent(
            event_id=str(uuid.uuid4()),
            wafer_id=wafer_id,
            lot_id=lot_id,
            event_type=EventType.PROCESS_END,
            equipment_id=equipment_id,
            duration_seconds=duration_seconds,
            result=result,
            measurements=measurements,
            timestamp=datetime.now(timezone.utc),
        )

        await self.record_process_event(wafer_id, event)

        # 更新晶圆状态
        wafer = await self.get_wafer(wafer_id)
        if wafer:
            wafer.status = wafer_status

        return event

    async def get_wafer_history(self, wafer_id: str) -> List[WaferEvent]:
        """获取晶圆历史

        Args:
            wafer_id: 晶圆ID

        Returns:
            事件列表
        """
        wafer = self._wafers.get(wafer_id)
        if wafer:
            return wafer.history

        # 从数据库获取
        if self.db:
            return await self.db.get_wafer_events(wafer_id)

        return []

    async def trace_lot(self, lot_id: str) -> List[WaferEvent]:
        """追溯批次

        获取批次中所有晶圆的事件历史。

        Args:
            lot_id: 批次ID

        Returns:
            所有晶圆事件的列表
        """
        events = []

        # 从批次索引获取晶圆ID
        wafer_ids = self._lot_index.get(lot_id, [])

        for wafer_id in wafer_ids:
            wafer = await self.get_wafer(wafer_id)
            if wafer:
                events.extend(wafer.history)

        # 从数据库获取
        if self.db:
            db_events = await self.db.get_lot_events(lot_id)
            # 合并去重
            existing_ids = {e.event_id for e in events}
            for event in db_events:
                if event.event_id not in existing_ids:
                    events.append(event)

        # 按时间排序
        events.sort(key=lambda e: e.timestamp)

        return events

    async def find_affected_wafers(
        self,
        equipment_id: str,
        time_range: Tuple[datetime, datetime],
    ) -> List[str]:
        """查找受影响晶圆

        查找在指定时间范围内在指定设备上处理过的晶圆。

        Args:
            equipment_id: 设备ID
            time_range: 时间范围 (start, end)

        Returns:
            受影响的晶圆ID列表
        """
        start_time, end_time = time_range
        affected_wafers = []

        # 从设备索引获取晶圆ID
        if equipment_id in self._equipment_index:
            for wafer_id in self._equipment_index[equipment_id]:
                wafer = await self.get_wafer(wafer_id)
                if wafer:
                    # 检查是否有事件在时间范围内
                    for event in wafer.history:
                        if (
                            event.equipment_id == equipment_id
                            and start_time <= event.timestamp <= end_time
                        ):
                            if wafer_id not in affected_wafers:
                                affected_wafers.append(wafer_id)
                            break

        # 从数据库获取
        if self.db:
            db_wafers = await self.db.get_wafers_at_equipment(
                equipment_id, start_time, end_time
            )
            for wafer_id in db_wafers:
                if wafer_id not in affected_wafers:
                    affected_wafers.append(wafer_id)

        return affected_wafers

    async def get_wafers_at_location(self, location: str) -> List[Wafer]:
        """获取指定位置的晶圆

        Args:
            location: 位置ID

        Returns:
            晶圆列表
        """
        wafers = []

        # 从位置索引获取晶圆ID
        wafer_id = self._location_index.get(location)
        if wafer_id:
            wafer = await self.get_wafer(wafer_id)
            if wafer:
                wafers.append(wafer)

        # 从设备索引获取
        if location in self._equipment_index:
            for wafer_id in self._equipment_index[location]:
                wafer = await self.get_wafer(wafer_id)
                if wafer and wafer not in wafers:
                    wafers.append(wafer)

        return wafers

    async def get_wafers_by_status(self, status: WaferStatus) -> List[Wafer]:
        """按状态获取晶圆

        Args:
            status: 晶圆状态

        Returns:
            晶圆列表
        """
        return [w for w in self._wafers.values() if w.status == status]

    async def get_all_wafers(self) -> List[Wafer]:
        """获取所有晶圆

        Returns:
            晶圆列表
        """
        return list(self._wafers.values())

    async def get_wafer_count(self) -> Dict[WaferStatus, int]:
        """获取各状态的晶圆数量

        Returns:
            状态到数量的映射
        """
        counts: Dict[WaferStatus, int] = {status: 0 for status in WaferStatus}
        for wafer in self._wafers.values():
            counts[wafer.status] += 1
        return counts

    def get_tracker_stats(self) -> Dict[str, int]:
        """获取追踪器统计信息

        Returns:
            统计信息字典
        """
        total = len(self._wafers)
        by_status = {}
        for status in WaferStatus:
            by_status[status.value] = sum(
                1 for w in self._wafers.values() if w.status == status
            )

        return {
            "total": total,
            "by_status": by_status,
            "tracked_lots": len(self._lot_index),
            "equipment_count": len(self._equipment_index),
        }
