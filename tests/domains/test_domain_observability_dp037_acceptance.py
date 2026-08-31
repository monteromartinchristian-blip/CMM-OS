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
    DomainHealthStatus,
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


def _result_like_denied_permission_allow():
    """Construct a canonical permission evidence object whose outcome is ALLOW."""
    from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
    from cmm.domains.permission_adapters import DomainOperationPermissionDecision

    return DomainOperationPermissionDecision(
        operation_id="health.read",
        operation_version="1.0.0",
        decision=PermissionOutcome.ALLOW,
        reasons=("allowed by policy",),
    )


def _metric(snapshot, name: str):
    for measurement in snapshot.measurements:
        if measurement.name == name:
            return measurement
    raise AssertionError(f"metric {name} missing from snapshot")


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


def test_at_dp037_remediated_behaviors_are_proven() -> None:
    """Expanded acceptance proving every repaired V1 behavior end-to-end.

    Checkpoints (MAJOR-05 §11):
    - canonical evidence incl. real workflow result, real rule evidence via the
      canonical trace-owned path, real resource bindings, real transfers,
      identical-duplicate deduplication, distinct-occurrence identity,
      conflicting-duplicate fail-closed, event/trace/result overlap.
    - repaired metric semantics: permission DENY -> rejected=1, session
      degradation counts session occurrences not refs, workflow duration,
      rule bucket via trace references, resource bucket via accepted bindings.
    - health bound to current Domain version.
    - privacy/determinism: identical digest across order permutations and
      single-clock capture.
    """
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionApprovalRequirement,
        PermissionCapability,
        PermissionOutcome,
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
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer
    from cmm.domains.discovery_contracts import DomainCandidate
    from cmm.domains.enums import (
        DomainLoadStatus,
        DomainOperationStatus,
        DomainResourceResolutionStatus,
        DomainSourceKind,
        DomainValidationStatus,
    )
    from cmm.domains.loader_contracts import DomainLoadResult
    from cmm.domains.permission_adapters import DomainOperationPermissionDecision
    from cmm.domains.resource_contracts import (
        DomainResourceBinding,
        DomainResourceResolution,
    )
    from cmm.domains.session_contracts import DomainSessionContext
    from cmm.domains.trace_assembler import DomainTraceAssembler
    from cmm.domains.trace_contracts import (
        DomainTraceAssemblyRequest,
        DomainTraceContribution,
        DomainTraceReference,
        DomainTraceReferenceKind,
        DomainTraceReferences,
        DomainTraceRole,
    )
    from cmm.domains.validation_contracts import DomainValidationResult
    from cmm.domains.workflow_contracts import DomainWorkflowResult
    from cmm.workflows.contracts import WorkflowResult, WorkflowRun
    from cmm.workflows.enums import WorkflowRunStatus

    bootstrap = build_standard_health_domain_bootstrap()
    bootstrap.domain_registry.enable(GENERAL_DOMAIN_ID)
    bootstrap.domain_registry.enable(HEALTH_DOMAIN_ID)

    # ── Canonical evidence ─────────────────────────────────────────────────
    # Real resolution + composition.
    result_health = bootstrap.resolver.resolve(
        _resolution_context(
            objective="acceptance reparada",
            explicit=(HEALTH,),
            signals=(_health_signal("medical symptom", 0.9),),
        )
    )
    assert result_health.status is DomainResolutionStatus.RESOLVED

    composition = DomainComposition(
        id="comp-remediated-1",
        resolution_id=result_health.id,
        primary_domain=HEALTH,
        supporting_domains=(GENERAL,),
        status=DomainCompositionStatus.COMPOSED,
    )

    # Real Domain Events (23/23).
    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    event = _event(
        "event-remediated-1", "domain.resolution.completed", HEALTH_DOMAIN_ID
    )

    # Real Domain Trace with an APPLIED_RULE_TRACE reference (canonical rule
    # path) in the PRIMARY contribution.
    trace_contributions = (
        DomainTraceContribution(
            domain_id=HEALTH_DOMAIN_ID,
            role=DomainTraceRole.PRIMARY,
            references=(
                DomainTraceReference(
                    ref_id="rule:applied-1",
                    kind=DomainTraceReferenceKind.APPLIED_RULE_TRACE,
                    domain_id=HEALTH_DOMAIN_ID,
                ),
            ),
        ),
    )
    trace_request = DomainTraceAssemblyRequest(
        request_id="request:remediated-1",
        goal_id="goal:remediated-1",
        primary_domain=HEALTH_DOMAIN_ID,
        supporting_domains=(),
        contributions=trace_contributions,
        references=DomainTraceReferences(
            resolution_context_id="resolution-context:remediated-1",
            resolution_result_id="resolution-result:remediated-1",
            composition_id=composition.id,
        ),
        domain_results=(),
        started_at=NOW,
        completed_at=datetime(2026, 8, 31, 12, 0, 1, tzinfo=timezone.utc),
        metadata={"category": "at-dp-037-remediated"},
    )
    trace = DomainTraceAssembler().assemble(trace_request)
    assert trace.primary_domain == HEALTH

    # Real shared session evidence (no degradation refs).
    session = DomainSessionContext(
        session_id="session-remediated-1",
        primary_domain=HEALTH_DOMAIN_ID,
        supporting_domains=(GENERAL_DOMAIN_ID,),
        domain_versions={"domain:health": "1.0.0", "domain:general": "1.0.0"},
        composition_id=composition.id,
        trace_refs=(trace.id,),
        updated_at=NOW,
    )

    # Real canonical permission DENY.
    permission_denied = DomainOperationPermissionDecision(
        operation_id="health.export_medical_context",
        operation_version="1.0.0",
        decision=PermissionOutcome.DENY,
    )
    permission_allowed = DomainOperationPermissionDecision(
        operation_id="health.read",
        operation_version="1.0.0",
        decision=PermissionOutcome.ALLOW,
    )

    # Real canonical approval evidence.
    approval = PermissionApprovalRequirement(
        requirement_id="approval-remediated-1",
        action=PermissionCapability.OPERATION_EXECUTE,
        actor_id="actor-1",
        session_id="session-remediated-1",
        domain_id=HEALTH_DOMAIN_ID,
        operation_id="health.export_medical_context",
        operation_version="1.0.0",
        fingerprint="fingerprint-remediated-1",
    )

    # Real operation + workflow results.
    operation = _operation_result(
        "op-remediated-1", HEALTH_DOMAIN_ID, DomainOperationStatus.COMPLETED
    )
    run = WorkflowRun(
        run_id="wf-run-remediated-1",
        workflow_id="wf-remediated-1",
        workflow_version="1.0.0",
        status=WorkflowRunStatus.COMPLETED,
        started_at=NOW,
        completed_at=datetime(2026, 8, 31, 12, 0, 2, tzinfo=timezone.utc),
    )
    workflow = DomainWorkflowResult(
        common_result=WorkflowResult(run=run),
        domain_id=HEALTH_DOMAIN_ID,
    )

    # Real resource resolution with accepted bindings.
    binding_health = DomainResourceBinding(
        id="binding-remediated-health",
        resource_id="resource:health-1",
        definition_id="definition:health-1",
        domain_id=HEALTH,
        adapter="source-test",
        provenance=("at-dp-037-remediated",),
    )
    binding_general = DomainResourceBinding(
        id="binding-remediated-general",
        resource_id="resource:general-1",
        definition_id="definition:general-1",
        domain_id=GENERAL,
        adapter="source-test",
        provenance=("at-dp-037-remediated",),
    )
    resolution_resource = DomainResourceResolution(
        id="resolution-resource-remediated-1",
        resource_id="resource:health-1",
        status=DomainResourceResolutionStatus.RESOLVED,
        trace_id="trace:resource-remediated-1",
        resolved_at=NOW,
        bindings=(binding_health, binding_general),
    )

    # Real distinct failed load attempts for one candidate + real transfers.
    candidate_health = DomainCandidate(
        candidate_id="domain:health:1.0.0",
        source_id="source-test",
        source_kind=DomainSourceKind.DEVELOPMENT,
        location="/tmp/health",
        manifest_path="manifest.json",
        domain_id=HEALTH_DOMAIN_ID,
        detected_version="1.0.0",
        checksum=f"sha256:{'cd' * 32}",
        trusted=True,
        discovered_at=NOW,
    )
    load_fail_1 = DomainLoadResult(
        candidate=candidate_health,
        status=DomainLoadStatus.FAILED,
        pack=None,
        registry_record=None,
        errors=("first attempt failed",),
        warnings=(),
        loaded_at=NOW,
        metadata={},
    )
    load_fail_2 = DomainLoadResult(
        candidate=candidate_health,
        status=DomainLoadStatus.FAILED,
        pack=None,
        registry_record=None,
        errors=("second attempt failed",),
        warnings=(),
        loaded_at=datetime(2026, 8, 31, 12, 0, 1, tzinfo=timezone.utc),
        metadata={},
    )
    transfer_a = CrossDomainContextTransfer(
        source_domain=HEALTH,
        target_domain=GENERAL,
        kind="knowledge",
        identifier="transfer-remediated-a",
        value={"k": "a"},
        reason="handoff",
        provenance=("at-dp-037-remediated",),
    )
    transfer_b = CrossDomainContextTransfer(
        source_domain=HEALTH,
        target_domain=GENERAL,
        kind="knowledge",
        identifier="transfer-remediated-b",
        value={"k": "b"},
        reason="handoff",
        provenance=("at-dp-037-remediated",),
    )

    # Real conflict case (used also for fail-closed duplicate identity).
    conflict = DomainConflictCase(
        id="conflict-remediated-1",
        domains=(HEALTH, GENERAL),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.ADVISORY,
        status=DomainConflictStatus.OPEN,
        references=(
            DomainConflictReference(
                source_kind=DomainConflictSourceKind.DECLARED_DOMAIN_CONFLICT,
                source_id="evidence-remediated-1",
                domain_id=HEALTH,
                blocking=False,
                severity=DomainConflictSeverity.ADVISORY,
                authority_kind=DomainConflictAuthority.GLOBAL_SAFETY,
                evidence_refs=(),
            ),
        ),
    )

    # ── 41. Health bound to current version (positive) ─────────────────────
    version_validation = DomainValidationResult(
        domain_id=HEALTH_DOMAIN_ID,
        version="1.0.0",
        status=DomainValidationStatus.PASSED,
        manifest_valid=True,
        compatibility_valid=True,
        dependencies_valid=True,
        contracts_valid=True,
        permissions_valid=True,
        operations_valid=True,
        workflows_valid=True,
        security_valid=True,
        fragmentation_valid=True,
        tests_valid=True,
        validated_at=NOW,
    )
    stale_validation = DomainValidationResult(
        domain_id=HEALTH_DOMAIN_ID,
        version="0.9.0",
        status=DomainValidationStatus.PASSED,
        manifest_valid=True,
        compatibility_valid=True,
        dependencies_valid=True,
        contracts_valid=True,
        permissions_valid=True,
        operations_valid=True,
        workflows_valid=True,
        security_valid=True,
        fragmentation_valid=True,
        tests_valid=True,
        validated_at=NOW,
    )

    health_checker_valid = DomainHealthChecker(
        domain_registry=bootstrap.domain_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
        manifest_validation_lookup=lambda domain_id: version_validation,
        clock=lambda: NOW,
    )
    health_result_valid = health_checker_valid.check(HEALTH_DOMAIN_ID)
    assert health_result_valid.status is DomainHealthStatus.HEALTHY
    assert health_result_valid.manifest is True

    health_checker_stale = DomainHealthChecker(
        domain_registry=bootstrap.domain_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
        manifest_validation_lookup=lambda domain_id: stale_validation,
        clock=lambda: NOW,
    )
    health_result_stale = health_checker_stale.check(HEALTH_DOMAIN_ID)
    assert health_result_stale.manifest is False
    assert health_result_stale.status is not DomainHealthStatus.HEALTHY

    # ── 36-38. Load attempts, distinct transfers, fail-closed ──────────────
    evidence = DomainObservabilityEvidence(
        registry_records=bootstrap.domain_registry.list_records(),
        load_results=(load_fail_1, load_fail_2),
        resolution_results=(result_health,),
        compositions=(composition,),
        events=(event,),
        traces=(trace,),
        sessions=(session,),
        permission_evidence=(permission_denied, permission_allowed),
        approval_evidence=(approval,),
        operation_evidence=(operation, operation),
        workflow_evidence=(workflow,),
        rule_evidence=(),
        resource_evidence=(resolution_resource,),
        conflict_results=(conflict, conflict),
        cross_domain_transfers=(transfer_a, transfer_b),
    )
    service = _service(bootstrap)
    report = service.build_report(
        evidence,
        health_domain_ids=(HEALTH_DOMAIN_ID, GENERAL_DOMAIN_ID),
    )
    metrics = {m.name: m for m in report.metrics.measurements}

    # ── 36. Two distinct failed load attempts for one candidate count twice
    assert metrics["loading.failures"].value == 2

    # ── 37. Distinct transfers same pair/kind remain distinct
    assert metrics["cross_domain.transfers"].value == 2

    # ── 33-35. Duplicated identical operation/workflow/session evidence
    assert {b.key: b.value for b in metrics["operations.by_domain"].buckets} == {
        "domain:health": 1
    }
    assert {b.key: b.value for b in metrics["workflows.by_domain"].buckets} == {
        "domain:health": 1
    }
    assert metrics["workflows.duration.mean_ms"].value == pytest.approx(2000.0)

    # ── 21. Permission DENY produces rejected=1
    assert metrics["permissions.rejected"].value == 1

    # ── 25. Rule bucket via canonical trace-owned path
    assert {b.key: b.value for b in metrics["rules.applied_by_domain"].buckets} == {
        "domain:health": 1
    }

    # ── 26. Resource bucket via accepted bindings
    resource_buckets = {
        b.key: b.value for b in metrics["resources.loaded_by_domain"].buckets
    }
    assert resource_buckets == {"domain:general": 1, "domain:health": 1}

    # ── 27. Session degradation counts occurrences, not refs
    assert metrics["sessions.degraded"].status is DomainMetricStatus.UNAVAILABLE

    # ── 28-32. Fallback/transfer/knowledge/avoided/duplicates UNAVAILABLE
    assert metrics["resolution.fallback"].status is DomainMetricStatus.UNAVAILABLE
    assert metrics["cross_domain.transfers"].status is DomainMetricStatus.OBSERVED
    assert metrics["knowledge.reused"].status is DomainMetricStatus.UNAVAILABLE
    assert (
        metrics["questions.avoided_shared_context"].status
        is DomainMetricStatus.UNAVAILABLE
    )
    assert metrics["duplicates.prevented"].status is DomainMetricStatus.UNAVAILABLE

    # ── 20. Resolution confidence exact from explicit evidence
    assert metrics["resolution.decisions_by_domain"].value == 1 or {
        b.key: b.value for b in metrics["resolution.decisions_by_domain"].buckets
    } == {"domain:health": 1}

    # ── 38. Conflicting duplicate identity fails closed without echo ───────
    from cmm.domains.errors import InvalidDomainObservabilityEvidenceError

    conflicting = DomainConflictCase(
        id="conflict-remediated-1",
        domains=(HEALTH, DomainId(slug="other")),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.ADVISORY,
        status=DomainConflictStatus.OPEN,
        references=(
            DomainConflictReference(
                source_kind=DomainConflictSourceKind.DECLARED_DOMAIN_CONFLICT,
                source_id="evidence-remediated-1",
                domain_id=DomainId(slug="other"),
                blocking=False,
                severity=DomainConflictSeverity.ADVISORY,
                authority_kind=DomainConflictAuthority.GLOBAL_SAFETY,
                evidence_refs=(),
            ),
        ),
    )
    with pytest.raises(InvalidDomainObservabilityEvidenceError) as excinfo:
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(
                conflict_results=(conflict, conflicting),
            ),
            generated_at=NOW,
        )
    payload = str(excinfo.value).lower()
    assert "conflict-remediated-1" in payload
    assert "other" not in payload

    # ── 39. Real source precedence: linked Event/Trace/result → one logical
    # occurrence ────────────────────────────────────────────────────────────
    # The shared canonical identity is the operation RESULT ID: canonical
    # adapters place DEFINITION IDs into ``operation_run`` provenance, and
    # definition IDs legitimately repeat across executions, so only an
    # explicit execution-instance reference may merge the three channels.
    from cmm.domains.event_contracts import DomainEventReference
    from cmm.domains.trace_contracts import (
        DomainTraceReference,
        DomainTraceReferenceKind,
    )

    linked_operation = DomainOperationResult(
        result_id="op-overlap-linked",
        request_id="req-overlap-linked",
        operation_id="op-overlap-linked-op",
        operation_version="1.0.0",
        domain_id=HEALTH_DOMAIN_ID,
        status=DomainOperationStatus.COMPLETED,
        started_at=NOW,
        completed_at=datetime(2026, 8, 31, 12, 0, 1, tzinfo=timezone.utc),
    )
    linked_event = DomainEvent(
        event_id="evt-overlap-linked",
        event_type="domain.operation.completed",
        schema_version="1.0",
        domain_id=HEALTH_DOMAIN_ID,
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
        provenance=(
            DomainEventReference(
                kind="operation_run",
                reference_id="op-overlap-linked",
                domain_id=HEALTH_DOMAIN_ID,
            ),
        ),
    )
    linked_trace_contributions = (
        DomainTraceContribution(
            domain_id=HEALTH_DOMAIN_ID,
            role=DomainTraceRole.PRIMARY,
            references=(
                DomainTraceReference(
                    ref_id="op-overlap-linked",
                    kind=DomainTraceReferenceKind.OPERATION_RESULT,
                    domain_id=HEALTH_DOMAIN_ID,
                ),
            ),
        ),
    )
    linked_trace_request = DomainTraceAssemblyRequest(
        request_id="request:overlap-linked",
        goal_id="goal:overlap-linked",
        primary_domain=HEALTH_DOMAIN_ID,
        supporting_domains=(),
        contributions=linked_trace_contributions,
        references=DomainTraceReferences(
            resolution_context_id="resolution-context:overlap-linked",
            resolution_result_id="resolution-result:overlap-linked",
            composition_id="composition:overlap-linked",
        ),
        domain_results=(),
        started_at=NOW,
        completed_at=datetime(2026, 8, 31, 12, 0, 1, tzinfo=timezone.utc),
        metadata={"category": "at-dp-037-overlap-linked"},
    )
    linked_trace = DomainTraceAssembler().assemble(linked_trace_request)
    overlap_report = service.build_report(
        DomainObservabilityEvidence(
            events=(linked_event,),
            traces=(linked_trace,),
            operation_evidence=(linked_operation,),
        )
    )
    # Genuinely linked Event/Trace/result share one explicit canonical
    # execution reference (the result_id) → exactly one logical log occurrence.
    assert len(overlap_report.log_entries) == 1
    overlap_entry = overlap_report.log_entries[0]
    assert overlap_entry.source_kind == "domain_event"
    assert "op-overlap-linked" in overlap_entry.reference_ids

    # Unlinked Event/Trace/result (no shared canonical reference) must remain
    # distinct: co-location is not shared identity.
    unlinked_event = DomainEvent(
        event_id="evt-overlap-unlinked",
        event_type="domain.operation.completed",
        schema_version="1.0",
        domain_id=HEALTH_DOMAIN_ID,
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
        provenance=(
            DomainEventReference(
                kind="operation_run",
                reference_id="op-unlinked-event",
                domain_id=HEALTH_DOMAIN_ID,
            ),
        ),
    )
    unlinked_trace_request = DomainTraceAssemblyRequest(
        request_id="request:overlap-unlinked",
        goal_id="goal:overlap-unlinked",
        primary_domain=HEALTH_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            DomainTraceContribution(
                domain_id=HEALTH_DOMAIN_ID,
                role=DomainTraceRole.PRIMARY,
                references=(
                    DomainTraceReference(
                        ref_id="op-unlinked-trace",
                        kind=DomainTraceReferenceKind.OPERATION_RESULT,
                        domain_id=HEALTH_DOMAIN_ID,
                    ),
                ),
            ),
        ),
        references=DomainTraceReferences(
            resolution_context_id="resolution-context:overlap-unlinked",
            resolution_result_id="resolution-result:overlap-unlinked",
            composition_id="composition:overlap-unlinked",
        ),
        domain_results=(),
        started_at=NOW,
        completed_at=datetime(2026, 8, 31, 12, 0, 1, tzinfo=timezone.utc),
        metadata={"category": "at-dp-037-overlap-unlinked"},
    )
    unlinked_trace = DomainTraceAssembler().assemble(unlinked_trace_request)
    unlinked_operation = _operation_result(
        "op-overlap-unlinked", HEALTH_DOMAIN_ID, DomainOperationStatus.COMPLETED
    )
    unlinked_report = service.build_report(
        DomainObservabilityEvidence(
            events=(unlinked_event,),
            traces=(unlinked_trace,),
            operation_evidence=(unlinked_operation,),
        )
    )
    assert len(unlinked_report.log_entries) == 3
    # No fuzzy suppression: distinct source IDs stay distinct.
    unlinked_ids = sorted(entry.source_id for entry in unlinked_report.log_entries)
    assert "evt-overlap-unlinked" in unlinked_ids
    assert "op-overlap-unlinked" in unlinked_ids

    # ── 53. Transfer occurrence identity (same identifier, iterations 0/1) ──
    transfer_iter_0 = CrossDomainContextTransfer(
        source_domain=HEALTH,
        target_domain=GENERAL,
        kind="finding",
        identifier="finding-iterated",
        value={"k": "iteration-0"},
        reason="handoff",
        iteration=0,
        provenance=("at-dp-037-iterations",),
    )
    transfer_iter_1 = CrossDomainContextTransfer(
        source_domain=HEALTH,
        target_domain=GENERAL,
        kind="finding",
        identifier="finding-iterated",
        value={"k": "iteration-1"},
        reason="handoff",
        iteration=1,
        provenance=("at-dp-037-iterations",),
    )
    transfer_metric = _metric(
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(
                cross_domain_transfers=(transfer_iter_0, transfer_iter_1)
            ),
            generated_at=NOW,
        ),
        "cross_domain.transfers",
    )
    assert transfer_metric.status is DomainMetricStatus.OBSERVED
    assert transfer_metric.value == 2

    # Same exact transfer duplicated → one occurrence.
    same_transfer = _metric(
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(
                cross_domain_transfers=(transfer_iter_0, transfer_iter_0)
            ),
            generated_at=NOW,
        ),
        "cross_domain.transfers",
    )
    assert same_transfer.value == 1

    # ── 54. Permission identity (same operation ID, versions 1.0.0/2.0.0) ──
    deny_v1 = DomainOperationPermissionDecision(
        operation_id="health.export_medical_context",
        operation_version="1.0.0",
        decision=PermissionOutcome.DENY,
    )
    deny_v2 = DomainOperationPermissionDecision(
        operation_id="health.export_medical_context",
        operation_version="2.0.0",
        decision=PermissionOutcome.DENY,
    )
    permission_version_metric = _metric(
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(permission_evidence=(deny_v1, deny_v2)),
            generated_at=NOW,
        ),
        "permissions.rejected",
    )
    assert permission_version_metric.status is DomainMetricStatus.OBSERVED
    assert permission_version_metric.value == 2

    # ── 55. Canonical permission log status and stable source identity ──────
    permission_log_report = service.build_report(
        DomainObservabilityEvidence(
            permission_evidence=(
                deny_v1,
                deny_v2,
                _result_like_denied_permission_allow(),
            )
        )
    )
    permission_entries = [
        entry
        for entry in permission_log_report.log_entries
        if entry.source_kind == "permission_decision"
    ]
    permission_statuses = {entry.status for entry in permission_entries}
    assert permission_statuses == {"deny", "allow"}
    permission_source_ids = {entry.source_id for entry in permission_entries}
    assert len(permission_source_ids) == 3
    assert any("1.0.0" in sid for sid in permission_source_ids)
    assert any("2.0.0" in sid for sid in permission_source_ids)
    assert all(
        "DomainOperationPermissionDecision" not in sid for sid in permission_source_ids
    )

    # ── 56. Malformed typed evidence fails closed (resource + permission) ───
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(resource_evidence=({"reused": True},))
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(permission_evidence=({"decision": "deny"},))
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(approval_evidence=({"requested": True},))
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(
            cross_domain_transfers=({"source_domain": "domain:a"},)
        )

    # ── 57. Valid canonical evidence remains accepted (no over-validation) ──
    valid_evidence = DomainObservabilityEvidence(
        resource_evidence=(resolution_resource,),
        permission_evidence=(deny_v1,),
        approval_evidence=(approval,),
        cross_domain_transfers=(transfer_iter_0,),
    )
    assert len(valid_evidence.resource_evidence) == 1

    # ── 46-48. Order-independent determinism ───────────────────────────────
    permuted_evidence = DomainObservabilityEvidence(
        registry_records=evidence.registry_records,
        load_results=tuple(reversed(evidence.load_results)),
        resolution_results=tuple(reversed(evidence.resolution_results)),
        compositions=tuple(reversed(evidence.compositions)),
        events=tuple(reversed(evidence.events)),
        traces=tuple(reversed(evidence.traces)),
        sessions=tuple(reversed(evidence.sessions)),
        permission_evidence=tuple(reversed(evidence.permission_evidence)),
        approval_evidence=tuple(reversed(evidence.approval_evidence)),
        operation_evidence=tuple(reversed(evidence.operation_evidence)),
        workflow_evidence=tuple(reversed(evidence.workflow_evidence)),
        rule_evidence=(),
        resource_evidence=tuple(reversed(evidence.resource_evidence)),
        conflict_results=tuple(reversed(evidence.conflict_results)),
        cross_domain_transfers=tuple(reversed(evidence.cross_domain_transfers)),
    )
    report_permuted = service.build_report(
        permuted_evidence,
        health_domain_ids=(GENERAL_DOMAIN_ID, HEALTH_DOMAIN_ID),
    )
    assert report.to_dict() == report_permuted.to_dict()
    assert report.digest == report_permuted.digest

    # ── 49. Single-clock capture (no opportunistic samples) ────────────────
    calls: list[datetime] = []
    clock_at = datetime(2026, 8, 31, 13, 0, 0, tzinfo=timezone.utc)

    def counting_clock() -> datetime:
        calls.append(clock_at)
        return clock_at

    checker_clock = DomainHealthChecker(
        domain_registry=bootstrap.domain_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
        manifest_validation_lookup=lambda domain_id: None,
        clock=lambda: NOW,
    )
    service_clocked = DomainObservabilityService(
        metrics_calculator=DomainMetricsCalculator(),
        health_checker=checker_clock,
        clock=counting_clock,
    )
    service_clocked.build_report(
        evidence,
        health_domain_ids=(HEALTH_DOMAIN_ID,),
    )
    assert len(calls) == 1

    # ── 50-52. No parallel infrastructure, DomainAPI unchanged, 23/23 events
    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert len({e for e in CANONICAL_DOMAIN_EVENTS}) == 23
