# CMM OS — Phase 10.42 — Independent Re-Audit V8

**Phase:** 10.42 — Integration with Planner and Workflow Engine
**Audit type:** Independent Re-Audit V8
**Auditor:** ChatGPT / CMM OS project
**Date:** 2026-09-06
**Result:** **FAIL**

---

## 1. Final verdict

```text
PHASE10_42_INDEPENDENT_REAUDIT_V8=FAIL

AUDITED_HEAD=e80214fbd5228f163889c8233e0a9cdaeee707a0
AUDIT_V8_BUNDLE_SHA256=3c51738a6104ac6185f47ff9367ef2ddc8019cfb7fdc8a09682aeb2e514f3c98

V1_BLOCKER_01_INVALID_UNAVAILABLE_PLAN=FIXED
V1_MAJOR_01_EXACT_OPERATION_SEMANTICS=FIXED
V1_MAJOR_02_CONNECTED_ACCEPTANCE=FIXED

V2_MAJOR_03_REAL_DOMAIN_OPERATION_SELECTION=FIXED
V2_MAJOR_04_MISSING_REQUIRED_DEPENDENCY=FIXED

V3_MAJOR_05_EFFECTIVE_OPERATION_CANDIDATES=FIXED

V4_MAJOR_06_OPERATION_PERMISSION_COMPATIBILITY=FIXED

V5_MAJOR_07_WORKFLOW_PERMISSION_COMPATIBILITY=FIXED

V6_MAJOR_08_WORKFLOW_FINAL_AVAILABILITY_COMPATIBILITY=FIXED
V6_MAJOR_09_UNSELECTED_WORKFLOW_APPROVAL_LEAKAGE=FIXED

V7_MAJOR_10_WORKFLOW_NODE_APPROVAL_PROJECTION=FIXED
V7_MAJOR_11_SUBWORKFLOW_PLANNING_ELIGIBILITY=FIXED

BLOCKERS=0
MAJORS=2
MINORS=0

V8_MAJOR_12_WORKFLOW_OPERATION_NODE_SEMANTICS=OPEN
V8_MAJOR_13_SUBWORKFLOW_PERMISSION_APPROVAL_SEMANTICS=OPEN

DP-042=NOT_VERIFIED
AT-DP-042=PASS
CLOSURE_ELIGIBLE=NO

NEXT=PHASE10_42_REMEDIATION_V8_TO_V9
```

Phase 10.42 is **not eligible for closure** after V8.

V8 successfully fixes both findings reported by V7:

1. all canonical selected-workflow approval sources currently encoded through workflow-level gates and node-level `REQUEST_APPROVAL` / `WorkflowNode.approval_gate` are projected;
2. required `INVOKE_SUBWORKFLOW` references are resolved recursively, version-aware and cycle-safe, and missing/ineligible required children fail before planner invocation.

The V8 closure pass then compared Phase 10.42 planning semantics directly against the three capability-sensitive branches of the canonical workflow permission adapter:

```text
WorkflowNode.operation_id
WorkflowNode.subworkflow_id
WorkflowNode.approval_gate / REQUEST_APPROVAL
```

The approval branch is now aligned.

The remaining mismatches are concentrated in the other two branches and are therefore grouped as two majors rather than fragmented into multiple one-field findings:

- `EXECUTE_OPERATION` planning eligibility still treats an operation mostly as an opaque operation ID and does not preserve exact node version, required/optional semantics, or operation-level approval/validation obligations of workflow-internal operations;
- `INVOKE_SUBWORKFLOW` planning eligibility handles required child existence/basic final eligibility, but still drops or ignores canonical permission/approval semantics for optional children and cross-domain child invocation.

Both remain execution-fail-safe because canonical execution and permission adapters re-evaluate these nodes. They are nevertheless closure-blocking Phase 10.42 planning-contract defects.

---

# 2. Exact V8 bundle authentication

Audited artifact:

```text
phase-10.42-audit-v8-e80214fbd5228f163889c8233e0a9cdaeee707a0.tar.gz
```

Declared SHA-256:

```text
3c51738a6104ac6185f47ff9367ef2ddc8019cfb7fdc8a09682aeb2e514f3c98
```

Independently recalculated SHA-256:

```text
3c51738a6104ac6185f47ff9367ef2ddc8019cfb7fdc8a09682aeb2e514f3c98
```

Embedded PAX global header:

```text
comment=e80214fbd5228f163889c8233e0a9cdaeee707a0
```

Archive inspection:

```text
MEMBERS=2051
TOP_LEVEL_PREFIX=CMM-OS-e80214fbd522
UNSAFE_PATHS=0
SPECIAL_MEMBERS=0
SYMLINKS_OR_HARDLINKS=0
```

Result:

