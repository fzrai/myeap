"""RBAC service tests"""

import pytest
from myeap.core.exceptions import AuthorizationError
from myeap.security.models import (
    Action,
    Permission,
    Resource,
    Role,
    User,
)
from myeap.security.rbac import RBACService, ROLE_PERMISSIONS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rbac():
    return RBACService()


@pytest.fixture
def admin():
    return User(username="admin", role=Role.ADMIN)


@pytest.fixture
def engineer():
    return User(username="engineer", role=Role.ENGINEER)


@pytest.fixture
def operator():
    return User(username="operator", role=Role.OPERATOR)


@pytest.fixture
def viewer():
    return User(username="viewer", role=Role.VIEWER)


# ---------------------------------------------------------------------------
# Default Permission Matrices
# ---------------------------------------------------------------------------

class TestDefaultPermissions:
    def test_admin_has_all_resources(self):
        for resource in Resource:
            for action in Action:
                perm = Permission(resource=resource, action=action)
                assert perm in ROLE_PERMISSIONS[Role.ADMIN], \
                    f"Admin missing {action.value} on {resource.value}"

    def test_admin_permission_count(self):
        total = len(Resource) * len(Action)
        assert len(ROLE_PERMISSIONS[Role.ADMIN]) == total

    def test_engineer_has_recipe_approve(self):
        assert Permission(resource=Resource.RECIPE, action=Action.APPROVE) in ROLE_PERMISSIONS[Role.ENGINEER]

    def test_engineer_has_recipe_export(self):
        assert Permission(resource=Resource.RECIPE, action=Action.EXPORT) in ROLE_PERMISSIONS[Role.ENGINEER]

    def test_operator_has_equipment_execute(self):
        assert Permission(resource=Resource.EQUIPMENT, action=Action.EXECUTE) in ROLE_PERMISSIONS[Role.OPERATOR]

    def test_operator_has_no_recipe_approve(self):
        assert Permission(resource=Resource.RECIPE, action=Action.APPROVE) not in ROLE_PERMISSIONS[Role.OPERATOR]

    def test_viewer_is_read_only(self):
        for perm in ROLE_PERMISSIONS[Role.VIEWER]:
            assert perm.action == Action.READ, \
                f"Viewer has non-READ action: {perm.action.value} on {perm.resource.value}"

    def test_viewer_has_all_resource_reads(self):
        for resource in Resource:
            assert Permission(resource=resource, action=Action.READ) in ROLE_PERMISSIONS[Role.VIEWER]


# ---------------------------------------------------------------------------
# Permission Checks
# ---------------------------------------------------------------------------

class TestCheckPermission:
    def test_admin_can_do_everything(self, rbac, admin):
        for resource in Resource:
            for action in Action:
                assert rbac.check_permission(admin, resource, action), \
                    f"Admin denied {action.value} on {resource.value}"

    def test_engineer_can_read(self, rbac, engineer):
        assert rbac.check_permission(engineer, Resource.RECIPE, Action.READ)

    def test_engineer_can_update_recipe(self, rbac, engineer):
        assert rbac.check_permission(engineer, Resource.RECIPE, Action.UPDATE)

    def test_engineer_cannot_manage_users(self, rbac, engineer):
        assert not rbac.check_permission(engineer, Resource.USER, Action.UPDATE)
        assert not rbac.check_permission(engineer, Resource.USER, Action.CREATE)

    def test_operator_can_read(self, rbac, operator):
        assert rbac.check_permission(operator, Resource.EQUIPMENT, Action.READ)

    def test_operator_cannot_create_recipe(self, rbac, operator):
        assert not rbac.check_permission(operator, Resource.RECIPE, Action.CREATE)

    def test_operator_cannot_approve_recipe(self, rbac, operator):
        assert not rbac.check_permission(operator, Resource.RECIPE, Action.APPROVE)

    def test_viewer_can_only_read(self, rbac, viewer):
        assert rbac.check_permission(viewer, Resource.EQUIPMENT, Action.READ)
        assert rbac.check_permission(viewer, Resource.RECIPE, Action.READ)
        assert rbac.check_permission(viewer, Resource.ALARM, Action.READ)

    def test_viewer_cannot_create(self, rbac, viewer):
        assert not rbac.check_permission(viewer, Resource.EQUIPMENT, Action.CREATE)

    def test_viewer_cannot_update(self, rbac, viewer):
        assert not rbac.check_permission(viewer, Resource.RECIPE, Action.UPDATE)

    def test_viewer_cannot_delete(self, rbac, viewer):
        assert not rbac.check_permission(viewer, Resource.ALARM, Action.DELETE)


# ---------------------------------------------------------------------------
# Permission Queries
# ---------------------------------------------------------------------------

