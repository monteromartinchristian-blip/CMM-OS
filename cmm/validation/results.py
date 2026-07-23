from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Mapping, Tuple, Optional, Any

from .enums import ValidationStatus
from .findings import ValidationFinding
from .artifacts import ValidationArtifact
from .steps import ValidationStepResult


@dataclass(frozen=True, slots=True)
class ValidationResult:
    id: str
    status: ValidationStatus
    policy: Optional[str] = None
    steps: Tuple[ValidationStepResult, ...] = ()
    artifacts: Tuple[ValidationArtifact, ...] = ()
    blocking_findings: Tuple[ValidationFinding, ...] = ()
    warnings: Tuple[ValidationFinding, ...] = ()
    changed_files: Tuple[Path, ...] = ()
    affected_tests: Tuple[str, ...] = ()
    duration_ms: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    can_commit: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("ValidationResult.id must not be empty")
        if self.duration_ms < 0:
            raise ValueError("ValidationResult.duration_ms must be non-negative")
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValueError("ValidationResult.completed_at cannot be before started_at")
        # defensive copies
        object.__setattr__(self, "steps", tuple(self.steps or ()))
        object.__setattr__(self, "artifacts", tuple(self.artifacts or ()))
        object.__setattr__(self, "blocking_findings", tuple(self.blocking_findings or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(self, "changed_files", tuple(self.changed_files or ()))
        object.__setattr__(self, "affected_tests", tuple(self.affected_tests or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def failed_steps(self) -> Tuple[ValidationStepResult, ...]:
        return tuple(s for s in self.steps if s.status == ValidationStatus.FAILED)

    @property
    def skipped_steps(self) -> Tuple[ValidationStepResult, ...]:
        return tuple(s for s in self.steps if s.status == ValidationStatus.SKIPPED)

    @property
    def total_findings(self) -> int:
        count = len(self.blocking_findings) + len(self.warnings)
        for s in self.steps:
            count += len(s.findings)
        for a in self.artifacts:
            count += len(a.findings)
        return count

    @property
    def is_successful(self) -> bool:
        return self.status == ValidationStatus.PASSED

    @property
    def has_blockers(self) -> bool:
        if self.blocking_findings:
            return True
        for s in self.steps:
            if s.is_blocking:
                return True
        for a in self.artifacts:
            for f in a.findings:
                if f.blocking:
                    return True
        return False

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "policy": self.policy,
            "steps": [s.serialize() for s in self.steps],
            "artifacts": [a.serialize() for a in self.artifacts],
            "blocking_findings": [f.serialize() for f in self.blocking_findings],
            "warnings": [f.serialize() for f in self.warnings],
            "changed_files": [str(p) for p in self.changed_files],
            "affected_tests": list(self.affected_tests),
            "duration_ms": self.duration_ms,
            "started_at": None if self.started_at is None else self.started_at.isoformat(),
            "completed_at": None if self.completed_at is None else self.completed_at.isoformat(),
            "can_commit": self.can_commit,
            "metadata": dict(self.metadata or {}),
        }
