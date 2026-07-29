"""Phase 9.29 – Model requirement resolution errors."""

from __future__ import annotations

from typing import Any


class ModelRequirementsError(Exception):
    """Base error for model requirement contracts and resolution."""

    error_code = "MODEL_REQUIREMENTS_ERROR"

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": dict(self.details),
        }


class InvalidModelRequirementsContractError(ModelRequirementsError):
    error_code = "INVALID_MODEL_REQUIREMENTS_CONTRACT"


class ModelRequirementsConflictError(ModelRequirementsError):
    error_code = "MODEL_REQUIREMENTS_CONFLICT"


class ModelRequirementsResolutionError(ModelRequirementsError):
    error_code = "MODEL_REQUIREMENTS_RESOLUTION_ERROR"


__all__ = [
    "InvalidModelRequirementsContractError",
    "ModelRequirementsConflictError",
    "ModelRequirementsError",
    "ModelRequirementsResolutionError",
]
