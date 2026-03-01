"""Custom exceptions for PyServiceLab.

All application-specific errors inherit from ``PyServiceLabError`` so callers
can catch the base type when needed, or a specific subtype for fine-grained
handling.
"""


class PyServiceLabError(Exception):
    """Base exception for all PyServiceLab errors."""


class NotFoundError(PyServiceLabError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource_type: str, resource_id: str | int) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} with id '{resource_id}' not found")


class ValidationError(PyServiceLabError):
    """Raised when input data fails validation rules."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"Validation error on '{field}': {message}")


class AuthError(PyServiceLabError):
    """Raised when authentication credentials are invalid or missing."""


class AccessDeniedError(PyServiceLabError):
    """Raised when a user lacks permission to perform an action."""

    def __init__(self, action: str, resource: str) -> None:
        self.action = action
        self.resource = resource
        super().__init__(f"Permission denied: cannot '{action}' on '{resource}'")


class DuplicateError(PyServiceLabError):
    """Raised when a uniqueness constraint is violated."""

    def __init__(self, field: str, value: str) -> None:
        self.field = field
        self.value = value
        super().__init__(f"Duplicate value for '{field}': '{value}' already exists")


class ConfigError(PyServiceLabError):
    """Raised when configuration is missing or invalid."""


class DatabaseError(PyServiceLabError):
    """Raised when a low-level database operation fails."""


class SecurityError(PyServiceLabError):
    """Raised when a security check detects a violation."""


class TokenError(PyServiceLabError):
    """Raised when a token is invalid, expired, or tampered with."""
