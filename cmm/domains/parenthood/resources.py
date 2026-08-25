"""Phase 10.27 — Parenthood Domain Resources.

Builds the nineteen Parenthood resource definitions deterministically using
the shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts. Resources are definitions only (lineage and interpretation metadata).
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_RESOURCE_IDS,
    PARENTHOOD_RESOURCE_KINDS,
)
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

__all__ = [
    "PARENTHOOD_RESOURCE_KINDS",
    "build_parenthood_resource_definitions",
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
    metadata: dict | None = None,
) -> DomainResourceDefinition:
    return DomainResourceDefinition(
        id=resource_id,
        kind=resource_id.split(".", 1)[1],
        domain_id="domain:parenthood",
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


def build_parenthood_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the nineteen Parenthood Domain resource definitions deterministically.

    Definitions are returned in canonical order (catalog order).
    """
    by_id = {
        "parenthood.resource.life_plan": _resource(
            "parenthood.resource.life_plan",
            adapter="cognitive.document",
            entity_types=("parenthood_goal", "timeline", "long_term_plan"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.8,
            metadata={"provenance": True, "user_authored": True},
        ),
        "parenthood.resource.legal_document": _resource(
            "parenthood.resource.legal_document",
            adapter="cognitive.document",
            entity_types=(
                "legal_requirement",
                "administrative_requirement",
                "documentation_requirement",
            ),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.95,
            effective_date_required=True,
            expiration_required=True,
            metadata={"provenance": True, "legal_source": True},
        ),
        "parenthood.resource.medical_report": _resource(
            "parenthood.resource.medical_report",
            adapter="cognitive.document",
            entity_types=("medical_pathway", "medical_provider", "health_context"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.95,
            effective_date_required=True,
            metadata={"provenance": True, "clinical_source": True},
        ),
        "parenthood.resource.financial_plan": _resource(
            "parenthood.resource.financial_plan",
            adapter="cognitive.document",
            entity_types=("financial_scenario",),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            metadata={"provenance": True, "cost_planning": True},
        ),
        "parenthood.resource.provider_information": _resource(
            "parenthood.resource.provider_information",
            adapter="cognitive.document",
            entity_types=("medical_provider", "participant", "school"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.8,
            metadata={"provenance": True},
        ),
        "parenthood.resource.jurisdiction_information": _resource(
            "parenthood.resource.jurisdiction_information",
            adapter="cognitive.document",
            entity_types=("jurisdiction", "legal_requirement"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            effective_date_required=True,
            metadata={"provenance": True, "legal_reference": True},
        ),
        "parenthood.resource.decision": _resource(
            "parenthood.resource.decision",
            adapter="cognitive.note",
            entity_types=("decision", "parental_decision"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.9,
            metadata={"provenance": True, "explicit_decision": True},
        ),
        "parenthood.resource.note": _resource(
            "parenthood.resource.note",
            adapter="cognitive.note",
            entity_types=("parenthood_goal", "routine", "value"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            metadata={"provenance": True, "user_note": True},
        ),
        "parenthood.resource.parenting_note": _resource(
            "parenthood.resource.parenting_note",
            adapter="cognitive.note",
            entity_types=("care_need", "routine", "wellbeing_signal"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.8,
            metadata={"provenance": True, "child_scoped": True},
        ),
        "parenthood.resource.education_document": _resource(
            "parenthood.resource.education_document",
            adapter="cognitive.document",
            entity_types=("education_plan", "school", "activity"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.85,
            metadata={"provenance": True, "education": True},
        ),
        "parenthood.resource.child_development_resource": _resource(
            "parenthood.resource.child_development_resource",
            adapter="cognitive.document",
            entity_types=("developmental_stage", "milestone", "care_need"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            metadata={"provenance": True, "developmental_reference": True},
        ),
        "parenthood.resource.health_summary": _resource(
            "parenthood.resource.health_summary",
            adapter="cognitive.document",
            entity_types=("health_context", "care_need"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.9,
            metadata={"provenance": True, "child_health": True},
        ),
        "parenthood.resource.schedule": _resource(
            "parenthood.resource.schedule",
            adapter="cognitive.calendar",
            entity_types=("schedule", "routine", "timeline"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.8,
            metadata={"provenance": True, "schedule": True},
        ),
        "parenthood.resource.parental_decision": _resource(
            "parenthood.resource.parental_decision",
            adapter="cognitive.note",
            entity_types=("parental_decision", "boundary", "value"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.9,
            metadata={"provenance": True, "explicit_parental_choice": True},
        ),
        "parenthood.resource.school_information": _resource(
            "parenthood.resource.school_information",
            adapter="cognitive.document",
            entity_types=("school", "education_plan"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.8,
            metadata={"provenance": True},
        ),
        "parenthood.resource.activity_information": _resource(
            "parenthood.resource.activity_information",
            adapter="cognitive.document",
            entity_types=("activity", "routine"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.8,
            metadata={"provenance": True},
        ),
        "parenthood.resource.user_message": _resource(
            "parenthood.resource.user_message",
            adapter="cognitive.message",
            entity_types=("parenthood_goal", "decision", "value"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
        "parenthood.resource.external_source": _resource(
            "parenthood.resource.external_source",
            adapter="cognitive.external",
            entity_types=("jurisdiction",),
            sensitivity=SensitivityLevel.PUBLIC,
            reliability=0.75,
            effective_date_required=True,
            metadata={"provenance": True, "read_only_reference": True},
        ),
        "parenthood.resource.memory_entry": _resource(
            "parenthood.resource.memory_entry",
            adapter="cognitive.memory",
            entity_types=("decision", "parental_decision", "milestone"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.7,
            metadata={"provenance": True, "proposal_only": True},
        ),
    }

    return tuple(by_id[resource_id] for resource_id in CANONICAL_PARENTHOOD_RESOURCE_IDS)
