"""Phase 10.28 — Sport Domain Definition.

Builds the immutable ``domain:sport`` definition deterministically using
the shared ``DomainDefinition`` contract. No global registration at import time.
"""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_OPERATION_IDS,
    CANONICAL_SPORT_RESOURCE_IDS,
    CANONICAL_SPORT_RULE_IDS,
    CANONICAL_SPORT_WORKFLOW_IDS,
)

SPORT_DOMAIN_ID = "domain:sport"
SPORT_DOMAIN_VERSION = "1.0.0"
SPORT_MANIFEST_ID = "manifest:sport:1.0.0"
SPORT_PROFILE_NAME = "SportProfile"

SPORT_RESOURCE_IDS: tuple[str, ...] = CANONICAL_SPORT_RESOURCE_IDS
SPORT_RULE_IDS: tuple[str, ...] = CANONICAL_SPORT_RULE_IDS
SPORT_OPERATION_IDS: tuple[str, ...] = CANONICAL_SPORT_OPERATION_IDS
SPORT_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_SPORT_WORKFLOW_IDS

SPORT_PERMISSION_IDS: tuple[str, ...] = ("domain-permission:sport:1.0.0",)


def build_sport_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:sport`` definition deterministically."""
    return DomainDefinition(
        id=SPORT_DOMAIN_ID,
        name="sport",
        display_name="Sport",
        version=SPORT_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Sport domain supporting athletic training, progression, physical "
            "activity goals, load management, recovery tracking, body measurements, "
            "injury risk signals, and controlled Health coordination. Does not "
            "diagnose injuries or prescribe medical treatments."
        ),
        manifest_id=SPORT_MANIFEST_ID,
        reasoning_profile=SPORT_PROFILE_NAME,
        resources=SPORT_RESOURCE_IDS,
        rules=SPORT_RULE_IDS,
        operations=SPORT_OPERATION_IDS,
        workflows=SPORT_WORKFLOW_IDS,
        permissions=SPORT_PERMISSION_IDS,
        validators=(),
        presentation_policy={
            "detail_level": "detailed",
            "include_uncertainty": True,
            "include_provenance": True,
            "include_alternatives": True,
            "allow_speculation": False,
            "require_disclaimers": True,
        },
        dependencies=(),
        optional_dependencies=(),
        conflicts=(),
        capabilities=(
            DomainCapability(
                name="sport_training_planning",
                kind="planning",
                provided_by=SPORT_DOMAIN_ID,
                version=SPORT_DOMAIN_VERSION,
                metadata={"phase": "10.28"},
            ),
            DomainCapability(
                name="sport_training_load_review",
                kind="analysis",
                provided_by=SPORT_DOMAIN_ID,
                version=SPORT_DOMAIN_VERSION,
                metadata={"phase": "10.28"},
            ),
            DomainCapability(
                name="sport_progress_review",
                kind="analysis",
                provided_by=SPORT_DOMAIN_ID,
                version=SPORT_DOMAIN_VERSION,
                metadata={"phase": "10.28"},
            ),
            DomainCapability(
                name="sport_recovery_review",
                kind="analysis",
                provided_by=SPORT_DOMAIN_ID,
                version=SPORT_DOMAIN_VERSION,
                metadata={"phase": "10.28"},
            ),
            DomainCapability(
                name="sport_measurement_tracking",
                kind="reasoning",
                provided_by=SPORT_DOMAIN_ID,
                version=SPORT_DOMAIN_VERSION,
                metadata={"phase": "10.28"},
            ),
            DomainCapability(
                name="sport_risk_identification",
                kind="analysis",
                provided_by=SPORT_DOMAIN_ID,
                version=SPORT_DOMAIN_VERSION,
                metadata={"phase": "10.28"},
            ),
            DomainCapability(
                name="sport_health_constraint_coordination",
                kind="reasoning",
                provided_by=SPORT_DOMAIN_ID,
                version=SPORT_DOMAIN_VERSION,
                metadata={"phase": "10.28"},
            ),
            DomainCapability(
                name="sport_schedule_proposal",
                kind="planning",
                provided_by=SPORT_DOMAIN_ID,
                version=SPORT_DOMAIN_VERSION,
                metadata={"phase": "10.28"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("sport", "training", "exercise", "workout", "fitness", "recovery"),
            metadata={"phase": "10.28"},
        ),
    )


__all__ = [
    "SPORT_DOMAIN_ID",
    "SPORT_DOMAIN_VERSION",
    "SPORT_MANIFEST_ID",
    "SPORT_OPERATION_IDS",
    "SPORT_PERMISSION_IDS",
    "SPORT_PROFILE_NAME",
    "SPORT_RESOURCE_IDS",
    "SPORT_RULE_IDS",
    "SPORT_WORKFLOW_IDS",
    "build_sport_domain_definition",
]
