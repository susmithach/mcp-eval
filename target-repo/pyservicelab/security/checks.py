"""Security check helpers – pattern detection for common attack vectors.

These are lightweight heuristic checks and are **not** a substitute for
parameterised queries, output encoding, and other defence-in-depth measures.
"""
from __future__ import annotations

import re

from pyservicelab.core.errors import SecurityError

# ---------------------------------------------------------------------------
# SQL injection detection
# ---------------------------------------------------------------------------

_SQL_INJECTION_PATTERNS = [
    r"(?i)\b(union\s+select|insert\s+into|drop\s+table|delete\s+from|update\s+\w+\s+set)\b",
    r"(?i)(--|;|/\*|\*/|xp_|sp_)",
    r"(?i)\b(or|and)\s+[\'\"]?\d+[\'\"]?\s*=\s*[\'\"]?\d+",
    r"(?i)sleep\s*\(",
    r"(?i)benchmark\s*\(",
]

_SQL_PATTERNS_COMPILED = [re.compile(p) for p in _SQL_INJECTION_PATTERNS]


def has_sql_injection(text: str) -> bool:
    """Return True if *text* contains patterns typical of SQL injection."""
    return any(pattern.search(text) for pattern in _SQL_PATTERNS_COMPILED)


# ---------------------------------------------------------------------------
# XSS detection
# ---------------------------------------------------------------------------

_XSS_PATTERNS = [
    r"(?i)<script[^>]*>",
    r"(?i)javascript\s*:",
    r"(?i)on\w+\s*=",           # onclick=, onerror=, etc.
    r"(?i)<\s*iframe",
    r"(?i)<\s*img[^>]+src\s*=",
    r"(?i)expression\s*\(",
    r"(?i)eval\s*\(",
]

_XSS_PATTERNS_COMPILED = [re.compile(p) for p in _XSS_PATTERNS]


def has_xss(text: str) -> bool:
    """Return True if *text* contains patterns typical of XSS attacks."""
    return any(pattern.search(text) for pattern in _XSS_PATTERNS_COMPILED)


# ---------------------------------------------------------------------------
# Path traversal detection
# ---------------------------------------------------------------------------


def has_path_traversal(path: str) -> bool:
    """Return True if *path* contains path-traversal sequences."""
    dangerous = ["..", "~", "%2e", "%2f", "%5c", "\x00", "//"]
    lower = path.lower()
    return any(d in lower for d in dangerous)


# ---------------------------------------------------------------------------
# Enforcement helpers
# ---------------------------------------------------------------------------


def assert_no_sql_injection(text: str, field_name: str = "input") -> None:
    """Raise :class:`SecurityError` if *text* looks like SQL injection.

    Args:
        text: The user-supplied string to check.
        field_name: Label for the field in the error message.

    Raises:
        SecurityError: If a SQL injection pattern is detected.
    """
    if has_sql_injection(text):
        raise SecurityError(f"Potential SQL injection detected in '{field_name}'")


def assert_no_xss(text: str, field_name: str = "input") -> None:
    """Raise :class:`SecurityError` if *text* looks like an XSS payload.

    Raises:
        SecurityError: If an XSS pattern is detected.
    """
    if has_xss(text):
        raise SecurityError(f"Potential XSS detected in '{field_name}'")


def assert_safe_path(path: str, field_name: str = "path") -> None:
    """Raise :class:`SecurityError` if *path* contains traversal sequences.

    Raises:
        SecurityError: If a path traversal pattern is detected.
    """
    if has_path_traversal(path):
        raise SecurityError(f"Path traversal attempt detected in '{field_name}'")


def sanitize_and_check(text: str, field_name: str = "input") -> str:
    """Run all security checks on *text* and return it unchanged on success.

    Raises:
        SecurityError: If any check fails.
    """
    assert_no_sql_injection(text, field_name)
    assert_no_xss(text, field_name)
    return text
