"""Phase 10.15 Block 2 – Domain Permission Gate tests.

Covers:
- Gate ALLOW, DENY, APPROVAL_REQUIRED outcomes
- Atomic validate_and_consume via ApprovalService
- Concurrent one_time consumption
- Dry-run mode
- Reusable grants
- Revocation
- Expiration
- Scope/domain/action mismatch
- Operation gate integration
- Workflow gate integration
- Cross-domain gate
- Bridge contract conversion
- External domain trust
- ApprovalConsumptionEvidence contract
- Gate backward compatibility (no gate injected)
"""

from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.approval_contracts import (
    ApprovalConsumptionEvidence,
    ApprovalDecision,
    ApprovalRequirement,
)
from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    EffectivePermissionResult,
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionLayer,
    PermissionLayerEvaluation,
    PermissionOutcome,
)
from cmm.agent_runtime.enums import (
    ApprovalDecisionType,
    ApprovalRequirementSource,
    PolicyRiskLevel,
)
from cmm.agent_runtime.errors import InvalidApprovalContractError
from cmm.domains.approval_bridge import (
    to_approval_requirement,
    to_approval_requirements,
)
from cmm.domains.enums import DomainOperationStatus, DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.permission_adapters import evaluate_domain_operation
from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateOutcome,
    PermissionGateResult,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_FUTURE_EXPIRY = datetime(2027, 6, 1, 13, 0, 0, tzinfo=timezone.utc)


def _id() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


@dataclass
class _FakeResolution:
    effective_permissions: EffectivePermissionResult


class _FakeResolver:
    """Configurable fake resolver for testing the gate in isolation."""

    def __init__(
        self,
        decision: PermissionOutcome,
        *,
        reasons: tuple[str, ...] = (),
        approval_requirements: tuple[PermissionApprovalRequirement, ...] = (),
    ):
        self._decision = decision
        self._reasons = reasons
        self._approval_requirements = approval_requirements

    def resolve(self, request, **kwargs):
        layer = PermissionLayerEvaluation(
            PermissionLayer.DOMAIN,
            self._decision,
            source_id=f"primary:{request.domain_id}:v1",
            policy_id="test-policy",
            policy_version="1",
            domain_role="primary",
            matched_rules=("test-policy",),
            reasons=self._reasons,
            approval_requirements=self._approval_requirements,
        )
        return _FakeResolution(
            EffectivePermissionResult(
                request_id=request.request_id,
                action=request.action,
                decision=self._decision,
                layer_evaluations=(layer,),
                approval_requirements=self._approval_requirements,
                denied_by=(layer.source_id,)
                if self._decision is PermissionOutcome.DENY
                else (),
                allowed_by=(layer.source_id,)
                if self._decision is PermissionOutcome.ALLOW
                else (),
                unresolved_by=(layer.source_id,)
                if self._decision is PermissionOutcome.ABSTAIN
                else (),
                reasons=self._reasons,
            )
        )


def _create_approval_service_and_request(
    permission_requirement: PermissionApprovalRequirement | None = None,
    *,
    status: str = "approved",
    expires_at: datetime | None = None,
    metadata: dict | None = None,
) -> tuple[ApprovalService, str]:
    """Create an ApprovalService with a pre-approved request."""
    repo = InMemoryApprovalRepository()
    service = ApprovalService(repo)

    if permission_requirement is None:
        requirement = ApprovalRequirement(
            id=_id(),
            source=ApprovalRequirementSource.SECURITY,
            title="Test approval",
            description="Test approval for gate testing",
            reason_codes=("test",),
            scope="operation",
            agent_run_id="run-1",
            expires_at=expires_at,
            metadata=metadata or {},
        )
    else:
        requirement = to_approval_requirement(
            permission_requirement,
            agent_run_id="run-1",
        )
    request = service.create_request_from_requirement(
        requirement,
        requested_by="agent-runtime",
    )
    if status == "approved":
        service.approve(
            request.id,
            "human-approver",
            comment="Approved for testing",
        )

    return service, request.id


# ── 1. Gate ALLOW ────────────────────────────────────────────────────────────


class TestGateAllow:
    def test_allow_returns_allowed(self):
        resolver = _FakeResolver(PermissionOutcome.ALLOW, reasons=("policy_allow",))
        gate = DomainPermissionGate(resolver, clock=lambda: _NOW)
        result = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
        )
        assert result.allowed
        assert not result.denied
        assert not result.requires_approval
        assert result.outcome == PermissionGateOutcome.ALLOW

    def test_allow_has_no_approval_evidence(self):
        resolver = _FakeResolver(PermissionOutcome.ALLOW)
        gate = DomainPermissionGate(resolver, clock=lambda: _NOW)
        result = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
        )
        assert result.approval_evidence is None


# ── 2. Gate DENY ─────────────────────────────────────────────────────────────


class TestGateDeny:
    def test_deny_returns_denied(self):
        resolver = _FakeResolver(
            PermissionOutcome.DENY, reasons=("capability_not_allowed",)
        )
        gate = DomainPermissionGate(resolver, clock=lambda: _NOW)
        result = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
        )
        assert result.denied
        assert not result.allowed
        assert result.outcome == PermissionGateOutcome.DENY
        assert "capability_not_allowed" in result.reasons


