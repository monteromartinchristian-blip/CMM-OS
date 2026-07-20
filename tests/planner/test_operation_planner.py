from __future__ import annotations

import pytest

from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.mock_llm_provider import MockLLMProvider
from kernel.planner.operation_planner import OperationPlanner
from kernel.planner.operation_catalog import OperationCatalog
from kernel.planner.operations import CreateClassOperation, EnsureImportOperation, InsertMethodOperation, ReplaceMethodOperation
from kernel.planner.planner_strategy import LLMPlannerStrategy, PlannerStrategy, RuleBasedPlannerStrategy
from kernel.planner.planner_response_parser import parse as parse_planner_response


class DummyPlannerStrategy(PlannerStrategy):
    def __init__(self) -> None:
        self.calls: list[tuple[str, OperationCatalog]] = []

    def plan(self, goal: str, catalog: OperationCatalog) -> ExecutionPlan:
        self.calls.append((goal, catalog))
        return ExecutionPlan()


def test_operation_planner_creates_valid_execution_plan() -> None:
    planner = OperationPlanner()

    assert isinstance(planner.strategy, RuleBasedPlannerStrategy)

    plan = planner.plan("create class User")

    assert isinstance(plan, ExecutionPlan)
    assert len(plan) == 1
    assert isinstance(plan[0], CreateClassOperation)
    assert plan[0].class_name == "User"


def test_operation_planner_uses_operation_catalog() -> None:
    planner = OperationPlanner()

    operation_names = {metadata.name for metadata in planner.catalog.operations()}

    assert {"create_class", "insert_method", "replace_method", "ensure_import"}.issubset(operation_names)


def test_operation_planner_behavior_is_stable_for_known_goals() -> None:
    planner = OperationPlanner()
    goal = "create class User with method login"

    first_plan = planner.plan(goal)
    second_plan = planner.plan(goal)

    first_signature = [({key: value for key, value in operation.serialize().items() if key != "id"}, operation.operation_type_value) for operation in first_plan]
    second_signature = [({key: value for key, value in operation.serialize().items() if key != "id"}, operation.operation_type_value) for operation in second_plan]

    assert first_signature == second_signature
    assert len(first_plan) == 2
    assert isinstance(first_plan[0], CreateClassOperation)
    assert isinstance(first_plan[1], InsertMethodOperation)
    assert first_plan[0].class_name == "User"
    assert first_plan[1].method_name == "login"


def test_operation_planner_can_inject_another_strategy() -> None:
    strategy = DummyPlannerStrategy()
    planner = OperationPlanner(strategy=strategy)

    plan = planner.plan("  create class User  ")

    assert isinstance(plan, ExecutionPlan)
    assert len(plan) == 0
    assert strategy.calls == [("create class User", planner.catalog)]


def test_operation_planner_uses_llm_strategy_and_returns_execution_plan() -> None:
    provider = MockLLMProvider()
    planner = OperationPlanner(strategy=LLMPlannerStrategy(provider=provider))

    plan = planner.plan("create class User")

    assert isinstance(plan, ExecutionPlan)
    assert len(plan) == 1
    assert isinstance(plan[0], CreateClassOperation)
    assert plan[0].class_name == "User"
    assert provider.prompts
    assert "Goal: create class User" in provider.prompts[0]


def test_operation_planner_handles_multiple_llm_operations() -> None:
    provider = MockLLMProvider()
    planner = OperationPlanner(strategy=LLMPlannerStrategy(provider=provider))

    plan = planner.plan("Crea Logger y añade hello() a User")

    assert isinstance(plan, ExecutionPlan)
    assert len(plan) == 2
    assert isinstance(plan[0], CreateClassOperation)
    assert isinstance(plan[1], InsertMethodOperation)
    assert plan[0].class_name == "Logger"
    assert plan[1].target_class == "User"
    assert plan[1].method_name == "hello"


def test_mock_llm_provider_records_the_prompt() -> None:
    provider = MockLLMProvider(response="mocked")

    result = provider.complete("Plan this goal")

    assert result == "mocked"
    assert provider.prompts == ["Plan this goal"]


