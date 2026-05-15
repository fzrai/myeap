"""设备插件基类

定义设备插件的接口，所有设备类型插件都应实现此接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from myeap.core.logging import get_logger
from myeap.observability.tracing import trace_async, create_span

logger = get_logger(__name__)


class EquipmentPlugin(ABC):
    """设备插件基类

    所有设备类型都应实现此接口。
    插件负责：
    - 设备特定的消息处理
    - 工艺流程控制
    - 设备特定的状态转换
    - 配方管理

    Example:
        class MyEquipmentPlugin(EquipmentPlugin):
            @property
            def equipment_type(self) -> str:
                return "my_equipment"

            async def initialize(self, config: Dict[str, Any]) -> None:
                self._config = config

            # ... 实现其他抽象方法
    """

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._initialized = False
        self._equipment_id: Optional[str] = None

    @property
    @abstractmethod
    def equipment_type(self) -> str:
        """设备类型"""
        pass

    @property
    def equipment_id(self) -> Optional[str]:
        """获取关联的设备ID"""
        return self._equipment_id

    @equipment_id.setter
    def equipment_id(self, value: str) -> None:
        """设置关联的设备ID"""
        self._equipment_id = value

    @property
    def is_initialized(self) -> bool:
        """插件是否已初始化"""
        return self._initialized

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件

        Args:
            config: 插件配置
        """
        pass

    @abstractmethod
    async def on_connected(self) -> None:
        """连接建立回调

        当设备连接成功建立时调用。
        """
        pass

    @abstractmethod
    async def on_disconnected(self) -> None:
        """连接断开回调

        当设备连接断开时调用。
        """
        pass

    @abstractmethod
    async def handle_message(self, message: Any) -> Optional[Any]:
        """处理设备消息

        Args:
            message: 接收到的设备消息

        Returns:
            响应消息，如果没有响应则返回None
        """
        pass

    @abstractmethod
    async def start_process(
        self,
        recipe_id: str,
        chamber_id: str,
        params: Dict[str, Any],
    ) -> str:
        """启动工艺

        Args:
            recipe_id: 配方ID
            chamber_id: 腔体ID
            params: 工艺参数

        Returns:
            工艺实例ID
        """
        pass

    @abstractmethod
    async def pause_process(self, process_id: str) -> bool:
        """暂停工艺

        Args:
            process_id: 工艺实例ID

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def resume_process(self, process_id: str) -> bool:
        """恢复工艺

        Args:
            process_id: 工艺实例ID

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def abort_process(self, process_id: str) -> bool:
        """中止工艺

        Args:
            process_id: 工艺实例ID

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def get_process_status(self, process_id: str) -> Dict[str, Any]:
        """获取工艺状态

        Args:
            process_id: 工艺实例ID

        Returns:
            工艺状态信息
        """
        pass

    async def on_alarm(self, alarm: Dict[str, Any]) -> None:
        """报警回调

        Args:
            alarm: 报警信息
        """
        logger.warning(
            "equipment_alarm",
            equipment_id=self._equipment_id,
            alarm_id=alarm.get("id"),
            severity=alarm.get("severity"),
            message=alarm.get("message"),
        )

    async def validate_recipe(self, recipe: Dict[str, Any]) -> bool:
        """验证配方

        Args:
            recipe: 配方数据

        Returns:
            验证是否通过
        """
        return True

    async def get_capabilities(self) -> Dict[str, Any]:
        """获取设备能力

        Returns:
            设备能力字典
        """
        return {}

    async def get_supported_recipes(self) -> List[str]:
        """获取支持的配方列表

        Returns:
            配方ID列表
        """
        return []

    async def cleanup(self) -> None:
        """清理资源

        当插件被卸载时调用，用于清理资源。
        """
        self._initialized = False
        logger.info("plugin_cleaned_up", equipment_type=self.equipment_type)


class PluginRegistry:
    """插件注册表

    管理所有设备类型插件。
    """

    def __init__(self):
        self._plugins: Dict[str, EquipmentPlugin] = {}
        self._lock = None  # 简化实现，实际应使用asyncio.Lock

    def register(self, plugin: EquipmentPlugin) -> None:
        """注册插件

        Args:
            plugin: 设备插件实例
        """
        self._plugins[plugin.equipment_type] = plugin
        logger.info("plugin_registered", equipment_type=plugin.equipment_type)

    def unregister(self, equipment_type: str) -> None:
        """注销插件

        Args:
            equipment_type: 设备类型
        """
        if equipment_type in self._plugins:
            del self._plugins[equipment_type]
            logger.info("plugin_unregistered", equipment_type=equipment_type)

    def get(self, equipment_type: str) -> Optional[EquipmentPlugin]:
        """获取插件

        Args:
            equipment_type: 设备类型

        Returns:
            插件实例或None
        """
        return self._plugins.get(equipment_type)

    def get_all(self) -> Dict[str, EquipmentPlugin]:
        """获取所有插件"""
        return self._plugins.copy()

    def get_supported_types(self) -> List[str]:
        """获取支持的设备类型"""
        return list(self._plugins.keys())
