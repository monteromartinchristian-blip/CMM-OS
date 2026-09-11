"""Phase 10.50 – immutable ``DomainPrivacyPolicy`` contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.privacy import (
    PrivacyMetadata,
    PrivacyPolicy,
    ProcessingLocation,
)
from cmm.domains.errors import (
    DomainError,
    DomainPrivacyPolicyContractError,
    DomainPrivacyPolicySerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.privacy_policy_contracts import DomainPrivacyPolicy


def _privacy(**overrides: object) -> PrivacyMetadata:
    data: dict[str, object] = {
        "policy": PrivacyPolicy.REMOTE_ALLOWED,
        "sensitivity": SensitivityLevel.INTERNAL,
        "allowed_processing_locations": (
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        "allowed_providers": ("provider:alpha", "provider:beta"),
        "prohibited_providers": ("provider:gamma",),
        "allow_remote": True,
        "allow_premium": False,
        "allow_cache": True,
        "allow_export": False,
        "requires_redaction": True,
        "requires_approval": False,
        "inherited_from": ("resource:alpha",),
    }
    data.update(overrides)
    return PrivacyMetadata(**data)  # type: ignore[arg-type]


def _policy(**overrides: object) -> DomainPrivacyPolicy:
    data: dict[str, object] = {
        "schema_version": "1",
        "domain_id": DomainId(slug="university"),
        "default_privacy": _privacy(),
    }
    data.update(overrides)
    return DomainPrivacyPolicy(**data)  # type: ignore[arg-type]


# ── Shape, immutability and validation ────────────────────────────────────────


def test_domain_privacy_policy_is_frozen_and_slotted() -> None:
    policy = _policy()

    assert not hasattr(policy, "__dict__")
    with pytest.raises(FrozenInstanceError):
        policy.require_approval_for_remote = True  # type: ignore[misc]


def test_domain_privacy_policy_requires_canonical_domain_id() -> None:
    with pytest.raises(DomainPrivacyPolicyContractError):
        _policy(domain_id="domain:university")

    with pytest.raises(DomainPrivacyPolicyContractError):
        _policy(domain_id=None)


def test_domain_privacy_policy_requires_canonical_privacy_metadata() -> None:
    with pytest.raises(DomainPrivacyPolicyContractError):
        _policy(default_privacy={"policy": "remote_allowed"})

    with pytest.raises(DomainPrivacyPolicyContractError):
        _policy(default_privacy=None)


def test_domain_privacy_policy_rejects_unsupported_schema_version() -> None:
    with pytest.raises(DomainPrivacyPolicyContractError):
        _policy(schema_version="2")

    with pytest.raises(DomainPrivacyPolicyContractError):
        _policy(schema_version=1)


def test_domain_privacy_policy_requires_literal_bool_remote_approval() -> None:
    assert _policy(require_approval_for_remote=True).require_approval_for_remote is True
    assert (
        _policy(require_approval_for_remote=False).require_approval_for_remote is False
    )

    for invalid in (1, 0, "true", None):
        with pytest.raises(DomainPrivacyPolicyContractError):
            _policy(require_approval_for_remote=invalid)


def test_domain_privacy_policy_freezes_metadata() -> None:
    policy = _policy(metadata={"note": "declared", "nested": {"a": [1, 2]}})

    assert isinstance(policy.metadata, MappingProxyType)
    assert policy.metadata["note"] == "declared"
    assert policy.metadata["nested"]["a"] == (1, 2)

    with pytest.raises(TypeError):
        policy.metadata["note"] = "mutated"  # type: ignore[index]


def test_domain_privacy_policy_rejects_secret_like_metadata_keys() -> None:
    for key in ("api_key", "password", "secret", "access_token", "private_key"):
        with pytest.raises(DomainPrivacyPolicyContractError):
            _policy(metadata={key: "value"})

    with pytest.raises(DomainPrivacyPolicyContractError):
        _policy(metadata={"nested": {"credentials": "value"}})


def test_domain_privacy_policy_rejects_non_mapping_metadata() -> None:
    with pytest.raises(DomainPrivacyPolicyContractError):
        _policy(metadata=["not", "a", "mapping"])


# ── Serialization ─────────────────────────────────────────────────────────────


def test_domain_privacy_policy_to_dict_is_deterministic() -> None:
    policy = _policy(metadata={"b": 2, "a": 1})

    first = policy.to_dict()
    second = policy.to_dict()

    assert first == second
    assert first["schema_version"] == "1"
    assert first["domain_id"] == "domain:university"
    assert first["require_approval_for_remote"] is False
    assert first["metadata"] == {"a": 1, "b": 2}
    assert list(first.keys()) == [
        "schema_version",
        "domain_id",
        "default_privacy",
        "require_approval_for_remote",
        "metadata",
    ]


def test_domain_privacy_policy_round_trip_preserves_canonical_privacy() -> None:
    policy = _policy(
        require_approval_for_remote=True,
        metadata={"note": "declared", "nested": {"a": [1, 2]}},
    )

    payload = policy.to_dict()
    restored = DomainPrivacyPolicy.from_dict(payload)

    assert restored == policy
    assert restored.default_privacy == policy.default_privacy
    assert restored.to_dict() == payload

    privacy_payload = payload["default_privacy"]
    assert privacy_payload["policy"] == "remote_allowed"
    assert privacy_payload["sensitivity"] == "internal"
    assert privacy_payload["allowed_processing_locations"] == ["local", "remote"]
    assert privacy_payload["allowed_providers"] == ["provider:alpha", "provider:beta"]
    assert privacy_payload["prohibited_providers"] == ["provider:gamma"]
    assert privacy_payload["allow_remote"] is True
    assert privacy_payload["allow_premium"] is False
    assert privacy_payload["allow_cache"] is True
    assert privacy_payload["allow_export"] is False
    assert privacy_payload["requires_redaction"] is True
    assert privacy_payload["requires_approval"] is False
    assert privacy_payload["inherited_from"] == ["resource:alpha"]


def test_domain_privacy_policy_round_trip_accepts_enum_and_string_domain_id() -> None:
    payload = _policy().to_dict()
    payload["domain_id"] = {"slug": "university"}

    assert DomainPrivacyPolicy.from_dict(payload).domain_id == DomainId(
        slug="university"
    )


def test_domain_privacy_policy_from_dict_rejects_unknown_fields() -> None:
    payload = _policy().to_dict()
    payload["allow_cross_domain"] = True

    with pytest.raises(DomainPrivacyPolicySerializationError):
        DomainPrivacyPolicy.from_dict(payload)


def test_domain_privacy_policy_from_dict_rejects_missing_required_fields() -> None:
    payload = _policy().to_dict()
    del payload["domain_id"]

    with pytest.raises(DomainPrivacyPolicySerializationError):
        DomainPrivacyPolicy.from_dict(payload)


def test_domain_privacy_policy_from_dict_rejects_malformed_privacy_metadata() -> None:
    payload = _policy().to_dict()
    payload["default_privacy"]["sensitivity"] = "nonsense"

    with pytest.raises(DomainPrivacyPolicySerializationError):
        DomainPrivacyPolicy.from_dict(payload)

    payload = _policy().to_dict()
    payload["default_privacy"] = "not-a-mapping"

    with pytest.raises(DomainPrivacyPolicySerializationError):
        DomainPrivacyPolicy.from_dict(payload)


def test_domain_privacy_policy_from_dict_rejects_non_mapping_payload() -> None:
    with pytest.raises(DomainPrivacyPolicySerializationError):
        DomainPrivacyPolicy.from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_domain_privacy_policy_has_no_cross_domain_authority_field() -> None:
    policy = _policy()

    assert not hasattr(policy, "allow_cross_domain")
    assert "allow_cross_domain" not in {f for f in DomainPrivacyPolicy.__slots__}
    assert "allow_cross_domain" not in policy.to_dict()


def test_domain_privacy_policy_error_hierarchy() -> None:
    assert issubclass(DomainPrivacyPolicyContractError, DomainError)
    assert issubclass(DomainPrivacyPolicyContractError, ValueError)
    assert issubclass(
        DomainPrivacyPolicySerializationError, DomainPrivacyPolicyContractError
    )
