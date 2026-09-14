# CMM OS — Phase 10.47 — Independent Re-audit V2 (Corrected)

**Audit date:** 2026-09-10
**Phase:** 10.47 — Domain Benchmark Suites
**Design Point:** DP-047 — Portable, Model-Agnostic Domain Benchmark Suites
**Acceptance:** AT-DP-047 — Connected Domain Benchmark Asset Acceptance
**Audit type:** Independent exact-HEAD remediation re-audit
**Verdict:** **FAIL — remediation V2 required**
**Correction note:** This corrected report supersedes an uncommitted draft that incorrectly classified generated cache artifacts as tracked Git content. Fresh direct archive inspection proved both the V1 and V2 `git archive` bundles contain zero tracked `__pycache__`, `.pyc`, or `.pytest_cache` files. That discarded draft was never committed and is not audit evidence.

---

## Audited artifact

```text
BUNDLE=phase-10.47-reaudit-v2-240af985a78f68488d069582ae9f8d554767f7da.tar.gz
AUDITED_REMEDIATION_HEAD=240af985a78f68488d069582ae9f8d554767f7da
AUDIT_BUNDLE_SHA256=291b1b18b40d552d170ab5782ea43174030cc5d721fdcc26b1b1679fbc0998b7
```

Independent artifact verification:

```text
SHA256_MATCH_REPORTED=PASS
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=240af985a78f68488d069582ae9f8d554767f7da
FILENAME_HEAD_MATCH=PASS
EXACT_HEAD_BUNDLE=PASS
ARCHIVE_ENTRY_COUNT=2156
TRACKED_GENERATED_CACHE_FILES=0
```

The prior V1 artifact remains historical evidence:

```text
V1_HEAD=319f9fbc8f75de3d9beadf311df9e1425de18d13
V1_SHA256=4f093fc9a1c3637cb48393a0d1a97c4faeb644790864bff90be3c6bc94450447
V1_TRACKED_GENERATED_CACHE_FILES=0
```

---

# 1. Independent Re-audit V2 result

```text
INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=0
MAJORS=2
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=NOT_VERIFIED_REMEDIATED
MAJOR_03=NOT_VERIFIED_REMEDIATED

DP-047=NOT_VERIFIED
AT-DP-047_TEST_EXECUTION=PASS
AT-DP-047=FAIL_INDEPENDENT_ADEQUACY

CLOSURE_ELIGIBLE=NO
PHASE10_48=NOT_STARTED
```

Phase 10.47 must not be closed.

---

# 2. Independent test execution

The audit container lacks the unrelated `libcst` dependency. As in V1, an external audit-only import stub was used solely to unblock unrelated package imports. It was stored outside the extracted archive and did not replace any Phase 10.47 benchmark behavior.

Fresh independent execution against the exact V2 bundle:

```text
FOCUSED_PHASE10_47=227 PASSED
PHASE10_46_REGRESSIONS=104 PASSED
```

The focused suite includes:

```text
tests/domains/test_domain_benchmark_contracts.py
tests/domains/test_domain_benchmark_pack_integration.py
tests/domains/test_domain_benchmark_first_party.py
tests/domains/test_domain_benchmark_architecture.py
tests/domains/test_domain_benchmark_dp047_acceptance.py
```

The increase from V1's 170 focused tests to 227 confirms substantial remediation coverage was added.

A wider pack/loader/public-API sweep was attempted. Its first failure was environmental: a subprocess launched from a temporary directory could not import the extracted `cmm` package because the audit archive is not installed into that subprocess environment. That failure is not attributed to Phase 10.47.

---

# 3. V1 MAJOR-01 — VERIFIED REMEDIATED

## Finding

```text
MAJOR_01=DECLARATIVE_PACK_BENCHMARK_PATH_MISSING
```

## Independent verification

The audited remediation extends the existing canonical declarative pack path:

```text
DomainManifest declarative-known fields
    -> benchmark_suites recognized
ParsedDomainPack.from_declarative_dict(...)
    -> DomainBenchmarkSuite.from_dict(...)
    -> DomainDefinition(..., benchmark_suites=...)
DeclarativeDomainLoader
    -> existing canonical loader / registry / validation path
```

