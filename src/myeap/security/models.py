"""Security Data Models

Pydantic models for authentication, authorization, and audit.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """User roles for RBAC"""

    ADMIN = "admin"
    ENGINEER = "engineer"
    OPERATOR = "operator"
    VIEWER = "viewer"

    @property
    def priority(self) -> int:
        """Role priority (lower = higher privilege)"""
        return {Role.ADMIN: 1, Role.ENGINEER: 2, Role.OPERATOR: 3, Role.VIEWER: 4}[self]


class Resource(str, Enum):
    """Securable resources"""

    EQUIPMENT = "equipment"
    RECIPE = "recipe"
    ALARM = "alarm"
    USER = "user"
    SYSTEM = "system"
    DATA = "data"
    PROCESS = "process"
    REPORT = "report"


class Action(str, Enum):
    """Actions that can be performed on resources"""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    EXECUTE = "execute"
    EXPORT = "export"
    IMPORT = "import"
    SIGN = "sign"


class AuditEventType(str, Enum):
    """Types of audit events"""

    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    SIGN = "sign"
    SIGN_REQUEST = "sign_request"
    SIGN_VERIFY = "sign_verify"
    PERMISSION_DENIED = "permission_denied"
    CONFIG_CHANGE = "config_change"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    RECIPE_CHANGE = "recipe_change"
    RECIPE_VERSION = "recipe_version"


class SignatureMeaning(str, Enum):
    """21 CFR Part 11 signature meaning types"""

    AUTHOR = "author"
    REVIEWER = "reviewer"
    APPROVER = "approver"
    VERIFIER = "verifier"


class SignatureStatus(str, Enum):
    """Electronic signature request status"""

    PENDING = "pending"
    PARTIALLY_SIGNED = "partially_signed"
    FULLY_SIGNED = "fully_signed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


# ---------------------------------------------------------------------------
# Auth Models
# ---------------------------------------------------------------------------


class Token(BaseModel):
    """JWT token response"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Expiration time in seconds")


class TokenData(BaseModel):
    """Data encoded in JWT token"""

    sub: str = Field(..., description="Subject (username)")
    role: str = Field(..., description="User role")
    exp: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    iat: Optional[datetime] = Field(default=None, description="Issued at timestamp")
    jti: Optional[str] = Field(default=None, description="JWT ID for revocation")

    @classmethod
    def create(cls, username: str, role: str, jti: Optional[str] = None) -> "TokenData":
        return cls(sub=username, role=role, jti=jti or str(uuid.uuid4()))


class UserCredentials(BaseModel):
    """User login credentials"""

    username: str = Field(..., min_length=1, max_length=128, description="Username")
    password: str = Field(..., min_length=1, description="Password")

    @field_validator("username")
    @classmethod
    def username_must_be_trimmed(cls, v: str) -> str:
        result = v.strip().lower()
        if not result:
            raise ValueError("Username must not be empty")
        return result


