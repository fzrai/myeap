"""Authentication Service

JWT token generation, validation, and LDAP integration.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from jose import JWTError, jwt

from myeap.core.config import SecuritySettings, get_settings
from myeap.core.exceptions import AuthenticationError, ConfigurationError
from myeap.security.models import (
    PasswordChange,
    Role,
    Session,
    Token,
    TokenData,
    User,
    UserCreate,
    UserCredentials,
    UserUpdate,
)


class JWTHandler:
    """JWT token creation and verification"""

    def __init__(self, settings: Optional[SecuritySettings] = None):
        self.settings = settings or get_settings().security
        self._validate_settings()

    def _validate_settings(self) -> None:
        if self.settings.secret_key == "change-me-in-production":
            raise ConfigurationError(
                "Security secret_key must be changed from default value",
                code="INSECURE_CONFIG",
            )

    def create_access_token(self, data: TokenData) -> str:
        """Create a JWT access token"""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.settings.access_token_expire_minutes)
        payload = {
            "sub": data.sub,
            "role": data.role,
            "iat": now,
            "exp": expire,
            "jti": data.jti or str(uuid.uuid4()),
            "type": "access",
        }
        return jwt.encode(payload, self.settings.secret_key, algorithm=self.settings.algorithm)

    def create_refresh_token(self, data: TokenData) -> str:
        """Create a JWT refresh token"""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.settings.refresh_token_expire_days)
        payload = {
            "sub": data.sub,
            "role": data.role,
            "iat": now,
            "exp": expire,
            "jti": data.jti or str(uuid.uuid4()),
            "type": "refresh",
        }
        return jwt.encode(payload, self.settings.secret_key, algorithm=self.settings.algorithm)

    def decode_token(self, token: str) -> TokenData:
        """Decode and validate a JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded TokenData

        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token, self.settings.secret_key, algorithms=[self.settings.algorithm]
            )
            return TokenData(
                sub=payload["sub"],
                role=payload.get("role", "viewer"),
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                jti=payload.get("jti"),
            )
        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {e}") from e

    def is_token_expired(self, token: str) -> bool:
        """Check if a token has expired"""
        try:
            self.decode_token(token)
            return False
        except AuthenticationError:
            return True

    def get_token_jti(self, token: str) -> Optional[str]:
        """Extract JWT ID from token without full validation"""
        try:
            payload = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=[self.settings.algorithm],
                options={"verify_exp": False},
            )
            return payload.get("jti")
        except JWTError:
            return None


