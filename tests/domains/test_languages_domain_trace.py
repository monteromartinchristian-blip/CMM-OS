"""Tests for Phase 10.26 Languages Domain Trace Integration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from cmm.domains.languages.definition import LANGUAGES_DOMAIN_ID
from cmm.domains.languages.trace import (
    assemble_languages_trace,
    build_languages_trace_contribution,
    build_languages_trace_reference,
    build_supporting_trace_contribution,
    validate_languages_trace,
)
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceRole,
)


def test_build_languages_trace_reference() -> None:
    """Verify trace reference builder for Languages."""
    ref = build_languages_trace_reference(
        ref_id="ref-1",
        kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION,
    )
    assert isinstance(ref, DomainTraceReference)
    assert ref.ref_id == "ref-1"
    assert ref.domain_id == LANGUAGES_DOMAIN_ID
    assert ref.kind is DomainTraceReferenceKind.RESOURCE_RESOLUTION


def test_build_languages_trace_contribution() -> None:
    """Verify primary trace contribution builder."""
    ref = build_languages_trace_reference(
        ref_id="res-1",
        kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION,
    )
    contrib = build_languages_trace_contribution(
        domain_result_id="res-out-1",
        references=(ref,),
    )
    assert isinstance(contrib, DomainTraceContribution)
    assert contrib.role is DomainTraceRole.PRIMARY
    assert contrib.domain_id == LANGUAGES_DOMAIN_ID
    assert len(contrib.references) == 2


def test_assemble_languages_trace_and_validation() -> None:
    """Verify trace assembly with primary and supporting contributions and inventory validation."""
    now = datetime.now(timezone.utc)
    supporting_contrib = build_supporting_trace_contribution(
        domain_result_id="supp-res-1",
        domain_id="domain:university",
    )
    primary_ref = build_languages_trace_reference(
        ref_id="lang-res-1",
        kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION,
    )
    trace = assemble_languages_trace(
        request_id="req-tr-1",
        resolution_context_id="ctx-1",
        resolution_result_id="res-ctx-1",
        composition_id="comp-1",
        domain_result_id="lang-res-out-1",
        started_at=now,
        completed_at=now,
        references=(primary_ref,),
        supporting_domains=("domain:university",),
        contributions=(supporting_contrib,),
    )
    assert isinstance(trace, DomainTrace)
    assert trace.primary_domain == LANGUAGES_DOMAIN_ID
    assert trace.supporting_domains == ("domain:university",)

    # Validate against inventory
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain=LANGUAGES_DOMAIN_ID,
        expected_supporting_domains=("domain:university",),
        resolution_result_domains=DomainTraceDomainSelection(
            "res-ctx-1",
            LANGUAGES_DOMAIN_ID,
            ("domain:university",),
        ),
        composition_domains=DomainTraceDomainSelection(
            "comp-1",
            LANGUAGES_DOMAIN_ID,
            ("domain:university",),
        ),
    )
    val_res = validate_languages_trace(trace=trace, inventory=inventory)
    assert val_res.valid is True

    # Bad inventory should fail validation
    ghost = build_languages_trace_reference(
        ref_id="ghost", kind=DomainTraceReferenceKind.FINDING
    )
    bad = replace(inventory, references=(*inventory.references, ghost))
    bad_res = validate_languages_trace(trace=trace, inventory=bad)
    assert bad_res.valid is False
