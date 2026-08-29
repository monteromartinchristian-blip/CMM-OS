"""Phase 10.33 independent audit V7/V8 regression tests.

These tests encode findings from independent audits V7 and V8
of Phase 10.33 Domain Events (docs/audits/phase-10.33-independent-audit-v7.md,
docs/audits/phase-10.33-independent-audit-v8.md).

Remediates M8: Binds all event-boundary regression tests directly to the canonical
HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES registry with exact 1:1 name parity.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import FrozenInstanceError, dataclass
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


@dataclass(frozen=True, slots=True)
class CredentialTestVector:
    """Synthetic test vector representing one canonical CredentialSignature."""

    name: str
    positive_example: str
    near_miss: str


# ── Canonical Registry-Linked Synthetic Credential Test Vectors ───────────────

SYNTHETIC_CREDENTIAL_VECTORS: dict[str, CredentialTestVector] = {
    "openai_or_prefixed_key": CredentialTestVector(
        name="openai_or_prefixed_key",
        positive_example="sk-" + "A" * 40,
        near_miss="sk-tiny",
    ),
    "generic_key_pattern": CredentialTestVector(
        name="generic_key_pattern",
        positive_example="key-" + "a" * 24,
        near_miss="key-tiny",
    ),
    "github_classic_token": CredentialTestVector(
        name="github_classic_token",
        positive_example="ghp_" + "1" * 36,
        near_miss="ghp_short",
    ),
    "github_fine_grained_pat": CredentialTestVector(
        name="github_fine_grained_pat",
        positive_example="github_pat_" + "1" * 82,
        near_miss="github_pat_short",
    ),
    "aws_access_key_id": CredentialTestVector(
        name="aws_access_key_id",
        positive_example="AKIA" + "1234567890ABCDEF",
        near_miss="akia1234567890abcdef",
    ),
    "google_api_key": CredentialTestVector(
        name="google_api_key",
        positive_example="AIza" + "SyD1234567890abcdefghijklmnopqrstuv",
        near_miss="AIzaSyShort",
    ),
    "slack_token": CredentialTestVector(
        name="slack_token",
        positive_example="xoxb-123456789012-1234567890123-abcdef123456",
        near_miss="xoxb-short",
    ),
    "gitlab_pat": CredentialTestVector(
        name="gitlab_pat",
        positive_example="glpat-" + "a" * 20,
        near_miss="glpat-short",
    ),
    "npm_token": CredentialTestVector(
        name="npm_token",
        positive_example="npm_" + "a" * 36,
        near_miss="npm_short",
    ),
    "huggingface_token": CredentialTestVector(
        name="huggingface_token",
        positive_example="hf_" + "a" * 34,
        near_miss="hf_short",
    ),
    "sendgrid_api_key": CredentialTestVector(
        name="sendgrid_api_key",
        positive_example="SG." + "a" * 22 + "." + "b" * 43,
        near_miss="SG.short.short",
    ),
    "digitalocean_pat": CredentialTestVector(
        name="digitalocean_pat",
        positive_example="dop_v1_" + "0" * 64,
        near_miss="dop_v1_short",
    ),
    "stripe_api_key": CredentialTestVector(
        name="stripe_api_key",
        positive_example="sk_live_" + "a" * 24,
        near_miss="rk_live_short",
    ),
    "twilio_api_key": CredentialTestVector(
        name="twilio_api_key",
        positive_example="SK" + "0123456789abcdef0123456789abcdef",
        near_miss="SK0123456789",
    ),
    "pypi_token": CredentialTestVector(
        name="pypi_token",
        positive_example="pypi-" + "a" * 50,
        near_miss="pypi-short",
    ),
    "dockerhub_pat": CredentialTestVector(
        name="dockerhub_pat",
        positive_example="dckr_pat_" + "a" * 27,
        near_miss="dckr_pat_short",
    ),
    "authorization_header": CredentialTestVector(
        name="authorization_header",
        positive_example="Authorization: Bearer myauthtoken123",
        near_miss="authorized: true",
    ),
    "bearer_token": CredentialTestVector(
        name="bearer_token",
        positive_example="Bearer mybearertoken123",
        near_miss="bearer short",
    ),
    "bearer_assignment": CredentialTestVector(
        name="bearer_assignment",
        positive_example="bearer=mybearertoken123",
        near_miss="bearer_mode=active",
    ),
    "credential_assignment": CredentialTestVector(
        name="credential_assignment",
        positive_example="password=supersecretpassword123",
        near_miss="password_prompt=enter",
    ),
}

REGISTRY_SIGNATURE_NAMES: tuple[str, ...] = tuple(
    sig.name for sig in HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES
)

EXTRA_NEAR_MISSES: list[tuple[str, str]] = [
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

SAFE_STRINGS: list[tuple[str, str]] = [
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

VALID_SLUG_CREDENTIAL_EXAMPLES: list[tuple[str, str]] = [
    ("gitlab_pat", "glpat-" + "a" * 20),
    ("pypi_token", "pypi-" + "a" * 50),
    ("generic_key_pattern", "key-" + "a" * 24),
    ("openai_or_prefixed_key", "sk-" + "a" * 32),
    ("slack_token", "xoxb-123456789012-1234567890123-abcdef123456"),
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
# 1. Canonical Policy Registry Gates & Self-Tests
# ===============================================================================


def test_audit_v7_policy_registry_names_unique() -> None:
    """CredentialSignature names in the canonical registry must be unique and match exact count."""
    names = [sig.name for sig in HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES]
    assert len(names) == len(set(names))
    assert len(HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES) == 20


def test_audit_v8_registry_driven_test_vectors_exact_parity() -> None:
    """SYNTHETIC_CREDENTIAL_VECTORS must have exact 1:1 key parity with HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES.

    Guarantees:
    - New registry signature without test vector => test failure
    - Stale test vector without registry signature => test failure
    - Exact 20 signature count
    - No name mismatch or alias drifting
    """
    registry_names = {sig.name for sig in HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES}
    assert len(HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES) == 20
    assert len(registry_names) == 20
    assert set(SYNTHETIC_CREDENTIAL_VECTORS) == registry_names
    assert len(SYNTHETIC_CREDENTIAL_VECTORS) == 20
    for sig in HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES:
        vector = SYNTHETIC_CREDENTIAL_VECTORS[sig.name]
        assert vector.name == sig.name
        assert isinstance(vector.positive_example, str)
        assert len(vector.positive_example) > 0
        assert isinstance(vector.near_miss, str)
        assert len(vector.near_miss) > 0


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


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_policy_detects_synthetic_credentials(sig_name: str) -> None:
    """contains_high_confidence_credential must return True for every registry-linked synthetic positive vector."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    assert contains_high_confidence_credential(vector.positive_example) is True


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_policy_detects_embedded_credentials(sig_name: str) -> None:
    """contains_high_confidence_credential must detect credentials embedded in larger text for all 20 signatures."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    embedded = f'{{"api_key": "{vector.positive_example}", "status": "ok"}}'
    assert contains_high_confidence_credential(embedded) is True


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_policy_ignores_near_misses(sig_name: str) -> None:
    """contains_high_confidence_credential must not trigger on safe near-misses for all 20 signatures."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    assert contains_high_confidence_credential(vector.near_miss) is False


