"""Tests for Phase 10.18 Domain Memory strict privacy boundaries."""

from typing import Any

import pytest

from cmm.domains.errors import DomainMemoryPrivacyError
from cmm.domains.memory_contracts import (
    DomainMemoryReference,
    DomainMemoryReferenceKind,
)


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "content",
        "raw_content",
        "rawContent",
        "RawContent",
        "raw-content",
        "raw content",
        "claim_text",
        "claimText",
        "ClaimText",
        "claim-text",
        "claim text",
        "payload",
        "payloads",
        "raw_payload",
        "rawPayload",
        "resource_content",
        "resourceContent",
        "ResourceContent",
        "user_message",
        "userMessage",
        "UserMessage",
        "message",
        "prompt",
        "prompts",
        "system_prompt",
        "systemPrompt",
        "SystemPrompt",
        "developer_prompt",
        "reasoning",
        "chain_of_thought",
        "chainOfThought",
        "ChainOfThought",
        "raw_reasoning",
        "reasoning_text",
        "secret",
        "secrets",
        "credential",
        "credentials",
        "token",
        "tokens",
        "password",
        "passwords",
        "api_key",
        "apiKey",
        "ApiKey",
        "APIKey",
        "api-key",
        "api key",
        "provider_request",
        "providerRequest",
        "provider_response",
        "providerResponse",
        "tool_arguments",
        "toolArguments",
        "tool_response",
        "toolResponse",
        "pii",
    ],
)
def test_metadata_rejects_forbidden_privacy_keys(forbidden_key: str) -> None:
    with pytest.raises(DomainMemoryPrivacyError) as exc_info:
        DomainMemoryReference(
            reference_id="ref:privacy:1",
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id="item:1",
            domain_id="domain:health",
            metadata={forbidden_key: "forbidden_value_xyz"},
        )
    # Ensure error message NEVER echoes rejected value or key
    assert "forbidden_value_xyz" not in str(exc_info.value)


def test_metadata_rejects_nested_forbidden_privacy_keys() -> None:
    with pytest.raises(DomainMemoryPrivacyError):
        DomainMemoryReference(
            reference_id="ref:privacy:2",
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id="item:2",
            domain_id="domain:health",
            metadata={"nested": {"deep": {"chainOfThought": "step 1"}}},
        )


def test_metadata_rejects_excessive_depth() -> None:
    deep_meta: dict[str, Any] = {}
    curr = deep_meta
    for _ in range(6):
        curr["child"] = {}
        curr = curr["child"]
    curr["val"] = "too deep"

    with pytest.raises(DomainMemoryPrivacyError):
        DomainMemoryReference(
            reference_id="ref:privacy:3",
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id="item:3",
            domain_id="domain:health",
            metadata=deep_meta,
        )


def test_metadata_rejects_oversized_string() -> None:
    long_str = "a" * 200
    with pytest.raises(DomainMemoryPrivacyError):
        DomainMemoryReference(
            reference_id="ref:privacy:4",
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id="item:4",
            domain_id="domain:health",
            metadata={"label": long_str},
        )


def test_metadata_rejects_sensitive_value_under_innocuous_key() -> None:
    with pytest.raises(DomainMemoryPrivacyError):
        DomainMemoryReference(
            reference_id="ref:privacy:5",
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id="item:5",
            domain_id="domain:health",
            metadata={"category": "secret-password-value"},
        )


def test_decision_and_validation_result_structurally_pii_proof() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySelectionDecision,
        DomainMemorySelectionDecisionCode,
        DomainMemoryValidationCode,
        DomainMemoryValidationResult,
    )

    dec = DomainMemorySelectionDecision(
        reference_id="ref:1",
        code=DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED,
        related_reference_ids=("ref:2",),
        permission_decision_ids=("perm:1",),
    )
    assert not hasattr(dec, "reason")
    assert dec.to_dict() == {
        "reference_id": "ref:1",
        "code": "excluded_permission_denied",
        "related_reference_ids": ["ref:2"],
        "permission_decision_ids": ["perm:1"],
    }

    res = DomainMemoryValidationResult(
        is_valid=False,
        code=DomainMemoryValidationCode.INVALID_PRIVACY_BREACH,
        codes=(DomainMemoryValidationCode.INVALID_PRIVACY_BREACH,),
        affected_reference_ids=("ref:1",),
    )
    assert res.diagnostics == ("invalid_privacy_breach",)
    assert res.to_dict()["codes"] == ["invalid_privacy_breach"]
