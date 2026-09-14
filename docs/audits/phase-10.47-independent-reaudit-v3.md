# CMM OS — Phase 10.47 — Independent Re-audit V3

**Audit date:** 2026-09-10
**Phase:** 10.47 — Domain Benchmark Suites
**Design Point:** DP-047 — Portable, Model-Agnostic Domain Benchmark Suites
**Acceptance:** AT-DP-047 — Connected Domain Benchmark Asset Acceptance
**Audit type:** Independent exact-HEAD remediation re-audit
**Verdict:** **FAIL — one documentation-only MINOR remains**

---

## Audited artifact

```text
BUNDLE=phase-10.47-reaudit-v3-ef41ba0074621412089b15b501be7e17f7b81140.tar.gz
AUDITED_REMEDIATION_HEAD=ef41ba0074621412089b15b501be7e17f7b81140
AUDIT_BUNDLE_SHA256=38fd8aeea739f69599e6b9eb644f73cb042084ab22bbb51e68baa6d7f41453f9
```

Independent artifact verification:

```text
SHA256_MATCH_REPORTED=PASS
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=ef41ba0074621412089b15b501be7e17f7b81140
FILENAME_HEAD_MATCH=PASS
EXACT_HEAD_BUNDLE=PASS
ARCHIVE_ENTRY_COUNT=2159
TRACKED_GENERATED_CACHE_FILES=0
```

The V1 and V2 audit bundles remain separate historical evidence.

---

# 1. Independent Re-audit V3 result

```text
INDEPENDENT_REAUDIT_V3=FAIL

BLOCKERS=0
MAJORS=0
MINORS=1

MINOR_01=ROADMAP_PHASE10_47_DUPLICATE_STATUS_STALE

MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
MAJOR_03=VERIFIED_REMEDIATED
MAJOR_04=WITHDRAWN_FALSE_POSITIVE

DP-047=VERIFIED_EXISTING
AT-DP-047_TEST_EXECUTION=PASS
AT-DP-047=PASS

CLOSURE_ELIGIBLE=NO
PHASE10_48=NOT_STARTED
```

The Phase 10.47 implementation and acceptance behavior are independently verified.

Closure is blocked solely because one live `ROADMAP.md` status section is stale and contradicts the current Phase 10.47 remediation/audit state.

---

# 2. Exact-head scope review

Fresh comparison of the exact V2 and V3 archives found:

```text
V2_TO_V3_ADDED_FILES=3
V2_TO_V3_CHANGED_FILES=8
V2_TO_V3_REMOVED_FILES=0
```

Added:

```text
docs/audits/phase-10.47-independent-reaudit-v2.md
docs/superpowers/plans/2026-09-10-phase-10.47-remediation-v2-implementation-plan.md
docs/superpowers/specs/2026-09-10-phase-10.47-remediation-v2-design-amendment.md
```

Changed:

```text
ROADMAP.md
cmm/domains/benchmark_contracts.py
docs/reference/domain-benchmark-suites.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
pytest.ini
tests/domains/test_domain_benchmark_contracts.py
tests/domains/test_domain_benchmark_dp047_acceptance.py
```

This matches the expected remediation history:

- the post-audit `pytest.ini` retention commit is preserved;
- the corrected V2 report/design/plan are preserved;
- production semantic change is confined to `benchmark_contracts.py`;
- MAJOR-01 production files `manifest.py` / `pack.py` are unchanged;
- no Kernel or Agent Runtime production change is present.

No generated caches are tracked in the V3 archive.

---

# 3. Independent test execution

The audit environment does not provide the unrelated `libcst` dependency. An external audit-only stub was used solely to unblock package imports for Domain benchmark tests; it was outside the extracted archive and did not replace Phase 10.47 behavior.

Fresh execution against the exact V3 bundle:

```text
FOCUSED_PHASE10_47=296 PASSED
```

Modules:

```text
tests/domains/test_domain_benchmark_contracts.py
tests/domains/test_domain_benchmark_pack_integration.py
tests/domains/test_domain_benchmark_first_party.py
tests/domains/test_domain_benchmark_architecture.py
tests/domains/test_domain_benchmark_dp047_acceptance.py
```

Fresh execution of the real declarative-loader Scenario B plus Phase 10.46 model-policy regressions:

