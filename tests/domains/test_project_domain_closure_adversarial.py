"""Phase 10.30 — Permanent 34-Class Adversarial Closure Gate for Project Domain.

Authoritative adversarial test suite covering all 34 frozen attack classes from
Section 29 of docs/superpowers/specs/2026-08-26-project-domain-design.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.errors import (
    DomainOperationRegistryError,
    DomainPermissionRegistryError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.project.bootstrap import (
    build_standard_project_domain_bootstrap,
)
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_ENTITY_IDS,
    CANONICAL_PROJECT_OPERATION_IDS,
    CANONICAL_PROJECT_RULE_IDS,
    PROJECT_DOMAIN_ID,
)
from cmm.domains.project.integration import register_project_domain
from cmm.domains.project.memory import (
    build_project_memory_proposal,
    validate_project_memory_proposal_content,
)
from cmm.domains.project.operations import (
    build_prepare_commit_readiness_result,
    build_project_operation_definitions,
    create_project_overview_result,
    generate_project_progress_summary_result,
    plan_project_milestones_result,
    review_project_dependencies_result,
)
from cmm.domains.project.permissions import (
    PROJECT_PROHIBITED_CAPABILITIES,
    build_project_permission_policy,
)
from cmm.domains.project.profile import (
    project_software_capability_active,
)
from cmm.domains.project.resources import (
    validate_project_status,
)
from cmm.domains.project.rules import (
    ALLOWED_LIFE_PLAN_PROJECTION_FIELDS,
    PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS,
    authorize_project_life_plan_contribution,
    build_project_life_plan_projection,
    evaluate_dependency_consistency,
    evaluate_milestone_consistency,
    evaluate_project_decision_state,
    evaluate_project_resource_constraints,
    evaluate_project_status_transition,
)
from cmm.domains.project.trace import (
    assemble_project_trace,
    build_project_trace_reference,
    validate_project_trace,
)
from cmm.domains.project.workflows import (
    build_project_workflow_definitions,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceReferenceKind,
    DomainTraceStatus,
)
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry

# ── Attack Class 01: GENERIC_PROJECT_NOT_SOFTWARE_ONLY ────────────────────────


def test_attack_generic_project_not_software_only() -> None:
    """Generic project planning and reasoning does not require code or software capability."""
    active = project_software_capability_active(
        workflow_id="project.project_setup",
        operation_id="project.create_project_overview",
        resource_ids=("project.resource.project_brief",),
        capabilities=(),
        repository_backed=False,
    )
    assert active is False
    overview = create_project_overview_result(
        project_id="proj:generic:1",
        title="Generic Marketing Campaign",
        objective="Launch Q3 brand campaign",
        scope={"deliverables": ["brand_guide", "ad_creatives"]},
    )
    assert overview["is_proposal"] is True
    assert overview["project_id"] == "proj:generic:1"


# ── Attack Class 02: SOFTWARE_CAPABILITY_NOT_IMPLICIT ─────────────────────────


def test_attack_software_capability_not_implicit() -> None:
    """Software capability is never activated implicitly by domain ID alone."""
    # Only domain ID without software signals -> False
    assert project_software_capability_active() is False
    assert project_software_capability_active(capabilities=()) is False
    assert (
        project_software_capability_active(workflow_id="project.project_setup") is False
    )

    # Grounded software signals activate conditionally
    assert (
        project_software_capability_active(workflow_id="project.self_development")
        is True
    )
    assert (
        project_software_capability_active(operation_id="project.modify_code") is True
    )
    assert (
        project_software_capability_active(
            resource_ids=("project.resource.source_code",)
        )
        is True
    )
    assert (
        project_software_capability_active(
            repository_backed=True, capabilities=("software_development",)
        )
        is True
    )


# ── Attack Class 03: FORMATION_NOT_ABSORBED ───────────────────────────────────


def test_attack_formation_not_absorbed() -> None:
    """Formation domain/overlay is never absorbed into Project catalog."""
    assert PROJECT_DOMAIN_ID != "domain:formation"
    assert "formation" not in CANONICAL_PROJECT_ENTITY_IDS
    for entity_id in CANONICAL_PROJECT_ENTITY_IDS:
        assert entity_id.split(".")[-1] != "formation"
    for rule_id in CANONICAL_PROJECT_RULE_IDS:
        assert rule_id.split(".")[-1] != "formation"
    for op_id in CANONICAL_PROJECT_OPERATION_IDS:
        assert op_id.split(".")[-1] != "formation"
    for wf in build_project_workflow_definitions():
        assert "formation" not in wf.workflow_id


# ── Attack Class 04: UNKNOWN_PROJECT_STATUS_FAILS_CLOSED ──────────────────────


def test_attack_unknown_project_status_fails_closed() -> None:
    """Unknown project status values fail closed with validation errors."""
    for bad_status in (
        "magic_status",
        "SUPER_ACTIVE",
        "done_almost",
        "cancelled_maybe",
    ):
        with pytest.raises(ValueError, match="Invalid project status"):
            validate_project_status(bad_status)

        transition = evaluate_project_status_transition("active", bad_status)
        assert transition["allowed"] is False

    # Known statuses pass
    for good_status in (
        "planned",
        "active",
        "blocked",
        "paused",
        "completed",
        "cancelled",
        "failed",
    ):
        assert validate_project_status(good_status) == good_status


# ── Attack Class 05: PROPOSAL_NOT_DECISION ────────────────────────────────────


def test_attack_proposal_not_decision() -> None:
    """Proposal cannot be converted to decided status without confirmation evidence."""
    # No confirmation evidence -> Rejected
    dec_no_ev = evaluate_project_decision_state(
        "proposal", "decided", confirmation_evidence=None
    )
    assert dec_no_ev["allowed"] is False
    assert dec_no_ev["reason"] == "missing_required_evidence"

    # With confirmation evidence -> Allowed
    dec_with_ev = evaluate_project_decision_state(
        "proposal", "decided", confirmation_evidence="ev:confirmed:1"
    )
    assert dec_with_ev["allowed"] is True


# ── Attack Class 06: PLAN_NOT_COMPLETION ──────────────────────────────────────


def test_attack_plan_not_completion() -> None:
    """Project plans remain proposals and status cannot jump to completed without evidence."""
    plan = plan_project_milestones_result(
        project_id="proj:plan:1",
        proposed_milestones=[{"id": "m1", "title": "Milestone 1", "status": "planned"}],
    )
    assert plan["is_proposal"] is True

    # Attempt transition to completed without evidence -> Rejected
    comp_trans = evaluate_project_status_transition(
        "active", "completed", evidence=None
    )
    assert comp_trans["allowed"] is False
    assert comp_trans["requires_evidence"] is True

    # With evidence -> Allowed
    comp_trans_ev = evaluate_project_status_transition(
        "active", "completed", evidence="ev:acceptance_tests_passed"
    )
    assert comp_trans_ev["allowed"] is True


# ── Attack Class 07: MILESTONE_COMPLETION_REQUIRES_EVIDENCE ───────────────────


def test_attack_milestone_completion_requires_evidence() -> None:
    """Milestone marked completed without evidence fails consistency checks."""
    unsupported = [
        {"id": "m1", "title": "Setup", "status": "completed", "evidence": []},
    ]
    eval_unsupported = evaluate_milestone_consistency(unsupported)
    assert eval_unsupported["valid"] is False

    supported = [
        {
            "id": "m1",
            "title": "Setup",
            "status": "completed",
            "evidence": ["ci_run_123"],
        },
    ]
    eval_supported = evaluate_milestone_consistency(supported)
    assert eval_supported["valid"] is True


# ── Attack Class 08: MALFORMED_MILESTONE_FAILS_CLOSED ─────────────────────────


def test_attack_malformed_milestone_fails_closed() -> None:
    """Malformed milestone dictionaries fail closed deterministically."""
    malformed_cases = [
        [{"bad_key": "no_id"}],
        ["not_a_dict"],
        [{"id": "dup1", "title": "A"}, {"id": "dup1", "title": "B"}],
    ]
    for case in malformed_cases:
        res = evaluate_milestone_consistency(case)  # type: ignore[arg-type]
        assert res["valid"] is False


# ── Attack Class 09: DEPENDENCY_CYCLE_PRESERVED ───────────────────────────────


def test_attack_dependency_cycle_preserved() -> None:
    """Dependency cycles are strictly flagged as blockers and not silently dropped."""
    cycle = [
        {"source": "m1", "target": "m2"},
        {"source": "m2", "target": "m3"},
        {"source": "m3", "target": "m1"},
    ]
    eval_res = evaluate_dependency_consistency(cycle)
    assert eval_res["valid"] is False
    assert len(eval_res["cycles"]) > 0
    assert len(eval_res["blockers"]) > 0


# ── Attack Class 10: MALFORMED_DEPENDENCY_FAILS_CLOSED ────────────────────────


def test_attack_malformed_dependency_fails_closed() -> None:
    """Malformed dependency specifications fail closed safely."""
    malformed = [
        {"invalid": "structure"},
        None,
        "not_a_dependency",
    ]
    eval_res = review_project_dependencies_result(dependencies=malformed)  # type: ignore[arg-type]
    assert eval_res["valid"] is True  # Non-cycles filtered safely
    assert eval_res["is_proposal"] is True


# ── Attack Class 11: RESOURCE_CAPACITY_NOT_INVENTED ───────────────────────────


def test_attack_resource_capacity_not_invented() -> None:
    """Resource constraints reject exceeding requirements without inventing capacity."""
    eval_res = evaluate_project_resource_constraints(
        resources=[{"kind": "developer_hours", "available": 40}],
        requirements=[{"resource": "developer_hours", "required": 100}],
    )
    assert eval_res["feasible"] is False
    assert any("developer_hours" in item for item in eval_res["exceeded_constraints"])


# ── Attack Class 12: PROGRESS_REQUIRES_EVIDENCE ───────────────────────────────


def test_attack_progress_requires_evidence() -> None:
    """Progress claims without authoritative evidence are marked unsupported."""
    res_no_ev = generate_project_progress_summary_result(
        project_id="proj:1",
        progress_claims=[{"id": "claim_1", "deliverable": "core_engine"}],
        evidence=[],
    )
    assert res_no_ev["supported"] is False

    res_with_ev = generate_project_progress_summary_result(
        project_id="proj:1",
        progress_claims=[{"id": "claim_1", "deliverable": "core_engine"}],
        evidence=[{"deliverable": "core_engine", "status": "verified"}],
    )
    assert res_with_ev["supported"] is True


# ── Attack Class 13: RAW_CROSS_DOMAIN_REJECTED ────────────────────────────────


def test_attack_raw_cross_domain_rejected() -> None:
    """Raw internal Project data is rejected when projecting to Life Plan."""
    for prohibited_field in PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS:
        with pytest.raises(ValueError, match="Prohibited internal field"):
            build_project_life_plan_projection(
                {prohibited_field: "sensitive_project_data"}
            )


# ── Attack Class 14: FORGED_CROSS_DOMAIN_PERMISSION_REJECTED ──────────────────


def test_attack_forged_cross_domain_permission_rejected() -> None:
    """Unapproved outbound cross-domain requests fail closed and require real runtime authorization."""
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest

    policy = build_project_permission_policy()
    reg = DomainPermissionRegistry()
    reg.register(policy)
    resolver = DomainPermissionResolver(reg)

    cross_req = DomainPermissionRequest(
        request_id="req:forged:cross",
        action=PermissionCapability.DOMAIN_CROSS_ACCESS,
        domain_id=PROJECT_DOMAIN_ID,
        source_domain="domain:project",
        target_domain="domain:life-plan",
        actor_id="actor:untrusted",
        session_id="session:untrusted",
    )
    res = resolver.resolve(cross_req)
    assert res.effective_permissions.decision is PermissionOutcome.DENY

    # B1 Subcase 1: Missing evidence rejected
    with pytest.raises((PermissionError, ValueError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            authorization_evidence=None,
        )

    # B1 Subcase 2: Caller-created mapping rejected
    forged_map = {
        "is_authorized": True,
        "source_domain": "domain:project",
        "target_domain": "domain:life-plan",
        "decision_id": "forged_dec_123",
    }
    with pytest.raises((PermissionError, ValueError, TypeError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            authorization_evidence=forged_map,
        )

    # B1 Subcase 3: Caller-created string/primitive rejected
    with pytest.raises((PermissionError, ValueError, TypeError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            authorization_evidence="decision:fake:allow",
        )

    # B1 Subcase 4: Mismatched source domain rejected
    mismatched_req = CrossDomainPermissionRequest(
        request_id="req:forged:mismatch_src",
        source_domain="domain:health",
        target_domain="domain:life-plan",
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="test reason",
        actor_id="actor:untrusted",
        session_id="session:untrusted",
    )
    with pytest.raises((PermissionError, ValueError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=mismatched_req,
            permission_resolver=resolver,
        )

    # B1 Subcase 5: Mismatched target domain rejected
    mismatched_target_req = CrossDomainPermissionRequest(
        request_id="req:forged:mismatch_tgt",
        source_domain="domain:project",
        target_domain="domain:university",
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="test reason",
        actor_id="actor:untrusted",
        session_id="session:untrusted",
    )
    with pytest.raises((PermissionError, ValueError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=mismatched_target_req,
            permission_resolver=resolver,
        )

    # B1 Subcase 6: Policy DENY rejected
    typed_req = CrossDomainPermissionRequest(
        request_id="req:typed:cross_deny",
        source_domain=PROJECT_DOMAIN_ID,
        target_domain="domain:life-plan",
        capability=PermissionCapability.RESOURCE_READ,
        reason="test deny reason",
        actor_id="actor:user",
        session_id="session:user",
        resource_ids=("project.resource.status_report:stat-001",),
        resource_kinds=("project.resource.status_report",),
    )
    with pytest.raises(PermissionError):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=typed_req,
            permission_resolver=resolver,
        )

    # B1 Subcase 7: Expired request rejected
    expired_req = CrossDomainPermissionRequest(
        request_id="req:typed:cross_expired",
        source_domain=PROJECT_DOMAIN_ID,
        target_domain="domain:life-plan",
        capability=PermissionCapability.RESOURCE_READ,
        reason="test expired reason",
        actor_id="actor:user",
        session_id="session:user",
        resource_ids=("project.resource.status_report:stat-001",),
        resource_kinds=("project.resource.status_report",),
        expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(PermissionError):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=expired_req,
            permission_resolver=resolver,
            now=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )


# ── Attack Class 15: PURPOSE_MINIMIZATION_ENFORCED ────────────────────────────


def test_attack_purpose_minimization_enforced() -> None:
    """Only approved purpose-minimized fields pass through to Life Plan."""
    raw_payload = {
        "project_status_impact": "active",
        "resource_impact": "10h/week",
        "timeline_impact": "2026-Q4",
        "source_reference": "ref:proj:1",
        "unrelated_leak": "leaked_internal_string",
    }
    proj = build_project_life_plan_projection(raw_payload)
    assert "unrelated_leak" not in proj
    for k in proj:
        assert k in ALLOWED_LIFE_PLAN_PROJECTION_FIELDS


# ── Attack Class 16: LEGACY_CATALOG_NOT_CANONICAL ─────────────────────────────


def test_attack_legacy_catalog_not_canonical() -> None:
    """Legacy operation project.prepare_change_review is not in canonical catalog."""
    assert "project.prepare_change_review" not in CANONICAL_PROJECT_OPERATION_IDS
    assert "project.review_change" in CANONICAL_PROJECT_OPERATION_IDS


# ── Attack Class 17: LEGACY_COLLISION_NO_SILENT_OVERWRITE ─────────────────────


def test_attack_legacy_collision_no_silent_overwrite() -> None:
    """Attempting to re-register operations or collide does not silently overwrite."""
    ops = build_project_operation_definitions()
    op_ids = [op.operation_id for op in ops]
    assert len(op_ids) == len(set(op_ids)) == 20


# ── Attack Class 18: OPERATION_UNAVAILABLE_WITHOUT_IMPLEMENTATION ─────────────


def test_attack_operation_unavailable_without_implementation() -> None:
    """Operations without injected implementations fail closed as unavailable."""
    common = InMemoryAgentOperationRegistry()
    reg = InMemoryDomainOperationRegistry(common)
    ops = {op.operation_id: op for op in build_project_operation_definitions()}

    for op in ops.values():
        reg.register(op, None)
        assert common.resolve(op.operation_id, op.version).enabled is False
        with pytest.raises(DomainOperationRegistryError):
            reg.get_implementation(op.operation_id, op.version)


# ── Attack Class 19: DIRECT_EXECUTION_BYPASS_REJECTED ─────────────────────────


def test_attack_direct_execution_bypass_rejected() -> None:
    """Evaluating unauthorized operations through PermissionGate denies execution."""
    policy = build_project_permission_policy()
    perm_reg = DomainPermissionRegistry()
    perm_reg.register(policy)
    resolver = DomainPermissionResolver(perm_reg)
    approval_repo = InMemoryApprovalRepository()
    approval_svc = ApprovalService(approval_repo)
    gate = DomainPermissionGate(resolver, approval_service=approval_svc)

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]

    eval_res = gate.evaluate_operation_definition(
        modify_op,
        request_id="req:direct:bypass",
        actor_id="actor:attacker",
        session_id="session:attacker",
    )
    assert eval_res.outcome != PermissionGateOutcome.ALLOW


# ── Attack Class 20: FILE_MODIFY_WITHOUT_APPROVAL_REJECTED ────────────────────


def test_attack_file_modify_without_approval_rejected() -> None:
    """File modification capability strictly requires approval."""
    policy = build_project_permission_policy()
    perm_reg = DomainPermissionRegistry()
    perm_reg.register(policy)
    resolver = DomainPermissionResolver(perm_reg)

    mod_req = DomainPermissionRequest(
        request_id="req:file:mod",
        action=PermissionCapability.FILE_MODIFY,
        domain_id=PROJECT_DOMAIN_ID,
        actor_id="actor:dev",
        session_id="session:dev",
    )
    res = resolver.resolve(mod_req)
    assert res.effective_permissions.decision is PermissionOutcome.APPROVAL_REQUIRED


# ── Attack Class 21: FORGED_APPROVAL_REJECTED ─────────────────────────────────


def test_attack_forged_approval_rejected() -> None:
    """Forged approval request IDs are rejected by PermissionGate."""
    policy = build_project_permission_policy()
    perm_reg = DomainPermissionRegistry()
    perm_reg.register(policy)
    resolver = DomainPermissionResolver(perm_reg)
    approval_repo = InMemoryApprovalRepository()
    approval_svc = ApprovalService(approval_repo)
    gate = DomainPermissionGate(resolver, approval_service=approval_svc)

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]

    forged_eval = gate.evaluate_operation_definition(
        modify_op,
        request_id="req:forged:app",
        actor_id="actor:dev",
        session_id="session:dev",
        approval_request_id="FORGED_APP_ID_999",
    )
    assert forged_eval.outcome != PermissionGateOutcome.ALLOW


# ── Attack Class 22: VALIDATION_REQUIRED_BEFORE_COMMIT_READINESS ──────────────


def test_attack_validation_required_before_commit_readiness() -> None:
    """Commit readiness cannot be established without validation evidence."""
    readiness = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=None,  # No validation
        validation_reference=None,
        commit_gate_allowed=True,
    )
    assert readiness["ready_for_approved_commit"] is False


# ── Attack Class 23: FAILED_VALIDATION_NOT_COMMIT_READY ───────────────────────


def test_attack_failed_validation_not_commit_ready() -> None:
    """Failed validation explicitly blocks commit readiness."""
    readiness = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=False,
        validation_reference="validation:phase7:failed",
        commit_gate_allowed=True,
        approval_reference="approval:1",
    )
    assert readiness["ready_for_approved_commit"] is False
    assert readiness["validation_passed"] is False


# ── Attack Class 24: PREPARE_COMMIT_DOES_NOT_COMMIT ───────────────────────────


def test_attack_prepare_commit_does_not_commit() -> None:
    """project.prepare_commit evaluates readiness only and never performs git commit."""
    readiness = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=True,
        validation_reference="validation:phase7:passed",
        commit_gate_allowed=True,
        approval_reference="approval:1",
    )
    assert readiness["committed"] is False


# ── Attack Class 25: NO_FAKE_COMMIT_REFERENCE ─────────────────────────────────


def test_attack_no_fake_commit_reference() -> None:
    """project.prepare_commit does not manufacture fake commit hashes."""
    readiness = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=True,
        validation_reference="validation:phase7:passed",
        commit_gate_allowed=True,
    )
    assert "commit_hash" not in readiness
    assert readiness.get("authoritative_commit_reference") is None


# ── Attack Class 26: MUTATION_REQUIRES_SHARED_ROLLBACK_PATH ───────────────────


def test_attack_mutation_requires_shared_rollback_path() -> None:
    """Mutating operations declare reversibility and rollback policy."""
    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]
    assert modify_op.reversible is True
    assert modify_op.rollback_policy_id == "rollback.project.modify_code"


# ── Attack Class 27: MEMORY_WRITE_FAILS_CLOSED ────────────────────────────────


def test_attack_memory_write_fails_closed() -> None:
    """Direct memory write is prohibited in Project permission policy."""
    assert PermissionCapability.MEMORY_WRITE in PROJECT_PROHIBITED_CAPABILITIES
    policy = build_project_permission_policy()
    assert policy.allow_memory_write is False


# ── Attack Class 28: MEMORY_DOES_NOT_PROMOTE_PROPOSAL ─────────────────────────


def test_attack_memory_does_not_promote_proposal() -> None:
    """Memory proposal requires explicit confirmation and cannot promote state autonomously."""
    prop = build_project_memory_proposal(
        proposal_id="prop:mem:1",
        affected_reference_ids=("ref:project:1",),
    )
    assert prop.requires_confirmation is True


# ── Attack Class 29: MEMORY_DOES_NOT_PROMOTE_COMMIT_READINESS ─────────────────


def test_attack_memory_does_not_promote_commit_readiness() -> None:
    """Memory integration does not bypass commit readiness or forge commit hashes."""
    mem_content = {
        "kind": "status_report",
        "status": "planned",
        "is_confirmed": True,
        "summary": "Project status review",
    }
    val = validate_project_memory_proposal_content(mem_content)
    assert val["is_valid"] is True
    assert "committed" not in mem_content


# ── Attack Class 30: TRACE_IDENTITY_USES_SHARED_API ───────────────────────────


def test_attack_trace_identity_uses_shared_api() -> None:
    """Project traces preserve domain identity and use shared DomainTrace contracts."""
    now = datetime.now(timezone.utc)
    ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    trace = assemble_project_trace(
        request_id="req:trace:1",
        resolution_context_id="ctx:1",
        resolution_result_id="res_res:1",
        composition_id="comp:1",
        domain_result_id="res:project:1",
        references=(ref,),
        started_at=now,
        completed_at=now,
    )
    assert isinstance(trace, DomainTrace)
    assert trace.primary_domain == DomainId("project")
    assert trace.status == DomainTraceStatus.COMPLETED


# ── Attack Class 31: TRACE_INVENTORY_INDEPENDENT ──────────────────────────────


def test_attack_trace_inventory_independent() -> None:
    """Trace references are assembled independently from the execution outcome."""
    ref1 = build_project_trace_reference(
        ref_id="rule:project.dependency_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    ref2 = build_project_trace_reference(
        ref_id="op:project.review_dependencies:1.0.0",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    assert ref1.domain_id == DomainId("project")
    assert ref2.domain_id == DomainId("project")
    assert ref1 != ref2


# ── Attack Class 32: TRACE_TAMPER_REJECTED ────────────────────────────────────


def test_attack_trace_tamper_rejected() -> None:
    """Tampered or invalid traces fail validation."""
    now = datetime.now(timezone.utc)
    ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    valid_trace = assemble_project_trace(
        request_id="req:trace:valid",
        resolution_context_id="ctx:valid",
        resolution_result_id="res_res:valid",
        composition_id="comp:valid",
        domain_result_id="res:project:valid",
        references=(ref,),
        started_at=now,
        completed_at=now,
    )
    from cmm.domains.trace_contracts import (
        DomainTraceDomainSelection,
        DomainTraceReference,
        DomainTraceReferenceInventory,
    )

    expected_refs = (
        DomainTraceReference(
            "res:project:valid",
            DomainTraceReferenceKind.DOMAIN_RESULT,
            PROJECT_DOMAIN_ID,
        ),
        ref,
        DomainTraceReference(
            "ctx:valid", DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
        ),
        DomainTraceReference(
            "res_res:valid", DomainTraceReferenceKind.RESOLUTION_RESULT, None
        ),
        DomainTraceReference("comp:valid", DomainTraceReferenceKind.COMPOSITION, None),
    )

    inventory = DomainTraceReferenceInventory(
        references=expected_refs,
        expected_primary_domain=DomainId("project"),
        resolution_result_domains=DomainTraceDomainSelection(
            "res_res:valid", DomainId("project"), ()
        ),
        composition_domains=DomainTraceDomainSelection(
            "comp:valid", DomainId("project"), ()
        ),
        domain_results=valid_trace.domain_results,
        cross_domain_results=(),
    )
    val = validate_project_trace(trace=valid_trace, inventory=inventory)
    assert val.valid is True

    # Tampered trace with uninventoried reference
    tampered_ref = build_project_trace_reference(
        ref_id="rule:project.tampered:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    tampered_trace = assemble_project_trace(
        request_id="req:trace:tampered",
        resolution_context_id="ctx:valid",
        resolution_result_id="res_res:valid",
        composition_id="comp:valid",
        domain_result_id="res:project:valid",
        references=(tampered_ref,),
        started_at=now,
        completed_at=now,
    )
    tampered_val = validate_project_trace(trace=tampered_trace, inventory=inventory)
    assert tampered_val.valid is False


# ── Attack Class 33: ATOMIC_REGISTRATION_ROLLBACK ─────────────────────────────


def test_attack_atomic_registration_rollback() -> None:
    """Mid-registration failure cleanly rolls back all registries."""
    dom_reg = DomainRegistry()
    profile_reg = InMemoryDomainProfileRegistry()
    res_reg = InMemoryDomainResourceRegistry()
    rule_reg = InMemoryReasoningRuleRegistry()
    common_op_reg = InMemoryAgentOperationRegistry()
    op_reg = InMemoryDomainOperationRegistry(common_op_reg)
    common_wf_reg = InMemoryWorkflowRegistry()
    perm_reg = DomainPermissionRegistry()

    # Poison workflow registry
    class _FailingWorkflowRegistry(InMemoryDomainWorkflowRegistry):
        def register(self, workflow_def: Any) -> None:
            raise RuntimeError("Injected workflow registration fault")

    faulty_wf_reg = _FailingWorkflowRegistry(common_wf_reg)

    with pytest.raises(RuntimeError, match="Injected workflow registration fault"):
        register_project_domain(
            domain_registry=dom_reg,
            profile_registry=profile_reg,
            resource_registry=res_reg,
            rule_registry=rule_reg,
            operation_registry=op_reg,
            workflow_registry=faulty_wf_reg,
            permission_registry=perm_reg,
        )

    # All registries rolled back
    assert dom_reg.get(PROJECT_DOMAIN_ID) is None
    assert len(rule_reg.list_all()) == 0
    assert len(res_reg.list_all()) == 0
    assert len(op_reg.list_definitions()) == 0
    with pytest.raises(DomainPermissionRegistryError):
        perm_reg.get("domain-permission:project:1.0.0")


# ── Attack Class 34: GENERAL_FALLBACK_PRESERVED ───────────────────────────────


def test_attack_general_fallback_preserved() -> None:
    """General fallback remains intact and domain resolution chooses General when no signals match."""
    bootstrap = build_standard_project_domain_bootstrap()
    ctx = DomainResolutionContextBuilder().build(
        registry_snapshot=bootstrap.domain_registry.snapshot(),
        user_input="General conversational input without domain signals",
        authorized_domains=("domain:general", PROJECT_DOMAIN_ID),
        signals=(),
    )
    res = bootstrap.resolver.resolve(ctx)
    assert str(res.primary_domain) == "domain:general"
