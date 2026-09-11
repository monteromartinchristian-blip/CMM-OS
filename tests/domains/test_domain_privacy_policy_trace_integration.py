"""Phase 10.50 – privacy decisions surface through existing Domain Trace references.

The trace remains reference-only: it carries the canonical privacy decision
identity/status/reason evidence by reference and never embeds a restricted raw
payload or a copied ``PrivacyMetadata`` blob.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.privacy import (
    PrivacyDecision,
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    PrivacyPolicy,
    ProcessingLocation,
    evaluate_privacy_operation,
)
from cmm.domains.errors import DomainTraceContractError
from cmm.domains.trace_contracts import (
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)

NOW = datetime(2026, 9, 11, 11, 0, tzinfo=timezone.utc)


def _privacy_decision() -> PrivacyDecision:
    return evaluate_privacy_operation(
        PrivacyMetadata(
            policy=PrivacyPolicy.LOCAL_ONLY,
            allowed_processing_locations=(ProcessingLocation.LOCAL,),
            allow_remote=False,
        ),
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )


def test_domain_trace_accepts_privacy_decision_reference_kind() -> None:
    assert DomainTraceReferenceKind.PRIVACY_DECISION.value == "privacy_decision"

    reference = DomainTraceReference(
        ref_id="privacy-decision:1",
        kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        domain_id="domain:health",
    )

    assert reference.kind is DomainTraceReferenceKind.PRIVACY_DECISION
    assert reference.domain_id is not None


def test_privacy_trace_reference_requires_a_domain_owner() -> None:
    with pytest.raises(DomainTraceContractError):
        DomainTraceReference(
            ref_id="privacy-decision:1",
            kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        )


def test_privacy_trace_reference_is_reference_only() -> None:
    reference = DomainTraceReference(
        ref_id="privacy-decision:1",
        kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        domain_id="domain:health",
    )

    payload = reference.to_dict()

    assert set(payload) == {"ref_id", "kind", "domain_id"}
    assert payload["kind"] == "privacy_decision"

    decision = _privacy_decision()
    assert decision.reason_code not in payload.values()
    assert decision.status.value not in payload.values()
    assert decision.reasons[0] not in payload.values()


def test_privacy_trace_reference_does_not_embed_privacy_payload() -> None:
    reference = DomainTraceReference(
        ref_id="privacy-decision:1",
        kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        domain_id="domain:health",
    )

    serialized = repr(reference.to_dict())

    for forbidden in (
        "allowed_providers",
        "prohibited_providers",
        "allowed_processing_locations",
        "sensitivity",
        "requires_redaction",
    ):
        assert forbidden not in serialized


def test_privacy_trace_reference_round_trip_is_deterministic() -> None:
    reference = DomainTraceReference(
        ref_id="privacy-decision:1",
        kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        domain_id="domain:health",
    )

    payload = reference.to_dict()
    restored = DomainTraceReference.from_dict(payload)

    assert restored == reference
    assert restored.to_dict() == payload


def test_trace_inventory_validates_privacy_reference() -> None:
    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                ref_id="privacy-decision:1",
                kind=DomainTraceReferenceKind.PRIVACY_DECISION,
                domain_id="domain:health",
            ),
        ),
        expected_primary_domain="domain:health",
        resolution_result_domains=DomainTraceDomainSelection(
            source_id="resolution-result:1", primary_domain="domain:health"
        ),
        composition_domains=DomainTraceDomainSelection(
            source_id="composition:1", primary_domain="domain:health"
        ),
    )

    assert inventory.references[0].kind is DomainTraceReferenceKind.PRIVACY_DECISION
    assert (
        inventory.digest
        == DomainTraceReferenceInventory.from_dict(inventory.to_dict()).digest
    )


def test_trace_inventory_rejects_unknown_privacy_reference_kind() -> None:
    with pytest.raises(ValueError):
        DomainTraceReference(
            ref_id="privacy-decision:1",
            kind="privacy_decision_v2",
            domain_id="domain:health",
        )
