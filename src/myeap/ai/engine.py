"""AI引擎模块

AI智能分析引擎的主入口，协调预测性维护、良率预测和根因分析组件。

Example:
    >>> import numpy as np
    >>> from myeap.ai import AIEngine
    >>> engine = AIEngine()
    >>> health = engine.get_equipment_health("eq-001", np.random.normal(100, 5, (1, 3)))
    >>> yp_result = engine.predict_yield("batch-001", {"temperature": 150.0})
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from myeap.ai.models import (
    AnalysisStatus,
    EquipmentHealthReport,
    FailurePrediction,
    MaintenanceRecommendation,
    ProcessParameter,
    RootCauseResult,
    TrainingResult,
    YieldPrediction,
)
from myeap.ai.predictive_maintenance import (
    MaintenanceSchedule,
    PredictiveMaintenance,
)
from myeap.ai.yield_prediction import YieldPredictor
from myeap.ai.root_cause import (
    CausalGraph,
    PropagationPath,
    RootCauseAnalyzer,
)

logger = logging.getLogger(__name__)


class AIEngine:
    """AI智能分析引擎

    统一的AI分析引擎，协调所有智能分析组件。

    Attributes:
        on_prediction: 预测回调
        on_alert: 告警回调

    Example:
        >>> engine = AIEngine()
        >>> engine.train_baseline("eq-001", historical_data)
        >>> health = engine.get_equipment_health("eq-001", current_data)
        >>> print(f"Health score: {health.health_score}")
    """

    def __init__(
        self,
        rul_threshold: float = 168.0,
        yield_min_samples: int = 10,
    ):
        """初始化AI引擎

        Args:
            rul_threshold: RUL阈值（小时）
            yield_min_samples: 良率预测最少样本数
        """
        self._predictive_maintenance = PredictiveMaintenance(
            rul_threshold=rul_threshold,
        )
        self._yield_predictor = YieldPredictor(
            min_samples=yield_min_samples,
        )
        self._root_cause_analyzer = RootCauseAnalyzer()

        # 回调
        self._on_prediction: Optional[Callable[[FailurePrediction], None]] = None
        self._on_alert: Optional[Callable[[str, Any], None]] = None

        # 健康报告缓存
        self._health_reports: Dict[str, EquipmentHealthReport] = {}

        # 统计
        self._prediction_count: int = 0
        self._alert_count: int = 0

    @property
    def predictive_maintenance(self) -> PredictiveMaintenance:
        """获取预测性维护组件"""
        return self._predictive_maintenance

    @property
    def yield_predictor(self) -> YieldPredictor:
        """获取良率预测器组件"""
        return self._yield_predictor

    @property
    def root_cause_analyzer(self) -> RootCauseAnalyzer:
        """获取根因分析器组件"""
        return self._root_cause_analyzer

    def set_on_prediction(
        self,
        callback: Callable[[FailurePrediction], None],
    ) -> None:
        """设置预测回调

        Args:
            callback: 预测回调函数
        """
        self._on_prediction = callback

    def set_on_alert(
        self,
        callback: Callable[[str, Any], None],
    ) -> None:
        """设置告警回调

        Args:
            callback: 告警回调函数 (alert_type, data)
        """
        self._on_alert = callback

    # ---- 预测性维护 ----

    def train_baseline(
        self,
        equipment_id: str,
        historical_data: np.ndarray,
        parameter_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """训练设备基线

        Args:
            equipment_id: 设备标识
            historical_data: 历史健康数据
            parameter_names: 参数名称列表

        Returns:
            Dict[str, Any]: 基线统计信息
        """
        return self._predictive_maintenance.train_baseline(
            equipment_id, historical_data, parameter_names
        )

    def update_baseline(
        self,
        equipment_id: str,
        new_data: np.ndarray,
        learning_rate: float = 0.1,
    ) -> None:
        """在线更新设备基线

        Args:
            equipment_id: 设备标识
            new_data: 新健康数据
            learning_rate: 学习率
        """
        self._predictive_maintenance.update_baseline(
            equipment_id, new_data, learning_rate
        )

    def predict_failure(
        self,
        equipment_id: str,
        current_data: np.ndarray,
    ) -> FailurePrediction:
        """预测设备故障

        Args:
            equipment_id: 设备标识
            current_data: 当前测量数据

        Returns:
            FailurePrediction: 故障预测结果
        """
        result = self._predictive_maintenance.predict_failure(
            equipment_id, current_data
        )

        self._prediction_count += 1

        # 触发回调
        if result.failure_probability >= 0.5 and self._on_prediction:
            try:
                self._on_prediction(result)
            except Exception as e:
                logger.error(f"Error in prediction callback: {e}")

        return result

    def get_maintenance_schedule(
        self,
        equipment_id: str,
        prediction: Optional[FailurePrediction] = None,
        look_ahead_days: int = 30,
    ) -> MaintenanceSchedule:
        """获取维护计划

        Args:
            equipment_id: 设备标识
            prediction: 故障预测 (可选，如不提供则使用最新)
            look_ahead_days: 预测天数

        Returns:
            MaintenanceSchedule: 维护计划
        """
        if prediction is None:
            prediction = self._predictive_maintenance.predict_failure(
                equipment_id, np.zeros(1)
            )

        return self._predictive_maintenance.get_maintenance_schedule(
            equipment_id, prediction, look_ahead_days
        )

    # ---- 良率预测 ----

    def add_process_parameter(
        self,
        name: str,
        value: float,
        target: Optional[float] = None,
        unit: str = "",
        tolerance_upper: Optional[float] = None,
        tolerance_lower: Optional[float] = None,
        importance: float = 1.0,
    ) -> ProcessParameter:
        """添加工艺参数定义

        Args:
            name: 参数名称
            value: 当前值
            target: 目标值
            unit: 单位
            tolerance_upper: 上公差
            tolerance_lower: 下公差
            importance: 重要性权重

        Returns:
            ProcessParameter: 工艺参数
        """
        return self._yield_predictor.add_process_parameter(
            name, value, target, unit, tolerance_upper, tolerance_lower, importance
        )

    def add_yield_record(
        self,
        batch_id: str,
        yield_rate: float,
        process_params: Dict[str, float],
        timestamp: Optional[datetime] = None,
        product_type: str = "",
    ) -> Any:
        """添加良率历史记录

        Args:
            batch_id: 批次标识
            yield_rate: 实际良率
            process_params: 工艺参数
            timestamp: 时间戳
            product_type: 产品类型

        Returns:
            BatchYieldRecord: 良率记录
        """
        return self._yield_predictor.add_yield_record(
            batch_id, yield_rate, process_params, timestamp, product_type
        )

    def train_yield_model(self) -> TrainingResult:
        """训练良率预测模型

        Returns:
            TrainingResult: 训练结果
        """
        return self._yield_predictor.train()

    def predict_yield(
        self,
        batch_id: str,
        process_params: Dict[str, float],
    ) -> YieldPrediction:
        """预测批次良率

        Args:
            batch_id: 批次标识
            process_params: 工艺参数值字典

        Returns:
            YieldPrediction: 良率预测结果
        """
        result = self._yield_predictor.predict_yield(batch_id, process_params)

        # 低良率告警
        if result.predicted_yield < 0.85 and self._on_alert:
            try:
                self._on_alert("low_yield_warning", result.to_dict())
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        return result

    def predict_yield_batch(
        self,
        batches: List[Tuple[str, Dict[str, float]]],
    ) -> List[YieldPrediction]:
        """批量预测良率

        Args:
            batches: 批次列表

        Returns:
            List[YieldPrediction]: 预测结果列表
        """
        return self._yield_predictor.predict_yield_batch(batches)

    # ---- 根因分析 ----

    def record_event(
        self,
        equipment_id: str,
        event_type: str,
        timestamp: Optional[datetime] = None,
        severity: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录设备事件

        Args:
            equipment_id: 设备标识
            event_type: 事件类型
            timestamp: 时间戳
            severity: 严重程度
            metadata: 附加元数据
        """
        self._root_cause_analyzer.add_event(
            equipment_id, event_type, timestamp, severity, metadata
        )

    def analyze_root_cause(
        self,
        incident_id: str,
        equipment_id: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> RootCauseResult:
        """分析根因

        Args:
            incident_id: 事件标识
            equipment_id: 设备标识
            time_range: 时间范围

        Returns:
            RootCauseResult: 根因分析结果
        """
        return self._root_cause_analyzer.analyze(
            incident_id, equipment_id, time_range
        )

    def analyze_root_cause_multi(
        self,
        incident_id: str,
        equipment_ids: List[str],
    ) -> RootCauseResult:
        """多设备根因分析

        Args:
            incident_id: 事件标识
            equipment_ids: 设备标识列表

        Returns:
            RootCauseResult: 根因分析结果
        """
        return self._root_cause_analyzer.analyze_multi_equipment(
            incident_id, equipment_ids
        )

    # ---- 综合健康报告 ----

    def get_equipment_health(
        self,
        equipment_id: str,
        current_data: np.ndarray,
        include_maintenance: bool = True,
    ) -> EquipmentHealthReport:
        """获取设备综合健康报告

        综合故障预测和维护建议生成完整的设备健康报告。

        Args:
            equipment_id: 设备标识
            current_data: 当前测量数据
            include_maintenance: 是否包含维护建议

        Returns:
            EquipmentHealthReport: 设备健康报告
        """
        # 故障预测
        failure_pred = self.predict_failure(equipment_id, current_data)

        # 计算健康分数
        health_score = (1.0 - failure_pred.failure_probability) * 100

        # 维护建议
        recommendations = []
        if include_maintenance and failure_pred.risk_factors:
            recs = self._predictive_maintenance._generate_recommendations(
                equipment_id, failure_pred.risk_factors, failure_pred.failure_probability
            )

            from myeap.ai.predictive_maintenance import get_default_maintenance_recommendations
            recommendations = get_default_maintenance_recommendations(
                equipment_id, failure_pred.risk_factors
            )

        # 趋势判断
        status = self._predictive_maintenance.get_equipment_status(equipment_id)
        deg_rate = status.get("avg_degradation_rate", 0.0)
        if deg_rate > 0.05:
            trend = "declining"
        elif deg_rate > 0.01:
            trend = "stable"
        else:
            trend = "improving"

        report = EquipmentHealthReport(
            equipment_id=equipment_id,
            health_score=health_score,
            failure_prediction=failure_pred,
            maintenance_recommendations=recommendations,
            active_alerts=len(failure_pred.risk_factors),
            trend=trend,
            last_updated=datetime.now(),
        )

        self._health_reports[equipment_id] = report

        # 低健康分数告警
        if health_score < 50 and self._on_alert:
            try:
                self._on_alert("low_health_score", report.to_dict())
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        return report

    def get_cached_health_report(
        self, equipment_id: str
    ) -> Optional[EquipmentHealthReport]:
        """获取缓存的健康报告

        Args:
            equipment_id: 设备标识

        Returns:
            Optional[EquipmentHealthReport]: 健康报告
        """
        return self._health_reports.get(equipment_id)

    # ---- 统计和摘要 ----

    def get_summary(self) -> Dict[str, Any]:
        """获取引擎摘要

        Returns:
            Dict[str, Any]: 引擎摘要信息
        """
        pm_status = self._predictive_maintenance.get_equipment_status("__all__") if False else {}
        yp_stats = self._yield_predictor.get_statistics()
        rca_history = self._root_cause_analyzer.get_history()

        return {
            "prediction_count": self._prediction_count,
            "alert_count": self._alert_count,
            "equipment_count": len(self._predictive_maintenance._baselines),
            "yield_records_count": yp_stats.get("record_count", 0),
            "yield_model_trained": yp_stats.get("is_trained", False),
            "rca_history_count": len(rca_history),
            "cached_reports": len(self._health_reports),
        }

    def reset(self) -> None:
        """重置引擎状态"""
        self._predictive_maintenance.reset()
        self._yield_predictor.reset()
        self._root_cause_analyzer.reset()
        self._health_reports.clear()
        self._prediction_count = 0
        self._alert_count = 0
        logger.info("AIEngine reset")


class AsyncAIEngine(AIEngine):
    """异步AI引擎

    支持异步回调的AI引擎版本。
    """

    def __init__(
        self,
        rul_threshold: float = 168.0,
        yield_min_samples: int = 10,
    ):
        super().__init__(rul_threshold, yield_min_samples)
        self._on_prediction_async: Optional[Callable[[FailurePrediction], Any]] = None
        self._on_alert_async: Optional[Callable[[str, Any], Any]] = None

    def set_on_prediction_async(
        self,
        callback: Callable[[FailurePrediction], Any],
    ) -> None:
        """设置异步预测回调

        Args:
            callback: 异步回调函数
        """
        self._on_prediction_async = callback

    def set_on_alert_async(
        self,
        callback: Callable[[str, Any], Any],
    ) -> None:
        """设置异步告警回调

        Args:
            callback: 异步回调函数
        """
        self._on_alert_async = callback

    async def predict_failure_async(
        self,
        equipment_id: str,
        current_data: np.ndarray,
    ) -> FailurePrediction:
        """异步预测设备故障

        Args:
            equipment_id: 设备标识
            current_data: 当前测量数据

        Returns:
            FailurePrediction: 故障预测结果
        """
        result = self._predictive_maintenance.predict_failure(
            equipment_id, current_data
        )

        self._prediction_count += 1

        if result.failure_probability >= 0.5:
            if self._on_prediction_async:
                try:
                    ret = self._on_prediction_async(result)
                    if asyncio.iscoroutine(ret):
                        await ret
                except Exception as e:
                    logger.error(f"Error in async prediction callback: {e}")
            elif self._on_prediction:
                try:
                    self._on_prediction(result)
                except Exception as e:
                    logger.error(f"Error in prediction callback: {e}")

        return result

    async def get_equipment_health_async(
        self,
        equipment_id: str,
        current_data: np.ndarray,
        include_maintenance: bool = True,
    ) -> EquipmentHealthReport:
        """异步获取设备健康报告

        Args:
            equipment_id: 设备标识
            current_data: 当前测量数据
            include_maintenance: 是否包含维护建议

        Returns:
            EquipmentHealthReport: 设备健康报告
        """
        result = await self.predict_failure_async(equipment_id, current_data)
        return self.get_equipment_health(equipment_id, current_data, include_maintenance)
