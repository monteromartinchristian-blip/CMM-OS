"""Registry-based dispatch for planner operations.

The registry decouples the execution pipeline from concrete operation classes.
Handlers are resolved dynamically so new operations can be added without
changing the executor implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from kernel.planner.exceptions import PlannerError
from kernel.planner.operations import Operation


class OperationHandler(ABC):
    """Abstract base class for handlers that execute one planner operation."""

    @abstractmethod
    def execute(self, operation: Operation, engine: Any) -> Any:
        """Execute the operation against the provided engine."""


class OperationRegistry:
    """Resolve operations to their execution handlers."""

    def __init__(self) -> None:
        self._handlers: dict[type[Operation], OperationHandler] = {}

    def register(self, operation_cls: type[Operation], handler: OperationHandler) -> None:
        """Register a handler for a specific operation class."""

        if not issubclass(operation_cls, Operation):
            raise PlannerError("operation_cls must be a subclass of Operation.")
        self._handlers[operation_cls] = handler

    def resolve(self, operation: Operation) -> OperationHandler:
        """Resolve the appropriate handler for an operation."""

        for operation_cls, handler in self._handlers.items():
            if isinstance(operation, operation_cls):
                return handler

        raise PlannerError(f"No handler registered for operation: {operation!r}")

    def has_handler(self, operation: Operation) -> bool:
        """Return whether there is a handler registered for the operation."""

        try:
            self.resolve(operation)
        except PlannerError:
            return False
        return True

    def registered_operations(self) -> tuple[type[Operation], ...]:
        """Return the registered operation classes."""

        return tuple(self._handlers.keys())


class CreateClassHandler(OperationHandler):
    """Execute a create_class operation on the engine."""

    def execute(self, operation: Operation, engine: Any) -> Any:
        return engine.create_class(operation.class_name)


class InsertMethodHandler(OperationHandler):
    """Execute an insert_method operation on the engine."""

    def execute(self, operation: Operation, engine: Any) -> Any:
        return engine.insert_method(
            operation.target_class,
            operation.method_name,
            operation.source_code,
        )


class ReplaceMethodHandler(OperationHandler):
    """Execute a replace_method operation on the engine."""

    def execute(self, operation: Operation, engine: Any) -> Any:
        return engine.replace_method(
            operation.target_class,
            operation.method_name,
            operation.source_code,
        )


class EnsureImportHandler(OperationHandler):
    """Execute an ensure_import operation on the engine."""

    def execute(self, operation: Operation, engine: Any) -> Any:
        return engine.ensure_import(operation.module, operation.name)


class ExtractFactsHandler(OperationHandler):
    """Execute an extract_facts operation against the operation itself."""

    def execute(self, operation: Operation, engine: Any) -> Any:
        return operation.execute()


class MergeKnowledgeHandler(OperationHandler):
    """Execute a merge_knowledge operation against the operation itself."""

    def execute(self, operation: Operation, engine: Any) -> Any:
        return operation.execute()


__all__ = [
    "CreateClassHandler",
    "EnsureImportHandler",
    "ExtractFactsHandler",
    "InsertMethodHandler",
    "MergeKnowledgeHandler",
    "OperationHandler",
    "OperationRegistry",
    "ReplaceMethodHandler",
]
