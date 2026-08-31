"""Phase 10.37 — Domain Observability metric catalog and pure calculator tests.

Proves the exact 25-entry canonical metric catalog, clean OBSERVED/UNAVAILABLE
semantics, deterministic ordering and pure calculation over canonical evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionStatus,
)
from cmm.domains.contracts import DomainDefinition, DomainId
from cmm.domains.discovery_contracts import DomainCandidate
from cmm.domains.enums import (
    DomainLoadStatus,
    DomainSourceKind,
    DomainStatus,
)
from cmm.domains.loader_contracts import DomainLoadResult
from cmm.domains.observability_metrics import (
    CANONICAL_DOMAIN_OBSERVABILITY_METRICS,
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.resolver_contracts import (
    DomainResolutionResult,
    DomainResolutionStatus,
)

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)

EXPECTED_METRICS = (
    "domains.installed",
    "domains.active",
    "loading.duration.mean_ms",
    "loading.failures",
    "resolution.decisions_by_domain",
    "resolution.confidence.mean",
    "resolution.ambiguous",
    "resolution.fallback",
    "execution.multi_domain",
    "execution.domains.mean",
    "conflicts.detected",
    "permissions.rejected",
    "approvals.requested",
    "operations.by_domain",
    "workflows.by_domain",
    "workflows.duration.mean_ms",
    "rules.applied_by_domain",
    "resources.loaded_by_domain",
    "cross_domain.transfers",
    "knowledge.reused",
    "questions.avoided_shared_context",
    "duplicates.prevented",
    "errors.by_domain_pack",
    "sessions.degraded",
    "external_domains.active",
)


def test_canonical_catalog_is_exactly_25_unique() -> None:
    assert CANONICAL_DOMAIN_OBSERVABILITY_METRICS == EXPECTED_METRICS
    assert len(CANONICAL_DOMAIN_OBSERVABILITY_METRICS) == 25
    assert len(set(CANONICAL_DOMAIN_OBSERVABILITY_METRICS)) == 25


def _definition(
    domain_id: str, *, enabled: bool = True, kind: str = "system"
) -> DomainDefinition:
    slug = domain_id.removeprefix("domain:")
    return DomainDefinition(
        id=DomainId.from_str(domain_id),
        name=slug,
        display_name=slug.title(),
        version="1.0.0",
        kind=kind,
        description=f"Description of {domain_id}",
        manifest_id=f"manifest:{slug}:1.0.0",
        enabled=enabled,
    )


def _registry_record(domain_id: str, status: DomainStatus) -> DomainRegistryRecord:
    return DomainRegistryRecord(
        definition=_definition(domain_id),
        status=status,
        registered_at=NOW,
        updated_at=NOW,
    )


def _candidate(domain_id: str) -> DomainCandidate:
    slug = domain_id.removeprefix("domain:")
    return DomainCandidate(
        candidate_id=f"{slug}:1.0.0",
        source_id="source-test",
        source_kind=DomainSourceKind.DEVELOPMENT,
        location=f"/tmp/{slug}",
        manifest_path="manifest.json",
        domain_id=domain_id,
        detected_version="1.0.0",
        checksum=f"sha256:{'ab' * 32}",
        trusted=True,
        discovered_at=NOW,
    )


def _load_result(
    candidate_id: str,
    status: DomainLoadStatus,
    *,
    errors: tuple[str, ...] = (),
    duration_ms: int | None = None,
) -> DomainLoadResult:
    metadata = {"duration_ms": duration_ms} if duration_ms is not None else {}
    return DomainLoadResult(
        candidate=_candidate(candidate_id),
        status=status,
        pack=None,
        registry_record=None,
        errors=errors,
        warnings=(),
        loaded_at=NOW,
        metadata=metadata,
    )


def _load_ok(candidate_id: str, duration_ms: int) -> DomainLoadResult:
    return DomainLoadResult(
        candidate=_candidate(candidate_id),
        status=DomainLoadStatus.VALID,
        pack=None,
        registry_record=None,
        errors=(),
        warnings=(),
        loaded_at=datetime(2026, 8, 31, 11, 59, 0, tzinfo=timezone.utc),
        metadata={"duration_ms": duration_ms},
    )


def _load_failed(candidate_id: str, duration_ms: int) -> DomainLoadResult:
    return DomainLoadResult(
        candidate=_candidate(candidate_id),
        status=DomainLoadStatus.FAILED,
        pack=None,
        registry_record=None,
        errors=("load failure",),
        warnings=(),
        loaded_at=datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc),
        metadata={"duration_ms": duration_ms},
    )


def _load_failed(candidate_id: str, duration_ms: int) -> DomainLoadResult:
    return _load_result(
        candidate_id,
        DomainLoadStatus.FAILED,
        errors=("load failure",),
        duration_ms=duration_ms,
    )


def test_metrics_from_empty_evidence_are_all_unavailable() -> None:
    calculator = DomainMetricsCalculator()
    snapshot = calculator.calculate(DomainObservabilityEvidence(), generated_at=NOW)

    assert len(snapshot.measurements) == 25
    for measurement in snapshot.measurements:
        assert measurement.status.value == "unavailable"
        assert measurement.value is None


def test_installed_and_active_metrics() -> None:
    general = _registry_record("domain:general", DomainStatus.ACTIVE)
    health = _registry_record("domain:health", DomainStatus.ACTIVE)
    legacy = _registry_record("domain:legacy", DomainStatus.DISABLED)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(
            registry_records=(general, health, legacy),
        ),
        generated_at=NOW,
    )

    by_name = {measurement.name: measurement for measurement in snapshot.measurements}

    assert by_name["domains.installed"].value == 3
    assert by_name["domains.active"].value == 2


def test_load_failures_and_mean_duration() -> None:
    ok = _load_ok("domain:general", 40)
    fail = _load_failed("domain:general", 80)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(load_results=(ok, fail)),
        generated_at=NOW,
    )

    by_name = {measurement.name: measurement for measurement in snapshot.measurements}

    assert by_name["loading.failures"].value == 1
    assert by_name["loading.duration.mean_ms"].value == 60.0


def test_load_duration_unavailable_without_explicit_duration() -> None:
    load = _load_result("domain:general", DomainLoadStatus.VALID)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(load_results=(load,)),
        generated_at=NOW,
    )

    by_name = {measurement.name: measurement for measurement in snapshot.measurements}
    assert by_name["loading.duration.mean_ms"].status.value == "unavailable"


def test_resolution_decisions_and_confidence() -> None:
    res_a = DomainResolutionResult(
        id="res-1",
        context_id="ctx-1",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId.from_str("domain:health"),
        confidence=0.91,
    )
    res_b = DomainResolutionResult(
        id="res-2",
        context_id="ctx-2",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId.from_str("domain:general"),
        confidence=0.75,
    )

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(resolution_results=(res_a, res_b)),
        generated_at=NOW,
    )

    by_name = {measurement.name: measurement for measurement in snapshot.measurements}
    buckets = {
        bucket.key: bucket.value
        for bucket in by_name["resolution.decisions_by_domain"].buckets
    }
    assert buckets == {"domain:general": 1, "domain:health": 1}
    assert by_name["resolution.confidence.mean"].value == pytest.approx(0.83)


def test_resolution_ambiguous_count() -> None:
    ambiguous = DomainResolutionResult(
        id="res-3",
        context_id="ctx-3",
        status=DomainResolutionStatus.AMBIGUOUS,
        ambiguous_domains=(
            DomainId.from_str("domain:health"),
            DomainId.from_str("domain:general"),
        ),
        requires_clarification=True,
        recommended_question="Which domain is relevant?",
    )

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(resolution_results=(ambiguous,)),
        generated_at=NOW,
    )

    by_name = {measurement.name: measurement for measurement in snapshot.measurements}
    assert by_name["resolution.ambiguous"].value == 1


def test_multi_domain_execution_from_composition() -> None:
    composition = DomainComposition(
        id="comp-1",
        resolution_id="res-1",
        primary_domain=DomainId.from_str("domain:health"),
        supporting_domains=(DomainId.from_str("domain:general"),),
        status=DomainCompositionStatus.COMPOSED,
    )

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(compositions=(composition,)),
        generated_at=NOW,
    )

    by_name = {measurement.name: measurement for measurement in snapshot.measurements}
    assert by_name["execution.multi_domain"].value == 1
    assert by_name["execution.domains.mean"].value == 2.0


def test_measurements_follow_canonical_catalog_order() -> None:
    calculator = DomainMetricsCalculator()
    snapshot = calculator.calculate(DomainObservabilityEvidence(), generated_at=NOW)

    assert [measurement.name for measurement in snapshot.measurements] == list(
        CANONICAL_DOMAIN_OBSERVABILITY_METRICS
    )


def test_snapshot_is_deterministic_for_same_evidence() -> None:
    evidence = DomainObservabilityEvidence(
        registry_records=(_registry_record("domain:general", DomainStatus.ACTIVE),),
    )

    first = DomainMetricsCalculator().calculate(evidence, generated_at=NOW)
    second = DomainMetricsCalculator().calculate(evidence, generated_at=NOW)

    assert first.to_dict() == second.to_dict()
    assert first.digest == second.digest