# ── 3. Gate APPROVAL_REQUIRED without approval_request_id ────────────────────


class TestGateApprovalRequired:
    def test_approval_required_without_id(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            fingerprint="fp-1",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        gate = DomainPermissionGate(resolver, clock=lambda: _NOW)
        result = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
        )
        assert result.requires_approval
        assert not result.allowed
        assert result.outcome == PermissionGateOutcome.APPROVAL_REQUIRED
        assert len(result.approval_requirements) == 1


# ── 4. Gate APPROVAL_CONSUMED (happy path) ───────────────────────────────────


class TestGateApprovalConsumed:
    def test_approval_consumed_grants_access(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-1",
            scope="operation",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        service, request_id = _create_approval_service_and_request(par)
        gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)
        result = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
            approval_request_id=request_id,
        )
        assert result.allowed
        assert result.outcome == PermissionGateOutcome.APPROVAL_CONSUMED
        assert result.approval_evidence is not None
        assert result.approval_evidence["granted"] is True


class TestGateDecisionIdentity:
    @staticmethod
    def _approval_consumption_scenario(id_factory):
        requirement = PermissionApprovalRequirement(
            requirement_id="par-post-approval-identity",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="test.post-approval-identity",
            operation_version="1.0.0",
            fingerprint="fp-post-approval-identity",
            scope="operation",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(requirement,),
        )
        service, approval_request_id = _create_approval_service_and_request(requirement)
        gate = DomainPermissionGate(
            resolver,
            service,
            clock=lambda: _NOW,
            id_factory=id_factory,
        )
        operation = DomainOperationDefinition(
            operation_id="test.post-approval-identity",
            domain_id="domain:test",
            version="1.0.0",
            name="Post-approval identity validation test",
            description="Exercises identity reservation before approval consumption.",
            operation_type=DomainOperationType.ANALYSIS,
            risk_level=PolicyRiskLevel.LOW,
            reversible=True,
        )
        return gate, service, approval_request_id, operation

    def test_each_evaluation_has_a_distinct_default_decision_identity(self):
        """Catches reuse of request identity or one gate identity across evaluations."""
        resolver = _FakeResolver(PermissionOutcome.ALLOW)
        gate = DomainPermissionGate(resolver, clock=lambda: _NOW)

        first = gate.evaluate_operation(
            request_id="same-request",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
        )
        second = gate.evaluate_operation(
            request_id="same-request",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
        )

        assert first.decision_id.startswith("permission-gate-decision-")
        assert second.decision_id.startswith("permission-gate-decision-")
        assert first.decision_id != second.decision_id

    def test_injected_id_factory_controls_gate_decision_identity(self):
        """Catches a gate that bypasses its deterministic identity dependency."""
        decision_ids = iter(("decision-first", "decision-second"))
        resolver = _FakeResolver(PermissionOutcome.DENY)
        gate = DomainPermissionGate(
            resolver,
            clock=lambda: _NOW,
            id_factory=decision_ids.__next__,
        )

        first = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
        )
        second = gate.evaluate_workflow(
            request_id="req-2",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            workflow_id="workflow-1",
        )

        assert first.decision_id == "decision-first"
        assert second.decision_id == "decision-second"

    @pytest.mark.parametrize("generated", ["", "   ", None, 7])
    def test_gate_rejects_invalid_generated_decision_identity(self, generated):
        """Catches gate-produced decisions with missing or blank runtime identity."""
        resolver = _FakeResolver(PermissionOutcome.ALLOW)
        gate = DomainPermissionGate(
            resolver,
            clock=lambda: _NOW,
            id_factory=lambda: generated,
        )

        with pytest.raises(ValueError, match="non-empty string"):
            gate.evaluate_operation(
                request_id="req-invalid-id",
                domain_id="domain:test",
                actor_id="actor-1",
                session_id="sess-1",
                operation_id="op-1",
            )

    def test_gate_rejects_duplicate_generated_decision_identity(self):
        """Catches two gate evaluations that claim the same runtime decision."""
        resolver = _FakeResolver(PermissionOutcome.ALLOW)
        gate = DomainPermissionGate(
            resolver,
            clock=lambda: _NOW,
            id_factory=lambda: "duplicate-decision",
        )
        gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
        )

        with pytest.raises(ValueError, match="unique"):
            gate.evaluate_operation(
                request_id="req-2",
                domain_id="domain:test",
                actor_id="actor-1",
                session_id="sess-1",
                operation_id="op-1",
            )

    def test_invalid_post_approval_identity_does_not_consume_approval(self):
        """Catches invalid ID validation that runs after one-time consumption."""
        gate, service, approval_request_id, operation = (
            self._approval_consumption_scenario(lambda: "")
        )

        with pytest.raises(ValueError, match="non-empty string"):
            gate.evaluate_operation_definition(
                operation,
                request_id="req-invalid-post-approval-id",
                actor_id="actor-1",
                session_id="sess-1",
                approval_request_id=approval_request_id,
            )

        assert service.repository.is_consumed(approval_request_id) is False

    def test_duplicate_post_approval_identity_does_not_consume_approval(self):
        """Catches duplicate ID validation that runs after one-time consumption."""
        gate, service, approval_request_id, operation = (
            self._approval_consumption_scenario(lambda: "duplicate-decision")
        )
        pending = gate.evaluate_operation_definition(
            operation,
            request_id="req-pending-duplicate-id",
            actor_id="actor-1",
            session_id="sess-1",
        )
        assert pending.decision_id == "duplicate-decision"

        with pytest.raises(ValueError, match="unique"):
            gate.evaluate_operation_definition(
                operation,
                request_id="req-duplicate-post-approval-id",
                actor_id="actor-1",
                session_id="sess-1",
                approval_request_id=approval_request_id,
            )

        assert service.repository.is_consumed(approval_request_id) is False

    def test_decision_identity_round_trip_and_legacy_payload_compatibility(self):
        """Catches loss of new identity or rejection of pre-identity payloads."""
        identified = PermissionGateResult(
            outcome=PermissionGateOutcome.ALLOW,
            action="operation.execute",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            decision_id="decision-round-trip",
        )

        assert identified.to_dict()["decision_id"] == "decision-round-trip"
        assert PermissionGateResult.from_dict(identified.to_dict()) == identified

        legacy_payload = {
            "outcome": PermissionGateOutcome.DENY,
            "action": "operation.execute",
            "domain_id": "domain:test",
            "actor_id": "actor-1",
            "session_id": "sess-1",
        }
        legacy = PermissionGateResult.from_dict(legacy_payload)
        assert legacy.decision_id is None
        assert PermissionGateResult.from_dict(legacy.to_dict()) == legacy

    def test_consumed_operation_definition_decision_has_runtime_identity(self):
        """Catches a gate result that cannot identify its own consumed decision."""
        requirement = PermissionApprovalRequirement(
            requirement_id="par-decision-identity",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="test.op-definition",
            operation_version="1.0.0",
            fingerprint="fp-decision-identity",
            scope="operation",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(requirement,),
        )
        service, request_id = _create_approval_service_and_request(requirement)
        gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)
        operation = DomainOperationDefinition(
            operation_id="test.op-definition",
            domain_id="domain:test",
            version="1.0.0",
            name="Operation definition identity test",
            description="Consumes a real approval through the definition gate.",
            operation_type=DomainOperationType.ANALYSIS,
            risk_level=PolicyRiskLevel.LOW,
            reversible=True,
        )

        consumed = gate.evaluate_operation_definition(
            operation,
            request_id="req-decision-identity",
            actor_id="actor-1",
            session_id="sess-1",
            approval_request_id=request_id,
        )

        assert consumed.outcome == PermissionGateOutcome.APPROVAL_CONSUMED
        assert consumed.decision_id


