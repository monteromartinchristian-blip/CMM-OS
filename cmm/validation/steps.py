from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Optional, Tuple, Any
from datetime import datetime, timezone

from .errors import ValidationContractError
from .enums import ValidationStatus
from .findings import ValidationFinding
from .artifacts import ValidationArtifact


class ValidationStepType(str, Enum):
    COMMAND = "command"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class ValidationStep:
    name: str
    step_type: ValidationStepType = ValidationStepType.COMMAND
    command: Tuple[str, ...] = ()
    required: bool = True
    timeout_seconds: int = 60
    stop_on_failure: bool = True
    allowed_exit_codes: Tuple[int, ...] = (0,)
    environment: Mapping[str, str] = field(default_factory=dict)
    working_directory: Optional[Path] = None
    dependencies: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationContractError("ValidationStep.name must not be empty")
        if self.timeout_seconds <= 0:
            raise ValidationContractError(
                "ValidationStep.timeout_seconds must be positive"
            )
        if self.step_type == ValidationStepType.COMMAND and not self.command:
            raise ValidationContractError(
                "ValidationStep.command must be provided for command steps and must be a tuple of strings"
            )
        # enforce uniqueness of dependencies
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValidationContractError(
                "ValidationStep.dependencies must not contain duplicates"
            )
        # defensive copies
        object.__setattr__(self, "environment", dict(self.environment or {}))
        object.__setattr__(self, "dependencies", tuple(self.dependencies or ()))
        object.__setattr__(self, "tags", tuple(self.tags or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "step_type": self.step_type.value,
            "command": list(self.command),
            "required": self.required,
            "timeout_seconds": self.timeout_seconds,
            "stop_on_failure": self.stop_on_failure,
            "allowed_exit_codes": list(self.allowed_exit_codes),
            "environment": dict(self.environment or {}),
            "working_directory": None
            if self.working_directory is None
            else str(self.working_directory),
            "dependencies": list(self.dependencies),
            "tags": list(self.tags),
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True, slots=True)
class ValidationStepResult:
    name: str
    status: ValidationStatus
    exit_code: Optional[int] = None
    duration_ms: int = 0
    stdout: str = ""
    stderr: str = ""
    findings: Tuple[ValidationFinding, ...] = ()
    artifacts: Tuple[ValidationArtifact, ...] = ()
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationContractError("ValidationStepResult.name must not be empty")
        if self.duration_ms < 0:
            raise ValidationContractError(
                "ValidationStepResult.duration_ms must be non-negative"
            )
        if (
            self.started_at
            and self.completed_at
            and self.completed_at < self.started_at
        ):
            raise ValidationContractError(
                "ValidationStepResult.completed_at cannot be before started_at"
            )
        # defensive copies
        object.__setattr__(self, "findings", tuple(self.findings or ()))
        object.__setattr__(self, "artifacts", tuple(self.artifacts or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def is_blocking(self) -> bool:
        return any(f.blocking for f in self.findings)

    @property
    def is_successful(self) -> bool:
        return self.status in (
            ValidationStatus.PASSED,
            ValidationStatus.WARNING,
            ValidationStatus.SKIPPED,
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "findings": [f.serialize() for f in self.findings],
            "artifacts": [a.serialize() for a in self.artifacts],
            "started_at": None
            if self.started_at is None
            else self.started_at.isoformat(),
            "completed_at": None
            if self.completed_at is None
            else self.completed_at.isoformat(),
            "metadata": dict(self.metadata or {}),
        }
