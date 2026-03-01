"""Base repository providing common CRUD helpers.

All concrete repositories extend :class:`BaseRepository` and implement
:meth:`_table_name` and :meth:`_row_to_model`.
"""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pyservicelab.db.sqlite import DatabaseConnection

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic base class for SQLite-backed repositories.

    Sub-classes must implement:

    - :meth:`_table_name` – return the SQL table name.
    - :meth:`_row_to_model` – convert a :class:`sqlite3.Row` to a domain model.
    """

    def __init__(self, db: DatabaseConnection) -> None:
        """Initialise with a shared :class:`DatabaseConnection`."""
        self.db = db

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    def _table_name(self) -> str:  # pragma: no cover
        raise NotImplementedError

    def _row_to_model(self, row: Any) -> T:  # pragma: no cover
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Generic queries
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the total number of rows in the table."""
        row = self.db.fetchone(f"SELECT COUNT(*) AS cnt FROM {self._table_name()}")
        return row["cnt"] if row else 0

    def exists(self, record_id: int) -> bool:
        """Return True if a row with *record_id* exists."""
        row = self.db.fetchone(
            f"SELECT id FROM {self._table_name()} WHERE id = ?",
            (record_id,),
        )
        return row is not None

    def delete_by_id(self, record_id: int) -> bool:
        """Delete the row with *record_id*.  Returns True if a row was deleted."""
        cursor = self.db.execute(
            f"DELETE FROM {self._table_name()} WHERE id = ?",
            (record_id,),
        )
        self.db.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Helpers for sub-classes
    # ------------------------------------------------------------------

    def _commit(self) -> None:
        """Commit the current transaction."""
        self.db.commit()

    def _insert_and_get_id(self, sql: str, params: tuple) -> int:
        """Execute an INSERT statement and return the new row id."""
        cursor = self.db.execute(sql, params)
        self._commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("INSERT did not return a lastrowid")
        return row_id

    def _execute_update(self, sql: str, params: tuple) -> int:
        """Execute an UPDATE/DELETE statement; return the number of affected rows."""
        cursor = self.db.execute(sql, params)
        self._commit()
        return cursor.rowcount
