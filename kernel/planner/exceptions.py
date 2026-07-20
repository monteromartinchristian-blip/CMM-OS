"""Exceptions for the Semantic Planner domain model."""


class PlannerError(Exception):
    """Base exception for planner-related errors."""


class InvalidOperationError(PlannerError):
    """Raised when an operation payload or structure is invalid."""


class ExecutionPlanError(PlannerError):
    """Raised when an execution plan cannot be built or modified."""
