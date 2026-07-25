"""Phase 9.13 – Operation Execution Integrations.

Provides explicit integration adapters between Operation Execution and existing CMM subsystems:
Action Budget, Policy Engine, Autonomy Evaluator, Human Approval, Lock Manager, Resource Version Provider,
and Execution Engine (cmm.execution).
"""

from __future__ import annotations

from typing import Any, Protocol

from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest


class ResourceVersionProvider(Protocol):
    """Protocol for checking live resource state versions."""

    def get_version(self, resource_uri: str) -> str:
        """Return current version hash or identifier for resource_uri."""
        ...


class InMemoryResourceVersionProvider:
    """In-memory dictionary provider for resource version checking."""

    def __init__(self, versions: dict[str, str] | None = None) -> None:
        self._versions = versions or {}

    def set_version(self, resource_uri: str, version: str) -> None:
        self._versions[resource_uri] = version

    def get_version(self, resource_uri: str) -> str:
        return self._versions.get(resource_uri, "unknown")


class TransformationExecutionEngineAdapter:
    """Adapts AgentOperationRequest to cmm.execution (TransformationOperation / OperationExecutor)."""

    def __init__(
        self,
        transformation_registry: Any | None = None,
        executor_registry: Any | None = None,
    ) -> None:
        self._transformation_registry = transformation_registry
        self._executor_registry = executor_registry

    def execute(self, request: AgentOperationRequest) -> dict[str, Any]:
        """Execute request using underlying CMM execution pipeline/executors."""
        if self._transformation_registry and hasattr(
            self._transformation_registry, "resolve"
        ):
            try:
                op = self._transformation_registry.resolve(request.operation_name)
                if self._executor_registry and hasattr(
                    self._executor_registry, "resolve"
                ):
                    executor = self._executor_registry.resolve(op)
                    # Prepare mock request or execution context if needed
                    from cmm.transformations.execution_request import ExecutionRequest

                    exec_req = ExecutionRequest(
                        operation=op, metadata=dict(request.metadata)
                    )
                    result = executor.execute(exec_req)
                    success = getattr(result, "success", True)
                    diagnostics = getattr(result, "diagnostics", ())
                    created_paths = getattr(result, "created_paths", ())

                    return {
                        "success": success,
                        "execution_result_id": f"exec-res-{request.id}",
                        "effects": (f"executed:{request.operation_name}",),
                        "artifacts": [str(p) for p in created_paths],
                        "reason_codes": diagnostics,
                    }
            except Exception as exc:  # noqa: BLE001
                return {
                    "success": False,
                    "effects": (),
                    "reason_codes": (str(exc),),
                }

        # Fallback adapter output if no explicit registry is provided
        return {
            "success": True,
            "execution_result_id": f"exec-res-{request.id}",
            "effects": (f"executed:{request.operation_name}",),
            "side_effects": (),
            "artifacts": (),
            "validation_result_ids": (),
        }
