"""根因分析模块测试

测试RootCauseAnalyzer、CausalGraph和PropagationPath。
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from myeap.ai.root_cause import (
    CausalGraph,
    EventCorrelation,
    PropagationPath,
    RootCauseAnalyzer,
    build_correlation_matrix,
    infer_propagation_path,
)


class TestRootCauseAnalyzerInit:
    """测试RootCauseAnalyzer初始化"""

    def test_creation(self):
        """测试创建"""
        rca = RootCauseAnalyzer()
        assert rca.min_correlation == 0.3
        assert rca.time_window_seconds == 3600
        assert rca.max_candidates == 5

    def test_creation_custom(self):
        """测试自定义参数创建"""
        rca = RootCauseAnalyzer(
            min_correlation=0.5,
            time_window_seconds=1800,
            max_candidates=10,
        )
        assert rca.min_correlation == 0.5
        assert rca.max_candidates == 10


class TestEventManagement:
    """测试事件管理"""

    def test_add_event(self):
        """测试添加事件"""
        rca = RootCauseAnalyzer()
        rca.add_event("eq-001", "temp_high", datetime.now(), 0.8)

        events = rca.get_recent_events("eq-001")
        assert len(events) == 1
        assert events[0][0] == "temp_high"

    def test_add_multiple_events(self):
        """测试添加多个事件"""
        rca = RootCauseAnalyzer()
        rca.add_event("eq-001", "temp_high", datetime.now(), 0.8)
        rca.add_event("eq-001", "pressure_low", datetime.now(), 0.6)
        rca.add_event("eq-001", "flow_error", datetime.now(), 0.7)

        events = rca.get_recent_events("eq-001")
        assert len(events) == 3

    def test_add_event_multi_equipment(self):
        """测试多设备事件"""
        rca = RootCauseAnalyzer()
        rca.add_event("eq-001", "temp_high", datetime.now(), 0.8)
        rca.add_event("eq-002", "vibration", datetime.now(), 0.5)

        assert len(rca.get_recent_events("eq-001")) == 1
        assert len(rca.get_recent_events("eq-002")) == 1

    def test_get_recent_events_time_filter(self):
        """测试时间过滤"""
        rca = RootCauseAnalyzer()
        now = datetime.now()

        # 添加一个较早的事件
        rca.add_event("eq-001", "old_event", now - timedelta(hours=5), 0.5)
        # 添加一个最近的事件
        rca.add_event("eq-001", "new_event", now - timedelta(minutes=10), 0.8)

        # 只获取1小时内的
        recent = rca.get_recent_events("eq-001", time_window_seconds=3600)
        assert len(recent) == 1
        assert recent[0][0] == "new_event"

    def test_get_recent_events_empty(self):
        """测试获取不存在设备的事件"""
        rca = RootCauseAnalyzer()
        events = rca.get_recent_events("eq-unknown")
        assert len(events) == 0


class TestAnalyze:
    """测试根因分析"""

    def test_analyze_no_events(self):
        """测试无事件的分析"""
        rca = RootCauseAnalyzer()
        result = rca.analyze("incident-001")

        assert result.incident_id == "incident-001"
        assert len(result.root_causes) == 0

    def test_analyze_single_event(self):
        """测试单个事件的分析"""
        rca = RootCauseAnalyzer()
        rca.add_event("eq-001", "temp_high", datetime.now(), 0.8)

        result = rca.analyze("incident-001", equipment_id="eq-001")

        assert result.incident_id == "incident-001"
        assert result.has_root_cause

    def test_analyze_multiple_events(self):
        """测试多个事件的分析"""
        rca = RootCauseAnalyzer()
        base_time = datetime.now()

        # 按时间顺序添加事件(模拟传播)
        rca.add_event("eq-001", "power_fluctuation", base_time, 0.9)
        rca.add_event("eq-001", "temp_high", base_time + timedelta(minutes=5), 0.7)
        rca.add_event("eq-001", "pressure_drop", base_time + timedelta(minutes=10), 0.6)
        rca.add_event("eq-001", "shutdown", base_time + timedelta(minutes=15), 1.0)

        result = rca.analyze("incident-001", equipment_id="eq-001")

        assert result.incident_id == "incident-001"
        assert result.has_root_cause
        assert len(result.propagation_path) > 0

    def test_analyze_with_time_range(self):
        """测试带时间范围的分析"""
        rca = RootCauseAnalyzer()
        now = datetime.now()

        # 旧事件
        rca.add_event("eq-001", "old_temp", now - timedelta(hours=5), 0.8)
        # 新事件
        rca.add_event("eq-001", "new_temp", now - timedelta(minutes=10), 0.9)

        result = rca.analyze(
            "incident-001",
            equipment_id="eq-001",
            time_range=(now - timedelta(hours=1), now),
        )

        assert result.incident_id == "incident-001"

    def test_analyze_multi_equipment(self):
        """测试多设备分析"""
        rca = RootCauseAnalyzer()
        base_time = datetime.now()

        rca.add_event("eq-001", "temp_high", base_time, 0.8)
        rca.add_event("eq-002", "vibration", base_time + timedelta(minutes=2), 0.6)

        result = rca.analyze_multi_equipment("incident-001", ["eq-001", "eq-002"])

        assert result.incident_id == "incident-001"
        assert result.analysis_time is not None

    def test_analyze_returns_evidence(self):
        """测试分析返回证据"""
        rca = RootCauseAnalyzer()
        base_time = datetime.now()

        rca.add_event("eq-001", "temp_high", base_time, 0.8)
        rca.add_event("eq-001", "pressure_drop", base_time + timedelta(minutes=5), 0.6)

        result = rca.analyze("incident-001", equipment_id="eq-001")

        assert len(result.evidence) > 0


class TestCausalGraph:
    """测试因果图"""

    def test_creation(self):
        """测试创建因果图"""
        graph = CausalGraph(
            nodes=["A", "B", "C"],
            edges=[("A", "B", 0.8), ("B", "C", 0.6)],
            root_candidates=[("A", 0.8)],
        )

        assert graph.node_count == 3
        assert graph.edge_count == 2

    def test_get_children(self):
        """测试获取子节点"""
        graph = CausalGraph(
            nodes=["A", "B", "C"],
            edges=[("A", "B", 0.8), ("A", "C", 0.5)],
        )

        children = graph.get_children("A")
        assert len(children) == 2

    def test_get_parents(self):
        """测试获取父节点"""
        graph = CausalGraph(
            nodes=["A", "B", "C"],
            edges=[("A", "B", 0.8), ("A", "C", 0.5)],
        )

        parents = graph.get_parents("B")
        assert len(parents) == 1
        assert parents[0][0] == "A"

    def test_is_root_cause(self):
        """测试根因判断"""
        graph = CausalGraph(
            nodes=["A", "B", "C"],
            edges=[("A", "B", 0.8), ("B", "C", 0.6)],
        )

        assert graph.is_root_cause("A") is True
        assert graph.is_root_cause("B") is False
        assert graph.is_root_cause("C") is False

    def test_no_parents_not_root(self):
        """测试无父节点但有子节点"""
        graph = CausalGraph(
            nodes=["A", "B"],
        )
        # 没有边，A没有父节点也没有子节点
        assert graph.is_root_cause("A") is False

    def test_to_dict(self):
        """测试转换为字典"""
        graph = CausalGraph(
            nodes=["A", "B"],
            edges=[("A", "B", 0.9)],
            root_candidates=[("A", 0.9)],
        )
        d = graph.to_dict()
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1
        assert len(d["root_candidates"]) == 1


class TestPropagationPath:
    """测试传播路径"""

    def test_creation(self):
        """测试创建传播路径"""
        path = PropagationPath(
            path=["power_fault", "temp_rise", "shutdown"],
            confidence=0.85,
            start_node="power_fault",
            end_node="shutdown",
            total_time_span_seconds=600.0,
        )

        assert path.depth == 3
        assert path.start_node == "power_fault"

    def test_empty_path(self):
        """测试空路径"""
        path = PropagationPath()
        assert path.depth == 0

    def test_to_dict(self):
        """测试转换为字典"""
        path = PropagationPath(
            path=["A", "B", "C"],
            confidence=0.9,
            start_node="A",
            end_node="C",
        )
        d = path.to_dict()
        assert d["depth"] == 3
        assert d["confidence"] == 0.9


class TestInferPropagationPath:
    """测试推断传播路径"""

    def test_infer_single_event(self):
        """测试单事件路径推断"""
        events = [("temp_high", datetime.now(), 0.8)]
        path = infer_propagation_path(events)
        assert len(path.path) == 1
        assert path.confidence == 0.0

    def test_infer_multiple_events(self):
        """测试多事件路径推断"""
        now = datetime.now()
        events = [
            ("power_issue", now, 0.9),
            ("temp_rise", now + timedelta(minutes=2), 0.7),
            ("alarm", now + timedelta(minutes=5), 0.8),
        ]
        path = infer_propagation_path(events)
        assert len(path.path) == 3
        assert path.start_node == "power_issue"


class TestCorrelationMatrix:
    """测试关联矩阵"""

    def test_build_correlation_matrix_empty(self):
        """测试空关联矩阵"""
        matrix = build_correlation_matrix({})
        assert matrix.size == 0

    def test_build_correlation_matrix(self):
        """测试构建关联矩阵"""
        now = datetime.now()
        event_series = {
            "temp": [(now + timedelta(minutes=i), 0.7 + i * 0.01) for i in range(10)],
            "pressure": [(now + timedelta(minutes=i), 0.6 + i * 0.02) for i in range(10)],
        }

        matrix = build_correlation_matrix(event_series)
        assert matrix.shape == (2, 2)
        # 对角线应为1
        assert abs(matrix[0, 0] - 1.0) < 0.01
        assert abs(matrix[1, 1] - 1.0) < 0.01


class TestEventCorrelation:
    """测试事件关联"""

    def test_creation(self):
        """测试创建事件关联"""
        corr = EventCorrelation(
            event_a="temp_high",
            event_b="shutdown",
            correlation_score=0.8,
            time_lag=300.0,
            direction="a_to_b",
        )
        assert corr.is_significant is True

    def test_not_significant(self):
        """测试不显著的关联"""
        corr = EventCorrelation(
            event_a="A",
            event_b="B",
            correlation_score=0.1,
            direction="none",
        )
        assert corr.is_significant is False


class TestHistoryAndReset:
    """测试历史和重置"""

    def test_get_history(self):
        """测试获取历史"""
        rca = RootCauseAnalyzer()
        rca.add_event("eq-001", "temp_high", datetime.now(), 0.8)

        rca.analyze("incident-001", equipment_id="eq-001")
        rca.analyze("incident-002", equipment_id="eq-001")

        history = rca.get_history()
        assert len(history) == 2

    def test_get_causal_graph(self):
        """测试获取因果图"""
        rca = RootCauseAnalyzer()
        rca.add_event("eq-001", "temp_high", datetime.now(), 0.8)
        rca.add_event("eq-001", "shutdown", datetime.now(), 1.0)

        rca.analyze("incident-001", equipment_id="eq-001")

        graph = rca.get_causal_graph()
        assert graph is not None
        assert graph.node_count > 0

    def test_reset(self):
        """测试重置"""
        rca = RootCauseAnalyzer()
        rca.add_event("eq-001", "temp_high", datetime.now(), 0.8)
        rca.analyze("incident-001", equipment_id="eq-001")

        assert len(rca.get_history()) == 1

        rca.reset()

        assert len(rca.get_history()) == 0
        assert len(rca._events) == 0


def run_all_tests():
    """运行所有测试"""
    test_classes = [
        TestRootCauseAnalyzerInit,
        TestEventManagement,
        TestAnalyze,
        TestCausalGraph,
        TestPropagationPath,
        TestInferPropagationPath,
        TestCorrelationMatrix,
        TestEventCorrelation,
        TestHistoryAndReset,
    ]

    passed = 0
    failed = 0
    errors = []

    for test_class in test_classes:
        print(f"\n=== {test_class.__name__} ===")
        instance = test_class()

        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    method = getattr(instance, method_name)
                    method()
                    print(f"  PASS: {method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  FAIL: {method_name}: {e}")
                    failed += 1
                    errors.append((test_class.__name__, method_name, str(e)))

    print(f"\n{'='*50}")
    print(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")

    if errors:
        print("\nFailed tests:")
        for cls_name, method_name, error in errors:
            print(f"  {cls_name}.{method_name}: {error}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
