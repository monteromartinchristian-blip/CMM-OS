"""Inventory validation for Phase 10.17 traces."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    CrossDomainTraceReference,
    DomainResultTraceReference,
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
    DomainTraceValidationCode,
)
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator


def _trace_and_inventory():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    request = DomainTraceAssemblyRequest(
        request_id="request:1", primary_domain="domain:life-plan", supporting_domains=("domain:health",),
        contributions=(
            DomainTraceContribution("domain:life-plan", DomainTraceRole.PRIMARY, (DomainTraceReference("domain-result:1", DomainTraceReferenceKind.DOMAIN_RESULT, "domain:life-plan"),)),
            DomainTraceContribution("domain:health", DomainTraceRole.SUPPORTING, (DomainTraceReference("warning:1", DomainTraceReferenceKind.WARNING, "domain:health"),)),
        ),
        references=DomainTraceReferences(
            "resolution-context:1", "resolution-result:1", "composition:1",
            cross_domain_results=(CrossDomainTraceReference("cross-domain-result:1", "cross-trace:upstream"),),
        ),
        domain_results=(DomainResultTraceReference("domain-result:1", "domain:life-plan"),),
        started_at=now, completed_at=now.replace(second=1),
    )
    trace = DomainTraceAssembler().assemble(request)
    return trace, DomainTraceReferenceInventory(
        references=trace.all_references(), domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain="domain:life-plan",
        expected_supporting_domains=("domain:health",),
        resolution_result_domains=DomainTraceDomainSelection("resolution-result:1", "domain:life-plan", ("domain:health",)),
        composition_domains=DomainTraceDomainSelection("composition:1", "domain:life-plan", ("domain:health",)),
    )


def test_validator_accepts_an_exact_typed_inventory() -> None:
    trace, inventory = _trace_and_inventory()

    assert DefaultDomainTraceReferenceValidator().validate(trace, inventory).valid


def test_validator_rejects_reference_with_same_id_in_a_different_category() -> None:
    trace, inventory = _trace_and_inventory()
    wrong_kind = tuple(
        replace(item, kind=DomainTraceReferenceKind.FINDING)
        if item.ref_id == "warning:1" else item for item in inventory.references
    )

    result = DefaultDomainTraceReferenceValidator().validate(
        trace, replace(inventory, references=wrong_kind)
    )

    assert DomainTraceValidationCode.KIND_MISMATCH in result.codes


def test_validator_rejects_tampered_id_digest_and_result_pairing() -> None:
    trace, inventory = _trace_and_inventory()
    object.__setattr__(trace, "id", "domain-trace:tampered")
    object.__setattr__(trace, "domain_results", (DomainResultTraceReference("domain-result:1", "domain:life-plan", "domain-trace:other"),))

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert DomainTraceValidationCode.ID_DIGEST_MISMATCH in result.codes
    assert DomainTraceValidationCode.DOMAIN_RESULT_PAIRING_MISMATCH in result.codes


def test_validator_rejects_naive_completed_time_without_crashing() -> None:
    trace, inventory = _trace_and_inventory()
    object.__setattr__(trace, "completed_at", trace.completed_at.replace(tzinfo=None))

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert DomainTraceValidationCode.INVALID_TIMESTAMP in result.codes
