"""Alarm models tests"""

import pytest
from datetime import datetime, timedelta

from myeap.alarm.models import (
    Alarm,
    AlarmDefinition,
    AlarmEscalationPolicy,
    AlarmSeverity,
    AlarmStatus,
    AlarmStatistics,
)


class TestAlarmSeverity:
    """AlarmSeverity tests"""

    def test_priority_values(self):
        """Test priority values for each severity level"""
        assert AlarmSeverity.CRITICAL.priority == 1
        assert AlarmSeverity.MAJOR.priority == 2
        assert AlarmSeverity.MINOR.priority == 3
        assert AlarmSeverity.WARNING.priority == 4

    def test_from_string(self):
        """Test converting from string to enum"""
        assert AlarmSeverity.from_string("critical") == AlarmSeverity.CRITICAL
        assert AlarmSeverity.from_string("MAJOR") == AlarmSeverity.MAJOR
        assert AlarmSeverity.from_string("Minor") == AlarmSeverity.MINOR
        assert AlarmSeverity.from_string("unknown") == AlarmSeverity.WARNING

    def test_all_severities_have_value(self):
        """Test all severity levels have string values"""
        for severity in AlarmSeverity:
            assert severity.value is not None
            assert isinstance(severity.value, str)


class TestAlarmStatus:
    """AlarmStatus tests"""

    def test_status_values(self):
        """Test status enum values"""
        assert AlarmStatus.RAISED.value == "raised"
        assert AlarmStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlarmStatus.CLEARED.value == "cleared"
        assert AlarmStatus.SUPPRESSED.value == "suppressed"


class TestAlarm:
    """Alarm model tests"""

    def test_creation(self):
        """Test creating an alarm"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEMP_HIGH",
            alarm_text="Temperature exceeds threshold",
            severity=AlarmSeverity.MAJOR,
            raised_at=datetime.utcnow(),
        )

        assert alarm.id == "alarm-001"
        assert alarm.equipment_id == "eq-001"
        assert alarm.alarm_code == "TEMP_HIGH"
        assert alarm.severity == AlarmSeverity.MAJOR
        assert alarm.status == AlarmStatus.RAISED
        assert alarm.escalated is False
        assert alarm.escalation_level == 0
        assert alarm.suppressed is False

    def test_is_active(self):
        """Test is_active property"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test",
            severity=AlarmSeverity.MINOR,
            raised_at=datetime.utcnow(),
        )

        # RAISED is active
        assert alarm.is_active is True

        # ACKNOWLEDGED is active
        alarm.status = AlarmStatus.ACKNOWLEDGED
        assert alarm.is_active is True

        # CLEARED is not active
        alarm.status = AlarmStatus.CLEARED
        assert alarm.is_active is False

    def test_needs_attention(self):
        """Test needs_attention property"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test",
            severity=AlarmSeverity.MINOR,
            raised_at=datetime.utcnow(),
        )

        # RAISED needs attention
        assert alarm.needs_attention is True

        # ACKNOWLEDGED does not need attention
        alarm.status = AlarmStatus.ACKNOWLEDGED
        assert alarm.needs_attention is False

    def test_to_dict(self):
        """Test converting alarm to dictionary"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEMP_HIGH",
            alarm_text="Temperature exceeds threshold",
            severity=AlarmSeverity.MAJOR,
            raised_at=datetime(2024, 1, 1, 12, 0, 0),
            parameters={"temperature": 150.0},
        )

        data = alarm.to_dict()
        assert data["id"] == "alarm-001"
        assert data["equipment_id"] == "eq-001"
        assert data["alarm_code"] == "TEMP_HIGH"
        assert data["severity"] == "major"
        assert data["status"] == "raised"
        assert data["parameters"]["temperature"] == 150.0

    def test_repr(self):
        """Test string representation"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.CRITICAL,
            raised_at=datetime.utcnow(),
        )

        repr_str = repr(alarm)
        assert "alarm-001" in repr_str
        assert "TEST" in repr_str
        assert "critical" in repr_str


class TestAlarmDefinition:
    """AlarmDefinition tests"""

    def test_creation(self):
        """Test creating an alarm definition"""
        definition = AlarmDefinition(
            alarm_code="TEMP_HIGH",
            equipment_type="cvd",
            severity=AlarmSeverity.MAJOR,
            description="Temperature too high",
            default_text="Temperature exceeds 150C threshold",
            suggested_action="Check cooling system",
            auto_clear=True,
            auto_clear_delay=300,
        )

        assert definition.alarm_code == "TEMP_HIGH"
        assert definition.equipment_type == "cvd"
        assert definition.severity == AlarmSeverity.MAJOR
        assert definition.auto_clear is True
        assert definition.auto_clear_delay == 300

    def test_to_dict(self):
        """Test converting definition to dictionary"""
        definition = AlarmDefinition(
            alarm_code="TEST",
            equipment_type="cleaner",
            severity=AlarmSeverity.WARNING,
            description="Test description",
            default_text="Test text",
        )

        data = definition.to_dict()
        assert data["alarm_code"] == "TEST"
        assert data["severity"] == "warning"
        assert data["auto_clear"] is False


class TestAlarmEscalationPolicy:
    """AlarmEscalationPolicy tests"""

    def test_creation(self):
        """Test creating an escalation policy"""
        policy = AlarmEscalationPolicy(
            severity=AlarmSeverity.CRITICAL,
            initial_delay=60,
            escalation_interval=300,
            max_escalation_level=3,
            notify_channels=["email", "sms"],
            assignees=["operator", "supervisor", "manager"],
        )

        assert policy.severity == AlarmSeverity.CRITICAL
        assert policy.initial_delay == 60
        assert policy.escalation_interval == 300
        assert policy.max_escalation_level == 3
        assert "email" in policy.notify_channels
        assert len(policy.assignees) == 3

    def test_to_dict(self):
        """Test converting policy to dictionary"""
        policy = AlarmEscalationPolicy(
            severity=AlarmSeverity.MAJOR,
            initial_delay=300,
            escalation_interval=600,
            max_escalation_level=2,
            notify_channels=["email"],
            assignees=["operator", "supervisor"],
        )

        data = policy.to_dict()
        assert data["severity"] == "major"
        assert data["max_escalation_level"] == 2


class TestAlarmStatistics:
    """AlarmStatistics tests"""

    def test_creation(self):
        """Test creating alarm statistics"""
        stats = AlarmStatistics(
            total_count=100,
            active_count=10,
            by_severity={"critical": 2, "major": 5, "minor": 3},
            by_equipment={"eq-001": 5, "eq-002": 5},
            mtta=120.5,
            escalation_count=2,
        )

        assert stats.total_count == 100
        assert stats.active_count == 10
        assert stats.by_severity["critical"] == 2
        assert stats.mtta == 120.5

    def test_to_dict(self):
        """Test converting statistics to dictionary"""
        stats = AlarmStatistics(
            total_count=50,
            active_count=5,
            by_severity={"major": 5},
        )

        data = stats.to_dict()
        assert data["total_count"] == 50
        assert data["active_count"] == 5
