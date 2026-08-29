"""Phase 10.33 independent audit V5 regression tests.

These tests encode findings for B2 from the independent audit V5
of Phase 10.33 Domain Events (docs/audits/phase-10.33-independent-audit-v5.md).

Strict TDD: Written to observe RED against audited HEAD before minimal GREEN remediation.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

import pytest

from cmm.domains.errors import (
    DomainEventContractError,
    DomainEventSerializationError,
)
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.event_factory import DomainEventFactory
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.identifiers import DomainId

_SYNTHETIC_SECRET = "sk-" + "A" * 40


class _CustomObject:
    """Arbitrary non-JSON object."""

    def __init__(self, value: Any = "custom") -> None:
        self.value = value


class _SecretCarrier:
    """Arbitrary object carrying synthetic secret in attribute and repr."""

    def __init__(self, secret: str = _SYNTHETIC_SECRET) -> None:
        self.secret = secret

    def __repr__(self) -> str:
        return f"_SecretCarrier({self.secret})"


class _SecretKey:
    """Custom hashable object whose repr contains synthetic secret."""

    def __init__(self, secret: str = _SYNTHETIC_SECRET) -> None:
        self.secret = secret

    def __hash__(self) -> int:
        return hash(self.secret)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _SecretKey):
            return self.secret == other.secret
        return False

    def __repr__(self) -> str:
        return f"_SecretKey({self.secret})"


def _sample_event(
    *,
    event_id: str = "evt-v5-100",
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
    dom = (
        DomainId.from_str(domain_id)
        if isinstance(domain_id, str) and domain_id.startswith("domain:")
        else DomainId(slug=domain_id)
        if isinstance(domain_id, str)
        else domain_id
    )
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


def _sample_event_dict(
    *,
    payload: Any = None,
    metadata: Any = None,
    extra_fields: dict[Any, Any] | None = None,
) -> dict[Any, Any]:
    base: dict[Any, Any] = {
        "event_id": "evt-v5-valid-1",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
        "payload": payload if payload is not None else {},
        "metadata": metadata if metadata is not None else {},
    }
    if extra_fields:
        base.update(extra_fields)
    return base


def _sample_reference_dict(
    *,
    extra_fields: dict[Any, Any] | None = None,
) -> dict[Any, Any]:
    base: dict[Any, Any] = {
        "kind": "resolution",
        "reference_id": "res-1",
    }
    if extra_fields:
        base.update(extra_fields)
    return base


# ===============================================================================
# 1. B2.1 — MappingProxyType bypass: JSON safety, deep immutability, privacy
# ===============================================================================


def test_audit_v5_b2_payload_mapping_proxy_with_custom_object_rejected() -> None:
    """Payload MappingProxyType with custom object must be rejected with DomainEventContractError."""
    with pytest.raises(DomainEventContractError):
        _sample_event(payload=MappingProxyType({"opaque": _CustomObject()}))


def test_audit_v5_b2_metadata_mapping_proxy_with_custom_object_rejected() -> None:
    """Metadata MappingProxyType with custom object must be rejected with DomainEventContractError."""
    with pytest.raises(DomainEventContractError):
        _sample_event(metadata=MappingProxyType({"opaque": _CustomObject()}))


def test_audit_v5_b2_payload_mapping_proxy_with_set_rejected() -> None:
    """Payload MappingProxyType with set must be rejected with DomainEventContractError."""
    with pytest.raises(DomainEventContractError):
        _sample_event(payload=MappingProxyType({"tags": {"a", "b"}}))


def test_audit_v5_b2_payload_mapping_proxy_with_frozenset_rejected() -> None:
    """Payload MappingProxyType with frozenset must be rejected with DomainEventContractError."""
    with pytest.raises(DomainEventContractError):
        _sample_event(payload=MappingProxyType({"tags": frozenset({"a", "b"})}))


@pytest.mark.parametrize(
    "bad_float",
    [
        float("inf"),
        float("-inf"),
        float("nan"),
    ],
)
def test_audit_v5_b2_payload_mapping_proxy_with_non_finite_float_rejected(
    bad_float: float,
) -> None:
    """Payload MappingProxyType with non-finite float must be rejected."""
    with pytest.raises(DomainEventContractError):
        _sample_event(payload=MappingProxyType({"value": bad_float}))


def test_audit_v5_b2_payload_mapping_proxy_with_non_string_key_rejected() -> None:
    """Payload MappingProxyType with non-string key must raise typed DomainEventContractError."""
    with pytest.raises(DomainEventContractError):
        _sample_event(payload=MappingProxyType({123: "val"}))  # type: ignore[dict-item]


def test_audit_v5_b2_payload_mapping_proxy_with_tuple_key_rejected() -> None:
    """Payload MappingProxyType with tuple key must raise typed DomainEventContractError."""
    with pytest.raises(DomainEventContractError):
        _sample_event(payload=MappingProxyType({("a", "b"): "val"}))  # type: ignore[dict-item]


def test_audit_v5_b2_metadata_mapping_proxy_with_set_rejected() -> None:
    """Metadata MappingProxyType with set must be rejected."""
    with pytest.raises(DomainEventContractError):
        _sample_event(metadata=MappingProxyType({"tags": {"a"}}))


def test_audit_v5_b2_metadata_mapping_proxy_with_non_finite_float_rejected() -> None:
    """Metadata MappingProxyType with non-finite float must be rejected."""
    with pytest.raises(DomainEventContractError):
        _sample_event(metadata=MappingProxyType({"val": float("inf")}))


def test_audit_v5_b2_metadata_mapping_proxy_with_non_string_key_rejected() -> None:
    """Metadata MappingProxyType with non-string key must raise typed DomainEventContractError."""
    with pytest.raises(DomainEventContractError):
        _sample_event(metadata=MappingProxyType({123: "val"}))  # type: ignore[dict-item]


def test_audit_v5_b2_payload_mapping_proxy_with_bytes_rejected() -> None:
    """Payload MappingProxyType with bytes must be rejected."""
    with pytest.raises(DomainEventContractError):
        _sample_event(payload=MappingProxyType({"data": b"binary"}))


def test_audit_v5_b2_payload_mapping_proxy_with_bytearray_rejected() -> None:
    """Payload MappingProxyType with bytearray must be rejected."""
    with pytest.raises(DomainEventContractError):
        _sample_event(payload=MappingProxyType({"data": bytearray(b"binary")}))


def test_audit_v5_b2_from_dict_payload_mapping_proxy_with_custom_object_rejected() -> (
    None
):
    """DomainEvent.from_dict with MappingProxyType containing custom object must be rejected."""
    data = _sample_event_dict(payload=MappingProxyType({"opaque": _CustomObject()}))
    with pytest.raises((DomainEventContractError, DomainEventSerializationError)):
        DomainEvent.from_dict(data)


def test_audit_v5_b2_from_dict_metadata_mapping_proxy_with_custom_object_rejected() -> (
    None
):
    """DomainEvent.from_dict with MappingProxyType containing custom object in metadata rejected."""
    data = _sample_event_dict(metadata=MappingProxyType({"opaque": _CustomObject()}))
    with pytest.raises((DomainEventContractError, DomainEventSerializationError)):
        DomainEvent.from_dict(data)


def test_audit_v5_b2_factory_create_event_payload_mapping_proxy_with_custom_object_rejected() -> (
    None
):
    """DomainEventFactory.create_event with MappingProxyType custom object rejected."""
    factory = DomainEventFactory()
    with pytest.raises(DomainEventContractError):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            payload=MappingProxyType({"opaque": _CustomObject()}),
        )


def test_audit_v5_b2_factory_create_event_metadata_mapping_proxy_with_custom_object_rejected() -> (
    None
):
    """DomainEventFactory.create_event with MappingProxyType custom object in metadata rejected."""
    factory = DomainEventFactory()
    with pytest.raises(DomainEventContractError):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            metadata=MappingProxyType({"opaque": _CustomObject()}),
        )


def test_audit_v5_b2_caller_nested_list_mutation_does_not_affect_event() -> None:
    """Mutating caller's nested list after construction does not mutate event.payload."""
    nested = ["safe_value"]
    payload = MappingProxyType({"items": nested})
    event = _sample_event(payload=payload)

    nested.append("mutated_value")
    assert event.payload["items"] == ("safe_value",)
    assert "mutated_value" not in event.payload["items"]


