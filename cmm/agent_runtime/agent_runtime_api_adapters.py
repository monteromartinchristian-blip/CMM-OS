"""Phase 9.21 – Agent Runtime API Adapters.

Resource-specific adapters that translate public API requests to internal contracts
and map results back to public responses.
Each adapter respects permissions, sanitizes data, and never exposes mutable internals.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, ClassVar

from cmm.agent_runtime.agent_runtime_api_contracts import (
    AgentRunResponse,
    AgentRuntimeApiContext,
    AgentRuntimeApiError,
    AgentRuntimeApiRequest,
    AgentRuntimeApiResponse,
    ApprovalResponse,
    BudgetResponse,
    EventResponse,
    GoalResponse,
    RuntimeHealthResponse,
    RuntimeStatsResponse,
    TraceResponse,
)
from cmm.agent_runtime.agent_runtime_api_enums import (
    AgentRuntimeApiErrorCode,
    AgentRuntimeApiStatus,
)
from cmm.agent_runtime.agent_runtime_api_errors import (
    AgentRuntimeApiNotFoundError,
    AgentRuntimeApiValidationError,
)
from cmm.agent_runtime.runtime_event_types import (
    get_event_category,
    is_registered_event_type,
)

# Sensitive keys that must never leave the process boundary through an
# adapter response, regardless of what internal state happens to contain.
_SENSITIVE_FIELDS = frozenset(
    {
        "chain_of_thought",
        "internal_reasoning",
        "private_prompt",
        "password",
        "token",
        "api_key",
        "bearer",
        "private_key",
        "secret",
        "credential",
    }
)

_UNSAFE_PAYLOAD_MARKERS = (
    "chain_of_thought",
    "internal_reasoning",
    "private_prompt",
    "password",
    "token=",
    "api_key=",
    "bearer ",
    "private_key=",
    "eval(",
    "exec(",
    "subprocess",
    "__import__",
    "os.system",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(
    request: AgentRuntimeApiRequest,
    code: AgentRuntimeApiErrorCode,
    message: str,
) -> AgentRuntimeApiResponse:
    """Build a structured error response. The single place adapters do this."""
    return AgentRuntimeApiResponse(
        status=AgentRuntimeApiStatus.ERROR,
        errors=[
            AgentRuntimeApiError(
                code=code, message=message, request_id=request.request_id
            )
        ],
        request_id=request.request_id,
    )


def _redact(obj: Any) -> Any:
    """Recursively strip sensitive keys before data leaves an adapter."""
    if isinstance(obj, dict):
        return {
            k: "**REDACTED**" if k in _SENSITIVE_FIELDS else _redact(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


def _contains_unsafe_content(payload: dict[str, Any]) -> bool:
    blob = json.dumps(payload, default=str, sort_keys=True).lower()
    return any(marker in blob for marker in _UNSAFE_PAYLOAD_MARKERS)


# ── GoalApiAdapter ────────────────────────────────────────────────────────


class GoalApiAdapter:
    """Translates Goal API requests to goal manager/repository calls."""

    def __init__(self, goal_manager=None, goal_repository=None) -> None:
        self._manager = goal_manager
        self._repo = goal_repository
        # In-memory store for demo/testing when managers are not wired
        self._goals: dict[str, dict[str, Any]] = {}
        self._counter = 0

    @property
    def has_manager(self) -> bool:
        return self._manager is not None

    @property
    def has_repository(self) -> bool:
        return self._repo is not None

    def lookup_status(self, goal_id: str) -> str | None:
        """Read-only status lookup used by other adapters (e.g. run start)."""
        goal = self._goals.get(goal_id)
        return goal.get("status") if goal else None

    def _next_id(self) -> str:
        self._counter += 1
        return f"goal-{self._counter}"

    def _build_response(self, goal: dict[str, Any]) -> GoalResponse:
        return GoalResponse(
            goal_id=goal["goal_id"],
            title=goal["title"],
            objective=goal["objective"],
            status=goal.get("status", "active"),
            goal_kind=goal.get("goal_kind", "GENERAL"),
            priority=goal.get("priority", 5),
            created_at=goal.get("created_at", ""),
            updated_at=goal.get("updated_at", ""),
            # Defensively copied: callers must never be able to mutate our
            # internal goal state through the nested mutable containers.
            context=copy.deepcopy(goal.get("context", {})),
            constraints=copy.deepcopy(goal.get("constraints", [])),
            success_criteria=copy.deepcopy(goal.get("success_criteria", [])),
            creator=goal.get("creator"),
            owner=goal.get("owner"),
        )

    def create(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        payload = request.payload
        title = payload.get("title", "").strip()
        objective = payload.get("objective", "").strip()
        if not title:
            return _error(
                request,
                AgentRuntimeApiErrorCode.VALIDATION_ERROR,
                "title must not be empty",
            )
        if not objective:
            return _error(
                request,
                AgentRuntimeApiErrorCode.VALIDATION_ERROR,
                "objective must not be empty",
            )
        gid = self._next_id()
        goal = {
            "goal_id": gid,
            "title": title,
            "objective": objective,
            "goal_kind": payload.get("goal_kind", "GENERAL"),
            "priority": payload.get("priority", 5),
            "status": "active",
            "context": payload.get("context", {}),
            "constraints": payload.get("constraints", []),
            "success_criteria": payload.get("success_criteria", []),
            "creator": context.actor,
            "owner": context.actor,
            "created_at": request.timestamp,
            "updated_at": request.timestamp,
        }
        self._goals[gid] = goal
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._build_response(goal),
            request_id=request.request_id,
        )

    def get(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        goal_id = request.payload.get("goal_id", "")
        goal = self._goals.get(goal_id)
        if not goal:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Goal {goal_id} not found"
            )
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._build_response(goal),
            request_id=request.request_id,
        )

    def list(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        goals = list(self._goals.values())
        goals.sort(key=lambda g: g.get("priority", 0))
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data={
                "items": [self._build_response(g) for g in goals],
                "total": len(goals),
            },
            request_id=request.request_id,
        )

    def update(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        payload = request.payload
        goal_id = payload.get("goal_id", "")
        goal = self._goals.get(goal_id)
        if not goal:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Goal {goal_id} not found"
            )
        if goal.get("status") == "archived":
            return _error(
                request,
                AgentRuntimeApiErrorCode.STATE_ERROR,
                "Cannot mutate archived goal",
            )
        for field in ("title", "objective", "priority", "context"):
            if field in payload and payload[field] is not None:
                goal[field] = payload[field]
        goal["updated_at"] = request.timestamp
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._build_response(goal),
            request_id=request.request_id,
        )

    def prioritize(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        goal_id = request.payload.get("goal_id", "")
        priority = request.payload.get("new_priority", 5)
        goal = self._goals.get(goal_id)
        if not goal:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Goal {goal_id} not found"
            )
        if goal.get("status") == "archived":
            return _error(
                request,
                AgentRuntimeApiErrorCode.STATE_ERROR,
                "Cannot prioritize archived goal",
            )
        goal["priority"] = max(0, priority)
        goal["updated_at"] = request.timestamp
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._build_response(goal),
            request_id=request.request_id,
        )

    def pause(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return self._transition(
            request,
            "paused",
            allowed_from={"active", "running"},
            denied_if={"completed", "cancelled"},
        )

    def resume(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return self._transition(
            request,
            "active",
            allowed_from={"paused"},
            denied_if={"completed", "cancelled"},
        )

    def cancel(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return self._transition(
            request,
            "cancelled",
            allowed_from={"active", "paused", "running"},
            denied_if={"completed"},
        )

    def _transition(
        self,
        request: AgentRuntimeApiRequest,
        target: str,
        allowed_from: set[str],
        denied_if: set[str],
    ) -> AgentRuntimeApiResponse:
        goal_id = request.payload.get("goal_id", "")
        goal = self._goals.get(goal_id)
        if not goal:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Goal {goal_id} not found"
            )
        current = goal.get("status", "active")
        if current in denied_if:
            return _error(
                request,
                AgentRuntimeApiErrorCode.STATE_ERROR,
                f"Cannot {target} a {current} goal",
            )
        if allowed_from and current not in allowed_from:
            return _error(
                request,
                AgentRuntimeApiErrorCode.STATE_ERROR,
                f"Cannot {target} from status {current}",
            )
        goal["status"] = target
        goal["updated_at"] = request.timestamp
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._build_response(goal),
            request_id=request.request_id,
        )


# ── AgentRunApiAdapter ──────────────────────────────────────────────────────


class AgentRunApiAdapter:
    """Run API adapter.

    Optionally validates the referenced goal via ``goal_lookup`` (a callable
    returning the goal's status string, or ``None`` if it doesn't exist) so a
    run can never be started against a missing, paused or cancelled goal.
    """

    def __init__(self, goal_lookup=None) -> None:
        self._goal_lookup = goal_lookup
        self._runs: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"run-{self._counter}"

    def _to_response(self, run: dict[str, Any]) -> AgentRunResponse:
        return AgentRunResponse(
            run_id=run["run_id"],
            goal_id=run["goal_id"],
            status=run.get("status", "active"),
            autonomy_level=run.get("autonomy_level", 1),
            created_at=run.get("created_at", ""),
            updated_at=run.get("updated_at", ""),
            current_step=run.get("current_step"),
            iteration=run.get("iteration", 0),
            error=run.get("error"),
        )

    def start(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        goal_id = request.payload.get("goal_id", "")
        if self._goal_lookup is not None:
            goal_status = self._goal_lookup(goal_id)
            if goal_status is None:
                return _error(
                    request,
                    AgentRuntimeApiErrorCode.NOT_FOUND,
                    f"Goal {goal_id} not found",
                )
            if goal_status == "paused":
                return _error(
                    request,
                    AgentRuntimeApiErrorCode.STATE_ERROR,
                    f"Cannot start run: goal {goal_id} is paused",
                )
            if goal_status == "cancelled":
                return _error(
                    request,
                    AgentRuntimeApiErrorCode.STATE_ERROR,
                    f"Cannot start run: goal {goal_id} is cancelled",
                )
        run_id = self._next_id()
        run = {
            "run_id": run_id,
            "goal_id": goal_id,
            "status": "running",
            "autonomy_level": request.payload.get("autonomy_level", 1),
            "created_at": request.timestamp,
            "updated_at": request.timestamp,
            "iteration": 0,
        }
        self._runs[run_id] = run
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(run),
            request_id=request.request_id,
        )

    def get(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        run_id = request.payload.get("run_id", "")
        run = self._runs.get(run_id)
        if not run:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Run {run_id} not found"
            )
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(run),
            request_id=request.request_id,
        )

    def list(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        runs = list(self._runs.values())
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data={"runs": [self._to_response(r) for r in runs], "total": len(runs)},
            request_id=request.request_id,
        )

    def pause(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return self._run_transition(
            request,
            "paused",
            allowed={"running"},
            terminal={"completed", "cancelled", "failed"},
        )

    def resume(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return self._run_transition(
            request,
            "running",
            allowed={"paused"},
            terminal={"completed", "cancelled", "failed"},
        )

    def cancel(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return self._run_transition(
            request,
            "cancelled",
            allowed={"running", "paused", "active"},
            terminal={"completed", "failed"},
        )

    def _run_transition(
        self,
        request: AgentRuntimeApiRequest,
        target: str,
        allowed: set[str],
        terminal: set[str],
    ) -> AgentRuntimeApiResponse:
        run_id = request.payload.get("run_id", "")
        run = self._runs.get(run_id)
        if not run:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Run {run_id} not found"
            )
        current = run.get("status", "running")
        if current in terminal:
            return _error(
                request,
                AgentRuntimeApiErrorCode.STATE_ERROR,
                f"Cannot modify terminal run {current}",
            )
        if current not in allowed:
            return _error(
                request,
                AgentRuntimeApiErrorCode.STATE_ERROR,
                f"Cannot {target} from {current}",
            )
        run["status"] = target
        run["updated_at"] = request.timestamp
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(run),
            request_id=request.request_id,
        )


# ── ApprovalApiAdapter ──────────────────────────────────────────────────────


class ApprovalApiAdapter:
    """Approval API adapter.

    Approval requests can only be created via ``request_approval`` (an
    internal seam meant for runtime flows, e.g. a goal/run needing human
    sign-off) - there is no public ``approval.create``/``approval.request``
    API operation. This is intentional: an external API caller must never be
    able to manufacture a pending approval and then approve its own request.
    """

    def __init__(self) -> None:
        self._approvals: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"approval-{self._counter}"

    def request_approval(
        self,
        requirement: dict[str, Any] | None = None,
        assigned_to: str | None = None,
        expires_at: str | None = None,
        created_at: str | None = None,
    ) -> ApprovalResponse:
        aid = self._next_id()
        a = {
            "approval_id": aid,
            "status": "pending",
            "requirement": copy.deepcopy(requirement) if requirement else None,
            "assigned_to": assigned_to,
            "created_at": created_at or _now_iso(),
            "expires_at": expires_at,
        }
        self._approvals[aid] = a
        return self._to_response(a)

    def _to_response(self, a: dict[str, Any]) -> ApprovalResponse:
        return ApprovalResponse(
            approval_id=a["approval_id"],
            status=a.get("status", "pending"),
            requirement=copy.deepcopy(a.get("requirement")),
            decision=a.get("decision"),
            actor=a.get("actor"),
            comment=a.get("comment"),
            created_at=a.get("created_at", ""),
            expires_at=a.get("expires_at"),
            resolved_at=a.get("resolved_at"),
        )

    def list(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        pending = [v for v in self._approvals.values() if v.get("status") == "pending"]
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data={
                "approvals": [self._to_response(a) for a in pending],
                "total": len(pending),
            },
            request_id=request.request_id,
        )

    def get(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        aid = request.payload.get("approval_id", "")
        a = self._approvals.get(aid)
        if not a:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Approval {aid} not found"
            )
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(a),
            request_id=request.request_id,
        )

    def approve(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return self._decide(request, context, "approved")

    def reject(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return self._decide(request, context, "rejected")

    def _decide(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
        decision: str,
    ) -> AgentRuntimeApiResponse:
        aid = request.payload.get("approval_id", "")
        a = self._approvals.get(aid)
        if not a:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Approval {aid} not found"
            )
        if a.get("status") != "pending":
            return _error(
                request, AgentRuntimeApiErrorCode.CONFLICT, "Approval already decided"
            )
        expires_at = a.get("expires_at")
        if expires_at and datetime.now(timezone.utc) > datetime.fromisoformat(
            expires_at
        ):
            return _error(
                request,
                AgentRuntimeApiErrorCode.STATE_ERROR,
                "Approval request has expired",
            )
        assigned_to = a.get("assigned_to")
        if assigned_to is not None and assigned_to != context.actor:
            return _error(
                request,
                AgentRuntimeApiErrorCode.PERMISSION_DENIED,
                f"Actor {context.actor} is not authorized to decide this approval",
            )
        a["status"] = decision
        a["decision"] = decision
        a["actor"] = context.actor
        a["comment"] = request.payload.get("comment") or request.payload.get("reason")
        a["resolved_at"] = request.timestamp
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(a),
            request_id=request.request_id,
        )


# ── BudgetApiAdapter ────────────────────────────────────────────────────────


class BudgetApiAdapter:
    """Budget API adapter."""

    def __init__(self) -> None:
        self._budgets: dict[str, dict[str, Any]] = {}
        self._reservations: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"budget-{self._counter}"

    def _get_or_create_budget(
        self, bid: str, unit: str | None = None
    ) -> dict[str, Any]:
        if bid not in self._budgets:
            self._budgets[bid] = {
                "budget_id": bid,
                "limit": 100.0,
                "used": 0.0,
                "reserved": 0.0,
                "unit": unit or "iteration",
            }
        return self._budgets[bid]

    def _to_response(
        self, b: dict[str, Any], reservation: dict | None = None
    ) -> BudgetResponse:
        return BudgetResponse(
            budget_id=b["budget_id"],
            status="active",
            limit=b["limit"],
            used=b["used"],
            reserved=b["reserved"],
            unit=b.get("unit", "iteration"),
            reservation=copy.deepcopy(reservation) if reservation else None,
        )

    def get(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        bid = request.payload.get("budget_id", "")
        b = self._get_or_create_budget(bid)
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(b),
            request_id=request.request_id,
        )

    def reserve(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        bid = request.payload.get("budget_id", "")
        amount = request.payload.get("amount", 0.0)
        unit = request.payload.get("unit", "iteration")
        reservation_id = request.payload.get("reservation_id") or str(uuid.uuid4())
        if amount <= 0:
            return _error(
                request,
                AgentRuntimeApiErrorCode.VALIDATION_ERROR,
                "Amount must be positive",
            )
        b = self._get_or_create_budget(bid, unit=unit)
        if b["unit"] != unit:
            return _error(
                request,
                AgentRuntimeApiErrorCode.VALIDATION_ERROR,
                f"Incompatible unit: budget uses {b['unit']}, got {unit}",
            )
        available = b["limit"] - b["used"] - b["reserved"]
        if amount > available:
            return _error(
                request,
                AgentRuntimeApiErrorCode.BUDGET_EXCEEDED,
                f"Requested {amount} exceeds available {available}",
            )
        b["reserved"] += amount
        self._reservations[reservation_id] = {"budget_id": bid, "amount": amount}
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(
                b, reservation={"reservation_id": reservation_id, "amount": amount}
            ),
            request_id=request.request_id,
        )

    def release(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        bid = request.payload.get("budget_id", "")
        reservation_id = request.payload.get("reservation_id", "")
        amount = request.payload.get("amount", 0.0)
        r = self._reservations.get(reservation_id)
        if not r or r["budget_id"] != bid:
            return _error(
                request,
                AgentRuntimeApiErrorCode.NOT_FOUND,
                f"Reservation {reservation_id} not found",
            )
        if amount > r["amount"]:
            return _error(
                request,
                AgentRuntimeApiErrorCode.VALIDATION_ERROR,
                "Cannot release more than reserved",
            )
        b = self._budgets.get(bid, {})
        b["reserved"] = max(0, b.get("reserved", 0) - amount)
        r["amount"] -= amount
        remaining = r["amount"]
        if remaining <= 0:
            del self._reservations[reservation_id]
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(
                b, reservation={"reservation_id": reservation_id, "amount": remaining}
            ),
            request_id=request.request_id,
        )


# ── TraceApiAdapter ─────────────────────────────────────────────────────────


class TraceApiAdapter:
    """Trace API adapter re-using 9.19 trace service when wired.

    Records form a hash chain (each record's hash covers its data and the
    previous record's hash), so ``verify`` can genuinely detect tampering
    instead of always reporting a fixed status.
    """

    def __init__(self, trace_service=None) -> None:
        self._service = trace_service
        self._traces: dict[str, dict[str, Any]] = {}
        self._counter = 0

    @property
    def has_service(self) -> bool:
        return self._service is not None

    def _next_id(self) -> str:
        self._counter += 1
        return f"trace-{self._counter}"

    def _record_hash(self, prev_hash: str | None, data: Any) -> str:
        blob = json.dumps(
            {"prev_hash": prev_hash, "data": data}, sort_keys=True, default=str
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def create_trace(
        self,
        run_id: str | None = None,
        goal_id: str | None = None,
        owner: str | None = None,
        created_at: str | None = None,
    ) -> TraceResponse:
        """Internal seam: register a new trace. Not a public API operation."""
        tid = self._next_id()
        t = {
            "trace_id": tid,
            "run_id": run_id,
            "goal_id": goal_id,
            "owner": owner,
            "status": "open",
            "records": [],
            "created_at": created_at or _now_iso(),
        }
        self._traces[tid] = t
        return self._to_response(t)

    def append_record(self, trace_id: str, data: Any) -> None:
        """Internal seam: append a hash-chained record. Not a public API operation."""
        t = self._traces.get(trace_id)
        if t is None:
            raise AgentRuntimeApiNotFoundError(f"Trace {trace_id} not found")
        prev_hash = t["records"][-1]["hash"] if t["records"] else None
        record_hash = self._record_hash(prev_hash, data)
        t["records"].append({"data": data, "hash": record_hash})

    def _to_response(self, t: dict[str, Any], export_data: Any = None) -> TraceResponse:
        return TraceResponse(
            trace_id=t["trace_id"],
            run_id=t.get("run_id"),
            goal_id=t.get("goal_id"),
            status=t.get("status", "open"),
            record_count=len(t.get("records", [])),
            created_at=t.get("created_at", ""),
            finalized_at=t.get("finalized_at"),
            integrity_status=t.get("integrity_status"),
            export_format=t.get("export_format"),
            export_data=export_data,
        )

    def _authorize(
        self,
        request: AgentRuntimeApiRequest,
        context: AgentRuntimeApiContext,
        t: dict[str, Any],
    ) -> AgentRuntimeApiResponse | None:
        owner = t.get("owner")
        if owner is not None and owner != context.actor:
            return _error(
                request,
                AgentRuntimeApiErrorCode.PERMISSION_DENIED,
                "Actor is not authorized to access this trace",
            )
        return None

    def get(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        tid = request.payload.get("trace_id", "")
        t = self._traces.get(tid)
        if not t:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Trace {tid} not found"
            )
        denied = self._authorize(request, context, t)
        if denied is not None:
            return denied
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(t),
            request_id=request.request_id,
        )

    def list(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        traces = [
            t for t in self._traces.values() if t.get("owner") in (None, context.actor)
        ]
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data={
                "traces": [self._to_response(t) for t in traces],
                "total": len(traces),
            },
            request_id=request.request_id,
        )

    def verify(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        tid = request.payload.get("trace_id", "")
        t = self._traces.get(tid)
        if not t:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Trace {tid} not found"
            )
        denied = self._authorize(request, context, t)
        if denied is not None:
            return denied
        records = t.get("records", [])
        status = "empty"
        prev_hash = None
        for rec in records:
            expected = self._record_hash(prev_hash, rec.get("data"))
            if rec.get("hash") != expected:
                status = "tampered"
                break
            prev_hash = rec["hash"]
        else:
            if records:
                status = "verified"
        t["integrity_status"] = status
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(t),
            request_id=request.request_id,
        )

    def export(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        tid = request.payload.get("trace_id", "")
        fmt = request.payload.get("format", "JSON")
        t = self._traces.get(tid)
        if not t:
            return _error(
                request, AgentRuntimeApiErrorCode.NOT_FOUND, f"Trace {tid} not found"
            )
        denied = self._authorize(request, context, t)
        if denied is not None:
            return denied
        # Never let chain-of-thought or other sensitive fields leave through
        # an exported blob, since the outer redaction middleware cannot see
        # inside an already-serialized string.
        safe_records = _redact(t.get("records", []))
        fmt_upper = fmt.upper()
        if fmt_upper == "JSON":
            export_data = json.dumps(
                {
                    **{k: v for k, v in t.items() if k != "records"},
                    "records": safe_records,
                },
                default=str,
            )
        elif fmt_upper == "JSONL":
            export_data = json.dumps(
                {"trace_id": tid, "records": safe_records}, default=str
            )
        else:
            export_data = {"trace_id": tid, "summary": f"{len(safe_records)} records"}
        t["export_format"] = fmt_upper
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=self._to_response(t, export_data),
            request_id=request.request_id,
        )


# ── RuntimeEventApiAdapter ──────────────────────────────────────────────────


class RuntimeEventApiAdapter:
    """Runtime Event API adapter, validated against the 9.20 event registry.

    The events list is append-only: publish/replay only ever add new entries,
    never mutate or remove existing ones. Delivery is reported as
    ``"recorded"`` (never a fabricated ``"delivered"``) since this in-memory
    adapter has no real subscriber to confirm delivery against; genuine
    delivery confirmation requires the real event bus (``event_bus``) once
    wired.
    """

    def __init__(self, event_bus=None) -> None:
        self._bus = event_bus
        self._events: list[dict[str, Any]] = []
        self._dead_letters: list[dict[str, Any]] = []
        self._dedup_index: dict[str, str] = {}
        self._counter = 0
        self._dl_counter = 0

    @property
    def has_bus(self) -> bool:
        return self._bus is not None

    def _next_id(self) -> str:
        self._counter += 1
        return f"event-{self._counter}"

    def _next_dl_id(self) -> str:
        self._dl_counter += 1
        return f"dead-letter-{self._dl_counter}"

    def _do_publish(
        self, event_type: str, payload: dict[str, Any], sensitivity: str
    ) -> dict[str, Any]:
        dedup_key = payload.get("dedup_key")
        if dedup_key and dedup_key in self._dedup_index:
            existing_id = self._dedup_index[dedup_key]
            return next(e for e in self._events if e["event_id"] == existing_id)
        ev = {
            "event_id": self._next_id(),
            "event_type": event_type,
            "category": get_event_category(event_type).value,
            "sensitivity": sensitivity,
            "timestamp": _now_iso(),
            "delivery": {"status": "recorded"},
            "original_event_id": None,
        }
        self._events.append(ev)
        if dedup_key:
            self._dedup_index[dedup_key] = ev["event_id"]
        return ev

    def publish_internal(
        self,
        event_type: str,
        payload: dict[str, Any],
        sensitivity: str = "internal",
    ) -> EventResponse:
        """Publish without going through the router. Used for internal
        lifecycle events (goal/run/approval/budget) emitted by the service."""
        if not is_registered_event_type(event_type):
            raise AgentRuntimeApiValidationError(f"Unknown event type: {event_type}")
        if _contains_unsafe_content(payload):
            raise AgentRuntimeApiValidationError("Payload contains unsafe content")
        ev = self._do_publish(event_type, payload, sensitivity)
        return EventResponse(**ev)

    def publish(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        payload = request.payload
        event_type = payload.get("event_type", "")
        if not event_type:
            return _error(
                request,
                AgentRuntimeApiErrorCode.VALIDATION_ERROR,
                "event_type required",
            )
        try:
            ev_response = self.publish_internal(
                event_type, payload, payload.get("sensitivity", "internal")
            )
        except AgentRuntimeApiValidationError as exc:
            return _error(request, AgentRuntimeApiErrorCode.VALIDATION_ERROR, str(exc))
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=ev_response,
            request_id=request.request_id,
        )

    def list(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data={
                "events": [EventResponse(**e) for e in self._events],
                "total": len(self._events),
            },
            request_id=request.request_id,
        )

    def replay(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        event_type = request.payload.get("event_type")
        replay_mode = request.payload.get("replay_mode", "skip_delivered")
        if replay_mode not in ("skip_delivered", "force_all", "dead_letter_only"):
            return _error(
                request,
                AgentRuntimeApiErrorCode.VALIDATION_ERROR,
                f"invalid replay_mode: {replay_mode}",
            )
        source = (
            self._dead_letters if replay_mode == "dead_letter_only" else self._events
        )
        to_replay = [
            e for e in source if event_type is None or e.get("event_type") == event_type
        ]
        replayed: list[dict[str, Any]] = []
        for original in to_replay:
            new_ev = {
                "event_id": self._next_id(),
                "event_type": original["event_type"],
                "category": original.get("category")
                or get_event_category(original["event_type"]).value,
                "sensitivity": original.get("sensitivity", "internal"),
                "timestamp": _now_iso(),
                "delivery": {"status": "recorded"},
                "original_event_id": original.get("original_event_id")
                or original.get("event_id"),
            }
            self._events.append(new_ev)
            replayed.append(new_ev)
            if replay_mode == "dead_letter_only":
                original["replayed"] = True
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data={
                "replayed": len(replayed),
                "events": [EventResponse(**e) for e in replayed],
            },
            request_id=request.request_id,
        )

    def route_to_dead_letter(self, event_id: str, reason: str) -> EventResponse:
        """Internal seam: record a delivery failure instead of dropping it
        silently. Not a public API operation."""
        original = next((e for e in self._events if e["event_id"] == event_id), None)
        if original is None:
            raise AgentRuntimeApiNotFoundError(f"Event {event_id} not found")
        dl_id = self._next_dl_id()
        entry = {
            "dead_letter_id": dl_id,
            "event_id": event_id,
            "event_type": original["event_type"],
            "category": original.get("category"),
            "sensitivity": original.get("sensitivity", "internal"),
            "timestamp": _now_iso(),
            "reason": reason,
            "original_event_id": event_id,
            "replayed": False,
        }
        self._dead_letters.append(entry)
        return EventResponse(
            event_id=dl_id,
            event_type=original["event_type"],
            category=entry["category"] or "unknown",
            sensitivity=entry["sensitivity"],
            dead_letter_id=dl_id,
            original_event_id=event_id,
        )

    def list_dead_letters(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data={
                "dead_letters": list(self._dead_letters),
                "total": len(self._dead_letters),
            },
            request_id=request.request_id,
        )

    def replay_dead_letter(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        dlid = request.payload.get("dead_letter_id", "")
        entry = next(
            (d for d in self._dead_letters if d["dead_letter_id"] == dlid), None
        )
        if entry is None:
            return _error(
                request,
                AgentRuntimeApiErrorCode.NOT_FOUND,
                f"Dead letter {dlid} not found",
            )
        new_ev = {
            "event_id": self._next_id(),
            "event_type": entry["event_type"],
            "category": entry.get("category")
            or get_event_category(entry["event_type"]).value,
            "sensitivity": entry.get("sensitivity", "internal"),
            "timestamp": _now_iso(),
            "delivery": {"status": "recorded"},
            "original_event_id": entry.get("original_event_id"),
        }
        self._events.append(new_ev)
        entry["replayed"] = True
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data={
                "dead_letter_id": dlid,
                "replayed": True,
                "event": EventResponse(**new_ev),
            },
            request_id=request.request_id,
        )


# ── RuntimeSystemApiAdapter ─────────────────────────────────────────────────


class RuntimeSystemApiAdapter:
    """System health and stats adapter.

    Only ever reports a component as available if something explicitly told
    it so via ``set_component_wired`` - it never invents managers/repositories
    that were never actually configured on the service.
    """

    _KNOWN_COMPONENTS: ClassVar[tuple[str, ...]] = (
        "goal_manager",
        "goal_repository",
        "event_bus",
        "trace_service",
    )

    def __init__(self) -> None:
        self._api_errors = 0
        self._ops_executed = 0
        self._latency_acc_ms = 0.0
        self._latency_count = 0
        self._components: dict[str, bool] = dict.fromkeys(self._KNOWN_COMPONENTS, False)

    def set_component_wired(self, name: str, wired: bool) -> None:
        self._components[name] = wired

    def set_unavailable(self, components: list[str]) -> None:
        """Convenience: mark named components as unavailable."""
        for name in components:
            self._components[name] = False

    def record_error(self) -> None:
        self._api_errors += 1

    def record_operation(self, latency_ms: float) -> None:
        self._ops_executed += 1
        self._latency_acc_ms += latency_ms
        self._latency_count += 1

    def _unavailable(self) -> list[str]:
        return [name for name, wired in self._components.items() if not wired]

    def health(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        unavailable = self._unavailable()
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=RuntimeHealthResponse(
                status="healthy" if not unavailable else "degraded",
                version="9.21.0",
                managers={"goal": self._status_of("goal_manager")},
                repositories={"goal": self._status_of("goal_repository")},
                event_bus=self._status_of("event_bus"),
                trace_service=self._status_of("trace_service"),
                warnings=[],
            ),
            request_id=request.request_id,
        )

    def stats(
        self, request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data=RuntimeStatsResponse(
                goals_by_status={
                    "active": 0,
                    "paused": 0,
                    "completed": 0,
                    "cancelled": 0,
                },
                runs_by_status={"running": 0, "paused": 0, "completed": 0},
                approvals_pending=0,
                api_errors=self._api_errors,
                operations_executed=self._ops_executed,
                latency_accumulated_ms=self._latency_acc_ms,
                latency_count=self._latency_count,
                unavailable=self._unavailable(),
            ),
            request_id=request.request_id,
        )

    def _status_of(self, name: str) -> str:
        return "available" if self._components.get(name, False) else "unavailable"
