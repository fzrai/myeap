"""Security models tests"""

import pytest
from datetime import datetime, timezone, timedelta

from myeap.security.models import (
    Role,
    Resource,
    Action,
    AuditEventType,
    SignatureMeaning,
    SignatureStatus,
    Token,
    TokenData,
    UserCredentials,
    User,
    UserCreate,
    UserUpdate,
    PasswordChange,
    Session,
    Permission,
    PermissionSet,
    AuditEvent,
    AuditFilter,
    SignatureRequest,
    SignatureRecord,
    SignatureVerificationResult,
    SignatureHistory,
)


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------

class TestRole:
    """Role enum tests"""

    def test_role_values(self):
        assert Role.ADMIN.value == "admin"
        assert Role.ENGINEER.value == "engineer"
        assert Role.OPERATOR.value == "operator"
        assert Role.VIEWER.value == "viewer"

    def test_role_priority(self):
        assert Role.ADMIN.priority == 1
        assert Role.ENGINEER.priority == 2
        assert Role.OPERATOR.priority == 3
        assert Role.VIEWER.priority == 4

    def test_admin_has_highest_priority(self):
        assert Role.ADMIN.priority < Role.ENGINEER.priority
        assert Role.ENGINEER.priority < Role.VIEWER.priority


# ---------------------------------------------------------------------------
# Resource / Action
# ---------------------------------------------------------------------------

class TestResource:
    def test_resource_values(self):
        assert Resource.EQUIPMENT.value == "equipment"
        assert Resource.RECIPE.value == "recipe"
        assert Resource.ALARM.value == "alarm"
        assert Resource.USER.value == "user"
        assert Resource.SYSTEM.value == "system"
        assert Resource.DATA.value == "data"

    def test_all_resources_defined(self):
        resources = list(Resource)
        assert len(resources) >= 6


class TestAction:
    def test_action_values(self):
        assert Action.CREATE.value == "create"
        assert Action.READ.value == "read"
        assert Action.UPDATE.value == "update"
        assert Action.DELETE.value == "delete"
        assert Action.APPROVE.value == "approve"
        assert Action.SIGN.value == "sign"

    def test_all_actions_defined(self):
        actions = list(Action)
        assert len(actions) >= 7


# ---------------------------------------------------------------------------
# AuditEventType
# ---------------------------------------------------------------------------

class TestAuditEventType:
    def test_event_type_values(self):
        assert AuditEventType.LOGIN.value == "login"
        assert AuditEventType.LOGOUT.value == "logout"
        assert AuditEventType.LOGIN_FAILED.value == "login_failed"
        assert AuditEventType.CREATE.value == "create"
        assert AuditEventType.READ.value == "read"

    def test_all_types_defined(self):
        types = list(AuditEventType)
        assert len(types) >= 15


# ---------------------------------------------------------------------------
# Token / TokenData
# ---------------------------------------------------------------------------

class TestTokenData:
    def test_create_token_data(self):
        td = TokenData.create(username="user1", role="admin")
        assert td.sub == "user1"
        assert td.role == "admin"
        assert td.jti is not None

    def test_create_with_custom_jti(self):
        td = TokenData.create(username="user1", role="engineer", jti="my-jti")
        assert td.jti == "my-jti"

    def test_token_data_defaults(self):
        td = TokenData(sub="user1", role="viewer")
        assert td.exp is None
        assert td.iat is None
        assert td.jti is None


class TestToken:
    def test_create_token(self):
        token = Token(
            access_token="access123",
            refresh_token="refresh456",
            expires_in=1800,
        )
        assert token.access_token == "access123"
        assert token.refresh_token == "refresh456"
        assert token.token_type == "bearer"
        assert token.expires_in == 1800

    def test_token_default_type(self):
        token = Token(access_token="a", refresh_token="b", expires_in=60)
        assert token.token_type == "bearer"


# ---------------------------------------------------------------------------
# UserCredentials
# ---------------------------------------------------------------------------

