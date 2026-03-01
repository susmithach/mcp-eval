"""Tests for the project service."""
from __future__ import annotations

import pytest

from pyservicelab.core.errors import NotFoundError, ValidationError
from pyservicelab.domain.project import ProjectStatus
from pyservicelab.services.project_service import ProjectService
from pyservicelab.services.user_service import UserService
from tests.conftest import make_user


@pytest.fixture()
def owner(user_service: UserService):
    return make_user(user_service, username="owner")


@pytest.fixture()
def project(project_service: ProjectService, owner):
    return project_service.create_project(
        name="Test Project",
        description="A test project",
        owner_id=owner.id,
    )


class TestCreateProject:
    def test_create_returns_project(
        self, project_service: ProjectService, owner
    ) -> None:
        p = project_service.create_project(
            name="My Project",
            description="Description here",
            owner_id=owner.id,
        )
        assert p.id is not None
        assert p.name == "My Project"
        assert p.owner_id == owner.id

    def test_create_default_status_is_draft(
        self, project_service: ProjectService, owner
    ) -> None:
        p = project_service.create_project("Draft", "desc", owner.id)
        assert p.status == ProjectStatus.DRAFT

    def test_create_with_active_status(
        self, project_service: ProjectService, owner
    ) -> None:
        p = project_service.create_project("Active P", "desc", owner.id, status="active")
        assert p.status == ProjectStatus.ACTIVE

    def test_create_with_tags(
        self, project_service: ProjectService, owner
    ) -> None:
        p = project_service.create_project(
            "Tagged", "desc", owner.id, tags=["alpha", "beta"]
        )
        assert "alpha" in p.get_tags()
        assert "beta" in p.get_tags()

    def test_create_unknown_owner_raises(
        self, project_service: ProjectService
    ) -> None:
        with pytest.raises(NotFoundError):
            project_service.create_project("P", "desc", owner_id=99999)

    def test_create_empty_name_raises(
        self, project_service: ProjectService, owner
    ) -> None:
        with pytest.raises(ValidationError):
            project_service.create_project("", "desc", owner.id)


class TestGetProject:
    def test_get_existing(self, project_service: ProjectService, project) -> None:
        fetched = project_service.get_project(project.id)
        assert fetched.id == project.id

    def test_get_nonexistent_raises(self, project_service: ProjectService) -> None:
        with pytest.raises(NotFoundError):
            project_service.get_project(99999)


class TestListProjects:
    def test_list_empty(self, project_service: ProjectService) -> None:
        assert project_service.list_projects() == []

    def test_list_returns_all(
        self, project_service: ProjectService, owner
    ) -> None:
        project_service.create_project("P1", "d1", owner.id)
        project_service.create_project("P2", "d2", owner.id)
        projects = project_service.list_projects()
        assert len(projects) == 2

    def test_list_by_owner(
        self,
        project_service: ProjectService,
        user_service: UserService,
        owner,
    ) -> None:
        other = make_user(user_service, username="other_owner")
        project_service.create_project("Owner P", "desc", owner.id)
        project_service.create_project("Other P", "desc", other.id)
        mine = project_service.list_by_owner(owner.id)
        assert len(mine) == 1
        assert mine[0].name == "Owner P"

    def test_list_by_status(
        self, project_service: ProjectService, owner
    ) -> None:
        project_service.create_project("Draft P", "d", owner.id, status="draft")
        project_service.create_project("Active P", "d", owner.id, status="active")
        active = project_service.list_by_status("active")
        assert all(p.status == ProjectStatus.ACTIVE for p in active)


class TestUpdateProject:
    def test_update_name(self, project_service: ProjectService, project) -> None:
        updated = project_service.update_project(project.id, name="New Name")
        assert updated.name == "New Name"

    def test_update_status(self, project_service: ProjectService, project) -> None:
        updated = project_service.update_project(project.id, status="active")
        assert updated.status == ProjectStatus.ACTIVE

    def test_update_invalid_status_raises(
        self, project_service: ProjectService, project
    ) -> None:
        with pytest.raises(ValidationError):
            project_service.update_project(project.id, status="invalid_status")

    def test_update_tags(self, project_service: ProjectService, project) -> None:
        updated = project_service.update_project(project.id, tags=["tag1", "tag2"])
        assert "tag1" in updated.get_tags()

    def test_archive_project(self, project_service: ProjectService, project) -> None:
        archived = project_service.archive_project(project.id)
        assert archived.status == ProjectStatus.ARCHIVED

    def test_activate_project(self, project_service: ProjectService, project) -> None:
        project_service.archive_project(project.id)
        activated = project_service.activate_project(project.id)
        assert activated.status == ProjectStatus.ACTIVE


class TestDeleteProject:
    def test_delete_existing(self, project_service: ProjectService, project) -> None:
        result = project_service.delete_project(project.id)
        assert result is True
        with pytest.raises(NotFoundError):
            project_service.get_project(project.id)

    def test_delete_nonexistent_raises(self, project_service: ProjectService) -> None:
        with pytest.raises(NotFoundError):
            project_service.delete_project(99999)
