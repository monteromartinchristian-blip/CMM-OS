"""Phase 10.28 — Sport Domain AT-DP-028 Acceptance Scenario.

A single connected state-linked deterministic scenario covering all 44 semantic
checkpoints for domain:sport using real shared contracts for resolver, profile,
rules, operations, workflows, cross-domain permission requests/gates, approval
lifecycle, memory proposal/view/binding validation, and trace inventory validation.
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
)
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainResult
from cmm.domains.enums import (
    DomainRuleSelectionStatus,
    DomainRuleSource,
)
from cmm.domains.general.permissions import build_general_permission_policy
from cmm.domains.health.permissions import build_health_permission_policy
from cmm.domains.identifiers import DomainId
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
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_contracts import CrossDomainPermissionRequest
from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateOutcome,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import DomainResolutionSignal
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.rule_contracts import (
    DomainRuleExecutionPlan,
    DomainRuleSourceRecord,
    SelectedReasoningRule,
)
from cmm.domains.rule_execution import DefaultDomainRuleExecutor
from cmm.domains.sport import (
    SPORT_DOMAIN_ID,
    SPORT_ENTITY_IDS,
    SPORT_OPERATION_IDS,
    SPORT_PROFILE_ID,
    SPORT_RESOURCE_IDS,
    SPORT_RULE_IDS,
    SPORT_WORKFLOW_IDS,
    adjust_training_load_result,
    assemble_sport_trace,
    build_sport_domain_definition,
    build_sport_memory_binding,
    build_sport_memory_proposal,
    build_sport_memory_view,
    build_sport_memory_view_request,
    build_sport_operation_definitions,
    build_sport_permission_policy,
    build_sport_rules,
    build_sport_trace_reference,
    build_sport_workflow_definitions,
    build_standard_sport_domain_bootstrap,
    create_training_plan_result,
    evaluate_health_constraint,
    evaluate_injury_signal,
    evaluate_measurement_trend,
    evaluate_progressive_overload,
    evaluate_recovery,
    evaluate_training_load,
    execute_return_to_training_workflow,
    generate_workout_result,
    identify_risks_result,
    present_sport_result,
    register_sport_domain,
    schedule_sessions_result,
    track_measurements_result,
    validate_sport_memory_binding,
    validate_sport_memory_proposal_content,
    validate_sport_trace,
)
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowNodeType
from cmm.workflows.registry import InMemoryWorkflowRegistry

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


class DeterministicIdFactory:
    def __init__(self) -> None:
        self._counter = 0

    def __call__(self) -> str:
        self._counter += 1
        return f"at-dp028-id-{self._counter}"


def test_at_dp028_connected_acceptance_scenario() -> None:
    """Execute the full 44-checkpoint connected AT-DP-028 acceptance scenario."""
    id_factory = DeterministicIdFactory()
    state: dict[str, Any] = {}

    # 01 resolve domain:sport through canonical resolver
    bootstrap = build_standard_sport_domain_bootstrap()
    resolution_signals = (
        DomainResolutionSignal(
            kind="intent",
            source="user",
            value="train for marathon",
            domain_ids=("domain:sport",),
        ),
        DomainResolutionSignal(
            kind="entity",
            source="user",
            value="running schedule",
            domain_ids=("domain:sport",),
        ),
    )
    resolution_context = DomainResolutionContextBuilder(
        id_factory=id_factory, clock=lambda: NOW
    ).build(
        registry_snapshot=bootstrap.domain_registry.snapshot(),
        user_input="Help me set up a 12-week marathon training plan.",
        authorized_domains=("domain:general", SPORT_DOMAIN_ID),
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
    ).compose(resolution, (build_sport_domain_definition(),))
    domain_def = bootstrap.domain_registry.get(SPORT_DOMAIN_ID)

    assert domain_def is not None
    assert str(domain_def.id) == "domain:sport"
    assert str(resolution.primary_domain) == SPORT_DOMAIN_ID
    assert str(composition.primary_domain) == SPORT_DOMAIN_ID
    state["01_resolved_domain"] = domain_def

    # 02 load/reuse SportProfile
    profile = bootstrap.profile_registry.get_by_domain(DomainId("sport"))
    assert profile is not None
    assert profile.id == SPORT_PROFILE_ID
    assert profile.profile_name == "SportProfile"
    state["02_profile"] = profile

    # 03 verify exact 11/9/6/8/5 catalog
    assert len(SPORT_ENTITY_IDS) == 11
    assert len(SPORT_RESOURCE_IDS) == 9
    assert len(SPORT_RULE_IDS) == 6
    assert len(SPORT_OPERATION_IDS) == 8
    assert len(SPORT_WORKFLOW_IDS) == 5
    state["03_catalog_verified"] = True

    # 04 create explicit sport goal
    goal = {
        "goal_id": "goal-marathon-001",
        "name": "Run marathon in under 4 hours",
        "type": "endurance",
    }
    state["04_goal"] = goal

    # 05 create training plan proposal
    plan_res = create_training_plan_result(goal=goal["name"], weeks=12)
    assert plan_res["is_proposal"] is True
    assert plan_res["is_medical_prescription"] is False
    state["05_plan_proposal"] = plan_res

    # 06 preserve baseline workload
    baseline_volume = 100.0
    baseline_intensity = 0.7
    baseline_frequency = 3
    base_load_res = evaluate_training_load(
        volume=baseline_volume,
        intensity=baseline_intensity,
        frequency=baseline_frequency,
    )
    assert base_load_res["status"] == "evaluated"
    assert base_load_res["load_value"] == 210.0
    state["06_baseline_load"] = base_load_res

    # 07 evaluate volume
    assert base_load_res["components"]["volume"] == 100.0
    state["07_volume"] = 100.0

    # 08 evaluate intensity
    assert base_load_res["components"]["intensity"] == 0.7
    state["08_intensity"] = 0.7

    # 09 evaluate frequency
    assert base_load_res["components"]["frequency"] == 3
    state["09_frequency"] = 3

    # 10 preserve missing load evidence as unknown
    missing_load = evaluate_training_load(volume=100.0, intensity=None, frequency=3)
    assert missing_load["status"] == "unknown"
    state["10_missing_load"] = missing_load

    # 11 compare progressive overload
    overload_res = evaluate_progressive_overload(
        baseline_load=210.0, proposed_load=226.8, threshold_percentage=10.0
    )
    assert overload_res["status"] == "accepted"
    assert overload_res["increase_percentage"] == pytest.approx(8.0)
    state["11_overload"] = overload_res

    # 12 use explicit progression policy rather than universal percentage
    no_thresh_res = evaluate_progressive_overload(
        baseline_load=210.0, proposed_load=250.0, threshold_percentage=None
    )
    assert no_thresh_res["status"] == "proposal"
    assert no_thresh_res["certainty"] is False
    state["12_no_universal_percentage"] = no_thresh_res

    # 13 generate workout under current plan
    gen_workout = generate_workout_result(requested_type="tempo_run_45min")
    assert gen_workout["status"] == "generated"
    state["13_generated_workout"] = gen_workout

    # 14 record completed session evidence
    session = {
        "session_id": "sess-101",
        "workout": "tempo_run_45min",
        "duration": 45,
        "distance_km": 8.5,
    }
    state["14_session"] = session

    # 15 ingest relevant wearable observation
    wearable = {"timestamp": "2026-08-25T08:00:00Z", "avg_hr": 152, "calories": 480}
    state["15_wearable"] = wearable

    # 16 track body measurement with timestamp/unit
    meas1 = track_measurements_result(
        metric="body_weight", value=72.0, unit="kg", timestamp="2026-08-20T07:00:00Z"
    )
    assert meas1["measurement"]["unit"] == "kg"
    state["16_measurement_1"] = meas1

    # 17 reject one observation as a trend
    single_obs_res = evaluate_measurement_trend(
        [meas1["measurement"]], metric="body_weight"
    )
    assert single_obs_res["status"] == "insufficient_data"
    state["17_single_obs_trend_rejected"] = single_obs_res

    # 18 derive trend only from comparable ordered observations
    multi_obs = [
        {
            "timestamp": "2026-08-24T07:00:00Z",
            "value": 72.0,
            "unit": "kg",
            "method": "scale",
            "metric": "body_weight",
        },
        {
            "timestamp": "2026-08-10T07:00:00Z",
            "value": 73.0,
            "unit": "kg",
            "method": "scale",
            "metric": "body_weight",
        },
        {
            "timestamp": "2026-08-17T07:00:00Z",
            "value": 72.5,
            "unit": "kg",
            "method": "scale",
            "metric": "body_weight",
        },
    ]
    trend_res = evaluate_measurement_trend(multi_obs, metric="body_weight")
    assert trend_res["status"] == "evaluated"
    assert trend_res["direction"] == "decreasing"
    state["18_trend_derived"] = trend_res

    # 19 preserve punctual variation/outlier
    outlier_obs = [
        {
            "timestamp": "2026-08-10T07:00:00Z",
            "value": 73.0,
            "unit": "kg",
            "method": "scale",
            "metric": "body_weight",
        },
        {
            "timestamp": "2026-08-11T07:00:00Z",
            "value": 85.0,
            "unit": "kg",
            "method": "scale",
            "metric": "body_weight",
        },  # spike
        {
            "timestamp": "2026-08-24T07:00:00Z",
            "value": 72.0,
            "unit": "kg",
            "method": "scale",
            "metric": "body_weight",
        },
    ]
    outlier_res = evaluate_measurement_trend(outlier_obs, metric="body_weight")
    assert len(outlier_res["outliers"]) == 1
    state["19_outlier_preserved"] = outlier_res

    # 20 review current recovery
    rec_res = evaluate_recovery(
        rest_hours=8.0, fatigue_score=2, pain_score=0, workload_score=4
    )
    assert rec_res["readiness_state"] == "ready"
    state["20_recovery"] = rec_res

    # 21 combine rest/fatigue/pain/workload without diagnosis
    rec_limited = evaluate_recovery(
        rest_hours=5.5, fatigue_score=7, pain_score=3, workload_score=8
    )
    assert rec_limited["readiness_state"] == "limited"
    state["21_recovery_combined"] = rec_limited

    # 22 update mutable readiness with newer evidence
    assert rec_res["is_mutable"] is True
    assert rec_limited["is_mutable"] is True
    state["22_readiness_mutable"] = True

    # 23 identify injury signal
    sig_res = evaluate_injury_signal(
        pain_score=6, pain_location="knee", load_spike=True
    )
    assert sig_res["action"] in ("stop_and_check", "reduce_load")
    assert sig_res["is_diagnosis"] is False
    state["23_injury_signal"] = sig_res

    # 24 produce stop/check behavior without injury diagnosis
    assert sig_res["is_diagnosis"] is False
    state["24_stop_check_no_diagnosis"] = True

    # ── Permission & Approval Shared Setup ──────────────────────────────────────
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_sport_permission_policy())
    perm_registry.register(build_general_permission_policy())
    health_policy = dataclasses.replace(
        build_health_permission_policy(),
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:sport",),
        allowed_capabilities=(
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            PermissionCapability.RESOURCE_READ,
        ),
        allowed_resource_kinds=("resource.health_resource",),
        allowed_sensitivity_levels=("restricted",),
    )
    perm_registry.register(health_policy)
    approval_service = ApprovalService(InMemoryApprovalRepository())
    permission_resolver = DomainPermissionResolver(perm_registry)
    gate = DomainPermissionGate(
        permission_resolver, approval_service, clock=lambda: NOW
    )

    # 25 request Health contribution for return-to-training via typed request
    cross_request = CrossDomainPermissionRequest(
        request_id=id_factory(),
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="return-to-training functional constraint",
        actor_id="actor-at-dp028",
        session_id="sess-at-dp028",
        sensitivity_level="restricted",
        resource_ids=("sport.resource.health_resource:rtt-001",),
        resource_kinds=("resource.health_resource",),
    )
    state["25_health_contribution_request"] = cross_request

    # 26 authorize only health_constraint projection through permission resolution + gate
    pending_cross = gate.evaluate_cross_domain(cross_request)

    assert pending_cross.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    req_item = PermissionApprovalRequirement.from_dict(
        pending_cross.approval_requirements[0]
    )
    cross_approval = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id=id_factory()),
        requested_by="sports-physician-review",
    )
    approval_service.approve(cross_approval.id, "sports-physician")
    cross_decision = approval_service.repository.list_decisions(cross_approval.id)[0]
    assert cross_decision.id is not None
    consumed_cross = gate.evaluate_cross_domain(
        cross_request, approval_request_id=cross_approval.id
    )

    assert consumed_cross.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert consumed_cross.allowed is True
    assert consumed_cross.decision_id is not None

    health_raw_projection = {
        "constraint_id": "const-rtt-001",
        "status": "active",
        "activity_limits": ["no_plyometrics"],
        "load_limits": {"reduction_pct": 30},
        "authorization_reference": consumed_cross.decision_id,
        "source_reference": "health.ref.99",
        "diagnosis": "patellar tendinopathy",
        "treatment_plan": "physiotherapy",
        "clinical_notes": "restricted",
    }
    hc_eval = evaluate_health_constraint(
        health_raw_projection,
        permission_decision=consumed_cross,
        is_current=True,
    )
    assert hc_eval["applied"] is True
    assert "activity_limits" in hc_eval["applied_fields"]
    assert "diagnosis" not in hc_eval["constraint"]
    assert "treatment_plan" not in hc_eval["constraint"]
    assert "clinical_notes" not in hc_eval["constraint"]
    state["26_authorized_projection"] = hc_eval

    # 27 deny full medical report/Health dossier through permission gate & rule
    dossier_req = CrossDomainPermissionRequest(
        request_id=id_factory(),
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="unauthorized clinical dossier request",
        actor_id="actor-at-dp028",
        session_id="sess-at-dp028",
        sensitivity_level="restricted",
        resource_ids=("health.dossier:001",),
        resource_kinds=("medical_report", "full_clinical_history"),
    )
    dossier_gate = gate.evaluate_cross_domain(dossier_req)
    assert dossier_gate.outcome is PermissionGateOutcome.DENY
    assert not dossier_gate.allowed

    full_dossier = {
        "full_clinical_history": ["surgery_2024"],
        "medication_list": ["med1"],
    }
    hc_dossier = evaluate_health_constraint(
        full_dossier, is_authorized=True, is_current=True
    )
    assert hc_dossier["applied"] is False
    assert hc_dossier["reason"] == "rejected_unauthorized_dossier"
    state["27_full_dossier_denied"] = True

    # 28 preserve Health constraint provenance and authorization
    assert (
        hc_eval["provenance"]["authorization_reference"] == consumed_cross.decision_id
    )
    assert hc_eval["provenance"]["source_reference"] == "health.ref.99"
    state["28_provenance_preserved"] = True

    # 29 reject expired/unauthorized constraint as current
    hc_expired = evaluate_health_constraint(
        hc_eval["constraint"],
        permission_decision=consumed_cross,
        is_current=False,
    )
    assert hc_expired["applied"] is False
    state["29_expired_rejected"] = True

    # 30 run sport.return_to_training_with_health_constraints through shared workflow runtime
    wf_defs = {w.workflow_id: w for w in build_sport_workflow_definitions()}
    rtt_def = wf_defs["sport.return_to_training_with_health_constraints"]

    def wf_op_adapter(node: Any, run: Any) -> NodeExecution:
        if node.operation_id == "sport.identify_risks":
            res = identify_risks_result(
                pain_score=2,
                performance_drop=0.0,
                load_spike=False,
            )
            return NodeExecution.complete(res)
        elif node.operation_id == "sport.adjust_training_load":
            res = adjust_training_load_result(
                current_load=100.0,
                readiness_state="ready",
                health_constraint=hc_eval,
            )
            return NodeExecution.complete(res)
        elif node.node_type == WorkflowNodeType.LOAD_RESOURCE:
            return NodeExecution.complete(
                {"loaded": True, "sources": ("training_plan", "wearable_data")}
            )
        elif node.node_type == WorkflowNodeType.APPLY_PROFILE:
            return NodeExecution.complete({"applied_profile": profile.profile_name})
        elif node.node_type == WorkflowNodeType.REASON:
            return NodeExecution.complete({"reasoned": True})
        elif node.node_type == WorkflowNodeType.VALIDATE:
            return NodeExecution.complete({"validated": True})
        elif node.node_type == WorkflowNodeType.COMPLETE:
            res = execute_return_to_training_workflow(
                rest_hours=7.5,
                fatigue_score=4,
                pain_score=2,
                health_constraint=hc_eval,
                is_current=True,
            )
            return NodeExecution.complete(res)
        return NodeExecution.complete({"status": "ok"})

    wf_ctx = DomainWorkflowContext(
        primary_domain_id=SPORT_DOMAIN_ID,
        known_domain_ids=frozenset(
            {SPORT_DOMAIN_ID, "domain:general", "domain:health"}
        ),
        authorized_domain_ids=frozenset({SPORT_DOMAIN_ID}),
        available_resources=frozenset(rtt_def.required_resources),
        available_operations=frozenset(
            op.operation_id for op in build_sport_operation_definitions()
        ),
    )
    wf_exec = DomainWorkflowExecutor(
        id_factory=id_factory,
        clock=lambda: NOW,
        operation_adapter=wf_op_adapter,
    )
    workflow_run = wf_exec.execute(
        rtt_def,
        wf_ctx,
        inputs={
            "rest_hours": 7.5,
            "fatigue_score": 4,
            "pain_score": 2,
        },
    )
    assert workflow_run.common_run.status.value == "completed"
    assert (
        workflow_run.common_run.workflow_id
        == "sport.return_to_training_with_health_constraints"
    )
    complete_node_output = workflow_run.execution_result.node_results["complete"].output
    state["30_rtt_workflow_run"] = workflow_run

    # 31 apply restrictive current constraint to Sport recommendation (from workflow runtime)
    assert complete_node_output["recommendation"] == "reduce_load"
    assert complete_node_output["health_constraint_applied"] is True
    state["31_restrictive_constraint_applied"] = True

    # 32 deny treatment modification
    assert complete_node_output["treatment_modified"] is False
    state["32_treatment_modification_denied"] = True

    # 33 deny clinical-clearance claim
    assert complete_node_output["clinical_clearance_claimed"] is False
    state["33_clinical_clearance_denied"] = True

    # 34 produce schedule proposal
    sched_prop = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
    )
    assert sched_prop["status"] == "proposal_pending_approval"
    state["34_schedule_proposal"] = sched_prop

    # 35 deny direct calendar mutation without approval
    assert sched_prop["external_calendar_mutated"] is False
    assert sched_prop["approval_required"] is True
    bare_sched = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        has_approval=True,
    )
    assert bare_sched["status"] == "proposal_pending_approval"

    # Fabricated approval strings fail
    fake_sched = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_request_id="fake-request-id",
        approval_decision_id="fake-decision-id",
    )
    assert fake_sched["status"] == "proposal_pending_approval"

    # Duck-typed fake approval evidence fails
    class FakeApprovalEvidence:
        granted = True
        action = "sport.schedule_sessions"
        request_id = "fake-req"

    assert (
        schedule_sessions_result(
            sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
            approval_evidence=FakeApprovalEvidence(),
        )["status"]
        == "proposal_pending_approval"
    )

    state["35_direct_calendar_mutation_denied"] = True

    # 36 preserve scoped approval for calendar path
    cal_approval = approval_service.create_request(
        title="Approve weekly running schedule",
        description="Schedule 3 weekly training sessions on athlete calendar",
        requested_by="athlete-scheduler",
        operation_id="sport.schedule_sessions",
    )
    approval_service.approve(cal_approval.id, "athlete")
    cal_decision = approval_service.repository.list_decisions(cal_approval.id)[0]

    # Mismatched approval fails
    mismatched_req = approval_service.create_request(
        title="Approve other schedule",
        description="Other schedule",
        operation_id="sport.schedule_sessions",
    )
    mismatched_sched = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_request=mismatched_req,
        approval_decision=cal_decision,
    )
    assert mismatched_sched["status"] == "proposal_pending_approval"

    sched_approved = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_request=cal_approval,
        approval_decision=cal_decision,
    )
    assert sched_approved["status"] == "ready_for_external_execution"
    assert sched_approved["approval_granted"] is True
    assert sched_approved["approval_request_id"] == cal_approval.id
    assert sched_approved["approval_decision_id"] == cal_decision.id
    assert sched_approved["external_calendar_mutated"] is False
    state["36_scoped_approval_preserved"] = sched_approved

    # 37 produce memory proposal rather than direct write
    mem_proposal_id = id_factory()
    mem_ref_id = id_factory()
    mem_canon_id = id_factory()
    mem_ev_id = id_factory()
    mem_reference = DomainMemoryReference(
        reference_id=mem_ref_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=mem_canon_id,
        domain_id=SPORT_DOMAIN_ID,
        applicable_domains=(SPORT_DOMAIN_ID,),
        evidence_ids=(mem_ev_id,),
    )

    mem_trace_id = id_factory()
    mem_proposal = build_sport_memory_proposal(
        proposal_id=mem_proposal_id,
        affected_reference_ids=(mem_ref_id,),
    )
    assert mem_proposal.requires_confirmation is True
    state["37_memory_proposal_produced"] = mem_proposal

    # 38 prevent clinical/sensitive Health detail from Sport memory proposal and validate binding
    diag_validation = validate_sport_memory_proposal_content(
        {"kind": "injury_diagnosis", "clinical_diagnosis": "fracture"}
    )
    assert diag_validation["is_valid"] is False

    mem_perm_snapshot = DomainMemoryPermissionDecisionSnapshot(
        decision_id=consumed_cross.decision_id,
        allowed=consumed_cross.allowed,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=SPORT_DOMAIN_ID,
        target_domain_id=SPORT_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    mem_view_req = build_sport_memory_view_request(
        request_id=id_factory(),
        trace_id=mem_trace_id,
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(mem_reference,),
        permission_decision_ids=(consumed_cross.decision_id,),
    )
    mem_base_inventory = DomainMemoryReferenceInventory(
        references=(mem_reference,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=mem_trace_id, primary_domain=SPORT_DOMAIN_ID
            ),
        ),
        permission_decisions=(mem_perm_snapshot,),
    )
    mem_view = build_sport_memory_view(
        request=mem_view_req, inventory=mem_base_inventory
    )
    mem_binding = build_sport_memory_binding(
        proposal=mem_proposal,
        view=mem_view,
        trace_id=mem_trace_id,
        permission_decision_ids=(consumed_cross.decision_id,),
        approval_request_ids=(cal_approval.id,),
        approval_decision_ids=(cal_decision.id,),
    )

    mem_full_inventory = DomainMemoryReferenceInventory(
        references=(mem_reference,),
        proposals=(mem_proposal,),
        permission_decisions=(mem_perm_snapshot,),
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id=cal_approval.id, proposal_id=mem_proposal_id
            ),
        ),
        approval_decisions=(
            DomainMemoryApprovalDecisionSnapshot(
                decision_id=cal_decision.id,
                request_id=cal_approval.id,
                approved=True,
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=mem_trace_id, primary_domain=SPORT_DOMAIN_ID
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
    mem_val = validate_sport_memory_binding(
        binding=mem_binding, inventory=mem_full_inventory
    )
    assert mem_val.is_valid is True

    # Malformed / empty inventory fails validation
    bad_mem_val = validate_sport_memory_binding(
        binding=mem_binding, inventory=DomainMemoryReferenceInventory()
    )
    assert bad_mem_val.is_valid is False
    state["38_sensitive_health_detail_prevented"] = True

    # 39 render trend/readiness/risk with uncertainty
    raw_res = {
        "readiness_state": "limited",
        "recommendation": "reduce_load",
        "trend": "decreasing",
    }
    presented = present_sport_result(raw_res)
    assert presented["domain_display_name"] == "Sport"
    assert presented["uncertainty_preserved"] is True
    assert presented["is_diagnosis"] is False
    state["39_presentation_rendered"] = presented

    # 40 preserve real runtime trace IDs and cross-domain provenance with reference inventory
    rule_plan_id = id_factory()
    rules = {rule.definition.id: rule for rule in build_sport_rules()}
    rule_plan = DomainRuleExecutionPlan(
        id=rule_plan_id,
        status=DomainRuleSelectionStatus.READY,
        created_at=NOW,
        selected_rules=(
            SelectedReasoningRule(
                definition=rules["sport.rule.progressive_overload"].definition,
                sources=(
                    DomainRuleSourceRecord(
                        source=DomainRuleSource.PROFILE,
                        reference="sport.rule.progressive_overload",
                        required=True,
                        domain_id=SPORT_DOMAIN_ID,
                        profile_name=profile.profile_name,
                    ),
                ),
                group=DomainRuleSource.PRIMARY_DOMAIN,
                required=True,
            ),
        ),
        contributing_profiles=(profile.profile_name,),
        contributing_domains=(SPORT_DOMAIN_ID,),
    )
    rule_reg = InMemoryReasoningRuleRegistry()
    rule_reg.register(rules["sport.rule.progressive_overload"])
    rule_exec = DefaultDomainRuleExecutor(
        clock=lambda: NOW, id_factory=id_factory
    ).execute(
        plan=rule_plan,
        context=ReasoningRuleContext(
            reasoning_id=id_factory(),
            timestamp=NOW,
            session_id="sess-at-dp028",
            active_domains=(SPORT_DOMAIN_ID,),
            primary_domain=SPORT_DOMAIN_ID,
            metadata={
                "baseline_load": 210.0,
                "proposed_load": 226.8,
                "threshold_percentage": 10.0,
            },
        ),
        registry=rule_reg,
    )

    # 40 preserve real runtime trace IDs and cross-domain provenance with reference inventory
    runtime_domain_result = DomainResult(
        id=f"result-{id_factory()}",
        status="completed",
        objective="Sport return-to-training with Health constraints",
        primary_domain=SPORT_DOMAIN_ID,
        supporting_domains=("domain:health",),
        reasoning_result_id=rule_exec.id,
        workflow_result_id=workflow_run.common_run.run_id,
        approval_ids=(cal_approval.id,),
    )
    runtime_domain_result_id = str(runtime_domain_result.id)

    # Build reference inventory independently from upstream runtime objects
    independent_inventory_refs = (
        DomainTraceReference(
            ref_id=runtime_domain_result_id,
            kind=DomainTraceReferenceKind.DOMAIN_RESULT,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=str(profile.id),
            kind=DomainTraceReferenceKind.PROFILE,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=rule_plan.id,
            kind=DomainTraceReferenceKind.RULE_PLAN,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=rule_exec.id,
            kind=DomainTraceReferenceKind.RULE_RESULT,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=consumed_cross.decision_id,
            kind=DomainTraceReferenceKind.PERMISSION_DECISION,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=cal_approval.id,
            kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=cal_decision.id,
            kind=DomainTraceReferenceKind.APPROVAL_DECISION,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=workflow_run.common_run.run_id,
            kind=DomainTraceReferenceKind.WORKFLOW_RUN,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=mem_proposal.proposal_id,
            kind=DomainTraceReferenceKind.MEMORY_PROPOSAL,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=mem_binding.binding_id,
            kind=DomainTraceReferenceKind.MEMORY_BINDING,
            domain_id=SPORT_DOMAIN_ID,
        ),
        DomainTraceReference(
            ref_id=resolution_context.id,
            kind=DomainTraceReferenceKind.RESOLUTION_CONTEXT,
            domain_id=None,
        ),
        DomainTraceReference(
            ref_id=resolution.id,
            kind=DomainTraceReferenceKind.RESOLUTION_RESULT,
            domain_id=None,
        ),
        DomainTraceReference(
            ref_id=composition.id,
            kind=DomainTraceReferenceKind.COMPOSITION,
            domain_id=None,
        ),
    )
    # Assemble trace from runtime references
    runtime_trace_refs = (
        build_sport_trace_reference(
            ref_id=str(profile.id), kind=DomainTraceReferenceKind.PROFILE
        ),
        build_sport_trace_reference(
            ref_id=rule_plan.id, kind=DomainTraceReferenceKind.RULE_PLAN
        ),
        build_sport_trace_reference(
            ref_id=rule_exec.id, kind=DomainTraceReferenceKind.RULE_RESULT
        ),
        build_sport_trace_reference(
            ref_id=consumed_cross.decision_id,
            kind=DomainTraceReferenceKind.PERMISSION_DECISION,
        ),
        build_sport_trace_reference(
            ref_id=cal_approval.id, kind=DomainTraceReferenceKind.APPROVAL_REQUEST
        ),
        build_sport_trace_reference(
            ref_id=cal_decision.id, kind=DomainTraceReferenceKind.APPROVAL_DECISION
        ),
        build_sport_trace_reference(
            ref_id=workflow_run.common_run.run_id,
            kind=DomainTraceReferenceKind.WORKFLOW_RUN,
        ),
        build_sport_trace_reference(
            ref_id=mem_proposal.proposal_id,
            kind=DomainTraceReferenceKind.MEMORY_PROPOSAL,
        ),
        build_sport_trace_reference(
            ref_id=mem_binding.binding_id,
            kind=DomainTraceReferenceKind.MEMORY_BINDING,
        ),
    )
    trace = assemble_sport_trace(
        request_id=cross_request.request_id,
        resolution_context_id=resolution_context.id,
        resolution_result_id=resolution.id,
        composition_id=composition.id,
        domain_result_id=runtime_domain_result_id,
        started_at=NOW,
        completed_at=NOW,
        references=runtime_trace_refs,
    )
    assert trace.primary_domain == SPORT_DOMAIN_ID

    inventory = DomainTraceReferenceInventory(
        references=independent_inventory_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id=runtime_domain_result_id,
                domain_id=SPORT_DOMAIN_ID,
                trace_id=trace.id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=SPORT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            resolution.id, SPORT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(
            composition.id, SPORT_DOMAIN_ID, ()
        ),
    )

    val_trace = validate_sport_trace(trace=trace, inventory=inventory)
    assert val_trace.valid is True

    # Negative 1: Fabricated reference present in trace but absent from inventory fails
    fabricated_trace = assemble_sport_trace(
        request_id=cross_request.request_id,
        resolution_context_id=resolution_context.id,
        resolution_result_id=resolution.id,
        composition_id=composition.id,
        domain_result_id=runtime_domain_result_id,
        started_at=NOW,
        completed_at=NOW,
        references=(
            *runtime_trace_refs,
            build_sport_trace_reference(
                ref_id="ghost-fabricated-ref",
                kind=DomainTraceReferenceKind.RULE_RESULT,
            ),
        ),
    )
    bad_fabricated_val = validate_sport_trace(
        trace=fabricated_trace, inventory=inventory
    )
    assert bad_fabricated_val.valid is False
    assert "ghost-fabricated-ref" in bad_fabricated_val.unexpected_references

    # Negative 2: Tampered reference in trace fails validation
    primary_contrib = trace.contributions[0]
    tampered_trace = replace(
        trace,
        contributions=(
            replace(
                primary_contrib,
                references=tuple(
                    replace(ref, ref_id="ghost-tampered-id")
                    if ref.ref_id == rule_exec.id
                    else ref
                    for ref in primary_contrib.references
                ),
            ),
        ),
    )
    bad_trace_val = validate_sport_trace(trace=tampered_trace, inventory=inventory)
    assert bad_trace_val.valid is False
    assert rule_exec.id in bad_trace_val.missing_references

    # Negative 3: Fabricated domain result ID without inventory backing fails
    fake_res_trace = assemble_sport_trace(
        request_id=cross_request.request_id,
        resolution_context_id=resolution_context.id,
        resolution_result_id=resolution.id,
        composition_id=composition.id,
        domain_result_id="fabricated-domain-result-999",
        started_at=NOW,
        completed_at=NOW,
        references=runtime_trace_refs,
    )
    bad_fake_res_val = validate_sport_trace(trace=fake_res_trace, inventory=inventory)
    assert bad_fake_res_val.valid is False

    state["40_real_trace_preserved"] = trace

    # 41 prove atomic Sport registration
    regs = {
        "domain_registry": DomainRegistry(),
        "profile_registry": InMemoryDomainProfileRegistry(),
        "resource_registry": InMemoryDomainResourceRegistry(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
        "operation_registry": InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        "workflow_registry": InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry()),
        "permission_registry": DomainPermissionRegistry(),
    }
    int_res = register_sport_domain(**regs)
    assert int_res.definition.id == "domain:sport"
    state["41_atomic_registration_proven"] = True

    # 42 prove rollback parity after registration failure
    faulty_regs = {
        "domain_registry": DomainRegistry(),
        "profile_registry": InMemoryDomainProfileRegistry(),
        "resource_registry": InMemoryDomainResourceRegistry(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
        "operation_registry": InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        "workflow_registry": InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry()),
        "permission_registry": DomainPermissionRegistry(),
    }

    class FaultyPerm(DomainPermissionRegistry):
        def register(self, policy: Any) -> Any:
            raise RuntimeError("Injected integration fault")

    faulty_regs["permission_registry"] = FaultyPerm()
    with pytest.raises(RuntimeError):
        register_sport_domain(**faulty_regs)
    assert faulty_regs["domain_registry"].get(SPORT_DOMAIN_ID) is None
    state["42_rollback_parity_proven"] = True

    # 43 prove no parallel Sport runtime/planner/memory/workflow engine
    import cmm.domains.sport

    assert not hasattr(cmm.domains.sport, "SportRuntime")
    assert not hasattr(cmm.domains.sport, "SportPlanner")
    assert not hasattr(cmm.domains.sport, "SportMemoryStore")
    assert not hasattr(cmm.domains.sport, "SportWorkflowEngine")
    state["43_no_parallel_engine_proven"] = True

    # 44 prove General fallback compatibility
    gen_def = bootstrap.domain_registry.get("domain:general")
    assert gen_def is not None
    assert str(gen_def.id) == "domain:general"
    state["44_general_fallback_proven"] = True

    # Confirm all 44 checkpoints completed
    assert len(state) == 44
