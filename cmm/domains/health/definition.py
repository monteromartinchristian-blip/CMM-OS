"""Phase 10.20 — Health Domain Definition."""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.health.catalog import (
    CANONICAL_HEALTH_OPERATION_IDS,
    CANONICAL_HEALTH_RESOURCE_IDS,
    CANONICAL_HEALTH_RULE_IDS,
    CANONICAL_HEALTH_WORKFLOW_IDS,
)

HEALTH_DOMAIN_ID = "domain:health"
HEALTH_DOMAIN_VERSION = "1.0.0"
HEALTH_MANIFEST_ID = "manifest:health:1.0.0"
HEALTH_PROFILE_NAME = "HealthProfile"

HEALTH_RESOURCE_IDS: tuple[str, ...] = CANONICAL_HEALTH_RESOURCE_IDS
HEALTH_RULE_IDS: tuple[str, ...] = CANONICAL_HEALTH_RULE_IDS
HEALTH_OPERATION_IDS: tuple[str, ...] = CANONICAL_HEALTH_OPERATION_IDS
HEALTH_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_HEALTH_WORKFLOW_IDS

HEALTH_PERMISSION_IDS: tuple[str, ...] = ("domain-permission:health:1.0.0",)


def build_health_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:health`` definition deterministically."""
    return DomainDefinition(
        id=HEALTH_DOMAIN_ID,
        name="health",
        display_name="Health",
        version=HEALTH_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Personal Health domain for organizing health information, "
            "analyzing temporal evolution, preparing consults, comparing "
            "reports and tests, detecting contradictions and missing "
            "information, recognizing signals that require professional "
            "review, and producing traceable health context.  Health never "
            "provides definitive diagnoses, never modifies medication, never "
            "takes treatment decisions, and never communicates externally "
            "without the required approval path."
        ),
        manifest_id=HEALTH_MANIFEST_ID,
        reasoning_profile=HEALTH_PROFILE_NAME,
        resources=HEALTH_RESOURCE_IDS,
        rules=HEALTH_RULE_IDS,
        operations=HEALTH_OPERATION_IDS,
        workflows=HEALTH_WORKFLOW_IDS,
        permissions=HEALTH_PERMISSION_IDS,
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
                name="health_timeline",
                kind="timeline",
                provided_by=HEALTH_DOMAIN_ID,
                version=HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.20"},
            ),
            DomainCapability(
                name="health_comparison",
                kind="analysis",
                provided_by=HEALTH_DOMAIN_ID,
                version=HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.20"},
            ),
            DomainCapability(
                name="health_summary",
                kind="operation",
                provided_by=HEALTH_DOMAIN_ID,
                version=HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.20"},
            ),
            DomainCapability(
                name="health_questions",
                kind="presentation",
                provided_by=HEALTH_DOMAIN_ID,
                version=HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.20"},
            ),
            DomainCapability(
                name="health_escalation",
                kind="safety",
                provided_by=HEALTH_DOMAIN_ID,
                version=HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.20"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("health", "personal", "high-sensitivity"),
            metadata={"phase": "10.20"},
        ),
    )


__all__ = [
    "HEALTH_DOMAIN_ID",
    "HEALTH_DOMAIN_VERSION",
    "HEALTH_MANIFEST_ID",
    "HEALTH_OPERATION_IDS",
    "HEALTH_PERMISSION_IDS",
    "HEALTH_PROFILE_NAME",
    "HEALTH_RESOURCE_IDS",
    "HEALTH_RULE_IDS",
    "HEALTH_WORKFLOW_IDS",
    "build_health_domain_definition",
]