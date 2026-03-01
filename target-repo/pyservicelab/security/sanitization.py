"""Input sanitization utilities.

These helpers strip or encode potentially dangerous content from user-supplied
strings.  They are intended as a first line of defence; domain validation
should still be applied afterwards.
"""
from __future__ import annotations

import re
import unicodedata


# ---------------------------------------------------------------------------
# General sanitization
# ---------------------------------------------------------------------------


def sanitize_string(text: str, max_length: int = 2000) -> str:
    """Strip control characters and limit length.

    Preserves printable ASCII, common Unicode text, and standard whitespace
    (spaces, newlines, tabs).  Null bytes and other C0/C1 control characters
    are removed.

    Args:
        text: The raw input string.
        max_length: Maximum allowed length after sanitization.

    Returns:
        A sanitized version of *text*, truncated to *max_length*.
    """
    # Remove null bytes and control characters (keep tab, LF, CR)
    cleaned = "".join(
        ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\t\n\r"
    )
    return cleaned[:max_length]


def sanitize_html(text: str) -> str:
    """Remove all HTML tags from *text*.

    This is a simple regex-based stripper and is not a full HTML sanitizer.
    For user-supplied rich text, a dedicated library should be used in
    production.
    """
    return re.sub(r"<[^>]+>", "", text)


def sanitize_filename(name: str) -> str:
    """Convert *name* to a safe filename by replacing problematic characters.

    Replaces path separators, null bytes, and other shell-special characters
    with underscores.  The result is limited to 255 characters.
    """
    # Normalize unicode
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    # Remove path-traversal sequences (.. and longer dot runs) before anything else
    name = re.sub(r"\.{2,}", "", name)
    # Replace dangerous characters
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    # Remove leading/trailing dots and spaces
    name = name.strip(". ")
    # Collapse repeated underscores
    name = re.sub(r"_+", "_", name)
    return name[:255] or "unnamed"


def sanitize_sql_like(text: str) -> str:
    """Escape LIKE wildcard characters (``%``, ``_``, ``\\``) in *text*.

    Use this when building SQL LIKE patterns from user input so that the
    characters are treated literally rather than as wildcards.
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def sanitize_identifier(name: str) -> str:
    """Return a safe SQL identifier (alphanumeric and underscores only).

    Raises:
        ValueError: If the cleaned identifier is empty.
    """
    cleaned = re.sub(r"[^\w]", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if not cleaned:
        raise ValueError(f"Cannot sanitize '{name}' to a valid identifier")
    return cleaned
