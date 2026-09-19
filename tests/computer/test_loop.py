"""Loop, policy and permission behavior of the Computer Use capability."""

from __future__ import annotations

import json
import sys
from threading import Event

import pytest

from cmm.computer.contracts import (
    Action,
    ActionResult,
    ComputerUseLimits,
    ElementInfo,
    Observation,
    PermissionState,
    WindowInfo,
)
from cmm.computer.errors import ComputerUseError
from cmm.computer.loop import ComputerUseService
from cmm.computer.policy import classify_action


def make_observation(app="TextEdit", elements=()) -> Observation:
    return Observation(
        frontmost_app=app,
        frontmost_bundle=f"com.test.{app.lower()}",
        windows=(WindowInfo(title=f"{app} window", app=app, x=0, y=0, width=800, height=600),),
        elements=tuple(elements),
    )


class FakeRuntime:
    def __init__(self, observations=None, permissions=None):
        self.observations = list(observations or [make_observation()])
        self.permissions_state = permissions or PermissionState(True, True)
        self.executed: list[Action] = []
        self.observe_calls = 0
        self.fail_next: str | None = None

    def available(self) -> bool:
        return True

    def permissions(self) -> PermissionState:
        return self.permissions_state

    def observe(self, **_) -> Observation:
        self.observe_calls += 1
        index = min(self.observe_calls - 1, len(self.observations) - 1)
        return self.observations[index]

    def execute(self, action, observation=None) -> ActionResult:
        self.executed.append(action)
        if self.fail_next == action.kind:
            return ActionResult(False, "element vanished")
        return ActionResult(True, "ok")


class ScriptedPlan:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt, system, cancel_event=None):
        self.prompts.append(prompt)
        return self.replies.pop(0) if self.replies else json.dumps(
            {"action": "finish", "summary": "script exhausted"}
        )


class RecordingGate:
    def __init__(self, decision="allow_once"):
        self.decision = decision
        self.proposals = []

    def request(self, proposal):
        self.proposals.append(proposal)
        return self.decision


def collect_emit():
    events = []
    return events, (lambda kind, data: events.append((kind, data)))


def test_multi_step_task_runs_and_finishes():
    events, emit = collect_emit()
    runtime = FakeRuntime()
    plan = ScriptedPlan(
        [
            json.dumps({"action": "app.open", "app": "TextEdit"}),
            json.dumps({"action": "keyboard.type", "text": "Hola CMM"}),
            json.dumps({"action": "finish", "summary": "Documento creado"}),
        ]
    )
    service = ComputerUseService(runtime=runtime, plan=plan, emit=emit)
    outcome = service.run_task("Crea un documento con Hola CMM")
    assert outcome.summary == "Documento creado"
    assert outcome.steps == 3
    assert [action.kind for action in runtime.executed] == ["app.open", "keyboard.type"]
    kinds = [kind for kind, _ in events]
    assert kinds[0] == "tool.requested" and kinds[1] == "tool.started"
    assert kinds.count("computer.observation") == 3
    assert kinds.count("tool.progress") == 2
    assert kinds[-1] == "tool.completed"


def test_sensitive_action_requires_approval_and_allow_once_executes_it():
    events, emit = collect_emit()
    runtime = FakeRuntime(observations=[make_observation(app="Mail")])
    gate = RecordingGate("allow_once")
    plan = ScriptedPlan(
        [
            json.dumps({"action": "keyboard.type", "text": "mensaje"}),
            json.dumps({"action": "finish", "summary": "texto escrito"}),
        ]
    )
    service = ComputerUseService(runtime=runtime, plan=plan, approval_gate=gate, emit=emit)
    outcome = service.run_task("Escribe un borrador")
    assert outcome.approvals == 1
    assert [action.kind for action in runtime.executed] == ["keyboard.type"]
    proposal = gate.proposals[0]
    assert proposal.app == "Mail" and proposal.reason and proposal.consequence
    kinds = [kind for kind, _ in events]
    assert "approval.requested" in kinds and "approval.resolved" in kinds


def test_rejected_action_is_never_executed_and_feeds_the_planner():
    runtime = FakeRuntime(observations=[make_observation(app="Mail")])
    gate = RecordingGate("reject")
    events, emit = collect_emit()
    plan = ScriptedPlan(
        [
            json.dumps({"action": "keyboard.type", "text": "mensaje"}),
            json.dumps({"action": "finish", "summary": "cancelado por el usuario"}),
        ]
    )
    service = ComputerUseService(runtime=runtime, plan=plan, approval_gate=gate, emit=emit)
    outcome = service.run_task("Escribe y envía")
    assert runtime.executed == []
    assert outcome.rejections == 1
    assert "REJECTED" in plan.prompts[1]
    resolved = [data for kind, data in events if kind == "approval.resolved"]
    assert resolved[0]["decision"] == "reject"


def test_missing_gate_denies_by_default():
    runtime = FakeRuntime(observations=[make_observation(app="Mail")])
    plan = ScriptedPlan(
        [
            json.dumps({"action": "keyboard.type", "text": "x"}),
            json.dumps({"action": "finish", "summary": "sin aprobador"}),
        ]
    )
    service = ComputerUseService(runtime=runtime, plan=plan)
    outcome = service.run_task("tarea")
    assert runtime.executed == [] and outcome.rejections == 1


