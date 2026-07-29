"""Phase 9.13 – Agent Operation Execution Repository.

Defines the repository interface and thread-safe in-memory store for operation requests and results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock

from cmm.agent_runtime.errors import (
    AgentOperationRequestNotFoundError,
    AgentOperationResultNotFoundError,
    DuplicateAgentOperationRequestError,
    DuplicateAgentOperationResultError,
)
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationExecutionResult,
    AgentOperationRequest,
)


class AgentOperationExecutionRepository(ABC):
    """Abstract repository interface for operation requests and execution results."""

    @abstractmethod
    def add_request(self, request: AgentOperationRequest) -> None:
        """Store an operation request."""
        ...

    @abstractmethod
    def get_request(self, request_id: str) -> AgentOperationRequest:
        """Retrieve an operation request by ID."""
        ...

    @abstractmethod
    def list_requests(
        self, agent_run_id: str | None = None
    ) -> list[AgentOperationRequest]:
        """List all operation requests, optionally filtered by agent_run_id."""
        ...

    @abstractmethod
    def add_result(self, result: AgentOperationExecutionResult) -> None:
        """Store an operation execution result."""
        ...

    @abstractmethod
    def get_result(self, result_id: str) -> AgentOperationExecutionResult:
        """Retrieve an execution result by ID."""
        ...

    @abstractmethod
    def list_results(
        self, agent_run_id: str | None = None
    ) -> list[AgentOperationExecutionResult]:
        """List all execution results, optionally filtered by agent_run_id."""
        ...

    @abstractmethod
    def find_by_idempotency_key(
        self, idempotency_key: str
    ) -> AgentOperationExecutionResult | None:
        """Find a completed or persisted execution result by idempotency key."""
        ...

    @abstractmethod
    def count_uses(
        self,
        agent_run_id: str,
        operation_name: str,
        operation_version: str = "1",
    ) -> int:
        """Count confirmed or executed runs for a specific operation within an agent run scope."""
        ...


class InMemoryAgentOperationExecutionRepository(AgentOperationExecutionRepository):
    """Thread-safe in-memory implementation of AgentOperationExecutionRepository."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._requests: dict[str, AgentOperationRequest] = {}
        self._results: dict[str, AgentOperationExecutionResult] = {}
        self._request_order: list[str] = []
        self._result_order: list[str] = []

    def add_request(self, request: AgentOperationRequest) -> None:
        with self._lock:
            if request.id in self._requests:
                raise DuplicateAgentOperationRequestError(
                    f"Request '{request.id}' already exists."
                )
            self._requests[request.id] = request
            self._request_order.append(request.id)

    def get_request(self, request_id: str) -> AgentOperationRequest:
        with self._lock:
            if request_id not in self._requests:
                raise AgentOperationRequestNotFoundError(
                    f"Request '{request_id}' not found."
                )
            return self._requests[request_id]

    def list_requests(
        self, agent_run_id: str | None = None
    ) -> list[AgentOperationRequest]:
        with self._lock:
            if agent_run_id is None:
                return [self._requests[rid] for rid in self._request_order]
            return [
                self._requests[rid]
                for rid in self._request_order
                if self._requests[rid].agent_run_id == agent_run_id
            ]

    def add_result(self, result: AgentOperationExecutionResult) -> None:
        with self._lock:
            if result.id in self._results:
                raise DuplicateAgentOperationResultError(
                    f"Result '{result.id}' already exists."
                )
            if result.request_id not in self._requests:
                raise AgentOperationRequestNotFoundError(
                    f"Orphaned result: request '{result.request_id}' not found."
                )
            self._results[result.id] = result
            self._result_order.append(result.id)

    def get_result(self, result_id: str) -> AgentOperationExecutionResult:
        with self._lock:
            if result_id not in self._results:
                raise AgentOperationResultNotFoundError(
                    f"Result '{result_id}' not found."
                )
            return self._results[result_id]

    def list_results(
        self, agent_run_id: str | None = None
    ) -> list[AgentOperationExecutionResult]:
        with self._lock:
            if agent_run_id is None:
                return [self._results[rid] for rid in self._result_order]
            return [
                self._results[rid]
                for rid in self._result_order
                if self._results[rid].agent_run_id == agent_run_id
            ]

    def find_by_idempotency_key(
        self, idempotency_key: str
    ) -> AgentOperationExecutionResult | None:
        with self._lock:
            for rid in reversed(self._result_order):
                res = self._results[rid]
                if res.idempotency_key == idempotency_key:
                    return res
            return None

    def count_uses(
        self,
        agent_run_id: str,
        operation_name: str,
        operation_version: str = "1",
    ) -> int:
        with self._lock:
            count = 0
            for rid in self._result_order:
                res = self._results[rid]
                if (
                    res.agent_run_id == agent_run_id
                    and res.operation_name == operation_name
                    and res.operation_version == operation_version
                    and res.status in ("completed", "partially_completed")
                ):
                    count += 1
            return count
