"""Phase 10.22 — University safety invariants.

These tests enforce the non-negotiable safety model: University must NOT send
email, submit formal procedures, modify the official academic record, infer
intellectual capacity from observed performance, adopt an academic decision,
mutate calendar/tasks autonomously, or persist sensitive memory outside the
proposal/approval path.  Academic State is never overridden by Personal Memory.
"""

from __future__ import annotations

from cmm.domains import university
from cmm.domains.university.profile import UNIVERSITY_PROHIBITED_ACTIONS


def test_prohibited_actions_cover_the_safety_model():
    required = {
        "email_sending",
        "email_authorization",
        "formal_procedure_submission",
        "enrollment_registration",
        "official_record_modification",
        "official_record_write",
        "calendar_event_creation",
        "task_creation",
        "schedule_modification",
        "capacity_inference_from_performance",
        "intellectual_capacity_inference",
        "performance_as_capacity",
        "academic_decision_adoption",
        "academic_decision_execution",
        "sensitive_inference_persist",
        "sensitive_cross_domain_transfer",
        "unconfirmed_sensitive_memory_persistence",
        "export",
        "shell_execution",
    }
    assert required <= set(UNIVERSITY_PROHIBITED_ACTIONS)


def test_prohibited_inferences_no_capacity_inference():
    profile = university.build_university_profile()
    assert "capacity_inference" in profile.prohibited_inferences
    assert "intellectual_capacity" in profile.prohibited_inferences
    assert "academic_decision_adoption" in profile.prohibited_inferences
    assert "sensitive_inference" in profile.prohibited_inferences


def test_memory_is_proposal_only():
    profile = university.build_university_profile()
    assert profile.memory_policy.allow_write is False
    assert profile.memory_policy.allow_long_term is False
    assert profile.memory_policy.allow_cross_domain is False
    assert "sensitive_inference_persist" in UNIVERSITY_PROHIBITED_ACTIONS


def test_production_policy_requires_review_and_blocks_final():
    profile = university.build_university_profile()
    assert profile.production_policy.allow_external_action is False
    assert profile.production_policy.require_review is True
    assert profile.production_policy.require_validation is True
    assert profile.production_policy.allow_final is False


def test_temporal_policy_blocks_future_projection():
    profile = university.build_university_profile()
    assert profile.temporal_policy.allow_future_projection is False
    assert profile.temporal_policy.require_current_information is True
    assert profile.temporal_policy.require_temporal_provenance is True


def test_presentation_blocks_speculation_and_requires_disclaimers():
    policy = university.build_university_presentation_policy()
    assert policy.allow_speculation is False
    assert policy.require_disclaimers is True
    assert policy.include_uncertainty is True
    assert policy.include_provenance is True


def test_no_operation_grant_academic_external_capability():
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability

    policy = university.build_university_permission_policy()
    assert (
        PermissionCapability.COMMUNICATION_EXTERNAL not in policy.allowed_capabilities
    )
    assert PermissionCapability.EXPORT not in policy.allowed_capabilities
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.prohibited_capabilities


def test_no_autonomous_external_communication_or_calendar():
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability

    policy = university.build_university_permission_policy()
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.prohibited_capabilities
    assert policy.allow_external_communication is False
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.approval_capabilities
    assert PermissionCapability.SCHEDULE_MODIFY in policy.prohibited_capabilities
    assert PermissionCapability.TASK_CREATE in policy.prohibited_capabilities


def test_prepare_exam_is_preparation_not_send():
    from cmm.domains.enums import DomainOperationType

    ops = {
        op.operation_id: op
        for op in university.build_university_operation_definitions()
    }
    prepare = ops["university.prepare_exam"]
    assert prepare.operation_type is DomainOperationType.PREPARATION
    for op in university.build_university_operation_definitions():
        assert op.operation_type is not DomainOperationType.EXTERNAL
        assert op.operation_type is not DomainOperationType.DESTRUCTIVE
        for word in ("send", "submit", "contact", "message"):
            assert word not in op.operation_id


def test_update_subject_status_internal_only():
    """update_subject_status is MEMORY (INTERNAL Academic State), never an
    official record or calendar mutation."""
    from cmm.domains.enums import DomainOperationType

    ops = {
        op.operation_id: op
        for op in university.build_university_operation_definitions()
    }
    status = ops["university.update_subject_status"]
    assert status.operation_type is DomainOperationType.MEMORY
    # The output schema cannot authorize official-record mutation.
    inner = status.output_schema["properties"]["status"]["properties"]
    assert "official_record_untouched" in inner
    assert "internal_academic_state_only" in inner


def test_no_autonomous_academic_action_operation():
    op_ids = {
        op.operation_id
        for op in university.build_university_operation_definitions()
    }
    assert not any(
        word in op
        for op in op_ids
        for word in ("send", "submit", "enrol", "register", "write_record")
    )


def test_memory_proposal_requires_confirmation():
    from cmm.domains.university.memory import build_university_memory_proposal

    proposal = build_university_memory_proposal(proposal_id="p1")
    assert proposal.requires_confirmation is True


def test_decision_support_never_adopts():
    """Decision support compares options but never adopts an academic decision."""
    from datetime import datetime, timezone

    from cmm.cognitive.enums import ReasoningRuleResultStatus
    from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext

    rules = {
        rule.definition.id: rule
        for rule in university.build_university_rules()
    }
    rule = rules["university.academic_decision_preservation"]
    result = rule.evaluate(
        ReasoningRuleContext(
            reasoning_id="rid",
            timestamp=datetime(2026, 8, 1, tzinfo=timezone.utc),
            active_domains=("domain:university",),
            primary_domain="domain:university",
            metadata={"decision_support": {"options": (1, 2), "criteria": ("x",)}},
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "DECISION_NOT_ADOPTED"
        and finding.metadata["adopted_decision"] is False
        for finding in result.findings
    )