class TestUserCredentials:
    def test_create_valid_credentials(self):
        creds = UserCredentials(username="testuser", password="mypassword")
        assert creds.username == "testuser"
        assert creds.password == "mypassword"

    def test_username_stripped(self):
        creds = UserCredentials(username="  TestUser  ", password="pass")
        assert creds.username == "testuser"

    def test_empty_username_raises(self):
        with pytest.raises(ValueError):
            UserCredentials(username="   ", password="pass")

    def test_username_min_length(self):
        with pytest.raises(ValueError):
            UserCredentials(username="", password="pass")


# ---------------------------------------------------------------------------
# PasswordChange
# ---------------------------------------------------------------------------

class TestPasswordChange:
    def test_valid_password_change(self):
        pc = PasswordChange(
            old_password="OldPass1!", new_password="NewPass1!"
        )
        assert pc.old_password == "OldPass1!"

    def test_short_password_raises(self):
        with pytest.raises(ValueError):
            PasswordChange(old_password="X", new_password="Abc1!")

    def test_password_no_uppercase_raises(self):
        with pytest.raises(ValueError):
            PasswordChange(old_password="X", new_password="abcdef1!")

    def test_password_no_lowercase_raises(self):
        with pytest.raises(ValueError):
            PasswordChange(old_password="X", new_password="ABCDEF1!")

    def test_password_no_digit_raises(self):
        with pytest.raises(ValueError):
            PasswordChange(old_password="X", new_password="Abcdefg!")

    def test_password_no_special_char_raises(self):
        with pytest.raises(ValueError):
            PasswordChange(old_password="X", new_password="Abcdefg1")

    def test_password_exactly_eight_with_all_chars(self):
        pc = PasswordChange(old_password="X", new_password="Ab1!defg")
        assert len(pc.new_password) == 8


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class TestUser:
    def test_create_user_defaults(self):
        user = User(username="testuser")
        assert user.username == "testuser"
        assert user.role == Role.VIEWER
        assert user.is_active is True
        assert user.is_locked is False
        assert user.failed_login_attempts == 0
        assert user.id is not None
        assert user.created_at is not None

    def test_user_is_authenticated(self):
        user = User(username="testuser")
        assert user.is_authenticated is True

    def test_user_is_authenticated_when_locked(self):
        user = User(username="testuser", is_locked=True)
        assert user.is_authenticated is False

    def test_user_is_authenticated_when_inactive(self):
        user = User(username="testuser", is_active=False)
        assert user.is_authenticated is False

    def test_increment_failed_login(self):
        user = User(username="testuser")
        user.increment_failed_login()
        user.increment_failed_login()
        assert user.failed_login_attempts == 2

    def test_reset_failed_login(self):
        user = User(username="testuser", failed_login_attempts=5)
        user.reset_failed_login()
        assert user.failed_login_attempts == 0

    def test_create_user_with_role(self):
        user = User(username="admin", role=Role.ADMIN)
        assert user.role == Role.ADMIN

    def test_create_user_with_email(self):
        user = User(username="user", email="user@test.com")
        assert user.email == "user@test.com"

    def test_create_user_with_department(self):
        user = User(username="user", department="Engineering")
        assert user.department == "Engineering"

    def test_create_user_with_permissions(self):
        user = User(
            username="user",
            permissions=["recipe:create", "equipment:read"],
        )
        assert "recipe:create" in user.permissions
        assert "equipment:read" in user.permissions


class TestUserCreate:
    def test_create_request(self):
        uc = UserCreate(username="newuser", password="pass123")
        assert uc.username == "newuser"
        assert uc.role == Role.VIEWER

    def test_create_request_with_role(self):
        uc = UserCreate(
            username="newuser", password="pass123", role=Role.ENGINEER
        )
        assert uc.role == Role.ENGINEER


class TestUserUpdate:
    def test_update_request(self):
        uu = UserUpdate(email="new@test.com", full_name="New Name")
        assert uu.email == "new@test.com"
        assert uu.full_name == "New Name"

    def test_update_partial(self):
        uu = UserUpdate()
        assert uu.email is None
        assert uu.role is None


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class TestSession:
    def test_create_session(self):
        session = Session(username="user1", token_jti="jti-123")
        assert session.username == "user1"
        assert session.token_jti == "jti-123"
        assert session.is_active is True
        assert session.session_id is not None

    def test_expire_session(self):
        session = Session(username="user1", token_jti="jti-123")
        assert session.is_active is True
        session.expire()
        assert session.is_active is False

    def test_session_with_metadata(self):
        session = Session(
            username="user1",
            token_jti="jti-123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert session.ip_address == "192.168.1.1"
        assert session.user_agent == "Mozilla/5.0"

    def test_session_expiration(self):
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=1)
        session = Session(
            username="user1", token_jti="jti-123", expires_at=exp
        )
        assert session.expires_at == exp


