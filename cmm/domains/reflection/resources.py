"""Phase 10.24 — Reflection Domain Resources.

Builds the nine Reflection resource definitions deterministically using the
shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts.  No resource store is created here: resources are definitions only.

Shared-resource principle: ``user_message``, ``conversation``, ``note``,
``journal_entry``, ``memory_entry``, ``relationship_event``, ``life_event``,
``goal`` and ``decision`` reuse the shared cognitive adapters and are never
duplicated just because Reflection interprets them differently.  Resource
metadata never creates truth: a resource existing is not the same as a fact
being authoritative, and ``memory_entry`` is provenance, not current truth.
``relationship_event`` is consumed only as an authorized minimal projection
through the shared cross-domain mechanism; no Relationships store/state is
merged.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.reflection.catalog import CANONICAL_REFLECTION_RESOURCE_IDS
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

REFLECTION_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_REFLECTION_RESOURCE_IDS
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
        domain_id="domain:reflection",
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


def build_reflection_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the nine Reflection Domain resource definitions deterministically.

    Definitions are returned in canonical order (sorted by resource ID).
    Every Reflection resource reuses the canonical provenance / temporality /
    reliability / sensitivity contracts.  ``memory_entry`` is provenance, not
    automatically current truth; ``relationship_event`` is an authorized
    minimal cross-domain projection only.
    """
    by_id = {
        "reflection.conversation": _resource(
            "reflection.conversation",
            adapter="cognitive.conversation",
            entity_types=("reflection", "question", "belief", "value"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True},
        ),
        "reflection.decision": _resource(
            "reflection.decision",
            adapter="cognitive.goal",
            entity_types=("decision", "value", "conflict"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "candidate_not_adopted": True,
            },
        ),
        "reflection.goal": _resource(
            "reflection.goal",
            adapter="cognitive.goal",
            entity_types=("value", "need", "goal"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True},
        ),
        "reflection.journal_entry": _resource(
            "reflection.journal_entry",
            adapter="cognitive.note",
            entity_types=(
                "reflection",
                "belief",
                "value",
                "emotion",
                "need",
                "conflict",
                "identity_narrative",
            ),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.6,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "user_reported": True,
                "interpretation_heavy": True,
            },
        ),
        "reflection.life_event": _resource(
            "reflection.life_event",
            adapter="cognitive.event",
            entity_types=("life_event", "identity_narrative", "emotion", "need"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.6,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True, "user_reported": True},
        ),
        "reflection.memory_entry": _resource(
            "reflection.memory_entry",
            adapter="cognitive.memory",
            entity_types=("belief", "value", "emotion", "need", "question"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.7,
            metadata={
                "memory_integration": True,
                "proposal_only": True,
                "provenance_not_truth": True,
            },
        ),
        "reflection.note": _resource(
            "reflection.note",
            adapter="cognitive.note",
            entity_types=("reflection", "belief", "value", "question"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True},
        ),
        "reflection.relationship_event": _resource(
            "reflection.relationship_event",
            adapter="cognitive.event",
            entity_types=("relationship_event", "conflict", "emotion", "need"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "cross_domain_projection": True,
                "minimal_authorized_projection": True,
                "no_relationships_store_merge": True,
            },
        ),
        "reflection.user_message": _resource(
            "reflection.user_message",
            adapter="cognitive.message",
            entity_types=("reflection", "belief", "value", "question", "emotion"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.5,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
    }
    return tuple(
        by_id[resource_id] for resource_id in CANONICAL_REFLECTION_RESOURCE_IDS
    )


__all__ = ["REFLECTION_RESOURCE_KINDS", "build_reflection_resource_definitions"]
