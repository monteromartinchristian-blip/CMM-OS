"""Phase 10.37 — MAJOR-02 RED regressions: bind metrics to real canonical
evidence.

Audit findings under test:

- 8.1 permission rejections: the canonical denial contract
  (``DomainOperationPermissionDecision``) does not expose ``decision_id``/``id``;
  the calculator must bind to its real canonical fields, not duck-type a
  missing ID.
- 8.4 session degradation: ``approval_refs`` / ``pending_domain_question_refs``
  are references, not degradation status. Sessions carrying only references
  must NOT be counted degraded.
- 8.3 resource metrics: canonical attribution lives in accepted
  ``DomainResourceBinding`` (domain_id), not a top-level ``domain_id``; no
  ``id(item)`` process-memory fallback.
- 8.5 knowledge reuse: no stable canonical reuse contract exists, so
  ``knowledge.reused`` must be UNAVAILABLE; duck typing via
  ``reused``/``reuse_count`` is forbidden.
- 8.6 evidence aggregate typing: where stable canonical contracts exist, the
  aggregate fields must be typed to them (no ``Any``).
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
from cmm.domains.contracts import DomainId
from cmm.domains.enums import (
    DomainResourceResolutionStatus,
)
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.permission_adapters import DomainOperationPermissionDecision
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceResolution,
)
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionResumeResult,
    DomainSessionResumeStatus,
)

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def _permission_decision(
    operation_id: str,
    outcome: PermissionOutcome,
) -> DomainOperationPermissionDecision:
    return DomainOperationPermissionDecision(
        operation_id=operation_id,
        operation_version="1.0.0",
        decision=outcome,
    )


def _session(
    session_id: str,
    *,
    approval_refs: tuple[str, ...] = (),
    pending_question_refs: tuple[str, ...] = (),
) -> DomainSessionContext:
    return DomainSessionContext(
        session_id=session_id,
        primary_domain="domain:health",
        approval_refs=approval_refs,
        pending_domain_question_refs=pending_question_refs,
        updated_at=NOW,
    )


def _binding(binding_id: str, domain_id: str) -> DomainResourceBinding:
    return DomainResourceBinding(
        id=binding_id,
        resource_id=f"resource:{binding_id}",
        definition_id=f"definition:{binding_id}",
        domain_id=DomainId.from_str(domain_id),
        adapter="source-test",
        provenance=("test",),
    )


def _resolution(
    resolution_id: str,
    bindings: tuple[DomainResourceBinding, ...],
) -> DomainResourceResolution:
    return DomainResourceResolution(
        id=resolution_id,
        resource_id=f"resource:{resolution_id}",
        status=DomainResourceResolutionStatus.RESOLVED,
        trace_id=f"trace:{resolution_id}",
        resolved_at=NOW,
        bindings=bindings,
    )


def _metric(snapshot, name: str):
    for measurement in snapshot.measurements:
        if measurement.name == name:
            return measurement
    raise AssertionError(f"metric {name} missing from snapshot")


# ── 8.1 Permission rejections bound to canonical fields ──────────────────────


def test_permission_deny_canonical_decision_counts_one() -> None:
    """A canonical DENY decision counts rejected=1 via its real fields."""
    decision = _permission_decision("op-deny-1", PermissionOutcome.DENY)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(permission_evidence=(decision,)),
        generated_at=NOW,
    )

    metric = _metric(snapshot, "permissions.rejected")
    assert metric.status.value == "observed"
    assert metric.value == 1
    assert metric.evidence_reference_ids == ("op-deny-1",)


def test_permission_allow_counts_zero() -> None:
    """An ALLOW canonical decision yields rejected=0 (observed zero)."""
    allow = _permission_decision("op-allow-1", PermissionOutcome.ALLOW)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(permission_evidence=(allow,)),
        generated_at=NOW,
    )

    metric = _metric(snapshot, "permissions.rejected")
    assert metric.status.value == "observed"
    assert metric.value == 0


def test_permission_two_denies_count_two() -> None:
    """Two distinct canonical DENY decisions count rejected=2."""
    deny_a = _permission_decision("op-deny-a", PermissionOutcome.DENY)
    deny_b = _permission_decision("op-deny-b", PermissionOutcome.DENY)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(permission_evidence=(deny_a, deny_b)),
        generated_at=NOW,
    )

    metric = _metric(snapshot, "permissions.rejected")
    assert metric.status.value == "observed"
    assert metric.value == 2


# ── 8.4 Session degradation: references are not degradation ─────────────────


def test_session_with_approval_refs_only_is_not_degraded() -> None:
    """approval_refs are references, not degradation status."""
    session = _session("session-a", approval_refs=("approval-1", "approval-2"))

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(sessions=(session,)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "sessions.degraded").status.value == "unavailable"


def test_session_with_pending_question_refs_only_is_not_degraded() -> None:
    """pending_domain_question_refs are references, not degradation status."""
    session = _session("session-b", pending_question_refs=("question-1",))

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(sessions=(session,)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "sessions.degraded").status.value == "unavailable"


def test_session_resume_blocked_counts_degraded_once_per_session() -> None:
    """A BLOCKED resume result is explicit degradation evidence.

    Two degraded resume records for the same session count once.
    """
    blocked = DomainSessionResumeResult(
        status=DomainSessionResumeStatus.BLOCKED,
        session_id="session-c",
        previous_revision=4,
        resumed_revision=4,
    )

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(
            session_resume_results=(blocked, blocked),
        ),
        generated_at=NOW,
    )

    metric = _metric(snapshot, "sessions.degraded")
    assert metric.status.value == "observed"
    assert metric.value == 1


def test_session_with_no_degradation_evidence_is_unavailable() -> None:
    """A normal session (no refs, no degradation) is not degraded."""
    session = _session("session-d")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(sessions=(session,)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "sessions.degraded").status.value == "unavailable"


# ── 8.3 Resource metrics bound to accepted bindings ──────────────────────────


def test_resources_loaded_by_domain_from_accepted_bindings() -> None:
    """Resource attribution comes from accepted binding domain_id."""
    health_binding = _binding("binding-1", "domain:health")
    general_binding = _binding("binding-2", "domain:general")
    resolution = _resolution(
        "resolution-1",
        bindings=(health_binding, general_binding),
    )

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(resource_evidence=(resolution,)),
        generated_at=NOW,
    )

    metric = _metric(snapshot, "resources.loaded_by_domain")
    assert metric.status.value == "observed"
    buckets = {bucket.key: bucket.value for bucket in metric.buckets}
    assert buckets == {"domain:general": 1, "domain:health": 1}
    assert "id(" not in " ".join(metric.evidence_reference_ids)


def test_resources_without_attributable_bindings_is_unavailable() -> None:
    """A resolution with no acceptable bindings cannot fabricate a bucket."""
    resolution = DomainResourceResolution(
        id="resolution-empty",
        resource_id="resource:empty",
        status=DomainResourceResolutionStatus.REJECTED,
        trace_id="trace:empty",
        resolved_at=NOW,
        bindings=(),
    )

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(resource_evidence=(resolution,)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "resources.loaded_by_domain").status.value == "unavailable"


def test_resources_identical_binding_counts_once() -> None:
    """Duplicate identical canonical resolution evidence counts once."""
    binding = _binding("binding-3", "domain:health")
    resolution = _resolution("resolution-2", bindings=(binding,))

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(resource_evidence=(resolution, resolution)),
        generated_at=NOW,
    )

    metric = _metric(snapshot, "resources.loaded_by_domain")
    assert metric.status.value == "observed"
    buckets = {bucket.key: bucket.value for bucket in metric.buckets}
    assert buckets == {"domain:health": 1}


# ── 8.5 Knowledge reuse stays UNAVAILABLE ────────────────────────────────────


def test_knowledge_reuse_duck_typing_is_not_accepted() -> None:
    """An object with reused=True/reuse_count>0 must NOT be reuse evidence."""
    fake_reuse = {"reused": True, "reuse_count": 3}

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(resource_evidence=(fake_reuse,)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "knowledge.reused").status.value == "unavailable"


def test_knowledge_reuse_without_canonical_evidence_is_unavailable() -> None:
    """Without canonical reuse evidence, knowledge.reused is UNAVAILABLE."""
    binding = _binding("binding-4", "domain:health")
    resolution = _resolution("resolution-3", bindings=(binding,))

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(resource_evidence=(resolution,)),
        generated_at=NOW,
    )

    assert _metric(snapshot, "knowledge.reused").status.value == "unavailable"


# ── 8.6 Evidence aggregate typing ────────────────────────────────────────────


def test_evidence_aggregate_types_are_canonical_not_any() -> None:
    """Stable canonical evidence categories must be typed, not Any."""
    import typing

    fields = typing.get_type_hints(DomainObservabilityEvidence)
    assert fields["permission_evidence"] != typing.Any
    assert fields["approval_evidence"] != typing.Any
    assert fields["resource_evidence"] != typing.Any
