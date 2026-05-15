"""预测性维护模块

基于统计方法实现设备故障预测。

主要功能：
- 基于趋势分析预测设备剩余使用寿命(RUL)
- 基于多维特征识别早期故障征兆
- 支持在线学习更新模型

Example:
    >>> import numpy as np
    >>> from myeap.ai.predictive_maintenance import PredictiveMaintenance
    >>> pm = PredictiveMaintenance()
    >>> pm.train_baseline("eq-001", np.random.normal(100, 5, (100, 3)))
    >>> result = pm.predict_failure("eq-001", np.array([120, 105, 98]))
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np

from myeap.ai.models import FailurePrediction, MaintenanceRecommendation

logger = logging.getLogger(__name__)


@dataclass
class MaintenanceSchedule:
    """维护计划

    表示针对特定设备的计划性维护安排。

    Attributes:
        equipment_id: 设备标识
        scheduled_date: 计划日期
        maintenance_type: 维护类型 (preventive, corrective, condition-based)
        priority: 优先级
        actions: 维护动作列表
        estimated_downtime_hours: 预计停机时间
    """

    equipment_id: str
    scheduled_date: datetime
    maintenance_type: str = "preventive"
    priority: int = 3
    actions: List[str] = field(default_factory=list)
    estimated_downtime_hours: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "equipment_id": self.equipment_id,
            "scheduled_date": self.scheduled_date.isoformat(),
            "maintenance_type": self.maintenance_type,
            "priority": self.priority,
            "actions": self.actions,
            "estimated_downtime_hours": self.estimated_downtime_hours,
        }


def get_default_maintenance_recommendations(
    equipment_id: str,
    risk_factors: List[str],
) -> List[MaintenanceRecommendation]:
    """根据风险因素生成默认维护建议

    Args:
        equipment_id: 设备标识
        risk_factors: 风险因素列表

    Returns:
        List[MaintenanceRecommendation]: 维护建议列表
    """
    recommendations = []
    factor_action_map = {
        "temperature_high": ("检查冷却系统并校准温度传感器", "温度持续偏高"),
        "temperature_low": ("检查加热器工作状态", "温度持续偏低"),
        "pressure_high": ("检查压力调节阀和排气系统", "压力持续偏高"),
        "pressure_low": ("检查真空泵和密封系统", "压力持续偏低"),
        "flow_rate_anomaly": ("校准MFC并检查气路", "流量速率异常"),
        "vibration_high": ("检查机械部件和轴承", "振动偏高"),
        "power_drift": ("检查RF电源和匹配网络", "功率漂移"),
        "contamination": ("安排腔体清洗维护", "腔体污染迹象"),
        "sensor_noise": ("检查传感器连接和屏蔽", "传感器噪声增大"),
        "degradation_trend": ("计划预防性维护", "性能退化趋势"),
    }

    for i, factor in enumerate(risk_factors):
        for key, (action, reason) in factor_action_map.items():
            if key in factor.lower().replace(" ", "_"):
                recommendations.append(
                    MaintenanceRecommendation(
                        equipment_id=equipment_id,
                        priority=min(i + 1, 5),
                        action=action,
                        reason=reason,
                        estimated_duration_hours=2.0,
                    )
                )
                break

    return recommendations


class PredictiveMaintenance:
    """预测性维护引擎

    基于统计方法预测设备故障和维护需求。

    Attributes:
        rul_threshold: RUL阈值（小时），默认168小时(7天)
        degradation_rate_threshold: 退化速率阈值

    Example:
        >>> pm = PredictiveMaintenance(rul_threshold=168.0)
        >>> pm.train_baseline("eq-001", historical_data)
        >>> result = pm.predict_failure("eq-001", current_data)
    """

    def __init__(self, rul_threshold: float = 168.0):
        """初始化预测性维护引擎

        Args:
            rul_threshold: RUL阈值（小时），用于触发维护告警，默认7天
        """
        self.rul_threshold = rul_threshold
        self.degradation_rate_threshold = 0.01

        # 基线数据
        self._baselines: Dict[str, Dict[str, np.ndarray]] = {}

        # 趋势数据缓冲区
        self._trend_data: Dict[str, Deque[np.ndarray]] = defaultdict(
            lambda: deque(maxlen=500)
        )

        # 退化速率历史
        self._degradation_rates: Dict[str, List[float]] = defaultdict(list)

        # 建议映射
        self._recommendation_map: Dict[str, Tuple[str, str]] = {}

    def train_baseline(
        self,
        equipment_id: str,
        historical_data: np.ndarray,
        parameter_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """基于历史健康数据训练基线

        Args:
            equipment_id: 设备标识
            historical_data: 历史健康数据 (samples, features)
            parameter_names: 参数名称列表 (可选)

        Returns:
            Dict[str, Any]: 基线统计信息
        """
        if len(historical_data) == 0:
            raise ValueError("Historical data cannot be empty")

        data = np.asarray(historical_data, dtype=np.float64)

        # 计算统计基线
        mean = np.mean(data, axis=0)
        std = np.std(data, axis=0)

        # 多维数据计算协方差矩阵
        if data.ndim > 1 and data.shape[1] > 1:
            cov_matrix = np.cov(data.T)
        else:
            cov_matrix = np.array([[np.var(data)]]) if data.ndim > 1 else np.array([[np.var(data)]])

        # 计算数据范围
        data_min = np.min(data, axis=0) if data.ndim > 1 else np.min(data)
        data_max = np.max(data, axis=0) if data.ndim > 1 else np.max(data)

        self._baselines[equipment_id] = {
            "mean": mean,
            "std": std,
            "cov_matrix": cov_matrix,
            "min": data_min,
            "max": data_max,
            "sample_count": len(data),
            "parameter_names": parameter_names or [],
        }

        baseline_info = {
            "mean": mean.tolist() if hasattr(mean, "tolist") else float(mean),
            "std": std.tolist() if hasattr(std, "tolist") else float(std),
            "sample_count": len(data),
            "parameter_names": parameter_names or [],
        }

        logger.info(
            f"Baseline trained for {equipment_id}: {len(data)} samples, "
            f"{data.shape[1] if data.ndim > 1 else 1} parameters"
        )
        return baseline_info

    def update_baseline(
        self,
        equipment_id: str,
        new_data: np.ndarray,
        learning_rate: float = 0.1,
    ) -> None:
        """在线更新基线模型

        使用指数移动平均方式在线更新基线统计量。

        Args:
            equipment_id: 设备标识
            new_data: 新的健康数据
            learning_rate: 学习率 (0-1)

        Raises:
            ValueError: 如果基线尚未建立
        """
        if equipment_id not in self._baselines:
            raise ValueError(f"No baseline found for equipment {equipment_id}")

        baseline = self._baselines[equipment_id]
        data = np.asarray(new_data, dtype=np.float64)

        new_mean = np.mean(data, axis=0)
        new_std = np.std(data, axis=0)

        # 指数移动平均更新
        baseline["mean"] = (1 - learning_rate) * baseline["mean"] + learning_rate * new_mean
        baseline["std"] = (1 - learning_rate) * baseline["std"] + learning_rate * new_std

        logger.debug(f"Baseline updated for {equipment_id} with learning_rate={learning_rate}")

    def predict_failure(
        self,
        equipment_id: str,
        current_data: np.ndarray,
    ) -> FailurePrediction:
        """预测设备故障

        基于当前数据和历史基线预测故障概率和剩余使用寿命。

        Args:
            equipment_id: 设备标识
            current_data: 当前测量数据 (1D或2D array)

        Returns:
            FailurePrediction: 故障预测结果
        """
        baseline = self._baselines.get(equipment_id)

        if baseline is None:
            return FailurePrediction(
                equipment_id=equipment_id,
                failure_probability=0.0,
                predicted_failure_time=None,
                remaining_useful_life_hours=float("inf"),
                confidence_interval=(0.0, 0.0),
                risk_factors=[],
                recommended_actions=[],
            )

        data = np.asarray(current_data, dtype=np.float64).flatten()

        # 计算Z-score偏差
        std_safe = baseline["std"] + 1e-10
        if baseline["std"].ndim > 0:
            deviations = (data - baseline["mean"].flatten()[:len(data)]) / std_safe.flatten()[:len(data)]
        else:
            deviations = (data - baseline["mean"]) / std_safe

        max_deviation = float(np.max(np.abs(deviations)))

        # 故障概率 (sigmoid函数映射)
        failure_prob = 1.0 / (1.0 + np.exp(-(max_deviation - 3.0)))
        failure_prob = float(failure_prob)

        # 估计退化速率
        degradation_rate = self._estimate_degradation_rate(equipment_id, data)

        # 计算RUL
        if degradation_rate > self.degradation_rate_threshold:
            rul = min(self.rul_threshold / max(degradation_rate, 1e-10), self.rul_threshold * 10)
        else:
            rul = float("inf")

        # 预测失效时间
        if rul < float("inf") and rul < self.rul_threshold * 20:
            predicted_time = datetime.now() + timedelta(hours=float(rul))
        else:
            predicted_time = None

        # 计算置信区间
        ci_lower = max(0.0, failure_prob - 0.15)
        ci_upper = min(1.0, failure_prob + 0.15)

        # 识别风险因素
        risk_factors = self._identify_risk_factors(deviations, baseline)

        # 生成建议
        recommended_actions = self._generate_recommendations(
            equipment_id, risk_factors, failure_prob
        )

        # 存储趋势数据
        self._trend_data[equipment_id].append(data)

        return FailurePrediction(
            equipment_id=equipment_id,
            failure_probability=failure_prob,
            predicted_failure_time=predicted_time,
            remaining_useful_life_hours=float(rul),
            confidence_interval=(ci_lower, ci_upper),
            risk_factors=risk_factors,
            recommended_actions=recommended_actions,
        )

    def _estimate_degradation_rate(
        self,
        equipment_id: str,
        current_data: np.ndarray,
    ) -> float:
        """估计设备退化速率

        基于历史趋势和当前数据估计退化速率。

        Args:
            equipment_id: 设备标识
            current_data: 当前数据

        Returns:
            float: 退化速率
        """
        trend = self._trend_data.get(equipment_id)
        if trend is None or len(trend) < 2:
            return 0.0

        baseline = self._baselines.get(equipment_id)
        if baseline is None:
            return 0.0

        # 计算趋势中每个数据点的最大偏差
        mean_val = baseline["mean"]
        if hasattr(mean_val, "ndim") and mean_val.ndim > 0:
            recent_data = np.array(list(trend)[-20:])
            deviations = []
            for d in recent_data:
                m = mean_val.flatten()[:len(d)]
                s = (baseline["std"] + 1e-10).flatten()[:len(d)]
                dev = np.max(np.abs((d - m) / s))
                deviations.append(dev)
            deviations = np.array(deviations)
        else:
            recent_data = np.array(list(trend)[-20:])
            deviations = np.abs(recent_data.flatten() - float(mean_val)) / (float(baseline["std"]) + 1e-10)

        if len(deviations) < 2:
            return 0.0

        # 线性回归估计退化速率
        x = np.arange(len(deviations))
        slope = np.polyfit(x, deviations, 1)[0]
        rate = max(0.0, float(slope))

        self._degradation_rates[equipment_id].append(rate)
        return rate

    def _identify_risk_factors(
        self,
        deviations: np.ndarray,
        baseline: Dict[str, Any],
    ) -> List[str]:
        """识别风险因素

        根据参数偏差识别主要风险因素。

        Args:
            deviations: 各参数的Z-score偏差
            baseline: 基线统计信息

        Returns:
            List[str]: 风险因素列表
        """
        risk_factors = []
        param_names = baseline.get("parameter_names", [])

        # 定义参数与风险因素的映射
        risk_mapping = {
            "temperature": "temperature_anomaly",
            "temp": "temperature_anomaly",
            "pressure": "pressure_anomaly",
            "flow": "flow_rate_anomaly",
            "vibration": "vibration_high",
            "power": "power_drift",
            "rf": "power_drift",
            "current": "power_drift",
        }

        deviations_flat = np.atleast_1d(deviations).flatten()

        # 识别偏差最大的参数
        if len(deviations_flat) > 0:
            sorted_indices = np.argsort(np.abs(deviations_flat))[::-1]

            for idx in sorted_indices:
                if abs(deviations_flat[idx]) < 1.0:
                    break

                if param_names and idx < len(param_names):
                    param_name = param_names[idx].lower()
                    matched = False
                    for key, risk in risk_mapping.items():
                        if key in param_name:
                            direction = "high" if deviations_flat[idx] > 0 else "low"
                            risk_factors.append(f"{risk}_{direction}")
                            matched = True
                            break
                    if not matched:
                        direction = "high" if deviations_flat[idx] > 0 else "low"
                        risk_factors.append(f"{param_name}_{direction}")
                else:
                    direction = "high" if deviations_flat[idx] > 0 else "low"
                    risk_factors.append(f"parameter_{idx}_{direction}")

                if len(risk_factors) >= 5:
                    break

        if not risk_factors and np.max(np.abs(deviations_flat)) > 0.5:
            risk_factors.append("degradation_trend")

        return risk_factors

    def _generate_recommendations(
        self,
        equipment_id: str,
        risk_factors: List[str],
        failure_probability: float,
    ) -> List[str]:
        """生成维护建议

        Args:
            equipment_id: 设备标识
            risk_factors: 风险因素列表
            failure_probability: 故障概率

        Returns:
            List[str]: 建议措施列表
        """
        actions = []

        factor_action_map = {
            "temperature_anomaly": "检查温控系统并校准温度传感器",
            "temperature_high": "检查冷却系统是否正常工作",
            "temperature_low": "检查加热器元件和温控器",
            "pressure_anomaly": "检查真空系统密封性和压力传感器",
            "pressure_high": "检查压力调节阀和排气管道",
            "pressure_low": "检查真空泵性能和系统密封",
            "flow_rate_anomaly": "校准质量流量控制器(MFC)",
            "vibration_high": "检查机械传动部件和轴承状态",
            "power_drift": "检查RF电源输出和匹配网络",
            "degradation_trend": "安排常规预防性维护检查",
            "contamination": "安排腔体清洗维护",
            "sensor_noise": "检查传感器连接线路和接地",
        }

        # 根据风险因素生成对应建议
        for factor in risk_factors:
            for key, action in factor_action_map.items():
                if key in factor.lower().replace(" ", "_"):
                    if action not in actions:
                        actions.append(action)
                    break

        # 根据故障概率添加紧急建议
        if failure_probability >= 0.8:
            if "建议立即停止设备运行进行全面检查" not in actions:
                actions.insert(0, "建议立即停止设备运行进行全面检查")
        elif failure_probability >= 0.6:
            if "建议在下一个维护窗口进行详细检查" not in actions:
                actions.append("建议在下一个维护窗口进行详细检查")
        elif failure_probability >= 0.3:
            if "建议加强监控并准备备件" not in actions:
                actions.append("建议加强监控并准备备件")

        if not actions:
            actions.append("继续正常监控")

        return actions

    def get_maintenance_schedule(
        self,
        equipment_id: str,
        prediction: FailurePrediction,
        look_ahead_days: int = 30,
    ) -> MaintenanceSchedule:
        """根据预测结果生成维护计划

        Args:
            equipment_id: 设备标识
            prediction: 故障预测结果
            look_ahead_days: 预测天数范围

        Returns:
            MaintenanceSchedule: 维护计划
        """
        now = datetime.now()

        if prediction.predicted_failure_time:
            scheduled_date = prediction.predicted_failure_time - timedelta(hours=24)
            if scheduled_date < now:
                scheduled_date = now + timedelta(hours=4)
        else:
            scheduled_date = now + timedelta(days=look_ahead_days)

        # 确定维护类型
        if prediction.failure_probability >= 0.8:
            maint_type = "corrective"
            priority = 1
        elif prediction.failure_probability >= 0.5:
            maint_type = "condition-based"
            priority = 2
        else:
            maint_type = "preventive"
            priority = 3

        return MaintenanceSchedule(
            equipment_id=equipment_id,
            scheduled_date=scheduled_date,
            maintenance_type=maint_type,
            priority=priority,
            actions=prediction.recommended_actions[:5],
            estimated_downtime_hours=4.0 if priority == 1 else 2.0,
        )

    def batch_predict(
        self,
        equipment_data: Dict[str, np.ndarray],
    ) -> List[FailurePrediction]:
        """批量预测多台设备

        Args:
            equipment_data: {equipment_id: current_data} 字典

        Returns:
            List[FailurePrediction]: 故障预测结果列表
        """
        results = []
        for equipment_id, data in equipment_data.items():
            prediction = self.predict_failure(equipment_id, data)
            results.append(prediction)
        return results

    def get_equipment_status(self, equipment_id: str) -> Dict[str, Any]:
        """获取设备状态摘要

        Args:
            equipment_id: 设备标识

        Returns:
            Dict[str, Any]: 设备状态摘要
        """
        baseline = self._baselines.get(equipment_id)
        trend = self._trend_data.get(equipment_id)
        rates = self._degradation_rates.get(equipment_id, [])

        return {
            "equipment_id": equipment_id,
            "has_baseline": baseline is not None,
            "baseline_samples": baseline["sample_count"] if baseline else 0,
            "trend_points": len(trend) if trend else 0,
            "avg_degradation_rate": float(np.mean(rates)) if rates else 0.0,
            "max_degradation_rate": float(np.max(rates)) if rates else 0.0,
        }

    def reset(self) -> None:
        """重置引擎状态"""
        self._baselines.clear()
        self._trend_data.clear()
        self._degradation_rates.clear()
        self._recommendation_map.clear()
        logger.info("PredictiveMaintenance engine reset")
