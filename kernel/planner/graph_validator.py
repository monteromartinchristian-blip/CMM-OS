"""Validation for execution graphs.

This validator operates only on :class:`ExecutionGraph` instances and keeps the
current graph container untouched. It is intentionally small so new structural
rules can be added without changing the call sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from uuid import UUID

from kernel.planner.execution_graph import ExecutionGraph


@dataclass(slots=True)
class GraphValidationResult:
    """Structured result returned by :class:`GraphValidator`."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Record a validation error and mark the result invalid."""

        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Record a validation warning."""

        self.warnings.append(message)

    def has_errors(self) -> bool:
        """Return whether the validation found errors."""

        return bool(self.errors)


class GraphValidator:
    """Validate the structure of an execution graph.

    The current checks are deliberately limited to:
    - duplicate operation identifiers
    - missing dependency targets
    - dependency cycles
    """

    def validate(self, graph: ExecutionGraph | None) -> GraphValidationResult:
        """Validate a graph and return a structured result."""

        result = GraphValidationResult()

        if graph is None:
            result.add_error("Execution graph cannot be None.")
            return result

        operation_ids = [operation.operation_id for operation in graph.operations()]
        seen_ids: set[UUID] = set()
        for operation_id in operation_ids:
            if operation_id in seen_ids:
                result.add_error(f"Duplicate operation_id detected: {operation_id}")
            else:
                seen_ids.add(operation_id)

        graph_ids = set(operation_ids)
        for operation in graph.operations():
            missing_dependencies = [dependency_id for dependency_id in graph.dependencies_of(operation.operation_id) if dependency_id not in graph_ids]
            for dependency_id in missing_dependencies:
                result.add_error(
                    f"Missing dependency detected for {operation.operation_id}: {dependency_id}"
                )

        cycle = self._find_cycle(graph)
        if cycle is not None:
            result.add_error("Cycle detected: " + " -> ".join(str(operation_id) for operation_id in cycle))

        return result

    def _find_cycle(self, graph: ExecutionGraph) -> list[UUID] | None:
        """Detect a cycle using depth-first search.

        The search tracks a recursion stack so that back edges can be converted
        into a human-readable cycle path.
        """

        visited: set[UUID] = set()
        active: set[UUID] = set()
        path: list[UUID] = []

        def visit(operation_id: UUID) -> list[UUID] | None:
            if operation_id in active:
                cycle_start = path.index(operation_id)
                return path[cycle_start:] + [operation_id]
            if operation_id in visited:
                return None

            visited.add(operation_id)
            active.add(operation_id)
            path.append(operation_id)

            for dependency_id in graph.dependencies_of(operation_id):
                if not graph.contains(dependency_id):
                    continue
                cycle = visit(dependency_id)
                if cycle is not None:
                    return cycle

            active.remove(operation_id)
            path.pop()
            return None

        for operation in graph.operations():
            cycle = visit(operation.operation_id)
            if cycle is not None:
                return cycle

        return None
