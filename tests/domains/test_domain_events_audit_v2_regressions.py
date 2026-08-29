"""Phase 10.33 independent audit V2 regression tests.

These tests encode findings B2, M2, M5, and m2 from the independent audit V2
of Phase 10.33 Domain Events (docs/audits/phase-10.33-independent-audit-v2.md).

Strict TDD: Written to observe RED against audited HEAD before minimal GREEN remediation.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReference,
    DomainConflictResolutionPolicy,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
)
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainEventContractError,
    DomainEventPublicationError,
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
from cmm.domains.lifecycle_bridge import DomainLifecycleEventBridge
from kernel.events.event import Event


def _sample_event(
    *,
    event_id: str = "evt-v2-123",
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
# Finding B2 — BLOCKER: Event-wide privacy validation and secret-value coverage
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v2_b2_rejects_secret_in_top_level_actor() -> None:
    """actor containing secret values (e.g. sk-...) must be rejected."""
    synthetic_key = "sk-" + "a" * 40
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(actor=synthetic_key)


def test_audit_v2_b2_rejects_secret_in_top_level_permissions() -> None:
    """permissions containing secret values (e.g. Bearer ...) must be rejected."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(permissions=("Bearer abcdefghijklmnop",))


def test_audit_v2_b2_rejects_forbidden_marker_in_event_reference_kind() -> None:
    """DomainEventReference with forbidden private marker kind (e.g. system_prompt) must be rejected."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(
            kind="system_prompt",
            reference_id="ref-1",
        )


def test_audit_v2_b2_rejects_secret_in_event_reference_id() -> None:
    """DomainEventReference with secret-shaped reference_id must be rejected."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(
            kind="resolution",
            reference_id="Authorization: Bearer SECRET1234567890",
        )


@pytest.mark.parametrize(
    "secret_payload",
    [
        {"error": "password=hunter2"},
        {"error": "password: mypassword123"},
        {"error": "secret=supersecret"},
        {"error": "secret: supersecret"},
        {"error": "credential=mysecret"},
        {"error": "credential: mysecret"},
        {"error": "cookie: abcdefghijklmnop"},
        {"error": "cookie=abcdefghijklmnop"},
        {"error": "session_token=abcdefghijklmnop"},
        {"error": "session-token=abcdefghijklmnop"},
        {"error": "access_token=abcdefghijklmnop"},
        {"error": "access-token=abcdefghijklmnop"},
        {"error": "refresh_token=abcdefghijklmnop"},
        {"error": "refresh-token=abcdefghijklmnop"},
    ],
)
def test_audit_v2_b2_rejects_secret_patterns_in_payload(
    secret_payload: dict[str, str],
) -> None:
    """Payload containing newly covered secret patterns must be rejected."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload=secret_payload)


@pytest.mark.parametrize(
    "raw_error",
    [
        "Error password=hunter2 occurred",
        "Failed with secret=supersecret",
        "Invalid credential=mysecret",
        "Set-Cookie: cookie: abcdefghijklmnop",
        "Auth failure: session_token=abcdef1234567890",
        "Token expired: access_token=abcdef1234567890",
        "Token expired: refresh-token=abcdef1234567890",
    ],
)
def test_audit_v2_b2_failure_adapters_sanitize_expanded_secret_patterns(
    raw_error: str,
) -> None:
    """Failure adapters must sanitize or safely represent expanded secret patterns."""
    evt_op = adapt_operation_failed(
        operation_id="op-v2",
        domain_id="domain:project",
        error=raw_error,
    )
    for val in evt_op.payload.values():
        val_str = str(val)
        assert "hunter2" not in val_str
        assert "supersecret" not in val_str
        assert "mysecret" not in val_str
        assert "abcdefghijklmnop" not in val_str
        assert "abcdef1234567890" not in val_str

    evt_exec = adapt_execution_failed(
        execution_id="exec-v2",
        domain_id="domain:project",
        error=raw_error,
    )
    for val in evt_exec.payload.values():
        val_str = str(val)
        assert "hunter2" not in val_str
        assert "supersecret" not in val_str
        assert "mysecret" not in val_str
        assert "abcdefghijklmnop" not in val_str
        assert "abcdef1234567890" not in val_str


def test_audit_v2_b2_publisher_does_not_leak_listener_exception_secret() -> None:
    """DomainEventPublicationError must NOT embed raw listener exception text containing secrets."""
    secret_listener_msg = (
        "Database auth error with Authorization: Bearer SECRET_LISTENER_TOKEN_123"
    )

    def leaking_listener(evt: Event) -> None:
        raise RuntimeError(secret_listener_msg)

    publisher = DomainKernelEventPublisher(event_listener=leaking_listener)
    event = _sample_event()

    with pytest.raises(DomainEventPublicationError) as exc_info:
        publisher.publish(event)

    pub_error_str = str(exc_info.value)
    assert "SECRET_LISTENER_TOKEN_123" not in pub_error_str
    assert "Authorization: Bearer" not in pub_error_str


# ═══════════════════════════════════════════════════════════════════════════════
# Finding M2 — MAJOR: Strict construction and deserialization for optional IDs
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("invalid_id", [123, object(), ["list"], {"dict": 1}, True])
def test_audit_v2_m2_direct_construction_rejects_invalid_optional_identifiers(
    invalid_id: Any,
) -> None:
    """Direct DomainEvent construction must reject non-string session_id, correlation_id, causation_id."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        _sample_event(session_id=invalid_id)

    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        _sample_event(correlation_id=invalid_id)

    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        _sample_event(causation_id=invalid_id)


