"""Hybrid planner that combines rule-based and LLM-backed planning."""

from __future__ import annotations

from kernel.llm.mock_provider import MockProvider
from kernel.llm.parser import OperationPlanParser
from kernel.llm.prompt import PromptBuilder
from kernel.planner.context import PlanningContext
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.llm_planner import LLMPlanner
from kernel.planner.planner import Planner, PlanningError, RuleBasedPlanner


class HybridPlanner(Planner):
    """Try the rule-based planner first and fall back to the LLM planner."""

    def __init__(self, rule_planner: Planner, llm_planner: Planner) -> None:
        self.rule_planner = rule_planner
        self.llm_planner = llm_planner

    def plan(self, context: PlanningContext) -> ExecutionPlan:
        """Try the rule-based planner and fall back to the LLM planner on PlanningError."""

        try:
            return self.rule_planner.plan(context)
        except PlanningError:
            return self.llm_planner.plan(context)
