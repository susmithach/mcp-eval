"""User repository – CRUD operations for the ``users`` table."""
from __future__ import annotations

import sqlite3
from typing import Optional

from pyservicelab.core.errors import DatabaseError
from pyservicelab.db.repo_base import BaseRepository
from pyservicelab.db.sqlite import DatabaseConnection
from pyservicelab.domain.user import User, UserRole, UserStatus


class UserRepository(BaseRepository[User]):
    """Data-access object for :class:`~pyservicelab.domain.user.User`."""

    def __init__(self, db: DatabaseConnection) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # BaseRepository interface
    # ------------------------------------------------------------------

    def _table_name(self) -> str:
        return "users"

    def _row_to_model(self, row: sqlite3.Row) -> User:
        from datetime import datetime

        def _dt(val: Optional[str]) -> Optional[datetime]:
            return datetime.fromisoformat(val) if val else None

        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            role=UserRole(row["role"]),
            status=UserStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_login=_dt(row["last_login"]),
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, user: User) -> User:
        """Persist a new user and return it with its assigned ``id``."""
        try:
            row_id = self._insert_and_get_id(
                """
                INSERT INTO users
                    (username, email, password_hash, role, status, created_at, updated_at, last_login)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.username,
                    user.email,
                    user.password_hash,
                    user.role.value,
                    user.status.value,
                    user.created_at.isoformat(),
                    user.updated_at.isoformat(),
                    user.last_login.isoformat() if user.last_login else None,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"Could not create user: {exc}") from exc

        user.id = row_id
        return user

    def update(self, user: User) -> User:
        """Persist changes to an existing user."""
        affected = self._execute_update(
            """
            UPDATE users
            SET username = ?, email = ?, password_hash = ?,
                role = ?, status = ?, updated_at = ?, last_login = ?
            WHERE id = ?
            """,
            (
                user.username,
                user.email,
                user.password_hash,
                user.role.value,
                user.status.value,
                user.updated_at.isoformat(),
                user.last_login.isoformat() if user.last_login else None,
                user.id,
            ),
        )
        if affected == 0:
            raise DatabaseError(f"User {user.id} not found during update")
        return user

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Return the user with *user_id*, or None."""
        row = self.db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return self._row_to_model(row) if row else None

    def get_by_username(self, username: str) -> Optional[User]:
        """Return the user with *username*, or None."""
        row = self.db.fetchone("SELECT * FROM users WHERE username = ?", (username,))
        return self._row_to_model(row) if row else None

    def get_by_email(self, email: str) -> Optional[User]:
        """Return the user with *email*, or None."""
        row = self.db.fetchone("SELECT * FROM users WHERE email = ?", (email,))
        return self._row_to_model(row) if row else None

    def list_all(self) -> list[User]:
        """Return all users ordered by creation date."""
        rows = self.db.fetchall("SELECT * FROM users ORDER BY created_at ASC")
        return [self._row_to_model(r) for r in rows]

    def list_by_role(self, role: UserRole) -> list[User]:
        """Return all users with the given role."""
        rows = self.db.fetchall(
            "SELECT * FROM users WHERE role = ? ORDER BY username ASC",
            (role.value,),
        )
        return [self._row_to_model(r) for r in rows]

    def list_by_status(self, status: UserStatus) -> list[User]:
        """Return all users with the given status."""
        rows = self.db.fetchall(
            "SELECT * FROM users WHERE status = ? ORDER BY username ASC",
            (status.value,),
        )
        return [self._row_to_model(r) for r in rows]

    def username_exists(self, username: str) -> bool:
        """Return True if *username* is already taken."""
        row = self.db.fetchone(
            "SELECT id FROM users WHERE username = ?", (username,)
        )
        return row is not None

    def email_exists(self, email: str) -> bool:
        """Return True if *email* is already registered."""
        row = self.db.fetchone("SELECT id FROM users WHERE email = ?", (email,))
        return row is not None
