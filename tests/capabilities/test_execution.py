"""The normalized capability execution surface over the model seam."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from cmm.capabilities.events import EVENT_KINDS, CapabilityEvent, CapabilityRequest
from cmm.capabilities.execution import CapabilityExecution
from cmm.computer.contracts import (
    ActionResult,
    ElementInfo,
    Observation,
    PermissionState,
    WindowInfo,
)
from cmm.web.contracts import WebResultItem, WebSearchResult

NOW = datetime(2026, 9, 19, tzinfo=UTC)
RESOLVED = object()


class FakeExecutor:
    """Scripted seam: each stream call yields one scripted reply."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def stream(self, resolved, *, prompt, system=None, history=(), cancel_event=None, **_):
        self.calls.append({"prompt": prompt, "system": system, "history": history})
        reply = (
            self.replies.pop(0)
            if self.replies
            else json.dumps({"action": "finish", "summary": "script exhausted"})
        )
        if isinstance(reply, BaseException):
            raise reply
        yield reply


class FakeSearch:
    def __init__(self):
        self.queries = []

    def search(self, request, cancel_event=None):
        self.queries.append(request.query)
        return WebSearchResult(
            query=request.query,
            items=(
                WebResultItem(
                    title="Resultado oficial",
                    url="https://example.com/doc",
                    domain="example.com",
                    snippet="Extracto oficial.",
                    rank=1,
                    backend_id="fake",
                    searched_at=NOW,
                ),
            ),
            backend_id="fake",
            searched_at=NOW,
        )


class FakeRuntime:
    def __init__(self, app="Mail", permissions=None):
        self.app = app
        self.permissions_state = permissions or PermissionState(True, True)
        self.executed = []

    def available(self):
        return True

    def permissions(self):
        return self.permissions_state

    def observe(self, **_):
        return Observation(
            frontmost_app=self.app,
            frontmost_bundle="com.test.app",
            windows=(WindowInfo("w", self.app, 0, 0, 100, 100),),
            elements=(ElementInfo(1, "AXButton", "OK", "", 0, 0, 10, 10, True),),
        )

    def execute(self, action, observation=None):
        self.executed.append(action.kind)
        return ActionResult(True, "ok")


def kinds(events):
    return [event.kind for event in events]


def test_plain_chat_streams_real_deltas_and_summarizes():
    class ChunkedExecutor:
        def stream(self, resolved, **kwargs):
            yield "Hola "
            yield "mundo"

    facade = CapabilityExecution(executor=ChunkedExecutor(), search_service=FakeSearch())
    events = list(facade.stream(RESOLVED, prompt="hola", capabilities=CapabilityRequest()))
    assert kinds(events) == ["message.delta", "message.delta", "run.summary"]
    assert events[0].data["delta"] == "Hola "
    assert events[-1].data["mode"] == "chat"
    assert all(event.kind in EVENT_KINDS for event in events)


def test_web_mode_produces_citations_and_summary():
    executor = FakeExecutor(
        [
            json.dumps({"action": "search", "query": "normativa vigente"}),
            json.dumps(
                {"action": "answer", "text": "Según la fuente [1].", "citations": [1]}
            ),
        ]
    )
    search = FakeSearch()
    facade = CapabilityExecution(executor=executor, search_service=search)
    events = list(
        facade.stream(
            RESOLVED,
            prompt="¿Qué dice la normativa?",
            capabilities=CapabilityRequest(web_search="auto"),
        )
    )
    event_kinds = kinds(events)
    assert event_kinds[0] == "tool.requested"
    assert "tool.completed" in event_kinds
    assert event_kinds[-2:] == ["message.delta", "run.summary"]
    summary = events[-1].data
    assert summary["mode"] == "web"
    citation = summary["citations"][0]
    assert citation["url"] == "https://example.com/doc"
    assert citation["inspected"] is False
    assert events[-2].data["delta"].startswith("Según la fuente")
    assert search.queries == ["normativa vigente"]


