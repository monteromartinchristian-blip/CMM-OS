"""Phase 10.46 – ``DomainModelPolicy`` contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.model_policy_contracts import DomainModelPolicy

_APPROVED_FIELDS = (
    "domain_id",
    "require_reasoning",
    "require_tool_calling",
    "require_structured_output",
    "require_json_mode",
    "require_json_schema",
    "require_vision",
    "require_audio_input",
    "require_audio_output",
    "require_embeddings",
    "minimum_context_window",
    "require_context_validation",
    "require_response_validation",
    "fallback_policy",
    "metadata",
)

_BOOLEAN_FIELDS = (
    "require_reasoning",
    "require_tool_calling",
    "require_structured_output",
    "require_json_mode",
    "require_json_schema",
    "require_vision",
    "require_audio_input",
    "require_audio_output",
    "require_embeddings",
    "require_context_validation",
    "require_response_validation",
)

_FORBIDDEN_FIELDS = (
    "preferred_models",
    "prohibited_models",
    "preferred_providers",
    "prohibited_providers",
    "local_models",
    "minimum_quality",
    "latency_tolerance",
    "recommended_budget_eur",
)


def test_domain_model_policy_is_model_agnostic_and_serializable() -> None:
    policy = DomainModelPolicy(
        domain_id="domain:health",
        require_reasoning=True,
        require_structured_output=True,
        require_response_validation=True,
        minimum_context_window=32_768,
        metadata={"phase": "10.46"},
    )

    payload = policy.to_dict()

    assert payload["domain_id"] == "domain:health"
    assert payload["require_reasoning"] is True
    assert payload["require_structured_output"] is True
    assert payload["require_response_validation"] is True
    assert payload["minimum_context_window"] == 32_768
    assert DomainModelPolicy.from_dict(payload) == policy
    assert set(payload) == set(_APPROVED_FIELDS)
    assert set(_FORBIDDEN_FIELDS).isdisjoint(payload)


def test_domain_model_policy_defaults_match_approved_surface() -> None:
    policy = DomainModelPolicy(domain_id="domain:health")

    assert policy.domain_id == DomainId(slug="health")
    assert policy.minimum_context_window is None
    assert policy.fallback_policy is None
    assert dict(policy.metadata) == {}
    for field_name in _BOOLEAN_FIELDS:
        assert getattr(policy, field_name) is False


@pytest.mark.parametrize("field_name", _BOOLEAN_FIELDS)
def test_domain_model_policy_sets_and_round_trips_each_boolean(
    field_name: str,
) -> None:
    policy = DomainModelPolicy(domain_id="domain:health", **{field_name: True})

    assert getattr(policy, field_name) is True
    assert DomainModelPolicy.from_dict(policy.to_dict()) == policy


@pytest.mark.parametrize("field_name", _BOOLEAN_FIELDS)
def test_domain_model_policy_rejects_non_bool_boolean(field_name: str) -> None:
    with pytest.raises(DomainContractValidationError):
        DomainModelPolicy(domain_id="domain:health", **{field_name: 1})


def test_domain_model_policy_coerces_canonical_domain_id_string() -> None:
    policy = DomainModelPolicy(domain_id="domain:health")

    assert policy.domain_id == DomainId(slug="health")
    assert policy.to_dict()["domain_id"] == "domain:health"


def test_domain_model_policy_accepts_domain_id_instance() -> None:
    policy = DomainModelPolicy(domain_id=DomainId(slug="health"))

    assert policy.domain_id == DomainId(slug="health")


@pytest.mark.parametrize(
    "domain_id",
    ("health", "manifest:health:1.0.0", 42, None),
)
def test_domain_model_policy_rejects_non_domain_ids(domain_id: object) -> None:
    with pytest.raises(DomainError):
        DomainModelPolicy(domain_id=domain_id)  # type: ignore[arg-type]


def test_domain_model_policy_requires_positive_context_when_declared() -> None:
    with pytest.raises(DomainContractValidationError):
        DomainModelPolicy(domain_id="domain:health", minimum_context_window=0)


@pytest.mark.parametrize("value", (-1, 0, True, 1.5, "32768"))
def test_domain_model_policy_rejects_invalid_context_window(value: object) -> None:
    with pytest.raises(DomainContractValidationError):
        DomainModelPolicy(
            domain_id="domain:health",
            minimum_context_window=value,  # type: ignore[arg-type]
        )


def test_domain_model_policy_is_frozen() -> None:
    policy = DomainModelPolicy(domain_id="domain:health")

    with pytest.raises(FrozenInstanceError):
        policy.require_reasoning = True  # type: ignore[misc]


def test_domain_model_policy_freezes_metadata() -> None:
    policy = DomainModelPolicy(
        domain_id="domain:health",
        metadata={"phase": "10.46", "nested": {"k": [1, 2]}},
    )

    assert policy.metadata["phase"] == "10.46"
    assert policy.metadata["nested"]["k"] == (1, 2)
    with pytest.raises(TypeError):
        policy.metadata["phase"] = "other"  # type: ignore[index]
    with pytest.raises(TypeError):
        policy.metadata["nested"]["k"] = ()  # type: ignore[index]


def test_domain_model_policy_rejects_non_mapping_metadata() -> None:
    with pytest.raises(DomainContractValidationError):
        DomainModelPolicy(domain_id="domain:health", metadata=["phase"])  # type: ignore[arg-type]


def test_domain_model_policy_rejects_non_string_metadata_keys() -> None:
    with pytest.raises(DomainContractValidationError):
        DomainModelPolicy(domain_id="domain:health", metadata={1: "phase"})


def test_domain_model_policy_rejects_unknown_model_selection_fields() -> None:
    with pytest.raises(DomainSerializationError):
        DomainModelPolicy.from_dict(
            {
                "domain_id": "domain:health",
                "preferred_models": ["vendor:model"],
            }
        )


@pytest.mark.parametrize("field_name", _FORBIDDEN_FIELDS)
def test_domain_model_policy_rejects_every_forbidden_field(field_name: str) -> None:
    with pytest.raises(DomainSerializationError):
        DomainModelPolicy.from_dict(
            {"domain_id": "domain:health", field_name: ["vendor:model"]}
        )


def test_domain_model_policy_rejects_unknown_field() -> None:
    with pytest.raises(DomainSerializationError):
        DomainModelPolicy.from_dict(
            {"domain_id": "domain:health", "unexpected": "value"}
        )


def test_domain_model_policy_requires_domain_id_in_from_dict() -> None:
    with pytest.raises(DomainSerializationError):
        DomainModelPolicy.from_dict({"require_reasoning": True})


def test_domain_model_policy_from_dict_requires_mapping() -> None:
    with pytest.raises(DomainSerializationError):
        DomainModelPolicy.from_dict(["domain:health"])  # type: ignore[arg-type]


def test_domain_model_policy_round_trip_is_deterministic() -> None:
    policy = DomainModelPolicy(
        domain_id="domain:health",
        require_tool_calling=True,
        minimum_context_window=8_192,
        metadata={"phase": "10.46", "tags": ["a", "b"]},
    )

    first = policy.to_dict()
    second = DomainModelPolicy.from_dict(first).to_dict()

    assert first == second


def test_domain_model_policy_rejects_invalid_fallback_policy_type() -> None:
    with pytest.raises(DomainContractValidationError):
        DomainModelPolicy(domain_id="domain:health", fallback_policy="nope")  # type: ignore[arg-type]


def test_domain_model_policy_round_trips_typed_fallback_policy() -> None:
    from cmm.agent_runtime.model_fallback_contracts import ModelFallbackPolicy

    fallback = ModelFallbackPolicy(id="domain-health-fallback", maximum_attempts=2)
    policy = DomainModelPolicy(domain_id="domain:health", fallback_policy=fallback)

    payload = policy.to_dict()

    assert payload["fallback_policy"]["id"] == "domain-health-fallback"
    restored = DomainModelPolicy.from_dict(payload)
    assert restored.fallback_policy == fallback
    assert restored == policy


def test_domain_model_policy_is_exported_from_domains_package() -> None:
    from cmm import domains

    assert domains.DomainModelPolicy is DomainModelPolicy
    assert "DomainModelPolicy" in domains.__all__
