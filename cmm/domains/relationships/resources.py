"""Phase 10.21 — Relationships Domain Resources."""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_RESOURCE_IDS
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

RELATIONSHIPS_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_RELATIONSHIPS_RESOURCE_IDS
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
        domain_id="domain:relationships",
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


def build_relationships_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the eight Relationships Domain resource definitions deterministically.

    Definitions are returned in canonical order (sorted by resource ID).
    Every Relationships resource is **high sensitivity** (HIGHLY_SENSITIVE) and
    reuses the canonical provenance / temporality / reliability / sensitivity
    contracts rather than bypassing them.

    ``relationships.communication`` represents an existing communication or
    communication context.  It does NOT authorize communication execution.
    """
    by_id = {
        "relationships.communication": _resource(
            "relationships.communication",
            adapter="cognitive.message",
            entity_types=("conversation", "interaction"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "communication_context": True,
                "no_authorization_send": True,
            },
        ),
        "relationships.conversation": _resource(
            "relationships.conversation",
            adapter="cognitive.conversation",
            entity_types=("conversation", "interaction"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True},
        ),
        "relationships.memory_entry": _resource(
            "relationships.memory_entry",
            adapter="cognitive.memory",
            entity_types=(
                "relationship",
                "person",
                "emotion",
                "need",
                "boundary",
            ),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.8,
            metadata={"memory_integration": True, "proposal_only": True},
        ),
        "relationships.note": _resource(
            "relationships.note",
            adapter="cognitive.note",
            entity_types=("person", "relationship"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True},
        ),
        "relationships.personal_reflection": _resource(
            "relationships.personal_reflection",
            adapter="cognitive.note",
            entity_types=("emotion", "need", "expectation"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.5,
            metadata={
                "provenance": True,
                "user_reported": True,
                "interpretation_heavy": True,
            },
        ),
        "relationships.relationship_event": _resource(
            "relationships.relationship_event",
            adapter="cognitive.event",
            entity_types=(
                "conflict",
                "rupture",
                "reconciliation",
                "interaction",
                "commitment",
                "support_event",
            ),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True},
        ),
        "relationships.timeline": _resource(
            "relationships.timeline",
            adapter="cognitive.timeline",
            entity_types=("relationship", "interaction"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True, "derived": True},
        ),
        "relationships.user_message": _resource(
            "relationships.user_message",
            adapter="cognitive.message",
            entity_types=(
                "person",
                "emotion",
                "need",
                "expectation",
                "boundary",
            ),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.5,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
    }
    return tuple(
        by_id[resource_id] for resource_id in CANONICAL_RELATIONSHIPS_RESOURCE_IDS
    )


__all__ = ["RELATIONSHIPS_RESOURCE_KINDS", "build_relationships_resource_definitions"]
