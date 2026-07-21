"""Supervised execution, validation, diff, and rollback orchestration."""

from __future__ import annotations

import ast
import difflib
from dataclasses import replace
from pathlib import Path, PurePath
from time import perf_counter
from typing import Callable, Iterable, Mapping

from cmm.development.analyzer import ProjectAnalyzer
from cmm.development.models import (
    DevelopmentPlan,
    DevelopmentResult,
    PlanValidationError,
    ValidationRecord,
)
from cmm.development.providers import PlanningProvider
from kernel.protocol.parser import PlanParser
from kernel.semantic import SemanticOperation, SemanticRuntime
from kernel.semantic_executors import create_default_semantic_registry


_ALLOWED_VALIDATIONS = {"python_ast", "python_compile"}


class DevelopmentService:
    """Execute one human-supervised development plan without retries."""

    def __init__(
        self,
        provider: PlanningProvider,
        runtime: SemanticRuntime | None = None,
        analyzer: ProjectAnalyzer | None = None,
        parser: PlanParser | None = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        self.provider = provider
        self.runtime = runtime or SemanticRuntime(create_default_semantic_registry())
        self.analyzer = analyzer or ProjectAnalyzer()
        self.parser = parser or PlanParser()
        self.input_fn = input_fn
        self.output_fn = output_fn

    def develop(
        self,
        goal: str,
        project: Path,
        *,
        yes: bool = False,
        dry_run: bool = False,
        max_files: int = 40,
        validations: Iterable[str] | None = None,
        plan_override: DevelopmentPlan | Mapping[str, object] | None = None,
    ) -> DevelopmentResult:
        started = perf_counter()
        plan: DevelopmentPlan | None = None
        root: Path | None = None
        snapshots: Mapping[str, tuple[Path, bytes | None]] | None = None
        execution_results = []
        approved = False
        try:
            root = self._validate_project(project)
            context = self.analyzer.analyze(root, goal, max_files=max_files)
            generated = plan_override if plan_override is not None else self.provider.generate_plan(goal, context)
            plan = generated if isinstance(generated, DevelopmentPlan) else DevelopmentPlan.from_mapping(generated, goal)
            plan.validate()
            if plan.goal != goal.strip():
                raise PlanValidationError("The plan goal does not match the requested goal.")
            paths = self._resolve_plan_paths(root, plan)
            semantic_operations = self._normalize_operations(root, plan.to_semantic_operations(self.parser))
            self._validate_executors(semantic_operations)
            validation_names = self._validation_names(plan, validations)
            self._present_plan(plan, context.total_python_files, context.truncated)

            if dry_run:
                return self._result(
                    started,
                    success=True,
                    goal=goal,
                    plan=plan,
                    dry_run=True,
                    warnings=("Dry run: no changes were applied.",),
                )
            approved = yes or self.input_fn("¿Aplicar cambios? [y/N] ").strip().lower() in {"y", "yes"}
            if not approved:
                return self._result(
                    started,
                    success=True,
                    goal=goal,
                    plan=plan,
                    warnings=("Plan rejected; no changes were applied.",),
                )

            snapshots = self._snapshot(paths)
            execution_error: str | None = None
            for operation in semantic_operations:
                result = self.runtime.execute_operation(operation)
                execution_results.append(result)
                if not result.success:
                    execution_error = result.message
                    break

            attempted_diff, modified = self._diff(snapshots)
            if execution_error is not None:
                self._restore(root, snapshots)
                return self._result(
                    started,
                    success=False,
                    goal=goal,
                    plan=plan,
                    operations_executed=tuple(execution_results),
                    modified_files=modified,
                    diff=attempted_diff,
                    errors=(execution_error,),
                    approved=True,
                    rollback_applied=True,
                )

            validation_records = self._run_validations(paths, validation_names)
            validation_errors = tuple(record.message for record in validation_records if not record.success)
            final_diff, modified = self._diff(snapshots)
            if validation_errors:
                self._restore(root, snapshots)
                return self._result(
                    started,
                    success=False,
                    goal=goal,
                    plan=plan,
                    operations_executed=tuple(execution_results),
                    modified_files=modified,
                    diff=final_diff,
                    validations=validation_records,
                    errors=validation_errors,
                    approved=True,
                    rollback_applied=True,
                )
            warnings = tuple(
                warning
                for result in execution_results
                for warning in result.data.get("warnings", ())
            ) + plan.risks
            return self._result(
                started,
                success=True,
                goal=goal,
                plan=plan,
                operations_executed=tuple(execution_results),
                modified_files=modified,
                diff=final_diff,
                validations=validation_records,
                warnings=warnings,
                approved=True,
            )
        except Exception as error:
            rollback_applied = False
            diff = ""
            modified: tuple[str, ...] = ()
            errors = [str(error)]
            if snapshots is not None and root is not None:
                try:
                    diff, modified = self._diff(snapshots)
                except Exception:
                    pass
                try:
                    self._restore(root, snapshots)
                    rollback_applied = True
                except Exception as rollback_error:
                    errors.append(f"Rollback failed: {rollback_error}")
            return self._result(
                started,
                success=False,
                goal=goal,
                plan=plan,
                operations_executed=tuple(execution_results),
                modified_files=modified,
                diff=diff,
                errors=tuple(errors),
                approved=approved,
                rollback_applied=rollback_applied,
            )

    def _validate_project(self, project: Path) -> Path:
        candidate = Path(project)
        if not candidate.exists():
            raise PlanValidationError(f"Project path does not exist: {candidate}")
        if not candidate.is_dir():
            raise PlanValidationError(f"Project path is not a directory: {candidate}")
        return candidate.resolve(strict=True)

    def _resolve_plan_paths(self, root: Path, plan: DevelopmentPlan) -> Mapping[str, Path]:
        paths = {relative: self._safe_path(root, relative) for relative in plan.affected_files}
        for operation in plan.operations:
            if "path" in operation.parameters:
                relative = str(operation.parameters["path"])
                if relative not in paths:
                    raise PlanValidationError(f"Operation path is not declared as affected: {relative}")
        for path in paths.values():
            if path.exists() and path.is_dir():
                raise PlanValidationError(f"Affected path is a directory, not a file: {path}")
        return paths

    def _safe_path(self, root: Path, value: str) -> Path:
        raw = PurePath(value)
        if raw.is_absolute():
            raise PlanValidationError(f"Absolute operation paths are not allowed: {value}")
        if ".." in raw.parts:
            raise PlanValidationError(f"Parent path traversal is not allowed: {value}")
        candidate = (root / Path(*raw.parts)).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise PlanValidationError(f"Path escapes the project: {value}") from error
        return candidate

    def _normalize_operations(
        self,
        root: Path,
        operations: tuple[SemanticOperation, ...],
    ) -> tuple[SemanticOperation, ...]:
        normalized = []
        for operation in operations:
            parameters = dict(operation.parameters)
            if "path" in parameters:
                parameters["path"] = str(self._safe_path(root, str(parameters["path"])))
            normalized.append(replace(operation, parameters=parameters))
        return tuple(normalized)

    def _validate_executors(self, operations: tuple[SemanticOperation, ...]) -> None:
        for operation in operations:
            self.runtime.registry.resolve(operation)

    def _validation_names(self, plan: DevelopmentPlan, configured: Iterable[str] | None) -> tuple[str, ...]:
        requested = tuple(configured) if configured is not None else plan.validations
        names = tuple(dict.fromkeys((*requested, "python_compile")))
        unknown = set(names).difference(_ALLOWED_VALIDATIONS)
        if unknown:
            raise PlanValidationError("Unsupported validation: " + ", ".join(sorted(unknown)))
        return names

    def _present_plan(self, plan: DevelopmentPlan, file_count: int, truncated: bool) -> None:
        self.output_fn(f"Goal: {plan.goal}")
        self.output_fn(f"Project analysis: {file_count} Python files" + (" (context limited)" if truncated else ""))
        self.output_fn("Affected files:")
        for path in plan.affected_files:
            self.output_fn(f"- {path}")
        self.output_fn("Operations:")
        for index, operation in enumerate(plan.operations, start=1):
            suffix = f" - {operation.reason}" if operation.reason else ""
            self.output_fn(f"{index}. {operation.domain}.{operation.operation_type}{suffix}")
        self.output_fn("Validations: " + ", ".join(plan.validations))
        if plan.risks:
            self.output_fn("Risks: " + "; ".join(plan.risks))

    def _snapshot(self, paths: Mapping[str, Path]) -> dict[str, tuple[Path, bytes | None]]:
        return {
            relative: (path, path.read_bytes() if path.exists() else None)
            for relative, path in paths.items()
        }

    def _restore(self, root: Path, snapshots: Mapping[str, tuple[Path, bytes | None]]) -> None:
        for path, content in snapshots.values():
            if content is None:
                if path.exists() and path.is_file():
                    path.unlink()
                elif path.exists() and path.is_dir():
                    try:
                        path.rmdir()
                    except OSError:
                        pass
                self._remove_empty_parents(root, path.parent)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

    def _remove_empty_parents(self, root: Path, path: Path) -> None:
        while path != root and path.exists() and path.is_dir():
            try:
                path.rmdir()
            except OSError:
                break
            path = path.parent

    def _run_validations(
        self,
        paths: Mapping[str, Path],
        names: tuple[str, ...],
    ) -> tuple[ValidationRecord, ...]:
        records = []
        python_paths = [(relative, path) for relative, path in paths.items() if path.suffix == ".py" and path.exists()]
        for name in names:
            try:
                for relative, path in python_paths:
                    source = path.read_text(encoding="utf-8")
                    if name == "python_ast":
                        ast.parse(source, filename=relative)
                    elif name == "python_compile":
                        compile(source, relative, "exec")
                records.append(ValidationRecord(name, True, f"Validated {len(python_paths)} Python file(s)."))
            except (SyntaxError, UnicodeDecodeError) as error:
                records.append(ValidationRecord(name, False, f"{name} failed: {error}"))
        return tuple(records)

    def _diff(self, snapshots: Mapping[str, tuple[Path, bytes | None]]) -> tuple[str, tuple[str, ...]]:
        chunks = []
        modified = []
        for relative, (path, before_bytes) in snapshots.items():
            after_bytes = path.read_bytes() if path.exists() and path.is_file() else None
            if before_bytes == after_bytes:
                continue
            modified.append(relative)
            before = (before_bytes or b"").decode("utf-8", errors="replace").splitlines(keepends=True)
            after = (after_bytes or b"").decode("utf-8", errors="replace").splitlines(keepends=True)
            chunks.extend(
                difflib.unified_diff(
                    before,
                    after,
                    fromfile=f"a/{relative}",
                    tofile=f"b/{relative}",
                )
            )
        return "".join(chunks), tuple(modified)

    def _result(self, started: float, **values) -> DevelopmentResult:
        return DevelopmentResult(duration_seconds=perf_counter() - started, **values)
