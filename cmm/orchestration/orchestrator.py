"""Phase 11.2 — the global request orchestrator.

``Orchestrator`` is the one Phase 11 global request coordinator.  It resolves
deterministic intent, gathers authorized context, delegates domain selection to
canonical Domain Intelligence, selects a bounded execution route while
delegating agent selection to canonical Agent Runtime authority, applies the
restrictive orchestration policy, records a safe orchestration decision, emits
safe lifecycle events and returns an immutable structured result.

It deliberately does **not** execute the downstream vertical.  It never runs an
operation, starts a workflow, runs an agent, writes memory or knowledge, and
makes no provider or model call; the only Phase 11.2-owned side effects are safe
decision persistence and safe event emission.

Collaborators are constructor-injected.  The orchestrator holds no service
locator and never resolves a service from a container while handling a request.

Frozen pipeline order::

    validate request
    emit request_received
    resolve intent            -> unknown stops for clarification
    resolve base context      -> unresolved session stops for clarification
    resolve canonical domain  -> ambiguity stops / canonical deny blocks
    resolve authorized domain context
    select execution route
    evaluate restrictive policy -> deny / approval / escalate terminal paths
    construct safe decision record
    persist decision record
    emit terminal routing event
    return OrchestrationResult
"""

from __future__ import annotations

import contextlib
from typing import Any, Protocol, runtime_checkable

from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationDecisionRecord,
    OrchestrationPolicyDecision,
    OrchestrationRequest,
    OrchestrationResult,
    OrchestrationStatus,
    PolicyDisposition,
    ResolvedContext,
)
from cmm.orchestration.errors import OrchestrationError

__all__ = [
    "Orchestrator",
    "OrchestratorProtocol",
]

#: The decision identity is derived from the request identity, so replaying the
#: same request maps to the same decision and repository replay stays
#: idempotent without introducing backend idempotency keys (Phase 11.3).
DECISION_ID_PREFIX = "orchestration-decision"

EVENT_REQUEST_RECEIVED = "orchestration.request_received"
EVENT_INTENT_RESOLVED = "orchestration.intent_resolved"
EVENT_DOMAIN_RESOLVED = "orchestration.domain_resolved"
EVENT_ROUTE_SELECTED = "orchestration.route_selected"
EVENT_APPROVAL_REQUIRED = "orchestration.approval_required"
EVENT_BLOCKED = "orchestration.blocked"
EVENT_ESCALATED = "orchestration.escalated"
EVENT_ROUTED = "orchestration.routed"
EVENT_FAILED = "orchestration.failed"

REASON_INTENT_UNKNOWN = "ORCHESTRATION_INTENT_UNKNOWN"
REASON_SESSION_UNRESOLVED = "ORCHESTRATION_SESSION_UNRESOLVED"
REASON_DOMAIN_CLARIFICATION = "ORCHESTRATION_DOMAIN_NEEDS_CLARIFICATION"
REASON_DOMAIN_BLOCK = "ORCHESTRATION_CANONICAL_DOMAIN_BLOCK"

EVENT_EMISSION_FAILED = "ORCHESTRATION_EVENT_EMISSION_FAILED"
INTERNAL_FAILURE = "ORCHESTRATION_INTERNAL_FAILURE"


@runtime_checkable
class OrchestratorProtocol(Protocol):
    """The one global Phase 11 request coordination boundary."""

    def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult: ...


