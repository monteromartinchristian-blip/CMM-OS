from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
    DomainWorkflowResolution,
)
from cmm.workflows.enums import WorkflowAvailabilityStatus, WorkflowNodeType


def resolve_domain_workflow(definition: DomainWorkflowDefinition, context: DomainWorkflowContext) -> DomainWorkflowResolution:
    missing_permissions = tuple(sorted(set(definition.required_permissions) - context.available_permissions))
    denied = tuple(sorted(set(definition.required_permissions) & context.denied_permissions))
    missing_resources = tuple(sorted(set(definition.required_resources) - context.available_resources))
    declared_domains = {definition.domain_id, *definition.supporting_domain_ids, *context.supporting_domain_ids}
    unknown_domains = declared_domains - set(context.known_domain_ids) if context.known_domain_ids else set()
    unauthorized_domains = (declared_domains & set(context.authorized_domain_ids)) ^ declared_domains if context.authorized_domain_ids else set()
    unavailable_nodes = []
    for node in definition.nodes:
        if node.node_type is WorkflowNodeType.EXECUTE_OPERATION and node.operation_id not in context.available_operations:
            unavailable_nodes.append(node.node_id)
    reasons = []
    if not definition.enabled:
        return DomainWorkflowResolution(definition.workflow_id, definition.version, definition.domain_id, WorkflowAvailabilityStatus.UNAVAILABLE, ("workflow.disabled",))
    if denied:
        return DomainWorkflowResolution(definition.workflow_id, definition.version, definition.domain_id, WorkflowAvailabilityStatus.BLOCKED, ("permission.denied",), tuple(unavailable_nodes), missing_permissions, denied, missing_resources)
    if unknown_domains:
        return DomainWorkflowResolution(definition.workflow_id, definition.version, definition.domain_id, WorkflowAvailabilityStatus.BLOCKED, ("domain.unknown",))
    if unauthorized_domains:
        return DomainWorkflowResolution(definition.workflow_id, definition.version, definition.domain_id, WorkflowAvailabilityStatus.BLOCKED, ("domain.unauthorized",))
    if set(definition.approval_gates) - context.approved_gates:
        return DomainWorkflowResolution(definition.workflow_id, definition.version, definition.domain_id, WorkflowAvailabilityStatus.WAITING_FOR_APPROVAL, ("approval.pending",), (), missing_permissions, denied, missing_resources)
    if missing_permissions or missing_resources or unavailable_nodes:
        reasons.extend(("permission.missing",) if missing_permissions else ())
        reasons.extend(("resource.missing",) if missing_resources else ())
        reasons.extend(("operation.unavailable",) if unavailable_nodes else ())
        return DomainWorkflowResolution(definition.workflow_id, definition.version, definition.domain_id, WorkflowAvailabilityStatus.UNAVAILABLE, tuple(reasons), tuple(unavailable_nodes), missing_permissions, denied, missing_resources)
    return DomainWorkflowResolution(definition.workflow_id, definition.version, definition.domain_id, WorkflowAvailabilityStatus.AVAILABLE)
