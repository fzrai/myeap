"""Audit Logging Service

Enterprise audit logging for all operations, recipe changes,
login/logout records, and data access audit trails.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from myeap.core.config import get_settings
from myeap.security.models import (
    AuditEvent,
    AuditEventType,
    AuditFilter,
    Resource,
)


class AuditLogger:
    """Enterprise audit logging service

    Records all security-relevant events with full context including:
    - Who performed the action
    - What resource was affected
    - When it happened
    - What changed (before/after state)
    - Whether it succeeded or failed
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        max_in_memory_events: int = 10000,
        async_writer: bool = True,
    ):
        settings = get_settings()
        self.log_dir = log_dir or settings.log_dir / "audit"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_in_memory_events = max_in_memory_events
        self.async_writer = async_writer

        self._events: List[AuditEvent] = []
        self._lock = threading.Lock()
        self._write_queue: List[AuditEvent] = []
        self._subscribers: List[Callable[[AuditEvent], None]] = []

    # ------------------------------------------------------------------
    # Event Logging
    # ------------------------------------------------------------------

    def log(self, event: AuditEvent) -> None:
        """Log an audit event

        The event is stored in memory and optionally written to disk.
        Subscribers are notified of the event.
        """
        with self._lock:
            self._events.append(event)
            # Evict old events if exceeding limit
            if len(self._events) > self.max_in_memory_events:
                self._events = self._events[-self.max_in_memory_events:]

        # Notify subscribers
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception:
                pass  # Subscriber errors must not break logging

        # Write to disk if async_writer is off (sync mode)
        if not self.async_writer:
            self._write_event(event)

    def log_event(
        self,
        event_type: AuditEventType,
        username: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Create and log an audit event with the given parameters"""
        event = AuditEvent(
            event_type=event_type,
            username=username,
            resource=resource,
            resource_id=resource_id,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=success,
            error_message=error_message,
            before_state=before_state,
            after_state=after_state,
        )
        self.log(event)
        return event

    # ------------------------------------------------------------------
    # Convenience methods for common events
    # ------------------------------------------------------------------

    def log_login(
        self, username: str, success: bool = True, ip_address: Optional[str] = None
    ) -> AuditEvent:
        """Log a login event"""
        return self.log_event(
            event_type=AuditEventType.LOGIN if success else AuditEventType.LOGIN_FAILED,
            username=username,
            resource=Resource.USER.value,
            action="login",
            ip_address=ip_address,
            success=success,
            error_message=None if success else "Invalid credentials",
        )

    def log_logout(self, username: str, session_id: Optional[str] = None) -> AuditEvent:
        """Log a logout event"""
        return self.log_event(
            event_type=AuditEventType.LOGOUT,
            username=username,
            resource=Resource.USER.value,
            action="logout",
            session_id=session_id,
        )

    def log_resource_create(
        self,
        username: str,
        resource: Resource,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log resource creation"""
        return self.log_event(
            event_type=AuditEventType.CREATE,
            username=username,
            resource=resource.value,
            resource_id=resource_id,
            action="create",
            details=details,
        )

    def log_resource_read(
        self,
        username: str,
        resource: Resource,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log resource access"""
        return self.log_event(
            event_type=AuditEventType.READ,
            username=username,
            resource=resource.value,
            resource_id=resource_id,
            action="read",
            details=details,
        )

    def log_resource_update(
        self,
        username: str,
        resource: Resource,
        resource_id: str,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any],
    ) -> AuditEvent:
        """Log resource update with change tracking"""
        return self.log_event(
            event_type=AuditEventType.UPDATE,
            username=username,
            resource=resource.value,
            resource_id=resource_id,
            action="update",
            before_state=before_state,
            after_state=after_state,
        )

    def log_resource_delete(
        self,
        username: str,
        resource: Resource,
        resource_id: str,
        before_state: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log resource deletion"""
        return self.log_event(
            event_type=AuditEventType.DELETE,
            username=username,
            resource=resource.value,
            resource_id=resource_id,
            action="delete",
            before_state=before_state,
        )

    def log_recipe_change(
        self,
        username: str,
        recipe_id: str,
        version: str,
        changes: Dict[str, Any],
    ) -> AuditEvent:
        """Log recipe modification (special handling for recipe audit trails)"""
        return self.log_event(
            event_type=AuditEventType.RECIPE_CHANGE,
            username=username,
            resource=Resource.RECIPE.value,
            resource_id=recipe_id,
            action="change",
            details={"version": version, "changes": changes},
        )

    def log_recipe_version(
        self,
        username: str,
        recipe_id: str,
        old_version: str,
        new_version: str,
    ) -> AuditEvent:
        """Log recipe version change"""
        return self.log_event(
            event_type=AuditEventType.RECIPE_VERSION,
            username=username,
            resource=Resource.RECIPE.value,
            resource_id=recipe_id,
            action="version",
            before_state={"version": old_version},
            after_state={"version": new_version},
        )

    def log_permission_denied(
        self,
        username: str,
        resource: str,
        action: str,
    ) -> AuditEvent:
        """Log a permission denied event"""
        return self.log_event(
            event_type=AuditEventType.PERMISSION_DENIED,
            username=username,
            resource=resource,
            action=action,
            success=False,
            error_message="Permission denied",
        )

    def log_signature(
        self,
        username: str,
        request_id: str,
        document_id: str,
        meaning: str,
    ) -> AuditEvent:
        """Log an electronic signature event"""
        return self.log_event(
            event_type=AuditEventType.SIGN,
            username=username,
            resource="signature",
            resource_id=request_id,
            action="sign",
            details={"document_id": document_id, "meaning": meaning},
        )

    def log_system_event(
        self,
        event_type: AuditEventType,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log a system-level event"""
        return self.log_event(
            event_type=event_type,
            resource=Resource.SYSTEM.value,
            details=details,
        )

    # ------------------------------------------------------------------
    # Query / Filtering
    # ------------------------------------------------------------------

    def get_events(self, filter: Optional[AuditFilter] = None) -> List[AuditEvent]:
        """Get events matching optional filter"""
        with self._lock:
            events = list(self._events)

        if filter is None:
            return events[-filter.limit:] if filter else events

        matched = []
        for event in reversed(events):
            if filter.matches(event):
                matched.append(event)
                if len(matched) >= filter.limit:
                    break
        return list(reversed(matched))

    def get_user_events(
        self,
        username: str,
        limit: int = 100,
        event_type: Optional[AuditEventType] = None,
    ) -> List[AuditEvent]:
        """Get events for a specific user"""
        f = AuditFilter(
            username=username, limit=limit, event_type=event_type
        )
        return self.get_events(f)

    def get_resource_events(
        self,
        resource: Resource,
        resource_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get events for a specific resource"""
        f = AuditFilter(
            resource=resource.value, resource_id=resource_id, limit=limit
        )
        return self.get_events(f)

    def get_recipe_audit_trail(
        self,
        recipe_id: str,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get complete audit trail for a recipe"""
        f = AuditFilter(
            resource=Resource.RECIPE.value, resource_id=recipe_id, limit=limit
        )
        return self.get_events(f)

    def get_login_history(
        self,
        username: Optional[str] = None,
        limit: int = 50,
    ) -> List[AuditEvent]:
        """Get login/logout history"""
        events = self.get_events(
            AuditFilter(username=username, limit=limit)
        )
        return [
            e
            for e in events
            if e.event_type in (AuditEventType.LOGIN, AuditEventType.LOGOUT, AuditEventType.LOGIN_FAILED)
        ]

    def get_failed_events(self, limit: int = 100) -> List[AuditEvent]:
        """Get failed events (useful for security monitoring)"""
        return self.get_events(AuditFilter(success_only=False, limit=limit * 2))

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_event_count(
        self,
        event_type: Optional[AuditEventType] = None,
        username: Optional[str] = None,
    ) -> int:
        """Count events matching criteria"""
        with self._lock:
            events = list(self._events)
        count = 0
        for e in events:
            if event_type and e.event_type != event_type:
                continue
            if username and e.username != username:
                continue
            count += 1
        return count

    def get_login_attempts(
        self,
        username: str,
        since: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Get login attempt statistics for a user"""
        with self._lock:
            events = [
                e
                for e in self._events
                if e.username == username
                and e.event_type
                in (AuditEventType.LOGIN, AuditEventType.LOGIN_FAILED)
            ]

        if since:
            events = [e for e in events if e.timestamp >= since]

        success = sum(1 for e in events if e.success)
        failed = sum(1 for e in events if not e.success)
        return {"total": len(events), "success": success, "failed": failed}

    # ------------------------------------------------------------------
    # Subscribers
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[AuditEvent], None]) -> None:
        """Subscribe to audit events"""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AuditEvent], None]) -> None:
        """Unsubscribe from audit events"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _write_event(self, event: AuditEvent) -> None:
        """Write a single event to the audit log file (JSON lines format)"""
        date_str = event.timestamp.strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit-{date_str}.jsonl"
        try:
            event_data = event.model_dump(mode="json")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_data, default=str) + "\n")
        except OSError:
            pass  # Logging must never crash the application

    def flush(self) -> None:
        """Write all in-memory events to disk"""
        with self._lock:
            events = list(self._events)
        for event in events:
            self._write_event(event)

    def clear(self) -> None:
        """Clear all in-memory events (for testing)"""
        with self._lock:
            self._events.clear()
