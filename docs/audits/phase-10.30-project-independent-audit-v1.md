# Phase 10.30 — Project Domain Independent Audit V1

**Date:** 2026-08-26
**Candidate:** `79ab64d` (as reported by the implementation agent)
**Bundle:** `phase-10.30-audit-v1.tar.gz`
**Bundle SHA-256:** `e287c8ffd09c053a2c8588934286f5267a2c109ca7a4c04c78d82bbf621c8d57`
**Independent verdict:** **FAIL — remediation required**

```text
INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=2
MAJORS=5
MINORS=0
DP_030=REQUIRES_PHASE_INSPECTION
AT_DP_030=CANDIDATE_REPORTED_PASS_BUT_NOT_INDEPENDENTLY_ACCEPTED
CLOSURE_ADVERSARIAL_GATE=CANDIDATE_REPORTED_PASS_BUT_INCOMPLETE
NEXT=REMEDIATION_V1
```

---

## 1. Audit scope and method

The audit used the uploaded versioned candidate archive as the implementation source of truth.

Independent integrity verification:

```text
SHA256 phase-10.30-audit-v1.tar.gz
= e287c8ffd09c053a2c8588934286f5267a2c109ca7a4c04c78d82bbf621c8d57
MATCHES_CANDIDATE_REPORT=PASS
```

Independent static inventory extraction from `cmm/domains/project/catalog.py`:

```text
PROJECT_PRODUCTION_MODULES=14
ENTITIES=27 unique=27
RESOURCES=22 unique=22
RULES=18 unique=18
OPERATIONS=20 unique=20
WORKFLOWS=12 unique=12
PROJECT_TEST_FILES=18
ADVERSARIAL_TEST_FUNCTIONS=34
AT_DP_030_CHECKPOINT_CALLS=56
```

Independent syntax compilation:

```text
python -m compileall -q cmm/domains/project tests/domains/test_project_domain_*.py
COMPILEALL=PASS
```

Independent full pytest collection could not be performed in the audit container because the environment lacks the project dependency `libcst`. Importing the CMM package graph fails at:

```text
ModuleNotFoundError: No module named 'libcst'
```

This is an auditor-environment limitation and is **not** counted as a candidate defect.

`ruff` is also unavailable in the independent audit environment. Candidate-reported suite/lint counts therefore remain reported evidence, not independently re-executed evidence.

The audit additionally executed isolated copies of the exact bundled pure-function bodies for the security-relevant findings below.

---

# 2. Positive findings

The candidate has substantial correct structure.

Verified directly from the bundle:

- exactly 14 canonical Project modules;
- exact frozen `27 / 22 / 18 / 20 / 12` catalog counts;
- one `domain:project` / `ProjectProfile`;
- generic and software rule partitions match the frozen design;
- canonical `project.review_change` is present and legacy `project.prepare_change_review` is excluded from the canonical operation inventory;
- no Project-local planner, agent runtime, workflow engine, memory store, trace store, unrestricted shell execution, `os.system`, `shell=True`, or `domain-trace:probe` was found;
- Project operations are declarative and use the shared operation registry;
- file modification is approval-gated in the Project permission policy;
- memory proposals are proposal-only and require confirmation;
- registration captures snapshots and performs rollback on mutation failure;
- Formation is not introduced as a Project entity/rule/operation/workflow;
- candidate documentation correctly keeps `DP-030=REQUIRES_PHASE_INSPECTION` and independent audit pending.

These positives are preserved by the remediation requirements below.

---

# 3. BLOCKERS

## B1 — Project → Life Plan cross-domain authorization is bypassable

### Required contract

The frozen implementation plan requires:

```text
build_project_life_plan_projection(...)
+
authorize_project_life_plan_contribution(...)
using the real shared permission gate/resolver
```

and explicitly states that:

```text
Presence of Life Plan, a raw decision ID, is_authorized=True,
or a forged permission result is not enough.
```

### Candidate implementation

`cmm/domains/project/rules.py` exposes only:

```python
def build_project_life_plan_projection(
    raw_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
```

It filters fields but receives no runtime-owned authorization evidence.

