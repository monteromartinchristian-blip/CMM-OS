# Domain Benchmark Suites

**Phase:** 10.47 — Domain Benchmark Suites
**Design Point:** `DP-047` — Portable, Model-Agnostic Domain Benchmark Suites
**Acceptance:** `AT-DP-047` — Connected Domain Benchmark Asset Acceptance
**Status:** `PHASE10_47=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT`

> **Domains define representative evidence cases. Phase 10.48 defines how domain
> quality is measured. Phase 11 executes and compares models.**

## 1. Purpose and boundary

Phase 10.47 adds a declarative **benchmark asset layer** to Domain Intelligence.
A Domain Pack can now ship immutable, typed, versioned, reproducible and
exportable benchmark suites describing what a future evaluation framework must
verify for that domain.

Benchmark assets are **data**. They are **not** a benchmark runtime.

| Owner | Responsibility |
| --- | --- |
| Phase 10.47 | Declares benchmark assets (`DomainBenchmarkSuite`, `DomainBenchmarkCase`), validation, deterministic export/digest, `DomainDefinition.benchmark_suites`, Domain Pack round-trip, first-party suites |
| Phase 10.48 | Domain quality metrics (weights, thresholds, blocking scores, aggregate scores) |
| Phase 11.36 | Model execution, output evaluation, candidate comparison, cost/latency, regression detection, rankings, routing evidence |

Phase 10.47 does **not** execute models, invoke providers, select candidate
models/providers, resolve or run evaluators, schedule benchmarks, persist
results, build leaderboards, or implement Phase 10.48/Phase 11 behavior.

## 2. Production contracts

Module: `cmm/domains/benchmark_contracts.py`

### 2.1 `DomainBenchmarkSuite`

```python
DomainBenchmarkSuite(
    id="benchmark-suite:health:core",
    domain_id="domain:health",
    schema_version="1",
    version="1",
    cases=(...),
    metadata={},
)
```

- `id` — stable canonical identifier.
- `domain_id` — canonical `DomainId`; must match the domain slug embedded in `id`.
- `schema_version` — versions the serialization contract.
- `version` — versions the benchmark content.
- `cases` — non-empty tuple of `DomainBenchmarkCase`; case IDs are unique.
- `metadata` — immutable, JSON-safe audit metadata only.
- `content_digest` — SHA-256 over the canonical serialized suite content.

### 2.2 `DomainBenchmarkCase`

```python
DomainBenchmarkCase(
    id="benchmark-case:health:clinical-timeline-001",
    domain_id="domain:health",
    objective="Build a reliable clinical timeline",
    knowledge_package_id=None,
    input_resource_refs=(),
    expected_elements=(),
    required_constraints=(),
    prohibited_behaviors=(),
    evaluation_criteria=(),
    required_format=None,
    required_schema=None,
    sensitivity=None,
    privacy_requirement=None,
    maximum_cost_eur=None,
    evaluator_ids=(),
    human_review_required=False,
    human_review_guidance=(),
    metadata={},
)
```

`evaluation_criteria` are **unweighted descriptive** dimensions. No Phase 10.47
contract carries `weight`, `minimum_score`, `blocking`, `aggregate_score` or
`DomainQualityMetric`; those belong to Phase 10.48.

### 2.3 Export helpers

```python
from cmm.domains import (
    export_domain_benchmark_suite,
    import_domain_benchmark_suite,
)
```

Export is canonical JSON: UTF-8, sorted keys, stable separators,
`ensure_ascii=False`, no timestamps, no random IDs, no local paths. Repeated
exports of the same suite are byte-identical; `import(export(suite)) == suite`;
export/import preserves `content_digest`.

## 3. Benchmark identity

```text
benchmark-suite:<domain-slug>:<suite-slug>
benchmark-case:<domain-slug>:<case-slug>
```

The embedded domain slug must equal `domain_id.slug`. Malformed IDs, mismatched
domains, empty cases and duplicate IDs fail closed. The canonical Domain slug
syntax is reused; no competing Domain identifier model is introduced.

## 4. Validation

Benchmark contracts fail closed on:

- empty objectives, empty/duplicate string collections, empty suite cases;
- malformed or domain-mismatched benchmark IDs;
- suite/case domain mismatches and duplicate suite/case IDs;
- non-`bool` `human_review_required`;
- non-JSON or deeply mutable `metadata` / `required_schema`;
- `maximum_cost_eur` that is not a finite, non-negative `Decimal`
  (`bool`, `float`, `int`, `str`, `NaN`, `Infinity`, negative rejected);
- unknown serialized fields;
- reserved model/provider authority metadata keys.

`maximum_cost_eur` serializes as a canonical decimal string.

### 4.1 Reserved metadata authority keys