```text
AUDIT_V8_BUNDLE_SHA256=VERIFIED
AUDITED_HEAD=VERIFIED_EXACT
ARCHIVE_PATH_SAFETY=PASS
ARCHIVE_HYGIENE=PASS
```

---

# 3. Frozen artifact integrity

## 3.1 Approved design spec

Expected and observed SHA-256:

```text
8c777d4e4c71595eedd02445f6d66a172db31f70a7a3b95991a24a0129d023e1
```

```text
SPEC_HASH=PASS
```

## 3.2 Approved implementation plan

Expected and observed SHA-256:

```text
5b5cbdb4ed9aecd311918f777b641f311f12b8dd51ca68ea493675198ed85d8a
```

```text
PLAN_HASH=PASS
```

## 3.3 Historical audit reports

Exact expected hashes remain preserved:

```text
V1  79debf52218a2bb0e2fb206bb3b72bf72dca8b5c5cfbe3c6f3c8dee4040515f2
V2  56d6ee71cfb1606538f154968ea85b4a8cc63c1b8ca1f579049d516c02553090
V3  62bb248d0402da7214e47f823f20fc8aecd9e141781cd6eb4a17eebeb1985414
V4  230c85b15e42b92f71a09d58f9c7686704852e6b6c5c61cbdc419ad6fb79943d
V5  89309ea61ba6f28d02b3a00d372f4156a7617bb87af495ec567c748486d408cd
V6  15b00d833cbf73902a681cab7335a70e0071ea0b412210f82c6dac047865dc3d
V7  9eaaf9046306f199c9ac6a176cad6c0d46048761537d2a018c41758d7948d9eb
```

Result:

```text
HISTORICAL_AUDIT_ARTIFACTS_PRESERVED=YES
```

---

# 4. V7 → V8 remediation scope

V8 remediation baseline:

```text
6c274a6327888150fcce43aa24c4fe0861ab8ac6
```

V8 implementation HEAD:

```text
e80214fbd5228f163889c8233e0a9cdaeee707a0
```

V8 commits reported and present in the audited lineage:

```text
5e38309 fix(domains): project canonical workflow node approvals
2aa95bf fix(domains): enforce subworkflow planning eligibility
7c4f38b test(domains): classify canonical workflow node planning semantics
a98816f test(domains): cover workflow graph planning obligations
4e28e04 docs(domains): update phase 10.42 v8 remediation evidence
e80214f test(domains): satisfy ruff and format on v8 eligibility tests
```

Phase 10.42 production change remains concentrated in:

```text
cmm/domains/planner_workflow_integration.py
```

No Phase 9 production redesign was introduced.

No parallel planner, workflow engine, workflow resolver, approval owner, permission owner, runtime, store, event bus, or state machine was introduced.

---

# 5. V7 MAJOR-10 — VERIFIED FIXED

Canonical V7 finding:

```text
V7_MAJOR_10_WORKFLOW_NODE_APPROVAL_PROJECTION=OPEN
```

V8 adds:

```text
_workflow_approval_ids(...)
```

and projects the deterministic deduplicated union of the canonical workflow approval sources used by existing execution/permission semantics:

```text
DomainWorkflowDefinition.approval_gates
WorkflowNode.approval_gate
REQUEST_APPROVAL node fallback: approval_gate or node_id
```

The projection occurs only for selected workflow graphs, preserving the prior no-leakage invariant.

Independent V8 focused tests and source inspection support:

```text
REAL_RELATIONSHIPS_DECISION_SUPPORT_NODE_APPROVAL=PROJECTED
REAL_HEALTH_MEDICATION_REVIEW_NODE_APPROVAL=PROJECTED
UNSELECTED_NODE_APPROVAL_GATE_LEAKAGE=0
WORKFLOW_APPROVAL_DEDUPLICATION=PASS
UNREPRESENTED_SELECTED_WORKFLOW_APPROVAL_GATE=0
```

Therefore:

```text
V7_MAJOR_10_WORKFLOW_NODE_APPROVAL_PROJECTION=FIXED
```

---

# 6. V7 MAJOR-11 — VERIFIED FIXED

Canonical V7 finding:

```text
V7_MAJOR_11_SUBWORKFLOW_PLANNING_ELIGIBILITY=OPEN
```

V8 introduces a required-child traversal:

```text
_required_subworkflow_closure_for_planning(...)
```

For required `INVOKE_SUBWORKFLOW` nodes it performs:

```text
exact workflow ID/version lookup
active registry resolution
same final planning permissions
same final operation candidates
same resource references
same effective Domain composition
recursive required-child evaluation
versioned ancestry cycle detection
child approval propagation
```

Independent V8 focused evidence passes for:

```text
missing required child
ineligible required child
eligible parent → child
nested chain
exact child version
cycle failure
same final authority propagation
required child approval propagation
```

