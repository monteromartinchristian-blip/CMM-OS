from __future__ import annotations

from typing import Any

import pytest

from kernel.llm.exceptions import ParserError
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.mock_provider import MockProvider
from kernel.llm.parser import OperationPlanParser
from kernel.llm.prompt import PromptBuilder
from kernel.llm.provider import LLMProvider
from kernel.planner.context import PlanningContext
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.hybrid_planner import HybridPlanner
from kernel.planner.llm_planner import LLMPlanner
from kernel.planner.planner import Planner, PlanningError, RuleBasedPlanner
from kernel.planner.rules import CreateClassRule


class DummyRulePlanner(Planner):
    def __init__(self, plan_result: ExecutionPlan | None = None, error: Exception | None = None) -> None:
        self.plan_result = plan_result
        self.error = error
        self.calls: list[PlanningContext] = []

    def plan(self, context: PlanningContext) -> ExecutionPlan:
        self.calls.append(context)
        if self.error is not None:
            raise self.error
        if self.plan_result is None:
            return ExecutionPlan()
        return self.plan_result


class DummyLLMPlanner(Planner):
    def __init__(self, plan_result: ExecutionPlan | None = None) -> None:
        self.plan_result = plan_result
        self.calls: list[PlanningContext] = []

    def plan(self, context: PlanningContext) -> ExecutionPlan:
        self.calls.append(context)
        if self.plan_result is None:
            return ExecutionPlan()
        return self.plan_result


def test_hybrid_planner_uses_rule_planner_for_known_intent() -> None:
    rule_output = ExecutionPlan()
    rule_planner = DummyRulePlanner(plan_result=rule_output)
    llm_planner = DummyLLMPlanner()
    hybrid = HybridPlanner(rule_planner=rule_planner, llm_planner=llm_planner)

    result = hybrid.plan(PlanningContext(intent="crea una clase User"))

    assert result is rule_output
    assert llm_planner.calls == []


def test_hybrid_planner_uses_llm_planner_for_unknown_intent() -> None:
    llm_output = ExecutionPlan()
    rule_planner = DummyRulePlanner(error=PlanningError("unknown"))
    llm_planner = DummyLLMPlanner(plan_result=llm_output)
    hybrid = HybridPlanner(rule_planner=rule_planner, llm_planner=llm_planner)

    result = hybrid.plan(PlanningContext(intent="something else"))

    assert result is llm_output
    assert len(llm_planner.calls) == 1


def test_hybrid_planner_propagates_non_planning_errors() -> None:
    rule_planner = DummyRulePlanner(error=RuntimeError("boom"))
    llm_planner = DummyLLMPlanner()
    hybrid = HybridPlanner(rule_planner=rule_planner, llm_planner=llm_planner)

    with pytest.raises(RuntimeError, match="boom"):
        hybrid.plan(PlanningContext(intent="anything"))


def test_hybrid_planner_does_not_call_llm_when_rule_planner_succeeds() -> None:
    rule_output = ExecutionPlan()
    rule_planner = DummyRulePlanner(plan_result=rule_output)
    llm_planner = DummyLLMPlanner()
    hybrid = HybridPlanner(rule_planner=rule_planner, llm_planner=llm_planner)

    hybrid.plan(PlanningContext(intent="crea una clase User"))

    assert llm_planner.calls == []


def test_hybrid_planner_runs_rule_planner_first() -> None:
    rule_planner = DummyRulePlanner(plan_result=ExecutionPlan())
    llm_planner = DummyLLMPlanner()
    hybrid = HybridPlanner(rule_planner=rule_planner, llm_planner=llm_planner)

    hybrid.plan(PlanningContext(intent="crea una clase User"))

    assert len(rule_planner.calls) == 1
    assert llm_planner.calls == []
