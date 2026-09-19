"""The Computer Use execution loop: observe → plan → policy → (approval) →
execute → observe.  Multi-step, cancellable before every action, honest about
permissions, and normalized for the product surface."""

from __future__ import annotations

import json
import re
from threading import Event
from typing import Any, Callable, Protocol

from cmm.computer.contracts import (
    Action,
    ApprovalProposal,
    ComputerTaskOutcome,
    ComputerUseLimits,
    Observation,
)
from cmm.computer.errors import ComputerUseError
from cmm.computer.policy import classify_action

__all__ = ["ApprovalGate", "ComputerUseService"]

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_PLANNER_SYSTEM = (
    "You control a macOS computer for the user through CMM OS. Reply with ONE "
    "strict JSON object and nothing else. Allowed actions:\n"
    '{"action":"app.open","app":"<name>"}\n'
    '{"action":"app.activate","app":"<name>"}\n'
    '{"action":"window.focus","title":"<window title fragment>"}\n'
    '{"action":"ui.press","element_id":<id from the observation>}\n'
    '{"action":"ui.set_value","element_id":<id>,"text":"<text>"}\n'
    '{"action":"keyboard.type","text":"<text>"}\n'
    '{"action":"keyboard.shortcut","keys":"cmd+n"}\n'
    '{"action":"pointer.click","x":<int>,"y":<int>}\n'
    '{"action":"pointer.scroll","dy":<negative scrolls down>}\n'
    '{"action":"wait","seconds":<0.5-5>}\n'
    '{"action":"finish","summary":"<what was accomplished>"}\n'
    "Rules: act on the current observation only; prefer element ids over "
    "coordinates; one action per reply; never repeat an action that produced "
    "no observable change — adapt or finish honestly; finish as soon as the "
    "task is done; never invent elements that are not listed."
)


class ApprovalGate(Protocol):
    def request(self, proposal: ApprovalProposal) -> str:
        """Block until the user decides: ``allow_once`` or ``reject``."""
        ...


