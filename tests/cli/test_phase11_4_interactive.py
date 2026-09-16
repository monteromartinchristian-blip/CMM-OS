"""Phase 11.4 — the one-shot ``ask`` and the minimal interactive ``chat``.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

``ask`` and ``chat`` are the two conversational commands of the one public front
door.  Both are thin: they resolve exactly one canonical session through the
CLI application adapter when the caller did not name one, submit text through
the canonical ``ApplicationGateway`` on the CLI channel, and render the safe
result.  Neither owns a conversation, a transcript, a history file, an
orchestrator reference or a session store.

The tests here drive the real root ``main()`` with a real local canonical
runtime and injected streams, so what is proven is the public behavior a user
and a script actually get: which requests reach the canonical graph, what
reaches stdout versus stderr, which exit code the process returns, and that a
local interruption is reported as a local cancellation rather than as a
canonical one.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

import cmm.__main__ as cli_main
from cmm.application import (
    ApplicationChannel,
    ApplicationErrorCode,
    ApplicationOperation,
    ApplicationRequest,
    ApplicationStatus,
)
from cmm.application.local_runtime import build_local_application_runtime
from cmm.cli_application import CliApplicationAdapter
from cmm.cli_contracts import CliExitCode
from cmm.cli_doctor import CliDoctor
from cmm.orchestration.contracts import OrchestrationChannel, OrchestrationRequest

ACTOR_ID = "actor-1"
ANSI_ESCAPE = "\x1b"

#: Words a local cancellation must never use, because the CLI can not cancel a
#: canonical request: it only stops reading locally.
CANONICAL_CANCELLATION_CLAIM = "no canonical cancellation"


class _GatewayRecorder:
    """Records the public requests one real gateway handles, and still runs them."""

    def __init__(self, gateway: Any) -> None:
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


@pytest.fixture
def runtime():
    return build_local_application_runtime()


@pytest.fixture
def adapter(runtime) -> CliApplicationAdapter:
    return CliApplicationAdapter(runtime.gateway)


@pytest.fixture
def doctor(adapter: CliApplicationAdapter) -> CliDoctor:
    return CliDoctor(adapter)


def _run(
    argv: list[str],
    *,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    stdin = io.StringIO("" if stdin_text is None else stdin_text)
    code = cli_main.main(
        argv,
        application=adapter,
        doctor=doctor,
        stdin=stdin,
        stdout=out,
        stderr=err,
    )
    return code, out.getvalue(), err.getvalue()


def _error_document(text: str) -> dict[str, Any]:
    return json.loads(text)


# ── ask: exactly one canonical one-shot request ──────────────────────────────


def test_ask_submits_one_request_from_an_argument(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)
    orchestration = _OrchestrationRecorder(runtime.orchestrator)
    orchestration.install(monkeypatch)

    code, out, err = _run(
        ["ask", "hello", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
    )

    assert (code, err) == (0, "")
    document = json.loads(out)
    assert document["schema_version"] == "v1"
    assert document["command"] == "ask"
    assert document["ok"] is True
    assert document["error"] is None
    assert gateway_recorder.operations == [
        ApplicationOperation.SESSION_CREATE,
        ApplicationOperation.MESSAGE_SUBMIT,
    ]
    assert all(
        request.channel is ApplicationChannel.CLI
        for request in gateway_recorder.requests
    )
    assert len(orchestration.requests) == 1
    assert orchestration.requests[0].channel is OrchestrationChannel.CLI
    assert orchestration.requests[0].user_id == ACTOR_ID
    assert orchestration.requests[0].input["content"] == "hello"


def test_ask_reads_the_request_from_stdin_when_no_argument_is_given(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)
    orchestration = _OrchestrationRecorder(runtime.orchestrator)
    orchestration.install(monkeypatch)

    code, out, err = _run(
        ["ask", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello from stdin\n",
    )

    assert (code, err) == (0, "")
    assert json.loads(out)["ok"] is True
    assert len(orchestration.requests) == 1
    assert orchestration.requests[0].input["content"] == "hello from stdin"


def test_ask_refuses_an_argument_and_stdin_at_once(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)

    code, out, err = _run(
        ["ask", "from argument", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="from stdin\n",
    )

    assert code == int(CliExitCode.INVALID_REQUEST) == 3
    assert out == ""
    document = _error_document(err)
    assert document["command"] == "ask"
    assert document["ok"] is False
    assert document["error"]["code"] == ApplicationErrorCode.INVALID_REQUEST.value
    assert "Traceback" not in err
    assert gateway_recorder.requests == []


def test_ask_refuses_an_invocation_with_no_request_text(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)

    code, out, err = _run(
        ["ask", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="   \n",
    )

    assert code == 3
    assert out == ""
    assert _error_document(err)["error"]["code"] == "INVALID_REQUEST"
    assert gateway_recorder.requests == []


def test_ask_reuses_an_explicit_session(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    created = adapter.create_session(session_id="session-1")
    session_id = created.data["session_id"]
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)

    code, _, err = _run(
        [
            "ask",
            "hello",
            "--actor",
            ACTOR_ID,
            "--session",
            session_id,
            "--output",
            "json",
        ],
        adapter=adapter,
        doctor=doctor,
    )

    assert (code, err) == (0, "")
    assert gateway_recorder.operations == [ApplicationOperation.MESSAGE_SUBMIT]
    assert gateway_recorder.requests[0].session_id == session_id


def test_ask_reports_an_unknown_session_with_the_not_found_exit(
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
) -> None:
    code, out, err = _run(
        [
            "ask",
            "hello",
            "--actor",
            ACTOR_ID,
            "--session",
            "session-missing",
            "--output",
            "json",
        ],
        adapter=adapter,
        doctor=doctor,
    )

    assert code == int(CliExitCode.NOT_FOUND) == 4
    assert out == ""
    document = _error_document(err)
    assert document["error"]["code"] == ApplicationErrorCode.RESOURCE_NOT_FOUND.value
    assert "Traceback" not in err


def test_ask_carries_the_idempotency_key_to_the_application_command(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    created = adapter.create_session(session_id="session-1")
    session_id = created.data["session_id"]
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)
    orchestration = _OrchestrationRecorder(runtime.orchestrator)
    orchestration.install(monkeypatch)
    argv = [
        "ask",
        "hello",
        "--actor",
        ACTOR_ID,
        "--session",
        session_id,
        "--idempotency-key",
        "key-1",
        "--output",
        "json",
    ]

    first = _run(argv, adapter=adapter, doctor=doctor)
    second = _run(argv, adapter=adapter, doctor=doctor)

    assert first[0] == second[0] == 0
    assert first[1] == second[1]
    message_ids = {
        request.payload["message_id"] for request in gateway_recorder.requests
    }
    assert len(message_ids) == 1
    assert len(orchestration.requests) == 1


def test_ask_reports_a_local_interruption_without_claiming_canonical_cancellation(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    def _interrupted(request: Any) -> Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(runtime.gateway, "handle", _interrupted)

    code, out, err = _run(
        ["ask", "hello", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
    )

    assert code == int(CliExitCode.CANCELLED) == 9
    assert out == ""
    document = _error_document(err)
    assert document["command"] == "ask"
    assert document["ok"] is False
    assert document["error"]["code"] == ApplicationErrorCode.CANCELLED.value
    assert CANONICAL_CANCELLATION_CLAIM in document["error"]["message"]
    assert "Traceback" not in err


# ── chat: one session, one loop, no local conversation state ─────────────────


def test_chat_submits_every_line_into_one_canonical_session(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)
    orchestration = _OrchestrationRecorder(runtime.orchestrator)
    orchestration.install(monkeypatch)

    code, _, err = _run(
        ["chat", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\nsecond message\n/exit\n",
    )

    assert (code, err) == (0, "")
    assert gateway_recorder.operations == [
        ApplicationOperation.SESSION_CREATE,
        ApplicationOperation.MESSAGE_SUBMIT,
        ApplicationOperation.MESSAGE_SUBMIT,
    ]
    assert all(
        request.channel is ApplicationChannel.CLI
        for request in gateway_recorder.requests
    )
    assert [request.input["content"] for request in orchestration.requests] == [
        "hello",
        "second message",
    ]
    assert all(
        request.channel is OrchestrationChannel.CLI
        for request in orchestration.requests
    )
    session_ids = {request.session_id for request in orchestration.requests}
    assert len(session_ids) == 1
    assert all(session_ids)


def test_chat_ignores_blank_lines_and_terminates_on_quit(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)

    code, _, err = _run(
        ["chat", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\n\n   \n/quit\nhello after quit\n",
    )

    assert (code, err) == (0, "")
    assert gateway_recorder.operations == [
        ApplicationOperation.SESSION_CREATE,
        ApplicationOperation.MESSAGE_SUBMIT,
    ]


def test_chat_terminates_cleanly_on_end_of_input(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)

    code, out, err = _run(
        ["chat", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\n",
    )

    assert (code, err) == (0, "")
    assert gateway_recorder.operations == [
        ApplicationOperation.SESSION_CREATE,
        ApplicationOperation.MESSAGE_SUBMIT,
    ]
    assert json.loads(out.splitlines()[-1])["data"]["termination"] == "eof"


def test_chat_reuses_an_explicit_session(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    created = adapter.create_session(session_id="session-1")
    session_id = created.data["session_id"]
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)

    code, _, err = _run(
        ["chat", "--actor", ACTOR_ID, "--session", session_id, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\n/exit\n",
    )

    assert (code, err) == (0, "")
    assert gateway_recorder.operations == [ApplicationOperation.MESSAGE_SUBMIT]
    assert gateway_recorder.requests[0].session_id == session_id


def test_chat_writes_one_parseable_document_per_turn_and_no_ansi(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    code, out, err = _run(
        ["chat", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\nsecond message\n/exit\n",
    )

    assert (code, err) == (0, "")
    documents = [json.loads(line) for line in out.splitlines() if line.strip()]
    assert [document["command"] for document in documents] == [
        "chat",
        "chat",
        "chat",
    ]
    assert all(document["schema_version"] == "v1" for document in documents)
    termination = documents[-1]
    assert termination["ok"] is True
    assert termination["data"]["termination"] == "exit"
    assert termination["data"]["submitted"] == 2
    assert termination["data"]["failed"] == 0
    assert ANSI_ESCAPE not in out


def test_chat_renders_each_turn_in_human_mode(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    code, out, err = _run(
        ["chat", "--actor", ACTOR_ID],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\n/exit\n",
    )

    assert (code, err) == (0, "")
    assert out.startswith("chat: ")
    assert "Traceback" not in out


def test_chat_continues_after_a_non_terminal_application_failure(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    """An unknown session fails every turn; the local loop still terminates."""

    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)

    code, out, err = _run(
        [
            "chat",
            "--actor",
            ACTOR_ID,
            "--session",
            "session-missing",
            "--output",
            "json",
        ],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\nsecond message\n/exit\n",
    )

    assert code == 0
    assert gateway_recorder.operations == [
        ApplicationOperation.MESSAGE_SUBMIT,
        ApplicationOperation.MESSAGE_SUBMIT,
    ]
    failures = [json.loads(line) for line in err.splitlines() if line.strip()]
    assert [failure["error"]["code"] for failure in failures] == [
        ApplicationErrorCode.RESOURCE_NOT_FOUND.value,
        ApplicationErrorCode.RESOURCE_NOT_FOUND.value,
    ]
    termination = json.loads(out.splitlines()[-1])
    assert termination["ok"] is True
    assert termination["status"] == "degraded"
    assert termination["data"]["submitted"] == 2
    assert termination["data"]["failed"] == 2
    assert termination["data"]["termination"] == "exit"
    assert "Traceback" not in err


def test_chat_exits_with_the_internal_failure_code_and_stops_the_loop(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    gateway_recorder = _GatewayRecorder(runtime.gateway)
    gateway_recorder.install(monkeypatch)

    def _defective_submit(*, request_id: str, message: Any, channel: Any) -> Any:
        raise RuntimeError("internal defect with AKIA-EXAMPLE")

    monkeypatch.setattr(
        vars(runtime.gateway)["_requests"], "submit_message", _defective_submit
    )

    code, out, err = _run(
        ["chat", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\nsecond message\n/exit\n",
    )

    assert code == int(CliExitCode.INTERNAL_FAILURE) == 10
    assert out == ""
    document = _error_document(err)
    assert document["command"] == "chat"
    assert document["ok"] is False
    assert document["error"]["code"] == ApplicationErrorCode.INTERNAL_FAILURE.value
    # The loop stopped at the defect instead of replaying it for every line.
    assert gateway_recorder.operations == [
        ApplicationOperation.SESSION_CREATE,
        ApplicationOperation.MESSAGE_SUBMIT,
    ]
    assert "AKIA" not in err
    assert "Traceback" not in err


def test_chat_reports_a_local_interruption_without_claiming_canonical_cancellation(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    def _interrupted(
        *, text: str, actor_id: str, session_id: str, **kwargs: Any
    ) -> Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(adapter, "submit_message", _interrupted)

    code, out, err = _run(
        ["chat", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\n",
    )

    assert code == int(CliExitCode.CANCELLED) == 9
    assert out == ""
    document = _error_document(err)
    assert document["command"] == "chat"
    assert document["error"]["code"] == ApplicationErrorCode.CANCELLED.value
    assert CANONICAL_CANCELLATION_CLAIM in document["error"]["message"]
    assert "Traceback" not in err


def test_chat_keeps_no_local_conversation_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
) -> None:
    monkeypatch.chdir(tmp_path)

    code, _, err = _run(
        ["chat", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\nsecond message\n/exit\n",
    )

    assert (code, err) == (0, "")
    assert sorted(path.name for path in tmp_path.iterdir()) == []


def test_chat_never_reports_a_canonically_cancelled_request(
    monkeypatch: pytest.MonkeyPatch,
    adapter: CliApplicationAdapter,
    doctor: CliDoctor,
    runtime,
) -> None:
    """The CLI owns no cancellation path, so it never claims one succeeded."""

    code, out, err = _run(
        ["chat", "--actor", ACTOR_ID, "--output", "json"],
        adapter=adapter,
        doctor=doctor,
        stdin_text="hello\n/exit\n",
    )

    assert code == 0
    documents = [json.loads(line) for line in out.splitlines() if line.strip()]
    assert all(
        document["status"] != ApplicationStatus.CANCELLED.value
        for document in documents
    )
    assert "cancel" not in err.lower()
