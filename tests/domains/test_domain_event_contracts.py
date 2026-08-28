"""Phase 10.33 — Domain Event Contracts and Serialization Tests.

Tests covering:
- Immutability of DomainEvent and DomainEventReference
- Timezone enforcement on occurred_at
- Non-empty identifier validation
- JSON-safety checks
- Recursive secret-key rejection (payload & metadata)
- Reference-first provenance
- Strict round-trip serialization and deserialization
- Unknown fields fail-closed on deserialization
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainEventContractError,
    DomainEventSerializationError,
)
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.identifiers import DomainId


def _sample_event(
    *,
    event_id: str = "evt-123",
    event_type: str = "domain.resolution.completed",
    schema_version: str = "1.0.0",
    domain_id: DomainId | None = None,
    related_domain_ids: tuple[DomainId, ...] = (),
    actor: str = "user-1",
    session_id: str | None = None,
    occurred_at: datetime | None = None,
    provenance: tuple[DomainEventReference, ...] = (),
    sensitivity: str = "internal",
    permissions: tuple[str, ...] = (),
    correlation_id: str | None = None,
    causation_id: str | None = None,
    payload: dict | None = None,
    metadata: dict | None = None,
) -> DomainEvent:
    now = occurred_at or datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    dom_id = domain_id if domain_id is not None else DomainId(slug="project")
    return DomainEvent(
        event_id=event_id,
        event_type=event_type,
        schema_version=schema_version,
        domain_id=dom_id,
        related_domain_ids=related_domain_ids,
        actor=actor,
        session_id=session_id,
        occurred_at=now,
        provenance=provenance,
        sensitivity=sensitivity,
        permissions=permissions,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload or {},
        metadata=metadata or {},
    )


# 1. Immutability
def test_domain_event_immutability() -> None:
    event = _sample_event(payload={"key": "val"})
    with pytest.raises((AttributeError, TypeError)):
        event.event_id = "new-id"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        event.payload["key"] = "modified"  # type: ignore[index]
    with pytest.raises((AttributeError, TypeError)):
        event.metadata["new_key"] = "bad"  # type: ignore[index]


def test_domain_event_reference_immutability() -> None:
    ref = DomainEventReference(kind="resolution", reference_id="res-1")
    with pytest.raises((AttributeError, TypeError)):
        ref.kind = "other"  # type: ignore[misc]


# 2. Timezone enforcement
def test_occurred_at_naive_datetime_rejected() -> None:
    naive_dt = datetime(2026, 8, 28, 10, 0, 0)  # noqa: DTZ001
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(occurred_at=naive_dt)


# 3. Non-empty identifiers
@pytest.mark.parametrize("empty_val", ["", "   "])
def test_empty_required_fields_rejected(empty_val: str) -> None:
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(event_id=empty_val)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(event_type=empty_val)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(schema_version=empty_val)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(actor=empty_val)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(sensitivity=empty_val)


# 4. JSON-safety
def test_non_json_safe_payload_rejected() -> None:
    class CustomObj:
        pass

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload={"bad": CustomObj()})


def test_infinite_float_rejected() -> None:
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload={"bad": float("inf")})
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload={"bad": float("nan")})


# 5. Recursive secret-key rejection
@pytest.mark.parametrize(
    "secret_key",
    [
        "api_key",
        "apiKey",
        "secret",
        "client_secret",
        "password",
        "user_password",
        "token",
        "access_token",
        "auth_token",
        "private_key",
        "credential",
        "authorization",
        "cookie",
    ],
)
def test_secret_key_rejection_in_payload_and_metadata(secret_key: str) -> None:
    # Top-level payload
    with pytest.raises(DomainContractValidationError):
        _sample_event(payload={secret_key: "val"})

    # Nested payload
    with pytest.raises(DomainContractValidationError):
        _sample_event(payload={"nested": {"sub": {secret_key: "val"}}})

    # List in payload
    with pytest.raises(DomainContractValidationError):
        _sample_event(payload={"items": [{secret_key: "val"}]})

    # Metadata
    with pytest.raises(DomainContractValidationError):
        _sample_event(metadata={secret_key: "val"})


# 6. Provenance references
def test_provenance_references_coercion_and_storage() -> None:
    ref1 = DomainEventReference(
        kind="resolution", reference_id="res-1", domain_id=DomainId(slug="project")
    )
    event = _sample_event(provenance=(ref1,))
    assert len(event.provenance) == 1
    assert event.provenance[0].kind == "resolution"
    assert event.provenance[0].reference_id == "res-1"
    assert event.provenance[0].domain_id == DomainId(slug="project")


# 7. Serialization and Deserialization roundtrip
def test_domain_event_roundtrip_serialization() -> None:
    now = datetime(2026, 8, 28, 14, 30, 0, tzinfo=timezone.utc)
    ref = DomainEventReference(
        kind="composition",
        reference_id="comp-99",
        domain_id=DomainId(slug="project"),
    )
    event = DomainEvent(
        event_id="evt-roundtrip",
        event_type="domain.composition.created",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        related_domain_ids=(DomainId(slug="general"), DomainId(slug="health")),
        actor="agent-x",
        session_id="sess-100",
        occurred_at=now,
        provenance=(ref,),
        sensitivity="confidential",
        permissions=("domain.project.execute", "domain.health.read"),
        correlation_id="corr-99",
        causation_id="caus-88",
        payload={"composition_id": "comp-99", "item_count": 5},
        metadata={"environment": "production"},
    )
    d = event.to_dict()
    restored = DomainEvent.from_dict(d)

    assert restored.event_id == event.event_id
    assert restored.event_type == event.event_type
    assert restored.schema_version == event.schema_version
    assert restored.domain_id == event.domain_id
    assert restored.related_domain_ids == event.related_domain_ids
    assert restored.actor == event.actor
    assert restored.session_id == event.session_id
    assert restored.occurred_at == event.occurred_at
    assert restored.provenance == event.provenance
    assert restored.sensitivity == event.sensitivity
    assert restored.permissions == event.permissions
    assert restored.correlation_id == event.correlation_id
    assert restored.causation_id == event.causation_id
    assert restored.payload == event.payload
    assert restored.metadata == event.metadata


# 8. Unknown fields fail closed
def test_from_dict_unknown_fields_rejected() -> None:
    event = _sample_event()
    d = event.to_dict()
    d["extra_unknown_field"] = "bad"
    with pytest.raises(DomainEventSerializationError):
        DomainEvent.from_dict(d)


def test_reference_from_dict_unknown_fields_rejected() -> None:
    ref = DomainEventReference(kind="res", reference_id="1")
    d = ref.to_dict()
    d["rogue_key"] = 123
    with pytest.raises(DomainEventSerializationError):
        DomainEventReference.from_dict(d)
