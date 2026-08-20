"""Phase 10.24 — Reflection Domain Rules and deterministic helpers.

A declarative domain + pure deterministic reflection helpers.  The helper
functions are state-free: no IO, no model calls, no registry mutation, no
internal clock.  They receive context explicitly and return deterministic
structures.

The six reasoning rules are ``@dataclass(frozen=True, slots=True)``
definitions exposing ``definition`` and ``evaluate(context)``, exactly like
the General, Health, Relationships, University, and Opposition Domain rules,
so they compose with the existing cognitive layer.

Epistemic-safety core (frozen spec §6–§17, §24–§29):

- distinct epistemic levels are preserved: observation != interpretation !=
  belief != fact; hypothesis != fact; plausibility != certainty; emotion !=
  external evidence; memory != current truth; repetition != proof;
  correlation != cause.
- multiple hypotheses are retained; no arbitrary winner; no first-input-wins;
  a stronger hypothesis stays a hypothesis.
- ambivalence is valid information, never forced into one true state.
- belief/evidence/counterevidence/experience/interpretation stay separate;
  malformed evidence fails closed and never widens certainty.
- open questions remain open; a plausible hypothesis does not close them.
- temporal evolution requires grounded chronology; equal timestamps,
  malformed dates and input order never manufacture direction.
- interest mapping is source-grounded; duplicates never inflate evidence;
  model summaries never become independent evidence.
- persistence is confirmation-gated: only the literal boolean ``True``
  authorizes a confirmation field; repetition never establishes confirmed
  persistence.
- reflection completes successfully without a conclusion; no forced
  conclusion and no psychological hypothesis presented as a diagnosis.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
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
from cmm.domains.reflection.catalog import CANONICAL_REFLECTION_RULE_IDS
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

REFLECTION_RULE_IDS: tuple[str, ...] = CANONICAL_REFLECTION_RULE_IDS

# ── Strict literal gates ──────────────────────────────────────────────────────

def _boolean_true(value: Any) -> bool:
    """Strict runtime boolean: only the literal ``True`` counts (not truthiness)."""
    return isinstance(value, bool) and value is True


def _grants_authorization(value: Any) -> bool:
    """Only the literal ``True`` authorizes a boolean-gated field.

    ``"true"``, ``"false"``, ``1``, ``0``, ``[]``, ``{}``, ``None`` and
    arbitrary objects never authorize.  No coercion and no string parsing.
    """
    return value is True


def _authorization_malformed(value: Any) -> bool:
    """True when a boolean-gated field holds an unsupported non-boolean type."""
    return value is not None and not isinstance(value, bool)


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


def _usable_string_items(value: Any) -> tuple[str, ...]:
    """Yield the ordered unique usable scalar strings of a collection.

    A scalar string value is treated as a single-item collection.  Malformed
    members are dropped (they are tracked by the caller as malformed when the
    overall collection is inspected); a non-collection non-string is empty.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, (list, tuple)):
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            usable = _usable_scalar_string(item)
            if usable is not None and usable not in seen:
                seen.add(usable)
                result.append(usable)
        return tuple(result)
    return ()


def _normalize_collection(
    value: Any,
    *,
    require_mapping_elements: bool = False,
) -> tuple[list, bool]:
    """Normalize a raw collection value into ``(items, malformed)``.

    ``None`` yields an empty collection that is NOT malformed (absent is
    distinct from malformed).  A non-collection, non-string value is malformed
    when a collection is required.
    """
    if value is None:
        return [], False
    if isinstance(value, str):
        # A plain string is not a collection of semantic records.
        return [], True
    if isinstance(value, (list, tuple)):
        items = list(value)
        if require_mapping_elements:
            malformed = any(not isinstance(item, Mapping) for item in items)
        else:
            malformed = False
        return items, malformed
    return [], True


def _value_missing(value: Any) -> bool:
    """Only ``None`` and blank strings are missing; numeric zero/False are real values."""
    return value is None or (isinstance(value, str) and not value.strip())


