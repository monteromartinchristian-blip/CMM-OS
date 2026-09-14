"""Phase 10.33 independent audit V3 regression tests.

These tests encode findings for B2 from the independent audit V3
of Phase 10.33 Domain Events (docs/audits/phase-10.33-independent-audit-v3.md).

Strict TDD: Written to observe RED against audited HEAD before minimal GREEN remediation.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainEventContractError,
    DomainEventSerializationError,
)
from cmm.domains.event_adapters import (
    adapt_execution_failed,
    adapt_operation_failed,
)
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.event_factory import DomainEventFactory
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.identifiers import DomainId


def _sample_event(
    *,
    event_id: str = "evt-v3-123",
    event_type: str = "domain.resolution.started",
    schema_version: str = "1.0.0",
    domain_id: DomainId | str = "domain:project",
    actor: str = "system",
    sensitivity: str = "internal",
    occurred_at: datetime | None = None,
    payload: Any = None,
    metadata: Any = None,
    permissions: Sequence[str] = (),
    provenance: Sequence[Any] = (),
    session_id: Any = None,
    correlation_id: Any = None,
    causation_id: Any = None,
    related_domain_ids: Any = (),
) -> DomainEvent:
    dom = DomainId.from_str(domain_id) if isinstance(domain_id, str) else domain_id
    occ = occurred_at or datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    return DomainEvent(
        event_id=event_id,
        event_type=event_type,
        schema_version=schema_version,
        domain_id=dom,
        actor=actor,
        sensitivity=sensitivity,
        occurred_at=occ,
        payload=payload if payload is not None else {},
        metadata=metadata if metadata is not None else {},
        permissions=permissions,
        provenance=tuple(provenance),
        session_id=session_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        related_domain_ids=related_domain_ids,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Explicit event_id privacy validation (secret-shaped and password-shaped)
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v3_b2_direct_construction_rejects_secret_shaped_event_id() -> None:
    """Direct DomainEvent construction must reject secret-shaped explicit event_id."""
    synthetic_key = "sk-" + "A" * 40
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(event_id=synthetic_key)


def test_audit_v3_b2_direct_construction_rejects_password_shaped_event_id() -> None:
    """Direct DomainEvent construction must reject password-shaped explicit event_id."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(event_id="password=supersecret123")


def test_audit_v3_b2_from_dict_rejects_secret_shaped_event_id() -> None:
    """DomainEvent.from_dict must reject secret-shaped event_id."""
    synthetic_key = "sk-" + "A" * 40
    data = {
        "event_id": synthetic_key,
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(
        (
            DomainEventSerializationError,
            DomainContractValidationError,
            DomainEventContractError,
        )
    ):
        DomainEvent.from_dict(data)


def test_audit_v3_b2_factory_create_event_rejects_secret_shaped_explicit_event_id() -> (
    None
):
    """DomainEventFactory.create_event must reject secret-shaped explicit event_id."""
    synthetic_key = "sk-" + "A" * 40
    factory = DomainEventFactory()
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            event_id=synthetic_key,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DomainEventReference.reference_id rejects forbidden private-content markers
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "forbidden_ref_id",
    [
        "system_prompt",
        "raw_prompt: hidden instructions",
        "pii:user@example.com",
        "chain_of_thought: private reasoning",
        "hidden_reasoning",
        "developer_prompt",
        "raw_content: confidential text",
        "tool_arguments: sensitive args",
        "provider_response: raw payload",
    ],
)
def test_audit_v3_b2_reference_id_rejects_private_content_markers(
    forbidden_ref_id: str,
) -> None:
    """DomainEventReference direct construction must reject private-content markers in reference_id."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(
            kind="resolution",
            reference_id=forbidden_ref_id,
        )


@pytest.mark.parametrize(
    "forbidden_ref_id",
    [
        "system_prompt",
        "raw_prompt: hidden instructions",
        "pii:user@example.com",
    ],
)
def test_audit_v3_b2_reference_id_from_dict_rejects_private_content_markers(
    forbidden_ref_id: str,
) -> None:
    """DomainEventReference.from_dict must reject private-content markers in reference_id."""
    with pytest.raises(
        (
            DomainEventSerializationError,
            DomainContractValidationError,
            DomainEventContractError,
        )
    ):
        DomainEventReference.from_dict(
            {
                "kind": "resolution",
                "reference_id": forbidden_ref_id,
            }
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Recursive payload/metadata string values reject private-content markers
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "unsafe_payload",
    [
        {"note": "system_prompt: hidden instructions"},
        {"note": "chain_of_thought: private reasoning"},
        {"note": "chain-of-thought: private reasoning"},
        {"note": "pii: alice@example.com"},
        {"note": "raw_content: confidential text"},
        {"note": "developer_prompt: instructions"},
        {"note": "hidden_reasoning: thinking steps"},
        {"note": "reasoning_content: internal steps"},
        {"note": "provider_request: confidential params"},
        {"note": "tool_arguments: secret args"},
    ],
)
def test_audit_v3_b2_payload_string_values_reject_private_markers(
    unsafe_payload: dict[str, str],
) -> None:
    """Payload string values containing forbidden private-content markers must be rejected."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload=unsafe_payload)


