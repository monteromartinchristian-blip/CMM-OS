"""Backend-independent plan of staged transformation execution requests."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.preconditions import TransformationPrecondition
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.execution_stage import ExecutionStage


@dataclass(frozen=True)
class ExecutionPlan:
    """Immutable sequence of execution stages."""

    stages: tuple[ExecutionStage, ...]
    version: str = "1.0"
    plan_id: str | None = None
    planned_steps: tuple[str, ...] = ()
    preconditions: tuple[TransformationPrecondition, ...] = ()
    impact_requests: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(self, "planned_steps", tuple(self.planned_steps))
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
        object.__setattr__(self, "impact_requests", tuple(self.impact_requests))

    def all_requests(self) -> tuple[ExecutionRequest, ...]:
        """Return every request in stage and request order."""
        return tuple(
            request
            for stage in self.stages
            for request in stage.requests
        )

    def metadata(self) -> dict[str, object]:
        """Return serializable execution-plan data."""
        return {
            "version": self.version,
            "plan_id": self.plan_id,
            "planned_steps": list(self.planned_steps),
            "impact_requests": [getattr(request, "__dict__", str(request)) for request in self.impact_requests],
            "stages": [stage.metadata() for stage in self.stages],
        }

    def describe(self) -> str:
        """Return a human-readable execution-plan description."""
        return (
            f"Execution plan version {self.version} with "
            f"{len(self.stages)} stages and {len(self.all_requests())} requests."
        )
