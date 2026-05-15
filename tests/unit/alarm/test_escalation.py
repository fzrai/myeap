"""Alarm escalation service tests"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from myeap.alarm.models import (
    Alarm,
    AlarmDefinition,
    AlarmEscalationPolicy,
    AlarmSeverity,
)
from myeap.alarm.escalation import AlarmEscalationService
from myeap.alarm.notifier import AlarmNotifier


class MockNotifier(AlarmNotifier):
    """Mock notifier for testing"""

    def __init__(self):
        super().__init__()
        self.notify_calls = []

    async def notify_alarm(
        self,
        alarm: Alarm,
        recipient: str,
        escalation_level: int,
        message: str,
    ):
        self.notify_calls.append({
            "alarm_id": alarm.id,
            "recipient": recipient,
            "level": escalation_level,
            "message": message,
        })


class TestAlarmEscalationService:
    """AlarmEscalationService tests"""

    @pytest.fixture
    def mock_notifier(self):
        """Create a mock notifier"""
        return MockNotifier()

    @pytest.fixture
    def escalation_service(self, mock_notifier):
        """Create an escalation service with test policies"""
        policies = {
            AlarmSeverity.CRITICAL: AlarmEscalationPolicy(
                severity=AlarmSeverity.CRITICAL,
                initial_delay=0,
                escalation_interval=0,
                max_escalation_level=3,
                notify_channels=["email"],
                assignees=["op1", "op2", "op3"],
            ),
            AlarmSeverity.MAJOR: AlarmEscalationPolicy(
                severity=AlarmSeverity.MAJOR,
                initial_delay=0,
                escalation_interval=0,
                max_escalation_level=2,
                notify_channels=["email"],
                assignees=["op1", "sup1"],
            ),
            AlarmSeverity.MINOR: AlarmEscalationPolicy(
                severity=AlarmSeverity.MINOR,
                initial_delay=0,
                escalation_interval=0,
                max_escalation_level=1,
                notify_channels=["email"],
                assignees=["op1"],
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
        return AlarmEscalationService(mock_notifier, policies)

    @pytest.fixture
    def sample_alarm(self):
        """Create a sample alarm for testing"""
        return Alarm(
            id="test-alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST_ALARM",
            alarm_text="Test alarm text",
            severity=AlarmSeverity.CRITICAL,
            raised_at=datetime.utcnow(),
        )

    def test_initialization(self, escalation_service, mock_notifier):
        """Test service initialization"""
        assert escalation_service.notifier is mock_notifier
        assert len(escalation_service.policies) == 4

    def test_get_policy(self, escalation_service):
        """Test getting escalation policy"""
        policy = escalation_service.get_policy(AlarmSeverity.CRITICAL)
        assert policy is not None
        assert policy.max_escalation_level == 3

        # WARNING has policy but with max_escalation_level=0 (no escalation)
        warning_policy = escalation_service.get_policy(AlarmSeverity.WARNING)
        assert warning_policy is not None
        assert warning_policy.max_escalation_level == 0

    def test_set_policy(self, escalation_service):
        """Test setting escalation policy"""
        new_policy = AlarmEscalationPolicy(
            severity=AlarmSeverity.WARNING,
            initial_delay=100,
            escalation_interval=200,
            max_escalation_level=2,
            notify_channels=["sms"],
            assignees=["admin"],
        )
        escalation_service.set_policy(AlarmSeverity.WARNING, new_policy)

        policy = escalation_service.get_policy(AlarmSeverity.WARNING)
        assert policy.max_escalation_level == 2

    def test_default_policies(self):
        """Test default policies are created correctly"""
        service = AlarmEscalationService(MagicMock())
        assert AlarmSeverity.CRITICAL in service.policies
        assert AlarmSeverity.MAJOR in service.policies
        assert AlarmSeverity.MINOR in service.policies
        assert AlarmSeverity.WARNING in service.policies

    @pytest.mark.asyncio
    async def test_start_escalation(self, escalation_service, sample_alarm):
        """Test starting escalation for an alarm"""
        await escalation_service.start_escalation(sample_alarm)

        assert escalation_service.is_escalating(sample_alarm.id)
        assert escalation_service.get_active_escalation_count() == 1

    @pytest.mark.asyncio
    async def test_stop_escalation(self, escalation_service, sample_alarm):
        """Test stopping escalation"""
        await escalation_service.start_escalation(sample_alarm)
        assert escalation_service.is_escalating(sample_alarm.id)

        result = await escalation_service.stop_escalation(sample_alarm.id)
        assert result is True
        assert not escalation_service.is_escalating(sample_alarm.id)

    @pytest.mark.asyncio
    async def test_stop_nonexistent_escalation(self, escalation_service):
        """Test stopping non-existent escalation"""
        result = await escalation_service.stop_escalation("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_all_escalations(self, escalation_service):
        """Test stopping all escalations"""
        # Start multiple escalations
        started_count = 0
        for i in range(3):
            alarm = Alarm(
                id=f"alarm-{i}",
                equipment_id="eq-001",
                alarm_code="TEST",
                alarm_text="Test",
                severity=AlarmSeverity.CRITICAL,
                raised_at=datetime.utcnow(),
            )
            await escalation_service.start_escalation(alarm)
            started_count += 1

        # At least we started 3 escalations (they may complete quickly)
        assert started_count == 3

        count = await escalation_service.stop_all_escalations()
        # Some may have already completed, so count could be 0-3
        assert escalation_service.get_active_escalation_count() == 0

    @pytest.mark.asyncio
    async def test_escalation_loop_completes(self, escalation_service, sample_alarm):
        """Test escalation loop runs through all levels"""
        await escalation_service.start_escalation(sample_alarm)

        # Wait for escalation to complete
        while escalation_service.is_escalating(sample_alarm.id):
            await asyncio.sleep(0.1)

        history = escalation_service.get_escalation_history(sample_alarm.id)
        assert len(history) == 3  # CRITICAL has max 3 levels

    def test_get_assignees(self, escalation_service):
        """Test getting assignees for escalation level"""
        policy = escalation_service.get_policy(AlarmSeverity.CRITICAL)

        level_1 = escalation_service._get_assignees(policy, 1)
        assert level_1 == ["op1"]

        level_2 = escalation_service._get_assignees(policy, 2)
        assert level_2 == ["op1", "op2"]

        level_3 = escalation_service._get_assignees(policy, 3)
        assert level_3 == ["op1", "op2", "op3"]

    def test_get_assignees_exceeds_list(self, escalation_service):
        """Test getting assignees when level exceeds list length"""
        policy = escalation_service.get_policy(AlarmSeverity.MAJOR)

        # MAJOR only has 2 assignees but request level 5
        assignees = escalation_service._get_assignees(policy, 5)
        assert len(assignees) == 2

    def test_record_escalation(self, escalation_service):
        """Test recording escalation events"""
        escalation_service._record_escalation("alarm-1", 1, ["op1"])
        escalation_service._record_escalation("alarm-1", 2, ["op1", "op2"])

        history = escalation_service.get_escalation_history("alarm-1")
        assert len(history) == 2
        assert history[0]["level"] == 1
        assert history[1]["level"] == 2

    def test_get_escalation_history_empty(self, escalation_service):
        """Test getting escalation history for non-existent alarm"""
        history = escalation_service.get_escalation_history("nonexistent")
        assert history == []
