"""Phase 11.2 — structured orchestration error tests.

Phase 11.2 reuses the Phase 11.1 :class:`cmm.platform.contracts.ErrorResult`
boundary value.  These tests prove that internal typed exceptions expose only
safe identifiers and reason codes, never secrets, raw request payloads, hidden
reasoning or tracebacks.
"""

from __future__ import annotations

import json

import pytest

from cmm.orchestration.errors import (
    AgentRoutingError,
    ContextResolutionError,
    DecisionPersistenceError,
    DomainRoutingError,
    IntentResolutionError,
    OrchestrationError,
    OrchestrationPolicyError,
)
from cmm.platform.contracts import ErrorResult

ERROR_TYPES = (
    IntentResolutionError,
    ContextResolutionError,
    DomainRoutingError,
    AgentRoutingError,
    OrchestrationPolicyError,
    DecisionPersistenceError,
)


def test_orchestration_error_is_an_exception() -> None:
    error = OrchestrationError("orchestration failed closed")

    assert isinstance(error, Exception)
    assert str(error) == "orchestration failed closed"


def test_orchestration_error_exposes_structured_facts() -> None:
    error = OrchestrationError(
        "orchestration failed closed",
        code="ORCHESTRATION_TEST",
        details={"request_id": "request-1"},
    )

    assert error.code == "ORCHESTRATION_TEST"
    assert error.category == "orchestration"
    assert error.retryable is False


@pytest.mark.parametrize("error_type", ERROR_TYPES, ids=lambda item: item.__name__)
def test_error_subclasses_declare_category_and_code(error_type: type) -> None:
    error = error_type("failure")

    assert isinstance(error, OrchestrationError)
    assert error.code
    assert error.category
    assert error.retryable is False


def test_every_error_category_is_distinct() -> None:
    categories = {error_type("failure").category for error_type in ERROR_TYPES}

    assert len(categories) == len(ERROR_TYPES)


def test_error_converts_to_a_platform_error_result() -> None:
    error = DomainRoutingError(
        "canonical domain resolution was blocked",
        details={"request_id": "request-1", "reason_code": "DOMAIN_POLICY_DENIED"},
    )

    result = error.to_error_result()

    assert isinstance(result, ErrorResult)
    assert result.code == error.code
    assert result.category == error.category
    assert result.message == "canonical domain resolution was blocked"
    assert dict(result.details) == {
        "request_id": "request-1",
        "reason_code": "DOMAIN_POLICY_DENIED",
    }


def test_error_result_serializes_without_traceback() -> None:
    error = ContextResolutionError("context resolution failed")

    payload = json.loads(json.dumps(dict(error.to_error_result().details)))

    assert payload == {}
    assert "traceback" not in str(error.to_error_result().details).lower()


def test_error_requires_a_non_empty_message() -> None:
    with pytest.raises(ValueError):
        OrchestrationError("   ")


def test_error_rejects_an_empty_code() -> None:
    with pytest.raises(ValueError):
        OrchestrationError("failure", code="  ")


def test_error_rejects_a_non_mapping_details_payload() -> None:
    with pytest.raises(TypeError):
        OrchestrationError("failure", details=["request-1"])


def test_error_rejects_non_string_detail_values() -> None:
    with pytest.raises(TypeError):
        OrchestrationError("failure", details={"request_id": {"raw": "request text"}})


def test_error_rejects_a_payload_shaped_detail_key() -> None:
    with pytest.raises(ValueError):
        OrchestrationError("failure", details={"payload": "raw request text"})


def test_error_rejects_raw_request_text_detail() -> None:
    with pytest.raises(ValueError):
        OrchestrationError(
            "failure",
            details={"request_text": "raw user request"},
        )


@pytest.mark.parametrize(
    "key",
    [
        "secret",
        "api_key",
        "credential",
        "authorization",
        "password",
        "token",
        "prompt",
        "reasoning",
        "chain_of_thought",
        "hidden_reasoning",
        "provider_payload",
        "traceback",
    ],
)
def test_error_details_reject_unsafe_keys(key: str) -> None:
    with pytest.raises(ValueError):
        OrchestrationError("failure", details={key: "value"})


@pytest.mark.parametrize(
    "key",
    [
        "secret",
        "api-key",
        "apiKey",
        "Access_Token",
        "providerPayload",
        "chainOfThought",
    ],
)
def test_error_details_normalize_keys_before_the_denylist(key: str) -> None:
    with pytest.raises(ValueError):
        OrchestrationError("failure", details={key: "value"})


def test_error_details_allow_safe_identifiers() -> None:
    error = OrchestrationError(
        "failure",
        details={
            "request_id": "request-1",
            "session_id": "session-1",
            "service_id": "orchestration.orchestrator",
            "domain_id": "domain:health",
            "agent_id": "agent.alpha",
            "route": "direct_response",
            "reason_code": "DOMAIN_AMBIGUOUS_SCORE",
        },
    )

    assert set(error.to_error_result().details) == {
        "request_id",
        "session_id",
        "service_id",
        "domain_id",
        "agent_id",
        "route",
        "reason_code",
    }


def test_error_details_are_defensively_copied() -> None:
    details = {"request_id": "request-1"}

    error = OrchestrationError("failure", details=details)
    details["request_id"] = "mutated"

    assert dict(error.to_error_result().details) == {"request_id": "request-1"}


def test_decision_persistence_error_is_not_retryable() -> None:
    error = DecisionPersistenceError("decision persistence failed closed")

    assert error.retryable is False
    assert error.category == "persistence"


def test_subclass_may_override_the_default_code() -> None:
    error = IntentResolutionError(
        "intent resolution failed closed",
        code="INTENT_RESOLUTION_FAILED",
    )

    assert error.code == "INTENT_RESOLUTION_FAILED"


def test_subclass_rejects_an_invalid_retryable_override() -> None:
    with pytest.raises(TypeError):
        OrchestrationError("failure", retryable="yes")