Therefore:

```text
V7_MAJOR_11_SUBWORKFLOW_PLANNING_ELIGIBILITY=FIXED
```

---

# 7. Independent focused verification

The audit sandbox does not contain repository dependency:

```text
libcst
```

As in V2–V7, exact archive tests were run through the established namespace-package bootstrap for `cmm.agent_runtime` / `cmm.execution`, avoiding heavyweight package `__init__` side effects without modifying audited source.

## 7.1 Focused Phase 10.42 suite

Exact V8 archive:

```text
tests/domains/test_domain_planner_workflow_integration_contracts.py
tests/domains/test_domain_planner_workflow_integration.py
tests/domains/test_domain_planner_workflow_boundaries.py
tests/domains/test_domain_planner_workflow_dp042_acceptance.py
tests/agent_runtime/test_workflow_planner_adapter.py
```

Fresh independent result:

```text
222 passed
```

```text
FOCUSED_PHASE10_42=PASS
FOCUSED_PHASE10_42_COUNT=222
```

## 7.2 AT-DP-042

Fresh exact archive result:

```text
24 passed
```

```text
AT-DP-042=PASS
AT_DP_042_INDEPENDENT_COUNT=24
```

## 7.3 Boundary / fragmentation

Fresh exact archive result:

```text
92 passed
```

```text
BOUNDARY_FRAGMENTATION_TESTS=PASS
BOUNDARY_FRAGMENTATION_COUNT=92
```

## 7.4 Compile

Fresh exact archive:

```text
python3 -m compileall -q cmm tests
```

Result:

```text
COMPILEALL=PASS
```

## 7.5 Reverse imports

Fresh AST scan:

```text
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
WORKFLOWS_TO_DOMAIN_IMPORTS=0
```

## 7.6 Resolver ownership

V8 retains:

```text
cmm/domains/workflow_resolution.py
  resolve_domain_workflow
```

as the canonical workflow availability engine.

The Phase 10.42 helpers remain planning projections/delegates rather than a second workflow runtime.

```text
NO_PARALLEL_WORKFLOW_RESOLVER=YES
NO_PARALLEL_SUBWORKFLOW_RESOLVER=YES
```

---

# 8. Canonical node-branch closure methodology

V8 added an explicit classification for all current `WorkflowNodeType` enum members.

That is useful coverage, but classification alone is not sufficient to prove behavioral equivalence.

For closure, the auditor compared Phase 10.42 planning behavior against the actual capability-sensitive branches of canonical:

```text
cmm.domains.permission_adapters._node_decision(...)
```

That adapter has three semantic branches that can materially change permission/eligibility behavior:

```text
1. node.operation_id
2. node.subworkflow_id
3. node.approval_gate / REQUEST_APPROVAL
```

Observed after V8:

```text
approval branch:
  planning semantics aligned

operation branch:
  planning semantics still incomplete

subworkflow branch:
  planning semantics still incomplete
```

The remaining findings below therefore represent the two unresolved canonical branches, not arbitrary new fields.

---

# 9. MAJOR-12 — workflow EXECUTE_OPERATION planning semantics are incomplete

## 9.1 Severity

```text
MAJOR
```

Not a blocker because canonical workflow permission evaluation / Domain operation execution later resolves the exact operation and can deny execution.

It is closure-blocking because Phase 10.42 currently returns selected workflows and VALID canonical plans while the same workflow operation node is invalid, optional, or carries canonical static obligations that are absent from the plan.

## 9.2 Root cause

V8 final workflow availability ultimately evaluates an `EXECUTE_OPERATION` node primarily through:

```text
node.operation_id in context.available_operations
```

The final operation planning authority is also represented as operation IDs.

But canonical workflow permission evaluation resolves:

```text
(node.operation_id, node.operation_version)
```

and evaluates the exact `DomainOperationDefinition`.

The planning path therefore does not preserve the full canonical node semantics:

```text
operation ID
operation version
node.required
exact operation permission result
operation approval requirements
operation validation policy
```

The mismatch appears in multiple independently reproduced forms.

---

# 10. MAJOR-12 reproduction A — nonexistent operation version accepted

Registered canonical operation:

```text
python.find_symbol@1.0.0
```

Selected workflow node:

```text
node_type=EXECUTE_OPERATION
operation_id=python.find_symbol
operation_version=9.9.9
required=True
```

V8 planning observation:

```text
BLOCKED=False
REASONS=()
SELECTED=("python.badver",)
CANDIDATES=["python.find_symbol"]
PLAN_VALID=True
PLAN_CALLS=1
NODE_OP_VERSION=9.9.9
```

Canonical permission adapter behavior for the same node contract resolves exact:

```text
(operation_id, operation_version)
```

and returns:

