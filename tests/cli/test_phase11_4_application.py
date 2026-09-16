"""Phase 11.4 — the thin CLI-to-application adapter.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

``CliApplicationAdapter`` is the only place the public CLI reaches the canonical
application boundary.  It owns exactly one collaborator — the real
``ApplicationGateway`` — builds versioned public requests with the CLI channel,
and projects the safe application response back into the frozen CLI result.

The tests here run against the real local canonical runtime, observe the real
``ApplicationGateway`` and the real ``Orchestrator`` through recording wrappers
that still execute the canonical implementation, and prove that the CLI adds no
authority of its own: no orchestrator reference, no lower-owner import, no
unsafe field and no raw defect text.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from cmm.application import (
    APPLICATION_API_VERSION,
    ApplicationChannel,
    ApplicationErrorCode,
    ApplicationGateway,
    ApplicationOperation,
    ApplicationRequest,
    ApplicationStatus,
)
from cmm.application.local_runtime import build_local_application_runtime
from cmm.cli_application import CliApplicationAdapter
from cmm.cli_contracts import CliResult
from cmm.orchestration.contracts import OrchestrationChannel, OrchestrationRequest

ADAPTER_PATH = Path(__file__).resolve().parents[2] / "cmm" / "cli_application.py"

ACTOR_ID = "actor-1"
MESSAGE_TEXT = "What changed in the plan?"

#: Raw internal defect text that must never reach a CLI result.
RAW_DEFECT_TEXT = (
    "Traceback (most recent call last): internal defect at "
    "/private/tmp/cmm-internal-detail with secret AKIA-EXAMPLE-SECRET-KEY"
)

#: The frozen safe projection of one ``status`` result.
STATUS_DATA_KEYS = frozenset(
    {
        "platform_state",
        "platform_ready",
        "application_api_version",
        "services",
        "capabilities",
    }
)


class _Recorder:
    """Records the public requests one real gateway handles, and still runs them."""

    def __init__(self, gateway: ApplicationGateway) -> None:
        self.gateway = gateway
        self.requests: list[ApplicationRequest] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original = self.gateway.handle

        def recording(request: ApplicationRequest) -> Any:
            self.requests.append(request)
            return original(request)

        monkeypatch.setattr(self.gateway, "handle", recording)

    @property
    def operations(self) -> list[ApplicationOperation]:
        return [request.operation for request in self.requests]


class _OrchestrationRecorder:
    """Records the canonical requests one real orchestrator receives."""

    def __init__(self, orchestrator: Any) -> None:
        self.orchestrator = orchestrator
        self.requests: list[OrchestrationRequest] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original = self.orchestrator.orchestrate

        def recording(request: OrchestrationRequest) -> Any:
            self.requests.append(request)
            return original(request)

        monkeypatch.setattr(self.orchestrator, "orchestrate", recording)


def _adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[CliApplicationAdapter, _Recorder, Any]:
    runtime = build_local_application_runtime()
    recorder = _Recorder(runtime.gateway)
    recorder.install(monkeypatch)
    return CliApplicationAdapter(runtime.gateway), recorder, runtime


# ── Authority boundary ───────────────────────────────────────────────────────


def test_the_adapter_owns_only_the_application_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, runtime = _adapter(monkeypatch)

    assert set(vars(adapter)) == {"_gateway"}
    assert adapter._gateway is runtime.gateway


def test_the_adapter_rejects_anything_but_the_gateway() -> None:
    with pytest.raises(TypeError):
        CliApplicationAdapter(object())  # type: ignore[arg-type]


def test_the_adapter_imports_no_lower_owner() -> None:
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for module in imported:
        assert not module.startswith(
            (
                "cmm.orchestration",
                "cmm.domains",
                "cmm.agent_runtime",
                "cmm.runtime",
                "cmm.workflows",
                "kernel",
            )
        ), module
        if module.startswith("cmm."):
            assert module.startswith(("cmm.application", "cmm.cli_")), module


def test_the_adapter_stores_no_orchestrator_or_session_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, runtime = _adapter(monkeypatch)

    values = list(vars(adapter).values())

    assert values == [runtime.gateway]
    assert not any(isinstance(value, ApplicationChannel) for value in values)


# ── status ───────────────────────────────────────────────────────────────────


def test_status_reads_health_and_capabilities_through_the_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, recorder, _ = _adapter(monkeypatch)

    result = adapter.status()

    assert recorder.operations == [
        ApplicationOperation.HEALTH_GET,
        ApplicationOperation.CAPABILITIES_LIST,
    ]
    assert all(
        request.channel is ApplicationChannel.CLI for request in recorder.requests
    )
    assert result.command == "status"
    assert result.ok is True
    assert result.status == ApplicationStatus.SUCCESS.value
    assert result.error is None
    assert result.metadata["request_id"] in {
        request.request_id for request in recorder.requests
    }
    assert result.metadata["api_version"] == APPLICATION_API_VERSION


def test_status_projects_safe_readiness_and_capability_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, _ = _adapter(monkeypatch)

    result = adapter.status()
    data = result.to_dict()["data"]

    assert set(data) == STATUS_DATA_KEYS
    assert data["platform_state"] in {"ok", "degraded"}
    assert data["platform_ready"] is True
    assert data["application_api_version"] == "v1"
    assert data["services"] == sorted(data["services"])
    assert "orchestration.orchestrator" in data["services"]
    assert "domain.registry" in data["services"]

    capabilities = data["capabilities"]
    assert [entry["capability_id"] for entry in capabilities] == sorted(
        entry["capability_id"] for entry in capabilities
    )
    declared = {entry["capability_id"]: entry for entry in capabilities}
    assert declared["health"]["status"] == "available"
    assert declared["request-cancellation"]["status"] == "unavailable"
    assert declared["domains"]["status"] == "deferred"


def test_status_carries_the_primary_quiet_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, _ = _adapter(monkeypatch)

    metadata = adapter.status().to_dict()["metadata"]

    assert set(metadata) == {"request_id", "api_version", "quiet_value"}
    assert metadata["quiet_value"] in {"ok", "degraded"}


def test_status_is_deterministic_in_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, _ = _adapter(monkeypatch)

    first = adapter.status().to_dict()
    second = adapter.status().to_dict()

    first["metadata"] = second["metadata"] = {}
    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True)) == first


def test_status_surfaces_a_gateway_failure_as_a_safe_cli_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, runtime = _adapter(monkeypatch)

    def _defective_health() -> Any:
        raise RuntimeError(RAW_DEFECT_TEXT)

    monkeypatch.setattr(
        vars(runtime.gateway)["_health"], "get_health", _defective_health
    )

    result = adapter.status()

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == ApplicationErrorCode.INTERNAL_FAILURE.value
    rendered = json.dumps(result.to_dict())
    assert RAW_DEFECT_TEXT not in rendered
    assert "AKIA-EXAMPLE-SECRET-KEY" not in rendered
    assert "Traceback" not in rendered


# ── ask ──────────────────────────────────────────────────────────────────────


def test_ask_creates_one_session_and_submits_one_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, recorder, runtime = _adapter(monkeypatch)
    orchestration = _OrchestrationRecorder(runtime.orchestrator)
    orchestration.install(monkeypatch)

    result = adapter.ask(text=MESSAGE_TEXT, actor_id=ACTOR_ID)

    assert recorder.operations == [
        ApplicationOperation.SESSION_CREATE,
        ApplicationOperation.MESSAGE_SUBMIT,
    ]
    assert result.command == "ask"
    assert result.ok is True
    assert result.data["session_id"]
    assert result.data["decision_id"]

    # The canonical pipeline received exactly one request, on the CLI channel.
    assert len(orchestration.requests) == 1
    assert orchestration.requests[0].channel is OrchestrationChannel.CLI
    assert orchestration.requests[0].user_id == ACTOR_ID
    assert orchestration.requests[0].session_id == result.data["session_id"]


def test_ask_reuses_an_explicit_session(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, recorder, _ = _adapter(monkeypatch)
    created = adapter.create_session(session_id="session-1")
    session_id = created.data["session_id"]
    recorder.requests.clear()

    result = adapter.ask(text=MESSAGE_TEXT, actor_id=ACTOR_ID, session_id=session_id)

    assert recorder.operations == [ApplicationOperation.MESSAGE_SUBMIT]
    assert result.data["session_id"] == session_id


def test_ask_reports_an_unknown_session_as_a_safe_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, _ = _adapter(monkeypatch)

    result = adapter.ask(
        text=MESSAGE_TEXT, actor_id=ACTOR_ID, session_id="session-missing"
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == ApplicationErrorCode.RESOURCE_NOT_FOUND.value


def test_ask_submits_no_message_when_session_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, recorder, runtime = _adapter(monkeypatch)

    def _defective_create_session(session_id: str) -> Any:
        raise ValueError(RAW_DEFECT_TEXT)

    monkeypatch.setattr(
        vars(runtime.gateway)["_sessions"], "create_session", _defective_create_session
    )

    result = adapter.ask(text=MESSAGE_TEXT, actor_id=ACTOR_ID)

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == ApplicationErrorCode.INTERNAL_FAILURE.value
    # The session was attempted and the message was never submitted.
    assert recorder.operations == [ApplicationOperation.SESSION_CREATE]
    assert RAW_DEFECT_TEXT not in json.dumps(result.to_dict())


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_ask_rejects_blank_text(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    adapter, _, _ = _adapter(monkeypatch)

    with pytest.raises(ValueError):
        adapter.ask(text=text, actor_id=ACTOR_ID)


@pytest.mark.parametrize("actor", ["", "   "])
def test_ask_rejects_a_blank_actor(monkeypatch: pytest.MonkeyPatch, actor: str) -> None:
    adapter, _, _ = _adapter(monkeypatch)

    with pytest.raises(ValueError):
        adapter.ask(text=MESSAGE_TEXT, actor_id=actor)


def test_ask_never_invents_an_actor_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, _ = _adapter(monkeypatch)
    monkeypatch.setenv("USER", "environment-user")
    monkeypatch.setenv("USERNAME", "environment-user")

    with pytest.raises(TypeError):
        adapter.ask(text=MESSAGE_TEXT)  # type: ignore[call-arg]


# ── idempotency ──────────────────────────────────────────────────────────────


def test_a_keyed_ask_replays_one_canonical_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, runtime = _adapter(monkeypatch)
    orchestration = _OrchestrationRecorder(runtime.orchestrator)
    orchestration.install(monkeypatch)
    created = adapter.create_session(session_id="session-1")
    session_id = created.data["session_id"]

    first = adapter.ask(
        text=MESSAGE_TEXT,
        actor_id=ACTOR_ID,
        session_id=session_id,
        idempotency_key="key-1",
    )
    second = adapter.ask(
        text=MESSAGE_TEXT,
        actor_id=ACTOR_ID,
        session_id=session_id,
        idempotency_key="key-1",
    )

    assert first == second
    assert len(orchestration.requests) == 1


def test_a_keyed_ask_with_changed_text_is_an_idempotency_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, _ = _adapter(monkeypatch)
    created = adapter.create_session(session_id="session-1")
    session_id = created.data["session_id"]

    adapter.ask(
        text=MESSAGE_TEXT,
        actor_id=ACTOR_ID,
        session_id=session_id,
        idempotency_key="key-1",
    )
    conflict = adapter.ask(
        text="A materially different question",
        actor_id=ACTOR_ID,
        session_id=session_id,
        idempotency_key="key-1",
    )

    assert conflict.ok is False
    assert conflict.error is not None
    assert conflict.error.code == ApplicationErrorCode.IDEMPOTENCY_CONFLICT.value
    assert "A materially different question" not in json.dumps(conflict.to_dict())


# ── chat message submission ──────────────────────────────────────────────────


def test_submit_message_uses_an_existing_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, recorder, runtime = _adapter(monkeypatch)
    orchestration = _OrchestrationRecorder(runtime.orchestrator)
    orchestration.install(monkeypatch)
    created = adapter.create_session(session_id="session-1")
    session_id = created.data["session_id"]
    recorder.requests.clear()

    first = adapter.submit_message(
        text="hello", actor_id=ACTOR_ID, session_id=session_id
    )
    second = adapter.submit_message(
        text="second message", actor_id=ACTOR_ID, session_id=session_id
    )

    assert recorder.operations == [
        ApplicationOperation.MESSAGE_SUBMIT,
        ApplicationOperation.MESSAGE_SUBMIT,
    ]
    assert all(
        request.channel is ApplicationChannel.CLI for request in recorder.requests
    )
    assert [request.user_id for request in orchestration.requests] == [
        ACTOR_ID,
        ACTOR_ID,
    ]
    assert all(
        request.channel is OrchestrationChannel.CLI
        for request in orchestration.requests
    )
    assert first.command == "chat"
    assert second.command == "chat"
    # Two independent messages, not a replay: distinct canonical message ids.
    message_ids = {request.payload["message_id"] for request in recorder.requests}
    assert len(message_ids) == 2


def test_submit_message_returns_a_result_that_can_be_rendered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, _ = _adapter(monkeypatch)
    created = adapter.create_session(session_id="session-1")

    result = adapter.submit_message(
        text=MESSAGE_TEXT,
        actor_id=ACTOR_ID,
        session_id=created.data["session_id"],
    )

    assert isinstance(result, CliResult)
    assert json.loads(json.dumps(result.to_dict(), sort_keys=True)) == result.to_dict()


def test_create_session_returns_the_application_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, _ = _adapter(monkeypatch)

    created = adapter.create_session(session_id="session-1", actor_id=ACTOR_ID)

    assert created.status is ApplicationStatus.SUCCESS
    assert created.data["session_id"] == "session-1"
    assert created.data["revision"] == 1
