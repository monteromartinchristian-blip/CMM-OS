"""Phase 10.47 — architecture guards for Domain benchmark assets.

These guards are intentionally narrow: they protect the Phase 10.47 boundary
(no benchmark runtime/registry, no model/provider authority, no quality
weighting attached to benchmark assets, no reverse dependency) without banning
unrelated pre-existing Agent Runtime evaluation infrastructure.

Phase 10.48 introduces the canonical `DomainQualityMetric` type in
``cmm/domains/quality_contracts.py``. That type is owned by the quality layer,
not by benchmark assets; the boundary this module protects is that benchmark
sources never gain quality weighting.
"""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOMAINS_DIR = _REPO_ROOT / "cmm" / "domains"

_FORBIDDEN_PRODUCTION_NAMES = (
    "DomainBenchmarkRegistry",
    "DomainBenchmarkRunner",
    "BenchmarkExecutionEngine",
    "DomainBenchmarkRuntime",
    "DomainBenchmarkScheduler",
    "BenchmarkWorker",
    "BenchmarkJobStore",
    "BenchmarkResultRepository",
    "BenchmarkLeaderboard",
    "ModelBenchmarkRouter",
    "BenchmarkProviderAdapter",
    "BenchmarkModelClient",
)

_FORBIDDEN_BENCHMARK_IMPORTS = (
    "ModelRouter",
    "OutcomeEvaluationEngine",
    "ProviderRegistry",
    "model_router",
    "provider_client",
)

_FORBIDDEN_CONTRACT_FIELDS = (
    "candidate_models",
    "candidate_providers",
    "preferred_models",
    "preferred_providers",
    "prohibited_models",
    "prohibited_providers",
    "model_id",
    "provider_id",
    "routing_weight",
    "weight",
    "minimum_score",
    "blocking",
    "aggregate_score",
)

_FORBIDDEN_QUALITY_TOKENS = (
    "DomainQualityMetric",
    "minimum_score",
    "aggregate_score",
)


def _benchmark_module_paths() -> list[Path]:
    paths = [_DOMAINS_DIR / "benchmark_contracts.py"]
    paths.extend(sorted(_DOMAINS_DIR.glob("*/benchmarks.py")))
    return paths


def _production_python_files() -> list[Path]:
    return sorted(_DOMAINS_DIR.rglob("*.py"))


def test_no_benchmark_runtime_or_registry_classes_exist() -> None:
    offenders: list[str] = []
    for path in _production_python_files():
        source = path.read_text(encoding="utf-8")
        for name in _FORBIDDEN_PRODUCTION_NAMES:
            if re.search(rf"^\s*class\s+{name}\b", source, re.MULTILINE):
                offenders.append(f"{path}:{name}")

    assert offenders == []


def test_benchmark_modules_do_not_import_runtime_or_provider_infrastructure() -> None:
    offenders: list[str] = []
    for path in _benchmark_module_paths():
        source = path.read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            for token in _FORBIDDEN_BENCHMARK_IMPORTS:
                if token in stripped:
                    offenders.append(f"{path}:{stripped}")

    assert offenders == []


def test_benchmark_contracts_expose_no_forbidden_fields() -> None:
    case_fields = {f.name for f in fields(DomainBenchmarkCase)}
    suite_fields = {f.name for f in fields(DomainBenchmarkSuite)}

    for forbidden in _FORBIDDEN_CONTRACT_FIELDS:
        assert forbidden not in case_fields
        assert forbidden not in suite_fields


def test_no_phase_10_48_quality_tokens_in_benchmark_sources() -> None:
    offenders: list[str] = []
    for path in _benchmark_module_paths():
        source = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_QUALITY_TOKENS:
            if token in source:
                offenders.append(f"{path}:{token}")

    assert offenders == []


def test_public_api_exposes_no_execution_concepts() -> None:
    from cmm import domains

    for name in _FORBIDDEN_PRODUCTION_NAMES:
        assert name not in domains.__all__


def test_kernel_and_agent_runtime_have_no_reverse_benchmark_dependency() -> None:
    roots = [_REPO_ROOT / "kernel", _REPO_ROOT / "cmm" / "agent_runtime"]
    pattern = re.compile(r"^\s*(from|import)\s+.*benchmark")
    offenders: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            for line in source.splitlines():
                if pattern.match(line):
                    offenders.append(f"{path}:{line.strip()}")

    assert offenders == []
