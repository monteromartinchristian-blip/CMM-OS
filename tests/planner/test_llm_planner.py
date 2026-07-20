from __future__ import annotations

from typing import Any

import pytest

from kernel.llm.exceptions import ParserError
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.parser import OperationPlanParser
from kernel.llm.prompt import PromptBuilder
from kernel.llm.provider import LLMProvider
from kernel.planner.context import PlanningContext
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.llm_planner import LLMPlanner
from kernel.planner.operations import InsertMethodOperation


class DummyProvider(LLMProvider):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content='{"operations": []}', model="dummy")


class FailingProvider(LLMProvider):
    def generate(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("boom")


class DummyParser(OperationPlanParser):
    def __init__(self) -> None:
        self.responses: list[LLMResponse] = []

    def parse(self, payload: LLMResponse | str) -> ExecutionPlan:
        self.responses.append(payload if isinstance(payload, LLMResponse) else LLMResponse(content=payload, model="dummy"))
        return ExecutionPlan()


class FailingParser(OperationPlanParser):
    def parse(self, payload: LLMResponse | str) -> ExecutionPlan:
        raise ParserError("broken")


def test_prompt_builder_builds_request_from_context() -> None:
    builder = PromptBuilder(system_prompt="system")
    context = PlanningContext(intent="create a class")

    request = builder.build(context)

    assert isinstance(request, LLMRequest)
    assert request.prompt == "create a class"
    assert request.system_prompt == "system"


def test_provider_receives_llm_request() -> None:
    provider = DummyProvider()
    builder = PromptBuilder(system_prompt="system")
    parser = DummyParser()
    planner = LLMPlanner(provider=provider, prompt_builder=builder, parser=parser)

    planner.plan(PlanningContext(intent="hello"))

    assert len(provider.requests) == 1
    assert isinstance(provider.requests[0], LLMRequest)


def test_parser_receives_llm_response() -> None:
    provider = DummyProvider()
    builder = PromptBuilder(system_prompt="system")
    parser = DummyParser()
    planner = LLMPlanner(provider=provider, prompt_builder=builder, parser=parser)

    planner.plan(PlanningContext(intent="hello"))

    assert len(parser.responses) == 1
    assert isinstance(parser.responses[0], LLMResponse)


def test_llm_planner_returns_execution_plan() -> None:
    provider = DummyProvider()
    builder = PromptBuilder(system_prompt="system")
    parser = DummyParser()
    planner = LLMPlanner(provider=provider, prompt_builder=builder, parser=parser)

    result = planner.plan(PlanningContext(intent="hello"))

    assert isinstance(result, ExecutionPlan)
    assert len(result) == 0


def test_provider_exceptions_propagate() -> None:
    provider = FailingProvider()
    builder = PromptBuilder(system_prompt="system")
    parser = DummyParser()
    planner = LLMPlanner(provider=provider, prompt_builder=builder, parser=parser)

    with pytest.raises(RuntimeError, match="boom"):
        planner.plan(PlanningContext(intent="hello"))


def test_parser_exceptions_propagate() -> None:
    provider = DummyProvider()
    builder = PromptBuilder(system_prompt="system")
    parser = FailingParser()
    planner = LLMPlanner(provider=provider, prompt_builder=builder, parser=parser)

    with pytest.raises(ParserError, match="broken"):
        planner.plan(PlanningContext(intent="hello"))


def test_llm_planner_parses_insert_method_operation() -> None:
    provider = DummyProvider()
    builder = PromptBuilder(system_prompt="system")
    parser = OperationPlanParser()
    planner = LLMPlanner(provider=provider, prompt_builder=builder, parser=parser)

    plan = planner.plan(PlanningContext(intent="insert a method"))

    assert isinstance(plan, ExecutionPlan)
    assert len(plan) == 0
