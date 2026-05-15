"""配置热更新模块

监控配置文件变更，支持热加载和变更通知。
支持文件系统和etcd/consul等后端。
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConfigChangeType(str, Enum):
    """配置变更类型"""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    RELOADED = "reloaded"


@dataclass
class ConfigChangeEvent:
    """配置变更事件

    Attributes:
        key: 配置键
        old_value: 旧值
        new_value: 新值
        change_type: 变更类型
        source: 来源路径
        timestamp: 变更时间
        metadata: 附加信息
    """
    key: str
    old_value: Any = None
    new_value: Any = None
    change_type: ConfigChangeType = ConfigChangeType.UPDATED
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConfigWatcher:
    """配置文件监听器

    监控配置文件变更，支持热加载和键级回调通知。
    支持JSON、YAML和TOML格式配置文件。

    Attributes:
        config_path: 配置文件路径
        _watchers: 键级回调映射
        _global_watcher: 全局变更回调
        _current_config: 当前加载的配置
        _last_modified: 上次修改时间
        _watch_task: 后台监听任务

    Example:
        watcher = ConfigWatcher("/etc/myeap/config.json")
        watcher.watch("database.host", lambda key, val: print(f"Config changed: {key}={val}"))
        await watcher.start()
    """

    def __init__(self, config_path: str):
        """初始化配置监听器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self._watchers: Dict[str, Callable[[str, Any], Any]] = {}
        self._global_watcher: Optional[Callable[[ConfigChangeEvent], Any]] = None
        self._current_config: Dict[str, Any] = {}
        self._last_modified: Optional[float] = None
        self._last_checked: Optional[datetime] = None
        self._watch_task: Optional[asyncio.Task] = None
        self._running: bool = False

        # 统计
        self._reload_count: int = 0
        self._change_events: List[ConfigChangeEvent] = []

    @property
    def current_config(self) -> Dict[str, Any]:
        """当前配置（只读副本）"""
        return dict(self._current_config)

    def watch(self, key: str, callback: Callable[[str, Any], Any]) -> None:
        """监听配置键变更

        当指定的配置键发生变化时，调用回调函数。

        Args:
            key: 配置键（支持点分隔的嵌套路径，如 "database.host"）
            callback: 回调函数 (key, new_value) -> Any
        """
        self._watchers[key] = callback
        logger.debug("Registered watcher for config key: %s", key)

    def unwatch(self, key: str) -> bool:
        """取消监听配置键

        Args:
            key: 配置键

        Returns:
            bool: 是否成功取消
        """
        if key in self._watchers:
            del self._watchers[key]
            logger.debug("Unregistered watcher for config key: %s", key)
            return True
        return False

    def on_change(self, callback: Callable[[ConfigChangeEvent], Any]) -> None:
        """设置全局变更回调

        Args:
            callback: 回调函数（接收ConfigChangeEvent）
        """
        self._global_watcher = callback

    async def start(self, poll_interval: int = 5) -> None:
        """启动配置监听

        Args:
            poll_interval: 轮询间隔（秒）
        """
        if self._running:
            logger.warning("Config watcher already running")
            return

        # 首次加载
        try:
            self._current_config = self._load_config()
            self._last_modified = os.path.getmtime(self.config_path)
        except FileNotFoundError:
            logger.warning("Config file not found: %s", self.config_path)
        except Exception as e:
            logger.error("Error loading initial config: %s", e)

        self._running = True
        self._watch_task = asyncio.create_task(
            self._watch_loop(poll_interval)
        )
        logger.info(
            "Config watcher started: %s (interval=%ds)",
            self.config_path,
            poll_interval,
        )

    async def stop(self) -> None:
        """停止配置监听"""
        self._running = False
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            self._watch_task = None
        logger.info("Config watcher stopped")

    async def reload(self) -> Dict[str, Any]:
        """手动重新加载配置

        Returns:
            新配置字典
        """
        old_config = self._current_config.copy()
        new_config = self._load_config()
        self._current_config = new_config
        self._reload_count += 1

        await self._notify_changes(old_config, new_config)
        return new_config

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点号分隔的嵌套键）

        Args:
            key: 配置键 (如 "database.host")
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._current_config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值（仅内存中，不写回文件）

        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split(".")
        target = self._current_config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    # ---- 内部方法 ----

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件

        根据扩展名自动识别格式。

        Returns:
            配置字典
        """
        path = Path(self.config_path)

        if not path.exists():
            logger.warning("Config file not found: %s", self.config_path)
            return {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                try:
                    import yaml
                    return yaml.safe_load(f) or {}
                except ImportError:
                    logger.error("PyYAML not installed, cannot load YAML config")
                    return {}
            elif path.suffix == ".toml":
                try:
                    import tomllib
                    return tomllib.loads(f.read())
                except ImportError:
                    try:
                        import tomli
                        return tomli.loads(f.read())
                    except ImportError:
                        logger.error("tomllib/tomli not installed, cannot load TOML config")
                        return {}
            else:
                # 默认JSON
                try:
                    return json.load(f)
                except json.JSONDecodeError as e:
                    logger.error("Error parsing config JSON: %s", e)
                    return {}

    async def _watch_loop(self, poll_interval: int) -> None:
        """配置监听循环

        Args:
            poll_interval: 轮询间隔
        """
        while self._running:
            try:
                if os.path.exists(self.config_path):
                    mtime = os.path.getmtime(self.config_path)
                    self._last_checked = datetime.now(timezone.utc)

                    if self._last_modified is not None and mtime > self._last_modified:
                        logger.info("Config file changed, reloading...")
                        await self.reload()

                    self._last_modified = mtime
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Config watcher error: %s", e)

            await asyncio.sleep(poll_interval)

    async def _notify_changes(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any],
    ) -> None:
        """通知配置变更

        Args:
            old_config: 旧配置
            new_config: 新配置
        """
        # 收集变更事件
        events = self._diff_configs(old_config, new_config)

        # 触发全局回调
        for event in events:
            if self._global_watcher:
                await self._invoke_callback(self._global_watcher, event)

            # 触发现键回调
            if event.key in self._watchers:
                await self._invoke_callback(
                    self._watchers[event.key], event.key, event.new_value
                )

            self._change_events.append(event)

    def _diff_configs(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any],
        prefix: str = "",
    ) -> List[ConfigChangeEvent]:
        """比较新旧配置差异

        Args:
            old_config: 旧配置
            new_config: 新配置
            prefix: 键前缀（用于嵌套路径）

        Returns:
            变更事件列表
        """
        events: List[ConfigChangeEvent] = []

        all_keys = set(old_config.keys()) | set(new_config.keys())

        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_val = old_config.get(key)
            new_val = new_config.get(key)

            if key not in old_config:
                # 新增键
                events.append(ConfigChangeEvent(
                    key=full_key,
                    new_value=new_val,
                    change_type=ConfigChangeType.CREATED,
                    source=self.config_path,
                ))
            elif key not in new_config:
                # 删除键
                events.append(ConfigChangeEvent(
                    key=full_key,
                    old_value=old_val,
                    change_type=ConfigChangeType.DELETED,
                    source=self.config_path,
                ))
            elif isinstance(old_val, dict) and isinstance(new_val, dict):
                # 嵌套字典，递归比较
                events.extend(
                    self._diff_configs(old_val, new_val, prefix=full_key)
                )
            elif old_val != new_val:
                # 值变更
                events.append(ConfigChangeEvent(
                    key=full_key,
                    old_value=old_val,
                    new_value=new_val,
                    change_type=ConfigChangeType.UPDATED,
                    source=self.config_path,
                ))

        return events

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息字典
        """
        return {
            "config_path": self.config_path,
            "reload_count": self._reload_count,
            "change_event_count": len(self._change_events),
            "watcher_count": len(self._watchers),
            "last_modified": (
                datetime.fromtimestamp(self._last_modified).isoformat()
                if self._last_modified else None
            ),
            "last_checked": (
                self._last_checked.isoformat()
                if self._last_checked else None
            ),
            "running": self._running,
        }

    @staticmethod
    async def _invoke_callback(callback: Callable, *args: Any) -> None:
        """调用回调函数

        Args:
            callback: 回调函数
            *args: 回调参数
        """
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.exception("Error invoking config watcher callback: %s", e)
