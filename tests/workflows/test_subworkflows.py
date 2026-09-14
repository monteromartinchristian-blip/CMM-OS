
from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode
from cmm.workflows.registry import InMemoryWorkflowRegistry


def definition(workflow_id, child=None):
    node = WorkflowNode("call", "invoke_subworkflow", "Call", subworkflow_id=child, subworkflow_version="1.0.0") if child else WorkflowNode("done", "complete", "Done")
    return WorkflowDefinition(workflow_id, "1.0.0", workflow_id, nodes=(node,))


def test_subworkflow_resolution_is_order_independent_but_global_cycles_fail():
    registry = InMemoryWorkflowRegistry()
    registry.register(definition("a", "b"))
    assert registry.resolve_subworkflow("b", "1.0.0") is None
    registry.register(definition("b"))
    assert registry.resolve_subworkflow("b", "1.0.0").workflow_id == "b"
    registry.register(definition("c", "a"))
    registry.register(WorkflowDefinition("b", "2.0.0", "b2", nodes=(WorkflowNode("done", "complete", "Done"),)))
    registry.validate_registry()
