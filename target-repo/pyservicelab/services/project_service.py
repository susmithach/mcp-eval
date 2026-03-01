"""Project service – CRUD operations with validation and audit logging."""
from __future__ import annotations

from typing import Optional

from pyservicelab.core.errors import NotFoundError, ValidationError
from pyservicelab.core.logging import ServiceLogger
from pyservicelab.core.time import utcnow
from pyservicelab.core.validation import validate_non_empty, validate_optional_str
from pyservicelab.db.project_repo import ProjectRepository
from pyservicelab.db.user_repo import UserRepository
from pyservicelab.domain.project import Project, ProjectStatus
from pyservicelab.services.audit_service import AuditService

_log = ServiceLogger(__name__)


class ProjectService:
    """Manages projects.

    Args:
        project_repo: Repository for project persistence.
        user_repo: Repository used to verify owner existence.
        audit_service: Optional service for recording audit events.
    """

    def __init__(
        self,
        project_repo: ProjectRepository,
        user_repo: UserRepository,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._repo = project_repo
        self._user_repo = user_repo
        self._audit = audit_service

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        description: str,
        owner_id: int,
        status: str = "draft",
        tags: Optional[list[str]] = None,
        actor_id: Optional[int] = None,
    ) -> Project:
        """Create and persist a new project.

        Args:
            name: Project name.
            description: Project description.
            owner_id: ID of the owning user.
            status: Initial status string (defaults to ``"draft"``).
            tags: Optional list of tag strings.
            actor_id: ID of the user performing the action (for audit).

        Returns:
            The newly created :class:`~pyservicelab.domain.project.Project`.

        Raises:
            NotFoundError: If *owner_id* does not refer to a known user.
            ValidationError: If *name* or *description* is invalid.
        """
        name = validate_non_empty(name, "name", max_length=200)
        description = validate_optional_str(description, "description") or ""

        if self._user_repo.get_by_id(owner_id) is None:
            raise NotFoundError("User", owner_id)

        try:
            status_enum = ProjectStatus(status)
        except ValueError:
            status_enum = ProjectStatus.DRAFT

        now = utcnow()
        project = Project(
            id=None,
            name=name,
            description=description,
            owner_id=owner_id,
            status=status_enum,
            created_at=now,
            updated_at=now,
            tags=", ".join(tags) if tags else "",
        )
        created = self._repo.create(project)

        _log.log_operation(
            f"Project '{name}' created",
            operation="project.create_project",
            entity_id=created.id,
            user_id=actor_id or owner_id,
        )

        if self._audit:
            self._audit.log_create(
                resource_type="project",
                resource_id=str(created.id),
                details=f"Project '{name}' created by user {owner_id}",
                user_id=actor_id or owner_id,
            )

        return created

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_project(self, project_id: int) -> Project:
        """Return the project with *project_id*.

        Raises:
            NotFoundError: If no project exists with that ID.
        """
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError("Project", project_id)
        return project

    def list_projects(self) -> list[Project]:
        """Return all projects ordered by creation date."""
        return self._repo.list_all()

    def list_by_owner(self, owner_id: int) -> list[Project]:
        """Return all projects owned by *owner_id*."""
        return self._repo.list_by_owner(owner_id)

    def list_by_status(self, status: str) -> list[Project]:
        """Return all projects with the given *status*.

        Raises:
            ValueError: If *status* is not a valid :class:`ProjectStatus`.
        """
        status_enum = ProjectStatus(status)
        return self._repo.list_by_status(status_enum)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_project(
        self,
        project_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[list[str]] = None,
        actor_id: Optional[int] = None,
    ) -> Project:
        """Update one or more fields of *project_id*.

        Only non-None arguments are applied.

        Raises:
            NotFoundError: If the project does not exist.
            ValidationError: If any provided value is invalid.
        """
        project = self.get_project(project_id)
        changed: list[str] = []

        if name is not None:
            project.name = validate_non_empty(name, "name", max_length=200)
            changed.append("name")

        if description is not None:
            project.description = validate_optional_str(description, "description") or ""
            changed.append("description")

        if status is not None:
            try:
                project.status = ProjectStatus(status)
            except ValueError:
                raise ValidationError("status", f"'{status}' is not a valid project status")
            changed.append("status")

        if tags is not None:
            project.set_tags(tags)
            changed.append("tags")

        project.updated_at = utcnow()
        updated = self._repo.update(project)

        if changed:
            _log.log_operation(
                f"Project {project_id} updated fields: {', '.join(changed)}",
                operation="project.update_project",
                entity_id=project_id,
                user_id=actor_id,
            )

            if self._audit:
                self._audit.log_update(
                    resource_type="project",
                    resource_id=str(project_id),
                    details=f"Project '{project.name}' updated fields: {', '.join(changed)}",
                    user_id=actor_id,
                )

        return updated

    def archive_project(self, project_id: int, actor_id: Optional[int] = None) -> Project:
        """Set project status to ARCHIVED."""
        return self.update_project(project_id, status="archived", actor_id=actor_id)

    def activate_project(self, project_id: int, actor_id: Optional[int] = None) -> Project:
        """Set project status to ACTIVE."""
        return self.update_project(project_id, status="active", actor_id=actor_id)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_project(self, project_id: int, actor_id: Optional[int] = None) -> bool:
        """Permanently delete a project (and its tasks via CASCADE).

        Raises:
            NotFoundError: If the project does not exist.

        Returns:
            True if the project was deleted.
        """
        project = self.get_project(project_id)
        deleted = self._repo.delete_by_id(project_id)

        if deleted:
            _log.log_operation(
                f"Project '{project.name}' deleted",
                operation="project.delete_project",
                entity_id=project_id,
                user_id=actor_id,
            )

            if self._audit:
                self._audit.log_delete(
                    resource_type="project",
                    resource_id=str(project_id),
                    details=f"Project '{project.name}' deleted",
                    user_id=actor_id,
                )

        return deleted
