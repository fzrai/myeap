"""高可用管理测试"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock

from myeap.cluster.ha import HAManager, HealthCheckResult, FailoverReason


@pytest.fixture
def ha_manager():
    """创建HA管理器实例"""
    return HAManager(
        node_id="node-1",
        role="active",
        max_failover_count=3,
        failover_cooldown=0,  # 测试时不等待冷却
    )


class TestHealthCheckResult:
    """测试健康检查结果"""

    def test_create_result(self):
        result = HealthCheckResult(name="check-1", healthy=True, message="OK")
        assert result.name == "check-1"
        assert result.healthy is True
        assert result.message == "OK"
        assert result.latency_ms == 0.0
        assert isinstance(result.timestamp, datetime)

    def test_create_result_with_details(self):
        result = HealthCheckResult(
            name="check-2",
            healthy=False,
            message="Failed",
            details={"error": "timeout"},
            latency_ms=50.0,
        )
        assert result.healthy is False
        assert result.details == {"error": "timeout"}
        assert result.latency_ms == 50.0

    def test_default_details(self):
        result = HealthCheckResult(name="check", healthy=True)
        assert result.details == {}

    def test_default_timestamp(self):
        result = HealthCheckResult(name="check", healthy=True)
        assert result.timestamp is not None


class TestHAManagerInit:
    """测试HA管理器初始化"""

    def test_default_init(self, ha_manager):
        assert ha_manager.node_id == "node-1"
        assert ha_manager.role == "active"
        assert ha_manager.is_active is True
        assert ha_manager.max_failover_count == 3
        assert ha_manager.failover_count == 0

    def test_init_standby_role(self):
        ha = HAManager("node-2", role="standby")
        assert ha.role == "standby"
        assert ha.is_active is False


class TestHAManagerHealthChecks:
    """测试健康检查管理"""

    def test_register_health_check(self, ha_manager):
        check_fn = lambda: True
        ha_manager.register_health_check("db", check_fn, interval=10)
        assert "db" in ha_manager._health_checks
        assert ha_manager._health_checks["db"]["interval"] == 10

    def test_unregister_health_check(self, ha_manager):
        ha_manager.register_health_check("db", lambda: True)
        result = ha_manager.unregister_health_check("db")
        assert result is True
        assert "db" not in ha_manager._health_checks

    def test_unregister_nonexistent_health_check(self, ha_manager):
        result = ha_manager.unregister_health_check("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_run_health_check_success(self, ha_manager):
        ha_manager.register_health_check("check_ok", lambda: True, interval=30)
        result = await ha_manager.run_health_check("check_ok")
        assert result.healthy is True
        assert result.name == "check_ok"
        assert result.message == "OK"

    @pytest.mark.asyncio
    async def test_run_health_check_failure(self, ha_manager):
        ha_manager.register_health_check("check_fail", lambda: False, interval=30)
        result = await ha_manager.run_health_check("check_fail")
        assert result.healthy is False
        assert result.message == "FAIL"

    @pytest.mark.asyncio
    async def test_run_health_check_exception(self, ha_manager):
        def bad_check():
            raise RuntimeError("DB connection lost")

        ha_manager.register_health_check("bad_check", bad_check, interval=30)
        result = await ha_manager.run_health_check("bad_check")
        assert result.healthy is False
        assert "Error" in result.message
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_run_health_check_not_found(self, ha_manager):
        result = await ha_manager.run_health_check("nonexistent")
        assert result.healthy is False
        assert "not found" in result.message

    @pytest.mark.asyncio
    async def test_run_all_checks(self, ha_manager):
        ha_manager.register_health_check("check1", lambda: True, interval=30)
        ha_manager.register_health_check("check2", lambda: False, interval=30)
        results = await ha_manager.run_all_checks()
        assert len(results) == 2
        assert results["check1"].healthy is True
        assert results["check2"].healthy is False

    @pytest.mark.asyncio
    async def test_check_health_status_all_healthy(self, ha_manager):
        ha_manager.register_health_check("check1", lambda: True, interval=30)
        ha_manager.register_health_check("check2", lambda: True, interval=30)
        assert await ha_manager.check_health_status() is True

    @pytest.mark.asyncio
    async def test_check_health_status_has_unhealthy(self, ha_manager):
        ha_manager.register_health_check("check1", lambda: True, interval=30)
        ha_manager.register_health_check("check2", lambda: False, interval=30)
        assert await ha_manager.check_health_status() is False

    @pytest.mark.asyncio
    async def test_run_async_health_check(self, ha_manager):
        async def async_check():
            return True

        ha_manager.register_health_check("async_check", async_check, interval=30)
        result = await ha_manager.run_health_check("async_check")
        assert result.healthy is True


class TestHAManagerRoleManagement:
    """测试角色管理"""

    def test_switch_role(self, ha_manager):
        callback = Mock()
        ha_manager.on_role_change(callback)
        ha_manager.switch_role("standby")
        assert ha_manager.role == "standby"
        assert ha_manager.is_active is False

    def test_switch_same_role(self, ha_manager):
        callback = Mock()
        ha_manager.on_role_change(callback)
        ha_manager.switch_role("active")
        callback.assert_not_called()

    def test_promote_to_active(self, ha_manager):
        ha_manager.demote_to_standby()
        assert ha_manager.is_active is False
        ha_manager.promote_to_active()
        assert ha_manager.is_active is True

    def test_demote_to_standby(self, ha_manager):
        ha_manager.demote_to_standby()
        assert ha_manager.role == "standby"

    @pytest.mark.asyncio
    async def test_role_change_callback_called(self, ha_manager):
        changes = []

        def on_change(old_role, new_role):
            changes.append((old_role, new_role))

        ha_manager.on_role_change(on_change)
        ha_manager.switch_role("standby")
        await asyncio.sleep(0.05)  # allow task to run
        assert len(changes) == 1
        assert changes[0] == ("active", "standby")


class TestHAManagerFailover:
    """测试故障切换"""

    @pytest.mark.asyncio
    async def test_manual_failover(self, ha_manager):
        callback = AsyncMock()
        ha_manager.on_failover(callback)
        result = await ha_manager.trigger_failover("test_reason")
        assert result is True
        assert ha_manager.failover_count == 1
        assert ha_manager.role == "standby"
        callback.assert_called_once_with("test_reason")

    @pytest.mark.asyncio
    async def test_failover_not_active_node(self):
        ha = HAManager("node-2", role="standby", failover_cooldown=0)
        result = await ha.trigger_failover("test")
        assert result is False
        assert ha.failover_count == 0

    @pytest.mark.asyncio
    async def test_failover_max_count_reached(self, ha_manager):
        ha_manager.max_failover_count = 1
        await ha_manager.trigger_failover("first")
        # Promote back for next failover
        ha_manager.promote_to_active()
        ha_manager._last_failover_time = None  # reset cooldown
        result = await ha_manager.trigger_failover("second")
        assert result is False

    @pytest.mark.asyncio
    async def test_failover_cooldown(self):
        ha = HAManager("node-1", role="active", failover_cooldown=60)
        await ha.trigger_failover("first")
        ha.promote_to_active()
        result = await ha.trigger_failover("second")
        assert result is False

    @pytest.mark.asyncio
    async def test_failover_callback_with_sync(self, ha_manager):
        callback = Mock()
        ha_manager.on_failover(callback)
        await ha_manager.trigger_failover("test")
        callback.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_failover_callback_with_async(self, ha_manager):
        callback = AsyncMock()
        ha_manager.on_failover(callback)
        await ha_manager.trigger_failover("test")
        callback.assert_called_once_with("test")


class TestHAManagerStats:
    """测试统计数据"""

    def test_reset_stats(self, ha_manager):
        ha_manager._failover_count = 5
        ha_manager._last_failover_time = datetime.utcnow()
        ha_manager._consecutive_failures = {"check1": 3}
        ha_manager.reset_stats()
        assert ha_manager.failover_count == 0
        assert ha_manager._last_failover_time is None
        assert len(ha_manager._consecutive_failures) == 0

    @pytest.mark.asyncio
    async def test_health_status_callback(self, ha_manager):
        statuses = []

        def on_status(name, healthy):
            statuses.append((name, healthy))

        ha_manager.on_health_status(on_status)
        ha_manager.register_health_check("check1", lambda: True, interval=30)
        ha_manager.register_health_check("check2", lambda: False, interval=30)
        await ha_manager.run_all_checks()
        assert len(statuses) == 2


class TestHAManagerShutdown:
    """测试关闭"""

    @pytest.mark.asyncio
    async def test_shutdown(self, ha_manager):
        ha_manager.register_health_check("db", lambda: True)
        await ha_manager.shutdown()
        assert ha_manager._monitor_task is None or ha_manager._monitor_task.done()
