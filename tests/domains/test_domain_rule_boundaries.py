from __future__ import annotations

import ast
from pathlib import Path


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_cognitive_rule_core_has_no_domain_dependency() -> None:
    for path in Path("cmm/cognitive").glob("reasoning_rule*.py"):
        assert not any(name.startswith("cmm.domains") for name in _imports(path))


def test_rule_services_have_no_runtime_io_or_future_phase_dependencies() -> None:
    forbidden = ("agent_runtime", "workflow", "operation", "subprocess", "requests", "httpx", "socket")
    for path in Path("cmm/domains").glob("rule*.py"):
        source = path.read_text()
        assert not any(term in source for term in forbidden)
        assert "except Exception" not in source
        assert "str(exc)" not in source
        assert "repr(exc)" not in source


def test_rule_services_do_not_resolve_or_register_profiles() -> None:
    for filename in ("rule_selection.py", "rule_execution.py"):
        source = (Path("cmm/domains") / filename).read_text()
        assert "profile_registry" not in source
        assert "profile_resolver" not in source
