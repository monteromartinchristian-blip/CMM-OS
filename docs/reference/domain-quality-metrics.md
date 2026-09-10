# Domain Quality Metrics

**Phase:** 10.48 — Domain Quality Metrics
**Design Point:** `DP-048` — Declarative, Domain-Owned Quality Policy and Deterministic Assessment
**Acceptance Test:** `AT-DP-048` — Connected Domain Quality Metrics Acceptance
**Status:** `PHASE10_48=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT_V4` · `INDEPENDENT_AUDIT_V1=FAIL` · `INDEPENDENT_REAUDIT_V2=FAIL` · `INDEPENDENT_REAUDIT_V3=FAIL` · `MINOR_04=REMEDIATED_REPORTED` · `DP-048=VERIFIED_EXISTING` · `AT-DP-048=PASS` · `CLOSURE_ELIGIBLE=NO`

> A Domain Pack declares what quality means. External evaluation produces evidence
> later. Phase 10.48 validates and deterministically aggregates that evidence
> without executing benchmarks, evaluators, models, or providers.

## 1. Purpose and boundaries

Phase 10.48 adds the canonical Domain Intelligence **quality-policy** layer:

```text
Phase 10.47  Domain benchmark assets      (what evidence should be checked)
Phase 10.48  Domain quality policy + deterministic assessment
Phase 11.36  evaluator/model execution, comparison, regression, rankings
Phase 11.35/11.36+  routing evidence
```

A Domain Pack may declare which quality dimensions matter, their relative
weights, opaque evaluator references, minimum scores and blocking semantics.
Phase 10.48 also defines immutable evidence/result contracts and a pure
deterministic assessment function over evidence produced elsewhere.

Everything is declarative and local: Phase 10.48 never executes a benchmark,
evaluator, model or provider, never compares or ranks models, never detects
regressions and never routes requests.

## 2. Public contracts

Exposed additively through `cmm.domains`:

```python
DomainQualityMetric
DomainQualityHumanReviewResult
DomainQualityMetricResult
DomainQualityAssessment
build_domain_quality_metric_result
assess_domain_quality
export_domain_quality_assessment
import_domain_quality_assessment
```

No evaluator, provider, model, registry, loader, resolver, store, runtime or
engine API is exported.

### 2.1 `DomainQualityMetric`

Immutable, typed, versioned, serializable, deterministic, domain-owned,
provider-independent, model-independent and evaluator-execution-independent.

```python
DomainQualityMetric(
    id="quality-metric:health:prudence",
    domain_id=DomainId(slug="health"),
    schema_version="1",
    version="1",
    name="prudence",
    weight=Decimal("0.25"),
    evaluator_id="evaluator:prudence",
    minimum_score=Decimal("0.90"),
    blocking=True,
    metadata={},
)
```

* Canonical ID: `quality-metric:<domain-slug>:<metric-slug>`; the embedded slug
  must equal `domain_id.slug` and both slugs follow the canonical domain-slug
  grammar.
* `DomainId` from `cmm.domains.identifiers` is reused; no competing identifier
  type exists.
* `schema_version` versions serialization; `version` versions the policy.
* `name` is a stable extensible dimension string, not a closed enum.
* `evaluator_id` is an opaque, non-empty reference only. Its presence neither
  authorizes nor implies that an evaluator implementation exists.
* `metadata` is immutable, JSON-safe, descriptive audit metadata.

### 2.2 `DomainQualityHumanReviewResult`

An immutable evidence container only. It records status, optional score and
confidence, an optional reviewer reference, notes and metadata.

It never schedules a review, contacts or authenticates a reviewer, creates a
workflow or approval engine, or performs any external operation.

### 2.3 `DomainQualityMetricResult`

Preserves the policy snapshot that actually applied:

```text
metric_id, domain_id, schema_version, metric_version, metric_name, score,
weight, minimum_score, blocking, evaluator_id, evaluator_version, confidence,
human_review_results, metadata
```

Derived, non-caller-controlled semantics:

```text
threshold_passed = score >= minimum_score
blocking_failure = blocking and not threshold_passed
```

