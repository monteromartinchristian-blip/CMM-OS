# CMM OS — Phase 10.48 — Independent Audit V1

**Date:** 2026-09-10
**Phase:** 10.48 — Domain Quality Metrics
**Audit type:** Independent exact-HEAD artifact audit
**Audited artifact:** `phase-10.48-audit-f588c7b79fa1.tar.gz`
**Audited implementation HEAD:** `f588c7b79fa122698ef578adc6cf57397fe0eca7`
**Bundle SHA-256:** `aadc6b9a1b04c5c8cafa493429b89d8db9f7306ef50fff360eabc2ba4a65e931`
**Design Point:** `DP-048`
**Acceptance:** `AT-DP-048`

## 1. Verdict

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=2
MINORS=2

DP-048=IMPLEMENTED_NOT_YET_VERIFIED_FOR_CLOSURE
AT-DP-048=PASS_REPORTED_NOT_SUFFICIENT_FOR_CLOSURE
CLOSURE_ELIGIBLE=NO
```

Phase 10.48 is substantially implemented and its central architecture is aligned with the approved design, but the audited exact-HEAD artifact is **not closure-eligible**.

Two major findings require remediation:

1. the mandatory repository-wide Ruff and format gates did not pass, despite the committed implementation plan requiring them to pass before audit;
2. `DomainQualityHumanReviewResult.from_dict()` has a real fail-closed/type-safety defect for serialized `notes`.

Two minor findings should be remediated in the same cycle:

1. source-clause coverage is stale because `R10-C48` is cited by the requirements matrix but absent from `domain-prompt-clause-coverage.md`;
2. Decimal evidence/documentation contains an ineffective non-unit-sum test and an inaccurate statement about non-terminating weighted ratios.

A new exact-HEAD bundle is required after remediation. The V1 artifact must remain immutable as historical evidence.

---

## 2. Artifact integrity

Independent verification:

```text
SHA256=aadc6b9a1b04c5c8cafa493429b89d8db9f7306ef50fff360eabc2ba4a65e931
GZIP_INTEGRITY=PASS
ARCHIVE_COMMIT_ID=f588c7b79fa122698ef578adc6cf57397fe0eca7
EXACT_HEAD_BUNDLE=PASS
```

The supplied SHA-256 matches the implementation handoff exactly.

`git get-tar-commit-id` over the decompressed archive independently resolves the exact audited commit:

```text
f588c7b79fa122698ef578adc6cf57397fe0eca7
```

The artifact is therefore suitable for independent content audit.

---

## 3. Scope and architecture verification

### 3.1 Canonical ownership

Verified:

```text
DomainRegistry
    ↓
DomainDefinition
    ├── model_policy
    ├── benchmark_suites
    └── quality_metrics
```

`DomainDefinition.quality_metrics` is additive and follows `benchmark_suites`.

The existing Domain Pack/declarative path carries `quality_metrics`; no separate quality lifecycle was introduced.

### 3.2 Parallel infrastructure

Independent source scan:

```text
DomainQualityRegistry=ABSENT
DomainQualityLoader=ABSENT
DomainQualityResolver=ABSENT
DomainQualityStore=ABSENT
DomainQualityRuntime=ABSENT
DomainQualityEngine=ABSENT
```

No prohibited parallel quality subsystem was found in production code.

### 3.3 Phase 10.47 preservation

`DomainBenchmarkCase` fields at audited HEAD are:

```text
id
domain_id
objective
knowledge_package_id
input_resource_refs
expected_elements
required_constraints
prohibited_behaviors
evaluation_criteria
required_format
required_schema
sensitivity
privacy_requirement
maximum_cost_eur
evaluator_ids
human_review_required
human_review_guidance
metadata
```

None of the following Phase 10.48 fields leaked into the 10.47 benchmark-case contract:

```text
weight
minimum_score
blocking
aggregate_score
quality_metrics
```

Result:

```text
PHASE10_47_BENCHMARK_SEMANTICS=PRESERVED
```

### 3.4 Phase 11 boundary

No production implementation was found for:

```text
model execution
provider execution
evaluator execution
benchmark execution
model comparison
model ranking
routing implementation
```

Quality contracts remain declarative/pure.

### 3.5 Observability separation

The Phase 10.48 quality path is separate from the existing observability contracts:

```text
DomainMetricMeasurement
DomainMetricsSnapshot
DomainMetricsCalculator
```

No repurposing of the observability subsystem was found.

Result:

```text
OBSERVABILITY_SEPARATION=PRESERVED
```

---

## 4. First-party quality catalogs

Independent AST inspection found exactly twelve first-party catalogs and 63 metric definitions.

```text
general        metrics=5  weight_sum=1.00  blocking=1
health         metrics=5  weight_sum=1.00  blocking=4
relationships  metrics=5  weight_sum=1.00  blocking=2
university     metrics=5  weight_sum=1.00  blocking=2
oppositions    metrics=5  weight_sum=1.00  blocking=3
reflection     metrics=5  weight_sum=1.00  blocking=2
concerns       metrics=8  weight_sum=1.000 blocking=6
languages      metrics=5  weight_sum=1.00  blocking=2
parenthood     metrics=5  weight_sum=1.00  blocking=3
sport          metrics=5  weight_sum=1.00  blocking=2
life_plan      metrics=5  weight_sum=1.00  blocking=1
project        metrics=5  weight_sum=1.00  blocking=4