# ── 5. One-time consumption atomicity ────────────────────────────────────────


class TestOneTimeConsumption:
    def test_second_consumption_denied(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-1",
            scope="operation",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        service, request_id = _create_approval_service_and_request(par)
        gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)

        result1 = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
            approval_request_id=request_id,
            one_time=True,
        )
        assert result1.allowed

        result2 = gate.evaluate_operation(
            request_id="req-2",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
            approval_request_id=request_id,
            one_time=True,
        )
        assert result2.denied
        assert result2.outcome == PermissionGateOutcome.APPROVAL_DENIED

    def test_concurrent_consumption_only_one_wins(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-1",
            scope="operation",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        service, request_id = _create_approval_service_and_request(par)
        gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)

        results: list[PermissionGateResult] = []
        barrier = threading.Barrier(2)

        def consume():
            barrier.wait()
            r = gate.evaluate_operation(
                request_id="req-concurrent",
                domain_id="domain:test",
                actor_id="actor-1",
                session_id="sess-1",
                operation_id="op-1",
                approval_request_id=request_id,
                one_time=True,
            )
            results.append(r)

        threads = [threading.Thread(target=consume) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        granted = [r for r in results if r.allowed]
        denied = [r for r in results if r.denied]
        assert len(granted) == 1
        assert len(denied) == 1


# ── 6. Dry-run mode ─────────────────────────────────────────────────────────


class TestDryRun:
    def test_dry_run_does_not_consume(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-1",
            scope="operation",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        service, request_id = _create_approval_service_and_request(par)
        gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)

        result1 = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
            approval_request_id=request_id,
            dry_run=True,
        )
        assert result1.allowed

        # Second call still succeeds since first was dry-run
        result2 = gate.evaluate_operation(
            request_id="req-2",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
            approval_request_id=request_id,
            one_time=True,
        )
        assert result2.allowed


# ── 7. Reusable grants ──────────────────────────────────────────────────────


class TestReusableGrants:
    def test_reusable_not_consumed(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-1",
            scope="operation",
            one_time=False,
            reusable=True,
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        service, request_id = _create_approval_service_and_request(par)
        gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)

        for _ in range(3):
            result = gate.evaluate_operation(
                request_id=_id(),
                domain_id="domain:test",
                actor_id="actor-1",
                session_id="sess-1",
                operation_id="op-1",
                approval_request_id=request_id,
                one_time=False,
            )
            assert result.allowed


# ── 8. Revocation ────────────────────────────────────────────────────────────


class TestRevocation:
    def test_revoked_approval_denied(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-1",
            scope="operation",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        service, request_id = _create_approval_service_and_request(par)
        service.revoke(request_id, "admin-1", reason="security_policy")
        gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)

        result = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
            approval_request_id=request_id,
        )
        assert result.denied
        assert result.approval_evidence is not None
        assert result.approval_evidence["denial_reason"] == "revoked"


