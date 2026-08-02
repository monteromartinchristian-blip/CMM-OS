from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleScope,
    ReasoningRuleStatus,
)
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.permission_adapters import (
    evaluate_domain_operation,
    evaluate_domain_rule,
    evaluate_domain_workflow,
)
from cmm.domains.permission_contracts import DomainPermissionPolicy
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType


def test_operation_adapter_uses_real_definition_and_requires_approval_for_destructive():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
        allowed_operations=("project.delete",),
    ))
    operation = DomainOperationDefinition(
        operation_id="project.delete", domain_id="domain:project", version="1.0.0",
        name="Delete", description="Delete a reversible record",
        operation_type=DomainOperationType.DESTRUCTIVE,
        risk_level=PolicyRiskLevel.HIGH, reversible=False, requires_approval=True,
    )
    decision = evaluate_domain_operation(
        operation, DomainPermissionResolver(registry), request_id="r", actor_id="a", session_id="s"
    )
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert decision.operation_id == operation.operation_id


def test_operation_adapter_evaluates_required_permission_with_provenance():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
        allowed_operations=("project.write",),
    ))
    operation = DomainOperationDefinition(
        operation_id="project.write", domain_id="domain:project", version="1.0.0",
        name="Write", description="Write", operation_type=DomainOperationType.PREPARATION,
        reversible=True, required_permissions=(PermissionCapability.MEMORY_WRITE.value,),
    )
    decision = evaluate_domain_operation(operation, DomainPermissionResolver(registry), request_id="r", actor_id="a", session_id="s")
    assert decision.decision is PermissionOutcome.DENY
    assert decision.requirement_decisions[0].permission == PermissionCapability.MEMORY_WRITE.value
    assert decision.requirement_decisions[0].decision is PermissionOutcome.DENY
    assert decision.requirement_decisions[0].provenance


def test_operation_adapter_requires_approval_for_irreversible_and_external_capability():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE, PermissionCapability.SEARCH_EXTERNAL),
        approval_capabilities=(PermissionCapability.SEARCH_EXTERNAL,),
        allowed_operations=("project.external",),
    ))
    operation = DomainOperationDefinition(
        operation_id="project.external", domain_id="domain:project", version="1.0.0",
        name="External", description="External", operation_type=DomainOperationType.EXTERNAL,
        reversible=False,
    )
    decision = evaluate_domain_operation(operation, DomainPermissionResolver(registry), request_id="r", actor_id="a", session_id="s")
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert {item.permission for item in decision.requirement_decisions} == {PermissionCapability.SEARCH_EXTERNAL.value}
    assert {item.reason_code for item in decision.approval_requirements} >= {"irreversible_operation"}


def test_operation_adapter_denies_disabled_and_missing_external_capability():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
        allowed_operations=("project.external", "project.read"),
    ))
    external = DomainOperationDefinition("project.external", "domain:project", "1.0.0", "External", "External", DomainOperationType.EXTERNAL, reversible=True)
    disabled = DomainOperationDefinition("project.read", "domain:project", "1.0.0", "Read", "Read", DomainOperationType.READ, reversible=True, enabled=False)
    resolver = DomainPermissionResolver(registry)
    assert evaluate_domain_operation(external, resolver, request_id="r", actor_id="a", session_id="s").decision is PermissionOutcome.DENY
    assert evaluate_domain_operation(disabled, resolver, request_id="r", actor_id="a", session_id="s").decision is PermissionOutcome.DENY


def test_operation_adapter_propagates_approval_for_a_required_permission():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE, PermissionCapability.MEDICAL_DECISION),
        allowed_operations=("project.decide",),
    ))
    operation = DomainOperationDefinition("project.decide", "domain:project", "1.0.0", "Decide", "Decide", DomainOperationType.PREPARATION, reversible=True, required_permissions=(PermissionCapability.MEDICAL_DECISION.value,))
    decision = evaluate_domain_operation(operation, DomainPermissionResolver(registry), request_id="r", actor_id="a", session_id="s")
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert decision.requirement_decisions[0].decision is PermissionOutcome.APPROVAL_REQUIRED
    assert {item.action for item in decision.approval_requirements} == {
        PermissionCapability.MEDICAL_DECISION
    }


