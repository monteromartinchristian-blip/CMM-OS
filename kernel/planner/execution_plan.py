"""Execution plan container for the Semantic Planner domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Mapping
from uuid import UUID, uuid4

from kernel.planner.exceptions import ExecutionPlanError
from kernel.planner.operations import Operation


@dataclass(slots=True)
class ExecutionPlan:
    """An ordered collection of planner operations.

    The execution plan is intentionally independent from the semantic engine and
    only describes the intended sequence of operations.
    """

    plan_id: UUID = field(default_factory=uuid4)
    operations: list[Operation] = field(default_factory=list)

    def add(self, operation: Operation) -> None:
        """Append an operation to the end of the plan."""

        self._validate_operation(operation)
        self.operations.append(operation)

    def extend(self, operations: Iterable[Operation]) -> None:
        """Append multiple operations to the plan in order."""

        for operation in operations:
            self.add(operation)

    def remove(self, operation: Operation) -> None:
        """Remove an operation from the plan if it exists."""

        self._validate_operation(operation)
        try:
            self.operations.remove(operation)
        except ValueError as exc:
            raise ExecutionPlanError("The provided operation is not present in the plan.") from exc

    def __iter__(self) -> Iterator[Operation]:
        """Iterate over the operations in order."""

        return iter(self.operations)

    def __getitem__(self, index: int) -> Operation:
        """Get an operation by index."""

        return self.operations[index]

    def __len__(self) -> int:
        """Return the number of operations in the plan."""

        return len(self.operations)

    def is_empty(self) -> bool:
        """Return whether the plan has any operations."""

        return len(self.operations) == 0

    def serialize(self) -> dict[str, Any]:
        """Serialize the plan into a dictionary."""

        return {
            "plan_id": str(self.plan_id),
            "operations": [operation.serialize() for operation in self.operations],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionPlan":
        """Create an execution plan from serialized data."""

        operations_payload = payload.get("operations", [])
        plan_id = payload.get("plan_id")
        plan = cls(plan_id=UUID(str(plan_id)) if plan_id is not None else uuid4())

        for item in operations_payload:
            plan.add(Operation.from_dict(item))

        return plan

    @staticmethod
    def _validate_operation(operation: Operation) -> None:
        if not isinstance(operation, Operation):
            raise ExecutionPlanError("ExecutionPlan only accepts Operation instances.")
