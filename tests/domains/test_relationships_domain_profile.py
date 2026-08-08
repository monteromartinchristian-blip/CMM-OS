"""Tests for Phase 10.21 Relationships Domain profile."""

from __future__ import annotations

from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.relationships.profile import (
    RELATIONSHIPS_PROFILE_ID,
    RELATIONSHIPS_PROFILE_NAME,
    build_relationships_profile,
)


def test_profile_identity():
    profile = build_relationships_profile()
    assert profile.id == RELATIONSHIPS_PROFILE_ID
    assert profile.profile_name == RELATIONSHIPS_PROFILE_NAME
    assert profile.domain_id == "domain:relationships"


def test_required_rules_match_catalog():
    from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_RULE_IDS

    profile = build_relationships_profile()
    assert profile.required_rules == CANONICAL_RELATIONSHIPS_RULE_IDS
    assert len(profile.required_rules) == 8


def test_profile_is_conservative():
    profile = build_relationships_profile()
    assert profile.minimum_confidence >= 0.7
    assert profile.reasoning_depth is DomainReasoningDepth.STANDARD
    assert profile.allowed_inferences
    assert "intent_as_fact" in profile.prohibited_inferences
    assert "third_party_diagnosis" in profile.prohibited_inferences


def test_escalation_rules_present():
    profile = build_relationships_profile()
    assert "relationships.self_other_perspective" in profile.escalation_rules
    assert "relationships.do_not_infer_intent" in profile.escalation_rules


def test_resource_kinds_match_catalog():
    from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_RESOURCE_IDS

    profile = build_relationships_profile()
    expected_kinds = tuple(
        resource_id.split(".", 1)[1]
        for resource_id in CANONICAL_RELATIONSHIPS_RESOURCE_IDS
    )
    assert profile.allowed_resource_kinds == expected_kinds
