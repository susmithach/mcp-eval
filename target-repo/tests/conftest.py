"""Shared test fixtures for PyServiceLab.

All fixtures use in-memory SQLite databases so tests are isolated and
deterministic.
"""
from __future__ import annotations

import pytest

from pyservicelab.auth.service import AuthService
from pyservicelab.config.loaders import AppConfig
from pyservicelab.db.audit_repo import AuditRepository
from pyservicelab.db.migrations import run_migrations
from pyservicelab.db.project_repo import ProjectRepository
from pyservicelab.db.sqlite import DatabaseConnection
from pyservicelab.db.task_repo import TaskRepository
from pyservicelab.db.user_repo import UserRepository
from pyservicelab.services.audit_service import AuditService
from pyservicelab.services.project_service import ProjectService
from pyservicelab.services.task_service import TaskService
from pyservicelab.services.user_service import UserService


# ---------------------------------------------------------------------------
# Database / repository fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> DatabaseConnection:
    """Fresh in-memory SQLite database with schema applied."""
    conn = DatabaseConnection(":memory:")
    run_migrations(conn)
    return conn


@pytest.fixture()
def user_repo(db: DatabaseConnection) -> UserRepository:
    return UserRepository(db)


@pytest.fixture()
def project_repo(db: DatabaseConnection) -> ProjectRepository:
    return ProjectRepository(db)


@pytest.fixture()
def task_repo(db: DatabaseConnection) -> TaskRepository:
    return TaskRepository(db)


@pytest.fixture()
def audit_repo(db: DatabaseConnection) -> AuditRepository:
    return AuditRepository(db)


# ---------------------------------------------------------------------------
# Service fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def audit_service(audit_repo: AuditRepository) -> AuditService:
    return AuditService(audit_repo, enabled=True)


@pytest.fixture()
def user_service(user_repo: UserRepository, audit_service: AuditService) -> UserService:
    return UserService(user_repo, audit_service)


@pytest.fixture()
def auth_service(user_repo: UserRepository) -> AuthService:
    return AuthService(
        user_repo,
        secret_key="test-secret-key-for-testing-only",
        token_expiry_seconds=3600,
    )


@pytest.fixture()
def project_service(
    project_repo: ProjectRepository,
    user_repo: UserRepository,
    audit_service: AuditService,
) -> ProjectService:
    return ProjectService(project_repo, user_repo, audit_service)


@pytest.fixture()
def task_service(
    task_repo: TaskRepository,
    project_repo: ProjectRepository,
    user_repo: UserRepository,
    audit_service: AuditService,
) -> TaskService:
    return TaskService(task_repo, project_repo, user_repo, audit_service)


# ---------------------------------------------------------------------------
# Config fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_config() -> AppConfig:
    return AppConfig.for_testing()


# ---------------------------------------------------------------------------
# Seed data helpers (functions, not fixtures, to avoid accidental coupling)
# ---------------------------------------------------------------------------


def make_user(user_service: UserService, *, username: str = "testuser") -> object:
    """Helper to create a deterministic test user."""
    return user_service.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass1!",
        role="member",
    )


def make_admin(user_service: UserService, *, username: str = "adminuser") -> object:
    """Helper to create a deterministic test admin user."""
    return user_service.create_user(
        username=username,
        email=f"{username}@example.com",
        password="AdminPass1!",
        role="admin",
    )
