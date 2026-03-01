"""Tests for the configuration layer."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from pyservicelab.config.feature_flags import FeatureFlags
from pyservicelab.config.loaders import AppConfig
from pyservicelab.config.settings import Settings
from pyservicelab.core.errors import ConfigError


class TestSettings:
    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Clear any PYSERVICELAB_ env vars
        for key in list(os.environ):
            if key.startswith("PYSERVICELAB_"):
                monkeypatch.delenv(key, raising=False)
        settings = Settings.from_env()
        assert settings.db_path == ":memory:"
        assert settings.log_level == "INFO"
        assert settings.debug is False

    def test_from_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYSERVICELAB_DB", "/tmp/test.db")
        monkeypatch.setenv("PYSERVICELAB_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("PYSERVICELAB_DEBUG", "true")
        settings = Settings.from_env()
        assert settings.db_path == "/tmp/test.db"
        assert settings.log_level == "DEBUG"
        assert settings.debug is True

    def test_validate_passes_defaults(self) -> None:
        settings = Settings(
            db_path=":memory:",
            secret_key="a-secret-key-that-is-long-enough",
            token_expiry_seconds=3600,
            log_level="INFO",
            debug=False,
            max_login_attempts=5,
            admin_email="a@b.com",
            app_name="Test",
            version="0.1.0",
        )
        settings.validate()  # should not raise

    def test_validate_short_secret_raises(self) -> None:
        settings = Settings(
            db_path=":memory:",
            secret_key="tooshort",  # < 16 chars
            token_expiry_seconds=3600,
            log_level="INFO",
            debug=False,
            max_login_attempts=5,
            admin_email="a@b.com",
            app_name="Test",
            version="0.1.0",
        )
        with pytest.raises(ConfigError):
            settings.validate()

    def test_validate_invalid_log_level_raises(self) -> None:
        settings = Settings(
            db_path=":memory:",
            secret_key="a-secret-key-that-is-long-enough",
            token_expiry_seconds=3600,
            log_level="VERBOSE",
            debug=False,
            max_login_attempts=5,
            admin_email="a@b.com",
            app_name="Test",
            version="0.1.0",
        )
        with pytest.raises(ConfigError):
            settings.validate()

    def test_validate_zero_expiry_raises(self) -> None:
        settings = Settings(
            db_path=":memory:",
            secret_key="a-secret-key-that-is-long-enough",
            token_expiry_seconds=0,
            log_level="INFO",
            debug=False,
            max_login_attempts=5,
            admin_email="a@b.com",
            app_name="Test",
            version="0.1.0",
        )
        with pytest.raises(ConfigError):
            settings.validate()

    def test_as_dict_masks_secret(self) -> None:
        settings = Settings(
            db_path=":memory:",
            secret_key="super-secret-value",
            token_expiry_seconds=3600,
            log_level="INFO",
            debug=False,
            max_login_attempts=5,
            admin_email="a@b.com",
            app_name="Test",
            version="0.1.0",
        )
        d = settings.as_dict()
        assert d["secret_key"] == "***"

    def test_is_production_false_for_memory_db(self) -> None:
        settings = Settings(
            db_path=":memory:",
            secret_key="secret-key-long-enough",
            token_expiry_seconds=3600,
            log_level="INFO",
            debug=False,
            max_login_attempts=5,
            admin_email="a@b.com",
            app_name="Test",
            version="0.1.0",
        )
        assert settings.is_production() is False


class TestFeatureFlags:
    def test_defaults(self) -> None:
        flags = FeatureFlags()
        assert flags.enable_audit_log is True
        assert flags.enable_rate_limiting is False

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FEATURE_RATE_LIMITING", "true")
        monkeypatch.setenv("FEATURE_AUDIT_LOG", "false")
        flags = FeatureFlags.from_env()
        assert flags.enable_rate_limiting is True
        assert flags.enable_audit_log is False

    def test_is_enabled(self) -> None:
        flags = FeatureFlags(enable_audit_log=True, enable_rate_limiting=False)
        assert flags.is_enabled("enable_audit_log") is True
        assert flags.is_enabled("enable_rate_limiting") is False

    def test_is_enabled_unknown_raises(self) -> None:
        flags = FeatureFlags()
        with pytest.raises(AttributeError):
            flags.is_enabled("nonexistent_flag")

    def test_enabled_flags(self) -> None:
        flags = FeatureFlags(enable_audit_log=True, enable_rate_limiting=False)
        enabled = flags.enabled_flags()
        assert "enable_audit_log" in enabled
        assert "enable_rate_limiting" not in enabled

    def test_disabled_flags(self) -> None:
        flags = FeatureFlags(enable_rate_limiting=False)
        disabled = flags.disabled_flags()
        assert "enable_rate_limiting" in disabled

    def test_as_dict(self) -> None:
        flags = FeatureFlags()
        d = flags.as_dict()
        assert isinstance(d, dict)
        assert "enable_audit_log" in d


class TestAppConfig:
    def test_for_testing(self) -> None:
        config = AppConfig.for_testing()
        assert config.settings.db_path == ":memory:"
        assert config.settings.debug is True

    def test_load(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYSERVICELAB_SECRET", "a-secret-key-that-is-long-enough")
        config = AppConfig.load()
        assert config.settings is not None
        assert config.feature_flags is not None

    def test_as_dict_structure(self) -> None:
        config = AppConfig.for_testing()
        d = config.as_dict()
        assert "settings" in d
        assert "feature_flags" in d

    def test_load_from_file(self) -> None:
        data = {
            "settings": {
                "app_name": "TestApp",
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name

        try:
            # Clear env so our file values are used
            config = AppConfig.load_from_file(path)
            assert config is not None
        finally:
            os.unlink(path)

    def test_load_from_missing_file_raises(self) -> None:
        with pytest.raises(ConfigError):
            AppConfig.load_from_file("/nonexistent/path/config.json")
