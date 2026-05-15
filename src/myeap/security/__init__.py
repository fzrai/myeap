"""MyEAP Security Module

Provides enterprise-level security functionality including:
- JWT/OAuth2 authentication
- LDAP integration
- Role-based access control (RBAC)
- Audit logging
- Electronic signature (FDA 21 CFR Part 11 compliant)
"""

from myeap.security.auth import AuthService, JWTHandler
from myeap.security.rbac import RBACService, Role, Resource, Action, Permission
from myeap.security.audit import AuditLogger, AuditEvent, AuditEventType
from myeap.security.signature import ElectronicSignature, SignatureRequest, SignatureRecord

__all__ = [
    # Auth
    "AuthService",
    "JWTHandler",
    # RBAC
    "RBACService",
    "Role",
    "Resource",
    "Action",
    "Permission",
    # Audit
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    # Signature
    "ElectronicSignature",
    "SignatureRequest",
    "SignatureRecord",
]
