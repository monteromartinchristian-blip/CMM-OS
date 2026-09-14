"""Phase 10.20 — Health Domain Workflows.

Eight declarative Health workflows.  Every workflow loads its context,
applies the conservative health profile, reasons under the eight Health
rules, detects gaps, optionally executes one or more Health operations, and
only ever *proposes* memory or *prepares* for approval — never acting on a
person's health autonomously.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain
(an analytical operation can never run before reasoning, and reasoning never
before the profile/context are loaded).  A terminal ``COMPLETE`` node always
transitively depends on a ``VALIDATE`` node, so completion cannot bypass
validation.  High-impact workflows (e.g. medication review) carry a real
``REQUEST_APPROVAL`` escalation gate on the path to completion, so a path
requiring professional/human escalation cannot proceed as ordinary
successful completion without the gate.
"""

from __future__ import annotations

from cmm.domains.health.catalog import CANONICAL_HEALTH_WORKFLOW_IDS
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

HEALTH_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_HEALTH_WORKFLOW_IDS


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
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadHealthSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyHealthProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyHealthRules",
            dependencies=("profile",),
        ),
    )


def _propose_memory_tail() -> tuple[WorkflowNode, ...]:
    # Shared tail: validate then propose memory (never write without approval).
    return (
        _node(
            "validate",
            WorkflowNodeType.VALIDATE,
            "Validate",
            dependencies=("questions",),
        ),
        _node(
            "memory",
            WorkflowNodeType.PROPOSE_MEMORY,
            "ProposeMemory",
            dependencies=("validate",),
        ),
        _node(
            "complete", WorkflowNodeType.COMPLETE, "Complete", dependencies=("memory",)
        ),
    )


def _validate_only_tail() -> tuple[WorkflowNode, ...]:
    # Tail that completes without proposing memory (memory proposal optional).
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


def _chronic_condition_timeline() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="health.chronic_condition_timeline",
        domain_id="domain:health",
        version="1.0.0",
        name="ChronicConditionTimeline",
        description="Build a traceable timeline for a chronic condition.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "timeline",
                WorkflowNodeType.EXECUTE_OPERATION,
                "BuildMedicalTimeline",
                dependencies=("reason",),
                operation_id="health.build_medical_timeline",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareQuestions",
                dependencies=("timeline",),
                operation_id="health.prepare_questions",
            ),
            *_propose_memory_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Chronic condition timeline",
        metadata={"phase": "10.20"},
    )


def _diagnostic_process_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="health.diagnostic_process_review",
        domain_id="domain:health",
        version="1.0.0",
        name="DiagnosticProcessReview",
        description="Review the diagnostic conversation without diagnosing.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "timeline",
                WorkflowNodeType.EXECUTE_OPERATION,
                "BuildSymptomTimeline",
                dependencies=("reason",),
                operation_id="health.build_symptom_timeline",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "DetectOpenQuestions",
                dependencies=("timeline",),
                operation_id="health.detect_open_medical_questions",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Diagnostic process review (no definitive diagnosis)",
        metadata={"phase": "10.20"},
    )


def _medical_follow_up() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="health.medical_follow_up",
        domain_id="domain:health",
        version="1.0.0",
        name="MedicalFollowUp",
        description="Review follow-up for a condition or symptom trend.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewFollowUp",
                dependencies=("reason",),
                operation_id="health.review_follow_up",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareQuestions",
                dependencies=("review",),
                operation_id="health.prepare_questions",
            ),
            *_propose_memory_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Medical follow-up review",
        metadata={"phase": "10.20"},
    )


def _medical_report_comparison() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="health.medical_report_comparison",
        domain_id="domain:health",
        version="1.0.0",
        name="MedicalReportComparison",
        description="Compare two medical reports on supported criteria.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "compare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CompareReports",
                dependencies=("reason",),
                operation_id="health.compare_reports",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareQuestions",
                dependencies=("compare",),
                operation_id="health.prepare_questions",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Medical report comparison",
        metadata={"phase": "10.20"},
    )


def _medication_change_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="health.medication_change_review",
        domain_id="domain:health",
        version="1.0.0",
        name="MedicationChangeReview",
        description="Review medication temporal associations without changing medication.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewMedicationChanges",
                dependencies=("reason",),
                operation_id="health.review_medication_changes",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareQuestions",
                dependencies=("review",),
                operation_id="health.prepare_questions",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "Validate",
                dependencies=("questions",),
            ),
            _node(
                "escalate",
                WorkflowNodeType.REQUEST_APPROVAL,
                "EscalateMedicationReview",
                dependencies=("validate",),
                approval_gate="health.medication_review",
            ),
            _node(
                "memory",
                WorkflowNodeType.PROPOSE_MEMORY,
                "ProposeMemory",
                dependencies=("escalate",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("memory",),
            ),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Medication change review (never modifies medication)",
        metadata={"phase": "10.20"},
    )


def _postoperative_follow_up() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="health.postoperative_follow_up",
        domain_id="domain:health",
        version="1.0.0",
        name="PostoperativeFollowUp",
        description="Review postoperative follow-up information.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "symptom_timeline",
                WorkflowNodeType.EXECUTE_OPERATION,
                "BuildSymptomTimeline",
                dependencies=("reason",),
                operation_id="health.build_symptom_timeline",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareQuestions",
                dependencies=("symptom_timeline",),
                operation_id="health.prepare_questions",
            ),
            *_propose_memory_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Postoperative follow-up",
        metadata={"phase": "10.20"},
    )


def _specialist_appointment_preparation() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="health.specialist_appointment_preparation",
        domain_id="domain:health",
        version="1.0.0",
        name="SpecialistAppointmentPreparation",
        description="Prepare for a specialist appointment without booking it.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "summary",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateMedicalSummary",
                dependencies=("reason",),
                operation_id="health.generate_medical_summary",
            ),
            _node(
                "prepare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareAppointment",
                dependencies=("summary",),
                operation_id="health.prepare_medical_appointment",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareQuestions",
                dependencies=("prepare",),
                operation_id="health.prepare_questions",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Specialist appointment preparation (no booking)",
        metadata={"phase": "10.20"},
    )


def _symptom_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="health.symptom_review",
        domain_id="domain:health",
        version="1.0.0",
        name="SymptomReview",
        description="Review reported symptoms, classify epistemic status, detect red flags.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "symptom_timeline",
                WorkflowNodeType.EXECUTE_OPERATION,
                "BuildSymptomTimeline",
                dependencies=("reason",),
                operation_id="health.build_symptom_timeline",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareQuestions",
                dependencies=("symptom_timeline",),
                operation_id="health.prepare_questions",
            ),
            *_propose_memory_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Symptom review",
        metadata={"phase": "10.20"},
    )


def build_health_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build the eight Health Domain workflow definitions deterministically in canonical order."""
    by_id = {
        "health.chronic_condition_timeline": _chronic_condition_timeline(),
        "health.diagnostic_process_review": _diagnostic_process_review(),
        "health.medical_follow_up": _medical_follow_up(),
        "health.medical_report_comparison": _medical_report_comparison(),
        "health.medication_change_review": _medication_change_review(),
        "health.postoperative_follow_up": _postoperative_follow_up(),
        "health.specialist_appointment_preparation": _specialist_appointment_preparation(),
        "health.symptom_review": _symptom_review(),
    }
    return tuple(by_id[workflow_id] for workflow_id in HEALTH_WORKFLOW_IDS)


__all__ = ["HEALTH_WORKFLOW_IDS", "build_health_workflow_definitions"]
