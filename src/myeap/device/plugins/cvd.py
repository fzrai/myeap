"""CVD设备插件

实现化学气相沉积设备的设备插件接口。
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from myeap.core.logging import get_logger
from myeap.device.plugins.base import EquipmentPlugin
from myeap.device.process import ProcessInstance, ProcessState

logger = get_logger(__name__)


class CvdPlugin(EquipmentPlugin):
    """CVD设备插件

    实现CVD设备的特定功能：
    - 薄膜沉积工艺控制
    - 气体流量控制
    - 温度控制
    - 压力控制
    - RF/等离子体控制
    """

    @property
    def equipment_type(self) -> str:
        return "cvd"

    def __init__(self):
        super().__init__()
        self._processes: Dict[str, ProcessInstance] = {}
        self._recipes: Dict[str, Dict[str, Any]] = {}
        self._gas_flows: Dict[str, Dict[str, float]] = {}
        self._temperature_zones: Dict[str, float] = {}
        self._pressure: float = 0.0
        self._rf_power: float = 0.0

    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件

        Args:
            config: 插件配置
        """
        self._config = config
        self._recipes = config.get("recipes", {})
        self._initialized = True
        logger.info("cvd_plugin_initialized", config=config)

    async def on_connected(self) -> None:
        """连接建立回调"""
        logger.info("cvd_connected", equipment_id=self._equipment_id)

    async def on_disconnected(self) -> None:
        """连接断开回调"""
        # 停止所有活跃工艺
        for process_id, process in self._processes.items():
            if process.is_active:
                await self.abort_process(process_id)
        logger.info("cvd_disconnected", equipment_id=self._equipment_id)

    async def handle_message(self, message: Any) -> Optional[Any]:
        """处理设备消息

        Args:
            message: SECS消息

        Returns:
            响应消息
        """
        msg_type = getattr(message, "type", None) or getattr(message, "sf", None)

        if msg_type == "S6F11":  # Event Report
            return await self._handle_event_report(message)
        elif msg_type == "S5F1":  # Alarm Report
            return await self._handle_alarm_report(message)
        elif msg_type == "S7F23":  # Process Recipe Ack
            return await self._handle_recipe_ack(message)
        elif msg_type == "S7F25":  # Process Started Ack
            return await self._handle_process_started(message)

        return None

    async def _handle_event_report(self, message: Any) -> Optional[Any]:
        """处理事件报告"""
        event_id = message.get("event_id")

        # 处理CVD特定事件
        if event_id == "process_started":
            chamber_id = message.get("chamber_id")
            process_id = message.get("process_id")
            if process_id and process_id in self._processes:
                self._processes[process_id].start()
        elif event_id == "process_completed":
            process_id = message.get("process_id")
            if process_id and process_id in self._processes:
                self._processes[process_id].complete()
        elif event_id == "step_completed":
            process_id = message.get("process_id")
            step_id = message.get("step_id")
            if process_id and process_id in self._processes:
                process = self._processes[process_id]
                if step_id < len(process.steps):
                    process.steps[step_id].completed_at = datetime.utcnow()
                    process.move_to_step(step_id + 1)

        logger.debug("cvd_event_report", equipment_id=self._equipment_id, event_id=event_id)
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
        logger.debug("cvd_recipe_ack", equipment_id=self._equipment_id, ack=ack)
        return None

    async def _handle_process_started(self, message: Any) -> Optional[Any]:
        """处理工艺启动确认"""
        process_id = message.get("process_id")
        if process_id and process_id in self._processes:
            self._processes[process_id].start()
        return None

    async def start_process(
        self,
        recipe_id: str,
        chamber_id: str,
        params: Dict[str, Any],
    ) -> str:
        """启动CVD工艺

        Args:
            recipe_id: 配方ID
            chamber_id: 腔体ID
            params: 工艺参数，包含 wafer_ids, thickness_target 等

        Returns:
            工艺实例ID
        """
        # 验证配方
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            raise ValueError(f"Recipe not found: {recipe_id}")

        # 创建工艺实例
        process_id = f"cvd-{uuid.uuid4().hex[:8]}"

        process = ProcessInstance(
            process_id=process_id,
            equipment_id=self._equipment_id or "",
            chamber_id=chamber_id,
            recipe_id=recipe_id,
            recipe_name=recipe.get("name", recipe_id),
            wafer_ids=params.get("wafer_ids", []),
            lot_id=params.get("lot_id"),
            priority=params.get("priority", 5),
        )

        # 添加结果信息
        process.result = {
            "thickness_target": params.get("thickness_target", 0),
            "deposition_rate": recipe.get("deposition_rate", 0),
        }

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

        # 添加腔体信息
        if recipe.get("steps_total"):
            process.recipe_steps_total = recipe["steps_total"]

        # 启动工艺
        self._processes[process_id] = process
        process.start()

        logger.info(
            "cvd_process_started",
            equipment_id=self._equipment_id,
            process_id=process_id,
            recipe_id=recipe_id,
            chamber_id=chamber_id,
            wafer_count=len(process.wafer_ids),
            thickness_target=params.get("thickness_target"),
        )

        return process_id

    async def pause_process(self, process_id: str) -> bool:
        """暂停CVD工艺

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
        logger.info("cvd_process_paused", process_id=process_id)
        return True

    async def resume_process(self, process_id: str) -> bool:
        """恢复CVD工艺

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
        logger.info("cvd_process_resumed", process_id=process_id)
        return True

    async def abort_process(self, process_id: str) -> bool:
        """中止CVD工艺

        Args:
            process_id: 工艺实例ID

        Returns:
            是否成功
        """
        process = self._processes.get(process_id)
        if not process:
            return False

        process.abort()
        logger.info("cvd_process_aborted", process_id=process_id)
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

        status = process.to_dict()

        # 添加CVD特定信息
        status["gas_flows"] = self._gas_flows.get(process.chamber_id, {})
        status["temperature_zones"] = self._temperature_zones.copy()
        status["pressure"] = self._pressure
        status["rf_power"] = self._rf_power

        return status

    async def validate_recipe(self, recipe: Dict[str, Any]) -> bool:
        """验证CVD配方

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

        if len(recipe["steps"]) == 0:
            return False

        # 验证每个步骤
        required_params = ["temperature", "pressure"]
        for step in recipe["steps"]:
            if "name" not in step:
                return False
            if "duration" not in step or step["duration"] <= 0:
                return False

            # 检查温度和压力参数
            params = step.get("parameters", {})
            for param in required_params:
                if param not in params:
                    return False

        return True

    async def get_capabilities(self) -> Dict[str, Any]:
        """获取设备能力

        Returns:
            设备能力字典
        """
        return {
            "supports_plasma": True,
            "supports_multi_layer": True,
            "supports_in_situ_cleaning": True,
            "max_chambers": self._config.get("max_chambers", 4),
            "max_wafer_per_chamber": self._config.get("max_wafer_per_chamber", 25),
            "max_temperature": self._config.get("max_temperature", 900),
            "max_pressure": self._config.get("max_pressure", 100),
            "max_rf_power": self._config.get("max_rf_power", 3000),
            "gas_mbox_count": self._config.get("gas_mbox_count", 8),
            "supported_films": self._config.get("supported_films", [
                "SiO2", "SiN", "Poly-Si", "SiON", "SiOC", "Al2O3"
            ]),
        }

    async def get_supported_recipes(self) -> List[str]:
        """获取支持的配方列表

        Returns:
            配方ID列表
        """
        return list(self._recipes.keys())

    # ========== CVD设备特定方法 ==========

    async def set_gas_flows(self, chamber_id: str, flows: Dict[str, float]) -> None:
        """设置气体流量

        Args:
            chamber_id: 腔体ID
            flows: 气体流量字典 {gas_name: sccm}
        """
        self._gas_flows[chamber_id] = flows
        logger.debug("gas_flows_set", chamber_id=chamber_id, flows=flows)

    async def get_gas_flows(self, chamber_id: str) -> Dict[str, float]:
        """获取气体流量

        Args:
            chamber_id: 腔体ID

        Returns:
            气体流量字典
        """
        return self._gas_flows.get(chamber_id, {})

    async def set_temperature(self, zone: str, temperature: float) -> None:
        """设置温度

        Args:
            zone: 温区标识
            temperature: 温度值 (摄氏度)
        """
        self._temperature_zones[zone] = temperature
        logger.debug("temperature_set", zone=zone, temperature=temperature)

    async def get_temperatures(self) -> Dict[str, float]:
        """获取所有温区温度

        Returns:
            温度字典
        """
        return self._temperature_zones.copy()

    async def set_pressure(self, pressure: float) -> None:
        """设置压力

        Args:
            pressure: 压力值 (torr)
        """
        self._pressure = pressure
        logger.debug("pressure_set", pressure=pressure)

    async def get_pressure(self) -> float:
        """获取压力

        Returns:
            压力值 (torr)
        """
        return self._pressure

    async def set_rf_power(self, power: float) -> None:
        """设置RF功率

        Args:
            power: 功率值 (W)
        """
        self._rf_power = power
        logger.debug("rf_power_set", power=power)

    async def get_rf_power(self) -> float:
        """获取RF功率

        Returns:
            功率值 (W)
        """
        return self._rf_power

    async def trigger_in_situ_cleaning(self, chamber_id: str) -> bool:
        """触发原位清洗

        Args:
            chamber_id: 腔体ID

        Returns:
            是否成功
        """
        logger.info("in_situ_cleaning_triggered", chamber_id=chamber_id)
        return True
