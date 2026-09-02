# CMM OS — Phase 10.39 — Independent Re-audit V3

**Phase:** 10.39 — Preventing Fragmentation
**Audit:** Independent Re-audit V3
**Date:** 2026-09-02
**Auditor:** ChatGPT / independent project audit
**Verdict:** **FAIL**
**Closure eligible:** **NO**

---

## 1. Audited artifact

Audit bundle:

```text
phase-10.39-audit-v3-7011f552c4d592554b8368b837c3e17e1a0af559.tar.gz
```

Google Drive file ID:

```text
1W6cfWt1l3wEQB8FX-LXZuwF9nBMgoqrV
```

Drive-reported size:

```text
5,221,741 bytes
```

Independent SHA-256:

```text
8f39f810470960d37fd55be8bf3b07577192373228ad5240398dfa50203de4ee
```

Embedded `git archive` commit ID:

```text
7011f552c4d592554b8368b837c3e17e1a0af559
```

Archive integrity:

```text
entries = 2003
unsafe traversal paths = 0
symlinks/hardlinks = 0
tracked __pycache__ / .pyc entries = 0
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
AUDITED_HEAD=7011f552c4d592554b8368b837c3e17e1a0af559
AUDIT_BUNDLE_SHA256=8f39f810470960d37fd55be8bf3b07577192373228ad5240398dfa50203de4ee
```

---

## 2. Audit basis

The V3 re-audit checked the exact committed archive against:

```text
docs/audits/phase-10.39-independent-audit-v1.md
docs/audits/phase-10.39-independent-reaudit-v2.md
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
cmm/domains/validation_validators.py
cmm/domains/validation.py
cmm/domains/validation_contracts.py
cmm/domains/validation_steps.py
```

---

# 3. Positive V3 findings

## 3.1 Exact-head authentication — PASS

Independent SHA-256 matches the agent-reported V3 SHA:

```text
8f39f810470960d37fd55be8bf3b07577192373228ad5240398dfa50203de4ee
```

Independent embedded `git archive` HEAD matches:

```text
7011f552c4d592554b8368b837c3e17e1a0af559
```

The filename, SHA and embedded commit are strongly bound.

---

## 3.2 Archive hygiene — PASS

Independent inspection:

```text
entries=2003
unsafe paths=0
links=0
tracked bytecode=0
```

No `.pyc` / `__pycache__` is present in the exact archive.

---

## 3.3 Canonical architecture owner preserved — PASS

The production chain remains:

```text
PipelineDomainValidator
→ domain.fragmentation
→ DomainFragmentationValidator
→ analyze_fragmentation(...)
→ fragmentation_valid
→ ensure_domain_validation_allows_install(...)
```

Independent scan found no:

```text
DomainArchitectureGuard service
ArchitectureGuardRegistry
FragmentationEngine
parallel validation owner
```

Result:

```text
CANONICAL_GUARD=domain.fragmentation
PARALLEL_ARCHITECTURE_GUARD=NO
```

---

## 3.4 Canonical validation integration remains intact — PASS

The canonical validator still invokes:

```text
analyze_fragmentation(text, rel_path)
```

and findings determine the `domain.fragmentation` validation step.

`PipelineDomainValidator` still derives:

```text
fragmentation_valid
```

from `STEP_FRAGMENTATION`.

The installation gate still adds:

```text
fragmentation_invalid
```

when `fragmentation_valid=False`.

No parallel result flag or alternate gate was introduced.

---

## 3.5 Canonical validation step — PASS

Independent inspection:

```text
STEP_FRAGMENTATION=domain.fragmentation
```

---

## 3.6 Domain Event invariant — PASS

Independent AST inspection:

```text
CANONICAL_DOMAIN_EVENTS=23
UNIQUE_CANONICAL_DOMAIN_EVENTS=23
```

Result:

```text
DOMAIN_EVENTS=23/23
```

---

## 3.7 V1 regression matrix — independently PASS 12/12

The exact V3 `validation_fragmentation.py` was loaded directly without executing Domain Pack code.

Independent V1 matrix:

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

Result:

```text
V1_REGRESSION_MATRIX=12/12 PASS
```

---

## 3.8 V2 regression matrix — independently PASS 18/18

### Rebound canonical names

```text
TaskPlanner imported then rebound                    PASS
TaskPlanner import alias rebound                     PASS
WorkflowEngine imported then rebound                 PASS
MemoryStore canonical symbol rebound                 PASS
```

All four are now rejected.

### Legitimate canonical adapters

```text
Planner from-import                                  PASS
Planner module alias                                 PASS
Planner unaliased package import                     PASS
WorkflowEngine from-import                           PASS
WorkflowEngine module alias                          PASS
WorkflowEngine unaliased package import              PASS
```

