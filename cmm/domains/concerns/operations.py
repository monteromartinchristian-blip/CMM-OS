"""Phase 10.25 — Concerns Domain Operations.

Thirteen declarative concern-support operations built on the shared
``DomainOperationDefinition`` contract.  No implementation is embedded here;
an operation without a provided implementation is registered as
**UNAVAILABLE** (fail-closed).  Each operation exposes a pure, deterministic
result builder that produces its JSON-safe output payload by **delegating to
the canonical rule helpers** rather than reimplementing competing logic.

Safety posture (frozen design §74, §95):

- Every operation is an analysis/preparation operation.  No operation sends a
  message, contacts anyone, books anything, transmits, modifies a calendar,
  writes semantic memory, executes a personal decision, or starts monitoring.
- ``prepare_professional_discussion`` prepares content only:
  PREPARATION != SEND.
- ``required_resources`` uses strict AND semantics; only operations that
  structurally consume a resource declare it.
"""

from __future__ import annotations

from collections.abc import Mapping

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.concerns.catalog import CANONICAL_CONCERNS_OPERATION_IDS
from cmm.domains.concerns.rules import (
    QUESTION_MATERIAL,
    classify_concern_statement,
    detect_false_reassurance,
    evaluate_action_state,
    evaluate_immediate_risk_escalation,
    evaluate_proportional_risk,
    evaluate_question_materiality,
    evaluate_reassurance,
    evaluate_repetitive_certainty_pattern,
    evaluate_uncertainty,
    infer_support_need,
    map_lived_experience,
    normalize_json_value,
    review_recurring_concern_state,
    understand_concern,
)
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition

CONCERNS_OPERATION_IDS: tuple[str, ...] = CANONICAL_CONCERNS_OPERATION_IDS

_OPERATION_TYPES: dict[str, DomainOperationType] = {
    operation_id: (
        DomainOperationType.PREPARATION
        if operation_id
        in (
            "concerns.prepare_next_step",
            "concerns.prepare_professional_discussion",
        )
        else DomainOperationType.ANALYSIS
    )
    for operation_id in CANONICAL_CONCERNS_OPERATION_IDS
}

# Resources each operation structurally consumes (AND semantics).
_REQUIRED_RESOURCES: dict[str, tuple[str, ...]] = {
    "concerns.understand_concern": ("concerns.user_message",),
    "concerns.infer_support_need": ("concerns.conversation",),
    "concerns.map_lived_experience": ("concerns.user_message",),
    "concerns.separate_reality_interpretation": ("concerns.user_message",),
    "concerns.explore_hypotheses": ("concerns.conversation",),
    "concerns.calibrate_uncertainty": ("concerns.note",),
    "concerns.evaluate_reassurance": ("concerns.conversation", "concerns.domain_result"),
    "concerns.evaluate_risk": ("concerns.domain_result",),
    "concerns.identify_open_questions": ("concerns.conversation",),
    "concerns.explore_options": ("concerns.goal",),
    "concerns.prepare_next_step": ("concerns.goal",),
    "concerns.review_recurring_concern": (
        "concerns.memory_entry",
        "concerns.conversation",
    ),
    "concerns.prepare_professional_discussion": (
        "concerns.note",
        "concerns.journal_entry",
    ),
}


def _schema(required: tuple[str, ...], properties: dict) -> dict:
    """Build a deterministic JSON object schema with closed properties."""
    return {
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": False,
    }


# Canonical flat record shapes: every operation's declared output schema is
# the exact contract of its canonical result helper (B-002 remediation — one
# shape across helper, runtime, workflows and presentation).
_ID_ARRAY = {"type": "array", "items": {"type": "string"}}
_RECORDS = {"type": "array", "items": {"type": "object"}}
_BOOL = {"type": "boolean"}
_STR = {"type": "string"}
_STR_OR_NULL = {"type": ["string", "null"]}
_INT = {"type": "integer"}
_NUM_OR_NULL = {"type": ["number", "null"]}

