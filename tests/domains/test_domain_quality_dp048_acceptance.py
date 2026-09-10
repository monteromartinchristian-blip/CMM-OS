"""Phase 10.48 — AT-DP-048 Connected Domain Quality Metrics Acceptance.

Scenarios A–J exercise the real canonical Domain infrastructure: first-party
definition builders, ``DomainRegistry``, the official ``ParsedDomainPack`` and
declarative loader paths, real Phase 10.47 benchmark suites, and the real
quality contracts/helpers. No mock substitutes.
"""

from __future__ import annotations

import ast
import copy
import importlib
import json
from dataclasses import fields, replace
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from cmm.domains.contracts import DomainDefinition
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainError,
    DomainSerializationError,
)
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.health.quality_metrics import build_health_quality_metrics
from cmm.domains.identifiers import DomainId
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.pack import DomainPack, ParsedDomainPack
from cmm.domains.quality_contracts import (
    DomainQualityAssessment,
    DomainQualityHumanReviewResult,
    DomainQualityMetric,
    assess_domain_quality,
    build_domain_quality_metric_result,
    export_domain_quality_assessment,
    import_domain_quality_assessment,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.relationships.definition import build_relationships_domain_definition
from cmm.domains.relationships.quality_metrics import (
    build_relationships_quality_metrics,
)

from ._loader_helpers import make_candidate

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOMAINS_DIR = _REPO_ROOT / "cmm" / "domains"

_OBSERVABILITY_TYPES = (
    "DomainMetricMeasurement",
    "DomainMetricsSnapshot",
    "DomainMetricsCalculator",
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _results_for(
    metrics: tuple[DomainQualityMetric, ...],
    *,
    scores: dict[str, Decimal] | None = None,
    default_score: Decimal = Decimal("1.00"),
    confidence: Decimal = Decimal("0.90"),
) -> tuple:
    scores = scores or {}
    return tuple(
        build_domain_quality_metric_result(
            metric,
            score=scores.get(metric.name, default_score),
            evaluator_version="1",
            confidence=confidence,
        )
        for metric in metrics
    )


def _quality_module_paths() -> list[Path]:
    paths = [_DOMAINS_DIR / "quality_contracts.py"]
    paths.extend(sorted(_DOMAINS_DIR.glob("*/quality_metrics.py")))
    return [path for path in paths if path.exists()]


# ── Scenario A — canonical discovery ──────────────────────────────────────────


def test_scenario_a_registry_discovery_exposes_quality_metrics() -> None:
    registry = DomainRegistry()
    registry.register(build_health_domain_definition())

    definition = registry.get_required("domain:health")

    assert definition.quality_metrics == build_health_quality_metrics()
    assert definition.quality_metrics
    assert all(
        metric.domain_id == definition.id for metric in definition.quality_metrics
    )


def test_scenario_a_no_quality_specific_registry_exists() -> None:
    import cmm.domains

    for name in (
        "DomainQualityRegistry",
        "DomainQualityLoader",
        "DomainQualityResolver",
        "DomainQualityStore",
        "DomainQualityRuntime",
        "DomainQualityEngine",
    ):
        assert not hasattr(cmm.domains, name)
        assert name not in cmm.domains.__all__
    assert importlib.util.find_spec("cmm.domains.quality_registry") is None


# ── Scenario B — real declarative round-trip ──────────────────────────────────


def _declarative_payload_for(definition: DomainDefinition) -> dict:
    return {
        "id": definition.id.slug,
        "version": definition.version,
        "name": definition.name,
        "display_name": definition.display_name,
        "description": definition.description,
        "author": "tester",
        "license": "MIT",
        "benchmark_suites": [suite.to_dict() for suite in definition.benchmark_suites],
        "quality_metrics": [metric.to_dict() for metric in definition.quality_metrics],
    }


def test_scenario_b_declarative_loader_preserves_quality_metrics(
    tmp_path: Path,
) -> None:
    source = build_health_domain_definition()
    domain_dir = tmp_path / source.id.slug
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "manifest.json").write_text(
        json.dumps(_declarative_payload_for(source)), encoding="utf-8"
    )
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(),
        registry=DomainRegistry(),
    )

    result = loader.load(make_candidate(domain_dir, source.id.slug, source.version))

    assert result.pack is not None
    assert result.pack.definition.quality_metrics == source.quality_metrics
    assert result.pack.definition.quality_metrics


def test_scenario_b_parsed_pack_declarative_and_from_dict_round_trip() -> None:
    source = build_health_domain_definition()

    declarative = ParsedDomainPack.from_declarative_dict(
        _declarative_payload_for(source)
    )
    assert declarative.definition.quality_metrics == source.quality_metrics

    restored = ParsedDomainPack.from_dict(declarative.to_dict())
    assert restored.definition.quality_metrics == source.quality_metrics


