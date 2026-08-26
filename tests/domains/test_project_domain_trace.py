"""Phase 10.30 — Project Domain Trace Integration Tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.identifiers import DomainId
from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.project.trace import (
    assemble_project_trace,
    build_project_trace_contribution,
    build_project_trace_reference,
    build_supporting_trace_contribution,
)
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceContribution,
    DomainTraceReference,
    DomainTraceReferenceKind,
    DomainTraceRole,
    DomainTraceStatus,
)


def test_build_project_trace_reference() -> None:
    ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    assert isinstance(ref, DomainTraceReference)
    assert ref.domain_id == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert ref.ref_id == "rule:project.scope_consistency:1.0.0"
    assert ref.kind == DomainTraceReferenceKind.RULE_RESULT


def test_build_project_trace_contribution_primary() -> None:
    ref = build_project_trace_reference(
        ref_id="op:project.review_status:1.0.0",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    contrib = build_project_trace_contribution(
        domain_result_id="res:project:1",
        references=(ref,),
    )
    assert isinstance(contrib, DomainTraceContribution)
    assert contrib.domain_id == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert contrib.role == DomainTraceRole.PRIMARY
    assert len(contrib.references) == 2


def test_build_supporting_trace_contribution() -> None:
    ref = build_project_trace_reference(
        ref_id="rule:life_plan:1",
        kind=DomainTraceReferenceKind.RULE_RESULT,
        domain_id="domain:life-plan",
    )
    contrib = build_supporting_trace_contribution(
        domain_result_id="res:life_plan:1",
        domain_id="domain:life-plan",
        references=(ref,),
    )
    assert isinstance(contrib, DomainTraceContribution)
    assert contrib.role == DomainTraceRole.SUPPORTING
    assert contrib.domain_id == DomainId.from_str("domain:life-plan")


def test_assemble_project_trace_reference_only() -> None:
    now = datetime.now(timezone.utc)
    ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    trace = assemble_project_trace(
        request_id="req:1",
        resolution_context_id="ctx:1",
        resolution_result_id="res_res:1",
        composition_id="comp:1",
        domain_result_id="res:project:1",
        references=(ref,),
        started_at=now,
        completed_at=now,
    )
    assert isinstance(trace, DomainTrace)
    assert trace.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert trace.status == DomainTraceStatus.COMPLETED
    assert trace.references.resolution_context_id == "ctx:1"
