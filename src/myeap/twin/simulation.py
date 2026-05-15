"""What-If仿真模块

提供工艺场景的假设分析功能，包括：
- 基于数字孪生当前状态的仿真运行
- 工艺参数调整的后果预测
- 风险评估和约束检查
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from myeap.twin.digital_twin import DigitalTwin
from myeap.twin.models import (
    RiskLevel,
    SimulationResult,
    SimulationScenario,
    SimulationStep,
    TwinState,
)

logger = logging.getLogger(__name__)


class ProcessSimulator:
    """工艺仿真器

    基于数字孪生状态运行What-If仿真，评估工艺参数调整的潜在影响。

    支持的仿真类型：
    - 参数灵敏度分析：改变单个参数观察影响
    - 退化模拟：模拟设备劣化过程
    - 工艺优化：寻找最优工艺窗口

    Attributes:
        twin: 关联的数字孪生实例
        on_step: 步骤完成回调
        default_step_interval: 默认仿真步长（秒）

    Example:
        dt = DigitalTwin()
        sim = ProcessSimulator(dt)
        scenario = SimulationScenario(
            scenario_id="what-if-1", name="Increase Temperature",
            equipment_id="eq-001", parameters={"Temperature": 1.1},
            duration=600
        )
        result = await sim.simulate("eq-001", scenario)
    """

    def __init__(
        self,
        digital_twin: DigitalTwin,
        default_step_interval: float = 60.0,
    ):
        """初始化仿真器

        Args:
            digital_twin: 数字孪生实例
            default_step_interval: 默认仿真步长（秒）
        """
        self.twin = digital_twin
        self.default_step_interval = default_step_interval

        # 工艺模型参数 -> 响应函数
        self._process_models: Dict[str, Callable] = {}

        # 步骤回调
        self._on_step: Optional[Callable[[SimulationStep], Any]] = None

        # 统计数据
        self._simulation_count: int = 0

        logger.info(
            f"ProcessSimulator initialized (step_interval={default_step_interval}s)"
        )

    def set_on_step(self, callback: Callable[[SimulationStep], Any]) -> None:
        """设置步骤完成回调

        Args:
            callback: 回调函数，接收 SimulationStep 参数
        """
        self._on_step = callback

    def register_process_model(
        self,
        process_type: str,
        model_func: Callable[[Dict[str, float], Dict[str, Any]], Dict[str, float]],
    ) -> None:
        """注册工艺模型

        工艺模型是一个函数，接收当前状态和参数，返回下一步状态。

        Args:
            process_type: 工艺类型名称
            model_func: 模型函数 (current_state, params) -> next_state
        """
        self._process_models[process_type] = model_func
        logger.debug(f"Registered process model: {process_type}")

    def unregister_process_model(self, process_type: str) -> bool:
        """移除工艺模型

        Args:
            process_type: 工艺类型名称

        Returns:
            bool: 是否成功移除
        """
        if process_type in self._process_models:
            del self._process_models[process_type]
            return True
        return False

    async def simulate(
        self,
        equipment_id: str,
        scenario: SimulationScenario,
    ) -> SimulationResult:
        """运行What-If仿真

        基于数字孪生当前状态，使用仿真场景运行假设分析。

        Args:
            equipment_id: 设备ID
            scenario: 仿真场景定义

        Returns:
            SimulationResult: 仿真结果

        Raises:
            ValueError: 如果设备ID不存在或场景参数无效
        """
        # 获取当前状态
        twin = self.twin.get_twin(equipment_id)
        if not twin:
            raise ValueError(f"No twin for equipment '{equipment_id}'")

        if scenario.equipment_id != equipment_id:
            raise ValueError(
                f"Scenario equipment_id '{scenario.equipment_id}' "
                f"does not match '{equipment_id}'"
            )

        started_at = datetime.now(timezone.utc)
        current_state = dict(twin.sensor_data)
        step_interval = scenario.step_interval or self.default_step_interval
        step_count = scenario.step_count

        # 获取工艺模型（如果有注册的话）
        process_type = scenario.metadata.get("process_type", "default")
        model_func = self._process_models.get(process_type)

        steps: List[SimulationStep] = []
        events: List[Dict[str, Any]] = []

        for step_index in range(step_count):
            timestamp = started_at + timedelta(seconds=step_interval * step_index)

            # 计算当前步状态
            if model_func:
                # 使用注册的工艺模型
                current_state = model_func(current_state, scenario.parameters)
            else:
                # 默认模型：参数乘性叠加
                current_state = self._default_model(
                    current_state, scenario.parameters, step_index
                )

            # 检查约束条件
            step_events = self._check_constraints(
                current_state, scenario.constraints, step_index
            )
            events.extend(step_events)

            step = SimulationStep(
                time_offset=step_interval * step_index,
                timestamp=timestamp,
                parameters=dict(current_state),
                events=step_events,
            )
            steps.append(step)

            # 触发步骤回调
            if self._on_step:
                try:
                    self._on_step(step)
                except Exception as e:
                    logger.error(f"Error in step callback: {e}")

        # 评估风险
        risk_assessment = self._assess_risks(steps, scenario.constraints)

        # 生成摘要
        summary = self._generate_summary(steps, risk_assessment)

        completed_at = datetime.now(timezone.utc)
        self._simulation_count += 1

        result = SimulationResult(
            scenario=scenario.to_sim_dict(),
            steps=steps,
            predicted_outcomes=[s.parameters for s in steps],
            risk_assessment=risk_assessment,
            summary=summary,
            started_at=started_at,
            completed_at=completed_at,
        )

        logger.info(
            f"Simulation completed: {scenario.scenario_id} "
            f"({step_count} steps, risk={risk_assessment.get('level', 'none')})"
        )
        return result

    def simulate_sync(
        self,
        equipment_id: str,
        scenario: SimulationScenario,
    ) -> SimulationResult:
        """运行What-If仿真（同步版本）

        Args:
            equipment_id: 设备ID
            scenario: 仿真场景定义

        Returns:
            SimulationResult: 仿真结果
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.simulate(equipment_id, scenario))
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, self.simulate(equipment_id, scenario)
                )
                return future.result()

    async def simulate_batch(
        self,
        equipment_id: str,
        scenarios: List[SimulationScenario],
    ) -> List[SimulationResult]:
        """批量运行多个仿真场景

        Args:
            equipment_id: 设备ID
            scenarios: 场景列表

        Returns:
            List[SimulationResult]: 各场景的仿真结果
        """
        import asyncio

        tasks = [self.simulate(equipment_id, s) for s in scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(
                    f"Simulation failed for scenario '{scenarios[i].scenario_id}': {r}"
                )
                valid_results.append(
                    SimulationResult(
                        scenario=scenarios[i].to_sim_dict(),
                        summary={"error": str(r)},
                    )
                )
            else:
                valid_results.append(r)

        return valid_results

    async def run_sensitivity_analysis(
        self,
        equipment_id: str,
        parameter: str,
        base_value: float,
        variations: List[float],
        duration: float = 3600.0,
    ) -> List[SimulationResult]:
        """运行参数灵敏度分析

        对单个参数在不同变化幅度下进行仿真，
        分析参数对结果的影响程度。

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            base_value: 参数基准值
            variations: 变化因子列表，如 [0.8, 0.9, 1.0, 1.1, 1.2]
            duration: 仿真时长

        Returns:
            List[SimulationResult]: 各变体的仿真结果
        """
        scenarios = []
        for i, factor in enumerate(variations):
            scenario = SimulationScenario(
                scenario_id=f"sensitivity-{parameter}-{i}",
                name=f"Sensitivity: {parameter} x{factor}",
                equipment_id=equipment_id,
                parameters={parameter: factor},
                duration=duration,
                metadata={"analysis_type": "sensitivity", "parameter": parameter},
            )
            scenarios.append(scenario)

        return await self.simulate_batch(equipment_id, scenarios)

    # --- 内部方法 ---

    def _default_model(
        self,
        current_state: Dict[str, float],
        parameters: Dict[str, Any],
        step_index: int,
    ) -> Dict[str, float]:
        """默认仿真模型

        使用乘性因子逐步调整参数值。

        Args:
            current_state: 当前状态
            parameters: 场景参数（乘性因子）
            step_index: 当前步索引

        Returns:
            Dict[str, float]: 下一步状态
        """
        result = dict(current_state)
        for key, factor in parameters.items():
            if key in current_state:
                if isinstance(factor, (int, float)) and 0 < factor < 10:
                    # 乘性因子：逐步应用
                    current_value = current_state[key]
                    target_value = current_value * factor
                    progress = min(1.0, (step_index + 1) / max(1, len(result)))
                    result[key] = current_value + (target_value - current_value) * progress * 0.1
                elif isinstance(factor, (int, float)):
                    # 绝对偏移
                    current_value = current_state[key]
                    result[key] = current_value + factor * min(1.0, (step_index + 1) / 60.0)
                else:
                    # 固定值
                    result[key] = float(factor)
        return result

    def _check_constraints(
        self,
        state: Dict[str, float],
        constraints: Dict[str, Any],
        step_index: int,
    ) -> List[Dict[str, Any]]:
        """检查约束条件

        Args:
            state: 当前状态
            constraints: 约束条件字典
            step_index: 当前步索引

        Returns:
            List[Dict[str, Any]]: 约束违反事件列表
        """
        events = []

        # 检查参数上限
        for key, max_val in constraints.get("max_values", {}).items():
            if key in state and state[key] > max_val:
                events.append(
                    {
                        "type": "constraint_violation",
                        "severity": "warning",
                        "parameter": key,
                        "value": state[key],
                        "limit": max_val,
                        "step": step_index,
                        "message": f"Parameter '{key}' exceeds maximum: {state[key]} > {max_val}",
                    }
                )

        # 检查参数下限
        for key, min_val in constraints.get("min_values", {}).items():
            if key in state and state[key] < min_val:
                events.append(
                    {
                        "type": "constraint_violation",
                        "severity": "warning",
                        "parameter": key,
                        "value": state[key],
                        "limit": min_val,
                        "step": step_index,
                        "message": f"Parameter '{key}' below minimum: {state[key]} < {min_val}",
                    }
                )

        # 检查安全限值
        for key, limit_val in constraints.get("safety_limits", {}).items():
            if key in state and state[key] > limit_val:
                events.append(
                    {
                        "type": "safety_violation",
                        "severity": "critical",
                        "parameter": key,
                        "value": state[key],
                        "limit": limit_val,
                        "step": step_index,
                        "message": f"SAFETY: Parameter '{key}' exceeds safety limit: {state[key]} > {limit_val}",
                    }
                )

        return events

    def _assess_risks(
        self,
        steps: List[SimulationStep],
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        """评估仿真风险

        Args:
            steps: 仿真步骤列表
            constraints: 约束条件

        Returns:
            Dict[str, Any]: 风险评估结果
        """
        if not steps:
            return {"level": RiskLevel.NONE.value, "score": 0.0, "details": []}

        # 统计事件
        total_events = 0
        critical_events = 0
        warning_events = 0
        violated_params = set()

        for step in steps:
            for event in step.events:
                total_events += 1
                if event.get("severity") == "critical":
                    critical_events += 1
                elif event.get("severity") == "warning":
                    warning_events += 1
                violated_params.add(event.get("parameter", ""))

        # 计算风险评分
        if critical_events > 0:
            risk_level = RiskLevel.CRITICAL
            risk_score = min(1.0, 0.8 + critical_events * 0.05)
        elif warning_events > len(steps) * 0.5:
            risk_level = RiskLevel.HIGH
            risk_score = 0.6 + min(0.3, warning_events * 0.02)
        elif warning_events > 0:
            risk_level = RiskLevel.MEDIUM
            risk_score = 0.3 + min(0.3, warning_events * 0.03)
        elif total_events > 0:
            risk_level = RiskLevel.LOW
            risk_score = 0.1
        else:
            risk_level = RiskLevel.NONE
            risk_score = 0.0

        # 计算参数变化幅度
        param_variations = {}
        if len(steps) >= 2:
            first = steps[0].parameters
            last = steps[-1].parameters
            for key in first:
                if key in last and first[key] != 0:
                    variation = abs(last[key] - first[key]) / abs(first[key])
                    param_variations[key] = round(variation, 4)

        return {
            "level": risk_level.value,
            "score": round(risk_score, 4),
            "total_events": total_events,
            "critical_events": critical_events,
            "warning_events": warning_events,
            "violated_parameters": list(violated_params),
            "param_variations": param_variations,
            "details": f"Risk={risk_level.value}, score={risk_score:.2f}, "
            f"events={total_events} (critical={critical_events}, warning={warning_events})",
        }

    def _generate_summary(
        self,
        steps: List[SimulationStep],
        risk_assessment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """生成仿真摘要

        Args:
            steps: 仿真步骤列表
            risk_assessment: 风险评估结果

        Returns:
            Dict[str, Any]: 摘要信息
        """
        if not steps:
            return {"total_steps": 0}

        initial = steps[0].parameters
        final = steps[-1].parameters

        # 参数变化
        changes = {}
        for key in final:
            if key in initial:
                changes[key] = {
                    "initial": initial[key],
                    "final": final[key],
                    "delta": round(final[key] - initial[key], 4),
                }

        return {
            "total_steps": len(steps),
            "initial_parameters": initial,
            "final_parameters": final,
            "parameter_changes": changes,
            "risk_level": risk_assessment.get("level", "none"),
            "risk_score": risk_assessment.get("score", 0.0),
            "total_events": risk_assessment.get("total_events", 0),
        }

    @property
    def simulation_count(self) -> int:
        """仿真次数"""
        return self._simulation_count

    @property
    def registered_models(self) -> List[str]:
        """已注册的工艺模型列表"""
        return list(self._process_models.keys())

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "simulation_count": self._simulation_count,
            "registered_models": self.registered_models,
            "default_step_interval": self.default_step_interval,
        }

    def reset(self) -> None:
        """重置仿真器"""
        self._process_models.clear()
        self._simulation_count = 0
        logger.info("ProcessSimulator reset")
