# CMM OS — Phase 10.42 — Independent Re-Audit V5

**Phase:** 10.42 — Integration with Planner and Workflow Engine
**Audit type:** Independent Re-Audit V5
**Auditor:** ChatGPT / CMM OS project
**Date:** 2026-09-04
**Result:** **FAIL**

---

## 1. Final verdict

```text
PHASE10_42_INDEPENDENT_REAUDIT_V5=FAIL

AUDITED_HEAD=5735e6808b21934fcca045b1010dfde4012b1cf5
AUDIT_V5_BUNDLE_SHA256=70f85f01e6d1267defb15c37a0581b0ac71ddbcfcec7288dbe9bb133495f9b2c

V1_BLOCKER_01_INVALID_UNAVAILABLE_PLAN=FIXED
V1_MAJOR_01_EXACT_OPERATION_SEMANTICS=FIXED
V1_MAJOR_02_CONNECTED_ACCEPTANCE=FIXED

V2_MAJOR_03_REAL_DOMAIN_OPERATION_SELECTION=FIXED
V2_MAJOR_04_MISSING_REQUIRED_DEPENDENCY=FIXED

V3_MAJOR_05_EFFECTIVE_OPERATION_CANDIDATES=FIXED

V4_MAJOR_06_OPERATION_PERMISSION_COMPATIBILITY=FIXED

BLOCKERS=0
MAJORS=1
MINORS=0

V5_MAJOR_07_WORKFLOW_PERMISSION_COMPATIBILITY=OPEN

DP-042=NOT_VERIFIED
AT-DP-042=PASS
CLOSURE_ELIGIBLE=NO

NEXT=PHASE10_42_REMEDIATION_V5_TO_V6
```

Phase 10.42 is **not eligible for closure** after V5.

The V4 remediation correctly removes permission-incompatible Domain operations from the planner candidate set before planner invocation.

The remaining defect is the workflow analogue: workflow availability is filtered against the Domain-side effective permission provider before request preparation, but an incoming canonical `AgentPlanningRequest.permissions` restriction may narrow the final prepared permission set further. Explicit workflow selection is still performed against the broader pre-preparation workflow view, so a workflow can be selected and a canonical VALID plan returned even when its required permissions are absent from `prepared.permissions`.

This remains fail-safe at the later Domain workflow execution boundary, which re-evaluates current permission authority, so it is not a blocker. It is nevertheless closure-blocking because the frozen Phase 10.42 design requires workflows to be permission-compatible with the effective planning authority and requires the most-restrictive combination of Domain and canonical/runtime permission constraints.

---

# 2. Exact V5 bundle authentication

Audited artifact:

```text
phase-10.42-audit-v5-5735e6808b21934fcca045b1010dfde4012b1cf5.tar.gz
```

Declared SHA-256:

```text
70f85f01e6d1267defb15c37a0581b0ac71ddbcfcec7288dbe9bb133495f9b2c
```

Independently recalculated SHA-256:

```text
70f85f01e6d1267defb15c37a0581b0ac71ddbcfcec7288dbe9bb133495f9b2c
```

The embedded PAX global header contains:

```text
comment=5735e6808b21934fcca045b1010dfde4012b1cf5
```

Archive inspection:

```text
MEMBERS=2043
TOP_LEVEL_PREFIX=CMM-OS-5735e6808b21
UNSAFE_PATHS=0
SPECIAL_MEMBERS=0
```

Result:

```text
AUDIT_V5_BUNDLE_SHA256=VERIFIED
AUDITED_HEAD=VERIFIED_EXACT
ARCHIVE_PATH_SAFETY=PASS
ARCHIVE_HYGIENE=PASS
```

---

# 3. Frozen artifact integrity

## Approved design spec

Expected and observed SHA-256:

```text
8c777d4e4c71595eedd02445f6d66a172db31f70a7a3b95991a24a0129d023e1
```

```text
SPEC_HASH=PASS
```

## Approved implementation plan

Expected and observed SHA-256:

```text
5b5cbdb4ed9aecd311918f777b641f311f12b8dd51ca68ea493675198ed85d8a
```

```text
PLAN_HASH=PASS
```

## Historical audit reports

Observed exact hashes:

