"""Wave E — canonical provider token streaming tests (kernel layer).

These tests pin the semantic delta ported from the obsolete Phase-10 clone:
provider-independent token streaming with cancellation and a multi-turn
transcript, delivered through the *existing* canonical provider abstraction.
No new gateway, router, registry, catalog or provider owner is introduced.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest

from kernel.llm.clients.openai_compatible_client import OpenAICompatibleClient
from kernel.llm.exceptions import ProviderError
from kernel.llm.models import ChatTurn, LLMRequest
from kernel.llm.openai_compatible_provider import OpenAICompatibleProvider

# ── ChatTurn / LLMRequest transcript ─────────────────────────────────────────


def test_chat_turn_accepts_the_conversational_roles() -> None:
    for role in ("system", "user", "assistant"):
        assert ChatTurn(role=role, content="hola").role == role


def test_chat_turn_rejects_other_roles() -> None:
    with pytest.raises(ValueError):
        ChatTurn(role="tool", content="x")


def test_chat_turn_rejects_empty_content() -> None:
    with pytest.raises(ValueError):
        ChatTurn(role="user", content="   ")


def test_llm_request_history_defaults_to_empty_transcript_to_prompt() -> None:
    request = LLMRequest(prompt="hola")
    assert request.history == ()
    assert request.transcript() == [{"role": "user", "content": "hola"}]


def test_transcript_orders_system_then_history_then_prompt() -> None:
    request = LLMRequest(
        prompt="respuesta",
        system_prompt="eres CMMChat",
        history=(
            ChatTurn(role="user", content="hola"),
            ChatTurn(role="assistant", content="¡hey!"),
        ),
    )
    assert request.transcript() == [
        {"role": "system", "content": "eres CMMChat"},
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "¡hey!"},
        {"role": "user", "content": "respuesta"},
    ]


# ── OpenAICompatibleClient.stream_chat over a scripted SDK ───────────────────


def _chunk(text: str | None) -> SimpleNamespace:
    delta = SimpleNamespace(content=text)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


class _ScriptedStream:
    """A fake SDK stream object: yields preset chunks, tracks closure."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self.closed = False

    def __iter__(self):
        for event in self._events:
            if callable(event):
                event()
                continue
            yield _chunk(event)

    def close(self) -> None:
        self.closed = True


class _ScriptedSDK:
    def __init__(self, stream: _ScriptedStream) -> None:
        self.stream = stream
        self.calls: list[dict[str, Any]] = []

    @property
    def chat(self):
        outer = self

        class _Chat:
            @property
            def completions(self):
                class _Completions:
                    def create(self, **parameters):
                        outer.calls.append(parameters)
                        return outer.stream

                return _Completions()

        return _Chat()


def _client_with(sdk: Any) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(client=sdk)


def test_stream_chat_yields_only_content_deltas() -> None:
    sdk = _ScriptedSDK(_ScriptedStream(["Hola", None, " mundo"]))
    deltas = list(
        _client_with(sdk).stream_chat(
            model="m", messages=[{"role": "user", "content": "hi"}], temperature=0.0
        )
    )
    assert deltas == ["Hola", " mundo"]
    call = sdk.calls[0]
    assert call["model"] == "m"
    assert call["stream"] is True
    assert call["messages"] == [{"role": "user", "content": "hi"}]


def test_stream_chat_forwards_temperature_and_max_tokens() -> None:
    sdk = _ScriptedSDK(_ScriptedStream(["x"]))
    list(
        _client_with(sdk).stream_chat(
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.5,
            max_tokens=64,
        )
    )
    assert sdk.calls[0]["temperature"] == 0.5
    assert sdk.calls[0]["max_tokens"] == 64


def test_stream_chat_honours_cancellation_and_closes_the_stream() -> None:
    cancel = threading.Event()
    stream = _ScriptedStream(["a", lambda: cancel.set(), "b"])
    sdk = _ScriptedSDK(stream)
    deltas = list(
        _client_with(sdk).stream_chat(
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
            cancel_event=cancel,
        )
    )
    assert deltas == ["a"]
    assert stream.closed is True


def test_stream_chat_normalizes_transport_failures_to_provider_error() -> None:
    """Transport failures become the canonical ProviderError (internal only;
    the seam is what normalizes them into secret-free public failures)."""

    class _Boom:
        @property
        def chat(self):
            class _Chat:
                @property
                def completions(self):
                    class _Completions:
                        def create(self, **_):
                            raise RuntimeError("HTTP 500 upstream said nope")

                    return _Completions()

            return _Chat()

    with pytest.raises(ProviderError):
        list(
            _client_with(_Boom()).stream_chat(
                model="m", messages=[{"role": "user", "content": "hi"}], temperature=0.0
            )
        )


def test_stream_chat_closes_the_stream_when_iteration_fails() -> None:
    class _BrokenStream:
        def __init__(self) -> None:
            self.closed = False

        def __iter__(self):
            yield _chunk("ok")
            raise RuntimeError("connection reset")

        def close(self) -> None:
            self.closed = True

    stream = _BrokenStream()
    collected: list[str] = []
    with pytest.raises(ProviderError):
        for delta in _client_with(_ScriptedSDK(stream)).stream_chat(
            model="m", messages=[{"role": "user", "content": "hi"}], temperature=0.0
        ):
            collected.append(delta)  # noqa: PERF402 - partial deltas are the point
    assert collected == ["ok"]
    assert stream.closed is True


# ── Provider.stream over the canonical abstraction ───────────────────────────


class _RecordingStreamClient:
    """A scripted canonical transport client exposing stream_chat."""

    def __init__(self, deltas: tuple[str, ...]) -> None:
        self._deltas = deltas
        self.stream_calls: list[dict[str, Any]] = []

    def generate(self, **_: Any) -> Any:  # pragma: no cover - unused
        raise AssertionError("generate must not be used by stream")

    def stream_chat(self, **parameters: Any) -> Any:
        self.stream_calls.append(parameters)
        yield from self._deltas


def _provider(client: Any) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        provider_id="cmmchat-router", client=client, model="m"
    )


def test_provider_stream_yields_deltas_and_carries_the_transcript() -> None:
    client = _RecordingStreamClient(("Ho", "la"))
    provider = _provider(client)
    request = LLMRequest(
        prompt="sigue",
        system_prompt="sys",
        history=(ChatTurn(role="user", content="hola"),),
    )
    assert list(provider.stream(request)) == ["Ho", "la"]
    call = client.stream_calls[0]
    assert call["model"] == "m"
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hola"},
        {"role": "user", "content": "sigue"},
    ]
    assert call["cancel_event"] is None


def test_provider_stream_propagates_the_cancel_event() -> None:
    cancel = threading.Event()
    client = _RecordingStreamClient(())
    list(_provider(client).stream(LLMRequest(prompt="x"), cancel_event=cancel))
    assert client.stream_calls[0]["cancel_event"] is cancel


def test_provider_stream_rejects_an_empty_prompt() -> None:
    with pytest.raises(ProviderError):
        list(_provider(_RecordingStreamClient(())).stream(LLMRequest(prompt="  ")))


def test_llm_provider_base_stream_is_explicitly_unsupported() -> None:
    """Providers without a token stream fail closed with a normalized error."""

    from kernel.llm.mock_provider import MockProvider

    with pytest.raises(ProviderError):
        list(MockProvider("text").stream(LLMRequest(prompt="hola")))
