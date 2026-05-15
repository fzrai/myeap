"""What-If仿真测试"""

import pytest
from datetime import datetime

from myeap.twin.digital_twin import DigitalTwin
from myeap.twin.simulation import ProcessSimulator
from myeap.twin.models import (
    RiskLevel,
    SimulationResult,
    SimulationScenario,
    SimulationStep,
)


@pytest.fixture
async def dt():
    """创建数字孪生实例"""
    return DigitalTwin()


@pytest.fixture
async def dt_with_twin(dt):
    """创建带数据的数字孪生"""
    await dt.create_twin("eq-001", {
        "chambers": {"ch-1": {"Temp": 100.0}},
        "status": "IDLE",
        "sensor_data": {
            "Temperature": 25.0,
            "Pressure": 1.0,
            "Flow": 50.0,
            "RF_Power": 200.0,
        },
    })
    return dt


@pytest.fixture
async def sim(dt_with_twin):
    """创建仿真器实例"""
    return ProcessSimulator(dt_with_twin)


@pytest.fixture
def basic_scenario():
    """创建基础仿真场景"""
    return SimulationScenario(
        scenario_id="sc-001",
        name="Basic Test",
        equipment_id="eq-001",
        parameters={"Temperature": 1.1},
        duration=600.0,
        step_interval=60.0,
    )


@pytest.fixture(scope="function")
def _event_loop():
    """为每个测试创建新的事件循环"""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


class TestProcessModelRegistration:
    """工艺模型注册测试"""

    @pytest.mark.asyncio
    async def test_register_model(self, sim):
        """测试注册工艺模型"""
        assert len(sim.registered_models) == 0

        def my_model(state, params):
            return state

        sim.register_process_model("etch", my_model)
        assert len(sim.registered_models) == 1
        assert "etch" in sim.registered_models

    @pytest.mark.asyncio
    async def test_unregister_model(self, sim):
        """测试移除工艺模型"""
        def my_model(state, params):
            return state

        sim.register_process_model("etch", my_model)
        assert sim.unregister_process_model("etch")
        assert "etch" not in sim.registered_models

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_model(self, sim):
        """测试移除不存在的工艺模型"""
        assert not sim.unregister_process_model("nonexistent")

    @pytest.mark.asyncio
    async def test_register_multiple_models(self, sim):
        """测试注册多个工艺模型"""
        def model1(state, params):
            return state

        def model2(state, params):
            return state

        sim.register_process_model("etch", model1)
        sim.register_process_model("deposition", model2)
        assert len(sim.registered_models) == 2