class ComputerUseService:
    """One canonical computer-use loop over a runtime and the model seam."""

    def __init__(
        self,
        *,
        runtime: Any,
        plan: Callable[..., str],
        approval_gate: ApprovalGate | None = None,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
        limits: ComputerUseLimits | None = None,
        web_search: Any | None = None,
    ) -> None:
        self._runtime = runtime
        self._plan = plan
        self._gate = approval_gate
        self._emit = emit or (lambda kind, data: None)
        self._limits = limits or ComputerUseLimits()
        self._web_search = web_search

    def status(self) -> dict[str, Any]:
        """Honest availability/permission report for the product surface."""

        available = bool(getattr(self._runtime, "available", lambda: False)())
        permissions = {"accessibility": False, "screen_recording": False, "detail": ""}
        if available:
            state = self._runtime.permissions()
            permissions = {
                "accessibility": state.accessibility,
                "screen_recording": state.screen_recording,
                "detail": state.detail,
            }
        return {
            "available": available and permissions["accessibility"],
            "runtime_available": available,
            "permissions": permissions,
        }

    def run_task(self, task: str, *, cancel_event: Event | None = None) -> ComputerTaskOutcome:
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        if not getattr(self._runtime, "available", lambda: False)():
            raise ComputerUseError(
                "Computer Use is not available on this machine.",
                code="COMPUTER_RUNTIME_UNAVAILABLE",
            )
        permissions = self._runtime.permissions()
        if not permissions.satisfied:
            raise ComputerUseError(
                "Computer Use needs macOS permissions that are not granted.",
                code="COMPUTER_PERMISSION_DENIED",
                detail=permissions.detail,
            )

        tool_run_id = f"computer-{abs(hash(task)) % 100_000}"
        self._emit(
            "tool.requested",
            {"tool_run_id": tool_run_id, "capability": "computer.use",
             "tool": "computer", "summary": task[:120]},
        )
        self._emit(
            "tool.started",
            {"tool_run_id": tool_run_id, "capability": "computer.use",
             "tool": "computer", "summary": task[:120]},
        )

        actions: list[str] = []
        warnings: list[str] = []
        feedback = ""
        approvals = rejections = 0
        observation: Observation | None = None
        attempts: dict[tuple[str, str], int] = {}

        for step in range(self._limits.max_steps):
            if cancel_event is not None and cancel_event.is_set():
                self._emit(
                    "tool.cancelled",
                    {"tool_run_id": tool_run_id, "capability": "computer.use",
                     "tool": "computer", "status": "cancelled",
                     "summary": f"{len(actions)} actions before cancellation"},
                )
                raise ComputerUseError(
                    "The computer task was cancelled.", code="CANCELLED"
                )

            observation = self._runtime.observe()
            self._emit(
                "computer.observation",
                {"tool_run_id": tool_run_id, "capability": "computer.use",
                 "app": observation.frontmost_app,
                 "windows": len(observation.windows),
                 "elements": len(observation.elements)},
            )

            forced = step == self._limits.max_steps - 1
            decision = self._plan(
                self._planner_prompt(task, observation, actions, feedback, forced),
                self._planner_system(),
                cancel_event,
            )
            feedback = ""
            if cancel_event is not None and cancel_event.is_set():
                self._emit(
                    "tool.cancelled",
                    {"tool_run_id": tool_run_id, "capability": "computer.use",
                     "tool": "computer", "status": "cancelled",
                     "summary": "cancelled while planning the next action"},
                )
                raise ComputerUseError(
                    "The computer task was cancelled.", code="CANCELLED"
                )
            parsed = _parse_action(decision)
            if parsed is None:
                feedback = "The previous reply was not a valid JSON action; follow the protocol."
                warnings.append("invalid planner reply")
                continue

            kind = str(parsed.get("action", "")).strip()
            params = {k: v for k, v in parsed.items() if k != "action"}
            if kind == "finish" or forced:
                summary = str(params.get("summary", "")).strip() or (
                    "Step budget exhausted; task stopped." if forced else "Task finished."
                )
                if forced and kind != "finish":
                    warnings.append("step budget exhausted")
                self._emit(
                    "tool.completed",
                    {"tool_run_id": tool_run_id, "capability": "computer.use",
                     "tool": "computer", "status": "completed", "summary": summary},
                )
                return ComputerTaskOutcome(
                    summary=summary,
                    steps=step + 1,
                    actions=tuple(actions),
                    approvals=approvals,
                    rejections=rejections,
                    warnings=tuple(warnings),
                )

            try:
                if kind == "web.search":
                    feedback = self._run_web_search(params, tool_run_id, step)
                    continue
                action = Action(kind=kind, params=params)
            except ValueError:
                feedback = f"Unknown action “{kind}”; use only the allowed actions."
                warnings.append(f"unknown action: {kind}")
                continue

            decision_policy = classify_action(action, observation)
            if decision_policy.decision == "deny":
                feedback = f"The action was denied by policy: {decision_policy.reason}"
                warnings.append("action denied by policy")
                continue
            if decision_policy.decision == "approval":
                proposal = ApprovalProposal(
                    tool_run_id=f"{tool_run_id}-{step}",
                    action_description=action.describe(observation),
                    app=observation.frontmost_app,
                    reason=decision_policy.reason or "Acción con efectos sensibles.",
                    consequence=decision_policy.consequence,
                    egress=decision_policy.egress,
                )
                self._emit(
                    "approval.requested",
                    {"tool_run_id": proposal.tool_run_id, "capability": "computer.use",
                     "approval": {
                         "action": proposal.action_description,
                         "app": proposal.app,
                         "reason": proposal.reason,
                         "consequence": proposal.consequence,
                         "egress": proposal.egress,
                     }},
                )
                verdict = (
                    self._gate.request(proposal) if self._gate is not None else "reject"
                )
                self._emit(
                    "approval.resolved",
                    {"tool_run_id": proposal.tool_run_id, "capability": "computer.use",
                     "decision": verdict},
                )
                if verdict != "allow_once":
                    rejections += 1
                    feedback = (
                        "The user REJECTED that action. Do not retry it; adapt the "
                        "plan or finish explaining what is missing."
                    )
                    continue
                approvals += 1

            if cancel_event is not None and cancel_event.is_set():
                # Cancellation must prevent the next action even after approval.
                self._emit(
                    "tool.cancelled",
                    {"tool_run_id": tool_run_id, "capability": "computer.use",
                     "tool": "computer", "status": "cancelled",
                     "summary": "cancelled before executing the next action"},
                )
                raise ComputerUseError(
                    "The computer task was cancelled.", code="CANCELLED"
                )

            description = action.describe(observation)
            signature = (kind, json.dumps(params, sort_keys=True, default=str))
            attempts[signature] = attempts.get(signature, 0) + 1
            if attempts[signature] > 2:
                feedback = (
                    f"The action “{description}” was already attempted "
                    f"{attempts[signature] - 1} times with no observable change. "
                    "Do not repeat it: choose a different approach, or finish "
                    "honestly describing what could not be completed."
                )
                warnings.append(f"repeated action: {description}")
                continue
            self._emit(
                "tool.progress",
                {"tool_run_id": tool_run_id, "capability": "computer.use",
                 "tool": "computer", "summary": description},
            )
            result = self._runtime.execute(action, observation)
            if result.ok:
                actions.append(description)
            else:
                feedback = f"The action failed: {result.detail}. Adapt the plan."
                warnings.append(f"action failed: {description}")

        self._emit(
            "tool.failed",
            {"tool_run_id": tool_run_id, "capability": "computer.use",
             "tool": "computer",
             "error": {"code": "CAPABILITY_UNSUPPORTED",
                       "message": "The computer task did not converge."}},
        )
        raise ComputerUseError(
            "The computer task did not converge within the step budget.",
            code="CAPABILITY_UNSUPPORTED",
        )

    def _planner_system(self) -> str:
        if self._web_search is None:
            return _PLANNER_SYSTEM
        return (
            _PLANNER_SYSTEM
            + '\nAdditionally allowed when the task needs current web information:\n'
            '{"action":"web.search","query":"<web query>"}'
        )

    def _run_web_search(
        self, params: dict[str, Any], tool_run_id: str, step: int
    ) -> str:
        from cmm.web.contracts import WebSearchRequest
        from cmm.web.errors import WebCapabilityError

        query = str(params.get("query", "")).strip()
        search_run_id = f"{tool_run_id}-web-{step}"
        if not query or self._web_search is None:
            return "Web search is not available or the query was empty."
        self._emit(
            "tool.requested",
            {"tool_run_id": search_run_id, "capability": "web.search",
             "tool": "search", "summary": query},
        )
        self._emit(
            "tool.started",
            {"tool_run_id": search_run_id, "capability": "web.search",
             "tool": "search", "summary": query},
        )
        try:
            result = self._web_search.search(WebSearchRequest(query=query))
        except WebCapabilityError as error:
            self._emit(
                "tool.failed",
                {"tool_run_id": search_run_id, "capability": "web.search",
                 "tool": "search",
                 "error": {"code": error.code, "message": error.message}},
            )
            return f"The web search failed ({error.code}); adapt the plan."
        sources = [
            {"title": item.title, "url": item.url, "domain": item.domain,
             "snippet": item.snippet, "rank": item.rank,
             "retrieved_at": item.searched_at.isoformat(), "inspected": False}
            for item in result.items[:6]
        ]
        self._emit(
            "tool.completed",
            {"tool_run_id": search_run_id, "capability": "web.search",
             "tool": "search", "status": "completed",
             "summary": f"{len(sources)} sources for “{query}”",
             "sources": sources},
        )
        listing = "\n".join(
            f"[{source['rank']}] {source['title']} — {source['url']} "
            f"({source['domain']}): {source['snippet'][:160]}"
            for source in sources
        )
        return f"Web search results for “{query}”:\n{listing}"

    @staticmethod
    def _planner_prompt(
        task: str,
        observation: Observation,
        actions: list[str],
        feedback: str,
        forced: bool,
    ) -> str:
        parts = [
            f"Task: {task}",
            f"Executed actions so far: {json.dumps(actions[-8:], ensure_ascii=False)}",
            "Current observation:\n" + observation.render(),
        ]
        if feedback:
            parts.append(f"Feedback: {feedback}")
        if forced:
            parts.append(
                "Step budget exhausted: reply with the finish action now and "
                "summarize honestly what was and was not accomplished."
            )
        return "\n\n".join(parts)


def _parse_action(text: str) -> dict[str, Any] | None:
    if not isinstance(text, str) or not text.strip():
        return None
    candidate = text.strip()
    fenced = _FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
