"""Phase 5 coordination of real project actions with snapshots and review output."""

from __future__ import annotations

import ast
import difflib
from pathlib import Path, PurePath
from time import perf_counter
from typing import Any, Callable, Iterable, Mapping

from cmm.development.analyzer import ProjectAnalyzer
from cmm.development.models import DevelopmentPlan, DevelopmentResult, PlanValidationError, ValidationRecord
from cmm.development.providers import PlanningProvider
from cmm.execution import Action, ActionPlanner, ActionType, create_default_executor_registry
from cmm.runtime import ActionRuntime
from cmm.memory import TechnicalMemory, TechnicalReasoner
from cmm.planner import TaskPlanner
from kernel.semantic import SemanticOperation, SemanticResult


_ACTION_TYPES = {item.value: item for item in ActionType}
_ALLOWED_VALIDATIONS = {"python_ast", "python_compile"}


class AutonomousExecutionService:
    """Execute one real, bounded project change; Fase 3 owns iteration."""

    supports_project_actions = True

    def __init__(
        self,
        provider: PlanningProvider,
        *,
        analyzer: ProjectAnalyzer | None = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        self.provider = provider
        self.analyzer = analyzer or ProjectAnalyzer()
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
        plan_override: DevelopmentPlan | Mapping[str, Any] | None = None,
        isolate: bool = False,
        branch_name: str | None = None,
        keep_changes: bool = True,
        restore: bool = False,
    ) -> DevelopmentResult:
        started = perf_counter()
        root: Path | None = None
        snapshots: dict[str, tuple[Path, bytes | None]] = {}
        plan: DevelopmentPlan | None = None
        actions: list[Action] = []
        executed: list[dict[str, Any]] = []
        try:
            root = self._project(project)
            memory = TechnicalMemory.for_project(root)
            memory.load()
            memory.refresh()
            reasoner = TechnicalReasoner(memory)
            task_planner = TaskPlanner(reasoner)
            technical_plan = task_planner.create_plan(goal)
            action_planner = ActionPlanner(task_planner)
            context = self.analyzer.analyze(root, goal, max_files=max_files)
            generated = plan_override if plan_override is not None else self.provider.generate_plan(goal, context)
            plan = generated if isinstance(generated, DevelopmentPlan) else DevelopmentPlan.from_mapping(generated, goal)
            plan.validate()
            actions = self._actions(root, plan, action_planner, isolate=isolate, branch_name=branch_name)
            action_validation = action_planner.validate(actions)
            if not action_validation["valid"]:
                raise PlanValidationError("Invalid action queue: " + " ".join(action_validation["errors"]))
            validation_names = self._validations(plan, validations)
            snapshots = self._snapshot(root, plan)
            self._present(plan, actions, context.total_python_files, context.truncated)
            if dry_run:
                return self._result(started, True, goal, plan, dry_run=True, approved=True, actions=actions, review_ready=True)
            approved = yes or self.input_fn("¿Aplicar cambios? [y/N] ").strip().lower() in {"y", "yes"}
            if not approved:
                return self._result(started, True, goal, plan, approved=False, actions=actions, warnings=("Plan rejected; no changes were applied.",))

            runtime = ActionRuntime(action_planner, registry=create_default_executor_registry(), working_directory=root)
            runtime_result = runtime.execute(actions)
            executed = [self._execution_payload(item) for item in runtime_result.executions]
            diff, modified = self._diff(snapshots)
            if not runtime_result.success:
                self._restore(snapshots)
                return self._result(started, False, goal, plan, approved=True, actions=actions, executed=executed, modified=modified, diff=diff, errors=runtime_result.errors, rollback=True)

            validation_records = self._validate(snapshots, validation_names)
            validation_errors = tuple(item.message for item in validation_records if not item.success)
            if validation_errors or restore:
                self._restore(snapshots)
                return self._result(started, not validation_errors, goal, plan, approved=True, actions=actions, executed=executed, modified=modified, diff=diff, validations=validation_records, errors=validation_errors, warnings=("Changes restored by request.",) if restore else (), rollback=True)

            refresh = memory.refresh()
            if not refresh.success:
                self._restore(snapshots)
                return self._result(started, False, goal, plan, approved=True, actions=actions, executed=executed, modified=modified, diff=diff, validations=validation_records, errors=refresh.errors or ("Technical memory refresh failed.",), rollback=True)
            created, deleted = self._created_deleted(snapshots)
            return self._result(started, True, goal, plan, approved=True, actions=actions, executed=executed, modified=modified, diff=diff, validations=validation_records, created=created, deleted=deleted, memory_refreshed=True, review_ready=keep_changes)
        except Exception as error:
            if snapshots:
                self._restore(snapshots)
            return self._result(started, False, goal, plan, approved=bool(actions), actions=actions, executed=executed, errors=(str(error),), rollback=bool(snapshots))

    def _project(self, project: Path) -> Path:
        root = Path(project).resolve(strict=True)
        if not root.is_dir():
            raise PlanValidationError(f"Project path is not a directory: {project}")
        return root

    def _validate_project(self, project: Path) -> Path:
        """Compatibility hook used by the Phase 3 correction planner."""
        return self._project(project)

    def _actions(self, root: Path, plan: DevelopmentPlan, action_planner: ActionPlanner, *, isolate: bool, branch_name: str | None) -> list[Action]:
        actions: list[Action] = []
        if isolate:
            actions.append(Action("action-1", 1, ActionType.GIT_CREATE_BRANCH, ".", "Create isolated review branch.", {"branch": branch_name or f"cmm-review-{int(perf_counter() * 1000)}"}))
        operation_actions = action_planner.create_operation_actions(list(plan.operations))
        for operation_action in operation_actions:
            action_type = operation_action.action_type
            qualified = action_type.value
            parameters = dict(operation_action.metadata)
            path = parameters.get("path", ".")
            if not isinstance(path, str):
                raise PlanValidationError(f"Action path must be a string: {qualified}")
            safe = self._safe_path(root, path)
            parameters["path"] = str(safe)
            if "destination" in parameters:
                parameters["destination"] = str(self._safe_path(root, str(parameters["destination"])))
            actions.append(Action(f"action-{len(actions) + 1}", len(actions) + 1, action_type, path, qualified, parameters))
        return actions

    def _safe_path(self, root: Path, value: str) -> Path:
        raw = PurePath(value)
        if raw.is_absolute() or ".." in raw.parts:
            raise PlanValidationError(f"Unsafe project path: {value}")
        candidate = (root / Path(*raw.parts)).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise PlanValidationError(f"Path escapes project: {value}") from error
        return candidate

    def _snapshot(self, root: Path, plan: DevelopmentPlan) -> dict[str, tuple[Path, bytes | None]]:
        paths: set[str] = set(plan.affected_files)
        for operation in plan.operations:
            for key in ("path", "destination"):
                if key in operation.parameters:
                    paths.add(str(operation.parameters[key]))
        result = {}
        for relative in paths:
            path = self._safe_path(root, relative)
            result[relative] = (path, path.read_bytes() if path.is_file() else None)
        return result

    def _restore(self, snapshots: Mapping[str, tuple[Path, bytes | None]]) -> None:
        for path, content in snapshots.values():
            if content is None:
                if path.is_file():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

    def _validate(self, snapshots: Mapping[str, tuple[Path, bytes | None]], names: tuple[str, ...]) -> tuple[ValidationRecord, ...]:
        records = []
        for name in names:
            try:
                for relative, (path, _) in snapshots.items():
                    if path.suffix != ".py" or not path.is_file():
                        continue
                    source = path.read_text(encoding="utf-8")
                    if name == "python_ast":
                        ast.parse(source, filename=relative)
                    else:
                        compile(source, relative, "exec")
                records.append(ValidationRecord(name, True, f"Validated project Python files for {name}."))
            except (SyntaxError, UnicodeDecodeError) as error:
                records.append(ValidationRecord(name, False, f"{name} failed: {error}"))
        return tuple(records)

    def _validations(self, plan: DevelopmentPlan, configured: Iterable[str] | None) -> tuple[str, ...]:
        names = tuple(dict.fromkeys(tuple(configured) if configured is not None else plan.validations))
        unknown = set(names).difference(_ALLOWED_VALIDATIONS)
        if unknown:
            raise PlanValidationError("Unsupported validation: " + ", ".join(sorted(unknown)))
        return names or ("python_ast", "python_compile")

    def _diff(self, snapshots: Mapping[str, tuple[Path, bytes | None]]) -> tuple[str, tuple[str, ...]]:
        chunks: list[str] = []
        modified: list[str] = []
        for relative, (path, before_bytes) in snapshots.items():
            after_bytes = path.read_bytes() if path.is_file() else None
            if after_bytes == before_bytes:
                continue
            modified.append(relative)
            before = (before_bytes or b"").decode("utf-8", errors="replace").splitlines(keepends=True)
            after = (after_bytes or b"").decode("utf-8", errors="replace").splitlines(keepends=True)
            chunks.extend(difflib.unified_diff(before, after, fromfile=f"a/{relative}", tofile=f"b/{relative}"))
        return "".join(chunks), tuple(sorted(modified))

    def _created_deleted(self, snapshots: Mapping[str, tuple[Path, bytes | None]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        created = tuple(sorted(relative for relative, (path, before) in snapshots.items() if before is None and path.is_file()))
        deleted = tuple(sorted(relative for relative, (path, before) in snapshots.items() if before is not None and not path.exists()))
        return created, deleted

    def _execution_payload(self, execution: object) -> dict[str, Any]:
        action = getattr(execution, "action", None)
        result = getattr(execution, "result", None)
        return {"action_id": str(getattr(action, "id", "")), "type": str(getattr(getattr(action, "action_type", None), "value", "")), "status": getattr(getattr(execution, "status", None), "value", str(getattr(execution, "status", ""))), "success": bool(getattr(result, "success", False)), "message": str(getattr(result, "message", "")), "metadata": dict(getattr(result, "metadata", {}) or {})}

    def _present(self, plan: DevelopmentPlan, actions: list[Action], files: int, truncated: bool) -> None:
        self.output_fn(f"Goal: {plan.goal}")
        self.output_fn(f"Project analysis: {files} Python files" + (" (context limited)" if truncated else ""))
        self.output_fn("Actions:")
        for action in actions:
            self.output_fn(f"{action.order}. {action.action_type.value} {action.target}")

    def _result(self, started: float, success: bool, goal: str, plan: DevelopmentPlan | None, *, approved: bool = False, dry_run: bool = False, actions: list[Action] = (), executed: list[dict[str, Any]] = (), modified: tuple[str, ...] = (), diff: str = "", validations: tuple[ValidationRecord, ...] = (), errors: tuple[str, ...] = (), warnings: tuple[str, ...] = (), rollback: bool = False, created: tuple[str, ...] = (), deleted: tuple[str, ...] = (), memory_refreshed: bool = False, review_ready: bool = False) -> DevelopmentResult:
        semantic_results = tuple(SemanticResult(item["success"], item["message"], errors=(item["message"],) if not item["success"] else ()) for item in executed)
        git_state = {item["type"]: item.get("metadata", {}) for item in executed if item.get("type", "").startswith("git.")}
        return DevelopmentResult(success, goal, plan, semantic_results, modified, diff, validations, warnings, errors, approved, dry_run, rollback, perf_counter() - started, tuple({"id": action.id, "type": action.action_type.value, "target": action.target, "metadata": dict(action.metadata)} for action in actions), tuple(executed), created, deleted, git_state, memory_refreshed, review_ready)
