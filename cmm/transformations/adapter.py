"""Transformation-domain adaptation to backend-independent requests."""

from __future__ import annotations

from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation


class TransformationActionAdapter:
    """Convert transformation operations into backend-independent requests."""

    def adapt(
        self,
        operation: TransformationOperation,
    ) -> ExecutionRequest:
        """Create a backend-independent request for ``operation``."""
        return ExecutionRequest(
            operation=operation,
            metadata=operation.metadata(),
        )
