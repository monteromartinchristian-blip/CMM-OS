"""Phase 9.14 – Validation Integration Repository.

Defines thread-safe repositories for persisting validation requests, results, and decisions.
"""

from __future__ import annotations

import threading
from typing import Protocol

from cmm.agent_runtime.errors import ValidationRepositoryError
from cmm.agent_runtime.validation_integration_contracts import (
    AgentValidationRequest,
    AgentValidationResult,
)


class AgentValidationRepository(Protocol):
    """Protocol for validation integration repository implementations."""

    def add_request(self, request: AgentValidationRequest) -> None: ...

    def get_request(self, request_id: str) -> AgentValidationRequest: ...

    def add_result(self, result: AgentValidationResult) -> None: ...

    def get_result(self, request_id: str) -> AgentValidationResult: ...

    def get_results_by_run_id(
        self, run_id: str
    ) -> tuple[AgentValidationResult, ...]: ...

    def get_results_by_operation_request_id(
        self, operation_request_id: str
    ) -> tuple[AgentValidationResult, ...]: ...

    def find_by_idempotency_key(
        self, idempotency_key: str
    ) -> AgentValidationResult | None: ...


class InMemoryAgentValidationRepository:
    """In-memory thread-safe repository implementation for validation requests and results."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._requests: dict[str, AgentValidationRequest] = {}
        self._results: dict[str, AgentValidationResult] = {}
        self._idempotency_index: dict[str, str] = {}  # idempotency_key -> request_id

    def add_request(self, request: AgentValidationRequest) -> None:
        with self._lock:
            if request.id in self._requests:
                existing = self._requests[request.id]
                if existing.fingerprint != request.fingerprint:
                    raise ValidationRepositoryError(
                        f"Request '{request.id}' already exists with different fingerprint."
                    )
                return

            if request.idempotency_key:
                existing_req_id = self._idempotency_index.get(request.idempotency_key)
                if existing_req_id:
                    existing_req = self._requests.get(existing_req_id)
                    if existing_req and existing_req.fingerprint != request.fingerprint:
                        raise ValidationRepositoryError(
                            f"Idempotency key '{request.idempotency_key}' reused with conflicting payload."
                        )

            self._requests[request.id] = request
            if request.idempotency_key:
                self._idempotency_index[request.idempotency_key] = request.id

    def get_request(self, request_id: str) -> AgentValidationRequest:
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                raise ValidationRepositoryError(
                    f"Validation request '{request_id}' not found."
                )
            return req

    def add_result(self, result: AgentValidationResult) -> None:
        with self._lock:
            if result.request_id in self._results:
                existing = self._results[result.request_id]
                if existing.fingerprint != result.fingerprint:
                    raise ValidationRepositoryError(
                        f"Validation result for request '{result.request_id}' already finalized and cannot be mutated."
                    )
                return
            self._results[result.request_id] = result

    def get_result(self, request_id: str) -> AgentValidationResult:
        with self._lock:
            res = self._results.get(request_id)
            if res is None:
                raise ValidationRepositoryError(
                    f"Validation result for request '{request_id}' not found."
                )
            return res

    def get_results_by_run_id(self, run_id: str) -> tuple[AgentValidationResult, ...]:
        with self._lock:
            return tuple(res for res in self._results.values() if res.run_id == run_id)

    def get_results_by_operation_request_id(
        self, operation_request_id: str
    ) -> tuple[AgentValidationResult, ...]:
        with self._lock:
            return tuple(
                res
                for res in self._results.values()
                if res.operation_request_id == operation_request_id
            )

    def find_by_idempotency_key(
        self, idempotency_key: str
    ) -> AgentValidationResult | None:
        if not idempotency_key:
            return None
        with self._lock:
            req_id = self._idempotency_index.get(idempotency_key)
            if not req_id:
                return None
            return self._results.get(req_id)
