"""Tests for Phase 10.28 Sport Domain Trace."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from cmm.domains.sport.trace import (
    assemble_sport_trace,
    build_sport_trace_reference,
    validate_sport_trace,
)
from cmm.domains.trace_contracts import (
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)


def test_sport_trace_reference_creation() -> None:
    ref = build_sport_trace_reference(
        ref_id="rule:sport.rule.training_load",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    assert ref.ref_id == "rule:sport.rule.training_load"
    assert ref.domain_id == "domain:sport"


def test_sport_trace_assembly_real_ids() -> None:
    now = datetime.now(timezone.utc)
    trace = assemble_sport_trace(
        request_id="req-sport-001",
        resolution_context_id="ctx-001",
        resolution_result_id="res-001",
        composition_id="comp-001",
        domain_result_id="dres-001",
        started_at=now,
        completed_at=now,
    )
    assert trace.primary_domain == "domain:sport"
    assert trace.request_id == "req-sport-001"
    assert len(trace.contributions) >= 1


def test_sport_trace_validation_against_independent_inventory() -> None:
    now = datetime.now(timezone.utc)
    ref1 = build_sport_trace_reference(
        ref_id="prof-001", kind=DomainTraceReferenceKind.PROFILE
    )
    ref2 = build_sport_trace_reference(
        ref_id="rule-001", kind=DomainTraceReferenceKind.RULE_RESULT
    )

    trace = assemble_sport_trace(
        request_id="req-sport-001",
        resolution_context_id="ctx-001",
        resolution_result_id="res-001",
        composition_id="comp-001",
        domain_result_id="dres-001",
        started_at=now,
        completed_at=now,
        references=(ref1, ref2),
    )

    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                "dres-001", DomainTraceReferenceKind.DOMAIN_RESULT, "domain:sport"
            ),
            DomainTraceReference(
                "prof-001", DomainTraceReferenceKind.PROFILE, "domain:sport"
            ),
            DomainTraceReference(
                "rule-001", DomainTraceReferenceKind.RULE_RESULT, "domain:sport"
            ),
            DomainTraceReference(
                "ctx-001", DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                "res-001", DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(
                "comp-001", DomainTraceReferenceKind.COMPOSITION, None
            ),
        ),
        domain_results=trace.domain_results,
        cross_domain_results=(),
        expected_primary_domain="domain:sport",
        resolution_result_domains=DomainTraceDomainSelection(
            "res-001", "domain:sport", ()
        ),
        composition_domains=DomainTraceDomainSelection("comp-001", "domain:sport", ()),
    )

    val = validate_sport_trace(trace=trace, inventory=inventory)
    assert val.valid is True

    # Tampered reference fails
    tampered_contrib = replace(
        trace.contributions[0],
        references=tuple(
            replace(ref, ref_id="fake-prof") if ref.ref_id == "prof-001" else ref
            for ref in trace.contributions[0].references
        ),
    )
    tampered_trace = replace(trace, contributions=(tampered_contrib,))
    bad_val = validate_sport_trace(trace=tampered_trace, inventory=inventory)
    assert bad_val.valid is False
