"""报警升级服务

根据升级策略自动升级未处理的报警：
- 初始延迟后开始升级
- 周期性升级直到最大级别
- 通知不同级别的接收人
"""

import asyncio
import logging
from typing import Dict, List, Optional

from myeap.alarm.models import Alarm, AlarmEscalationPolicy, AlarmSeverity

from myeap.alarm.notifier import AlarmNotifier

logger = logging.getLogger(__name__)


class AlarmEscalationService:
    """报警升级服务

    负责管理和执行报警升级流程。

    Attributes:
        notifier: 报警通知器
        policies: 升级策略字典，按严重程度索引
        _escalation_tasks: 当前正在执行的升级任务
    """

    def __init__(
        self,
        notifier: AlarmNotifier,
        escalation_policies: Optional[Dict[AlarmSeverity, AlarmEscalationPolicy]] = None,
    ):
        """初始化报警升级服务

        Args:
            notifier: 报警通知器实例
            escalation_policies: 升级策略字典，键为严重程度
        """
        self.notifier = notifier
        self.policies = escalation_policies or self._default_policies()
        self._escalation_tasks: Dict[str, asyncio.Task] = {}
        self._escalation_history: Dict[str, List[Dict]] = {}  # 存储升级历史

    def _default_policies(self) -> Dict[AlarmSeverity, AlarmEscalationPolicy]:
        """获取默认升级策略"""
        return {
            AlarmSeverity.CRITICAL: AlarmEscalationPolicy(
                severity=AlarmSeverity.CRITICAL,
                initial_delay=60,  # 1分钟后开始升级
                escalation_interval=300,  # 每5分钟升级一次
                max_escalation_level=3,
                notify_channels=["sms", "email"],
                assignees=["operator", "supervisor", "manager"],
            ),
            AlarmSeverity.MAJOR: AlarmEscalationPolicy(
                severity=AlarmSeverity.MAJOR,
                initial_delay=300,  # 5分钟后开始升级
                escalation_interval=600,  # 每10分钟升级一次
                max_escalation_level=2,
                notify_channels=["email"],
                assignees=["operator", "supervisor"],
            ),
            AlarmSeverity.MINOR: AlarmEscalationPolicy(
                severity=AlarmSeverity.MINOR,
                initial_delay=1800,  # 30分钟后开始升级
                escalation_interval=3600,  # 每小时升级一次
                max_escalation_level=1,
                notify_channels=["email"],
                assignees=["operator"],
            ),
            AlarmSeverity.WARNING: AlarmEscalationPolicy(
                severity=AlarmSeverity.WARNING,
                initial_delay=0,
                escalation_interval=0,
                max_escalation_level=0,
                notify_channels=[],
                assignees=[],
            ),
        }

    def set_policy(self, severity: AlarmSeverity, policy: AlarmEscalationPolicy) -> None:
        """设置指定严重程度的升级策略

        Args:
            severity: 严重程度
            policy: 升级策略
        """
        self.policies[severity] = policy

    def get_policy(self, severity: AlarmSeverity) -> Optional[AlarmEscalationPolicy]:
        """获取指定严重程度的升级策略

        Args:
            severity: 严重程度

        Returns:
            升级策略，不存在返回None
        """
        return self.policies.get(severity)

    async def start_escalation(self, alarm: Alarm) -> None:
        """启动报警升级流程

        Args:
            alarm: 报警对象
        """
        policy = self.policies.get(alarm.severity)
        if not policy or policy.max_escalation_level == 0:
            logger.debug(f"No escalation policy for alarm {alarm.id} with severity {alarm.severity}")
            return

        # 如果已经有该报警的升级任务，先停止
        if alarm.id in self._escalation_tasks:
            await self.stop_escalation(alarm.id)

        # 创建新的升级任务
        task = asyncio.create_task(
            self._escalation_loop(alarm, policy)
        )
        self._escalation_tasks[alarm.id] = task
        self._escalation_history[alarm.id] = []

        logger.info(f"Started escalation for alarm {alarm.id} with policy for {alarm.severity}")

    async def stop_escalation(self, alarm_id: str) -> bool:
        """停止报警升级流程

        Args:
            alarm_id: 报警ID

        Returns:
            是否成功停止
        """
        if alarm_id in self._escalation_tasks:
            task = self._escalation_tasks[alarm_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._escalation_tasks[alarm_id]
            logger.info(f"Stopped escalation for alarm {alarm_id}")
            return True
        return False

    async def stop_all_escalations(self) -> int:
        """停止所有升级流程

        Returns:
            停止的任务数量
        """
        count = 0
        for alarm_id in list(self._escalation_tasks.keys()):
            if await self.stop_escalation(alarm_id):
                count += 1
        return count

    def get_escalation_history(self, alarm_id: str) -> List[Dict]:
        """获取报警的升级历史

        Args:
            alarm_id: 报警ID

        Returns:
            升级历史列表
        """
        return self._escalation_history.get(alarm_id, [])

    def is_escalating(self, alarm_id: str) -> bool:
        """检查报警是否正在升级

        Args:
            alarm_id: 报警ID

        Returns:
            是否正在升级
        """
        return alarm_id in self._escalation_tasks

    async def _escalation_loop(self, alarm: Alarm, policy: AlarmEscalationPolicy) -> None:
        """升级循环

        Args:
            alarm: 报警对象
            policy: 升级策略
        """
        try:
            # 初始延迟
            if policy.initial_delay > 0:
                await asyncio.sleep(policy.initial_delay)

            # 逐级升级
            for level in range(1, policy.max_escalation_level + 1):
                # 检查是否已确认或清除
                if not alarm.is_active:
                    break

                # 获取当前级别的通知人
                assignees = self._get_assignees(policy, level)

                # 发送通知
                for assignee in assignees:
                    await self.notifier.notify_alarm(
                        alarm,
                        assignee,
                        level,
                        f"Alarm escalation level {level}",
                    )

                # 记录升级历史
                self._record_escalation(alarm.id, level, assignees)

                logger.info(
                    f"Alarm {alarm.id} escalated to level {level}, "
                    f"notified: {assignees}"
                )

                # 等待下一个升级间隔
                if level < policy.max_escalation_level and policy.escalation_interval > 0:
                    await asyncio.sleep(policy.escalation_interval)

        except asyncio.CancelledError:
            logger.debug(f"Escalation loop cancelled for alarm {alarm.id}")
        except Exception as e:
            logger.exception(f"Error in escalation loop for alarm {alarm.id}: {e}")
        finally:
            # 清理已完成的任务
            if alarm.id in self._escalation_tasks:
                del self._escalation_tasks[alarm.id]

    def _get_assignees(self, policy: AlarmEscalationPolicy, level: int) -> List[str]:
        """获取指定级别的通知人

        Args:
            policy: 升级策略
            level: 升级级别

        Returns:
            通知人列表
        """
        # 按级别分配通知人，从列表开头取level个
        return policy.assignees[: min(level, len(policy.assignees))]

    def _record_escalation(self, alarm_id: str, level: int, assignees: List[str]) -> None:
        """记录升级事件

        Args:
            alarm_id: 报警ID
            level: 升级级别
            assignees: 通知人列表
        """
        if alarm_id not in self._escalation_history:
            self._escalation_history[alarm_id] = []

        self._escalation_history[alarm_id].append({
            "level": level,
            "assignees": assignees,
            "timestamp": asyncio.get_event_loop().time(),
        })

    def get_active_escalation_count(self) -> int:
        """获取当前活跃的升级任务数量

        Returns:
            活跃升级任务数量
        """
        return len(self._escalation_tasks)
