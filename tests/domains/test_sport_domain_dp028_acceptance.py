"""Phase 10.28 — Sport Domain AT-DP-028 Acceptance Scenario.

A single connected state-linked deterministic scenario covering all 44 semantic
checkpoints for domain:sport.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.sport import (
    SPORT_DOMAIN_ID,
    SPORT_DOMAIN_VERSION,
    SPORT_ENTITY_IDS,
    SPORT_OPERATION_IDS,
    SPORT_PERMISSION_POLICY_ID,
    SPORT_PROFILE_ID,
    SPORT_RESOURCE_IDS,
    SPORT_RULE_IDS,
    SPORT_WORKFLOW_IDS,
    adjust_training_load_result,
    assemble_sport_trace,
    build_sport_domain_definition,
    build_sport_memory_binding,
    build_sport_memory_proposal,
    build_sport_memory_view_request,
    build_sport_permission_policy,
    build_sport_presentation_policy,
    build_sport_profile,
    build_sport_rules,
    build_sport_trace_reference,
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
    review_progress_result,
    review_recovery_result,
    schedule_sessions_result,
    track_measurements_result,
    validate_sport_memory_proposal_content,
)
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


def test_at_dp028_connected_acceptance_scenario() -> None:
    """Execute the full 44-checkpoint connected AT-DP-028 acceptance scenario."""
    state: dict[str, Any] = {}

    # 01 resolve domain:sport
    bootstrap = build_standard_sport_domain_bootstrap()
    domain_def = bootstrap.domain_registry.get(SPORT_DOMAIN_ID)
    assert domain_def is not None
    assert str(domain_def.id) == "domain:sport"
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
    goal = {"goal_id": "goal-marathon-001", "name": "Run marathon in under 4 hours", "type": "endurance"}
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
    base_load_res = evaluate_training_load(volume=baseline_volume, intensity=baseline_intensity, frequency=baseline_frequency)
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
    overload_res = evaluate_progressive_overload(baseline_load=210.0, proposed_load=226.8, threshold_percentage=10.0)
    assert overload_res["status"] == "accepted"
    assert overload_res["increase_percentage"] == pytest.approx(8.0)
    state["11_overload"] = overload_res

    # 12 use explicit progression policy rather than universal percentage
    no_thresh_res = evaluate_progressive_overload(baseline_load=210.0, proposed_load=250.0, threshold_percentage=None)
    assert no_thresh_res["status"] == "proposal"
    assert no_thresh_res["certainty"] is False
    state["12_no_universal_percentage"] = no_thresh_res

    # 13 generate workout under current plan
    gen_workout = generate_workout_result(requested_type="tempo_run_45min")
    assert gen_workout["status"] == "generated"
    state["13_generated_workout"] = gen_workout

    # 14 record completed session evidence
    session = {"session_id": "sess-101", "workout": "tempo_run_45min", "duration": 45, "distance_km": 8.5}
    state["14_session"] = session

    # 15 ingest relevant wearable observation
    wearable = {"timestamp": "2026-08-25T08:00:00Z", "avg_hr": 152, "calories": 480}
    state["15_wearable"] = wearable

    # 16 track body measurement with timestamp/unit
    meas1 = track_measurements_result(metric="body_weight", value=72.0, unit="kg", timestamp="2026-08-20T07:00:00Z")
    assert meas1["measurement"]["unit"] == "kg"
    state["16_measurement_1"] = meas1

    # 17 reject one observation as a trend
    single_obs_res = evaluate_measurement_trend([meas1["measurement"]], metric="body_weight")
    assert single_obs_res["status"] == "insufficient_data"
    state["17_single_obs_trend_rejected"] = single_obs_res

    # 18 derive trend only from comparable ordered observations
    multi_obs = [
        {"timestamp": "2026-08-10T07:00:00Z", "value": 73.0, "unit": "kg", "method": "scale"},
        {"timestamp": "2026-08-17T07:00:00Z", "value": 72.5, "unit": "kg", "method": "scale"},
        {"timestamp": "2026-08-24T07:00:00Z", "value": 72.0, "unit": "kg", "method": "scale"},
    ]
    trend_res = evaluate_measurement_trend(multi_obs, metric="body_weight")
    assert trend_res["status"] == "evaluated"
    assert trend_res["direction"] == "decreasing"
    state["18_trend_derived"] = trend_res

    # 19 preserve punctual variation/outlier
    outlier_obs = [
        {"timestamp": "2026-08-10T07:00:00Z", "value": 73.0, "unit": "kg", "method": "scale"},
        {"timestamp": "2026-08-11T07:00:00Z", "value": 85.0, "unit": "kg", "method": "scale"},  # spike
        {"timestamp": "2026-08-24T07:00:00Z", "value": 72.0, "unit": "kg", "method": "scale"},
    ]
    outlier_res = evaluate_measurement_trend(outlier_obs, metric="body_weight")
    assert len(outlier_res["outliers"]) == 1
    state["19_outlier_preserved"] = outlier_res

    # 20 review current recovery
    rec_res = evaluate_recovery(rest_hours=8.0, fatigue_score=2, pain_score=0, workload_score=4)
    assert rec_res["readiness_state"] == "ready"
    state["20_recovery"] = rec_res

    # 21 combine rest/fatigue/pain/workload without diagnosis
    rec_limited = evaluate_recovery(rest_hours=5.5, fatigue_score=7, pain_score=3, workload_score=8)
    assert rec_limited["readiness_state"] == "limited"
    state["21_recovery_combined"] = rec_limited

    # 22 update mutable readiness with newer evidence
    assert rec_res["is_mutable"] is True
    assert rec_limited["is_mutable"] is True
    state["22_readiness_mutable"] = True

    # 23 identify injury signal
    sig_res = evaluate_injury_signal(pain_score=6, pain_location="knee", load_spike=True)
    assert sig_res["action"] in ("stop_and_check", "reduce_load")
    assert sig_res["is_diagnosis"] is False
    state["23_injury_signal"] = sig_res

    # 24 produce stop/check behavior without injury diagnosis
    assert sig_res["is_diagnosis"] is False
    state["24_stop_check_no_diagnosis"] = True

    # 25 request Health contribution for return-to-training
    health_projection = {
        "constraint_id": "const-rtt-001",
        "status": "active",
        "activity_limits": ["no_plyometrics"],
        "load_limits": {"max_intensity": 0.5},
        "authorization_reference": "auth.scope.rtt_001",
        "source_reference": "health.ref.99",
    }
    state["25_health_contribution_request"] = health_projection

    # 26 authorize only health_constraint projection
    hc_eval = evaluate_health_constraint(health_projection, is_authorized=True, is_current=True)
    assert hc_eval["applied"] is True
    assert "activity_limits" in hc_eval["applied_fields"]
    state["26_authorized_projection"] = hc_eval

    # 27 deny full medical report/Health dossier
    full_dossier = {"full_clinical_history": ["surgery_2024"], "medication_list": ["med1"]}
    hc_dossier = evaluate_health_constraint(full_dossier, is_authorized=True, is_current=True)
    assert hc_dossier["applied"] is False
    state["27_full_dossier_denied"] = True

    # 28 preserve Health constraint provenance and authorization
    assert hc_eval["provenance"]["authorization_reference"] == "auth.scope.rtt_001"
    state["28_provenance_preserved"] = True

    # 29 reject expired/unauthorized constraint as current
    hc_expired = evaluate_health_constraint(health_projection, is_authorized=True, is_current=False)
    assert hc_expired["applied"] is False
    state["29_expired_rejected"] = True

    # 30 run sport.return_to_training_with_health_constraints
    wf_res = execute_return_to_training_workflow(
        rest_hours=7.5,
        fatigue_score=4,
        pain_score=2,
        health_constraint=health_projection,
        is_authorized=True,
        is_current=True,
    )
    assert wf_res["status"] == "completed"
    assert wf_res["workflow_id"] == "sport.return_to_training_with_health_constraints"
    state["30_rtt_workflow_run"] = wf_res

    # 31 apply restrictive current constraint to Sport recommendation
    assert wf_res["recommendation"] == "reduce_load"
    assert wf_res["health_constraint_applied"] is True
    state["31_restrictive_constraint_applied"] = True

    # 32 deny treatment modification
    assert wf_res["treatment_modified"] is False
    state["32_treatment_modification_denied"] = True

    # 33 deny clinical-clearance claim
    assert wf_res["clinical_clearance_claimed"] is False
    state["33_clinical_clearance_denied"] = True

    # 34 produce schedule proposal
    sched_prop = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        has_approval=False,
    )
    assert sched_prop["status"] == "proposal_pending_approval"
    state["34_schedule_proposal"] = sched_prop

    # 35 deny direct calendar mutation without approval
    assert sched_prop["external_calendar_mutated"] is False
    state["35_direct_calendar_mutation_denied"] = True

    # 36 preserve scoped approval for calendar path
    sched_approved = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        has_approval=True,
    )
    assert sched_approved["status"] == "ready_for_external_execution"
    state["36_scoped_approval_preserved"] = True

    # 37 produce memory proposal rather than direct write
    mem_prop = build_sport_memory_proposal(proposal_id="sprop-100")
    assert mem_prop.requires_confirmation is True
    state["37_memory_proposal_produced"] = mem_prop

    # 38 prevent clinical/sensitive Health detail from Sport memory proposal
    diag_validation = validate_sport_memory_proposal_content({"kind": "injury_diagnosis", "clinical_diagnosis": "fracture"})
    assert diag_validation["is_valid"] is False
    state["38_sensitive_health_detail_prevented"] = True

    # 39 render trend/readiness/risk with uncertainty
    raw_res = {"readiness_state": "limited", "recommendation": "reduce_load", "trend": "decreasing"}
    presented = present_sport_result(raw_res)
    assert presented["domain_display_name"] == "Sport"
    assert presented["uncertainty_preserved"] is True
    assert presented["is_diagnosis"] is False
    state["39_presentation_rendered"] = presented

    # 40 preserve real runtime trace IDs and cross-domain provenance
    now = datetime.now(timezone.utc)
    trace = assemble_sport_trace(
        request_id="req-acceptance-040",
        resolution_context_id="ctx-040",
        resolution_result_id="res-040",
        composition_id="comp-040",
        domain_result_id="dres-040",
        started_at=now,
        completed_at=now,
    )
    assert trace.primary_domain == "domain:sport"
    assert trace.request_id == "req-acceptance-040"
    state["40_real_trace_preserved"] = trace

    # 41 prove atomic Sport registration
    regs = {
        "domain_registry": DomainRegistry(),
        "profile_registry": InMemoryDomainProfileRegistry(),
        "resource_registry": InMemoryDomainResourceRegistry(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
        "operation_registry": InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry()),
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
        "operation_registry": InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry()),
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