TOTAL_METRICS=63
```

The implemented catalog literals were compared against the approved specification table:

```text
MISSING_APPROVED_METRICS=0
UNEXPECTED_METRICS=0
POLICY_VALUE_MISMATCHES=0
```

No premature quality catalog exists for:

```text
domain:mental-health
domain:neurodivergence
```

Result:

```text
FIRST_PARTY_QUALITY_POLICY=PASS
FUTURE_DOMAIN_BOUNDARY=PRESERVED
```

---

## 5. Contract and assessment verification

### 5.1 Verified behavior

The audited code provides:

- immutable `DomainQualityMetric`;
- immutable `DomainQualityHumanReviewResult`;
- immutable `DomainQualityMetricResult`;
- immutable `DomainQualityAssessment`;
- strict constructor-side `Decimal` handling;
- canonical decimal serialization;
- deterministic weighted aggregation;
- deterministic weighted confidence;
- exact policy binding for metric identity/version/name/weight/threshold/blocking/evaluator;
- explicit blocking-failure derivation;
- canonical assessment export/import.

The weighted-mean implementation converts finite Decimal operands to exact rational values and avoids dependence on the ambient Decimal context.

Blocking semantics are implemented so that a failed blocking metric forces `passed=False` regardless of aggregate score.

### 5.2 Independent focused execution

The audit environment independently executed:

```text
tests/domains/test_domain_quality_contracts.py
tests/domains/test_domain_quality_pack_integration.py
```

Result:

```text
111 passed in 0.21s
```

Selected Phase 10.48 production/test files also pass independent `compileall`.

The audit environment does not contain the repository's complete development dependency set (`libcst` and Ruff are unavailable), so the full domain/global suite was not independently re-run here. This does not change the V1 verdict because the two major findings below already prevent closure.

---

# 6. Findings

## MAJOR-01 — Mandatory global Ruff/format gates were red

### Evidence

The committed Phase 10.48 implementation plan explicitly requires:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m compileall -q cmm kernel
git diff --check
```

and immediately states:

```text
Expected: PASS.
```

The implementation handoff instead discloses:

```text
ruff check .              -> 839 pre-existing violations
ruff format --check .     -> 340 files needing reformat
```

The agent then substituted scoped Phase 10.48 lint/format checks and nevertheless reported "all gates green".

### Why this is major

This is not merely historical lint debt. It is a direct mismatch between:

- the approved/committed implementation plan;
- the permanent Phase workflow;
- the evidence required before independent audit;
- the state actually handed to audit.

A scoped clean result does not make a required global gate green.

The implementation may contain zero newly introduced Ruff issues, but the **approved audit precondition was not satisfied**.

### Required remediation

Do **not** silently mass-format or lint-fix hundreds of unrelated historical files inside Phase 10.48.

Resolve the pre-existing baseline explicitly and audibly. The remediation must choose and document one legitimate path:

1. bring the repository-wide Ruff/format baseline to green in a separately controlled maintenance/remediation scope; or
2. if the project intentionally adopts baseline-aware gates for legacy debt, add an explicit remediation design/plan amendment approved before execution, prove the exact starting-HEAD baseline, prove zero new Phase 10.48 violations, and define the canonical gate that replaces the impossible whole-repo PASS requirement.

The existing plan cannot simply be treated as satisfied.

```text
MAJOR_01=OPEN
GLOBAL_RUFF_GATE=FAIL_REPORTED
GLOBAL_FORMAT_GATE=FAIL_REPORTED
```

---

## MAJOR-02 — Human-review `notes` deserialization is not fail-closed

### Location

`cmm/domains/quality_contracts.py`

The constructor correctly validates `notes` through `_require_str_tuple()`:

```python
object.__setattr__(self, "notes", _require_str_tuple(self.notes, "notes"))
```

