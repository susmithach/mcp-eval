"""Tests for the task service."""
from __future__ import annotations

import pytest

from pyservicelab.core.errors import NotFoundError, ValidationError
from pyservicelab.domain.task import TaskPriority, TaskStatus
from pyservicelab.services.project_service import ProjectService
from pyservicelab.services.task_service import TaskService
from pyservicelab.services.user_service import UserService
from tests.conftest import make_user


@pytest.fixture()
def owner(user_service: UserService):
    return make_user(user_service, username="task_owner")


@pytest.fixture()
def project(project_service: ProjectService, owner):
    return project_service.create_project("Task Project", "desc", owner.id)


@pytest.fixture()
def task(task_service: TaskService, project, owner):
    return task_service.create_task(
        project_id=project.id,
        title="Sample Task",
        description="A sample task",
        created_by=owner.id,
    )


class TestCreateTask:
    def test_create_returns_task(
        self, task_service: TaskService, project, owner
    ) -> None:
        t = task_service.create_task(
            project_id=project.id,
            title="My Task",
            description="Description",
            created_by=owner.id,
        )
        assert t.id is not None
        assert t.title == "My Task"
        assert t.project_id == project.id

    def test_create_default_status_todo(
        self, task_service: TaskService, project, owner
    ) -> None:
        t = task_service.create_task(project.id, "T", "D", owner.id)
        assert t.status == TaskStatus.TODO

    def test_create_default_priority_medium(
        self, task_service: TaskService, project, owner
    ) -> None:
        t = task_service.create_task(project.id, "T", "D", owner.id)
        assert t.priority == TaskPriority.MEDIUM

    def test_create_with_assignee(
        self,
        task_service: TaskService,
        project,
        owner,
        user_service: UserService,
    ) -> None:
        assignee = make_user(user_service, username="assignee_user")
        t = task_service.create_task(
            project_id=project.id,
            title="Assigned Task",
            description="D",
            created_by=owner.id,
            assignee_id=assignee.id,
        )
        assert t.assignee_id == assignee.id

    def test_create_unknown_project_raises(
        self, task_service: TaskService, owner
    ) -> None:
        with pytest.raises(NotFoundError):
            task_service.create_task(99999, "T", "D", owner.id)

    def test_create_unknown_assignee_raises(
        self, task_service: TaskService, project, owner
    ) -> None:
        with pytest.raises(NotFoundError):
            task_service.create_task(project.id, "T", "D", owner.id, assignee_id=99999)

    def test_create_empty_title_raises(
        self, task_service: TaskService, project, owner
    ) -> None:
        with pytest.raises(ValidationError):
            task_service.create_task(project.id, "", "D", owner.id)

    def test_create_with_estimated_hours(
        self, task_service: TaskService, project, owner
    ) -> None:
        t = task_service.create_task(project.id, "T", "D", owner.id, estimated_hours=3.5)
        assert t.estimated_hours == 3.5


class TestGetTask:
    def test_get_existing(self, task_service: TaskService, task) -> None:
        fetched = task_service.get_task(task.id)
        assert fetched.id == task.id

    def test_get_nonexistent_raises(self, task_service: TaskService) -> None:
        with pytest.raises(NotFoundError):
            task_service.get_task(99999)


class TestListTasks:
    def test_list_empty(self, task_service: TaskService) -> None:
        assert task_service.list_tasks() == []

    def test_list_by_project(
        self, task_service: TaskService, project, owner
    ) -> None:
        task_service.create_task(project.id, "T1", "D", owner.id)
        task_service.create_task(project.id, "T2", "D", owner.id)
        tasks = task_service.list_by_project(project.id)
        assert len(tasks) == 2

    def test_list_by_assignee(
        self,
        task_service: TaskService,
        user_service: UserService,
        project,
        owner,
    ) -> None:
        a = make_user(user_service, username="list_assignee")
        task_service.create_task(project.id, "Assigned", "D", owner.id, assignee_id=a.id)
        task_service.create_task(project.id, "Unassigned", "D", owner.id)
        assigned = task_service.list_by_assignee(a.id)
        assert len(assigned) == 1
        assert assigned[0].title == "Assigned"

    def test_list_by_status(
        self, task_service: TaskService, project, owner
    ) -> None:
        task_service.create_task(project.id, "Todo Task", "D", owner.id)
        t2 = task_service.create_task(project.id, "Done Task", "D", owner.id)
        task_service.update_task(t2.id, status="done")
        done = task_service.list_by_status("done")
        assert len(done) == 1
        assert done[0].title == "Done Task"


class TestUpdateTask:
    def test_update_title(self, task_service: TaskService, task) -> None:
        updated = task_service.update_task(task.id, title="New Title")
        assert updated.title == "New Title"

    def test_update_status(self, task_service: TaskService, task) -> None:
        updated = task_service.update_task(task.id, status="in_progress")
        assert updated.status == TaskStatus.IN_PROGRESS

    def test_update_priority(self, task_service: TaskService, task) -> None:
        updated = task_service.update_task(task.id, priority="critical")
        assert updated.priority == TaskPriority.CRITICAL

    def test_update_invalid_status_raises(self, task_service: TaskService, task) -> None:
        with pytest.raises(ValidationError):
            task_service.update_task(task.id, status="flying")

    def test_update_invalid_priority_raises(self, task_service: TaskService, task) -> None:
        with pytest.raises(ValidationError):
            task_service.update_task(task.id, priority="ultra")

    def test_transition_status(self, task_service: TaskService, task) -> None:
        updated = task_service.transition_status(task.id, "done")
        assert updated.is_complete() is True

    def test_assign_task(
        self,
        task_service: TaskService,
        user_service: UserService,
        task,
    ) -> None:
        assignee = make_user(user_service, username="new_assignee")
        updated = task_service.assign_task(task.id, assignee.id)
        assert updated.assignee_id == assignee.id


class TestDeleteTask:
    def test_delete_existing(self, task_service: TaskService, task) -> None:
        result = task_service.delete_task(task.id)
        assert result is True
        with pytest.raises(NotFoundError):
            task_service.get_task(task.id)

    def test_delete_nonexistent_raises(self, task_service: TaskService) -> None:
        with pytest.raises(NotFoundError):
            task_service.delete_task(99999)
