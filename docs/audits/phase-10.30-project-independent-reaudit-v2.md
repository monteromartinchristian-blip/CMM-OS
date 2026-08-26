# Phase 10.30 — Project Domain Independent Re-Audit V2

**Date:** 2026-08-26
**Candidate HEAD:** `836fadc4a3fc09a808de38cc6b01817d2257c97c`
**Bundle:** `phase-10.30-audit-v2.tar.gz`
**Bundle SHA-256:** `c00d90a6fc17614364c238bb858191b0a78a61734fa8c930dd237a47ab0e8782`
**Independent verdict:** **FAIL — targeted remediation still required**

```text
PHASE10_30_INDEPENDENT_REAUDIT_V2=FAIL
BLOCKERS=1
MAJORS=2
MINORS=1

B1=OPEN
B2=CLOSED
M1=CLOSED
M2=OPEN
M3=CLOSED
M4=CLOSED_WITH_MINOR_FOLLOWUP
M5=OPEN

DP_030=REQUIRES_PHASE_INSPECTION
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
NEXT=REMEDIATION_V2
```

---

## 1. Independent bundle verification

The uploaded V2 archive is now a valid full versioned snapshot.

Independent verification:

```text
SHA256=c00d90a6fc17614364c238bb858191b0a78a61734fa8c930dd237a47ab0e8782
ARCHIVE_ENTRIES=1828
ROOT_PREFIX=ABSENT
ROADMAP.md=PRESENT
FULL CMM SOURCE TREE=PRESENT
```

Git's archive PAX metadata independently identifies:

```text
836fadc4a3fc09a808de38cc6b01817d2257c97c
```

so the uploaded bundle is confirmed to come from the candidate HEAD reported by the remediation agent.

Independent structural checks:

```text
PROJECT_PRODUCTION_MODULES=14
ENTITIES=27
RESOURCES=22
RULES=18
OPERATIONS=20
WORKFLOWS=12
AT_DP_030_CHECKPOINT_LABELS=56 unique=56
ADVERSARIAL_ATTACK_CLASSES=34 unique=34
COMPILEALL=PASS
```

Independent pytest execution remains blocked by the audit container's missing project dependency:

```text
ModuleNotFoundError: No module named 'libcst'
```

This is an auditor-environment limitation, not a candidate defect.

---

# 2. V1 finding disposition

## B1 — Project → Life Plan runtime authorization

**Status: OPEN — BLOCKER**

The remediation added:

```python
authorize_project_life_plan_contribution(...)
```

and correctly rejects:

- missing evidence;
- raw mappings;
- strings;
- mismatched source requests;
- mismatched target requests;
- DENY results;
- expired requests.

The resolver and gate paths are materially better.

However, the implementation also accepts a caller-supplied:

```python
CrossDomainPermissionDecision
```

directly.

Relevant branch:

```python
elif permission_decision is not None:
    if not isinstance(permission_decision, CrossDomainPermissionDecision):
        raise TypeError(...)
    if permission_decision.decision is not PermissionOutcome.ALLOW:
        raise PermissionError(...)
    if (
        permission_request is not None
        and permission_decision.request_id != permission_request.request_id
    ):
        raise PermissionError(...)
    auth_verified = True
    auth_ref = permission_decision.request_id
```

`CrossDomainPermissionDecision` is a public frozen dataclass and can be constructed directly by a caller:

```python
CrossDomainPermissionDecision(
    request_id="caller:forged",
    decision=PermissionOutcome.ALLOW,
)
```

No permission request is required in this branch.

Therefore there is no binding to:

```text
source domain
target domain
actor
session
purpose
resource
temporal context
resolver/gate provenance
```

### Independent reproduction

The exact bundled function body was executed in isolation with the actual branch semantics.

Input:

```text
raw_payload={"project_status_impact": "active"}

permission_decision=
CrossDomainPermissionDecision(
    request_id="caller:forged",
    decision=ALLOW
)
```

Result:

```text
{
  "source_domain": "domain:project",
  "project_status_impact": "active",
  "authorization_reference": "caller:forged"
}
```

Result:

```text
B1_CALLER_CONSTRUCTED_TYPED_DECISION_FORGE=REPRODUCED
```

This directly violates the remediation requirement:

```text
runtime-owned, verifiable authorization evidence
caller-created objects are not authority
```

### Additional AT-DP-030 issue

The connected acceptance still does not exercise a successful authorized Project → Life Plan path.

Checkpoint 27 deliberately expects:

```python
with pytest.raises(PermissionError):
    authorize_project_life_plan_contribution(...)
```

and checkpoint 28 then uses the pure minimizer:

```python
build_project_life_plan_projection(...)
```

So the connected gate still records the denied path and then proceeds without demonstrating runtime-authorized contribution.

### Required remediation

Remove standalone `permission_decision` authority.

Accept authorization only when the decision is obtained during the call from a trusted shared:

```text
DomainPermissionGate
or
DomainPermissionResolver
```

using the supplied typed request.

If a decision object must be supported for another shared reason, it must be verifiably bound to a runtime trust root/repository and to the original request; the current public dataclass alone cannot prove that.

AT-DP-030 checkpoint 27/28 must become:

```text
real runtime authorization succeeds
→ authorized purpose-minimized contribution produced
→ Life Plan consumer verifies/uses it
```

and must include a caller-created typed decision adversarial probe.

---

## B2 — Caller-controlled committed-state forgery

**Status: CLOSED**

`build_prepare_commit_readiness_result(...)` now always returns:

```python
"committed": False
```

and does not return an authoritative commit reference.

The V1 exploit:

```text
validation=False
gate=False
approval=None
authoritative_commit_reference="caller:fake"
```

can no longer produce `committed=True`.

No Project-local Git commit implementation was introduced.

This finding is independently accepted as closed.

---

## M1 — Project bootstrap skipped Life Plan chain

**Status: CLOSED**

`build_standard_project_domain_bootstrap()` now uses:

```python
prior = build_standard_life_plan_domain_bootstrap()
```

and registers Project into the same registry instances.

The implementation preserves:

```text
General
Life Plan
Project
```

without auto-registering Mental Health or Neurodivergence.

This finding is independently accepted as closed.

---

## M2 — Self-development E2E did not execute shared runtime

**Status: OPEN — MAJOR**

The V2 test is materially stronger than V1:

- creates a real temporary Git repository;
- executes `ProjectAnalyzer`;
- executes a real semantic Python mutation using `Runtime`;
- evaluates a real `CommitGateEvaluator`;
- checks Git HEAD remains unchanged;
- builds/validates real trace objects.

However, it still does **not** execute the frozen self-development contract end-to-end.

### A. No real shared planning/development path

The frozen implementation plan requires:

```text
Use the existing shared planning/development contract.
Project must not instantiate a custom planner.
```

The V2 E2E imports no shared planner/development planning service and produces no real implementation-plan artifact.

### B. Permission gate is not connected to the mutation

The test proves an unapproved `project.modify_code` evaluation returns:

```text
APPROVAL_REQUIRED / DENY
```

but then directly calls:

```python
Runtime().run(runtime_action)
```

without obtaining and consuming a real approval and without executing the injected `project.modify_code` implementation through the Domain Operation/Agent Runtime path.

So it demonstrates:

```text
gate blocks one path
+
an unrelated direct runtime mutates the file
```

rather than:

```text
approved Project operation
→ controlled shared mutation
```

### C. Rollback/transaction is not actually executed

The test only verifies that `git diff --stat` sees the changed file.

It does not force a downstream failure and prove the shared transaction/rollback restores:

```text
source bytes
working-tree state
operation outcome
```

### D. Phase 7 validation is still synthetic

The test manually constructs:

```python
ValidationStepResult(...)
ValidationResult(...)
```

with all statuses set to `PASSED`, then calls:

```python
CommitGateEvaluator.evaluate(...)
```

It never runs:

```text
ValidationPipeline
ValidationApplicationService
ValidationIntegrationService
or another actual Phase 7 validation execution path
```

against the modified temporary repository.

This directly contradicts the frozen Task 16 / remediation Task 6 requirement:

```text
Run the existing Phase 7 validation service/pipeline against the changed temporary project.
Capture its authoritative result/reference.
```

### E. Approval evidence remains a caller string in the E2E

Readiness is produced with:

```python
approval_reference="approval:user_grant_001"
```

without a canonical approval grant being created/consumed in the test.

### AT-DP-030 still overstates M2 behavior

The following checkpoint labels remain unsupported by their bodies:

```text
44 controlled semantic mutation runs in temp repo
45 shared rollback/transaction path is present
46 shared Phase 7 validation executes
```

but they only assert:

```text
operation metadata
callable(register_project_domain)
run_validation operation definition exists
```

No temp repository, runtime mutation, rollback, or validation pipeline is executed in those checkpoints.

### Required remediation

Follow the already-frozen Task 16 literally:

```text
real temporary repository
→ ProjectAnalyzer
→ real shared planning/development contract
→ DomainPermissionGate
→ real canonical approval creation/consumption
→ injected project.modify_code implementation
→ shared controlled semantic mutation
→ forced failure + real transaction rollback
→ real Phase 7 ValidationPipeline/service execution
→ failed validation readiness false
→ successful validation readiness true
→ Git HEAD unchanged
→ memory/trace from actual runtime outputs
```