@pytest.mark.parametrize(
    "unsafe_metadata",
    [
        {"info": "system_prompt: hidden instructions"},
        {"info": "chain_of_thought: private reasoning"},
        {"info": "pii: user@domain.com"},
        {"info": "raw_content: secret text"},
    ],
)
def test_audit_v3_b2_metadata_string_values_reject_private_markers(
    unsafe_metadata: dict[str, str],
) -> None:
    """Metadata string values containing forbidden private-content markers must be rejected."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(metadata=unsafe_metadata)


def test_audit_v3_b2_deeply_nested_private_marker_rejection() -> None:
    """Deeply nested structures (dict in list in dict) must reject private markers in string values."""
    deep_payload = {
        "outer": [
            {"safe_key": "safe_val"},
            {"nested_list": ["ok", {"target": "system_prompt: leaked_prompt"}]},
        ]
    }
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload=deep_payload)

    deep_metadata = {
        "level1": {
            "level2": ("item1", "pii: bob@example.com"),
        }
    }
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(metadata=deep_metadata)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Multi-part Cookie / Set-Cookie header sanitization in failure adapters
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v3_b2_multi_part_cookie_header_fully_sanitized() -> None:
    """Multi-part Cookie header must be completely redacted with no residual sessionid."""
    raw_error = (
        "Request failed with Cookie: foo=bar; sessionid=VERYSECRET_SESSION_TOKEN_12345"
    )
    evt = adapt_operation_failed(
        operation_id="op-v3-1",
        domain_id="domain:project",
        error=raw_error,
    )
    error_str = str(evt.payload["error"])
    assert "VERYSECRET_SESSION_TOKEN_12345" not in error_str
    assert "sessionid=" not in error_str
    assert "foo=bar" not in error_str


def test_audit_v3_b2_multi_part_set_cookie_header_fully_sanitized() -> None:
    """Multi-part Set-Cookie header must be completely redacted with no residual csrftoken."""
    raw_error = (
        "Response header Set-Cookie: a=b; csrftoken=TOPSECRET_CSRF_TOKEN_67890; Path=/"
    )
    evt = adapt_execution_failed(
        execution_id="exec-v3-1",
        domain_id="domain:project",
        error=raw_error,
    )
    error_str = str(evt.payload["error"])
    assert "TOPSECRET_CSRF_TOKEN_67890" not in error_str
    assert "csrftoken=" not in error_str
    assert "a=b" not in error_str


def test_audit_v3_b2_secondary_token_material_absent_from_failure_event() -> None:
    """Secondary session and csrf token assignments without Cookie header must be sanitized."""
    raw_error = "Auth context failed: sessionid=MY_SECRET_ID_999 and csrftoken=CSRF_TOKEN_VAL_888"
    evt = adapt_operation_failed(
        operation_id="op-v3-sec",
        domain_id="domain:project",
        error=raw_error,
    )
    error_str = str(evt.payload["error"])
    assert "MY_SECRET_ID_999" not in error_str
    assert "CSRF_TOKEN_VAL_888" not in error_str


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Validation errors must not echo rejected private content
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v3_b2_validation_exception_message_does_not_echo_secret() -> None:
    """Validation exception message must not contain raw secret or private content."""
    secret_text = "SECRET_INSTRUCTION_BODY_XYZ_12345"
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(actor=f"sk-{secret_text}")

    exc_msg = str(exc_info.value)
    assert secret_text not in exc_msg
    assert "sk-" not in exc_msg


def test_audit_v3_b2_validation_exception_details_do_not_echo_private_content() -> None:
    """Validation exception details must not contain raw private marker string."""
    private_payload_text = "system_prompt: DO NOT REVEAL THIS TEXT"
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(payload={"note": private_payload_text})

    exc_msg = str(exc_info.value)
    assert "DO NOT REVEAL THIS TEXT" not in exc_msg

    exc_details = getattr(exc_info.value, "details", {})
    assert "DO NOT REVEAL THIS TEXT" not in str(exc_details)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Kernel publication boundary privacy
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v3_b2_kernel_publication_boundary_cannot_receive_rejected_data() -> None:
    """Invalid event IDs, private reference IDs, and private payload data fail before publication."""
    publisher = DomainKernelEventPublisher()
    synthetic_key = "sk-" + "A" * 40

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt = _sample_event(event_id=synthetic_key)
        publisher.publish(bad_evt)

    assert len(publisher.emitted_events) == 0


def test_audit_v3_b2_valid_event_content_preserved_and_json_serializable() -> None:
    """Legitimate text without private markers or secrets passes validation and serializes cleanly."""
    event = _sample_event(
        event_id="evt-v3-safe-100",
        actor="system_agent",
        payload={
            "status": "completed",
            "message": "Domain task finished successfully",
            "count": 5,
            "metrics": {"duration_ms": 42.5},
        },
        metadata={"environment": "production", "version": "1.0.0"},
    )
    serialized = json.dumps(event.to_dict())
    assert "Domain task finished successfully" in serialized
    deserialized = json.loads(serialized)
    assert deserialized["payload"]["status"] == "completed"
