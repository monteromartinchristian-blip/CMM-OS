"""Tests for Phase 10.26 Languages Domain Definition."""

from __future__ import annotations

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_OPERATION_IDS,
    CANONICAL_LANGUAGES_RESOURCE_IDS,
    CANONICAL_LANGUAGES_RULE_IDS,
    CANONICAL_LANGUAGES_WORKFLOW_IDS,
)
from cmm.domains.languages.definition import (
    LANGUAGES_DOMAIN_ID,
    LANGUAGES_DOMAIN_VERSION,
    LANGUAGES_MANIFEST_ID,
    LANGUAGES_PERMISSION_IDS,
    LANGUAGES_PROFILE_NAME,
    build_languages_domain_definition,
)


def test_build_languages_domain_definition_contract() -> None:
    """Verify the immutable domain definition structure."""
    definition = build_languages_domain_definition()

    assert isinstance(definition, DomainDefinition)
    assert str(definition.id) == "domain:languages"
    assert definition.name == "languages"
    assert definition.display_name == "Idiomas"
    assert definition.version == "1.0.0"
    assert definition.kind is DomainKind.PERSONAL
    assert definition.reasoning_profile == "LanguageLearningProfile"
    assert tuple(definition.resources) == CANONICAL_LANGUAGES_RESOURCE_IDS
    assert tuple(definition.rules) == CANONICAL_LANGUAGES_RULE_IDS
    assert tuple(definition.operations) == CANONICAL_LANGUAGES_OPERATION_IDS
    assert tuple(definition.workflows) == CANONICAL_LANGUAGES_WORKFLOW_IDS
    assert definition.metadata.metadata["phase"] == "10.26"
    assert definition.permissions == LANGUAGES_PERMISSION_IDS
    assert build_languages_domain_definition().to_dict() == definition.to_dict()


def test_languages_domain_capabilities() -> None:
    """Verify exact 10 capabilities declared in definition."""
    definition = build_languages_domain_definition()
    cap_names = tuple(c.name for c in definition.capabilities)
    expected_capabilities = (
        "language_onboarding",
        "proficiency_assessment",
        "adaptive_language_teaching",
        "language_practice",
        "writing_review",
        "speaking_review",
        "error_remediation",
        "spaced_review",
        "progression_review",
        "certification_preparation",
    )
    assert cap_names == expected_capabilities
    for cap in definition.capabilities:
        assert cap.provided_by == "domain:languages"
        assert cap.version == "1.0.0"
        assert cap.metadata["phase"] == "10.26"


def test_languages_domain_constants() -> None:
    """Verify definition module constants."""
    assert LANGUAGES_DOMAIN_ID == "domain:languages"
    assert LANGUAGES_DOMAIN_VERSION == "1.0.0"
    assert LANGUAGES_MANIFEST_ID == "manifest:languages:1.0.0"
    assert LANGUAGES_PROFILE_NAME == "LanguageLearningProfile"
    assert LANGUAGES_PERMISSION_IDS == ("domain-permission:languages:1.0.0",)
