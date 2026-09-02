# CMM OS — Phase 10.39 — Independent Re-audit V2

**Phase:** 10.39 — Preventing Fragmentation
**Audit:** Independent Re-audit V2
**Date:** 2026-09-02
**Auditor:** ChatGPT / independent project audit
**Verdict:** **FAIL**
**Closure eligible:** **NO**

---

## 1. Audited artifact

Audit bundle:

```text
phase-10.39-audit-v2-d51431d133c59fcaa71afa83bff1b238c6efcc35.tar.gz
```

Google Drive file ID:

```text
1Wgi0kw-wgoLbjkyBiCv3GnPsoAvPAOWf
```

Drive-reported size:

```text
5,215,444 bytes
```

Independent SHA-256:

```text
457c47d5e6d4dec1b1a7a81cc57034553e996c954f99f1b768a6093bfaa65e51
```

Embedded `git archive` commit ID:

```text
d51431d133c59fcaa71afa83bff1b238c6efcc35
```

Archive integrity:

```text
entries = 2002
unsafe traversal paths = 0
symlinks/hardlinks = 0
tracked __pycache__ / .pyc entries = 0
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
AUDITED_HEAD=d51431d133c59fcaa71afa83bff1b238c6efcc35
AUDIT_BUNDLE_SHA256=457c47d5e6d4dec1b1a7a81cc57034553e996c954f99f1b768a6093bfaa65e51
```

---

## 2. Audit basis

The re-audit checked the V2 candidate against:

```text
docs/audits/phase-10.39-independent-audit-v1.md
docs/superpowers/specs/2026-09-01-phase-10.39-preventing-fragmentation-design.md
docs/superpowers/plans/2026-09-01-phase-10.39-preventing-fragmentation-implementation-plan.md
ROADMAP.md
docs/roadmap/phase-10-domain-intelligence.md
docs/reference/domain-intelligence-requirements-matrix.md
```

Primary implementation:

```text
cmm/domains/validation_fragmentation.py
tests/domains/test_domain_validation_fragmentation.py
tests/domains/test_domain_architecture_guard_dp039_acceptance.py
```

Canonical integration inspected:

```text
cmm/domains/validation.py
cmm/domains/validation_validators.py
cmm/domains/validation_steps.py
cmm/domains/validation_contracts.py
```

---

## 3. Positive V2 findings

### 3.1 Exact-head artifact authentication

The bundle SHA-256 independently matches:

```text
457c47d5e6d4dec1b1a7a81cc57034553e996c954f99f1b768a6093bfaa65e51
```

The embedded commit ID independently matches:

```text
d51431d133c59fcaa71afa83bff1b238c6efcc35
```

### 3.2 Canonical architecture owner preserved

The implementation remains on:

```text
PipelineDomainValidator
→ domain.fragmentation
→ DomainFragmentationValidator
→ analyze_fragmentation(...)
→ DomainValidationResult.fragmentation_valid
→ ensure_domain_validation_allows_install(...)
```

No second production architecture guard was introduced.

Independent scan:

```text
PARALLEL_ARCHITECTURE_GUARD=NONE
```

### 3.3 Production scope remains narrow

Compared with the Phase 10.38 independently audited production code, Phase 10.39 changes only:

```text
cmm/domains/validation_fragmentation.py
```

No new CMM production Python modules were added for a parallel guard.

### 3.4 Expected tests are present

Phase 10.39 changes/adds only the intended Domain test surfaces:

```text
tests/domains/test_domain_validation_fragmentation.py
tests/domains/test_domain_architecture_guard_dp039_acceptance.py
```

### 3.5 Canonical event invariant preserved

Independent AST inspection:

```text
CANONICAL_DOMAIN_EVENTS=23
UNIQUE_CANONICAL_DOMAIN_EVENTS=23
```

### 3.6 Canonical validation step preserved

Independent AST inspection:

```text
STEP_FRAGMENTATION=domain.fragmentation
```

### 3.7 Compile gate

Independent:

```text
COMPILEALL=PASS
```

### 3.8 Original V1 adversarial matrix is now green

The exact V2 analyzer was loaded directly without importing or executing Domain Pack code.

All twelve V1 control/adversarial expectations now behave correctly:

