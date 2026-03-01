"""Task domain model."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pyservicelab.core.time import utcnow


class TaskStatus(str, Enum):
    """Lifecycle status of a task."""

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid status strings."""
        return [s.value for s in cls]

    @classmethod
    def terminal_statuses(cls) -> list["TaskStatus"]:
        """Return statuses that represent a completed workflow."""
        return [cls.DONE, cls.CANCELLED]


class TaskPriority(str, Enum):
    """Priority level of a task."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid priority strings."""
        return [p.value for p in cls]


@dataclass
class Task:
    """Represents a unit of work within a project.

    Attributes:
        id: Database primary key (None before first save).
        project_id: Foreign key referencing the parent project.
        title: Short task title.
        description: Detailed description of the work to be done.
        created_by: User ID of the task creator.
        assignee_id: Optional user ID of the assigned member.
        status: Current workflow state of the task.
        priority: Importance level of the task.
        created_at: UTC creation timestamp.
        updated_at: UTC last-modified timestamp.
        due_date: Optional deadline for the task.
        estimated_hours: Optional work estimate in hours.
    """

    id: Optional[int]
    project_id: int
    title: str
    description: str
    created_by: int
    assignee_id: Optional[int] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None

    # ------------------------------------------------------------------
    # State checks
    # ------------------------------------------------------------------

    def is_complete(self) -> bool:
        """Return True if the task is in a terminal state."""
        return self.status in TaskStatus.terminal_statuses()

    def is_in_progress(self) -> bool:
        """Return True if the task is actively being worked on."""
        return self.status == TaskStatus.IN_PROGRESS

    def is_high_priority(self) -> bool:
        """Return True if the task is HIGH or CRITICAL priority."""
        return self.priority in (TaskPriority.HIGH, TaskPriority.CRITICAL)

    def is_assigned(self) -> bool:
        """Return True if the task has an assignee."""
        return self.assignee_id is not None

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        """Return True if the task is past its due date and not yet complete."""
        if self.due_date is None or self.is_complete():
            return False
        return (now or utcnow()) > self.due_date

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the task to a plain dict."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "created_by": self.created_by,
            "assignee_id": self.assignee_id,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "estimated_hours": self.estimated_hours,
        }
