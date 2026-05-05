"""Secret generation and comparison utilities.

Uses Python's :mod:`secrets` module for cryptographically strong randomness.
"""
from __future__ import annotations

import hmac
import secrets
import string


def generate_secret(n_bytes: int = 32) -> str:
    """Return *n_bytes* of cryptographically random data as a hex string."""
    return secrets.token_hex(n_bytes)


def generate_api_key(prefix: str = "psl") -> str:
    """Return a prefixed API key of the form ``<prefix>_<random-hex>``.

    The random portion is 32 bytes (64 hex chars), giving ~256 bits of entropy.
    """
    random_part = secrets.token_hex(32)
    return f"{prefix}_{random_part}"


def generate_otp(length: int = 6) -> str:
    """Return a numeric one-time password of *length* digits."""
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def generate_slug_token(length: int = 12) -> str:
    """Return a URL-safe random token using lowercase alphanumeric characters."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Equivalent to :func:`hmac.compare_digest` but accepts arbitrary strings.
    """
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def is_strong_secret(value: str, min_length: int = 32) -> bool:
    """Return True if *value* meets minimum strength requirements.

    Checks:
    - Length >= *min_length*
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    """
    if len(value) < min_length:
        return False
    has_upper = any(c.isupper() for c in value)
    has_lower = any(c.islower() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return has_upper and has_lower and has_digit
