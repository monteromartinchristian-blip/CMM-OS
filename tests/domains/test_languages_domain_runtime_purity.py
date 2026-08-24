"""Adversarial tests for the Languages schedule runtime-purity oracle."""

from __future__ import annotations

import pathlib as _MODULE_SERVICE

from tests.domains import _languages_runtime_state as runtime_state


class _HiddenCalendarClient:
    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def create_event(self, event: dict[str, str]) -> None:
        self.events.append(event)


_HIDDEN_CALENDAR_CLIENT = _HiddenCalendarClient()
_HIDDEN_MUTABLE_STATE: dict[str, str] = {}


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
