"""Database schema migrations for PyServiceLab.

:func:`run_migrations` is idempotent – it is safe to call on every startup.
The ``schema_version`` table tracks which migrations have been applied.
"""
from __future__ import annotations

from pyservicelab.db.sqlite import DatabaseConnection

CURRENT_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# DDL statements
# ---------------------------------------------------------------------------

_CREATE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
)
"""

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'member',
    status          TEXT    NOT NULL DEFAULT 'active',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    last_login      TEXT
)
"""

_CREATE_PROJECTS = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status      TEXT    NOT NULL DEFAULT 'draft',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    due_date    TEXT,
    tags        TEXT    NOT NULL DEFAULT ''
)
"""

_CREATE_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id       INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title            TEXT    NOT NULL,
    description      TEXT    NOT NULL DEFAULT '',
    created_by       INTEGER NOT NULL REFERENCES users(id),
    assignee_id      INTEGER REFERENCES users(id),
    status           TEXT    NOT NULL DEFAULT 'todo',
    priority         TEXT    NOT NULL DEFAULT 'medium',
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL,
    due_date         TEXT,
    estimated_hours  REAL
)
"""

_CREATE_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    user_id       INTEGER,
    action        TEXT    NOT NULL,
    resource_type TEXT    NOT NULL,
    resource_id   TEXT,
    details       TEXT    NOT NULL DEFAULT '',
    ip_address    TEXT,
    success       INTEGER NOT NULL DEFAULT 1
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)",
    "CREATE INDEX IF NOT EXISTS idx_users_email    ON users (email)",
    "CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects (owner_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_project  ON tasks (project_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks (assignee_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_user     ON audit_log (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log (resource_type, resource_id)",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_migrations(db: DatabaseConnection) -> None:
    """Apply any outstanding schema migrations.

    This function is idempotent and safe to call on every application start.
    """
    conn = db.connect()
    conn.execute(_CREATE_SCHEMA_VERSION)
    conn.commit()

    row = db.fetchone("SELECT version FROM schema_version")
    current_version: int = row["version"] if row else 0

    if current_version < 1:
        _apply_v1(db)


def _apply_v1(db: DatabaseConnection) -> None:
    """Apply the initial (v1) schema."""
    conn = db.connect()
    conn.execute(_CREATE_USERS)
    conn.execute(_CREATE_PROJECTS)
    conn.execute(_CREATE_TASKS)
    conn.execute(_CREATE_AUDIT_LOG)

    for index_sql in _INDEXES:
        conn.execute(index_sql)

    # Record schema version
    row = conn.execute("SELECT COUNT(*) AS cnt FROM schema_version").fetchone()
    if row["cnt"] == 0:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (CURRENT_SCHEMA_VERSION,),
        )
    else:
        conn.execute(
            "UPDATE schema_version SET version = ?",
            (CURRENT_SCHEMA_VERSION,),
        )

    conn.commit()


def get_schema_version(db: DatabaseConnection) -> int:
    """Return the current schema version, or 0 if migrations have never run."""
    if not db.table_exists("schema_version"):
        return 0
    row = db.fetchone("SELECT version FROM schema_version")
    return row["version"] if row else 0
