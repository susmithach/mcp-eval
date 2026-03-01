"""User domain model."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pyservicelab.core.time import utcnow


class UserRole(str, Enum):
    """Roles available to users in the system."""

    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    GUEST = "guest"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid role strings."""
        return [r.value for r in cls]


class UserStatus(str, Enum):
    """Lifecycle status of a user account."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid status strings."""
        return [s.value for s in cls]


@dataclass
class User:
    """Represents a registered user.

    Attributes:
        id: Database primary key (None before first save).
        username: Unique login handle (3-50 alphanumeric chars).
        email: Unique email address.
        password_hash: PBKDF2 hash of the user's password.
        role: Access level within the system.
        status: Lifecycle state of the account.
        created_at: UTC timestamp of account creation.
        updated_at: UTC timestamp of last modification.
        last_login: UTC timestamp of the most recent successful login.
    """

    id: Optional[int]
    username: str
    email: str
    password_hash: str
    role: UserRole = UserRole.MEMBER
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    last_login: Optional[datetime] = None

    # ------------------------------------------------------------------
    # State checks
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """Return True if the account is in active status."""
        return self.status == UserStatus.ACTIVE

    def is_admin(self) -> bool:
        """Return True if the user holds the ADMIN role."""
        return self.role == UserRole.ADMIN

    def is_manager_or_above(self) -> bool:
        """Return True if the user is a manager or admin."""
        return self.role in (UserRole.ADMIN, UserRole.MANAGER)

    def can_manage_users(self) -> bool:
        """Return True if the user has sufficient privileges to manage other users."""
        return self.is_admin()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def display_name(self) -> str:
        """Return a human-friendly display name."""
        return self.username

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the user to a plain dict (password hash excluded)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
