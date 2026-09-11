"""Phase 10.50 – first-party Domain privacy declarations."""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.privacy import PrivacyMetadata, PrivacyPolicy, ProcessingLocation
from cmm.domains.concerns.definition import build_concerns_domain_definition
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.languages.definition import build_languages_domain_definition
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.parenthood.definition import build_parenthood_domain_definition
from cmm.domains.project.definition import build_project_domain_definition
from cmm.domains.reflection.definition import build_reflection_domain_definition
from cmm.domains.relationships.definition import (
    build_relationships_domain_definition,
)
from cmm.domains.sport.definition import build_sport_domain_definition
from cmm.domains.university.definition import build_university_domain_definition

# Approved first-party inventory: slug -> definition builder.
FIRST_PARTY_BUILDERS = {
    "general": build_general_domain_definition,
    "health": build_health_domain_definition,
    "relationships": build_relationships_domain_definition,
    "university": build_university_domain_definition,
    "oppositions": build_oppositions_domain_definition,
    "reflection": build_reflection_domain_definition,
    "concerns": build_concerns_domain_definition,
    "languages": build_languages_domain_definition,
    "parenthood": build_parenthood_domain_definition,
    "sport": build_sport_domain_definition,
    "life_plan": build_life_plan_domain_definition,
    "project": build_project_domain_definition,
}

SENSITIVE_LOCAL_ONLY = (
    "health",
    "relationships",
    "reflection",
    "concerns",
    "parenthood",
    "sport",
    "life_plan",
)

REMOTE_ALLOWED = ("university", "oppositions", "languages")

_LOCAL_ONLY_LOCATIONS = (ProcessingLocation.LOCAL,)
_LOCAL_REMOTE_LOCATIONS = (
    ProcessingLocation.LOCAL,
    ProcessingLocation.REMOTE,
)


def _definitions() -> dict[str, object]:
    return {slug: builder() for slug, builder in FIRST_PARTY_BUILDERS.items()}


def test_first_party_inventory_is_exactly_twelve() -> None:
    definitions = _definitions()

    assert len(definitions) == 12
    assert set(definitions) == {
        "general",
        "health",
        "relationships",
        "university",
        "oppositions",
        "reflection",
        "concerns",
        "languages",
        "parenthood",
        "sport",
        "life_plan",
        "project",
    }


def test_general_declares_no_domain_privacy_default() -> None:
    definition = build_general_domain_definition()

    assert definition.privacy_policy is None


def test_exactly_eleven_first_party_domains_declare_a_privacy_policy() -> None:
    definitions = _definitions()

    declared = {
        slug: definition.privacy_policy
        for slug, definition in definitions.items()
        if definition.privacy_policy is not None
    }

    assert len(declared) == 11
    assert "general" not in declared


def test_every_declared_policy_is_bound_to_its_own_domain() -> None:
    for slug, builder in FIRST_PARTY_BUILDERS.items():
        definition = builder()
        if definition.privacy_policy is None:
            assert slug == "general"
            continue
        assert definition.privacy_policy.domain_id == definition.id


def test_sensitive_local_only_group_posture() -> None:
    for slug in SENSITIVE_LOCAL_ONLY:
        definition = FIRST_PARTY_BUILDERS[slug]()
        policy = definition.privacy_policy
        assert policy is not None, slug

        privacy = policy.default_privacy
        assert privacy.policy is PrivacyPolicy.LOCAL_ONLY, slug
        assert privacy.sensitivity is SensitivityLevel.SENSITIVE, slug
        assert privacy.allowed_processing_locations == _LOCAL_ONLY_LOCATIONS, slug
        assert privacy.allow_remote is False, slug
        assert privacy.allow_premium is False, slug
        assert privacy.allow_cache is True, slug
        assert privacy.allow_export is False, slug
        assert policy.require_approval_for_remote is True, slug
        assert policy.schema_version == "1", slug


def test_remote_allowed_group_posture() -> None:
    for slug in REMOTE_ALLOWED:
        definition = FIRST_PARTY_BUILDERS[slug]()
        policy = definition.privacy_policy
        assert policy is not None, slug

        privacy = policy.default_privacy
        assert privacy.policy is PrivacyPolicy.REMOTE_ALLOWED, slug
        assert privacy.sensitivity is SensitivityLevel.INTERNAL, slug
        assert privacy.allowed_processing_locations == _LOCAL_REMOTE_LOCATIONS, slug
        assert privacy.allow_remote is True, slug
        assert privacy.allow_premium is False, slug
        assert privacy.allow_cache is True, slug
        assert privacy.allow_export is False, slug
        assert policy.require_approval_for_remote is False, slug
        assert policy.schema_version == "1", slug


def test_project_posture() -> None:
    definition = build_project_domain_definition()
    policy = definition.privacy_policy
    assert policy is not None

    privacy = policy.default_privacy
    assert privacy.policy is PrivacyPolicy.LOCAL_PREFERRED
    assert privacy.sensitivity is SensitivityLevel.INTERNAL
    assert privacy.allowed_processing_locations == _LOCAL_REMOTE_LOCATIONS
    assert privacy.allow_remote is True
    assert privacy.allow_premium is False
    assert privacy.allow_cache is True
    assert privacy.allow_export is False
    assert policy.require_approval_for_remote is True


def test_declared_policies_never_grant_export_or_premium() -> None:
    for slug, builder in FIRST_PARTY_BUILDERS.items():
        policy = builder().privacy_policy
        if policy is None:
            continue
        assert policy.default_privacy.allow_export is False, slug
        assert policy.default_privacy.allow_premium is False, slug


def test_declared_policies_are_provider_neutral() -> None:
    for slug, builder in FIRST_PARTY_BUILDERS.items():
        policy = builder().privacy_policy
        if policy is None:
            continue
        privacy = policy.default_privacy
        assert privacy.allowed_providers is None, slug
        assert privacy.prohibited_providers == (), slug
        assert privacy.permissions == (), slug
        assert privacy.permissions_denied is False, slug


def test_declared_policies_are_deterministic_and_immutable() -> None:
    for slug, builder in FIRST_PARTY_BUILDERS.items():
        first = builder().privacy_policy
        second = builder().privacy_policy
        if first is None:
            assert second is None, slug
            continue
        assert first == second, slug
        assert first.to_dict() == second.to_dict(), slug
        assert isinstance(first.default_privacy, PrivacyMetadata), slug


def test_declared_policies_never_require_redaction_or_approval_locally() -> None:
    for slug, builder in FIRST_PARTY_BUILDERS.items():
        policy = builder().privacy_policy
        if policy is None:
            continue
        assert policy.default_privacy.requires_redaction is False, slug
        assert policy.default_privacy.requires_approval is False, slug
