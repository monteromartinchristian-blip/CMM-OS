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
from cmm.orchestration.errors import (
    AgentRoutingError,
    ContextResolutionError,
    DecisionPersistenceError,
    DomainRoutingError,
    IntentResolutionError,
    OrchestrationError,
    OrchestrationPolicyError,
)

__all__ = [
    "AgentRouteDecision",
    "AgentRoutingError",
    "ContextResolutionError",
    "DecisionPersistenceError",
    "DomainRouteDecision",
    "DomainRoutingError",
    "ExecutionRoute",
    "IntentKind",
    "IntentResolution",
    "IntentResolutionError",
    "OrchestrationChannel",
    "OrchestrationDecisionRecord",
    "OrchestrationError",
    "OrchestrationPolicyDecision",
    "OrchestrationPolicyError",
    "OrchestrationRequest",
    "OrchestrationResult",
    "OrchestrationStatus",
    "PolicyDisposition",
    "ResolvedContext",
]
