"""配置热更新测试"""
import asyncio
import json
import os
import pytest
import tempfile
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from myeap.cluster.config_watcher import (
    ConfigWatcher,
    ConfigChangeEvent,
    ConfigChangeType,
)


@pytest.fixture
def config_file(tmp_path):
    """创建临时配置文件"""
    config = {"database": {"host": "localhost", "port": 5432}, "debug": True}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return str(config_path)


@pytest.fixture
def watcher(config_file):
    """创建配置监听器实例"""
    return ConfigWatcher(config_file)


class TestConfigChangeType:
    """测试配置变更类型枚举"""

    def test_values(self):
        assert ConfigChangeType.CREATED.value == "created"
        assert ConfigChangeType.UPDATED.value == "updated"
        assert ConfigChangeType.DELETED.value == "deleted"
        assert ConfigChangeType.RELOADED.value == "reloaded"


class TestConfigChangeEvent:
    """测试配置变更事件"""

    def test_create_event(self):
        event = ConfigChangeEvent(
            key="database.host",
            old_value="localhost",
            new_value="remote",
            change_type=ConfigChangeType.UPDATED,
        )
        assert event.key == "database.host"
        assert event.old_value == "localhost"
        assert event.new_value == "remote"
        assert event.change_type == ConfigChangeType.UPDATED
        assert isinstance(event.timestamp, datetime)

    def test_event_defaults(self):
        event = ConfigChangeEvent(key="test")
        assert event.old_value is None
        assert event.new_value is None
        assert event.change_type == ConfigChangeType.UPDATED
        assert event.source == ""
        assert event.metadata == {}


class TestConfigWatcherInit:
    """测试配置监听器初始化"""

    def test_init(self, watcher, config_file):
        assert watcher.config_path == config_file
        assert watcher._running is False
        assert watcher._reload_count == 0

    def test_current_config_default(self, watcher):
        assert watcher.current_config == {}

    def test_get_stats_default(self, watcher, config_file):
        stats = watcher.get_stats()
        assert stats["config_path"] == config_file
        assert stats["reload_count"] == 0
        assert stats["watcher_count"] == 0
        assert stats["running"] is False


class TestConfigWatcherLoad:
    """测试配置加载"""

    def test_load_config_json(self, watcher, config_file):
        config = watcher._load_config()
        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432
        assert config["debug"] is True

    def test_load_config_nonexistent(self, tmp_path):
        watcher = ConfigWatcher(str(tmp_path / "nonexistent.json"))
        config = watcher._load_config()
        assert config == {}

    def test_load_yaml_config(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "database:\n  host: localhost\n  port: 5432\ndebug: true\n",
            encoding="utf-8",
        )
        watcher = ConfigWatcher(str(config_path))
        config = watcher._load_config()
        assert config["database"]["host"] == "localhost"
        assert config["debug"] is True

    def test_load_invalid_json(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("{invalid json}", encoding="utf-8")
        watcher = ConfigWatcher(str(config_path))
        config = watcher._load_config()
        assert config == {}


class TestConfigWatcherKeyOperations:
    """测试配置键操作"""

    def test_get_simple_key(self, watcher):
        watcher._current_config = {"debug": True, "name": "test"}
        assert watcher.get("debug") is True
        assert watcher.get("name") == "test"

    def test_get_nested_key(self, watcher):
        watcher._current_config = {"database": {"host": "localhost", "port": 5432}}
        assert watcher.get("database.host") == "localhost"
        assert watcher.get("database.port") == 5432

    def test_get_missing_key_with_default(self, watcher):
        watcher._current_config = {}
        assert watcher.get("missing", "default_val") == "default_val"

    def test_get_missing_key_no_default(self, watcher):
        watcher._current_config = {}
        assert watcher.get("missing") is None

    def test_set_simple_key(self, watcher):
        watcher.set("debug", False)
        assert watcher._current_config["debug"] is False

    def test_set_nested_key(self, watcher):
        watcher.set("database.host", "remote-db")
        assert watcher._current_config["database"]["host"] == "remote-db"

    def test_set_nested_key_creates_path(self, watcher):
        watcher.set("new.nested.key", "value")
        assert watcher._current_config["new"]["nested"]["key"] == "value"


class TestConfigWatcherWatchers:
    """测试监听器注册与触发"""

    def test_watch_register(self, watcher):
        callback = Mock()
        watcher.watch("database.host", callback)
        assert "database.host" in watcher._watchers

    def test_unwatch(self, watcher):
        callback = Mock()
        watcher.watch("database.host", callback)
        result = watcher.unwatch("database.host")
        assert result is True
        assert "database.host" not in watcher._watchers

    def test_unwatch_nonexistent(self, watcher):
        result = watcher.unwatch("nonexistent")
        assert result is False

    def test_on_change_register(self, watcher):
        callback = Mock()
        watcher.on_change(callback)
        assert watcher._global_watcher == callback


class TestConfigWatcherDiff:
    """测试配置差异比较"""

    def test_diff_new_key(self, watcher):
        events = watcher._diff_configs({}, {"new_key": "value"})
        assert len(events) == 1
        assert events[0].change_type == ConfigChangeType.CREATED
        assert events[0].key == "new_key"
        assert events[0].new_value == "value"

    def test_diff_deleted_key(self, watcher):
        events = watcher._diff_configs({"old_key": "value"}, {})
        assert len(events) == 1
        assert events[0].change_type == ConfigChangeType.DELETED
        assert events[0].key == "old_key"
        assert events[0].old_value == "value"

    def test_diff_updated_key(self, watcher):
        events = watcher._diff_configs({"key": "old"}, {"key": "new"})
        assert len(events) == 1
        assert events[0].change_type == ConfigChangeType.UPDATED
        assert events[0].key == "key"
        assert events[0].old_value == "old"
        assert events[0].new_value == "new"

    def test_diff_no_change(self, watcher):
        events = watcher._diff_configs({"key": "same"}, {"key": "same"})
        assert len(events) == 0

    def test_diff_nested_changes(self, watcher):
        old = {"db": {"host": "old", "port": 5432}}
        new = {"db": {"host": "new", "port": 5432}}
        events = watcher._diff_configs(old, new)
        assert len(events) == 1
        assert events[0].key == "db.host"
        assert events[0].old_value == "old"
        assert events[0].new_value == "new"

    def test_diff_multiple_changes(self, watcher):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 20, "d": 4}
        events = watcher._diff_configs(old, new)
        assert len(events) == 3  # b updated, c deleted, d created
        change_types = {e.change_type for e in events}
        assert ConfigChangeType.UPDATED in change_types
        assert ConfigChangeType.DELETED in change_types
        assert ConfigChangeType.CREATED in change_types


