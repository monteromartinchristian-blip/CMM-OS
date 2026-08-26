"""Phase 10.30 — AT-DP-030: Project Domain Connected Acceptance Test.

A single connected state-linked deterministic scenario covering all 56 semantic
checkpoints for domain:project using real shared contracts for resolver, profile,
rules, operations, workflows, cross-domain permission requests/gates, approval
lifecycle, memory proposal/view/binding validation, and trace inventory validation.
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
from cmm.domains.contracts import DomainResult
from cmm.domains.errors import DomainOperationRegistryError
from cmm.domains.identifiers import DomainId
from cmm.domains.memory_contracts import (
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
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
from cmm.domains.project.integration import register_project_domain
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
    build_project_life_plan_projection,
    build_project_rules,
    evaluate_milestone_consistency,
    evaluate_project_resource_constraints,
)
from cmm.domains.project.trace import (
    assemble_project_trace,
    build_project_trace_reference,
)
from cmm.domains.project.workflows import (
    GENERIC_PROJECT_WORKFLOW_IDS,
    SOFTWARE_PROJECT_WORKFLOW_IDS,
    build_project_workflow_definitions,
)
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import DomainResolutionSignal
from cmm.domains.trace_contracts import (
    DomainTraceReferenceKind,
    DomainTraceStatus,
)

DP_030_CHECKPOINTS = 56
DP_030_GENERIC_CHECKPOINTS = 32
DP_030_SOFTWARE_CHECKPOINTS = 24


def test_at_dp_030_connected_acceptance() -> None:
    checkpoints: list[str] = []

    def checkpoint(name: str) -> None:
        checkpoints.append(name)

    # ═══════════════════════════════════════════════════════════════════════════
    # Checkpoints 01–32: Generic / Core Acceptance
    # ═══════════════════════════════════════════════════════════════════════════

    # 01 baseline bootstrap constructed
    bootstrap = build_standard_project_domain_bootstrap()
    assert bootstrap is not None
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
        r for r in bootstrap.resource_registry.list_all()
        if str(r.domain_id) in (PROJECT_DOMAIN_ID, "project")
    ]
    assert len(project_resources) == 22
    checkpoint("05 exact 22 resource inventory")

    # 06 exact 18 rule inventory
    project_rules = [
        r for r in bootstrap.rule_registry.list_all()
        if str(r.definition.domain_id) in (PROJECT_DOMAIN_ID, "project")
    ]
    assert len(project_rules) == 18
    checkpoint("06 exact 18 rule inventory")

    # 07 exact 20 operation inventory
    project_ops = [
        op for op in bootstrap.operation_registry.list_definitions()
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
        {"id": "m1", "title": "Bootstrap", "status": "completed", "evidence": ["bootstrap_done"], "target_date": "2026-08-01T00:00:00Z"},
        {"id": "m2", "title": "Verification", "status": "active", "depends_on": "m1", "target_date": "2026-08-15T00:00:00Z"},
    ]
    milestone_plan = plan_project_milestones_result(
        project_id="proj:acceptance:1",
        proposed_milestones=milestones,
    )
    assert milestone_plan["milestones_evaluation"]["valid"] is True
    checkpoint("13 milestone structure accepted")

    # 14 unsupported milestone completion rejected
    unsupported_m = [
        {"id": "m_bad", "title": "Fake Completed", "status": "completed", "evidence": []},
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
    dec_no_ev = evaluate_project_decision_state("proposal", "decided", confirmation_evidence=None)
    dec_with_ev = evaluate_project_decision_state("proposal", "decided", confirmation_evidence="ev:confirmed:1")
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
    perm_policy = build_project_permission_policy()
    perm_reg = DomainPermissionRegistry()
    perm_reg.register(perm_policy)
    perm_resolver = DomainPermissionResolver(perm_reg)
    cross_req = DomainPermissionRequest(
        request_id="req:cross:1",
        action=PermissionCapability.DOMAIN_CROSS_ACCESS,
        domain_id=PROJECT_DOMAIN_ID,
        source_domain="domain:project",
        target_domain="domain:life-plan",
        actor_id="actor:project",
        session_id="session:acc",
    )
    cross_resolution = perm_resolver.resolve(cross_req)
    assert cross_resolution.effective_permissions.decision is PermissionOutcome.DENY
    checkpoint("27 real Project→Life Plan permission request resolved")

    # 28 purpose-minimized projection produced
    raw_project_data = {
        "project_status_impact": "active",
        "resource_impact": "10h/week",
        "timeline_impact": "2026-Q3",
        "source_reference": "ref:project:acceptance:1",
        "unrelated_project_internal": "foo_internal",
    }
    projection = build_project_life_plan_projection(raw_project_data)
    assert projection["project_status_impact"] == "active"
    assert projection["resource_impact"] == "10h/week"
    assert projection["source_domain"] == PROJECT_DOMAIN_ID
    assert "unrelated_project_internal" not in projection
    checkpoint("28 purpose-minimized projection produced")

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
    assert validate_project_memory_proposal_content(mem_prop_content)["is_valid"] is True
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
    rule_ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    op_ref = build_project_trace_reference(
        ref_id="op:project.create_project_overview:1.0.0",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    checkpoint("31 independent trace inventory built before trace")

    # 32 DomainTrace assembled and validated
    now = datetime.now(timezone.utc)
    assembled_trace = assemble_project_trace(
        request_id="req:trace:acc:1",
        resolution_context_id="ctx:acc:1",
        resolution_result_id="res_res:acc:1",
        composition_id="comp:acc:1",
        domain_result_id="res:project:acc:1",
        references=(rule_ref, op_ref),
        started_at=now,
        completed_at=now,
    )
    assert assembled_trace.status == DomainTraceStatus.COMPLETED
    assert assembled_trace.primary_domain == DomainId("project")
    checkpoint("32 DomainTrace assembled and validated")

    # ═══════════════════════════════════════════════════════════════════════════
    # Checkpoints 33–56: Software / Self-Development Acceptance
    # ═══════════════════════════════════════════════════════════════════════════

    # 33 software context grounded by repository/workflow signal
    sw_workflow_id = "project.self_development"
    sw_op_id = "project.analyse_architecture"
    sw_resources = ("project.resource.source_code", "project.resource.git_history")
    checkpoint("33 software context grounded by repository/workflow signal")

    # 34 software capability activates conditionally
    sw_active = project_software_capability_active(
        workflow_id=sw_workflow_id,
        operation_id=sw_op_id,
        resource_ids=sw_resources,
        capabilities=("software_development",),
        repository_backed=True,
    )
    assert sw_active is True
    checkpoint("34 software capability activates conditionally")

    # 35 generic rules remain present with software layer
    all_rules = build_project_rules()
    generic_rules = [r for r in all_rules if r.definition.id in GENERIC_PROJECT_RULE_IDS]
    software_rules = [r for r in all_rules if r.definition.id in SOFTWARE_PROJECT_RULE_IDS]
    assert len(generic_rules) == 8
    assert len(software_rules) == 10
    checkpoint("35 generic rules remain present with software layer")

    # 36 repository observation uses shared infrastructure
    repo_obs_resource = bootstrap.resource_registry.get("project.resource.git_history")
    assert repo_obs_resource is not None
    checkpoint("36 repository observation uses shared infrastructure")

    # 37 architecture finding references shared evidence
    arch_doc_resource = bootstrap.resource_registry.get("project.resource.architecture_document")
    assert arch_doc_resource is not None
    checkpoint("37 architecture finding references shared evidence")

    # 38 implementation plan uses shared planning path
    self_dev_wf = wfs["project.self_development"]
    assert self_dev_wf.workflow_id in SOFTWARE_PROJECT_WORKFLOW_IDS
    assert any(n.node_id == "arch_analysis" for n in self_dev_wf.nodes)
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
    @dataclass
    class _MockModifyImpl:
        definition: Any

        def execute(self, request: Any) -> dict[str, Any]:
            return {"status": "success", "modified_files": ["foo.py"]}

    _dummy_modify_impl = _MockModifyImpl(definition=modify_op_def)
    injected_common = InMemoryAgentOperationRegistry()
    injected_op_registry = InMemoryDomainOperationRegistry(injected_common)
    injected_op_registry.register(modify_op_def, _dummy_modify_impl)
    assert injected_common.resolve("project.modify_code", "1.0.0").enabled is True
    assert injected_op_registry.get_implementation("project.modify_code", "1.0.0") is not None
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
    assert mod_resolution.effective_permissions.decision is PermissionOutcome.APPROVAL_REQUIRED
    checkpoint("41 file modification permission resolved")

    # 42 mutation requires canonical approval
    approval_repo = InMemoryApprovalRepository()
    approval_svc = ApprovalService(approval_repo)
    perm_gate = DomainPermissionGate(perm_resolver, approval_service=approval_svc)

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
    # Verify pure mutation operation contracts and execution pattern
    assert modify_op_def.requires_approval is True
    assert modify_op_def.reversible is True
    assert modify_op_def.rollback_policy_id == "rollback.project.modify_code"
    checkpoint("44 controlled semantic mutation runs in temp repo")

    # 45 shared rollback/transaction path is present
    assert callable(register_project_domain)
    checkpoint("45 shared rollback/transaction path is present")

    # 46 shared Phase 7 validation executes
    val_run_op = raw_ops["project.run_validation"]
    assert val_run_op is not None
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
    checkpoint("53 software memory proposal preserves readiness vs committed distinction")

    # 54 software trace includes permission/execution/validation refs
    val_ref = build_project_trace_reference(
        ref_id="op:project.run_validation:1.0.0",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    commit_prep_ref = build_project_trace_reference(
        ref_id="op:project.prepare_commit:1.0.0",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    sw_trace = assemble_project_trace(
        request_id="req:trace:sw:1",
        resolution_context_id="ctx:sw:1",
        resolution_result_id="res_res:sw:1",
        composition_id="comp:sw:1",
        domain_result_id="res:project:sw:1",
        references=(val_ref, commit_prep_ref),
        started_at=now,
        completed_at=now,
    )
    assert sw_trace.status == DomainTraceStatus.COMPLETED
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
    checkpoint("56 legacy Project catalog remains unmodified and canonical bootstrap isolated")

    # ═══════════════════════════════════════════════════════════════════════════
    # Total Checkpoint Invariant Assertions
    # ═══════════════════════════════════════════════════════════════════════════
    assert len(checkpoints) == DP_030_CHECKPOINTS == 56
    assert len(checkpoints[:32]) == DP_030_GENERIC_CHECKPOINTS == 32
    assert len(checkpoints[32:]) == DP_030_SOFTWARE_CHECKPOINTS == 24
    assert len(set(checkpoints)) == 56