No benchmark-specific loader was introduced.

Fresh direct probe:

```text
DECLARATIVE_BENCHMARK_PARSE=PASS
DECLARATIVE_BENCHMARK_SUITE_COUNT=1
DECLARATIVE_BENCHMARK_CASE_COUNT=1
REAL_LOADER_BENCHMARK_PACK=PASS
MALFORMED_DECLARATIVE_BENCHMARK=REJECTED
```

The implementation also contains focused fail-closed declarative tests for:

```text
invalid benchmark_suites container
non-mapping suite entries
unknown suite fields
unknown case fields
suite/definition domain mismatch
case/suite domain mismatch
duplicate suite IDs
duplicate case IDs
invalid maximum cost
reserved metadata authority
```

AT-DP-047 now exercises the real declarative loader path.

## Verdict

```text
MAJOR_01=VERIFIED_REMEDIATED
```

No further architectural change is required for MAJOR-01. Preserve this implementation and regression-test it during the next remediation.

---

# 4. V1 MAJOR-02 — PARTIALLY REMEDIATED, BUT DIRECT AUTHORITY ALIASES REMAIN

## Finding

```text
MAJOR_02=BENCHMARK_AUTHORITY_VALIDATION_MISSCOPED
```

## What is correctly fixed

The schema/metadata validation responsibilities are now separated.

`required_schema` uses generic JSON-safe/deep-freezing validation without model/provider authority scanning.

Benchmark `metadata` uses generic JSON validation plus recursive normalized authority-key rejection.

Fresh direct probe:

```text
SCHEMA_PROVIDER_FIELD=ACCEPTED
SCHEMA_MODEL_FIELD=ACCEPTED

preferred_model=REJECTED
candidate_model=REJECTED
preferred_provider=REJECTED
candidate_provider=REJECTED
preferredModel=REJECTED
candidateProvider=REJECTED
preferred-model=REJECTED
routingWeight=REJECTED
NESTED_METADATA_AUTHORITY=REJECTED
ORDINARY_METADATA_PROSE=ACCEPTED
```

This successfully fixes the concrete V1 examples.

## Residual defect

The implementation still relies on a finite exact-key denylist after normalization.

Obvious authority-bearing compound aliases remain accepted.

Fresh independent reproduction:

```text
preferred_model_id=ACCEPTED
candidate_model_id=ACCEPTED
prohibited_model_id=ACCEPTED

preferred_provider_id=ACCEPTED
candidate_provider_id=ACCEPTED
prohibited_provider_id=ACCEPTED

model_preference=ACCEPTED
provider_preference=ACCEPTED
routing_model=ACCEPTED
routing_provider=ACCEPTED
```

At minimum, keys such as:

```text
preferred_model_id
candidate_model_id
preferred_provider_id
candidate_provider_id
```

are direct semantic equivalents of the model/provider authority the Phase 10.46/10.47 boundary is intended to prohibit.

They are not ordinary prose or incidental uses of the words `model` or `provider`.

The approved remediation design requires benchmark metadata not to become an authority channel and requires obvious model/provider authority aliases to fail closed.

## Impact

A future consumer of benchmark metadata can still encounter explicit candidate/preference/provider identifiers inside a supposedly model-agnostic Domain benchmark asset.

The Phase 10.46 model/provider-authority boundary is therefore not yet enforced as a durable Phase 10.47 contract.

## Required remediation

Do not introduce fuzzy natural-language matching.

Extend deterministic normalized-key authority detection so direct compound authority aliases are also rejected.

A narrow acceptable rule is to reject normalized metadata keys that encode combinations such as:

```text
(candidate|preferred|prohibited)_(model|provider)
(candidate|preferred|prohibited)_(model|provider)_(id|ids)
(model|provider)_(candidate|preference|preferred|prohibited)
routing_(model|provider)
```

while retaining explicit exact reserved keys such as:

