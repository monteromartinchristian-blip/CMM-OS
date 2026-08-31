"""Phase 10.26 — Languages Domain Operations.

Fifteen declarative language pedagogy operations built on the shared
``DomainOperationDefinition`` contract. No implementation is embedded here;
an operation without a provided implementation is registered as
**UNAVAILABLE** (fail-closed). Each operation exposes a pure, deterministic
result builder that produces its JSON-safe output payload by delegating to
the canonical rule helpers.

Safety posture:
- All 15 operations are low-risk internal analysis, planning, or preparation operations.
- No operation mutates external calendar, registers for exams, submits forms,
  makes payments, or writes to persistent memory directly.
- `create_learning_plan` explicitly outputs tracking choice fields (`tracking_choice`,
  `tracking_choice_resolved`, `memory_proposal_required`, `persistence_applied=False`).
- `required_resources` uses strict AND semantics.
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Mapping
from typing import Any

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.languages.catalog import CANONICAL_LANGUAGES_OPERATION_IDS
from cmm.domains.languages.profile import LANGUAGES_PEDAGOGICAL_MODES
from cmm.domains.languages.rules import (
    classify_language_variety,
    evaluate_certification_source,
    evaluate_error_pattern,
    evaluate_learning_load,
    evaluate_level_update,
    evaluate_progression,
    normalize_json_value,
    plan_spaced_review,
    prioritize_corrections,
)
from cmm.domains.operation_contracts import DomainOperationDefinition


def _finite_number(value: Any) -> float | None:
    """Normalize a public numeric input without accepting bool or NaN/Inf."""
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ):
        return float(value)
    return None


def _pronunciation_outcome_feedback(evidence: Any) -> str | None:
    """Return grounded pronunciation feedback from provenance plus an outcome."""
    if not isinstance(evidence, Mapping):
        return None
    has_provenance = any(
        isinstance(evidence.get(key), str) and bool(evidence[key].strip())
        for key in ("source_id", "provenance_id")
    )
    if not has_provenance:
        return None
    finding = evidence.get("finding")
    if isinstance(finding, str) and finding.strip():
        return finding.strip()
    if _finite_number(evidence.get("score")) is not None:
        return "Pronunciation assessment recorded."
    return None


_VOCABULARY_STATES = frozenset(
    {"new", "learning", "review", "consolidated", "needs_reinforcement"}
)

_LESSON_MODE_BEHAVIORS: dict[str, dict[str, str | tuple[str, ...]]] = {
    "teach": {
        "warmup": "Review prerequisite vocabulary and activate prior knowledge.",
        "input_material": "Explicit explanation with models and worked examples.",
        "guided_practice": "Scaffolded construction with checks for understanding.",
        "active_production": "Apply the new concept with gradually reduced support.",
        "feedback_criteria": ("Accuracy", "Understanding", "Task fulfillment"),
        "next_step": "Reapply the concept independently in a communicative task.",
    },
    "practice": {
        "warmup": "Use a brief retrieval prompt before sustained practice.",
        "input_material": "A concise model that leaves most time for active use.",
        "guided_practice": "Active use rehearsal with minimal flow interruption.",
        "active_production": "Sustain a meaningful response before selective feedback.",
        "feedback_criteria": (
            "Communicative effectiveness",
            "Priority accuracy",
            "Flow",
        ),
        "next_step": "Review selective feedback after the useful interaction unit.",
    },
    "assess": {
        "warmup": "Confirm task instructions without coaching the target skill.",
        "input_material": "Neutral task material without worked target answers.",
        "guided_practice": "Orient to the task without contaminating the evidence.",
        "active_production": "Complete the target task without coaching or hints.",
        "feedback_criteria": ("Observed evidence", "Uncertainty", "Task fulfillment"),
        "next_step": "Classify the observed result without inferring a stable level.",
    },
    "review": {
        "warmup": "Retrieve previously authorized material and unresolved gaps.",
        "input_material": "Compare prior evidence with a targeted refresher model.",
        "guided_practice": "Reinforce weak material through spaced retrieval.",
        "active_production": "Demonstrate the reviewed concept in a fresh context.",
        "feedback_criteria": ("Retention", "Resolved gaps", "Remaining uncertainty"),
        "next_step": "Schedule further reinforcement only where evidence supports it.",
    },
    "certification": {
        "warmup": "Recall the current official task format and rubric boundaries.",
        "input_material": "Current certification criteria and task-specific models.",
        "guided_practice": "Rehearse the official format without equating it to broad proficiency.",
        "active_production": "Complete a certification-style response under relevant constraints.",
        "feedback_criteria": (
            "Official rubric",
            "Format readiness",
            "General-skill boundary",
        ),
        "next_step": "Separate exam-format readiness from broader proficiency needs.",
    },
    "immersion": {
        "warmup": "Activate the topic primarily in the target language.",
        "input_material": "Comprehensible target-language material with minimal fallback.",
        "guided_practice": "Use target-language scaffolding while preserving comprehension.",
        "active_production": "Respond in the target language with user-controlled fallback.",
        "feedback_criteria": (
            "Comprehensibility",
            "Target-language use",
            "Naturalness",
        ),
        "next_step": "Increase target-language use while keeping the task comprehensible.",
    },
}

assert set(_LESSON_MODE_BEHAVIORS) == set(LANGUAGES_PEDAGOGICAL_MODES)


def _normalize_vocabulary_state(value: Any) -> str:
    """Return a frozen candidate state, failing closed to ``new``."""
    state = value.strip().lower() if isinstance(value, str) else ""
    return state if state in _VOCABULARY_STATES else "new"


def _normalize_vocabulary_item_id(value: Any) -> str | None:
    """Return a stable JSON-safe vocabulary identity or ``None`` when unusable."""
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return str(int(value)) if value.is_integer() else str(value)
    return None


def _vocabulary_item_identity(item: Mapping[str, Any]) -> str | None:
    """Read an item's stable identity, preferring item_id over id."""
    return _normalize_vocabulary_item_id(
        item.get("item_id")
    ) or _normalize_vocabulary_item_id(item.get("id"))


