"""Composition of the web and computer capabilities over the model seam."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from queue import Queue
from typing import Any

from cmm.capabilities.approvals import CanonicalApprovalGate
from cmm.capabilities.events import CapabilityEvent, CapabilityRequest
from cmm.computer.contracts import ComputerUseLimits
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


def _unused_plan(*_args: Any, **_kwargs: Any) -> str:  # pragma: no cover
    return ""


class CapabilityExecution:
    """One normalized capability execution surface over the canonical seam.

    ``stream`` yields product events in real time (tool activity, approvals,
    observations, message deltas) and finishes with one ``run.summary``
    carrying the mode, the processing locality and the citations to persist.
    Capability selection is intent-driven: with ``computer_use="auto"`` the
    planner decides whether the task needs the computer; approvals run through
    the canonical ApprovalService via :class:`CanonicalApprovalGate` and are
    resolved from the product side through :meth:`resolve_approval`.
    """

    def __init__(
        self,
        *,
        executor: Any,
        search_service: WebSearchService | None = None,
        computer_runtime: Any | None = None,
        approval_timeout: float | None = None,
        approval_service: Any | None = None,
    ) -> None:
        self._executor = executor
        self._search = search_service or WebSearchService()
        self._computer_runtime = computer_runtime
        self._approval_service = approval_service
        self._approval_timeout = (
            _DEFAULT_APPROVAL_TIMEOUT
            if approval_timeout is None
            else float(approval_timeout)
        )
        self._gates: list[CanonicalApprovalGate] = []
        self._gates_lock = threading.Lock()

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

    def _computer_available(self) -> bool:
        try:
            runtime = self._runtime()
            if not getattr(runtime, "available", lambda: False)():
                return False
            return bool(runtime.permissions().satisfied)
        except Exception:  # noqa: BLE001 - unavailable is the honest answer
            return False

    # ── approvals (canonical service owns the lifecycle) ─────────────────

    def resolve_approval(self, key: str, decision: str) -> bool:
        if decision not in ("allow_once", "reject"):
            raise ValueError("decision must be allow_once or reject")
        with self._gates_lock:
            gates = list(self._gates)
        for gate in gates:
            if gate.resolve(key, decision):
                return True
        return False

    def _make_gate(self, emit: Any, processing: str) -> CanonicalApprovalGate:
        gate = CanonicalApprovalGate(
            approval_service=self._approval_service,
            emit=emit,
            timeout=self._approval_timeout,
            processing=processing,
        )
        with self._gates_lock:
            self._gates.append(gate)
        return gate

    def _release_gate(self, gate: CanonicalApprovalGate | None) -> None:
        if gate is None:
            return
        with self._gates_lock:
            if gate in self._gates:
                self._gates.remove(gate)

    @staticmethod
    def _processing_for(resolved: Any) -> str:
        """Honest egress class of the lane that will process the context."""

        provider_id = getattr(resolved, "provider_id", None) or getattr(
            getattr(resolved, "provider", None), "id", ""
        )
        try:
            from cmm.model_execution.composition import lane_egress_class

            return lane_egress_class(str(provider_id))
        except Exception:  # noqa: BLE001 - conservative default
            return "remote"

    # ── execution ─────────────────────────────────────────────────────────

    def _complete(self, resolved: Any, cancel_event: threading.Event | None):
        def complete(
            prompt: str, system: str | None, cancel_event: threading.Event | None = None
        ) -> str:
            # Decision calls are bounded: a runaway reasoning model must
            # never stall a supervised tool loop.
            parts = list(
                self._executor.stream(
                    resolved,
                    prompt=prompt,
                    system=system,
                    history=(),
                    cancel_event=cancel_event,
                    max_tokens=800,
                )
            )
            return "".join(parts)

        return complete

    def _stream_call(self, resolved: Any):
        def stream(
            prompt: str, system: str | None, cancel_event: threading.Event | None = None
        ):
            return self._executor.stream(
                resolved,
                prompt=prompt,
                system=system,
                history=(),
                cancel_event=cancel_event,
                max_tokens=4000,
            )

        return stream

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

        thread = threading.Thread(target=worker, daemon=True, name="cmm-capability-run")
        thread.start()
        while True:
            item = queue.get()
            if isinstance(item, _Final):
                answer = str(item.result.get("answer", ""))
                if answer:
                    yield CapabilityEvent("message.delta", {"delta": answer})
                summary = {
                    key: value for key, value in item.result.items() if key != "answer"
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
        processing = self._processing_for(resolved)
        computer_mode = caps.computer_mode

        if computer_mode == "on":
            gate = self._make_gate(emit, processing)
            try:
                service = ComputerUseService(
                    runtime=self._runtime(),
                    plan=complete,
                    approval_gate=gate,
                    emit=emit,
                    limits=ComputerUseLimits(),
                    web_search=self._search if caps.web_search != "off" else None,
                )
                outcome = service.run_task(prompt, cancel_event=cancel_event)
            finally:
                self._release_gate(gate)
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
                "processing": processing,
            }

        if caps.web_search in ("auto", "on") or computer_mode == "auto":
            # Intent routing: one planner loop decides chat / web / computer.
            gate = None
            delegate = None
            if computer_mode == "auto" and self._computer_available():
                gate = self._make_gate(emit, processing)
                delegate = ComputerUseService(
                    runtime=self._runtime(),
                    plan=complete,
                    approval_gate=gate,
                    emit=emit,
                    limits=ComputerUseLimits(),
                    web_search=self._search if caps.web_search != "off" else None,
                )
            research = WebResearchService(
                search_service=self._search,
                complete=complete,
                emit=emit,
                limits=ResearchLimits(),
                computer=delegate,
                allow_search=caps.web_search != "off",
                stream=self._stream_call(resolved),
            )
            try:
                outcome = research.research(
                    prompt, system=system, history=history, cancel_event=cancel_event
                )
            finally:
                self._release_gate(gate)
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
            if outcome.computer_uses and not outcome.searches and not outcome.reads:
                mode = "computer"
            elif outcome.searches or outcome.reads or outcome.citations:
                mode = "web"
            else:
                mode = "chat"
            return {
                "mode": mode,
                "answer": "" if outcome.streamed else outcome.answer,
                "citations": citations,
                "warnings": list(outcome.warnings),
                "searches": outcome.searches,
                "reads": outcome.reads,
                "computer_uses": outcome.computer_uses,
                "processing": processing,
            }

        for delta in self._executor.stream(
            resolved,
            prompt=prompt,
            system=system,
            history=history,
            cancel_event=cancel_event,
        ):
            emit("message.delta", {"delta": delta})
        return {"mode": "chat", "answer": "", "citations": [], "processing": processing}
