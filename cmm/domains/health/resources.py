"""Phase 10.20 — Health Domain Resources."""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.health.catalog import CANONICAL_HEALTH_RESOURCE_IDS
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

HEALTH_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_HEALTH_RESOURCE_IDS
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
        domain_id="domain:health",
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


def build_health_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the twelve Health Domain resource definitions deterministically.

    Definitions are returned in canonical order (sorted by resource ID).
    Every Health resource is **high sensitivity** (HIGHLY_SENSITIVE) and
    reuses the canonical provenance / temporality / reliability / sensitivity
    contracts rather than bypassing them.
    """
    by_id = {
        "health.appointment": _resource(
            "health.appointment",
            adapter="cognitive.appointment",
            entity_types=("appointment",),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True},
        ),
        "health.discharge_report": _resource(
            "health.discharge_report",
            adapter="cognitive.document",
            entity_types=("medical_report",),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.8,
            effective_date_required=True,
            metadata={"provenance": True, "clinical_document": True},
        ),
        "health.external_medical_source": _resource(
            "health.external_medical_source",
            adapter="cognitive.external",
            entity_types=("medical_report", "medical_condition"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.3,
            effective_date_required=True,
            expiration_required=True,
            metadata={
                "provenance": True,
                "untrusted": True,
                "external_medical": True,
            },
        ),
        "health.health_memory": _resource(
            "health.health_memory",
            adapter="cognitive.memory",
            entity_types=("medical_condition", "medication", "symptom"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.8,
            metadata={"memory_integration": True, "proposal_only": True},
        ),
        "health.imaging_report": _resource(
            "health.imaging_report",
            adapter="cognitive.document",
            entity_types=("medical_report", "medical_test"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.8,
            effective_date_required=True,
            metadata={"provenance": True, "clinical_document": True},
        ),
        "health.laboratory_result": _resource(
            "health.laboratory_result",
            adapter="cognitive.test_result",
            entity_types=("medical_test",),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.8,
            effective_date_required=True,
            expiration_required=True,
            metadata={"provenance": True, "clinical_document": True},
        ),
        "health.medical_report": _resource(
            "health.medical_report",
            adapter="cognitive.document",
            entity_types=("medical_report",),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.8,
            effective_date_required=True,
            metadata={"provenance": True, "clinical_document": True},
        ),
        "health.medication_list": _resource(
            "health.medication_list",
            adapter="cognitive.medication",
            entity_types=("medication",),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "medication_organizational": True,
            },
        ),
        "health.prescription": _resource(
            "health.prescription",
            adapter="cognitive.document",
            entity_types=("medication", "treatment"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.8,
            effective_date_required=True,
            expiration_required=True,
            metadata={"provenance": True, "clinical_document": True},
        ),
        "health.symptom_log": _resource(
            "health.symptom_log",
            adapter="cognitive.symptom",
            entity_types=("symptom", "vital_sign"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.5,
            effective_date_required=True,
            metadata={"provenance": True, "user_reported": True},
        ),
        "health.treatment_plan": _resource(
            "health.treatment_plan",
            adapter="cognitive.document",
            entity_types=("treatment", "procedure", "surgery"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.8,
            effective_date_required=True,
            metadata={"provenance": True, "clinical_document": True},
        ),
        "health.user_message": _resource(
            "health.user_message",
            adapter="cognitive.message",
            entity_types=("symptom", "medical_condition", "medication"),
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            reliability=0.5,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
    }
    return tuple(by_id[resource_id] for resource_id in CANONICAL_HEALTH_RESOURCE_IDS)


__all__ = ["HEALTH_RESOURCE_KINDS", "build_health_resource_definitions"]