"""Role-Based Access Control (RBAC)

Fine-grained permission system with role-based and explicit permissions.
Supports the following roles:
  - ADMIN: Full access to all resources
  - ENGINEER: Can manage equipment, recipes, alarms, and processes
  - OPERATOR: Can operate equipment, read recipes, acknowledge alarms
  - VIEWER: Read-only access
"""

from typing import Dict, List, Optional, Set

from myeap.core.exceptions import AuthorizationError
from myeap.security.models import (
    Action,
    Permission,
    PermissionSet,
    Resource,
    Role,
    User,
)


# ---------------------------------------------------------------------------
# Helper to build permission sets
# ---------------------------------------------------------------------------

def _perm(resource: Resource, action: Action) -> Permission:
    return Permission(resource=resource, action=action)


# ---------------------------------------------------------------------------
# Default role permission matrices
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # Full CRUD + approve on all resources
        *(_perm(r, a) for r in Resource for a in Action),
    },
    Role.ENGINEER: {
        # Equipment: full CRUD, approve, execute
        _perm(Resource.EQUIPMENT, Action.CREATE),
        _perm(Resource.EQUIPMENT, Action.READ),
        _perm(Resource.EQUIPMENT, Action.UPDATE),
        _perm(Resource.EQUIPMENT, Action.DELETE),
        _perm(Resource.EQUIPMENT, Action.APPROVE),
        _perm(Resource.EQUIPMENT, Action.EXECUTE),
        # Recipe: full CRUD, approve, import/export
        _perm(Resource.RECIPE, Action.CREATE),
        _perm(Resource.RECIPE, Action.READ),
        _perm(Resource.RECIPE, Action.UPDATE),
        _perm(Resource.RECIPE, Action.DELETE),
        _perm(Resource.RECIPE, Action.APPROVE),
        _perm(Resource.RECIPE, Action.EXPORT),
        _perm(Resource.RECIPE, Action.IMPORT),
        # Alarm: full CRUD, acknowledge
        _perm(Resource.ALARM, Action.CREATE),
        _perm(Resource.ALARM, Action.READ),
        _perm(Resource.ALARM, Action.UPDATE),
        _perm(Resource.ALARM, Action.DELETE),
        _perm(Resource.ALARM, Action.APPROVE),
        # Data: full access
        _perm(Resource.DATA, Action.CREATE),
        _perm(Resource.DATA, Action.READ),
        _perm(Resource.DATA, Action.UPDATE),
        _perm(Resource.DATA, Action.DELETE),
        _perm(Resource.DATA, Action.EXPORT),
        # Process: full access
        _perm(Resource.PROCESS, Action.CREATE),
        _perm(Resource.PROCESS, Action.READ),
        _perm(Resource.PROCESS, Action.UPDATE),
        _perm(Resource.PROCESS, Action.EXECUTE),
        # Report: read and export
        _perm(Resource.REPORT, Action.READ),
        _perm(Resource.REPORT, Action.EXPORT),
        _perm(Resource.REPORT, Action.CREATE),
        # System: read access
        _perm(Resource.SYSTEM, Action.READ),
        # User: read
        _perm(Resource.USER, Action.READ),
    },
    Role.OPERATOR: {
        # Equipment: read, execute
        _perm(Resource.EQUIPMENT, Action.READ),
        _perm(Resource.EQUIPMENT, Action.EXECUTE),
        # Recipe: read only
        _perm(Resource.RECIPE, Action.READ),
        # Alarm: read, acknowledge (= approve)
        _perm(Resource.ALARM, Action.READ),
        _perm(Resource.ALARM, Action.APPROVE),
        # Data: read only
        _perm(Resource.DATA, Action.READ),
        # Process: read, execute
        _perm(Resource.PROCESS, Action.READ),
        _perm(Resource.PROCESS, Action.EXECUTE),
        # Report: read only
        _perm(Resource.REPORT, Action.READ),
        # System: read
        _perm(Resource.SYSTEM, Action.READ),
    },
    Role.VIEWER: {
        # Read-only access to all resources
        _perm(Resource.EQUIPMENT, Action.READ),
        _perm(Resource.RECIPE, Action.READ),
        _perm(Resource.ALARM, Action.READ),
        _perm(Resource.DATA, Action.READ),
        _perm(Resource.PROCESS, Action.READ),
        _perm(Resource.REPORT, Action.READ),
        _perm(Resource.SYSTEM, Action.READ),
        _perm(Resource.USER, Action.READ),
    },
}


