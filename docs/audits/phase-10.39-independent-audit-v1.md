# CMM OS — Phase 10.39 — Independent Audit V1

**Phase:** 10.39 — Preventing Fragmentation
**Audit:** Independent Audit V1
**Date:** 2026-09-01
**Auditor:** ChatGPT / independent project audit
**Verdict:** **FAIL**
**Closure eligible:** **NO**

---

## 1. Audited artifact

Audit bundle:

```text
phase-10.39-audit-aa3b38427da15a532270029fcf7674313214f634.tar.gz
```

Google Drive file ID:

```text
1QWRq53J6-nVdIJqbqptff_aPeOwlxqC9
```

Drive-reported size:

```text
5,204,042 bytes
```

Independent SHA-256:

```text
52eb016d326e26caf5aaec69f5298520666de418889fc29888e69e3868322578
```

`git archive` embedded commit ID:

```text
aa3b38427da15a532270029fcf7674313214f634
```

The embedded commit ID matches the HEAD encoded in the bundle filename.

Archive integrity checks:

```text
entries = 2001
unsafe traversal paths = 0
symlinks/hardlinks = 0
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
AUDITED_HEAD=aa3b38427da15a532270029fcf7674313214f634
```

---

## 2. Audit basis

The audit checked the implementation against:

```text
docs/superpowers/specs/2026-09-01-phase-10.39-preventing-fragmentation-design.md
docs/superpowers/plans/2026-09-01-phase-10.39-preventing-fragmentation-implementation-plan.md
ROADMAP.md
docs/roadmap/phase-10-domain-intelligence.md
docs/reference/domain-intelligence-requirements-matrix.md
```

Primary implementation inspected:

```text
cmm/domains/validation_fragmentation.py
tests/domains/test_domain_validation_fragmentation.py
tests/domains/test_domain_architecture_guard_dp039_acceptance.py
```

Relevant canonical integration inspected:

```text
cmm/domains/validation.py
cmm/domains/validation_validators.py
cmm/domains/validation_steps.py
cmm/domains/validation_contracts.py
```

Previous independently audited comparison bundle:

```text
phase-10.38-audit-v3.tar.gz
```

Previous audited implementation HEAD:

```text
dcf2a058c9ab849642291c44842e1efe53d57906
```

Previous bundle SHA-256 independently confirmed:

```text
dae36ab2b50bd3d09861eb3ea090be8edddc9e905ee720049171a350205300e0
```

---

## 3. Positive findings

The following architectural properties are correctly preserved in the audited HEAD.

### 3.1 Canonical owner preserved

The implementation continues to use:

```text
PipelineDomainValidator
→ domain.fragmentation
→ DomainFragmentationValidator
→ analyze_fragmentation(...)
→ DomainValidationResult.fragmentation_valid
→ ensure_domain_validation_allows_install(...)
```

No second validation pipeline or production `DomainArchitectureGuard` service was introduced.

Independent production scan found no:

```text
class DomainArchitectureGuard
ArchitectureGuardRegistry
FragmentationEngine
```

### 3.2 Integration contracts were not rewritten

Compared with the independently audited Phase 10.38 V3 code, these production files are unchanged:

```text
cmm/domains/validation_validators.py
cmm/domains/validation.py
cmm/domains/validation_steps.py
cmm/domains/validation_contracts.py
```

The intended Phase 10.39 production logic is concentrated in:

```text
cmm/domains/validation_fragmentation.py
```

### 3.3 Canonical fragmentation step preserved

Independent AST verification:

```text
STEP_FRAGMENTATION=domain.fragmentation
```

### 3.4 Domain Event invariant preserved

Independent AST verification:

```text
DOMAIN_EVENT_COUNT=23
DOMAIN_EVENT_UNIQUE_COUNT=23
```

### 3.5 Syntax compilation

Independent syntax compilation of:

```text
cmm
kernel
tests
```

completed successfully:

```text
COMPILEALL=PASS
```

### 3.6 Changed Phase 10.39 text files have clean trailing whitespace

Independent text hygiene check over the principal modified text files found:

```text
TRAILING_WHITESPACE_COUNT=0
```

---

# 4. Blocking finding

## BLOCKER-01 — Architecture-guard adapter exemption is trivially bypassable and AT-DP-039 positive proof is not a real canonical adapter

