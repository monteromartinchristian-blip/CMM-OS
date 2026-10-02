"""Bridge architecture regression tests: the actual boundaries, not booleans.

The product path measures Computer Use on the SIGNED HELPER process, not on
this Python interpreter. These tests drive the real NDJSON-over-pipe client
against scripted fake helpers (real subprocesses, real pipes) so framing,
timeouts, crashes, malformed frames and identity checks are exercised — plus
live-helper tests proving the installed .app answers truthfully.
"""

from __future__ import annotations

import base64
import json
import sys
import textwrap

import pytest

from cmm.computer.bridge import (
    BRIDGE_BUNDLE_ID,
    BridgeClient,
    BridgeUnavailable,
)
from cmm.computer.contracts import Action
from cmm.computer.errors import ComputerUseError
from cmm.computer.loop import ComputerUseService
from cmm.computer.runtime_bridge import BridgeComputerRuntime

TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9"
    "awAAAABJRU5ErkJggg=="
)


def _fake_helper_script(behavior: str) -> str:
    """A scripted NDJSON helper: real process, real pipes, canned behavior."""

    return textwrap.dedent(
        f"""
        import json, sys, time
        behavior = {behavior!r}
        tiny_png = {TINY_PNG_B64!r}
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                req = json.loads(raw)
            except ValueError:
                sys.stdout.write(json.dumps({{"version": 1, "id": None, "ok": False,
                    "error": {{"code": "ACTION_FAILED", "message": "bad json"}}}}) + "\\n")
                sys.stdout.flush()
                continue
            rid, op = req.get("id"), req.get("operation")
            # Identity answers on every behavior except the impostor ones:
            # availability must be decidable even when later calls fail.
            if op == "bridge.ping" and behavior not in ("wrong-identity", "wrong-version",
                                                        "sleep", "crash", "garbage"):
                sys.stdout.write(json.dumps({{"version": 1, "id": rid, "ok": True,
                    "result": {{"bridge": "cmm-computer-use", "protocol": 1,
                                "pid": 9,
                                "bundle_id": {BRIDGE_BUNDLE_ID!r}}}}}) + "\\n")
                sys.stdout.flush()
                continue
            def answer(result):
                sys.stdout.write(json.dumps({{"version": 1, "id": rid, "ok": True,
                    "result": result}}) + "\\n")
                sys.stdout.flush()
            def refuse(code, message, detail=""):
                sys.stdout.write(json.dumps({{"version": 1, "id": rid, "ok": False,
                    "error": {{"code": code, "message": message,
                               "detail": detail}}}}) + "\\n")
                sys.stdout.flush()
            if behavior == "sleep":
                time.sleep(30)
            elif behavior == "garbage":
                sys.stdout.write("this is not json\\n")
                sys.stdout.flush()
            elif behavior == "crash":
                raise SystemExit(3)
            elif behavior == "wrong-identity":
                answer({{"bridge": "cmm-computer-use", "protocol": 1, "pid": 9,
                        "bundle_id": "com.evil.impostor"}})
            elif behavior == "wrong-version":
                answer({{"bridge": "cmm-computer-use", "protocol": 999, "pid": 9,
                        "bundle_id": {BRIDGE_BUNDLE_ID!r}}})
            elif behavior == "permissions-denied":
                answer({{"accessibility": False, "screen_recording": False,
                        "detail": "Accesibilidad, Grabación de pantalla"}})
            elif behavior == "permissions-granted":
                answer({{"accessibility": True, "screen_recording": True, "detail": ""}})
            elif behavior == "screen-partial":
                answer({{"accessibility": True, "screen_recording": False,
                        "detail": "Grabación de pantalla"}})
            elif behavior == "deny-screenshot":
                refuse("COMPUTER_PERMISSION_DENIED",
                       "Screen recording permission is required.",
                       "Grabación de pantalla")
            elif behavior == "shot":
                answer({{"screenshot_base64": tiny_png}})
            elif behavior == "bad-shot":
                answer({{"screenshot_base64": "aGVsbG8gd29ybGQ="}})
            elif behavior == "fail-action":
                answer({{"ok": False, "message": "AXPress failed (1)"}})
            elif behavior == "echo":
                if op == "bridge.ping":
                    answer({{"bridge": "cmm-computer-use", "protocol": 1, "pid": 9,
                            "bundle_id": {BRIDGE_BUNDLE_ID!r}}})
                elif op == "permissions.status":
                    answer({{"accessibility": True, "screen_recording": True,
                            "detail": ""}})
                elif op == "observation.describe":
                    answer({{"frontmost_app": "Finder",
                            "frontmost_bundle": "com.apple.finder",
                            "windows": [{{"title": "Recents", "app": "Finder", "x": 0,
                                         "y": 0, "width": 800, "height": 600}}],
                            "elements": [{{"element_id": 1, "role": "AXButton",
                                          "title": "Close", "value": "", "x": 1, "y": 2,
                                          "width": 3, "height": 4, "pressable": True}}],
                            "screenshot_base64": None, "captured_at": 1.5}})
                elif op == "action.execute":
                    answer({{"ok": True, "message": "pressed"}})
                else:
                    refuse("CAPABILITY_UNSUPPORTED", f"Unknown operation: {{op}}")
            else:
                refuse("CAPABILITY_UNSUPPORTED", f"Unknown operation: {{op}}")
        """
    )


