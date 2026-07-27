"""Phase 9.23 – Agent Registry & Factory Enumerations.

Typed enumerations for the Agent Registry & Factory subsystem.

The enums cover:
* AgentKind: functional category of an agent.
* AgentLifecycle: registration / lifecycle states.
* AgentAvailability: current availability status.
* AgentCapabilityKind: type of declared capability.
* AgentFactoryScope: lifetime scope of a factory instance.
* AgentResolutionStrategy: strategy used to resolve a requirement.
* AgentCompatibilityStatus: structured compatibility result.
* AgentRegistrationStatus: explicit registration status codes.
* AgentVersionStatus: explicit version status codes.

The naming follows the conventions already in use by Agent Runtime
(``str, Enum`` mixins for stable string values).
"""

from __future__ import annotations

from enum import Enum


class AgentKind(str, Enum):
    """Functional category of a registered agent."""

    GENERAL = "general"
    DOMAIN = "domain"
    WORKFLOW = "workflow"
    TOOL = "tool"
    COORDINATOR = "coordinator"
    REVIEWER = "reviewer"
    PLANNER = "planner"
    EXECUTOR = "executor"
    OBSERVER = "observer"


class AgentLifecycle(str, Enum):
    """Registration / lifecycle states for an agent version.

    A registered descriptor carries exactly one of these values.
    Only ``ACTIVE`` is resolvable by default; ``EXPERIMENTAL`` requires
    opt-in; ``DEPRECATED`` is not selectable by default; ``RETIRED`` and
    ``DISABLED`` are never resolvable.
    """

    EXPERIMENTAL = "experimental"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    DISABLED = "disabled"


class AgentAvailability(str, Enum):
    """Current availability status of a registered agent.

    This is a *declared* status, not a runtime probe. It must reflect
    reality (i.e. cannot be set to ``AVAILABLE`` if the factory is
    missing or disabled).
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class AgentCapabilityKind(str, Enum):
    """Functional type of a declared capability."""

    INPUT = "input"
    OUTPUT = "output"
    OPERATION = "operation"
    KNOWLEDGE = "knowledge"
    TOOL = "tool"
    PERMISSION = "permission"
    COGNITIVE = "cognitive"
    COMPOSITE = "composite"


class AgentFactoryScope(str, Enum):
    """Lifetime scope of a factory-created instance.

    * ``TRANSIENT`` – new instance per call.
    * ``REQUEST`` – one instance per request/session, may be cached.
    * ``RUN`` – one instance per run id; requires ``run_id``.
    * ``SINGLETON`` – global; only allowed if the factory is
      thread-safe and explicitly declares so.
    """

    TRANSIENT = "transient"
    REQUEST = "request"
    RUN = "run"
    SINGLETON = "singleton"


class AgentResolutionStrategy(str, Enum):
    """Strategy used by the resolver to pick a candidate.

    The default strategy is ``BEST_MATCH`` and is deterministic.
    """

    EXACT = "exact"
    BEST_MATCH = "best_match"
    HIGHEST_PRIORITY = "highest_priority"
    HIGHEST_VERSION = "highest_version"
    CAPABILITY_MATCH = "capability_match"


class AgentCompatibilityStatus(str, Enum):
    """Structured result of the compatibility check."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE_LIFECYCLE = "incompatible_lifecycle"
    INCOMPATIBLE_VERSION = "incompatible_version"
    INCOMPATIBLE_CAPABILITY = "incompatible_capability"
    INCOMPATIBLE_OPERATION = "incompatible_operation"
    INCOMPATIBLE_PERMISSION = "incompatible_permission"
    INCOMPATIBLE_COMPONENT = "incompatible_component"
    INCOMPATIBLE_RUNTIME = "incompatible_runtime"
    EXCLUDED = "excluded"
    FACTORY_UNAVAILABLE = "factory_unavailable"


class AgentRegistrationStatus(str, Enum):
    """Explicit registration status codes returned by the registry."""

    REGISTERED = "registered"
    UPDATED = "updated"
    REPLACED = "replaced"
    REJECTED_CONFLICT = "rejected_conflict"
    REJECTED_INVALID = "rejected_invalid"
    NOT_FOUND = "not_found"
    REMOVED = "removed"


class AgentVersionStatus(str, Enum):
    """Explicit version status codes for registered descriptors."""

    ACTIVE = "active"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    DISABLED = "disabled"


__all__ = [
    "AgentAvailability",
    "AgentCapabilityKind",
    "AgentCompatibilityStatus",
    "AgentFactoryScope",
    "AgentKind",
    "AgentLifecycle",
    "AgentRegistrationStatus",
    "AgentResolutionStrategy",
    "AgentVersionStatus",
]
