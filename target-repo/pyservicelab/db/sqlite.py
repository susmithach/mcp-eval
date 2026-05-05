"""SQLite connection management for PyServiceLab.

:class:`DatabaseConnection` wraps a single :class:`sqlite3.Connection` and
provides helpers for executing queries, managing transactions, and row
retrieval.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Generator, Optional


class DatabaseConnection:
    """Manages a single SQLite database connection.

    Attributes:
        db_path: Filesystem path to the SQLite database, or ``:memory:``.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        """Open and return the underlying :class:`sqlite3.Connection`.

        The connection is created lazily on first call and reused thereafter.
        """
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
        return self._connection

    def close(self) -> None:
        """Close the database connection if it is open."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # ------------------------------------------------------------------
    # Transaction management
    # ------------------------------------------------------------------

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that commits on success and rolls back on error."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute *sql* with *params* and return the cursor."""
        return self.connect().execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute *sql* for each parameter tuple in *params_list*."""
        return self.connect().executemany(sql, params_list)

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute *sql* and return all result rows."""
        return self.execute(sql, params).fetchall()

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute *sql* and return the first result row, or None."""
        return self.execute(sql, params).fetchone()

    def commit(self) -> None:
        """Explicitly commit the current transaction."""
        self.connect().commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self.connect().rollback()

    def lastrowid(self, sql: str, params: tuple = ()) -> Optional[int]:
        """Execute *sql* and return the last inserted row id."""
        cursor = self.execute(sql, params)
        self.commit()
        return cursor.lastrowid

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def table_exists(self, table_name: str) -> bool:
        """Return True if *table_name* exists in the database."""
        row = self.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return row is not None

    def row_count(self, table_name: str) -> int:
        """Return the number of rows in *table_name*."""
        row = self.fetchone(f"SELECT COUNT(*) AS cnt FROM {table_name}")
        return row["cnt"] if row else 0
