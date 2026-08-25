"""Tests for Phase 10.29 Life Plan Domain Trace."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.contracts import DomainResult
from cmm.domains.life_plan.catalog import LIFE_PLAN_DOMAIN_ID
from cmm.domains.life_plan.trace import (
    assemble_life_plan_trace,
    build_life_plan_trace_contribution,
    build_life_plan_trace_reference,
    build_supporting_trace_contribution,
    validate_life_plan_trace,
)
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTrace,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
    DomainTraceStatus,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def test_build_life_plan_trace_reference() -> None:
    ref = build_life_plan_trace_reference(
        ref_id="rule:life_plan.rule.decision_status",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    assert ref.ref_id == "rule:life_plan.rule.decision_status"
    assert ref.domain_id == LIFE_PLAN_DOMAIN_ID
    assert ref.kind == DomainTraceReferenceKind.RULE_RESULT


def test_build_life_plan_trace_contribution() -> None:
    contrib = build_life_plan_trace_contribution(
        domain_result_id="res-01",
    )
    assert contrib.domain_id == LIFE_PLAN_DOMAIN_ID
    assert contrib.role == DomainTraceRole.PRIMARY
    assert any(r.ref_id == "res-01" for r in contrib.references)


def test_build_supporting_trace_contribution() -> None:
    contrib = build_supporting_trace_contribution(
        domain_result_id="res-health-01",
        domain_id="domain:health",
    )
    assert str(contrib.domain_id) == "domain:health"
    assert contrib.role == DomainTraceRole.SUPPORTING


def test_assemble_and_validate_life_plan_trace() -> None:
    upstream_domain_result = DomainResult(
        id="dres-001",
        status="completed",
        objective="Life Plan long term decision evaluation",
        primary_domain=LIFE_PLAN_DOMAIN_ID,
        supporting_domains=("domain:health",),
    )

    ref1 = build_life_plan_trace_reference(
        ref_id="prof-001", kind=DomainTraceReferenceKind.PROFILE
    )
    ref2 = build_life_plan_trace_reference(
        ref_id="rule-001", kind=DomainTraceReferenceKind.RULE_RESULT
    )
    result_id_str = str(upstream_domain_result.id)

    req_id = "req-lp-001"
    ctx_id = "ctx-001"
    res_id = "res-001"
    comp_id = "comp-001"

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
        primary_domain=LIFE_PLAN_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            build_life_plan_trace_contribution(
                domain_result_id=result_id_str,
                references=(ref1, ref2),
            ),
        ),
        references=trace_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id_str,
                LIFE_PLAN_DOMAIN_ID,
                "domain-trace:probe",
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
        duration_ms=0,
        metadata={},
    )
    expected_trace_id = probe.canonical_id

    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                result_id_str,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                LIFE_PLAN_DOMAIN_ID,
            ),
            DomainTraceReference(
                "prof-001", DomainTraceReferenceKind.PROFILE, LIFE_PLAN_DOMAIN_ID
            ),
            DomainTraceReference(
                "rule-001", DomainTraceReferenceKind.RULE_RESULT, LIFE_PLAN_DOMAIN_ID
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
                domain_id=LIFE_PLAN_DOMAIN_ID,
                trace_id=expected_trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=LIFE_PLAN_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, LIFE_PLAN_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(
            comp_id, LIFE_PLAN_DOMAIN_ID, ()
        ),
    )

    trace = assemble_life_plan_trace(
        request_id=req_id,
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        started_at=NOW,
        completed_at=NOW,
        references=(ref1, ref2),
    )
    assert trace.id == expected_trace_id

    val = validate_life_plan_trace(trace=trace, inventory=inventory)
    assert val.valid is True