class AuthService:
    """Authentication service with JWT and LDAP support

    Handles user authentication, token management, session tracking,
    and LDAP directory integration.
    """

    MAX_FAILED_ATTEMPTS = 5

    def __init__(
        self,
        settings: Optional[SecuritySettings] = None,
        jwt_handler: Optional[JWTHandler] = None,
    ):
        self.settings = settings or get_settings().security
        self.jwt = jwt_handler or JWTHandler(self.settings)
        self._users: Dict[str, User] = {}  # In-memory store (replace with DB)
        self._sessions: Dict[str, Session] = {}  # Active sessions
        self._blacklisted_tokens: set[str] = set()  # Revoked tokens

    # ------------------------------------------------------------------
    # User Management
    # ------------------------------------------------------------------

    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user account"""
        if user_data.username in self._users:
            raise AuthenticationError(
                f"User {user_data.username} already exists", code="USER_EXISTS"
            )

        user = User(
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            department=user_data.department,
            created_at=datetime.now(timezone.utc),
        )

        self._users[user.username] = user
        return user

    def get_user(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self._users.get(username.lower())

    def list_users(self) -> List[User]:
        """List all users"""
        return list(self._users.values())

    def update_user(self, username: str, update: UserUpdate) -> User:
        """Update user information"""
        user = self.get_user(username)
        if not user:
            raise AuthenticationError(f"User {username} not found", code="USER_NOT_FOUND")

        update_data = update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)
        user.updated_at = datetime.now(timezone.utc)
        return user

    def delete_user(self, username: str) -> bool:
        """Delete a user account"""
        if username not in self._users:
            raise AuthenticationError(f"User {username} not found", code="USER_NOT_FOUND")
        del self._users[username]
        # Clean up sessions
        self._sessions = {
            sid: s for sid, s in self._sessions.items() if s.username != username
        }
        return True

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, credentials: UserCredentials) -> Token:
        """Authenticate user with username/password

        Args:
            credentials: Login credentials

        Returns:
            Token with access and refresh tokens

        Raises:
            AuthenticationError: On invalid credentials or locked account
        """
        username = credentials.username.lower()
        user = self.get_user(username)

        if not user:
            raise AuthenticationError(
                "Invalid username or password", code="AUTH_FAILED"
            )

        if not user.is_active:
            raise AuthenticationError("Account is disabled", code="ACCOUNT_DISABLED")

        if user.is_locked:
            raise AuthenticationError(
                "Account is locked due to too many failed attempts",
                code="ACCOUNT_LOCKED",
            )

        # Verify password (in production, use passlib with hashed passwords)
        if not self._verify_password(credentials.password, username):
            user.increment_failed_login()
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.is_locked = True
            raise AuthenticationError(
                "Invalid username or password", code="AUTH_FAILED"
            )

        # Successful login
        user.reset_failed_login()
        user.last_login = datetime.now(timezone.utc)
        return self._generate_tokens(user)

    def authenticate_ldap(self, username: str, password: str) -> Token:
        """Authenticate against LDAP server

        Args:
            username: LDAP username
            password: LDAP password

        Returns:
            Token with access and refresh tokens

        Raises:
            AuthenticationError: On LDAP failure
        """
        ldap_user = self._verify_ldap(username, password)
        if not ldap_user:
            raise AuthenticationError(
                f"LDAP authentication failed for {username}", code="LDAP_AUTH_FAILED"
            )

        # Find or create user
        user = self.get_user(username)
        if user is None:
            ldap_attrs = self._get_ldap_attributes(username)
            user = self.create_user(
                UserCreate(
                    username=username,
                    email=ldap_attrs.get("email"),
                    full_name=ldap_attrs.get("full_name"),
                    role=Role.VIEWER,  # Default role for LDAP users
                    department=ldap_attrs.get("department"),
                )
            )

        if not user.is_active or user.is_locked:
            raise AuthenticationError(
                "Account is disabled or locked", code="ACCOUNT_DISABLED"
            )

        user.reset_failed_login()
        user.last_login = datetime.now(timezone.utc)
        return self._generate_tokens(user)

    def refresh_token(self, refresh_token: str) -> Token:
        """Refresh access token using refresh token

        Args:
            refresh_token: Valid refresh token

        Returns:
            New token pair

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        if refresh_token in self._blacklisted_tokens:
            raise AuthenticationError("Token has been revoked", code="TOKEN_REVOKED")

        token_data = self.jwt.decode_token(refresh_token)
        user = self.get_user(token_data.sub)
        if not user:
            raise AuthenticationError("User not found", code="USER_NOT_FOUND")

        # Blacklist the old refresh token
        self._blacklisted_tokens.add(refresh_token)

        # Remove old session
        old_jti = self.jwt.get_token_jti(refresh_token)
        if old_jti:
            self._sessions = {
                sid: s
                for sid, s in self._sessions.items()
                if s.token_jti != old_jti
            }

        return self._generate_tokens(user)

    def logout(self, access_token: str) -> bool:
        """Logout user by revoking token

        Args:
            access_token: Current access token

        Returns:
            True on success
        """
        jti = self.jwt.get_token_jti(access_token)
        if jti:
            self._blacklisted_tokens.add(access_token)
            # Remove session
            self._sessions = {
                sid: s
                for sid, s in self._sessions.items()
                if s.token_jti != jti
            }
        return True

    def change_password(
        self, username: str, password_change: PasswordChange
    ) -> bool:
        """Change user password

        Args:
            username: Target username
            password_change: Old and new password

        Returns:
            True on success

        Raises:
            AuthenticationError: On wrong old password
        """
        user = self.get_user(username)
        if not user:
            raise AuthenticationError("User not found", code="USER_NOT_FOUND")

        # Verify old password
        if not self._verify_password(password_change.old_password, username):
            raise AuthenticationError(
                "Current password is incorrect", code="INVALID_PASSWORD"
            )

        # Store new password (in production, hash it)
        user.last_password_change = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        return True

    def validate_token(self, token: str) -> TokenData:
        """Validate token and return data

        Args:
            token: JWT token

        Returns:
            TokenData if valid

        Raises:
            AuthenticationError: If token is invalid
        """
        if token in self._blacklisted_tokens:
            raise AuthenticationError("Token has been revoked", code="TOKEN_REVOKED")

        token_data = self.jwt.decode_token(token)

        user = self.get_user(token_data.sub)
        if not user:
            raise AuthenticationError("User not found", code="USER_NOT_FOUND")
        if not user.is_active:
            raise AuthenticationError("Account is disabled", code="ACCOUNT_DISABLED")
        if user.is_locked:
            raise AuthenticationError("Account is locked", code="ACCOUNT_LOCKED")

        return token_data

    def get_current_user(self, token: str) -> User:
        """Get current user from token"""
        token_data = self.validate_token(token)
        return self.get_user(token_data.sub)  # type: ignore

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def create_session(
        self,
        username: str,
        token_jti: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Session:
        """Create a new session record"""
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.settings.access_token_expire_minutes
        )
        session = Session(
            username=username,
            token_jti=token_jti,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        self._sessions[session.session_id] = session
        return session

    def list_sessions(self, username: Optional[str] = None) -> List[Session]:
        """List active sessions, optionally filtered by username"""
        sessions = [
            s for s in self._sessions.values() if s.is_active
        ]
        if username:
            sessions = [s for s in sessions if s.username == username]
        return sessions

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a specific session"""
        session = self._sessions.get(session_id)
        if session and session.is_active:
            session.expire()
            self._blacklisted_tokens.add(session.token_jti)
            return True
        return False

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now(timezone.utc)
        expired = [
            sid
            for sid, s in self._sessions.items()
            if s.expires_at and s.expires_at < now
        ]
        for sid in expired:
            self._blacklisted_tokens.add(self._sessions[sid].token_jti)
            del self._sessions[sid]
        return len(expired)

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _generate_tokens(self, user: User) -> Token:
        """Generate access and refresh token pair"""
        jti = str(uuid.uuid4())
        token_data = TokenData.create(username=user.username, role=user.role.value, jti=jti)

        access_token = self.jwt.create_access_token(token_data)
        refresh_token = self.jwt.create_refresh_token(token_data)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )

    def _verify_password(self, password: str, username: str) -> bool:
        """Verify password (placeholder for passlib/bcrypt)

        In production, compare against stored bcrypt hash.
        This implementation uses a simple hash for testing.
        """
        expected_hash = hashlib.sha256(f"{username}:default_pass".encode()).hexdigest()
        actual_hash = hashlib.sha256(f"{username}:{password}".encode()).hexdigest()
        return actual_hash == expected_hash

    def _verify_ldap(self, username: str, password: str) -> bool:
        """Verify credentials against LDAP

        Placeholder for actual LDAP bind using python-ldap.
        Returns True if LDAP authentication succeeds.
        """
        # In production:
        # import ldap
        # conn = ldap.initialize(self.settings.ldap_server)
        # conn.simple_bind_s(f"uid={username},{self.settings.ldap_base_dn}", password)
        # conn.unbind()
        return False  # LDAP disabled by default

    def _get_ldap_attributes(self, username: str) -> Dict[str, Any]:
        """Get user attributes from LDAP directory"""
        return {
            "email": f"{username}@example.com",
            "full_name": username.title(),
            "department": "Engineering",
        }

