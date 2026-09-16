"""Phase 11.2 — CMM OS orchestration layer.

This package owns the global request **coordination** boundary.  It coordinates
already-authoritative canonical subsystems (Domain Intelligence, Agent Runtime,
sessions, workflows, execution, validation); it never becomes the owner of the
subsystems it coordinates and never executes the downstream vertical.

Direction of dependency::

    cmm.orchestration  ->  cmm.platform + canonical subsystem packages

Canonical subsystem packages never import ``cmm.orchestration``.

Importing this package performs no registration, no repository mutation, no
event emission, no file I/O and no canonical subsystem construction.
"""

from __future__ import annotations

from cmm.orchestration.agent_router import (
    AgentRouter,
    CanonicalAgentRouter,
)
from cmm.orchestration.context import (
    ContextReferenceReader,
    ContextResolver,
    DefaultContextResolver,
)
from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationDecisionRecord,
    OrchestrationPolicyDecision,
    OrchestrationRequest,
    OrchestrationResult,
    OrchestrationStatus,
    PolicyDisposition,
    ResolvedContext,
)
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
    OrchestrationDecisionRepository,
)
from cmm.orchestration.domain_router import (
    CanonicalDomainRouter,
    DomainRouter,
)
from cmm.orchestration.errors import (
    AgentRoutingError,
    ContextResolutionError,
    DecisionPersistenceError,
    DomainRoutingError,
    IntentResolutionError,
    OrchestrationError,
    OrchestrationPolicyError,
)
from cmm.orchestration.events import (
    ALLOWED_EVENT_TYPES,
    OrchestrationEventSink,
    RecordedOrchestrationEvent,
    RecordingOrchestrationEventSink,
    validate_orchestration_event,
)
from cmm.orchestration.intent import (
    DeterministicIntentResolver,
    IntentResolver,
)
from cmm.orchestration.policy import (
    DefaultOrchestrationPolicy,
    OrchestrationConfiguration,
    OrchestrationPolicy,
)

__all__ = [
    "ALLOWED_EVENT_TYPES",
    "AgentRouteDecision",
    "AgentRouter",
    "AgentRoutingError",
    "CanonicalAgentRouter",
    "CanonicalDomainRouter",
    "ContextReferenceReader",
    "ContextResolutionError",
    "ContextResolver",
    "DecisionPersistenceError",
    "DefaultContextResolver",
    "DefaultOrchestrationPolicy",
    "DeterministicIntentResolver",
    "DomainRouteDecision",
    "DomainRouter",
    "DomainRoutingError",
    "ExecutionRoute",
    "InMemoryOrchestrationDecisionRepository",
    "IntentKind",
    "IntentResolution",
    "IntentResolutionError",
    "IntentResolver",
    "OrchestrationChannel",
    "OrchestrationConfiguration",
    "OrchestrationDecisionRecord",
    "OrchestrationDecisionRepository",
    "OrchestrationError",
    "OrchestrationEventSink",
    "OrchestrationPolicy",
    "OrchestrationPolicyDecision",
    "OrchestrationPolicyError",
    "OrchestrationRequest",
    "OrchestrationResult",
    "OrchestrationStatus",
    "PolicyDisposition",
    "RecordedOrchestrationEvent",
    "RecordingOrchestrationEventSink",
    "ResolvedContext",
    "validate_orchestration_event",
]
