"""Phase 10.33 independent audit V6 regression tests.

These tests encode findings for B2 from the independent audit V6
of Phase 10.33 Domain Events (docs/audits/phase-10.33-independent-audit-v6.md).

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

# Synthetic credential formats for B2.2
SYNTHETIC_CREDENTIALS = [
    ("gh_classic_pat", "ghp_" + "1" * 36),
    ("gh_fine_grained_pat", "github_pat_" + "1" * 82),
    ("aws_access_key", "AKIA" + "1234567890ABCDEF"),
    ("google_api_key", "AIza" + "SyD1234567890abcdefghijklmnopqrstuv"),
    ("slack_bot_token", "xoxb-123456789012-1234567890123-abcdef123456"),
    ("slack_user_token", "xoxp-123456789012-1234567890123-abcdef123456"),
    ("slack_app_token", "xoxa-123456789012-1234567890123-abcdef123456"),
    ("slack_refresh_token", "xoxr-123456789012-1234567890123-abcdef123456"),
]


class _CustomObject:
    """Arbitrary non-JSON object."""

    def __init__(self, value: Any = "custom") -> None:
        self.value = value


def _sample_event(
    *,
    event_id: str = "evt-v6-100",
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
        "event_id": "evt-v6-valid-1",
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


# ===============================================================================
# 1. B2.1 — Privacy validation ordering regressions
# ===============================================================================


def test_audit_v6_b2_payload_top_level_secret_key_with_custom_object_does_not_leak_secret() -> (
    None
):
    """Payload top-level secret key with non-JSON custom object must not leak secret in error."""
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError)
    ) as exc_info:
        _sample_event(payload={_SYNTHETIC_SECRET: _CustomObject()})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v6_b2_payload_top_level_secret_key_with_inf_does_not_leak_secret() -> (
    None
):
    """Payload top-level secret key with non-finite float must not leak secret in error."""
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError)
    ) as exc_info:
        _sample_event(payload={_SYNTHETIC_SECRET: float("inf")})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v6_b2_payload_nested_secret_key_with_custom_object_does_not_leak_secret() -> (
    None
):
    """Payload deeply nested secret key with non-JSON object must not leak secret in error."""
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError)
    ) as exc_info:
        _sample_event(
            payload={
                "safe_parent": {"nested_level": {_SYNTHETIC_SECRET: _CustomObject()}}
            }
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v6_b2_metadata_top_level_secret_key_with_custom_object_does_not_leak_secret() -> (
    None
):
    """Metadata top-level secret key with non-JSON custom object must not leak secret in error."""
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError)
    ) as exc_info:
        _sample_event(metadata={_SYNTHETIC_SECRET: _CustomObject()})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v6_b2_metadata_nested_secret_key_with_inf_does_not_leak_secret() -> None:
    """Metadata deeply nested secret key with non-finite float must not leak secret in error."""
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError)
    ) as exc_info:
        _sample_event(
            metadata={"config": {"settings": {_SYNTHETIC_SECRET: float("inf")}}}
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v6_b2_from_dict_payload_secret_key_with_custom_object_does_not_leak_secret() -> (
    None
):
    """DomainEvent.from_dict with secret key and custom object must not leak secret in error."""
    data = _sample_event_dict(payload={_SYNTHETIC_SECRET: _CustomObject()})
    with pytest.raises(
        (
            DomainEventContractError,
            DomainEventSerializationError,
            DomainContractValidationError,
        )
    ) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v6_b2_factory_create_event_payload_secret_key_with_custom_object_does_not_leak_secret() -> (
    None
):
    """DomainEventFactory.create_event with secret key and custom object does not leak."""
    factory = DomainEventFactory()
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError)
    ) as exc_info:
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            payload={_SYNTHETIC_SECRET: _CustomObject()},
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert _SYNTHETIC_SECRET not in err_str
    assert _SYNTHETIC_SECRET not in details_str


def test_audit_v6_b2_payload_top_level_private_marker_key_with_custom_object_does_not_leak_key() -> (
    None
):
    """Payload top-level private marker key with custom object does not leak marker into field path."""
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError)
    ) as exc_info:
        _sample_event(payload={"system_prompt": _CustomObject()})

    err_str = str(exc_info.value)
    assert "payload.system_prompt" not in err_str


def test_audit_v6_b2_payload_safe_key_diagnostic_preserved() -> None:
    """Safe mapping keys preserve standard diagnostic field-path information."""
    with pytest.raises(DomainEventContractError) as exc_info:
        _sample_event(payload={"safe_field": _CustomObject()})

    err_str = str(exc_info.value)
    assert "payload.safe_field" in err_str


# ===============================================================================
# 2. B2.2 — High-confidence credential format regressions
# ===============================================================================


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_payload_nested_string_credential_rejected(
    family: str, credential: str
) -> None:
    """Payload nested string containing high-confidence credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(payload={"api_info": {"token": credential}})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_metadata_nested_string_credential_rejected(
    family: str, credential: str
) -> None:
    """Metadata nested string containing high-confidence credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(metadata={"config": {"key": credential}})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_event_id_credential_rejected(family: str, credential: str) -> None:
    """DomainEvent event_id containing high-confidence credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(event_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_reference_id_credential_rejected(
    family: str, credential: str
) -> None:
    """DomainEventReference reference_id containing credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        DomainEventReference(kind="resolution", reference_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_reference_from_dict_credential_rejected(
    family: str, credential: str
) -> None:
    """DomainEventReference.from_dict containing credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventSerializationError)
    ) as exc_info:
        DomainEventReference.from_dict(
            {"kind": "resolution", "reference_id": credential}
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_session_id_credential_rejected(
    family: str, credential: str
) -> None:
    """DomainEvent session_id containing credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(session_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_correlation_id_credential_rejected(
    family: str, credential: str
) -> None:
    """DomainEvent correlation_id containing credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(correlation_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_causation_id_credential_rejected(
    family: str, credential: str
) -> None:
    """DomainEvent causation_id containing credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(causation_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_actor_credential_rejected(family: str, credential: str) -> None:
    """DomainEvent actor containing credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(actor=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_permissions_credential_rejected(
    family: str, credential: str
) -> None:
    """DomainEvent permissions item containing credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(permissions=(credential,))

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_from_dict_credential_in_payload_rejected(
    family: str, credential: str
) -> None:
    """DomainEvent.from_dict with credential in payload must fail closed."""
    data = _sample_event_dict(payload={"token": credential})
    with pytest.raises(
        (
            DomainContractValidationError,
            DomainEventSerializationError,
            DomainEventContractError,
        )
    ) as exc_info:
        DomainEvent.from_dict(data)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_factory_create_event_credential_rejected(
    family: str, credential: str
) -> None:
    """DomainEventFactory.create_event with credential in payload must fail closed."""
    factory = DomainEventFactory()
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            payload={"token": credential},
        )

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


# ===============================================================================
# 3. Kernel Publication Boundary Gates for Credential Formats
# ===============================================================================


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v6_b2_kernel_boundary_rejects_all_credential_families(
    family: str, credential: str
) -> None:
    """DomainKernelEventPublisher publication fails before emission for each credential family."""
    publisher = DomainKernelEventPublisher()

    # Attempt to construct and publish event with credential in payload
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt = _sample_event(payload={"credential_key": credential})
        publisher.publish(bad_evt)

    assert len(publisher.emitted_events) == 0