**Severity:** BLOCKER
**Status:** OPEN

### Affected code

```text
cmm/domains/validation_fragmentation.py
  _collect_import_bindings(...)
  _is_adapter_pattern(...)
  detect_class_duplication(...)
```

Relevant implementation behavior:

```text
any class whose protected name/suffix matches a fragmentation component
is exempted whenever any base class resolves to a path beginning with:

cmm.
cmm_agent.
kernel.
```

The exemption is not tied to the protected component being checked.

`_is_adapter_pattern(...)` receives `class_name` but does not use it to verify that the inherited canonical base is the canonical owner for that protected architecture type.

### Reproduced exploit

The audited analyzer was executed directly from the exact-HEAD source.

Input:

```python
from cmm.domains.pack import DomainPack

class EvilMemoryStore(DomainPack):
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

Equivalent bypass was reproduced for a protected planner-shaped class.

This means a Domain Pack can claim prohibited architecture by name while obtaining blanket immunity through inheritance from an unrelated official CMM class.

That directly violates the Phase 10.39 requirement that Domain Packs must not recreate shared infrastructure.

### AT-DP-039 defect

The positive connected acceptance uses:

```python
from cmm.planner import BasePlanner

class GuardedPlannerAdapter(BasePlanner):
    pass
```

Repository-wide inspection found **no real `BasePlanner` definition** in `cmm` or `kernel`.

The only `BasePlanner` occurrences are in:

```text
validation_fragmentation.py comments
fragmentation tests
AT-DP-039
```

The real exported planner is:

```text
cmm.planner.TaskPlanner
```

Therefore AT-DP-039 does not demonstrate a legitimate existing canonical adapter/reuse path.

Because Domain validation intentionally does not execute untrusted pack code, the nonexistent import does not fail during validation. The test therefore passes precisely because the scanner trusts an arbitrary official-looking import path.

### Spec violations

The design requires:

```text
The guard must distinguish architectural duplication from legitimate specialization.
```

and:

```text
Tests must explicitly prove at least one legitimate canonical adapter/reuse path remains accepted.
```

and AT-DP-039 must show:

```text
a valid Domain Pack that reuses canonical infrastructure
```

The current acceptance does not establish that.

### Required remediation

1. Replace blanket official-prefix adapter immunity with component-aware canonical-base recognition.
2. A protected `MemoryStore`, `Planner`, `WorkflowEngine`, etc. may be exempt only when its inheritance/reuse relationship is actually valid for that canonical component boundary.
3. Do not import or execute Domain Pack code to prove this.
4. Use exact known canonical symbols/modules or a narrow immutable mapping in the existing analyzer.
5. Replace fictional `BasePlanner` acceptance with a real canonical reuse pattern supported by the repository.
6. Add adversarial tests proving unrelated official bases cannot grant immunity:

```python
from cmm.domains.pack import DomainPack
class EvilMemoryStore(DomainPack): ...
```

and equivalent cases for at least Planner / WorkflowEngine.
7. Re-run the connected install-gate proof.

Until fixed:

```text
DP-039 != VERIFIED_EXISTING
AT-DP-039 != PASS
CLOSURE_ELIGIBLE=NO
```

---

# 5. Major findings

## MAJOR-01 — Explicit fragmentation requirements remain unenforced

**Severity:** MAJOR
**Status:** OPEN

The spec requires Phase 10.39 to block, among other things:

```text
recreated global services already owned by canonical CMM OS infrastructure
statically demonstrable global validation/policy bypasses
known direct persistence/backend bypasses
```

The audited analyzer does not flag representative recreated global services.

### Reproduced misses

All of these produced no fragmentation finding:

```python
class HealthDomainRegistry:
    pass
```

```python
class HealthResourceRegistry:
    pass
```

```python
class HealthWorkflowRegistry:
    pass
```

```python
class HealthEventBus:
    pass
```

```python
class HealthDomainResolver:
    pass
```

```python
class HealthDomainLoader:
    pass
```

```python
class HealthTraceStore:
    pass
```

These are directly relevant to the shared owners the phase is intended to protect.

### Explicit policy-bypass miss

Input:

```python
class Config:
    pass

