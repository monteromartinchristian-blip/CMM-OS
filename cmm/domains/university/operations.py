"""Phase 10.22 — University Domain Operations.

Eleven declarative operations.  No implementation is embedded here; an operation
without a provided implementation is registered as **UNAVAILABLE** (fail-closed).

Safety posture (spec §1, §8):
- No operation performs an autonomous academic action.  ``prepare_exam`` and
  ``prepare_assignment`` are PREPARATION only — they prepare material and never
  send, submit, or execute anything.  No EXTERNAL/send/submit operation exists
  anywhere in the domain.
- ``update_subject_status`` is INTERNAL Academic State only; it never touches
  the official university record, calendar, or tasks.
- ``review_*`` operations only *review*; they never modify, enforce, or
  communicate an academic decision.
- ``required_resources`` uses strict AND semantics: an operation only declares a
  resource it structurally consumes.  It is never mechanically populated.
- There are no MEMORY, PLANNING, or DESTRUCTIVE operations: the domain memory
  policy is read-only (``allow_write=False``) and academic decisions require
  explicit user confirmation.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_OPERATION_IDS

UNIVERSITY_OPERATION_IDS: tuple[str, ...] = CANONICAL_UNIVERSITY_OPERATION_IDS

_OPERATION_TYPES = {
    "university.plan_semester": DomainOperationType.PLANNING,
    "university.create_study_plan": DomainOperationType.PLANNING,
    "university.review_academic_record": DomainOperationType.ANALYSIS,
    "university.compare_semesters": DomainOperationType.ANALYSIS,
    "university.prepare_exam": DomainOperationType.PREPARATION,
    "university.prepare_assignment": DomainOperationType.PREPARATION,
    "university.track_deadlines": DomainOperationType.ANALYSIS,
    "university.analyse_performance": DomainOperationType.ANALYSIS,
    "university.generate_academic_summary": DomainOperationType.PREPARATION,
    "university.update_subject_status": DomainOperationType.MEMORY,
    "university.review_degree_completion": DomainOperationType.ANALYSIS,
}

_APPROVAL_REQUIRED = frozenset(
    {
        "university.plan_semester",
        "university.create_study_plan",
        "university.update_subject_status",
    }
)

_HIGHER_RISK = frozenset(
    {
        "university.plan_semester",
        "university.create_study_plan",
        "university.update_subject_status",
    }
)

# No proposal-only operations: the domain memory policy is read-only and no
# operation proposes a memory write.  ``update_subject_status`` mutates only
# the INTERNAL Academic State, never persistent personal memory.
_PROPOSAL_ONLY = frozenset()

# Resources each operation structurally consumes (AND semantics).  Only
# operations that genuinely read a University resource declare it here.
_REQUIRED_RESOURCES = {
    "university.plan_semester": ("university.academic_record",),
    "university.create_study_plan": ("university.academic_record",),
    "university.review_academic_record": ("university.academic_record",),
    "university.compare_semesters": ("university.academic_record",),
    "university.prepare_exam": ("university.examination_schedule",),
    "university.prepare_assignment": ("university.assignment",),
    "university.track_deadlines": ("university.university_calendar",),
    "university.analyse_performance": ("university.grade",),
    "university.generate_academic_summary": ("university.academic_record",),
    "university.update_subject_status": ("university.grade",),
    "university.review_degree_completion": ("university.academic_record",),
}


def _schema(required: tuple[str, ...], properties: dict) -> dict:
    """Build a deterministic JSON object schema with closed properties."""
    return {
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": False,
    }


_ID_ARRAY = {"type": "array", "items": {"type": "string"}}
_DATE_STRING = {"type": "string"}


def _ids(min_items: int) -> dict:
    return {"type": "array", "items": {"type": "string"}, "minItems": min_items}


def _period() -> dict:
    """A closed period object with explicit ``start``/``end`` properties."""
    return {
        "type": "object",
        "required": ["start", "end"],
        "properties": {
            "start": _DATE_STRING,
            "end": _DATE_STRING,
        },
        "additionalProperties": False,
    }


_INPUT_SCHEMAS = {
    "university.plan_semester": _schema(
        ("semester",),
        {
            "semester": {"type": "string"},
            "source_ids": _ID_ARRAY,
        },
    ),
    "university.create_study_plan": _schema(
        ("subjects",),
        {
            "subjects": _ids(1),
            "semester": {"type": "string"},
        },
    ),
    "university.review_academic_record": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "university.compare_semesters": _schema(
        ("period_a", "period_b"),
        {
            "period_a": _period(),
            "period_b": _period(),
        },
    ),
    "university.prepare_exam": _schema(
        ("examination_id",), {"examination_id": {"type": "string"}}
    ),
    "university.prepare_assignment": _schema(
        ("assignment_id",), {"assignment_id": {"type": "string"}}
    ),
    "university.track_deadlines": _schema(("source_ids",), {"source_ids": _ids(1)}),
    "university.analyse_performance": _schema(("source_ids",), {"source_ids": _ids(1)}),
    "university.generate_academic_summary": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "university.update_subject_status": _schema(
        ("subject_id", "status"),
        {
            "subject_id": {"type": "string"},
            "status": {"type": "string"},
        },
    ),
    "university.review_degree_completion": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
}

# An academic plan is a proposal, not an adopted decision.
_PLAN = _schema(
    ("semester",),
    {
        "semester": {"type": "string"},
        "subjects": _ID_ARRAY,
        "source_references": _ID_ARRAY,
        "adopted_decision": {"type": "boolean"},
        "requires_user_confirmation": {"type": "boolean"},
    },
)

# A study plan proposal, never an enrolment or registration.
_STUDY_PLAN = _schema(
    ("subjects",),
    {
        "subjects": {"type": "array", "items": {"type": "string"}},
        "semester": {"type": "string"},
        "proposal_only": {"type": "boolean"},
        "adopted_decision": {"type": "boolean"},
    },
)

# A record review is a structured analysis, never a record mutation.
_RECORD_REVIEW = _schema(
    ("subject_records",),
    {
        "subject_records": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
)

# A comparison between two periods is a structured review of change.
_PERIOD_COMPARISON = _schema(
    ("period_a", "period_b"),
    {
        "period_a": _DATE_STRING,
        "period_b": _DATE_STRING,
        "observed_changes": _ID_ARRAY,
        "summary": {"type": "string"},
    },
)

# Exam preparation is PREPARATION-only: it describes study material, never
# schema-authorizes sending, submitting, or executing anything.
_EXAM_PREPARATION = _schema(
    ("examination_id",),
    {
        "examination_id": {"type": "string"},
        "topics": _ID_ARRAY,
        "material_refs": _ID_ARRAY,
        "preparation_only": {"type": "boolean"},
        "no_authorization_send": {"type": "boolean"},
    },
)

# Assignment preparation is PREPARATION-only.
_ASSIGNMENT_PREPARATION = _schema(
    ("assignment_id",),
    {
        "assignment_id": {"type": "string"},
        "outline": {"type": "string"},
        "source_references": _ID_ARRAY,
        "preparation_only": {"type": "boolean"},
    },
)

# Deadline tracking is review output, not a calendar mutation.
_DEADLINE_TRACKING = _schema(
    ("deadlines",),
    {
        "deadlines": {"type": "array", "items": {"type": "string"}},
        "upcoming": _ID_ARRAY,
        "calendar_not_modified": {"type": "boolean"},
    },
)

# Performance analysis keeps performance distinct from capacity.
_PERFORMANCE_ANALYSIS = _schema(
    ("observed_performance",),
    {
        "observed_performance": {"type": "array", "items": {"type": "string"}},
        "capacity_inferred": {"type": "boolean"},
        "summary": {"type": "string"},
    },
)

# An academic summary is a structured synthesis.
_ACADEMIC_SUMMARY = _schema(("summary",), {"summary": {"type": "string"}})

# ``update_subject_status`` output reflects only the INTERNAL Academic State.
_SUBJECT_STATUS = _schema(
    ("subject_id", "status"),
    {
        "subject_id": {"type": "string"},
        "status": {"type": "string"},
        "internal_academic_state_only": {"type": "boolean"},
        "official_record_untouched": {"type": "boolean"},
    },
)

# Degree completion review is review output, never a graduation action.
_DEGREE_COMPLETION_REVIEW = _schema(
    ("requirements",),
    {
        "requirements": {"type": "array", "items": {"type": "string"}},
        "completion_state": {"type": "string"},
        "official_action_none": {"type": "boolean"},
    },
)

_OUTPUT_SCHEMAS = {
    "university.plan_semester": _schema(("plan",), {"plan": _PLAN}),
    "university.create_study_plan": _schema(
        ("study_plan",), {"study_plan": _STUDY_PLAN}
    ),
    "university.review_academic_record": _schema(
        ("review",), {"review": _RECORD_REVIEW}
    ),
    "university.compare_semesters": _schema(
        ("comparison",), {"comparison": _PERIOD_COMPARISON}
    ),
    "university.prepare_exam": _schema(
        ("preparation",), {"preparation": _EXAM_PREPARATION}
    ),
    "university.prepare_assignment": _schema(
        ("preparation",), {"preparation": _ASSIGNMENT_PREPARATION}
    ),
    "university.track_deadlines": _schema(
        ("tracking",), {"tracking": _DEADLINE_TRACKING}
    ),
    "university.analyse_performance": _schema(
        ("analysis",), {"analysis": _PERFORMANCE_ANALYSIS}
    ),
    "university.generate_academic_summary": _schema(
        ("summary",), {"summary": _ACADEMIC_SUMMARY}
    ),
    "university.update_subject_status": _schema(
        ("status",), {"status": _SUBJECT_STATUS}
    ),
    "university.review_degree_completion": _schema(
        ("review",), {"review": _DEGREE_COMPLETION_REVIEW}
    ),
}


def build_university_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build the eleven University Domain operation definitions deterministically."""
    result = []
    for operation_id in UNIVERSITY_OPERATION_IDS:
        operation_type = _OPERATION_TYPES[operation_id]
        operation_name = operation_id.split(".", 1)[1]
        requires_approval = operation_id in _APPROVAL_REQUIRED
        result.append(
            DomainOperationDefinition(
                operation_id=operation_id,
                domain_id="domain:university",
                version="1.0.0",
                name=operation_name.replace("_", " ").title(),
                description=f"Conservative structured operation for {operation_id}.",
                operation_type=operation_type,
                input_schema=_INPUT_SCHEMAS[operation_id],
                output_schema=_OUTPUT_SCHEMAS[operation_id],
                required_resources=_REQUIRED_RESOURCES[operation_id],
                required_permissions=(),
                risk_level=(
                    PolicyRiskLevel.MEDIUM
                    if operation_id in _HIGHER_RISK
                    else PolicyRiskLevel.LOW
                ),
                reversible=False,
                requires_approval=requires_approval,
                validation_policy_id=None,
                rollback_policy_id=None,
                enabled=True,
                metadata={
                    "phase": "10.22",
                    "domain": "university",
                    "proposal_only": operation_id in _PROPOSAL_ONLY,
                },
            )
        )
    return tuple(result)


__all__ = [
    "UNIVERSITY_OPERATION_IDS",
    "build_university_operation_definitions",
]
