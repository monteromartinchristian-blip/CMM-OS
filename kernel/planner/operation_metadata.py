"""Structured metadata for planner operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class OperationParameter:
    """Describe a single parameter exposed by an operation."""

    name: str
    type: str
    required: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the parameter metadata into a JSON-friendly dictionary."""

        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class OperationMetadata:
    """Structured description of an operation contract."""

    name: str
    description: str
    category: str
    parameters: tuple[OperationParameter, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the metadata into a JSON-friendly dictionary."""

        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": [parameter.to_dict() for parameter in self.parameters],
        }