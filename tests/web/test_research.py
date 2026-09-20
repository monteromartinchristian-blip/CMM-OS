"""The bounded research loop: protocol, budgets, citations, cancellation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from threading import Event

import pytest

from cmm.web.contracts import (
    FetchedSource,
    ResearchLimits,
    WebResultItem,
    WebSearchResult,
)
from cmm.web.errors import WebCapabilityError
from cmm.web.research import WebResearchService

NOW = datetime(2026, 9, 19, tzinfo=UTC)


class FakeSearch:
    def __init__(self, items=None, error=None):
        self.items = items or (
            WebResultItem(
                title="BOE — Anuncio real",
                url="https://www.boe.es/anuncio",
                domain="boe.es",
                snippet="Texto oficial del anuncio.",
                rank=1,
                backend_id="fake",
                searched_at=NOW,
            ),
        )
        self.error = error
        self.queries = []

    def search(self, request, cancel_event=None):
        self.queries.append(request.query)
        if self.error is not None:
            raise self.error
        return WebSearchResult(
            query=request.query,
            items=self.items,
            backend_id="fake",
            searched_at=NOW,
        )


def fake_fetch(request, cancel_event=None):
    return FetchedSource(
        url=request.url,
        final_url=request.url,
        domain="boe.es",
        title="BOE — Anuncio real",
        text="Contenido completo del anuncio oficial. " * 10,
        content_type="text/html",
        retrieved_at=NOW,
        truncated=False,
    )


class ScriptedComplete:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt, system, cancel_event=None):
        self.prompts.append((prompt, system))
        return self.replies.pop(0)


def collect_emit():
    events = []
    return events, (lambda kind, data: events.append((kind, data)))


def test_search_read_answer_with_real_citations():
    events, emit = collect_emit()
    search = FakeSearch()
    complete = ScriptedComplete(
        [
            json.dumps({"action": "search", "query": "anuncio boe"}),
            json.dumps({"action": "read", "url": "https://www.boe.es/anuncio"}),
            json.dumps(
                {"action": "answer", "text": "El anuncio dice X [1].", "citations": [1]}
            ),
        ]
    )
    service = WebResearchService(
        search_service=search, fetch=fake_fetch, complete=complete, emit=emit
    )
    outcome = service.research("¿Qué dice el anuncio del BOE?")
    assert outcome.answer.startswith("El anuncio dice X")
    assert len(outcome.citations) == 1
    citation = outcome.citations[0]
    assert (citation.url, citation.domain, citation.inspected) == (
        "https://www.boe.es/anuncio",
        "boe.es",
        True,
    )
    assert outcome.searches == 1 and outcome.reads == 1
    kinds = [kind for kind, _ in events]
    assert kinds == [
        "tool.requested",
        "tool.started",
        "tool.completed",
        "tool.requested",
        "tool.started",
        "tool.completed",
    ]
    search_payload = events[2][1]
    assert search_payload["capability"] == "web.search"
    assert search_payload["sources"][0]["url"] == "https://www.boe.es/anuncio"


def test_direct_answer_without_search_for_trivial_questions():
    events, emit = collect_emit()
    complete = ScriptedComplete(
        [json.dumps({"action": "answer", "text": "2 + 2 = 4.", "citations": []})]
    )
    service = WebResearchService(
        search_service=FakeSearch(), fetch=fake_fetch, complete=complete, emit=emit
    )
    outcome = service.research("¿Cuánto es 2+2?")
    assert outcome.answer == "2 + 2 = 4."
    assert outcome.searches == 0 and events == []


def test_plain_text_reply_is_accepted_as_answer():
    complete = ScriptedComplete(["La respuesta directa sin JSON."])
    service = WebResearchService(
        search_service=FakeSearch(), fetch=fake_fetch, complete=complete
    )
    outcome = service.research("pregunta")
    assert outcome.answer == "La respuesta directa sin JSON."
    assert "decision protocol not followed" in outcome.warnings


def test_citations_cannot_reference_unknown_evidence():
    complete = ScriptedComplete(
        [
            json.dumps({"action": "search", "query": "q"}),
            json.dumps({"action": "answer", "text": "ok", "citations": [1, 99]}),
        ]
    )
    service = WebResearchService(
        search_service=FakeSearch(), fetch=fake_fetch, complete=complete
    )
    outcome = service.research("pregunta")
    assert [c.index for c in outcome.citations] == [1]


def test_read_is_refused_for_urls_outside_the_evidence():
    events, emit = collect_emit()
    complete = ScriptedComplete(
        [
            json.dumps({"action": "read", "url": "https://evil.example/x"}),
            json.dumps({"action": "answer", "text": "sin lectura", "citations": []}),
        ]
    )
    service = WebResearchService(
        search_service=FakeSearch(), fetch=fake_fetch, complete=complete, emit=emit
    )
    outcome = service.research("pregunta")
    assert outcome.reads == 1  # attempt counted, execution refused
    assert any(kind == "tool.failed" for kind, _ in events)
    assert "read refused" in " ".join(outcome.warnings)


def test_fetch_failure_does_not_kill_the_run_and_never_fakes_a_citation():
    events, emit = collect_emit()

    def failing_fetch(request, cancel_event=None):
        raise WebCapabilityError("no access", code="SOURCE_BLOCKED")

    complete = ScriptedComplete(
        [
            json.dumps({"action": "search", "query": "q"}),
            json.dumps({"action": "read", "url": "https://www.boe.es/anuncio"}),
            json.dumps({"action": "answer", "text": "respuesta [1]", "citations": [1]}),
        ]
    )
    service = WebResearchService(
        search_service=FakeSearch(), fetch=failing_fetch, complete=complete, emit=emit
    )
    outcome = service.research("pregunta")
    assert outcome.citations[0].inspected is False
    assert any(
        kind == "tool.failed" and data["error"]["code"] == "SOURCE_BLOCKED"
        for kind, data in events
    )


def test_budgets_force_a_final_answer():
    complete = ScriptedComplete(
        [
            json.dumps({"action": "search", "query": "q0"}),
            json.dumps({"action": "search", "query": "q1"}),
            json.dumps({"action": "answer", "text": "forzado", "citations": []}),
        ]
    )
    search = FakeSearch()
    service = WebResearchService(
        search_service=search,
        fetch=fake_fetch,
        complete=complete,
        limits=ResearchLimits(max_searches=2, max_reads=0, max_turns=4),
    )
    outcome = service.research("pregunta")
    assert outcome.answer == "forzado"
    assert outcome.searches == 2


def test_search_backend_failure_propagates_normalized():
    complete = ScriptedComplete([json.dumps({"action": "search", "query": "q"})])
    service = WebResearchService(
        search_service=FakeSearch(
            error=WebCapabilityError("down", code="SEARCH_BACKEND_UNAVAILABLE")
        ),
        fetch=fake_fetch,
        complete=complete,
    )
    with pytest.raises(WebCapabilityError) as info:
        service.research("pregunta")
    assert info.value.code == "SEARCH_BACKEND_UNAVAILABLE"


def test_cancellation_stops_the_loop_between_steps():
    event = Event()
    complete = ScriptedComplete(
        [
            json.dumps({"action": "search", "query": "q"}),
            json.dumps({"action": "answer", "text": "no debe llegar", "citations": []}),
        ]
    )

    def cancelling_search(request, cancel_event=None):
        event.set()
        return FakeSearch().search(request)

    class SearchProxy:
        search = staticmethod(cancelling_search)

    service = WebResearchService(
        search_service=SearchProxy(), fetch=fake_fetch, complete=complete
    )
    with pytest.raises(WebCapabilityError) as info:
        service.research("pregunta", cancel_event=event)
    assert info.value.code == "CANCELLED"


def test_fenced_json_is_tolerated():
    complete = ScriptedComplete(
        ['```json\n{"action":"answer","text":"ok","citations":[]}\n```']
    )
    service = WebResearchService(
        search_service=FakeSearch(), fetch=fake_fetch, complete=complete
    )
    assert service.research("x").answer == "ok"


# ── intent routing inside the research loop ────────────────────────────────


class FakeComputer:
    def __init__(self, summary="tarea hecha", error=None):
        self.tasks = []
        self.summary = summary
        self.error = error

    def run_task(self, task, cancel_event=None):
        self.tasks.append(task)
        if self.error is not None:
            raise self.error
        from cmm.computer.contracts import ComputerTaskOutcome

        return ComputerTaskOutcome(
            summary=self.summary, steps=2, actions=("Abrir TextEdit",)
        )


def test_computer_action_delegates_and_feeds_the_planner():
    computer = FakeComputer()
    complete = ScriptedComplete(
        [
            json.dumps({"action": "computer", "task": "Abre TextEdit"}),
            json.dumps({"action": "answer", "text": "Hecho.", "citations": []}),
        ]
    )
    service = WebResearchService(
        search_service=FakeSearch(),
        fetch=fake_fetch,
        complete=complete,
        computer=computer,
    )
    outcome = service.research("Abre TextEdit")
    assert computer.tasks == ["Abre TextEdit"]
    assert outcome.computer_uses == 1
    assert "Computer task completed: tarea hecha" in complete.prompts[1][0]


def test_computer_failure_is_reported_not_raised():
    from cmm.computer.errors import ComputerUseError

    computer = FakeComputer(
        error=ComputerUseError("denied", code="COMPUTER_PERMISSION_DENIED")
    )
    complete = ScriptedComplete(
        [
            json.dumps({"action": "computer", "task": "x"}),
            json.dumps({"action": "answer", "text": "No pude.", "citations": []}),
        ]
    )
    service = WebResearchService(
        search_service=FakeSearch(),
        fetch=fake_fetch,
        complete=complete,
        computer=computer,
    )
    outcome = service.research("x")
    assert outcome.answer == "No pude."
    assert any("computer task failed" in w for w in outcome.warnings)


def test_allow_search_false_refuses_search_and_hides_it_from_the_protocol():
    complete = ScriptedComplete(
        [
            json.dumps({"action": "search", "query": "q"}),
            json.dumps(
                {"action": "answer", "text": "respuesta directa", "citations": []}
            ),
        ]
    )
    search = FakeSearch()
    service = WebResearchService(
        search_service=search,
        fetch=fake_fetch,
        complete=complete,
        allow_search=False,
    )
    outcome = service.research("pregunta")
    assert outcome.searches == 0
    assert search.queries == []
    assert any("search refused" in w for w in outcome.warnings)
    system = complete.prompts[0][1]
    assert '"action":"search"' not in system
    assert '"action":"computer"' not in system


def test_planner_protocol_adapts_to_available_capabilities():
    complete = ScriptedComplete(
        [json.dumps({"action": "answer", "text": "ok", "citations": []})]
    )
    service = WebResearchService(
        search_service=FakeSearch(),
        fetch=fake_fetch,
        complete=complete,
        computer=FakeComputer(),
    )
    service.research("x")
    system = complete.prompts[0][1]
    assert '"action":"computer"' in system
    assert '"action":"search"' in system


def test_first_decision_streams_direct_answers():
    events = []
    emit = lambda kind, data: events.append((kind, data))

    def fake_stream(prompt, system, cancel_event=None):
        yield "La prescripción "
        yield "adquisitiva es un modo de adquirir."

    complete = ScriptedComplete([])
    service = WebResearchService(
        search_service=FakeSearch(),
        fetch=fake_fetch,
        complete=complete,
        emit=emit,
        stream=fake_stream,
    )
    outcome = service.research("Explícame la prescripción adquisitiva.")
    assert outcome.streamed is True
    assert outcome.answer.startswith("La prescripción")
    assert complete.prompts == []
    assert [kind for kind, _ in events] == ["message.delta", "message.delta"]


def test_first_decision_json_start_enters_the_protocol_loop():
    events = []
    emit = lambda kind, data: events.append((kind, data))

    def fake_stream(prompt, system, cancel_event=None):
        yield '{"action":'
        yield '"answer","text":"ok","citations":[]}'

    service = WebResearchService(
        search_service=FakeSearch(),
        fetch=fake_fetch,
        complete=ScriptedComplete([]),
        emit=emit,
        stream=fake_stream,
    )
    outcome = service.research("x")
    assert outcome.answer == "ok"
    assert outcome.streamed is False
    assert events == []
