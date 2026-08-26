"""Phase 10.29 — Life Plan Domain AT-DP-029 Acceptance Scenario.

A single connected state-linked deterministic scenario covering all 45 semantic
checkpoints for domain:life-plan using real shared contracts for resolver, profile,
rules, operations, workflows, cross-domain permission requests/gates, approval
lifecycle, memory proposal/view/binding validation, and trace inventory validation.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainResult
from cmm.domains.general.permissions import build_general_permission_policy
from cmm.domains.health.permissions import build_health_permission_policy
from cmm.domains.identifiers import DomainId
from cmm.domains.life_plan import (
    LIFE_PLAN_DOMAIN_ID,
    LIFE_PLAN_ENTITY_IDS,
    LIFE_PLAN_OPERATION_IDS,
    LIFE_PLAN_PROFILE_ID,
    LIFE_PLAN_RESOURCE_IDS,
    LIFE_PLAN_RULE_IDS,
    LIFE_PLAN_WORKFLOW_IDS,
    assemble_life_plan_trace,
    build_life_plan_domain_definition,
    build_life_plan_memory_binding,
    build_life_plan_memory_proposal,
    build_life_plan_memory_view,
    build_life_plan_memory_view_request,
    build_life_plan_operation_definitions,
    build_life_plan_permission_policy,
    build_life_plan_trace_reference,
    build_life_plan_workflow_definitions,
    build_standard_life_plan_domain_bootstrap,
    compare_scenarios_result,
    create_milestones_result,
    evaluate_alternative_route,
    evaluate_cross_domain_impact,
    evaluate_decision_status,
    evaluate_feasibility_result,
    evaluate_goal_dependencies,
    evaluate_long_term_temporal,
    evaluate_plan_drift,
    evaluate_resource_constraints,
    evaluate_scenario_consistency,
    execute_cross_domain_impact_workflow,
    generate_periodic_review_result,
    identify_risks_result,
    present_life_plan_result,
    validate_life_plan_memory_binding,
    validate_life_plan_trace,
)
from cmm.domains.life_plan.trace import (
    build_life_plan_trace_contribution,
)
from cmm.domains.memory_contracts import (
    DomainMemoryApprovalDecisionSnapshot,
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionRequest,
)
from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateOutcome,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import DomainResolutionSignal
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTrace,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceStatus,
)
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowNodeType

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


class DeterministicIdFactory:
    def __init__(self) -> None:
        self._counter = 0

    def __call__(self) -> str:
        self._counter += 1
        return f"at-dp029-id-{self._counter}"


def test_at_dp029_connected_acceptance_scenario() -> None:
    """Execute the full 45-checkpoint connected AT-DP-029 acceptance scenario."""
    id_factory = DeterministicIdFactory()
    state: dict[str, Any] = {}

    # 01 resolve domain:life-plan through canonical resolver
    bootstrap = build_standard_life_plan_domain_bootstrap()
    resolution_signals = (
        DomainResolutionSignal(
            kind="intent",
            source="user",
            value="long term career strategy and relocation plan",
            domain_ids=("domain:life-plan",),
        ),
    )
    resolution_context = DomainResolutionContextBuilder(
        id_factory=id_factory, clock=lambda: NOW
    ).build(
        registry_snapshot=bootstrap.domain_registry.snapshot(),
        user_input="Help me structure a 5-year life plan for relocation and career growth.",
        authorized_domains=("domain:general", LIFE_PLAN_DOMAIN_ID),
        signals=resolution_signals,
    )
    resolver = DefaultDomainResolver(
        scoring_policy=bootstrap.resolver.scoring_policy,
        fallback_domain=bootstrap.resolver.fallback_domain,
        id_factory=id_factory,
        clock=lambda: NOW,
    )
    resolution = resolver.resolve(resolution_context)
    composition = DefaultDomainComposer(
        id_factory=id_factory, clock=lambda: NOW
    ).compose(resolution, (build_life_plan_domain_definition(),))
    domain_def = bootstrap.domain_registry.get(LIFE_PLAN_DOMAIN_ID)

    assert domain_def is not None
    assert str(domain_def.id) == "domain:life-plan"
    assert str(resolution.primary_domain) == LIFE_PLAN_DOMAIN_ID
    assert str(composition.primary_domain) == LIFE_PLAN_DOMAIN_ID
    state["01_resolved_domain"] = domain_def

    # 02 load/reuse LifePlanProfile
    profile = bootstrap.profile_registry.get_by_domain(DomainId("life-plan"))
    assert profile is not None
    assert profile.id == LIFE_PLAN_PROFILE_ID
    assert profile.profile_name == "LifePlanProfile"
    state["02_profile"] = profile

    # 03 verify exact 13/12/8/10/7 catalog
    assert len(LIFE_PLAN_ENTITY_IDS) == 13
    assert len(LIFE_PLAN_RESOURCE_IDS) == 12
    assert len(LIFE_PLAN_RULE_IDS) == 8
    assert len(LIFE_PLAN_OPERATION_IDS) == 10
    assert len(LIFE_PLAN_WORKFLOW_IDS) == 7
    state["03_catalog_verified"] = True

    # 04 create explicit life goal
    life_goal = {
        "goal_id": "goal-relocation-001",
        "title": "Relocate to Europe & Transition to Technical Lead",
        "category": "career_and_lifestyle",
        "horizon_years": 5,
    }
    state["04_life_goal"] = life_goal

    # 05 create milestones
    milestones_op = create_milestones_result(
        milestones=[
            {
                "id": "ms-01",
                "title": "Obtain C1 Language Certification",
                "target_date": "2027-06-01",
            },
            {
                "id": "ms-02",
                "title": "Secure Offer in Target Country",
                "target_date": "2028-03-01",
                "depends_on": "ms-01",
            },
            {
                "id": "ms-03",
                "title": "Complete Relocation",
                "target_date": "2028-09-01",
                "depends_on": "ms-02",
            },
        ],
    )
    assert milestones_op["status"] == "created"
    assert len(milestones_op["milestones"]) == 3
    state["05_milestones"] = milestones_op["milestones"]

    # 06 evaluate decision status idea
    dec_idea = evaluate_decision_status("idea", "preference")
    assert dec_idea["allowed"] is True
    state["06_dec_idea"] = dec_idea

    # 07 evaluate decision status preference
    dec_pref = evaluate_decision_status("preference", "preference")
    assert dec_pref["allowed"] is True
    state["07_dec_pref"] = dec_pref

    # 08 deny unconfirmed preference to decision
    unconf_dec = evaluate_decision_status("preference", "decision")
    assert unconf_dec["allowed"] is False
    assert unconf_dec["requires_confirmation"] is True
    state["08_unconfirmed_preference_denied"] = True

    # 09 confirm decision with evidence
    conf_dec = evaluate_decision_status(
        "preference",
        "decision",
        confirmation_evidence={"confirmed_by_user": True, "date": "2026-08-26"},
    )
    assert conf_dec["allowed"] is True
    state["09_confirmed_decision"] = conf_dec

    # 10 deny unconfirmed decision to commitment
    unconf_comm = evaluate_decision_status("decision", "commitment")
    assert unconf_comm["allowed"] is False
    assert unconf_comm["requires_confirmation"] is True
    state["10_unconfirmed_commitment_denied"] = True

    # 11 confirm commitment with evidence
    conf_comm = evaluate_decision_status(
        "decision",
        "commitment",
        confirmation_evidence={"signed_agreement": True, "deposit_paid": True},
    )
    assert conf_comm["allowed"] is True
    state["11_confirmed_commitment"] = conf_comm

    # 12 deny closed decision reopening without new evidence
    reopen_fail = evaluate_decision_status(
        "decision",
        "idea",
        is_closed=True,
        has_new_evidence=False,
    )
    assert reopen_fail["allowed"] is False
    state["12_closed_decision_reopen_denied"] = True

    # 13 reopen closed decision with new evidence
    reopen_ok = evaluate_decision_status(
        "decision",
        "idea",
        is_closed=True,
        has_new_evidence=True,
        new_evidence="Remote policy changed corporate-wide",
    )
    assert reopen_ok["allowed"] is True
    assert reopen_ok["reopened"] is True
    state["13_closed_decision_reopened"] = True

    # 14 create scenario A
    scenario_a = {
        "scenario_id": "scen-berlin",
        "title": "Relocate to Berlin",
        "assumptions": {"visa_stream": "EU Blue Card", "cost_index": 1.2},
    }
    state["14_scenario_a"] = scenario_a

    # 15 create scenario B
    scenario_b = {
        "scenario_id": "scen-amsterdam",
        "title": "Relocate to Amsterdam",
        "assumptions": {"visa_stream": "Highly Skilled Migrant", "cost_index": 1.4},
    }
    state["15_scenario_b"] = scenario_b

    # 16 evaluate scenario consistency
    consist_a = evaluate_scenario_consistency(
        scenario_id="scen-berlin",
        assumptions={"visa_stream": "EU Blue Card"},
        milestones=milestones_op["milestones"],
    )
    assert consist_a["consistent"] is True
    assert consist_a["is_decision"] is False
    assert consist_a["is_commitment"] is False
    state["16_scenario_consistency"] = consist_a

    # 17 compare scenarios operation
    comp_scens = compare_scenarios_result(
        scenarios=[scenario_a, scenario_b],
    )
    assert comp_scens["status"] == "completed"
    assert comp_scens["is_decision"] is False
    assert comp_scens["is_commitment"] is False
    state["17_compared_scenarios"] = comp_scens

    # 18 evaluate alternative route
    alt_route = evaluate_alternative_route(
        primary_goal_id=life_goal["goal_id"],
        alternative_route_id="route-remote-fallback",
        route_type="contingency",
        rationale="Retain domestic role if visa processing exceeds 12 months",
    )
    assert alt_route["status"] == "active_alternative"
    assert alt_route["primary_goal_abandoned"] is False
    assert alt_route["is_failure"] is False
    state["18_alternative_route"] = alt_route

    # 19 evaluate goal dependencies clean
    deps_clean = evaluate_goal_dependencies(
        dependencies={
            "goal-lang": [],
            "goal-offer": ["goal-lang"],
            "goal-reloc": ["goal-offer"],
        }
    )
    assert deps_clean["valid"] is True
    assert deps_clean["has_cycles"] is False
    state["19_deps_clean"] = deps_clean

    # 20 evaluate goal dependencies cycle detection
    deps_cycle = evaluate_goal_dependencies(
        dependencies={"goal-a": ["goal-b"], "goal-b": ["goal-c"], "goal-c": ["goal-a"]}
    )
    assert deps_cycle["valid"] is False
    assert deps_cycle["has_cycles"] is True
    state["20_deps_cycle"] = deps_cycle

    # 21 evaluate goal dependencies hard vs soft
    deps_soft = evaluate_goal_dependencies(
        dependencies={"goal-reloc": ["goal-offer"]},
        soft_dependencies={"goal-reloc": ["goal-friendship-network"]},
    )
    assert deps_soft["valid"] is True
    assert "goal-reloc" in deps_soft["prerequisites"]
    assert "goal-reloc" in deps_soft["soft_dependencies"]
    state["21_deps_soft"] = deps_soft

    # 22 evaluate resource constraints time
    res_time = evaluate_resource_constraints(
        time={"available_hours_per_week": 15.0, "required_hours_per_week": 10.0},
        money={"available_funds": 20000.0, "required_funds": 15000.0},
        energy={"current_energy_level": "moderate", "minimum_required": "moderate"},
        available_capacity={"slots": 3, "required_slots": 1},
    )
    assert res_time["status"] == "feasible"
    assert res_time["feasible"] is True
    state["22_resource_time"] = res_time

    # 23 evaluate resource constraints money
    res_money_deficit = evaluate_resource_constraints(
        time={"available_hours_per_week": 15.0, "required_hours_per_week": 10.0},
        money={"available_funds": 5000.0, "required_funds": 15000.0},
        energy={"current_energy_level": "moderate", "minimum_required": "moderate"},
        available_capacity={"slots": 3, "required_slots": 1},
    )
    assert res_money_deficit["status"] == "constrained"
    assert "money_deficit" in res_money_deficit["blocking_constraints"]
    state["23_resource_money_deficit"] = res_money_deficit

    # 24 evaluate resource constraints energy
    res_energy = evaluate_resource_constraints(
        time={"available_hours_per_week": 15.0, "required_hours_per_week": 10.0},
        money={"available_funds": 20000.0, "required_funds": 15000.0},
        energy={"current_energy_level": "exhausted", "minimum_required": "high"},
        available_capacity={"slots": 3, "required_slots": 1},
    )
    assert res_energy["status"] == "constrained"
    assert "energy_deficit" in res_energy["blocking_constraints"]
    state["24_resource_energy"] = res_energy

    # 25 evaluate resource constraints capacity
    res_cap = evaluate_resource_constraints(
        time={"available_hours_per_week": 15.0, "required_hours_per_week": 10.0},
        money={"available_funds": 20000.0, "required_funds": 15000.0},
        energy={"current_energy_level": "moderate", "minimum_required": "moderate"},
        available_capacity={"slots": 1, "required_slots": 2},
    )
    assert res_cap["status"] == "constrained"
    assert "capacity_deficit" in res_cap["blocking_constraints"]
    state["25_resource_capacity"] = res_cap

    # 26 reject NaN, Inf, booleans in resource constraints
    res_nan = evaluate_resource_constraints(
        time={"available_hours_per_week": float("nan"), "required_hours_per_week": 10.0}
    )
    assert res_nan["status"] == "invalid_evidence"
    res_bool = evaluate_resource_constraints(
        time={"available_hours_per_week": True, "required_hours_per_week": 10.0}
    )
    assert res_bool["status"] == "invalid_evidence"
    state["26_nan_bool_rejected"] = True

    # 27 preserve missing resource as unknown
    res_missing = evaluate_resource_constraints(time={"required_hours_per_week": 10.0})
    assert res_missing["status"] == "unknown"
    assert res_missing["feasible"] is None
    state["27_missing_unknown"] = True

    # 28 evaluate long term temporal valid
    temp_valid = evaluate_long_term_temporal(milestones=milestones_op["milestones"])
    assert temp_valid["valid"] is True
    assert temp_valid["ordering_valid"] is True
    state["28_temporal_valid"] = temp_valid

    # 29 detect temporal ordering conflict
    temp_conflict = evaluate_long_term_temporal(
        milestones=[
            {"id": "m1", "target_date": "2029-01-01"},
            {"id": "m2", "target_date": "2027-01-01", "depends_on": "m1"},
        ]
    )
    assert temp_conflict["valid"] is False
    assert len(temp_conflict["ordering_conflicts"]) > 0
    state["29_temporal_conflict"] = temp_conflict

    # 30 preserve uncertain distant milestones
    temp_uncertain = evaluate_long_term_temporal(
        milestones=[
            {"id": "m_distant_future", "title": "Buy home abroad in 2035"},
        ]
    )
    assert temp_uncertain["valid"] is True
    assert "m_distant_future" in temp_uncertain["uncertain_milestones"]
    state["30_uncertain_milestones_preserved"] = True

    # ── Permission & Approval Shared Setup ──────────────────────────────────────
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_life_plan_permission_policy())
    perm_registry.register(build_general_permission_policy())
    health_policy = dataclasses.replace(
        build_health_permission_policy(),
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:life-plan",),
        allowed_capabilities=(
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            PermissionCapability.RESOURCE_READ,
        ),
        allowed_resource_kinds=("resource.health_constraints",),
        allowed_sensitivity_levels=("restricted",),
    )
    perm_registry.register(health_policy)
    approval_service = ApprovalService(InMemoryApprovalRepository())
    permission_resolver = DomainPermissionResolver(perm_registry)
    gate = DomainPermissionGate(
        permission_resolver, approval_service, clock=lambda: NOW
    )

    # 31 request cross-domain health contribution
    cross_request = CrossDomainPermissionRequest(
        request_id=id_factory(),
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health limitation on relocation climate",
        actor_id="actor-lp-user",
        session_id="sess-lp-user",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )
    state["31_cross_request"] = cross_request

    # 32 gate evaluate cross-domain approval required
    pending_gate = gate.evaluate_cross_domain(cross_request)
    assert pending_gate.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    state["32_pending_gate"] = pending_gate

    # 33 approve cross-domain via approval service
    req_item = PermissionApprovalRequirement.from_dict(
        pending_gate.approval_requirements[0]
    )
    cross_approval = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id=id_factory()),
        requested_by="physician-review",
    )
    approval_service.approve(cross_approval.id, "user-or-physician")
    cross_decision = approval_service.repository.list_decisions(cross_approval.id)[0]
    assert cross_decision.id is not None
    state["33_cross_approved"] = cross_decision

    # 34 consume cross-domain gate approval
    consumed_gate = gate.evaluate_cross_domain(
        cross_request, approval_request_id=cross_approval.id
    )
    assert consumed_gate.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert consumed_gate.allowed is True
    assert consumed_gate.decision_id is not None
    state["34_consumed_gate"] = consumed_gate

    # 35 apply authorized purpose-minimized health contribution
    cross_eval_approval = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id=id_factory()),
        requested_by="physician-review",
    )
    approval_service.approve(cross_eval_approval.id, "user-or-physician")

    health_raw_projection = {
        "constraint_id": "hc-climate-01",
        "status": "active",
        "activity_limits": ["avoid_high_humidity_locations"],
        "source_reference": "health.profile.hp01",
        "full_clinical_history": ["asthma_records_2020"],
        "medication_list": ["inhaler_daily"],
    }
    # Clinical dossier stripped before passing to evaluator
    health_sanitized = {
        "constraint_id": "hc-climate-01",
        "status": "active",
        "activity_limits": ["avoid_high_humidity_locations"],
        "source_reference": "health.profile.hp01",
    }
    hc_eval = evaluate_cross_domain_impact(
        health_sanitized,
        permission_request=cross_request,
        permission_gate=gate,
        approval_request_id=cross_eval_approval.id,
        is_current=True,
    )
    assert hc_eval["applied"] is True
    assert hc_eval["authorization_verified"] is True
    assert "activity_limits" in hc_eval["applied_fields"]
    state["35_authorized_health_impact"] = hc_eval

    # 36 deny unauthorized raw medical dossier
    dossier_eval = evaluate_cross_domain_impact(
        health_raw_projection,
        is_authorized=True,
        is_current=True,
    )
    assert dossier_eval["applied"] is False
    assert dossier_eval["reason"] == "rejected_unauthorized_dossier"
    state["36_raw_dossier_denied"] = True

    # 37 execute life_plan.cross_domain_impact_review workflow
    wf_defs = {w.workflow_id: w for w in build_life_plan_workflow_definitions()}
    cdir_def = wf_defs["life_plan.cross_domain_impact_review"]

    def wf_op_adapter(node: Any, run: Any) -> NodeExecution:
        if node.operation_id == "life_plan.evaluate_feasibility":
            res = evaluate_feasibility_result(
                time={
                    "available_hours_per_week": 15.0,
                    "required_hours_per_week": 10.0,
                },
                money={"available_funds": 20000.0, "required_funds": 15000.0},
            )
            return NodeExecution.complete(res)
        elif node.operation_id == "life_plan.identify_risks":
            res = identify_risks_result(risks=[{"id": "r1", "severity": "medium"}])
            return NodeExecution.complete(res)
        elif node.node_type == WorkflowNodeType.LOAD_RESOURCE:
            return NodeExecution.complete(
                {"loaded": True, "sources": ("life_plan", "health_constraints")}
            )
        elif node.node_type == WorkflowNodeType.APPLY_PROFILE:
            return NodeExecution.complete({"applied_profile": profile.profile_name})
        elif node.node_type == WorkflowNodeType.REASON:
            return NodeExecution.complete({"reasoned": True})
        elif node.node_type == WorkflowNodeType.VALIDATE:
            return NodeExecution.complete({"validated": True})
        elif node.node_type == WorkflowNodeType.COMPLETE:
            res = execute_cross_domain_impact_workflow(
                primary_goal=life_goal,
                supporting_domain_contributions=[hc_eval],
                alternative_routes=[alt_route],
            )
            return NodeExecution.complete(res)
        return NodeExecution.complete({"status": "ok"})

    wf_ctx = DomainWorkflowContext(
        primary_domain_id=LIFE_PLAN_DOMAIN_ID,
        known_domain_ids=frozenset(
            {LIFE_PLAN_DOMAIN_ID, "domain:general", "domain:health"}
        ),
        authorized_domain_ids=frozenset({LIFE_PLAN_DOMAIN_ID}),
        available_resources=frozenset(cdir_def.required_resources),
        available_operations=frozenset(
            op.operation_id for op in build_life_plan_operation_definitions()
        ),
    )
    wf_exec = DomainWorkflowExecutor(
        id_factory=id_factory,
        clock=lambda: NOW,
        operation_adapter=wf_op_adapter,
    )
    workflow_run = wf_exec.execute(
        cdir_def,
        wf_ctx,
        inputs={"plan_id": "plan-reloc-01"},
    )
    assert workflow_run.common_run.status.value == "completed"
    assert workflow_run.common_run.workflow_id == "life_plan.cross_domain_impact_review"
    complete_output = workflow_run.execution_result.node_results["complete"].output
    state["37_workflow_run"] = workflow_run

    # 38 verify Major Decision Support output
    assert complete_output["is_decision_support"] is True
    assert complete_output["alternatives_preserved"] is True
    assert complete_output["disclaimer_present"] is True
    state["38_decision_support_verified"] = True

    # 39 evaluate plan drift detection
    drift_res = evaluate_plan_drift(
        planned_state={"language_cert": "achieved", "job_search": "active"},
        confirmed_decisions={"destination": "Berlin"},
        actual_state={"language_cert": "in_progress", "job_search": "not_started"},
    )
    assert drift_res["has_drift"] is True
    assert drift_res["goal_abandoned"] is False
    state["39_plan_drift"] = drift_res

    # 40 generate periodic review
    review_res = generate_periodic_review_result(
        period="annual",
        goals=[life_goal],
        plan_drift=drift_res,
    )
    assert review_res["status"] == "completed"
    assert review_res["period"] == "annual"
    state["40_periodic_review"] = review_res

    # 41 build memory proposal requires confirmation
    mem_proposal_id = id_factory()
    mem_ref_id = id_factory()
    mem_canon_id = id_factory()
    mem_reference = DomainMemoryReference(
        reference_id=mem_ref_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=mem_canon_id,
        domain_id=LIFE_PLAN_DOMAIN_ID,
        applicable_domains=(LIFE_PLAN_DOMAIN_ID,),
    )
    mem_proposal = build_life_plan_memory_proposal(
        proposal_id=mem_proposal_id,
        affected_reference_ids=(mem_ref_id,),
    )
    assert mem_proposal.requires_confirmation is True
    state["41_mem_proposal"] = mem_proposal

    # 42 validate memory view, binding, and tamper rejection
    mem_trace_id = id_factory()

    # Memory-specific permission request & resolution
    mem_perm_req_id = id_factory()
    mem_perm_request = DomainPermissionRequest(
        request_id=mem_perm_req_id,
        action=PermissionCapability.OPERATION_EXECUTE,
        domain_id=LIFE_PLAN_DOMAIN_ID,
        actor_id="actor-lp-user",
        session_id="sess-lp-user",
        operation_id="life_plan.update_plan",
        resource_id="life_plan.resource.memory_entry",
        purpose="propose-confirmed-life-plan-memory",
        context={"proposal_id": mem_proposal.proposal_id},
    )
    mem_perm_res = permission_resolver.resolve(mem_perm_request, now=NOW)
    assert mem_perm_res.effective_permissions.decision is PermissionOutcome.ALLOW
    mem_perm_decision_id = f"memory-permission:{mem_perm_req_id}"
    mem_perm_snapshot = DomainMemoryPermissionDecisionSnapshot(
        decision_id=mem_perm_decision_id,
        allowed=(
            mem_perm_res.effective_permissions.decision is PermissionOutcome.ALLOW
        ),
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=LIFE_PLAN_DOMAIN_ID,
        target_domain_id=LIFE_PLAN_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )

    # Memory-specific approval request & decision
    mem_app_req = approval_service.create_request(
        title="Life Plan Memory Confirmation",
        description=f"Confirm memory proposal {mem_proposal_id}",
        requested_by="life-plan-agent",
        metadata={
            "domain_id": LIFE_PLAN_DOMAIN_ID,
            "proposal_id": mem_proposal.proposal_id,
            "purpose": "persist-confirmed-life-plan-memory",
        },
    )
    approval_service.approve(mem_app_req.id, "user")
    mem_approval_dec = approval_service.repository.list_decisions(mem_app_req.id)[0]
    assert mem_approval_dec.id is not None

    mem_app_req_snapshot = DomainMemoryApprovalRequestSnapshot(
        request_id=mem_app_req.id,
        proposal_id=mem_proposal_id,
    )
    mem_app_dec_snapshot = DomainMemoryApprovalDecisionSnapshot(
        decision_id=mem_approval_dec.id,
        request_id=mem_app_req.id,
        approved=True,
    )

    mem_view_req = build_life_plan_memory_view_request(
        request_id=id_factory(),
        trace_id=mem_trace_id,
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(mem_reference,),
        permission_decision_ids=(mem_perm_decision_id,),
    )
    mem_base_inventory = DomainMemoryReferenceInventory(
        references=(mem_reference,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=mem_trace_id, primary_domain=LIFE_PLAN_DOMAIN_ID
            ),
        ),
        permission_decisions=(mem_perm_snapshot,),
    )
    mem_view = build_life_plan_memory_view(
        request=mem_view_req, inventory=mem_base_inventory
    )
    mem_binding = build_life_plan_memory_binding(
        proposal=mem_proposal,
        view=mem_view,
        trace_id=mem_trace_id,
        permission_decision_ids=(mem_perm_decision_id,),
        approval_request_ids=(mem_app_req.id,),
        approval_decision_ids=(mem_approval_dec.id,),
    )
    mem_full_inventory = DomainMemoryReferenceInventory(
        references=(mem_reference,),
        proposals=(mem_proposal,),
        permission_decisions=(mem_perm_snapshot,),
        approval_requests=(mem_app_req_snapshot,),
        approval_decisions=(mem_app_dec_snapshot,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=mem_trace_id, primary_domain=LIFE_PLAN_DOMAIN_ID
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=mem_view.view_id,
                request_id=mem_view.request_id,
                primary_domain=mem_view.primary_domain,
                trace_id=mem_view.trace_id,
                view_digest=mem_view.content_digest,
            ),
        ),
    )
    mem_val = validate_life_plan_memory_binding(
        binding=mem_binding, inventory=mem_full_inventory
    )
    assert mem_val.is_valid is True

    # Memory Tamper & Substitution Rejection Checks
    # 1. Empty inventory rejected
    bad_mem_val = validate_life_plan_memory_binding(
        binding=mem_binding, inventory=DomainMemoryReferenceInventory()
    )
    assert bad_mem_val.is_valid is False

    # 2. Fake decision ID rejected
    tampered_decision_binding = build_life_plan_memory_binding(
        proposal=mem_proposal,
        view=mem_view,
        trace_id=mem_trace_id,
        permission_decision_ids=("fake-decision-999",),
        approval_request_ids=(mem_app_req.id,),
        approval_decision_ids=(mem_approval_dec.id,),
    )
    assert (
        validate_life_plan_memory_binding(
            binding=tampered_decision_binding, inventory=mem_full_inventory
        ).is_valid
        is False
    )

    # 3. Missing permission decisions rejected
    tampered_inventory = dataclasses.replace(
        mem_full_inventory, permission_decisions=()
    )
    assert (
        validate_life_plan_memory_binding(
            binding=mem_binding, inventory=tampered_inventory
        ).is_valid
        is False
    )

    # 4. Cross-domain permission reused as memory permission rejected
    binding_cross_perm = build_life_plan_memory_binding(
        proposal=mem_proposal,
        view=mem_view,
        trace_id=mem_trace_id,
        permission_decision_ids=(consumed_gate.decision_id,),
        approval_request_ids=(mem_app_req.id,),
        approval_decision_ids=(mem_approval_dec.id,),
    )
    assert (
        validate_life_plan_memory_binding(
            binding=binding_cross_perm, inventory=mem_full_inventory
        ).is_valid
        is False
    )

    # 5. Cross-domain approval reused for memory proposal rejected
    cross_as_mem_app_binding = build_life_plan_memory_binding(
        proposal=mem_proposal,
        view=mem_view,
        trace_id=mem_trace_id,
        permission_decision_ids=(mem_perm_decision_id,),
        approval_request_ids=(cross_approval.id,),
        approval_decision_ids=(cross_decision.id,),
    )
    assert (
        validate_life_plan_memory_binding(
            binding=cross_as_mem_app_binding, inventory=mem_full_inventory
        ).is_valid
        is False
    )

    # 6. Approval for proposal A used for proposal B rejected
    other_proposal_inventory = dataclasses.replace(
        mem_full_inventory,
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id=mem_app_req.id,
                proposal_id="other-proposal-id-999",
            ),
        ),
    )
    assert (
        validate_life_plan_memory_binding(
            binding=mem_binding, inventory=other_proposal_inventory
        ).is_valid
        is False
    )

    # 7. Memory permission for wrong domain rejected
    wrong_domain_perm_inventory = dataclasses.replace(
        mem_full_inventory,
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id=mem_perm_decision_id,
                allowed=True,
                capabilities=(DomainMemoryCapability.PROPOSE,),
                source_domain_id=LIFE_PLAN_DOMAIN_ID,
                target_domain_id="domain:health",
                sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
            ),
        ),
    )
    assert (
        validate_life_plan_memory_binding(
            binding=mem_binding, inventory=wrong_domain_perm_inventory
        ).is_valid
        is False
    )

    # 8. Permission without MEMORY_WRITE / PROPOSE capability rejected
    no_propose_perm_inventory = dataclasses.replace(
        mem_full_inventory,
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id=mem_perm_decision_id,
                allowed=True,
                capabilities=(),
                source_domain_id=LIFE_PLAN_DOMAIN_ID,
                target_domain_id=LIFE_PLAN_DOMAIN_ID,
                sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
            ),
        ),
    )
    assert (
        validate_life_plan_memory_binding(
            binding=mem_binding, inventory=no_propose_perm_inventory
        ).is_valid
        is False
    )

    # 9. Denied shared memory permission (MEMORY_WRITE) cannot produce valid binding
    denied_perm_req = DomainPermissionRequest(
        request_id=id_factory(),
        action=PermissionCapability.MEMORY_WRITE,
        domain_id=LIFE_PLAN_DOMAIN_ID,
        actor_id="actor-lp-user",
        session_id="sess-lp-user",
        resource_id="life_plan.resource.memory_entry",
        purpose="direct-write-denied",
    )
    denied_perm_res = permission_resolver.resolve(denied_perm_req, now=NOW)
    assert denied_perm_res.effective_permissions.decision is PermissionOutcome.DENY
    denied_perm_snapshot = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"memory-permission:{denied_perm_req.request_id}",
        allowed=(
            denied_perm_res.effective_permissions.decision is PermissionOutcome.ALLOW
        ),
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=LIFE_PLAN_DOMAIN_ID,
        target_domain_id=LIFE_PLAN_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    denied_perm_inventory = dataclasses.replace(
        mem_full_inventory, permission_decisions=(denied_perm_snapshot,)
    )
    denied_perm_binding = build_life_plan_memory_binding(
        proposal=mem_proposal,
        view=mem_view,
        trace_id=mem_trace_id,
        permission_decision_ids=(denied_perm_snapshot.decision_id,),
        approval_request_ids=(mem_app_req.id,),
        approval_decision_ids=(mem_approval_dec.id,),
    )
    assert (
        validate_life_plan_memory_binding(
            binding=denied_perm_binding, inventory=denied_perm_inventory
        ).is_valid
        is False
    )

    state["42_mem_val"] = mem_val

    # 43 present life plan result
    raw_lp_res = {
        "status": "feasible",
        "recommended_scenario": "scen-berlin",
        "alternatives_count": 2,
    }
    presented = present_life_plan_result(raw_lp_res)
    presentation_id = id_factory()
    presented["presentation_id"] = presentation_id
    assert presented["domain_display_name"] == "Life Plan"
    assert presented["decision_lattice_preserved"] is True
    state["43_presented"] = presented

    # 44 assemble, validate provenance trace, and test tamper rejection
    domain_result = DomainResult(
        id=id_factory(),
        status="completed",
        objective="Life Plan strategy review",
        primary_domain=LIFE_PLAN_DOMAIN_ID,
        supporting_domains=("domain:health",),
    )
    result_id_str = str(domain_result.id)
    req_id = id_factory()

    runtime_refs = (
        build_life_plan_trace_reference(
            ref_id=str(profile.id), kind=DomainTraceReferenceKind.PROFILE
        ),
        build_life_plan_trace_reference(
            ref_id=workflow_run.common_run.run_id,
            kind=DomainTraceReferenceKind.WORKFLOW_RUN,
        ),
        build_life_plan_trace_reference(
            ref_id=str(workflow_run.common_run.checkpoint_id),
            kind=DomainTraceReferenceKind.WORKFLOW_RESULT,
        ),
        build_life_plan_trace_reference(
            ref_id=consumed_gate.decision_id,
            kind=DomainTraceReferenceKind.PERMISSION_DECISION,
        ),
        build_life_plan_trace_reference(
            ref_id=cross_approval.id,
            kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
        ),
        build_life_plan_trace_reference(
            ref_id=cross_decision.id,
            kind=DomainTraceReferenceKind.APPROVAL_DECISION,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_perm_decision_id,
            kind=DomainTraceReferenceKind.PERMISSION_DECISION,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_app_req.id,
            kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_approval_dec.id,
            kind=DomainTraceReferenceKind.APPROVAL_DECISION,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_proposal.proposal_id,
            kind=DomainTraceReferenceKind.MEMORY_PROPOSAL,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_binding.binding_id,
            kind=DomainTraceReferenceKind.MEMORY_BINDING,
        ),
    )

    expected_refs = (
        DomainTraceReference(
            result_id_str, DomainTraceReferenceKind.DOMAIN_RESULT, LIFE_PLAN_DOMAIN_ID
        ),
        DomainTraceReference(
            str(profile.id), DomainTraceReferenceKind.PROFILE, LIFE_PLAN_DOMAIN_ID
        ),
        DomainTraceReference(
            workflow_run.common_run.run_id,
            DomainTraceReferenceKind.WORKFLOW_RUN,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            str(workflow_run.common_run.checkpoint_id),
            DomainTraceReferenceKind.WORKFLOW_RESULT,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            consumed_gate.decision_id,
            DomainTraceReferenceKind.PERMISSION_DECISION,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            cross_approval.id,
            DomainTraceReferenceKind.APPROVAL_REQUEST,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            cross_decision.id,
            DomainTraceReferenceKind.APPROVAL_DECISION,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_perm_decision_id,
            DomainTraceReferenceKind.PERMISSION_DECISION,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_app_req.id,
            DomainTraceReferenceKind.APPROVAL_REQUEST,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_approval_dec.id,
            DomainTraceReferenceKind.APPROVAL_DECISION,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_proposal.proposal_id,
            DomainTraceReferenceKind.MEMORY_PROPOSAL,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_binding.binding_id,
            DomainTraceReferenceKind.MEMORY_BINDING,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            resolution_context.id,
            DomainTraceReferenceKind.RESOLUTION_CONTEXT,
            None,
        ),
        DomainTraceReference(
            resolution.id,
            DomainTraceReferenceKind.RESOLUTION_RESULT,
            None,
        ),
        DomainTraceReference(
            composition.id,
            DomainTraceReferenceKind.COMPOSITION,
            None,
        ),
        DomainTraceReference(
            presentation_id,
            DomainTraceReferenceKind.PRESENTATION_RESULT,
            None,
        ),
    )

    primary_contrib = build_life_plan_trace_contribution(
        domain_result_id=result_id_str,
        references=runtime_refs,
        domain_id=LIFE_PLAN_DOMAIN_ID,
    )
    trace_refs = DomainTraceReferences(
        resolution_context_id=resolution_context.id,
        resolution_result_id=resolution.id,
        composition_id=composition.id,
        cross_domain_results=(),
        presentation_result_ids=(presentation_id,),
    )
    probe = DomainTrace(
        id="domain-trace:probe",
        digest="0" * 64,
        request_id=req_id,
        goal_id=life_goal["goal_id"],
        primary_domain=LIFE_PLAN_DOMAIN_ID,
        supporting_domains=(),
        contributions=(primary_contrib,),
        references=trace_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id=LIFE_PLAN_DOMAIN_ID,
                trace_id="domain-trace:probe",
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
        duration_ms=0,
        metadata={},
    )
    expected_trace_id = probe.canonical_id

    # Build reference inventory independently from upstream runtime objects BEFORE trace assembly
    inventory = DomainTraceReferenceInventory(
        references=expected_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id=LIFE_PLAN_DOMAIN_ID,
                trace_id=expected_trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=LIFE_PLAN_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            resolution.id, LIFE_PLAN_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(
            composition.id, LIFE_PLAN_DOMAIN_ID, ()
        ),
    )

    # Assemble trace from runtime references
    trace = assemble_life_plan_trace(
        request_id=req_id,
        resolution_context_id=resolution_context.id,
        resolution_result_id=resolution.id,
        composition_id=composition.id,
        domain_result_id=result_id_str,
        presentation_result_ids=(presentation_id,),
        started_at=NOW,
        completed_at=NOW,
        references=runtime_refs,
        goal_id=life_goal["goal_id"],
    )
    assert trace.id == expected_trace_id

    trace_val = validate_life_plan_trace(trace=trace, inventory=inventory)
    assert trace_val.valid is True

    # Trace Tamper Rejection Checks
    primary_contrib = trace.contributions[0]

    # 1. Tampered profile reference rejected
    tampered_ref_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-profile-id")
                    if r.ref_id == str(profile.id)
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    assert (
        validate_life_plan_trace(trace=tampered_ref_trace, inventory=inventory).valid
        is False
    )

    # 2. Tampered permission decision reference rejected
    tampered_perm_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-permission-id")
                    if r.ref_id == consumed_gate.decision_id
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    assert (
        validate_life_plan_trace(trace=tampered_perm_trace, inventory=inventory).valid
        is False
    )

    # 3. Tampered approval decision reference rejected
    tampered_app_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-approval-id")
                    if r.ref_id == cross_decision.id
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    assert (
        validate_life_plan_trace(trace=tampered_app_trace, inventory=inventory).valid
        is False
    )

    # 4. Tampered memory binding reference rejected
    tampered_mem_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-memory-binding-id")
                    if r.ref_id == mem_binding.binding_id
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    assert (
        validate_life_plan_trace(trace=tampered_mem_trace, inventory=inventory).valid
        is False
    )

    # 5. Tampered workflow run reference rejected
    tampered_wf_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-workflow-run-id")
                    if r.ref_id == workflow_run.common_run.run_id
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    assert (
        validate_life_plan_trace(trace=tampered_wf_trace, inventory=inventory).valid
        is False
    )

    # 6. Empty inventory rejected
    bad_inv_val = validate_life_plan_trace(
        trace=trace,
        inventory=dataclasses.replace(inventory, references=()),
    )
    assert bad_inv_val.valid is False

    state["44_trace_validated"] = trace_val

    # 45 end-to-end audit integrity
    assert len(state) >= 44
    assert state["01_resolved_domain"] is not None
    assert state["03_catalog_verified"] is True
    assert state["37_workflow_run"].common_run.status.value == "completed"
    assert state["42_mem_val"].is_valid is True
    assert state["44_trace_validated"].valid is True
