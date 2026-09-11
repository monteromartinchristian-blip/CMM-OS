"""Phase 10.50 – ``privacy_policy`` in ``DomainDefinition`` and the canonical Pack path."""

from __future__ import annotations

from typing import Any

import pytest

from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.privacy import PrivacyMetadata, PrivacyPolicy, ProcessingLocation
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainPackKind
from cmm.domains.errors import DomainContractValidationError, DomainError
from cmm.domains.identifiers import DomainId
from cmm.domains.manifest import DomainManifest
from cmm.domains.pack import ParsedDomainPack
from cmm.domains.privacy_policy_contracts import DomainPrivacyPolicy


def _privacy(**overrides: object) -> PrivacyMetadata:
    data: dict[str, object] = {
        "policy": PrivacyPolicy.REMOTE_ALLOWED,
        "sensitivity": SensitivityLevel.INTERNAL,
        "allowed_processing_locations": (
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        "allow_remote": True,
        "allow_cache": True,
    }
    data.update(overrides)
    return PrivacyMetadata(**data)  # type: ignore[arg-type]


def _policy(
    domain_slug: str = "university", **overrides: object
) -> DomainPrivacyPolicy:
    data: dict[str, object] = {
        "schema_version": "1",
        "domain_id": DomainId(slug=domain_slug),
        "default_privacy": _privacy(),
    }
    data.update(overrides)
    return DomainPrivacyPolicy(**data)  # type: ignore[arg-type]


def _definition(**overrides: object) -> DomainDefinition:
    data: dict[str, object] = {
        "id": "domain:university",
        "name": "university",
        "display_name": "University",
        "version": "1.0.0",
        "kind": DomainKind.PERSONAL,
        "description": "university domain",
        "manifest_id": "manifest:university:1.0.0",
    }
    data.update(overrides)
    return DomainDefinition(**data)  # type: ignore[arg-type]


def _manifest_for(definition: DomainDefinition) -> DomainManifest:
    return DomainManifest(
        id=definition.manifest_id,
        domain_id=definition.id,
        schema_version="1",
        package_version=definition.version,
        pack_kind=DomainPackKind.INTERNAL,
    )


# ── DomainDefinition integration ──────────────────────────────────────────────


def test_domain_definition_privacy_policy_defaults_to_none() -> None:
    assert _definition().privacy_policy is None


def test_domain_definition_accepts_canonical_privacy_policy() -> None:
    policy = _policy()
    definition = _definition(privacy_policy=policy)

    assert definition.privacy_policy is policy
    assert definition.privacy_policy.domain_id == definition.id


def test_domain_definition_serializes_privacy_policy_deterministically() -> None:
    definition = _definition(privacy_policy=_policy())

    first = definition.to_dict()
    second = definition.to_dict()

    assert first == second
    assert first["privacy_policy"] == _policy().to_dict()


def test_domain_definition_round_trip_preserves_privacy_policy() -> None:
    definition = _definition(privacy_policy=_policy(require_approval_for_remote=True))

    payload = definition.to_dict()
    restored = DomainDefinition.from_dict(payload)

    assert restored.privacy_policy == definition.privacy_policy
    assert restored.to_dict() == payload


def test_domain_definition_rejects_invalid_privacy_policy_payload() -> None:
    payload = _definition().to_dict()
    payload["privacy_policy"] = "not-a-policy"

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_domain_definition_rejects_privacy_policy_domain_mismatch() -> None:
    payload = _definition().to_dict()
    payload["privacy_policy"] = _policy("relationships").to_dict()

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_domain_definition_rejects_malformed_nested_privacy_metadata() -> None:
    payload = _definition().to_dict()
    malformed = _policy().to_dict()
    malformed["default_privacy"]["policy"] = "sensitive"
    payload["privacy_policy"] = malformed

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_domain_definition_rejects_unknown_privacy_policy_fields() -> None:
    payload = _definition().to_dict()
    malformed = _policy().to_dict()
    malformed["allow_cross_domain"] = True
    payload["privacy_policy"] = malformed

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


@pytest.mark.parametrize("item", (42, "privacy-policy:university", [1]))
def test_domain_definition_rejects_non_policy_values(item: object) -> None:
    with pytest.raises(DomainContractValidationError):
        _definition(privacy_policy=item)


def test_legacy_domain_definition_without_privacy_policy_round_trips() -> None:
    payload = _definition().to_dict()
    del payload["privacy_policy"]

    restored = DomainDefinition.from_dict(payload)

    assert restored.privacy_policy is None
    assert restored.to_dict() == _definition().to_dict()


# ── Declarative Domain Pack path ──────────────────────────────────────────────


def _declarative_payload() -> dict[str, Any]:
    return {
        "id": "university",
        "version": "1.0.0",
        "name": "university",
        "display_name": "University",
        "description": "university domain",
        "author": "tester",
        "license": "MIT",
        "privacy_policy": _policy().to_dict(),
    }


def test_canonical_declarative_pack_parses_domain_privacy_policy() -> None:
    parsed = ParsedDomainPack.from_declarative_dict(_declarative_payload())

    assert parsed.definition.privacy_policy == _policy()


def test_declarative_pack_without_privacy_policy_stays_backward_compatible() -> None:
    payload = _declarative_payload()
    del payload["privacy_policy"]

    parsed = ParsedDomainPack.from_declarative_dict(payload)

    assert parsed.definition.privacy_policy is None


@pytest.mark.parametrize("container", ("not-a-mapping", 42, ["not-a-mapping"]))
def test_declarative_pack_rejects_invalid_privacy_policy_container(
    container: object,
) -> None:
    payload = _declarative_payload()
    payload["privacy_policy"] = container

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_rejects_privacy_policy_domain_mismatch() -> None:
    payload = _declarative_payload()
    payload["privacy_policy"] = _policy("relationships").to_dict()

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_rejects_unsupported_privacy_schema_version() -> None:
    payload = _declarative_payload()
    malformed = _policy().to_dict()
    malformed["schema_version"] = "2"
    payload["privacy_policy"] = malformed

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_rejects_unknown_privacy_policy_fields() -> None:
    payload = _declarative_payload()
    malformed = _policy().to_dict()
    malformed["allow_cross_domain"] = True
    payload["privacy_policy"] = malformed

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_round_trips_privacy_policy_through_parsed_dict() -> None:
    parsed = ParsedDomainPack.from_declarative_dict(_declarative_payload())

    restored = ParsedDomainPack.from_dict(parsed.to_dict())

    assert restored.definition.privacy_policy == parsed.definition.privacy_policy
    assert restored.to_dict() == parsed.to_dict()


def test_definition_round_trips_policy_benchmarks_quality_schema_and_privacy() -> None:
    definition = _definition(privacy_policy=_policy())

    payload = definition.to_dict()
    restored = DomainDefinition.from_dict(payload)

    assert restored.privacy_policy == definition.privacy_policy
    assert restored.knowledge_package_schema == definition.knowledge_package_schema
    assert restored.to_dict() == payload
