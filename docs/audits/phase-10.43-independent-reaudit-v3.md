# CMM OS — Phase 10.43 Independent Re-Audit V3

**Phase:** 10.43 — Integration with Validation System
**Audit:** Independent ChatGPT Re-Audit V3
**Date:** 2026-09-07
**Bundle:** `phase-10.43-audit-v3-edfd853c3b6197a7e84137e538ec6f37f5b02230.tar.gz`
**Audited implementation HEAD:** `edfd853c3b6197a7e84137e538ec6f37f5b02230`
**Bundle SHA-256:** `7176bb459fae33fe1fdccbed612c4cc0fbf0338e152a48b0ebb1238754e76280`
**Historical V2 audited implementation HEAD:** `6faa26fec6fd835ca0f47b1c093020c83bddb67a`
**Design Point:** `DP-043`
**Connected Acceptance:** `AT-DP-043`

---

## Final verdict

```text
AUDIT_RESULT=FAIL

BLOCKERS=3
MAJORS=1
MINORS=0

DP-043=NOT_VERIFIED
AT-DP-043=FAIL
CLOSURE_ELIGIBLE=NO
```

Phase 10.43 is **not yet eligible for closure**.

V3 materially remediates the V2 provider-omission bypass and makes specialized-result acceptance provider-independent. The Project Domain policy is also materially closer to the approved design.

However, the V3 Project acceptance is still a false positive for the specific `affected_tests` guarantee, and the newly added Project impact / changed-file channels are not populated by any production constructor. The acceptance test manually injects both. As a result, the claimed real Project change-policy path is not yet the actual host path required by the approved specification.

---

# 1. Independent bundle verification

## 1.1 SHA-256

Independent calculation:

```text
7176bb459fae33fe1fdccbed612c4cc0fbf0338e152a48b0ebb1238754e76280
```

Matches the implementation handoff.

```text
BUNDLE_SHA256=PASS
```

## 1.2 Archive integrity

Independent checks:

```text
GZIP=PASS
ARCHIVE_ENTRIES=2074
UNSAFE_PATHS=0
```

Single archive root:

```text
CMM-OS-phase-10.43-edfd853c3b6197a7e84137e538ec6f37f5b02230/
```

```text
ARCHIVE_INTEGRITY=PASS
ARCHIVE_PATH_SAFETY=PASS
```

## 1.3 Exact embedded Git HEAD

`git get-tar-commit-id` independently returns:

```text
edfd853c3b6197a7e84137e538ec6f37f5b02230
```

Therefore:

```text
EXACT_HEAD=PASS
```

## 1.4 Independent syntax compilation

The extracted V3 tree was independently checked with:

```text
python -m compileall -q cmm tests
```

Result:

```text
COMPILEALL_AUDITOR=PASS
```

The independent audit environment has `pytest`, but does not have the repository dependencies `libcst` or `ruff`, so the full project suites and Ruff cannot be independently replayed here.

That limitation is not the reason for the FAIL verdict. The blockers below are established directly from committed production and acceptance code.

---

# 2. V2 → V3 remediation matrix

| V2 finding | V3 status | Independent assessment |
|---|---|---|
| BLOCKER-V2-01 — provider omission / empty requirements / specialized result provider condition | **REMEDIATED** | Domain orchestrator fails closed without provider when validation is mandatory; Phase 9 rejects `requires_validation=True` with empty materialized requirements; specialized-result gate is unconditional |
| BLOCKER-V2-02 — ProjectDomainChangePolicy not governing real mutation path | **PARTIALLY REMEDIATED** | canonical small-policy mapping exists, but affected-test/lint results still fail open and production does not derive impact/changed files |
| BLOCKER-V2-03 — AT-DP-043 incomplete | **PARTIALLY REMEDIATED** | V3 acceptance adds scenarios, but Project affected-test and impact-escalation proofs are not connected to the real host path |
| MAJOR-V2-01 — docs mismatch | **PARTIALLY REMEDIATED** | provider documentation is corrected, but Project docs now overstate affected-test and host-owned impact behavior |
| MAJOR-V2-02 — gate evidence missing | **REMEDIATED WITH BASELINE CAVEAT** | V3 evidence records exact full-tree Ruff/format failures and changed-file canonical gates; `CONTRIBUTING.md` defines changed-file Ruff/format as repository canonical practice |