class TestPermissionQueries:
    def test_get_role_permissions_admin(self, rbac):
        perms = rbac.get_role_permissions(Role.ADMIN)
        assert len(perms) == len(Resource) * len(Action)

    def test_get_role_permissions_viewer(self, rbac):
        perms = rbac.get_role_permissions(Role.VIEWER)
        assert len(perms) == len(Resource)  # READ on each resource

    def test_get_role_permissions_unknown_role(self, rbac):
        # Custom role not in map should return empty set
        perms = rbac.get_role_permissions(Role.VIEWER)
        assert isinstance(perms, set)

    def test_get_user_permissions_with_explicit_grant(self, rbac, viewer):
        viewer.permissions = ["recipe:create"]
        perms = rbac.get_user_permissions(viewer)
        perm_set = {(p.resource.value, p.action.value) for p in perms}
        assert ("recipe", "create") in perm_set

    def test_get_user_permissions_excludes_denied(self, rbac, viewer):
        rbac.deny_permission(viewer.username, Resource.EQUIPMENT, Action.READ)
        perms = rbac.get_user_permissions(viewer)
        perm_set = {(p.resource.value, p.action.value) for p in perms}
        assert ("equipment", "read") not in perm_set


# ---------------------------------------------------------------------------
# Multiple Action Checks
# ---------------------------------------------------------------------------

class TestMultipleChecks:
    def test_check_permissions_multiple(self, rbac, engineer):
        results = rbac.check_permissions(
            engineer, Resource.RECIPE, [Action.READ, Action.UPDATE, Action.DELETE]
        )
        assert results[Action.READ] is True
        assert results[Action.UPDATE] is True
        assert results[Action.DELETE] is True

    def test_check_any_permission_true(self, rbac, operator):
        # Operator can READ but not CREATE
        result = rbac.check_any_permission(
            operator, Resource.RECIPE, [Action.CREATE, Action.READ]
        )
        assert result is True

    def test_check_any_permission_false(self, rbac, viewer):
        result = rbac.check_any_permission(
            viewer, Resource.RECIPE, [Action.CREATE, Action.DELETE, Action.APPROVE]
        )
        assert result is False

    def test_check_all_permissions_true(self, rbac, engineer):
        result = rbac.check_all_permissions(
            engineer, Resource.RECIPE, [Action.READ, Action.UPDATE]
        )
        assert result is True

    def test_check_all_permissions_false(self, rbac, operator):
        result = rbac.check_all_permissions(
            operator, Resource.RECIPE, [Action.READ, Action.APPROVE]
        )
        assert result is False


# ---------------------------------------------------------------------------
# Require Permission
# ---------------------------------------------------------------------------

class TestRequirePermission:
    def test_require_permission_passes(self, rbac, admin):
        rbac.require_permission(admin, Resource.RECIPE, Action.CREATE)

    def test_require_permission_raises(self, rbac, viewer):
        with pytest.raises(AuthorizationError):
            rbac.require_permission(viewer, Resource.RECIPE, Action.CREATE)

    def test_require_permission_error_details(self, rbac, viewer):
        with pytest.raises(AuthorizationError) as exc_info:
            rbac.require_permission(viewer, Resource.EQUIPMENT, Action.DELETE)
        assert exc_info.value.details["resource"] == "equipment"
        assert exc_info.value.details["action"] == "delete"


# ---------------------------------------------------------------------------
# Permission Management
# ---------------------------------------------------------------------------

class TestPermissionManagement:
    def test_grant_permission(self, rbac, viewer):
        assert not rbac.check_permission(viewer, Resource.RECIPE, Action.CREATE)
        rbac.grant_permission(viewer, Resource.RECIPE, Action.CREATE)
        assert rbac.check_permission(viewer, Resource.RECIPE, Action.CREATE)

    def test_grant_permission_already_exists(self, rbac, viewer):
        rbac.grant_permission(viewer, Resource.RECIPE, Action.CREATE)
        rbac.grant_permission(viewer, Resource.RECIPE, Action.CREATE)
        assert viewer.permissions.count("recipe:create") == 1

    def test_revoke_permission(self, rbac, viewer):
        rbac.grant_permission(viewer, Resource.RECIPE, Action.CREATE)
        rbac.revoke_permission(viewer, Resource.RECIPE, Action.CREATE)
        assert not rbac.check_permission(viewer, Resource.RECIPE, Action.CREATE)

    def test_revoke_nonexistent_permission(self, rbac, viewer):
        rbac.revoke_permission(viewer, Resource.RECIPE, Action.CREATE)
        assert not rbac.check_permission(viewer, Resource.RECIPE, Action.CREATE)

    def test_deny_permission_overrides_role(self, rbac, engineer):
        assert rbac.check_permission(engineer, Resource.RECIPE, Action.READ)
        rbac.deny_permission(engineer.username, Resource.RECIPE, Action.READ)
        assert not rbac.check_permission(engineer, Resource.RECIPE, Action.READ)

    def test_remove_deny(self, rbac, engineer):
        rbac.deny_permission(engineer.username, Resource.RECIPE, Action.READ)
        assert not rbac.check_permission(engineer, Resource.RECIPE, Action.READ)
        rbac.remove_deny(engineer.username, Resource.RECIPE, Action.READ)
        assert rbac.check_permission(engineer, Resource.RECIPE, Action.READ)

    def test_grant_role_permission(self, rbac):
        rbac.grant_role_permission(Role.VIEWER, Resource.RECIPE, Action.CREATE)
        viewer = User(username="newviewer", role=Role.VIEWER)
        assert rbac.check_permission(viewer, Resource.RECIPE, Action.CREATE)

    def test_revoke_role_permission(self, rbac):
        rbac.revoke_role_permission(Role.ENGINEER, Resource.RECIPE, Action.READ)
        engineer = User(username="eng", role=Role.ENGINEER)
        assert not rbac.check_permission(engineer, Resource.RECIPE, Action.READ)


