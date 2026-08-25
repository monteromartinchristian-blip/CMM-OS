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
    DomainResultTraceReference,
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
    from cmm.domains.contracts import DomainResult

    now = datetime.now(timezone.utc)
    upstream_domain_result = DomainResult(
        id="dres-001",
        status="completed",
        objective="Sport training load adjustment",
        primary_domain="domain:sport",
        supporting_domains=("domain:health",),
    )

    ref1 = build_sport_trace_reference(
        ref_id="prof-001", kind=DomainTraceReferenceKind.PROFILE
    )
    ref2 = build_sport_trace_reference(
        ref_id="rule-001", kind=DomainTraceReferenceKind.RULE_RESULT
    )
    result_id_str = str(upstream_domain_result.id)

    from cmm.domains.sport.trace import build_sport_trace_contribution
    from cmm.domains.trace_contracts import (
        DomainTrace,
        DomainTraceReferences,
        DomainTraceStatus,
    )

    req_id = "req-sport-001"
    ctx_id = "ctx-001"
    res_id = "res-001"
    comp_id = "comp-001"

    # Precompute expected trace canonical ID via probe
    trace_refs = DomainTraceReferences(
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        cross_domain_results=(),
        presentation_result_ids=(),
    )
    probe = DomainTrace(
        id="domain-trace:probe",
        digest="0" * 64,
        request_id=req_id,
        goal_id=None,
        primary_domain="domain:sport",
        supporting_domains=(),
        contributions=(
            build_sport_trace_contribution(
                domain_result_id=result_id_str,
                references=(ref1, ref2),
            ),
        ),
        references=trace_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id_str,
                "domain:sport",
                "domain-trace:probe",
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        duration_ms=0,
        metadata={},
    )
    expected_trace_id = probe.canonical_id

    # Build inventory independently BEFORE trace assembly
    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                result_id_str,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                "domain:sport",
            ),
            DomainTraceReference(
                "prof-001", DomainTraceReferenceKind.PROFILE, "domain:sport"
            ),
            DomainTraceReference(
                "rule-001", DomainTraceReferenceKind.RULE_RESULT, "domain:sport"
            ),
            DomainTraceReference(
                ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(comp_id, DomainTraceReferenceKind.COMPOSITION, None),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id="domain:sport",
                trace_id=expected_trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain="domain:sport",
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, "domain:sport", ()
        ),
        composition_domains=DomainTraceDomainSelection(comp_id, "domain:sport", ()),
    )

    # Assemble trace from upstream runtime references
    trace = assemble_sport_trace(
        request_id=req_id,
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        started_at=now,
        completed_at=now,
        references=(ref1, ref2),
    )
    assert trace.id == expected_trace_id

    val = validate_sport_trace(trace=trace, inventory=inventory)
    assert val.valid is True

    # Tampered reference absent from inventory fails
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

    # Fabricated domain result ID without inventory backing fails
    fake_result_trace = assemble_sport_trace(
        request_id="req-sport-001",
        resolution_context_id="ctx-001",
        resolution_result_id="res-001",
        composition_id="comp-001",
        domain_result_id="fabricated-result-999",
        started_at=now,
        completed_at=now,
        references=(ref1, ref2),
    )
    fake_val = validate_sport_trace(trace=fake_result_trace, inventory=inventory)
    assert fake_val.valid is False
