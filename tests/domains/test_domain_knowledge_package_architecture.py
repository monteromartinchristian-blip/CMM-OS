"""Phase 10.49 — architecture and anti-fragmentation guards.

AST-based guards over the Phase 10.49 declarative Domain surface.  They prove
that the new surface only *narrows* the canonical Phase 8 ``KnowledgePackage``
and never grows a parallel knowledge store, graph, provenance, temporal,
contradiction, privacy, permission, Cognitive Layer or Domain Pack parser, and
that the canonical ``domain.fragmentation`` owner is reused rather than
re-implemented.

Guards are AST-based rather than prose-based, so documentation that merely
*describes* prohibited behaviour does not trip them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cmm.domains.validation_fragmentation import analyze_fragmentation

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOMAINS_DIR = _REPO_ROOT / "cmm" / "domains"
_COGNITIVE_DIR = _REPO_ROOT / "cmm" / "cognitive"

# The three canonical Phase 10.49 modules.
PHASE_10_49_CANONICAL_MODULES = (
    _DOMAINS_DIR / "knowledge_package_contracts.py",
    _DOMAINS_DIR / "knowledge_package_composition.py",
    _DOMAINS_DIR / "knowledge_package_validation.py",
)

# The first-party declarative schema modules.
FIRST_PARTY_SCHEMA_MODULES = tuple(sorted(_DOMAINS_DIR.glob("*/knowledge_package.py")))

# ── Prohibited production infrastructure (plan Task 8 Step 1) ─────────────────

PROHIBITED_PRODUCTION_NAMES = frozenset(
    {
        "DomainKnowledgePackageBuilder",
        "DomainKnowledgePackageRegistry",
        "DomainKnowledgeRegistry",
        "DomainKnowledgePackageLoader",
        "DomainKnowledgeLoader",
        "DomainKnowledgePackageResolver",
        "DomainKnowledgeResolver",
        "DomainKnowledgePackageStore",
        "DomainKnowledgeStore",
        "DomainKnowledgePackageRuntime",
        "DomainKnowledgeRuntime",
        "DomainKnowledgePackageEngine",
        "DomainKnowledgeEngine",
    }
)

# Parallel knowledge infrastructure that must never be recreated, at any depth.
PROHIBITED_PARALLEL_SUFFIXES = (
    "KnowledgeStore",
    "KnowledgeGraph",
    "KnowledgePackageBuilder",
    "KnowledgePackageRegistry",
    "ProvenanceStore",
    "TemporalStore",
    "ContradictionStore",
    "PrivacyStore",
    "PermissionStore",
    "CognitiveLayer",
    "DomainPackParser",
)

FORBIDDEN_IMPORT_PREFIXES = (
    "cmm.agent_runtime",
    "cmm.domains.model_gateway",
    "cmm.domains.providers",
    "cmm.gateway",
    "cmm.providers",
    "cmm.runtime",
)

FORBIDDEN_IMPORT_NAMES = frozenset(
    {
        "ModelGateway",
        "ModelRouter",
        "ProviderAdapter",
        "ProviderRegistry",
        "DomainKnowledgePackageBuilder",
        "DomainKnowledgePackageEngine",
        "DomainKnowledgePackageRegistry",
    }
)

FORBIDDEN_EXECUTION_FUNCTIONS = frozenset(
    {
        "invoke_model",
        "call_model",
        "invoke_provider",
        "select_model",
        "route_request",
        "load_domain_pack",
        "parse_domain_pack",
        "resolve_domain_knowledge",
        "execute_validator",
        "run_validator",
    }
)

FORBIDDEN_NETWORK_MODULES = frozenset(
    {
        "httpx",
        "requests",
        "shelve",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }
)

_PHASE_10_49_SURFACE = PHASE_10_49_CANONICAL_MODULES + FIRST_PARTY_SCHEMA_MODULES


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _relative(path: Path) -> str:
    return str(path.relative_to(_REPO_ROOT))


def _iter_domain_sources() -> list[Path]:
    return sorted(_DOMAINS_DIR.rglob("*.py"))


def _defined_names(tree: ast.Module) -> list[str]:
    """Return every top-level and nested class/function/assigned name."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return names


def _imported_modules(tree: ast.Module) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _imported_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.extend(alias.asname or alias.name for alias in node.names)
    return names


def _called_names(tree: ast.Module) -> list[str]:
    called: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.append(func.id)
            elif isinstance(func, ast.Attribute):
                called.append(func.attr)
    return called


# ── Prohibited production names ───────────────────────────────────────────────


def test_domain_sources_never_define_prohibited_production_names() -> None:
    """No Phase 10.49 (or sibling) Domain module may define these symbols."""
    violations: list[str] = []
    for path in _iter_domain_sources():
        for name in _defined_names(_parse(path)):
            if name in PROHIBITED_PRODUCTION_NAMES:
                violations.append(f"{_relative(path)}::{name}")

    assert violations == [], violations


