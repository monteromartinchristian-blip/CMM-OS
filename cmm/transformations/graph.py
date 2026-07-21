"""Transformation graph representation and DAG validation."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from cmm.transformations.models import TransformationGraphNode
from cmm.transformations.plan import TransformationPlan


@dataclass(frozen=True)
class GraphValidationError:
    """Structured DAG validation error."""

    code: str
    message: str
    step_id: str | None = None
    dependency_id: str | None = None


@dataclass(frozen=True)
class GraphValidationResult:
    """Structured result of validating a transformation graph."""

    success: bool
    errors: tuple[GraphValidationError, ...] = ()
    topological_order: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransformationGraph:
    """Directed acyclic graph representation for transformation execution."""

    nodes: Mapping[str, TransformationGraphNode]

    def __post_init__(self) -> None:
        nodes = dict(self.nodes)
        for node_id, node in nodes.items():
            if node_id != node.step.id:
                raise ValueError(
                    "Transformation graph node key must match TransformationStep.id."
                )

        object.__setattr__(self, "nodes", MappingProxyType(nodes))

    @classmethod
    def from_plan(cls, plan: TransformationPlan) -> "TransformationGraph":
        """Build a graph from step-local dependency declarations."""
        seen: set[str] = set()
        nodes: dict[str, TransformationGraphNode] = {}
        for step in plan.steps:
            if step.id in seen:
                continue
            seen.add(step.id)
            nodes[step.id] = TransformationGraphNode(
                step=step,
                dependencies=step.dependencies,
            )
        return cls(nodes=nodes)

    @staticmethod
    def validate_plan(plan: TransformationPlan) -> GraphValidationResult:
        """Validate duplicate step IDs before materializing the graph mapping."""
        errors: list[GraphValidationError] = []
        seen: set[str] = set()
        for step in plan.steps:
            if step.id in seen:
                errors.append(
                    GraphValidationError(
                        code="duplicate_step_id",
                        message=f"Duplicate transformation step id: {step.id}.",
                        step_id=step.id,
                    )
                )
            seen.add(step.id)

        graph = TransformationGraph.from_plan(plan)
        graph_result = graph.validate()
        errors.extend(graph_result.errors)
        if errors:
            return GraphValidationResult(success=False, errors=tuple(errors))
        return graph_result

    def validate(self) -> GraphValidationResult:
        """Validate dependencies, cycles, and deterministic topological order."""
        errors: list[GraphValidationError] = []
        node_ids = set(self.nodes)
        for node_id, node in self.nodes.items():
            for dependency in node.dependencies:
                if dependency not in node_ids:
                    errors.append(
                        GraphValidationError(
                            code="missing_dependency",
                            message=(
                                f"Step {node_id} depends on missing step "
                                f"{dependency}."
                            ),
                            step_id=node_id,
                            dependency_id=dependency,
                        )
                    )
        if errors:
            return GraphValidationResult(success=False, errors=tuple(errors))

        order, cycle = self._topological_order()
        if cycle:
            return GraphValidationResult(
                success=False,
                errors=(
                    GraphValidationError(
                        code="cycle_detected",
                        message=f"Transformation graph contains a cycle: {' -> '.join(cycle)}.",
                        step_id=cycle[0],
                    ),
                ),
            )
        return GraphValidationResult(success=True, topological_order=tuple(order))

    def topological_order(self) -> tuple[TransformationGraphNode, ...]:
        """Return graph nodes in deterministic topological order."""
        result = self.validate()
        if not result.success:
            messages = "; ".join(error.message for error in result.errors)
            raise ValueError(messages)
        return tuple(self.nodes[node_id] for node_id in result.topological_order)

    def _topological_order(self) -> tuple[list[str], list[str]]:
        """Use deterministic Kahn ordering without recursion depth limits."""
        remaining = {
            node_id: set(node.dependencies)
            for node_id, node in self.nodes.items()
        }
        ready = sorted(node_id for node_id, dependencies in remaining.items() if not dependencies)
        order: list[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for dependent_id in sorted(remaining):
                dependencies = remaining[dependent_id]
                if node_id in dependencies:
                    dependencies.remove(node_id)
                    if not dependencies:
                        ready.append(dependent_id)
            ready.sort()

        if len(order) == len(self.nodes):
            return order, []

        cycle_nodes = sorted(node_id for node_id, dependencies in remaining.items() if dependencies)
        cycle = cycle_nodes + [cycle_nodes[0]] if cycle_nodes else []
        return order, cycle