def test_workflow_adapter_blocks_real_required_nodes_when_workflow_is_denied():
    workflow = DomainWorkflowDefinition(
        workflow_id="project.workflow", domain_id="domain:project", version="1.0.0",
        name="Project workflow", nodes=(WorkflowNode("node-1", WorkflowNodeType.EXECUTE_OPERATION, "Run", operation_id="project.delete"),),
    )
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy("project", "domain:project", "1.0.0"))
    decision = evaluate_domain_workflow(workflow, DomainPermissionResolver(registry), request_id="r", actor_id="a", session_id="s")
    assert decision.decision is PermissionOutcome.DENY
    assert decision.blocked_nodes == ("node-1",)


def test_workflow_adapter_evaluates_each_node_and_preserves_optional_blocks():
    execute = WorkflowNode("execute", WorkflowNodeType.EXECUTE_OPERATION, "Execute", operation_id="project.read")
    optional = WorkflowNode("optional", WorkflowNodeType.EXECUTE_OPERATION, "Optional", operation_id="project.missing", required=False)
    gate = WorkflowNode("gate", WorkflowNodeType.REQUEST_APPROVAL, "Gate", approval_gate="review")
    workflow = DomainWorkflowDefinition("project.workflow", "domain:project", "1.0.0", "Project", nodes=(execute, optional, gate))
    operation = DomainOperationDefinition("project.read", "domain:project", "1.0.0", "Read", "Read", DomainOperationType.READ, reversible=True)
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0",
        allowed_capabilities=(PermissionCapability.WORKFLOW_EXECUTE, PermissionCapability.OPERATION_EXECUTE),
        allowed_workflows=("project.workflow",), allowed_operations=("project.read",),
    ))
    decision = evaluate_domain_workflow(workflow, DomainPermissionResolver(registry), request_id="r", actor_id="a", session_id="s", operations={(operation.operation_id, operation.version): operation})
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert decision.allowed_nodes == ("execute",)
    assert decision.blocked_nodes == ("optional",)
    assert decision.approval_nodes == ("gate",)
    assert {node.node_id for node in decision.node_decisions} == {"execute", "optional", "gate"}


def test_workflow_adapter_evaluates_declared_permissions_not_only_execute():
    workflow = DomainWorkflowDefinition(
        "project.workflow", "domain:project", "1.0.0", "Project",
        required_permissions=(PermissionCapability.MEMORY_WRITE.value,),
        nodes=(WorkflowNode("done", WorkflowNodeType.COMPLETE, "Done"),),
    )
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0",
        allowed_capabilities=(PermissionCapability.WORKFLOW_EXECUTE,),
        allowed_workflows=("project.workflow",),
    ))

    decision = evaluate_domain_workflow(
        workflow, DomainPermissionResolver(registry),
        request_id="r", actor_id="a", session_id="s",
    )

    assert decision.decision is PermissionOutcome.DENY
    assert decision.requirement_decisions[0].permission == PermissionCapability.MEMORY_WRITE.value
    assert decision.requirement_decisions[0].decision is PermissionOutcome.DENY


def test_workflow_adapter_evaluates_required_resource_id_without_treating_it_as_kind():
    workflow = DomainWorkflowDefinition(
        "project.workflow", "domain:project", "1.0.0", "Project",
        required_resources=("record:1",),
        nodes=(WorkflowNode("done", WorkflowNodeType.COMPLETE, "Done"),),
    )
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0",
        allowed_capabilities=(
            PermissionCapability.WORKFLOW_EXECUTE,
            PermissionCapability.RESOURCE_READ,
        ),
        allowed_workflows=("project.workflow",),
        allowed_resources=("record:1",),
    ))

    decision = evaluate_domain_workflow(
        workflow, DomainPermissionResolver(registry),
        request_id="r", actor_id="a", session_id="s",
    )

    assert decision.decision is PermissionOutcome.DENY
    assert decision.requirement_decisions[0].permission == "resource:record:1"
    assert "resource_allowlist_not_matched" not in decision.requirement_decisions[0].reasons
    assert "resource_kind_allowlist_not_matched" not in decision.requirement_decisions[0].reasons


def test_required_workflow_node_includes_its_operation_requirements():
    operation = DomainOperationDefinition(
        "project.write", "domain:project", "1.0.0", "Write", "Write",
        DomainOperationType.PREPARATION, reversible=True,
        required_permissions=(PermissionCapability.MEMORY_WRITE.value,),
    )
    workflow = DomainWorkflowDefinition(
        "project.workflow", "domain:project", "1.0.0", "Project",
        nodes=(WorkflowNode(
            "write", WorkflowNodeType.EXECUTE_OPERATION, "Write",
            operation_id="project.write",
        ),),
    )
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0",
        allowed_capabilities=(
            PermissionCapability.WORKFLOW_EXECUTE,
            PermissionCapability.OPERATION_EXECUTE,
        ),
        allowed_workflows=("project.workflow",),
        allowed_operations=("project.write",),
    ))

    decision = evaluate_domain_workflow(
        workflow, DomainPermissionResolver(registry),
        request_id="r", actor_id="a", session_id="s",
        operations={(operation.operation_id, operation.version): operation},
    )

    assert decision.decision is PermissionOutcome.DENY
    assert decision.node_decisions[0].decision is PermissionOutcome.DENY


