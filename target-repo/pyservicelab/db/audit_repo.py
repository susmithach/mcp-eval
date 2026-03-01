"""Audit-log repository – write and query operations for ``audit_log``."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional

from pyservicelab.db.repo_base import BaseRepository
from pyservicelab.db.sqlite import DatabaseConnection
from pyservicelab.domain.audit import AuditAction, AuditEntry


class AuditRepository(BaseRepository[AuditEntry]):
    """Data-access object for :class:`~pyservicelab.domain.audit.AuditEntry`."""

    def __init__(self, db: DatabaseConnection) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # BaseRepository interface
    # ------------------------------------------------------------------

    def _table_name(self) -> str:
        return "audit_log"

    def _row_to_model(self, row: sqlite3.Row) -> AuditEntry:
        return AuditEntry(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            user_id=row["user_id"],
            action=AuditAction(row["action"]),
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            details=row["details"],
            ip_address=row["ip_address"],
            success=bool(row["success"]),
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, entry: AuditEntry) -> AuditEntry:
        """Persist a new audit entry and return it with its ``id``."""
        row_id = self._insert_and_get_id(
            """
            INSERT INTO audit_log
                (timestamp, user_id, action, resource_type, resource_id,
                 details, ip_address, success)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.timestamp.isoformat(),
                entry.user_id,
                entry.action.value,
                entry.resource_type,
                entry.resource_id,
                entry.details,
                entry.ip_address,
                int(entry.success),
            ),
        )
        entry.id = row_id
        return entry

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_all(self, limit: int = 100) -> list[AuditEntry]:
        """Return the most recent *limit* audit entries."""
        rows = self.db.fetchall(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_model(r) for r in rows]

    def list_by_user(self, user_id: int, limit: int = 100) -> list[AuditEntry]:
        """Return audit entries for a specific user."""
        rows = self.db.fetchall(
            "SELECT * FROM audit_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        )
        return [self._row_to_model(r) for r in rows]

    def list_by_resource(
        self, resource_type: str, resource_id: Optional[str] = None, limit: int = 100
    ) -> list[AuditEntry]:
        """Return audit entries for a resource type, optionally filtered by id."""
        if resource_id is not None:
            rows = self.db.fetchall(
                """SELECT * FROM audit_log
                   WHERE resource_type = ? AND resource_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (resource_type, resource_id, limit),
            )
        else:
            rows = self.db.fetchall(
                """SELECT * FROM audit_log
                   WHERE resource_type = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (resource_type, limit),
            )
        return [self._row_to_model(r) for r in rows]

    def list_by_action(self, action: AuditAction, limit: int = 100) -> list[AuditEntry]:
        """Return audit entries for a specific action type."""
        rows = self.db.fetchall(
            "SELECT * FROM audit_log WHERE action = ? ORDER BY timestamp DESC LIMIT ?",
            (action.value, limit),
        )
        return [self._row_to_model(r) for r in rows]

    def list_failures(self, limit: int = 100) -> list[AuditEntry]:
        """Return audit entries where the operation failed."""
        rows = self.db.fetchall(
            "SELECT * FROM audit_log WHERE success = 0 ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_model(r) for r in rows]

    def count_by_action(self, action: AuditAction) -> int:
        """Return the total number of entries for a specific action."""
        row = self.db.fetchone(
            "SELECT COUNT(*) AS cnt FROM audit_log WHERE action = ?",
            (action.value,),
        )
        return row["cnt"] if row else 0
