"""Alarm notifier tests"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from myeap.alarm.models import (
    Alarm,
    AlarmSeverity,
)
from myeap.alarm.notifier import (
    AlarmNotifier,
    EmailChannel,
    SMSChannel,
    WebhookChannel,
    InAppChannel,
    NotificationChannel,
)


class ConcreteTestChannel(NotificationChannel):
    """Concrete implementation for testing base class"""

    name = "test"

    async def send(
        self,
        alarm: Alarm,
        recipient=None,
        escalation_level: int = 0,
        message=None,
        **kwargs,
    ) -> bool:
        return True


class TestNotificationChannel:
    """NotificationChannel base class tests"""

    def test_format_alarm_message(self):
        """Test alarm message formatting"""
        channel = ConcreteTestChannel()

        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.CRITICAL,
            raised_at=datetime(2024, 1, 1, 12, 0, 0),
        )

        message = channel.format_alarm_message(alarm, escalation_level=2, message="Urgent")
        assert "CRITICAL" in message
        assert "Test alarm" in message
        assert "eq-001" in message
        assert "TEST" in message
        assert "Escalation Level: 2" in message
        assert "Urgent" in message


class TestEmailChannel:
    """EmailChannel tests"""

    @pytest.fixture
    def email_channel(self):
        """Create an email channel for testing"""
        return EmailChannel(
            smtp_host="smtp.test.com",
            smtp_port=587,
            from_address="alarm@test.com",
        )

    def test_initialization(self, email_channel):
        """Test channel initialization"""
        assert email_channel.smtp_host == "smtp.test.com"
        assert email_channel.smtp_port == 587
        assert email_channel.from_address == "alarm@test.com"

    @pytest.mark.asyncio
    async def test_send_email(self, email_channel):
        """Test sending email"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.MAJOR,
            raised_at=datetime.utcnow(),
        )

        result = await email_channel.send(
            alarm,
            recipient="user@test.com",
            message="Test message",
        )
        assert result is True

    def test_get_subject(self, email_channel):
        """Test email subject generation"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.CRITICAL,
            raised_at=datetime.utcnow(),
        )

        subject = email_channel._get_subject(alarm, escalation_level=0)
        assert "CRITICAL" in subject

        subject = email_channel._get_subject(alarm, escalation_level=2)
        assert "ESCALATED L2" in subject


class TestSMSChannel:
    """SMSChannel tests"""

    @pytest.fixture
    def sms_channel(self):
        """Create an SMS channel for testing"""
        return SMSChannel(
            api_url="http://sms-gateway.local/api/send",
            api_key="test-key",
        )

    def test_initialization(self, sms_channel):
        """Test channel initialization"""
        assert sms_channel.api_url == "http://sms-gateway.local/api/send"
        assert sms_channel.api_key == "test-key"

    @pytest.mark.asyncio
    async def test_send_sms(self, sms_channel):
        """Test sending SMS"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.CRITICAL,
            raised_at=datetime.utcnow(),
        )

        result = await sms_channel.send(
            alarm,
            recipient="+1234567890",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_sms_no_recipient(self, sms_channel):
        """Test sending SMS without recipient fails"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.MINOR,
            raised_at=datetime.utcnow(),
        )

        result = await sms_channel.send(alarm)
        assert result is False


class TestWebhookChannel:
    """WebhookChannel tests"""

    @pytest.fixture
    def webhook_channel(self):
        """Create a webhook channel for testing"""
        return WebhookChannel(
            webhook_url="http://webhook.local/notify",
            headers={"Authorization": "Bearer test"},
        )

    def test_initialization(self, webhook_channel):
        """Test channel initialization"""
        assert webhook_channel.webhook_url == "http://webhook.local/notify"
        assert webhook_channel.headers["Authorization"] == "Bearer test"

    @pytest.mark.asyncio
    async def test_send_webhook(self, webhook_channel):
        """Test sending webhook"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.MAJOR,
            raised_at=datetime.utcnow(),
        )

        result = await webhook_channel.send(alarm)
        assert result is True

    def test_build_payload(self, webhook_channel):
        """Test webhook payload building"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.MAJOR,
            raised_at=datetime.utcnow(),
        )

        payload = webhook_channel._build_payload(alarm, escalation_level=1, message="Test")
        assert payload["type"] == "alarm"
        assert payload["escalation_level"] == 1
        assert payload["message"] == "Test"


class TestInAppChannel:
    """InAppChannel tests"""

    @pytest.fixture
    def inapp_channel(self):
        """Create an in-app channel for testing"""
        return InAppChannel()

    def test_initialization(self, inapp_channel):
        """Test channel initialization"""
        assert inapp_channel._notifications == []

    @pytest.mark.asyncio
    async def test_send_notification(self, inapp_channel):
        """Test sending in-app notification"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.MAJOR,
            raised_at=datetime.utcnow(),
        )

        result = await inapp_channel.send(alarm, recipient="user@test.com")
        assert result is True
        assert len(inapp_channel._notifications) == 1

    def test_get_notifications(self, inapp_channel):
        """Test getting notifications"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.MAJOR,
            raised_at=datetime.utcnow(),
        )

        # Send notifications for different recipients
        asyncio.run(inapp_channel.send(alarm, recipient="user1@test.com"))
        asyncio.run(inapp_channel.send(alarm, recipient="user2@test.com"))
        asyncio.run(inapp_channel.send(alarm, recipient="user1@test.com"))

        # Get all notifications
        all_notifs = inapp_channel.get_notifications()
        assert len(all_notifs) == 3

        # Filter by recipient
        user1_notifs = inapp_channel.get_notifications(recipient="user1@test.com")
        assert len(user1_notifs) == 2

    def test_get_title(self, inapp_channel):
        """Test notification title generation"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.CRITICAL,
            raised_at=datetime.utcnow(),
        )

        title = inapp_channel._get_title(alarm)
        assert title == "Critical Alarm"


