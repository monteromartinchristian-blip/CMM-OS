"""Shared, domain-generic hypothesis evaluation (Phase 10 extraction).

``evaluate_hypotheses`` preserves every plausible hypothesis together with its
supporting/counterevidence references and uncertainty, keeps conflicts
unresolved, never selects an arbitrary winner, never converts a hypothesis into
a fact, collapses exact duplicates without inflating evidence, and is fully
input-order invariant (frozen design §38; reused by both Reflection and
Concerns).

The diagnostic-risk hook is a *callable parameter*: the caller decides whether
a statement is diagnostic/restricted under its own domain policy.  Reflection
passes its private lexical classifier; Concerns passes a conservative
``None``/no-diagnosis default.  This keeps the evaluator genuinely generic
while the two specialized domains retain their own diagnostic vocabularies
(no shared medical/psychological lexicon in generic code).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

LEVEL_HYPOTHESIS = "hypothesis"

EVIDENCE_MALFORMED = "malformed"
EVIDENCE_UNKNOWN = "unknown"
EVIDENCE_CONFLICTING = "conflicting"
EVIDENCE_GROUNDED = "grounded"

_DIAGNOSTIC_KINDS: frozenset[str] = frozenset(
    {
        "diagnosis",
        "mental_health_diagnosis",
        "personality_classification",
        "attachment_classification",
        "stable_identity_classification",
        "fixed_motive_classification",
        "moral_character_classification",
    }
)

# Restriction shorthand: a diagnostic finding may never be ranked "stronger"
# and the result must report no_diagnosis=False.
_DIAG_RESTRICTED = "restricted"


def _boolean_true(value: Any) -> bool:
    return isinstance(value, bool) and value is True


def _usable_scalar_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _usable_string_items(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, (list, tuple)):
        seen: list[str] = []
        for item in value:
            usable = _usable_scalar_string(item)
            if usable is not None and usable not in seen:
                seen.append(usable)
        return tuple(seen)
    return ()


def _normalize_collection(
    value: Any, *, require_mapping_elements: bool = False
) -> tuple[list, bool]:
    if value is None:
        return [], False
    if isinstance(value, str):
        return [], True
    if isinstance(value, (list, tuple)):
        items = list(value)
        if require_mapping_elements:
            malformed = any(not isinstance(item, Mapping) for item in items)
        else:
            malformed = False
        return items, malformed
    return [], True


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    import math

    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def normalize_json_value(value: Any) -> Any:
    """Recursively normalize a value to JSON-safe form (shared boundary)."""
    import math

    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {
            (str(key) if not isinstance(key, str) else key): normalize_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return tuple(normalize_json_value(item) for item in value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return None


def evaluate_hypotheses(
    *,
    hypotheses: Any = (),
    diagnostic_signal: Callable[[Any], bool] | None = None,
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

    ``diagnostic_signal(statement)`` is the caller-owned policy hook.  When
    ``None`` (Concerns default), no statement is classified diagnostic and
    ``no_diagnosis=True`` always; Reflection passes its own classifier.
    """
    raw, malformed = _normalize_collection(
        hypotheses, require_mapping_elements=True
    )
    if malformed:
        return normalize_json_value(
            {
                "hypotheses": (),
                "supported_ids": (),
                "conflicting_ids": (),
                "collision_ids": (),
                "unresolved": True,
                "winner_selected": False,
                "forced_conclusion": False,
                "no_diagnosis": True,
                "insufficient_basis_to_rank": True,
                "evidence_state": EVIDENCE_MALFORMED,
            }
        )

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
        explicit_diag = (
            _boolean_true(entry.get("diagnostic"))
            or _boolean_true(entry.get("restricted_inference"))
        )
        kind = _usable_scalar_string(entry.get("classification_kind"))
        if kind in _DIAGNOSTIC_KINDS:
            explicit_diag = True

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
            previous["explicit_diagnostic"] = (
                bool(previous.get("explicit_diagnostic", False)) or explicit_diag
            )
            continue
        for existing_identity, existing_statement in merged:
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
            "explicit_diagnostic": explicit_diag,
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
    # Same identity with incompatible statements is a semantic collision and
    # must fail closed to unresolved/conflicting, never a clean ranking.
    collision_ids = set(collisions)

    supported = {
        source_id
        for record in records
        for source_id in record["supporting_ids"]
    }
    unresolved = (
        bool(conflicting_ids)
        or bool(collision_ids)
        or any(not record["supporting_ids"] for record in records)
    )
    insufficient_to_rank = any(not record["supporting_ids"] for record in records)

    # Relative strength: strictly more grounded support than every other
    # hypothesis with no conflicts on its own evidence and no collided identity.
    strengths: dict[str, int | None] = {
        record["identity"]: (
            len(record["supporting_ids"]) if record["supporting_ids"] else None
        )
        for record in records
        if record["identity"] not in collision_ids
    }
    max_strength = max(
        (v for v in strengths.values() if v is not None), default=None
    )
    relative_strength: dict[str, str | None] = {}
    for record in records:
        identity = record["identity"]
        if identity in collision_ids:
            relative_strength[identity] = None
            continue
        strength = strengths.get(identity)
        if (
            strength is not None
            and max_strength is not None
            and strength == max_strength
            and sum(1 for v in strengths.values() if v == max_strength) == 1
            and not any(
                source_id in conflicting_ids
                for source_id in record["supporting_ids"]
            )
        ):
            relative_strength[identity] = "stronger"
        else:
            relative_strength[identity] = None

    is_diagnostic = diagnostic_signal if diagnostic_signal is not None else (
        lambda statement: False
    )
    hypotheses_out = []
    for record in records:
        diagnostic = (
            bool(record.get("explicit_diagnostic", False))
            or is_diagnostic(record["statement"])
        )
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
                "diagnostic": diagnostic,
                "restricted_inference": diagnostic,
                "relative_strength": (
                    None if diagnostic else relative_strength[record["identity"]]
                ),
            }
        )

    any_diagnostic = any(h["diagnostic"] for h in hypotheses_out)
    return normalize_json_value(
        {
            "hypotheses": tuple(hypotheses_out),
            "supported_ids": tuple(sorted(supported)),
            "conflicting_ids": tuple(sorted(conflicting_ids)),
            "collision_ids": tuple(sorted(collision_ids)),
            "unresolved": unresolved,
            "winner_selected": False,
            "forced_conclusion": False,
            "no_diagnosis": not any_diagnostic,
            "insufficient_basis_to_rank": insufficient_to_rank,
            "evidence_state": (
                EVIDENCE_MALFORMED
                if malformed
                else EVIDENCE_CONFLICTING
                if conflicting_ids or collision_ids
                else EVIDENCE_GROUNDED
                if supported
                else EVIDENCE_UNKNOWN
            ),
        }
    )


__all__ = [
    "EVIDENCE_CONFLICTING",
    "EVIDENCE_GROUNDED",
    "EVIDENCE_MALFORMED",
    "EVIDENCE_UNKNOWN",
    "LEVEL_HYPOTHESIS",
    "evaluate_hypotheses",
    "normalize_json_value",
]