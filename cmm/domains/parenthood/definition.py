"""Phase 10.27 — Parenthood Domain Definition.

Builds the immutable ``domain:parenthood`` definition deterministically using
the shared ``DomainDefinition`` contract. No global registration happens at
import time.
"""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_OPERATION_IDS,
    CANONICAL_PARENTHOOD_RESOURCE_IDS,
    CANONICAL_PARENTHOOD_RULE_IDS,
    CANONICAL_PARENTHOOD_WORKFLOW_IDS,
)

PARENTHOOD_DOMAIN_ID = "domain:parenthood"
PARENTHOOD_DOMAIN_VERSION = "1.0.0"
PARENTHOOD_MANIFEST_ID = "manifest:parenthood:1.0.0"
PARENTHOOD_PROFILE_NAME = "ParenthoodProfile"

PARENTHOOD_RESOURCE_IDS: tuple[str, ...] = CANONICAL_PARENTHOOD_RESOURCE_IDS
PARENTHOOD_RULE_IDS: tuple[str, ...] = CANONICAL_PARENTHOOD_RULE_IDS
PARENTHOOD_OPERATION_IDS: tuple[str, ...] = CANONICAL_PARENTHOOD_OPERATION_IDS
PARENTHOOD_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_PARENTHOOD_WORKFLOW_IDS

PARENTHOOD_PERMISSION_IDS: tuple[str, ...] = ("domain-permission:parenthood:1.0.0",)


def build_parenthood_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:parenthood`` definition deterministically."""
    return DomainDefinition(
        id=PARENTHOOD_DOMAIN_ID,
        name="parenthood",
        display_name="Paternidad",
        version=PARENTHOOD_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Parenthood domain supporting both the path to becoming a parent "
            "(parenthood.journey) and the long-term parenting of each child "
            "(parenthood.child:<child_id>) in isolated workspaces. Preserves "
            "epistemic boundaries between proposals, preferences, and adopted "
            "decisions; ensures strict sibling identity/history/health/memory "
            "isolation; enforces selective and authorized journey-to-child "
            "context transfer; protects minor privacy with fail-closed defaults; "
            "and maintains normal developmental variations as non-pathological."
        ),
        manifest_id=PARENTHOOD_MANIFEST_ID,
        reasoning_profile=PARENTHOOD_PROFILE_NAME,
        resources=PARENTHOOD_RESOURCE_IDS,
        rules=PARENTHOOD_RULE_IDS,
        operations=PARENTHOOD_OPERATION_IDS,
        workflows=PARENTHOOD_WORKFLOW_IDS,
        permissions=PARENTHOOD_PERMISSION_IDS,
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
                name="parenthood_journey_planning",
                kind="planning",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
            DomainCapability(
                name="parenthood_pathway_comparison",
                kind="analysis",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
            DomainCapability(
                name="parenthood_requirements_review",
                kind="analysis",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
            DomainCapability(
                name="parenthood_financial_scenario_review",
                kind="analysis",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
            DomainCapability(
                name="parenthood_child_workspace",
                kind="reasoning",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
            DomainCapability(
                name="parenthood_developmental_review",
                kind="analysis",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
            DomainCapability(
                name="parenthood_parental_decision_support",
                kind="reasoning",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
            DomainCapability(
                name="parenthood_family_context_review",
                kind="analysis",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
            DomainCapability(
                name="parenthood_journey_to_child_transition",
                kind="reasoning",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
            DomainCapability(
                name="parenthood_multi_child_isolation",
                kind="reasoning",
                provided_by=PARENTHOOD_DOMAIN_ID,
                version=PARENTHOOD_DOMAIN_VERSION,
                metadata={"phase": "10.27"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("parenthood", "paternidad", "family", "child", "parenting"),
            metadata={"phase": "10.27"},
        ),
    )


__all__ = [
    "PARENTHOOD_DOMAIN_ID",
    "PARENTHOOD_DOMAIN_VERSION",
    "PARENTHOOD_MANIFEST_ID",
    "PARENTHOOD_OPERATION_IDS",
    "PARENTHOOD_PERMISSION_IDS",
    "PARENTHOOD_PROFILE_NAME",
    "PARENTHOOD_RESOURCE_IDS",
    "PARENTHOOD_RULE_IDS",
    "PARENTHOOD_WORKFLOW_IDS",
    "build_parenthood_domain_definition",
]