def _client(behavior: str, **kwargs) -> BridgeClient:
    return BridgeClient(
        [sys.executable, "-c", _fake_helper_script(behavior)], **kwargs
    )


def _runtime(behavior: str, **kwargs) -> BridgeComputerRuntime:
    return BridgeComputerRuntime(_client(behavior, **kwargs))


# ── discovery: bridge absent ────────────────────────────────────────────


def test_missing_helper_is_unavailable_not_granted():
    runtime = BridgeComputerRuntime(
        BridgeClient("/nonexistent/CMMComputerUse-missing")
    )
    assert runtime.available() is False
    service = ComputerUseService(runtime=runtime, plan=lambda *_: "{}")
    status = service.status()
    assert status["runtime_available"] is False
    assert status["available"] is False
    # A missing runtime must not claim permissions it never measured.
    assert status["permissions"] == {
        "accessibility": False,
        "screen_recording": False,
        "detail": "",
    }


def test_default_executable_points_at_the_product_bundle():
    from cmm.computer.bridge import default_bridge_executable

    exe = default_bridge_executable()
    assert exe.endswith("CMMComputerUse.app/Contents/MacOS/CMMComputerUse")
    assert "com.cmm.chat.computer-use" in BRIDGE_BUNDLE_ID


# ── identity: impostors are not the product path ────────────────────────


def test_wrong_bundle_id_is_unavailable():
    assert _runtime("wrong-identity").available() is False


def test_wrong_protocol_version_is_unavailable():
    assert _runtime("wrong-version").available() is False


# ── framing: malformed, oversized, unknown ──────────────────────────────


def test_garbage_frame_is_unavailable():
    client = _client("garbage")
    with pytest.raises(BridgeUnavailable):
        client.request("bridge.ping", {}, timeout=5)


def test_unknown_operation_is_rejected_with_closed_code():
    client = _client("echo")
    with pytest.raises(ComputerUseError) as caught:
        client.request("bogus.op")
    assert caught.value.code == "CAPABILITY_UNSUPPORTED"


def test_oversized_request_is_refused_before_spawn():
    client = _client("echo")
    with pytest.raises(BridgeUnavailable):
        client.request("action.execute", {"blob": "x" * 2_000_000})
    assert client.alive is False


def test_unnamed_operation_is_refused():
    client = _client("echo")
    with pytest.raises(BridgeUnavailable):
        client.request("")


# ── supervision: timeout kills, crash recovers ──────────────────────────


def test_timeout_kills_the_child():
    client = _client("sleep", timeout=0.5)
    with pytest.raises(BridgeUnavailable):
        client.request("bridge.ping")
    assert client.alive is False


def test_crash_recovers_on_next_request():
    client = _client("crash", timeout=5)
    with pytest.raises(BridgeUnavailable):
        client.request("bridge.ping", {}, timeout=2)


def test_crash_then_healthy_helper_recovers():
    dead = _client("crash", timeout=5)
    with pytest.raises(BridgeUnavailable):
        dead.request("bridge.ping", {}, timeout=2)
    assert dead.alive is False
    healthy = _client("echo")
    assert healthy.ping()["bundle_id"] == BRIDGE_BUNDLE_ID


# ── permission propagation ──────────────────────────────────────────────