The candidate Project permission policy also has outbound cross-domain access disabled.

The connected acceptance test demonstrates the contradiction:

```text
checkpoint 27:
Project → Life Plan DOMAIN_CROSS_ACCESS
=> DENY

checkpoint 28:
build_project_life_plan_projection(raw_project_data)
=> projection produced anyway
```

There is no `authorize_project_life_plan_contribution(...)` implementation in the canonical package.

### Independent reproduction

The exact bundled projection helper was executed in isolation:

```text
input:
{
  "project_status_impact": "active",
  "timeline_impact": "Q4"
}

authorization evidence:
NONE

result:
{
  "source_domain": "domain:project",
  "project_status_impact": "active",
  "timeline_impact": "Q4"
}
```

Result:

```text
B1_UNAUTHORIZED_PROJECT_LIFE_PLAN_PROJECTION=REPRODUCED
```

### Impact

A caller can construct a Life Plan-shaped Project projection without passing the required shared permission/trust boundary. Field minimization is useful but does not establish authorization, provenance ownership, actor/session/purpose binding, target-domain binding, or temporal validity.

This is the same class of trust-root failure previously treated as a blocker in hardened cross-domain Domain Packs.

### Required remediation

Implement the frozen real authorization path, preferably by reusing the already-hardened shared/Life Plan cross-domain authorization mechanism.

The remediated API must:

- require runtime-owned permission/gate evidence;
- bind source `domain:project`;
- bind target `domain:life-plan`;
- bind actor/session/purpose/context where the shared contract supports it;
- reject denied, missing, forged, stale, mismatched, caller-constructed, or unverified evidence;
- create the authorized contribution only after purpose minimization;
- preserve the Life Plan consumer trust boundary;
- add direct and wrapped-forgery adversarial regressions;
- update AT-DP-030 so its Project→Life Plan checkpoint actually succeeds through the authorized path rather than observing DENY and bypassing it.

---

## B2 — Caller-controlled commit reference can forge `committed=True`

### Required contract

The frozen design states that `project.prepare_commit`:

```text
does not perform git commit
must not fabricate a commit hash
must not claim a commit occurred
must not promote ready_for_approved_commit to committed
without authoritative shared commit outcome
```

### Candidate implementation

`cmm/domains/project/operations.py` contains:

```python
ready_for_approved_commit = (
    bool(validation_passed)
    and bool(commit_gate_allowed)
    and (approval_reference is not None)
)

committed = authoritative_commit_reference is not None
```

`authoritative_commit_reference` is a raw caller-provided `str | None`. No shared commit outcome, trust token, permission proof, repository verification, or authority binding is required.

### Independent reproduction

The exact bundled function body was executed in isolation:

```text
validation_passed=False
commit_gate_allowed=False
approval_reference=None
authoritative_commit_reference="caller:fake"
```

Actual result:

```text
ready_for_approved_commit=False
committed=True
authoritative_commit_reference="caller:fake"
```

A second probe with failed validation and an arbitrary approval string also returned:

```text
committed=True
```

Result:

```text
B2_CALLER_COMMIT_STATUS_FORGE=REPRODUCED
```

### Impact

Project can represent an unvalidated, unapproved, caller-invented string as an authoritative committed state. This violates the phase's explicit state distinction:

```text
proposal != decision
planned != completed
ready_for_commit != committed
```

and may contaminate presentation, memory proposals, traces, or downstream reasoning with a false repository state.

### Required remediation

Remove caller authority over committed state.

Acceptable patterns include:

- `project.prepare_commit` never emits `committed=True`; it ends only at `ready_for_approved_commit`; or
- a separate reflection helper consumes a **runtime-owned, verifiable shared commit outcome** whose authority, repository/change identity, and request context are validated before reflecting committed state.

A plain string, boolean, arbitrary mapping, or caller-created object must never prove commit completion.

Add adversarial regressions for:

```text
fake authoritative_commit_reference
validation failed + fake reference
gate denied + fake reference
missing approval + fake reference
mismatched change/repository reference
caller-created wrapped commit outcome
```

---

# 4. MAJOR FINDINGS

## M1 — Canonical Project bootstrap does not extend the frozen 10.29 chain

