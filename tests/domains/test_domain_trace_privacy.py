"""Privacy boundary tests for reference-only Domain Trace metadata."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.trace_contracts import (
    DomainTraceAssemblyRequest,
    DomainTraceContractError,
    DomainTraceContribution,
    DomainTraceReferences,
    DomainTraceRole,
)


def _request(metadata):
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    return DomainTraceAssemblyRequest(
        request_id="request:1", primary_domain="domain:life-plan",
        contributions=(DomainTraceContribution("domain:life-plan", DomainTraceRole.PRIMARY),),
        references=DomainTraceReferences("resolution-context:1", "resolution-result:1", "composition:1"),
        started_at=now, completed_at=now, metadata=metadata,
    )


@pytest.mark.parametrize("key", ["system-prompt", "USER MESSAGE", "raw_content", "tool response", "API_KEY", "chain_of_thought"])
def test_private_keys_are_rejected_after_normalization(key: str) -> None:
    with pytest.raises(DomainTraceContractError):
        _request({"outer": {key: "safe-id"}})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_metadata_is_rejected(value: float) -> None:
    with pytest.raises(DomainTraceContractError):
        _request({"score": value})


def test_safe_reference_metadata_names_are_not_false_positives() -> None:
    request = _request({
        "reasoning_trace_id": "reasoning-trace:1",
        "knowledge_package_id": "package:1",
        "provider_audit_id": "audit:1",
        "cross_domain_trace_id": "cross-trace:1",
    })

    assert request.metadata["reasoning_trace_id"] == "reasoning-trace:1"


@pytest.mark.parametrize(
    "key",
    ["prompt_text", "system_prompt_backup", "secret_value", "my-user-message"],
)
def test_private_key_token_variants_are_rejected(key: str) -> None:
    with pytest.raises(DomainTraceContractError):
        _request({"outer": {key: "safe-id"}})


@pytest.mark.parametrize(
    "key",
    [
        "promptText",
        "secretValue",
        "systemPromptBackup",
        "rawContentBackup",
        "chainOfThoughtData",
        "developerPromptText",
        "userMessageBackup",
    ],
)
def test_private_camel_and_pascal_case_keys_are_rejected(key: str) -> None:
    with pytest.raises(DomainTraceContractError):
        _request({"outer": {key: "safe-id"}})


def test_excessive_metadata_depth_is_rejected() -> None:
    with pytest.raises(DomainTraceContractError):
        _request({"a": {"b": {"c": {"d": {"e": "safe-id"}}}}})
