"""清洗设备插件

实现清洗设备的设备插件接口。
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from myeap.core.logging import get_logger
from myeap.device.plugins.base import EquipmentPlugin
from myeap.device.process import ProcessInstance, ProcessState

logger = get_logger(__name__)


class CleanerPlugin(EquipmentPlugin):
    """清洗设备插件

    实现清洗设备的特定功能：
    - 清洗工艺控制
    - 药液管理
    - 超声控制
    - 漂洗控制
    """

    @property
    def equipment_type(self) -> str:
        return "cleaner"

    def __init__(self):
        super().__init__()
        self._processes: Dict[str, ProcessInstance] = {}
        self._recipes: Dict[str, Dict[str, Any]] = {}
        self._chemical_levels: Dict[str, float] = {}
        self._ultrasonic_power: Dict[str, float] = {}

    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件

        Args:
            config: 插件配置
        """
        self._config = config
        self._recipes = config.get("recipes", {})
        self._initialized = True
        logger.info("cleaner_plugin_initialized", config=config)

    async def on_connected(self) -> None:
        """连接建立回调"""
        logger.info("cleaner_connected", equipment_id=self._equipment_id)

    async def on_disconnected(self) -> None:
        """连接断开回调"""
        # 停止所有活跃工艺
        for process_id, process in self._processes.items():
            if process.is_active:
                await self.abort_process(process_id)
        logger.info("cleaner_disconnected", equipment_id=self._equipment_id)

    async def handle_message(self, message: Any) -> Optional[Any]:
        """处理设备消息

        Args:
            message: SECS消息

        Returns:
            响应消息
        """
        # 处理设备特定消息
        msg_type = getattr(message, "type", None) or getattr(message, "sf", None)

        if msg_type == "S6F11":  # Event Report
            return await self._handle_event_report(message)
        elif msg_type == "S5F1":  # Alarm Report
            return await self._handle_alarm_report(message)
        elif msg_type == "S2F41":  # Recipe Download Ack
            return await self._handle_recipe_ack(message)

        return None

    async def _handle_event_report(self, message: Any) -> Optional[Any]:
        """处理事件报告"""
        logger.debug("cleaner_event_report", equipment_id=self._equipment_id)
        return None

    async def _handle_alarm_report(self, message: Any) -> Optional[Any]:
        """处理报警报告"""
        alarm_id = message.get("alarm_id")
        alarm_message = message.get("message", "Unknown alarm")
        severity = message.get("severity", "INFO")

        await self.on_alarm({
            "id": alarm_id,
            "message": alarm_message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return None

    async def _handle_recipe_ack(self, message: Any) -> Optional[Any]:
        """处理配方确认"""
        ack = message.get("ack", 0)
        logger.debug("cleaner_recipe_ack", equipment_id=self._equipment_id, ack=ack)
        return None

    async def start_process(
        self,
        recipe_id: str,
        chamber_id: str,
        params: Dict[str, Any],
    ) -> str:
        """启动清洗工艺

        Args:
            recipe_id: 配方ID
            chamber_id: 腔体ID
            params: 工艺参数，包含 wafer_ids

        Returns:
            工艺实例ID
        """
        # 验证配方
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            raise ValueError(f"Recipe not found: {recipe_id}")

        # 创建工艺实例
        process_id = f"cleaner-{uuid.uuid4().hex[:8]}"

        process = ProcessInstance(
            process_id=process_id,
            equipment_id=self._equipment_id or "",
            chamber_id=chamber_id,
            recipe_id=recipe_id,
            recipe_name=recipe.get("name", recipe_id),
            wafer_ids=params.get("wafer_ids", []),
            lot_id=params.get("lot_id"),
        )

        # 创建工艺步骤
        steps = recipe.get("steps", [])
        for i, step in enumerate(steps):
            from myeap.device.process import ProcessStep
            process.steps.append(ProcessStep(
                step_id=i,
                name=step.get("name", f"Step {i}"),
                duration=step.get("duration", 60),
                parameters=step.get("parameters", {}),
            ))

        # 启动工艺
        self._processes[process_id] = process
        process.start()

        logger.info(
            "cleaner_process_started",
            equipment_id=self._equipment_id,
            process_id=process_id,
            recipe_id=recipe_id,
            chamber_id=chamber_id,
            wafer_count=len(process.wafer_ids),
        )

        return process_id

    async def pause_process(self, process_id: str) -> bool:
        """暂停清洗工艺

        Args:
            process_id: 工艺实例ID

        Returns:
            是否成功
        """
        process = self._processes.get(process_id)
        if not process:
            return False

        if process.state != ProcessState.RUNNING:
            return False

        process.pause()
        logger.info("cleaner_process_paused", process_id=process_id)
        return True

    async def resume_process(self, process_id: str) -> bool:
        """恢复清洗工艺

        Args:
            process_id: 工艺实例ID

        Returns:
            是否成功
        """
        process = self._processes.get(process_id)
        if not process:
            return False

        if process.state != ProcessState.PAUSED:
            return False

        process.resume()
        logger.info("cleaner_process_resumed", process_id=process_id)
        return True

    async def abort_process(self, process_id: str) -> bool:
        """中止清洗工艺

        Args:
            process_id: 工艺实例ID

        Returns:
            是否成功
        """
        process = self._processes.get(process_id)
        if not process:
            return False

        process.abort()
        logger.info("cleaner_process_aborted", process_id=process_id)
        return True

    async def get_process_status(self, process_id: str) -> Dict[str, Any]:
        """获取工艺状态

        Args:
            process_id: 工艺实例ID

        Returns:
            工艺状态信息
        """
        process = self._processes.get(process_id)
        if not process:
            return {"error": f"Process not found: {process_id}"}

        return process.to_dict()

    async def validate_recipe(self, recipe: Dict[str, Any]) -> bool:
        """验证清洗配方

        Args:
            recipe: 配方数据

        Returns:
            验证是否通过
        """
        # 检查必要字段
        if "name" not in recipe:
            return False

        if "steps" not in recipe or not isinstance(recipe["steps"], list):
            return False

        # 验证每个步骤
        for step in recipe["steps"]:
            if "name" not in step:
                return False
            if "duration" not in step or step["duration"] <= 0:
                return False

        return True

    async def get_capabilities(self) -> Dict[str, Any]:
        """获取设备能力

        Returns:
            设备能力字典
        """
        return {
            "supports_chemical_management": True,
            "supports_ultrasonic": True,
            "supports_rinse": True,
            "supports_drying": True,
            "max_chambers": self._config.get("max_chambers", 4),
            "max_wafer_per_chamber": self._config.get("max_wafer_per_chamber", 25),
            "chemical_count": self._config.get("chemical_count", 6),
        }

    async def get_supported_recipes(self) -> List[str]:
        """获取支持的配方列表

        Returns:
            配方ID列表
        """
        return list(self._recipes.keys())

    # ========== 清洗设备特定方法 ==========

    async def get_chemical_levels(self) -> Dict[str, float]:
        """获取药液液位

        Returns:
            药液液位字典 {chemical_name: level_percent}
        """
        return self._chemical_levels.copy()

    async def set_chemical_level(self, chemical: str, level: float) -> None:
        """设置药液液位

        Args:
            chemical: 药液名称
            level: 液位百分比
        """
        self._chemical_levels[chemical] = level
        logger.debug("chemical_level_set", chemical=chemical, level=level)

    async def get_ultrasonic_power(self, chamber_id: str) -> float:
        """获取超声功率

        Args:
            chamber_id: 腔体ID

        Returns:
            超声功率百分比
        """
        return self._ultrasonic_power.get(chamber_id, 0.0)

    async def set_ultrasonic_power(self, chamber_id: str, power: float) -> None:
        """设置超声功率

        Args:
            chamber_id: 腔体ID
            power: 功率百分比 (0-100)
        """
        self._ultrasonic_power[chamber_id] = max(0.0, min(100.0, power))
        logger.debug("ultrasonic_power_set", chamber_id=chamber_id, power=power)

    async def trigger_drying(self, chamber_id: str) -> bool:
        """触发干燥

        Args:
            chamber_id: 腔体ID

        Returns:
            是否成功
        """
        logger.info("drying_triggered", chamber_id=chamber_id)
        return True