# ---------------------------------------------------------------------------
# Permission / PermissionSet
# ---------------------------------------------------------------------------

class TestPermission:
    def test_create_permission(self):
        perm = Permission(resource=Resource.RECIPE, action=Action.CREATE)
        assert perm.resource == Resource.RECIPE
        assert perm.action == Action.CREATE
        assert perm.granted is True

    def test_permission_equality(self):
        p1 = Permission(resource=Resource.RECIPE, action=Action.CREATE)
        p2 = Permission(resource=Resource.RECIPE, action=Action.CREATE)
        assert p1 == p2
        assert hash(p1) == hash(p2)

    def test_permission_inequality(self):
        p1 = Permission(resource=Resource.RECIPE, action=Action.CREATE)
        p2 = Permission(resource=Resource.RECIPE, action=Action.DELETE)
        assert p1 != p2

    def test_denied_permission(self):
        perm = Permission(resource=Resource.RECIPE, action=Action.DELETE, granted=False)
        assert perm.granted is False


class TestPermissionSet:
    def test_empty_permission_set(self):
        ps = PermissionSet()
        assert len(ps.permissions) == 0

    def test_add_permission(self):
        ps = PermissionSet()
        ps.add(Resource.RECIPE, Action.READ)
        assert len(ps.permissions) == 1
        assert ps.has(Resource.RECIPE, Action.READ)

    def test_add_duplicate(self):
        ps = PermissionSet()
        ps.add(Resource.RECIPE, Action.READ)
        ps.add(Resource.RECIPE, Action.READ)
        assert len(ps.permissions) == 1

    def test_remove_permission(self):
        ps = PermissionSet()
        ps.add(Resource.RECIPE, Action.READ)
        ps.add(Resource.RECIPE, Action.UPDATE)
        ps.remove(Resource.RECIPE, Action.READ)
        assert not ps.has(Resource.RECIPE, Action.READ)
        assert ps.has(Resource.RECIPE, Action.UPDATE)

    def test_has_nonexistent(self):
        ps = PermissionSet()
        assert not ps.has(Resource.RECIPE, Action.READ)

    def test_has_any(self):
        ps = PermissionSet()
        ps.add(Resource.RECIPE, Action.READ)
        assert ps.has_any(Resource.RECIPE, [Action.READ, Action.CREATE])
        assert not ps.has_any(Resource.RECIPE, [Action.CREATE, Action.DELETE])

    def test_has_all(self):
        ps = PermissionSet()
        ps.add(Resource.RECIPE, Action.READ)
        ps.add(Resource.RECIPE, Action.CREATE)
        assert ps.has_all(Resource.RECIPE, [Action.READ, Action.CREATE])
        assert not ps.has_all(Resource.RECIPE, [Action.READ, Action.DELETE])


# ---------------------------------------------------------------------------
# AuditEvent
# ---------------------------------------------------------------------------

class TestAuditEvent:
    def test_create_audit_event(self):
        event = AuditEvent(event_type=AuditEventType.LOGIN, username="user1")
        assert event.event_type == AuditEventType.LOGIN
        assert event.username == "user1"
        assert event.success is True
        assert event.id is not None
        assert event.timestamp is not None

    def test_create_audit_event_with_details(self):
        event = AuditEvent(
            event_type=AuditEventType.LOGIN_FAILED,
            username="user1",
            success=False,
            error_message="Invalid password",
        )
        assert event.success is False
        assert event.error_message == "Invalid password"

    def test_audit_event_with_state_changes(self):
        before = {"temperature": 100}
        after = {"temperature": 150}
        event = AuditEvent(
            event_type=AuditEventType.UPDATE,
            before_state=before,
            after_state=after,
        )
        assert event.before_state == before
        assert event.after_state == after

    def test_to_log_line(self):
        event = AuditEvent(
            event_type=AuditEventType.LOGIN,
            username="user1",
            success=True,
        )
        line = event.to_log_line()
        assert "type=login" in line
        assert "user=user1" in line
        assert "success=True" in line