class RBACService:
    """Role-Based Access Control service

    Checks permissions against role-based matrices and user-specific grants.
    Supports both allow and deny semantics.
    """

    def __init__(self, permissions: Optional[Dict[Role, Set[Permission]]] = None):
        self._role_permissions: Dict[Role, Set[Permission]] = (
            permissions or self._copy_default_permissions()
        )
        self._denied_permissions: Dict[str, Set[Permission]] = {}

    @staticmethod
    def _copy_default_permissions() -> Dict[Role, Set[Permission]]:
        return {role: set(perms) for role, perms in ROLE_PERMISSIONS.items()}

    # ------------------------------------------------------------------
    # Permission Queries
    # ------------------------------------------------------------------

    def get_role_permissions(self, role: Role) -> Set[Permission]:
        """Get all permissions for a role"""
        return self._role_permissions.get(role, set())

    def get_user_permissions(self, user: User) -> Set[Permission]:
        """Get effective permissions for a user

        Combines role-based permissions with explicit user grants.
        """
        perms = set(self.get_role_permissions(user.role))

        # Apply user-specific explicit permissions
        for perm_str in user.permissions:
            try:
                resource_str, action_str = perm_str.split(":")
                resource = Resource(resource_str)
                action = Action(action_str)
                perms.add(_perm(resource, action))
            except (ValueError, KeyError):
                continue  # Skip invalid permission strings

        # Remove denied permissions
        denied = self._denied_permissions.get(user.username, set())
        perms -= denied

        return perms

    def check_permission(
        self, user: User, resource: Resource, action: Action
    ) -> bool:
        """Check if user has a specific permission

        Args:
            user: User to check
            resource: Target resource
            action: Requested action

        Returns:
            True if permission is granted
        """
        # Check explicit denials first
        denied = self._denied_permissions.get(user.username, set())
        if _perm(resource, action) in denied:
            return False

        # Check explicit user permissions
        perm_key = f"{resource.value}:{action.value}"
        if perm_key in user.permissions:
            return True

        # Check role-based permissions
        role_perms = self.get_role_permissions(user.role)
        return _perm(resource, action) in role_perms

    def check_permissions(
        self, user: User, resource: Resource, actions: List[Action]
    ) -> Dict[Action, bool]:
        """Check multiple actions on a resource"""
        return {action: self.check_permission(user, resource, action) for action in actions}

    def check_any_permission(
        self, user: User, resource: Resource, actions: List[Action]
    ) -> bool:
        """Check if user has any of the specified actions"""
        return any(self.check_permission(user, resource, a) for a in actions)

    def check_all_permissions(
        self, user: User, resource: Resource, actions: List[Action]
    ) -> bool:
        """Check if user has all of the specified actions"""
        return all(self.check_permission(user, resource, a) for a in actions)

    def require_permission(
        self, user: User, resource: Resource, action: Action
    ) -> None:
        """Require a permission, raise if not granted

        Args:
            user: User to check
            resource: Target resource
            action: Requested action

        Raises:
            AuthorizationError: If permission is denied
        """
        if not self.check_permission(user, resource, action):
            raise AuthorizationError(
                f"User {user.username} does not have {action.value} permission "
                f"on {resource.value}",
                code="PERMISSION_DENIED",
                details={
                    "user": user.username,
                    "role": user.role.value,
                    "resource": resource.value,
                    "action": action.value,
                },
            )

    # ------------------------------------------------------------------
    # Permission Management
    # ------------------------------------------------------------------

    def grant_permission(self, user: User, resource: Resource, action: Action) -> None:
        """Grant an explicit permission to a user"""
        perm_key = f"{resource.value}:{action.value}"
        if perm_key not in user.permissions:
            user.permissions.append(perm_key)

    def revoke_permission(
        self, user: User, resource: Resource, action: Action
    ) -> None:
        """Revoke an explicit permission from a user"""
        perm_key = f"{resource.value}:{action.value}"
        if perm_key in user.permissions:
            user.permissions.remove(perm_key)

    def deny_permission(self, username: str, resource: Resource, action: Action) -> None:
        """Explicitly deny a permission (overrides role grants)"""
        if username not in self._denied_permissions:
            self._denied_permissions[username] = set()
        self._denied_permissions[username].add(_perm(resource, action))

    def remove_deny(self, username: str, resource: Resource, action: Action) -> None:
        """Remove an explicit denial"""
        if username in self._denied_permissions:
            self._denied_permissions[username].discard(_perm(resource, action))

    def grant_role_permission(
        self, role: Role, resource: Resource, action: Action
    ) -> None:
        """Grant a permission to an entire role

        This modifies the permission matrix for all users with this role.
        """
        if role not in self._role_permissions:
            self._role_permissions[role] = set()
        self._role_permissions[role].add(_perm(resource, action))

    def revoke_role_permission(
        self, role: Role, resource: Resource, action: Action
    ) -> None:
        """Revoke a permission from a role"""
        if role in self._role_permissions:
            self._role_permissions[role].discard(_perm(resource, action))

    def has_role(self, user: User, role: Role) -> bool:
        """Check if user has a specific role"""
        return user.role == role

    def has_any_role(self, user: User, roles: List[Role]) -> bool:
        """Check if user has any of the specified roles"""
        return user.role in roles

    def has_admin_access(self, user: User) -> bool:
        """Check if user has admin-level access"""
        return user.role == Role.ADMIN

    # ------------------------------------------------------------------
    # Access Control Helpers
    # ------------------------------------------------------------------

    def can_manage_users(self, user: User) -> bool:
        """Check if user can manage other users"""
        return self.check_permission(user, Resource.USER, Action.UPDATE)

    def can_edit_recipe(self, user: User) -> bool:
        """Check if user can edit recipes"""
        return self.check_permission(user, Resource.RECIPE, Action.UPDATE)

    def can_approve_recipe(self, user: User) -> bool:
        """Check if user can approve recipes"""
        return self.check_permission(user, Resource.RECIPE, Action.APPROVE)

    def can_run_equipment(self, user: User) -> bool:
        """Check if user can execute equipment commands"""
        return self.check_permission(user, Resource.EQUIPMENT, Action.EXECUTE)

    def can_acknowledge_alarm(self, user: User) -> bool:
        """Check if user can acknowledge alarms"""
        return self.check_permission(user, Resource.ALARM, Action.APPROVE)

    def can_sign_document(self, user: User) -> bool:
        """Check if user can provide electronic signatures"""
        return self.check_permission(user, Resource.RECIPE, Action.SIGN)

    def get_allowed_resources(self, user: User) -> List[Resource]:
        """Get list of resources the user can read"""
        allowed = []
        for resource in Resource:
            if self.check_permission(user, resource, Action.READ):
                allowed.append(resource)
        return allowed

    def get_accessible_actions(self, user: User, resource: Resource) -> List[Action]:
        """Get all actions user can perform on a resource"""
        return [
            action
            for action in Action
            if self.check_permission(user, resource, action)
        ]

    def get_permission_matrix(self, user: User) -> Dict[str, Dict[str, bool]]:
        """Get full permission matrix for a user"""
        matrix: Dict[str, Dict[str, bool]] = {}
        for resource in Resource:
            matrix[resource.value] = {}
            for action in Action:
                matrix[resource.value][action.value] = self.check_permission(
                    user, resource, action
                )
        return matrix
