"""Phase 10.24 — Reflection Domain Presentation.

The Reflection presentation policy is owned by the conservative Reflection
profile and surfaced here without duplication.  ``present_reflection_result``
produces a certainty-preserving user-facing projection of a structured
reflection result: hypotheses stay hypotheses, uncertainty/ambivalence/open
questions stay visible, and identity/persistence/decision/temporal statuses
are never silently upgraded (spec §36, §46).

Presentation never increases certainty: an unresolved result is never
presented as resolved, and a hypothesis is never worded as a fact or diagnosis.
All outputs are JSON-safe.
"""

from __future__ import annotations

from collections.abc import Mapping

from cmm.domains.reflection.profile import build_reflection_profile
from cmm.domains.reflection.rules import _diagnostic_signal

PRESENTATION_STATE_OBSERVED = "observed"
PRESENTATION_STATE_USER_STATED = "user-stated"
PRESENTATION_STATE_INFERRED = "inferred"
PRESENTATION_STATE_HYPOTHETICAL = "hypothetical"
PRESENTATION_STATE_UNKNOWN = "unknown"
PRESENTATION_STATE_CONFLICTING = "conflicting"
PRESENTATION_STATE_CONFIRMED = "confirmed"
PRESENTATION_STATE_PENDING_CONFIRMATION = "pending-confirmation"

_STATE_MAP = {
    "observation": PRESENTATION_STATE_OBSERVED,
    "observed": PRESENTATION_STATE_OBSERVED,
    "user-stated": PRESENTATION_STATE_USER_STATED,
    "user_stated": PRESENTATION_STATE_USER_STATED,
    "explicit": PRESENTATION_STATE_USER_STATED,
    "inferred": PRESENTATION_STATE_INFERRED,
    "hypothesis": PRESENTATION_STATE_HYPOTHETICAL,
    "counter_hypothesis": PRESENTATION_STATE_HYPOTHETICAL,
    "unknown": PRESENTATION_STATE_UNKNOWN,
    "conflicting": PRESENTATION_STATE_CONFLICTING,
    "contradicted": PRESENTATION_STATE_CONFLICTING,
    "confirmed": PRESENTATION_STATE_CONFIRMED,
    "pending_confirmation": PRESENTATION_STATE_PENDING_CONFIRMATION,
    "pending confirmation": PRESENTATION_STATE_PENDING_CONFIRMATION,
}


def present_state(value) -> str:
    """Map a raw state marker to a closed presentation state.

    Malformed or unknown values collapse to ``unknown``; they never widen
    certainty.  Only the canonical string markers map to their closed states;
    a bare boolean or any other non-string never maps to ``confirmed`` (it is
    not a presentation state marker, and must not widen certainty).
    """
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _STATE_MAP:
            return _STATE_MAP[normalized]
        return PRESENTATION_STATE_UNKNOWN
    return PRESENTATION_STATE_UNKNOWN


def _literal_true(value) -> bool:
    """Strict literal-boolean guard for decision/security-relevant fields.

    Only the literal ``True`` counts; ``"true"``, ``"false"``, ``1``, ``0``,
    ``-1``, ``None``, mappings, and collections never count as truthy.
    """
    return value is True


def build_reflection_presentation_policy():
    """Build the Reflection Domain presentation policy from the profile."""
    return build_reflection_profile().presentation_policy