```text
DENY
reason=operation_not_registered
```

Thus an exact-version-invalid workflow node can be represented by an unblocked VALID plan.

Required invariant:

```text
required EXECUTE_OPERATION exact ID/version
must resolve canonically before planner invocation
```

---

# 11. MAJOR-12 reproduction B — optional unavailable operation over-blocks workflow

Canonical workflow:

```text
required node:
  python.find_symbol
  available

optional node:
  python.list_imports
  required=False
  unavailable under final operation authority
```

V8 planning observation:

```text
BLOCKED=True
REASONS=("domain_workflow_unavailable",)
SELECTED=()
CANDIDATES=["python.find_symbol"]
PLAN_CALLS=0
```

Canonical workflow permission / engine semantics treat unavailable optional nodes differently:

```text
required=False DENY
does not make required_blocked=True

failed optional workflow engine node
is converted to skipped/not-applicable behavior
```

Therefore V8 is more restrictive than the canonical workflow contract.

The correct invariant is not:

```text
every unavailable EXECUTE_OPERATION node blocks
```

but:

```text
required node unavailable → blocks
optional node unavailable → preserve canonical optional-node semantics
```

---

# 12. MAJOR-12 reproduction C — workflow-internal operation approvals/validations can disappear

A selected workflow can internally execute an operation that carries canonical operation-level obligations while the Phase 9 planner independently chooses different operation candidates for its six planned operations.

Independent canonical in-memory reproduction:

```text
workflow:
  demo.flow

internal workflow operation:
  demo.z

demo.z:
  requires_approval=True
  validation_policy_id=validation.demo.z
```

Final operation candidates contain:

```text
demo.a
demo.b
demo.c
demo.d
demo.e
demo.f
demo.g
demo.z
```

The canonical planner chooses the first six unrelated candidates:

```text
PLAN_OPS=[
  demo.a,
  demo.b,
  demo.c,
  demo.d,
  demo.e,
  demo.f,
]
```

V8 result:

```text
BLOCKED=False
SELECTED=("demo.flow",)

PREPARED_VALIDATIONS=[]
PREPARED_APPROVALS=[]

PLAN_VALIDATION_IDS=[]
PLAN_APPROVAL_IDS=[]
PLAN_APPROVAL_NODE_COUNT=0

PLAN_CALLS=1
```

The selected workflow's internal canonical operation obligation therefore disappears from the planning representation merely because the generic planner happened not to choose that operation as one of its own operation steps.

This violates the Phase 10.42 requirement that declared operation/workflow approvals and validations remain representable and are not silently dropped.

---

# 13. MAJOR-12 required remediation

Do not flatten workflow execution into the Phase 9 planner.

Do not create a workflow-specific planner.

Do not copy every execution detail into `AgentWorkflowPlan`.

Instead, complete the Domain-side planning projection for canonical `EXECUTE_OPERATION` node semantics.

For every reachable selected-workflow `EXECUTE_OPERATION` node:

## Exact identity

Resolve exact:

```text
operation_id
operation_version
```

using the canonical Domain operation registry/definition source.

Do not accept an arbitrary registered version when the node declares a different version.

## Required / optional semantics

Use existing canonical workflow permission/engine behavior:

```text
required unavailable operation → workflow planning unavailable
optional unavailable operation → does not fail the whole workflow merely because unavailable
```

Do not weaken execution-time revalidation.

## Static representable obligations

For workflow-internal operations that are eligible/reachable, preserve canonical static planning obligations that Phase 10.42 requires to be representable, at minimum:

```text
required approvals
validation_policy_id / validation requirements
required permissions where relevant to final authority
```

Do not synthesize approval grants.

Do not duplicate runtime execution.

Do not blindly union unrelated risk/timeout metadata unless the frozen design requires it at plan level.

Use current V1 exact operation semantic projection as the canonical source rather than implementing a second semantics extractor.

---

# 14. MAJOR-12 required RED/GREEN evidence

At minimum:

```text
V8_MAJOR_12_WORKFLOW_OPERATION_NODE_SEMANTICS=FIXED

WORKFLOW_OPERATION_EXACT_VERSION_REQUIRED=PASS
MISSING_WORKFLOW_OPERATION_VERSION_BLOCKS_BEFORE_PLANNER=PASS

REQUIRED_UNAVAILABLE_WORKFLOW_OPERATION_BLOCKS=PASS
OPTIONAL_UNAVAILABLE_WORKFLOW_OPERATION_DOES_NOT_BLOCK=PASS

SELECTED_WORKFLOW_INTERNAL_OPERATION_APPROVALS_PROJECTED=PASS
SELECTED_WORKFLOW_INTERNAL_OPERATION_VALIDATIONS_PROJECTED=PASS

WORKFLOW_OPERATION_NODE_FINAL_AUTHORITY=PASS
```