# ── 9. Expiration ────────────────────────────────────────────────────────────


class TestExpiration:
    def test_expired_approval_denied(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-1",
            scope="operation",
            expires_at=(_NOW - timedelta(hours=1)).isoformat(),
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        repo = InMemoryApprovalRepository()
        service = ApprovalService(repo)

        requirement = to_approval_requirement(par, agent_run_id="run-1")
        request = service.create_request_from_requirement(
            requirement,
            requested_by="agent-runtime",
        )
        decision = ApprovalDecision(
            id=_id(),
            request_id=request.id,
            decision=ApprovalDecisionType.APPROVE,
            actor_id="approver",
            comment="OK",
        )
        service.submit_decision(decision, now=_NOW - timedelta(hours=2))

        gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)
        result = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
            approval_request_id=request.id,
        )
        assert result.denied


# ── 10. Scope mismatch ──────────────────────────────────────────────────────


class TestScopeMismatch:
    def test_scope_mismatch_denied(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-1",
            scope="workflow",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        service, request_id = _create_approval_service_and_request(par)
        gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)
        result = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
            approval_request_id=request_id,
        )
        # Gate passes scope="operation" but requirement has scope="workflow"
        assert result.denied
        assert result.approval_evidence is None
        assert "approval_requirement_context_mismatch" in result.reasons


# ── 11. Workflow gate ────────────────────────────────────────────────────────


class TestWorkflowGate:
    def test_workflow_allow(self):
        resolver = _FakeResolver(PermissionOutcome.ALLOW)
        gate = DomainPermissionGate(resolver, clock=lambda: _NOW)
        result = gate.evaluate_workflow(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            workflow_id="wf-1",
        )
        assert result.allowed
        assert result.outcome == PermissionGateOutcome.ALLOW

    def test_workflow_deny(self):
        resolver = _FakeResolver(PermissionOutcome.DENY, reasons=("workflow_denied",))
        gate = DomainPermissionGate(resolver, clock=lambda: _NOW)
        result = gate.evaluate_workflow(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            workflow_id="wf-1",
        )
        assert result.denied


# ── 12. Cross-domain gate ───────────────────────────────────────────────────


class TestCrossDomainGate:
    def test_cross_domain_allow(self):
        resolver = _FakeResolver(PermissionOutcome.ALLOW)
        gate = DomainPermissionGate(resolver, clock=lambda: _NOW)
        result = gate.evaluate_cross_domain(
            request_id="req-1",
            source_domain="domain:a",
            target_domain="domain:b",
            actor_id="actor-1",
            session_id="sess-1",
        )
        assert result.allowed

    def test_cross_domain_deny(self):
        resolver = _FakeResolver(
            PermissionOutcome.DENY, reasons=("target_domain_not_allowed",)
        )
        gate = DomainPermissionGate(resolver, clock=lambda: _NOW)
        result = gate.evaluate_cross_domain(
            request_id="req-1",
            source_domain="domain:a",
            target_domain="domain:b",
            actor_id="actor-1",
            session_id="sess-1",
        )
        assert result.denied


# ── 13. Bridge contract conversion ──────────────────────────────────────────


class TestApprovalBridge:
    def test_single_conversion(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            resource_id="resource-1",
            resource_kind="record",
            operation_id="op-1",
            operation_version="1",
            workflow_id="workflow-1",
            workflow_version="2",
            source_domain="domain:source",
            target_domain="domain:target",
            purpose="clinical-review",
            sensitivity=SensitivityLevel.CONFIDENTIAL,
            fingerprint="fp-1",
            expires_at=(_NOW + timedelta(hours=1)).isoformat(),
            scope="operation",
            one_time=True,
            reusable=False,
            constraints={"allowed_resources": ("resource-1",), "maximum_operations": 1},
            reason_code="approval_required",
            risk="high",
        )
        ar = to_approval_requirement(par, agent_run_id="run-1", goal_id="goal-1")
        assert ar.id == "par-1"
        assert ar.source == ApprovalRequirementSource.SECURITY
        assert ar.risk_level == PolicyRiskLevel.HIGH
        assert ar.agent_run_id == "run-1"
        assert ar.goal_id == "goal-1"
        assert ar.operation_id == "op-1"
        assert ar.workflow_id == "workflow-1"
        assert ar.permission_requirement == par
        assert ar.metadata == {"source": "domain_permission"}

        service = ApprovalService(InMemoryApprovalRepository())
        request = service.create_request_from_requirement(ar)
        assert request.permission_requirement == par

    def test_batch_conversion(self):
        pars = (
            PermissionApprovalRequirement(
                requirement_id="par-1",
                action=PermissionCapability.OPERATION_EXECUTE,
                actor_id="actor-1",
                session_id="sess-1",
                domain_id="domain:test",
                fingerprint="fp-1",
            ),
            PermissionApprovalRequirement(
                requirement_id="par-2",
                action=PermissionCapability.WORKFLOW_EXECUTE,
                actor_id="actor-1",
                session_id="sess-1",
                domain_id="domain:test",
                fingerprint="fp-2",
            ),
        )
        ars = to_approval_requirements(pars)
        assert len(ars) == 2
        assert ars[0].id == "par-1"
        assert ars[1].id == "par-2"