def test_denied_permissions_propagate_precisely():
    runtime = _runtime("permissions-denied")
    assert runtime.available() is True
    state = runtime.permissions()
    assert (state.accessibility, state.screen_recording) == (False, False)
    status = ComputerUseService(runtime=runtime, plan=lambda *_: "{}").status()
    assert status["runtime_available"] is True
    assert status["available"] is False
    assert status["permissions"]["detail"] == "Accesibilidad, Grabación de pantalla"


def test_granted_permissions_are_available():
    runtime = _runtime("permissions-granted")
    status = ComputerUseService(runtime=runtime, plan=lambda *_: "{}").status()
    assert status["available"] is True
    assert status["permissions"] == {
        "accessibility": True,
        "screen_recording": True,
        "detail": "",
    }


def test_partial_screen_recording_still_gates_screenshots_only():
    runtime = _runtime("screen-partial")
    status = ComputerUseService(runtime=runtime, plan=lambda *_: "{}").status()
    # Parity with the frozen contract: availability follows Accessibility;
    # Screen Recording gates screenshots, not the capability.
    assert status["available"] is True
    assert status["permissions"]["screen_recording"] is False


def test_screenshot_denied_maps_to_permission_code():
    runtime = _runtime("deny-screenshot")
    with pytest.raises(ComputerUseError) as caught:
        runtime.capture_screenshot()
    assert caught.value.code == "COMPUTER_PERMISSION_DENIED"


def test_non_png_screenshot_is_refused():
    runtime = _runtime("bad-shot")
    with pytest.raises(BridgeUnavailable):
        runtime.capture_screenshot()


# ── observation / execution mapping ─────────────────────────────────────


def test_observation_maps_onto_frozen_contracts():
    runtime = _runtime("echo")
    observation = runtime.observe()
    assert observation.frontmost_app == "Finder"
    assert observation.frontmost_bundle == "com.apple.finder"
    assert len(observation.windows) == 1
    assert observation.windows[0].title == "Recents"
    assert len(observation.elements) == 1
    element = observation.elements[0]
    assert (element.element_id, element.role, element.pressable) == (1, "AXButton", True)
    assert "Finder" in observation.render()


def test_execute_maps_ok_and_soft_failure():
    runtime = _runtime("echo")
    result = runtime.execute(Action(kind="wait", params={"seconds": 0.1}))
    assert result.ok is True

    failing = _runtime("fail-action")
    soft = failing.execute(Action(kind="ui.press", params={"element_id": 1}))
    assert soft.ok is False
    assert "AXPress" in soft.detail


def test_unknown_action_kind_rejected_before_ipc():
    runtime = _runtime("echo")
    with pytest.raises(ValueError):
        runtime.execute(Action(kind="nope", params={}))


# ── status derives from bridge truth ────────────────────────────────────


def test_service_status_derives_from_bridge_not_interpreter():
    for behavior, expect_available in (
        ("permissions-granted", True),
        ("permissions-denied", False),
    ):
        runtime = _runtime(behavior)
        status = ComputerUseService(
            runtime=runtime, plan=lambda *_: "{}"
        ).status()
        assert status["available"] is expect_available
        runtime.close()


# ── live helper (darwin + installed .app) ───────────────────────────────


def _live_runtime() -> BridgeComputerRuntime:
    return BridgeComputerRuntime()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS helper")
def test_live_helper_ping_reports_product_identity():
    import os as _os

    if not _os.path.exists(
        "/Users/chris/Applications/CMMComputerUse.app/Contents/MacOS/CMMComputerUse"
    ) and "CMM_COMPUTER_BRIDGE_APP" not in _os.environ:
        pytest.skip("helper .app not installed")
    runtime = _live_runtime()
    assert runtime.available() is True
    try:
        status = ComputerUseService(
            runtime=runtime, plan=lambda *_: "{}"
        ).status()
        assert status["runtime_available"] is True
        assert set(status["permissions"]) == {
            "accessibility",
            "screen_recording",
            "detail",
        }
    finally:
        runtime.close()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS helper")
def test_live_helper_observes_the_real_desktop():
    import os as _os

    exe = _os.environ.get(
        "CMM_COMPUTER_BRIDGE_APP",
        "/Users/chris/Applications/CMMComputerUse.app",
    )
    if not _os.path.exists(exe):
        pytest.skip("helper .app not installed")
    runtime = BridgeComputerRuntime()
    try:
        assert runtime.available() is True
        observation = runtime.observe()
        assert observation.frontmost_app, "a real frontmost app is expected"
        assert len(observation.windows) >= 1, "real windows are expected"
    finally:
        runtime.close()
