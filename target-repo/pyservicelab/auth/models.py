"""Authentication-specific data models.

These are value objects used by the auth service and are distinct from the
domain ``User`` model.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Credentials:
    """Raw login credentials submitted by a client."""

    username: str
    password: str


@dataclass
class TokenPayload:
    """Decoded content of an authentication token.

    Attributes:
        user_id: Primary key of the authenticated user.
        role: Role string of the authenticated user.
        issued_at: UTC datetime when the token was issued.
        expires_at: UTC datetime when the token expires.
    """

    user_id: int
    role: str
    issued_at: datetime
    expires_at: datetime

    @classmethod
    def from_dict(cls, data: dict) -> "TokenPayload":
        """Construct from a decoded token payload dict."""
        from datetime import timezone

        def _from_ts(ts: float) -> datetime:
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)

        return cls(
            user_id=int(data["sub"]),
            role=str(data["role"]),
            issued_at=_from_ts(data["iat"]),
            expires_at=_from_ts(data["exp"]),
        )

    def is_expired(self) -> bool:
        """Return True if the token is past its expiry time."""
        from pyservicelab.core.time import utcnow

        return utcnow() > self.expires_at

    def to_dict(self) -> dict:
        """Serialize to a plain dict."""
        return {
            "user_id": self.user_id,
            "role": self.role,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass
class AuthResult:
    """Result returned by a successful authentication attempt.

    Attributes:
        token: Signed authentication token string.
        user_id: ID of the authenticated user.
        username: Username of the authenticated user.
        role: Role of the authenticated user.
        expires_at: UTC expiry datetime of the token.
    """

    token: str
    user_id: int
    username: str
    role: str
    expires_at: datetime

    def to_dict(self) -> dict:
        """Serialize to a plain dict."""
        return {
            "token": self.token,
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass
class RegistrationRequest:
    """Data required to register a new user.

    Attributes:
        username: Desired username.
        email: User's email address.
        password: Plaintext password (will be hashed before storage).
        role: Requested role (may be overridden by policy).
    """

    username: str
    email: str
    password: str
    role: str = "member"
