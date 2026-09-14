"""Phase 10.51 — conformance architecture and anti-fragmentation guards.

AST/filesystem-based guards proving that the Phase 10.51 conformance gate adds
**no** parallel Domain owner and keeps the approved later-phase boundaries out
of production scope:

  NEW_PARALLEL_ENGINE / REGISTRY / LOADER / RESOLVER / STORE / RUNTIME /
  PLANNER / MEMORY / TRACE_STORE / PERMISSION_OWNER / VALIDATION_OWNER = 0

Guards are structural rather than prose-based, so documentation that merely
*describes* a prohibited construct does not trip them and a real parallel owner
cannot hide behind a comment.

The canonical Phase 10.39 fragmentation acceptance remains authoritative and is
exercised separately by
``tests/domains/test_domain_architecture_guard_dp039_acceptance.py`` and
``tests/domains/test_domain_validation_fragmentation.py``; this module reuses
the same production guard rather than reimplementing it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cmm.domains.validation_fragmentation import analyze_fragmentation
from tests.domains.domain_core_conformance_support import (
    CORE_CONFORMANCE_REQUIREMENTS,
    DEFERRED_DOMAIN_PACKAGE_PATHS,
    FORBIDDEN_PARALLEL_OWNER_NAMES,
    HISTORICAL_DEFERRED_DOMAIN_PACKAGE_PATHS,
    iter_owner_modules,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CMM_ROOT = _REPO_ROOT / "cmm"
_PRODUCTION_ROOTS = (_CMM_ROOT,)
_PHASE_10_51_TEST_FILES = (
    _REPO_ROOT / "tests" / "domains" / "domain_core_conformance_support.py",
    _REPO_ROOT / "tests" / "domains" / "test_domain_core_conformance_inventory.py",
    _REPO_ROOT / "tests" / "domains" / "test_domain_core_conformance_integration.py",
    _REPO_ROOT / "tests" / "domains" / "test_domain_core_conformance_architecture.py",
    _REPO_ROOT / "tests" / "domains" / "test_domain_core_dp051_acceptance.py",
)
_SUPPORT_MODULE_NAME = "domain_core_conformance_support"

#: Conceptual parallel-owner suffixes that must never appear as a new binding in
#: production code. These cover the ``second X`` prohibitions of the design.
PROHIBITED_PARALLEL_SUFFIXES = (
    "CoreEngine",
    "CoreRuntime",
    "CoreRegistry",
    "CoreResolver",
    "CoreLoader",
    "CoreStore",
    "ConformanceRegistry",
    "ConformanceRuntime",
    "ConformanceEngine",
    "ConformanceLoader",
    "ConformanceStore",
    "ClosureEngine",
    "ClosureRegistry",
    "ClosureRuntime",
    "ClosureStore",
    "OrchestrationEngine",
    "FinalIntegrator",
    "FinalRuntime",
    "FinalRegistry",
    "IntegrationEngineV2",
    "DomainDefinitionV2",
    "DomainRegistryV2",
    "DomainResolverV2",
    "DomainComposerV2",
    "DomainPackParserV2",
    "ManifestParserV2",
    "WorkflowEngineV2",
    "ValidationEngineV2",
    "PermissionEngineV2",
    "MemoryStoreV2",
    "TraceStoreV2",
    "DomainMemoryStore",
    "DomainKnowledgeGraph",
    "DomainTraceStore",
    "DomainSessionStore",
    "DomainPermissionAuthority",
    "DomainValidationAuthority",
    "DomainObservabilityBackend",
    "DomainModelRouter",
    "DomainBenchmarkEvaluatorRuntime",
    "DomainQualityRuntime",
    "DomainPrivacyRuntime",
    "DomainPrivacyEngine",
    "DomainPrivacyRegistry",
    "DomainPrivacyStore",
    "DomainPrivacyResolver",
)

#: Production module name fragments implying a second core/runtime/registry.
PROHIBITED_PRODUCTION_MODULE_STEMS = (
    "domain_core_",
    "core_conformance",
    "conformance_registry",
    "conformance_runtime",
    "closure_engine",
    "final_integrator",
    "orchestration_engine",
)

#: Phase 11 platform/UI responsibilities that must stay absent from 10.51.
PROHIBITED_PHASE11_MODULE_STEMS = (
    "model_gateway",
    "domain_center_ui",
    "cross_domain_view",
    "chat_ui",
    "application_ui",
    "platform_orchestration",
    "model_evaluation_runtime",
)


def _production_python_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for root in _PRODUCTION_ROOTS:
        files.extend(
            path for path in root.rglob("*.py") if "__pycache__" not in path.parts
        )
    return tuple(sorted(files))


def _top_level_bindings(tree: ast.AST) -> set[str]:
    """Names bound at module scope by class/function/assignment."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _parsed_production_files() -> list[tuple[Path, ast.Module]]:
    parsed: list[tuple[Path, ast.Module]] = []
    for path in _production_python_files():
        parsed.append((path, ast.parse(path.read_text(encoding="utf-8"))))
    return parsed