config = Config()
config.skip_validation = True
```

Actual:

```text
NO_FINDINGS
```

`_extract_assign_target_name(...)` returns a dotted name such as:

```text
config.skip_validation
```

but the detector compares it against exact identifiers such as:

```text
skip_validation
```

so the attribute assignment is not detected.

The approved implementation plan explicitly required detection of `ast.Attribute` assignment targets.

Annotated assignment is also not covered:

```python
skip_validation: bool = True
```

### Persistence bypass miss

Input:

```python
from shelve import open as shelf_open

db = shelf_open("state")
```

Actual:

```text
NO_FINDINGS
```

The implementation blocks `import shelve` but not `from shelve import ...`.

The same structural gap exists for `ImportFrom` forms of several protected persistence modules.

### Required remediation

1. Extend the existing analyzer only; do not create a new guard subsystem.
2. Add narrow protected global-service categories grounded in canonical owners:
   - registries whose ownership is canonical;
   - resolver/loader ownership;
   - event-bus/catalog ownership where relevant;
   - trace-store ownership where relevant.
3. Detect attribute-form policy bypass assignments by inspecting the final attribute name rather than comparing the whole dotted path.
4. Add `AnnAssign` coverage where the assigned identifier is statically explicit.
5. Treat `ImportFrom` for the known persistence backends consistently with `Import`.
6. Add connected negative acceptance coverage for representative newly protected cases.

---

## MAJOR-02 — Persistence/direct-write detection has architecture-breaking false positives

**Severity:** MAJOR
**Status:** OPEN

The spec explicitly requires the guard to remain conservative enough not to reject ordinary Domain-specific code through generic naming heuristics.

The audited implementation violates that rule.

### False positive: arbitrary `connect()`

Input:

```python
def f(client):
    return client.connect()
```

Actual:

```text
DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS
```

The implementation flags any call whose final name is:

```text
connect
create_engine
Redis
```

without verifying that it belongs to a known persistence backend or a corresponding protected import binding.

This can block ordinary network/API/domain clients.

A local function is also incorrectly blocked:

```python
def connect():
    return True

connect()
```

### False positive: arbitrary `.write_text(...)`

Input:

```python
def f(writer):
    writer.write_text("hello")
```

Actual:

```text
DOMAIN_FRAGMENTATION_DIRECT_WRITE
```

The implementation treats every method named:

```text
write_text
write_bytes
```

as `pathlib.Path` filesystem access without resolving the receiver.

### False positive: shadowed `open`

Input:

```python
def open(path, mode):
    return None