def test_audit_v5_b2_caller_nested_mapping_mutation_does_not_affect_event() -> None:
    """Mutating caller's nested mapping after construction does not mutate event.payload."""
    nested = {"key": "original"}
    payload = MappingProxyType({"sub": nested})
    event = _sample_event(payload=payload)

    nested["key"] = "mutated"
    assert event.payload["sub"]["key"] == "original"


def test_audit_v5_b2_event_nested_state_cannot_be_mutated_through_event_payload() -> (
    None
):
    """Event.payload nested structures must be immutable (MappingProxyType and tuple)."""
    event = _sample_event(payload={"items": ["a", "b"], "sub": {"k": "v"}})
    assert isinstance(event.payload, MappingProxyType)
    assert isinstance(event.payload["items"], tuple)
    assert isinstance(event.payload["sub"], MappingProxyType)

    with pytest.raises(TypeError):
        event.payload["items"] = ("c",)  # type: ignore[index]

    with pytest.raises(TypeError):
        event.payload["sub"]["k"] = "new"  # type: ignore[index]


def test_audit_v5_b2_event_nested_state_cannot_be_mutated_through_event_metadata() -> (
    None
):
    """Event.metadata nested structures must be immutable (MappingProxyType and tuple)."""
    event = _sample_event(metadata={"items": ["a", "b"], "sub": {"k": "v"}})
    assert isinstance(event.metadata, MappingProxyType)
    assert isinstance(event.metadata["items"], tuple)
    assert isinstance(event.metadata["sub"], MappingProxyType)

    with pytest.raises(TypeError):
        event.metadata["items"] = ("c",)  # type: ignore[index]

    with pytest.raises(TypeError):
        event.metadata["sub"]["k"] = "new"  # type: ignore[index]


