"""Project repository – CRUD operations for the ``projects`` table."""
from __future__ import annotations

import sqlite3
from typing import Optional

from pyservicelab.core.errors import DatabaseError
from pyservicelab.db.repo_base import BaseRepository
from pyservicelab.db.sqlite import DatabaseConnection
from pyservicelab.domain.project import Project, ProjectStatus


class ProjectRepository(BaseRepository[Project]):
    """Data-access object for :class:`~pyservicelab.domain.project.Project`."""

    def __init__(self, db: DatabaseConnection) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # BaseRepository interface
    # ------------------------------------------------------------------

    def _table_name(self) -> str:
        return "projects"

    def _row_to_model(self, row: sqlite3.Row) -> Project:
        from datetime import datetime

        def _dt(val: Optional[str]) -> Optional[datetime]:
            return datetime.fromisoformat(val) if val else None

        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            owner_id=row["owner_id"],
            status=ProjectStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            due_date=_dt(row["due_date"]),
            tags=row["tags"] or "",
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, project: Project) -> Project:
        """Persist a new project and return it with its assigned ``id``."""
        try:
            row_id = self._insert_and_get_id(
                """
                INSERT INTO projects
                    (name, description, owner_id, status, created_at, updated_at, due_date, tags)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.name,
                    project.description,
                    project.owner_id,
                    project.status.value,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                    project.due_date.isoformat() if project.due_date else None,
                    project.tags,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"Could not create project: {exc}") from exc

        project.id = row_id
        return project

    def update(self, project: Project) -> Project:
        """Persist changes to an existing project."""
        affected = self._execute_update(
            """
            UPDATE projects
            SET name = ?, description = ?, status = ?,
                updated_at = ?, due_date = ?, tags = ?
            WHERE id = ?
            """,
            (
                project.name,
                project.description,
                project.status.value,
                project.updated_at.isoformat(),
                project.due_date.isoformat() if project.due_date else None,
                project.tags,
                project.id,
            ),
        )
        if affected == 0:
            raise DatabaseError(f"Project {project.id} not found during update")
        return project

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_by_id(self, project_id: int) -> Optional[Project]:
        """Return the project with *project_id*, or None."""
        row = self.db.fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
        return self._row_to_model(row) if row else None

    def list_all(self) -> list[Project]:
        """Return all projects ordered by creation date."""
        rows = self.db.fetchall("SELECT * FROM projects ORDER BY created_at ASC")
        return [self._row_to_model(r) for r in rows]

    def list_by_owner(self, owner_id: int) -> list[Project]:
        """Return all projects belonging to *owner_id*."""
        rows = self.db.fetchall(
            "SELECT * FROM projects WHERE owner_id = ? ORDER BY created_at ASC",
            (owner_id,),
        )
        return [self._row_to_model(r) for r in rows]

    def list_by_status(self, status: ProjectStatus) -> list[Project]:
        """Return all projects with the given *status*."""
        rows = self.db.fetchall(
            "SELECT * FROM projects WHERE status = ? ORDER BY created_at ASC",
            (status.value,),
        )
        return [self._row_to_model(r) for r in rows]

    def name_exists_for_owner(self, name: str, owner_id: int) -> bool:
        """Return True if *owner_id* already has a project named *name*."""
        row = self.db.fetchone(
            "SELECT id FROM projects WHERE name = ? AND owner_id = ?",
            (name, owner_id),
        )
        return row is not None
