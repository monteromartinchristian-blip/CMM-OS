from pathlib import Path

from kernel.core.bootstrap import create_kernel
from kernel.core.kernel import AgentKernel
from kernel.core.result import KernelResult
from kernel.planner.context import PlanningContext
from kernel.planner.executor import ExecutionResult
from kernel.planner.operations import CreateClassOperation, InsertMethodOperation
from kernel.planner.validator import ValidationResult


class DummyPlanner:
    def __init__(self) -> None:
        self.received_contexts: list[PlanningContext] = []

    def plan(self, context: PlanningContext):
        self.received_contexts.append(context)
        plan = []
        plan.append(CreateClassOperation(class_name="User"))
        plan.append(InsertMethodOperation(target_class="user", method_name="login", source_code="def login(self): pass"))
        return plan


class DummyExecutor:
    def __init__(self) -> None:
        self.received_plans: list[object] = []

    def execute(self, plan):
        self.received_plans.append(plan)
        return ExecutionResult(success=True, executed_operations=list(plan))


class DummyValidator:
    def __init__(self, errors: bool = False) -> None:
        self.errors = errors
        self.received_plans: list[object] = []

    def validate(self, plan):
        self.received_plans.append(plan)
        return ValidationResult(valid=not self.errors, errors=["bad plan"] if self.errors else [])


def test_kernel_executes_full_flow_successfully() -> None:
    planner = DummyPlanner()
    validator = DummyValidator(errors=False)
    executor = DummyExecutor()
    kernel = AgentKernel(planner=planner, validator=validator, executor=executor)

    context = PlanningContext(intent="create User", project_root=Path("/tmp/project"))
    result = kernel.execute(context)

    assert isinstance(result, KernelResult)
    assert result.success is True
    assert result.planning_context is context
    assert result.execution_result is not None
    assert result.execution_result.success is True
    assert result.has_validation_errors is False
    assert result.has_execution_errors is False


def test_validation_errors_prevent_execution() -> None:
    planner = DummyPlanner()
    validator = DummyValidator(errors=True)
    executor = DummyExecutor()
    kernel = AgentKernel(planner=planner, validator=validator, executor=executor)

    context = PlanningContext(intent="create bad plan")
    result = kernel.execute(context)

    assert result.success is False
    assert result.execution_result is None
    assert result.has_validation_errors is True
    assert result.has_execution_errors is False
    assert executor.received_plans == []


def test_kernel_passes_planning_context_to_planner() -> None:
    planner = DummyPlanner()
    validator = DummyValidator(errors=False)
    executor = DummyExecutor()
    kernel = AgentKernel(planner=planner, validator=validator, executor=executor)

    context = PlanningContext(intent="use context")
    kernel.execute(context)

    assert planner.received_contexts == [context]


def test_kernel_passes_execution_plan_to_executor() -> None:
    planner = DummyPlanner()
    validator = DummyValidator(errors=False)
    executor = DummyExecutor()
    kernel = AgentKernel(planner=planner, validator=validator, executor=executor)

    context = PlanningContext(intent="run")
    kernel.execute(context)

    assert executor.received_plans[0] is not None
    assert len(executor.received_plans) == 1


def test_kernel_result_success_flag_matches_execution() -> None:
    planner = DummyPlanner()
    validator = DummyValidator(errors=False)
    executor = DummyExecutor()
    kernel = AgentKernel(planner=planner, validator=validator, executor=executor)

    result = kernel.execute(PlanningContext(intent="flag"))

    assert result.success is True


def test_create_kernel_builds_default_components() -> None:
    kernel = create_kernel()

    assert isinstance(kernel, AgentKernel)
    assert kernel.planner is not None
    assert kernel.validator is not None
    assert kernel.executor is not None
