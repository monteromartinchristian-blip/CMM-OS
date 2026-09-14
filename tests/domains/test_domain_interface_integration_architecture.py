"""Phase 10.45 — Architecture and anti-fragmentation boundary guards.

Asserts Phase 10.45 stays a thin integration boundary:
- No parallel infrastructure owner classes (registry, store, repository,
  session store, workflow engine, approval store, permission engine, memory,
  knowledge graph, observability store, update service, runtime,
  orchestrator) — including for the canonical selection transition
  coordinator (no transition store, repository or interface-owned authority).
- The coordinator owns no persistence: it calls the injected shared session
  adapter but never instantiates or imports a store.
- Dependency direction is mandatory:
  ``interface_integration → selection_transition → resolver/composer/
  permission/session`` and never the reverse.
- No UI/frontend/transport framework imports (Swift/SwiftUI, React, web
  servers) and no transport primitives introduced by the phase.
- No direct ``cmm.memory`` / ``TechnicalMemory`` / ``cmm.cognitive`` access
  and no cognitive-store mutation calls.
- Strict dependency direction: canonical earlier-phase modules never import
  Phase 10.45 modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOMAINS_DIR = REPO_ROOT / "cmm" / "domains"

PHASE_10_45_FILES = (
    DOMAINS_DIR / "interface_integration_contracts.py",
    DOMAINS_DIR / "interface_integration.py",
    DOMAINS_DIR / "selection_transition_contracts.py",
    DOMAINS_DIR / "selection_transition.py",
    DOMAINS_DIR / "api.py",
    DOMAINS_DIR / "errors.py",
)

# Modules that existed before Phase 10.45 and must never depend on it.
# api.py, __init__.py and the Phase 10.45 modules themselves are excluded:
# the API facade and package aggregator legitimately expose the new seam.
EARLIER_PHASE_MODULES = tuple(
    path
    for path in sorted(DOMAINS_DIR.glob("*.py"))
    if path.name
    not in {
        "api.py",
        "__init__.py",
        "interface_integration.py",
        "interface_integration_contracts.py",
        "selection_transition.py",
        "selection_transition_contracts.py",
    }
)

FORBIDDEN_CLASS_TOKENS = (
    "InterfaceRegistry",
    "InterfaceStore",
    "InterfaceRepository",
    "InterfaceSessionStore",
    "InterfaceWorkflowEngine",
    "InterfaceApprovalStore",
    "InterfacePermissionEngine",
    "InterfaceMemory",
    "InterfaceKnowledgeGraph",
    "InterfaceObservabilityStore",
    "InterfaceUpdateService",
    "InterfaceRuntime",
    "InterfaceOrchestrator",
    "InterfaceSelectionStore",
    "InterfaceCompositionEngine",
    "InterfaceResolver",
    "InterfaceReviewStore",
    "InterfaceMemoryStore",
    "SelectionTransitionStore",
    "SelectionTransitionRepository",
)

FORBIDDEN_OWNER_SUFFIXES = ("Store", "Repository", "Engine")

FORBIDDEN_UI_IMPORT_TOKENS = (
    "swift",
    "swiftui",
    "react",
    "jsx",
    "uikit",
    "appkit",
    "flask",
    "fastapi",
    "starlette",
    "uvicorn",
    "django",
    "tornado",
    "aiohttp",
    "websocket",
    "socketio",
    "grpc",
    "graphql",
)

FORBIDDEN_UI_TEXT_TOKENS = ("Swift", "SwiftUI", "React", "JSX", "UIKit", "AppKit")

FORBIDDEN_TRANSPORT_MODULES = (
    "socket",
    "requests",
    "httpx",
    "urllib",
    "asyncio",
    "threading",
    "multiprocessing",
    "subprocess",
)

COGNITIVE_STORE_MUTATION_VERBS = frozenset(
    {
        "remember",
        "forget",
        "persist",
        "save",
        "commit",
        "delete",
        "relate",
        "invalidate",
        "mutate",
    }
)


def _parse(file_path: Path) -> ast.Module:
    return ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))


def _imported_module_names(tree: ast.Module) -> list[str]:
    """Module paths only; from-imported symbol names are not modules."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _imported_symbol_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.extend(alias.name for alias in node.names)
    return names


