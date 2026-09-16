"""Phase 11.3 — HTTP/OpenAPI/SSE adapter for the public application boundary.

This package is an adapter and owns no business, domain, agent, workflow,
operation, execution, validation, session or provider authority.  It adapts HTTP
transport concerns — path/method, transport DTO parsing, application service
invocation, public response serialization, HTTP status mapping and SSE
adaptation — onto ``cmm.application``.

It must never import canonical internal owners directly; it reaches the platform
only through the application layer.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from cmm.api.errors import (
    REASON_INVALID_IDEMPOTENCY_KEY,
    REASON_INVALID_REQUEST_BODY,
    REASON_INVALID_REQUEST_CONTRACT,
    REASON_INVALID_REQUEST_ID,
    http_status_for,
    invalid_request_error,
    status_code_for,
    success_status_code,
)
from cmm.api.models import (
    ApiVersion,
    ApplicationCapabilityModel,
    ApplicationErrorModel,
    ApplicationHealthModel,
    ApplicationResponseModel,
    ApplicationSessionModel,
    CreateSessionBody,
    MessageBody,
    capability_model_from,
    error_model_from,
    health_model_from,
    response_model_from,
    session_model_from,
)

__all__ = [
    "REASON_INVALID_IDEMPOTENCY_KEY",
    "REASON_INVALID_REQUEST_BODY",
    "REASON_INVALID_REQUEST_CONTRACT",
    "REASON_INVALID_REQUEST_ID",
    "ApiVersion",
    "ApplicationCapabilityModel",
    "ApplicationErrorModel",
    "ApplicationHealthModel",
    "ApplicationResponseModel",
    "ApplicationSessionModel",
    "CreateSessionBody",
    "MessageBody",
    "capability_model_from",
    "error_model_from",
    "health_model_from",
    "http_status_for",
    "invalid_request_error",
    "response_model_from",
    "session_model_from",
    "status_code_for",
    "success_status_code",
]
