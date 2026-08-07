"""Tests for General Domain profile."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.general import (
    GENERAL_PROFILE_ID,
    GENERAL_PROFILE_NAME,
    GENERAL_PROHIBITED_ACTIONS,
    build_general_profile,
)
from cmm.domains.profile_contracts import DomainProfileDefinition


def test_profile_id():
    profile = build_general_profile()
    assert profile.id == GENERAL_PROFILE_ID


def test_profile_name():
    profile = build_general_profile()
    assert profile.profile_name == GENERAL_PROFILE_NAME


def test_profile_domain():
    profile = build_general_profile()
    assert profile.domain_id.slug == "general"


def test_profile_required_rules():
    profile = build_general_profile()
    assert profile.required_rules == (
        "general.temporal_validity",
        "general.source_reliability",
        "general.ambiguity",
        "general.permission",
        "general.goal_clarification",
        "general.duplication",
    )


def test_profile_allowed_resources():
    profile = build_general_profile()
    assert profile.allowed_resource_kinds is not None
    assert len(profile.allowed_resource_kinds) == 9


def test_profile_minimum_confidence():
    profile = build_general_profile()
    assert profile.minimum_confidence == 0.55


def test_profile_reasoning_depth():
    profile = build_general_profile()
    assert profile.reasoning_depth is DomainReasoningDepth.STANDARD


def test_profile_maximum_questions():
    profile = build_general_profile()
    assert profile.maximum_questions == 8


def test_profile_prohibited_actions():
    profile = build_general_profile()
    assert profile.prohibited_actions == GENERAL_PROHIBITED_ACTIONS


def test_profile_memory_policy():
    profile = build_general_profile()
    assert profile.memory_policy.allow_read is True
    assert profile.memory_policy.allow_write is False


def test_profile_production_policy():
    profile = build_general_profile()
    assert profile.production_policy.allow_external_action is False
    assert profile.production_policy.require_review is True
    assert profile.production_policy.require_validation is True


def test_profile_question_policy():
    profile = build_general_profile()
    assert profile.question_policy.maximum_questions == 8
    assert profile.question_policy.require_deduplication is True
    assert profile.question_policy.stop_on_blocking_gap is True


def test_profile_serialization_round_trip():
    profile = build_general_profile()
    restored = DomainProfileDefinition.from_dict(profile.to_dict())
    assert restored == profile


def test_profile_is_frozen():
    profile = build_general_profile()
    with pytest.raises(FrozenInstanceError):
        profile.profile_name = "changed"  # type: ignore[misc]


def test_profile_deterministic():
    a = build_general_profile()
    b = build_general_profile()
    assert a == b
    assert a.to_dict() == b.to_dict()


def test_profile_can_be_registered():
    from cmm.domains.profile_registry import InMemoryDomainProfileRegistry

    registry = InMemoryDomainProfileRegistry()
    profile = build_general_profile()
    registered = registry.register(profile)
    assert registered == profile
    assert registry.get(GENERAL_PROFILE_ID) == profile