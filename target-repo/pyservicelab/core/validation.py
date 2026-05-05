"""Input validation helpers for PyServiceLab.

All validators raise :class:`~pyservicelab.core.errors.ValidationError` on
failure and return the (possibly normalised) value on success.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from pyservicelab.core.errors import ValidationError

# ---------------------------------------------------------------------------
# Compiled regular expressions
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{3,50}$")

MIN_PASSWORD_LENGTH = 8
MAX_FIELD_LENGTH = 2000


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_email(email: str) -> str:
    """Validate and normalise (lowercase) an email address.

    Raises:
        ValidationError: If the email is malformed.
    """
    email = email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValidationError("email", f"'{email}' is not a valid email address")
    return email


def validate_username(username: str) -> str:
    """Validate a username (3-50 alphanumeric chars, underscore, or hyphen).

    Raises:
        ValidationError: If the username does not meet requirements.
    """
    username = username.strip()
    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            "username",
            "Username must be 3-50 characters: letters, digits, underscores, or hyphens",
        )
    return username


def validate_password(password: str) -> None:
    """Validate password meets minimum length requirements.

    Raises:
        ValidationError: If the password is too short.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            "password",
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long",
        )


def validate_non_empty(value: str, field_name: str, max_length: int = MAX_FIELD_LENGTH) -> str:
    """Validate that a string field is non-empty and within length limits.

    Raises:
        ValidationError: If the value is blank or too long.
    """
    value = value.strip()
    if not value:
        raise ValidationError(field_name, f"'{field_name}' must not be empty")
    if len(value) > max_length:
        raise ValidationError(
            field_name, f"'{field_name}' exceeds maximum length of {max_length} characters"
        )
    return value


def validate_optional_str(
    value: Optional[str],
    field_name: str,
    max_length: int = MAX_FIELD_LENGTH,
) -> Optional[str]:
    """Validate an optional string field; returns None if empty.

    Raises:
        ValidationError: If the value is too long.
    """
    if value is None:
        return None
    value = value.strip()
    if len(value) > max_length:
        raise ValidationError(
            field_name, f"'{field_name}' exceeds maximum length of {max_length} characters"
        )
    return value or None


def validate_positive_int(value: Any, field_name: str) -> int:
    """Validate that *value* converts to a positive integer.

    Raises:
        ValidationError: If conversion fails or the value is not positive.
    """
    try:
        int_val = int(value)
    except (TypeError, ValueError):
        raise ValidationError(field_name, f"'{field_name}' must be a valid integer")
    if int_val <= 0:
        raise ValidationError(field_name, f"'{field_name}' must be greater than zero")
    return int_val


def validate_positive_float(value: Any, field_name: str) -> float:
    """Validate that *value* converts to a positive float.

    Raises:
        ValidationError: If conversion fails or the value is not positive.
    """
    try:
        float_val = float(value)
    except (TypeError, ValueError):
        raise ValidationError(field_name, f"'{field_name}' must be a valid number")
    if float_val <= 0:
        raise ValidationError(field_name, f"'{field_name}' must be greater than zero")
    return float_val


def validate_enum_value(value: str, field_name: str, valid_values: list[str]) -> str:
    """Validate that *value* is one of the allowed enum strings.

    Raises:
        ValidationError: If the value is not in the allowed set.
    """
    if value not in valid_values:
        raise ValidationError(
            field_name,
            f"'{value}' is not valid for '{field_name}'. "
            f"Allowed values: {', '.join(valid_values)}",
        )
    return value


def validate_id(value: Any, field_name: str = "id") -> int:
    """Validate a database record identifier (positive integer).

    Raises:
        ValidationError: If the value is not a positive integer.
    """
    return validate_positive_int(value, field_name)
