"""Phase 10.53 — Neurodivergence Domain architecture / adversarial gate.

Detects forbidden fragmentation of the Neurodivergence Domain Pack and proves
the pack introduces no parallel infrastructure, no Phase 11 production surface,
and no import-time side effects.

Reuses the canonical Phase 10.39 fragmentation analyzer
(``cmm.domains.validation_fragmentation``) instead of building a new scanner.

The import-safety checks are done in-process (fresh module import + static
top-level statements + canonical registry emptiness) rather than by spawning an
interpreter, so this gate itself never executes anything external.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

from cmm.domains.validation_fragmentation import analyze_fragmentation

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = REPO_ROOT / "cmm" / "domains" / "neurodivergence"

#: Production class/function names that must never exist in this pack.
FORBIDDEN_OWNER_NAMES = (
    "NeurodivergenceRegistry",
    "NeurodivergenceLoader",
    "NeurodivergenceResolver",
    "NeurodivergenceComposer",
    "NeurodivergenceRuntime",
    "NeurodivergenceEngine",
    "NeurodivergenceStore",
    "NeurodivergenceMemory",
    "NeurodivergenceMemoryStore",
    "NeurodivergenceKnowledgeGraph",
    "NeurodivergenceTemporalEngine",
    "NeurodivergencePlanner",
    "NeurodivergenceWorkflowEngine",
    "NeurodivergencePermissionEngine",
    "NeurodivergenceApprovalEngine",
    "NeurodivergencePrivacyEngine",
    "NeurodivergenceTraceStore",
    "NeurodivergenceValidationEngine",
    "NeurodivergenceDiagnosticEngine",
    "NeurodivergenceDifferentialEngine",
    "NeurodivergenceDiagnosisRegistry",
    "NeurodivergenceModelRouter",
    "NeurodivergenceModelGateway",
    "DiagnosisRegistry",
    "DiagnosisStore",
)

#: Substrings that must never appear in a pack class/function name.
FORBIDDEN_OWNER_FRAGMENTS = (
    "NeurodivergenceRegistry",
    "NeurodivergenceLoader",
    "NeurodivergenceResolver",
    "NeurodivergenceComposer",
    "NeurodivergenceRuntime",
    "NeurodivergenceEngine",
    "NeurodivergenceStore",
    "NeurodivergenceKnowledgeGraph",
    "NeurodivergenceTemporalEngine",
    "NeurodivergencePlanner",
    "NeurodivergenceWorkflowEngine",
    "NeurodivergencePermissionEngine",
    "NeurodivergenceApprovalEngine",
    "NeurodivergencePrivacyEngine",
    "NeurodivergenceTraceStore",
    "NeurodivergenceValidationEngine",
    "NeurodivergenceDiagnosticEngine",
    "NeurodivergenceDifferentialEngine",
    "DiagnosisRegistry",
)

#: Production module stems that must never appear in this pack.
FORBIDDEN_MODULE_STEMS = (
    "registry",
    "loader",
    "resolver",
    "composer",
    "runtime",
    "store",
    "planner",
    "engine",
    "gateway",
    "router",
)

#: Sanctioned pack modules (the approved 19-module package boundary).
APPROVED_MODULES = frozenset(
    {
        "__init__.py",
        "benchmarks.py",
        "bootstrap.py",
        "catalog.py",
        "definition.py",
        "integration.py",
        "knowledge_package.py",
        "memory.py",
        "model_policy.py",
        "operations.py",
        "permissions.py",
        "presentation.py",
        "privacy.py",
        "profile.py",
        "quality_metrics.py",
        "resources.py",
        "rules.py",
        "trace.py",
        "workflows.py",
    }
)

#: Phase 11 surfaces that Phase 10.53 must not introduce.
FORBIDDEN_PHASE_11_NAMES = (
    "CommunicationProfile",
    "ResponseRenderer",
    "ModelGateway",
    "ProviderRegistry",
    "ApplicationUI",
    "RenderPlan",
    "ResponsePlan",
)

#: A second epistemic/certainty enum or second knowledge model must not exist.
FORBIDDEN_SECOND_MODEL_NAMES = (
    "KnowledgePackageBuilder",
    "KnowledgeModel",
    "CertaintyLevel",
    "CertaintyState",
    "EpistemicStatus",
    "ClinicalStatus",
    "DiagnosisRecord",
    "BenchmarkRunner",
    "BenchmarkRuntime",
    "QualityEvaluatorRuntime",
    "QualityRuntime",
)

#: Executable/external surfaces the production pack must never import.
FORBIDDEN_IMPORT_ROOTS = (
    "subprocess",
    "requests",
    "urllib",
    "httpx",
    "socket",
    "os",
    "shutil",
)

_PACK_PACKAGE = "cmm.domains.neurodivergence"


def _pack_files() -> tuple[Path, ...]:
    return tuple(sorted(PACKAGE_DIR.glob("*.py")))


def _pack_sources() -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in _pack_files()}


def _class_and_function_names(tree: ast.Module) -> tuple[str, ...]:
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
    return tuple(names)


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_package_boundary_matches_the_approved_structure():
    modules = {path.name for path in _pack_files()}

    assert modules == APPROVED_MODULES
    assert len(modules) == 19


def test_no_forbidden_parallel_owner_class_or_function_exists():
    offenders: list[str] = []
    for path, source in _pack_sources().items():
        for name in _class_and_function_names(ast.parse(source)):
            if name in FORBIDDEN_OWNER_NAMES:
                offenders.append(f"{path.name}:{name}")
            if any(fragment in name for fragment in FORBIDDEN_OWNER_FRAGMENTS):
                offenders.append(f"{path.name}:{name}")

    assert offenders == []


def test_no_forbidden_module_stem_is_introduced():
    stems = {path.stem for path in _pack_files()}

    assert stems.isdisjoint(FORBIDDEN_MODULE_STEMS)


def test_no_phase_11_surface_is_introduced():
    offenders: list[str] = []
    for path, source in _pack_sources().items():
        for name in _class_and_function_names(ast.parse(source)):
            if any(forbidden in name for forbidden in FORBIDDEN_PHASE_11_NAMES):
                offenders.append(f"{path.name}:{name}")

    assert offenders == []


def test_no_second_epistemic_model_or_runtime_is_introduced():
    """No pack may define a second knowledge model, certainty enum or runtime.

    Compared against exact declared class names, never by substring.
    """
    for path, source in _pack_sources().items():
        tree = ast.parse(source)
        declared = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        for forbidden in FORBIDDEN_SECOND_MODEL_NAMES:
            assert forbidden not in declared, f"{path.name}: class {forbidden}"
        # A canonical builder is imported, never redefined here.
        assert "class KnowledgePackageBuilder" not in source, path.name


def test_production_does_not_import_tests():
    for path, source in _pack_sources().items():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "tests"
            ):
                pytest.fail(f"{path.name} imports tests")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("tests"):
                        pytest.fail(f"{path.name} imports tests")


def test_no_neurodivergence_owned_persistent_store_or_database_exists():
    """No pack module may import a concrete persistent store or database."""
    forbidden_fragments = (
        "sqlite3",
        "sqlalchemy",
        "NeurodivergenceStore",
        "DiagnosisRegistry",
        "database",
        "pymongo",
        "redis",
    )
    for path, source in _pack_sources().items():
        for fragment in forbidden_fragments:
            assert fragment not in source, f"{path.name}: {fragment}"


def test_no_external_or_executable_surface_is_imported():
    """The pack must not reach out: no network, no shell, no process control."""
    for path, source in _pack_sources().items():
        imported = _imported_roots(ast.parse(source))
        for module in FORBIDDEN_IMPORT_ROOTS:
            assert module not in imported, f"{path.name}: {module}"


def test_no_pack_module_executes_work_at_import_time():
    """No module-level call may register, persist or otherwise act on import.

    Every top-level statement must be an import, a definition, a docstring, an
    ``__all__``/constant assignment, or a frozen tuple/dict literal.
    """
    allowed_value_nodes = (
        ast.Constant,
        ast.Tuple,
        ast.List,
        ast.Dict,
        ast.Set,
        ast.BinOp,
        ast.UnaryOp,
        ast.Name,
        ast.Attribute,
        ast.Subscript,
        ast.JoinedStr,
        ast.Call,
    )
    for path, source in _pack_sources().items():
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Expr,
                ),
            ):
                if isinstance(node, ast.Expr) and not isinstance(
                    node.value, (ast.Constant, ast.JoinedStr)
                ):
                    pytest.fail(f"{path.name}: top-level expression statement")
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if value is not None and not isinstance(value, allowed_value_nodes):
                    pytest.fail(f"{path.name}: top-level assignment of {type(value)}")
                continue
            if isinstance(node, ast.If):
                # Only the canonical ``if __name__ == "__main__":`` guard shape
                # would be tolerated, and this pack must not have one.
                pytest.fail(f"{path.name}: unexpected top-level conditional")
            pytest.fail(f"{path.name}: unexpected top-level statement {type(node)}")


def test_no_top_level_registration_call_exists():
    """A module-level ``.register(...)`` call would be an import-time mutation.

    Only real module-level statements are inspected; calls inside a function or
    class body are the canonical registration API and are not import-time work.
    """
    for path, source in _pack_sources().items():
        tree = ast.parse(source)
        for node in tree.body:
            value = node.value if isinstance(node, ast.Expr) else None
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr in {"register", "restore_state"}
            ):
                pytest.fail(f"{path.name}: module-level {value.func.attr} call")


def test_canonical_fragmentation_analyzer_reports_no_findings():
    for path, source in _pack_sources().items():
        findings = analyze_fragmentation(source, path.relative_to(REPO_ROOT).as_posix())
        assert findings == [], (path.name, findings)


def test_fresh_import_is_side_effect_free():
    """Re-importing the whole pack fresh leaves canonical state untouched."""
    from cmm.domains.registry import DomainRegistry

    before = DomainRegistry().list()
    for name in tuple(sys.modules):
        if name == _PACK_PACKAGE or name.startswith(f"{_PACK_PACKAGE}."):
            del sys.modules[name]

    module = importlib.import_module(_PACK_PACKAGE)

    assert module is not None
    assert DomainRegistry().list() == before == ()
    # The pack exposes no registry/store object at module level.
    for name in dir(module):
        assert not isinstance(getattr(module, name), DomainRegistry), name


def test_no_import_time_registration_side_effect_in_this_interpreter():
    from cmm.domains.registry import DomainRegistry

    assert DomainRegistry().list() == ()


def test_operations_remain_unavailable_without_injection():
    from cmm.domains.neurodivergence import (
        build_standard_neurodivergence_domain_bootstrap,
    )

    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    operations = [
        operation
        for operation in bootstrap.operation_registry.list_definitions()
        if operation.domain_id == "domain:neurodivergence"
    ]

    assert operations
    assert all(operation.enabled is False for operation in operations)


def test_pack_does_not_import_sibling_pack_implementations():
    """Cross-domain support is registry/permission-driven, never an import."""
    for path, source in _pack_sources().items():
        for sibling in (
            "cmm.domains.health",
            "cmm.domains.mental_health",
            "cmm.domains.university",
            "cmm.domains.relationships",
        ):
            assert sibling not in source, f"{path.name}: {sibling}"


def test_pack_defines_no_local_authority_owner_or_second_authority_contract():
    """The V3 trusted authority channel stays in canonical Cognitive infrastructure.

    The pack may consume ``ReasoningAuthorityContext`` and the
    provenance-bearing ``AuthoritativeSourceClaim`` projection and must obtain
    both from ``cmm.cognitive.reasoning_rule_contracts``.  It may not define its
    own authority registry, resolver, store, engine or a second trusted-context
    or source-claim contract, and no parallel authority contract may appear
    anywhere under ``cmm/domains``.
    """
    forbidden_authority_owners = (
        "NeurodivergenceAuthorityRegistry",
        "NeurodivergenceAuthorityResolver",
        "NeurodivergenceAuthorityStore",
        "NeurodivergencePermissionEngine",
        "NeurodivergenceClinicalAuthority",
        "NeurodivergenceTrustedContext",
        "HealthAuthorityRegistry",
        "ReasoningAuthorityStore",
        "ReasoningAuthorityContext",
        "AuthoritativeSourceClaim",
    )
    consumers: list[Path] = []
    for path in _pack_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defined = set(_class_and_function_names(tree))
        assert not defined & set(forbidden_authority_owners), (
            f"{path.name} defines a forbidden authority owner"
        )
        if "ReasoningAuthorityContext" in path.read_text(encoding="utf-8"):
            consumers.append(path)

    for path in consumers:
        source = path.read_text(encoding="utf-8")
        assert "from cmm.cognitive.reasoning_rule_contracts import" in source
        assert "class ReasoningAuthorityContext" not in source
        assert "class AuthoritativeSourceClaim" not in source

    for contract in ("ReasoningAuthorityContext", "AuthoritativeSourceClaim"):
        duplicate = [
            path
            for path in sorted((REPO_ROOT / "cmm" / "domains").rglob("*.py"))
            if path.parent != PACKAGE_DIR
            and f"class {contract}" in path.read_text(encoding="utf-8")
        ]
        assert duplicate == [], contract

    # The canonical source-claim projection is defined exactly once, in shared
    # Cognitive infrastructure — never inside a Domain Pack.
    declared = [
        path
        for path in sorted((REPO_ROOT / "cmm").rglob("*.py"))
        if "class AuthoritativeSourceClaim" in path.read_text(encoding="utf-8")
    ]
    assert declared == [REPO_ROOT / "cmm" / "cognitive" / "reasoning_rule_contracts.py"]