```text
model
models
model_id
model_ids
provider
providers
provider_id
provider_ids
routing_weight
routing_weights
```

The exact implementation may use a small deterministic pattern/table.

It must not reject unrelated keys such as:

```text
modeling_notes
provider_context_description
```

Add RED/GREEN tests and strengthen AT-DP-047 Scenario F.

## Verdict

```text
MAJOR_02=NOT_VERIFIED_REMEDIATED
```

---

# 5. V1 MAJOR-03 — EQUIVALENT EXAMPLES FIXED, BUT PRECISION-SAFE CANONICALIZATION IS STILL BROKEN

## Finding

```text
MAJOR_03=NON_CANONICAL_COST_DIGEST
```

## What is correctly fixed

The remediation added canonicalization for the concrete equality groups required by the V1 plan.

Fresh independent reproduction:

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

DISTINCT_COST_EXPORT_DIFFERENT=True
DISTINCT_COST_DIGEST_DIFFERENT=True
```

## Residual defect

The implementation uses:

```python
value.normalize()
```

inside Decimal canonicalization.

`Decimal.normalize()` is context-sensitive. It applies the active Decimal context precision before reducing the exponent.

Therefore the current helper can round a valid `maximum_cost_eur`, losing numeric precision and making export/digest depend on ambient process state.

Fresh independent reproduction using the default audit context:

```text
ORIG=123456789012345678901234567890.123456789
SER=123456789012345678901234567900
ROUNDTRIP_EQUAL=False
ROUNDTRIP=123456789012345678901234567900
```

A second valid high-precision cost shows the same problem:

```text
ORIG=0.123456789012345678901234567890123456789
SER=0.1234567890123456789012345679
ROUNDTRIP_EQUAL=False
```

This directly violates the approved requirement that cost serialization be:

```text
precision-preserving
```

and that:

```text
Decimal -> canonical decimal string -> Decimal
```

remain numerically exact.

## Ambient-context nondeterminism

The same valid benchmark suite serializes differently depending only on the active Decimal context:

```text
PREC10_SER=123456789000000000000000000000
PREC50_SER=123456789012345678901234567890.123456789

