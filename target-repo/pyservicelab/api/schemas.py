"""Request / response schemas (data-transfer objects).

These plain dataclasses decouple the API surface from the internal domain
models.  They carry no business logic and are easy to serialise to dicts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Generic response wrapper
# ---------------------------------------------------------------------------


@dataclass
class ApiResponse:
    """Standard envelope for all API responses.

    Attributes:
        success: True when the operation succeeded.
        data: Payload on success (dict, list, or scalar).
        error: Human-readable error message on failure.
        meta: Optional metadata (pagination info, counts, etc.).
    """

    success: bool
    data: Any = None
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any = None, **meta: Any) -> "ApiResponse":
        """Construct a successful response."""
        return cls(success=True, data=data, meta=dict(meta))

    @classmethod
    def fail(cls, error: str, **meta: Any) -> "ApiResponse":
        """Construct an error response."""
        return cls(success=False, error=error, meta=dict(meta))

    def to_dict(self) -> dict:
        """Serialize to a plain dict."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "meta": self.meta,
        }


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------


@dataclass
class LoginRequest:
    """Credentials submitted for authentication."""

    username: str
    password: str


@dataclass
class RegisterRequest:
    """Data required to create a new user account."""

    username: str
    email: str
    password: str
    role: str = "member"


@dataclass
class ChangePasswordRequest:
    """Fields needed to change a user's password."""

    user_id: int
    current_password: str
    new_password: str


@dataclass
class TokenResponse:
    """Returned after a successful login."""

    token: str
    user_id: int
    username: str
    role: str
    expires_at: str

    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "expires_at": self.expires_at,
        }


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------


@dataclass
class CreateUserRequest:
    """Fields required to create a user via the service layer."""

    username: str
    email: str
    password: str
    role: str = "member"


@dataclass
class UpdateUserRequest:
    """Fields that may be updated on an existing user."""

    user_id: int
    email: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


@dataclass
class UserResponse:
    """Serialised representation of a user (no password hash)."""

    id: int
    username: str
    email: str
    role: str
    status: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_user(cls, user: Any) -> "UserResponse":
        """Build from a domain User object."""
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
            status=user.status.value,
            created_at=user.created_at.isoformat(),
        )


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------


@dataclass
class CreateProjectRequest:
    """Fields required to create a project."""

    name: str
    description: str
    owner_id: int
    status: str = "draft"
    tags: list[str] = field(default_factory=list)


@dataclass
class UpdateProjectRequest:
    """Fields that may be updated on an existing project."""

    project_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None


@dataclass
class ProjectResponse:
    """Serialised representation of a project."""

    id: int
    name: str
    description: str
    owner_id: int
    status: str
    created_at: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "status": self.status,
            "created_at": self.created_at,
            "tags": self.tags,
        }

    @classmethod
    def from_project(cls, project: Any) -> "ProjectResponse":
        """Build from a domain Project object."""
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            owner_id=project.owner_id,
            status=project.status.value,
            created_at=project.created_at.isoformat(),
            tags=project.get_tags(),
        )


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------


@dataclass
class CreateTaskRequest:
    """Fields required to create a task."""

    project_id: int
    title: str
    description: str
    created_by: int
    priority: str = "medium"
    assignee_id: Optional[int] = None
    estimated_hours: Optional[float] = None


@dataclass
class UpdateTaskRequest:
    """Fields that may be updated on an existing task."""

    task_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[int] = None
    estimated_hours: Optional[float] = None


@dataclass
class TaskResponse:
    """Serialised representation of a task."""

    id: int
    project_id: int
    title: str
    description: str
    status: str
    priority: str
    created_by: int
    created_at: str
    assignee_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "assignee_id": self.assignee_id,
        }

    @classmethod
    def from_task(cls, task: Any) -> "TaskResponse":
        """Build from a domain Task object."""
        return cls(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status.value,
            priority=task.priority.value,
            created_by=task.created_by,
            created_at=task.created_at.isoformat(),
            assignee_id=task.assignee_id,
        )