### 2.4 `DomainQualityAssessment`

Preserves `domain_id`, `schema_version`, `metric_results`, `aggregate_score`,
`confidence`, `blocking_failures`, `passed` and `metadata`.

* Exactly one unique result per declared metric.
* Results are emitted in canonical declared metric order.
* `blocking_failures` lists, in declared order, every blocking metric whose
  score is below its threshold.
* `passed = not blocking_failures`.
* No separate global aggregate-pass threshold is introduced by Phase 10.48.

The assessment re-derives aggregate score, confidence, blocking failures and
`passed` at construction time, so caller-controlled derived state that is
inconsistent with the canonical calculation fails closed — including on
deserialization.

## 3. Decimal semantics

All policy and evidence numeric values are `Decimal`: weight, minimum score,
metric score, result confidence, optional human-review score/confidence,
aggregate score and assessment confidence.

* Runtime constructors reject `float`, `int`, `bool` and numeric strings.
* Deserialization accepts the canonical decimal strings emitted by
  serialization.
* Values must be finite; `NaN`, `Infinity` and `-Infinity` are rejected.
* Ranges: `0 < weight <= 1`; `0 <= minimum_score <= 1`; `0 <= score <= 1`;
  `0 <= confidence <= 1`.

Canonical decimal text is built directly from `Decimal.as_tuple()`, so the
active global decimal context can never round or reformat a value. Insignificant
trailing zeros are stripped without losing value (matching Phase 10.47 cost
semantics).

### 3.1 Context-independent assessment arithmetic

The normalized weighted means are computed with exact rational arithmetic
(`fractions.Fraction`) and reconstructed as `Decimal`. Weighted operands are
converted exactly to rational values before division. When the normalized
rational has a terminating decimal expansion, reconstruction is exact. Finite
`Decimal` inputs can still produce a non-terminating normalized ratio (for
example, a value equivalent to `2/3`); in that case the contract uses
deterministic bounded `ROUND_HALF_EVEN` reconstruction derived from operand
magnitudes. The result is therefore independent of the process-global decimal
context even when exact finite `Decimal` representation is impossible, and the
process-global decimal context is never mutated.

Tests prove identical behaviour under `prec=10`, `prec=28` and `prec=50`.

## 4. Aggregation formulas

```text
aggregate_score = Σ(metric_score × metric_weight) / Σ(metric_weight)
confidence      = Σ(metric_confidence × metric_weight) / Σ(metric_weight)
```

Weights need not sum to `1`; normalization preserves relative priority without
forcing every future metric addition to rebalance a catalog. First-party
catalogs nevertheless sum exactly to `Decimal("1")`.

## 5. Blocking semantics

```text
if any blocking metric result has score < minimum_score:
    passed = False
```

A high aggregate score can never compensate for a failed blocking metric: the
`passed` flag is derived solely from `blocking_failures`.

## 6. Exact policy binding

`assess_domain_quality(metrics, results)` fails closed unless, for each declared
metric, there is exactly one result whose snapshot matches the declared policy
exactly:

```text
domain_id, metric_version, metric_name, weight, minimum_score, blocking,
evaluator_id
```

It also rejects empty metric sets, duplicate metric IDs, duplicate result IDs,
mixed domains, missing declared results and unexpected results. No invalid
metric or result is silently dropped.

## 7. Metadata authority restrictions

Quality metadata is descriptive audit metadata only and must not carry
model/provider/routing authority. A recursive normalized scan over mapping keys
rejects semantic style/case variants (snake_case, kebab-case, camelCase,
PascalCase and compound aliases) of:

```text
model, model_id, models, candidate_models, preferred_models, prohibited_models
provider, provider_id, providers, candidate_providers, preferred_providers,
prohibited_providers
routing_weight, routing_weights
```

Only mapping keys are inspected; human-readable prose values are never
fuzzy-scanned. Contract-owned concepts (`weight`, `minimum_score`, `blocking`,
`evaluator_id`, `evaluator_version`, `score`, `confidence`) remain valid.
`evaluator_id` is not model/provider authority.

