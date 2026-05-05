"""Simple in-process request tracing for PyServiceLab.

Provides a lightweight span model (no external dependencies) suitable for
benchmarking and debugging.  Spans are stored in memory only.
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator, Optional


@dataclass
class Span:
    """A single traced operation."""

    trace_id: str
    span_id: str
    operation: str
    start_time: float
    end_time: Optional[float] = None
    tags: dict = field(default_factory=dict)
    error: Optional[str] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def duration_ms(self) -> Optional[float]:
        """Duration in milliseconds, or None if the span has not finished."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    @property
    def is_finished(self) -> bool:
        """True when the span has been closed."""
        return self.end_time is not None

    @property
    def is_error(self) -> bool:
        """True when the span recorded an error."""
        return self.error is not None

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def finish(self, error: Optional[str] = None) -> None:
        """Mark the span as complete, optionally recording an error."""
        self.end_time = time.monotonic()
        if error:
            self.error = error

    def set_tag(self, key: str, value: object) -> None:
        """Attach a key/value tag to the span."""
        self.tags[key] = value

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize span to a plain dictionary."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "tags": self.tags,
            "error": self.error,
        }


class Tracer:
    """Collects spans for a single process or test run."""

    def __init__(self) -> None:
        self._spans: list[Span] = []

    # ------------------------------------------------------------------
    # Span lifecycle
    # ------------------------------------------------------------------

    def start_span(
        self,
        operation: str,
        trace_id: Optional[str] = None,
        **tags: object,
    ) -> Span:
        """Create, record, and return a new open span."""
        span = Span(
            trace_id=trace_id or str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            operation=operation,
            start_time=time.monotonic(),
            tags=dict(tags),
        )
        self._spans.append(span)
        return span

    @contextmanager
    def trace(
        self,
        operation: str,
        trace_id: Optional[str] = None,
        **tags: object,
    ) -> Generator[Span, None, None]:
        """Context manager that automatically closes the span on exit.

        Any unhandled exception is recorded as the span error.
        """
        span = self.start_span(operation, trace_id=trace_id, **tags)
        try:
            yield span
        except Exception as exc:
            span.finish(error=str(exc))
            raise
        else:
            span.finish()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_spans(self) -> list[Span]:
        """Return a copy of all recorded spans."""
        return list(self._spans)

    def get_finished_spans(self) -> list[Span]:
        """Return only completed spans."""
        return [s for s in self._spans if s.is_finished]

    def get_error_spans(self) -> list[Span]:
        """Return only spans that recorded an error."""
        return [s for s in self._spans if s.is_error]

    def summary(self) -> list[dict]:
        """Return serialised summaries of all finished spans."""
        return [s.to_dict() for s in self.get_finished_spans()]

    def clear(self) -> None:
        """Remove all recorded spans."""
        self._spans.clear()


# Module-level default tracer
_default_tracer: Tracer = Tracer()


def get_tracer() -> Tracer:
    """Return the process-wide default tracer."""
    return _default_tracer