Add a production inventory for workflow operation nodes:

```text
PRODUCTION_WORKFLOW_OPERATION_NODES=<count>
PRODUCTION_WORKFLOW_OPERATION_VERSION_REFERENCES=VERIFIED
UNREPRESENTED_WORKFLOW_INTERNAL_OPERATION_OBLIGATIONS=0
```

where "obligations" means only Phase 10.42 planning-representable canonical obligations, not arbitrary execution internals.

---

# 15. MAJOR-13 — subworkflow permission/approval semantics remain incomplete

## 15.1 Severity

```text
MAJOR
```

Not a blocker because canonical execution-time permission evaluation still checks child workflow permissions and cross-domain access.

It is closure-blocking because V8 can plan a parent while dropping approval obligations or ignoring permission DENY decisions that canonical subworkflow invocation will encounter.

## 15.2 Root cause

V8 `_required_subworkflow_closure_for_planning(...)` evaluates required children through availability/composition/operation/resource/permission IDs, but:

1. it skips every optional `INVOKE_SUBWORKFLOW` node immediately;
2. it does not run/reuse the canonical subworkflow node permission decision that handles cross-domain child access;
3. it therefore cannot project canonical `DOMAIN_CROSS_ACCESS` approvals;
4. it can accept a required cross-domain child whose canonical permission adapter would DENY.

The V8 helper is correct for the V7 missing/ineligible-child finding, but not yet equivalent to the full canonical subworkflow permission semantics.

---

# 16. MAJOR-13 reproduction A — optional eligible child approval is dropped

Parent:

```text
python.opt_parent
```

Optional child node:

```text
node_type=INVOKE_SUBWORKFLOW
subworkflow_id=python.opt_child
subworkflow_version=1.0.0
required=False
```

Child exists, is eligible, and declares:

```text
approval_gates=("child-approval",)
```

V8 planning selection:

```text
_WorkflowSelection(
  workflow_ids=("python.opt_parent",),
  approval_gate_ids=(),
  failure_reason=None
)
```

Because V8 currently executes:

```text
if not node.required:
    continue
```

the optional child is not inspected at all.

Canonical permission semantics do **not** mean "ignore every optional child obligation".

They mean optional DENY does not block the whole workflow; approval requirements from node decisions are still aggregated.

Therefore an optional child that is usable but approval-requiring may introduce a real representable approval obligation even though an unavailable optional child remains nonblocking.

---

# 17. MAJOR-13 reproduction B — required cross-domain child approval is dropped

Parent:

```text
project.parent
```

Required child:

```text
health.child@1.0.0
```

The effective composition contains both:

```text
domain:project
domain:health
```

V8 Phase 10.42 selection:

```text
PLANNING_SELECTION=
_WorkflowSelection(
  workflow_ids=("project.parent",),
  approval_gate_ids=(),
  failure_reason=None
)
```

Canonical workflow permission evaluation for the same child node and permission policies returns:

```text
CANONICAL_NODE_DECISION=approval_required
CANONICAL_APPROVAL_ACTIONS=["domain.cross_access"]
CANONICAL_APPROVAL_COUNT=1
```

Thus the parent workflow is selected while the canonical cross-domain handoff approval is absent from the planning approval projection.

---

# 18. MAJOR-13 reproduction C — canonical cross-domain DENY does not block planning selection

Using the same required:

```text
project.parent
→ health.child
```

but with target/inbound cross-domain permission policy denying the handoff:

V8 planning selection still succeeds because the Phase 10.42 subworkflow closure does not consult canonical cross-domain permission resolution.

Canonical evaluation:

```text
CROSS_CHILD_DENIED_CANONICAL=deny

reasons=(
  "capability_not_allowed",
  "target_cross_domain_denied",
)
```

This means the parent can be considered plan-eligible while canonical node permission semantics already say that the required child handoff is denied.

Execution remains fail-safe, so this is a major rather than blocker.

---

# 19. MAJOR-13 required remediation

Do not create another permission resolver.

Do not create a subworkflow runtime.

Reuse the existing canonical workflow-node permission semantics or factor the relevant pure child-permission logic so planning and execution share one truth.

For every reachable `INVOKE_SUBWORKFLOW` node:

## Required child

Preserve V8 behavior:

```text
missing/ineligible required child → block before planner
```

Additionally:

```text
canonical subworkflow node permission DENY → block before planner
canonical approval-required result → preserve approval obligation in plan
```

## Optional child

Preserve canonical optional semantics:

```text
missing/ineligible/denied optional child
does not automatically block the parent
```

But do not drop canonical obligations from an optional child that is actually resolvable/eligible and produces an approval-required result.

Required distinction:

```text
optional child DENY → nonblocking according to canonical required=False rule
optional child APPROVAL_REQUIRED → approval obligation remains representable
```

## Cross-domain child

Reuse canonical:

```text
resolve_cross_domain(...)
```

semantics for child workflow handoff.

Do not treat mere Domain composition membership as permission approval.

Preserve exact:

```text
source Domain
target Domain
workflow identity/version
capability=WORKFLOW_EXECUTE / DOMAIN_CROSS_ACCESS
sensitivity
approval requirement provenance
```

at the level required by existing Phase 10.42 planning contracts.

---

# 20. MAJOR-13 required RED/GREEN evidence

At minimum:

```text
V8_MAJOR_13_SUBWORKFLOW_PERMISSION_APPROVAL_SEMANTICS=FIXED

OPTIONAL_MISSING_SUBWORKFLOW_REMAINS_NONBLOCKING=PASS
OPTIONAL_INELIGIBLE_SUBWORKFLOW_REMAINS_NONBLOCKING=PASS
OPTIONAL_ELIGIBLE_SUBWORKFLOW_APPROVALS_PROJECTED=PASS
OPTIONAL_SUBWORKFLOW_APPROVAL_NOT_DROPPED=PASS

REQUIRED_CROSS_DOMAIN_SUBWORKFLOW_DENY_BLOCKS_BEFORE_PLANNER=PASS
REQUIRED_CROSS_DOMAIN_SUBWORKFLOW_APPROVAL_PROJECTED=PASS

SUBWORKFLOW_PERMISSION_DECISION_REUSES_CANONICAL_RESOLVER=PASS
SUBWORKFLOW_FINAL_AUTHORITY_PROPAGATES=PASS
SUBWORKFLOW_VERSION_RESOLUTION=PASS
SUBWORKFLOW_CYCLE_FAILS_CLOSED=PASS

NO_PARALLEL_SUBWORKFLOW_PERMISSION_RESOLVER=YES
```

Also preserve:

```text
MISSING_REQUIRED_SUBWORKFLOW_BLOCKS_BEFORE_PLANNER=PASS
INELIGIBLE_REQUIRED_SUBWORKFLOW_BLOCKS_BEFORE_PLANNER=PASS
ELIGIBLE_SUBWORKFLOW_CHAIN_PLANS=PASS
SUBWORKFLOW_REUSES_SHARED_WORKFLOW_ENGINE=PASS
```

---

# 21. WorkflowNodeType classification assessment

V8 added an enum-complete matrix for all 18 current `WorkflowNodeType` members.

That gate remains useful:

```text
ALL_CANONICAL_WORKFLOW_NODE_TYPES_CLASSIFIED=PASS
UNCLASSIFIED_WORKFLOW_NODE_TYPES=0
```

The V8 findings do **not** imply the other 15 node types require new owners or planning behavior.

Instead, they show that classification of:

```text
EXECUTE_OPERATION
INVOKE_SUBWORKFLOW
```

was too coarse to guarantee semantic equivalence with canonical permission/runtime rules.

The next remediation should strengthen the behavioral invariants of those two classifications, not create special planning handlers for every enum member.

---

# 22. Prior findings remain fixed

Independent V8 evidence supports:

```text
V1_BLOCKER_01_INVALID_UNAVAILABLE_PLAN=FIXED
V1_MAJOR_01_EXACT_OPERATION_SEMANTICS=FIXED
V1_MAJOR_02_CONNECTED_ACCEPTANCE=FIXED

V2_MAJOR_03_REAL_DOMAIN_OPERATION_SELECTION=FIXED
V2_MAJOR_04_MISSING_REQUIRED_DEPENDENCY=FIXED

V3_MAJOR_05_EFFECTIVE_OPERATION_CANDIDATES=FIXED

V4_MAJOR_06_OPERATION_PERMISSION_COMPATIBILITY=FIXED

V5_MAJOR_07_WORKFLOW_PERMISSION_COMPATIBILITY=FIXED

V6_MAJOR_08_WORKFLOW_FINAL_AVAILABILITY_COMPATIBILITY=FIXED
V6_MAJOR_09_UNSELECTED_WORKFLOW_APPROVAL_LEAKAGE=FIXED

V7_MAJOR_10_WORKFLOW_NODE_APPROVAL_PROJECTION=FIXED
V7_MAJOR_11_SUBWORKFLOW_PLANNING_ELIGIBILITY=FIXED
```

MAJOR-12 and MAJOR-13 are deeper semantic completeness gaps inside the two canonical node branches that V8 now explicitly classifies.

---

# 23. Documentation audit

Current V8 documentation remains correctly in:

```text
PHASE10_42=IMPLEMENTED_PENDING_AUDIT
DP_042=IMPLEMENTED_PENDING_AUDIT
AT_DP_042=PASS
```

