"""User service – CRUD operations with validation and audit logging."""
from __future__ import annotations

from typing import Optional

from pyservicelab.auth.hashing import hash_password
from pyservicelab.core.errors import DuplicateError, NotFoundError
from pyservicelab.core.logging import ServiceLogger
from pyservicelab.core.time import utcnow
from pyservicelab.core.validation import validate_email, validate_password, validate_username
from pyservicelab.db.user_repo import UserRepository
from pyservicelab.domain.audit import AuditAction
from pyservicelab.domain.user import User, UserRole, UserStatus
from pyservicelab.services.audit_service import AuditService

_log = ServiceLogger(__name__)


class UserService:
    """Manages user accounts.

    Args:
        user_repo: Repository for user persistence.
        audit_service: Optional service for recording audit events.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._repo = user_repo
        self._audit = audit_service

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "member",
        created_by: Optional[int] = None,
    ) -> User:
        """Create and persist a new user.

        Args:
            username: Desired login handle.
            email: Email address.
            password: Plaintext password (will be hashed).
            role: Role string (defaults to ``"member"``).
            created_by: ID of the admin performing the creation (for audit).

        Returns:
            The newly created :class:`~pyservicelab.domain.user.User`.

        Raises:
            ValidationError: If any field is invalid.
            DuplicateError: If username or email is already taken.
        """
        username = validate_username(username)
        email = validate_email(email)
        validate_password(password)

        if self._repo.username_exists(username):
            raise DuplicateError("username", username)
        if self._repo.email_exists(email):
            raise DuplicateError("email", email)

        try:
            role_enum = UserRole(role)
        except ValueError:
            role_enum = UserRole.MEMBER

        now = utcnow()
        user = User(
            id=None,
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role_enum,
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        created = self._repo.create(user)

        _log.log_operation(
            f"User '{username}' created",
            operation="user.create_user",
            entity_id=created.id,
            user_id=created_by,
        )

        if self._audit:
            self._audit.log_create(
                resource_type="user",
                resource_id=str(created.id),
                details=f"User '{username}' created",
                user_id=created_by,
            )

        return created

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_user(self, user_id: int) -> User:
        """Return the user with *user_id*.

        Raises:
            NotFoundError: If no user exists with that ID.
        """
        user = self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User", user_id)
        return user

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Return the user with *username*, or None if not found."""
        return self._repo.get_by_username(username)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Return the user with *email*, or None if not found."""
        return self._repo.get_by_email(email)

    def list_users(self) -> list[User]:
        """Return all users ordered by creation date."""
        return self._repo.list_all()

    def list_active_users(self) -> list[User]:
        """Return all users in ACTIVE status."""
        return self._repo.list_by_status(UserStatus.ACTIVE)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_email(
        self, user_id: int, new_email: str, actor_id: Optional[int] = None
    ) -> User:
        """Update the email address of *user_id*.

        Raises:
            NotFoundError: If the user does not exist.
            ValidationError: If *new_email* is invalid.
            DuplicateError: If *new_email* is already registered.
        """
        user = self.get_user(user_id)
        new_email = validate_email(new_email)

        if new_email != user.email and self._repo.email_exists(new_email):
            raise DuplicateError("email", new_email)

        user.email = new_email
        user.updated_at = utcnow()
        updated = self._repo.update(user)

        _log.log_operation(
            f"Email updated for user {user_id}",
            operation="user.update_email",
            entity_id=user_id,
            user_id=actor_id,
        )

        if self._audit:
            self._audit.log_update(
                resource_type="user",
                resource_id=str(user_id),
                details=f"Email updated for '{user.username}'",
                user_id=actor_id,
            )

        return updated

    def update_role(
        self, user_id: int, new_role: str, actor_id: Optional[int] = None
    ) -> User:
        """Update the role of *user_id*.

        Raises:
            NotFoundError: If the user does not exist.
            ValueError: If *new_role* is not a valid :class:`UserRole`.
        """
        user = self.get_user(user_id)
        role_enum = UserRole(new_role)
        old_role = user.role.value
        user.role = role_enum
        user.updated_at = utcnow()
        updated = self._repo.update(user)

        _log.log_operation(
            f"Role changed from '{old_role}' to '{new_role}' for user {user_id}",
            operation="user.update_role",
            entity_id=user_id,
            user_id=actor_id,
        )

        if self._audit:
            self._audit.log(
                action=AuditAction.STATUS_CHANGE,
                resource_type="user",
                resource_id=str(user_id),
                details=f"Role changed from '{old_role}' to '{new_role}' for '{user.username}'",
                user_id=actor_id,
            )

        return updated

    def set_status(
        self, user_id: int, status: str, actor_id: Optional[int] = None
    ) -> User:
        """Set the account status of *user_id*.

        Raises:
            NotFoundError: If the user does not exist.
            ValueError: If *status* is not a valid :class:`UserStatus`.
        """
        user = self.get_user(user_id)
        old_status = user.status.value
        user.status = UserStatus(status)
        user.updated_at = utcnow()
        updated = self._repo.update(user)

        _log.log_operation(
            f"Status changed from '{old_status}' to '{status}' for user {user_id}",
            operation="user.set_status",
            entity_id=user_id,
            user_id=actor_id,
        )

        if self._audit:
            self._audit.log(
                action=AuditAction.STATUS_CHANGE,
                resource_type="user",
                resource_id=str(user_id),
                details=f"Status changed from '{old_status}' to '{status}' for '{user.username}'",
                user_id=actor_id,
            )

        return updated

    def deactivate_user(self, user_id: int, actor_id: Optional[int] = None) -> User:
        """Set a user's status to INACTIVE."""
        return self.set_status(user_id, UserStatus.INACTIVE.value, actor_id)

    def activate_user(self, user_id: int, actor_id: Optional[int] = None) -> User:
        """Set a user's status to ACTIVE."""
        return self.set_status(user_id, UserStatus.ACTIVE.value, actor_id)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_user(self, user_id: int, actor_id: Optional[int] = None) -> bool:
        """Permanently delete a user.

        Raises:
            NotFoundError: If the user does not exist.

        Returns:
            True if the user was deleted.
        """
        user = self.get_user(user_id)
        deleted = self._repo.delete_by_id(user_id)

        if deleted:
            _log.log_operation(
                f"User '{user.username}' deleted",
                operation="user.delete_user",
                entity_id=user_id,
                user_id=actor_id,
            )

            if self._audit:
                self._audit.log_delete(
                    resource_type="user",
                    resource_id=str(user_id),
                    details=f"User '{user.username}' deleted",
                    user_id=actor_id,
                )

        return deleted
