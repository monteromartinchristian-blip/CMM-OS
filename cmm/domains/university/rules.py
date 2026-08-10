"""Phase 10.22 — University Domain Rules and deterministic helpers.

A declarative domain + pure deterministic academic helpers.  The helper
functions are state-free: no IO, no model calls, no registry mutation, no
internal clock.  They receive context explicitly and return deterministic
structures.

The ten reasoning rules are ``@dataclass(frozen=True, slots=True)``
definitions exposing ``definition`` and ``evaluate(context)``, exactly like the
General, Health, and Relationships Domain rules, so they compose with the
existing cognitive layer.

Epistemic-safety core (spec §6–§8): source authority is preserved **by
attribute**, not by a global naive ranking.  A material academic contradiction
that cannot be resolved is **fail-closed** (BLOCKED).  Observed academic
performance never establishes intellectual capacity.  Academic State is never
overridden by Personal Memory.  Academic Integrity Mode C is permissive by
default.  Decision support never adopts an academic decision.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
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
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult
from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RULE_IDS

UNIVERSITY_RULE_IDS: tuple[str, ...] = CANONICAL_UNIVERSITY_RULE_IDS

# ── Closed source-authority levels (spec §9) ──────────────────────────────────

SOURCE_AUTHORITY_ATTRIBUTE = "attribute"
SOURCE_AUTHORITY_OFFICIAL = "official"
SOURCE_AUTHORITY_REGULATION = "regulation"
SOURCE_AUTHORITY_USER_REPORTED = "user_reported"
SOURCE_AUTHORITY_INFERRED = "inferred"
SOURCE_AUTHORITY_UNKNOWN = "unknown"

# A canonical fixed ordering of source types for a *given attribute*.  Source
# authority is resolved per-attribute, not as a global ranking.
_SOURCE_TYPE_RANK = (
    SOURCE_AUTHORITY_OFFICIAL,
    SOURCE_AUTHORITY_REGULATION,
    SOURCE_AUTHORITY_USER_REPORTED,
    SOURCE_AUTHORITY_INFERRED,
    SOURCE_AUTHORITY_UNKNOWN,
)

# ── Closed integrity modes (spec §17) ─────────────────────────────────────────

INTEGRITY_MODE_A = "mode_a"
INTEGRITY_MODE_B = "mode_b"
INTEGRITY_MODE_C = "mode_c"

# ── Closed contradiction states (spec §10) ────────────────────────────────────

CONTRADICTION_RESOLVED = "resolved"
CONTRADICTION_UNRESOLVED = "unresolved"
CONTRADICTION_MATERIAL = "material"


# ═══════════════════════════════════════════════════════════════════════════════
# Pure deterministic university helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _usable_reference(value: Any) -> str | None:
    """Return a usable reference identifier from a raw value, or ``None``.

    A reference is usable only when it is a non-empty string.  Lists/tuples
    yield the first usable reference.  This deliberately never fabricates a
    placeholder (e.g. ``"unknown"``): an absent or blank reference is
    ``None``, never a fake evidence ID.
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


def _reference_from(
    mapping: Mapping,
    *keys: str,
) -> str | None:
    """Extract the first usable reference from ``mapping`` under any of ``keys``."""
    for key in keys:
        value = mapping.get(key)
        usable = _usable_reference(value)
        if usable is not None:
            return usable
    return None


def _normalize_references(values: Any) -> tuple[str, ...]:
    """Normalize a collection of reference IDs into a deterministic,
    order-preserving, de-duplicated tuple of usable references.

    Blank/placeholder IDs are dropped and never count as evidence.  This never
    fabricates a placeholder (e.g. ``"unknown"``) for a missing identifier.
    """
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, (list, tuple)):
        return ()
    seen: list[str] = []
    seen_set: set[str] = set()
    for value in values:
        usable = _usable_reference(value)
        if usable is not None and usable not in seen_set:
            seen_set.add(usable)
            seen.append(usable)
    return tuple(seen)


# ── Closed source classes (spec §6) ───────────────────────────────────────────
# A source class is grounded academic-provenance metadata, distinct from a
# caller's ``source_type`` claim.  Caller metadata cannot fabricate a class.

SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD = "official_academic_record"
SOURCE_CLASS_OFFICIAL_PUBLICATION = "official_publication"
SOURCE_CLASS_REGULATION = "regulation"
SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION = "official_act_resolution"
SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL = "specific_official_call"
SOURCE_CLASS_SUBJECT_GUIDE = "subject_guide"
SOURCE_CLASS_PROFESSOR_INSTRUCTION = "professor_instruction"
SOURCE_CLASS_INSTITUTIONAL_EMAIL = "institutional_email"
SOURCE_CLASS_ACADEMIC_CALENDAR = "academic_calendar"
SOURCE_CLASS_GENERAL_ACADEMIC_RECORD = "general_academic_record"
SOURCE_CLASS_PERSONAL_NOTE = "personal_note"
SOURCE_CLASS_USER_RECOLLECTION = "user_recollection"
SOURCE_CLASS_STUDY_SESSION = "study_session"
SOURCE_CLASS_INFERRED = "inferred"
SOURCE_CLASS_UNKNOWN = "unknown"

_SOURCE_CLASSES: tuple[str, ...] = (
    SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_SUBJECT_GUIDE,
    SOURCE_CLASS_PROFESSOR_INSTRUCTION,
    SOURCE_CLASS_INSTITUTIONAL_EMAIL,
    SOURCE_CLASS_ACADEMIC_CALENDAR,
    SOURCE_CLASS_GENERAL_ACADEMIC_RECORD,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_INFERRED,
    SOURCE_CLASS_UNKNOWN,
)

# ── Closed provenance states ───────────────────────────────────────────────────
# ``grounded`` is the only provenance that can carry authority.  Caller-claimed
# provenance is evidence of a claim, never authority itself.

PROVENANCE_GROUNDED = "grounded"
PROVENANCE_UNVERIFIED = "unverified"
PROVENANCE_CALLER_CLAIMED = "caller_claimed"
PROVENANCE_NONE = "none"

_GROUNDED_PROVENANCES: frozenset[str] = frozenset({PROVENANCE_GROUNDED})

# ── Closed specificity levels ─────────────────────────────────────────────────

SPECIFICITY_SPECIFIC = "specific"
SPECIFICITY_GENERAL = "general"
SPECIFICITY_UNKNOWN = "unknown"

_SPECIFICITY_RANK = {
    SPECIFICITY_SPECIFIC: 2,
    SPECIFICITY_GENERAL: 1,
    SPECIFICITY_UNKNOWN: 0,
}

# ── Closed temporal states (align with shared TemporalValidityStatus) ─────────

TEMPORAL_VALID = "valid"
TEMPORAL_EXPIRED = "expired"
TEMPORAL_FUTURE = "future"
TEMPORAL_UNKNOWN = "unknown"
TEMPORAL_TIMELESS = "timeless"

_CURRENT_TEMPORAL_STATES: frozenset[str] = frozenset(
    {TEMPORAL_VALID, TEMPORAL_TIMELESS}
)

# ── Per-attribute source-class priority (most authoritative first) ───────────
# Reflects spec §6 attribute-specific hierarchies.  A class not listed for an
# attribute is ``unknown`` for that attribute (rank 0).

_OFFICIAL_RECORD_PRIORITY = (
    SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_SUBJECT_GUIDE,
    SOURCE_CLASS_PROFESSOR_INSTRUCTION,
    SOURCE_CLASS_INSTITUTIONAL_EMAIL,
    SOURCE_CLASS_ACADEMIC_CALENDAR,
    SOURCE_CLASS_GENERAL_ACADEMIC_RECORD,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_INFERRED,
)

_REGULATION_PRIORITY = (
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_SUBJECT_GUIDE,
    SOURCE_CLASS_PROFESSOR_INSTRUCTION,
    SOURCE_CLASS_INSTITUTIONAL_EMAIL,
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_ACADEMIC_CALENDAR,
    SOURCE_CLASS_GENERAL_ACADEMIC_RECORD,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_INFERRED,
)

_EXAM_DATE_PRIORITY = (
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_ACADEMIC_CALENDAR,
    SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD,
    SOURCE_CLASS_SUBJECT_GUIDE,
    SOURCE_CLASS_PROFESSOR_INSTRUCTION,
    SOURCE_CLASS_INSTITUTIONAL_EMAIL,
    SOURCE_CLASS_GENERAL_ACADEMIC_RECORD,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_INFERRED,
)

_DEADLINE_PRIORITY = (
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD,
    SOURCE_CLASS_SUBJECT_GUIDE,
    SOURCE_CLASS_PROFESSOR_INSTRUCTION,
    SOURCE_CLASS_INSTITUTIONAL_EMAIL,
    SOURCE_CLASS_ACADEMIC_CALENDAR,
    SOURCE_CLASS_GENERAL_ACADEMIC_RECORD,
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_INFERRED,
)

_REQUIREMENT_PRIORITY = _REGULATION_PRIORITY

_STUDY_PROGRESS_PRIORITY = (
    SOURCE_CLASS_STUDY_SESSION,
    SOURCE_CLASS_USER_RECOLLECTION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_GENERAL_ACADEMIC_RECORD,
    SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_SUBJECT_GUIDE,
    SOURCE_CLASS_PROFESSOR_INSTRUCTION,
    SOURCE_CLASS_INSTITUTIONAL_EMAIL,
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SOURCE_CLASS_ACADEMIC_CALENDAR,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
    SOURCE_CLASS_INFERRED,
)

_ATTRIBUTE_PRIORITY: dict[str, tuple[str, ...]] = {
    "grade": _OFFICIAL_RECORD_PRIORITY,
    "credit": _OFFICIAL_RECORD_PRIORITY,
    "enrollment": _OFFICIAL_RECORD_PRIORITY,
    "passed": _OFFICIAL_RECORD_PRIORITY,
    "failed": _OFFICIAL_RECORD_PRIORITY,
    "recognized_credit": _OFFICIAL_RECORD_PRIORITY,
    "pending_credit": _OFFICIAL_RECORD_PRIORITY,
    "subject_status": _OFFICIAL_RECORD_PRIORITY,
    "requirement": _REQUIREMENT_PRIORITY,
    "regulation": _REQUIREMENT_PRIORITY,
    "exam_date": _EXAM_DATE_PRIORITY,
    "call_date": _EXAM_DATE_PRIORITY,
    "examination_date": _EXAM_DATE_PRIORITY,
    "deadline": _DEADLINE_PRIORITY,
    "assignment_deadline": _DEADLINE_PRIORITY,
    "study_progress": _STUDY_PROGRESS_PRIORITY,
    "study_hours": _STUDY_PROGRESS_PRIORITY,
    "study_activity": _STUDY_PROGRESS_PRIORITY,
}

_DEFAULT_PRIORITY = _OFFICIAL_RECORD_PRIORITY


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


def _source_scope(source: Mapping) -> str | None:
    scope = source.get("scope")
    return scope if isinstance(scope, str) and scope.strip() else None


def _source_rank(source: Mapping, attribute: str) -> int:
    """Return the source-class rank of ``source`` for ``attribute`` (0 = no
    authority for that attribute)."""
    priority = _ATTRIBUTE_PRIORITY.get(attribute, _DEFAULT_PRIORITY)
    source_class = _normalize_source_class(source.get("source_class"))
    try:
        return len(priority) - priority.index(source_class)
    except ValueError:
        return 0


def _value_missing(value: Any) -> bool:
    """Return whether an authoritative fact value is absent.

    Only ``None`` and blank strings are missing.  Numeric zero and ``False``
    remain valid factual values.
    """
    return value is None or (isinstance(value, str) and not value.strip())


def _values_compatible(left: Any, right: Any) -> bool:
    """Return whether two present claim values are exactly compatible."""
    return not _value_missing(left) and not _value_missing(right) and left == right