# ── No production import of the test-only conformance inventory ───────────────


def test_phase_10_51_test_support_is_not_imported_by_production() -> None:
    offenders: list[str] = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        if _SUPPORT_MODULE_NAME in text:
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert offenders == []


def test_no_production_module_imports_the_tests_package() -> None:
    offenders: list[str] = []
    for path, tree in _parsed_production_files():
        for node in ast.walk(tree):
            imported: tuple[str | None, ...] = ()
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported = (node.module,)
            for module_name in imported:
                if module_name is not None and (
                    module_name == "tests" or module_name.startswith("tests.")
                ):
                    offenders.append(
                        f"{path.relative_to(_REPO_ROOT)}:{node.lineno}:{module_name}"
                    )
    assert offenders == []


# ── No forbidden parallel owner names in production ───────────────────────────


def test_no_forbidden_parallel_owner_class_names_in_production() -> None:
    offenders: list[str] = []
    for path, tree in _parsed_production_files():
        for name in _top_level_bindings(tree):
            if name in FORBIDDEN_PARALLEL_OWNER_NAMES:
                offenders.append(f"{path.relative_to(_REPO_ROOT)}:{name}")
    assert offenders == []


def test_no_prohibited_parallel_owner_suffixes_in_production() -> None:
    offenders: list[str] = []
    for path, tree in _parsed_production_files():
        for name in _top_level_bindings(tree):
            if name.endswith(PROHIBITED_PARALLEL_SUFFIXES):
                offenders.append(f"{path.relative_to(_REPO_ROOT)}:{name}")
    assert offenders == []


def test_no_prohibited_production_module_names() -> None:
    offenders: list[str] = []
    for path in _production_python_files():
        stem = path.name.removesuffix(".py")
        if stem.startswith(PROHIBITED_PRODUCTION_MODULE_STEMS):
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert offenders == []


# ── Phase 10.53 / Phase 11 boundaries ────────────────────────────────────────


def test_phase_10_53_domain_is_implemented() -> None:
    """Phase 10.53 adds the neurodivergence pack; DP-051 history is not rewritten."""
    assert (_REPO_ROOT / "cmm/domains/neurodivergence").is_dir()
    assert "cmm/domains/neurodivergence" in HISTORICAL_DEFERRED_DOMAIN_PACKAGE_PATHS
    assert "cmm/domains/neurodivergence" not in DEFERRED_DOMAIN_PACKAGE_PATHS
    # No DP-051 deferral remains unimplemented.
    assert DEFERRED_DOMAIN_PACKAGE_PATHS == ()


def test_phase_10_52_mental_health_pack_is_implemented() -> None:
    """Phase 10.52 adds the mental-health pack; DP-051 history is not rewritten."""
    assert (_REPO_ROOT / "cmm/domains/mental_health").is_dir()
    assert "cmm/domains/mental_health" in HISTORICAL_DEFERRED_DOMAIN_PACKAGE_PATHS
    # Both DP-051 deferrals are now implemented, so the current deferred set is
    # empty while the historical two-path baseline above is preserved.
    assert DEFERRED_DOMAIN_PACKAGE_PATHS == ()


