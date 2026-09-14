"""Tests for Phase 10.22 University Domain profile."""

from __future__ import annotations

from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.university.profile import (
    UNIVERSITY_PROFILE_ID,
    UNIVERSITY_PROFILE_NAME,
    build_university_profile,
)


def test_profile_identity():
    profile = build_university_profile()
    assert profile.id == UNIVERSITY_PROFILE_ID
    assert profile.profile_name == UNIVERSITY_PROFILE_NAME
    assert profile.domain_id == "domain:university"


def test_required_rules_match_catalog():
    from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RULE_IDS

    profile = build_university_profile()
    assert profile.required_rules == CANONICAL_UNIVERSITY_RULE_IDS
    assert len(profile.required_rules) == 10


def test_profile_is_conservative():
    profile = build_university_profile()
    assert profile.minimum_confidence >= 0.7
    assert profile.reasoning_depth is DomainReasoningDepth.STANDARD
    assert profile.allowed_inferences
    assert "capacity_inference" in profile.prohibited_inferences
    assert "intellectual_capacity" in profile.prohibited_inferences
    assert "academic_decision_adoption" in profile.prohibited_inferences


def test_escalation_rules_present():
    profile = build_university_profile()
    assert "university.academic_source_authority" in profile.escalation_rules
    assert "university.observed_performance_capacity" in profile.escalation_rules
    assert "university.academic_integrity" in profile.escalation_rules


def test_resource_kinds_match_catalog():
    from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RESOURCE_IDS

    profile = build_university_profile()
    expected_kinds = tuple(
        resource_id.split(".", 1)[1]
        for resource_id in CANONICAL_UNIVERSITY_RESOURCE_IDS
    )
    assert profile.allowed_resource_kinds == expected_kinds


def test_prohibited_actions_include_email_submit_capacity():
    """The profile forbids email sending, procedure submission, record
    modification, and capacity inference."""
    profile = build_university_profile()
    for action in (
        "email_sending",
        "formal_procedure_submission",
        "official_record_modification",
        "capacity_inference_from_performance",
        "intellectual_capacity_inference",
        "academic_decision_adoption",
        "calendar_event_creation",
        "task_creation",
    ):
        assert action in profile.prohibited_actions


def test_memory_policy_read_only():
    profile = build_university_profile()
    assert profile.memory_policy.allow_write is False
    assert profile.memory_policy.allow_read is True


def test_production_policy_no_external_action():
    profile = build_university_profile()
    assert profile.production_policy.allow_external_action is False
    assert profile.production_policy.allow_final is False
