"""Backend-independent plan of staged transformation execution requests."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.execution_stage import ExecutionStage


@dataclass(frozen=True)
class ExecutionPlan:
    """Immutable sequence of execution stages."""

    stages: tuple[ExecutionStage, ...]
    version: str = "1.0"

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
            "stages": [stage.metadata() for stage in self.stages],
        }

    def describe(self) -> str:
        """Return a human-readable execution-plan description."""
        return (
            f"Execution plan version {self.version} with "
            f"{len(self.stages)} stages and {len(self.all_requests())} requests."
        )