```text
MemoryStore duplication blocked                     PASS
sqlite3 direct persistence blocked                  PASS
unrelated official-base adapter bypass blocked      PASS
global registry recreation blocked                  PASS
event bus recreation blocked                        PASS
resolver recreation blocked                         PASS
loader recreation blocked                           PASS
attribute policy bypass blocked                     PASS
shelve ImportFrom persistence blocked               PASS
innocent client.connect allowed                     PASS
innocent writer.write_text allowed                  PASS
backend import text in comment allowed              PASS
```

Summary:

```text
ORIGINAL_V1_MATRIX=12/12 PASS
```

This confirms meaningful remediation progress.

---

# 4. Auditor correction to V1

## V1 MAJOR-03 — tracked bytecode finding was erroneous

The V1 report stated that the exact V1 `git archive` contained:

```text
334 tracked __pycache__/*.pyc files
```

A fresh direct inspection of the original V1 TAR with its independently verified SHA:

```text
52eb016d326e26caf5aaec69f5298520666de418889fc29888e69e3868322578
```

shows:

```text
V1 archive entries = 2001
V1 __pycache__ / .pyc entries = 0
```

The V2 archive likewise contains:

```text
V2 __pycache__ / .pyc entries = 0
```

The earlier V1 finding came from auditor-side extraction/runtime contamination, not from the committed `git archive`.

Therefore:

```text
V1_MAJOR_03_TRACKED_BYTECODE=WITHDRAWN_AS_AUDITOR_ERROR
```

The historical V1 report should remain immutable, but V2 records this correction explicitly.

The remediation agent's statement:

```text
MAJOR_03_TRACKED_BYTECODE=REMEDIATED (0 tracked files — already clean)
```

is consistent with the exact archives.

This auditor correction does not change the V2 FAIL result because independent V2 blockers/majors remain.

---

# 5. BLOCKER

## BLOCKER-01 — Canonical adapter exemption remains bypassable through rebinding of an approved imported base

**Severity:** BLOCKER
**Status:** OPEN

### V1 remediation intent

V1 required adapter immunity to become component-aware and non-bypassable.

V2 correctly replaces blanket `cmm.*` immunity with exact per-component canonical bases.

However, `_collect_import_bindings(...)` records an imported canonical symbol and `_is_adapter_pattern(...)` later trusts that binding without proving the name still refers to the imported symbol at the class declaration.

Assignments/rebindings do not invalidate the stored canonical binding.

### Independently reproduced planner bypass

Input:

```python
from cmm.planner import TaskPlanner

TaskPlanner = object

class EvilPlanner(TaskPlanner):
    pass
```

Expected:

```text
DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION
```

Actual:

```text
NO_FINDINGS
```

At runtime, `EvilPlanner` inherits from `object`, not from canonical `TaskPlanner`.

The static guard nevertheless grants canonical-adapter immunity because it still associates the name `TaskPlanner` with:

```text
cmm.planner.task_planner.TaskPlanner
```

### Independently reproduced WorkflowEngine bypass

Input:

```python
from cmm.workflows import WorkflowEngine

WorkflowEngine = object

class EvilWorkflowEngine(WorkflowEngine):
    pass
```

Expected:

```text
DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION
```

Actual:

```text
NO_FINDINGS
```

### Independently reproduced MemoryStore bypass

Input:

```python
from cmm.cognitive import InMemoryResolutionMemoryStore

InMemoryResolutionMemoryStore = object

class EvilMemoryStore(InMemoryResolutionMemoryStore):
    pass
```

Expected:

```text
DOMAIN_FRAGMENTATION_MEMORY_DUPLICATION
```

Actual:

```text
NO_FINDINGS
```

### Why this is a blocker

This is not merely an uncovered naming variant.

The exact mechanism introduced to remediate V1's architecture-boundary bypass remains exploitable using ordinary Python rebinding.

The approved design point requires the boundary to:

```text
fail closed on architectural attempts to recreate, redefine, or bypass shared CMM OS infrastructure
```

and V1 explicitly required component-aware canonical-base recognition to be non-bypassable.

The V2 implementation still permits a protected architecture class to obtain adapter immunity without actually inheriting from the canonical owner.

Therefore the original blocker is not fully remediated.

### Required remediation

Stay inside the existing analyzer.

Do not execute or import Domain Pack code dynamically.

Make adapter binding analysis state-aware at the point of the protected class declaration.

A minimal correct approach should:

1. process relevant top-level statements in source order;
2. record canonical imports;
3. invalidate a canonical binding when that local name is reassigned, annotated-assigned, augmented-assigned, deleted, or otherwise rebound before the protected class declaration;
4. grant adapter exemption only when the base name/path still resolves to an intact approved canonical binding at that class declaration;
5. preserve alias support;
6. add RED regressions for:
   - direct rebinding to `object`;
   - alias rebinding;
   - WorkflowEngine rebinding;
   - MemoryStore rebinding.

Do not build a general Python interpreter.

---

# 6. MAJOR findings

## MAJOR-01 — Legitimate unaliased canonical package imports are still falsely rejected as fragmentation

**Severity:** MAJOR
**Status:** OPEN

The design requires legitimate canonical adapters/reuse not to be rejected.

The V2 tests prove:

```python
from cmm.planner import TaskPlanner
class GuardedPlannerAdapter(TaskPlanner):
    pass
```

and alias-module forms.

But the ordinary Python import form below is falsely blocked:

```python
import cmm.planner

class MyPlanner(cmm.planner.TaskPlanner):
    pass
```

Actual:

```text
DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION
```

Equivalent WorkflowEngine case:

```python
import cmm.workflows

class MyWorkflowEngine(cmm.workflows.WorkflowEngine):
    pass
```

Actual:

```text
DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION
```

### Cause

For unaliased:

```python
import cmm.planner
```

`_collect_import_bindings(...)` stores the binding under the full string rather than a binding that `_resolve_single_base(...)` can resolve through the first name `cmm`.

The raw path:

```text
cmm.planner.TaskPlanner
```

is then returned without applying the known submodule mapping to:

```text
cmm.planner.task_planner.TaskPlanner
```

so the approved base is not recognized.

### Why major

The positive side of DP-039 is not optional.

The spec requires:

```text
legitimate canonical adapters/reuse are not rejected
```

A guard that blocks a normal import spelling of the exact canonical component violates that contract and can prevent legitimate Domain Packs from installing.

### Required remediation

Extend the existing static resolver so equivalent import spellings resolve identically:

```text
from cmm.planner import TaskPlanner
import cmm.planner as planner
import cmm.planner
```

and equivalent approved Workflow/Memory forms.

Add positive regression tests for unaliased package imports.

---

## MAJOR-02 — Direct-write enforcement remains trivially bypassable by statically obvious aliases/order

**Severity:** MAJOR
**Status:** OPEN

Phase 10.39's normative roadmap and implementation plan require direct writes to be detected.

V2 fixed the V1 false positives, but several direct writes remain statically obvious and undetected.

### A. pathlib module alias bypass

Input:

```python
import pathlib as pl

pl.Path("state.json").write_text("{}")
```

Expected:

```text
DOMAIN_FRAGMENTATION_DIRECT_WRITE
```

Actual:

```text
NO_FINDINGS
```

The analyzer already records `pl` as a pathlib binding, but `_receiver_is_path(...)` does not use that binding when resolving `pl.Path(...)`.

### B. builtin open alias bypass

Input:

```python
from builtins import open as bo

bo("state.json", "w").write("{}")
```

Expected:

```text
DOMAIN_FRAGMENTATION_DIRECT_WRITE
```

Actual:

```text
NO_FINDINGS
```

This is a statically explicit alias of builtin `open`.

### C. order-insensitive shadow detection creates a false negative

Input:

```python
open("state.json", "w").write("{}")

def open(path, mode):
    return None
```

At module execution time the first call resolves to builtin `open`, because the later function definition has not executed yet.

Expected:

```text
DOMAIN_FRAGMENTATION_DIRECT_WRITE
```

Actual:

```text
NO_FINDINGS
```

`_is_builtin_open(...)` scans the entire AST and treats any function named `open` anywhere in the module as shadowing every call, regardless of source order.

### Why major

These are not dynamic or symbolic edge cases.

They are simple AST-visible variants of the exact direct-write operations Phase 10.39 is intended to guard.

The direct-write boundary therefore remains bypassable without metaprogramming or runtime introspection.

### Required remediation

Remain AST-only and narrow.

1. Resolve `pathlib` module aliases when checking `Path(...).write_text/write_bytes`.
2. Recognize explicit aliases imported from `builtins.open`.
3. Make builtin-`open` shadow analysis source-order aware at module scope.
4. Keep V1 false-positive regressions green.
5. Add connected negative acceptance for at least one aliased direct-write form.

