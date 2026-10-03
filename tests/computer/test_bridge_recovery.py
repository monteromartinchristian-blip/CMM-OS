"""Recoverable bridge failures rejoin the loop; fatal ones still terminate.

Regression coverage for the production bridge transport defect: every
ok:false used to raise straight out of ComputerUseService.run_task, so one
refused native action killed the whole run and the planner never adapted.
Now ACTION_FAILED and COMPUTER_TARGET_UNAVAILABLE return as failed action
results (planner feedback, next step allowed) while approval rejections,
permission loss, runtime death and protocol violations still raise.
"""

from __future__ import annotations

import json

import pytest

from cmm.computer.bridge import BridgeUnavailable
from cmm.computer.contracts import (
    Action,
    ActionResult,
    Observation,
    PermissionState,
    WindowInfo,
)
from cmm.computer.errors import ComputerUseError
from cmm.computer.loop import ComputerUseService
from cmm.computer.runtime_bridge import BridgeComputerRuntime


def make_observation(app="Finder") -> Observation:
    return Observation(
        frontmost_app=app,
        frontmost_bundle="com.test.finder",
        windows=(
            WindowInfo(title="probe", app=app, x=0, y=0, width=800, height=600),
        ),
        elements=(),
    )


class ScriptedClient:
    """A BridgeClient double scripted per operation name."""

    def __init__(self, script):
        # script: dict operation -> list of ("raise", error) | ("return", value)
        self.script = {op: list(steps) for op, steps in script.items()}
        self.calls: list[tuple[str, dict]] = []

    def ping(self):
        self.calls.append(("bridge.ping", {}))
        return self._next("bridge.ping", {"bridge": "test", "protocol": 1})

    def request(self, operation, arguments=None):
        self.calls.append((operation, arguments or {}))
        return self._next(operation, {})

    def _next(self, operation, default):
        steps = self.script.get(operation, [])
        if not steps:
            return default
        kind, value = steps.pop(0)
        if kind == "raise":
            raise value
        return value

    def close(self):
        pass


class ScriptedPlan:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def __call__(self, prompt, system, cancel_event=None):
        self.prompts.append(prompt)
        if self.replies:
            return self.replies.pop(0)
        return json.dumps({"action": "finish", "summary": "script exhausted"})


def unaffected_permissions() -> PermissionState:
    return PermissionState(True, True, "")


def run_service(runtime, replies):
    service = ComputerUseService(
        runtime=runtime, plan=ScriptedPlan(replies), approval_gate=None
    )
    return service


# 1. window.focus on a missing target: recoverable, planner sees it, loop lives.
def test_focus_missing_target_returns_to_planner():
    client = ScriptedClient(
        {
            "permissions.status": [
                ("return", {"accessibility": True, "screen_recording": True, "detail": ""}),
            ],
            "observation.describe": [
                ("return", {
                    "frontmost_app": "Finder", "frontmost_bundle": "com.test.finder",
                    "windows": [], "elements": [], "screenshot_base64": None,
                    "captured_at": 0.0,
                }),
            ],
            "action.execute": [
                ("raise", ComputerUseError(
                    "window not found: CMMChat-E2E-Probe", code="ACTION_FAILED")),
            ],
        }
    )
    runtime = BridgeComputerRuntime(client=client)
    service = run_service(
        runtime,
        [
            json.dumps({"action": "window.focus", "title": "CMMChat-E2E-Probe"}),
            json.dumps({"action": "finish", "summary": "window is not there"}),
        ],
    )
    outcome = service.run_task("count the probe window items")
    assert outcome.summary == "window is not there"
    # The failure reached the NEXT planning step instead of killing the run.
    assert len(service._plan.prompts) == 2
    assert "window not found" in service._plan.prompts[1]
    assert "ACTION_FAILED" in service._plan.prompts[1]