def _finite_number(value: Any) -> float | None:
    """Parse a finite number (int/float, not bool) or return ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


# ── Closed evidence states ───────────────────────────────────────────────────

EVIDENCE_ABSENT = "absent"
EVIDENCE_VALID_EMPTY = "valid_empty"
EVIDENCE_MALFORMED = "malformed"
EVIDENCE_UNKNOWN = "unknown"
EVIDENCE_CONFLICTING = "conflicting"
EVIDENCE_GROUNDED = "grounded"
EVIDENCE_UNGROUNDED = "ungrounded"
EVIDENCE_TEMPORALLY_AMBIGUOUS = "temporally_ambiguous"

# ── Chronology normalization ─────────────────────────────────────────────────

CHRONOLOGY_ORDERED = "ordered"
CHRONOLOGY_EQUAL = "equal_timestamps"
CHRONOLOGY_MALFORMED = "malformed"
CHRONOLOGY_UNKNOWN = "unknown"
CHRONOLOGY_EMPTY = "empty"

# Forbidden certainty phrases (spec §13) used by NoForcedConclusionRule.
FORCED_CONCLUSION_PHRASES: tuple[str, ...] = (
    "therefore this proves",
    "the real reason is",
    "you are definitely",
    "the answer is clearly",
    "definitely is",
    "clearly proves",
    "certainly means",
    "must be because",
)


def _normalize_chronology(value: Any) -> float | None:
    """Normalize a date/time value into a UTC epoch scalar, or ``None``.

    Naive values (e.g. date-only) are treated as UTC; aware values are
    normalized to UTC; ``Z`` is normalized to ``+00:00``.  Non-date strings,
    numbers, booleans, collections and ``None`` are not chronological.  The
    result is a plain float so it never leaks a ``datetime`` into public
    structured output.
    """
    if value is None or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.timestamp()


# ── Epistemic level classification (spec §6, §10) ───────────────────────────

LEVEL_SOURCE = "source"
LEVEL_OBSERVATION = "observation"
LEVEL_INTERPRETATION = "interpretation"
LEVEL_BELIEF = "belief"
LEVEL_HYPOTHESIS = "hypothesis"
LEVEL_COUNTER_HYPOTHESIS = "counter_hypothesis"
LEVEL_UNCERTAINTY = "uncertainty"
LEVEL_OPEN_QUESTION = "open_question"
LEVEL_UNKNOWN = "unknown"

_KNOWN_LEVELS: frozenset[str] = frozenset(
    {
        LEVEL_SOURCE,
        LEVEL_OBSERVATION,
        LEVEL_INTERPRETATION,
        LEVEL_BELIEF,
        LEVEL_HYPOTHESIS,
        LEVEL_COUNTER_HYPOTHESIS,
        LEVEL_UNCERTAINTY,
        LEVEL_OPEN_QUESTION,
    }
)

# Diagnostic / classification vocabulary that must never be produced as a
# fact by Reflection (spec §15, §29).
DIAGNOSTIC_TERMS: tuple[str, ...] = (
    "diagnosis",
    "disorder",
    "personality disorder",
    "attachment style is",
    "you are a",
    "you are an",
    "you have [a-z]+ disorder",
    "narcissist",
    "psychopath",
    "sociopath",
    "borderline",
    "bipolar",
    "depressive disorder",
    "anxiety disorder",
)


def classify_statement_level(value: Any) -> dict:
    """Classify a statement into the canonical epistemic pipeline level.

    A caller-supplied ``level`` is honored only when it is one of the known
    levels; a supplied ``fact=True``/``confirmed=True``/``official=True`` label
    never promotes the level by itself (spec §24).  The projection is
    JSON-safe and deterministic.
    """
    if not isinstance(value, Mapping):
        return {
            "level": LEVEL_UNKNOWN,
            "promotion": False,
            "labeled_fact": False,
            "malformed": True,
        }
    labeled_fact = _boolean_true(value.get("fact")) or _boolean_true(
        value.get("confirmed")
    ) or _boolean_true(value.get("official"))
    level = value.get("level")
    if isinstance(level, str) and level in _KNOWN_LEVELS:
        normalized_level = level
    else:
        normalized_level = LEVEL_UNKNOWN
    if normalized_level == LEVEL_UNKNOWN:
        # Positional inference: an explicit experience/interpretation marker
        # selects the closest level without promoting to belief/fact.
        if _boolean_true(value.get("experience")):
            normalized_level = LEVEL_OBSERVATION
        elif _boolean_true(value.get("interpretation")):
            normalized_level = LEVEL_INTERPRETATION
        elif _boolean_true(value.get("hypothesis")):
            normalized_level = LEVEL_HYPOTHESIS
        elif _boolean_true(value.get("question")):
            normalized_level = LEVEL_OPEN_QUESTION
    promotion = bool(
        normalized_level in (LEVEL_BELIEF, LEVEL_HYPOTHESIS) and labeled_fact
    )
    return {
        "level": normalized_level,
        "promotion": promotion,
        "labeled_fact": labeled_fact,
        "malformed": False,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Task 4 helpers — multiple hypotheses + no forced conclusion
# ═══════════════════════════════════════════════════════════════════════════════


def evaluate_hypotheses(
    *,
    hypotheses: Any = (),
) -> dict:
    """Evaluate a set of hypotheses preserving multiples, evidence and unknowns.

    Every plausible hypothesis is retained.  Supporting and counterevidence
    references are preserved per hypothesis.  Conflicts (the same reference
    supporting different statements, or supporting one and contradicting
    another) keep the result unresolved.  No arbitrary winner is selected; a
    hypothesis with strictly more grounded support than every other may be
    marked ``relative_strength="stronger"`` but is never converted into a
    fact.  Exact duplicates collapse (no evidence inflation).  Input order
    never changes the semantic result.  All outputs are JSON-safe.
    """
    raw, malformed = _normalize_collection(
        hypotheses, require_mapping_elements=True
    )
    if malformed:
        return {
            "hypotheses": (),
            "supported_ids": (),
            "conflicting_ids": (),
            "unresolved": True,
            "winner_selected": False,
            "forced_conclusion": False,
            "insufficient_basis_to_rank": True,
            "evidence_state": EVIDENCE_MALFORMED,
        }

    # Collapse exact duplicates (same identity and same statement) without
    # inflating evidence; collisions (same identity, different statement) stay
    # conflicting.
    merged: dict[tuple, dict] = {}
    collisions: set[str] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            malformed = True
            continue
        identity = _usable_scalar_string(entry.get("identity"))
        statement = _usable_scalar_string(entry.get("statement"))
        if identity is None:
            identity = _usable_scalar_string(entry.get("id")) or "unknown"
        key = (identity, statement)
        if key in merged:
            previous = merged[key]
            previous["supporting_ids"] = sorted(
                set(previous["supporting_ids"])
                | set(_usable_string_items(entry.get("supporting_ids")))
            )
            previous["counterevidence_ids"] = sorted(
                set(previous["counterevidence_ids"])
                | set(_usable_string_items(entry.get("counterevidence_ids")))
            )
            continue
        for (existing_identity, existing_statement) in merged:
            if existing_identity == identity and existing_statement != statement:
                collisions.add(identity)
        merged[key] = {
            "identity": identity,
            "statement": statement or "unstated",
            "supporting_ids": sorted(
                set(_usable_string_items(entry.get("supporting_ids")))
            ),
            "counterevidence_ids": sorted(
                set(_usable_string_items(entry.get("counterevidence_ids")))
            ),
            "uncertainty": _finite_number(entry.get("uncertainty")),
            "scope": _usable_scalar_string(entry.get("scope")),
            "temporal": _usable_scalar_string(entry.get("temporal")),
        }

    ordered_keys = sorted(merged)
    records = [merged[key] for key in ordered_keys]

    # Conflict detection: a reference used by two different statements, or
    # supporting one hypothesis while contradicting another.
    support_by_source: dict[str, set[str]] = {}
    counter_by_source: dict[str, set[str]] = {}
    for record in records:
        identity = record["identity"]
        for source_id in record["supporting_ids"]:
            support_by_source.setdefault(source_id, set()).add(identity)
        for source_id in record["counterevidence_ids"]:
            counter_by_source.setdefault(source_id, set()).add(identity)

    conflicting_ids: set[str] = set()
    for source_id, supporting in support_by_source.items():
        if len(supporting) > 1:
            conflicting_ids.add(source_id)
        for identity in supporting:
            if identity in counter_by_source.get(source_id, ()):
                conflicting_ids.add(source_id)
    for source_id, countering in counter_by_source.items():
        if source_id in support_by_source:
            conflicting_ids.add(source_id)
        if len(countering) > 1:
            conflicting_ids.add(source_id)

    conflicting_ids = {source_id for source_id in conflicting_ids}

    supported = {source_id for record in records for source_id in record["supporting_ids"]}
    unresolved = bool(conflicting_ids) or any(
        not record["supporting_ids"] for record in records
    )
    insufficient_to_rank = any(not record["supporting_ids"] for record in records)

    # Relative strength: strictly more grounded support than every other
    # hypothesis with no conflicts on its own evidence.
    strengths: dict[str, int | None] = {
        record["identity"]: (
            len(record["supporting_ids"]) if record["supporting_ids"] else None
        )
        for record in records
    }
    max_strength = max((v for v in strengths.values() if v is not None), default=None)
    relative_strength: dict[str, str | None] = {}
    for identity, strength in strengths.items():
        if (
            strength is not None
            and max_strength is not None
            and strength == max_strength
            and sum(1 for v in strengths.values() if v == max_strength) == 1
            and not any(
                source_id in conflicting_ids for source_id in (strength and [])
            )
        ):
            # Only when the leading hypothesis has no conflicted evidence can
            # we mark it relatively stronger.
            record = next(r for r in records if r["identity"] == identity)
            if not any(source_id in conflicting_ids for source_id in record["supporting_ids"]):
                relative_strength[identity] = "stronger"
            else:
                relative_strength[identity] = None
        else:
            relative_strength[identity] = None

    hypotheses_out = []
    for record in records:
        hypotheses_out.append(
            {
                "identity": record["identity"],
                "statement": record["statement"],
                "supporting_ids": tuple(record["supporting_ids"]),
                "counterevidence_ids": tuple(record["counterevidence_ids"]),
                "uncertainty": record["uncertainty"],
                "scope": record["scope"],
                "temporal": record["temporal"],
                "status": LEVEL_HYPOTHESIS,
                "fact": False,
                "relative_strength": relative_strength[record["identity"]],
            }
        )

    return {
        "hypotheses": tuple(hypotheses_out),
        "supported_ids": tuple(sorted(supported)),
        "conflicting_ids": tuple(sorted(conflicting_ids)),
        "unresolved": unresolved,
        "winner_selected": False,
        "forced_conclusion": False,
        "insufficient_basis_to_rank": insufficient_to_rank,
        "evidence_state": (
            EVIDENCE_CONFLICTING
            if conflicting_ids
            else EVIDENCE_GROUNDED
            if supported
            else EVIDENCE_UNKNOWN
        ),
    }


def _collect_text(mapping: Mapping) -> list[str]:
    """Collect all scalar string values reachable from a mapping (including
    lists/tuples) for certainty-phrase scanning.  Never recurses into cycles
    (guarded by id tracking)."""
    texts: list[str] = []
    seen: set[int] = set()

    def visit(value: Any) -> None:
        marker = id(value)
        if marker in seen:
            return
        seen.add(marker)
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, Mapping):
            for item in value.values():
                visit(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(mapping)
    return texts


def no_forced_conclusion_policy(result: Any) -> dict:
    """Determine whether a structured result forces a conclusion.

    A result that is unresolved (or missing a conclusion) may complete
    successfully as long as no forbidden certainty phrasing is present.
    When the result is unresolved and forbidden phrasing appears, the result
    is flagged as a forced conclusion with the offending phrases listed.
    """
    if not isinstance(result, Mapping):
        return {
            "forced_conclusion": False,
            "valid_unresolved_completion": False,
            "unsupported_certainty": (),
            "unresolved": True,
            "evaluated": False,
        }
    unresolved = _boolean_true(result.get("unresolved"))
    if result.get("unresolved") is None and "conclusion" not in result:
        unresolved = True
    texts = _collect_text(result)
    lowered = " ".join(texts).lower()
    matched = tuple(
        phrase for phrase in FORCED_CONCLUSION_PHRASES if phrase in lowered
    )
    forced = bool(unresolved) and bool(matched)
    return {
        "forced_conclusion": forced,
        "valid_unresolved_completion": bool(unresolved) and not forced,
        "unsupported_certainty": matched,
        "unresolved": bool(unresolved),
        "evaluated": True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Task 5 helpers — ambivalence + belief/evidence separation
# ═══════════════════════════════════════════════════════════════════════════════

_AMBIVALENT_KINDS: frozenset[str] = frozenset(
    {"need", "emotion", "belief", "value", "desire"}
)

CONFLICT_AMBIVALENT = "ambivalent"
CONFLICT_CONFLICTING = "conflicting"
CONFLICT_UNRESOLVED = "unresolved"
CONFLICT_DISTINCT_CONTEXTS = "distinct_contexts"
CONFLICT_DISTINCT_TIMES = "distinct_times"
CONFLICT_NONE = "none"

_EVIDENCE_KINDS: frozenset[str] = frozenset(
    {"belief", "evidence", "counterevidence", "experience", "interpretation",
     "memory", "observation", "hypothesis"}
)


def evaluate_ambivalence(
    *,
    records: Any = (),
) -> dict:
    """Evaluate emotional/need/belief positions preserving genuine ambivalence.

    Simultaneous opposing positions in the same context and grounded time are
    ambivalence, never a forced resolution.  Positions that differ by context
    or by grounded time are preserved with their distinctions visible.
    Identical duplicates collapse (no double weighting).  Input order never
    changes the semantic result.  Outputs are JSON-safe.
    """
    raw, malformed = _normalize_collection(records, require_mapping_elements=True)
    if malformed:
        return {
            "ambivalence_present": False,
            "forced_resolution": False,
            "winner_selected": False,
            "positions": (),
            "duplicates_ignored": (),
            "context_distinctions": (),
            "temporal_distinctions": (),
            "conflict_state": CONFLICT_UNRESOLVED,
            "evidence_state": EVIDENCE_MALFORMED,
        }

    # Normalize and collapse exact duplicates (same identity + same statement
    # + same kind + same context + same temporal bucket).
    merged: dict[tuple, dict] = {}
    duplicates: list[str] = []
    order: list[tuple] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            malformed = True
            continue
        identity = _usable_scalar_string(entry.get("identity")) or "unknown"
        statement = _usable_scalar_string(entry.get("statement")) or "unstated"
        kind = _usable_scalar_string(entry.get("kind")) or "unknown"
        context = _usable_scalar_string(entry.get("context"))
        temporal = _usable_scalar_string(entry.get("temporal"))
        polarity = _finite_number(entry.get("polarity"))
        key = (identity, statement, kind, context, temporal)
        if key in merged:
            duplicates.append(identity)
            continue
        merged[key] = {
            "identity": identity,
            "statement": statement,
            "kind": kind,
            "context": context,
            "temporal": temporal,
            "polarity": polarity,
            "opposes": tuple(sorted(_usable_string_items(entry.get("opposes")))),
            "sources": tuple(sorted(_usable_string_items(entry.get("source")))),
        }
        order.append(key)

    records_out = [merged[key] for key in sorted(order)]

    # Opposition detection.
    context_distinctions: list[str] = []
    temporal_distinctions: list[str] = []
    ambivalent_ids: set[str] = set()
    by_context_time: dict[tuple, list[dict]] = {}
    for record in records_out:
        bucket = (record["context"], record["temporal"])
        by_context_time.setdefault(bucket, []).append(record)

    for bucket, members in by_context_time.items():
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                same_kind = left["kind"] == right["kind"]
                same_bucket = left["context"] == right["context"] and (
                    left["temporal"] == right["temporal"]
                )
                if not same_bucket:
                    continue
                if left["identity"] == right["identity"]:
                    continue
                opposing = False
                if same_kind and left["kind"] in _AMBIVALENT_KINDS:
                    left_polarity = left["polarity"]
                    right_polarity = right["polarity"]
                    if (
                        left_polarity is not None
                        and right_polarity is not None
                        and left_polarity != 0
                        and right_polarity != 0
                        and left_polarity == -right_polarity
                    ):
                        opposing = True
                if not opposing and (
                    left["identity"] in right["opposes"]
                    or right["identity"] in left["opposes"]
                ):
                    opposing = True
                if opposing:
                    ambivalent_ids.add(left["identity"])
                    ambivalent_ids.add(right["identity"])

    # Distinct contexts / times are preserved but are not same-time ambivalence.
    context_distinctions_set: set[str] = set()
    temporal_distinctions_set: set[str] = set()
    for index, left in enumerate(records_out):
        if left["identity"] in ambivalent_ids:
            continue
        for right in records_out[index + 1 :]:
            if right["identity"] in ambivalent_ids:
                continue
            if left["identity"] == right["identity"]:
                continue
            same_context = left["context"] == right["context"]
            same_temporal = left["temporal"] == right["temporal"]
            left_temporal_valid = bool(left["temporal"])
            right_temporal_valid = bool(right["temporal"])
            if not same_context:
                # different contexts: context distinction preserved
                context_distinctions_set.add(left["identity"])
                context_distinctions_set.add(right["identity"])
                if left_temporal_valid and right_temporal_valid and not same_temporal:
                    temporal_distinctions_set.add(left["identity"])
                    temporal_distinctions_set.add(right["identity"])
            elif same_context and (
                left_temporal_valid and right_temporal_valid and not same_temporal
            ):
                temporal_distinctions_set.add(left["identity"])
                temporal_distinctions_set.add(right["identity"])

    context_distinctions = sorted(context_distinctions_set)
    temporal_distinctions = sorted(temporal_distinctions_set)

    positions_out = []
    for record in records_out:
        positions_out.append(
            {
                "identity": record["identity"],
                "statement": record["statement"],
                "kind": record["kind"],
                "context": record["context"],
                "temporal": record["temporal"],
                "sources": record["sources"],
            }
        )

    if ambivalent_ids:
        conflict_state = CONFLICT_AMBIVALENT
        ambivalence_present = True
    elif temporal_distinctions and context_distinctions or temporal_distinctions:
        conflict_state = CONFLICT_DISTINCT_TIMES
        ambivalence_present = False
    elif context_distinctions:
        conflict_state = CONFLICT_DISTINCT_CONTEXTS
        ambivalence_present = False
    elif records_out:
        conflict_state = CONFLICT_NONE
        ambivalence_present = False
    else:
        conflict_state = CONFLICT_NONE
        ambivalence_present = False

    return {
        "ambivalence_present": ambivalence_present,
        "forced_resolution": False,
        "winner_selected": False,
        "positions": tuple(positions_out),
        "duplicates_ignored": tuple(duplicates),
        "context_distinctions": tuple(context_distinctions),
        "temporal_distinctions": tuple(temporal_distinctions),
        "conflict_state": conflict_state,
        "evidence_state": (
            EVIDENCE_CONFLICTING
            if ambivalence_present
            else EVIDENCE_GROUNDED
            if records_out
            else EVIDENCE_ABSENT
        ),
    }


def _normalize_evidence_kind(value: Any) -> str:
    kind = _usable_scalar_string(value)
    if kind is not None and kind in _EVIDENCE_KINDS:
        return kind
    return "unknown"


def classify_belief_evidence(
    *,
    records: Any = (),
) -> dict:
    """Classify records into the five canonical epistemic dimensions.

    belief / evidence / counterevidence / experience / interpretation stay
    separate.  A caller ``fact``/``observation``/``confirmed`` label never
    promotes a record automatically: experience stays experience, an
    interpretation stays an interpretation, a memory entry stays provenance.
    Duplicates collapse without inflating evidence.  Conflicting evidence
    stays conflicting.  Malformed records fail closed and never raise.
    Outputs are JSON-safe.
    """
    raw, malformed = _normalize_collection(records, require_mapping_elements=True)
    projections = {
        "beliefs": [],
        "evidence": [],
        "counterevidence": [],
        "experiences": [],
        "interpretations": [],
        "memories": [],
        "observations": [],
        "hypotheses": [],
        "facts": [],
        "beliefs_as_facts": [],
    }
    promotions_blocked: list[str] = []
    malformed_records: list[dict] = []
    duplicates_ignored: list[str] = []
    conflict_state = CONFLICT_NONE

    seen_keys: set[tuple] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            malformed = True
            malformed_records.append({"record": entry, "reason": "not_a_mapping"})
            continue
        identity = _usable_scalar_string(entry.get("identity")) or "unknown"
        statement = _usable_scalar_string(entry.get("statement")) or "unstated"
        kind = _normalize_evidence_kind(entry.get("kind"))
        if kind == "unknown":
            malformed = True
            malformed_records.append({"record": identity, "reason": "unknown_kind"})
            continue
        source = _usable_reference(entry.get("source")) or _usable_scalar_string(
            entry.get("source_id")
        )
        value = entry.get("value")

        # Duplicate detection: identical content + kind + source collapse
        # (distinct identities do not inflate evidence).  Conflicts are
        # content differences, which keep the records separate.
        key = (statement, kind, source)
        if key in seen_keys:
            duplicates_ignored.append(identity)
            continue
        seen_keys.add(key)

        labeled_fact = _boolean_true(entry.get("fact")) or _boolean_true(
            entry.get("confirmed")
        ) or _boolean_true(entry.get("official"))
        labeled_observation = _boolean_true(entry.get("observation"))
        inferred = _boolean_true(entry.get("inferred"))
        uncertain = _boolean_true(entry.get("uncertain"))
        contradicted = _boolean_true(entry.get("contradicted"))

        target = kind
        if target in ("memory", "observation", "hypothesis"):
            target = "memories" if kind == "memory" else (
                "observations" if kind == "observation" else "hypotheses"
            )
        projection = {
            "identity": identity,
            "statement": statement,
            "kind": kind,
            "source": source,
            "value": value,
        }
        if kind == "belief":
            if labeled_fact:
                # a belief can never become a user fact through a caller label
                promotions_blocked.append(identity)
                projections["beliefs"].append(projection)
            else:
                projection["status"] = (
                    "contradicted"
                    if contradicted
                    else "uncertain"
                    if uncertain
                    else "inferred"
                    if inferred
                    else "explicit"
                )
                projections["beliefs"].append(projection)
            continue

        if kind in ("evidence", "counterevidence"):
            projections[("counterevidence" if kind == "counterevidence" else "evidence")].append(projection)
            continue
        if kind == "experience":
            if labeled_fact:
                # experience alone cannot become an external fact
                promotions_blocked.append(identity)
            projections["experiences"].append(projection)
            continue
        if kind == "interpretation":
            if labeled_observation or labeled_fact:
                # interpretation cannot become an observation or fact
                promotions_blocked.append(identity)
            projections["interpretations"].append(projection)
            continue
        if kind == "memory":
            if labeled_fact:
                # memory_entry is provenance, never a current fact
                promotions_blocked.append(identity)
            projections["memories"].append(projection)
            continue
        projections[target].append(projection)

    if malformed:
        conflict_state = CONFLICT_UNRESOLVED
    elif len(projections["evidence"]) > 1:
        # conflicting evidence on the same source/attribute stays conflicting
        if any(
            left.get("value") is not None
            and right.get("value") is not None
            and left.get("value") != right.get("value")
            for index, left in enumerate(projections["evidence"])
            for right in projections["evidence"][index + 1 :]
        ) or any(
            left.get("statement") != right.get("statement")
            for index, left in enumerate(projections["evidence"])
            for right in projections["evidence"][index + 1 :]
        ):
            conflict_state = CONFLICT_CONFLICTING
    elif projections["counterevidence"] and projections["evidence"]:
        conflict_state = CONFLICT_CONFLICTING

    return {
        "beliefs": tuple(projections["beliefs"]),
        "evidence": tuple(projections["evidence"]),
        "counterevidence": tuple(projections["counterevidence"]),
        "experiences": tuple(projections["experiences"]),
        "interpretations": tuple(projections["interpretations"]),
        "memories": tuple(projections["memories"]),
        "observations": tuple(projections["observations"]),
        "hypotheses": tuple(projections["hypotheses"]),
        "facts": tuple(projections["facts"]),
        "beliefs_as_facts": tuple(projections["beliefs_as_facts"]),
        "promotions_blocked": tuple(sorted(set(promotions_blocked))),
        "promotion_applied": False,
        "type_promotion": bool(promotions_blocked),
        "malformed_records": tuple(malformed_records),
        "duplicates_ignored": tuple(duplicates_ignored),
        "unresolved": bool(malformed) or conflict_state == CONFLICT_UNRESOLVED
        or conflict_state == CONFLICT_CONFLICTING,
        "conflict_state": conflict_state,
        "evidence_state": (
            EVIDENCE_MALFORMED
            if malformed
            else EVIDENCE_CONFLICTING
            if conflict_state == CONFLICT_CONFLICTING
            or conflict_state == CONFLICT_UNRESOLVED
            else EVIDENCE_GROUNDED
            if any(projections.values())
            else EVIDENCE_ABSENT
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Task 6 helpers — open questions + temporal evolution
# ═══════════════════════════════════════════════════════════════════════════════

OPEN_REASON_EVIDENCE_MISSING = "evidence_missing"
OPEN_REASON_EVIDENCE_CONFLICTING = "evidence_conflicting"
OPEN_REASON_PLAUSIBLE_HYPOTHESIS_ONLY = "plausible_hypothesis_only"
OPEN_REASON_FUTURE_BEHAVIOR_UNKNOWABLE = "future_behavior_unknowable"
OPEN_REASON_MOTIVE_NOT_STATED = "motive_not_stated"
OPEN_REASON_TIMELINE_INCOMPLETE = "timeline_incomplete"
OPEN_REASON_SOURCE_BASIS_UNGROUNDED = "source_basis_ungrounded"
OPEN_REASON_MALFORMED = "malformed"


def evaluate_open_questions(
    *,
    questions: Any = (),
) -> dict:
    """Evaluate which questions remain open and why.

    A question remains open when the evidence is missing/conflicting/ungrounded,
    only a plausible hypothesis exists, future behavior is unknowable, the
    motive was not stated, or the timeline is incomplete.  A plausible
    hypothesis alone never closes a question and no answer is ever invented.
    Input order never changes the semantic result.  Outputs are JSON-safe.
    """
    raw, malformed = _normalize_collection(questions, require_mapping_elements=True)
    questions_out: list[dict] = []
    unresolved_count = 0
    answered_count = 0
    invented: list[str] = []

    for entry in raw:
        if not isinstance(entry, Mapping):
            malformed = True
            continue
        identity = _usable_scalar_string(entry.get("identity")) or "unknown"
        question = _usable_scalar_string(entry.get("question")) or ""
        evidence = _usable_scalar_string(entry.get("evidence"))
        plausible = _boolean_true(entry.get("plausible_hypothesis"))
        future_behavior = _boolean_true(entry.get("future_behavior"))
        motive_stated = entry.get("motive_stated")
        timeline_complete = entry.get("timeline_complete")
        source_grounded = entry.get("source_grounded")
        answer = _usable_scalar_string(entry.get("answer"))

        reasons: list[str] = []
        if evidence in (None, "absent", "unknown", "temporally_ambiguous"):
            reasons.append(OPEN_REASON_EVIDENCE_MISSING)
        elif evidence == "conflicting":
            reasons.append(OPEN_REASON_EVIDENCE_CONFLICTING)
        elif evidence in ("ungrounded", "unsupported"):
            reasons.append(OPEN_REASON_SOURCE_BASIS_UNGROUNDED)
        if plausible and not evidence in ("grounded", "conflicting"):
            reasons.append(OPEN_REASON_PLAUSIBLE_HYPOTHESIS_ONLY)
        if future_behavior:
            reasons.append(OPEN_REASON_FUTURE_BEHAVIOR_UNKNOWABLE)
        if motive_stated is False:
            reasons.append(OPEN_REASON_MOTIVE_NOT_STATED)
        if timeline_complete is False:
            reasons.append(OPEN_REASON_TIMELINE_INCOMPLETE)
        if source_grounded is False:
            reasons.append(OPEN_REASON_SOURCE_BASIS_UNGROUNDED)
        if evidence == "malformed":
            reasons.append(OPEN_REASON_MALFORMED)

        is_open = answer is None and bool(reasons)
        if is_open:
            unresolved_count += 1
            status = "open"
        else:
            answered_count += 1
            status = "answered"
        questions_out.append(
            {
                "identity": identity,
                "question": question,
                "status": status,
                "reasons": tuple(dict.fromkeys(reasons)),
                "plausible_hypothesis": plausible,
                "answered": answer is not None,
                "answer_provided": answer is not None,
            }
        )

    if malformed:
        unresolved_count = max(unresolved_count, 1)
        questions_out.append(
            {
                "identity": "malformed",
                "question": "",
                "status": "open",
                "reasons": (OPEN_REASON_MALFORMED,),
                "plausible_hypothesis": False,
                "answered": False,
                "answer_provided": False,
            }
        )

    return {
        "questions": tuple(
            sorted(questions_out, key=lambda item: item["identity"])
        ),
        "unresolved_count": unresolved_count,
        "answered_count": answered_count,
        "invented_answers": tuple(invented),
        "open_question": unresolved_count > 0,
        "evidence_state": EVIDENCE_MALFORMED if malformed else EVIDENCE_GROUNDED,
    }


def compare_reflection_versions(
    *,
    versions: Any = (),
) -> dict:
    """Compare versions of an idea/belief/value/hypothesis over time.

    Directional evolution requires grounded chronology: valid, distinct
    timestamps.  Equal normalized timestamps (including different textual
    representations of the same instant, and identical date-only values) never
    create before/after.  Malformed or missing dates never establish
    direction, and input order never supplies chronology.  Rephrased wording
    is not a substantive change; repetition is not persistence; a newer
    ungrounded record is not current truth.  Outputs are JSON-safe.
    """
    raw, malformed = _normalize_collection(versions, require_mapping_elements=True)
    if malformed:
        return {
            "chronology_state": CHRONOLOGY_MALFORMED,
            "temporally_ordered": False,
            "versions": (),
            "changes": (),
            "input_order_not_chronology": True,
            "equal_timestamps_no_evolution": False,
            "malformed_datetime_ignored_for_direction": True,
            "newest_is_current_truth": False,
        }

    normalized: list[dict] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            malformed = True
            continue
        version_id = _usable_scalar_string(entry.get("version_id")) or "unknown"
        identity = _usable_scalar_string(entry.get("identity")) or "unknown"
        observed_at = entry.get("observed_at")
        content = _usable_scalar_string(entry.get("content")) or ""
        source = _usable_scalar_string(entry.get("source"))
        grounded = entry.get("grounded")
        normalized.append(
            {
                "version_id": version_id,
                "identity": identity,
                "observed_at": observed_at if isinstance(observed_at, str) else None,
                "observed_scalar": _normalize_chronology(observed_at),
                "content": content,
                "source": source,
                "grounded": grounded,
                "contradiction": _boolean_true(entry.get("contradiction")),
                "uncertain": _boolean_true(entry.get("uncertain")),
            }
        )

    if malformed or not normalized:
        return {
            "chronology_state": CHRONOLOGY_MALFORMED if malformed else CHRONOLOGY_EMPTY,
            "temporally_ordered": False,
            "versions": tuple(
                {
                    "version_id": item["version_id"],
                    "identity": item["identity"],
                    "observed_at": item["observed_at"],
                    "state": "unknown",
                }
                for item in normalized
            ),
            "changes": (),
            "input_order_not_chronology": True,
            "equal_timestamps_no_evolution": False,
            "malformed_datetime_ignored_for_direction": bool(malformed),
            "newest_is_current_truth": False,
        }

    scalars = [item["observed_scalar"] for item in normalized]
    absent = any(item["observed_at"] is None for item in normalized)
    malformed_rows = any(
        item["observed_at"] is not None and scalar is None
        for item, scalar in zip(normalized, scalars)
    )
    if absent:
        return {
            "chronology_state": CHRONOLOGY_UNKNOWN,
            "temporally_ordered": False,
            "versions": tuple(
                {
                    "version_id": item["version_id"],
                    "identity": item["identity"],
                    "observed_at": item["observed_at"],
                    "state": "unknown",
                }
                for item in normalized
            ),
            "changes": (),
            "input_order_not_chronology": True,
            "equal_timestamps_no_evolution": False,
            "malformed_datetime_ignored_for_direction": False,
            "newest_is_current_truth": False,
        }
    if malformed_rows:
        return {
            "chronology_state": CHRONOLOGY_MALFORMED,
            "temporally_ordered": False,
            "versions": tuple(
                {
                    "version_id": item["version_id"],
                    "identity": item["identity"],
                    "observed_at": item["observed_at"],
                    "state": "malformed",
                }
                for item in normalized
            ),
            "changes": (),
            "input_order_not_chronology": True,
            "equal_timestamps_no_evolution": False,
            "malformed_datetime_ignored_for_direction": True,
            "newest_is_current_truth": False,
        }

    distinct = len(set(scalars)) > 1
    if not distinct:
        return {
            "chronology_state": CHRONOLOGY_EQUAL,
            "temporally_ordered": False,
            "versions": tuple(
                {
                    "version_id": item["version_id"],
                    "identity": item["identity"],
                    "observed_at": item["observed_at"],
                    "state": "simultaneous",
                }
                for item in normalized
            ),
            "changes": (),
            "input_order_not_chronology": True,
            "equal_timestamps_no_evolution": True,
            "malformed_datetime_ignored_for_direction": False,
            "newest_is_current_truth": False,
        }

    # Grounded chronology exists: order by normalized timestamp deterministically
    # (stable tie-break by version_id for equal instants).
    ordered = sorted(
        normalized, key=lambda item: (item["observed_scalar"], item["version_id"])
    )
    changes: list[dict] = []
    for index in range(1, len(ordered)):
        left = ordered[index - 1]
        right = ordered[index]
        left_tokens = frozenset(
            token for token in left["content"].lower().split() if token
        )
        right_tokens = frozenset(
            token for token in right["content"].lower().split() if token
        )
        same_tokens = left_tokens == right_tokens and bool(left_tokens)
        # Rephrase detection: high symmetric token overlap without negation.
        overlap = 0.0
        if left_tokens and right_tokens:
            larger = max(len(left_tokens), len(right_tokens))
            smaller = min(len(left_tokens), len(right_tokens))
            if larger > 0:
                overlap = len(left_tokens & right_tokens) / larger
            ratio_ok = smaller == 0 or larger / smaller <= 2.0
            rephrase_candidate = overlap >= 0.5 and ratio_ok
        else:
            rephrase_candidate = False
        _NEGATION_TOKENS = frozenset(
            {"no", "not", "never", "don't", "dont", "doesn't", "doesnt",
             "no longer", "stop", "quit", "refuse", "cannot", "can't"}
        )
        left_negated = bool(left_tokens & _NEGATION_TOKENS) or " no " in f" {left['content'].lower()} "
        right_negated = bool(right_tokens & _NEGATION_TOKENS) or " no " in f" {right['content'].lower()} "
        negation_present = left_negated or right_negated
        rephrased = (same_tokens or rephrase_candidate) and not negation_present
        changed = not (same_tokens or rephrase_candidate) or negation_present
        contradiction = left["contradiction"] or right["contradiction"]
        uncertain = left["uncertain"] or right["uncertain"]
        changes.append(
            {
                "identity": left["identity"],
                "from_version_id": left["version_id"],
                "to_version_id": right["version_id"],
                "changed": changed,
                "rephrased": rephrased,
                "stable": not changed,
                "uncertain": uncertain,
                "contradiction": contradiction,
                "persistence_established": False,
            }
        )

    # Newest-grounded check: the newest record is current truth only when it is
    # grounded; Reflection never claims current truth from an ungrounded record.
    newest = ordered[-1]
    newest_is_current_truth = bool(newest["grounded"] is True)

    return {
        "chronology_state": CHRONOLOGY_ORDERED,
        "temporally_ordered": True,
        "versions": tuple(
            {
                "version_id": item["version_id"],
                "identity": item["identity"],
                "observed_at": item["observed_at"],
                "state": "ordered",
            }
            for item in ordered
        ),
        "changes": tuple(changes),
        "input_order_not_chronology": True,
        "equal_timestamps_no_evolution": False,
        "malformed_datetime_ignored_for_direction": False,
        "newest_is_current_truth": newest_is_current_truth,
    }


# ── Interest source kinds ───────────────────────────────────────────────────────
# Model/memory summaries and inferences are NEVER independent source evidence
# for interest mapping (spec §16, §28): they merely re-narrate earlier user
# evidence and cannot corroborate it.

_NON_INDEPENDENT_SOURCE_KINDS: frozenset[str] = frozenset(
    {
        "model_summary",
        "memory_summary",
        "model_inference",
        "inferred",
        "memory",
        "summary",
        "system",
        "llm",
    }
)

_GROUNDED_SOURCE_KINDS: frozenset[str] = frozenset(
    {
        "user_statement",
        "activity",
        "discussion",
        "goal",
        "reading_history",
        "practice",
        "user_message",
        "conversation",
        "note",
        "journal_entry",
        "life_event",
        "relationship_event",
        "explicit",
    }
)


def map_interests(
    *,
    records: Any = (),
) -> dict:
    """Map interest candidates grounded in source-backed user evidence.

    A topic mention alone is a candidate, never a confirmed/committed
    interest.  Grounded evidence counts distinct user-anchored sources per
    interest; duplicate source copies never inflate the count, and model or
    memory summaries/inferences are never independent corroboration.
    Contradictory evidence keeps the candidate uncertain.  Interest is never
    converted into identity or commitment.  Input order never changes the
    semantic result.  Outputs are JSON-safe.
    """
    raw, malformed = _normalize_collection(records, require_mapping_elements=True)
    malformed_records: list[Any] = []
    grouped: dict[str, list[dict]] = {}
    duplicates: list[str] = []

    for entry in raw:
        if not isinstance(entry, Mapping):
            malformed = True
            malformed_records.append(entry)
            continue
        raw_interest = entry.get("interest")
        if isinstance(raw_interest, str) and raw_interest.strip():
            interest = raw_interest.strip().lower()
        else:
            malformed = True
            malformed_records.append(entry)
            continue
        source = _usable_scalar_string(entry.get("source")) or _usable_scalar_string(
            entry.get("source_id")
        )
        source_kind = _usable_scalar_string(entry.get("source_kind")) or "user_statement"
        recording = _usable_scalar_string(entry.get("recording")) or _usable_scalar_string(
            entry.get("statement")
        )
        key = (source, source_kind, recording)
        records_for_interest = grouped.setdefault(interest, [])
        if any(existing["_key"] == key for existing in records_for_interest):
            duplicates.append(source or interest)
            continue
        records_for_interest.append(
            {
                "_key": key,
                "interest": interest,
                "source": source,
                "source_kind": source_kind,
                "recording": recording,
                "explicit": _boolean_true(entry.get("explicit")),
                "activity": _boolean_true(entry.get("activity")),
                "mention": _boolean_true(entry.get("mention")),
                "context": _usable_scalar_string(entry.get("context")),
                "observed_at": entry.get("observed_at"),
                "contradictory": _boolean_true(entry.get("contradictory")),
            }
        )

    candidates: list[dict] = []
    contradictions: list[str] = []
    model_source_total = 0
    for interest in sorted(grouped):
        records_for_interest = grouped[interest]
        grounded_sources: set[str] = set()
        counter_sources: list[str] = []
        model_sources = 0
        mention_count = 0
        time_span = None
        contexts: list[str] = []
        for record in records_for_interest:
            mention_count += 1
            context = record["context"]
            if context and context not in contexts:
                contexts.append(context)
            if record["source_kind"] in _NON_INDEPENDENT_SOURCE_KINDS:
                model_sources += 1
                model_source_total += 1
                continue
            if record["contradictory"]:
                if record["source"] and record["source"] not in counter_sources:
                    counter_sources.append(record["source"])
                continue
            if record["source"]:
                grounded_sources.add(record["source"])
            # time span: earliest..latest observed_at when both are usable
            observed = record["observed_at"]
            if isinstance(observed, str) and observed.strip():
                scalar = _normalize_chronology(observed)
                if scalar is not None:
                    if time_span is None:
                        time_span = [scalar, scalar]
                    else:
                        time_span[0] = min(time_span[0], scalar)
                        time_span[1] = max(time_span[1], scalar)

        grounded_count = len(grounded_sources)
        independent_grounded = grounded_count
        time_span_out = None
        if time_span is not None:
            time_span_out = {
                "earliest": format_timestamp(time_span[0]),
                "latest": format_timestamp(time_span[1]),
            }
        candidates.append(
            {
                "interest": interest,
                "sources": tuple(sorted(grounded_sources)),
                "grounded_evidence_count": grounded_count,
                "independent_grounded_count": independent_grounded,
                "model_source_count": model_sources,
                "mention_count": mention_count,
                "time_span": time_span_out,
                "recency": time_span_out,
                "context": tuple(contexts) if contexts else None,
                "counterevidence": tuple(counter_sources),
                "uncertainty": (
                    mention_count <= 1 or grounded_count == 0 or bool(counter_sources)
                    or malformed
                ),
                "persistent_confirmed": False,
                "identity_claim": False,
                "commitment": False,
                "relative_strength": None,
            }
        )
        if counter_sources:
            contradictions.append(interest)

    # Relative strength: strictly more grounded evidence than every other
    # candidate with grounded evidence, with no contradictions.
    max_grounded = max(
        (c["grounded_evidence_count"] for c in candidates if c["grounded_evidence_count"] > 0),
        default=None,
    )
    strong_candidates = [
        c["interest"]
        for c in candidates
        if c["grounded_evidence_count"] == max_grounded
        and max_grounded is not None
        and not c["counterevidence"]
    ]
    if len(strong_candidates) == 1:
        for candidate in candidates:
            if candidate["interest"] in strong_candidates:
                candidate["relative_strength"] = "stronger"

    return {
        "interest_candidates": tuple(candidates),
        "duplicates_ignored": tuple(duplicates),
        "malformed_records": tuple(malformed_records),
        "model_inference_not_source": True,
        "persistent_confirmed": False,
        "contradictions": tuple(contradictions),
        "evidence_state": EVIDENCE_GROUNDED if candidates else EVIDENCE_ABSENT,
    }


def format_timestamp(epoch: float) -> str:
    """Format a UTC epoch scalar as an ISO string (public/serialization-safe)."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


