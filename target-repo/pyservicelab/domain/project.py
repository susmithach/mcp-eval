"""Project domain model."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pyservicelab.core.time import utcnow


class ProjectStatus(str, Enum):
    """Lifecycle status of a project."""

    DRAFT = "draft"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid status strings."""
        return [s.value for s in cls]


@dataclass
class Project:
    """Represents a project owned by a user.

    Attributes:
        id: Database primary key (None before first save).
        name: Human-readable project name.
        description: Detailed description of the project.
        owner_id: Foreign key referencing the owning user.
        status: Lifecycle state of the project.
        created_at: UTC creation timestamp.
        updated_at: UTC last-modified timestamp.
        due_date: Optional deadline for the project.
        tags: Comma-separated tag string (use :meth:`get_tags` for a list).
    """

    id: Optional[int]
    name: str
    description: str
    owner_id: int
    status: ProjectStatus = ProjectStatus.DRAFT
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    due_date: Optional[datetime] = None
    tags: str = ""

    # ------------------------------------------------------------------
    # State checks
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """Return True if the project is currently active."""
        return self.status == ProjectStatus.ACTIVE

    def is_archived(self) -> bool:
        """Return True if the project has been archived."""
        return self.status == ProjectStatus.ARCHIVED

    def is_complete(self) -> bool:
        """Return True if the project has been completed."""
        return self.status == ProjectStatus.COMPLETED

    def is_editable(self) -> bool:
        """Return True if the project can receive new tasks."""
        return self.status in (ProjectStatus.DRAFT, ProjectStatus.ACTIVE)

    # ------------------------------------------------------------------
    # Tag helpers
    # ------------------------------------------------------------------

    def get_tags(self) -> list[str]:
        """Return tags as a list of stripped strings."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def set_tags(self, tags: list[str]) -> None:
        """Set tags from a list."""
        self.tags = ", ".join(tags)

    def has_tag(self, tag: str) -> bool:
        """Return True if the project carries the given tag."""
        return tag.strip().lower() in [t.lower() for t in self.get_tags()]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the project to a plain dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "tags": self.get_tags(),
        }