# 2. app.activate transient refusal: recoverable, next step allowed.
def test_activate_refusal_allows_next_step():
    client = ScriptedClient(
        {
            "permissions.status": [
                ("return", {"accessibility": True, "screen_recording": True, "detail": ""}),
            ],
            "observation.describe": [
                ("return", {
                    "frontmost_app": "TextEdit", "frontmost_bundle": "com.test.textedit",
                    "windows": [], "elements": [], "screenshot_base64": None,
                    "captured_at": 0.0,
                }),
            ],
            "action.execute": [
                ("raise", ComputerUseError(
                    "activation did not bring Finder to the front",
                    code="ACTION_FAILED")),
            ],
        }
    )
    runtime = BridgeComputerRuntime(client=client)
    service = run_service(
        runtime,
        [
            json.dumps({"action": "app.activate", "app": "Finder"}),
            json.dumps({"action": "finish", "summary": "activation refused, stopping"}),
        ],
    )
    outcome = service.run_task("bring Finder forward")
    assert outcome.summary == "activation refused, stopping"
    assert len(service._plan.prompts) == 2
    assert "activation did not bring Finder" in service._plan.prompts[1]


# Recoverable codes convert at the runtime seam (code + safe detail kept).
def test_target_unavailable_converts_to_failed_result():
    client = ScriptedClient({})
    runtime = BridgeComputerRuntime(client=client)
    client.script["action.execute"] = [
        ("raise", ComputerUseError("application not found: Nope", code="COMPUTER_TARGET_UNAVAILABLE")),
    ]
    result = runtime.execute(Action(kind="app.open", params={"app": "Nope"}))
    assert isinstance(result, ActionResult)
    assert result.ok is False
    assert "COMPUTER_TARGET_UNAVAILABLE" in result.detail


# 3. Helper unavailable stays fatal and truthful.
def test_helper_unavailable_raises():
    client = ScriptedClient(
        {"action.execute": [("raise", BridgeUnavailable("socket gone"))]}
    )
    runtime = BridgeComputerRuntime(client=client)
    with pytest.raises(BridgeUnavailable):
        runtime.execute(Action(kind="window.focus", params={"title": "x"}))


def test_helper_unavailable_kills_loop_truthfully():
    client = ScriptedClient(
        {
            "permissions.status": [
                ("return", {"accessibility": True, "screen_recording": True, "detail": ""}),
            ],
            "observation.describe": [
                ("return", {
                    "frontmost_app": "Finder", "frontmost_bundle": "com.test.finder",
                    "windows": [], "elements": [], "screenshot_base64": None,
                    "captured_at": 0.0,
                }),
            ],
            "action.execute": [("raise", BridgeUnavailable("socket gone"))],
        }
    )
    runtime = BridgeComputerRuntime(client=client)
    service = run_service(
        runtime, [json.dumps({"action": "window.focus", "title": "x"})]
    )
    with pytest.raises(BridgeUnavailable):
        service.run_task("focus x")


# 4. Malformed helper responses stay fatal, never planned around.
def test_malformed_response_raises():
    client = ScriptedClient({"action.execute": [("return", "not-a-dict")]})
    runtime = BridgeComputerRuntime(client=client)
    with pytest.raises(BridgeUnavailable):
        runtime.execute(Action(kind="wait", params={"seconds": 1}))


# 5. Approval rejection stands: raised, never converted to a retryable failure.
def test_approval_rejection_raises_not_converted():
    client = ScriptedClient(
        {
            "action.execute": [
                ("raise", ComputerUseError("user rejected", code="APPROVAL_REJECTED")),
            ]
        }
    )
    runtime = BridgeComputerRuntime(client=client)
    with pytest.raises(ComputerUseError) as caught:
        runtime.execute(Action(kind="pointer.click", params={"x": 1, "y": 2}))
    assert caught.value.code == "APPROVAL_REJECTED"


