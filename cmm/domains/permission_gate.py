"""Phase 10.15 – Domain Permission Gate.

Mandatory gate that must be evaluated BEFORE executing any domain operation
or workflow. The gate:

1. Evaluates the current permission resolution via DomainPermissionResolver
2. Re-verifies policies (never caches stale decisions)
3. On APPROVAL_REQUIRED → locates and validates/consumes the approval
4. On DENY → blocks execution with structured evidence
5. On ALLOW → permits execution with constraint evidence

The gate never executes the operation itself — it only produces
authorization evidence that the orchestrator uses to decide.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from cmm.agent_runtime.domain_permission_contracts import (
    EffectivePermissionResult,
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.permission_adapters import (
    evaluate_domain_operation,
    evaluate_domain_workflow,
    evaluate_domain_workflow_node,
)
from cmm.domains.permission_contracts import (
    DomainPermissionRequest,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class PermissionGateOutcome:
    """Enumeration of gate outcomes."""

    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_CONSUMED = "approval_consumed"
    APPROVAL_DENIED = "approval_denied"


class PermissionGateReason(str, Enum):
    GATE_UNAVAILABLE = "permission.gate_unavailable"
    APPROVAL_MISSING = "approval.missing"
    APPROVAL_EXPIRED = "approval.expired"
    APPROVAL_REVOKED = "approval.revoked"
    APPROVAL_CONSUMED = "approval.consumed"
    APPROVAL_SCOPE_INCORRECT = "approval.scope_incorrect"
    POLICY_DENIED = "permission.policy_denied"
    BINDING_FAILURE = "approval.binding_failure"


def _typed_denial_reason(reason: str | None) -> str:
    if reason in {"expired"}:
        return PermissionGateReason.APPROVAL_EXPIRED.value
    if reason in {"revoked"}:
        return PermissionGateReason.APPROVAL_REVOKED.value
    if reason in {"already_consumed"}:
        return PermissionGateReason.APPROVAL_CONSUMED.value
    if reason in {"approval_not_found", "not_satisfied", "not_executable"}:
        return PermissionGateReason.APPROVAL_MISSING.value
    if reason == "scope_mismatch" or (reason or "").endswith(":scope"):
        return PermissionGateReason.APPROVAL_SCOPE_INCORRECT.value
    return PermissionGateReason.BINDING_FAILURE.value


@dataclass(frozen=True, slots=True)
class PermissionGateResult:
    """Structured result from a permission gate evaluation.

    This is the single contract that orchestrators use to decide
    whether to proceed with execution.
    """

    outcome: str
    action: str
    domain_id: str
    actor_id: str
    session_id: str
    reasons: tuple[str, ...] = ()
    effective_constraints: Mapping[str, Any] = field(default_factory=dict)
    approval_evidence: Mapping[str, Any] | None = None
    approval_requirements: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.outcome in (PermissionGateOutcome.ALLOW, PermissionGateOutcome.APPROVAL_CONSUMED)

    @property
    def denied(self) -> bool:
        return self.outcome in (PermissionGateOutcome.DENY, PermissionGateOutcome.APPROVAL_DENIED)

    @property
    def requires_approval(self) -> bool:
        return self.outcome == PermissionGateOutcome.APPROVAL_REQUIRED

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "action": self.action,
            "domain_id": self.domain_id,
            "actor_id": self.actor_id,
            "session_id": self.session_id,
            "reasons": list(self.reasons),
            "effective_constraints": dict(self.effective_constraints),
            "approval_evidence": dict(self.approval_evidence) if self.approval_evidence else None,
            "approval_requirements": [dict(r) for r in self.approval_requirements],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PermissionGateResult:
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown PermissionGateResult fields: {sorted(unknown)}")
        values = dict(data)
        values["reasons"] = tuple(values.get("reasons", ()))
        values["approval_requirements"] = tuple(
            values.get("approval_requirements", ())
        )
        return cls(**values)

    def to_trace_dict(self) -> dict[str, Any]:
        """Return redacted gate evidence suitable for logs and operation traces."""
        denial_reason = None
        if self.approval_evidence:
            denial_reason = self.approval_evidence.get("denial_reason")
            if denial_reason is None:
                items = self.approval_evidence.get("items", ())
                denial_reason = next(
                    (item.get("denial_reason") for item in items if item.get("denial_reason")),
                    None,
                )
        return {
            "outcome": self.outcome,
            "action": self.action,
            "reasons": list(self.reasons),
            "approval_requirement_count": len(self.approval_requirements),
            "approval_denial_reason": _typed_denial_reason(denial_reason)
            if denial_reason
            else None,
        }


@runtime_checkable
class PermissionResolverProtocol(Protocol):
    """Minimal protocol for a DomainPermissionResolver."""

    def resolve(self, request: DomainPermissionRequest, **kwargs: Any) -> Any:
        ...


@runtime_checkable
class ApprovalServiceProtocol(Protocol):
    """Minimal protocol for the canonical ApprovalService."""

    def validate_and_consume(
        self,
        request_id: str,
        *,
        actor_id: str,
        session_id: str,
        action: str,
        domain_id: str,
        target_domain: str | None,
        scope: str,
        one_time: bool,
        requirement_id: str | None,
        expected_requirement: PermissionApprovalRequirement | None,
        dry_run: bool,
        now: datetime | None,
        **kwargs: Any,
    ) -> Any:
        ...


class DomainPermissionGate:
    """Mandatory pre-execution gate for domain operations and workflows.

    Usage:
        gate = DomainPermissionGate(resolver, approval_service)
        result = gate.evaluate_operation(...)
        if not result.allowed:
            # block execution
    """

    def __init__(
        self,
        resolver: PermissionResolverProtocol,
        approval_service: ApprovalServiceProtocol | None = None,
        *,
        clock: Any | None = None,
    ) -> None:
        self._resolver = resolver
        self._approval_service = approval_service
        self._clock = clock or _now_utc

    def evaluate_operation(
        self,
        *,
        request_id: str,
        domain_id: str,
        actor_id: str,
        session_id: str,
        operation_id: str,
        operation_version: str | None = None,
        approval_request_id: str | None = None,
        one_time: bool = True,
        dry_run: bool = False,
    ) -> PermissionGateResult:
        """Evaluate the permission gate for a domain operation.

        Returns a PermissionGateResult indicating whether execution may proceed.
        """
        perm_request = DomainPermissionRequest(
            request_id,
            PermissionCapability.OPERATION_EXECUTE,
            domain_id,
            actor_id,
            session_id,
            operation_id=operation_id,
            operation_version=operation_version,
        )
        now = self._clock()
        resolution = self._resolver.resolve(perm_request, now=now)
        effective = resolution.effective_permissions

        return self._evaluate_resolution(
            effective=effective,
            action=PermissionCapability.OPERATION_EXECUTE.value,
            domain_id=domain_id,
            actor_id=actor_id,
            session_id=session_id,
            scope="operation",
            approval_request_id=approval_request_id,
            dry_run=dry_run,
            now=now,
            metadata={
                "operation_id": operation_id,
                "operation_version": operation_version,
                "legacy_one_time_hint_ignored": one_time,
            },
        )

    def evaluate_operation_definition(
        self,
        definition: DomainOperationDefinition,
        *,
        request_id: str,
        actor_id: str,
        session_id: str,
        approval_request_id: str | None = None,
        approval_request_ids: Mapping[str, str] | None = None,
        dry_run: bool = False,
    ) -> PermissionGateResult:
        """Reevaluate every declared operation requirement immediately pre-dispatch."""
        now = self._clock()
        decision = evaluate_domain_operation(
            definition,
            self._resolver,  # type: ignore[arg-type]
            request_id=request_id,
            actor_id=actor_id,
            session_id=session_id,
            now=now,
        )
        metadata = {
            "operation_id": definition.operation_id,
            "operation_version": definition.version,
        }
        if decision.decision is PermissionOutcome.DENY:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.DENY,
                action=PermissionCapability.OPERATION_EXECUTE.value,
                domain_id=definition.domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=decision.reasons,
                effective_constraints=decision.effective_constraints,
                metadata=metadata,
            )
        if decision.decision is PermissionOutcome.ALLOW:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.ALLOW,
                action=PermissionCapability.OPERATION_EXECUTE.value,
                domain_id=definition.domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=decision.reasons,
                effective_constraints=decision.effective_constraints,
                metadata=metadata,
            )
        return self._validate_requirements(
            requirements=decision.approval_requirements,
            aggregate_action=PermissionCapability.OPERATION_EXECUTE.value,
            domain_id=definition.domain_id,
            actor_id=actor_id,
            session_id=session_id,
            approval_request_id=approval_request_id,
            approval_request_ids=approval_request_ids,
            dry_run=dry_run,
            now=now,
            reasons=decision.reasons,
            effective_constraints=decision.effective_constraints,
            metadata=metadata,
        )

    def _validate_requirements(
        self,
        *,
        requirements: tuple[PermissionApprovalRequirement, ...],
        aggregate_action: str,
        domain_id: str,
        actor_id: str,
        session_id: str,
        approval_request_id: str | None,
        approval_request_ids: Mapping[str, str] | None,
        dry_run: bool,
        now: datetime,
        reasons: tuple[str, ...],
        effective_constraints: Mapping[str, Any],
        metadata: dict[str, Any],
    ) -> PermissionGateResult:
        serialized = tuple(item.to_dict() for item in requirements)
        references = dict(approval_request_ids or {})
        if approval_request_id is not None and len(requirements) == 1:
            references.setdefault(requirements[0].requirement_id, approval_request_id)
        if not requirements or any(
            item.requirement_id not in references for item in requirements
        ):
            return PermissionGateResult(
                outcome=PermissionGateOutcome.APPROVAL_REQUIRED,
                action=aggregate_action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=(*reasons, "approval_required"),
                effective_constraints=effective_constraints,
                approval_requirements=serialized,
                metadata=metadata,
            )
        if self._approval_service is None:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.APPROVAL_REQUIRED,
                action=aggregate_action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=(*reasons, "no_approval_service"),
                effective_constraints=effective_constraints,
                approval_requirements=serialized,
                metadata=metadata,
            )
        for requirement in requirements:
            if (
                requirement.actor_id != actor_id
                or requirement.session_id != session_id
                or requirement.domain_id != domain_id
            ):
                return PermissionGateResult(
                    outcome=PermissionGateOutcome.DENY,
                    action=aggregate_action,
                    domain_id=domain_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    reasons=(*reasons, "approval_requirement_context_mismatch"),
                    effective_constraints=effective_constraints,
                    approval_requirements=serialized,
                    metadata=metadata,
                )
        batch = tuple(
            (references[item.requirement_id], item) for item in requirements
        )
        validate_batch = getattr(
            self._approval_service, "validate_and_consume_batch", None
        )
        if validate_batch is None:
            if len(batch) != 1:
                return PermissionGateResult(
                    outcome=PermissionGateOutcome.APPROVAL_REQUIRED,
                    action=aggregate_action,
                    domain_id=domain_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    reasons=(*reasons, "atomic_batch_validation_unavailable"),
                    effective_constraints=effective_constraints,
                    approval_requirements=serialized,
                    metadata=metadata,
                )
            request_reference, requirement = batch[0]
            evidences = (
                self._approval_service.validate_and_consume(
                    request_reference,
                    actor_id=requirement.actor_id,
                    session_id=requirement.session_id,
                    action=requirement.action.value,
                    domain_id=requirement.domain_id,
                    target_domain=requirement.target_domain,
                    scope=requirement.scope,
                    one_time=requirement.one_time,
                    requirement_id=requirement.requirement_id,
                    expected_requirement=requirement,
                    dry_run=dry_run,
                    now=now,
                ),
            )
        else:
            evidences = validate_batch(batch, dry_run=dry_run, now=now)
        denied = next((item for item in evidences if not item.granted), None)
        if denied is not None:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.APPROVAL_DENIED,
                action=aggregate_action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=(
                    *reasons,
                    _typed_denial_reason(denied.denial_reason),
                ),
                effective_constraints=effective_constraints,
                approval_evidence={"items": [item.to_dict() for item in evidences]},
                approval_requirements=serialized,
                metadata=metadata,
            )
        return PermissionGateResult(
            outcome=PermissionGateOutcome.APPROVAL_CONSUMED,
            action=aggregate_action,
            domain_id=domain_id,
            actor_id=actor_id,
            session_id=session_id,
            reasons=(*reasons, "approval_consumed"),
            effective_constraints=effective_constraints,
            approval_evidence={"items": [item.to_dict() for item in evidences]},
            metadata=metadata,
        )

    def evaluate_workflow(
        self,
        *,
        request_id: str,
        domain_id: str,
        actor_id: str,
        session_id: str,
        workflow_id: str,
        workflow_version: str | None = None,
        supporting_domains: tuple[str, ...] = (),
        approval_request_id: str | None = None,
        one_time: bool = True,
        dry_run: bool = False,
    ) -> PermissionGateResult:
        """Evaluate the permission gate for a domain workflow."""
        perm_request = DomainPermissionRequest(
            request_id,
            PermissionCapability.WORKFLOW_EXECUTE,
            domain_id,
            actor_id,
            session_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
        )
        now = self._clock()
        resolution = self._resolver.resolve(
            perm_request,
            supporting_domains=supporting_domains,
            now=now,
        )
        effective = resolution.effective_permissions

        return self._evaluate_resolution(
            effective=effective,
            action=PermissionCapability.WORKFLOW_EXECUTE.value,
            domain_id=domain_id,
            actor_id=actor_id,
            session_id=session_id,
            scope="workflow",
            approval_request_id=approval_request_id,
            dry_run=dry_run,
            now=now,
            metadata={
                "workflow_id": workflow_id,
                "workflow_version": workflow_version,
                "legacy_one_time_hint_ignored": one_time,
            },
        )

    def evaluate_workflow_definition(
        self,
        definition: DomainWorkflowDefinition,
        *,
        request_id: str,
        actor_id: str,
        session_id: str,
        operations: Mapping[tuple[str, str | None], DomainOperationDefinition] | None = None,
        workflows: Mapping[tuple[str, str | None], DomainWorkflowDefinition] | None = None,
        approval_request_id: str | None = None,
        approval_request_ids: Mapping[str, str] | None = None,
        dry_run: bool = False,
    ) -> PermissionGateResult:
        """Preflight global and mandatory workflow policy without consuming node grants."""
        now = self._clock()
        decision = evaluate_domain_workflow(
            definition,
            self._resolver,  # type: ignore[arg-type]
            request_id=request_id,
            actor_id=actor_id,
            session_id=session_id,
            operations=operations,
            workflows=workflows,
            now=now,
        )
        metadata = {
            "workflow_id": definition.workflow_id,
            "workflow_version": definition.version,
            "approval_nodes": decision.approval_nodes,
            "blocked_nodes": decision.blocked_nodes,
        }
        if decision.decision is PermissionOutcome.DENY:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.DENY,
                action=PermissionCapability.WORKFLOW_EXECUTE.value,
                domain_id=definition.domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=("policy_currently_denied",),
                effective_constraints=decision.effective_constraints,
                metadata=metadata,
            )
        node_requirement_ids = {
            requirement.requirement_id
            for node in decision.node_decisions
            for requirement in node.approval_requirements
        }
        start_requirements = tuple(
            item
            for item in decision.approval_requirements
            if item.requirement_id not in node_requirement_ids
        )
        if not start_requirements:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.ALLOW,
                action=PermissionCapability.WORKFLOW_EXECUTE.value,
                domain_id=definition.domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=decision.decision.value,
                effective_constraints=decision.effective_constraints,
                metadata=metadata,
            )
        return self._validate_requirements(
            requirements=start_requirements,
            aggregate_action=PermissionCapability.WORKFLOW_EXECUTE.value,
            domain_id=definition.domain_id,
            actor_id=actor_id,
            session_id=session_id,
            approval_request_id=approval_request_id,
            approval_request_ids=approval_request_ids,
            dry_run=dry_run,
            now=now,
            reasons=(),
            effective_constraints=decision.effective_constraints,
            metadata=metadata,
        )

    def evaluate_workflow_node(
        self,
        node: WorkflowNode,
        definition: DomainWorkflowDefinition,
        *,
        request_id: str,
        actor_id: str,
        session_id: str,
        operations: Mapping[tuple[str, str | None], DomainOperationDefinition] | None = None,
        workflows: Mapping[tuple[str, str | None], DomainWorkflowDefinition] | None = None,
        approval_request_ids: Mapping[str, str] | None = None,
        dry_run: bool = False,
    ) -> PermissionGateResult:
        now = self._clock()
        decision = evaluate_domain_workflow_node(
            node,
            definition,
            self._resolver,  # type: ignore[arg-type]
            request_id=request_id,
            actor_id=actor_id,
            session_id=session_id,
            operations=operations,
            workflows=workflows,
            now=now,
        )
        metadata = {"workflow_id": definition.workflow_id, "node_id": node.node_id}
        if decision.decision is PermissionOutcome.DENY:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.DENY,
                action=PermissionCapability.WORKFLOW_EXECUTE.value,
                domain_id=definition.domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=decision.reasons,
                effective_constraints=decision.effective_constraints,
                metadata=metadata,
            )
        if decision.decision is PermissionOutcome.ALLOW:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.ALLOW,
                action=PermissionCapability.WORKFLOW_EXECUTE.value,
                domain_id=definition.domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=decision.reasons,
                effective_constraints=decision.effective_constraints,
                metadata=metadata,
            )
        return self._validate_requirements(
            requirements=decision.approval_requirements,
            aggregate_action=PermissionCapability.WORKFLOW_EXECUTE.value,
            domain_id=definition.domain_id,
            actor_id=actor_id,
            session_id=session_id,
            approval_request_id=None,
            approval_request_ids=approval_request_ids,
            dry_run=dry_run,
            now=now,
            reasons=decision.reasons,
            effective_constraints=decision.effective_constraints,
            metadata=metadata,
        )

    def evaluate_cross_domain(
        self,
        *,
        request_id: str,
        source_domain: str,
        target_domain: str,
        actor_id: str,
        session_id: str,
        approval_request_id: str | None = None,
        one_time: bool = True,
        dry_run: bool = False,
    ) -> PermissionGateResult:
        """Evaluate cross-domain access permission."""
        perm_request = DomainPermissionRequest(
            request_id,
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            source_domain,
            actor_id,
            session_id,
            source_domain=source_domain,
            target_domain=target_domain,
        )
        now = self._clock()
        resolution = self._resolver.resolve(perm_request, now=now)
        effective = resolution.effective_permissions

        return self._evaluate_resolution(
            effective=effective,
            action=PermissionCapability.DOMAIN_CROSS_ACCESS.value,
            domain_id=source_domain,
            actor_id=actor_id,
            session_id=session_id,
            scope="cross_domain",
            approval_request_id=approval_request_id,
            dry_run=dry_run,
            now=now,
            metadata={
                "source_domain": source_domain,
                "target_domain": target_domain,
                "legacy_one_time_hint_ignored": one_time,
            },
        )

    def _evaluate_resolution(
        self,
        *,
        effective: EffectivePermissionResult,
        action: str,
        domain_id: str,
        actor_id: str,
        session_id: str,
        scope: str,
        approval_request_id: str | None,
        dry_run: bool,
        now: datetime,
        metadata: dict[str, Any],
    ) -> PermissionGateResult:
        """Core resolution evaluator shared by operation/workflow/cross-domain."""
        if effective.decision is PermissionOutcome.DENY:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.DENY,
                action=action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=(*effective.reasons, PermissionGateReason.POLICY_DENIED.value),
                effective_constraints=dict(effective.effective_constraints),
                metadata=metadata,
            )

        if effective.decision is PermissionOutcome.ALLOW:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.ALLOW,
                action=action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=effective.reasons,
                effective_constraints=dict(effective.effective_constraints),
                metadata=metadata,
            )

        # APPROVAL_REQUIRED
        approval_reqs = tuple(r.to_dict() for r in effective.approval_requirements)

        if not approval_request_id:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.APPROVAL_REQUIRED,
                action=action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=(
                    *effective.reasons,
                    "approval_required",
                    PermissionGateReason.APPROVAL_MISSING.value,
                ),
                effective_constraints=dict(effective.effective_constraints),
                approval_requirements=approval_reqs,
                metadata=metadata,
            )

        if self._approval_service is None:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.APPROVAL_REQUIRED,
                action=action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=(*effective.reasons, "no_approval_service"),
                effective_constraints=dict(effective.effective_constraints),
                approval_requirements=approval_reqs,
                metadata=metadata,
            )

        if len(effective.approval_requirements) != 1:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.APPROVAL_REQUIRED,
                action=action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=(*effective.reasons, "exactly_one_approval_requirement_required"),
                effective_constraints=dict(effective.effective_constraints),
                approval_requirements=approval_reqs,
                metadata=metadata,
            )

        requirement = effective.approval_requirements[0]
        expected_operation = metadata.get("operation_id")
        expected_workflow = metadata.get("workflow_id")
        target_domain = metadata.get("target_domain")
        exact_context = (
            requirement.action.value == action
            and requirement.actor_id == actor_id
            and requirement.session_id == session_id
            and requirement.domain_id == domain_id
            and requirement.scope == scope
            and requirement.target_domain == target_domain
            and (
                expected_operation is None
                or requirement.operation_id == expected_operation
            )
            and (
                expected_workflow is None
                or requirement.workflow_id == expected_workflow
            )
        )
        if not exact_context:
            typed_reason = (
                PermissionGateReason.APPROVAL_SCOPE_INCORRECT.value
                if requirement.scope != scope
                else PermissionGateReason.BINDING_FAILURE.value
            )
            return PermissionGateResult(
                outcome=PermissionGateOutcome.DENY,
                action=action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=(
                    *effective.reasons,
                    "approval_requirement_context_mismatch",
                    typed_reason,
                ),
                effective_constraints=dict(effective.effective_constraints),
                approval_requirements=approval_reqs,
                metadata=metadata,
            )

        evidence = self._approval_service.validate_and_consume(
            approval_request_id,
            actor_id=actor_id,
            session_id=session_id,
            action=action,
            domain_id=domain_id,
            target_domain=target_domain,
            scope=scope,
            one_time=requirement.one_time,
            requirement_id=requirement.requirement_id,
            expected_requirement=requirement,
            dry_run=dry_run,
            now=now,
        )

        if evidence.granted:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.APPROVAL_CONSUMED,
                action=action,
                domain_id=domain_id,
                actor_id=actor_id,
                session_id=session_id,
                reasons=(*effective.reasons, "approval_consumed"),
                effective_constraints=dict(effective.effective_constraints),
                approval_evidence=evidence.to_dict(),
                metadata=metadata,
            )

        return PermissionGateResult(
            outcome=PermissionGateOutcome.APPROVAL_DENIED,
            action=action,
            domain_id=domain_id,
            actor_id=actor_id,
            session_id=session_id,
            reasons=(
                *effective.reasons,
                evidence.denial_reason or "approval_invalid",
                _typed_denial_reason(evidence.denial_reason),
            ),
            effective_constraints=dict(effective.effective_constraints),
            approval_evidence=evidence.to_dict(),
            approval_requirements=approval_reqs,
            metadata=metadata,
        )


__all__ = [
    "DomainPermissionGate",
    "PermissionGateOutcome",
    "PermissionGateReason",
    "PermissionGateResult",
]
