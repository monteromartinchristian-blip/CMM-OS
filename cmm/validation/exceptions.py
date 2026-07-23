from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Any


@dataclass(frozen=True, slots=True)
class ValidationErrorBase(Exception):
    code: str
    message: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.message}"


class ValidationRegistryError(ValidationErrorBase):
    pass


class ValidationDependencyError(ValidationErrorBase):
    pass


class ValidationExecutionError(ValidationErrorBase):
    pass


class ValidationPipelineError(ValidationErrorBase):
    pass


__all__ = [
    "ValidationErrorBase",
    "ValidationRegistryError",
    "ValidationDependencyError",
    "ValidationExecutionError",
    "ValidationPipelineError",
]
