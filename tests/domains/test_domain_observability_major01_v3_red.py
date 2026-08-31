"""Phase 10.37 — Audit V3 MAJOR-01 RED regressions: execution occurrence identity.

Audit defect: V3 treats ``DomainOperationResult.operation_id`` and
``WorkflowRun.workflow_id`` as occurrence keys. Those are definition/action
IDs, not unique execution IDs. Two real executions of the same operation
share ``operation_id`` while having distinct ``result_id``/``request_id``;
two runs of the same workflow share ``workflow_id`` while having distinct
``run_id``.

Canonical contract facts verified from the repository (not inferred):

- ``DomainOperationResult`` fields: ``result_id`` (generated fresh per
  execution by ``DefaultDomainOperationOrchestrator``), ``request_id``,
  ``operation_id`` (copied from the request), ``operation_version``.
- ``DomainWorkflowResult.run_id`` delegates to ``WorkflowRun.run_id``
  (generated per run by the canonical workflow engine); ``workflow_id`` is
  the definition being run.
- The canonical event adapters
  (``adapt_operation_started/completed/failed``,
  ``adapt_workflow_started/completed``) place the DEFINITION ID into
  ``DomainEventReference(kind="operation_run"/"workflow_run")`` — they never
  carry ``result_id``/``request_id``/``run_id``.
- ``DomainTraceReferenceKind.OPERATION_RESULT/WORKFLOW_RUN/WORKFLOW_RESULT``
  references are reference-only IDs; no canonical producer places a public
  result's execution identity into a trace reference.
- ``DomainOperationTraceEntry`` carries only code/status/occurred_at/
  reason_code/metadata — no event or trace IDs.

Therefore NO explicit canonical cross-channel execution-instance reference
exists between a public result and an Event/Trace. Per the remediation law:

- two same-definition executions MUST remain distinct occurrences;
- Event and Trace still merge when they share an explicit reference;
- a public result is NEVER suppressed through its definition ID.

Tests here must FAIL on the audited V3 code (which merges via definition IDs)
and PASS after the production fix.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cmm.domains.contracts import DomainId
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.event_adapters import (
    adapt_operation_completed,
    adapt_workflow_completed,
)
from cmm.domains.event_contracts import DomainEventReference
from cmm.domains.health.bootstrap import (
    build_standard_health_domain_bootstrap,
)
from cmm.domains.observability_health import DomainHealthChecker
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.observability_service import DomainObservabilityService
from cmm.domains.operation_contracts import DomainOperationResult
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
HEALTH = DomainId.from_str("domain:health")


def _service() -> DomainObservabilityService:
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
        clock=lambda: NOW,
    )


def _operation_result(
    result_id: str,
    request_id: str,
    operation_id: str = "health.build_summary",
) -> DomainOperationResult:
    """Two real canonical executions of the same operation definition."""
    return DomainOperationResult(
        result_id=result_id,
        request_id=request_id,
        operation_id=operation_id,
        operation_version="1.0.0",
        domain_id="domain:health",
        status=DomainOperationStatus.COMPLETED,
        started_at=NOW - timedelta(seconds=1),
        completed_at=NOW,
    )


def _workflow_result(run_id: str, workflow_id: str = "wf-summary") -> DomainWorkflowResult:
    """Two real canonical runs of the same workflow definition."""
    run = WorkflowRun(
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_version="1.0.0",
        status=WorkflowRunStatus.COMPLETED,
        started_at=NOW - timedelta(seconds=1),
        completed_at=NOW,
    )
    return DomainWorkflowResult(
        common_result=WorkflowResult(run=run),
        domain_id="domain:health",
    )


def _trace_referencing_operation(trace_id: str, ref_id: str) -> DomainTrace:
    """A canonical trace whose PRIMARY contribution references one operation."""
    return DomainTrace(
        id=trace_id,
        digest="a" * 64,
        request_id=f"req-{trace_id}",
        primary_domain=HEALTH,
        supporting_domains=(),
        contributions=(
            DomainTraceContribution(
                domain_id=HEALTH,
                role=DomainTraceRole.PRIMARY,
                references=(
                    DomainTraceReference(
                        ref_id=ref_id,
                        kind=DomainTraceReferenceKind.OPERATION_RESULT,
                        domain_id=HEALTH,
                    ),
                ),
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


def _event_with_reference(
    event_id: str, kind: str, reference_id: str
):
    from cmm.domains.event_contracts import DomainEvent

    return DomainEvent(
        event_id=event_id,
        event_type="domain.operation.completed",
        schema_version="1.0",
        domain_id=HEALTH,
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
        provenance=(
            DomainEventReference(
                kind=kind, reference_id=reference_id, domain_id=HEALTH
            ),
        ),
    )


def _operation_log_ids(report) -> tuple[str, ...]:
    return tuple(
        entry.source_id
        for entry in report.log_entries
        if entry.source_kind == "operation_result"
    )


def _workflow_log_ids(report) -> tuple[str, ...]:
    return tuple(
        entry.source_id
        for entry in report.log_entries
        if entry.source_kind == "workflow_result"
    )


# ── 7.2 Mandatory RED: two executions of one operation definition ────────────


def test_two_operation_executions_same_definition_remain_two() -> None:
    """same operation_id + same version, different result_id/request_id → 2."""
    first = _operation_result("domain-result:aaa", "request-1")
    second = _operation_result("domain-result:bbb", "request-2")
    assert first.operation_id == second.operation_id

    report = _service().build_report(
        DomainObservabilityEvidence(operation_evidence=(first, second))
    )

    assert _operation_log_ids(report) == ("domain-result:aaa", "domain-result:bbb")


def test_two_operation_executions_same_definition_metric_counts_two() -> None:
    """operations.by_domain counts both real executions."""
    first = _operation_result("domain-result:aaa", "request-1")
    second = _operation_result("domain-result:bbb", "request-2")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(operation_evidence=(first, second)),
        generated_at=NOW,
    )
    operations = next(
        item
        for item in snapshot.measurements
        if item.name == "operations.by_domain"
    )
    buckets = {bucket.key: bucket.value for bucket in operations.buckets}
    assert buckets == {"domain:health": 2}


def test_adapted_operation_events_do_not_merge_two_executions() -> None:
    """Canonical adapter events reference the DEFINITION ID; two real
    executions of that definition must still remain two distinct log
    occurrences (the events are separate channel entries, not occurrence
    collapses of the results)."""
    first = _operation_result("domain-result:aaa", "request-1")
    second = _operation_result("domain-result:bbb", "request-2")
    event = adapt_operation_completed("health.build_summary", "domain:health")

    report = _service().build_report(
        DomainObservabilityEvidence(
            events=(event,),
            operation_evidence=(first, second),
        )
    )

    # Both executions survive as distinct public-result occurrences.
    assert _operation_log_ids(report) == ("domain-result:aaa", "domain-result:bbb")
    # The canonical event remains its own (highest-precedence) entry; it was
    # not used to suppress either execution.
    event_entries = [
        entry
        for entry in report.log_entries
        if entry.source_kind == "domain_event"
    ]
    assert len(event_entries) == 1


# ── 7.3 Mandatory RED: two runs of one workflow definition ───────────────────


def test_two_workflow_runs_same_definition_remain_two() -> None:
    """same workflow_id, different run_id → 2 log occurrences."""
    first = _workflow_result("run-aaa")
    second = _workflow_result("run-bbb")
    assert first.common_result.run.workflow_id == "wf-summary"
    assert second.common_result.run.workflow_id == "wf-summary"

    report = _service().build_report(
        DomainObservabilityEvidence(workflow_evidence=(first, second))
    )

    assert _workflow_log_ids(report) == ("run-aaa", "run-bbb")


def test_two_workflow_runs_same_definition_metric_counts_two() -> None:
    """workflows.by_domain counts both real runs."""
    first = _workflow_result("run-aaa")
    second = _workflow_result("run-bbb")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(workflow_evidence=(first, second)),
        generated_at=NOW,
    )
    workflows = next(
        item
        for item in snapshot.measurements
        if item.name == "workflows.by_domain"
    )
    buckets = {bucket.key: bucket.value for bucket in workflows.buckets}
    assert buckets == {"domain:health": 2}


def test_adapted_workflow_event_does_not_merge_two_runs() -> None:
    """The canonical workflow adapter references the DEFINITION ID; two real
    runs of that definition remain two distinct log occurrences."""
    first = _workflow_result("run-aaa")
    second = _workflow_result("run-bbb")
    event = adapt_workflow_completed("wf-summary", "domain:health")

    report = _service().build_report(
        DomainObservabilityEvidence(
            events=(event,),
            workflow_evidence=(first, second),
        )
    )

    assert _workflow_log_ids(report) == ("run-aaa", "run-bbb")


# ── 7.4 Mandatory RED: genuinely linked operation occurrence ─────────────────


def test_linked_event_and_trace_merge_result_stays_distinct() -> None:
    """Event + Trace sharing an explicit canonical reference merge into one
    entry; the public result has NO canonical execution-instance reference
    into either channel, so it remains a distinct entry.

    The event/trace reference the operation DEFINITION ID — exactly what the
    canonical adapters (``adapt_operation_completed`` → ``operation_run``)
    place in references. The audited V3 code collapses all three channels
    through that definition ID; the fixed code merges only the genuinely
    linked Event/Trace pair and never suppresses the public result.
    """
    event = _event_with_reference(
        "evt-v3-linked", "operation_run", "health.build_summary"
    )
    trace = _trace_referencing_operation("trace-v3-linked", "health.build_summary")
    result = _operation_result("domain-result:linked", "request-linked")

    report = _service().build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            operation_evidence=(result,),
        )
    )

    assert len(report.log_entries) == 2
    event_entries = [
        entry
        for entry in report.log_entries
        if entry.source_kind == "domain_event"
    ]
    trace_entries = [
        entry
        for entry in report.log_entries
        if entry.source_kind == "domain_trace"
    ]
    # Precedence inside the genuinely linked pair: DomainEvent wins.
    assert len(event_entries) == 1
    assert len(trace_entries) == 0
    assert "health.build_summary" in tuple(event_entries[0].reference_ids)
    # The public result is never suppressed through its definition ID.
    assert _operation_log_ids(report) == ("domain-result:linked",)


def test_linked_event_trace_and_result_with_real_shared_ref_merge() -> None:
    """If the public result's result_id IS the explicit reference target of
    both channels (the only canonical execution-instance link the contracts
    support), all three channels genuinely merge to one entry."""
    result = _operation_result("domain-result:shared-ref", "request-shared-ref")
    event = _event_with_reference(
        "evt-v3-shared-ref", "operation_run", "domain-result:shared-ref"
    )
    trace = _trace_referencing_operation(
        "trace-v3-shared-ref", "domain-result:shared-ref"
    )

    report = _service().build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            operation_evidence=(result,),
        )
    )

    assert len(report.log_entries) == 1
    entry = report.log_entries[0]
    assert entry.source_kind == "domain_event"
    assert "domain-result:shared-ref" in tuple(entry.reference_ids)


# ── 7.5 Mandatory RED: genuinely linked workflow occurrence ──────────────────


def _trace_referencing_workflow(trace_id: str, ref_id: str) -> DomainTrace:
    return DomainTrace(
        id=trace_id,
        digest="b" * 64,
        request_id=f"req-{trace_id}",
        primary_domain=HEALTH,
        supporting_domains=(),
        contributions=(
            DomainTraceContribution(
                domain_id=HEALTH,
                role=DomainTraceRole.PRIMARY,
                references=(
                    DomainTraceReference(
                        ref_id=ref_id,
                        kind=DomainTraceReferenceKind.WORKFLOW_RESULT,
                        domain_id=HEALTH,
                    ),
                ),
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


def test_workflow_definition_reference_does_not_merge_runs() -> None:
    """A trace whose WORKFLOW_RESULT reference holds the workflow DEFINITION
    ID must not merge two real runs of that definition."""
    first = _workflow_result("run-aaa")
    second = _workflow_result("run-bbb")
    trace = _trace_referencing_workflow("trace-v3-wf", "wf-summary")

    report = _service().build_report(
        DomainObservabilityEvidence(
            traces=(trace,),
            workflow_evidence=(first, second),
        )
    )

    assert _workflow_log_ids(report) == ("run-aaa", "run-bbb")


def test_workflow_linked_event_trace_run_merge_on_run_id() -> None:
    """Event + Trace explicitly referencing the run_id merge with that run's
    public result into one entry (precedence: event wins)."""
    result = _workflow_result("run-shared-ref")
    event = _event_with_reference("evt-v3-wf", "workflow_run", "run-shared-ref")
    trace = _trace_referencing_workflow("trace-v3-wf-shared", "run-shared-ref")

    report = _service().build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            workflow_evidence=(result,),
        )
    )

    assert len(report.log_entries) == 1
    entry = report.log_entries[0]
    assert entry.source_kind == "domain_event"
    assert "run-shared-ref" in tuple(entry.reference_ids)


# ── 7.6 Mandatory RED: no fuzzy suppression ──────────────────────────────────


def test_same_domain_status_category_stays_distinct() -> None:
    """Two operation results with identical domain/status/timestamps but
    distinct result/request IDs remain distinct — no fuzzy collapse."""
    first = _operation_result("domain-result:aaa", "request-1")
    second = _operation_result("domain-result:bbb", "request-2")

    report = _service().build_report(
        DomainObservabilityEvidence(operation_evidence=(first, second))
    )

    assert len(report.log_entries) == 2


def test_definition_id_reuse_across_channels_does_not_collapse_results() -> None:
    """An event and a trace that both reference the DEFINITION ID do not
    suppress two distinct executions of that definition."""
    first = _operation_result("domain-result:aaa", "request-1")
    second = _operation_result("domain-result:bbb", "request-2")
    event = _event_with_reference("evt-v3-def", "operation_run", "health.build_summary")
    trace = _trace_referencing_operation("trace-v3-def", "health.build_summary")

    report = _service().build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            operation_evidence=(first, second),
        )
    )

    # Event+Trace merge (they share the explicit definition reference), but
    # both public executions remain distinct entries.
    kinds = sorted(entry.source_kind for entry in report.log_entries)
    assert kinds == ["domain_event", "operation_result", "operation_result"]
    assert _operation_log_ids(report) == ("domain-result:aaa", "domain-result:bbb")


# ── 7.7 Determinism after occurrence-key correction ──────────────────────────


def test_permuted_occurrence_evidence_is_digest_stable() -> None:
    """same evidence reordered → same log_entries → same report/digest."""
    event = _event_with_reference("evt-v3-det", "operation_run", "op-ref-det")
    trace = _trace_referencing_operation("trace-v3-det", "op-ref-det")
    first = _operation_result("domain-result:det-1", "request-det-1")
    second = _operation_result("domain-result:det-2", "request-det-2")

    service = _service()
    forward = service.build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            operation_evidence=(first, second),
        )
    )
    backward = service.build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            operation_evidence=(second, first),
        )
    )

    assert forward.log_entries == backward.log_entries
    assert forward.to_dict() == backward.to_dict()
    assert forward.digest == backward.digest
