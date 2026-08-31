"""Phase 10.37 — Domain Observability Service.

Coordinates read-only projection only: pure metric calculation, read-only
per-domain health and privacy-minimized log/report construction.

The service owns no store, no repository, no bus, no runtime, no registry, no
resolver and no loader. It composes purely derived read models from canonical
evidence supplied by the caller.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any

from cmm.domains.errors import InvalidDomainObservabilityEvidenceError
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
    _normalize_evidence,
)
from cmm.domains.permission_adapters import DomainOperationPermissionDecision
from cmm.domains.trace_contracts import DomainTraceReferenceKind

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


# ── Source precedence ────────────────────────────────────────────────────────
#
# One logical occurrence may be represented through multiple canonical
# channels (DomainEvent → DomainTrace → canonical public result). The report
# MUST produce one log entry per logical occurrence with an explicit source
# precedence:
#
#   domain_event (1) wins over domain_trace (2) wins over public results (3+)
#
# Occurrence identity is derived ONLY from explicit canonical references —
# never from fuzzy content, co-location, category/status/domain similarity or
# timestamp proximity. A public result that has no explicit reference link to
# an Event/Trace can never be suppressed merely because it "looks similar".

_SOURCE_PRECEDENCE: dict[str, int] = {
    "domain_event": 1,
    "domain_trace": 2,
    "operation_result": 3,
    "workflow_result": 4,
    "resolution_result": 5,
    "composition_result": 6,
    "conflict_case": 7,
    "permission_decision": 8,
    "approval_evidence": 9,
    "session_context": 10,
}

# Canonical event-provenance reference kinds, normalized to occurrence
# categories (matching the trace reference-kind categories below so that an
# event and a trace can resolve to the SAME logical occurrence reference).
_EVENT_REF_KIND_TO_OCCURRENCE: dict[str, str] = {
    "operation_run": "operation",
    "workflow_run": "workflow",
    "composition": "composition",
    "resolution": "resolution",
    "conflict_case": "conflict",
    "conflict_resolution": "conflict",
    "approval": "approval",
    "memory_proposal": "memory",
    "memory_update": "memory",
    "execution": "execution",
}

_TRACE_KIND_TO_OCCURRENCE: dict[DomainTraceReferenceKind, str] = {
    DomainTraceReferenceKind.OPERATION_RESULT: "operation",
    DomainTraceReferenceKind.WORKFLOW_RUN: "workflow",
    DomainTraceReferenceKind.WORKFLOW_RESULT: "workflow",
    DomainTraceReferenceKind.COMPOSITION: "composition",
    DomainTraceReferenceKind.RESOLUTION_RESULT: "resolution",
    DomainTraceReferenceKind.RESOLUTION_CONTEXT: "resolution",
    DomainTraceReferenceKind.PERMISSION_DECISION: "permission",
    DomainTraceReferenceKind.APPROVAL_REQUEST: "approval",
    DomainTraceReferenceKind.APPROVAL_DECISION: "approval",
    DomainTraceReferenceKind.RULE_RESULT: "rule",
    DomainTraceReferenceKind.APPLIED_RULE_TRACE: "rule",
    DomainTraceReferenceKind.RESOURCE_RESOLUTION: "resource",
    DomainTraceReferenceKind.KNOWLEDGE_PACKAGE: "knowledge",
    DomainTraceReferenceKind.MEMORY_PROPOSAL: "memory",
    DomainTraceReferenceKind.MEMORY_BINDING: "memory",
    DomainTraceReferenceKind.CROSS_DOMAIN_RESULT: "cross_domain",
    DomainTraceReferenceKind.CROSS_DOMAIN_TRACE: "cross_domain",
    DomainTraceReferenceKind.FINDING: "finding",
}

_OCCURRENCE_KEY = frozenset[tuple[str, str]]


def _event_occurrence_keys(event: Any) -> _OCCURRENCE_KEY:
    """Explicit occurrence references for one DomainEvent.

    The event's own ID is always an occurrence reference; each provenance
    reference contributes its canonical occurrence reference. Provenance
    references are the canonical way an event links to an operation/workflow/
    composition/resolution occurrence.
    """
    keys = {("domain_event", event.event_id)}
    for reference in getattr(event, "provenance", ()) or ():
        occurrence_kind = _EVENT_REF_KIND_TO_OCCURRENCE.get(reference.kind)
        if occurrence_kind is not None:
            keys.add((occurrence_kind, reference.reference_id))
    return frozenset(keys)


def _trace_occurrence_keys(trace: Any) -> _OCCURRENCE_KEY:
    """Explicit occurrence references for one DomainTrace.

    The trace's own ID is always an occurrence reference; every canonical
    trace reference contributes its occurrence reference. This is how a trace
    links to the same operation/workflow/composition occurrence referenced by
    an event provenance reference or a public result.
    """
    keys = {("domain_trace", trace.id)}
    for reference in trace.all_references():
        occurrence_kind = _TRACE_KIND_TO_OCCURRENCE.get(reference.kind)
        if occurrence_kind is not None:
            keys.add((occurrence_kind, reference.ref_id))
    return frozenset(keys)


def _operation_occurrence_keys(result: Any) -> _OCCURRENCE_KEY:
    """Explicit occurrence references for one DomainOperationResult.

    The result occurrence ID (``result_id``) is the self reference; the
    canonical ``operation_id`` is the logical operation occurrence reference
    shared with ``operation_run`` event provenance and ``OPERATION_RESULT``
    trace references.
    """
    return frozenset(
        {
            ("operation_result", result.result_id),
            ("operation", result.operation_id),
        }
    )


def _workflow_occurrence_keys(result: Any) -> _OCCURRENCE_KEY:
    """Explicit occurrence references for one DomainWorkflowResult."""
    run = result.common_result.run
    return frozenset(
        {
            ("workflow_result", result.run_id),
            ("workflow", run.workflow_id),
        }
    )


def _resolution_occurrence_keys(result: Any) -> _OCCURRENCE_KEY:
    """Explicit occurrence references for one DomainResolutionResult."""
    return frozenset(
        {
            ("resolution_result", result.id),
            ("resolution", result.id),
        }
    )


def _composition_occurrence_keys(result: Any) -> _OCCURRENCE_KEY:
    """Explicit occurrence references for one DomainComposition."""
    return frozenset({("composition", result.id)})


def _conflict_occurrence_keys(result: Any) -> _OCCURRENCE_KEY:
    """Explicit occurrence references for one DomainConflictCase."""
    return frozenset({("conflict", result.id)})


def _permission_occurrence_keys(result: Any) -> _OCCURRENCE_KEY:
    return frozenset({("permission", _permission_decision_id(result))})


def _approval_occurrence_keys(result: Any) -> _OCCURRENCE_KEY:
    requirement_id = getattr(result, "requirement_id", None)
    return frozenset(
        {
            ("approval", requirement_id)
            if requirement_id
            else ("approval", type(result).__name__)
        }
    )


def _session_occurrence_keys(result: Any) -> _OCCURRENCE_KEY:
    return frozenset({("session", result.session_id)})


def _normalize_log_occurrences(
    projected: Sequence[tuple[DomainObservabilityLogEntry, _OCCURRENCE_KEY]],
) -> tuple[DomainObservabilityLogEntry, ...]:
    """Normalize projected log entries into ONE entry per logical occurrence.

    Two entries represent the same logical occurrence only when they share an
    explicit canonical occurrence reference (a common key). Within each merged
    occurrence the highest-precedence source wins:
    ``domain_event → domain_trace → public result``. Legitimate secondary
    reference IDs of the suppressed sources are preserved in the winning
    entry's ``reference_ids`` (safe refs only, no payload duplication).

    Conflicting same-source identity is handled before projection by evidence
    normalization (identical canonical duplicates collapse, conflicts fail
    closed). This stage only merges cross-channel representations of one
    explicit occurrence, then sorts canonically.
    """
    items = list(projected)

    # Union-find over shared explicit occurrence references. The grouping is
    # order-independent because it is the transitive closure of a pure
    # key-intersection relation.
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        root_a = find(first)
        root_b = find(second)
        if root_a != root_b:
            parent[root_a] = root_b

    key_index: dict[tuple[str, str], int] = {}
    for index, (_entry, keys) in enumerate(items):
        for key in keys:
            if key in key_index:
                union(index, key_index[key])
            else:
                key_index[key] = index

    groups: dict[int, list[int]] = {}
    for index in range(len(items)):
        groups.setdefault(find(index), []).append(index)

    winners: list[DomainObservabilityLogEntry] = []
    for indices in groups.values():
        entries = [items[index][0] for index in indices]
        ordered = sorted(
            entries,
            key=lambda entry: (
                _SOURCE_PRECEDENCE.get(entry.source_kind, 99),
                entry.source_kind,
                entry.source_id,
            ),
        )
        winner = ordered[0]
        merged_reference_ids = tuple(
            sorted(
                {reference for entry in entries for reference in entry.reference_ids}
            )
        )
        if merged_reference_ids != winner.reference_ids:
            winner = replace(winner, reference_ids=merged_reference_ids)
        winners.append(winner)

    return tuple(
        sorted(winners, key=lambda entry: (entry.source_kind, entry.source_id))
    )


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
        """Build a deterministic, privacy-minimized observability report.

        Determinism laws:
        - the clock is captured exactly once per report request; every derived
          report timestamp comes from the captured ``generated_at``;
        - log entries are sorted canonically by ``(source_kind, source_id)``;
        - health results are ordered by Domain ID;
        - health_domain_ids are deduplicated and sorted before evaluation.
        """
        generated_at = self._clock()

        # Occurrence normalization happens BEFORE log projection:
        #  - identical same-source canonical evidence collapses to one entry;
        #  - conflicting same-source identity fails closed;
        #  - cross-channel representations of one explicit occurrence merge
        #    with source precedence (event → trace → public result).
        normalized = _normalize_evidence(evidence)

        projected: list[
            tuple[DomainObservabilityLogEntry, frozenset[tuple[str, str]]]
        ] = []
        for event in normalized.events:
            projected.append(
                (self._project_event(event), _event_occurrence_keys(event))
            )
        for trace in normalized.traces:
            projected.append(
                (self._project_trace(trace), _trace_occurrence_keys(trace))
            )

        for operation in normalized.operation_evidence:
            projected.append(
                (
                    self._project_operation(operation),
                    _operation_occurrence_keys(operation),
                )
            )

        for workflow in normalized.workflow_evidence:
            projected.append(
                (
                    self._project_workflow(workflow, generated_at),
                    _workflow_occurrence_keys(workflow),
                )
            )

        for result in normalized.resolution_results:
            projected.append(
                (self._project_resolution(result), _resolution_occurrence_keys(result))
            )

        for composition in normalized.compositions:
            projected.append(
                (
                    self._project_composition(composition),
                    _composition_occurrence_keys(composition),
                )
            )

        for conflict in normalized.conflict_results:
            projected.append(
                (
                    self._project_conflict(conflict, generated_at),
                    _conflict_occurrence_keys(conflict),
                )
            )

        for permission in normalized.permission_evidence:
            projected.append(
                (
                    self._project_permission(permission, generated_at),
                    _permission_occurrence_keys(permission),
                )
            )

        for approval in normalized.approval_evidence:
            projected.append(
                (
                    self._project_approval(approval, generated_at),
                    _approval_occurrence_keys(approval),
                )
            )

        for session in normalized.sessions:
            projected.append(
                (
                    self._project_session(session, generated_at),
                    _session_occurrence_keys(session),
                )
            )

        # One logical occurrence per explicit canonical reference, then a
        # canonical final sort by (source_kind, source_id).
        log_entries = _normalize_log_occurrences(projected)

        metrics = self._metrics_calculator.calculate(
            evidence, generated_at=generated_at
        )

        health_domain_ids_sorted = tuple(
            sorted({domain_id for domain_id in health_domain_ids})
        )
        health_results = tuple(
            self._health_checker.check(domain_id)
            for domain_id in health_domain_ids_sorted
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

    def _project_workflow(
        self, result: Any, generated_at: datetime
    ) -> DomainObservabilityLogEntry:
        run = result.common_result.run
        return DomainObservabilityLogEntry(
            source_kind="workflow_result",
            source_id=result.run_id,
            category="workflow",
            status=str(run.status.value),
            occurred_at=run.started_at or generated_at,
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

    def _project_conflict(
        self, result: Any, generated_at: datetime
    ) -> DomainObservabilityLogEntry:
        return DomainObservabilityLogEntry(
            source_kind="conflict_case",
            source_id=result.id,
            category="conflict",
            status=str(result.status.value),
            occurred_at=generated_at,
            supporting_domains=tuple(str(domain_id) for domain_id in result.domains),
            reference_ids=tuple(
                sorted({reference.source_id for reference in result.references})
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

    def _project_permission(
        self, result: Any, generated_at: datetime
    ) -> DomainObservabilityLogEntry:
        """Project one canonical ``DomainOperationPermissionDecision``.

        The canonical permission contract exposes

        ``operation_id / operation_version / decision / reasons /
        approval_requirements / requirement_decisions / provenance /
        effective_constraints``

        and does NOT expose ``outcome``, ``decision_id``, ``domain_id`` or
        ``action``. The projection reads only canonical safe fields: the
        status is ``decision.value``, the stable source identity binds
        ``operation_id + operation_version``, and the explicit metadata
        allowlist carries those two safe identifiers. Reason/approval text is
        never copied.
        """
        if isinstance(result, DomainOperationPermissionDecision):
            return DomainObservabilityLogEntry(
                source_kind="permission_decision",
                source_id=_permission_decision_id(result),
                category="permission",
                status=result.decision.value,
                occurred_at=generated_at,
                primary_domain=None,
                session_id=None,
                reference_ids=tuple(
                    item
                    for item in (
                        result.operation_id,
                        result.operation_version,
                    )
                    if item
                ),
                metadata={
                    "operation_id": result.operation_id,
                    "operation_version": result.operation_version,
                },
            )
        # Non-canonical permission evidence has no stable public projection.
        raise InvalidDomainObservabilityEvidenceError(
            "permission evidence must be a canonical DomainOperationPermissionDecision",
            field="permission_evidence",
            details={
                "source_type": type(result).__name__,
                "source_id": "",
            },
        )

    def _project_approval(
        self, result: Any, generated_at: datetime
    ) -> DomainObservabilityLogEntry:
        requirement_id = getattr(result, "requirement_id", None)
        request_id = getattr(result, "request_id", None)
        source_id = requirement_id or request_id or type(result).__name__
        return DomainObservabilityLogEntry(
            source_kind="approval_evidence",
            source_id=str(source_id),
            category="approval",
            status="requested",
            occurred_at=generated_at,
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

    def _project_session(
        self, session: Any, generated_at: datetime
    ) -> DomainObservabilityLogEntry:
        return DomainObservabilityLogEntry(
            source_kind="session_context",
            source_id=session.session_id,
            category="session",
            status="active",
            occurred_at=generated_at,
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


def _permission_decision_id(decision: DomainOperationPermissionDecision) -> str:
    """Stable canonical permission decision identity.

    Binds ``operation_id`` + ``operation_version`` so that two DENY decisions
    for the same operation at distinct semantic versions are distinct
    decisions while identical decisions project to identical IDs. Never a
    class name.
    """
    return f"permission:{decision.operation_id}:{decision.operation_version}"


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
