"""Phase 10.26 — Languages Domain Definition.

Builds the immutable ``domain:languages`` definition deterministically using
the shared ``DomainDefinition`` contract.  No global registration happens at
import time.
"""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_OPERATION_IDS,
    CANONICAL_LANGUAGES_RESOURCE_IDS,
    CANONICAL_LANGUAGES_RULE_IDS,
    CANONICAL_LANGUAGES_WORKFLOW_IDS,
)

LANGUAGES_DOMAIN_ID = "domain:languages"
LANGUAGES_DOMAIN_VERSION = "1.0.0"
LANGUAGES_MANIFEST_ID = "manifest:languages:1.0.0"
LANGUAGES_PROFILE_NAME = "LanguageLearningProfile"

LANGUAGES_RESOURCE_IDS: tuple[str, ...] = CANONICAL_LANGUAGES_RESOURCE_IDS
LANGUAGES_RULE_IDS: tuple[str, ...] = CANONICAL_LANGUAGES_RULE_IDS
LANGUAGES_OPERATION_IDS: tuple[str, ...] = CANONICAL_LANGUAGES_OPERATION_IDS
LANGUAGES_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_LANGUAGES_WORKFLOW_IDS

LANGUAGES_PERMISSION_IDS: tuple[str, ...] = (
    "domain-permission:languages:1.0.0",
)


def build_languages_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:languages`` definition deterministically."""
    return DomainDefinition(
        id=LANGUAGES_DOMAIN_ID,
        name="languages",
        display_name="Idiomas",
        version=LANGUAGES_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Languages domain for language learning, communicative practice, "
            "proficiency assessment, writing and speaking feedback, adaptive "
            "teaching, error remediation, vocabulary spaced review, and "
            "certification preparation. Preserves epistemic separation between "
            "certified proficiency, estimated proficiency, and observed "
            "performance; enforces skill separation, language variety validity, "
            "and framework non-identity; respects consent-gated longitudinal "
            "memory proposals, calendar proposal boundaries, and shared "
            "read-only official source verification."
        ),
        manifest_id=LANGUAGES_MANIFEST_ID,
        reasoning_profile=LANGUAGES_PROFILE_NAME,
        resources=LANGUAGES_RESOURCE_IDS,
        rules=LANGUAGES_RULE_IDS,
        operations=LANGUAGES_OPERATION_IDS,
        workflows=LANGUAGES_WORKFLOW_IDS,
        permissions=LANGUAGES_PERMISSION_IDS,
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
                name="language_onboarding",
                kind="reasoning",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
            DomainCapability(
                name="proficiency_assessment",
                kind="analysis",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
            DomainCapability(
                name="adaptive_language_teaching",
                kind="reasoning",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
            DomainCapability(
                name="language_practice",
                kind="preparation",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
            DomainCapability(
                name="writing_review",
                kind="analysis",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
            DomainCapability(
                name="speaking_review",
                kind="analysis",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
            DomainCapability(
                name="error_remediation",
                kind="reasoning",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
            DomainCapability(
                name="spaced_review",
                kind="planning",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
            DomainCapability(
                name="progression_review",
                kind="analysis",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
            DomainCapability(
                name="certification_preparation",
                kind="preparation",
                provided_by=LANGUAGES_DOMAIN_ID,
                version=LANGUAGES_DOMAIN_VERSION,
                metadata={"phase": "10.26"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("languages", "personal", "learning", "pedagogy", "idiomas"),
            metadata={"phase": "10.26"},
        ),
    )


__all__ = [
    "LANGUAGES_DOMAIN_ID",
    "LANGUAGES_DOMAIN_VERSION",
    "LANGUAGES_MANIFEST_ID",
    "LANGUAGES_OPERATION_IDS",
    "LANGUAGES_PERMISSION_IDS",
    "LANGUAGES_PROFILE_NAME",
    "LANGUAGES_RESOURCE_IDS",
    "LANGUAGES_RULE_IDS",
    "LANGUAGES_WORKFLOW_IDS",
    "build_languages_domain_definition",
]
