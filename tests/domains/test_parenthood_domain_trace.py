"""Tests for Phase 10.27 Parenthood Domain Trace Integration."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.parenthood.trace import (
    assemble_parenthood_trace,
    build_parenthood_trace_contribution,
    build_parenthood_trace_reference,
    build_supporting_trace_contribution,
)
from cmm.domains.trace_contracts import (
    DomainTraceReferenceKind,
    DomainTraceRole,
    DomainTraceStatus,
)


def test_build_parenthood_trace_reference() -> None:
    """Verify building a trace reference owned by domain:parenthood."""
    ref = build_parenthood_trace_reference(
        ref_id="rule-res:parenthood.rule.minor_privacy",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    assert ref.ref_id == "rule-res:parenthood.rule.minor_privacy"
    assert str(ref.domain_id) == "domain:parenthood"
    assert ref.kind is DomainTraceReferenceKind.RULE_RESULT


def test_build_parenthood_trace_contribution() -> None:
    """Verify primary contribution creation."""
    contrib = build_parenthood_trace_contribution(
        domain_result_id="dom-res-001",
    )
    assert str(contrib.domain_id) == "domain:parenthood"
    assert contrib.role is DomainTraceRole.PRIMARY
    assert any(r.ref_id == "dom-res-001" for r in contrib.references)


def test_assemble_parenthood_trace() -> None:
    """Verify full trace assembly for parenthood."""
    now = datetime.now(timezone.utc)
    trace = assemble_parenthood_trace(
        request_id="trace-req-001",
        resolution_context_id="ctx-001",
        resolution_result_id="resol-res-001",
        composition_id="comp-001",
        domain_result_id="dom-res-001",
        started_at=now,
        completed_at=now,
        scope="parenthood.child:child:001",
        child_id="child:001",
    )
    assert trace.status is DomainTraceStatus.COMPLETED
    assert str(trace.primary_domain) == "domain:parenthood"
    assert trace.metadata.get("child_id") == "child:001"
    assert trace.metadata.get("scope") == "parenthood.child:child:001"
