"""Tests for Phase 10.29 Life Plan Domain Profile."""

from __future__ import annotations

from cmm.domains.identifiers import DomainId
from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_RULE_IDS,
    LIFE_PLAN_RESOURCE_KINDS,
)
from cmm.domains.life_plan.profile import (
    LIFE_PLAN_PROFILE_ID,
    LIFE_PLAN_PROFILE_NAME,
    LIFE_PLAN_PROHIBITED_ACTIONS,
    build_life_plan_profile,
)
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry


def test_life_plan_profile_identity() -> None:
    profile = build_life_plan_profile()
    assert profile.id == LIFE_PLAN_PROFILE_ID
    assert profile.id == "life-plan.profile"
    assert profile.profile_name == LIFE_PLAN_PROFILE_NAME
    assert profile.profile_name == "LifePlanProfile"
    assert str(profile.domain_id) == "domain:life-plan"
    assert profile.required_rules == CANONICAL_LIFE_PLAN_RULE_IDS
    assert profile.allowed_resource_kinds == LIFE_PLAN_RESOURCE_KINDS


def test_life_plan_profile_prohibitions_and_invariants() -> None:
    profile = build_life_plan_profile()
    assert "direct_memory_write" in profile.prohibited_actions
    assert "silent_memory_persistence" in profile.prohibited_actions
    assert "automatic_goal_abandonment" in profile.prohibited_actions
    assert "unconfirmed_decision_promotion" in profile.prohibited_actions
    assert "payment" in profile.prohibited_actions
    assert profile.prohibited_actions == LIFE_PLAN_PROHIBITED_ACTIONS

    assert "unconfirmed_decision_promotion" in profile.prohibited_inferences
    assert "automatic_goal_abandonment" in profile.prohibited_inferences

    assert profile.presentation_policy.include_uncertainty is True
    assert profile.presentation_policy.include_provenance is True
    assert profile.presentation_policy.include_alternatives is True
    assert profile.presentation_policy.allow_speculation is False

    assert profile.memory_policy.allow_read is True
    assert profile.memory_policy.allow_write is None or profile.memory_policy.allow_write is False
    assert profile.production_policy.allow_external_action is False


def test_life_plan_profile_registers_in_profile_registry() -> None:
    registry = InMemoryDomainProfileRegistry()
    profile = build_life_plan_profile()
    registry.register(profile)
    retrieved = registry.get(LIFE_PLAN_PROFILE_ID)
    assert retrieved is profile
    retrieved_by_domain = registry.get_by_domain(DomainId("life-plan"))
    assert retrieved_by_domain is profile