### Required contract

The frozen spec and Task 14 require:

```python
prior = build_standard_life_plan_domain_bootstrap()
register_project_domain(...same registry objects...)
```

and explicitly prohibit a General-only bootstrap.

### Candidate implementation

`cmm/domains/project/bootstrap.py` imports:

```python
build_standard_general_domain_bootstrap
```

and executes:

```python
general = build_standard_general_domain_bootstrap()
register_project_domain(...general registries...)
```

The bootstrap test only proves:

```text
General present
Project present
```

It does not prove Life Plan or the required prior chain is preserved.

### Impact

The canonical “standard Project bootstrap” can construct a registry set that omits the completed 10.29 Domain Pack and therefore does not satisfy the frozen composition contract for extending the existing standard chain.

### Required remediation

Make Project bootstrap consume the 10.29 standard bootstrap as specified and assert at minimum:

```text
domain:general present
domain:life-plan present
domain:project present
mental-health absent
neurodivergence absent
same registry objects reused
General fallback preserved
```

If the existing 10.29 bootstrap itself is insufficient to represent the intended chain, stop and prove that as a shared architectural defect before modifying shared infrastructure.

---

## M2 — Self-development E2E does not execute the required shared runtime path

### Required contract

Task 16 requires a real temporary Git/Python repository and actual shared:

```text
repository observation
planning/development contract
permission + approval
controlled semantic mutation
rollback/transaction
Phase 7 validation
commit readiness
```

### Candidate test

`tests/domains/test_project_domain_self_development_e2e.py` has no `tmp_path` repository fixture and does not execute repository analysis, a shared planner, semantic mutation, transaction rollback, or Phase 7 validation.

Instead it uses:

- caller-created reasoning metadata;
- a permission-gate check;
- synthetic validation strings such as `"validation:phase7:pass"`;
- pure readiness result builders;
- memory/trace builders.

AT-DP-030 repeats this weakness.

Examples of checkpoint labels versus actual proof:

```text
36 "repository observation uses shared infrastructure"
   -> only checks a resource definition exists

38 "implementation plan uses shared planning path"
   -> only checks a workflow node exists

44 "controlled semantic mutation runs in temp repo"
   -> only asserts requires_approval/reversible/rollback_policy_id

45 "shared rollback/transaction path is present"
   -> only asserts callable(register_project_domain)

46 "shared Phase 7 validation executes"
   -> only checks project.run_validation definition exists
```

### Impact

The candidate does not prove the historical Project self-development requirement or that Project correctly composes with the existing development/execution/validation stack.

### Required remediation

Implement the exact Task 16 E2E:

- temporary Git/Python project;
- real shared repository observation;
- real shared planning/development path;
- permission/approval gate;
- injected `project.modify_code` delegate using existing controlled mutation;
- real rollback/transaction path;
- real Phase 7 validation;
- failed-validation case;
- successful validation readiness case;
- unchanged Git HEAD across `prepare_commit`;
- memory/trace evidence from real runtime outputs.

---

## M3 — AT-DP-030 does not build or validate an independent trace inventory

### Required contract

The frozen design requires:

```text
independent trace inventory
→ final trace assembly
→ trace validation
```

The inventory must be constructed from expected/runtime-owned artifacts **before** final trace assembly and not derived from the finished trace.

### Candidate acceptance

Checkpoint 31 is labelled:

```text
"independent trace inventory built before trace"
```

but only constructs two `DomainTraceReference` objects.

No `DomainTraceReferenceInventory` is built.

Checkpoint 32 is labelled:

```text
"DomainTrace assembled and validated"
```

but only calls `assemble_project_trace(...)` and asserts status/domain.

It never calls:

```python
validate_project_trace(...)
```

The permanent adversarial test named `test_attack_trace_inventory_independent()` only checks that two references have different values. It does not construct an independent inventory or validate a trace against it.

### Impact

A frozen provenance invariant and a named AT-DP-030 checkpoint are claimed without the corresponding behavior being executed.

### Required remediation

Rebuild the acceptance trace segment using the same hardened pattern established after the Life Plan trace remediation:

