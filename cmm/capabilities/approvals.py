"""Canonical approval integration for the capability loops.

The Phase-11 :class:`~cmm.agent_runtime.approval_service.ApprovalService` owns
the approval lifecycle (request, decision, allow-once consumption, rejection,
cancellation).  The computer policy only decides *whether* an action requires
approval; this gate adapts the canonical service to the capability loops and
to the product transport (Hub SSE/REST).  No parallel approval authority.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from cmm.agent_runtime.approval_service import ApprovalService
from cmm.computer.contracts import ApprovalProposal

__all__ = ["CanonicalApprovalGate"]

_DEFAULT_TIMEOUT = 300.0


class CanonicalApprovalGate:
    """One approval gate over the canonical ApprovalService."""

    def __init__(
        self,
        *,
        approval_service: ApprovalService | None = None,
        transport: Callable[[str, ApprovalProposal], str] | None = None,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
        timeout: float | None = None,
        processing: str = "local",
    ) -> None:
        self._service = approval_service or ApprovalService()
        self._transport = transport
        self._emit = emit or (lambda kind, data: None)
        self._timeout = _DEFAULT_TIMEOUT if timeout is None else float(timeout)
        self._processing = processing
        self._pending: dict[str, tuple[threading.Event, dict[str, str]]] = {}
        self._by_tool_run: dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def service(self) -> ApprovalService:
        return self._service

    def request(self, proposal: ApprovalProposal) -> str:
        """Run one canonical approval lifecycle; returns allow_once|reject."""

        request = self._service.create_request(
            title=proposal.action_description,
            description=f"{proposal.reason} Consecuencia: {proposal.consequence}",
            requested_by="cmm-capabilities",
            reason_codes=("computer_action_sensitive",),
            risk_level=(
                "high"
                if proposal.egress == "screen_content" and self._processing == "remote"
                else "medium"
            ),
            expected_effects=(proposal.action_description,),
            possible_side_effects=(proposal.consequence,),
            metadata={
                "app": proposal.app,
                "egress": proposal.egress,
                "tool_run_id": proposal.tool_run_id,
                "processing": self._processing,
            },
        )
        waiter = threading.Event()
        holder = {"verdict": "reject"}
        with self._lock:
            self._pending[request.id] = (waiter, holder)
            self._by_tool_run[proposal.tool_run_id] = request.id
        self._emit(
            "approval.requested",
            {
                "tool_run_id": proposal.tool_run_id,
                "approval_id": request.id,
                "capability": "computer.use",
                "approval": {
                    "action": proposal.action_description,
                    "app": proposal.app,
                    "reason": proposal.reason,
                    "consequence": proposal.consequence,
                    "egress": proposal.egress,
                    "processing": self._processing,
                },
            },
        )
        try:
            if self._transport is not None:
                verdict = self._transport(request.id, proposal)
                if verdict in ("allow_once", "reject"):
                    holder["verdict"] = verdict
                else:
                    waiter.wait(timeout=self._timeout)
            else:
                waiter.wait(timeout=self._timeout)
        finally:
            with self._lock:
                self._pending.pop(request.id, None)
                self._by_tool_run.pop(proposal.tool_run_id, None)

        verdict = holder["verdict"]
        if verdict == "allow_once":
            self._service.approve(request.id, actor_id="user", comment="allow once")
            try:
                self._service.validate_and_consume(
                    request.id,
                    actor_id="user",
                    session_id=proposal.tool_run_id,
                    one_time=True,
                )
            except Exception:  # noqa: BLE001 - canonical consumption refused
                verdict = "reject"
        elif verdict == "reject":
            self._service.reject(
                request.id, actor_id="user", comment="rejected by user"
            )
        else:
            self._service.cancel(
                request.id, actor_id="system", comment="approval timed out"
            )
            verdict = "reject"
        self._emit(
            "approval.resolved",
            {
                "tool_run_id": proposal.tool_run_id,
                "approval_id": request.id,
                "capability": "computer.use",
                "decision": "allow_once" if verdict == "allow_once" else "reject",
            },
        )
        return verdict

    def resolve(self, key: str, decision: str) -> bool:
        """Resolve one pending approval by canonical id or tool_run_id."""

        if decision not in ("allow_once", "reject"):
            raise ValueError("decision must be allow_once or reject")
        with self._lock:
            approval_id = key if key in self._pending else self._by_tool_run.get(key)
            entry = self._pending.get(approval_id) if approval_id else None
            if entry is None:
                return False
            waiter, holder = entry
        holder["verdict"] = decision
        waiter.set()
        return True