AT-DP-030 checkpoints 36/38/44/45/46 must carry or execute real artifacts instead of catalog/metadata existence checks.

---

## M3 — Independent trace inventory/validation

**Status: CLOSED**

V2 now explicitly builds a:

```python
DomainTraceReferenceInventory
```

before final trace assembly, computes the shared identity, assembles the trace, and invokes:

```python
validate_project_trace(...)
```

The dedicated trace tests include tampered/incorrect inventory cases.

AT-DP-030 checkpoints 31/32 now perform the required preassembly inventory and real validation.

This finding is independently accepted as closed.

---

## M4 — Canonical reference documentation diverged from catalog

**Status: CLOSED, with one MINOR follow-up**

The core V1 defect is fixed.

Independent set verification found every canonical ID from:

```text
CANONICAL_PROJECT_ENTITY_IDS
CANONICAL_PROJECT_RESOURCE_IDS
CANONICAL_PROJECT_RULE_IDS
CANONICAL_PROJECT_OPERATION_IDS
CANONICAL_PROJECT_WORKFLOW_IDS
```

present in `docs/reference/project-domain.md`.

Result:

```text
ENTITY_IDS_MISSING=0
RESOURCE_IDS_MISSING=0
RULE_IDS_MISSING=0
OPERATION_IDS_MISSING=0
WORKFLOW_IDS_MISSING=0
```

The reference now reflects the real `27 / 22 / 18 / 20 / 12` catalog.

### Minor follow-up D1

The remediation plan also required:

- a documentation/catalog consistency regression;
- roadmap/matrix status updated to record Audit V1 FAIL and Re-audit V2 pending.

Neither is present.

`tests/domains/test_project_domain_catalog.py` contains no reference-document consistency test.

The roadmap and requirements matrix still use generic wording such as:

```text
independent audit pending
```

rather than recording:

```text
Independent Audit V1 = FAIL
Independent Re-audit V2 = pending
```

This no longer makes the canonical inventory incorrect, so it is classified **MINOR**, not MAJOR.

Required remediation:

- add a mechanical catalog/reference consistency assertion;
- update Project status in `ROADMAP.md`,
  `docs/roadmap/phase-10-domain-intelligence.md`, and
  `docs/reference/domain-intelligence-requirements-matrix.md`
  with the actual audit lineage.

---

## M5 — Software capability activation accepts ungrounded caller primitives

**Status: OPEN — MAJOR**

The V2 function correctly rejects:

```text
workflow_id="project.software_forged"
resource_ids=("attacker.source_code",)
repository_backed=True
```

However it still accepts other caller-created primitives without provenance.

Relevant implementation:

```python
for cap in capabilities:
    if cap in SOFTWARE_CAPABILITY_NAMES:
        return True

for r_id in resource_ids:
    base = r_id.split(":", 1)[0]
    if base in CANONICAL_SOFTWARE_RESOURCE_IDS or base in SOFTWARE_RESOURCE_KINDS:
        return True

if repository_context is not None:
    ...
    if isinstance(repository_context, dict) and (
        "repo_path" in repository_context
        or "repository_id" in repository_context
    ):
        return True
```

### Independent reproduction

The exact bundled function body was executed independently:

```text
repository_context={"repo_path": "/tmp/fake"}
→ True

capabilities=("project_software_development",)
→ True

resource_ids=("source_code",)
→ True
```

while the already-added negative cases correctly return false:

```text
workflow_id="project.software_forged"
→ False

resource_ids=("attacker.source_code",)
→ False

repository_backed=True
→ False
```

Result:

```text
M5_CALLER_MAPPING_CONTEXT_ACTIVATION=REPRODUCED
M5_CALLER_CAPABILITY_STRING_ACTIVATION=REPRODUCED
M5_CALLER_RESOURCE_KIND_ACTIVATION=REPRODUCED
```

This violates the remediation contract:

```text
mappings or caller-created objects are not authority
resolved canonical/shared evidence required
```

AT-DP-030 checkpoint 34 itself uses:

```python
repository_context={"repo_path": "/path/to/repo"}
```

as positive grounding evidence, so the connected acceptance currently endorses the remaining bypass.

### Required remediation

Ground activation using actual resolved objects/registries.

Preferred minimal direction:

```text
workflow/operation:
  require exact registered/resolved canonical definition,
  or pass a verified resolved-context object rather than an ID string alone

resource:
  require resolved canonical DomainResourceDefinition/reference,
  not a bare resource kind string

repository:
  require actual shared ProjectContext (or another canonical shared context type)
  produced by ProjectAnalyzer/shared runtime,
  not a mapping with a repo_path key

capability:
  require resolved canonical capability context,
  not a caller string
```

Do not reintroduce prefixes/suffix matching.

---

# 3. AT-DP-030 disposition

The bundle contains exactly:

```text
56 unique checkpoint labels
```

but the connected acceptance is still not independently accepted.

Material mismatches remain:

```text
27 claims real Project→Life Plan permission request resolved
   but the test expects PermissionError

28 produces the pure projection after that denied path

34 uses a caller-created repository mapping as grounding

36 calls resource-definition existence "repository observation"

38 calls workflow-node existence "shared planning path"

44 calls operation metadata "controlled semantic mutation runs in temp repo"

45 calls callable(register_project_domain) "shared rollback/transaction path"

46 calls operation-definition existence "shared Phase 7 validation executes"
```

Therefore:

```text
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
```

The count must remain 56, but the bodies must execute the named behavior.

---

# 4. Permanent adversarial gate disposition

The bundle contains exactly:

```text
34 unique top-level test_attack_* functions
```

and several V1 attacks were materially strengthened.

However the gate does not cover:

```text
caller-created typed CrossDomainPermissionDecision(ALLOW)
caller-created repository_context mapping with repo_path
raw accepted canonical software capability string
bare accepted software resource-kind string
```

Therefore:

```text
PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
```

Keep 34 top-level attack classes and strengthen the relevant existing classes with these subcases.

---

# 5. Re-audit V2 acceptance matrix

```text
B1_PROJECT_LIFE_PLAN_RUNTIME_AUTHORIZATION=FAIL
B1_RAW_MAPPING_NOT_AUTHORITY=PASS
B1_FORGED_PERMISSION_EVIDENCE_REJECTED=PARTIAL
B1_CONTEXT_PURPOSE_TARGET_MISMATCH_REJECTED=PARTIAL

B2_CALLER_COMMIT_REFERENCE_NOT_AUTHORITY=PASS
B2_FAILED_VALIDATION_CANNOT_COMMIT=PASS
B2_DENIED_GATE_CANNOT_COMMIT=PASS
B2_MISSING_APPROVAL_CANNOT_COMMIT=PASS
B2_COMMIT_OUTCOME_RUNTIME_OWNED=PASS

M1_PROJECT_BOOTSTRAP_EXTENDS_10_29=PASS
M1_GENERAL_FALLBACK_PRESERVED=PASS

M2_TEMP_REPOSITORY_SELF_DEVELOPMENT=PARTIAL
M2_SHARED_REPOSITORY_ANALYSIS=PASS
M2_SHARED_PLANNING=FAIL
M2_CONTROLLED_MUTATION=FAIL
M2_TRANSACTION_ROLLBACK=FAIL
M2_PHASE7_VALIDATION_REAL=FAIL
M2_PREPARE_COMMIT_HEAD_UNCHANGED=PASS

M3_TRACE_INVENTORY_PREASSEMBLY=PASS
M3_TRACE_VALIDATION_REAL=PASS
M3_TRACE_TAMPER_REJECTED=PASS

M4_REFERENCE_INVENTORY_MATCHES_CATALOG=PASS
M4_AGENT_REPORT_GENERATED_FROM_CATALOG=PASS
M4_DOCUMENTATION_REGRESSION=FAIL_MINOR
M4_AUDIT_LINEAGE_STATUS=FAIL_MINOR

M5_FAKE_WORKFLOW_ACTIVATION_REJECTED=PASS
M5_SUFFIX_COLLISION_RESOURCE_REJECTED=PASS
M5_REPOSITORY_SIGNAL_GROUNDED=FAIL
M5_CALLER_CAPABILITY_NOT_AUTHORITY=FAIL
M5_BARE_RESOURCE_KIND_NOT_AUTHORITY=FAIL

AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
```

---

# 6. Final independent verdict

```text
PHASE10_30_INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=1
MAJORS=2
MINORS=1

B1=OPEN
B2=CLOSED
M1=CLOSED
M2=OPEN
M3=CLOSED
M4=CLOSED_WITH_MINOR_FOLLOWUP
M5=OPEN

DP_030=REQUIRES_PHASE_INSPECTION
INDEPENDENT_REAUDIT_V3=REQUIRED
PUSH=NO
MERGE=NO
NEXT=PHASE_10_30_REMEDIATION_V2
```

The V2 remediation made substantial progress and closed three of the four most structural V1 defects, but Phase 10.30 cannot yet be independently closed.
