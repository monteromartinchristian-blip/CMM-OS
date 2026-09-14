"""Thin Domain → Agent Runtime integration boundary.

Phase 10.41 coordination only.  All stateful owners (resolver, composer,
profile resolver, permission resolver/gate, cognitive integrator, Agent
Runtime service, Action Budget service) are received by dependency
injection; this boundary owns no runtime, store, registry, or state
machine.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
)
from cmm.agent_runtime.agent_runtime_integration_enums import (
    IntegrationExecutionState,
)
from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.agent_runtime.enums import BudgetResourceType
from cmm.agent_runtime.errors import ControlledOperationExecutionError
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.domains.agent_runtime_integration_contracts import (
    DomainAgentRuntimeDecision,
    DomainAgentRuntimeDecisionCode,
    DomainAgentRuntimeIntegrationRequest,
    DomainAgentRuntimeIntegrationResult,
)
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
)
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainOperationStatus, DomainResolutionStatus
from cmm.domains.errors import (
    DomainAgentRuntimeIntegrationBlockedError,
    DomainAgentRuntimeIntegrationContractError,
    DomainError,
)
from cmm.domains.operation_contracts import DomainOperationRequest
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.profile_contracts import ResolvedDomainProfile
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.validation_integration import (
    derive_host_project_change_impact,
    is_project_domain_code_mutation,
)

PROJECTION_NAMESPACE = "domain_intelligence"

# Phase 9 terminal states that count as a successfully completed delegation.
_TERMINAL_SUCCESS_STATES = frozenset(
    {
        IntegrationExecutionState.COMPLETED,
        IntegrationExecutionState.PARTIALLY_COMPLETED,
    }
)

# Domain policy booleans that may only narrow canonical Agent permission
# context booleans (AND semantics; a Domain True never widens the Agent).
_AGENT_BOOLEAN_BY_POLICY_ATTR: tuple[tuple[str, str], ...] = (
    ("allow_memory_write", "allow_memory_write"),
    ("allow_external_models", "allow_external_models"),
    ("allow_external_communication", "allow_communications"),
    ("allow_external_search", "allow_external_access"),
)
# Capability prohibitions that force the matching Agent boolean to False.
_CAPABILITY_BOOLEAN_PROHIBITIONS: tuple[tuple[PermissionCapability, str], ...] = (
    (PermissionCapability.MEMORY_WRITE, "allow_memory_write"),
    (PermissionCapability.MODEL_EXTERNAL, "allow_external_models"),
    (PermissionCapability.COMMUNICATION_EXTERNAL, "allow_communications"),
    (PermissionCapability.PUBLICATION, "allow_publication"),
    (PermissionCapability.SEARCH_EXTERNAL, "allow_external_access"),
    (PermissionCapability.FILE_MODIFY, "allow_destructive_actions"),
)

# Canonical Phase 9 BudgetResourceType dimensions mappable from a
# DomainActionBudget ceiling.  Unmapped Domain dimensions are enforced only
# through canonical runtime evidence; Phase 10.41 owns no consumption ledger.
_DOMAIN_BUDGET_ATTR_BY_RESOURCE: tuple[tuple[BudgetResourceType, str], ...] = (
    (BudgetResourceType.OPERATION, "maximum_operations"),
    (BudgetResourceType.ITERATION, "maximum_iterations"),
    (BudgetResourceType.QUESTION, "maximum_questions"),
    (BudgetResourceType.EXTERNAL_CALL, "maximum_external_calls"),
    (BudgetResourceType.DURATION_SECONDS, "maximum_duration_seconds"),
    (BudgetResourceType.COST, "maximum_cost"),
)


@runtime_checkable
class DomainAgentRuntimeIntegrator(Protocol):
    """Protocol for the Domain-owned Agent Runtime integration boundary."""

    def run(
        self,
        request: DomainAgentRuntimeIntegrationRequest,
    ) -> DomainAgentRuntimeIntegrationResult: ...

    execute = run


def _require_dependency(dependency: object, name: str, method: str) -> None:
    if dependency is None or not callable(getattr(dependency, method, None)):
        raise DomainAgentRuntimeIntegrationContractError(
            f"{name} must provide a callable {method}(...) method",
            field=name,
        )


class DomainOperationDispatchAdapter:
    """Project a Phase 9 operation into the canonical Domain orchestrator.

    ``AgentRuntimeIntegrationService`` retains the lifecycle and calls its
    normal ``AgentExecutionAdapter`` once per operation.  This callable is
    installed at that adapter's generic delegate seam; it performs only the
    contract projection needed to enter ``DefaultDomainOperationOrchestrator``.
    """

    def __init__(self, orchestrator: object) -> None:
        _require_dependency(orchestrator, "orchestrator", "execute")
        self._orchestrator = orchestrator

    @staticmethod
    def _strings(value: object, field: str) -> tuple[str, ...]:
        if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
            raise ControlledOperationExecutionError(
                code="DOMAIN_OPERATION_CONTEXT_INVALID",
                message="Domain operation dispatch context is invalid",
                details={"field": field},
            )
        values = tuple(value)
        if any(not isinstance(item, str) or not item.strip() for item in values):
            raise ControlledOperationExecutionError(
                code="DOMAIN_OPERATION_CONTEXT_INVALID",
                message="Domain operation dispatch context is invalid",
                details={"field": field},
            )
        return values

    def __call__(self, request: AgentOperationRequest) -> Mapping[str, Any]:
        context = request.metadata.get(PROJECTION_NAMESPACE)
        if not isinstance(context, Mapping):
            raise ControlledOperationExecutionError(
                code="DOMAIN_OPERATION_CONTEXT_MISSING",
                message="Domain operation dispatch context is required",
                details={"operation_name": request.operation_name},
            )
        primary_domain_id = context.get("primary_domain_id")
        session_id = context.get("session_id")
        actor_id = context.get("actor_id")
        goal_id = context.get("goal_id")
        if not isinstance(primary_domain_id, str) or not primary_domain_id.strip():
            raise ControlledOperationExecutionError(
                code="DOMAIN_OPERATION_CONTEXT_INVALID",
                message="Domain operation dispatch context is invalid",
                details={"field": "primary_domain_id"},
            )
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ControlledOperationExecutionError(
                code="DOMAIN_OPERATION_CONTEXT_INVALID",
                message="Domain operation dispatch context is invalid",
                details={"field": "actor_id"},
            )
        if not isinstance(goal_id, str) or not goal_id.strip():
            raise ControlledOperationExecutionError(
                code="DOMAIN_OPERATION_CONTEXT_INVALID",
                message="Domain operation dispatch context is invalid",
                details={"field": "goal_id"},
            )
        if session_id is not None and (
            not isinstance(session_id, str) or not session_id.strip()
        ):
            raise ControlledOperationExecutionError(
                code="DOMAIN_OPERATION_CONTEXT_INVALID",
                message="Domain operation dispatch context is invalid",
                details={"field": "session_id"},
            )
        metadata = dict(request.metadata)
        metadata.update(
            {
                "actor_id": actor_id,
                "goal_id": goal_id,
                "approval_request_ids": dict(context.get("approval_request_ids", {})),
            }
        )
        val_impact = None
        val_files: tuple[str, ...] = ()
        val_root = getattr(request, "validation_project_root", None) or metadata.get(
            "validation_project_root"
        )
        if is_project_domain_code_mutation(request.operation_name):
            val_impact, val_files = derive_host_project_change_impact(
                val_root,
                changed_files=metadata.get("validation_changed_files", ()),
            )
        domain_request = DomainOperationRequest(
            request_id=request.id,
            operation_id=request.operation_name,
            operation_version=request.operation_version,
            inputs=request.parameters,
            agent_run_id=request.agent_run_id,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            session_id=session_id,
            primary_domain_id=primary_domain_id,
            supporting_domain_ids=self._strings(
                context.get("supporting_domain_ids", ()),
                "supporting_domain_ids",
            ),
            granted_permissions=request.permissions,
            denied_permissions=self._strings(
                context.get("denied_permissions", ()), "denied_permissions"
            ),
            available_resources=self._strings(
                context.get("available_resources", ()), "available_resources"
            ),
            capabilities=self._strings(
                context.get("capabilities", ("execute",)), "capabilities"
            ),
            approval_request_id=request.approval_request_id,
            idempotency_key=request.idempotency_key,
            created_at=datetime.fromisoformat(request.created_at),
            metadata=metadata,
            validation_impact=val_impact,
            validation_changed_files=val_files,
        )
        result = self._orchestrator.execute(domain_request)
        success = result.status is DomainOperationStatus.COMPLETED
        error = result.error
        if not success and error is None:
            error = {
                "code": "DOMAIN_OPERATION_DISPATCH_BLOCKED",
                "message": "Domain operation dispatch did not complete",
                "details": {"status": result.status.value},
            }
        return {
            "success": success,
            "execution_result_id": result.result_id,
            "domain_operation_result_id": result.result_id,
            "output": dict(result.output),
            "error": dict(error) if error is not None else None,
            "effects": (),
            "side_effects": (),
            "artifacts": (),
            "validation_result_ids": (),
            "rollback_reference": result.transaction_id,
        }


@dataclass(frozen=True, slots=True)
class _PreparedDomainContext:
    """Canonical preparation evidence for one specialized execution."""

    request_id: str
    resolution: DomainResolutionResult
    composition: DomainComposition
    profile: ResolvedDomainProfile
    decisions: tuple[DomainAgentRuntimeDecision, ...]


class DefaultDomainAgentRuntimeIntegrator:
    """Prepare, constrain, invoke, observe, and bind the Phase 9 runtime."""

    def __init__(
        self,
        *,
        resolver: object,
        composer: object,
        profile_resolver: object,
        permission_resolver: object,
        permission_gate: object,
        cognitive_integrator: object,
        agent_runtime_service: object,
        action_budget_service: object | None = None,
        domain_definition_provider: Callable[
            [DomainResolutionResult], tuple[DomainDefinition, ...]
        ],
        profile_input_provider: Callable[
            [DomainComposition, DomainAgentRuntimeIntegrationRequest],
            Mapping[str, object],
        ],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        _require_dependency(resolver, "resolver", "resolve")
        _require_dependency(composer, "composer", "compose")
        _require_dependency(profile_resolver, "profile_resolver", "resolve")
        _require_dependency(permission_resolver, "permission_resolver", "resolve")
        _require_dependency(permission_gate, "permission_gate", "evaluate_operation")
        _require_dependency(cognitive_integrator, "cognitive_integrator", "integrate")
        _require_dependency(agent_runtime_service, "agent_runtime_service", "execute")
        if action_budget_service is not None:
            _require_dependency(
                action_budget_service, "action_budget_service", "decrease_budget"
            )
        if not callable(domain_definition_provider):
            raise DomainAgentRuntimeIntegrationContractError(
                "domain_definition_provider must be callable",
                field="domain_definition_provider",
            )
        if not callable(profile_input_provider):
            raise DomainAgentRuntimeIntegrationContractError(
                "profile_input_provider must be callable",
                field="profile_input_provider",
            )
        if clock is not None and not callable(clock):
            raise DomainAgentRuntimeIntegrationContractError(
                "clock must be callable", field="clock"
            )

        self._resolver = resolver
        self._composer = composer
        self._profile_resolver = profile_resolver
        self._permission_resolver = permission_resolver
        self._permission_gate = permission_gate
        self._cognitive_integrator = cognitive_integrator
        self._agent_runtime_service = agent_runtime_service
        self._action_budget_service = action_budget_service
        self._domain_definition_provider = domain_definition_provider
        self._profile_input_provider = profile_input_provider
        self._clock = (
            clock if clock is not None else (lambda: datetime.now(timezone.utc))
        )

    def _now(self) -> datetime:
        value = self._clock()
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise DomainAgentRuntimeIntegrationContractError(
                "clock must return a timezone-aware datetime", field="clock"
            )
        return value

    # ── Public entry point ────────────────────────────────────────────────

    def run(
        self,
        request: DomainAgentRuntimeIntegrationRequest,
    ) -> DomainAgentRuntimeIntegrationResult:
        """Execute one Domain-specialized Agent Runtime request."""
        if type(request) is not DomainAgentRuntimeIntegrationRequest:
            raise DomainAgentRuntimeIntegrationContractError(
                "request must be a DomainAgentRuntimeIntegrationRequest",
                field="request",
            )
        prepared = self._prepare(request)
        specialized_request = request.agent_request
        cognitive_result = None
        decisions = prepared.decisions
        if request.cognitive_resources:
            cognitive_request = self._cognitive_request(request, prepared)
            cognitive_result = self._cognitive_integrator.integrate(cognitive_request)
            projected_context = self._project_cognitive_context(
                incoming_context=request.agent_request.cognitive_context,
                resolution_context=request.resolution_context,
                prepared=prepared,
                cognitive_result=cognitive_result,
            )
            specialized_request = replace(
                specialized_request, cognitive_context=projected_context
            )
            decisions = (
                *decisions,
                DomainAgentRuntimeDecision(
                    code=DomainAgentRuntimeDecisionCode.DOMAIN_COGNITIVE_BOUND,
                    subject_id=cognitive_result.request_id,
                    reason_codes=("domain_cognitive_projection_complete",),
                    related_ids=(
                        cognitive_result.knowledge_package.id,
                        prepared.composition.id,
                    ),
                ),
            )
        # ── Domain permission restriction ────────────────────────────────
        permission_resolution = self._resolve_domain_permissions(request, prepared)
        # Canonical gate authority: the injected DomainPermissionGate must be
        # exercised at the safe pre-execution boundary. Its decision has real
        # authority to deny or require approval for the specialized path.
        gate_results = self._evaluate_gates(request, prepared)
        gate_denied = any(getattr(result, "denied", False) for result in gate_results)
        gate_requires_approval = any(
            getattr(result, "requires_approval", False) for result in gate_results
        )
        permission_outcome = permission_resolution.effective_permissions.decision
        approval_hint = False
        if permission_outcome is PermissionOutcome.DENY or gate_denied:
            # Domain DENY and Agent denial precedence remain fail-closed;
            # no operation side effects may occur. Gate denial has equal authority.
            blocked_decision = self._blocked_decision(
                subject_id=prepared.composition.id,
                related_ids=(prepared.resolution.id, prepared.profile.id),
                reason_codes=("domain_permission_denied",),
            )
            return DomainAgentRuntimeIntegrationResult(
                request_id=prepared.request_id,
                resolution=prepared.resolution,
                composition=prepared.composition,
                profile=prepared.profile,
                cognitive_result=cognitive_result,
                agent_result=None,
                decisions=(*decisions, blocked_decision),
                domain_trace_id=None,
                agent_trace_id=None,
                blocked=True,
            )
        if (
            permission_outcome is PermissionOutcome.APPROVAL_REQUIRED
            or gate_requires_approval
        ):
            # Approval is owned by the canonical Phase 9 approval
            # infrastructure; Phase 10.41 records the requirement and passes
            # only the existing Phase 9 hint metadata.
            approval_hint = True
            decisions = (
                *decisions,
                DomainAgentRuntimeDecision(
                    code=DomainAgentRuntimeDecisionCode.DOMAIN_APPROVAL_REQUIRED,
                    subject_id=(
                        request.agent_request.operations[0].operation_name
                        if request.agent_request.operations
                        else prepared.composition.id
                    ),
                    reason_codes=("domain_approval_required",),
                    related_ids=(prepared.composition.id,),
                ),
            )
        # Narrowing applies for every non-denied outcome: restrictions are
        # computed from the Domain composition independently of the approval
        # requirement so authority is never wider than the Domain allows.
        narrowed_context = self._narrow_permission_context(
            request.agent_request.permission_context,
            permission_resolution.domain_policies,
            primary_domain_id=str(prepared.composition.primary_domain),
        )
        if narrowed_context is not None:
            changed = (
                request.agent_request.permission_context is None
                or narrowed_context.to_dict()
                != request.agent_request.permission_context.to_dict()
            )
            specialized_request = replace(
                specialized_request, permission_context=narrowed_context
            )
            if changed:
                decisions = (
                    *decisions,
                    DomainAgentRuntimeDecision(
                        code=DomainAgentRuntimeDecisionCode.DOMAIN_PERMISSION_RESTRICTED,
                        subject_id=prepared.composition.id,
                        reason_codes=("domain_permission_narrowing_applied",),
                        related_ids=(prepared.resolution.id,),
                    ),
                )
        # ── Domain autonomy ceiling ──────────────────────────────────────
        specialized_request, autonomy_decision = self._apply_autonomy_ceiling(
            specialized_request, permission_resolution.domain_policies
        )
        if autonomy_decision is not None:
            decisions = (*decisions, autonomy_decision)
        # ── Domain budget restriction ────────────────────────────────────
        budget_decisions = self._apply_budget_restriction(request, prepared)
        if budget_decisions:
            decisions = (*decisions, *budget_decisions)
        # ── Operation / workflow eligibility binding ─────────────────────
        binding_decisions, fail_closed_reason = self._bind_operations_and_workflows(
            request, prepared
        )
        if fail_closed_reason is not None:
            blocked_decision = self._blocked_decision(
                subject_id=prepared.composition.id,
                related_ids=(prepared.resolution.id, prepared.profile.id),
                reason_codes=(fail_closed_reason,),
            )
            return DomainAgentRuntimeIntegrationResult(
                request_id=prepared.request_id,
                resolution=prepared.resolution,
                composition=prepared.composition,
                profile=prepared.profile,
                cognitive_result=cognitive_result,
                agent_result=None,
                decisions=(*decisions, *binding_decisions, blocked_decision),
                domain_trace_id=None,
                agent_trace_id=None,
                blocked=True,
            )
        if binding_decisions:
            decisions = (*decisions, *binding_decisions)

        specialized_request = self._bind_domain_dispatch_context(
            specialized_request, request, prepared
        )

        # ── Approval hint (hint only; canonical approval owns pause) ─────
        if approval_hint and not specialized_request.metadata.get("requires_approval"):
            merged_metadata = dict(specialized_request.metadata)
            merged_metadata["requires_approval"] = True
            specialized_request = replace(specialized_request, metadata=merged_metadata)

        # ── Canonical Phase 9 delegation ─────────────────────────────────
        service_run = self._agent_runtime_service.execute
        agent_result = service_run(specialized_request)

        if agent_result.final_state in _TERMINAL_SUCCESS_STATES:
            decisions = (
                *decisions,
                DomainAgentRuntimeDecision(
                    code=DomainAgentRuntimeDecisionCode.DOMAIN_RUNTIME_COMPLETED,
                    subject_id=agent_result.execution_id,
                    reason_codes=("agent_runtime_execution_completed",),
                    related_ids=(prepared.composition.id, agent_result.request_id),
                ),
            )

        memory_binding_ids = tuple(
            str(update["id"])
            for update in agent_result.memory_updates
            if isinstance(update, Mapping) and update.get("id") is not None
        )
        return DomainAgentRuntimeIntegrationResult(
            request_id=prepared.request_id,
            resolution=prepared.resolution,
            composition=prepared.composition,
            profile=prepared.profile,
            cognitive_result=cognitive_result,
            agent_result=agent_result,
            decisions=decisions,
            domain_trace_id=None,
            agent_trace_id=agent_result.trace_id,
            memory_binding_ids=memory_binding_ids,
            blocked=False,
        )

    execute = run

    # ── Preparation pipeline ──────────────────────────────────────────────

    def _cognitive_request(
        self,
        request: DomainAgentRuntimeIntegrationRequest,
        prepared: _PreparedDomainContext,
    ) -> DomainCognitiveIntegrationRequest:
        context = request.resolution_context
        objective = context.objective or context.user_input
        if not objective:
            raise self._blocked_error(
                "Domain cognitive preparation requires a canonical objective",
                request_id=request.request_id,
                subject_id=prepared.composition.id,
                related_ids=(prepared.resolution.id,),
                reason_codes=("domain_cognitive_objective_missing",),
                details={"composition_id": prepared.composition.id},
            )
        return DomainCognitiveIntegrationRequest(
            request_id=request.request_id,
            resolution_context_id=context.id,
            resolution_result_id=prepared.resolution.id,
            objective=objective,
            composition=prepared.composition,
            profile=prepared.profile,
            resources=request.cognitive_resources,
            actor_id=request.agent_request.actor_id,
            session_id=context.session_id,
            effective_permissions=tuple(context.permissions),
        )

    def _project_cognitive_context(
        self,
        *,
        incoming_context: Mapping[str, Any],
        resolution_context: Any,
        prepared: _PreparedDomainContext,
        cognitive_result: Any,
    ) -> dict[str, Any]:
        """Deterministically project Domain cognition into the Phase 9 seam."""
        projection: dict[str, Any] = {
            "domain_resolution_context_id": resolution_context.id,
            "domain_resolution_result_id": prepared.resolution.id,
            "domain_composition_id": prepared.composition.id,
            "primary_domain": str(prepared.composition.primary_domain),
            "supporting_domains": tuple(
                str(domain) for domain in prepared.composition.supporting_domains
            ),
            "resolved_profile_id": prepared.profile.id,
            "knowledge_package_id": cognitive_result.knowledge_package.id,
            "adapted_resource_ids": tuple(
                resource.id for resource in cognitive_result.adapted_resources
            ),
            "presentation_reference_ids": tuple(
                item.ref_id for item in cognitive_result.presentation_items
            ),
            "domain_cognitive_request_id": cognitive_result.request_id,
        }
        merged = dict(incoming_context)
        existing = merged.get(PROJECTION_NAMESPACE)
        if existing is not None and existing != projection:
            raise DomainAgentRuntimeIntegrationContractError(
                "cognitive_context['domain_intelligence'] collision with "
                "non-equal caller-owned data; refusing to overwrite",
                field="cognitive_context",
            )
        merged[PROJECTION_NAMESPACE] = projection
        return merged

    @staticmethod
    def _specialized_agent_request(
        agent_request: IntegratedAgentExecutionRequest,
        projected_context: Mapping[str, Any],
    ) -> IntegratedAgentExecutionRequest:
        """Specialize the canonical Phase 9 request through dataclasses.replace."""
        return replace(agent_request, cognitive_context=projected_context)

    def _resolve_domain_permissions(
        self,
        request: DomainAgentRuntimeIntegrationRequest,
        prepared: _PreparedDomainContext,
    ) -> Any:
        """Resolve the effective Domain permission decision for this execution."""
        if request.agent_request.operations:
            action = PermissionCapability.OPERATION_EXECUTE
            operation_id = request.agent_request.operations[0].operation_name
            workflow_id = None
        elif request.agent_request.workflow is not None:
            action = PermissionCapability.WORKFLOW_EXECUTE
            operation_id = None
            workflow_id = request.agent_request.workflow.workflow_id
        else:
            # Baseline read-level Domain evaluation for executions that carry
            # neither an operation nor an already-resolved workflow.
            action = PermissionCapability.KNOWLEDGE_READ
            operation_id = None
            workflow_id = None
        perm_request = DomainPermissionRequest(
            request_id=f"{request.request_id}:permissions",
            action=action,
            domain_id=str(prepared.composition.primary_domain),
            actor_id=request.agent_request.actor_id,
            session_id=request.resolution_context.session_id or "system",
            operation_id=operation_id,
            workflow_id=workflow_id,
            sensitivity_level=request.agent_request.sensitivity,
        )
        try:
            return self._permission_resolver.resolve(
                perm_request,
                supporting_domains=tuple(
                    str(domain) for domain in prepared.composition.supporting_domains
                ),
            )
        except (DomainError, ValueError) as exc:
            raise self._blocked_error(
                "Domain permission resolution failed for the composed specialization",
                request_id=request.request_id,
                subject_id=prepared.composition.id,
                related_ids=(prepared.resolution.id,),
                reason_codes=("domain_permission_resolution_failed",),
                details={"composition_id": prepared.composition.id},
                cause=exc,
            ) from exc

    def _evaluate_gates(
        self,
        request: DomainAgentRuntimeIntegrationRequest,
        prepared: _PreparedDomainContext,
    ) -> tuple[Any, ...]:
        """Exercise canonical DomainPermissionGate authority at safe boundary.

        Every declared operation receives its own dry-run gate evaluation.
        Dry-run preserves one-time approval evidence for the authoritative
        dispatch-time gate in ``DefaultDomainOperationOrchestrator``.
        """
        if request.agent_request.operations:
            return tuple(
                self._permission_gate.evaluate_operation(
                    request_id=f"{request.request_id}:gate:{index}:{op.operation_name}",
                    domain_id=str(prepared.composition.primary_domain),
                    actor_id=request.agent_request.actor_id,
                    session_id=request.resolution_context.session_id or "system",
                    operation_id=op.operation_name,
                    operation_version=getattr(op, "operation_version", None),
                    dry_run=True,
                )
                for index, op in enumerate(request.agent_request.operations)
            )
        if request.agent_request.workflow is not None:
            wf = request.agent_request.workflow
            return (
                self._permission_gate.evaluate_workflow(
                    request_id=f"{request.request_id}:gate:workflow",
                    domain_id=str(prepared.composition.primary_domain),
                    actor_id=request.agent_request.actor_id,
                    session_id=request.resolution_context.session_id or "system",
                    workflow_id=wf.workflow_id,
                    workflow_version=getattr(wf, "workflow_version", None),
                    dry_run=True,
                ),
            )
        return ()

    def _narrow_permission_context(
        self,
        permission_context: AgentPermissionContext | None,
        domain_policies: tuple[Any, ...],
        *,
        primary_domain_id: str | None = None,
    ) -> AgentPermissionContext | None:
        """Restrict the Agent permission context by Domain policies only.

        Set/list dimensions intersect with the primary Domain allowlist and
        with every Domain prohibition; booleans use AND; prohibitions win.
        Supporting-Domain allowlists describe their own Domain scope and may
        only narrow through explicit prohibitions.  A Domain value never
        widens the incoming Agent authority.
        """
        if permission_context is None:
            return None
        data = dict(permission_context.to_dict())
        primary_policies = tuple(
            policy
            for policy in domain_policies
            if primary_domain_id is None or policy.domain_id == primary_domain_id
        )
        effective_operations = set(data["allowed_operations"])
        allowed_operation_constraints = [
            tuple(policy.allowed_operations)
            for policy in primary_policies
            if policy.allowed_operations is not None
        ]
        if allowed_operation_constraints:
            effective_operations &= set.intersection(
                *(set(constraint) for constraint in allowed_operation_constraints)
            )
        for policy in domain_policies:
            effective_operations -= set(policy.prohibited_operations)
        data["allowed_operations"] = tuple(
            operation
            for operation in permission_context.allowed_operations
            if operation in effective_operations
        )
        allowed_resource_constraints = [
            tuple(policy.allowed_resources)
            for policy in primary_policies
            if policy.allowed_resources is not None
        ]
        effective_resources = set(data["allowed_resources"])
        if allowed_resource_constraints:
            effective_resources &= set.intersection(
                *(set(constraint) for constraint in allowed_resource_constraints)
            )
        for policy in domain_policies:
            effective_resources -= set(policy.prohibited_resources)
        data["allowed_resources"] = tuple(
            resource
            for resource in permission_context.allowed_resources
            if resource in effective_resources
        )
        sensitivity_constraints = [
            {level.value for level in policy.allowed_sensitivity_levels}
            for policy in domain_policies
            if policy.allowed_sensitivity_levels is not None
        ]
        if sensitivity_constraints:
            allowed_levels = set.intersection(*sensitivity_constraints)
            data["allowed_sensitivity_levels"] = tuple(
                level.value
                for level in permission_context.allowed_sensitivity_levels
                if level.value in allowed_levels
            )
        for policy_attr, context_key in _AGENT_BOOLEAN_BY_POLICY_ATTR:
            for policy in domain_policies:
                if not getattr(policy, policy_attr):
                    data[context_key] = False
        for capability, context_key in _CAPABILITY_BOOLEAN_PROHIBITIONS:
            for policy in domain_policies:
                if capability in policy.prohibited_capabilities:
                    data[context_key] = False
        # Reversible/irreversible autonomy flags compose restrictively (AND).
        # Domain false can disable incoming true; Domain true never enables
        # incoming false. Irreversible maps directly to destructive actions.
        effective_allow_reversible = (
            all(
                policy.autonomy_limits.allow_reversible_changes
                for policy in domain_policies
            )
            if domain_policies
            else True
        )
        effective_allow_irreversible = (
            all(
                policy.autonomy_limits.allow_irreversible_changes
                for policy in domain_policies
            )
            if domain_policies
            else True
        )
        if not effective_allow_irreversible:
            data["allow_destructive_actions"] = False
        domain_autonomy_max = self._effective_domain_autonomy_max(domain_policies)
        if domain_autonomy_max is not None:
            data["maximum_autonomy_level"] = min(
                int(data["maximum_autonomy_level"]), domain_autonomy_max
            )
        if not effective_allow_reversible:
            data["maximum_autonomy_level"] = min(int(data["maximum_autonomy_level"]), 1)
        if not effective_allow_irreversible:
            data["maximum_autonomy_level"] = min(int(data["maximum_autonomy_level"]), 2)
        return AgentPermissionContext.from_mapping(data)

    @staticmethod
    def _effective_domain_autonomy_max(
        domain_policies: tuple[Any, ...],
    ) -> int | None:
        limits = [
            policy.autonomy_limits.maximum_autonomy_level
            for policy in domain_policies
            if policy.autonomy_limits.maximum_autonomy_level is not None
        ]
        return min(limits) if limits else None

    def _apply_autonomy_ceiling(
        self,
        agent_request: IntegratedAgentExecutionRequest,
        domain_policies: tuple[Any, ...],
    ) -> tuple[IntegratedAgentExecutionRequest, DomainAgentRuntimeDecision | None]:
        """Enforce DOMAIN_AUTONOMY <= GLOBAL_AUTHORIZED_AUTONOMY.

        The Domain limit is a ceiling: it can only reduce or preserve the
        incoming authorized autonomy level, never raise it.  An absent or
        unconstrained Domain limit preserves the incoming Phase 9 value.
        Reversible/irreversible flags compose restrictively via AND and cap
        the effective autonomy level accordingly.
        """
        effective_domain_max = self._effective_domain_autonomy_max(domain_policies)
        effective_allow_reversible = (
            all(
                policy.autonomy_limits.allow_reversible_changes
                for policy in domain_policies
            )
            if domain_policies
            else True
        )
        effective_allow_irreversible = (
            all(
                policy.autonomy_limits.allow_irreversible_changes
                for policy in domain_policies
            )
            if domain_policies
            else True
        )
        effective_max = agent_request.max_autonomy_level
        if effective_domain_max is not None:
            effective_max = min(effective_max, effective_domain_max)
        if not effective_allow_reversible:
            effective_max = min(effective_max, 1)
        if not effective_allow_irreversible:
            effective_max = min(effective_max, 2)
        if effective_max >= agent_request.max_autonomy_level:
            return agent_request, None
        specialized = replace(agent_request, max_autonomy_level=effective_max)
        decision = DomainAgentRuntimeDecision(
            code=DomainAgentRuntimeDecisionCode.DOMAIN_AUTONOMY_RESTRICTED,
            subject_id=agent_request.request_id,
            reason_codes=("domain_autonomy_ceiling_applied",),
            related_ids=(agent_request.execution_id,),
        )
        return specialized, decision

    def _apply_budget_restriction(
        self,
        request: DomainAgentRuntimeIntegrationRequest,
        prepared: _PreparedDomainContext,
    ) -> tuple[DomainAgentRuntimeDecision, ...]:
        """Restrict the one canonical Phase 9 Action Budget.

        Only the canonical decrease path is used; a stricter master limit is
        preserved untouched and no increase path exists in this boundary.
        """
        domain_budget = request.domain_budget
        budget_id = request.agent_request.budget_id
        if domain_budget is None:
            return ()
        if budget_id is None or self._action_budget_service is None:
            raise self._blocked_error(
                "Domain budget restriction requires the canonical Action "
                "Budget service and a canonical budget identifier",
                request_id=request.request_id,
                subject_id=prepared.composition.id,
                related_ids=(prepared.resolution.id,),
                reason_codes=("domain_budget_service_unavailable",),
                details={"composition_id": prepared.composition.id},
            )
        decisions: list[DomainAgentRuntimeDecision] = []
        for resource_type, attribute in _DOMAIN_BUDGET_ATTR_BY_RESOURCE:
            ceiling = getattr(domain_budget, attribute)
            if ceiling is None:
                continue
            budget = self._action_budget_service.get_budget(budget_id)
            current_limit = budget.limit_for(resource_type)
            if current_limit is not None and ceiling >= current_limit:
                continue
            self._action_budget_service.decrease_budget(
                budget_id=budget_id,
                resource_type=resource_type,
                new_limit=ceiling,
                reason_codes=("domain_budget_restriction",),
            )
            decisions.append(
                DomainAgentRuntimeDecision(
                    code=DomainAgentRuntimeDecisionCode.DOMAIN_BUDGET_RESTRICTED,
                    subject_id=budget_id,
                    reason_codes=("domain_budget_ceiling_applied",),
                    related_ids=(prepared.composition.id,),
                    metadata={"resource_type": resource_type.value},
                )
            )
        return tuple(decisions)

    def _bind_operations_and_workflows(
        self,
        request: DomainAgentRuntimeIntegrationRequest,
        prepared: _PreparedDomainContext,
    ) -> tuple[tuple[DomainAgentRuntimeDecision, ...], str | None]:
        """Validate operation/workflow eligibility and bind by reference.

        Selection only: execution stays with the canonical Phase 9/Domain
        orchestration stack.  A Domain-requested workflow that the current
        Phase 9 seam cannot represent fails closed (Phase 10.42 scope).
        """
        decisions: list[DomainAgentRuntimeDecision] = []
        eligible_operations = {
            item.identifier for item in prepared.composition.operations
        }
        for operation in request.agent_request.operations:
            if operation.operation_name not in eligible_operations:
                return tuple(decisions), "domain_operation_not_composable"
        if request.agent_request.operations:
            decisions.append(
                DomainAgentRuntimeDecision(
                    code=DomainAgentRuntimeDecisionCode.DOMAIN_OPERATION_SELECTED,
                    subject_id=request.agent_request.operations[0].operation_name,
                    reason_codes=("domain_operation_eligible",),
                    related_ids=(prepared.composition.id,),
                )
            )
        if request.agent_request.workflow is not None:
            decisions.append(
                DomainAgentRuntimeDecision(
                    code=DomainAgentRuntimeDecisionCode.DOMAIN_WORKFLOW_BOUND,
                    subject_id=request.agent_request.workflow.id,
                    reason_codes=("existing_workflow_plan_bound_by_reference",),
                    related_ids=(prepared.composition.id,),
                )
            )
        elif (
            request.agent_request.workflow is None
            and not request.agent_request.operations
            and request.resolution_context.current_workflow is not None
        ):
            return (
                tuple(decisions),
                "domain_workflow_unsupported_pending_phase_10_42",
            )
        return tuple(decisions), None

    @staticmethod
    def _bind_domain_dispatch_context(
        agent_request: IntegratedAgentExecutionRequest,
        integration_request: DomainAgentRuntimeIntegrationRequest,
        prepared: _PreparedDomainContext,
    ) -> IntegratedAgentExecutionRequest:
        """Bind current Domain references to every Phase 9 operation request."""
        if not agent_request.operations:
            return agent_request
        permission_context = agent_request.permission_context
        context = {
            "primary_domain_id": str(prepared.composition.primary_domain),
            "supporting_domain_ids": tuple(
                str(domain) for domain in prepared.composition.supporting_domains
            ),
            "session_id": integration_request.resolution_context.session_id or "system",
            "actor_id": agent_request.actor_id,
            "goal_id": agent_request.goal_id,
            "available_resources": (
                permission_context.allowed_resources if permission_context else ()
            ),
            "denied_permissions": (),
            "approval_request_ids": {},
            "composition_id": prepared.composition.id,
            "profile_id": prepared.profile.id,
        }
        operations = []
        for operation in agent_request.operations:
            operation_data = operation.to_dict()
            metadata = dict(operation_data["metadata"])
            existing = metadata.get(PROJECTION_NAMESPACE)
            approval_request_ids: Mapping[str, object] = {}
            capabilities: tuple[str, ...] = ("execute",)
            if existing is not None:
                if not isinstance(existing, Mapping):
                    raise DomainAgentRuntimeIntegrationContractError(
                        "operation metadata Domain context collision",
                        field="agent_request.operations.metadata",
                    )
                for key, value in existing.items():
                    if key == "approval_request_ids":
                        if not isinstance(value, Mapping):
                            raise DomainAgentRuntimeIntegrationContractError(
                                "approval_request_ids must be a mapping",
                                field="agent_request.operations.metadata",
                            )
                        approval_request_ids = value
                    elif key == "capabilities":
                        capabilities = DomainOperationDispatchAdapter._strings(
                            value, "capabilities"
                        )
                    elif key in context and context[key] != value:
                        raise DomainAgentRuntimeIntegrationContractError(
                            "operation metadata Domain context collision",
                            field="agent_request.operations.metadata",
                        )
            metadata[PROJECTION_NAMESPACE] = {
                **context,
                "approval_request_ids": dict(approval_request_ids),
                "capabilities": capabilities,
            }
            operation_data["metadata"] = metadata
            operations.append(AgentOperationRequest.from_dict(operation_data))
        return replace(agent_request, operations=tuple(operations))

    def _reevaluation_decisions(
        self,
        request: DomainAgentRuntimeIntegrationRequest,
        resolution: DomainResolutionResult,
    ) -> tuple[DomainAgentRuntimeDecision, ...]:
        """Report safe-boundary reevaluation against previous evidence.

        Previous evidence arrives as caller-provided canonical metadata on
        the wrapper request; this boundary stays stateless and never
        reevaluates inside an operation.
        """
        decisions: list[DomainAgentRuntimeDecision] = []
        if request.force_domain_reevaluation:
            decisions.append(
                DomainAgentRuntimeDecision(
                    code=DomainAgentRuntimeDecisionCode.DOMAIN_REEVALUATED,
                    subject_id=request.request_id,
                    reason_codes=("explicit_reevaluation_boundary",),
                    related_ids=(resolution.id,),
                )
            )
        previous_primary = request.metadata.get("previous_primary_domain")
        if (
            isinstance(previous_primary, str)
            and previous_primary.strip()
            and resolution.primary_domain is not None
            and previous_primary != str(resolution.primary_domain)
        ):
            decisions.append(
                DomainAgentRuntimeDecision(
                    code=DomainAgentRuntimeDecisionCode.PRIMARY_DOMAIN_CHANGED,
                    subject_id=str(resolution.primary_domain),
                    reason_codes=("primary_domain_changed_on_reevaluation",),
                    related_ids=(previous_primary,),
                )
            )
        previous_supporting = request.metadata.get("previous_supporting_domains")
        if isinstance(previous_supporting, (list, tuple)):
            previous_set = {str(domain) for domain in previous_supporting}
            for domain in resolution.supporting_domains:
                if str(domain) not in previous_set:
                    decisions.append(
                        DomainAgentRuntimeDecision(
                            code=DomainAgentRuntimeDecisionCode.SUPPORTING_DOMAIN_ADDED,
                            subject_id=str(domain),
                            reason_codes=("supporting_domain_added_on_reevaluation",),
                            related_ids=(resolution.id,),
                        )
                    )
        return tuple(decisions)

    def _prepare(
        self, request: DomainAgentRuntimeIntegrationRequest
    ) -> _PreparedDomainContext:
        resolution = self._resolver.resolve(request.resolution_context)
        if resolution.status is not DomainResolutionStatus.RESOLVED:
            raise self._blocked_error(
                "Domain resolution does not permit a specialized agent execution",
                request_id=request.request_id,
                subject_id=resolution.id,
                related_ids=(request.resolution_context.id,),
                reason_codes=("domain_resolution_not_resolved",),
                details={
                    "resolution_status": resolution.status.value,
                    "resolution_id": resolution.id,
                },
            )
        try:
            definitions = self._domain_definition_provider(resolution)
            composition = self._composer.compose(resolution, definitions)
        except DomainError as exc:
            raise self._blocked_error(
                "Domain composition failed for the selected specialization",
                request_id=request.request_id,
                subject_id=resolution.id,
                related_ids=(request.resolution_context.id,),
                reason_codes=("domain_composition_failed",),
                details={"resolution_id": resolution.id},
                cause=exc,
            ) from exc
        try:
            profile_inputs = self._profile_input_provider(composition, request)
            profile_resolution = self._profile_resolver.resolve(**dict(profile_inputs))
        except DomainError as exc:
            raise self._blocked_error(
                "Domain profile resolution failed for the composed specialization",
                request_id=request.request_id,
                subject_id=composition.id,
                related_ids=(resolution.id,),
                reason_codes=("domain_profile_resolution_failed",),
                details={"composition_id": composition.id},
                cause=exc,
            ) from exc
        profile = profile_resolution.profile
        if profile is None:
            raise self._blocked_error(
                "Domain profile resolution produced no effective profile",
                request_id=request.request_id,
                subject_id=composition.id,
                related_ids=(resolution.id,),
                reason_codes=("domain_profile_unresolved",),
                details={"composition_id": composition.id},
            )
        reevaluation_decisions = self._reevaluation_decisions(request, resolution)
        decisions = (
            *reevaluation_decisions,
            DomainAgentRuntimeDecision(
                code=DomainAgentRuntimeDecisionCode.DOMAIN_RESOLVED,
                subject_id=resolution.id,
                reason_codes=("domain_resolution_complete",),
                related_ids=(request.resolution_context.id,),
            ),
            DomainAgentRuntimeDecision(
                code=DomainAgentRuntimeDecisionCode.DOMAIN_COMPOSED,
                subject_id=composition.id,
                reason_codes=("domain_composition_complete",),
                related_ids=(resolution.id,),
            ),
            DomainAgentRuntimeDecision(
                code=DomainAgentRuntimeDecisionCode.PROFILE_RESOLVED,
                subject_id=profile.id,
                reason_codes=("domain_profile_resolved",),
                related_ids=(composition.id,),
            ),
        )
        return _PreparedDomainContext(
            request_id=request.request_id,
            resolution=resolution,
            composition=composition,
            profile=profile,
            decisions=decisions,
        )

    # ── Fail-closed helpers ───────────────────────────────────────────────

    @staticmethod
    def _blocked_decision(
        *,
        subject_id: str,
        related_ids: tuple[str, ...],
        reason_codes: tuple[str, ...] = ("domain_runtime_blocked",),
    ) -> DomainAgentRuntimeDecision:
        return DomainAgentRuntimeDecision(
            code=DomainAgentRuntimeDecisionCode.DOMAIN_RUNTIME_BLOCKED,
            subject_id=subject_id,
            reason_codes=reason_codes,
            related_ids=related_ids,
        )

    def _blocked_error(
        self,
        message: str,
        *,
        request_id: str,
        subject_id: str,
        related_ids: tuple[str, ...],
        reason_codes: tuple[str, ...],
        details: Mapping[str, object] | None = None,
        cause: Exception | None = None,
    ) -> DomainAgentRuntimeIntegrationBlockedError:
        decision = self._blocked_decision(
            subject_id=subject_id,
            related_ids=related_ids,
            reason_codes=reason_codes,
        )
        error_details: dict[str, object] = {
            "request_id": request_id,
            "decisions": (decision.to_dict(),),
        }
        if details is not None:
            error_details.update(dict(details))
        error = DomainAgentRuntimeIntegrationBlockedError(
            message, details=error_details
        )
        if cause is not None:
            error.__cause__ = cause
        return error


__all__ = [
    "DefaultDomainAgentRuntimeIntegrator",
    "DomainAgentRuntimeIntegrator",
    "DomainOperationDispatchAdapter",
]