class TestForbiddenInfrastructureClasses:
    """Ensure Phase 10.45 defines no parallel authority or storage owner."""

    def test_no_forbidden_infrastructure_class_tokens(self) -> None:
        for file_path in PHASE_10_45_FILES:
            tree = _parse(file_path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for token in FORBIDDEN_CLASS_TOKENS:
                    assert token not in node.name, (
                        f"Forbidden infrastructure class {node.name} defined in "
                        f"{file_path.name}"
                    )

    def test_no_owner_class_suffixes(self) -> None:
        for file_path in PHASE_10_45_FILES:
            tree = _parse(file_path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for suffix in FORBIDDEN_OWNER_SUFFIXES:
                    assert not node.name.endswith(suffix), (
                        f"Forbidden owner class {node.name} ends with {suffix} "
                        f"in {file_path.name}"
                    )


class TestForbiddenUiAndFrameworkImports:
    """Ensure Phase 10.45 never imports UI, frontend, or transport frameworks."""

    def test_no_ui_or_frontend_imports(self) -> None:
        for file_path in PHASE_10_45_FILES:
            modules = _imported_module_names(_parse(file_path))
            for module in modules:
                lowered = module.lower()
                for token in FORBIDDEN_UI_IMPORT_TOKENS:
                    assert token not in lowered, (
                        f"Forbidden UI/framework import '{module}' in {file_path.name}"
                    )

    def test_no_ui_framework_text_tokens(self) -> None:
        for file_path in PHASE_10_45_FILES:
            source = file_path.read_text(encoding="utf-8")
            for token in FORBIDDEN_UI_TEXT_TOKENS:
                assert token not in source, (
                    f"Forbidden UI framework token '{token}' in {file_path.name}"
                )

    def test_no_transport_primitive_imports(self) -> None:
        for file_path in PHASE_10_45_FILES:
            modules = _imported_module_names(_parse(file_path))
            for module in modules:
                for token in FORBIDDEN_TRANSPORT_MODULES:
                    assert token not in module.lower(), (
                        f"Forbidden transport import '{module}' in {file_path.name}"
                    )


class TestNoDirectMemoryOrCognitiveAccess:
    """Ensure Phase 10.45 never touches cmm.memory or cognitive stores directly."""

    def test_no_memory_or_cognitive_imports(self) -> None:
        for file_path in PHASE_10_45_FILES:
            tree = _parse(file_path)
            modules = _imported_module_names(tree)
            for module in modules:
                assert not module.startswith("cmm.memory"), (
                    f"Prohibited cmm.memory import '{module}' in {file_path.name}"
                )
                assert "TechnicalMemory" not in module, (
                    f"Prohibited TechnicalMemory import '{module}' in {file_path.name}"
                )
                assert not module.startswith("cmm.cognitive"), (
                    f"Prohibited cognitive import '{module}' in {file_path.name}"
                )
            for symbol in _imported_symbol_names(tree):
                assert "TechnicalMemory" not in symbol, (
                    f"Prohibited TechnicalMemory import '{symbol}' in {file_path.name}"
                )

    def test_no_cognitive_store_mutation_calls(self) -> None:
        integrator_file = DOMAINS_DIR / "interface_integration.py"
        tree = _parse(integrator_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in COGNITIVE_STORE_MUTATION_VERBS, (
                    f"Prohibited cognitive-store mutation verb "
                    f"'{node.func.attr}' in {integrator_file.name} at line {node.lineno}"
                )


class TestDependencyDirection:
    """Ensure canonical earlier-phase modules never import Phase 10.45."""

    def test_earlier_phase_modules_never_import_phase_10_45(self) -> None:
        for file_path in EARLIER_PHASE_MODULES:
            modules = _imported_module_names(_parse(file_path))
            for module in modules:
                assert "interface_integration" not in module, (
                    f"Illegal Phase 10.45 import '{module}' in {file_path.name}"
                )
                assert "selection_transition" not in module, (
                    f"Illegal Phase 10.45 import '{module}' in {file_path.name}"
                )

    def test_selection_transition_never_imports_interface_modules(self) -> None:
        for file_path in (
            DOMAINS_DIR / "selection_transition.py",
            DOMAINS_DIR / "selection_transition_contracts.py",
        ):
            modules = _imported_module_names(_parse(file_path))
            for module in modules:
                assert "interface_integration" not in module, (
                    f"Illegal reverse dependency '{module}' in {file_path.name}"
                )

    def test_interface_integration_imports_selection_transition_contracts(
        self,
    ) -> None:
        """The delegation seam imports the coordinator contracts, never reverse."""
        modules = _imported_module_names(
            _parse(DOMAINS_DIR / "interface_integration.py")
        )
        assert any("selection_transition_contracts" in module for module in modules)


class TestSelectionTransitionCoordinatorArchitecture:
    """Ensure the coordinator owns no store, registry or parallel authority."""

    def test_coordinator_imports_no_store_or_authority_owner(self) -> None:
        file_path = DOMAINS_DIR / "selection_transition.py"
        tree = _parse(file_path)
        symbols = _imported_symbol_names(tree)
        owner_symbols = (
            "SessionStore",
            "InMemorySessionStore",
            "DomainRegistry",
            "DomainPermissionRegistry",
            "DefaultDomainResolver",
            "DefaultDomainComposer",
            "SharedSessionDomainAdapter",
        )
        for symbol in symbols:
            assert symbol not in owner_symbols, (
                f"Coordinator imports owned authority '{symbol}' in {file_path.name}"
            )
        source = file_path.read_text(encoding="utf-8")
        for token in ("SessionStore(", "InMemorySessionStore("):
            assert token not in source, (
                f"Coordinator instantiates a store in {file_path.name}"
            )

    def test_coordinator_may_call_injected_session_adapter_only(self) -> None:
        """The adapter itself remains injected: no direct store calls."""
        file_path = DOMAINS_DIR / "selection_transition.py"
        source = file_path.read_text(encoding="utf-8")
        assert "session_adapter" in source
