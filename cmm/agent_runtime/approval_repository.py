"""Phase 9.10 – Human Approval System Repository.

Provides in-memory, deterministic storage and querying for ApprovalRequest,
ApprovalDecision, and ApprovalResolution domain entities.
"""

from __future__ import annotations

import threading
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from .approval_contracts import ApprovalDecision, ApprovalRequest, ApprovalResolution
from .enums import ApprovalRequestStatus
from .errors import (
    ApprovalDecisionNotFoundError,
    ApprovalRequestNotFoundError,
    DuplicateApprovalDecisionError,
    DuplicateApprovalRequestError,
    InvalidApprovalContractError,
)


def _now_utc() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@runtime_checkable
class ApprovalRepository(Protocol):
    """Protocol defining the repository interface for the Human Approval System."""

    @property
    def atomic_consumption_guaranteed(self) -> bool:
        """Declare that ``critical_section`` protects validation and consumption."""
        ...

    def critical_section(self) -> AbstractContextManager[None]:
        """Return one boundary covering reads, validation, and consumption."""
        ...

    def add_request(self, request: ApprovalRequest) -> ApprovalRequest:
        """Store a new ApprovalRequest."""
        ...

    def get_request(self, request_id: str) -> ApprovalRequest:
        """Retrieve an ApprovalRequest by ID."""
        ...

    def update_request(self, request: ApprovalRequest) -> ApprovalRequest:
        """Update an existing ApprovalRequest."""
        ...

    def list_requests(
        self,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        workflow_id: str | None = None,
        operation_id: str | None = None,
        status: ApprovalRequestStatus | None = None,
    ) -> tuple[ApprovalRequest, ...]:
        """List ApprovalRequests matching given criteria."""
        ...

    def add_decision(self, decision: ApprovalDecision) -> ApprovalDecision:
        """Record an ApprovalDecision."""
        ...

    def get_decision(self, decision_id: str) -> ApprovalDecision:
        """Retrieve an ApprovalDecision by ID."""
        ...

    def list_decisions(self, request_id: str) -> tuple[ApprovalDecision, ...]:
        """List all decisions associated with a request ID in chronological order."""
        ...

    def find_pending_for_run(self, agent_run_id: str) -> tuple[ApprovalRequest, ...]:
        """Retrieve all pending approval requests for an agent run."""
        ...

    def find_pending_for_operation(
        self, operation_id: str
    ) -> tuple[ApprovalRequest, ...]:
        """Retrieve all pending approval requests for a specific operation."""
        ...

    def resolve_request(self, resolution: ApprovalResolution) -> ApprovalResolution:
        """Store or update the resolution for an approval request."""
        ...

    def get_resolution(self, request_id: str) -> ApprovalResolution | None:
        """Get the resolution for a request if resolved."""
        ...

    def expire_requests(
        self, now: datetime | None = None
    ) -> tuple[ApprovalRequest, ...]:
        """Evaluate expiration times and mark expired pending requests."""
        ...

    def mark_consumed(
        self, request_id: str, *, now: datetime | None = None
    ) -> bool:
        """Atomically mark a request as consumed. Returns True iff this call consumed it."""
        ...

    def mark_revoked(
        self, request_id: str, actor_id: str, *, now: datetime | None = None
    ) -> bool:
        """Mark a request as revoked. Returns True iff this call revoked it."""
        ...

    def is_consumed(self, request_id: str) -> bool:
        """Check if a request has been consumed."""
        ...

    def is_revoked(self, request_id: str) -> bool:
        """Check if a request has been revoked."""
        ...


