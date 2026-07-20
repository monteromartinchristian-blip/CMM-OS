"""Bootstrap helpers for creating the default agent kernel."""

from __future__ import annotations

from kernel.core.kernel import AgentKernel
from kernel.planner.bootstrap import create_default_planner, create_default_registry
from kernel.planner.executor import Executor
from kernel.planner.validator import PlanValidator


def create_kernel() -> AgentKernel:
    """Create the default kernel wiring planner, validator, and executor."""

    planner = create_default_planner()
    validator = PlanValidator()
    registry = create_default_registry()
    executor = Executor(engine=None, registry=registry)
    return AgentKernel(planner=planner, validator=validator, executor=executor)