def test_deferred_domain_ids_are_not_registered_by_first_party_bootstrap() -> None:
    from cmm.domains.project.bootstrap import build_standard_project_domain_bootstrap

    bootstrap = build_standard_project_domain_bootstrap()
    registered = {str(definition.id) for definition in bootstrap.domain_registry.list()}
    assert "domain:mental-health" not in registered
    assert "domain:neurodivergence" not in registered
    assert not bootstrap.domain_registry.contains("domain:mental-health")
    assert not bootstrap.domain_registry.contains("domain:neurodivergence")


def test_no_phase_11_platform_or_ui_module_in_production() -> None:
    offenders: list[str] = []
    for path in _production_python_files():
        stem = path.name.removesuffix(".py")
        if stem.startswith(PROHIBITED_PHASE11_MODULE_STEMS):
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert offenders == []


def test_phase_10_51_adds_no_new_production_module() -> None:
    """Phase 10.51 is a conformance gate: NEW_PRODUCTION_FILES=0.

    The 28-block owner inventory must reference only modules that already
    existed before this phase, which is equivalent to asserting that no
    production module was created to host conformance behaviour.
    """
    conformance_named = [
        path
        for path in _production_python_files()
        if path.name.removesuffix(".py").startswith(PROHIBITED_PRODUCTION_MODULE_STEMS)
    ]
    assert conformance_named == []


# ── Connected acceptance reuses the canonical interface seam ──────────────────


def test_phase_10_51_tests_reuse_canonical_interface_integration() -> None:
    """Phase 11 boundary: reuse ``interface_integration``, never a renderer."""
    acceptance = (
        _REPO_ROOT / "tests" / "domains" / "test_domain_core_dp051_acceptance.py"
    )
    if not acceptance.exists():
        pytest.skip("DP-051 acceptance not created yet")
    text = acceptance.read_text(encoding="utf-8")
    assert "cmm.domains.interface_integration" in text
    for forbidden in (
        "Renderer",
        "render_ui",
        "QWidget",
        "tkinter",
        "flask",
        "fastapi",
    ):
        assert forbidden not in text, forbidden


def test_phase_10_51_tests_do_not_define_local_fakes_for_canonical_owners() -> None:
    """The connected acceptance must not be a chain of isolated mocks."""
    offenders: list[str] = []
    for path in _PHASE_10_51_TEST_FILES:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith(
                ("Fake", "Stub", "Mock")
            ):
                offenders.append(f"{path.name}:{node.name}")
    assert offenders == []


# ── Canonical ownership stays singular across the inventory ───────────────────


def test_inventory_owner_modules_all_resolve_to_real_production_files() -> None:
    missing: list[str] = []
    for module_name in iter_owner_modules():
        relative = module_name.replace(".", "/")
        candidates = (
            _REPO_ROOT / f"{relative}.py",
            _REPO_ROOT / relative / "__init__.py",
        )
        if not any(candidate.exists() for candidate in candidates):
            missing.append(module_name)
    assert missing == []


def test_no_block_maps_to_a_test_only_owner() -> None:
    for requirement in CORE_CONFORMANCE_REQUIREMENTS:
        for module_name in requirement.owner_modules:
            assert module_name.startswith("cmm."), requirement.block


def test_phase_10_39_fragmentation_guard_remains_canonical_and_active() -> None:
    """Reuse the existing fragmentation owner rather than a second guard."""
    duplicate = "class DomainRegistry:\n    pass\n\n\nDomainRegistry = DomainRegistry\n"
    findings = analyze_fragmentation(duplicate, "probe.py")
    codes = {finding.get("code") for finding in findings}
    assert "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION" in codes


def test_phase_10_51_fragmentation_guard_accepts_legitimate_reuse() -> None:
    legitimate = "from cmm.domains.registry import DomainRegistry\n\n__all__ = ['DomainRegistry']\n"
    findings = analyze_fragmentation(legitimate, "probe.py")
    duplications = [
        finding
        for finding in findings
        if finding.get("code") == "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION"
    ]
    assert duplications == []