@pytest.mark.parametrize("label,near_miss", EXTRA_NEAR_MISSES)
def test_audit_v7_policy_ignores_extra_near_misses(label: str, near_miss: str) -> None:
    """contains_high_confidence_credential must not trigger on additional known safe near-misses."""
    assert contains_high_confidence_credential(near_miss) is False


@pytest.mark.parametrize("label,safe_str", SAFE_STRINGS)
def test_audit_v7_policy_ignores_safe_strings(label: str, safe_str: str) -> None:
    """contains_high_confidence_credential must not trigger on normal IDs, UUIDs, URLs, or slugs."""
    assert contains_high_confidence_credential(safe_str) is False


# ===============================================================================
# 2. Registry-Driven Regression Matrix Across All Event Boundaries
# ===============================================================================


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_payload_nested_credential_rejected(sig_name: str) -> None:
    """Payload nested string containing high-confidence credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(payload={"data": {"token": credential}})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_metadata_nested_credential_rejected(sig_name: str) -> None:
    """Metadata nested string containing credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(metadata={"config": {"key": credential}})

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_event_id_credential_rejected(sig_name: str) -> None:
    """DomainEvent event_id containing credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(event_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_reference_id_credential_rejected(sig_name: str) -> None:
    """DomainEventReference reference_id containing credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        DomainEventReference(kind="resolution", reference_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_reference_from_dict_credential_rejected(sig_name: str) -> None:
    """DomainEventReference.from_dict containing credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
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


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_session_id_credential_rejected(sig_name: str) -> None:
    """DomainEvent session_id containing credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(session_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_correlation_id_credential_rejected(sig_name: str) -> None:
    """DomainEvent correlation_id containing credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(correlation_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_causation_id_credential_rejected(sig_name: str) -> None:
    """DomainEvent causation_id containing credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(causation_id=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_actor_credential_rejected(sig_name: str) -> None:
    """DomainEvent actor containing credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(actor=credential)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_permissions_credential_rejected(sig_name: str) -> None:
    """DomainEvent permissions item containing credential must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(permissions=(credential,))

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert credential not in err_str
    assert credential not in details_str


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_from_dict_credential_in_payload_rejected(sig_name: str) -> None:
    """DomainEvent.from_dict with credential in payload must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
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


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_factory_create_event_credential_rejected(sig_name: str) -> None:
    """DomainEventFactory.create_event with credential in payload must fail closed with non-disclosure."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
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
# 3. Kernel Publication Boundary Gates for All 20 Credential Signatures
# ===============================================================================


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_kernel_boundary_rejects_all_credential_families(
    sig_name: str,
) -> None:
    """DomainKernelEventPublisher publication fails before emission for every canonical credential signature."""
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example
    publisher = DomainKernelEventPublisher()

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt = _sample_event(payload={"credential_key": credential})
        publisher.publish(bad_evt)

    assert len(publisher.emitted_events) == 0


# ===============================================================================
# 4. DomainId Credential Boundary Matrix
# ===============================================================================


@pytest.mark.parametrize("sig_name", REGISTRY_SIGNATURE_NAMES)
def test_audit_v8_domain_id_channel_boundary_for_all_signatures(
    sig_name: str,
) -> None:
    """All 20 credential signatures are safely rejected across the DomainId channel.

    If a signature form is a syntactically valid slug, it must be rejected by
    the privacy boundary with non-disclosure and never reach Kernel publication.
    If the signature contains characters forbidden by slug grammar (uppercase,
    underscores, symbols), it must fail at slug grammar validation without crashing.
    """
    vector = SYNTHETIC_CREDENTIAL_VECTORS[sig_name]
    credential = vector.positive_example

    try:
        dom_id = DomainId(slug=credential)
        # If slug grammar permitted it, DomainEvent must reject it at privacy boundary
        with pytest.raises(
            (DomainContractValidationError, DomainEventContractError)
        ) as exc_info:
            _sample_event(domain_id=dom_id)

        err_str = str(exc_info.value)
        details_str = str(getattr(exc_info.value, "details", {}))
        assert credential not in err_str
        assert credential not in details_str

        # DomainEventReference must also reject it
        with pytest.raises(
            (DomainContractValidationError, DomainEventContractError)
        ) as exc_info_ref:
            DomainEventReference(
                kind="resolution", reference_id="res-123", domain_id=dom_id
            )
        assert credential not in str(exc_info_ref.value)

        # Kernel publisher must never emit it
        pub = DomainKernelEventPublisher()
        with pytest.raises((DomainContractValidationError, DomainEventContractError)):
            pub.publish(_sample_event(domain_id=dom_id))
        assert len(pub.emitted_events) == 0
    except DomainContractValidationError as exc:
        # Rejected by DomainId slug grammar before privacy validation
        msg = str(exc).lower()
        assert "slug" in msg or "must be" in msg or "empty" in msg or "contain" in msg
        assert credential not in str(
            getattr(exc, "details", {}).get("secret_value", "")
        )


@pytest.mark.parametrize("label,cred_slug", VALID_SLUG_CREDENTIAL_EXAMPLES)
def test_audit_v8_syntactically_valid_credential_slugs_rejected_at_event_boundary(
    label: str, cred_slug: str
) -> None:
    """A syntactically valid lower-case credential-shaped slug must fail closed at DomainEvent boundary."""
    dom_id = DomainId(slug=cred_slug)

    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        _sample_event(domain_id=dom_id)

    err_str = str(exc_info.value)
    details_str = str(getattr(exc_info.value, "details", {}))
    assert cred_slug not in err_str
    assert cred_slug not in details_str


@pytest.mark.parametrize("label,cred_slug", VALID_SLUG_CREDENTIAL_EXAMPLES)
def test_audit_v8_syntactically_valid_credential_slugs_rejected_in_reference(
    label: str, cred_slug: str
) -> None:
    """DomainEventReference with syntactically valid credential-shaped DomainId must fail closed."""
    dom_id = DomainId(slug=cred_slug)

    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        DomainEventReference(
            kind="resolution", reference_id="res-123", domain_id=dom_id
        )

    err_str = str(exc_info.value)
    assert cred_slug not in err_str


@pytest.mark.parametrize("label,cred_slug", VALID_SLUG_CREDENTIAL_EXAMPLES)
def test_audit_v8_syntactically_valid_credential_slugs_never_emitted_to_kernel(
    label: str, cred_slug: str
) -> None:
    """A syntactically valid credential-shaped DomainId cannot be emitted to Kernel event envelope."""
    publisher = DomainKernelEventPublisher()
    dom_id = DomainId(slug=cred_slug)

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt = _sample_event(domain_id=dom_id)
        publisher.publish(bad_evt)

    assert len(publisher.emitted_events) == 0
