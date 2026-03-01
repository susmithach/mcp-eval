"""Authentication service – registration, login, and token validation."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pyservicelab.auth.hashing import hash_password, verify_password
from pyservicelab.auth.models import AuthResult, Credentials, RegistrationRequest, TokenPayload
from pyservicelab.auth.tokens import decode_token, generate_token
from pyservicelab.core.errors import AuthError, DuplicateError, TokenError
from pyservicelab.core.logging import ServiceLogger
from pyservicelab.core.time import add_seconds, utcnow
from pyservicelab.core.validation import validate_email, validate_password, validate_username
from pyservicelab.db.user_repo import UserRepository
from pyservicelab.domain.user import User, UserRole, UserStatus

_log = ServiceLogger(__name__)


class AuthService:
    """Handles user registration, login, and token lifecycle.

    Args:
        user_repo: Repository for user persistence.
        secret_key: HMAC secret used for token signing.
        token_expiry_seconds: Token lifetime in seconds (default: 3600).
    """

    def __init__(
        self,
        user_repo: UserRepository,
        secret_key: str,
        token_expiry_seconds: int = 3600,
    ) -> None:
        self._repo = user_repo
        self._secret = secret_key
        self._expiry = token_expiry_seconds

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, request: RegistrationRequest) -> User:
        """Register a new user account.

        Validates inputs, checks uniqueness, hashes the password, and
        persists the user.

        Args:
            request: Registration details (username, email, password, role).

        Returns:
            The newly created :class:`~pyservicelab.domain.user.User`.

        Raises:
            ValidationError: If any field fails validation.
            DuplicateError: If username or email is already taken.
        """
        username = validate_username(request.username)
        email = validate_email(request.email)
        validate_password(request.password)

        if self._repo.username_exists(username):
            raise DuplicateError("username", username)
        if self._repo.email_exists(email):
            raise DuplicateError("email", email)

        try:
            role = UserRole(request.role)
        except ValueError:
            role = UserRole.MEMBER

        now = utcnow()
        user = User(
            id=None,
            username=username,
            email=email,
            password_hash=hash_password(request.password),
            role=role,
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        created = self._repo.create(user)
        _log.log_operation(
            f"User '{username}' registered",
            operation="auth.register",
            entity_id=created.id,
            user_id=None,
        )
        return created

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, credentials: Credentials) -> AuthResult:
        """Authenticate a user and return a signed token.

        Args:
            credentials: Username and plaintext password.

        Returns:
            :class:`~pyservicelab.auth.models.AuthResult` with token details.

        Raises:
            AuthError: If the username does not exist or the password is wrong.
            AuthError: If the account is not active.
        """
        user = self._repo.get_by_username(credentials.username)
        if user is None:
            raise AuthError("Invalid username or password")

        if not verify_password(credentials.password, user.password_hash):
            raise AuthError("Invalid username or password")

        if not user.is_active():
            raise AuthError(f"Account '{user.username}' is not active")

        # Update last login timestamp
        user.last_login = utcnow()
        user.updated_at = utcnow()
        self._repo.update(user)

        token = generate_token(
            user_id=user.id,  # type: ignore[arg-type]
            role=user.role.value,
            secret=self._secret,
            expiry_seconds=self._expiry,
        )
        expires_at = add_seconds(utcnow(), self._expiry)

        _log.log_operation(
            f"User '{user.username}' logged in",
            operation="auth.login",
            entity_id=user.id,
            user_id=user.id,
        )

        return AuthResult(
            token=token,
            user_id=user.id,  # type: ignore[arg-type]
            username=user.username,
            role=user.role.value,
            expires_at=expires_at,
        )

    # ------------------------------------------------------------------
    # Token validation
    # ------------------------------------------------------------------

    def validate_token(self, token: str) -> TokenPayload:
        """Decode and validate *token*, returning its payload.

        Raises:
            TokenError: If the token is invalid or expired.
        """
        payload = decode_token(token, self._secret)
        return TokenPayload.from_dict(payload)

    def get_user_from_token(self, token: str) -> Optional[User]:
        """Return the user identified by *token*, or None if token is invalid."""
        try:
            tp = self.validate_token(token)
        except TokenError:
            return None
        return self._repo.get_by_id(tp.user_id)

    # ------------------------------------------------------------------
    # Password management
    # ------------------------------------------------------------------

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change a user's password after verifying the current one.

        Raises:
            AuthError: If the user is not found or current password is wrong.
            ValidationError: If the new password is too short.
        """
        user = self._repo.get_by_id(user_id)
        if user is None:
            raise AuthError("User not found")

        if not verify_password(current_password, user.password_hash):
            raise AuthError("Current password is incorrect")

        validate_password(new_password)
        user.password_hash = hash_password(new_password)
        user.updated_at = utcnow()
        self._repo.update(user)
        _log.log_operation(
            f"Password changed for user {user_id}",
            operation="auth.change_password",
            entity_id=user_id,
            user_id=user_id,
        )