# ═══════════════════════════════════════════════════════════════════════════════
# Task 8 helpers — confirmed persistence + memory boundary
# ═══════════════════════════════════════════════════════════════════════════════

PERSISTENCE_CANDIDATE = "candidate"
PERSISTENCE_PENDING_CONFIRMATION = "pending_confirmation"
PERSISTENCE_CONFIRMED = "confirmed"
PERSISTENCE_REJECTED = "rejected"


def authorizes_confirmation(value: Any) -> bool:
    """Only the literal boolean ``True`` authorizes a confirmation field.

    Strings (``"true"``), numerics (``1``, ``0``), collections (``[]``,
    ``{}``), ``None`` and arbitrary objects never authorize.  This is the
    semantic-memory persistence gate required by the frozen spec (§17, §22).
    """
    return value is True


def evaluate_persistence_basis(record: Any) -> dict:
    """Evaluate the evidence basis of a candidate persistent pattern.

    Repetition, model inference, memory summaries, and single-conversation
    repetition never count as independent grounded corroboration.  Duplicate
    memory summaries are ignored.  The result never asserts persistence on its
    own: it only reports how strong the *basis* is.  Output is JSON-safe.
    """
    if not isinstance(record, Mapping):
        return {
            "pattern": None,
            "independent_grounded_sources": 0,
            "duplicate_summaries_ignored": 0,
            "model_inference_count": 0,
            "repetition_count": 0,
            "single_conversation": False,
            "basis_sufficient": False,
            "malformed": True,
        }
    pattern = _usable_scalar_string(record.get("pattern")) or _usable_scalar_string(
        record.get("identity")
    )
    sources = tuple(
        sorted(set(_usable_string_items(record.get("sources"))))
    )
    repetition = _finite_number(record.get("repetition_count")) or 0
    model_inferred = _boolean_true(record.get("model_inferred"))
    duplicate_summaries = tuple(
        sorted(set(_usable_string_items(record.get("duplicate_summaries"))))
    )
    single_conversation = _boolean_true(record.get("single_conversation"))

    unique_sources = len({source for source in sources} )
    summary_overlap = len(set(sources) & set(duplicate_summaries))
    independent_grounded = max(0, unique_sources - summary_overlap)
    model_inference_count = 1 if model_inferred else 0
    basis_sufficient = independent_grounded >= 1 and not single_conversation and not model_inferred
    return {
        "pattern": pattern,
        "sources": sources,
        "independent_grounded_sources": independent_grounded,
        "duplicate_summaries_ignored": len(duplicate_summaries),
        "model_inference_count": model_inference_count,
        "repetition_count": int(repetition),
        "single_conversation": single_conversation,
        "basis_sufficient": basis_sufficient,
        "malformed": False,
    }


