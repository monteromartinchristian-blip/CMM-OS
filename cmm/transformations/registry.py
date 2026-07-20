"""Registry for transformation definitions."""

from __future__ import annotations

from cmm.transformations.transformation import Transformation


class UnsupportedTransformationError(Exception):
    """Raised when no registered transformation matches a request."""


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