```text
V1:
79debf52218a2bb0e2fb206bb3b72bf72dca8b5c5cfbe3c6f3c8dee4040515f2

V2:
56d6ee71cfb1606538f154968ea85b4a8cc63c1b8ca1f579049d516c02553090

V3:
62bb248d0402da7214e47f823f20fc8aecd9e141781cd6eb4a17eebeb1985414

V4:
230c85b15e42b92f71a09d58f9c7686704852e6b6c5c61cbdc419ad6fb79943d
```

Result:

```text
HISTORICAL_AUDIT_ARTIFACTS_PRESERVED=YES
```

---

# 4. V4 → V5 production scope

The substantive V5 production change remains narrow and Domain-side.

Primary changed production file:

```text
cmm/domains/planner_workflow_integration.py
```

The V5 implementation adds:

```text
_permission_compatible_operation_candidates(...)
```

and applies it to the already-effective candidate set before storing:

```text
metadata["operation_candidates"]
```

No Phase 9 planning contract was redesigned.

No new permission owner was introduced.

No new planner, runtime, registry, workflow engine, store, event bus, or state machine was introduced.

---

# 5. V4 MAJOR-06 — VERIFIED FIXED

Canonical V4 finding:

```text
V4_MAJOR_06_OPERATION_PERMISSION_COMPATIBILITY=OPEN
```

V5 now filters each existing candidate by exact canonical:

```text
DomainOperationDefinition.required_permissions
```

against the same effective permission set written into:

```text
prepared.permissions
```

A candidate with a known canonical definition survives only when:

```text
set(definition.required_permissions)
<=
set(prepared.permissions)
```

Unknown definitions preserve prior registration/availability semantics rather than receiving invented permissions.

## 5.1 Dedicated V5 tests

Fresh exact-archive execution covers:

```text
test_v5_real_project_modify_code_without_permission_blocked
test_v5_real_project_modify_code_with_permission_plans
test_v5_mixed_permission_candidates_filtered
test_v5_permission_compatible_candidates_satisfy_all_authority
test_v5_zero_permission_compatible_candidates_fails_before_planner
test_v5_unknown_operation_definition_preserves_registration_authority
```

Together with the V5 acceptance file:

```text
21 passed
```

Result:

```text
V4_MAJOR_06_OPERATION_PERMISSION_COMPATIBILITY=FIXED
PERMISSION_INCOMPATIBLE_OPERATION_CANDIDATE=0
REAL_PROJECT_MODIFY_CODE_WITHOUT_PERMISSION=BLOCKED
REAL_PROJECT_MODIFY_CODE_WITH_PERMISSION=PASS
MIXED_PERMISSION_CANDIDATES_FILTERED=PASS
ZERO_PERMISSION_COMPATIBLE_CANDIDATES_FAILS_BEFORE_PLANNER=PASS
```

---

# 6. Independent focused verification

The audit environment lacks repository dependency:

```text
libcst
```

so ordinary import of the package fails through unrelated Python execution imports.

As in V2–V4, the auditor loaded `cmm.agent_runtime` and `cmm.execution` as namespace packages solely to avoid executing heavyweight package `__init__` files. No audited repository source was changed.

## 6.1 Focused Phase 10.42 suite

Fresh exact-archive execution:

```text
tests/domains/test_domain_planner_workflow_integration_contracts.py
tests/domains/test_domain_planner_workflow_integration.py
tests/domains/test_domain_planner_workflow_boundaries.py
tests/domains/test_domain_planner_workflow_dp042_acceptance.py
tests/agent_runtime/test_workflow_planner_adapter.py
```

Result:

```text
180 passed
```

```text
FOCUSED_PHASE10_42=PASS
FOCUSED_PHASE10_42_COUNT=180
```

## 6.2 AT-DP-042

Fresh exact-archive execution:

```text
15 passed
```

```text
AT-DP-042=PASS
AT_DP_042_INDEPENDENT_COUNT=15
```

---

# 7. Static / architecture gates

Fresh AST scan:

```text
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
WORKFLOWS_TO_DOMAIN_IMPORTS=0
```

Fresh boundary / fragmentation execution:

```text
92 passed
```

Fresh compile:

```text
COMPILEALL=PASS
```

Result:

