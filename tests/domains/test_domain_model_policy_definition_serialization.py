"""Phase 10.46 – ``DomainDefinition`` model policy attachment and serialization."""

from __future__ import annotations

import pytest

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.model_policy_contracts import DomainModelPolicy


def _make_definition(**overrides: object) -> DomainDefinition:
    data: dict[str, object] = {
        "id": "domain:test",
        "name": "test",
        "display_name": "Test",
        "version": "1.0.0",
        "kind": DomainKind.PERSONAL,
        "description": "test domain",
        "manifest_id": "manifest:test:1.0.0",
    }
    data.update(overrides)
    return DomainDefinition(**data)  # type: ignore[arg-type]


def test_domain_definition_defaults_model_policy_to_none() -> None:
    assert _make_definition().model_policy is None


def test_domain_definition_round_trips_model_policy() -> None:
    definition = _make_definition(
        model_policy=DomainModelPolicy(
            domain_id="domain:test",
            require_tool_calling=True,
            require_response_validation=True,
            minimum_context_window=16_384,
        )
    )

    payload = definition.to_dict()
    restored = DomainDefinition.from_dict(payload)

    assert payload["model_policy"]["domain_id"] == "domain:test"
    assert restored.model_policy == definition.model_policy
    assert restored.to_dict() == payload


def test_domain_definition_coerces_model_policy_mapping() -> None:
    payload = _make_definition().to_dict()
    payload["model_policy"] = {
        "domain_id": "domain:test",
        "require_reasoning": True,
    }

    definition = DomainDefinition.from_dict(payload)

    assert isinstance(definition.model_policy, DomainModelPolicy)
    assert definition.model_policy.require_reasoning is True


def test_domain_definition_rejects_model_policy_for_another_domain() -> None:
    with pytest.raises(DomainContractValidationError):
        _make_definition(model_policy=DomainModelPolicy(domain_id="domain:other"))


def test_domain_definition_rejects_mapping_policy_for_another_domain() -> None:
    payload = _make_definition().to_dict()
    payload["model_policy"] = {"domain_id": "domain:other"}

    with pytest.raises(DomainContractValidationError):
        DomainDefinition.from_dict(payload)


def test_domain_definition_rejects_invalid_model_policy_type() -> None:
    with pytest.raises(DomainContractValidationError):
        _make_definition(model_policy="nope")


def test_domain_definition_serializes_absent_policy_as_none() -> None:
    payload = _make_definition().to_dict()

    assert "model_policy" in payload
    assert payload["model_policy"] is None


def test_domain_definition_from_dict_accepts_legacy_payload() -> None:
    payload = _make_definition().to_dict()
    payload.pop("model_policy")

    definition = DomainDefinition.from_dict(payload)

    assert definition.model_policy is None
    assert definition == _make_definition()


def test_domain_definition_rejects_unknown_policy_field_in_mapping() -> None:
    payload = _make_definition().to_dict()
    payload["model_policy"] = {
        "domain_id": "domain:test",
        "preferred_models": ["vendor:model"],
    }

    with pytest.raises(DomainSerializationError):
        DomainDefinition.from_dict(payload)