All six are accepted.

### Direct-write precision matrix

```text
pathlib alias write_text blocked                     PASS
pathlib alias write_bytes blocked                    PASS
builtins.open alias blocked                          PASS
builtin open before later shadow blocked             PASS
earlier local open shadow allowed                    PASS
unrelated imported open allowed                      PASS
innocent client.connect allowed                      PASS
innocent writer.write_text allowed                   PASS
```

Result:

```text
V2_REGRESSION_MATRIX=18/18 PASS
```

---

## 3.9 Canonical MemoryStore import spellings — independently PASS 3/3

Accepted:

```text
from cmm.cognitive import InMemoryResolutionMemoryStore
import cmm.cognitive as cognitive
import cmm.cognitive
```

when used to extend the real approved canonical MemoryStore base.

Result:

```text
V2_MEMORY_IMPORT_SPELLINGS=3/3 PASS
```

---

## 3.10 Requirements matrix — PASS

The canonical `DP-*` table now contains exactly one structural row:

```text
DP-039
```

The row correctly includes:

```text
Phase 10.39
canonical owner = domain.fragmentation
cmm/domains/validation_fragmentation.py
DomainFragmentationValidator / PipelineDomainValidator
approved design spec
approved implementation plan
AT-DP-039 path
IMPLEMENTED_PENDING_AUDIT
```

The AT table also contains:

```text
AT-DP-039
```

and points to:

```text
tests/domains/test_domain_architecture_guard_dp039_acceptance.py
```

Independent checks:

```text
DP039_ROWS=1
AT_DP039_ROWS=1
STALE_DP039_IMPLEMENTED_PENDING_REMEDIATION=0
```

The V2 MAJOR-03 documentation finding is remediated.

---

## 3.11 Normative roadmap restoration remains intact — PASS

The detailed roadmap retains the full original Phase 10.39 normative section:

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

and separately records implementation evidence.

It does not claim independent closure.

---

## 3.12 Scope — PASS

A pristine exact-archive comparison V2 → V3 shows only:

```text
cmm/domains/validation_fragmentation.py
tests/domains/test_domain_validation_fragmentation.py
tests/domains/test_domain_architecture_guard_dp039_acceptance.py
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
docs/audits/phase-10.39-independent-reaudit-v2.md
```

No unrelated production subsystem was modified.

Result:

```text
SCOPE=NARROW
PARALLEL_INFRASTRUCTURE=NO
```

---

## 3.13 Syntax compile — PASS

Independent:

```text
COMPILEALL=PASS
```

---

# 4. BLOCKER

## BLOCKER-01 — Canonical adapter immunity remains bypassable through attribute rebinding on a trusted imported module

**Severity:** BLOCKER
**Status:** OPEN

### V3 improvement

The V3 implementation correctly made top-level local-name bindings source-order aware.

It invalidates trusted local names for:

```text
Assign
AnnAssign
AugAssign
Delete
FunctionDef
AsyncFunctionDef
ClassDef
```

and therefore fixes the exact V2 cases such as:

```python
from cmm.planner import TaskPlanner
TaskPlanner = object
class EvilPlanner(TaskPlanner):
    pass
```

That now blocks correctly.

### Residual problem

The binding tracker invalidates only local `ast.Name` targets.

`_assigned_names(...)` returns names for:

```text
Name
Tuple/List
Starred
```

but not for:

```text
Attribute
```

As a result, an imported module binding remains trusted after one of its canonical members — or a trusted submodule path — is reassigned.

The adapter resolver therefore treats the later base expression as canonical even though ordinary Python execution would no longer resolve it to the canonical class.

---

## 4.1 Independently reproduced Planner bypass: module alias member reassignment

Input:

```python
import cmm.planner as planner

planner.TaskPlanner = object

class EvilPlanner(planner.TaskPlanner):
    pass
```

Expected:

```text
DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION
```

Actual V3:

```text
NO_FINDINGS
```

At runtime, the class inherits from `object`.

The fragmentation analyzer nevertheless grants Planner adapter immunity.

---

## 4.2 Independently reproduced Planner bypass: trusted root submodule reassignment

Input:

```python
import cmm.planner

cmm.planner = object

class EvilPlanner(cmm.planner.TaskPlanner):
    pass
```

Expected:

```text
DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION
```

Actual V3:

```text
NO_FINDINGS
```

The trusted root binding `cmm → cmm` remains in the binding table despite the statically explicit mutation of `cmm.planner`.

---

## 4.3 Independently reproduced Planner bypass: canonical member reassignment through root

Input:

```python
import cmm.planner

cmm.planner.TaskPlanner = object

class EvilPlanner(cmm.planner.TaskPlanner):
    pass
```

Expected:

