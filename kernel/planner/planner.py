"""Rule-based planner for simple developer intents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from kernel.planner.context import PlanningContext
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.exceptions import PlannerError
from kernel.planner.operations import Operation
from kernel.planner.rules import PlanningRule


class Planner(ABC):
    """Abstract planner interface."""

    @abstractmethod
    def plan(self, context: PlanningContext) -> ExecutionPlan:
        """Transform a planning context into an execution plan."""


class PlanningError(PlannerError):
    """Raised when an intent cannot be converted into a plan."""


class RuleBasedPlanner(Planner):
    """A simple rule-based planner that delegates to independent rules."""

    def __init__(self, rules: list[PlanningRule]) -> None:
        self._rules = rules

    def plan(self, context: PlanningContext) -> ExecutionPlan:
        """Create an execution plan from a planning context."""

        if not isinstance(context, PlanningContext):
            raise PlanningError("Context must be a PlanningContext instance.")
        if not context.intent or not context.intent.strip():
            raise PlanningError("Intent must be a non-empty string.")

        for rule in self._rules:
            if rule.matches(context.intent):
                operations = rule.build(context.intent)
                plan = ExecutionPlan()
                for operation in operations:
                    plan.add(operation)
                return plan

        raise PlanningError(f"Unable to interpret intent: {context.intent}")


__all__ = ["Planner", "PlanningError", "RuleBasedPlanner"]