class TestAlarmNotifier:
    """AlarmNotifier tests"""

    @pytest.fixture
    def notifier(self):
        """Create an alarm notifier for testing"""
        return AlarmNotifier()

    def test_initialization(self, notifier):
        """Test notifier initialization"""
        # Should have default inapp channel
        assert "inapp" in notifier.channels

    def test_register_channel(self, notifier):
        """Test registering a new channel"""
        email = EmailChannel()
        notifier.register_channel(email)

        assert "email" in notifier.channels
        assert notifier.get_channel("email") is email

    def test_unregister_channel(self, notifier):
        """Test unregistering a channel"""
        email = EmailChannel()
        notifier.register_channel(email)
        assert "email" in notifier.channels

        result = notifier.unregister_channel("email")
        assert result is True
        assert "email" not in notifier.channels

    def test_unregister_protected_channel(self, notifier):
        """Test cannot unregister protected channels"""
        result = notifier.unregister_channel("inapp")
        assert result is False

    def test_get_channel(self, notifier):
        """Test getting a channel"""
        email = EmailChannel()
        notifier.register_channel(email)

        assert notifier.get_channel("email") is email
        assert notifier.get_channel("nonexistent") is None

    @pytest.mark.asyncio
    async def test_notify(self, notifier):
        """Test sending notification"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.MAJOR,
            raised_at=datetime.utcnow(),
        )

        # Should not raise
        await notifier.notify(alarm, recipient="user@test.com")

    @pytest.mark.asyncio
    async def test_notify_custom_channels(self, notifier):
        """Test sending notification through specific channels"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.MINOR,
            raised_at=datetime.utcnow(),
        )

        await notifier.notify_custom(
            alarm,
            channel_names=["inapp"],
            recipient="user@test.com",
        )

    def test_get_channels_for_alarm_critical(self, notifier):
        """Test channel selection for critical alarm"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.CRITICAL,
            raised_at=datetime.utcnow(),
        )

        channels = notifier._get_channels_for_alarm(alarm)
        assert "sms" in channels
        assert "email" in channels
        assert "webhook" in channels
        assert "inapp" in channels

    def test_get_channels_for_alarm_minor(self, notifier):
        """Test channel selection for minor alarm"""
        alarm = Alarm(
            id="alarm-001",
            equipment_id="eq-001",
            alarm_code="TEST",
            alarm_text="Test alarm",
            severity=AlarmSeverity.MINOR,
            raised_at=datetime.utcnow(),
        )

        channels = notifier._get_channels_for_alarm(alarm)
        assert "sms" not in channels
        assert "webhook" in channels
        assert "inapp" in channels