## 8. `DomainDefinition` integration

`DomainDefinition` gains one additive, last-declared field:

```python
quality_metrics: tuple[DomainQualityMetric, ...] = ()
```

* Backward-compatible positional construction; a missing serialized field
  deserializes to `()`.
* Members may be canonical `DomainQualityMetric` objects or mappings parsed
  through `DomainQualityMetric.from_dict`.
* Domain mismatch and duplicate metric IDs fail closed.
* Phase 10.46 `model_policy` and Phase 10.47 `benchmark_suites` are preserved
  unchanged.

Canonical ownership:

```text
DomainRegistry
    ↓
DomainDefinition
    ↓
quality_metrics
```

There is no quality-specific registry.

## 9. Canonical Domain Pack integration

The existing declarative path is extended, not replaced:

```text
declarative definition
    ↓
existing ParsedDomainPack / Domain Pack parser
    ↓
DomainDefinition
    ↓
quality_metrics
    ↓
existing DomainRegistry
```

`quality_metrics` is accepted as a declarative list of metric mappings on the
same canonical path as `benchmark_suites`; malformed containers and non-mapping
entries fail closed with `quality_metrics` / `quality_metrics[<index>]` fields.
No `DomainQualityMetricLoader`, registry, resolver, store, runtime or engine is
introduced.

## 10. First-party catalogs

Exactly twelve already-implemented first-party Domain Packs declare an approved
quality policy through a local, pure factory in
`cmm/domains/<domain>/quality_metrics.py`, attached via
`quality_metrics=build_<domain>_quality_metrics()`:

```text
general, health, relationships, university, oppositions, reflection, concerns,
languages, parenthood, sport, life-plan, project
```

| Domain | Metric | Weight | Minimum | Blocking |
| --- | --- | ---: | ---: | --- |
| general | factual-fidelity | 0.25 | 0.70 | no |
| general | contextual-fidelity | 0.20 | 0.65 | no |
| general | usefulness | 0.20 | 0.65 | no |
| general | clarity | 0.15 | 0.65 | no |
| general | instruction-compliance | 0.20 | 0.70 | yes |
| health | factual-fidelity | 0.25 | 0.90 | yes |
| health | prudence | 0.25 | 0.90 | yes |
| health | temporal-correctness | 0.20 | 0.85 | yes |
| health | privacy-compliance | 0.20 | 0.95 | yes |
| health | contextual-fidelity | 0.10 | 0.80 | no |
| relationships | ambiguity-handling | 0.25 | 0.80 | no |
| relationships | contextual-continuity | 0.20 | 0.75 | no |
| relationships | non-attribution-of-intent | 0.25 | 0.90 | yes |
| relationships | uncertainty-preservation | 0.15 | 0.80 | yes |
| relationships | usefulness | 0.15 | 0.70 | no |
| university | temporal-correctness | 0.25 | 0.85 | yes |
| university | constraint-compliance | 0.25 | 0.85 | yes |
| university | feasibility | 0.20 | 0.75 | no |
| university | plan-quality | 0.20 | 0.75 | no |
| university | factual-fidelity | 0.10 | 0.80 | no |
| oppositions | official-source-fidelity | 0.25 | 0.90 | yes |
| oppositions | temporal-correctness | 0.25 | 0.90 | yes |
| oppositions | requirement-precision | 0.20 | 0.85 | yes |
| oppositions | contextual-continuity | 0.15 | 0.75 | no |
| oppositions | usefulness | 0.15 | 0.70 | no |
| reflection | epistemic-separation | 0.25 | 0.80 | yes |
| reflection | ambiguity-preservation | 0.20 | 0.75 | no |
| reflection | contextual-continuity | 0.20 | 0.75 | no |
| reflection | depth | 0.20 | 0.65 | no |
| reflection | user-agency | 0.15 | 0.80 | yes |
| concerns | contextual-understanding | 0.15 | 0.75 | no |
| concerns | support-need-calibration | 0.15 | 0.80 | yes |
| concerns | epistemic-separation | 0.15 | 0.85 | yes |
| concerns | reassurance-calibration | 0.15 | 0.85 | yes |
| concerns | proportional-risk | 0.15 | 0.90 | yes |
| concerns | useful-questioning | 0.10 | 0.70 | no |
| concerns | non-pathologizing-recurrence | 0.075 | 0.85 | yes |
| concerns | user-agency | 0.075 | 0.80 | yes |
| languages | linguistic-correctness | 0.30 | 0.80 | yes |
| languages | level-alignment | 0.20 | 0.75 | no |
| languages | instruction-compliance | 0.20 | 0.80 | yes |
| languages | usefulness | 0.15 | 0.70 | no |
| languages | clarity | 0.15 | 0.70 | no |
| parenthood | factual-fidelity | 0.25 | 0.85 | yes |
| parenthood | sensitivity | 0.20 | 0.80 | no |
| parenthood | prudence | 0.20 | 0.85 | yes |
| parenthood | temporal-correctness | 0.15 | 0.75 | no |
| parenthood | privacy-compliance | 0.20 | 0.90 | yes |
| sport | factual-fidelity | 0.25 | 0.80 | yes |
| sport | temporal-correctness | 0.20 | 0.75 | no |
| sport | plan-quality | 0.20 | 0.75 | no |
| sport | usefulness | 0.20 | 0.70 | no |
| sport | instruction-compliance | 0.15 | 0.75 | yes |
| life-plan | contextual-fidelity | 0.20 | 0.80 | no |
| life-plan | feasibility | 0.25 | 0.80 | yes |
| life-plan | tradeoff-quality | 0.20 | 0.75 | no |
| life-plan | temporal-correctness | 0.15 | 0.75 | no |
| life-plan | plan-quality | 0.20 | 0.75 | no |
| project | correctness | 0.25 | 0.90 | yes |
| project | architectural-consistency | 0.20 | 0.85 | yes |
| project | validation-quality | 0.20 | 0.90 | yes |
| project | tool-calling-quality | 0.20 | 0.85 | yes |
| project | structured-output | 0.15 | 0.80 | no |

