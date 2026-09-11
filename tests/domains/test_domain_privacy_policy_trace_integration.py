"""Phase 10.50 – privacy decisions surface through existing Domain Trace references.

The trace remains reference-only: it carries the canonical privacy decision
identity/status/reason evidence by reference and never embeds a restricted raw
payload or a copied ``PrivacyMetadata`` blob.

Remediation V1 (MAJOR-02) replaces the synthetic ``privacy-decision:<n>``
reference with a real production binding: a canonical ``PrivacyDecision``
produced by ``evaluate_privacy_operation(...)`` is projected into a
deterministic, content-addressed ``PrivacyDecisionTraceEvidence`` and only then
referenced from the trace.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.privacy import (
    PrivacyDecision,
    PrivacyDecisionStatus,
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    PrivacyPolicy,
    ProcessingLocation,
    evaluate_privacy_operation,
)
from cmm.domains.errors import DomainTraceContractError, DomainTraceError
from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
    DomainTraceValidationCode,
    PrivacyDecisionTraceEvidence,
)
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator

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


def _allowed_decision() -> PrivacyDecision:
    return evaluate_privacy_operation(
        PrivacyMetadata(
            policy=PrivacyPolicy.REMOTE_ALLOWED,
            allowed_processing_locations=(
                ProcessingLocation.LOCAL,
                ProcessingLocation.REMOTE,
            ),
            allow_remote=True,
        ),
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )


def _evidence(
    decision: PrivacyDecision | None = None,
) -> PrivacyDecisionTraceEvidence:
    return PrivacyDecisionTraceEvidence.from_privacy_decision(
        domain_id="domain:health",
        operation=PrivacyOperation.PROCESS_REMOTE,
        decision=decision if decision is not None else _privacy_decision(),
    )


def _inventory(
    *,
    reference: DomainTraceReference,
    privacy_decisions: tuple[PrivacyDecisionTraceEvidence, ...],
) -> DomainTraceReferenceInventory:
    return DomainTraceReferenceInventory(
        references=(reference,),
        expected_primary_domain="domain:health",
        resolution_result_domains=DomainTraceDomainSelection(
            source_id="resolution-result:1", primary_domain="domain:health"
        ),
        composition_domains=DomainTraceDomainSelection(
            source_id="composition:1", primary_domain="domain:health"
        ),
        privacy_decisions=privacy_decisions,
    )


# ── Evidence is derived from a real canonical decision ────────────────────────


def test_privacy_decision_evidence_is_built_from_real_canonical_decision() -> None:
    decision = _privacy_decision()

    evidence = PrivacyDecisionTraceEvidence.from_privacy_decision(
        domain_id="domain:health",
        operation=PrivacyOperation.PROCESS_REMOTE,
        decision=decision,
    )

    assert evidence.domain_id == "domain:health"
    assert evidence.operation is PrivacyOperation.PROCESS_REMOTE
    assert evidence.allowed is decision.allowed
    assert evidence.status is decision.status
    assert evidence.reason_code == decision.reason_code
    assert evidence.requires_redaction is decision.requires_redaction
    assert evidence.requires_approval is decision.requires_approval
    assert evidence.excluded is decision.excluded


def test_privacy_decision_evidence_id_is_deterministic() -> None:
    first = _evidence()
    second = _evidence()

    assert first.decision_id == second.decision_id
    assert first.decision_id.startswith("privacy-decision:")
    assert first.decision_id != "privacy-decision:1"


def test_privacy_decision_evidence_id_changes_when_safe_outcome_changes() -> None:
    denied = _evidence(_privacy_decision())
    allowed = _evidence(_allowed_decision())

    assert denied.decision_id != allowed.decision_id
    assert denied.allowed is False
    assert allowed.allowed is True


def test_privacy_decision_evidence_excludes_reasons_metadata_context_and_payload() -> (
    None
):
    decision = _privacy_decision()

    evidence = PrivacyDecisionTraceEvidence.from_privacy_decision(
        domain_id="domain:health",
        operation=PrivacyOperation.PROCESS_REMOTE,
        decision=decision,
    )

    serialized = repr(evidence.to_dict())

    for forbidden in (
        "reasons",
        "metadata",
        "privacy_metadata",
        "actor_id",
        "provider_id",
        "prompt",
        "content",
        "payload",
        "credential",
        "token",
        "secret",
    ):
        assert forbidden not in serialized
    assert decision.reasons[0] not in serialized


def test_privacy_decision_evidence_reference_uses_exact_evidence_id() -> None:
    evidence = _evidence()

    reference = evidence.to_reference()

    assert isinstance(reference, DomainTraceReference)
    assert reference.ref_id == evidence.decision_id
    assert reference.kind is DomainTraceReferenceKind.PRIVACY_DECISION
    assert reference.domain_id == evidence.domain_id
    assert set(reference.to_dict()) == {"ref_id", "kind", "domain_id"}


def test_privacy_decision_evidence_round_trip_is_deterministic() -> None:
    evidence = _evidence()

    payload = evidence.to_dict()
    restored = PrivacyDecisionTraceEvidence.from_dict(payload)

    assert restored == evidence
    assert restored.to_dict() == payload


def test_privacy_decision_evidence_rejects_non_canonical_decision_id() -> None:
    evidence = _evidence()
    payload = evidence.to_dict()
    payload["decision_id"] = "privacy-decision:000000000000000000000000"

    with pytest.raises(DomainTraceError):
        PrivacyDecisionTraceEvidence.from_dict(payload)

    with pytest.raises(DomainTraceContractError):
        PrivacyDecisionTraceEvidence(
            decision_id="privacy-decision:000000000000000000000000",
            domain_id="domain:health",
            operation=PrivacyOperation.PROCESS_REMOTE,
            allowed=False,
            status=PrivacyDecisionStatus.DENIED,
            reason_code="remote_blocked_local_only",
            requires_redaction=False,
            requires_approval=False,
            excluded=False,
        )


def test_privacy_decision_evidence_requires_a_canonical_decision() -> None:
    with pytest.raises(DomainTraceContractError):
        PrivacyDecisionTraceEvidence.from_privacy_decision(
            domain_id="domain:health",
            operation=PrivacyOperation.PROCESS_REMOTE,
            decision={"allowed": False},
        )


# ── Authoritative inventory binding ───────────────────────────────────────────


def test_inventory_accepts_bound_privacy_decision_evidence() -> None:
    evidence = _evidence()
    reference = evidence.to_reference()

    inventory = _inventory(reference=reference, privacy_decisions=(evidence,))

    assert inventory.privacy_decisions == (evidence,)
    assert (
        inventory.digest
        == DomainTraceReferenceInventory.from_dict(inventory.to_dict()).digest
    )


def test_inventory_requires_evidence_for_privacy_decision_reference() -> None:
    reference = _evidence().to_reference()

    with pytest.raises(DomainTraceContractError):
        _inventory(reference=reference, privacy_decisions=())


def test_inventory_rejects_orphan_privacy_decision_evidence() -> None:
    evidence = _evidence()

    with pytest.raises(DomainTraceContractError):
        _inventory(
            reference=DomainTraceReference(
                ref_id="warning:1",
                kind=DomainTraceReferenceKind.WARNING,
                domain_id="domain:health",
            ),
            privacy_decisions=(evidence,),
        )


def test_inventory_rejects_privacy_decision_domain_mismatch() -> None:
    evidence = PrivacyDecisionTraceEvidence.from_privacy_decision(
        domain_id="domain:health",
        operation=PrivacyOperation.PROCESS_REMOTE,
        decision=_privacy_decision(),
    )
    reference = DomainTraceReference(
        ref_id=evidence.decision_id,
        kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        domain_id="domain:university",
    )

    with pytest.raises(DomainTraceContractError):
        _inventory(reference=reference, privacy_decisions=(evidence,))


def test_inventory_rejects_privacy_decision_kind_mismatch() -> None:
    evidence = _evidence()
    reference = DomainTraceReference(
        ref_id=evidence.decision_id,
        kind=DomainTraceReferenceKind.PERMISSION_DECISION,
        domain_id=evidence.domain_id,
    )

    with pytest.raises(DomainTraceContractError):
        _inventory(reference=reference, privacy_decisions=(evidence,))


def test_inventory_rejects_duplicate_privacy_decision_evidence() -> None:
    evidence = _evidence()
    reference = evidence.to_reference()

    with pytest.raises(DomainTraceContractError):
        _inventory(
            reference=reference,
            privacy_decisions=(evidence, evidence),
        )


def test_inventory_privacy_evidence_round_trip_is_deterministic() -> None:
    evidence = _evidence()
    inventory = _inventory(
        reference=evidence.to_reference(), privacy_decisions=(evidence,)
    )

    payload = inventory.to_dict()
    restored = DomainTraceReferenceInventory.from_dict(payload)

    assert restored == inventory
    assert restored.to_dict() == payload


def test_inventory_without_privacy_evidence_stays_backward_compatible() -> None:
    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                ref_id="warning:1",
                kind=DomainTraceReferenceKind.WARNING,
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

    assert inventory.privacy_decisions == ()
    assert DomainTraceReferenceInventory.from_dict(inventory.to_dict()) == inventory


# ── Existing reference-kind behavior is preserved ─────────────────────────────


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
    evidence = _evidence()
    reference = evidence.to_reference()

    payload = reference.to_dict()

    assert set(payload) == {"ref_id", "kind", "domain_id"}
    assert payload["kind"] == "privacy_decision"

    decision = _privacy_decision()
    assert decision.reason_code not in payload.values()
    assert decision.status.value not in payload.values()
    assert decision.reasons[0] not in payload.values()


def test_privacy_trace_reference_does_not_embed_privacy_payload() -> None:
    reference = _evidence().to_reference()

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
    reference = _evidence().to_reference()

    payload = reference.to_dict()
    restored = DomainTraceReference.from_dict(payload)

    assert restored == reference
    assert restored.to_dict() == payload


def test_trace_inventory_validates_privacy_reference() -> None:
    evidence = _evidence()
    inventory = _inventory(
        reference=evidence.to_reference(), privacy_decisions=(evidence,)
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


# ── Validator pairing against the authoritative inventory ─────────────────────


def _trace_with_privacy_reference(
    evidence: PrivacyDecisionTraceEvidence,
    *,
    reference: DomainTraceReference | None = None,
) -> object:
    ref = reference if reference is not None else evidence.to_reference()
    request = DomainTraceAssemblyRequest(
        request_id="request:privacy-1",
        primary_domain=evidence.domain_id,
        contributions=(
            DomainTraceContribution(
                evidence.domain_id,
                DomainTraceRole.PRIMARY,
                (ref,),
            ),
        ),
        references=DomainTraceReferences(
            "resolution-context:1", "resolution-result:1", "composition:1"
        ),
        started_at=NOW,
        completed_at=NOW.replace(second=1),
    )
    return DomainTraceAssembler().assemble(request)


def _privacy_inventory(
    evidence: PrivacyDecisionTraceEvidence,
    *,
    reference: DomainTraceReference | None = None,
) -> DomainTraceReferenceInventory:
    bound = reference if reference is not None else evidence.to_reference()
    return DomainTraceReferenceInventory(
        references=(*_global_references(), bound),
        expected_primary_domain=evidence.domain_id,
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", evidence.domain_id
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", evidence.domain_id
        ),
        privacy_decisions=(evidence,),
    )


def _global_references() -> tuple[DomainTraceReference, ...]:
    return (
        DomainTraceReference(
            "resolution-context:1", DomainTraceReferenceKind.RESOLUTION_CONTEXT
        ),
        DomainTraceReference(
            "resolution-result:1", DomainTraceReferenceKind.RESOLUTION_RESULT
        ),
        DomainTraceReference("composition:1", DomainTraceReferenceKind.COMPOSITION),
    )


def _with_contribution(trace: object, contribution: DomainTraceContribution) -> object:
    object.__setattr__(trace, "contributions", (contribution,))
    return trace


def test_validator_accepts_real_bound_privacy_decision_reference() -> None:
    evidence = _evidence()

    result = DefaultDomainTraceReferenceValidator().validate(
        _trace_with_privacy_reference(evidence), _privacy_inventory(evidence)
    )

    assert result.valid
    assert result.codes == ()


def test_validator_rejects_fake_privacy_decision_reference() -> None:
    evidence = _evidence()
    fake = DomainTraceReference(
        ref_id="privacy-decision:000000000000000000000000",
        kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        domain_id=evidence.domain_id,
    )
    trace = _with_contribution(
        _trace_with_privacy_reference(evidence),
        DomainTraceContribution(evidence.domain_id, DomainTraceRole.PRIMARY, (fake,)),
    )

    result = DefaultDomainTraceReferenceValidator().validate(
        trace, _privacy_inventory(evidence)
    )

    assert not result.valid
    assert DomainTraceValidationCode.PRIVACY_DECISION_PAIRING_MISMATCH in result.codes


def test_validator_rejects_stale_privacy_decision_reference() -> None:
    stale = _evidence(_privacy_decision())
    current = _evidence(_allowed_decision())
    assert stale.decision_id != current.decision_id

    result = DefaultDomainTraceReferenceValidator().validate(
        _trace_with_privacy_reference(stale), _privacy_inventory(current)
    )

    assert not result.valid
    assert DomainTraceValidationCode.PRIVACY_DECISION_PAIRING_MISMATCH in result.codes


def test_validator_rejects_privacy_decision_domain_mismatch() -> None:
    evidence = _evidence()
    mismatched = DomainTraceReference(
        ref_id=evidence.decision_id,
        kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        domain_id="domain:university",
    )
    trace = _with_contribution(
        _trace_with_privacy_reference(evidence),
        DomainTraceContribution(
            "domain:university", DomainTraceRole.PRIMARY, (mismatched,)
        ),
    )

    result = DefaultDomainTraceReferenceValidator().validate(
        trace, _privacy_inventory(evidence)
    )

    assert not result.valid
    assert DomainTraceValidationCode.PRIVACY_DECISION_PAIRING_MISMATCH in result.codes


def test_validator_rejects_privacy_decision_kind_mismatch() -> None:
    evidence = _evidence()
    inventory = DomainTraceReferenceInventory(
        references=(
            *_global_references(),
            DomainTraceReference(
                ref_id=evidence.decision_id,
                kind=DomainTraceReferenceKind.FINDING,
                domain_id=evidence.domain_id,
            ),
        ),
        expected_primary_domain=evidence.domain_id,
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", evidence.domain_id
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", evidence.domain_id
        ),
    )

    result = DefaultDomainTraceReferenceValidator().validate(
        _trace_with_privacy_reference(evidence), inventory
    )

    assert not result.valid
    assert DomainTraceValidationCode.PRIVACY_DECISION_PAIRING_MISMATCH in result.codes