_INPUT_SCHEMAS: dict[str, dict] = {
    "concerns.understand_concern": _schema(
        ("material",), {"material": {"type": "object"}}
    ),
    "concerns.infer_support_need": _schema(
        ("inputs",), {"inputs": {"type": "object"}}
    ),
    "concerns.map_lived_experience": _schema(
        ("material",), {"material": {"type": "object"}}
    ),
    "concerns.separate_reality_interpretation": _schema(
        ("statements",), {"statements": _RECORDS}
    ),
    "concerns.explore_hypotheses": _schema(("hypotheses",), {"hypotheses": _RECORDS}),
    "concerns.calibrate_uncertainty": _schema(("records",), {"records": _RECORDS}),
    "concerns.evaluate_reassurance": _schema(
        ("evidence",),
        {
            "evidence": _RECORDS,
            "counterevidence": _RECORDS,
            "uncertainty": _RECORDS,
        },
    ),
    "concerns.evaluate_risk": _schema(
        ("severity",),
        {
            "severity": {"type": ["string", "null"]},
            "evidence": _RECORDS,
        },
    ),
    "concerns.identify_open_questions": _schema(
        ("questions",), {"questions": _RECORDS}
    ),
    "concerns.explore_options": _schema(("options",), {"options": _RECORDS}),
    "concerns.prepare_next_step": _schema(
        ("options",), {"options": _RECORDS, "user_request": {"type": ["string", "null"]}}
    ),
    "concerns.review_recurring_concern": _schema(
        ("current",),
        {"current": {"type": "object"}, "previous": _RECORDS, "turns": _RECORDS},
    ),
    "concerns.prepare_professional_discussion": _schema(
        ("concern_summary",),
        {
            "concern_summary": {"type": "string"},
            "key_facts": _ID_ARRAY,
            "open_questions": _ID_ARRAY,
            "documents_to_bring": _ID_ARRAY,
        },
    ),
}

_REASSURANCE_PAYLOAD = _schema(
    (
        "assessment",
        "remaining_uncertainty",
        "absolute_certainty",
        "numeric_probability_assigned",
    ),
    {
        "assessment": {"type": "string"},
        "supporting": _RECORDS,
        "counterevidence": _RECORDS,
        "remaining_uncertainty": _ID_ARRAY,
        "acknowledged_concerns": _ID_ARRAY,
        "material_concern": {"type": "boolean"},
        "concern_erased": {"type": "boolean"},
        "absolute_certainty": {"type": "boolean"},
        "duplicate_count": {"type": "integer"},
        "malformed_count": {"type": "integer"},
        "invented_assessment": {"type": "boolean"},
        "numeric_probability_assigned": {"type": "boolean"},
        "probability": {"type": ["number", "null"]},
        "specialized_probability": {"type": ["number", "null"]},
        "specialized_authorized": {"type": "boolean"},
        "reassurance_coexists_with_uncertainty": {"type": "boolean"},
        "persisted": {"type": "boolean"},
    },
)

