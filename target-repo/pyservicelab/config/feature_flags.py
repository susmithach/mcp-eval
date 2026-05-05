"""Feature-flag support for enabling or disabling runtime behaviours.

Flags are loaded from environment variables and are purely boolean.  They can
be queried by name via :meth:`FeatureFlags.is_enabled`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


def _bool_flag(env_name: str, default: bool) -> bool:
    """Read a boolean feature flag from the environment."""
    raw = os.environ.get(env_name, str(default)).strip().lower()
    return raw in ("true", "1", "yes")


@dataclass
class FeatureFlags:
    """Collection of boolean feature flags.

    Attributes:
        enable_audit_log: Record audit entries for state-changing operations.
        enable_token_refresh: Allow tokens to be refreshed before expiry.
        enable_rate_limiting: Enforce rate limits on authentication endpoints.
        enable_email_verification: Require e-mail verification after registration.
        allow_anonymous_access: Allow unauthenticated read requests.
        enable_tracing: Attach trace spans to service operations.
        enable_debug_endpoints: Expose debug/diagnostic endpoints.
    """

    enable_audit_log: bool = True
    enable_token_refresh: bool = True
    enable_rate_limiting: bool = False
    enable_email_verification: bool = False
    allow_anonymous_access: bool = False
    enable_tracing: bool = False
    enable_debug_endpoints: bool = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        """Load feature flags from environment variables."""
        return cls(
            enable_audit_log=_bool_flag("FEATURE_AUDIT_LOG", True),
            enable_token_refresh=_bool_flag("FEATURE_TOKEN_REFRESH", True),
            enable_rate_limiting=_bool_flag("FEATURE_RATE_LIMITING", False),
            enable_email_verification=_bool_flag("FEATURE_EMAIL_VERIFY", False),
            allow_anonymous_access=_bool_flag("FEATURE_ANONYMOUS", False),
            enable_tracing=_bool_flag("FEATURE_TRACING", False),
            enable_debug_endpoints=_bool_flag("FEATURE_DEBUG_ENDPOINTS", False),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_enabled(self, flag_name: str) -> bool:
        """Return the boolean value of *flag_name*.

        Raises:
            AttributeError: If no flag with that name exists.
        """
        if not hasattr(self, flag_name):
            raise AttributeError(f"Unknown feature flag: '{flag_name}'")
        return bool(getattr(self, flag_name))

    def enabled_flags(self) -> list[str]:
        """Return the names of all currently enabled flags."""
        return [name for name, value in self.as_dict().items() if value]

    def disabled_flags(self) -> list[str]:
        """Return the names of all currently disabled flags."""
        return [name for name, value in self.as_dict().items() if not value]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dict of all flag names and their values."""
        return {
            "enable_audit_log": self.enable_audit_log,
            "enable_token_refresh": self.enable_token_refresh,
            "enable_rate_limiting": self.enable_rate_limiting,
            "enable_email_verification": self.enable_email_verification,
            "allow_anonymous_access": self.allow_anonymous_access,
            "enable_tracing": self.enable_tracing,
            "enable_debug_endpoints": self.enable_debug_endpoints,
        }
