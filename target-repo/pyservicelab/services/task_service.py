"""Task service – CRUD operations with validation and audit logging."""
from __future__ import annotations

from typing import Optional

from pyservicelab.core.errors import NotFoundError, ValidationError
from pyservicelab.core.logging import ServiceLogger
from pyservicelab.core.time import utcnow
from pyservicelab.core.validation import validate_non_empty, validate_optional_str
from pyservicelab.db.project_repo import ProjectRepository
from pyservicelab.db.task_repo import TaskRepository
from pyservicelab.db.user_repo import UserRepository
from pyservicelab.domain.task import Task, TaskPriority, TaskStatus
from pyservicelab.services.audit_service import AuditService

_log = ServiceLogger(__name__)


class TaskService:
    """Manages tasks within projects.

    Args:
        task_repo: Repository for task persistence.
        project_repo: Repository used to verify project existence.
        user_repo: Repository used to verify assignee existence.
        audit_service: Optional service for recording audit events.
    """

    def __init__(
        self,
        task_repo: TaskRepository,
        project_repo: ProjectRepository,
        user_repo: UserRepository,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._repo = task_repo
        self._project_repo = project_repo
        self._user_repo = user_repo
        self._audit = audit_service

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_task(
        self,
        project_id: int,
        title: str,
        description: str,
        created_by: int,
        priority: str = "medium",
        assignee_id: Optional[int] = None,
        estimated_hours: Optional[float] = None,
    ) -> Task:
        """Create and persist a new task.

        Args:
            project_id: ID of the parent project.
            title: Short task title.
            description: Detailed description.
            created_by: ID of the creating user.
            priority: Priority string (defaults to ``"medium"``).
            assignee_id: Optional ID of the assigned user.
            estimated_hours: Optional effort estimate in hours.

        Returns:
            The newly created :class:`~pyservicelab.domain.task.Task`.

        Raises:
            NotFoundError: If *project_id* or *assignee_id* are unknown.
            ValidationError: If any field is invalid.
        """
        title = validate_non_empty(title, "title", max_length=300)
        description = validate_optional_str(description, "description") or ""

        if self._project_repo.get_by_id(project_id) is None:
            raise NotFoundError("Project", project_id)

        if assignee_id is not None and self._user_repo.get_by_id(assignee_id) is None:
            raise NotFoundError("User (assignee)", assignee_id)

        try:
            priority_enum = TaskPriority(priority)
        except ValueError:
            priority_enum = TaskPriority.MEDIUM

        now = utcnow()
        task = Task(
            id=None,
            project_id=project_id,
            title=title,
            description=description,
            created_by=created_by,
            assignee_id=assignee_id,
            status=TaskStatus.TODO,
            priority=priority_enum,
            created_at=now,
            updated_at=now,
            estimated_hours=estimated_hours,
        )
        created = self._repo.create(task)

        _log.log_operation(
            f"Task '{title}' created in project {project_id}",
            operation="task.create_task",
            entity_id=created.id,
            user_id=created_by,
        )

        if self._audit:
            self._audit.log_create(
                resource_type="task",
                resource_id=str(created.id),
                details=f"Task '{title}' created in project {project_id}",
                user_id=created_by,
            )

        return created

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_task(self, task_id: int) -> Task:
        """Return the task with *task_id*.

        Raises:
            NotFoundError: If no task exists with that ID.
        """
        task = self._repo.get_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        return task

    def list_tasks(self) -> list[Task]:
        """Return all tasks ordered by creation date."""
        return self._repo.list_all()

    def list_by_project(self, project_id: int) -> list[Task]:
        """Return all tasks in *project_id*."""
        return self._repo.list_by_project(project_id)

    def list_by_assignee(self, assignee_id: int) -> list[Task]:
        """Return all tasks assigned to *assignee_id*."""
        return self._repo.list_by_assignee(assignee_id)

    def list_by_status(self, status: str) -> list[Task]:
        """Return all tasks with *status*."""
        status_enum = TaskStatus(status)
        return self._repo.list_by_status(status_enum)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[int] = None,
        estimated_hours: Optional[float] = None,
        actor_id: Optional[int] = None,
    ) -> Task:
        """Update one or more fields of *task_id*.

        Raises:
            NotFoundError: If the task or new assignee does not exist.
            ValidationError: If any provided value is invalid.
        """
        task = self.get_task(task_id)
        changed: list[str] = []

        if title is not None:
            task.title = validate_non_empty(title, "title", max_length=300)
            changed.append("title")

        if description is not None:
            task.description = validate_optional_str(description, "description") or ""
            changed.append("description")

        if status is not None:
            try:
                task.status = TaskStatus(status)
            except ValueError:
                raise ValidationError("status", f"'{status}' is not a valid task status")
            changed.append("status")

        if priority is not None:
            try:
                task.priority = TaskPriority(priority)
            except ValueError:
                raise ValidationError("priority", f"'{priority}' is not a valid task priority")
            changed.append("priority")

        if assignee_id is not None:
            if self._user_repo.get_by_id(assignee_id) is None:
                raise NotFoundError("User (assignee)", assignee_id)
            task.assignee_id = assignee_id
            changed.append("assignee_id")

        if estimated_hours is not None:
            task.estimated_hours = estimated_hours
            changed.append("estimated_hours")

        task.updated_at = utcnow()
        updated = self._repo.update(task)

        if changed:
            _log.log_operation(
                f"Task {task_id} updated fields: {', '.join(changed)}",
                operation="task.update_task",
                entity_id=task_id,
                user_id=actor_id,
            )

            if self._audit:
                self._audit.log_update(
                    resource_type="task",
                    resource_id=str(task_id),
                    details=f"Task '{task.title}' updated fields: {', '.join(changed)}",
                    user_id=actor_id,
                )

        return updated

    def transition_status(
        self,
        task_id: int,
        new_status: str,
        actor_id: Optional[int] = None,
    ) -> Task:
        """Change the status of *task_id*.

        Raises:
            NotFoundError: If the task does not exist.
            ValidationError: If *new_status* is not a valid :class:`TaskStatus`.
        """
        return self.update_task(task_id, status=new_status, actor_id=actor_id)

    def assign_task(
        self,
        task_id: int,
        assignee_id: int,
        actor_id: Optional[int] = None,
    ) -> Task:
        """Assign *task_id* to *assignee_id*.

        Raises:
            NotFoundError: If the task or user does not exist.
        """
        return self.update_task(task_id, assignee_id=assignee_id, actor_id=actor_id)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_task(self, task_id: int, actor_id: Optional[int] = None) -> bool:
        """Permanently delete *task_id*.

        Raises:
            NotFoundError: If the task does not exist.

        Returns:
            True if the task was deleted.
        """
        task = self.get_task(task_id)
        deleted = self._repo.delete_by_id(task_id)

        if deleted:
            _log.log_operation(
                f"Task '{task.title}' deleted",
                operation="task.delete_task",
                entity_id=task_id,
                user_id=actor_id,
            )

            if self._audit:
                self._audit.log_delete(
                    resource_type="task",
                    resource_id=str(task_id),
                    details=f"Task '{task.title}' deleted",
                    user_id=actor_id,
                )

        return deleted
