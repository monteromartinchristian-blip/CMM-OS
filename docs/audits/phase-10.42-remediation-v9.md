# Phase 10.42 — V8 to V9 remediation evidence

Status: **IMPLEMENTED_PENDING_AUDIT**. DP-042 remains IMPLEMENTED_PENDING_AUDIT;
AT-DP-042 passes. Next authority: Independent Re-Audit V9. This is implementation
and local verification evidence, not an independent audit or phase closure.

## Scope and immutable baseline

Only V8 MAJOR-12 (workflow operation-node semantics) and MAJOR-13 (subworkflow
permission and approval semantics) are remediated. Branch:
`feature/phase-10-domain-intelligence`.

- Starting HEAD / V8 report commit: `35065d2380f6fd75975843efe17b42e1ad282103`.
- V8 audited implementation: `e80214fbd5228f163889c8233e0a9cdaeee707a0`.
- Verified code and tests commit: `d300678b4b27e16ed1db4582c14180d499a051a9`.
- Spec commit: `78bb4f994f23420039144609754f7ff94ab1b845`;
  SHA-256: `8c777d4e4c71595eedd02445f6d66a172db31f70a7a3b95991a24a0129d023e1`.
- Plan commit: `35396687b7b5ac690af5ce515d71f65ff5ab4c3a`;
  SHA-256: `5b5cbdb4ed9aecd311918f777b641f311f12b8dd51ca68ea493675198ed85d8a`.
- V8 report SHA-256:
  `62aa77245d2ef9685ba7396a1f9ba83ddefb127b6cadf24a40108de3f1a276fb`.

All three frozen files retain these hashes. Historical audit artifacts are
unchanged. The final handoff records the subsequent documentation commit as the
exact archive HEAD; no self-referential archive hash is embedded in its contents.

## Before and after

| Canonical branch | V8 defect | V9 behavior and owner |
| --- | --- | --- |
| Operation exact version | A missing requested version could reach the planner | Exact shared `workflow_node_reference` lookup; a required unavailable node blocks before planning |
| Optional operation | Canonically skippable unavailable operation blocked selection | `resolve_domain_workflow` respects `node.required`; graph skips unavailable optional nodes and their obligations |
| Internal operation approval | Planner choices could omit the internal operation and lose its approval | Selected graph reuses `_operation_semantics` and canonical node permission decisions; existing plan approval nodes remain pending |
| Internal operation validation | Validation depended on planner operation selection | Exact internal operation validation IDs join the existing required-validations contract |
| Optional eligible subworkflow | Its obligations were dropped | Eligible optional children contribute approvals and validations recursively; missing/ineligible/denied optional children contribute neither a block nor obligations |
| Cross-domain subworkflow | Required child policy deny or approval could be missed | Shared `evaluate_subworkflow_handoff` invokes the existing `DomainPermissionResolver.resolve_cross_domain`; required deny blocks and approval requirements are projected |

Final incoming and Domain operation allow/prohibit authority applies to the exact
workflow reference independently of generic planner default-version filtering.
With a permission gate, the executor's copied exact definition snapshots are the
canonical authority: absent or stale child/operation snapshots are not repaired
from a separate planner provider. Registered parent/child Domain ownership,
actor, explicit session (or agent-run fallback), requested child and sensitivity
are retained in cross-domain policy requests. Policies are evaluated afresh.

Root workflow permission/resource requirements are factored into
`evaluate_domain_workflow_requirements`, shared by the canonical evaluator and
planning traversal. The existing V1 operation projection is factored once into
`_operation_semantics`; the existing V8 graph eligibility traversal is extended.
There is no parallel permission resolver or operation semantics mapper.

Planning reads the executor/gate policy context without issuing gate evidence,
looking up or consuming grants, executing workflows, or changing executor runtime
state. Execution still uses the existing permission gates and shared engine.
Obligations use existing action/gate IDs and validation IDs; approval remains a
pending requirement, never an authorization grant.

## RED to GREEN evidence

Seven regressions failed against V8 before production edits (7 failed, 95
deselected). The final strengthened fixtures were also checked against the actual
starting-HEAD modules without rolling back or mutating the worktree:

