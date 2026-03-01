"""Path-traversal protection utilities.

All file-system paths produced by user input should go through these helpers
before being opened or passed to OS-level calls.
"""
from __future__ import annotations

from pathlib import Path


def is_safe_path(base: Path, target: Path) -> bool:
    """Return True if *target* is inside *base* (no path traversal).

    Both paths are resolved to absolute form before comparison so that
    ``../`` components cannot escape the base directory.

    Args:
        base: The trusted root directory.
        target: The path to validate (may be absolute or relative).

    Returns:
        True if *target* resolves to a location within *base*.
    """
    try:
        base_resolved = base.resolve()
        target_resolved = target.resolve()
        target_resolved.relative_to(base_resolved)
        return True
    except ValueError:
        return False


def safe_join(base: str, *parts: str) -> Path:
    """Join *parts* onto *base* and validate the result is within *base*.

    Args:
        base: The trusted root directory (as a string).
        *parts: Path components to join.

    Returns:
        A :class:`pathlib.Path` that is guaranteed to be within *base*.

    Raises:
        ValueError: If the joined path would escape *base*.
    """
    base_path = Path(base).resolve()
    candidate = base_path.joinpath(*parts)
    if not is_safe_path(base_path, candidate):
        raise ValueError(
            f"Path traversal detected: '{candidate}' is outside '{base_path}'"
        )
    return candidate


def has_traversal_attempt(raw: str) -> bool:
    """Return True if *raw* contains obvious path-traversal patterns.

    This is a quick heuristic check; use :func:`is_safe_path` for full
    validation.
    """
    suspicious = ["..", "~", "%2e%2e", "%2F", "%5C", "\x00"]
    raw_lower = raw.lower()
    return any(pattern in raw_lower for pattern in suspicious)


def normalize_path(raw: str, base: str) -> Path:
    """Normalize *raw* relative to *base*, raising on traversal.

    Convenience wrapper around :func:`safe_join`.
    """
    if has_traversal_attempt(raw):
        raise ValueError(f"Potential path traversal in: '{raw}'")
    return safe_join(base, raw)
