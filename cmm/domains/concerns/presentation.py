"""Phase 10.25 — Concerns Domain Presentation.

``present_concerns_result`` produces a semantics-preserving, user-facing
projection of a structured concern-support result: facts stay facts,
interpretations stay interpretations, hypotheses stay hypothetical,
fears/scenarios never become predictions or probabilities, uncertainty stays
visible without drowning the answer in caveats, reassurance/material-concern
assessments and risk/action/memory/permission states are preserved verbatim.

Presentation NEVER changes epistemic content.  It defines no fixed persona:
tone, warmth, register, verbosity, rhythm and channel behavior belong to the
shared presentation layer and later Phase 11 Communication Profiles (frozen
design §8, §78).  All outputs are JSON-safe.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.domains.concerns.profile import build_concerns_profile

PRESENTATION_STATE_KNOWN_FACT = "known_fact"
PRESENTATION_STATE_USER_EXPERIENCE = "user_experience"
PRESENTATION_STATE_INTERPRETATION = "interpretation"
PRESENTATION_STATE_HYPOTHETICAL = "hypothetical"
PRESENTATION_STATE_FEAR = "fear"
PRESENTATION_STATE_SCENARIO = "scenario"
PRESENTATION_STATE_UNCERTAIN = "uncertain"
PRESENTATION_STATE_UNKNOWN = "unknown"

_STATE_MAP: dict[str, str] = {
    "fact": PRESENTATION_STATE_KNOWN_FACT,
    "known_fact": PRESENTATION_STATE_KNOWN_FACT,
    "experience": PRESENTATION_STATE_USER_EXPERIENCE,
    "emotion": PRESENTATION_STATE_USER_EXPERIENCE,
    "interpretation": PRESENTATION_STATE_INTERPRETATION,
    "hypothesis": PRESENTATION_STATE_HYPOTHETICAL,
    "fear": PRESENTATION_STATE_FEAR,
    "scenario": PRESENTATION_STATE_SCENARIO,
    "uncertainty": PRESENTATION_STATE_UNCERTAIN,
}

# Semantic content order (frozen design §78): actual concern first, then lived
# impact, then substantive perspective, then useful distinctions, uncertainty,
# reassurance/material concern, and proportional action last.
_SECTION_ORDER: tuple[str, ...] = (
    "actual_concern",
    "lived_impact",
    "perspective",
    "epistemic_distinctions",
    "uncertainty",
    "reassurance_material_concern",
    "proportional_action",
)


def _literal_true(value) -> bool:
    """Strict literal-boolean guard for decision-relevant fields."""
    return value is True


def _string_items(value: Any) -> tuple[str, ...]:
    """Ordered unique usable strings from a scalar/collection; malformed dropped."""
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, (list, tuple)):
        seen: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip() and item not in seen:
                seen.append(item)
        return tuple(seen)
    return ()


def build_concerns_presentation_policy():
    """Build the Concerns Domain presentation policy from the profile."""
    return build_concerns_profile().presentation_policy


def _project_records(value: Any, *, state: str, **extra: Any) -> tuple[dict, ...]:
    """Project record/string collections into presentation-state-tagged items.

    String members are treated as bare statements of the given state; mapping
    members keep their fields and gain the presentation state plus any extra
    semantic flags.  Non-collection scalars are ignored (never widened).
    """
    projected: list[dict] = []
    if isinstance(value, Mapping):
        candidates: tuple = (value,)
    elif isinstance(value, (list, tuple)):
        candidates = tuple(value)
    else:
        return ()
    for item in candidates:
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            projected.append({"statement": text, "presentation_state": state, **extra})
        elif isinstance(item, Mapping):
            statement = (
                item.get("statement")
                or item.get("content")
                or item.get("text")
            )
            entry = {
                key: item.get(key)
                for key in ("identity", "id", "option_id", "source")
                if key in item
            }
            entry["statement"] = (
                statement if isinstance(statement, str) else None
            ) or ""
            entry["presentation_state"] = state
            entry.update(extra)
            projected.append(entry)
    return tuple(projected)


def present_concerns_result(result) -> dict:
    """Project a structured concern-support result without altering semantics.

    Preserved verbatim: support need, reassurance assessment, material
    concerns, risk, action state, memory state, permissions, desired outcome.
    Epistemic records are tagged with their closed presentation state but are
    never upgraded, erased, or converted into user facts.  Uncertainty is never
    resolved by presentation; an unresolved result is presented as unresolved.
    """
    if not isinstance(result, Mapping):
        return {
            "section_order": _SECTION_ORDER,
            "unresolved": True,
            "facts": (),
            "interpretations": (),
            "hypotheses": (),
            "fears": (),
            "scenarios": (),
            "uncertainty": (),
            "reassurance_assessment": "INSUFFICIENT_BASIS",
            "material_concerns": (),
            "risk": {"risk_level": "unresolved"},
            "action_state": "NO_ACTION_NEEDED",
            "memory_state": {"persisted": False},
            "support_need": "UNCLEAR",
            "certainty_amplified": False,
            "conclusion_presented": False,
            "presentation_state": PRESENTATION_STATE_UNKNOWN,
        }

    facts = _project_records(result.get("facts"), state=PRESENTATION_STATE_KNOWN_FACT)
    experiences = _project_records(
        result.get("experiences") or result.get("emotions"),
        state=PRESENTATION_STATE_USER_EXPERIENCE,
        experience_valid=True,
        external_fact=False,
    )
    interpretations = _project_records(
        result.get("interpretations"),
        state=PRESENTATION_STATE_INTERPRETATION,
        promoted_to_fact=False,
        user_fact=False,
    )
    hypotheses = _project_records(
        result.get("hypotheses"),
        state=PRESENTATION_STATE_HYPOTHETICAL,
        fact=False,
    )
    fears = _project_records(
        result.get("fears"),
        state=PRESENTATION_STATE_FEAR,
        prediction=False,
        probability_claim=False,
    )
    scenarios = _project_records(
        result.get("scenarios"),
        state=PRESENTATION_STATE_SCENARIO,
        probability_claim=False,
    )
    caveats_input = result.get("caveats")
    if caveats_input:
        from cmm.domains.concerns.rules import evaluate_caveat_policy

        caveat_eval = evaluate_caveat_policy(caveats=caveats_input)
        retained_texts = {
            c["caveat"] for c in caveat_eval["retained"] if "caveat" in c
        }
        scenarios = tuple(
            s
            for s in scenarios
            if s.get("statement") in retained_texts or s.get("caveat") in retained_texts
        )

    uncertainty_raw = result.get("uncertainty")
    if isinstance(uncertainty_raw, (str, list, tuple)):
        uncertainty = _string_items(uncertainty_raw)
    elif isinstance(result.get("remaining_uncertainty"), (list, tuple)):
        # Canonical reassurance helper shape: remaining_uncertainty (I-007).
        uncertainty = _string_items(result.get("remaining_uncertainty"))
    else:
        uncertainty = ()

    # Verbatim semantic fields — never altered by presentation.
    # The canonical flat helper shape carries assessment at top level with
    # remaining_uncertainty (I-007); legacy nested shapes are also honoured.
    reassurance_assessment = None
    if isinstance(result.get("reassurance"), Mapping):
        reassurance_assessment = result["reassurance"].get("assessment")
    if reassurance_assessment is None:
        reassurance_assessment = result.get("assessment")
    if reassurance_assessment is None:
        reassurance_assessment = result.get("reassurance_assessment")
    material_concerns_raw = result.get("material_concerns")
    if material_concerns_raw is None:
        material_concerns_raw = result.get("acknowledged_concerns")
    material_concerns = _string_items(material_concerns_raw)
    # A canonical reassurance result is never an absolute certainty: absolute
    # certainty is structurally forbidden (frozen §22).
    absolute_certainty_claimed = (
        _literal_true(result.get("absolute_certainty"))
        or _literal_true(result.get("certainty_amplified"))
    )
    risk_value = result.get("risk")
    risk = dict(risk_value) if isinstance(risk_value, Mapping) else {"risk_level": "none"}
    action_state = result.get("action_state") or "NO_ACTION_NEEDED"
    memory_value = result.get("memory_state")
    memory_state = (
        dict(memory_value) if isinstance(memory_value, Mapping) else {"persisted": False}
    )
    permissions = _string_items(result.get("permissions"))
    support_need = result.get("support_need") or "UNCLEAR"

    unresolved = bool(uncertainty) or _literal_true(result.get("unresolved"))

    perspective_value = result.get("perspective")
    perspective = (
        dict(perspective_value)
        if isinstance(perspective_value, Mapping)
        else {"available": False}
    )
    epistemic_distinctions = _string_items(result.get("epistemic_distinctions"))
    lived_impact = _string_items(result.get("lived_impact"))
    actual_concern = _string_items(result.get("actual_concern"))

    return {
        "section_order": _SECTION_ORDER,
        "actual_concern": actual_concern,
        "lived_impact": lived_impact,
        "perspective": perspective,
        "epistemic_distinctions": epistemic_distinctions,
        "facts": facts,
        "experiences": experiences,
        "interpretations": interpretations,
        "hypotheses": hypotheses,
        "fears": fears,
        "scenarios": scenarios,
        "uncertainty": uncertainty,
        "reassurance_material_concern": {
            "reassurance_assessment": reassurance_assessment or "INSUFFICIENT_BASIS",
            "material_concerns": material_concerns,
        },
        "reassurance_assessment": reassurance_assessment or "INSUFFICIENT_BASIS",
        "material_concerns": material_concerns,
        "proportional_action": {"action_state": action_state, "risk": risk},
        "desired_outcome": (
            result.get("desired_outcome")
            if isinstance(result.get("desired_outcome"), str)
            else None
        ),
        "options": tuple(
            option
            for option in _project_records(
                result.get("options"),
                state="candidate_option",
                adopted=False,
            )
        ),
        "next_step": (
            result.get("next_step")
            if isinstance(result.get("next_step"), Mapping)
            else None
        ),
        "risk": risk,
        "action_state": action_state,
        "memory_state": memory_state,
        "permissions": permissions,
        "support_need": support_need,
        "unresolved": unresolved or absolute_certainty_claimed,
        "certainty_amplified": absolute_certainty_claimed,
        "conclusion_presented": not unresolved,
        "presentation_state": (
            PRESENTATION_STATE_UNCERTAIN
            if unresolved or absolute_certainty_claimed
            else PRESENTATION_STATE_KNOWN_FACT
        ),
    }


__all__ = [
    "PRESENTATION_STATE_FEAR",
    "PRESENTATION_STATE_HYPOTHETICAL",
    "PRESENTATION_STATE_INTERPRETATION",
    "PRESENTATION_STATE_KNOWN_FACT",
    "PRESENTATION_STATE_SCENARIO",
    "PRESENTATION_STATE_UNCERTAIN",
    "PRESENTATION_STATE_UNKNOWN",
    "PRESENTATION_STATE_USER_EXPERIENCE",
    "build_concerns_presentation_policy",
    "present_concerns_result",
]