# ---------------------------------------------------------------------------
# AuditFilter
# ---------------------------------------------------------------------------

class TestAuditFilter:
    def test_default_filter(self):
        f = AuditFilter()
        assert f.limit == 100

    def test_filter_by_username(self):
        f = AuditFilter(username="user1")
        event = AuditEvent(event_type=AuditEventType.LOGIN, username="user1")
        assert f.matches(event)
        event2 = AuditEvent(event_type=AuditEventType.LOGIN, username="user2")
        assert not f.matches(event2)

    def test_filter_by_event_type(self):
        f = AuditFilter(event_type=AuditEventType.LOGIN)
        event = AuditEvent(event_type=AuditEventType.LOGIN)
        assert f.matches(event)
        event2 = AuditEvent(event_type=AuditEventType.LOGOUT)
        assert not f.matches(event2)

    def test_filter_by_resource(self):
        f = AuditFilter(resource="recipe")
        event = AuditEvent(event_type=AuditEventType.CREATE, resource="recipe")
        assert f.matches(event)
        event2 = AuditEvent(event_type=AuditEventType.CREATE, resource="equipment")
        assert not f.matches(event2)

    def test_filter_by_resource_id(self):
        f = AuditFilter(resource_id="recipe-001")
        event = AuditEvent(event_type=AuditEventType.UPDATE, resource_id="recipe-001")
        assert f.matches(event)
        event2 = AuditEvent(event_type=AuditEventType.UPDATE, resource_id="recipe-002")
        assert not f.matches(event2)

    def test_filter_by_success(self):
        f = AuditFilter(success_only=True)
        event = AuditEvent(event_type=AuditEventType.CREATE, success=True)
        assert f.matches(event)
        event2 = AuditEvent(event_type=AuditEventType.CREATE, success=False)
        assert not f.matches(event2)

    def test_filter_by_time_range(self):
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=2)
        end = now - timedelta(hours=1)
        f = AuditFilter(start_time=start, end_time=end)

        evt_too_early = AuditEvent(
            event_type=AuditEventType.CREATE,
            timestamp=now - timedelta(hours=3),
        )
        assert not f.matches(evt_too_early)

        evt_in_range = AuditEvent(
            event_type=AuditEventType.CREATE,
            timestamp=now - timedelta(hours=1, minutes=30),
        )
        assert f.matches(evt_in_range)

        evt_too_late = AuditEvent(
            event_type=AuditEventType.CREATE,
            timestamp=now,
        )
        assert not f.matches(evt_too_late)


# ---------------------------------------------------------------------------
# SignatureRequest
# ---------------------------------------------------------------------------