class TestSimulate:
    """仿真运行测试"""

    @pytest.mark.asyncio
    async def test_simulate_basic(self, sim, basic_scenario):
        """测试基本仿真运行"""
        result = await sim.simulate("eq-001", basic_scenario)
        assert isinstance(result, SimulationResult)
        assert result.step_count == 10  # 600/60
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration is not None

    @pytest.mark.asyncio
    async def test_simulate_nonexistent_twin_raises(self, dt):
        """测试仿真实不存在的设备抛出异常"""
        sim = ProcessSimulator(dt)
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Test",
            equipment_id="eq-001",
        )
        with pytest.raises(ValueError, match="No twin"):
            await sim.simulate("eq-001", scenario)

    @pytest.mark.asyncio
    async def test_simulate_mismatched_id_raises(self, sim):
        """测试设备ID不匹配抛出异常"""
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Test",
            equipment_id="eq-002",  # Different from eq-001
        )
        with pytest.raises(ValueError, match="does not match"):
            await sim.simulate("eq-001", scenario)

    @pytest.mark.asyncio
    async def test_simulate_custom_step_interval(self, dt_with_twin):
        """测试自定义步长"""
        sim = ProcessSimulator(dt_with_twin, default_step_interval=30.0)
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Test",
            equipment_id="eq-001",
            duration=600.0,
            step_interval=120.0,  # 5 steps
        )
        result = await sim.simulate("eq-001", scenario)
        assert result.step_count == 5

    @pytest.mark.asyncio
    async def test_simulate_zero_duration(self, dt_with_twin):
        """测试零时长仿真"""
        sim = ProcessSimulator(dt_with_twin)
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Zero Duration",
            equipment_id="eq-001",
            duration=0.0,
            step_interval=60.0,
        )
        result = await sim.simulate("eq-001", scenario)
        assert result.step_count == 1  # Minimum 1 step

    @pytest.mark.asyncio
    async def test_simulate_with_registered_model(self, sim, basic_scenario):
        """测试使用注册的工艺模型"""
        calls = []

        def my_model(state, params):
            calls.append(1)
            result = dict(state)
            for key, factor in params.items():
                if key in result:
                    result[key] *= factor
            return result

        sim.register_process_model("default", my_model)
        basic_scenario.metadata["process_type"] = "default"

        result = await sim.simulate("eq-001", basic_scenario)
        assert result.step_count == 10
        assert len(calls) == 10

    @pytest.mark.asyncio
    async def test_simulate_increments_count(self, sim, basic_scenario):
        """测试仿真计数增加"""
        assert sim.simulation_count == 0
        await sim.simulate("eq-001", basic_scenario)
        assert sim.simulation_count == 1

    @pytest.mark.asyncio
    async def test_simulate_sync_version(self, sim, basic_scenario):
        """测试仿真同步版本"""
        result = sim.simulate_sync("eq-001", basic_scenario)
        assert isinstance(result, SimulationResult)
        assert result.step_count > 0

    @pytest.mark.asyncio
    async def test_simulate_parameters_change(self, sim):
        """测试仿真中参数变化"""
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Temp Increase",
            equipment_id="eq-001",
            parameters={"Temperature": 1.5},  # 50% increase
            duration=600.0,
            step_interval=60.0,
        )
        result = await sim.simulate("eq-001", scenario)
        initial = result.steps[0].parameters["Temperature"]
        final = result.get_final_parameters()["Temperature"]
        assert final > initial  # Temperature should increase

    @pytest.mark.asyncio
    async def test_simulate_result_to_dict(self, sim, basic_scenario):
        """测试仿真结果转字典"""
        result = await sim.simulate("eq-001", basic_scenario)
        d = result.to_dict()
        assert "scenario" in d
        assert "predicted_outcomes" in d
        assert "risk_assessment" in d
        assert "step_count" in d
        assert d["step_count"] == 10


class TestConstraints:
    """约束条件测试"""

    @pytest.mark.asyncio
    async def test_max_value_constraint(self, dt_with_twin):
        """测试最大值约束"""
        sim = ProcessSimulator(dt_with_twin)
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="With Max Constraint",
            equipment_id="eq-001",
            parameters={"Temperature": 2.0},  # Large increase
            duration=600.0,
            step_interval=60.0,
            constraints={"max_values": {"Temperature": 30.0}},
        )
        result = await sim.simulate("eq-001", scenario)
        # Check that violations were detected
        all_events = []
        for step in result.steps:
            all_events.extend(step.events)
        violation_events = [e for e in all_events if e["type"] == "constraint_violation"]
        assert len(violation_events) > 0

    @pytest.mark.asyncio
    async def test_min_value_constraint(self, dt_with_twin):
        """测试最小值约束"""
        sim = ProcessSimulator(dt_with_twin)
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="With Min Constraint",
            equipment_id="eq-001",
            parameters={"Flow": 0.5},  # Decrease
            duration=600.0,
            step_interval=60.0,
            constraints={"min_values": {"Flow": 45.0}},
        )
        result = await sim.simulate("eq-001", scenario)
        all_events = []
        for step in result.steps:
            all_events.extend(step.events)
        violation_events = [e for e in all_events if e["type"] == "constraint_violation"]
        assert len(violation_events) > 0

    @pytest.mark.asyncio
    async def test_safety_limit_constraint(self, dt_with_twin):
        """测试安全限值约束"""
        sim = ProcessSimulator(dt_with_twin)
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Safety Limit Test",
            equipment_id="eq-001",
            parameters={"RF_Power": 100.0},  # Absolute increase
            duration=600.0,
            step_interval=60.0,
            constraints={"safety_limits": {"RF_Power": 100.0}},
        )
        result = await sim.simulate("eq-001", scenario)
        all_events = []
        for step in result.steps:
            all_events.extend(step.events)
        safety_events = [e for e in all_events if e["type"] == "safety_violation"]
        assert len(safety_events) > 0

    @pytest.mark.asyncio
    async def test_no_constraints_no_events(self, sim, basic_scenario):
        """测试无约束时无违例事件"""
        basic_scenario.constraints = {}
        result = await sim.simulate("eq-001", basic_scenario)
        all_events = []
        for step in result.steps:
            all_events.extend(step.events)
        assert len(all_events) == 0


