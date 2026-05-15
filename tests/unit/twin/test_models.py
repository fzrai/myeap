"""数字孪生模型测试"""

import pytest
from datetime import datetime

from myeap.twin.models import (
    TwinState,
    TwinHealth,
    HealthStatus,
    RiskLevel,
    SimulationStep,
    SimulationResult,
    SimulationScenario,
    TwinEvent,
)


class TestHealthStatus:
    """健康状态枚举测试"""

    def test_status_values(self):
        """测试健康状态值"""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.NORMAL.value == "normal"
        assert HealthStatus.ATTENTION.value == "attention"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.CRITICAL.value == "critical"
        assert HealthStatus.UNKNOWN.value == "unknown"

    def test_status_count(self):
        """测试健康状态数量"""
        assert len(HealthStatus) == 6


class TestRiskLevel:
    """风险等级枚举测试"""

    def test_risk_values(self):
        """测试风险等级值"""
        assert RiskLevel.NONE.value == "none"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_priority(self):
        """测试风险优先级"""
        assert RiskLevel.CRITICAL.priority == 1
        assert RiskLevel.HIGH.priority == 2
        assert RiskLevel.MEDIUM.priority == 3
        assert RiskLevel.LOW.priority == 4
        assert RiskLevel.NONE.priority == 5

    def test_priority_ordering(self):
        """测试风险排序"""
        risks = [
            RiskLevel.NONE,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]
        sorted_risks = sorted(risks, key=lambda r: r.priority)
        assert sorted_risks == [
            RiskLevel.CRITICAL,
            RiskLevel.HIGH,
            RiskLevel.MEDIUM,
            RiskLevel.LOW,
            RiskLevel.NONE,
        ]

    def test_risk_count(self):
        """测试风险等级数量"""
        assert len(RiskLevel) == 5


class TestTwinState:
    """虚拟状态测试"""

    def test_create_twin_state(self):
        """测试创建虚拟状态"""
        ts = datetime.utcnow()
        state = TwinState(
            equipment_id="eq-001",
            timestamp=ts,
            status="IDLE",
            sensor_data={"Temperature": 25.0, "Pressure": 1.0},
        )
        assert state.equipment_id == "eq-001"
        assert state.status == "IDLE"
        assert state.timestamp == ts
        assert state.sensor_data["Temperature"] == 25.0

    def test_default_values(self):
        """测试默认值"""
        state = TwinState(
            equipment_id="eq-002",
            timestamp=datetime.utcnow(),
        )
        assert state.chambers == {}
        assert state.status == "UNKNOWN"
        assert state.sub_status is None
        assert state.alarms == []
        assert state.sensor_data == {}
        assert state.metadata == {}

    def test_to_dict(self):
        """测试转换为字典"""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        state = TwinState(
            equipment_id="eq-003",
            timestamp=ts,
            chambers={"ch-1": {"Temp": 100.0}},
            status="RUNNING",
            sensor_data={"Temp": 100.0},
        )
        d = state.to_dict()
        assert d["equipment_id"] == "eq-003"
        assert d["status"] == "RUNNING"
        assert "ch-1" in d["chambers"]

    def test_repr(self):
        """测试字符串表示"""
        state = TwinState(
            equipment_id="eq-004",
            timestamp=datetime.utcnow(),
            sensor_data={"Temp": 25.0, "Pressure": 1.0},
        )
        r = repr(state)
        assert "eq-004" in r
        assert "sensors=2" in r

    def test_chambers_dict(self):
        """测试腔体状态"""
        state = TwinState(
            equipment_id="eq-005",
            timestamp=datetime.utcnow(),
            chambers={"ch-1": {"Temp": 100.0}, "ch-2": {"Press": 5.0}},
        )
        assert len(state.chambers) == 2
        assert state.chambers["ch-1"]["Temp"] == 100.0

    def test_alarms_list(self):
        """测试告警列表"""
        state = TwinState(
            equipment_id="eq-006",
            timestamp=datetime.utcnow(),
            alarms=[{"type": "high_temp", "value": 120}],
        )
        assert len(state.alarms) == 1
        assert state.alarms[0]["type"] == "high_temp"