# ---------------------------------------------------------------------------
# Role Checks
# ---------------------------------------------------------------------------

class TestRoleChecks:
    def test_has_role_true(self, rbac, admin):
        assert rbac.has_role(admin, Role.ADMIN)

    def test_has_role_false(self, rbac, viewer):
        assert not rbac.has_role(viewer, Role.ADMIN)

    def test_has_any_role_true(self, rbac, admin):
        assert rbac.has_any_role(admin, [Role.ADMIN, Role.ENGINEER])

    def test_has_any_role_false(self, rbac, viewer):
        assert not rbac.has_any_role(viewer, [Role.ADMIN, Role.ENGINEER])

    def test_has_admin_access(self, rbac, admin):
        assert rbac.has_admin_access(admin)

    def test_no_admin_access_for_viewer(self, rbac, viewer):
        assert not rbac.has_admin_access(viewer)


# ---------------------------------------------------------------------------
# Access Control Helpers
# ---------------------------------------------------------------------------

class TestAccessControlHelpers:
    def test_admin_can_manage_users(self, rbac, admin):
        assert rbac.can_manage_users(admin)

    def test_viewer_cannot_manage_users(self, rbac, viewer):
        assert not rbac.can_manage_users(viewer)

    def test_engineer_can_edit_recipe(self, rbac, engineer):
        assert rbac.can_edit_recipe(engineer)

    def test_viewer_cannot_edit_recipe(self, rbac, viewer):
        assert not rbac.can_edit_recipe(viewer)

    def test_engineer_can_approve_recipe(self, rbac, engineer):
        assert rbac.can_approve_recipe(engineer)

    def test_operator_cannot_approve_recipe(self, rbac, operator):
        assert not rbac.can_approve_recipe(operator)

    def test_operator_can_run_equipment(self, rbac, operator):
        assert rbac.can_run_equipment(operator)

    def test_viewer_cannot_run_equipment(self, rbac, viewer):
        assert not rbac.can_run_equipment(viewer)

    def test_operator_can_acknowledge_alarm(self, rbac, operator):
        assert rbac.can_acknowledge_alarm(operator)

    def test_viewer_cannot_acknowledge_alarm(self, rbac, viewer):
        assert not rbac.can_acknowledge_alarm(viewer)

    def test_get_allowed_resources_admin(self, rbac, admin):
        resources = rbac.get_allowed_resources(admin)
        assert set(resources) == set(Resource)

    def test_get_allowed_resources_viewer(self, rbac, viewer):
        resources = rbac.get_allowed_resources(viewer)
        assert set(resources) == set(Resource)

    def test_get_accessible_actions(self, rbac, engineer):
        actions = rbac.get_accessible_actions(engineer, Resource.RECIPE)
        assert Action.CREATE in actions
        assert Action.READ in actions
        assert Action.UPDATE in actions
        assert Action.DELETE in actions
        assert Action.APPROVE in actions

    def test_get_permission_matrix(self, rbac, viewer):
        matrix = rbac.get_permission_matrix(viewer)
        assert "recipe" in matrix
        assert "equipment" in matrix
        assert matrix["recipe"]["read"] is True
        assert matrix["recipe"]["create"] is False


# ---------------------------------------------------------------------------
# Deny-specific edge cases
# ---------------------------------------------------------------------------

class TestDenyEdgeCases:
    def test_deny_multiple_times(self, rbac, viewer):
        rbac.deny_permission(viewer.username, Resource.EQUIPMENT, Action.READ)
        rbac.deny_permission(viewer.username, Resource.EQUIPMENT, Action.READ)
        assert not rbac.check_permission(viewer, Resource.EQUIPMENT, Action.READ)

    def test_remove_deny_nonexistent(self, rbac, viewer):
        rbac.remove_deny(viewer.username, Resource.EQUIPMENT, Action.READ)
        assert rbac.check_permission(viewer, Resource.EQUIPMENT, Action.READ)

    def test_deny_with_explicit_grant_still_denied(self, rbac, viewer):
        rbac.grant_permission(viewer, Resource.EQUIPMENT, Action.CREATE)
        rbac.deny_permission(viewer.username, Resource.EQUIPMENT, Action.CREATE)
        assert not rbac.check_permission(viewer, Resource.EQUIPMENT, Action.CREATE)
