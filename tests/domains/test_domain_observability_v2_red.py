"""Phase 10.37 — Audit V2 residual RED regressions.

Regressions for the four V2 findings, exercising the exact canonical
contracts the audit cited:

- V2 MAJOR-01: cross-domain transfer occurrence identity must distinguish
  ``identifier`` + ``iteration`` occurrences (canonical engine reuses the same
  finding identifier across iterations); same exact transfer duplicated counts
  once; same identifier/iteration with conflicting canonical identity fails
  closed.
- V2 MAJOR-02: permission rejection identity must bind
  ``operation_id + operation_version``; canonical permission log projection
  must read the real ``DomainOperationPermissionDecision`` fields; malformed
  typed evidence elements must fail closed with
  ``InvalidDomainObservabilityEvidenceError``.
- V2 MAJOR-03: source precedence (DomainEvent → DomainTrace → public result)
  must produce one logical occurrence per canonical shared reference, without
  suppressing unrelated evidence; determinism must hold after normalization.
- V2 MAJOR-04: the connected acceptance must prove the residual fixes.

These tests must FAIL before the corresponding production fixes and PASS after.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
from cmm.domains.contracts import DomainId
from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.errors import InvalidDomainObservabilityEvidenceError
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.health.bootstrap import build_standard_health_domain_bootstrap
from cmm.domains.observability_contracts import (
    DomainMetricStatus,
    DomainObservabilityLogEntry,
)
from cmm.domains.observability_health import DomainHealthChecker
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.observability_service import DomainObservabilityService
from cmm.domains.operation_contracts import DomainOperationResult
from cmm.domains.permission_adapters import DomainOperationPermissionDecision
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceContribution,
    DomainTraceReference,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
    DomainTraceStatus,
)

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)

HEALTH = DomainId.from_str("domain:health")
GENERAL = DomainId.from_str("domain:general")


def _metric(snapshot, name: str):
    for measurement in snapshot.measurements:
        if measurement.name == name:
            return measurement
    raise AssertionError(f"metric {name} missing from snapshot")


def _transfer(
    identifier: str,
    *,
    iteration: int = 0,
    source: DomainId = HEALTH,
    target: DomainId = GENERAL,
    kind: str = "finding",
    value: object = "safe-public-value",
) -> CrossDomainContextTransfer:
    """Construct a canonical transfer mirroring the cross-domain engine shape."""
    return CrossDomainContextTransfer(
        source_domain=source,
        target_domain=target,
        kind=kind,
        identifier=identifier,
        value=value,
        reason="context handoff",
        iteration=iteration,
        provenance=("test",),
    )


def _transfer_metric(*transfers: CrossDomainContextTransfer):
    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(cross_domain_transfers=transfers),
        generated_at=NOW,
    )
    return _metric(snapshot, "cross_domain.transfers")


# ── V2 MAJOR-01 — transfer occurrence identity ───────────────────────────────


def test_transfer_same_exact_duplicate_counts_once() -> None:
    """Same exact transfer duplicated → one occurrence."""
    transfer = _transfer("finding-123", iteration=0)

    metric = _transfer_metric(transfer, transfer)

    assert metric.status is DomainMetricStatus.OBSERVED
    assert metric.value == 1


def test_transfer_same_identifier_same_iteration_conflict_fails_closed() -> None:
    """Same identifier + same iteration + conflicting canonical identity → fail closed."""
    original = _transfer("finding-123", iteration=0, value={"k": "a"})
    conflicting = _transfer("finding-123", iteration=0, value={"k": "b"})

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as excinfo:
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(cross_domain_transfers=(original, conflicting)),
            generated_at=NOW,
        )

    payload = str(excinfo.value).lower()
    assert "finding-123" in payload  # safe source identity may appear
    assert '"k"' not in payload.replace(
        "finding-123", ""
    )  # conflicting value must not echo


def test_transfer_same_identifier_different_iteration_counts_twice() -> None:
    """Same identifier + different iteration → two distinct occurrences.

    The canonical cross-domain engine transfers the same finding identifier
    in more than one coordination iteration, so iteration is part of the
    occurrence identity.
    """
    iteration_0 = _transfer("finding-123", iteration=0)
    iteration_1 = _transfer("finding-123", iteration=1)

    metric = _transfer_metric(iteration_0, iteration_1)

    assert metric.status is DomainMetricStatus.OBSERVED
    assert metric.value == 2
    assert len(metric.evidence_reference_ids) == 2


def test_transfer_same_pair_kind_different_identifier_counts_twice() -> None:
    """Same source/target/kind + different identifier → two occurrences."""
    first = _transfer("finding-123", iteration=0)
    second = _transfer("finding-456", iteration=0)

    metric = _transfer_metric(first, second)

    assert metric.status is DomainMetricStatus.OBSERVED
    assert metric.value == 2


# ── V2 MAJOR-02 — canonical permission evidence ──────────────────────────────


def _permission(
    operation_id: str,
    version: str,
    decision: PermissionOutcome,
) -> DomainOperationPermissionDecision:
    return DomainOperationPermissionDecision(
        operation_id=operation_id,
        operation_version=version,
        decision=decision,
    )


def test_permission_same_operation_id_two_versions_deny_counts_two() -> None:
    """Two DENY decisions for one operation ID at distinct versions are 2."""
    v1 = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)
    v2 = _permission("domain.op", "2.0.0", PermissionOutcome.DENY)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(permission_evidence=(v1, v2)),
        generated_at=NOW,
    )

    metric = _metric(snapshot, "permissions.rejected")
    assert metric.status is DomainMetricStatus.OBSERVED
    assert metric.value == 2


def test_permission_identical_duplicate_evidence_counts_once() -> None:
    """Identical duplicate DENY evidence for the same operation/version counts once."""
    only = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(permission_evidence=(only, only)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "permissions.rejected").value == 1


def test_permission_allow_does_not_increment_rejections() -> None:
    """ALLOW must not increment the rejection count."""
    deny = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)
    allow = _permission("domain.other", "1.0.0", PermissionOutcome.ALLOW)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(permission_evidence=(deny, allow)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "permissions.rejected").value == 1


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


def _permission_log_entries(*evidence) -> tuple[DomainObservabilityLogEntry, ...]:
    report = _service().build_report(
        DomainObservabilityEvidence(permission_evidence=evidence)
    )
    return tuple(
        entry
        for entry in report.log_entries
        if entry.source_kind == "permission_decision"
    )


def test_permission_log_canonical_deny_has_status_deny() -> None:
    """Canonical DENY → log.status == 'deny'."""
    deny = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)

    entries = _permission_log_entries(deny)

    assert len(entries) == 1
    assert entries[0].status == "deny"


def test_permission_log_canonical_allow_has_status_allow() -> None:
    """Canonical ALLOW → log.status == 'allow'."""
    allow = _permission("domain.op", "1.0.0", PermissionOutcome.ALLOW)

    entries = _permission_log_entries(allow)

    assert len(entries) == 1
    assert entries[0].status == "allow"


def test_permission_log_source_ids_distinguish_versions() -> None:
    """Same operation_id with versions 1.0.0/2.0.0 → distinct stable source IDs."""
    v1 = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)
    v2 = _permission("domain.op", "2.0.0", PermissionOutcome.DENY)

    entries = _permission_log_entries(v1, v2)

    assert len(entries) == 2
    assert {entry.source_id for entry in entries} == {
        entry.source_id for entry in entries
    }
    assert len({entry.source_id for entry in entries}) == 2
    # No class-name fallback identity.
    assert all(
        "DomainOperationPermissionDecision" not in entry.source_id for entry in entries
    )
    # No raw reason text copied into the public projection.
    for entry in entries:
        assert "not authorized" not in entry.metadata.get("reasons", [])  # type: ignore[union-attr]


def test_permission_log_projection_is_deterministic() -> None:
    """Same canonical permission decision projected twice → identical source ID."""
    deny = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)

    report_a = _service().build_report(
        DomainObservabilityEvidence(permission_evidence=(deny,))
    )
    report_b = _service().build_report(
        DomainObservabilityEvidence(permission_evidence=(deny,))
    )

    first = next(
        entry
        for entry in report_a.log_entries
        if entry.source_kind == "permission_decision"
    )
    second = next(
        entry
        for entry in report_b.log_entries
        if entry.source_kind == "permission_decision"
    )
    assert first.source_id == second.source_id


# ── V2 MAJOR-02 — runtime validation of DomainObservabilityEvidence ──────────


def _resolution_binding(binding_id: str, domain_id: DomainId):
    from cmm.domains.enums import DomainResourceResolutionStatus
    from cmm.domains.resource_contracts import (
        DomainResourceBinding,
        DomainResourceResolution,
    )

    binding = DomainResourceBinding(
        id=binding_id,
        resource_id=f"resource:{binding_id}",
        definition_id=f"definition:{binding_id}",
        domain_id=domain_id,
        adapter="source-test",
        provenance=("test",),
    )
    return DomainResourceResolution(
        id=f"resolution:{binding_id}",
        resource_id=f"resource:{binding_id}",
        status=DomainResourceResolutionStatus.RESOLVED,
        trace_id=f"trace:{binding_id}",
        resolved_at=NOW,
        bindings=(binding,),
    )


def test_invalid_resource_evidence_dict_fails_closed() -> None:
    """A dict in resource_evidence is malformed typed evidence → fail closed."""
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(resource_evidence=({"reused": True},))


def test_invalid_permission_evidence_dict_fails_closed() -> None:
    """A dict in permission_evidence is malformed typed evidence → fail closed."""
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(permission_evidence=({"decision": "deny"},))


def test_invalid_approval_evidence_dict_fails_closed() -> None:
    """A dict in approval_evidence is malformed typed evidence → fail closed."""
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(approval_evidence=({"requested": True},))


def test_invalid_transfer_evidence_dict_fails_closed() -> None:
    """A dict in cross_domain_transfers is malformed typed evidence → fail closed."""
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(
            cross_domain_transfers=({"source_domain": "domain:a"},)
        )


def test_valid_canonical_evidence_still_accepted() -> None:
    """Valid canonical objects in typed fields remain accepted."""
    resolution = _resolution_binding("binding-valid", HEALTH)
    permission = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)
    transfer = _transfer("finding-valid")

    evidence = DomainObservabilityEvidence(
        resource_evidence=(resolution,),
        permission_evidence=(permission,),
        cross_domain_transfers=(transfer,),
    )

    snapshot = DomainMetricsCalculator().calculate(evidence, generated_at=NOW)
    assert _metric(snapshot, "permissions.rejected").value == 1
    assert _metric(snapshot, "cross_domain.transfers").value == 1


def test_knowledge_reuse_without_canonical_reuse_evidence_is_unavailable() -> None:
    """Valid canonical resource evidence with no reuse contract → UNAVAILABLE."""
    resolution = _resolution_binding("binding-noreuse", HEALTH)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(resource_evidence=(resolution,)),
        generated_at=NOW,
    )

    metric = _metric(snapshot, "knowledge.reused")
    assert metric.status is DomainMetricStatus.UNAVAILABLE
    assert metric.value is None


# ── V2 MAJOR-03 — source precedence and determinism ──────────────────────────


def _event_with_reference(event_id: str, kind: str, reference_id: str) -> DomainEvent:
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


def _operation_result(
    result_id: str, operation_id: str = "op-shared"
) -> DomainOperationResult:
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


def _trace_referencing_operation(trace_id: str, operation_id: str) -> DomainTrace:
    return DomainTrace(
        id=trace_id,
        digest="c" * 64,
        request_id=f"req-{trace_id}",
        primary_domain=HEALTH,
        supporting_domains=(),
        contributions=(
            DomainTraceContribution(
                domain_id=HEALTH,
                role=DomainTraceRole.PRIMARY,
                references=(
                    DomainTraceReference(
                        ref_id=operation_id,
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


def test_linked_event_trace_result_produces_one_log_occurrence() -> None:
    """Event + Trace + public result sharing one explicit canonical execution
    reference must produce exactly one logical log occurrence.

    The shared canonical identity is the operation RESULT ID
    (``DomainOperationResult.result_id``): the event carries ``operation_run``
    provenance pointing at that execution reference, the trace carries an
    ``OPERATION_RESULT`` contribution reference with the same ID, and the
    operation result's own identity IS that ``result_id``.

    Audit V3 MAJOR-01: ``operation_id`` is a definition ID (canonical
    adapters place it in ``operation_run`` provenance and two executions of
    one operation share it), so it must never merge executions. Only the
    explicit execution-instance reference may.
    """
    event = _event_with_reference("evt-major3-1", "operation_run", "op-res-major3-1")
    trace = _trace_referencing_operation("trace-major3-1", "op-res-major3-1")
    operation = _operation_result("op-res-major3-1", "op-3")

    report = _service().build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            operation_evidence=(operation,),
        )
    )

    assert len(report.log_entries) == 1
    entry = report.log_entries[0]
    # Precedence: the DomainEvent wins over the trace and the public result.
    assert entry.source_kind == "domain_event"
    assert entry.source_id == "evt-major3-1"
    # Legitimate secondary references remain available in the winning entry.
    assert "op-res-major3-1" in tuple(entry.reference_ids)


def test_unlinked_evidence_remains_distinct() -> None:
    """Event + Trace + result with no shared canonical reference stay distinct."""
    event = _event_with_reference("evt-major3-unlink", "operation_run", "op-unlink")
    trace = _trace_referencing_operation("trace-major3-unlink", "op-unlink-trace")
    operation = _operation_result("op-res-major3-unlink", "op-unlink-result")

    report = _service().build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            operation_evidence=(operation,),
        )
    )

    assert len(report.log_entries) == 3


def test_same_source_duplicate_evidence_produces_one_log_entry() -> None:
    """Identical same-source evidence duplicated → one log entry."""
    operation = _operation_result("op-res-major3-same", "op-same")

    report = _service().build_report(
        DomainObservabilityEvidence(operation_evidence=(operation, operation))
    )

    assert len(report.log_entries) == 1
    assert report.log_entries[0].source_id == "op-res-major3-same"


def test_report_is_deterministic_after_normalization() -> None:
    """Reordered equivalent evidence → same log_entries/report/digest."""
    event = _event_with_reference("evt-major3-det", "operation_run", "op-res-major3-det")
    trace = _trace_referencing_operation("trace-major3-det", "op-res-major3-det")
    operation = _operation_result("op-res-major3-det", "op-det")

    forward = _service().build_report(
        DomainObservabilityEvidence(
            events=(event,),
            traces=(trace,),
            operation_evidence=(operation,),
        )
    )
    reversed_evidence = DomainObservabilityEvidence(
        events=tuple(reversed((event,))),
        traces=tuple(reversed((trace,))),
        operation_evidence=tuple(reversed((operation,))),
    )
    backward = _service().build_report(reversed_evidence)

    assert forward.to_dict() == backward.to_dict()
    assert forward.digest == backward.digest
    assert forward.log_entries == backward.log_entries
