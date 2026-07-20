"""Planning context for the rule-based planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PlanningContext:
    """Immutable execution context for planner rules.

    The context carries the user intent and optional project information that can
    later be enriched by additional planning layers such as LLMs or repository
    analysis.
    """

    intent: str
    language: str = "python"
    project_root: Path | None = None
    current_file: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_metadata(self, **kwargs: Any) -> "PlanningContext":
        """Return a new context with merged metadata."""

        merged_metadata = dict(self.metadata)
        merged_metadata.update(kwargs)
        return PlanningContext(
            intent=self.intent,
            language=self.language,
            project_root=self.project_root,
            current_file=self.current_file,
            metadata=merged_metadata,
        )

    @property
    def has_project(self) -> bool:
        """Return whether the context carries a project root."""

        return self.project_root is not None

    @property
    def has_current_file(self) -> bool:
        """Return whether the context carries a current file."""

        return self.current_file is not None