Every catalog has at least one blocking metric and total weight exactly
`Decimal("1")`. `domain:mental-health` and `domain:neurodivergence` quality
catalogs remain out of scope until Phases 10.52/10.53.

Wiring follows `DomainDefinition.quality_metrics` list order as the canonical
declared order.

## 11. Determinism

* First-party metric order is declared and deterministic.
* Assessment emits metric results and blocking failures in declared order.
* Metadata serialization uses stable key ordering.
* Decimal serialization is canonical and context-independent.
* Identical policy plus evidence yields equal assessments.
* Canonical assessment export is byte-identical across repeated calls.
* Core assessment creates no timestamps and no random IDs.

## 12. Phase 10.47 boundary (frozen)

`DomainBenchmarkCase.evaluation_criteria` remains descriptive, unweighted,
model-agnostic and provider-agnostic. Benchmark cases carry no `weight`,
`minimum_score`, `blocking` or `aggregate_score`, no `DomainQualityMetric`, and
there is no mandatory one-to-one mapping between benchmark criteria and quality
metrics. The two layers coexist:

```text
benchmark case  = what representative evidence should be checked
quality metric  = how a domain weights/gates a quality dimension
```

## 13. Observability separation (frozen)

`DomainMetricStatus`, `DomainMetricBucket`, `DomainMetricMeasurement`,
`DomainMetricsSnapshot` and `DomainMetricsCalculator` are operational
observability contracts. They are not quality policy: they are not renamed, not
repurposed, not imported into quality assessment, and
`DomainMetricsCalculator` does not calculate quality. Quality production modules
never reference those types (guarded by AST inspection).

## 14. Phase 11 boundary

Phase 11.36 owns evaluation execution. Phase 10.48 contains no benchmark
execution or scheduling, benchmark runner, evaluator discovery/registry/
resolution/execution, model or provider invocation, Model Gateway integration,
provider adapters, model registry, candidate generation, model comparison,
ranking, leaderboards, regression detection, historical evaluation store,
routing evidence or decisions, best-model recommendations, real-call cost or
latency measurement.