class TestRiskAssessment:
    """风险评估测试"""

    @pytest.mark.asyncio
    async def test_no_risk_when_clean(self, sim, basic_scenario):
        """测试无风险场景"""
        result = await sim.simulate("eq-001", basic_scenario)
        assert result.risk_assessment is not None
        assert result.risk_assessment["level"] == RiskLevel.NONE.value

    @pytest.mark.asyncio
    async def test_medium_risk_with_warnings(self, dt_with_twin):
        """测试有警告时的中风险"""
        sim = ProcessSimulator(dt_with_twin)
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Risk Test",
            equipment_id="eq-001",
            parameters={"Temperature": 2.0, "Flow": 0.5},
            duration=600.0,
            step_interval=60.0,
            constraints={
                "max_values": {"Temperature": 26.0},
                "min_values": {"Flow": 48.0},
            },
        )
        result = await sim.simulate("eq-001", scenario)
        level = result.risk_assessment["level"]
        assert level in (RiskLevel.MEDIUM.value, RiskLevel.HIGH.value, RiskLevel.LOW.value)

    @pytest.mark.asyncio
    async def test_critical_risk_with_safety(self, dt_with_twin):
        """测试有安全违例时的极高风险"""
        sim = ProcessSimulator(dt_with_twin)
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Critical Test",
            equipment_id="eq-001",
            parameters={"RF_Power": 100.0},  # Large absolute increase
            duration=600.0,
            step_interval=10.0,  # More steps = more violations
            constraints={"safety_limits": {"RF_Power": 10.0}},
        )
        result = await sim.simulate("eq-001", scenario)
        assert result.risk_assessment["level"] == RiskLevel.CRITICAL.value

    @pytest.mark.asyncio
    async def test_risk_assessment_details(self, sim):
        """测试风险评估详细信息"""
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Risk Detail Test",
            equipment_id="eq-001",
            parameters={"Temperature": 2.0},
            duration=600.0,
            step_interval=60.0,
            constraints={"max_values": {"Temperature": 26.0}},
        )
        result = await sim.simulate("eq-001", scenario)
        ra = result.risk_assessment
        assert "level" in ra
        assert "score" in ra
        assert "total_events" in ra
        assert "critical_events" in ra
        assert "warning_events" in ra
        assert "details" in ra
        assert "param_variations" in ra
        assert "violated_parameters" in ra

    @pytest.mark.asyncio
    async def test_risk_assessment_score_range(self, sim):
        """测试风险评分范围"""
        scenario = SimulationScenario(
            scenario_id="sc-001",
            name="Score Test",
            equipment_id="eq-001",
            parameters={"Temperature": 2.0},
            duration=600.0,
            step_interval=60.0,
            constraints={"max_values": {"Temperature": 26.0}},
        )
        result = await sim.simulate("eq-001", scenario)
        score = result.risk_assessment["score"]
        assert 0.0 <= score <= 1.0