---

# 3. Positive V3 findings

These changes are valid and should be preserved.

## 3.1 Provider omission now fails closed

`DefaultDomainOperationOrchestrator._resolve_host_validation_requirements()` now raises `DomainValidationIntegrationError` when:

```text
operation has mandatory validation
+
operation_validation_provider is None
```

rather than returning an empty requirement set.

This directly remediates the principal V2 provider bypass.

```text
PROVIDER_OMISSION=FAIL_CLOSED
```

## 3.2 Phase 9 now rejects mandatory validation with zero materialized requirements

`AgentExecutionAdapter` now checks:

```python
if requires_val and not request.validation_requirements:
    raise ValidationAdapterError(...)
```

Therefore the common runtime no longer treats:

```text
requires_validation=True
validation_requirements=()
```

as a valid no-op validation.

```text
EMPTY_RUNTIME_REQUIREMENTS=FAIL_CLOSED
```

## 3.3 Specialized-result structural acceptance is provider-independent

The real operation output path now invokes:

```text
_check_specialized_result_acceptance(...)
```

for mapping outputs before accepting success.

That call is no longer conditional on `operation_validation_provider`.

```text
SPECIALIZED_RESULT_GATE=UNCONDITIONAL
```

## 3.4 Project small-policy mapping is now based on canonical Phase 7 policy steps

V3 introduces a deterministic mapping from canonical Project policy steps to executable Phase 9 validator IDs:

```text
formatter_check → formatter_check
lint            → lint
syntax          → syntax_validator
ast             → ast_validator
affected_tests  → affected_tests_step
```

`resolve_project_domain_change_validation_ids()` obtains the required steps from:

```text
build_project_domain_change_policy(...)
```

and fails closed when a mandatory Phase 7 step lacks an executable mapping.

This is directionally correct and should be preserved.

## 3.5 Stronger impacts are not silently downgraded

Structural/public/full policies that contain currently unmappable mandatory steps raise `DomainValidationIntegrationError`.

This is safe fail-closed behavior and preferable to silently falling back to `small`.

## 3.6 No parallel validation infrastructure introduced

Independent source scan finds no production implementation of:

```text
DomainValidationEngine
DomainValidationRuntime
DomainValidationStore
DomainValidationRepository
DomainValidationEventBus
DomainValidationHistory
DomainValidationCommitGate
DomainValidationPolicyRegistry
DomainValidationExecutor
ProjectValidationEngine
CrossDomainValidationEngine
```

```text
ANTI_FRAGMENTATION=PASS
```

## 3.7 V3 remediation evidence is candid about full-tree quality debt

The committed evidence does **not** fabricate Ruff/format PASS.

It records:

```text
RUFF_FULL_GATE=FAIL_PRE_EXISTING_702
FORMAT_FULL_GATE=FAIL_PRE_EXISTING_185
```

and documents changed-file canonical gates as passing.

`CONTRIBUTING.md` explicitly requires Ruff check / format check for changed Python files. This is accepted as repository-canonical phase evidence rather than forcing Phase 10.43 to repair unrelated historical formatting debt.

---

# 4. BLOCKER-V3-01 — `affected_tests` and lint validation still fail open in the canonical Phase 7 command path

**Severity:** BLOCKER
**Scope:** Project Domain small-change policy, Phase 7 validation truth, explicit Phase 10.43 acceptance requirement
**DP impact:** Project code changes can receive false validation success
**AT impact:** the V3 affected-test acceptance scenario is not proving what it claims

## 4.1 `affected_tests_step` allows all normal pytest exit codes

The canonical Phase 7 pytest step builder creates test steps with:

