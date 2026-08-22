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
                or item.get("claim")
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
            "experiences": (),
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

    raw_statements = result.get("statements") or result.get("records") or ()
    stmt_facts = []
    stmt_experiences = []
    stmt_interpretations = []
    stmt_hypotheses = []
    stmt_fears = []
    if isinstance(raw_statements, (list, tuple)):
        for item in raw_statements:
            if isinstance(item, Mapping):
                lvl = item.get("level") or item.get("kind")
                if lvl in ("fact", "known_fact"):
                    stmt_facts.append(item)
                elif lvl in ("experience", "emotion"):
                    stmt_experiences.append(item)
                elif lvl in ("interpretation", "inference"):
                    stmt_interpretations.append(item)
                elif lvl in ("hypothesis", "hypothetical"):
                    stmt_hypotheses.append(item)
                elif lvl in ("fear", "worry"):
                    stmt_fears.append(item)

    # Key facts from professional discussion
    key_facts = result.get("key_facts") or ()
    all_facts = list(result.get("facts") or tuple(stmt_facts))
    if isinstance(key_facts, (list, tuple)):
        for kf in key_facts:
            if isinstance(kf, str) and kf.strip() and kf not in all_facts or isinstance(kf, Mapping) and kf not in all_facts:
                all_facts.append(kf)
    prepared_content = result.get("prepared_content")
    if not all_facts and isinstance(prepared_content, str) and "## Key facts" in prepared_content:
        lines = prepared_content.splitlines()
        in_key_facts = False
        for line in lines:
            if line.startswith("## Key facts"):
                in_key_facts = True
                continue
            elif line.startswith("## "):
                in_key_facts = False
            elif in_key_facts and line.startswith("- ") and line[2:].strip() and line[2:].strip() != "Not stated.":
                all_facts.append(line[2:].strip())

    facts = _project_records(
        tuple(all_facts),
        state=PRESENTATION_STATE_KNOWN_FACT,
    )
    experiences = _project_records(
        result.get("experiences") or result.get("emotions") or tuple(stmt_experiences),
        state=PRESENTATION_STATE_USER_EXPERIENCE,
        experience_valid=True,
        external_fact=False,
    )
    interpretations = _project_records(
        result.get("interpretations") or tuple(stmt_interpretations),
        state=PRESENTATION_STATE_INTERPRETATION,
        promoted_to_fact=False,
        user_fact=False,
    )
    hypotheses = _project_records(
        result.get("hypotheses") or tuple(stmt_hypotheses),
        state=PRESENTATION_STATE_HYPOTHETICAL,
        fact=False,
    )
    fears = _project_records(
        result.get("fears") or tuple(stmt_fears),
        state=PRESENTATION_STATE_FEAR,
        prediction=False,
        probability_claim=False,
    )
    scenarios = _project_records(
        result.get("scenarios"),
        state=PRESENTATION_STATE_SCENARIO,
        probability_claim=False,
    )

    # Caveats: remove ONLY scenarios/caveats that match suppressed/remote caveats (FI-001)
    caveats_input = result.get("caveats")
    if caveats_input:
        from cmm.domains.concerns.rules import evaluate_caveat_policy

        caveat_eval = evaluate_caveat_policy(caveats=caveats_input)
        retained_texts: set[str] = {
            c["caveat"]
            for c in caveat_eval.get("retained", ())
            if isinstance(c, Mapping) and "caveat" in c and isinstance(c["caveat"], str)
        }
        suppressed_texts: set[str] = set()
        if isinstance(caveats_input, (list, tuple)):
            for c in caveats_input:
                if isinstance(c, Mapping):
                    text = (
                        c.get("caveat")
                        or c.get("warning")
                        or c.get("statement")
                        or c.get("text")
                    )
                    if isinstance(text, str) and text.strip() and text.strip() not in retained_texts:
                        suppressed_texts.add(text.strip())
                elif isinstance(c, str) and c.strip() and c.strip() not in retained_texts:
                    suppressed_texts.add(c.strip())
        scenarios = tuple(
            s
            for s in scenarios
            if s.get("statement") not in suppressed_texts and s.get("caveat") not in suppressed_texts
        )

    # Uncertainty and calibrations preservation (FI-001)
    uncertainty_raw = result.get("uncertainty")
    calibrations_raw = result.get("calibrations")
    if isinstance(uncertainty_raw, (str, list, tuple)):
        uncertainty = _string_items(uncertainty_raw)
    elif isinstance(result.get("remaining_uncertainty"), (list, tuple)):
        uncertainty = _string_items(result.get("remaining_uncertainty"))
    elif isinstance(calibrations_raw, (list, tuple)) and calibrations_raw:
        cal_items: list[str] = []
        for c in calibrations_raw:
            if isinstance(c, Mapping):
                claim = c.get("claim") or c.get("statement") or c.get("identity")
                status = c.get("status")
                if claim and status:
                    cal_items.append(f"{claim}: {status}")
                elif claim:
                    cal_items.append(str(claim))
            elif isinstance(c, str) and c.strip():
                cal_items.append(c.strip())
        if result.get("conflict_present"):
            cal_items.append("conflict_present: true")
        uncertainty = tuple(cal_items)
    else:
        uncertainty = ()

    # Calibrations structured projection
    if isinstance(calibrations_raw, (list, tuple)):
        calibrations = tuple(
            dict(c) if isinstance(c, Mapping) else {"claim": str(c)}
            for c in calibrations_raw
        )
    else:
        calibrations = ()

    # Open questions & why_it_matters preservation (FI-001)
    questions_raw = (
        result.get("open_questions")
        or result.get("questions")
        or result.get("specific_questions")
        or ()
    )
    if isinstance(questions_raw, (list, tuple)):
        open_questions = tuple(
            {
                "question": q.get("question") if isinstance(q, Mapping) else str(q),
                "materiality": q.get("materiality", "material") if isinstance(q, Mapping) else "material",
                "why_it_matters": tuple(q.get("why_it_matters", ())) if isinstance(q, Mapping) and isinstance(q.get("why_it_matters"), (list, tuple)) else (),
            }
            if isinstance(q, Mapping)
            else {"question": str(q), "materiality": "material", "why_it_matters": ()}
            for q in questions_raw
            if (isinstance(q, Mapping) and q.get("question")) or (isinstance(q, str) and q.strip())
        )
    else:
        open_questions = ()

    # Verbatim semantic fields — do not manufacture defaults if not evaluated (FI-001)
    reassurance_assessment = None
    if isinstance(result.get("reassurance"), Mapping):
        reassurance_assessment = result["reassurance"].get("assessment")
    if reassurance_assessment is None and "assessment" in result:
        reassurance_assessment = result.get("assessment")
    if reassurance_assessment is None and "reassurance_assessment" in result:
        reassurance_assessment = result.get("reassurance_assessment")

    material_concerns_raw = result.get("material_concerns")
    if material_concerns_raw is None:
        material_concerns_raw = result.get("acknowledged_concerns")
    material_concerns = _string_items(material_concerns_raw)

    absolute_certainty_claimed = (
        _literal_true(result.get("absolute_certainty"))
        or _literal_true(result.get("certainty_amplified"))
    )

    risk_value = result.get("risk")
    if isinstance(risk_value, Mapping):
        risk = dict(risk_value)
    elif "risk_level" in result and result.get("risk_level") is not None:
        risk = {
            "risk_level": result.get("risk_level"),
            "emotion_drove_risk": result.get("emotion_drove_risk", False),
            "grounded_risk_evidence": result.get("grounded_risk_evidence", False),
            "specialized_ownership_preserved": result.get("specialized_ownership_preserved", False),
            "immediate": result.get("immediate", False),
            "escalation_recommended": result.get("escalation_recommended", False),
        }
    else:
        # Not evaluated — do NOT manufacture a 'none' conclusion if risk was never evaluated
        risk = {"risk_level": None}

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

    # Actual concern preservation from understand_concern, professional discussion, or similar operations (FI-001)
    actual_concern_raw = result.get("actual_concern")
    if actual_concern_raw is not None:
        actual_concern = _string_items(actual_concern_raw)
    else:
        candidates: list[str] = []
        for key in (
            "core_issue",
            "situation",
            "trigger",
            "what_matters",
            "concern_summary",
            "topic",
            "concern",
        ):
            val = result.get(key)
            if isinstance(val, str) and val.strip() and val.strip() not in candidates:
                candidates.append(val.strip())
            elif isinstance(val, (list, tuple)):
                for item in val:
                    if isinstance(item, str) and item.strip() and item.strip() not in candidates:
                        candidates.append(item.strip())
        prepared_content = result.get("prepared_content")
        if not candidates and isinstance(prepared_content, str) and "—" in prepared_content:
            first_line = prepared_content.splitlines()[0]
            summary = first_line.split("—", 1)[-1].strip()
            if summary:
                candidates.append(summary)
        actual_concern = tuple(candidates)

    # Recurrence state preservation
    recurrence = result.get("recurrence")

    if unresolved or absolute_certainty_claimed:
        presentation_state = PRESENTATION_STATE_UNCERTAIN
    elif bool(facts):
        presentation_state = PRESENTATION_STATE_KNOWN_FACT
    elif bool(interpretations):
        presentation_state = PRESENTATION_STATE_INTERPRETATION
    elif bool(hypotheses):
        presentation_state = PRESENTATION_STATE_HYPOTHETICAL
    elif bool(fears):
        presentation_state = PRESENTATION_STATE_FEAR
    elif bool(experiences) or bool(actual_concern):
        presentation_state = PRESENTATION_STATE_USER_EXPERIENCE
    elif bool(scenarios):
        presentation_state = PRESENTATION_STATE_SCENARIO
    else:
        presentation_state = PRESENTATION_STATE_UNKNOWN

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
        "calibrations": calibrations,
        "open_questions": open_questions,
        "questions": open_questions,
        "recurrence": recurrence,
        "reassurance_material_concern": {
            "reassurance_assessment": reassurance_assessment,
            "material_concerns": material_concerns,
        },
        "reassurance_assessment": reassurance_assessment,
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
        "presentation_state": presentation_state,
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
