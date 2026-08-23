"""Phase 10.26 — Languages Domain Adversarial & Failure-Mode Suite."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import datetime, timezone

from cmm.agent_runtime.approval_contracts import ApprovalRequest
from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
)
from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.agent_runtime.operation_schema import validate_operation_schema
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.contracts import DomainResult
from cmm.domains.enums import DomainOperationType
from cmm.domains.languages.catalog import CANONICAL_LANGUAGES_OPERATION_IDS
from cmm.domains.languages.memory import build_languages_memory_proposal
from cmm.domains.languages.operations import (
    assess_sample_result,
    build_languages_operation_definitions,
    create_learning_plan_result,
    generate_conversation_turn_result,
    generate_exercises_result,
    generate_lesson_result,
    generate_progress_review_result,
    generate_roleplay_turn_result,
    plan_review_schedule_result,
    prepare_certification_result,
    review_errors_result,
    review_exercise_result,
    review_speaking_result,
    review_writing_result,
    track_vocabulary_result,
    update_level_evidence_result,
)
from cmm.domains.languages.permissions import (
    build_languages_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.languages.rules import (
    adapt_difficulty,
    classify_language_variety,
    classify_proficiency_record,
    evaluate_certification_source,
    evaluate_error_pattern,
    evaluate_framework_mapping,
    evaluate_language_memory_consent,
    evaluate_level_update,
    evaluate_progression,
)
from cmm.domains.languages.workflows import build_languages_workflow_definitions
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.permission_contracts import (
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowRunStatus

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def test_adversarial_certified_level_overwrite_attempt() -> None:
    """A higher observed sample must NEVER overwrite a certified proficiency record."""
    cert = {"kind": "CERTIFIED", "level_or_score": "B1", "framework": "CEFR", "evidence": [{"id": "c1"}]}
    ass = {"observed_performance": "C2", "skill": "writing"}
    res = update_level_evidence_result(existing_record=cert, assessment=ass, target_skill="writing")
    assert res["is_certified"] is True
    assert res["stable_update_supported"] is False
    assert res["proposed_level"] == "B1"


def test_adversarial_malformed_consent_strings() -> None:
    """String 'true', 'yes', 1, dicts must never authorize persistence."""
    for bad_consent in ("true", "TRUE", "yes", 1, 0, 1.0, {"consent": True}, [True]):
        eval_res = evaluate_language_memory_consent(content_kind="profile", session_only=False, consent=bad_consent)
        assert eval_res["persistence_authorized"] is False
        assert permission_authorization_allows(bad_consent) is False


def test_adversarial_audio_transcript_hallucination_prevention() -> None:
    """Text transcript alone must NEVER claim to have assessed pronunciation."""
    res = review_speaking_result(
        audio_transcript={"transcript": "Every sound was pronounced perfectly."},
        target_language="English",
        pronunciation_evidence=None,
    )
    assert res["pronunciation_assessed"] is False
    assert res["pronunciation_feedback"] is None


def test_adversarial_variety_difference_as_error_rejection() -> None:
    """A valid regional variety difference must never be classified as an error."""
    var_res = classify_language_variety(
        preferred_variety="Mexican Spanish",
        observed_variety="Peninsular Spanish",
        form_status="valid",
    )
    assert var_res["is_valid_alternative"] is True
    assert var_res["error_rejected"] is True


def test_adversarial_one_session_regression_not_stable() -> None:
    """A single bad session must not downgrade stable proficiency."""
    diff_res = adapt_difficulty(current_difficulty=3, performance=[{"score": 0.1}], stable_proficiency="B2")
    assert diff_res["stable_proficiency_changed"] is False
    assert diff_res["action"] != "stable_regression"


def test_adversarial_certification_auto_registration_prevention() -> None:
    """Certification prep must never perform external registration or payment."""
    res = prepare_certification_result(target_certification="DELE C1")
    assert res["registration_performed"] is False
    assert res["payment_performed"] is False
    assert res["submission_performed"] is False


def test_adversarial_unsupported_framework_mapping() -> None:
    """Mapping between unknown or uncalibrated frameworks must return unsupported_framework."""
    res = evaluate_framework_mapping(
        source_framework="UNKNOWN_FRAMEWORK",
        source_value="Level 5",
        target_framework="CEFR",
    )
    assert res["mapping_status"] == "unsupported_framework"
    assert res["calibrated"] is False


def test_certification_requires_grounded_official_credential_evidence() -> None:
    invalid_evidence = (
        {"id": "generic-id"},
        {"provenance_id": "user-sample", "source_kind": "user_sample"},
        {"source_kind": "official_certificate", "certificate_id": "C1"},
    )
    for evidence in invalid_evidence:
        result = classify_proficiency_record(
            kind="CERTIFIED",
            framework="CEFR",
            level_or_score="C1",
            skill_scope="writing",
            evidence=(evidence,),
        )
        assert result["is_certified"] is False

    grounded = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=({"source_kind": "official_certificate", "certificate_id": "C1", "source_id": "official-record"},),
    )
    assert grounded["is_certified"] is True


def test_level_updates_require_distinct_comparable_same_skill_evidence() -> None:
    existing = {"kind": "ESTIMATED", "level_or_score": "B1", "skill_scope": "writing"}
    base = {"observed": "B2", "skill": "writing", "comparable": True, "comparison_key": "essay"}
    duplicated = evaluate_level_update(
        existing=existing,
        target_skill="writing",
        evidence=({**base, "id": "one", "provenance_id": "same"}, {**base, "id": "two", "provenance_id": "same"}),
    )
    assert duplicated["stable_update_supported"] is False

    non_comparable = evaluate_level_update(
        existing=existing,
        target_skill="writing",
        evidence=({**base, "provenance_id": "one"}, {**base, "provenance_id": "two", "comparable": False}),
    )
    assert non_comparable["stable_update_supported"] is False
    for wrong_skill in ("grammar", "speaking"):
        cross_skill = evaluate_level_update(
            existing=existing,
            target_skill="writing",
            evidence=(
                {**base, "provenance_id": "one", "skill": wrong_skill},
                {**base, "provenance_id": "two", "skill": wrong_skill},
            ),
        )
        assert cross_skill["stable_update_supported"] is False


def test_error_patterns_require_independence_and_comparability() -> None:
    one = {"provenance_id": "one", "error_type": "inversion", "comparable": True, "comparison_key": "essay"}
    assert evaluate_error_pattern(observations=(one,))["eligible"] is False
    copied = ({**one, "id": "a"}, {**one, "id": "b"})
    assert evaluate_error_pattern(observations=copied)["eligible"] is False
    non_comparable = (
        one,
        {**one, "provenance_id": "two", "comparable": False},
    )
    assert evaluate_error_pattern(observations=non_comparable)["eligible"] is False
    valid = (one, {**one, "provenance_id": "two"})
    assert evaluate_error_pattern(observations=valid)["pattern_state"] == "candidate"


def test_progression_requires_real_comparable_baseline_and_repetition() -> None:
    baseline = ({"provenance_id": "baseline", "score": 0.6, "skill": "writing", "comparable": True, "comparison_key": "essay"},)
    current = (
        {"provenance_id": "one", "score": 0.85, "skill": "writing", "comparable": True, "comparison_key": "essay"},
        {"provenance_id": "two", "score": 0.88, "skill": "writing", "comparable": True, "comparison_key": "essay"},
    )
    assert evaluate_progression(previous_evidence=(), current_evidence=current, skill="writing")["stable_progression"] is False
    assert evaluate_progression(previous_evidence=baseline, current_evidence=current[:1], skill="writing")["stable_progression"] is False
    incomparable = tuple({**item, "comparable": False} for item in current)
    assert evaluate_progression(previous_evidence=baseline, current_evidence=incomparable, skill="writing")["stable_progression"] is False
    assert evaluate_progression(previous_evidence=baseline, current_evidence=current, skill="writing")["stable_progression"] is True
    poor = ({"provenance_id": "poor", "score": 0.2, "skill": "writing", "comparable": True, "comparison_key": "essay"},)
    assert evaluate_progression(previous_evidence=baseline, current_evidence=poor, skill="writing")["progression_outcome"] != "stable_regression"


def test_certification_temporality_and_readiness_never_upgrade_proficiency() -> None:
    ranked = evaluate_certification_source(
        sources=(
            {"id": "stale", "source_type": "official", "date_valid": False},
            {"id": "current", "source_type": "official", "date_valid": True},
        ),
        decision_critical=True,
    )
    assert ranked["selected_source"]["id"] == "current"
    for source in (
        {"id": "stale", "source_type": "official", "date_valid": False},
        {"id": "unknown", "source_type": "official"},
    ):
        assert evaluate_certification_source(sources=(source,), decision_critical=True)["needs_verification"] is True
    conflict = evaluate_certification_source(
        sources=(
            {"id": "a", "source_type": "official", "date_valid": True, "task_count": 3},
            {"id": "b", "source_type": "official", "date_valid": True, "task_count": 4},
        ), decision_critical=True,
    )
    assert conflict["selected_source"] is None
    assert conflict["needs_verification"] is True
    assert prepare_certification_result(target_certification="C1")["readiness_promoted_to_proficiency"] is False


class _Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"adversarial-workflow-{self.value}"


def _execute_workflow(workflow_id: str, outputs: dict[str, dict]):
    workflow = next(item for item in build_languages_workflow_definitions() if item.workflow_id == workflow_id)

    def adapter(node, run):
        if node.operation_id:
            result = outputs[node.operation_id]
            return NodeExecution.complete(result, operation_result=result)
        return NodeExecution.complete({"ok": True})

    operations = build_languages_operation_definitions()
    context = DomainWorkflowContext(
        primary_domain_id="domain:languages",
        known_domain_ids=frozenset({"domain:languages", "domain:general"}),
        authorized_domain_ids=frozenset({"domain:languages"}),
        available_resources=frozenset(workflow.required_resources),
        available_operations=frozenset(item.operation_id for item in operations),
    )
    return DomainWorkflowExecutor(id_factory=_Ids(), operation_adapter=adapter).execute(
        workflow, context, {"language": "English"}
    )


def test_workflows_accept_legitimate_variable_outcomes_and_reject_mutations() -> None:
    wrong_exercise = review_exercise_result(exercise_result={"is_correct": False, "score": 0.0})
    lesson_run = _execute_workflow(
        "languages.adaptive_language_lesson",
        {
            "languages.generate_lesson": generate_lesson_result(language="English", target_skill="writing", current_level="B1", topic="inversion"),
            "languages.generate_exercises": generate_exercises_result(language="English", skill="grammar", difficulty=2, target_topic="inversion"),
            "languages.review_exercise": wrong_exercise,
        },
    )
    assert lesson_run.status is WorkflowRunStatus.COMPLETED

    a2_writing = review_writing_result(writing_sample={"text": "Short text."})
    assert a2_writing["estimated_level"] == "A2"
    assert _execute_workflow("languages.writing_review", {"languages.review_writing": a2_writing}).status is WorkflowRunStatus.COMPLETED

    recurrent = (
        {"provenance_id": "one", "error_type": "inversion", "comparable": True, "comparison_key": "essay"},
        {"provenance_id": "two", "error_type": "inversion", "comparable": True, "comparison_key": "essay"},
    )
    error_review = review_errors_result(observed_errors=recurrent)
    error_run = _execute_workflow(
        "languages.error_remediation",
        {
            "languages.review_errors": error_review,
            "languages.generate_exercises": generate_exercises_result(language="English", skill="grammar", difficulty=2, target_topic="inversion"),
            "languages.review_exercise": review_exercise_result(exercise_result={"is_correct": True}),
        },
    )
    assert error_review["error_patterns"]
    assert error_run.status is WorkflowRunStatus.COMPLETED

    speaking = review_speaking_result(
        audio_transcript={"transcript": "Hello"},
        pronunciation_evidence=({"source_id": "audio-1", "phoneme": "h"},),
    )
    practice_run = _execute_workflow(
        "languages.conversation_roleplay_practice",
        {
            "languages.generate_conversation_turn": generate_conversation_turn_result(conversation={"turns": ()}),
            "languages.generate_roleplay_turn": generate_roleplay_turn_result(conversation={"turns": ()}),
            "languages.review_speaking": speaking,
        },
    )
    assert speaking["pronunciation_assessed"] is True
    assert practice_run.status is WorkflowRunStatus.COMPLETED

    certification = prepare_certification_result(
        target_certification="C1",
        official_source={"source_type": "official", "date_valid": False},
    )
    assert certification["needs_verification"] is True
    assert _execute_workflow("languages.certification_preparation", {"languages.prepare_certification": certification}).status is WorkflowRunStatus.COMPLETED

    baseline = ({"provenance_id": "baseline", "score": 0.6, "skill": "writing", "comparable": True, "comparison_key": "essay"},)
    current = (
        {"provenance_id": "one", "score": 0.85, "skill": "writing", "comparable": True, "comparison_key": "essay"},
        {"provenance_id": "two", "score": 0.88, "skill": "writing", "comparable": True, "comparison_key": "essay"},
    )
    progress = generate_progress_review_result(language="English", period="month", previous_evidence=baseline, evidence=current, skill="writing")
    assert progress["stable_progression"] is True
    assert _execute_workflow("languages.progress_checkpoint", {"languages.generate_progress_review": progress}).status is WorkflowRunStatus.COMPLETED

    schedule = plan_review_schedule_result(review_items=())
    malicious_schedule = {**schedule, "calendar_modified": True}
    vocab = track_vocabulary_result(vocabulary_list={"items": ()})
    failed_schedule = _execute_workflow(
        "languages.vocabulary_spaced_review",
        {"languages.track_vocabulary": vocab, "languages.plan_review_schedule": malicious_schedule},
    )
    assert failed_schedule.status is WorkflowRunStatus.FAILED

    malicious_certification = {**certification, "registration_performed": True, "payment_performed": True, "submission_performed": True}
    failed_certification = _execute_workflow(
        "languages.certification_preparation",
        {"languages.prepare_certification": malicious_certification},
    )
    assert failed_certification.status is WorkflowRunStatus.FAILED


def _permission_stack():
    registry = DomainPermissionRegistry()
    registry.register(build_languages_permission_policy())
    service = ApprovalService(InMemoryApprovalRepository())
    gate = DomainPermissionGate(DomainPermissionResolver(registry), service, clock=lambda: NOW)
    operation = DomainOperationDefinition(
        operation_id="languages.test_adversarial_memory_write",
        domain_id="domain:languages",
        version="1.0.0",
        name="Adversarial memory boundary",
        description="Test-only shared permission lifecycle operation.",
        operation_type=DomainOperationType.ANALYSIS,
        required_permissions=(PermissionCapability.MEMORY_WRITE.value,),
        risk_level=PolicyRiskLevel.LOW,
        reversible=True,
    )
    return registry, service, gate, operation


def test_memory_write_requires_exact_one_shot_approval_and_proposal_does_not_consume() -> None:
    _, service, gate, operation = _permission_stack()
    kwargs = {"request_id": "adversarial-memory", "actor_id": "actor", "session_id": "session"}
    pending = gate.evaluate_operation_definition(operation, **kwargs)
    assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    requirement = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    approval = service.create_request_from_requirement(
        to_approval_requirement(requirement, agent_run_id="run-adversarial"),
        requested_by="agent-runtime",
    )
    service.approve(approval.id, "human")

    proposal = build_languages_memory_proposal(proposal_id="proposal-adversarial")
    assert proposal.requires_confirmation is True
    assert service.repository.is_consumed(approval.id) is False
    for actor, session in (("wrong", "session"), ("actor", "wrong")):
        denied = gate.evaluate_operation_definition(
            operation,
            request_id="adversarial-memory",
            actor_id=actor,
            session_id=session,
            approval_request_id=approval.id,
        )
        assert denied.outcome is PermissionGateOutcome.APPROVAL_DENIED
        assert service.repository.is_consumed(approval.id) is False

    wrong_scope = service.create_request_from_requirement(
        to_approval_requirement(
            replace(requirement, scope="wrong-scope"),
            agent_run_id="run-wrong-scope",
        ),
        requested_by="agent-runtime",
    )
    service.approve(wrong_scope.id, "human")
    assert gate.evaluate_operation_definition(
        operation, approval_request_id=wrong_scope.id, **kwargs
    ).outcome is PermissionGateOutcome.APPROVAL_DENIED
    assert service.repository.is_consumed(approval.id) is False

    consumed = gate.evaluate_operation_definition(operation, approval_request_id=approval.id, **kwargs)
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert gate.evaluate_operation_definition(operation, approval_request_id=approval.id, **kwargs).outcome is PermissionGateOutcome.APPROVAL_DENIED

    _, expired_service, expired_gate, expired_operation = _permission_stack()
    expired_pending = expired_gate.evaluate_operation_definition(expired_operation, **kwargs)
    expired_requirement = PermissionApprovalRequirement.from_dict(expired_pending.approval_requirements[0])
    expired_approval = expired_service.create_request_from_requirement(
        to_approval_requirement(expired_requirement, agent_run_id="run-expired"), requested_by="agent-runtime"
    )
    expired_service.approve(expired_approval.id, "human")
    stored = expired_service.repository.get_request(expired_approval.id)
    expired_service.repository.update_request(ApprovalRequest.from_mapping({**stored.to_dict(), "expires_at": NOW.replace(year=2025).isoformat()}))
    assert expired_gate.evaluate_operation_definition(
        expired_operation, approval_request_id=expired_approval.id, **kwargs
    ).outcome is PermissionGateOutcome.APPROVAL_DENIED


def test_supporting_domain_cannot_widen_languages_memory_policy() -> None:
    registry = DomainPermissionRegistry()
    registry.register(build_languages_permission_policy())
    registry.register(DomainPermissionPolicy(
        "support-allow", "domain:support", "1.0.0",
        allowed_capabilities=(PermissionCapability.MEMORY_WRITE,),
        allowed_sensitivity_levels=("internal",), allow_memory_write=True,
    ))
    result = DomainPermissionResolver(registry).resolve(
        DomainPermissionRequest(
            "support-cannot-widen", PermissionCapability.MEMORY_WRITE,
            "domain:languages", "actor", "session", sensitivity_level="internal",
        ),
        supporting_domains=("domain:support",), now=NOW,
    )
    assert result.effective_permissions.decision.value == "approval_required"


def test_cross_domain_projection_is_minimal_and_narratives_are_not_level_evidence() -> None:
    allowed = {
        "certification_status": "not_certified",
        "estimated_readiness": "unknown",
        "relevant_proficiency": {},
        "progress_toward_shared_goal": "unknown",
        "recommended_workload": "light",
        "blocking_language_gap": None,
    }
    projection = DomainResult(
        id="adversarial-minimal-projection",
        status="completed",
        objective="Purpose-minimized projection",
        primary_domain="domain:languages",
        supporting_domains=("domain:oppositions",),
        findings=(allowed,),
    ).to_dict()["findings"][0]
    assert set(projection) == set(allowed)
    for provenance_id, source_kind in (
        ("concern-worry", "concern_narrative"),
        ("reflection-identity", "identity_narrative"),
        ("university-requirement", "academic_requirement"),
    ):
        result = classify_proficiency_record(
            kind="CERTIFIED", framework="CEFR", level_or_score="C1", skill_scope="writing",
            evidence=({"provenance_id": provenance_id, "source_kind": source_kind},),
        )
        assert result["is_certified"] is False


def _representative_outputs() -> dict[str, dict]:
    return {
        "languages.assess_sample": assess_sample_result(sample={"text": "A complete writing sample."}),
        "languages.update_level_evidence": update_level_evidence_result(
            existing_record={"kind": "ESTIMATED", "level_or_score": "B1", "skill_scope": "writing"},
            assessment={"provenance_id": "assessment", "observed": "B2", "skill": "writing", "comparable": True, "comparison_key": "essay"},
            target_skill="writing",
        ),
        "languages.create_learning_plan": create_learning_plan_result(language="English", goals=({"target": "C1"},), tracking_consent=True),
        "languages.generate_lesson": generate_lesson_result(language="English", target_skill="writing", current_level="B1", topic="essays"),
        "languages.generate_exercises": generate_exercises_result(language="English", skill="grammar", difficulty=2, target_topic="inversion"),
        "languages.review_exercise": review_exercise_result(exercise_result={"is_correct": False}),
        "languages.review_writing": review_writing_result(writing_sample={"text": "My favourite colour is blue."}, preferred_variety="British English"),
        "languages.generate_conversation_turn": generate_conversation_turn_result(conversation={"turns": ()}),
        "languages.generate_roleplay_turn": generate_roleplay_turn_result(conversation={"turns": ()}),
        "languages.review_speaking": review_speaking_result(audio_transcript={"transcript": "Hello"}),
        "languages.review_errors": review_errors_result(observed_errors=()),
        "languages.track_vocabulary": track_vocabulary_result(vocabulary_list={"items": ()}),
        "languages.plan_review_schedule": plan_review_schedule_result(review_items=()),
        "languages.prepare_certification": prepare_certification_result(target_certification="C1"),
        "languages.generate_progress_review": generate_progress_review_result(language="English", period="month"),
    }


def test_all_operation_schemas_and_workflow_invariant_gates_are_directly_connected() -> None:
    outputs = _representative_outputs()
    definitions = build_languages_operation_definitions()
    assert tuple(item.operation_id for item in definitions) == CANONICAL_LANGUAGES_OPERATION_IDS
    assert set(outputs) == set(CANONICAL_LANGUAGES_OPERATION_IDS)
    for definition in definitions:
        assert validate_operation_schema(outputs[definition.operation_id], definition.output_schema) == ()

    forbidden = {
        "is_correct", "score", "estimated_level", "pattern_candidate",
        "pronunciation_assessed", "needs_verification", "stable_progression",
        "is_certified", "stable_update_supported",
    }
    operations = {item.operation_id: item for item in definitions}
    for workflow in build_languages_workflow_definitions():
        nodes = {item.node_id: item for item in workflow.nodes}
        for node in workflow.nodes:
            if not node.wait_condition:
                continue
            assert forbidden.isdisjoint(node.wait_condition)
            for field_name in node.wait_condition:
                assert any(
                    dependency.operation_id
                    and field_name in operations[dependency.operation_id].output_schema["properties"]
                    for dependency in (nodes[item] for item in node.dependencies)
                )


def test_semantic_rules_are_order_invariant_non_mutating_finite_and_json_safe() -> None:
    observations = [
        {"provenance_id": "one", "error_type": "inversion", "comparable": True, "comparison_key": "essay"},
        {"provenance_id": "two", "error_type": "inversion", "comparable": True, "comparison_key": "essay"},
    ]
    original = copy.deepcopy(observations)
    forward = evaluate_error_pattern(observations=observations)
    reverse = evaluate_error_pattern(observations=list(reversed(observations)))
    assert forward == reverse
    assert observations == original

    baseline = ({"provenance_id": "baseline", "score": 0.5, "skill": "writing", "comparable": True, "comparison_key": "essay"},)
    for invalid in (float("nan"), float("inf"), float("-inf")):
        result = evaluate_progression(
            previous_evidence=baseline,
            current_evidence=(
                {"provenance_id": "one", "score": invalid, "skill": "writing", "comparable": True, "comparison_key": "essay"},
                {"provenance_id": "two", "score": invalid, "skill": "writing", "comparable": True, "comparison_key": "essay"},
            ),
            skill="writing",
        )
        assert result["stable_progression"] is False

    for output in _representative_outputs().values():
        json.dumps(output, allow_nan=False)
