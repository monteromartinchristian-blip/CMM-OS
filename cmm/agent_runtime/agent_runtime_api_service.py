"""Phase 9.21 – Agent Runtime API Service.

Main facade that exposes the Agent Runtime API.
Delegates to adapters, managers, repositories and existing services.
No duplicated domain logic.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from cmm.agent_runtime.agent_runtime_api_adapters import (
    AgentRunApiAdapter,
    ApprovalApiAdapter,
    BudgetApiAdapter,
    GoalApiAdapter,
    RuntimeEventApiAdapter,
    RuntimeSystemApiAdapter,
    TraceApiAdapter,
)
from cmm.agent_runtime.agent_runtime_api_contracts import (
    AgentRuntimeApiContext,
    AgentRuntimeApiError,
    AgentRuntimeApiRequest,
    AgentRuntimeApiResponse,
)
from cmm.agent_runtime.agent_runtime_api_enums import (
    AgentRuntimeApiErrorCode,
    AgentRuntimeApiOperation,
    AgentRuntimeApiStatus,
)
from cmm.agent_runtime.agent_runtime_api_errors import (
    AgentRuntimeApiException,
    AgentRuntimeApiIdempotencyConflictError,
)
from cmm.agent_runtime.agent_runtime_api_idempotency import (
    InMemoryAgentRuntimeApiIdempotencyStore,
    compute_fingerprint,
)
from cmm.agent_runtime.agent_runtime_api_middleware import (
    create_default_middleware_chain,
)
from cmm.agent_runtime.agent_runtime_api_router import (
    AgentRuntimeApiRouter,
)
from cmm.agent_runtime.runtime_event_types import EventType

# Mutating operations that emit a canonical runtime lifecycle event on
# success, and the response attribute holding the affected resource id.
_LIFECYCLE_EVENTS: dict[AgentRuntimeApiOperation, tuple[str, str]] = {
    AgentRuntimeApiOperation.GOAL_CREATE: (EventType.GOAL_CREATED, "goal_id"),
    AgentRuntimeApiOperation.GOAL_UPDATE: (EventType.GOAL_UPDATED, "goal_id"),
    AgentRuntimeApiOperation.GOAL_PRIORITIZE: (EventType.GOAL_PRIORITIZED, "goal_id"),
    AgentRuntimeApiOperation.GOAL_PAUSE: (EventType.GOAL_PAUSED, "goal_id"),
    AgentRuntimeApiOperation.GOAL_RESUME: (EventType.GOAL_RESUMED, "goal_id"),
    AgentRuntimeApiOperation.GOAL_CANCEL: (EventType.GOAL_CANCELLED, "goal_id"),
    AgentRuntimeApiOperation.RUN_START: (EventType.AGENT_RUN_STARTED, "run_id"),
    AgentRuntimeApiOperation.RUN_PAUSE: (EventType.AGENT_RUN_PAUSED, "run_id"),
    AgentRuntimeApiOperation.RUN_RESUME: (EventType.AGENT_RUN_RESUMED, "run_id"),
    AgentRuntimeApiOperation.RUN_CANCEL: (EventType.AGENT_RUN_CANCELLED, "run_id"),
    AgentRuntimeApiOperation.APPROVAL_APPROVE: (
        EventType.APPROVAL_APPROVED,
        "approval_id",
    ),
    AgentRuntimeApiOperation.APPROVAL_REJECT: (
        EventType.APPROVAL_REJECTED,
        "approval_id",
    ),
    AgentRuntimeApiOperation.BUDGET_RESERVE: (EventType.BUDGET_RESERVED, "budget_id"),
    AgentRuntimeApiOperation.BUDGET_RELEASE: (EventType.BUDGET_RELEASED, "budget_id"),
}


class AgentRuntimeApiService:
    """Application facade for the Agent Runtime API.

    Exposes: execute, execute_many, health, stats.
    Delegates to registered adapters via the router.
    """

    def __init__(self) -> None:
        self._router = AgentRuntimeApiRouter()
        self._idempotency = InMemoryAgentRuntimeApiIdempotencyStore(
            default_ttl_seconds=300.0
        )
        self._start_time = time.time()

        # Adapters
        self._goal_adapter = GoalApiAdapter()
        self._run_adapter = AgentRunApiAdapter(
            goal_lookup=self._goal_adapter.lookup_status
        )
        self._approval_adapter = ApprovalApiAdapter()
        self._budget_adapter = BudgetApiAdapter()
        self._trace_adapter = TraceApiAdapter()
        self._event_adapter = RuntimeEventApiAdapter()
        self._system_adapter = RuntimeSystemApiAdapter()

        # Health reflects only what is actually wired - never invented.
        self._system_adapter.set_component_wired(
            "goal_manager", self._goal_adapter.has_manager
        )
        self._system_adapter.set_component_wired(
            "goal_repository", self._goal_adapter.has_repository
        )
        self._system_adapter.set_component_wired(
            "event_bus", self._event_adapter.has_bus
        )
        self._system_adapter.set_component_wired(
            "trace_service", self._trace_adapter.has_service
        )

        # Middleware
        for mw in create_default_middleware_chain():
            self._router.add_middleware(mw)

        # Register all operations
        self._register_operations()

    def _register_operations(self) -> None:
        """Register all API operations with their handler closures."""
        r = self._router
        g = self._goal_adapter
        ru = self._run_adapter
        a = self._approval_adapter
        b = self._budget_adapter
        t = self._trace_adapter
        e = self._event_adapter
        s = self._system_adapter

        # Goals
        r.register(AgentRuntimeApiOperation.GOAL_CREATE, g.create)
        r.register(AgentRuntimeApiOperation.GOAL_GET, g.get)
        r.register(AgentRuntimeApiOperation.GOAL_LIST, g.list)
        r.register(AgentRuntimeApiOperation.GOAL_UPDATE, g.update)
        r.register(AgentRuntimeApiOperation.GOAL_PRIORITIZE, g.prioritize)
        r.register(AgentRuntimeApiOperation.GOAL_PAUSE, g.pause)
        r.register(AgentRuntimeApiOperation.GOAL_RESUME, g.resume)
        r.register(AgentRuntimeApiOperation.GOAL_CANCEL, g.cancel)

        # Runs
        r.register(AgentRuntimeApiOperation.RUN_START, ru.start)
        r.register(AgentRuntimeApiOperation.RUN_GET, ru.get)
        r.register(AgentRuntimeApiOperation.RUN_LIST, ru.list)
        r.register(AgentRuntimeApiOperation.RUN_PAUSE, ru.pause)
        r.register(AgentRuntimeApiOperation.RUN_RESUME, ru.resume)
        r.register(AgentRuntimeApiOperation.RUN_CANCEL, ru.cancel)

        # Approvals
        r.register(AgentRuntimeApiOperation.APPROVAL_LIST, a.list)
        r.register(AgentRuntimeApiOperation.APPROVAL_GET, a.get)
        r.register(AgentRuntimeApiOperation.APPROVAL_APPROVE, a.approve)
        r.register(AgentRuntimeApiOperation.APPROVAL_REJECT, a.reject)

        # Budgets
        r.register(AgentRuntimeApiOperation.BUDGET_GET, b.get)
        r.register(AgentRuntimeApiOperation.BUDGET_RESERVE, b.reserve)
        r.register(AgentRuntimeApiOperation.BUDGET_RELEASE, b.release)

        # Traces
        r.register(AgentRuntimeApiOperation.TRACE_GET, t.get)
        r.register(AgentRuntimeApiOperation.TRACE_LIST, t.list)
        r.register(AgentRuntimeApiOperation.TRACE_VERIFY, t.verify)
        r.register(AgentRuntimeApiOperation.TRACE_EXPORT, t.export)

        # Events
        r.register(AgentRuntimeApiOperation.EVENT_PUBLISH, e.publish)
        r.register(AgentRuntimeApiOperation.EVENT_LIST, e.list)
        r.register(AgentRuntimeApiOperation.EVENT_REPLAY, e.replay)
        r.register(AgentRuntimeApiOperation.DEAD_LETTER_LIST, e.list_dead_letters)
        r.register(AgentRuntimeApiOperation.DEAD_LETTER_REPLAY, e.replay_dead_letter)

        # System
        r.register(AgentRuntimeApiOperation.RUNTIME_HEALTH, s.health)
        r.register(AgentRuntimeApiOperation.RUNTIME_STATS, s.stats)

    # ── Public facade ───────────────────────────────────────────────────────

    def execute(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
    ) -> AgentRuntimeApiResponse:
        """Execute a single API request. Always returns a response, never raises."""
        start = time.time()

        # Ensure request_id
        if not request.request_id:
            object.__setattr__(request, "request_id", str(uuid.uuid4()))

        try:
            cached = self._check_idempotency(request)
            if cached is not None:
                return cached

            response = self._router.dispatch(request, context)
            self._store_idempotency(request, response)
        except AgentRuntimeApiException as api_err:
            response = self._response_from_exception(request, api_err)
        except Exception:  # noqa: BLE001 - facade boundary: execute() must always
            # return a structured response and never raise for genuinely
            # unexpected failures (e.g. non-serializable idempotency payloads).
            # No exception text is forwarded to callers.
            response = self._handle_internal_error(request)

        latency_ms = (time.time() - start) * 1000
        self._system_adapter.record_operation(latency_ms)
        if response.status == AgentRuntimeApiStatus.ERROR:
            self._system_adapter.record_error()
        else:
            self._emit_lifecycle_event(request, context, response)

        return response

    def _response_from_exception(
        self, request: AgentRuntimeApiRequest, api_err: AgentRuntimeApiException
    ) -> AgentRuntimeApiResponse:
        """Turn an application error into a structured error response."""
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.ERROR,
            errors=[
                AgentRuntimeApiError(
                    code=AgentRuntimeApiErrorCode(api_err.error_code),
                    message=str(api_err),
                    details=api_err.details,
                    request_id=request.request_id,
                )
            ],
            request_id=request.request_id,
        )

    def _handle_internal_error(
        self, request: AgentRuntimeApiRequest
    ) -> AgentRuntimeApiResponse:
        """Convert unexpected exceptions to safe internal error responses."""
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.ERROR,
            errors=[
                AgentRuntimeApiError(
                    code=AgentRuntimeApiErrorCode.INTERNAL_ERROR,
                    message="An internal error occurred",
                    request_id=request.request_id,
                )
            ],
            request_id=request.request_id,
        )

    def _emit_lifecycle_event(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
        response: AgentRuntimeApiResponse,
    ) -> None:
        """Publish the canonical runtime event for a successful mutation.

        Uses only resource ids/status, never free-text fields, so the event
        payload can never itself be rejected as unsafe or leak user content.
        """
        spec = _LIFECYCLE_EVENTS.get(request.operation)
        if spec is None:
            return
        event_type, id_field = spec
        resource_id = getattr(response.data, id_field, None)
        self._event_adapter.publish_internal(
            event_type=event_type,
            payload={
                "resource_id": resource_id,
                "operation": request.operation.value,
                "actor": context.actor,
            },
        )

    def execute_many(
        self,
        requests: list[AgentRuntimeApiRequest],
        context: AgentRuntimeApiContext,
    ) -> list[AgentRuntimeApiResponse]:
        """Execute multiple requests preserving order.

        Each request is independent: one failing request produces its own
        error response without affecting the others or faking success.
        """
        return [self.execute(req, context) for req in requests]

    def health(self) -> dict[str, Any]:
        """Return health status of the API service."""
        ops = self._router.list_operations()
        return {
            "service": "AgentRuntimeApiService",
            "version": "9.21.0",
            "uptime_seconds": time.time() - self._start_time,
            "router_operations": len(ops),
            "idempotency_entries": self._idempotency.size,
        }

    def stats(self) -> dict[str, Any]:
        """Return stats for the API service."""
        return {
            "service": "AgentRuntimeApiService",
            "operations": self._router.list_operations(),
            "idempotency_entries": self._idempotency.size,
        }

    @property
    def router(self) -> AgentRuntimeApiRouter:
        return self._router

    @property
    def goal_adapter(self) -> GoalApiAdapter:
        return self._goal_adapter

    @property
    def run_adapter(self) -> AgentRunApiAdapter:
        return self._run_adapter

    @property
    def approval_adapter(self) -> ApprovalApiAdapter:
        return self._approval_adapter

    @property
    def budget_adapter(self) -> BudgetApiAdapter:
        return self._budget_adapter

    @property
    def trace_adapter(self) -> TraceApiAdapter:
        return self._trace_adapter

    @property
    def event_adapter(self) -> RuntimeEventApiAdapter:
        return self._event_adapter

    @property
    def system_adapter(self) -> RuntimeSystemApiAdapter:
        return self._system_adapter

    # ── Idempotency helpers ─────────────────────────────────────────────────

    def _check_idempotency(
        self, request: AgentRuntimeApiRequest
    ) -> AgentRuntimeApiResponse | None:
        idem_key = request.idempotency_key
        if not idem_key:
            return None
        entry = self._idempotency.get(idem_key)
        if entry is None:
            return None
        # Same key: check fingerprint
        new_fp = compute_fingerprint(request.operation.value, request.payload)
        if entry.fingerprint != new_fp:
            raise AgentRuntimeApiIdempotencyConflictError(
                f"Idempotency key {idem_key} re-used with different payload"
            )
        # Return cached result
        return entry.result

    def _store_idempotency(
        self,
        request: AgentRuntimeApiRequest,
        response: AgentRuntimeApiResponse,
    ) -> None:
        idem_key = request.idempotency_key
        if not idem_key:
            return
        fingerprint = compute_fingerprint(request.operation.value, request.payload)
        self._idempotency.store(idem_key, fingerprint, response)
