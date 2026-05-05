"""Password hashing using PBKDF2-HMAC-SHA256 (stdlib only).

Hashes are stored as ``<hex-salt>$<hex-digest>`` so the salt can be
retrieved for verification without a separate lookup.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 100_000
_HASH_NAME = "sha256"
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash *password* with a random salt using PBKDF2-HMAC-SHA256.

    Returns a string in the form ``<salt_hex>$<digest_hex>``.
    """
    salt = secrets.token_hex(_SALT_BYTES)
    digest = _derive(password, salt)
    return f"{salt}${digest}"


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches the stored *hashed* value.

    Uses :func:`hmac.compare_digest` to prevent timing attacks.
    """
    try:
        salt, stored_digest = hashed.split("$", 1)
    except ValueError:
        return False

    candidate = _derive(password, salt)
    return hmac.compare_digest(candidate, stored_digest)


def _derive(password: str, salt: str) -> str:
    """Return the hex-encoded PBKDF2 digest for *password* and *salt*."""
    raw = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _ITERATIONS,
    )
    return raw.hex()


def needs_rehash(hashed: str) -> bool:
    """Return True if the stored hash uses outdated parameters.

    Currently always returns False – a hook for future migration logic.
    """
    return False