```text
DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION
```

Actual V3:

```text
NO_FINDINGS
```

---

## 4.4 Independently reproduced WorkflowEngine bypass

Input:

```python
import cmm.workflows as workflows

workflows.WorkflowEngine = object

class EvilWorkflowEngine(workflows.WorkflowEngine):
    pass
```

Expected:

```text
DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION
```

Actual V3:

```text
NO_FINDINGS
```

---

## 4.5 Independently reproduced MemoryStore bypass

Input:

```python
import cmm.cognitive as cognitive

cognitive.InMemoryResolutionMemoryStore = object

class EvilMemoryStore(cognitive.InMemoryResolutionMemoryStore):
    pass
```

Expected:

```text
DOMAIN_FRAGMENTATION_MEMORY_DUPLICATION
```

Actual V3:

```text
NO_FINDINGS
```

---

## 4.6 Independent expanded V3 probe result

```text
planner member rebind via alias       FAIL
planner submodule rebind via root     FAIL
planner member rebind via root        FAIL
workflow member rebind                FAIL
memory-store member rebind            FAIL
```

Result:

```text
V3_EXTRA_BINDING_PROBES=0/5 PASS
V3_EXTRA_BINDING_FAILURES=5
```

Here `0/5 PASS` means none of the five expected blocking behaviors were satisfied.

---

## 4.7 Why this remains a blocker

DP-039 requires the existing canonical Domain Validation fragmentation boundary to fail closed on architectural attempts to recreate, redefine, or bypass shared CMM OS infrastructure while permitting legitimate adapters and canonical service reuse.

The current mechanism grants adapter immunity based on a canonical module/member path that no longer refers to the canonical owner at the protected class declaration.

This is the same security/architecture property as V1 and V2's canonical-adapter bypass:

```text
protected class
→ apparent canonical base
→ base was statically rebound
→ analyzer still grants immunity
→ fragmentation finding omitted
```

It is not a theoretical dynamic-code case.

The bypass is visible in ordinary top-level AST:

```text
Import
Assign(Attribute(...))
ClassDef
```

and requires no reflection, import hooks, metaprogramming, control-flow interpretation or code execution.

Because the exact Phase 10.39 authority boundary can still be intentionally escaped, the design point cannot be verified.

---

# 5. Required remediation for BLOCKER-01

Remain inside:

```text
cmm/domains/validation_fragmentation.py
```

Do not create another architecture subsystem.

The binding analysis must track enough statically explicit attribute invalidation to ensure an approved canonical module/member path remains trustworthy at the class declaration.

A narrow remediation should:

1. preserve the current source-order top-level state machine;
2. distinguish trusted module bindings from arbitrary names;
3. when a top-level assignment/delete/augmented assignment targets an attribute under a currently trusted canonical module binding, invalidate the affected trusted canonical path;
4. ensure later base resolution cannot treat that invalidated member/submodule path as canonical;
5. cover both imported module aliases (`planner.TaskPlanner = ...`) and unaliased roots (`cmm.planner = ...`, `cmm.planner.TaskPlanner = ...`);
6. preserve all V1 and V2 regression matrices;
7. avoid a general Python dataflow/interpreter;
8. continue to avoid importing or executing Domain Pack code.

A path-aware invalidation set is sufficient; a general static-analysis framework is out of scope.

---

# 6. AT-DP-039 verdict

## Positive

The V3 acceptance is materially improved.

It uses real:

```text
cmm.planner.TaskPlanner
```

and covers:

```text
from-import canonical reuse
unaliased module canonical reuse
rebound local canonical name
pathlib module-alias direct write
fragmentation_valid propagation
fragmentation_invalid installation rejection
no code execution
no filesystem side effects
```

The connected architecture remains correct.

## Blocking deficiency

The acceptance does not include the residual attribute-rebinding bypass.

Because `analyze_fragmentation(...)` returns no fragmentation finding for the independently reproduced cases, `DomainFragmentationValidator` has no fragmentation finding to convert into a failed `domain.fragmentation` step for those sources.

Therefore the connected acceptance does not establish the required fail-closed behavior for the actual V3 implementation.

Result:

```text
AT-DP-039=FAIL
```

---

# 7. DP-039 verdict

Positive:

```text
canonical owner preserved
no parallel guard
component-aware adapter mapping preserved
source-order local-name rebinding fixed
V1 matrix independently 12/12 PASS
V2 matrix independently 18/18 PASS
Memory import spellings independently 3/3 PASS
direct-write V2 issues remediated
requirements matrix remediated
roadmap remediated
23/23 events preserved
archive exact-head and clean
```

Negative:

```text
trusted canonical module/member attributes can be rebound
adapter immunity then remains active
protected Planner / WorkflowEngine / MemoryStore duplicates can evade fragmentation
```