class InMemoryApprovalRepository:
    """Deterministic, thread-safe in-memory implementation of ApprovalRepository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._requests: dict[str, ApprovalRequest] = {}
        self._decisions: dict[str, ApprovalDecision] = {}
        self._decisions_by_request: dict[str, list[str]] = {}
        self._resolutions: dict[str, ApprovalResolution] = {}
        self._consumed: dict[str, datetime] = {}
        self._revoked: dict[str, tuple[str, datetime]] = {}

    @property
    def atomic_consumption_guaranteed(self) -> bool:
        """The repository's re-entrant lock protects the full consume sequence."""
        return True

    def critical_section(self) -> AbstractContextManager[None]:
        """Use the repository RLock as one re-entrant atomic boundary."""
        return self._lock

    def add_request(self, request: ApprovalRequest) -> ApprovalRequest:
        """Store a new ApprovalRequest."""
        if not isinstance(request, ApprovalRequest):
            raise InvalidApprovalContractError(
                f"request must be an ApprovalRequest, got {type(request).__name__}"
            )

        with self._lock:
            if request.id in self._requests:
                raise DuplicateApprovalRequestError(
                    f"ApprovalRequest with ID {request.id!r} already exists"
                )
            self._requests[request.id] = request
            if request.id not in self._decisions_by_request:
                self._decisions_by_request[request.id] = []
            return request

    def get_request(self, request_id: str) -> ApprovalRequest:
        """Retrieve an ApprovalRequest by ID."""
        if not isinstance(request_id, str) or not request_id.strip():
            raise InvalidApprovalContractError("request_id must be a non-empty string")

        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                raise ApprovalRequestNotFoundError(
                    f"ApprovalRequest with ID {request_id!r} not found"
                )
            return req

    def update_request(self, request: ApprovalRequest) -> ApprovalRequest:
        """Update an existing ApprovalRequest."""
        if not isinstance(request, ApprovalRequest):
            raise InvalidApprovalContractError(
                f"request must be an ApprovalRequest, got {type(request).__name__}"
            )

        with self._lock:
            if request.id not in self._requests:
                raise ApprovalRequestNotFoundError(
                    f"Cannot update non-existent ApprovalRequest {request.id!r}"
                )
            self._requests[request.id] = request
            return request

    def list_requests(
        self,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        workflow_id: str | None = None,
        operation_id: str | None = None,
        status: ApprovalRequestStatus | None = None,
    ) -> tuple[ApprovalRequest, ...]:
        """List ApprovalRequests matching given criteria."""
        with self._lock:
            results: list[ApprovalRequest] = []
            for req in self._requests.values():
                if agent_run_id is not None and req.agent_run_id != agent_run_id:
                    continue
                if goal_id is not None and req.goal_id != goal_id:
                    continue
                if workflow_id is not None and req.workflow_id != workflow_id:
                    continue
                if operation_id is not None and req.operation_id != operation_id:
                    continue
                if status is not None and req.status != status:
                    continue
                results.append(req)
            return tuple(results)

    def add_decision(self, decision: ApprovalDecision) -> ApprovalDecision:
        """Record an ApprovalDecision associated with an existing request."""
        if not isinstance(decision, ApprovalDecision):
            raise InvalidApprovalContractError(
                f"decision must be an ApprovalDecision, got {type(decision).__name__}"
            )

        with self._lock:
            if decision.id in self._decisions:
                raise DuplicateApprovalDecisionError(
                    f"ApprovalDecision with ID {decision.id!r} already exists"
                )
            if decision.request_id not in self._requests:
                raise ApprovalRequestNotFoundError(
                    f"Orphan decision: ApprovalRequest with ID {decision.request_id!r} not found"
                )

            self._decisions[decision.id] = decision
            if decision.request_id not in self._decisions_by_request:
                self._decisions_by_request[decision.request_id] = []
            self._decisions_by_request[decision.request_id].append(decision.id)
            return decision

    def get_decision(self, decision_id: str) -> ApprovalDecision:
        """Retrieve an ApprovalDecision by ID."""
        if not isinstance(decision_id, str) or not decision_id.strip():
            raise InvalidApprovalContractError("decision_id must be a non-empty string")

        with self._lock:
            dec = self._decisions.get(decision_id)
            if dec is None:
                raise ApprovalDecisionNotFoundError(
                    f"ApprovalDecision with ID {decision_id!r} not found"
                )
            return dec

    def list_decisions(self, request_id: str) -> tuple[ApprovalDecision, ...]:
        """List all decisions associated with a request ID in insertion order."""
        if not isinstance(request_id, str) or not request_id.strip():
            raise InvalidApprovalContractError("request_id must be a non-empty string")

        with self._lock:
            if request_id not in self._requests:
                raise ApprovalRequestNotFoundError(
                    f"ApprovalRequest with ID {request_id!r} not found"
                )
            decision_ids = self._decisions_by_request.get(request_id, [])
            return tuple(self._decisions[d_id] for d_id in decision_ids)

    def find_pending_for_run(self, agent_run_id: str) -> tuple[ApprovalRequest, ...]:
        """Retrieve all pending approval requests for an agent run."""
        if not isinstance(agent_run_id, str) or not agent_run_id.strip():
            raise InvalidApprovalContractError(
                "agent_run_id must be a non-empty string"
            )
        return self.list_requests(
            agent_run_id=agent_run_id, status=ApprovalRequestStatus.PENDING
        )

    def find_pending_for_operation(
        self, operation_id: str
    ) -> tuple[ApprovalRequest, ...]:
        """Retrieve all pending approval requests for a specific operation."""
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise InvalidApprovalContractError(
                "operation_id must be a non-empty string"
            )
        return self.list_requests(
            operation_id=operation_id, status=ApprovalRequestStatus.PENDING
        )

    def resolve_request(self, resolution: ApprovalResolution) -> ApprovalResolution:
        """Store or update the resolution for an approval request."""
        if not isinstance(resolution, ApprovalResolution):
            raise InvalidApprovalContractError(
                f"resolution must be an ApprovalResolution, got {type(resolution).__name__}"
            )

        with self._lock:
            if resolution.request_id not in self._requests:
                raise ApprovalRequestNotFoundError(
                    f"ApprovalRequest with ID {resolution.request_id!r} not found"
                )
            self._resolutions[resolution.request_id] = resolution
            return resolution

    def get_resolution(self, request_id: str) -> ApprovalResolution | None:
        """Get the stored resolution for a request if present."""
        if not isinstance(request_id, str) or not request_id.strip():
            raise InvalidApprovalContractError("request_id must be a non-empty string")

        with self._lock:
            return self._resolutions.get(request_id)

    def expire_requests(
        self, now: datetime | None = None
    ) -> tuple[ApprovalRequest, ...]:
        """Evaluate expiration times and mark expired pending/postponed requests."""
        current_time = now or _now_utc()
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        with self._lock:
            expired_requests: list[ApprovalRequest] = []
            for req_id, req in list(self._requests.items()):
                if (
                    req.status
                    in (ApprovalRequestStatus.PENDING, ApprovalRequestStatus.POSTPONED)
                    and req.expires_at is not None
                    and req.expires_at <= current_time
                ):
                    updated_req = ApprovalRequest.from_mapping(
                        {
                            **req.to_dict(),
                            "status": ApprovalRequestStatus.EXPIRED.value,
                            "updated_at": current_time.isoformat(),
                        }
                    )
                    self._requests[req_id] = updated_req
                    expired_requests.append(updated_req)
            return tuple(expired_requests)

    def mark_consumed(
        self, request_id: str, *, now: datetime | None = None
    ) -> bool:
        """Atomically mark a request as consumed. Returns True iff this call consumed it.

        Thread-safe: two concurrent calls for the same one_time request
        will result in exactly one returning True.
        """
        current_time = now or _now_utc()
        with self._lock:
            if request_id not in self._requests:
                raise ApprovalRequestNotFoundError(
                    f"ApprovalRequest with ID {request_id!r} not found"
                )
            if request_id in self._consumed:
                return False
            self._consumed[request_id] = current_time
            return True

    def mark_revoked(
        self, request_id: str, actor_id: str, *, now: datetime | None = None
    ) -> bool:
        """Mark a request as revoked. Returns True iff this call revoked it."""
        current_time = now or _now_utc()
        with self._lock:
            if request_id not in self._requests:
                raise ApprovalRequestNotFoundError(
                    f"ApprovalRequest with ID {request_id!r} not found"
                )
            if request_id in self._revoked:
                return False
            self._revoked[request_id] = (actor_id, current_time)
            return True

    def is_consumed(self, request_id: str) -> bool:
        """Check if a request has been consumed."""
        with self._lock:
            return request_id in self._consumed

    def is_revoked(self, request_id: str) -> bool:
        """Check if a request has been revoked."""
        with self._lock:
            return request_id in self._revoked
