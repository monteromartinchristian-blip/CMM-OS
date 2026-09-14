"""Contract tests for non-routable hybrid provider candidates.

Candidates are detection evidence, never execution handles: they must not
grow credential references, connection ids, or execution methods.
"""

import dataclasses

import pytest

from kernel.llm.provider_candidates import CandidateRisk, ProviderCandidate

# Attribute/method names that would make a candidate routable or executable.
_FORBIDDEN_ATTRIBUTES = (
    "credential_ref",
    "connection_id",
    "connect",
    "execute",
    "invoke",
    "generate",
    "complete",
    "chat",
    "run",
)


def _candidate(**overrides: object) -> ProviderCandidate:
    kwargs: dict[str, object] = {
        "provider_id": "deepseek",
        "source": "env",
        "detected": True,
        "auth_available": True,
        "external_config_present": False,
        "external_endpoint_override_present": False,
        "risks": (),
    }
    kwargs.update(overrides)
    return ProviderCandidate(**kwargs)  # type: ignore[arg-type]


def test_candidate_carries_exact_field_set() -> None:
    names = [field.name for field in dataclasses.fields(ProviderCandidate)]

    assert names == [
        "provider_id",
        "source",
        "detected",
        "auth_available",
        "external_config_present",
        "external_endpoint_override_present",
        "risks",
        "metadata",
    ]


def test_candidate_is_frozen_and_slots_backed() -> None:
    candidate = _candidate()

    assert dataclasses.is_dataclass(candidate)
    assert not hasattr(candidate, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.provider_id = "other"  # type: ignore[misc]


def test_candidate_has_no_routable_attributes_or_execution_methods() -> None:
    candidate = _candidate()

    names = [field.name for field in dataclasses.fields(ProviderCandidate)]
    for forbidden in _FORBIDDEN_ATTRIBUTES:
        assert forbidden not in names
        assert not hasattr(candidate, forbidden)


def test_candidate_normalizes_provider_id_and_source() -> None:
    candidate = _candidate(provider_id="  DeepSeek  ", source="  env  ")

    assert candidate.provider_id == "deepseek"
    assert candidate.source == "env"


def test_candidate_rejects_blank_provider_id_and_source() -> None:
    with pytest.raises(ValueError, match="Provider id cannot be empty"):
        _candidate(provider_id="   ")
    with pytest.raises(ValueError, match="source cannot be empty"):
        _candidate(source="   ")


def test_candidate_coerces_risks_to_tuple_and_rejects_unknown() -> None:
    candidate = _candidate(risks=[CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE])

    assert candidate.risks == (CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE,)
    with pytest.raises(ValueError, match="unknown risk"):
        _candidate(risks=("no-such-risk",))  # type: ignore[list-item]


def test_candidate_metadata_defaults_to_empty_and_coerces_pairs() -> None:
    assert _candidate().metadata == ()
    candidate = _candidate(metadata=[("path", "~/.codex/auth.json")])

    assert candidate.metadata == (("path", "~/.codex/auth.json"),)


def test_candidate_metadata_rejects_secret_shaped_values() -> None:
    with pytest.raises(ValueError, match="metadata must not carry secrets"):
        _candidate(metadata=(("api_key", "sk-abc123"),))
    with pytest.raises(ValueError, match="metadata must not carry secrets"):
        _candidate(metadata=(("token", "Bearer abc123"),))
    with pytest.raises(ValueError, match="metadata must not carry secrets"):
        _candidate(metadata=(("auth", "password=hunter2"),))
    with pytest.raises(ValueError, match="metadata cannot contain empty"):
        _candidate(metadata=(("path", "   "),))


def test_candidate_risk_includes_external_endpoint_override() -> None:
    assert CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE.value == (
        "external-endpoint-override"
    )
