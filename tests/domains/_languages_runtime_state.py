"""Runtime-state observations for Languages purity boundary tests."""

from __future__ import annotations

import builtins as python_builtins
import dis
import inspect
import math
import uuid
from collections.abc import Mapping, MutableMapping, MutableSequence, MutableSet
from copy import deepcopy
from dataclasses import dataclass
from types import CodeType, FunctionType, ModuleType
from typing import Any

_MUTABLE_RUNTIME_TYPES = (MutableMapping, MutableSequence, MutableSet, bytearray)
_LANGUAGES_MODULE_PREFIX = "cmm.domains.languages."
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
_ALLOWED_GLOBAL_IDENTITIES = frozenset({Mapping})
_ALLOWED_BUILTINS = frozenset(
    {
        bool,
        dict,
        float,
        frozenset,
        int,
        isinstance,
        len,
        list,
        min,
        set,
        sorted,
        str,
        tuple,
    }
)
_ALLOWED_MODULE_CAPABILITIES = (
    (math, frozenset({("isfinite",), ("isinf",), ("isnan",)})),
    (uuid, frozenset({("uuid4",)})),
)
_EFFECTFUL_WRITE_OPCODES = frozenset(
    {
        "DELETE_ATTR",
        "DELETE_GLOBAL",
        "DELETE_SUBSCR",
        "STORE_ATTR",
        "STORE_GLOBAL",
        "STORE_SUBSCR",
    }
)


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


def _allowed_module_capabilities(
    value: Any,
) -> frozenset[tuple[str, ...]] | None:
    for module, capabilities in _ALLOWED_MODULE_CAPABILITIES:
        if value is module:
            return capabilities
    return None


def _iter_code_objects(code: CodeType) -> tuple[CodeType, ...]:
    nested = tuple(
        nested_code
        for constant in code.co_consts
        if isinstance(constant, CodeType)
        for nested_code in _iter_code_objects(constant)
    )
    return (code, *nested)


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
            function_module = value.__module__ or ""
            if function_module == root_module or function_module.startswith(
                _LANGUAGES_MODULE_PREFIX
            ):
                pending.append(value)
            else:
                violations.add(
                    RuntimePurityViolation("external_function", dependency, owner)
                )
            return
        if isinstance(value, ModuleType):
            if source != "global" or _allowed_module_capabilities(value) is None:
                violations.add(RuntimePurityViolation("module", dependency, owner))
            return
        if _is_allowed_identity(
            value, _ALLOWED_GLOBAL_IDENTITIES
        ) or _is_allowed_identity(value, _ALLOWED_BUILTINS):
            return
        violations.add(RuntimePurityViolation(f"{source}_object", dependency, owner))

    def inspect_code_dependencies(
        function: FunctionType,
        function_owner: str,
    ) -> None:
        global_namespace = function.__globals__
        missing = object()

        for code in _iter_code_objects(function.__code__):
            code_owner = (
                function_owner
                if code is function.__code__
                else f"{function.__module__}.{getattr(code, 'co_qualname', code.co_name)}"
            )
            instructions = tuple(dis.get_instructions(code))
            for index, instruction in enumerate(instructions):
                opcode = instruction.opname
                dependency = str(instruction.argval)

                if opcode == "IMPORT_NAME":
                    violations.add(
                        RuntimePurityViolation("import", dependency, code_owner)
                    )
                    continue

                if opcode in _EFFECTFUL_WRITE_OPCODES:
                    write_target = (
                        "<subscript>"
                        if opcode in {"DELETE_SUBSCR", "STORE_SUBSCR"}
                        else dependency
                    )
                    violations.add(
                        RuntimePurityViolation(
                            "bytecode_write",
                            f"{opcode}:{write_target}",
                            code_owner,
                        )
                    )
                    continue

                if (
                    opcode in {"DELETE_DEREF", "STORE_DEREF"}
                    and dependency in code.co_freevars
                ):
                    violations.add(
                        RuntimePurityViolation(
                            "bytecode_write",
                            f"{opcode}:{dependency}",
                            code_owner,
                        )
                    )
                    continue

                if opcode != "LOAD_GLOBAL":
                    continue

                value = global_namespace.get(dependency, missing)
                if value is missing:
                    value = getattr(python_builtins, dependency, missing)
                    if value is missing:
                        violations.add(
                            RuntimePurityViolation(
                                "unresolved_global", dependency, code_owner
                            )
                        )
                    elif not _is_allowed_identity(value, _ALLOWED_BUILTINS):
                        violations.add(
                            RuntimePurityViolation("builtin", dependency, code_owner)
                        )
                    continue

                inspect_dependency(
                    owner=code_owner,
                    dependency=dependency,
                    value=value,
                    source="global",
                )
                capabilities = _allowed_module_capabilities(value)
                if capabilities is None:
                    continue

                attribute_chain: list[str] = []
                next_index = index + 1
                while next_index < len(instructions) and instructions[
                    next_index
                ].opname in {"LOAD_ATTR", "LOAD_METHOD"}:
                    attribute_chain.append(str(instructions[next_index].argval))
                    next_index += 1
                capability = tuple(attribute_chain)
                if capability not in capabilities:
                    rendered_capability = ".".join(attribute_chain) or "<direct>"
                    violations.add(
                        RuntimePurityViolation(
                            "module_capability",
                            f"{dependency}.{rendered_capability}",
                            code_owner,
                        )
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
                violations.add(RuntimePurityViolation("builtin", dependency, owner))

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

        inspect_code_dependencies(function, owner)

    return tuple(sorted(violations))


def snapshot_languages_module_state(module: ModuleType) -> dict[str, Any]:
    """Deep-copy observable module-owned state, including private containers."""
    return {
        name: deepcopy(value)
        for name, value in vars(module).items()
        if not name.startswith("__") and isinstance(value, _MUTABLE_RUNTIME_TYPES)
    }