```python
allowed_exit_codes=(0, 1, 2, 3, 4, 5)
```

and metadata:

```python
"result_parser": "pytest"
```

The executor initially marks any allowed exit code as:

```text
ValidationStatus.PASSED
```

Therefore pytest exit `1` is intentionally expected to be reinterpreted later by a pytest result parser.

## 4.2 `CommandResultParser` has no pytest branch

The committed `CommandResultParser.parse()` supports:

```text
ruff / formatter / lint
mypy / type_check
vulture / dead_code
bandit / code_security
pip_audit / dependency_security
```

but has **no** branch for:

```text
pytest
```

Independent source check:

```text
PYTEST_PARSER_BRANCHES=0
```

and:

```text
PARSE_PYTEST_RESULT_CALLS_OUTSIDE_TESTS=0
```

`parse_pytest_result()` exists in:

```text
cmm/validation/testing/pytest_parser.py
```

but is not wired into the production command-result parser.

Consequently:

```text
pytest exit 1
→ allowed exit code
→ generic result PASSED
→ parser="pytest" not recognized
→ generic result returned unchanged
→ affected_tests PASSED
```

This is a fail-open validation bug.

## 4.3 Ruff lint has the same class of fail-open issue for current Ruff JSON output

The V3 implementation-machine evidence correctly notes that current Ruff JSON is a list, while `parse_ruff_results()` only extracts diagnostics from:

```python
payload.get("messages")
```

when `payload` is a mapping.

A normal Ruff lint failure with list-form JSON can therefore produce:

```text
exit 1
→ allowed exit code
→ JSON parses successfully as list
→ messages=None
→ findings=[]
→ ValidationStatus.PASSED
```

This means two of the five canonical `small_change` requirements are not currently trustworthy:

```text
lint
affected_tests
```

The V3 evidence labels these parser issues "out of scope", but Phase 10.43's approved spec explicitly requires the Project Domain to reuse:

```text
format/lint
syntax/AST
affected tests
```

and explicitly requires:

> failing affected test blocks acceptance.

Therefore the parser defects are not out of scope for Phase 10.43 closure. They are minimal necessary corrections to the canonical Phase 7 execution path.

## 4.4 V3 affected-test acceptance is a false positive

The V3 helper `_affected_test_stack(..., break_test=True)` mutates the file to:

```python
def add(a,b):
    return a-b
```

The helper's own docstring explicitly acknowledges that the mutation is also **unformatted**.

Therefore the real operation can be rejected by:

```text
formatter_check
```

before the fact that the affected pytest test fails is ever meaningfully represented in canonical validation truth.

The acceptance then runs pytest separately with `subprocess.run()` and proves that pytest itself returns non-zero.

That demonstrates:

```text
the test is broken
```

but not:

```text
the Phase 7 affected_tests validation step detected and blocked the broken test
```

The two facts are disconnected.

## Impact

The approved specification explicitly requires:

```text
failing affected test blocks acceptance
```

and:

```text
Project Domain code changes fail closed when mandatory validation is unsuccessful
```

Those guarantees are not true while the canonical test/lint result adapters can turn failing commands into `PASSED`.

## Required remediation

This is a **narrow canonical Phase 7 correction**, not a redesign.

At minimum:

1. wire `result_parser="pytest"` to the existing `parse_pytest_result()` implementation in `CommandResultParser`;
2. pass the existing `pytest_junitxml` metadata into that parser;
3. ensure exit 1/2/3/4/5 are converted to the canonical statuses already defined by `parse_pytest_result`;
4. repair `parse_ruff_results()` to accept the actual Ruff list-form JSON while preserving existing mapping compatibility if needed;
5. add Phase 7 regression tests that execute the real parser path, not only parser unit functions;
6. prove `affected_tests` exit 1 becomes `FAILED`;
7. prove Ruff lint diagnostics produce `FAILED`;
8. preserve all existing Phase 7 contracts and result types.

Do not create new parsers or a second executor. Reuse the existing canonical parser implementations.

---