```text
NO_PARALLEL_PLANNER=YES
NO_PARALLEL_WORKFLOW_ENGINE=YES
NO_PARALLEL_PLAN_STORE=YES
NO_PARALLEL_WORKFLOW_STORE=YES
NO_PARALLEL_PERMISSION_SYSTEM=YES
NO_PARALLEL_APPROVAL_SYSTEM=YES
NO_PARALLEL_VALIDATION_SYSTEM=YES
NO_PARALLEL_RUNTIME=YES
NO_PARALLEL_EVENT_BUS=YES
NO_PARALLEL_STATE_MACHINE=YES
```

---

# 8. V5 MAJOR-07 — workflow selection ignores final prepared permission authority

## 8.1 Severity

```text
MAJOR
```

Not a blocker because actual workflow execution remains delegated to:

```text
DomainWorkflowExecutor
→ WorkflowEngine
```

with current permission/dependency checks at the execution boundary.

The planning defect does not itself grant workflow execution authority.

## 8.2 Frozen design requirement

The approved Phase 10.42 spec states:

> A workflow may be planned only when its effective permissions permit planning/use.

It also states:

> The effective planning capability set must be no broader than all applicable constraints.

And the general authority rule is:

```text
Domain specialization may restrict authority
but may never expand canonical global/runtime authority.
```

The canonical incoming planning request is explicitly part of this composition.

## 8.3 Root cause

Workflow capability projection occurs in:

```text
_build_capability_view(...)
```

and filters `DomainWorkflowDefinition.required_permissions` against:

```text
effective_permission_ids
```

provided by the Domain permission authority.

That creates:

```text
capability_view.available_workflow_ids
```

Later `_prepare_planning_request(...)` computes the final canonical permission set:

```text
prepared.permissions
=
incoming.permissions
∩
capability_view.required_permission_ids
```

However `_select_workflows(...)` is called using only:

```text
request
capability_view
```

before / independently of the final prepared permission restriction.

It validates explicit requested workflow IDs against:

```text
view.available_workflow_ids
```

but does not re-check each workflow's required permissions against:

```text
prepared.permissions
```

Therefore the Domain-side view can make a workflow available using Domain permission authority while the canonical incoming planning request subsequently removes that permission.

The workflow remains selected anyway.

## 8.4 Independent real-production reproduction

The reproduction uses the actual production Project Domain workflow definitions:

```text
build_project_workflow_definitions()
```

The real workflow:

```text
project.project_setup
```

declares:

```text
required_permissions=(
  "domain-permission:project:1.0.0",
)
```

The Domain permission provider grants:

```text
domain-permission:project:1.0.0
```

so the workflow legitimately appears in the pre-preparation capability view.

The incoming canonical `AgentPlanningRequest.permissions` is intentionally narrower:

```text
()
```

The final prepared request therefore contains:

```text
PREPARED_PERMISSIONS=[]
```

Observed exact V5 result:

```text
WORKFLOW=project.project_setup

WORKFLOW_REQUIRED_PERMISSIONS=(
  'domain-permission:project:1.0.0',
)

VIEW_PERMISSIONS=(
  'domain-permission:project:1.0.0',
)

WORKFLOW_IN_VIEW=True

PREPARED_PERMISSIONS=[]

SELECTED=(
  'project.project_setup',
)

BLOCKED=False
REASON_CODES=()

PLAN_VALID=True
```

This proves:

```text
workflow required permission absent from final prepared permissions
→ workflow still selected
→ canonical plan remains VALID
→ integration result remains unblocked
```

## 8.5 Why this is closure-blocking

Phase 10.42's workflow planning contract is stronger than execution-only safety.

The spec requires workflows to be permission-compatible **at planning time** under the most-restrictive effective authority.

Returning an unblocked canonical plan with a selected workflow whose exact required permission is absent from the final canonical request violates that requirement.

Execution-time revalidation is required in addition; it does not replace planning-time filtering.

## 8.6 Required remediation

Keep remediation narrow and Domain-side.

Do not modify Phase 9.

Do not create a new workflow permission owner.

Reuse:

```text
InMemoryDomainWorkflowRegistry
DomainWorkflowDefinition.required_permissions
prepared.permissions
existing requested_workflow_ids selection
```

