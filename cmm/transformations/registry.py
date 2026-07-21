"""Registry for transformation definitions."""

from __future__ import annotations

from cmm.transformations.operation import TransformationOperation
from cmm.transformations.transformation import Transformation


class UnsupportedTransformationError(Exception):
    """Raised when no registered transformation matches a request."""


class UnsupportedOperationError(Exception):
    """Raised when no registered operation matches a request."""


class TransformationRegistry:
    """Register and resolve transformation definitions by stable name."""

    def __init__(self) -> None:
        """Initialize an empty transformation registry."""
        self._transformations: list[Transformation] = []

    def register(self, transformation: Transformation) -> None:
        """Register one transformation if its name is unique."""
        self.register_many([transformation])

    def register_many(self, transformations: list[Transformation]) -> None:
        """Register multiple transformations atomically."""
        names = {transformation.name for transformation in self._transformations}
        new_names = set()

        for transformation in transformations:
            if not isinstance(transformation, Transformation):
                raise TypeError("Transformation must implement Transformation.")
            if transformation.name in names or transformation.name in new_names:
                raise ValueError(f"Transformation already registered: {transformation.name}.")
            new_names.add(transformation.name)

        self._transformations.extend(transformations)

    def resolve(self, name: str) -> Transformation:
        """Resolve a registered transformation by name."""
        for transformation in self._transformations:
            if transformation.name == name:
                return transformation

        raise UnsupportedTransformationError(f"Unsupported transformation: {name}.")

    def all(self) -> list[Transformation]:
        """Return all registered transformations in registration order."""
        return list(self._transformations)

    def clear(self) -> None:
        """Remove every transformation from the registry."""
        self._transformations.clear()


class OperationRegistry:
    """Register and resolve transformation operations by stable name."""

    def __init__(self) -> None:
        """Initialize an empty operation registry."""
        self._operations: list[TransformationOperation] = []

    def register(self, operation: TransformationOperation) -> None:
        """Register one operation if its name is unique."""
        self.register_many([operation])

    def register_many(self, operations: list[TransformationOperation]) -> None:
        """Register multiple operations atomically."""
        names = {operation.name for operation in self._operations}
        new_names = set()

        for operation in operations:
            if not isinstance(operation, TransformationOperation):
                raise TypeError("Operation must implement TransformationOperation.")
            if operation.name in names or operation.name in new_names:
                raise ValueError(f"Operation already registered: {operation.name}.")
            new_names.add(operation.name)

        self._operations.extend(operations)

    def resolve(self, name: str) -> TransformationOperation:
        """Resolve a registered operation by name."""
        for operation in self._operations:
            if operation.name == name:
                return operation

        raise UnsupportedOperationError(f"Unsupported operation: {name}.")

    def all(self) -> list[TransformationOperation]:
        """Return all registered operations in registration order."""
        return list(self._operations)

    def clear(self) -> None:
        """Remove every registered operation."""
        self._operations.clear()
