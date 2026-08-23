"""Phase 10.26 — Languages Domain Workflows.

Nine declarative Languages workflows. Every workflow loads its context,
applies the LanguageLearningProfile, reasons under the fourteen Languages rules,
executes pedagogy/assessment operations, and validates results against safety
and epistemic gates before completion.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE``
node that verifies output constraints emitted by direct upstream operation nodes.
"""

from __future__ import annotations

from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_WORKFLOW_IDS,
    LANGUAGES_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

LANGUAGES_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_LANGUAGES_WORKFLOW_IDS


def _node(
    node_id: str,
    node_type: WorkflowNodeType,
    name: str,
    *,
    dependencies: tuple[str, ...] = (),
    operation_id: str | None = None,
    approval_gate: str | None = None,
    wait_condition: dict | None = None,
    metadata: dict | None = None,
) -> WorkflowNode:
    return WorkflowNode(
        node_id=node_id,
        node_type=node_type,
        name=name,
        dependencies=dependencies,
        operation_id=operation_id,
        operation_version="1.0.0" if operation_id else None,
        approval_gate=approval_gate,
        wait_condition=wait_condition,
        metadata=metadata or {},
    )


def _ordered_prefix() -> tuple[WorkflowNode, ...]:
    """Strict safety prefix: load -> profile -> reason (enforced as deps)."""
    return (
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadLanguageSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyLanguageLearningProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyLanguagesRules",
            dependencies=("profile",),
        ),
    )


def _workflow(
    workflow_id: str,
    *,
    description: str,
    purpose: str,
    core_nodes: tuple[WorkflowNode, ...],
    extra_metadata: dict | None = None,
) -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id=workflow_id,
        domain_id="domain:languages",
        version="1.0.0",
        name=LANGUAGES_WORKFLOW_NAMES_BY_ID[workflow_id],
        description=description,
        nodes=(*_ordered_prefix(), *core_nodes),
        completion_criteria={
            "all_required_nodes_completed": True,
            "no_blocking_failures": True,
        },
        metadata={
            "phase": "10.26",
            "purpose": purpose,
            "non_autonomous": True,
            **(extra_metadata or {}),
        },
    )


