"""Configuration loading and composition.

:class:`AppConfig` bundles :class:`~pyservicelab.config.settings.Settings`
and :class:`~pyservicelab.config.feature_flags.FeatureFlags` into a single
object that can be passed through the application.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyservicelab.config.feature_flags import FeatureFlags
from pyservicelab.config.settings import Settings
from pyservicelab.core.errors import ConfigError


@dataclass
class AppConfig:
    """Top-level application configuration.

    Attributes:
        settings: Core application settings.
        feature_flags: Runtime feature toggles.
    """

    settings: Settings
    feature_flags: FeatureFlags

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration entirely from environment variables."""
        settings = Settings.from_env()
        settings.validate()
        feature_flags = FeatureFlags.from_env()
        return cls(settings=settings, feature_flags=feature_flags)

    @classmethod
    def load_from_file(cls, path: str) -> "AppConfig":
        """Load configuration from a JSON file, then merge into environment.

        The file may contain ``settings`` and/or ``feature_flags`` keys whose
        values are dicts of variable-name → value pairs.  Values are only
        applied if the corresponding environment variable is **not** already
        set (``os.environ.setdefault``).

        Raises:
            ConfigError: If the file is missing or contains invalid JSON.
        """
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigError(f"Config file not found: {path}")

        try:
            with config_path.open() as f:
                data: dict = json.load(f)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in config file '{path}': {exc}") from exc

        for key, value in data.get("settings", {}).items():
            os.environ.setdefault(f"PYSERVICELAB_{key.upper()}", str(value))

        for key, value in data.get("feature_flags", {}).items():
            os.environ.setdefault(f"FEATURE_{key.upper()}", str(value))

        return cls.load()

    @classmethod
    def for_testing(cls, db_path: str = ":memory:") -> "AppConfig":
        """Return a minimal configuration suitable for unit tests."""
        settings = Settings(
            db_path=db_path,
            secret_key="test-secret-key-for-testing",
            token_expiry_seconds=3600,
            log_level="WARNING",
            debug=True,
            max_login_attempts=5,
            admin_email="admin@test.example.com",
            app_name="PyServiceLab-Test",
            version="0.1.0",
        )
        feature_flags = FeatureFlags(
            enable_audit_log=True,
            enable_token_refresh=True,
        )
        return cls(settings=settings, feature_flags=feature_flags)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        """Return the full configuration as a nested dict."""
        return {
            "settings": self.settings.as_dict(),
            "feature_flags": self.feature_flags.as_dict(),
        }
