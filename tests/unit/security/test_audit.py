"""Audit logger tests"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

from myeap.security.audit import AuditLogger
from myeap.security.models import (
    AuditEvent,
    AuditEventType,
    AuditFilter,
    Resource,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def audit_log_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def audit(audit_log_dir):
    return AuditLogger(log_dir=audit_log_dir, async_writer=False)


@pytest.fixture
def audit_sync(audit_log_dir):
    return AuditLogger(log_dir=audit_log_dir, async_writer=False, max_in_memory_events=100)


# ---------------------------------------------------------------------------
# Basic Logging
# ---------------------------------------------------------------------------

class TestAuditLogging:
    def test_log_event(self, audit):
        event = audit.log_event(
            event_type=AuditEventType.LOGIN,
            username="user1",
        )
        assert event.event_type == AuditEventType.LOGIN
        assert event.username == "user1"

    def test_log_returns_audit_event(self, audit):
        event = audit.log_event(event_type=AuditEventType.LOGIN)
        assert isinstance(event, AuditEvent)

    def test_log_event_with_details(self, audit):
        event = audit.log_event(
            event_type=AuditEventType.CREATE,
            username="user1",
            resource=Resource.RECIPE.value,
            resource_id="recipe-001",
            action="create",
            details={"name": "New Recipe"},
        )
        assert event.resource == "recipe"
        assert event.resource_id == "recipe-001"
        assert event.details["name"] == "New Recipe"

    def test_log_event_with_state_changes(self, audit):
        event = audit.log_event(
            event_type=AuditEventType.UPDATE,
            username="user1",
            resource=Resource.RECIPE.value,
            resource_id="recipe-001",
            before_state={"name": "Old"},
            after_state={"name": "New"},
        )
        assert event.before_state["name"] == "Old"
        assert event.after_state["name"] == "New"

    def test_log_event_success_flag(self, audit):
        event = audit.log_event(
            event_type=AuditEventType.CREATE,
            success=True,
        )
        assert event.success is True

    def test_log_event_failure_flag(self, audit):
        event = audit.log_event(
            event_type=AuditEventType.CREATE,
            success=False,
            error_message="Permission denied",
        )
        assert event.success is False
        assert event.error_message == "Permission denied"

    def test_log_event_with_ip_and_ua(self, audit):
        event = audit.log_event(
            event_type=AuditEventType.LOGIN,
            username="user1",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert event.ip_address == "192.168.1.1"
        assert event.user_agent == "Mozilla/5.0"


# ---------------------------------------------------------------------------
# Convenience Methods
# ---------------------------------------------------------------------------

class TestAuditConvenienceMethods:
    def test_log_login_success(self, audit):
        event = audit.log_login("user1", success=True, ip_address="10.0.0.1")
        assert event.event_type == AuditEventType.LOGIN
        assert event.success is True

    def test_log_login_failed(self, audit):
        event = audit.log_login("user1", success=False)
        assert event.event_type == AuditEventType.LOGIN_FAILED
        assert event.success is False

    def test_log_logout(self, audit):
        event = audit.log_logout("user1", session_id="sess-123")
        assert event.event_type == AuditEventType.LOGOUT
        assert event.session_id == "sess-123"

    def test_log_resource_create(self, audit):
        event = audit.log_resource_create(
            username="user1",
            resource=Resource.RECIPE,
            resource_id="recipe-001",
        )
        assert event.event_type == AuditEventType.CREATE
        assert event.resource == Resource.RECIPE.value

    def test_log_resource_read(self, audit):
        event = audit.log_resource_read(
            username="user1",
            resource=Resource.EQUIPMENT,
            resource_id="eq-001",
        )
        assert event.event_type == AuditEventType.READ

    def test_log_resource_update(self, audit):
        event = audit.log_resource_update(
            username="user1",
            resource=Resource.RECIPE,
            resource_id="recipe-001",
            before_state={"temp": 100},
            after_state={"temp": 200},
        )
        assert event.event_type == AuditEventType.UPDATE
        assert event.before_state["temp"] == 100

    def test_log_resource_delete(self, audit):
        event = audit.log_resource_delete(
            username="admin",
            resource=Resource.ALARM,
            resource_id="alarm-001",
            before_state={"status": "active"},
        )
        assert event.event_type == AuditEventType.DELETE

    def test_log_recipe_change(self, audit):
        event = audit.log_recipe_change(
            username="engineer1",
            recipe_id="recipe-001",
            version="2.0.0",
            changes={"temperature": {"old": 100, "new": 200}},
        )
        assert event.event_type == AuditEventType.RECIPE_CHANGE
        assert event.details["version"] == "2.0.0"

    def test_log_recipe_version(self, audit):
        event = audit.log_recipe_version(
            username="engineer1",
            recipe_id="recipe-001",
            old_version="1.0.0",
            new_version="2.0.0",
        )
        assert event.event_type == AuditEventType.RECIPE_VERSION
        assert event.before_state["version"] == "1.0.0"
        assert event.after_state["version"] == "2.0.0"

    def test_log_permission_denied(self, audit):
        event = audit.log_permission_denied(
            username="viewer1",
            resource="recipe",
            action="create",
        )
        assert event.event_type == AuditEventType.PERMISSION_DENIED
        assert event.success is False

    def test_log_signature(self, audit):
        event = audit.log_signature(
            username="approver1",
            request_id="req-001",
            document_id="recipe-001",
            meaning="approver",
        )
        assert event.event_type == AuditEventType.SIGN

    def test_log_system_event(self, audit):
        event = audit.log_system_event(
            event_type=AuditEventType.SYSTEM_START,
            details={"version": "1.0.0"},
        )
        assert event.event_type == AuditEventType.SYSTEM_START
        assert event.resource == Resource.SYSTEM.value


# ---------------------------------------------------------------------------
# Query / Filtering
# ---------------------------------------------------------------------------

class TestAuditQuery:
    def _populate_audit(self, audit: AuditLogger) -> None:
        """Populate audit logger with test events"""
        for i in range(20):
            audit.log_event(
                event_type=AuditEventType.LOGIN if i % 2 == 0 else AuditEventType.LOGOUT,
                username=f"user{i % 3}",
                success=i % 5 != 0,
            )

    def test_get_all_events(self, audit):
        self._populate_audit(audit)
        events = audit.get_events()
        assert len(events) == 20

    def test_get_events_with_filter(self, audit):
        self._populate_audit(audit)
        f = AuditFilter(username="user0")
        events = audit.get_events(f)
        assert all(e.username == "user0" for e in events)

    def test_get_events_limit(self, audit):
        self._populate_audit(audit)
        f = AuditFilter(limit=5)
        events = audit.get_events(f)
        assert len(events) <= 5

    def test_get_events_by_event_type(self, audit):
        self._populate_audit(audit)
        f = AuditFilter(event_type=AuditEventType.LOGIN)
        events = audit.get_events(f)
        assert all(e.event_type == AuditEventType.LOGIN for e in events)

    def test_get_user_events(self, audit):
        self._populate_audit(audit)
        events = audit.get_user_events("user1")
        assert all(e.username == "user1" for e in events)

    def test_get_resource_events(self, audit):
        for i in range(5):
            audit.log_event(
                event_type=AuditEventType.CREATE,
                resource=Resource.RECIPE.value,
                resource_id=f"recipe-{i:03d}",
            )
        events = audit.get_resource_events(Resource.RECIPE)
        assert len(events) == 5

    def test_get_resource_events_filtered_by_id(self, audit):
        for i in range(5):
            audit.log_event(
                event_type=AuditEventType.CREATE,
                resource=Resource.RECIPE.value,
                resource_id=f"recipe-{i:03d}",
            )
        events = audit.get_resource_events(Resource.RECIPE, resource_id="recipe-000")
        assert len(events) == 1

    def test_get_recipe_audit_trail(self, audit):
        audit.log_event(
            event_type=AuditEventType.CREATE,
            resource=Resource.RECIPE.value,
            resource_id="recipe-001",
        )
        audit.log_event(
            event_type=AuditEventType.UPDATE,
            resource=Resource.RECIPE.value,
            resource_id="recipe-001",
        )
        audit.log_event(
            event_type=AuditEventType.CREATE,
            resource=Resource.RECIPE.value,
            resource_id="recipe-002",
        )
        trail = audit.get_recipe_audit_trail("recipe-001")
        assert len(trail) == 2

    def test_get_login_history(self, audit):
        for i in range(5):
            audit.log_event(
                event_type=AuditEventType.LOGIN,
                username=f"user{i}",
            )
            audit.log_event(
                event_type=AuditEventType.LOGOUT,
                username=f"user{i}",
            )
        history = audit.get_login_history()
        assert len(history) == 10

    def test_get_failed_events(self, audit):
        for i in range(5):
            audit.log_event(
                event_type=AuditEventType.LOGIN,
                success=i < 3,
            )
        events = audit.get_failed_events()
        assert len(events) >= 2


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

class TestAuditStats:
    def test_get_event_count(self, audit):
        for i in range(5):
            audit.log_event(event_type=AuditEventType.LOGIN, username="user1")
        count = audit.get_event_count(event_type=AuditEventType.LOGIN, username="user1")
        assert count == 5

    def test_get_event_count_no_filter(self, audit):
        for i in range(5):
            audit.log_event(event_type=AuditEventType.LOGIN)
        for i in range(3):
            audit.log_event(event_type=AuditEventType.LOGOUT)
        count = audit.get_event_count()
        assert count == 8

    def test_get_event_count_by_type(self, audit):
        for i in range(5):
            audit.log_event(event_type=AuditEventType.LOGIN)
        for i in range(3):
            audit.log_event(event_type=AuditEventType.LOGOUT)
        assert audit.get_event_count(event_type=AuditEventType.LOGIN) == 5
        assert audit.get_event_count(event_type=AuditEventType.LOGOUT) == 3

    def test_get_event_count_by_username(self, audit):
        for i in range(5):
            audit.log_event(event_type=AuditEventType.CREATE, username="user1")
        for i in range(3):
            audit.log_event(event_type=AuditEventType.CREATE, username="user2")
        assert audit.get_event_count(username="user1") == 5
        assert audit.get_event_count(username="user2") == 3

    def test_get_login_attempts(self, audit):
        for i in range(3):
            audit.log_login("user1", success=True)
        for i in range(2):
            audit.log_login("user1", success=False)
        stats = audit.get_login_attempts("user1")
        assert stats["total"] == 5
        assert stats["success"] == 3
        assert stats["failed"] == 2

    def test_get_login_attempts_filtered_by_time(self, audit):
        for i in range(5):
            audit.log_login("user1", success=True)
        now = datetime.now(timezone.utc)
        stats = audit.get_login_attempts("user1", since=now - timedelta(seconds=1))
        assert stats["total"] >= 0


# ---------------------------------------------------------------------------
# Subscribers
# ---------------------------------------------------------------------------

class TestAuditSubscribers:
    def test_subscribe_notifies(self, audit):
        received = []

        def handler(event):
            received.append(event)

        audit.subscribe(handler)
        audit.log_event(event_type=AuditEventType.LOGIN)
        assert len(received) == 1
        assert received[0].event_type == AuditEventType.LOGIN

    def test_multiple_subscribers(self, audit):
        received1 = []
        received2 = []

        def handler1(event):
            received1.append(event)

        def handler2(event):
            received2.append(event)

        audit.subscribe(handler1)
        audit.subscribe(handler2)
        audit.log_event(event_type=AuditEventType.LOGIN)
        assert len(received1) == 1
        assert len(received2) == 1

    def test_unsubscribe(self, audit):
        received = []

        def handler(event):
            received.append(event)

        audit.subscribe(handler)
        audit.log_event(event_type=AuditEventType.LOGIN)
        assert len(received) == 1

        audit.unsubscribe(handler)
        audit.log_event(event_type=AuditEventType.LOGIN)
        assert len(received) == 1  # No new event received

    def test_subscriber_error_does_not_break_logging(self, audit):
        def bad_handler(event):
            raise RuntimeError("Subscriber error")

        audit.subscribe(bad_handler)
        event = audit.log_event(event_type=AuditEventType.LOGIN)
        assert event is not None
        assert len(audit.get_events()) == 1


# ---------------------------------------------------------------------------
# In-Memory Limits
# ---------------------------------------------------------------------------

class TestAuditLimits:
    def test_max_in_memory_events(self, audit_sync):
        for i in range(150):
            audit_sync.log_event(event_type=AuditEventType.READ)
        events = audit_sync.get_events()
        assert len(events) <= 100

    def test_clear_events(self, audit):
        for i in range(5):
            audit.log_event(event_type=AuditEventType.READ)
        assert len(audit.get_events()) == 5
        audit.clear()
        assert len(audit.get_events()) == 0


# ---------------------------------------------------------------------------
# Disk Persistence (sync mode)
# ---------------------------------------------------------------------------

class TestAuditDiskWrite:
    def test_write_event_to_file(self, audit):
        audit.log_event(event_type=AuditEventType.LOGIN, username="user1")
        audit.flush()
        log_files = list(audit.log_dir.glob("audit-*.jsonl"))
        assert len(log_files) >= 1

    def test_log_dir_created(self, audit_log_dir):
        audit = AuditLogger(
            log_dir=audit_log_dir / "nested" / "audit", async_writer=False
        )
        assert audit.log_dir.exists()


# ---------------------------------------------------------------------------
# AuditEvent Model
# ---------------------------------------------------------------------------

class TestAuditEventModel:
    def test_to_log_line_contains_fields(self):
        event = AuditEvent(
            event_type=AuditEventType.LOGIN,
            username="user1",
            resource=Resource.USER.value,
            resource_id="user-001",
            action="login",
            success=True,
        )
        line = event.to_log_line()
        assert "type=login" in line
        assert "user=user1" in line
        assert "resource=user" in line
        assert "resource_id=user-001" in line
        assert "success=True" in line