def test_domain_sources_never_define_prohibited_execution_functions() -> None:
    violations: list[str] = []
    for path in _iter_domain_sources():
        for name in _defined_names(_parse(path)):
            if name in FORBIDDEN_EXECUTION_FUNCTIONS:
                violations.append(f"{_relative(path)}::{name}")

    assert violations == [], violations


@pytest.mark.parametrize("path", _PHASE_10_49_SURFACE, ids=lambda p: _relative(p))
def test_phase_10_49_surface_has_no_parallel_knowledge_infrastructure(
    path: Path,
) -> None:
    """The new surface may not recreate parallel knowledge infrastructure."""
    tree = _parse(path)
    offenders = [
        name
        for name in _defined_names(tree)
        if any(name.endswith(suffix) for suffix in PROHIBITED_PARALLEL_SUFFIXES)
    ]

    assert offenders == [], f"{_relative(path)} defines {offenders}"


# ── Canonical builder ownership ───────────────────────────────────────────────


def test_cognitive_integration_still_owns_the_canonical_builder() -> None:
    """Phase 10.49 must not replace the canonical package construction path."""
    source = (_DOMAINS_DIR / "cognitive_integration.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="cmm/domains/cognitive_integration.py")

    assert "KnowledgePackageBuilder" in _imported_names(tree)
    assert "KnowledgePackageBuilder" in _called_names(tree)


def test_cognitive_integration_does_not_define_a_builder() -> None:
    tree = _parse(_DOMAINS_DIR / "cognitive_integration.py")

    assert [name for name in _defined_names(tree) if name.endswith("Builder")] == []


def test_validation_helper_returns_the_canonical_package_type() -> None:
    """Validation narrows; it never converts the package into a Domain model."""
    source = (_DOMAINS_DIR / "knowledge_package_validation.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source, filename="knowledge_package_validation.py")

    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    assert classes == []
    assert "KnowledgePackage" in _imported_names(tree)


# ── Provider / runtime / network isolation ────────────────────────────────────


@pytest.mark.parametrize("path", _PHASE_10_49_SURFACE, ids=lambda p: _relative(p))
def test_phase_10_49_surface_imports_no_provider_or_runtime_authority(
    path: Path,
) -> None:
    tree = _parse(path)
    modules = _imported_modules(tree)
    names = _imported_names(tree)

    violations = [
        module
        for module in modules
        if any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        )
    ]
    violations += [name for name in names if name in FORBIDDEN_IMPORT_NAMES]

    assert violations == [], f"{_relative(path)} imports {violations}"


@pytest.mark.parametrize("path", _PHASE_10_49_SURFACE, ids=lambda p: _relative(p))
def test_phase_10_49_surface_has_no_network_or_persistence_imports(
    path: Path,
) -> None:
    tree = _parse(path)
    roots = {module.split(".", 1)[0] for module in _imported_modules(tree)}

    assert roots & FORBIDDEN_NETWORK_MODULES == set()


# ── Canonical fragmentation owner reuse ───────────────────────────────────────


@pytest.mark.parametrize("path", _PHASE_10_49_SURFACE, ids=lambda p: _relative(p))
def test_canonical_fragmentation_owner_reports_no_findings(path: Path) -> None:
    """Reuse the canonical ``domain.fragmentation`` owner; never a parallel one."""
    findings = analyze_fragmentation(path.read_text(encoding="utf-8"), _relative(path))

    assert findings == [], findings


# ── Directional boundary: cognition must not depend on Domain packages ────────


def test_cognitive_layer_never_imports_domain_packages() -> None:
    """The canonical Phase 8 layer must stay below the Domain layer."""
    violations: list[str] = []
    for path in sorted(_COGNITIVE_DIR.rglob("*.py")):
        for module in _imported_modules(_parse(path)):
            if module == "cmm.domains" or module.startswith("cmm.domains."):
                violations.append(f"{_relative(path)}::{module}")

    assert violations == [], violations


# ── Declarative purity of the first-party surface ─────────────────────────────


def test_first_party_schema_modules_are_declarative_only() -> None:
    """Each first-party module declares exactly one pure schema factory.

    The twelve Phase 10.49 modules plus the Phase 10.52 ``mental_health``
    module, which follows the same declarative convention.
    """
    assert len(FIRST_PARTY_SCHEMA_MODULES) == 13

    for path in FIRST_PARTY_SCHEMA_MODULES:
        tree = _parse(path)
        functions = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        classes = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]

        assert functions == [f"build_{path.parent.name}_knowledge_package_schema"], (
            _relative(path),
            functions,
        )
        assert classes == [], _relative(path)
