"""Tests for Phase 10.20 Health Domain profile."""

from __future__ import annotations

from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.health.profile import (
    HEALTH_PROFILE_ID,
    HEALTH_PROFILE_NAME,
    build_health_profile,
)


def test_profile_identity():
    profile = build_health_profile()
    assert profile.id == HEALTH_PROFILE_ID
    assert profile.profile_name == HEALTH_PROFILE_NAME
    assert profile.domain_id == "domain:health"


def test_required_rules_match_catalog():
    from cmm.domains.health.catalog import CANONICAL_HEALTH_RULE_IDS

    profile = build_health_profile()
    assert profile.required_rules == CANONICAL_HEALTH_RULE_IDS
    assert len(profile.required_rules) == 8


def test_profile_is_conservative():
    profile = build_health_profile()
    assert profile.minimum_confidence >= 0.7
    assert profile.reasoning_depth is DomainReasoningDepth.STANDARD
    assert profile.allowed_inferences
    assert "definitive_diagnosis" in profile.prohibited_inferences


def test_escalation_rules_present():
    profile = build_health_profile()
    assert "health.professional_escalation" in profile.escalation_rules
    assert "health.medical_red_flag" in profile.escalation_rules


def test_resource_kinds_match_catalog():
    from cmm.domains.health.catalog import CANONICAL_HEALTH_RESOURCE_IDS

    profile = build_health_profile()
    expected_kinds = tuple(
        resource_id.split(".", 1)[1] for resource_id in CANONICAL_HEALTH_RESOURCE_IDS
    )
    assert profile.allowed_resource_kinds == expected_kinds
