"""End-to-end orchestration for planning and executing project edits."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kernel.planner.bootstrap import create_default_registry
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.executor import ExecutionResult, Executor
from kernel.planner.mock_llm_provider import MockLLMProvider
from kernel.planner.operation_planner import OperationPlanner
from kernel.planner.plan_validator import PlanValidator, ValidationResult
from kernel.planner.planner_strategy import LLMPlannerStrategy
from kernel.services.project_analyzer import ProjectAnalyzer
from kernel.services.python_editor import PythonEditor


@dataclass(frozen=True, slots=True)
class EndToEndResult:
    """Structured result returned by the end-to-end runner."""

    goal: str
    project_path: Path
    execution_plan: ExecutionPlan
    validation_result: ValidationResult
    execution_result: ExecutionResult | None
    modified_files: tuple[Path, ...] = field(default_factory=tuple)

    @property
    def success(self) -> bool:
        """Return whether the end-to-end run completed successfully."""

        return self.validation_result.valid and self.execution_result is not None and self.execution_result.success

    @property
    def errors(self) -> tuple[str, ...]:
        """Return all execution errors."""

        validation_errors = tuple(self.validation_result.errors)
        execution_errors = tuple(self.execution_result.errors) if self.execution_result is not None else tuple()
        return validation_errors + execution_errors


class _ProjectPythonEngine:
    """Adapter that applies planner operations to a Python project tree."""

    def __init__(self, project_path: Path) -> None:
        self.project_path = Path(project_path)
        self.editor = PythonEditor()
        self.analyzer = ProjectAnalyzer(self.project_path)
        self.modified_files: list[Path] = []

    def create_class(self, class_name: str) -> bool:
        path = self._resolve_module_path(class_name)
        changed = self.editor.create_class(path, class_name)
        self._record_change(path, changed)
        return changed

    def insert_method(self, target_class: str, method_name: str, source_code: str) -> bool:
        path = self._resolve_class_path(target_class)
        changed = self.editor.insert_method(path, target_class, "end", source_code)
        self._record_change(path, changed)
        return changed

    def replace_method(self, target_class: str, method_name: str, source_code: str) -> bool:
        path = self._resolve_class_path(target_class)
        changed = self.editor.replace_method(path, target_class, method_name, source_code)
        self._record_change(path, changed)
        return changed

    def ensure_import(self, module: str, name: str | None) -> bool:
        path = self._resolve_primary_path()
        changed = self.editor.ensure_import(path, module, name=name)
        self._record_change(path, changed)
        return changed

    def _resolve_class_path(self, class_name: str) -> Path:
        for relative_path in self.analyzer.python_files():
            path = self.project_path / relative_path
            if self.editor.locator.find_class(path, class_name) is not None:
                return path

        raise FileNotFoundError(f"Class {class_name!r} was not found under {self.project_path}")

    def _resolve_module_path(self, class_name: str) -> Path:
        try:
            return self._resolve_class_path(class_name)
        except FileNotFoundError:
            return self._resolve_primary_path()

    def _resolve_primary_path(self) -> Path:
        python_files = self.analyzer.python_files()
        if not python_files:
            raise FileNotFoundError(f"No Python files found under {self.project_path}")

        return self.project_path / python_files[0]

    def _record_change(self, path: Path, changed: bool) -> None:
        if changed and path not in self.modified_files:
            self.modified_files.append(path)


@dataclass(slots=True)
class EndToEndRunner:
    """Execute a natural-language goal against a Python project."""

    planner: OperationPlanner = field(
        default_factory=lambda: OperationPlanner(
            strategy=LLMPlannerStrategy(provider=MockLLMProvider())
        )
    )
    validator: PlanValidator = field(default_factory=PlanValidator)

    def run(self, goal: str, project_path: Path) -> EndToEndResult:
        project_path = Path(project_path)
        plan = self.planner.plan(goal)
        validation_result = self.validator.validate(plan)

        if validation_result.has_errors():
            return EndToEndResult(
                goal=goal,
                project_path=project_path,
                execution_plan=plan,
                validation_result=validation_result,
                execution_result=None,
                modified_files=tuple(),
            )

        engine = _ProjectPythonEngine(project_path)
        executor = Executor(engine=engine, registry=create_default_registry())
        execution_result = executor.execute(plan)

        return EndToEndResult(
            goal=goal,
            project_path=project_path,
            execution_plan=plan,
            validation_result=validation_result,
            execution_result=execution_result,
            modified_files=tuple(engine.modified_files),
        )