```text
runtime/expected reference artifacts
→ independent DomainTraceReferenceInventory
→ calculate shared preassembly identity where required
→ assemble trace
→ validate trace against prebuilt inventory
```

The adversarial gate must prove that constructing expected inventory from the final trace, omitting references, adding references, or substituting forged references fails.

---

## M4 — Canonical Project reference documentation is materially inconsistent with code/spec

`docs/reference/project-domain.md` and the implementation agent's final report list a different canonical inventory than `catalog.py` and the frozen spec.

Independent set comparison found:

```text
Entities:
19 actual IDs missing from reference
19 noncanonical IDs added by reference

Resources:
16 actual IDs missing
16 noncanonical IDs added

Rules:
all 18 canonical rule IDs missing
18 noncanonical `project.rule.*` IDs added

Operations:
8 canonical IDs missing
8 noncanonical IDs added

Workflows:
7 canonical IDs missing
7 noncanonical IDs added
```

Examples:

```text
actual entity: project.entity.objective
reference:     project.entity.task

actual resource: project.resource.milestone_record
reference:       project.resource.milestone_schedule

actual rule: project.scope_consistency
reference:   project.rule.scope_consistency

actual operation: project.create_implementation_plan
reference:       project.plan_implementation

actual workflow: project.feature_implementation
reference:      project.code_modification
```

The candidate report repeats the same incorrect inventory.

### Impact

The canonical reference documentation does not describe the implementation it claims to document. This is especially material for Project because code/documentation consistency is itself part of the Project contract.

### Required remediation

Generate the inventory section directly from or mechanically verify it against `cmm/domains/project/catalog.py`.

Add a regression asserting exact documented canonical IDs or use a documentation-generation/check mechanism already present in the repository.

Do not change the correct frozen catalog merely to match the incorrect reference document.

---

## M5 — Software capability activation trusts ungrounded caller primitives

### Required contract

Software capability activation must be grounded by an explicit canonical workflow/operation/resource/capability or equivalent shared resolved context.

### Candidate implementation

`project_software_capability_active(...)` accepts raw primitives and includes:

```python
if workflow_id.startswith("project.software"):
    return True
```

It also accepts any resource ID whose final token matches a software resource kind.

`repository_backed=True` is accepted as sufficient by itself.

No registry resolution, resource definition, goal/request authority, or provenance evidence is required.

### Independent reproduction

The exact bundled function body returned:

```text
workflow_id="project.software_forged"
=> True

resource_ids=("attacker.source_code",)
=> True

repository_backed=True
=> True
```

Result:

```text
M5_SOFTWARE_CAPABILITY_UNGROUNDED_ACTIVATION=REPRODUCED
```

### Impact

A generic Project request can be shifted into software-specific reasoning semantics through fabricated strings or booleans without proving repository/software context.

This does not itself grant file mutation authority, so it is classified MAJOR rather than BLOCKER, but it violates the phase's central generic-vs-software boundary.

### Required remediation

Require grounded canonical evidence:

- exact registered software workflow ID;
- exact registered software operation ID;
- resolved canonical Project resource definition/reference;
- verified repository-backed goal/context from shared runtime;
- resolved software capability from shared Domain contracts.

Remove wildcard/prefix activation from untrusted strings.

Add negative tests for forged workflow IDs, suffix-collision resource IDs, arbitrary booleans, and caller-provided fake capability context.

---

# 5. Acceptance and adversarial-gate disposition

The candidate reported:

```text
AT_DP_030=PASS
AT_DP_030_CHECKPOINTS=56
PROJECT_CLOSURE_ADVERSARIAL_GATE=PASS
PROJECT_CLOSURE_ATTACK_CLASSES=34
```

The audit confirms that there are structurally 56 checkpoint calls and 34 `test_attack_*` functions.

However, several checkpoints/attack classes do not execute the behavior named by their labels, including the cross-domain authorization, self-development runtime, and independent trace-inventory contracts.

Therefore:

```text
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
```

The remediation may keep 56 checkpoints and 34 top-level attack classes only if every required behavior is genuinely represented. Correct coverage is more important than cosmetic preservation of counts.

---

# 6. Candidate report accuracy