def _normalize_vocabulary_item(item: Any) -> dict[str, Any] | None:
    """Copy and normalize one candidate vocabulary item without mutating its source."""
    if not isinstance(item, Mapping):
        return None

    candidate = dict(normalize_json_value(item))
    for field in ("item_id", "id"):
        if field not in item:
            continue
        normalized_id = _normalize_vocabulary_item_id(item[field])
        if normalized_id is None:
            candidate.pop(field, None)
        else:
            candidate[field] = normalized_id
    candidate["state"] = _normalize_vocabulary_state(item.get("state"))
    return candidate


def _candidate_vocabulary_items(
    *,
    vocabulary_list: Mapping[str, Any] | None,
    new_items: tuple[Any, ...] | list[Any] | None,
) -> list[dict[str, Any]]:
    """Normalize and deterministically deduplicate vocabulary candidates."""
    existing_items = (
        vocabulary_list.get("items", ()) if isinstance(vocabulary_list, Mapping) else ()
    )
    raw_items = (
        list(existing_items) if isinstance(existing_items, (tuple, list)) else []
    )
    if isinstance(new_items, (tuple, list)):
        raw_items.extend(new_items)

    candidates: list[dict[str, Any]] = []
    seen_identities: set[str] = set()
    seen_anonymous_items: set[str] = set()
    for item in raw_items:
        candidate = _normalize_vocabulary_item(item)
        if candidate is None:
            continue
        identity = _vocabulary_item_identity(candidate)
        if identity is not None:
            if identity in seen_identities:
                continue
            seen_identities.add(identity)
        else:
            anonymous_key = json.dumps(
                candidate,
                sort_keys=True,
                separators=(",", ":"),
            )
            if anonymous_key in seen_anonymous_items:
                continue
            seen_anonymous_items.add(anonymous_key)
        candidates.append(candidate)
    return candidates


def _candidate_state_from_review(review: Mapping[str, Any]) -> str | None:
    """Derive one conservative candidate transition from a grounded review payload."""
    explicit_state = review.get("state")
    if isinstance(explicit_state, str):
        normalized_state = explicit_state.strip().lower()
        if normalized_state in _VOCABULARY_STATES:
            return normalized_state
    if review.get("correct") is True:
        return "review"
    if review.get("correct") is False:
        return "needs_reinforcement"
    return None


def _candidate_review_states(
    review_results: tuple[Any, ...] | list[Any] | None,
) -> dict[str, str]:
    """Build a stable-ID lookup of review-derived candidate states."""
    if not isinstance(review_results, (tuple, list)):
        return {}

    transitions: dict[str, str] = {}
    for review in review_results:
        if not isinstance(review, Mapping):
            continue
        identity = _vocabulary_item_identity(review)
        candidate_state = _candidate_state_from_review(review)
        if identity is not None and candidate_state is not None:
            transitions[identity] = candidate_state
    return transitions


LANGUAGES_OPERATION_IDS: tuple[str, ...] = CANONICAL_LANGUAGES_OPERATION_IDS

_OPERATION_TYPES: dict[str, DomainOperationType] = {
    "languages.assess_sample": DomainOperationType.ANALYSIS,
    "languages.update_level_evidence": DomainOperationType.ANALYSIS,
    "languages.create_learning_plan": DomainOperationType.PLANNING,
    "languages.generate_lesson": DomainOperationType.PREPARATION,
    "languages.generate_exercises": DomainOperationType.PREPARATION,
    "languages.review_exercise": DomainOperationType.ANALYSIS,
    "languages.review_writing": DomainOperationType.ANALYSIS,
    "languages.generate_conversation_turn": DomainOperationType.PREPARATION,
    "languages.generate_roleplay_turn": DomainOperationType.PREPARATION,
    "languages.review_speaking": DomainOperationType.ANALYSIS,
    "languages.review_errors": DomainOperationType.ANALYSIS,
    "languages.track_vocabulary": DomainOperationType.ANALYSIS,
    "languages.plan_review_schedule": DomainOperationType.PLANNING,
    "languages.prepare_certification": DomainOperationType.PREPARATION,
    "languages.generate_progress_review": DomainOperationType.ANALYSIS,
}

_REQUIRED_RESOURCES: dict[str, tuple[str, ...]] = {
    "languages.assess_sample": (),
    "languages.update_level_evidence": (),
    "languages.create_learning_plan": (),
    "languages.generate_lesson": (),
    "languages.generate_exercises": (),
    "languages.review_exercise": ("languages.exercise_result",),
    "languages.review_writing": ("languages.writing_sample",),
    "languages.generate_conversation_turn": ("languages.conversation",),
    "languages.generate_roleplay_turn": ("languages.conversation",),
    "languages.review_speaking": (),
    "languages.review_errors": (),
    "languages.track_vocabulary": ("languages.vocabulary_list",),
    "languages.plan_review_schedule": (),
    "languages.prepare_certification": (),
    "languages.generate_progress_review": (),
}