# ── 14. ApprovalConsumptionEvidence contract ─────────────────────────────────


class TestApprovalConsumptionEvidence:
    def test_granted_evidence(self):
        evidence = ApprovalConsumptionEvidence(
            request_id="req-1",
            requirement_id="par-1",
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            action="operation.execute",
            scope="operation",
            one_time=True,
            reusable=False,
            consumed=True,
            granted=True,
        )
        assert evidence.granted
        assert evidence.consumed
        assert evidence.denial_reason is None
        d = evidence.to_dict()
        assert d["granted"] is True
        assert ApprovalConsumptionEvidence.from_mapping(d) == evidence

    def test_denied_evidence_requires_reason(self):
        with pytest.raises(InvalidApprovalContractError):
            ApprovalConsumptionEvidence(
                request_id="req-1",
                granted=False,
            )

    def test_denied_evidence_with_reason(self):
        evidence = ApprovalConsumptionEvidence(
            request_id="req-1",
            granted=False,
            denial_reason="expired",
        )
        assert not evidence.granted
        assert evidence.denial_reason == "expired"

    def test_granted_cannot_have_denial_reason(self):
        with pytest.raises(InvalidApprovalContractError):
            ApprovalConsumptionEvidence(
                request_id="req-1",
                granted=True,
                denial_reason="expired",
            )


# ── 15. External domain trust (10.15 fix) ───────────────────────────────────


class TestExternalDomainTrust:
    def test_external_domain_always_requires_approval(self):
        from cmm.domains.permission_contracts import DomainPermissionRequest
        from cmm.domains.permission_evaluator import _requires_mandatory_approval

        # Even with external_domain_trusted=True, should require approval
        request = DomainPermissionRequest(
            "req-1",
            PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
            "domain:test",
            "actor-1",
            "sess-1",
            external_domain_trusted=True,
        )
        assert _requires_mandatory_approval(request) is True

        # Without trusted flag, also requires approval
        request2 = DomainPermissionRequest(
            "req-2",
            PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
            "domain:test",
            "actor-1",
            "sess-1",
            external_domain_trusted=False,
        )
        assert _requires_mandatory_approval(request2) is True


# ── 16. No gate injected (backward compatibility) ───────────────────────────


class TestBackwardCompatibility:
    def test_gate_result_to_dict(self):
        result = PermissionGateResult(
            outcome=PermissionGateOutcome.ALLOW,
            action="operation.execute",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            reasons=("policy_allow",),
        )
        d = result.to_dict()
        assert d["outcome"] == "allow"
        assert d["action"] == "operation.execute"
        assert "policy_allow" in d["reasons"]
        assert PermissionGateResult.from_dict(d) == result

    def test_no_approval_service_returns_approval_required(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor-1",
            session_id="sess-1",
            domain_id="domain:test",
            fingerprint="fp-1",
        )
        resolver = _FakeResolver(
            PermissionOutcome.APPROVAL_REQUIRED,
            reasons=("approval_required",),
            approval_requirements=(par,),
        )
        gate = DomainPermissionGate(resolver, None, clock=lambda: _NOW)
        result = gate.evaluate_operation(
            request_id="req-1",
            domain_id="domain:test",
            actor_id="actor-1",
            session_id="sess-1",
            operation_id="op-1",
            approval_request_id="some-id",
        )
        assert result.requires_approval
        assert "no_approval_service" in result.reasons


# ── 17. validate_and_consume directly ────────────────────────────────────────


class TestValidateAndConsume:
    def test_not_found_denied(self):
        repo = InMemoryApprovalRepository()
        service = ApprovalService(repo)
        evidence = service.validate_and_consume(
            "nonexistent",
            actor_id="a",
            session_id="s",
            now=_NOW,
        )
        assert not evidence.granted
        assert evidence.denial_reason == "approval_not_found"

    def test_exact_requirement_mismatch_is_denied(self):
        approved = PermissionApprovalRequirement(
            requirement_id="par-1",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor",
            session_id="session",
            domain_id="domain:other",
            operation_id="op-1",
            fingerprint="fp-1",
            scope="operation",
        )
        service, request_id = _create_approval_service_and_request(approved)
        evidence = service.validate_and_consume(
            request_id,
            actor_id="actor",
            session_id="session",
            domain_id="domain:test",
            expected_requirement=replace(approved, domain_id="domain:test"),
            now=_NOW,
        )
        assert not evidence.granted
        assert evidence.denial_reason == "requirement_mismatch:domain_id"

    @pytest.mark.parametrize(
        "changes",
        [
            {"actor_id": "actor-2"},
            {"session_id": "session-2"},
            {"source_domain": "domain:other-source"},
            {"target_domain": "domain:other-target"},
            {"action": PermissionCapability.WORKFLOW_EXECUTE},
            {"operation_id": "op-2"},
            {"workflow_id": "workflow-2"},
            {"node_id": "node-2"},
            {"resource_id": "resource-2"},
            {"purpose": "other-purpose"},
            {"sensitivity": SensitivityLevel.SECRET},
            {"scope": "workflow"},
            {"expires_at": (_FUTURE_EXPIRY + timedelta(hours=1)).isoformat()},
            {"one_time": False, "reusable": True},
            {"constraints": {"maximum_operations": 2}},
        ],
    )
    def test_each_security_binding_field_is_validated(self, changes):
        approved = PermissionApprovalRequirement(
            requirement_id="par-security",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor",
            session_id="session",
            domain_id="domain:test",
            source_domain="domain:source",
            target_domain="domain:target",
            operation_id="op-1",
            workflow_id="workflow-1",
            resource_id="resource-1",
            resource_kind="record",
            purpose="approved-purpose",
            sensitivity=SensitivityLevel.CONFIDENTIAL,
            fingerprint="fp-security",
            expires_at=_FUTURE_EXPIRY.isoformat(),
            scope="operation",
            one_time=True,
            reusable=False,
            constraints={"maximum_operations": 1},
        )
        service, request_id = _create_approval_service_and_request(approved)
        evidence = service.validate_and_consume(
            request_id,
            actor_id="actor",
            session_id="session",
            expected_requirement=replace(approved, **changes),
            now=_NOW,
        )
        assert not evidence.granted
        assert evidence.denial_reason.startswith("requirement_mismatch:")


