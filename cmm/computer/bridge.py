"""Client for the CMMChat macOS Computer Bridge (``CMM Computer Use``).

The bridge is a small signed native helper whose ONLY job is the macOS
observation/action primitives that require a grantable TCC application
identity. CMM OS remains the orchestrator: it decides WHAT is allowed, the
helper performs the narrow native operation.

Transport (product): the helper is launched by the bundled CMMChat app with
``--serve-socket <path>`` and spoken to over that Unix-domain socket with
line-delimited JSON (protocol version 1). The private socket is the local
transport boundary: no TCP port, no HTTP server, bounded request/response
sizes, an explicit operation allowlist on the helper side, bounded timeouts,
and supervision here (a timed-out or dropped connection is closed and the
next request reconnects).

Why not a Hub child process: on current macOS a helper spawned by the
unbundled Hub interpreter inherits an unusable TCC ancestry — the decision
subject becomes the bare interpreter, never the helper identity, so grants
bound to the helper never apply (proven live via the TCC log). A helper
launched by the bundled app keeps a grantable ancestry. Direct stdio child
mode remains for explicit development use (``CMM_COMPUTER_BRIDGE_DIRECT=1``)
and for tests driving scripted fakes.

Request:  {"version": 1, "id": "...", "operation": "...", "arguments": {...}}
Response: {"version": 1, "id": "...", "ok": true, "result": {...}}
          {"version": 1, "id": "...", "ok": false,
           "error": {"code": "...", "message": "...", "detail": "..."}}
"""

from __future__ import annotations

import itertools
import json
import os
import queue
import socket
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Any

from cmm.computer.errors import ComputerUseError

__all__ = [
    "BRIDGE_BUNDLE_ID",
    "BRIDGE_PROTOCOL_VERSION",
    "BRIDGE_SOCKET_PATH",
    "BridgeClient",
    "BridgeUnavailable",
    "default_bridge_executable",
    "default_bridge_socket",
]

#: Protocol version this client speaks. The helper rejects anything else.
BRIDGE_PROTOCOL_VERSION = 1

#: The bundle identity the helper must report. A binary that answers the
#: protocol but is not OUR signed helper is not the product path.
BRIDGE_BUNDLE_ID = "com.cmm.chat.computer-use"

#: Requests are control plane (never media): anything larger is rejected.
REQUEST_BYTES_MAX = 1_048_576

#: Responses may carry one PNG screenshot as base64; this still bounds them.
RESPONSE_BYTES_MAX = 32_000_000

#: Per-operation timeouts (seconds). Observation and execution can wait on
#: the window server; nothing waits forever.
OPERATION_TIMEOUTS = {
    "bridge.ping": 10.0,
    "permissions.status": 10.0,
    "permissions.request_accessibility": 15.0,
    "permissions.request_screen_recording": 15.0,
    "observation.describe": 20.0,
    "observation.capture_screen": 30.0,
    "action.execute": 60.0,
}
DEFAULT_TIMEOUT = 20.0


class BridgeUnavailable(ComputerUseError):
    """The native helper could not be reached or did not answer truthfully."""

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(
            message, code="COMPUTER_RUNTIME_UNAVAILABLE", detail=detail
        )


#: Where the app-served helper listens. The CMMChat app launches the helper
#: with ``--serve-socket`` on this path; the Hub only ever connects.
#: ``CMM_COMPUTER_BRIDGE_SOCKET`` overrides it (tests, nonstandard setups).
#: The directory must be user-private (0700); the socket itself is
#: same-user-only by filesystem permissions — no TCP, no network.
BRIDGE_SOCKET_PATH = str(
    Path.home() / ".cmm" / "computer-bridge" / "bridge.sock"
)

#: How long a socket connect may take (the app owns serving; if nobody
#: listens, the capability is unavailable — never waited on forever).
SOCKET_CONNECT_TIMEOUT = 5.0


def default_bridge_socket() -> str:
    """Rendezvous path of the app-served product helper."""

    return os.environ.get("CMM_COMPUTER_BRIDGE_SOCKET") or BRIDGE_SOCKET_PATH


def default_bridge_executable() -> str:
    """Where the product helper lives.

    ``CMM_COMPUTER_BRIDGE_APP`` overrides the .app bundle location (tests,
    nonstandard installs); by default the helper installed by
    ``tools/build-computer-bridge.sh`` into the user's Applications folder.
    """

    app = os.environ.get("CMM_COMPUTER_BRIDGE_APP") or str(
        Path.home() / "Applications" / "CMMComputerUse.app"
    )
    return str(Path(app) / "Contents" / "MacOS" / "CMMComputerUse")


