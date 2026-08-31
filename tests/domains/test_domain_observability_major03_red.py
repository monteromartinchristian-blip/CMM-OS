"""Phase 10.37 — MAJOR-03 RED regressions: source precedence and
order-independent determinism.

Audit findings under test:

- A. evidence-order permutation: semantically equivalent evidence with
  different input tuple order must produce identical report/to_dict/digest.
- B. one clock capture per report: the report service must capture the clock
  exactly once per report request and derive all report timestamps from it.
- C. event → trace → result overlap: one logical occurrence must not be
  duplicated across DomainEvent / DomainTrace / canonical result.
- D. canonical final ordering: log entries have a stable explicit sort order;
  health results are ordered by Domain ID.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionStatus,
)
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReference,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
)
from cmm.domains.contracts import DomainId
from cmm.domains.enums import (
    DomainOperationStatus,
    DomainResolutionStatus,
)
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.health.bootstrap import build_standard_health_domain_bootstrap
from cmm.domains.observability_health import DomainHealthChecker
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.observability_service import DomainObservabilityService
from cmm.domains.operation_contracts import DomainOperationResult
from cmm.domains.resolver_contracts import (
    DomainResolutionResult,
)
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceContribution,
    DomainTraceReference,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
    DomainTraceStatus,
)
from cmm.domains.workflow_contracts import DomainWorkflowResult
from cmm.workflows.contracts import WorkflowResult, WorkflowRun
from cmm.workflows.enums import WorkflowRunStatus

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def _event(event_id: str) -> DomainEvent:
    return DomainEvent(
        event_id=event_id,
        event_type="domain.resolution.completed",
        schema_version="1.0",
        domain_id=DomainId.from_str("domain:health"),
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
    )


def _operation(result_id: str, operation_id: str) -> DomainOperationResult:
    return DomainOperationResult(
        result_id=result_id,
        request_id=f"req-{operation_id}",
        operation_id=operation_id,
        operation_version="1.0.0",
        domain_id="domain:health",
        status=DomainOperationStatus.COMPLETED,
        started_at=NOW - timedelta(seconds=1),
        completed_at=NOW,
    )


def _resolve(result_id: str) -> DomainResolutionResult:
    return DomainResolutionResult(
        id=result_id,
        context_id=f"ctx-{result_id}",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId.from_str("domain:health"),
        confidence=0.9,
    )


def _composition(composition_id: str) -> DomainComposition:
    return DomainComposition(
        id=composition_id,
        resolution_id=f"res-{composition_id}",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=DomainId.from_str("domain:health"),
        supporting_domains=(DomainId.from_str("domain:general"),),
        composed_at=NOW,
    )


def _trace(trace_id: str) -> DomainTrace:
    return DomainTrace(
        id=trace_id,
        digest="a" * 64,
        request_id=f"req-{trace_id}",
        primary_domain=DomainId.from_str("domain:health"),
        supporting_domains=(),
        contributions=(
            DomainTraceContribution(
                domain_id=DomainId.from_str("domain:health"),
                role=DomainTraceRole.PRIMARY,
                references=(),
            ),
        ),
        references=DomainTraceReferences(
            resolution_context_id=f"ctx-{trace_id}",
            resolution_result_id=f"res-{trace_id}",
            composition_id=f"comp-{trace_id}",
        ),
        domain_results=(),
        status=DomainTraceStatus.COMPLETED,
        started_at=NOW - timedelta(seconds=2),
        completed_at=NOW,
        duration_ms=2000,
    )


def _workflow(run_id: str, domain_id: str = "domain:health") -> DomainWorkflowResult:
    run = WorkflowRun(
        run_id=run_id,
        workflow_id=f"wf-{run_id}",
        workflow_version="1.0.0",
        status=WorkflowRunStatus.COMPLETED,
        started_at=NOW - timedelta(seconds=1),
        completed_at=NOW,
    )
    return DomainWorkflowResult(
        common_result=WorkflowResult(run=run),
        domain_id=domain_id,
    )


def _service(clock=None) -> DomainObservabilityService:
    bootstrap = build_standard_health_domain_bootstrap()
    health_checker = DomainHealthChecker(
        domain_registry=bootstrap.domain_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
        manifest_validation_lookup=lambda domain_id: None,
        clock=lambda: NOW,
    )
    return DomainObservabilityService(
        metrics_calculator=DomainMetricsCalculator(),
        health_checker=health_checker,
        clock=clock or (lambda: NOW),
    )


def _canonical_evidence() -> DomainObservabilityEvidence:
    return DomainObservabilityEvidence(
        events=(_event("evt-a"), _event("evt-b")),
        traces=(_trace("trace-a"), _trace("trace-b")),
        operation_evidence=(
            _operation("op-res-1", "op-1"),
            _operation("op-res-2", "op-2"),
        ),
        workflow_evidence=(_workflow("wf-1"), _workflow("wf-2")),
        resolution_results=(_resolve("res-1"), _resolve("res-2")),
        compositions=(_composition("comp-1"), _composition("comp-2")),
        conflict_results=(_conflict("conflict-1"), _conflict("conflict-2")),
    )


def _conflict(conflict_id: str) -> DomainConflictCase:
    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DECLARED_DOMAIN_CONFLICT,
        source_id=f"evidence-{conflict_id}",
        domain_id=DomainId.from_str("domain:health"),
        blocking=False,
        severity=DomainConflictSeverity.ADVISORY,
        authority_kind=DomainConflictAuthority.GLOBAL_SAFETY,
        evidence_refs=(),
    )
    return DomainConflictCase(
        id=conflict_id,
        domains=(
            DomainId.from_str("domain:health"),
            DomainId.from_str("domain:general"),
        ),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.ADVISORY,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
    )


# ── A. Evidence-order permutation ────────────────────────────────────────────


def test_permuted_evidence_produces_identical_report() -> None:
    """Reversed input order yields identical report, digest and metrics."""
    base = _canonical_evidence()
    reversed_evidence = DomainObservabilityEvidence(
        events=tuple(reversed(base.events)),
        traces=tuple(reversed(base.traces)),
        operation_evidence=tuple(reversed(base.operation_evidence)),
        workflow_evidence=tuple(reversed(base.workflow_evidence)),
        resolution_results=tuple(reversed(base.resolution_results)),
        compositions=tuple(reversed(base.compositions)),
        conflict_results=tuple(reversed(base.conflict_results)),
    )

    service = _service()
    first = service.build_report(base)
    second = service.build_report(reversed_evidence)

    assert first.to_dict() == second.to_dict()
    assert first.digest == second.digest
    assert first.metrics.to_dict() == second.metrics.to_dict()


def test_reversed_health_domain_order_identical_report() -> None:
    """Reversing health_domain_ids must not change report/digest."""
    service = _service()
    first = service.build_report(
        DomainObservabilityEvidence(),
        health_domain_ids=("domain:health", "domain:general"),
    )
    second = service.build_report(
        DomainObservabilityEvidence(),
        health_domain_ids=("domain:general", "domain:health"),
    )

    assert first.to_dict() == second.to_dict()
    assert first.digest == second.digest


# ── B. One clock capture per report ──────────────────────────────────────────


def test_report_captures_clock_exactly_once() -> None:
    """The report service calls the clock exactly once per report request."""
    calls: list[datetime] = []
    ticker = datetime(2026, 8, 31, 13, 0, 0, tzinfo=timezone.utc)

    def counting_clock() -> datetime:
        calls.append(ticker)
        return ticker

    service = _service(clock=counting_clock)
    evidence = DomainObservabilityEvidence(
        events=(_event("evt-a"),),
        traces=(_trace("trace-a"),),
        operation_evidence=(_operation("op-res-1", "op-1"),),
        workflow_evidence=(_workflow("wf-1"),),
        resolution_results=(_resolve("res-1"),),
        compositions=(_composition("comp-1"),),
        conflict_results=(_conflict("conflict-1"),),
    )
    service.build_report(evidence, health_domain_ids=("domain:health",))

    # metrics calculator itself captures its own clock; the service must
    # capture the clock exactly once for generated_at, and never call it
    # opportunistically inside _project_* helpers.
    assert len(calls) == 1


# ── C. Event → Trace → result overlap ────────────────────────────────────────


def test_shared_reference_occurrence_is_not_duplicated() -> None:
    """One logical occurrence represented by event+trace+result counts once.

    The three channels share an explicit canonical occurrence reference: the
    event's ``operation_run`` provenance, the trace's ``OPERATION_RESULT``
    contribution reference and the operation result's ``operation_id`` all
    resolve to the same operation occurrence reference. Source precedence
    keeps the DomainEvent as the single winning log entry.
    """
    event = DomainEvent(
        event_id="evt-shared-1",
        event_type="domain.operation.completed",
        schema_version="1.0",
        domain_id=DomainId.from_str("domain:health"),
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
        provenance=(
            DomainEventReference(
                kind="operation_run",
                reference_id="op-shared",
                domain_id=DomainId.from_str("domain:health"),
            ),
        ),
    )
    operation = _operation("op-res-shared", "op-shared")

    trace = DomainTrace(
        id="trace-shared-1",
        digest="b" * 64,
        request_id="req-shared",
        primary_domain=DomainId.from_str("domain:health"),
        supporting_domains=(),
        contributions=(
            DomainTraceContribution(
                domain_id=DomainId.from_str("domain:health"),
                role=DomainTraceRole.PRIMARY,
                references=(
                    DomainTraceReference(
                        ref_id="op-shared",
                        kind=DomainTraceReferenceKind.OPERATION_RESULT,
                        domain_id=DomainId.from_str("domain:health"),
                    ),
                ),
            ),
        ),
        references=DomainTraceReferences(
            resolution_context_id="ctx-shared",
            resolution_result_id="res-shared",
            composition_id="comp-shared",
        ),
        domain_results=(),
        status=DomainTraceStatus.COMPLETED,
        started_at=NOW - timedelta(seconds=2),
        completed_at=NOW,
        duration_ms=2000,
    )

    service = _service()
    report = service.build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            operation_evidence=(operation,),
        )
    )

    # The report must contain exactly 1 logical log occurrence for the three
    # channels, with the DomainEvent winning by source precedence.
    assert len(report.log_entries) == 1
    entry = report.log_entries[0]
    assert entry.source_kind == "domain_event"
    assert entry.source_id == "evt-shared-1"
    # Legitimate secondary references remain available on the winning entry.
    assert "op-shared" in entry.reference_ids


# ── D. Canonical final ordering ──────────────────────────────────────────────


def test_log_entries_have_stable_sort_order() -> None:
    """Log entries are ordered by (source_kind, source_id), not input order."""
    service = _service()
    evidence = DomainObservabilityEvidence(
        operation_evidence=(
            _operation("op-res-b", "op-b"),
            _operation("op-res-a", "op-a"),
        ),
        events=(_event("evt-z"), _event("evt-a")),
    )
    report = service.build_report(evidence)

    ids = [entry.source_id for entry in report.log_entries]
    assert ids == sorted(ids)
    kinds = [entry.source_kind for entry in report.log_entries]
    assert kinds == sorted(kinds)


def test_health_results_ordered_by_domain_id() -> None:
    """Health results are ordered by Domain ID."""
    service = _service()
    report = service.build_report(
        DomainObservabilityEvidence(),
        health_domain_ids=("domain:zebra", "domain:alpha"),
    )

    assert [r.domain_id for r in report.health_results] == sorted(
        r.domain_id for r in report.health_results
    )
