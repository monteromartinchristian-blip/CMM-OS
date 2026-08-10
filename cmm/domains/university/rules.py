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
                "source_id": source.get("source_id"),
                "source_class": source_class,
                "provenance": provenance,
                "temporal": temporal,
                "specificity": specificity,
                "scope": scope_value,
                "grounded": grounded,
                "current": current,
                "rank": rank,
                "supersedes": _normalize_references(source.get("supersedes")),
                "superseded_by": _normalize_references(source.get("superseded_by")),
            }
        )

    # Only grounded, currently-valid sources can carry current authority.
    candidates = [e for e in evaluated if e["grounded"] and e["current"] and e["rank"] > 0]
    if not candidates:
        return {
            "attribute": attribute,
            "authority_resolved": False,
            "authoritative_source_id": None,
            "authority_class": None,
            "matched_sources": tuple(evaluated),
            "superseded_sources": (),
            "authority_unknown": True,
            "conflict": False,
            "reason": "no_grounded_current_authority",
        }

    # Apply supersession: a candidate that is superseded by another grounded
    # current candidate is demoted to history (not the current authority).
    superseded_ids: set[str] = set()
    for candidate in candidates:
        for target in candidate["supersedes"]:
            targeting = [
                e
                for e in candidates
                if e["source_id"] == target
            ]
            if targeting:
                superseded_ids.add(target)

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

    if len(top) > 1:
        # Equal-authority, equally-specific incompatible claims: unresolved.
        return {
            "attribute": attribute,
            "authority_resolved": False,
            "authoritative_source_id": None,
            "authority_class": None,
            "matched_sources": tuple(evaluated),
            "superseded_sources": tuple(sorted(superseded_ids)),
            "authority_unknown": True,
            "conflict": True,
            "reason": "equal_authority_conflict",
        }

    winner = top[0]
    return {
        "attribute": attribute,
        "authority_resolved": True,
        "authoritative_source_id": winner["source_id"],
        "authority_class": winner["source_class"],
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
    """Resolve the authoritative source for a *single* academic attribute.

    Source authority is preserved **by attribute**, not by a global naive
    ranking (spec §9).  Each source carries a ``source_type`` chosen from the
    closed set above.  For the given attribute, the highest-ranking source
    type that actually supplies the attribute is authoritative; official /
    regulation sources dominate user-reported and inferred sources.

    A source is only authoritative for the attribute when it *supplies* that
    attribute (``supplied_attributes`` contains ``attribute``).  A source that
    does not supply the attribute never competes for it.
    """
    candidate: str | None = None
    candidate_rank = len(_SOURCE_TYPE_RANK)
    matched: list[dict] = []
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        supplied = source.get("supplied_attributes", ())
        if not isinstance(supplied, (list, tuple)) or attribute not in supplied:
            continue
        source_type = str(source.get("source_type", SOURCE_AUTHORITY_UNKNOWN))
        try:
            rank = _SOURCE_TYPE_RANK.index(source_type)
        except ValueError:
            rank = len(_SOURCE_TYPE_RANK)
        matched.append(
            {
                "source_id": source.get("source_id"),
                "source_type": source_type,
                "rank": rank,
            }
        )
        if rank < candidate_rank:
            candidate_rank = rank
            candidate = source_type
    return {
        "attribute": attribute,
        "authority": candidate,
        "authority_source_type": candidate,
        "matched_sources": tuple(matched),
        "authority_resolved": candidate is not None,
    }


def evaluate_academic_contradiction(
    *,
    statements: tuple = (),
) -> dict:
    """Classify an academic contradiction state deterministically.

    Returns one of: ``resolved``, ``unresolved``, ``material``.

    A contradiction is **material** when it concerns an attribute that is
    required for a pending academic decision/reasoning step and the divergent
    sources cannot be ordered by source authority (e.g. two official sources
    disagree).  A material contradiction that cannot be resolved is
    **fail-closed** (spec §10): the reasoning step must not proceed on the
    assumption.
    """
    if not statements:
        return {
            "state": CONTRADICTION_UNRESOLVED,
            "material": False,
            "resolved": False,
        }
    material = False
    resolved = True
    for statement in statements:
        if not isinstance(statement, Mapping):
            continue
        if statement.get("material"):
            material = True
        if statement.get("unresolved"):
            resolved = False
    if material and not resolved:
        return {
            "state": CONTRADICTION_MATERIAL,
            "material": True,
            "resolved": False,
        }
    if resolved:
        return {
            "state": CONTRADICTION_RESOLVED,
            "material": material,
            "resolved": True,
        }
    return {
        "state": CONTRADICTION_UNRESOLVED,
        "material": False,
        "resolved": False,
    }


def _claim_field(claim: Mapping, key: str) -> Any:
    return claim.get(key)


def _claim_scope(claim: Mapping) -> str | None:
    scope = _claim_field(claim, "scope")
    return scope if isinstance(scope, str) and scope.strip() else None


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
        "supplied_attributes": (),
        "supersedes": claim.get("supersedes"),
    }


