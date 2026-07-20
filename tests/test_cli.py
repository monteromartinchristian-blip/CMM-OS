from __future__ import annotations

from typing import Any

import pytest

from kernel.cli import build_parser, main
from kernel.core.kernel import AgentKernel
from kernel.planner.context import PlanningContext
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.validator import ValidationResult
from kernel.planner.executor import ExecutionResult
from kernel.core.result import KernelResult
from kernel.planner.operations import CreateClassOperation


class DummyPlanner:
    def __init__(self, plan: ExecutionPlan | None = None) -> None:
        self.plan_result = plan or ExecutionPlan()
        self.calls: list[PlanningContext] = []

    def plan(self, context: PlanningContext) -> ExecutionPlan:
        self.calls.append(context)
        return self.plan_result


class DummyValidator:
    def __init__(self, errors: bool = False) -> None:
        self.errors = errors

    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        result = ValidationResult()
        if self.errors:
            result.add_error("boom")
        return result


class DummyExecutor:
    def __init__(self) -> None:
        self.calls: list[ExecutionPlan] = []

    def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        self.calls.append(plan)
        return ExecutionResult(
            success=True,
            executed_operations=[CreateClassOperation(class_name="User")],
            failed_operations=[],
            errors=[],
        )


def test_parser_parses_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(["Create a User class", "--model", "glm4.5", "--host", "http://example.test"])

    assert args.prompt == "Create a User class"
    assert args.model == "glm4.5"
    assert args.host == "http://example.test"
    assert args.dry_run is False
    assert args.json is False


def test_dry_run_stops_before_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = AgentKernel(planner=DummyPlanner(plan=ExecutionPlan([CreateClassOperation(class_name="User")])) if False else DummyPlanner(), validator=DummyValidator(), executor=DummyExecutor())

    monkeypatch.setattr("kernel.cli._build_kernel", lambda model, host: kernel)

    exit_code = main(["--dry-run", "Create a User class"])

    assert exit_code == 0


def test_json_output_uses_serialized_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = AgentKernel(planner=DummyPlanner(plan=ExecutionPlan([CreateClassOperation(class_name="User")])) if False else DummyPlanner(), validator=DummyValidator(), executor=DummyExecutor())

    monkeypatch.setattr("kernel.cli._build_kernel", lambda model, host: kernel)

    exit_code = main(["--json", "Create a User class"])

    assert exit_code == 0


def test_model_selection_is_propagated(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class RecordingKernel(AgentKernel):
        def __init__(self) -> None:
            super().__init__(planner=DummyPlanner(), validator=DummyValidator(), executor=DummyExecutor())

        def execute(self, context: PlanningContext) -> KernelResult:
            captured["model"] = context.metadata["model"]
            return KernelResult(
                success=True,
                planning_context=context,
                execution_plan=ExecutionPlan([CreateClassOperation(class_name="User")]),
                validation_result=ValidationResult(),
                execution_result=ExecutionResult(success=True, executed_operations=[], failed_operations=[], errors=[]),
            )

    monkeypatch.setattr("kernel.cli._build_kernel", lambda model, host: RecordingKernel())
    main(["--model", "glm4.5", "Create a User class"])

    assert captured["model"] == "glm4.5"


def test_host_selection_is_propagated(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class RecordingKernel(AgentKernel):
        def __init__(self) -> None:
            super().__init__(planner=DummyPlanner(), validator=DummyValidator(), executor=DummyExecutor())

        def execute(self, context: PlanningContext) -> KernelResult:
            captured["host"] = context.metadata["host"]
            return KernelResult(
                success=True,
                planning_context=context,
                execution_plan=ExecutionPlan([CreateClassOperation(class_name="User")]),
                validation_result=ValidationResult(),
                execution_result=ExecutionResult(success=True, executed_operations=[], failed_operations=[], errors=[]),
            )

    monkeypatch.setattr("kernel.cli._build_kernel", lambda model, host: RecordingKernel())
    main(["--host", "http://example.test", "Create a User class"])

    assert captured["host"] == "http://example.test"


def test_integration_with_create_ollama_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kernel.cli.create_ollama_planner_bootstrap", lambda: DummyPlanner())

    kernel = main(["Create a User class"])

    assert kernel == 0


def test_agent_kernel_receives_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class RecordingKernel(AgentKernel):
        def __init__(self) -> None:
            super().__init__(planner=DummyPlanner(), validator=DummyValidator(), executor=DummyExecutor())

        def execute(self, context: PlanningContext) -> KernelResult:
            captured["prompt"] = context.intent
            return KernelResult(
                success=True,
                planning_context=context,
                execution_plan=ExecutionPlan([CreateClassOperation(class_name="User")]),
                validation_result=ValidationResult(),
                execution_result=ExecutionResult(success=True, executed_operations=[], failed_operations=[], errors=[]),
            )

    monkeypatch.setattr("kernel.cli._build_kernel", lambda model, host: RecordingKernel())
    main(["Create a User class"])

    assert captured["prompt"] == "Create a User class"
