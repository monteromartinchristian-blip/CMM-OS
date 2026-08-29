"""Phase 10.33 independent audit V4 regression tests.

These tests encode findings for B2 from the independent audit V4
of Phase 10.33 Domain Events (docs/audits/phase-10.33-independent-audit-v4.md).

Strict TDD: Written to observe RED against audited HEAD before minimal GREEN remediation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainEventContractError,
    DomainEventSerializationError,
)
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.event_factory import DomainEventFactory
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.identifiers import DomainId

_SYNTHETIC_SECRET = "sk-" + "A" * 40
_SYNTHETIC_SECRET_SLUG = "sk-aaaaaaaaaaaa"


def _sample_event(
    *,
    event_id: str = "evt-v4-100",
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


# ═══════════════════════════════════════════════════════════════════════════════
# 1. B2.1 — DomainId privacy bypass remediation tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v4_b2_direct_domain_event_rejects_secret_slug() -> None:
    """Direct DomainEvent construction must reject secret-shaped domain_id."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(domain_id=DomainId(slug=_SYNTHETIC_SECRET_SLUG))


@pytest.mark.parametrize(
    "private_slug",
    [
        "system-prompt",
        "raw-prompt",
        "chain-of-thought",
        "developer-prompt",
        "provider-response",
        "tool-arguments",
    ],
)
def test_audit_v4_b2_direct_domain_event_rejects_private_marker_slug(
    private_slug: str,
) -> None:
    """Direct DomainEvent construction must reject private-marker domain_id."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(domain_id=DomainId(slug=private_slug))


def test_audit_v4_b2_direct_domain_event_rejects_secret_in_related_domain_ids() -> None:
    """Direct DomainEvent construction must reject secret-shaped slug in related_domain_ids."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(
            domain_id=DomainId(slug="project"),
            related_domain_ids=(DomainId(slug=_SYNTHETIC_SECRET_SLUG),),
        )


def test_audit_v4_b2_direct_domain_event_rejects_private_marker_in_related_domain_ids() -> (
    None
):
    """Direct DomainEvent construction must reject private-marker slug in related_domain_ids."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(
            domain_id=DomainId(slug="project"),
            related_domain_ids=(DomainId(slug="system-prompt"),),
        )


def test_audit_v4_b2_from_dict_rejects_secret_domain_id() -> None:
    """DomainEvent.from_dict must reject secret-shaped domain_id."""
    data = {
        "event_id": "evt-v4-fromdict-1",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": _SYNTHETIC_SECRET_SLUG},
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


def test_audit_v4_b2_from_dict_rejects_private_marker_domain_id() -> None:
    """DomainEvent.from_dict must reject private-marker domain_id."""
    data = {
        "event_id": "evt-v4-fromdict-2",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "system-prompt"},
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


def test_audit_v4_b2_from_dict_rejects_secret_in_related_domain_ids() -> None:
    """DomainEvent.from_dict must reject secret-shaped slug in related_domain_ids."""
    data = {
        "event_id": "evt-v4-fromdict-3",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "related_domain_ids": [{"slug": _SYNTHETIC_SECRET_SLUG}],
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


def test_audit_v4_b2_from_dict_rejects_private_marker_in_related_domain_ids() -> None:
    """DomainEvent.from_dict must reject private-marker slug in related_domain_ids."""
    data = {
        "event_id": "evt-v4-fromdict-4",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "related_domain_ids": [{"slug": "system-prompt"}],
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


def test_audit_v4_b2_reference_direct_rejects_secret_domain_id() -> None:
    """DomainEventReference direct construction must reject secret-shaped domain_id."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(
            kind="resolution",
            reference_id="res-1",
            domain_id=DomainId(slug=_SYNTHETIC_SECRET_SLUG),
        )


