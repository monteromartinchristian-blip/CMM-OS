"""Topological sorting for execution graphs.

This module provides the first execution-order bridge over the graph model.
It assumes the input graph has already been validated and only computes a
stable topological ordering.
"""

from __future__ import annotations

from collections import deque
from typing import Dict
from uuid import UUID

from kernel.planner.execution_graph import ExecutionGraph
from kernel.planner.operations import Operation


class TopologicalSorter:
    """Compute a valid execution order for a validated execution graph."""

    def sort(self, graph: ExecutionGraph) -> list[Operation]:
        """Return the operations in topological order.

        The implementation uses Kahn's algorithm with insertion order as the
        deterministic tie-breaker for nodes that become ready at the same time.
        """

        operations = list(graph.operations())
        if not operations:
            return []

        operation_ids = [operation.operation_id for operation in operations]
        operation_positions = {operation_id: index for index, operation_id in enumerate(operation_ids)}
        in_degree: Dict[UUID, int] = {}
        ready_ids: deque[UUID] = deque()
        pending_ready: list[UUID] = []

        for operation_id in operation_ids:
            dependencies = [dependency_id for dependency_id in graph.dependencies_of(operation_id) if graph.contains(dependency_id)]
            in_degree[operation_id] = len(dependencies)
            if not dependencies:
                pending_ready.append(operation_id)

        pending_ready.sort(key=operation_positions.__getitem__)
        ready_ids.extend(pending_ready)

        ordered_operations: list[Operation] = []
        while ready_ids:
            operation_id = ready_ids.popleft()
            operation = graph.get(operation_id)
            if operation is None:
                continue

            ordered_operations.append(operation)

            for dependent_id in sorted(graph.dependents_of(operation_id), key=operation_positions.__getitem__):
                if dependent_id not in in_degree:
                    continue
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    ready_ids.append(dependent_id)

        return ordered_operations
