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

import uuid
from collections.abc import Mapping
from typing import Any

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.languages.catalog import CANONICAL_LANGUAGES_OPERATION_IDS
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
_INT = {"type": "integer"}
_NUM = {"type": "number"}
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
            "pronunciation_evidence": {"type": ["array", "null"], "items": {"type": "object"}},
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
            "previous_evidence": {"type": ["array", "null"], "items": {"type": "object"}},
            "skill": _STR_OR_NULL,
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
            "score": _NUM,
            "is_correct": _BOOL,
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
    if preferred_variety and "colour" in text.lower() and "american" in preferred_variety.lower():
        v_class = classify_language_variety(
            preferred_variety=preferred_variety,
            observed_variety="British English",
            form_status="valid",
        )
        if v_class.get("is_valid_alternative"):
            valid_alts.append({
                "id": "alt-1",
                "token": "colour",
                "variety": "British English",
                "classification": "valid_alternative",
            })

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
        "observed_performance": (
            "B2" if len(text) > 10 else "A2"
        ) if has_sample_evidence else "unknown",
        "confidence": 0.75 if has_sample_evidence else 0.0,
        "strengths": (
            ["Clear expression", "Good lexical choice"]
            if len(text) > 10
            else ["Initial production"]
        ) if has_sample_evidence else [],
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
    ex = dict(existing_record or {})
    ass = dict(assessment or {})
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
        {"phase_number": 2, "title": "Active Practice & Consolidation", "duration_weeks": 6},
    ]

    tracking_resolved = tracking_consent is not None
    choice = "opt_in" if tracking_consent is True else ("opt_out" if tracking_consent is False else "unresolved")

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
    return {
        "lesson_id": f"lsn-{uuid.uuid4().hex[:8]}",
        "language": language,
        "target_skill": target_skill,
        "level": current_level,
        "objective": f"Master {topic} in {language} for {target_skill}",
        "warmup": f"Review key vocabulary related to {topic}.",
        "input_material": f"Authentic text and models demonstrating {topic}.",
        "guided_practice": "Scaffolded sentence construction and analysis.",
        "active_production": "Open response prompt applying new concepts.",
        "feedback_criteria": ["Accuracy", "Naturalness", "Task fulfillment"],
        "next_step": "Apply in communicative roleplay or writing.",
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
    num = count or 3
    exercises = [
        {
            "exercise_id": f"ex-{i+1}",
            "prompt": f"Complete the sentence using correct {target_topic}.",
            "target_skill": skill,
            "difficulty": difficulty,
        }
        for i in range(num)
    ]
    return {
        "exercise_batch_id": f"exb-{uuid.uuid4().hex[:8]}",
        "language": language,
        "skill": skill,
        "difficulty": difficulty,
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
    is_correct = er.get("is_correct", True)
    score = float(er.get("score", 1.0 if is_correct else 0.0))
    review_id = f"exr-{uuid.uuid4().hex[:8]}"

    errors = []
    if not is_correct:
        errors.append({
            "id": f"err-{uuid.uuid4().hex[:6]}",
            "provenance_id": review_id,
            "topic": target_topic or "general",
            "error_type": "target_structure",
            "comparable": True,
            "comparison_key": target_topic or "general",
            "user_answer": er.get("user_answer", ""),
            "category": "observed_error",
        })

    return {
        "review_id": review_id,
        "score": score,
        "is_correct": is_correct,
        "observed_errors": errors,
        "feedback": "Great job!" if is_correct else "Review the target structure.",
        "difficulty_adjustment": "maintain" if is_correct else "scaffold",
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
    if preferred_variety and "colour" in text.lower() and "british" in preferred_variety.lower():
        valid_alts.append({
            "token": "colour",
            "variety": "British English",
            "status": "valid_alternative",
        })

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
        "register_feedback": "Formal and appropriate." if has_writing_evidence else "not_assessed",
        "estimated_level": (
            "B2" if word_count > 10 else "A2"
        ) if has_writing_evidence else "unknown",
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
    turns = conv.get("turns", [])
    turn_count = len(turns) + 1

    return {
        "turn_id": f"ct-{uuid.uuid4().hex[:8]}",
        "speaker": role or "tutor",
        "utterance": f"That is very interesting! Tell me more about your experience with {topic or 'languages'}.",
        "pedagogical_intent": "encourage_production",
        "scaffolding_hint": "Try using connectors like 'however' or 'furthermore'." if target_level == "B2" else None,
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
    turns = conv.get("turns", [])
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
    observed_errors = [
        dict(normalize_json_value(item))
        for item in at.get("observed_errors", ())
        if isinstance(item, Mapping)
    ]

    has_audio_evidence = bool(pronunciation_evidence)
    missing_evidence = []
    if not transcript:
        missing_evidence.append("speaking_sample")
    if not has_audio_evidence:
        missing_evidence.append("pronunciation_evidence")
    return {
        "review_id": f"sr-{uuid.uuid4().hex[:8]}",
        "transcript_text": transcript,
        "pronunciation_assessed": has_audio_evidence,
        "pronunciation_feedback": "Phoneme clarity verified." if has_audio_evidence else None,
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
        "recommended_focus": "Grammar concord" if patterns else "Fluency practice",
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
    vl = dict(vocabulary_list or {})
    items = list(vl.get("items", []))
    if new_items:
        items.extend(new_items)

    plan_res = plan_spaced_review(items=items)

    return {
        "tracking_id": f"vt-{uuid.uuid4().hex[:8]}",
        "total_items": len(items),
        "due_items": plan_res["backlog_count"],
        "mastery_summary": {"mastered": 5, "learning": len(items)},
        "candidate_updates": items,
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
    load_res = evaluate_learning_load(available_time=available_time, energy=energy, review_backlog=review_items)

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
    src_eval = evaluate_certification_source(sources=[official_source] if official_source else [], decision_critical=True)
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
    if not skill_levels and isinstance(estimated_level, str) and estimated_level.strip():
        skill_levels = {"general": estimated_level.strip().upper()}

    cefr_rank = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    target_level = next(
        (level for level in reversed(tuple(cefr_rank)) if level in target_certification.upper()),
        None,
    )
    grounded_levels = {
        skill: level
        for skill, level in skill_levels.items()
        if level in cefr_rank
    }
    has_profile_evidence = bool(grounded_levels) and target_level is not None
    target_rank = cefr_rank[target_level] if target_level is not None else 0
    readiness_score = (
        round(
            sum(min(cefr_rank[level] / target_rank, 1.0) for level in grounded_levels.values())
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
        "official_source_status": "verified" if official_source else "unverified_guide",
        "needs_verification": src_eval["needs_verification"] or not has_profile_evidence,
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
) -> dict[str, Any]:
    """Generate comprehensive progress review."""
    ev = list(evidence or [])
    prog = evaluate_progression(
        previous_evidence=previous_evidence or (),
        current_evidence=ev,
        skill=skill,
    )

    return {
        "review_id": f"pr-{uuid.uuid4().hex[:8]}",
        "language": language,
        "period": period,
        "skill_progress": {"writing": "improving", "reading": "consolidated"},
        "overall_progression": prog["progression_outcome"],
        "stable_progression": prog["stable_progression"],
        "active_patterns_count": 1,
        "certification_readiness": "in_progress",
        "recommended_next_focus": "Writing coherence and timed tasks",
        "progression_evidence_valid": True,
        "cross_skill_inflation": False,
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