# ── 18. Revoke via ApprovalService ───────────────────────────────────────────


class TestRevokeService:
    def test_revoke_produces_resolution(self):
        service, request_id = _create_approval_service_and_request()
        resolution = service.revoke(request_id, "admin-1", reason="policy_change")
        assert not resolution.may_execute
        assert "approval.revoked" in resolution.reason_codes
        assert "policy_change" in resolution.reason_codes


# ── 19. Repository mark_consumed / mark_revoked ─────────────────────────────


class TestRepositoryAtomics:
    def test_mark_consumed_once(self):
        repo2 = InMemoryApprovalRepository()
        s2 = ApprovalService(repo2)
        req = ApprovalRequirement(
            id=_id(),
            source=ApprovalRequirementSource.SECURITY,
            title="T",
            description="D",
            reason_codes=("t",),
            agent_run_id="r",
        )
        ar = s2.create_request_from_requirement(req, requested_by="sys")
        assert repo2.mark_consumed(ar.id) is True
        assert repo2.mark_consumed(ar.id) is False
        assert repo2.is_consumed(ar.id) is True

    def test_batch_validation_failure_consumes_nothing(self):
        first = PermissionApprovalRequirement(
            requirement_id="batch:first",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor",
            session_id="session",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="batch:first",
            scope="operation",
        )
        second = replace(
            first, requirement_id="batch:second", fingerprint="batch:second"
        )
        repo = InMemoryApprovalRepository()
        service = ApprovalService(repo)
        first_request = service.create_request_from_requirement(
            to_approval_requirement(first)
        )
        second_request = service.create_request_from_requirement(
            to_approval_requirement(second)
        )
        service.approve(first_request.id, "reviewer")
        service.approve(second_request.id, "reviewer")
        service.revoke(second_request.id, "admin")

        evidence = service.validate_and_consume_batch(
            ((first_request.id, first), (second_request.id, second)), now=_NOW
        )

        assert any(not item.granted for item in evidence)
        assert repo.is_consumed(first_request.id) is False
        assert repo.is_consumed(second_request.id) is False

    def test_mark_revoked_once(self):
        repo = InMemoryApprovalRepository()
        s = ApprovalService(repo)
        req = ApprovalRequirement(
            id=_id(),
            source=ApprovalRequirementSource.SECURITY,
            title="T",
            description="D",
            reason_codes=("t",),
            agent_run_id="r",
        )
        ar = s.create_request_from_requirement(req, requested_by="sys")
        assert repo.mark_revoked(ar.id, "admin") is True
        assert repo.mark_revoked(ar.id, "admin") is False
        assert repo.is_revoked(ar.id) is True

    def test_service_validates_and_consumes_inside_repository_critical_section(self):
        class TrackingRepository(InMemoryApprovalRepository):
            def __init__(self):
                super().__init__()
                self.in_critical_section = False
                self.check_atomicity = False
                self.checked_calls: list[str] = []

            @contextmanager
            def critical_section(self):
                with super().critical_section():
                    self.in_critical_section = True
                    try:
                        yield
                    finally:
                        self.in_critical_section = False

            def _check(self, name):
                if self.check_atomicity:
                    assert self.in_critical_section, (
                        f"{name} ran outside critical section"
                    )
                    self.checked_calls.append(name)

            def get_request(self, request_id):
                self._check("get_request")
                return super().get_request(request_id)

            def is_revoked(self, request_id):
                self._check("is_revoked")
                return super().is_revoked(request_id)

            def is_consumed(self, request_id):
                self._check("is_consumed")
                return super().is_consumed(request_id)

            def get_resolution(self, request_id):
                self._check("get_resolution")
                return super().get_resolution(request_id)

            def mark_consumed(self, request_id, *, now=None):
                self._check("mark_consumed")
                return super().mark_consumed(request_id, now=now)

        par = PermissionApprovalRequirement(
            requirement_id="par-atomic",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor",
            session_id="session",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-atomic",
            scope="operation",
        )
        repo = TrackingRepository()
        service = ApprovalService(repo)
        requirement = to_approval_requirement(par)
        request = service.create_request_from_requirement(requirement)
        service.approve(request.id, "approver")

        repo.check_atomicity = True
        evidence = service.validate_and_consume(
            request.id,
            actor_id="actor",
            session_id="session",
            expected_requirement=par,
            now=_NOW,
        )

        assert evidence.granted
        assert repo.checked_calls == [
            "get_request",
            "is_revoked",
            "is_consumed",
            "get_resolution",
            "mark_consumed",
        ]


