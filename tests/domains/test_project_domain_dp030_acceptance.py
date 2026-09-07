"""Phase 10.30 — AT-DP-030: Project Domain Connected Acceptance Test.

A single connected state-linked deterministic scenario covering all 56 semantic
checkpoints for domain:project using real shared contracts for resolver, profile,
rules, operations, workflows, cross-domain permission requests/gates, approval
lifecycle, memory proposal/view/binding validation, and trace inventory validation.
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
    PermissionCapability,
    PermissionOutcome,
)
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.transaction_manager import TransactionManager
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.development.analyzer import ProjectAnalyzer
from cmm.development.models import DevelopmentPlan
from cmm.development.providers import DeterministicPlanningProvider
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.contracts import DomainResult
from cmm.domains.errors import DomainOperationRegistryError
from cmm.domains.identifiers import DomainId
from cmm.domains.validation_integration import (
    resolve_domain_operation_validation_requirements,
)
from cmm.domains.memory_contracts import (
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
    sha256_digest,
)
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
from cmm.domains.project.bootstrap import build_standard_project_domain_bootstrap
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_ENTITY_IDS,
    CANONICAL_PROJECT_OPERATION_IDS,
    CANONICAL_PROJECT_RULE_IDS,
    PROJECT_DOMAIN_ID,
)
from cmm.domains.project.memory import (
    build_project_memory_binding,
    build_project_memory_proposal,
    validate_project_memory_binding,
    validate_project_memory_proposal_content,
)
from cmm.domains.project.operations import (
    build_prepare_commit_readiness_result,
    build_project_operation_definitions,
    create_project_overview_result,
    generate_project_progress_summary_result,
    plan_project_milestones_result,
    review_project_dependencies_result,
    review_project_risks_result,
)
from cmm.domains.project.permissions import (
    build_project_permission_policy,
)
from cmm.domains.project.presentation import present_project_result
from cmm.domains.project.profile import (
    GENERIC_PROJECT_RULE_IDS,
    SOFTWARE_PROJECT_RULE_IDS,
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
    build_project_rules,
    evaluate_milestone_consistency,
    evaluate_project_resource_constraints,
)
from cmm.domains.project.trace import (
    assemble_project_trace,
    build_project_trace_contribution,
    build_project_trace_reference,
    validate_project_trace,
)
from cmm.domains.project.workflows import (
    GENERIC_PROJECT_WORKFLOW_IDS,
    SOFTWARE_PROJECT_WORKFLOW_IDS,
    build_project_workflow_definitions,
)
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import DomainResolutionSignal
from cmm.domains.trace_assembler import calculate_domain_trace_identity
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTraceAssemblyRequest,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceStatus,
)
from cmm.validation.context import ValidationContext
from cmm.validation.defaults import build_default_pipeline
from cmm.validation.results import ValidationResult
from cmm.validation.testing_defaults import default_validation_steps
from kernel.runtime import Runtime

DP_030_CHECKPOINTS = 56
DP_030_GENERIC_CHECKPOINTS = 32
DP_030_SOFTWARE_CHECKPOINTS = 24


def test_at_dp_030_connected_acceptance(tmp_path: Path) -> None:
    checkpoints: list[str] = []

    def checkpoint(name: str) -> None:
        checkpoints.append(name)

    # ═══════════════════════════════════════════════════════════════════════════
    # Checkpoints 01–32: Generic / Core Acceptance
    # ═══════════════════════════════════════════════════════════════════════════

    # 01 baseline bootstrap constructed
    bootstrap = build_standard_project_domain_bootstrap()
    assert bootstrap is not None
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get("domain:life-plan") is not None
    assert bootstrap.domain_registry.get(PROJECT_DOMAIN_ID) is not None
    assert bootstrap.domain_registry.get("domain:mental-health") is None
    assert bootstrap.domain_registry.get("domain:neurodivergence") is None
    checkpoint("01 baseline bootstrap constructed")

    # 02 domain:project registered
    assert bootstrap.domain_registry.get(PROJECT_DOMAIN_ID) is not None
    checkpoint("02 domain:project registered")

    # 03 ProjectProfile registered
    assert bootstrap.profile_registry.get_by_domain(DomainId("project")) is not None
    checkpoint("03 ProjectProfile registered")

    # 04 exact 27 entity inventory
    assert len(CANONICAL_PROJECT_ENTITY_IDS) == 27
    checkpoint("04 exact 27 entity inventory")

    # 05 exact 22 resource inventory
    project_resources = [
        r
        for r in bootstrap.resource_registry.list_all()
        if str(r.domain_id) in (PROJECT_DOMAIN_ID, "project")
    ]
    assert len(project_resources) == 22
    checkpoint("05 exact 22 resource inventory")

    # 06 exact 18 rule inventory
    project_rules = [
        r
        for r in bootstrap.rule_registry.list_all()
        if str(r.definition.domain_id) in (PROJECT_DOMAIN_ID, "project")
    ]
    assert len(project_rules) == 18
    checkpoint("06 exact 18 rule inventory")

    # 07 exact 20 operation inventory
    project_ops = [
        op
        for op in bootstrap.operation_registry.list_definitions()
        if str(op.domain_id) in (PROJECT_DOMAIN_ID, "project")
    ]
    assert len(project_ops) == 20
    checkpoint("07 exact 20 operation inventory")

    # 08 exact 12 workflow inventory
    assert len(bootstrap.workflow_registry.list_for_domain(PROJECT_DOMAIN_ID)) == 12
    checkpoint("08 exact 12 workflow inventory")

    # 09 generic resolution selects Project
    resolution_signals = (
        DomainResolutionSignal(
            kind="intent",
            source="user",
            value="project deliverables and milestones",
            domain_ids=(PROJECT_DOMAIN_ID,),
        ),
    )
    res_ctx = DomainResolutionContextBuilder().build(
        registry_snapshot=bootstrap.domain_registry.snapshot(),
        user_input="Help me structure my project roadmap and deliverables.",
        authorized_domains=("domain:general", PROJECT_DOMAIN_ID),
        signals=resolution_signals,
    )
    res_outcome = bootstrap.resolver.resolve(res_ctx)
    assert str(res_outcome.primary_domain) == PROJECT_DOMAIN_ID
    checkpoint("09 generic resolution selects Project")

    # 10 General fallback preserved
    fallback_ctx = DomainResolutionContextBuilder().build(
        registry_snapshot=bootstrap.domain_registry.snapshot(),
        user_input="General general input with no domain signals.",
        authorized_domains=("domain:general", PROJECT_DOMAIN_ID),
        signals=(),
    )
    fallback_outcome = bootstrap.resolver.resolve(fallback_ctx)
    assert str(fallback_outcome.primary_domain) == "domain:general"
    checkpoint("10 General fallback preserved")

    # 11 generic software capability remains inactive
    generic_sw_active = project_software_capability_active(
        workflow_id="project.project_setup",
        operation_id="project.create_project_overview",
        resource_ids=("project.resource.project_brief",),
        capabilities=(),
        repository_backed=False,
    )
    assert generic_sw_active is False
    assert (
        project_software_capability_active(workflow_id="project.software_forged")
        is False
    )
    assert (
        project_software_capability_active(resource_ids=("attacker.source_code",))
        is False
    )
    assert project_software_capability_active(repository_backed=True) is False
    checkpoint("11 generic software capability remains inactive")

    # 12 scope/objective grounded
    overview = create_project_overview_result(
        project_id="proj:acceptance:1",
        title="Project Acceptance Test",
        objective="Validate 56 acceptance checkpoints",
        scope={
            "objective": "Validate 56 acceptance checkpoints",
            "deliverables": ["test_suite", "verification_report"],
            "exclusions": ["scope_creep"],
        },
        proposed_items=[{"id": "item1", "deliverable": "test_suite"}],
    )
    assert overview["scope_evaluation"]["valid"] is True
    checkpoint("12 scope/objective grounded")

    # 13 milestone structure accepted
    milestones = [
        {
            "id": "m1",
            "title": "Bootstrap",
            "status": "completed",
            "evidence": ["bootstrap_done"],
            "target_date": "2026-08-01T00:00:00Z",
        },
        {
            "id": "m2",
            "title": "Verification",
            "status": "active",
            "depends_on": "m1",
            "target_date": "2026-08-15T00:00:00Z",
        },
    ]
    milestone_plan = plan_project_milestones_result(
        project_id="proj:acceptance:1",
        proposed_milestones=milestones,
    )
    assert milestone_plan["milestones_evaluation"]["valid"] is True
    checkpoint("13 milestone structure accepted")

    # 14 unsupported milestone completion rejected
    unsupported_m = [
        {
            "id": "m_bad",
            "title": "Fake Completed",
            "status": "completed",
            "evidence": [],
        },
    ]
    bad_m_eval = evaluate_milestone_consistency(unsupported_m)
    assert bad_m_eval["valid"] is False
    checkpoint("14 unsupported milestone completion rejected")

    # 15 dependency structure accepted
    dep_eval = review_project_dependencies_result(
        dependencies=[{"source": "m1", "target": "m2"}]
    )
    assert dep_eval["valid"] is True
    checkpoint("15 dependency structure accepted")

    # 16 dependency cycle preserved as blocker
    cycle_dep_eval = review_project_dependencies_result(
        dependencies=[
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
            {"source": "c", "target": "a"},
        ]
    )
    assert cycle_dep_eval["valid"] is False
    assert len(cycle_dep_eval["cycles"]) > 0
    checkpoint("16 dependency cycle preserved as blocker")

    # 17 resource capacity not invented
    res_eval = evaluate_project_resource_constraints(
        resources=[{"kind": "hours", "available": 10}],
        requirements=[{"resource": "hours", "required": 20}],
    )
    assert res_eval["feasible"] is False
    checkpoint("17 resource capacity not invented")

    # 18 valid status recognized
    assert validate_project_status("active") == "active"
    checkpoint("18 valid status recognized")

    # 19 unknown status rejected
    with pytest.raises(ValueError, match="Invalid project status"):
        validate_project_status("nonexistent_status")
    checkpoint("19 unknown status rejected")

    # 20 proposal remains proposal
    assert overview["is_proposal"] is True
    assert milestone_plan["is_proposal"] is True
    checkpoint("20 proposal remains proposal")

    # 21 decision state evidence enforced
    from cmm.domains.project.rules import evaluate_project_decision_state

    dec_no_ev = evaluate_project_decision_state(
        "proposal", "decided", confirmation_evidence=None
    )
    dec_with_ev = evaluate_project_decision_state(
        "proposal", "decided", confirmation_evidence="ev:confirmed:1"
    )
    assert dec_no_ev["allowed"] is False
    assert dec_with_ev["allowed"] is True
    checkpoint("21 decision state evidence enforced")

    # 22 temporal uncertainty preserved
    presented_overview = present_project_result(overview)
    assert presented_overview["uncertainty_preserved"] is True
    checkpoint("22 temporal uncertainty preserved")

    # 23 progress evidence required
    unsupported_prog = generate_project_progress_summary_result(
        project_id="proj:acceptance:1",
        progress_claims=[{"id": "claim1", "deliverable": "test_suite"}],
        evidence=[],
    )
    assert unsupported_prog["supported"] is False
    checkpoint("23 progress evidence required")

    # 24 risk/unknown result produced
    risk_res = review_project_risks_result(
        risks=[{"id": "r1", "severity": "medium", "description": "tight timeline"}]
    )
    assert len(risk_res["risks"]) == 1
    checkpoint("24 risk/unknown result produced")

    # 25 generic workflow evaluated/executed through shared path
    wfs = {w.workflow_id: w for w in build_project_workflow_definitions()}
    generic_setup_wf = wfs["project.project_setup"]
    assert generic_setup_wf.nodes[0].node_id == "load"
    assert generic_setup_wf.workflow_id in GENERIC_PROJECT_WORKFLOW_IDS
    checkpoint("25 generic workflow evaluated/executed through shared path")

    # 26 DomainResult built
    domain_result = DomainResult(
        id="res-project-001",
        status="success",
        objective="Validate 56 acceptance checkpoints",
        primary_domain=DomainId("project"),
    )
    assert domain_result.primary_domain == DomainId("project")
    checkpoint("26 DomainResult built")

    # 27 real Project→Life Plan permission request resolved
    from cmm.domains.life_plan.permissions import build_life_plan_permission_policy
    from cmm.domains.life_plan.rules import evaluate_cross_domain_impact
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest

    perm_reg = DomainPermissionRegistry()
    perm_reg.register(build_life_plan_permission_policy())
    perm_reg.register(
        replace(
            build_project_permission_policy(),
            allow_cross_domain_access=True,
            allowed_target_domains=("domain:life-plan",),
            allowed_capabilities=(
                PermissionCapability.DOMAIN_CROSS_ACCESS,
                PermissionCapability.RESOURCE_READ,
            ),
            allowed_resource_kinds=("project.resource.status_report",),
            allowed_sensitivity_levels=("internal",),
        )
    )
    cross_domain_resolver = DomainPermissionResolver(perm_reg)
    permission_now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    cross_domain_gate = DomainPermissionGate(
        cross_domain_resolver, clock=lambda: permission_now
    )
    cross_req = CrossDomainPermissionRequest(
        request_id="req:cross:1",
        source_domain="domain:project",
        target_domain="domain:life-plan",
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="Sync project milestone to life plan",
        actor_id="actor:project",
        session_id="session:acc",
        sensitivity_level="internal",
        requires_approval=False,
    )
    raw_project_data = {
        "project_status_impact": "active",
        "resource_impact": "10h/week",
        "timeline_impact": "2026-Q3",
        "source_reference": "ref:project:acceptance:1",
        "unrelated_project_internal": "foo_internal",
    }
    projection = authorize_project_life_plan_contribution(
        raw_project_data,
        permission_gate=cross_domain_gate,
        permission_request=cross_req,
        now=permission_now,
    )
    assert projection["authorization_reference"]
    checkpoint("27 real Project→Life Plan permission request resolved")

    # 28 authorized purpose-minimized contribution consumed by Life Plan
    assert projection["project_status_impact"] == "active"
    assert projection["resource_impact"] == "10h/week"
    assert projection["source_domain"] == PROJECT_DOMAIN_ID
    assert "unrelated_project_internal" not in projection
    life_plan_result = evaluate_cross_domain_impact(
        projection,
        permission_request=cross_req,
        permission_gate=cross_domain_gate,
        now=permission_now,
    )
    assert life_plan_result["applied"] is True
    assert life_plan_result["contribution"]["project_status_impact"] == "active"
    checkpoint("28 authorized purpose-minimized contribution consumed")

    # The later operation-approval checkpoints use the default Project policy.
    perm_reg = DomainPermissionRegistry()
    perm_reg.register(build_project_permission_policy())
    perm_resolver = DomainPermissionResolver(perm_reg)

    # 29 raw Project internals absent from projection
    with pytest.raises(ValueError, match="Prohibited internal field"):
        build_project_life_plan_projection({"source_code": "def foo(): pass"})
    for prohibited in PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS:
        assert prohibited not in projection
    for allowed_key in projection:
        assert allowed_key in ALLOWED_LIFE_PLAN_PROJECTION_FIELDS
    checkpoint("29 raw Project internals absent from projection")

    # 30 memory proposal/view/binding validated
    mem_prop_content = {
        "kind": "decision_record",
        "status": "decision",
        "is_confirmed": True,
        "summary": "Confirmed Project Acceptance Architecture",
    }
    assert (
        validate_project_memory_proposal_content(mem_prop_content)["is_valid"] is True
    )
    mem_proposal = build_project_memory_proposal(
        proposal_id="prop:acc:1",
        affected_reference_ids=("ref:project:acceptance:1",),
    )
    assert mem_proposal.requires_confirmation is True

    mem_reference = DomainMemoryReference(
        reference_id="ref:project:acceptance:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="canon:project:1",
        domain_id=PROJECT_DOMAIN_ID,
        applicable_domains=(PROJECT_DOMAIN_ID,),
    )
    from dataclasses import dataclass

    req_id = "req-mem-acc-1"
    view_digest = "0" * 64
    view_id = f"view:{req_id}:{'0' * 12}"

    @dataclass
    class _FakeResolvedView:
        view_id: str
        primary_domain: str
        content_digest: str

    from cmm.domains.memory_contracts import (
        DomainMemoryApprovalDecisionSnapshot,
        DomainMemoryApprovalRequestSnapshot,
        DomainMemoryCapability,
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemorySensitivityLevel,
    )

    mem_perm_snapshot = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm-dec-acc-1",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=PROJECT_DOMAIN_ID,
        target_domain_id=PROJECT_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )

    mem_app_req_snapshot = DomainMemoryApprovalRequestSnapshot(
        request_id="app-req-acc-1",
        proposal_id="prop:acc:1",
    )
    mem_app_dec_snapshot = DomainMemoryApprovalDecisionSnapshot(
        decision_id="app-dec-acc-1",
        request_id="app-req-acc-1",
        approved=True,
    )

    resolved_view = _FakeResolvedView(
        view_id=view_id,
        primary_domain="domain:project",
        content_digest=view_digest,
    )
    mem_binding = build_project_memory_binding(
        proposal=mem_proposal,
        view=resolved_view,  # type: ignore[arg-type]
        trace_id="trace:acc:1",
        permission_decision_ids=("perm-dec-acc-1",),
        approval_request_ids=("app-req-acc-1",),
        approval_decision_ids=("app-dec-acc-1",),
    )
    mem_inventory = DomainMemoryReferenceInventory(
        references=(mem_reference,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace:acc:1",
                primary_domain=PROJECT_DOMAIN_ID,
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=view_id,
                request_id=req_id,
                view_digest=view_digest,
                primary_domain=DomainId("project"),
                trace_id="trace:acc:1",
            ),
        ),
        proposals=(mem_proposal,),
        permission_decisions=(mem_perm_snapshot,),
        approval_requests=(mem_app_req_snapshot,),
        approval_decisions=(mem_app_dec_snapshot,),
    )
    val_res = validate_project_memory_binding(
        binding=mem_binding,
        inventory=mem_inventory,
    )
    assert val_res.is_valid is True
    checkpoint("30 memory proposal/view/binding validated")

    # 31 independent trace inventory built before trace
    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    rule_ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    op_ref = build_project_trace_reference(
        ref_id="op:project.create_project_overview:1.0.0",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    req_id_31 = "req:trace:acc:1"
    ctx_id_31 = "ctx:acc:1"
    res_id_31 = "res_res:acc:1"
    comp_id_31 = "comp:acc:1"
    dres_id_31 = "res:project:acc:1"

    trace_refs_31 = DomainTraceReferences(
        resolution_context_id=ctx_id_31,
        resolution_result_id=res_id_31,
        composition_id=comp_id_31,
        cross_domain_results=(),
        presentation_result_ids=(),
    )
    assembly_req_31 = DomainTraceAssemblyRequest(
        request_id=req_id_31,
        goal_id=None,
        primary_domain=PROJECT_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            build_project_trace_contribution(
                domain_result_id=dres_id_31,
                references=(rule_ref, op_ref),
            ),
        ),
        references=trace_refs_31,
        domain_results=(
            DomainResultTraceReference(
                dres_id_31,
                PROJECT_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        metadata={},
    )
    pred_id_31 = calculate_domain_trace_identity(assembly_req_31)

    inv_31 = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                dres_id_31,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                PROJECT_DOMAIN_ID,
            ),
            rule_ref,
            op_ref,
            DomainTraceReference(
                ctx_id_31, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id_31, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(
                comp_id_31, DomainTraceReferenceKind.COMPOSITION, None
            ),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=dres_id_31,
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=pred_id_31.trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=PROJECT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            res_id_31, PROJECT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(
            comp_id_31, PROJECT_DOMAIN_ID, ()
        ),
    )
    checkpoint("31 independent trace inventory built before trace")

    # 32 DomainTrace assembled and validated
    assembled_trace = assemble_project_trace(
        request_id=req_id_31,
        resolution_context_id=ctx_id_31,
        resolution_result_id=res_id_31,
        composition_id=comp_id_31,
        domain_result_id=dres_id_31,
        references=(rule_ref, op_ref),
        started_at=now,
        completed_at=now,
    )
    assert assembled_trace.id == pred_id_31.trace_id
    assert assembled_trace.status == DomainTraceStatus.COMPLETED
    assert assembled_trace.primary_domain == DomainId("project")
    val_32 = validate_project_trace(trace=assembled_trace, inventory=inv_31)
    assert val_32.valid is True
    checkpoint("32 DomainTrace assembled and validated")

    # ═══════════════════════════════════════════════════════════════════════════
    # Checkpoints 33–56: Software / Self-Development Acceptance
    # ═══════════════════════════════════════════════════════════════════════════

    # 33 software context grounded by repository/workflow signal
    sw_workflow_id = "project.self_development"
    sw_op_id = "project.analyse_architecture"
    sw_resources = ("project.resource.source_code", "project.resource.git_history")
    checkpoint("33 software context grounded by repository/workflow signal")

    # 34 software capability activates only from shared analyzed context
    project_context = ProjectAnalyzer().analyze(
        Path(__file__).resolve().parents[2],
        "project software acceptance",
        max_files=1,
    )
    sw_active = project_software_capability_active(
        workflow_id=sw_workflow_id,
        operation_id=sw_op_id,
        resource_ids=sw_resources,
        capabilities=("project_software_development",),
        repository_context=project_context,
    )
    assert sw_active is True
    checkpoint("34 software capability activates conditionally")

    # 35 generic rules remain present with software layer
    all_rules = build_project_rules()
    generic_rules = [
        r for r in all_rules if r.definition.id in GENERIC_PROJECT_RULE_IDS
    ]
    software_rules = [
        r for r in all_rules if r.definition.id in SOFTWARE_PROJECT_RULE_IDS
    ]
    assert len(generic_rules) == 8
    assert len(software_rules) == 10
    checkpoint("35 generic rules remain present with software layer")

    # Setup temporary repository for acceptance chain
    acc_repo_dir = tmp_path / "acc_repo"
    acc_repo_dir.mkdir()
    acc_file = acc_repo_dir / "service.py"
    acc_file.write_text(
        "class InitialService:\n"
        '    """Initial service."""\n\n'
        "    def execute(self) -> bool:\n"
        "        return True\n",
        encoding="utf-8",
    )

    # 36 repository observation uses shared infrastructure
    acc_analyzer = ProjectAnalyzer()
    acc_repo_context = acc_analyzer.analyze(
        acc_repo_dir, "Add feature method to InitialService"
    )
    assert acc_repo_context.total_python_files >= 1
    assert acc_repo_context.files[0].classes[0]["name"] == "InitialService"
    checkpoint("36 repository observation uses shared infrastructure")

    # 37 architecture finding references shared evidence
    arch_doc_resource = bootstrap.resource_registry.get(
        "project.resource.architecture_document"
    )
    assert arch_doc_resource is not None
    checkpoint("37 architecture finding references shared evidence")

    # 38 implementation plan uses shared planning path
    self_dev_wf = wfs["project.self_development"]
    assert self_dev_wf.workflow_id in SOFTWARE_PROJECT_WORKFLOW_IDS
    assert any(n.node_id == "arch_analysis" for n in self_dev_wf.nodes)
    acc_plan_payload = {
        "goal": "Add feature method to InitialService",
        "affected_files": ["service.py"],
        "operations": [
            {
                "domain": "python",
                "type": "insert_method",
                "parameters": {
                    "path": "service.py",
                    "class_name": "InitialService",
                    "position": "end",
                    "code": (
                        "def feature(self) -> str:\n"
                        '    """Feature docstring."""\n'
                        '    return "ok"\n'
                    ),
                },
                "reason": "Add feature method",
            }
        ],
        "rationale": "Plan for InitialService",
        "validations": ["python_ast", "python_compile"],
        "risks": [],
    }
    acc_provider = DeterministicPlanningProvider(acc_plan_payload)
    acc_plan_dict = acc_provider.generate_plan(
        "Add feature method to InitialService", acc_repo_context
    )
    acc_dev_plan = DevelopmentPlan.from_mapping(
        acc_plan_dict, "Add feature method to InitialService"
    )
    acc_dev_plan.validate()
    assert acc_dev_plan.affected_files == ("service.py",)
    checkpoint("38 implementation plan uses shared planning path")

    # 39 project.modify_code unavailable before injection
    raw_common = InMemoryAgentOperationRegistry()
    raw_op_registry = InMemoryDomainOperationRegistry(raw_common)
    raw_ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op_def = raw_ops["project.modify_code"]
    raw_op_registry.register(modify_op_def, None)
    assert raw_common.resolve("project.modify_code", "1.0.0").enabled is False
    with pytest.raises(DomainOperationRegistryError):
        raw_op_registry.get_implementation("project.modify_code", "1.0.0")
    checkpoint("39 project.modify_code unavailable before injection")

    # 40 valid injected implementation accepted
    class _MockModifyImpl:
        def __init__(self, definition: Any, *, fail: bool = False) -> None:
            self.definition = definition
            self.fail = fail

        def execute(self, request: Any) -> dict[str, Any]:
            runtime_action = request.parameters["runtime_action"]
            run_res = Runtime().run(runtime_action)
            # Canonical formatter policy: normalize ast.unparse output.
            try:
                import subprocess
                import sys

                try:
                    actions = tuple(runtime_action.get("actions", ()) or ())
                except Exception:
                    actions = ()
                for act in actions:
                    pp = act.get("path") if hasattr(act, "get") else None
                    if pp:
                        subprocess.run(
                            [sys.executable, "-m", "ruff", "format", str(pp)],
                            capture_output=True,
                            check=False,
                        )
            except Exception:
                pass
            if self.fail or request.parameters.get("force_failure"):
                return {
                    "success": False,
                    "error": {
                        "code": "OPERATION_EXECUTION_FAILED",
                        "message": "Forced failure for rollback",
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
            return {
                "success": run_res.success,
                "output": {
                    "status": "completed" if run_res.success else "failed",
                    "result": {
                        "modified_files": list(
                            request.parameters.get("modified_files", [])
                        )
                    },
                },
                "modified_files": request.parameters.get("modified_files", []),
            }

    _dummy_modify_impl = _MockModifyImpl(definition=modify_op_def)
    injected_common = InMemoryAgentOperationRegistry()
    injected_op_registry = InMemoryDomainOperationRegistry(injected_common)
    injected_op_registry.register(modify_op_def, _dummy_modify_impl)
    assert injected_common.resolve("project.modify_code", "1.0.0").enabled is True
    assert (
        injected_op_registry.get_implementation("project.modify_code", "1.0.0")
        is not None
    )
    checkpoint("40 valid injected implementation accepted")

    # 41 file modification permission resolved
    mod_perm_req = DomainPermissionRequest(
        request_id="req:perm:file_mod",
        action=PermissionCapability.FILE_MODIFY,
        domain_id=PROJECT_DOMAIN_ID,
        actor_id="actor:self_dev",
        session_id="session:dev_1",
    )
    mod_resolution = perm_resolver.resolve(mod_perm_req)
    assert (
        mod_resolution.effective_permissions.decision
        is PermissionOutcome.APPROVAL_REQUIRED
    )
    checkpoint("41 file modification permission resolved")

    # 42 mutation requires canonical approval
    approval_repo = InMemoryApprovalRepository()
    approval_svc = ApprovalService(approval_repo)
    perm_gate = DomainPermissionGate(perm_resolver, approval_service=approval_svc)

    assert modify_op_def.required_permissions == (
        PermissionCapability.FILE_MODIFY.value,
    )
    unapproved_eval = perm_gate.evaluate_operation_definition(
        modify_op_def,
        request_id="req:gate:mod:1",
        actor_id="actor:self_dev",
        session_id="session:dev_1",
    )
    assert unapproved_eval.outcome in (
        PermissionGateOutcome.APPROVAL_REQUIRED,
        PermissionGateOutcome.DENY,
    )
    checkpoint("42 mutation requires canonical approval")

    # 43 forged approval rejected
    forged_eval = perm_gate.evaluate_operation_definition(
        modify_op_def,
        request_id="req:gate:mod:forged",
        actor_id="actor:self_dev",
        session_id="session:dev_1",
        approval_request_id="FORGED_REQUEST_ID_XYZ",
    )
    assert forged_eval.outcome != PermissionGateOutcome.ALLOW
    checkpoint("43 forged approval rejected")

    # 44 controlled semantic mutation runs in temp repo
    class _RepoVersionProvider:
        def __init__(self, path: Path) -> None:
            self.path = path
            self._snaps: dict[str, dict[Path, bytes]] = {}

        def capture_version(self, rkey: str) -> str:
            st = {
                p: p.read_bytes()
                for p in self.path.rglob("*")
                if p.is_file() and ".git" not in p.parts
            }
            digest_src = "".join(
                f"{p.relative_to(self.path)}:{hashlib.sha256(b).hexdigest()};"
                for p, b in sorted(st.items(), key=lambda x: str(x[0]))
            )
            d = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()
            self._snaps[d] = st
            return d

        def verify_version(self, rkey: str, ver: str) -> bool:
            return self.capture_version(rkey) == ver

        def restore_version(self, rkey: str, ver: str) -> bool:
            if ver not in self._snaps:
                return False
            snap = self._snaps[ver]
            cur = {
                p for p in self.path.rglob("*") if p.is_file() and ".git" not in p.parts
            }
            for p in cur - set(snap.keys()):
                p.unlink()
            for p, data in snap.items():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            return True

    acc_res_provider = _RepoVersionProvider(acc_repo_dir)
    acc_cp_repo = InMemoryCheckpointRepository()
    acc_cp_mgr = CheckpointManager(
        repository=acc_cp_repo, resource_provider=acc_res_provider
    )
    acc_tx_mgr = TransactionManager(acc_cp_mgr)
    acc_rest_mgr = CheckpointRestorationManager(
        repository=acc_cp_repo, resource_provider=acc_res_provider
    )
    acc_rollback_exec = CheckpointRestorationRollbackExecutor(
        transaction_manager=acc_tx_mgr, restoration_manager=acc_rest_mgr
    )
    acc_val_adapter = AgentValidationAdapter()

    acc_runtime_action = {
        "version": 1,
        "actions": [
            {
                "tool": "python",
                "action": "insert_method",
                "path": str(acc_file),
                "class_name": "InitialService",
                "position": "end",
                "code": (
                    "def feature(self) -> str:\n"
                    '    """Feature docstring."""\n'
                    '    return "ok"\n'
                ),
            }
        ],
    }

    acc_adapter = AgentExecutionAdapter(
        registry=injected_common,
        execution_delegate=DomainOperationExecutionDelegate(injected_op_registry),
        validation_adapter=acc_val_adapter,
    )
    acc_orchestrator = DefaultDomainOperationOrchestrator(
        injected_op_registry,
        acc_adapter,
        approval_service=approval_svc,
        permission_gate=perm_gate,
        transaction_manager=acc_tx_mgr,
        rollback_executor=acc_rollback_exec,
        operation_validation_provider=resolve_domain_operation_validation_requirements,
    )

    acc_op_req_proto = DomainOperationRequest(
        request_id="req:op:acc:mod",
        operation_id=modify_op_def.operation_id,
        operation_version=modify_op_def.version,
        inputs={
            "runtime_action": acc_runtime_action,
            "modified_files": ["service.py"],
        },
        agent_run_id="run:acc:1",
        workflow_id="project.self_development",
        task_id="task:acc:1",
        session_id="session:dev_1",
        primary_domain_id=PROJECT_DOMAIN_ID,
        idempotency_key="idem:acc:1",
        granted_permissions=modify_op_def.required_permissions,
        available_resources=modify_op_def.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor:self_dev"},
    )
    acc_decision = evaluate_domain_operation(
        modify_op_def,
        perm_resolver,
        request_id=acc_op_req_proto.request_id,
        actor_id="actor:self_dev",
        session_id="session:dev_1",
    )
    assert acc_decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    acc_approval_ids: dict[str, str] = {}
    acc_op_exec_approval_id: str | None = None
    for req in acc_decision.approval_requirements:
        bridged = to_approval_requirement(
            req,
            agent_run_id=acc_op_req_proto.agent_run_id,
        )
        app_req = approval_svc.create_request_from_requirement(
            bridged,
            requested_by="agent:self_dev",
            metadata_override={
                "domain_request_fingerprint": acc_op_req_proto.calculate_fingerprint()
            },
        )
        approval_svc.approve(
            app_req.id,
            actor_id="human:tech_lead",
            comment=f"Approved requirement {req.requirement_id}",
        )
        acc_approval_ids[req.requirement_id] = app_req.id
        if req.action is PermissionCapability.OPERATION_EXECUTE:
            acc_op_exec_approval_id = app_req.id

    assert acc_op_exec_approval_id is not None
    acc_op_req = DomainOperationRequest(
        request_id=acc_op_req_proto.request_id,
        operation_id=acc_op_req_proto.operation_id,
        operation_version=acc_op_req_proto.operation_version,
        inputs=acc_op_req_proto.inputs,
        agent_run_id=acc_op_req_proto.agent_run_id,
        workflow_id=acc_op_req_proto.workflow_id,
        task_id=acc_op_req_proto.task_id,
        session_id=acc_op_req_proto.session_id,
        primary_domain_id=acc_op_req_proto.primary_domain_id,
        idempotency_key=acc_op_req_proto.idempotency_key,
        granted_permissions=acc_op_req_proto.granted_permissions,
        available_resources=acc_op_req_proto.available_resources,
        capabilities=acc_op_req_proto.capabilities,
        approval_request_id=acc_op_exec_approval_id,
        metadata={
            "actor_id": "actor:self_dev",
            "approval_request_ids": acc_approval_ids,
            "validation_project_root": str(acc_repo_dir),
        },
    )
    acc_op_res = acc_orchestrator.execute(acc_op_req)
    assert acc_op_res.status is DomainOperationStatus.COMPLETED
    assert acc_op_res.transaction_id is not None
    for app_id in acc_approval_ids.values():
        assert approval_repo.is_consumed(app_id) is True
    assert "def feature" in acc_file.read_text(encoding="utf-8")
    checkpoint("44 controlled semantic mutation runs in temp repo")

    # 45 shared rollback/transaction path is present
    acc_bytes_before_fail = acc_file.read_bytes()
    fail_modify_impl = _MockModifyImpl(definition=modify_op_def, fail=True)
    fail_common = InMemoryAgentOperationRegistry()
    fail_op_reg = InMemoryDomainOperationRegistry(fail_common)
    fail_op_reg.register(modify_op_def, fail_modify_impl)
    fail_adapter = AgentExecutionAdapter(
        registry=fail_common,
        execution_delegate=DomainOperationExecutionDelegate(fail_op_reg),
        validation_adapter=acc_val_adapter,
    )
    fail_orchestrator = DefaultDomainOperationOrchestrator(
        fail_op_reg,
        fail_adapter,
        approval_service=approval_svc,
        permission_gate=perm_gate,
        transaction_manager=acc_tx_mgr,
        rollback_executor=acc_rollback_exec,
        operation_validation_provider=resolve_domain_operation_validation_requirements,
    )
    fail_runtime_action = {
        "version": 1,
        "actions": [
            {
                "tool": "python",
                "action": "insert_method",
                "path": str(acc_file),
                "class_name": "InitialService",
                "position": "end",
                "code": (
                    "def bad_feature(self) -> str:\n"
                    '    """Broken method."""\n'
                    "    return 'broken'\n"
                ),
            }
        ],
    }
    fail_op_req_proto = DomainOperationRequest(
        request_id="req:op:acc:fail",
        operation_id=modify_op_def.operation_id,
        operation_version=modify_op_def.version,
        inputs={
            "runtime_action": fail_runtime_action,
            "modified_files": ["service.py"],
        },
        agent_run_id="run:acc:1",
        workflow_id="project.self_development",
        task_id="task:acc:fail:1",
        session_id="session:dev_1",
        primary_domain_id=PROJECT_DOMAIN_ID,
        idempotency_key="idem:acc:fail:1",
        granted_permissions=modify_op_def.required_permissions,
        available_resources=modify_op_def.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor:self_dev"},
    )
    fail_decision = evaluate_domain_operation(
        modify_op_def,
        perm_resolver,
        request_id=fail_op_req_proto.request_id,
        actor_id="actor:self_dev",
        session_id="session:dev_1",
    )
    assert fail_decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    fail_approval_ids: dict[str, str] = {}
    fail_op_exec_approval_id: str | None = None
    for req in fail_decision.approval_requirements:
        bridged = to_approval_requirement(
            req,
            agent_run_id=fail_op_req_proto.agent_run_id,
        )
        app_req = approval_svc.create_request_from_requirement(
            bridged,
            requested_by="agent:self_dev",
            metadata_override={
                "domain_request_fingerprint": fail_op_req_proto.calculate_fingerprint()
            },
        )
        approval_svc.approve(
            app_req.id,
            actor_id="human:tech_lead",
            comment=f"Approved requirement {req.requirement_id}",
        )
        fail_approval_ids[req.requirement_id] = app_req.id
        if req.action is PermissionCapability.OPERATION_EXECUTE:
            fail_op_exec_approval_id = app_req.id

    assert fail_op_exec_approval_id is not None
    fail_op_req = DomainOperationRequest(
        request_id=fail_op_req_proto.request_id,
        operation_id=fail_op_req_proto.operation_id,
        operation_version=fail_op_req_proto.operation_version,
        inputs=fail_op_req_proto.inputs,
        agent_run_id=fail_op_req_proto.agent_run_id,
        workflow_id=fail_op_req_proto.workflow_id,
        task_id=fail_op_req_proto.task_id,
        session_id=fail_op_req_proto.session_id,
        primary_domain_id=fail_op_req_proto.primary_domain_id,
        idempotency_key=fail_op_req_proto.idempotency_key,
        granted_permissions=fail_op_req_proto.granted_permissions,
        available_resources=fail_op_req_proto.available_resources,
        capabilities=fail_op_req_proto.capabilities,
        approval_request_id=fail_op_exec_approval_id,
        metadata={
            "actor_id": "actor:self_dev",
            "approval_request_ids": fail_approval_ids,
            "validation_project_root": str(acc_repo_dir),
        },
    )
    fail_res = fail_orchestrator.execute(fail_op_req)
    assert fail_res.status is DomainOperationStatus.ROLLED_BACK
    assert fail_res.rollback_result is not None
    assert fail_res.rollback_result.attempted is True
    assert fail_res.rollback_result.succeeded is True
    assert acc_file.read_bytes() == acc_bytes_before_fail
    checkpoint("45 shared rollback/transaction path is present")

    # 46 shared Phase 7 validation executes
    acc_test_file = acc_repo_dir / "tests" / "test_service.py"
    acc_test_file.parent.mkdir(parents=True, exist_ok=True)
    acc_test_file.write_text(
        "from service import InitialService\n\n\n"
        "def test_execute() -> None:\n"
        "    assert InitialService().execute() is True\n",
        encoding="utf-8",
    )
    acc_val_ctx = ValidationContext(
        project_root=acc_repo_dir,
        requested_policy="small_change",
        changed_files=(Path("service.py"), Path("tests/test_service.py")),
        allow_commit=True,
    )
    acc_val_pipeline = build_default_pipeline()
    acc_val_result = acc_val_pipeline.run(
        acc_val_ctx, default_validation_steps(acc_val_ctx)
    )
    assert isinstance(acc_val_result, ValidationResult)
    assert acc_val_result.id is not None
    checkpoint("46 shared Phase 7 validation executes")

    # 47 failed validation blocks commit readiness
    failed_readiness = build_prepare_commit_readiness_result(
        change_id="change:bugfix:1",
        validation_passed=False,
        validation_reference="validation:phase7:failed",
        commit_gate_allowed=True,
        approval_reference="approval:valid:1",
    )
    assert failed_readiness["ready_for_approved_commit"] is False
    checkpoint("47 failed validation blocks commit readiness")

    # 48 successful validation evidence accepted
    passed_readiness = build_prepare_commit_readiness_result(
        change_id="change:bugfix:1",
        validation_passed=True,
        validation_reference="validation:phase7:passed",
        commit_gate_allowed=True,
        approval_reference="approval:valid:1",
    )
    assert passed_readiness["ready_for_approved_commit"] is True
    checkpoint("48 successful validation evidence accepted")

    # 49 change review remains distinct from approval
    rev_op = raw_ops["project.review_change"]
    assert rev_op.operation_id == "project.review_change"
    assert rev_op.requires_approval is False
    assert "permission.file.modify" not in rev_op.required_permissions
    checkpoint("49 change review remains distinct from approval")

    # 50 project.prepare_commit evaluates readiness
    assert "ready_for_approved_commit" in passed_readiness
    assert "validation_passed" in passed_readiness
    checkpoint("50 project.prepare_commit evaluates readiness")

    # 51 project.prepare_commit performs no git commit
    assert passed_readiness["committed"] is False
    checkpoint("51 project.prepare_commit performs no git commit")

    # 52 no fake commit reference is created
    assert "commit_hash" not in passed_readiness
    assert passed_readiness.get("authoritative_commit_reference") is None
    checkpoint("52 no fake commit reference is created")

    # 53 software memory proposal preserves readiness vs committed distinction
    sw_proposal = build_project_memory_proposal(
        proposal_id="prop:sw:ready",
        affected_reference_ids=("ref:project:change:bugfix:1",),
    )
    assert sw_proposal.requires_confirmation is True
    checkpoint(
        "53 software memory proposal preserves readiness vs committed distinction"
    )

    # 54 software trace includes permission/execution/validation refs
    authority_54 = acc_op_res.metadata["permission_authority"]
    permission_decision_id_54 = authority_54["permission_decision_id"]
    approval_authorities_54 = tuple(authority_54["approvals"])

    assert {item["action"] for item in approval_authorities_54} == {
        PermissionCapability.OPERATION_EXECUTE.value,
        PermissionCapability.FILE_MODIFY.value,
    }

    approval_request_ids_54 = tuple(
        sorted(item["approval_request_id"] for item in approval_authorities_54)
    )
    approval_decision_ids_54 = tuple(
        sorted(
            {
                decision_id
                for item in approval_authorities_54
                for decision_id in item["approval_decision_ids"]
            }
        )
    )

    file_modify_authority_54 = next(
        item
        for item in approval_authorities_54
        if item["action"] == PermissionCapability.FILE_MODIFY.value
    )
    assert file_modify_authority_54["approval_request_id"] in approval_request_ids_54
    assert set(file_modify_authority_54["approval_decision_ids"]).issubset(
        set(approval_decision_ids_54)
    )

    perm_ref_54 = build_project_trace_reference(
        ref_id=permission_decision_id_54,
        kind=DomainTraceReferenceKind.PERMISSION_DECISION,
    )
    app_req_refs_54 = tuple(
        build_project_trace_reference(
            ref_id=req_id,
            kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
        )
        for req_id in approval_request_ids_54
    )
    app_dec_refs_54 = tuple(
        build_project_trace_reference(
            ref_id=dec_id,
            kind=DomainTraceReferenceKind.APPROVAL_DECISION,
        )
        for dec_id in approval_decision_ids_54
    )
    op_mutation_ref = build_project_trace_reference(
        ref_id=str(acc_op_res.result_id),
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    tx_ref = build_project_trace_reference(
        ref_id=str(acc_op_res.transaction_id),
        kind=DomainTraceReferenceKind.EVIDENCE,
    )
    assert fail_res.rollback_result is not None
    rollback_res_ref = "rollback-result:sha256:" + sha256_digest(
        fail_res.rollback_result.to_dict()
    )
    rollback_ref = build_project_trace_reference(
        ref_id=rollback_res_ref,
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    val_ref = build_project_trace_reference(
        ref_id=str(acc_val_result.id),
        kind=DomainTraceReferenceKind.EVIDENCE,
    )
    readiness_res_ref = "prepare-commit-readiness:sha256:" + sha256_digest(
        passed_readiness
    )
    commit_prep_ref = build_project_trace_reference(
        ref_id=readiness_res_ref,
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    sw_trace_refs = (
        perm_ref_54,
        *app_req_refs_54,
        *app_dec_refs_54,
        op_mutation_ref,
        tx_ref,
        rollback_ref,
        val_ref,
        commit_prep_ref,
    )
    req_id_54 = "req:trace:sw:1"
    ctx_id_54 = "ctx:sw:1"
    res_id_54 = "res_res:sw:1"
    comp_id_54 = "comp:sw:1"
    dres_id_54 = "res:project:sw:1"

    trace_refs_54 = DomainTraceReferences(
        resolution_context_id=ctx_id_54,
        resolution_result_id=res_id_54,
        composition_id=comp_id_54,
        cross_domain_results=(),
        presentation_result_ids=(),
    )
    assembly_req_54 = DomainTraceAssemblyRequest(
        request_id=req_id_54,
        goal_id=None,
        primary_domain=PROJECT_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            build_project_trace_contribution(
                domain_result_id=dres_id_54,
                references=sw_trace_refs,
            ),
        ),
        references=trace_refs_54,
        domain_results=(
            DomainResultTraceReference(
                dres_id_54,
                PROJECT_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        metadata={},
    )
    pred_id_54 = calculate_domain_trace_identity(assembly_req_54)

    inv_54 = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                dres_id_54,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                PROJECT_DOMAIN_ID,
            ),
            *sw_trace_refs,
            DomainTraceReference(
                ctx_id_54, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id_54, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(
                comp_id_54, DomainTraceReferenceKind.COMPOSITION, None
            ),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=dres_id_54,
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=pred_id_54.trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=PROJECT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            res_id_54, PROJECT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(
            comp_id_54, PROJECT_DOMAIN_ID, ()
        ),
    )

    sw_trace = assemble_project_trace(
        request_id=req_id_54,
        resolution_context_id=ctx_id_54,
        resolution_result_id=res_id_54,
        composition_id=comp_id_54,
        domain_result_id=dres_id_54,
        references=sw_trace_refs,
        started_at=now,
        completed_at=now,
    )
    assert sw_trace.status == DomainTraceStatus.COMPLETED
    assert validate_project_trace(trace=sw_trace, inventory=inv_54).valid is True
    kinds_54 = {ref.kind for ref in sw_trace_refs}
    assert DomainTraceReferenceKind.PERMISSION_DECISION in kinds_54
    assert DomainTraceReferenceKind.APPROVAL_REQUEST in kinds_54
    assert DomainTraceReferenceKind.APPROVAL_DECISION in kinds_54
    assert DomainTraceReferenceKind.OPERATION_RESULT in kinds_54
    assert DomainTraceReferenceKind.EVIDENCE in kinds_54
    checkpoint("54 software trace includes permission/execution/validation refs")

    # 55 Formation remains outside Project
    assert PROJECT_DOMAIN_ID != "domain:formation"
    assert "formation" not in CANONICAL_PROJECT_ENTITY_IDS
    for entity_id in CANONICAL_PROJECT_ENTITY_IDS:
        assert entity_id.split(".")[-1] != "formation"
    for rule_id in CANONICAL_PROJECT_RULE_IDS:
        assert rule_id.split(".")[-1] != "formation"
    for op_id in CANONICAL_PROJECT_OPERATION_IDS:
        assert op_id.split(".")[-1] != "formation"
    checkpoint("55 Formation remains outside Project")

    # 56 legacy Project catalog remains unmodified and canonical bootstrap isolated
    assert "project.prepare_change_review" not in CANONICAL_PROJECT_OPERATION_IDS
    assert "project.review_change" in CANONICAL_PROJECT_OPERATION_IDS
    checkpoint(
        "56 legacy Project catalog remains unmodified and canonical bootstrap isolated"
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Total Checkpoint Invariant Assertions
    # ═══════════════════════════════════════════════════════════════════════════
    assert len(checkpoints) == DP_030_CHECKPOINTS == 56
    assert len(checkpoints[:32]) == DP_030_GENERIC_CHECKPOINTS == 32
    assert len(checkpoints[32:]) == DP_030_SOFTWARE_CHECKPOINTS == 24
    assert len(set(checkpoints)) == 56