def classify_persistence(
    record: Any,
    *,
    confirmation: Any = None,
) -> dict:
    """Classify the persistence state of a candidate pattern.

    A candidate pattern is persistent only when a valid shared confirmation
    authorizes it: the literal boolean ``True``.  Repetition, model inference,
    memory summaries, and single-conversation repetition are explicit reasons
    that do NOT confirm persistence.  Malformed/nonliteral authorization fails
    closed (never widens persistence).  Output is JSON-safe.
    """
    basis = evaluate_persistence_basis(record)
    malformed = basis["malformed"]
    authorization_accepted = authorizes_confirmation(confirmation)
    authorization_malformed = confirmation is not None and not isinstance(confirmation, bool)

    excluded: list[str] = []
    if basis["model_inference_count"] > 0:
        excluded.append("model_inference")
    if basis["single_conversation"]:
        excluded.append("single_conversation")
    if basis["duplicate_summaries_ignored"] > 0:
        excluded.append("duplicate_summaries")
    if basis["independent_grounded_sources"] == 0 and basis["sources"]:
        excluded.append("no_independent_grounded_sources")

    if authorization_accepted:
        if basis["basis_sufficient"]:
            state = PERSISTENCE_CONFIRMED
            confirmed = True
        else:
            state = PERSISTENCE_PENDING_CONFIRMATION
            confirmed = False
    elif confirmation is False:
        state = PERSISTENCE_REJECTED
        confirmed = False
    else:
        state = PERSISTENCE_CANDIDATE
        confirmed = False

    return {
        "persistence_state": state,
        "confirmed": confirmed,
        "eligible_for_confirmation": authorization_accepted and not malformed,
        "authorization_accepted": authorization_accepted,
        "authorization_malformed": authorization_malformed or malformed,
        "excluded_reasons": tuple(excluded),
        "basis_sufficient": basis["basis_sufficient"],
        "pattern": basis["pattern"],
        "repetition_count": basis["repetition_count"],
        "malformed": malformed,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Shared rule builders
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
        domain_id="domain:reflection",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Conservative reflection rule for {rule_id}.",
        metadata={"phase": "10.24"},
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
class PreserveAmbivalenceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if "records" not in context.metadata:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No ambivalence records supplied.",
            )
        record = evaluate_ambivalence(
            records=context.metadata.get("records", ()),
        )
        finding = ReasoningFinding(
            code="AMBIVALENCE_PRESERVED",
            message=(
                "Simultaneous opposing states are preserved as ambivalence; "
                "no state was forced into a single true answer."
                if record["ambivalence_present"]
                else "No same-context/time opposition was detected; positions "
                "are preserved with their context/time distinctions."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "ambivalence_present": record["ambivalence_present"],
                "forced_resolution": record["forced_resolution"],
                "winner_selected": record["winner_selected"],
                "positions": record["positions"],
                "context_distinctions": record["context_distinctions"],
                "temporal_distinctions": record["temporal_distinctions"],
                "conflict_state": record["conflict_state"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="AMBIVALENCE_PRESERVED",
            message="Ambivalence preserved without forced resolution.",
        )


@dataclass(frozen=True, slots=True)
class BeliefEvidenceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if "records" not in context.metadata:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No belief/evidence records supplied.",
            )
        record = classify_belief_evidence(
            records=context.metadata.get("records", ()),
        )
        finding = ReasoningFinding(
            code="BELIEF_EVIDENCE_SEPARATION",
            message=(
                "Belief, evidence, counterevidence, experience and "
                "interpretation are kept separate; no type promotion occurred."
            ),
            severity=(
                ReasoningSeverity.WARNING
                if record["type_promotion"]
                else ReasoningSeverity.INFO
            ),
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "beliefs": record["beliefs"],
                "evidence": record["evidence"],
                "counterevidence": record["counterevidence"],
                "experiences": record["experiences"],
                "interpretations": record["interpretations"],
                "memories": record["memories"],
                "observations": record["observations"],
                "facts": record["facts"],
                "promotions_blocked": record["promotions_blocked"],
                "type_promotion": record["type_promotion"],
                "promotion_applied": record["promotion_applied"],
                "unresolved": record["unresolved"],
                "conflict_state": record["conflict_state"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="BELIEF_EVIDENCE_SEPARATED",
            message="Epistemic dimensions preserved without promotion.",
        )


@dataclass(frozen=True, slots=True)
class OpenQuestionRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if "questions" not in context.metadata:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No questions supplied.",
            )
        record = evaluate_open_questions(
            questions=context.metadata.get("questions", ()),
        )
        finding = ReasoningFinding(
            code="OPEN_QUESTION_RETAINED",
            message=(
                f"{record['unresolved_count']} question(s) remain open with "
                "explicit reasons; no answer was invented."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "open_question": record["open_question"],
                "unresolved_count": record["unresolved_count"],
                "answered_count": record["answered_count"],
                "questions": record["questions"],
                "invented_answers": record["invented_answers"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="OPEN_QUESTION_PRESERVED",
            message="Open questions preserved without invented answers.",
        )


@dataclass(frozen=True, slots=True)
class ReflectionTemporalEvolutionRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if "versions" not in context.metadata:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No versions supplied.",
            )
        record = compare_reflection_versions(
            versions=context.metadata.get("versions", ()),
        )
        finding = ReasoningFinding(
            code="TEMPORAL_EVOLUTION",
            message=(
                "Versions compare with grounded chronology; directional "
                "evolution is established."
                if record["temporally_ordered"]
                else "Versions cannot be directionally ordered; chronology is "
                f"{record['chronology_state']}."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "chronology_state": record["chronology_state"],
                "temporally_ordered": record["temporally_ordered"],
                "changes": record["changes"],
                "input_order_not_chronology": record["input_order_not_chronology"],
                "equal_timestamps_no_evolution": record["equal_timestamps_no_evolution"],
                "malformed_datetime_ignored_for_direction": record[
                    "malformed_datetime_ignored_for_direction"
                ],
                "newest_is_current_truth": record["newest_is_current_truth"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="TEMPORAL_EVOLUTION_EVALUATED",
            message="Temporal evolution grounded in valid chronology.",
        )


@dataclass(frozen=True, slots=True)
class MultipleHypothesesRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if "hypotheses" not in context.metadata:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No hypotheses supplied.",
            )
        record = evaluate_hypotheses(
            hypotheses=context.metadata.get("hypotheses", ()),
        )
        finding = ReasoningFinding(
            code="MULTIPLE_HYPOTHESES",
            message=(
                "Multiple hypotheses retained with explicit uncertainty and "
                "counterevidence; no arbitrary winner was selected."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "hypothesis_count": len(record["hypotheses"]),
                "hypotheses": record["hypotheses"],
                "supported_ids": record["supported_ids"],
                "conflicting_ids": record["conflicting_ids"],
                "unresolved": record["unresolved"],
                "winner_selected": record["winner_selected"],
                "forced_conclusion": record["forced_conclusion"],
                "insufficient_basis_to_rank": record["insufficient_basis_to_rank"],
                "evidence_state": record["evidence_state"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="MULTIPLE_HYPOTHESES_PRESERVED",
            message="Multiple prudent hypotheses preserved.",
        )


@dataclass(frozen=True, slots=True)
class NoForcedConclusionRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if "result" not in context.metadata:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No structured result supplied.",
            )
        record = no_forced_conclusion_policy(context.metadata.get("result"))
        finding = ReasoningFinding(
            code="NO_FORCED_CONCLUSION",
            message=(
                "The reflection completes without a forced conclusion; open "
                "questions and uncertainty remain visible."
                if record["valid_unresolved_completion"]
                else "The result contains unsupported certainty phrasing while "
                "remaining unresolved; it must not be presented as a conclusion."
            ),
            severity=(
                ReasoningSeverity.INFO
                if not record["forced_conclusion"]
                else ReasoningSeverity.WARNING
            ),
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={
                "forced_conclusion": record["forced_conclusion"],
                "valid_unresolved_completion": record["valid_unresolved_completion"],
                "unsupported_certainty": record["unsupported_certainty"],
                "unresolved": record["unresolved"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="NO_FORCED_CONCLUSION_PRESERVED",
            message="No conclusion is forced beyond the grounded basis.",
        )


def build_reflection_rules() -> tuple[Any, ...]:
    """Build the six Reflection Domain rules deterministically in canonical order."""
    by_id = {
        "reflection.belief_evidence": BeliefEvidenceRule(
            definition=_definition(
                "reflection.belief_evidence",
                "BeliefEvidenceRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                730,
            )
        ),
        "reflection.multiple_hypotheses": MultipleHypothesesRule(
            definition=_definition(
                "reflection.multiple_hypotheses",
                "MultipleHypothesesRule",
                ReasoningRuleCategory.INFERENCE.value,
                710,
            )
        ),
        "reflection.no_forced_conclusion": NoForcedConclusionRule(
            definition=_definition(
                "reflection.no_forced_conclusion",
                "NoForcedConclusionRule",
                ReasoningRuleCategory.SAFETY.value,
                780,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "reflection.open_question": OpenQuestionRule(
            definition=_definition(
                "reflection.open_question",
                "OpenQuestionRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                740,
            )
        ),
        "reflection.preserve_ambivalence": PreserveAmbivalenceRule(
            definition=_definition(
                "reflection.preserve_ambivalence",
                "PreserveAmbivalenceRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                720,
            )
        ),
        "reflection.temporal_evolution": ReflectionTemporalEvolutionRule(
            definition=_definition(
                "reflection.temporal_evolution",
                "ReflectionTemporalEvolutionRule",
                ReasoningRuleCategory.TEMPORALITY.value,
                750,
            )
        ),
    }
    built = tuple(by_id[rule_id] for rule_id in REFLECTION_RULE_IDS)
    if any(rule is None for rule in built):
        missing = tuple(
            rule_id for rule_id in REFLECTION_RULE_IDS if by_id[rule_id] is None
        )
        raise RuntimeError(f"Reflection rules not yet implemented: {missing}")
    return built


__all__ = [
    "CHRONOLOGY_EQUAL",
    "CHRONOLOGY_MALFORMED",
    "CHRONOLOGY_ORDERED",
    "CHRONOLOGY_UNKNOWN",
    "CONFLICT_AMBIVALENT",
    "CONFLICT_DISTINCT_CONTEXTS",
    "CONFLICT_DISTINCT_TIMES",
    "CONFLICT_NONE",
    "CONFLICT_UNRESOLVED",
    "DIAGNOSTIC_TERMS",
    "EVIDENCE_ABSENT",
    "EVIDENCE_CONFLICTING",
    "EVIDENCE_GROUNDED",
    "EVIDENCE_MALFORMED",
    "EVIDENCE_TEMPORALLY_AMBIGUOUS",
    "EVIDENCE_UNGROUNDED",
    "EVIDENCE_UNKNOWN",
    "EVIDENCE_VALID_EMPTY",
    "FORCED_CONCLUSION_PHRASES",
    "LEVEL_BELIEF",
    "LEVEL_COUNTER_HYPOTHESIS",
    "LEVEL_HYPOTHESIS",
    "LEVEL_INTERPRETATION",
    "LEVEL_OBSERVATION",
    "LEVEL_OPEN_QUESTION",
    "LEVEL_SOURCE",
    "LEVEL_UNCERTAINTY",
    "LEVEL_UNKNOWN",
    "REFLECTION_RULE_IDS",
    "BeliefEvidenceRule",
    "MultipleHypothesesRule",
    "NoForcedConclusionRule",
    "OpenQuestionRule",
    "PreserveAmbivalenceRule",
    "ReflectionTemporalEvolutionRule",
    "build_reflection_rules",
    "classify_belief_evidence",
    "classify_statement_level",
    "compare_reflection_versions",
    "evaluate_ambivalence",
    "evaluate_hypotheses",
    "evaluate_open_questions",
    "format_timestamp",
    "map_interests",
    "no_forced_conclusion_policy",
]