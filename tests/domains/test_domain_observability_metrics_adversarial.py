"""Phase 10.37 — Adversarial metric semantics tests.

Proves Phase 10.37 never infers fallback, transfers, knowledge reuse,
avoided questions or duplicate prevention by proxy. Missing numeric samples
become UNAVAILABLE, never zero.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionStatus,
)
from cmm.domains.contracts import DomainId
from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.operation_contracts import DomainOperationResult
from cmm.domains.resolver_contracts import (
    DomainResolutionResult,
    DomainResolutionStatus,
)

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def _metric_map(evidence: DomainObservabilityEvidence) -> dict:
    snapshot = DomainMetricsCalculator().calculate(evidence, generated_at=NOW)
    return {measurement.name: measurement for measurement in snapshot.measurements}


def _resolved(domain: str, *, fallback: bool = False) -> DomainResolutionResult:
    return DomainResolutionResult(
        id=f"res-{domain}-{fallback!s}",
        context_id=f"ctx-{domain}",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId.from_str(domain),
        confidence=0.9,
        fallback_used=fallback,
    )


def test_general_primary_does_not_imply_fallback() -> None:
    general = _resolved("domain:general")

    metric = _metric_map(DomainObservabilityEvidence(resolution_results=(general,)))[
        "resolution.fallback"
    ]

    assert metric.status.value == "unavailable"
    assert metric.value is None
    assert metric.unavailable_reason == "NO_FALLBACK_EVIDENCE"


def test_explicit_fallback_marker_is_observed() -> None:
    health = _resolved("domain:health", fallback=True)

    metric = _metric_map(DomainObservabilityEvidence(resolution_results=(health,)))[
        "resolution.fallback"
    ]

    assert metric.status.value == "observed"
    assert metric.value == 1


def test_supporting_domains_do_not_imply_transfer() -> None:
    composition = DomainComposition(
        id="comp-1",
        resolution_id="res-1",
        primary_domain=DomainId.from_str("domain:health"),
        supporting_domains=(DomainId.from_str("domain:general"),),
        status=DomainCompositionStatus.COMPOSED,
    )

    metric = _metric_map(DomainObservabilityEvidence(compositions=(composition,)))[
        "cross_domain.transfers"
    ]

    assert metric.status.value == "unavailable"
    assert metric.value is None
    assert metric.unavailable_reason == "NO_TRANSFER_EVIDENCE"


def test_explicit_transfer_is_observed() -> None:
    transfer = CrossDomainContextTransfer(
        source_domain=DomainId.from_str("domain:health"),
        target_domain=DomainId.from_str("domain:general"),
        kind="knowledge",
        identifier="kn-1",
        value="safe-public-value",
        reason="explicit transfer",
        provenance=("transfer:1",),
    )

    metric = _metric_map(
        DomainObservabilityEvidence(cross_domain_transfers=(transfer,))
    )["cross_domain.transfers"]

    assert metric.status.value == "observed"
    assert metric.value == 1


def test_repeated_knowledge_reference_does_not_imply_reuse() -> None:
    metric = _metric_map(DomainObservabilityEvidence())["knowledge.reused"]

    assert metric.status.value == "unavailable"
    assert metric.value is None
    assert metric.unavailable_reason == "NO_KNOWLEDGE_REUSE_EVIDENCE"


def test_absence_of_question_does_not_imply_avoided() -> None:
    metric = _metric_map(DomainObservabilityEvidence())[
        "questions.avoided_shared_context"
    ]

    assert metric.status.value == "unavailable"
    assert metric.value is None
    assert metric.unavailable_reason == "NO_AVOIDED_QUESTION_EVIDENCE"


def test_absence_of_duplicate_does_not_imply_prevention() -> None:
    metric = _metric_map(DomainObservabilityEvidence())["duplicates.prevented"]

    assert metric.status.value == "unavailable"
    assert metric.value is None
    assert metric.unavailable_reason == "NO_DUPLICATE_PREVENTION_EVIDENCE"


def test_missing_load_duration_is_unavailable_not_zero() -> None:
    from cmm.domains.enums import DomainLoadStatus
    from cmm.domains.loader_contracts import DomainLoadResult

    load = DomainLoadResult(
        candidate=_candidate(),
        status=DomainLoadStatus.VALID,
        pack=None,
        registry_record=None,
        errors=(),
        warnings=(),
        loaded_at=NOW,
        metadata={},
    )

    metric = _metric_map(DomainObservabilityEvidence(load_results=(load,)))[
        "loading.duration.mean_ms"
    ]

    assert metric.status.value == "unavailable"
    assert metric.value is None
    assert metric.unavailable_reason == "NO_LOAD_DURATION_EVIDENCE"


def test_missing_workflow_duration_is_unavailable_not_zero() -> None:
    from cmm.domains.workflow_contracts import DomainWorkflowResult
    from cmm.workflows.contracts import WorkflowResult, WorkflowRun
    from cmm.workflows.enums import WorkflowRunStatus

    # A RUNNING workflow has no completed_at → no explicit duration sample.
    run = WorkflowRun(
        run_id="wf-run-1",
        workflow_id="wf-1",
        workflow_version="1.0.0",
        status=WorkflowRunStatus.RUNNING,
        completed_nodes=(),
        failed_nodes=(),
        waiting_nodes=(),
        skipped_nodes=(),
        inputs={},
        outputs={},
        started_at=NOW,
        updated_at=NOW,
        completed_at=None,
    )
    workflow = WorkflowResult(run=run)
    evidence = DomainWorkflowResult(
        common_result=workflow,
        domain_id="domain:health",
    )

    metric = _metric_map(DomainObservabilityEvidence(workflow_evidence=(evidence,)))[
        "workflows.duration.mean_ms"
    ]

    assert metric.status.value == "unavailable"
    assert metric.value is None
    assert metric.unavailable_reason == "NO_WORKFLOW_DURATION_EVIDENCE"


def test_unavailable_metric_is_distinct_from_observed_zero() -> None:
    from cmm.domains.enums import DomainLoadStatus
    from cmm.domains.loader_contracts import DomainLoadResult

    load = DomainLoadResult(
        candidate=_candidate(),
        status=DomainLoadStatus.VALID,
        pack=None,
        registry_record=None,
        errors=(),
        warnings=(),
        loaded_at=NOW,
        metadata={"duration_ms": 50},
    )

    metrics = _metric_map(DomainObservabilityEvidence(load_results=(load,)))
    # Load evidence exists and zero failures occurred → observed zero.
    assert metrics["loading.failures"].status.value == "observed"
    assert metrics["loading.failures"].value == 0
    # No knowledge-reuse evidence category at all → unavailable.
    assert metrics["knowledge.reused"].status.value == "unavailable"


def test_operation_completed_without_approval_is_observed() -> None:
    operation = DomainOperationResult(
        result_id="op-res-1",
        request_id="req-1",
        operation_id="op-1",
        operation_version="1.0.0",
        domain_id="domain:health",
        status=DomainOperationStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
    )

    metrics = _metric_map(DomainObservabilityEvidence(operation_evidence=(operation,)))

    assert metrics["operations.by_domain"].status.value == "observed"
    assert {
        bucket.key: bucket.value for bucket in metrics["operations.by_domain"].buckets
    } == {
        "domain:health": 1,
    }


def _candidate():
    from cmm.domains.discovery_contracts import DomainCandidate
    from cmm.domains.enums import DomainSourceKind

    return DomainCandidate(
        candidate_id="general:1.0.0",
        source_id="source-test",
        source_kind=DomainSourceKind.DEVELOPMENT,
        location="/tmp/general",
        manifest_path="manifest.json",
        domain_id="domain:general",
        detected_version="1.0.0",
        checksum=f"sha256:{'ab' * 32}",
        trusted=True,
        discovered_at=NOW,
    )
