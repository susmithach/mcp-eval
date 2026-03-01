"""Application settings loaded from environment variables with sane defaults.

Use :meth:`Settings.from_env` to obtain a populated instance at startup, then
pass it around the application rather than re-reading the environment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from pyservicelab.core.errors import ConfigError

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass
class Settings:
    """All application-wide configuration in one place.

    Attributes:
        db_path: SQLite database path (use ``:memory:`` for testing).
        secret_key: HMAC secret for token signing – must be ≥ 16 chars.
        token_expiry_seconds: Token lifetime in seconds.
        log_level: One of DEBUG / INFO / WARNING / ERROR / CRITICAL.
        debug: Enable verbose debug output.
        max_login_attempts: Lockout threshold (informational; not enforced by DB).
        admin_email: Default admin contact address.
        app_name: Display name of the application.
        version: Application version string.
    """

    db_path: str
    secret_key: str
    token_expiry_seconds: int
    log_level: str
    debug: bool
    max_login_attempts: int
    admin_email: str
    app_name: str
    version: str

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "Settings":
        """Build a Settings object from environment variables.

        Every variable falls back to a sensible default so the application
        starts without any configuration in development.
        """
        return cls(
            db_path=os.environ.get("PYSERVICELAB_DB", ":memory:"),
            secret_key=os.environ.get(
                "PYSERVICELAB_SECRET", "dev-secret-key-please-change"
            ),
            token_expiry_seconds=int(
                os.environ.get("PYSERVICELAB_TOKEN_EXPIRY", "3600")
            ),
            log_level=os.environ.get("PYSERVICELAB_LOG_LEVEL", "INFO"),
            debug=os.environ.get("PYSERVICELAB_DEBUG", "false").lower()
            in ("true", "1", "yes"),
            max_login_attempts=int(
                os.environ.get("PYSERVICELAB_MAX_ATTEMPTS", "5")
            ),
            admin_email=os.environ.get(
                "PYSERVICELAB_ADMIN_EMAIL", "admin@example.com"
            ),
            app_name=os.environ.get("PYSERVICELAB_APP_NAME", "PyServiceLab"),
            version="0.1.0",
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Raise :class:`~pyservicelab.core.errors.ConfigError` on invalid values."""
        if not self.secret_key or len(self.secret_key) < 16:
            raise ConfigError("secret_key must be at least 16 characters long")
        if self.token_expiry_seconds <= 0:
            raise ConfigError("token_expiry_seconds must be a positive integer")
        if self.max_login_attempts <= 0:
            raise ConfigError("max_login_attempts must be a positive integer")
        if self.log_level.upper() not in _VALID_LOG_LEVELS:
            raise ConfigError(
                f"Invalid log_level '{self.log_level}'. "
                f"Must be one of: {', '.join(sorted(_VALID_LOG_LEVELS))}"
            )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def as_dict(self) -> dict:
        """Return settings as a plain dict, masking the secret key."""
        return {
            "app_name": self.app_name,
            "version": self.version,
            "db_path": self.db_path,
            "secret_key": "***",
            "token_expiry_seconds": self.token_expiry_seconds,
            "log_level": self.log_level,
            "debug": self.debug,
            "max_login_attempts": self.max_login_attempts,
            "admin_email": self.admin_email,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_production(self) -> bool:
        """Return True if the settings look like a production configuration."""
        return not self.debug and self.db_path != ":memory:"