def test_computer_mode_with_approval_resolved_by_the_product_side():
    executor = FakeExecutor(
        [
            json.dumps({"action": "keyboard.type", "text": "borrador"}),
            json.dumps({"action": "finish", "summary": "Borrador escrito"}),
        ]
    )
    runtime = FakeRuntime(app="Mail")
    facade = CapabilityExecution(
        executor=executor, search_service=FakeSearch(), computer_runtime=runtime
    )
    collected = []
    for event in facade.stream(
        RESOLVED, prompt="Escribe", capabilities=CapabilityRequest(computer_use=True)
    ):
        collected.append(event)
        if event.kind == "approval.requested":
            approval = event.data["approval"]
            assert approval["app"] == "Mail"
            assert facade.resolve_approval(event.data["tool_run_id"], "allow_once")
    event_kinds = kinds(collected)
    assert "approval.resolved" in event_kinds
    assert runtime.executed == ["keyboard.type"]
    summary = collected[-1].data
    assert summary["mode"] == "computer" and summary["approvals"] == 1
    assert "Borrador escrito" in collected[-2].data["delta"]


def test_approval_timeout_rejects_without_executing():
    executor = FakeExecutor(
        [
            json.dumps({"action": "keyboard.type", "text": "x"}),
            json.dumps({"action": "finish", "summary": "sin aprobacion"}),
        ]
    )
    runtime = FakeRuntime(app="Mail")
    facade = CapabilityExecution(
        executor=executor,
        search_service=FakeSearch(),
        computer_runtime=runtime,
        approval_timeout=0.1,
    )
    events = list(
        facade.stream(
            RESOLVED, prompt="Escribe", capabilities=CapabilityRequest(computer_use=True)
        )
    )
    assert runtime.executed == []
    resolved = [e for e in events if e.kind == "approval.resolved"]
    assert resolved[0].data["decision"] == "reject"
    assert events[-1].data["rejections"] == 1


def test_resolve_approval_validates_decisions_and_unknown_ids():
    facade = CapabilityExecution(executor=FakeExecutor([]), search_service=FakeSearch())
    with pytest.raises(ValueError):
        facade.resolve_approval("x", "always")
    assert facade.resolve_approval("missing", "allow_once") is False


def test_capability_status_reports_computer_permissions():
    facade = CapabilityExecution(
        executor=FakeExecutor([]),
        search_service=FakeSearch(),
        computer_runtime=FakeRuntime(permissions=PermissionState(False, False, "Accesibilidad")),
    )
    status = facade.capability_status()
    assert status["web_search"]["available"] is True
    assert status["computer"]["available"] is False
    assert status["computer"]["permissions"]["accessibility"] is False


def test_model_failures_propagate_normalized():
    from cmm.model_execution.errors import ModelExecutionError

    class FailingExecutor:
        def stream(self, resolved, **kwargs):
            raise ModelExecutionError("no answer", code="PROVIDER_FAILURE")
            yield  # pragma: no cover

    facade = CapabilityExecution(executor=FailingExecutor(), search_service=FakeSearch())
    with pytest.raises(ModelExecutionError) as info:
        list(facade.stream(RESOLVED, prompt="hola", capabilities=CapabilityRequest()))
    assert info.value.code == "PROVIDER_FAILURE"


def test_computer_mode_can_compose_web_search():
    executor = FakeExecutor(
        [
            json.dumps({"action": "web.search", "query": "pagina oficial"}),
            json.dumps({"action": "app.open", "app": "Safari"}),
            json.dumps({"action": "finish", "summary": "Abierto"}),
        ]
    )
    search = FakeSearch()
    facade = CapabilityExecution(
        executor=executor, search_service=search, computer_runtime=FakeRuntime(app="Finder")
    )
    events = list(
        facade.stream(
            RESOLVED,
            prompt="Busca y abre",
            capabilities=CapabilityRequest(web_search="on", computer_use=True),
        )
    )
    web_events = [e for e in events if e.data.get("capability") == "web.search"]
    assert web_events and search.queries == ["pagina oficial"]
    completed = [e for e in web_events if e.kind == "tool.completed"]
    assert completed[0].data["sources"][0]["url"] == "https://example.com/doc"
    assert events[-1].data["mode"] == "computer"


def test_event_contract_is_closed():
    with pytest.raises(ValueError):
        CapabilityEvent(kind="provider.raw", data={})
    with pytest.raises(ValueError):
        CapabilityRequest(web_search="maybe")