## 15. Fail-closed validation summary

Rejected at the contract or assessment boundary: malformed IDs; wrong domain
ID; empty required strings; duplicate metric/result IDs; non-`Decimal`
constructor values; `NaN`/`Infinity`; score/confidence/threshold outside
`[0,1]`; `weight <= 0` or `weight > 1`; non-strict booleans; unknown serialized
fields; non-JSON-safe metadata; model/provider/routing authority metadata;
missing, extra, wrong-domain, stale-version or otherwise policy-mismatched
evidence; and caller-controlled derived state inconsistent with the canonical
calculation.

## 16. Error behavior

Contract and assessment boundaries raise the canonical
`DomainContractValidationError`; deserialization boundaries raise
`DomainSerializationError`. Nested definition/pack parsing uses the canonical
indexed nested-error wrapping (`quality_metrics[<index>]`).

## 17. Implementation evidence

Production:

```text
cmm/domains/quality_contracts.py
cmm/domains/contracts.py                       (DomainDefinition.quality_metrics)
cmm/domains/pack.py                            (declarative quality_metrics)
cmm/domains/manifest.py                        (declarative known-field set)
cmm/domains/__init__.py                        (public exports)
cmm/domains/<twelve domains>/quality_metrics.py
cmm/domains/<twelve domains>/definition.py
```

Tests:

```text
tests/domains/test_domain_quality_contracts.py
tests/domains/test_domain_quality_pack_integration.py
tests/domains/test_domain_quality_first_party.py
tests/domains/test_domain_quality_architecture.py
tests/domains/test_domain_quality_dp048_acceptance.py
```

Design and plan:

```text
docs/superpowers/specs/2026-09-10-phase-10.48-domain-quality-metrics-design.md
docs/superpowers/plans/2026-09-10-phase-10.48-domain-quality-metrics-implementation-plan.md
```

`AT-DP-048` scenarios A–J cover canonical registry discovery, real declarative
round-trip, `prec=10/28/50` Decimal determinism, non-compensable blocking
failure, domain differentiation, human-review preservation, Phase 10.47
coexistence, fail-closed policy binding, observability isolation and the Phase 11
no-execution boundary — all over real canonical components (real first-party
definitions, real `DomainRegistry`, real `ParsedDomainPack`/declarative loader,
real benchmark suites).

## 18. Non-goals

Phase 10.48 does not provide: a benchmark runner or scheduler; an evaluator
registry, resolver or runner; model/provider invocation or adapters; model
comparison, ranking, leaderboards or regression detection; a historical
evaluation store; routing evidence or decisions; real-call cost/latency
measurement; a quality registry, loader, resolver, store, runtime or engine;
observability repurposing; or any Phase 10.49–10.53 and Phase 11 behaviour.

## 19. Status

```text
PHASE10_48=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT_V4
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=FAIL
INDEPENDENT_REAUDIT_V3=FAIL
BLOCKERS=0
MAJORS=0
MINORS=1
MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
MINOR_01=VERIFIED_REMEDIATED
MINOR_02=VERIFIED_REMEDIATED
MINOR_03=VERIFIED_REMEDIATED
MINOR_04=REMEDIATED_REPORTED
DP-048=VERIFIED_EXISTING
AT-DP-048=PASS
CLOSURE_ELIGIBLE=NO
```

Independent Audit V1 and Re-audits V2/V3 remain preserved as historical
evidence. Re-audit V3 verified `DP-048`, `AT-DP-048`, all four V1 findings
and `MINOR_03`, but returned `FAIL` for docs-only `MINOR_04`. That finding
is now `REMEDIATED_REPORTED`. Phase closure requires Independent Re-audit V4
reporting `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`,
`DP-048=VERIFIED_EXISTING`, `AT-DP-048=PASS` and
`CLOSURE_ELIGIBLE=YES`. Only after that PASS may a separate docs-only
closure commit be made.
