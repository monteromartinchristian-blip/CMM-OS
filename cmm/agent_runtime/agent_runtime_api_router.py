"""Phase 9.21 – Agent Runtime API Router.

Dispatches API requests to registered handlers with middleware support.
Single-operation registration, typed handlers, alias support, ordered middleware.
No dynamic arbitrary code execution.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from cmm.agent_runtime.agent_runtime_api_contracts import (
    AgentRuntimeApiContext,
    AgentRuntimeApiError,
    AgentRuntimeApiRequest,
    AgentRuntimeApiResponse,
)
from cmm.agent_runtime.agent_runtime_api_enums import (
    AgentRuntimeApiOperation,
    AgentRuntimeApiStatus,
)
from cmm.agent_runtime.agent_runtime_api_errors import (
    AgentRuntimeApiConflictError,
    AgentRuntimeApiContractError,
    AgentRuntimeApiException,
    AgentRuntimeApiInternalError,
    AgentRuntimeApiNotFoundError,
    AgentRuntimeApiUnsupportedOperationError,
)

# Handler signature: (request, context) -> AgentRuntimeApiResponse
ApiHandler = Callable[
    [AgentRuntimeApiRequest, AgentRuntimeApiContext], AgentRuntimeApiResponse
]


class AgentRuntimeApiRouter:
    """Typed operation router for the Agent Runtime API."""

    def __init__(self) -> None:
        self._handlers: dict[str, ApiHandler] = OrderedDict()
        self._aliases: dict[str, str] = {}
        self._middleware: list[AgentRuntimeApiMiddleware] = []

    # ── Registration ──────────────────────────────────────────────────────

    def register(
        self,
        operation: AgentRuntimeApiOperation,
        handler: ApiHandler,
        aliases: list[str] | None = None,
    ) -> None:
        """Register a handler for an operation. Raises ConflictError if duplicate."""
        op_key = operation.value
        if op_key in self._handlers:
            raise AgentRuntimeApiUnsupportedOperationError(
                f"Operation already registered: {op_key}"
            )
        if not callable(handler):
            raise AgentRuntimeApiContractError(
                f"Handler for '{op_key}' must be callable"
            )
        self._handlers[op_key] = handler
        if aliases:
            for alias in aliases:
                if alias in self._handlers or alias in self._aliases:
                    raise AgentRuntimeApiConflictError(
                        f"Alias '{alias}' conflicts with existing operation"
                    )
                self._aliases[alias] = op_key

    def unregister(self, operation: AgentRuntimeApiOperation) -> None:
        """Remove a handler. Raises NotFoundError if not registered."""
        op_key = operation.value
        if op_key not in self._handlers:
            raise AgentRuntimeApiNotFoundError(f"Operation not registered: {op_key}")
        del self._handlers[op_key]
        # Remove aliases pointing to this operation
        self._aliases = {a: k for a, k in self._aliases.items() if k != op_key}

    def add_middleware(self, middleware: AgentRuntimeApiMiddleware) -> None:
        """Add middleware to the chain. Executed in registration order."""
        self._middleware.append(middleware)

    # ── Resolution ──────────────────────────────────────────────────────────

    def resolve(self, operation: AgentRuntimeApiOperation) -> ApiHandler:
        """Resolve handler for operation. Raises if not found."""
        return self._resolve_op_key(operation.value)

    def _resolve_op_key(self, op_key: str) -> ApiHandler:
        # Try direct lookup
        handler = self._handlers.get(op_key)
        if handler is not None:
            return handler
        # Try alias lookup
        resolved = self._aliases.get(op_key)
        if resolved and resolved in self._handlers:
            return self._handlers[resolved]
        raise AgentRuntimeApiUnsupportedOperationError(
            f"No handler registered for operation: {op_key}"
        )

    # ── Dispatch ────────────────────────────────────────────────────────────

    def dispatch(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
    ) -> AgentRuntimeApiResponse:
        """Execute request through middleware chain and handler.

        The chain (built even with zero middleware) is the single place that
        converts unexpected handler exceptions into ``AgentRuntimeApiException``,
        so this method only ever needs to catch application errors.
        """
        if request.operation is None:
            return AgentRuntimeApiResponse(
                status=AgentRuntimeApiStatus.ERROR,
                errors=[
                    AgentRuntimeApiError(
                        code="VALIDATION_ERROR",
                        message="Operation is required",
                        request_id=request.request_id,
                    )
                ],
                request_id=request.request_id,
            )

        try:
            handler = self._resolve_op_key(request.operation.value)
            chain = self._build_chain(handler)
            return chain.execute(request, context)
        except AgentRuntimeApiException as api_err:
            return AgentRuntimeApiResponse(
                status=AgentRuntimeApiStatus.ERROR,
                errors=[
                    AgentRuntimeApiError(
                        code=api_err.error_code,
                        message=str(api_err),
                        details=api_err.details,
                        request_id=request.request_id,
                    )
                ],
                request_id=request.request_id,
            )

    def _build_chain(self, final_handler: ApiHandler) -> AgentRuntimeApiMiddlewareChain:
        """Build middleware chain wrapping the handler."""
        chain = AgentRuntimeApiMiddlewareChain(self._middleware, final_handler)
        return chain

    # ── Introspection ───────────────────────────────────────────────────────

    def list_operations(self) -> list[str]:
        """Return all registered operation names."""
        return list(self._handlers.keys())

    def has_operation(self, operation: AgentRuntimeApiOperation) -> bool:
        return operation.value in self._handlers


# ── Middleware Protocol ─────────────────────────────────────────────────────


class AgentRuntimeApiMiddleware:
    """Base middleware protocol for the API router."""

    def forward(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> tuple[AgentRuntimeApiRequest, AgentRuntimeApiContext]:
        """Transform request/context before handler. Default pass-through."""
        return request, context

    def after(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
        response: AgentRuntimeApiResponse,
    ) -> AgentRuntimeApiResponse:
        """Transform response after handler. Default pass-through."""
        return response

    def on_error(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
        error: Exception,
    ) -> AgentRuntimeApiResponse | None:
        """Handle errors. Return None to re-raise."""
        return None


class AgentRuntimeApiMiddlewareChain:
    """Ordered middleware chain wrapping the final handler."""

    def __init__(
        self,
        middleware: list[AgentRuntimeApiMiddleware],
        handler: ApiHandler,
    ) -> None:
        self._middleware = list(middleware)
        self._handler = handler

    def execute(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
    ) -> AgentRuntimeApiResponse:
        """Execute through middleware chain then handler."""
        current_request, current_context = request, context

        # Forward pass - transform request
        for mw in self._middleware:
            current_request, current_context = mw.forward(
                current_request, current_context
            )

        # Execute handler
        try:
            response = self._handler(current_request, current_context)
        except AgentRuntimeApiException:
            raise
        except Exception as exc:
            # Sole handler boundary: handlers are arbitrary adapter code with
            # no guarantee they only raise AgentRuntimeApiException; give
            # middleware a chance to handle the failure, then convert it to a
            # safe internal error. The original exception text is never
            # forwarded (see AgentRuntimeApiInternalError).
            for mw in self._middleware:
                result = mw.on_error(current_request, current_context, exc)
                if result is not None:
                    return result
            # Re-raise if no middleware handled it. Only non-Application
            # exceptions reach here; str(exc) is intentionally not exposed.
            raise AgentRuntimeApiInternalError() from exc

        # Reverse pass - transform response
        for mw in reversed(self._middleware):
            response = mw.after(current_request, current_context, response)

        return response
