"""FDC模块

故障检测与分类引擎 (Fault Detection and Classification)
负责实时监测工艺异常，检测和分类各种类型的设备故障。
"""

from myeap.fdc.models import (
    Fault,
    FaultSeverity,
    FaultStatus,
    FaultType,
)
from myeap.fdc.features import FeatureVector
from myeap.fdc.detector import (
    DetectionResult,
    FaultDetector,
    StatisticalDetector,
    ChangePointDetector,
)
from myeap.fdc.classifier import (
    Condition,
    ClassificationRule,
    FaultClassification,
    FaultClassifier,
)
from myeap.fdc.engine import FDCEngine

__all__ = [
    # Models
    "Fault",
    "FaultType",
    "FaultSeverity",
    "FaultStatus",
    # Features
    "FeatureVector",
    # Detectors
    "DetectionResult",
    "FaultDetector",
    "StatisticalDetector",
    "ChangePointDetector",
    # Classifier
    "Condition",
    "ClassificationRule",
    "FaultClassification",
    "FaultClassifier",
    # Engine
    "FDCEngine",
]

__version__ = "1.0.0"
