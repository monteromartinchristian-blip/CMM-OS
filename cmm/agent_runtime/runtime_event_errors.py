"""Phase 9.20 – Runtime Event Bus Errors.

Defines error hierarchy for the Agent Runtime Event Bus.
"""

from __future__ import annotations


class AgentRuntimeEventError(Exception):
    """Base error for all Runtime Event Bus operations."""


class AgentRuntimeEventContractError(AgentRuntimeEventError, ValueError):
    """Raised when an event contract is invalid or violates invariants."""


class AgentRuntimeEventRegistryError(AgentRuntimeEventError, ValueError):
    """Raised when event registry operations fail."""


class AgentRuntimeEventDuplicateError(AgentRuntimeEventError, ValueError):
    """Raised when a duplicate event is detected."""


class AgentRuntimeEventUnknownTypeError(AgentRuntimeEventContractError):
    """Raised when an unknown event type is used."""


class AgentRuntimeEventSerializationError(AgentRuntimeEventError, ValueError):
    """Raised when event serialization or deserialization fails."""


class AgentRuntimeEventValidationError(AgentRuntimeEventError, ValueError):
    """Raised when event validation fails."""


class AgentRuntimeEventBusClosedError(AgentRuntimeEventError, RuntimeError):
    """Raised when publishing to a closed event bus."""


class AgentRuntimeEventQueueFullError(AgentRuntimeEventError, RuntimeError):
    """Raised when the event queue is full and backpressure is active."""


class AgentRuntimeEventDeliveryError(AgentRuntimeEventError, RuntimeError):
    """Raised when event delivery to a handler fails."""


class AgentRuntimeEventReplayError(AgentRuntimeEventError, RuntimeError):
    """Raised when event replay fails."""


class AgentRuntimeEventPermissionError(AgentRuntimeEventError, PermissionError):
    """Raised when event permissions are insufficient."""


class AgentRuntimeEventSensitivityError(AgentRuntimeEventError, ValueError):
    """Raised when event sensitivity constraints are violated."""


class AgentRuntimeEventDeadLetterQueueError(AgentRuntimeEventError, RuntimeError):
    """Raised when dead letter queue operations fail."""


class AgentRuntimeEventRepositoryError(AgentRuntimeEventError, RuntimeError):
    """Raised when event repository operations fail."""


class AgentRuntimeEventIdentityConflictError(AgentRuntimeEventRepositoryError):
    """Raised when one event ID is reused with materially different content.

    Phase 11.22 deduplication is identity based *and* content bound: an exact
    repeat of an already-persisted event is an idempotent duplicate, while the
    same event ID carrying different canonical content is an identity conflict.
    A conflict fails closed and mutates no stored record.
    """


class AgentRuntimeEventPersistenceCorruptionError(AgentRuntimeEventRepositoryError):
    """Raised when stored event evidence cannot be trusted.

    Corrupt, malformed, truncated or unsupported persisted records fail closed
    rather than being silently skipped or repaired.
    """


class AgentRuntimeEventRetryExhaustedError(AgentRuntimeEventDeliveryError):
    """Raised when a subscriber delivery exhausts its bounded attempts."""


class AgentRuntimeEventReplayDeniedError(AgentRuntimeEventReplayError):
    """Raised when replay is attempted for a subscriber that did not opt in."""


class AgentRuntimeEventTraceSubscriberError(AgentRuntimeEventError, RuntimeError):
    """Raised when the trace subscriber encounters an error."""
