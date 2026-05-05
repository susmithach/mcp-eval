"""Tests for the authentication layer."""
from __future__ import annotations

import pytest

from pyservicelab.auth.hashing import hash_password, needs_rehash, verify_password
from pyservicelab.auth.models import Credentials, RegistrationRequest, TokenPayload
from pyservicelab.auth.policies import (
    can_create_project,
    can_create_user,
    can_view_audit_log,
    has_role,
    require_role,
    role_level,
)
from pyservicelab.auth.service import AuthService
from pyservicelab.auth.tokens import (
    decode_token,
    extract_user_id,
    generate_token,
    is_token_valid,
)
from pyservicelab.core.errors import AuthError, DuplicateError, TokenError, ValidationError
from pyservicelab.db.user_repo import UserRepository


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_returns_string(self) -> None:
        h = hash_password("secret123")
        assert isinstance(h, str)

    def test_hash_contains_separator(self) -> None:
        h = hash_password("secret123")
        assert "$" in h

    def test_verify_correct_password(self) -> None:
        h = hash_password("correct_horse")
        assert verify_password("correct_horse", h) is True

    def test_verify_wrong_password(self) -> None:
        h = hash_password("correct_horse")
        assert verify_password("wrong_horse", h) is False

    def test_two_hashes_differ(self) -> None:
        """Different salts → different hashes for the same password."""
        h1 = hash_password("same_pass")
        h2 = hash_password("same_pass")
        assert h1 != h2

    def test_verify_malformed_hash(self) -> None:
        assert verify_password("any", "no-separator-here") is False

    def test_needs_rehash_always_false(self) -> None:
        h = hash_password("pw")
        assert needs_rehash(h) is False


# ---------------------------------------------------------------------------
# Token generation and validation
# ---------------------------------------------------------------------------


SECRET = "super-secret-key-for-tests"


class TestTokens:
    def test_generate_returns_string(self) -> None:
        token = generate_token(user_id=1, role="member", secret=SECRET)
        assert isinstance(token, str)

    def test_token_contains_dot_separator(self) -> None:
        token = generate_token(user_id=1, role="member", secret=SECRET)
        assert "." in token

    def test_decode_valid_token(self) -> None:
        token = generate_token(user_id=42, role="admin", secret=SECRET)
        payload = decode_token(token, SECRET)
        assert payload["sub"] == 42
        assert payload["role"] == "admin"

    def test_decode_invalid_signature(self) -> None:
        token = generate_token(user_id=1, role="member", secret=SECRET)
        tampered = token[:-4] + "XXXX"
        with pytest.raises(TokenError):
            decode_token(tampered, SECRET)

    def test_decode_wrong_secret(self) -> None:
        token = generate_token(user_id=1, role="member", secret=SECRET)
        with pytest.raises(TokenError):
            decode_token(token, "wrong-secret")

    def test_decode_expired_token(self) -> None:
        token = generate_token(user_id=1, role="member", secret=SECRET, expiry_seconds=-1)
        with pytest.raises(TokenError, match="expired"):
            decode_token(token, SECRET)

    def test_is_token_valid_true(self) -> None:
        token = generate_token(user_id=1, role="member", secret=SECRET)
        assert is_token_valid(token, SECRET) is True

    def test_is_token_valid_false(self) -> None:
        assert is_token_valid("garbage.token", SECRET) is False

    def test_extract_user_id(self) -> None:
        token = generate_token(user_id=99, role="member", secret=SECRET)
        assert extract_user_id(token, SECRET) == 99

    def test_malformed_token_no_separator(self) -> None:
        with pytest.raises(TokenError):
            decode_token("nodot", SECRET)


# ---------------------------------------------------------------------------
# Auth service
# ---------------------------------------------------------------------------