CONTEXT_INDEPENDENT_EXPORT=False
CONTEXT_INDEPENDENT_DIGEST=False
```

That violates the core DP-047 reproducibility and deterministic-export requirement.

## Required remediation

Do not use context-sensitive `Decimal.normalize()` for canonicalization.

Canonical text must be derived exactly from the Decimal's coefficient and exponent, for example via:

```python
value.as_tuple()
```

or another context-independent representation.

Required properties:

```text
no float conversion
no context-dependent arithmetic
no rounding
equal numeric values -> identical text
distinct numeric values -> distinct text
round-trip numerically exact
zero canonicalized to "0"
canonical export independent of decimal.getcontext().prec
canonical digest independent of decimal.getcontext().prec
```

Add focused tests covering:

```text
very high precision
large positive exponent
small negative exponent within reasonable test size
different localcontext().prec values
round-trip exactness
```

The direct remediation gate must include:

```text
HIGH_PRECISION_ROUNDTRIP=True
DECIMAL_CONTEXT_INDEPENDENT_EXPORT=True
DECIMAL_CONTEXT_INDEPENDENT_DIGEST=True
```

## Verdict

```text
MAJOR_03=NOT_VERIFIED_REMEDIATED
```

---

# 6. Correction of discarded cache finding

An earlier uncommitted draft of this Re-audit V2 incorrectly inferred that generated caches had entered Git because cache files appeared in extracted audit working directories after tests were executed there.

That inference was wrong.

Fresh direct inspection of the archive member lists proves:

```text
V1_TRACKED_GENERATED_CACHE_FILES=0
V2_TRACKED_GENERATED_CACHE_FILES=0
```

Repository-side independent confirmation after the audit also showed:

```text
240af985a78f68488d069582ae9f8d554767f7da CACHE_FILES=0
58e4b278946b7cbc795f7073cef5e84e3ec59c4c CACHE_FILES=0
```

Therefore:

```text
MAJOR_04=WITHDRAWN_FALSE_POSITIVE
```

`MAJOR_04` is not part of the canonical V2 verdict and must not be recorded as an open Phase 10.47 finding.

The discarded draft was never committed.

---

# 7. Post-audit commit classification

After the exact audited V2 HEAD, the repository acquired one direct child commit:

```text
POST_AUDIT_HEAD=58e4b278946b7cbc795f7073cef5e84e3ec59c4c
PARENT=240af985a78f68488d069582ae9f8d554767f7da
SUBJECT=test(pytest): retain temp artifacts only on failure
```

Exact scope:

```text
pytest.ini | 4 +++-
1 file changed, 3 insertions(+), 1 deletion(-)
```

Patch:

```text
pythonpath = .
tmp_path_retention_count = 1
tmp_path_retention_policy = failed
```

This commit:

- is not part of the exact audited V2 bundle;
- does not modify Phase 10.47 production contracts;
- does not remediate MAJOR-02 or MAJOR-03;
- contains no tracked generated caches;
- may be preserved as the baseline for the next remediation;
- must be included and re-tested in the next exact-HEAD bundle.

It must not be retrospectively treated as part of Re-audit V2.

---

# 8. Architecture boundary review

Independent static checks on the V2 bundle found no forbidden benchmark subsystem:

```text
DOMAIN_BENCHMARK_REGISTRY=ABSENT
DOMAIN_BENCHMARK_RUNNER=ABSENT
BENCHMARK_EXECUTION_ENGINE=ABSENT
DOMAIN_QUALITY_METRICS_IMPLEMENTED=NO
PHASE11_MODEL_EVALUATION_FRAMEWORK_IMPLEMENTED=NO
REVERSE_BENCHMARK_DEPENDENCY=NONE
MODEL_PROVIDER_RUNTIME_INVOCATION=NONE
```

No Phase 10.48 implementation was identified.

The declarative pack remediation uses the existing pack/loader path rather than a parallel loader.

These architectural boundaries remain sound.

---

# 9. Documentation state

The audited V2 live documentation remains appropriately pre-audit.

Verified markers include:

```text
PHASE10_47=REMEDIATION_V1_IMPLEMENTED_PENDING_REAUDIT
INDEPENDENT_AUDIT_V1=FAIL
MAJOR_01=REMEDIATED_PENDING_INDEPENDENT_VERIFICATION
MAJOR_02=REMEDIATED_PENDING_INDEPENDENT_VERIFICATION
MAJOR_03=REMEDIATED_PENDING_INDEPENDENT_VERIFICATION
DP-047=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-047=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
PHASE10_48=NOT_STARTED
```

No Phase 10.47 premature closure marker was identified.

Because Re-audit V2 fails, the next remediation cycle must preserve this conservative state and record the corrected V2 FAIL before implementation.

---

# 10. DP-047 evaluation

Phase 10.47 now correctly provides:

```text
declarative pack portability
real loader preservation
first-party benchmark assets
schema/metadata separation
basic normalized metadata authority protection
basic canonical Decimal equivalence groups
no benchmark runtime
no benchmark registry
no Phase 10.48 quality metrics
no Phase 11 model-evaluation execution
```

However DP-047 still requires benchmark assets to be:

```text
model-agnostic
reproducible
portable
deterministic
auditable
```

The remaining direct metadata authority aliases violate model-agnostic durability.

The context-sensitive, precision-losing Decimal serialization violates reproducibility and deterministic content identity.

Therefore:

```text
DP-047=NOT_VERIFIED
```

---

# 11. AT-DP-047 evaluation

The strengthened acceptance module executes successfully:

```text
AT-DP-047_TEST_EXECUTION=PASS
```

It now adequately exercises:

```text
canonical declarative pack path
real loader preservation
the concrete V1 schema/metadata examples
the concrete V1 Decimal equality groups
```

However it still misses:

```text
authority-bearing compound aliases such as preferred_model_id
high-precision Decimal round-trip preservation
Decimal context independence
```

Therefore:

```text
AT-DP-047=FAIL_INDEPENDENT_ADEQUACY
```

---

# 12. Required Remediation V2 scope

The next remediation must be narrow.

## Preserve MAJOR-01

No design or production rewrite is required.

Regression-test the current declarative pack fix only.

## Open MAJOR-02

Strengthen metadata authority-key detection for direct compound authority aliases while avoiding fuzzy prose/substrings.

Required direct examples include:

```text
preferred_model_id=REJECTED
candidate_model_id=REJECTED
prohibited_model_id=REJECTED
preferred_provider_id=REJECTED
candidate_provider_id=REJECTED
prohibited_provider_id=REJECTED
routing_model=REJECTED
routing_provider=REJECTED
```

and negative controls such as:

```text
modeling_notes=ACCEPTED
provider_context_description=ACCEPTED
```

## Open MAJOR-03

Replace context-sensitive Decimal canonicalization with an exact, context-independent implementation.

Required direct evidence:

```text
HIGH_PRECISION_ROUNDTRIP=True
DECIMAL_CONTEXT_INDEPENDENT_EXPORT=True
DECIMAL_CONTEXT_INDEPENDENT_DIGEST=True
```

while retaining all previous equality-group behavior.

## Post-audit pytest.ini commit

Preserve `58e4b278946b7cbc795f7073cef5e84e3ec59c4c` unless a regression proves it problematic.

It must simply be included in the next implementation/audit HEAD and subjected to the normal global gates.

---

# 13. Required gates before Re-audit V3

At minimum:

```text
focused Phase 10.47
declarative pack/loader regressions
Phase 10.46 regressions
Domain subsystem
global suite
Ruff remediation-changed Python files
format remediation-changed Python files
compileall
git diff --check
anti-fragmentation
reverse benchmark dependency
MAJOR-01 regression probe
metadata authority direct probe
high-precision Decimal round-trip probe
Decimal context-independence export/digest probes
```

Required direct outputs include:

```text
MAJOR_01_DECLARATIVE_PACK=PASS

