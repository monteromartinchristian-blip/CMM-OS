"""Phase 10.21 — Relationships Domain Definition."""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.relationships.catalog import (
    CANONICAL_RELATIONSHIPS_OPERATION_IDS,
    CANONICAL_RELATIONSHIPS_RESOURCE_IDS,
    CANONICAL_RELATIONSHIPS_RULE_IDS,
    CANONICAL_RELATIONSHIPS_WORKFLOW_IDS,
)

RELATIONSHIPS_DOMAIN_ID = "domain:relationships"
RELATIONSHIPS_DOMAIN_VERSION = "1.0.0"
RELATIONSHIPS_MANIFEST_ID = "manifest:relationships:1.0.0"
RELATIONSHIPS_PROFILE_NAME = "RelationshipsProfile"

RELATIONSHIPS_RESOURCE_IDS: tuple[str, ...] = CANONICAL_RELATIONSHIPS_RESOURCE_IDS
RELATIONSHIPS_RULE_IDS: tuple[str, ...] = CANONICAL_RELATIONSHIPS_RULE_IDS
RELATIONSHIPS_OPERATION_IDS: tuple[str, ...] = CANONICAL_RELATIONSHIPS_OPERATION_IDS
RELATIONSHIPS_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_RELATIONSHIPS_WORKFLOW_IDS

RELATIONSHIPS_PERMISSION_IDS: tuple[str, ...] = (
    "domain-permission:relationships:1.0.0",
)


def build_relationships_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:relationships`` definition deterministically."""
    return DomainDefinition(
        id=RELATIONSHIPS_DOMAIN_ID,
        name="relationships",
        display_name="Relationships",
        version=RELATIONSHIPS_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Personal Relationships domain for organizing and analysing "
            "relationships, interactions, conversations, conflicts, relational "
            "events, emotional responses, needs, expectations, commitments, "
            "boundaries, ruptures, reconciliations, and support events.  "
            "Relationships preserves the distinction between observed "
            "behavior, direct statements, user interpretations, and system "
            "hypotheses.  It never attributes intentions without direct "
            "evidence, never diagnoses a third party, never collapses "
            "ambivalence, never adopts a relational decision without explicit "
            "confirmation, and never contacts or communicates with another "
            "person automatically."
        ),
        manifest_id=RELATIONSHIPS_MANIFEST_ID,
        reasoning_profile=RELATIONSHIPS_PROFILE_NAME,
        resources=RELATIONSHIPS_RESOURCE_IDS,
        rules=RELATIONSHIPS_RULE_IDS,
        operations=RELATIONSHIPS_OPERATION_IDS,
        workflows=RELATIONSHIPS_WORKFLOW_IDS,
        permissions=RELATIONSHIPS_PERMISSION_IDS,
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
                name="relationships_timeline",
                kind="timeline",
                provided_by=RELATIONSHIPS_DOMAIN_ID,
                version=RELATIONSHIPS_DOMAIN_VERSION,
                metadata={"phase": "10.21"},
            ),
            DomainCapability(
                name="relationships_analysis",
                kind="reasoning",
                provided_by=RELATIONSHIPS_DOMAIN_ID,
                version=RELATIONSHIPS_DOMAIN_VERSION,
                metadata={"phase": "10.21"},
            ),
            DomainCapability(
                name="relationships_boundary",
                kind="analysis",
                provided_by=RELATIONSHIPS_DOMAIN_ID,
                version=RELATIONSHIPS_DOMAIN_VERSION,
                metadata={"phase": "10.21"},
            ),
            DomainCapability(
                name="relationships_preparation",
                kind="operation",
                provided_by=RELATIONSHIPS_DOMAIN_ID,
                version=RELATIONSHIPS_DOMAIN_VERSION,
                metadata={"phase": "10.21"},
            ),
            DomainCapability(
                name="relationships_decision_support",
                kind="safety",
                provided_by=RELATIONSHIPS_DOMAIN_ID,
                version=RELATIONSHIPS_DOMAIN_VERSION,
                metadata={"phase": "10.21"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("relationships", "personal", "high-sensitivity"),
            metadata={"phase": "10.21"},
        ),
    )


__all__ = [
    "RELATIONSHIPS_DOMAIN_ID",
    "RELATIONSHIPS_DOMAIN_VERSION",
    "RELATIONSHIPS_MANIFEST_ID",
    "RELATIONSHIPS_OPERATION_IDS",
    "RELATIONSHIPS_PERMISSION_IDS",
    "RELATIONSHIPS_PROFILE_NAME",
    "RELATIONSHIPS_RESOURCE_IDS",
    "RELATIONSHIPS_RULE_IDS",
    "RELATIONSHIPS_WORKFLOW_IDS",
    "build_relationships_domain_definition",
]
