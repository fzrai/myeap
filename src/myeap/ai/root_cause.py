"""根因分析模块

使用关联分析和因果推断定位故障根因。

主要功能：
- 时序相关性分析
- 异常传播路径推断
- 根因候选排序

Example:
    >>> import numpy as np
    >>> from myeap.ai.root_cause import RootCauseAnalyzer
    >>> rca = RootCauseAnalyzer()
    >>> rca.add_event("eq-001", "temp_high", datetime.now(), 0.8)
    >>> result = rca.analyze("incident-001", events)
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

import numpy as np

from myeap.ai.models import RootCauseResult, AnalysisStatus

logger = logging.getLogger(__name__)


@dataclass
class EventCorrelation:
    """事件关联

    表示两个事件之间的关联关系。

    Attributes:
        event_a: 事件A标识
        event_b: 事件B标识
        correlation_score: 关联分数 (-1 到 1)
        time_lag: 时间延迟(秒)
        direction: 因果方向 (a_to_b, b_to_a, bidirectional, none)
    """

    event_a: str
    event_b: str
    correlation_score: float
    time_lag: float = 0.0
    direction: str = "none"

    @property
    def is_significant(self) -> bool:
        """是否为显著关联"""
        return abs(self.correlation_score) >= 0.3


@dataclass
class PropagationPath:
    """异常传播路径

    表示异常在系统中传播的路径。

    Attributes:
        path: 传播路径节点列表
        confidence: 传播路径置信度
        start_node: 起始节点 (根因候选)
        end_node: 结束节点
        total_time_span_seconds: 总传播时间
    """

    path: List[str] = field(default_factory=list)
    confidence: float = 0.0
    start_node: str = ""
    end_node: str = ""
    total_time_span_seconds: float = 0.0

    @property
    def depth(self) -> int:
        """传播深度"""
        return len(self.path)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "path": self.path,
            "confidence": self.confidence,
            "start_node": self.start_node,
            "end_node": self.end_node,
            "depth": self.depth,
            "total_time_span_seconds": self.total_time_span_seconds,
        }


@dataclass
class CausalGraph:
    """因果图

    表示事件之间的因果关系网络。

    Attributes:
        nodes: 节点列表
        edges: 边列表 [(from, to, weight), ...]
        root_candidates: 根因候选节点
    """

    nodes: List[str] = field(default_factory=list)
    edges: List[Tuple[str, str, float]] = field(default_factory=list)
    root_candidates: List[Tuple[str, float]] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        """节点数量"""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """边数量"""
        return len(self.edges)

    def get_children(self, node: str) -> List[Tuple[str, float]]:
        """获取节点的子节点

        Args:
            node: 节点名称

        Returns:
            List[Tuple[str, float]]: (子节点, 权重)
        """
        return [(to_node, weight) for from_node, to_node, weight in self.edges if from_node == node]

    def get_parents(self, node: str) -> List[Tuple[str, float]]:
        """获取节点的父节点

        Args:
            node: 节点名称

        Returns:
            List[Tuple[str, float]]: (父节点, 权重)
        """
        return [(from_node, weight) for from_node, to_node, weight in self.edges if to_node == node]

    def is_root_cause(self, node: str) -> bool:
        """判断节点是否为根因候选

        Args:
            node: 节点名称

        Returns:
            bool: 是否为根因候选
        """
        return len(self.get_parents(node)) == 0 and len(self.get_children(node)) > 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "nodes": self.nodes,
            "edges": [
                {"from": f, "to": t, "weight": w} for f, t, w in self.edges
            ],
            "root_candidates": [
                {"node": n, "confidence": c} for n, c in self.root_candidates
            ],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }


def build_correlation_matrix(
    event_series: Dict[str, List[Tuple[datetime, float]]],
    time_window_seconds: float = 300,
) -> np.ndarray:
    """构建事件关联矩阵

    计算各事件序列之间的时序相关性。

    Args:
        event_series: {event_name: [(timestamp, value), ...]} 字典
        time_window_seconds: 时间窗口(秒)

    Returns:
        np.ndarray: 关联矩阵 (n_events x n_events)
    """
    event_names = list(event_series.keys())
    n = len(event_names)

    if n == 0:
        return np.array([[]])

    # 对齐时间序列
    aligned_series = {}
    base_time = None
    for name, series in event_series.items():
        if series:
            times = [t.timestamp() for t, _ in series]
            if base_time is None:
                base_time = min(times)
            aligned_series[name] = {
                (t.timestamp() - base_time) / time_window_seconds: v
                for t, v in series
            }

    # 计算关联矩阵
    corr_matrix = np.zeros((n, n))

    for i, name_i in enumerate(event_names):
        for j, name_j in enumerate(event_names):
            if i == j:
                corr_matrix[i, j] = 1.0
                continue

            series_i = event_series.get(name_i, [])
            series_j = event_series.get(name_j, [])

            if len(series_i) >= 3 and len(series_j) >= 3:
                values_i = np.array([v for _, v in series_i[:min(len(series_i), len(series_j))]])
                values_j = np.array([v for _, v in series_j[:min(len(series_i), len(series_j))]])
                min_len = min(len(values_i), len(values_j))
                if min_len > 1:
                    corr = np.corrcoef(values_i[:min_len], values_j[:min_len])[0, 1]
                    corr_matrix[i, j] = float(corr) if not np.isnan(corr) else 0.0
            else:
                corr_matrix[i, j] = 0.0

    return corr_matrix


def infer_propagation_path(
    events: List[Tuple[str, datetime, float]],
    correlation_min: float = 0.3,
    max_depth: int = 10,
) -> PropagationPath:
    """推断异常传播路径

    基于事件时序和相关性推断异常传播路径。

    Args:
        events: [(event_type, timestamp, severity), ...] 事件列表
        correlation_min: 最小相关性阈值
        max_depth: 最大传播深度

    Returns:
        PropagationPath: 传播路径
    """
    if len(events) < 2:
        return PropagationPath(path=[e[0] for e in events], confidence=0.0)

    # 按时间排序
    sorted_events = sorted(events, key=lambda x: x[1])

    path = []
    confidences = []

    # 构建时序路径
    for event_type, ts, severity in sorted_events:
        path.append(event_type)

    # 计算相邻事件间的关联置信度
    for i in range(len(sorted_events) - 1):
        _, ts1, s1 = sorted_events[i]
        _, ts2, s2 = sorted_events[i + 1]

        # 时间间隔
        time_diff = abs((ts2 - ts1).total_seconds())

        # 基于时间接近度和严重程度关联的置信度
        if time_diff < 60:  # 1分钟内
            conf = 0.9
        elif time_diff < 300:  # 5分钟内
            conf = 0.7
        elif time_diff < 900:  # 15分钟内
            conf = 0.5
        else:
            conf = max(0.0, 0.3 - time_diff / 3600)

        # 考虑严重程度的相似性
        severity_sim = 1.0 - abs(s1 - s2)
        conf = conf * 0.6 + severity_sim * 0.4

        confidences.append(conf)

    avg_confidence = float(np.mean(confidences)) if confidences else 0.0

    return PropagationPath(
        path=path,
        confidence=avg_confidence,
        start_node=path[0] if path else "",
        end_node=path[-1] if path else "",
        total_time_span_seconds=(
            (sorted_events[-1][1] - sorted_events[0][1]).total_seconds()
            if len(sorted_events) > 1
            else 0.0
        ),
    )


class RootCauseAnalyzer:
    """根因分析器

    使用关联分析和因果推断定位故障根因。

    Attributes:
        min_correlation: 最小关联阈值
        time_window_seconds: 时间窗口
        max_candidates: 最大根因候选数

    Example:
        >>> rca = RootCauseAnalyzer()
        >>> rca.add_event("eq-001", "temp_high", datetime.now(), 0.8)
        >>> rca.add_event("eq-001", "pressure_low", datetime.now(), 0.6)
        >>> result = rca.analyze("incident-001")
    """

    def __init__(
        self,
        min_correlation: float = 0.3,
        time_window_seconds: float = 3600,
        max_candidates: int = 5,
    ):
        """初始化根因分析器

        Args:
            min_correlation: 最小关联阈值
            time_window_seconds: 时间窗口(秒)
            max_candidates: 最大根因候选数
        """
        self.min_correlation = min_correlation
        self.time_window_seconds = time_window_seconds
        self.max_candidates = max_candidates

        # 事件存储: {equipment_id: [(event_type, timestamp, severity, metadata), ...]}
        self._events: Dict[str, List[Tuple[str, datetime, float, Dict[str, Any]]]] = defaultdict(list)

        # 关联分析缓存
        self._correlations: Dict[str, EventCorrelation] = {}

        # 因果图
        self._causal_graphs: Dict[str, CausalGraph] = {}

        # 历史根因
        self._root_cause_history: List[RootCauseResult] = []

    def add_event(
        self,
        equipment_id: str,
        event_type: str,
        timestamp: Optional[datetime] = None,
        severity: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """添加事件

        Args:
            equipment_id: 设备标识
            event_type: 事件类型
            timestamp: 时间戳 (默认当前时间)
            severity: 严重程度 (0-1)
            metadata: 附加元数据
        """
        ts = timestamp or datetime.now()
        self._events[equipment_id].append(
            (event_type, ts, float(np.clip(severity, 0, 1)), metadata or {})
        )

        # 保持事件缓冲区在合理大小
        if len(self._events[equipment_id]) > 1000:
            self._events[equipment_id] = self._events[equipment_id][-1000:]

        logger.debug(f"Event added: {equipment_id}/{event_type} severity={severity:.2f}")

    def get_recent_events(
        self,
        equipment_id: str,
        time_window_seconds: Optional[float] = None,
    ) -> List[Tuple[str, datetime, float, Dict[str, Any]]]:
        """获取最近的事件

        Args:
            equipment_id: 设备标识
            time_window_seconds: 时间窗口(秒)，默认使用引擎配置

        Returns:
            List: 事件列表
        """
        events = self._events.get(equipment_id, [])
        if not events:
            return []

        window = time_window_seconds or self.time_window_seconds
        now = datetime.now()
        cutoff = now - timedelta(seconds=window)

        return [e for e in events if e[1] >= cutoff]

    def analyze(
        self,
        incident_id: str,
        equipment_id: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> RootCauseResult:
        """执行根因分析

        Args:
            incident_id: 事件标识
            equipment_id: 设备标识 (可选)
            time_range: 时间范围 (可选)

        Returns:
            RootCauseResult: 根因分析结果
        """
        # 收集相关事件
        all_events = []

        if equipment_id:
            events = self._events.get(equipment_id, [])
        else:
            events = []
            for eq_events in self._events.values():
                events.extend(eq_events)

        # 按时间过滤
        if time_range:
            start, end = time_range
            events = [e for e in events if start <= e[1] <= end]
        else:
            events = events[-100:]  # 取最近100个事件

        if not events:
            return RootCauseResult(
                incident_id=incident_id,
                root_causes=[],
                analysis_time=datetime.now(),
            )

        # 1. 计算事件间的相关性
        correlation_matrix = self._compute_event_correlations(events)

        # 2. 构建因果图
        causal_graph = self._build_causal_graph(events, correlation_matrix)

        # 3. 推断传播路径
        propagation = infer_propagation_path(
            [(e[0], e[1], e[2]) for e in events],
            correlation_min=self.min_correlation,
        )

        # 4. 排序根因候选
        root_causes = self._rank_root_causes(causal_graph, events)

        # 5. 收集证据
        evidence = self._collect_evidence(events, root_causes)

        result = RootCauseResult(
            incident_id=incident_id,
            root_causes=root_causes[:self.max_candidates],
            propagation_path=propagation.path,
            correlation_scores={
                f"{e1[0]}->{e2[0]}": r
                for e1, e2, r in self._pairwise_correlations(events, correlation_matrix)
            },
            analysis_time=datetime.now(),
            evidence=evidence,
        )

        self._root_cause_history.append(result)
        logger.info(f"Root cause analysis completed for {incident_id}: {len(root_causes)} candidates")

        return result

    def analyze_multi_equipment(
        self,
        incident_id: str,
        equipment_ids: List[str],
    ) -> RootCauseResult:
        """多设备联合根因分析

        跨设备分析，识别系统级根因。

        Args:
            incident_id: 事件标识
            equipment_ids: 设备标识列表

        Returns:
            RootCauseResult: 根因分析结果
        """
        all_events = []
        for eq_id in equipment_ids:
            eq_events = self._events.get(eq_id, [])
            all_events.extend([(eq_id, e[0], e[1], e[2]) for e in eq_events[-50:]])

        if not all_events:
            return RootCauseResult(incident_id=incident_id, analysis_time=datetime.now())

        # 转换为统一格式
        unified_events = [(f"{eq}:{etype}", ts, sev) for eq, etype, ts, sev in all_events]

        # 使用统一分析
        events_for_analyze = [(f"{eq}:{etype}", ts, sev, {}) for eq, etype, ts, sev in all_events]

        correlation_matrix = self._compute_event_correlations(events_for_analyze)
        causal_graph = self._build_causal_graph(events_for_analyze, correlation_matrix)
        root_causes = self._rank_root_causes(causal_graph, events_for_analyze)

        propagation = infer_propagation_path(
            unified_events,
            correlation_min=self.min_correlation,
        )

        return RootCauseResult(
            incident_id=incident_id,
            root_causes=root_causes[:self.max_candidates],
            propagation_path=propagation.path,
            correlation_scores={
                f"{e1[0]}->{e2[0]}": r
                for e1, e2, r in self._pairwise_correlations(
                    events_for_analyze, correlation_matrix
                )
            },
            analysis_time=datetime.now(),
            evidence=[f"Cross-equipment analysis: {len(equipment_ids)} equipment"],
        )

    def _compute_event_correlations(
        self,
        events: List[Tuple[str, datetime, float, Dict[str, Any]]],
    ) -> np.ndarray:
        """计算事件相关性矩阵

        Args:
            events: 事件列表

        Returns:
            np.ndarray: 相关性矩阵
        """
        n = len(events)
        if n == 0:
            return np.array([[]])

        # 提取严重程度
        severities = np.array([e[2] for e in events])

        # 基于严重程度和时序的相关性
        corr_matrix = np.eye(n)

        for i in range(n):
            for j in range(i + 1, n):
                # 时间差
                time_diff = abs((events[i][1] - events[j][1]).total_seconds())

                # 事件类型相似度 (字符重叠度)
                type_i = events[i][0]
                type_j = events[j][0]
                overlap = len(set(type_i.lower()) & set(type_j.lower())) / max(
                    len(set(type_i.lower())), len(set(type_j.lower())), 1
                )

                # 基于时间、严重程度和类型的综合相关性
                time_weight = np.exp(-time_diff / self.time_window_seconds)
                severity_sim = 1.0 - abs(float(severities[i]) - float(severities[j]))
                type_sim = overlap

                corr = time_weight * 0.4 + severity_sim * 0.4 + type_sim * 0.2
                corr_matrix[i, j] = corr
                corr_matrix[j, i] = corr

        return corr_matrix

    def _build_causal_graph(
        self,
        events: List[Tuple[str, datetime, float, Dict[str, Any]]],
        correlation_matrix: np.ndarray,
    ) -> CausalGraph:
        """构建因果图

        Args:
            events: 事件列表
            correlation_matrix: 相关性矩阵

        Returns:
            CausalGraph: 因果图
        """
        n = len(events)
        # 提取唯一的节点名称 (事件类型)
        node_map = {}
        for i, e in enumerate(events):
            node_type = e[0]
            if node_type not in node_map:
                node_map[node_type] = []
            node_map[node_type].append(i)

        nodes = list(node_map.keys())
        edges = []

        # 建立因果关系边 (根据时间顺序)
        sorted_indices = sorted(range(n), key=lambda i: events[i][1])

        for a_idx in range(len(sorted_indices)):
            for b_idx in range(a_idx + 1, len(sorted_indices)):
                i = sorted_indices[a_idx]
                j = sorted_indices[b_idx]

                corr = correlation_matrix[i, j]
                if abs(corr) >= self.min_correlation:
                    from_node = events[i][0]
                    to_node = events[j][0]
                    time_diff = (events[j][1] - events[i][1]).total_seconds()
                    weight = corr * np.exp(-time_diff / self.time_window_seconds)
                    edges.append((from_node, to_node, float(weight)))

        # 识别根因候选
        has_incoming = {node: False for node in nodes}
        for _, to_node, _ in edges:
            has_incoming[to_node] = True

        root_candidates = []
        for node in nodes:
            if not has_incoming[node]:
                # 计算该节点的异常分数作为置信度
                node_events = [events[i] for i in node_map[node]]
                avg_severity = float(np.mean([e[2] for e in node_events])) if node_events else 0.0
                if avg_severity > 0.3:
                    root_candidates.append((node, avg_severity))

        root_candidates.sort(key=lambda x: x[1], reverse=True)

        graph = CausalGraph(
            nodes=nodes,
            edges=edges,
            root_candidates=root_candidates,
        )

        self._causal_graphs["latest"] = graph
        return graph

    def _rank_root_causes(
        self,
        causal_graph: CausalGraph,
        events: List[Tuple[str, datetime, float, Dict[str, Any]]],
    ) -> List[Tuple[str, float]]:
        """排序根因候选

        基于因果图结构和事件严重性排序根因。

        Args:
            causal_graph: 因果图
            events: 事件列表

        Returns:
            List[Tuple[str, float]]: 排序后的(根因, 置信度)列表
        """
        # 使用因果图的根因候选
        scored = {}

        for node, base_confidence in causal_graph.root_candidates:
            # 加分: 如果节点是多个节点的上游
            children = causal_graph.get_children(node)
            influence_score = base_confidence + 0.05 * len(children)
            scored[node] = min(1.0, influence_score)

        # 如果没有明确的根因候选，从事件中找最早的高严重性事件
        if not scored:
            sorted_by_time = sorted(events, key=lambda e: e[1])
            for event_type, ts, severity, meta in sorted_by_time:
                if severity >= 0.5 or len(scored) == 0:
                    if event_type not in scored:
                        scored[event_type] = severity

        # 按分数降序排序
        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)
        return ranked

    def _pairwise_correlations(
        self,
        events: List[Tuple[str, datetime, float, Dict[str, Any]]],
        correlation_matrix: np.ndarray,
    ) -> List[Tuple[Any, Any, float]]:
        """生成成对相关性列表

        Args:
            events: 事件列表
            correlation_matrix: 相关性矩阵

        Returns:
            List[Tuple]: (事件A, 事件B, 相关性)
        """
        results = []
        n = len(events)
        for i in range(n):
            for j in range(i + 1, n):
                r = correlation_matrix[i, j]
                if abs(r) >= self.min_correlation:
                    results.append((events[i], events[j], float(r)))
        return results

    def _collect_evidence(
        self,
        events: List[Tuple[str, datetime, float, Dict[str, Any]]],
        root_causes: List[Tuple[str, float]],
    ) -> List[str]:
        """收集支持证据

        Args:
            events: 事件列表
            root_causes: 根因候选

        Returns:
            List[str]: 证据描述列表
        """
        evidence = []

        if not events:
            evidence.append("没有足够的事件数据进行分析")
            return evidence

        # 事件数量证据
        evidence.append(f"分析基于 {len(events)} 个事件")

        # 时间跨度
        timestamps = [e[1] for e in events]
        if len(timestamps) > 1:
            time_span = max(timestamps) - min(timestamps)
            evidence.append(f"事件时间跨度: {time_span}")

        # 最高严重性事件
        max_severity_event = max(events, key=lambda e: e[2])
        evidence.append(f"最高严重性事件: {max_severity_event[0]} (严重程度: {max_severity_event[2]:.2f})")

        # 跟因相关证据
        for cause, conf in root_causes[:3]:
            cause_events = [e for e in events if e[0] == cause]
            if cause_events:
                first_time = min(e[1] for e in cause_events)
                evidence.append(f"根因候选 '{cause}' 首次出现时间: {first_time.isoformat()}")

        return evidence

    def get_causal_graph(self) -> Optional[CausalGraph]:
        """获取最新的因果图

        Returns:
            Optional[CausalGraph]: 因果图
        """
        return self._causal_graphs.get("latest")

    def get_history(self) -> List[RootCauseResult]:
        """获取分析历史

        Returns:
            List[RootCauseResult]: 历史分析结果
        """
        return self._root_cause_history.copy()

    def reset(self) -> None:
        """重置分析器状态"""
        self._events.clear()
        self._correlations.clear()
        self._causal_graphs.clear()
        self._root_cause_history.clear()
        logger.info("RootCauseAnalyzer reset")
