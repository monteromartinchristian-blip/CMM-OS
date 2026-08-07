"""Phase 10.19 — General Domain Resources."""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.general.catalog import CANONICAL_GENERAL_RESOURCE_IDS
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

GENERAL_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_GENERAL_RESOURCE_IDS
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
        domain_id="domain:general",
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


def build_general_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the nine General Domain resource definitions deterministically.

    Definitions are returned in canonical order (sorted by resource ID).
    """
    by_id = {
        "general.calendar_event": _resource(
            "general.calendar_event",
            adapter="cognitive.calendar",
            entity_types=("calendar_event",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.7,
            effective_date_required=True,
        ),
        "general.conversation": _resource(
            "general.conversation",
            adapter="cognitive.conversation",
            entity_types=("conversation",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.5,
            metadata={"composite": True},
        ),
        "general.document": _resource(
            "general.document",
            adapter="cognitive.document",
            entity_types=("document",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.7,
        ),
        "general.external_source": _resource(
            "general.external_source",
            adapter="cognitive.external",
            entity_types=("external_source",),
            sensitivity=SensitivityLevel.RESTRICTED,
            reliability=0.3,
            effective_date_required=True,
            expiration_required=True,
            metadata={"untrusted": True},
        ),
        "general.generic_goal": _resource(
            "general.generic_goal",
            adapter="cognitive.goal",
            entity_types=("goal",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.6,
        ),
        "general.generic_task": _resource(
            "general.generic_task",
            adapter="cognitive.task",
            entity_types=("task",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.6,
        ),
        "general.memory_entry": _resource(
            "general.memory_entry",
            adapter="cognitive.memory",
            entity_types=("memory_entry",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.8,
            metadata={"memory_integration": True},
        ),
        "general.note": _resource(
            "general.note",
            adapter="cognitive.note",
            entity_types=("note",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.6,
        ),
        "general.user_message": _resource(
            "general.user_message",
            adapter="cognitive.message",
            entity_types=("message",),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.5,
            metadata={"unverified": True},
        ),
    }
    return tuple(by_id[resource_id] for resource_id in CANONICAL_GENERAL_RESOURCE_IDS)


__all__ = ["GENERAL_RESOURCE_KINDS", "build_general_resource_definitions"]