# ── Scenario C — exact Decimal determinism ────────────────────────────────────


def test_scenario_c_high_precision_assessment_is_context_independent() -> None:
    metrics = build_health_quality_metrics()
    scores = {
        "factual-fidelity": Decimal("0.9123456789012345678901234567891"),
        "prudence": Decimal("0.9123456789012345678901234567891"),
        "temporal-correctness": Decimal("0.8123456789012345678901234567891"),
        "privacy-compliance": Decimal("0.9123456789012345678901234567891"),
        "contextual-fidelity": Decimal("0.7123456789012345678901234567891"),
    }
    confidence = Decimal("0.8123456789012345678901234567891")
    results = _results_for(metrics, scores=scores, confidence=confidence)

    assessments: list[DomainQualityAssessment] = []
    payloads: list[bytes] = []
    for precision in (10, 28, 50):
        with localcontext() as ctx:
            ctx.prec = precision
            assessment = assess_domain_quality(metrics, results)
            assessments.append(assessment)
            payloads.append(export_domain_quality_assessment(assessment))

    assert assessments[0] == assessments[1] == assessments[2]
    assert payloads[0] == payloads[1] == payloads[2]

    # Exactness: the aggregate equals the independently computed rational mean,
    # so no operand precision was lost under any context.
    pairs = [(scores[metric.name], metric.weight) for metric in metrics]
    expected = sum(Fraction(score) * Fraction(weight) for score, weight in pairs) / sum(
        Fraction(weight) for _score, weight in pairs
    )
    assert Fraction(assessments[0].aggregate_score) == expected
    assert assessments[0].confidence == confidence
    assert [result.score for result in assessments[0].metric_results] == [
        scores[metric.name] for metric in metrics
    ]

    restored = import_domain_quality_assessment(payloads[0])
    assert restored == assessments[0]
    assert restored.aggregate_score == assessments[0].aggregate_score


# ── Scenario D — non-compensable blocking failure ─────────────────────────────


def test_scenario_d_blocking_failure_cannot_be_compensated() -> None:
    metrics = build_health_quality_metrics()
    prudence = next(metric for metric in metrics if metric.name == "prudence")
    assert prudence.blocking is True
    results = _results_for(
        metrics,
        scores={"prudence": prudence.minimum_score - Decimal("0.01")},
    )

    assessment = assess_domain_quality(metrics, results)

    assert assessment.aggregate_score == Decimal("0.9725")
    assert assessment.aggregate_score > Decimal("0.95")
    assert assessment.blocking_failures == (prudence.id,)
    assert assessment.passed is False


# ── Scenario E — domain differentiation ───────────────────────────────────────


def test_scenario_e_domains_share_contracts_but_differ_in_policy() -> None:
    health = build_health_definition_metrics()
    relationships = build_relationships_quality_metrics()

    assert isinstance(health, tuple) and isinstance(relationships, tuple)
    assert all(isinstance(m, DomainQualityMetric) for m in health + relationships)
    assert {m.id for m in health} != {m.id for m in relationships}
    assert {m.domain_id.slug for m in health} == {"health"}
    assert {m.domain_id.slug for m in relationships} == {"relationships"}
    assert [m.weight for m in health] != [m.weight for m in relationships]
    assert [m.name for m in health] != [m.name for m in relationships]
    for metric in health + relationships:
        assert metric.id.startswith("quality-metric:")
        assert metric.evaluator_id.startswith("evaluator:")
        for segment in (metric.id, metric.evaluator_id):
            assert "model" not in segment
            assert "provider" not in segment


def build_health_definition_metrics() -> tuple[DomainQualityMetric, ...]:
    """Catalog exactly as attached to the real Health definition."""
    return build_health_domain_definition().quality_metrics


# ── Scenario F — human-review preservation ────────────────────────────────────


def test_scenario_f_human_review_evidence_survives_round_trip() -> None:
    metrics = build_health_quality_metrics()
    prudence = next(metric for metric in metrics if metric.name == "prudence")
    review = DomainQualityHumanReviewResult(
        id="quality-review:health:prudence:001",
        schema_version="1",
        status="accepted",
        score=Decimal("0.93"),
        confidence=Decimal("0.98"),
        reviewer_ref="reviewer:human",
        notes=("Prudence requirements preserved.",),
    )
    results = tuple(
        build_domain_quality_metric_result(
            metric,
            score=Decimal("0.95"),
            evaluator_version="1",
            confidence=Decimal("0.90"),
            human_review_results=(review,) if metric.id == prudence.id else (),
        )
        for metric in metrics
    )

    assessment = assess_domain_quality(metrics, results)
    restored = import_domain_quality_assessment(
        export_domain_quality_assessment(assessment)
    )

    assert restored == assessment
    preserved = next(
        result for result in restored.metric_results if result.metric_id == prudence.id
    )
    assert preserved.human_review_results == (review,)


