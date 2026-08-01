from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
)
from cmm.domains.workflow_resolution import resolve_domain_workflow
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowAvailabilityStatus


def test_supporting_domain_cannot_expand_permissions_and_unknown_domain_blocks():
    definition = DomainWorkflowDefinition(
        "x.cross", "domain:x", "1.0.0", "Cross",
        nodes=(WorkflowNode("done", "complete", "Done"),),
        supporting_domain_ids=("domain:y",), required_permissions=("read:x",),
    )
    unknown = resolve_domain_workflow(definition, DomainWorkflowContext("domain:x", supporting_domain_ids=("domain:y",), known_domain_ids=frozenset({"domain:x"}), available_permissions=frozenset({"read:x"})))
    assert unknown.status is WorkflowAvailabilityStatus.BLOCKED
    denied = resolve_domain_workflow(definition, DomainWorkflowContext("domain:x", supporting_domain_ids=("domain:y",), known_domain_ids=frozenset({"domain:x", "domain:y"}), authorized_domain_ids=frozenset({"domain:x"}), available_permissions=frozenset({"read:x"})))
    assert denied.status is WorkflowAvailabilityStatus.BLOCKED
