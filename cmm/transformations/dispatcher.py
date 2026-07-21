"""Dispatch transformation operations through a transformation adapter."""

from __future__ import annotations

from cmm.transformations.adapter import TransformationActionAdapter
from cmm.transformations.operation import TransformationOperation


class TransformationDispatcher:
    """Delegate typed operations directly to a transformation adapter."""

    def __init__(self, adapter: TransformationActionAdapter) -> None:
        self._adapter = adapter

    def dispatch(self, operation: TransformationOperation) -> object:
        """Delegate ``operation`` without inspecting or transforming it."""
        return self._adapter.adapt(operation)