class TestTwinHealth:
    """健康评估测试"""

    def test_create_health(self):
        """测试创建健康评估"""
        health = TwinHealth(
            equipment_id="eq-001",
            overall_score=95.0,
            component_scores={"Temp": 95.0, "Pressure": 92.0},
            confidence=0.95,
        )
        assert health.equipment_id == "eq-001"
        assert health.overall_score == 95.0
        assert health.status == HealthStatus.HEALTHY
        assert health.confidence == 0.95

    def test_status_healthy(self):
        """测试健康状态映射 - 健康"""
        health = TwinHealth(equipment_id="eq-001", overall_score=95.0)
        assert health.status == HealthStatus.HEALTHY

    def test_status_normal(self):
        """测试健康状态映射 - 正常"""
        health = TwinHealth(equipment_id="eq-001", overall_score=85.0)
        assert health.status == HealthStatus.NORMAL

    def test_status_attention(self):
        """测试健康状态映射 - 需关注"""
        health = TwinHealth(equipment_id="eq-001", overall_score=65.0)
        assert health.status == HealthStatus.ATTENTION

    def test_status_degraded(self):
        """测试健康状态映射 - 退化中"""
        health = TwinHealth(equipment_id="eq-001", overall_score=45.0)
        assert health.status == HealthStatus.DEGRADED

    def test_status_critical(self):
        """测试健康状态映射 - 危险"""
        health = TwinHealth(equipment_id="eq-001", overall_score=20.0)
        assert health.status == HealthStatus.CRITICAL

    def test_boundary_healthy_normal(self):
        """测试边界值：健康 -> 正常"""
        health = TwinHealth(equipment_id="eq-001", overall_score=90.0)
        assert health.status == HealthStatus.HEALTHY
        health2 = TwinHealth(equipment_id="eq-001", overall_score=89.9)
        assert health2.status == HealthStatus.NORMAL

    def test_default_values(self):
        """测试默认值"""
        health = TwinHealth(equipment_id="eq-001", overall_score=80.0)
        assert health.component_scores == {}
        assert health.anomalies == []
        assert health.recommendations == []

    def test_to_dict(self):
        """测试转换为字典"""
        health = TwinHealth(
            equipment_id="eq-001",
            overall_score=92.0,
            anomalies=[{"parameter": "Temp", "z_score": 2.5}],
            recommendations=["Check Temp"],
        )
        d = health.to_dict()
        assert d["equipment_id"] == "eq-001"
        assert d["overall_score"] == 92.0
        assert d["status"] == "healthy"
        assert len(d["anomalies"]) == 1

    def test_repr(self):
        """测试字符串表示"""
        health = TwinHealth(equipment_id="eq-001", overall_score=85.5)
        r = repr(health)
        assert "eq-001" in r
        assert "85.5" in r

    def test_health_status_with_explicit_status(self):
        """测试显式设置状态"""
        health = TwinHealth(
            equipment_id="eq-001",
            overall_score=95.0,
            status=HealthStatus.CRITICAL,
        )
        assert health.status == HealthStatus.CRITICAL


class TestSimulationStep:
    """仿真步骤测试"""

    def test_create_step(self):
        """测试创建仿真步骤"""
        ts = datetime.utcnow()
        step = SimulationStep(
            time_offset=60.0,
            timestamp=ts,
            parameters={"Temp": 100.0, "Pressure": 2.0},
        )
        assert step.time_offset == 60.0
        assert step.timestamp == ts
        assert step.parameters["Temp"] == 100.0

    def test_default_events(self):
        """测试默认事件为空"""
        step = SimulationStep(
            time_offset=0.0,
            timestamp=datetime.utcnow(),
        )
        assert step.events == []