The selected workflow set must be validated against the final prepared effective permission set.

Preferred invariant:

For every selected workflow:

```text
set(workflow.required_permissions)
<=
set(prepared.permissions)
```

A workflow failing this must not be returned as selected.

If an explicitly requested workflow becomes permission-incompatible after final request authority composition:

```text
blocked=True
planner not invoked
```

Use an existing deterministic Phase 10.42 workflow/permission reason where semantically appropriate.

Do not grant missing permissions.

Do not broaden incoming permissions.

## 8.7 Required RED/GREEN coverage

### RED A — real Project workflow, Domain permission present, incoming permission absent

```text
Domain effective permissions:
  domain-permission:project:1.0.0

incoming planning permissions:
  ()

requested workflow:
  project.project_setup

→ workflow not selected
→ planner not invoked
→ blocked=True
```

### RED B — same workflow with permission present in both authorities

```text
Domain effective permissions:
  domain-permission:project:1.0.0

incoming planning permissions:
  domain-permission:project:1.0.0

→ workflow remains selected
→ planning succeeds
```

### RED C — mixed workflow permissions

Use at least two real or canonical workflow definitions such that one remains compatible and one does not.

Expected:

```text
permission-compatible explicitly requested workflow remains usable
permission-incompatible explicitly requested workflow causes deterministic fail-closed behavior
```

If current semantics define the explicit requested workflow set atomically, failing the whole explicit request is acceptable; do not silently drop a requested workflow without an explicit existing contract permitting partial selection.

### RED D — no regression of V5 operation permission filtering

Preserve:

```text
project.modify_code without file.modify
→ excluded before planner

project.modify_code with file.modify
→ plannable
```

## 8.8 Required remediation marker

```text
V5_MAJOR_07_WORKFLOW_PERMISSION_COMPATIBILITY=FIXED
WORKFLOW_REQUIRED_PERMISSIONS_SUBSET_OF_PREPARED=PASS
REAL_PROJECT_WORKFLOW_WITHOUT_INCOMING_PERMISSION=BLOCKED
REAL_PROJECT_WORKFLOW_WITH_PERMISSION=PASS
PERMISSION_INCOMPATIBLE_SELECTED_WORKFLOW=0
```

---

# 9. Prior findings remain fixed

Independent V5 evidence supports:

```text
V1_BLOCKER_01_INVALID_UNAVAILABLE_PLAN=FIXED
V1_MAJOR_01_EXACT_OPERATION_SEMANTICS=FIXED
V1_MAJOR_02_CONNECTED_ACCEPTANCE=FIXED

V2_MAJOR_03_REAL_DOMAIN_OPERATION_SELECTION=FIXED
V2_MAJOR_04_MISSING_REQUIRED_DEPENDENCY=FIXED

V3_MAJOR_05_EFFECTIVE_OPERATION_CANDIDATES=FIXED

V4_MAJOR_06_OPERATION_PERMISSION_COMPATIBILITY=FIXED
```

No prior finding is reopened by MAJOR-07.

---

# 10. Documentation status

V5 documentation correctly remains:

```text
PHASE10_42=IMPLEMENTED_PENDING_AUDIT
DP_042=IMPLEMENTED_PENDING_AUDIT
AT_DP_042=PASS
```

No premature closure was found.

Result:

```text
DOCUMENTATION_STATUS_DISCIPLINE=PASS
```

---

# 11. DP-042 assessment

V5 now proves:

```text
registered real Domain operation selection = PASS
operation semantics projection = PASS
operation allow/prohibit composition = PASS
operation required-permission filtering = PASS
missing required dependencies fail closed = PASS
valid dependencies materialize canonically = PASS
connected operation/workflow/replan acceptance = PASS
reverse imports = 0
parallel owners absent
```

But selected workflow permission compatibility against the final canonical planning authority still fails.

Therefore:

```text
DP-042=NOT_VERIFIED
```

---

# 12. AT-DP-042 assessment

The canonical connected acceptance passes independently:

```text
15 passed
```

Therefore:

```text
AT-DP-042=PASS
```

MAJOR-07 is a missing adversarial workflow permission-composition case, not a failure of the existing connected acceptance chain.

---

# 13. Severity summary

