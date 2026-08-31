"""Phase 10.23 — Opposition Domain Definition.

Builds the immutable ``domain:oppositions`` definition deterministically
using the shared ``DomainDefinition`` contract.  No global registration
happens at import time.
"""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.oppositions.catalog import (
    CANONICAL_OPPOSITION_OPERATION_IDS,
    CANONICAL_OPPOSITION_RESOURCE_IDS,
    CANONICAL_OPPOSITION_RULE_IDS,
    CANONICAL_OPPOSITION_WORKFLOW_IDS,
)

OPPOSITIONS_DOMAIN_ID = "domain:oppositions"
OPPOSITIONS_DOMAIN_VERSION = "1.0.0"
OPPOSITIONS_MANIFEST_ID = "manifest:oppositions:1.0.0"
OPPOSITIONS_PROFILE_NAME = "OppositionProfile"

OPPOSITIONS_RESOURCE_IDS: tuple[str, ...] = CANONICAL_OPPOSITION_RESOURCE_IDS
OPPOSITIONS_RULE_IDS: tuple[str, ...] = CANONICAL_OPPOSITION_RULE_IDS
OPPOSITIONS_OPERATION_IDS: tuple[str, ...] = CANONICAL_OPPOSITION_OPERATION_IDS
OPPOSITIONS_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_OPPOSITION_WORKFLOW_IDS

OPPOSITIONS_PERMISSION_IDS: tuple[str, ...] = ("domain-permission:oppositions:1.0.0",)


def build_oppositions_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:oppositions`` definition deterministically."""
    return DomainDefinition(
        id=OPPOSITIONS_DOMAIN_ID,
        name="oppositions",
        display_name="Oppositions",
        version=OPPOSITIONS_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Opposition domain for structured reasoning and preparation about "
            "public competitive examinations/oppositions: public bodies and "
            "alternative routes, official calls, syllabi, topics and blocks, "
            "exam milestones, deadlines and requirements, merits, study plans, "
            "study progress, revision, mock exams, scores, workload and "
            "feasibility, risks, alternative routes, and strategy review.  "
            "Opposition preserves source authority by attribute and scope, "
            "provenance, temporality, explicit uncertainty, and user control.  "
            "It never registers, submits an application, pays a fee, signs a "
            "filing, modifies official public-body records, abandons or "
            "switches the target automatically, or adopts a strategy without an "
            "explicit user decision.  External official verification is "
            "read-only and OFFICIAL_ONLY."
        ),
        manifest_id=OPPOSITIONS_MANIFEST_ID,
        reasoning_profile=OPPOSITIONS_PROFILE_NAME,
        resources=OPPOSITIONS_RESOURCE_IDS,
        rules=OPPOSITIONS_RULE_IDS,
        operations=OPPOSITIONS_OPERATION_IDS,
        workflows=OPPOSITIONS_WORKFLOW_IDS,
        permissions=OPPOSITIONS_PERMISSION_IDS,
        validators=(),
        presentation_policy={
            "detail_level": "detailed",
            "include_uncertainty": True,
            "include_provenance": True,
            "include_alternatives": True,
            "allow_speculation": False,
            "require_disclaimers": True,
        },
        # General remains the fallback dependency; Health/University
        # participate only through normal cross-domain resolution and never
        # widen Opposition permissions.
        dependencies=(),
        optional_dependencies=(),
        conflicts=(),
        capabilities=(
            DomainCapability(
                name="opposition_planning",
                kind="planning",
                provided_by=OPPOSITIONS_DOMAIN_ID,
                version=OPPOSITIONS_DOMAIN_VERSION,
                metadata={"phase": "10.23"},
            ),
            DomainCapability(
                name="opposition_analysis",
                kind="analysis",
                provided_by=OPPOSITIONS_DOMAIN_ID,
                version=OPPOSITIONS_DOMAIN_VERSION,
                metadata={"phase": "10.23"},
            ),
            DomainCapability(
                name="opposition_official_verification",
                kind="reasoning",
                provided_by=OPPOSITIONS_DOMAIN_ID,
                version=OPPOSITIONS_DOMAIN_VERSION,
                metadata={"phase": "10.23"},
            ),
            DomainCapability(
                name="opposition_source_authority",
                kind="reasoning",
                provided_by=OPPOSITIONS_DOMAIN_ID,
                version=OPPOSITIONS_DOMAIN_VERSION,
                metadata={"phase": "10.23"},
            ),
            DomainCapability(
                name="opposition_decision_support",
                kind="safety",
                provided_by=OPPOSITIONS_DOMAIN_ID,
                version=OPPOSITIONS_DOMAIN_VERSION,
                metadata={"phase": "10.23"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("oppositions", "public-body", "planning", "personal"),
            metadata={"phase": "10.23"},
        ),
    )


__all__ = [
    "OPPOSITIONS_DOMAIN_ID",
    "OPPOSITIONS_DOMAIN_VERSION",
    "OPPOSITIONS_MANIFEST_ID",
    "OPPOSITIONS_OPERATION_IDS",
    "OPPOSITIONS_PERMISSION_IDS",
    "OPPOSITIONS_PROFILE_NAME",
    "OPPOSITIONS_RESOURCE_IDS",
    "OPPOSITIONS_RULE_IDS",
    "OPPOSITIONS_WORKFLOW_IDS",
    "build_oppositions_domain_definition",
]
