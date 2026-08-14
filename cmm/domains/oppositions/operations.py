"""Phase 10.23 — Opposition Domain Operations.

Ten declarative opposition operations.  No implementation is embedded here; an
operation without a provided implementation is registered as **UNAVAILABLE**
(fail-closed).

Safety posture (spec §19, §22):
- No operation performs an autonomous external action.  ``review_call`` never
  registers or submits; ``create_study_plan`` and ``generate_revision_plan``
  are PROPOSAL-only; ``update_progress`` only proposes an internal progress
  update and never mutates official systems, calendar, tasks, or memory.
- ``required_resources`` uses strict AND semantics: an operation only declares
  a resource it structurally consumes.  It is never mechanically populated.
- Planning may propose calendar/task changes but never mutates them.
- Missing operation implementation is unavailable/fail-closed; malformed input
  is a structured validation failure, never a permissive fallback.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.oppositions.catalog import CANONICAL_OPPOSITION_OPERATION_IDS

OPPOSITIONS_OPERATION_IDS: tuple[str, ...] = CANONICAL_OPPOSITION_OPERATION_IDS

_OPERATION_TYPES = {
    "oppositions.create_study_plan": DomainOperationType.PLANNING,
    "oppositions.divide_syllabus": DomainOperationType.PLANNING,
    "oppositions.track_progress": DomainOperationType.ANALYSIS,
    "oppositions.review_mock_exam": DomainOperationType.ANALYSIS,
    "oppositions.compare_bodies": DomainOperationType.ANALYSIS,
    "oppositions.review_call": DomainOperationType.ANALYSIS,
    "oppositions.generate_weekly_review": DomainOperationType.PREPARATION,
    "oppositions.identify_risks": DomainOperationType.ANALYSIS,
    "oppositions.generate_revision_plan": DomainOperationType.PLANNING,
    "oppositions.update_progress": DomainOperationType.MEMORY,
}

_APPROVAL_REQUIRED = frozenset(
    {
        "oppositions.create_study_plan",
        "oppositions.generate_revision_plan",
        "oppositions.update_progress",
    }
)

_HIGHER_RISK = frozenset(
    {
        "oppositions.create_study_plan",
        "oppositions.generate_revision_plan",
        "oppositions.update_progress",
    }
)

# Proposal-only operations: they produce a structured proposal and never adopt
# a plan, strategy, or progress change by themselves.
_PROPOSAL_ONLY = frozenset(
    {
        "oppositions.create_study_plan",
        "oppositions.divide_syllabus",
        "oppositions.compare_bodies",
        "oppositions.generate_weekly_review",
        "oppositions.generate_revision_plan",
        "oppositions.update_progress",
    }
)

# Resources each operation structurally consumes (AND semantics).  Only
# operations that genuinely read a resource declare it here.
_REQUIRED_RESOURCES = {
    "oppositions.create_study_plan": ("oppositions.syllabus",),
    "oppositions.divide_syllabus": ("oppositions.syllabus",),
    "oppositions.track_progress": ("oppositions.study_plan",),
    "oppositions.review_mock_exam": ("oppositions.score_record",),
    "oppositions.compare_bodies": ("oppositions.official_call",),
    "oppositions.review_call": ("oppositions.official_call",),
    "oppositions.generate_weekly_review": ("oppositions.official_call",),
    "oppositions.identify_risks": ("oppositions.official_call",),
    "oppositions.generate_revision_plan": ("oppositions.syllabus",),
    "oppositions.update_progress": ("oppositions.study_plan",),
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


_INPUT_SCHEMAS = {
    "oppositions.create_study_plan": _schema(
        ("target_id",),
        {
            "target_id": {"type": "string"},
            "target_date": _DATE_STRING,
            "constraints": _ID_ARRAY,
        },
    ),
    "oppositions.divide_syllabus": _schema(
        ("syllabus_id",), {"syllabus_id": {"type": "string"}}
    ),
    "oppositions.track_progress": _schema(
        ("plan_id",), {"plan_id": {"type": "string"}}
    ),
    "oppositions.review_mock_exam": _schema(
        ("mock_id",), {"mock_id": {"type": "string"}}
    ),
    "oppositions.compare_bodies": _schema(
        ("primary_id",),
        {
            "primary_id": {"type": "string"},
            "alternatives": _ids(1),
        },
    ),
    "oppositions.review_call": _schema(
        ("call_id",), {"call_id": {"type": "string"}}
    ),
    "oppositions.generate_weekly_review": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "oppositions.identify_risks": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "oppositions.generate_revision_plan": _schema(
        ("syllabus_id", "target_date"),
        {
            "syllabus_id": {"type": "string"},
            "target_date": _DATE_STRING,
        },
    ),
    "oppositions.update_progress": _schema(
        ("plan_id", "progress"),
        {
            "plan_id": {"type": "string"},
            "progress": {"type": "object"},
        },
    ),
}

# A study plan is a proposal, never an adoption, registration, or strategy
# change.
_STUDY_PLAN = _schema(
    ("target_id",),
    {
        "target_id": {"type": "string"},
        "scenario": {"type": "string"},
        "proposal_only": {"type": "boolean"},
        "adopted_decision": {"type": "boolean"},
        "calendar_not_modified": {"type": "boolean"},
    },
)

# Syllabus division structures the current known syllabus; it is conditional
# when syllabus identity/version is unresolved and never invents official
# content.
_SYLLABUS_DIVISION = _schema(
    ("blocks",),
    {
        "blocks": {"type": "array", "items": {"type": "string"}},
        "syllabus_version": {"type": "string"},
        "conditional": {"type": "boolean"},
        "verification_need": {"type": "boolean"},
    },
)

# Progress tracking is internal analysis, not a write.
_PROGRESS_TRACKING = _schema(
    ("progress",),
    {
        "progress": {"type": "array", "items": {"type": "string"}},
        "direct_write": {"type": "boolean"},
        "summary": {"type": "string"},
    },
)

# Mock exam review is grounded interpretation, never capacity inference.
_MOCK_REVIEW = _schema(
    ("interpretation",),
    {
        "interpretation": {"type": "string"},
        "trend_inferred": {"type": "boolean"},
        "capacity_inferred": {"type": "boolean"},
        "summary": {"type": "string"},
    },
)

# Body comparison is a trade-off proposal; it never changes the target.
_BODY_COMPARISON = _schema(
    ("comparison",),
    {
        "comparison": {"type": "array", "items": {"type": "string"}},
        "proposal_only": {"type": "boolean"},
        "target_unchanged": {"type": "boolean"},
    },
)

# Call review is read-only OFFICIAL_ONLY analysis; never registration.
_CALL_REVIEW = _schema(
    ("call_summary",),
    {
        "call_summary": {"type": "string"},
        "official_verification": {"type": "boolean"},
        "registration_none": {"type": "boolean"},
        "needs": _ID_ARRAY,
    },
)

_WEEKLY_REVIEW = _schema(
    ("review",), {"review": {"type": "string"}, "next_proposals": _ID_ARRAY}
)

_EXPLICIT_RISKS = _schema(
    ("risks",),
    {
        "risks": {"type": "array", "items": {"type": "string"}},
        "risk_as_certainty": {"type": "boolean"},
    },
)

_REVISION_PLAN = _schema(
    ("revision",),
    {
        "revision": {"type": "string"},
        "grounded_in_coverage": {"type": "boolean"},
        "proposal_only": {"type": "boolean"},
    },
)

_PROGRESS_UPDATE = _schema(
    ("update",),
    {
        "update": {"type": "string"},
        "proposal_only": {"type": "boolean"},
        "memory_not_modified": {"type": "boolean"},
    },
)

_OUTPUT_SCHEMAS = {
    "oppositions.create_study_plan": _schema(
        ("study_plan",), {"study_plan": _STUDY_PLAN}
    ),
    "oppositions.divide_syllabus": _schema(
        ("division",), {"division": _SYLLABUS_DIVISION}
    ),
    "oppositions.track_progress": _schema(
        ("tracking",), {"tracking": _PROGRESS_TRACKING}
    ),
    "oppositions.review_mock_exam": _schema(
        ("review",), {"review": _MOCK_REVIEW}
    ),
    "oppositions.compare_bodies": _schema(
        ("comparison",), {"comparison": _BODY_COMPARISON}
    ),
    "oppositions.review_call": _schema(
        ("review",), {"review": _CALL_REVIEW}
    ),
    "oppositions.generate_weekly_review": _schema(
        ("weekly_review",), {"weekly_review": _WEEKLY_REVIEW}
    ),
    "oppositions.identify_risks": _schema(
        ("risks",), {"risks": _EXPLICIT_RISKS}
    ),
    "oppositions.generate_revision_plan": _schema(
        ("revision_plan",), {"revision_plan": _REVISION_PLAN}
    ),
    "oppositions.update_progress": _schema(
        ("progress_update",), {"progress_update": _PROGRESS_UPDATE}
    ),
}


def build_oppositions_operation_definitions() -> tuple[
    DomainOperationDefinition, ...
]:
    """Build the ten Opposition Domain operation definitions deterministically."""
    result = []
    for operation_id in OPPOSITIONS_OPERATION_IDS:
        operation_type = _OPERATION_TYPES[operation_id]
        operation_name = operation_id.split(".", 1)[1]
        requires_approval = operation_id in _APPROVAL_REQUIRED
        result.append(
            DomainOperationDefinition(
                operation_id=operation_id,
                domain_id="domain:oppositions",
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
                    "phase": "10.23",
                    "domain": "oppositions",
                    "proposal_only": operation_id in _PROPOSAL_ONLY,
                },
            )
        )
    return tuple(result)


__all__ = [
    "OPPOSITIONS_OPERATION_IDS",
    "build_oppositions_operation_definitions",
]