from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


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


class CommitGateError(ValidationErrorBase):
    pass


class CommitAuthorizationError(ValidationErrorBase):
    pass


class UnsafeRepositoryStateError(ValidationErrorBase):
    pass


class ProvisionalCommitError(ValidationErrorBase):
    pass


__all__ = [
    "CommitAuthorizationError",
    "CommitGateError",
    "ProvisionalCommitError",
    "UnsafeRepositoryStateError",
    "ValidationDependencyError",
    "ValidationErrorBase",
    "ValidationExecutionError",
    "ValidationPipelineError",
    "ValidationRegistryError",
]
