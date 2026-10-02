"""Socket rendezvous regression tests (the product transport).

The Mac app serves the helper on a Unix-domain socket; the Hub only ever
connects. These tests drive the real socket transport against scripted fake
servers over real sockets: framing, timeouts, reconnects, missing/stale
sockets, and the transport selection contract. No test here spawns a child.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time as _time

import pytest

from cmm.computer.bridge import (
    BRIDGE_BUNDLE_ID,
    BridgeClient,
    BridgeUnavailable,
    default_bridge_socket,
)
from cmm.computer.errors import ComputerUseError
from cmm.computer.loop import ComputerUseService
from cmm.computer.runtime_bridge import BridgeComputerRuntime


class FakeSocketServer:
    """A scripted NDJSON server on a temp Unix socket (real sockets)."""

    _counter = [0]

    def __init__(self, behavior="echo", tmp_path=None):
        import tempfile as _tf

        self.behavior = behavior
        FakeSocketServer._counter[0] += 1
        # AF_UNIX paths are capped (~104 chars on macOS) and pytest tmp
        # paths are long: serve from a short dir under /tmp instead.
        self._dir = _tf.mkdtemp(prefix="cbs")
        self.path = os.path.join(
            self._dir, "f%d.sock" % FakeSocketServer._counter[0])
        try:
            os.unlink(self.path)
        except OSError:
            pass
        self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._listener.bind(self.path)
        self._listener.listen(5)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._conns = []
        self._conns_lock = threading.Lock()

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        import shutil as _sh

        self._stop.set()
        try:
            self._listener.close()
        except OSError:
            pass
        try:
            _sh.rmtree(self._dir, ignore_errors=True)
        except OSError:
            pass

    def kill(self):
        try:
            self._listener.close()
        except OSError:
            pass
        with self._conns_lock:
            conns, self._conns = self._conns, []
        for conn in conns:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _serve(self):
        self._listener.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except OSError:
                continue
            with self._conns_lock:
                self._conns.append(conn)
            threading.Thread(
                target=self._handle, args=(conn,), daemon=True
            ).start()

    def _answer(self, conn, rid, ok, payload):
        if ok:
            frame = {"version": 1, "id": rid, "ok": True, "result": payload}
        else:
            frame = {"version": 1, "id": rid, "ok": False, "error": payload}
        conn.sendall(json.dumps(frame).encode() + b"\n")

    def _handle(self, conn):
        with conn:
            buf = b""
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    if not raw.strip():
                        continue
                    try:
                        req = json.loads(raw.decode("utf-8"))
                    except ValueError:
                        self._answer(conn, None, False, {
                            "code": "ACTION_FAILED", "message": "bad json"})
                        continue
                    rid, op = req.get("id"), req.get("operation")
                    # Identity answers on every behavior except the
                    # fault-injection ones.
                    if op == "bridge.ping" and self.behavior not in (
                            "sleep", "garbage"):
                        self._answer(conn, rid, True, {
                            "bridge": "cmm-computer-use", "protocol": 1,
                            "pid": 4242, "bundle_id": BRIDGE_BUNDLE_ID})
                        continue
                    if self.behavior == "sleep":
                        _time.sleep(30)
                        return
                    if self.behavior == "garbage":
                        conn.sendall(b"this is not json\n")
                        continue
                    if self.behavior == "denied":
                        self._answer(conn, rid, True, {
                            "accessibility": False,
                            "screen_recording": False,
                            "detail": "Accesibilidad"})
                    elif self.behavior == "granted":
                        self._answer(conn, rid, True, {
                            "accessibility": True,
                            "screen_recording": True, "detail": ""})
                    elif op == "bridge.ping":
                        self._answer(conn, rid, True, {
                            "bridge": "cmm-computer-use", "protocol": 1,
                            "pid": 4242, "bundle_id": BRIDGE_BUNDLE_ID})
                    elif op == "permissions.status":
                        self._answer(conn, rid, True, {
                            "accessibility": True,
                            "screen_recording": True, "detail": ""})
                    elif op == "observation.describe":
                        self._answer(conn, rid, True, {
                            "frontmost_app": "Finder",
                            "frontmost_bundle": "com.apple.finder",
                            "windows": [], "elements": [],
                            "screenshot_base64": None, "captured_at": 1.0})
                    elif op == "action.execute":
                        self._answer(conn, rid, True, {
                            "ok": True, "message": "pressed"})
                    else:
                        self._answer(conn, rid, False, {
                            "code": "CAPABILITY_UNSUPPORTED",
                            "message": "Unknown: %s" % (op,)})


def _socket_client(server, **kwargs):
    return BridgeClient(socket_path=server.path, **kwargs)


def test_product_default_is_the_socket(monkeypatch):
    monkeypatch.delenv("CMM_COMPUTER_BRIDGE_DIRECT", raising=False)
    assert BridgeClient().transport_kind == "socket"


def test_direct_env_selects_stdio_child(monkeypatch):
    monkeypatch.setenv("CMM_COMPUTER_BRIDGE_DIRECT", "1")
    assert BridgeClient().transport_kind == "stdio"


def test_argv_list_is_stdio_for_tests():
    assert BridgeClient([sys.executable, "-c", "pass"]).transport_kind == "stdio"


def test_default_socket_path_is_user_private():
    assert default_bridge_socket().endswith(".cmm/computer-bridge/bridge.sock")


def test_socket_ping_and_status(tmp_path):
    with FakeSocketServer(tmp_path=tmp_path) as server:
        client = _socket_client(server)
        try:
            assert client.ping()["bundle_id"] == BRIDGE_BUNDLE_ID
            assert client.request("permissions.status")["accessibility"] is True
        finally:
            client.close()


def test_socket_unknown_op_rejected(tmp_path):
    with FakeSocketServer(tmp_path=tmp_path) as server:
        client = _socket_client(server)
        try:
            with pytest.raises(ComputerUseError) as caught:
                client.request("bogus.op")
            assert caught.value.code == "CAPABILITY_UNSUPPORTED"
        finally:
            client.close()


def test_socket_garbage_is_unavailable(tmp_path):
    with FakeSocketServer("garbage", tmp_path=tmp_path) as server:
        client = _socket_client(server)
        try:
            with pytest.raises(BridgeUnavailable):
                client.request("bridge.ping", {}, timeout=5)
        finally:
            client.close()


def test_socket_timeout_disconnects(tmp_path):
    with FakeSocketServer("sleep", tmp_path=tmp_path) as server:
        client = _socket_client(server, timeout=0.5)
        try:
            with pytest.raises(BridgeUnavailable):
                client.request("bridge.ping")
            assert client.alive is False
        finally:
            client.close()


def test_socket_server_death_is_unavailable(tmp_path):
    with FakeSocketServer(tmp_path=tmp_path) as server:
        client = _socket_client(server)
        try:
            assert client.ping()["bundle_id"] == BRIDGE_BUNDLE_ID
            server.kill()
            with pytest.raises(BridgeUnavailable):
                client.request("bridge.ping", {}, timeout=2)
        finally:
            client.close()


def test_missing_socket_is_unavailable(tmp_path):
    client = BridgeClient(socket_path=str(tmp_path / "nobody-listens.sock"))
    try:
        runtime = BridgeComputerRuntime(client)
        assert runtime.available() is False
        status = ComputerUseService(
            runtime=runtime, plan=lambda *_: "{}").status()
        assert status["runtime_available"] is False
        assert status["available"] is False
    finally:
        client.close()


def test_socket_permission_denied_propagates(tmp_path):
    with FakeSocketServer("denied", tmp_path=tmp_path) as server:
        runtime = BridgeComputerRuntime(_socket_client(server))
        try:
            status = ComputerUseService(
                runtime=runtime, plan=lambda *_: "{}").status()
            assert status["runtime_available"] is True
            assert status["available"] is False
        finally:
            runtime.close()


def test_socket_granted_is_available(tmp_path):
    with FakeSocketServer("granted", tmp_path=tmp_path) as server:
        runtime = BridgeComputerRuntime(_socket_client(server))
        try:
            status = ComputerUseService(
                runtime=runtime, plan=lambda *_: "{}").status()
            assert status["available"] is True
        finally:
            runtime.close()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS helper")
def test_live_socket_served_by_the_mac_app(monkeypatch):
    import os as _os

    monkeypatch.delenv("CMM_COMPUTER_BRIDGE_DIRECT", raising=False)
    if not _os.path.exists(default_bridge_socket()):
        pytest.skip("Mac app is not serving the helper socket")
    runtime = BridgeComputerRuntime()
    try:
        assert runtime.available() is True
        status = ComputerUseService(
            runtime=runtime, plan=lambda *_: "{}").status()
        assert status["runtime_available"] is True
        assert set(status["permissions"]) == {
            "accessibility", "screen_recording", "detail"}
    finally:
        runtime.close()