def test_workflow_adapter_denies_cross_domain_subworkflow_node():
    parent_node = WorkflowNode("child", WorkflowNodeType.INVOKE_SUBWORKFLOW, "Child", subworkflow_id="health.workflow")
    child_node = WorkflowNode("done", WorkflowNodeType.COMPLETE, "Done")
    parent = DomainWorkflowDefinition("project.workflow", "domain:project", "1.0.0", "Parent", nodes=(parent_node,))
    child = DomainWorkflowDefinition("health.workflow", "domain:health", "1.0.0", "Child", nodes=(child_node,))
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy("project", "domain:project", "1.0.0", allowed_capabilities=(PermissionCapability.WORKFLOW_EXECUTE,), allowed_workflows=("project.workflow",)))
    registry.register(DomainPermissionPolicy("health", "domain:health", "1.0.0", allowed_capabilities=(PermissionCapability.WORKFLOW_EXECUTE,), allowed_workflows=("health.workflow",), allow_inbound_cross_domain_access=False))
    decision = evaluate_domain_workflow(parent, DomainPermissionResolver(registry), request_id="r", actor_id="a", session_id="s", workflows={(child.workflow_id, child.version): child})
    assert decision.decision is PermissionOutcome.DENY
    assert "source_cross_domain_denied" in decision.node_decisions[0].reasons


def test_workflow_adapter_preserves_cross_domain_approval_as_node_scoped():
    parent_node = WorkflowNode(
        "child",
        WorkflowNodeType.INVOKE_SUBWORKFLOW,
        "Child",
        subworkflow_id="health.workflow",
    )
    parent = DomainWorkflowDefinition(
        "project.workflow", "domain:project", "1.0.0", "Parent", nodes=(parent_node,)
    )
    child = DomainWorkflowDefinition(
        "health.workflow",
        "domain:health",
        "1.0.0",
        "Child",
        nodes=(WorkflowNode("done", WorkflowNodeType.COMPLETE, "Done"),),
        sensitivity="internal",
    )
    registry = DomainPermissionRegistry()
    registry.register(
        DomainPermissionPolicy(
            "project",
            "domain:project",
            "1.0.0",
            allowed_capabilities=(
                PermissionCapability.DOMAIN_CROSS_ACCESS,
                PermissionCapability.WORKFLOW_EXECUTE,
            ),
            allowed_workflows=("project.workflow", "health.workflow"),
            allow_cross_domain_access=True,
            allowed_target_domains=("domain:health",),
        )
    )
    registry.register(
        DomainPermissionPolicy(
            "health",
            "domain:health",
            "1.0.0",
            allowed_capabilities=(PermissionCapability.WORKFLOW_EXECUTE,),
            allowed_workflows=("health.workflow",),
            allow_inbound_cross_domain_access=True,
            allowed_source_domains=("domain:project",),
        )
    )

    decision = evaluate_domain_workflow(
        parent,
        DomainPermissionResolver(registry),
        request_id="r",
        actor_id="a",
        session_id="s",
        workflows={(child.workflow_id, child.version): child},
    )

    requirement = decision.node_decisions[0].approval_requirements[0]
    assert decision.node_decisions[0].decision is PermissionOutcome.APPROVAL_REQUIRED
    assert requirement.action is PermissionCapability.DOMAIN_CROSS_ACCESS
    assert requirement.node_id == "child"
    assert requirement.scope == "node"


def test_rule_adapter_allows_partial_enforcement_for_optional_rule():
    rule = DomainReasoningRuleDefinition(
        id="project.test", name="Test", version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN, category=ReasoningRuleCategory.SAFETY,
        status=ReasoningRuleStatus.ENABLED, priority=10, risk_level=ReasoningRiskLevel.LOW,
        domain_id="domain:project", required_permissions=("permission.modify",),
    )
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy("project", "domain:project", "1.0.0"))
    decision = evaluate_domain_rule(rule, DomainPermissionResolver(registry), request_id="r", actor_id="a", session_id="s", required=False)
    assert decision.blocked is True
    assert decision.partial_enforcement is True
