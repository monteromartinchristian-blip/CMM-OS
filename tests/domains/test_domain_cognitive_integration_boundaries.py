"""Architecture boundaries for the Phase 10.40 cognitive integration."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cmm.domains.validation_fragmentation import analyze_fragmentation

ROOT = Path(__file__).resolve().parents[2]
COGNITIVE = ROOT / "cmm" / "cognitive"
PHASE_1040_MODULES = (
    ROOT / "cmm" / "domains" / "cognitive_integration_contracts.py",
    ROOT / "cmm" / "domains" / "cognitive_integration.py",
)
PROHIBITED_IMPORTS = (
    "cmm.agent_runtime",
    "cmm.domains.cross_domain_engine",
)
PROHIBITED_OWNER_SUFFIXES = (
    "CognitiveEngine",
    "KnowledgeStore",
    "KnowledgeGraph",
    "GapEngine",
    "QuestionEngine",
    "ConfidenceEngine",
    "ContradictionEngine",
    "TemporalEngine",
    "CognitiveTraceStore",
    "CognitiveSessionStore",
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports_domain(path: Path) -> bool:
    tree = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if _absolute_import_module(node, path).startswith("cmm.domains"):
                return True
        elif isinstance(node, ast.Import) and any(
            alias.name.startswith("cmm.domains") for alias in node.names
        ):
            return True
    return False


def _absolute_import_module(node: ast.ImportFrom, path: Path) -> str:
    """Resolve an import-from module relative to its source module."""
    if not node.level:
        return node.module or ""

    source_parts = path.with_suffix("").parts
    cmm_index = source_parts.index("cmm")
    module_parts = source_parts[cmm_index:]
    package_parts = module_parts[:-1]
    parent_parts = package_parts[: len(package_parts) - node.level + 1]
    return ".".join((*parent_parts, *(node.module or "").split("."))).rstrip(".")


def _is_prohibited_import(module: str) -> bool:
    return any(
        module == prohibited or module.startswith(f"{prohibited}.")
        for prohibited in PROHIBITED_IMPORTS
    )


def _prohibited_imports(path: Path) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.Import):
            imports.extend(
                alias.name for alias in node.names if _is_prohibited_import(alias.name)
            )
        elif isinstance(node, ast.ImportFrom):
            module = _absolute_import_module(node, path)
            if _is_prohibited_import(module):
                imports.append(module)
            imports.extend(
                f"{module}.{alias.name}".lstrip(".")
                for alias in node.names
                if _is_prohibited_import(f"{module}.{alias.name}".lstrip("."))
            )
    return imports


def _prohibited_owner_definitions(path: Path) -> list[str]:
    return [
        node.name
        for node in ast.walk(_parse(path))
        if isinstance(node, ast.ClassDef)
        and node.name != "DefaultDomainCognitiveIntegrator"
        and any(node.name.endswith(suffix) for suffix in PROHIBITED_OWNER_SUFFIXES)
    ]


def test_cognitive_layer_remains_domain_agnostic() -> None:
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in sorted(COGNITIVE.rglob("*.py"))
        if _imports_domain(path)
    ]
    assert offenders == []


def test_cognitive_dependency_scan_resolves_relative_domain_import(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "cmm" / "cognitive" / "relative_import.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("from ..domains import contracts\n", encoding="utf-8")

    assert _imports_domain(source_path)


def test_phase_1040_modules_do_not_depend_on_runtime_or_cross_domain_engine() -> None:
    offenders = {
        path.relative_to(ROOT).as_posix(): _prohibited_imports(path)
        for path in PHASE_1040_MODULES
        if path.exists() and _prohibited_imports(path)
    }
    assert offenders == {}


def test_phase_1040_modules_do_not_define_cognitive_or_global_owners() -> None:
    offenders = {
        path.relative_to(ROOT).as_posix(): _prohibited_owner_definitions(path)
        for path in PHASE_1040_MODULES
        if path.exists() and _prohibited_owner_definitions(path)
    }
    assert offenders == {}


@pytest.mark.parametrize(
    ("source", "expected_code"),
    (
        (
            "class DomainKnowledgeStore:\n    pass\n",
            "DOMAIN_FRAGMENTATION_KNOWLEDGE_STORE_DUPLICATION",
        ),
        (
            "class DomainKnowledgeGraph:\n    pass\n",
            "DOMAIN_FRAGMENTATION_KNOWLEDGE_GRAPH_DUPLICATION",
        ),
        (
            "class DomainCognitiveTraceStore:\n    pass\n",
            "DOMAIN_FRAGMENTATION_TRACE_STORE_DUPLICATION",
        ),
    ),
)
def test_fragmentation_guard_rejects_duplicate_cognitive_or_global_owners(
    source: str,
    expected_code: str,
) -> None:
    findings = analyze_fragmentation(source, "phase1040_owner.py")
    assert expected_code in {str(finding["code"]) for finding in findings}


# ── Task 10: Adversarial Boundary Gate (Cases J & K) ─────────────────────────


def test_integrator_has_no_direct_persistence_mutations() -> None:
    """Case J: AST inspect calls inside DefaultDomainCognitiveIntegrator and

    reject mutation calls on its knowledge-store field:
    - save item/evidence/relation/contradiction;
    - delete item/evidence/relation/contradiction;
    - transaction mutation.
    Avoid repository-wide substring scans.
    """
    path = ROOT / "cmm" / "domains" / "cognitive_integration.py"
    tree = _parse(path)

    mutation_methods = {
        "save_item",
        "save_evidence",
        "save_relation",
        "save_contradiction",
        "delete_item",
        "delete_evidence",
        "delete_relation",
        "delete_contradiction",
        "begin_transaction",
        "commit_transaction",
        "rollback_transaction",
        "transaction",
    }

    mutations_found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and (
                func.attr in mutation_methods
                or func.attr.startswith(("save_", "delete_", "mutate_"))
            ):
                mutations_found.append((func.attr, getattr(node, "lineno", 0)))

    assert mutations_found == []


def test_persistence_mutation_checker_detects_violations() -> None:
    """Verifies that the persistence mutation AST scanner detects violations."""
    fake_source = (
        "def mutate(store, item):\n"
        "    store.save_item(item)\n"
        "    store.delete_relation('rel-1')\n"
        "    store.begin_transaction()\n"
    )
    fake_tree = ast.parse(fake_source)
    mutation_methods = {
        "save_item",
        "save_evidence",
        "save_relation",
        "save_contradiction",
        "delete_item",
        "delete_evidence",
        "delete_relation",
        "delete_contradiction",
        "begin_transaction",
        "commit_transaction",
        "rollback_transaction",
        "transaction",
    }
    mutations_found = [
        node.func.attr
        for node in ast.walk(fake_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in mutation_methods
    ]
    assert mutations_found == ["save_item", "delete_relation", "begin_transaction"]


def test_no_parallel_cognitive_or_runtime_owner_introduced() -> None:
    """Case K: Architecture scan confirms no parallel owners exist in Phase 10.40."""
    for path in PHASE_1040_MODULES:
        assert path.exists()
        assert _prohibited_imports(path) == []
        assert _prohibited_owner_definitions(path) == []