class Orchestrator:
    """The one global Phase 11 request coordinator."""

    def __init__(
        self,
        *,
        intent_resolver: Any,
        context_resolver: Any,
        domain_router: Any,
        agent_router: Any,
        policy: Any,
        decision_repository: Any,
        event_sink: Any,
    ) -> None:
        for name, collaborator in (
            ("intent_resolver", intent_resolver),
            ("context_resolver", context_resolver),
            ("domain_router", domain_router),
            ("agent_router", agent_router),
            ("policy", policy),
            ("decision_repository", decision_repository),
            ("event_sink", event_sink),
        ):
            if collaborator is None:
                raise TypeError(f"{name} must be provided")

        self._intent_resolver = intent_resolver
        self._context_resolver = context_resolver
        self._domain_router = domain_router
        self._agent_router = agent_router
        self._policy = policy
        self._decision_repository = decision_repository
        self._event_sink = event_sink

    # ── Public API ───────────────────────────────────────────────────────────

    def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult:
        """Coordinate one request, or fail closed with a safe result."""

        if not isinstance(request, OrchestrationRequest):
            raise TypeError(
                f"request must be an OrchestrationRequest, got {type(request).__name__}"
            )

        try:
            return self._run(request)
        except OrchestrationError as error:
            return self._failed(request, error)
        except Exception:  # noqa: BLE001 - DP-102 requires a fail-closed result
            # DP-102: every accepted request must produce a safe structured
            # result or fail closed.  An unexpected internal defect is therefore
            # converted into a safe failed result; no exception text and no
            # traceback is exposed through the public boundary.
            return self._failed(
                request,
                OrchestrationError(
                    "Orchestration failed closed",
                    code=INTERNAL_FAILURE,
                    details={"request_id": request.request_id},
                ),
            )

    # ── Frozen pipeline ──────────────────────────────────────────────────────

    def _run(self, request: OrchestrationRequest) -> OrchestrationResult:
        self._emit(
            EVENT_REQUEST_RECEIVED,
            request,
            channel=request.channel.value,
            session_id=request.session_id,
        )

        resolution = self._resolve_intent(request)
        self._emit(
            EVENT_INTENT_RESOLVED,
            request,
            intent=resolution.intent.value,
            needs_clarification=resolution.needs_clarification,
        )

        if resolution.needs_clarification or resolution.intent is IntentKind.UNKNOWN:
            return self._clarification(
                request,
                resolution,
                (REASON_INTENT_UNKNOWN, *resolution.reason_codes),
            )

        base_context = self._resolve_base_context(request)
        if base_context.missing_refs:
            return self._clarification(
                request,
                resolution,
                (REASON_SESSION_UNRESOLVED, *base_context.reason_codes),
            )

        domain = self._route_domain(request, resolution, base_context)
        self._emit(
            EVENT_DOMAIN_RESOLVED,
            request,
            status=domain.status,
            primary_domain=domain.primary_domain,
            supporting_domains=domain.supporting_domains,
            needs_clarification=domain.needs_clarification,
        )

        if domain.needs_clarification:
            return self._clarification(
                request,
                resolution,
                (
                    REASON_DOMAIN_CLARIFICATION,
                    *domain.reason_codes,
                ),
                domain=domain,
            )

        if domain.primary_domain is None:
            return self._domain_block(request, resolution, domain)

        domain_context = self._resolve_domain_context(request, base_context, domain)
        route = self._route_execution(request, resolution, domain_context, domain)
        self._emit(
            EVENT_ROUTE_SELECTED,
            request,
            route=route.route.value,
            agent_id=route.agent_id,
            workflow_id=route.workflow_id,
        )

        policy_decision = self._evaluate_policy(
            request, resolution, domain_context, domain, route
        )
        return self._terminal_policy(
            request, resolution, domain, route, policy_decision
        )

    # ── Pipeline steps ───────────────────────────────────────────────────────

    def _resolve_intent(self, request: OrchestrationRequest) -> IntentResolution:
        resolution = self._intent_resolver.resolve(request)
        if not isinstance(resolution, IntentResolution):
            raise OrchestrationError(
                "Intent resolution returned an unexpected value",
                code="INTENT_RESOLUTION_CONTRACT_VIOLATION",
                details={"request_id": request.request_id},
            )
        return resolution

    def _resolve_base_context(self, request: OrchestrationRequest) -> ResolvedContext:
        context = self._context_resolver.resolve_base(request)
        if not isinstance(context, ResolvedContext):
            raise OrchestrationError(
                "Base context resolution returned an unexpected value",
                code="CONTEXT_RESOLUTION_CONTRACT_VIOLATION",
                details={"request_id": request.request_id},
            )
        return context

    def _route_domain(
        self,
        request: OrchestrationRequest,
        resolution: IntentResolution,
        context: ResolvedContext,
    ) -> DomainRouteDecision:
        decision = self._domain_router.route(request, resolution, context)
        if not isinstance(decision, DomainRouteDecision):
            raise OrchestrationError(
                "Domain routing returned an unexpected value",
                code="DOMAIN_ROUTING_CONTRACT_VIOLATION",
                details={"request_id": request.request_id},
            )
        return decision

    def _resolve_domain_context(
        self,
        request: OrchestrationRequest,
        base_context: ResolvedContext,
        domain: DomainRouteDecision,
    ) -> ResolvedContext:
        context = self._context_resolver.resolve_domain_context(
            request, base_context, domain
        )
        if not isinstance(context, ResolvedContext):
            raise OrchestrationError(
                "Authorized domain context resolution returned an unexpected value",
                code="CONTEXT_RESOLUTION_CONTRACT_VIOLATION",
                details={"request_id": request.request_id},
            )
        return context

    def _route_execution(
        self,
        request: OrchestrationRequest,
        resolution: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
    ) -> AgentRouteDecision:
        decision = self._agent_router.route(
            request=request, intent=resolution, context=context, domain=domain
        )
        if not isinstance(decision, AgentRouteDecision):
            raise OrchestrationError(
                "Execution routing returned an unexpected value",
                code="AGENT_ROUTING_CONTRACT_VIOLATION",
                details={"request_id": request.request_id},
            )
        return decision

    def _evaluate_policy(
        self,
        request: OrchestrationRequest,
        resolution: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
        route: AgentRouteDecision,
    ) -> OrchestrationPolicyDecision:
        decision = self._policy.evaluate(
            request=request,
            intent=resolution,
            context=context,
            domain=domain,
            route=route,
        )
        if not isinstance(decision, OrchestrationPolicyDecision):
            raise OrchestrationError(
                "Policy evaluation returned an unexpected value",
                code="ORCHESTRATION_POLICY_CONTRACT_VIOLATION",
                details={"request_id": request.request_id},
            )
        return decision

    # ── Terminal paths ───────────────────────────────────────────────────────

    def _clarification(
        self,
        request: OrchestrationRequest,
        resolution: IntentResolution,
        reason_codes: tuple[str, ...],
        *,
        domain: DomainRouteDecision | None = None,
    ) -> OrchestrationResult:
        return self._terminate(
            request=request,
            status=OrchestrationStatus.NEEDS_CLARIFICATION,
            intent=resolution.intent,
            domain=domain,
            route=AgentRouteDecision(route=ExecutionRoute.NONE),
            disposition=None,
            reason_codes=reason_codes,
            event_type=EVENT_ROUTED,
        )

    def _domain_block(
        self,
        request: OrchestrationRequest,
        resolution: IntentResolution,
        domain: DomainRouteDecision,
    ) -> OrchestrationResult:
        return self._terminate(
            request=request,
            status=OrchestrationStatus.BLOCKED,
            intent=resolution.intent,
            domain=domain,
            route=AgentRouteDecision(route=ExecutionRoute.NONE),
            disposition=PolicyDisposition.DENY,
            reason_codes=(REASON_DOMAIN_BLOCK, *domain.reason_codes),
            event_type=EVENT_BLOCKED,
        )

    def _terminal_policy(
        self,
        request: OrchestrationRequest,
        resolution: IntentResolution,
        domain: DomainRouteDecision,
        route: AgentRouteDecision,
        decision: OrchestrationPolicyDecision,
    ) -> OrchestrationResult:
        if decision.disposition is PolicyDisposition.DENY:
            status = OrchestrationStatus.BLOCKED
            event_type = EVENT_BLOCKED
        elif decision.disposition is PolicyDisposition.ESCALATE:
            status = OrchestrationStatus.ESCALATED
            event_type = EVENT_ESCALATED
        elif decision.disposition is PolicyDisposition.REQUIRE_APPROVAL:
            status = OrchestrationStatus.ROUTED
            event_type = EVENT_APPROVAL_REQUIRED
        else:
            status = (
                OrchestrationStatus.CANCELLED
                if resolution.intent is IntentKind.CANCELLATION
                else OrchestrationStatus.ROUTED
            )
            event_type = EVENT_ROUTED

        return self._terminate(
            request=request,
            status=status,
            intent=resolution.intent,
            domain=domain,
            route=route,
            disposition=decision.disposition,
            reason_codes=(*decision.reason_codes, *domain.reason_codes),
            event_type=event_type,
            approval_refs=tuple(
                dict.fromkeys((*decision.approval_refs, *domain.approval_refs))
            ),
        )

    def _terminate(
        self,
        *,
        request: OrchestrationRequest,
        status: OrchestrationStatus,
        intent: IntentKind,
        domain: DomainRouteDecision | None,
        route: AgentRouteDecision,
        disposition: PolicyDisposition | None,
        reason_codes: tuple[str, ...],
        event_type: str,
        approval_refs: tuple[str, ...] | None = None,
    ) -> OrchestrationResult:
        """Persist the terminal decision, emit the terminal event, return a result."""

        decision_id = f"{DECISION_ID_PREFIX}:{request.request_id}"
        trace_refs = () if domain is None else domain.trace_refs
        if approval_refs is None:
            approval_refs = () if domain is None else domain.approval_refs
        normalized_reasons = tuple(dict.fromkeys(reason_codes))

        record = OrchestrationDecisionRecord(
            decision_id=decision_id,
            request_id=request.request_id,
            session_id=request.session_id,
            channel=request.channel,
            intent=intent,
            primary_domain=None if domain is None else domain.primary_domain,
            supporting_domains=() if domain is None else domain.supporting_domains,
            execution_route=route.route,
            policy_disposition=disposition,
            selected_agent_id=route.agent_id,
            workflow_id=route.workflow_id,
            approval_refs=approval_refs,
            trace_refs=trace_refs,
            reason_codes=normalized_reasons,
        )
        self._persist(record, request)

        result = OrchestrationResult(
            request_id=request.request_id,
            status=status,
            intent=intent,
            primary_domain=record.primary_domain,
            supporting_domains=record.supporting_domains,
            profile_id=None if domain is None else domain.profile_id,
            route=route.route,
            agent_id=route.agent_id,
            workflow_id=route.workflow_id,
            approval_refs=approval_refs,
            decision_id=decision_id,
            trace_refs=trace_refs,
            reason_codes=normalized_reasons,
            error=None,
        )

        self._emit(
            event_type,
            request,
            status=status.value,
            intent=intent.value,
            route=route.route.value,
            decision_id=decision_id,
            primary_domain=record.primary_domain,
            supporting_domains=record.supporting_domains,
            agent_id=route.agent_id,
            workflow_id=route.workflow_id,
            approval_refs=approval_refs,
            policy_disposition=None if disposition is None else disposition.value,
            reason_codes=normalized_reasons,
        )
        return result

    # ── Phase 11.2-owned side effects ────────────────────────────────────────

    def _persist(
        self, record: OrchestrationDecisionRecord, request: OrchestrationRequest
    ) -> None:
        stored = self._decision_repository.save(record)
        if stored is None:
            raise OrchestrationError(
                "Decision persistence returned no record",
                code="DECISION_PERSISTENCE_ERROR",
                details={"decision_id": record.decision_id},
            )

    def _emit(
        self, event_type: str, request: OrchestrationRequest, **facts: object
    ) -> None:
        payload = {
            key: value
            for key, value in facts.items()
            if value is not None and value != ()
        }
        try:
            self._event_sink.emit(
                event_type, request_id=request.request_id, payload=payload
            )
        except Exception as error:
            raise OrchestrationError(
                "Required orchestration event emission failed",
                code=EVENT_EMISSION_FAILED,
                details={"request_id": request.request_id, "event_type": event_type},
            ) from error

    def _failed(
        self, request: OrchestrationRequest, error: OrchestrationError
    ) -> OrchestrationResult:
        """Return a safe failed result and emit the failure lifecycle event."""

        with contextlib.suppress(Exception):
            self._emit(
                EVENT_FAILED,
                request,
                error_code=error.code,
                error_category=error.category,
            )
        return OrchestrationResult(
            request_id=request.request_id,
            status=OrchestrationStatus.FAILED,
            reason_codes=(error.code,),
            error=error.to_error_result(),
        )
