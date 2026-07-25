from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Mapping, Optional, Any

from .enums import ValidationSeverity
from .errors import ValidationContractError


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str
    message: str
    severity: ValidationSeverity
    source: str
    file_path: Optional[Path] = None
    line: Optional[int] = None
    column: Optional[int] = None
    blocking: bool = False
    suggested_fix: Optional[str] = None
    documentation_url: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code:
            raise ValidationContractError("ValidationFinding.code must not be empty")
        if not self.message:
            raise ValidationContractError("ValidationFinding.message must not be empty")
        if not isinstance(self.severity, ValidationSeverity):
            raise ValidationContractError("ValidationFinding.severity must be a ValidationSeverity")
        if not self.source:
            raise ValidationContractError("ValidationFinding.source must not be empty")
        if self.line is not None and self.line <= 0:
            raise ValidationContractError("ValidationFinding.line must be a positive integer when provided")
        if self.column is not None and self.column <= 0:
            raise ValidationContractError("ValidationFinding.column must be a positive integer when provided")
        # defensive copy of metadata mapping to avoid external mutation
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
            "file_path": None if self.file_path is None else str(self.file_path),
            "line": self.line,
            "column": self.column,
            "blocking": self.blocking,
            "suggested_fix": self.suggested_fix,
            "documentation_url": self.documentation_url,
            "metadata": dict(self.metadata or {}),
        }
