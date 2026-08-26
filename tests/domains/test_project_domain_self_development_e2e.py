"""Phase 10.30 — Project Domain Software & Self-Development End-to-End Acceptance Tests.

Tests the full software-project and self-development lifecycle:
- grounded software capability activation (repository, software workflow, software resources)
- all 10 software reasoning rules actively evaluate code quality, contracts, and debt
- controlled implementation workflow under approval gate (PermissionCapability.FILE_MODIFY -> APPROVAL_REQUIRED)
- prepare_commit evaluates readiness without fabricating git commits or executing subprocess
- memory proposals require confirmation; traces record all references deterministically
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningRuleContext,
    ReasoningRuleResultStatus,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.project.bootstrap import build_standard_project_domain_bootstrap
from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.project.memory import (
    build_project_memory_binding,
    build_project_memory_proposal,
    validate_project_memory_proposal_content,
)
from cmm.domains.project.operations import (
    build_prepare_commit_readiness_result,
    build_project_operation_definitions,
)
from cmm.domains.project.permissions import build_project_permission_policy
from cmm.domains.project.presentation import present_project_result
from cmm.domains.project.profile import (
    SOFTWARE_PROJECT_RULE_IDS,
    project_software_capability_active,
)
from cmm.domains.project.rules import build_project_rules
from cmm.domains.project.trace import (
    assemble_project_trace,
    build_project_trace_reference,
)
from cmm.domains.trace_contracts import DomainTraceReferenceKind, DomainTraceStatus


def test_software_and_self_development_lifecycle_e2e() -> None:
    # 1. Bootstrap system
    bootstrap = build_standard_project_domain_bootstrap()
    assert bootstrap.domain_registry.get(PROJECT_DOMAIN_ID) is not None

    # 2. Grounded Software Activation
    software_active = project_software_capability_active(
        workflow_id="project.self_development",
        operation_id="project.analyse_architecture",
        resource_ids=("project.resource.source_code", "project.resource.git_history"),
        capabilities=("software_development",),
        repository_backed=True,
    )
    assert software_active is True

    # 3. Active Software Reasoning Rules Evaluation
    rules = build_project_rules()
    software_rules = {r.definition.id: r for r in rules if r.definition.id in SOFTWARE_PROJECT_RULE_IDS}
    assert len(software_rules) == 10

    software_context = ReasoningRuleContext(
        reasoning_id="reasoning:software:e2e:1",
        timestamp=datetime.now(timezone.utc),
        metadata={
            "workflow_id": "project.self_development",
            "operation_id": "project.analyse_architecture",
            "resource_ids": ["project.resource.source_code"],
            "repository_backed": True,
            "architecture_findings": [{"contract": "clean_arch", "status": "passed"}],
            "validation_result": {"passed": True},
            "technical_debt": [],
        },
    )

    for rule in software_rules.values():
        res = rule.evaluate(software_context)
        assert res.status == ReasoningRuleResultStatus.APPLIED
        # Should not produce inactive markers in active software context
        assert not any(t.code == "SOFTWARE_CAPABILITY_INACTIVE" for t in res.trace_entries)

    # 4. Supervised Code Modification & Permission Gate
    policy = build_project_permission_policy()
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(policy)
    resolver = DomainPermissionResolver(perm_registry)
    approval_svc = ApprovalService(InMemoryApprovalRepository())
    gate = DomainPermissionGate(resolver, approval_service=approval_svc)

    perm_req = DomainPermissionRequest(
        request_id="req:perm:mod:1",
        action=PermissionCapability.FILE_MODIFY,
        domain_id=PROJECT_DOMAIN_ID,
        actor_id="actor:agent",
        session_id="session:dev",
    )
    resolution = resolver.resolve(perm_req)
    assert resolution.effective_permissions.decision is PermissionOutcome.APPROVAL_REQUIRED

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]

    # Without approval, gate rejects execution
    gate_res_unapproved = gate.evaluate_operation_definition(
        modify_op,
        request_id="req:gate:1",
        actor_id="actor:agent",
        session_id="session:dev",
    )
    assert gate_res_unapproved.outcome in (
        PermissionGateOutcome.APPROVAL_REQUIRED,
        PermissionGateOutcome.DENY,
    )

    # 5. Prepare Commit Readiness Semantics
    # Case A: Validation passed, gate allowed, but approval missing -> NOT ready
    readiness_unapproved = build_prepare_commit_readiness_result(
        change_id="change:feature_x",
        validation_passed=True,
        validation_reference="validation:phase7:pass",
        commit_gate_allowed=True,
        approval_reference=None,
    )
    assert readiness_unapproved["ready_for_approved_commit"] is False
    assert readiness_unapproved["committed"] is False
    assert "commit_hash" not in readiness_unapproved

    # Case B: Validation passed, gate allowed, approval present -> READY for approved commit
    readiness_ready = build_prepare_commit_readiness_result(
        change_id="change:feature_x",
        validation_passed=True,
        validation_reference="validation:phase7:pass",
        commit_gate_allowed=True,
        approval_reference="approval:user_grant_001",
    )
    assert readiness_ready["ready_for_approved_commit"] is True
    assert readiness_ready["committed"] is False
    assert "commit_hash" not in readiness_ready

    # Case C: External commit reference provided by authorized runtime
    readiness_committed = build_prepare_commit_readiness_result(
        change_id="change:feature_x",
        validation_passed=True,
        validation_reference="validation:phase7:pass",
        commit_gate_allowed=True,
        approval_reference="approval:user_grant_001",
        authoritative_commit_reference="git:commit:1a2b3c4d5e6f",
    )
    assert readiness_committed["ready_for_approved_commit"] is True
    assert readiness_committed["committed"] is True
    assert readiness_committed["authoritative_commit_reference"] == "git:commit:1a2b3c4d5e6f"

    # 6. Memory Integration
    proposal_content = {
        "kind": "architecture_document",
        "status": "decision",
        "is_confirmed": True,
        "summary": "Decided to maintain strict layer isolation",
    }
    assert validate_project_memory_proposal_content(proposal_content)["is_valid"] is True

    mem_proposal = build_project_memory_proposal(
        proposal_id="prop:arch:001",
        affected_reference_ids=("ref:project:arch",),
    )
    assert mem_proposal.requires_confirmation is True

    from dataclasses import dataclass

    @dataclass
    class _ResolvedView:
        view_id: str = f"view:project:1:{'0' * 12}"
        primary_domain: str = "domain:project"
        content_digest: str = "0" * 64

    binding = build_project_memory_binding(
        proposal=mem_proposal,
        view=_ResolvedView(),  # type: ignore[arg-type]
        trace_id="trace:software:e2e:1",
    )
    assert binding.trace_id == "trace:software:e2e:1"

    # 7. Trace Assembly
    now = datetime.now(timezone.utc)
    trace_ref = build_project_trace_reference(
        ref_id="op:project.prepare_commit:1.0.0",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    trace = assemble_project_trace(
        request_id="req:trace:dev:1",
        resolution_context_id="ctx:dev:1",
        resolution_result_id="res_res:dev:1",
        composition_id="comp:dev:1",
        domain_result_id="res:project:dev:1",
        references=(trace_ref,),
        started_at=now,
        completed_at=now,
    )
    assert trace.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert trace.status == DomainTraceStatus.COMPLETED

    # 8. Presentation Projection
    presented = present_project_result(readiness_ready)
    assert presented["domain_display_name"] == "Project"
    assert presented["ready_for_approved_commit"] is True
    assert presented["committed"] is False
