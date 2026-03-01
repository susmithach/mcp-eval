"""Date and time utilities for PyServiceLab.

All functions operate on naïve UTC datetimes to keep the codebase simple
and free of timezone-conversion edge cases.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Current time
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    """Return the current UTC datetime (naïve, no tzinfo)."""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Parsing and formatting
# ---------------------------------------------------------------------------


def parse_iso(value: str) -> Optional[datetime]:
    """Parse an ISO 8601 datetime string; return None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def format_iso(dt: datetime) -> str:
    """Format *dt* as an ISO 8601 string."""
    return dt.isoformat()


def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    """Format *dt* as a date string (default: YYYY-MM-DD)."""
    return dt.strftime(fmt)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format *dt* as a human-readable datetime string."""
    return dt.strftime(fmt)


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------


def add_seconds(dt: datetime, seconds: int) -> datetime:
    """Return *dt* shifted forward by *seconds*."""
    return dt + timedelta(seconds=seconds)


def add_days(dt: datetime, days: int) -> datetime:
    """Return *dt* shifted forward by *days*."""
    return dt + timedelta(days=days)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def is_past(dt: datetime, reference: Optional[datetime] = None) -> bool:
    """Return True if *dt* is before *reference* (default: utcnow)."""
    return dt < (reference or utcnow())


def is_future(dt: datetime, reference: Optional[datetime] = None) -> bool:
    """Return True if *dt* is after *reference* (default: utcnow)."""
    return dt > (reference or utcnow())


def seconds_until(dt: datetime, reference: Optional[datetime] = None) -> float:
    """Return the number of seconds from *reference* until *dt*."""
    return (dt - (reference or utcnow())).total_seconds()


def seconds_since(dt: datetime, reference: Optional[datetime] = None) -> float:
    """Return the number of seconds elapsed since *dt* as of *reference*."""
    return ((reference or utcnow()) - dt).total_seconds()


# ---------------------------------------------------------------------------
# Humanisation
# ---------------------------------------------------------------------------


def human_readable_duration(seconds: float) -> str:
    """Convert a duration in *seconds* to a compact human-readable string.

    Examples::

        human_readable_duration(45)     == "45s"
        human_readable_duration(125)    == "2m 5s"
        human_readable_duration(3700)   == "1h 1m"
        human_readable_duration(90000)  == "1d 1h"
    """
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    if seconds < 86400:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    return f"{days}d {hours}h"