# 5. BLOCKER-V3-02 — Project impact and changed-file scope are still not derived by the real production host path

**Severity:** BLOCKER
**Scope:** `ProjectDomainChangePolicy`, impact escalation, affected-test selection
**DP impact:** caller/default state can weaken Project validation
**AT impact:** the V3 impact scenario is not a real runtime scenario

## 5.1 V3 added request fields, but production does not populate them

V3 adds:

```text
DomainOperationRequest.validation_impact
DomainOperationRequest.validation_changed_files
```

and the orchestrator forwards those values into:

```text
resolve_domain_operation_validation_requirements(...)
```

However independent search across production code finds:

```text
PROD_VALIDATION_IMPACT_ASSIGNMENTS=0
PROD_VALIDATION_CHANGED_FILES_ASSIGNMENTS=0
```

The real production constructors in:

```text
cmm/domains/agent_runtime_integration.py
cmm/domains/operation_execution.py workflow adapter
cmm/domains/operation_execution.py cross-domain port
```

do not derive or set either field.

## 5.2 Missing impact silently becomes `small`

`resolve_project_domain_change_validation_ids()` uses:

```text
small
```

when no impact is supplied.

Therefore the actual production Project path currently behaves as:

```text
project.modify_code
→ no host-derived validation_impact
→ default small
```

regardless of whether the real change is structural, public-contract, broad, or full.

This is not the spec's required semantic impact selection.

## 5.3 Missing changed files weakens affected-test selection

Production also does not populate:

```text
validation_changed_files
```

so the actual Project runtime commonly reaches:

```text
changed_files=()
```

The affected-test selector can then yield no affected tests and return a not-applicable/no-test step instead of testing the actual mutation.

The V3 test helper manually injects:

```text
validation_changed_files=("main.py",)
```

which is not what the production Agent Runtime / workflow / cross-domain constructors currently do.

## 5.4 The new fields are request-controlled, not demonstrably host-owned

`DomainOperationRequest.from_dict()` accepts both fields as ordinary serialized request members.

`DefaultDomainAPI.execute_operation()` accepts a `DomainOperationRequest` and delegates directly to the orchestrator.

Therefore the statement:

```text
validation_impact is host-owned and caller cannot downgrade it
```

is not established merely by moving impact out of `metadata`.

A typed request field can still be caller-controlled.

The current test:

```text
test_caller_cannot_downgrade_project_impact
```

does not exercise a caller/host conflict. It calls the resolver with `impact="small"` and verifies the small policy.

That is not downgrade-resistance evidence.

## 5.5 The V3 AT impact test is not a runtime execution

`test_project_impact_escalation_via_real_runtime()` calls:

```text
resolve_project_domain_change_validation_ids(...)
resolve_domain_operation_validation_requirements(...)
```

directly.

It does not execute:

```text
Agent Runtime
→ Domain dispatch
→ host impact derivation
→ DomainOperationRequest
→ orchestrator
→ AgentValidationAdapter
```

Therefore the test name overstates the connected behavior.

## Impact

The approved spec requires:

> The policy must be selected by semantic operation capability/risk, not by trusting free-form caller metadata.

and requires actual Project impact escalation.

V3 has implemented an impact-aware **resolver**, but it has not connected a trusted impact/scope source to the real Project mutation runtime.

## Required remediation

Use the existing canonical Phase 7 change-impact owner if one exists.

The narrow remediation must:

1. identify the canonical host-owned impact source for a Project mutation;
2. derive impact after/around the actual mutation as appropriate, rather than accepting the caller's requested severity as authority;
3. derive changed-file scope from the real mutation/change set using existing Project/validation change-impact infrastructure;
4. populate the validation requirement context from that canonical host data;
5. ensure caller-provided values cannot lower the derived impact or remove changed files;
6. if a caller-supplied field is retained as a hint, combine it monotonically with host-derived impact and never let it weaken host truth;
7. add a connected test where caller requests `small` but host impact is structural/public and prove the stronger policy wins;
8. add a connected test where caller omits changed files but actual mutation changes `main.py`, and prove affected-test selection still sees `main.py`.

