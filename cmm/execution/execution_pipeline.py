"""Sequential execution of transformation execution plans."""

from __future__ import annotations

from pathlib import Path

from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor_registry import OperationExecutorRegistry
from cmm.execution.python.semantic_context import SemanticContext
from cmm.transformations.execution_plan import ExecutionPlan
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operations import (
    CopySymbolOperation,
    RenameSymbolOperation,
    UpdateImportsOperation,
)


class ExecutionPipeline:
    """Execute a plan in order, stopping as soon as an executor fails."""

    def __init__(
        self,
        registry: OperationExecutorRegistry,
        semantic_context: SemanticContext,
        project_root: Path,
    ) -> None:
        self._registry = registry
        self._semantic_context = semantic_context
        self._project_root = project_root

    def execute(self, plan: ExecutionPlan) -> tuple[ExecutionResult, ...]:
        """Execute every request in order until one result fails."""
        results = []
        previous_result = None
        for request in plan.all_requests():
            enriched_request = self._enrich_request(request, previous_result)
            result = self._registry.resolve(enriched_request.operation).execute(
                enriched_request
            )
            results.append(result)
            previous_result = result
            semantic_context = result.metadata.get("semantic_context")
            if isinstance(semantic_context, SemanticContext):
                self._semantic_context = semantic_context
            if not result.success:
                break
        return tuple(results)

    def _enrich_request(
        self,
        request: ExecutionRequest,
        previous_result: ExecutionResult | None,
    ) -> ExecutionRequest:
        metadata = {
            **request.metadata,
            "semantic_context": self._semantic_context,
            "project_root": str(self._project_root),
            "previous_result": previous_result,
        }
        operation = request.operation
        if isinstance(operation, UpdateImportsOperation):
            copy_operation = self._copy_operation(request)
            if copy_operation is not None:
                metadata.update(
                    {
                        "old_module": copy_operation.source,
                        "new_module": copy_operation.destination,
                        "symbol_name": copy_operation.symbol,
                    }
                )
        if isinstance(operation, RenameSymbolOperation):
            metadata["module"] = self._target_module(request)
        return ExecutionRequest(operation=operation, metadata=metadata)

    def _copy_operation(
        self,
        request: ExecutionRequest,
    ) -> CopySymbolOperation | None:
        for candidate in request.metadata.get("plan_operations", ()):
            if isinstance(candidate, CopySymbolOperation):
                return candidate
        return None

    def _target_module(self, request: ExecutionRequest) -> str | None:
        copy_operation = self._copy_operation(request)
        return copy_operation.destination if copy_operation is not None else None