@pytest.mark.parametrize("invalid_id", [123, object(), ["list"], {"dict": 1}, True])
def test_audit_v2_m2_from_dict_rejects_invalid_optional_identifiers(
    invalid_id: Any,
) -> None:
    """DomainEvent.from_dict must reject non-string session_id, correlation_id, causation_id."""
    base_dict = {
        "event_id": "evt-123",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
    }

    with pytest.raises(
        (DomainEventSerializationError, DomainEventContractError, TypeError)
    ):
        DomainEvent.from_dict({**base_dict, "session_id": invalid_id})

    with pytest.raises(
        (DomainEventSerializationError, DomainEventContractError, TypeError)
    ):
        DomainEvent.from_dict({**base_dict, "correlation_id": invalid_id})

    with pytest.raises(
        (DomainEventSerializationError, DomainEventContractError, TypeError)
    ):
        DomainEvent.from_dict({**base_dict, "causation_id": invalid_id})


@pytest.mark.parametrize("invalid_id", [123, object(), ["list"], {"dict": 1}, True])
def test_audit_v2_m2_factory_rejects_invalid_optional_identifiers(
    invalid_id: Any,
) -> None:
    """DomainEventFactory.create_event must reject non-string session_id, correlation_id, causation_id."""
    factory = DomainEventFactory()
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError, TypeError)
    ):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            session_id=invalid_id,
        )

    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError, TypeError)
    ):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            correlation_id=invalid_id,
        )

    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError, TypeError)
    ):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            causation_id=invalid_id,
        )


def test_audit_v2_m2_valid_events_are_strictly_json_serializable() -> None:
    """Every validly constructed event must successfully serialize with json.dumps(event.to_dict())."""
    event = _sample_event(
        session_id="sess-1",
        correlation_id="corr-1",
        causation_id="cause-1",
        permissions=("read", "write"),
        payload={
            "key": "value",
            "count": 42,
            "ratio": 3.14,
            "flag": True,
            "empty": None,
        },
        metadata={"tag": "audit_v2"},
    )
    serialized = json.dumps(event.to_dict())
    assert isinstance(serialized, str)
    deserialized = json.loads(serialized)
    assert deserialized["session_id"] == "sess-1"
    assert deserialized["correlation_id"] == "corr-1"
    assert deserialized["causation_id"] == "cause-1"


# ═══════════════════════════════════════════════════════════════════════════════
# Finding M5 — MAJOR: Conflict lifecycle bridge call-around with real resolver
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v2_m5_lifecycle_bridge_call_around_with_real_resolver() -> None:
    """DomainLifecycleEventBridge.resolve_conflict_with_events() executes with real DomainConflictResolver."""
    published_events: list[Event] = []
    publisher = DomainKernelEventPublisher(event_listener=published_events.append)
    bridge = DomainLifecycleEventBridge(publisher=publisher)
    real_resolver = DomainConflictResolver()

    # Create a conflict case that will resolve under PRIMARY_DOMAIN_PRECEDENCE when primary_domain is set
    ref1 = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-primary",
        domain_id=DomainId(slug="project"),
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    ref2 = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-secondary",
        domain_id=DomainId(slug="general"),
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.UNCLASSIFIED,
    )
    case = DomainConflictCase(
        id="case-callaround-1",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        kind=DomainConflictKind.RECOMMENDATION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
    )

    resolution = bridge.resolve_conflict_with_events(
        resolver=real_resolver,
        case=case,
        primary_domain="domain:project",
    )

    # Verify real resolution succeeded
    assert resolution.status == DomainConflictStatus.RESOLVED
    assert resolution.can_proceed is True
    assert resolution.winning_reference_ids == ("ref-primary",)

    # Verify event publication sequence:
    # 1. domain.conflict.detected
    # 2. domain.conflict.resolved
    assert len(published_events) == 2
    assert published_events[0].name == "domain.conflict.detected"
    assert published_events[0].payload["payload"]["conflict_id"] == "case-callaround-1"
    assert published_events[1].name == "domain.conflict.resolved"
    assert published_events[1].payload["payload"]["conflict_id"] == "case-callaround-1"
    assert published_events[1].payload["payload"]["winning_reference_ids"] == [
        "ref-primary"
    ]