The implementation agent reported full completion, 56 connected checkpoints, a 34-class gate, suite counts, and candidate HEAD/bundle metadata.

The bundle SHA matches the reported SHA.

The reported canonical inventory, however, does **not** match the bundled `catalog.py` or frozen design, and multiple “connected” checkpoint labels overstate what the tests actually execute.

The remediation worker must therefore treat the bundle source/spec/plan as authoritative rather than copying the final implementation report.

---

# 7. Remediation acceptance requirements

A V2 candidate is eligible for re-audit only when all of the following are true:

```text
B1_PROJECT_LIFE_PLAN_RUNTIME_AUTHORIZATION=PASS
B1_RAW_MAPPING_NOT_AUTHORITY=PASS
B1_FORGED_PERMISSION_EVIDENCE_REJECTED=PASS
B1_CONTEXT_PURPOSE_TARGET_MISMATCH_REJECTED=PASS

B2_CALLER_COMMIT_REFERENCE_NOT_AUTHORITY=PASS
B2_FAILED_VALIDATION_CANNOT_COMMIT=PASS
B2_DENIED_GATE_CANNOT_COMMIT=PASS
B2_MISSING_APPROVAL_CANNOT_COMMIT=PASS
B2_COMMIT_OUTCOME_RUNTIME_OWNED=PASS

M1_PROJECT_BOOTSTRAP_EXTENDS_10_29=PASS
M1_GENERAL_FALLBACK_PRESERVED=PASS

M2_TEMP_REPOSITORY_SELF_DEVELOPMENT=PASS
M2_SHARED_REPOSITORY_ANALYSIS=PASS
M2_SHARED_PLANNING=PASS
M2_CONTROLLED_MUTATION=PASS
M2_TRANSACTION_ROLLBACK=PASS
M2_PHASE7_VALIDATION_REAL=PASS
M2_PREPARE_COMMIT_HEAD_UNCHANGED=PASS

M3_TRACE_INVENTORY_PREASSEMBLY=PASS
M3_TRACE_VALIDATION_REAL=PASS
M3_TRACE_TAMPER_REJECTED=PASS

M4_REFERENCE_INVENTORY_MATCHES_CATALOG=PASS
M4_AGENT_REPORT_GENERATED_FROM_CATALOG=PASS

M5_FAKE_WORKFLOW_ACTIVATION_REJECTED=PASS
M5_SUFFIX_COLLISION_RESOURCE_REJECTED=PASS
M5_REPOSITORY_SIGNAL_GROUNDED=PASS

AT_DP_030=PASS
AT_DP_030_CHECKPOINTS=56
PROJECT_CLOSURE_ADVERSARIAL_GATE=PASS
PROJECT_CLOSURE_ATTACK_CLASSES=<fresh exact count>
PROJECT_TESTS=<fresh exact count>
DOMAIN_TESTS=<fresh exact count>
GLOBAL_TESTS=<fresh exact count>
RUFF=PASS
FORMAT=PASS
COMPILEALL=PASS
DP_030=REQUIRES_PHASE_INSPECTION
INDEPENDENT_REAUDIT_V2=PENDING
PUSH=NO
MERGE=NO
```

If closing the defects requires changing shared infrastructure, the remediation worker must first prove the generic shared defect with RED coverage and keep the shared change minimal and separately committed.

---

# 8. Final independent verdict

```text
PHASE10_30_INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=2
MAJORS=5
MINORS=0

B1=OPEN  Project→Life Plan authorization bypass
B2=OPEN  caller-controlled committed-state forgery

M1=OPEN  Project bootstrap does not extend frozen 10.29 chain
M2=OPEN  self-development E2E does not execute shared runtime
M3=OPEN  independent trace inventory/validation not demonstrated
M4=OPEN  canonical reference documentation materially diverges from catalog
M5=OPEN  software capability activation accepts ungrounded caller primitives

DP_030=REQUIRES_PHASE_INSPECTION
INDEPENDENT_REAUDIT_V2=REQUIRED
PUSH=NO
MERGE=NO
NEXT=PHASE_10_30_AUDIT_V1_REMEDIATION
```
