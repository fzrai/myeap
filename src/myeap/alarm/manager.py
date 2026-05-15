"""报警管理器

负责报警的接收、分发、确认、清除和屏蔽。
集成报警升级和通知服务。
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from myeap.alarm.models import (
    Alarm,
    AlarmDefinition,
    AlarmSeverity,
    AlarmStatus,
    AlarmStatistics,
)

from myeap.alarm.escalation import AlarmEscalationService
from myeap.alarm.notifier import AlarmNotifier

logger = logging.getLogger(__name__)


class AlarmManager:
    """报警管理器

    负责报警的完整生命周期管理。

    Attributes:
        escalation: 报警升级服务
        notifier: 报警通知服务
        db_manager: 数据库管理器
        _active_alarms: 活跃报警字典
        _definitions: 报警定义字典
        _suppressed_codes: 被屏蔽的报警代码集合
    """

    def __init__(
        self,
        escalation_service: AlarmEscalationService,
        notifier: AlarmNotifier,
        db_manager: Optional[Any] = None,
    ):
        """初始化报警管理器

        Args:
            escalation_service: 报警升级服务实例
            notifier: 报警通知服务实例
            db_manager: 数据库管理器（可选）
        """
        self.escalation = escalation_service
        self.notifier = notifier
        self.db = db_manager

        self._active_alarms: Dict[str, Alarm] = {}
        self._definitions: Dict[str, AlarmDefinition] = {}
        self._suppressed_codes: set = set()
        self._suppression_tasks: Dict[str, asyncio.Task] = {}

        # 回调函数
        self._on_alarm: Optional[Callable] = None
        self._on_alarm_acknowledged: Optional[Callable] = None
        self._on_alarm_cleared: Optional[Callable] = None

    @property
    def active_alarm_count(self) -> int:
        """活跃报警数量"""
        return len(self._active_alarms)

    def set_callback(
        self,
        event: str,
        callback: Callable,
    ) -> None:
        """设置报警事件回调

        Args:
            event: 事件类型 (alarm, acknowledged, cleared)
            callback: 回调函数
        """
        if event == "alarm":
            self._on_alarm = callback
        elif event == "acknowledged":
            self._on_alarm_acknowledged = callback
        elif event == "cleared":
            self._on_alarm_cleared = callback

    def register_definition(self, definition: AlarmDefinition) -> None:
        """注册报警定义

        Args:
            definition: 报警定义对象
        """
        self._definitions[definition.alarm_code] = definition
        logger.debug(f"Registered alarm definition: {definition.alarm_code}")

    def register_definitions(self, definitions: List[AlarmDefinition]) -> None:
        """批量注册报警定义

        Args:
            definitions: 报警定义列表
        """
        for definition in definitions:
            self.register_definition(definition)

    def get_definition(self, alarm_code: str) -> Optional[AlarmDefinition]:
        """获取报警定义

        Args:
            alarm_code: 报警代码

        Returns:
            报警定义，不存在返回None
        """
        return self._definitions.get(alarm_code)

    async def raise_alarm(
        self,
        equipment_id: str,
        alarm_code: str,
        parameters: Optional[Dict[str, Any]] = None,
        severity: Optional[AlarmSeverity] = None,
        alarm_text: Optional[str] = None,
    ) -> Optional[Alarm]:
        """产生报警

        Args:
            equipment_id: 设备ID
            alarm_code: 报警代码
            parameters: 附加参数
            severity: 报警严重程度（覆盖定义中的设置）
            alarm_text: 报警文本（覆盖定义中的设置）

        Returns:
            创建的报警对象，如果被屏蔽返回None
        """
        # 检查是否屏蔽
        if alarm_code in self._suppressed_codes:
            logger.debug(f"Alarm {alarm_code} for equipment {equipment_id} is suppressed")
            return None

        # 检查是否已有相同报警
        existing = self._find_existing_alarm(equipment_id, alarm_code)
        if existing:
            logger.debug(f"Alarm {alarm_code} already exists for equipment {equipment_id}")
            return existing

        # 获取报警定义
        definition = self._definitions.get(alarm_code)

        # 创建报警
        alarm = Alarm(
            id=str(uuid.uuid4()),
            equipment_id=equipment_id,
            alarm_code=alarm_code,
            alarm_text=alarm_text or (definition.default_text if definition else alarm_code),
            severity=severity or (definition.severity if definition else AlarmSeverity.MINOR),
            raised_at=datetime.utcnow(),
            parameters=parameters,
        )

        # 保存到数据库（如果可用）
        if self.db:
            await self.db.save_alarm(alarm)

        # 添加到活跃报警
        self._active_alarms[alarm.id] = alarm

        logger.info(
            f"Alarm raised: {alarm.id} - {alarm_code} for equipment {equipment_id} "
            f"(severity: {alarm.severity.value})"
        )

        # 发送通知
        await self.notifier.notify(alarm)

        # 启动升级
        await self.escalation.start_escalation(alarm)

        # 调用回调
        if self._on_alarm:
            try:
                result = self._on_alarm(alarm)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception(f"Error in alarm callback: {e}")

        # 检查是否需要自动清除
        if definition and definition.auto_clear:
            asyncio.create_task(self._auto_clear_alarm(alarm, definition.auto_clear_delay))

        return alarm

    async def acknowledge_alarm(self, alarm_id: str, user: str) -> bool:
        """确认报警

        Args:
            alarm_id: 报警ID
            user: 确认人

        Returns:
            是否成功确认
        """
        alarm = self._active_alarms.get(alarm_id)
        if not alarm:
            logger.warning(f"Alarm not found for acknowledgment: {alarm_id}")
            return False

        if alarm.is_acknowledged:
            logger.debug(f"Alarm already acknowledged: {alarm_id}")
            return True

        alarm.status = AlarmStatus.ACKNOWLEDGED
        alarm.acknowledged_by = user
        alarm.acknowledged_at = datetime.utcnow()

        # 更新数据库
        if self.db:
            await self.db.update_alarm(alarm)

        # 停止升级
        await self.escalation.stop_escalation(alarm.id)

        logger.info(f"Alarm acknowledged: {alarm_id} by {user}")

        # 调用回调
        if self._on_alarm_acknowledged:
            try:
                result = self._on_alarm_acknowledged(alarm)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception(f"Error in acknowledgment callback: {e}")

        return True

    async def clear_alarm(self, alarm_id: str, user: str) -> bool:
        """清除报警

        Args:
            alarm_id: 报警ID
            user: 清除人

        Returns:
            是否成功清除
        """
        alarm = self._active_alarms.get(alarm_id)
        if not alarm:
            logger.warning(f"Alarm not found for clearing: {alarm_id}")
            return False

        alarm.status = AlarmStatus.CLEARED
        alarm.cleared_by = user
        alarm.cleared_at = datetime.utcnow()

        # 更新数据库
        if self.db:
            await self.db.update_alarm(alarm)

        # 从活跃列表移除
        del self._active_alarms[alarm_id]

        # 停止升级
        await self.escalation.stop_escalation(alarm.id)

        logger.info(f"Alarm cleared: {alarm_id} by {user}")

        # 调用回调
        if self._on_alarm_cleared:
            try:
                result = self._on_alarm_cleared(alarm)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception(f"Error in clear callback: {e}")

        return True

    async def suppress_alarm(
        self,
        alarm_code: str,
        until: Optional[datetime] = None,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """屏蔽报警

        Args:
            alarm_code: 报警代码
            until: 屏蔽截止时间
            duration_seconds: 屏蔽持续秒数（与until二选一）
        """
        self._suppressed_codes.add(alarm_code)
        logger.info(f"Alarm suppressed: {alarm_code}")

        # 计算截止时间
        if duration_seconds:
            until = datetime.utcnow() + timedelta(seconds=duration_seconds)

        if until:
            # 定时取消屏蔽
            task = asyncio.create_task(self._unsuppress_after(alarm_code, until))
            self._suppression_tasks[alarm_code] = task

    async def unsuppress_alarm(self, alarm_code: str) -> bool:
        """取消屏蔽报警

        Args:
            alarm_code: 报警代码

        Returns:
            是否成功取消屏蔽
        """
        if alarm_code not in self._suppressed_codes:
            return False

        self._suppressed_codes.discard(alarm_code)

        # 取消定时任务
        if alarm_code in self._suppression_tasks:
            task = self._suppression_tasks[alarm_code]
            task.cancel()
            del self._suppression_tasks[alarm_code]

        logger.info(f"Alarm unsuppressed: {alarm_code}")
        return True

    def get_active_alarms(
        self,
        equipment_id: Optional[str] = None,
        severity: Optional[AlarmSeverity] = None,
        status: Optional[AlarmStatus] = None,
    ) -> List[Alarm]:
        """获取活跃报警

        Args:
            equipment_id: 设备ID过滤
            severity: 严重程度过滤
            status: 状态过滤

        Returns:
            报警列表
        """
        alarms = list(self._active_alarms.values())

        if equipment_id:
            alarms = [a for a in alarms if a.equipment_id == equipment_id]

        if severity:
            alarms = [a for a in alarms if a.severity == severity]

        if status:
            alarms = [a for a in alarms if a.status == status]

        # 按严重程度和产生时间排序
        alarms.sort(key=lambda a: (a.severity.priority, a.raised_at))
        return alarms

    def get_alarm(self, alarm_id: str) -> Optional[Alarm]:
        """获取指定报警

        Args:
            alarm_id: 报警ID

        Returns:
            报警对象，不存在返回None
        """
        return self._active_alarms.get(alarm_id)

    async def get_statistics(self) -> AlarmStatistics:
        """获取报警统计信息

        Returns:
            统计信息对象
        """
        active_alarms = list(self._active_alarms.values())

        # 按严重程度分组
        by_severity: Dict[str, int] = {}
        for severity in AlarmSeverity:
            by_severity[severity.value] = sum(1 for a in active_alarms if a.severity == severity)

        # 按设备分组
        by_equipment: Dict[str, int] = {}
        for alarm in active_alarms:
            by_equipment[alarm.equipment_id] = by_equipment.get(alarm.equipment_id, 0) + 1

        # 计算平均确认时间
        acknowledged_alarms = [a for a in active_alarms if a.is_acknowledged]
        mtta = None
        if acknowledged_alarms:
            total_time = sum(
                (a.acknowledged_at - a.raised_at).total_seconds()
                for a in acknowledged_alarms
                if a.acknowledged_at
            )
            mtta = total_time / len(acknowledged_alarms)

        # 获取已清除报警数量
        cleared_count = await self._get_cleared_count() if self.db else 0

        return AlarmStatistics(
            total_count=len(active_alarms) + cleared_count,
            active_count=len(active_alarms),
            by_severity=by_severity,
            by_equipment=by_equipment,
            mtta=mtta,
            escalation_count=self.escalation.get_active_escalation_count(),
        )

    def _find_existing_alarm(self, equipment_id: str, alarm_code: str) -> Optional[Alarm]:
        """查找已存在的未清除报警

        Args:
            equipment_id: 设备ID
            alarm_code: 报警代码

        Returns:
            报警对象，不存在返回None
        """
        for alarm in self._active_alarms.values():
            if alarm.equipment_id == equipment_id and alarm.alarm_code == alarm_code:
                if alarm.status != AlarmStatus.CLEARED:
                    return alarm
        return None

    async def _unsuppress_after(self, alarm_code: str, until: datetime) -> None:
        """延迟取消屏蔽

        Args:
            alarm_code: 报警代码
            until: 截止时间
        """
        delay = (until - datetime.utcnow()).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
        self._suppressed_codes.discard(alarm_code)
        if alarm_code in self._suppression_tasks:
            del self._suppression_tasks[alarm_code]
        logger.info(f"Alarm auto-unsuppressed: {alarm_code}")

    async def _auto_clear_alarm(self, alarm: Alarm, delay_seconds: int) -> None:
        """自动清除报警

        Args:
            alarm: 报警对象
            delay_seconds: 延迟秒数
        """
        await asyncio.sleep(delay_seconds)

        # 检查报警是否还存在且未确认
        current_alarm = self._active_alarms.get(alarm.id)
        if current_alarm and current_alarm.status == AlarmStatus.RAISED:
            await self.clear_alarm(alarm.id, "auto")
            logger.info(f"Alarm auto-cleared: {alarm.id}")

    async def _get_cleared_count(self) -> int:
        """获取已清除的报警数量（从数据库）"""
        if self.db and hasattr(self.db, "get_cleared_alarm_count"):
            return await self.db.get_cleared_alarm_count()
        return 0

    async def shutdown(self) -> None:
        """关闭管理器，清理资源"""
        # 停止所有升级
        await self.escalation.stop_all_escalations()

        # 取消所有屏蔽任务
        for task in self._suppression_tasks.values():
            task.cancel()

        self._suppression_tasks.clear()
        self._active_alarms.clear()

        logger.info("AlarmManager shutdown complete")
