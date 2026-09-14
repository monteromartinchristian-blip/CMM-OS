import pytest

from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode
from cmm.workflows.errors import WorkflowGraphError
from cmm.workflows.graph import ready_node_ids, validate_workflow_graph


def n(i, deps=(), typ="complete", **kw):
    return WorkflowNode(node_id=i, node_type=typ, name=i, dependencies=deps, **kw)


def test_graph_rejects_cycles_and_invalid_references():
    with pytest.raises(WorkflowGraphError):
        validate_workflow_graph(WorkflowDefinition("x", "1.0.0", "x", nodes=(n("a", ("b",)), n("b", ("a",)))))
    with pytest.raises(WorkflowGraphError):
        validate_workflow_graph(WorkflowDefinition("x", "1.0.0", "x", nodes=(n("a", typ="execute_operation"),)))


def test_graph_returns_deterministic_ready_nodes():
    definition = WorkflowDefinition("x", "1.0.0", "x", nodes=(n("b", ("a",), typ="load_resource"), n("a", typ="load_resource"), n("c")))
    validate_workflow_graph(definition)
    assert ready_node_ids(definition, ()) == ("a", "c")
    assert ready_node_ids(definition, ("a",)) == ("b", "c")