# ── Scenario G — Phase 10.47 coexistence ──────────────────────────────────────


def test_scenario_g_benchmark_suites_and_quality_metrics_coexist() -> None:
    for definition in (
        build_health_domain_definition(),
        build_relationships_domain_definition(),
    ):
        assert definition.benchmark_suites
        assert definition.quality_metrics

        restored = DomainDefinition.from_dict(definition.to_dict())

        assert restored.benchmark_suites == definition.benchmark_suites
        assert restored.quality_metrics == definition.quality_metrics

    # Canonical pack round-trip on a coherent real first-party definition.
    definition = build_health_domain_definition()
    parsed = ParsedDomainPack(
        definition=definition,
        manifest=_manifest_for(definition),
    )
    pack_restored = ParsedDomainPack.from_dict(parsed.to_dict())

    assert pack_restored.definition.benchmark_suites == definition.benchmark_suites
    assert pack_restored.definition.quality_metrics == definition.quality_metrics


def test_scenario_g_benchmark_case_remains_unweighted() -> None:
    from cmm.domains.benchmark_contracts import DomainBenchmarkCase

    annotations = {field.name for field in fields(DomainBenchmarkCase)}

    assert "evaluation_criteria" in annotations
    for forbidden in ("weight", "minimum_score", "blocking", "aggregate_score"):
        assert forbidden not in annotations
    for quality_type in ("DomainQualityMetric", "DomainQualityMetricResult"):
        assert quality_type not in annotations


def _manifest_for(definition: DomainDefinition):
    from cmm.domains.enums import DomainPackKind
    from cmm.domains.manifest import (
        DomainComponentReference,
        DomainManifest,
        DomainPermissionReference,
    )

    def component(component_id: str) -> DomainComponentReference:
        return DomainComponentReference(id=component_id, path=f"{component_id}.py")

    return DomainManifest(
        id=definition.manifest_id,
        domain_id=definition.id,
        schema_version="1",
        package_version=definition.version,
        pack_kind=DomainPackKind.INTERNAL,
        resources=tuple(component(c) for c in definition.resources),
        rules=tuple(component(c) for c in definition.rules),
        operations=tuple(component(c) for c in definition.operations),
        workflows=tuple(component(c) for c in definition.workflows),
        validators=tuple(component(c) for c in definition.validators),
        permissions=(
            DomainPermissionReference(
                policy="permissions.py",
                required_permissions=definition.permissions,
            )
            if definition.permissions
            else None
        ),
        dependencies=definition.dependencies,
        conflicts=definition.conflicts,
    )


# ── Scenario H — fail-closed policy binding ───────────────────────────────────


def _health_policy_and_results() -> tuple[tuple, tuple]:
    metrics = build_health_quality_metrics()
    return metrics, _results_for(metrics)


def test_scenario_h_missing_metric_result_fails_closed() -> None:
    metrics, results = _health_policy_and_results()
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality(metrics, results[:-1])


def test_scenario_h_extra_metric_result_fails_closed() -> None:
    metrics, results = _health_policy_and_results()
    extra_metric = DomainQualityMetric(
        id="quality-metric:health:unexpected",
        domain_id=DomainId(slug="health"),
        schema_version="1",
        version="1",
        name="unexpected",
        weight=Decimal("0.1"),
        evaluator_id="evaluator:unexpected",
        minimum_score=Decimal("0.5"),
    )
    extra = build_domain_quality_metric_result(
        extra_metric,
        score=Decimal(1),
        evaluator_version="1",
        confidence=Decimal(1),
    )
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality(metrics, results + (extra,))


def test_scenario_h_wrong_domain_fails_closed() -> None:
    metrics, results = _health_policy_and_results()
    relationships = build_relationships_quality_metrics()
    foreign = _results_for(relationships)[0]
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality(metrics, (foreign,) + results[1:])
    with pytest.raises(DomainContractValidationError):
        replace(foreign, domain_id=DomainId(slug="health"))


@pytest.mark.parametrize(
    "field,value",
    (
        ("metric_version", "9"),
        ("metric_name", "other"),
        ("weight", Decimal("0.5")),
        ("minimum_score", Decimal("0.1")),
        ("blocking", False),
        ("evaluator_id", "evaluator:other"),
    ),
)
def test_scenario_h_altered_policy_snapshot_fails_closed(
    field: str, value: object
) -> None:
    metrics, results = _health_policy_and_results()
    corrupted = replace(results[0], **{field: value})

    with pytest.raises(DomainContractValidationError):
        assess_domain_quality(metrics, (corrupted,) + results[1:])