Do not add a new Domain impact engine.

---

# 6. BLOCKER-V3-03 — AT-DP-043 still does not satisfy the approved connected acceptance

**Severity:** BLOCKER
**Scope:** closure acceptance
**Closure impact:** `AT-DP-043=FAIL`

V3 acceptance now correctly proves:

```text
provider omission fails closed
mandatory empty requirements fail closed
specialized-result gate is provider-independent
```

Those scenarios should be preserved.

But the Project portion still fails the approved acceptance standard.

## A. Affected-test scenario

The operation is rejected, but because the changed code is also formatter-invalid.

The test only proves pytest failure in a separate subprocess after the operation result is already known.

It does not prove canonical `affected_tests` caused the rejection.

## B. Impact escalation scenario

The test calls resolver functions directly.

No real host-derived impact enters a real operation request.

No caller-vs-host downgrade conflict is exercised.

No changed-file scope is derived from the actual mutation.

## Required acceptance remediation

Extend AT-DP-043 after BLOCKER-V3-01 and BLOCKER-V3-02 are fixed.

The connected test must prove:

### Affected tests

```text
change is formatter-clean
change is lint-clean
change is syntax-valid
change is AST-valid
affected pytest test fails
→ canonical affected_tests step status = FAILED
→ real project.modify_code is not accepted
```

Then repair the semantic regression and prove acceptance.

### Impact escalation

```text
caller/hint = small
actual host-derived change impact = structural/public
→ stronger canonical policy wins
→ runtime receives stronger requirements or safely fails closed on unmappable mandatory steps
```

### Changed-file derivation

```text
caller omits validation_changed_files
actual mutation changes main.py
→ host-derived validation scope includes main.py
→ affected-test selection uses that scope
```

Only then can the independent auditor verify:

```text
AT-DP-043=PASS
```

---

# 7. MAJOR-V3-01 — documentation and requirements matrix overstate Project runtime guarantees

**Severity:** MAJOR

`docs/reference/domain-validation-integration.md` currently states:

```text
a syntactically valid change that breaks an affected test is rejected
```

and says:

```text
ProjectDomainChangePolicy selected by host-owned impact
resource_scope carrying host-declared changed files
caller metadata cannot lower host-owned impact
```

The detailed roadmap and requirements matrix likewise claim connected Project affected-test rejection and impact escalation.

Those claims are stronger than the audited implementation.

The runtime currently has:

```text
no production assignment of validation_impact
no production assignment of validation_changed_files
pytest result parser not connected
Ruff lint list-form result not correctly interpreted
```

## Required remediation

After the code is corrected, update the documentation to match the actual connected host path.

Until then Phase 10.43 must remain:

```text
IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
```

Do not mark it closed.

---

# 8. Quality-gate assessment

## Implementation-machine evidence

V3 records:

```text
PHASE10_43_FOCUSED_TESTS=281 PASS
VALIDATION_SUITE=527 PASS
AGENT_RUNTIME_SUITE=3434 PASS
DOMAIN_SUITE=9653 PASS
GLOBAL_SUITE=15252 PASS
```

These are implementation-machine results.

The auditor could independently replay compileall, but not the project suites because the audit environment lacks `libcst`.

## Ruff / format

V3 records the full-tree commands and their pre-existing failures:

```text
.venv/bin/python -m ruff check cmm tests
→ 702 pre-existing failures

.venv/bin/python -m ruff format --check cmm tests
→ 185 pre-existing files requiring format
```

The repository's `CONTRIBUTING.md` says:

```text
For changed Python files, run python -m ruff check <changed-python-paths>
and python -m ruff format --check <changed-python-paths>.
```

V3 records those changed-file gates as passing.

Therefore the V2 gate-evidence finding is considered remediated, with the repository-wide debt explicitly preserved as baseline debt rather than silently ignored.

This does **not** excuse new Phase 10.43 files from Ruff/format; the V3 evidence states the V3 delta passes.

