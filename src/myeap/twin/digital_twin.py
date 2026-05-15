"""数字孪生核心模块

提供设备虚拟镜像的核心功能，包括：
- 虚拟状态创建和同步
- 传感器数据EWMA平滑
- 状态趋势预测
- 健康评估和异常检测
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from myeap.twin.models import (
    HealthStatus,
    TwinEvent,
    TwinHealth,
    TwinState,
)

logger = logging.getLogger(__name__)


class DigitalTwin:
    """数字孪生核心

    维护物理设备的虚拟镜像，支持实时状态同步、趋势预测和健康评估。

    Attributes:
        on_event: 事件回调函数
        max_history: 每个设备最大历史记录数

    Example:
        dt = DigitalTwin()
        twin = await dt.create_twin("eq-001", {"chambers": {}, "status": "IDLE"})
        updated = await dt.sync_state("eq-001", {"Temperature": 25.0, "Pressure": 1.0})
        health = await dt.assess_health("eq-001")
    """

    def __init__(
        self,
        max_history: int = 10000,
        smoothing_factor: float = 0.3,
        min_history_for_prediction: int = 10,
        prediction_window: int = 50,
        anomaly_z_threshold: float = 2.0,
    ):
        """初始化数字孪生

        Args:
            max_history: 每个设备最大历史记录数
            smoothing_factor: EWMA平滑因子 (0-1)
            min_history_for_prediction: 预测所需最小历史记录数
            prediction_window: 趋势计算窗口大小
            anomaly_z_threshold: 异常检测Z分数阈值
        """
        self.max_history = max_history
        self.smoothing_factor = max(0.0, min(1.0, smoothing_factor))
        self.min_history_for_prediction = min_history_for_prediction
        self.prediction_window = prediction_window
        self.anomaly_z_threshold = anomaly_z_threshold

        # 当前状态
        self._twins: Dict[str, TwinState] = {}

        # 历史记录
        self._history: Dict[str, List[TwinState]] = {}

        # 退化模型
        self._models: Dict[str, Dict[str, Any]] = {}

        # 事件回调
        self._on_event: Optional[Callable[[TwinEvent], Any]] = None
        self._on_event_async: Optional[Callable[[TwinEvent], Any]] = None

        # 统计数据
        self._sync_count: int = 0
        self._prediction_count: int = 0
        self._health_check_count: int = 0

        logger.info(
            f"DigitalTwin initialized (max_history={max_history}, "
            f"smoothing={smoothing_factor}, anomaly_threshold={anomaly_z_threshold})"
        )

    def set_on_event(
        self,
        callback: Callable[[TwinEvent], Any],
        async_callback: bool = False,
    ) -> None:
        """设置事件回调

        Args:
            callback: 回调函数
            async_callback: 是否为异步回调
        """
        if async_callback:
            self._on_event_async = callback
        else:
            self._on_event = callback

    async def create_twin(
        self,
        equipment_id: str,
        initial_state: Dict[str, Any],
    ) -> TwinState:
        """创建数字孪生

        为指定设备创建一个新的数字孪生实例。

        Args:
            equipment_id: 设备ID
            initial_state: 初始状态字典，包含 chambers, status, sensor_data 等

        Returns:
            TwinState: 创建的数字孪生状态

        Raises:
            ValueError: 如果设备ID已存在
        """
        if equipment_id in self._twins:
            raise ValueError(f"Twin already exists for equipment '{equipment_id}'")

        twin = TwinState(
            equipment_id=equipment_id,
            timestamp=datetime.now(timezone.utc),
            chambers=initial_state.get("chambers", {}),
            status=initial_state.get("status", "UNKNOWN"),
            sub_status=initial_state.get("sub_status"),
            sensor_data=initial_state.get("sensor_data", {}),
            metadata=initial_state.get("metadata", {}),
        )
        self._twins[equipment_id] = twin
        self._history[equipment_id] = [twin]

        logger.info(f"Created digital twin for equipment '{equipment_id}'")
        await self._emit_event("twin_created", equipment_id, {"status": twin.status})
        return twin

    async def remove_twin(self, equipment_id: str) -> bool:
        """移除数字孪生

        Args:
            equipment_id: 设备ID

        Returns:
            bool: 是否成功移除
        """
        if equipment_id not in self._twins:
            return False

        del self._twins[equipment_id]
        self._history.pop(equipment_id, None)
        self._models.pop(equipment_id, None)

        logger.info(f"Removed digital twin for equipment '{equipment_id}'")
        await self._emit_event("twin_removed", equipment_id, {})
        return True

    def get_twin(self, equipment_id: str) -> Optional[TwinState]:
        """获取数字孪生当前状态

        Args:
            equipment_id: 设备ID

        Returns:
            Optional[TwinState]: 数字孪生状态，不存在时返回 None
        """
        return self._twins.get(equipment_id)

    def get_history(
        self,
        equipment_id: str,
        limit: Optional[int] = None,
    ) -> List[TwinState]:
        """获取数字孪生历史记录

        Args:
            equipment_id: 设备ID
            limit: 返回的记录数量限制（最新的N条）

        Returns:
            List[TwinState]: 历史状态列表
        """
        history = self._history.get(equipment_id, [])
        if limit is not None:
            return history[-limit:]
        return list(history)

    def get_twin_ids(self) -> List[str]:
        """获取所有数字孪生设备ID

        Returns:
            List[str]: 设备ID列表
        """
        return list(self._twins.keys())

    async def sync_state(
        self,
        equipment_id: str,
        sensor_data: Dict[str, float],
        status: Optional[str] = None,
        sub_status: Optional[str] = None,
        chambers: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> TwinState:
        """同步物理设备状态到数字孪生

        使用EWMA（指数加权移动平均）平滑传感器数据，
        减少噪声影响。

        Args:
            equipment_id: 设备ID
            sensor_data: 传感器数据字典
            status: 设备状态（可选）
            sub_status: 子状态（可选）
            chambers: 腔体状态（可选）

        Returns:
            TwinState: 更新后的数字孪生状态

        Raises:
            ValueError: 如果设备ID不存在
        """
        twin = self._twins.get(equipment_id)
        if not twin:
            raise ValueError(f"No twin for equipment '{equipment_id}'")

        # EWMA平滑传感器数据
        alpha = self.smoothing_factor
        for key, value in sensor_data.items():
            old_value = twin.sensor_data.get(key, value)
            twin.sensor_data[key] = alpha * value + (1 - alpha) * old_value

        # 更新时间戳
        twin.timestamp = datetime.now(timezone.utc)

        # 更新状态
        if status is not None:
            twin.status = status
        if sub_status is not None:
            twin.sub_status = sub_status

        # 更新腔体状态
        if chambers is not None:
            for chamber_id, params in chambers.items():
                if chamber_id not in twin.chambers:
                    twin.chambers[chamber_id] = {}
                twin.chambers[chamber_id].update(params)

        # 追加历史记录
        history = self._history.setdefault(equipment_id, [])
        snapshot = TwinState(
            equipment_id=twin.equipment_id,
            timestamp=twin.timestamp,
            chambers={k: dict(v) for k, v in twin.chambers.items()},
            status=twin.status,
            sub_status=twin.sub_status,
            alarms=list(twin.alarms),
            sensor_data=dict(twin.sensor_data),
            metadata=dict(twin.metadata),
        )
        history.append(snapshot)
        if len(history) > self.max_history:
            self._history[equipment_id] = history[-self.max_history:]

        self._sync_count += 1
        logger.debug(f"Synced state for '{equipment_id}': {len(sensor_data)} parameters")
        return twin

    def sync_state_sync(
        self,
        equipment_id: str,
        sensor_data: Dict[str, float],
        status: Optional[str] = None,
        sub_status: Optional[str] = None,
        chambers: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> TwinState:
        """同步状态（同步版本）

        Args:
            equipment_id: 设备ID
            sensor_data: 传感器数据字典
            status: 设备状态（可选）
            sub_status: 子状态（可选）
            chambers: 腔体状态（可选）

        Returns:
            TwinState: 更新后的数字孪生状态
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.sync_state(equipment_id, sensor_data, status, sub_status, chambers)
            )
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.sync_state(equipment_id, sensor_data, status, sub_status, chambers),
                )
                return future.result()

    async def predict_next_state(
        self,
        equipment_id: str,
        horizon: int = 1,
        parameters: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """预测未来状态

        基于历史趋势线性外推预测未来N步的状态。

        Args:
            equipment_id: 设备ID
            horizon: 预测步数
            parameters: 要预测的参数列表，None表示所有参数

        Returns:
            List[Dict[str, Any]]: 预测结果列表，每项包含 time_offset 和 values
        """
        twin = self._twins.get(equipment_id)
        history = self._history.get(equipment_id, [])

        if len(history) < self.min_history_for_prediction:
            return []

        # 确定预测参数
        pred_params = parameters if parameters else list(twin.sensor_data.keys())
        if not pred_params:
            return []

        current = dict(twin.sensor_data)
        predictions = []

        for step in range(horizon):
            next_values = {}
            for key in pred_params:
                trend = self._calculate_trend(equipment_id, key)
                current_value = current.get(key, 0.0)
                next_values[key] = current_value + trend * (step + 1)

                # 物理约束：温度不低于绝对零度，压力不高于上限等
                next_values[key] = self._apply_physical_constraints(key, next_values[key])

            predictions.append(
                {
                    "time_offset": step + 1,
                    "values": {k: round(v, 4) for k, v in next_values.items()},
                }
            )

        self._prediction_count += 1
        await self._emit_event(
            "prediction_completed",
            equipment_id,
            {"horizon": horizon, "parameters": pred_params},
        )
        return predictions

    def predict_next_state_sync(
        self,
        equipment_id: str,
        horizon: int = 1,
        parameters: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """预测未来状态（同步版本）

        Args:
            equipment_id: 设备ID
            horizon: 预测步数
            parameters: 要预测的参数列表

        Returns:
            List[Dict[str, Any]]: 预测结果列表
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.predict_next_state(equipment_id, horizon, parameters)
            )
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.predict_next_state(equipment_id, horizon, parameters),
                )
                return future.result()

    async def assess_health(self, equipment_id: str) -> TwinHealth:
        """评估设备健康状态

        基于传感器数据与历史基线的偏差评估设备健康度。

        对每个传感器参数计算Z分数，超过阈值的标记为异常。
        综合评分取所有参数的最低分（木桶原理）。

        Args:
            equipment_id: 设备ID

        Returns:
            TwinHealth: 健康评估结果
        """
        twin = self._twins.get(equipment_id)
        history = self._history.get(equipment_id, [])

        if not twin or not history:
            health = TwinHealth(
                equipment_id=equipment_id,
                overall_score=100.0,
                confidence=1.0,
            )
            self._health_check_count += 1
            return health

        scores: Dict[str, float] = {}
        anomalies: List[dict] = []
        recommendations: List[str] = []

        # 用于计算置信度的数据点数量
        data_points = 0

        for key, current_value in twin.sensor_data.items():
            # 提取历史值
            values = [
                h.sensor_data[key]
                for h in history[-self.prediction_window:]
                if key in h.sensor_data
            ]

            if len(values) < 3:
                # 数据不足，默认为健康
                scores[key] = 90.0
                data_points += len(values)
                continue

            data_points += len(values)
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std = variance**0.5

            if std > 0:
                z_score = abs(current_value - mean) / std
                # 健康评分：Z分数越低越健康，使用sigmoid-like衰减
                health_score = max(0.0, 100.0 - z_score * 20.0)
                scores[key] = round(min(100.0, health_score), 2)

                if z_score > self.anomaly_z_threshold:
                    anomalies.append(
                        {
                            "parameter": key,
                            "z_score": round(z_score, 4),
                            "current_value": current_value,
                            "expected": round(mean, 4),
                            "std": round(std, 4),
                        }
                    )
                    recommendations.append(
                        f"Check {key}: deviates {z_score:.1f} sigma from normal "
                        f"(current={current_value:.4f}, expected={mean:.4f})"
                    )
            else:
                # 无方差，认为稳定
                scores[key] = 100.0

        # 综合评分：取最低分（木桶原理）
        overall = min(scores.values()) if scores else 100.0

        # 计算置信度：基于数据量
        min_data = self.min_history_for_prediction
        confidence = min(1.0, data_points / max(1, len(scores) * min_data))

        health = TwinHealth(
            equipment_id=equipment_id,
            overall_score=round(overall, 2),
            component_scores=scores,
            anomalies=anomalies,
            recommendations=recommendations,
            assessed_at=datetime.now(timezone.utc),
            confidence=round(confidence, 4),
        )

        self._health_check_count += 1
        if anomalies:
            await self._emit_event(
                "health_anomaly_detected",
                equipment_id,
                {"anomalies_count": len(anomalies), "overall_score": overall},
            )

        return health

    def assess_health_sync(self, equipment_id: str) -> TwinHealth:
        """评估设备健康状态（同步版本）

        Args:
            equipment_id: 设备ID

        Returns:
            TwinHealth: 健康评估结果
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.assess_health(equipment_id))
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.assess_health(equipment_id))
                return future.result()

    def set_degradation_model(
        self,
        equipment_id: str,
        parameter: str,
        model_params: Dict[str, Any],
    ) -> None:
        """设置退化模型

        为指定设备的参数设置退化模型，用于更准确的趋势预测。

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            model_params: 模型参数，如 {"rate": 0.001, "type": "linear"}
        """
        if equipment_id not in self._models:
            self._models[equipment_id] = {}
        self._models[equipment_id][parameter] = model_params
        logger.debug(
            f"Set degradation model for {equipment_id}.{parameter}: {model_params}"
        )

    def get_degradation_model(
        self,
        equipment_id: str,
        parameter: str,
    ) -> Optional[Dict[str, Any]]:
        """获取退化模型

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            Optional[Dict[str, Any]]: 模型参数
        """
        return self._models.get(equipment_id, {}).get(parameter)

    def remove_degradation_model(
        self,
        equipment_id: str,
        parameter: str,
    ) -> bool:
        """移除退化模型

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            bool: 是否成功移除
        """
        if equipment_id in self._models and parameter in self._models[equipment_id]:
            del self._models[equipment_id][parameter]
            return True
        return False

    # --- 内部方法 ---

    def _calculate_trend(self, equipment_id: str, parameter: str) -> float:
        """计算参数的线性趋势

        使用最小二乘法拟合最近N个数据点的线性趋势。

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            float: 趋势斜率（每个时间步的变化量）
        """
        history = self._history.get(equipment_id, [])
        values = [
            h.sensor_data[parameter]
            for h in history[-self.prediction_window:]
            if parameter in h.sensor_data
        ]

        if len(values) < self.min_history_for_prediction:
            # 数据不足，使用退化模型（如果有）
            model = self._models.get(equipment_id, {}).get(parameter, {})
            if model.get("type") == "linear":
                return model.get("rate", 0.0)
            return 0.0

        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _apply_physical_constraints(self, parameter: str, value: float) -> float:
        """应用物理约束

        确保预测值在合理的物理范围内。

        Args:
            parameter: 参数名称
            value: 预测值

        Returns:
            float: 约束后的值
        """
        param_lower = parameter.lower()

        # 温度约束：不低于 -273.15（绝对零度），不高于 2000
        if "temp" in param_lower:
            return max(-273.15, min(2000.0, value))

        # 压力约束：不低于 0
        if "pressure" in param_lower:
            return max(0.0, value)

        # 功率约束：不低于 0
        if "power" in param_lower or "rf" in param_lower:
            return max(0.0, value)

        # 流量约束：不低于 0
        if "flow" in param_lower:
            return max(0.0, value)

        return value

    async def _emit_event(
        self,
        event_type: str,
        equipment_id: str,
        data: Dict[str, Any],
    ) -> None:
        """发送事件

        Args:
            event_type: 事件类型
            equipment_id: 设备ID
            data: 事件数据
        """
        event = TwinEvent(
            event_type=event_type,
            equipment_id=equipment_id,
            data=data,
            timestamp=datetime.now(timezone.utc),
        )

        # 同步回调
        if self._on_event:
            try:
                self._on_event(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

        # 异步回调
        if self._on_event_async:
            try:
                result = self._on_event_async(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in async event callback: {e}")

    # --- 统计属性 ---

    @property
    def sync_count(self) -> int:
        """同步次数"""
        return self._sync_count

    @property
    def prediction_count(self) -> int:
        """预测次数"""
        return self._prediction_count

    @property
    def health_check_count(self) -> int:
        """健康检查次数"""
        return self._health_check_count

    @property
    def twin_count(self) -> int:
        """数字孪生数量"""
        return len(self._twins)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            Dict[str, Any]: 统计信息字典
        """
        return {
            "twin_count": self.twin_count,
            "sync_count": self._sync_count,
            "prediction_count": self._prediction_count,
            "health_check_count": self._health_check_count,
            "max_history": self.max_history,
            "smoothing_factor": self.smoothing_factor,
        }

    def reset(self) -> None:
        """重置所有状态"""
        self._twins.clear()
        self._history.clear()
        self._models.clear()
        self._sync_count = 0
        self._prediction_count = 0
        self._health_check_count = 0
        logger.info("DigitalTwin reset")