def test_mock_llm_provider_returns_valid_llm_response_format() -> None:
    provider = MockLLMProvider()

    response = provider.complete("You are an operation planner.\nGoal: replace method login in User")

    assert response.startswith("OPERATION replace_method")
    assert "CLASS User" in response
    assert "METHOD login" in response
    assert "---" not in response


def test_mock_llm_provider_returns_multiple_operations_format() -> None:
    provider = MockLLMProvider()

    response = provider.complete("You are an operation planner.\nGoal: Crea Logger y añade hello() a User")

    assert response.count("OPERATION") == 2
    assert "OPERATION create_class" in response
    assert "OPERATION insert_method" in response
    assert "---" in response


def test_planner_response_parser_parses_one_operation() -> None:
    plan = parse_planner_response(
        "OPERATION create_class\nNAME User",
        OperationCatalog(),
    )

    assert isinstance(plan, ExecutionPlan)
    assert len(plan) == 1
    assert isinstance(plan[0], CreateClassOperation)
    assert plan[0].class_name == "User"


def test_planner_response_parser_parses_multiple_operations_in_order() -> None:
    response = (
        "OPERATION create_class\nNAME Logger\n\n"
        "---\n\n"
        "OPERATION insert_method\nCLASS User\nMETHOD hello\n\n"
        "---\n\n"
        "OPERATION ensure_import\nMODULE logging"
    )

    plan = parse_planner_response(response, OperationCatalog())

    assert len(plan) == 3
    assert isinstance(plan[0], CreateClassOperation)
    assert isinstance(plan[1], InsertMethodOperation)
    assert isinstance(plan[2], EnsureImportOperation)
    assert plan[0].class_name == "Logger"
    assert plan[1].target_class == "User"
    assert plan[1].method_name == "hello"
    assert plan[2].module == "logging"


def test_planner_response_parser_is_backward_compatible_with_single_block_format() -> None:
    plan = parse_planner_response(
        "OPERATION insert_method\nCLASS User\nMETHOD hello\nSOURCE_CODE def hello(self):\n    pass",
        OperationCatalog(),
    )

    assert len(plan) == 1
    assert isinstance(plan[0], InsertMethodOperation)
    assert plan[0].target_class == "User"
    assert plan[0].method_name == "hello"


def test_llm_strategy_parser_handles_multiple_blocks() -> None:
    provider = MockLLMProvider()
    planner = OperationPlanner(strategy=LLMPlannerStrategy(provider=provider))

    plan = planner.plan("Crea Logger y añade hello() a User")

    assert len(plan) == 2
    assert isinstance(plan[0], CreateClassOperation)
    assert isinstance(plan[1], InsertMethodOperation)
    assert plan[0].class_name == "Logger"
    assert plan[1].target_class == "User"
    assert plan[1].method_name == "hello"


def test_operation_planner_keeps_existing_ensure_import_behavior() -> None:
    planner = OperationPlanner()

    plan = planner.plan("ensure import requests")

    assert len(plan) == 1
    assert isinstance(plan[0], EnsureImportOperation)
    assert plan[0].module == "requests"


def test_rule_based_strategy_keeps_existing_behavior() -> None:
    planner = OperationPlanner(strategy=RuleBasedPlannerStrategy())

    create_plan = planner.plan("create class User")
    replace_plan = planner.plan("replace method login in User")

    assert len(create_plan) == 1
    assert isinstance(create_plan[0], CreateClassOperation)
    assert create_plan[0].class_name == "User"

    assert len(replace_plan) == 1
    assert isinstance(replace_plan[0], ReplaceMethodOperation)
    assert replace_plan[0].target_class == "User"
    assert replace_plan[0].method_name == "login"


def test_operation_planner_supports_replace_method_goals() -> None:
    planner = OperationPlanner()

    plan = planner.plan("replace method login in User")

    assert len(plan) == 1
    assert isinstance(plan[0], ReplaceMethodOperation)
    assert plan[0].target_class == "User"
    assert plan[0].method_name == "login"