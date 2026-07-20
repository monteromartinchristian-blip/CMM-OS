"""LLM-backed planner implementation for CMM OS."""

from __future__ import annotations

from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.parser import OperationPlanParser
from kernel.llm.prompt import PromptBuilder
from kernel.llm.provider import LLMProvider
from kernel.planner.context import PlanningContext
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.planner import Planner


class LLMPlanner(Planner):
    """Create an execution plan by delegating to an LLM provider and parser."""

    def __init__(
        self,
        provider: LLMProvider,
        prompt_builder: PromptBuilder,
        parser: OperationPlanParser,
    ) -> None:
        self.provider = provider
        self.prompt_builder = prompt_builder
        self.parser = parser

    def plan(self, context: PlanningContext) -> ExecutionPlan:
        """Generate an execution plan from a planning context."""

        request = self.prompt_builder.build(context)
        response = self.provider.generate(request)
        return self.parser.parse(response)
