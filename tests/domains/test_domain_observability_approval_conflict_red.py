"""Phase 10.37 — Audit V4 residual MAJOR RED: same-ID conflicting approvals.

Audit V4 residual defect under test:

    same PermissionApprovalRequirement.requirement_id
    + materially conflicting canonical approval content
    → not rejected before source precedence

The remediation contract:

    same requirement_id + identical/equivalent canonical requirement
    → one logical identity / duplicate acceptable

    same requirement_id + materially conflicting canonical requirement
    → InvalidDomainObservabilityEvidenceError

    different requirement_id
    → distinct approval occurrences

Error text must remain reference-safe: source type and requirement_id only —
never actor/session payload, never fingerprint contents, never a repr.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
)
from cmm.domains.errors import InvalidDomainObservabilityEvidenceError
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def _approval(requirement_id: str, **overrides) -> PermissionApprovalRequirement:
    """A valid canonical approval requirement, with material overrides."""
    defaults = {
        "requirement_id": requirement_id,
        "action": PermissionCapability.OPERATION_EXECUTE,
        "actor_id": "actor-1",
        "session_id": "session-1",
        "domain_id": "domain:health",
        "operation_id": "health.op_a",
        "operation_version": "1.0.0",
        "fingerprint": f"fingerprint-{requirement_id}",
    }
    defaults.update(overrides)
    return PermissionApprovalRequirement(**defaults)


# ── RED A — same identity, contradictory content ─────────────────────────────


def test_same_requirement_id_conflicting_content_fails_closed() -> None:
    """Same requirement_id + a different material canonical field must be
    rejected at the public evidence boundary, before source precedence."""
    first = _approval("approval-req-1")
    conflicting = _approval("approval-req-1", operation_id="health.op_z")

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as err:
        DomainObservabilityEvidence(approval_evidence=(first, conflicting))

    # Safe error: source type and requirement_id only.
    message = str(err.value)
    assert "PermissionApprovalRequirement" in message
    assert "approval-req-1" in message
    assert "fingerprint-" not in message
    assert "actor-1" not in message
    assert "session-1" not in message


def test_same_requirement_id_conflicting_action_fails_closed() -> None:
    """A different material canonical field (here: action) is also a
    conflict for one identity."""
    first = _approval("approval-req-2")
    conflicting = _approval("approval-req-2", action=PermissionCapability.FILE_MODIFY)

    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(approval_evidence=(first, conflicting))


# ── RED B — identical duplicate remains admissible ───────────────────────────


def test_identical_duplicate_approval_remains_admissible() -> None:
    """Same exact canonical approval object duplicated → accepted, and the
    downstream report shows one logical approval log occurrence."""
    from cmm.domains.health.bootstrap import (
        build_standard_health_domain_bootstrap,
    )
    from cmm.domains.observability_health import DomainHealthChecker
    from cmm.domains.observability_service import DomainObservabilityService

    bootstrap = build_standard_health_domain_bootstrap()
    service = DomainObservabilityService(
        metrics_calculator=DomainMetricsCalculator(),
        health_checker=DomainHealthChecker(
            domain_registry=bootstrap.domain_registry,
            resource_registry=bootstrap.resource_registry,
            rule_registry=bootstrap.rule_registry,
            operation_registry=bootstrap.operation_registry,
            workflow_registry=bootstrap.workflow_registry,
            permission_registry=bootstrap.permission_registry,
            manifest_validation_lookup=lambda domain_id: None,
            clock=lambda: NOW,
        ),
        clock=lambda: NOW,
    )

    first = _approval("approval-req-dup")
    duplicate = _approval("approval-req-dup")

    report = service.build_report(
        DomainObservabilityEvidence(approval_evidence=(first, duplicate))
    )

    entries = [
        entry
        for entry in report.log_entries
        if entry.source_kind == "approval_evidence"
    ]
    assert len(entries) == 1
    assert entries[0].source_id == "approval-req-dup"


# ── RED C — different IDs remain distinct ────────────────────────────────────


def test_different_requirement_ids_remain_distinct() -> None:
    """Two canonical approval requirements with different requirement_ids
    (same class) produce two distinct approval occurrences — the accepted V4
    class-name fallback removal is preserved."""
    from cmm.domains.health.bootstrap import (
        build_standard_health_domain_bootstrap,
    )
    from cmm.domains.observability_health import DomainHealthChecker
    from cmm.domains.observability_service import DomainObservabilityService

    bootstrap = build_standard_health_domain_bootstrap()
    service = DomainObservabilityService(
        metrics_calculator=DomainMetricsCalculator(),
        health_checker=DomainHealthChecker(
            domain_registry=bootstrap.domain_registry,
            resource_registry=bootstrap.resource_registry,
            rule_registry=bootstrap.rule_registry,
            operation_registry=bootstrap.operation_registry,
            workflow_registry=bootstrap.workflow_registry,
            permission_registry=bootstrap.permission_registry,
            manifest_validation_lookup=lambda domain_id: None,
            clock=lambda: NOW,
        ),
        clock=lambda: NOW,
    )

    first = _approval("approval-req-1")
    second = _approval("approval-req-2")

    report = service.build_report(
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


# ── RED D — safe error ───────────────────────────────────────────────────────


def test_conflict_error_is_reference_safe() -> None:
    """The conflict error may include the source type and the safe
    requirement_id, but must not echo fingerprint contents, actor/session
    payload, or a repr of the object."""
    first = _approval("approval-req-safe")
    conflicting = _approval("approval-req-safe", operation_id="health.op_z")

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as err:
        DomainObservabilityEvidence(approval_evidence=(first, conflicting))

    message = str(err.value)
    assert "PermissionApprovalRequirement" in message
    assert "approval-req-safe" in message
    # Never echo sensitive material:
    assert "fingerprint-" not in message
    assert "actor-1" not in message
    assert "session-1" not in message


# ── RED V5 — complete canonical approval material comparison ────────────────


def test_same_requirement_id_different_risk_fails_closed() -> None:
    """Same requirement_id + different canonical risk must fail closed (V5
    MAJOR-01: risk is validated canonical approval semantics)."""
    first = _approval("approval-req-risk")
    conflicting = _approval("approval-req-risk", risk="high")

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as err:
        DomainObservabilityEvidence(approval_evidence=(first, conflicting))

    # Safe error: source type and requirement_id only — never risk detail.
    message = str(err.value)
    assert "PermissionApprovalRequirement" in message
    assert "approval-req-risk" in message
    assert "high" not in message


def test_same_requirement_id_different_sensitivity_fails_closed() -> None:
    """Same requirement_id + different canonical sensitivity must fail
    closed."""
    from cmm.agent_runtime.agent_security_enums import SensitivityLevel

    first = _approval("approval-req-sensitivity")
    conflicting = _approval(
        "approval-req-sensitivity", sensitivity=SensitivityLevel.RESTRICTED
    )

    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(approval_evidence=(first, conflicting))


def test_same_requirement_id_different_constraints_fails_closed() -> None:
    """Same requirement_id + materially different canonical constraints must
    fail closed (canonical constraint contents compared, not identity)."""
    first = _approval(
        "approval-req-constraints", constraints={"allow_external_access": True}
    )
    conflicting = _approval(
        "approval-req-constraints", constraints={"allow_external_access": False}
    )

    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(approval_evidence=(first, conflicting))


def test_same_requirement_id_different_reason_code_fails_closed() -> None:
    """Same requirement_id + different canonical reason_code must fail
    closed."""
    first = _approval("approval-req-reason")
    conflicting = _approval("approval-req-reason", reason_code="policy_override")

    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(approval_evidence=(first, conflicting))


def test_same_requirement_id_different_purpose_fails_closed() -> None:
    """Same requirement_id + different canonical purpose must fail closed."""
    first = _approval("approval-req-purpose", purpose="routine")
    conflicting = _approval("approval-req-purpose", purpose="emergency")

    with pytest.raises(InvalidDomainObservabilityEvidenceError):
        DomainObservabilityEvidence(approval_evidence=(first, conflicting))


def test_identical_duplicate_with_full_semantic_fields_remains_admissible() -> None:
    """The complete semantic comparison must not reject two genuinely
    equivalent canonical requirements: identical risk/sensitivity/purpose/
    reason_code/constraints on both copies is one identity."""
    from cmm.agent_runtime.agent_security_enums import SensitivityLevel

    kwargs = {
        "risk": "high",
        "sensitivity": SensitivityLevel.CONFIDENTIAL,
        "purpose": "export",
        "reason_code": "policy_approval_required",
        "constraints": {
            "allow_external_access": True,
            "allowed_resources": ("res:a", "res:b"),
        },
    }
    first = _approval("approval-req-full-dup", **kwargs)
    duplicate = _approval("approval-req-full-dup", **kwargs)

    DomainObservabilityEvidence(approval_evidence=(first, duplicate))
