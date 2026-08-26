"""Phase 10.30 — Project Domain Resources.

Builds the 22 Project resource definitions deterministically using
the shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts. Resources are definitions only (lineage and interpretation metadata).
"""

from __future__ import annotations

from typing import Any

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_RESOURCE_IDS,
    CANONICAL_PROJECT_RESOURCE_KINDS,
)
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

GENERIC_PROJECT_RESOURCE_KINDS: tuple[str, ...] = (
    "project_brief",
    "project_plan",
    "milestone_record",
    "work_item_record",
    "dependency_record",
    "resource_record",
    "status_report",
    "decision_record",
    "risk_record",
    "project_timeline",
)

SOFTWARE_PROJECT_RESOURCE_KINDS: tuple[str, ...] = (
    "source_code",
    "project_file",
    "documentation",
    "test_result",
    "validation_result",
    "git_history",
    "issue",
    "roadmap",
    "architecture_document",
    "commit",
    "pull_request",
    "memory_entry",
)

PROJECT_STATUS_VALUES: tuple[str, ...] = (
    "planned",
    "active",
    "blocked",
    "paused",
    "completed",
    "failed",
    "cancelled",
)

PROJECT_DECISION_STATE_VALUES: tuple[str, ...] = (
    "option",
    "proposal",
    "decided",
    "approved",
    "applied",
    "rejected",
    "deferred",
    "cancelled",
)


def validate_project_status(value: str) -> str:
    """Validate project status against the closed vocabulary."""
    if not isinstance(value, str) or value not in PROJECT_STATUS_VALUES:
        raise ValueError(
            f"Invalid project status {value!r}; must be one of: {', '.join(PROJECT_STATUS_VALUES)}"
        )
    return value


def validate_project_decision_state(value: str) -> str:
    """Validate project decision state against the closed vocabulary."""
    if not isinstance(value, str) or value not in PROJECT_DECISION_STATE_VALUES:
        raise ValueError(
            f"Invalid project decision state {value!r}; must be one of: {', '.join(PROJECT_DECISION_STATE_VALUES)}"
        )
    return value


def _resource(
    resource_id: str,
    *,
    adapter: str,
    entity_types: tuple[str, ...],
    sensitivity: SensitivityLevel,
    reliability: float,
    effective_date_required: bool = False,
    expiration_required: bool = False,
    metadata: dict[str, Any] | None = None,
) -> DomainResourceDefinition:
    return DomainResourceDefinition(
        id=resource_id,
        kind=resource_id.split(".", 2)[2],
        domain_id="domain:project",
        adapter=adapter,
        entity_types=entity_types,
        default_sensitivity=sensitivity,
        default_reliability=reliability,
        temporal_policy=DomainResourceTemporalPolicy(
            effective_date_required=effective_date_required,
            expiration_required=expiration_required,
            historical_allowed=True,
        ),
        metadata=metadata or {},
    )


def build_project_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the 22 Project Domain resource definitions deterministically."""
    by_id = {
        # Generic project resources (10)
        "project.resource.project_brief": _resource(
            "project.resource.project_brief",
            adapter="cognitive.document",
            entity_types=("project", "objective", "deliverable"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        "project.resource.project_plan": _resource(
            "project.resource.project_plan",
            adapter="cognitive.document",
            entity_types=("project", "milestone", "work_item", "deliverable"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        "project.resource.milestone_record": _resource(
            "project.resource.milestone_record",
            adapter="cognitive.document",
            entity_types=("milestone", "deliverable"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        "project.resource.work_item_record": _resource(
            "project.resource.work_item_record",
            adapter="cognitive.document",
            entity_types=("work_item", "deliverable"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        "project.resource.dependency_record": _resource(
            "project.resource.dependency_record",
            adapter="cognitive.document",
            entity_types=("dependency", "constraint"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        "project.resource.resource_record": _resource(
            "project.resource.resource_record",
            adapter="cognitive.document",
            entity_types=("project_resource", "constraint"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        "project.resource.status_report": _resource(
            "project.resource.status_report",
            adapter="cognitive.document",
            entity_types=("status_change", "project_event"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.95,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        "project.resource.decision_record": _resource(
            "project.resource.decision_record",
            adapter="cognitive.document",
            entity_types=("decision",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.95,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        "project.resource.risk_record": _resource(
            "project.resource.risk_record",
            adapter="cognitive.document",
            entity_types=("risk", "constraint"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        "project.resource.project_timeline": _resource(
            "project.resource.project_timeline",
            adapter="cognitive.document",
            entity_types=("project", "milestone", "project_event"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "generic": True},
        ),
        # Software-project resources (12)
        "project.resource.source_code": _resource(
            "project.resource.source_code",
            adapter="cognitive.source_code",
            entity_types=(
                "repository",
                "module",
                "package",
                "file",
                "class",
                "method",
                "function",
            ),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.95,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.project_file": _resource(
            "project.resource.project_file",
            adapter="cognitive.document",
            entity_types=("file", "package"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.9,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.documentation": _resource(
            "project.resource.documentation",
            adapter="cognitive.document",
            entity_types=("contract", "architecture_decision"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.test_result": _resource(
            "project.resource.test_result",
            adapter="cognitive.document",
            entity_types=("test", "validation_result"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.95,
            effective_date_required=True,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.validation_result": _resource(
            "project.resource.validation_result",
            adapter="cognitive.document",
            entity_types=("validation_result",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.95,
            effective_date_required=True,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.git_history": _resource(
            "project.resource.git_history",
            adapter="cognitive.document",
            entity_types=("commit", "release"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.95,
            effective_date_required=True,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.issue": _resource(
            "project.resource.issue",
            adapter="cognitive.document",
            entity_types=("issue", "technical_debt"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.roadmap": _resource(
            "project.resource.roadmap",
            adapter="cognitive.document",
            entity_types=("milestone", "release"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.architecture_document": _resource(
            "project.resource.architecture_document",
            adapter="cognitive.document",
            entity_types=("architecture_decision", "contract"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.commit": _resource(
            "project.resource.commit",
            adapter="cognitive.document",
            entity_types=("commit",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.95,
            effective_date_required=True,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.pull_request": _resource(
            "project.resource.pull_request",
            adapter="cognitive.document",
            entity_types=("commit", "workflow"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "software": True},
        ),
        "project.resource.memory_entry": _resource(
            "project.resource.memory_entry",
            adapter="cognitive.document",
            entity_types=("decision", "milestone"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            metadata={"provenance": True, "proposal_only": True},
        ),
    }

    return tuple(by_id[res_id] for res_id in CANONICAL_PROJECT_RESOURCE_IDS)


__all__ = [
    "CANONICAL_PROJECT_RESOURCE_IDS",
    "CANONICAL_PROJECT_RESOURCE_KINDS",
    "GENERIC_PROJECT_RESOURCE_KINDS",
    "PROJECT_DECISION_STATE_VALUES",
    "PROJECT_STATUS_VALUES",
    "SOFTWARE_PROJECT_RESOURCE_KINDS",
    "build_project_resource_definitions",
    "validate_project_decision_state",
    "validate_project_status",
]
