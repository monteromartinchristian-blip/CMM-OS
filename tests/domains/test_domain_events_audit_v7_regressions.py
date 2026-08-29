"""Phase 10.33 independent audit V7 regression tests.

These tests encode findings from the independent audit V7
of Phase 10.33 Domain Events (docs/audits/phase-10.33-independent-audit-v7.md).

Strict TDD: Written to observe RED against audited HEAD before minimal GREEN remediation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.domains.credential_policy import (
    HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES,
    CredentialSignature,
    contains_high_confidence_credential,
)
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainEventContractError,
    DomainEventSerializationError,
)
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.event_factory import DomainEventFactory
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.identifiers import DomainId

# Synthetic credential formats for V7 remediation
SYNTHETIC_CREDENTIALS = [
    # V6 families (preserved)
    ("gh_classic_pat", "ghp_" + "1" * 36),
    ("gh_fine_grained_pat", "github_pat_" + "1" * 82),
    ("aws_access_key", "AKIA" + "1234567890ABCDEF"),
    ("google_api_key", "AIza" + "SyD1234567890abcdefghijklmnopqrstuv"),
    ("slack_bot_token", "xoxb-123456789012-1234567890123-abcdef123456"),
    ("slack_user_token", "xoxp-123456789012-1234567890123-abcdef123456"),
    ("slack_app_token", "xoxa-123456789012-1234567890123-abcdef123456"),
    ("slack_refresh_token", "xoxr-123456789012-1234567890123-abcdef123456"),
    ("openai_key", "sk-" + "A" * 40),
    # V7 families required by Audit V7
    ("gitlab_pat", "glpat-" + "a" * 20),
    ("npm_token", "npm_" + "a" * 36),
    ("huggingface_token", "hf_" + "a" * 34),
    ("sendgrid_api_key", "SG." + "a" * 22 + "." + "b" * 43),
    ("digitalocean_pat", "dop_v1_" + "0" * 64),
    # Additional high-confidence provider credential families
    ("stripe_secret_key", "sk_live_" + "a" * 24),
    ("stripe_restricted_key", "rk_live_" + "a" * 24),
    ("twilio_api_key", "SK" + "0123456789abcdef0123456789abcdef"),
    ("pypi_token", "pypi-" + "a" * 50),
    ("dockerhub_pat", "dckr_pat_" + "a" * 27),
]

SYNTHETIC_V7_NEW_FAMILIES = [
    ("gitlab_pat", "glpat-" + "a" * 20),
    ("npm_token", "npm_" + "a" * 36),
    ("huggingface_token", "hf_" + "a" * 34),
    ("sendgrid_api_key", "SG." + "a" * 22 + "." + "b" * 43),
    ("digitalocean_pat", "dop_v1_" + "0" * 64),
]

NEAR_MISSES = [
    ("gitlab_pat_short", "glpat-short"),
    ("npm_token_short", "npm_short"),
    ("huggingface_token_short", "hf_short"),
    ("sendgrid_api_key_invalid", "SG.short.short"),
    ("digitalocean_pat_short", "dop_v1_short"),
    ("stripe_key_short", "sk_tiny"),
    ("twilio_api_key_short", "SK0123456789"),
    ("twilio_api_key_non_hex", "SKZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"),
    ("pypi_token_short", "pypi-short"),
    ("dockerhub_pat_short", "dckr_pat_short"),
    ("aws_access_key_lower", "akia1234567890abcdef"),
    ("google_api_key_short", "AIzaSyShort"),
    ("github_classic_short", "ghp_short"),
    ("slack_token_short", "xoxb-short"),
]

SAFE_STRINGS = [
    ("uuid", "123e4567-e89b-12d3-a456-426614174000"),
    ("url", "https://api.example.com/v1/projects/alpha"),
    ("event_id", "evt-20260829-001"),
    ("context_id", "ctx-resolution-alpha"),
    ("domain_slug_general", "general"),
    ("domain_slug_project", "project"),
    ("domain_slug_life_plan", "life-plan"),
    ("domain_slug_health", "health"),
    ("normal_prose", "The domain completed execution with standard parameters."),
]


def _sample_event(
    *,
    event_id: str = "evt-v7-100",
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
        "event_id": "evt-v7-valid-1",
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
# 1. Canonical Policy Self-Tests
# ===============================================================================


def test_audit_v7_policy_registry_names_unique() -> None:
    """CredentialSignature names in the canonical registry must be unique."""
    names = [sig.name for sig in HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES]
    assert len(names) == len(set(names))


def test_audit_v7_policy_registry_immutable() -> None:
    """The canonical registry must be an immutable tuple of frozen CredentialSignature instances."""
    assert isinstance(HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES, tuple)
    for sig in HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES:
        assert isinstance(sig, CredentialSignature)
        with pytest.raises(FrozenInstanceError):
            sig.name = "mutated"  # type: ignore[misc]


def test_audit_v7_policy_all_patterns_compile() -> None:
    """All patterns in the canonical policy must be precompiled regular expressions."""
    for sig in HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES:
        assert hasattr(sig.pattern, "search")


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v7_policy_detects_synthetic_credentials(
    family: str, credential: str
) -> None:
    """contains_high_confidence_credential must return True for every supported synthetic token."""
    assert contains_high_confidence_credential(credential) is True


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v7_policy_detects_embedded_credentials(
    family: str, credential: str
) -> None:
    """contains_high_confidence_credential must detect credentials embedded in larger text."""
    embedded = f'{{"api_key": "{credential}", "status": "ok"}}'
    assert contains_high_confidence_credential(embedded) is True


@pytest.mark.parametrize("label,near_miss", NEAR_MISSES)
def test_audit_v7_policy_ignores_near_misses(label: str, near_miss: str) -> None:
    """contains_high_confidence_credential must not trigger on safe near-misses."""
    assert contains_high_confidence_credential(near_miss) is False


@pytest.mark.parametrize("label,safe_str", SAFE_STRINGS)
def test_audit_v7_policy_ignores_safe_strings(label: str, safe_str: str) -> None:
    """contains_high_confidence_credential must not trigger on normal IDs, UUIDs, URLs, or slugs."""
    assert contains_high_confidence_credential(safe_str) is False


# ===============================================================================
# 2. Table-Driven Regression Matrix Across Event Boundaries
# ===============================================================================


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v7_payload_nested_credential_rejected(
    family: str, credential: str
) -> None:
    """Payload nested string containing high-confidence credential must fail closed with non-disclosure."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(payload={"data": {"token": credential}})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v7_metadata_nested_credential_rejected(
    family: str, credential: str
) -> None:
    """Metadata nested string containing credential must fail closed with non-disclosure."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(metadata={"config": {"key": credential}})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v7_event_id_credential_rejected(family: str, credential: str) -> None:
    """DomainEvent event_id containing credential must fail closed."""
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(event_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("family,credential", SYNTHETIC_CREDENTIALS)
def test_audit_v7_reference_id_credential_rejected(
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
def test_audit_v7_reference_from_dict_credential_rejected(
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
def test_audit_v7_session_id_credential_rejected(family: str, credential: str) -> None:
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
def test_audit_v7_correlation_id_credential_rejected(
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
def test_audit_v7_causation_id_credential_rejected(
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
def test_audit_v7_actor_credential_rejected(family: str, credential: str) -> None:
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
def test_audit_v7_permissions_credential_rejected(family: str, credential: str) -> None:
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
def test_audit_v7_from_dict_credential_in_payload_rejected(
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
def test_audit_v7_factory_create_event_credential_rejected(
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
def test_audit_v7_kernel_boundary_rejects_all_credential_families(
    family: str, credential: str
) -> None:
    """DomainKernelEventPublisher publication fails before emission for each credential family."""
    publisher = DomainKernelEventPublisher()

    # Attempt to construct and publish event with credential in payload
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt = _sample_event(payload={"credential_key": credential})
        publisher.publish(bad_evt)

    assert len(publisher.emitted_events) == 0


# ===============================================================================
# 4. DomainId Credential Boundary
# ===============================================================================


def test_audit_v7_domain_id_with_gitlab_pat_slug_rejected_at_event_boundary() -> None:
    """A syntactically valid lower-case credential-shaped slug (glpat-...) must fail closed at DomainEvent boundary."""
    cred_slug = "glpat-" + "a" * 20
    dom_id = DomainId(slug=cred_slug)

    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(domain_id=dom_id)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert cred_slug not in err_str
    assert cred_slug not in details_str


def test_audit_v7_domain_id_with_credential_slug_rejected_in_reference() -> None:
    """DomainEventReference with credential-shaped DomainId must fail closed."""
    cred_slug = "glpat-" + "a" * 20
    dom_id = DomainId(slug=cred_slug)

    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        DomainEventReference(
            kind="resolution", reference_id="res-123", domain_id=dom_id
        )

    err_str = str(exc_info.value)
    assert cred_slug not in err_str


def test_audit_v7_domain_id_credential_never_emitted_to_kernel() -> None:
    """A credential-shaped DomainId cannot be emitted to Kernel event envelope."""
    publisher = DomainKernelEventPublisher()
    cred_slug = "glpat-" + "a" * 20
    dom_id = DomainId(slug=cred_slug)

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt = _sample_event(domain_id=dom_id)
        publisher.publish(bad_evt)

    assert len(publisher.emitted_events) == 0