class TestGateOrder:
    def test_policy_reevaluation_precedes_approval_consumption(self):
        events: list[str] = []
        par = PermissionApprovalRequirement(
            requirement_id="par-order",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor",
            session_id="session",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-order",
            scope="operation",
        )

        class RecordingResolver(_FakeResolver):
            def resolve(self, request, **kwargs):
                events.append("policy_reevaluated")
                return super().resolve(request, **kwargs)

        class RecordingApprovalService(ApprovalService):
            def validate_and_consume(self, *args, **kwargs):
                events.append("approval_validated_and_consumed")
                return super().validate_and_consume(*args, **kwargs)

        repo = InMemoryApprovalRepository()
        service = RecordingApprovalService(repo)
        approval = service.create_request_from_requirement(to_approval_requirement(par))
        service.approve(approval.id, "approver")
        gate = DomainPermissionGate(
            RecordingResolver(
                PermissionOutcome.APPROVAL_REQUIRED,
                reasons=("approval_required",),
                approval_requirements=(par,),
            ),
            service,
            clock=lambda: _NOW,
        )

        result = gate.evaluate_operation(
            request_id="req-order",
            domain_id="domain:test",
            actor_id="actor",
            session_id="session",
            operation_id="op-1",
            approval_request_id=approval.id,
        )

        assert result.allowed
        assert events == ["policy_reevaluated", "approval_validated_and_consumed"]

    def test_denial_from_latest_policy_does_not_consume_approval(self):
        par = PermissionApprovalRequirement(
            requirement_id="par-deny",
            action=PermissionCapability.OPERATION_EXECUTE,
            actor_id="actor",
            session_id="session",
            domain_id="domain:test",
            operation_id="op-1",
            fingerprint="fp-deny",
            scope="operation",
        )
        service, approval_id = _create_approval_service_and_request(par)
        gate = DomainPermissionGate(
            _FakeResolver(PermissionOutcome.DENY, reasons=("policy_changed",)),
            service,
            clock=lambda: _NOW,
        )

        result = gate.evaluate_operation(
            request_id="req-deny",
            domain_id="domain:test",
            actor_id="actor",
            session_id="session",
            operation_id="op-1",
            approval_request_id=approval_id,
        )

        assert result.denied
        assert service.repository.is_consumed(approval_id) is False


def test_domain_operation_status_reuses_existing_blocked_and_waiting_states():
    assert not hasattr(DomainOperationStatus, "PERMISSION_DENIED")
    assert not hasattr(DomainOperationStatus, "PENDING_APPROVAL")


def test_permission_gate_result_to_authority_reference_dict():
    gate_result = PermissionGateResult(
        decision_id="permission-gate-decision-123",
        outcome=PermissionGateOutcome.APPROVAL_CONSUMED,
        action="operation.execute",
        domain_id="domain:project",
        actor_id="actor-1",
        session_id="sess-1",
        approval_evidence={
            "items": [
                {
                    "requirement_id": "req:file-modify",
                    "action": "file.modify",
                    "request_id": "apr-file",
                    "approval_decision_ids": ["dec-file-1"],
                },
                {
                    "requirement_id": "req:op-exec",
                    "action": "operation.execute",
                    "request_id": "apr-op",
                    "approval_decision_ids": ["dec-op-1"],
                },
            ]
        },
    )

    authority = gate_result.to_authority_reference_dict()
    assert authority["permission_decision_id"] == "permission-gate-decision-123"
    assert authority["outcome"] == PermissionGateOutcome.APPROVAL_CONSUMED
    assert len(authority["approvals"]) == 2

    actions = [item["action"] for item in authority["approvals"]]
    assert actions == [
        PermissionCapability.FILE_MODIFY.value,
        PermissionCapability.OPERATION_EXECUTE.value,
    ]

    file_item = authority["approvals"][0]
    assert file_item["requirement_id"] == "req:file-modify"
    assert file_item["approval_request_id"] == "apr-file"
    assert file_item["approval_decision_ids"] == ["dec-file-1"]

    op_item = authority["approvals"][1]
    assert op_item["requirement_id"] == "req:op-exec"
    assert op_item["approval_request_id"] == "apr-op"
    assert op_item["approval_decision_ids"] == ["dec-op-1"]

    # Verify no sensitive payload fields are present
    for item in authority["approvals"]:
        for forbidden in (
            "comment",
            "modified_parameters",
            "reasoning",
            "full_request",
        ):
            assert forbidden not in item


