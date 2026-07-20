"""Discovery catalog for planner operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from kernel.planner.operation_metadata import OperationMetadata
from kernel.planner.operations import Operation, registered_operation_classes


@dataclass(slots=True)
class OperationCatalog:
    """Discover and expose all registered planner operations."""

    _operations: dict[str, type[Operation]] = field(default_factory=dict)

    def __init__(self, operations: Iterable[type[Operation]] | None = None) -> None:
        if operations is None:
            operations = registered_operation_classes()

        self._operations = {operation.operation_metadata().name: operation for operation in operations}

    def operations(self) -> tuple[OperationMetadata, ...]:
        """Return all operation metadata objects in deterministic order."""

        return tuple(operation.operation_metadata() for operation in self._operations.values())

    def get(self, name: str) -> OperationMetadata | None:
        """Return the metadata for an operation name if it exists."""

        operation = self._operations.get(name)
        if operation is None:
            return None
        return operation.operation_metadata()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire catalog into a JSON-friendly structure."""

        return {"operations": [metadata.to_dict() for metadata in self.operations()]}