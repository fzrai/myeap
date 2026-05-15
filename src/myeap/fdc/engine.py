"""FDC引擎模块

故障检测与分类引擎的主入口。
负责协调故障检测、分类和处理流程。
"""

import asyncio
import logging
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Deque

import numpy as np

from myeap.data.limit_monitor import Limit, LimitType
from myeap.fdc.classifier import FaultClassifier
from myeap.fdc.detector import (
    CompositeDetector,
    FaultDetector,
    StatisticalDetector,
    ChangePointDetector,
    TrendDetector,
)
from myeap.fdc.features import FeatureExtractor, FeatureVector
from myeap.fdc.models import (
    DetectionResult,
    FDCEvent,
    FDCEventType,
    Fault,
    FaultClassification,
    FaultSeverity,
    FaultStatus,
    FaultType,
)

logger = logging.getLogger(__name__)


class FDCEngine:
    """FDC引擎

    故障检测与分类引擎的核心类。

    Attributes:
        on_fault: 故障回调函数
        on_event: 事件回调函数

    Example:
        engine = FDCEngine()
        engine.set_limit("eq-001", "Temperature", Limit(...))
        fault = await engine.process_data("eq-001", "ch-1", {"Temperature": 150.0}, datetime.now())
    """

    def __init__(
        self,
        window_size: int = 100,
        min_window_size: int = 30,
    ):
        """初始化FDC引擎

        Args:
            window_size: 滑动窗口大小
            min_window_size: 最小窗口大小
        """
        self._window_size = window_size
        self._min_window_size = min_window_size

        # 检测器
        self._detectors: Dict[str, FaultDetector] = {}
        self._default_detector_factory = StatisticalDetector

        # 分类器
        self._classifier = FaultClassifier()

        # 限值
        self._limits: Dict[str, Dict[str, Limit]] = defaultdict(dict)

        # 特征缓冲区
        self._feature_buffer: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=window_size))

        # 基线数据
        self._baselines: Dict[str, np.ndarray] = {}

        # 特征提取器
        self._feature_extractor = FeatureExtractor(window_size=window_size)

        # 回调函数
        self._on_fault: Optional[Callable[[Fault], Any]] = None
        self._on_fault_async: Optional[Callable[[Fault], Any]] = None
        self._on_event: Optional[Callable[[FDCEvent], Any]] = None
        self._on_event_async: Optional[Callable[[FDCEvent], Any]] = None

        # 统计数据
        self._fault_count = 0
        self._active_faults: Dict[str, Fault] = {}
        self._fault_history: List[Fault] = []

        # 配置
        self._detection_threshold = 0.7
        self._classification_threshold = 0.6

    def set_on_fault(
        self,
        callback: Callable[[Fault], Any],
        async_callback: bool = False,
    ) -> None:
        """设置故障回调

        Args:
            callback: 回调函数
            async_callback: 是否为异步回调
        """
        if async_callback:
            self._on_fault_async = callback
        else:
            self._on_fault = callback

    def set_on_event(
        self,
        callback: Callable[[FDCEvent], Any],
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

    def set_limit(
        self,
        equipment_id: str,
        parameter: str,
        limit: Limit,
    ) -> None:
        """设置FDC限值

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            limit: 限值定义
        """
        self._limits[equipment_id][parameter] = limit
        logger.debug(f"Set limit for {equipment_id}.{parameter}: {limit}")

    def remove_limit(
        self,
        equipment_id: str,
        parameter: str,
    ) -> bool:
        """移除限值

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            bool: 是否成功移除
        """
        if equipment_id in self._limits and parameter in self._limits[equipment_id]:
            del self._limits[equipment_id][parameter]
            return True
        return False

    def get_limits(self, equipment_id: str) -> Dict[str, Limit]:
        """获取设备的所有限值

        Args:
            equipment_id: 设备ID

        Returns:
            Dict[str, Limit]: 限值字典
        """
        return self._limits.get(equipment_id, {}).copy()

    def register_detector(
        self,
        parameter: str,
        detector: FaultDetector,
    ) -> None:
        """注册检测器

        Args:
            parameter: 参数名称
            detector: 检测器实例
        """
        self._detectors[parameter] = detector
        logger.debug(f"Registered detector for parameter: {parameter}")

    def set_baseline(
        self,
        equipment_id: str,
        parameter: str,
        baseline_data: np.ndarray,
    ) -> None:
        """设置基线数据

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            baseline_data: 基线数据
        """
        key = f"{equipment_id}:{parameter}"
        self._baselines[key] = baseline_data

        # 更新检测器基线
        detector = self._detectors.get(parameter)
        if detector:
            detector.update_baseline(baseline_data)

        logger.debug(f"Set baseline for {key}, size: {len(baseline_data)}")

    def get_baseline(
        self,
        equipment_id: str,
        parameter: str,
    ) -> Optional[np.ndarray]:
        """获取基线数据

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            Optional[np.ndarray]: 基线数据
        """
        key = f"{equipment_id}:{parameter}"
        return self._baselines.get(key)

    async def process_data(
        self,
        equipment_id: str,
        chamber_id: Optional[str],
        data: Dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> Optional[Fault]:
        """处理工艺数据

        Args:
            equipment_id: 设备ID
            chamber_id: 腔体ID
            data: 工艺数据字典
            timestamp: 时间戳

        Returns:
            Optional[Fault]: 检测到的故障（如果有）
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        faults = []

        # 1. 限值检查
        limit_violations = self._check_limits(equipment_id, data, timestamp)
        faults.extend(limit_violations)

        # 2. 统计检测
        for param, value in data.items():
            self._update_buffer(equipment_id, param, value)

        # 3. 特征提取和检测
        for param, value in data.items():
            buffer = self._feature_buffer.get(f"{equipment_id}:{param}")
            if buffer and len(buffer) >= self._min_window_size:
                feature_result = await self._detect_and_classify(
                    equipment_id, param, np.array(buffer), timestamp
                )
                if feature_result:
                    faults.append(feature_result)

        # 4. 触发回调
        primary_fault = None
        if faults:
            # 按严重程度排序
            faults.sort(key=lambda f: f.severity.priority)
            primary_fault = faults[0]

            # 更新统计数据
            self._fault_count += len(faults)
            for fault in faults:
                self._active_faults[fault.fault_id] = fault
                self._fault_history.append(fault)

            # 触发回调
            await self._notify_fault(primary_fault)

        return primary_fault

    def process_data_sync(
        self,
        equipment_id: str,
        chamber_id: Optional[str],
        data: Dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> Optional[Fault]:
        """同步处理工艺数据

        Args:
            equipment_id: 设备ID
            chamber_id: 腔体ID
            data: 工艺数据字典
            timestamp: 时间戳

        Returns:
            Optional[Fault]: 检测到的故障（如果有）
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        faults = []

        # 1. 限值检查
        limit_violations = self._check_limits_sync(equipment_id, data, timestamp)
        faults.extend(limit_violations)

        # 2. 统计检测
        for param, value in data.items():
            self._update_buffer(equipment_id, param, value)

        # 3. 特征提取和检测
        for param, value in data.items():
            buffer = self._feature_buffer.get(f"{equipment_id}:{param}")
            if buffer and len(buffer) >= self._min_window_size:
                feature_result = self._detect_and_classify_sync(
                    equipment_id, param, np.array(buffer), timestamp
                )
                if feature_result:
                    faults.append(feature_result)

        # 4. 触发回调
        primary_fault = None
        if faults:
            # 按严重程度排序
            faults.sort(key=lambda f: f.severity.priority)
            primary_fault = faults[0]

            # 更新统计数据
            self._fault_count += len(faults)
            for fault in faults:
                self._active_faults[fault.fault_id] = fault
                self._fault_history.append(fault)

            # 触发回调
            self._notify_fault_sync(primary_fault)

        return primary_fault

    def _check_limits(
        self,
        equipment_id: str,
        data: Dict[str, float],
        timestamp: datetime,
    ) -> List[Fault]:
        """检查限值

        Args:
            equipment_id: 设备ID
            data: 工艺数据
            timestamp: 时间戳

        Returns:
            List[Fault]: 检测到的故障列表
        """
        faults = []
        limits = self._limits.get(equipment_id, {})

        for param, value in data.items():
            limit = limits.get(param)
            if limit and self._check_limit(value, limit):
                fault = self._create_limit_fault(
                    equipment_id,
                    param,
                    value,
                    limit,
                    timestamp,
                )
                faults.append(fault)

        return faults

    def _check_limits_sync(
        self,
        equipment_id: str,
        data: Dict[str, float],
        timestamp: datetime,
    ) -> List[Fault]:
        """同步检查限值

        Args:
            equipment_id: 设备ID
            data: 工艺数据
            timestamp: 时间戳

        Returns:
            List[Fault]: 检测到的故障列表
        """
        return self._check_limits(equipment_id, data, timestamp)

    def _check_limit(self, value: float, limit: Limit) -> bool:
        """检查限值是否被突破

        Args:
            value: 当前值
            limit: 限值

        Returns:
            bool: 是否突破限值
        """
        if limit.limit_type == LimitType.UCL and value > limit.value:
            return True
        if limit.limit_type == LimitType.LCL and value < limit.value:
            return True
        if limit.limit_type == LimitType.USL and value > limit.value:
            return True
        if limit.limit_type == LimitType.LSL and value < limit.value:
            return True
        return False

    async def _detect_and_classify(
        self,
        equipment_id: str,
        parameter: str,
        data: np.ndarray,
        timestamp: datetime,
    ) -> Optional[Fault]:
        """检测和分类

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            data: 时间序列数据
            timestamp: 时间戳

        Returns:
            Optional[Fault]: 检测到的故障
        """
        # 获取或创建检测器
        detector = self._detectors.get(parameter)
        if not detector:
            detector = self._default_detector_factory()
            self._detectors[parameter] = detector

        # 获取基线
        baseline = self._baselines.get(f"{equipment_id}:{parameter}")

        # 检测
        result = detector.detect(data, baseline)
        if not result.is_anomaly or result.score < self._detection_threshold:
            return None

        # 提取特征
        features = FeatureVector.from_time_series(data)

        # 分类
        classification = self._classifier.classify(features)
        if classification.fault_type == FaultType.UNKNOWN:
            return None

        # 创建故障
        fault = self._create_feature_fault(
            equipment_id,
            parameter,
            features,
            classification,
            result,
            timestamp,
        )

        return fault

    def _detect_and_classify_sync(
        self,
        equipment_id: str,
        parameter: str,
        data: np.ndarray,
        timestamp: datetime,
    ) -> Optional[Fault]:
        """同步检测和分类

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            data: 时间序列数据
            timestamp: 时间戳

        Returns:
            Optional[Fault]: 检测到的故障
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行的事件循环，创建一个
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(
                self._detect_and_classify(equipment_id, parameter, data, timestamp)
            )
            loop.close()
            return result
        else:
            # 在事件循环中运行时，使用线程池执行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._detect_and_classify(equipment_id, parameter, data, timestamp)
                )
                return future.result()

    def _create_limit_fault(
        self,
        equipment_id: str,
        parameter: str,
        value: float,
        limit: Limit,
        timestamp: datetime,
    ) -> Fault:
        """创建限值违规故障

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            value: 当前值
            limit: 限值
            timestamp: 时间戳

        Returns:
            Fault: 故障对象
        """
        # 根据限值类型确定故障类型
        fault_type = self._infer_fault_type_from_limit(limit)
        severity = self._get_severity_from_limit(limit)

        return Fault(
            fault_id=str(uuid.uuid4()),
            fault_type=fault_type,
            severity=severity,
            equipment_id=equipment_id,
            start_time=timestamp,
            affected_parameters=[parameter],
            confidence=1.0,
            recommendations=self._classifier.get_recommendations(fault_type),
            metadata={
                "value": value,
                "limit_value": limit.value,
                "limit_type": limit.limit_type.value,
                "deviation": abs(value - limit.value),
            },
        )

    def _create_feature_fault(
        self,
        equipment_id: str,
        parameter: str,
        features: FeatureVector,
        classification: FaultClassification,
        detection_result: DetectionResult,
        timestamp: datetime,
    ) -> Fault:
        """创建特征检测故障

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            features: 特征向量
            classification: 分类结果
            detection_result: 检测结果
            timestamp: 时间戳

        Returns:
            Fault: 故障对象
        """
        return Fault(
            fault_id=str(uuid.uuid4()),
            fault_type=classification.fault_type,
            severity=self._infer_severity(classification.fault_type, features),
            equipment_id=equipment_id,
            start_time=timestamp,
            affected_parameters=[parameter],
            feature_vector=features.to_dict(),
            confidence=classification.confidence,
            recommendations=classification.matched_rule
            and self._classifier.get_recommendations(classification.fault_type)
            or [],
            metadata={
                "detection_score": detection_result.score,
                "matched_rule": classification.matched_rule,
                "anomaly_indices": detection_result.anomaly_indices,
            },
        )

    def _infer_fault_type_from_limit(self, limit: Limit) -> FaultType:
        """从限值推断故障类型

        Args:
            limit: 限值

        Returns:
            FaultType: 故障类型
        """
        param_name = limit.parameter_name.lower()

        if "temp" in param_name:
            return FaultType.TEMP_DRIFT
        elif "pressure" in param_name:
            return FaultType.PRESSURE_DRIFT
        elif "flow" in param_name:
            return FaultType.GAS_FLOW_ERROR
        elif "plasma" in param_name:
            return FaultType.PLASMA_UNSTABLE
        elif "rf" in param_name or "power" in param_name:
            return FaultType.RF_POWER_ERROR
        else:
            return FaultType.UNKNOWN

    def _get_severity_from_limit(self, limit: Limit) -> FaultSeverity:
        """从限值获取严重程度

        Args:
            limit: 限值

        Returns:
            FaultSeverity: 严重程度
        """
        if limit.severity == "critical":
            return FaultSeverity.CRITICAL
        elif limit.severity == "fatal":
            return FaultSeverity.FATAL
        elif limit.severity == "warning":
            return FaultSeverity.WARNING
        else:
            return FaultSeverity.INFO

    def _infer_severity(
        self,
        fault_type: FaultType,
        features: FeatureVector,
    ) -> FaultSeverity:
        """从特征推断严重程度

        Args:
            fault_type: 故障类型
            features: 特征向量

        Returns:
            FaultSeverity: 严重程度
        """
        # 等离子体熄灭是最严重的
        if fault_type == FaultType.PLASMA_EXTINCTION:
            return FaultSeverity.FATAL

        # 气体泄漏
        if fault_type == FaultType.GAS_LEAK:
            return FaultSeverity.CRITICAL

        # 基于稳定性评分判断
        if features.stability_score < 0.2:
            return FaultSeverity.CRITICAL
        elif features.stability_score < 0.4:
            return FaultSeverity.WARNING
        else:
            return FaultSeverity.INFO

    def _update_buffer(
        self,
        equipment_id: str,
        parameter: str,
        value: float,
    ) -> None:
        """更新特征缓冲区

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            value: 参数值
        """
        key = f"{equipment_id}:{parameter}"
        self._feature_buffer[key].append(value)

    async def _notify_fault(self, fault: Fault) -> None:
        """通知故障

        Args:
            fault: 故障对象
        """
        # 同步回调
        if self._on_fault:
            try:
                self._on_fault(fault)
            except Exception as e:
                logger.error(f"Error in fault callback: {e}")

        # 异步回调
        if self._on_fault_async:
            try:
                result = self._on_fault_async(fault)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in async fault callback: {e}")

        # 事件回调
        event = FDCEvent(
            event_type=FDCEventType.FAULT_DETECTED.value,
            equipment_id=fault.equipment_id,
            chamber_id=fault.chamber_id,
            fault=fault,
            data={"fault_type": fault.fault_type.value},
        )
        await self._notify_event(event)

    def _notify_fault_sync(self, fault: Fault) -> None:
        """同步通知故障

        Args:
            fault: 故障对象
        """
        if self._on_fault:
            try:
                self._on_fault(fault)
            except Exception as e:
                logger.error(f"Error in fault callback: {e}")

        if self._on_fault_async:
            try:
                result = self._on_fault_async(fault)
                if asyncio.iscoroutine(result):
                    asyncio.get_event_loop().run_until_complete(result)
            except Exception as e:
                logger.error(f"Error in async fault callback: {e}")

    async def _notify_event(self, event: FDCEvent) -> None:
        """通知事件

        Args:
            event: 事件对象
        """
        if self._on_event:
            try:
                self._on_event(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

        if self._on_event_async:
            try:
                result = self._on_event_async(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in async event callback: {e}")

    def resolve_fault(
        self,
        fault_id: str,
        end_time: Optional[datetime] = None,
    ) -> bool:
        """解决故障

        Args:
            fault_id: 故障ID
            end_time: 结束时间

        Returns:
            bool: 是否成功解决
        """
        fault = self._active_faults.get(fault_id)
        if not fault:
            return False

        fault.resolve(end_time)
        del self._active_faults[fault_id]

        logger.info(f"Fault resolved: {fault_id}")
        return True

    def dismiss_fault(
        self,
        fault_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """忽略故障

        Args:
            fault_id: 故障ID
            reason: 忽略原因

        Returns:
            bool: 是否成功忽略
        """
        fault = self._active_faults.get(fault_id)
        if not fault:
            return False

        fault.dismiss(reason)
        del self._active_faults[fault_id]

        logger.info(f"Fault dismissed: {fault_id}, reason: {reason}")
        return True

    @property
    def fault_count(self) -> int:
        """故障计数"""
        return self._fault_count

    @property
    def active_faults(self) -> List[Fault]:
        """活跃故障列表"""
        return list(self._active_faults.values())

    @property
    def fault_history(self) -> List[Fault]:
        """故障历史"""
        return self._fault_history.copy()

    def clear_history(self) -> None:
        """清除故障历史"""
        self._fault_history.clear()
        self._fault_count = 0

    def reset(self) -> None:
        """重置引擎状态"""
        self._detectors.clear()
        self._limits.clear()
        self._feature_buffer.clear()
        self._baselines.clear()
        self._active_faults.clear()
        self._fault_history.clear()
        self._fault_count = 0
        logger.info("FDC engine reset")