def test_audit_v4_b2_reference_direct_rejects_private_marker_domain_id() -> None:
    """DomainEventReference direct construction must reject private-marker domain_id."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(
            kind="resolution",
            reference_id="res-1",
            domain_id=DomainId(slug="system-prompt"),
        )


def test_audit_v4_b2_reference_from_dict_rejects_secret_domain_id() -> None:
    """DomainEventReference.from_dict must reject secret-shaped domain_id."""
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
                "reference_id": "res-1",
                "domain_id": {"slug": _SYNTHETIC_SECRET_SLUG},
            }
        )


def test_audit_v4_b2_reference_from_dict_rejects_private_marker_domain_id() -> None:
    """DomainEventReference.from_dict must reject private-marker domain_id."""
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
                "reference_id": "res-1",
                "domain_id": {"slug": "system-prompt"},
            }
        )


def test_audit_v4_b2_factory_create_event_rejects_secret_domain_id() -> None:
    """DomainEventFactory.create_event must reject secret-shaped domain_id."""
    factory = DomainEventFactory()
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id=_SYNTHETIC_SECRET_SLUG,
            actor="system",
        )
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id=DomainId(slug=_SYNTHETIC_SECRET_SLUG),
            actor="system",
        )


def test_audit_v4_b2_factory_create_event_rejects_private_marker_domain_id() -> None:
    """DomainEventFactory.create_event must reject private-marker domain_id."""
    factory = DomainEventFactory()
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="system-prompt",
            actor="system",
        )


def test_audit_v4_b2_factory_create_event_rejects_secret_in_related_domain_ids() -> (
    None
):
    """DomainEventFactory.create_event must reject secret in related_domain_ids."""
    factory = DomainEventFactory()
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            related_domain_ids=[_SYNTHETIC_SECRET_SLUG],
            actor="system",
        )


def test_audit_v4_b2_factory_create_event_rejects_private_marker_in_related_domain_ids() -> (
    None
):
    """DomainEventFactory.create_event must reject private-marker in related_domain_ids."""
    factory = DomainEventFactory()
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            related_domain_ids=["system-prompt"],
            actor="system",
        )


@pytest.mark.parametrize(
    "canonical_slug",
    [
        "health",
        "project",
        "life-plan",
        "oppositions",
        "university",
        "languages",
        "sport",
        "parenthood",
        "general",
        "relationships",
        "reflection",
        "concerns",
    ],
)
def test_audit_v4_b2_valid_canonical_domain_ids_preserved(canonical_slug: str) -> None:
    """Legitimate canonical domain slugs pass all validation paths."""
    dom = DomainId(slug=canonical_slug)
    evt = _sample_event(domain_id=dom, related_domain_ids=(dom,))
    assert evt.domain_id.slug == canonical_slug

    ref = DomainEventReference(kind="resolution", reference_id="res-1", domain_id=dom)
    assert ref.domain_id == dom

    factory = DomainEventFactory()
    f_evt = factory.create_event(
        event_type="domain.resolution.started",
        domain_id=dom,
        related_domain_ids=[dom],
        actor="system",
        provenance=[ref],
    )
    assert f_evt.domain_id == dom


# ═══════════════════════════════════════════════════════════════════════════════
# 2. B2.2 — Validation-error non-disclosure for malformed values
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v4_b2_from_dict_event_id_malformed_list_does_not_leak_secret() -> None:
    """DomainEvent.from_dict with malformed list containing secret does not leak secret in error."""
    data = {
        "event_id": [_SYNTHETIC_SECRET],
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_from_dict_session_id_malformed_list_does_not_leak_secret() -> None:
    """DomainEvent.from_dict with malformed session_id list does not leak secret in error."""
    data = {
        "event_id": "evt-v4-valid-1",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "session_id": [_SYNTHETIC_SECRET],
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_from_dict_correlation_id_malformed_dict_does_not_leak_secret() -> (
    None
):
    """DomainEvent.from_dict with malformed correlation_id dict does not leak secret in error."""
    data = {
        "event_id": "evt-v4-valid-2",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "correlation_id": {"x": _SYNTHETIC_SECRET},
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_from_dict_causation_id_malformed_list_does_not_leak_secret() -> (
    None
):
    """DomainEvent.from_dict with malformed causation_id list does not leak secret in error."""
    data = {
        "event_id": "evt-v4-valid-3",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "causation_id": [_SYNTHETIC_SECRET],
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_reference_from_dict_malformed_reference_id_does_not_leak_secret() -> (
    None
):
    """DomainEventReference.from_dict with malformed reference_id list does not leak secret in error."""
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEventReference.from_dict(
            {"kind": "resolution", "reference_id": [_SYNTHETIC_SECRET]}
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_reference_from_dict_malformed_kind_does_not_leak_secret() -> None:
    """DomainEventReference.from_dict with malformed kind list does not leak secret in error."""
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEventReference.from_dict(
            {"kind": [_SYNTHETIC_SECRET], "reference_id": "ref-1"}
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_from_dict_occurred_at_invalid_string_does_not_leak_secret() -> (
    None
):
    """DomainEvent.from_dict with invalid occurred_at datetime containing secret does not leak."""
    data = {
        "event_id": "evt-v4-valid-4",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "occurred_at": f"not-a-datetime-{_SYNTHETIC_SECRET}",
        "sensitivity": "internal",
    }
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_factory_event_id_malformed_list_does_not_leak_secret() -> None:
    """DomainEventFactory.create_event with malformed event_id list does not leak secret in error."""
    factory = DomainEventFactory()
    with pytest.raises(DomainEventContractError) as exc_info:
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            event_id=[_SYNTHETIC_SECRET],  # type: ignore[arg-type]
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_factory_session_id_malformed_list_does_not_leak_secret() -> None:
    """DomainEventFactory.create_event with malformed session_id list does not leak secret in error."""
    factory = DomainEventFactory()
    with pytest.raises(DomainEventContractError) as exc_info:
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            session_id=[_SYNTHETIC_SECRET],  # type: ignore[arg-type]
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_factory_correlation_id_malformed_dict_does_not_leak_secret() -> (
    None
):
    """DomainEventFactory.create_event with malformed correlation_id dict does not leak secret in error."""
    factory = DomainEventFactory()
    with pytest.raises(DomainEventContractError) as exc_info:
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            correlation_id={"x": _SYNTHETIC_SECRET},  # type: ignore[arg-type]
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_factory_causation_id_malformed_list_does_not_leak_secret() -> None:
    """DomainEventFactory.create_event with malformed causation_id list does not leak secret in error."""
    factory = DomainEventFactory()
    with pytest.raises(DomainEventContractError) as exc_info:
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            causation_id=[_SYNTHETIC_SECRET],  # type: ignore[arg-type]
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_from_dict_invalid_provenance_does_not_leak_secret() -> None:
    """DomainEvent.from_dict with invalid provenance containing secret does not leak in error."""
    data = {
        "event_id": "evt-v4-valid-5",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
        "provenance": [{"kind": "resolution", "reference_id": [_SYNTHETIC_SECRET]}],
    }
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_from_dict_invalid_domain_id_container_does_not_leak_secret() -> (
    None
):
    """DomainEvent.from_dict with invalid domain_id container containing secret does not leak."""
    data = {
        "event_id": "evt-v4-valid-6",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": [_SYNTHETIC_SECRET],
        "actor": "system",
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_from_dict_invalid_related_domain_ids_does_not_leak_secret() -> (
    None
):
    """DomainEvent.from_dict with invalid related_domain_ids item containing secret does not leak."""
    data = {
        "event_id": "evt-v4-valid-7",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "related_domain_ids": [[_SYNTHETIC_SECRET]],
        "actor": "system",
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_from_dict_invalid_permissions_does_not_leak_secret() -> None:
    """DomainEvent.from_dict with invalid permissions item containing secret does not leak."""
    data = {
        "event_id": "evt-v4-valid-8",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "permissions": [[_SYNTHETIC_SECRET]],
        "actor": "system",
        "occurred_at": "2026-08-29T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(DomainEventSerializationError) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v4_b2_invalid_payload_json_safe_type_does_not_leak_secret() -> None:
    """Payload non-JSON-safe value whose repr would contain secret does not leak in error message."""

    class BadReprSecret:
        def __repr__(self) -> str:
            return f"BadReprObject({_SYNTHETIC_SECRET})"

    with pytest.raises(DomainEventContractError) as exc_info:
        _sample_event(payload={"bad": BadReprSecret()})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Kernel Publication Boundary Privacy Gate
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v4_kernel_publication_boundary_fails_closed_on_secret_domain_id() -> (
    None
):
    """DomainKernelEventPublisher cannot receive or emit any event with secret or private domain ID."""
    publisher = DomainKernelEventPublisher()

    # Secret domain_id
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt = _sample_event(domain_id=DomainId(slug=_SYNTHETIC_SECRET_SLUG))
        publisher.publish(bad_evt)

    # Private-marker domain_id
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt2 = _sample_event(domain_id=DomainId(slug="system-prompt"))
        publisher.publish(bad_evt2)

    # Secret in related_domain_ids
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt3 = _sample_event(
            domain_id=DomainId(slug="project"),
            related_domain_ids=(DomainId(slug=_SYNTHETIC_SECRET_SLUG),),
        )
        publisher.publish(bad_evt3)

    # Secret in provenance domain_id
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_ref = DomainEventReference(
            kind="resolution",
            reference_id="res-1",
            domain_id=DomainId(slug=_SYNTHETIC_SECRET_SLUG),
        )
        bad_evt4 = _sample_event(
            domain_id=DomainId(slug="project"),
            provenance=(bad_ref,),
        )
        publisher.publish(bad_evt4)

    assert len(publisher.emitted_events) == 0
