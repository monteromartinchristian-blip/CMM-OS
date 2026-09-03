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
from cmm.domains.profile_contracts import ResolvedDomainProfile
from cmm.domains.resolver_contracts import DomainResolutionResult

PROJECTION_NAMESPACE = "domain_intelligence"


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
        # Specialized execution pipeline stages after cognition (permission
        # narrowing, autonomy, budget, operation routing, runtime delegation)
        # extend this boundary in subsequent tasks and remain fail-closed
        # until then.
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
