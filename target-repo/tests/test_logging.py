"""Tests for structured JSON logging across service operations.

Each test asserts that the relevant service method emits a log record whose
``operation``, ``entity_id``, and ``user_id`` attributes match what was
performed.  A :class:`CapturingHandler` is attached to the module logger for
the duration of each test and removed in teardown, keeping tests isolated.

Timestamp assertions only check format (``YYYY-MM-DDTHH:MM:SSZ``) rather than
an exact value, which keeps the suite deterministic without mocking the clock.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Generator

import pytest

from pyservicelab.auth.models import Credentials, RegistrationRequest
from pyservicelab.auth.service import AuthService
from pyservicelab.core.logging import CapturingHandler, JsonFormatter, ServiceLogger
from tests.conftest import make_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def capturing_logs(logger_name: str) -> Generator[CapturingHandler, None, None]:
    """Attach a :class:`CapturingHandler` to *logger_name* for the block.

    The handler is removed and the logger's effective level is restored on
    exit, ensuring complete test isolation.
    """
    handler = CapturingHandler()
    logger = logging.getLogger(logger_name)
    original_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)


def ops(handler: CapturingHandler, operation: str) -> list[logging.LogRecord]:
    """Return records from *handler* whose ``operation`` attribute matches."""
    return [r for r in handler.records if getattr(r, "operation", None) == operation]


# ---------------------------------------------------------------------------
# JsonFormatter
# ---------------------------------------------------------------------------


class TestJsonFormatter:
    """Unit tests for the JsonFormatter class."""

    def _record(self, msg: str = "test", **extra: object) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_required_fields_always_present(self) -> None:
        fmt = JsonFormatter()
        data = json.loads(fmt.format(self._record("hello")))
        assert "timestamp" in data
        assert "level" in data
        assert "logger" in data
        assert "message" in data

    def test_timestamp_iso_utc_format(self) -> None:
        fmt = JsonFormatter()
        data = json.loads(fmt.format(self._record()))
        ts: str = data["timestamp"]
        # Must be exactly YYYY-MM-DDTHH:MM:SSZ (20 characters)
        assert len(ts) == 20
        assert ts[4] == "-" and ts[7] == "-" and ts[10] == "T"
        assert ts.endswith("Z")

    def test_message_value(self) -> None:
        fmt = JsonFormatter()
        data = json.loads(fmt.format(self._record("operation completed")))
        assert data["message"] == "operation completed"

    def test_level_value(self) -> None:
        fmt = JsonFormatter()
        data = json.loads(fmt.format(self._record()))
        assert data["level"] == "INFO"

    def test_logger_name_value(self) -> None:
        fmt = JsonFormatter()
        data = json.loads(fmt.format(self._record()))
        assert data["logger"] == "test.logger"

    def test_operation_included_when_set(self) -> None:
        fmt = JsonFormatter()
        data = json.loads(fmt.format(self._record(operation="user.create_user")))
        assert data["operation"] == "user.create_user"

    def test_entity_id_included_when_set(self) -> None:
        fmt = JsonFormatter()
        data = json.loads(fmt.format(self._record(entity_id=42)))
        assert data["entity_id"] == 42

    def test_user_id_included_when_set(self) -> None:
        fmt = JsonFormatter()
        data = json.loads(fmt.format(self._record(user_id=7)))
        assert data["user_id"] == 7

    def test_none_extra_fields_omitted(self) -> None:
        """Fields that are not set (or set to None) must not appear in JSON."""
        fmt = JsonFormatter()
        data = json.loads(fmt.format(self._record()))
        assert "operation" not in data
        assert "entity_id" not in data
        assert "user_id" not in data

    def test_output_is_valid_json(self) -> None:
        fmt = JsonFormatter()
        raw = fmt.format(self._record("test", operation="x.op", entity_id=1, user_id=2))
        parsed = json.loads(raw)  # must not raise
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# CapturingHandler
# ---------------------------------------------------------------------------


class TestCapturingHandler:
    """Unit tests for the CapturingHandler class."""

    def test_captures_emitted_records(self) -> None:
        with capturing_logs("test.capture_basic") as handler:
            logging.getLogger("test.capture_basic").info("first")
            logging.getLogger("test.capture_basic").info("second")
        assert len(handler.records) == 2

    def test_records_have_correct_messages(self) -> None:
        with capturing_logs("test.capture_msgs") as handler:
            logging.getLogger("test.capture_msgs").info("hello world")
        assert handler.records[0].getMessage() == "hello world"

    def test_clear_empties_list(self) -> None:
        with capturing_logs("test.capture_clear") as handler:
            log = logging.getLogger("test.capture_clear")
            log.info("a")
            log.info("b")
            assert len(handler.records) == 2
            handler.clear()
            assert handler.records == []

    def test_captures_different_levels(self) -> None:
        with capturing_logs("test.capture_levels") as handler:
            log = logging.getLogger("test.capture_levels")
            log.debug("dbg")
            log.info("inf")
            log.warning("wrn")
        assert len(handler.records) == 3
        levels = {r.levelname for r in handler.records}
        assert levels == {"DEBUG", "INFO", "WARNING"}


# ---------------------------------------------------------------------------
# ServiceLogger
# ---------------------------------------------------------------------------


class TestServiceLogger:
    """Unit tests for the ServiceLogger class."""

    def test_log_operation_attaches_operation_field(self) -> None:
        with capturing_logs("test.svclog.op") as handler:
            slog = ServiceLogger("test.svclog.op")
            slog.log_operation("done", operation="ns.method", entity_id=1, user_id=2)
        assert len(handler.records) == 1
        assert handler.records[0].operation == "ns.method"  # type: ignore[attr-defined]

    def test_log_operation_attaches_entity_id(self) -> None:
        with capturing_logs("test.svclog.eid") as handler:
            slog = ServiceLogger("test.svclog.eid")
            slog.log_operation("done", operation="ns.method", entity_id=99)
        assert handler.records[0].entity_id == 99  # type: ignore[attr-defined]

    def test_log_operation_attaches_user_id(self) -> None:
        with capturing_logs("test.svclog.uid") as handler:
            slog = ServiceLogger("test.svclog.uid")
            slog.log_operation("done", operation="ns.method", user_id=5)
        assert handler.records[0].user_id == 5  # type: ignore[attr-defined]

    def test_log_operation_none_fields_stored_as_none(self) -> None:
        with capturing_logs("test.svclog.none") as handler:
            slog = ServiceLogger("test.svclog.none")
            slog.log_operation("done", operation="ns.method")
        rec = handler.records[0]
        assert rec.entity_id is None  # type: ignore[attr-defined]
        assert rec.user_id is None  # type: ignore[attr-defined]

    def test_log_operation_default_level_is_info(self) -> None:
        with capturing_logs("test.svclog.lvl") as handler:
            slog = ServiceLogger("test.svclog.lvl")
            slog.log_operation("done", operation="ns.method")
        assert handler.records[0].levelname == "INFO"

    def test_log_operation_respects_level_param(self) -> None:
        with capturing_logs("test.svclog.custom_lvl") as handler:
            slog = ServiceLogger("test.svclog.custom_lvl")
            slog.log_operation("warn", operation="ns.warn", level="warning")
        assert handler.records[0].levelname == "WARNING"


# ---------------------------------------------------------------------------
# UserService logging
# ---------------------------------------------------------------------------

_USER_SVC_LOGGER = "pyservicelab.services.user_service"


class TestUserServiceLogging:
    def test_create_user_emits_operation(self, user_service: object) -> None:
        with capturing_logs(_USER_SVC_LOGGER) as handler:
            user = make_user(user_service)  # type: ignore[arg-type]
        records = ops(handler, "user.create_user")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == user.id  # type: ignore[attr-defined]

    def test_create_user_with_actor_sets_user_id(self, user_service: object) -> None:
        # First create an admin without a handler so we don't pick it up
        admin = make_user(user_service, username="adminactor")  # type: ignore[arg-type]
        with capturing_logs(_USER_SVC_LOGGER) as handler:
            user = user_service.create_user(  # type: ignore[attr-defined]
                username="newbie",
                email="newbie@example.com",
                password="StrongPass1!",
                created_by=admin.id,
            )
        records = ops(handler, "user.create_user")
        assert len(records) == 1
        assert records[0].user_id == admin.id  # type: ignore[attr-defined]
        assert records[0].entity_id == user.id  # type: ignore[attr-defined]

    def test_update_email_emits_operation(self, user_service: object) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        with capturing_logs(_USER_SVC_LOGGER) as handler:
            user_service.update_email(user.id, "updated@example.com", actor_id=user.id)  # type: ignore[attr-defined]
        records = ops(handler, "user.update_email")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == user.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]

    def test_update_role_emits_operation(self, user_service: object) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        with capturing_logs(_USER_SVC_LOGGER) as handler:
            user_service.update_role(user.id, "admin", actor_id=user.id)  # type: ignore[attr-defined]
        records = ops(handler, "user.update_role")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == user.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]

    def test_set_status_emits_operation(self, user_service: object) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        with capturing_logs(_USER_SVC_LOGGER) as handler:
            user_service.set_status(user.id, "inactive", actor_id=user.id)  # type: ignore[attr-defined]
        records = ops(handler, "user.set_status")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == user.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]

    def test_delete_user_emits_operation(self, user_service: object) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        with capturing_logs(_USER_SVC_LOGGER) as handler:
            user_service.delete_user(user.id, actor_id=user.id)  # type: ignore[attr-defined]
        records = ops(handler, "user.delete_user")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == user.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]

    def test_read_operations_do_not_emit_service_logs(self, user_service: object) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        with capturing_logs(_USER_SVC_LOGGER) as handler:
            user_service.get_user(user.id)  # type: ignore[attr-defined]
            user_service.list_users()  # type: ignore[attr-defined]
        # No service-operation records expected for reads
        service_ops = [r for r in handler.records if hasattr(r, "operation")]
        assert service_ops == []


# ---------------------------------------------------------------------------
# ProjectService logging
# ---------------------------------------------------------------------------

_PROJ_SVC_LOGGER = "pyservicelab.services.project_service"


class TestProjectServiceLogging:
    def test_create_project_emits_operation(
        self, project_service: object, user_service: object
    ) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        with capturing_logs(_PROJ_SVC_LOGGER) as handler:
            project = project_service.create_project(  # type: ignore[attr-defined]
                name="Alpha",
                description="desc",
                owner_id=user.id,
                actor_id=user.id,
            )
        records = ops(handler, "project.create_project")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == project.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]

    def test_create_project_without_actor_uses_owner(
        self, project_service: object, user_service: object
    ) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        with capturing_logs(_PROJ_SVC_LOGGER) as handler:
            project_service.create_project(  # type: ignore[attr-defined]
                name="Beta", description="desc", owner_id=user.id
            )
        records = ops(handler, "project.create_project")
        assert len(records) == 1
        assert records[0].user_id == user.id  # type: ignore[attr-defined]

    def test_update_project_emits_operation(
        self, project_service: object, user_service: object
    ) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        project = project_service.create_project(  # type: ignore[attr-defined]
            name="Old Name", description="d", owner_id=user.id
        )
        with capturing_logs(_PROJ_SVC_LOGGER) as handler:
            project_service.update_project(  # type: ignore[attr-defined]
                project.id, name="New Name", actor_id=user.id
            )
        records = ops(handler, "project.update_project")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == project.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]

    def test_update_project_no_changes_does_not_emit(
        self, project_service: object, user_service: object
    ) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        project = project_service.create_project(  # type: ignore[attr-defined]
            name="Stable", description="d", owner_id=user.id
        )
        with capturing_logs(_PROJ_SVC_LOGGER) as handler:
            # Calling update_project with no fields changed → no log expected
            project_service.update_project(project.id)  # type: ignore[attr-defined]
        records = ops(handler, "project.update_project")
        assert records == []

    def test_delete_project_emits_operation(
        self, project_service: object, user_service: object
    ) -> None:
        user = make_user(user_service)  # type: ignore[arg-type]
        project = project_service.create_project(  # type: ignore[attr-defined]
            name="Doomed", description="d", owner_id=user.id
        )
        with capturing_logs(_PROJ_SVC_LOGGER) as handler:
            project_service.delete_project(project.id, actor_id=user.id)  # type: ignore[attr-defined]
        records = ops(handler, "project.delete_project")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == project.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# TaskService logging
# ---------------------------------------------------------------------------

_TASK_SVC_LOGGER = "pyservicelab.services.task_service"


class TestTaskServiceLogging:
    def _setup(
        self, user_service: object, project_service: object
    ) -> tuple[object, object]:
        user = make_user(user_service)  # type: ignore[arg-type]
        project = project_service.create_project(  # type: ignore[attr-defined]
            name="P", description="d", owner_id=user.id
        )
        return user, project

    def test_create_task_emits_operation(
        self,
        task_service: object,
        project_service: object,
        user_service: object,
    ) -> None:
        user, project = self._setup(user_service, project_service)
        with capturing_logs(_TASK_SVC_LOGGER) as handler:
            task = task_service.create_task(  # type: ignore[attr-defined]
                project_id=project.id,
                title="Fix bug",
                description="desc",
                created_by=user.id,
            )
        records = ops(handler, "task.create_task")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == task.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]

    def test_update_task_emits_operation(
        self,
        task_service: object,
        project_service: object,
        user_service: object,
    ) -> None:
        user, project = self._setup(user_service, project_service)
        task = task_service.create_task(  # type: ignore[attr-defined]
            project_id=project.id, title="Old", description="d", created_by=user.id
        )
        with capturing_logs(_TASK_SVC_LOGGER) as handler:
            task_service.update_task(task.id, title="New", actor_id=user.id)  # type: ignore[attr-defined]
        records = ops(handler, "task.update_task")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == task.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]

    def test_update_task_no_changes_does_not_emit(
        self,
        task_service: object,
        project_service: object,
        user_service: object,
    ) -> None:
        user, project = self._setup(user_service, project_service)
        task = task_service.create_task(  # type: ignore[attr-defined]
            project_id=project.id, title="Stable", description="d", created_by=user.id
        )
        with capturing_logs(_TASK_SVC_LOGGER) as handler:
            task_service.update_task(task.id)  # type: ignore[attr-defined]
        records = ops(handler, "task.update_task")
        assert records == []

    def test_delete_task_emits_operation(
        self,
        task_service: object,
        project_service: object,
        user_service: object,
    ) -> None:
        user, project = self._setup(user_service, project_service)
        task = task_service.create_task(  # type: ignore[attr-defined]
            project_id=project.id, title="Bye", description="d", created_by=user.id
        )
        with capturing_logs(_TASK_SVC_LOGGER) as handler:
            task_service.delete_task(task.id, actor_id=user.id)  # type: ignore[attr-defined]
        records = ops(handler, "task.delete_task")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == task.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AuthService logging
# ---------------------------------------------------------------------------

_AUTH_SVC_LOGGER = "pyservicelab.auth.service"


class TestAuthServiceLogging:
    def test_register_emits_operation(self, auth_service: object) -> None:
        with capturing_logs(_AUTH_SVC_LOGGER) as handler:
            user = auth_service.register(  # type: ignore[attr-defined]
                RegistrationRequest(
                    username="reguser",
                    email="reg@example.com",
                    password="RegPass1!",
                )
            )
        records = ops(handler, "auth.register")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == user.id  # type: ignore[attr-defined]
        assert r.user_id is None  # type: ignore[attr-defined]

    def test_login_emits_operation(self, auth_service: object) -> None:
        auth_service.register(  # type: ignore[attr-defined]
            RegistrationRequest(
                username="loginuser",
                email="login@example.com",
                password="LoginPass1!",
            )
        )
        with capturing_logs(_AUTH_SVC_LOGGER) as handler:
            result = auth_service.login(  # type: ignore[attr-defined]
                Credentials(username="loginuser", password="LoginPass1!")
            )
        records = ops(handler, "auth.login")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == result.user_id  # type: ignore[attr-defined]
        assert r.user_id == result.user_id  # type: ignore[attr-defined]

    def test_change_password_emits_operation(self, auth_service: object) -> None:
        user = auth_service.register(  # type: ignore[attr-defined]
            RegistrationRequest(
                username="pwduser",
                email="pwd@example.com",
                password="OldPass1!",
            )
        )
        with capturing_logs(_AUTH_SVC_LOGGER) as handler:
            auth_service.change_password(user.id, "OldPass1!", "NewPass1!")  # type: ignore[attr-defined]
        records = ops(handler, "auth.change_password")
        assert len(records) == 1
        r = records[0]
        assert r.entity_id == user.id  # type: ignore[attr-defined]
        assert r.user_id == user.id  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# End-to-end: service log record → JsonFormatter → valid JSON
# ---------------------------------------------------------------------------


class TestJsonFormatterEndToEnd:
    """Verify that records emitted by services produce parseable JSON with
    all required fields when processed through JsonFormatter."""

    def test_user_create_produces_valid_json(self, user_service: object) -> None:
        fmt = JsonFormatter()
        with capturing_logs(_USER_SVC_LOGGER) as handler:
            user = make_user(user_service)  # type: ignore[arg-type]

        records = ops(handler, "user.create_user")
        assert len(records) == 1
        raw = fmt.format(records[0])
        data = json.loads(raw)

        assert data["operation"] == "user.create_user"
        assert data["entity_id"] == user.id
        assert "timestamp" in data
        assert len(data["timestamp"]) == 20  # YYYY-MM-DDTHH:MM:SSZ
        assert data["timestamp"].endswith("Z")
        assert data["level"] == "INFO"
        assert data["logger"] == _USER_SVC_LOGGER

    def test_project_delete_produces_valid_json(
        self, project_service: object, user_service: object
    ) -> None:
        fmt = JsonFormatter()
        user = make_user(user_service)  # type: ignore[arg-type]
        project = project_service.create_project(  # type: ignore[attr-defined]
            name="Ephemeral", description="d", owner_id=user.id
        )
        with capturing_logs(_PROJ_SVC_LOGGER) as handler:
            project_service.delete_project(project.id, actor_id=user.id)  # type: ignore[attr-defined]

        records = ops(handler, "project.delete_project")
        assert len(records) == 1
        data = json.loads(fmt.format(records[0]))
        assert data["operation"] == "project.delete_project"
        assert data["entity_id"] == project.id
        assert data["user_id"] == user.id

    def test_task_create_produces_valid_json(
        self,
        task_service: object,
        project_service: object,
        user_service: object,
    ) -> None:
        fmt = JsonFormatter()
        user = make_user(user_service)  # type: ignore[arg-type]
        project = project_service.create_project(  # type: ignore[attr-defined]
            name="P", description="d", owner_id=user.id
        )
        with capturing_logs(_TASK_SVC_LOGGER) as handler:
            task = task_service.create_task(  # type: ignore[attr-defined]
                project_id=project.id,
                title="My Task",
                description="d",
                created_by=user.id,
            )

        records = ops(handler, "task.create_task")
        assert len(records) == 1
        data = json.loads(fmt.format(records[0]))
        assert data["operation"] == "task.create_task"
        assert data["entity_id"] == task.id
        assert data["user_id"] == user.id

    def test_auth_login_produces_valid_json(self, auth_service: object) -> None:
        fmt = JsonFormatter()
        auth_service.register(  # type: ignore[attr-defined]
            RegistrationRequest(
                username="e2elogin",
                email="e2elogin@example.com",
                password="E2ePass1!",
            )
        )
        with capturing_logs(_AUTH_SVC_LOGGER) as handler:
            result = auth_service.login(  # type: ignore[attr-defined]
                Credentials(username="e2elogin", password="E2ePass1!")
            )

        records = ops(handler, "auth.login")
        assert len(records) == 1
        data = json.loads(fmt.format(records[0]))
        assert data["operation"] == "auth.login"
        assert data["entity_id"] == result.user_id
        assert data["user_id"] == result.user_id
        assert "timestamp" in data
        assert "user_id" not in {k: v for k, v in data.items() if v is None}
