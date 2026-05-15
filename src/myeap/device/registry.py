"""设备注册表模块

提供设备注册、发现和管理功能。
"""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from myeap.core.logging import get_logger
from myeap.device.equipment import Equipment, EquipmentStatus, EquipmentType

logger = get_logger(__name__)


class EquipmentRegistry:
    """设备注册表

    管理所有设备连接，支持：
    - 设备注册/注销
    - 设备状态查询
    - 设备连接管理
    - 设备分组
    - 驱动程序管理

    Example:
        registry = EquipmentRegistry()
        await registry.register(equipment, driver)
        eq = await registry.get("equipment-001")
        available = await registry.get_available(EquipmentType.CLEANER)
    """

    def __init__(self):
        self._equipment: Dict[str, Equipment] = {}
        self._drivers: Dict[str, Any] = {}
        self._groups: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        equipment: Equipment,
        driver: Any,
    ) -> None:
        """注册设备

        Args:
            equipment: 设备对象
            driver: 设备驱动程序
        """
        async with self._lock:
            if equipment.equipment_id in self._equipment:
                logger.warning(
                    "equipment_already_registered",
                    equipment_id=equipment.equipment_id,
                )
                return

            self._equipment[equipment.equipment_id] = equipment
            self._drivers[equipment.equipment_id] = driver

            logger.info(
                "equipment_registered",
                equipment_id=equipment.equipment_id,
                equipment_type=equipment.equipment_type.value,
                host=equipment.host,
                port=equipment.port,
            )

    async def unregister(self, equipment_id: str) -> None:
        """注销设备

        Args:
            equipment_id: 设备ID
        """
        async with self._lock:
            if equipment_id in self._equipment:
                del self._equipment[equipment_id]
                logger.info("equipment_unregistered", equipment_id=equipment_id)

            if equipment_id in self._drivers:
                del self._drivers[equipment_id]

    async def get(self, equipment_id: str) -> Optional[Equipment]:
        """获取设备

        Args:
            equipment_id: 设备ID

        Returns:
            设备对象或None
        """
        return self._equipment.get(equipment_id)

    async def get_or_raise(self, equipment_id: str) -> Equipment:
        """获取设备，不存在则抛出异常

        Args:
            equipment_id: 设备ID

        Returns:
            设备对象

        Raises:
            ValueError: 设备不存在
        """
        equipment = await self.get(equipment_id)
        if equipment is None:
            raise ValueError(f"Equipment not found: {equipment_id}")
        return equipment

    def get_driver(self, equipment_id: str) -> Optional[Any]:
        """获取设备驱动程序

        Args:
            equipment_id: 设备ID

        Returns:
            驱动程序或None
        """
        return self._drivers.get(equipment_id)

    async def get_by_type(self, equipment_type: EquipmentType) -> List[Equipment]:
        """按类型获取设备

        Args:
            equipment_type: 设备类型

        Returns:
            设备列表
        """
        return [
            eq for eq in self._equipment.values()
            if eq.equipment_type == equipment_type
        ]

    async def get_available(self, equipment_type: EquipmentType) -> List[Equipment]:
        """获取可用设备

        Args:
            equipment_type: 设备类型

        Returns:
            可用设备列表
        """
        return [
            eq for eq in self._equipment.values()
            if eq.equipment_type == equipment_type and eq.is_available
        ]

    async def get_all(self) -> List[Equipment]:
        """获取所有设备

        Returns:
            所有设备列表
        """
        return list(self._equipment.values())

    async def get_connected(self) -> List[Equipment]:
        """获取已连接设备

        Returns:
            已连接设备列表
        """
        return [eq for eq in self._equipment.values() if eq.is_connected]

    async def get_by_status(self, status: EquipmentStatus) -> List[Equipment]:
        """按状态获取设备

        Args:
            status: 设备状态

        Returns:
            设备列表
        """
        return [eq for eq in self._equipment.values() if eq.status == status]

    def get_connected_count(self) -> int:
        """获取已连接设备数量"""
        return sum(1 for eq in self._equipment.values() if eq.is_connected)

    def get_total_count(self) -> int:
        """获取设备总数"""
        return len(self._equipment)

    def get_count_by_type(self, equipment_type: EquipmentType) -> int:
        """按类型获取设备数量

        Args:
            equipment_type: 设备类型

        Returns:
            设备数量
        """
        return sum(1 for eq in self._equipment.values() if eq.equipment_type == equipment_type)

    def get_count_by_status(self, status: EquipmentStatus) -> int:
        """按状态获取设备数量

        Args:
            status: 设备状态

        Returns:
            设备数量
        """
        return sum(1 for eq in self._equipment.values() if eq.status == status)

    # ========== 分组管理 ==========

    async def add_to_group(self, equipment_id: str, group_name: str) -> None:
        """添加到分组

        Args:
            equipment_id: 设备ID
            group_name: 分组名称
        """
        async with self._lock:
            if equipment_id not in self._equipment:
                raise ValueError(f"Equipment not found: {equipment_id}")

            if group_name not in self._groups:
                self._groups[group_name] = []

            if equipment_id not in self._groups[group_name]:
                self._groups[group_name].append(equipment_id)
                logger.info(
                    "equipment_added_to_group",
                    equipment_id=equipment_id,
                    group=group_name,
                )

    async def remove_from_group(self, equipment_id: str, group_name: str) -> None:
        """从分组移除

        Args:
            equipment_id: 设备ID
            group_name: 分组名称
        """
        async with self._lock:
            if group_name in self._groups and equipment_id in self._groups[group_name]:
                self._groups[group_name].remove(equipment_id)
                logger.info(
                    "equipment_removed_from_group",
                    equipment_id=equipment_id,
                    group=group_name,
                )

    async def get_group(self, group_name: str) -> List[Equipment]:
        """获取分组中的设备

        Args:
            group_name: 分组名称

        Returns:
            设备列表
        """
        async with self._lock:
            equipment_ids = self._groups.get(group_name, [])
            return [self._equipment[eq_id] for eq_id in equipment_ids if eq_id in self._equipment]

    async def get_all_groups(self) -> Dict[str, List[str]]:
        """获取所有分组

        Returns:
            分组字典
        """
        return self._groups.copy()

    async def get_group_names(self) -> List[str]:
        """获取所有分组名称"""
        return list(self._groups.keys())

    # ========== 状态更新 ==========

    async def update_status(self, equipment_id: str, status: EquipmentStatus) -> None:
        """更新设备状态

        Args:
            equipment_id: 设备ID
            status: 新状态
        """
        async with self._lock:
            if equipment_id in self._equipment:
                self._equipment[equipment_id].status = status
                logger.debug(
                    "equipment_status_updated",
                    equipment_id=equipment_id,
                    status=status.value,
                )

    async def update_connection(self, equipment_id: str, connected: bool) -> None:
        """更新连接状态

        Args:
            equipment_id: 设备ID
            connected: 是否已连接
        """
        async with self._lock:
            if equipment_id in self._equipment:
                self._equipment[equipment_id].set_connected(connected)

                logger.info(
                    "equipment_connection_updated",
                    equipment_id=equipment_id,
                    connected=connected,
                )

    async def update_last_message(self, equipment_id: str) -> None:
        """更新最后消息时间

        Args:
            equipment_id: 设备ID
        """
        async with self._lock:
            if equipment_id in self._equipment:
                self._equipment[equipment_id].last_message = datetime.utcnow()

    # ========== 事件处理 ==========

    def set_on_connect(self, callback: Callable[[str], None]) -> None:
        """设置连接回调"""
        self._on_connect = callback

    def set_on_disconnect(self, callback: Callable[[str], None]) -> None:
        """设置断开回调"""
        self._on_disconnect = callback

    def set_on_status_change(self, callback: Callable[[str, EquipmentStatus, EquipmentStatus], None]) -> None:
        """设置状态变化回调"""
        self._on_status_change = callback

    async def _notify_connect(self, equipment_id: str) -> None:
        """通知连接事件"""
        if hasattr(self, "_on_connect"):
            self._on_connect(equipment_id)

    async def _notify_disconnect(self, equipment_id: str) -> None:
        """通知断开事件"""
        if hasattr(self, "_on_disconnect"):
            self._on_disconnect(equipment_id)

    async def _notify_status_change(
        self,
        equipment_id: str,
        old_status: EquipmentStatus,
        new_status: EquipmentStatus,
    ) -> None:
        """通知状态变化事件"""
        if hasattr(self, "_on_status_change"):
            self._on_status_change(equipment_id, old_status, new_status)

    # ========== 统计信息 ==========

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "total": self.get_total_count(),
            "connected": self.get_connected_count(),
            "disconnected": self.get_total_count() - self.get_connected_count(),
            "by_type": {},
            "by_status": {},
        }

        for eq_type in EquipmentType:
            count = self.get_count_by_type(eq_type)
            if count > 0:
                stats["by_type"][eq_type.value] = count

        for status in EquipmentStatus:
            count = self.get_count_by_status(status)
            if count > 0:
                stats["by_status"][status.value] = count

        return stats