def _incompatible(left: Any, right: Any) -> bool:
    """Two values are incompatible when they are non-equal and neither is an
    absent/unknown placeholder."""
    if left is None or right is None:
        return False
    if isinstance(left, str) and not left.strip():
        return False
    if isinstance(right, str) and not right.strip():
        return False
    return left != right


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
    current_by_attribute: dict[str, Any] = {}
    material = False
    unresolved = False

    for attribute, attr_claims in grouped.items():
        if len(attr_claims) < 2:
            continue
        # Find the first pair of incompatible, scope-overlapping, contemporary
        # claims for this attribute.
        for i in range(len(attr_claims)):
            for j in range(i + 1, len(attr_claims)):
                left = attr_claims[i]
                right = attr_claims[j]
                left_scope = _claim_scope(left)
                right_scope = _claim_scope(right)
                # Scope overlap: two claims with different non-null scopes do not
                # overlap, so they never conflict on the same attribute.
                if (
                    left_scope is not None
                    and right_scope is not None
                    and left_scope != right_scope
                ):
                    continue
                if (
                    scope is not None
                    and left_scope is not None
                    and left_scope != scope
                ):
                    continue
                if (
                    scope is not None
                    and right_scope is not None
                    and right_scope != scope
                ):
                    continue
                if not _incompatible(_claim_value(left), _claim_value(right)):
                    continue
                # A conflict exists between these two claims.
                conflicts.append(
                    {
                        "attribute": attribute,
                        "left_id": left.get("id"),
                        "right_id": right.get("id"),
                        "left_value": _claim_value(left),
                        "right_value": _claim_value(right),
                    }
                )
                # Try supersession resolution.
                left_supersedes = _normalize_references(left.get("supersedes"))
                right_supersedes = _normalize_references(right.get("supersedes"))
                left_id = left.get("id")
                right_id = right.get("id")
                if left_id in right_supersedes:
                    superseded_ids.add(left_id)
                    current_by_attribute.setdefault(attribute, _claim_value(right))
                elif right_id in left_supersedes:
                    superseded_ids.add(right_id)
                    current_by_attribute.setdefault(attribute, _claim_value(left))
                else:
                    # No supersession: try authority resolution.
                    authority = classify_academic_source_authority(
                        attribute=attribute,
                        sources=(_claim_source(left), _claim_source(right)),
                        scope=scope,
                    )
                    if authority["authority_resolved"]:
                        winner_id = authority["authoritative_source_id"]
                        if winner_id == left_id:
                            current_by_attribute.setdefault(
                                attribute, _claim_value(left)
                            )
                        elif winner_id == right_id:
                            current_by_attribute.setdefault(
                                attribute, _claim_value(right)
                            )
                        else:
                            unresolved = True
                    else:
                        unresolved = True
                if _claim_critical(left) or _claim_critical(right):
                    material = True
        # Guard: if any pair for this attribute remained unresolved, mark.
        # (handled above via unresolved flag when no resolution path applied)

    resolved = not unresolved
    blocked = bool(conflicts) and unresolved and material

    return {
        "contradiction": bool(conflicts),
        "resolved": resolved,
        "unresolved": bool(conflicts) and unresolved,
        "material": material,
        "blocked": blocked,
        "current_value": _first_current(current_by_attribute),
        "superseded_claims": tuple(sorted(superseded_ids)),
        "conflicts": tuple(conflicts),
    }


def _first_current(mapping: Mapping) -> Any:
    for value in mapping.values():
        return value
    return None