_OUTPUT_SCHEMAS: dict[str, dict] = {
    "concerns.understand_concern": _schema(
        (
            "understood",
            "core_issue",
            "situation",
            "trigger",
            "resolved_from_session_context",
            "missing_material_context",
            "ask_question",
            "questions",
            "respond_with_qualification",
            "ready_for_substantive_response",
            "support_need",
            "mandatory_action_plan",
            "advice_generated",
            "malformed_input",
        ),
        {
            "understood": _BOOL,
            "core_issue": _STR_OR_NULL,
            "situation": _STR_OR_NULL,
            "trigger": _STR_OR_NULL,
            "resolved_from_session_context": _BOOL,
            "missing_material_context": _RECORDS,
            "ask_question": _BOOL,
            "questions": _RECORDS,
            "respond_with_qualification": _BOOL,
            "ready_for_substantive_response": _BOOL,
            "support_need": _STR,
            "mandatory_action_plan": _BOOL,
            "advice_generated": _BOOL,
            "malformed_input": _BOOL,
        },
    ),
    "concerns.infer_support_need": _schema(
        (
            "support_need",
            "basis",
            "components",
            "explicit",
            "inferred",
            "invented_classification",
            "problem_solving_allowed",
            "diagnosis",
            "personality_trait",
            "durable_identity",
            "revisable",
        ),
        {
            "support_need": _STR,
            "basis": _STR,
            "components": _ID_ARRAY,
            "explicit": _BOOL,
            "inferred": _BOOL,
            "invented_classification": _BOOL,
            "problem_solving_allowed": _BOOL,
            "diagnosis": _BOOL,
            "personality_trait": _BOOL,
            "durable_identity": _BOOL,
            "revisable": _BOOL,
        },
    ),
    "concerns.map_lived_experience": _schema(
        (
            "emotions",
            "fears",
            "interpretations",
            "needs",
            "desired_outcome",
            "perceived_meaning",
            "complete",
            "failure",
            "diagnosis",
            "stable_identity_inference",
            "persisted",
            "malformed_input",
        ),
        {
            "emotions": _RECORDS,
            "fears": _RECORDS,
            "interpretations": _RECORDS,
            "needs": _RECORDS,
            "desired_outcome": _STR_OR_NULL,
            "perceived_meaning": _STR_OR_NULL,
            "complete": _BOOL,
            "failure": _BOOL,
            "diagnosis": _BOOL,
            "stable_identity_inference": _BOOL,
            "persisted": _BOOL,
            "malformed_input": _BOOL,
        },
    ),
    "concerns.separate_reality_interpretation": _schema(
        (
            "statements",
            "promotions_blocked_total",
            "interpretation_promoted_to_fact",
            "catastrophic_escalation_present",
            "persisted",
            "malformed_input",
        ),
        {
            "statements": _RECORDS,
            "promotions_blocked_total": _INT,
            "interpretation_promoted_to_fact": _BOOL,
            "catastrophic_escalation_present": _BOOL,
            "persisted": _BOOL,
            "malformed_input": _BOOL,
        },
    ),
    "concerns.explore_hypotheses": _schema(
        (
            "hypotheses",
            "conflicting_ids",
            "evidence_state",
            "winner_selected",
            "forced_conclusion",
            "no_diagnosis",
            "unresolved",
        ),
        {
            "hypotheses": _RECORDS,
            "conflicting_ids": _ID_ARRAY,
            "evidence_state": _STR,
            "winner_selected": _BOOL,
            "forced_conclusion": _BOOL,
            "no_diagnosis": _BOOL,
            "unresolved": _BOOL,
        },
    ),
    "concerns.calibrate_uncertainty": _schema(
        (
            "calibrations",
            "resolved_by_invention",
            "conflict_present",
            "numeric_probability_invented",
            "malformed_input",
        ),
        {
            "calibrations": _RECORDS,
            "resolved_by_invention": _BOOL,
            "conflict_present": _BOOL,
            "numeric_probability_invented": _BOOL,
            "malformed_input": _BOOL,
        },
    ),
    # Flat canonical helper contract: the reassurance record IS the operation
    # output (B-002 remediation, Option A — one shape everywhere).
    "concerns.evaluate_reassurance": _schema(
        (
            "assessment",
            "target_claim",
            "base_plausibility",
            "supporting",
            "counterevidence",
            "remaining_uncertainty",
            "acknowledged_concerns",
            "material_concern",
            "concern_erased",
            "absolute_certainty",
            "duplicate_count",
            "malformed_count",
            "invented_assessment",
            "numeric_probability_assigned",
            "probability",
            "specialized_probability",
            "specialized_authorized",
            "reassurance_coexists_with_uncertainty",
            "false_reassurance_detected",
            "false_reassurance",
            "corrected_assessment",
            "persisted",
        ),
        {
            "assessment": _STR,
            "target_claim": _STR_OR_NULL,
            "base_plausibility": _STR_OR_NULL,
            "supporting": _RECORDS,
            "counterevidence": _RECORDS,
            "remaining_uncertainty": _ID_ARRAY,
            "acknowledged_concerns": _ID_ARRAY,
            "material_concern": _BOOL,
            "concern_erased": _BOOL,
            "absolute_certainty": _BOOL,
            "duplicate_count": _INT,
            "malformed_count": _INT,
            "invented_assessment": _BOOL,
            "numeric_probability_assigned": _BOOL,
            "probability": _NUM_OR_NULL,
            "specialized_probability": _NUM_OR_NULL,
            "specialized_authorized": _BOOL,
            "reassurance_coexists_with_uncertainty": _BOOL,
            "false_reassurance_detected": _BOOL,
            "false_reassurance": _BOOL,
            "corrected_assessment": _STR,
            "persisted": _BOOL,
        },
    ),
    "concerns.evaluate_risk": _schema(
        (
            "risk_level",
            "emotion_drove_risk",
            "downgraded",
            "specialized_ownership_preserved",
            "specialized_domain_id",
            "specialized_red_flags",
            "immediate",
            "escalation_recommended",
            "immediate_escalation",
            "escalation_source",
            "invented_risk",
            "malformed_input_ignored",
            "persisted",
        ),
        {
            "risk_level": _STR,
            "emotion_drove_risk": _BOOL,
            "downgraded": _BOOL,
            "specialized_ownership_preserved": _BOOL,
            "specialized_domain_id": _STR_OR_NULL,
            "specialized_red_flags": _ID_ARRAY,
            "immediate": _BOOL,
            "escalation_recommended": _BOOL,
            "immediate_escalation": _BOOL,
            "escalation_source": _STR_OR_NULL,
            "invented_risk": _BOOL,
            "malformed_input_ignored": _BOOL,
            "persisted": _BOOL,
        },
    ),
    "concerns.identify_open_questions": _schema(
        ("questions", "ritual_questions_suppressed", "malformed_input"),
        {
            "questions": _RECORDS,
            "ritual_questions_suppressed": _INT,
            "malformed_input": _BOOL,
        },
    ),
    "concerns.explore_options": _schema(
        ("options", "decision_adopted", "action_state_hint", "malformed_input"),
        {
            "options": _RECORDS,
            "decision_adopted": _BOOL,
            "action_state_hint": _STR,
            "malformed_input": _BOOL,
        },
    ),
    "concerns.prepare_next_step": _schema(
        (
            "next_step",
            "no_next_step_required",
            "action_state",
            "executed",
            "external_action_executed",
        ),
        {
            "next_step": {"type": ["object", "null"]},
            "no_next_step_required": _BOOL,
            "action_state": _STR,
            "executed": _BOOL,
            "external_action_executed": _BOOL,
        },
    ),
    "concerns.review_recurring_concern": _schema(
        (
            "recurrence",
            "meaningfully_different",
            "evidence_changed",
            "impact_changed",
            "reassurance_allowed",
            "pattern_detected",
            "missing_pattern_dimensions",
            "unchanged_evidence_visible",
            "unresolved_uncertainty_visible",
            "new_risk_invented_from_repetition",
            "pathology_inferred",
            "psychiatric_label",
            "diagnosis",
        ),
        {
            "recurrence": _STR,
            "meaningfully_different": _BOOL,
            "evidence_changed": _BOOL,
            "impact_changed": _BOOL,
            "reassurance_allowed": _BOOL,
            "pattern_detected": _BOOL,
            "missing_pattern_dimensions": _ID_ARRAY,
            "unchanged_evidence_visible": _BOOL,
            "unresolved_uncertainty_visible": _BOOL,
            "new_risk_invented_from_repetition": _BOOL,
            "pathology_inferred": _BOOL,
            "psychiatric_label": _BOOL,
            "diagnosis": _STR_OR_NULL,
        },
    ),
    "concerns.prepare_professional_discussion": _schema(
        (
            "prepared_content",
            "external_transmission_performed",
            "appointment_booked",
            "contact_performed",
            "message_sent",
            "calendar_modified",
            "memory_written",
        ),
        {
            "prepared_content": _STR,
            "external_transmission_performed": _BOOL,
            "appointment_booked": _BOOL,
            "contact_performed": _BOOL,
            "message_sent": _BOOL,
            "calendar_modified": _BOOL,
            "memory_written": _BOOL,
        },
    ),
}

