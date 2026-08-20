"""Phase 10.24 — Reflection Domain Definition.

Builds the immutable ``domain:reflection`` definition deterministically
using the shared ``DomainDefinition`` contract.  No global registration
happens at import time.
"""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.reflection.catalog import (
    CANONICAL_REFLECTION_OPERATION_IDS,
    CANONICAL_REFLECTION_RESOURCE_IDS,
    CANONICAL_REFLECTION_RULE_IDS,
    CANONICAL_REFLECTION_WORKFLOW_IDS,
)

REFLECTION_DOMAIN_ID = "domain:reflection"
REFLECTION_DOMAIN_VERSION = "1.0.0"
REFLECTION_MANIFEST_ID = "manifest:reflection:1.0.0"
REFLECTION_PROFILE_NAME = "ReflectionProfile"

REFLECTION_RESOURCE_IDS: tuple[str, ...] = CANONICAL_REFLECTION_RESOURCE_IDS
REFLECTION_RULE_IDS: tuple[str, ...] = CANONICAL_REFLECTION_RULE_IDS
REFLECTION_OPERATION_IDS: tuple[str, ...] = CANONICAL_REFLECTION_OPERATION_IDS
REFLECTION_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_REFLECTION_WORKFLOW_IDS

REFLECTION_PERMISSION_IDS: tuple[str, ...] = (
    "domain-permission:reflection:1.0.0",
)


def build_reflection_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:reflection`` definition deterministically."""
    return DomainDefinition(
        id=REFLECTION_DOMAIN_ID,
        name="reflection",
        display_name="Reflection",
        version=REFLECTION_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Reflection domain for complex reflection, hypothesis exploration, "
            "organization of ideas, longitudinal comparison, decision review, "
            "and preservation of genuine ambivalence without forcing a single "
            "conclusion.  Reflection preserves distinct epistemic levels "
            "(observation, interpretation, belief, hypothesis, uncertainty, "
            "open question), keeps source grounding explicit, and never "
            "presents a psychological hypothesis as a diagnosis.  It never "
            "classifies identity, never adopts a personal decision, never "
            "writes semantic memory without confirmation, and never performs "
            "an external write: prepared content is preparation only."
        ),
        manifest_id=REFLECTION_MANIFEST_ID,
        reasoning_profile=REFLECTION_PROFILE_NAME,
        resources=REFLECTION_RESOURCE_IDS,
        rules=REFLECTION_RULE_IDS,
        operations=REFLECTION_OPERATION_IDS,
        workflows=REFLECTION_WORKFLOW_IDS,
        permissions=REFLECTION_PERMISSION_IDS,
        validators=(),
        presentation_policy={
            "detail_level": "detailed",
            "include_uncertainty": True,
            "include_provenance": True,
            "include_alternatives": True,
            "allow_speculation": False,
            "require_disclaimers": True,
        },
        # General remains the fallback dependency; Relationships/Health/
        # University participate only through normal cross-domain resolution
        # and never widen Reflection permissions.
        dependencies=(),
        optional_dependencies=(),
        conflicts=(),
        capabilities=(
            DomainCapability(
                name="reflection_analysis",
                kind="reasoning",
                provided_by=REFLECTION_DOMAIN_ID,
                version=REFLECTION_DOMAIN_VERSION,
                metadata={"phase": "10.24"},
            ),
            DomainCapability(
                name="reflection_hypothesis_exploration",
                kind="reasoning",
                provided_by=REFLECTION_DOMAIN_ID,
                version=REFLECTION_DOMAIN_VERSION,
                metadata={"phase": "10.24"},
            ),
            DomainCapability(
                name="reflection_longitudinal_comparison",
                kind="analysis",
                provided_by=REFLECTION_DOMAIN_ID,
                version=REFLECTION_DOMAIN_VERSION,
                metadata={"phase": "10.24"},
            ),
            DomainCapability(
                name="reflection_interest_mapping",
                kind="reasoning",
                provided_by=REFLECTION_DOMAIN_ID,
                version=REFLECTION_DOMAIN_VERSION,
                metadata={"phase": "10.24"},
            ),
            DomainCapability(
                name="reflection_decision_review",
                kind="safety",
                provided_by=REFLECTION_DOMAIN_ID,
                version=REFLECTION_DOMAIN_VERSION,
                metadata={"phase": "10.24"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("reflection", "personal", "hypothesis", "ambivalence"),
            metadata={"phase": "10.24"},
        ),
    )


__all__ = [
    "REFLECTION_DOMAIN_ID",
    "REFLECTION_DOMAIN_VERSION",
    "REFLECTION_MANIFEST_ID",
    "REFLECTION_OPERATION_IDS",
    "REFLECTION_PERMISSION_IDS",
    "REFLECTION_PROFILE_NAME",
    "REFLECTION_RESOURCE_IDS",
    "REFLECTION_RULE_IDS",
    "REFLECTION_WORKFLOW_IDS",
    "build_reflection_domain_definition",
]