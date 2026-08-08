"""Phase 10.21 — Relationships safety invariants.

These tests enforce the non-negotiable safety model: Relationships must NOT
autonomously diagnose a third party, attribute intent as fact without direct
evidence, collapse ambivalence, adopt a relational decision, modify/enforce a
boundary, contact or communicate with another person automatically, or persist
sensitive memory outside the proposal/approval path.
"""

from __future__ import annotations

from cmm.domains import relationships
from cmm.domains.relationships.profile import RELATIONSHIPS_PROHIBITED_ACTIONS


def test_prohibited_actions_cover_the_safety_model():
    required = {
        "third_party_diagnosis",
        "third_party_psychiatric_diagnosis",
        "personality_disorder_attribution",
        "intent_attribution_as_fact",
        "mind_reading_as_fact",
        "relational_decision_adoption",
        "relational_decision_execution",
        "boundary_modification",
        "boundary_enforcement",
        "boundary_communication",
        "automatic_external_communication",
        "contact_initiation",
        "message_sending",
        "relationship_end",
        "relationship_resume",
        "relationship_distance",
        "reconciliation_initiation",
        "sensitive_inference_persist",
        "sensitive_cross_domain_transfer",
        "unconfirmed_sensitive_memory_persistence",
        "ambivalence_resolution",
        "export",
        "shell_execution",
    }
    assert required <= set(RELATIONSHIPS_PROHIBITED_ACTIONS)


def test_prohibited_inferences_no_intent_as_fact():
    profile = relationships.build_relationships_profile()
    assert "intent_as_fact" in profile.prohibited_inferences
    assert "third_party_diagnosis" in profile.prohibited_inferences
    assert "psychological_cause" in profile.prohibited_inferences
    assert "sensitive_inference" in profile.prohibited_inferences


def test_memory_is_proposal_only():
    profile = relationships.build_relationships_profile()
    assert profile.memory_policy.allow_write is False
    assert profile.memory_policy.allow_long_term is False
    assert profile.memory_policy.allow_cross_domain is False
    if hasattr(profile.memory_policy, "proposal_only"):
        assert profile.memory_policy.proposal_only is True
    assert "sensitive_inference_persist" in RELATIONSHIPS_PROHIBITED_ACTIONS


def test_production_policy_requires_review_and_blocks_final():
    profile = relationships.build_relationships_profile()
    assert profile.production_policy.allow_external_action is False
    assert profile.production_policy.require_review is True
    assert profile.production_policy.require_validation is True
    assert profile.production_policy.allow_final is False


def test_temporal_policy_blocks_future_projection():
    profile = relationships.build_relationships_profile()
    assert profile.temporal_policy.allow_future_projection is False
    assert profile.temporal_policy.require_current_information is True
    assert profile.temporal_policy.require_temporal_provenance is True


def test_presentation_blocks_speculation_and_requires_disclaimers():
    policy = relationships.build_relationships_presentation_policy()
    assert policy.allow_speculation is False
    assert policy.require_disclaimers is True
    assert policy.include_uncertainty is True
    assert policy.include_provenance is True


def test_no_operation_may_grant_relational_decision():
    """No operation type may be an external/decision capability."""
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability

    policy = relationships.build_relationships_permission_policy()
    assert (
        PermissionCapability.COMMUNICATION_EXTERNAL not in policy.allowed_capabilities
    )
    assert PermissionCapability.EXPORT not in policy.allowed_capabilities
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.prohibited_capabilities


def test_no_autonomous_external_communication():
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability

    policy = relationships.build_relationships_permission_policy()
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.prohibited_capabilities
    assert policy.allow_external_communication is False
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.approval_capabilities


def test_prepare_conversation_is_preparation_not_send():
    """prepare_conversation prepares material; it is never an EXTERNAL/send
    operation, and there is no send/contact/message operation anywhere."""
    from cmm.domains.enums import DomainOperationType

    ops = {
        op.operation_id: op
        for op in relationships.build_relationships_operation_definitions()
    }
    prepare = ops["relationships.prepare_conversation"]
    assert prepare.operation_type is DomainOperationType.PREPARATION
    assert prepare.requires_approval is True
    for op in relationships.build_relationships_operation_definitions():
        assert op.operation_type is not DomainOperationType.EXTERNAL
        assert "send" not in op.operation_id
        assert "contact" not in op.operation_id
        assert "message" not in op.operation_id


def test_boundary_only_reviewed_never_acted():
    """Boundaries are reviewed, never modified/enforced/communicated/withdrawn."""
    ops = {
        op.operation_id: op
        for op in relationships.build_relationships_operation_definitions()
    }
    review = ops["relationships.review_boundaries"]
    assert "review" in review.operation_id
    assert review.operation_id == "relationships.review_boundaries"
    op_ids = {
        op.operation_id
        for op in relationships.build_relationships_operation_definitions()
    }
    assert not any(
        "modify" in op or "enforce" in op or "communicate" in op or "withdraw" in op
        for op in op_ids
    )


def test_no_decision_adoption_operation():
    """No operation adopts, executes, or ends a relational decision."""
    op_ids = {
        op.operation_id
        for op in relationships.build_relationships_operation_definitions()
    }
    assert not any(
        "adopt" in op or "execute" in op or "end" in op or "resume" in op
        for op in op_ids
    )


def test_all_relationships_resources_high_sensitivity():
    resources = relationships.build_relationships_resource_definitions()
    from cmm.cognitive.enums import SensitivityLevel

    assert all(
        resource.default_sensitivity is SensitivityLevel.HIGHLY_SENSITIVE
        for resource in resources
    )


def test_memory_proposal_requires_confirmation():
    from cmm.domains.relationships.memory import build_relationships_memory_proposal

    proposal = build_relationships_memory_proposal(proposal_id="p1")
    assert proposal.requires_confirmation is True


def test_decision_support_never_adopts():
    """Decision Support Mode A compares options but never adopts a decision."""
    from cmm.domains.relationships.rules import compare_relationship_options

    comparison = compare_relationship_options(
        options=[{"id": "opt-a", "criteria": ("clarity",)}],
        criteria=("clarity",),
    )
    assert comparison["adopted_decision"] is False
    assert comparison["requires_user_confirmation"] is True