def check_ects_consistency(
    *,
    completed: int = 0,
    recognized: int = 0,
    enrolled: int = 0,
    planned: int = 0,
    pending_recognition: int = 0,
    required: int = 0,
    double_counted: tuple = (),
    contradictory: tuple = (),
    critical_requirement_uncertain: bool = False,
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
    recognized_total = int(completed) + int(recognized)
    double_counting = len(double_counted) > 0
    contradiction = len(contradictory) > 0
    completion_blocked = critical_requirement_uncertain or double_counting or contradiction

    satisfied = (
        not completion_blocked
        and recognized_total >= int(required)
    )

    return {
        "recognized_total": recognized_total,
        "completed": int(completed),
        "recognized": int(recognized),
        "enrolled": int(enrolled),
        "planned": int(planned),
        "pending_recognition": int(pending_recognition),
        "required": int(required),
        "double_counted": tuple(double_counted),
        "double_counting": double_counting,
        "contradictory": tuple(contradictory),
        "contradiction": contradiction,
        "critical_requirement_uncertain": critical_requirement_uncertain,
        "completion_blocked": completion_blocked,
        "completion_determinable": not completion_blocked,
        "satisfied": satisfied,
        "flagged": double_counting or contradiction or critical_requirement_uncertain,
    }


def evaluate_exam_attempt(
    *,
    attempts: tuple = (),
    max_attempts: int | None = 3,
    regulation_active: bool = True,
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

    for entry in attempts:
        if not isinstance(entry, Mapping):
            continue
        if not entry.get("grounded"):
            ungrounded_attempts += 1
            continue
        kind = entry.get("kind", "ordinary")
        status = entry.get("status", "consumed")
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

    if not regulation_active:
        return {
            "consumed_attempts": consumed_attempts,
            "reassessment_count": reassessment_count,
            "ungrounded_attempts": ungrounded_attempts,
            "canceled": canceled,
            "waived": waived,
            "failed_grade_not_consumed": failed_grade_not_consumed,
            "max_attempts": max_attempts,
            "regulation_inactive": True,
            "within_limits": False,
            "limit_exceeded": False,
        }

    within_limits = max_attempts is None or consumed_attempts <= max_attempts
    return {
        "consumed_attempts": consumed_attempts,
        "reassessment_count": reassessment_count,
        "ungrounded_attempts": ungrounded_attempts,
        "canceled": canceled,
        "waived": waived,
        "failed_grade_not_consumed": failed_grade_not_consumed,
        "max_attempts": max_attempts,
        "regulation_inactive": False,
        "within_limits": within_limits,
        "limit_exceeded": not within_limits,
    }


def evaluate_academic_workload(
    *,
    total_ect: int = 0,
    full_time_ect: int = 30,
    health_constraint: Mapping | None = None,
    hard_constraints: tuple = (),
    preferences: tuple = (),
    selected_scenario: str | None = None,
) -> dict:
    """Evaluate academic workload through the staged planning pipeline.

    Pipeline: HARD CONSTRAINTS -> FEASIBILITY -> PREFERENCES -> TRADE-OFFS ->
    SCENARIOS -> PROPOSAL.  An unsatisfied hard constraint stops the pipeline
    before preferences are applied.  An authorized Health functional constraint
    (e.g. a reduced-load cap) participates as a hard constraint affecting
    feasibility; clinical details are never consumed by the domain.  A proposal
    is only emitted at the final stage and never adopts a decision.
    """
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


def evaluate_academic_dependency(
    *,
    subject_id: str,
    dependencies: tuple = (),
) -> dict:
    """Evaluate academic dependency relationships deterministically.

    A subject may list prerequisite subjects (including credit/TFG sequencing).
    A prerequisite is satisfied only by *grounded* evidence of passing; a
    caller-claimed ``passed`` boolean with no grounding is not authoritative and
    is ignored.  An unknown prerequisite status remains unresolved and is never
    treated as satisfied.  The helper only *reports*; it never changes the
    official record and never auto-enrols.
    """
    satisfied: list[str] = []
    open_prereqs: list[str] = []
    unknown_prereqs: list[str] = []
    caller_passed_ignored: list[str] = []

    for dep in dependencies:
        if not isinstance(dep, Mapping):
            continue
        dep_id = _usable_reference(dep.get("id"))
        if dep_id is None:
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
        "dependency_blocked": bool(open_prereqs or unknown_prereqs),
    }


def evaluate_academic_integrity(
    *,
    mode: str = INTEGRITY_MODE_C,
    caller_restriction: Mapping | None = None,
    grounded_restriction: Mapping | None = None,
    remembered_restriction: bool = False,
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
    restriction_scope: tuple[str, ...] = ()
    if isinstance(grounded_restriction, Mapping):
        status = grounded_restriction.get("status")
        grounded = bool(grounded_restriction.get("grounded"))
        source_class = str(grounded_restriction.get("source_class", ""))
        temporal = str(grounded_restriction.get("temporal", ""))
        if (
            status == "prohibited"
            and grounded
            and source_class == "official_regulation"
            and temporal == "current"
        ):
            restriction_grounded = True
            restriction_scope = _normalize_references(
                grounded_restriction.get("scope")
            )

    remembered_not_official = bool(
        remembered_restriction
        or (
            isinstance(grounded_restriction, Mapping)
            and not restriction_grounded
            and grounded_restriction.get("source_class") != "official_regulation"
        )
    )

    assistance_permitted = not restriction_grounded

    return {
        "mode": mode,
        "mode_valid": True,
        "assistance_permitted": assistance_permitted,
        "restriction": "prohibited" if restriction_grounded else None,
        "restriction_grounded": restriction_grounded,
        "restriction_scope": restriction_scope,
        "caller_forbidden_ignored": caller_forbidden and assistance_permitted,
        "remembered_not_official": remembered_not_official,
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
        "verification_triggered": triggered,
        "reason": reason,
        "fact_state": state,
        "decision_critical": decision_critical,
        "source_class": "official_only",
        "read_only": True,
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
    """Represent a deadline as a structured fact with its own provenance.

    A deadline is a factual item with a date; it is never invented and never
    auto-scheduled.  The helper reports whether a usable deadline value is
    present.  It does not create calendar events.
    """
    usable = _usable_reference(deadline)
    return {
        "deadline_present": usable is not None,
        "deadline": usable,
        "auto_scheduled": False,
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
) -> bool:
    """A deadline is confirmed only when it has authorized grounding (grounded
    provenance), a source class suitable for that attribute (official/specific),
    and current temporal applicability."""
    if provenance not in _DEADLINE_PROVENANCE_GROUNDED:
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
        for claim in claims:
            if not isinstance(claim, Mapping):
                continue
            attribute = str(claim.get("attribute", "unknown"))
            source_type = str(claim.get("source_type", SOURCE_AUTHORITY_UNKNOWN))
            supplied = claim.get("supplied_attributes", ())
            supplies_attribute = (
                isinstance(supplied, (list, tuple)) and attribute in supplied
            )
            claim_id = _usable_reference(claim.get("id"))
            references = (claim_id,) if claim_id is not None else ()
            findings.append(
                ReasoningFinding(
                    code="ATTRIBUTE_AUTHORITY",
                    message=(
                        f"Attribute {attribute} supplied by source type "
                        f"{source_type}; authority preserved by attribute."
                    ),
                    severity=ReasoningSeverity.INFO,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=references,
                    metadata={
                        "attribute": attribute,
                        "source_type": source_type,
                        "supplies_attribute": supplies_attribute,
                    },
                )
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="ATTRIBUTE_SOURCE_AUTHORITY_PRESERVED",
            message="Source authority preserved by attribute, not a global ranking.",
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
        if deadline is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No deadline metadata supplied.",
            )
        record = classify_deadline_grounding(
            deadline=deadline, critical=bool(deadline.get("critical"))
        )
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
                metadata={
                    "state": record["state"],
                    "confirmed": record["confirmed"],
                    "verification_needed": True,
                },
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
            metadata={
                "state": record["state"],
                "confirmed": record["confirmed"],
                "verification_needed": False,
            },
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
        record = check_ects_consistency(
            completed=int(ects.get("completed", 0)),
            recognized=int(ects.get("recognized", 0)),
            enrolled=int(ects.get("enrolled", 0)),
            planned=int(ects.get("planned", 0)),
            pending_recognition=int(ects.get("pending_recognition", 0)),
            required=int(ects.get("required", 0)),
            double_counted=tuple(ects.get("double_counted", ())),
            contradictory=tuple(ects.get("contradictory", ())),
            critical_requirement_uncertain=bool(
                ects.get("critical_requirement_uncertain")
            ),
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
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
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
            attempts=tuple(attempt.get("attempts", ())),
            max_attempts=attempt.get("max_attempts"),
            regulation_active=bool(attempt.get("regulation_active", True)),
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
        record = evaluate_academic_workload(
            total_ect=int(workload.get("total_ect", 0)),
            full_time_ect=int(workload.get("full_time_ect", 30)),
            health_constraint=workload.get("health_constraint"),
            hard_constraints=tuple(workload.get("hard_constraints", ())),
            preferences=tuple(workload.get("preferences", ())),
            selected_scenario=workload.get("selected_scenario"),
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
            dependencies=tuple(dependency.get("prerequisites", ()) or ()),
        )
        blocked_ids = tuple(
            dict.fromkeys(record["open_prerequisites"] + record["unknown_prerequisites"])
        )
        if record["dependency_blocked"]:
            finding = ReasoningFinding(
                code="DEPENDENCY_BLOCKED",
                message=(
                    f"Unsatisfied prerequisites block planning for "
                    f"{record['subject_id']}: {', '.join(blocked_ids)}."
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
        finding = ReasoningFinding(
            code=code,
            message=resolved["reason"],
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "mode": resolved["mode"],
                "assistance_permitted": resolved["assistance_permitted"],
                "restriction_grounded": resolved["restriction_grounded"],
                "restriction_scope": resolved["restriction_scope"],
                "caller_forbidden_ignored": resolved["caller_forbidden_ignored"],
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