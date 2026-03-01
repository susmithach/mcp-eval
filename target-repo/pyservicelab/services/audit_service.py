"""Audit service – records and queries audit log entries."""
from __future__ import annotations

from typing import Optional

from pyservicelab.db.audit_repo import AuditRepository
from pyservicelab.domain.audit import AuditAction, AuditEntry


class AuditService:
    """Business logic layer for the audit log.

    Args:
        audit_repo: The underlying audit-log repository.
        enabled: When False all :meth:`log` calls are no-ops (useful for tests).
    """

    def __init__(self, audit_repo: AuditRepository, enabled: bool = True) -> None:
        self._repo = audit_repo
        self._enabled = enabled

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def log(
        self,
        action: AuditAction,
        resource_type: str,
        details: str,
        resource_id: Optional[str] = None,
        user_id: Optional[int] = None,
        success: bool = True,
        ip_address: Optional[str] = None,
    ) -> Optional[AuditEntry]:
        """Record an audit event.

        Args:
            action: The type of action performed.
            resource_type: Name of the affected entity type (e.g. ``"user"``).
            details: Human-readable event description.
            resource_id: Optional string ID of the affected entity.
            user_id: Optional ID of the acting user (None = system event).
            success: Whether the operation succeeded.
            ip_address: Optional originating IP address.

        Returns:
            The persisted :class:`~pyservicelab.domain.audit.AuditEntry`, or
            None if auditing is disabled.
        """
        if not self._enabled:
            return None

        entry = AuditEntry.make(
            action=action,
            resource_type=resource_type,
            details=details,
            resource_id=resource_id,
            user_id=user_id,
            success=success,
            ip_address=ip_address,
        )
        return self._repo.create(entry)

    def log_create(
        self,
        resource_type: str,
        resource_id: str,
        details: str,
        user_id: Optional[int] = None,
    ) -> Optional[AuditEntry]:
        """Shorthand for logging a CREATE action."""
        return self.log(
            action=AuditAction.CREATE,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            user_id=user_id,
        )

    def log_update(
        self,
        resource_type: str,
        resource_id: str,
        details: str,
        user_id: Optional[int] = None,
    ) -> Optional[AuditEntry]:
        """Shorthand for logging an UPDATE action."""
        return self.log(
            action=AuditAction.UPDATE,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            user_id=user_id,
        )

    def log_delete(
        self,
        resource_type: str,
        resource_id: str,
        details: str,
        user_id: Optional[int] = None,
    ) -> Optional[AuditEntry]:
        """Shorthand for logging a DELETE action."""
        return self.log(
            action=AuditAction.DELETE,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            user_id=user_id,
        )

    def log_auth(
        self,
        action: AuditAction,
        username: str,
        success: bool,
        user_id: Optional[int] = None,
    ) -> Optional[AuditEntry]:
        """Log an authentication-related event."""
        return self.log(
            action=action,
            resource_type="auth",
            resource_id=None,
            details=f"Auth event for '{username}': {action.value}",
            user_id=user_id,
            success=success,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def recent(self, limit: int = 50) -> list[AuditEntry]:
        """Return the most recent *limit* audit entries."""
        return self._repo.list_all(limit=limit)

    def for_user(self, user_id: int, limit: int = 50) -> list[AuditEntry]:
        """Return audit entries for *user_id*."""
        return self._repo.list_by_user(user_id, limit=limit)

    def for_resource(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[AuditEntry]:
        """Return audit entries for a resource type / id combination."""
        return self._repo.list_by_resource(resource_type, resource_id, limit=limit)

    def failures(self, limit: int = 50) -> list[AuditEntry]:
        """Return audit entries for failed operations."""
        return self._repo.list_failures(limit=limit)

    def count(self, action: Optional[AuditAction] = None) -> int:
        """Return total audit entry count, optionally filtered by *action*."""
        if action is not None:
            return self._repo.count_by_action(action)
        return self._repo.count()
