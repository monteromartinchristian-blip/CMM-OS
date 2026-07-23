from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Any, Tuple

from .findings import ValidationFinding


@dataclass(frozen=True, slots=True)
class ValidationArtifact:
    id: str
    kind: str
    source: str
    path: Optional[Path] = None
    content: Mapping[str, Any] = field(default_factory=dict)
    findings: Tuple[ValidationFinding, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # defensive copies for mappings
        object.__setattr__(self, "content", dict(self.content or {}))
        object.__setattr__(self, "metrics", dict(self.metrics or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source,
            "path": None if self.path is None else str(self.path),
            "content": dict(self.content or {}),
            "findings": [f.serialize() for f in self.findings],
            "metrics": dict(self.metrics or {}),
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata or {}),
        }
