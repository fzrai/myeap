"""Authentication service tests"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from myeap.core.config import SecuritySettings
from myeap.core.exceptions import AuthenticationError, ConfigurationError
from myeap.security.auth import JWTHandler, AuthService
from myeap.security.models import (
    Role,
    Token,
    TokenData,
    User,
    UserCreate,
    UserCredentials,
    UserUpdate,
    PasswordChange,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_SECRET = "test-secret-key-12345678901234567890"


@pytest.fixture
def settings():
    """Non-default security settings for testing"""
    return SecuritySettings(
        secret_key=TEST_SECRET,
        algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def jwt_handler(settings):
    return JWTHandler(settings)


@pytest.fixture
def auth_service(settings):
    svc = AuthService(settings=settings, jwt_handler=JWTHandler(settings))
    # Create a test user (password verified by hash)
    svc.create_user(
        UserCreate(
            username="testuser",
            password="password123",
            role=Role.VIEWER,
        )
    )
    svc.create_user(
        UserCreate(
            username="admin",
            password="admin123",
            role=Role.ADMIN,
        )
    )
    svc.create_user(
        UserCreate(
            username="engineer1",
            password="eng123",
            role=Role.ENGINEER,
        )
    )
    return svc


@pytest.fixture
def admin_user():
    return User(username="admin", role=Role.ADMIN)


@pytest.fixture
def viewer_user():
    return User(username="testuser", role=Role.VIEWER)


# ---------------------------------------------------------------------------
# JWTHandler
# ---------------------------------------------------------------------------

class TestJWTHandler:
    """JWT token handler tests"""

    def test_create_access_token(self, jwt_handler):
        data = TokenData.create(username="user1", role="admin")
        token = jwt_handler.create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self, jwt_handler):
        data = TokenData.create(username="user1", role="admin")
        token = jwt_handler.create_refresh_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self, jwt_handler):
        data = TokenData.create(username="user1", role="admin")
        token = jwt_handler.create_access_token(data)
        decoded = jwt_handler.decode_token(token)
        assert decoded.sub == "user1"
        assert decoded.role == "admin"
        assert decoded.exp is not None
        assert decoded.iat is not None

    def test_decode_refresh_token(self, jwt_handler):
        data = TokenData.create(username="user2", role="engineer")
        token = jwt_handler.create_refresh_token(data)
        decoded = jwt_handler.decode_token(token)
        assert decoded.sub == "user2"
        assert decoded.role == "engineer"

    def test_decode_invalid_token(self, jwt_handler):
        with pytest.raises(AuthenticationError):
            jwt_handler.decode_token("invalid.token.value")

    def test_decode_token_wrong_secret(self, settings):
        handler1 = JWTHandler(settings)
        settings2 = SecuritySettings(
            secret_key="other-secret-key-12345678901234567890",
        )
        handler2 = JWTHandler(settings2)
        data = TokenData.create(username="user1", role="viewer")
        token = handler1.create_access_token(data)
        with pytest.raises(AuthenticationError):
            handler2.decode_token(token)

    def test_token_not_expired(self, jwt_handler):
        data = TokenData.create(username="user1", role="viewer")
        token = jwt_handler.create_access_token(data)
        assert not jwt_handler.is_token_expired(token)

    def test_get_token_jti(self, jwt_handler):
        data = TokenData.create(username="user1", role="viewer", jti="custom-jti")
        token = jwt_handler.create_access_token(data)
        jti = jwt_handler.get_token_jti(token)
        assert jti == "custom-jti"

    def test_different_tokens_have_different_jti(self, jwt_handler):
        data1 = TokenData.create(username="user1", role="viewer")
        data2 = TokenData.create(username="user2", role="admin")
        token1 = jwt_handler.create_access_token(data1)
        token2 = jwt_handler.create_access_token(data2)
        jti1 = jwt_handler.get_token_jti(token1)
        jti2 = jwt_handler.get_token_jti(token2)
        assert jti1 != jti2

    def test_default_secret_raises_error(self):
        settings = SecuritySettings(secret_key="change-me-in-production")
        with pytest.raises(ConfigurationError):
            JWTHandler(settings)


# ---------------------------------------------------------------------------
# AuthService – User Management
# ---------------------------------------------------------------------------

class TestAuthServiceUserMgmt:
    def test_create_user(self, auth_service):
        user = auth_service.create_user(
            UserCreate(username="newuser", password="pass123", role=Role.OPERATOR)
        )
        assert user.username == "newuser"
        assert user.role == Role.OPERATOR

    def test_create_duplicate_user_raises(self, auth_service):
        with pytest.raises(AuthenticationError):
            auth_service.create_user(
                UserCreate(username="testuser", password="pass")
            )

    def test_get_user(self, auth_service):
        user = auth_service.get_user("testuser")
        assert user is not None
        assert user.username == "testuser"

    def test_get_nonexistent_user(self, auth_service):
        user = auth_service.get_user("nonexistent")
        assert user is None

    def test_list_users(self, auth_service):
        users = auth_service.list_users()
        assert len(users) >= 3

    def test_update_user(self, auth_service):
        update = UserUpdate(full_name="New Name", email="new@test.com")
        user = auth_service.update_user("testuser", update)
        assert user.full_name == "New Name"
        assert user.email == "new@test.com"
        assert user.updated_at is not None

    def test_update_nonexistent_user_raises(self, auth_service):
        with pytest.raises(AuthenticationError):
            auth_service.update_user("nonexistent", UserUpdate(full_name="X"))

    def test_delete_user(self, auth_service):
        auth_service.create_user(UserCreate(username="delme", password="pass"))
        assert auth_service.get_user("delme") is not None
        result = auth_service.delete_user("delme")
        assert result is True
        assert auth_service.get_user("delme") is None

    def test_delete_nonexistent_user_raises(self, auth_service):
        with pytest.raises(AuthenticationError):
            auth_service.delete_user("nonexistent")


# ---------------------------------------------------------------------------
# AuthService – Authentication
# ---------------------------------------------------------------------------

class TestAuthServiceAuthenticate:
    def test_authenticate_invalid_password(self, auth_service):
        creds = UserCredentials(username="testuser", password="wrongpassword")
        with pytest.raises(AuthenticationError):
            auth_service.authenticate(creds)

    def test_authenticate_invalid_username(self, auth_service):
        creds = UserCredentials(username="nonexistent", password="pass")
        with pytest.raises(AuthenticationError):
            auth_service.authenticate(creds)

    def test_authenticate_inactive_user_raises(self, auth_service):
        auth_service.get_user("testuser").is_active = False
        creds = UserCredentials(username="testuser", password="wrongpass")
        with pytest.raises(AuthenticationError):
            auth_service.authenticate(creds)

    def test_authenticate_locked_user_raises(self, auth_service):
        user = auth_service.get_user("testuser")
        user.is_locked = True
        creds = UserCredentials(username="testuser", password="wrongpass")
        with pytest.raises(AuthenticationError):
            auth_service.authenticate(creds)

    def test_failed_login_increments_attempts(self, auth_service):
        creds = UserCredentials(username="testuser", password="wrongpass")
        try:
            auth_service.authenticate(creds)
        except AuthenticationError:
            pass
        user = auth_service.get_user("testuser")
        assert user.failed_login_attempts >= 1

    def test_account_locks_after_max_attempts(self, auth_service):
        user = auth_service.get_user("testuser")
        for _ in range(AuthService.MAX_FAILED_ATTEMPTS):
            user.increment_failed_login()
        user.is_locked = True
        creds = UserCredentials(username="testuser", password="wrongpass")
        with pytest.raises(AuthenticationError, match="locked"):
            auth_service.authenticate(creds)


# ---------------------------------------------------------------------------
# AuthService – Token Operations
# ---------------------------------------------------------------------------

class TestAuthServiceTokens:
    def test_validate_token(self, auth_service):
        """Validate a valid token"""
        creds = UserCredentials(username="testuser", password="default_pass")
        token = auth_service.authenticate(creds)
        assert isinstance(token, Token)
        assert token.access_token
        assert token.refresh_token
        assert token.expires_in > 0

    def test_validate_token_data(self, auth_service):
        """Validate token returns correct user data"""
        creds = UserCredentials(username="admin", password="default_pass")
        token = auth_service.authenticate(creds)
        token_data = auth_service.validate_token(token.access_token)
        assert token_data.sub == "admin"

    def test_validate_blacklisted_token_raises(self, auth_service):
        creds = UserCredentials(username="testuser", password="default_pass")
        token = auth_service.authenticate(creds)
        auth_service.logout(token.access_token)
        with pytest.raises(AuthenticationError, match="revoked"):
            auth_service.validate_token(token.access_token)

    def test_validate_token_for_inactive_user_raises(self, auth_service):
        creds = UserCredentials(username="testuser", password="default_pass")
        token = auth_service.authenticate(creds)
        auth_service.get_user("testuser").is_active = False
        with pytest.raises(AuthenticationError, match="disabled"):
            auth_service.validate_token(token.access_token)

    def test_validate_token_for_locked_user_raises(self, auth_service):
        creds = UserCredentials(username="testuser", password="default_pass")
        token = auth_service.authenticate(creds)
        auth_service.get_user("testuser").is_locked = True
        with pytest.raises(AuthenticationError, match="locked"):
            auth_service.validate_token(token.access_token)

    def test_refresh_token(self, auth_service):
        creds = UserCredentials(username="testuser", password="default_pass")
        original_token = auth_service.authenticate(creds)
        new_token = auth_service.refresh_token(original_token.refresh_token)
        assert new_token.access_token != original_token.access_token
        assert new_token.refresh_token != original_token.refresh_token

    def test_refresh_token_blacklisted_raises(self, auth_service):
        creds = UserCredentials(username="testuser", password="default_pass")
        token = auth_service.authenticate(creds)
        auth_service.logout(token.refresh_token)
        with pytest.raises(AuthenticationError, match="revoked"):
            auth_service.refresh_token(token.refresh_token)

    def test_refresh_token_blacklists_old_token(self, auth_service):
        creds = UserCredentials(username="testuser", password="default_pass")
        token = auth_service.authenticate(creds)
        old_refresh = token.refresh_token
        auth_service.refresh_token(old_refresh)
        with pytest.raises(AuthenticationError, match="revoked"):
            auth_service.validate_token(old_refresh)


# ---------------------------------------------------------------------------
# AuthService – Logout
# ---------------------------------------------------------------------------

class TestAuthServiceLogout:
    def test_logout(self, auth_service):
        creds = UserCredentials(username="testuser", password="default_pass")
        token = auth_service.authenticate(creds)
        result = auth_service.logout(token.access_token)
        assert result is True

    def test_logout_invalidates_token(self, auth_service):
        creds = UserCredentials(username="testuser", password="default_pass")
        token = auth_service.authenticate(creds)
        auth_service.logout(token.access_token)
        with pytest.raises(AuthenticationError):
            auth_service.validate_token(token.access_token)


# ---------------------------------------------------------------------------
# AuthService – Password Change
# ---------------------------------------------------------------------------

class TestAuthServicePasswordChange:
    def test_change_password_invalid_user(self, auth_service):
        pc = PasswordChange(old_password="old", new_password="NewPass1!")
        with pytest.raises(AuthenticationError):
            auth_service.change_password("nonexistent", pc)


# ---------------------------------------------------------------------------
# AuthService – Sessions
# ---------------------------------------------------------------------------

class TestAuthServiceSessions:
    def test_create_session(self, auth_service):
        session = auth_service.create_session(
            username="testuser", token_jti="jti-123"
        )
        assert session.username == "testuser"
        assert session.token_jti == "jti-123"
        assert session.is_active

    def test_create_session_with_metadata(self, auth_service):
        session = auth_service.create_session(
            username="testuser",
            token_jti="jti-123",
            ip_address="192.168.1.1",
            user_agent="test-agent",
        )
        assert session.ip_address == "192.168.1.1"
        assert session.user_agent == "test-agent"

    def test_list_sessions(self, auth_service):
        auth_service.create_session(username="user1", token_jti="jti-1")
        auth_service.create_session(username="user2", token_jti="jti-2")
        sessions = auth_service.list_sessions()
        assert len(sessions) >= 2

    def test_list_sessions_filtered_by_username(self, auth_service):
        auth_service.create_session(username="user1", token_jti="jti-1")
        auth_service.create_session(username="user2", token_jti="jti-2")
        sessions = auth_service.list_sessions(username="user1")
        assert all(s.username == "user1" for s in sessions)

    def test_revoke_session(self, auth_service):
        session = auth_service.create_session(
            username="testuser", token_jti="jti-123"
        )
        result = auth_service.revoke_session(session.session_id)
        assert result is True
        assert not session.is_active

    def test_revoke_nonexistent_session(self, auth_service):
        result = auth_service.revoke_session("nonexistent-id")
        assert result is False

    def test_cleanup_expired_sessions(self, auth_service):
        session = auth_service.create_session(
            username="testuser", token_jti="jti-123"
        )
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        count = auth_service.cleanup_expired_sessions()
        assert count >= 1


# ---------------------------------------------------------------------------
# AuthService – LDAP
# ---------------------------------------------------------------------------

class TestAuthServiceLDAP:
    def test_ldap_auth_fails_by_default(self, auth_service):
        with pytest.raises(AuthenticationError, match="LDAP"):
            auth_service.authenticate_ldap("ldapuser", "ldappass")

    def test_get_ldap_attributes(self, auth_service):
        attrs = auth_service._get_ldap_attributes("testuser")
        assert attrs["email"] == "testuser@example.com"
        assert attrs["full_name"] == "Testuser"


# ---------------------------------------------------------------------------
# AuthService – User Info
# ---------------------------------------------------------------------------

class TestAuthServiceUserInfo:
    def test_get_current_user(self, auth_service):
        creds = UserCredentials(username="testuser", password="default_pass")
        token = auth_service.authenticate(creds)
        user = auth_service.get_current_user(token.access_token)
        assert user.username == "testuser"