open("x", "w")
```

Actual:

```text
DOMAIN_FRAGMENTATION_DIRECT_WRITE
```

The static detector assumes every `open(...)` call is the builtin.

### Existing backend-regex false positive

Input:

```python
# from cmm.memory.backend import Store
x = 1
```

Actual:

```text
DOMAIN_FRAGMENTATION_BACKEND_BYPASS
```

The legacy backend detector still scans raw lines and therefore interprets comments as executable imports.

### Required remediation

1. Make persistence detection import-aware.
2. Bind persistence calls to known protected module/import aliases rather than call-name suffixes.
3. Restrict `write_text` / `write_bytes` detection to statically recognizable `pathlib.Path` usage or equivalent known filesystem objects.
4. Avoid treating locally shadowed `open` as builtin when the AST can prove it is shadowed.
5. Replace/comment-proof the legacy backend import regex with AST import inspection.
6. Add explicit false-positive tests for:
   - arbitrary client `.connect()`;
   - local `connect()`;
   - non-Path `.write_text()`;
   - comments/docstrings containing forbidden import text.

---

## MAJOR-03 — Exact audited HEAD contains 334 tracked `__pycache__/*.pyc` files

**Severity:** MAJOR
**Status:** OPEN

Because the audit artifact is a `git archive`, every file inside it is tracked by the audited commit.

Independent comparison with the Phase 10.38 audited V3 bundle shows new bytecode artifacts across:

```text
cmm/
kernel/
```

Count:

```text
PYC_COUNT=334
```

Total byte size:

```text
PYC_BYTES=4,974,041
```

Distribution:

```text
290 cmm
44 kernel
```

The repository `.gitignore` explicitly contains:

```text
__pycache__/
```

These are therefore out-of-scope generated artifacts and should not be versioned.

This violates:

```text
clear commit scope
no unrelated changes
clean auditable implementation boundary
```

and materially inflates the exact-HEAD audit artifact.

### Required remediation

Remove only the tracked Phase 10.39 bytecode artifacts from version control while leaving source files untouched.

Do not use:

```text
git reset
git clean
git stash
```

Use an explicit index/worktree-safe removal approach approved by the user's repository rules, then commit the removal as remediation.

Afterwards verify:

```text
git ls-files | grep '__pycache__\|\.pyc$'
```

returns no tracked bytecode artifacts intended to be excluded.

Regenerate a new exact-HEAD bundle.

---

## MAJOR-04 — Phase 10.39 roadmap requirements were deleted and status documentation is internally inconsistent

**Severity:** MAJOR
**Status:** OPEN

The independently audited Phase 10.38 V3 roadmap contained the full normative Phase 10.39 section, including:

```text
Objective
Domains must not be free to...
Domain Architecture Guard conceptual shape
Comprobaciones
local validation
CI
installation
update
publication
global suite
```

The audited Phase 10.39 HEAD replaces that section with a compact implementation summary and removes the original normative checklist.

This is a documentation regression because it erases the roadmap requirements against which Phase 10.39 is supposed to be audited.

The project workflow requires preserving roadmap detail and historical auditability, not replacing requirements with post-implementation claims.

### Additional top-level ROADMAP inconsistency

The top of `ROADMAP.md` correctly says:

```text
Implemented: Phases 0–9 plus Phase 10 through 10.39
Implemented and audited: ... through 10.38
Next milestone: Phase 10.39 independent audit
```

but later the same file still says:

```text
Next implementation milestone: Phase 10.39
```

and:

```text
Phase 10.39 is the next milestone
```

Those statements are stale because Phase 10.39 is already implemented and pending audit.

### Required remediation

1. Restore the original normative Phase 10.39 roadmap requirements.
2. Add implementation-status/evidence below or alongside them rather than replacing them.
3. Keep `implemented and pending independent audit`.
4. Do not mark Phase 10.39 closed/audited.
5. Normalize all top-level ROADMAP status references so no section still calls 10.39 the next implementation milestone.
6. Preserve the requirements matrix mapping for DP-039 / AT-DP-039, updating only as needed after remediation.

---

# 6. Independent adversarial matrix

The exact audited `validation_fragmentation.py` was loaded directly without importing the broader CMM package.

This is possible because the module itself depends only on stdlib for these checks.

Twelve audit cases were executed.

Control checks:

```text
MemoryStore duplication blocked = PASS
sqlite3 direct persistence blocked = PASS
```

Adversarial/false-positive expectations:

```text
unrelated official-base adapter bypass = FAIL
global registry recreation = FAIL
event bus recreation = FAIL
resolver recreation = FAIL
loader recreation = FAIL
attribute policy bypass = FAIL
shelve ImportFrom persistence = FAIL
innocent client.connect allowed = FAIL
innocent writer.write_text allowed = FAIL
backend import text in comment allowed = FAIL
```

Summary:

```text
ADVERSARIAL_EXPECTATION_FAILURES=10/12
```

This matrix is independent audit evidence and is not part of the implementation's own test suite.

---

# 7. Test/gate reproducibility

## 7.1 Full pytest suite

The extracted audit artifact does not include the project virtual environment.

The independent audit runtime lacks the declared dependency:

```text
libcst
```

Attempting to import the full CMM package fails with:

```text
ModuleNotFoundError: No module named 'libcst'
```

The audit environment has no internet access, so the missing dependency could not be fetched.

Therefore:

```text
FULL_PYTEST_INDEPENDENT_RERUN=NOT_AVAILABLE_IN_AUDITOR_ENVIRONMENT
```

This is **not** counted as a product finding.

The FAIL verdict does not rely on inability to rerun pytest; it relies on directly reproduced defects in the Phase 10.39 stdlib-only analyzer and exact-HEAD scope inspection.

## 7.2 Compile gate

Independent:

```text
COMPILEALL=PASS
```

## 7.3 Ruff

Ruff is not available in the audit environment and could not be installed offline.

Therefore:

```text
RUFF_INDEPENDENT_RERUN=NOT_AVAILABLE_IN_AUDITOR_ENVIRONMENT
```

Again, this is not counted as a product finding.

---

# 8. DP-039 audit verdict

Required design point:

```text
DP-039 — Canonical Domain Architecture Guard
```

Positive architectural fact:

```text
the canonical owner remains the existing domain.fragmentation path
no parallel guard subsystem was introduced
```

However, the actual guard is trivially bypassable through unrelated official-base inheritance and does not cover multiple required recreated global-service patterns.

Therefore:

```text
DP-039=NOT_VERIFIED
```

It may not be reported as:

```text
DP-039=VERIFIED_EXISTING
```

until remediation and independent re-audit.

---

# 9. AT-DP-039 audit verdict

The connected test reaches the canonical pipeline and installation gate, which is good.

However, the required positive scenario is invalid because it uses nonexistent:

```text
cmm.planner.BasePlanner
```

and therefore does not prove a real canonical adapter/reuse path.

The test also does not cover the reproduced adapter-bypass and several required fragmentation cases.

Therefore:

```text
AT-DP-039=FAIL
```

---

# 10. Public-contract and architecture verdict

Positive:

```text
PipelineDomainValidator unchanged
DomainFragmentationValidator integration unchanged
validation step remains domain.fragmentation
DomainValidationResult.fragmentation_valid unchanged
installation gate unchanged
Domain Events remain 23/23
no parallel architecture guard introduced
```

Negative:

```text
guard semantics are insufficiently precise
guard can be bypassed
guard overblocks legitimate-looking non-persistence code
multiple explicit architectural-owner recreations remain unguarded
```

Result:

```text
PUBLIC_CANONICAL_PATH=PRESERVED
ARCHITECTURAL_ENFORCEMENT=FAIL
```

---

# 11. Scope verdict

Intended production code changes are narrow: the main production source change is:

```text
cmm/domains/validation_fragmentation.py
```

and the canonical pipeline files remain unchanged.

However, exact-HEAD scope is not acceptable because 334 ignored bytecode files were committed.

Result:

```text
INTENDED_CODE_SCOPE=NARROW
EXACT_HEAD_SCOPE=FAIL
```

---

# 12. Documentation verdict

Requirements matrix correctly records:

```text
10.39 implemented and pending independent audit
DP-039=IMPLEMENTED_PENDING_AUDIT
AT-DP-039 path
canonical guard = existing domain.fragmentation
```

However:

```text
full normative 10.39 roadmap requirements were removed
top-level ROADMAP has stale contradictory milestone text
```

Result:

```text
DOCUMENTATION_STATUS=FAIL
```

---

# 13. Final independent audit verdict

```text
PHASE=10.39
AUDIT=INDEPENDENT_AUDIT_V1
AUDITED_HEAD=aa3b38427da15a532270029fcf7674313214f634
AUDIT_BUNDLE_SHA256=52eb016d326e26caf5aaec69f5298520666de418889fc29888e69e3868322578

BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS

BLOCKERS=1
MAJORS=4
MINORS=0

DP-039=NOT_VERIFIED
AT-DP-039=FAIL

CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL
```

Phase 10.39 must remain:

```text
IMPLEMENTED_PENDING_REMEDIATION
```

It must not be closed.

---

# 14. Remediation boundary

Remediation must fix **only** the V1 findings.

Required remediation work:

```text
1. make canonical adapter exemption component-aware and non-bypassable;
2. replace fictional BasePlanner AT positive scenario with real canonical reuse;
3. protect recreated canonical global services required by the spec/roadmap;
4. close statically explicit policy-bypass and persistence ImportFrom gaps;
5. make persistence/direct-write/backend detection precise enough to avoid reproduced false positives;
6. remove the 334 tracked pyc/__pycache__ artifacts from the commit history moving forward;
7. restore the original normative Phase 10.39 roadmap requirements;
8. correct stale ROADMAP 10.39 milestone wording;
9. add regression tests for every reproduced V1 defect;
10. rerun focused, inherited, Domain subsystem, global, Ruff, format, compileall, and diff gates;
11. commit all remediation;
12. leave worktree clean;
13. create a NEW exact-HEAD `git archive` bundle;
14. calculate a NEW SHA-256;
15. submit that new bundle for Independent Re-audit V2.
```

Do not broaden Phase 10.39 beyond these findings.

Do not start Phase 10.40.

Do not modify the original V1 bundle.