class TestBatchSimulation:
    """批量仿真测试"""

    @pytest.mark.asyncio
    async def test_simulate_batch(self, sim):
        """测试批量仿真"""
        scenarios = [
            SimulationScenario(
                scenario_id=f"sc-{i}",
                name=f"Scenario {i}",
                equipment_id="eq-001",
                parameters={"Temperature": 1.0 + i * 0.1},
                duration=300.0,
                step_interval=60.0,
            )
            for i in range(3)
        ]
        results = await sim.simulate_batch("eq-001", scenarios)
        assert len(results) == 3
        for result in results:
            assert isinstance(result, SimulationResult)

    @pytest.mark.asyncio
    async def test_simulate_batch_with_error(self, dt_with_twin):
        """测试批量仿真中部分失败"""
        sim = ProcessSimulator(dt_with_twin)
        scenarios = [
            SimulationScenario(
                scenario_id="sc-ok",
                name="OK",
                equipment_id="eq-001",
                duration=60.0,
            ),
            SimulationScenario(
                scenario_id="sc-bad",
                name="Bad",
                equipment_id="eq-002",  # Will fail due to mismatch
                duration=60.0,
            ),
        ]
        results = await sim.simulate_batch("eq-001", scenarios)
        assert len(results) == 2
        # First should succeed
        assert results[0].step_count > 0
        # Second should have error summary
        assert "error" in results[1].summary or results[1].step_count == 0

    @pytest.mark.asyncio
    async def test_simulate_batch_empty(self, sim):
        """测试空批量仿真"""
        results = await sim.simulate_batch("eq-001", [])
        assert len(results) == 0


class TestSensitivityAnalysis:
    """灵敏度分析测试"""

    @pytest.mark.asyncio
    async def test_sensitivity_analysis(self, dt_with_twin):
        """测试灵敏度分析"""
        sim = ProcessSimulator(dt_with_twin)
        results = await sim.run_sensitivity_analysis(
            equipment_id="eq-001",
            parameter="Temperature",
            base_value=25.0,
            variations=[0.8, 1.0, 1.2],
            duration=300.0,
        )
        assert len(results) == 3
        for r in results:
            assert isinstance(r, SimulationResult)

    @pytest.mark.asyncio
    async def test_sensitivity_analysis_single_variation(self, dt_with_twin):
        """测试单变体灵敏度分析"""
        sim = ProcessSimulator(dt_with_twin)
        results = await sim.run_sensitivity_analysis(
            equipment_id="eq-001",
            parameter="Pressure",
            base_value=1.0,
            variations=[1.0],
            duration=120.0,
        )
        assert len(results) == 1


class TestSummary:
    """摘要测试"""

    @pytest.mark.asyncio
    async def test_summary_generation(self, sim, basic_scenario):
        """测试摘要生成"""
        result = await sim.simulate("eq-001", basic_scenario)
        summary = result.summary
        assert "total_steps" in summary
        assert "initial_parameters" in summary
        assert "final_parameters" in summary
        assert "parameter_changes" in summary
        assert "risk_level" in summary
        assert summary["total_steps"] == 10

    @pytest.mark.asyncio
    async def test_summary_parameter_changes(self, sim, basic_scenario):
        """测试摘要中的参数变化"""
        result = await sim.simulate("eq-001", basic_scenario)
        changes = result.summary["parameter_changes"]
        assert "Temperature" in changes
        assert "initial" in changes["Temperature"]
        assert "final" in changes["Temperature"]
        assert "delta" in changes["Temperature"]

    @pytest.mark.asyncio
    async def test_result_repr(self, sim, basic_scenario):
        """测试结果字符串表示"""
        result = await sim.simulate("eq-001", basic_scenario)
        r = repr(result)
        assert "steps=" in r
        assert "risk=" in r


class TestStatistics:
    """仿真器统计测试"""

    @pytest.mark.asyncio
    async def test_get_statistics(self, sim):
        """测试获取统计信息"""
        stats = sim.get_statistics()
        assert "simulation_count" in stats
        assert "registered_models" in stats
        assert "default_step_interval" in stats
        assert stats["default_step_interval"] == 60.0

    @pytest.mark.asyncio
    async def test_reset(self, sim):
        """测试重置仿真器"""
        def my_model(state, params):
            return state

        sim.register_process_model("test", my_model)
        sim.reset()
        assert sim.simulation_count == 0
        assert len(sim.registered_models) == 0
