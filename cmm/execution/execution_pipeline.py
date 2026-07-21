"""Sequential execution of transformation execution plans."""

from __future__ import annotations

import ast
import shutil
from dataclasses import dataclass
from pathlib import Path

from cmm.execution.execution_context import ExecutionContext, ProjectPathError
from cmm.execution.execution_result import (
    ExecutionResult,
    FinalValidationResult,
    OperationResultRecord,
    PipelineExecutionResult,
    RollbackResult,
    StructuredExecutionError,
)
from cmm.execution.operation_executor_registry import OperationExecutorRegistry
from cmm.execution.operation_executor_registry import UnsupportedOperationExecutorError
from cmm.execution.python.semantic_context import SemanticContext
from cmm.transformations.execution_plan import ExecutionPlan
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.preconditions import PreconditionResult, TransformationPrecondition
from cmm.transformations.operations import (
    CopySymbolOperation,
    RenameSymbolOperation,
    UpdateImportsOperation,
)


@dataclass(frozen=True)
class _SnapshotEntry:
    existed: bool
    is_file: bool
    content: bytes | None = None


class ExecutionPipeline:
    """Execute a plan in order with validation, snapshots, and rollback."""

    def __init__(
        self,
        registry: OperationExecutorRegistry,
        semantic_context: SemanticContext,
        project_root: Path,
    ) -> None:
        self._registry = registry
        self._context = ExecutionContext(project_root, semantic_context=semantic_context)
        self._semantic_context = self._context.semantic_context
        self._project_root = self._context.project_root

    def execute(self, plan: ExecutionPlan) -> PipelineExecutionResult:
        """Execute every request in order and return one structured result."""
        try:
            precondition_results = self._evaluate_global_preconditions(plan)
        except ProjectPathError as error:
            return PipelineExecutionResult(
                success=False,
                plan_id=plan.plan_id,
                planned_steps=plan.planned_steps,
                executed_steps=(),
                error=StructuredExecutionError(
                    code="path_error",
                    message=str(error),
                ),
            )
        failed_precondition = next((result for result in precondition_results if not result.success), None)
        if failed_precondition is not None:
            return self._precondition_failure(plan, precondition_results, failed_precondition, ())

        first_request = plan.all_requests()[0] if plan.all_requests() else None
        if first_request is not None:
            try:
                first_results = self._evaluate_step_preconditions(first_request)
            except ProjectPathError as error:
                return self._path_failure(plan, precondition_results, error)
            precondition_results += first_results
            failed_precondition = next((result for result in first_results if not result.success), None)
            if failed_precondition is not None:
                return self._precondition_failure(plan, precondition_results, failed_precondition, ())

        try:
            snapshot = self._snapshot(plan)
        except ProjectPathError as error:
            return PipelineExecutionResult(
                success=False,
                plan_id=plan.plan_id,
                planned_steps=plan.planned_steps,
                executed_steps=(),
                precondition_results=precondition_results,
                error=StructuredExecutionError(
                    code="path_error",
                    message=str(error),
                ),
            )
        operation_results: list[OperationResultRecord] = []
        executed_steps: list[str] = []
        raw_results: list[ExecutionResult] = []
        previous_result = None
        for request_index, request in enumerate(plan.all_requests()):
            if request_index > 0:
                try:
                    step_results = self._evaluate_step_preconditions(request)
                except ProjectPathError as error:
                    rollback = self._rollback(snapshot)
                    return self._structured_result(
                        plan=plan,
                        success=False,
                        precondition_results=precondition_results,
                        operation_results=tuple(operation_results),
                        raw_results=tuple(raw_results),
                        snapshot=snapshot,
                        executed_steps=tuple(executed_steps),
                        failed_step=self._step_id(request),
                        error=StructuredExecutionError("path_error", str(error), self._step_id(request)),
                        rollback=rollback,
                        validations=(),
                    )
                precondition_results += step_results
                failed_precondition = next((result for result in step_results if not result.success), None)
                if failed_precondition is not None:
                    rollback = self._rollback(snapshot)
                    return self._structured_result(
                        plan=plan,
                        success=False,
                        precondition_results=precondition_results,
                        operation_results=tuple(operation_results),
                        raw_results=tuple(raw_results),
                        snapshot=snapshot,
                        executed_steps=tuple(executed_steps),
                        failed_step=failed_precondition.step_id,
                        error=StructuredExecutionError("precondition_failed", failed_precondition.message, failed_precondition.step_id),
                        rollback=rollback,
                        validations=(),
                    )
            enriched_request = self._enrich_request(request, previous_result)
            step_id = self._step_id(enriched_request)
            try:
                result = self._registry.resolve(enriched_request.operation).execute(enriched_request)
            except UnsupportedOperationExecutorError as error:
                rollback = self._rollback(snapshot)
                return self._structured_result(
                    plan=plan,
                    success=False,
                    precondition_results=precondition_results,
                    operation_results=tuple(operation_results),
                    raw_results=tuple(raw_results),
                    snapshot=snapshot,
                    executed_steps=tuple(executed_steps),
                    failed_step=step_id,
                    error=StructuredExecutionError("unsupported_operation", str(error), step_id),
                    rollback=rollback,
                    validations=(),
                )
            except (OSError, ProjectPathError) as error:
                rollback = self._rollback(snapshot)
                return self._structured_result(
                    plan=plan,
                    success=False,
                    precondition_results=precondition_results,
                    operation_results=tuple(operation_results),
                    raw_results=tuple(raw_results),
                    snapshot=snapshot,
                    executed_steps=tuple(executed_steps),
                    failed_step=step_id,
                    error=StructuredExecutionError("operation_error", str(error), step_id),
                    rollback=rollback,
                    validations=(),
                )
            raw_results.append(result)
            operation_results.append(
                OperationResultRecord(
                    step_id=step_id,
                    operation=enriched_request.operation.name,
                    success=result.success,
                    diagnostics=result.diagnostics,
                )
            )
            previous_result = result
            semantic_context = result.metadata.get("semantic_context")
            if isinstance(semantic_context, SemanticContext):
                self._semantic_context = semantic_context
                self._context.semantic_context = semantic_context
            else:
                self._context.refresh_semantic_context()
                self._semantic_context = self._context.semantic_context
            if step_id is not None:
                executed_steps.append(step_id)
            if not result.success:
                rollback = self._rollback(snapshot)
                return self._structured_result(
                    plan=plan,
                    success=False,
                    precondition_results=precondition_results,
                    operation_results=tuple(operation_results),
                    raw_results=tuple(raw_results),
                    snapshot=snapshot,
                    executed_steps=tuple(executed_steps),
                    failed_step=step_id,
                    error=StructuredExecutionError(
                        code="operation_failed",
                        message="; ".join(result.diagnostics) or "Operation failed.",
                        step_id=step_id,
                    ),
                    rollback=rollback,
                    validations=(),
                )

        validation = self._validate_final(snapshot)
        if not validation.success:
            rollback = self._rollback(snapshot)
            restored_validation = self._validate_final(snapshot)
            return self._structured_result(
                plan=plan,
                success=False,
                precondition_results=precondition_results,
                operation_results=tuple(operation_results),
                raw_results=tuple(raw_results),
                snapshot=snapshot,
                executed_steps=tuple(executed_steps),
                failed_step=None,
                error=StructuredExecutionError(
                    code="final_validation_failed",
                    message="; ".join(validation.diagnostics),
                ),
                rollback=rollback,
                validations=(validation, restored_validation),
            )

        return self._structured_result(
            plan=plan,
            success=True,
            precondition_results=precondition_results,
            operation_results=tuple(operation_results),
            raw_results=tuple(raw_results),
            snapshot=snapshot,
            executed_steps=tuple(executed_steps),
            failed_step=None,
            error=None,
            rollback=RollbackResult(),
            validations=(validation,),
        )

    def _evaluate_global_preconditions(
        self,
        plan: ExecutionPlan,
    ) -> tuple[PreconditionResult, ...]:
        results: list[PreconditionResult] = []
        for precondition in plan.preconditions:
            results.append(precondition.evaluate(self._context))
        return tuple(results)

    def _evaluate_step_preconditions(self, request: ExecutionRequest) -> tuple[PreconditionResult, ...]:
        step_id = self._step_id(request)
        return tuple(
            precondition.evaluate(self._context, step_id)
            for precondition in request.metadata.get("preconditions", ())
            if isinstance(precondition, TransformationPrecondition)
        )

    def _precondition_failure(self, plan, results, failed, snapshot):
        return PipelineExecutionResult(
            success=False,
            plan_id=plan.plan_id,
            planned_steps=plan.planned_steps,
            executed_steps=(),
            failed_step=failed.step_id,
            error=StructuredExecutionError("precondition_failed", failed.message, failed.step_id),
            precondition_results=results,
        )

    def _path_failure(self, plan, results, error):
        return PipelineExecutionResult(
            success=False,
            plan_id=plan.plan_id,
            planned_steps=plan.planned_steps,
            executed_steps=(),
            precondition_results=results,
            error=StructuredExecutionError("path_error", str(error)),
        )

    def _enrich_request(
        self,
        request: ExecutionRequest,
        previous_result: ExecutionResult | None,
    ) -> ExecutionRequest:
        metadata = {
            **request.metadata,
            "semantic_context": self._semantic_context,
            "project_root": str(self._context.project_root),
            "execution_context": self._context,
            "previous_result": previous_result,
        }
        operation = request.operation
        if isinstance(operation, UpdateImportsOperation):
            if (
                operation.old_module is not None
                and operation.new_module is not None
                and operation.symbol_name is not None
            ):
                metadata.update(
                    {
                        "old_module": operation.old_module,
                        "new_module": operation.new_module,
                        "symbol_name": operation.symbol_name,
                        "new_symbol_name": operation.new_symbol_name
                        or operation.symbol_name,
                    }
                )
        if isinstance(operation, RenameSymbolOperation):
            metadata["module"] = operation.module or self._target_module(request)
        return ExecutionRequest(operation=operation, metadata=metadata)

    def _step_id(self, request: ExecutionRequest) -> str | None:
        step_id = request.metadata.get("step_id")
        return step_id if isinstance(step_id, str) else None

    def _snapshot(self, plan: ExecutionPlan) -> dict[Path, _SnapshotEntry]:
        paths: set[Path] = set()
        for request in plan.all_requests():
            paths.update(self._context.affected_paths_for(request.operation))
        return {
            path: _SnapshotEntry(
                existed=path.exists(),
                is_file=path.is_file(),
                content=path.read_bytes() if path.is_file() else None,
            )
            for path in sorted(paths)
        }

    def _rollback(self, snapshot: dict[Path, _SnapshotEntry]) -> RollbackResult:
        restored: list[Path] = []
        removed: list[Path] = []
        errors: list[str] = []
        for path, entry in snapshot.items():
            try:
                if not entry.existed:
                    if path.is_file():
                        path.unlink()
                        removed.append(path)
                    elif path.exists():
                        shutil.rmtree(path)
                        removed.append(path)
                    self._remove_empty_parents(path.parent)
                elif entry.is_file and entry.content is not None:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(entry.content)
                    restored.append(path)
            except OSError as error:
                errors.append(f"{path}: {error}")
        applied = bool(restored or removed) and not errors
        self._context.refresh_semantic_context()
        self._semantic_context = self._context.semantic_context
        return RollbackResult(
            attempted=True,
            applied=applied,
            restored_paths=tuple(restored),
            removed_created_paths=tuple(removed),
            errors=tuple(errors),
        )

    def _remove_empty_parents(self, path: Path) -> None:
        while path != self._context.project_root and path.is_relative_to(self._context.project_root):
            try:
                path.rmdir()
            except OSError:
                return
            path = path.parent

    def _validate_final(self, snapshot: dict[Path, _SnapshotEntry]) -> FinalValidationResult:
        checked_paths = tuple(
            sorted(
                path
                for path in snapshot
                if path.suffix == ".py" and path.is_file()
            )
        )
        self._context.refresh_semantic_context()
        diagnostics: list[str] = []
        for path in checked_paths:
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError, UnicodeError) as error:
                diagnostics.append(f"{path}: {error}")
        return FinalValidationResult(
            success=not diagnostics,
            diagnostics=tuple(diagnostics),
            checked_paths=checked_paths,
        )

    def _structured_result(
        self,
        *,
        plan: ExecutionPlan,
        success: bool,
        precondition_results: tuple[PreconditionResult, ...],
        operation_results: tuple[OperationResultRecord, ...],
        raw_results: tuple[ExecutionResult, ...],
        snapshot: dict[Path, _SnapshotEntry],
        executed_steps: tuple[str, ...],
        failed_step: str | None,
        error: StructuredExecutionError | None,
        rollback: RollbackResult,
        validations: tuple[FinalValidationResult, ...],
    ) -> PipelineExecutionResult:
        created, modified, deleted = self._diff_paths(plan, raw_results, snapshot)
        return PipelineExecutionResult(
            success=success,
            plan_id=plan.plan_id,
            planned_steps=plan.planned_steps,
            executed_steps=executed_steps,
            failed_step=failed_step,
            error=error,
            precondition_results=precondition_results,
            operation_results=operation_results,
            validations=validations,
            rollback_attempted=rollback.attempted,
            rollback_applied=rollback.applied,
            rollback_restored_paths=rollback.restored_paths + rollback.removed_created_paths,
            rollback_errors=rollback.errors,
            created_paths=created,
            modified_paths=modified,
            deleted_paths=deleted,
        )

    def _diff_paths(
        self,
        plan: ExecutionPlan,
        raw_results: tuple[ExecutionResult, ...],
        snapshot: dict[Path, bytes | None],
    ) -> tuple[tuple[Path, ...], tuple[Path, ...], tuple[Path, ...]]:
        affected: set[Path] = set()
        for request in plan.all_requests():
            affected.update(self._context.affected_paths_for(request.operation))
        for result in raw_results:
            affected.update(
                self._context.resolve_project_path(path)
                for path in result.created_paths
            )
            deleted_paths = result.metadata.get("deleted_paths", ())
            if isinstance(deleted_paths, tuple):
                affected.update(
                    self._context.resolve_project_path(path)
                    for path in deleted_paths
                    if isinstance(path, Path)
                )
        created: set[Path] = set()
        modified: set[Path] = set()
        deleted: set[Path] = set()
        all_created_paths = {
            self._context.resolve_project_path(created_path)
            for result in raw_results
            for created_path in result.created_paths
        }
        result_created_paths = {
            path
            for path in all_created_paths
            if not any(other != path and path in other.parents for other in all_created_paths)
        }
        result_deleted_paths = set()
        for result in raw_results:
            deleted_paths = result.metadata.get("deleted_paths", ())
            if isinstance(deleted_paths, tuple):
                result_deleted_paths.update(
                    self._context.resolve_project_path(path)
                    for path in deleted_paths
                    if isinstance(path, Path)
                )
        for path in sorted(affected):
            snapshot_entry = snapshot.get(path)
            existed_before = snapshot_entry is not None and snapshot_entry.existed
            if path in result_deleted_paths:
                deleted.add(path)
            elif path in result_created_paths and not existed_before:
                created.add(path)
            elif existed_before and path in result_created_paths:
                modified.add(path)
        return tuple(sorted(created)), tuple(sorted(modified)), tuple(sorted(deleted))

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
