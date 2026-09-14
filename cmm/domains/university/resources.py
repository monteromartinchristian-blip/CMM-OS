"""Phase 10.22 — University Domain Resources."""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)
from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RESOURCE_IDS

UNIVERSITY_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_UNIVERSITY_RESOURCE_IDS
)


def _resource(
    resource_id: str,
    *,
    adapter: str,
    entity_types: tuple[str, ...],
    sensitivity: SensitivityLevel,
    reliability: float,
    effective_date_required: bool = False,
    expiration_required: bool = False,
    metadata: dict | None = None,
) -> DomainResourceDefinition:
    return DomainResourceDefinition(
        id=resource_id,
        kind=resource_id.split(".", 1)[1],
        domain_id="domain:university",
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


def build_university_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the twelve University Domain resource definitions deterministically.

    Definitions are returned in canonical order (sorted by resource ID).
    Every University resource reuses the canonical provenance / temporality /
    reliability / sensitivity contracts rather than bypassing them.

    ``university.email`` represents an existing email or email context.  It does
    NOT authorize sending.  ``university.memory_entry`` represents personal
    memory and never overrides Academic State.
    """
    by_id = {
        "university.academic_record": _resource(
            "university.academic_record",
            adapter="cognitive.record",
            entity_types=(
                "subject",
                "grade",
                "credit",
                "exam_attempt",
                "academic_requirement",
            ),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.9,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
                "academic_state": True,
            },
        ),
        "university.subject_guide": _resource(
            "university.subject_guide",
            adapter="cognitive.document",
            entity_types=(
                "subject",
                "examination",
                "assignment",
                "academic_requirement",
            ),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
            },
        ),
        "university.university_calendar": _resource(
            "university.university_calendar",
            adapter="cognitive.calendar",
            entity_types=("deadline", "semester", "academic_year"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.8,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
            },
        ),
        "university.examination_schedule": _resource(
            "university.examination_schedule",
            adapter="cognitive.schedule",
            entity_types=("examination", "deadline", "exam_attempt"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
                "specific_call": True,
            },
        ),
        "university.assignment": _resource(
            "university.assignment",
            adapter="cognitive.document",
            entity_types=("assignment", "deadline", "subject"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.8,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
            },
        ),
        "university.grade": _resource(
            "university.grade",
            adapter="cognitive.record",
            entity_types=("grade", "subject", "exam_attempt"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.85,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
                "academic_state": True,
            },
        ),
        "university.email": _resource(
            "university.email",
            adapter="cognitive.message",
            entity_types=("subject", "deadline", "professor", "assignment"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "preparation_only": True,
                "no_authorization_send": True,
            },
        ),
        "university.note": _resource(
            "university.note",
            adapter="cognitive.note",
            entity_types=("subject", "semester", "deadline"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True},
        ),
        "university.study_session": _resource(
            "university.study_session",
            adapter="cognitive.event",
            entity_types=("subject", "semester", "academic_year"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True, "user_reported": True},
        ),
        "university.user_message": _resource(
            "university.user_message",
            adapter="cognitive.message",
            entity_types=("subject", "deadline", "assignment", "examination"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.5,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
        "university.regulation": _resource(
            "university.regulation",
            adapter="cognitive.document",
            entity_types=(
                "academic_requirement",
                "examination",
                "exam_attempt",
                "deadline",
                "credit",
            ),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            effective_date_required=True,
            expiration_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
                "regulation": True,
            },
        ),
        "university.memory_entry": _resource(
            "university.memory_entry",
            adapter="cognitive.memory",
            entity_types=(
                "subject",
                "semester",
                "assignment",
                "examination",
            ),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={
                "memory_integration": True,
                "proposal_only": True,
                "not_academic_state": True,
            },
        ),
    }
    return tuple(
        by_id[resource_id] for resource_id in CANONICAL_UNIVERSITY_RESOURCE_IDS
    )


__all__ = ["UNIVERSITY_RESOURCE_KINDS", "build_university_resource_definitions"]