def test_audit_v5_b2_valid_nested_mapping_proxy_round_trip_remains_json_safe() -> None:
    """Valid nested MappingProxyType round-trip produces exact JSON-safe match."""
    payload = MappingProxyType(
        {"sub": MappingProxyType({"count": 42, "items": ["a", "b"]})}
    )
    event = _sample_event(payload=payload)
    d = event.to_dict()
    json_str = json.dumps(d, allow_nan=False)
    restored = DomainEvent.from_dict(json.loads(json_str))
    assert restored.event_id == event.event_id
    assert restored.payload["sub"]["count"] == 42
    assert restored.payload["sub"]["items"] == ("a", "b")


def test_audit_v5_b2_json_dumps_allow_nan_false_succeeds_for_valid_direct_event() -> (
    None
):
    """json.dumps(event.to_dict(), allow_nan=False) must succeed for direct event."""
    event = _sample_event(
        payload={"score": 0.95, "nested": {"list": [1, 2, "3"]}},
        metadata={"source": "agent"},
    )
    serialized = json.dumps(event.to_dict(), allow_nan=False)
    assert isinstance(serialized, str)


def test_audit_v5_b2_json_dumps_allow_nan_false_succeeds_for_from_dict_event() -> None:
    """json.dumps(event.to_dict(), allow_nan=False) must succeed for from_dict event."""
    data = _sample_event_dict(
        payload={"score": 0.95, "nested": {"list": [1, 2, "3"]}},
        metadata={"source": "agent"},
    )
    event = DomainEvent.from_dict(data)
    serialized = json.dumps(event.to_dict(), allow_nan=False)
    assert isinstance(serialized, str)


def test_audit_v5_b2_json_dumps_allow_nan_false_succeeds_for_factory_event() -> None:
    """json.dumps(event.to_dict(), allow_nan=False) must succeed for factory-created event."""
    factory = DomainEventFactory()
    event = factory.create_event(
        event_type="domain.resolution.started",
        domain_id="domain:project",
        actor="system",
        payload={"score": 0.95, "nested": {"list": [1, 2, "3"]}},
        metadata={"source": "agent"},
    )
    serialized = json.dumps(event.to_dict(), allow_nan=False)
    assert isinstance(serialized, str)


def test_audit_v5_b2_kernel_publication_receives_only_canonical_json_safe_values() -> (
    None
):
    """Kernel publication receives only canonical JSON-safe values and serializes cleanly."""
    publisher = DomainKernelEventPublisher()
    event = _sample_event(
        payload={"key": "value", "items": [1, 2, 3]},
        metadata={"tag": "test"},
    )
    kernel_event = publisher.publish(event)
    assert kernel_event.name == event.event_type
    serialized = json.dumps(kernel_event.payload, allow_nan=False)
    assert isinstance(serialized, str)
    assert json.loads(serialized)["payload"]["items"] == [1, 2, 3]


def test_audit_v5_b2_synthetic_privacy_carrying_object_cannot_cross_kernel_boundary() -> (
    None
):
    """Synthetic privacy-carrying object fails JSON contract and cannot cross Kernel boundary."""
    carrier = _SecretCarrier(_SYNTHETIC_SECRET)
    publisher = DomainKernelEventPublisher()

    with pytest.raises(DomainEventContractError) as exc_info:
        bad_evt = _sample_event(payload=MappingProxyType({"opaque": carrier}))
        publisher.publish(bad_evt)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str
    assert "_SecretCarrier(" not in err_str
    assert len(publisher.emitted_events) == 0


