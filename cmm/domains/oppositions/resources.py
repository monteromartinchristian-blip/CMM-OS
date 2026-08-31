"""Phase 10.23 — Opposition Domain Resources.

Builds the eleven Opposition resource definitions deterministically using the
shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts.  No resource store is created here: resources are definitions only.

Shared-resource principle: ``calendar_event``, ``note``, ``user_message``,
``memory_entry`` and external-source content reuse the shared cognitive
adapters and are never duplicated just because Oppositions interprets them
differently.  Resource metadata never creates truth: a resource existing is
not the same as a fact being authoritative.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.oppositions.catalog import CANONICAL_OPPOSITION_RESOURCE_IDS
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

OPPOSITIONS_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_OPPOSITION_RESOURCE_IDS
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
        domain_id="domain:oppositions",
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


def build_oppositions_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the eleven Opposition Domain resource definitions.

    Definitions are returned in canonical order (sorted by resource ID).
    Every Opposition resource reuses the canonical provenance / temporality /
    reliability / sensitivity contracts.  ``calendar_event``, ``note``,
    ``user_message``, ``memory_entry`` and external-source content reuse shared
    adapters and are not duplicated.  Resource metadata (``official_capable``)
    only marks the *capability* to represent official evidence; it never makes
    a resource authoritative by itself.
    """
    by_id = {
        "oppositions.official_call": _resource(
            "oppositions.official_call",
            adapter="cognitive.document",
            entity_types=("call", "deadline", "requirement", "exam"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
                "specific_call": True,
            },
        ),
        "oppositions.syllabus": _resource(
            "oppositions.syllabus",
            adapter="cognitive.document",
            entity_types=("syllabus", "topic", "block"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
            },
        ),
        "oppositions.regulation": _resource(
            "oppositions.regulation",
            adapter="cognitive.document",
            entity_types=("requirement", "merit", "call"),
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
        "oppositions.study_plan": _resource(
            "oppositions.study_plan",
            adapter="cognitive.document",
            entity_types=("syllabus", "topic", "block", "study_session"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            metadata={
                "provenance": True,
                "proposal_only": True,
                "not_official_state": True,
            },
        ),
        "oppositions.mock_exam": _resource(
            "oppositions.mock_exam",
            adapter="cognitive.record",
            entity_types=("mock_exam", "exam", "score"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True, "user_reported": True},
        ),
        "oppositions.score_record": _resource(
            "oppositions.score_record",
            adapter="cognitive.record",
            entity_types=("score", "mock_exam"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.75,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True, "user_reported": True},
        ),
        "oppositions.calendar_event": _resource(
            "oppositions.calendar_event",
            adapter="cognitive.calendar",
            entity_types=("study_session", "deadline", "call"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.75,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "shared_adapter": True,
                "mutation_approval_gated": True,
            },
        ),
        "oppositions.note": _resource(
            "oppositions.note",
            adapter="cognitive.note",
            entity_types=("topic", "syllabus", "call"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True},
        ),
        "oppositions.user_message": _resource(
            "oppositions.user_message",
            adapter="cognitive.message",
            entity_types=("call", "deadline", "syllabus", "topic"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.5,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
        "oppositions.external_official_source": _resource(
            "oppositions.external_official_source",
            adapter="cognitive.document",
            entity_types=("call", "syllabus", "requirement", "merit", "public_body"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "official_capable": True,
                "external_source": True,
            },
        ),
        "oppositions.memory_entry": _resource(
            "oppositions.memory_entry",
            adapter="cognitive.memory",
            entity_types=("study_session", "topic", "syllabus", "call"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={
                "memory_integration": True,
                "proposal_only": True,
                "not_official_state": True,
            },
        ),
    }
    return tuple(
        by_id[resource_id] for resource_id in CANONICAL_OPPOSITION_RESOURCE_IDS
    )


__all__ = ["OPPOSITIONS_RESOURCE_KINDS", "build_oppositions_resource_definitions"]
