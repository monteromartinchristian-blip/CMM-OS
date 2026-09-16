"""Phase 11.3 — Application Backend — transport-neutral public application core.

This package owns the public application semantics of CMM OS: the versioned
public contracts, the safe public error model, the session/request/capability/
health application services, the narrowly scoped idempotency seam and the one
canonical public entrypoint ``ApplicationGateway``.

It owns no canonical subsystem authority.  Domain, agent, provider, workflow,
operation, execution, validation, memory, knowledge, session and orchestration
ownership all stay with their canonical packages; this layer adapts public
requests to them and projects safe public results.

The package is transport-neutral: it never imports a web framework and performs
no direct external network I/O.  The HTTP/OpenAPI/SSE adapter lives in
``cmm.api``.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    COMMAND_OPERATIONS,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    MAX_IDENTIFIER_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_METADATA_DEPTH,
    MAX_METADATA_ITEMS,
    MAX_STRING_LENGTH,
    QUERY_OPERATIONS,
    ApplicationCancellationRequest,
    ApplicationCapability,
    ApplicationCommand,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationHealth,
    ApplicationMessage,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationRequest,
    ApplicationResponse,
    ApplicationSession,
    ApplicationStatus,
    ApplicationStreamEvent,
    CapabilityStatus,
    StreamEventKind,
)

__all__ = [
    "APPLICATION_API_VERSION",
    "COMMAND_OPERATIONS",
    "MAX_IDEMPOTENCY_KEY_LENGTH",
    "MAX_IDENTIFIER_LENGTH",
    "MAX_MESSAGE_LENGTH",
    "MAX_METADATA_DEPTH",
    "MAX_METADATA_ITEMS",
    "MAX_STRING_LENGTH",
    "QUERY_OPERATIONS",
    "ApplicationCancellationRequest",
    "ApplicationCapability",
    "ApplicationCommand",
    "ApplicationError",
    "ApplicationErrorCode",
    "ApplicationHealth",
    "ApplicationMessage",
    "ApplicationOperation",
    "ApplicationQuery",
    "ApplicationRequest",
    "ApplicationResponse",
    "ApplicationSession",
    "ApplicationStatus",
    "ApplicationStreamEvent",
    "CapabilityStatus",
    "StreamEventKind",
]
