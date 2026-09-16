"""Phase 11.2 — deterministic intent resolver tests.

The baseline Phase 11.2 resolver is deterministic and makes no external model
call.  These tests freeze its precedence order, its ambiguity behaviour and its
structural purity.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cmm.orchestration.contracts import (
    IntentKind,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationRequest,
)
from cmm.orchestration.intent import (
    DeterministicIntentResolver,
    IntentResolver,
)

INTENT_MODULE = (
    Path(__file__).resolve().parents[2] / "cmm" / "orchestration" / "intent.py"
)

FORBIDDEN_INTENT_IMPORT_ROOTS = (
    "kernel.llm",
    "openai",
    "anthropic",
    "requests",
    "httpx",
)

FORBIDDEN_INTENT_NAME_TOKENS = (
    "ModelGateway",
    "ModelRouter",
    "ProviderRegistry",
    "completion",
    "chat",
)


def _resolve(input_payload: dict[str, object], **overrides: object) -> IntentResolution:
    request = OrchestrationRequest(
        request_id="request-1",
        user_id="user-1",
        channel=OrchestrationChannel.CONVERSATION,
        input=input_payload,
        **overrides,  # type: ignore[arg-type]
    )
    return DeterministicIntentResolver().resolve(request)


def _kind(input_payload: dict[str, object], **overrides: object) -> IntentKind:
    return _resolve(input_payload, **overrides).intent


def test_resolver_satisfies_the_intent_resolver_protocol() -> None:
    assert isinstance(DeterministicIntentResolver(), IntentResolver)


def test_resolver_requires_an_orchestration_request() -> None:
    with pytest.raises(TypeError):
        DeterministicIntentResolver().resolve(object())  # type: ignore[arg-type]


# ── Explicit hint ────────────────────────────────────────────────────────────


def test_explicit_goal_hint_is_honoured_with_its_structured_shape() -> None:
    resolution = _resolve(
        {"goal": {"title": "Complete task"}},
        intent_hint=IntentKind.GOAL,
    )

    assert resolution.intent is IntentKind.GOAL
    assert resolution.source_kind == "intent_hint"
    assert resolution.needs_clarification is False


def test_explicit_question_hint_is_honoured_without_a_shape() -> None:
    resolution = _resolve({"text": "anything"}, intent_hint=IntentKind.QUESTION)

    assert resolution.intent is IntentKind.QUESTION
    assert resolution.source_kind == "intent_hint"


def test_shape_bound_hint_without_its_shape_does_not_guess_a_route() -> None:
    """A hinted side-effecting intent without structured evidence fails closed."""

    resolution = _resolve({"text": "do the thing"}, intent_hint=IntentKind.COMMAND)

    assert resolution.intent is IntentKind.UNKNOWN
    assert resolution.needs_clarification is True
    assert "INTENT_HINT_SHAPE_MISSING" in resolution.reason_codes


def test_shape_bound_hint_falls_through_to_structured_evidence() -> None:
    resolution = _resolve(
        {"goal": {"title": "Complete task"}},
        intent_hint=IntentKind.COMMAND,
    )

    assert resolution.intent is IntentKind.GOAL
    assert resolution.source_kind == "structured_input"


def test_unresolved_hint_stays_fail_closed() -> None:
    resolution = _resolve(
        {"goal": {"title": "Complete task"}},
        intent_hint=IntentKind.UNKNOWN,
    )

    assert resolution.intent is IntentKind.UNKNOWN
    assert resolution.needs_clarification is True


# ── Structured precedence ────────────────────────────────────────────────────


def test_approval_response_signal() -> None:
    resolution = _resolve({"approval_id": "approval-1", "decision": "approved"})

    assert resolution.intent is IntentKind.APPROVAL_RESPONSE
    assert resolution.needs_clarification is False


def test_approval_signal_requires_a_decision() -> None:
    assert _kind({"approval_id": "approval-1"}) is IntentKind.UNKNOWN


def test_cancellation_signal() -> None:
    assert _kind({"cancel_target_id": "workflow-1"}) is IntentKind.CANCELLATION


def test_continuation_signal() -> None:
    assert _kind({"continuation_id": "workflow-1"}) is IntentKind.CONTINUATION


def test_configuration_change_signal() -> None:
    payload = {"configuration_change": {"path": "autonomy.level", "value": "low"}}

    assert _kind(payload) is IntentKind.CONFIGURATION_CHANGE


def test_information_update_signal() -> None:
    payload = {"information_update": {"subject_ref": "knowledge-1"}}

    assert _kind(payload) is IntentKind.INFORMATION_UPDATE


def test_workflow_request_signal() -> None:
    assert (
        _kind({"workflow_request": {"workflow_type": "review"}})
        is IntentKind.WORKFLOW_REQUEST
    )


def test_goal_signal() -> None:
    assert _kind({"goal": {"title": "Complete task"}}) is IntentKind.GOAL


def test_command_signal() -> None:
    payload = {"command": {"operation": "project.inspect"}}

    assert _kind(payload) is IntentKind.COMMAND


def test_question_signal() -> None:
    assert _kind({"question": "What changed?"}) is IntentKind.QUESTION


def test_reflection_signal() -> None:
    payload = {"reflection": "I want to think through this"}

    assert _kind(payload) is IntentKind.REFLECTION


@pytest.mark.parametrize(
    ("higher", "lower"),
    [
        (
            {"approval_id": "approval-1", "decision": "approved"},
            {"cancel_target_id": "workflow-1"},
        ),
        ({"cancel_target_id": "workflow-1"}, {"continuation_id": "workflow-1"}),
        (
            {"continuation_id": "workflow-1"},
            {"information_update": {"subject_ref": "knowledge-1"}},
        ),
        (
            {"information_update": {"subject_ref": "knowledge-1"}},
            {"workflow_request": {"workflow_type": "review"}},
        ),
        (
            {"workflow_request": {"workflow_type": "review"}},
            {"goal": {"title": "Complete task"}},
        ),
        ({"goal": {"title": "Complete task"}}, {"command": {"operation": "op"}}),
        ({"command": {"operation": "op"}}, {"question": "What changed?"}),
        ({"question": "What changed?"}, {"reflection": "Let me think"}),
    ],
)
def test_precedence_order_is_frozen(
    higher: dict[str, object], lower: dict[str, object]
) -> None:
    assert _kind({**lower, **higher}) is _kind(higher)
    assert _kind({**higher, **lower}) is _kind(higher)


def test_multiple_distinct_signals_are_traceable() -> None:
    resolution = _resolve({"question": "What changed?", "goal": {"title": "task"}})

    assert resolution.intent is IntentKind.GOAL
    assert "INTENT_MULTIPLE_SIGNALS" in resolution.reason_codes


# ── Fail-closed behaviour ────────────────────────────────────────────────────


def test_unstructured_input_is_unknown_and_needs_clarification() -> None:
    resolution = _resolve({"text": "something"})

    assert resolution.intent is IntentKind.UNKNOWN
    assert resolution.needs_clarification is True
    assert resolution.source_kind == "unresolved"


def test_empty_input_is_unknown() -> None:
    assert _kind({}) is IntentKind.UNKNOWN


@pytest.mark.parametrize(
    "payload",
    [
        {"command": {}},
        {"command": {"operation": "   "}},
        {"goal": {"title": ""}},
        {"workflow_request": {"workflow_type": "  "}},
        {"information_update": {}},
        {"configuration_change": {"value": "low"}},
        {"question": "   "},
        {"reflection": ""},
        {"cancel_target_id": ""},
        {"continuation_id": None},
        {"command": "operation"},
        {"goal": ("title",)},
    ],
)
def test_malformed_signals_fail_closed(payload: dict[str, object]) -> None:
    assert _kind(payload) is IntentKind.UNKNOWN


def test_only_unknown_requires_clarification() -> None:
    for payload in (
        {"question": "What changed?"},
        {"goal": {"title": "Complete task"}},
        {"command": {"operation": "op"}},
    ):
        assert _resolve(payload).needs_clarification is False


def test_resolution_is_deterministic() -> None:
    payload = {"goal": {"title": "Complete task"}}

    assert _resolve(payload).to_dict() == _resolve(payload).to_dict()


def test_resolution_carries_no_free_form_reasoning() -> None:
    resolution = _resolve({"question": "What changed?"})

    assert set(resolution.to_dict()) == {
        "intent",
        "needs_clarification",
        "source_kind",
        "reason_codes",
    }


# ── No model call ────────────────────────────────────────────────────────────


def test_intent_module_imports_no_model_or_provider_surface() -> None:
    tree = ast.parse(INTENT_MODULE.read_text())

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    offenders = [
        module
        for module in imported
        for forbidden in FORBIDDEN_INTENT_IMPORT_ROOTS
        if module == forbidden or module.startswith(f"{forbidden}.")
    ]

    assert not offenders, f"intent resolution must not depend on models: {offenders}"


def test_intent_module_never_references_a_model_or_provider_symbol() -> None:
    tree = ast.parse(INTENT_MODULE.read_text())

    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)

    offenders = sorted(
        name
        for name in referenced
        for forbidden in FORBIDDEN_INTENT_NAME_TOKENS
        if forbidden in name
    )

    assert not offenders, f"intent resolution must not reference models: {offenders}"
