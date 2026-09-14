"""Phase 10.30 — Permanent 34-Class Adversarial Closure Gate for Project Domain.

Authoritative adversarial test suite covering all 34 frozen attack classes from
Section 29 of docs/superpowers/specs/2026-08-26-project-domain-design.md.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.checkpoint_manager import CheckpointManager
from cmm.agent_runtime.checkpoint_repository import InMemoryCheckpointRepository
from cmm.agent_runtime.checkpoint_restoration import CheckpointRestorationManager
from cmm.agent_runtime.checkpoint_rollback_executor import (
    CheckpointRestorationRollbackExecutor,
)
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.transaction_manager import TransactionManager
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.development.analyzer import ProjectContext
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.validation_integration import (
    resolve_domain_operation_validation_requirements,
)
from cmm.domains.errors import (
    DomainOperationRegistryError,
    DomainPermissionRegistryError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_contracts import (
    DomainOperationRequest,
    DomainOperationStatus,
)
from cmm.domains.operation_execution import (
    DefaultDomainOperationOrchestrator,
    DomainOperationExecutionDelegate,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_adapters import evaluate_domain_operation
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
    build_project_trace_contribution,
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
    """Software capability is never activated implicitly by domain ID alone or forged primitives."""
    # Only domain ID without software signals -> False
    assert project_software_capability_active() is False
    assert project_software_capability_active(capabilities=()) is False
    assert (
        project_software_capability_active(workflow_id="project.project_setup") is False
    )

    # M5 Subcase 1: Forged workflow prefix rejected
    assert (
        project_software_capability_active(workflow_id="project.software_forged")
        is False
    )

    # M5 Subcase 2: Suffix collision resource rejected
    assert (
        project_software_capability_active(resource_ids=("attacker.source_code",))
        is False
    )

    # M5 Subcase 3: Bare repository boolean is not independent authority
    assert project_software_capability_active(repository_backed=True) is False

    # M5 Subcase 4: Repository-shaped caller mappings are not shared context.
    assert (
        project_software_capability_active(
            repository_context={"repo_path": "/path/to/repo"}
        )
        is False
    )
    assert (
        project_software_capability_active(
            repository_context={"repository_id": "repo:forged"}
        )
        is False
    )

    # M5 Subcase 5: Canonical-looking strings remain caller-owned primitives.
    assert (
        project_software_capability_active(workflow_id="project.self_development")
        is False
    )
    assert (
        project_software_capability_active(operation_id="project.modify_code") is False
    )
    assert (
        project_software_capability_active(
            resource_ids=("project.resource.source_code",)
        )
        is False
    )
    assert (
        project_software_capability_active(
            capabilities=("project_software_development",)
        )
        is False
    )
    assert project_software_capability_active(resource_ids=("source_code",)) is False

    # M5 Subcase 6: A typed-looking caller object is not ProjectContext.
    class FakeProjectContext:
        root = Path("/path/to/repo")
        files = ()
        total_python_files = 1
        truncated = False

    assert (
        project_software_capability_active(repository_context=FakeProjectContext())
        is False
    )

    class FakeWorkflowDefinition:
        workflow_id = "project.self_development"
        domain_id = PROJECT_DOMAIN_ID

    assert (
        project_software_capability_active(workflow_definition=FakeWorkflowDefinition())
        is False
    )

    # M5 Subcase 7: Public typed objects and clones are still caller-owned.
    assert (
        project_software_capability_active(
            repository_context=ProjectContext(
                root=Path(__file__).resolve().parents[2],
                files=(),
                total_python_files=0,
                truncated=False,
            )
        )
        is False
    )
    bootstrap = build_standard_project_domain_bootstrap()
    workflow = next(
        definition
        for definition in bootstrap.workflow_registry.list_for_domain(PROJECT_DOMAIN_ID)
        if definition.workflow_id == "project.self_development"
    )
    operation = next(
        definition
        for definition in bootstrap.operation_registry.list_definitions()
        if definition.operation_id == "project.modify_code"
    )
    resource = next(
        definition
        for definition in bootstrap.resource_registry.list_all()
        if definition.id == "project.resource.source_code"
    )
    assert (
        project_software_capability_active(workflow_definition=replace(workflow))
        is False
    )
    assert (
        project_software_capability_active(operation_definition=replace(operation))
        is False
    )
    assert (
        project_software_capability_active(resource_definitions=(replace(resource),))
        is False
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
    with pytest.raises((PermissionError, TypeError, ValueError)):
        authorize_project_life_plan_contribution({"project_status_impact": "active"})

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

    # B1 Subcase 2a: A caller-created typed ALLOW decision is not authority.
    from cmm.domains.permission_contracts import CrossDomainPermissionDecision

    forged_decision = CrossDomainPermissionDecision(
        request_id="caller:forged:allow",
        decision=PermissionOutcome.ALLOW,
    )
    with pytest.raises((PermissionError, ValueError, TypeError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_decision=forged_decision,
        )

    # B1 Subcase 2b: A mapping cannot wrap a typed decision into authority.
    with pytest.raises((PermissionError, ValueError, TypeError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            authorization_evidence={"permission_decision": forged_decision},
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
    """Evaluating unauthorized operations through PermissionGate denies execution and orchestrator enforces."""
    policy = build_project_permission_policy()
    perm_reg = DomainPermissionRegistry()
    perm_reg.register(policy)
    resolver = DomainPermissionResolver(perm_reg)
    approval_repo = InMemoryApprovalRepository()
    approval_svc = ApprovalService(approval_repo)
    gate = DomainPermissionGate(resolver, approval_service=approval_svc)

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]

    # 1. PermissionGate rejects unapproved execution
    eval_res = gate.evaluate_operation_definition(
        modify_op,
        request_id="req:direct:bypass",
        actor_id="actor:attacker",
        session_id="session:attacker",
    )
    assert eval_res.outcome != PermissionGateOutcome.ALLOW

    # 2. Orchestrator fails closed when unapproved request is executed
    class _DummyImpl:
        def __init__(self, definition: Any) -> None:
            self.definition = definition

        def execute(self, request: Any) -> dict[str, Any]:
            return {"status": "completed", "result": {}}

    common_reg = InMemoryAgentOperationRegistry()
    domain_op_reg = InMemoryDomainOperationRegistry(common_reg)
    domain_op_reg.register(modify_op, _DummyImpl(modify_op))
    adapter = AgentExecutionAdapter(
        registry=common_reg,
        execution_delegate=DomainOperationExecutionDelegate(domain_op_reg),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        domain_op_reg,
        adapter,
        approval_service=approval_svc,
        permission_gate=gate,
    )
    unapproved_req = DomainOperationRequest(
        request_id="req:unapproved:1",
        operation_id=modify_op.operation_id,
        operation_version=modify_op.version,
        inputs={"runtime_action": {}, "modified_files": []},
        agent_run_id="run:atk:1",
        workflow_id="project.self_development",
        task_id="task:atk:1",
        session_id="session:atk",
        primary_domain_id=PROJECT_DOMAIN_ID,
        idempotency_key="idem:atk:1",
        available_resources=modify_op.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor:attacker"},
    )
    orch_res = orchestrator.execute(unapproved_req)
    assert orch_res.status in (
        DomainOperationStatus.BLOCKED,
        DomainOperationStatus.WAITING_FOR_APPROVAL,
        DomainOperationStatus.FAILED,
    )


# ── Attack Class 20: FILE_MODIFY_WITHOUT_APPROVAL_REJECTED ────────────────────


def test_attack_file_modify_without_approval_rejected(tmp_path) -> None:
    """File modification capability strictly requires approval and cannot be executed via generic approval alone."""
    validation_root = tmp_path / "validation-root"
    validation_root.mkdir(parents=True, exist_ok=True)
    (validation_root / "main.py").write_text("x = 1\n", encoding="utf-8")
    policy = build_project_permission_policy()
    perm_reg = DomainPermissionRegistry()
    perm_reg.register(policy)
    resolver = DomainPermissionResolver(perm_reg)

    # Subcase 1: Direct FILE_MODIFY permission request requires approval
    mod_req = DomainPermissionRequest(
        request_id="req:file:mod",
        action=PermissionCapability.FILE_MODIFY,
        domain_id=PROJECT_DOMAIN_ID,
        actor_id="actor:dev",
        session_id="session:dev",
    )
    res = resolver.resolve(mod_req)
    assert res.effective_permissions.decision is PermissionOutcome.APPROVAL_REQUIRED

    # Subcase 2: Operation definition declares FILE_MODIFY capability
    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]
    assert modify_op.required_permissions == (PermissionCapability.FILE_MODIFY.value,)

    class _MockModifyImpl:
        def __init__(self, definition: Any) -> None:
            self.definition = definition
            self.execution_count = 0
            # Host authority: the implementation declares the tree it
            # mutates; the orchestrator validates that tree.
            self.host_project_root = str(validation_root)

        def execute(self, request: Any) -> dict[str, Any]:
            self.execution_count += 1
            return {
                "success": True,
                "output": {
                    "status": "completed",
                    "result": {
                        "modified_files": list(
                            request.parameters.get("modified_files", [])
                        )
                    },
                },
                "modified_files": request.parameters.get("modified_files", []),
            }

    modify_impl = _MockModifyImpl(modify_op)
    common_reg = InMemoryAgentOperationRegistry()
    domain_reg = InMemoryDomainOperationRegistry(common_reg)
    domain_reg.register(modify_op, modify_impl)

    class _DummyVersionProvider:
        def capture_version(self, rkey: str) -> str:
            return "v1"

        def verify_version(self, rkey: str, ver: str) -> bool:
            return True

        def restore_version(self, rkey: str, ver: str) -> bool:
            return True

    res_provider = _DummyVersionProvider()
    cp_repo = InMemoryCheckpointRepository()
    cp_mgr = CheckpointManager(repository=cp_repo, resource_provider=res_provider)
    tx_mgr = TransactionManager(cp_mgr)
    rest_mgr = CheckpointRestorationManager(
        repository=cp_repo, resource_provider=res_provider
    )
    rollback_exec = CheckpointRestorationRollbackExecutor(
        transaction_manager=tx_mgr, restoration_manager=rest_mgr
    )

    approval_repo = InMemoryApprovalRepository()
    approval_svc = ApprovalService(approval_repo)
    gate = DomainPermissionGate(resolver, approval_service=approval_svc)
    adapter = AgentExecutionAdapter(
        registry=common_reg,
        execution_delegate=DomainOperationExecutionDelegate(domain_reg),
        validation_adapter=AgentValidationAdapter(),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        domain_reg,
        adapter,
        approval_service=approval_svc,
        permission_gate=gate,
        transaction_manager=tx_mgr,
        rollback_executor=rollback_exec,
        operation_validation_provider=resolve_domain_operation_validation_requirements,
    )

    proto_req = DomainOperationRequest(
        request_id="req:adv:mod:1",
        operation_id=modify_op.operation_id,
        operation_version=modify_op.version,
        inputs={"runtime_action": {}, "modified_files": ["file.py"]},
        agent_run_id="run:adv:1",
        workflow_id="project.self_development",
        task_id="task:adv:1",
        session_id="session:adv",
        primary_domain_id=PROJECT_DOMAIN_ID,
        idempotency_key="idem:adv:1",
        granted_permissions=modify_op.required_permissions,
        available_resources=modify_op.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor:dev"},
    )

    # Subcase 3: Generic OPERATION_EXECUTE approval only -> BLOCKED
    generic_req = PermissionApprovalRequirement(
        requirement_id=f"operation:project.modify_code:1.0.0:{proto_req.request_id}:operation_requires_approval",
        action=PermissionCapability.OPERATION_EXECUTE,
        actor_id="actor:dev",
        session_id="session:adv",
        domain_id=PROJECT_DOMAIN_ID,
        operation_id="project.modify_code",
        operation_version="1.0.0",
        fingerprint=f"{proto_req.request_id}:project.modify_code:1.0.0:actor:dev:session:adv:operation_requires_approval",
        scope="operation",
        reason_code="operation_requires_approval",
        risk="high",
    )
    bridged_gen = to_approval_requirement(generic_req, agent_run_id="run:adv:1")
    app_gen = approval_svc.create_request_from_requirement(
        bridged_gen,
        requested_by="agent:dev",
        metadata_override={
            "domain_request_fingerprint": proto_req.calculate_fingerprint()
        },
    )
    approval_svc.approve(app_gen.id, actor_id="lead", comment="approve op only")

    req_gen_only = replace(
        proto_req,
        approval_request_id=app_gen.id,
        metadata={
            "actor_id": "actor:dev",
            "approval_request_ids": {generic_req.requirement_id: app_gen.id},
        },
    )
    res_gen_only = orchestrator.execute(req_gen_only)
    assert res_gen_only.status in (
        DomainOperationStatus.WAITING_FOR_APPROVAL,
        DomainOperationStatus.BLOCKED,
    )
    assert modify_impl.execution_count == 0

    # Subcase 4: FILE_MODIFY prohibited policy variant -> BLOCKED
    prohibited_policy = replace(
        policy,
        policy_id="policy:project:no_file_modify",
        prohibited_capabilities=(
            *policy.prohibited_capabilities,
            PermissionCapability.FILE_MODIFY,
        ),
        allowed_capabilities=tuple(
            c
            for c in policy.allowed_capabilities
            if c is not PermissionCapability.FILE_MODIFY
        ),
    )
    proh_reg = DomainPermissionRegistry()
    proh_reg.register(prohibited_policy)
    proh_resolver = DomainPermissionResolver(proh_reg)
    proh_gate = DomainPermissionGate(proh_resolver, approval_service=approval_svc)
    proh_orchestrator = DefaultDomainOperationOrchestrator(
        domain_reg,
        adapter,
        approval_service=approval_svc,
        permission_gate=proh_gate,
    )
    res_proh = proh_orchestrator.execute(req_gen_only)
    assert res_proh.status is DomainOperationStatus.BLOCKED
    assert modify_impl.execution_count == 0

    # Subcase 5: Forged/mismatched FILE_MODIFY approval -> BLOCKED
    forged_req = replace(
        proto_req,
        approval_request_id=app_gen.id,
        metadata={
            "actor_id": "actor:dev",
            "approval_request_ids": {
                generic_req.requirement_id: app_gen.id,
                f"domain-permission:project:1.0.0:1.0.0:{proto_req.request_id}:file.modify": "FORGED_APP_ID",
            },
        },
    )
    res_forged = orchestrator.execute(forged_req)
    assert res_forged.status is DomainOperationStatus.BLOCKED
    assert modify_impl.execution_count == 0

    # Subcase 6: Valid OPERATION_EXECUTE + valid FILE_MODIFY approvals -> ALLOW / COMPLETED
    op_decision = evaluate_domain_operation(
        modify_op,
        resolver,
        request_id=proto_req.request_id,
        actor_id="actor:dev",
        session_id="session:adv",
    )
    assert op_decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    approval_ids: dict[str, str] = {}
    op_exec_id: str | None = None
    for req_item in op_decision.approval_requirements:
        bridged_item = to_approval_requirement(
            req_item, agent_run_id=proto_req.agent_run_id
        )
        created_app = approval_svc.create_request_from_requirement(
            bridged_item,
            requested_by="agent:dev",
            metadata_override={
                "domain_request_fingerprint": proto_req.calculate_fingerprint()
            },
        )
        approval_svc.approve(
            created_app.id,
            actor_id="lead",
            comment=f"Approved {req_item.requirement_id}",
        )
        approval_ids[req_item.requirement_id] = created_app.id
        if req_item.action is PermissionCapability.OPERATION_EXECUTE:
            op_exec_id = created_app.id

    assert op_exec_id is not None
    valid_dual_req = replace(
        proto_req,
        approval_request_id=op_exec_id,
        metadata={
            "actor_id": "actor:dev",
            "approval_request_ids": approval_ids,
            "validation_project_root": str(validation_root),
        },
    )
    res_dual = orchestrator.execute(valid_dual_req)
    assert res_dual.status is DomainOperationStatus.COMPLETED
    assert modify_impl.execution_count == 1


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

    # Caller cannot forge committed state via caller string or boolean
    forged_ref = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=True,
        validation_reference="validation:phase7:passed",
        commit_gate_allowed=True,
        approval_reference="approval:1",
        authoritative_commit_reference="caller:fake:commit",
    )
    assert forged_ref["committed"] is False


# ── Attack Class 25: NO_FAKE_COMMIT_REFERENCE ─────────────────────────────────


def test_attack_no_fake_commit_reference() -> None:
    """project.prepare_commit does not manufacture fake commit hashes or accept unverified commit outcomes."""
    # Subcase 1: No fabricated commit hash emitted
    readiness = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=True,
        validation_reference="validation:phase7:passed",
        commit_gate_allowed=True,
    )
    assert "commit_hash" not in readiness
    assert readiness.get("authoritative_commit_reference") is None

    # Subcase 2: Failed validation + fake reference cannot commit
    res_val_fail = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=False,
        validation_reference=None,
        commit_gate_allowed=True,
        approval_reference="approval:1",
        authoritative_commit_reference="git:commit:123",
    )
    assert res_val_fail["ready_for_approved_commit"] is False
    assert res_val_fail["committed"] is False

    # Subcase 3: Denied gate + fake reference cannot commit
    res_gate_deny = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=True,
        validation_reference="validation:1",
        commit_gate_allowed=False,
        approval_reference="approval:1",
        authoritative_commit_reference="git:commit:123",
    )
    assert res_gate_deny["ready_for_approved_commit"] is False
    assert res_gate_deny["committed"] is False

    # Subcase 4: Missing approval + fake reference cannot commit
    res_no_appr = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=True,
        validation_reference="validation:1",
        commit_gate_allowed=True,
        approval_reference=None,
        authoritative_commit_reference="git:commit:123",
    )
    assert res_no_appr["ready_for_approved_commit"] is False
    assert res_no_appr["committed"] is False


# ── Attack Class 26: MUTATION_REQUIRES_SHARED_ROLLBACK_PATH ───────────────────


def test_attack_mutation_requires_shared_rollback_path(tmp_path: Path) -> None:
    """Mutating operations declare reversibility, rollback policy, and restore state via shared rollback executor."""
    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]
    assert modify_op.reversible is True
    assert modify_op.rollback_policy_id == "rollback.project.modify_code"

    # Prove actual rollback restoration through shared DefaultDomainOperationOrchestrator and CheckpointRestorationRollbackExecutor
    test_file = tmp_path / "mod.py"
    initial_bytes = b"# Original file content\n"
    test_file.write_bytes(initial_bytes)

    class _SnapshotVersionProvider:
        def __init__(self, target: Path) -> None:
            self.target = target
            self._snaps: dict[str, bytes] = {}

        def capture_version(self, rkey: str) -> str:
            data = self.target.read_bytes()
            d = hashlib.sha256(data).hexdigest()
            self._snaps[d] = data
            return d

        def verify_version(self, rkey: str, ver: str) -> bool:
            return self.capture_version(rkey) == ver

        def restore_version(self, rkey: str, ver: str) -> bool:
            if ver in self._snaps:
                self.target.write_bytes(self._snaps[ver])
                return True
            return False

    res_provider = _SnapshotVersionProvider(test_file)
    cp_repo = InMemoryCheckpointRepository()
    cp_mgr = CheckpointManager(repository=cp_repo, resource_provider=res_provider)
    tx_mgr = TransactionManager(cp_mgr)
    rest_mgr = CheckpointRestorationManager(
        repository=cp_repo, resource_provider=res_provider
    )
    rollback_exec = CheckpointRestorationRollbackExecutor(
        transaction_manager=tx_mgr, restoration_manager=rest_mgr
    )

    class _FailingModifyImpl:
        def __init__(self, definition: Any) -> None:
            self.definition = definition
            # Host authority: the implementation declares the tree it
            # mutates; the orchestrator validates that tree.
            self.host_project_root = str(tmp_path)

        def execute(self, request: Any) -> dict[str, Any]:
            test_file.write_bytes(b"# Corrupted content from failing operation\n")
            return {
                "success": False,
                "error": {
                    "code": "OPERATION_EXECUTION_FAILED",
                    "message": "Forced failure",
                    "details": {},
                },
                "output": {
                    "status": "failed",
                    "result": {
                        "modified_files": list(
                            request.parameters.get("modified_files", [])
                        )
                    },
                },
                "modified_files": request.parameters.get("modified_files", []),
            }

    common_reg = InMemoryAgentOperationRegistry()
    domain_op_reg = InMemoryDomainOperationRegistry(common_reg)
    domain_op_reg.register(modify_op, _FailingModifyImpl(modify_op))

    policy = build_project_permission_policy()
    perm_reg = DomainPermissionRegistry()
    perm_reg.register(policy)
    resolver = DomainPermissionResolver(perm_reg)
    approval_repo = InMemoryApprovalRepository()
    approval_svc = ApprovalService(approval_repo)
    gate = DomainPermissionGate(resolver, approval_service=approval_svc)

    adapter = AgentExecutionAdapter(
        registry=common_reg,
        execution_delegate=DomainOperationExecutionDelegate(domain_op_reg),
        validation_adapter=AgentValidationAdapter(),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        domain_op_reg,
        adapter,
        approval_service=approval_svc,
        permission_gate=gate,
        transaction_manager=tx_mgr,
        rollback_executor=rollback_exec,
        operation_validation_provider=resolve_domain_operation_validation_requirements,
    )

    proto_req = DomainOperationRequest(
        request_id="req:adv:fail:1",
        operation_id=modify_op.operation_id,
        operation_version=modify_op.version,
        inputs={"runtime_action": {}, "modified_files": ["mod.py"]},
        agent_run_id="run:adv:1",
        workflow_id="project.self_development",
        task_id="task:adv:1",
        session_id="session:adv",
        primary_domain_id=PROJECT_DOMAIN_ID,
        idempotency_key="idem:adv:fail",
        granted_permissions=modify_op.required_permissions,
        available_resources=modify_op.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor:dev"},
    )
    dec = evaluate_domain_operation(
        modify_op,
        resolver,
        request_id=proto_req.request_id,
        actor_id="actor:dev",
        session_id="session:adv",
    )
    app_ids: dict[str, str] = {}
    op_exec_app_id: str | None = None
    for req_item in dec.approval_requirements:
        bridged = to_approval_requirement(req_item, agent_run_id="run:adv:1")
        app_req = approval_svc.create_request_from_requirement(
            bridged,
            requested_by="agent:dev",
            metadata_override={
                "domain_request_fingerprint": proto_req.calculate_fingerprint()
            },
        )
        approval_svc.approve(app_req.id, actor_id="lead", comment="approve")
        app_ids[req_item.requirement_id] = app_req.id
        if req_item.action is PermissionCapability.OPERATION_EXECUTE:
            op_exec_app_id = app_req.id

    assert op_exec_app_id is not None
    exec_req = DomainOperationRequest(
        request_id=proto_req.request_id,
        operation_id=proto_req.operation_id,
        operation_version=proto_req.operation_version,
        inputs=proto_req.inputs,
        agent_run_id=proto_req.agent_run_id,
        workflow_id=proto_req.workflow_id,
        task_id=proto_req.task_id,
        session_id=proto_req.session_id,
        primary_domain_id=proto_req.primary_domain_id,
        idempotency_key=proto_req.idempotency_key,
        granted_permissions=proto_req.granted_permissions,
        available_resources=proto_req.available_resources,
        capabilities=proto_req.capabilities,
        approval_request_id=op_exec_app_id,
        metadata={
            "actor_id": "actor:dev",
            "approval_request_ids": app_ids,
            "validation_project_root": str(tmp_path),
        },
    )
    res = orchestrator.execute(exec_req)
    assert res.status is DomainOperationStatus.ROLLED_BACK
    assert res.rollback_result is not None
    assert res.rollback_result.attempted is True
    assert res.rollback_result.succeeded is True
    assert test_file.read_bytes() == initial_bytes


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
    """Trace references are assembled independently before trace creation and validated against prebuilt inventory."""
    from cmm.domains.trace_assembler import calculate_domain_trace_identity
    from cmm.domains.trace_contracts import (
        DomainResultTraceReference,
        DomainTraceAssemblyRequest,
        DomainTraceDomainSelection,
        DomainTraceReference,
        DomainTraceReferenceInventory,
        DomainTraceReferences,
    )

    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
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

    req_id = "req:adv:trace:1"
    ctx_id = "ctx:adv:1"
    res_id = "res:adv:1"
    comp_id = "comp:adv:1"
    result_id_str = "dres:proj:adv"

    trace_refs = DomainTraceReferences(
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        cross_domain_results=(),
        presentation_result_ids=(),
    )
    assembly_request = DomainTraceAssemblyRequest(
        request_id=req_id,
        goal_id=None,
        primary_domain=PROJECT_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            build_project_trace_contribution(
                domain_result_id=result_id_str,
                references=(ref1, ref2),
            ),
        ),
        references=trace_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id_str,
                PROJECT_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        metadata={},
    )
    predicted_identity = calculate_domain_trace_identity(assembly_request)

    # Prebuilt independent inventory
    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                result_id_str,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                PROJECT_DOMAIN_ID,
            ),
            ref1,
            ref2,
            DomainTraceReference(
                ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(comp_id, DomainTraceReferenceKind.COMPOSITION, None),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=predicted_identity.trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=PROJECT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, PROJECT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(comp_id, PROJECT_DOMAIN_ID, ()),
    )

    trace = assemble_project_trace(
        request_id=req_id,
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        started_at=now,
        completed_at=now,
        references=(ref1, ref2),
    )

    val = validate_project_trace(trace=trace, inventory=inventory)
    assert val.valid is True


# ── Attack Class 32: TRACE_TAMPER_REJECTED ────────────────────────────────────


def test_attack_trace_tamper_rejected() -> None:
    """Tampered, substituted, or forged traces fail validation."""
    from cmm.domains.trace_assembler import calculate_domain_trace_identity
    from cmm.domains.trace_contracts import (
        DomainResultTraceReference,
        DomainTraceAssemblyRequest,
        DomainTraceDomainSelection,
        DomainTraceReference,
        DomainTraceReferenceInventory,
        DomainTraceReferences,
    )

    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    req_id = "req:trace:valid"
    ctx_id = "ctx:valid"
    res_id = "res_res:valid"
    comp_id = "comp:valid"
    result_id_str = "res:project:valid"

    assembly_request = DomainTraceAssemblyRequest(
        request_id=req_id,
        goal_id=None,
        primary_domain=PROJECT_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            build_project_trace_contribution(
                domain_result_id=result_id_str,
                references=(ref,),
            ),
        ),
        references=DomainTraceReferences(
            resolution_context_id=ctx_id,
            resolution_result_id=res_id,
            composition_id=comp_id,
            cross_domain_results=(),
            presentation_result_ids=(),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id_str,
                PROJECT_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        metadata={},
    )
    predicted = calculate_domain_trace_identity(assembly_request)

    expected_refs = (
        DomainTraceReference(
            result_id_str,
            DomainTraceReferenceKind.DOMAIN_RESULT,
            PROJECT_DOMAIN_ID,
        ),
        ref,
        DomainTraceReference(ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None),
        DomainTraceReference(res_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None),
        DomainTraceReference(comp_id, DomainTraceReferenceKind.COMPOSITION, None),
    )

    inventory = DomainTraceReferenceInventory(
        references=expected_refs,
        expected_primary_domain=DomainId("project"),
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, DomainId("project"), ()
        ),
        composition_domains=DomainTraceDomainSelection(
            comp_id, DomainId("project"), ()
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=predicted.trace_id,
            ),
        ),
        cross_domain_results=(),
    )
    valid_trace = assemble_project_trace(
        request_id=req_id,
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        references=(ref,),
        started_at=now,
        completed_at=now,
    )
    val = validate_project_trace(trace=valid_trace, inventory=inventory)
    assert val.valid is True

    # Tamper 1: Uninventoried reference in trace
    tampered_ref = build_project_trace_reference(
        ref_id="rule:project.tampered:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    tampered_trace = assemble_project_trace(
        request_id="req:trace:tampered",
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        references=(tampered_ref,),
        started_at=now,
        completed_at=now,
    )
    assert (
        validate_project_trace(trace=tampered_trace, inventory=inventory).valid is False
    )

    # Tamper 2: Missing expected reference
    incomplete_trace = assemble_project_trace(
        request_id=req_id,
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        references=(),  # Omitted ref
        started_at=now,
        completed_at=now,
    )
    assert (
        validate_project_trace(trace=incomplete_trace, inventory=inventory).valid
        is False
    )

    # Tamper 3: FILE_MODIFY approval authority omitted from inventory
    perm_dec_ref = build_project_trace_reference(
        ref_id="permission-gate-decision-adv-1",
        kind=DomainTraceReferenceKind.PERMISSION_DECISION,
    )
    op_app_req_ref = build_project_trace_reference(
        ref_id="apr-op-exec-1",
        kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
    )
    file_app_req_ref = build_project_trace_reference(
        ref_id="apr-file-modify-1",
        kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
    )
    op_app_dec_ref = build_project_trace_reference(
        ref_id="dec-op-exec-1",
        kind=DomainTraceReferenceKind.APPROVAL_DECISION,
    )
    file_app_dec_ref = build_project_trace_reference(
        ref_id="dec-file-modify-1",
        kind=DomainTraceReferenceKind.APPROVAL_DECISION,
    )
    op_res_ref = build_project_trace_reference(
        ref_id="res:op:modify_code:1",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )

    auth_trace_refs = (
        perm_dec_ref,
        op_app_req_ref,
        file_app_req_ref,
        op_app_dec_ref,
        file_app_dec_ref,
        op_res_ref,
    )

    auth_trace_references = DomainTraceReferences(
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        cross_domain_results=(),
        presentation_result_ids=(),
    )

    auth_assembly = DomainTraceAssemblyRequest(
        request_id="req:trace:auth",
        goal_id=None,
        primary_domain=PROJECT_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            build_project_trace_contribution(
                domain_result_id="res:project:auth",
                references=auth_trace_refs,
            ),
        ),
        references=auth_trace_references,
        domain_results=(
            DomainResultTraceReference(
                "res:project:auth",
                PROJECT_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        metadata={},
    )
    predicted_auth = calculate_domain_trace_identity(auth_assembly)

    full_auth_inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                "res:project:auth",
                DomainTraceReferenceKind.DOMAIN_RESULT,
                PROJECT_DOMAIN_ID,
            ),
            *auth_trace_refs,
            DomainTraceReference(
                ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(comp_id, DomainTraceReferenceKind.COMPOSITION, None),
        ),
        expected_primary_domain=DomainId("project"),
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, DomainId("project"), ()
        ),
        composition_domains=DomainTraceDomainSelection(
            comp_id, DomainId("project"), ()
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id="res:project:auth",
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=predicted_auth.trace_id,
            ),
        ),
        cross_domain_results=(),
    )

    auth_trace = assemble_project_trace(
        request_id="req:trace:auth",
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id="res:project:auth",
        references=auth_trace_refs,
        started_at=now,
        completed_at=now,
    )
    assert (
        validate_project_trace(trace=auth_trace, inventory=full_auth_inventory).valid
        is True
    )

    # Omit FILE_MODIFY approval request from inventory
    omitted_file_auth_inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                "res:project:auth",
                DomainTraceReferenceKind.DOMAIN_RESULT,
                PROJECT_DOMAIN_ID,
            ),
            perm_dec_ref,
            op_app_req_ref,
            # file_app_req_ref omitted!
            op_app_dec_ref,
            file_app_dec_ref,
            op_res_ref,
            DomainTraceReference(
                ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(comp_id, DomainTraceReferenceKind.COMPOSITION, None),
        ),
        expected_primary_domain=DomainId("project"),
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, DomainId("project"), ()
        ),
        composition_domains=DomainTraceDomainSelection(
            comp_id, DomainId("project"), ()
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id="res:project:auth",
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=predicted_auth.trace_id,
            ),
        ),
        cross_domain_results=(),
    )
    assert (
        validate_project_trace(
            trace=auth_trace, inventory=omitted_file_auth_inventory
        ).valid
        is False
    )

    # Tamper 4: Approval decision substitution in inventory
    substituted_decision_inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                "res:project:auth",
                DomainTraceReferenceKind.DOMAIN_RESULT,
                PROJECT_DOMAIN_ID,
            ),
            perm_dec_ref,
            op_app_req_ref,
            file_app_req_ref,
            op_app_dec_ref,
            DomainTraceReference(
                "dec-forged-unrelated-999",
                DomainTraceReferenceKind.APPROVAL_DECISION,
                DomainId("project"),
            ),  # Substituted decision!
            op_res_ref,
            DomainTraceReference(
                ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(comp_id, DomainTraceReferenceKind.COMPOSITION, None),
        ),
        expected_primary_domain=DomainId("project"),
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, DomainId("project"), ()
        ),
        composition_domains=DomainTraceDomainSelection(
            comp_id, DomainId("project"), ()
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id="res:project:auth",
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=predicted_auth.trace_id,
            ),
        ),
        cross_domain_results=(),
    )
    assert (
        validate_project_trace(
            trace=auth_trace, inventory=substituted_decision_inventory
        ).valid
        is False
    )


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
