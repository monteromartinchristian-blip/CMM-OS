"""Composition of the web and computer capabilities over the model seam."""

from __future__ import annotations

import threading
from queue import Queue
from typing import Any, Iterator

from cmm.capabilities.events import CapabilityEvent, CapabilityRequest
from cmm.computer.contracts import ApprovalProposal, ComputerUseLimits
from cmm.computer.loop import ComputerUseService
from cmm.web.contracts import ResearchLimits
from cmm.web.research import WebResearchService
from cmm.web.service import WebSearchService

__all__ = ["CapabilityExecution"]

_DEFAULT_APPROVAL_TIMEOUT = 300.0


class _Final:
    __slots__ = ("result",)

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result


class _Error:
    __slots__ = ("error",)

    def __init__(self, error: BaseException) -> None:
        self.error = error


class _FacadeApprovalGate:
    """Bridges loop approvals to the facade's resolve_approval channel."""

    def __init__(self, execution: "CapabilityExecution") -> None:
        self._execution = execution

    def request(self, proposal: ApprovalProposal) -> str:
        return self._execution._await_approval(proposal)


def _unused_plan(*_args: Any, **_kwargs: Any) -> str:  # pragma: no cover
    return ""


class CapabilityExecution:
    """One normalized capability execution surface over the canonical seam.

    ``stream`` yields product events in real time (tool activity, approvals,
    observations, message deltas) and finishes with one ``run.summary``
    carrying the mode and the citations to persist.  Approvals are resolved
    from the product side through :meth:`resolve_approval`.
    """

    def __init__(
        self,
        *,
        executor: Any,
        search_service: WebSearchService | None = None,
        computer_runtime: Any | None = None,
        approval_timeout: float | None = None,
    ) -> None:
        self._executor = executor
        self._search = search_service or WebSearchService()
        self._computer_runtime = computer_runtime
        self._approval_timeout = (
            _DEFAULT_APPROVAL_TIMEOUT
            if approval_timeout is None
            else float(approval_timeout)
        )
        self._approvals: dict[str, tuple[threading.Event, dict[str, str]]] = {}
        self._approvals_lock = threading.Lock()

    # ── status ────────────────────────────────────────────────────────────

    def capability_status(self) -> dict[str, Any]:
        computer = ComputerUseService(
            runtime=self._runtime(), plan=_unused_plan
        ).status()
        return {"web_search": {"available": True}, "computer": computer}

    def _runtime(self) -> Any:
        if self._computer_runtime is None:
            from cmm.computer.runtime_macos import MacComputerRuntime

            self._computer_runtime = MacComputerRuntime()
        return self._computer_runtime

    # ── approvals ─────────────────────────────────────────────────────────

    def resolve_approval(self, tool_run_id: str, decision: str) -> bool:
        if decision not in ("allow_once", "reject"):
            raise ValueError("decision must be allow_once or reject")
        with self._approvals_lock:
            entry = self._approvals.get(tool_run_id)
            if entry is None:
                return False
            waiter, holder = entry
        holder["verdict"] = decision
        waiter.set()
        return True

    def _await_approval(self, proposal: ApprovalProposal) -> str:
        waiter = threading.Event()
        holder = {"verdict": "reject"}
        with self._approvals_lock:
            self._approvals[proposal.tool_run_id] = (waiter, holder)
        try:
            waiter.wait(timeout=self._approval_timeout)
        finally:
            with self._approvals_lock:
                self._approvals.pop(proposal.tool_run_id, None)
        return holder["verdict"]

    # ── execution ─────────────────────────────────────────────────────────

    def _complete(self, resolved: Any, cancel_event: threading.Event | None):
        def complete(
            prompt: str, system: str | None, cancel_event: threading.Event | None = None
        ) -> str:
            parts: list[str] = []
            for delta in self._executor.stream(
                resolved,
                prompt=prompt,
                system=system,
                history=(),
                cancel_event=cancel_event,
            ):
                parts.append(delta)
            return "".join(parts)

        return complete

    def stream(
        self,
        resolved: Any,
        *,
        prompt: str,
        system: str | None = None,
        history: tuple[tuple[str, str], ...] = (),
        cancel_event: threading.Event | None = None,
        capabilities: CapabilityRequest | None = None,
    ) -> Iterator[CapabilityEvent]:
        caps = capabilities or CapabilityRequest()
        queue: Queue = Queue()

        def emit(kind: str, data: dict[str, Any]) -> None:
            queue.put(CapabilityEvent(kind, dict(data)))

        def worker() -> None:
            try:
                result = self._run(
                    resolved,
                    prompt=prompt,
                    system=system,
                    history=history,
                    caps=caps,
                    emit=emit,
                    cancel_event=cancel_event,
                )
                queue.put(_Final(result))
            except BaseException as error:  # noqa: BLE001 - bridged to the consumer
                queue.put(_Error(error))

        thread = threading.Thread(
            target=worker, daemon=True, name="cmm-capability-run"
        )
        thread.start()
        while True:
            item = queue.get()
            if isinstance(item, _Final):
                answer = str(item.result.get("answer", ""))
                if answer:
                    yield CapabilityEvent("message.delta", {"delta": answer})
                summary = {
                    key: value
                    for key, value in item.result.items()
                    if key != "answer"
                }
                yield CapabilityEvent("run.summary", summary)
                return
            if isinstance(item, _Error):
                raise item.error
            yield item

    def _run(
        self,
        resolved: Any,
        *,
        prompt: str,
        system: str | None,
        history: tuple[tuple[str, str], ...],
        caps: CapabilityRequest,
        emit: Any,
        cancel_event: threading.Event | None,
    ) -> dict[str, Any]:
        complete = self._complete(resolved, cancel_event)

        if caps.computer_use:
            service = ComputerUseService(
                runtime=self._runtime(),
                plan=complete,
                approval_gate=_FacadeApprovalGate(self),
                emit=emit,
                limits=ComputerUseLimits(),
                web_search=self._search if caps.web_search != "off" else None,
            )
            outcome = service.run_task(prompt, cancel_event=cancel_event)
            digest = "\n".join(f"- {action}" for action in outcome.actions)
            answer = outcome.summary
            if digest:
                answer = f"{answer}\n\nAcciones realizadas:\n{digest}"
            return {
                "mode": "computer",
                "answer": answer,
                "citations": [],
                "warnings": list(outcome.warnings),
                "steps": outcome.steps,
                "approvals": outcome.approvals,
                "rejections": outcome.rejections,
            }

        if caps.web_search in ("auto", "on"):
            research = WebResearchService(
                search_service=self._search,
                complete=complete,
                emit=emit,
                limits=ResearchLimits(),
            )
            outcome = research.research(
                prompt, system=system, history=history, cancel_event=cancel_event
            )
            citations = [
                {
                    "index": citation.index,
                    "title": citation.title,
                    "url": citation.url,
                    "domain": citation.domain,
                    "snippet": citation.snippet,
                    "inspected": citation.inspected,
                    "retrieved_at": (
                        citation.retrieved_at.isoformat()
                        if citation.retrieved_at is not None
                        else None
                    ),
                }
                for citation in outcome.citations
            ]
            return {
                "mode": "web",
                "answer": outcome.answer,
                "citations": citations,
                "warnings": list(outcome.warnings),
                "searches": outcome.searches,
                "reads": outcome.reads,
            }

        for delta in self._executor.stream(
            resolved,
            prompt=prompt,
            system=system,
            history=history,
            cancel_event=cancel_event,
        ):
            emit("message.delta", {"delta": delta})
        return {"mode": "chat", "answer": "", "citations": []}
