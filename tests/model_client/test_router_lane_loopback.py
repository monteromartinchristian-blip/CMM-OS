"""The CHAT_ONLY router lane, proven over a real loopback socket.

The frozen CMMChat Router cannot be modified and its subscription upstreams are
external preconditions, so the lane's own contract is exercised here against a
minimal OpenAI-compatible double that speaks the Router's wire: bearer-gated
``/v1/models`` discovery and ``/v1/chat/completions`` as server-sent events that
honour client disconnect.  What is proven is the seam side of section 11's
validation list — selection, stream lifecycle, cancellation, auth-unavailable
and model-unavailable — over real HTTP, with the real canonical transport.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cmm.model_client import ModelClient, ModelClientError

BEARER = "loopback-test-bearer"
MODEL_ONE = "router-model-one"
MODEL_TWO = "router-model-two"


class _RouterDouble:
    """A loopback stand-in for the Router's OpenAI-compatible surface."""

    def __init__(self, *, bearer: str = BEARER, deltas: tuple[str, ...] = ("Ho", "la CMM")) -> None:
        self.bearer = bearer
        self.deltas = deltas
        self.requests: list[dict] = []
        self.saw_disconnect = threading.Event()
        self.chunk_gap = 1.5
        double = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: object) -> None:
                pass

            def _authorized(self) -> bool:
                return self.headers.get("Authorization") == f"Bearer {double.bearer}"

            def do_GET(self) -> None:  # noqa: N802 - http.server contract
                double.requests.append(
                    {"method": "GET", "path": self.path,
                     "authorization": self.headers.get("Authorization")}
                )
                if self.path.rstrip("/").endswith("/models"):
                    if not self._authorized():
                        self._json(401, {"error": {"type": "invalid_request", "message": "bad bearer"}})
                        return
                    self._json(
                        200,
                        {
                            "object": "list",
                            "data": [
                                {"id": MODEL_ONE, "object": "model"},
                                {"id": MODEL_TWO, "object": "model"},
                            ],
                        },
                    )
                    return
                self._json(200, {"status": "ok"})

            def do_POST(self) -> None:  # noqa: N802 - http.server contract
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                if not self._authorized():
                    self._json(401, {"error": {"type": "invalid_request", "message": "bad bearer"}})
                    return
                double.requests.append(
                    {"headers": {k.lower(): v for k, v in self.headers.items()},
                     "body": body}
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                try:
                    import time as _time

                    for index, delta in enumerate(double.deltas):
                        if index:
                            _time.sleep(double.chunk_gap)
                        self._chunk(
                            {
                                "id": "chatcmpl-double",
                                "object": "chat.completion.chunk",
                                "created": 0,
                                "model": body.get("model", ""),
                                "choices": [
                                    {"index": 0, "delta": {"content": delta}, "finish_reason": None}
                                ],
                            }
                        )
                    self._chunk(
                        {
                            "id": "chatcmpl-double",
                            "object": "chat.completion.chunk",
                            "created": 0,
                            "model": body.get("model", ""),
                            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                        }
                    )
                    self.wfile.write(b"0\r\n\r\n")
                except (BrokenPipeError, ConnectionResetError):
                    double.saw_disconnect.set()
                    return
                self.wfile.flush()

            def _chunk(self, payload: dict) -> None:
                line = f"data: {json.dumps(payload)}\n\n".encode()
                self.wfile.write(f"{len(line):x}\r\n".encode() + line + b"\r\n")
                self.wfile.flush()

            def _json(self, status: int, payload: dict) -> None:
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/v1"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def router_double(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CMM_ROUTER_TOKEN", BEARER)
    monkeypatch.delenv("CMM_ROUTER_DISABLED", raising=False)
    monkeypatch.delenv("CMM_ROUTER_MODEL", raising=False)
    monkeypatch.delenv("CMM_LOCAL_RUNTIME_MODEL_IDS", raising=False)
    double = _RouterDouble()
    yield double
    double.stop()


def _client(double: _RouterDouble) -> ModelClient:
    return ModelClient(router_base_url=double.base_url)


def test_discovery_advertises_the_lane_over_the_real_socket(router_double) -> None:
    client = _client(router_double)

    try:
        models = client.catalog()
    except ModelClientError as error:
        raise AssertionError(
            f"catalog failed: {error.code}; GET auth seen: "
            f"{[r.get('authorization') for r in router_double.requests if r.get('method') == 'GET']}"
        ) from error

    assert {model.id for model in models} == {MODEL_ONE, MODEL_TWO}
    assert {model.provider_id for model in models} == {"cmmchat-router"}
    assert all(model.locality == "local" for model in models)


def test_stream_lifecycle_carries_the_bearer_and_the_transcript(router_double) -> None:
    client = _client(router_double)
    resolved = client.resolve(MODEL_ONE)

    deltas = list(
        client.stream(
            resolved,
            prompt="mundo",
            system="sys",
            history=({"role": "user", "content": "hola"},),
        )
    )

    assert "".join(deltas) == "Hola CMM"
    call = next(r for r in router_double.requests if "body" in r)
    assert call["headers"]["authorization"] == f"Bearer {BEARER}"
    assert call["body"]["model"] == MODEL_ONE
    assert call["body"]["stream"] is True
    assert [message["role"] for message in call["body"]["messages"]] == [
        "system",
        "user",
        "user",
    ]


def test_cancellation_stops_the_product_stream_at_the_transport(router_double) -> None:
    router_double.deltas = tuple(f"d{i} " for i in range(400))
    router_double.chunk_gap = 0.01
    client = _client(router_double)
    resolved = client.resolve(MODEL_ONE)
    cancel = threading.Event()

    received: list[str] = []

    def consume() -> None:
        for delta in client.stream(resolved, prompt="x", cancel_event=cancel):
            received.append(delta)
            cancel.set()

    worker = threading.Thread(target=consume, daemon=True)
    worker.start()
    worker.join(timeout=30)
    router_double.saw_disconnect.wait(timeout=30)

    # The product stream stopped at the first delta: the cancel reached the
    # read loop, the iterator was closed, and the transport observed the close.
    assert received == ["d0 "]
    assert router_double.saw_disconnect.is_set()


def test_a_wrong_bearer_is_normalized_without_leaking_it(
    router_double, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CMM_ROUTER_TOKEN", "not-the-double-bearer")
    client = _client(router_double)

    with pytest.raises(ModelClientError) as raised:
        client.catalog()

    assert raised.value.code in {"PROVIDER_FAILURE", "PROVIDER_UNAVAILABLE"}
    assert "not-the-double-bearer" not in raised.value.message


def test_an_unadvertised_model_is_refused_before_any_call(router_double) -> None:
    client = _client(router_double)

    with pytest.raises(ModelClientError) as raised:
        client.resolve("router-model-absent")

    assert raised.value.code == "MODEL_UNAVAILABLE"
    assert [r for r in router_double.requests if "body" in r] == []
