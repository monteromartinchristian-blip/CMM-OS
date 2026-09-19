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
from dataclasses import dataclass
from threading import Event
from typing import Any, Callable

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

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_DECISION_SYSTEM = (
    "You are the web-research planner inside CMM OS. Reply with ONE strict "
    "JSON object and nothing else. Allowed actions:\n"
    '{"action":"search","query":"<web query>"}\n'
    '{"action":"read","url":"<absolute http(s) url from the evidence>"}\n'
    '{"action":"answer","text":"<final answer in the user language>",'
    '"citations":[<evidence indexes used>]}\n'
    "Rules: prefer answering directly when no current information is needed; "
    "search at most a few times; read only urls present in the evidence; cite "
    "only evidence indexes you actually used; never invent urls or citations."
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
        return f"[{self.index}] ({state}) {self.title} — {self.domain}\n{self.url}\n{body}"


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
    ) -> None:
        self._search = search_service or WebSearchService()
        self._fetch = fetch or fetch_source
        self._complete = complete
        self._emit = emit or (lambda kind, data: None)
        self._limits = limits or ResearchLimits()

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
        searches = reads = 0

        for turn in range(self._limits.max_turns):
            self._check_cancel(cancel_event)
            forced = (
                searches >= self._limits.max_searches
                and reads >= self._limits.max_reads
            ) or turn == self._limits.max_turns - 1
            decision_text = self._complete(
                self._decision_prompt(prompt, evidence, forced=forced),
                _DECISION_SYSTEM if system is None else f"{system}\n\n{_DECISION_SYSTEM}",
                cancel_event,
            )
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
                    warnings=tuple(warnings),
                )
            if action == "search":
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
            {"tool_run_id": tool_run_id, "capability": "web.search", "tool": "search",
             "summary": query},
        )
        self._emit(
            "tool.started",
            {"tool_run_id": tool_run_id, "capability": "web.search", "tool": "search",
             "summary": query},
        )
        try:
            result = self._search.search(
                WebSearchRequest(query=query), cancel_event=cancel_event
            )
        except WebCapabilityError as error:
            self._emit(
                "tool.failed",
                {"tool_run_id": tool_run_id, "capability": "web.search",
                 "tool": "search", "error": {"code": error.code, "message": error.message}},
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
                {"title": item.title, "url": item.url, "domain": item.domain,
                 "snippet": item.snippet, "rank": item.rank,
                 "retrieved_at": item.searched_at.isoformat(), "inspected": False}
            )
        self._emit(
            "tool.completed",
            {"tool_run_id": tool_run_id, "capability": "web.search", "tool": "search",
             "status": "completed",
             "summary": f"{added} sources for “{query}”",
             "sources": payload_sources},
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
            {"tool_run_id": tool_run_id, "capability": "web.fetch", "tool": "read",
             "summary": url},
        )
        self._emit(
            "tool.started",
            {"tool_run_id": tool_run_id, "capability": "web.fetch", "tool": "read",
             "summary": url},
        )
        entry = next((item for item in evidence if item.url == url), None)
        if entry is None:
            warnings.append("read refused: url is not in the evidence")
            self._emit(
                "tool.failed",
                {"tool_run_id": tool_run_id, "capability": "web.fetch", "tool": "read",
                 "error": {"code": "SOURCE_BLOCKED",
                           "message": "Only evidence urls can be read."}},
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
                {"tool_run_id": tool_run_id, "capability": "web.fetch", "tool": "read",
                 "error": {"code": error.code, "message": error.message}},
            )
            return
        entry.inspected = True
        entry.text = fetched.text
        entry.title = fetched.title or entry.title
        entry.retrieved_at = fetched.retrieved_at
        sources.append(fetched)
        self._emit(
            "tool.completed",
            {"tool_run_id": tool_run_id, "capability": "web.fetch", "tool": "read",
             "status": "completed", "summary": f"Read {fetched.domain}",
             "sources": [{"title": entry.title, "url": fetched.final_url,
                          "domain": fetched.domain, "snippet": fetched.text[:300],
                          "rank": entry.index,
                          "retrieved_at": fetched.retrieved_at.isoformat(),
                          "inspected": True}]},
        )

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _check_cancel(cancel_event: Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise WebCapabilityError("The web research was cancelled.", code="CANCELLED")

    @staticmethod
    def _decision_prompt(
        prompt: str, evidence: list[EvidenceItem], *, forced: bool
    ) -> str:
        parts = [f"User question:\n{prompt}"]
        if evidence:
            parts.append(
                "Evidence gathered so far:\n"
                + "\n\n".join(item.summary() for item in evidence)
            )
        else:
            parts.append("Evidence gathered so far: (none)")
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