class _StdioTransport:
    """A locally spawned helper child (stdio pipes). Development/tests."""

    def __init__(self, argv: list[str]) -> None:
        self._argv = argv
        self._proc: subprocess.Popen[bytes] | None = None

    @property
    def kind(self) -> str:
        return "stdio"

    @property
    def alive(self) -> bool:
        proc = self._proc
        return proc is not None and proc.poll() is None

    def start(self) -> tuple[Any, Any, Any | None]:
        """Spawn; return ``(stdout, stdin, stderr)`` binary streams."""

        try:
            proc = subprocess.Popen(
                self._argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (OSError, ValueError) as error:
            raise BridgeUnavailable(
                "The computer bridge helper is not installed.",
                detail=type(error).__name__,
            ) from error
        self._proc = proc
        assert proc.stdout is not None and proc.stdin is not None
        return (proc.stdout, proc.stdin, proc.stderr)

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:  # noqa: BLE001 - teardown never raises
            pass
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except Exception:  # noqa: BLE001 - teardown never raises
                pass


class _SocketTransport:
    """The app-served helper over its Unix-socket rendezvous. Product."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._sock: socket.socket | None = None

    @property
    def kind(self) -> str:
        return "socket"

    @property
    def path(self) -> str:
        return self._path

    @property
    def alive(self) -> bool:
        return self._sock is not None

    def start(self) -> tuple[Any, Any, None]:
        """Connect; return ``(rfile, wfile, None)`` binary streams."""

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(SOCKET_CONNECT_TIMEOUT)
            sock.connect(self._path)
            sock.settimeout(None)
        except (OSError, ValueError) as error:
            try:
                sock.close()
            except Exception:  # noqa: BLE001 - teardown never raises
                pass
            raise BridgeUnavailable(
                "The computer bridge is not serving (is the Mac app running?).",
                detail=type(error).__name__,
            ) from error
        self._sock = sock
        # One buffered reader plus unbuffered writes on the same socket.
        return (sock.makefile("rb"), sock.makefile("wb"), None)

    def stop(self) -> None:
        sock, self._sock = self._sock, None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:  # noqa: BLE001 - teardown never raises
            pass
        try:
            sock.close()
        except Exception:  # noqa: BLE001 - teardown never raises
            pass


class BridgeClient:
    """One supervised helper connection speaking protocol v1.

    A single in-flight request at a time (guarded by a lock): responses are
    matched by id; a timeout or broken connection drops the transport so a
    late answer can never be mistaken for the next request's, and the next
    request reconnects (socket) or relaunches (stdio child).
    """

    def __init__(
        self,
        executable: str | list[str] | None = None,
        *,
        timeout: float | None = None,
        transport: Any | None = None,
        socket_path: str | None = None,
    ) -> None:
        if transport is not None:
            self._transport = transport
        elif isinstance(executable, list):
            # A list argv exists for tests driving scripted fake helpers
            # over real pipes.
            self._transport = _StdioTransport(list(executable))
        elif os.environ.get("CMM_COMPUTER_BRIDGE_DIRECT") == "1":
            # Explicit development mode: spawn the helper as our own child.
            # Never the product path (unusable TCC ancestry — see module doc).
            resolved = executable or default_bridge_executable()
            argv = [resolved] if isinstance(resolved, str) else list(resolved)
            self._transport = _StdioTransport(argv)
        else:
            # Product: the Mac app serves the helper on its socket.
            self._transport = _SocketTransport(
                socket_path or default_bridge_socket()
            )
        self._timeout_override = timeout
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._read_stream: Any | None = None
        self._write_stream: Any | None = None
        self._reader: threading.Thread | None = None
        self._responses: queue.Queue[str] = queue.Queue()
        self._stderr_lines: deque[str] = deque(maxlen=50)
        self._closed = False

    # ── lifecycle ─────────────────────────────────────────────────────

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._terminate_locked()

    @property
    def alive(self) -> bool:
        return self._transport.alive

    @property
    def transport_kind(self) -> str:
        """``socket`` (product) or ``stdio`` (direct/tests)."""

        return self._transport.kind

    def _terminate_locked(self) -> None:
        self._read_stream = None
        self._write_stream = None
        try:
            self._transport.stop()
        except Exception:  # noqa: BLE001 - teardown never raises
            pass

    def _ensure_running_locked(self) -> None:
        if self._closed:
            raise BridgeUnavailable("The computer bridge is closed.")
        if self.alive:
            return
        self._terminate_locked()
        self._responses = queue.Queue()
        read_stream, write_stream, err_stream = self._transport.start()
        self._read_stream = read_stream
        self._write_stream = write_stream
        reader = threading.Thread(
            target=self._read_loop, args=(read_stream,),
            name="cmm-bridge-reader", daemon=True,
        )
        self._reader = reader
        reader.start()
        if err_stream is not None:
            drainer = threading.Thread(
                target=self._drain_stderr, args=(err_stream,),
                name="cmm-bridge-stderr", daemon=True,
            )
            drainer.start()

    def _read_loop(self, read_stream: Any) -> None:
        try:
            while True:
                line = read_stream.readline()
                if not line:
                    break
                if len(line) > RESPONSE_BYTES_MAX:
                    continue  # oversized frame is dropped, never trusted
                try:
                    self._responses.put(line.decode("utf-8"))
                except UnicodeDecodeError:
                    continue
        except Exception:  # noqa: BLE001 - a dead reader just stops
            pass

    def _drain_stderr(self, err_stream: Any) -> None:
        try:
            for raw in err_stream:
                try:
                    self._stderr_lines.append(
                        raw.decode("utf-8", "replace").rstrip()[-500:]
                    )
                except Exception:  # noqa: BLE001 - diagnostics never break us
                    pass
        except Exception:  # noqa: BLE001 - a dead drainer just stops
            pass

    # ── request/response ──────────────────────────────────────────────

    def ping(self, *, timeout: float | None = None) -> dict[str, Any]:
        """Prove the server is OUR helper: protocol, bridge name, bundle id."""

        result = self.request("bridge.ping", {}, timeout=timeout)
        if (
            not isinstance(result, dict)
            or result.get("bridge") != "cmm-computer-use"
            or result.get("protocol") != BRIDGE_PROTOCOL_VERSION
        ):
            raise BridgeUnavailable(
                "The computer bridge answered, but not as the product helper."
            )
        bundle = result.get("bundle_id", "")
        if bundle != BRIDGE_BUNDLE_ID:
            raise BridgeUnavailable(
                "The computer bridge has an unexpected application identity.",
                detail=str(bundle)[:120],
            )
        return result

    def request(
        self,
        operation: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        """Send one versioned request; return ``result`` or raise."""

        if not operation or not isinstance(operation, str):
            raise BridgeUnavailable("Refusing to send an unnamed operation.")
        payload = {
            "version": BRIDGE_PROTOCOL_VERSION,
            "id": f"py-{next(self._ids)}",
            "operation": operation,
            "arguments": dict(arguments or {}),
        }
        try:
            line = (json.dumps(payload) + "\n").encode("utf-8")
        except (TypeError, ValueError) as error:
            raise BridgeUnavailable(
                "Refusing to send an unencodable request.",
                detail=type(error).__name__,
            ) from error
        if len(line) > REQUEST_BYTES_MAX:
            raise BridgeUnavailable(
                "Refusing to send a request beyond the bounded size."
            )
        limit = (
            self._timeout_override
            if timeout is None and self._timeout_override is not None
            else (timeout or OPERATION_TIMEOUTS.get(operation, DEFAULT_TIMEOUT))
        )
        with self._lock:
            self._ensure_running_locked()
            write_stream = self._write_stream
            assert write_stream is not None
            try:
                write_stream.write(line)
                write_stream.flush()
            except (BrokenPipeError, OSError) as error:
                self._terminate_locked()
                raise BridgeUnavailable(
                    "The computer bridge closed its request channel.",
                    detail=type(error).__name__,
                ) from error
            try:
                raw = self._responses.get(timeout=limit)
            except queue.Empty as error:
                # A late answer must never surface as a later request's
                # response: the child dies here and the next request starts
                # a fresh one.
                self._terminate_locked()
                raise BridgeUnavailable(
                    f"The computer bridge did not answer {operation} in time.",
                    detail=f"{limit:g}s",
                ) from error
        return self._decode_response(payload["id"], operation, raw)

    def _decode_response(
        self, request_id: str, operation: str, raw: str
    ) -> Any:
        try:
            frame = json.loads(raw)
        except (ValueError, TypeError) as error:
            self._kill_after_protocol_violation()
            raise BridgeUnavailable(
                "The computer bridge answered with malformed JSON.",
                detail=type(error).__name__,
            ) from error
        if not isinstance(frame, dict):
            self._kill_after_protocol_violation()
            raise BridgeUnavailable(
                "The computer bridge answered outside the protocol."
            )
        if frame.get("version") != BRIDGE_PROTOCOL_VERSION:
            self._kill_after_protocol_violation()
            raise BridgeUnavailable(
                "The computer bridge answered with the wrong protocol version."
            )
        if frame.get("id") != request_id:
            self._kill_after_protocol_violation()
            raise BridgeUnavailable(
                "The computer bridge answered for a different request."
            )
        if frame.get("ok") is True:
            return frame.get("result")
        error = frame.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        message = error.get("message") if isinstance(error, dict) else None
        detail = error.get("detail") if isinstance(error, dict) else ""
        raise ComputerUseError(
            str(message or f"The computer bridge refused {operation}."),
            code=str(code) if code in _BRIDGE_ERROR_CODES else "ACTION_FAILED",
            detail=str(detail or "")[:500],
        )

    def _kill_after_protocol_violation(self) -> None:
        with self._lock:
            self._terminate_locked()

    @property
    def recent_diagnostics(self) -> list[str]:
        """Helper stderr tail for humans; never contains secrets by design."""

        return list(self._stderr_lines)


#: Bridge error codes are already the frozen product grammar; anything else
#: is carried as a generic action failure, never invented here.
_BRIDGE_ERROR_CODES = frozenset(
    {
        "COMPUTER_RUNTIME_UNAVAILABLE",
        "COMPUTER_PERMISSION_DENIED",
        "COMPUTER_TARGET_UNAVAILABLE",
        "ACTION_FAILED",
        "APPROVAL_REJECTED",
        "CAPABILITY_UNSUPPORTED",
        "CANCELLED",
    }
)