def test_cancellation_prevents_the_next_action():
    events, emit = collect_emit()
    runtime = FakeRuntime()
    cancel = Event()

    def cancelling_plan(prompt, system, cancel_event=None):
        cancel.set()
        return json.dumps({"action": "finish", "summary": "no debe ejecutarse"})

    service = ComputerUseService(runtime=runtime, plan=cancelling_plan, emit=emit)
    with pytest.raises(ComputerUseError) as info:
        service.run_task("tarea larga", cancel_event=cancel)
    assert info.value.code == "CANCELLED"
    assert runtime.executed == []
    assert any(kind == "tool.cancelled" for kind, _ in events)


def test_missing_permissions_fail_before_any_observation():
    runtime = FakeRuntime(permissions=PermissionState(False, False, detail="Accesibilidad"))
    service = ComputerUseService(runtime=runtime, plan=ScriptedPlan([]))
    with pytest.raises(ComputerUseError) as info:
        service.run_task("tarea")
    assert info.value.code == "COMPUTER_PERMISSION_DENIED"
    assert runtime.observe_calls == 0
    status = service.status()
    assert status["available"] is False
    assert status["permissions"]["accessibility"] is False


def test_unavailable_runtime_is_normalized():
    class NoRuntime:
        def available(self):
            return False

    service = ComputerUseService(runtime=NoRuntime(), plan=ScriptedPlan([]))
    with pytest.raises(ComputerUseError) as info:
        service.run_task("tarea")
    assert info.value.code == "COMPUTER_RUNTIME_UNAVAILABLE"
    assert service.status()["available"] is False


def test_unknown_actions_are_fed_back_not_executed():
    runtime = FakeRuntime()
    plan = ScriptedPlan(
        [
            json.dumps({"action": "launch.rocket"}),
            json.dumps({"action": "finish", "summary": "ok"}),
        ]
    )
    service = ComputerUseService(runtime=runtime, plan=plan)
    outcome = service.run_task("tarea")
    assert runtime.executed == []
    assert any("unknown action" in warning for warning in outcome.warnings)
    assert "Unknown action" in plan.prompts[1]


def test_failed_action_feedback_lets_the_loop_adapt():
    runtime = FakeRuntime()
    runtime.fail_next = "ui.press"
    events, emit = collect_emit()
    plan = ScriptedPlan(
        [
            json.dumps({"action": "ui.press", "element_id": 1}),
            json.dumps({"action": "finish", "summary": "adaptado"}),
        ]
    )
    service = ComputerUseService(runtime=runtime, plan=plan, emit=emit)
    outcome = service.run_task("pulsa el boton")
    assert outcome.summary == "adaptado"
    assert "action failed" in " ".join(outcome.warnings)
    assert "The action failed" in plan.prompts[1]


def test_step_budget_forces_an_honest_finish():
    runtime = FakeRuntime()
    plan = ScriptedPlan(
        [json.dumps({"action": "wait", "seconds": 0.1})] * 5
    )
    service = ComputerUseService(
        runtime=runtime, plan=plan, limits=ComputerUseLimits(max_steps=3)
    )
    outcome = service.run_task("tarea larga")
    assert outcome.steps == 3
    assert "Step budget exhausted" in outcome.summary
    assert "step budget exhausted" in outcome.warnings


# ── policy unit behavior ────────────────────────────────────────────────────


def test_policy_classifies_sensitive_targets_and_apps():
    press_send = Action(
        kind="ui.press", params={"element_id": 1}, target_description="botón"
    )
    observation = make_observation(
        app="TextEdit",
        elements=(ElementInfo(1, "AXButton", "Enviar mensaje", "", 0, 0, 10, 10, True),),
    )
    assert classify_action(press_send, observation).decision == "approval"

    safe_press = Action(kind="ui.press", params={"element_id": 1})
    safe_observation = make_observation(
        elements=(ElementInfo(1, "AXButton", "Nuevo documento", "", 0, 0, 10, 10, True),)
    )
    assert classify_action(safe_press, safe_observation).decision == "auto"

    typing_in_mail = Action(kind="keyboard.type", params={"text": "hola"})
    mail_decision = classify_action(typing_in_mail, make_observation(app="Mail"))
    assert mail_decision.decision == "approval"
    assert mail_decision.egress == "screen_content"
    assert classify_action(typing_in_mail, make_observation(app="TextEdit")).decision == "auto"

    force_quit = Action(kind="keyboard.shortcut", params={"keys": "cmd+option+esc"})
    assert classify_action(force_quit, None).decision == "approval"
    new_doc = Action(kind="keyboard.shortcut", params={"keys": "cmd+n"})
    assert classify_action(new_doc, None).decision == "auto"
    assert classify_action(Action(kind="app.open", params={"app": "Safari"}), None).decision == "auto"


@pytest.mark.skipif(
    sys.platform != "darwin", reason="real macOS runtime smoke test"
)
def test_real_macos_runtime_observes_without_acting():
    from cmm.computer.runtime_macos import MacComputerRuntime

    runtime = MacComputerRuntime()
    assert runtime.available() is True
    permissions = runtime.permissions()
    assert isinstance(permissions.accessibility, bool)
    observation = runtime.observe()
    assert observation.frontmost_app
    assert isinstance(observation.windows, tuple)
    # Observation must never execute anything: no events posted, state intact.
    assert observation.captured_at > 0
