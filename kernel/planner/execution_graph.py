"""In-memory execution graph for planner operations.

This module introduces the first graph-shaped container for future execution
planning work while preserving the current linear plan behavior elsewhere.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID

from kernel.planner.operations import Operation


@dataclass(slots=True)
class ExecutionGraph:
    """Store operations and their dependency relationships by operation id.

    The graph is intentionally minimal for now: it stores nodes by their
    identifier and records direct dependency edges without deriving execution
    order or validating graph shape.
    """

    _operations: dict[UUID, Operation] = field(default_factory=dict)
    _dependencies: dict[UUID, set[UUID]] = field(default_factory=dict)
    _dependents: dict[UUID, set[UUID]] = field(default_factory=dict)
    _insertion_order: list[UUID] = field(default_factory=list)

    def add_operation(self, operation: Operation) -> None:
        """Add an operation node and register its dependency edges."""

        operation_id = operation.operation_id
        self._operations[operation_id] = operation

        if operation_id not in self._insertion_order:
            self._insertion_order.append(operation_id)

        dependencies = set(operation.depends_on)
        self._dependencies[operation_id] = dependencies
        self._dependents.setdefault(operation_id, set())

        for dependency_id in dependencies:
            self._dependents.setdefault(dependency_id, set()).add(operation_id)

    def get(self, operation_id: UUID) -> Operation | None:
        """Return the operation registered for the given identifier."""

        return self._operations.get(operation_id)

    def contains(self, operation_id: UUID) -> bool:
        """Return whether the graph contains an operation id."""

        return operation_id in self._operations

    def operations(self) -> tuple[Operation, ...]:
        """Return the stored operations in insertion order."""

        return tuple(self._operations[operation_id] for operation_id in self._insertion_order)

    def dependencies_of(self, operation_id: UUID) -> tuple[UUID, ...]:
        """Return the direct dependency ids for an operation."""

        return tuple(self._dependencies.get(operation_id, set()))

    def dependents_of(self, operation_id: UUID) -> tuple[UUID, ...]:
        """Return the direct dependent ids for an operation."""

        return tuple(self._dependents.get(operation_id, set()))
