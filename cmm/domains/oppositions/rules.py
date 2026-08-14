"""Phase 10.23 — Opposition Domain Rules and deterministic helpers.

A declarative domain + pure deterministic opposition helpers.  The helper
functions are state-free: no IO, no model calls, no registry mutation, no
internal clock.  They receive context explicitly and return deterministic
structures.

The six reasoning rules are ``@dataclass(frozen=True, slots=True)``
definitions exposing ``definition`` and ``evaluate(context)``, exactly like
the General, Health, Relationships, and University Domain rules, so they
compose with the existing cognitive layer.

Epistemic-safety core (frozen spec §9–§15, §31):
- source authority is preserved **by attribute** and **scope**, not by a naive
  global ranking; resolution is input-order invariant.
- provenance is not truth; a caller ``official=True`` label never fabricates
  authority; a source missing a usable reference cannot confirm a decision-
  critical material fact.
- equal top authority + compatible value corroborates; equal top authority +
  incompatible value stays unresolved (a verification need), never an
  arbitrary winner.
- malformed scope never becomes global scope; absent != valid empty !=
  malformed != unknown != stale != future != conflicting != grounded current.
- decision-critical missing/stale/conflicting/undergrounded official facts
  emit a structured monitoring / verification requirement and never create a
  calendar event or a scheduler.
- syllabus coverage is multidimensional and topic-identity grounded; forgetting
  is never proven by elapsed time alone and an aggregate percentage never
  overrides contradictory topic evidence.
- study feasibility applies hard constraints before preferences and consumes
  only minimal authorized Health/University projections (``authorized is True``),
  never a store and never detailed clinical/academic data.
- one mock is an observation, not a trend; incomparable mocks are never naively
  combined; mock performance never proves capacity or guaranteed success.
- alternative comparison and strategy versioning never silently switch/abandon
  the target: a proposal is not an adopted user decision.
"""

from __future__ import annotations

import math
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
)
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)
from cmm.domains.oppositions.catalog import CANONICAL_OPPOSITION_RULE_IDS
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

OPPOSITIONS_RULE_IDS: tuple[str, ...] = CANONICAL_OPPOSITION_RULE_IDS

# ── Closed scope states ──────────────────────────────────────────────────────
# ``None`` may never mean both "absent" and "malformed".  A malformed scope
# fails closed and never collapses to the unscoped/global semantics.

SCOPE_ABSENT = "absent"
SCOPE_VALID = "valid"
SCOPE_MALFORMED = "malformed"


def _scope_state(value: Any) -> str:
    """Classify a raw scope value into ABSENT / VALID / MALFORMED."""
    if value is None:
        return SCOPE_ABSENT
    if isinstance(value, str) and value.strip():
        return SCOPE_VALID
    return SCOPE_MALFORMED


def _usable_scalar_string(value: Any) -> str | None:
    """Return a usable scalar string identity, or ``None``.

    Never unwraps ``list``/``tuple``: a collection is malformed for a singular
    field and is not coerced into a scalar.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _usable_reference(value: Any) -> str | None:
    """Return the first usable reference identifier, or ``None``.

    A list/tuple yields the first usable scalar member.  Never fabricates a
    placeholder for an absent/blank reference.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if isinstance(value, (list, tuple)):
        for item in value:
            usable = _usable_reference(item)
            if usable is not None:
                return usable
    return None


def _reference_from(mapping: Mapping, *keys: str) -> str | None:
    for key in keys:
        usable = _usable_reference(mapping.get(key))
        if usable is not None:
            return usable
    return None


def _scalar_reference_from(mapping: Mapping, *keys: str) -> str | None:
    """Extract the first present **scalar** reference (V-pattern)."""
    for key in keys:
        if key in mapping:
            return _usable_scalar_string(mapping.get(key))
    return None


def _value_missing(value: Any) -> bool:
    """Only ``None`` and blank strings are missing; numeric zero/False are real values."""
    return value is None or (isinstance(value, str) and not value.strip())


def _values_compatible(left: Any, right: Any) -> bool:
    return (
        not _value_missing(left)
        and not _value_missing(right)
        and left == right
    )


def _incompatible(left: Any, right: Any) -> bool:
    if _value_missing(left) or _value_missing(right):
        return False
    return not _values_compatible(left, right)


def _boolean_true(value: Any) -> bool:
    """Strict runtime boolean: only the literal ``True`` counts (not truthiness)."""
    return isinstance(value, bool) and value


def _grants_trust(value: Any) -> bool:
    """Strict trust-bearing flag: only the literal ``True`` grants grounding/authorization.

    ``"true"``, ``"false"``, ``1``, ``0``, ``[]``, ``{}`` and arbitrary objects
    do NOT grant trust.  No coercion and no string parsing.
    """
    return value is True


def _trust_flag_malformed(value: Any) -> bool:
    """True when a trust-bearing field holds an unsupported type."""
    return value is not None and not isinstance(value, bool)


# ── Closed source classes ────────────────────────────────────────────────────

SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL = "specific_official_call"
SOURCE_CLASS_OFFICIAL_PUBLICATION = "official_publication"
SOURCE_CLASS_OFFICIAL_GAZETTE = "official_gazette"
SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION = "official_act_resolution"
SOURCE_CLASS_REGULATION = "regulation"
SOURCE_CLASS_PUBLIC_BODY_DOCUMENT = "public_body_document"
SOURCE_CLASS_EXTERNAL_OFFICIAL_SOURCE = "external_official_source"
SOURCE_CLASS_STUDY_SESSION = "study_session"
SOURCE_CLASS_ACADEMY_MATERIAL = "academy_material"
SOURCE_CLASS_PERSONAL_NOTE = "personal_note"
SOURCE_CLASS_USER_RECOLLECTION = "user_recollection"
SOURCE_CLASS_USER_MESSAGE = "user_message"
SOURCE_CLASS_MEMORY = "memory"
SOURCE_CLASS_INFERRED = "inferred"
SOURCE_CLASS_UNKNOWN = "unknown"

_SOURCE_CLASSES: tuple[str, ...] = (
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_OFFICIAL_GAZETTE,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_PUBLIC_BODY_DOCUMENT,
    SOURCE_CLASS_EXTERNAL_OFFICIAL_SOURCE,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_ACADEMY_MATERIAL,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_USER_MESSAGE,
    SOURCE_CLASS_MEMORY,
    SOURCE_CLASS_INFERRED,
    SOURCE_CLASS_UNKNOWN,
)

# ── Closed provenance states ─────────────────────────────────────────────────

PROVENANCE_GROUNDED = "grounded"
PROVENANCE_UNVERIFIED = "unverified"
PROVENANCE_CALLER_CLAIMED = "caller_claimed"
PROVENANCE_NONE = "none"

_GROUNDED_PROVENANCES: frozenset[str] = frozenset({PROVENANCE_GROUNDED})

# ── Closed specificity levels ────────────────────────────────────────────────

SPECIFICITY_SPECIFIC = "specific"
SPECIFICITY_GENERAL = "general"
SPECIFICITY_UNKNOWN = "unknown"

_SPECIFICITY_RANK = {
    SPECIFICITY_SPECIFIC: 2,
    SPECIFICITY_GENERAL: 1,
    SPECIFICITY_UNKNOWN: 0,
}

# ── Closed temporal states ───────────────────────────────────────────────────

TEMPORAL_VALID = "valid"
TEMPORAL_EXPIRED = "expired"
TEMPORAL_FUTURE = "future"
TEMPORAL_UNKNOWN = "unknown"
TEMPORAL_TIMELESS = "timeless"

_CURRENT_TEMPORAL_STATES: frozenset[str] = frozenset({TEMPORAL_VALID, TEMPORAL_TIMELESS})


def _normalize_source_class(value: Any) -> str:
    if isinstance(value, str) and value in _SOURCE_CLASSES:
        return value
    return SOURCE_CLASS_UNKNOWN


def _normalize_provenance(value: Any) -> str:
    if isinstance(value, str) and value in (
        PROVENANCE_GROUNDED,
        PROVENANCE_UNVERIFIED,
        PROVENANCE_CALLER_CLAIMED,
        PROVENANCE_NONE,
    ):
        return value
    return PROVENANCE_NONE


def _normalize_temporal(value: Any) -> str:
    if isinstance(value, str) and value in (
        TEMPORAL_VALID,
        TEMPORAL_EXPIRED,
        TEMPORAL_FUTURE,
        TEMPORAL_UNKNOWN,
        TEMPORAL_TIMELESS,
    ):
        return value
    return TEMPORAL_UNKNOWN


def _normalize_specificity(value: Any) -> str:
    if isinstance(value, str) and value in (
        SPECIFICITY_SPECIFIC,
        SPECIFICITY_GENERAL,
        SPECIFICITY_UNKNOWN,
    ):
        return value
    return SPECIFICITY_UNKNOWN


def _usable_attribute_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


# ── Per-attribute source-class priority (most authoritative first) ──────────
# Attribute-specific: a naive global ranking does NOT hold.  The specific
# official call leads for call-specific facts; official publications lead for
# exam-date/publication facts; the regulating material leads for general
# requirements.  A class not listed for an attribute is ``unknown`` (rank 0).

_CALL_FACT_PRIORITY = (
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_OFFICIAL_GAZETTE,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_EXTERNAL_OFFICIAL_SOURCE,
    SOURCE_CLASS_PUBLIC_BODY_DOCUMENT,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_ACADEMY_MATERIAL,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_USER_MESSAGE,
    SOURCE_CLASS_MEMORY,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_INFERRED,
)

