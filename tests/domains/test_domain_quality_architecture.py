"""Phase 10.48 — architecture and no-execution guards.

These guards protect the Phase 10.48 boundary: declarative, domain-owned quality
policy plus deterministic aggregation only. They are AST-based rather than
prose-based, so documentation that *describes* prohibited behaviour does not
trip them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOMAINS_DIR = _REPO_ROOT / "cmm" / "domains"

APPROVED_PUBLIC_API = (
    "DomainQualityAssessment",
    "DomainQualityHumanReviewResult",
    "DomainQualityMetric",
    "DomainQualityMetricResult",
    "assess_domain_quality",
    "build_domain_quality_metric_result",
    "export_domain_quality_assessment",
    "import_domain_quality_assessment",
)

# Internal Phase 10.48 helpers that must never become public API.
INTERNAL_QUALITY_HELPERS = (
    "_canonical_decimal_text",
    "_decimal_from_dict",
    "_is_reserved_authority_key",
    "_normalize_key",
    "_reject_reserved_authority_keys",
    "_require_quality_metadata",
    "_weighted_mean",
)

FORBIDDEN_AUTHORITY_SYMBOLS = frozenset(
    {
        "DomainQualityRegistry",
        "DomainQualityLoader",
        "DomainQualityResolver",
        "DomainQualityStore",
        "DomainQualityRuntime",
        "DomainQualityEngine",
        "DomainBenchmarkRunner",
        "BenchmarkRunner",
        "EvaluatorRegistry",
        "EvaluatorRunner",
        "EvaluatorResolver",
        "ModelComparison",
        "ModelComparator",
        "ModelRanker",
        "ModelLeaderboard",
        "RoutingEvidenceEngine",
        "ModelGateway",
        "ProviderAdapter",
        "ModelProviderClient",
    }
)

FORBIDDEN_EXECUTION_FUNCTIONS = frozenset(
    {
        "execute_benchmark",
        "run_benchmark",
        "schedule_benchmark",
        "execute_evaluator",
        "run_evaluator",
        "resolve_evaluator",
        "discover_evaluators",
        "invoke_model",
        "call_model",
        "invoke_provider",
        "compare_models",
        "rank_models",
        "detect_regression",
        "route_request",
        "select_model",
    }
)

FORBIDDEN_IMPORT_PREFIXES = (
    "cmm.agent_runtime",
    "cmm.cognitive",
    "cmm.domains.providers",
    "cmm.domains.model_gateway",
    "cmm.providers",
    "cmm.gateway",
)

FORBIDDEN_IMPORT_NAMES = frozenset(
    {
        "ModelGateway",
        "ProviderRegistry",
        "ProviderAdapter",
        "ModelRouter",
        "DomainMetricsCalculator",
        "DomainMetricsSnapshot",
        "DomainMetricMeasurement",
    }
)

FORBIDDEN_NETWORK_MODULES = frozenset(
    {"subprocess", "socket", "requests", "httpx", "urllib"}
)

OBSERVABILITY_ONLY_TYPES = frozenset(
    {"DomainMetricsCalculator", "DomainMetricsSnapshot", "DomainMetricMeasurement"}
)

# Markers reported by the guard, mirroring the phase evidence vocabulary.
REQUIRED_ABSENCE_MARKERS = {
    "DOMAIN_QUALITY_REGISTRY": ("DomainQualityRegistry",),
    "DOMAIN_QUALITY_LOADER": ("DomainQualityLoader",),
    "DOMAIN_QUALITY_RESOLVER": ("DomainQualityResolver",),
    "DOMAIN_QUALITY_STORE": ("DomainQualityStore",),
    "DOMAIN_QUALITY_RUNTIME": ("DomainQualityRuntime",),
    "DOMAIN_QUALITY_ENGINE": ("DomainQualityEngine",),
    "BENCHMARK_RUNNER": ("BenchmarkRunner", "DomainBenchmarkRunner"),
    "EVALUATOR_EXECUTION": (
        "EvaluatorRegistry",
        "EvaluatorRunner",
        "EvaluatorResolver",
    ),
    "MODEL_EXECUTION": ("ModelGateway", "ModelProviderClient"),
    "PROVIDER_EXECUTION": ("ProviderAdapter",),
    "MODEL_COMPARISON": ("ModelComparison", "ModelComparator"),
    "MODEL_RANKING": ("ModelRanker", "ModelLeaderboard"),
    "ROUTING_EVIDENCE_ENGINE": ("RoutingEvidenceEngine",),
}


def _phase_10_48_production_modules() -> list[Path]:
    modules = [_DOMAINS_DIR / "quality_contracts.py"]
    modules.extend(sorted(_DOMAINS_DIR.glob("*/quality_metrics.py")))
    return [path for path in modules if path.exists()]


def _iter_ast_nodes(paths: list[Path]) -> list[tuple[Path, ast.AST]]:
    nodes: list[tuple[Path, ast.AST]] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        nodes.extend((path, node) for node in ast.walk(tree))
    return nodes


def _declared_symbols(paths: list[Path]) -> set[str]:
    found: set[str] = set()
    for _path, node in _iter_ast_nodes(paths):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            found.add(node.name)
    return found


def _imported_modules_and_names(paths: list[Path]) -> list[tuple[Path, str, str]]:
    imports: list[tuple[Path, str, str]] = []
    for path, node in _iter_ast_nodes(paths):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((path, alias.name, alias.asname or alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append((path, module, alias.name))
    return imports


# ── Public surface ────────────────────────────────────────────────────────────


def test_public_api_exposes_exactly_the_approved_quality_surface() -> None:
    from cmm import domains

    for name in APPROVED_PUBLIC_API:
        assert hasattr(domains, name), f"missing approved export {name}"
        assert name in domains.__all__, f"{name} must be in cmm.domains.__all__"


def test_public_api_does_not_export_internal_helpers() -> None:
    from cmm import domains

    for name in INTERNAL_QUALITY_HELPERS:
        assert name not in domains.__all__


def test_public_api_keeps_earlier_phase_exports() -> None:
    from cmm import domains

    for name in (
        "DomainDefinition",
        "DomainModelPolicy",
        "DomainBenchmarkCase",
        "DomainBenchmarkSuite",
        "DomainRegistry",
    ):
        assert name in domains.__all__


# ── No parallel quality infrastructure / no execution ─────────────────────────


def test_required_absence_markers_are_all_absent() -> None:
    declared = _declared_symbols(_phase_10_48_production_modules())

    for marker, symbols in REQUIRED_ABSENCE_MARKERS.items():
        present = sorted(symbol in declared for symbol in symbols)
        assert not any(present), (
            f"{marker}=PRESENT: {[s for s in symbols if s in declared]}"
        )


def test_phase_10_48_declares_no_forbidden_authority_symbols() -> None:
    declared = _declared_symbols(_phase_10_48_production_modules())
    offenders = sorted(declared & FORBIDDEN_AUTHORITY_SYMBOLS)

    assert offenders == []


def test_phase_10_48_declares_no_execution_functions() -> None:
    declared = _declared_symbols(_phase_10_48_production_modules())
    offenders = sorted(declared & FORBIDDEN_EXECUTION_FUNCTIONS)

    assert offenders == []


def test_phase_10_48_imports_no_execution_infrastructure() -> None:
    offenders: list[str] = []
    for path, module, name in _imported_modules_and_names(
        _phase_10_48_production_modules()
    ):
        if (
            module.startswith(FORBIDDEN_IMPORT_PREFIXES)
            or module in FORBIDDEN_NETWORK_MODULES
        ):
            offenders.append(f"{path}:{module}")
        if name in FORBIDDEN_IMPORT_NAMES:
            offenders.append(f"{path}:{name}")

    assert offenders == []


def test_phase_10_48_does_not_import_observability_calculator_types() -> None:
    offenders: list[str] = []
    for path, _module, name in _imported_modules_and_names(
        _phase_10_48_production_modules()
    ):
        if name in OBSERVABILITY_ONLY_TYPES:
            offenders.append(f"{path}:{name}")

    assert offenders == []


def test_phase_10_48_never_references_observability_types_in_code() -> None:
    offenders: list[str] = []
    for path, node in _iter_ast_nodes(_phase_10_48_production_modules()):
        if isinstance(node, ast.Name) and node.id in OBSERVABILITY_ONLY_TYPES:
            offenders.append(f"{path}:{node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in OBSERVABILITY_ONLY_TYPES:
            offenders.append(f"{path}:{node.attr}")

    assert offenders == []


def test_phase_10_48_performs_no_process_or_network_execution() -> None:
    offenders: list[str] = []
    for path, node in _iter_ast_nodes(_phase_10_48_production_modules()):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {
                "eval",
                "exec",
                "compile",
                "open",
            }:
                offenders.append(f"{path}:{func.id}")
            elif (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id in FORBIDDEN_NETWORK_MODULES
            ):
                offenders.append(f"{path}:{func.value.id}.{func.attr}")

    assert offenders == []


# ── Frozen Phase 10.47 / observability boundaries ─────────────────────────────


def test_benchmark_contracts_define_no_quality_types() -> None:
    source = (_DOMAINS_DIR / "benchmark_contracts.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    declared = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert declared.isdisjoint(APPROVED_PUBLIC_API)
    assert "DomainQualityMetric" not in declared


@pytest.mark.parametrize(
    "forbidden",
    ("weight", "minimum_score", "blocking", "aggregate_score", "quality_metrics"),
)
def test_benchmark_case_annotations_remain_unweighted(forbidden: str) -> None:
    source = (_DOMAINS_DIR / "benchmark_contracts.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    annotations: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "DomainBenchmarkCase":
            annotations = {
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            }

    assert "evaluation_criteria" in annotations
    assert forbidden not in annotations


def test_kernel_has_no_cmm_domains_dependency() -> None:
    kernel = _REPO_ROOT / "kernel"
    offenders: list[str] = []
    for path in sorted(kernel.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.startswith("cmm.domains") for alias in node.names):
                    offenders.append(str(path))
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "cmm.domains"
            ):
                offenders.append(str(path))

    assert offenders == []


def test_quality_contracts_has_no_provider_or_runtime_imports() -> None:
    contracts = _DOMAINS_DIR / "quality_contracts.py"
    offenders: list[str] = []
    for path, module, name in _imported_modules_and_names([contracts]):
        if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
            offenders.append(f"{path}:{module}")
        if name in FORBIDDEN_IMPORT_NAMES:
            offenders.append(f"{path}:{name}")

    assert offenders == []