```text
A_EXACT_VERSION: canonical=deny; blocked=False; planner_calls=1; status=valid
B_OPTIONAL_UNAVAILABLE: canonical=allow; blocked=True; planner_calls=0
C_INTERNAL_APPROVAL: canonical=approval_required; blocked=False; planner_calls=1
D_INTERNAL_VALIDATION: canonical=allow; blocked=False; planner_calls=1
E_OPTIONAL_CHILD_APPROVAL: canonical=allow; blocked=False; planner_calls=1
G_CROSS_DOMAIN_DENY: canonical=deny; blocked=False; planner_calls=1
H_CROSS_DOMAIN_APPROVAL: canonical=approval_required; blocked=False; planner_calls=1
V8_RED_REPRODUCTIONS=7/7
```

C/D deliberately use eight unrelated safe operations preceding the internal
operation, asserting the real TaskPlanner does not select the internal operation.
The V8 plans omit the internal approval/validation obligations. E demonstrates a
child workflow-level gate lost from planning (the canonical node permission
adapter itself reports allow for that workflow-level gate); additional eligible
child REQUEST_APPROVAL tests directly assert canonical APPROVAL_REQUIRED.
F (optional missing/ineligible) is a preservation case and stays nonblocking.

The connected fixture uses real DefaultDomainResolver, DefaultDomainComposer,
registries, canonical permission policies/resolver/gate/executor,
AgentPlanningService, TaskPlanner and validator. Adversarial AT-DP-042 cases assert
pending approval and validation traceability without depending on internal
operation selection. The matrix covers required/optional nodes, exact versions,
disabled/missing/denied/approval-required definitions, resources and permissions,
nested children, cycles, stale snapshots, and final authority. Optional denied
operation skipping also has an execution test against the existing engine.

All 18 WorkflowNodeType values have planning/canonical branch-parity coverage;
an exhaustive test covers all four shared WorkflowNodePermissionBranch values.
Canonical cross-domain invocation requests require approval by default, so a
policy-permitted crossing yields APPROVAL_REQUIRED. An approval-free cross-domain
ALLOW case cannot be manufactured without changing that canonical contract.

## Production inventory

The executable inventory traverses 95 workflows from 12 production Domain packs
plus the four compatibility workflows in `initial_domain_workflows()` (all 13
construction sources). The bootstrap workflows add no operation or subworkflow
references. Every operation reference resolves at its declared exact version;
internal approval/validation obligations are represented.

```text
PRODUCTION_WORKFLOW_OPERATION_NODES=200
PRODUCTION_WORKFLOW_OPERATION_NODES_WITH_VERSION=200
PRODUCTION_WORKFLOW_OPERATION_NODES_WITHOUT_VERSION=0
PRODUCTION_WORKFLOW_OPERATION_VERSION_REFERENCES=VERIFIED
UNREPRESENTED_WORKFLOW_INTERNAL_OPERATION_OBLIGATIONS=0
PRODUCTION_SUBWORKFLOW_NODE_COUNT=0
PRODUCTION_CROSS_DOMAIN_SUBWORKFLOW_NODE_COUNT=0
PRODUCTION_OPTIONAL_SUBWORKFLOW_NODE_COUNT=0
```

Zero production subworkflow references is an observed inventory result; synthetic
connected tests supply required/optional and cross-domain regression evidence.

## Final verification

All results below were obtained on the final Python source, including the
bootstrap inventory assertions. SHA-256 checks confirmed that all seven changed
Python files were identical when committed. Later changes are documentation only.
Counts overlap across suites and must not be summed.