class TestSignatureRequest:
    def test_create_signature_request(self):
        sr = SignatureRequest(
            document_type="recipe",
            document_id="recipe-001",
            title="Sign Recipe",
            requested_by="admin",
            signatories=["engineer1"],
        )
        assert sr.status == SignatureStatus.PENDING
        assert len(sr.signatories) == 1
        assert sr.min_signatures == 1
        assert sr.id is not None

    def test_is_expired_false_when_no_expiry(self):
        sr = SignatureRequest(
            document_type="recipe",
            document_id="recipe-001",
            title="Test",
            requested_by="admin",
            signatories=["user1"],
        )
        assert not sr.is_expired

    def test_is_expired_when_expired(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        sr = SignatureRequest(
            document_type="recipe",
            document_id="recipe-001",
            title="Test",
            requested_by="admin",
            signatories=["user1"],
            expires_at=past,
        )
        assert sr.is_expired

    def test_is_complete_when_pending(self):
        sr = SignatureRequest(
            document_type="recipe",
            document_id="recipe-001",
            title="Test",
            requested_by="admin",
            signatories=["user1"],
        )
        assert not sr.is_complete

    def test_is_complete_when_fully_signed(self):
        sr = SignatureRequest(
            document_type="recipe",
            document_id="recipe-001",
            title="Test",
            requested_by="admin",
            signatories=["user1"],
            status=SignatureStatus.FULLY_SIGNED,
        )
        assert sr.is_complete

    def test_min_signatures_default(self):
        sr = SignatureRequest(
            document_type="recipe",
            document_id="recipe-001",
            title="Test",
            requested_by="admin",
            signatories=["user1"],
        )
        assert sr.min_signatures == 1

    def test_request_with_metadata(self):
        sr = SignatureRequest(
            document_type="recipe",
            document_id="recipe-001",
            title="Test",
            requested_by="admin",
            signatories=["user1"],
            metadata={"priority": "high"},
        )
        assert sr.metadata["priority"] == "high"


# ---------------------------------------------------------------------------
# SignatureRecord
# ---------------------------------------------------------------------------

class TestSignatureRecord:
    def test_create_signature_record(self):
        record = SignatureRecord(
            request_id="req-001",
            username="user1",
            full_name="User One",
            meaning="approver",
            signature_hash="abc123",
        )
        assert record.username == "user1"
        assert record.meaning == "approver"
        assert record.verified is True
        assert record.revoked is False
        assert record.method == "password"

    def test_meaning_validation_empty(self):
        with pytest.raises(ValueError):
            SignatureRecord(
                request_id="req-001",
                username="user1",
                meaning="",
                signature_hash="abc123",
            )

    def test_meaning_validation_whitespace(self):
        with pytest.raises(ValueError):
            SignatureRecord(
                request_id="req-001",
                username="user1",
                meaning="   ",
                signature_hash="abc123",
            )

    def test_record_with_comment(self):
        record = SignatureRecord(
            request_id="req-001",
            username="user1",
            meaning="approver",
            signature_hash="abc123",
            comment="Approved after review",
        )
        assert record.comment == "Approved after review"


# ---------------------------------------------------------------------------
# SignatureVerificationResult
# ---------------------------------------------------------------------------

class TestSignatureVerificationResult:
    def test_valid_result(self):
        result = SignatureVerificationResult(
            signature_id="sig-001",
            valid=True,
            request_id="req-001",
            username="user1",
        )
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_invalid_result(self):
        result = SignatureVerificationResult(
            signature_id="sig-001",
            valid=False,
            errors=["Signature revoked"],
        )
        assert not result.is_valid

    def test_result_with_meaning(self):
        result = SignatureVerificationResult(
            signature_id="sig-001",
            valid=True,
            meaning="approver",
        )
        assert result.meaning == "approver"


# ---------------------------------------------------------------------------
# SignatureHistory
# ---------------------------------------------------------------------------

class TestSignatureHistory:
    def test_empty_history(self):
        sh = SignatureHistory(
            document_type="recipe",
            document_id="recipe-001",
        )
        assert sh.latest_request is None
        assert sh.latest_signature is None

    def test_history_with_requests(self):
        now = datetime.now(timezone.utc)
        old_req = SignatureRequest(
            document_type="recipe",
            document_id="recipe-001",
            title="Old",
            requested_by="admin",
            signatories=["user1"],
            created_at=now - timedelta(days=5),
            status=SignatureStatus.FULLY_SIGNED,
        )
        new_req = SignatureRequest(
            document_type="recipe",
            document_id="recipe-001",
            title="New",
            requested_by="admin",
            signatories=["user1"],
            created_at=now,
        )
        sh = SignatureHistory(
            document_type="recipe",
            document_id="recipe-001",
            requests=[old_req, new_req],
        )
        assert sh.latest_request == new_req

    def test_history_with_signatures(self):
        now = datetime.now(timezone.utc)
        old_sig = SignatureRecord(
            request_id="req-001",
            username="user1",
            meaning="author",
            signature_hash="hash1",
            signed_at=now - timedelta(days=3),
        )
        new_sig = SignatureRecord(
            request_id="req-001",
            username="user2",
            meaning="approver",
            signature_hash="hash2",
            signed_at=now,
        )
        sh = SignatureHistory(
            document_type="recipe",
            document_id="recipe-001",
            signatures=[old_sig, new_sig],
        )
        assert sh.latest_signature == new_sig