No general dataflow engine is required.

---

## MAJOR-03 — Requirements matrix still lacks the required DP-039 mapping and carries stale remediation status

**Severity:** MAJOR
**Status:** OPEN

The approved implementation plan explicitly requires:

```text
Update requirements matrix with DP-039 / AT-DP-039 mapping
```

with:

```text
DP-039
→ canonical Domain Validation / domain.fragmentation
→ no parallel guard
→ protected shared owners
→ implementation evidence paths

AT-DP-039
→ tests/domains/test_domain_architecture_guard_dp039_acceptance.py
→ PipelineDomainValidator
→ fragmentation_valid propagation
→ installation gate rejection
```

### V2 actual state

The canonical `DP-*` requirements table contains:

```text
DP-038
...
DP-052
DP-053
```

There is no `DP-039` table row.

Phase 10.39 appears only later in the implementation-order prose.

That is not the required requirements-matrix mapping.

Additionally, both the detailed roadmap and requirements-matrix prose still say:

```text
DP-039=IMPLEMENTED_PENDING_REMEDIATION
```

while V2 is already a remediated candidate pending independent re-audit.

The file itself defines the canonical status:

```text
IMPLEMENTED_PENDING_AUDIT
```

but does not use it for DP-039.

### Positive part

The original normative Phase 10.39 roadmap checklist removed in V1 has been restored.

Top-level `ROADMAP.md` now correctly describes Phase 10.39 as implemented and pending independent re-audit.

Therefore the core V1 roadmap-restoration finding is substantially remediated.

### Why major

The requirements matrix is the project's canonical requirement-to-evidence traceability artifact.

The phase's own implementation plan explicitly requires a DP-039/AT-DP-039 mapping there.

A prose entry in final implementation order does not replace the missing requirement row.

### Required remediation

Add a proper `DP-039` row to the `DP-*` requirements table.

It must include:

```text
responsible phase = 10.39
canonical owner = domain.fragmentation
implementation evidence = validation_fragmentation.py
design spec path
implementation plan path
connected AT path
mapping status = IMPLEMENTED_PENDING_AUDIT
```

Do not mark it independently verified before a PASS re-audit.

Update stale:

```text
IMPLEMENTED_PENDING_REMEDIATION
```

to the repository's canonical pre-audit/re-audit state.

---

# 7. AT-DP-039 verdict

## Positive evidence

The acceptance test now uses the real repository symbol:

```text
cmm.planner.TaskPlanner
```

instead of fictional `BasePlanner`.

The connected test code still traverses:

```text
DomainValidationRequest
→ PipelineDomainValidator
→ domain.fragmentation
→ fragmentation_valid
→ ensure_domain_validation_allows_install(...)
```

The acceptance also retains no-code-execution and side-effect checks.

## Negative evidence

AT-DP-039 does not cover the independently reproduced canonical-binding rebinding bypass.

It also does not cover the residual direct-write alias bypasses.

Because an installation candidate can still evade the architecture guard, the acceptance requirement is not satisfied independently.

Result:

```text
AT-DP-039=FAIL
```

---

# 8. DP-039 verdict

Positive:

```text
canonical owner preserved
no parallel guard
component-aware adapter mapping introduced
original V1 exploit blocked
original V1 coverage gaps fixed
original V1 false positives fixed
23/23 Domain Events preserved
```

Negative:

```text
adapter exemption still bypassable by rebinding
legitimate canonical import form still falsely blocked
direct-write guard remains trivially bypassable
```

Therefore:

```text
DP-039=NOT_VERIFIED
```

---

# 9. Documentation verdict

### PASS

```text
original normative Phase 10.39 roadmap requirements restored
top-level ROADMAP Phase 10.39 implementation/audit direction corrected
V1 audit report preserved
spec preserved
plan preserved
```

### FAIL

```text
no actual DP-039 requirements-table row
DP-039 status remains IMPLEMENTED_PENDING_REMEDIATION instead of pre-audit state
```

Result:

```text
DOCUMENTATION_STATUS=FAIL
```

---

# 10. Scope verdict

V1 → V2 changed source/test/documentation scope is narrow and appropriate:

