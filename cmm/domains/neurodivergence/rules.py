"""Phase 10.53 — Neurodivergence Domain Rules and deterministic helpers.

A declarative domain plus pure deterministic neurodevelopmental helpers.  The
helpers are state-free: no IO, no model calls, no registry mutation, no
internal clock.  They receive context explicitly and return deterministic
structures.

The pack is deliberately **exploration-friendly**: working hypotheses, pattern
association, differential comparison and overlap reasoning are first-class
applied behavior.  What it refuses is *promotion*.

Semantic invariants preserved here (frozen design §6, §7, §11, §28):

    exploratory inference is allowed; diagnostic promotion is not;
    screening != diagnosis; self_report != confirmed status;
    observation != retrospective report != third-party report;
    trait != clinically significant impairment;
    historical != current; retrospective != contemporaneous;
    absence of corroboration != disproof; competing evidence stays visible;
    overlap != co-diagnosis; imported fact keeps its source owner;
    Health clinical status is never overwritten;
    a working hypothesis never silently becomes persistent memory;
    clinical certainty is bound to the runtime-only trusted authority channel
    and to a provenance-bound Health-owned claim, never to caller-authored
    metadata, provenance shapes or serialized authority (Audit V1/V2 MAJOR-01;
    Re-audit V3-redo MAJOR-01).

Certainty labels below are **pack-local derived labels**.  They are
non-authoritative, never persisted as a second truth, and can never upgrade
canonical Phase 8 knowledge.  No second global epistemic enum is introduced.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
    ResourceSourceKind,
)
from cmm.cognitive.errors import InvalidResourceProvenanceError
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningAuthorityContext,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)
from cmm.cognitive.resources import ResourceProvenance
from cmm.domains.cross_domain_contracts import (
    CrossDomainContextTransfer,
    CrossDomainSerializationError,
)
from cmm.domains.errors import (
    CrossDomainContractError,
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.neurodivergence.catalog import (
    CANONICAL_NEURODIVERGENCE_RULE_IDS,
    NEURODIVERGENCE_DOMAIN_ID,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

NEURODIVERGENCE_RULE_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_RULE_IDS

#: The canonical Health owner identity.  Authority comparisons use the
#: canonical ``DomainId`` contract, never a free-form domain string.
HEALTH_DOMAIN = DomainId(slug="health")

HEALTH_DOMAIN_ID = str(HEALTH_DOMAIN)

# ── Pack-local certainty labels (derived, non-authoritative) ──────────────────
# The canonical Phase 8 Cognitive Layer remains the source of truth for
# knowledge kind, provenance, uncertainty and contradictions.  These labels are
# a local, serializable vocabulary only: they grant no clinical status and can
# never upgrade canonical knowledge (frozen design §7.2).

CERTAINTY_CONFIRMED = "confirmed"
CERTAINTY_IN_EVALUATION = "in_evaluation"
CERTAINTY_HYPOTHESIS = "hypothesis"
CERTAINTY_NOT_CONFIRMED = "not_confirmed"
CERTAINTY_RULED_OUT = "ruled_out"
CERTAINTY_INSUFFICIENTLY_SUPPORTED = "insufficiently_supported"
CERTAINTY_UNKNOWN = "unknown"

#: States that may only be established by the owning authority — never here.
_AUTHORITY_REQUIRED_CERTAINTY_STATES = frozenset(
    {CERTAINTY_CONFIRMED, CERTAINTY_RULED_OUT}
)

_KNOWN_CERTAINTY_STATES = frozenset(
    {
        CERTAINTY_CONFIRMED,
        CERTAINTY_IN_EVALUATION,
        CERTAINTY_HYPOTHESIS,
        CERTAINTY_NOT_CONFIRMED,
        CERTAINTY_RULED_OUT,
        CERTAINTY_INSUFFICIENTLY_SUPPORTED,
        CERTAINTY_UNKNOWN,
    }
)

# ── Closed evidence-source classes (never collapsed into one another) ────────

EVIDENCE_DIRECT_OBSERVATION = "direct_observation"
EVIDENCE_RETROSPECTIVE_SELF_REPORT = "retrospective_self_report"
EVIDENCE_THIRD_PARTY_REPORT = "third_party_report"
EVIDENCE_CONTEMPORANEOUS_RECORD = "contemporaneous_record"
EVIDENCE_SCREENING_RESULT = "screening_result"
EVIDENCE_MODEL_INTERPRETATION = "model_interpretation"
EVIDENCE_UNKNOWN = "unknown"

_KNOWN_EVIDENCE_TYPES = frozenset(
    {
        EVIDENCE_DIRECT_OBSERVATION,
        EVIDENCE_RETROSPECTIVE_SELF_REPORT,
        EVIDENCE_THIRD_PARTY_REPORT,
        EVIDENCE_CONTEMPORANEOUS_RECORD,
        EVIDENCE_SCREENING_RESULT,
        EVIDENCE_MODEL_INTERPRETATION,
    }
)

# ── Temporal vocabulary ──────────────────────────────────────────────────────

PERIOD_HISTORICAL = "historical"
PERIOD_CURRENT = "current"
PERIOD_UNKNOWN = "unknown"

_HISTORICAL_MARKERS = frozenset({"historical", "past", "childhood", "earlier"})
_CURRENT_MARKERS = frozenset({"current", "present", "now", "recent"})

OBSERVATION_CONTEMPORANEOUS = "contemporaneous"
OBSERVATION_RETROSPECTIVE = "retrospective"
OBSERVATION_UNKNOWN = "unknown"

GENERALIZED_TO_CURRENT_IMPAIRMENT = "current_impairment"
GENERALIZED_TO_LIFELONG_PATTERN = "lifelong_pattern"

# ── Persistence vocabulary ───────────────────────────────────────────────────

#: Content kinds this pack may never persist at all — not even as a proposal.
#: These are clinical-status artifacts that only the owning authority may hold.
_NEVER_PERSISTABLE_CONTENT_KINDS = frozenset(
    {
        "confirmed_diagnosis",
        "diagnosis_assertion",
        "diagnosis_removal",
        "clinical_status",
        "clinical_authority_claim",
        "psychiatric_label",
        "psychological_diagnosis",
        "medication_change",
        "treatment_change",
        "medical_contraindication_override",
        "source_authority_rewrite",
    }
)

#: Content kinds that may only ever move through the canonical proposal path,
#: preserving their hypothesis/certainty semantics.
_PROPOSAL_REQUIRED_CONTENT_KINDS = frozenset(
    {
        "working_hypothesis",
        "diagnostic_hypothesis",
        "differential_hypothesis",
        "overlap_hypothesis",
        "developmental_pattern_candidate",
        "screening_interpretation",
        "psychometric_interpretation",
        "assessment_conclusion",
        "functional_impairment_label",
        "third_party_profile",
    }
)

_HEALTH_OWNED_CLINICAL_KEYS = (
    "documented_diagnosis",
    "diagnosis_status",
    "treatment_plan",
    "medication",
    "documented_medication_change",
    "medical_safety",
    "medical_test",
    "medical_contraindication",
    "clinical_record",
)

_CLINICAL_OVERRIDE_REQUESTS = frozenset(
    {
        "confirm_diagnosis",
        "set_diagnosis",
        "remove_diagnosis",
        "adjust_medication",
        "change_medication",
        "stop_medication",
        "start_medication",
        "change_treatment",
        "override_contraindication",
    }
)

# Source-domain slugs that never identify a real canonical transfer source.
_UNKNOWN_SOURCE_SLUGS = frozenset({"", "unknown", "unspecified", "none"})

_DIFFERENTIAL_CATEGORIES = (
    "supporting",
    "unclear",
    "conflicting",
    "alternatives",
    "clarifying_evidence",
)


def _definition(
    rule_id: str,
    name: str,
    category: str,
    priority: int,
    risk_level: ReasoningRiskLevel = ReasoningRiskLevel.LOW,
) -> DomainReasoningRuleDefinition:
    return DomainReasoningRuleDefinition(
        id=rule_id,
        name=name,
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id=NEURODIVERGENCE_DOMAIN_ID,
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=(
            "Exploration-friendly neurodevelopmental rule for " + rule_id + "."
        ),
        metadata={"phase": "10.53"},
    )


def _result(
    definition: ReasoningRuleDefinition,
    context: ReasoningRuleContext,
    status: ReasoningRuleResultStatus,
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    metadata: Mapping | None = None,
    code: str,
    message: str,
) -> ReasoningRuleResult:
    return DomainRuleResult(
        rule_id=definition.id,
        rule_name=definition.name,
        rule_version=definition.version,
        domain_id=definition.domain_id,
        status=status,
        findings=findings,
        gaps=gaps,
        escalation=None,
        trace_entries=(
            ReasoningRuleTraceEntry(
                code=code,
                message=message,
                rule_id=definition.id,
                domain_id=definition.domain_id,
                status=status,
                occurred_at=context.timestamp,
                output_count=len(findings) + len(gaps),
            ),
        ),
        metadata=dict(metadata or {}),
        started_at=context.timestamp,
        completed_at=context.timestamp,
    )


def _mapping(metadata: Mapping, key: str) -> Mapping | None:
    value = metadata.get(key)
    return value if isinstance(value, Mapping) else None


def _seq(metadata: Mapping, key: str) -> tuple | None:
    value = metadata.get(key)
    return value if isinstance(value, (list, tuple)) else None


def _strict_flag(metadata: Mapping, key: str, *, default: bool = False) -> bool:
    """Fail-closed boolean semantics for high-stakes Neurodivergence flags.

    Python truthiness makes ``bool("false")`` ``True``, so a naive read of an
    authority, evidence, relevance or promotion flag would let a malformed
    JSON-like value (``"false"``, ``"0"``, ``1``, ``0``, ``{}``, ``[]``)
    acquire a condition it must never hold.

    Only a literal ``True``/``False`` is honoured.  A missing key keeps the
    contract's documented ``default`` — absence is not malformed input.  Any
    other *present* value is malformed and fails closed to ``False``.

    This is a single local pure helper, not a registry, engine or parser.
    """
    if key not in metadata:
        return default
    value = metadata[key]
    return value if isinstance(value, bool) else False


def _finding(
    definition: ReasoningRuleDefinition,
    code: str,
    message: str,
    *,
    severity: ReasoningSeverity = ReasoningSeverity.INFO,
    references: tuple[str, ...] = (),
    metadata: Mapping | None = None,
) -> ReasoningFinding:
    return ReasoningFinding(
        code=code,
        message=message,
        severity=severity,
        rule_id=definition.id,
        domain_id=definition.domain_id,
        references=references,
        metadata=dict(metadata or {}),
    )


def _is_non_empty_id(value: Any) -> bool:
    """True only for a real, non-blank string identifier."""
    return isinstance(value, str) and bool(value.strip())


def _normalized(value: Any) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _certainty_label(value: Any) -> str:
    """Normalize a pack-local certainty label; unknown values stay unknown."""
    normalized = _normalized(value)
    return normalized if normalized in _KNOWN_CERTAINTY_STATES else CERTAINTY_UNKNOWN


def _identifier_list(items: Any) -> tuple[str, ...]:
    """Return the non-blank ``id`` of every mapping in ``items``."""
    if not isinstance(items, (list, tuple)):
        return ()
    return tuple(
        str(item.get("id")).strip()
        for item in items
        if isinstance(item, Mapping) and _is_non_empty_id(item.get("id"))
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Pure deterministic helpers
# ═══════════════════════════════════════════════════════════════════════════════


def describe_certainty_state(label: Any) -> dict:
    """Describe a pack-local certainty label's derived semantics.

    The description is explicitly non-authoritative: ``certified_here`` is
    always ``False`` because this pack can never establish ``CONFIRMED`` or
    ``RULED OUT`` clinical status.  ``NOT CONFIRMED`` is not an exclusion, and
    ``INSUFFICIENTLY SUPPORTED`` is not a contradiction.
    """
    normalized = _certainty_label(label)
    return {
        "label": normalized,
        "requires_authority": normalized in _AUTHORITY_REQUIRED_CERTAINTY_STATES,
        "implies_exclusion": normalized == CERTAINTY_RULED_OUT,
        "implies_disproof": False,
        "certified_here": False,
        "non_authoritative": True,
    }


def evaluate_certainty_transition(
    request: Mapping,
    *,
    authority_context: ReasoningAuthorityContext | None = None,
) -> dict:
    """Deterministically evaluate a proposed certainty-state transition.

    The requested transition, claim identifier, evidence kind, purpose and
    provenance references continue to come from ordinary request data.  What
    request data can never supply is **authority**: a clinical ``CONFIRMED``
    transition requires an applicable runtime-only
    :class:`~cmm.cognitive.ReasoningAuthorityContext` placed on the reasoning
    context by trusted canonical integration code after the real permission
    gate and the Health owner have both resolved their own semantics — and the
    claim must be carried there as a provenance-bound
    :class:`~cmm.cognitive.AuthoritativeSourceClaim` built from canonical
    ``ResourceProvenance``, not merely named.

    A transition to ``RULED OUT`` is never established here at all: no existing
    canonical contract encodes an authoritative *negative* clinical status, so
    an exclusion claim stays blocked rather than inventing one.  Every other
    transition is informational and is reported without being blocked.
    """
    from_state = _certainty_label(request.get("from_state"))
    to_state = _certainty_label(request.get("to_state"))
    evidence_kind = _normalized(request.get("evidence_kind"))
    clinical = _strict_flag(request, "clinical")

    authority = _trusted_health_authority(request, authority_context)

    promotes = to_state == CERTAINTY_CONFIRMED
    excludes = to_state == CERTAINTY_RULED_OUT
    requires_authority = promotes or excludes
    # The trusted channel carries a *positive* Health-owned clinical claim only,
    # so it can never carry an exclusion.
    authority_ok = promotes and authority is not None
    blocked = requires_authority and not authority_ok

    return {
        "from_state": from_state,
        "to_state": to_state,
        "certainty_state": from_state if blocked else to_state,
        "requires_authority": requires_authority,
        "authoritative_evidence": authority_ok,
        "documented_authority": authority is not None,
        "health_authority_supplied": authority is not None,
        "canonical_authority": authority,
        "promotion_blocked": blocked and promotes,
        "exclusion_blocked": blocked and excludes,
        "certified_here": False,
        "promotion_performed": False,
        "exclusion_created": False,
        "confirmed_diagnosis_created": False,
        "certainty_preserved": True,
        "evidence_kind": evidence_kind or None,
        "clinical": clinical,
    }


def classify_evidence_source(item: Mapping) -> str:
    """Return the closed evidence-source class for one evidence item.

    Direct observation, retrospective self-report, third-party report,
    contemporaneous record, screening result and model interpretation are
    separate classes and are never collapsed into one another.
    """
    if _strict_flag(item, "model_interpretation"):
        return EVIDENCE_MODEL_INTERPRETATION
    normalized = _normalized(item.get("evidence_type"))
    if normalized in _KNOWN_EVIDENCE_TYPES:
        return normalized
    return EVIDENCE_UNKNOWN


def classify_development_period(value: Any) -> str:
    """Classify a period label as historical, current, or unknown."""
    normalized = _normalized(value)
    if normalized in _HISTORICAL_MARKERS:
        return PERIOD_HISTORICAL
    if normalized in _CURRENT_MARKERS:
        return PERIOD_CURRENT
    return PERIOD_UNKNOWN


def evaluate_developmental_temporality(request: Mapping) -> dict:
    """Evaluate whether a temporal claim stays inside its evidence scope.

    A historical observation may not be generalized into current impairment,
    a current difficulty may not be generalized into a lifelong developmental
    pattern, and a retrospective report may not be presented as a
    contemporaneous observation.
    """
    observed_period = classify_development_period(request.get("observed_period"))
    observation_kind = _normalized(request.get("observation_kind"))
    if observation_kind not in {OBSERVATION_CONTEMPORANEOUS, OBSERVATION_RETROSPECTIVE}:
        observation_kind = OBSERVATION_UNKNOWN
    generalized_to = _normalized(request.get("generalized_to"))
    presented_as = _normalized(request.get("presented_as"))

    over_generalized = (
        observed_period == PERIOD_HISTORICAL
        and generalized_to == GENERALIZED_TO_CURRENT_IMPAIRMENT
    ) or (
        observed_period == PERIOD_CURRENT
        and generalized_to == GENERALIZED_TO_LIFELONG_PATTERN
    )
    retrospective_as_contemporaneous = (
        observation_kind == OBSERVATION_RETROSPECTIVE
        and presented_as == OBSERVATION_CONTEMPORANEOUS
    )
    return {
        "observed_period": observed_period,
        "observation_kind": observation_kind,
        "generalized_to": generalized_to or None,
        "temporal_generalization_blocked": over_generalized,
        "retrospective_as_contemporaneous": retrospective_as_contemporaneous,
        "current_vs_historical_distinguished": True,
        "historical_trait_created_current_impairment": False,
        "current_difficulty_created_lifelong_pattern": False,
    }


def evaluate_longitudinal_corroboration(request: Mapping) -> dict:
    """Compare evidence across periods and sources without inventing disproof.

    Absent corroboration reduces confidence.  It is never treated as proof that
    the pattern does not exist.
    """
    period_ids = _identifier_list(request.get("periods"))
    source_ids = _identifier_list(request.get("sources"))
    corroboration_present = len(set(period_ids)) >= 2 or len(set(source_ids)) >= 2
    asserted_disproof = _strict_flag(request, "absence_is_disproof")
    return {
        "period_ids": period_ids,
        "source_ids": source_ids,
        "period_count": len(set(period_ids)),
        "source_count": len(set(source_ids)),
        "corroboration_present": corroboration_present,
        "confidence_reduced": not corroboration_present,
        "absence_treated_as_disproof": False,
        "disproof_created": False,
        "absence_is_disproof_asserted": asserted_disproof,
        "missing_corroboration_is_disproof": False,
    }


def evaluate_contradiction_preservation(request: Mapping) -> dict:
    """Keep competing evidence visible instead of erasing it.

    Weakening evidence is surfaced explicitly.  If the caller reports a
    narrowed evidence set that omits known weakening evidence, the
    contradiction has been erased and the rule fails closed.
    """
    evidence = _seq(request, "evidence") or ()
    entries = tuple(item for item in evidence if isinstance(item, Mapping))
    evidence_ids = _identifier_list(entries)
    weakening_ids = tuple(
        str(item.get("id")).strip()
        for item in entries
        if _is_non_empty_id(item.get("id"))
        and _normalized(item.get("direction")) in {"weakens", "contradicts", "against"}
    )
    reported = _seq(request, "reported_evidence_ids")
    if reported is None:
        reported_ids = evidence_ids
    else:
        reported_ids = tuple(
            str(item).strip() for item in reported if _is_non_empty_id(item)
        )
    missing_weakening = tuple(
        item for item in weakening_ids if item not in reported_ids
    )
    visible_weakening = tuple(item for item in weakening_ids if item in reported_ids)
    return {
        "evidence_ids": evidence_ids,
        "reported_evidence_ids": reported_ids,
        "weakening_evidence_ids": weakening_ids,
        "visible_weakening_evidence_ids": visible_weakening,
        "missing_weakening_evidence_ids": missing_weakening,
        "contradiction_erased": bool(missing_weakening),
        "competing_evidence_visible": not missing_weakening,
    }


def detect_health_owned_clinical_status(claim: Mapping) -> dict:
    """Deterministically decide whether a claim is Health-owned clinical truth.

    Any documented diagnosis, treatment, medication, medical-test or
    medical-safety claim is Health-owned.  Neurodivergence may reason over an
    authorized projection of it but may never override it.
    """
    is_clinical = any(_strict_flag(claim, key) for key in _HEALTH_OWNED_CLINICAL_KEYS)
    requested = _normalized(claim.get("requested"))
    override_requested = requested in _CLINICAL_OVERRIDE_REQUESTS
    competing_hypothesis = claim.get("competing_hypothesis")
    hypothesis_present = _is_non_empty_id(competing_hypothesis)
    return {
        "primary_authority": HEALTH_DOMAIN_ID
        if is_clinical
        else NEURODIVERGENCE_DOMAIN_ID,
        "is_health_owned": is_clinical,
        "override_requested": override_requested,
        "requested": requested or None,
        "health_clinical_status_preserved": True,
        "neurodivergence_may_override": False,
        "neurodivergence_supporting_allowed": is_clinical,
        "competing_hypothesis_present": hypothesis_present,
        "competing_hypothesis_discussable": hypothesis_present,
        "competing_hypothesis_promoted": False,
        "medication_change_blocked": True,
        "treatment_change_blocked": True,
        "autonomous_medical_action": False,
    }


def is_persistence_restricted_content(content_kind: Any) -> bool:
    """True when this pack may never persist ``content_kind`` at all.

    Malformed or unlisted input fails closed: an unknown content kind is
    treated as restricted rather than silently persistable.
    """
    if not isinstance(content_kind, str):
        return True
    normalized = _normalized(content_kind)
    if normalized in _NEVER_PERSISTABLE_CONTENT_KINDS:
        return True
    return normalized not in _PROPOSAL_REQUIRED_CONTENT_KINDS


def persistence_requires_proposal(content_kind: Any) -> bool:
    """True when ``content_kind`` may only move through the proposal path."""
    if not isinstance(content_kind, str):
        return True
    return _normalized(content_kind) in _PROPOSAL_REQUIRED_CONTENT_KINDS


def persistence_is_authorized(authorization: Any) -> bool:
    """Strict authorization: only an explicit approval chain authorizes.

    Raw booleans, numerics, strings, ``None`` and arbitrary mappings never
    authorize.  The referenced proposal and binding must be real non-empty
    identifiers — a malformed container must not stand in for one.
    """
    if not isinstance(authorization, Mapping):
        return False
    if authorization.get("approved") is not True:
        return False
    return _is_non_empty_id(authorization.get("proposal_id")) and _is_non_empty_id(
        authorization.get("binding_id")
    )


def proposal_preserves_hypothesis_status(request: Mapping) -> bool:
    """True when a proposal keeps its hypothesis status instead of promoting it.

    A working hypothesis may be proposed for memory; it may never be proposed
    *as* a confirmed state.
    """
    current = _certainty_label(request.get("certainty_state"))
    proposed = _certainty_label(request.get("proposed_state"))
    if proposed == CERTAINTY_UNKNOWN:
        return True
    if proposed == CERTAINTY_CONFIRMED:
        return False
    return current != CERTAINTY_CONFIRMED or proposed != CERTAINTY_CONFIRMED


def _canonical_source_provenance(value: Any) -> ResourceProvenance | None:
    """Return validated canonical source provenance, else ``None``.

    Reuses the existing canonical cognitive ``ResourceProvenance`` contract (no
    second provenance model is invented).  Malformed or incomplete evidence
    fails closed to ``None`` rather than fabricating provenance.
    """
    if not isinstance(value, Mapping):
        return None
    try:
        source_type = ResourceSourceKind(value.get("source_type"))
    except (ValueError, TypeError):
        return None
    try:
        return ResourceProvenance(
            source_type=source_type,
            source_id=value.get("source_id"),
            author=value.get("author"),
            original_location=value.get("original_location"),
            checksum=value.get("checksum"),
        )
    except (InvalidResourceProvenanceError, AttributeError, TypeError):
        return None


def _canonical_transfer(value: Any) -> CrossDomainContextTransfer | None:
    """Return a validated canonical cross-domain transfer, else ``None``.

    Reuses the existing canonical ``CrossDomainContextTransfer`` contract — no
    Neurodivergence-specific transfer or provenance model is invented.  That
    contract already enforces distinct valid domains, non-empty provenance and
    strict boolean transfer flags; malformed input fails closed to ``None``.
    """
    if isinstance(value, CrossDomainContextTransfer):
        return value
    if not isinstance(value, Mapping):
        return None
    try:
        return CrossDomainContextTransfer.from_dict(dict(value))
    except (
        CrossDomainSerializationError,
        CrossDomainContractError,
        TypeError,
        ValueError,
        KeyError,
    ):
        return None


def _transfer_rejection(
    transfer: CrossDomainContextTransfer, purpose: str
) -> str | None:
    """Return the canonical rejection reason, or ``None`` when acceptable."""
    if str(transfer.target_domain) != NEURODIVERGENCE_DOMAIN_ID:
        return "target_domain_not_neurodivergence"
    if transfer.source_domain.slug.strip().casefold() in _UNKNOWN_SOURCE_SLUGS:
        return "source_domain_unknown"
    if not transfer.provenance:
        return "provenance_missing"
    if transfer.private:
        return "private_context_not_transferable"
    if not transfer.transferable:
        return "transfer_not_permitted"
    if transfer.reason.strip() != purpose:
        return "purpose_mismatch"
    return None


def _canonical_domain_identity(value: Any) -> DomainId | None:
    """Return the canonical ``DomainId`` for ``value``, else ``None``.

    Reuses the canonical Phase 10.1 ``DomainId`` contract as the single
    owner-identity validator, so no local slug regex or parallel identifier
    vocabulary is introduced.  An already-valid ``DomainId`` is returned as-is;
    a string must be the exact canonical ``domain:<slug>`` form.  A non-string,
    a blank or padded value, a missing ``domain:`` prefix and an invalid slug
    all fail closed to ``None``.
    """
    if isinstance(value, DomainId):
        return value
    if not isinstance(value, str):
        return None
    try:
        return DomainId.from_str(value)
    except (DomainSerializationError, DomainContractValidationError):
        return None


def _trusted_health_authority(
    request: Mapping,
    authority_context: ReasoningAuthorityContext | None,
) -> dict | None:
    """Return the applicable trusted Health authority, else ``None``.

    Authority comes only from the runtime-only ``ReasoningAuthorityContext``
    that trusted canonical integration code attached to the reasoning context.
    Caller-authored request data is never consulted for authority: no
    ``permission_authority`` boolean, decision ID, approval flag, serialized
    gate result, canonical-shaped transfer, provenance or
    Health-definitive-looking mapping can reach this check.  Shape is not
    provenance and serialization is not authority.

    A clinical ``CONFIRMED`` transition requires the trusted authority to bind
    to the canonical Health source domain, this Neurodivergence target domain,
    the exact claim as both a permissioned resource and a *provenance-bound*
    Health-owned authoritative claim, and the requested purpose.  A claim id
    without canonical source provenance is not authority and blocks.
    """
    if authority_context is None:
        return None

    claim_id = request.get("claim_id")
    if not _is_non_empty_id(claim_id):
        return None
    claim_id = str(claim_id).strip()

    raw_purpose = request.get("purpose")
    purpose = raw_purpose.strip() if isinstance(raw_purpose, str) else ""
    if not purpose:
        return None

    if authority_context.source_domain != HEALTH_DOMAIN_ID:
        return None
    if authority_context.target_domain != NEURODIVERGENCE_DOMAIN_ID:
        return None
    if claim_id not in authority_context.resource_ids:
        return None
    if authority_context.purpose != purpose:
        return None

    # The claim must be carried as a provenance-bound projection: authority
    # cannot exist in the trusted channel without canonical source provenance.
    bound_claim = next(
        (
            claim
            for claim in authority_context.authoritative_claims
            if getattr(claim, "claim_id", None) == claim_id
        ),
        None,
    )
    if bound_claim is None:
        return None
    if getattr(bound_claim, "source_domain", None) != HEALTH_DOMAIN_ID:
        return None
    if getattr(bound_claim, "purpose", None) != purpose:
        return None
    source_provenance_id = getattr(bound_claim, "source_provenance_id", None)
    if not _is_non_empty_id(source_provenance_id):
        return None

    return {
        "claim_id": claim_id,
        "source_domain": authority_context.source_domain,
        "target_domain": authority_context.target_domain,
        "permission_decision_id": authority_context.permission_decision_id,
        "permission_outcome": authority_context.permission_outcome,
        "approval_consumed": authority_context.approval_consumed,
        "purpose": purpose,
        "source_provenance_id": source_provenance_id,
        "authoritative_claim": {
            "claim_id": bound_claim.claim_id,
            "source_domain": bound_claim.source_domain,
            "purpose": bound_claim.purpose,
            "source_provenance_id": source_provenance_id,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CertaintyStatePreservationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class CertaintyStatePreservationRule:
    """No upward certainty transition without canonical authoritative evidence.

    Exploration stays permissive and useful; only *clinical certainty
    promotion* is gated, and it is gated on canonical Health authority rather
    than on a caller-authored mapping.
    """

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        request = _mapping(context.metadata, "certainty_transition")
        if request is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No certainty transition supplied.",
            )
        raw_target = request.get("to_state")
        if not isinstance(raw_target, str) or not raw_target.strip():
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No certainty target state supplied.",
            )
        record = evaluate_certainty_transition(
            request,
            authority_context=context.authority_context,
        )
        metadata = dict(record)
        if record["promotion_blocked"] or record["exclusion_blocked"]:
            blocked_state = (
                CERTAINTY_CONFIRMED
                if record["promotion_blocked"]
                else CERTAINTY_RULED_OUT
            )
            finding = _finding(
                self.definition,
                "CERTAINTY_PROMOTION_BLOCKED",
                (
                    f"A transition to {blocked_state} requires canonical "
                    "authoritative evidence; the supplied evidence does not "
                    "carry it, so the prior certainty state is preserved."
                ),
                severity=ReasoningSeverity.WARNING,
                metadata={
                    "from_state": record["from_state"],
                    "requested_state": record["to_state"],
                    "confirmed_diagnosis_created": False,
                    "certified_here": False,
                },
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=metadata,
                code="CERTAINTY_PROMOTION_BLOCKED",
                message="Certainty promotion failed closed.",
            )
        finding = _finding(
            self.definition,
            "CERTAINTY_STATE_PRESERVED",
            (
                f"Certainty state kept as {record['certainty_state']}; no upward "
                "transition was manufactured."
            ),
            metadata={
                "certainty_state": record["certainty_state"],
                "requires_authority": record["requires_authority"],
                "authoritative_evidence": record["authoritative_evidence"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=metadata,
            code="CERTAINTY_STATE_PRESERVED",
            message="Certainty state preserved without promotion.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ClinicalStatusAuthorityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ClinicalStatusAuthorityRule:
    """Health keeps clinical status; Neurodivergence may discuss hypotheses."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claim = _mapping(context.metadata, "clinical_claim")
        if claim is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No clinical claim supplied.",
            )
        verdict = detect_health_owned_clinical_status(claim)
        if verdict["is_health_owned"] and verdict["override_requested"]:
            finding = _finding(
                self.definition,
                "CLINICAL_STATUS_AUTHORITY_BOUNDARY",
                "Documented diagnosis, treatment, medication and medical-safety "
                "truth belong to Health; Neurodivergence may reason alongside a "
                "working hypothesis but never overrides that status.",
                severity=ReasoningSeverity.WARNING,
                metadata={
                    "primary_authority": verdict["primary_authority"],
                    "neurodivergence_may_override": False,
                    "health_clinical_status_preserved": True,
                    "competing_hypothesis_discussable": verdict[
                        "competing_hypothesis_discussable"
                    ],
                    "autonomous_medical_action": False,
                },
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=verdict,
                code="CLINICAL_OVERRIDE_BLOCKED",
                message="Clinical override blocked; Health authority preserved.",
            )
        finding = _finding(
            self.definition,
            "CLINICAL_STATUS_AUTHORITY_BOUNDARY",
            "No clinical override requested; Health ownership unchanged and "
            "working hypotheses remain discussable.",
            metadata={
                "primary_authority": verdict["primary_authority"],
                "neurodivergence_may_override": False,
                "health_clinical_status_preserved": True,
                "competing_hypothesis_discussable": verdict[
                    "competing_hypothesis_discussable"
                ],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=verdict,
            code="CLINICAL_STATUS_AUTHORITY_PRESERVED",
            message="Health clinical authority preserved.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SourceAuthorityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SourceAuthorityRule:
    """An imported source-domain fact keeps its owner."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claims = _seq(context.metadata, "source_claims")
        if not claims:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No source claims supplied.",
            )
        rewritten: list[str] = []
        unknown: list[str] = []
        source_domains: set[str] = set()
        findings: list[ReasoningFinding] = []
        for claim in claims:
            if not isinstance(claim, Mapping):
                continue
            claim_id = str(claim.get("id", "unknown"))
            # The owner must be a canonical domain identifier; an arbitrary
            # string is not a domain and leaves the imported fact unowned.
            owner = _canonical_domain_identity(claim.get("source_domain"))
            if owner is None:
                unknown.append(claim_id)
                continue
            source_domain = str(owner)
            source_domains.add(source_domain)
            re_emitted_as = claim.get("re_emitted_as")
            if _is_non_empty_id(re_emitted_as) and str(re_emitted_as).strip() != (
                source_domain
            ):
                rewritten.append(claim_id)
                findings.append(
                    _finding(
                        self.definition,
                        "SOURCE_AUTHORITY_REWRITTEN",
                        f"Claim {claim_id} was re-emitted as "
                        f"{str(re_emitted_as).strip()} but belongs to "
                        f"{source_domain}.",
                        severity=ReasoningSeverity.WARNING,
                        references=(claim_id, source_domain),
                        metadata={"source_domain": source_domain},
                    )
                )
                continue
            findings.append(
                _finding(
                    self.definition,
                    "SOURCE_AUTHORITY_PRESERVED",
                    f"Claim {claim_id} keeps {source_domain} as its owner.",
                    references=(claim_id, source_domain),
                    metadata={"source_domain": source_domain},
                )
            )
        preserved = not rewritten and not unknown
        metadata = {
            "source_authority_preserved": preserved,
            "rewritten_claims": tuple(rewritten),
            "unknown_source_claims": tuple(unknown),
            "source_domains": tuple(sorted(source_domains)),
        }
        if not preserved:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=tuple(findings),
                metadata=metadata,
                code="SOURCE_AUTHORITY_BLOCKED",
                message="Source-domain ownership was rewritten or unknown.",
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            metadata=metadata,
            code="SOURCE_AUTHORITY_PRESERVED",
            message="Imported facts keep their source-domain owner.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DevelopmentalTemporalityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DevelopmentalTemporalityRule:
    """Current and historical evidence stay distinguishable."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claim = _mapping(context.metadata, "temporal_claim")
        if claim is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No temporal claim supplied.",
            )
        record = evaluate_developmental_temporality(claim)
        blocked = (
            record["temporal_generalization_blocked"]
            or record["retrospective_as_contemporaneous"]
        )
        if blocked:
            finding = _finding(
                self.definition,
                "TEMPORAL_GENERALIZATION_BLOCKED",
                "The claim was generalized beyond its evidence scope: current "
                "and historical evidence stay distinct, and a retrospective "
                "report is not a contemporaneous observation.",
                severity=ReasoningSeverity.WARNING,
                references=(str(claim.get("claim_id", "unknown")),),
                metadata=dict(record),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=record,
                code="TEMPORAL_GENERALIZATION_BLOCKED",
                message="Temporal generalization blocked.",
            )
        finding = _finding(
            self.definition,
            "TEMPORAL_SCOPE_PRESERVED",
            "The claim stays inside its observed period and observation kind.",
            metadata=dict(record),
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=record,
            code="TEMPORAL_SCOPE_PRESERVED",
            message="Developmental temporality preserved.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ObservationReportSeparationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ObservationReportSeparationRule:
    """Direct observation, retrospective report and third-party report differ."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        items = _seq(context.metadata, "evidence_items")
        if not items:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No evidence items supplied.",
            )
        provenance = _canonical_source_provenance(
            context.metadata.get("source_provenance")
        )
        provenance_id = provenance.source_id if provenance is not None else None

        findings: list[ReasoningFinding] = []
        classes: list[str] = []
        collapsed: list[str] = []
        unprovenanced: list[str] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            item_id = str(item.get("id", "unknown"))
            evidence_class = classify_evidence_source(item)
            classes.append(evidence_class)
            presented_as = _normalized(item.get("presented_as"))
            if presented_as and presented_as != evidence_class:
                collapsed.append(item_id)
            source_ref = item.get("source_ref")
            item_provenanced = provenance is not None and _is_non_empty_id(source_ref)
            if not item_provenanced:
                unprovenanced.append(item_id)
            findings.append(
                _finding(
                    self.definition,
                    "EVIDENCE_SOURCE_SEPARATED",
                    f"Evidence {item_id} kept as {evidence_class}.",
                    references=(item_id,),
                    metadata={
                        "evidence_class": evidence_class,
                        "source_ref": (
                            str(source_ref).strip()
                            if _is_non_empty_id(source_ref)
                            else None
                        ),
                        "source_identity_preserved": item_provenanced,
                    },
                )
            )

        metadata = {
            "evidence_classes": tuple(sorted(set(classes))),
            "report_collapsed_into_observation": bool(collapsed),
            "collapsed_evidence_ids": tuple(collapsed),
            "unprovenanced_evidence_ids": tuple(unprovenanced),
            "provenance_preserved": bool(provenance is not None and not unprovenanced),
            "source_provenance_id": provenance_id,
            "high_confidence_output_blocked": bool(collapsed or unprovenanced),
        }
        if collapsed:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(
                    *findings,
                    _finding(
                        self.definition,
                        "EVIDENCE_CLASS_COLLAPSED",
                        "A report was presented as a different evidence class; "
                        "observation, retrospective report and third-party "
                        "report never collapse into one another.",
                        severity=ReasoningSeverity.WARNING,
                        references=tuple(collapsed),
                    ),
                ),
                metadata=metadata,
                code="EVIDENCE_CLASS_COLLAPSED",
                message="Evidence classes must remain distinct.",
            )
        if provenance is not None and unprovenanced:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(
                    *findings,
                    _finding(
                        self.definition,
                        "EVIDENCE_PROVENANCE_INSUFFICIENT",
                        "Evidence without canonical source/provenance evidence "
                        "cannot support a high-confidence conclusion.",
                        severity=ReasoningSeverity.WARNING,
                        references=tuple(unprovenanced),
                    ),
                ),
                metadata=metadata,
                code="EVIDENCE_PROVENANCE_INSUFFICIENT",
                message="High-confidence output blocked: provenance insufficient.",
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            metadata=metadata,
            code="EVIDENCE_SOURCES_SEPARATED",
            message="Observation and report classes kept separate.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ScreeningDiagnosisSeparationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ScreeningDiagnosisSeparationRule:
    """Screening contributes evidence; it never becomes a diagnosis."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        screening = _mapping(context.metadata, "screening")
        if screening is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No screening input supplied.",
            )
        promoted = _strict_flag(screening, "claimed_as_diagnosis")
        source_ref = screening.get("source_ref")
        metadata = {
            "instrument": screening.get("instrument"),
            "source_ref": (
                str(source_ref).strip() if _is_non_empty_id(source_ref) else None
            ),
            "screening_is_evidence_only": True,
            "screening_promoted_to_diagnosis": False,
            "diagnosis_created": False,
            "confirmed_diagnosis_created": False,
        }
        if promoted:
            finding = _finding(
                self.definition,
                "SCREENING_DIAGNOSIS_SEPARATION",
                "A screening result is evidence, not a diagnosis; it cannot "
                "independently establish a confirmed clinical status.",
                severity=ReasoningSeverity.WARNING,
                metadata=dict(metadata),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=metadata,
                code="SCREENING_PROMOTION_BLOCKED",
                message="Screening cannot become a diagnosis.",
            )
        finding = _finding(
            self.definition,
            "SCREENING_DIAGNOSIS_SEPARATION",
            "Screening contributes evidence only; no diagnosis was created.",
            metadata=dict(metadata),
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=metadata,
            code="SCREENING_EVIDENCE_ONLY",
            message="Screening kept as evidence.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. TraitFunctionSeparationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class TraitFunctionSeparationRule:
    """A trait does not imply clinically significant functional impairment."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claim = _mapping(context.metadata, "trait_claim")
        if claim is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No trait claim supplied.",
            )
        impact_evidence = _strict_flag(claim, "functional_impact_evidence")
        demanded = _strict_flag(claim, "claimed_clinically_significant")
        metadata = {
            "trait": claim.get("trait"),
            "functional_impact_evidence": impact_evidence,
            "trait_treated_as_impairment": False,
            "functional_relevance_analyzed": True,
            "impairment_inferred_from_trait": False,
        }
        if demanded and not impact_evidence:
            finding = _finding(
                self.definition,
                "TRAIT_FUNCTION_SEPARATION",
                "A trait is not clinically significant impairment: functional "
                "relevance must be analyzed separately and evidence-backed.",
                severity=ReasoningSeverity.WARNING,
                metadata=dict(metadata),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=metadata,
                code="TRAIT_AS_IMPAIRMENT_BLOCKED",
                message="Trait-to-impairment promotion blocked.",
            )
        finding = _finding(
            self.definition,
            "TRAIT_FUNCTION_SEPARATION",
            "Trait and functional relevance stay separate.",
            metadata=dict(metadata),
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=metadata,
            code="TRAIT_FUNCTION_SEPARATED",
            message="Trait kept distinct from functional significance.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 8. LongitudinalCorroborationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class LongitudinalCorroborationRule:
    """Missing corroboration reduces confidence; it is never disproof."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        longitudinal = _mapping(context.metadata, "longitudinal")
        if longitudinal is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No longitudinal inputs supplied.",
            )
        record = evaluate_longitudinal_corroboration(longitudinal)
        metadata = dict(record)
        if record["absence_is_disproof_asserted"]:
            finding = _finding(
                self.definition,
                "ABSENCE_AS_DISPROOF_BLOCKED",
                "Missing longitudinal corroboration reduces confidence; it does "
                "not disprove the pattern.",
                severity=ReasoningSeverity.WARNING,
                metadata=dict(metadata),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=metadata,
                code="ABSENCE_AS_DISPROOF_BLOCKED",
                message="Absence of corroboration is not disproof.",
            )
        finding = _finding(
            self.definition,
            "LONGITUDINAL_CORROBORATION_REVIEWED",
            (
                "Evidence compared across periods and sources; corroboration present."
                if record["corroboration_present"]
                else "Corroboration is thin, so confidence is reduced rather "
                "than the pattern being disproved."
            ),
            metadata=dict(metadata),
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=metadata,
            code="LONGITUDINAL_CORROBORATION_REVIEWED",
            message="Longitudinal corroboration reviewed proportionately.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. ContradictionPreservationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ContradictionPreservationRule:
    """Competing evidence stays visible."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        evidence_set = _mapping(context.metadata, "evidence_set")
        if evidence_set is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No evidence set supplied.",
            )
        record = evaluate_contradiction_preservation(evidence_set)
        metadata = dict(record)
        if record["contradiction_erased"]:
            finding = _finding(
                self.definition,
                "CONTRADICTION_ERASED",
                "Weakening evidence was dropped from the reported evidence set; "
                "competing evidence must remain visible.",
                severity=ReasoningSeverity.WARNING,
                references=record["missing_weakening_evidence_ids"],
                metadata=dict(metadata),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=metadata,
                code="CONTRADICTION_ERASED",
                message="Competing evidence must not be erased.",
            )
        finding = _finding(
            self.definition,
            "CONTRADICTION_PRESERVED",
            "Supporting and weakening evidence remain visible together.",
            references=record["weakening_evidence_ids"],
            metadata=dict(metadata),
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=metadata,
            code="CONTRADICTION_PRESERVED",
            message="Contradictions preserved.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 10. DifferentialExplanationsRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DifferentialExplanationsRule:
    """Exploratory inference is allowed and must be genuinely useful.

    The rule organizes an exploratory question into what may fit, why it may
    fit, what remains unclear, what may not fit, alternative/overlapping
    explanations and what evidence would clarify the picture.  It never
    fabricates a negative case merely for symmetry and never replaces
    reasoning with a disclaimer.
    """

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        exploration = _mapping(context.metadata, "exploration")
        if exploration is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No exploratory request supplied.",
            )
        categories = {
            name: _identifier_list(exploration.get(name))
            for name in _DIFFERENTIAL_CATEGORIES
        }
        covered = tuple(name for name in _DIFFERENTIAL_CATEGORIES if categories[name])
        hypothesis = exploration.get("hypothesis")
        hypothesis_label = (
            str(hypothesis).strip() if _is_non_empty_id(hypothesis) else None
        )
        reasoning_present = bool(covered) or hypothesis_label is not None

        findings = [
            _finding(
                self.definition,
                "EXPLORATORY_HYPOTHESIS",
                (
                    f"Working hypothesis '{hypothesis_label}' held as a "
                    "hypothesis, not as a clinical fact."
                    if hypothesis_label
                    else "Exploratory comparison held without asserting a "
                    "diagnostic identity."
                ),
                references=(hypothesis_label,) if hypothesis_label else (),
                metadata={"hypothesis_state": CERTAINTY_HYPOTHESIS},
            )
        ]
        category_messages = {
            "supporting": "Evidence that could support the hypothesis.",
            "unclear": "Material points that remain unclear.",
            "conflicting": "Evidence that points away from the hypothesis.",
            "alternatives": "Alternative or overlapping explanations considered.",
            "clarifying_evidence": "Evidence that would clarify the picture.",
        }
        for name in covered:
            findings.append(
                _finding(
                    self.definition,
                    f"DIFFERENTIAL_{name.upper()}",
                    category_messages[name],
                    references=categories[name],
                    metadata={"category": name, "count": len(categories[name])},
                )
            )

        metadata = {
            "exploration_performed": True,
            "exploratory_model_inference": "allowed",
            "differential_reasoning": "balanced_not_adversarial",
            "hypothesis": hypothesis_label,
            "hypothesis_state": CERTAINTY_HYPOTHESIS,
            "confirmed_diagnosis_created": False,
            "certified_here": False,
            "categories_covered": covered,
            "category_evidence_ids": {
                name: categories[name] for name in _DIFFERENTIAL_CATEGORIES
            },
            # Balance is descriptive, never a fabricated counterargument.
            "negative_evidence_required": False,
            "fabricated_negative_evidence": False,
            "refusal_generated": False,
            "disclaimer_only_output": False,
            "professional_assessment_substituted_reasoning": False,
            "reasoning_present": reasoning_present,
        }
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            metadata=metadata,
            code="EXPLORATORY_REASONING_APPLIED",
            message="Exploratory reasoning applied without diagnostic promotion.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 11. OverlapReasoningRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class OverlapReasoningRule:
    """Overlap is not automatic co-diagnosis."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        overlap = _mapping(context.metadata, "overlap")
        if overlap is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No overlap inputs supplied.",
            )
        hypotheses = tuple(
            str(item).strip()
            for item in (overlap.get("hypotheses") or ())
            if _is_non_empty_id(item)
        )
        metadata = {
            "hypotheses": hypotheses,
            "overlapping_features": _identifier_list(
                overlap.get("overlapping_features")
            ),
            "distinguishing_evidence": _identifier_list(
                overlap.get("distinguishing_evidence")
            ),
            "overlap_considered": True,
            "overlap_is_not_co_diagnosis": True,
            "co_diagnosis_created": False,
            "confirmed_diagnosis_created": False,
        }
        if _strict_flag(overlap, "create_co_diagnosis"):
            finding = _finding(
                self.definition,
                "OVERLAP_AS_CO_DIAGNOSIS_BLOCKED",
                "Overlapping possibilities may be explored together, but "
                "overlap never creates a co-diagnosis.",
                severity=ReasoningSeverity.WARNING,
                metadata=dict(metadata),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=metadata,
                code="OVERLAP_AS_CO_DIAGNOSIS_BLOCKED",
                message="Overlap-to-co-diagnosis promotion blocked.",
            )
        finding = _finding(
            self.definition,
            "OVERLAP_REASONING_APPLIED",
            "Overlapping possibilities compared without creating a co-diagnosis.",
            references=hypotheses,
            metadata=dict(metadata),
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=metadata,
            code="OVERLAP_REASONING_APPLIED",
            message="Overlap reasoning applied.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 12. PurposeMinimizedCrossDomainRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class PurposeMinimizedCrossDomainRule:
    """Minimize an inbound projection to the fields its own evidence backs.

    A projected field is included only when an accepted canonical
    ``CrossDomainContextTransfer`` exists whose ``identifier`` equals the field
    name.  Provenance and source domains are derived from those backing
    transfers only, so one authorized field can never launder another field and
    an unrelated transfer grants no projection authority.

    A structurally valid transfer is **not** authority by itself.  When the
    caller supplies ``permission_authority``, only a literal ``True`` permits
    inclusion — the canonical current-permission decision is expressed as that
    fail-closed flag after the resolver/gate has actually run.
    """

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        projection = _mapping(context.metadata, "projection")
        if projection is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No cross-domain projection supplied.",
            )
        raw_purpose = projection.get("purpose")
        purpose = raw_purpose.strip() if isinstance(raw_purpose, str) else ""
        fields = projection.get("fields")
        if not isinstance(fields, Mapping):
            fields = {}
        authority_supplied = "permission_authority" in projection
        permission_authority = _strict_flag(projection, "permission_authority")
        if not purpose:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                metadata={
                    "included_fields": (),
                    "excluded_fields": tuple(fields),
                    "provenance_preserved": False,
                    "rejected_transfers": ("purpose_missing",),
                    "purpose": None,
                    "permission_authority": (
                        permission_authority if authority_supplied else None
                    ),
                },
                code="CROSS_DOMAIN_TRANSFER_BLOCKED",
                message="Cross-domain import blocked: no authorized purpose supplied.",
            )
        if authority_supplied and not permission_authority:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                metadata={
                    "included_fields": (),
                    "excluded_fields": tuple(fields),
                    "unbound_fields": (),
                    "provenance_preserved": False,
                    "provenance_references": (),
                    "source_domains": (),
                    "rejected_transfers": ("current_authority_denied",),
                    "purpose": purpose,
                    "permission_authority": False,
                },
                code="CROSS_DOMAIN_TRANSFER_BLOCKED",
                message=(
                    "Cross-domain import blocked: current permission authority "
                    "does not admit the transfer."
                ),
            )

        # Only a literal ``True`` relevance flag survives minimization; a
        # malformed value never gains relevance.
        relevant = tuple(
            name
            for name, spec in fields.items()
            if isinstance(spec, Mapping) and _strict_flag(spec, "relevant")
        )

        # Canonical transfer evidence is required — an untyped mapping is not
        # provenance.  Accepted transfers are indexed by their canonical
        # identifier so a projected field can only ever be authorized by
        # transfer evidence for that same identifier.
        accepted_by_identifier: dict[str, list[CrossDomainContextTransfer]] = {}
        rejected: list[str] = []
        for item in _seq(context.metadata, "transfers") or ():
            transfer = _canonical_transfer(item)
            if transfer is None:
                rejected.append("malformed_transfer")
                continue
            reason = _transfer_rejection(transfer, purpose)
            if reason is not None:
                rejected.append(reason)
                continue
            accepted_by_identifier.setdefault(transfer.identifier, []).append(transfer)

        included = tuple(name for name in relevant if name in accepted_by_identifier)
        excluded = tuple(name for name in fields if name not in included)
        unbound = tuple(name for name in relevant if name not in accepted_by_identifier)

        if not included:
            finding = _finding(
                self.definition,
                "CROSS_DOMAIN_TRANSFER_BLOCKED",
                "Cross-domain import requires canonical transfer evidence with "
                "non-empty provenance and current transfer authority for each "
                "projected field.",
                severity=ReasoningSeverity.WARNING,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata={
                    "included_fields": (),
                    "excluded_fields": tuple(fields),
                    "unbound_fields": unbound,
                    "provenance_preserved": False,
                    "provenance_references": (),
                    "source_domains": (),
                    "rejected_transfers": tuple(rejected),
                    "purpose": purpose,
                    "permission_authority": (
                        permission_authority if authority_supplied else None
                    ),
                },
                code="CROSS_DOMAIN_TRANSFER_BLOCKED",
                message=(
                    "Cross-domain import blocked: no projected field is backed "
                    "by canonical transfer evidence for the same identifier."
                ),
            )

        # Provenance and source domains derive only from the transfers actually
        # backing an included field — never from unrelated evidence.
        backing = tuple(
            transfer for name in included for transfer in accepted_by_identifier[name]
        )
        provenance_references = tuple(
            sorted({ref for transfer in backing for ref in transfer.provenance})
        )
        source_domains = tuple(sorted({str(item.source_domain) for item in backing}))
        finding = _finding(
            self.definition,
            "PURPOSE_MINIMIZED_PROJECTION",
            "Only fields material to the current purpose were projected; "
            "irrelevant sensitive fields were excluded.",
            metadata={
                "purpose": purpose,
                "source_domains": list(source_domains),
                "included_fields": list(included),
                "excluded_fields": list(excluded),
                "provenance_preserved": True,
                "provenance_references": list(provenance_references),
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata={
                "included_fields": included,
                "excluded_fields": excluded,
                "unbound_fields": unbound,
                "provenance_preserved": True,
                "provenance_references": provenance_references,
                "source_domains": source_domains,
                "purpose": purpose,
                "rejected_transfers": tuple(rejected),
                "permission_authority": (
                    permission_authority if authority_supplied else None
                ),
            },
            code="CROSS_DOMAIN_MINIMIZED",
            message="Cross-domain import minimized to the authorized purpose.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 13. GlobalAttributionGuardRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class GlobalAttributionGuardRule:
    """An active domain does not make every difficulty neurodivergence-caused.

    This guard is anti-over-attribution, not anti-hypothesis: ordinary
    exploratory associations — including unevidenced ones held openly as
    hypotheses — are never suppressed.
    """

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        attribution = _mapping(context.metadata, "attribution")
        if attribution is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No attribution input supplied.",
            )
        global_claim = _strict_flag(attribution, "global_causal_claim")
        evidence_supplied = _strict_flag(attribution, "evidence_supplied")
        alternatives = _identifier_list(attribution.get("alternatives"))
        blocked = global_claim and not evidence_supplied
        metadata = {
            "global_causal_claim": global_claim,
            "evidence_supplied": evidence_supplied,
            "alternatives_considered": alternatives,
            "global_attribution_blocked": blocked,
            # The guard must never collapse into blanket hypothesis suppression.
            "exploratory_association_suppressed": False,
            "hypothesis_status_preserved": True,
            "confirmed_diagnosis_created": False,
        }
        if blocked:
            finding = _finding(
                self.definition,
                "GLOBAL_ATTRIBUTION_BLOCKED",
                "Every difficulty may not be explained by neurodivergence merely "
                "because the domain is active; a global causal claim needs "
                "evidence or must be held as a hypothesis.",
                severity=ReasoningSeverity.WARNING,
                metadata=dict(metadata),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=metadata,
                code="GLOBAL_ATTRIBUTION_BLOCKED",
                message="Global attribution blocked; exploration is unaffected.",
            )
        finding = _finding(
            self.definition,
            "ATTRIBUTION_SCOPED",
            "The attribution stays scoped and is held as a hypothesis.",
            metadata=dict(metadata),
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=metadata,
            code="ATTRIBUTION_SCOPED",
            message="Attribution scoped without suppressing exploration.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 14. SensitiveLabelPersistenceRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SensitiveLabelPersistenceRule:
    """Working hypotheses never silently become stable memory."""

    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        request = _mapping(context.metadata, "persistence_request")
        if request is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No persistence request supplied.",
            )
        content_kind = request.get("content_kind")
        restricted = is_persistence_restricted_content(content_kind)
        authorized = persistence_is_authorized(request.get("authorization"))
        preserves = proposal_preserves_hypothesis_status(request)
        certainty_promoted = not preserves
        blocked = restricted or not authorized or certainty_promoted
        metadata = {
            "content_kind": content_kind if isinstance(content_kind, str) else None,
            "content_restricted": restricted,
            "proposal_required": True,
            "direct_write_performed": False,
            "authorization_accepted": authorized,
            "certainty_promoted": certainty_promoted,
            "hypothesis_status_preserved": preserves,
            "read_is_not_propose": True,
            "propose_is_not_approve": True,
            "approve_is_not_apply": True,
        }
        if blocked:
            finding = _finding(
                self.definition,
                "SENSITIVE_LABEL_PERSISTENCE_BLOCKED",
                (
                    "This content kind may never be persisted by this pack."
                    if restricted
                    else "A working hypothesis is not persisted: discussion is "
                    "not authorization and no canonical approval chain was "
                    "presented."
                    if not authorized
                    else "A proposal may not upgrade a hypothesis to a confirmed state."
                ),
                severity=ReasoningSeverity.WARNING,
                metadata=dict(metadata),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata=metadata,
                code="SENSITIVE_LABEL_PERSISTENCE_BLOCKED",
                message="Sensitive label persistence blocked; proposal path required.",
            )
        finding = _finding(
            self.definition,
            "SENSITIVE_LABEL_PROPOSAL_ALLOWED",
            "Persistence moves through the canonical proposal path only, with "
            "hypothesis status preserved.",
            metadata=dict(metadata),
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata=metadata,
            code="SENSITIVE_LABEL_PROPOSAL_ALLOWED",
            message="Proposal-first persistence only.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_neurodivergence_rules() -> tuple[Any, ...]:
    """Build the fourteen Neurodivergence rules deterministically in catalog order."""
    by_id: dict[str, Any] = {
        "neurodivergence.certainty_state_preservation": (
            CertaintyStatePreservationRule(
                definition=_definition(
                    "neurodivergence.certainty_state_preservation",
                    "CertaintyStatePreservationRule",
                    ReasoningRuleCategory.EPISTEMIC.value,
                    790,
                    risk_level=ReasoningRiskLevel.HIGH,
                )
            )
        ),
        "neurodivergence.clinical_status_authority": ClinicalStatusAuthorityRule(
            definition=_definition(
                "neurodivergence.clinical_status_authority",
                "ClinicalStatusAuthorityRule",
                ReasoningRuleCategory.SAFETY.value,
                830,
                risk_level=ReasoningRiskLevel.HIGH,
            )
        ),
        "neurodivergence.source_authority": SourceAuthorityRule(
            definition=_definition(
                "neurodivergence.source_authority",
                "SourceAuthorityRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                730,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "neurodivergence.developmental_temporality": DevelopmentalTemporalityRule(
            definition=_definition(
                "neurodivergence.developmental_temporality",
                "DevelopmentalTemporalityRule",
                ReasoningRuleCategory.TEMPORALITY.value,
                750,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "neurodivergence.observation_report_separation": (
            ObservationReportSeparationRule(
                definition=_definition(
                    "neurodivergence.observation_report_separation",
                    "ObservationReportSeparationRule",
                    ReasoningRuleCategory.EPISTEMIC.value,
                    770,
                    risk_level=ReasoningRiskLevel.MEDIUM,
                )
            )
        ),
        "neurodivergence.screening_diagnosis_separation": (
            ScreeningDiagnosisSeparationRule(
                definition=_definition(
                    "neurodivergence.screening_diagnosis_separation",
                    "ScreeningDiagnosisSeparationRule",
                    ReasoningRuleCategory.EPISTEMIC.value,
                    785,
                    risk_level=ReasoningRiskLevel.HIGH,
                )
            )
        ),
        "neurodivergence.trait_function_separation": TraitFunctionSeparationRule(
            definition=_definition(
                "neurodivergence.trait_function_separation",
                "TraitFunctionSeparationRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                775,
            )
        ),
        "neurodivergence.longitudinal_corroboration": LongitudinalCorroborationRule(
            definition=_definition(
                "neurodivergence.longitudinal_corroboration",
                "LongitudinalCorroborationRule",
                ReasoningRuleCategory.TEMPORALITY.value,
                760,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "neurodivergence.contradiction_preservation": ContradictionPreservationRule(
            definition=_definition(
                "neurodivergence.contradiction_preservation",
                "ContradictionPreservationRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                780,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "neurodivergence.differential_explanations": DifferentialExplanationsRule(
            definition=_definition(
                "neurodivergence.differential_explanations",
                "DifferentialExplanationsRule",
                ReasoningRuleCategory.INFERENCE.value,
                700,
            )
        ),
        "neurodivergence.overlap_reasoning": OverlapReasoningRule(
            definition=_definition(
                "neurodivergence.overlap_reasoning",
                "OverlapReasoningRule",
                ReasoningRuleCategory.INFERENCE.value,
                710,
            )
        ),
        "neurodivergence.purpose_minimized_cross_domain": (
            PurposeMinimizedCrossDomainRule(
                definition=_definition(
                    "neurodivergence.purpose_minimized_cross_domain",
                    "PurposeMinimizedCrossDomainRule",
                    ReasoningRuleCategory.CONSISTENCY.value,
                    740,
                    risk_level=ReasoningRiskLevel.MEDIUM,
                )
            )
        ),
        "neurodivergence.global_attribution_guard": GlobalAttributionGuardRule(
            definition=_definition(
                "neurodivergence.global_attribution_guard",
                "GlobalAttributionGuardRule",
                ReasoningRuleCategory.SAFETY.value,
                800,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "neurodivergence.sensitive_label_persistence": (
            SensitiveLabelPersistenceRule(
                definition=_definition(
                    "neurodivergence.sensitive_label_persistence",
                    "SensitiveLabelPersistenceRule",
                    ReasoningRuleCategory.SAFETY.value,
                    820,
                    risk_level=ReasoningRiskLevel.HIGH,
                )
            )
        ),
    }
    return tuple(by_id[rule_id] for rule_id in NEURODIVERGENCE_RULE_IDS)


__all__ = [
    "CERTAINTY_CONFIRMED",
    "CERTAINTY_HYPOTHESIS",
    "CERTAINTY_INSUFFICIENTLY_SUPPORTED",
    "CERTAINTY_IN_EVALUATION",
    "CERTAINTY_NOT_CONFIRMED",
    "CERTAINTY_RULED_OUT",
    "CERTAINTY_UNKNOWN",
    "EVIDENCE_CONTEMPORANEOUS_RECORD",
    "EVIDENCE_DIRECT_OBSERVATION",
    "EVIDENCE_MODEL_INTERPRETATION",
    "EVIDENCE_RETROSPECTIVE_SELF_REPORT",
    "EVIDENCE_SCREENING_RESULT",
    "EVIDENCE_THIRD_PARTY_REPORT",
    "EVIDENCE_UNKNOWN",
    "HEALTH_DOMAIN_ID",
    "NEURODIVERGENCE_RULE_IDS",
    "PERIOD_CURRENT",
    "PERIOD_HISTORICAL",
    "PERIOD_UNKNOWN",
    "CertaintyStatePreservationRule",
    "ClinicalStatusAuthorityRule",
    "ContradictionPreservationRule",
    "DevelopmentalTemporalityRule",
    "DifferentialExplanationsRule",
    "GlobalAttributionGuardRule",
    "LongitudinalCorroborationRule",
    "ObservationReportSeparationRule",
    "OverlapReasoningRule",
    "PurposeMinimizedCrossDomainRule",
    "ScreeningDiagnosisSeparationRule",
    "SensitiveLabelPersistenceRule",
    "SourceAuthorityRule",
    "TraitFunctionSeparationRule",
    "build_neurodivergence_rules",
    "classify_development_period",
    "classify_evidence_source",
    "describe_certainty_state",
    "detect_health_owned_clinical_status",
    "evaluate_certainty_transition",
    "evaluate_contradiction_preservation",
    "evaluate_developmental_temporality",
    "evaluate_longitudinal_corroboration",
    "is_persistence_restricted_content",
    "persistence_is_authorized",
    "persistence_requires_proposal",
    "proposal_preserves_hypothesis_status",
]