def _valid_supersession(candidate: Mapping, target: Mapping) -> bool:
    """Return whether a claimed replacement can affect current authority.

    A ``supersedes`` declaration is only a claimed relationship.  It takes
    effect when both source records are grounded, currently applicable,
    referenceable, scope-compatible, and the replacing source has at least the
    target's attribute-specific authority.  The declared relation supplies the
    version sequence; this helper does not infer one from observation order.
    """
    candidate_scope = candidate["scope"]
    target_scope = target["scope"]
    return bool(
        candidate["source_id"]
        and target["source_id"]
        and candidate["source_id"] != target["source_id"]
        and candidate["grounded"]
        and target["grounded"]
        and candidate["current"]
        and (
            target["current"]
            or target["temporal"] == TEMPORAL_UNKNOWN
        )
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


def classify_academic_source_authority(
    *,
    attribute: str,
    sources: tuple = (),
    scope: str | None = None,
) -> dict:
    """Classify the authoritative source for a *single* academic attribute using
    grounded, attribute-specific evidence.

    Authority is derived from: attribute, source class, provenance, temporal
    validity, specificity and scope (spec §6).  A caller cannot fabricate
    ``official``: a source is authoritative only when its provenance is
    ``grounded`` and its source class is grounded classification.  Recency alone
    never wins.  Supersession resolves the current value while preserving the
    superseded source as history.  Equal-authority incompatible claims with no
    valid supersession remain unresolved (never an arbitrary choice).
    """
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
        evaluated.append(
            {
                "source_id": _usable_reference(source.get("source_id")),
                "source_class": source_class,
                "provenance": provenance,
                "temporal": temporal,
                "specificity": specificity,
                "scope": scope_value,
                "grounded": grounded,
                "current": current,
                "rank": rank,
                "value": source.get("value"),
                "supersedes": _normalize_references(source.get("supersedes")),
                "superseded_by": _normalize_references(source.get("superseded_by")),
            }
        )

    # Only grounded, currently-valid sources can carry current authority.
    candidates = [
        evaluated
        for evaluated in evaluated
        if (
            evaluated["source_id"] is not None
            and evaluated["grounded"]
            and evaluated["current"]
            and evaluated["rank"] > 0
        )
    ]
    unresolved_temporal = [
        evaluated
        for evaluated in evaluated
        if (
            evaluated["source_id"] is not None
            and evaluated["grounded"]
            and evaluated["temporal"] == TEMPORAL_UNKNOWN
            and evaluated["rank"] > 0
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

    # Normalize both source representations into the same claimed replacement
    # relation, then validate it before any candidate is demoted to history.
    superseded_ids: set[str] = set()
    supersession_candidates = (*candidates, *unresolved_temporal)
    by_source_id = {
        candidate["source_id"]: candidate
        for candidate in supersession_candidates
        if candidate["source_id"] is not None
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

    # Rank by source class, then specificity.
    best_rank = max(e["rank"] for e in active)
    best = [e for e in active if e["rank"] == best_rank]
    best_specificity = max(_SPECIFICITY_RANK[e["specificity"]] for e in best)
    top = [
        e
        for e in best
        if _SPECIFICITY_RANK[e["specificity"]] == best_specificity
    ]

    # Unknown temporality is not known non-current.  A grounded unknown source
    # that could outrank the selected value (or tie it at the same specificity)
    # keeps the present fact unresolved unless validated supersession demoted it.
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
        top_values = [candidate["value"] for candidate in top]
        if all(_values_compatible(top_values[0], value) for value in top_values[1:]):
            supporting_source_ids = tuple(
                sorted(
                    source_id
                    for source_id in (
                        _usable_reference(candidate["source_id"])
                        for candidate in top
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
        # Equal-authority, equally-specific incompatible claims: unresolved.
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
            (_usable_reference(winner["source_id"]),)
            if _usable_reference(winner["source_id"]) is not None
            else ()
        ),
        "matched_sources": tuple(evaluated),
        "superseded_sources": tuple(sorted(superseded_ids)),
        "authority_unknown": False,
        "conflict": False,
        "reason": "resolved",
    }


def resolve_source_authority_by_attribute(
    *,
    attribute: str,
    sources: tuple = (),
) -> dict:
    """Compatibility adapter for the canonical grounded authority resolver.

    Older callers provide only ``source_type``.  That surface remains public,
    but canonical University rules never use it as authority evidence.  When
    legacy fields are present, this adapter translates them into the current
    structured shape and delegates all semantics to
    :func:`classify_academic_source_authority`.
    """
    normalized: list[dict] = []
    source_class_for_type = {
        SOURCE_AUTHORITY_OFFICIAL: SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD,
        SOURCE_AUTHORITY_REGULATION: SOURCE_CLASS_REGULATION,
        SOURCE_AUTHORITY_USER_REPORTED: SOURCE_CLASS_USER_RECOLLECTION,
        SOURCE_AUTHORITY_INFERRED: SOURCE_CLASS_INFERRED,
    }
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        item = dict(source)
        if "source_class" not in item and "source_type" in item:
            source_type = str(item.get("source_type"))
            item["source_class"] = source_class_for_type.get(
                source_type, SOURCE_CLASS_UNKNOWN
            )
            item.setdefault("provenance", PROVENANCE_GROUNDED)
            item.setdefault("temporal", TEMPORAL_VALID)
            item.setdefault("specificity", SPECIFICITY_GENERAL)
        normalized.append(item)
    result = classify_academic_source_authority(
        attribute=attribute,
        sources=tuple(normalized),
    )
    authority_class = result["authority_class"]
    authority = {
        SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD: SOURCE_AUTHORITY_OFFICIAL,
        SOURCE_CLASS_REGULATION: SOURCE_AUTHORITY_REGULATION,
        SOURCE_CLASS_USER_RECOLLECTION: SOURCE_AUTHORITY_USER_REPORTED,
        SOURCE_CLASS_INFERRED: SOURCE_AUTHORITY_INFERRED,
    }.get(authority_class)
    return {
        "attribute": attribute,
        "authority": authority,
        "authority_source_type": authority,
        "authoritative_source_id": result["authoritative_source_id"],
        "matched_sources": result["matched_sources"],
        "authority_resolved": result["authority_resolved"],
        "authority_unknown": result["authority_unknown"],
        "conflict": result["conflict"],
    }


def evaluate_academic_contradiction(
    *,
    statements: tuple = (),
) -> dict:
    """Compatibility adapter to the canonical claim conflict resolver.

    Structured claims delegate to resolve_academic_conflict. The flag-only
    shape remains solely for older callers and is never used by the canonical
    rule.
    """
    if not statements:
        return {
            "state": CONTRADICTION_UNRESOLVED,
            "material": False,
            "resolved": False,
        }
    structured = tuple(
        statement
        for statement in statements
        if isinstance(statement, Mapping)
        and "attribute" in statement
        and "value" in statement
    )
    if structured:
        record = resolve_academic_conflict(claims=structured)
        state = (
            CONTRADICTION_MATERIAL
            if record["material"] and record["unresolved"]
            else CONTRADICTION_UNRESOLVED
            if record["unresolved"]
            else CONTRADICTION_RESOLVED
        )
        return {
            "state": state,
            "material": record["material"],
            "resolved": record["resolved"],
        }
    material = any(
        isinstance(statement, Mapping) and statement.get("material")
        for statement in statements
    )
    unresolved = any(
        isinstance(statement, Mapping) and statement.get("unresolved")
        for statement in statements
    )
    return {
        "state": (
            CONTRADICTION_MATERIAL
            if material and unresolved
            else CONTRADICTION_UNRESOLVED
            if unresolved
            else CONTRADICTION_RESOLVED
        ),
        "material": bool(material),
        "resolved": not unresolved,
    }


def _claim_field(claim: Mapping, key: str) -> Any:
    return claim.get(key)


def _claim_scope(claim: Mapping) -> str | None:
    scope = _claim_field(claim, "scope")
    return scope if isinstance(scope, str) and scope.strip() else None


def _scope_matches(claim: Mapping, effective_scope: str | None) -> bool:
    """Return whether a claim applies to an effective resolution scope.

    Unscoped evidence retains the existing global applicability semantics and
    may participate in any scoped resolution.  Scoped claims only participate
    in their own scope; no new scope hierarchy is inferred.
    """
    claim_scope = _claim_scope(claim)
    return (
        effective_scope is None
        or claim_scope is None
        or claim_scope == effective_scope
    )


def _effective_scopes(
    claims: tuple[Mapping, ...],
    requested_scope: str | None = None,
) -> tuple[str | None, ...]:
    """Return deterministic resolution scopes without collapsing scoped facts."""
    if requested_scope is not None:
        return (requested_scope,)
    scoped = sorted(
        {
            scope
            for claim in claims
            if (scope := _claim_scope(claim)) is not None
        }
    )
    return tuple(scoped) if scoped else (None,)


def _claim_attribute(claim: Mapping) -> str:
    attribute = _claim_field(claim, "attribute")
    return str(attribute) if isinstance(attribute, str) else "unknown"


def _claim_value(claim: Mapping) -> Any:
    return _claim_field(claim, "value")


def _claim_critical(claim: Mapping) -> bool:
    return bool(_claim_field(claim, "critical"))


def _claim_source(claim: Mapping) -> Mapping:
    """Build a source descriptor for authority resolution from a claim."""
    return {
        "source_id": _usable_reference(claim.get("id")),
        "source_class": claim.get("source_class"),
        "provenance": claim.get("provenance"),
        "temporal": claim.get("temporal"),
        "specificity": claim.get("specificity"),
        "scope": _claim_scope(claim),
        "supplied_attributes": (_claim_attribute(claim),),
        "value": _claim_value(claim),
        "supersedes": claim.get("supersedes"),
        "superseded_by": claim.get("superseded_by"),
    }


def _incompatible(left: Any, right: Any) -> bool:
    """Return whether two values are present and exactly incompatible."""
    if left is None or right is None:
        return False
    if isinstance(left, str) and not left.strip():
        return False
    if isinstance(right, str) and not right.strip():
        return False
    return not _values_compatible(left, right)


def _claim_is_current(claim: Mapping) -> bool:
    return _normalize_temporal(claim.get("temporal")) in _CURRENT_TEMPORAL_STATES


def _claim_is_temporally_relevant(claim: Mapping) -> bool:
    return _normalize_temporal(claim.get("temporal")) not in {
        TEMPORAL_EXPIRED,
        TEMPORAL_FUTURE,
    }


def _claim_sort_key(claim: Mapping) -> tuple[str, ...]:
    return (
        _claim_attribute(claim),
        _claim_scope(claim) or "",
        _usable_reference(claim.get("id")) or "",
        repr(_claim_value(claim)),
        _normalize_source_class(claim.get("source_class")),
        _normalize_specificity(claim.get("specificity")),
    )


def resolve_academic_conflict(
    *,
    claims: tuple = (),
    scope: str | None = None,
) -> dict:
    """Derive the academic contradiction state from structured claims.

    Contradiction is DERIVED — never trusted from a caller boolean.  Two claims
    conflict when they share an attribute, hold incompatible values, overlap in
    relevant scope and are temporally contemporary.  Resolution is possible only
    when a valid authoritative supersession (or a strictly higher authority)
    justifies picking a current value; the superseded/historical claim is
    preserved.  A material unresolved conflict blocks only the dependent
    conclusion, not the whole domain.
    """
    if not claims:
        return {
            "contradiction": False,
            "resolved": True,
            "unresolved": False,
            "material": False,
            "blocked": False,
            "current_value": None,
            "superseded_claims": (),
            "conflicts": (),
        }

    grouped: dict[str, list[Mapping]] = {}
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        grouped.setdefault(_claim_attribute(claim), []).append(claim)

    conflicts: list[dict] = []
    superseded_ids: set[str] = set()
    current_by_scope: dict[tuple[str, str | None], Any] = {}
    material = False
    unresolved = False

    for attribute in sorted(grouped):
        attr_claims = sorted(grouped[attribute], key=_claim_sort_key)
        for effective_scope in _effective_scopes(attr_claims, scope):
            relevant_claims = [
                claim
                for claim in attr_claims
                if _scope_matches(claim, effective_scope)
            ]
            conflict_claims = [
                claim
                for claim in relevant_claims
                if _claim_is_temporally_relevant(claim)
            ]
            scope_conflicts: list[dict] = []

            # Collect all temporally relevant, overlapping incompatible evidence
            # first. No current value is selected during pair iteration.
            for i, left in enumerate(conflict_claims):
                for right in conflict_claims[i + 1 :]:
                    left_scope = _claim_scope(left)
                    right_scope = _claim_scope(right)
                    if (
                        left_scope is not None
                        and right_scope is not None
                        and left_scope != right_scope
                    ):
                        continue
                    if not _incompatible(_claim_value(left), _claim_value(right)):
                        continue
                    scope_conflicts.append(
                        {
                            "attribute": attribute,
                            "scope": effective_scope,
                            "left_id": left.get("id"),
                            "right_id": right.get("id"),
                            "left_value": _claim_value(left),
                            "right_value": _claim_value(right),
                        }
                    )
                    if _claim_critical(left) or _claim_critical(right):
                        material = True

            conflicts.extend(scope_conflicts)
            authority = classify_academic_source_authority(
                attribute=attribute,
                sources=tuple(_claim_source(claim) for claim in relevant_claims),
                scope=effective_scope,
            )
            superseded_ids.update(authority["superseded_sources"])
            if authority["authority_resolved"]:
                current_by_scope[(attribute, effective_scope)] = authority.get(
                    "authoritative_value"
                )
            elif scope_conflicts:
                unresolved = True

    resolved = not unresolved
    blocked = bool(conflicts) and unresolved and material
    conflicts.sort(
        key=lambda conflict: (
            str(conflict["attribute"]),
            str(conflict.get("scope") or ""),
            str(conflict["left_id"]),
            str(conflict["right_id"]),
            repr(conflict["left_value"]),
            repr(conflict["right_value"]),
        )
    )
    current_values_by_scope = tuple(
        {
            "attribute": attribute,
            "scope": effective_scope,
            "value": value,
        }
        for (attribute, effective_scope), value in sorted(
            current_by_scope.items(),
            key=lambda item: (item[0][0], item[0][1] or ""),
        )
    )

    return {
        "contradiction": bool(conflicts),
        "resolved": resolved,
        "unresolved": bool(conflicts) and unresolved,
        "material": material,
        "blocked": blocked,
        "current_value": (
            current_values_by_scope[0]["value"]
            if len(current_values_by_scope) == 1
            else None
        ),
        "current_values_by_scope": current_values_by_scope,
        "superseded_claims": tuple(sorted(superseded_ids)),
        "conflicts": tuple(conflicts),
    }


def _first_current(mapping: Mapping) -> Any:
    for value in mapping.values():
        return value
    return None


def _parse_ects_integer(value: Any, *, minimum: int = 0) -> int | None:
    """Return a valid ECTS integer without raising for runtime metadata."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= minimum else None


def _parse_non_negative_number(value: Any) -> int | float | None:
    """Return a finite non-negative numeric value without coercing metadata."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not isfinite(value) or value < 0:
        return None
    return value


def check_ects_consistency(
    *,
    completed: int = 0,
    recognized: int = 0,
    enrolled: int = 0,
    planned: int = 0,
    pending_recognition: int = 0,
    required: int | None = None,
    double_counted: tuple = (),
    contradictory: tuple = (),
    critical_requirement_uncertain: bool = False,
    records: tuple = (),
    degree_requirement: Mapping | None = None,
    derive_from_records: bool = False,
) -> dict:
    """Check ECTS credit consistency deterministically over distinct buckets.

    Credits are reasoned over as separate buckets: completed (earned),
    recognized (officially recognized toward the degree), enrolled (committed
    but not yet earned), planned (intended) and pending-recognition (submitted
    but not yet recognized).  Only earned and recognized credits count toward
    the requirement.  A credit present in more than one earned bucket is
    double-counted and flagged rather than summed twice; contradictory buckets
    are flagged, never silently reconciled into a confident total.  A
    completion conclusion is blocked while a critical requirement's status is
    uncertain.  The helper never reads the clock and never rewrites the
    official record; it only reports.
    """
    derived_double_counted: list[str] = []
    derived_contradictory: list[str] = []
    unknown_records: list[str] = []
    if records:
        bucket_totals = {
            "completed": 0,
            "recognized": 0,
            "enrolled": 0,
            "planned": 0,
            "pending_recognition": 0,
        }
        identities: dict[str, list[str]] = {}
        states_by_identity: dict[str, set[str]] = {}
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                unknown_records.append(f"record-{index}")
                continue
            identity = _usable_reference(
                record.get("subject_id")
                or record.get("credit_id")
                or record.get("id")
            )
            amount = record.get("ects", record.get("credit_amount", record.get("credits")))
            state = str(record.get("state", record.get("status", "unknown")))
            record_ref = identity or f"record-{index}"
            if identity is None:
                unknown_records.append(record_ref)
                continue
            source_reference = _reference_from(
                record,
                "source_reference",
                "source_ref",
            )
            if (
                not bool(record.get("grounded"))
                or source_reference is None
                or _normalize_temporal(record.get("temporal"))
                not in _CURRENT_TEMPORAL_STATES
            ):
                unknown_records.append(identity)
                continue
            numeric_amount = _parse_ects_integer(amount)
            if numeric_amount is None:
                unknown_records.append(identity)
                continue
            if state not in {*bucket_totals, "failed", "not_completed"}:
                unknown_records.append(identity)
                continue
            recognition_status = str(record.get("recognition_status", ""))
            if state == "completed" and recognition_status == "recognized":
                bucket = "recognized"
            else:
                bucket = state if state in bucket_totals else None
            states_by_identity.setdefault(identity, set()).add(state)
            if bucket is not None:
                bucket_totals[bucket] += numeric_amount
                identities.setdefault(identity, []).append(bucket)
            if state in {"failed", "not_completed"}:
                states_by_identity.setdefault(identity, set()).add("failed")

        for identity, buckets in identities.items():
            if len(buckets) > 1:
                derived_double_counted.append(identity)
        for identity, states in states_by_identity.items():
            earned = states & {"completed", "recognized"}
            if earned and "failed" in states:
                derived_contradictory.append(identity)
        completed = bucket_totals["completed"]
        recognized = bucket_totals["recognized"]
        enrolled = bucket_totals["enrolled"]
        planned = bucket_totals["planned"]
        pending_recognition = bucket_totals["pending_recognition"]

    requirement_grounded = required is not None
    requirement_temporal = TEMPORAL_UNKNOWN
    if degree_requirement is not None:
        candidate = degree_requirement.get("required_ects", degree_requirement.get("required"))
        required_value = _parse_ects_integer(candidate, minimum=1)
        requirement_grounded = bool(degree_requirement.get("grounded"))
        requirement_reference = _usable_reference(
            degree_requirement.get("source_reference")
            or degree_requirement.get("source_ref")
        )
        requirement_temporal = _normalize_temporal(
            degree_requirement.get("temporal")
        )
        requirement_grounded = bool(
            requirement_grounded
            and requirement_reference is not None
            and requirement_temporal in _CURRENT_TEMPORAL_STATES
            and required_value is not None
        )
        required = required_value if requirement_grounded else None
    elif derive_from_records:
        # Strict callers may still report legacy aggregates for diagnostics,
        # but an absent structured requirement cannot establish a requirement.
        required = None
    required_known = required is not None
    credit_state_sufficiently_grounded = (
        bool(records) and not unknown_records
        if derive_from_records
        else True
    )
    if derive_from_records and degree_requirement is None:
        requirement_grounded = False
    double_counted = tuple(dict.fromkeys((*double_counted, *derived_double_counted)))
    contradictory = tuple(dict.fromkeys((*contradictory, *derived_contradictory)))
    recognized_total = int(completed) + int(recognized)
    double_counting = len(double_counted) > 0
    contradiction = len(contradictory) > 0
    critical_requirement_uncertain = bool(
        critical_requirement_uncertain
        or not required_known
        or (
            derive_from_records
            and (
                not credit_state_sufficiently_grounded
                or not requirement_grounded
                or bool(unknown_records)
            )
        )
    )
    completion_blocked = (
        critical_requirement_uncertain or double_counting or contradiction
    )

    satisfied = bool(
        required_known
        and not completion_blocked
        and recognized_total >= int(required)
    )

    return {
        "recognized_total": recognized_total,
        "completed": int(completed),
        "recognized": int(recognized),
        "enrolled": int(enrolled),
        "planned": int(planned),
        "pending_recognition": int(pending_recognition),
        "required": int(required) if required_known else None,
        "required_known": required_known,
        "requirement_grounded": requirement_grounded,
        "requirement_temporal": requirement_temporal,
        "credit_state_sufficiently_grounded": credit_state_sufficiently_grounded,
        "double_counted": tuple(double_counted),
        "double_counting": double_counting,
        "contradictory": tuple(contradictory),
        "contradiction": contradiction,
        "critical_requirement_uncertain": critical_requirement_uncertain,
        "completion_blocked": completion_blocked,
        "completion_determinable": not completion_blocked,
        "satisfied": satisfied,
        "scenario_if_recognized": (
            recognized_total + int(pending_recognition)
            if required_known
            else None
        ),
        "unknown_records": tuple(sorted(set(unknown_records))),
        "flagged": double_counting or contradiction or critical_requirement_uncertain,
    }


def evaluate_exam_attempt(
    *,
    attempts: tuple = (),
    max_attempts: int | None = None,
    regulation_active: bool | None = None,
    regulation: Mapping | None = None,
    require_complete_evidence: bool = False,
) -> dict:
    """Evaluate exam attempts deterministically against the rules in force.

    An attempt only counts against the budget when it is grounded, has a
    consumed status, and is an ordinary (not reassessment) attempt.  A failed
    grade does not by itself consume an attempt; a caller-claimed attempt with
    no grounding is not authoritative; canceled or waived attempts do not
    count.  When the governing regulation is not in force, limits cannot be
    evaluated as authoritative.  The helper only *reports*; it never modifies
    the official record and never authorizes a retake.
    """
    consumed_attempts = 0
    reassessment_count = 0
    ungrounded_attempts = 0
    canceled = 0
    waived = 0
    failed_grade_not_consumed = False
    unknown_attempts = 0

    regulation_unknown = False
    regulation_stale = False
    regulation_current = False
    parsed_input_limit = _parse_ects_integer(max_attempts, minimum=1)
    limit_unknown = max_attempts is not None and parsed_input_limit is None
    max_attempts = parsed_input_limit
    if isinstance(regulation, Mapping):
        regulation_grounded = bool(regulation.get("grounded"))
        regulation_temporal = _normalize_temporal(regulation.get("temporal"))
        regulation_reference = _usable_reference(
            regulation.get("source_reference")
            or regulation.get("source_ref")
            or regulation.get("id")
        )
        regulation_class = _normalize_source_class(regulation.get("source_class"))
        regulation_current = bool(
            regulation_grounded
            and regulation_reference
            and regulation_class in {
                SOURCE_CLASS_REGULATION,
                SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
            }
            and regulation_temporal in _CURRENT_TEMPORAL_STATES
        )
        regulation_stale = regulation_temporal in {
            TEMPORAL_EXPIRED,
            TEMPORAL_FUTURE,
        }
        regulation_unknown = not regulation_current and not regulation_stale
        if regulation_current:
            max_attempts = _parse_ects_integer(
                regulation.get("max_attempts"),
                minimum=1,
            )
            limit_unknown = max_attempts is None
    elif require_complete_evidence:
        # The canonical rule never treats a caller boolean as the governing
        # regulation. Missing structured evidence remains unknown.
        regulation_unknown = True
    elif regulation_active is not None:
        # Compatibility calls may still explicitly model an inactive rule.
        regulation_current = bool(regulation_active)
        regulation_unknown = False
    else:
        # Compatibility helper calls from the pre-structured API retain their
        # historical active assumption; canonical production calls use the
        # strict path above.
        regulation_current = True
        regulation_unknown = False

    for entry in attempts:
        if not isinstance(entry, Mapping):
            unknown_attempts += 1
            continue
        complete_evidence = all(
            _usable_reference(entry.get(key)) is not None
            for key in ("id", "exam_id", "date", "source_reference")
        ) and entry.get("status") is not None
        if not entry.get("grounded") or (
            require_complete_evidence and not complete_evidence
        ):
            ungrounded_attempts += 1
            continue
        kind = entry.get("kind")
        status = entry.get("status")
        if kind not in {"ordinary", "reassessment"}:
            unknown_attempts += 1
            continue
        if status not in {"consumed", "canceled", "waived", "not_consumed"}:
            unknown_attempts += 1
            continue
        if kind == "reassessment":
            reassessment_count += 1
            continue
        if status == "canceled":
            canceled += 1
        elif status == "waived":
            waived += 1
        elif status == "consumed":
            consumed_attempts += 1
        elif entry.get("outcome") == "failed":
            failed_grade_not_consumed = True

    if regulation_unknown or not regulation_current:
        return {
            "consumed_attempts": consumed_attempts,
            "reassessment_count": reassessment_count,
            "ungrounded_attempts": ungrounded_attempts,
            "unknown_attempts": unknown_attempts,
            "attempt_evidence_unknown": bool(unknown_attempts),
            "canceled": canceled,
            "waived": waived,
            "failed_grade_not_consumed": failed_grade_not_consumed,
            "max_attempts": max_attempts,
            "limit_unknown": limit_unknown,
            "regulation_inactive": not regulation_unknown,
            "regulation_unknown": regulation_unknown,
            "regulation_stale": regulation_stale,
            "within_limits": False,
            "limit_exceeded": False,
        }

    within_limits = not (limit_unknown or unknown_attempts) and (
        max_attempts is None or consumed_attempts <= max_attempts
    )
    return {
        "consumed_attempts": consumed_attempts,
        "reassessment_count": reassessment_count,
        "ungrounded_attempts": ungrounded_attempts,
        "unknown_attempts": unknown_attempts,
        "attempt_evidence_unknown": bool(unknown_attempts),
        "canceled": canceled,
        "waived": waived,
        "failed_grade_not_consumed": failed_grade_not_consumed,
        "max_attempts": max_attempts,
        "limit_unknown": limit_unknown,
        "regulation_inactive": False,
        "regulation_unknown": False,
        "regulation_stale": False,
        "within_limits": within_limits,
        "limit_exceeded": not within_limits
        and not (limit_unknown or unknown_attempts),
    }


def _evaluate_workload_constraint(
    constraint: Mapping,
    *,
    scenario: Mapping | None,
    strict: bool,
) -> bool | None:
    if strict and constraint.get("grounded") is not True:
        return None
    field = constraint.get("field") or constraint.get("scenario_field")
    if scenario is not None and isinstance(field, str) and field in scenario:
        actual = scenario[field]
    elif "actual" in constraint:
        actual = constraint.get("actual")
    elif "actual_value" in constraint:
        actual = constraint.get("actual_value")
    elif not strict and "satisfied" in constraint:
        return bool(constraint.get("satisfied"))
    else:
        return None

    kind = str(constraint.get("kind", "")).lower()
    if actual is None:
        return None
    if kind in {"prerequisite", "deadline", "requirement"}:
        expected = constraint.get("requirement", True)
        return bool(actual) is bool(expected)
    if kind in {"availability", "minimum_hours", "credit_threshold"}:
        requirement = constraint.get("requirement", constraint.get("minimum"))
        actual_number = _parse_non_negative_number(actual)
        requirement_number = _parse_non_negative_number(requirement)
        if actual_number is None or requirement_number is None:
            return None
        return actual_number >= requirement_number
    if kind in {"workload_cap", "hours_cap", "credit_load", "maximum_hours"}:
        limit = constraint.get("limit", constraint.get("maximum"))
        actual_number = _parse_non_negative_number(actual)
        limit_number = _parse_non_negative_number(limit)
        if actual_number is None or limit_number is None:
            return None
        return actual_number <= limit_number
    if "limit" in constraint:
        actual_number = _parse_non_negative_number(actual)
        limit_number = _parse_non_negative_number(constraint["limit"])
        if actual_number is None or limit_number is None:
            return None
        return actual_number <= limit_number
    if "requirement" in constraint:
        return actual == constraint["requirement"]
    if isinstance(actual, bool):
        return actual
    return None


def _evaluate_structured_workload(
    *,
    total_ect: int,
    health_constraint: Mapping | None,
    hard_constraints: tuple,
    preferences: tuple,
    selected_scenario: str | None,
    scenarios: tuple,
) -> dict:
    scenario_records = tuple(item for item in scenarios if isinstance(item, Mapping))
    consumed_factors: set[str] = set()
    feasible_ids: list[str] = []
    infeasible_ids: list[str] = []
    unresolved_ids: list[str] = []
    hard_constraint_ids: set[str] = set()

    global_constraints = tuple(
        item for item in hard_constraints if isinstance(item, Mapping)
    )
    for scenario in scenario_records:
        scenario_id = _usable_reference(scenario.get("id"))
        if scenario_id is None:
            continue
        constraints = (*global_constraints, *tuple(
            item for item in scenario.get("hard_constraints", ())
            if isinstance(item, Mapping)
        ))
        if (
            isinstance(health_constraint, Mapping)
            and health_constraint.get("authorized")
            and health_constraint.get("functional_cap_ect") is not None
        ):
            constraints = (
                *constraints,
                {
                    "id": "health_functional_cap",
                    "kind": "workload_cap",
                    "field": "credit_load",
                    "limit": health_constraint.get("functional_cap_ect"),
                    "grounded": True,
                },
            )
            consumed_factors.add("health_functional_cap")
        states: list[bool | None] = []
        for constraint in constraints:
            cid = _usable_reference(constraint.get("id"))
            if cid is not None:
                hard_constraint_ids.add(cid)
            states.append(
                _evaluate_workload_constraint(
                    constraint,
                    scenario=scenario,
                    strict=True,
                )
            )
        if any(state is False for state in states):
            infeasible_ids.append(scenario_id)
        elif any(state is None for state in states):
            unresolved_ids.append(scenario_id)
        else:
            feasible_ids.append(scenario_id)

    explicit_preferences = tuple(
        pref
        for pref in preferences
        if isinstance(pref, Mapping) and pref.get("dimension")
    )
    ranking: tuple[str, ...] = ()
    ranking_incomplete = False
    if explicit_preferences and feasible_ids:
        ranked = [
            scenario
            for scenario in scenario_records
            if _usable_reference(scenario.get("id")) in feasible_ids
        ]
        for preference in reversed(explicit_preferences):
            dimension = str(preference["dimension"])
            direction = str(preference.get("direction", "maximize")).lower()
            reverse = direction in {"maximize", "desc", "descending"}
            values = tuple(
                _parse_non_negative_number(
                    scenario.get(
                        dimension,
                        scenario.get("preference_values", {}).get(dimension)
                        if isinstance(scenario.get("preference_values"), Mapping)
                        else None,
                    )
                )
                for scenario in ranked
            )
            if any(value is None for value in values):
                ranking_incomplete = True
                break
            ranked.sort(
                key=lambda scenario: scenario.get(
                    dimension,
                    scenario.get("preference_values", {}).get(dimension)
                    if isinstance(scenario.get("preference_values"), Mapping)
                    else None,
                ),
                reverse=reverse,
            )
        if not ranking_incomplete:
            ranking = tuple(
                _usable_reference(scenario.get("id"))
                for scenario in ranked
                if _usable_reference(scenario.get("id")) is not None
            )

    all_feasible = bool(feasible_ids) and not unresolved_ids
    if unresolved_ids or not all_feasible:
        stage = "feasibility"
    elif explicit_preferences:
        stage = "preferences"
    else:
        stage = "preferences"
    proposal = selected_scenario if selected_scenario in feasible_ids else None
    return {
        "feasible": all_feasible,
        "stage": stage,
        "preferences_applied": bool(explicit_preferences),
        "tradeoffs": (),
        "scenarios": tuple(
            _usable_reference(scenario.get("id"))
            for scenario in scenario_records
            if _usable_reference(scenario.get("id")) is not None
        ),
        "feasible_scenarios": tuple(feasible_ids),
        "infeasible_scenarios": tuple(infeasible_ids),
        "unresolved_scenarios": tuple(unresolved_ids),
        "feasibility_uncertain": bool(unresolved_ids),
        "ranking": ranking,
        "ranking_incomplete": ranking_incomplete,
        "numeric_metadata_unknown": False,
        "proposal": proposal,
        "adopted_decision": False,
        "consumed_factors": tuple(sorted(consumed_factors)),
        "clinical_details_consumed": False,
        "hard_constraint_ids": tuple(sorted(hard_constraint_ids)),
    }


def evaluate_academic_workload(
    *,
    total_ect: int = 0,
    full_time_ect: int = 30,
    health_constraint: Mapping | None = None,
    hard_constraints: tuple = (),
    preferences: tuple = (),
    selected_scenario: str | None = None,
    scenarios: tuple = (),
    derive_from_facts: bool = False,
) -> dict:
    """Evaluate academic workload through the staged planning pipeline.

    Pipeline: HARD CONSTRAINTS -> FEASIBILITY -> PREFERENCES -> TRADE-OFFS ->
    SCENARIOS -> PROPOSAL.  An unsatisfied hard constraint stops the pipeline
    before preferences are applied.  An authorized Health functional constraint
    (e.g. a reduced-load cap) participates as a hard constraint affecting
    feasibility; clinical details are never consumed by the domain.  A proposal
    is only emitted at the final stage and never adopts a decision.
    """
    if derive_from_facts or scenarios:
        return _evaluate_structured_workload(
            total_ect=total_ect,
            health_constraint=health_constraint,
            hard_constraints=hard_constraints,
            preferences=preferences,
            selected_scenario=selected_scenario,
            scenarios=tuple(scenarios),
        )

    consumed_factors = set()
    hard_constraint_ids = set()
    for hard in hard_constraints:
        if not isinstance(hard, Mapping):
            continue
        cid = _usable_reference(hard.get("id"))
        if cid is None:
            continue
        hard_constraint_ids.add(cid)

    # Authorized Health functional constraint is a hard constraint on
    # feasibility; only the functional cap is read, never clinical details.
    if isinstance(health_constraint, Mapping) and health_constraint.get("authorized"):
        functional_cap = health_constraint.get("functional_cap_ect")
        if functional_cap is not None:
            consumed_factors.add("health_functional_cap")
            if int(functional_cap) < int(total_ect):
                hard_constraint_ids.add("health_functional_cap_unsatisfied")

    satisfied = all(
        hc.get("satisfied") for hc in hard_constraints if isinstance(hc, Mapping)
    )
    feasible = satisfied and not any(
        cid.endswith("_unsatisfied") for cid in hard_constraint_ids
    )
    if not feasible:
        return {
            "feasible": False,
            "stage": "feasibility",
            "preferences_applied": False,
            "tradeoffs": (),
            "scenarios": (),
            "proposal": None,
            "adopted_decision": False,
            "consumed_factors": tuple(sorted(consumed_factors)),
            "clinical_details_consumed": False,
            "hard_constraint_ids": tuple(sorted(hard_constraint_ids)),
        }

    pref_list = tuple(p for p in preferences if isinstance(p, Mapping))
    preferences_applied = bool(pref_list)
    if not preferences_applied:
        return {
            "feasible": True,
            "stage": "preferences",
            "preferences_applied": False,
            "tradeoffs": (),
            "scenarios": (),
            "proposal": selected_scenario,
            "adopted_decision": False,
            "consumed_factors": tuple(sorted(consumed_factors)),
            "clinical_details_consumed": False,
            "hard_constraint_ids": tuple(sorted(hard_constraint_ids)),
        }

    # Trade-offs are surfaced when two preferences share the same rank and
    # cannot both be satisfied without conflict.
    ranks = sorted({int(p.get("rank", 0)) for p in pref_list})
    conflicted_ranks = {
        rank for rank in ranks if sum(int(p.get("rank", 0)) == rank for p in pref_list) > 1
    }
    tradeoffs = tuple(f"pref-rank-{rank}" for rank in sorted(conflicted_ranks))
    if tradeoffs:
        return {
            "feasible": True,
            "stage": "tradeoffs",
            "preferences_applied": True,
            "tradeoffs": tradeoffs,
            "scenarios": (),
            "proposal": None,
            "adopted_decision": False,
            "consumed_factors": tuple(sorted(consumed_factors)),
            "clinical_details_consumed": False,
            "hard_constraint_ids": tuple(sorted(hard_constraint_ids)),
        }

    scenarios = tuple(f"scenario-{pref.get('id')}" for pref in pref_list)
    if len(pref_list) < 2 and selected_scenario is None:
        return {
            "feasible": True,
            "stage": "preferences",
            "preferences_applied": True,
            "tradeoffs": (),
            "scenarios": (),
            "proposal": None,
            "adopted_decision": False,
            "consumed_factors": tuple(sorted(consumed_factors)),
            "clinical_details_consumed": False,
            "hard_constraint_ids": tuple(sorted(hard_constraint_ids)),
        }
    if selected_scenario is None:
        return {
            "feasible": True,
            "stage": "scenarios",
            "preferences_applied": True,
            "tradeoffs": (),
            "scenarios": scenarios,
            "proposal": None,
            "adopted_decision": False,
            "consumed_factors": tuple(sorted(consumed_factors)),
            "clinical_details_consumed": False,
            "hard_constraint_ids": tuple(sorted(hard_constraint_ids)),
        }

    return {
        "feasible": True,
        "stage": "proposal",
        "preferences_applied": True,
        "tradeoffs": (),
        "scenarios": scenarios,
        "proposal": selected_scenario,
        "adopted_decision": False,
        "consumed_factors": tuple(sorted(consumed_factors)),
        "clinical_details_consumed": False,
        "hard_constraint_ids": tuple(sorted(hard_constraint_ids)),
    }


def _resolve_dependency_credit_evidence(records: tuple) -> dict:
    """Resolve academic records into deterministic earned-credit evidence,
    grouping by canonical credit identity (spec §§13–18).

    A canonical identity is counted at most once with a single deterministic
    amount.  Compatible duplicate evidence counts the identity once — never
    twice.  A contradictory identity (earned + failed) or an amount conflict on
    the same identity keeps the evidence unknown rather than fabricating a
    satisfied threshold.  Identityless records cannot establish earned credits.
    """
    by_identity: dict[str, list[Mapping]] = {}
    identityless = False
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            identityless = True
            continue
        identity = _usable_reference(
            record.get("subject_id") or record.get("credit_id") or record.get("id")
        )
        if identity is None:
            identityless = True
            continue
        by_identity.setdefault(identity, []).append(record)

    completed_credits = 0
    pending_credits = 0
    credit_evidence_unknown = False
    unknown_identities: set[str] = set()
    contradictory_identities: set[str] = set()
    amount_conflict_identities: set[str] = set()

    for identity, group in sorted(by_identity.items()):
        validated: list[dict] = []
        has_unknown = False
        for record in group:
            grounded = bool(record.get("grounded")) and bool(
                _usable_reference(
                    record.get("source_reference") or record.get("source_ref")
                )
            )
            current = (
                _normalize_temporal(record.get("temporal"))
                in _CURRENT_TEMPORAL_STATES
            )
            amount_i = _parse_ects_integer(
                record.get("ects", record.get("credit_amount", 0))
            )
            state = str(record.get("status", record.get("state", "unknown")))
            if not grounded or not current or amount_i is None:
                has_unknown = True
                continue
            validated.append({"state": state, "amount": amount_i})
        if has_unknown:
            credit_evidence_unknown = True
            unknown_identities.add(identity)
            continue
        if not validated:
            continue
        states = {entry["state"] for entry in validated}
        earned = states & {"completed", "passed", "recognized"}
        failed = states & {"failed", "not_completed"}
        if earned and failed:
            credit_evidence_unknown = True
            contradictory_identities.add(identity)
            continue
        earned_amounts = [
            entry["amount"]
            for entry in validated
            if entry["state"] in {"completed", "passed", "recognized"}
        ]
        if earned_amounts:
            if len(set(earned_amounts)) != 1:
                credit_evidence_unknown = True
                amount_conflict_identities.add(identity)
                continue
            completed_credits += earned_amounts[0]
            continue
        pending_amounts = [
            entry["amount"]
            for entry in validated
            if entry["state"] == "pending_recognition"
        ]
        if pending_amounts:
            if len(set(pending_amounts)) != 1:
                credit_evidence_unknown = True
                amount_conflict_identities.add(identity)
                continue
            pending_credits += pending_amounts[0]
            continue
        if states <= {"failed", "not_completed"}:
            continue
        credit_evidence_unknown = True
        unknown_identities.add(identity)

    return {
        "completed_credits": completed_credits,
        "pending_credits": pending_credits,
        "credit_evidence_unknown": credit_evidence_unknown or identityless,
        "unknown_credit_identities": tuple(sorted(unknown_identities)),
        "contradictory_credit_identities": tuple(sorted(contradictory_identities)),
        "amount_conflict_credit_identities": tuple(sorted(amount_conflict_identities)),
    }


def evaluate_academic_dependency(
    *,
    subject_id: str,
    dependencies: tuple = (),
    academic_records: tuple = (),
    derive_from_academic_state: bool = False,
) -> dict:
    """Evaluate academic dependency relationships deterministically.

    A subject may list prerequisite subjects (including credit/TFG sequencing).
    A prerequisite is satisfied only by *grounded* evidence of passing; a
    caller-claimed ``passed`` boolean with no grounding is not authoritative and
    is ignored.  An unknown prerequisite status remains unresolved and is never
    treated as satisfied.  The helper only *reports*; it never changes the
    official record and never auto-enrols.
    """
    if derive_from_academic_state:
        records_by_subject: dict[str, list[Mapping]] = {}
        for record in academic_records:
            if not isinstance(record, Mapping):
                continue
            record_id = _usable_reference(
                record.get("subject_id")
                or record.get("credit_id")
                or record.get("id")
            )
            if record_id is not None:
                records_by_subject.setdefault(record_id, []).append(record)
        credit_evidence = _resolve_dependency_credit_evidence(
            tuple(academic_records)
        )
        completed_credits = credit_evidence["completed_credits"]
        pending_credits = credit_evidence["pending_credits"]
        credit_evidence_unknown = credit_evidence["credit_evidence_unknown"]

        satisfied: list[str] = []
        open_prereqs: list[str] = []
        unknown_prereqs: list[str] = []
        conditional_prereqs: list[str] = []
        caller_passed_ignored: list[str] = []
        anonymous_prerequisite_count = 0
        credit_thresholds: dict[str, dict] = {}
        for dep in dependencies:
            if not isinstance(dep, Mapping):
                anonymous_prerequisite_count += 1
                continue
            dep_id = _usable_reference(dep.get("id"))
            if dep_id is None:
                anonymous_prerequisite_count += 1
                continue
            if dep.get("caller_passed") or dep.get("passed") or dep.get("grounded_passed"):
                caller_passed_ignored.append(dep_id)
            kind = str(dep.get("kind", "subject")).lower()
            if kind in {"credit_threshold", "tfg_eligibility", "credit", "tfg"}:
                required = dep.get("required_credits", dep.get("threshold"))
                required_i = _parse_ects_integer(required, minimum=1)
                if required_i is None:
                    unknown_prereqs.append(dep_id)
                    continue
                current_satisfied = completed_credits >= required_i
                conditional_satisfied = (
                    completed_credits + pending_credits >= required_i
                )
                status = (
                    "satisfied"
                    if current_satisfied
                    else "unknown"
                    if credit_evidence_unknown
                    else "conditional"
                    if conditional_satisfied
                    else "open"
                )
                credit_thresholds[dep_id] = {
                    "required": required_i,
                    "completed": completed_credits,
                    "pending_recognition": pending_credits,
                    "status": status,
                    "scenario_if_recognized": conditional_satisfied,
                }
                if current_satisfied:
                    satisfied.append(dep_id)
                elif conditional_satisfied:
                    conditional_prereqs.append(dep_id)
                else:
                    open_prereqs.append(dep_id)
                continue

            evidence = dep.get("academic_state")
            evidence_records = (
                (evidence,) if isinstance(evidence, Mapping) else records_by_subject.get(dep_id, ())
            )
            passed = False
            failed = False
            for evidence_record in evidence_records:
                if not isinstance(evidence_record, Mapping):
                    continue
                grounded = bool(evidence_record.get("grounded")) and bool(
                    _usable_reference(
                        evidence_record.get("source_reference")
                        or evidence_record.get("source_ref")
                    )
                )
                current = _normalize_temporal(evidence_record.get("temporal")) in _CURRENT_TEMPORAL_STATES
                status = str(evidence_record.get("status", evidence_record.get("state", "unknown")))
                if grounded and current and status in {"passed", "completed"}:
                    passed = True
                if grounded and current and status in {"failed", "not_completed"}:
                    failed = True
            if passed and not failed:
                satisfied.append(dep_id)
            elif failed:
                open_prereqs.append(dep_id)
            else:
                unknown_prereqs.append(dep_id)

        blocked_ids = tuple(dict.fromkeys((*open_prereqs, *unknown_prereqs, *conditional_prereqs)))
        return {
            "subject_id": subject_id,
            "satisfied_prerequisites": tuple(satisfied),
            "open_prerequisites": tuple(open_prereqs),
            "unknown_prerequisites": tuple(unknown_prereqs),
            "conditional_prerequisites": tuple(conditional_prereqs),
            "caller_passed_ignored": tuple(caller_passed_ignored),
            "anonymous_prerequisite_count": anonymous_prerequisite_count,
            "credit_thresholds": credit_thresholds,
            "credit_evidence_unknown": credit_evidence_unknown,
            "unknown_credit_identities": credit_evidence[
                "unknown_credit_identities"
            ],
            "contradictory_credit_identities": credit_evidence[
                "contradictory_credit_identities"
            ],
            "amount_conflict_credit_identities": credit_evidence[
                "amount_conflict_credit_identities"
            ],
            "dependency_blocked": bool(
                blocked_ids or anonymous_prerequisite_count
            ),
        }

    satisfied: list[str] = []
    open_prereqs: list[str] = []
    unknown_prereqs: list[str] = []
    caller_passed_ignored: list[str] = []
    anonymous_prerequisite_count = 0

    for dep in dependencies:
        if not isinstance(dep, Mapping):
            anonymous_prerequisite_count += 1
            continue
        dep_id = _usable_reference(dep.get("id"))
        if dep_id is None:
            anonymous_prerequisite_count += 1
            continue
        if dep.get("grounded_passed"):
            satisfied.append(dep_id)
            continue
        if dep.get("caller_passed") and not dep.get("grounded_passed"):
            caller_passed_ignored.append(dep_id)
        status = dep.get("status")
        if status in ("passed", "failed", "pending"):
            open_prereqs.append(dep_id)
        else:
            unknown_prereqs.append(dep_id)

    return {
        "subject_id": subject_id,
        "satisfied_prerequisites": tuple(satisfied),
        "open_prerequisites": tuple(open_prereqs),
        "unknown_prerequisites": tuple(unknown_prereqs),
        "caller_passed_ignored": tuple(caller_passed_ignored),
        "anonymous_prerequisite_count": anonymous_prerequisite_count,
        "dependency_blocked": bool(
            open_prereqs or unknown_prereqs or anonymous_prerequisite_count
        ),
    }


def evaluate_academic_integrity(
    *,
    mode: str = INTEGRITY_MODE_C,
    caller_restriction: Mapping | None = None,
    grounded_restriction: Mapping | None = None,
    remembered_restriction: bool = False,
    current_course: str | None = None,
    current_assessment: str | None = None,
    requested_action: str | None = None,
) -> dict:
    """Resolve Academic Integrity Mode C assistance posture (spec §16).

    Mode C is permissive by default: assistance is allowed when no applicable
    restriction is grounded.  A caller cannot create a prohibition merely by
    setting a boolean without grounding.  A remembered prohibition is not
    automatically equivalent to a current official one.  When an explicit,
    sufficiently grounded restriction exists, the concrete scope is respected
    and its source/temporal validity are preserved.
    """
    if mode not in (INTEGRITY_MODE_A, INTEGRITY_MODE_B, INTEGRITY_MODE_C):
        return {
            "mode": mode,
            "mode_valid": False,
            "assistance_permitted": False,
            "restriction": None,
            "restriction_grounded": False,
            "reason": f"Unknown integrity mode {mode!r}; not permissive.",
        }

    # Only Mode C is permissive by default; A and B are subject to their own
    # (stricter) policies and are not treated as permissive here.
    if mode != INTEGRITY_MODE_C:
        return {
            "mode": mode,
            "mode_valid": True,
            "assistance_permitted": False,
            "restriction": None,
            "restriction_grounded": False,
            "reason": f"Integrity mode {mode} is not permissive by default.",
        }

    # A caller-provided restriction with no grounding cannot fabricate a
    # prohibition.
    caller_forbidden = False
    if isinstance(caller_restriction, Mapping) and caller_restriction.get(
        "ai_forbidden"
    ):
        caller_forbidden = True

    # A grounded, current, official restriction is respected within its scope.
    restriction_grounded = False
    restriction_applies = False
    restriction_scope: tuple[str, ...] = ()
    scope_applicability: str | None = None
    if isinstance(grounded_restriction, Mapping):
        status = grounded_restriction.get("status")
        grounded = bool(grounded_restriction.get("grounded"))
        source_class = str(grounded_restriction.get("source_class", ""))
        temporal = str(grounded_restriction.get("temporal", ""))
        source_reference = _reference_from(
            grounded_restriction,
            "source_reference",
            "source_ref",
        )
        if (
            status == "prohibited"
            and grounded
            and source_reference is not None
            and source_class == "official_regulation"
            and temporal == "current"
            and not grounded_restriction.get("superseded")
            and not grounded_restriction.get("superseded_by")
        ):
            restriction_grounded = True
            restriction_scope = _normalize_references(
                grounded_restriction.get("scope")
            )
            course_scope = _usable_reference(grounded_restriction.get("course"))
            assessment_scope = _usable_reference(
                grounded_restriction.get("assessment")
            )
            # Exact-scope fail-closed invariant: a scoped restriction applies
            # only when its required scope is actually established.  An unknown
            # current scope is NOT a matching scope.  Only a genuinely global
            # restriction (no course/assessment scope) applies without a
            # current scope.
            scope_matches = True
            if course_scope is not None:
                scope_matches = (
                    current_course is not None and course_scope == current_course
                )
            if assessment_scope is not None and scope_matches:
                scope_matches = (
                    current_assessment is not None
                    and assessment_scope == current_assessment
                )
            ambiguous = bool(grounded_restriction.get("ambiguous"))
            prohibited_actions = _normalize_references(
                grounded_restriction.get("prohibited_actions")
            )
            allowed_actions = _normalize_references(
                grounded_restriction.get("allowed_actions")
            )
            if requested_action is None:
                restriction_applies = scope_matches and not ambiguous
            else:
                restriction_applies = (
                    scope_matches
                    and not ambiguous
                    and requested_action in prohibited_actions
                    and requested_action not in allowed_actions
                )
            # Diagnostic: distinguish an unresolved scope (unknown current
            # scope) from a matched scope and a mismatched scope.  An unresolved
            # scope is never authority to apply a restriction.
            scope_applicability = "matched"
            if course_scope is not None:
                if current_course is None:
                    scope_applicability = "unresolved"
                elif course_scope != current_course:
                    scope_applicability = "mismatched"
            if assessment_scope is not None and scope_applicability == "matched":
                if current_assessment is None:
                    scope_applicability = "unresolved"
                elif assessment_scope != current_assessment:
                    scope_applicability = "mismatched"

    remembered_not_official = bool(
        remembered_restriction
        or (
            isinstance(grounded_restriction, Mapping)
            and not restriction_grounded
            and grounded_restriction.get("source_class") != "official_regulation"
        )
    )

    assistance_permitted = not restriction_applies

    return {
        "mode": mode,
        "mode_valid": True,
        "assistance_permitted": assistance_permitted,
        "restriction": "prohibited" if restriction_grounded else None,
        "restriction_grounded": restriction_grounded,
        "restriction_applies": restriction_applies,
        "restriction_scope": restriction_scope,
        "current_course": current_course,
        "current_assessment": current_assessment,
        "requested_action": requested_action,
        "caller_forbidden_ignored": caller_forbidden and assistance_permitted,
        "remembered_not_official": remembered_not_official,
        "scope_applicability": scope_applicability,
        "reason": (
            "Assistance permitted by default under Mode C; no applicable "
            "grounded restriction."
            if assistance_permitted
            else "Assistance restricted by a grounded official restriction."
        ),
    }


def conditional_verification_trigger(
    *,
    fact_state: str,
    decision_critical: bool = False,
    attribute: str | None = None,
    scope: str | None = None,
) -> dict:
    """Decide whether conditional official verification is warranted (spec §32).

    Verification triggers only when an academic fact is missing, stale,
    conflicting, or decision-critical and insufficiently grounded.  It is
    always READ-ONLY and OFFICIAL_ONLY.  This is a deterministic helper that
    returns a structured signal for the shared capability layer; it never
    performs I/O, never authorizes an action, and is not a canonical operation
    or rule.
    """
    state = _normalize_verification_fact_state(fact_state)

    if state in ("unknown", "missing"):
        reason = "missing"
    elif state == "stale":
        reason = "stale"
    elif state == "conflicting":
        reason = "conflicting"
    elif state == "reported" and decision_critical:
        reason = "decision_critical_insufficiently_grounded"
    else:
        reason = None

    triggered = reason is not None
    return {
        "needed": triggered,
        "verification_triggered": triggered,
        "reason": reason,
        "fact_state": state,
        "decision_critical": decision_critical,
        "source_class": "official_only",
        "read_only": True,
        "attribute": attribute,
        "scope": scope,
        "action_authorized": False,
        "authorizes_action": False,
    }


def _normalize_verification_fact_state(value: Any) -> str:
    value_s = str(value)
    if value_s in ("unknown", "missing", "missing_value"):
        return "missing"
    if value_s in ("reported", "remembered", "inferred", "calculated"):
        return "reported"
    allowed = {
        "confirmed_official",
        "confirmed",
        "future",
        "stale",
        "conflicting",
        "unknown",
        "missing",
    }
    if value_s in allowed:
        return value_s
    return "unknown"


def evaluate_performance_capacity(
    *,
    performance_observation: dict | None = None,
) -> dict:
    """Bound observed academic performance away from intellectual capacity.

    Observed performance is a **fact about output**, never a measure of
    capacity (spec §16).  A single poor performance establishes neither
    capacity nor incapacity; performance is contextual, time-bound, and
    non-predictive of future ability.  The helper returns a structured record
    that keeps performance and capacity distinct.
    """
    if performance_observation is None:
        return {
            "performance_observed": False,
            "capacity_inferred": False,
            "statement": "No performance observation supplied.",
        }
    return {
        "performance_observed": True,
        "capacity_inferred": False,
        "statement": (
            "Observed performance is a fact about output, not a measure of "
            "intellectual capacity; it never implies capacity or incapacity."
        ),
        "performance_ref": _usable_reference(performance_observation.get("ref")),
    }


def evaluate_deadline(
    *,
    deadline: str | None = None,
) -> dict:
    """Compatibility adapter to the canonical deadline grounding classifier."""
    usable = _usable_reference(deadline)
    structured = classify_deadline_grounding(
        deadline={"value": usable} if usable is not None else None
    )
    return {
        "deadline_present": usable is not None,
        "deadline": usable,
        "auto_scheduled": False,
        "state": structured["state"],
        "confirmed": structured["confirmed"],
        "verification_needed": structured["verification_needed"],
    }


# ── Deadline epistemic states (spec §10) ──────────────────────────────────────

DEADLINE_CONFIRMED_OFFICIAL = "confirmed_official"
DEADLINE_REPORTED = "reported"
DEADLINE_REMEMBERED = "remembered"
DEADLINE_INFERRED = "inferred"
DEADLINE_CALCULATED = "calculated"
DEADLINE_CONFLICTING = "conflicting"
DEADLINE_STALE = "stale"
DEADLINE_UNKNOWN = "unknown"
DEADLINE_FUTURE = "future"

# Deadline provenance values (grounded vs recollection vs inference).
_DEADLINE_PROVENANCE_GROUNDED = frozenset({"grounded", "reported", "calculated"})
_DEADLINE_PROVENANCE_REMEMBERED = frozenset({"remembered"})
_DEADLINE_PROVENANCE_INFERRED = frozenset({"inferred"})
_DEADLINE_PROVENANCE_CALLER_CLAIMED = frozenset({"caller_claimed"})

# Source classes suitable for confirming a deadline (official or attribute-specific).
_DEADLINE_OFFICIAL_SOURCE_CLASSES = frozenset(
    {
        SOURCE_CLASS_OFFICIAL_ACADEMIC_RECORD,
        SOURCE_CLASS_OFFICIAL_PUBLICATION,
        SOURCE_CLASS_REGULATION,
        SOURCE_CLASS_OFFICIAL_ACT_RESOLUTION,
        SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        SOURCE_CLASS_SUBJECT_GUIDE,
        SOURCE_CLASS_PROFESSOR_INSTRUCTION,
        SOURCE_CLASS_INSTITUTIONAL_EMAIL,
    }
)


def _deadline_confirmed_by(
    *,
    source_class: str,
    provenance: str,
    temporal: str,
    source_reference: str | None,
) -> bool:
    """A deadline is confirmed only when it has authorized grounding (grounded
    provenance), a source class suitable for that attribute (official/specific),
    current temporal applicability, and traceable source evidence."""
    if provenance not in _DEADLINE_PROVENANCE_GROUNDED:
        return False
    if source_reference is None:
        return False
    if temporal not in _CURRENT_TEMPORAL_STATES:
        return False
    return source_class in _DEADLINE_OFFICIAL_SOURCE_CLASSES


def classify_deadline_grounding(
    *,
    deadline: Mapping | None = None,
    critical: bool = False,
) -> dict:
    """Classify a deadline's epistemic state from grounded evidence.

    Distinguishes confirmed, reported, remembered, inferred, calculated,
    conflicting, stale, future and unknown.  A ``confirmed`` deadline requires
    authorized grounding plus a source suitable for that attribute plus current
    temporal applicability — a date string existing is never sufficient.  The
    helper never reads the clock and never schedules.  A missing, stale,
    conflicting or decision-critical under-grounded deadline produces a
    *verification need* (a structured signal for the shared capability layer).
    ``critical`` reflects decision-criticality supplied by the calling context.
    """
    if deadline is None:
        return {
            "state": DEADLINE_UNKNOWN,
            "confirmed": False,
            "verification_needed": True,
            "reason": "missing",
            "auto_scheduled": False,
        }
    usable = _usable_reference(deadline.get("value"))
    if usable is None:
        return {
            "state": DEADLINE_UNKNOWN,
            "confirmed": False,
            "verification_needed": True,
            "reason": "missing_value",
            "auto_scheduled": False,
        }

    source_class = _normalize_source_class(deadline.get("source_class"))
    provenance_raw = deadline.get("provenance", "none")
    provenance = _normalize_provenance(provenance_raw)
    temporal = _normalize_temporal(deadline.get("temporal"))
    source_reference = _reference_from(
        deadline,
        "source_reference",
        "source_ref",
    )
    conflicting = bool(deadline.get("conflicting"))
    critical = critical or bool(deadline.get("critical"))
    retrieval_date = _usable_reference(deadline.get("retrieval_date"))
    effective_date = _usable_reference(deadline.get("effective_date"))

    # Conflicting evidence always supersedes a naive confirmation.
    if conflicting:
        return {
            "state": DEADLINE_CONFLICTING,
            "confirmed": False,
            "verification_needed": True,
            "reason": "conflicting",
            "auto_scheduled": False,
            "deadline": usable,
            "retrieval_date": retrieval_date,
            "effective_date": effective_date,
        }

    confirmed = _deadline_confirmed_by(
        source_class=source_class,
        provenance=provenance,
        temporal=temporal,
        source_reference=source_reference,
    )

    if confirmed:
        state = DEADLINE_CONFIRMED_OFFICIAL
    elif temporal == TEMPORAL_EXPIRED:
        state = DEADLINE_STALE
    elif temporal == TEMPORAL_FUTURE:
        state = DEADLINE_FUTURE
    elif provenance_raw in _DEADLINE_PROVENANCE_REMEMBERED:
        state = DEADLINE_REMEMBERED
    elif provenance_raw in _DEADLINE_PROVENANCE_INFERRED:
        state = DEADLINE_INFERRED
    elif provenance_raw in _DEADLINE_PROVENANCE_GROUNDED:
        state = DEADLINE_REPORTED
    elif provenance_raw in _DEADLINE_PROVENANCE_CALLER_CLAIMED:
        state = DEADLINE_UNKNOWN
    else:
        state = DEADLINE_UNKNOWN

    # Verification need: missing, stale, conflicting, or decision-critical and
    # insufficiently grounded.
    verification_needed = (
        state in (DEADLINE_STALE, DEADLINE_CONFLICTING, DEADLINE_UNKNOWN)
        or (critical and not confirmed)
    )

    return {
        "state": state,
        "confirmed": confirmed,
        "verification_needed": verification_needed,
        "reason": state,
        "auto_scheduled": False,
        "deadline": usable,
        "retrieval_date": retrieval_date,
        "effective_date": effective_date,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Reasoning rule scaffolding
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
        domain_id="domain:university",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Conservative university rule for {rule_id}.",
        metadata={"phase": "10.22"},
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


def _mapping(metadata: Mapping, key: str) -> Mapping | None:
    value = metadata.get(key)
    return value if isinstance(value, Mapping) else None


def _seq(metadata: Mapping, key: str) -> tuple | None:
    value = metadata.get(key)
    return value if isinstance(value, (list, tuple)) else None


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicSourceAuthorityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicSourceAuthorityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claims = _seq(context.metadata, "academic_claims")
        if not claims:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No academic claims supplied.",
            )
        findings: list[ReasoningFinding] = []
        by_attribute: dict[str, list[Mapping]] = {}
        for claim in claims:
            if isinstance(claim, Mapping):
                by_attribute.setdefault(_claim_attribute(claim), []).append(claim)

        for attribute in sorted(by_attribute):
            attribute_claims = by_attribute[attribute]
            for effective_scope in _effective_scopes(tuple(attribute_claims)):
                scoped_claims = tuple(
                    claim
                    for claim in attribute_claims
                    if _scope_matches(claim, effective_scope)
                )
                authority = classify_academic_source_authority(
                    attribute=attribute,
                    sources=tuple(_claim_source(claim) for claim in scoped_claims),
                    scope=effective_scope,
                )
                authoritative_id = authority["authoritative_source_id"]
                authoritative_claim = (
                    next(
                        (
                            claim
                            for claim in scoped_claims
                            if _usable_reference(claim.get("id")) == authoritative_id
                        ),
                        None,
                    )
                    if authoritative_id is not None
                    else None
                )
                supporting_source_ids = tuple(
                    authority.get("supporting_source_ids", ())
                )
                references = tuple(
                    ref
                    for claim in scoped_claims
                    if (ref := _usable_reference(claim.get("id"))) is not None
                )
                historical_ids = tuple(
                    sorted(
                        ref
                        for claim in scoped_claims
                        if (ref := _usable_reference(claim.get("id"))) is not None
                        and (
                            ref in authority["superseded_sources"]
                            or _normalize_temporal(claim.get("temporal"))
                            == TEMPORAL_EXPIRED
                        )
                    )
                )
                decision_critical = any(
                    _claim_critical(claim) for claim in scoped_claims
                )
                verification_need = (
                    conditional_verification_trigger(
                        fact_state=(
                            "conflicting"
                            if authority["conflict"]
                            else "unknown"
                        ),
                        decision_critical=decision_critical,
                        attribute=attribute,
                        scope=effective_scope,
                    )
                    if not authority["authority_resolved"]
                    else conditional_verification_trigger(
                        fact_state="missing",
                        decision_critical=decision_critical,
                        attribute=attribute,
                        scope=effective_scope,
                    )
                    if not authority["fact_value_known"]
                    else conditional_verification_trigger(
                        fact_state="confirmed_official",
                        decision_critical=False,
                        attribute=attribute,
                        scope=effective_scope,
                    )
                )
                metadata = {
                "attribute": attribute,
                    "source_type": (
                    authoritative_claim.get("source_type")
                    if authoritative_claim is not None
                    else next(
                        (
                            claim.get("source_type")
                            for claim in attribute_claims
                            if claim.get("source_type") is not None
                        ),
                        SOURCE_AUTHORITY_UNKNOWN,
                    )
                    ),
                    "scope": effective_scope,
                    "supplies_attribute": True,
                    "authority_resolved": authority["authority_resolved"],
                    "authority_conflict": authority["conflict"],
                    "authority_unknown": authority["authority_unknown"],
                    "authority_class": authority["authority_class"],
                    "authoritative_source_id": authoritative_id,
                    "fact_value_known": authority["fact_value_known"],
                    "fact_resolved": authority["fact_resolved"],
                    "authoritative_value": (
                    authoritative_claim.get("value")
                    if authoritative_claim is not None
                    else authority.get("authoritative_value")
                    ),
                    "supporting_source_ids": supporting_source_ids,
                    "historical_source_ids": historical_ids,
                    "superseded_source_ids": authority["superseded_sources"],
                    "matched_sources": authority["matched_sources"],
                    "verification_need": verification_need,
                }
                findings.append(
                    ReasoningFinding(
                        code="ATTRIBUTE_AUTHORITY",
                        message=(
                        f"Attribute {attribute} authority resolved by grounded "
                        "source class, provenance, temporal validity, specificity "
                        "and scope."
                        if authority["authority_resolved"]
                        else f"Authority for attribute {attribute} remains unknown; "
                        "no unsupported source is selected."
                        ),
                        severity=(
                        ReasoningSeverity.INFO
                        if authority["authority_resolved"]
                        else ReasoningSeverity.WARNING
                        ),
                        rule_id=self.definition.id,
                        domain_id=self.definition.domain_id,
                        references=references,
                        metadata=metadata,
                    )
                )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="ATTRIBUTE_SOURCE_AUTHORITY_PRESERVED",
            message="Grounded source authority resolved by attribute.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicContradictionRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicContradictionRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        statements = _seq(context.metadata, "contradiction_statements")
        if not statements:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No contradiction statements supplied.",
            )
        record = resolve_academic_conflict(claims=tuple(statements))
        references: tuple[str, ...] = ()
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            ref = _usable_reference(statement.get("id"))
            if ref is not None:
                references = (*references, ref)
        verification_need = conditional_verification_trigger(
            fact_state="conflicting" if record["unresolved"] else "confirmed_official",
            decision_critical=bool(record["material"]),
            attribute=(
                str(record["conflicts"][0]["attribute"])
                if record["conflicts"]
                else None
            ),
        )
        result_metadata = {
            **record,
            "verification_need": verification_need,
        }
        if record["blocked"]:
            finding = ReasoningFinding(
                code="MATERIAL_CONTRADICTION_UNRESOLVED",
                message=(
                    "A material academic contradiction cannot be resolved by "
                    "source authority; reasoning is fail-closed and must not "
                    "proceed on the assumption."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=references,
                metadata=result_metadata,
            )
            escalation = ReasoningEscalation(
                code="MATERIAL_CONTRADICTION_BLOCKED",
                message="Material contradiction unresolved; reasoning step blocked.",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                escalation=escalation,
                code="MATERIAL_CONTRADICTION_BLOCKED",
                message="Material contradiction unresolved; blocked.",
            )
        if record["unresolved"]:
            finding = ReasoningFinding(
                code="CONTRADICTION_UNRESOLVED",
                message=(
                    "An academic contradiction is unresolved; the conflict is "
                    "preserved and no arbitrary value is chosen."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=references,
                metadata=result_metadata,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="CONTRADICTION_UNRESOLVED",
                message="Academic contradiction preserved as unresolved.",
            )
        finding = ReasoningFinding(
            code="CONTRADICTION_STATE",
            message=(
                "Academic contradiction resolved while preserving history."
                if record["contradiction"]
                else "No academic contradiction among the supplied claims."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=references,
            metadata=result_metadata,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="CONTRADICTION_EVALUATED",
            message="Academic contradiction evaluated deterministically.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicDeadlineRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicDeadlineRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        deadline = _mapping(context.metadata, "deadline")
        # Effective decision-criticality is resolved once and shared by the
        # grounding classification, the verification trigger, and finding
        # metadata.  A context-level ``deadline_decision_critical`` /
        # ``deadline_required`` signal is NOT optional payload detail: it
        # propagates even when a deadline payload carries no ``critical``.
        context_critical = bool(
            context.metadata.get("deadline_decision_critical")
            or context.metadata.get("deadline_required")
        )
        if deadline is None:
            if context_critical:
                verification_need = conditional_verification_trigger(
                    fact_state="missing",
                    decision_critical=context_critical,
                    attribute="deadline",
                )
                finding = ReasoningFinding(
                    code="DEADLINE_VERIFICATION_NEEDED",
                    message=(
                        "A decision-critical deadline is missing; official "
                        "verification is needed before relying on it."
                    ),
                    severity=ReasoningSeverity.WARNING,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    metadata={
                        "state": DEADLINE_UNKNOWN,
                        "confirmed": False,
                        "verification_needed": True,
                        "verification_need": verification_need,
                    },
                )
                return _result(
                    self.definition,
                    context,
                    ReasoningRuleResultStatus.APPLIED,
                    findings=(finding,),
                    code="DEADLINE_VERIFICATION_NEEDED",
                    message="Missing deadline requires official verification.",
                )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No deadline metadata supplied.",
            )
        effective_critical = context_critical or bool(deadline.get("critical"))
        record = classify_deadline_grounding(
            deadline=deadline, critical=effective_critical
        )
        verification_need = conditional_verification_trigger(
            fact_state=record["state"],
            decision_critical=effective_critical,
            attribute="deadline",
            scope=deadline.get("scope"),
        )
        source_reference = _reference_from(
            deadline, "source_reference", "source_ref"
        )
        references = (source_reference,) if source_reference is not None else ()
        evidence_metadata = {
            "state": record["state"],
            "confirmed": record["confirmed"],
            "verification_needed": record["verification_needed"],
            "verification_need": verification_need,
            "critical": effective_critical,
            "source_class": _normalize_source_class(deadline.get("source_class")),
            "temporal": _normalize_temporal(deadline.get("temporal")),
            "provenance": _normalize_provenance(deadline.get("provenance")),
        }
        if record["verification_needed"]:
            finding = ReasoningFinding(
                code="DEADLINE_VERIFICATION_NEEDED",
                message=(
                    f"Deadline state is {record['state']}; official verification "
                    "is needed before relying on it."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=references,
                metadata=evidence_metadata,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="DEADLINE_VERIFICATION_NEEDED",
                message="Deadline state requires official verification.",
            )
        finding = ReasoningFinding(
            code="DEADLINE_FACT",
            message=(
                f"Deadline state {record['state']}; structured fact with "
                "grounding; no calendar event is created."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=references,
            metadata=evidence_metadata,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="DEADLINE_RECORDED",
            message="Deadline recorded as a fact; no auto-scheduling.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EctsConsistencyRule
# ═══════════════════════════════════════════════════════════════════════════════


def _ects_block_reason(record: Mapping) -> str:
    """Build a human-readable reason string for a blocked ECTS conclusion."""
    reasons: list[str] = []
    if record.get("double_counting"):
        reasons.append("credits double-counted")
    if record.get("contradiction"):
        reasons.append("credit buckets contradict each other")
    if record.get("critical_requirement_uncertain"):
        reasons.append("critical requirement status uncertain")
    if not record.get("credit_state_sufficiently_grounded", True):
        reasons.append("grounded credit records missing or incomplete")
    if not record.get("requirement_grounded", True):
        reasons.append("grounded degree requirement missing")
    return "; ".join(reasons) if reasons else "completion not determinable"


@dataclass(frozen=True, slots=True)
class EctsConsistencyRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        ects = _mapping(context.metadata, "ects")
        if ects is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No ECTS metadata supplied.",
            )
        records = tuple(_seq(ects, "records") or ())
        degree_requirement = ects.get("degree_requirement")
        record = check_ects_consistency(
            completed=_parse_ects_integer(ects.get("completed", 0)) or 0,
            recognized=_parse_ects_integer(ects.get("recognized", 0)) or 0,
            enrolled=_parse_ects_integer(ects.get("enrolled", 0)) or 0,
            planned=_parse_ects_integer(ects.get("planned", 0)) or 0,
            pending_recognition=(
                _parse_ects_integer(ects.get("pending_recognition", 0)) or 0
            ),
            required=(
                _parse_ects_integer(ects["required"], minimum=1)
                if ects.get("required") is not None
                else None
            ),
            double_counted=tuple(_seq(ects, "double_counted") or ()),
            contradictory=tuple(_seq(ects, "contradictory") or ()),
            critical_requirement_uncertain=bool(
                ects.get("critical_requirement_uncertain")
            ),
            records=records,
            degree_requirement=(
                degree_requirement
                if isinstance(degree_requirement, Mapping)
                else None
            ),
            derive_from_records=True,
        )
        verification_fact_state = (
            "conflicting"
            if record["double_counting"] or record["contradiction"]
            else "missing"
            if (
                not record["required_known"]
                or not record["credit_state_sufficiently_grounded"]
                or record["critical_requirement_uncertain"]
            )
            else "confirmed_official"
        )
        verification_need = conditional_verification_trigger(
            fact_state=verification_fact_state,
            decision_critical=True,
            attribute="required_credits",
            scope="degree_completion",
        )
        if record["completion_blocked"]:
            finding = ReasoningFinding(
                code="ECTS_COMPLETION_BLOCKED",
                message=(
                    "ECTS completion cannot be concluded: "
                    + _ects_block_reason(record)
                    + "; reported, never silently summed."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata={**record, "verification_need": verification_need},
            )
            gaps: list[ReasoningGap] = []
            if not record["required_known"]:
                gaps.append(
                    ReasoningGap(
                        code="ECTS_REQUIREMENT_UNKNOWN",
                        message=(
                            "The grounded degree requirement is missing; required "
                            "credits remain unknown and completion cannot be confirmed."
                        ),
                        severity=ReasoningSeverity.WARNING,
                        rule_id=self.definition.id,
                        domain_id=self.definition.domain_id,
                        metadata={"verification_need": verification_need},
                    )
                )
            if not record["credit_state_sufficiently_grounded"]:
                gaps.append(
                    ReasoningGap(
                        code="ECTS_CREDIT_STATE_UNKNOWN",
                        message=(
                            "Grounded structured credit records are missing or "
                            "incomplete; reported aggregates cannot confirm completion."
                        ),
                        severity=ReasoningSeverity.WARNING,
                        rule_id=self.definition.id,
                        domain_id=self.definition.domain_id,
                        metadata={"verification_need": verification_need},
                    )
                )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                gaps=tuple(gaps),
                code="ECTS_COMPLETION_BLOCKED",
                message="ECTS completion conclusion blocked.",
            )
        if record["satisfied"]:
            finding = ReasoningFinding(
                code="ECTS_REQUIREMENT_SATISFIED",
                message=(
                    f"Recognized credits ({record['recognized_total']}) "
                    f"satisfy the requirement ({record['required']})."
                ),
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="ECTS_REQUIREMENT_SATISFIED",
                message="ECTS requirement satisfied.",
            )
        finding = ReasoningFinding(
            code="ECTS_REQUIREMENT_NOT_SATISFIED",
            message=(
                f"Recognized credits ({record['recognized_total']}) do not yet "
                f"satisfy the requirement ({record['required']})."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=record,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="ECTS_REQUIREMENT_NOT_SATISFIED",
            message="ECTS requirement not yet satisfied.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ExamAttemptRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ExamAttemptRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        attempt = _mapping(context.metadata, "exam_attempt")
        if attempt is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No exam attempt metadata supplied.",
            )
        record = evaluate_exam_attempt(
            attempts=tuple(_seq(attempt, "attempts") or ()),
            max_attempts=attempt.get("max_attempts"),
            regulation=attempt.get("regulation"),
            require_complete_evidence=True,
        )
        if (
            record["regulation_unknown"]
            or record["regulation_stale"]
            or record["limit_unknown"]
            or record["attempt_evidence_unknown"]
        ):
            verification_need = conditional_verification_trigger(
                fact_state="stale" if record["regulation_stale"] else "missing",
                decision_critical=True,
                attribute="exam_attempt_regulation",
                scope=attempt.get("applicable_scope"),
            )
            finding = ReasoningFinding(
                code="EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED",
                message=(
                    "The governing examination regulation or attempt evidence "
                    "is incomplete; attempt consumption limits remain unknown."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata={**record, "verification_need": verification_need},
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED",
                message="Exam attempt regulation requires official verification.",
            )
        if record["regulation_inactive"]:
            finding = ReasoningFinding(
                code="EXAM_ATTEMPT_REGULATION_INACTIVE",
                message=(
                    "The governing examination regulation is not currently in "
                    "force; attempt limits cannot be evaluated authoritatively."
                ),
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="EXAM_ATTEMPT_REGULATION_INACTIVE",
                message="Attempt regulation not in force.",
            )
        if record["limit_exceeded"]:
            finding = ReasoningFinding(
                code="EXAM_ATTEMPT_LIMIT_EXCEEDED",
                message=(
                    f"{record['consumed_attempts']} grounded ordinary attempts "
                    f"exceed the permitted maximum ({record['max_attempts']}); "
                    "reported without authorizing a retake or modifying the record."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="EXAM_ATTEMPT_LIMIT_EXCEEDED",
                message="Exam attempt limit exceeded; reported, not acted on.",
            )
        finding = ReasoningFinding(
            code="EXAM_ATTEMPT_EVALUATED",
            message=(
                f"{record['consumed_attempts']} grounded ordinary attempts "
                f"within the permitted maximum ({record['max_attempts']})."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=record,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="EXAM_ATTEMPT_EVALUATED",
            message="Exam attempt evaluated within permitted limits.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicWorkloadRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicWorkloadRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        workload = _mapping(context.metadata, "workload")
        if workload is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No workload metadata supplied.",
            )
        total_ect = _parse_ects_integer(workload.get("total_ect", 0))
        full_time_ect = _parse_ects_integer(workload.get("full_time_ect", 30))
        numeric_metadata_unknown = total_ect is None or full_time_ect is None
        record = evaluate_academic_workload(
            total_ect=total_ect if total_ect is not None else 0,
            full_time_ect=full_time_ect if full_time_ect is not None else 30,
            health_constraint=workload.get("health_constraint"),
            hard_constraints=tuple(_seq(workload, "hard_constraints") or ()),
            preferences=tuple(_seq(workload, "preferences") or ()),
            selected_scenario=workload.get("selected_scenario"),
            scenarios=tuple(_seq(workload, "scenarios") or ()),
            derive_from_facts=True,
        )
        if numeric_metadata_unknown:
            record = {
                **record,
                "feasible": False,
                "feasibility_uncertain": True,
                "numeric_metadata_unknown": True,
                "ranking": (),
                "ranking_incomplete": True,
            }
        if record.get("feasibility_uncertain"):
            finding = ReasoningFinding(
                code="WORKLOAD_FEASIBILITY_UNCERTAIN",
                message=(
                    "A decision-critical workload constraint is unknown; affected "
                    "scenarios remain unresolved and cannot be ranked as feasible."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="WORKLOAD_FEASIBILITY_UNCERTAIN",
                message="Workload feasibility remains unresolved.",
            )
        if not record["feasible"]:
            finding = ReasoningFinding(
                code="WORKLOAD_INFEASIBLE",
                message=(
                    "Planned workload fails a hard constraint; the pipeline "
                    "stops before applying preferences. Clinical details are "
                    "not consumed."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="WORKLOAD_INFEASIBLE",
                message="Workload infeasible under hard constraints.",
            )
        if record["stage"] == "tradeoffs":
            finding = ReasoningFinding(
                code="WORKLOAD_TRADEOFFS",
                message=(
                    "Conflicting preferences require a trade-off before a "
                    "scenario can be produced."
                ),
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="WORKLOAD_TRADEOFFS",
                message="Workload trade-offs surfaced.",
            )
        finding = ReasoningFinding(
            code="WORKLOAD_ASSESSED",
            message=(
                f"Workload pipeline reached stage '{record['stage']}'; "
                "proposal (if any) never adopts a decision."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=record,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="WORKLOAD_ASSESSED",
            message="Workload assessed through the planning pipeline.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicDependencyRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicDependencyRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        dependency = _mapping(context.metadata, "dependency")
        if dependency is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No dependency metadata supplied.",
            )
        record = evaluate_academic_dependency(
            subject_id=str(dependency.get("subject_id", "unknown")),
            dependencies=tuple(_seq(dependency, "prerequisites") or ()),
            academic_records=tuple(_seq(dependency, "academic_records") or ()),
            derive_from_academic_state=True,
        )
        blocked_ids = tuple(
            dict.fromkeys(
                record["open_prerequisites"]
                + record["unknown_prerequisites"]
                + record["conditional_prerequisites"]
            )
        )
        if record["dependency_blocked"]:
            blocked_summary = ", ".join(blocked_ids) or "unidentified prerequisite evidence"
            finding = ReasoningFinding(
                code="DEPENDENCY_BLOCKED",
                message=(
                    f"Unsatisfied prerequisites block planning for "
                    f"{record['subject_id']}: {blocked_summary}."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=blocked_ids,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="DEPENDENCY_BLOCKED",
                message="Open prerequisites flagged; no auto-enrolment.",
            )
        finding = ReasoningFinding(
            code="DEPENDENCY_SATISFIED",
            message=f"Prerequisites satisfied for {record['subject_id']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=record["satisfied_prerequisites"],
            metadata=record,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="DEPENDENCY_SATISFIED",
            message="Prerequisites satisfied; dependency resolved.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ObservedPerformanceCapacityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ObservedPerformanceCapacityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        performance = _mapping(context.metadata, "performance_observation")
        if performance is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No performance observation supplied.",
            )
        record = evaluate_performance_capacity(performance_observation=performance)
        references = (
            (record["performance_ref"],)
            if record.get("performance_ref")
            else ()
        )
        finding = ReasoningFinding(
            code="PERFORMANCE_NOT_CAPACITY",
            message=(
                "Observed academic performance is a fact about output, never a "
                "measure of intellectual capacity; capacity is never inferred "
                "from performance."
            ),
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=references,
            metadata={"capacity_inferred": False},
        )
        escalation = ReasoningEscalation(
            code="CAPACITY_INFERENCE_BLOCKED",
            message="Intellectual capacity inference from performance is blocked.",
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            escalation=escalation,
            code="PERFORMANCE_NOT_CAPACITY",
            message="Performance kept distinct from capacity.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicIntegrityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicIntegrityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        integrity = _mapping(context.metadata, "integrity")
        if integrity is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No integrity metadata supplied.",
            )
        resolved = evaluate_academic_integrity(
            mode=str(integrity.get("mode", INTEGRITY_MODE_C)),
            caller_restriction=integrity.get("caller_restriction"),
            grounded_restriction=integrity.get("grounded_restriction"),
            remembered_restriction=bool(integrity.get("remembered_restriction")),
            current_course=integrity.get("course", integrity.get("current_course")),
            current_assessment=integrity.get(
                "assessment", integrity.get("current_assessment")
            ),
            requested_action=integrity.get(
                "requested_action", integrity.get("action")
            ),
        )
        # Academic Integrity Mode C is permissive-by-default (spec §16): the
        # domain does not police academic conduct; it preserves the user's
        # stated mode, never substitutes its own policing for the institution's
        # rules, and never treats a caller boolean as a grounded prohibition.
        if not resolved["mode_valid"]:
            finding = ReasoningFinding(
                code="INTEGRITY_MODE_REJECTED",
                message=resolved["reason"],
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                code="INTEGRITY_MODE_REJECTED",
                message="Unsupported integrity mode blocked.",
            )
        code = (
            "INTEGRITY_RESTRICTION_APPLIED"
            if resolved["restriction_grounded"]
            else "INTEGRITY_MODE_PRESERVED"
        )
        restriction_evidence = (
            integrity.get("grounded_restriction")
            if isinstance(integrity.get("grounded_restriction"), Mapping)
            else None
        )
        evidence_metadata = {
            "restriction_source_class": (
                restriction_evidence.get("source_class")
                if restriction_evidence is not None
                else None
            ),
            "restriction_temporal": (
                restriction_evidence.get("temporal")
                if restriction_evidence is not None
                else None
            ),
            "restriction_provenance": (
                restriction_evidence.get("provenance")
                if restriction_evidence is not None
                else None
            ),
            "restriction_source_reference": _reference_from(
                restriction_evidence,
                "source_reference",
                "source_ref",
            )
            if restriction_evidence is not None
            else None,
        }
        references = (
            (evidence_metadata["restriction_source_reference"],)
            if evidence_metadata["restriction_source_reference"] is not None
            else ()
        )
        finding = ReasoningFinding(
            code=code,
            message=resolved["reason"],
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=references,
            metadata={
                "mode": resolved["mode"],
                "assistance_permitted": resolved["assistance_permitted"],
                "restriction_grounded": resolved["restriction_grounded"],
                "restriction_applies": resolved["restriction_applies"],
                "restriction_scope": resolved["restriction_scope"],
                "current_course": resolved["current_course"],
                "current_assessment": resolved["current_assessment"],
                "requested_action": resolved["requested_action"],
                "caller_forbidden_ignored": resolved["caller_forbidden_ignored"],
                **evidence_metadata,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code=code,
            message=resolved["reason"],
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicDecisionPreservationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicDecisionPreservationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        decision_support = _mapping(context.metadata, "decision_support")
        if decision_support is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No decision-support metadata supplied.",
            )
        finding = ReasoningFinding(
            code="DECISION_NOT_ADOPTED",
            message=(
                "Decision support compares options against explicit criteria; "
                "no academic decision is adopted, persisted, or executed."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={"adopted_decision": False, "requires_user_confirmation": True},
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="DECISION_NOT_ADOPTED",
            message="Academic decision preserved for the user; never adopted.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_university_rules() -> tuple[Any, ...]:
    """Build the ten University Domain rules deterministically in canonical order."""
    by_id = {
        "university.academic_contradiction": AcademicContradictionRule(
            definition=_definition(
                "university.academic_contradiction",
                "AcademicContradictionRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                740,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "university.academic_deadline": AcademicDeadlineRule(
            definition=_definition(
                "university.academic_deadline",
                "AcademicDeadlineRule",
                ReasoningRuleCategory.TEMPORALITY.value,
                730,
            )
        ),
        "university.academic_decision_preservation": AcademicDecisionPreservationRule(
            definition=_definition(
                "university.academic_decision_preservation",
                "AcademicDecisionPreservationRule",
                ReasoningRuleCategory.SAFETY.value,
                770,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "university.academic_dependency": AcademicDependencyRule(
            definition=_definition(
                "university.academic_dependency",
                "AcademicDependencyRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                750,
            )
        ),
        "university.academic_integrity": AcademicIntegrityRule(
            definition=_definition(
                "university.academic_integrity",
                "AcademicIntegrityRule",
                ReasoningRuleCategory.SAFETY.value,
                790,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "university.academic_source_authority": AcademicSourceAuthorityRule(
            definition=_definition(
                "university.academic_source_authority",
                "AcademicSourceAuthorityRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                720,
            )
        ),
        "university.academic_workload": AcademicWorkloadRule(
            definition=_definition(
                "university.academic_workload",
                "AcademicWorkloadRule",
                ReasoningRuleCategory.INFERENCE.value,
                760,
            )
        ),
        "university.ects_consistency": EctsConsistencyRule(
            definition=_definition(
                "university.ects_consistency",
                "EctsConsistencyRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                735,
            )
        ),
        "university.exam_attempt": ExamAttemptRule(
            definition=_definition(
                "university.exam_attempt",
                "ExamAttemptRule",
                ReasoningRuleCategory.INFERENCE.value,
                745,
            )
        ),
        "university.observed_performance_capacity": ObservedPerformanceCapacityRule(
            definition=_definition(
                "university.observed_performance_capacity",
                "ObservedPerformanceCapacityRule",
                ReasoningRuleCategory.SAFETY.value,
                780,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
    }
    return tuple(by_id[rule_id] for rule_id in UNIVERSITY_RULE_IDS)


__all__ = [
    "CONTRADICTION_MATERIAL",
    "CONTRADICTION_RESOLVED",
    "CONTRADICTION_UNRESOLVED",
    "INTEGRITY_MODE_A",
    "INTEGRITY_MODE_B",
    "INTEGRITY_MODE_C",
    "SOURCE_AUTHORITY_ATTRIBUTE",
    "SOURCE_AUTHORITY_INFERRED",
    "SOURCE_AUTHORITY_OFFICIAL",
    "SOURCE_AUTHORITY_REGULATION",
    "SOURCE_AUTHORITY_UNKNOWN",
    "SOURCE_AUTHORITY_USER_REPORTED",
    "UNIVERSITY_RULE_IDS",
    "AcademicContradictionRule",
    "AcademicDeadlineRule",
    "AcademicDecisionPreservationRule",
    "AcademicDependencyRule",
    "AcademicIntegrityRule",
    "AcademicSourceAuthorityRule",
    "AcademicWorkloadRule",
    "EctsConsistencyRule",
    "ExamAttemptRule",
    "ObservedPerformanceCapacityRule",
    "build_university_rules",
    "check_ects_consistency",
    "conditional_verification_trigger",
    "evaluate_academic_contradiction",
    "evaluate_academic_dependency",
    "evaluate_academic_integrity",
    "evaluate_academic_workload",
    "evaluate_deadline",
    "evaluate_exam_attempt",
    "evaluate_performance_capacity",
    "resolve_source_authority_by_attribute",
]