class TestConfigWatcherReload:
    """测试配置重新加载"""

    @pytest.mark.asyncio
    async def test_manual_reload(self, watcher, config_file):
        await watcher.reload()
        assert watcher.current_config["database"]["host"] == "localhost"
        assert watcher._reload_count == 1

    @pytest.mark.asyncio
    async def test_reload_notifies_watchers(self, watcher, config_file):
        received = []

        def callback(key, value):
            received.append((key, value))

        watcher._current_config = {"database": {"host": "old", "port": 5432}, "debug": True}
        watcher.watch("database.host", callback)

        await watcher.reload()
        assert len(received) == 1
        assert received[0] == ("database.host", "localhost")

    @pytest.mark.asyncio
    async def test_reload_notifies_global_watcher(self, watcher, config_file):
        events = []

        def on_change(event):
            events.append(event)

        watcher._current_config = {"database": {"host": "old", "port": 5432}}
        watcher.on_change(on_change)

        await watcher.reload()
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_reload_increments_count(self, watcher, config_file):
        assert watcher._reload_count == 0
        await watcher.reload()
        assert watcher._reload_count == 1
        await watcher.reload()
        assert watcher._reload_count == 2


class TestConfigWatcherStartStop:
    """测试启动和停止"""

    @pytest.mark.asyncio
    async def test_start(self, watcher):
        await watcher.start(poll_interval=10)
        assert watcher._running is True
        assert watcher._watch_task is not None
        await watcher.stop()

    @pytest.mark.asyncio
    async def test_stop(self, watcher):
        await watcher.start(poll_interval=10)
        await watcher.stop()
        assert watcher._running is False

    @pytest.mark.asyncio
    async def test_start_initial_load(self, watcher, config_file):
        await watcher.start(poll_interval=10)
        assert watcher.current_config.get("database", {}).get("host") == "localhost"
        await watcher.stop()

    @pytest.mark.asyncio
    async def test_start_nonexistent_file(self, tmp_path):
        watcher = ConfigWatcher(str(tmp_path / "nonexistent.json"))
        await watcher.start(poll_interval=10)
        assert watcher._running is True
        await watcher.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, watcher):
        await watcher.start(poll_interval=10)
        # Should warn and not start again
        await watcher.start(poll_interval=10)
        assert watcher._running is True
        await watcher.stop()


class TestConfigWatcherCallbackInvocation:
    """测试回调调用"""

    @pytest.mark.asyncio
    async def test_invoke_sync_callback(self, watcher):
        callback = Mock()
        await ConfigWatcher._invoke_callback(callback, "arg1", "arg2")
        callback.assert_called_once_with("arg1", "arg2")

    @pytest.mark.asyncio
    async def test_invoke_async_callback(self, watcher):
        callback = AsyncMock()
        await ConfigWatcher._invoke_callback(callback, "arg1")
        callback.assert_called_once_with("arg1")

    @pytest.mark.asyncio
    async def test_invoke_callback_with_exception(self, watcher):
        def bad_callback(*args):
            raise RuntimeError("boom")

        # Should not raise
        await ConfigWatcher._invoke_callback(bad_callback, "arg")
