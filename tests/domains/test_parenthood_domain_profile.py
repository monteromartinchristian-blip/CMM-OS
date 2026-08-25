"""Tests for Phase 10.27 Parenthood Domain Profile."""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.parenthood.catalog import CANONICAL_PARENTHOOD_RULE_IDS, PARENTHOOD_RESOURCE_KINDS
from cmm.domains.parenthood.profile import (
    PARENTHOOD_FUNCTIONAL_SCOPES,
    PARENTHOOD_PROFILE_ID,
    PARENTHOOD_PROFILE_NAME,
    PARENTHOOD_PROHIBITED_ACTIONS,
    build_parenthood_profile,
)


def test_parenthood_profile_constants() -> None:
    """Verify profile identity constants."""
    assert PARENTHOOD_PROFILE_ID == "parenthood.profile"
    assert PARENTHOOD_PROFILE_NAME == "ParenthoodProfile"
    assert PARENTHOOD_FUNCTIONAL_SCOPES == ("parenthood.journey", "parenthood.child")


def test_parenthood_profile_construction() -> None:
    """Verify deterministic build of ParenthoodProfile."""
    profile = build_parenthood_profile()
    assert profile.id == PARENTHOOD_PROFILE_ID
    assert profile.domain_id == "domain:parenthood"
    assert profile.profile_name == PARENTHOOD_PROFILE_NAME
    assert profile.required_rules == CANONICAL_PARENTHOOD_RULE_IDS
    assert profile.allowed_resource_kinds == PARENTHOOD_RESOURCE_KINDS
    assert profile.minimum_confidence >= 0.7
    assert profile.reasoning_depth is DomainReasoningDepth.STANDARD


def test_parenthood_profile_prohibited_actions() -> None:
    """Verify safety-critical actions are explicitly prohibited."""
    profile = build_parenthood_profile()
    expected_prohibitions = (
        "direct_memory_write",
        "silent_memory_persistence",
        "external_communication",
        "child_enrollment",
        "contracting",
        "payment",
        "consent",
        "legal_commitment",
        "medical_decision",
        "legal_decision",
        "financial_decision",
        "high_impact_parental_decision",
    )
    for action in expected_prohibitions:
        assert action in profile.prohibited_actions
        assert action in PARENTHOOD_PROHIBITED_ACTIONS


def test_parenthood_profile_inferences() -> None:
    """Verify allowed and prohibited inference boundaries."""
    profile = build_parenthood_profile()
    assert "journey_dependency" in profile.allowed_inferences
    assert "pathway_comparison" in profile.allowed_inferences
    assert "developmental_context" in profile.allowed_inferences
    assert "sibling_specific_context" in profile.allowed_inferences
    assert "transfer_candidate" in profile.allowed_inferences

    assert "inferred_parental_decision_as_adopted" in profile.prohibited_inferences
    assert "cross_sibling_identity_merge" in profile.prohibited_inferences
    assert "medical_diagnosis_from_parenting_context" in profile.prohibited_inferences
    assert "legal_conclusion_without_current_verification" in profile.prohibited_inferences
    assert "journey_history_auto_transfer" in profile.prohibited_inferences
    assert "silent_memory_persistence" in profile.prohibited_inferences


def test_parenthood_profile_policies() -> None:
    """Verify memory, temporal, and production policies."""
    profile = build_parenthood_profile()

    # Memory policy
    assert profile.memory_policy.allow_read is True
    assert profile.memory_policy.allow_write is not True  # None or False (fail-closed)
    assert profile.memory_policy.allow_cross_domain is False
    assert profile.memory_policy.sensitivity_limit == SensitivityLevel.SENSITIVE

    # Temporal policy
    assert profile.temporal_policy.require_current_information is True
    assert profile.temporal_policy.require_temporal_provenance is True

    # Production policy
    assert profile.production_policy.allow_draft is True
    assert profile.production_policy.allow_final is False
    assert profile.production_policy.allow_external_action is False
    assert profile.production_policy.require_review is True
    assert profile.production_policy.require_validation is True