No premature closure was found.

```text
DOCUMENTATION_STATUS_DISCIPLINE=PASS
```

However any V8 reference wording that claims complete canonical workflow-node semantic coverage must be narrowed or updated during V8→V9 because MAJOR-12 and MAJOR-13 show the two capability-sensitive branches are not yet fully aligned.

---

# 24. Architecture / ownership assessment

V8 remains architecturally within the approved design:

```text
TaskPlanner remains canonical planner
AgentPlanningService remains canonical planning facade
AgentWorkflowPlan remains sole plan contract
AgentWorkflowPlanValidator remains canonical plan validator

Domain operation registry remains exact operation-definition authority
Domain permission resolver remains permission authority
DomainWorkflowExecutor remains Domain workflow execution owner
WorkflowEngine remains shared workflow engine
resolve_domain_workflow remains canonical Domain workflow availability engine

Phase 10.41 remains actual operation execution path
```

Reverse imports:

```text
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
WORKFLOWS_TO_DOMAIN_IMPORTS=0
```

No parallel owners found:

```text
NO_PARALLEL_PLANNER=YES
NO_PARALLEL_WORKFLOW_ENGINE=YES
NO_PARALLEL_WORKFLOW_RESOLVER=YES
NO_PARALLEL_SUBWORKFLOW_RESOLVER=YES
NO_PARALLEL_PLAN_STORE=YES
NO_PARALLEL_WORKFLOW_STORE=YES
NO_PARALLEL_PERMISSION_SYSTEM=YES
NO_PARALLEL_APPROVAL_SYSTEM=YES
NO_PARALLEL_VALIDATION_SYSTEM=YES
NO_PARALLEL_RUNTIME=YES
NO_PARALLEL_EVENT_BUS=YES
NO_PARALLEL_STATE_MACHINE=YES
```

The V8 findings should be remediated by reusing existing canonical operation and permission semantics, not by reopening architecture.

---

# 25. DP-042 assessment

V8 now proves:

```text
real Domain operation selection = PASS
operation allow/prohibit authority = PASS
operation permission compatibility = PASS

top-level workflow permission compatibility = PASS
top-level workflow operation ID compatibility = PASS
workflow resource compatibility = PASS
workflow composition compatibility = PASS

workflow-level approvals = PASS
node-level direct approval gates = PASS
unselected approval leakage = PASS

required subworkflow missing/ineligible handling = PASS
required subworkflow recursion = PASS
required subworkflow exact version = PASS
subworkflow cycle failure = PASS

all current WorkflowNodeType enum members classified = PASS

connected canonical acceptance = PASS
execution-time revalidation = preserved
reverse imports = zero
parallel owners = absent
```

But DP-042 requires dependency-compatible, permission-compatible and representable workflow planning under canonical authority.

MAJOR-12 proves `EXECUTE_OPERATION` nodes still do not preserve exact canonical operation-node semantics.

MAJOR-13 proves `INVOKE_SUBWORKFLOW` nodes still do not preserve canonical optional/cross-domain permission and approval semantics.

Therefore:

```text
DP-042=NOT_VERIFIED
```

---

# 26. AT-DP-042 assessment

Independent exact V8 acceptance result:

```text
24 passed
```

Therefore:

```text
AT-DP-042=PASS
```

The current AT proves the connected positive chain and prior adversarial findings.

The next remediation must add the MAJOR-12/13 adversarial cases without weakening or replacing the existing connected acceptance.

---

# 27. Inherited Phase 10.41 / subsystem evidence

Agent-reported canonical environment:

```text
AT_DP_041=128 passed
DOMAIN_SUITE=9365 passed
AGENT_RUNTIME_SUITE=3432 passed
WORKFLOWS_SUITE=46 passed
GLOBAL_SUITE=14962 passed
```

Changed-file gates reported:

```text
RUFF_CHANGED_FILES=PASS
FORMAT_CHANGED_FILES=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
```

Repository-wide Ruff/format debt was reported as historical and with zero overlap with V7→V8 changed files.

Independent archive checks additionally confirm:

```text
FOCUSED_PHASE10_42=222 passed
AT_DP_042=24 passed
BOUNDARY_FRAGMENTATION=92 passed
COMPILEALL=PASS
```

The V8 FAIL does not rely on linter availability; MAJOR-12 and MAJOR-13 are independently reproduced semantic mismatches.

---

# 28. Severity summary

```text
BLOCKERS=0

MAJORS=2

  MAJOR-12:
    workflow EXECUTE_OPERATION planning semantics are incomplete:
    exact operation version is ignored, optional unavailable operation
    semantics are over-blocked, and static operation approval/validation
    obligations can disappear from the selected workflow plan.

  MAJOR-13:
    subworkflow planning semantics are incomplete:
    optional child approval obligations are skipped, and required
    cross-domain child invocation does not reuse canonical cross-domain
    permission DENY / APPROVAL_REQUIRED semantics.

MINORS=0
```

