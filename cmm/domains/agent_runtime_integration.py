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
from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.agent_runtime.enums import BudgetResourceType
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
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.errors import (
    DomainAgentRuntimeIntegrationBlockedError,
    DomainAgentRuntimeIntegrationContractError,
    DomainError,
)
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.profile_contracts import ResolvedDomainProfile
from cmm.domains.resolver_contracts import DomainResolutionResult

PROJECTION_NAMESPACE = "domain_intelligence"

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
        _require_dependency(agent_runtime_service, "agent_runtime_service", "run")
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
        cognitive_result = None
        decisions = prepared.decisions
        if request.cognitive_resources:
            cognitive_request = self._cognitive_request(request, prepared)
            cognitive_result = self._cognitive_integrator.integrate(cognitive_request)
            # Validate the deterministic projection (including fail-closed
            # collision handling) before it enters the Phase 9 request seam.
            self._project_cognitive_context(
                incoming_context=request.agent_request.cognitive_context,
                resolution_context=request.resolution_context,
                prepared=prepared,
                cognitive_result=cognitive_result,
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
        permission_outcome = permission_resolution.effective_permissions.decision
        if permission_outcome is PermissionOutcome.DENY:
            # Domain DENY and Agent denial precedence remain fail-closed;
            # no operation side effects may occur.
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
        if permission_outcome is PermissionOutcome.APPROVAL_REQUIRED:
            # Approval is owned by the canonical Phase 9 approval
            # infrastructure; Phase 10.41 records the requirement only.
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
        else:
            narrowed_context = self._narrow_permission_context(
                request.agent_request.permission_context,
                permission_resolution.domain_policies,
                primary_domain_id=str(prepared.composition.primary_domain),
            )
            if narrowed_context is not None and (
                request.agent_request.permission_context is None
                or narrowed_context.to_dict()
                != request.agent_request.permission_context.to_dict()
            ):
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
        _, autonomy_decision = self._apply_autonomy_ceiling(
            request.agent_request, permission_resolution.domain_policies
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
        # Specialized execution pipeline stages after cognition (budget,
        # operation routing, runtime delegation) extend this boundary in
        # subsequent tasks and remain fail-closed until then.
        blocked_decision = self._blocked_decision(
            subject_id=prepared.composition.id,
            related_ids=(prepared.resolution.id, prepared.profile.id),
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
        if allowed_resource_constraints:
            effective_resources = set(data["allowed_resources"]) & set.intersection(
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
        domain_autonomy_max = self._effective_domain_autonomy_max(domain_policies)
        if domain_autonomy_max is not None:
            data["maximum_autonomy_level"] = min(
                int(data["maximum_autonomy_level"]), domain_autonomy_max
            )
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
        """
        effective_domain_max = self._effective_domain_autonomy_max(domain_policies)
        if effective_domain_max is None:
            return agent_request, None
        effective_max = min(agent_request.max_autonomy_level, effective_domain_max)
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
        decisions = (
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
]
