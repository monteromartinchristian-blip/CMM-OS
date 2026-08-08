"""Phase 10.20 — Health safety invariants.

These tests enforce the non-negotiable safety model: Health must NOT
autonomously diagnose, prescribe/change medication, override a clinician,
automatically communicate externally, decide treatment, convert uncertainty
into certainty, or persist sensitive memory outside the proposal/approval
path.
"""

from __future__ import annotations

from cmm.domains import health
from cmm.domains.health.profile import HEALTH_PROHIBITED_ACTIONS


def test_prohibited_actions_cover_the_safety_model():
    required = {
        "definitive_diagnosis",
        "diagnostic_certainty_claim",
        "medication_start",
        "medication_stop",
        "medication_dose_change",
        "medication_substitution",
        "clinician_override",
        "automatic_treatment_decision",
        "automatic_medical_action",
        "automatic_external_communication",
        "sensitive_inference_persist",
        "sensitive_cross_domain_transfer",
        "unconfirmed_sensitive_memory_persistence",
        "export",
        "shell_execution",
    }
    assert required <= set(HEALTH_PROHIBITED_ACTIONS)


def test_prohibited_inferences_no_false_certainty():
    profile = health.build_health_profile()
    assert "definitive_diagnosis" in profile.prohibited_inferences
    assert "causal_claim" in profile.prohibited_inferences
    assert "sensitive_inference" in profile.prohibited_inferences


def test_memory_is_proposal_only():
    profile = health.build_health_profile()
    assert profile.memory_policy.allow_write is False
    assert profile.memory_policy.allow_long_term is False
    assert profile.memory_policy.allow_cross_domain is False
    if hasattr(profile.memory_policy, "proposal_only"):
        assert profile.memory_policy.proposal_only is True
    assert "sensitive_inference_persist" in HEALTH_PROHIBITED_ACTIONS


def test_production_policy_requires_review_and_blocks_final():
    profile = health.build_health_profile()
    assert profile.production_policy.allow_external_action is False
    assert profile.production_policy.require_review is True
    assert profile.production_policy.require_validation is True


def test_temporal_policy_blocks_future_projection():
    profile = health.build_health_profile()
    assert profile.temporal_policy.allow_future_projection is False
    assert profile.temporal_policy.require_current_information is True
    assert profile.temporal_policy.require_temporal_provenance is True


def test_presentation_blocks_speculation_and_requires_disclaimers():
    policy = health.build_health_presentation_policy()
    assert policy.allow_speculation is False
    assert policy.require_disclaimers is True
    assert policy.include_uncertainty is True
    assert policy.include_provenance is True


def test_no_operation_may_grant_medical_decision():
    """No operation type may be a medical action/decision capability."""
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability

    policy = health.build_health_permission_policy()
    assert PermissionCapability.MEDICAL_DECISION not in policy.allowed_capabilities
    assert PermissionCapability.MEDICAL_ACTION not in policy.allowed_capabilities
    assert PermissionCapability.MEDICAL_ACTION in policy.prohibited_capabilities


def test_no_autonomous_external_communication():
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability

    policy = health.build_health_permission_policy()
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.prohibited_capabilities
    assert policy.allow_external_communication is False
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.approval_capabilities


def test_approval_required_for_medical_mutation_operations():
    ops = {op.operation_id: op for op in health.build_health_operation_definitions()}
    assert ops["health.register_symptom_update"].requires_approval is True
    assert ops["health.export_medical_context"].requires_approval is True


def test_medication_only_reviewed_never_modified():
    ops = {op.operation_id: op for op in health.build_health_operation_definitions()}
    review = ops["health.review_medication_changes"]
    # Reviewing is permitted; there is no modify operation at all.
    assert "modify" not in review.operation_id
    assert review.requires_approval is False


def test_all_health_resources_high_sensitivity():
    resources = health.build_health_resource_definitions()
    from cmm.cognitive.enums import SensitivityLevel

    assert all(
        resource.default_sensitivity is SensitivityLevel.HIGHLY_SENSITIVE
        for resource in resources
    )


def test_memory_proposal_requires_confirmation():
    from cmm.domains.health.memory import build_health_symptom_proposal

    proposal = build_health_symptom_proposal(proposal_id="p1")
    assert proposal.requires_confirmation is True
