"""Task repository – CRUD operations for the ``tasks`` table."""
from __future__ import annotations

import sqlite3
from typing import Optional

from pyservicelab.core.errors import DatabaseError
from pyservicelab.db.repo_base import BaseRepository
from pyservicelab.db.sqlite import DatabaseConnection
from pyservicelab.domain.task import Task, TaskPriority, TaskStatus


class TaskRepository(BaseRepository[Task]):
    """Data-access object for :class:`~pyservicelab.domain.task.Task`."""

    def __init__(self, db: DatabaseConnection) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # BaseRepository interface
    # ------------------------------------------------------------------

    def _table_name(self) -> str:
        return "tasks"

    def _row_to_model(self, row: sqlite3.Row) -> Task:
        from datetime import datetime

        def _dt(val: Optional[str]) -> Optional[datetime]:
            return datetime.fromisoformat(val) if val else None

        return Task(
            id=row["id"],
            project_id=row["project_id"],
            title=row["title"],
            description=row["description"],
            created_by=row["created_by"],
            assignee_id=row["assignee_id"],
            status=TaskStatus(row["status"]),
            priority=TaskPriority(row["priority"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            due_date=_dt(row["due_date"]),
            estimated_hours=row["estimated_hours"],
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, task: Task) -> Task:
        """Persist a new task and return it with its assigned ``id``."""
        try:
            row_id = self._insert_and_get_id(
                """
                INSERT INTO tasks
                    (project_id, title, description, created_by, assignee_id,
                     status, priority, created_at, updated_at, due_date, estimated_hours)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.project_id,
                    task.title,
                    task.description,
                    task.created_by,
                    task.assignee_id,
                    task.status.value,
                    task.priority.value,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    task.due_date.isoformat() if task.due_date else None,
                    task.estimated_hours,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"Could not create task: {exc}") from exc

        task.id = row_id
        return task

    def update(self, task: Task) -> Task:
        """Persist changes to an existing task."""
        affected = self._execute_update(
            """
            UPDATE tasks
            SET title = ?, description = ?, assignee_id = ?,
                status = ?, priority = ?, updated_at = ?,
                due_date = ?, estimated_hours = ?
            WHERE id = ?
            """,
            (
                task.title,
                task.description,
                task.assignee_id,
                task.status.value,
                task.priority.value,
                task.updated_at.isoformat(),
                task.due_date.isoformat() if task.due_date else None,
                task.estimated_hours,
                task.id,
            ),
        )
        if affected == 0:
            raise DatabaseError(f"Task {task.id} not found during update")
        return task

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_by_id(self, task_id: int) -> Optional[Task]:
        """Return the task with *task_id*, or None."""
        row = self.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return self._row_to_model(row) if row else None

    def list_all(self) -> list[Task]:
        """Return all tasks ordered by creation date."""
        rows = self.db.fetchall("SELECT * FROM tasks ORDER BY created_at ASC")
        return [self._row_to_model(r) for r in rows]

    def list_by_project(self, project_id: int) -> list[Task]:
        """Return all tasks belonging to *project_id*."""
        rows = self.db.fetchall(
            "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        )
        return [self._row_to_model(r) for r in rows]

    def list_by_assignee(self, assignee_id: int) -> list[Task]:
        """Return all tasks assigned to *assignee_id*."""
        rows = self.db.fetchall(
            "SELECT * FROM tasks WHERE assignee_id = ? ORDER BY priority DESC",
            (assignee_id,),
        )
        return [self._row_to_model(r) for r in rows]

    def list_by_status(self, status: TaskStatus) -> list[Task]:
        """Return all tasks with the given *status*."""
        rows = self.db.fetchall(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC",
            (status.value,),
        )
        return [self._row_to_model(r) for r in rows]

    def list_by_priority(self, priority: TaskPriority) -> list[Task]:
        """Return all tasks with the given *priority*."""
        rows = self.db.fetchall(
            "SELECT * FROM tasks WHERE priority = ? ORDER BY created_at ASC",
            (priority.value,),
        )
        return [self._row_to_model(r) for r in rows]

    def count_by_project(self, project_id: int) -> int:
        """Return the number of tasks in *project_id*."""
        row = self.db.fetchone(
            "SELECT COUNT(*) AS cnt FROM tasks WHERE project_id = ?",
            (project_id,),
        )
        return row["cnt"] if row else 0
