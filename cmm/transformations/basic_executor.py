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
        unresolved = dict(graph.nodes)
        completed = set()
        dispatch_results = []

        while unresolved:
            progressed = False

            for node_id, node in list(unresolved.items()):
                if any(dependency not in completed for dependency in node.dependencies):
                    continue

                dispatch_results.append(self._dispatcher.dispatch(node.step))
                completed.add(node_id)
                del unresolved[node_id]
                progressed = True

            if not progressed:
                raise RuntimeError("Unresolvable transformation graph dependencies.")

        return dispatch_results
