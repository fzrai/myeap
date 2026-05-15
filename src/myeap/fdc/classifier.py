"""故障分类器模块

实现基于规则和ML的故障分类器。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from myeap.fdc.models import FaultClassification, FaultType
from myeap.fdc.features import FeatureVector

logger = logging.getLogger(__name__)


class Condition(ABC):
    """分类条件基类"""

    @abstractmethod
    def evaluate(self, features: FeatureVector) -> bool:
        """评估条件是否满足

        Args:
            features: 特征向量

        Returns:
            bool: 是否满足条件
        """
        pass


@dataclass
class FeatureCondition(Condition):
    """特征条件

    基于特征值的分类条件。

    Attributes:
        feature_name: 特征名称
        operator: 比较运算符 (">", "<", ">=", "<=", "==", "!=")
        threshold: 阈值
    """

    feature_name: str
    operator: str
    threshold: float

    def evaluate(self, features: FeatureVector) -> bool:
        """评估条件是否满足"""
        value = getattr(features, self.feature_name, None)
        if value is None:
            return False

        if self.operator == ">":
            return value > self.threshold
        elif self.operator == "<":
            return value < self.threshold
        elif self.operator == ">=":
            return value >= self.threshold
        elif self.operator == "<=":
            return value <= self.threshold
        elif self.operator == "==":
            return abs(value - self.threshold) < 1e-6
        elif self.operator == "!=":
            return abs(value - self.threshold) >= 1e-6
        else:
            return False


@dataclass
class CompositeCondition(Condition):
    """组合条件

    组合多个条件的逻辑运算。

    Attributes:
        conditions: 条件列表
        logic: 逻辑运算符 ("and", "or")
    """

    conditions: List[Condition]
    logic: str = "and"

    def evaluate(self, features: FeatureVector) -> bool:
        """评估条件是否满足"""
        if self.logic == "and":
            return all(c.evaluate(features) for c in self.conditions)
        elif self.logic == "or":
            return any(c.evaluate(features) for c in self.conditions)
        else:
            return False


@dataclass
class ClassificationRule:
    """分类规则

    定义故障分类的规则。

    Attributes:
        name: 规则名称
        fault_type: 故障类型
        conditions: 条件列表
        confidence: 置信度
        priority: 优先级（数值越小优先级越高）
        recommendations: 建议的处理措施
    """

    name: str
    fault_type: FaultType
    conditions: List[Condition]
    confidence: float = 0.8
    priority: int = 100
    recommendations: List[str] = None

    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []

    def validate(self, features: FeatureVector) -> bool:
        """验证特征是否匹配规则"""
        return all(c.evaluate(features) for c in self.conditions)


class FaultClassifier:
    """故障分类器

    基于规则和ML的故障分类。

    Attributes:
        rules: 分类规则列表
        ml_model: ML模型（可选）
    """

    # 默认规则定义
    DEFAULT_RULES: List[ClassificationRule] = []

    def __init__(
        self,
        rules: Optional[List[ClassificationRule]] = None,
        ml_model: Optional[Any] = None,
    ):
        """初始化故障分类器

        Args:
            rules: 分类规则列表
            ml_model: ML模型（可选）
        """
        self._rules: List[ClassificationRule] = rules or []
        self._ml_model = ml_model

        # 添加默认规则
        if not self._rules:
            self._rules = self._create_default_rules()

    def _create_default_rules(self) -> List[ClassificationRule]:
        """创建默认分类规则"""
        rules = [
            # 温度漂移规则
            ClassificationRule(
                name="temp_drift_rule",
                fault_type=FaultType.TEMP_DRIFT,
                conditions=[
                    FeatureCondition("slope", "!=", 0.0),
                    FeatureCondition("r_squared", ">=", 0.7),
                    FeatureCondition("stability_score", "<", 0.5),
                ],
                confidence=0.85,
                priority=10,
                recommendations=[
                    "检查温度传感器校准",
                    "检查加热元件性能",
                    "检查腔体热区分布",
                ],
            ),
            # 温度尖峰规则
            ClassificationRule(
                name="temp_spike_rule",
                fault_type=FaultType.TEMP_SPIKE,
                conditions=[
                    FeatureCondition("max_derivative", ">", 5.0),
                    FeatureCondition("kurtosis", ">", 3.0),
                ],
                confidence=0.90,
                priority=5,
                recommendations=[
                    "检查温度传感器连接",
                    "检查电源稳定性",
                    "检查干扰源",
                ],
            ),
            # 温度振荡规则
            ClassificationRule(
                name="temp_oscillation_rule",
                fault_type=FaultType.TEMP_OSCILLATION,
                conditions=[
                    FeatureCondition("zero_crossings", ">", 10),
                    FeatureCondition("spectral_entropy", ">", 0.5),
                    FeatureCondition("dominant_frequency", "!=", 0.0),
                ],
                confidence=0.80,
                priority=15,
                recommendations=[
                    "检查温度控制系统PID参数",
                    "检查反馈传感器响应",
                    "检查环境温度波动",
                ],
            ),
            # 压力漂移规则
            ClassificationRule(
                name="pressure_drift_rule",
                fault_type=FaultType.PRESSURE_DRIFT,
                conditions=[
                    FeatureCondition("slope", "!=", 0.0),
                    FeatureCondition("mean", "!=", 0.0),
                ],
                confidence=0.82,
                priority=10,
                recommendations=[
                    "检查压力传感器",
                    "检查真空泵性能",
                    "检查腔体密封",
                ],
            ),
            # 压力下降规则
            ClassificationRule(
                name="pressure_drop_rule",
                fault_type=FaultType.PRESSURE_DROP,
                conditions=[
                    FeatureCondition("slope", "<", -0.1),
                    FeatureCondition("r_squared", ">=", 0.7),
                ],
                confidence=0.88,
                priority=5,
                recommendations=[
                    "检查真空泵",
                    "检查腔体泄漏",
                    "检查阀门状态",
                ],
            ),
            # 压力尖峰规则
            ClassificationRule(
                name="pressure_spike_rule",
                fault_type=FaultType.PRESSURE_SPIKE,
                conditions=[
                    FeatureCondition("max_derivative", ">", 3.0),
                    FeatureCondition("peak_to_peak", ">", 2.0),
                ],
                confidence=0.87,
                priority=5,
                recommendations=[
                    "检查压力控制系统",
                    "检查阀门动作",
                    "检查气流冲击",
                ],
            ),
            # 气体流量异常规则
            ClassificationRule(
                name="gas_flow_error_rule",
                fault_type=FaultType.GAS_FLOW_ERROR,
                conditions=[
                    FeatureCondition("std", ">", 0.5),
                    FeatureCondition("mean", "!=", 0.0),
                ],
                confidence=0.83,
                priority=10,
                recommendations=[
                    "检查MFC流量计",
                    "检查气体管路",
                    "检查气体压力",
                ],
            ),
            # MFC漂移规则
            ClassificationRule(
                name="mfc_drift_rule",
                fault_type=FaultType.MFC_DRIFT,
                conditions=[
                    FeatureCondition("slope", "!=", 0.0),
                    FeatureCondition("r_squared", ">=", 0.6),
                ],
                confidence=0.80,
                priority=15,
                recommendations=[
                    "校准MFC流量计",
                    "检查MFC控制电路",
                    "检查气体纯度",
                ],
            ),
            # 气体泄漏规则
            ClassificationRule(
                name="gas_leak_rule",
                fault_type=FaultType.GAS_LEAK,
                conditions=[
                    FeatureCondition("mean", "<", 0.0),
                    FeatureCondition("slope", "<", -0.05),
                ],
                confidence=0.85,
                priority=3,
                recommendations=[
                    "立即检查腔体密封",
                    "检查气体管路连接",
                    "启动应急排气系统",
                ],
            ),
            # 等离子体不稳定规则
            ClassificationRule(
                name="plasma_unstable_rule",
                fault_type=FaultType.PLASMA_UNSTABLE,
                conditions=[
                    FeatureCondition("std", ">", 1.0),
                    FeatureCondition("stability_score", "<", 0.3),
                    FeatureCondition("zero_crossings", ">", 5),
                ],
                confidence=0.88,
                priority=5,
                recommendations=[
                    "检查RF匹配器",
                    "检查电极状态",
                    "检查气体成分",
                ],
            ),
            # 等离子体熄灭规则
            ClassificationRule(
                name="plasma_extinction_rule",
                fault_type=FaultType.PLASMA_EXTINCTION,
                conditions=[
                    FeatureCondition("mean", "<", 0.1),
                    FeatureCondition("std", "<", 0.1),
                ],
                confidence=0.95,
                priority=1,
                recommendations=[
                    "立即停止工艺",
                    "检查RF功率",
                    "检查气体供应",
                    "检查腔体状态",
                ],
            ),
            # 腔体污染规则
            ClassificationRule(
                name="chamber_contamination_rule",
                fault_type=FaultType.CHAMBER_CONTAMINATION,
                conditions=[
                    FeatureCondition("stability_score", "<", 0.4),
                    FeatureCondition("skewness", ">", 1.0),
                ],
                confidence=0.75,
                priority=20,
                recommendations=[
                    "执行腔体清洁",
                    "检查镀膜残留",
                    "检查副产物排放",
                ],
            ),
            # ESC加热器故障规则
            ClassificationRule(
                name="esc_heater_failure_rule",
                fault_type=FaultType.ESC_HEATER_FAILURE,
                conditions=[
                    FeatureCondition("mean", "<", 0.5),
                    FeatureCondition("slope", "!=", 0.0),
                ],
                confidence=0.80,
                priority=10,
                recommendations=[
                    "检查ESC加热器电路",
                    "测量加热器电阻",
                    "检查温度控制器",
                ],
            ),
            # RF功率异常规则
            ClassificationRule(
                name="rf_power_error_rule",
                fault_type=FaultType.RF_POWER_ERROR,
                conditions=[
                    FeatureCondition("std", ">", 0.5),
                    FeatureCondition("max_derivative", ">", 2.0),
                ],
                confidence=0.82,
                priority=8,
                recommendations=[
                    "检查RF发生器",
                    "检查RF匹配器",
                    "检查传输线连接",
                ],
            ),
        ]

    def _create_default_rules(self) -> List[ClassificationRule]:
        """创建默认分类规则"""
        rules = [
            # 温度漂移规则
            ClassificationRule(
                name="temp_drift_rule",
                fault_type=FaultType.TEMP_DRIFT,
                conditions=[
                    FeatureCondition("slope", "!=", 0.0),
                    FeatureCondition("r_squared", ">=", 0.7),
                    FeatureCondition("stability_score", "<", 0.5),
                ],
                confidence=0.85,
                priority=10,
                recommendations=[
                    "检查温度传感器校准",
                    "检查加热元件性能",
                    "检查腔体热区分布",
                ],
            ),
            # 温度尖峰规则
            ClassificationRule(
                name="temp_spike_rule",
                fault_type=FaultType.TEMP_SPIKE,
                conditions=[
                    FeatureCondition("max_derivative", ">", 5.0),
                    FeatureCondition("kurtosis", ">", 3.0),
                ],
                confidence=0.90,
                priority=5,
                recommendations=[
                    "检查温度传感器连接",
                    "检查电源稳定性",
                    "检查干扰源",
                ],
            ),
            # 温度振荡规则
            ClassificationRule(
                name="temp_oscillation_rule",
                fault_type=FaultType.TEMP_OSCILLATION,
                conditions=[
                    FeatureCondition("zero_crossings", ">", 10),
                    FeatureCondition("spectral_entropy", ">", 0.5),
                    FeatureCondition("dominant_frequency", "!=", 0.0),
                ],
                confidence=0.80,
                priority=15,
                recommendations=[
                    "检查温度控制系统PID参数",
                    "检查反馈传感器响应",
                    "检查环境温度波动",
                ],
            ),
            # 压力漂移规则
            ClassificationRule(
                name="pressure_drift_rule",
                fault_type=FaultType.PRESSURE_DRIFT,
                conditions=[
                    FeatureCondition("slope", "!=", 0.0),
                    FeatureCondition("mean", "!=", 0.0),
                ],
                confidence=0.82,
                priority=10,
                recommendations=[
                    "检查压力传感器",
                    "检查真空泵性能",
                    "检查腔体密封",
                ],
            ),
            # 压力下降规则
            ClassificationRule(
                name="pressure_drop_rule",
                fault_type=FaultType.PRESSURE_DROP,
                conditions=[
                    FeatureCondition("slope", "<", -0.1),
                    FeatureCondition("r_squared", ">=", 0.7),
                ],
                confidence=0.88,
                priority=5,
                recommendations=[
                    "检查真空泵",
                    "检查腔体泄漏",
                    "检查阀门状态",
                ],
            ),
            # 压力尖峰规则
            ClassificationRule(
                name="pressure_spike_rule",
                fault_type=FaultType.PRESSURE_SPIKE,
                conditions=[
                    FeatureCondition("max_derivative", ">", 3.0),
                    FeatureCondition("peak_to_peak", ">", 2.0),
                ],
                confidence=0.87,
                priority=5,
                recommendations=[
                    "检查压力控制系统",
                    "检查阀门动作",
                    "检查气流冲击",
                ],
            ),
            # 气体流量异常规则
            ClassificationRule(
                name="gas_flow_error_rule",
                fault_type=FaultType.GAS_FLOW_ERROR,
                conditions=[
                    FeatureCondition("std", ">", 1.0),  # 调整阈值以区分正常波动
                    FeatureCondition("mean", "!=", 0.0),
                ],
                confidence=0.83,
                priority=12,
                recommendations=[
                    "检查MFC流量计",
                    "检查气体管路",
                    "检查气体压力",
                ],
            ),
            # MFC漂移规则
            ClassificationRule(
                name="mfc_drift_rule",
                fault_type=FaultType.MFC_DRIFT,
                conditions=[
                    FeatureCondition("slope", "!=", 0.0),
                    FeatureCondition("r_squared", ">=", 0.6),
                ],
                confidence=0.80,
                priority=15,
                recommendations=[
                    "校准MFC流量计",
                    "检查MFC控制电路",
                    "检查气体纯度",
                ],
            ),
            # 气体泄漏规则
            ClassificationRule(
                name="gas_leak_rule",
                fault_type=FaultType.GAS_LEAK,
                conditions=[
                    FeatureCondition("mean", "<", 0.0),
                    FeatureCondition("slope", "<", -0.05),
                ],
                confidence=0.85,
                priority=3,
                recommendations=[
                    "立即检查腔体密封",
                    "检查气体管路连接",
                    "启动应急排气系统",
                ],
            ),
            # 等离子体不稳定规则
            ClassificationRule(
                name="plasma_unstable_rule",
                fault_type=FaultType.PLASMA_UNSTABLE,
                conditions=[
                    FeatureCondition("std", ">", 1.0),
                    FeatureCondition("stability_score", "<", 0.3),
                    FeatureCondition("zero_crossings", ">", 5),
                ],
                confidence=0.88,
                priority=5,
                recommendations=[
                    "检查RF匹配器",
                    "检查电极状态",
                    "检查气体成分",
                ],
            ),
            # 等离子体熄灭规则
            ClassificationRule(
                name="plasma_extinction_rule",
                fault_type=FaultType.PLASMA_EXTINCTION,
                conditions=[
                    FeatureCondition("mean", "<", 0.1),
                    FeatureCondition("std", "<", 0.1),
                ],
                confidence=0.95,
                priority=1,
                recommendations=[
                    "立即停止工艺",
                    "检查RF功率",
                    "检查气体供应",
                    "检查腔体状态",
                ],
            ),
            # 腔体污染规则
            ClassificationRule(
                name="chamber_contamination_rule",
                fault_type=FaultType.CHAMBER_CONTAMINATION,
                conditions=[
                    FeatureCondition("stability_score", "<", 0.4),
                    FeatureCondition("skewness", ">", 1.0),
                ],
                confidence=0.75,
                priority=20,
                recommendations=[
                    "执行腔体清洁",
                    "检查镀膜残留",
                    "检查副产物排放",
                ],
            ),
            # ESC加热器故障规则
            ClassificationRule(
                name="esc_heater_failure_rule",
                fault_type=FaultType.ESC_HEATER_FAILURE,
                conditions=[
                    FeatureCondition("mean", "<", 0.5),
                    FeatureCondition("slope", "!=", 0.0),
                ],
                confidence=0.80,
                priority=10,
                recommendations=[
                    "检查ESC加热器电路",
                    "测量加热器电阻",
                    "检查温度控制器",
                ],
            ),
            # RF功率异常规则
            ClassificationRule(
                name="rf_power_error_rule",
                fault_type=FaultType.RF_POWER_ERROR,
                conditions=[
                    FeatureCondition("std", ">", 0.5),
                    FeatureCondition("max_derivative", ">", 2.0),
                ],
                confidence=0.82,
                priority=8,
                recommendations=[
                    "检查RF发生器",
                    "检查RF匹配器",
                    "检查传输线连接",
                ],
            ),
        ]
        # 按优先级排序
        return sorted(rules, key=lambda r: r.priority)

    def add_rule(self, rule: ClassificationRule) -> None:
        """添加分类规则

        Args:
            rule: 分类规则
        """
        self._rules.append(rule)
        # 按优先级排序
        self._rules.sort(key=lambda r: r.priority)

    def remove_rule(self, rule_name: str) -> bool:
        """移除分类规则

        Args:
            rule_name: 规则名称

        Returns:
            bool: 是否成功移除
        """
        for i, rule in enumerate(self._rules):
            if rule.name == rule_name:
                self._rules.pop(i)
                return True
        return False

    def classify(
        self,
        features: FeatureVector,
        fault_type: Optional[FaultType] = None,
    ) -> FaultClassification:
        """分类故障

        Args:
            features: 特征向量
            fault_type: 故障类型（可选，用于验证）

        Returns:
            FaultClassification: 分类结果
        """
        # 如果已知故障类型，验证
        if fault_type:
            rule = self._find_rule(fault_type)
            if rule and rule.validate(features):
                return FaultClassification(
                    fault_type=fault_type,
                    confidence=rule.confidence,
                    matched_rule=rule.name,
                )

        # 使用规则匹配分类
        result = self._classify_rules(features)
        if result.fault_type != FaultType.UNKNOWN:
            return result

        # 使用ML模型分类
        if self._ml_model:
            return self._classify_ml(features)

        return result

    def _classify_rules(self, features: FeatureVector) -> FaultClassification:
        """基于规则分类"""
        # 按优先级检查规则
        for rule in sorted(self._rules, key=lambda r: r.priority):
            if rule.validate(features):
                return FaultClassification(
                    fault_type=rule.fault_type,
                    confidence=rule.confidence,
                    matched_rule=rule.name,
                )

        return FaultClassification(
            fault_type=FaultType.UNKNOWN,
            confidence=0.0,
        )

    def _classify_ml(self, features: FeatureVector) -> FaultClassification:
        """使用ML模型分类"""
        if not self._ml_model:
            return FaultClassification(
                fault_type=FaultType.UNKNOWN,
                confidence=0.0,
            )

        try:
            # 转换为模型输入格式
            feature_dict = features.to_dict()
            X = [feature_dict[k] for k in sorted(feature_dict.keys())]

            # 预测
            prediction = self._ml_model.predict([X])[0]
            probabilities = self._ml_model.predict_proba([X])[0]
            confidence = float(max(probabilities))

            return FaultClassification(
                fault_type=FaultType(prediction),
                confidence=confidence,
                matched_rule="ml_model",
            )
        except Exception as e:
            logger.error(f"ML classification error: {e}")
            return FaultClassification(
                fault_type=FaultType.UNKNOWN,
                confidence=0.0,
            )

    def _find_rule(self, fault_type: FaultType) -> Optional[ClassificationRule]:
        """查找指定故障类型的规则"""
        for rule in self._rules:
            if rule.fault_type == fault_type:
                return rule
        return None

    def get_recommendations(self, fault_type: FaultType) -> List[str]:
        """获取故障类型的建议处理措施

        Args:
            fault_type: 故障类型

        Returns:
            List[str]: 建议列表
        """
        rule = self._find_rule(fault_type)
        if rule:
            return rule.recommendations
        return []


class MLClassifier:
    """机器学习分类器封装

    用于封装sklearn等机器学习库的分类器。

    Attributes:
        model: 训练好的模型
        classes: 类别标签
    """

    def __init__(
        self,
        model: Any,
        classes: Optional[List[str]] = None,
    ):
        """初始化ML分类器

        Args:
            model: 训练好的模型
            classes: 类别标签
        """
        self.model = model
        self.classes = classes or []

    def predict(self, X: List[List[float]]) -> List[str]:
        """预测类别

        Args:
            X: 特征矩阵

        Returns:
            List[str]: 预测的类别标签
        """
        predictions = self.model.predict(X)
        if self.classes:
            return [self.classes[p] for p in predictions]
        return list(predictions)

    def predict_proba(self, X: List[List[float]]) -> List[List[float]]:
        """预测概率

        Args:
            X: 特征矩阵

        Returns:
            List[List[float]]: 每个类别的概率
        """
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X).tolist()
        return [[1.0 / len(self.classes)] * len(self.classes)]


def create_rule_based_classifier() -> FaultClassifier:
    """创建基于规则的分类器

    Returns:
        FaultClassifier: 配置好的分类器
    """
    return FaultClassifier()
