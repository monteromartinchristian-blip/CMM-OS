"""Phase 10.19 — General Domain Definition."""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.general.catalog import (
    CANONICAL_GENERAL_OPERATION_IDS,
    CANONICAL_GENERAL_RESOURCE_IDS,
    CANONICAL_GENERAL_RULE_IDS,
    CANONICAL_GENERAL_WORKFLOW_IDS,
)

GENERAL_DOMAIN_ID = "domain:general"
GENERAL_DOMAIN_VERSION = "1.0.0"
GENERAL_MANIFEST_ID = "manifest:general:1.0.0"
GENERAL_PROFILE_NAME = "GeneralProfile"

GENERAL_RESOURCE_IDS: tuple[str, ...] = CANONICAL_GENERAL_RESOURCE_IDS
GENERAL_RULE_IDS: tuple[str, ...] = CANONICAL_GENERAL_RULE_IDS
GENERAL_OPERATION_IDS: tuple[str, ...] = CANONICAL_GENERAL_OPERATION_IDS
GENERAL_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_GENERAL_WORKFLOW_IDS

GENERAL_PERMISSION_IDS: tuple[str, ...] = ("domain-permission:general:1.0.0",)


def build_general_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:general`` definition deterministically."""
    return DomainDefinition(
        id=GENERAL_DOMAIN_ID,
        name="general",
        display_name="General",
        version=GENERAL_DOMAIN_VERSION,
        kind=DomainKind.CORE,
        description=(
            "Base domain for non-specialized requests, general information "
            "analysis, common information organization, goal clarification, "
            "prudent decision support, periodic reviews, and safe fallback "
            "when no specialized domain applies."
        ),
        manifest_id=GENERAL_MANIFEST_ID,
        reasoning_profile=GENERAL_PROFILE_NAME,
        resources=GENERAL_RESOURCE_IDS,
        rules=GENERAL_RULE_IDS,
        operations=GENERAL_OPERATION_IDS,
        workflows=GENERAL_WORKFLOW_IDS,
        permissions=GENERAL_PERMISSION_IDS,
        validators=(),
        presentation_policy={
            "detail_level": "standard",
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
                name="general_analysis",
                kind="reasoning",
                provided_by=GENERAL_DOMAIN_ID,
                version=GENERAL_DOMAIN_VERSION,
                metadata={"phase": "10.19"},
            ),
            DomainCapability(
                name="general_summary",
                kind="operation",
                provided_by=GENERAL_DOMAIN_ID,
                version=GENERAL_DOMAIN_VERSION,
                metadata={"phase": "10.19"},
            ),
            DomainCapability(
                name="general_timeline",
                kind="timeline",
                provided_by=GENERAL_DOMAIN_ID,
                version=GENERAL_DOMAIN_VERSION,
                metadata={"phase": "10.19"},
            ),
            DomainCapability(
                name="general_questions",
                kind="presentation",
                provided_by=GENERAL_DOMAIN_ID,
                version=GENERAL_DOMAIN_VERSION,
                metadata={"phase": "10.19"},
            ),
            DomainCapability(
                name="general_fallback",
                kind="classification",
                provided_by=GENERAL_DOMAIN_ID,
                version=GENERAL_DOMAIN_VERSION,
                metadata={"phase": "10.19"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("general", "fallback", "core"),
            metadata={"phase": "10.19"},
        ),
    )


__all__ = [
    "GENERAL_DOMAIN_ID",
    "GENERAL_DOMAIN_VERSION",
    "GENERAL_MANIFEST_ID",
    "GENERAL_OPERATION_IDS",
    "GENERAL_PERMISSION_IDS",
    "GENERAL_PROFILE_NAME",
    "GENERAL_RESOURCE_IDS",
    "GENERAL_RULE_IDS",
    "GENERAL_WORKFLOW_IDS",
    "build_general_domain_definition",
]