class TestSimulationResult:
    """仿真结果测试"""

    def test_create_result(self):
        """测试创建仿真结果"""
        result = SimulationResult(
            scenario={"name": "test"},
            steps=[],
        )
        assert result.scenario["name"] == "test"
        assert result.steps == []
        assert result.step_count == 0

    def test_duration(self):
        """测试仿真耗时"""
        started = datetime(2024, 1, 1, 12, 0, 0)
        completed = datetime(2024, 1, 1, 12, 5, 0)
        result = SimulationResult(
            scenario={},
            started_at=started,
            completed_at=completed,
        )
        assert result.duration == 300.0

    def test_duration_none(self):
        """测试无时间时的耗时"""
        result = SimulationResult(scenario={})
        assert result.duration is None

    def test_step_count(self):
        """测试步骤计数"""
        step = SimulationStep(time_offset=0.0, timestamp=datetime.utcnow())
        result = SimulationResult(
            scenario={},
            steps=[step, step, step],
        )
        assert result.step_count == 3

    def test_get_final_parameters(self):
        """测试获取最终参数"""
        step1 = SimulationStep(
            time_offset=0.0,
            timestamp=datetime.utcnow(),
            parameters={"Temp": 100.0},
        )
        step2 = SimulationStep(
            time_offset=60.0,
            timestamp=datetime.utcnow(),
            parameters={"Temp": 110.0},
        )
        result = SimulationResult(scenario={}, steps=[step1, step2])
        final = result.get_final_parameters()
        assert final["Temp"] == 110.0

    def test_get_final_parameters_empty(self):
        """测试空步骤时获取最终参数"""
        result = SimulationResult(scenario={}, steps=[])
        assert result.get_final_parameters() == {}

    def test_to_dict(self):
        """测试转换为字典"""
        step = SimulationStep(
            time_offset=0.0,
            timestamp=datetime.utcnow(),
            parameters={"Temp": 100.0},
        )
        result = SimulationResult(
            scenario={"name": "test"},
            steps=[step],
            risk_assessment={"level": "none", "score": 0.0},
        )
        d = result.to_dict()
        assert d["step_count"] == 1
        assert d["risk_assessment"]["level"] == "none"
        assert d["final_parameters"]["Temp"] == 100.0

    def test_repr(self):
        """测试字符串表示"""
        step = SimulationStep(time_offset=0.0, timestamp=datetime.utcnow())
        result = SimulationResult(
            scenario={},
            steps=[step],
            risk_assessment={"level": "low"},
        )
        r = repr(result)
        assert "steps=1" in r
        assert "low" in r

    def test_repr_no_risk(self):
        """测试无风险评估时的字符串表示"""
        result = SimulationResult(scenario={})
        r = repr(result)
        assert "N/A" in r


class TestSimulationScenario:
    """仿真场景测试"""

    def test_create_scenario(self):
        """测试创建仿真场景"""
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Test Scenario",
            equipment_id="eq-001",
            parameters={"Temperature": 1.1},
            duration=3600.0,
        )
        assert scenario.scenario_id == "sc-001"
        assert scenario.name == "Test Scenario"
        assert scenario.equipment_id == "eq-001"
        assert scenario.duration == 3600.0

    def test_step_count(self):
        """测试步骤计数"""
        scenario = SimulationScenario(
            scenario_id="sc-002",
            name="Test",
            equipment_id="eq-001",
            duration=600.0,
            step_interval=60.0,
        )
        assert scenario.step_count == 10

    def test_step_count_minimum(self):
        """测试最小步骤数"""
        scenario = SimulationScenario(
            scenario_id="sc-003",
            name="Test",
            equipment_id="eq-001",
            duration=30.0,
            step_interval=60.0,
        )
        assert scenario.step_count == 1

    def test_default_values(self):
        """测试默认值"""
        scenario = SimulationScenario(
            scenario_id="sc-004",
            name="Test",
            equipment_id="eq-001",
        )
        assert scenario.parameters == {}
        assert scenario.duration == 3600.0
        assert scenario.step_interval == 60.0
        assert scenario.description is None
        assert scenario.constraints == {}
        assert scenario.metadata == {}

    def test_to_sim_dict(self):
        """测试转换为仿真字典"""
        scenario = SimulationScenario(
            scenario_id="sc-005",
            name="Test",
            equipment_id="eq-001",
            parameters={"Temp": 1.2},
            duration=1800.0,
        )
        d = scenario.to_sim_dict()
        assert d["scenario_id"] == "sc-005"
        assert d["name"] == "Test"
        assert d["parameters"]["Temp"] == 1.2
        assert d["duration"] == 1800.0

    def test_boundary_duration_zero(self):
        """测试零时长场景"""
        scenario = SimulationScenario(
            scenario_id="sc-006",
            name="Zero",
            equipment_id="eq-001",
            duration=0.0,
        )
        assert scenario.step_count == 1  # minimum 1 step


class TestTwinEvent:
    """数字孪生事件测试"""

    def test_create_event(self):
        """测试创建事件"""
        event = TwinEvent(
            event_type="state_synced",
            equipment_id="eq-001",
            data={"temp": 25.0},
        )
        assert event.event_type == "state_synced"
        assert event.equipment_id == "eq-001"
        assert event.data["temp"] == 25.0

    def test_default_timestamp(self):
        """测试默认时间戳"""
        event = TwinEvent(
            event_type="test",
            equipment_id="eq-001",
        )
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)

    def test_repr(self):
        """测试字符串表示"""
        event = TwinEvent(
            event_type="health_check",
            equipment_id="eq-001",
        )
        r = repr(event)
        assert "health_check" in r
        assert "eq-001" in r