class User(BaseModel):
    """User account model"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="User ID")
    username: str = Field(..., description="Username")
    email: Optional[str] = Field(default=None, description="Email address")
    full_name: Optional[str] = Field(default=None, description="Full name")
    role: Role = Field(default=Role.VIEWER, description="User role")
    is_active: bool = Field(default=True, description="Account enabled")
    is_locked: bool = Field(default=False, description="Account locked")
    failed_login_attempts: int = Field(default=0, description="Failed login count")
    last_login: Optional[datetime] = Field(default=None, description="Last login time")
    last_password_change: Optional[datetime] = Field(
        default=None, description="Last password change time"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Creation time"
    )
    updated_at: Optional[datetime] = Field(default=None, description="Last update time")
    permissions: List[str] = Field(
        default_factory=list, description="Explicit permission grants"
    )
    department: Optional[str] = Field(default=None, description="Department")
    employee_id: Optional[str] = Field(default=None, description="Employee ID")

    @property
    def is_authenticated(self) -> bool:
        return self.is_active and not self.is_locked

    def increment_failed_login(self) -> None:
        """Record a failed login attempt"""
        self.failed_login_attempts += 1

    def reset_failed_login(self) -> None:
        """Reset failed login attempts on successful login"""
        self.failed_login_attempts = 0


class UserCreate(UserCredentials):
    """User creation request"""

    email: Optional[str] = Field(default=None, description="Email address")
    full_name: Optional[str] = Field(default=None, description="Full name")
    role: Role = Field(default=Role.VIEWER, description="User role")
    department: Optional[str] = Field(default=None, description="Department")


class UserUpdate(BaseModel):
    """User update request"""

    email: Optional[str] = Field(default=None, description="Email address")
    full_name: Optional[str] = Field(default=None, description="Full name")
    role: Optional[Role] = Field(default=None, description="User role")
    is_active: Optional[bool] = Field(default=None, description="Account enabled")
    department: Optional[str] = Field(default=None, description="Department")


class PasswordChange(BaseModel):
    """Password change request"""

    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain an uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain a lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain a digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError("Password must contain a special character")
        return v


class Session(BaseModel):
    """User session"""

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Session ID"
    )
    username: str = Field(..., description="Username")
    token_jti: str = Field(..., description="JWT token ID")
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Session start"
    )
    expires_at: Optional[datetime] = Field(
        default=None, description="Session expiration"
    )
    is_active: bool = Field(default=True, description="Session active flag")

    def expire(self) -> None:
        self.is_active = False


# ---------------------------------------------------------------------------
# RBAC Models
# ---------------------------------------------------------------------------


class Permission(BaseModel):
    """Permission definition"""

    model_config = {"frozen": True}

    resource: Resource = Field(..., description="Target resource")
    action: Action = Field(..., description="Allowed action")
    granted: bool = Field(default=True, description="Grant/deny flag")

    def __hash__(self) -> int:
        return hash((self.resource, self.action))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Permission):
            return NotImplemented
        return self.resource == other.resource and self.action == other.action


class PermissionSet(BaseModel):
    """Set of permissions for a role or user"""

    permissions: List[Permission] = Field(
        default_factory=list, description="Permission list"
    )

    def add(self, resource: Resource, action: Action) -> None:
        perm = Permission(resource=resource, action=action)
        if perm not in self.permissions:
            self.permissions.append(perm)

    def remove(self, resource: Resource, action: Action) -> None:
        self.permissions = [p for p in self.permissions if p.resource != resource or p.action != action]

    def has(self, resource: Resource, action: Action) -> bool:
        return any(p.resource == resource and p.action == action and p.granted for p in self.permissions)

    def has_any(self, resource: Resource, actions: List[Action]) -> bool:
        return any(self.has(resource, a) for a in actions)

    def has_all(self, resource: Resource, actions: List[Action]) -> bool:
        return all(self.has(resource, a) for a in actions)


# ---------------------------------------------------------------------------
# Audit Models
# ---------------------------------------------------------------------------


class AuditEvent(BaseModel):
    """Audit event record"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Event ID")
    event_type: AuditEventType = Field(..., description="Event type")
    username: Optional[str] = Field(default=None, description="Actor username")
    resource: Optional[str] = Field(default=None, description="Target resource type")
    resource_id: Optional[str] = Field(default=None, description="Target resource ID")
    action: Optional[str] = Field(default=None, description="Action performed")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Event details"
    )
    ip_address: Optional[str] = Field(default=None, description="Client IP")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Event time"
    )
    success: bool = Field(default=True, description="Operation success")
    error_message: Optional[str] = Field(default=None, description="Error if failed")
    before_state: Optional[Dict[str, Any]] = Field(
        default=None, description="State before change"
    )
    after_state: Optional[Dict[str, Any]] = Field(
        default=None, description="State after change"
    )

    def to_log_line(self) -> str:
        """Format as log line"""
        parts = [
            f"ts={self.timestamp.isoformat()}",
            f"type={self.event_type.value}",
        ]
        if self.username:
            parts.append(f"user={self.username}")
        if self.resource:
            parts.append(f"resource={self.resource}")
        if self.resource_id:
            parts.append(f"resource_id={self.resource_id}")
        if self.action:
            parts.append(f"action={self.action}")
        parts.append(f"success={self.success}")
        return " ".join(parts)


