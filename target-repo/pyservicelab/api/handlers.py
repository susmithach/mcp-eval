"""API handler functions – orchestrate services and produce ApiResponse objects.

Handlers are the application-layer equivalent of HTTP controllers.  They
translate schema objects into service calls and wrap results in
:class:`~pyservicelab.api.schemas.ApiResponse`.
"""
from __future__ import annotations

from typing import Optional

from pyservicelab.api.schemas import (
    ApiResponse,
    ChangePasswordRequest,
    CreateProjectRequest,
    CreateTaskRequest,
    CreateUserRequest,
    LoginRequest,
    ProjectResponse,
    RegisterRequest,
    TaskResponse,
    UpdateProjectRequest,
    UpdateTaskRequest,
    UpdateUserRequest,
    UserResponse,
)
from pyservicelab.auth.models import Credentials, RegistrationRequest
from pyservicelab.auth.service import AuthService
from pyservicelab.core.errors import PyServiceLabError
from pyservicelab.services.audit_service import AuditService
from pyservicelab.services.project_service import ProjectService
from pyservicelab.services.task_service import TaskService
from pyservicelab.services.user_service import UserService


# ---------------------------------------------------------------------------
# Auth handlers
# ---------------------------------------------------------------------------


def handle_register(request: RegisterRequest, auth_service: AuthService) -> ApiResponse:
    """Register a new user account."""
    try:
        reg = RegistrationRequest(
            username=request.username,
            email=request.email,
            password=request.password,
            role=request.role,
        )
        user = auth_service.register(reg)
        return ApiResponse.ok(data=user.to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_login(request: LoginRequest, auth_service: AuthService) -> ApiResponse:
    """Authenticate a user and return a token."""
    try:
        result = auth_service.login(
            Credentials(username=request.username, password=request.password)
        )
        return ApiResponse.ok(data=result.to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_change_password(
    request: ChangePasswordRequest, auth_service: AuthService
) -> ApiResponse:
    """Change a user's password after verifying the current one."""
    try:
        auth_service.change_password(
            user_id=request.user_id,
            current_password=request.current_password,
            new_password=request.new_password,
        )
        return ApiResponse.ok(data={"message": "Password changed successfully"})
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


# ---------------------------------------------------------------------------
# User handlers
# ---------------------------------------------------------------------------


def handle_create_user(request: CreateUserRequest, user_service: UserService) -> ApiResponse:
    """Create a new user."""
    try:
        user = user_service.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            role=request.role,
        )
        return ApiResponse.ok(data=UserResponse.from_user(user).to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_get_user(user_id: int, user_service: UserService) -> ApiResponse:
    """Retrieve a user by ID."""
    try:
        user = user_service.get_user(user_id)
        return ApiResponse.ok(data=UserResponse.from_user(user).to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_list_users(user_service: UserService) -> ApiResponse:
    """Return all users."""
    try:
        users = user_service.list_users()
        return ApiResponse.ok(
            data=[UserResponse.from_user(u).to_dict() for u in users],
            count=len(users),
        )
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_update_user(request: UpdateUserRequest, user_service: UserService) -> ApiResponse:
    """Update user fields."""
    try:
        user = user_service.get_user(request.user_id)
        if request.email is not None:
            user = user_service.update_email(request.user_id, request.email)
        if request.role is not None:
            user = user_service.update_role(request.user_id, request.role)
        if request.status is not None:
            user = user_service.set_status(request.user_id, request.status)
        return ApiResponse.ok(data=UserResponse.from_user(user).to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_delete_user(user_id: int, user_service: UserService) -> ApiResponse:
    """Delete a user by ID."""
    try:
        deleted = user_service.delete_user(user_id)
        return ApiResponse.ok(data={"deleted": deleted, "user_id": user_id})
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


# ---------------------------------------------------------------------------
# Project handlers
# ---------------------------------------------------------------------------


def handle_create_project(
    request: CreateProjectRequest, project_service: ProjectService
) -> ApiResponse:
    """Create a new project."""
    try:
        project = project_service.create_project(
            name=request.name,
            description=request.description,
            owner_id=request.owner_id,
            status=request.status,
            tags=request.tags,
        )
        return ApiResponse.ok(data=ProjectResponse.from_project(project).to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_get_project(project_id: int, project_service: ProjectService) -> ApiResponse:
    """Retrieve a project by ID."""
    try:
        project = project_service.get_project(project_id)
        return ApiResponse.ok(data=ProjectResponse.from_project(project).to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_list_projects(
    project_service: ProjectService,
    owner_id: Optional[int] = None,
) -> ApiResponse:
    """Return projects, optionally filtered by owner."""
    try:
        if owner_id is not None:
            projects = project_service.list_by_owner(owner_id)
        else:
            projects = project_service.list_projects()
        return ApiResponse.ok(
            data=[ProjectResponse.from_project(p).to_dict() for p in projects],
            count=len(projects),
        )
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_update_project(
    request: UpdateProjectRequest, project_service: ProjectService
) -> ApiResponse:
    """Update project fields."""
    try:
        project = project_service.update_project(
            project_id=request.project_id,
            name=request.name,
            description=request.description,
            status=request.status,
            tags=request.tags,
        )
        return ApiResponse.ok(data=ProjectResponse.from_project(project).to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_delete_project(project_id: int, project_service: ProjectService) -> ApiResponse:
    """Delete a project by ID."""
    try:
        deleted = project_service.delete_project(project_id)
        return ApiResponse.ok(data={"deleted": deleted, "project_id": project_id})
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


# ---------------------------------------------------------------------------
# Task handlers
# ---------------------------------------------------------------------------


def handle_create_task(request: CreateTaskRequest, task_service: TaskService) -> ApiResponse:
    """Create a new task."""
    try:
        task = task_service.create_task(
            project_id=request.project_id,
            title=request.title,
            description=request.description,
            created_by=request.created_by,
            priority=request.priority,
            assignee_id=request.assignee_id,
            estimated_hours=request.estimated_hours,
        )
        return ApiResponse.ok(data=TaskResponse.from_task(task).to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_get_task(task_id: int, task_service: TaskService) -> ApiResponse:
    """Retrieve a task by ID."""
    try:
        task = task_service.get_task(task_id)
        return ApiResponse.ok(data=TaskResponse.from_task(task).to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_list_tasks(
    task_service: TaskService,
    project_id: Optional[int] = None,
) -> ApiResponse:
    """Return tasks, optionally filtered by project."""
    try:
        if project_id is not None:
            tasks = task_service.list_by_project(project_id)
        else:
            tasks = task_service.list_tasks()
        return ApiResponse.ok(
            data=[TaskResponse.from_task(t).to_dict() for t in tasks],
            count=len(tasks),
        )
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_update_task(request: UpdateTaskRequest, task_service: TaskService) -> ApiResponse:
    """Update task fields."""
    try:
        task = task_service.update_task(
            task_id=request.task_id,
            title=request.title,
            description=request.description,
            status=request.status,
            priority=request.priority,
            assignee_id=request.assignee_id,
            estimated_hours=request.estimated_hours,
        )
        return ApiResponse.ok(data=TaskResponse.from_task(task).to_dict())
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


def handle_delete_task(task_id: int, task_service: TaskService) -> ApiResponse:
    """Delete a task by ID."""
    try:
        deleted = task_service.delete_task(task_id)
        return ApiResponse.ok(data={"deleted": deleted, "task_id": task_id})
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))


# ---------------------------------------------------------------------------
# Audit handlers
# ---------------------------------------------------------------------------


def handle_list_audit(
    audit_service: AuditService,
    limit: int = 50,
) -> ApiResponse:
    """Return recent audit log entries."""
    try:
        entries = audit_service.recent(limit=limit)
        return ApiResponse.ok(
            data=[e.to_dict() for e in entries],
            count=len(entries),
        )
    except PyServiceLabError as exc:
        return ApiResponse.fail(str(exc))