def test_scenario_h_altered_derived_state_fails_closed() -> None:
    metrics, results = _health_policy_and_results()
    assessment = assess_domain_quality(metrics, results)

    payload = assessment.to_dict()
    payload["aggregate_score"] = "0.123"
    with pytest.raises(DomainError):
        import_domain_quality_assessment(json.dumps(payload).encode("utf-8"))


def test_scenario_h_malformed_nested_human_review_notes_fail_closed() -> None:
    metrics = build_health_quality_metrics()
    prudence = next(metric for metric in metrics if metric.name == "prudence")

    review = DomainQualityHumanReviewResult(
        id="quality-review:health:prudence:malformed",
        schema_version="1",
        status="accepted",
        notes=("valid",),
    )

    results = tuple(
        build_domain_quality_metric_result(
            metric,
            score=Decimal("0.95"),
            evaluator_version="1",
            confidence=Decimal("0.90"),
            human_review_results=(review,) if metric.id == prudence.id else (),
        )
        for metric in metrics
    )

    assessment = assess_domain_quality(metrics, results)
    payload = assessment.to_dict()

    prudence_payload = next(
        result
        for result in payload["metric_results"]
        if result["metric_id"] == prudence.id
    )
    prudence_payload["human_review_results"][0]["notes"] = "not-a-list"

    with pytest.raises(DomainSerializationError):
        DomainQualityAssessment.from_dict(payload)


# ── Scenario I — observability isolation ──────────────────────────────────────


def test_scenario_i_quality_path_never_references_observability_types() -> None:
    for path in _quality_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id not in _OBSERVABILITY_TYPES, f"{path}:{node.id}"
            elif isinstance(node, ast.Attribute):
                assert node.attr not in _OBSERVABILITY_TYPES, f"{path}:{node.attr}"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "") != "cmm.domains.observability_metrics"


def test_scenario_i_connected_assessment_path_is_observability_free() -> None:
    modules = [importlib.import_module("cmm.domains.quality_contracts")]
    modules.extend(
        importlib.import_module(f"cmm.domains.{path.parent.name}.quality_metrics")
        for path in _quality_module_paths()
        if path.name == "quality_metrics.py"
    )

    for module in modules:
        for value in vars(module).values():
            qualified = (
                f"{getattr(value, '__module__', '')}.{getattr(value, '__name__', '')}"
            )
            for token in _OBSERVABILITY_TYPES:
                assert token not in qualified, f"{module.__name__}:{qualified}"


# ── Scenario J — Phase 11 execution boundary ──────────────────────────────────


_FORBIDDEN_EXECUTION_CALLS = (
    "execute_benchmark",
    "run_benchmark",
    "execute_evaluator",
    "run_evaluator",
    "resolve_evaluator",
    "invoke_model",
    "invoke_provider",
    "compare_models",
    "rank_models",
    "detect_regression",
    "route_request",
)
_FORBIDDEN_EXECUTION_IMPORTS = (
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "cmm.agent_runtime",
    "cmm.domains.providers",
    "cmm.domains.model_gateway",
)


def test_scenario_j_phase_10_48_performs_no_execution() -> None:
    for path in _quality_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(_FORBIDDEN_EXECUTION_IMPORTS), (
                        f"{path}:{alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(_FORBIDDEN_EXECUTION_IMPORTS), (
                    f"{path}:{module}"
                )
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    assert func.id not in _FORBIDDEN_EXECUTION_CALLS, (
                        f"{path}:{func.id}"
                    )
                elif isinstance(func, ast.Attribute):
                    assert func.attr not in _FORBIDDEN_EXECUTION_CALLS, (
                        f"{path}:{func.attr}"
                    )


def test_scenario_j_connected_assessment_executes_nothing() -> None:
    metrics = build_health_quality_metrics()
    results = _results_for(metrics)
    assessment = assess_domain_quality(metrics, results)
    payload = export_domain_quality_assessment(assessment)
    restored = import_domain_quality_assessment(payload)

    assert restored == assessment
    assert restored.passed is True


def test_scenario_j_pack_round_trip_contains_no_execution_surface() -> None:
    definition = build_health_domain_definition()
    pack = DomainPack(
        definition=definition,
        manifest=_manifest_for(definition),
        root_path="/opt/health",
    )
    restored = DomainPack.from_dict(copy.deepcopy(pack.to_dict()))

    assert restored.definition.quality_metrics == definition.quality_metrics
