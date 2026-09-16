"""Phase 11.2 — restrictive orchestration policy.

``OrchestrationPolicy`` evaluates whether a proposed execution route may
proceed.  It is deliberately **not** a new authorization system, policy
language, policy registry or policy database: it is a small deterministic
coordinator over evidence that canonical owners already produced.

The governing invariant is monotonic restriction:

* canonical ``DENY`` can never become an orchestration ``ALLOW``;
* canonical ``REQUIRE_APPROVAL`` can never become a silent ``ALLOW``;
* supporting-domain evidence can never widen a primary restriction;
* a side-effecting route without canonical authority evidence escalates
  instead of being allowed by default.

Precedence is frozen:

``canonical deny``
    -> ``DENY``
``canonical approval required``
    -> ``REQUIRE_APPROVAL``
``unsupported / high-risk / missing critical authority``
    -> ``ESCALATE``
``otherwise``
    -> ``ALLOW_ROUTE``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationPolicyDecision,
    OrchestrationRequest,
    PolicyDisposition,
    ResolvedContext,
)

__all__ = [
    "DefaultOrchestrationPolicy",
    "OrchestrationConfiguration",
    "OrchestrationPolicy",
]

#: Canonical permission dispositions, as published by the domain route.
CANONICAL_DENY = "deny"
CANONICAL_ALLOW = "allow"
CANONICAL_APPROVAL_REQUIRED = "approval_required"

#: Routes that can produce a downstream side effect, so they require explicit
#: canonical authority evidence before they may be allowed.
SIDE_EFFECTING_ROUTES = frozenset(
    {
        ExecutionRoute.OPERATION,
        ExecutionRoute.WORKFLOW,
        ExecutionRoute.AUTONOMOUS_AGENT,
    }
)


def _channels(values: object) -> tuple[OrchestrationChannel, ...]:
    if isinstance(values, (str, bytes | bytearray)) or not isinstance(
        values, (tuple, list)
    ):
        raise TypeError("allowed_channels must be a sequence of channels")

    normalized: list[OrchestrationChannel] = []
    for value in values:
        if not isinstance(value, OrchestrationChannel):
            raise TypeError("allowed_channels must contain OrchestrationChannel values")
        if value in normalized:
            raise ValueError("allowed_channels must not contain duplicates")
        normalized.append(value)
    if not normalized:
        raise ValueError("allowed_channels must not be empty")
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class OrchestrationConfiguration:
    """Small immutable Phase 11.2 orchestration configuration.

    This is not the Phase 11.12 Configuration Center and it carries no secrets.
    Phase 11.2 keeps decision recording and event emission unconditional; the
    flags exist so a composition can state that requirement explicitly, and
    disabling either one fails closed instead of silently weakening the
    fail-closed baseline.
    """

    allowed_channels: tuple[OrchestrationChannel, ...] = field(
        default_factory=lambda: (
            OrchestrationChannel.CONVERSATION,
            OrchestrationChannel.CLI,
            OrchestrationChannel.INTERNAL,
            OrchestrationChannel.API,
        )
    )
    decision_recording_required: bool = True
    event_emission_required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_channels", _channels(self.allowed_channels))
        for name in ("decision_recording_required", "event_emission_required"):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be a bool")
            if not value:
                raise ValueError(
                    f"{name} cannot be disabled in Phase 11.2: safe decision "
                    "recording and safe event emission are unconditional"
                )

    def allows(self, channel: OrchestrationChannel) -> bool:
        """Return whether *channel* is enabled by this configuration."""

        return channel in self.allowed_channels


@runtime_checkable
class OrchestrationPolicy(Protocol):
    """Restrictive orchestration policy boundary."""

    def evaluate(
        self,
        *,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
        route: AgentRouteDecision,
    ) -> OrchestrationPolicyDecision: ...


class DefaultOrchestrationPolicy:
    """Deterministic restrictive policy over canonical evidence."""

    def __init__(
        self, *, configuration: OrchestrationConfiguration | None = None
    ) -> None:
        self._configuration = configuration or OrchestrationConfiguration()

    @property
    def configuration(self) -> OrchestrationConfiguration:
        return self._configuration

    def evaluate(
        self,
        *,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
        route: AgentRouteDecision,
    ) -> OrchestrationPolicyDecision:
        """Return the restrictive disposition for the proposed route."""

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
        if not isinstance(route, AgentRouteDecision):
            raise TypeError(
                f"route must be an AgentRouteDecision, got {type(route).__name__}"
            )

        disposition = domain.permission_disposition
        reason_codes: list[str] = []

        # 1. Canonical denial is terminal and can never be widened.
        if disposition == CANONICAL_DENY:
            return OrchestrationPolicyDecision(
                disposition=PolicyDisposition.DENY,
                reason_codes=("POLICY_CANONICAL_DENY",),
            )

        # 2. A canonical approval requirement is preserved, never silently allowed.
        if disposition == CANONICAL_APPROVAL_REQUIRED:
            return OrchestrationPolicyDecision(
                disposition=PolicyDisposition.REQUIRE_APPROVAL,
                approval_refs=domain.approval_refs,
                reason_codes=("POLICY_APPROVAL_REQUIRED",),
            )

        # 3. A channel that the composition does not enable is denied.
        if not self._configuration.allows(request.channel):
            return OrchestrationPolicyDecision(
                disposition=PolicyDisposition.DENY,
                reason_codes=(
                    "POLICY_CHANNEL_NOT_ALLOWED",
                    f"POLICY_CHANNEL_{request.channel.value.upper()}",
                ),
            )

        # 4. A route that already requires human judgement escalates.
        if route.route is ExecutionRoute.HUMAN_ESCALATION:
            return OrchestrationPolicyDecision(
                disposition=PolicyDisposition.ESCALATE,
                reason_codes=("POLICY_ROUTE_ESCALATION",),
            )

        # 5. A route that no canonical path can serve is unsupported.
        if route.route is ExecutionRoute.NONE:
            return OrchestrationPolicyDecision(
                disposition=PolicyDisposition.ESCALATE,
                reason_codes=("POLICY_ROUTE_UNSUPPORTED",),
            )

        # 6. A side-effecting route needs explicit canonical authority evidence.
        if route.route in SIDE_EFFECTING_ROUTES and disposition != CANONICAL_ALLOW:
            return OrchestrationPolicyDecision(
                disposition=PolicyDisposition.ESCALATE,
                reason_codes=("POLICY_MISSING_AUTHORITY_EVIDENCE",),
            )

        reason_codes.append("POLICY_ALLOWED")
        if disposition == CANONICAL_ALLOW:
            reason_codes.append("POLICY_CANONICAL_ALLOW")
        return OrchestrationPolicyDecision(
            disposition=PolicyDisposition.ALLOW_ROUTE,
            reason_codes=tuple(reason_codes),
        )
