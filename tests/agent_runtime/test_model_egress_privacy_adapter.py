"""Phase 11.21 — canonical privacy egress gate adapter tests.

The adapter must own no policy: every decision has to equal what the canonical
cognitive evaluator produces for the same privacy metadata, and the projection
must stay secret-free.
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.model_egress_privacy_adapter import (
    CanonicalPrivacyEgressGate,
    is_canonical_privacy_metadata,
)
from cmm.cognitive.privacy import (
    InvalidPrivacyMetadataError,
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    PrivacyPolicy,
    ProcessingLocation,
    evaluate_privacy_operation,
)

REMOTE_ALLOWED = PrivacyMetadata(
    policy=PrivacyPolicy.REMOTE_ALLOWED,
    allow_remote=True,
    allowed_processing_locations=(
        ProcessingLocation.LOCAL,
        ProcessingLocation.REMOTE,
    ),
)

LOCAL_ONLY = PrivacyMetadata(policy=PrivacyPolicy.LOCAL_ONLY)


def _gate() -> CanonicalPrivacyEgressGate:
    return CanonicalPrivacyEgressGate()


def test_local_only_blocks_remote_egress_with_the_canonical_reason() -> None:
    decision = _gate().evaluate_egress(
        privacy=LOCAL_ONLY, provider_id="remote-a", is_remote=True
    )

    assert decision.allowed is False
    assert decision.reason_code == "remote_blocked_local_only"
    assert decision.details["canonical_status"] == "denied"


def test_decision_matches_the_canonical_evaluator_exactly() -> None:
    expected = evaluate_privacy_operation(
        LOCAL_ONLY,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            provider_id="remote-a",
            processing_location=ProcessingLocation.REMOTE,
        ),
    )

    decision = _gate().evaluate_egress(
        privacy=LOCAL_ONLY, provider_id="remote-a", is_remote=True
    )

    assert decision.allowed is expected.allowed
    assert decision.reason_code == expected.reason_code
    assert decision.requires_approval is expected.requires_approval
    assert decision.requires_redaction is expected.requires_redaction


def test_approval_cannot_widen_a_canonical_privacy_denial() -> None:
    approved = evaluate_privacy_operation(
        LOCAL_ONLY,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            provider_id="remote-a",
            processing_location=ProcessingLocation.REMOTE,
            approval_granted=True,
            redaction_applied=True,
        ),
    )

    assert approved.allowed is False
    assert approved.reason_code == "remote_blocked_local_only"
    assert (
        _gate()
        .evaluate_egress(privacy=LOCAL_ONLY, provider_id="remote-a", is_remote=True)
        .allowed
        is False
    )


def test_local_only_allows_local_processing() -> None:
    decision = _gate().evaluate_egress(
        privacy=LOCAL_ONLY, provider_id="local", is_remote=False
    )

    assert decision.allowed is True
    assert decision.reason_code == "allowed"


def test_remote_allowed_policy_permits_transmission() -> None:
    decision = _gate().evaluate_egress(
        privacy=REMOTE_ALLOWED, provider_id="remote-a", is_remote=True
    )

    assert decision.allowed is True
    assert decision.reason_code == "allowed"


def test_local_preferred_requires_an_explicit_remote_exception() -> None:
    preferred = PrivacyMetadata(
        policy=PrivacyPolicy.LOCAL_PREFERRED,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
    )

    decision = _gate().evaluate_egress(
        privacy=preferred, provider_id="remote-a", is_remote=True
    )

    assert decision.allowed is False
    assert decision.reason_code == "remote_blocked_not_authorized"


def test_prohibited_provider_cannot_transmit() -> None:
    privacy = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        prohibited_providers=("remote-a",),
    )

    decision = _gate().evaluate_egress(
        privacy=privacy, provider_id="remote-a", is_remote=True
    )

    assert decision.allowed is False
    assert decision.reason_code == "provider_prohibited"
    assert decision.details["excluded"] is True


def test_provider_allowlist_is_enforced() -> None:
    privacy = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allowed_providers=("remote-b",),
    )

    decision = _gate().evaluate_egress(
        privacy=privacy, provider_id="remote-a", is_remote=True
    )

    assert decision.allowed is False
    assert decision.reason_code == "provider_not_allowlisted"


def test_a_policy_requiring_approval_stays_denied() -> None:
    privacy = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        requires_approval=True,
    )

    decision = _gate().evaluate_egress(
        privacy=privacy, provider_id="remote-a", is_remote=True
    )

    assert decision.allowed is False
    assert decision.reason_code == "approval_required"
    assert decision.requires_approval is True


def test_missing_privacy_metadata_defaults_conservatively() -> None:
    gate = _gate()

    remote = gate.evaluate_egress(privacy=None, provider_id="remote-a", is_remote=True)
    local = gate.evaluate_egress(privacy=None, provider_id="local", is_remote=False)

    assert remote.allowed is False
    assert remote.reason_code == "privacy_metadata_required"
    assert local.allowed is True
    assert local.reason_code == "not_required"


def test_foreign_privacy_input_fails_closed() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        _gate().evaluate_egress(
            privacy=object(), provider_id="remote-a", is_remote=True
        )
    assert is_canonical_privacy_metadata(LOCAL_ONLY) is True
    assert is_canonical_privacy_metadata("LOCAL_ONLY") is False


def test_the_projection_never_carries_canonical_metadata_payloads() -> None:
    privacy = PrivacyMetadata(
        policy=PrivacyPolicy.LOCAL_ONLY,
        metadata={"api_key": "sk-should-not-propagate"},
    )

    decision = _gate().evaluate_egress(
        privacy=privacy, provider_id="remote-a", is_remote=True
    )

    serialized = str(decision.to_dict())
    assert "sk-should-not-propagate" not in serialized
    assert set(decision.details) == {
        "provider_id",
        "canonical_status",
        "canonical_reason_code",
        "excluded",
    }
