"""数字孪生模块

提供设备虚拟镜像和仿真功能，包括：
- 数字孪生核心：实时传感器数据同步、虚拟状态维护
- 状态预测：基于历史趋势的未来状态预测
- 健康评估：设备健康度评分和异常检测
- What-If仿真：工艺场景假设分析和风险评估
"""

from myeap.twin.models import (
    TwinState,
    TwinHealth,
    HealthStatus,
    SimulationResult,
    SimulationScenario,
    SimulationStep,
    RiskLevel,
    TwinEvent,
)
from myeap.twin.digital_twin import DigitalTwin
from myeap.twin.simulation import ProcessSimulator

__all__ = [
    # Models
    "TwinState",
    "TwinHealth",
    "HealthStatus",
    "SimulationResult",
    "SimulationScenario",
    "SimulationStep",
    "RiskLevel",
    "TwinEvent",
    # Core
    "DigitalTwin",
    # Simulation
    "ProcessSimulator",
]

__version__ = "1.0.0"