def test_permission_loss_raises():
    client = ScriptedClient(
        {
            "action.execute": [
                ("raise", ComputerUseError("grant revoked", code="COMPUTER_PERMISSION_DENIED")),
            ]
        }
    )
    runtime = BridgeComputerRuntime(client=client)
    with pytest.raises(ComputerUseError) as caught:
        runtime.execute(Action(kind="window.focus", params={"title": "x"}))
    assert caught.value.code == "COMPUTER_PERMISSION_DENIED"


# 6. Supervised restart window: bounded wait rejoins, absence still fails.
# Production: the app supervisor relaunches the helper (relaunch beat +
# socket rebind); a run whose first ping lands in that window died with
# COMPUTER_RUNTIME_UNAVAILABLE before reaching the model. wait_until_ready
# tolerates seconds-long restarts; a genuinely absent helper still fails
# honestly after the bound.
def test_wait_until_ready_rejoins_restart():
    client = ScriptedClient(
        {
            "bridge.ping": [
                ("raise", BridgeUnavailable("socket gone")),
                ("raise", BridgeUnavailable("socket gone")),
                ("return", {"bridge": "x", "protocol": 1}),
            ],
        }
    )
    runtime = BridgeComputerRuntime(client=client)
    assert runtime.wait_until_ready(timeout=5.0, interval=0.01) is True
    assert [op for op, _ in client.calls].count("bridge.ping") == 3


class AlwaysDownClient(ScriptedClient):
    """ScriptedClient answers success once a script runs dry; downtime does not."""

    def ping(self):
        self.calls.append(("bridge.ping", {}))
        raise BridgeUnavailable("nobody home")


def test_wait_until_ready_absent_stays_false():
    runtime = BridgeComputerRuntime(client=AlwaysDownClient({}))
    assert runtime.wait_until_ready(timeout=0.05, interval=0.01) is False


def test_wait_until_ready_cancelled_aborts():
    import threading

    cancelled = threading.Event()
    cancelled.set()
    down = BridgeComputerRuntime(client=AlwaysDownClient({}))
    assert down.wait_until_ready(timeout=5.0, interval=0.01, cancel_event=cancelled) is False
    assert len(down._client.calls) == 1


def test_run_task_survives_restart_window():
    client = ScriptedClient(
        {
            "bridge.ping": [
                ("raise", BridgeUnavailable("relaunch beat")),
                ("raise", BridgeUnavailable("relaunch beat")),
                ("return", {"bridge": "x", "protocol": 1}),
            ],
            "permissions.status": [
                ("return", {"accessibility": True, "screen_recording": True, "detail": ""}),
            ],
            "observation.describe": [
                ("return", {
                    "frontmost_app": "Finder", "frontmost_bundle": "com.test.finder",
                    "windows": [], "elements": [], "screenshot_base64": None,
                    "captured_at": 0.0,
                }),
            ],
        }
    )
    runtime = BridgeComputerRuntime(client=client)
    service = run_service(
        runtime, [json.dumps({"action": "finish", "summary": "rejoined after restart"})]
    )
    outcome = service.run_task("count the probe window items")
    assert outcome.summary == "rejoined after restart"


def test_run_task_absent_helper_still_fails_truthfully():
    import threading

    runtime = BridgeComputerRuntime(client=AlwaysDownClient({}))
    service = run_service(runtime, [])
    # Pre-cancelled so the bounded wait aborts on its first probe instead
    # of sleeping through the whole product bound; the timeout path is
    # pinned by test_wait_until_ready_absent_stays_false.
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(ComputerUseError) as caught:
        service.run_task("do a thing", cancel_event=cancelled)
    assert caught.value.code == "COMPUTER_RUNTIME_UNAVAILABLE"


def test_run_task_no_waiter_fails_immediately():
    class BareRuntime:
        def available(self):
            return False

    service = run_service(BareRuntime(), [])
    with pytest.raises(ComputerUseError) as caught:
        service.run_task("do a thing")
    assert caught.value.code == "COMPUTER_RUNTIME_UNAVAILABLE"
