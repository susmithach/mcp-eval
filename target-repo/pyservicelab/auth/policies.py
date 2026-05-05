"""Role-based access control policies.

Policies are pure functions that accept a user role (string) and return a
boolean.  They do not touch the database.
"""
from __future__ import annotations

from pyservicelab.core.errors import AccessDeniedError
from pyservicelab.domain.user import UserRole

# ---------------------------------------------------------------------------
# Role hierarchy helpers
# ---------------------------------------------------------------------------

_ROLE_HIERARCHY: dict[str, int] = {
    UserRole.GUEST.value: 0,
    UserRole.MEMBER.value: 1,
    UserRole.MANAGER.value: 2,
    UserRole.ADMIN.value: 3,
}


def role_level(role: str) -> int:
    """Return the numeric privilege level of *role* (higher = more access)."""
    return _ROLE_HIERARCHY.get(role, -1)


def has_role(user_role: str, required_role: str) -> bool:
    """Return True if *user_role* meets or exceeds *required_role*."""
    return role_level(user_role) >= role_level(required_role)


# ---------------------------------------------------------------------------
# Named policy checks
# ---------------------------------------------------------------------------


def can_create_user(actor_role: str) -> bool:
    """Only admins may create new users via the service layer."""
    return has_role(actor_role, UserRole.ADMIN.value)


def can_delete_user(actor_role: str, target_user_id: int, actor_user_id: int) -> bool:
    """Admins can delete any user; a user cannot delete themselves."""
    if actor_user_id == target_user_id:
        return False
    return has_role(actor_role, UserRole.ADMIN.value)


def can_update_user_role(actor_role: str) -> bool:
    """Only admins may change a user's role."""
    return has_role(actor_role, UserRole.ADMIN.value)


def can_create_project(actor_role: str) -> bool:
    """Members and above may create projects."""
    return has_role(actor_role, UserRole.MEMBER.value)


def can_delete_project(actor_role: str, owner_id: int, actor_id: int) -> bool:
    """Project owners and admins may delete projects."""
    return actor_id == owner_id or has_role(actor_role, UserRole.ADMIN.value)


def can_manage_project(actor_role: str, owner_id: int, actor_id: int) -> bool:
    """Project owners, managers, and admins may manage a project."""
    if actor_id == owner_id:
        return True
    return has_role(actor_role, UserRole.MANAGER.value)


def can_create_task(actor_role: str) -> bool:
    """Members and above may create tasks."""
    return has_role(actor_role, UserRole.MEMBER.value)


def can_delete_task(actor_role: str, creator_id: int, actor_id: int) -> bool:
    """Task creators and admins may delete tasks."""
    return actor_id == creator_id or has_role(actor_role, UserRole.ADMIN.value)


def can_view_audit_log(actor_role: str) -> bool:
    """Only managers and admins may view audit logs."""
    return has_role(actor_role, UserRole.MANAGER.value)


# ---------------------------------------------------------------------------
# Enforcement helpers (raise on denial)
# ---------------------------------------------------------------------------


def require_role(actor_role: str, required_role: str, action: str = "perform this action") -> None:
    """Raise :class:`AccessDeniedError` if *actor_role* < *required_role*.

    Args:
        actor_role: The current user's role.
        required_role: The minimum role needed.
        action: Human-readable description of the attempted action.

    Raises:
        AccessDeniedError: If the check fails.
    """
    if not has_role(actor_role, required_role):
        raise AccessDeniedError(action, f"requires at least '{required_role}' role")


def require_admin(actor_role: str, action: str = "perform this action") -> None:
    """Raise :class:`AccessDeniedError` if the actor is not an admin."""
    require_role(actor_role, UserRole.ADMIN.value, action)