---

# 9. DP-043 assessment

V3 now has the correct ownership direction for most of the phase:

```text
Phase 7 validation remains canonical
Phase 9 remains agentic bridge
pack lifecycle is canonical
provider omission is fail-closed
workflow/cross-domain bridges exist
specialized result acceptance is real
```

But DP-043 also requires Project code changes to fail closed when mandatory validation is unsuccessful.

A failing affected test can currently be represented as a canonical `PASSED` step because the pytest result parser is not connected.

The actual runtime also lacks host-derived impact/scope.

Therefore:

```text
DP-043=NOT_VERIFIED
```

---

# 10. AT-DP-043 assessment

Provider and specialized-result sections now pass the connected-architecture standard.

The Project affected-test and impact sections do not.

Therefore:

```text
AT-DP-043=FAIL
```

---

# 11. Required targeted V3 → V4 remediation

This must be narrow.

Do **not** reopen pack lifecycle, workflow, cross-domain, provider fail-closed, empty-requirement fail-closed, specialized-result gating, or anti-fragmentation unless a regression proves they break.

## Block A — fix canonical Phase 7 command-result interpretation

Minimal canonical correction:

```text
wire existing pytest parser into CommandResultParser
fix existing Ruff parser for current list-form JSON
```

Add RED tests at the executor/parser integration boundary.

Prove:

```text
pytest exit 1 → affected_tests FAILED
ruff diagnostics → lint FAILED
```

Do not add new parser infrastructure.

## Block B — derive Project impact and changed files from canonical host state

Inspect and reuse existing Phase 7 change-impact / changed-file infrastructure.

Do not trust request fields as authority.

Prove:

```text
host structural/public impact beats caller small
actual changed files are derived even when caller omits them
```

If request fields remain, treat them only as monotonic hints.

## Block C — rebuild only the Project portion of AT-DP-043

Preserve V3's valid provider/specialized scenarios.

Add:

```text
formatter-clean + lint-clean + syntax-valid + AST-valid + failing affected test
→ real Project mutation blocked specifically by affected_tests FAILED

caller small + host stronger impact
→ stronger policy wins

caller omits changed files
→ host-derived changed-file scope still selects affected test
```

## Block D — docs and evidence

Correct Project claims only after code is green.

Run focused/relevant/full suites and canonical changed-file Ruff/format gates.

Create a new V4 remediation-evidence document if following the established audit convention.

Then generate:

```text
phase-10.43-audit-v4-<NEW_HEAD>.tar.gz
```

from exact committed HEAD.

---

# 12. Final V3 audit status

```text
PHASE=10.43
AUDIT_VERSION=V3

AUDITED_HEAD=edfd853c3b6197a7e84137e538ec6f37f5b02230
AUDIT_BUNDLE_SHA256=7176bb459fae33fe1fdccbed612c4cc0fbf0338e152a48b0ebb1238754e76280

BLOCKERS=3
MAJORS=1
MINORS=0

V2_BLOCKER_01=REMEDIATED
V2_BLOCKER_02=PARTIALLY_REMEDIATED
V2_BLOCKER_03=PARTIALLY_REMEDIATED
V2_MAJOR_01=PARTIALLY_REMEDIATED
V2_MAJOR_02=REMEDIATED_WITH_BASELINE_CAVEAT

BLOCKER_V3_01=PHASE7_PYTEST_AND_LINT_RESULT_PATH_FAIL_OPEN
BLOCKER_V3_02=PROJECT_IMPACT_AND_CHANGED_FILES_NOT_HOST_DERIVED
BLOCKER_V3_03=AT_DP_043_PROJECT_PROOF_INCOMPLETE

MAJOR_V3_01=PROJECT_DOCUMENTATION_OVERSTATES_RUNTIME

DP-043=NOT_VERIFIED
AT-DP-043=FAIL
CLOSURE_ELIGIBLE=NO

NEXT=TARGETED_V3_TO_V4_REMEDIATION
```
