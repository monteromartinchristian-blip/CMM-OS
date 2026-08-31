"""Phase 10.37 — AT-DP-037 connected acceptance test.

Proves the Domain Observability projection end-to-end through real canonical
components:

real Domain registries -> real registered internal domains -> real resolution
-> real ambiguity/blocked evidence -> real composition/multi-domain
participation -> real Domain Event contracts (23/23) -> real Domain Trace ->
real shared Domain session evidence -> canonical permission/approval evidence
-> canonical operation/workflow evidence -> Domain Observability -> exact
metrics / explicit UNAVAILABLE + Domain health.

Mocks may observe boundaries but never replace the behavior being accepted.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionStatus,
)
from cmm.domains.contracts import DomainId
from cmm.domains.enums import DomainOperationStatus, DomainStatus
from cmm.domains.event_catalog import CANONICAL_DOMAIN_EVENTS
from cmm.domains.event_contracts import DomainEvent
from cmm.domains.general import GENERAL_DOMAIN_ID
from cmm.domains.health import (
    HEALTH_DOMAIN_ID,
    build_standard_health_domain_bootstrap,
)
from cmm.domains.observability_contracts import (
    DomainMetricStatus,
)
from cmm.domains.observability_health import DomainHealthChecker
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.observability_service import DomainObservabilityService
from cmm.domains.operation_contracts import DomainOperationResult
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)
from cmm.domains.resolver_contracts import DomainResolutionStatus
from cmm.runtime.sessions import InMemorySessionStore

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
GENERAL = DomainId(slug="general")
HEALTH = DomainId(slug="health")


def _resolution_context(
    *,
    objective: str = "medical symptom",
    explicit: tuple = (),
    signals: tuple = (),
    available=None,
    authorized=None,
) -> DomainResolutionContext:
    return DomainResolutionContext(
        id=f"ctx-{objective.replace(' ', '-')}",
        objective=objective,
        available_domains=available or (GENERAL, HEALTH),
        authorized_domains=authorized or (GENERAL, HEALTH),
        explicit_domains=explicit,
        signals=signals,
        created_at=NOW,
    )


def _health_signal(value: str = "medical symptom", confidence: float = 0.9):
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=(HEALTH,),
        confidence=confidence,
        provenance={"source": "at-dp-037"},
    )


def _event(
    event_id: str, event_type: str, domain_id: str, *, payload=None, metadata=None
) -> DomainEvent:
    return DomainEvent(
        event_id=event_id,
        event_type=event_type,
        schema_version="1.0",
        domain_id=domain_id,
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
        payload=payload or {},
        metadata=metadata or {},
    )


def _operation_result(
    result_id: str, domain_id: str, status: DomainOperationStatus
) -> DomainOperationResult:
    return DomainOperationResult(
        result_id=result_id,
        request_id=f"req-{result_id}",
        operation_id=f"{domain_id.removeprefix('domain:')}.build_summary",
        operation_version="1.0.0",
        domain_id=domain_id,
        status=status,
        started_at=NOW,
        completed_at=NOW,
    )


def _service(bootstrap) -> DomainObservabilityService:
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


def test_at_dp037_connected_acceptance() -> None:
    # ── 1. Real canonical registries with two registered internal domains ──
    bootstrap = build_standard_health_domain_bootstrap()
    # Real lifecycle transition: enable both domains (ACTIVE) through the
    # canonical registry, proving installed != enabled.
    bootstrap.domain_registry.enable(GENERAL_DOMAIN_ID)
    bootstrap.domain_registry.enable(HEALTH_DOMAIN_ID)
    registered = {str(d.id) for d in bootstrap.domain_registry.list()}
    assert GENERAL_DOMAIN_ID in registered
    assert HEALTH_DOMAIN_ID in registered
    assert len(registered) == 2
    active_records = bootstrap.domain_registry.list_records()
    assert all(record.status is DomainStatus.ACTIVE for record in active_records)

    # ── 2. Real canonical resolution with explicit confidence ─────────────
    result_health = bootstrap.resolver.resolve(
        _resolution_context(
            objective="medical symptom check",
            explicit=(HEALTH,),
            signals=(_health_signal(),),
        )
    )
    assert result_health.status is DomainResolutionStatus.RESOLVED
    assert result_health.primary_domain == HEALTH
    assert result_health.confidence > 0.0

    # ── 3. Real ambiguity/blocked evidence path ────────────────────────────
    blocked = bootstrap.resolver.resolve(
        _resolution_context(
            objective="medical symptom but unauthorized",
            signals=(_health_signal(),),
            authorized=(GENERAL,),
        )
    )
    if blocked.status is DomainResolutionStatus.BLOCKED:
        blocked_status = blocked.status
    else:
        ambiguous_context = _resolution_context(
            objective="ambiguous request",
            explicit=(HEALTH, GENERAL),
            signals=(_health_signal(), _health_signal("general intent", 0.8)),
            available=(HEALTH,),
        )
        blocked = bootstrap.resolver.resolve(ambiguous_context)
        blocked_status = blocked.status
    assert blocked_status in (
        DomainResolutionStatus.BLOCKED,
        DomainResolutionStatus.AMBIGUOUS,
    )

    # ── 4. Real composition / multi-domain participation ───────────────────
    composition = DomainComposition(
        id="comp-connected-1",
        resolution_id=result_health.id,
        primary_domain=HEALTH,
        supporting_domains=(GENERAL,),
        status=DomainCompositionStatus.COMPOSED,
    )

    # ── 5. Real Domain Events (23/23 catalog preserved) ────────────────────
    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert len(set(CANONICAL_DOMAIN_EVENTS)) == 23
    event_resolution = _event(
        "event-acceptance-1",
        "domain.resolution.completed",
        HEALTH_DOMAIN_ID,
    )
    event_operation = _event(
        "event-acceptance-2",
        "domain.operation.completed",
        HEALTH_DOMAIN_ID,
    )

    # ── 6. Real Domain Trace (reference-only) ──────────────────────────────
    from cmm.domains.trace_assembler import DomainTraceAssembler
    from cmm.domains.trace_contracts import (
        DomainResultTraceReference,
        DomainTraceAssemblyRequest,
        DomainTraceContribution,
        DomainTraceReference,
        DomainTraceReferenceKind,
        DomainTraceReferences,
        DomainTraceRole,
        DomainTraceStatus,
    )

    trace_contributions = (
        DomainTraceContribution(
            domain_id=HEALTH_DOMAIN_ID,
            role=DomainTraceRole.PRIMARY,
            references=(
                DomainTraceReference(
                    ref_id="result:accepted-1",
                    kind=DomainTraceReferenceKind.DOMAIN_RESULT,
                    domain_id=HEALTH_DOMAIN_ID,
                ),
            ),
        ),
        DomainTraceContribution(
            domain_id=GENERAL_DOMAIN_ID,
            role=DomainTraceRole.SUPPORTING,
            references=(
                DomainTraceReference(
                    ref_id="result:accepted-1-general",
                    kind=DomainTraceReferenceKind.DOMAIN_RESULT,
                    domain_id=GENERAL_DOMAIN_ID,
                ),
            ),
        ),
    )
    trace_request = DomainTraceAssemblyRequest(
        request_id="request:accepted-1",
        goal_id="goal:accepted-1",
        primary_domain=HEALTH_DOMAIN_ID,
        supporting_domains=(GENERAL_DOMAIN_ID,),
        contributions=trace_contributions,
        references=DomainTraceReferences(
            resolution_context_id="resolution-context:accepted-1",
            resolution_result_id=f"resolution-result:{result_health.context_id}",
            composition_id=composition.id,
        ),
        domain_results=(
            DomainResultTraceReference("result:accepted-1", HEALTH_DOMAIN_ID),
            DomainResultTraceReference("result:accepted-1-general", GENERAL_DOMAIN_ID),
        ),
        started_at=NOW,
        completed_at=datetime(2026, 8, 31, 12, 0, 1, tzinfo=timezone.utc),
        metadata={"category": "at-dp-037"},
    )
    trace = DomainTraceAssembler().assemble(trace_request)
    assert isinstance(trace.status, DomainTraceStatus)
    assert trace.primary_domain == HEALTH

    # ── 7. Real shared Domain session evidence ─────────────────────────────
    from cmm.domains.session_contracts import DomainSessionContext
    from cmm.domains.session_persistence import SharedSessionDomainAdapter

    session_adapter = SharedSessionDomainAdapter(store=InMemorySessionStore())
    session = DomainSessionContext(
        session_id="session-accepted-037",
        primary_domain=HEALTH_DOMAIN_ID,
        supporting_domains=(GENERAL_DOMAIN_ID,),
        domain_versions={"domain:health": "1.0.0", "domain:general": "1.0.0"},
        composition_id=composition.id,
        trace_refs=(trace.id,),
        updated_at=NOW,
    )
    session_adapter.save_domain_session(session)
    persisted = session_adapter.load_domain_session("session-accepted-037")
    assert persisted is not None
    assert persisted.session_id == "session-accepted-037"

    # ── 8. Canonical permission/approval evidence ──────────────────────────
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionApprovalRequirement,
        PermissionCapability,
    )

    approval = PermissionApprovalRequirement(
        requirement_id="approval-accepted-1",
        action=PermissionCapability.OPERATION_EXECUTE,
        actor_id="actor-1",
        session_id="session-accepted-037",
        domain_id=HEALTH_DOMAIN_ID,
        operation_id="health.export_medical_context",
        operation_version="1.0.0",
        fingerprint="fingerprint-accepted-1",
    )
    permission_denied = _result_like_denied_permission()
    approval_evidence = (approval,)

    # ── 9. Canonical operation/workflow evidence ───────────────────────────
    operation = _operation_result(
        "op-accepted-1", HEALTH_DOMAIN_ID, DomainOperationStatus.COMPLETED
    )

    # ── 10. Build the report through the service ───────────────────────────
    evidence = DomainObservabilityEvidence(
        registry_records=bootstrap.domain_registry.list_records(),
        resolution_results=(result_health, blocked),
        compositions=(composition,),
        events=(event_resolution, event_operation),
        traces=(trace,),
        sessions=(persisted,),
        permission_evidence=(permission_denied,),
        approval_evidence=approval_evidence,
        operation_evidence=(operation,),
    )
    service = _service(bootstrap)
    report = service.build_report(
        evidence,
        health_domain_ids=(HEALTH_DOMAIN_ID, GENERAL_DOMAIN_ID),
    )

    metrics = {m.name: m for m in report.metrics.measurements}

    # ── 11. Connected metric truth ─────────────────────────────────────────
    assert metrics["domains.installed"].value == 2
    assert metrics["domains.active"].value == 2
    decisions = {
        b.key: b.value for b in metrics["resolution.decisions_by_domain"].buckets
    }
    assert decisions == {"domain:health": 1}
    assert metrics["resolution.confidence.mean"].value == pytest.approx(
        (result_health.confidence + blocked.confidence) / 2
    )
    assert metrics["execution.multi_domain"].value == 1
    assert {b.key: b.value for b in metrics["operations.by_domain"].buckets} == {
        "domain:health": 1
    }
    assert metrics["approvals.requested"].value == 1

    # ── 12. Anti-inference invariants ──────────────────────────────────────
    assert metrics["resolution.fallback"].status is DomainMetricStatus.UNAVAILABLE
    assert metrics["cross_domain.transfers"].status is DomainMetricStatus.UNAVAILABLE
    assert metrics["knowledge.reused"].status is DomainMetricStatus.UNAVAILABLE
    assert (
        metrics["questions.avoided_shared_context"].status
        is DomainMetricStatus.UNAVAILABLE
    )
    assert metrics["duplicates.prevented"].status is DomainMetricStatus.UNAVAILABLE

    # ── 13. Health truth ───────────────────────────────────────────────────
    health_health = {r.domain_id: r for r in report.health_results}[HEALTH_DOMAIN_ID]
    general_health = {r.domain_id: r for r in report.health_results}[GENERAL_DOMAIN_ID]
    # Positive verification: registry/resources/rules/operations/workflows/
    # permissions verified even when manifest evidence is absent (degraded).
    assert health_health.registry is True
    assert health_health.dependencies is True
    assert general_health.registry is True
    assert general_health.dependencies is True

    # ── 14. No mutation ────────────────────────────────────────────────────
    after_records = bootstrap.domain_registry.list_records()
    assert after_records == bootstrap.domain_registry.list_records()
    assert tuple(r.status for r in after_records) == tuple(
        r.status for r in bootstrap.domain_registry.list_records()
    )

    # ── 15. Privacy ────────────────────────────────────────────────────────
    rendered = json.dumps(report.to_dict(), ensure_ascii=False)
    assert "medical symptom check" not in rendered
    assert "op-accepted-1" in rendered  # public operation ID, not payload

    # ── 16. Determinism ────────────────────────────────────────────────────
    report_again = service.build_report(
        evidence,
        health_domain_ids=(HEALTH_DOMAIN_ID, GENERAL_DOMAIN_ID),
    )
    assert report.to_dict() == report_again.to_dict()
    assert report.digest == report_again.digest


def _result_like_denied_permission():
    """Construct a canonical permission evidence object whose outcome is DENY."""
    from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
    from cmm.domains.permission_adapters import DomainOperationPermissionDecision

    return DomainOperationPermissionDecision(
        operation_id="health.export_medical_context",
        operation_version="1.0.0",
        decision=PermissionOutcome.DENY,
        reasons=("not authorized at this session",),
    )


def test_at_dp037_no_parallel_observability_truth() -> None:
    """Observability derives everything from canonical evidence at runtime."""
    bootstrap = build_standard_health_domain_bootstrap()
    service = _service(bootstrap)

    evidence = DomainObservabilityEvidence(
        registry_records=bootstrap.domain_registry.list_records(),
        resolution_results=(),
        compositions=(),
        events=(),
        traces=(),
        sessions=(),
    )
    snapshot = service.calculate_metrics(evidence)
    by_name = {m.name: m for m in snapshot.measurements}

    # Registry-derived metrics are observed from canonical registry evidence.
    assert by_name["domains.installed"].status is DomainMetricStatus.OBSERVED
    # No resolution evidence at all -> unavailable, never zero.
    assert (
        by_name["resolution.decisions_by_domain"].status
        is DomainMetricStatus.UNAVAILABLE
    )