def present_reflection_result(result: Mapping) -> dict:
    """Project a structured reflection result without amplifying certainty.

    Preserves: observations, interpretations, beliefs, values, emotions,
    needs, hypotheses, counter-hypotheses, evidence, counterevidence,
    uncertainty, ambivalence, open questions, temporal state, interest
    provenance, persistence state, and decision state.  A hypothesis is
    presented with state ``hypothetical``; an unresolved result is presented as
    unresolved; nothing is converted into a fact, diagnosis, identity, adopted
    decision, or confirmed persistence.  Output is JSON-safe.
    """
    if not isinstance(result, Mapping):
        return {
            "unresolved": True,
            "hypotheses": (),
            "open_questions": (),
            "ambivalence_present": False,
            "persistent_confirmed": False,
            "decision_adopted": False,
            "temporally_ambiguous": True,
            "certainty_amplified": False,
            "conclusion_presented": False,
            "persistence_state": PRESENTATION_STATE_UNKNOWN,
            "decision_state": "not-adopted",
            "interest_candidates": (),
            "presentation_state": PRESENTATION_STATE_UNKNOWN,
        }

    unresolved = bool(result.get("unresolved", False)) or bool(
        result.get("open_questions")
    )
    hypotheses = tuple(result.get("hypotheses", ()) or ())
    presented_hypotheses = []
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, Mapping):
            continue
        statement = hypothesis.get("statement", "")
        diagnostic = bool(hypothesis.get("diagnostic", False)) or bool(
            hypothesis.get("restricted_inference", False)
        ) or _diagnostic_signal(statement)
        # A diagnostic/identity-classifying statement must never be presented
        # verbatim as a safe non-diagnostic hypothesis; it is represented
        # structurally as prohibited and its wording is withheld.
        presented_statement = (
            "[restricted: diagnostic/classifying claim withheld]"
            if diagnostic
            else statement
        )
        presented_hypotheses.append(
            {
                "identity": hypothesis.get("identity", "unknown"),
                "statement": presented_statement,
                "presentation_state": PRESENTATION_STATE_HYPOTHETICAL,
                "fact": False,
                "diagnosis": diagnostic,
                "restricted_inference": diagnostic,
                "relative_strength": (
                    None if diagnostic else hypothesis.get("relative_strength")
                ),
                "uncertainty": hypothesis.get("uncertainty"),
            }
        )

    open_questions = tuple(result.get("open_questions", ()) or ())
    if open_questions and not isinstance(open_questions, (list, tuple)):
        open_questions = (open_questions,)

    interest_candidates = tuple(result.get("interest_candidates", ()) or ())
    presented_interests = []
    for candidate in interest_candidates:
        if not isinstance(candidate, Mapping):
            continue
        candidate_confirmed = _literal_true(candidate.get("persistent_confirmed"))
        presented_interests.append(
            {
                "interest": candidate.get("interest", ""),
                "sources": tuple(candidate.get("sources", ()) or ()),
                "grounded_evidence_count": candidate.get("grounded_evidence_count", 0),
                "persistent_confirmed": candidate_confirmed,
                "presentation_state": (
                    PRESENTATION_STATE_CONFIRMED
                    if candidate_confirmed
                    else PRESENTATION_STATE_PENDING_CONFIRMATION
                ),
            }
        )

    persistent_confirmed = _literal_true(result.get("persistent_confirmed"))
    eligible_for_confirmation = _literal_true(result.get("eligible_for_confirmation"))
    persistence_state = (
        PRESENTATION_STATE_CONFIRMED
        if persistent_confirmed
        else PRESENTATION_STATE_PENDING_CONFIRMATION
        if eligible_for_confirmation
        or bool(interest_candidates)
        or result.get("pattern") is not None
        else PRESENTATION_STATE_UNKNOWN
    )
    decision_adopted = _literal_true(result.get("decision_adopted"))
    decision_state = "adopted" if decision_adopted else "not-adopted"

    chronology = result.get("chronology_state")
    temporally_ambiguous = chronology in ("malformed", "unknown", "equal_timestamps", None)

    return {
        "unresolved": unresolved,
        "hypotheses": tuple(presented_hypotheses),
        "hypothesis_count": len(presented_hypotheses),
        "open_questions": open_questions,
        "ambivalence_present": bool(result.get("ambivalence_present", False)),
        "counterevidence": tuple(result.get("counterevidence", ()) or ()),
        "persistent_confirmed": persistent_confirmed,
        "decision_adopted": decision_adopted,
        "temporally_ambiguous": temporally_ambiguous,
        "certainty_amplified": False,
        "conclusion_presented": not unresolved,
        "persistence_state": persistence_state,
        "decision_state": decision_state,
        "interest_candidates": tuple(presented_interests),
        "presentation_state": present_state(result.get("state")),
    }


__all__ = [
    "PRESENTATION_STATE_CONFIRMED",
    "PRESENTATION_STATE_CONFLICTING",
    "PRESENTATION_STATE_HYPOTHETICAL",
    "PRESENTATION_STATE_INFERRED",
    "PRESENTATION_STATE_OBSERVED",
    "PRESENTATION_STATE_PENDING_CONFIRMATION",
    "PRESENTATION_STATE_UNKNOWN",
    "PRESENTATION_STATE_USER_STATED",
    "build_reflection_presentation_policy",
    "present_reflection_result",
    "present_state",
]