def test_audit_v2_m5_primary_domain_materially_affects_resolution_and_is_propagated() -> (
    None
):
    """Primary domain passed to bridge must reach DomainConflictResolver and determine winner."""
    published_events: list[Event] = []
    publisher = DomainKernelEventPublisher(event_listener=published_events.append)
    bridge = DomainLifecycleEventBridge(publisher=publisher)
    real_resolver = DomainConflictResolver()

    ref_health = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-health",
        domain_id=DomainId(slug="health"),
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    ref_project = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-project",
        domain_id=DomainId(slug="project"),
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-primary-test",
        domains=(DomainId(slug="health"), DomainId(slug="project")),
        kind=DomainConflictKind.RECOMMENDATION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_health, ref_project),
    )

    # When health is primary domain, health reference must win
    res_health = bridge.resolve_conflict_with_events(
        resolver=real_resolver,
        case=case,
        primary_domain=DomainId(slug="health"),
    )
    assert res_health.winning_reference_ids == ("ref-health",)


def test_audit_v2_m5_unresolved_or_non_proceeding_conflict_does_not_emit_resolved_event() -> (
    None
):
    """When resolver returns an unresolved status, domain.conflict.resolved must NOT be emitted."""
    published_events: list[Event] = []
    publisher = DomainKernelEventPublisher(event_listener=published_events.append)
    bridge = DomainLifecycleEventBridge(publisher=publisher)
    real_resolver = DomainConflictResolver()

    # Equal unclassified references with no decisive authority → MAINTAIN_CONFLICT or unresolved
    ref_a = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-a",
        domain_id=DomainId(slug="project"),
        severity=DomainConflictSeverity.BLOCKING,
        authority_kind=DomainConflictAuthority.UNCLASSIFIED,
        blocking=True,
    )
    ref_b = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-b",
        domain_id=DomainId(slug="general"),
        severity=DomainConflictSeverity.BLOCKING,
        authority_kind=DomainConflictAuthority.UNCLASSIFIED,
        blocking=True,
    )
    case = DomainConflictCase(
        id="case-unresolved-1",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        kind=DomainConflictKind.RECOMMENDATION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_a, ref_b),
        blocking=True,
    )

    policy = DomainConflictResolutionPolicy()
    resolution = bridge.resolve_conflict_with_events(
        resolver=real_resolver,
        case=case,
        primary_domain="domain:project",
        policy=policy,
    )

    assert (
        resolution.status != DomainConflictStatus.RESOLVED
        or resolution.can_proceed is False
    )
    # Only domain.conflict.detected was emitted; domain.conflict.resolved was NOT emitted
    assert len(published_events) == 1
    assert published_events[0].name == "domain.conflict.detected"


# ═══════════════════════════════════════════════════════════════════════════════
# Finding m2 — MINOR: Reject unordered set inputs for serialized sequences
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v2_m2_rejects_unordered_sets_for_related_domain_ids() -> None:
    """Direct construction, factory, and from_dict must reject set/frozenset for related_domain_ids."""
    domain_set = {
        DomainId(slug="project"),
        DomainId(slug="health"),
        DomainId(slug="university"),
    }

    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        _sample_event(related_domain_ids=domain_set)

    factory = DomainEventFactory()
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError, TypeError)
    ):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            related_domain_ids=domain_set,  # type: ignore[arg-type]
        )


def test_audit_v2_m2_rejects_unordered_sets_for_permissions() -> None:
    """Direct construction and factory must reject set/frozenset for permissions."""
    perm_set = {"read", "write", "admin"}

    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        _sample_event(permissions=perm_set)  # type: ignore[arg-type]

    factory = DomainEventFactory()
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError, TypeError)
    ):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            permissions=perm_set,  # type: ignore[arg-type]
        )


def test_audit_v2_m2_deterministic_sequence_ordering_preserved() -> None:
    """Ordered sequences (tuples, lists) preserve deterministic ordering in event serialization."""
    ordered_domains = (
        DomainId(slug="project"),
        DomainId(slug="health"),
        DomainId(slug="university"),
    )
    evt = _sample_event(related_domain_ids=ordered_domains)
    serialized = evt.to_dict()
    slugs = [d["slug"] for d in serialized["related_domain_ids"]]
    assert slugs == ["project", "health", "university"]
