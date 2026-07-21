"""Typed registry for transformation operation executors."""

from __future__ import annotations

from cmm.execution.operation_executor import OperationExecutor
from cmm.transformations.operation import TransformationOperation


class UnsupportedOperationExecutorError(Exception):
    """Raised when no executor is registered for an operation type."""


class OperationExecutorRegistry:
    """Resolve operation executors by the concrete operation class."""

    def __init__(self) -> None:
        self._executors: dict[type[TransformationOperation], OperationExecutor] = {}

    def register(self, executor: OperationExecutor) -> None:
        """Register one executor for its concrete operation type."""
        self.register_many([executor])

    def register_many(self, executors: list[OperationExecutor]) -> None:
        """Register several executors atomically."""
        operation_types = set()
        for executor in executors:
            if not isinstance(executor, OperationExecutor):
                raise TypeError("Executor must implement OperationExecutor.")
            operation_type = executor.operation_type
            if operation_type in self._executors or operation_type in operation_types:
                raise ValueError(
                    f"Executor already registered for operation type: {operation_type.__name__}."
                )
            operation_types.add(operation_type)

        self._executors.update(
            {executor.operation_type: executor for executor in executors}
        )

    def unregister(
        self,
        operation_type: type[TransformationOperation],
    ) -> OperationExecutor:
        """Remove and return the executor registered for ``operation_type``."""
        try:
            return self._executors.pop(operation_type)
        except KeyError as error:
            raise UnsupportedOperationExecutorError(
                f"Unsupported operation type: {operation_type.__name__}."
            ) from error

    def resolve(self, operation: TransformationOperation) -> OperationExecutor:
        """Resolve the executor registered for the concrete operation type."""
        operation_type = type(operation)
        try:
            return self._executors[operation_type]
        except KeyError as error:
            raise UnsupportedOperationExecutorError(
                f"Unsupported operation type: {operation_type.__name__}."
            ) from error

    def supports(self, operation: TransformationOperation) -> bool:
        """Return whether an executor is registered for ``operation``."""
        return type(operation) in self._executors

    def all(self) -> list[OperationExecutor]:
        """Return executors in registration order."""
        return list(self._executors.values())
