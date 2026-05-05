"""Text-processing utilities for PyServiceLab."""
from __future__ import annotations

import re
import unicodedata


# ---------------------------------------------------------------------------
# Slugification
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Convert *text* to a URL-safe ASCII slug.

    Example::

        slugify("Hello World!") == "hello-world"
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s\-]", "", text)
    text = re.sub(r"[\s_\-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


# ---------------------------------------------------------------------------
# Truncation / wrapping
# ---------------------------------------------------------------------------


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate *text* to *max_length* characters, appending *suffix* if cut."""
    if len(text) <= max_length:
        return text
    cut = max_length - len(suffix)
    return text[:cut] + suffix


def word_wrap(text: str, width: int = 80) -> str:
    """Hard-wrap *text* to at most *width* characters per line."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip() if current else word
    if current:
        lines.append(current)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace into a single space and strip edges."""
    return re.sub(r"\s+", " ", text.strip())


def title_case(text: str) -> str:
    """Return *text* in title case."""
    return text.title()


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case.

    Example::

        camel_to_snake("MyClassName") == "my_class_name"
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase.

    Example::

        snake_to_camel("my_field_name") == "myFieldName"
    """
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


# ---------------------------------------------------------------------------
# Word / token helpers
# ---------------------------------------------------------------------------


def extract_words(text: str) -> list[str]:
    """Extract all word tokens (lowercase) from *text*."""
    return re.findall(r"\b\w+\b", text.lower())


def count_words(text: str) -> int:
    """Count the number of word tokens in *text*."""
    return len(extract_words(text))


def format_list(items: list[str], conjunction: str = "and") -> str:
    """Format a list as natural-language prose.

    Examples::

        format_list(["a"])             == "a"
        format_list(["a", "b"])        == "a and b"
        format_list(["a", "b", "c"])   == "a, b, and c"
    """
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return ", ".join(items[:-1]) + f", {conjunction} {items[-1]}"


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------


def contains_html(text: str) -> bool:
    """Return True if *text* contains any HTML tags."""
    return bool(re.search(r"<[a-zA-Z][^>]*>", text))


def strip_html(text: str) -> str:
    """Remove all HTML tags from *text*."""
    return re.sub(r"<[^>]+>", "", text)
