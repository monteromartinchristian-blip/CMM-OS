"""Phase 10.37 — Domain Observability Service.

Coordinates read-only projection only: pure metric calculation, read-only
per-domain health and privacy-minimized log/report construction.

The service owns no store, no repository, no bus, no runtime, no registry, no
resolver and no loader. It composes purely derived read models from canonical
evidence supplied by the caller.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from cmm.domains.observability_contracts import (
    DomainHealthResult,
    DomainMetricsSnapshot,
    DomainObservabilityLogEntry,
    DomainObservabilityReport,
)
from cmm.domains.observability_health import DomainHealthChecker
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)

# Stable projection categories (not a new event namespace).
_CATEGORY_BY_EVENT_TYPE_PREFIX: tuple[tuple[str, str], ...] = (
    ("domain.discovery.", "discovery"),
    ("domain.loading.", "loading"),
    ("domain.load.", "loading"),
    ("domain.resolution.", "resolution"),
    ("domain.composition.", "composition"),
    ("domain.conflict.", "conflict"),
    ("domain.profile.", "profile"),
    ("domain.rule.", "rule"),
    ("domain.resource.", "resource"),
    ("domain.operation.", "operation"),
    ("domain.workflow.", "workflow"),
    ("domain.permission.", "permission"),
    ("domain.approval.", "approval"),
    ("domain.cross_domain.", "cross_domain"),
    ("domain.session.", "session"),
    ("domain.memory.", "memory"),
    ("domain.error.", "error"),
)


def _category_for_event_type(event_type: str) -> str:
    for prefix, category in _CATEGORY_BY_EVENT_TYPE_PREFIX:
        if event_type.startswith(prefix):
            return category
    return "result"


class DomainObservabilityService:
    """Read-only projection coordinator for Phase 10.37 observability."""

    def __init__(
        self,
        *,
        metrics_calculator: DomainMetricsCalculator,
        health_checker: DomainHealthChecker,
        clock: Callable[[], datetime],
    ) -> None:
        self._metrics_calculator = metrics_calculator
        self._health_checker = health_checker
        self._clock = clock

    def calculate_metrics(
        self,
        evidence: DomainObservabilityEvidence,
    ) -> DomainMetricsSnapshot:
        """Project a metrics snapshot from canonical evidence."""
        return self._metrics_calculator.calculate(evidence, generated_at=self._clock())

    def check_domain_health(self, domain_id: str) -> DomainHealthResult:
        """Evaluate read-only health for one Domain."""
        return self._health_checker.check(domain_id)

    def build_report(
        self,
        evidence: DomainObservabilityEvidence,
        *,
        health_domain_ids: tuple[str, ...] = (),
    ) -> DomainObservabilityReport:
        """Build a deterministic, privacy-minimized observability report."""
        generated_at = self._clock()

        log_entries: tuple[DomainObservabilityLogEntry, ...] = ()
        for event in evidence.events:
            log_entries = (*log_entries, self._project_event(event))
        for trace in evidence.traces:
            log_entries = (*log_entries, self._project_trace(trace))

        for operation in evidence.operation_evidence:
            log_entries = (*log_entries, self._project_operation(operation))

        for workflow in evidence.workflow_evidence:
            log_entries = (*log_entries, self._project_workflow(workflow))

        for result in evidence.resolution_results:
            log_entries = (*log_entries, self._project_resolution(result))

        for composition in evidence.compositions:
            log_entries = (*log_entries, self._project_composition(composition))

        for conflict in evidence.conflict_results:
            log_entries = (*log_entries, self._project_conflict(conflict))

        for permission in evidence.permission_evidence:
            log_entries = (*log_entries, self._project_permission(permission))

        for approval in evidence.approval_evidence:
            log_entries = (*log_entries, self._project_approval(approval))

        for session in evidence.sessions:
            log_entries = (*log_entries, self._project_session(session))

        metrics = self._metrics_calculator.calculate(
            evidence, generated_at=generated_at
        )

        health_results = tuple(
            self._health_checker.check(domain_id) for domain_id in health_domain_ids
        )

        source_event_ids = tuple(sorted({event.event_id for event in evidence.events}))
        source_trace_ids = tuple(sorted({trace.id for trace in evidence.traces}))
        source_session_ids = tuple(
            sorted({session.session_id for session in evidence.sessions})
        )

        return DomainObservabilityReport(
            generated_at=generated_at,
            log_entries=log_entries,
            metrics=metrics,
            health_results=health_results,
            source_event_ids=source_event_ids,
            source_trace_ids=source_trace_ids,
            source_session_ids=source_session_ids,
        )

    # ── Reference-first projection helpers ────────────────────────────────
    # Each helper extracts only explicitly safe public fields. It NEVER copies
    # arbitrary payload/metadata wholesale.

    def _project_event(self, event: Any) -> DomainObservabilityLogEntry:
        supporting = tuple(str(domain_id) for domain_id in event.related_domain_ids)
        return DomainObservabilityLogEntry(
            source_kind="domain_event",
            source_id=event.event_id,
            category=_category_for_event_type(event.event_type),
            status=_event_status(event.event_type),
            occurred_at=event.occurred_at,
            primary_domain=str(event.domain_id),
            supporting_domains=supporting,
            session_id=event.session_id,
            reference_ids=tuple(
                sorted({reference.reference_id for reference in event.provenance})
            ),
            metadata={"event_type": event.event_type},
        )

    def _project_trace(self, trace: Any) -> DomainObservabilityLogEntry:
        supporting = tuple(str(domain_id) for domain_id in trace.supporting_domains)
        return DomainObservabilityLogEntry(
            source_kind="domain_trace",
            source_id=trace.id,
            category="result",
            status=str(trace.status.value),
            occurred_at=trace.started_at,
            primary_domain=str(trace.primary_domain),
            supporting_domains=supporting,
            duration_ms=trace.duration_ms,
            reference_ids=tuple(
                sorted({reference.ref_id for reference in trace.all_references()})
            ),
            metadata={
                "trace_status": str(trace.status.value),
                "request_id": trace.request_id,
            },
        )

    def _project_operation(self, result: Any) -> DomainObservabilityLogEntry:
        return DomainObservabilityLogEntry(
            source_kind="operation_result",
            source_id=result.result_id,
            category="operation",
            status=str(result.status.value),
            occurred_at=result.started_at,
            primary_domain=result.domain_id,
            duration_ms=_duration_ms(result.started_at, result.completed_at),
            reference_ids=tuple(
                sorted(
                    {
                        item
                        for item in (
                            result.transaction_id,
                            result.approval_request_id,
                        )
                        if item
                    }
                )
            ),
            metadata={
                "operation_id": result.operation_id,
                "operation_version": result.operation_version,
            },
        )

    def _project_workflow(self, result: Any) -> DomainObservabilityLogEntry:
        run = result.common_result.run
        return DomainObservabilityLogEntry(
            source_kind="workflow_result",
            source_id=result.run_id,
            category="workflow",
            status=str(run.status.value),
            occurred_at=run.started_at or self._clock(),
            primary_domain=result.domain_id,
            duration_ms=_duration_ms(run.started_at, run.completed_at),
            reference_ids=(result.run_id,),
            metadata={"workflow_id": run.workflow_id},
        )

    def _project_resolution(self, result: Any) -> DomainObservabilityLogEntry:
        return DomainObservabilityLogEntry(
            source_kind="resolution_result",
            source_id=result.id,
            category="resolution",
            status=str(result.status.value),
            occurred_at=result.resolved_at,
            primary_domain=str(result.primary_domain)
            if result.primary_domain
            else None,
            supporting_domains=tuple(
                str(domain_id) for domain_id in result.supporting_domains
            ),
            reference_ids=tuple(
                sorted({str(domain_id) for domain_id in result.ambiguous_domains})
            ),
            metadata={
                "confidence": _safe_float_metadata(result.confidence),
                "fallback_used": bool(result.fallback_used),
            },
        )

    def _project_composition(self, result: Any) -> DomainObservabilityLogEntry:
        return DomainObservabilityLogEntry(
            source_kind="composition_result",
            source_id=result.id,
            category="composition",
            status=str(result.status.value),
            occurred_at=result.composed_at,
            primary_domain=str(result.primary_domain),
            supporting_domains=tuple(
                str(domain_id) for domain_id in result.supporting_domains
            ),
            reference_ids=tuple(item for item in (result.resolution_id,) if item),
        )

    def _project_conflict(self, result: Any) -> DomainObservabilityLogEntry:
        return DomainObservabilityLogEntry(
            source_kind="conflict_case",
            source_id=result.id,
            category="conflict",
            status=str(result.status.value),
            occurred_at=self._clock(),
            supporting_domains=tuple(str(domain_id) for domain_id in result.domains),
            reference_ids=tuple(
                sorted({reference.ref_id for reference in result.references})
            ),
            metadata={
                "kind": result.kind.value
                if hasattr(result.kind, "value")
                else str(result.kind),
                "severity": result.severity.value
                if hasattr(result.severity, "value")
                else str(result.severity),
                "blocking": bool(result.blocking),
            },
        )

    def _project_permission(self, result: Any) -> DomainObservabilityLogEntry:
        outcome = getattr(result, "outcome", None)
        outcome_value = outcome.value if hasattr(outcome, "value") else str(outcome)
        return DomainObservabilityLogEntry(
            source_kind="permission_decision",
            source_id=str(
                getattr(result, "decision_id", None) or type(result).__name__
            ),
            category="permission",
            status=outcome_value,
            occurred_at=self._clock(),
            primary_domain=getattr(result, "domain_id", None),
            session_id=getattr(result, "session_id", None),
            reference_ids=tuple(
                str(item) for item in getattr(result, "reasons", ()) or ()
            ),
            metadata={"action": getattr(result, "action", None)},
        )

    def _project_approval(self, result: Any) -> DomainObservabilityLogEntry:
        requirement_id = getattr(result, "requirement_id", None)
        request_id = getattr(result, "request_id", None)
        source_id = requirement_id or request_id or type(result).__name__
        return DomainObservabilityLogEntry(
            source_kind="approval_evidence",
            source_id=str(source_id),
            category="approval",
            status="requested",
            occurred_at=self._clock(),
            primary_domain=getattr(result, "domain_id", None),
            session_id=getattr(result, "session_id", None),
            reference_ids=tuple(
                item
                for item in (
                    getattr(result, "operation_id", None),
                    getattr(result, "workflow_id", None),
                )
                if item
            ),
        )

    def _project_session(self, session: Any) -> DomainObservabilityLogEntry:
        return DomainObservabilityLogEntry(
            source_kind="session_context",
            source_id=session.session_id,
            category="session",
            status="active",
            occurred_at=self._clock(),
            primary_domain=session.primary_domain,
            supporting_domains=tuple(session.supporting_domains),
            reference_ids=tuple(
                sorted(
                    {
                        *session.trace_refs,
                        *session.approval_refs,
                        *session.domain_conflict_refs,
                    }
                )
            ),
        )


def _event_status(event_type: str) -> str:
    if event_type.endswith(".started"):
        return "started"
    if event_type.endswith(".failed"):
        return "failed"
    if event_type.endswith(".ambiguous"):
        return "ambiguous"
    if event_type.endswith(".blocked"):
        return "blocked"
    if event_type.endswith(".completed"):
        return "completed"
    return "recorded"


def _duration_ms(
    started_at: datetime | None, completed_at: datetime | None
) -> int | float | None:
    if started_at is None or completed_at is None:
        return None
    return (completed_at - started_at).total_seconds() * 1000


def _safe_float_metadata(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


__all__ = ["DomainObservabilityService"]