```text
SCENARIO_B_PLUS_PHASE10_46=105 PASSED
PHASE10_46_REGRESSIONS=104 PASSED
```

Independent audit-side quality checks:

```text
COMPILEALL=PASS
TRAILING_WHITESPACE_CHANGED_SURFACE=PASS
```

Ruff is not installed in the independent audit container, so the reported Ruff/format/global-suite results cannot be reproduced here. The implementation report states:

```text
RUFF_CHANGED_FILES=PASS
FORMAT_CHANGED_FILES=PASS
DOMAIN_SUBSYSTEM=10400 passed
GLOBAL_SUITE=16161 passed
```

Those agent-reported results are supporting evidence, not the basis of the semantic PASS.

A full independent `tests/domains` collection in the audit container hits the same Python 3.13 dataclass/zero-argument-`super()` collection issue reproduced on the prior V2 archive in legacy Domain remediation tests. It is pre-existing relative to this remediation and is not attributed to Phase 10.47.

---

# 4. MAJOR-01 — VERIFIED REMEDIATED

Status entering V3:

```text
MAJOR_01=VERIFIED_REMEDIATED
```

The V3 remediation did not modify the verified declarative pack architecture.

Independent connected execution confirms the canonical path remains green:

```text
declarative Domain Pack mapping
→ canonical declarative parser
→ DomainBenchmarkSuite.from_dict(...)
→ DomainDefinition.benchmark_suites
→ DeclarativeDomainLoader
→ existing registry/validation path
```

The real Scenario B acceptance test passes.

No benchmark-specific loader was introduced.

Verdict:

```text
MAJOR_01=VERIFIED_REMEDIATED
```

---

# 5. MAJOR-02 — VERIFIED REMEDIATED

## V2 defect

Re-audit V2 showed direct compound authority aliases still passed, including:

```text
preferred_model_id
candidate_model_id
preferred_provider_id
candidate_provider_id
model_preference
provider_preference
routing_model
routing_provider
```

## V3 implementation

`benchmark_contracts.py` now applies a narrow tokenized authority grammar over normalized metadata keys while preserving the schema/metadata separation.

The rule remains:

```text
deterministic
key-based
recursive
non-fuzzy
metadata-only
```

`required_schema` is not authority-scanned.

## Independent required probes

All required direct aliases are rejected:

```text
preferred_model_id=REJECTED
candidate_model_id=REJECTED
prohibited_model_id=REJECTED

preferred_provider_id=REJECTED
candidate_provider_id=REJECTED
prohibited_provider_id=REJECTED

model_preference=REJECTED
provider_preference=REJECTED
routing_model=REJECTED
routing_provider=REJECTED

preferredModelId=REJECTED
preferred-model-id=REJECTED
candidateProviderId=REJECTED
routingProvider=REJECTED

NESTED_PREFERRED_MODEL_ID=REJECTED
```

Negative controls remain accepted:

```text
modeling_notes=ACCEPTED
provider_context_description=ACCEPTED
model_output_description=ACCEPTED
provider_response_format=ACCEPTED
routing_explanation=ACCEPTED
```

Schema properties named:

```text
provider
model
provider_id
model_id
```

remain accepted.

## Independent grammar stress test

A generated matrix covering qualifier-first, subject-first and routing authority forms across:

```text
snake_case
camelCase
PascalCase
kebab-case
space-separated
UPPERCASE
```

produced:

```text
GRAMMAR_CASES=642
GRAMMAR_MISSES=0

NEGATIVE_CONTROLS=8
FALSE_POSITIVES=0
```

This goes beyond the fixed examples in the remediation prompt and confirms the deterministic grammar behaves as designed.

Verdict:

```text
MAJOR_02=VERIFIED_REMEDIATED
```

---

# 6. MAJOR-03 — VERIFIED REMEDIATED

## V2 defect

The previous implementation used context-sensitive:

```python
Decimal.normalize()
```

which could round valid benchmark costs and make export/digest depend on ambient Decimal precision.

## V3 implementation

Canonical cost text is now built directly from:

```python
Decimal.as_tuple()
```

using exact coefficient and exponent placement.

The implementation does not use:

```text
float conversion
normalize()
quantize()
context-dependent rounding arithmetic
```

