"""Tests for the user service."""
from __future__ import annotations

import pytest

from pyservicelab.core.errors import DuplicateError, NotFoundError, ValidationError
from pyservicelab.domain.user import UserRole, UserStatus
from pyservicelab.services.user_service import UserService
from tests.conftest import make_admin, make_user


class TestCreateUser:
    def test_create_returns_user(self, user_service: UserService) -> None:
        user = user_service.create_user(
            username="alice",
            email="alice@example.com",
            password="AlicePass1!",
        )
        assert user.id is not None
        assert user.username == "alice"
        assert user.email == "alice@example.com"

    def test_create_hashes_password(self, user_service: UserService) -> None:
        user = user_service.create_user(
            username="bob",
            email="bob@example.com",
            password="BobPass1!",
        )
        assert user.password_hash != "BobPass1!"

    def test_create_default_role_is_member(self, user_service: UserService) -> None:
        user = user_service.create_user(
            username="carol",
            email="carol@example.com",
            password="CarolPass1!",
        )
        assert user.role == UserRole.MEMBER

    def test_create_with_admin_role(self, user_service: UserService) -> None:
        user = user_service.create_user(
            username="dave",
            email="dave@example.com",
            password="DavePass1!",
            role="admin",
        )
        assert user.role == UserRole.ADMIN

    def test_create_duplicate_username_raises(self, user_service: UserService) -> None:
        user_service.create_user("dup", "dup@example.com", "DupPass1!")
        with pytest.raises(DuplicateError):
            user_service.create_user("dup", "other@example.com", "DupPass1!")

    def test_create_duplicate_email_raises(self, user_service: UserService) -> None:
        user_service.create_user("user1", "shared@example.com", "Pass1234!")
        with pytest.raises(DuplicateError):
            user_service.create_user("user2", "shared@example.com", "Pass1234!")

    def test_create_invalid_email_raises(self, user_service: UserService) -> None:
        with pytest.raises(ValidationError):
            user_service.create_user("badmail", "not-an-email", "ValidPass1!")

    def test_create_short_username_raises(self, user_service: UserService) -> None:
        with pytest.raises(ValidationError):
            user_service.create_user("ab", "ab@example.com", "ValidPass1!")

    def test_create_short_password_raises(self, user_service: UserService) -> None:
        with pytest.raises(ValidationError):
            user_service.create_user("shortpw", "short@example.com", "abc")

    def test_create_status_is_active(self, user_service: UserService) -> None:
        user = user_service.create_user("active", "active@example.com", "ActivePass1!")
        assert user.status == UserStatus.ACTIVE


class TestGetUser:
    def test_get_existing_user(self, user_service: UserService) -> None:
        created = make_user(user_service, username="findme")
        fetched = user_service.get_user(created.id)
        assert fetched.username == "findme"

    def test_get_nonexistent_raises(self, user_service: UserService) -> None:
        with pytest.raises(NotFoundError):
            user_service.get_user(99999)

    def test_get_by_username(self, user_service: UserService) -> None:
        make_user(user_service, username="lookup")
        user = user_service.get_user_by_username("lookup")
        assert user is not None
        assert user.username == "lookup"

    def test_get_by_username_missing_returns_none(self, user_service: UserService) -> None:
        assert user_service.get_user_by_username("nobody") is None

    def test_get_by_email(self, user_service: UserService) -> None:
        make_user(user_service, username="emailuser")
        user = user_service.get_user_by_email("emailuser@example.com")
        assert user is not None


class TestListUsers:
    def test_list_empty(self, user_service: UserService) -> None:
        assert user_service.list_users() == []

    def test_list_returns_all(self, user_service: UserService) -> None:
        make_user(user_service, username="user_a")
        make_user(user_service, username="user_b")
        users = user_service.list_users()
        assert len(users) == 2

    def test_list_active_only(self, user_service: UserService) -> None:
        u1 = make_user(user_service, username="active_u")
        u2 = make_user(user_service, username="inactive_u")
        user_service.deactivate_user(u2.id)
        active = user_service.list_active_users()
        usernames = [u.username for u in active]
        assert "active_u" in usernames
        assert "inactive_u" not in usernames


class TestUpdateUser:
    def test_update_email(self, user_service: UserService) -> None:
        user = make_user(user_service, username="emailchange")
        updated = user_service.update_email(user.id, "newemail@example.com")
        assert updated.email == "newemail@example.com"

    def test_update_email_invalid_raises(self, user_service: UserService) -> None:
        user = make_user(user_service, username="bademail")
        with pytest.raises(ValidationError):
            user_service.update_email(user.id, "not-an-email")

    def test_update_role(self, user_service: UserService) -> None:
        user = make_user(user_service, username="rolechange")
        updated = user_service.update_role(user.id, "manager")
        assert updated.role == UserRole.MANAGER

    def test_deactivate_user(self, user_service: UserService) -> None:
        user = make_user(user_service, username="deactivate_me")
        updated = user_service.deactivate_user(user.id)
        assert updated.status == UserStatus.INACTIVE

    def test_activate_user(self, user_service: UserService) -> None:
        user = make_user(user_service, username="reactivate_me")
        user_service.deactivate_user(user.id)
        updated = user_service.activate_user(user.id)
        assert updated.status == UserStatus.ACTIVE


class TestDeleteUser:
    def test_delete_existing_user(self, user_service: UserService) -> None:
        user = make_user(user_service, username="delete_me")
        result = user_service.delete_user(user.id)
        assert result is True
        with pytest.raises(NotFoundError):
            user_service.get_user(user.id)

    def test_delete_nonexistent_raises(self, user_service: UserService) -> None:
        with pytest.raises(NotFoundError):
            user_service.delete_user(99999)
