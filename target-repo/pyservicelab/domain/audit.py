"""Audit log domain model."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pyservicelab.core.time import utcnow


class AuditAction(str, Enum):
    """Action types recorded in the audit log."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    AUTH_FAILURE = "auth_failure"
    PERMISSION_DENIED = "permission_denied"
    PASSWORD_CHANGE = "password_change"
    STATUS_CHANGE = "status_change"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid action strings."""
        return [a.value for a in cls]


@dataclass
class AuditEntry:
    """An immutable record of a state-changing or security-relevant event.

    Attributes:
        id: Database primary key (None before first save).
        timestamp: UTC datetime when the event occurred.
        user_id: ID of the user who performed the action (None = system).
        action: Type of action performed.
        resource_type: Name of the affected resource type (e.g. ``"user"``).
        resource_id: String ID of the affected resource instance.
        details: Human-readable description of the event.
        ip_address: Optional originating IP address.
        success: Whether the operation succeeded.
    """

    id: Optional[int]
    timestamp: datetime
    user_id: Optional[int]
    action: AuditAction
    resource_type: str
    resource_id: Optional[str]
    details: str
    ip_address: Optional[str] = None
    success: bool = True

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def make(
        cls,
        action: AuditAction,
        resource_type: str,
        details: str,
        resource_id: Optional[str] = None,
        user_id: Optional[int] = None,
        success: bool = True,
        ip_address: Optional[str] = None,
    ) -> "AuditEntry":
        """Convenience constructor with a current UTC timestamp."""
        return cls(
            id=None,
            timestamp=utcnow(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            success=success,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the audit entry to a plain dict."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "success": self.success,
        }