| Gate | Observed result |
| --- | --- |
| FOCUSED_TESTS | 293 passed in 2.78s (exit 0) |
| AT_DP_042 | 30 passed in 1.52s (exit 0) |
| AT_DP_041 | 128 passed in 2.95s (exit 0) |
| WORKFLOW_OPERATION_NODE_REGRESSIONS | 452 passed in 2.42s (exit 0) |
| SUBWORKFLOW_PERMISSION_REGRESSIONS | 379 passed in 2.25s (exit 0) |
| APPROVAL_VALIDATION_REGRESSIONS | 559 passed in 2.20s (exit 0) |
| PLANNER_WORKFLOW_PERMISSION_REGRESSIONS | 426 passed in 2.20s (exit 0) |
| DOMAIN_SUITE | 9436 passed in 114.79s (0:01:54) (exit 0) |
| AGENT_RUNTIME_SUITE | 3432 passed in 5.72s (exit 0) |
| WORKFLOWS_SUITE | 46 passed in 0.04s (exit 0) |
| BOUNDARY_FRAGMENTATION_TESTS | 92 passed in 1.29s (exit 0) |
| PRODUCTION_INVENTORY | 1 passed in 0.90s (exit 0) |
| GLOBAL_SUITE | 15033 passed in 134.42s (exit 0) |
| RUFF_CHANGED_FILES | PASS, all seven changed Python files |
| FORMAT_CHANGED_FILES | PASS, all seven changed Python files |
| RUFF_GLOBAL | EXISTING_DEBT: exit 1; 825 diagnostics, baseline 825; zero new diagnostics and zero changed-file overlap |
| FORMAT_GLOBAL | EXISTING_DEBT: exit 1; 308 files, baseline 308; zero new files and zero changed-file overlap |
| COMPILEALL | PASS: `python3 -m compileall -q cmm tests` |
| DIFF_CHECK | PASS: `git diff --check` |
| AGENT_RUNTIME_TO_DOMAIN_IMPORTS | 0, AST scan |
| WORKFLOWS_TO_DOMAIN_IMPORTS | 0, AST scan |

Global lint/format debt was compared using the same Ruff against a temporary
`git archive` of starting HEAD. The global controls are not clean; the unchanged,
out-of-scope debt is reported under the task's permitted baseline qualification.
Focused checks are clean. The full suite command was
`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q`.

Owner scan and local diff review retain the existing planner, shared workflow
engine, Domain/workflow registries, DomainPermissionResolver, permission gate,
plan/workflow stores, approval and validation owners, runtime, event bus and state
machine. No parallel owner is introduced. Independent review was attempted but
the reviewer was unavailable due to a usage limit; these results are local
implementation verification only. The required independent V9 audit remains due.

## Preserved earlier findings

The focused suite retains the original 95 integration tests. V1 invalid/unavailable
plan handling, exact operation semantics and connected acceptance; V2 real Domain
operation selection and required dependencies; V3 effective candidates; V4 operation
permission compatibility; V5 workflow permission compatibility; V6 final workflow
availability and unselected approval isolation; and V7 node approval projection and
subworkflow eligibility remain covered and passing. Required/nested child
eligibility, cycle closure, exact child versions, final authority propagation and
selected-only approval projection are retained. Both unselected workflow and
unselected node approval-gate leakage remain zero.

## Reproducible focused scopes

Run `.venv/bin/python -m pytest -q` with the following arguments. Broader production
Domain discovery is covered by the complete Domain suite, and all tests by the
complete global suite.

### FOCUSED_TESTS

```text
tests/domains/test_domain_planner_workflow_integration.py
tests/domains/test_domain_planner_workflow_dp042_acceptance.py
tests/domains/test_domain_planner_workflow_integration_contracts.py
tests/domains/test_domain_planner_workflow_boundaries.py
tests/agent_runtime/test_workflow_planner_adapter.py
```

### AT_DP_042

```text
tests/domains/test_domain_planner_workflow_dp042_acceptance.py
```

### AT_DP_041

```text
tests/domains/test_domain_agent_runtime_integration_contracts.py
tests/domains/test_domain_agent_runtime_integration.py
tests/domains/test_domain_agent_runtime_integration_boundaries.py
tests/domains/test_domain_agent_runtime_dp041_acceptance.py
```

### WORKFLOW_OPERATION_NODE_REGRESSIONS

