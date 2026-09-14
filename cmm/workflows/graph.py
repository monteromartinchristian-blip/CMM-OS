from __future__ import annotations

from collections.abc import Mapping

from cmm.workflows.contracts import WorkflowDefinition
from cmm.workflows.enums import WorkflowNodeType
from cmm.workflows.errors import WorkflowGraphError


def validate_workflow_graph(definition: WorkflowDefinition) -> None:
    nodes = {node.node_id: node for node in definition.nodes}
    if len(nodes) != len(definition.nodes):
        raise WorkflowGraphError("workflow node IDs must be unique")
    if not nodes:
        raise WorkflowGraphError("workflow must contain nodes")
    for node in definition.nodes:
        if any(dep not in nodes for dep in node.dependencies):
            raise WorkflowGraphError(f"node {node.node_id} has an unknown dependency")
        if node.node_id in node.dependencies:
            raise WorkflowGraphError(f"node {node.node_id} cannot depend on itself")
        if node.node_type is WorkflowNodeType.EXECUTE_OPERATION and not node.operation_id:
            raise WorkflowGraphError("operation node requires operation_id")
        if node.node_type is WorkflowNodeType.EXECUTE_OPERATION and not node.operation_version:
            raise WorkflowGraphError("operation node requires operation_version")
        if node.node_type is WorkflowNodeType.INVOKE_SUBWORKFLOW and not node.subworkflow_id:
            raise WorkflowGraphError("subworkflow node requires subworkflow_id")
        if node.node_type is WorkflowNodeType.INVOKE_SUBWORKFLOW and not node.subworkflow_version:
            raise WorkflowGraphError("subworkflow node requires subworkflow_version")
        if node.node_type is WorkflowNodeType.REQUEST_APPROVAL and not node.approval_gate:
            raise WorkflowGraphError("approval node requires approval_gate")
        if node.node_type in (WorkflowNodeType.WAIT_FOR_RESOURCE, WorkflowNodeType.ASK_QUESTION) and node.wait_condition is None:
            raise WorkflowGraphError("wait node requires wait_condition")
        for binding in tuple(node.input_bindings.values()) + tuple(node.output_bindings.values()):
            if isinstance(binding, Mapping) and "from_node" in binding and binding["from_node"] not in nodes:
                raise WorkflowGraphError("binding references an unknown output node")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise WorkflowGraphError("workflow graph contains a cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dep in nodes[node_id].dependencies:
            visit(dep)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in sorted(nodes):
        visit(node_id)
    terminals = set(definition.terminal_node_ids) if definition.terminal_node_ids else {node.node_id for node in definition.nodes if not any(node.node_id in other.dependencies for other in definition.nodes)}
    if definition.terminal_node_ids and not terminals <= set(nodes):
        raise WorkflowGraphError("terminal_node_ids must reference existing nodes")
    if not terminals:
        raise WorkflowGraphError("workflow must have a terminal node")
    if any(node.node_type is WorkflowNodeType.COMPLETE and any(node.node_id in other.dependencies for other in definition.nodes) for node in definition.nodes):
        raise WorkflowGraphError("complete nodes cannot have successors")
    criteria_keys = {"all_required_nodes_completed", "output_schema_valid", "no_blocking_failures", "required_approvals_granted", "required_resources_resolved", "minimum_successful_nodes", "specific_node_completed"}
    if set(definition.completion_criteria) - criteria_keys:
        raise WorkflowGraphError("unsupported completion criterion")


def ready_node_ids(definition: WorkflowDefinition, completed: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    done = set(completed)
    return tuple(sorted(node.node_id for node in definition.nodes if node.node_id not in done and set(node.dependencies) <= done))
