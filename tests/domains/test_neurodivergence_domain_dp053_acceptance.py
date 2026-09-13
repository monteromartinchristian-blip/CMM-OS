"""AT-DP-053 — Phase 10.53 Neurodivergence Domain connected acceptance.

Every checkpoint uses real canonical components (or their official in-memory
implementations): the canonical registries, resolver, profile registry,
permission resolver, ``DomainPermissionGate``, ``ApprovalService`` with the
official in-memory repository, the canonical privacy composer, the Phase 10.18
memory validator, the real ``KnowledgePackageBuilder`` and the Phase 10.17 trace
assembler/validator.

The acceptance is connected, not mocked: checkpoints that prove a denial
deliberately carry a structurally valid matching transfer, and checkpoints that
prove exploratory usefulness require applied hypothesis-bearing behavior rather
than "not blocked".
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cmm.cognitive import (
    Confidence,
    InMemoryKnowledgeStore,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackageRequest,
)
from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.knowledge_packages import KnowledgePackageBuilder
from cmm.cognitive.privacy import (
    PrivacyPolicy,
    ProcessingLocation,
    resolve_effective_privacy_metadata,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.general import GENERAL_DOMAIN_ID
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_validation import validate_domain_knowledge_package
from cmm.domains.neurodivergence import (
    NEURODIVERGENCE_DOMAIN_ID,
    NEURODIVERGENCE_PROFILE_NAME,
    build_neurodivergence_domain_definition,
    build_neurodivergence_knowledge_package_schema,
    build_neurodivergence_privacy_policy,
    build_standard_neurodivergence_domain_bootstrap,
)
from cmm.domains.neurodivergence.integration import register_neurodivergence_domain
from cmm.domains.neurodivergence.rules import build_neurodivergence_rules
from cmm.domains.privacy_policy_contracts import project_domain_privacy_metadata
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)
from cmm.domains.trace_contracts import (
    DomainTraceDomainSelection,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)
from tests.domains.test_neurodivergence_domain_architecture import (
    FORBIDDEN_OWNER_NAMES,
    PACKAGE_DIR,
)
from tests.domains.test_neurodivergence_domain_memory import _full_chain
from tests.domains.test_neurodivergence_domain_permissions import (
    CROSS_DOMAIN_PURPOSE,
    _admit_cross_domain_transfers,
    _authorized_cross_domain_resolver,
    _canonical_transfer,
    _connected_permission_stack,
    _cross_domain_request,
    _evaluate_minimization,
    _grant_canonical_cross_domain_approval,
    _minimization_projection,
)

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
NEURODIVERGENCE = DomainId(slug="neurodivergence")
GENERAL = DomainId(slug="general")
HEALTH = DomainId(slug="health")
MENTAL_HEALTH = DomainId(slug="mental-health")


def _rules():
    return {rule.definition.id: rule for rule in build_neurodivergence_rules()}


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="at-rid",
        timestamp=NOW,
        active_domains=(NEURODIVERGENCE_DOMAIN_ID,),
        primary_domain=NEURODIVERGENCE_DOMAIN_ID,
        metadata=metadata,
    )


def _bootstrap():
    return build_standard_neurodivergence_domain_bootstrap()


def _signal(domain, value):
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=(domain,),
        confidence=0.9,
        provenance={"source": "test"},
    )


def _resolution_context(bootstrap, *, objective, explicit=(), signals=()):
    available = tuple(definition.id for definition in bootstrap.domain_registry.list())
    return DomainResolutionContext(
        id="at-ctx-1",
        objective=objective,
        available_domains=available,
        authorized_domains=available,
        explicit_domains=explicit,
        system_policy=None,
        signals=signals,
        created_at=NOW,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoints 1–8
# ═══════════════════════════════════════════════════════════════════════════════


def test_checkpoint_01_canonical_registration():
    """domain:neurodivergence registers through the canonical registry path."""
    bootstrap = _bootstrap()
    definition = bootstrap.domain_registry.get(NEURODIVERGENCE_DOMAIN_ID)

    assert definition is not None
    assert str(definition.id) == "domain:neurodivergence"
    assert definition.version == "1.0.0"
    assert str(bootstrap.domain_registry.get(GENERAL_DOMAIN_ID).id) == (
        "domain:general"
    )

    # A second registration of the same pack is rejected without mutation.
    from cmm.domains.errors import DomainError

    with pytest.raises(DomainError):
        register_neurodivergence_domain(
            domain_registry=bootstrap.domain_registry,
            profile_registry=bootstrap.profile_registry,
            resource_registry=bootstrap.resource_registry,
            rule_registry=bootstrap.rule_registry,
            operation_registry=bootstrap.operation_registry,
            workflow_registry=bootstrap.workflow_registry,
            permission_registry=bootstrap.permission_registry,
        )


def test_checkpoint_02_profile_resolution():
    """NeurodivergenceProfile resolves through the real profile registry."""
    bootstrap = _bootstrap()

    registered = bootstrap.profile_registry.get_by_domain(NEURODIVERGENCE)
    assert registered is not None
    assert registered.profile_name == NEURODIVERGENCE_PROFILE_NAME
    assert registered.required_rules == tuple(
        rule.definition.id for rule in build_neurodivergence_rules()
    )

    # Resolution still picks Neurodivergence for an explicit request.
    result = bootstrap.resolver.resolve(
        _resolution_context(
            bootstrap,
            objective="explore whether this could fit a hypothesis",
            explicit=(NEURODIVERGENCE,),
            signals=(
                _signal(NEURODIVERGENCE, "explore-neurodevelopmental-hypothesis"),
            ),
        )
    )
    assert result.primary_domain == NEURODIVERGENCE


def test_checkpoint_03_exploratory_inference_is_allowed():
    """Exploration produces useful hypothesis-oriented reasoning, not a block."""
    rule = _rules()["neurodivergence.differential_explanations"]

    result = rule.evaluate(
        _context(
            exploration={
                "objective": "Could these social and sensory patterns fit autism?",
                "hypothesis": "autism",
                "supporting": ({"id": "obs-1"}, {"id": "obs-2"}),
                "unclear": ({"id": "gap-1"},),
                "conflicting": ({"id": "con-1"},),
                "alternatives": ({"id": "alt-1"},),
                "clarifying_evidence": ({"id": "next-1"},),
            }
        )
    )

    assert result.status.value == "applied"
    assert result.metadata["exploratory_model_inference"] == "allowed"
    assert result.metadata["exploration_performed"] is True
    assert result.metadata["reasoning_present"] is True
    assert result.metadata["refusal_generated"] is False
    assert result.metadata["disclaimer_only_output"] is False
    # Useful applied behavior: every exploratory category was surfaced.
    assert set(result.metadata["categories_covered"]) == {
        "supporting",
        "unclear",
        "conflicting",
        "alternatives",
        "clarifying_evidence",
    }


def test_checkpoint_04_exploratory_inference_is_not_promoted_to_diagnosis():
    """MODEL_INFERENCE_TO_CONFIRMED_DIAGNOSIS=BLOCKED."""
    exploration_rule = _rules()["neurodivergence.differential_explanations"]
    certainty_rule = _rules()["neurodivergence.certainty_state_preservation"]

    exploration = exploration_rule.evaluate(
        _context(
            exploration={
                "objective": "Could this fit autism?",
                "hypothesis": "autism",
                "supporting": ({"id": "obs-1"},),
            }
        )
    )
    assert exploration.metadata["hypothesis_state"] == "hypothesis"
    assert exploration.metadata["confirmed_diagnosis_created"] is False

    promotion = certainty_rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": "claim-1",
                "from_state": "hypothesis",
                "to_state": "confirmed",
                "evidence_kind": "model_interpretation",
                "clinical": True,
            }
        )
    )
    assert promotion.status.value == "blocked"
    assert promotion.metadata["confirmed_diagnosis_created"] is False
    assert promotion.metadata["certified_here"] is False


def test_checkpoint_05_certainty_hierarchy_is_preserved():
    """Confirmed / in-evaluation / hypothesis / negative states stay distinct."""
    from cmm.domains.neurodivergence.rules import (
        CERTAINTY_CONFIRMED,
        CERTAINTY_HYPOTHESIS,
        CERTAINTY_IN_EVALUATION,
        CERTAINTY_INSUFFICIENTLY_SUPPORTED,
        CERTAINTY_NOT_CONFIRMED,
        CERTAINTY_RULED_OUT,
        describe_certainty_state,
    )

    distinct = {
        CERTAINTY_CONFIRMED,
        CERTAINTY_IN_EVALUATION,
        CERTAINTY_HYPOTHESIS,
        CERTAINTY_NOT_CONFIRMED,
        CERTAINTY_RULED_OUT,
        CERTAINTY_INSUFFICIENTLY_SUPPORTED,
    }
    assert len(distinct) == 6
    assert CERTAINTY_NOT_CONFIRMED != CERTAINTY_RULED_OUT
    assert CERTAINTY_INSUFFICIENTLY_SUPPORTED != CERTAINTY_RULED_OUT
    assert CERTAINTY_IN_EVALUATION != CERTAINTY_CONFIRMED
    assert CERTAINTY_HYPOTHESIS != CERTAINTY_CONFIRMED

    # The labels are derived and non-authoritative, and no upward transition
    # happens without the owning authority.
    for state in distinct:
        assert describe_certainty_state(state)["certified_here"] is False
    assert (
        describe_certainty_state(CERTAINTY_NOT_CONFIRMED)["implies_exclusion"] is False
    )
    assert describe_certainty_state(CERTAINTY_RULED_OUT)["requires_authority"] is True

    certainty_rule = _rules()["neurodivergence.certainty_state_preservation"]
    blocked = certainty_rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": "c-2",
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "screening",
                "clinical": True,
            }
        )
    )
    assert blocked.status.value == "blocked"
    assert blocked.metadata["certainty_state"] == "in_evaluation"


@pytest.mark.parametrize("source_kind", ("screening", "self_report"))
def test_checkpoint_06_screening_and_self_report_are_not_promoted(source_kind):
    certainty_rule = _rules()["neurodivergence.certainty_state_preservation"]
    result = certainty_rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": "c-3",
                "from_state": "hypothesis",
                "to_state": "confirmed",
                "evidence_kind": source_kind,
                "clinical": True,
            }
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["confirmed_diagnosis_created"] is False

    # Screening additionally cannot claim to be a diagnosis on its own.
    if source_kind == "screening":
        screening_rule = _rules()["neurodivergence.screening_diagnosis_separation"]
        promoted = screening_rule.evaluate(
            _context(
                screening={
                    "instrument": "screening-instrument",
                    "source_ref": "screening:1",
                    "claimed_as_diagnosis": True,
                }
            )
        )
        assert promoted.status.value == "blocked"
        assert promoted.metadata["screening_promoted_to_diagnosis"] is False
        assert promoted.metadata["diagnosis_created"] is False


def test_checkpoint_07_developmental_chronology_is_preserved():
    rule = _rules()["neurodivergence.developmental_temporality"]

    historical = rule.evaluate(
        _context(
            temporal_claim={
                "claim_id": "t-1",
                "observed_period": "historical",
                "observation_kind": "retrospective",
                "generalized_to": "current_impairment",
            }
        )
    )
    assert historical.status.value == "blocked"
    assert historical.metadata["temporal_generalization_blocked"] is True
    assert historical.metadata["current_vs_historical_distinguished"] is True
    assert historical.metadata["historical_trait_created_current_impairment"] is False

    current = rule.evaluate(
        _context(
            temporal_claim={
                "claim_id": "t-2",
                "observed_period": "current",
                "observation_kind": "contemporaneous",
                "generalized_to": "current_impairment",
            }
        )
    )
    assert current.status.value == "applied"
    assert current.metadata["temporal_generalization_blocked"] is False

    retrospective = rule.evaluate(
        _context(
            temporal_claim={
                "claim_id": "t-3",
                "observed_period": "historical",
                "observation_kind": "retrospective",
                "presented_as": "contemporaneous",
            }
        )
    )
    assert retrospective.status.value == "blocked"
    assert retrospective.metadata["retrospective_as_contemporaneous"] is True


def test_checkpoint_08_observer_and_source_separation():
    from cmm.cognitive.enums import ResourceSourceKind
    from cmm.cognitive.resources import ResourceProvenance

    rule = _rules()["neurodivergence.observation_report_separation"]
    provenance = ResourceProvenance(
        source_type=ResourceSourceKind.UPLOADED_FILE,
        source_id="assessment-report-1",
    ).to_dict()

    result = rule.evaluate(
        _context(
            evidence_items=(
                {
                    "id": "e1",
                    "evidence_type": "direct_observation",
                    "source_ref": "observer:parent-1",
                },
                {
                    "id": "e2",
                    "evidence_type": "retrospective_self_report",
                    "source_ref": "self:user-1",
                },
                {
                    "id": "e3",
                    "evidence_type": "third_party_report",
                    "source_ref": "report:school-1",
                },
            ),
            source_provenance=provenance,
        )
    )

    assert result.status.value == "applied"
    assert set(result.metadata["evidence_classes"]) == {
        "direct_observation",
        "retrospective_self_report",
        "third_party_report",
    }
    assert result.metadata["report_collapsed_into_observation"] is False
    assert result.metadata["provenance_preserved"] is True
    assert result.metadata["unprovenanced_evidence_ids"] == ()

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
    assert collapsed.status.value == "blocked"
    assert collapsed.metadata["report_collapsed_into_observation"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoints 9–14
# ═══════════════════════════════════════════════════════════════════════════════


def test_checkpoint_09_balanced_differential_reasoning():
    """A/why-it-fits/B-overlap/what-would-clarify, without adversarial default."""
    rule = _rules()["neurodivergence.differential_explanations"]

    supports_and_alternatives = rule.evaluate(
        _context(
            exploration={
                "objective": "Why might this fit? What else could explain it?",
                "hypothesis": "autism",
                "supporting": ({"id": "obs-1"},),
                "alternatives": ({"id": "alt-anxiety"},),
                "clarifying_evidence": ({"id": "next-school-records"},),
            }
        )
    )
    assert supports_and_alternatives.status.value == "applied"
    assert set(supports_and_alternatives.metadata["categories_covered"]) == {
        "supporting",
        "alternatives",
        "clarifying_evidence",
    }
    # No negative-evidence category was present, and none was manufactured.
    assert supports_and_alternatives.metadata["negative_evidence_required"] is False
    assert supports_and_alternatives.metadata["fabricated_negative_evidence"] is False
    assert supports_and_alternatives.metadata["differential_reasoning"] == (
        "balanced_not_adversarial"
    )

    # When the user does ask why it may not fit, the answer surfaces both sides.
    both_sides = rule.evaluate(
        _context(
            exploration={
                "objective": "Why might it not fit?",
                "hypothesis": "autism",
                "supporting": ({"id": "obs-1"},),
                "conflicting": ({"id": "con-1"},),
                "unclear": ({"id": "gap-1"},),
            }
        )
    )
    assert both_sides.status.value == "applied"
    assert {"supporting", "conflicting", "unclear"} <= set(
        both_sides.metadata["categories_covered"]
    )

    overlap = _rules()["neurodivergence.overlap_reasoning"].evaluate(
        _context(
            overlap={
                "hypotheses": ("autism", "adhd"),
                "overlapping_features": ({"id": "f1"},),
                "distinguishing_evidence": ({"id": "d1"},),
            }
        )
    )
    assert overlap.status.value == "applied"
    assert overlap.metadata["overlap_considered"] is True
    assert overlap.metadata["co_diagnosis_created"] is False
    assert overlap.metadata["overlap_is_not_co_diagnosis"] is True


def test_checkpoint_10_health_clinical_authority_is_preserved():
    rule = _rules()["neurodivergence.clinical_status_authority"]

    result = rule.evaluate(
        _context(
            clinical_claim={
                "documented_diagnosis": True,
                "medication": True,
                "treatment_plan": True,
                "competing_hypothesis": "autism",
                "requested": "confirm_diagnosis",
            }
        )
    )

    # The competing Neurodivergence hypothesis is present and may be discussed.
    assert result.metadata["competing_hypothesis_present"] is True
    assert result.metadata["competing_hypothesis_discussable"] is True
    # Health keeps the status; medication/treatment changes remain blocked.
    assert result.status.value == "blocked"
    assert result.metadata["primary_authority"] == "domain:health"
    assert result.metadata["health_clinical_status_preserved"] is True
    assert result.metadata["neurodivergence_may_override"] is False
    assert result.metadata["competing_hypothesis_promoted"] is False
    assert result.metadata["medication_change_blocked"] is True
    assert result.metadata["treatment_change_blocked"] is True
    assert result.metadata["autonomous_medical_action"] is False


def test_checkpoint_11_current_permission_deny_blocks_a_matching_transfer():
    from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome

    real_resolver = _real_neurodivergence_resolver()
    _approval_service, gate = _connected_permission_stack(real_resolver)
    request = _cross_domain_request("req-at-dp-053-deny", "denied_field")
    candidate = _canonical_transfer("denied_field", provenance=("prov:denied",))

    decision = real_resolver.resolve_cross_domain(request, now=NOW)
    assert decision.decision is PermissionOutcome.DENY

    # The withheld evidence is genuinely matching and would pass minimization.
    assert candidate["identifier"] in request.resource_ids
    assert candidate["source_domain"] == request.source_domain
    assert candidate["target_domain"] == request.target_domain
    assert candidate["reason"] == request.reason
    assert candidate["transferable"] is True
    assert candidate["private"] is False
    ungated = _evaluate_minimization(
        _minimization_projection(denied_field=True), (candidate,)
    )
    assert ungated.metadata["included_fields"] == ("denied_field",)

    decision, gate_result, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=(candidate,),
        resolver=real_resolver,
        gate=gate,
    )
    assert decision.decision is PermissionOutcome.DENY
    assert gate_result.allowed is False
    assert admitted == ()
    gated = _evaluate_minimization(
        _minimization_projection(denied_field=True), admitted
    )
    assert gated.status.value == "blocked"
    assert gated.metadata["included_fields"] == ()
    assert gated.metadata["provenance_preserved"] is False
    assert gated.metadata["source_domains"] == ()


def _real_neurodivergence_resolver():
    """Resolver over the *live* Neurodivergence permission registry only.

    No source-domain policy is registered, so the canonical resolver has no
    grant path into Neurodivergence: the DENY is the real current decision.
    """
    from cmm.domains.permission_resolution import DomainPermissionResolver

    return DomainPermissionResolver(_bootstrap().permission_registry)


def test_checkpoint_12_approval_required_without_consumption_blocks():
    from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
    from cmm.domains.permission_gate import PermissionGateOutcome

    authorized_resolver = _authorized_cross_domain_resolver()
    _approval_service, gate = _connected_permission_stack(authorized_resolver)
    request = _cross_domain_request("req-at-dp-053-pending", "emotional_context")
    candidate = _canonical_transfer("emotional_context")

    decision, gate_result, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=(candidate,),
        resolver=authorized_resolver,
        gate=gate,
    )
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert decision.approval_requirements
    assert gate_result.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    assert gate_result.allowed is False
    assert admitted == ()

    result = _evaluate_minimization(
        _minimization_projection(emotional_context=True), admitted
    )
    assert result.status.value == "blocked"
    assert result.metadata["included_fields"] == ()

    # The SENSITIVE floor was not lowered to manufacture a direct ALLOW.
    floor = resolve_effective_privacy_metadata(
        project_domain_privacy_metadata(
            build_neurodivergence_privacy_policy(),
            processing_location=ProcessingLocation.LOCAL,
        )
    ).effective
    assert floor.sensitivity is SensitivityLevel.SENSITIVE


def test_checkpoint_13_consumed_approval_admits_the_exact_transfer():
    from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
    from cmm.domains.permission_gate import PermissionGateOutcome

    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    request = _cross_domain_request("req-at-dp-053-approved", "emotional_context")
    candidates = (_canonical_transfer("emotional_context"),)

    decision, pending, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=candidates,
        resolver=authorized_resolver,
        gate=gate,
    )
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    assert admitted == ()

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, request
    )
    assert approval_service.repository.get_request(approval_request_id) is not None

    decision, consumed, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=candidates,
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert consumed.allowed is True
    evidence = consumed.approval_evidence
    assert evidence["granted"] is True
    assert evidence["consumed"] is True
    assert evidence["requirement_id"] == f"cross-domain:{request.request_id}"
    assert admitted == candidates

    result = _evaluate_minimization(
        _minimization_projection(emotional_context=True), admitted
    )
    assert result.status.value == "applied"
    assert result.metadata["included_fields"] == ("emotional_context",)


# ── Audit V1 MAJOR-01: genuine canonical Health authority still promotes ─────


def _canonical_clinical_status_transfer(identifier, *, reason=CROSS_DOMAIN_PURPOSE):
    """A canonical Health clinical-status transfer carrying Health-owned proof."""
    from cmm.cognitive.enums import ResourceSourceKind
    from cmm.cognitive.resources import ResourceProvenance
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer

    return CrossDomainContextTransfer(
        source_domain=HEALTH,
        target_domain=NEURODIVERGENCE,
        kind="clinical_status",
        identifier=identifier,
        value={
            "documented_diagnosis": True,
            "provenance": ResourceProvenance(
                source_type=ResourceSourceKind.UPLOADED_FILE,
                source_id="clinical-record:nd-1",
            ).to_dict(),
        },
        reason=reason,
        provenance=("clinical-record:nd-1",),
    ).to_dict()


def test_canonical_health_authority_confirms_through_the_connected_path():
    """CANONICAL_HEALTH_AUTHORITY_TO_CONFIRMED=PASS on the real canonical path.

    The clinical-status transfer is admitted only after the real canonical
    ``DomainPermissionResolver``, ``DomainPermissionGate`` and ``ApprovalService``
    lifecycle produce APPROVAL_CONSUMED for this exact request; the certainty
    rule then promotes using that admitted evidence.
    """
    from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
    from cmm.domains.permission_gate import PermissionGateOutcome

    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    request = _cross_domain_request("req-at-dp-053-authority", "clinical_status")
    candidate = _canonical_clinical_status_transfer("clinical_status")

    decision, pending, unadmitted = _admit_cross_domain_transfers(
        request=request,
        candidates=(candidate,),
        resolver=authorized_resolver,
        gate=gate,
    )
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    assert unadmitted == ()

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, request
    )
    _decision, consumed, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=(candidate,),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert consumed.allowed is True
    assert admitted == (candidate,)

    rule = _rules()["neurodivergence.certainty_state_preservation"]
    result = rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": "clinical_status",
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CROSS_DOMAIN_PURPOSE,
                "permission_authority": consumed.allowed,
                "transfers": admitted,
            }
        )
    )

    assert result.status.value == "applied"
    assert result.metadata["certainty_state"] == "confirmed"
    assert result.metadata["promotion_blocked"] is False
    assert result.metadata["authoritative_evidence"] is True
    assert result.metadata["health_authority_supplied"] is True
    assert result.metadata["canonical_authority"]["source_domain"] == "domain:health"
    assert result.metadata["canonical_authority"]["claim_id"] == "clinical_status"
    assert result.metadata["confirmed_diagnosis_created"] is False

    # The same canonical transfer without admitted current authority, and the
    # same transfer under a real canonical DENY, confirm nothing.
    without_authority = rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": "clinical_status",
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CROSS_DOMAIN_PURPOSE,
                "permission_authority": False,
                "transfers": (candidate,),
            }
        )
    )
    assert without_authority.status.value == "blocked"
    assert without_authority.metadata["certainty_state"] == "in_evaluation"

    denied_resolver = _real_neurodivergence_resolver()
    _approval_service, denied_gate = _connected_permission_stack(denied_resolver)
    denied_request = _cross_domain_request(
        "req-at-dp-053-authority-deny", "clinical_status"
    )
    denied_decision, denied_gate_result, denied_admitted = (
        _admit_cross_domain_transfers(
            request=denied_request,
            candidates=(candidate,),
            resolver=denied_resolver,
            gate=denied_gate,
        )
    )
    assert denied_decision.decision is PermissionOutcome.DENY
    assert denied_gate_result.allowed is False
    assert denied_admitted == ()

    denied = rule.evaluate(
        _context(
            certainty_transition={
                "claim_id": "clinical_status",
                "from_state": "in_evaluation",
                "to_state": "confirmed",
                "evidence_kind": "documented_clinical_status",
                "clinical": True,
                "purpose": CROSS_DOMAIN_PURPOSE,
                "permission_authority": denied_gate_result.allowed,
                "transfers": denied_admitted,
            }
        )
    )
    assert denied.status.value == "blocked"
    assert denied.metadata["certainty_state"] == "in_evaluation"
    assert denied.metadata["authoritative_evidence"] is False


def test_checkpoint_14_authority_tuple_binding_is_exact():
    from cmm.domains.permission_gate import PermissionGateOutcome

    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    field_a = _cross_domain_request("req-at-dp-053-binding", "field_a")
    field_b = _cross_domain_request("req-at-dp-053-binding", "field_b")

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, field_a
    )

    # Approval for resource A admits exactly A.
    _decision, gate_a, admitted_a = _admit_cross_domain_transfers(
        request=field_a,
        candidates=(_canonical_transfer("field_a"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_a.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert admitted_a == (_canonical_transfer("field_a"),)

    # The same consumed approval cannot authorize resource B.
    _decision, gate_b, admitted_b = _admit_cross_domain_transfers(
        request=field_b,
        candidates=(_canonical_transfer("field_b"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_b.allowed is False
    assert admitted_b == ()

    # Nor the same resource for another actor.
    other_actor = _cross_domain_request(
        "req-at-dp-053-binding", "field_a", actor_id="user-2"
    )
    _decision, gate_actor, admitted_actor = _admit_cross_domain_transfers(
        request=other_actor,
        candidates=(_canonical_transfer("field_a"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_actor.allowed is False
    assert admitted_actor == ()

    # Nor a different session.
    other_session = _cross_domain_request(
        "req-at-dp-053-binding", "field_a", session_id="session-2"
    )
    _decision, gate_session, admitted_session = _admit_cross_domain_transfers(
        request=other_session,
        candidates=(_canonical_transfer("field_a"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_session.allowed is False
    assert admitted_session == ()

    # Nor a different purpose: the authority was already consumed for field_a,
    # and a transfer filed under another purpose is never admitted.
    purpose_request = _cross_domain_request("req-at-dp-053-binding", "field_a")
    _decision, _gate_purpose, admitted_purpose = _admit_cross_domain_transfers(
        request=purpose_request,
        candidates=(_canonical_transfer("field_a", reason="assessment_summary"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert admitted_purpose == ()


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoints 15–20
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("source_domain", "field", "checkpoint"),
    (
        ("domain:mental-health", "emotional_context", 15),
        ("domain:university", "academic_accommodation", 16),
        ("domain:relationships", "social_interaction_context", 17),
    ),
)
def test_checkpoints_15_to_17_sibling_source_authority_is_preserved(
    source_domain, field, checkpoint
):
    """Imported context keeps its sibling owner; Neurodivergence never owns it."""
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer

    assert checkpoint in {15, 16, 17}
    transfer = CrossDomainContextTransfer(
        source_domain=source_domain,
        target_domain=NEURODIVERGENCE_DOMAIN_ID,
        kind="finding",
        identifier=field,
        value=True,
        reason="differential_context",
        provenance=(f"finding:{source_domain}:1",),
    ).to_dict()

    result = _evaluate_minimization(
        _minimization_projection(**{field: True}), (transfer,)
    )

    assert result.status.value == "applied"
    assert result.metadata["included_fields"] == (field,)
    assert result.metadata["source_domains"] == (source_domain,)
    assert NEURODIVERGENCE_DOMAIN_ID not in result.metadata["source_domains"]

    # The source-authority rule reports the same owner and refuses re-emission.
    source_rule = _rules()["neurodivergence.source_authority"]
    owned = source_rule.evaluate(
        _context(
            source_claims=(
                {
                    "id": "c1",
                    "source_domain": source_domain,
                    "fact": field,
                    "re_emitted_as": NEURODIVERGENCE_DOMAIN_ID,
                },
            )
        )
    )
    assert owned.status.value == "blocked"
    assert owned.metadata["rewritten_claims"] == ("c1",)
    assert owned.metadata["source_authority_preserved"] is False


def test_checkpoint_18_cross_domain_minimization_prevents_laundering():
    """One accepted field never authorizes another field."""
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionCapability as _Capability,
    )
    from cmm.domains.permission_gate import PermissionGateOutcome

    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    request = _cross_domain_request("req-at-dp-053-launder", "field_a")
    assert _Capability.DOMAIN_CROSS_ACCESS is _Capability.DOMAIN_CROSS_ACCESS

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, request
    )
    # field_b has its own structurally valid transfer but was not requested;
    # field_c has no transfer at all.
    _decision, consumed, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=(
            _canonical_transfer("field_a"),
            _canonical_transfer("field_b"),
        ),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    # Only the requested, authorized identifier is admitted.
    assert admitted == (_canonical_transfer("field_a"),)

    result = _evaluate_minimization(
        _minimization_projection(field_a=True, field_b=True, field_c=True),
        admitted,
    )
    assert result.status.value == "applied"
    assert result.metadata["included_fields"] == ("field_a",)
    assert set(result.metadata["excluded_fields"]) == {"field_b", "field_c"}
    assert set(result.metadata["unbound_fields"]) == {"field_b", "field_c"}
    # Provenance derives only from the transfer backing the included field.
    assert result.metadata["provenance_references"] == ("finding:health:7",)

    # An unrelated transfer grants no projection authority at all.
    unrelated = _evaluate_minimization(
        _minimization_projection(field_a=True),
        (_canonical_transfer("some_other_field"),),
    )
    assert unrelated.status.value == "blocked"
    assert unrelated.metadata["included_fields"] == ()
    assert unrelated.metadata["provenance_preserved"] is False


def test_checkpoint_19_sensitive_privacy_floor_is_enforced():
    policy = build_neurodivergence_privacy_policy()

    assert policy.default_privacy.sensitivity is SensitivityLevel.SENSITIVE
    assert policy.default_privacy.policy is PrivacyPolicy.LOCAL_ONLY
    assert policy.default_privacy.allow_remote is False
    assert policy.default_privacy.allow_export is False
    assert policy.require_approval_for_remote is True
    assert policy.default_privacy.allowed_processing_locations == (
        ProcessingLocation.LOCAL,
    )

    resource_floor = resolve_effective_privacy_metadata(
        project_domain_privacy_metadata(
            policy, processing_location=ProcessingLocation.LOCAL
        )
    ).effective
    assert resource_floor.sensitivity is SensitivityLevel.SENSITIVE
    assert resource_floor.allow_remote is False
    assert resource_floor.allow_export is False

    # Composition can only strengthen: a permissive sibling cannot widen it.
    permissive = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.REMOTE
    )
    composed = resolve_effective_privacy_metadata(permissive, resource_floor).effective
    assert composed.sensitivity is SensitivityLevel.SENSITIVE
    assert composed.allow_remote is False
    assert composed.allow_export is False
    assert ProcessingLocation.REMOTE not in composed.allowed_processing_locations


def test_checkpoint_20_working_hypothesis_memory_is_proposal_first():
    from cmm.domains.memory_contracts import (
        DomainMemoryCapability,
        DomainMemoryReferenceInventory,
    )

    binding, inventory, _view, proposal = _full_chain("mp-at-dp-053")

    # A hypothesis may be proposed — and the proposal is not a mutation.
    assert proposal.requires_confirmation is True
    assert proposal.required_capabilities == (DomainMemoryCapability.PROPOSE,)
    assert DomainMemoryCapability.APPLY not in proposal.required_capabilities
    assert _validate_memory_binding(binding=binding, inventory=inventory).is_valid

    # Without canonical approval coverage the chain fails closed.
    without_approval = DomainMemoryReferenceInventory(
        references=inventory.references,
        proposals=inventory.proposals,
        permission_decisions=inventory.permission_decisions,
        traces=inventory.traces,
        views=inventory.views,
    )
    assert not _validate_memory_binding(
        binding=binding, inventory=without_approval
    ).is_valid

    # Discussing a hypothesis in reasoning performs no memory mutation at all.
    rule = _rules()["neurodivergence.sensitive_label_persistence"]
    discussion = rule.evaluate(
        _context(
            persistence_request={
                "content_kind": "working_hypothesis",
                "certainty_state": "hypothesis",
                "authorization": None,
            }
        )
    )
    assert discussion.status.value == "blocked"
    assert discussion.metadata["direct_write_performed"] is False
    assert discussion.metadata["proposal_required"] is True
    assert discussion.metadata["certainty_promoted"] is False


def _validate_memory_binding(*, binding, inventory):
    from cmm.domains.neurodivergence.memory import (
        validate_neurodivergence_memory_binding,
    )

    return validate_neurodivergence_memory_binding(binding=binding, inventory=inventory)


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoints 21–27
# ═══════════════════════════════════════════════════════════════════════════════


def test_checkpoint_21_canonical_knowledge_package_builder_path():
    store = InMemoryKnowledgeStore()
    InMemoryKnowledgeStore.save_item(
        store,
        KnowledgeItem(
            id="nd-at-item-1",
            statement="The user reported lifelong sensory sensitivity.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(0.6, source="user-report"),
        ),
    )
    builder = KnowledgePackageBuilder(store)
    package = builder.build(
        KnowledgePackageRequest(
            objective="organize developmental evidence for an assessment",
            profile=NEURODIVERGENCE_PROFILE_NAME,
            domain=NEURODIVERGENCE_DOMAIN_ID,
            session_id="session-at-dp-053",
            permission_context={"actor_id": "user-1", "effective_permissions": ()},
        )
    )
    assert package.objective == "organize developmental evidence for an assessment"

    schema = build_neurodivergence_knowledge_package_schema()
    validate_domain_knowledge_package(package, schema)

    assert schema.minimum_sensitivity is SensitivityLevel.SENSITIVE
    assert schema.id == "knowledge-package-schema:neurodivergence"
    # No second builder exists anywhere in the pack.
    for path in sorted(PACKAGE_DIR.glob("*.py")):
        assert "class KnowledgePackageBuilder" not in path.read_text(
            encoding="utf-8"
        ), path.name


def test_checkpoint_22_presentation_and_canonical_trace():
    from cmm.cognitive.privacy import (
        PrivacyOperation,
        PrivacyOperationContext,
        evaluate_privacy_operation,
    )
    from cmm.domains.neurodivergence.presentation import (
        build_neurodivergence_presentation_policy,
    )
    from cmm.domains.neurodivergence.trace import (
        assemble_neurodivergence_trace,
        build_neurodivergence_trace_contribution,
        build_neurodivergence_trace_reference,
        validate_neurodivergence_trace,
    )
    from cmm.domains.trace_contracts import PrivacyDecisionTraceEvidence

    policy = build_neurodivergence_presentation_policy()
    assert policy.include_uncertainty is True
    assert policy.include_provenance is True
    assert policy.include_alternatives is True
    assert policy.require_disclaimers is False
    assert policy.warning_position != "before_content"
    for term in ("confirmed", "in_evaluation", "hypothesis", "working_hypothesis"):
        assert term in policy.protected_terms

    # A real canonical privacy decision for a local Neurodivergence operation,
    # projected into reference-only trace evidence.
    effective_privacy = project_domain_privacy_metadata(
        build_neurodivergence_privacy_policy(),
        processing_location=ProcessingLocation.LOCAL,
    )
    decision = evaluate_privacy_operation(
        effective_privacy,
        PrivacyOperation.PROCESS_LOCAL,
        PrivacyOperationContext(
            actor_id="user-1", domain=NEURODIVERGENCE_DOMAIN_ID, at=NOW
        ),
    )
    assert decision.allowed is True
    evidence = PrivacyDecisionTraceEvidence.from_privacy_decision(
        domain_id=NEURODIVERGENCE_DOMAIN_ID,
        operation=PrivacyOperation.PROCESS_LOCAL,
        decision=decision,
    )

    contribution = build_neurodivergence_trace_contribution(
        domain_result_id="result:nd:at",
        references=(
            build_neurodivergence_trace_reference(
                ref_id="permission:at",
                kind=DomainTraceReferenceKind.PERMISSION_DECISION,
            ),
            build_neurodivergence_trace_reference(
                ref_id="approval-decision:at",
                kind=DomainTraceReferenceKind.APPROVAL_DECISION,
            ),
            build_neurodivergence_trace_reference(
                ref_id=evidence.decision_id,
                kind=DomainTraceReferenceKind.PRIVACY_DECISION,
            ),
            build_neurodivergence_trace_reference(
                ref_id="memory-proposal:at",
                kind=DomainTraceReferenceKind.MEMORY_PROPOSAL,
            ),
        ),
    )
    kinds = {reference.kind for reference in contribution.references}
    assert DomainTraceReferenceKind.PERMISSION_DECISION in kinds
    assert DomainTraceReferenceKind.APPROVAL_DECISION in kinds
    assert DomainTraceReferenceKind.PRIVACY_DECISION in kinds
    assert DomainTraceReferenceKind.MEMORY_PROPOSAL in kinds

    trace = assemble_neurodivergence_trace(
        request_id="trace-req:at",
        resolution_context_id="ctx:at",
        resolution_result_id="resolution:at",
        composition_id="composition:at",
        domain_result_id="result:nd:at",
        started_at=NOW,
        completed_at=NOW,
        references=contribution.references[1:],
    )
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        expected_primary_domain=NEURODIVERGENCE_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution:at", NEURODIVERGENCE_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:at", NEURODIVERGENCE_DOMAIN_ID, ()
        ),
        privacy_decisions=(evidence,),
    )
    assert (
        validate_neurodivergence_trace(trace=trace, inventory=inventory).valid is True
    )
    # Reference-only: no raw source body or hidden chain of thought rides along.
    serialized = str(trace.to_dict()).casefold()
    for forbidden in ("source_body", "chain_of_thought", "prompt_text"):
        assert forbidden not in serialized, forbidden


def test_checkpoint_23_operations_and_workflows_are_canonical():
    bootstrap = _bootstrap()

    operations = [
        operation
        for operation in bootstrap.operation_registry.list_definitions()
        if operation.domain_id == NEURODIVERGENCE_DOMAIN_ID
    ]
    workflows = bootstrap.workflow_registry.list_for_domain(NEURODIVERGENCE_DOMAIN_ID)

    assert len(operations) == 8
    assert len(workflows) == 8
    # Declared, reachable and fail-closed: no implementation is implied.
    assert all(operation.enabled is False for operation in operations)
    assert all(workflow.enabled is True for workflow in workflows)


def test_checkpoint_24_benchmarks_and_quality_declarations():
    definition = build_neurodivergence_domain_definition()

    assert len(definition.benchmark_suites) == 1
    suite = definition.benchmark_suites[0]
    assert suite.id == "benchmark-suite:neurodivergence:core"
    assert len(suite.cases) == 12

    metrics = definition.quality_metrics
    assert len(metrics) == 10
    assert any(metric.blocking for metric in metrics)
    # No evaluator/runtime ownership: declarations only.
    for metric in metrics:
        assert metric.metadata == {}
        assert metric.evaluator_id == f"evaluator:{metric.name}"


def test_checkpoint_25_anti_fragmentation():
    from cmm.domains.validation_fragmentation import analyze_fragmentation

    offenders: list[str] = []
    for path in sorted(PACKAGE_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        findings = analyze_fragmentation(
            source, path.relative_to(Path(__file__).resolve().parents[2]).as_posix()
        )
        assert findings == [], (path.name, findings)
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and (
                node.name in FORBIDDEN_OWNER_NAMES
            ):
                offenders.append(f"{path.name}:{node.name}")

    assert offenders == []
    assert PACKAGE_DIR.is_dir()


def test_checkpoint_26_first_party_inventory_is_fourteen_and_zero_deferred():
    from tests.domains.domain_core_conformance_support import (
        DEFERRED_DOMAIN_IDS,
        FIRST_PARTY_DOMAIN_IDS,
        PHASE10_53_DEFERRED_DOMAIN_PACKS,
        PHASE10_53_FIRST_PARTY_DOMAIN_PACKS,
        load_first_party_definitions,
    )

    loaded = {str(definition.id) for definition in load_first_party_definitions()}

    assert NEURODIVERGENCE_DOMAIN_ID in loaded
    assert len(FIRST_PARTY_DOMAIN_IDS) == PHASE10_53_FIRST_PARTY_DOMAIN_PACKS == 14
    assert len(DEFERRED_DOMAIN_IDS) == PHASE10_53_DEFERRED_DOMAIN_PACKS == 0
    assert loaded == set(FIRST_PARTY_DOMAIN_IDS)
    # The historical DP-051 deferred pair is still preserved as evidence.
    from tests.domains.domain_core_conformance_support import (
        HISTORICAL_DEFERRED_DOMAIN_IDS,
    )

    assert len(HISTORICAL_DEFERRED_DOMAIN_IDS) == 2


def test_checkpoint_27_prior_domains_keep_their_authority_and_behavior():
    from cmm.domains.health.definition import build_health_domain_definition
    from cmm.domains.mental_health.definition import (
        build_mental_health_domain_definition,
    )
    from cmm.domains.relationships.definition import (
        build_relationships_domain_definition,
    )
    from cmm.domains.university.definition import (
        build_university_domain_definition,
    )

    # Prior packs keep their canonical definitions and their own bootstraps.
    health = build_health_domain_definition()
    mental_health = build_mental_health_domain_definition()
    university = build_university_domain_definition()
    relationships = build_relationships_domain_definition()

    assert str(health.id) == "domain:health"
    assert str(mental_health.id) == "domain:mental-health"
    assert str(university.id) == "domain:university"
    assert str(relationships.id) == "domain:relationships"

    # A Neurodivergence bootstrap does not silently absorb a sibling domain.
    neurodivergence_bootstrap = _bootstrap()
    assert not neurodivergence_bootstrap.domain_registry.contains(
        "domain:mental-health"
    )
    assert neurodivergence_bootstrap.domain_registry.contains(NEURODIVERGENCE_DOMAIN_ID)

    # A generic request still resolves to General, not Neurodivergence.
    generic = neurodivergence_bootstrap.resolver.resolve(
        _resolution_context(
            neurodivergence_bootstrap, objective="a generic non-specialized request"
        )
    )
    assert generic.primary_domain == GENERAL

    # A sibling signal that is not authorized is never absorbed by General.
    unauthorized = neurodivergence_bootstrap.resolver.resolve(
        _resolution_context(
            neurodivergence_bootstrap,
            objective="review my therapy session notes",
            signals=(_signal(MENTAL_HEALTH, "therapy-context"),),
        )
    )
    assert unauthorized.status is DomainResolutionStatus.BLOCKED
    assert unauthorized.primary_domain is None
    assert unauthorized.fallback_used is False

    # Health keeps clinical authority; a Health signal stays Health-primary in a
    # composed Health + Neurodivergence bootstrap.
    composed = _health_and_neurodivergence_bootstrap()
    health_result = composed.resolver.resolve(
        _resolution_context(
            composed,
            objective="review my documented medication contraindication",
            explicit=(HEALTH,),
            signals=(_signal(HEALTH, "documented-medication-contraindication"),),
        )
    )
    assert health_result.primary_domain == HEALTH


def _health_and_neurodivergence_bootstrap():
    from cmm.domains.health.integration import register_health_domain

    bootstrap = _bootstrap()
    register_health_domain(
        domain_registry=bootstrap.domain_registry,
        profile_registry=bootstrap.profile_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
    )
    return bootstrap


# ═══════════════════════════════════════════════════════════════════════════════
# Meta: every approved AT-DP-053 checkpoint is covered exactly once
# ═══════════════════════════════════════════════════════════════════════════════

_EXPECTED_CHECKPOINTS: tuple[int, ...] = tuple(range(1, 28))


def test_at_dp_053_all_27_checkpoints_are_covered():
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    declared = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_checkpoint")
    ]

    covered: set[int] = set()
    for name in declared:
        body = name.removeprefix("test_checkpoints").removeprefix("test_checkpoint")
        body = body.lstrip("_")
        if body.startswith("15_to_17"):
            covered.update({15, 16, 17})
        else:
            covered.add(int(body[:2]))

    assert len(_EXPECTED_CHECKPOINTS) == 27
    assert covered == set(_EXPECTED_CHECKPOINTS), sorted(
        set(_EXPECTED_CHECKPOINTS) - covered
    )
    # Every checkpoint is declared by exactly one test function.
    assert len(declared) == len(set(declared))
