"""Basic transformation executor implementation."""

from __future__ import annotations

from cmm.transformations.dispatcher import TransformationDispatcher
from cmm.transformations.executor import TransformationExecutor
from cmm.transformations.graph import TransformationGraph


class BasicTransformationExecutor(TransformationExecutor):
    """Execute graph nodes in dependency order via a dispatcher."""

    def __init__(self, dispatcher: TransformationDispatcher) -> None:
        self._dispatcher = dispatcher

    def execute(self, graph: TransformationGraph) -> object:
        """Traverse the graph and dispatch each step once dependencies are met."""
        dispatch_results = []
        for node in graph.topological_order():
            dispatch_results.append(self._dispatcher.dispatch(node.step.operation))

        return dispatch_results
