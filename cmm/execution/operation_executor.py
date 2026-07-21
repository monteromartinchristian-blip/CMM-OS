"""Abstract contract for executing one concrete transformation operation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cmm.execution.execution_result import ExecutionResult
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation


class OperationExecutor(ABC):
    """Execute requests for one concrete transformation operation type."""

    @property
    @abstractmethod
    def operation_type(self) -> type[TransformationOperation]:
        """Return the concrete operation type supported by this executor."""

    @abstractmethod
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute ``request`` without involving an action runtime."""