Benchmark validation rejects metadata keys semantically equivalent to `model`,
`model_id`, `models`, `candidate_models`, `preferred_models`,
`prohibited_models`, `provider`, `provider_id`, `providers`,
`candidate_providers`, `preferred_providers`, `prohibited_providers`,
`routing_weight` and `routing_weights`, including casing/style variants
(`camelCase`, `PascalCase`, `snake_case`, hyphenated) and nested mappings.
Only mapping keys are inspected; prose values are never scanned.

## 5. DomainDefinition and Domain Pack integration

`DomainDefinition` appends:

```python
benchmark_suites: tuple[DomainBenchmarkSuite, ...] = ()
```

as its last declared field, preserving existing positional construction and the
Phase 10.46 `model_policy`. Missing `benchmark_suites` deserializes to `()`.

The existing `ParsedDomainPack` / `DomainPack` path preserves benchmark suites
because it serializes the whole `DomainDefinition`. No benchmark loader,
registry, lifecycle or rollback mechanism is introduced. Invalid benchmark
payloads fail closed during definition/pack parsing instead of being dropped.

Canonical discovery remains:

```text
DomainRegistry -> DomainDefinition -> benchmark_suites
```

## 6. First-party benchmark assets

Every currently implemented first-party Domain Pack owns its suites in
`cmm/domains/<domain>/benchmarks.py` and attaches them in its `definition.py`.
There is no central semantic benchmark catalog.

| Domain | Suite | Cases |
| --- | --- | --- |
| general | `benchmark-suite:general:core` | 1 |
| health | `benchmark-suite:health:core` | 2 |
| relationships | `benchmark-suite:relationships:core` | 2 |
| university | `benchmark-suite:university:core` | 2 |
| oppositions | `benchmark-suite:oppositions:core` | 1 |
| reflection | `benchmark-suite:reflection:core` | 1 |
| concerns | `benchmark-suite:concerns:core` | 3 |
| languages | `benchmark-suite:languages:core` | 1 |
| parenthood | `benchmark-suite:parenthood:core` | 2 |
| sport | `benchmark-suite:sport:core` | 1 |
| life-plan | `benchmark-suite:life-plan:core` | 1 |
| project | `benchmark-suite:project:core` | 2 |

Content is derived from each domain's already-audited DP/AT, rules and
safety/privacy invariants. Fixtures are synthetic, sanitized, static and
non-user-specific; no real user data, credentials or local paths appear in any
benchmark asset.

## 7. Model/provider agnosticism

Benchmark contracts expose no model or provider authority: no
`candidate_models`, `preferred_models`, `prohibited_models`, `model_id`,
`candidate_providers`, `preferred_providers`, `prohibited_providers`,
`provider_id` or `routing_weight`. Metadata cannot be used as an escape hatch.

## 8. Privacy, cost and evaluator semantics

- `sensitivity` / `privacy_requirement` are **restrictions only**. They can
  constrain a future run and never authorize remote processing, egress, cache,
  export or cross-domain transfer.
- `maximum_cost_eur` is a **maximum requirement only**. It never reserves
  budget, approves spending, selects a cheaper model or authorizes premium use.
- `evaluator_ids` are **opaque identifiers**. Phase 10.47 does not resolve,
  import, register or execute evaluators.
- `human_review_required` / `human_review_guidance` record a requirement only;
  no review tasks, reviewers, decisions or consensus are created.
- `required_schema` is declarative JSON data, deep-frozen and serialized
  deterministically; no runtime response validation is performed here.

## 9. No execution

Construction, pack loading, serialization and export never call `ModelRouter`,
`OutcomeEvaluationEngine`, provider clients or evaluator implementations. The
existing Agent Runtime outcome-evaluation infrastructure
(`OutcomeEvaluationEngine`, `OutcomeMetricEvaluator`,
`OutcomeCriterionEvaluator`, `OutcomeEvaluationRepository`) remains untouched
and is not duplicated.

## 10. Public API

Exported through `cmm.domains`:

```python
DomainBenchmarkCase
DomainBenchmarkSuite
export_domain_benchmark_suite
import_domain_benchmark_suite
```

No execution concepts are exported.

## 11. Tests and traceability

| Artifact | Path |
| --- | --- |
| Contract tests | `tests/domains/test_domain_benchmark_contracts.py` |
| Pack integration | `tests/domains/test_domain_benchmark_pack_integration.py` |
| First-party conformance | `tests/domains/test_domain_benchmark_first_party.py` |
| Architecture guards | `tests/domains/test_domain_benchmark_architecture.py` |
| AT-DP-047 acceptance | `tests/domains/test_domain_benchmark_dp047_acceptance.py` |

Traceability:

```text
SRC-R10:R10-C47
    → DP-047
    → DomainBenchmarkSuite / DomainBenchmarkCase
    → DomainDefinition.benchmark_suites
    → Domain Pack round-trip
    → first-party benchmark assets
    → AT-DP-047
```

## 12. Pre-audit status

```text
PHASE10_47=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
DP-047=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-047=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
PHASE10_48=NOT_STARTED
```

Independent audit remains pending. Phase 10.48 has not started.
