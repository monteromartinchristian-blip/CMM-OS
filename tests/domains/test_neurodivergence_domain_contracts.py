"""Tests for Phase 10.53 Neurodivergence Domain canonical contracts.

Task 1: canonical inventory (catalog), resources and exploration-friendly
profile.
Task 2: epistemic rules — exploratory inference allowed, diagnostic promotion
blocked, certainty hierarchy preserved.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus, SensitivityLevel
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.identifiers import DomainId

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


def _rules():
    from cmm.domains.neurodivergence.rules import build_neurodivergence_rules

    return _by_id(build_neurodivergence_rules())


def _canonical_transfer(identifier: str, *, reason: str = "differential_context"):
    """Return the JSON-safe canonical ``CrossDomainContextTransfer`` mapping."""
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer

    return CrossDomainContextTransfer(
        source_domain="domain:mental-health",
        target_domain="domain:neurodivergence",
        kind="finding",
        identifier=identifier,
        value=True,
        reason=reason,
        provenance=("finding:mental-health:7",),
    ).to_dict()


def _canonical_transfer_provenance() -> dict:
    """Return the canonical JSON-safe ``ResourceProvenance`` representation."""
    from cmm.cognitive.enums import ResourceSourceKind
    from cmm.cognitive.resources import ResourceProvenance

    return ResourceProvenance(
        source_type=ResourceSourceKind.UPLOADED_FILE,
        source_id="assessment-report-1",
    ).to_dict()


def test_rule_inventory_matches_canonical_catalog():
    from cmm.domains.neurodivergence.catalog import NEURODIVERGENCE_RULE_IDS
    from cmm.domains.neurodivergence.rules import build_neurodivergence_rules

    rules = build_neurodivergence_rules()
    ids = tuple(rule.definition.id for rule in rules)
    assert ids == NEURODIVERGENCE_RULE_IDS
    assert len(ids) == len(set(ids))
    assert len(ids) == 14


# ── Exploratory inference is allowed and genuinely useful ────────────────────


def test_exploratory_differential_reasoning_produces_useful_hypotheses():
    """EXPLORATORY_MODEL_INFERENCE=ALLOWED — useful, applied, hypothesis-first."""
    rules = _rules()
    rule = rules["neurodivergence.differential_explanations"]

    result = rule.evaluate(
        _context(
            exploration={
                "objective": "Could these social and sensory patterns fit autism?",
                "hypothesis": "autism",
                "supporting": (
                    {"id": "obs-1", "note": "consistent sensory preferences"},
                    {"id": "obs-2", "note": "lifelong social exhaustion"},
                ),
                "unclear": ({"id": "gap-1", "note": "no early developmental record"},),
                "conflicting": (
                    {"id": "con-1", "note": "no childhood onset reported"},
                ),
                "alternatives": (
                    {"id": "alt-1", "note": "anxiety-related social avoidance"},
                ),
                "clarifying_evidence": (
                    {"id": "next-1", "note": "school observation records"},
                ),
            }
        )
    )

    # Genuinely useful applied behavior — not merely "not blocked".
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["exploration_performed"] is True
    assert result.metadata["exploratory_model_inference"] == "allowed"
    assert result.metadata["hypothesis_state"] == "hypothesis"
    assert result.metadata["confirmed_diagnosis_created"] is False
    assert result.metadata["differential_reasoning"] == "balanced_not_adversarial"
    assert result.metadata["negative_evidence_required"] is False
    for category in (
        "supporting",
        "unclear",
        "conflicting",
        "alternatives",
        "clarifying_evidence",
    ):
        assert category in result.metadata["categories_covered"]


def test_exploratory_reasoning_needs_no_fabricated_negative_case():
    """A hypothesis-only request is supported; no counterargument is invented."""
    rules = _rules()
    rule = rules["neurodivergence.differential_explanations"]

    result = rule.evaluate(
        _context(
            exploration={
                "objective": "Could this be related to ADHD?",
                "hypothesis": "adhd",
                "supporting": ({"id": "obs-1"},),
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["negative_evidence_required"] is False
    assert result.metadata["fabricated_negative_evidence"] is False
    assert result.metadata["refusal_generated"] is False
    assert result.metadata["confirmed_diagnosis_created"] is False


def test_exploratory_reasoning_does_not_produce_disclaimer_only_output():
    """Ordinary exploration is reasoned about, not replaced by a disclaimer."""
    rules = _rules()
    rule = rules["neurodivergence.differential_explanations"]

    result = rule.evaluate(
        _context(
            exploration={
                "objective": "Why might this fit?",
                "hypothesis": "autism",
                "supporting": ({"id": "obs-1"},),
                "alternatives": ({"id": "alt-1"},),
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["disclaimer_only_output"] is False
    assert result.metadata["professional_assessment_substituted_reasoning"] is False
    assert result.metadata["reasoning_present"] is True


# ── Canonical Health clinical authority (Audit V1 MAJOR-01 remediation) ──────
#
# Clinical certainty is bound to the existing canonical Health
# projection/transfer/provenance path instead of a caller-authored mapping.
# Every element below is an existing production contract: the canonical
# ``DomainId`` owner identity, the canonical ``CrossDomainContextTransfer``
# carriage with contract-enforced provenance, the canonical
# ``ResourceProvenance`` evidence identity, and the current canonical
# permission authority that the connected acceptance exercises for real.

HEALTH = DomainId(slug="health")
NEURODIVERGENCE = DomainId(slug="neurodivergence")
CANONICAL_AUTHORITY_PURPOSE = "clinical_status_review"
CANONICAL_CLAIM_ID = "claim-1"


def _canonical_clinical_status_record() -> dict:
    """The Health-owned documented clinical status with canonical provenance."""
    from cmm.cognitive.enums import ResourceSourceKind
    from cmm.cognitive.resources import ResourceProvenance

    return {
        "documented_diagnosis": True,
        "provenance": ResourceProvenance(
            source_type=ResourceSourceKind.UPLOADED_FILE,
            source_id="clinical-record:nd-1",
        ).to_dict(),
    }


def _canonical_health_authority_transfer(identifier, **overrides) -> dict:
    """A canonical Health -> Neurodivergence clinical-status transfer."""
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer

    values = {
        "source_domain": HEALTH,
        "target_domain": NEURODIVERGENCE,
        "kind": "clinical_status",
        "identifier": identifier,
        "value": _canonical_clinical_status_record(),
        "reason": CANONICAL_AUTHORITY_PURPOSE,
        "provenance": ("clinical-record:nd-1",),
    }
    values.update(overrides)
    return CrossDomainContextTransfer(**values).to_dict()


def _authoritative_claim(claim_id=CANONICAL_CLAIM_ID, **overrides):
    """The provenance-bound Health claim, as trusted source-owner code builds it.

    The canonical ``ResourceProvenance`` is constructed from the canonical
    contract (never rehydrated from a serialized shape) for the Health-owned
    clinical-record artifact that the admitted transfer references.
    """
    from cmm.cognitive import AuthoritativeSourceClaim
    from cmm.cognitive.enums import ResourceSourceKind
    from cmm.cognitive.resources import ResourceProvenance

    values = {
        "claim_id": claim_id,
        "source_domain": "domain:health",
        "purpose": CANONICAL_AUTHORITY_PURPOSE,
        "provenance": ResourceProvenance(
            source_type=ResourceSourceKind.UPLOADED_FILE,
            source_id="clinical-record:nd-1",
        ),
    }
    values.update(overrides)
    return AuthoritativeSourceClaim(**values)


def _canonical_certainty_request(**overrides) -> dict:
    """A CONFIRMED transition carrying canonical Health authority evidence."""
    values = {
        "claim_id": CANONICAL_CLAIM_ID,
        "from_state": "in_evaluation",
        "to_state": "confirmed",
        "evidence_kind": "documented_clinical_status",
        "clinical": True,
        "purpose": CANONICAL_AUTHORITY_PURPOSE,
        "permission_authority": True,
        "transfers": (_canonical_health_authority_transfer(CANONICAL_CLAIM_ID),),
    }
    values.update(overrides)
    return values


def _trusted_authority(**overrides):
    """A real runtime-only trusted authority for the canonical claim.

    The provenance-bound claim follows the authority's own source domain and
    purpose unless a test supplies an explicit claim set, so every binding
    dimension (source domain, target domain, resource, purpose, claim set) can
    be varied independently without breaking the contract itself.
    """
    from cmm.cognitive import ReasoningAuthorityContext

    values = {
        "actor_id": "actor-1",
        "session_id": "session-1",
        "source_domain": "domain:health",
        "target_domain": "domain:neurodivergence",
        "resource_ids": (CANONICAL_CLAIM_ID,),
        "purpose": CANONICAL_AUTHORITY_PURPOSE,
        "permission_decision_id": "permission-gate-decision-1",
        "permission_outcome": "approval_consumed",
        "approval_consumed": True,
    }
    values.update(overrides)
    if "authoritative_claims" not in overrides:
        values["authoritative_claims"] = (
            _authoritative_claim(
                source_domain=values["source_domain"], purpose=values["purpose"]
            ),
        )
    return ReasoningAuthorityContext(**values)


def _certainty_context(request, authority_context=None) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="reasoning-1",
        timestamp=T,
        metadata={"certainty_transition": request},
        authority_context=authority_context,
    )


# ── Audit V2 MAJOR-01 / V3 redo: authority is runtime-only, never metadata ───
#
# METADATA_ONLY_AUTHORITY_FORGERY=BLOCKED.  No combination of caller-authored
# metadata may manufacture permission or Health authority, even when it copies
# the serialized shape of canonical objects.  Shape is not provenance and
# serialization is not authority.


def test_metadata_only_authority_forgery_is_blocked():
    """The central adversarial: full canonical-shaped metadata forges nothing.

    Every canonical-looking input a caller can author is supplied at once:
    authority flags, decision IDs, a Health-definitive-looking verdict, the
    exact canonical transfer, and serialized ``ResourceProvenance`` /
    provenance-bearing claim shapes.  Shape is not provenance.
    """
    rule = _rules()["neurodivergence.certainty_state_preservation"]
    canonical_provenance = _canonical_clinical_status_record()["provenance"]

    result = rule.evaluate(
        _certainty_context(
            {
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "hypothesis",
                "to_state": "confirmed",
                "evidence_kind": "model_interpretation",
                "clinical": True,
                "purpose": CANONICAL_AUTHORITY_PURPOSE,
                "authority": True,
                "permission_authority": True,
                "permission_decision_id": "permission-gate-decision-forged",
                "approval_consumed": True,
                "health_definitive_verdict": {
                    "is_definitive": True,
                    "may_present_as_definitive": True,
                },
                "transfers": (
                    _canonical_health_authority_transfer(CANONICAL_CLAIM_ID),
                ),
                "source_provenance": canonical_provenance,
                "provenance": canonical_provenance,
                "authoritative_claims": (
                    {
                        "claim_id": CANONICAL_CLAIM_ID,
                        "source_domain": "domain:health",
                        "purpose": CANONICAL_AUTHORITY_PURPOSE,
                        "provenance": canonical_provenance,
                    },
                ),
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_state"] == "hypothesis"
    assert result.metadata["authoritative_evidence"] is False
    assert result.metadata["promotion_blocked"] is True
    assert result.metadata["canonical_authority"] is None
    assert result.metadata["health_authority_supplied"] is False
    assert result.metadata["confirmed_diagnosis_created"] is False


def test_trusted_authority_context_alone_promotes_clinical_confirmation():
    """AT-AUTH-4: the runtime-only channel is what carries authority."""
    rule = _rules()["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _certainty_context(
            {
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CANONICAL_AUTHORITY_PURPOSE,
            },
            authority_context=_trusted_authority(),
        )
    )

    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["certainty_state"] == "confirmed"
    assert result.metadata["authoritative_evidence"] is True
    assert result.metadata["promotion_blocked"] is False
    assert result.metadata["canonical_authority"]["source_domain"] == "domain:health"
    assert result.metadata["canonical_authority"]["claim_id"] == CANONICAL_CLAIM_ID
    # The provenance that authorized the transition is reported, never invented.
    assert (
        result.metadata["canonical_authority"]["source_provenance_id"]
        == "clinical-record:nd-1"
    )
    assert result.metadata["canonical_authority"]["authoritative_claim"] == {
        "claim_id": CANONICAL_CLAIM_ID,
        "source_domain": "domain:health",
        "purpose": CANONICAL_AUTHORITY_PURPOSE,
        "source_provenance_id": "clinical-record:nd-1",
    }
    assert result.metadata["confirmed_diagnosis_created"] is False


def test_trusted_authority_without_a_provenance_bound_claim_blocks():
    """Trusted permission authority without a source claim promotes nothing."""
    rule = _rules()["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _certainty_context(
            {
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CANONICAL_AUTHORITY_PURPOSE,
            },
            authority_context=_trusted_authority(authoritative_claims=()),
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_state"] == "in_evaluation"
    assert result.metadata["authoritative_evidence"] is False
    assert result.metadata["promotion_blocked"] is True
    assert result.metadata["canonical_authority"] is None
    # The trusted context itself was supplied; it simply carried no claim.
    assert result.metadata["health_authority_supplied"] is False


@pytest.mark.parametrize(
    "claims",
    (
        pytest.param((_authoritative_claim("another-claim"),), id="other-claim"),
        pytest.param(
            (_authoritative_claim(claim_id=CANONICAL_CLAIM_ID.upper()),),
            id="case-mismatch",
        ),
    ),
)
def test_trusted_authority_claim_must_name_the_requested_claim(claims):
    """A provenance-bound claim for another claim id is not this transition's."""
    rule = _rules()["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _certainty_context(
            {
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CANONICAL_AUTHORITY_PURPOSE,
            },
            authority_context=_trusted_authority(
                resource_ids=(CANONICAL_CLAIM_ID, "another-claim"),
                authoritative_claims=claims,
            ),
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_state"] == "in_evaluation"
    assert result.metadata["authoritative_evidence"] is False


@pytest.mark.parametrize(
    "overrides",
    (
        pytest.param({"source_domain": "domain:mental-health"}, id="wrong-source"),
        pytest.param({"target_domain": "domain:university"}, id="wrong-target"),
        pytest.param({"resource_ids": ("another-resource",)}, id="resource-mismatch"),
        pytest.param(
            {"authoritative_claims": (_authoritative_claim("another-claim"),)},
            id="claim-mismatch",
        ),
        pytest.param({"authoritative_claims": ()}, id="no-authoritative-claims"),
        pytest.param({"purpose": "another_purpose"}, id="purpose-mismatch"),
    ),
)
def test_trusted_authority_binding_must_match_the_request(overrides):
    """A real trusted context that does not bind this claim/purpose promotes nothing."""
    rule = _rules()["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _certainty_context(
            {
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CANONICAL_AUTHORITY_PURPOSE,
            },
            authority_context=_trusted_authority(**overrides),
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_state"] == "in_evaluation"
    assert result.metadata["authoritative_evidence"] is False


def test_trusted_authority_with_allow_outcome_promotes_confirmation():
    """A canonical ALLOW gate decision is effective authority too."""
    rule = _rules()["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _certainty_context(
            {
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CANONICAL_AUTHORITY_PURPOSE,
            },
            authority_context=_trusted_authority(
                permission_outcome="allow", approval_consumed=False
            ),
        )
    )

    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["certainty_state"] == "confirmed"
    assert result.metadata["authoritative_evidence"] is True


def test_metadata_cannot_revoke_or_rewrite_trusted_authority():
    """Metadata has zero authority effect in either direction."""
    rule = _rules()["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _certainty_context(
            {
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CANONICAL_AUTHORITY_PURPOSE,
                "permission_authority": False,
                "approval_consumed": False,
                "health_definitive_verdict": {"is_definitive": False},
            },
            authority_context=_trusted_authority(),
        )
    )

    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["certainty_state"] == "confirmed"
    assert result.metadata["authoritative_evidence"] is True


