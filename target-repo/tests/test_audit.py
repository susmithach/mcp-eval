"""Tests for the audit service and repository."""
from __future__ import annotations

import pytest

from pyservicelab.db.audit_repo import AuditRepository
from pyservicelab.domain.audit import AuditAction, AuditEntry
from pyservicelab.services.audit_service import AuditService
from pyservicelab.services.user_service import UserService
from tests.conftest import make_user


class TestAuditEntry:
    def test_make_creates_entry(self) -> None:
        entry = AuditEntry.make(
            action=AuditAction.CREATE,
            resource_type="user",
            details="User created",
        )
        assert entry.action == AuditAction.CREATE
        assert entry.resource_type == "user"
        assert entry.id is None  # not persisted yet

    def test_to_dict(self) -> None:
        entry = AuditEntry.make(
            action=AuditAction.LOGIN,
            resource_type="auth",
            details="Login attempt",
            user_id=1,
            success=True,
        )
        d = entry.to_dict()
        assert d["action"] == "login"
        assert d["user_id"] == 1
        assert d["success"] is True


class TestAuditRepository:
    def test_create_entry(self, audit_repo: AuditRepository) -> None:
        entry = AuditEntry.make(
            action=AuditAction.CREATE,
            resource_type="user",
            details="Test entry",
        )
        saved = audit_repo.create(entry)
        assert saved.id is not None

    def test_list_all(self, audit_repo: AuditRepository) -> None:
        for i in range(3):
            audit_repo.create(
                AuditEntry.make(AuditAction.UPDATE, "project", f"Update {i}")
            )
        entries = audit_repo.list_all()
        assert len(entries) == 3

    def test_list_by_user(self, audit_repo: AuditRepository) -> None:
        audit_repo.create(
            AuditEntry.make(AuditAction.CREATE, "task", "Task created", user_id=1)
        )
        audit_repo.create(
            AuditEntry.make(AuditAction.CREATE, "task", "Task created", user_id=2)
        )
        entries = audit_repo.list_by_user(1)
        assert len(entries) == 1
        assert entries[0].user_id == 1

    def test_list_by_resource(self, audit_repo: AuditRepository) -> None:
        audit_repo.create(
            AuditEntry.make(AuditAction.CREATE, "project", "P created", resource_id="42")
        )
        audit_repo.create(
            AuditEntry.make(AuditAction.DELETE, "user", "User deleted", resource_id="5")
        )
        entries = audit_repo.list_by_resource("project")
        assert len(entries) == 1
        assert entries[0].resource_type == "project"

    def test_list_by_resource_with_id(self, audit_repo: AuditRepository) -> None:
        audit_repo.create(
            AuditEntry.make(AuditAction.UPDATE, "project", "Updated", resource_id="10")
        )
        audit_repo.create(
            AuditEntry.make(AuditAction.UPDATE, "project", "Updated", resource_id="11")
        )
        entries = audit_repo.list_by_resource("project", resource_id="10")
        assert len(entries) == 1

    def test_list_failures(self, audit_repo: AuditRepository) -> None:
        audit_repo.create(
            AuditEntry.make(AuditAction.AUTH_FAILURE, "auth", "Bad login", success=False)
        )
        audit_repo.create(
            AuditEntry.make(AuditAction.LOGIN, "auth", "Good login", success=True)
        )
        failures = audit_repo.list_failures()
        assert len(failures) == 1
        assert failures[0].success is False

    def test_count_by_action(self, audit_repo: AuditRepository) -> None:
        audit_repo.create(AuditEntry.make(AuditAction.CREATE, "user", "c1"))
        audit_repo.create(AuditEntry.make(AuditAction.CREATE, "user", "c2"))
        audit_repo.create(AuditEntry.make(AuditAction.DELETE, "user", "d1"))
        assert audit_repo.count_by_action(AuditAction.CREATE) == 2
        assert audit_repo.count_by_action(AuditAction.DELETE) == 1


class TestAuditService:
    def test_log_creates_entry(self, audit_service: AuditService) -> None:
        entry = audit_service.log(
            action=AuditAction.CREATE,
            resource_type="user",
            details="User created",
            user_id=1,
        )
        assert entry is not None
        assert entry.id is not None

    def test_log_disabled_returns_none(self, audit_repo: AuditRepository) -> None:
        svc = AuditService(audit_repo, enabled=False)
        result = svc.log(AuditAction.CREATE, "user", "test")
        assert result is None

    def test_log_create_shorthand(self, audit_service: AuditService) -> None:
        entry = audit_service.log_create("project", "5", "Project created", user_id=1)
        assert entry is not None
        assert entry.action == AuditAction.CREATE

    def test_log_update_shorthand(self, audit_service: AuditService) -> None:
        entry = audit_service.log_update("task", "3", "Task updated")
        assert entry is not None
        assert entry.action == AuditAction.UPDATE

    def test_log_delete_shorthand(self, audit_service: AuditService) -> None:
        entry = audit_service.log_delete("user", "7", "User deleted")
        assert entry is not None
        assert entry.action == AuditAction.DELETE

    def test_recent_returns_latest(self, audit_service: AuditService) -> None:
        for i in range(5):
            audit_service.log(AuditAction.READ, "project", f"Read {i}")
        recent = audit_service.recent(limit=3)
        assert len(recent) == 3

    def test_for_user_filters(self, audit_service: AuditService) -> None:
        audit_service.log(AuditAction.CREATE, "task", "Created", user_id=1)
        audit_service.log(AuditAction.CREATE, "task", "Created", user_id=2)
        entries = audit_service.for_user(1)
        assert all(e.user_id == 1 for e in entries)

    def test_failures_filter(self, audit_service: AuditService) -> None:
        audit_service.log(
            AuditAction.AUTH_FAILURE, "auth", "Failed login", success=False
        )
        audit_service.log(AuditAction.LOGIN, "auth", "Logged in", success=True)
        failures = audit_service.failures()
        assert len(failures) == 1

    def test_count_total(self, audit_service: AuditService) -> None:
        audit_service.log(AuditAction.CREATE, "user", "u1")
        audit_service.log(AuditAction.CREATE, "user", "u2")
        assert audit_service.count() == 2

    def test_audit_integration_with_user_service(
        self, user_service: UserService, audit_service: AuditService
    ) -> None:
        make_user(user_service, username="audited_user")
        entries = audit_service.for_resource("user")
        assert len(entries) >= 1
