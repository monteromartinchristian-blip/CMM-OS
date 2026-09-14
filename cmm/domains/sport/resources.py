"""Phase 10.28 — Sport Domain Resources.

Builds the nine Sport resource definitions deterministically using
the shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts. Resources are definitions only (lineage and interpretation metadata).
"""

from __future__ import annotations

from typing import Any

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)
from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_RESOURCE_IDS,
    SPORT_RESOURCE_KINDS,
)

__all__ = [
    "SPORT_RESOURCE_KINDS",
    "build_sport_resource_definitions",
]


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
        kind=resource_id.split(".", 1)[1],
        domain_id="domain:sport",
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


def build_sport_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the nine Sport Domain resource definitions deterministically.

    Definitions are returned in canonical order (catalog order).
    """
    by_id = {
        "sport.resource.workout_log": _resource(
            "sport.resource.workout_log",
            adapter="cognitive.document",
            entity_types=("workout", "session", "exercise", "performance_record"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "activity_source": True},
        ),
        "sport.resource.health_resource": _resource(
            "sport.resource.health_resource",
            adapter="cognitive.document",
            entity_types=("injury", "recovery"),
            sensitivity=SensitivityLevel.RESTRICTED,
            reliability=0.95,
            effective_date_required=True,
            expiration_required=True,
            metadata={
                "provenance": True,
                "health_projection_only": True,
                "unrestricted_health_access": False,
            },
        ),
        "sport.resource.body_measurement": _resource(
            "sport.resource.body_measurement",
            adapter="cognitive.document",
            entity_types=("body_measurement", "metric"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "measurement_source": True},
        ),
        "sport.resource.training_plan": _resource(
            "sport.resource.training_plan",
            adapter="cognitive.document",
            entity_types=("training_plan", "sport_goal", "exercise"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={"provenance": True, "plan_source": True},
        ),
        "sport.resource.calendar_event": _resource(
            "sport.resource.calendar_event",
            adapter="cognitive.document",
            entity_types=("session", "workout"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.8,
            effective_date_required=True,
            metadata={"provenance": True, "approval_required_for_mutation": True},
        ),
        "sport.resource.user_message": _resource(
            "sport.resource.user_message",
            adapter="cognitive.document",
            entity_types=("sport_goal", "recovery", "session"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.8,
            metadata={"provenance": True, "user_authored": True},
        ),
        "sport.resource.note": _resource(
            "sport.resource.note",
            adapter="cognitive.document",
            entity_types=("workout", "equipment", "exercise"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.75,
            metadata={"provenance": True, "note_source": True},
        ),
        "sport.resource.wearable_data": _resource(
            "sport.resource.wearable_data",
            adapter="cognitive.document",
            entity_types=("metric", "session", "recovery", "performance_record"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "telemetry_source": True},
        ),
        "sport.resource.memory_entry": _resource(
            "sport.resource.memory_entry",
            adapter="cognitive.document",
            entity_types=("sport_goal", "training_plan", "performance_record"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            metadata={"provenance": True, "proposal_only": True},
        ),
    }

    return tuple(by_id[res_id] for res_id in CANONICAL_SPORT_RESOURCE_IDS)
