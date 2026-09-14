"""Phase 10.37 — MAJOR-01 RED regressions: evidence deduplication and
occurrence identity.

Audit findings under test:

1. ``_deduplicate_generic`` builds a deduplicated ``seen`` mapping but returns
   ``tuple(items)`` — the input order, including duplicates.

2. ``loading.failures`` collapses multiple distinct failed load attempts for
   the same candidate into one candidate ID.

3. ``cross_domain.transfers`` uses an occurrence identity too coarse
   (``source:target:kind``) to distinguish distinct transfer occurrences, and
   transfers are not passed through occurrence normalization at all.

Tests here must fail BEFORE the MAJOR-01 production fix and pass after it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReference,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
)
from cmm.domains.contracts import DomainDefinition, DomainId
from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer
from cmm.domains.discovery_contracts import DomainCandidate
from cmm.domains.enums import (
    DomainLoadStatus,
    DomainOperationStatus,
    DomainRuleExecutionStatus,
    DomainSourceKind,
    DomainStatus,
)
from cmm.domains.errors import InvalidDomainObservabilityEvidenceError
from cmm.domains.loader_contracts import DomainLoadResult
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.operation_contracts import DomainOperationResult
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.rule_contracts import DomainRuleExecutionResult
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionResumeResult,
    DomainSessionResumeStatus,
)
from cmm.domains.workflow_contracts import DomainWorkflowResult
from cmm.workflows.contracts import WorkflowResult, WorkflowRun

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def _definition(domain_id: str) -> DomainDefinition:
    slug = domain_id.removeprefix("domain:")
    return DomainDefinition(
        id=DomainId.from_str(domain_id),
        name=slug,
        display_name=slug.title(),
        version="1.0.0",
        kind="system",
        description=f"Description of {domain_id}",
        manifest_id=f"manifest:{slug}:1.0.0",
        enabled=True,
    )


def _registry_record(domain_id: str, status: DomainStatus) -> DomainRegistryRecord:
    return DomainRegistryRecord(
        definition=_definition(domain_id),
        status=status,
        registered_at=NOW,
        updated_at=NOW,
    )


def _candidate(candidate_id: str) -> DomainCandidate:
    slug = candidate_id.split(":")[-1]
    return DomainCandidate(
        candidate_id=candidate_id,
        source_id="source-test",
        source_kind=DomainSourceKind.DEVELOPMENT,
        location=f"/tmp/{slug}",
        manifest_path="manifest.json",
        domain_id=f"domain:{slug}",
        detected_version="1.0.0",
        checksum=f"sha256:{'ab' * 32}",
        trusted=True,
        discovered_at=NOW,
    )


def _load(
    candidate_id: str, status: DomainLoadStatus, at: datetime
) -> DomainLoadResult:
    return DomainLoadResult(
        candidate=_candidate(candidate_id),
        status=status,
        pack=None,
        registry_record=None,
        errors=("load failure",) if status == DomainLoadStatus.FAILED else (),
        warnings=(),
        loaded_at=at,
        metadata={},
    )


def _operation_result(result_id: str, domain_id: str) -> DomainOperationResult:
    return DomainOperationResult(
        result_id=result_id,
        request_id=f"req:{result_id}",
        operation_id=f"op:{result_id}",
        operation_version="1.0.0",
        domain_id=domain_id,
        status=DomainOperationStatus.COMPLETED,
        started_at=NOW - timedelta(seconds=1),
        completed_at=NOW,
    )


def _workflow_result(run_id: str, domain_id: str) -> DomainWorkflowResult:
    run = WorkflowRun(
        run_id=run_id,
        workflow_id=f"wf:{run_id}",
        workflow_version="1.0.0",
        status="completed",
        started_at=NOW - timedelta(seconds=1),
        completed_at=NOW,
    )
    return DomainWorkflowResult(
        common_result=WorkflowResult(run=run),
        domain_id=domain_id,
    )


def _rule_result(rule_id: str) -> DomainRuleExecutionResult:
    return DomainRuleExecutionResult(
        id=rule_id,
        plan_id=f"plan:{rule_id}",
        status=DomainRuleExecutionStatus.COMPLETED,
        started_at=NOW - timedelta(seconds=1),
        completed_at=NOW,
    )


def _session(session_id: str) -> DomainSessionContext:
    return DomainSessionContext(
        session_id=session_id,
        primary_domain="domain:health",
        updated_at=NOW,
    )


def _resume(session_id: str, revision: int) -> DomainSessionResumeResult:
    return DomainSessionResumeResult(
        status=DomainSessionResumeStatus.RESUMED,
        session_id=session_id,
        previous_revision=revision,
        resumed_revision=revision,
    )


def _conflict(conflict_id: str) -> DomainConflictCase:
    return DomainConflictCase(
        id=conflict_id,
        domains=(DomainId.from_str("domain:a"), DomainId.from_str("domain:b")),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.ADVISORY,
        status=DomainConflictStatus.OPEN,
        references=(
            DomainConflictReference(
                source_kind=DomainConflictSourceKind.DECLARED_DOMAIN_CONFLICT,
                source_id=f"evidence-{conflict_id}",
                domain_id=DomainId.from_str("domain:a"),
                blocking=False,
                severity=DomainConflictSeverity.ADVISORY,
                authority_kind=DomainConflictAuthority.GLOBAL_SAFETY,
                evidence_refs=(),
            ),
        ),
    )


def _conflict_with_different_content(conflict_id: str) -> DomainConflictCase:
    """Same ID as ``_conflict`` but with materially different public content."""
    return DomainConflictCase(
        id=conflict_id,
        domains=(DomainId.from_str("domain:a"), DomainId.from_str("domain:z")),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.ADVISORY,
        status=DomainConflictStatus.OPEN,
        references=(
            DomainConflictReference(
                source_kind=DomainConflictSourceKind.DECLARED_DOMAIN_CONFLICT,
                source_id=f"evidence-{conflict_id}",
                domain_id=DomainId.from_str("domain:z"),
                blocking=False,
                severity=DomainConflictSeverity.ADVISORY,
                authority_kind=DomainConflictAuthority.GLOBAL_SAFETY,
                evidence_refs=(),
            ),
        ),
    )


def _transfer(
    source: str, target: str, kind: str, identifier: str
) -> CrossDomainContextTransfer:
    return CrossDomainContextTransfer(
        source_domain=DomainId.from_str(source),
        target_domain=DomainId.from_str(target),
        kind=kind,
        identifier=identifier,
        value={"k": f"value:{identifier}"},
        reason="context handoff",
        provenance=("test",),
    )


def _metric(snapshot, name: str):
    for measurement in snapshot.measurements:
        if measurement.name == name:
            return measurement
    raise AssertionError(f"metric {name} missing from snapshot")


# ── A. Identical canonical duplicates count once ─────────────────────────────


def test_loading_failures_counts_distinct_failed_attempts_per_candidate() -> None:
    """Two distinct failed load attempts for one candidate are 2, not 1."""
    first = _load("domain:health", DomainLoadStatus.FAILED, NOW - timedelta(seconds=5))
    second = _load("domain:health", DomainLoadStatus.FAILED, NOW)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(load_results=(first, second)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "loading.failures").value == 2


def test_identical_load_failure_duplicates_count_once() -> None:
    """Two byte-identical failed load attempts are one occurrence."""
    only = _load("domain:health", DomainLoadStatus.FAILED, NOW)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(load_results=(only, only)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "loading.failures").value == 1


def test_conflicts_dedup_identical_and_keep_one_occurrence() -> None:
    """Identical DomainConflictCase duplicates count once via conflicts.detected."""
    case = _conflict("conflict-1")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(conflict_results=(case, case)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "conflicts.detected").value == 1


def test_conflicts_conflicting_duplicate_identity_fails_closed() -> None:
    """Same conflict ID with different public content raises without echo."""
    original = _conflict("conflict-1")
    conflicting = _conflict_with_different_content("conflict-1")

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as excinfo:
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(conflict_results=(original, conflicting)),
            generated_at=NOW,
        )

    payload = str(excinfo.value).lower()
    assert "conflict-1" in payload  # reference identity may appear
    assert "domain:z" not in payload  # conflicting content must not echo


def test_operations_dedup_identical_and_count_once() -> None:
    """Identical DomainOperationResult duplicates count once."""
    operation = _operation_result("op-1", "domain:health")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(operation_evidence=(operation, operation)),
        generated_at=NOW,
    )

    buckets = _metric(snapshot, "operations.by_domain").buckets
    assert len(buckets) == 1
    assert buckets[0].key == "domain:health"
    assert buckets[0].value == 1


def test_operations_conflicting_duplicate_identity_fails_closed() -> None:
    """Same operation result_id with different content raises without echo."""
    original = _operation_result("op-1", "domain:health")
    conflicting = _operation_result("op-1", "domain:general")

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as excinfo:
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(
                operation_evidence=(original, conflicting),
            ),
            generated_at=NOW,
        )

    payload = str(excinfo.value).lower()
    assert "op-1" in payload


def test_workflows_dedup_identical_and_count_once() -> None:
    """Identical DomainWorkflowResult duplicates count once."""
    workflow = _workflow_result("wf-1", "domain:health")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(workflow_evidence=(workflow, workflow)),
        generated_at=NOW,
    )

    buckets = _metric(snapshot, "workflows.by_domain").buckets
    assert len(buckets) == 1
    assert buckets[0].key == "domain:health"
    assert buckets[0].value == 1


def test_rules_dedup_identical_without_attribution_is_unavailable() -> None:
    """Identical DomainRuleExecutionResult duplicates normalize to one.

    rule_evidence is deduplicated before the rule path. Because
    DomainRuleExecutionResult carries no authoritative Domain identity here
    and no DomainTrace supplies rule references, the metric must be
    UNAVAILABLE — never an empty observed bucket.
    """
    rule = _rule_result("rule-1")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(rule_evidence=(rule, rule)),
        generated_at=NOW,
    )

    metric = _metric(snapshot, "rules.applied_by_domain")
    assert metric.status.value == "unavailable"


def test_sessions_dedup_identical_evidence_reference_not_duplicated() -> None:
    """Identical DomainSessionContext duplicates retain one reference."""
    session = _session("session-1")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(sessions=(session, session)),
        generated_at=NOW,
    )

    assert snapshot.evidence_session_ids == ("session-1",)


# ── D. Cross-domain transfer identity ────────────────────────────────────────


def test_identical_transfer_duplicates_count_once() -> None:
    """Two truly identical transfer records count once."""
    transfer = _transfer("domain:health", "domain:general", "knowledge", "transfer-1")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(cross_domain_transfers=(transfer, transfer)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "cross_domain.transfers").value == 1


def test_distinct_transfers_same_pair_kind_count_separately() -> None:
    """Distinct transfers with same source/target/kind count separately.

    The canonical occurrence identity for CrossDomainContextTransfer is the
    ``identifier`` field. Two transfers with the same domain pair and kind but
    different identifiers are two occurrences.
    """
    first = _transfer("domain:health", "domain:general", "knowledge", "transfer-1")
    second = _transfer("domain:health", "domain:general", "knowledge", "transfer-2")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(cross_domain_transfers=(first, second)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "cross_domain.transfers").value == 2