def test_ruled_out_remains_fail_closed_even_with_trusted_permission_authority():
    """No canonical Health negative authority path exists, so exclusion stays blocked."""
    rule = _rules()["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _certainty_context(
            {
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "hypothesis",
                "to_state": "ruled_out",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CANONICAL_AUTHORITY_PURPOSE,
            },
            authority_context=_trusted_authority(),
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_state"] == "hypothesis"
    assert result.metadata["exclusion_created"] is False


# ── Diagnostic promotion fails closed ────────────────────────────────────────


@pytest.mark.parametrize(
    "source_kind",
    ("screening", "self_report", "isolated_trait", "model_interpretation"),
)
def test_non_authoritative_evidence_cannot_become_confirmed_diagnosis(source_kind):
    rules = _rules()
    rule = rules["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": "claim-1",
                "from_state": "hypothesis",
                "to_state": "confirmed",
                "evidence_kind": source_kind,
                "clinical": True,
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["confirmed_diagnosis_created"] is False
    assert result.metadata["promotion_blocked"] is True
    assert result.metadata["certainty_preserved"] is True


def test_fabricated_health_mapping_cannot_confirm_a_clinical_status():
    """Audit V1 MAJOR-01: a caller-authored authority mapping grants nothing.

    The assertion is on the *effective certainty state*: the defect was that
    the returned state had already become ``confirmed``, not a cosmetic flag.
    """
    rules = _rules()
    rule = rules["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "hypothesis",
                "to_state": "confirmed",
                "evidence_kind": "model_interpretation",
                "clinical": True,
                "authority": {
                    "documented": True,
                    "domain": "domain:health",
                    "source_ref": "fabricated:1",
                },
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_state"] == "hypothesis"
    assert result.metadata["authoritative_evidence"] is False
    assert result.metadata["confirmed_diagnosis_created"] is False


def test_fabricated_health_mapping_cannot_rule_out_a_clinical_status():
    """Audit V1 MAJOR-01: exclusion is authoritative clinical status too."""
    rules = _rules()
    rule = rules["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "hypothesis",
                "to_state": "ruled_out",
                "evidence_kind": "model_interpretation",
                "clinical": True,
                "authority": {
                    "documented": True,
                    "domain": "domain:health",
                    "source_ref": "fabricated:1",
                },
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_state"] == "hypothesis"
    assert result.metadata["authoritative_evidence"] is False
    assert result.metadata["exclusion_blocked"] is True
    assert result.metadata["exclusion_created"] is False


def test_canonical_shaped_transfer_metadata_alone_confirms_nothing():
    """Audit V2 MAJOR-01 residual: canonical *shape* is not authority.

    A structurally valid Health ``CrossDomainContextTransfer`` with canonical
    ``ResourceProvenance``, plus a caller-authored ``permission_authority``
    boolean and matching claim and purpose, is still request data.  Under the
    trusted-authority amendment it grants nothing; only the runtime-only
    ``ReasoningAuthorityContext`` can, as the trusted-authority tests below
    prove in both directions.
    """
    rules = _rules()
    rule = rules["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _context(certainty_transition=_canonical_certainty_request())
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_state"] == "in_evaluation"
    assert result.metadata["promotion_blocked"] is True
    assert result.metadata["authoritative_evidence"] is False
    assert result.metadata["health_authority_supplied"] is False
    assert result.metadata["canonical_authority"] is None


@pytest.mark.parametrize(
    "overrides",
    (
        pytest.param({"permission_authority": False}, id="no-current-authority"),
        pytest.param({"permission_authority": None}, id="authority-not-supplied"),
        pytest.param({"purpose": "another_purpose"}, id="purpose-mismatch"),
        pytest.param({"claim_id": "another-claim"}, id="claim-mismatch"),
        pytest.param({"transfers": ()}, id="no-transfer-evidence"),
    ),
)
def test_canonical_evidence_without_current_authority_confirms_nothing(overrides):
    """A canonical transfer is never authority by itself."""
    rules = _rules()
    rule = rules["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _context(certainty_transition=_canonical_certainty_request(**overrides))
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_state"] == "in_evaluation"
    assert result.metadata["authoritative_evidence"] is False


@pytest.mark.parametrize(
    "malformed_record",
    (
        {"documented_diagnosis": "true"},
        {"documented_diagnosis": 1},
        {"documented_diagnosis": {}},
    ),
)
def test_malformed_canonical_clinical_status_never_confirms(malformed_record):
    """Strict boolean handling survives on the canonical path."""
    rules = _rules()
    rule = rules["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _context(
            certainty_transition=_canonical_certainty_request(
                transfers=(
                    _canonical_health_authority_transfer(
                        CANONICAL_CLAIM_ID,
                        value={
                            **_canonical_clinical_status_record(),
                            **malformed_record,
                        },
                    ),
                )
            )
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["authoritative_evidence"] is False


@pytest.mark.parametrize(
    "malformed",
    ("false", "0", 1, 0, [], {}, "yes"),
)
def test_malformed_authority_never_supports_a_confirmed_diagnosis(malformed):
    """A free-form authority mapping never authorizes, however it is shaped."""
    rules = _rules()
    rule = rules["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": CANONICAL_CLAIM_ID,
                "from_state": "hypothesis",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "authority": {
                    "domain": "domain:health",
                    "documented": malformed,
                    "source_ref": "health-record:1",
                },
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["confirmed_diagnosis_created"] is False


# ── Certainty hierarchy ──────────────────────────────────────────────────────


def test_certainty_states_remain_semantically_distinct():
    from cmm.domains.neurodivergence.rules import (
        CERTAINTY_CONFIRMED,
        CERTAINTY_HYPOTHESIS,
        CERTAINTY_IN_EVALUATION,
        CERTAINTY_INSUFFICIENTLY_SUPPORTED,
        CERTAINTY_NOT_CONFIRMED,
        CERTAINTY_RULED_OUT,
    )

    assert CERTAINTY_NOT_CONFIRMED != CERTAINTY_RULED_OUT
    assert CERTAINTY_INSUFFICIENTLY_SUPPORTED != CERTAINTY_RULED_OUT
    assert CERTAINTY_IN_EVALUATION != CERTAINTY_CONFIRMED
    assert CERTAINTY_HYPOTHESIS != CERTAINTY_CONFIRMED
    assert (
        len(
            {
                CERTAINTY_CONFIRMED,
                CERTAINTY_IN_EVALUATION,
                CERTAINTY_HYPOTHESIS,
                CERTAINTY_NOT_CONFIRMED,
                CERTAINTY_RULED_OUT,
                CERTAINTY_INSUFFICIENTLY_SUPPORTED,
            }
        )
        == 6
    )


def test_certainty_state_semantics_are_derived_and_non_authoritative():
    from cmm.domains.neurodivergence.rules import describe_certainty_state

    confirmed = describe_certainty_state("confirmed")
    ruled_out = describe_certainty_state("ruled_out")
    not_confirmed = describe_certainty_state("not_confirmed")
    in_evaluation = describe_certainty_state("in_evaluation")

    # CONFIRMED and RULED_OUT require the owning authority; NOT CONFIRMED does
    # not imply exclusion.
    assert confirmed["requires_authority"] is True
    assert confirmed["certified_here"] is False
    assert ruled_out["requires_authority"] is True
    assert ruled_out["certified_here"] is False
    assert not_confirmed["implies_exclusion"] is False
    assert ruled_out["implies_exclusion"] is True
    assert in_evaluation["certified_here"] is False
    assert describe_certainty_state("unknown")["label"] == "unknown"


def test_certainty_state_preservation_rule_keeps_negative_states_separate():
    rules = _rules()
    rule = rules["neurodivergence.certainty_state_preservation"]

    result = rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": "claim-2",
                "from_state": "not_confirmed",
                "to_state": "ruled_out",
                "evidence_kind": "model_interpretation",
                "clinical": True,
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certified_here"] is False
    assert result.metadata["exclusion_created"] is False


# ── Screening / self-report / observation separation ─────────────────────────


def test_screening_is_evidence_and_never_a_diagnosis():
    rules = _rules()
    rule = rules["neurodivergence.screening_diagnosis_separation"]

    contributed = rule.evaluate(
        _context(
            screening={
                "instrument": "screening-instrument",
                "source_ref": "screening:1",
                "claimed_as_diagnosis": False,
            }
        )
    )
    assert contributed.status is ReasoningRuleResultStatus.APPLIED
    assert contributed.metadata["screening_is_evidence_only"] is True
    assert contributed.metadata["diagnosis_created"] is False

    promoted = rule.evaluate(
        _context(
            screening={
                "instrument": "screening-instrument",
                "source_ref": "screening:1",
                "claimed_as_diagnosis": True,
            }
        )
    )
    assert promoted.status is ReasoningRuleResultStatus.BLOCKED
    assert promoted.metadata["screening_promoted_to_diagnosis"] is False
    assert promoted.metadata["confirmed_diagnosis_created"] is False


def test_observation_self_report_and_third_party_report_stay_separate():
    from cmm.domains.neurodivergence.rules import classify_evidence_source

    rules = _rules()
    rule = rules["neurodivergence.observation_report_separation"]

    assert classify_evidence_source({"evidence_type": "direct_observation"}) == (
        "direct_observation"
    )
    assert classify_evidence_source({"evidence_type": "retrospective_self_report"}) == (
        "retrospective_self_report"
    )
    assert classify_evidence_source({"evidence_type": "third_party_report"}) == (
        "third_party_report"
    )
    assert classify_evidence_source({}) == "unknown"

    result = rule.evaluate(
        _context(
            evidence_items=(
                {"id": "e1", "evidence_type": "direct_observation"},
                {"id": "e2", "evidence_type": "retrospective_self_report"},
                {"id": "e3", "evidence_type": "third_party_report"},
            )
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["report_collapsed_into_observation"] is False
    assert set(result.metadata["evidence_classes"]) == {
        "direct_observation",
        "retrospective_self_report",
        "third_party_report",
    }

    collapsed = rule.evaluate(
        _context(
            evidence_items=(
                {
                    "id": "e4",
                    "evidence_type": "retrospective_self_report",
                    "presented_as": "direct_observation",
                },
            )
        )
    )
    assert collapsed.status is ReasoningRuleResultStatus.BLOCKED
    assert collapsed.metadata["report_collapsed_into_observation"] is True


def test_observation_report_separation_requires_source_identity():
    rules = _rules()
    rule = rules["neurodivergence.observation_report_separation"]

    result = rule.evaluate(
        _context(
            evidence_items=(
                {
                    "id": "e1",
                    "evidence_type": "direct_observation",
                    "source_ref": "observer:parent-1",
                },
                {"id": "e2", "evidence_type": "third_party_report"},
            ),
            source_provenance=_canonical_transfer_provenance(),
        )
    )
    # A supplied provenance context makes an unprovenanced item fail closed
    # instead of silently supporting a high-confidence conclusion.
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["unprovenanced_evidence_ids"] == ("e2",)
    assert result.metadata["provenance_preserved"] is False


# ── Developmental temporality ────────────────────────────────────────────────


def test_historical_trait_is_not_generalized_to_current_impairment():
    rules = _rules()
    rule = rules["neurodivergence.developmental_temporality"]

    result = rule.evaluate(
        _context(
            temporal_claim={
                "claim_id": "t1",
                "observed_period": "historical",
                "observation_kind": "retrospective",
                "generalized_to": "current_impairment",
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["temporal_generalization_blocked"] is True
    assert result.metadata["current_vs_historical_distinguished"] is True


def test_retrospective_report_is_not_a_contemporaneous_observation():
    rules = _rules()
    rule = rules["neurodivergence.developmental_temporality"]

    result = rule.evaluate(
        _context(
            temporal_claim={
                "claim_id": "t2",
                "observed_period": "historical",
                "observation_kind": "retrospective",
                "presented_as": "contemporaneous",
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["retrospective_as_contemporaneous"] is True


def test_temporal_claims_within_their_evidence_scope_are_applied():
    rules = _rules()
    rule = rules["neurodivergence.developmental_temporality"]

    result = rule.evaluate(
        _context(
            temporal_claim={
                "claim_id": "t3",
                "observed_period": "current",
                "observation_kind": "contemporaneous",
                "generalized_to": "current_impairment",
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["temporal_generalization_blocked"] is False
    assert result.metadata["current_vs_historical_distinguished"] is True


# ── Trait vs functional significance ─────────────────────────────────────────


def test_a_trait_is_not_clinically_significant_impairment_by_itself():
    rules = _rules()
    rule = rules["neurodivergence.trait_function_separation"]

    separate = rule.evaluate(
        _context(
            trait_claim={
                "trait": "prefers predictable routines",
                "functional_impact_evidence": False,
                "claimed_clinically_significant": False,
            }
        )
    )
    assert separate.status is ReasoningRuleResultStatus.APPLIED
    assert separate.metadata["trait_treated_as_impairment"] is False
    assert separate.metadata["functional_relevance_analyzed"] is True

    promoted = rule.evaluate(
        _context(
            trait_claim={
                "trait": "prefers predictable routines",
                "functional_impact_evidence": False,
                "claimed_clinically_significant": True,
            }
        )
    )
    assert promoted.status is ReasoningRuleResultStatus.BLOCKED
    assert promoted.metadata["trait_treated_as_impairment"] is False


# ── Longitudinal corroboration ───────────────────────────────────────────────


def test_absent_longitudinal_corroboration_is_not_disproof():
    rules = _rules()
    rule = rules["neurodivergence.longitudinal_corroboration"]

    result = rule.evaluate(
        _context(
            longitudinal={
                "claim_id": "l1",
                "periods": ({"id": "p1", "period": "current"},),
                "sources": ({"id": "s1", "source": "self"},),
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["corroboration_present"] is False
    assert result.metadata["confidence_reduced"] is True
    assert result.metadata["absence_treated_as_disproof"] is False
    assert result.metadata["disproof_created"] is False


def test_explicit_disproof_from_absent_corroboration_is_blocked():
    rules = _rules()
    rule = rules["neurodivergence.longitudinal_corroboration"]

    result = rule.evaluate(
        _context(
            longitudinal={
                "claim_id": "l2",
                "periods": ({"id": "p1", "period": "current"},),
                "sources": ({"id": "s1", "source": "self"},),
                "absence_is_disproof": True,
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["absence_treated_as_disproof"] is False
    assert result.metadata["disproof_created"] is False


def test_multiple_corroborating_periods_raise_confidence():
    rules = _rules()
    rule = rules["neurodivergence.longitudinal_corroboration"]

    result = rule.evaluate(
        _context(
            longitudinal={
                "claim_id": "l3",
                "periods": (
                    {"id": "p1", "period": "historical"},
                    {"id": "p2", "period": "current"},
                ),
                "sources": (
                    {"id": "s1", "source": "self"},
                    {"id": "s2", "source": "third_party"},
                ),
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["corroboration_present"] is True
    assert result.metadata["confidence_reduced"] is False


# ── Contradiction preservation ───────────────────────────────────────────────


def test_competing_evidence_must_remain_visible():
    rules = _rules()
    rule = rules["neurodivergence.contradiction_preservation"]

    erased = rule.evaluate(
        _context(
            evidence_set={
                "hypothesis": "autism",
                "evidence": (
                    {"id": "e1", "direction": "supports"},
                    {"id": "e2", "direction": "weakens"},
                ),
                "reported_evidence_ids": ("e1",),
            }
        )
    )
    assert erased.status is ReasoningRuleResultStatus.BLOCKED
    assert erased.metadata["contradiction_erased"] is True
    assert erased.metadata["competing_evidence_visible"] is False

    preserved = rule.evaluate(
        _context(
            evidence_set={
                "hypothesis": "autism",
                "evidence": (
                    {"id": "e1", "direction": "supports"},
                    {"id": "e2", "direction": "weakens"},
                ),
                "reported_evidence_ids": ("e1", "e2"),
            }
        )
    )
    assert preserved.status is ReasoningRuleResultStatus.APPLIED
    assert preserved.metadata["contradiction_erased"] is False
    assert preserved.metadata["weakening_evidence_ids"] == ("e2",)


# ── Overlap reasoning ────────────────────────────────────────────────────────


def test_overlap_reasoning_allows_overlap_without_co_diagnosis():
    rules = _rules()
    rule = rules["neurodivergence.overlap_reasoning"]

    result = rule.evaluate(
        _context(
            overlap={
                "hypotheses": ("autism", "adhd"),
                "overlapping_features": ({"id": "f1"},),
                "distinguishing_evidence": ({"id": "d1"},),
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["overlap_considered"] is True
    assert result.metadata["co_diagnosis_created"] is False
    assert result.metadata["overlap_is_not_co_diagnosis"] is True


# ── Global-attribution guard ─────────────────────────────────────────────────


def test_global_attribution_guard_blocks_an_unevidenced_global_claim():
    rules = _rules()
    rule = rules["neurodivergence.global_attribution_guard"]

    result = rule.evaluate(
        _context(
            attribution={
                "explanation": "every difficulty is caused by neurodivergence",
                "global_causal_claim": True,
                "evidence_supplied": False,
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["global_attribution_blocked"] is True
    assert result.metadata["exploratory_association_suppressed"] is False


def test_global_attribution_guard_never_suppresses_exploration():
    """The guard is anti-over-attribution, not anti-hypothesis."""
    rules = _rules()
    rule = rules["neurodivergence.global_attribution_guard"]

    for attribution in (
        {
            "explanation": "sensory overload may contribute to this difficulty",
            "global_causal_claim": False,
            "evidence_supplied": False,
        },
        {
            "explanation": "attention difficulties",
            "global_causal_claim": True,
            "evidence_supplied": True,
        },
    ):
        result = rule.evaluate(_context(attribution=attribution))
        assert result.status is ReasoningRuleResultStatus.APPLIED
        assert result.metadata["global_attribution_blocked"] is False
        assert result.metadata["exploratory_association_suppressed"] is False
        assert result.metadata["hypothesis_status_preserved"] is True


# ── Source authority ─────────────────────────────────────────────────────────


def test_imported_facts_keep_their_source_domain_owner():
    rules = _rules()
    rule = rules["neurodivergence.source_authority"]

    result = rule.evaluate(
        _context(
            source_claims=(
                {
                    "id": "c1",
                    "source_domain": "domain:university",
                    "fact": "exam accommodation on record",
                },
                {
                    "id": "c2",
                    "source_domain": "domain:relationships",
                    "fact": "reports social exhaustion",
                },
            )
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["source_authority_preserved"] is True
    assert result.metadata["rewritten_claims"] == ()
    assert result.metadata["source_domains"] == (
        "domain:relationships",
        "domain:university",
    )


def test_source_authority_blocks_re_emitting_a_foreign_fact_as_owned():
    rules = _rules()
    rule = rules["neurodivergence.source_authority"]

    result = rule.evaluate(
        _context(
            source_claims=(
                {
                    "id": "c1",
                    "source_domain": "domain:health",
                    "fact": "documented diagnosis on record",
                    "re_emitted_as": "domain:neurodivergence",
                },
            )
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["source_authority_preserved"] is False
    assert result.metadata["rewritten_claims"] == ("c1",)


def test_source_authority_blocks_an_unknown_source_owner():
    rules = _rules()
    rule = rules["neurodivergence.source_authority"]

    result = rule.evaluate(
        _context(source_claims=({"id": "c1", "source_domain": "unknown", "fact": "x"},))
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["unknown_source_claims"] == ("c1",)


@pytest.mark.parametrize(
    "source_domain",
    (
        "not-a-domain",
        "health",
        "domain:",
        "domain:Not-A-Domain",
        "domain:health:extra",
        " domain:health",
    ),
)
def test_source_authority_rejects_a_non_canonical_source_domain(source_domain):
    """Audit V1 MAJOR-01: an owner identity must be a canonical ``DomainId``.

    ``not-a-domain`` is neither a canonical ``domain:<slug>`` identifier nor a
    real domain, so the imported fact has no valid owner and fails closed.
    """
    rules = _rules()
    rule = rules["neurodivergence.source_authority"]

    result = rule.evaluate(
        _context(
            source_claims=(
                {"id": "c1", "source_domain": source_domain, "fact": "imported fact"},
            )
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["source_authority_preserved"] is False
    assert result.metadata["source_domains"] == ()
    assert result.metadata["unknown_source_claims"] == ("c1",)


# ── Health clinical authority ────────────────────────────────────────────────


def test_clinical_status_authority_preserves_health_and_allows_hypothesis():
    rules = _rules()
    rule = rules["neurodivergence.clinical_status_authority"]

    result = rule.evaluate(
        _context(
            clinical_claim={
                "documented_diagnosis": True,
                "diagnosis_status": "confirmed",
                "competing_hypothesis": "autism",
                "requested": "confirm_diagnosis",
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["primary_authority"] == "domain:health"
    assert result.metadata["neurodivergence_may_override"] is False
    assert result.metadata["health_clinical_status_preserved"] is True
    assert result.metadata["competing_hypothesis_present"] is True
    assert result.metadata["competing_hypothesis_discussable"] is True
    assert result.metadata["competing_hypothesis_promoted"] is False
    assert result.metadata["medication_change_blocked"] is True
    assert result.metadata["treatment_change_blocked"] is True


def test_medication_and_treatment_mutation_remain_blocked():
    rules = _rules()
    rule = rules["neurodivergence.clinical_status_authority"]

    for requested in ("change_medication", "adjust_medication", "change_treatment"):
        result = rule.evaluate(
            _context(
                clinical_claim={
                    "medication": True,
                    "treatment_plan": True,
                    "requested": requested,
                }
            )
        )
        assert result.status is ReasoningRuleResultStatus.BLOCKED
        assert result.metadata["neurodivergence_may_override"] is False
        assert result.metadata["autonomous_medical_action"] is False


def test_clinical_status_authority_applies_when_no_override_is_requested():
    rules = _rules()
    rule = rules["neurodivergence.clinical_status_authority"]

    result = rule.evaluate(
        _context(
            clinical_claim={
                "documented_diagnosis": True,
                "competing_hypothesis": "adhd",
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["primary_authority"] == "domain:health"
    assert result.metadata["competing_hypothesis_discussable"] is True


# ── Health clinical authority boundary (Task 9) ──────────────────────────────


def test_health_clinical_status_survives_a_competing_neurodivergence_hypothesis():
    """A competing hypothesis stays discussable; Health keeps the status.

    The competing Neurodivergence hypothesis is genuinely present, so the
    boundary is proven against a real competing claim rather than an empty one.
    """
    rules = _rules()
    rule = rules["neurodivergence.clinical_status_authority"]

    result = rule.evaluate(
        _context(
            clinical_claim={
                "documented_diagnosis": True,
                "diagnosis_status": "confirmed",
                "medication": True,
                "treatment_plan": True,
                "competing_hypothesis": "autism",
                "requested": "set_diagnosis",
            }
        )
    )

    # The competing hypothesis is present and may still be explored...
    assert result.metadata["competing_hypothesis_present"] is True
    assert result.metadata["competing_hypothesis_discussable"] is True
    # ...but it never replaces, promotes over or rewrites the Health status.
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["primary_authority"] == "domain:health"
    assert result.metadata["health_clinical_status_preserved"] is True
    assert result.metadata["neurodivergence_may_override"] is False
    assert result.metadata["competing_hypothesis_promoted"] is False

    finding = result.findings[0]
    assert finding.metadata["primary_authority"] == "domain:health"
    assert finding.metadata["health_clinical_status_preserved"] is True


def test_documented_medical_contraindication_is_not_mutable_here():
    """Medical contraindication authority never moves to Neurodivergence."""
    rules = _rules()
    rule = rules["neurodivergence.clinical_status_authority"]

    result = rule.evaluate(
        _context(
            clinical_claim={
                "medical_contraindication": True,
                "medical_safety": True,
                "requested": "override_contraindication",
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["primary_authority"] == "domain:health"
    assert result.metadata["autonomous_medical_action"] is False
    assert result.metadata["neurodivergence_may_override"] is False


def test_a_working_hypothesis_is_never_silently_persisted():
    rules = _rules()
    rule = rules["neurodivergence.sensitive_label_persistence"]

    result = rule.evaluate(
        _context(
            persistence_request={
                "content_kind": "working_hypothesis",
                "certainty_state": "hypothesis",
            }
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["direct_write_performed"] is False
    assert result.metadata["proposal_required"] is True
    assert result.metadata["certainty_promoted"] is False


def test_an_approved_proposal_preserves_hypothesis_status():
    rules = _rules()
    rule = rules["neurodivergence.sensitive_label_persistence"]

    result = rule.evaluate(
        _context(
            persistence_request={
                "content_kind": "working_hypothesis",
                "certainty_state": "hypothesis",
                "authorization": {
                    "approved": True,
                    "proposal_id": "proposal-1",
                    "binding_id": "binding-1",
                },
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["direct_write_performed"] is False
    assert result.metadata["hypothesis_status_preserved"] is True
    assert result.metadata["certainty_promoted"] is False


def test_a_confirmed_diagnosis_may_never_be_persisted_by_this_pack():
    rules = _rules()
    rule = rules["neurodivergence.sensitive_label_persistence"]

    result = rule.evaluate(
        _context(
            persistence_request={
                "content_kind": "confirmed_diagnosis",
                "certainty_state": "hypothesis",
                "authorization": {
                    "approved": True,
                    "proposal_id": "proposal-1",
                    "binding_id": "binding-1",
                },
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["direct_write_performed"] is False
    assert result.metadata["proposal_required"] is True


def test_a_proposal_may_not_upgrade_hypothesis_to_confirmed():
    rules = _rules()
    rule = rules["neurodivergence.sensitive_label_persistence"]

    result = rule.evaluate(
        _context(
            persistence_request={
                "content_kind": "working_hypothesis",
                "certainty_state": "hypothesis",
                "proposed_state": "confirmed",
                "authorization": {
                    "approved": True,
                    "proposal_id": "proposal-1",
                    "binding_id": "binding-1",
                },
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["certainty_promoted"] is True
    assert result.metadata["direct_write_performed"] is False


# ── Cross-domain minimization ────────────────────────────────────────────────


def _projection(**fields):
    return {
        "purpose": "differential_context",
        "fields": {name: {"relevant": True, "value": True} for name in fields},
    }


def test_cross_domain_minimization_excludes_unbound_fields():
    rules = _rules()
    rule = rules["neurodivergence.purpose_minimized_cross_domain"]

    result = rule.evaluate(
        _context(
            projection=_projection(
                emotional_context=True,
                therapy_notes=True,
                unrelated_field=True,
            ),
            transfers=(_canonical_transfer("emotional_context"),),
        )
    )

    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.metadata["included_fields"] == ("emotional_context",)
    assert "therapy_notes" in result.metadata["excluded_fields"]
    # Relevant fields with no transfer of their own stay excluded: one accepted
    # transfer never authorizes another field.
    assert set(result.metadata["unbound_fields"]) == {
        "therapy_notes",
        "unrelated_field",
    }
    assert result.metadata["provenance_preserved"] is True
    assert result.metadata["provenance_references"] == ("finding:mental-health:7",)


def test_an_unrelated_transfer_authorizes_nothing():
    rules = _rules()
    rule = rules["neurodivergence.purpose_minimized_cross_domain"]

    result = rule.evaluate(
        _context(
            projection=_projection(emotional_context=True),
            transfers=(_canonical_transfer("documented_medication_change"),),
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["included_fields"] == ()
    assert result.metadata["provenance_preserved"] is False


def test_structural_transfer_alone_is_not_current_authority():
    """A matching transfer with no current authority admits no field."""
    rules = _rules()
    rule = rules["neurodivergence.purpose_minimized_cross_domain"]

    projection = _projection(emotional_context=True)
    projection["permission_authority"] = False

    result = rule.evaluate(
        _context(
            projection=projection,
            transfers=(_canonical_transfer("emotional_context"),),
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["included_fields"] == ()
    assert result.metadata["permission_authority"] is False
    assert result.metadata["provenance_preserved"] is False


def test_malformed_relevance_never_includes_a_cross_domain_field():
    rules = _rules()
    rule = rules["neurodivergence.purpose_minimized_cross_domain"]

    result = rule.evaluate(
        _context(
            projection={
                "purpose": "differential_context",
                "fields": {"emotional_context": {"relevant": "yes"}},
            },
            transfers=(_canonical_transfer("emotional_context"),),
        )
    )
    assert result.metadata["included_fields"] == ()
    assert result.status is ReasoningRuleResultStatus.BLOCKED


def test_cross_domain_import_requires_a_purpose_and_canonical_provenance():
    rules = _rules()
    rule = rules["neurodivergence.purpose_minimized_cross_domain"]

    no_purpose = rule.evaluate(
        _context(
            projection={"fields": {"emotional_context": {"relevant": True}}},
            transfers=(_canonical_transfer("emotional_context"),),
        )
    )
    assert no_purpose.status is ReasoningRuleResultStatus.BLOCKED
    assert no_purpose.metadata["included_fields"] == ()

    untyped = rule.evaluate(
        _context(
            projection=_projection(emotional_context=True),
            transfers=({"identifier": "emotional_context", "provenance": ["x"]},),
        )
    )
    assert untyped.status is ReasoningRuleResultStatus.BLOCKED
    assert untyped.metadata["included_fields"] == ()
    assert "malformed_transfer" in untyped.metadata["rejected_transfers"]