and `_require_str_tuple()` correctly rejects strings/bytes/non-sequences.

However `DomainQualityHumanReviewResult.from_dict()` pre-coerces serialized input:

```python
notes=tuple(data.get("notes", ()) or ()),
```

before constructor validation.

### Independent adversarial evidence

Using the audited exact-HEAD code:

```text
notes="abc"
→ ACCEPTED
→ ('a', 'b', 'c')

notes={"a": "x", "b": "y"}
→ ACCEPTED
→ ('a', 'b')

notes=123
→ raw TypeError: 'int' object is not iterable

notes=True
→ raw TypeError: 'bool' object is not iterable

notes=b"abc"
→ DomainSerializationError
```

### Why this is major

The serialized public contract is supposed to be typed and fail closed. The current implementation:

- silently accepts invalid container types;
- mutates their semantic shape;
- allows mapping keys to become review notes;
- leaks raw `TypeError` for malformed public input instead of the domain serialization error contract.

This affects one of the explicitly required result dimensions: human-review evidence.

The valid human-review round-trip in `AT-DP-048` does not exercise this adversarial path, so the acceptance test does not close the defect.

### Required remediation

Validate the raw serialized `notes` container **before** tuple conversion.

At minimum:

- list/tuple of non-empty strings → accepted;
- string → rejected with `DomainSerializationError`;
- bytes/bytearray → rejected with `DomainSerializationError`;
- mapping → rejected with `DomainSerializationError`;
- int/bool/other scalar → rejected with `DomainSerializationError`;
- nested/non-string items → rejected with `DomainSerializationError`.

Add regression tests proving the error taxonomy and no silent coercion.

```text
MAJOR_02=OPEN
HUMAN_REVIEW_DESERIALIZATION=FAIL
FAIL_CLOSED_SERIALIZATION=NOT_VERIFIED
```

---

## MINOR-01 — `R10-C48` is missing from source-clause coverage

### Evidence

`docs/reference/domain-intelligence-requirements-matrix.md` now contains:

```text
DP-048
source = SRC-R10:R10-C48
```

But `docs/audits/domain-prompt-clause-coverage.md` contains:

```text
R10-C46
R10-C47
```

and no `R10-C48` row.

The same coverage document still claims:

```text
total_clauses = 153
covered_clauses = 153
unclassified_clauses = 0
```

### Why this matters

The requirements matrix now depends on a source-clause identifier that its canonical coverage ledger does not classify. This makes the traceability claim internally stale.

### Required remediation

Add `R10-C48` with `DP-048` classification and update/recompute the coverage totals and any invariant asserting every clause appears exactly once.

Do not rewrite historical Phase 10.47 evidence.

```text
MINOR_01=OPEN
R10_C48_CLAUSE_COVERAGE=MISSING
TRACEABILITY_COUNTS=STALE
```

---

## MINOR-02 — Decimal test/doc evidence is internally inaccurate

This minor has two closely related parts.

### A. Non-unit-sum regression test does not test a non-unit sum

The test named:

```text
test_assessment_weight_normalization_does_not_require_unit_sum
```

uses:

```python
weight=Decimal("0.5")
weight=Decimal("0.5")
```

which sums to exactly `1.0`.

The implementation itself was independently probed with genuinely non-unit weights and behaves correctly, so this is a test-evidence gap rather than a production defect.

Required fix: use a real non-unit total such as `0.1 + 0.2`, assert the normalized expected result, and preferably check ambient-context independence.

### B. Reference documentation falsely says non-terminating ratios are impossible in practice

`docs/reference/domain-quality-metrics.md` states:

```text
A non-terminating ratio
(impossible for the bounded operations over finite decimals in practice)
...
```

That is mathematically false. Finite Decimal operands can produce a non-terminating weighted mean, for example a rational result equivalent to `2/3`.

The implementation already contains a deterministic local-context fallback for this case, so the code is more correct than the documentation.

Required fix: state that finite Decimal operands are converted exactly to rational values; terminating results reconstruct exactly, while non-terminating results use deterministic bounded rounding independent of ambient context.

```text
MINOR_02=OPEN
NON_UNIT_SUM_TEST=INEFFECTIVE
DECIMAL_REFERENCE_WORDING=INACCURATE
```

---

## 7. Acceptance-test assessment

The committed `AT-DP-048` is structurally strong and connected. It uses real canonical components rather than isolated mocks, including:

- real first-party Domain Definitions;
- real `DomainRegistry`;
- real declarative/ParsedDomainPack path;
- real quality contracts;
- real Phase 10.47 benchmark coexistence.

