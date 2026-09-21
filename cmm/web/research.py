"""Bounded web research loop: search → read → answer with real citations.

The loop is ordinary Chat intelligence using the Web capability (not Cowork):
the canonical model-execution seam answers through a strict JSON action
protocol, evidence comes only from the normalized search/retrieval boundary,
and every citation resolves to a source actually returned or inspected during
the run.  Cancellation is honored between every step.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from typing import Any

from cmm.web.contracts import (
    Citation,
    FetchedSource,
    FetchRequest,
    ResearchLimits,
    ResearchOutcome,
    WebSearchRequest,
)
from cmm.web.errors import WebCapabilityError
from cmm.web.retrieval import fetch_source
from cmm.web.service import WebSearchService

__all__ = ["EvidenceItem", "WebResearchService"]

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_DECISION_SYSTEM = (
    "You are the capability planner inside CMM OS. Reply with ONE strict "
    "JSON object and nothing else. Allowed actions:\n"
    '{"action":"search","query":"<web query>"}\n'
    '{"action":"read","url":"<absolute http(s) url from the evidence>"}\n'
    '{"action":"computer","task":"<one concrete task to perform on this Mac>"}\n'
    '{"action":"answer","text":"<final answer in the user language>",'
    '"citations":[<evidence indexes used>]}\n'
    "Rules: prefer answering directly when no current information and no "
    "computer action is needed; search at most a few times; read only urls "
    "present in the evidence; delegate to the computer only when the user "
    "intent requires operating this Mac; cite only evidence indexes you "
    "actually used; never invent urls or citations."
)


@dataclass
class EvidenceItem:
    index: int
    title: str
    url: str
    domain: str
    snippet: str
    inspected: bool = False
    text: str = ""
    retrieved_at: Any | None = None

    def summary(self) -> str:
        body = self.text[:1200] if self.inspected else self.snippet[:300]
        state = "read" if self.inspected else "search result"
        return (
            f"[{self.index}] ({state}) {self.title} — {self.domain}\n{self.url}\n{body}"
        )


class WebResearchService:
    """One canonical research loop over the normalized web boundary."""

    def __init__(
        self,
        *,
        search_service: WebSearchService | None = None,
        fetch: Callable[..., FetchedSource] | None = None,
        complete: Callable[..., str],
        emit: Callable[[str, dict[str, Any]], None] | None = None,
        limits: ResearchLimits | None = None,
        computer: Any | None = None,
        allow_search: bool = True,
        stream: Any | None = None,
    ) -> None:
        self._search = search_service or WebSearchService()
        self._fetch = fetch or fetch_source
        self._complete = complete
        self._emit = emit or (lambda kind, data: None)
        self._limits = limits or ResearchLimits()
        self._computer = computer
        self._allow_search = allow_search
        self._stream = stream

    # ── public surface ────────────────────────────────────────────────────

    def research(
        self,
        prompt: str,
        *,
        system: str | None = None,
        history: tuple[tuple[str, str], ...] = (),
        cancel_event: Event | None = None,
    ) -> ResearchOutcome:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        evidence: list[EvidenceItem] = []
        sources: list[FetchedSource] = []
        warnings: list[str] = []
        feedback = ""
        searches = reads = computer_uses = 0

        for turn in range(self._limits.max_turns):
            self._check_cancel(cancel_event)
            forced = (
                searches >= self._limits.max_searches
                and reads >= self._limits.max_reads
            ) or turn == self._limits.max_turns - 1
            decision_prompt = self._decision_prompt(
                prompt, evidence, forced=forced, feedback=feedback
            )
            planner_system = self._planner_system(system)
            if turn == 0 and self._stream is not None and not forced:
                # Ordinary chat must keep token streaming: the first decision
                # is streamed, and only a JSON-looking start enters the loop.
                streamed = self._stream_first_decision(
                    decision_prompt, planner_system, cancel_event
                )
                if isinstance(streamed, ResearchOutcome):
                    return streamed
                decision_text = streamed
            else:
                decision_text = self._complete(
                    decision_prompt, planner_system, cancel_event
                )
            feedback = ""
            decision = _parse_decision(decision_text)
            if decision is None:
                # A plain-text reply is accepted as a direct answer.
                answer = decision_text.strip()
                if answer:
                    return ResearchOutcome(
                        answer=answer,
                        citations=(),
                        sources=tuple(sources),
                        searches=searches,
                        reads=reads,
                        computer_uses=computer_uses,
                        warnings=tuple(warnings + ["decision protocol not followed"]),
                    )
                warnings.append("empty model decision")
                continue

            action = str(decision.get("action", "")).strip().lower()
            if action == "answer" or forced:
                answer = str(decision.get("text", "")).strip()
                if not answer:
                    warnings.append("answer action without text")
                    continue
                citations = self._build_citations(decision.get("citations"), evidence)
                if not citations and evidence:
                    warnings.append("answer without citations despite evidence")
                return ResearchOutcome(
                    answer=answer,
                    citations=citations,
                    sources=tuple(sources),
                    searches=searches,
                    reads=reads,
                    computer_uses=computer_uses,
                    warnings=tuple(warnings),
                )
            if action == "search":
                if not self._allow_search:
                    feedback = (
                        "Web search is disabled for this request; answer with "
                        "what you know or finish honestly."
                    )
                    warnings.append("search refused: web disabled for this request")
                    continue
                if searches >= self._limits.max_searches:
                    warnings.append("search budget exhausted")
                    continue
                query = str(decision.get("query", "")).strip()
                if not query:
                    warnings.append("search action without query")
                    continue
                searches += 1
                new_items = self._run_search(query, evidence, cancel_event)
                if not new_items:
                    warnings.append(f"search returned nothing: {query}")
                continue
            if action == "read":
                if reads >= self._limits.max_reads:
                    warnings.append("read budget exhausted")
                    continue
                url = str(decision.get("url", "")).strip()
                reads += 1
                self._run_read(url, evidence, sources, warnings, cancel_event)
                continue
            if action == "computer":
                if self._computer is None:
                    feedback = (
                        "The computer capability is not available for this "
                        "request; answer with what you have or explain honestly."
                    )
                    warnings.append("computer refused: capability not available")
                    continue
                task = str(decision.get("task", "")).strip()
                if not task:
                    warnings.append("computer action without task")
                    continue
                computer_uses += 1
                feedback = self._run_computer(task, cancel_event, warnings)
                continue
            warnings.append(f"unknown action: {action}")

        raise WebCapabilityError(
            "The web research loop did not converge.", code="CAPABILITY_UNSUPPORTED"
        )

    # ── steps ─────────────────────────────────────────────────────────────

    def _run_search(
        self, query: str, evidence: list[EvidenceItem], cancel_event: Event | None
    ) -> int:
        tool_run_id = f"web-search-{len(evidence) + 1}-{abs(hash(query)) % 10_000}"
        self._emit(
            "tool.requested",
            {
                "tool_run_id": tool_run_id,
                "capability": "web.search",
                "tool": "search",
                "summary": query,
            },
        )
        self._emit(
            "tool.started",
            {
                "tool_run_id": tool_run_id,
                "capability": "web.search",
                "tool": "search",
                "summary": query,
            },
        )
        try:
            result = self._search.search(
                WebSearchRequest(query=query), cancel_event=cancel_event
            )
        except WebCapabilityError as error:
            self._emit(
                "tool.failed",
                {
                    "tool_run_id": tool_run_id,
                    "capability": "web.search",
                    "tool": "search",
                    "error": {"code": error.code, "message": error.message},
                },
            )
            raise
        added = 0
        payload_sources = []
        for item in result.items:
            if any(existing.url == item.url for existing in evidence):
                continue
            evidence.append(
                EvidenceItem(
                    index=len(evidence) + 1,
                    title=item.title,
                    url=item.url,
                    domain=item.domain,
                    snippet=item.snippet,
                )
            )
            added += 1
            payload_sources.append(
                {
                    "title": item.title,
                    "url": item.url,
                    "domain": item.domain,
                    "snippet": item.snippet,
                    "rank": item.rank,
                    "retrieved_at": item.searched_at.isoformat(),
                    "inspected": False,
                }
            )
        self._emit(
            "tool.completed",
            {
                "tool_run_id": tool_run_id,
                "capability": "web.search",
                "tool": "search",
                "status": "completed",
                "summary": f"{added} sources for “{query}”",
                "sources": payload_sources,
            },
        )
        return added

    def _run_read(
        self,
        url: str,
        evidence: list[EvidenceItem],
        sources: list[FetchedSource],
        warnings: list[str],
        cancel_event: Event | None,
    ) -> None:
        tool_run_id = f"web-fetch-{abs(hash(url)) % 100_000}"
        self._emit(
            "tool.requested",
            {
                "tool_run_id": tool_run_id,
                "capability": "web.fetch",
                "tool": "read",
                "summary": url,
            },
        )
        self._emit(
            "tool.started",
            {
                "tool_run_id": tool_run_id,
                "capability": "web.fetch",
                "tool": "read",
                "summary": url,
            },
        )
        entry = next((item for item in evidence if item.url == url), None)
        if entry is None:
            warnings.append("read refused: url is not in the evidence")
            self._emit(
                "tool.failed",
                {
                    "tool_run_id": tool_run_id,
                    "capability": "web.fetch",
                    "tool": "read",
                    "error": {
                        "code": "SOURCE_BLOCKED",
                        "message": "Only evidence urls can be read.",
                    },
                },
            )
            return
        try:
            fetched = self._fetch(FetchRequest(url=url), cancel_event)
        except WebCapabilityError as error:
            if error.code == "CANCELLED":
                raise
            warnings.append(f"fetch failed for {url}: {error.code}")
            self._emit(
                "tool.failed",
                {
                    "tool_run_id": tool_run_id,
                    "capability": "web.fetch",
                    "tool": "read",
                    "error": {"code": error.code, "message": error.message},
                },
            )
            return
        entry.inspected = True
        entry.text = fetched.text
        entry.title = fetched.title or entry.title
        entry.retrieved_at = fetched.retrieved_at
        sources.append(fetched)
        self._emit(
            "tool.completed",
            {
                "tool_run_id": tool_run_id,
                "capability": "web.fetch",
                "tool": "read",
                "status": "completed",
                "summary": f"Read {fetched.domain}",
                "sources": [
                    {
                        "title": entry.title,
                        "url": fetched.final_url,
                        "domain": fetched.domain,
                        "snippet": fetched.text[:300],
                        "rank": entry.index,
                        "retrieved_at": fetched.retrieved_at.isoformat(),
                        "inspected": True,
                    }
                ],
            },
        )

    def _run_computer(
        self, task: str, cancel_event: Event | None, warnings: list[str]
    ) -> str:
        from cmm.computer.errors import ComputerUseError

        try:
            outcome = self._computer.run_task(task, cancel_event=cancel_event)
        except ComputerUseError as error:
            if error.code == "CANCELLED":
                raise
            warnings.append(f"computer task failed: {error.code}")
            return (
                f"The computer task failed ({error.code}). Adapt the plan or "
                "finish honestly explaining what could not be done."
            )
        actions = ", ".join(outcome.actions[-6:]) or "none"
        return (
            f"Computer task completed: {outcome.summary} "
            f"(actions: {actions}; approvals: {outcome.approvals}; "
            f"rejections: {outcome.rejections})"
        )

    # ── helpers ───────────────────────────────────────────────────────────

    def _stream_first_decision(
        self, prompt_text: str, system_text: str, cancel_event: Event | None
    ) -> ResearchOutcome | str:
        """Stream the first planner call.

        A reply starting with JSON (or a code fence) is buffered and returned
        as the decision text; any other reply is a direct answer and is
        streamed to the product as ``message.delta`` events.
        """

        buffer: list[str] = []
        answer: list[str] = []
        mode: str | None = None
        for delta in self._stream(
            prompt=prompt_text, system=system_text, cancel_event=cancel_event
        ):
            if mode is None:
                buffer.append(delta)
                head = "".join(buffer).lstrip()
                if head[:1] in ("{", "`"):
                    mode = "json"
                elif head or sum(len(part) for part in buffer) > 64:
                    mode = "direct"
                    for piece in buffer:
                        self._emit("message.delta", {"delta": piece})
                    answer.extend(buffer)
                continue
            if mode == "json":
                buffer.append(delta)
            else:
                self._emit("message.delta", {"delta": delta})
                answer.append(delta)
        if mode != "direct":
            return "".join(buffer)
        text = "".join(answer).strip()
        if not text:
            return ""
        return ResearchOutcome(answer=text, citations=(), streamed=True)

    def _planner_system(self, system: str | None) -> str:
        """Compose the action protocol with only the available capabilities."""

        lines = [
            (
                "You are the capability planner inside CMM OS. Reply with ONE "
                "strict JSON object and nothing else. Allowed actions:"
            )
        ]
        if self._allow_search:
            lines.append('{"action":"search","query":"<web query>"}')
            lines.append(
                '{"action":"read","url":"<absolute http(s) url from the evidence>"}'
            )
        if self._computer is not None:
            lines.append(
                '{"action":"computer","task":"<one concrete task to perform on this Mac>"}'
            )
        lines.append(
            '{"action":"answer","text":"<final answer in the user language>",'
            '"citations":[<evidence indexes used>]}'
        )
        rules = [
            (
                "Rules: prefer answering directly when no current information "
                "and no computer action is needed"
            )
        ]
        if self._allow_search:
            rules.append("search at most a few times")
            rules.append("read only urls present in the evidence")
        if self._computer is not None:
            rules.append(
                "delegate to the computer only when the user intent requires "
                "operating this Mac"
            )
        rules.append("cite only evidence indexes you actually used")
        rules.append("never invent urls or citations")
        rules.append(
            "never emit tool-call syntax or special tokens; reply with the "
            "JSON object or plain text only"
        )
        combined = "\n".join(lines) + "\n" + "; ".join(rules) + "."
        return combined if system is None else f"{system}\n\n{combined}"

    @staticmethod
    def _check_cancel(cancel_event: Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise WebCapabilityError(
                "The web research was cancelled.", code="CANCELLED"
            )

    @staticmethod
    def _decision_prompt(
        prompt: str,
        evidence: list[EvidenceItem],
        *,
        forced: bool,
        feedback: str = "",
    ) -> str:
        parts = [f"User question:\n{prompt}"]
        if evidence:
            parts.append(
                "Evidence gathered so far:\n"
                + "\n\n".join(item.summary() for item in evidence)
            )
        else:
            parts.append("Evidence gathered so far: (none)")
        if feedback:
            parts.append(f"Feedback: {feedback}")
        if forced:
            parts.append(
                "Budget exhausted: reply with the answer action now, using only "
                "the evidence above; cite the indexes you used."
            )
        return "\n\n".join(parts)

    @staticmethod
    def _build_citations(
        raw: Any, evidence: list[EvidenceItem]
    ) -> tuple[Citation, ...]:
        if not isinstance(raw, list):
            return ()
        citations: list[Citation] = []
        for value in raw:
            try:
                index = int(value)
            except (TypeError, ValueError):
                continue
            entry = next((item for item in evidence if item.index == index), None)
            if entry is None:
                continue
            citations.append(
                Citation(
                    index=entry.index,
                    title=entry.title,
                    url=entry.url,
                    domain=entry.domain,
                    snippet=(entry.text[:300] if entry.inspected else entry.snippet),
                    inspected=entry.inspected,
                    retrieved_at=entry.retrieved_at,
                )
            )
        return tuple(citations)


def _parse_decision(text: str) -> dict[str, Any] | None:
    """Parse the strict JSON action protocol, tolerating code fences."""

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
