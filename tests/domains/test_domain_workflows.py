
from cmm.domains.workflow_catalog import initial_domain_workflows
from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
)
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.domains.workflow_resolution import resolve_domain_workflow
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowAvailabilityStatus, WorkflowRunStatus


def definition(**kwargs):
    values = {"workflow_id": "x.flow", "domain_id": "domain:x", "version": "1.0.0", "name": "X", "nodes": (WorkflowNode("n", "complete", "N"),)}
    values.update(kwargs)
    return DomainWorkflowDefinition(**values)


def test_domain_registry_filters_domain_but_common_registry_does_not():
    registry = InMemoryDomainWorkflowRegistry()
    registry.register(definition())
    registry.register(definition(workflow_id="y.flow", domain_id="domain:y"))
    assert [d.workflow_id for d in registry.list_for_domain("domain:x")] == ["x.flow"]
    assert len(registry.common_registry.list_definitions()) == 2


def test_resolution_uses_deny_wins_and_is_pure():
    item = definition(required_permissions=("read",), required_resources=("record",))
    result = resolve_domain_workflow(item, DomainWorkflowContext("domain:x", available_permissions=frozenset({"read"}), denied_permissions=frozenset({"read"}), available_resources=frozenset({"record"})))
    assert result.status is WorkflowAvailabilityStatus.BLOCKED


def test_execution_uses_common_run_as_source_of_truth():
    item = definition()
    context = DomainWorkflowContext("domain:x")
    run = DomainWorkflowExecutor(id_factory=lambda: "run-1").execute(item, context, {})
    assert run.status is WorkflowRunStatus.FAILED
    assert run.common_run.run_id == "run-1"


def test_catalog_contains_exact_four_conservative_workflows():
    catalog = initial_domain_workflows()
    assert {item.workflow_id for item in catalog} == {
        "health.medical_follow_up", "university.semester_planning",
        "relationships.timeline_analysis", "project.architecture_review",
    }


def test_catalog_workflows_do_not_claim_completion_without_capabilities():
    for item in initial_domain_workflows():
        result = DomainWorkflowExecutor(id_factory=lambda: "run").execute(item, DomainWorkflowContext(item.domain_id), {})
        assert result.status is not WorkflowRunStatus.COMPLETED