Result:

```text
DP-039=NOT_VERIFIED
```

---

# 8. Documentation verdict

Independent result:

```text
REQUIREMENTS_MATRIX=PASS
DP039_ROW=PRESENT
AT_DP039_ROW=PRESENT
DP039_STATUS=IMPLEMENTED_PENDING_AUDIT
NORMATIVE_ROADMAP=PRESERVED
STALE_REMEDIATION_STATUS=ABSENT
DOCUMENTATION_STATUS=PASS
```

No documentation finding remains in V3.

---

# 9. Test / gate evidence

## Independent compile

```text
COMPILEALL=PASS
```

## Independent focused pytest

The independent audit runtime still lacks:

```text
libcst
```

and therefore focused pytest collection cannot complete.

Observed:

```text
ModuleNotFoundError: No module named 'libcst'
```

This is an auditor-environment limitation and is not counted as a product finding.

## Agent-supplied repository execution evidence

The V3 remediation agent reports:

```text
FOCUSED=145 passed
INHERITED_REGRESSIONS=148 passed
DOMAIN_SUITE=8902 passed
GLOBAL_SUITE=14457 passed
V1_REGRESSION_MATRIX=12/12 PASS
V2_REGRESSION_MATRIX=18/18 PASS
V2_MEMORY_IMPORT_SPELLINGS=3/3 PASS
CHANGED_PYTHON_RUFF=PASS
CHANGED_PYTHON_FORMAT=PASS
GLOBAL_RUFF_DIFFERENTIAL=PASS
GLOBAL_FORMAT_DIFFERENTIAL=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
```

The independent audit directly reproduced the V1/V2 matrices from exact V3 source and confirmed those advertised matrices.

The V3 FAIL does not rely on inability to rerun pytest or Ruff.

It relies on five independently reproduced failures in the stdlib-only fragmentation analyzer.

---

# 10. Public-contract verdict

Canonical integration contracts remain unchanged and correctly connected:

```text
DomainFragmentationValidator
PipelineDomainValidator
fragmentation_valid
ensure_domain_validation_allows_install(...)
STEP_FRAGMENTATION
```

Result:

```text
PUBLIC_CANONICAL_PATH=PRESERVED
PUBLIC_CONTRACT_REGRESSION=NONE_FOUND
```

---

# 11. Scope verdict

Exact V2 → V3 archive comparison is narrow:

```text
production:
  cmm/domains/validation_fragmentation.py

tests:
  tests/domains/test_domain_validation_fragmentation.py
  tests/domains/test_domain_architecture_guard_dp039_acceptance.py

documentation:
  docs/reference/domain-intelligence-requirements-matrix.md
  docs/roadmap/phase-10-domain-intelligence.md
  docs/audits/phase-10.39-independent-reaudit-v2.md
```

Result:

```text
SCOPE=PASS
```

---

# 12. Final Independent Re-audit V3 verdict

```text
PHASE=10.39
AUDIT=INDEPENDENT_REAUDIT_V3

AUDITED_HEAD=7011f552c4d592554b8368b837c3e17e1a0af559
AUDIT_BUNDLE_SHA256=8f39f810470960d37fd55be8bf3b07577192373228ad5240398dfa50203de4ee

BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS

BLOCKERS=1
MAJORS=0
MINORS=0

DP-039=NOT_VERIFIED
AT-DP-039=FAIL

CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL
```

Phase 10.39 must remain:

```text
REMEDIATION_REQUIRED
```

It must not be closed.

---

# 13. V3 remediation boundary

The next remediation must be smaller than V2 remediation.

Required work only:

```text
1. close canonical module/member attribute-rebinding adapter bypasses;
2. add RED regressions for the five independently reproduced V3 cases;
3. strengthen connected AT-DP-039 with at least one attribute-rebinding case;
4. preserve V1 12/12, V2 18/18 and Memory 3/3 matrices;
5. preserve the now-correct DP-039 requirements mapping and roadmap;
6. rerun focused, inherited, Domain, global, differential Ruff/format, compileall and diff gates;
7. commit remediation;
8. keep worktree clean and quarantine stash unchanged;
9. create a NEW exact-HEAD V4 git archive;
10. calculate a NEW SHA-256;
11. submit V4 for Independent Re-audit V4.
```

Do not broaden Phase 10.39.

Do not start Phase 10.40.

Do not modify V1, V2 or V3 bundles.

---

# 14. Closure requirements remain unmet

A future independent PASS must reach at least:

```text
BLOCKERS=0
MAJORS=0
DP-039=VERIFIED_EXISTING
AT-DP-039=PASS
CLOSURE_ELIGIBLE=YES
```

Only then may the separate docs-only closure commit be created.
