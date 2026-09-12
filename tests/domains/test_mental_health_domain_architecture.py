"""Phase 10.52 — Mental Health Domain architecture / adversarial gate.

Detects forbidden fragmentation of the Mental Health Domain Pack and proves the
pack introduces no parallel infrastructure, no Phase 10.53 production code, no
Phase 11 surface, and no import-time side effects.

Reuses the canonical Phase 10.39 fragmentation analyzer
(``cmm.domains.validation_fragmentation``) instead of building a new scanner.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from cmm.domains.validation_fragmentation import analyze_fragmentation

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = REPO_ROOT / "cmm" / "domains" / "mental_health"

#: Production class/function names that must never exist in this pack.
FORBIDDEN_OWNER_NAMES = (
    "MentalHealthRegistry",
    "MentalHealthLoader",
    "MentalHealthResolver",
    "MentalHealthComposer",
    "MentalHealthRuntime",
    "MentalHealthEngine",
    "MentalHealthStore",
    "MentalHealthMemory",
    "MentalHealthMemoryStore",
    "MentalHealthKnowledgeGraph",
    "MentalHealthPlanner",
    "MentalHealthWorkflowEngine",
    "MentalHealthPermissionEngine",
    "MentalHealthPrivacyEngine",
    "MentalHealthTraceStore",
    "MentalHealthValidationEngine",
    "MentalHealthSafetyEngine",
    "MentalHealthCrisisEngine",
    "TherapyHistoryStore",
    "MentalHealthModelRouter",
    "MentalHealthModelGateway",
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

#: Sanctioned pack modules (the approved package boundary).
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

#: Phase 11 surfaces that Phase 10.52 must not introduce.
FORBIDDEN_PHASE_11_NAMES = (
    "CommunicationProfile",
    "ResponseRenderer",
    "ModelGateway",
    "ProviderRegistry",
    "ApplicationUI",
)


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


def test_package_boundary_matches_the_approved_structure():
    modules = {path.name for path in _pack_files()}
    assert modules == APPROVED_MODULES


def test_no_forbidden_parallel_owner_class_or_function_exists():
    offenders: list[str] = []
    for path, source in _pack_sources().items():
        for name in _class_and_function_names(ast.parse(source)):
            if name in FORBIDDEN_OWNER_NAMES:
                offenders.append(f"{path.name}:{name}")
            if any(
                forbidden in name
                for forbidden in (
                    "MentalHealthRegistry",
                    "MentalHealthLoader",
                    "MentalHealthResolver",
                    "MentalHealthRuntime",
                    "MentalHealthEngine",
                    "MentalHealthStore",
                    "MentalHealthPlanner",
                    "MentalHealthPrivacyEngine",
                    "MentalHealthPermissionEngine",
                    "MentalHealthSafetyEngine",
                    "MentalHealthCrisisEngine",
                    "TherapyHistoryStore",
                )
            ):
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


def test_no_phase_10_53_neurodivergence_package_exists():
    assert not (REPO_ROOT / "cmm" / "domains" / "neurodivergence").exists()
    for path, source in _pack_sources().items():
        assert "cmm.domains.neurodivergence" not in source, path.name


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


def test_no_mental_health_owned_persistent_store_exists():
    """No pack module may import a concrete persistent store or database."""
    forbidden_fragments = (
        "sqlite3",
        "sqlalchemy",
        "MentalHealthStore",
        "TherapyHistoryStore",
        "database",
    )
    for path, source in _pack_sources().items():
        for fragment in forbidden_fragments:
            assert fragment not in source, f"{path.name}: {fragment}"


def test_no_second_knowledge_package_builder_or_benchmark_runtime_exists():
    for path, source in _pack_sources().items():
        assert "class KnowledgePackageBuilder" not in source, path.name
        assert "BenchmarkRunner" not in source, path.name
        assert "QualityEvaluatorRuntime" not in source, path.name


def test_canonical_fragmentation_analyzer_reports_no_findings():
    for path, source in _pack_sources().items():
        findings = analyze_fragmentation(source, path.relative_to(REPO_ROOT).as_posix())
        assert findings == [], (path.name, findings)


def test_fresh_import_is_side_effect_free():
    """Importing the package must not register, persist, or touch the network."""
    probe = (
        "import sys\n"
        "import cmm.domains.mental_health  # noqa: F401\n"
        "loaded = any(\n"
        "    name.startswith('cmm.domains.mental_health') for name in sys.modules\n"
        ")\n"
        "assert loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr

    # A second, isolated process proves no global registry was mutated.
    registry_probe = (
        "from cmm.domains.registry import DomainRegistry\n"
        "import cmm.domains.mental_health  # noqa: F401\n"
        "registry = DomainRegistry()\n"
        "assert registry.list() == ()\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", registry_probe],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr


def test_operations_remain_unavailable_without_injection():
    from cmm.domains.mental_health import (
        build_standard_mental_health_domain_bootstrap,
    )

    bootstrap = build_standard_mental_health_domain_bootstrap()
    mental_health_operations = [
        operation
        for operation in bootstrap.operation_registry.list_definitions()
        if operation.domain_id == "domain:mental-health"
    ]
    assert mental_health_operations
    assert all(operation.enabled is False for operation in mental_health_operations)