def test_orchestrator_execute_preserves_permission_authority_on_success(tmp_path):
    from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.domains.operation_contracts import (
        DomainOperationRequest,
        DomainOperationResult,
    )
    from cmm.domains.operation_execution import (
        DefaultDomainOperationOrchestrator,
        DomainOperationExecutionDelegate,
    )
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver
    from cmm.domains.project.operations import build_project_operation_definitions
    from cmm.domains.project.permissions import build_project_permission_policy
    from cmm.domains.validation_integration import (
        resolve_domain_operation_validation_requirements,
    )

    # Real canonical validation runs against this minimal valid project root.
    validation_root = tmp_path / "validation-root"
    validation_root.mkdir(parents=True, exist_ok=True)
    (validation_root / "main.py").write_text("x = 1\n", encoding="utf-8")

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    definition = ops["project.modify_code"]

    class Implementation:
        def __init__(self) -> None:
            self.definition = definition
            # Host authority: the implementation declares the tree it
            # mutates; the orchestrator validates that tree.
            self.host_project_root = str(validation_root)

        def execute(self, request: Any) -> dict[str, object]:
            return {"success": True, "output": {"status": "ok"}}

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, Implementation())

    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_project_permission_policy())
    resolver = DomainPermissionResolver(perm_registry)
    service = ApprovalService(InMemoryApprovalRepository())

    proto_request = DomainOperationRequest(
        request_id="req:exec:1",
        operation_id="project.modify_code",
        operation_version="1.0.0",
        inputs={},
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        session_id="sess-1",
        primary_domain_id="domain:project",
        idempotency_key="idem-1",
        granted_permissions=definition.required_permissions,
        available_resources=definition.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor-1"},
    )

    decision = evaluate_domain_operation(
        definition,
        resolver,
        request_id=proto_request.request_id,
        actor_id="actor-1",
        session_id="sess-1",
    )
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED

    approval_request_ids = {}
    op_exec_approval_id = None
    for req in decision.approval_requirements:
        bridged = to_approval_requirement(req, agent_run_id="run-1")
        app_req = service.create_request_from_requirement(
            bridged,
            requested_by="agent:dev",
            metadata_override={
                "domain_request_fingerprint": proto_request.calculate_fingerprint(),
            },
        )
        service.approve(app_req.id, actor_id="lead")
        approval_request_ids[req.requirement_id] = app_req.id
        if req.action is PermissionCapability.OPERATION_EXECUTE:
            op_exec_approval_id = app_req.id

    class Boundary:
        id = "transaction:1"

    class TransactionManagerSpy:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def start_transaction(self, **kwargs: object):
            self.calls.append("start")
            return Boundary(), "checkpoint:1"

        def register_operation(self, **kwargs: object) -> None:
            self.calls.append("register")

        def commit(self, transaction_id: str) -> None:
            self.calls.append("commit")

        def mark_rollback_started(self, transaction_id: str) -> None:
            self.calls.append("rollback_started")

        def mark_rolled_back(self, transaction_id: str) -> None:
            self.calls.append("rolled_back")

        def mark_failed(self, transaction_id: str) -> None:
            self.calls.append("failed")

    class RollbackSpy:
        def __init__(self, succeeds: bool = True) -> None:
            self.succeeds = succeeds
            self.calls = 0

        def rollback(self, transaction_id: str, checkpoint_id: str | None) -> bool:
            self.calls += 1
            return self.succeeds

    from cmm.agent_runtime.validation_execution_adapter import (
        AgentValidationAdapter,
    )

    gate = DomainPermissionGate(resolver, service, clock=lambda: _NOW)
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
        validation_adapter=AgentValidationAdapter(),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        approval_service=service,
        permission_gate=gate,
        transaction_manager=TransactionManagerSpy(),
        rollback_executor=RollbackSpy(),
        operation_validation_provider=resolve_domain_operation_validation_requirements,
    )

    op_req = DomainOperationRequest(
        request_id=proto_request.request_id,
        operation_id=proto_request.operation_id,
        operation_version=proto_request.operation_version,
        inputs=proto_request.inputs,
        agent_run_id=proto_request.agent_run_id,
        workflow_id=proto_request.workflow_id,
        task_id=proto_request.task_id,
        session_id=proto_request.session_id,
        primary_domain_id=proto_request.primary_domain_id,
        idempotency_key=proto_request.idempotency_key,
        granted_permissions=proto_request.granted_permissions,
        available_resources=proto_request.available_resources,
        capabilities=proto_request.capabilities,
        approval_request_id=op_exec_approval_id,
        metadata={
            "actor_id": "actor-1",
            "approval_request_ids": approval_request_ids,
            "validation_project_root": str(validation_root),
        },
    )

    res = orchestrator.execute(op_req)
    assert res.status is DomainOperationStatus.COMPLETED
    assert "permission_authority" in res.metadata

    authority = res.metadata["permission_authority"]
    assert authority["permission_decision_id"].startswith("permission-gate-decision-")
    assert authority["outcome"] == "approval_consumed"
    assert len(authority["approvals"]) == 2

    # Verify decision IDs match repo
    dec_ids = {
        item["approval_request_id"]: item["approval_decision_ids"]
        for item in authority["approvals"]
    }
    for app_id in approval_request_ids.values():
        repo_decs = [d.id for d in service.repository.list_decisions(app_id)]
        assert list(dec_ids[app_id]) == repo_decs

    # Verify DomainOperationResult roundtrip serialization preserves permission_authority
    serialized = res.to_dict()
    assert (
        serialized["metadata"]["permission_authority"]["permission_decision_id"]
        == authority["permission_decision_id"]
    )
    assert (
        serialized["metadata"]["permission_authority"]["outcome"]
        == authority["outcome"]
    )
    deserialized = DomainOperationResult.from_dict(serialized)
    assert deserialized.metadata["permission_authority"] == authority
