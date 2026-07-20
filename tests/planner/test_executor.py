from __future__ import annotations

from typing import Any

import pytest

from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.exceptions import PlannerError
from kernel.planner.executor import ExecutionResult, Executor
from kernel.planner.operations import CreateClassOperation, EnsureImportOperation, InsertMethodOperation, ReplaceMethodOperation
from kernel.planner.registry import CreateClassHandler, EnsureImportHandler, InsertMethodHandler, OperationRegistry, ReplaceMethodHandler


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def create_class(self, class_name: str) -> str:
        self.calls.append(("create_class", (class_name,), {}))
        return f"created:{class_name}"

    def insert_method(self, target_class: str, method_name: str, source_code: str) -> str:
        self.calls.append(("insert_method", (target_class, method_name, source_code), {}))
        return f"inserted:{target_class}:{method_name}"

    def replace_method(self, target_class: str, method_name: str, source_code: str) -> str:
        self.calls.append(("replace_method", (target_class, method_name, source_code), {}))
        return f"replaced:{target_class}:{method_name}"

    def ensure_import(self, module: str, name: str | None) -> str:
        self.calls.append(("ensure_import", (module, name), {}))
        return f"imported:{module}:{name}"


class FailingEngine(FakeEngine):
    def insert_method(self, target_class: str, method_name: str, source_code: str) -> str:
        raise RuntimeError("boom")


def build_registry() -> OperationRegistry:
    registry = OperationRegistry()
    registry.register(CreateClassOperation, CreateClassHandler())
    registry.register(InsertMethodOperation, InsertMethodHandler())
    registry.register(ReplaceMethodOperation, ReplaceMethodHandler())
    registry.register(EnsureImportOperation, EnsureImportHandler())
    return registry


def test_executor_executes_a_single_operation() -> None:
    engine = FakeEngine()
    executor = Executor(engine, build_registry())
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="Widget"))

    result = executor.execute(plan)

    assert result.success is True
    assert len(result.executed_operations) == 1
    assert engine.calls[0][0] == "create_class"


def test_executor_executes_operations_in_order() -> None:
    engine = FakeEngine()
    executor = Executor(engine, build_registry())
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="Widget"))
    plan.add(InsertMethodOperation(target_class="Widget", method_name="run", source_code="def run(self): pass"))

    result = executor.execute(plan)

    assert result.success is True
    assert [call[0] for call in engine.calls] == ["create_class", "insert_method"]


def test_executor_executes_replace_method_operation() -> None:
    engine = FakeEngine()
    executor = Executor(engine, build_registry())
    plan = ExecutionPlan()
    plan.add(
        ReplaceMethodOperation(
            target_class="Widget",
            method_name="run",
            source_code="def run(self):\n    return True",
        )
    )

    result = executor.execute(plan)

    assert result.success is True
    assert len(result.executed_operations) == 1
    assert engine.calls[0][0] == "replace_method"
    assert engine.calls[0][1] == ("Widget", "run", "def run(self):\n    return True")


def test_executor_uses_planning_engine_order_for_dependencies() -> None:
    engine = FakeEngine()
    executor = Executor(engine, build_registry())

    root = CreateClassOperation(class_name="User")
    child = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self): pass",
        depends_on=(root.operation_id,),
    )

    plan = ExecutionPlan()
    plan.extend([root, child])

    result = executor.execute(plan)

    assert result.success is True
    assert [call[0] for call in engine.calls] == ["create_class", "insert_method"]


def test_executor_uses_the_registered_handler() -> None:
    registry = OperationRegistry()
    registry.register(CreateClassOperation, CreateClassHandler())

    executor = Executor(FakeEngine(), registry)
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="Widget"))

    result = executor.execute(plan)

    assert result.success is True
    assert len(result.executed_operations) == 1


def test_executor_fails_when_no_handler_registered() -> None:
    executor = Executor(FakeEngine(), OperationRegistry())
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="Widget"))

    result = executor.execute(plan)

    assert result.success is False
    assert len(result.failed_operations) == 1
    assert result.errors


def test_executor_stops_on_first_error() -> None:
    engine = FailingEngine()
    executor = Executor(engine, build_registry())
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="Widget"))
    plan.add(InsertMethodOperation(target_class="Widget", method_name="run", source_code="def run(self): pass"))

    result = executor.execute(plan)

    assert result.success is False
    assert len(result.executed_operations) == 1
    assert len(result.failed_operations) == 1
    assert result.errors[0] == "boom"


def test_executor_inserts_import_when_missing() -> None:
    engine = FakeEngine()
    executor = Executor(engine, build_registry())
    plan = ExecutionPlan()
    plan.add(EnsureImportOperation(module="typing", name="Optional"))

    result = executor.execute(plan)

    assert result.success is True
    assert len(result.executed_operations) == 1
    assert engine.calls[0][0] == "ensure_import"
    assert engine.calls[0][1] == ("typing", "Optional")


def test_executor_does_not_duplicate_import_when_already_present() -> None:
    class ImportAwareEngine(FakeEngine):
        def __init__(self) -> None:
            super().__init__()
            self.imports: set[tuple[str, str | None]] = set()

        def ensure_import(self, module: str, name: str | None) -> str:
            key = (module, name)
            if key in self.imports:
                return "already_present"
            self.imports.add(key)
            self.calls.append(("ensure_import", (module, name), {}))
            return f"imported:{module}:{name}"

    engine = ImportAwareEngine()
    executor = Executor(engine, build_registry())
    plan = ExecutionPlan()
    plan.add(EnsureImportOperation(module="typing", name="Optional"))
    plan.add(EnsureImportOperation(module="typing", name="Optional"))

    result = executor.execute(plan)

    assert result.success is True
    assert len(result.executed_operations) == 2
    assert [call[0] for call in engine.calls] == ["ensure_import"]


def test_execution_result_contains_expected_fields() -> None:
    result = ExecutionResult(executed_operations=[CreateClassOperation(class_name="Widget")], failed_operations=[], errors=[], success=True)

    assert result.success is True
    assert len(result.executed_operations) == 1
    assert result.failed_operations == []
