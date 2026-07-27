"""Phase 9.21 – Agent Runtime API Middleware.

Ordered middleware chain for the Agent Runtime API.
Each middleware executes in deterministic order: before handler, then after handler, then on errors.
No middleware may bypass authorization or expose sensitive data.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import replace as dataclasses_replace
from typing import Any, ClassVar

from cmm.agent_runtime.agent_runtime_api_contracts import (
    AgentRuntimeApiContext,
    AgentRuntimeApiError,
    AgentRuntimeApiRequest,
    AgentRuntimeApiResponse,
)
from cmm.agent_runtime.agent_runtime_api_enums import (
    AgentRuntimeApiStatus,
)
from cmm.agent_runtime.agent_runtime_api_errors import (
    AgentRuntimeApiException,
    AgentRuntimeApiPermissionError,
    AgentRuntimeApiValidationError,
)
from cmm.agent_runtime.agent_runtime_api_router import (
    AgentRuntimeApiMiddleware,
)

# ── RequestIdMiddleware ─────────────────────────────────────────────────────


class RequestIdMiddleware(AgentRuntimeApiMiddleware):
    """Ensures every request has a request_id."""

    def forward(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
    ) -> tuple[AgentRuntimeApiRequest, AgentRuntimeApiContext]:
        rid = request.request_id or str(uuid.uuid4())
        # Create a new request with the request_id
        object.__setattr__(request, "request_id", rid)
        return request, context


# ── AuthenticationContextMiddleware ──────────────────────────────────────────


class AuthenticationContextMiddleware(AgentRuntimeApiMiddleware):
    """Validates authentication context is present and valid."""

    def forward(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
    ) -> tuple[AgentRuntimeApiRequest, AgentRuntimeApiContext]:
        if not context.actor.strip():
            raise AgentRuntimeApiPermissionError("Authentication context required")
        return request, context


# ── PermissionMiddleware ────────────────────────────────────────────────────


class PermissionMiddleware(AgentRuntimeApiMiddleware):
    """Validates that the actor has required permissions for the operation.

    Cannot be bypassed.
    """

    REQUIRED_PERMISSIONS: ClassVar[dict[str, list[str]]] = {
        "goal.create": ["goal:write"],
        "goal.get": ["goal:read"],
        "goal.list": ["goal:read"],
        "goal.update": ["goal:write"],
        "goal.prioritize": ["goal:write"],
        "goal.pause": ["goal:write"],
        "goal.resume": ["goal:write"],
        "goal.cancel": ["goal:write"],
        "run.start": ["run:write"],
        "run.get": ["run:read"],
        "run.list": ["run:read"],
        "run.pause": ["run:write"],
        "run.resume": ["run:write"],
        "run.cancel": ["run:write"],
        "approval.list": ["approval:read"],
        "approval.get": ["approval:read"],
        "approval.approve": ["approval:write"],
        "approval.reject": ["approval:write"],
        "budget.get": ["budget:read"],
        "budget.reserve": ["budget:write"],
        "budget.release": ["budget:write"],
        "trace.get": ["trace:read"],
        "trace.list": ["trace:read"],
        "trace.verify": ["trace:read"],
        "trace.export": ["trace:read", "trace:export"],
        "event.publish": ["event:write"],
        "event.list": ["event:read"],
        "event.replay": ["event:write"],
        "dead_letter.list": ["event:read"],
        "dead_letter.replay": ["event:write"],
        "runtime.health": ["system:read"],
        "runtime.stats": ["system:read"],
    }

    def forward(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
    ) -> tuple[AgentRuntimeApiRequest, AgentRuntimeApiContext]:
        required = self.REQUIRED_PERMISSIONS.get(request.operation.value, [])
        current_permissions = set(context.permissions)
        missing = [p for p in required if p not in current_permissions]
        if missing:
            raise AgentRuntimeApiPermissionError(
                f"Missing permissions: {', '.join(missing)}"
            )
        return request, context


# ── ValidationMiddleware ────────────────────────────────────────────────────


class ValidationMiddleware(AgentRuntimeApiMiddleware):
    """Validates request payloads against rules."""

    def forward(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
    ) -> tuple[AgentRuntimeApiRequest, AgentRuntimeApiContext]:
        _sensitive_keys = [
            "chain_of_thought",
            "password",
            "token",
            "api_key",
            "bearer",
            "private_key",
            "private_prompt",
        ]
        for sensitive in _sensitive_keys:
            if sensitive in str(request.payload).lower():
                raise AgentRuntimeApiValidationError(
                    f"Payload contains restricted key: {sensitive}"
                )
        # No eval/exec/subprocess in payload values
        _dangerous = ["eval(", "exec(", "subprocess", "__import__", "os.system"]
        payload_str = str(request.payload).lower()
        for d in _dangerous:
            if d in payload_str:
                raise AgentRuntimeApiValidationError("Payload contains dangerous code")
        return request, context


# ── RedactionMiddleware ─────────────────────────────────────────────────────


class RedactionMiddleware(AgentRuntimeApiMiddleware):
    """Redacts sensitive data from response before returning."""

    SENSITIVE_FIELDS: ClassVar[set[str]] = {
        "chain_of_thought",
        "private_prompt",
        "password",
        "token",
        "api_key",
        "bearer",
        "private_key",
        "secret",
        "credential",
        "internal_reasoning",
    }

    def _redact(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: "**REDACTED**" if k in self.SENSITIVE_FIELDS else self._redact(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self._redact(item) for item in obj]
        return obj

    def after(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
        response: AgentRuntimeApiResponse,
    ) -> AgentRuntimeApiResponse:
        if response.data is not None:
            try:
                redacted_data = self._redact(response.data)
                return dataclasses_replace(response, data=redacted_data)
            except Exception as e:  # noqa: BLE001 - intentional catch-all for fail-closed redaction
                # Fail-closed: if redaction fails, return safe structured response
                # or raise internal error - don't leak unredacted data
                raise AgentRuntimeApiException(
                    error_code="INTERNAL_ERROR",
                    message="Failed to redact sensitive data",
                    details={"original_error": type(e).__name__},
                )
        return response


# ── AuditMiddleware ─────────────────────────────────────────────────────────


class AuditMiddleware(AgentRuntimeApiMiddleware):
    """Records audit trail for every operation.

    Audit logging must never take down the real operation: if building an
    entry fails unexpectedly, the failure is recorded (safely, typed) instead
    of overwriting the caller's actual response.
    """

    def __init__(self) -> None:
        self._audit_log: list[dict[str, Any]] = []
        self._audit_failures: list[dict[str, str]] = []

    @property
    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)

    @property
    def audit_failures(self) -> list[dict[str, str]]:
        return list(self._audit_failures)

    def clear(self) -> None:
        self._audit_log.clear()

    def after(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
        response: AgentRuntimeApiResponse,
    ) -> AgentRuntimeApiResponse:
        try:
            entry = {
                "request_id": request.request_id,
                "actor": context.actor,
                "operation": request.operation.value,
                "resource": request.payload.get("resource", "unknown"),
                "status": response.status.value,
                "timestamp": time.time(),
                "error_codes": [
                    e.code.value if hasattr(e.code, "value") else e.code
                    for e in response.errors
                ]
                if response.errors
                else [],
            }
            self._audit_log.append(entry)
        except Exception as exc:  # noqa: BLE001 - audit is a non-critical
            # side channel: a malformed request/response must never mask the
            # real operation result. Record the failure, typed, and continue.
            self._audit_failures.append(
                {
                    "request_id": request.request_id or "",
                    "error_type": type(exc).__name__,
                }
            )
        return response


# ── MetricsMiddleware ───────────────────────────────────────────────────────


class MetricsMiddleware(AgentRuntimeApiMiddleware):
    """Collects operational metrics for each API call.

    Like auditing, metrics collection is a non-critical side channel: a
    failure here must never overwrite the caller's real response.
    """

    def __init__(self) -> None:
        self._start_times: dict[str, float] = {}
        self._metrics: list[dict[str, Any]] = []
        self._metrics_failures: list[dict[str, str]] = []

    @property
    def operation_count(self) -> int:
        return len(self._metrics)

    @property
    def metrics_failures(self) -> list[dict[str, str]]:
        return list(self._metrics_failures)

    def _record(
        self,
        request_id: str,
        request: AgentRuntimeApiRequest,
        response: AgentRuntimeApiResponse,
    ) -> None:
        try:
            start = self._start_times.pop(request_id, None)
            duration_ms = (time.time() - start) * 1000 if start else 0.0
            self._metrics.append(
                {
                    "request_id": request_id,
                    "operation": request.operation.value,
                    "status": response.status.value,
                    "duration_ms": duration_ms,
                }
            )
        except Exception as exc:  # noqa: BLE001 - metrics is a non-critical
            # side channel: never let it mask the real operation result.
            self._metrics_failures.append(
                {"request_id": request_id or "", "error_type": type(exc).__name__}
            )

    def forward(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
    ) -> tuple[AgentRuntimeApiRequest, AgentRuntimeApiContext]:
        self._start_times[request.request_id] = time.time()
        return request, context

    def after(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
        response: AgentRuntimeApiResponse,
    ) -> AgentRuntimeApiResponse:
        self._record(request.request_id, request, response)
        return response


# ── ErrorMappingMiddleware ──────────────────────────────────────────────────


class ErrorMappingMiddleware(AgentRuntimeApiMiddleware):
    """Converts internal exceptions to structured API responses."""

    def on_error(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
        error: Exception,
    ) -> AgentRuntimeApiResponse | None:
        if isinstance(error, AgentRuntimeApiException):
            return AgentRuntimeApiResponse(
                status=AgentRuntimeApiStatus.ERROR,
                errors=[
                    AgentRuntimeApiError(
                        code=error.error_code,
                        message=str(error),
                        details=error.details,
                        request_id=request.request_id,
                    )
                ],
                request_id=request.request_id,
            )
        # Generic Python exceptions become internal errors
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.ERROR,
            errors=[
                AgentRuntimeApiError(
                    code="INTERNAL_ERROR",
                    message="An internal error occurred",
                    request_id=request.request_id,
                )
            ],
            request_id=request.request_id,
        )


# ── Helper to create standard chain ─────────────────────────────────────────


def create_default_middleware_chain() -> list[AgentRuntimeApiMiddleware]:
    """Create the default ordered middleware chain for the API."""
    return [
        RequestIdMiddleware(),
        AuthenticationContextMiddleware(),
        PermissionMiddleware(),
        ValidationMiddleware(),
        MetricsMiddleware(),
        ErrorMappingMiddleware(),
        AuditMiddleware(),
        RedactionMiddleware(),
    ]
