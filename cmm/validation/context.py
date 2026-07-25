from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Tuple, Any

from .errors import ValidationContractError


@dataclass(frozen=True, slots=True)
class ValidationContext:
    project_root: Path
    changed_files: Tuple[Path, ...] = ()
    change_type: str = "full"
    execution_mode: str = "local"
    requested_steps: Optional[Tuple[str, ...]] = None
    excluded_steps: Tuple[str, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict)
    allow_commit: bool = False
    branch: Optional[str] = None
    base_commit: Optional[str] = None
    requested_policy: Optional[str] = None
    actor: Optional[str] = None
    workflow_id: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.project_root:
            raise ValidationContractError(
                "ValidationContext.project_root must be provided"
            )
        # normalize changed_files into Paths; keep them relative where possible
        normalized: list[Path] = []
        for p in self.changed_files:
            if isinstance(p, Path):
                path = p
            else:
                path = Path(str(p))
            try:
                rel = path.relative_to(self.project_root)
                normalized.append(rel)
            except Exception:
                normalized.append(path)
        object.__setattr__(self, "changed_files", tuple(normalized))
        # defensive copies & normalization
        if isinstance(self.excluded_steps, (list, tuple, set)):
            object.__setattr__(
                self, "excluded_steps", tuple(str(s) for s in self.excluded_steps)
            )
        else:
            object.__setattr__(self, "excluded_steps", (str(self.excluded_steps),))
        object.__setattr__(self, "environment", dict(self.environment or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "changed_files": [str(p) for p in self.changed_files],
            "change_type": self.change_type,
            "execution_mode": self.execution_mode,
            "requested_steps": list(self.requested_steps)
            if self.requested_steps is not None
            else None,
            "excluded_steps": list(self.excluded_steps),
            "environment": dict(self.environment or {}),
            "allow_commit": self.allow_commit,
            "branch": self.branch,
            "base_commit": self.base_commit,
            "requested_policy": self.requested_policy,
            "actor": self.actor,
            "workflow_id": self.workflow_id,
            "metadata": dict(self.metadata or {}),
        }
