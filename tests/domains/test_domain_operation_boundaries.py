from __future__ import annotations

import ast
import importlib
from pathlib import Path

from cmm import domains

PUBLIC = {
    "DomainOperationDefinition",
    "DomainOperationRequest",
    "DomainOperationContext",
    "DomainOperationResult",
    "DomainOperationType",
    "DomainOperationStatus",
    "DomainOperationAvailability",
    "DomainOperationAvailabilityResolver",
    "InMemoryDomainOperationRegistry",
    "DomainOperationExecutionDelegate",
    "DefaultDomainOperationOrchestrator",
    "build_initial_domain_operation_catalog",
}


def test_public_api_exports_operation_contracts_and_no_catalog_implementation() -> None:
    assert PUBLIC <= set(domains.__all__)
    assert "_CatalogImplementation" not in domains.__all__
    for symbol in PUBLIC:
        assert getattr(domains, symbol) is not None


def test_import_orders_are_cycle_free() -> None:
    importlib.import_module("cmm.agent_runtime")
    importlib.import_module("cmm.domains")
    importlib.reload(importlib.import_module("cmm.domains.operation_execution"))


def test_common_layers_do_not_import_domains() -> None:
    for root in (Path("cmm/agent_runtime"), Path("cmm/execution")):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = [
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            ]
            assert not any(module.startswith("cmm.domains") for module in imports), path


def test_domain_operation_modules_have_no_forbidden_effect_imports_or_calls() -> None:
    forbidden_imports = {
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "openai",
        "sqlite3",
    }
    forbidden_calls = {"open", "eval", "exec", "compile", "__import__"}
    for path in Path("cmm/domains").glob("operation_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name.split(".")[0] in forbidden_imports
                    for alias in node.names
                ), path
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden_imports, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls, path