```text
tests/domains/test_domain_planner_workflow_integration.py
tests/domains/test_domain_planner_workflow_dp042_acceptance.py
tests/domains/test_domain_workflows.py
tests/domains/test_domain_workflow_cross_domain.py
tests/domains/test_domain_workflow_pending.py
tests/domains/test_domain_workflow_result_preservation.py
tests/domains/test_phase_10_15_workflow_gate_integration.py
tests/workflows
tests/domains/test_domain_permission_adapters.py
tests/domains/test_domain_permission_gate.py
tests/domains/test_domain_permission_resolution.py
tests/domains/test_domain_operation_registry.py
tests/domains/test_domain_operation_availability.py
tests/domains/test_domain_operation_execution.py
tests/domains/test_domain_operation_approval.py
tests/agent_runtime/test_operation_execution_adapter.py
tests/agent_runtime/test_operation_execution_output.py
```

### SUBWORKFLOW_PERMISSION_REGRESSIONS

```text
tests/domains/test_domain_planner_workflow_integration.py
tests/domains/test_domain_planner_workflow_dp042_acceptance.py
tests/domains/test_domain_workflows.py
tests/domains/test_domain_workflow_cross_domain.py
tests/domains/test_domain_workflow_pending.py
tests/domains/test_domain_workflow_result_preservation.py
tests/domains/test_phase_10_15_workflow_gate_integration.py
tests/workflows
tests/domains/test_domain_permission_adapters.py
tests/domains/test_domain_permission_gate.py
tests/domains/test_domain_permission_resolution.py
tests/domains/test_registry_snapshot_common_workflow.py
tests/domains/test_registry_snapshot_domain_workflow.py
```

### APPROVAL_VALIDATION_REGRESSIONS

```text
tests/domains/test_domain_planner_workflow_integration.py
tests/domains/test_domain_planner_workflow_dp042_acceptance.py
tests/domains/test_domain_permission_adapters.py
tests/domains/test_domain_permission_gate.py
tests/domains/test_domain_permission_resolution.py
tests/agent_runtime/test_workflow_planner_adapter.py
tests/agent_runtime/test_human_approval.py
tests/agent_runtime/test_validation_integration.py
tests/domains/test_domain_operation_approval.py
tests/domains/test_domain_validation_contracts.py
tests/domains/test_domain_validation_service.py
tests/domains/test_domain_validation_gate.py
tests/domains/test_domain_validation_pipeline.py
```

### PLANNER_WORKFLOW_PERMISSION_REGRESSIONS

```text
tests/domains/test_domain_planner_workflow_integration.py
tests/domains/test_domain_planner_workflow_dp042_acceptance.py
tests/domains/test_domain_workflows.py
tests/domains/test_domain_workflow_cross_domain.py
tests/domains/test_domain_workflow_pending.py
tests/domains/test_domain_workflow_result_preservation.py
tests/domains/test_phase_10_15_workflow_gate_integration.py
tests/workflows
tests/domains/test_domain_permission_adapters.py
tests/domains/test_domain_permission_gate.py
tests/domains/test_domain_permission_resolution.py
tests/agent_runtime/test_workflow_planner_adapter.py
tests/domains/test_project_domain_workflows.py
tests/domains/test_health_domain_workflows.py
tests/domains/test_relationships_domain_workflows.py
```

### DOMAIN_SUITE

```text
tests/domains
```

### AGENT_RUNTIME_SUITE

```text
tests/agent_runtime
```

### WORKFLOWS_SUITE

```text
tests/workflows
```

### BOUNDARY_FRAGMENTATION_TESTS

```text
tests/domains/test_domain_planner_workflow_boundaries.py
tests/domains/test_domain_validation_fragmentation.py
```

### PRODUCTION_INVENTORY

```text
tests/domains/test_domain_planner_workflow_integration.py::test_v8_production_workflow_approval_inventory_gate
-s
```

## Handoff

The final delivery supplies ordered commits, clean-worktree and preserved
quarantine-stash checks, and a new exact-HEAD V9 `git archive` in iCloud Downloads
with its SHA-256. No push or merge is authorized or performed. Phase 10.43 is not
started. Phase 10.42 and DP-042 remain IMPLEMENTED_PENDING_AUDIT.

NEXT=INDEPENDENT_REAUDIT_V9
