"""Runtime-state observations for Languages purity boundary tests."""

from __future__ import annotations

import dis
import inspect
import math
import uuid
from collections.abc import MutableMapping, MutableSequence, MutableSet
from copy import deepcopy
from dataclasses import dataclass
from types import FunctionType, ModuleType
from typing import Any

from cmm.domains.languages.rules import evaluate_learning_load, plan_spaced_review

_MUTABLE_RUNTIME_TYPES = (MutableMapping, MutableSequence, MutableSet, bytearray)
_IMMUTABLE_SCALAR_TYPES = (
    type(None),
    bool,
    int,
    float,
    complex,
    str,
    bytes,
    range,
    type(Ellipsis),
    type(NotImplemented),
)
_ALLOWED_EXTERNAL_FUNCTIONS = frozenset(
    {evaluate_learning_load, plan_spaced_review}
)
_ALLOWED_MODULES = frozenset({math, uuid})
_ALLOWED_BUILTINS = frozenset({bool, float, int, isinstance})


@dataclass(frozen=True, order=True)
class RuntimePurityViolation:
    """One forbidden dependency reachable from a purportedly pure helper."""

    kind: str
    dependency: str
    owner: str


def _is_deeply_immutable(value: Any) -> bool:
    if isinstance(value, _IMMUTABLE_SCALAR_TYPES):
        return True
    if isinstance(value, (tuple, frozenset)):
        return all(_is_deeply_immutable(item) for item in value)
    return False


def _is_allowed_identity(value: Any, allowed: frozenset[Any]) -> bool:
    return any(value is item for item in allowed)


def find_languages_runtime_purity_violations(
    root: FunctionType,
) -> tuple[RuntimePurityViolation, ...]:
    """Audit the runtime dependency closure of a Languages pure helper."""
    if not isinstance(root, FunctionType):
        raise TypeError("root must be a Python function")

    root_module = root.__module__
    pending = [root]
    seen: set[int] = set()
    violations: set[RuntimePurityViolation] = set()

    def inspect_dependency(
        *,
        owner: str,
        dependency: str,
        value: Any,
        source: str,
    ) -> None:
        if _is_deeply_immutable(value):
            return
        if isinstance(value, FunctionType):
            if value.__module__ == root_module:
                pending.append(value)
            elif not _is_allowed_identity(value, _ALLOWED_EXTERNAL_FUNCTIONS):
                violations.add(
                    RuntimePurityViolation("external_function", dependency, owner)
                )
            return
        if isinstance(value, ModuleType):
            if not _is_allowed_identity(value, _ALLOWED_MODULES):
                violations.add(RuntimePurityViolation("module", dependency, owner))
            return
        if _is_allowed_identity(value, _ALLOWED_BUILTINS):
            return
        violations.add(
            RuntimePurityViolation(f"{source}_object", dependency, owner)
        )

    while pending:
        function = pending.pop()
        function_identity = id(function)
        if function_identity in seen:
            continue
        seen.add(function_identity)
        owner = f"{function.__module__}.{function.__qualname__}"
        closure = inspect.getclosurevars(function)

        for dependency, value in closure.globals.items():
            inspect_dependency(
                owner=owner,
                dependency=dependency,
                value=value,
                source="global",
            )
        for dependency, value in closure.nonlocals.items():
            inspect_dependency(
                owner=owner,
                dependency=dependency,
                value=value,
                source="nonlocal",
            )
        for dependency, value in closure.builtins.items():
            if not _is_allowed_identity(value, _ALLOWED_BUILTINS):
                violations.add(
                    RuntimePurityViolation("builtin", dependency, owner)
                )

        positional_defaults = function.__defaults__ or ()
        for index, value in enumerate(positional_defaults):
            inspect_dependency(
                owner=owner,
                dependency=f"default[{index}]",
                value=value,
                source="default",
            )
        for dependency, value in (function.__kwdefaults__ or {}).items():
            inspect_dependency(
                owner=owner,
                dependency=f"default[{dependency}]",
                value=value,
                source="default",
            )
        for dependency, value in vars(function).items():
            inspect_dependency(
                owner=owner,
                dependency=dependency,
                value=value,
                source="function_attribute",
            )

        for instruction in dis.get_instructions(function):
            if instruction.opname == "IMPORT_NAME":
                violations.add(
                    RuntimePurityViolation("import", str(instruction.argval), owner)
                )

    return tuple(sorted(violations))


def snapshot_languages_module_state(module: ModuleType) -> dict[str, Any]:
    """Deep-copy observable module-owned state, including private containers."""
    return {
        name: deepcopy(value)
        for name, value in vars(module).items()
        if not name.startswith("__")
        and isinstance(value, _MUTABLE_RUNTIME_TYPES)
    }
