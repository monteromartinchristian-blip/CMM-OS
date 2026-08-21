"""Phase 10.25 — Concerns Domain Definition.

Builds the immutable ``domain:concerns`` definition deterministically using
the shared ``DomainDefinition`` contract.  No global registration happens at
import time.
"""

from __future__ import annotations

from cmm.domains.concerns.catalog import (
    CANONICAL_CONCERNS_OPERATION_IDS,
    CANONICAL_CONCERNS_RESOURCE_IDS,
    CANONICAL_CONCERNS_RULE_IDS,
    CANONICAL_CONCERNS_WORKFLOW_IDS,
)
from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind

CONCERNS_DOMAIN_ID = "domain:concerns"
CONCERNS_DOMAIN_VERSION = "1.0.0"
CONCERNS_MANIFEST_ID = "manifest:concerns:1.0.0"
CONCERNS_PROFILE_NAME = "ConcernSupportProfile"

CONCERNS_RESOURCE_IDS: tuple[str, ...] = CANONICAL_CONCERNS_RESOURCE_IDS
CONCERNS_RULE_IDS: tuple[str, ...] = CANONICAL_CONCERNS_RULE_IDS
CONCERNS_OPERATION_IDS: tuple[str, ...] = CANONICAL_CONCERNS_OPERATION_IDS
CONCERNS_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_CONCERNS_WORKFLOW_IDS

CONCERNS_PERMISSION_IDS: tuple[str, ...] = (
    "domain-permission:concerns:1.0.0",
)


def build_concerns_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:concerns`` definition deterministically."""
    return DomainDefinition(
        id=CONCERNS_DOMAIN_ID,
        name="concerns",
        display_name="Concerns",
        version=CONCERNS_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Concerns domain for supporting the user through problems, "
            "worries, fears, uncertainty, recurring concerns, difficult "
            "decisions, requests for reassurance or perspective, and "
            "open-ended talk-it-through conversations.  Concerns understands "
            "the situation and its lived significance first, resolves or "
            "cautiously infers the current conversational support need, keeps "
            "facts, interpretations, hypotheses, fears, scenarios and "
            "uncertainty distinct when useful, offers evidence-calibrated "
            "reassurance when justified, acknowledges material concerns when "
            "justified, avoids catastrophic escalation and false reassurance, "
            "never pathologizes repetition, never forces action or closure, "
            "never adopts a personal decision, never writes semantic memory, "
            "and never performs an external action: prepared content is "
            "preparation only."
        ),
        manifest_id=CONCERNS_MANIFEST_ID,
        reasoning_profile=CONCERNS_PROFILE_NAME,
        resources=CONCERNS_RESOURCE_IDS,
        rules=CONCERNS_RULE_IDS,
        operations=CONCERNS_OPERATION_IDS,
        workflows=CONCERNS_WORKFLOW_IDS,
        permissions=CONCERNS_PERMISSION_IDS,
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
        # University/Reflection participate only through normal cross-domain
        # resolution and never widen Concerns permissions.
        dependencies=(),
        optional_dependencies=(),
        conflicts=(),
        capabilities=(
            DomainCapability(
                name="concern_understanding",
                kind="reasoning",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
            DomainCapability(
                name="support_need_resolution",
                kind="reasoning",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
            DomainCapability(
                name="reality_check",
                kind="analysis",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
            DomainCapability(
                name="evidence_calibrated_reassurance",
                kind="reasoning",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
            DomainCapability(
                name="uncertainty_support",
                kind="reasoning",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
            DomainCapability(
                name="risk_calibration",
                kind="safety",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
            DomainCapability(
                name="problem_solving",
                kind="reasoning",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
            DomainCapability(
                name="decision_support",
                kind="reasoning",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
            DomainCapability(
                name="recurring_concern_review",
                kind="analysis",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
            DomainCapability(
                name="professional_discussion_preparation",
                kind="preparation",
                provided_by=CONCERNS_DOMAIN_ID,
                version=CONCERNS_DOMAIN_VERSION,
                metadata={"phase": "10.25"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("concerns", "personal", "support", "reassurance"),
            metadata={"phase": "10.25"},
        ),
    )


__all__ = [
    "CONCERNS_DOMAIN_ID",
    "CONCERNS_DOMAIN_VERSION",
    "CONCERNS_MANIFEST_ID",
    "CONCERNS_OPERATION_IDS",
    "CONCERNS_PERMISSION_IDS",
    "CONCERNS_PROFILE_NAME",
    "CONCERNS_RESOURCE_IDS",
    "CONCERNS_RULE_IDS",
    "CONCERNS_WORKFLOW_IDS",
    "build_concerns_domain_definition",
]
