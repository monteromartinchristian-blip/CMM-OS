"""Phase 10.22 — University Domain Workflows.

Seven declarative University workflows.  Every workflow loads its context,
applies the conservative University profile, reasons under the ten University
rules, detects gaps, optionally executes one or more University operations,
and never acts on the official academic record autonomously.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain
(an analytical operation can never run before reasoning, and reasoning never
before the profile/context are loaded).  A terminal ``COMPLETE`` node always
transitively depends on a ``VALIDATE`` node, so completion cannot bypass
validation.

Academic-safety posture (spec §1, §8, §26):
- **No memory write**: the domain memory policy is read-only (``allow_write=False``),
  so no workflow proposes memory.  All tails are validate-only.
- **No autonomous academic action**: ``university.semester_planning`` and
  ``university.create_study_plan`` produce *proposals* and carry a real
  ``REQUEST_APPROVAL`` gate; they never enrol, register, submit, or send.
- **Decision Support Mode A**: planning workflows compare options against
  explicit user criteria and never adopt an academic decision.
- **``update_subject_status`` is INTERNAL Academic State only**: it never
  touches the official record, calendar, or tasks.
"""

from __future__ import annotations

from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_WORKFLOW_IDS
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

UNIVERSITY_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_UNIVERSITY_WORKFLOW_IDS


def _node(
    node_id: str,
    node_type: WorkflowNodeType,
    name: str,
    *,
    dependencies: tuple[str, ...] = (),
    operation_id: str | None = None,
    approval_gate: str | None = None,
    wait_condition: dict | None = None,
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
    )


def _ordered_prefix() -> tuple[WorkflowNode, ...]:
    """Strict safety prefix: load -> profile -> reason (enforced as deps)."""
    return (
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadAcademicSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyUniversityProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyUniversityRules",
            dependencies=("profile",),
        ),
    )


def _validate_only_tail() -> tuple[WorkflowNode, ...]:
    # Tail that completes without proposing memory (memory policy is read-only).
    return (
        _node(
            "validate",
            WorkflowNodeType.VALIDATE,
            "Validate",
            dependencies=("questions",),
        ),
        _node(
            "complete",
            WorkflowNodeType.COMPLETE,
            "Complete",
            dependencies=("validate",),
        ),
    )


def _planning_tail(approval_gate: str) -> tuple[WorkflowNode, ...]:
    # Tail for planning/proposal workflows: validate then request user approval.
    return (
        _node(
            "validate",
            WorkflowNodeType.VALIDATE,
            "Validate",
            dependencies=("questions",),
        ),
        _node(
            "approve",
            WorkflowNodeType.REQUEST_APPROVAL,
            "ConfirmPlan",
            dependencies=("validate",),
            approval_gate=approval_gate,
        ),
        _node(
            "complete",
            WorkflowNodeType.COMPLETE,
            "Complete",
            dependencies=("approve",),
        ),
    )


def _semester_planning() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="university.semester_planning",
        domain_id="domain:university",
        version="1.0.0",
        name="SemesterPlanning",
        description="Plan a semester as a proposal without enrolling or registering.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "plan",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PlanSemester",
                dependencies=("reason",),
                operation_id="university.plan_semester",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewAcademicRecord",
                dependencies=("plan",),
                operation_id="university.review_academic_record",
            ),
            *_planning_tail("university.semester_planning"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Semester planning (proposal only, never enrols)",
        metadata={"phase": "10.22"},
    )


def _exam_preparation() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="university.exam_preparation",
        domain_id="domain:university",
        version="1.0.0",
        name="ExamPreparation",
        description="Prepare exam material without sending or submitting anything.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "prepare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareExam",
                dependencies=("reason",),
                operation_id="university.prepare_exam",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackDeadlines",
                dependencies=("prepare",),
                operation_id="university.track_deadlines",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Exam preparation (preparation only)",
        metadata={"phase": "10.22"},
    )


def _academic_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="university.academic_review",
        domain_id="domain:university",
        version="1.0.0",
        name="AcademicReview",
        description="Review the academic record without modifying any official state.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewAcademicRecord",
                dependencies=("reason",),
                operation_id="university.review_academic_record",
            ),
            _node(
                "analyse",
                WorkflowNodeType.EXECUTE_OPERATION,
                "AnalysePerformance",
                dependencies=("review",),
                operation_id="university.analyse_performance",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CompareSemesters",
                dependencies=("analyse",),
                operation_id="university.compare_semesters",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Academic review (review only, no record mutation)",
        metadata={"phase": "10.22"},
    )


def _reassessment_planning() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="university.reassessment_planning",
        domain_id="domain:university",
        version="1.0.0",
        name="ReassessmentPlanning",
        description="Plan reassessment as a proposal without registering for it.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewAcademicRecord",
                dependencies=("reason",),
                operation_id="university.review_academic_record",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackDeadlines",
                dependencies=("review",),
                operation_id="university.track_deadlines",
            ),
            *_planning_tail("university.reassessment_planning"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Reassessment planning (internal Academic State only)",
        metadata={"phase": "10.22"},
    )


def _assignment_preparation() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="university.assignment_preparation",
        domain_id="domain:university",
        version="1.0.0",
        name="AssignmentPreparation",
        description="Prepare assignment material without submitting anything.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "prepare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareAssignment",
                dependencies=("reason",),
                operation_id="university.prepare_assignment",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackDeadlines",
                dependencies=("prepare",),
                operation_id="university.track_deadlines",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Assignment preparation (preparation only)",
        metadata={"phase": "10.22"},
    )


def _degree_completion_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="university.degree_completion_review",
        domain_id="domain:university",
        version="1.0.0",
        name="DegreeCompletionReview",
        description="Review degree completion without taking any official action.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewDegreeCompletion",
                dependencies=("reason",),
                operation_id="university.review_degree_completion",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateAcademicSummary",
                dependencies=("review",),
                operation_id="university.generate_academic_summary",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Degree completion review (no official graduation action)",
        metadata={"phase": "10.22"},
    )


def _tfg_planning() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="university.tfg_planning",
        domain_id="domain:university",
        version="1.0.0",
        name="TfgPlanning",
        description="Plan the TFG (final project) as a proposal without submitting it.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "plan",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CreateStudyPlan",
                dependencies=("reason",),
                operation_id="university.create_study_plan",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewAcademicRecord",
                dependencies=("plan",),
                operation_id="university.review_academic_record",
            ),
            *_planning_tail("university.tfg_planning"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="TFG planning (formal-procedure preparation only)",
        metadata={"phase": "10.22"},
    )


def build_university_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build the seven University Domain workflow definitions deterministically in canonical order."""
    by_id = {
        "university.academic_review": _academic_review(),
        "university.assignment_preparation": _assignment_preparation(),
        "university.degree_completion_review": _degree_completion_review(),
        "university.exam_preparation": _exam_preparation(),
        "university.reassessment_planning": _reassessment_planning(),
        "university.semester_planning": _semester_planning(),
        "university.tfg_planning": _tfg_planning(),
    }
    return tuple(by_id[workflow_id] for workflow_id in UNIVERSITY_WORKFLOW_IDS)


__all__ = ["UNIVERSITY_WORKFLOW_IDS", "build_university_workflow_definitions"]