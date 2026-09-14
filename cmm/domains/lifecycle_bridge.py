"""Phase 10.33 — Domain Lifecycle Event Bridge.

Orchestrates Domain Intelligence lifecycle events and publishes them to the
Kernel Event boundary via DomainKernelEventPublisher without contaminating
pure deterministic engines.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from cmm.domains.event_adapters import (
    _ensure_domain_id,
    adapt_conflict_detected,
    adapt_conflict_resolution,
    adapt_resolution_result,
    adapt_resolution_started,
)
from cmm.domains.event_factory import DomainEventFactory
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.identifiers import DomainId
from kernel.events.event import Event

if TYPE_CHECKING:
    from cmm.domains.conflict_resolution import DomainConflictResolver
    from cmm.domains.conflict_resolution_contracts import (
        DomainConflictCase,
        DomainConflictResolution,
        DomainConflictResolutionPolicy,
    )
    from cmm.domains.resolution_contracts import DomainResolutionContext
    from cmm.domains.resolver import DomainResolver
    from cmm.domains.resolver_contracts import DomainResolutionResult


class DomainLifecycleEventBridge:
    """Orchestration bridge connecting domain lifecycles to Kernel event publication."""

    def __init__(
        self,
        publisher: DomainKernelEventPublisher | None = None,
        factory: DomainEventFactory | None = None,
    ) -> None:
        """Initialize the lifecycle bridge.

        Args:
            publisher: DomainKernelEventPublisher instance (or default).
            factory: DomainEventFactory instance (or default).
        """
        self._publisher = publisher or DomainKernelEventPublisher()
        self._factory = factory or DomainEventFactory()

    @property
    def publisher(self) -> DomainKernelEventPublisher:
        """Return the underlying publisher."""
        return self._publisher

    @property
    def factory(self) -> DomainEventFactory:
        """Return the underlying factory."""
        return self._factory

    def emit_resolution_started(
        self,
        context_id: str,
        domain_id: DomainId | str | None = None,
        actor: str = "system",
    ) -> Event:
        """Adapt and publish a domain.resolution.started event."""
        evt = adapt_resolution_started(
            context_id=context_id,
            domain_id=domain_id,
            actor=actor,
            factory=self._factory,
        )
        return self._publisher.publish(evt)

    def emit_resolution_result(
        self,
        result: DomainResolutionResult,
        actor: str = "system",
    ) -> Event:
        """Adapt and publish a resolution result (completed or ambiguous)."""
        evt = adapt_resolution_result(
            result=result,
            actor=actor,
            factory=self._factory,
        )
        return self._publisher.publish(evt)

    def emit_conflict_detected(
        self,
        case: DomainConflictCase,
        actor: str = "system",
    ) -> Event:
        """Adapt and publish a domain.conflict.detected event."""
        evt = adapt_conflict_detected(
            case=case,
            actor=actor,
            factory=self._factory,
        )
        return self._publisher.publish(evt)

    def emit_conflict_resolution(
        self,
        resolution: DomainConflictResolution,
        primary_domain: DomainId | str,
        actor: str = "system",
    ) -> Event | None:
        """Adapt and publish a domain.conflict.resolved event if genuinely resolved."""
        evt = adapt_conflict_resolution(
            resolution=resolution,
            primary_domain=primary_domain,
            actor=actor,
            factory=self._factory,
        )
        if evt is not None:
            return self._publisher.publish(evt)
        return None

    def resolve_with_events(
        self,
        resolver: DomainResolver,
        context: DomainResolutionContext,
        actor: str = "system",
    ) -> DomainResolutionResult:
        """Call-around pattern for domain resolution with lifecycle events."""
        self.emit_resolution_started(context_id=context.id, actor=actor)
        result = resolver.resolve(context)
        self.emit_resolution_result(result=result, actor=actor)
        return result

    def resolve_conflict_with_events(
        self,
        resolver: DomainConflictResolver,
        case: DomainConflictCase,
        primary_domain: DomainId | str,
        policy: DomainConflictResolutionPolicy | None = None,
        actor: str = "system",
        *,
        highest_risk_domain: DomainId | None = None,
        evidence_scores: Mapping[str, float] | None = None,
        reliability_scores: Mapping[str, float] | None = None,
        temporal_scores: Mapping[str, float] | None = None,
    ) -> DomainConflictResolution:
        """Call-around pattern for conflict resolution with lifecycle events."""
        self.emit_conflict_detected(case=case, actor=actor)
        validated_primary = _ensure_domain_id(primary_domain)
        resolution = resolver.resolve(
            case,
            policy=policy,
            primary_domain=validated_primary,
            highest_risk_domain=highest_risk_domain,
            evidence_scores=evidence_scores,
            reliability_scores=reliability_scores,
            temporal_scores=temporal_scores,
        )
        self.emit_conflict_resolution(
            resolution=resolution,
            primary_domain=validated_primary,
            actor=actor,
        )
        return resolution