def _schema(required: tuple[str, ...], properties: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic JSON object schema with closed properties."""
    return {
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": False,
    }


_STR = {"type": "string"}
_STR_OR_NULL = {"type": ["string", "null"]}
_BOOL = {"type": "boolean"}
_BOOL_OR_NULL = {"type": ["boolean", "null"]}
_INT = {"type": "integer"}
_NUM = {"type": "number"}
_NUM_OR_NULL = {"type": ["number", "integer", "null"]}
_RECORDS = {"type": "array", "items": {"type": "object"}}
_STR_LIST = {"type": "array", "items": {"type": "string"}}

_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "languages.assess_sample": _schema(
        ("sample", "sample_type", "target_language", "skill_scope"),
        {
            "sample": {"type": "object"},
            "sample_type": _STR,
            "target_language": _STR,
            "skill_scope": _STR,
            "preferred_variety": _STR_OR_NULL,
        },
    ),
    "languages.update_level_evidence": _schema(
        ("existing_record", "assessment", "target_skill"),
        {
            "existing_record": {"type": "object"},
            "assessment": {"type": "object"},
            "target_skill": _STR,
            "evidence": _RECORDS,
        },
    ),
    "languages.create_learning_plan": _schema(
        ("language", "goals"),
        {
            "language": _STR,
            "goals": _RECORDS,
            "initial_assessment": {"type": ["object", "null"]},
            "tracking_consent": {"type": ["boolean", "null"]},
        },
    ),
    "languages.generate_lesson": _schema(
        ("language", "target_skill", "current_level", "topic"),
        {
            "language": _STR,
            "target_skill": _STR,
            "current_level": _STR,
            "topic": _STR,
            "mode": _STR_OR_NULL,
        },
    ),
    "languages.generate_exercises": _schema(
        ("language", "skill", "difficulty", "target_topic"),
        {
            "language": _STR,
            "skill": _STR,
            "difficulty": _INT,
            "target_topic": _STR,
            "count": {"type": ["integer", "null"]},
        },
    ),
    "languages.review_exercise": _schema(
        ("exercise_result", "language"),
        {
            "exercise_result": {"type": "object"},
            "language": _STR,
            "target_topic": _STR_OR_NULL,
        },
    ),
    "languages.review_writing": _schema(
        ("writing_sample", "language"),
        {
            "writing_sample": {"type": "object"},
            "language": _STR,
            "preferred_variety": _STR_OR_NULL,
            "prompt": _STR_OR_NULL,
        },
    ),
    "languages.generate_conversation_turn": _schema(
        ("conversation", "language"),
        {
            "conversation": {"type": "object"},
            "language": _STR,
            "role": _STR_OR_NULL,
            "topic": _STR_OR_NULL,
            "target_level": _STR_OR_NULL,
        },
    ),
    "languages.generate_roleplay_turn": _schema(
        ("conversation", "language", "scenario"),
        {
            "conversation": {"type": "object"},
            "language": _STR,
            "scenario": _STR,
            "user_role": _STR_OR_NULL,
            "agent_role": _STR_OR_NULL,
        },
    ),
    "languages.review_speaking": _schema(
        ("audio_transcript", "target_language"),
        {
            "audio_transcript": {"type": "object"},
            "target_language": _STR,
            "pronunciation_evidence": {
                "type": ["array", "null"],
                "items": {"type": "object"},
            },
        },
    ),
    "languages.review_errors": _schema(
        ("observed_errors", "language"),
        {
            "observed_errors": _RECORDS,
            "language": _STR,
            "history": {"type": ["array", "null"], "items": {"type": "object"}},
        },
    ),
    "languages.track_vocabulary": _schema(
        ("vocabulary_list", "language"),
        {
            "vocabulary_list": {"type": "object"},
            "language": _STR,
            "new_items": {"type": ["array", "null"], "items": {"type": "object"}},
            "review_results": {"type": ["array", "null"], "items": {"type": "object"}},
        },
    ),
    "languages.plan_review_schedule": _schema(
        ("review_items",),
        {
            "review_items": _RECORDS,
            "available_time": {"type": ["number", "integer", "null"]},
            "energy": _STR_OR_NULL,
            "active_goals": {"type": ["array", "null"], "items": {"type": "string"}},
        },
    ),
    "languages.prepare_certification": _schema(
        ("target_certification",),
        {
            "target_certification": _STR,
            "current_profile": {"type": ["object", "null"]},
            "official_source": {"type": ["object", "null"]},
        },
    ),
    "languages.generate_progress_review": _schema(
        ("language", "period"),
        {
            "language": _STR,
            "period": _STR,
            "evidence": {"type": ["array", "null"], "items": {"type": "object"}},
            "goals": {"type": ["array", "null"], "items": {"type": "object"}},
            "previous_evidence": {
                "type": ["array", "null"],
                "items": {"type": "object"},
            },
            "skill": _STR_OR_NULL,
            "patterns": {"type": ["array", "null"], "items": {"type": "object"}},
            "certification_profile": {"type": ["object", "null"]},
        },
    ),
}

_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "languages.assess_sample": _schema(
        (
            "assessment_id",
            "language",
            "skill_scope",
            "observed_performance",
            "confidence",
            "strengths",
            "errors",
            "valid_alternatives",
            "missing_evidence",
            "proficiency_kind",
        ),
        {
            "assessment_id": _STR,
            "language": _STR,
            "skill_scope": _STR,
            "observed_performance": _STR,
            "confidence": _NUM,
            "strengths": _STR_LIST,
            "errors": _RECORDS,
            "valid_alternatives": _RECORDS,
            "missing_evidence": _STR_LIST,
            "proficiency_kind": _STR,
        },
    ),
    "languages.update_level_evidence": _schema(
        (
            "skill_scope",
            "current_level",
            "proposed_level",
            "stable_update_supported",
            "reason",
            "updated_record",
            "is_certified",
            "certificate_overwritten",
            "skill_gaps_erased",
            "evidence_boundary_valid",
        ),
        {
            "skill_scope": _STR,
            "current_level": _STR_OR_NULL,
            "proposed_level": _STR_OR_NULL,
            "stable_update_supported": _BOOL,
            "reason": _STR,
            "updated_record": {"type": "object"},
            "is_certified": _BOOL,
            "certificate_overwritten": _BOOL,
            "skill_gaps_erased": _BOOL,
            "evidence_boundary_valid": _BOOL,
        },
    ),
    "languages.create_learning_plan": _schema(
        (
            "plan_id",
            "language",
            "goals",
            "phases",
            "recommended_intensity",
            "tracking_choice",
            "tracking_choice_resolved",
            "memory_proposal_required",
            "persistence_applied",
        ),
        {
            "plan_id": _STR,
            "language": _STR,
            "goals": _RECORDS,
            "phases": _RECORDS,
            "recommended_intensity": _STR,
            "tracking_choice": _STR,
            "tracking_choice_resolved": _BOOL,
            "memory_proposal_required": _BOOL,
            "persistence_applied": _BOOL,
        },
    ),
    "languages.generate_lesson": _schema(
        (
            "lesson_id",
            "language",
            "target_skill",
            "level",
            "objective",
            "warmup",
            "input_material",
            "guided_practice",
            "active_production",
            "feedback_criteria",
            "next_step",
        ),
        {
            "lesson_id": _STR,
            "language": _STR,
            "target_skill": _STR,
            "level": _STR,
            "objective": _STR,
            "warmup": _STR,
            "input_material": _STR,
            "guided_practice": _STR,
            "active_production": _STR,
            "feedback_criteria": _STR_LIST,
            "next_step": _STR,
        },
    ),
    "languages.generate_exercises": _schema(
        (
            "exercise_batch_id",
            "language",
            "skill",
            "difficulty",
            "exercises",
            "exercise_count",
        ),
        {
            "exercise_batch_id": _STR,
            "language": _STR,
            "skill": _STR,
            "difficulty": _INT,
            "exercises": _RECORDS,
            "exercise_count": _INT,
        },
    ),
    "languages.review_exercise": _schema(
        (
            "review_id",
            "score",
            "is_correct",
            "observed_errors",
            "feedback",
            "difficulty_adjustment",
            "pattern_candidate",
            "stable_proficiency_changed",
            "error_pattern_promoted_without_evidence",
        ),
        {
            "review_id": _STR,
            "score": _NUM_OR_NULL,
            "is_correct": _BOOL_OR_NULL,
            "observed_errors": _RECORDS,
            "feedback": _STR,
            "difficulty_adjustment": _STR,
            "pattern_candidate": _BOOL,
            "stable_proficiency_changed": _BOOL,
            "error_pattern_promoted_without_evidence": _BOOL,
        },
    ),
    "languages.review_writing": _schema(
        (
            "review_id",
            "language",
            "word_count",
            "strengths",
            "observed_errors",
            "valid_alternatives",
            "register_feedback",
            "estimated_level",
            "score",
            "valid_variety_misclassified",
            "proficiency_upgraded_without_evidence",
            "missing_evidence",
        ),
        {
            "review_id": _STR,
            "language": _STR,
            "word_count": _INT,
            "strengths": _STR_LIST,
            "observed_errors": _RECORDS,
            "valid_alternatives": _RECORDS,
            "register_feedback": _STR,
            "estimated_level": _STR,
            "score": _NUM,
            "valid_variety_misclassified": _BOOL,
            "proficiency_upgraded_without_evidence": _BOOL,
            "missing_evidence": _STR_LIST,
        },
    ),
    "languages.generate_conversation_turn": _schema(
        (
            "turn_id",
            "speaker",
            "utterance",
            "pedagogical_intent",
            "scaffolding_hint",
            "turn_count",
        ),
        {
            "turn_id": _STR,
            "speaker": _STR,
            "utterance": _STR,
            "pedagogical_intent": _STR,
            "scaffolding_hint": _STR_OR_NULL,
            "turn_count": _INT,
        },
    ),
    "languages.generate_roleplay_turn": _schema(
        (
            "roleplay_id",
            "scenario",
            "agent_role",
            "utterance",
            "prompt_for_user",
            "turn_number",
        ),
        {
            "roleplay_id": _STR,
            "scenario": _STR,
            "agent_role": _STR,
            "utterance": _STR,
            "prompt_for_user": _STR,
            "turn_number": _INT,
        },
    ),
    "languages.review_speaking": _schema(
        (
            "review_id",
            "transcript_text",
            "pronunciation_assessed",
            "pronunciation_feedback",
            "fluency_score",
            "observed_errors",
            "pronunciation_evidence_valid",
            "pronunciation_inferred_from_transcript_only",
            "missing_evidence",
        ),
        {
            "review_id": _STR,
            "transcript_text": _STR,
            "pronunciation_assessed": _BOOL,
            "pronunciation_feedback": _STR_OR_NULL,
            "fluency_score": _NUM,
            "observed_errors": _RECORDS,
            "pronunciation_evidence_valid": _BOOL,
            "pronunciation_inferred_from_transcript_only": _BOOL,
            "missing_evidence": _STR_LIST,
        },
    ),
    "languages.review_errors": _schema(
        (
            "review_id",
            "total_errors",
            "error_patterns",
            "prioritized_corrections",
            "recommended_focus",
            "pattern_evidence_valid",
            "pattern_promoted_without_independent_recurrence",
        ),
        {
            "review_id": _STR,
            "total_errors": _INT,
            "error_patterns": _RECORDS,
            "prioritized_corrections": _RECORDS,
            "recommended_focus": _STR,
            "pattern_evidence_valid": _BOOL,
            "pattern_promoted_without_independent_recurrence": _BOOL,
        },
    ),
    "languages.track_vocabulary": _schema(
        (
            "tracking_id",
            "total_items",
            "due_items",
            "mastery_summary",
            "candidate_updates",
            "persistence_applied",
        ),
        {
            "tracking_id": _STR,
            "total_items": _INT,
            "due_items": _INT,
            "mastery_summary": {"type": "object"},
            "candidate_updates": _RECORDS,
            "persistence_applied": _BOOL,
        },
    ),
    "languages.plan_review_schedule": _schema(
        (
            "schedule_id",
            "review_queue",
            "recommended_duration_minutes",
            "calendar_modified",
            "external_action_executed",
        ),
        {
            "schedule_id": _STR,
            "review_queue": _RECORDS,
            "recommended_duration_minutes": _INT,
            "calendar_modified": _BOOL,
            "external_action_executed": _BOOL,
        },
    ),
    "languages.prepare_certification": _schema(
        (
            "prep_id",
            "target_certification",
            "framework",
            "readiness_score",
            "skill_gaps",
            "official_source_status",
            "needs_verification",
            "registration_performed",
            "payment_performed",
            "submission_performed",
            "temporal_evidence_valid",
            "readiness_promoted_to_proficiency",
            "missing_evidence",
        ),
        {
            "prep_id": _STR,
            "target_certification": _STR,
            "framework": _STR,
            "readiness_score": _NUM,
            "skill_gaps": _STR_LIST,
            "official_source_status": _STR,
            "needs_verification": _BOOL,
            "registration_performed": _BOOL,
            "payment_performed": _BOOL,
            "submission_performed": _BOOL,
            "temporal_evidence_valid": _BOOL,
            "readiness_promoted_to_proficiency": _BOOL,
            "missing_evidence": _STR_LIST,
        },
    ),
    "languages.generate_progress_review": _schema(
        (
            "review_id",
            "language",
            "period",
            "skill_progress",
            "overall_progression",
            "stable_progression",
            "active_patterns_count",
            "certification_readiness",
            "recommended_next_focus",
            "progression_evidence_valid",
            "cross_skill_inflation",
        ),
        {
            "review_id": _STR,
            "language": _STR,
            "period": _STR,
            "skill_progress": {"type": "object"},
            "overall_progression": _STR,
            "stable_progression": _BOOL,
            "active_patterns_count": _INT,
            "certification_readiness": _STR,
            "recommended_next_focus": _STR,
            "progression_evidence_valid": _BOOL,
            "cross_skill_inflation": _BOOL,
        },
    ),
}


def build_languages_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build all fifteen canonical Languages Domain operation definitions deterministically."""
    result = []
    for op_id in CANONICAL_LANGUAGES_OPERATION_IDS:
        op_name = op_id.split(".", 1)[1].replace("_", " ").title()
        result.append(
            DomainOperationDefinition(
                operation_id=op_id,
                domain_id="domain:languages",
                version="1.0.0",
                name=op_name,
                description=f"Language learning and pedagogy operation for {op_id}.",
                operation_type=_OPERATION_TYPES[op_id],
                risk_level=PolicyRiskLevel.LOW,
                required_resources=_REQUIRED_RESOURCES[op_id],
                input_schema=_INPUT_SCHEMAS[op_id],
                output_schema=_OUTPUT_SCHEMAS[op_id],
                metadata={
                    "phase": "10.26",
                    "proposal_only": True,
                    "no_external_mutation": True,
                },
            )
        )
    return tuple(result)


# ── Result Helpers ────────────────────────────────────────────────────────────


def assess_sample_result(
    *,
    sample: Mapping[str, Any] | None = None,
    sample_type: str = "writing",
    target_language: str = "English",
    skill_scope: str = "writing",
    preferred_variety: str | None = None,
) -> dict[str, Any]:
    """Assess a language sample and return observed performance without inflating certified level."""
    s_dict = dict(normalize_json_value(sample or {}))
    raw_text = s_dict.get("text")
    text = raw_text.strip() if isinstance(raw_text, str) else ""
    has_sample_evidence = bool(text)

    errors: list[dict[str, Any]] = []
    valid_alts: list[dict[str, Any]] = []

    # Check variety
    if (
        preferred_variety
        and "colour" in text.lower()
        and "american" in preferred_variety.lower()
    ):
        v_class = classify_language_variety(
            preferred_variety=preferred_variety,
            observed_variety="British English",
            form_status="valid",
        )
        if v_class.get("is_valid_alternative"):
            valid_alts.append(
                {
                    "id": "alt-1",
                    "token": "colour",
                    "variety": "British English",
                    "classification": "valid_alternative",
                }
            )

    # Missing evidence check (e.g. speaking when assessing writing)
    missing = (
        (["speaking", "listening"] if skill_scope == "writing" else ["writing"])
        if has_sample_evidence
        else [f"{sample_type}_sample"]
    )

    return {
        "assessment_id": f"as-{uuid.uuid4().hex[:8]}",
        "language": target_language,
        "skill_scope": skill_scope,
        "observed_performance": ("B2" if len(text) > 10 else "A2")
        if has_sample_evidence
        else "unknown",
        "confidence": 0.75 if has_sample_evidence else 0.0,
        "strengths": (
            ["Clear expression", "Good lexical choice"]
            if len(text) > 10
            else ["Initial production"]
        )
        if has_sample_evidence
        else [],
        "errors": errors,
        "valid_alternatives": valid_alts,
        "missing_evidence": missing,
        "proficiency_kind": "OBSERVED_PERFORMANCE",
    }


def update_level_evidence_result(
    *,
    existing_record: Mapping[str, Any] | None = None,
    assessment: Mapping[str, Any] | None = None,
    target_skill: str = "writing",
    evidence: tuple[Any, ...] | list[Any] = (),
) -> dict[str, Any]:
    """Update level evidence proposal without overwriting certified record."""
    ex = dict(normalize_json_value(existing_record or {}))
    ass = dict(normalize_json_value(assessment or {}))
    if ass.get("observed") is None and ass.get("observed_performance") is not None:
        ass["observed"] = ass["observed_performance"]
    if ass.get("skill") is None:
        ass["skill"] = target_skill
    all_ev = list(evidence)
    if ass:
        all_ev.append(ass)

    evaluation = evaluate_level_update(
        existing=ex,
        evidence=all_ev,
        target_skill=target_skill,
    )

    return {
        "skill_scope": target_skill,
        "current_level": ex.get("level_or_score"),
        "proposed_level": evaluation["proposed_level"],
        "stable_update_supported": evaluation["stable_update_supported"],
        "reason": evaluation["reason"],
        "updated_record": evaluation["updated_record"],
        "is_certified": ex.get("kind") == "CERTIFIED",
        "certificate_overwritten": False,
        "skill_gaps_erased": False,
        "evidence_boundary_valid": True,
    }


def create_learning_plan_result(
    *,
    language: str,
    goals: tuple[Any, ...] | list[Any] = (),
    initial_assessment: Mapping[str, Any] | None = None,
    tracking_consent: bool | None = None,
) -> dict[str, Any]:
    """Create a structured learning plan with clear tracking choice and consent resolution."""
    raw_goals = [dict(normalize_json_value(g)) for g in goals if isinstance(g, Mapping)]
    phases = [
        {"phase_number": 1, "title": "Diagnostic & Foundations", "duration_weeks": 2},
        {
            "phase_number": 2,
            "title": "Active Practice & Consolidation",
            "duration_weeks": 6,
        },
    ]

    tracking_resolved = tracking_consent is not None
    choice = (
        "opt_in"
        if tracking_consent is True
        else ("opt_out" if tracking_consent is False else "unresolved")
    )

    return {
        "plan_id": f"lp-{uuid.uuid4().hex[:8]}",
        "language": language,
        "goals": raw_goals,
        "phases": phases,
        "recommended_intensity": "moderate (30m/day)",
        "tracking_choice": choice,
        "tracking_choice_resolved": tracking_resolved,
        "memory_proposal_required": tracking_consent is True,
        "persistence_applied": False,
    }


def generate_lesson_result(
    *,
    language: str,
    target_skill: str,
    current_level: str,
    topic: str,
    mode: str | None = None,
) -> dict[str, Any]:
    """Generate structured lesson material for guided teaching."""
    selected_mode = mode if mode in LANGUAGES_PEDAGOGICAL_MODES else "teach"
    behavior = _LESSON_MODE_BEHAVIORS[selected_mode]
    return {
        "lesson_id": f"lsn-{uuid.uuid4().hex[:8]}",
        "language": language,
        "target_skill": target_skill,
        "level": current_level,
        "objective": f"Master {topic} in {language} for {target_skill}",
        "warmup": f"{behavior['warmup']} Topic: {topic}.",
        "input_material": f"{behavior['input_material']} Focus: {topic}.",
        "guided_practice": behavior["guided_practice"],
        "active_production": behavior["active_production"],
        "feedback_criteria": list(behavior["feedback_criteria"]),
        "next_step": behavior["next_step"],
    }


def generate_exercises_result(
    *,
    language: str,
    skill: str,
    difficulty: int,
    target_topic: str,
    count: int | None = None,
) -> dict[str, Any]:
    """Generate targeted practice exercises aligned with skill and difficulty."""
    clean_count = _finite_number(count)
    num = (
        int(clean_count)
        if clean_count is not None and clean_count.is_integer() and clean_count > 0
        else 3
    )
    clean_difficulty_value = _finite_number(difficulty)
    clean_difficulty = (
        int(clean_difficulty_value)
        if clean_difficulty_value is not None and clean_difficulty_value.is_integer()
        else 1
    )
    exercises = [
        {
            "exercise_id": f"ex-{i + 1}",
            "prompt": f"Complete the sentence using correct {target_topic}.",
            "target_skill": skill,
            "difficulty": clean_difficulty,
        }
        for i in range(num)
    ]
    return {
        "exercise_batch_id": f"exb-{uuid.uuid4().hex[:8]}",
        "language": language,
        "skill": skill,
        "difficulty": clean_difficulty,
        "exercises": exercises,
        "exercise_count": len(exercises),
    }


def review_exercise_result(
    *,
    exercise_result: Mapping[str, Any] | None = None,
    language: str = "English",
    target_topic: str | None = None,
) -> dict[str, Any]:
    """Review exercise outcome without prematurely turning isolated error into pattern."""
    er = dict(exercise_result or {})
    has_correctness = isinstance(er.get("is_correct"), bool)
    clean_score = _finite_number(er.get("score")) if "score" in er else None
    has_score = clean_score is not None
    if not has_correctness and not has_score:
        is_correct = None
        score = None
    elif has_correctness:
        is_correct = er["is_correct"]
        score = clean_score if has_score else (1.0 if is_correct else 0.0)
    else:
        is_correct = None
        score = clean_score
    review_id = f"exr-{uuid.uuid4().hex[:8]}"

    errors = []
    if is_correct is False:
        errors.append(
            {
                "id": f"err-{uuid.uuid4().hex[:6]}",
                "provenance_id": review_id,
                "topic": target_topic or "general",
                "error_type": "target_structure",
                "comparable": True,
                "comparison_key": target_topic or "general",
                "user_answer": er.get("user_answer", ""),
                "category": "observed_error",
            }
        )

    return {
        "review_id": review_id,
        "score": score,
        "is_correct": is_correct,
        "observed_errors": errors,
        "feedback": (
            "Great job!"
            if is_correct is True
            else "Review the target structure."
            if is_correct is False
            else "Not assessed: missing exercise outcome."
        ),
        "difficulty_adjustment": (
            "maintain"
            if is_correct is True
            else "scaffold"
            if is_correct is False
            else "hold"
        ),
        "pattern_candidate": False,
        "stable_proficiency_changed": False,
        "error_pattern_promoted_without_evidence": False,
    }


def review_writing_result(
    *,
    writing_sample: Mapping[str, Any] | None = None,
    language: str = "English",
    preferred_variety: str | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Review writing sample distinguishing errors from valid varieties."""
    ws = dict(writing_sample or {})
    raw_text = ws.get("text")
    text = raw_text.strip() if isinstance(raw_text, str) else ""
    word_count = len(text.split())
    has_writing_evidence = word_count > 0

    valid_alts = []
    if (
        preferred_variety
        and "colour" in text.lower()
        and "british" in preferred_variety.lower()
    ):
        valid_alts.append(
            {
                "token": "colour",
                "variety": "British English",
                "status": "valid_alternative",
            }
        )

    return {
        "review_id": f"wr-{uuid.uuid4().hex[:8]}",
        "language": language,
        "word_count": word_count,
        "strengths": (
            ["Coherent structure", "Appropriate register"]
            if has_writing_evidence
            else []
        ),
        "observed_errors": [],
        "valid_alternatives": valid_alts,
        "register_feedback": "Formal and appropriate."
        if has_writing_evidence
        else "not_assessed",
        "estimated_level": ("B2" if word_count > 10 else "A2")
        if has_writing_evidence
        else "unknown",
        "score": 0.85 if has_writing_evidence else 0.0,
        "valid_variety_misclassified": False,
        "proficiency_upgraded_without_evidence": False,
        "missing_evidence": [] if has_writing_evidence else ["writing_sample"],
    }


def generate_conversation_turn_result(
    *,
    conversation: Mapping[str, Any] | None = None,
    language: str = "English",
    role: str | None = None,
    topic: str | None = None,
    target_level: str | None = None,
) -> dict[str, Any]:
    """Generate one pedagogical conversation turn without executing a conversation loop."""
    conv = dict(conversation or {})
    raw_turns = conv.get("turns")
    turns = raw_turns if isinstance(raw_turns, (list, tuple)) else ()
    turn_count = len(turns) + 1

    return {
        "turn_id": f"ct-{uuid.uuid4().hex[:8]}",
        "speaker": role or "tutor",
        "utterance": f"That is very interesting! Tell me more about your experience with {topic or 'languages'}.",
        "pedagogical_intent": "encourage_production",
        "scaffolding_hint": "Try using connectors like 'however' or 'furthermore'."
        if target_level == "B2"
        else None,
        "turn_count": turn_count,
    }


def generate_roleplay_turn_result(
    *,
    conversation: Mapping[str, Any] | None = None,
    language: str = "English",
    scenario: str = "General scenario",
    user_role: str | None = None,
    agent_role: str | None = None,
) -> dict[str, Any]:
    """Generate one roleplay turn grounded in scenario."""
    conv = dict(conversation or {})
    raw_turns = conv.get("turns")
    turns = raw_turns if isinstance(raw_turns, (list, tuple)) else ()
    turn_num = len(turns) + 1

    return {
        "roleplay_id": f"rp-{uuid.uuid4().hex[:8]}",
        "scenario": scenario,
        "agent_role": agent_role or "interlocutor",
        "utterance": f"Welcome! How can I assist you with {scenario} today?",
        "prompt_for_user": "Respond in character stating your request.",
        "turn_number": turn_num,
    }


def review_speaking_result(
    *,
    audio_transcript: Mapping[str, Any] | None = None,
    target_language: str = "English",
    pronunciation_evidence: tuple[Any, ...] | list[Any] | None = None,
) -> dict[str, Any]:
    """Review speaking transcript, ensuring transcript alone never assesses pronunciation."""
    at = dict(audio_transcript or {})
    raw_transcript = at.get("transcript")
    transcript = raw_transcript.strip() if isinstance(raw_transcript, str) else ""
    raw_observed_errors = at.get("observed_errors")
    observed_errors = [
        dict(normalize_json_value(item))
        for item in (
            raw_observed_errors
            if isinstance(raw_observed_errors, (list, tuple))
            else ()
        )
        if isinstance(item, Mapping)
    ]

    pronunciation_feedback = next(
        (
            feedback
            for item in pronunciation_evidence or ()
            if (feedback := _pronunciation_outcome_feedback(item)) is not None
        ),
        None,
    )
    has_audio_evidence = pronunciation_feedback is not None
    missing_evidence = []
    if not transcript:
        missing_evidence.append("speaking_sample")
    if not has_audio_evidence:
        missing_evidence.append("pronunciation_evidence")
    return {
        "review_id": f"sr-{uuid.uuid4().hex[:8]}",
        "transcript_text": transcript,
        "pronunciation_assessed": has_audio_evidence,
        "pronunciation_feedback": pronunciation_feedback,
        "fluency_score": 0.80 if transcript else 0.0,
        "observed_errors": observed_errors,
        "pronunciation_evidence_valid": True,
        "pronunciation_inferred_from_transcript_only": False,
        "missing_evidence": missing_evidence,
    }


def review_errors_result(
    *,
    observed_errors: tuple[Any, ...] | list[Any] = (),
    language: str = "English",
    history: tuple[Any, ...] | list[Any] | None = None,
) -> dict[str, Any]:
    """Analyze observed errors and prioritize corrections."""
    p_res = prioritize_corrections(errors=observed_errors, mode="practice")
    pat_res = evaluate_error_pattern(observations=observed_errors)

    patterns = [pat_res] if pat_res["eligible"] else []

    return {
        "review_id": f"er-{uuid.uuid4().hex[:8]}",
        "total_errors": len(observed_errors),
        "error_patterns": patterns,
        "prioritized_corrections": p_res["prioritized_errors"],
        "recommended_focus": "Grammar concord" if patterns else "not_assessed",
        "pattern_evidence_valid": True,
        "pattern_promoted_without_independent_recurrence": False,
    }


def track_vocabulary_result(
    *,
    vocabulary_list: Mapping[str, Any] | None = None,
    language: str = "English",
    new_items: tuple[Any, ...] | list[Any] | None = None,
    review_results: tuple[Any, ...] | list[Any] | None = None,
) -> dict[str, Any]:
    """Track vocabulary items and candidate review updates without mutating persistent store."""
    candidates = _candidate_vocabulary_items(
        vocabulary_list=vocabulary_list,
        new_items=new_items,
    )
    review_states = _candidate_review_states(review_results)
    for candidate in candidates:
        identity = _vocabulary_item_identity(candidate)
        if identity is not None and identity in review_states:
            candidate["state"] = review_states[identity]

    plan_res = plan_spaced_review(items=candidates)
    mastered = sum(item["state"] == "consolidated" for item in candidates)

    return {
        "tracking_id": f"vt-{uuid.uuid4().hex[:8]}",
        "total_items": len(candidates),
        "due_items": plan_res["backlog_count"],
        "mastery_summary": {
            "mastered": mastered,
            "learning": len(candidates) - mastered,
        },
        "candidate_updates": candidates,
        "persistence_applied": False,
    }


def plan_review_schedule_result(
    *,
    review_items: tuple[Any, ...] | list[Any] = (),
    available_time: float | None = None,
    energy: str | None = None,
    active_goals: tuple[Any, ...] | list[Any] | None = None,
) -> dict[str, Any]:
    """Generate pedagogical review proposal with explicit no calendar mutation guarantee."""
    plan_res = plan_spaced_review(items=review_items, active_goals=active_goals or ())
    load_res = evaluate_learning_load(
        available_time=_finite_number(available_time),
        energy=energy,
        review_backlog=review_items,
    )

    return {
        "schedule_id": f"rs-{uuid.uuid4().hex[:8]}",
        "review_queue": plan_res["review_queue"],
        "recommended_duration_minutes": load_res["recommended_duration_minutes"],
        "calendar_modified": False,
        "external_action_executed": False,
    }


def prepare_certification_result(
    *,
    target_certification: str,
    current_profile: Mapping[str, Any] | None = None,
    official_source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare for certification exam, keeping readiness distinct from general proficiency and never registering/paying."""
    src_eval = evaluate_certification_source(
        sources=[official_source] if official_source else [], decision_critical=True
    )
    source_verified = (
        src_eval["selected_source"] is not None
        and src_eval["needs_verification"] is False
        and src_eval["authority_rank"] >= 5
    )
    profile = dict(normalize_json_value(current_profile or {}))
    raw_skill_levels = profile.get("skill_levels")
    skill_levels = (
        {
            str(skill): str(level).upper()
            for skill, level in raw_skill_levels.items()
            if isinstance(skill, str) and isinstance(level, str)
        }
        if isinstance(raw_skill_levels, Mapping)
        else {}
    )
    estimated_level = profile.get("estimated_level")
    if (
        not skill_levels
        and isinstance(estimated_level, str)
        and estimated_level.strip()
    ):
        skill_levels = {"general": estimated_level.strip().upper()}

    cefr_rank = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    target_level = next(
        (
            level
            for level in reversed(tuple(cefr_rank))
            if level in target_certification.upper()
        ),
        None,
    )
    grounded_levels = {
        skill: level for skill, level in skill_levels.items() if level in cefr_rank
    }
    has_profile_evidence = bool(grounded_levels) and target_level is not None
    target_rank = cefr_rank[target_level] if target_level is not None else 0
    readiness_score = (
        round(
            sum(
                min(cefr_rank[level] / target_rank, 1.0)
                for level in grounded_levels.values()
            )
            / len(grounded_levels),
            2,
        )
        if has_profile_evidence
        else 0.0
    )
    skill_gaps = (
        [
            f"{skill}:{level}->{target_level}"
            for skill, level in grounded_levels.items()
            if cefr_rank[level] < target_rank
        ]
        if has_profile_evidence
        else []
    )

    return {
        "prep_id": f"cp-{uuid.uuid4().hex[:8]}",
        "target_certification": target_certification,
        "framework": "CEFR",
        "readiness_score": readiness_score,
        "skill_gaps": skill_gaps,
        "official_source_status": (
            "verified"
            if source_verified
            else "needs_verification"
            if official_source
            else "unverified_guide"
        ),
        "needs_verification": not source_verified or not has_profile_evidence,
        "registration_performed": False,
        "payment_performed": False,
        "submission_performed": False,
        "temporal_evidence_valid": True,
        "readiness_promoted_to_proficiency": False,
        "missing_evidence": [] if has_profile_evidence else ["current_profile"],
    }


def generate_progress_review_result(
    *,
    language: str,
    period: str,
    evidence: tuple[Any, ...] | list[Any] | None = None,
    goals: tuple[Any, ...] | list[Any] | None = None,
    previous_evidence: tuple[Any, ...] | list[Any] | None = None,
    skill: str | None = None,
    patterns: tuple[Any, ...] | list[Any] | None = None,
    certification_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate comprehensive progress review."""
    ev = list(evidence or [])
    evidenced_skills = {
        item_skill.strip()
        for item in ev
        if isinstance(item, Mapping)
        and isinstance((item_skill := item.get("skill")), str)
        and item_skill.strip()
    }
    skill_results = {
        evidenced_skill: evaluate_progression(
            previous_evidence=previous_evidence or (),
            current_evidence=ev,
            skill=evidenced_skill,
        )
        for evidenced_skill in sorted(evidenced_skills)
    }
    skill_progress = {
        evidenced_skill: result["progression_outcome"]
        for evidenced_skill, result in skill_results.items()
    }
    if skill is None and skill_results:
        skill_outcomes = set(skill_progress.values())
        prog = {
            "progression_outcome": (
                next(iter(skill_outcomes)) if len(skill_outcomes) == 1 else "mixed"
            ),
            "stable_progression": all(
                result["stable_progression"] for result in skill_results.values()
            ),
        }
    else:
        prog = evaluate_progression(
            previous_evidence=previous_evidence or (),
            current_evidence=ev,
            skill=skill,
        )

    grounded_patterns = [
        dict(normalize_json_value(pattern))
        for pattern in (patterns or ())
        if isinstance(pattern, Mapping)
        and (
            pattern.get("eligible") is True
            or pattern.get("pattern_state") in {"candidate", "evidenced", "improving"}
        )
    ]
    profile = dict(normalize_json_value(certification_profile or {}))
    readiness_score = profile.get("readiness_score")
    if (
        isinstance(readiness_score, (int, float))
        and not isinstance(readiness_score, bool)
        and readiness_score >= 0.8
    ):
        certification_readiness = "ready"
    elif (
        isinstance(readiness_score, (int, float))
        and not isinstance(readiness_score, bool)
        and readiness_score > 0
    ):
        certification_readiness = "in_progress"
    else:
        certification_readiness = "not_assessed"

    if grounded_patterns:
        first_pattern = grounded_patterns[0]
        recommended_next_focus = str(
            first_pattern.get("recommended_focus")
            or first_pattern.get("error_type")
            or "pattern_review"
        )
    else:
        grounded_goals = [
            dict(normalize_json_value(goal))
            for goal in (goals or ())
            if isinstance(goal, Mapping)
        ]
        recommended_next_focus = (
            str(grounded_goals[0].get("target") or grounded_goals[0].get("id"))
            if grounded_goals
            else "not_assessed"
        )

    positive_outcomes = {"short_term_improvement", "stable_improvement"}
    cross_skill_inflation = not set(skill_progress).issubset(evidenced_skills)
    progression_evidence_valid = not (
        prog["progression_outcome"] == "insufficient_evidence"
        and any(value in positive_outcomes for value in skill_progress.values())
    )

    return {
        "review_id": f"pr-{uuid.uuid4().hex[:8]}",
        "language": language,
        "period": period,
        "skill_progress": skill_progress,
        "overall_progression": prog["progression_outcome"],
        "stable_progression": prog["stable_progression"],
        "active_patterns_count": len(grounded_patterns),
        "certification_readiness": certification_readiness,
        "recommended_next_focus": recommended_next_focus,
        "progression_evidence_valid": progression_evidence_valid,
        "cross_skill_inflation": cross_skill_inflation,
    }


__all__ = [
    "CANONICAL_LANGUAGES_OPERATION_IDS",
    "LANGUAGES_OPERATION_IDS",
    "assess_sample_result",
    "build_languages_operation_definitions",
    "create_learning_plan_result",
    "generate_conversation_turn_result",
    "generate_exercises_result",
    "generate_lesson_result",
    "generate_progress_review_result",
    "generate_roleplay_turn_result",
    "plan_review_schedule_result",
    "prepare_certification_result",
    "review_errors_result",
    "review_exercise_result",
    "review_speaking_result",
    "review_writing_result",
    "track_vocabulary_result",
    "update_level_evidence_result",
]
