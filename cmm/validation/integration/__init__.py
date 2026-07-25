"""Continuous Validation Integration Package for CMM OS (Subphase 7.13).

Exports public contracts, adapters, and services connecting validation to
Semantic Engine, Execution Engine, Planner, Kernel Events, and Technical Memory.
"""

from __future__ import annotations

from .contracts import (
    ValidationAction,
    ValidationDecision,
    ValidationEventPayload,
    ValidationIntegrationRequest,
    ValidationIntegrationResult,
    ValidationMemoryRecord,
    ValidationPhase,
    ValidationPlanNode,
    ValidationTrigger,
)
from .events import KernelEventPublisher
from .execution import ExecutionValidationCoordinator
from .memory import ValidationMemoryAdapter
from .planning import PlannerValidationAdapter, PlannerValidationError
from .semantic import SemanticValidationAdapter
from .service import ValidationIntegrationService

__all__ = [
    "ExecutionValidationCoordinator",
    "KernelEventPublisher",
    "PlannerValidationAdapter",
    "PlannerValidationError",
    "SemanticValidationAdapter",
    "ValidationAction",
    "ValidationDecision",
    "ValidationEventPayload",
    "ValidationIntegrationRequest",
    "ValidationIntegrationResult",
    "ValidationIntegrationService",
    "ValidationMemoryAdapter",
    "ValidationMemoryRecord",
    "ValidationPhase",
    "ValidationPlanNode",
    "ValidationTrigger",
]