_EXAM_DATE_PRIORITY = (
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_OFFICIAL_GAZETTE,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_EXTERNAL_OFFICIAL_SOURCE,
    SOURCE_CLASS_PUBLIC_BODY_DOCUMENT,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_ACADEMY_MATERIAL,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_USER_MESSAGE,
    SOURCE_CLASS_MEMORY,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_INFERRED,
)

_DEADLINE_PRIORITY = (
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_OFFICIAL_GAZETTE,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_EXTERNAL_OFFICIAL_SOURCE,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_PUBLIC_BODY_DOCUMENT,
    SOURCE_CLASS_ACADEMY_MATERIAL,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_USER_MESSAGE,
    SOURCE_CLASS_MEMORY,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_INFERRED,
)

_REGULATION_PRIORITY = (
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_OFFICIAL_GAZETTE,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_EXTERNAL_OFFICIAL_SOURCE,
    SOURCE_CLASS_PUBLIC_BODY_DOCUMENT,
    SOURCE_CLASS_ACADEMY_MATERIAL,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_USER_MESSAGE,
    SOURCE_CLASS_MEMORY,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_INFERRED,
)

_REQUIREMENT_PRIORITY = _REGULATION_PRIORITY

_STUDY_PROGRESS_PRIORITY = (
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_ACADEMY_MATERIAL,
    SOURCE_CLASS_EXTERNAL_OFFICIAL_SOURCE,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_PUBLIC_BODY_DOCUMENT,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_OFFICIAL_GAZETTE,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_USER_MESSAGE,
    SOURCE_CLASS_MEMORY,
    SOURCE_CLASS_INFERRED,
)

_ATTRIBUTE_PRIORITY: dict[str, tuple[str, ...]] = {
    "call_status": _CALL_FACT_PRIORITY,
    "application_window": _DEADLINE_PRIORITY,
    "application_deadline": _DEADLINE_PRIORITY,
    "exam_date": _EXAM_DATE_PRIORITY,
    "exam_format": _CALL_FACT_PRIORITY,
    "syllabus_version": _CALL_FACT_PRIORITY,
    "regulation": _REGULATION_PRIORITY,
    "eligibility_requirement": _REQUIREMENT_PRIORITY,
    "requirement": _REQUIREMENT_PRIORITY,
    "merit_rule": _REQUIREMENT_PRIORITY,
    "exercises": _CALL_FACT_PRIORITY,
    "scoring_rule": _CALL_FACT_PRIORITY,
    "public_body": _CALL_FACT_PRIORITY,
    "places": _CALL_FACT_PRIORITY,
    "procedure": _CALL_FACT_PRIORITY,
    "study_progress": _STUDY_PROGRESS_PRIORITY,
    "study_hours": _STUDY_PROGRESS_PRIORITY,
    "study_activity": _STUDY_PROGRESS_PRIORITY,
}

_DEFAULT_PRIORITY = _CALL_FACT_PRIORITY


def _source_rank(source: Mapping, attribute: str) -> int:
    """Return the source-class rank of ``source`` for ``attribute`` (0 = none)."""
    priority = _ATTRIBUTE_PRIORITY.get(attribute, _DEFAULT_PRIORITY)
    source_class = _normalize_source_class(source.get("source_class"))
    try:
        return len(priority) - priority.index(source_class)
    except ValueError:
        return 0


def _source_scope(source: Mapping) -> str | None:
    scope = source.get("scope")
    return scope if isinstance(scope, str) and scope.strip() else None


def _source_scope_malformed(source: Mapping) -> bool:
    return "scope" in source and _scope_state(source["scope"]) != SCOPE_VALID


def _source_speaks_about(source: Mapping, attribute: str) -> bool:
    supplied = source.get("supplied_attributes", ())
    if isinstance(supplied, (list, tuple)) and attribute in supplied:
        return True
    return (
        isinstance(source.get("attribute"), str)
        and source["attribute"] == attribute
    )


_MAPPING_IDENTITY_KEYS = frozenset(
    {
        "attribute",
        "supplied_attributes",
        "id",
        "source_id",
        "value",
        "source_class",
    }
)


def _mapping_evidence_is_opaque(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return not any(key in value for key in _MAPPING_IDENTITY_KEYS)


def _semantic_evidence_malformed(items: tuple) -> bool:
    return any(
        isinstance(item, Mapping) and _mapping_evidence_is_opaque(item)
        for item in items
    )


def _attribute_carrier_malformed(mapping: Mapping) -> bool:
    if "supplied_attributes" in mapping:
        supplied = mapping["supplied_attributes"]
        if supplied is None:
            return True
        if not isinstance(supplied, (list, tuple)):
            return True
        if any(not _usable_attribute_string(item) for item in supplied):
            return True
    if "attribute" in mapping:
        attribute = mapping["attribute"]
        if attribute is None:
            return True
        if not _usable_attribute_string(attribute):
            return True
    return False


def _source_relationship(source: Mapping, attribute: str) -> str:
    """relevant / irrelevant / unknown relationship to the target attribute."""
    has_supplied = "supplied_attributes" in source
    has_attribute = "attribute" in source

    if has_supplied:
        supplied = source["supplied_attributes"]
        if supplied is None:
            return "unknown"
        if not isinstance(supplied, (list, tuple)):
            return "unknown"
        if any(not _usable_attribute_string(item) for item in supplied):
            return "unknown"
        return "relevant" if attribute in supplied else "irrelevant"

    if has_attribute:
        attr_value = source["attribute"]
        if attr_value is None:
            return "unknown"
        if not _usable_attribute_string(attr_value):
            return "unknown"
        return "relevant" if attr_value == attribute else "irrelevant"

    return "unknown"


def _source_has_recognized_authority(source: Mapping) -> bool:
    """A value-less same-attribute source is authority-only evidence only when
    its authority metadata normalizes to recognized values."""
    source_class = _normalize_source_class(source.get("source_class"))
    provenance = _normalize_provenance(source.get("provenance"))
    temporal = _normalize_temporal(source.get("temporal"))
    specificity = _normalize_specificity(source.get("specificity"))
    return bool(
        source_class != SOURCE_CLASS_UNKNOWN
        and provenance in _GROUNDED_PROVENANCES
        and temporal in _CURRENT_TEMPORAL_STATES
        and specificity != SPECIFICITY_UNKNOWN
    )


def _source_is_incomplete_for(source: Mapping, attribute: str) -> bool:
    """A same-attribute source with neither a usable fact value nor coherent
    recognized authority identity makes target resolution uncertain."""
    if not _source_speaks_about(source, attribute):
        return False
    if not _value_missing(source.get("value")):
        return False
    return not _source_has_recognized_authority(source)


def _valid_supersession(candidate: Mapping, target: Mapping) -> bool:
    """A claimed replacement takes effect only when both source records are
    grounded, currently applicable, referenceable, scope-compatible, and the
    replacing source has at least the target's attribute-specific authority."""
    candidate_scope = candidate["scope"]
    target_scope = target["scope"]
    return bool(
        candidate["source_id"]
        and target["source_id"]
        and candidate["source_id"] != target["source_id"]
        and candidate["grounded"]
        and target["grounded"]
        and candidate["current"]
        and (target["current"] or target["temporal"] == TEMPORAL_UNKNOWN)
        and candidate["rank"] > 0
        and target["rank"] > 0
        and (
            candidate_scope is None
            or target_scope is None
            or candidate_scope == target_scope
        )
        and (
            candidate["rank"] > target["rank"]
            or (
                candidate["rank"] == target["rank"]
                and _SPECIFICITY_RANK[candidate["specificity"]]
                >= _SPECIFICITY_RANK[target["specificity"]]
            )
        )
    )


@dataclass(frozen=True, slots=True)
class _CollectionEvidence:
    """Malformed-aware collection normalization.

    Preserves the epistemic distinction between an absent collection, a valid
    (possibly empty) collection, and a malformed collection.  A malformed value
    (container or element) is never silently coerced into an empty collection or
    a filtered subset: ``absent != valid empty != malformed``.
    """

    items: tuple
    present: bool
    container_malformed: bool
    element_malformed: bool

    @property
    def malformed(self) -> bool:
        return self.container_malformed or self.element_malformed


def _normalize_collection(
    metadata: Mapping,
    key: str,
    *,
    require_mapping_elements: bool = False,
) -> _CollectionEvidence:
    if key not in metadata:
        return _CollectionEvidence((), False, False, False)
    value = metadata[key]
    if isinstance(value, (list, tuple)):
        element_malformed = (
            any(not isinstance(item, Mapping) for item in value)
            if require_mapping_elements
            else False
        )
        return _CollectionEvidence(tuple(value), True, False, element_malformed)
    return _CollectionEvidence((), True, True, False)


def _normalize_collection_value(
    value: Any,
    *,
    require_mapping_elements: bool = False,
) -> _CollectionEvidence:
    if value is None:
        return _CollectionEvidence((), False, False, False)
    if isinstance(value, (list, tuple)):
        element_malformed = (
            any(not isinstance(item, Mapping) for item in value)
            if require_mapping_elements
            else False
        )
        return _CollectionEvidence(tuple(value), True, False, element_malformed)
    return _CollectionEvidence((), True, True, False)


def _normalize_mapping(metadata: Mapping, key: str):
    if key not in metadata:
        return None, False, False
    value = metadata[key]
    if isinstance(value, Mapping):
        return value, True, False
    return None, True, True


@dataclass(frozen=True, slots=True)
class _ReferenceCollectionEvidence:
    items: tuple[str, ...]
    malformed: bool


def _normalize_references(values: Any) -> _ReferenceCollectionEvidence:
    if values is None:
        return _ReferenceCollectionEvidence(items=(), malformed=False)
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, (list, tuple)):
        return _ReferenceCollectionEvidence(items=(), malformed=True)
    seen: list[str] = []
    seen_set: set[str] = set()
    malformed = False
    for value in values:
        usable = _usable_scalar_string(value)
        if usable is None:
            malformed = True
        elif usable not in seen_set:
            seen_set.add(usable)
            seen.append(usable)
    return _ReferenceCollectionEvidence(items=tuple(seen), malformed=malformed)


