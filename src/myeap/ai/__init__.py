"""AI/ML 智能分析模块

AI驱动的预测性维护、良率预测和根因分析模块。

主要功能：
- 预测性维护: 基于统计方法预测设备故障和剩余使用寿命
- 良率预测: 基于工艺参数预测批次良率
- 根因分析: 关联分析和因果推断定位故障根因
- AI引擎: 统一接口协调各分析组件

Example:
    >>> from myeap.ai import AIEngine
    >>> engine = AIEngine()
    >>> health = engine.get_equipment_health("eq-001", current_data)
    >>> yield_pred = engine.predict_yield("batch-001", process_params)
    >>> root_causes = engine.analyze_root_cause("eq-001", events)
"""

from myeap.ai.models import (
    FailurePrediction,
    YieldPrediction,
    RootCauseResult,
    ProcessParameter,
    MaintenanceRecommendation,
    AnomalyPattern,
    TrainingResult,
    EquipmentHealthReport,
    PredictionConfidence,
    AnalysisStatus,
)

from myeap.ai.predictive_maintenance import (
    PredictiveMaintenance,
    MaintenanceSchedule,
    get_default_maintenance_recommendations,
)

from myeap.ai.yield_prediction import (
    YieldPredictor,
    FeatureImportance,
    BatchYieldRecord,
    get_default_process_parameters,
)

from myeap.ai.root_cause import (
    RootCauseAnalyzer,
    CausalGraph,
    PropagationPath,
    EventCorrelation,
    build_correlation_matrix,
    infer_propagation_path,
)

from myeap.ai.engine import AIEngine, AsyncAIEngine

__all__ = [
    # Models
    "FailurePrediction",
    "YieldPrediction",
    "RootCauseResult",
    "ProcessParameter",
    "MaintenanceRecommendation",
    "AnomalyPattern",
    "TrainingResult",
    "EquipmentHealthReport",
    "PredictionConfidence",
    "AnalysisStatus",
    # Predictive Maintenance
    "PredictiveMaintenance",
    "MaintenanceSchedule",
    "get_default_maintenance_recommendations",
    # Yield Prediction
    "YieldPredictor",
    "FeatureImportance",
    "BatchYieldRecord",
    "get_default_process_parameters",
    # Root Cause Analysis
    "RootCauseAnalyzer",
    "CausalGraph",
    "PropagationPath",
    "EventCorrelation",
    "build_correlation_matrix",
    "infer_propagation_path",
    # Engine
    "AIEngine",
    "AsyncAIEngine",
]

__version__ = "1.0.0"
