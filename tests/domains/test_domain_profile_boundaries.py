"""Phase 10.11 – Boundary tests for Domain Profile modules.

Static AST and source scans confirming ``cmm/domains/profile_*.py`` never
touch the filesystem, network, persistence, memory operations, workflow or
operation execution, model or prompt selection, runtime identity lookup,
runtime authorization, cognitive rule execution, Phase 10.12 concrete rules,
broad exception handling or generic ``dict.update()`` merges.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_DOMAINS_DIR = Path("cmm/domains")
_PROFILE_PATHS = sorted(_DOMAINS_DIR.glob("profile_*.py"))

# Top-level modules the Domain Profile layer may import from. Everything
# else is a boundary violation. ``cmm.domains.*`` intra-package imports and
# ``cmm.cognitive.enums`` (for SensitivityLevel) are explicitly allowed.
_ALLOWED_TOP_LEVEL_IMPORTS = frozenset(
    {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "types",
        "typing",
        "uuid",
    }
)

_FORBIDDEN_SUBSYSTEM_ROOTS = frozenset(
    {
        "cmm.memory",
        "cmm.execution",
        "cmm.planner",
        "cmm.runtime",
        "cmm.agent_runtime",
        "cmm.development",
        "cmm.transformations",
        "cmm_agent",
        "kernel",
    }
)

# Dangerous builtins/executors that must never be called.
_FORBIDDEN_CALL_NAMES = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "input",
        "breakpoint",
    }
)

# Attribute calls that imply filesystem, persistence or process execution.
_FORBIDDEN_ATTRIBUTE_CALLS = frozenset(
    {
        "read_text",
        "write_text",
        "read_bytes",
        "write_bytes",
        "execute",
        "executemany",
        "executescript",
        "connect",
        "commit",
        "save",
        "Popen",
        "system",
        "popen",
        "unlink",
        "mkdir",
        "rmdir",
        "send",
        "recv",
        "post",
    }
)

_FORBIDDEN_TEXT_PATTERNS = {
    "pathlib": r"\bpathlib\b",
    "os_module": r"\bos\.",
    "subprocess": r"\bsubprocess\b",
    "socket": r"\bsocket\b",
    "requests": r"\brequests\b",
    "httpx": r"\bhttpx\b",
    "urllib": r"\burllib\b",
    "sqlite3": r"\bsqlite3\b",
    "sqlalchemy": r"\bsqlalchemy\b",
    "open_call": r"\bopen\(",
    "path_call": r"\bPath\(",
    "eval_call": r"\beval\(",
    "exec_call": r"\bexec\(",
    "compile_call": r"\bcompile\(",
    "importlib": r"\bimportlib\b",
    "broad_except": r"except\s+Exception",
    "str_exc": r"str\(exc\)",
    "repr_exc": r"repr\(exc\)",
    "dict_update": r"dict\.update\(",
    "shutil": r"\bshutil\b",
    "aiohttp": r"\baiohttp\b",
}

# Modules that must never import ``Callable`` at all: profiles are
# declarative and must not carry executable values.
_MODULES_WITHOUT_CALLABLE = frozenset(
    {
        "profile_contracts.py",
        "profile_registry.py",
        "profile_composition.py",
    }
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _import_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module)
    return roots


def test_profile_files_exist() -> None:
    names = {p.name for p in _PROFILE_PATHS}
    assert names == {
        "profile_contracts.py",
        "profile_registry.py",
        "profile_composition.py",
        "profile_resolver.py",
    }


class TestForbiddenImports:
    def test_only_allowed_import_roots(self) -> None:
        for path in _PROFILE_PATHS:
            tree = _parse(path)
            for module in _import_roots(tree):
                allowed = (
                    module.split(".")[0] in _ALLOWED_TOP_LEVEL_IMPORTS
                    or module == "cmm.cognitive.enums"
                    or module.startswith("cmm.domains.")
                )
                assert allowed, f"{path.name}: forbidden import root {module!r}"

    def test_no_forbidden_subsystem_imports(self) -> None:
        for path in _PROFILE_PATHS:
            tree = _parse(path)
            for module in _import_roots(tree):
                top = module.split(".")[0]
                assert top not in {
                    "pathlib",
                    "os",
                    "subprocess",
                    "socket",
                    "requests",
                    "httpx",
                    "urllib",
                    "sqlite3",
                    "sqlalchemy",
                    "importlib",
                    "shutil",
                    "sys",
                    "io",
                    "threading",
                    "multiprocessing",
                }, f"{path.name}: forbidden module import {module!r}"
                assert not any(
                    module == root or module.startswith(f"{root}.")
                    for root in _FORBIDDEN_SUBSYSTEM_ROOTS
                ), f"{path.name}: forbidden subsystem import {module!r}"

    def test_declarative_modules_do_not_import_callable(self) -> None:
        for path in _PROFILE_PATHS:
            if path.name not in _MODULES_WITHOUT_CALLABLE:
                continue
            tree = _parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported = {alias.name for alias in node.names}
                    assert "Callable" not in imported, (
                        f"{path.name}: Callable import implies executable values"
                    )


class TestForbiddenCalls:
    def test_no_dangerous_builtin_calls(self) -> None:
        for path in _PROFILE_PATHS:
            tree = _parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert node.func.id not in _FORBIDDEN_CALL_NAMES, (
                        f"{path.name}: forbidden call {node.func.id}()"
                    )

    def test_no_io_or_execution_attribute_calls(self) -> None:
        for path in _PROFILE_PATHS:
            tree = _parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in _FORBIDDEN_ATTRIBUTE_CALLS, (
                        f"{path.name}: forbidden attribute call .{node.func.attr}()"
                    )


class TestForbiddenExceptionPatterns:
    def test_no_broad_except_handlers(self) -> None:
        for path in _PROFILE_PATHS:
            tree = _parse(path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                assert node.type is not None, f"{path.name}: bare except handler"
                names = set()
                targets = (
                    node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
                )
                for target in targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
                    elif isinstance(target, ast.Attribute):
                        names.add(target.attr)
                assert names.isdisjoint({"Exception", "BaseException"}), (
                    f"{path.name}: broad exception handler {sorted(names)}"
                )


class TestForbiddenTextPatterns:
    def test_no_forbidden_patterns_in_source(self) -> None:
        for path in _PROFILE_PATHS:
            source = path.read_text(encoding="utf-8")
            for label, pattern in _FORBIDDEN_TEXT_PATTERNS.items():
                assert not re.search(pattern, source), (
                    f"{path.name}: forbidden pattern {label}"
                )

    def test_no_phase_1012_references(self) -> None:
        for path in _PROFILE_PATHS:
            source = path.read_text(encoding="utf-8")
            assert "10.12" not in source
            assert "phase_10_12" not in source


class TestDeterminismGuards:
    def test_no_iteration_over_set_literals_or_calls(self) -> None:
        # No output may depend on set iteration order: profile modules never
        # iterate directly over a set literal or a set() call.
        for path in _PROFILE_PATHS:
            tree = _parse(path)
            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.comprehension)):
                    iter_node = node.iter
                    assert not isinstance(iter_node, ast.Set), (
                        f"{path.name}: iteration over set literal"
                    )
                    if isinstance(iter_node, ast.Call) and isinstance(
                        iter_node.func, ast.Name
                    ):
                        assert iter_node.func.id != "set", (
                            f"{path.name}: iteration over set() call"
                        )

    def test_no_callable_fields_in_contracts(self) -> None:
        # Contracts are declarative: no annotated contract field may be a
        # callable type (no executable values).
        for path in _PROFILE_PATHS:
            if path.name != "profile_contracts.py":
                continue
            tree = _parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.AnnAssign) and isinstance(
                    node.annotation, ast.Name
                ):
                    assert node.annotation.id != "Callable", (
                        f"{path.name}: callable contract field"
                    )


class TestResolverBoundary:
    def test_resolver_has_no_registry_access(self) -> None:
        path = _DOMAINS_DIR / "profile_resolver.py"
        tree = _parse(path)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert "cmm.domains.profile_registry" not in imported
        source = path.read_text(encoding="utf-8")
        assert "DomainProfileRegistry" not in source
        assert "InMemoryDomainProfileRegistry" not in source