class AuditFilter(BaseModel):
    """Filter for audit log queries"""

    username: Optional[str] = Field(default=None, description="Filter by username")
    event_type: Optional[AuditEventType] = Field(default=None, description="Filter by event type")
    resource: Optional[str] = Field(default=None, description="Filter by resource type")
    resource_id: Optional[str] = Field(default=None, description="Filter by resource ID")
    start_time: Optional[datetime] = Field(default=None, description="Filter from time")
    end_time: Optional[datetime] = Field(default=None, description="Filter to time")
    success_only: Optional[bool] = Field(default=None, description="Only successful events")
    limit: int = Field(default=100, ge=1, le=10000, description="Max results")

    def matches(self, event: AuditEvent) -> bool:
        if self.username and event.username != self.username:
            return False
        if self.event_type and event.event_type != self.event_type:
            return False
        if self.resource and event.resource != self.resource:
            return False
        if self.resource_id and event.resource_id != self.resource_id:
            return False
        if self.start_time and event.timestamp < self.start_time:
            return False
        if self.end_time and event.timestamp > self.end_time:
            return False
        if self.success_only is not None and event.success != self.success_only:
            return False
        return True


# ---------------------------------------------------------------------------
# Digital Signature Models (21 CFR Part 11)
# ---------------------------------------------------------------------------


class SignatureRequest(BaseModel):
    """Electronic signature request (21 CFR Part 11)"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Request ID")
    document_type: str = Field(..., description="Document type being signed")
    document_id: str = Field(..., description="Document ID being signed")
    document_version: Optional[str] = Field(default=None, description="Document version")
    title: str = Field(..., description="Signing request title")
    description: Optional[str] = Field(default=None, description="Signing description")
    requested_by: str = Field(..., description="Requestor username")
    signatories: List[str] = Field(
        ..., min_length=1, description="Required signatory usernames"
    )
    min_signatures: int = Field(default=1, ge=1, description="Minimum signatures needed")
    status: SignatureStatus = Field(
        default=SignatureStatus.PENDING, description="Request status"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Creation time"
    )
    expires_at: Optional[datetime] = Field(default=None, description="Expiration time")
    completed_at: Optional[datetime] = Field(default=None, description="Completion time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_complete(self) -> bool:
        return self.status in (
            SignatureStatus.FULLY_SIGNED,
            SignatureStatus.REJECTED,
            SignatureStatus.EXPIRED,
            SignatureStatus.REVOKED,
        )


class SignatureRecord(BaseModel):
    """Individual signature record (21 CFR Part 11)"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Record ID")
    request_id: str = Field(..., description="Parent signature request ID")
    username: str = Field(..., description="Signatory username")
    full_name: Optional[str] = Field(default=None, description="Signatory full name")
    meaning: str = Field(..., description="Signature meaning (21 CFR 11.50)")
    comment: Optional[str] = Field(default=None, description="Signing comment")
    signature_hash: str = Field(..., description="Cryptographic signature hash")
    signed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Signature time"
    )
    method: str = Field(default="password", description="Signature method")
    ip_address: Optional[str] = Field(default=None, description="Signatory IP address")
    verified: bool = Field(default=True, description="Signature verified flag")
    revoked: bool = Field(default=False, description="Signature revoked flag")
    revoked_at: Optional[datetime] = Field(default=None, description="Revocation time")
    revoked_by: Optional[str] = Field(default=None, description="Revoked by username")

    @field_validator("meaning")
    @classmethod
    def validate_meaning(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Signature meaning is required per 21 CFR Part 11")
        return v.strip()


class SignatureVerificationResult(BaseModel):
    """Signature verification result"""

    signature_id: str = Field(..., description="Signature record ID")
    valid: bool = Field(..., description="Whether signature is valid")
    request_id: Optional[str] = Field(default=None, description="Parent request ID")
    username: Optional[str] = Field(default=None, description="Signatory username")
    signed_at: Optional[datetime] = Field(default=None, description="Signature time")
    meaning: Optional[str] = Field(default=None, description="Signature meaning")
    errors: List[str] = Field(default_factory=list, description="Verification errors")

    @property
    def is_valid(self) -> bool:
        return self.valid and len(self.errors) == 0


class SignatureHistory(BaseModel):
    """Complete signature history for a document"""

    document_type: str = Field(..., description="Document type")
    document_id: str = Field(..., description="Document ID")
    requests: List[SignatureRequest] = Field(
        default_factory=list, description="All signature requests"
    )
    signatures: List[SignatureRecord] = Field(
        default_factory=list, description="All signature records"
    )

    @property
    def latest_request(self) -> Optional[SignatureRequest]:
        if not self.requests:
            return None
        return sorted(self.requests, key=lambda r: r.created_at, reverse=True)[0]

    @property
    def latest_signature(self) -> Optional[SignatureRecord]:
        if not self.signatures:
            return None
        return sorted(self.signatures, key=lambda s: s.signed_at, reverse=True)[0]
