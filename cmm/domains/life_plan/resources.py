"""Phase 10.29 — Life Plan Domain Resources.

Builds the twelve Life Plan resource definitions deterministically using
the shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts. Resources are definitions only (lineage and interpretation metadata).
"""

from __future__ import annotations

from typing import Any

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_RESOURCE_IDS,
    LIFE_PLAN_RESOURCE_KINDS,
)
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

__all__ = [
    "LIFE_PLAN_RESOURCE_KINDS",
    "build_life_plan_resource_definitions",
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
        domain_id="domain:life-plan",
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


def build_life_plan_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the twelve Life Plan Domain resource definitions deterministically.

    Definitions are returned in canonical order (catalog order).
    """
    by_id = {
        "life_plan.resource.life_plan": _resource(
            "life_plan.resource.life_plan",
            adapter="cognitive.document",
            entity_types=("life_goal", "milestone", "scenario", "timeline"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "plan_source": True},
        ),
        "life_plan.resource.financial_plan": _resource(
            "life_plan.resource.financial_plan",
            adapter="cognitive.document",
            entity_types=("financial_resource", "constraint"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "financial_source": True},
        ),
        "life_plan.resource.academic_plan": _resource(
            "life_plan.resource.academic_plan",
            adapter="cognitive.document",
            entity_types=("education_path", "milestone"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "academic_source": True,
                "minimized_projection_only": True,
            },
        ),
        "life_plan.resource.opposition_plan": _resource(
            "life_plan.resource.opposition_plan",
            adapter="cognitive.document",
            entity_types=("career_path", "milestone"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "opposition_source": True,
                "minimized_projection_only": True,
            },
        ),
        "life_plan.resource.health_constraints": _resource(
            "life_plan.resource.health_constraints",
            adapter="cognitive.document",
            entity_types=("constraint", "risk"),
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
        "life_plan.resource.family_plan": _resource(
            "life_plan.resource.family_plan",
            adapter="cognitive.document",
            entity_types=("family_goal", "dependency"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.9,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "family_source": True,
                "minimized_projection_only": True,
            },
        ),
        "life_plan.resource.housing_plan": _resource(
            "life_plan.resource.housing_plan",
            adapter="cognitive.document",
            entity_types=("housing_goal", "financial_resource"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={"provenance": True, "housing_source": True},
        ),
        "life_plan.resource.goal": _resource(
            "life_plan.resource.goal",
            adapter="cognitive.document",
            entity_types=("life_goal", "milestone"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"provenance": True, "goal_source": True},
        ),
        "life_plan.resource.decision": _resource(
            "life_plan.resource.decision",
            adapter="cognitive.document",
            entity_types=("decision", "scenario"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.95,
            effective_date_required=True,
            metadata={"provenance": True, "decision_source": True},
        ),
        "life_plan.resource.calendar_event": _resource(
            "life_plan.resource.calendar_event",
            adapter="cognitive.document",
            entity_types=("timeline", "milestone"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.8,
            effective_date_required=True,
            metadata={"provenance": True, "approval_required_for_mutation": True},
        ),
        "life_plan.resource.memory_entry": _resource(
            "life_plan.resource.memory_entry",
            adapter="cognitive.document",
            entity_types=("life_goal", "decision", "milestone"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            metadata={"provenance": True, "proposal_only": True},
        ),
        "life_plan.resource.user_message": _resource(
            "life_plan.resource.user_message",
            adapter="cognitive.document",
            entity_types=("life_goal", "decision", "scenario"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.8,
            metadata={"provenance": True, "user_authored": True},
        ),
    }

    return tuple(by_id[res_id] for res_id in CANONICAL_LIFE_PLAN_RESOURCE_IDS)