```text
BLOCKERS=0

MAJORS=1
  MAJOR-07:
    explicitly selected workflows are checked against
    capability_view permissions, but not against the final
    prepared AgentPlanningRequest.permissions.

MINORS=0
```

---

# 14. Closure decision

Required closure floor:

```text
BLOCKERS=0
MAJORS=0
DP-042=VERIFIED_EXISTING
AT-DP-042=PASS
CLOSURE_ELIGIBLE=YES
```

Observed V5:

```text
BLOCKERS=0
MAJORS=1
DP-042=NOT_VERIFIED
AT-DP-042=PASS
CLOSURE_ELIGIBLE=NO
```

Therefore:

```text
PHASE10_42_INDEPENDENT_REAUDIT_V5=FAIL
CLOSURE_ELIGIBLE=NO
```

Do not create the Phase 10.42 docs-only closure commit.

Do not begin Phase 10.43.

---

# 15. Required next cycle

```text
COMMIT THIS V5 RE-AUDIT REPORT
→ REMEDIATION V5 → V6
→ RED workflow final-permission compatibility
→ minimal Domain-side selection fix
→ preserve V1–V4 fixes
→ focused tests
→ AT-DP-042
→ AT-DP-041
→ Domain suite
→ Agent Runtime suite
→ global suite
→ Ruff / format
→ compileall
→ git diff --check
→ architecture gates
→ fully committed clean implementation
→ NEW exact-HEAD V6 git-archive bundle
→ NEW SHA-256
→ Independent Re-Audit V6
```

---

# 16. Final machine-readable verdict

```text
PHASE10_42_INDEPENDENT_REAUDIT_V5=FAIL

AUDITED_HEAD=5735e6808b21934fcca045b1010dfde4012b1cf5
AUDIT_V5_BUNDLE_SHA256=70f85f01e6d1267defb15c37a0581b0ac71ddbcfcec7288dbe9bb133495f9b2c

ARCHIVE_PATH_SAFETY=PASS
ARCHIVE_HYGIENE=PASS
SPEC_HASH=PASS
PLAN_HASH=PASS
HISTORICAL_AUDIT_ARTIFACTS_PRESERVED=YES

FOCUSED_PHASE10_42=PASS
FOCUSED_PHASE10_42_COUNT=180
AT-DP-042=PASS
AT_DP_042_INDEPENDENT_COUNT=15
BOUNDARY_FRAGMENTATION_TESTS=PASS
BOUNDARY_FRAGMENTATION_COUNT=92
COMPILEALL=PASS

AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
WORKFLOWS_TO_DOMAIN_IMPORTS=0

NO_PARALLEL_PLANNER=YES
NO_PARALLEL_WORKFLOW_ENGINE=YES
NO_PARALLEL_PLAN_STORE=YES
NO_PARALLEL_WORKFLOW_STORE=YES
NO_PARALLEL_PERMISSION_SYSTEM=YES
NO_PARALLEL_APPROVAL_SYSTEM=YES
NO_PARALLEL_VALIDATION_SYSTEM=YES
NO_PARALLEL_RUNTIME=YES
NO_PARALLEL_EVENT_BUS=YES
NO_PARALLEL_STATE_MACHINE=YES

V1_BLOCKER_01_INVALID_UNAVAILABLE_PLAN=FIXED
V1_MAJOR_01_EXACT_OPERATION_SEMANTICS=FIXED
V1_MAJOR_02_CONNECTED_ACCEPTANCE=FIXED

V2_MAJOR_03_REAL_DOMAIN_OPERATION_SELECTION=FIXED
V2_MAJOR_04_MISSING_REQUIRED_DEPENDENCY=FIXED

V3_MAJOR_05_EFFECTIVE_OPERATION_CANDIDATES=FIXED

V4_MAJOR_06_OPERATION_PERMISSION_COMPATIBILITY=FIXED

V5_MAJOR_07_WORKFLOW_PERMISSION_COMPATIBILITY=OPEN

BLOCKERS=0
MAJORS=1
MINORS=0

DP-042=NOT_VERIFIED
AT-DP-042=PASS
CLOSURE_ELIGIBLE=NO

NEXT=PHASE10_42_REMEDIATION_V5_TO_V6
```
