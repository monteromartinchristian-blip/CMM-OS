"""Tests for Phase 10.53 Neurodivergence Domain canonical contracts.

Task 1: canonical inventory (catalog), resources and exploration-friendly
profile.
Task 2: epistemic rules — exploratory inference allowed, diagnostic promotion
blocked, certainty hierarchy preserved.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext

T = datetime(2026, 9, 1, tzinfo=timezone.utc)

EXPECTED_RESOURCES = (
    "neurodivergence.developmental_history",
    "neurodivergence.assessment_records",
    "neurodivergence.psychometric_results",
    "neurodivergence.executive_function_context",
    "neurodivergence.sensory_context",
    "neurodivergence.academic_function_context",
    "neurodivergence.social_function_context",
    "neurodivergence.functional_impact",
    "neurodivergence.longitudinal_evidence",
    "neurodivergence.differential_overlap_context",
)

EXPECTED_RULES = (
    "neurodivergence.certainty_state_preservation",
    "neurodivergence.clinical_status_authority",
    "neurodivergence.source_authority",
    "neurodivergence.developmental_temporality",
    "neurodivergence.observation_report_separation",
    "neurodivergence.screening_diagnosis_separation",
    "neurodivergence.trait_function_separation",
    "neurodivergence.longitudinal_corroboration",
    "neurodivergence.contradiction_preservation",
    "neurodivergence.differential_explanations",
    "neurodivergence.overlap_reasoning",
    "neurodivergence.purpose_minimized_cross_domain",
    "neurodivergence.global_attribution_guard",
    "neurodivergence.sensitive_label_persistence",
)

EXPECTED_OPERATIONS = (
    "neurodivergence.analyze_differential_overlap",
    "neurodivergence.build_developmental_timeline",
    "neurodivergence.compare_assessment_sources",
    "neurodivergence.map_certainty_states",
    "neurodivergence.prepare_assessment_summary",
    "neurodivergence.propose_memory_update",
    "neurodivergence.review_evidence",
    "neurodivergence.review_functional_impact",
)

EXPECTED_WORKFLOWS = (
    "neurodivergence.developmental_history_review",
    "neurodivergence.evidence_consolidation_review",
    "neurodivergence.diagnostic_status_review",
    "neurodivergence.neuropsychological_assessment_preparation",
    "neurodivergence.assessment_result_integration",
    "neurodivergence.differential_overlap_review",
    "neurodivergence.functional_impact_review",
    "neurodivergence.sensitive_memory_proposal_review",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Task 1 — canonical identity, resources, exploration-friendly profile
# ═══════════════════════════════════════════════════════════════════════════════


def test_neurodivergence_canonical_identity_is_frozen():
    from cmm.domains.neurodivergence.catalog import (
        NEURODIVERGENCE_DOMAIN_ID,
        NEURODIVERGENCE_OPERATION_IDS,
        NEURODIVERGENCE_PROFILE_NAME,
        NEURODIVERGENCE_RESOURCE_IDS,
        NEURODIVERGENCE_RULE_IDS,
        NEURODIVERGENCE_WORKFLOW_IDS,
    )

    assert NEURODIVERGENCE_DOMAIN_ID == "domain:neurodivergence"
    assert NEURODIVERGENCE_PROFILE_NAME == "NeurodivergenceProfile"
    assert NEURODIVERGENCE_RESOURCE_IDS == EXPECTED_RESOURCES
    assert NEURODIVERGENCE_RULE_IDS == EXPECTED_RULES
    assert NEURODIVERGENCE_OPERATION_IDS == EXPECTED_OPERATIONS
    assert NEURODIVERGENCE_WORKFLOW_IDS == EXPECTED_WORKFLOWS
    assert len(NEURODIVERGENCE_RESOURCE_IDS) == 10
    assert len(NEURODIVERGENCE_RULE_IDS) == 14
    assert len(NEURODIVERGENCE_OPERATION_IDS) == 8
    assert len(NEURODIVERGENCE_WORKFLOW_IDS) == 8


def test_neurodivergence_inventories_are_unique_and_namespaced():
    from cmm.domains.neurodivergence.catalog import (
        NEURODIVERGENCE_OPERATION_IDS,
        NEURODIVERGENCE_RESOURCE_IDS,
        NEURODIVERGENCE_RULE_IDS,
        NEURODIVERGENCE_WORKFLOW_IDS,
    )

    for inventory in (
        NEURODIVERGENCE_RESOURCE_IDS,
        NEURODIVERGENCE_RULE_IDS,
        NEURODIVERGENCE_OPERATION_IDS,
        NEURODIVERGENCE_WORKFLOW_IDS,
    ):
        assert len(inventory) == len(set(inventory))
        assert all(item.startswith("neurodivergence.") for item in inventory)


def test_neurodivergence_resources_are_sensitive_and_temporal():
    from cmm.domains.neurodivergence.resources import (
        build_neurodivergence_resource_definitions,
    )

    resources = build_neurodivergence_resource_definitions()
    assert len(resources) == 10
    for resource in resources:
        assert resource.domain_id == "domain:neurodivergence"
        assert resource.default_sensitivity is SensitivityLevel.SENSITIVE
        assert resource.temporal_policy.historical_allowed is True


def test_neurodivergence_resource_kinds_match_the_frozen_catalog():
    from cmm.domains.neurodivergence.catalog import NEURODIVERGENCE_RESOURCE_IDS
    from cmm.domains.neurodivergence.resources import (
        NEURODIVERGENCE_RESOURCE_KINDS,
        build_neurodivergence_resource_definitions,
    )

    assert NEURODIVERGENCE_RESOURCE_KINDS == tuple(
        resource_id.split(".", 1)[1] for resource_id in NEURODIVERGENCE_RESOURCE_IDS
    )
    assert (
        tuple(
            resource.kind for resource in build_neurodivergence_resource_definitions()
        )
        == NEURODIVERGENCE_RESOURCE_KINDS
    )


def test_resource_metadata_carries_references_never_raw_source_bodies():
    """Metadata may declare provenance requirements; never a source body."""
    from cmm.domains.neurodivergence.resources import (
        build_neurodivergence_resource_definitions,
    )

    forbidden_keys = {
        "body",
        "content",
        "text",
        "transcript",
        "raw_text",
        "source_body",
        "payload",
        "report_text",
    }
    for resource in build_neurodivergence_resource_definitions():
        assert forbidden_keys.isdisjoint(resource.metadata)
        for value in resource.metadata.values():
            if isinstance(value, str):
                assert len(value) <= 120


def test_cross_domain_projection_resources_declare_their_source_domain():
    """Imported context stays source-owned and read-only."""
    from cmm.domains.neurodivergence.resources import (
        build_neurodivergence_resource_definitions,
    )

    projections = {
        resource.kind: resource
        for resource in build_neurodivergence_resource_definitions()
        if resource.metadata.get("cross_domain_projection") is True
    }
    assert projections, "expected authorized source-domain projections"
    for resource in projections.values():
        assert resource.metadata["read_only_projection"] is True
        assert resource.metadata["purpose_minimized"] is True
        assert resource.metadata["source_domain"].startswith("domain:")


def test_profile_allows_exploratory_hypotheses_but_forbids_diagnostic_promotion():
    from cmm.domains.neurodivergence.profile import build_neurodivergence_profile

    profile = build_neurodivergence_profile()

    assert profile.profile_name == "NeurodivergenceProfile"
    assert profile.domain_id == "domain:neurodivergence"
    assert "working_hypothesis" in profile.allowed_inferences
    assert "pattern_association" in profile.allowed_inferences
    assert "differential_hypothesis" in profile.allowed_inferences
    assert "overlap_hypothesis" in profile.allowed_inferences
    assert "definitive_diagnosis" in profile.prohibited_inferences
    assert "model_inference_as_clinical_fact" in profile.prohibited_inferences
    assert "screening_as_diagnosis" in profile.prohibited_inferences
    assert "self_report_as_diagnosis" in profile.prohibited_inferences
    assert "isolated_trait_as_diagnostic_identity" in profile.prohibited_inferences


def test_profile_memory_and_presentation_policy_is_local_restrictive():
    from cmm.domains.neurodivergence.profile import build_neurodivergence_profile

    profile = build_neurodivergence_profile()

    assert profile.memory_policy.allow_read is True
    assert profile.memory_policy.allow_write is False
    assert profile.memory_policy.allow_long_term is False
    assert profile.memory_policy.allow_cross_domain is False
    assert profile.memory_policy.sensitivity_limit is SensitivityLevel.SENSITIVE
    assert profile.presentation_policy.include_uncertainty is True
    assert profile.presentation_policy.include_provenance is True
    assert profile.presentation_policy.include_alternatives is True


def test_profile_does_not_require_a_clinical_tone_or_a_disclaimer_wall():
    from cmm.domains.neurodivergence.profile import build_neurodivergence_profile

    policy = build_neurodivergence_profile().presentation_policy

    # An exploration-friendly pack permits useful exploratory content and never
    # opens with a mandatory warning block.
    assert policy.require_disclaimers is False
    assert policy.warning_position != "before_content"


def test_profile_prohibits_autonomous_clinical_and_medical_action():
    from cmm.domains.neurodivergence.profile import (
        NEURODIVERGENCE_PROHIBITED_ACTIONS,
        build_neurodivergence_profile,
    )

    profile = build_neurodivergence_profile()

    for action in (
        "medication_start",
        "medication_stop",
        "medication_dose_change",
        "treatment_plan_change",
        "clinical_authority_claim",
        "model_inference_as_clinical_fact",
        "semantic_memory_write",
        "unconfirmed_memory_persistence",
        "sensitive_inference_persist",
        "external_communication",
        "export",
    ):
        assert action in NEURODIVERGENCE_PROHIBITED_ACTIONS
        assert action in profile.prohibited_actions


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2 — epistemic rules
# ═══════════════════════════════════════════════════════════════════════════════


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="reasoning-1", timestamp=T, metadata=metadata
    )


def _by_id(rules):
    return {rule.definition.id: rule for rule in rules}


def test_rule_inventory_matches_canonical_catalog():
    from cmm.domains.neurodivergence.rules import build_neurodivergence_rules

    from cmm.domains.neurodivergence.catalog import NEURODIVERGENCE_RULE_IDS

    rules = build_neurodivergence_rules()
    ids = tuple(rule.definition.id for rule in rules)
    assert ids == NEURODIVERGENCE_RULE_IDS
    assert len(ids) == len(set(ids))
    assert len(ids) == 14
