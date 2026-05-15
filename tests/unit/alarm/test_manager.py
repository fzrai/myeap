"""Alarm manager tests"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from myeap.alarm.models import (
    Alarm,
    AlarmDefinition,
    AlarmEscalationPolicy,
    AlarmSeverity,
    AlarmStatus,
)
from myeap.alarm.manager import AlarmManager
from myeap.alarm.escalation import AlarmEscalationService
from myeap.alarm.notifier import AlarmNotifier, InAppChannel


class MockDbManager:
    """Mock database manager for testing"""

    def __init__(self):
        self.alarms = {}
        self.save_count = 0
        self.update_count = 0

    async def save_alarm(self, alarm: Alarm):
        self.alarms[alarm.id] = alarm
        self.save_count += 1

    async def update_alarm(self, alarm: Alarm):
        self.alarms[alarm.id] = alarm
        self.update_count += 1

    async def get_cleared_alarm_count(self):
        return 0


class MockNotifier(AlarmNotifier):
    """Mock notifier for testing"""

    def __init__(self):
        super().__init__()
        self.notify_count = 0

    async def notify(self, alarm: Alarm, recipient=None, **kwargs):
        self.notify_count += 1


class MockEscalationService(AlarmEscalationService):
    """Mock escalation service for testing"""

    def __init__(self, notifier):
        super().__init__(notifier)
        self.start_count = 0
        self.stop_count = 0

    async def start_escalation(self, alarm: Alarm):
        self.start_count += 1

    async def stop_escalation(self, alarm_id: str):
        self.stop_count += 1
        return True


class TestAlarmManager:
    """AlarmManager tests"""

    @pytest.fixture
    def notifier(self):
        """Create a mock notifier"""
        return MockNotifier()

    @pytest.fixture
    def escalation_service(self, notifier):
        """Create a mock escalation service"""
        return MockEscalationService(notifier)

    @pytest.fixture
    def db_manager(self):
        """Create a mock database manager"""
        return MockDbManager()

    @pytest.fixture
    def alarm_manager(self, escalation_service, notifier, db_manager):
        """Create an alarm manager with mocks"""
        return AlarmManager(escalation_service, notifier, db_manager)

    @pytest.fixture
    def sample_definition(self):
        """Create a sample alarm definition"""
        return AlarmDefinition(
            alarm_code="TEMP_HIGH",
            equipment_type="cvd",
            severity=AlarmSeverity.MAJOR,
            description="Temperature too high",
            default_text="Temperature exceeds 150C threshold",
            suggested_action="Check cooling system",
        )

    @pytest.mark.asyncio
    async def test_raise_alarm(self, alarm_manager, notifier, escalation_service):
        """Test raising a new alarm"""
        alarm = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="TEST_ALARM",
            alarm_text="Test alarm text",
        )

        assert alarm is not None
        assert alarm.equipment_id == "eq-001"
        assert alarm.alarm_code == "TEST_ALARM"
        assert alarm.status == AlarmStatus.RAISED
        assert notifier.notify_count == 1
        assert escalation_service.start_count == 1

    @pytest.mark.asyncio
    async def test_raise_alarm_with_definition(self, alarm_manager, sample_definition):
        """Test raising alarm with registered definition"""
        alarm_manager.register_definition(sample_definition)

        alarm = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="TEMP_HIGH",
        )

        assert alarm is not None
        assert alarm.alarm_text == "Temperature exceeds 150C threshold"
        assert alarm.severity == AlarmSeverity.MAJOR

    @pytest.mark.asyncio
    async def test_raise_alarm_suppressed(self, alarm_manager):
        """Test raising suppressed alarm returns None"""
        alarm_manager._suppressed_codes.add("SUPPRESSED_ALARM")

        alarm = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="SUPPRESSED_ALARM",
        )

        assert alarm is None

    @pytest.mark.asyncio
    async def test_raise_alarm_duplicate(self, alarm_manager):
        """Test duplicate alarm is not created"""
        alarm1 = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="DUPLICATE_TEST",
        )

        alarm2 = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="DUPLICATE_TEST",
        )

        assert alarm1.id == alarm2.id
        assert alarm_manager.active_alarm_count == 1

    @pytest.mark.asyncio
    async def test_acknowledge_alarm(self, alarm_manager, escalation_service):
        """Test acknowledging an alarm"""
        alarm = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="TEST_ALARM",
        )

        result = await alarm_manager.acknowledge_alarm(alarm.id, "operator1")

        assert result is True
        assert alarm_manager.get_alarm(alarm.id).status == AlarmStatus.ACKNOWLEDGED
        assert alarm_manager.get_alarm(alarm.id).acknowledged_by == "operator1"
        assert escalation_service.stop_count == 1

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_alarm(self, alarm_manager):
        """Test acknowledging non-existent alarm"""
        result = await alarm_manager.acknowledge_alarm("nonexistent", "user")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_alarm(self, alarm_manager, escalation_service):
        """Test clearing an alarm"""
        alarm = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="TEST_ALARM",
        )

        result = await alarm_manager.clear_alarm(alarm.id, "operator1")

        assert result is True
        assert alarm.id not in alarm_manager._active_alarms
        assert escalation_service.stop_count == 1

    @pytest.mark.asyncio
    async def test_clear_nonexistent_alarm(self, alarm_manager):
        """Test clearing non-existent alarm"""
        result = await alarm_manager.clear_alarm("nonexistent", "user")
        assert result is False

    @pytest.mark.asyncio
    async def test_suppress_alarm(self, alarm_manager):
        """Test suppressing an alarm code"""
        await alarm_manager.suppress_alarm("TEST_ALARM", duration_seconds=3600)

        assert "TEST_ALARM" in alarm_manager._suppressed_codes

        # Suppressed alarm should not be raised
        alarm = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="TEST_ALARM",
        )
        assert alarm is None

    @pytest.mark.asyncio
    async def test_unsuppress_alarm(self, alarm_manager):
        """Test unsuppressing an alarm code"""
        alarm_manager._suppressed_codes.add("TEST_ALARM")

        result = await alarm_manager.unsuppress_alarm("TEST_ALARM")

        assert result is True
        assert "TEST_ALARM" not in alarm_manager._suppressed_codes

    @pytest.mark.asyncio
    async def test_get_active_alarms(self, alarm_manager):
        """Test getting active alarms"""
        # Create multiple alarms
        await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="ALARM_1",
            severity=AlarmSeverity.WARNING,
        )
        await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="ALARM_2",
            severity=AlarmSeverity.MAJOR,
        )
        await alarm_manager.raise_alarm(
            equipment_id="eq-002",
            alarm_code="ALARM_3",
            severity=AlarmSeverity.CRITICAL,
        )

        # Get all
        all_alarms = alarm_manager.get_active_alarms()
        assert len(all_alarms) == 3

        # Filter by equipment
        eq1_alarms = alarm_manager.get_active_alarms(equipment_id="eq-001")
        assert len(eq1_alarms) == 2

        # Filter by severity
        critical_alarms = alarm_manager.get_active_alarms(severity=AlarmSeverity.CRITICAL)
        assert len(critical_alarms) == 1

    @pytest.mark.asyncio
    async def test_get_alarm(self, alarm_manager):
        """Test getting a specific alarm"""
        alarm = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="TEST_ALARM",
        )

        retrieved = alarm_manager.get_alarm(alarm.id)
        assert retrieved is alarm

        nonexistent = alarm_manager.get_alarm("nonexistent")
        assert nonexistent is None

    def test_register_definition(self, alarm_manager, sample_definition):
        """Test registering alarm definition"""
        alarm_manager.register_definition(sample_definition)

        retrieved = alarm_manager.get_definition("TEMP_HIGH")
        assert retrieved is sample_definition

    def test_register_definitions(self, alarm_manager):
        """Test batch registering definitions"""
        definitions = [
            AlarmDefinition(
                alarm_code=f"ALARM_{i}",
                equipment_type="test",
                severity=AlarmSeverity.MINOR,
                description=f"Test alarm {i}",
                default_text=f"Default text {i}",
            )
            for i in range(3)
        ]

        alarm_manager.register_definitions(definitions)

        for i in range(3):
            assert alarm_manager.get_definition(f"ALARM_{i}") is not None

    @pytest.mark.asyncio
    async def test_get_statistics(self, alarm_manager):
        """Test getting alarm statistics"""
        # Create some alarms
        await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="CRIT_1",
            severity=AlarmSeverity.CRITICAL,
        )
        await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="MAJ_1",
            severity=AlarmSeverity.MAJOR,
        )
        await alarm_manager.raise_alarm(
            equipment_id="eq-002",
            alarm_code="MIN_1",
            severity=AlarmSeverity.MINOR,
        )

        stats = await alarm_manager.get_statistics()

        assert stats.active_count == 3
        assert stats.by_severity["critical"] == 1
        assert stats.by_severity["major"] == 1
        assert stats.by_severity["minor"] == 1
        assert "eq-001" in stats.by_equipment
        assert "eq-002" in stats.by_equipment

    def test_set_callback(self, alarm_manager):
        """Test setting alarm callbacks"""
        callbacks_called = []

        def on_alarm(alarm):
            callbacks_called.append(("alarm", alarm.id))

        def on_ack(alarm):
            callbacks_called.append(("ack", alarm.id))

        def on_clear(alarm):
            callbacks_called.append(("clear", alarm.id))

        alarm_manager.set_callback("alarm", on_alarm)
        alarm_manager.set_callback("acknowledged", on_ack)
        alarm_manager.set_callback("cleared", on_clear)

        assert alarm_manager._on_alarm is on_alarm
        assert alarm_manager._on_alarm_acknowledged is on_ack
        assert alarm_manager._on_alarm_cleared is on_clear

    @pytest.mark.asyncio
    async def test_callback_on_alarm(self, alarm_manager):
        """Test alarm callback is called"""
        callback_called = []

        async def on_alarm(alarm):
            callback_called.append(alarm.id)

        alarm_manager.set_callback("alarm", on_alarm)

        alarm = await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="TEST",
        )

        assert callback_called[0] == alarm.id

    def test_active_alarm_count(self, alarm_manager):
        """Test active alarm count property"""
        assert alarm_manager.active_alarm_count == 0

    def test_find_existing_alarm(self, alarm_manager):
        """Test finding existing alarm"""
        assert alarm_manager._find_existing_alarm("eq-001", "TEST") is None

    @pytest.mark.asyncio
    async def test_shutdown(self, alarm_manager, escalation_service):
        """Test shutdown cleanup"""
        await alarm_manager.raise_alarm(
            equipment_id="eq-001",
            alarm_code="TEST",
        )

        await alarm_manager.shutdown()

        # After shutdown, active alarms should be 0
        assert alarm_manager.active_alarm_count == 0