def _normalize_reference_field(
    mapping: Mapping,
    key: str,
) -> _ReferenceCollectionEvidence:
    if key not in mapping:
        return _ReferenceCollectionEvidence(items=(), malformed=False)
    value = mapping[key]
    if value is None:
        return _ReferenceCollectionEvidence(items=(), malformed=True)
    return _normalize_references(value)


# ═══════════════════════════════════════════════════════════════════════════════
# Rule 1 — OfficialCallPriorityRule
# ═══════════════════════════════════════════════════════════════════════════════


def classify_opposition_source_authority(
    *,
    attribute: str,
    sources: tuple = (),
    scope: str | None = None,
    require_reference: bool = False,
) -> dict:
    """Classify the authoritative source for a *single* opposition attribute
    using grounded, attribute-specific, scope-aware evidence.

    Authority derives from attribute, source class, provenance, temporal
    validity, specificity and scope.  A caller cannot fabricate ``official``: a
    source is authoritative only with grounded provenance and a grounded source
    class.  Recency alone never wins.  A missing usable reference never confirms
    a material fact when ``require_reference`` is set.  Equal-authority
    incompatible claims with no valid supersession remain unresolved (never an
    arbitrary input-order winner).  Malformed scope never becomes global.
    """
    attribute_id = _usable_scalar_string(attribute)
    if attribute_id is None:
        return {
            "attribute": None,
            "authority_resolved": False,
            "authoritative_source_id": None,
            "authority_class": None,
            "authoritative_value": None,
            "fact_value_known": False,
            "fact_resolved": False,
            "supporting_source_ids": (),
            "matched_sources": (),
            "superseded_sources": (),
            "authority_unknown": True,
            "conflict": False,
            "reason": "malformed_requested_attribute",
        }
    attribute = attribute_id
    if _scope_state(scope) == SCOPE_MALFORMED:
        return {
            "attribute": attribute,
            "authority_resolved": False,
            "authoritative_source_id": None,
            "authority_class": None,
            "authoritative_value": None,
            "fact_value_known": False,
            "fact_resolved": False,
            "supporting_source_ids": (),
            "matched_sources": (),
            "superseded_sources": (),
            "authority_unknown": True,
            "conflict": False,
            "reason": "malformed_requested_scope",
        }

    sources_evidence = _normalize_collection_value(
        sources, require_mapping_elements=True
    )
    sources = sources_evidence.items
    evaluated: list[dict] = []
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        supplied = source.get("supplied_attributes", ())
        if not isinstance(supplied, (list, tuple)) or attribute not in supplied:
            continue
        scope_value = _source_scope(source)
        if scope is not None and scope_value is not None and scope_value != scope:
            continue
        provenance = _normalize_provenance(source.get("provenance"))
        temporal = _normalize_temporal(source.get("temporal"))
        source_class = _normalize_source_class(source.get("source_class"))
        specificity = _normalize_specificity(source.get("specificity"))
        grounded = provenance in _GROUNDED_PROVENANCES
        current = temporal in _CURRENT_TEMPORAL_STATES
        rank = _source_rank(source, attribute)
        supersedes_evidence = _normalize_reference_field(source, "supersedes")
        superseded_by_evidence = _normalize_reference_field(source, "superseded_by")
        evaluated.append(
            {
                "source_id": _usable_scalar_string(source.get("source_id")),
                "source_class": source_class,
                "provenance": provenance,
                "temporal": temporal,
                "specificity": specificity,
                "scope": scope_value,
                "grounded": grounded,
                "current": current,
                "rank": rank,
                "value": source.get("value"),
                "supersedes": (
                    ()
                    if supersedes_evidence.malformed
                    else supersedes_evidence.items
                ),
                "supersedes_malformed": supersedes_evidence.malformed,
                "superseded_by": (
                    ()
                    if superseded_by_evidence.malformed
                    else superseded_by_evidence.items
                ),
                "superseded_by_malformed": superseded_by_evidence.malformed,
            }
        )

    incomplete_sources = [
        source
        for source in sources
        if isinstance(source, Mapping)
        and _source_is_incomplete_for(source, attribute)
        and (
            scope is None
            or (source_scope := _source_scope(source)) is None
            or source_scope == scope
        )
    ]
    malformed_carrier = any(
        isinstance(source, Mapping) and _attribute_carrier_malformed(source)
        for source in sources
    )
    malformed_source_scope = any(
        isinstance(source, Mapping) and _source_scope_malformed(source)
        for source in sources
    )
    unusable_identity = any(
        isinstance(source, Mapping)
        and _source_speaks_about(source, attribute)
        and _usable_scalar_string(source.get("source_id")) is None
        and not _value_missing(source.get("value"))
        for source in sources
    )
    relation_unknown = any(
        isinstance(source, Mapping)
        and _source_relationship(source, attribute) == "unknown"
        for source in sources
    )
    # Missing usable reference cannot confirm a material fact when required.
    missing_reference = bool(
        require_reference
        and any(
            isinstance(source, Mapping)
            and _source_speaks_about(source, attribute)
            and not _value_missing(source.get("value"))
            and _usable_reference(source.get("source_reference", source.get("source_ref")))
            is None
            for source in sources
        )
    )
    malformed_relation = any(
        source["supersedes_malformed"] or source["superseded_by_malformed"]
        for source in evaluated
    )
    malformed_relation_conflict = malformed_relation and any(
        not _values_compatible(left["value"], right["value"])
        for index, left in enumerate(evaluated)
        for right in evaluated[index + 1 :]
    )
    if (
        sources_evidence.malformed
        or _semantic_evidence_malformed(sources)
        or incomplete_sources
        or malformed_carrier
        or malformed_source_scope
        or unusable_identity
        or relation_unknown
        or missing_reference
        or malformed_relation
    ):
        return {
            "attribute": attribute,
            "authority_resolved": False,
            "authoritative_source_id": None,
            "authority_class": None,
            "authoritative_value": None,
            "fact_value_known": False,
            "fact_resolved": False,
            "supporting_source_ids": (),
            "matched_sources": tuple(evaluated),
            "superseded_sources": (),
            "authority_unknown": True,
            "conflict": malformed_relation_conflict,
            "reason": (
                "missing_usable_reference"
                if missing_reference
                else "incomplete_same_attribute_evidence"
                if incomplete_sources
                else "unusable_source_identity"
                if unusable_identity
                else "relation_unknown_source"
                if relation_unknown
                else "malformed_source_evidence"
            ),
        }

    candidates = [
        source
        for source in evaluated
        if (
            source["source_id"] is not None
            and source["grounded"]
            and source["current"]
            and source["rank"] > 0
        )
    ]
    unresolved_temporal = [
        source
        for source in evaluated
        if (
            source["source_id"] is not None
            and source["grounded"]
            and source["temporal"] == TEMPORAL_UNKNOWN
            and source["rank"] > 0
        )
    ]
    if not candidates:
        return {
            "attribute": attribute,
            "authority_resolved": False,
            "authoritative_source_id": None,
            "authority_class": None,
            "authoritative_value": None,
            "fact_value_known": False,
            "fact_resolved": False,
            "supporting_source_ids": (),
            "matched_sources": tuple(evaluated),
            "superseded_sources": (),
            "authority_unknown": True,
            "conflict": False,
            "reason": "no_grounded_current_authority",
        }

    superseded_ids: set[str] = set()
    supersession_candidates = (*candidates, *unresolved_temporal)
    by_source_id = {
        source["source_id"]: source
        for source in supersession_candidates
        if source["source_id"] is not None
    }
    for candidate in candidates:
        for target in candidate["supersedes"]:
            target_candidate = by_source_id.get(target)
            if (
                target_candidate is not None
                and _valid_supersession(candidate, target_candidate)
            ):
                superseded_ids.add(target)
        for target in supersession_candidates:
            if (
                candidate["source_id"] in target["superseded_by"]
                and _valid_supersession(candidate, target)
            ):
                superseded_ids.add(target["source_id"])

    active = [e for e in candidates if e["source_id"] not in superseded_ids]
    if not active:
        active = candidates

    best_rank = max(e["rank"] for e in active)
    best = [e for e in active if e["rank"] == best_rank]
    best_specificity = max(_SPECIFICITY_RANK[e["specificity"]] for e in best)
    top = [
        e for e in best
        if _SPECIFICITY_RANK[e["specificity"]] == best_specificity
    ]

    potentially_current_unknown = [
        candidate
        for candidate in unresolved_temporal
        if candidate["source_id"] not in superseded_ids
        and (
            candidate["rank"] > best_rank
            or (
                candidate["rank"] == best_rank
                and _SPECIFICITY_RANK[candidate["specificity"]]
                >= best_specificity
            )
        )
        and any(
            not _values_compatible(candidate["value"], current["value"])
            for current in top
        )
    ]
    if potentially_current_unknown:
        return {
            "attribute": attribute,
            "authority_resolved": False,
            "authoritative_source_id": None,
            "authority_class": None,
            "authoritative_value": None,
            "fact_value_known": False,
            "fact_resolved": False,
            "supporting_source_ids": (),
            "matched_sources": tuple(evaluated),
            "superseded_sources": tuple(sorted(superseded_ids)),
            "authority_unknown": True,
            "conflict": True,
            "reason": "temporal_authority_unresolved",
        }

    if len(top) > 1:
        top_values = [source["value"] for source in top]
        if all(_values_compatible(top_values[0], value) for value in top_values[1:]):
            supporting_source_ids = tuple(
                sorted(
                    source_id
                    for source_id in (
                        _usable_scalar_string(source["source_id"])
                        for source in top
                    )
                    if source_id is not None
                )
            )
            return {
                "attribute": attribute,
                "authority_resolved": True,
                "authoritative_source_id": None,
                "authority_class": None,
                "authoritative_value": top_values[0],
                "fact_value_known": True,
                "fact_resolved": True,
                "supporting_source_ids": supporting_source_ids,
                "matched_sources": tuple(evaluated),
                "superseded_sources": tuple(sorted(superseded_ids)),
                "authority_unknown": False,
                "conflict": False,
                "reason": "corroborated",
            }
        return {
            "attribute": attribute,
            "authority_resolved": False,
            "authoritative_source_id": None,
            "authority_class": None,
            "authoritative_value": None,
            "fact_value_known": False,
            "fact_resolved": False,
            "supporting_source_ids": (),
            "matched_sources": tuple(evaluated),
            "superseded_sources": tuple(sorted(superseded_ids)),
            "authority_unknown": True,
            "conflict": True,
            "reason": "equal_authority_conflict",
        }

    winner = top[0]
    fact_value_known = not _value_missing(winner["value"])
    return {
        "attribute": attribute,
        "authority_resolved": True,
        "authoritative_source_id": winner["source_id"],
        "authority_class": winner["source_class"],
        "authoritative_value": winner["value"],
        "fact_value_known": fact_value_known,
        "fact_resolved": fact_value_known,
        "supporting_source_ids": (
            (_usable_scalar_string(winner["source_id"]),)
            if _usable_scalar_string(winner["source_id"]) is not None
            else ()
        ),
        "matched_sources": tuple(evaluated),
        "superseded_sources": tuple(sorted(superseded_ids)),
        "authority_unknown": False,
        "conflict": False,
        "reason": "resolved",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Rule 2 — OppositionTemporalValidityRule (+ call-monitoring signal)
# ═══════════════════════════════════════════════════════════════════════════════


def conditional_verification_trigger(
    *,
    fact_state: str,
    decision_critical: bool,
    attribute: str | None,
    scope: str | None = None,
) -> dict:
    """Structured verification need for a decision-critical official fact.

    The rule request is READ_ONLY + OFFICIAL_ONLY.  It never schedules, polls,
    or creates calendar events.  This is a structured requirement, not a
    connector.
    """
    critical = _boolean_true(decision_critical)
    verification_needed = bool(
        fact_state in ("missing", "stale", "conflicting", "unknown")
        or (critical and fact_state != "confirmed_official")
    )
    return {
        "verification_needed": verification_needed,
        "fact_state": fact_state,
        "decision_critical": critical,
        "attribute": attribute,
        "scope": scope,
        "requires_user_confirmation": critical,
        "read_only": True,
        "official_only": True,
        "monitoring_requirement": (
            {
                "kind": "official_verification",
                "read_only": True,
                "official_only": True,
                "attribute": attribute,
            }
            if verification_needed and critical
            else None
        ),
    }


def classify_opposition_temporal(
    *,
    fact: Any,
    decision_critical: bool = False,
) -> dict:
    """Classify the temporal state of a changing opposition fact.

    Preserves: current/applicable, stale/expired/superseded, future,
    unknown, conflicting, missing, malformed.  A bare date string is never a
    confirmed deadline; current status requires grounding.  No calendar event
    is ever created here.
    """
    if fact is None:
        return {
            "state": "missing",
            "current": False,
            "confirmed": False,
            "verification_needed": bool(_boolean_true(decision_critical)),
            "monitoring": conditional_verification_trigger(
                fact_state="missing",
                decision_critical=decision_critical,
                attribute=None,
            ),
            "calendar_not_created": True,
            "reason": "missing",
        }
    if not isinstance(fact, Mapping):
        return {
            "state": "malformed",
            "current": False,
            "confirmed": False,
            "verification_needed": True,
            "monitoring": conditional_verification_trigger(
                fact_state="malformed",
                decision_critical=decision_critical,
                attribute=None,
            ),
            "calendar_not_created": True,
            "reason": "malformed",
        }
    critical = _boolean_true(decision_critical) or _boolean_true(
        fact.get("decision_critical")
    )

    temporal = _normalize_temporal(fact.get("temporal"))
    grounded = _grants_trust(fact.get("grounded"))
    reference = _scalar_reference_from(
        fact, "source_reference", "source_ref", "source_id"
    )
    has_usable_reference = reference is not None

    # Bare date string value is not a confirmed official deadline.
    bare_value = bool(
        isinstance(fact.get("value"), str)
        and fact.get("value").strip()
        and not grounded
    )

    if temporal == TEMPORAL_EXPIRED:
        state = "stale"
    elif temporal == TEMPORAL_FUTURE:
        state = "future"
    elif temporal == TEMPORAL_UNKNOWN:
        state = "unknown"
    elif temporal in _CURRENT_TEMPORAL_STATES:
        if grounded and has_usable_reference:
            state = "current"
        else:
            # grounded provenance absent, or usable reference missing.
            state = "undergrounded" if grounded else "unknown"
    else:
        state = "unknown"

    confirmed = bool(state == "current")
    verification_needed = bool(
        critical
        and (
            state in ("missing", "stale", "conflicting", "unknown")
            or state == "malformed"
            or (state == "undergrounded" and not confirmed)
        )
    )
    if bare_value:
        verification_needed = True

    monitoring = conditional_verification_trigger(
        fact_state=state,
        decision_critical=critical,
        attribute=_usable_scalar_string(fact.get("attribute")),
        scope=_source_scope(fact),
    )

    return {
        "state": state,
        "current": confirmed,
        "confirmed": confirmed,
        "grounded": grounded,
        "has_usable_reference": has_usable_reference,
        "verification_needed": bool(verification_needed),
        "monitoring": monitoring,
        "calendar_not_created": True,
        "reason": state,
        "value": fact.get("value"),
        "supplied_deadline": isinstance(fact.get("value"), str) and not grounded,
    }


def opposition_call_monitoring(
    *,
    objective_active: bool,
    call_state: str,
    decision_critical: bool = True,
) -> dict:
    """Emit a structured monitoring / verification requirement for an active
    opposition objective when relevant call state is missing/stale/conflicting/
    under-grounded or due for review.

    This is semantic only: no scheduler, no polling daemon, no browser
    automation, no notification service (deferred infrastructure).
    """
    active = _boolean_true(objective_active)
    due_states = ("missing", "stale", "conflicting", "unknown", "undergrounded")
    monitoring_needed = bool(
        active and call_state in due_states
    )
    return {
        "monitoring_needed": monitoring_needed,
        "objective_active": active,
        "call_state": call_state,
        "kind": "official_verification_requirement",
        "scheduler_started": False,
        "notification_sent": False,
        "browser_automation": False,
        "verification": conditional_verification_trigger(
            fact_state=call_state,
            decision_critical=decision_critical,
            attribute="call",
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Rule 3 — SyllabusCoverageRule
# ═══════════════════════════════════════════════════════════════════════════════


def _parse_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def evaluate_syllabus_coverage(
    *,
    topics: tuple = (),
    syllabus_version: Any = None,
    syllabus_current: Any = None,
    past_minutes: Any = None,
) -> dict:
    """Evaluate multidimensional study coverage over topic records.

    Keeps independent dimensions: studied/exposure state, depth, revision
    state, review due / retention risk, mock-linked evidence, pending topics,
    unknown topics.  Duplicate identities are not double-counted; identityless
    topics cannot establish complete coverage; a valid empty collection is not
    absent/malformed; elapsed time may indicate retention risk but never proves
    forgetting; an aggregate percentage can never override contradictory
    topic-level evidence.
    """
    topics_evidence = _normalize_collection_value(
        topics, require_mapping_elements=True
    )
    topic_list = topics_evidence.items
    version_usable = _usable_scalar_string(syllabus_version)
    version_is_current = _boolean_true(syllabus_current)

    malformed = topics_evidence.malformed or _semantic_evidence_malformed(topic_list)

    studied: set[str] = set()
    studied_have_identity = False
    mock_linked: set[str] = set()
    pending: set[str] = set()
    unknown_topics: list[str] = []
    depth_total = 0
    depth_count = 0
    review_due_count = 0
    studied_records = 0

    for topic in topic_list:
        if not isinstance(topic, Mapping):
            unknown_topics.append("container-member")
            continue
        identity = _usable_scalar_string(topic.get("id", topic.get("topic_id")))
        studied_state = _usable_scalar_string(topic.get("studied"))
        depth_value = _parse_non_negative_int(topic.get("depth"))
        revision_state = _usable_scalar_string(topic.get("revision"))
        mock_mapped = _boolean_true(topic.get("mock_mapped"))
        review_due = _boolean_true(topic.get("review_due"))

        if identity is None:
            # identityless topic cannot establish complete coverage
            if not _value_missing(topic.get("studied")):
                unknown_topics.append("identityless")
            continue
        if studied_state == "yes":
            studied.add(identity)
            studied_have_identity = True
            studied_records += 1
            if depth_value is not None:
                depth_total += depth_value
                depth_count += 1
        elif studied_state == "no":
            pending.add(identity)
        else:
            # unknown topic state
            unknown_topics.append(identity)
        if mock_mapped:
            mock_linked.add(identity)
        if review_due:
            review_due_count += 1
        if revision_state == "pending":
            pending.add(identity)

    known_identities = studied | pending
    pending = pending - studied
    unknown_topic_count = len(unknown_topics)
    studied_count = len(studied)
    pending_count = len(pending)
    known_count = len(known_identities)

    # An aggregate percentage cannot override contradictory topic evidence.
    coverage_percent = None
    if known_count > 0:
        coverage_percent = round(studied_count / known_count, 4)

    # Complete coverage requires identity-grounded studied topics, a current
    # syllabus version, and no pending/unknown topics.
    complete = bool(
        studied_have_identity
        and not malformed
        and pending_count == 0
        and unknown_topic_count == 0
        and studied_count > 0
        and version_usable is not None
        and version_is_current
    )

    # Retention risk: review due signals risk, not proven forgetting.  Elapsed
    # time (past_minutes) may be reported as a review cue but never proves
    # forgetting.
    retention_risk = bool(review_due_count > 0)
    elapsed_time_cue = (
        _parse_non_negative_int(past_minutes) is not None
        and int(past_minutes) > 0
    )
    forgetting_proven = False  # never proven by elapsed time alone
    review_cue = bool(retention_risk or elapsed_time_cue)

    return {
        "valid": not malformed,
        "complete": complete,
        "malformed": malformed,
        "container_present": topics_evidence.present,
        "valid_empty": bool(
            topics_evidence.present and not topic_list and not malformed
        ),
        "studied_count": studied_count,
        "pending_count": pending_count,
        "unknown_count": unknown_topics.count("identityless")
        + sum(1 for value in unknown_topics if value != "identityless"),
        "study_depth_total": depth_total,
        "study_depth_records": depth_count,
        "mock_linked_count": len(mock_linked),
        "review_due_count": review_due_count,
        "retention_risk": retention_risk,
        "review_cue": review_cue,
        "forgetting_proven": forgetting_proven,
        "elapsed_time_cue": elapsed_time_cue,
        "unknown_topics": tuple(dict.fromkeys(unknown_topics)),
        "duplicate_double_counted": False,
        "duplicate_ignored": topics_evidence.present,
        "identityless_blocked_complete": bool(
            not studied_have_identity and studied_count == 0
        ),
        "syllabus_version_current": version_is_current,
        "syllabus_version_unknown": version_usable is None,
        "aggregate_bypass": False,
        "coverage_percent": coverage_percent,
        "dimensions": {
            "studied": studied_count,
            "pending": pending_count,
            "depth": depth_count,
            "revision_review_due": review_due_count,
            "mock_linked": len(mock_linked),
            "unknown": unknown_topic_count,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Rule 4 — StudyFeasibilityRule (+ Health/University minimal projections)
# ═══════════════════════════════════════════════════════════════════════════════


def _parse_non_negative_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def evaluate_study_feasibility(
    *,
    remaining_hours: Any = None,
    available_hours: Any = None,
    target_days: Any = None,
    review_hours: Any = None,
    mock_hours: Any = None,
    health_constraint: Any = None,
    university_projection: Any = None,
    user_constraints: tuple = (),
) -> dict:
    """Evaluate study-plan feasibility through the canonical staged pipeline.

    validate evidence -> hard constraints -> available capacity ->
    target-date feasibility -> valid scenarios -> trade-offs -> proposal.

    Hard constraints precede preferences.  ``health_constraint`` and
    ``university_projection`` are minimal authorized projections: only the
    literal ``authorized is True`` grants transfer; ``"true"``/``"false"``/``1``/
    ``0``/objects never authorize.  Malformed authorized caps fail closed as
    unknown, never permissive.  No plan is adopted and no Health/University
    store is read.
    """
    remaining = _parse_non_negative_number(remaining_hours)
    review = _parse_non_negative_number(review_hours)
    mock = _parse_non_negative_number(mock_hours)
    available = _parse_non_negative_number(available_hours)
    target = _parse_non_negative_int(target_days)
    malformed_numeric_any = bool(
        (remaining_hours is not None and remaining is None)
        or (review_hours is not None and review is None)
        or (mock_hours is not None and mock is None)
        or (available_hours is not None and available is None)
    )

    required_work = 0.0
    work_unknown = False
    if remaining_hours is not None:
        if remaining is None:
            work_unknown = True
        else:
            required_work += remaining
    if review_hours is not None:
        if review is None:
            work_unknown = True
        else:
            required_work += review
    if mock_hours is not None:
        if mock is None:
            work_unknown = True
        else:
            required_work += mock

    # ── validate evidence / resolve available capacity ─────────────────────
    provided_any = any(
        value is not None
        for value in (
            remaining_hours,
            available_hours,
            target_days,
            review_hours,
            mock_hours,
        )
    )
    capacity = available
    capacity_unknown = available is None and (available_hours is not None)
    cap_source = "user" if available is not None else None

    health_evidence, health_present, health_malformed = _normalize_mapping(
        {"h": health_constraint}, "h"
    )
    health = health_evidence
    health_authorized = False
    if health_present and not health_malformed and health is not None:
        if _grants_trust(health.get("authorized")):
            health_authorized = True
            health_cap = _parse_non_negative_number(health.get("functional_cap_hours"))
            if health_cap is not None:
                capacity = health_cap
                cap_source = "health"
            else:
                # malformed authorized cap remains unknown, never permissive
                capacity_unknown = True
        else:
            # not literally authorized True -> no transfer
            if health.get("authorized") is not None:
                capacity_unknown = True

    uni_evidence, uni_present, uni_malformed = _normalize_mapping(
        {"u": university_projection}, "u"
    )
    uni = uni_evidence
    uni_authorized = False
    uni_available = None
    if uni_present and not uni_malformed and uni is not None:
        if _grants_trust(uni.get("authorized")):
            uni_authorized = True
            uni_available = _parse_non_negative_number(uni.get("available_hours"))
            uni_workload = _parse_non_negative_number(uni.get("workload_hours"))
            if uni_available is None and uni.get("available_hours") is not None:
                capacity_unknown = True
            elif uni_available is not None and capacity is not None:
                capacity = min(capacity, uni_available)
            elif uni_available is not None:
                capacity = uni_available
            if capacity is not None and uni_workload is not None:
                capacity = max(0, capacity - uni_workload)
        else:
            if uni.get("authorized") is not None:
                capacity_unknown = True

    # ── target-date feasibility / hard constraints / scenarios ─────────────
    evidence_unknown = (work_unknown or remaining_hours is None) and provided_any
    has_malformed_numeric = malformed_numeric_any
    unmet_hard_constraints: list[str] = []
    scenarios: list[dict] = []
    trade_offs: list[dict] = []
    resolved = not (evidence_unknown or has_malformed_numeric or capacity_unknown)

    if not provided_any:
        resolved = False
        evidence_unknown = True

    if not resolved or capacity is None:
        feasibility = "unresolved"
    elif required_work > capacity:
        feasibility = "infeasible"
        unmet_hard_constraints.append("capacity_exceeded")
        scenarios.append(
            {
                "feasible": False,
                "class": "unmet_hard_constraint",
                "reason": "capacity_exceeded",
                "adopted": False,
            }
        )
    else:
        feasibility = "feasible"
        scenarios.append(
            {
                "feasible": True,
                "class": "best_fit",
                "daily_hours": round(
                    required_work / (target if target else 1), 2
                )
                if required_work > 0 and target
                else None,
                "adopted": False,
            }
        )

    infeasible = feasibility == "infeasible"
    unknown_constraint_confirmed = not resolved

    return {
        "feasibility": feasibility,
        "feasible": feasibility == "feasible",
        "infeasible": infeasible,
        "unresolved": not resolved,
        "evidence_unknown": evidence_unknown,
        "malformed_numeric": has_malformed_numeric,
        "capacity_unknown": capacity_unknown,
        "capacity_hours": capacity,
        "capacity_source": cap_source,
        "hard_constraints_met": not infeasible,
        "unmet_hard_constraints": tuple(unmet_hard_constraints),
        "hard_before_preferences": True,
        "scenarios": tuple(scenarios),
        "trade_offs": tuple(trade_offs),
        "proposal_only": True,
        "adopted_plan": False,
        "target_unchanged": True,
        "health_authorized": health_authorized,
        "university_authorized": uni_authorized,
        "clinical_details_consumed": False,
        "university_state_merged": False,
        "unknown_constraint_confirmed": unknown_constraint_confirmed,
        "target_date_invalid": target_days is not None and target is None,
        "calendar_not_modified": True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Rule 5 — MockExamInterpretationRule
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_SCORING_MISSING = "missing"
MOCK_SCORING_PENALTY = "penalty"
MOCK_SCORING_STANDARD = "standard"


def _normalize_score(value: Any) -> int | float | None:
    return _parse_non_negative_number(value)


def _normalize_scoring(value: Any) -> str:
    if value == MOCK_SCORING_PENALTY or value == MOCK_SCORING_STANDARD:
        return value
    if isinstance(value, str) and value.strip():
        return value.strip()
    return MOCK_SCORING_MISSING


def evaluate_mock_performance(
    *,
    mocks: tuple = (),
) -> dict:
    """Interpret mock-exam evidence keeping observation vs trend distinct.

    A single mock is an observation, never a trend.  A trend requires enough
    comparable, temporally ordered evidence (same/compatible format and scoring,
    valid chronology).  Incomparable mocks are never naively combined; unknown
    chronology prevents a temporal trend claim; duplicate identities are not
    double-counted; input order does not change the semantic trend result.
    Never infers intelligence, fixed capacity, or a guaranteed official-exam
    result.  Speed and knowledge remain separate where evidence permits.
    """
    mocks_evidence = _normalize_collection_value(
        mocks, require_mapping_elements=True
    )
    records = mocks_evidence.items
    malformed = mocks_evidence.malformed or _semantic_evidence_malformed(records)

    timeline: list[dict] = []
    seen: set[str] = set()
    duplicates = 0
    unknown_chronology = False
    has_knowledge = False
    has_speed = False
    has_process_error = False

    # Group records that are actually comparable for a trend by
    # (scoring, format).  A trend is only valid within one comparable group
    # with temporally ordered records; incomparable mocks are never combined.
    comparable_groups: dict[tuple[str, str], list[dict]] = {}

    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            malformed = True
            continue
        identity = _usable_scalar_string(record.get("id", record.get("mock_id")))
        if identity is not None:
            if identity in seen:
                duplicates += 1
                continue
            seen.add(identity)
        else:
            identity = f"mock-{index}"
        score = _normalize_score(record.get("score", record.get("correct")))
        total = _parse_non_negative_number(record.get("total"))
        scoring = _normalize_scoring(record.get("scoring"))
        date = _usable_scalar_string(record.get("date"))
        mock_format = _usable_scalar_string(
            record.get("format", record.get("exam_format")) or "unknown"
        )
        speed_score = _normalize_score(record.get("speed_score", record.get("speed")))
        process_errors = _parse_non_negative_int(record.get("process_errors"))
        knowledge_errors = _parse_non_negative_int(record.get("knowledge_errors"))

        has_knowledge = has_knowledge or score is not None
        has_speed = has_speed or speed_score is not None
        has_process_error = has_process_error or (
            process_errors is not None and process_errors > 0
        )
        if date is None:
            unknown_chronology = True

        percent = None
        if (
            score is not None
            and total is not None
            and total > 0
            and scoring != MOCK_SCORING_MISSING
        ):
            percent = round(score / total, 4)
        timeline.append(
            {
                "id": identity,
                "score": score,
                "total": total,
                "percent": percent,
                "scoring": scoring,
                "date": date,
                "format": mock_format,
                "speed_score": speed_score,
                "process_errors": process_errors,
                "knowledge_errors": knowledge_errors,
            }
        )
        key = (scoring, mock_format)
        if (
            score is not None
            and total is not None
            and total > 0
            and scoring != MOCK_SCORING_MISSING
            # temporal ordering requires a usable date
            and date is not None
        ):
            comparable_groups.setdefault(key, []).append(
                {
                    "id": identity,
                    "date": date,
                    "score": score,
                }
            )

    comparable_count = sum(len(group) for group in comparable_groups.values())

    trend_state = "no_trend"
    trend_inferred = False
    trend_slope = None
    best_group: list[dict] = []
    for group in comparable_groups.values():
        if len(group) >= 2 and len(group) > len(best_group):
            best_group = group
    if best_group:
        ordered = sorted(best_group, key=lambda entry: str(entry["date"]))
        trend_state = "trend"
        trend_inferred = True
        trend_slope = ordered[-1]["score"] - ordered[0]["score"]

    return {
        "observation_count": len(timeline),
        "duplicates_ignored": duplicates,
        "malformed": malformed,
        "has_scores": has_knowledge,
        "speed_dimension_present": has_speed,
        "process_error_dimension_present": has_process_error,
        "scoring_regimes": tuple(sorted({entry["scoring"] for entry in timeline})),
        "formats": tuple(sorted({entry["format"] for entry in timeline})),
        "comparable_count": comparable_count,
        "chronology_unknown": unknown_chronology,
        "trend_state": trend_state,
        "trend_inferred": trend_inferred,
        "trend_slope": trend_slope,
        "one_mock_is_trend": False,
        "incompatible_combined": False,
        "intelligence_inferred": False,
        "capacity_inferred": False,
        "pass_guaranteed": False,
        "speed_knowledge_separated": has_speed and has_knowledge,
        "format_error_separated": has_process_error,
        "timeline": tuple(timeline),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Rule 6 — AlternativeRouteRule (+ versioned strategy preservation)
# ═══════════════════════════════════════════════════════════════════════════════


def compare_alternative_routes(
    *,
    primary: Any,
    alternatives: tuple = (),
    priority_weights: Mapping | None = None,
) -> dict:
    """Compare a primary route with alternatives while preserving user decision
    ownership.

    May compare eligibility, syllabus overlap, exam format, official timing,
    study effort, requirements, merits, constraints, switching cost, uncertainty
    and trade-offs.  Fundamental invariant:
    ``alternative considered != alternative selected != primary target abandoned``.
    A better computed scenario is still only a proposal; hard constraints beat
    preferences; input order does not change semantics; malformed route identity
    never merges routes.
    """
    primary_evidence, primary_present, primary_malformed = _normalize_mapping(
        {"p": primary}, "p"
    )
    primary_route = primary_evidence
    alternatives_evidence = _normalize_collection_value(
        alternatives, require_mapping_elements=True
    )
    route_items = alternatives_evidence.items

    if not primary_present:
        return {
            "resolved": False,
            "reason": "missing_primary",
            "proposal_only": True,
            "target_unchanged": True,
            "primary_abandoned": False,
            "alternatives_considered": (),
            "trade_offs": (),
            "target_changed": False,
        }
    if primary_malformed or primary_route is None:
        return {
            "resolved": False,
            "reason": "malformed_primary",
            "proposal_only": True,
            "target_unchanged": True,
            "primary_abandoned": False,
            "alternatives_considered": (),
            "trade_offs": (),
            "target_changed": False,
        }

    primary_id = _usable_scalar_string(primary_route.get("id", primary_route.get("body_id")))
    if primary_id is None:
        return {
            "resolved": False,
            "reason": "malformed_primary_identity",
            "proposal_only": True,
            "target_unchanged": True,
            "primary_abandoned": False,
            "alternatives_considered": (),
            "trade_offs": (),
            "target_changed": False,
        }

    evaluated_routes: list[dict] = []
    route_ids: set[str] = set()
    malformed_route_member = alternatives_evidence.malformed
    conditional_requirements: list[str] = []
    stale_route_ids: set[str] = set()

    for item in route_items:
        if not isinstance(item, Mapping):
            malformed_route_member = True
            continue
        route_id = _usable_scalar_string(item.get("id", item.get("body_id")))
        if route_id is None:
            malformed_route_member = True
            continue
        if route_id == primary_id:
            continue
        if route_id in route_ids:
            continue
        route_ids.add(route_id)
        overlap = _parse_non_negative_number(item.get("syllabus_overlap"))
        effort = _parse_non_negative_number(item.get("effort_hours"))
        eligibility_known = _usable_scalar_string(
            item.get("eligibility", item.get("eligibility_state"))
        )
        call_state = _usable_scalar_string(item.get("call_state"))
        if eligibility_known is None:
            conditional_requirements.append(route_id)
        else:
            evaluated_routes.append(
                {
                    "route_id": route_id,
                    "syllabus_overlap": overlap,
                    "effort_hours": effort,
                    "eligibility": eligibility_known,
                    "call_state": call_state or "unknown",
                    "ranking": 0,
                }
            )
        if call_state == "stale":
            stale_route_ids.add(route_id)

    trade_offs: list[dict] = []
    # Prefer best-fit by syllabus overlap (a preference) only after hard
    # constraints are met; eligibility_known != "eligible" is a hard blocker.
    eligible_routes = [
        route
        for route in evaluated_routes
        if route["eligibility"] == "eligible"
    ]
    best_eligible = None
    if eligible_routes:
        best_eligible = max(
            eligible_routes,
            key=lambda route: (
                route["syllabus_overlap"] if route["syllabus_overlap"] is not None else -1
            ),
        )
    for route in sorted(evaluated_routes, key=lambda r: r["route_id"]):
        eligible = route["eligibility"] == "eligible"
        trade_offs.append(
            {
                "route_id": route["route_id"],
                "eligible": eligible,
                "syllabus_overlap": route["syllabus_overlap"],
                "effort_hours": route["effort_hours"],
                "call_state": route["call_state"],
                "recommended": bool(
                    best_eligible is not None
                    and route["route_id"] == best_eligible["route_id"]
                ),
                "conditional": route["route_id"] in conditional_requirements,
            }
        )

    resolved = not malformed_route_member

    return {
        "resolved": resolved,
        "consideration_id": f"alternatives:{primary_id}",
        "proposal_only": True,
        "target_unchanged": True,
        "primary_id": primary_id,
        "primary_abandoned": False,
        "target_changed": False,
        "alternatives_considered": tuple(sorted(route_ids)),
        "conditional_requirements": tuple(sorted(conditional_requirements)),
        "stale_route_ids": tuple(sorted(stale_route_ids)),
        "trade_offs": tuple(trade_offs),
        "recommendation": (
            best_eligible["route_id"]
            if best_eligible is not None
            else None
        ),
        "hard_constraints_before_preferences": True,
    }


def create_strategy_proposal(
    *,
    current_version: Any,
    proposed_change: Any,
    reason: Any,
    evidence: Any,
    actor: Any,
    target_id: Any,
) -> dict:
    """Build a structurer strategy-change record preserving versioned strategy.

    A generated scenario is a **proposal until explicitly adopted**; it never
    silently changes the target or becomes the new strategy.  Adoption tracking
    (actor/time/reason) is supplied only when the higher-layer decision
    mechanism explicitly records it (``adopted=True``, ``adoption_time``).
    No Opposition-local persistence is introduced.
    """
    version = _usable_scalar_string(current_version)
    change_text = _usable_scalar_string(proposed_change)
    reason_text = _usable_scalar_string(reason)
    target = _usable_scalar_string(target_id)
    changed = bool(change_text is not None and version is not None)

    return {
        "strategy_proposal": True,
        "preserves_previous_version": version is not None,
        "previous_version": version,
        "proposed_change": change_text,
        "reason": reason_text,
        "evidence": evidence if evidence is not None else (),
        "actor": _usable_scalar_string(actor),
        "target_id": target,
        "adopted": False,
        "adoption_time": None,
        "decision_pending": changed,
        "uncertainty_preserved": True,
        "official_state_overridden": False,
        "strategy_state_overridden": False,
        "relation_to_goal": target,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Reasoning-rule scaffolding
# ═══════════════════════════════════════════════════════════════════════════════


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
        domain_id="domain:oppositions",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Conservative opposition rule for {rule_id}.",
        metadata={"phase": "10.23"},
    )


def _result(
    definition: ReasoningRuleDefinition,
    context: ReasoningRuleContext,
    status: ReasoningRuleResultStatus,
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    escalation: ReasoningEscalation | None = None,
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
        escalation=escalation,
        trace_entries=(
            ReasoningRuleTraceEntry(
                code=code,
                message=message,
                rule_id=definition.id,
                domain_id=definition.domain_id,
                status=status,
                occurred_at=context.timestamp,
                output_count=len(findings) + len(gaps) + int(escalation is not None),
            ),
        ),
        started_at=context.timestamp,
        completed_at=context.timestamp,
    )


@dataclass(frozen=True, slots=True)
class OfficialCallPriorityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claims_evidence = _normalize_collection(
            context.metadata, "opposition_claims", require_mapping_elements=True
        )
        if not claims_evidence.present:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No opposition claims supplied.",
            )
        claims = claims_evidence.items
        request_scope = context.metadata.get("scope")
        require_reference = _boolean_true(context.metadata.get("require_reference"))
        malformed_evidence = claims_evidence.malformed or _semantic_evidence_malformed(
            claims
        )
        relation_unknown_evidence = any(
            isinstance(claim, Mapping)
            and (
                not _usable_attribute_string(claim.get("attribute"))
                or _claim_scope_malformed(claim)
            )
            for claim in claims
        )
        findings: list[ReasoningFinding] = []
        gaps: list[ReasoningGap] = []
        by_attribute: dict[str, list[Mapping]] = {}
        for claim in claims:
            if isinstance(claim, Mapping):
                by_attribute.setdefault(_claim_attribute(claim), []).append(claim)

        for attribute in sorted(by_attribute):
            attribute_claims = by_attribute[attribute]
            scoped_sources = tuple(
                _claim_source(claim)
                for claim in attribute_claims
                if _claim_scope_matches(claim, request_scope)
            )
            authority = classify_opposition_source_authority(
                attribute=attribute,
                sources=scoped_sources,
                scope=request_scope,
                require_reference=require_reference,
            )
            decision_critical = any(
                _claim_critical(claim)
                for claim in attribute_claims
                if _claim_scope_matches(claim, request_scope)
            )
            references = tuple(
                ref
                for claim in attribute_claims
                if (ref := _usable_scalar_string(claim.get("id"))) is not None
            )
            verification_need = conditional_verification_trigger(
                fact_state=(
                    "conflicting"
                    if authority["conflict"]
                    else "unknown"
                ),
                decision_critical=decision_critical,
                attribute=attribute,
                scope=request_scope,
            ) if not authority["authority_resolved"] else conditional_verification_trigger(
                fact_state="confirmed_official",
                decision_critical=False,
                attribute=attribute,
                scope=request_scope,
            )
            findings.append(
                ReasoningFinding(
                    code="ATTRIBUTE_AUTHORITY",
                    message=(
                        f"Attribute {attribute} authority resolved by grounded "
                        "source class, provenance, temporal validity, specificity "
                        "and scope."
                        if authority["authority_resolved"]
                        else f"Authority for attribute {attribute} remains "
                        "unknown; no unsupported source is selected."
                    ),
                    severity=(
                        ReasoningSeverity.INFO
                        if authority["authority_resolved"]
                        else ReasoningSeverity.WARNING
                    ),
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=references,
                    metadata={
                        "attribute": attribute,
                        "authority_resolved": authority["authority_resolved"],
                        "authority_conflict": authority["conflict"],
                        "authoritative_source_id": authority["authoritative_source_id"],
                        "fact_value_known": authority["fact_value_known"],
                        "fact_resolved": authority["fact_resolved"],
                        "verification_need": verification_need,
                    },
                )
            )
        if malformed_evidence and not findings:
            findings.append(
                ReasoningFinding(
                    code="ATTRIBUTE_AUTHORITY",
                    message=(
                        "Authority evidence is malformed; no attribute authority "
                        "can be resolved from incomplete claims."
                    ),
                    severity=ReasoningSeverity.WARNING,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    metadata={
                        "authority_resolved": False,
                        "fact_value_known": False,
                        "fact_resolved": False,
                        "authority_unknown": True,
                        "verification_need": conditional_verification_trigger(
                            fact_state="unknown",
                            decision_critical=False,
                            attribute=None,
                        ),
                    },
                )
            )
        if malformed_evidence or relation_unknown_evidence:
            gaps.append(
                ReasoningGap(
                    code="SOURCE_AUTHORITY_EVIDENCE_MALFORMED",
                    message=(
                        "Malformed or incomplete source authority evidence "
                        "prevents a confident authority conclusion."
                    ),
                    severity=ReasoningSeverity.WARNING,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    metadata={"authority_unknown": True},
                )
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            gaps=tuple(gaps),
            code="ATTRIBUTE_SOURCE_AUTHORITY_PRESERVED",
            message="Grounded source authority resolved by attribute.",
        )


@dataclass(frozen=True, slots=True)
class OppositionTemporalValidityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        facts_evidence = _normalize_collection(
            context.metadata, "temporal_facts", require_mapping_elements=True
        )
        if not facts_evidence.present:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No temporal facts supplied.",
            )
        facts = facts_evidence.items
        findings: list[ReasoningFinding] = []
        for fact in facts:
            if not isinstance(fact, Mapping):
                findings.append(
                    ReasoningFinding(
                        code="TEMPORAL_MALFORMED",
                        message="A temporal fact payload is malformed.",
                        severity=ReasoningSeverity.WARNING,
                        rule_id=self.definition.id,
                        domain_id=self.definition.domain_id,
                        metadata={"state": "malformed", "calendar_not_created": True},
                    )
                )
                continue
            attribute = _usable_scalar_string(fact.get("attribute"))
            critical = _boolean_true(fact.get("decision_critical"))
            record = classify_opposition_temporal(
                fact=fact,
                decision_critical=critical,
            )
            findings.append(
                ReasoningFinding(
                    code="TEMPORAL_STATE",
                    message=f"Temporal state of {attribute or 'fact'} is {record['state']}.",
                    severity=(
                        ReasoningSeverity.INFO
                        if record["current"]
                        else ReasoningSeverity.WARNING
                    ),
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    metadata={
                        "attribute": attribute,
                        "state": record["state"],
                        "current": record["current"],
                        "verification_needed": record["verification_needed"],
                        "monitoring": record["monitoring"],
                        "calendar_not_created": True,
                    },
                )
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="TEMPORAL_STATE_CLASSIFIED",
            message="Changing opposition facts classified with temporal validity.",
        )


@dataclass(frozen=True, slots=True)
class SyllabusCoverageRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if "topics" not in context.metadata and "syllabus_version" not in context.metadata:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No syllabus coverage evidence supplied.",
            )
        record = evaluate_syllabus_coverage(
            topics=context.metadata.get("topics", ()),
            syllabus_version=context.metadata.get("syllabus_version"),
            syllabus_current=context.metadata.get("syllabus_current"),
            past_minutes=context.metadata.get("past_minutes"),
        )
        finding = ReasoningFinding(
            code="SYLLABUS_COVERAGE",
            message=(
                "Syllabus coverage is complete."
                if record["complete"]
                else "Syllabus coverage is not complete (pending/unknown topics "
                "or unresolved syllabus version)."
            ),
            severity=(
                ReasoningSeverity.INFO
                if record["complete"]
                else ReasoningSeverity.WARNING
            ),
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "complete": record["complete"],
                "studied_count": record["studied_count"],
                "pending_count": record["pending_count"],
                "unknown_count": record["unknown_count"],
                "forgetting_proven": False,
                "review_cue": record["review_cue"],
                "dimensions": record["dimensions"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="SYLLABUS_COVERAGE_EVALUATED",
            message="Multidimensional syllabus coverage preserved.",
        )


@dataclass(frozen=True, slots=True)
class StudyFeasibilityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if not any(
            key in context.metadata
            for key in (
                "remaining_hours",
                "available_hours",
                "health_constraint",
                "university_projection",
            )
        ):
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No study feasibility evidence supplied.",
            )
        record = evaluate_study_feasibility(
            remaining_hours=context.metadata.get("remaining_hours"),
            available_hours=context.metadata.get("available_hours"),
            target_days=context.metadata.get("target_days"),
            review_hours=context.metadata.get("review_hours"),
            mock_hours=context.metadata.get("mock_hours"),
            health_constraint=context.metadata.get("health_constraint"),
            university_projection=context.metadata.get("university_projection"),
            user_constraints=context.metadata.get("user_constraints", ()),
        )
        finding = ReasoningFinding(
            code="STUDY_FEASIBILITY",
            message=(
                "Study plan is feasible."
                if record["feasible"]
                else "Study plan is not feasible or unresolved."
            ),
            severity=(
                ReasoningSeverity.INFO
                if record["feasible"]
                else ReasoningSeverity.WARNING
            ),
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "feasibility": record["feasibility"],
                "unmet_hard_constraints": record["unmet_hard_constraints"],
                "capacity_hours": record["capacity_hours"],
                "capacity_source": record["capacity_source"],
                "proposal_only": True,
                "adopted_plan": False,
                "clinical_details_consumed": False,
                "university_state_merged": False,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="STUDY_FEASIBILITY_ASSESSED",
            message="Study feasibility respects hard constraints and minimal projections.",
        )


@dataclass(frozen=True, slots=True)
class MockExamInterpretationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if "mocks" not in context.metadata and "mock" not in context.metadata:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No mock-exam evidence supplied.",
            )
        mocks = context.metadata.get("mocks", ())
        if not mocks and "mock" in context.metadata:
            mocks = (context.metadata.get("mock"),)
        record = evaluate_mock_performance(mocks=mocks)
        finding = ReasoningFinding(
            code="MOCK_INTERPRETATION",
            message=(
                f"Mock evidence: {record['observation_count']} observation(s), "
                f"trend state {record['trend_state']}."
            ),
            severity=(
                ReasoningSeverity.INFO
                if not record["capacity_inferred"]
                else ReasoningSeverity.WARNING
            ),
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "observation_count": record["observation_count"],
                "trend_state": record["trend_state"],
                "trend_inferred": record["trend_inferred"],
                "one_mock_is_trend": False,
                "capacity_inferred": False,
                "pass_guaranteed": False,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="MOCK_INTERPRETATION_PRESERVED",
            message="Mock observations kept distinct from trends and capacity.",
        )


@dataclass(frozen=True, slots=True)
class AlternativeRouteRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if "primary" not in context.metadata and "alternatives" not in context.metadata:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No route-comparison evidence supplied.",
            )
        record = compare_alternative_routes(
            primary=context.metadata.get("primary"),
            alternatives=context.metadata.get("alternatives", ()),
            priority_weights=context.metadata.get("priority_weights"),
        )
        finding = ReasoningFinding(
            code="ALTERNATIVE_COMPARISON",
            message=(
                "Alternative routes compared; the primary target is unchanged."
                if record["resolved"]
                else "Alternative-route comparison is unresolved."
            ),
            severity=(
                ReasoningSeverity.INFO
                if record["resolved"]
                else ReasoningSeverity.WARNING
            ),
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "primary_abandoned": False,
                "target_changed": False,
                "target_unchanged": True,
                "proposal_only": True,
                "alternatives_considered": record["alternatives_considered"],
                "recommendation": record["recommendation"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="ALTERNATIVE_COMPARISON_PRESERVED",
            message="Alternative comparison never changes the active target.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_oppositions_rules() -> tuple[Any, ...]:
    """Build the six Opposition Domain rules deterministically in canonical order."""
    by_id = {
        "oppositions.alternative_route": AlternativeRouteRule(
            definition=_definition(
                "oppositions.alternative_route",
                "AlternativeRouteRule",
                ReasoningRuleCategory.SAFETY.value,
                770,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "oppositions.mock_exam_interpretation": MockExamInterpretationRule(
            definition=_definition(
                "oppositions.mock_exam_interpretation",
                "MockExamInterpretationRule",
                ReasoningRuleCategory.INFERENCE.value,
                760,
            )
        ),
        "oppositions.official_call_priority": OfficialCallPriorityRule(
            definition=_definition(
                "oppositions.official_call_priority",
                "OfficialCallPriorityRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                720,
            )
        ),
        "oppositions.study_feasibility": StudyFeasibilityRule(
            definition=_definition(
                "oppositions.study_feasibility",
                "StudyFeasibilityRule",
                ReasoningRuleCategory.INFERENCE.value,
                750,
            )
        ),
        "oppositions.syllabus_coverage": SyllabusCoverageRule(
            definition=_definition(
                "oppositions.syllabus_coverage",
                "SyllabusCoverageRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                740,
            )
        ),
        "oppositions.temporal_validity": OppositionTemporalValidityRule(
            definition=_definition(
                "oppositions.temporal_validity",
                "OppositionTemporalValidityRule",
                ReasoningRuleCategory.TEMPORALITY.value,
                730,
            )
        ),
    }
    return tuple(by_id[rule_id] for rule_id in OPPOSITIONS_RULE_IDS)


def _claim_attribute(claim: Mapping) -> str:
    attribute = claim.get("attribute")
    return str(attribute) if isinstance(attribute, str) else "unknown"


def _claim_value(claim: Mapping) -> Any:
    return claim.get("value")


def _claim_critical(claim: Mapping) -> bool:
    return _boolean_true(claim.get("critical"))


def _claim_scope_malformed(claim: Mapping) -> bool:
    return "scope" in claim and _scope_state(claim["scope"]) != SCOPE_VALID


def _claim_scope_matches(claim: Mapping, scope: str | None) -> bool:
    if _claim_scope_malformed(claim):
        return False
    claim_scope = claim.get("scope")
    if isinstance(claim_scope, str) and claim_scope.strip():
        return scope is None or claim_scope == scope
    return True


def _claim_source(claim: Mapping) -> Mapping:
    source = {
        "source_id": _usable_scalar_string(claim.get("id")),
        "source_class": claim.get("source_class"),
        "provenance": claim.get("provenance"),
        "temporal": claim.get("temporal"),
        "specificity": claim.get("specificity"),
        "supplied_attributes": (_claim_attribute(claim),),
        "value": _claim_value(claim),
    }
    for key in ("scope", "supersedes", "superseded_by", "source_reference", "source_ref"):
        if key in claim:
            source[key] = claim[key]
    return source


__all__ = [
    "OPPOSITIONS_RULE_IDS",
    "PROVENANCE_CALLER_CLAIMED",
    "PROVENANCE_GROUNDED",
    "PROVENANCE_NONE",
    "PROVENANCE_UNVERIFIED",
    "SOURCE_CLASS_ACADEMY_MATERIAL",
    "SOURCE_CLASS_EXTERNAL_OFFICIAL_SOURCE",
    "SOURCE_CLASS_INFERRED",
    "SOURCE_CLASS_MEMORY",
    "SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION",
    "SOURCE_CLASS_OFFICIAL_GAZETTE",
    "SOURCE_CLASS_OFFICIAL_PUBLICATION",
    "SOURCE_CLASS_PERSONAL_NOTE",
    "SOURCE_CLASS_PUBLIC_BODY_DOCUMENT",
    "SOURCE_CLASS_REGULATION",
    "SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL",
    "SOURCE_CLASS_STUDY_SESSION",
    "SOURCE_CLASS_UNKNOWN",
    "SOURCE_CLASS_USER_MESSAGE",
    "SOURCE_CLASS_USER_RECOLLECTION",
    "SPECIFICITY_GENERAL",
    "SPECIFICITY_SPECIFIC",
    "SPECIFICITY_UNKNOWN",
    "TEMPORAL_EXPIRED",
    "TEMPORAL_FUTURE",
    "TEMPORAL_TIMELESS",
    "TEMPORAL_UNKNOWN",
    "TEMPORAL_VALID",
    "AlternativeRouteRule",
    "MockExamInterpretationRule",
    "OfficialCallPriorityRule",
    "OppositionTemporalValidityRule",
    "StudyFeasibilityRule",
    "SyllabusCoverageRule",
    "build_oppositions_rules",
    "classify_opposition_source_authority",
    "classify_opposition_temporal",
    "compare_alternative_routes",
    "conditional_verification_trigger",
    "create_strategy_proposal",
    "evaluate_mock_performance",
    "evaluate_study_feasibility",
    "evaluate_syllabus_coverage",
    "opposition_call_monitoring",
]