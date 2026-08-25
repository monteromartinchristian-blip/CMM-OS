"""Tests for Phase 10.28 Sport Domain Trace."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.trace_contracts import DomainTraceReferenceKind
from cmm.domains.sport.trace import (
    assemble_sport_trace,
    build_sport_trace_contribution,
    build_sport_trace_reference,
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
