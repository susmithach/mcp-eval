"""HMAC-signed token generation and validation (stdlib only).

Tokens are structured as ``<base64url-payload>.<hex-signature>`` where the
payload is a JSON object containing the user ID, role, and expiry.

No external JWT library is required.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from pyservicelab.core.errors import TokenError


def _encode_payload(payload: dict) -> str:
    """Base64url-encode a JSON payload (no padding)."""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_payload(encoded: str) -> dict:
    """Decode a base64url-encoded JSON payload."""
    # Restore padding
    padding = 4 - (len(encoded) % 4)
    padded = encoded + ("=" * (padding % 4))
    raw = base64.urlsafe_b64decode(padded)
    return json.loads(raw.decode("utf-8"))


def _sign(data: str, secret: str) -> str:
    """Return an HMAC-SHA256 hex signature for *data*."""
    return hmac.new(
        secret.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_token(
    user_id: int,
    role: str,
    secret: str,
    expiry_seconds: int = 3600,
) -> str:
    """Create a signed token for *user_id* with role *role*.

    Args:
        user_id: The authenticated user's primary key.
        role: The user's role string (e.g. ``"admin"``).
        secret: HMAC signing secret.
        expiry_seconds: Token lifetime in seconds from *now*.

    Returns:
        A ``<payload>.<signature>`` token string.
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + expiry_seconds,
    }
    encoded = _encode_payload(payload)
    signature = _sign(encoded, secret)
    return f"{encoded}.{signature}"


def decode_token(token: str, secret: str) -> dict:
    """Decode and verify *token*, returning its payload.

    Args:
        token: The token string to decode.
        secret: The HMAC signing secret used when generating the token.

    Returns:
        Payload dict containing ``sub`` (user_id), ``role``, ``iat``, ``exp``.

    Raises:
        TokenError: If the token is malformed, has an invalid signature,
            or has expired.
    """
    try:
        encoded, signature = token.rsplit(".", 1)
    except ValueError:
        raise TokenError("Malformed token: missing signature separator")

    expected = _sign(encoded, secret)
    if not hmac.compare_digest(expected, signature):
        raise TokenError("Token signature is invalid")

    try:
        payload = _decode_payload(encoded)
    except Exception as exc:
        raise TokenError(f"Token payload could not be decoded: {exc}") from exc

    if payload.get("exp", 0) < int(time.time()):
        raise TokenError("Token has expired")

    return payload


def is_token_valid(token: str, secret: str) -> bool:
    """Return True if *token* is valid and not expired; False otherwise."""
    try:
        decode_token(token, secret)
        return True
    except TokenError:
        return False


def extract_user_id(token: str, secret: str) -> int:
    """Extract and return the user ID from a valid token.

    Raises:
        TokenError: If the token is invalid.
    """
    payload = decode_token(token, secret)
    return int(payload["sub"])