_PREPARATION_ONLY = frozenset(
    {
        "concerns.prepare_next_step",
        "concerns.prepare_professional_discussion",
    }
)


def build_concerns_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build the thirteen Concerns Domain operation definitions deterministically."""
    result = []
    for operation_id in CONCERNS_OPERATION_IDS:
        operation_type = _OPERATION_TYPES[operation_id]
        operation_name = operation_id.split(".", 1)[1]
        result.append(
            DomainOperationDefinition(
                operation_id=operation_id,
                domain_id="domain:concerns",
                version="1.0.0",
                name=operation_name.replace("_", " ").title(),
                description=(
                    f"Conservative analysis/preparation operation for {operation_id}."
                ),
                operation_type=operation_type,
                input_schema=_INPUT_SCHEMAS[operation_id],
                output_schema=_OUTPUT_SCHEMAS[operation_id],
                required_resources=_REQUIRED_RESOURCES[operation_id],
                required_permissions=(),
                risk_level=PolicyRiskLevel.LOW,
                reversible=False,
                requires_approval=False,
                validation_policy_id=None,
                rollback_policy_id=None,
                enabled=True,
                metadata={
                    "phase": "10.25",
                    "domain": "concerns",
                    "analysis_or_preparation": True,
                    "proposal_only": True,
                    "preparation_only": operation_id in _PREPARATION_ONLY,
                },
            )
        )
    return tuple(result)


# ── Pure result builders (semantic cores; delegate to rule helpers) ─────────


def understand_concern_result(*, material=None) -> dict:
    """Delegate to the canonical understanding helper (rule semantics)."""
    return normalize_json_value(understand_concern(material))


def infer_support_need_result(**kwargs) -> dict:
    """Delegate to the canonical support-need inference with strict precedence."""
    allowed = {
        key: kwargs[key]
        for key in (
            "explicit_request",
            "current_signal",
            "session_context",
            "historical_preference",
        )
        if key in kwargs
    }
    return normalize_json_value(infer_support_need(**allowed))


def map_lived_experience_result(*, material=None) -> dict:
    """Delegate to the canonical lived-experience mapping."""
    return normalize_json_value(map_lived_experience(material))


def separate_reality_interpretation_result(*, statements=()) -> dict:
    """Classify statements into epistemic levels without promotion."""
    records = []
    promotions_blocked_total = 0
    malformed_structure = False
    raw, structure_malformed = _normalize_statement_collection(statements)
    malformed_structure = malformed_structure or structure_malformed
    for entry in raw:
        classified = classify_concern_statement(entry)
        if classified["promotion_blocked"]:
            promotions_blocked_total += 1
        records.append(classified)
    # An epistemic-boundary violation is present when any record was promoted
    # to fact without grounding, or a caller fact label was blocked from
    # promoting a non-fact level (frozen §18, §117).
    interpretation_promoted_to_fact = any(
        record["level"] == "fact" and record["grounded"] is False
        for record in records
    ) or any(
        _is_interpretation_labeled_fact(record) for record in records
    )
    # A catastrophic escalation is present when a possibility→probability style
    # promotion survives the epistemic separation (frozen §24).
    catastrophic_escalation_present = bool(
        promotions_blocked_total or interpretation_promoted_to_fact
    )
    return normalize_json_value(
        {
            "statements": tuple(records),
            "promotions_blocked_total": promotions_blocked_total,
            "interpretation_promoted_to_fact": interpretation_promoted_to_fact,
            "catastrophic_escalation_present": catastrophic_escalation_present,
            "malformed_input": malformed_structure,
            "persisted": False,
        }
    )


def _is_interpretation_labeled_fact(record: dict) -> bool:
    """True when a classified record that should stay interpretation was
    promoted to an external fact label (epistemic boundary violation)."""
    return bool(record.get("promotion_blocked")) and record.get("level") == "fact"


def explore_hypotheses_result(*, hypotheses=()) -> dict:
    """Preserve multiple hypotheses; no arbitrary winner, no diagnosis."""
    from datetime import datetime, timezone

    from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
    from cmm.domains.reflection.rules import evaluate_hypotheses as reflection_evaluate

    # Concerns reuses the shared Reflection hypothesis evaluator through the
    # public helper contract: multiple hypotheses, counterevidence preserved,
    # no winner, no diagnosis.  This is composition over shared contracts, not
    # a competing implementation.
    record = reflection_evaluate(hypotheses=hypotheses)
    del ReasoningRuleContext, datetime, timezone
    return normalize_json_value(
        {
            "hypotheses": record["hypotheses"],
            "winner_selected": record["winner_selected"],
            "forced_conclusion": record["forced_conclusion"],
            "no_diagnosis": record.get("no_diagnosis", True),
            "unresolved": record["unresolved"],
            "conflicting_ids": record["conflicting_ids"],
            "evidence_state": record["evidence_state"],
        }
    )


def calibrate_uncertainty_result(*, records=()) -> dict:
    """State what can, cannot and may reasonably be concluded.

    Output states follow the frozen vocabulary: established / reasonably
    supported / plausible / possible / unresolved / unsupported.  No numerical
    probability is invented.
    """
    normalized, malformed = _normalize_record_collection(records)
    calibrations = []
    uncertainty_eval = evaluate_uncertainty(
        records=tuple(
            item for item in normalized if isinstance(item, Mapping)
        )
    )
    for entry in normalized:
        if not isinstance(entry, Mapping):
            continue
        claim = entry.get("claim")
        basis_refs = (
            entry.get("basis_references")
            if isinstance(entry.get("basis_references"), (list, tuple))
            else ()
        )
        grounded_refs = [
            ref
            for ref in (_usable_ref(item) for item in basis_refs)
            if ref is not None
        ]
        stated = entry.get("status")
        status = (
            stated
            if isinstance(stated, str)
            and stated
            in (
                "established",
                "reasonably_supported",
                "plausible",
                "possible",
                "unresolved",
                "unsupported",
            )
            else None
        )
        if status is None:
            status = "established" if grounded_refs and stated == "established" else (
                "established" if grounded_refs else "unresolved"
            )
            if not grounded_refs and stated == "established":
                # An unsupported 'established' claim cannot stay established.
                status = "unsupported"
        calibrations.append(
            {
                "identity": entry.get("identity") or "unknown",
                "claim": claim if isinstance(claim, str) else None,
                "status": status,
                "grounded_reference_count": len(grounded_refs),
            }
        )
    return normalize_json_value(
        {
            "calibrations": tuple(calibrations),
            "resolved_by_invention": False,
            "conflict_present": uncertainty_eval["conflict_present"],
            "numeric_probability_invented": False,
            "malformed_input": malformed,
        }
    )


def evaluate_reassurance_result(
    *,
    target_claim=None,
    evidence=(),
    counterevidence=(),
    uncertainty=(),
    material_concerns=(),
    base_plausibility=None,
    specialized_domain_result=None,
) -> dict:
    """Delegate to the canonical reassurance evaluation."""
    record = evaluate_reassurance(
        target_claim=target_claim,
        evidence=evidence,
        counterevidence=counterevidence,
        uncertainty=uncertainty,
        material_concerns=material_concerns,
        base_plausibility=base_plausibility,
        specialized_domain_result=specialized_domain_result,
    )
    false_check = detect_false_reassurance(
        reassurance_state={"assessment": record["assessment"]},
        material_concerns=(
            record["acknowledged_concerns"]
            if record["assessment"] == "REASSURANCE_SUPPORTED"
            and record["material_concern"]
            else ()
        ),
    )
    record = dict(record)
    record["false_reassurance_detected"] = false_check["false_reassurance"]
    record["corrected_assessment"] = false_check["corrected_assessment"]
    # Gate-friendly alias required by the reassurance_review honesty gate
    # (B-003 remediation: the gate reads the field the helper actually emits).
    record["false_reassurance"] = false_check["false_reassurance"]
    return normalize_json_value(record)


def evaluate_risk_result(
    *,
    evidence=(),
    severity=None,
    immediacy=None,
    specialized_domain_result=None,
) -> dict:
    """Delegate to the canonical proportional-risk calibration."""
    record = evaluate_proportional_risk(
        evidence=evidence,
        severity=severity,
        immediacy=immediacy,
        specialized_domain_result=specialized_domain_result,
    )
    escalation = evaluate_immediate_risk_escalation(
        risk_state={"described_signal": immediacy} if immediacy else {},
        specialized_domain_result=specialized_domain_result,
    )
    record = dict(record)
    record["immediate_escalation"] = escalation["escalate"]
    record["escalation_source"] = escalation["escalation_source"]
    return normalize_json_value(record)


def identify_open_questions_result(*, questions=()) -> dict:
    """Return only materially useful questions, each with its rationale."""
    normalized, malformed = _normalize_record_collection(questions)
    evaluated = []
    ritual_suppressed = 0
    for entry in normalized:
        if not isinstance(entry, Mapping):
            malformed = True
            continue
        question_text = entry.get("question")
        changes = (
            entry.get("changes")
            if isinstance(entry.get("changes"), (list, tuple))
            else ()
        )
        materiality = evaluate_question_materiality(
            question=question_text, changes=changes
        )
        if materiality["materiality"] != QUESTION_MATERIAL:
            ritual_suppressed += 1
            continue
        evaluated.append(
            {
                "question": question_text if isinstance(question_text, str) else None,
                "materiality": materiality["materiality"],
                "why_it_matters": tuple(sorted(materiality["recognized_changes"])),
            }
        )
    return normalize_json_value(
        {
            "questions": tuple(evaluated),
            "ritual_questions_suppressed": ritual_suppressed,
            "malformed_input": malformed,
        }
    )


def explore_options_result(*, options=()) -> dict:
    """Generate realistic option candidates; none is adopted."""
    normalized, malformed = _normalize_record_collection(options)
    projected = []
    for entry in normalized:
        if not isinstance(entry, Mapping):
            malformed = True
            continue
        projected.append(
            {
                "option_id": entry.get("option_id", "unknown"),
                "expected_benefit": entry.get("expected_benefit"),
                "cost": entry.get("cost"),
                "reversibility": entry.get("reversible"),
                "uncertainty": entry.get("uncertainty"),
                "dependencies": tuple(
                    dep
                    for dep in (
                        entry.get("dependencies")
                        if isinstance(entry.get("dependencies"), (list, tuple))
                        else ()
                    )
                ),
                "adopted": False,
                "user_control_preserved": True,
            }
        )
    action = evaluate_action_state(options=options)
    return normalize_json_value(
        {
            "options": tuple(projected),
            "decision_adopted": False,
            "action_state_hint": action["state"],
            "malformed_input": malformed,
        }
    )


def prepare_next_step_result(
    *,
    desired_outcome=None,
    options=(),
    user_request=None,
    grounded_options=False,
    specialized_recommendation=False,
    specialized_domain_result=None,
) -> dict:
    """Identify one proportionate next step as a proposal; never executed."""
    action = evaluate_action_state(
        options=options,
        urgency=None,
        user_request=user_request,
        grounded_options=grounded_options,
        specialized_recommendation=specialized_recommendation,
        specialized_domain_result=specialized_domain_result,
    )
    next_step = None
    no_next_step_required = action["state"] in ("NO_ACTION_NEEDED", "USER_DECISION_REQUIRED")
    if action["state"] in ("ACTION_USEFUL", "ACTION_OPTIONAL", "ACTION_RECOMMENDED"):
        first_usable = None
        raw_options = options if isinstance(options, (list, tuple)) else ()
        for entry in raw_options:
            if isinstance(entry, Mapping):
                candidate = entry.get("option_id")
                if isinstance(candidate, str) and candidate.strip():
                    first_usable = candidate
                    break
            elif isinstance(entry, str) and entry.strip():
                first_usable = entry.strip()
                break
        if first_usable is not None:
            next_step = {
                "step": first_usable,
                "desired_outcome": (
                    desired_outcome if isinstance(desired_outcome, str) else None
                ),
                "state": action["state"],
                "proposal_only": True,
            }
    elif action["state"] == "DOMAIN_ESCALATION_NEEDED":
        next_step = {
            "step": "route to the relevant specialized domain",
            "desired_outcome": None,
            "state": action["state"],
            "proposal_only": True,
        }
        no_next_step_required = False
    return normalize_json_value(
        {
            "next_step": next_step,
            "no_next_step_required": no_next_step_required or next_step is None,
            "action_state": action["state"],
            "executed": False,
            "external_action_executed": False,
        }
    )


def review_recurring_concern_result(
    *,
    current=None,
    previous=(),
    turns=(),
) -> dict:
    """Compare recurrence against actual state; never pathologize."""
    record = review_recurring_concern_state(current=current, previous=previous)
    pattern = evaluate_repetitive_certainty_pattern(turns=turns)
    return normalize_json_value(
        {
            "recurrence": record["recurrence"],
            "meaningfully_different": record["meaningfully_different"],
            "evidence_changed": record["evidence_changed"],
            "impact_changed": record["impact_changed"],
            "reassurance_allowed": record["reassurance_allowed"],
            "pattern_detected": pattern["pattern_detected"],
            "missing_pattern_dimensions": pattern["missing_dimensions"],
            "unchanged_evidence_visible": pattern["unchanged_evidence_visible"],
            "unresolved_uncertainty_visible": pattern[
                "unresolved_uncertainty_visible"
            ],
            "new_risk_invented_from_repetition": record[
                "new_risk_invented_from_repetition"
            ],
            "pathology_inferred": (
                record["pathology_inferred"] or pattern["pathology_inferred"]
            ),
            "psychiatric_label": pattern["psychiatric_label"],
            "diagnosis": None,
        }
    )


def prepare_professional_discussion_result(
    *,
    concern_summary="",
    key_facts=(),
    open_questions=(),
    uncertainties=(),
    current_impact=None,
    documents_to_bring=(),
    decisions_required=(),
) -> dict:
    """Prepare professional-discussion *content* only.

    PREPARATION != TRANSMISSION: nothing is sent, booked, contacted, or
    transmitted.  Inputs are coerced fail-closed and never raise on malformed
    values.
    """
    def _lines(items) -> list[str]:
        if isinstance(items, str):
            items = (items,)
        elif not isinstance(items, (list, tuple)):
            return []
        usable = [
            item if isinstance(item, str) else ""
            for item in items
        ]
        return [item for item in usable if item]

    lines = [f"# Professional discussion preparation — {concern_summary if isinstance(concern_summary, str) else ''}"]
    lines.append("")
    lines.append("## Key facts")
    lines.extend(f"- {fact}" for fact in _lines(key_facts))
    lines.append("")
    lines.append("## Open questions")
    lines.extend(f"- {question}" for question in _lines(open_questions))
    lines.append("")
    lines.append("## Uncertainties")
    lines.extend(f"- {item}" for item in _lines(uncertainties))
    lines.append("")
    lines.append("## Current impact")
    impact_line = current_impact if isinstance(current_impact, str) else ""
    if impact_line:
        lines.append(f"- {impact_line}")
    else:
        lines.append("- Not stated.")
    lines.append("")
    lines.append("## Documents/sources to bring")
    lines.extend(f"- {doc}" for doc in _lines(documents_to_bring))
    lines.append("")
    lines.append("## Decisions required of the professional/user")
    lines.extend(f"- {decision}" for decision in _lines(decisions_required))
    lines.append("")
    lines.append(
        "Prepared content only: this document has not been sent to anyone."
    )
    return normalize_json_value(
        {
            "prepared_content": "\n".join(lines),
            "external_transmission_performed": False,
            "appointment_booked": False,
            "contact_performed": False,
            "message_sent": False,
            "calendar_modified": False,
            "memory_written": False,
        }
    )


# ── Shared normalization micro-helpers ──────────────────────────────────────


def _usable_ref(value) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _normalize_statement_collection(value):
    from cmm.domains.concerns.rules import _normalize_collection

    return _normalize_collection(value)


def _normalize_record_collection(value):
    from cmm.domains.concerns.rules import _normalize_collection

    return _normalize_collection(value, require_mapping_elements=True)


__all__ = [
    "CONCERNS_OPERATION_IDS",
    "build_concerns_operation_definitions",
    "calibrate_uncertainty_result",
    "evaluate_reassurance_result",
    "evaluate_risk_result",
    "explore_hypotheses_result",
    "explore_options_result",
    "identify_open_questions_result",
    "infer_support_need_result",
    "map_lived_experience_result",
    "prepare_next_step_result",
    "prepare_professional_discussion_result",
    "review_recurring_concern_result",
    "separate_reality_interpretation_result",
    "understand_concern_result",
]
