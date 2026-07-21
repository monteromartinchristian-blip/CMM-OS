"""Structured results for technical-memory persistence and refresh operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ProjectChangeSet:
    created: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()
    renamed: tuple[tuple[str, str], ...] = ()
    parse_errors: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not any((self.created, self.modified, self.deleted, self.renamed, self.parse_errors))

    def serialize(self) -> dict[str, Any]:
        return {
            "created": list(self.created),
            "modified": list(self.modified),
            "deleted": list(self.deleted),
            "renamed": [list(pair) for pair in self.renamed],
            "parse_errors": list(self.parse_errors),
        }


@dataclass(frozen=True, slots=True)
class RepositoryResult:
    success: bool
    operation: str
    message: str
    persisted: bool = False
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    duration_seconds: float = 0.0

    def serialize(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "operation": self.operation,
            "message": self.message,
            "persisted": self.persisted,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True, slots=True)
class MemoryLoadResult:
    success: bool
    origin: str
    persisted: bool
    rebuilt: bool = False
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    duration_seconds: float = 0.0

    def serialize(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "origin": self.origin,
            "persisted": self.persisted,
            "rebuilt": self.rebuilt,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True, slots=True)
class MemoryRefreshResult:
    success: bool
    change_set: ProjectChangeSet
    nodes_added: tuple[str, ...] = ()
    nodes_modified: tuple[str, ...] = ()
    nodes_deleted: tuple[str, ...] = ()
    persisted: bool = False
    rebuilt: bool = False
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    duration_seconds: float = 0.0

    def serialize(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "change_set": self.change_set.serialize(),
            "nodes_added": list(self.nodes_added),
            "nodes_modified": list(self.nodes_modified),
            "nodes_deleted": list(self.nodes_deleted),
            "persisted": self.persisted,
            "rebuilt": self.rebuilt,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "duration_seconds": self.duration_seconds,
        }
