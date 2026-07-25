from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from cmm.validation.errors import ValidationContractError


class StaticAnalysisScope(str, Enum):
    AFFECTED = "affected"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class StaticAnalysisPlan:
    project_root: Path
    scope: StaticAnalysisScope
    complete: bool
    reason: str
    files: tuple[Path, ...]
    change_type: str
    public_api_changed: bool
    requires_full_suite: bool
    confidence: float
    uncertainty: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError("StaticAnalysisPlan.confidence must be between 0 and 1")
        object.__setattr__(self, "project_root", Path(str(self.project_root)))
        object.__setattr__(self, "files", tuple(Path(str(item)) for item in self.files or ()))
        object.__setattr__(self, "uncertainty", tuple(str(item) for item in self.uncertainty or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "scope": self.scope.value,
            "complete": self.complete,
            "reason": self.reason,
            "files": [str(path) for path in self.files],
            "change_type": self.change_type,
            "public_api_changed": self.public_api_changed,
            "requires_full_suite": self.requires_full_suite,
            "confidence": self.confidence,
            "uncertainty": list(self.uncertainty),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "StaticAnalysisPlan":
        return cls(
            project_root=Path(str(payload["project_root"])),
            scope=StaticAnalysisScope(str(payload.get("scope", "affected"))),
            complete=bool(payload.get("complete", False)),
            reason=str(payload.get("reason", "")),
            files=tuple(Path(str(item)) for item in payload.get("files", ())),
            change_type=str(payload.get("change_type", "unknown")),
            public_api_changed=bool(payload.get("public_api_changed", False)),
            requires_full_suite=bool(payload.get("requires_full_suite", False)),
            confidence=float(payload.get("confidence", 0.0)),
            uncertainty=tuple(str(item) for item in payload.get("uncertainty", ())),
            metadata=dict(payload.get("metadata", {})) if isinstance(payload.get("metadata"), Mapping) else {},
        )
