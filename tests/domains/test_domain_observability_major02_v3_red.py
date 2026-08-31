"""Phase 10.37 — Audit V3 MAJOR-02 RED regressions: complete runtime evidence
validation and same-identity conflict normalization.

Audit defects under test:

1. ``_validate_evidence_element_types()`` validated only part of the
   canonically typed ``DomainObservabilityEvidence`` tuples. Malformed
   elements for registry_definitions / registry_records / load_results /
   resolution_results / compositions / events / traces reached normalization
   (arbitrary attribute access) instead of failing closed at the public
   evidence boundary with ``InvalidDomainObservabilityEvidenceError``.

2. Two canonical permission decisions with the same
   ``operation_id + operation_version`` but contradictory decisions
   (ALLOW vs DENY) are conflicting evidence for the SAME synthetic canonical
   observability identity and must fail closed before source precedence —
   not silently share/merge one occurrence key. Identical duplicates
   collapse to one; two distinct versions remain distinct.

3. Approval identity: ``PermissionApprovalRequirement.requirement_id`` is a
   canonical non-empty validated string, so it is a stable identity. The V3
   fallback ``("approval", type(result).__name__)`` must not cause unrelated
   approval requirements to merge merely because they are the same class;
   approval entries with distinct requirement IDs remain distinct.

Error text must remain safe: field name, expected canonical type, index —
never an arbitrary object repr/payload.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.contracts import DomainId
from cmm.domains.errors import InvalidDomainObservabilityEvidenceError
from cmm.domains.event_contracts import DomainEvent
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.observability_service import DomainObservabilityService
from cmm.domains.permission_adapters import DomainOperationPermissionDecision
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.resolver_contracts import DomainResolutionResult

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
HEALTH = DomainId.from_str("domain:health")


# ── 8.1 Missing runtime validation: malformed core fields fail closed ────────


def test_malformed_registry_definitions_fail_closed() -> None:
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(registry_definitions=({"fake": "definition"},))


def test_malformed_registry_records_fail_closed() -> None:
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(registry_records=({"fake": "record"},))


def test_malformed_load_results_fail_closed() -> None:
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(load_results=({"fake": "load"},))


def test_malformed_resolution_results_fail_closed() -> None:
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(resolution_results=({"fake": "resolution"},))


def test_malformed_compositions_fail_closed() -> None:
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(compositions=({"fake": "composition"},))


def test_malformed_events_fail_closed() -> None:
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(events=({"fake": "event"},))


def test_malformed_traces_fail_closed() -> None:
    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(traces=({"fake": "trace"},))


@pytest.mark.parametrize(
    "field",
    (
        "registry_definitions",
        "registry_records",
        "load_results",
        "resolution_results",
        "compositions",
        "conflict_results",
        "events",
        "traces",
        "sessions",
        "session_resume_results",
        "permission_evidence",
        "approval_evidence",
        "operation_evidence",
        "workflow_evidence",
        "rule_evidence",
        "resource_evidence",
        "cross_domain_transfers",
    ),
)
def test_every_canonically_typed_field_rejects_malformed_element(field) -> None:
    """Every declared tuple field must fail closed on a non-canonical element.

    A malformed string element is used (never a repr-sensitive object) so the
    error can be checked for safe content.
    """
    with pytest.raises(InvalidDomainObservabilityEvidenceError) as excinfo:
        DomainObservabilityEvidence(**{field: ("malformed-element",)})

    message = str(excinfo.value)
    assert field in message  # field name is safe and present
    # No arbitrary object repr/payload echo.
    assert "malformed-element" not in message


def test_malformed_secret_shaped_element_is_not_echoed() -> None:
    """A malformed element whose repr would carry a secret is not echoed."""
    secret_like = {"password": "super-secret-value", "fake": "event"}

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as excinfo:
        DomainObservabilityEvidence(events=(secret_like,))

    message = str(excinfo.value)
    assert "super-secret-value" not in message
    assert "password" not in message


def _resolution(result_id: str) -> DomainResolutionResult:
    from cmm.domains.resolver_contracts import DomainResolutionStatus

    return DomainResolutionResult(
        id=result_id,
        context_id=f"ctx-{result_id}",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=HEALTH,
        confidence=0.9,
    )


def test_valid_canonical_core_elements_remain_accepted() -> None:
    """Valid canonical objects in the previously unvalidated fields remain
    accepted and calculable — no over-validation."""
    from cmm.domains.composition_contracts import (
        DomainComposition,
        DomainCompositionStatus,
    )

    event = DomainEvent(
        event_id="evt-v3-valid",
        event_type="domain.resolution.completed",
        schema_version="1.0",
        domain_id=HEALTH,
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
    )
    composition = DomainComposition(
        id="comp-v3-valid",
        resolution_id="res-v3-valid",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=HEALTH,
        supporting_domains=(),
        composed_at=NOW,
    )

    evidence = DomainObservabilityEvidence(
        registry_definitions=(_registry_definition(),),
        registry_records=(_registry_record(),),
        resolution_results=(_resolution("res-v3-valid"),),
        compositions=(composition,),
        events=(event,),
        traces=(),
    )

    snapshot = DomainMetricsCalculator().calculate(evidence, generated_at=NOW)
    names = {item.name: item for item in snapshot.measurements}
    # The definition ID ("health") and the registry record ("domain:health")
    # are distinct canonical ID forms; both are counted as installed evidence.
    assert names["domains.installed"].value == 2
    assert {b.key: b.value for b in names["resolution.decisions_by_domain"].buckets} == {
        "domain:health": 1
    }


def _registry_definition():
    from cmm.domains.contracts import DomainDefinition

    return DomainDefinition(
        id=HEALTH,
        name="health",
        display_name="Health",
        version="1.0.0",
        kind="system",
        description="Health domain",
        manifest_id="manifest:health:1.0.0",
        enabled=True,
    )


def _registry_record() -> DomainRegistryRecord:
    return DomainRegistryRecord(
        definition=_registry_definition(),
        status=_active_status(),
        registered_at=NOW,
        updated_at=NOW,
    )


def _active_status():
    from cmm.domains.enums import DomainStatus

    return DomainStatus.ACTIVE


# ── 8.2 Same-identity permission conflicts fail closed ───────────────────────


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


def test_permission_same_identity_allow_and_deny_fails_closed() -> None:
    """same operation_id + same version + ALLOW + DENY → fail closed."""
    allow = _permission("domain.op", "1.0.0", PermissionOutcome.ALLOW)
    deny = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)

    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(permission_evidence=(allow, deny))


def test_permission_conflict_error_carries_no_reason_text() -> None:
    """No decision/reason text leaks into the conflict error."""
    allow = _permission("domain.op", "1.0.0", PermissionOutcome.ALLOW)
    deny = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as excinfo:
        DomainObservabilityEvidence(permission_evidence=(allow, deny))

    message = str(excinfo.value).lower()
    assert "allow" not in message
    assert "deny" not in message


def test_permission_conflict_also_fails_closed_in_calculator() -> None:
    """The same-identity conflict is rejected before any projection/metric."""
    allow = _permission("domain.op", "1.0.0", PermissionOutcome.ALLOW)
    deny = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)

    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(permission_evidence=(allow, deny)),
            generated_at=NOW,
        )


def test_permission_identical_duplicate_decisions_collapse_to_one() -> None:
    """Identical duplicate decisions (same identity, same decision) are one."""
    only = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(permission_evidence=(only, only)),
        generated_at=NOW,
    )

    rejected = next(
        item for item in snapshot.measurements if item.name == "permissions.rejected"
    )
    assert rejected.value == 1


def test_permission_two_distinct_versions_remain_distinct() -> None:
    """Two distinct versions are distinct canonical decisions — no conflict."""
    v1 = _permission("domain.op", "1.0.0", PermissionOutcome.DENY)
    v2 = _permission("domain.op", "2.0.0", PermissionOutcome.DENY)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(permission_evidence=(v1, v2)),
        generated_at=NOW,
    )

    rejected = next(
        item for item in snapshot.measurements if item.name == "permissions.rejected"
    )
    assert rejected.value == 2


def test_permission_two_allows_same_identity_remain_distinct_entries() -> None:
    """Two non-contradictory same-identity decisions (both ALLOW) are valid
    duplicate evidence and collapse to one — no false conflict."""
    allow_a = _permission("domain.op", "1.0.0", PermissionOutcome.ALLOW)
    allow_b = _permission("domain.op", "1.0.0", PermissionOutcome.ALLOW)

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(permission_evidence=(allow_a, allow_b)),
        generated_at=NOW,
    )

    rejected = next(
        item for item in snapshot.measurements if item.name == "permissions.rejected"
    )
    assert rejected.value == 0  # observed zero: evidence present, no denial


# ── 8.3 Approval identity must not collapse by class-name fallback ───────────


def _approval(requirement_id: str, operation_id: str) -> PermissionApprovalRequirement:
    return PermissionApprovalRequirement(
        requirement_id=requirement_id,
        action=PermissionCapability.OPERATION_EXECUTE,
        actor_id="actor-1",
        session_id="session-1",
        domain_id="domain:health",
        operation_id=operation_id,
        operation_version="1.0.0",
        fingerprint=f"fingerprint-{requirement_id}",
    )


def _service() -> DomainObservabilityService:
    from cmm.domains.health.bootstrap import (
        build_standard_health_domain_bootstrap,
    )
    from cmm.domains.observability_health import DomainHealthChecker

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


def test_unrelated_approval_requirements_remain_distinct_entries() -> None:
    """Two unrelated approval requirements (distinct requirement IDs, same
    class) must produce distinct log entries — never merged by a class-name
    fallback occurrence key."""
    first = _approval("approval-req-1", "health.op_a")
    second = _approval("approval-req-2", "health.op_b")

    report = _service().build_report(
        DomainObservabilityEvidence(approval_evidence=(first, second))
    )

    entries = [
        entry
        for entry in report.log_entries
        if entry.source_kind == "approval_evidence"
    ]
    assert len(entries) == 2
    assert {entry.source_id for entry in entries} == {
        "approval-req-1",
        "approval-req-2",
    }


def test_approval_log_source_id_is_requirement_id_not_class_name() -> None:
    """No approval entry may carry the class name as its source identity."""
    approval = _approval("approval-req-3", "health.op_c")

    report = _service().build_report(
        DomainObservabilityEvidence(approval_evidence=(approval,))
    )

    entries = [
        entry
        for entry in report.log_entries
        if entry.source_kind == "approval_evidence"
    ]
    assert len(entries) == 1
    assert entries[0].source_id == "approval-req-3"
    assert entries[0].source_id != "PermissionApprovalRequirement"


def test_approval_occurrence_keys_never_use_class_name_fallback() -> None:
    """Direct unit proof: the approval occurrence identity is the canonical
    requirement_id — never ``("approval", type(result).__name__)``."""
    from cmm.domains.observability_service import _approval_occurrence_keys

    first = _approval("approval-req-4", "health.op_d")
    second = _approval("approval-req-5", "health.op_e")

    keys_first = _approval_occurrence_keys(first)
    keys_second = _approval_occurrence_keys(second)

    assert keys_first != keys_second
    assert keys_first == frozenset({("approval", "approval-req-4")})
    assert keys_second == frozenset({("approval", "approval-req-5")})
    assert "PermissionApprovalRequirement" not in str(keys_first)


def test_approval_requested_counts_distinct_requirements() -> None:
    """approvals.requested counts distinct requirement IDs (2, not 1)."""
    first = _approval("approval-req-1", "health.op_a")
    second = _approval("approval-req-2", "health.op_b")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(approval_evidence=(first, second)),
        generated_at=NOW,
    )

    requested = next(
        item for item in snapshot.measurements if item.name == "approvals.requested"
    )
    assert requested.value == 2