Its intended A–J coverage addresses:

- canonical discovery;
- pack round-trip;
- Decimal determinism;
- blocking non-compensation;
- domain differentiation;
- human-review preservation;
- 10.47 coexistence;
- policy-binding fail-closed behavior;
- observability isolation;
- Phase 11 boundary.

However, the acceptance suite does not cover malformed human-review-note containers, and the audit environment could not independently execute the complete AT dependency graph because `libcst` is absent.

Therefore V1 records:

```text
AT-DP-048=PASS_REPORTED_NOT_SUFFICIENT_FOR_CLOSURE
```

After remediation, the exact AT must be rerun and independently re-audited from the new exact-HEAD bundle.

---

## 8. DP-048 assessment

The core design point clearly exists in production:

- domain-owned declarative metrics;
- `DomainDefinition.quality_metrics`;
- canonical Domain Pack path;
- deterministic assessment;
- weighted aggregation;
- non-compensable blocking failures;
- first-party policies;
- no evaluator/model/provider execution;
- no parallel quality subsystem.

But a required public serialization boundary remains defective and mandatory pre-audit gates were not green.

Therefore:

```text
DP-048=IMPLEMENTED_NOT_YET_VERIFIED_FOR_CLOSURE
```

`VERIFIED_EXISTING` is intentionally withheld until remediation passes independent re-audit.

---

## 9. Positive evidence retained

The V1 failure should not obscure what is already correct and should be preserved unchanged during remediation:

```text
ARTIFACT_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
FIRST_PARTY_DOMAIN_COUNT=12
FIRST_PARTY_METRIC_COUNT=63
FIRST_PARTY_POLICY_MATCH=PASS
FIRST_PARTY_WEIGHT_SUMS=PASS
BLOCKING_POLICY_PRESENT=PASS
DOMAIN_DEFINITION_INTEGRATION=PASS
DOMAIN_PACK_INTEGRATION=PASS
PHASE10_47_BOUNDARY=PASS
OBSERVABILITY_SEPARATION=PASS
PARALLEL_QUALITY_INFRASTRUCTURE=ABSENT
MODEL_EXECUTION=ABSENT
PROVIDER_EXECUTION=ABSENT
EVALUATOR_EXECUTION=ABSENT
BENCHMARK_EXECUTION=ABSENT
MODEL_COMPARISON=ABSENT
MODEL_RANKING=ABSENT
ROUTING_IMPLEMENTATION=ABSENT
SELECTED_INDEPENDENT_TESTS=111_PASS
COMPILE_PHASE_FILES=PASS
```

Remediation must be narrow and must not redesign these verified areas.

---

## 10. Remediation scope

Required remediation is limited to the four findings:

### Code/tests

1. Fix `DomainQualityHumanReviewResult.from_dict()` `notes` validation.
2. Add adversarial serialization regression tests.
3. Correct the non-unit-sum normalization test so the weights really do not sum to one.

### Documentation/traceability

4. Add/classify `R10-C48` in `domain-prompt-clause-coverage.md` and update coverage totals.
5. Correct the non-terminating-ratio wording in `domain-quality-metrics.md`.
6. Record V1 audit failure and remediation state without overwriting historical evidence.

### Gates

7. Resolve the global Ruff/format gate mismatch through an explicitly approved, documented remediation policy; do not silently waive it.
8. Rerun all Phase 10.48 focused tests, relevant 10.46/10.47 regressions, domain suite, global suite, lint/format gates, compileall, diff-check and architecture gates.
9. Commit all remediation.
10. Verify clean worktree and preserved quarantine stash.
11. Generate a **new** exact-HEAD TAR.GZ.
12. Compute a new SHA-256.
13. Submit the new bundle for Independent Re-audit V2.

The V1 bundle must not be replaced or modified.

---

## 11. Final V1 state

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=2
MINORS=2

MAJOR_01=OPEN
MAJOR_02=OPEN
MINOR_01=OPEN
MINOR_02=OPEN

DP-048=IMPLEMENTED_NOT_YET_VERIFIED_FOR_CLOSURE
AT-DP-048=PASS_REPORTED_NOT_SUFFICIENT_FOR_CLOSURE

CLOSURE_ELIGIBLE=NO
PHASE10_48=CANNOT_CLOSE

AUDITED_IMPLEMENTATION_HEAD=f588c7b79fa122698ef578adc6cf57397fe0eca7
AUDIT_BUNDLE_SHA256=aadc6b9a1b04c5c8cafa493429b89d8db9f7306ef50fff360eabc2ba4a65e931

NEXT=PHASE_10_48_REMEDIATION
```