```text
cmm/domains/validation_fragmentation.py
tests/domains/test_domain_validation_fragmentation.py
tests/domains/test_domain_architecture_guard_dp039_acceptance.py
ROADMAP.md
docs/roadmap/phase-10-domain-intelligence.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/audits/phase-10.39-independent-audit-v1.md
```

No parallel production module was added.

No bytecode is present in the exact archive.

Result:

```text
SCOPE=NARROW
PARALLEL_INFRASTRUCTURE=NO
ARCHIVE_HYGIENE=PASS
```

---

# 11. Test / quality evidence

## Independent environment

Independent `compileall`:

```text
PASS
```

Independent full pytest rerun cannot start because this audit runtime lacks the repository dependency:

```text
libcst
```

Attempting to collect the focused fragmentation test fails during package import with:

```text
ModuleNotFoundError: No module named 'libcst'
```

This is an auditor-environment limitation and is not counted as a product finding.

Ruff is likewise unavailable in the independent runtime.

## Supplied repository evidence

The remediation agent reported:

```text
FOCUSED=122 passed
INHERITED_REGRESSIONS=148 passed
DOMAIN_SUITE=8879 passed
GLOBAL_SUITE=14434 passed
```

A subsequent repository-side differential style gate established:

```text
CURRENT_RUFF_DIAGNOSTICS=580
BASELINE_RUFF_DIAGNOSTICS=580
NEW_RUFF_DIAGNOSTICS=0
RUFF_DIFFERENTIAL_GATE=PASS
PHASE10_39_CHANGED_PYTHON_STYLE=PASS
HEAD_UNCHANGED=YES
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

The independent FAIL verdict does not rely on missing local pytest/Ruff capability; it relies on directly reproduced analyzer defects from the exact V2 source.

---

# 12. Expanded independent adversarial matrix

The exact V2 analyzer was exercised directly.

Original V1 cases:

```text
12/12 PASS
```

Additional V2 probes:

```text
canonical Planner import binding rebinding        FAIL
canonical WorkflowEngine binding rebinding        FAIL
unaliased canonical Planner adapter allowed       FAIL
pathlib module-alias direct write blocked          FAIL
builtins.open alias direct write blocked           FAIL
builtin open before later shadow blocked           FAIL
```

Summary:

```text
V2_NEW_ADVERSARIAL_FAILURES=6
```

The most serious is the canonical-binding rebinding exploit because it revives the same adapter-immunity boundary that caused the V1 blocker.

---

# 13. Final independent Re-audit V2 verdict

```text
PHASE=10.39
AUDIT=INDEPENDENT_REAUDIT_V2

AUDITED_HEAD=d51431d133c59fcaa71afa83bff1b238c6efcc35
AUDIT_BUNDLE_SHA256=457c47d5e6d4dec1b1a7a81cc57034553e996c954f99f1b768a6093bfaa65e51

BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS

BLOCKERS=1
MAJORS=3
MINORS=0

DP-039=NOT_VERIFIED
AT-DP-039=FAIL

CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL
```

Phase status must remain:

```text
PHASE10_39=REMEDIATION_REQUIRED
```

It must not be closed.

---

# 14. V2 remediation boundary

Remediation V2 must remain narrow.

Required work only:

```text
1. invalidate canonical adapter bindings when imported names are rebound before a protected class declaration;
2. support legitimate unaliased canonical package import forms for approved adapters;
3. close statically obvious direct-write alias/order bypasses while preserving V1 false-positive fixes;
4. add a real DP-039 row to the canonical requirements matrix and update stale pending-remediation status;
5. add regression tests for every reproduced V2 defect;
6. rerun focused, inherited, Domain, global, differential Ruff/format, compileall and diff gates;
7. commit remediation;
8. keep worktree clean and quarantine stash unchanged;
9. create a NEW exact-HEAD V3 `git archive`;
10. calculate a NEW SHA-256;
11. submit the new bundle for Independent Re-audit V3.
```

Do not broaden Phase 10.39.

Do not start Phase 10.40.

Do not modify the V1 or V2 bundles.

---

# 15. Closure requirements remain unmet

A future independent PASS must reach at least:

```text
BLOCKERS=0
MAJORS=0
DP-039=VERIFIED_EXISTING
AT-DP-039=PASS
CLOSURE_ELIGIBLE=YES
```

Only then may the separate docs-only closure commit be created.
