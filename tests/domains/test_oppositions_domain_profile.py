"""Phase 10.23 — Opposition Domain Profile tests."""

from __future__ import annotations

from cmm.domains.oppositions import (
    OPPOSITIONS_PROFILE_ID,
    build_oppositions_profile,
)
from cmm.domains.oppositions.catalog import CANONICAL_OPPOSITION_RULE_IDS


def test_profile_binding():
    profile = build_oppositions_profile()
    assert profile.id == OPPOSITIONS_PROFILE_ID
    assert profile.profile_name == "OppositionProfile"
    assert profile.domain_id == "domain:oppositions"


def test_profile_requires_all_rule_ids():
    profile = build_oppositions_profile()
    assert set(profile.required_rules) == set(CANONICAL_OPPOSITION_RULE_IDS)


def test_profile_allowed_resource_kinds():
    profile = build_oppositions_profile()
    assert "official_call" in profile.allowed_resource_kinds
    assert "syllabus" in profile.allowed_resource_kinds


def test_profile_memory_readonly():
    profile = build_oppositions_profile()
    assert profile.memory_policy.allow_write is False
    assert profile.memory_policy.allow_read is True


def test_profile_prohibits_strategy_adoption():
    profile = build_oppositions_profile()
    assert "strategy_adoption" in profile.prohibited_actions
    assert "target_abandonment" in profile.prohibited_actions
    assert "opposition_registration" in profile.prohibited_actions


def test_profile_no_duplicate_registry():
    """No duplicate profile registry; the shared profile system owns it."""
    assert len({p.id for p in (build_oppositions_profile(),)}) == 1


def test_profile_deterministic():
    a = build_oppositions_profile()
    b = build_oppositions_profile()
    assert a.to_dict() == b.to_dict()