class TestAuthService:
    def test_register_creates_user(
        self, auth_service: AuthService, user_repo: UserRepository
    ) -> None:
        req = RegistrationRequest(
            username="newuser",
            email="new@example.com",
            password="ValidPass1!",
        )
        user = auth_service.register(req)
        assert user.id is not None
        assert user.username == "newuser"

    def test_register_hashes_password(self, auth_service: AuthService) -> None:
        req = RegistrationRequest(
            username="hashtest",
            email="hash@example.com",
            password="PlainText1!",
        )
        user = auth_service.register(req)
        assert user.password_hash != "PlainText1!"
        assert "$" in user.password_hash

    def test_register_duplicate_username_raises(self, auth_service: AuthService) -> None:
        req = RegistrationRequest(
            username="dupuser",
            email="dup@example.com",
            password="DupPass1!",
        )
        auth_service.register(req)
        with pytest.raises(DuplicateError):
            auth_service.register(
                RegistrationRequest(
                    username="dupuser",
                    email="other@example.com",
                    password="DupPass1!",
                )
            )

    def test_register_duplicate_email_raises(self, auth_service: AuthService) -> None:
        auth_service.register(
            RegistrationRequest(
                username="user_a",
                email="same@example.com",
                password="ValidPass1!",
            )
        )
        with pytest.raises(DuplicateError):
            auth_service.register(
                RegistrationRequest(
                    username="user_b",
                    email="same@example.com",
                    password="ValidPass1!",
                )
            )

    def test_register_invalid_email_raises(self, auth_service: AuthService) -> None:
        with pytest.raises(ValidationError):
            auth_service.register(
                RegistrationRequest(
                    username="badmail",
                    email="not-an-email",
                    password="ValidPass1!",
                )
            )

    def test_register_short_password_raises(self, auth_service: AuthService) -> None:
        with pytest.raises(ValidationError):
            auth_service.register(
                RegistrationRequest(
                    username="shortpw",
                    email="short@example.com",
                    password="abc",
                )
            )

    def test_login_returns_auth_result(self, auth_service: AuthService) -> None:
        auth_service.register(
            RegistrationRequest(
                username="loginuser",
                email="login@example.com",
                password="LoginPass1!",
            )
        )
        result = auth_service.login(Credentials("loginuser", "LoginPass1!"))
        assert result.token
        assert result.user_id is not None
        assert result.username == "loginuser"

    def test_login_wrong_password_raises(self, auth_service: AuthService) -> None:
        auth_service.register(
            RegistrationRequest(
                username="wpuser",
                email="wp@example.com",
                password="CorrectPass1!",
            )
        )
        with pytest.raises(AuthError):
            auth_service.login(Credentials("wpuser", "WrongPass"))

    def test_login_unknown_user_raises(self, auth_service: AuthService) -> None:
        with pytest.raises(AuthError):
            auth_service.login(Credentials("nobody", "anything"))

    def test_validate_token_returns_payload(self, auth_service: AuthService) -> None:
        auth_service.register(
            RegistrationRequest(
                username="tokenuser",
                email="token@example.com",
                password="TokenPass1!",
            )
        )
        result = auth_service.login(Credentials("tokenuser", "TokenPass1!"))
        tp = auth_service.validate_token(result.token)
        assert isinstance(tp, TokenPayload)
        assert tp.user_id == result.user_id

    def test_change_password_succeeds(self, auth_service: AuthService) -> None:
        user = auth_service.register(
            RegistrationRequest(
                username="changepw",
                email="changepw@example.com",
                password="OldPass1!",
            )
        )
        auth_service.change_password(user.id, "OldPass1!", "NewPass1!")
        # Should be able to log in with new password
        result = auth_service.login(Credentials("changepw", "NewPass1!"))
        assert result.token


# ---------------------------------------------------------------------------
# Role-based policies
# ---------------------------------------------------------------------------


class TestPolicies:
    def test_role_level_ordering(self) -> None:
        assert role_level("guest") < role_level("member")
        assert role_level("member") < role_level("manager")
        assert role_level("manager") < role_level("admin")

    def test_has_role_exact(self) -> None:
        assert has_role("admin", "admin") is True
        assert has_role("member", "member") is True

    def test_has_role_higher(self) -> None:
        assert has_role("admin", "member") is True
        assert has_role("manager", "member") is True

    def test_has_role_lower(self) -> None:
        assert has_role("member", "admin") is False
        assert has_role("guest", "manager") is False

    def test_can_create_user_admin_only(self) -> None:
        assert can_create_user("admin") is True
        assert can_create_user("manager") is False
        assert can_create_user("member") is False

    def test_can_create_project_members(self) -> None:
        assert can_create_project("member") is True
        assert can_create_project("admin") is True
        assert can_create_project("guest") is False

    def test_can_view_audit_log(self) -> None:
        assert can_view_audit_log("manager") is True
        assert can_view_audit_log("admin") is True
        assert can_view_audit_log("member") is False

    def test_require_role_raises(self) -> None:
        with pytest.raises(Exception):
            require_role("member", "admin", "create user")