preferred_model_id=REJECTED
candidate_model_id=REJECTED
preferred_provider_id=REJECTED
candidate_provider_id=REJECTED
modeling_notes=ACCEPTED
provider_context_description=ACCEPTED

HIGH_PRECISION_ROUNDTRIP=True
DECIMAL_CONTEXT_INDEPENDENT_EXPORT=True
DECIMAL_CONTEXT_INDEPENDENT_DIGEST=True
```

Then:

```text
all remediation changes committed
worktree clean
quarantine stash preserved
new exact-HEAD git archive
new SHA-256
independent Re-audit V3
```

Do not modify or overwrite the V1/V2 bundles.

---

# 14. Final corrected verdict

```text
PHASE10_47=REMEDIATION_V2_REQUIRED

INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=0
MAJORS=2
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=NOT_VERIFIED_REMEDIATED
MAJOR_03=NOT_VERIFIED_REMEDIATED
MAJOR_04=WITHDRAWN_FALSE_POSITIVE

DP-047=NOT_VERIFIED
AT-DP-047_TEST_EXECUTION=PASS
AT-DP-047=FAIL_INDEPENDENT_ADEQUACY

CLOSURE_ELIGIBLE=NO
PHASE10_48=NOT_STARTED

AUDITED_REMEDIATION_HEAD=240af985a78f68488d069582ae9f8d554767f7da
AUDIT_BUNDLE_SHA256=291b1b18b40d552d170ab5782ea43174030cc5d721fdcc26b1b1679fbc0998b7

POST_AUDIT_HEAD=58e4b278946b7cbc795f7073cef5e84e3ec59c4c
POST_AUDIT_COMMIT_SCOPE=pytest.ini_only
POST_AUDIT_COMMIT_INCLUDED_IN_V2_AUDIT=NO
```

Phase 10.47 is not closure-eligible until MAJOR-02 and MAJOR-03 are corrected and independently re-audited.

No docs-only closure commit is permitted from this verdict.
