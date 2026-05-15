"""载具管理模块

提供载具的注册、位置跟踪、状态管理等功能。
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from myeap.tracking.models import (
    Carrier,
    CarrierStatus,
    CarrierType,
    WaferEvent,
    EventType,
)


class CarrierManager:
    """载具管理器

    负责：
    - 载具注册和注销
    - 载具位置跟踪
    - 载具状态管理
    - 载具与晶圆关联

    Attributes:
        db_manager: 数据库管理器 (可选，用于持久化)
    """

    def __init__(self, db_manager=None):
        """初始化载具管理器

        Args:
            db_manager: 数据库管理器实例，用于持久化载具数据
        """
        self.db = db_manager
        self._carriers: Dict[str, Carrier] = {}
        self._location_index: Dict[str, str] = {}  # location -> carrier_id
        self._event_callbacks: List[callable] = []

    def register_event_callback(self, callback: callable) -> None:
        """注册事件回调函数

        Args:
            callback: 回调函数，签名为 callback(event: WaferEvent)
        """
        self._event_callbacks.append(callback)

    async def register_carrier(
        self,
        carrier_id: str,
        carrier_type: CarrierType,
        capacity: int,
    ) -> Carrier:
        """注册载具

        Args:
            carrier_id: 载具ID
            carrier_type: 载具类型
            capacity: 载具容量

        Returns:
            注册的载具对象
        """
        # 检查载具是否已存在
        if carrier_id in self._carriers:
            raise ValueError(f"Carrier {carrier_id} already exists")

        carrier = Carrier(
            carrier_id=carrier_id,
            carrier_type=carrier_type,
            capacity=capacity,
            created_at=datetime.now(timezone.utc),
        )

        self._carriers[carrier_id] = carrier

        # 如果有数据库管理器，保存到数据库
        if self.db:
            await self.db.save_carrier(carrier)

        return carrier

    async def unregister_carrier(self, carrier_id: str) -> bool:
        """注销载具

        Args:
            carrier_id: 载具ID

        Returns:
            是否成功注销
        """
        carrier = self._carriers.get(carrier_id)
        if not carrier:
            return False

        # 从位置索引中移除
        if carrier.current_location in self._location_index:
            del self._location_index[carrier.current_location]

        # 从载具字典中移除
        del self._carriers[carrier_id]

        # 如果有数据库管理器，从数据库删除
        if self.db:
            await self.db.delete_carrier(carrier_id)

        return True

    async def load_carrier(
        self,
        carrier_id: str,
        wafer_ids: List[str],
        location: str,
    ) -> bool:
        """装载晶圆到载具

        Args:
            carrier_id: 载具ID
            wafer_ids: 晶圆ID列表
            location: 位置

        Returns:
            是否成功装载
        """
        carrier = self._carriers.get(carrier_id)
        if not carrier:
            return False

        if len(wafer_ids) > carrier.capacity:
            return False

        carrier.wafer_ids = wafer_ids
        carrier.current_location = location
        carrier.status = CarrierStatus.LOADED
        carrier.loaded_at = datetime.now(timezone.utc)

        # 更新位置索引
        self._location_index[location] = carrier_id

        # 如果有数据库管理器，更新数据库
        if self.db:
            await self.db.update_carrier(carrier)

        return True

    async def unload_carrier(self, carrier_id: str) -> List[str]:
        """从载具卸载晶圆

        Args:
            carrier_id: 载具ID

        Returns:
            被卸载的晶圆ID列表
        """
        carrier = self._carriers.get(carrier_id)
        if not carrier:
            return []

        wafer_ids = carrier.wafer_ids.copy()

        carrier.wafer_ids = []
        carrier.status = CarrierStatus.IDLE
        carrier.unloaded_at = datetime.now(timezone.utc)

        # 如果有数据库管理器，更新数据库
        if self.db:
            await self.db.update_carrier(carrier)

        return wafer_ids

    async def move_carrier(
        self,
        carrier_id: str,
        destination: str,
    ) -> bool:
        """移动载具

        Args:
            carrier_id: 载具ID
            destination: 目标位置

        Returns:
            是否成功移动
        """
        carrier = self._carriers.get(carrier_id)
        if not carrier:
            return False

        # 从旧位置移除
        if carrier.current_location in self._location_index:
            del self._location_index[carrier.current_location]

        # 更新位置
        carrier.current_location = destination
        carrier.status = CarrierStatus.IN_TRANSIT

        # 更新位置索引
        self._location_index[destination] = carrier_id

        # 如果有数据库管理器，更新数据库
        if self.db:
            await self.db.update_carrier(carrier)

        # 记录事件
        await self._record_event(
            wafer_ids=carrier.wafer_ids,
            lot_id=carrier.wafer_ids[0] if carrier.wafer_ids else None,
            event_type=EventType.CARRIER_MOVED,
            equipment_id=destination,
        )

        return True

    async def arrive_at_equipment(
        self,
        carrier_id: str,
        equipment_id: str,
        position: int,
    ) -> bool:
        """载具到达设备

        Args:
            carrier_id: 载具ID
            equipment_id: 设备ID
            position: 在设备中的位置

        Returns:
            是否成功
        """
        carrier = self._carriers.get(carrier_id)
        if not carrier:
            return False

        carrier.current_position = position
        carrier.status = CarrierStatus.AT_EQUIPMENT

        # 如果有数据库管理器，更新数据库
        if self.db:
            await self.db.update_carrier(carrier)

        # 记录事件
        await self._record_event(
            wafer_ids=carrier.wafer_ids,
            lot_id=carrier.wafer_ids[0] if carrier.wafer_ids else None,
            event_type=EventType.CARRIER_ARRIVED,
            equipment_id=equipment_id,
        )

        return True

    async def depart_from_equipment(self, carrier_id: str) -> bool:
        """载具离开设备

        Args:
            carrier_id: 载具ID

        Returns:
            是否成功
        """
        carrier = self._carriers.get(carrier_id)
        if not carrier:
            return False

        equipment_id = carrier.current_location
        carrier.current_position = None
        carrier.status = CarrierStatus.IN_TRANSIT

        # 如果有数据库管理器，更新数据库
        if self.db:
            await self.db.update_carrier(carrier)

        # 记录事件
        await self._record_event(
            wafer_ids=carrier.wafer_ids,
            lot_id=carrier.wafer_ids[0] if carrier.wafer_ids else None,
            event_type=EventType.CARRIER_DEPARTED,
            equipment_id=equipment_id,
        )

        return True

    async def get_carrier(self, carrier_id: str) -> Optional[Carrier]:
        """获取载具

        Args:
            carrier_id: 载具ID

        Returns:
            载具对象，如果不存在则返回None
        """
        return self._carriers.get(carrier_id)

    async def get_carrier_at_location(self, location: str) -> Optional[Carrier]:
        """获取指定位置的载具

        Args:
            location: 位置ID

        Returns:
            载具对象，如果不存在则返回None
        """
        carrier_id = self._location_index.get(location)
        if carrier_id:
            return self._carriers.get(carrier_id)
        return None

    async def get_carriers_at_equipment(self, equipment_id: str) -> List[Carrier]:
        """获取指定设备的载具

        Args:
            equipment_id: 设备ID

        Returns:
            载具列表
        """
        return [
            c
            for c in self._carriers.values()
            if c.current_location == equipment_id
            and c.status == CarrierStatus.AT_EQUIPMENT
        ]

    async def get_carriers_by_status(self, status: CarrierStatus) -> List[Carrier]:
        """按状态获取载具

        Args:
            status: 载具状态

        Returns:
            载具列表
        """
        return [c for c in self._carriers.values() if c.status == status]

    async def get_all_carriers(self) -> List[Carrier]:
        """获取所有载具

        Returns:
            载具列表
        """
        return list(self._carriers.values())

    async def get_carrier_count(self) -> Dict[CarrierStatus, int]:
        """获取各状态的载具数量

        Returns:
            状态到数量的映射
        """
        counts: Dict[CarrierStatus, int] = {status: 0 for status in CarrierStatus}
        for carrier in self._carriers.values():
            counts[carrier.status] += 1
        return counts

    async def _record_event(
        self,
        wafer_ids: List[str],
        lot_id: Optional[str],
        event_type: str,
        equipment_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """记录事件

        Args:
            wafer_ids: 晶圆ID列表
            lot_id: 批次ID
            event_type: 事件类型
            equipment_id: 设备ID
            **kwargs: 其他事件参数
        """
        if not wafer_ids or not lot_id:
            return

        for wafer_id in wafer_ids:
            event = WaferEvent(
                event_id=str(uuid.uuid4()),
                wafer_id=wafer_id,
                lot_id=lot_id,
                event_type=event_type,
                equipment_id=equipment_id,
                timestamp=datetime.now(timezone.utc),
                **kwargs,
            )

            # 触发回调
            for callback in self._event_callbacks:
                try:
                    await callback(event) if asyncio.iscoroutinefunction(callback) else callback(event)
                except Exception:
                    pass  # 忽略回调异常

    def get_carrier_stats(self) -> Dict[str, int]:
        """获取载具统计信息

        Returns:
            统计信息字典
        """
        total = len(self._carriers)
        by_status = {}
        for status in CarrierStatus:
            by_status[status.value] = sum(
                1 for c in self._carriers.values() if c.status == status
            )

        return {
            "total": total,
            "by_status": by_status,
        }


# Import asyncio for type checking
import asyncio