def build_languages_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build all nine canonical Languages Domain workflow definitions deterministically."""
    # 1. language_onboarding
    onboarding = _workflow(
        "languages.language_onboarding",
        description="Onboard user to language learning and establish tracking preferences.",
        purpose="onboarding",
        core_nodes=(
            _node(
                "create_plan",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CreateLearningPlan",
                dependencies=("reason",),
                operation_id="languages.create_learning_plan",
            ),
            _node(
                "validate_tracking_boundary",
                WorkflowNodeType.VALIDATE,
                "ValidateTrackingBoundary",
                dependencies=("create_plan",),
                wait_condition={"tracking_choice_resolved": True, "persistence_applied": False},
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("validate_tracking_boundary",),
            ),
        ),
    )

    # 2. proficiency_assessment
    assessment = _workflow(
        "languages.proficiency_assessment",
        description="Assess language proficiency without overwriting certified records.",
        purpose="assessment",
        core_nodes=(
            _node(
                "assess",
                WorkflowNodeType.EXECUTE_OPERATION,
                "AssessSample",
                dependencies=("reason",),
                operation_id="languages.assess_sample",
            ),
            _node(
                "level_update",
                WorkflowNodeType.EXECUTE_OPERATION,
                "UpdateLevelEvidence",
                dependencies=("assess",),
                operation_id="languages.update_level_evidence",
            ),
            _node(
                "evidence_gate",
                WorkflowNodeType.VALIDATE,
                "ValidateEvidenceGate",
                dependencies=("level_update",),
                wait_condition={"is_certified": False, "stable_update_supported": False},
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("evidence_gate",),
            ),
        ),
    )

    # 3. adaptive_language_lesson
    lesson = _workflow(
        "languages.adaptive_language_lesson",
        description="Deliver structured adaptive language lesson.",
        purpose="lesson",
        core_nodes=(
            _node(
                "lesson",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateLesson",
                dependencies=("reason",),
                operation_id="languages.generate_lesson",
            ),
            _node(
                "exercises",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateExercises",
                dependencies=("lesson",),
                operation_id="languages.generate_exercises",
            ),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewExercise",
                dependencies=("exercises",),
                operation_id="languages.review_exercise",
            ),
            _node(
                "difficulty_gate",
                WorkflowNodeType.VALIDATE,
                "ValidateDifficultyGate",
                dependencies=("review",),
                wait_condition={"is_correct": True, "pattern_candidate": False},
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("difficulty_gate",),
            ),
        ),
    )

    # 4. conversation_roleplay_practice
    practice = _workflow(
        "languages.conversation_roleplay_practice",
        description="Interactive conversation and roleplay practice segment.",
        purpose="practice",
        core_nodes=(
            _node(
                "conversation_turn",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateConversationTurn",
                dependencies=("reason",),
                operation_id="languages.generate_conversation_turn",
            ),
            _node(
                "roleplay_turn",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateRoleplayTurn",
                dependencies=("conversation_turn",),
                operation_id="languages.generate_roleplay_turn",
            ),
            _node(
                "speaking_review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewSpeaking",
                dependencies=("roleplay_turn",),
                operation_id="languages.review_speaking",
            ),
            _node(
                "practice_gate",
                WorkflowNodeType.VALIDATE,
                "ValidatePracticeGate",
                dependencies=("speaking_review",),
                wait_condition={"pronunciation_assessed": False},
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("practice_gate",),
            ),
        ),
    )

    # 5. writing_review
    writing = _workflow(
        "languages.writing_review",
        description="Review writing production and preserve valid variety alternatives.",
        purpose="writing_review",
        core_nodes=(
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewWriting",
                dependencies=("reason",),
                operation_id="languages.review_writing",
            ),
            _node(
                "variety_gate",
                WorkflowNodeType.VALIDATE,
                "ValidateVarietyGate",
                dependencies=("review",),
                wait_condition={"score": 0.85, "estimated_level": "B2"},
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("variety_gate",),
            ),
        ),
    )

    # 6. error_remediation
    remediation = _workflow(
        "languages.error_remediation",
        description="Remediate errors and analyze candidate patterns.",
        purpose="remediation",
        core_nodes=(
            _node(
                "error_review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewErrors",
                dependencies=("reason",),
                operation_id="languages.review_errors",
            ),
            _node(
                "exercises",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateExercises",
                dependencies=("error_review",),
                operation_id="languages.generate_exercises",
            ),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewExercise",
                dependencies=("exercises",),
                operation_id="languages.review_exercise",
            ),
            _node(
                "pattern_gate",
                WorkflowNodeType.VALIDATE,
                "ValidatePatternGate",
                dependencies=("review",),
                wait_condition={"pattern_candidate": False},
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("pattern_gate",),
            ),
        ),
    )

    # 7. vocabulary_spaced_review
    vocab_review = _workflow(
        "languages.vocabulary_spaced_review",
        description="Track vocabulary items and propose spaced review schedule.",
        purpose="spaced_review",
        core_nodes=(
            _node(
                "vocabulary",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackVocabulary",
                dependencies=("reason",),
                operation_id="languages.track_vocabulary",
            ),
            _node(
                "review_plan",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PlanReviewSchedule",
                dependencies=("vocabulary",),
                operation_id="languages.plan_review_schedule",
            ),
            _node(
                "no_calendar_mutation_gate",
                WorkflowNodeType.VALIDATE,
                "ValidateNoCalendarMutation",
                dependencies=("review_plan",),
                wait_condition={"calendar_modified": False, "external_action_executed": False},
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("no_calendar_mutation_gate",),
            ),
        ),
    )

    # 8. certification_preparation
    certification = _workflow(
        "languages.certification_preparation",
        description="Prepare for language certification without registering or paying.",
        purpose="certification_preparation",
        core_nodes=(
            _node(
                "certification",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareCertification",
                dependencies=("reason",),
                operation_id="languages.prepare_certification",
            ),
            _node(
                "certification_gate",
                WorkflowNodeType.VALIDATE,
                "ValidateCertificationGate",
                dependencies=("certification",),
                wait_condition={
                    "needs_verification": False,
                    "registration_performed": False,
                    "payment_performed": False,
                    "submission_performed": False,
                },
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("certification_gate",),
            ),
        ),
    )

    # 9. progress_checkpoint
    progress = _workflow(
        "languages.progress_checkpoint",
        description="Generate progress review checkpoint.",
        purpose="progress_review",
        core_nodes=(
            _node(
                "progress",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateProgressReview",
                dependencies=("reason",),
                operation_id="languages.generate_progress_review",
            ),
            _node(
                "progression_gate",
                WorkflowNodeType.VALIDATE,
                "ValidateProgressionGate",
                dependencies=("progress",),
                wait_condition={"stable_progression": False},
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("progression_gate",),
            ),
        ),
    )

    by_id = {
        "languages.language_onboarding": onboarding,
        "languages.proficiency_assessment": assessment,
        "languages.adaptive_language_lesson": lesson,
        "languages.conversation_roleplay_practice": practice,
        "languages.writing_review": writing,
        "languages.error_remediation": remediation,
        "languages.vocabulary_spaced_review": vocab_review,
        "languages.certification_preparation": certification,
        "languages.progress_checkpoint": progress,
    }

    return tuple(
        by_id[workflow_id]
        for workflow_id in CANONICAL_LANGUAGES_WORKFLOW_IDS
    )


__all__ = [
    "CANONICAL_LANGUAGES_WORKFLOW_IDS",
    "LANGUAGES_WORKFLOW_IDS",
    "build_languages_workflow_definitions",
]