---

# 29. Closure decision

Required closure floor:

```text
BLOCKERS=0
MAJORS=0
DP-042=VERIFIED_EXISTING
AT-DP-042=PASS
CLOSURE_ELIGIBLE=YES
```

Observed V8:

```text
BLOCKERS=0
MAJORS=2
DP-042=NOT_VERIFIED
AT-DP-042=PASS
CLOSURE_ELIGIBLE=NO
```

Therefore:

```text
PHASE10_42_INDEPENDENT_REAUDIT_V8=FAIL
CLOSURE_ELIGIBLE=NO
```

Do not create the Phase 10.42 docs-only closure commit.

Do not begin Phase 10.43.

---

# 30. Required next cycle

The V8→V9 remediation should address **both remaining canonical node branches in one cycle**:

```text
COMMIT THIS V8 RE-AUDIT REPORT

→ REMEDIATION V8 → V9

→ RED exact workflow operation version
→ RED optional unavailable workflow operation
→ RED internal workflow-operation approval projection
→ RED internal workflow-operation validation projection

→ RED optional eligible child approval projection
→ RED required cross-domain child DENY
→ RED required cross-domain child APPROVAL_REQUIRED

→ reuse exact canonical operation definition semantics
→ reuse canonical workflow-node permission / cross-domain resolver semantics
→ preserve required/optional node behavior
→ no parallel resolver/planner/runtime/approval system

→ preserve all V1–V7 fixes

→ focused Phase 10.42
→ AT-DP-042
→ AT-DP-041
→ workflow operation-node regressions
→ subworkflow permission regressions
→ approval/validation regressions
→ Domain suite
→ Agent Runtime suite
→ Workflows suite
→ global suite
→ Ruff / format
→ compileall
→ git diff --check
→ architecture gates

→ fully committed clean implementation
→ NEW exact-HEAD V9 git-archive bundle
→ NEW SHA-256
→ Independent Re-Audit V9
```

Before implementation, the agent should compare Phase 10.42 planning projection directly against every branch and aggregate rule in:

```text
cmm.domains.permission_adapters._node_decision(...)
evaluate_domain_workflow(...)
```

so V9 does not repeat another partial semantic projection.

---

# 31. Final machine-readable verdict

```text
PHASE10_42_INDEPENDENT_REAUDIT_V8=FAIL

AUDITED_HEAD=e80214fbd5228f163889c8233e0a9cdaeee707a0
AUDIT_V8_BUNDLE_SHA256=3c51738a6104ac6185f47ff9367ef2ddc8019cfb7fdc8a09682aeb2e514f3c98

ARCHIVE_PATH_SAFETY=PASS
ARCHIVE_HYGIENE=PASS

SPEC_HASH=PASS
PLAN_HASH=PASS
HISTORICAL_AUDIT_ARTIFACTS_PRESERVED=YES

FOCUSED_PHASE10_42=PASS
FOCUSED_PHASE10_42_COUNT=222

AT-DP-042=PASS
AT_DP_042_INDEPENDENT_COUNT=24

BOUNDARY_FRAGMENTATION_TESTS=PASS
BOUNDARY_FRAGMENTATION_COUNT=92

COMPILEALL=PASS

AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
WORKFLOWS_TO_DOMAIN_IMPORTS=0

NO_PARALLEL_PLANNER=YES
NO_PARALLEL_WORKFLOW_ENGINE=YES
NO_PARALLEL_WORKFLOW_RESOLVER=YES
NO_PARALLEL_SUBWORKFLOW_RESOLVER=YES
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

V5_MAJOR_07_WORKFLOW_PERMISSION_COMPATIBILITY=FIXED

V6_MAJOR_08_WORKFLOW_FINAL_AVAILABILITY_COMPATIBILITY=FIXED
V6_MAJOR_09_UNSELECTED_WORKFLOW_APPROVAL_LEAKAGE=FIXED

V7_MAJOR_10_WORKFLOW_NODE_APPROVAL_PROJECTION=FIXED
V7_MAJOR_11_SUBWORKFLOW_PLANNING_ELIGIBILITY=FIXED

V8_MAJOR_12_WORKFLOW_OPERATION_NODE_SEMANTICS=OPEN
V8_MAJOR_13_SUBWORKFLOW_PERMISSION_APPROVAL_SEMANTICS=OPEN

BLOCKERS=0
MAJORS=2
MINORS=0

DP-042=NOT_VERIFIED
AT-DP-042=PASS
CLOSURE_ELIGIBLE=NO

NEXT=PHASE10_42_REMEDIATION_V8_TO_V9
```
