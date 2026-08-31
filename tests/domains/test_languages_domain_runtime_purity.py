"""Adversarial tests for the Languages schedule runtime-purity oracle."""

from __future__ import annotations

import pathlib as _MODULE_SERVICE
import uuid as _UUID_MODULE

import pytest

import cmm.domains.languages.rules as languages_rules
from cmm.domains.languages.operations import plan_review_schedule_result
from tests.domains import _languages_runtime_state as runtime_state


class _HiddenCalendarClient:
    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def create_event(self, event: dict[str, str]) -> None:
        self.events.append(event)


_HIDDEN_CALENDAR_CLIENT = _HiddenCalendarClient()
_RULES_HIDDEN_CALENDAR_CLIENT = _HIDDEN_CALENDAR_CLIENT
_HIDDEN_MUTABLE_STATE: dict[str, str] = {}
_IMMUTABLE_GLOBAL_STATE: tuple[str, ...] = ()


def _hidden_client_helper() -> None:
    _HIDDEN_CALENDAR_CLIENT.create_event({"title": "Hidden review"})


def _hidden_mutable_state_helper() -> None:
    _HIDDEN_MUTABLE_STATE["title"] = "Hidden review"


def _module_service_helper() -> object:
    return _MODULE_SERVICE.Path("hidden-review")


def _effectful_builtin_helper() -> object:
    return open(__file__, encoding="utf-8")


def _effectful_import_helper() -> object:
    import pathlib

    return pathlib.Path("hidden-review")


def _root_with_forbidden_helper_dependencies() -> None:
    _hidden_client_helper()
    _hidden_mutable_state_helper()
    _module_service_helper()
    _effectful_builtin_helper()
    _effectful_import_helper()


def _tampered_plan_spaced_review(
    *,
    items: tuple[object, ...] | list[object] = (),
    active_goals: tuple[object, ...] | list[object] = (),
) -> dict[str, object]:
    _RULES_HIDDEN_CALENDAR_CLIENT.create_event({"title": "Hidden review"})
    return {"items": items, "active_goals": active_goals}


def _tampered_evaluate_learning_load(
    *,
    available_time: object = None,
    energy: object = None,
    priorities: tuple[object, ...] | list[object] = (),
    deadlines: tuple[object, ...] | list[object] = (),
    recent_load: object = None,
    review_backlog: tuple[object, ...] | list[object] = (),
) -> dict[str, object]:
    _RULES_HIDDEN_CALENDAR_CLIENT.create_event({"title": "Hidden review"})
    return {
        "available_time": available_time,
        "energy": energy,
        "priorities": priorities,
        "deadlines": deadlines,
        "recent_load": recent_load,
        "review_backlog": review_backlog,
    }


def _immutable_global_rebinding_helper() -> None:
    global _IMMUTABLE_GLOBAL_STATE

    _IMMUTABLE_GLOBAL_STATE += ("hidden-review",)


def _attribute_write_helper(target: object) -> None:
    target.calendar_modified = True


def _subscript_write_helper(target: dict[str, object]) -> None:
    target["calendar_modified"] = True


def _nonlocal_write_root() -> None:
    state: tuple[str, ...] = ()

    def mutate() -> None:
        nonlocal state
        state += ("hidden-review",)

    mutate()


def _forbidden_uuid_capability_helper() -> None:
    _UUID_MODULE.os.mkdir("hidden-review")


def test_runtime_purity_oracle_recurses_and_rejects_effectful_dependencies() -> None:
    """A client, module service, open, or import cannot hide behind a helper."""
    violations = runtime_state.find_languages_runtime_purity_violations(
        _root_with_forbidden_helper_dependencies
    )

    assert {
        (violation.kind, violation.dependency, violation.owner)
        for violation in violations
    } == {
        (
            "builtin",
            "open",
            f"{__name__}._effectful_builtin_helper",
        ),
        (
            "bytecode_write",
            "STORE_SUBSCR:<subscript>",
            f"{__name__}._hidden_mutable_state_helper",
        ),
        (
            "global_object",
            "_HIDDEN_CALENDAR_CLIENT",
            f"{__name__}._hidden_client_helper",
        ),
        (
            "global_object",
            "_HIDDEN_MUTABLE_STATE",
            f"{__name__}._hidden_mutable_state_helper",
        ),
        (
            "import",
            "pathlib",
            f"{__name__}._effectful_import_helper",
        ),
        (
            "module",
            "_MODULE_SERVICE",
            f"{__name__}._module_service_helper",
        ),
    }


@pytest.mark.parametrize(
    ("helper", "replacement"),
    (
        (languages_rules.plan_spaced_review, _tampered_plan_spaced_review),
        (
            languages_rules.evaluate_learning_load,
            _tampered_evaluate_learning_load,
        ),
    ),
    ids=("plan-spaced-review", "evaluate-learning-load"),
)
def test_exact_imported_helper_identity_is_recursively_audited(
    monkeypatch: pytest.MonkeyPatch,
    helper: object,
    replacement: object,
) -> None:
    """Swapping a trusted helper body cannot hide a rules-module client."""
    client = _HiddenCalendarClient()

    with monkeypatch.context() as patch:
        patch.setitem(
            languages_rules.__dict__,
            "_RULES_HIDDEN_CALENDAR_CLIENT",
            client,
        )
        patch.setattr(helper, "__code__", replacement.__code__)

        violations = runtime_state.find_languages_runtime_purity_violations(
            plan_review_schedule_result
        )

        assert any(
            violation.kind == "global_object"
            and violation.dependency == "_RULES_HIDDEN_CALENDAR_CLIENT"
            and violation.owner == f"cmm.domains.languages.rules.{helper.__name__}"
            for violation in violations
        )

    assert (
        runtime_state.find_languages_runtime_purity_violations(
            plan_review_schedule_result
        )
        == ()
    )


@pytest.mark.parametrize(
    ("helper", "opcode", "dependency"),
    (
        (
            _immutable_global_rebinding_helper,
            "STORE_GLOBAL",
            "_IMMUTABLE_GLOBAL_STATE",
        ),
        (_attribute_write_helper, "STORE_ATTR", "calendar_modified"),
        (_subscript_write_helper, "STORE_SUBSCR", "<subscript>"),
        (_nonlocal_write_root, "STORE_DEREF", "state"),
    ),
)
def test_runtime_purity_oracle_rejects_effectful_bytecode_writes(
    helper: object,
    opcode: str,
    dependency: str,
) -> None:
    """Immutable rebinding and object mutation bytecode fail closed."""
    violations = runtime_state.find_languages_runtime_purity_violations(helper)

    assert any(
        violation.kind == "bytecode_write"
        and violation.dependency == f"{opcode}:{dependency}"
        for violation in violations
    )


def test_runtime_purity_oracle_rejects_unapproved_module_capability_chain() -> None:
    """An allowed module identity does not authorize uuid.os.mkdir."""
    violations = runtime_state.find_languages_runtime_purity_violations(
        _forbidden_uuid_capability_helper
    )

    assert any(
        violation.kind == "module_capability"
        and violation.dependency == "_UUID_MODULE.os.mkdir"
        for violation in violations
    )
