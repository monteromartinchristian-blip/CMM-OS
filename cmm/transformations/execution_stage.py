"""One backend-independent stage of transformation execution requests."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.execution_request import ExecutionRequest


@dataclass(frozen=True)
class ExecutionStage:
    """Immutable group of requests that share an execution strategy."""

    requests: tuple[ExecutionRequest, ...]
    parallel: bool = False

    def metadata(self) -> dict[str, object]:
        """Return serializable stage data."""
        return {
            "parallel": self.parallel,
            "requests": [
                {
                    "operation": request.operation.name,
                    "metadata": dict(request.metadata),
                }
                for request in self.requests
            ],
        }

    def describe(self) -> str:
        """Return a human-readable stage description."""
        mode = "parallel" if self.parallel else "sequential"
        return f"{mode.capitalize()} execution stage with {len(self.requests)} requests."