## Independent required probes

Canonical equality groups pass:

```text
SEMANTIC_025_EQUAL=True
EXPORT_025_EQUAL=True
DIGEST_025_EQUAL=True

SEMANTIC_1000_EQUAL=True
EXPORT_1000_EQUAL=True
DIGEST_1000_EQUAL=True

SEMANTIC_ZERO_EQUAL=True
EXPORT_ZERO_EQUAL=True
DIGEST_ZERO_EQUAL=True
```

High-precision and exponent cases round-trip exactly:

```text
123456789012345678901234567890.123456789
→ exact round-trip

0.123456789012345678901234567890123456789
→ exact round-trip

1E+30
→ 1000000000000000000000000000000
→ exact round-trip

1E-30
→ 0.000000000000000000000000000001
→ exact round-trip
```

Context independence was verified under:

```text
prec=6
prec=10
prec=28
prec=50
prec=100
```

with:

```text
DECIMAL_CONTEXT_INDEPENDENT_TO_DICT=True
DECIMAL_CONTEXT_INDEPENDENT_EXPORT=True
DECIMAL_CONTEXT_INDEPENDENT_DIGEST=True
```

## Independent randomized property probe

300 deterministic random finite non-negative Decimal values were tested with:

- coefficient lengths up to 80 digits;
- exponents from `-50` through `+50`;
- Decimal contexts `6/10/28/50/100`;
- semantically equivalent representations produced by appending coefficient zeros and compensating the exponent.

Result:

```text
RANDOM_CASES=300
ROUNDTRIP_FAILURES=0
CONTEXT_FAILURES=0
EQUIVALENT_REPRESENTATION_FAILURES=0
```

This independently verifies the exactness and reproducibility property beyond the required fixtures.

Verdict:

```text
MAJOR_03=VERIFIED_REMEDIATED
```

---

# 7. Architecture review

Independent static and executable checks confirm:

```text
DOMAIN_BENCHMARK_REGISTRY=ABSENT
DOMAIN_BENCHMARK_RUNNER=ABSENT
BENCHMARK_EXECUTION_ENGINE=ABSENT
DOMAIN_QUALITY_METRICS_IMPLEMENTED=NO
PHASE11_MODEL_EVALUATION_FRAMEWORK_IMPLEMENTED=NO
REVERSE_BENCHMARK_DEPENDENCY=NONE
MODEL_PROVIDER_RUNTIME_INVOCATION=NONE
```

The Phase 10.46 model/provider authority boundary is preserved.

The Phase 10.47 benchmark layer remains declarative.

Phase 10.48 has not been implemented.

No architecture MAJOR remains.

---

# 8. AT-DP-047 evaluation

The connected acceptance suite executes successfully inside the focused run.

V3 now covers:

```text
A — first-party benchmark coverage
B — real declarative pack/loader preservation
C — deterministic export, semantic Decimal equality, high precision and context independence
D — semantic mutation changes digest
E — fail-closed ownership
F — schema/metadata separation and compound authority grammar
G — Phase 10.48 boundary
H — no benchmark execution
I — privacy/cost preservation
J — Phase 10.46 coexistence
```

Independent semantic stress probes did not reveal a bypass in the strengthened Scenario C or F guarantees.

Verdict:

```text
AT-DP-047_TEST_EXECUTION=PASS
AT-DP-047=PASS
```

---

# 9. DP-047 evaluation

The implementation now demonstrates the complete DP-047 contract:

```text
portable
typed
immutable
versioned
declarative-pack owned
model/provider agnostic
schema-safe
metadata-authority safe
precision-preserving
context-independent
deterministic
exportable
content-digest reproducible
first-party populated
future-evaluation compatible
no benchmark runtime
no benchmark registry
no Phase 10.48 metrics
no Phase 11 model execution
```

Verdict:

```text
DP-047=VERIFIED_EXISTING
```

---

# 10. MINOR-01 — stale duplicate live Phase 10.47 status in ROADMAP.md

## Finding

```text
MINOR_01=ROADMAP_PHASE10_47_DUPLICATE_STATUS_STALE
```

The top Phase 10.47 status in `ROADMAP.md` is correctly updated to Remediation V2 pending Re-audit V3.

However a later live `Phase 10 — Domain Intelligence` status block still states:

```text
Next action: Phase 10.47 remediation V1 is implemented and pending independent Re-audit V2
```

and the following Phase 10.47 summary still records:

```text
PHASE10_47=REMEDIATION_V1_IMPLEMENTED_PENDING_REAUDIT
MAJOR_01=REMEDIATED_PENDING_INDEPENDENT_VERIFICATION
MAJOR_02=REMEDIATED_PENDING_INDEPENDENT_VERIFICATION
MAJOR_03=REMEDIATED_PENDING_INDEPENDENT_VERIFICATION
audit report docs/audits/phase-10.47-independent-audit-v1.md
```

This contradicts the current live state already recorded elsewhere in the same file and in:

```text
docs/reference/domain-benchmark-suites.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
```

where:

```text
PHASE10_47=REMEDIATION_V2_IMPLEMENTED_PENDING_REAUDIT
MAJOR_01=VERIFIED_REMEDIATED
INDEPENDENT_REAUDIT_V2=FAIL
```

are correctly represented.

## Severity rationale

This is documentation-only.

It does not affect production code, benchmark contracts, security, DP behavior or AT behavior.

It is nevertheless a live roadmap inconsistency and must be corrected before closure because the CMM OS phase workflow requires roadmap/reference state to be coherent before declaring the phase closed.

Therefore:

```text
MINOR
```

not MAJOR.

## Required remediation

Update only the stale live Phase 10.47 block in `ROADMAP.md`.

After recording this V3 report, the corrected live status should reflect:

```text
Independent Re-audit V3=FAIL
BLOCKERS=0
MAJORS=0
MINORS=1

MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
MAJOR_03=VERIFIED_REMEDIATED
MAJOR_04=WITHDRAWN_FALSE_POSITIVE

DP-047=VERIFIED_EXISTING
AT-DP-047=PASS

MINOR_01=REMEDIATION_PENDING
CLOSURE_ELIGIBLE=NO
PHASE10_48=NOT_STARTED
```

Do not change code.

Do not reopen MAJOR-01/02/03.

After the docs-only remediation:

```text
run documentation consistency guards
run git diff --check
run focused Phase 10.47 as regression evidence
run Phase 10.46 regressions
create a new exact-HEAD Re-audit V4 bundle
independent Re-audit V4
```

---

# 11. Documentation review

Correct/current:

```text
docs/reference/domain-benchmark-suites.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md top Phase 10.47 status
```

Stale:

```text
ROADMAP.md later Phase 10 — Domain Intelligence "Next action" / Phase 10.47 summary block
```

Historical audit/spec/plan references to older remediation states are intentionally historical and are not findings.

---

# 12. Closure decision

Functional and architectural closure requirements are now satisfied:

```text
BLOCKERS=0
MAJORS=0
DP-047=VERIFIED_EXISTING
AT-DP-047=PASS
```

However the CMM OS workflow also requires live documentation consistency before closure.

Because `MINOR_01` requires correction:

```text
CLOSURE_ELIGIBLE=NO
```

The next cycle is documentation-only.

No production remediation is authorized or required.

---

# 13. Final verdict

```text
PHASE10_47=DOCS_ONLY_REMEDIATION_REQUIRED

INDEPENDENT_REAUDIT_V3=FAIL

BLOCKERS=0
MAJORS=0
MINORS=1

MINOR_01=ROADMAP_PHASE10_47_DUPLICATE_STATUS_STALE

MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
MAJOR_03=VERIFIED_REMEDIATED
MAJOR_04=WITHDRAWN_FALSE_POSITIVE

DP-047=VERIFIED_EXISTING
AT-DP-047_TEST_EXECUTION=PASS
AT-DP-047=PASS

CLOSURE_ELIGIBLE=NO
PHASE10_48=NOT_STARTED

AUDITED_REMEDIATION_HEAD=ef41ba0074621412089b15b501be7e17f7b81140
AUDIT_BUNDLE_SHA256=38fd8aeea739f69599e6b9eb644f73cb042084ab22bbb51e68baa6d7f41453f9
```

The implementation itself is independently verified.

The only remaining work before closure is a narrow `ROADMAP.md` documentation correction followed by an exact-HEAD Re-audit V4.

No Phase 10.48 work is authorized.