# ===============================================================================
# 2. B2.2 — Unknown-field error non-disclosure regressions
# ===============================================================================


def test_audit_v5_b2_from_dict_non_string_unknown_tuple_key_containing_secret_does_not_leak() -> (
    None
):
    """DomainEvent.from_dict with non-string tuple key containing secret does not leak in error."""
    data = _sample_event_dict(
        extra_fields={("unknown", _SYNTHETIC_SECRET): "bad_value"}
    )
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v5_b2_reference_from_dict_non_string_unknown_tuple_key_containing_secret_does_not_leak() -> (
    None
):
    """DomainEventReference.from_dict with non-string tuple key containing secret does not leak."""
    data = _sample_reference_dict(
        extra_fields={("unknown", _SYNTHETIC_SECRET): "bad_value"}
    )
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEventReference.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v5_b2_from_dict_custom_hashable_key_containing_secret_does_not_leak() -> (
    None
):
    """DomainEvent.from_dict with custom hashable key containing secret does not leak."""
    bad_key = _SecretKey(_SYNTHETIC_SECRET)
    data = _sample_event_dict(extra_fields={bad_key: "bad_value"})
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str
    assert "_SecretKey(" not in err_str
    assert "_SecretKey(" not in details_str


def test_audit_v5_b2_reference_from_dict_custom_hashable_key_containing_secret_does_not_leak() -> (
    None
):
    """DomainEventReference.from_dict with custom hashable key containing secret does not leak."""
    bad_key = _SecretKey(_SYNTHETIC_SECRET)
    data = _sample_reference_dict(extra_fields={bad_key: "bad_value"})
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEventReference.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str
    assert "_SecretKey(" not in err_str
    assert "_SecretKey(" not in details_str


def test_audit_v5_b2_from_dict_unknown_safe_string_key() -> None:
    """DomainEvent.from_dict with safe unknown string key reports unknown fields cleanly."""
    data = _sample_event_dict(extra_fields={"extra_safe_field": "some_value"})
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    assert "extra_safe_field" in err_str
    assert tuple(exc_info.value.details.get("unknown_fields", ())) == (
        "extra_safe_field",
    )


def test_audit_v5_b2_reference_from_dict_unknown_safe_string_key() -> None:
    """DomainEventReference.from_dict with safe unknown string key reports unknown fields cleanly."""
    data = _sample_reference_dict(extra_fields={"extra_safe_field": "some_value"})
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEventReference.from_dict(data)

    err_str = str(exc_info.value)
    assert "extra_safe_field" in err_str
    assert tuple(exc_info.value.details.get("unknown_fields", ())) == (
        "extra_safe_field",
    )


def test_audit_v5_b2_from_dict_unknown_secret_shaped_string_key_does_not_leak() -> None:
    """DomainEvent.from_dict with unknown secret-shaped string key does not leak in error."""
    data = _sample_event_dict(extra_fields={_SYNTHETIC_SECRET: "some_value"})
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v5_b2_reference_from_dict_unknown_secret_shaped_string_key_does_not_leak() -> (
    None
):
    """DomainEventReference.from_dict with unknown secret-shaped string key does not leak."""
    data = _sample_reference_dict(extra_fields={_SYNTHETIC_SECRET: "some_value"})
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEventReference.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


@pytest.mark.parametrize(
    "private_key",
    [
        "system_prompt",
        "developer_prompt",
        "private_key",
        "api_key",
        "session_token",
        "raw_reasoning",
    ],
)
def test_audit_v5_b2_from_dict_unknown_private_marker_string_key_does_not_leak(
    private_key: str,
) -> None:
    """DomainEvent.from_dict with unknown private-marker string key does not leak marker in unknown_fields."""
    data = _sample_event_dict(extra_fields={private_key: "some_value"})
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    details = getattr(exc_info.value, "details", {})
    assert private_key not in details.get("unknown_fields", [])


@pytest.mark.parametrize(
    "private_key",
    [
        "system_prompt",
        "developer_prompt",
        "private_key",
        "api_key",
        "session_token",
        "raw_reasoning",
    ],
)
def test_audit_v5_b2_reference_from_dict_unknown_private_marker_string_key_does_not_leak(
    private_key: str,
) -> None:
    """DomainEventReference.from_dict with unknown private-marker string key does not leak."""
    data = _sample_reference_dict(extra_fields={private_key: "some_value"})
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEventReference.from_dict(data)

    details = getattr(exc_info.value, "details", {})
    assert private_key not in details.get("unknown_fields", [])
