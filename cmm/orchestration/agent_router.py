"""Phase 11.2 — canonical agent and execution-path routing.

The roadmap name ``AgentRouter`` is retained, but its Phase 11.2 responsibility
is execution-path selection, not agent scoring.  It chooses one of the frozen
:class:`~cmm.orchestration.contracts.ExecutionRoute` values and, when the route
is ``AUTONOMOUS_AGENT``, it delegates the actual agent selection to the
canonical ``AgentRegistryService`` / ``AgentResolver``.

This module therefore:

* implements no agent registry, no compatibility rule and no agent scoring;
* never fabricates an agent identifier — when the canonical registry cannot
  select a compatible agent, the route becomes ``HUMAN_ESCALATION``;
* never calls Agent Runtime execution: it returns a route decision for a later
  canonical owner to consume.

The baseline route matrix is deterministic and explicit, and it is the policy
layer — never this router — that may narrow or escalate a proposed route.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from cmm.agent_runtime.agent_registry_service import AgentRegistryService
from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationRequest,
    ResolvedContext,
)
from cmm.orchestration.errors import AgentRoutingError

__all__ = [
    "AgentRouter",
    "CanonicalAgentRouter",
]

#: The frozen Phase 11.2 execution-path matrix.
ROUTE_BY_INTENT: dict[IntentKind, ExecutionRoute] = {
    IntentKind.QUESTION: ExecutionRoute.DIRECT_RESPONSE,
    IntentKind.REFLECTION: ExecutionRoute.DIRECT_RESPONSE,
    IntentKind.COMMAND: ExecutionRoute.OPERATION,
    IntentKind.WORKFLOW_REQUEST: ExecutionRoute.WORKFLOW,
    IntentKind.GOAL: ExecutionRoute.AUTONOMOUS_AGENT,
    IntentKind.INFORMATION_UPDATE: ExecutionRoute.OPERATION,
    # An approval response applies an already-recorded decision through the
    # canonical approval/operation seam.
    IntentKind.APPROVAL_RESPONSE: ExecutionRoute.OPERATION,
    # Continuation and cancellation target the canonical workflow control seam.
    IntentKind.CONTINUATION: ExecutionRoute.WORKFLOW,
    IntentKind.CANCELLATION: ExecutionRoute.WORKFLOW,
    # Phase 11.2 owns no configuration authority, so a configuration change is
    # escalated rather than silently applied.
    IntentKind.CONFIGURATION_CHANGE: ExecutionRoute.HUMAN_ESCALATION,
    IntentKind.UNKNOWN: ExecutionRoute.NONE,
}

#: Structured request keys that carry an explicit workflow reference.
_WORKFLOW_REFERENCE_KEYS: tuple[tuple[str, str | None], ...] = (
    ("workflow_request", "workflow_id"),
    ("continuation_id", None),
    ("cancel_target_id", None),
)


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _workflow_reference(request: OrchestrationRequest) -> str | None:
    """Return the explicit canonical workflow reference, if the request has one."""

    for container, nested_key in _WORKFLOW_REFERENCE_KEYS:
        if nested_key is None:
            direct = _text(request.input.get(container))
            if direct is not None:
                return direct
            continue
        nested = request.input.get(container)
        if isinstance(nested, Mapping):
            value = _text(nested.get(nested_key))
            if value is not None:
                return value
    return None


@runtime_checkable
class AgentRouter(Protocol):
    """Execution-path selection boundary.

    The role method is named after the role on purpose: a runtime Protocol check
    verifies member presence rather than callable signature, so two orchestration
    roles that both exposed a generic ``route`` would satisfy each other and a
    cross-wired graph would survive composition and fail only on the first real
    request.
    """

    def route_agent(
        self,
        *,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
    ) -> AgentRouteDecision: ...


class CanonicalAgentRouter:
    """Deterministic execution-path router delegating agent selection canonically.

    Agent compatibility and selection stay owned by the canonical
    :class:`~cmm.agent_runtime.agent_registry_service.AgentRegistryService`, and
    this router accepts no other agent-selection authority: a noncanonical object
    that merely exposes ``resolve_agent`` is rejected at construction, so it can
    never fabricate an agent identifier through this boundary.
    """

    def __init__(self, *, registry_service: AgentRegistryService | None = None) -> None:
        if registry_service is not None and not isinstance(
            registry_service, AgentRegistryService
        ):
            raise TypeError(
                "registry_service must be the canonical "
                f"{AgentRegistryService.__name__}, "
                f"got {type(registry_service).__name__}"
            )
        self._registry_service = registry_service

    # ── Public API ───────────────────────────────────────────────────────────

    def route_agent(
        self,
        *,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
    ) -> AgentRouteDecision:
        """Return the bounded execution route for the resolved request."""

        if not isinstance(request, OrchestrationRequest):
            raise TypeError(
                f"request must be an OrchestrationRequest, got {type(request).__name__}"
            )
        if not isinstance(intent, IntentResolution):
            raise TypeError(
                f"intent must be an IntentResolution, got {type(intent).__name__}"
            )
        if not isinstance(context, ResolvedContext):
            raise TypeError(
                f"context must be a ResolvedContext, got {type(context).__name__}"
            )
        if not isinstance(domain, DomainRouteDecision):
            raise TypeError(
                f"domain must be a DomainRouteDecision, got {type(domain).__name__}"
            )

        route = ROUTE_BY_INTENT.get(intent.intent, ExecutionRoute.NONE)
        reason_codes = [f"AGENT_ROUTE_{intent.intent.value.upper()}"]

        if route is ExecutionRoute.WORKFLOW:
            return AgentRouteDecision(
                route=route,
                workflow_id=_workflow_reference(request),
                reason_codes=tuple(reason_codes),
            )

        if route is ExecutionRoute.AUTONOMOUS_AGENT:
            return self._route_autonomous(request, reason_codes)

        return AgentRouteDecision(route=route, reason_codes=tuple(reason_codes))

    # ── Canonical agent delegation ───────────────────────────────────────────

    def _route_autonomous(
        self, request: OrchestrationRequest, reason_codes: list[str]
    ) -> AgentRouteDecision:
        """Delegate agent selection to the canonical registry service."""

        if self._registry_service is None:
            reason_codes.append("AGENT_ROUTING_REGISTRY_UNAVAILABLE")
            return AgentRouteDecision(
                route=ExecutionRoute.HUMAN_ESCALATION,
                reason_codes=tuple(reason_codes),
            )

        requirement = self._requirement(request)
        if requirement is None:
            # Phase 11.2 never invents an agent requirement: without declared
            # capability evidence the autonomous route escalates.
            reason_codes.append("AGENT_ROUTING_REQUIREMENT_MISSING")
            return AgentRouteDecision(
                route=ExecutionRoute.HUMAN_ESCALATION,
                reason_codes=tuple(reason_codes),
            )

        try:
            resolution = self._registry_service.resolve_agent(requirement)
        except Exception as error:
            raise AgentRoutingError(
                "Canonical agent resolution failed",
                details={"request_id": request.request_id},
            ) from error

        selected = resolution.selected
        if selected is None:
            reason_codes.append("AGENT_ROUTING_NO_COMPATIBLE_AGENT")
            return AgentRouteDecision(
                route=ExecutionRoute.HUMAN_ESCALATION,
                reason_codes=tuple(reason_codes),
            )

        reason_codes.append("AGENT_ROUTING_DELEGATED")
        return AgentRouteDecision(
            route=ExecutionRoute.AUTONOMOUS_AGENT,
            agent_id=selected.agent_id,
            agent_version=selected.version.canonical(),
            reason_codes=tuple(reason_codes),
        )

    @staticmethod
    def _requirement(request: OrchestrationRequest) -> Any | None:
        """Build the canonical agent requirement from declared capability evidence."""

        capabilities = tuple(request.requested_capabilities)
        if not capabilities:
            return None

        from cmm.agent_runtime.agent_registry_contracts import AgentRequirement

        try:
            return AgentRequirement(required_capabilities=capabilities)
        except Exception as error:
            raise AgentRoutingError(
                "Canonical agent requirement could not be constructed",
                details={"request_id": request.request_id},
            ) from error
