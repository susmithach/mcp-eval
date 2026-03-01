"""General-purpose utility functions for PyServiceLab."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Dictionary helpers
# ---------------------------------------------------------------------------


def deep_merge(base: dict, override: dict) -> dict:
    """Return a new dict that is *base* deep-merged with *override*.

    Nested dictionaries are merged recursively; all other values from
    *override* take precedence.
    """
    result: dict = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Navigate a nested dictionary safely, returning *default* on any miss."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def omit_keys(data: dict, keys: list[str]) -> dict:
    """Return a copy of *data* without the specified keys."""
    return {k: v for k, v in data.items() if k not in keys}


def filter_none(data: dict) -> dict:
    """Return a copy of *data* with all None-valued keys removed."""
    return {k: v for k, v in data.items() if v is not None}


# ---------------------------------------------------------------------------
# List helpers
# ---------------------------------------------------------------------------


def chunk_list(items: list, size: int) -> list[list]:
    """Split *items* into sublists of at most *size* elements."""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    return [items[i : i + size] for i in range(0, len(items), size)]


def flatten(nested: list[list]) -> list:
    """Flatten one level of nesting from a list of lists."""
    return [item for sublist in nested for item in sublist]


def unique(items: list) -> list:
    """Return *items* with duplicates removed, preserving order."""
    seen: set = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------


def serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Serialize a datetime to ISO 8601 string, or None if dt is None."""
    if dt is None:
        return None
    return dt.isoformat()


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 string to datetime, or None if value is falsy."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------


def hash_content(content: str) -> str:
    """Return the SHA-256 hex digest of *content* (UTF-8 encoded)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def mask_sensitive(value: str, visible: int = 4) -> str:
    """Mask a sensitive string, exposing only the last *visible* characters."""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def to_json(obj: Any, indent: int = 2) -> str:
    """Serialize *obj* to a JSON string, falling back to str() for unknowns."""
    return json.dumps(obj, default=str, indent=indent)


def from_json(text: str) -> Any:
    """Deserialize a JSON string."""
    return json.loads(text)
