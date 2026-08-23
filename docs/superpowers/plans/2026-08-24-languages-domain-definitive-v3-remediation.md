# Phase 10.26 — Definitive V3 Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before every completion claim.

**Goal:** Remediate the final V3 independent-audit findings for Phase 10.26 Languages and eliminate same-root-cause semantic gaps before one final independent closure audit.

**Architecture:** Preserve the frozen Languages Domain architecture and all already-passing V1/V2 remediation. Fix the two residual Languages operation semantics at the source, replace static/manual trace provenance with canonical runtime identities, and add one minimal shared permission-gate decision identity because the existing shared contract has no runtime result ID. Add content-derived semantic closure tests across all 15 operation result helpers so a green schema/JSON check cannot hide impossible or evidence-free state.

**Tech Stack:** Python 3.10+, pytest, Ruff, CMM shared Domain Intelligence contracts, shared Workflow Engine, Domain Rule Executor, Domain Permission Gate/ApprovalService, Domain Trace contracts.

**Spec:** `docs/superpowers/specs/2026-08-23-languages-domain-design.md`

## Global Constraints

- Branch: `feature/phase-10-domain-intelligence`.
- Expected starting HEAD before installation commit: `13c8d5d`.
- Frozen domain: `domain:languages`.
- Display name: `Idiomas`.
- Profile: `LanguageLearningProfile`.
- Canon remains exactly `16 entities / 15 resources / 14 rules / 15 operations / 9 workflows`.
- Production package remains exactly 14 `cmm/domains/languages/*.py` modules.
- `languages.progress_checkpoint` remains canonical.
- Do not modify Phase 10.27 / Paternidad.
- Do not restore `Nil` architecture.
- No push.
- No merge to `main`.
- Do not close Phase 10.26 before the final independent audit.
- Preserve all previously authorized shared fixes:
  - typed `DomainMetadata.metadata` compatibility;
  - accumulated `WorkflowRun.outputs`;
  - trace kinds `EVIDENCE`, `MEMORY_PROPOSAL`, `MEMORY_BINDING`, `PRESENTATION_RESULT`;
  - `presentation_result_ids`.
- The only pre-authorized new shared change in this plan is the minimal runtime identity for `PermissionGateResult` described in Task 4.
- Any other shared-engine/interface change requires STOP + explicit human authorization.

## V3 Independent Audit Findings

```text
V3-B-001
Connected trace does not yet use canonical runtime identities for:
- rule execution result;
- permission-gate decision;
- selected profile mode is not preserved.

V3-M-001
review_exercise_result({}) becomes:
is_correct=True
score=1.0
feedback="Great job!"

V3-M-002
track_vocabulary_result(items=[]) reports:
total_items=0
mastered=5
```

## Root-cause statement

Do not patch symptoms.

The remaining operation defects share one root class:

```text
missing evidence / missing state
→ positive semantic default
```

The trace defect shares one root class:

```text
definition/request/synthetic identity
→ mislabeled as runtime result provenance
```

The final remediation must make those transformations structurally impossible.

---

# File map

Primary Languages source:

```text
cmm/domains/languages/operations.py
cmm/domains/languages/trace.py              only if a RED proves assembly needs adjustment
```

Connected acceptance / semantic tests:

```text
tests/domains/test_languages_domain_dp026_acceptance.py
tests/domains/test_languages_domain_operations.py
tests/domains/test_languages_domain_adversarial.py
tests/domains/test_languages_domain_trace.py
tests/domains/test_languages_domain_presentation.py
```

Shared rule runtime, expected to be reused without behavior changes:

```text
cmm/domains/rule_contracts.py
cmm/domains/rule_execution.py
cmm/domains/rule_selection.py
```

Shared permission runtime, minimal authorized extension:

```text
cmm/domains/permission_gate.py
tests/domains/test_domain_permission_gate.py
```

Shared trace contract should not require another extension:

```text
cmm/domains/trace_contracts.py
```

Documentation after GREEN:

```text
docs/reference/languages-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md
```

---

# Task 0 — Reproduce V3 findings and same-class baseline before touching production

**Files:**
- Test: `tests/domains/test_languages_domain_operations.py`
- Test: `tests/domains/test_languages_domain_adversarial.py`
- Test: `tests/domains/test_languages_domain_dp026_acceptance.py`
- Test: `tests/domains/test_domain_permission_gate.py`

**Produces:** hard RED evidence for every change in this plan.

- [ ] **Step 1: Capture clean baseline**

Run:

```bash
git branch --show-current
git rev-parse --short HEAD
git status --short --branch
```

Expected before implementation work:

```text
feature/phase-10-domain-intelligence
tracked worktree clean
only pre-existing ?? tmp/
```

- [ ] **Step 2: Add exact RED for missing exercise outcome**

Required assertion:

```python
result = review_exercise_result(exercise_result={})

assert result["is_correct"] is None
assert result["score"] is None
assert result["observed_errors"] == []
assert result["feedback"] == "Not assessed: missing exercise outcome."
assert result["difficulty_adjustment"] == "hold"
```

Current code must fail this test because it produces `True / 1.0 / Great job!`.

Also RED:

```python
result = review_exercise_result(exercise_result={"user_answer": "x"})
assert result["is_correct"] is None
assert result["score"] is None
```

A user answer without outcome evidence is not correctness evidence.

- [ ] **Step 3: Add exact RED for vocabulary impossible mastery**

Required:

```python
result = track_vocabulary_result(vocabulary_list={"items": []})
assert result["total_items"] == 0
assert result["mastery_summary"]["mastered"] == 0
assert result["mastery_summary"]["learning"] == 0
assert result["candidate_updates"] == []
```

And:

```python
result = track_vocabulary_result(
    vocabulary_list={"items": [{"id": "v1", "term": "hello", "state": "learning"}]}
)
assert result["total_items"] == 1
assert result["mastery_summary"]["mastered"] == 0
assert result["mastery_summary"]["learning"] == 1
```

Current code must fail because `mastered == 5`.

- [ ] **Step 4: Add trace RED for static rule definition IDs**

The connected acceptance must assert:

```python
assert rule_execution.id not in {
    selected.definition.id for selected in rule_plan.selected_rules
}
```

and:

```python
trace RULE_RESULT IDs == {rule_execution.id}
```

A static `languages.*` rule definition ID must never be accepted as `RULE_RESULT`.

- [ ] **Step 5: Add trace RED for permission decision identity**

Before the shared fix:

```python
consumed = gate.evaluate_operation_definition(...)
assert consumed.decision_id
```

must fail because `PermissionGateResult` currently has no `decision_id`.

This proves the shared extension is required by the real contract, not invented for Languages.

- [ ] **Step 6: Add profile-mode trace RED**

Pick one actual runtime selected mode in the connected scenario, e.g.:

```python
selected_profile_mode = "practice"
```

Require:

```python
assert selected_profile_mode in LANGUAGES_PEDAGOGICAL_MODES
assert trace.metadata["selected_profile_mode"] == selected_profile_mode
```

The current trace must fail because no selected mode is preserved.

- [ ] **Step 7: Verify REDs fail for the audited reasons**

Run only the new tests.

Store output in:

```text
tmp/phase10-26-v3-red/
```

Do not commit `tmp/`.

Expected failures must correspond exactly to:

```text
missing exercise -> positive default
mastered=5 constant
rule_id used instead of runtime result id
PermissionGateResult lacks decision_id
selected mode absent from trace
```

Do not continue if a RED passes unexpectedly; investigate first.

---

# Task 1 — Fix missing exercise outcome semantics at the source

**Files:**
- Modify: `cmm/domains/languages/operations.py`
- Test: `tests/domains/test_languages_domain_operations.py`
- Test: `tests/domains/test_languages_domain_adversarial.py`
- Test: `tests/domains/test_languages_domain_presentation.py`

**Interfaces:**
- Consumes: `exercise_result: Mapping[str, Any] | None`.
- Produces: the existing `languages.review_exercise` result, with `score` and `is_correct` now explicitly nullable for unassessed input.

## Design

Unknown must remain unknown.

Canonical evidence rules:

```text
strict bool is_correct present
→ correctness observed

finite numeric score present
→ score observed

neither present
→ unassessed

user_answer alone
→ not correctness evidence

malformed/non-finite score without valid correctness
→ unassessed

explicit is_correct=False
→ observed error may be created

unassessed
→ no observed error
→ no positive feedback
→ no difficulty promotion
```

Do not encode unknown as incorrect.

- [ ] **Step 1: Narrow output schema to represent unknown**

Add local schema helpers only if needed:

```python
_NUM_OR_NULL = {"type": ["number", "integer", "null"]}
_BOOL_OR_NULL = {"type": ["boolean", "null"]}
```

Update only the `languages.review_exercise` output properties:

```python
"score": _NUM_OR_NULL,
"is_correct": _BOOL_OR_NULL,
```

Keep both keys required.

- [ ] **Step 2: Implement evidence-presence logic**

Use strict checks:

```python
has_correctness = isinstance(er.get("is_correct"), bool)
clean_score = _finite_number(er.get("score")) if "score" in er else None
has_score = clean_score is not None
```

Semantics:

```python
if not has_correctness and not has_score:
    is_correct = None
    score = None
elif has_correctness:
    is_correct = er["is_correct"]
    score = clean_score if has_score else (1.0 if is_correct else 0.0)
else:
    is_correct = None
    score = clean_score
```

Malformed score does not create a false negative by itself.

- [ ] **Step 3: Gate errors/feedback on observed correctness**

Only:

```python
is_correct is False
```

may create an observed exercise error.

Feedback:

```text
True  -> Great job!
False -> Review the target structure.
None  -> Not assessed: missing exercise outcome.
```

Difficulty:

```text
True  -> maintain
False -> scaffold
None  -> hold
```

- [ ] **Step 4: GREEN focused tests**

Required cases:

```text
{}
{"user_answer": "..."}
{"is_correct": True}
{"is_correct": False}
{"score": 0.8}
{"is_correct": False, "score": 0.2}
NaN
+Inf
-Inf
True as score
"not-a-number"
{}
[]
None
```

Every public output must survive:

```python
json.dumps(result, allow_nan=False)
```

- [ ] **Step 5: Presentation parity**

`present_languages_result()` must preserve:

```text
is_correct=None
score=None
feedback="Not assessed..."
```

without converting unknown to false/zero/positive.

- [ ] **Step 6: Commit**

```bash
git add \
  cmm/domains/languages/operations.py \
  tests/domains/test_languages_domain_operations.py \
  tests/domains/test_languages_domain_adversarial.py \
  tests/domains/test_languages_domain_presentation.py

git diff --cached --check

git commit -m "fix(domains): preserve unknown exercise outcomes"
```

---

# Task 2 — Replace hard-coded vocabulary mastery with evidence-derived candidate state

**Files:**
- Modify: `cmm/domains/languages/operations.py`
- Test: `tests/domains/test_languages_domain_operations.py`
- Test: `tests/domains/test_languages_domain_adversarial.py`
- Test: `tests/domains/test_languages_domain_presentation.py`

**Interfaces:**
- Consumes:
  - `vocabulary_list.items`;
  - `new_items`;
  - `review_results`.
- Produces:
  - candidate-only vocabulary state;
  - no persistence.

## Canonical vocabulary states

Use only the frozen states:

```text
new
learning
review
consolidated
needs_reinforcement
```

Unknown/malformed state falls back to:

```text
new
```

for a new/unknown item; it must never become `consolidated`.

## Review-result application

Match review results to items by a stable item identity:

```text
item_id
or
id
```

A review result may change **candidate state only**.

Conservative transitions:

```text
explicit valid state in review result
→ use that valid candidate state

explicit correct=True
→ candidate state "review"
  (one correct review does not prove consolidation)

explicit correct=False
→ candidate state "needs_reinforcement"

no usable review evidence
→ retain existing normalized state
```

No single review should silently create `consolidated` unless the review payload explicitly contains canonical state `consolidated`.

Do not persist.

- [ ] **Step 1: Normalize all vocabulary items**

Normalize:
- existing items;
- new items;
- item IDs;
- states.

Reject/ignore non-mapping items deterministically.

Do not mutate input objects.

- [ ] **Step 2: Actually consume `review_results`**

Build a lookup by stable vocabulary item ID.

Apply only grounded candidate transitions above.

Review result for an unknown item must not invent an item.

- [ ] **Step 3: Derive summary from candidate items**

```python
mastered = sum(item["state"] == "consolidated" for item in candidate_items)
learning = len(candidate_items) - mastered
```

Required invariant:

```text
0 <= mastered <= total_items
0 <= learning <= total_items
mastered + learning == total_items
```

- [ ] **Step 4: Preserve proposal-only boundary**

Must remain:

```python
"persistence_applied": False
```

`candidate_updates` are candidate state, not a stored mutation.

- [ ] **Step 5: GREEN semantic matrix**

Required cases:

```text
0 items
1 new
1 learning
1 review
1 consolidated
1 needs_reinforcement
mixed states
new_items
correct review
incorrect review
explicit consolidated review state
review for unknown item
malformed state
duplicate item identity
```

For duplicates, fail closed/deduplicate deterministically; never count one logical item multiple times merely because it appears in two input collections.

- [ ] **Step 6: Add impossible-state assertions**

Across every test:

```python
assert 0 <= mastered <= total
assert 0 <= learning <= total
assert mastered + learning == total
```

- [ ] **Step 7: Presentation parity**

Presentation must not change the derived counts/state.

- [ ] **Step 8: Commit**

```bash
git add \
  cmm/domains/languages/operations.py \
  tests/domains/test_languages_domain_operations.py \
  tests/domains/test_languages_domain_adversarial.py \
  tests/domains/test_languages_domain_presentation.py

git diff --cached --check

git commit -m "fix(domains): derive languages vocabulary mastery"
```

---

# Task 3 — Execute selected Languages rules through the canonical shared rule runtime

**Files:**
- Modify: `tests/domains/test_languages_domain_dp026_acceptance.py`
- Test: `tests/domains/test_languages_domain_trace.py`
- Shared source: REUSE ONLY
  - `cmm/domains/rule_contracts.py`
  - `cmm/domains/rule_execution.py`
  - existing shared reasoning-rule registry implementation

No shared rule-contract modification is expected or authorized.

**Produces:**
- actual `DomainRuleExecutionPlan.id`;
- actual `DomainRuleExecutionResult.id`;
- actual rule execution payload.

## Design

The previous acceptance did:

```text
rule.evaluate(context)
→ DomainRuleResult.rule_id
→ RULE_RESULT
```

The final acceptance must do:

```text
typed DomainRuleExecutionPlan
→ DefaultDomainRuleExecutor.execute(...)
→ DomainRuleExecutionResult.id
→ RULE_RESULT
```

The canonical rule definition IDs remain definitions, not result identities.

- [ ] **Step 1: Build a real shared registry**

Register the actual selected Languages rule objects used in the connected scenario.

Do not create test-only fake rule implementations if the real rule objects satisfy the shared registry protocol.

- [ ] **Step 2: Build a typed execution plan**

Create a real `DomainRuleExecutionPlan` with:
- fresh plan `id`;
- current timestamp;
- selected real rule definitions;
- real `SelectedReasoningRule` / source records;
- domain `domain:languages`;
- profile source `LanguageLearningProfile`.

Use only the subset actually needed by the connected acceptance.

Do not modify all 14 rules merely to create trace noise.

- [ ] **Step 3: Execute with `DefaultDomainRuleExecutor`**

Use the scenario's deterministic ID factory and clock.

Store:

```python
self.state["rule_plan"] = rule_plan
self.state["rule_execution"] = rule_execution
```

Add both IDs to actual-produced inventory.

- [ ] **Step 4: Preserve semantic assertions**

Continue testing the actual rule results needed for:
- error-pattern evidence;
- progression evidence;
- certification temporal authority.

The executor path must produce the same semantic findings as the prior direct path.

- [ ] **Step 5: Trace runtime identities**

Use:

```text
rule_plan.id       -> RULE_PLAN
rule_execution.id  -> RULE_RESULT
```

Do not use:

```text
rule.definition.id -> RULE_RESULT
DomainRuleResult.rule_id -> RULE_RESULT
```

Explicit anti-cheat:

```python
definition_ids = {selected.definition.id for selected in rule_plan.selected_rules}
assert rule_execution.id not in definition_ids
assert not definition_ids.intersection(trace_rule_result_ids)
```

- [ ] **Step 6: Regression**

Tamper a trace to replace `rule_execution.id` with a definition ID.

Validation/acceptance must fail.

- [ ] **Step 7: Commit**

```bash
git add \
  tests/domains/test_languages_domain_dp026_acceptance.py \
  tests/domains/test_languages_domain_trace.py

git diff --cached --check

git commit -m "test(domains): trace real languages rule executions"
```

If production code needs a small Languages-only adapter to expose already-existing rule runtime objects, make it explicit and keep it inside the 14 existing modules. No new production module.

---

# Task 4 — Add canonical runtime identity to PermissionGateResult

**PRE-AUTHORIZED SHARED CHANGE**

**Files:**
- Modify: `cmm/domains/permission_gate.py`
- Test: `tests/domains/test_domain_permission_gate.py`
- Modify connected test: `tests/domains/test_languages_domain_dp026_acceptance.py`

**Produces:**
- one actual runtime `decision_id` for every real gate evaluation.

## Why shared change is required

The real `DomainPermissionGate` is executed, but `PermissionGateResult` currently has no unique result identity.

The frozen trace requires an actual permission decision result ID.

A manually minted ID in a memory snapshot is not adequate provenance.

This shared extension is authorized in advance so the agent must not STOP for it.

## Backward-compatible contract

Add:

```python
decision_id: str | None = None
```

to `PermissionGateResult`.

Rules:

```text
direct construction may omit it for backward compatibility
DomainPermissionGate-produced results MUST always have a non-empty decision_id
from_dict old payload without decision_id -> valid, decision_id=None
new payload round-trip preserves decision_id
```

Do not reinterpret `request_id` as decision identity.

## DomainPermissionGate ID generation

Add an optional constructor dependency:

```python
id_factory: Callable[[], str] | None = None
```

Default:

```python
permission-gate-decision-<uuid>
```

Validate generated values as non-empty strings.

Every result returned from a gate evaluation must be stamped exactly once with a new ID.

This includes:

```text
ALLOW
DENY
APPROVAL_REQUIRED
APPROVAL_CONSUMED
APPROVAL_DENIED
workflow evaluation paths
operation evaluation paths
node evaluation paths
```

A pre-approval result and post-approval result for the same request must have **different decision IDs**.

The same request ID is not sufficient.

- [ ] **Step 1: RED shared contract tests**

Prove:
- real gate result has `decision_id`;
- two evaluations have different IDs;
- injected deterministic `id_factory` works;
- round trip preserves it;
- legacy payload without field still parses.

- [ ] **Step 2: Implement minimal field + ID factory**

No changes to:
- permission resolution;
- policy evaluation;
- approvals;
- scope;
- consumption;
- allowed/denied semantics;
- scheduling/operations.

- [ ] **Step 3: Full shared regression**

Run all:
- `test_domain_permission_gate*.py`;
- approval lifecycle;
- University/other domain consumers using the gate;
- Languages permission tests.

- [ ] **Step 4: Bind memory permission snapshot to real gate decision**

After the actual memory-write gate result is produced:

```python
assert consumed.decision_id is not None
```

Build `DomainMemoryPermissionDecisionSnapshot` with:

```python
decision_id=consumed.decision_id
allowed=consumed.allowed
```

The memory snapshot may translate shared permission semantics into memory capability `PROPOSE`, but **must reuse the real gate result identity**.

Delete the separately minted `permission_id`.

- [ ] **Step 5: Trace actual permission decision**

Use:

```text
consumed.decision_id -> PERMISSION_DECISION
```

If both pending and consumed decisions are relevant, trace both with their real IDs; at minimum the permission used for the persistence boundary must be real.

Keep:

```text
approval_request.id -> APPROVAL_REQUEST
approval_decision.id -> APPROVAL_DECISION
```

- [ ] **Step 6: Anti-cheat regression**

Assert:

```python
trace_permission_ids <= {
    gate_result.decision_id
    for gate_result in actual_gate_results
    if gate_result.decision_id is not None
}
```

and specifically:

```python
memory_permission.decision_id == consumed.decision_id
```

A random `self.ids()` value must not satisfy the test.

- [ ] **Step 7: Commit shared fix separately**

```bash
git add \
  cmm/domains/permission_gate.py \
  tests/domains/test_domain_permission_gate.py

git diff --cached --check

git commit -m "feat(domains): identify permission gate decisions"
```

Then commit Languages connected adaptation separately:

```bash
git add \
  tests/domains/test_languages_domain_dp026_acceptance.py

git diff --cached --check

git commit -m "test(domains): trace real permission decisions"
```

---

# Task 5 — Preserve actual selected LanguageLearningProfile mode in trace

**Files:**
- Modify: `tests/domains/test_languages_domain_dp026_acceptance.py`
- Test: `tests/domains/test_languages_domain_trace.py`
- Shared trace contract: NO CHANGE EXPECTED

## Design

The profile definition identity and selected runtime mode are different facts.

Keep:

```text
languages.profile -> PROFILE
```

for the actual profile definition.

Select one real runtime mode for the scenario:

```python
selected_profile_mode = "practice"
```

It must be used by at least one real pedagogical operation/workflow input where mode is applicable, not merely written into trace metadata after the fact.

Preserve it in:

```python
DomainTrace.metadata["selected_profile_mode"]
```

This is a scalar runtime state, not a fake trace reference ID.

- [ ] **Step 1: Select mode before workflow execution**

Store:

```python
self.state["selected_profile_mode"] = "practice"
```

Validate membership:

```python
assert mode in LANGUAGES_PEDAGOGICAL_MODES
```

- [ ] **Step 2: Feed selected mode into actual scenario behavior**

Where the current operation/workflow input supports a mode, pass the selected runtime value.

Do not add a new operation merely for trace.

- [ ] **Step 3: Add trace metadata**

Trace metadata must contain:

```python
{
    ...,
    "selected_profile_mode": selected_profile_mode,
}
```

- [ ] **Step 4: Trace test**

Require:

```python
assert trace.metadata["selected_profile_mode"] == scenario.state["selected_profile_mode"]
assert trace.metadata["selected_profile_mode"] in LANGUAGES_PEDAGOGICAL_MODES
```

Tampering with a different mode must fail the semantic acceptance assertion.

- [ ] **Step 5: Commit**

```bash
git add \
  tests/domains/test_languages_domain_dp026_acceptance.py \
  tests/domains/test_languages_domain_trace.py

git diff --cached --check

git commit -m "test(domains): preserve selected languages profile mode"
```

---

# Task 6 — Rebuild checkpoint 44 as a provenance ownership proof

**Files:**
- Modify: `tests/domains/test_languages_domain_dp026_acceptance.py`
- Test: `tests/domains/test_languages_domain_trace.py`

## Required provenance sources

Build the expected inventory **only from canonical runtime objects**.

The source of truth must be explicit:

```text
RESOLUTION_CONTEXT   -> DomainResolutionContext.id
RESOLUTION_RESULT    -> DomainResolution.id
COMPOSITION          -> DomainComposition.id
PROFILE              -> DomainProfileDefinition.id
RULE_PLAN            -> DomainRuleExecutionPlan.id
RULE_RESULT          -> DomainRuleExecutionResult.id
OPERATION_RESULT     -> actual operation helper/result IDs produced by execution
WORKFLOW_RUN          -> WorkflowRun.run_id
EVIDENCE              -> actual evidence/assessment IDs
PERMISSION_DECISION   -> PermissionGateResult.decision_id
APPROVAL_REQUEST      -> ApprovalRequest.id
APPROVAL_DECISION     -> ApprovalDecision.id
MEMORY_PROPOSAL       -> memory proposal.proposal_id
MEMORY_BINDING        -> memory binding.binding_id
CROSS_DOMAIN_RESULT   -> real cross-domain result ID
CROSS_DOMAIN_TRACE    -> real cross-domain trace ID
PRESENTATION_RESULT   -> actual presentation result ID
```

No other source may populate these kinds.

## Forbidden provenance

Explicitly reject:

```text
static rule definition ID as RULE_RESULT
WorkflowEvent.event_id as WORKFLOW_RESULT
random self.ids() as PERMISSION_DECISION
response text-derived IDs
trace.all_references() as expected inventory source
```

- [ ] **Step 1: Introduce ownership map**

Build:

```python
expected_id_to_kind: dict[str, DomainTraceReferenceKind]
```

and a second ownership map:

```python
expected_id_to_owner: dict[str, object]
```

The owner object must be the runtime object that actually owns that ID.

- [ ] **Step 2: Assert source identity before trace assembly**

Examples:

```python
assert expected_id_to_owner[rule_execution.id] is rule_execution
assert expected_id_to_owner[consumed.decision_id] is consumed
assert expected_id_to_owner[run.run_id] is run
```

For plain dict operation results, store an explicit `(result_mapping, id_field)` owner tuple.

- [ ] **Step 3: Assemble trace from the independently built inventory**

Only after expected maps are complete.

- [ ] **Step 4: Validate exact kind parity**

For every trace ref:

```python
assert ref.ref_id in expected_id_to_kind
assert ref.kind is expected_id_to_kind[ref.ref_id]
```

And:

```python
assert set(expected_id_to_kind) == {ref.ref_id for ref in trace.all_references()}
```

subject only to canonical structural refs that the trace assembler must add; if so, list them explicitly and independently.

- [ ] **Step 5: Validate frozen semantic categories**

Checkpoint 44 must assert:
- resolver provenance;
- workflow run provenance;
- operation-result provenance;
- evidence provenance;
- rule execution provenance;
- permission decision provenance;
- memory-proposal/binding provenance;
- selected profile mode;
- cross-domain result;
- presentation result.

- [ ] **Step 6: Negative mutation matrix**

Create copies/tampered inventory cases:

```text
RULE_RESULT -> static definition id
PERMISSION_DECISION -> random id
PROFILE mode -> unselected different mode
WORKFLOW_RUN -> event id
EVIDENCE -> operation id
MEMORY_PROPOSAL -> binding id
```

Each must fail.

- [ ] **Step 7: Keep exact 45 checkpoint sequence**

No new diagnostic checkpoint may replace a frozen semantic checkpoint.

Diagnostic assertions belong inside existing steps or separate tests.

Required:

```python
tuple(scenario.checkpoints) == FROZEN_SEMANTIC_CHECKPOINTS
len(scenario.checkpoints) == 45
```

- [ ] **Step 8: Commit**

```bash
git add \
  tests/domains/test_languages_domain_dp026_acceptance.py \
  tests/domains/test_languages_domain_trace.py

git diff --cached --check

git commit -m "fix(domains): close DP-026 runtime trace provenance"
```

---

# Task 7 — Same-root-cause semantic closure audit across all 15 operation helpers

**Files:**
- Test: `tests/domains/test_languages_domain_adversarial.py`
- Test: `tests/domains/test_languages_domain_operations.py`
- Modify: `cmm/domains/languages/operations.py` only for same-class defects proven RED

This task is specifically intended to prevent a V5 caused by another hard-coded positive state.

## Mandatory static inspection

For every public `*_result` helper:

1. List parameters.
2. Identify parameters that are evidence/state-bearing.
3. Identify:
   - hard-coded positive scores;
   - hard-coded mastery/progress/readiness counts;
   - hard-coded levels;
   - positive feedback defaults;
   - ignored evidence/state inputs;
   - finite-number coercions;
   - counts that may exceed totals.
4. Classify each as:
   - legitimate content-generation default;
   - harmless unused optional presentation input;
   - semantic defect requiring RED.

Do not refactor harmless generation functions just because a parameter is unused.

## Mandatory semantic matrix

### Assessment-like helpers

For:

```text
assess_sample_result
review_exercise_result
review_writing_result
review_speaking_result
review_errors_result
prepare_certification_result
generate_progress_review_result
track_vocabulary_result
update_level_evidence_result
```

A minimal/empty evidence case must not create unsupported:

```text
correctness
score
proficiency
mastery
stable progression
error pattern
certification readiness
positive evidence confidence
```

### Preventive `review_errors` case

Current source returns generic `"Fluency practice"` when no pattern exists.

Test:

```python
result = review_errors_result(observed_errors=())
```

It must not claim an evidence-derived targeted correction from zero errors.

Preferred output:

```text
recommended_focus = "not_assessed"
```

or another explicit non-evidence state.

If a generic optional practice suggestion is desired, it must be labeled as a generic suggestion, not as an evidence-derived error focus.

### Count invariants

For every count/summary:

```text
count >= 0
subset count <= total count
sum of mutually-exclusive state counts == total
```

### Strict JSON

Every one of the 15 result helpers must serialize under:

```python
json.dumps(result, allow_nan=False)
```

for:
- representative valid input;
- schema-valid minimal input;
- malformed numeric input where a numeric input exists.

### Input immutability

Pass mutable mapping/list inputs, deep-copy before call, assert unchanged after call.

### Deterministic semantic invariants

IDs may vary.

All non-ID semantic output for identical normalized input should be equal.

## No new architecture

If this sweep finds a same-root-cause bug inside existing Languages operation helpers, fix it with RED/GREEN in the existing `operations.py`.

If it requires a shared engine/interface change beyond Task 4, STOP.

- [ ] **Step 1: Run static audit and record findings**

Create a non-committed scratch note in `tmp/`.

- [ ] **Step 2: Add semantic matrix tests**

They must inspect actual payload, not only invariant flags.

- [ ] **Step 3: Fix only RED-proven same-class defects**

No unrelated feature expansion.

- [ ] **Step 4: Commit**

```bash
git add \
  cmm/domains/languages/operations.py \
  tests/domains/test_languages_domain_operations.py \
  tests/domains/test_languages_domain_adversarial.py

git diff --cached --check

git commit -m "test(domains): enforce languages operation semantic closure"
```

If no new production fix is needed, use:

```text
test(domains): enforce languages operation semantic closure
```

---

# Task 8 — Final code review as an adversary

Do not ask a reviewer merely “does this look good?”

Review specifically against all audit generations.

## V1 findings

Prove still closed:

```text
connected AT-DP-026
workflow invariant gates
certification authority
evidence provenance/comparability
progression baseline/comparability
temporal authority
real permission lifecycle
```

## V2 findings

Prove still closed:

```text
calendar request/shared boundary
trace typed kinds
progress output grounding
empty evidence fail-closed
NaN/Inf malformed scores
```

## V3 findings

Prove:

```text
runtime rule result identity
runtime permission decision identity
selected profile mode
missing exercise stays unknown
vocabulary mastery derives from state
```

## Mutation challenges

A reviewer must try to make tests pass while introducing:

```text
rule_id -> RULE_RESULT
random permission id
event_id -> WORKFLOW_RESULT
mastered > total_items
empty exercise -> True
empty writing -> A2
empty speaking -> positive fluency
empty progress -> improvement
stale official source wins
same provenance duplicated by caller IDs
calendar mutation inside Languages
```

Each should be caught by an existing test.

Record the review in:

```text
tmp/phase10-26-v3-final-review.md
```

Do not commit scratch review unless project conventions require it.

---

# Task 9 — Fresh verification from HEAD

Use `superpowers:verification-before-completion`.

No completion claim before every command below is freshly green.

## 1. Languages focused

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_*.py
```

## 2. Shared permission gate

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_permission_gate*.py
```

Include any additional approval lifecycle consumers identified by `rg`.

## 3. Shared rules

Run all rule contract/selection/execution tests.

## 4. Shared trace/workflow/composition/resolver

Run all relevant Domain trace, workflow, composition and resolver tests.

## 5. All domains

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains
```

## 6. Global

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q
```

## 7. Ruff

Run normal and Python 3.10 target over the entire modified file set.

## 8. compileall

Use isolated temporary pycache.

## 9. Fresh import

Assert importing Languages creates no registry side effects.

## 10. Canon

Assert:

```text
ENTITIES=16
RESOURCES=15
RULES=14
OPERATIONS=15
WORKFLOWS=9
MODULES=14
languages.progress_checkpoint exists
```

## 11. Paternidad

Diff Phase 10.27/Paternidad-sensitive files against the V3 starting HEAD.

No unintended change.

## 12. Direct final probes

Print explicit markers:

```text
EMPTY_EXERCISE_UNASSESSED=PASS
ANSWER_ONLY_EXERCISE_UNASSESSED=PASS
INVALID_EXERCISE_SCORE_UNASSESSED=PASS
EXPLICIT_WRONG_EXERCISE_ERROR=PASS

EMPTY_VOCAB_ZERO_MASTERY=PASS
VOCAB_MASTERY_WITHIN_TOTAL=PASS
VOCAB_REVIEW_RESULTS_CONSUMED=PASS
VOCAB_UNKNOWN_REVIEW_NO_INVENTION=PASS
VOCAB_PERSISTENCE_PROPOSAL_ONLY=PASS

RULE_RUNTIME_EXECUTION_ID=PASS
RULE_DEFINITION_ID_NOT_RESULT_ID=PASS
PERMISSION_GATE_DECISION_ID=PASS
PERMISSION_PRE_POST_IDS_DISTINCT=PASS
MEMORY_PERMISSION_ID_DERIVED_FROM_GATE=PASS
SELECTED_PROFILE_MODE_TRACED=PASS

TRACE_RUNTIME_OWNER_MAP=PASS
TRACE_RULE_RUNTIME_PROVENANCE=PASS
TRACE_PERMISSION_RUNTIME_PROVENANCE=PASS
TRACE_NO_EVENT_AS_WORKFLOW_RESULT=PASS
TRACE_REQUIRED_CATEGORIES=PASS

AT_DP_026_FROZEN_SEMANTIC_CHECKPOINTS=45
AT_DP_026_REAL_WORKFLOWS=9
AT_DP_026_CONNECTED=PASS

ALL_15_OPERATION_MINIMAL_SEMANTICS=PASS
ALL_15_OPERATION_STRICT_JSON=PASS
ALL_15_OPERATION_INPUT_IMMUTABILITY=PASS
```

## 13. Worktree

Expected final:

```text
tracked worktree clean
only pre-existing ?? tmp/
```

---

# Task 10 — Documentation after remediation

**Files:**
- Modify: `docs/reference/languages-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `ROADMAP.md` only if current roadmap convention requires it

Record truthfully:

```text
V3 independent audit: FAIL
V3 findings remediated: 1 BLOCKER + 2 MAJOR
candidate AT-DP-026: PASS
final independent closure audit: PENDING
DP-026: REQUIRES_PHASE_INSPECTION
```

Do not write:
- independently audited;
- closed;
- complete;
- integrated to main.

Commit:

```bash
git add \
  docs/reference/languages-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  ROADMAP.md

git diff --cached --check

git commit -m "docs(domains): record phase 10.26 V3 remediation"
```

Stage only files actually modified.

---

# Task 11 — Prepare final independent closure-audit bundle

Do this only after Task 9 is fresh green and Task 10 committed.

Bundle must contain:

```text
frozen spec
original plan
V1 audit
V1 remediation plan
V2 audit
V2 remediation plan
V3 audit
this definitive remediation plan
current docs
14 Languages modules
all Languages tests
shared rule contracts/executor/tests
shared permission gate + tests
shared trace contracts + tests
workflow/composition/resolver shared code/tests
fresh verification evidence
direct final probes
git diff 13c8d5d..HEAD
git diff 93c2679..HEAD
commit list
manifest
SHA256
```

Bundle name:

```text
phase-10-26-final-independent-closure-audit-bundle.tar.gz
```

Do not declare closure.

Final implementation status may only be:

```text
PHASE10_26_V3_REMEDIATION_STATUS:
READY_FOR_FINAL_INDEPENDENT_CLOSURE_AUDIT
```

---

# Expected commit sequence

```text
fix(domains): preserve unknown exercise outcomes
fix(domains): derive languages vocabulary mastery
test(domains): trace real languages rule executions
feat(domains): identify permission gate decisions
test(domains): trace real permission decisions
test(domains): preserve selected languages profile mode
fix(domains): close DP-026 runtime trace provenance
test(domains): enforce languages operation semantic closure
docs(domains): record phase 10.26 V3 remediation
```

Task boundaries may combine adjacent acceptance-test-only commits when inseparable, but:

```text
feat(domains): identify permission gate decisions
```

must remain an independent shared commit.

---

# Definitive Definition of Done

## V3 findings

```text
[ ] V3-B-001 closed with actual rule execution result ID
[ ] V3-B-001 closed with actual PermissionGateResult decision ID
[ ] V3-B-001 selected profile mode preserved
[ ] V3-M-001 empty exercise unassessed
[ ] V3-M-002 vocabulary mastery evidence-derived
```

## Same-class closure

```text
[ ] no empty assessment creates level/confidence
[ ] no empty exercise creates correctness/score
[ ] no empty writing creates positive evaluation
[ ] no empty speaking creates positive fluency/pronunciation
[ ] no empty error review creates evidence-derived correction focus
[ ] no empty vocabulary creates mastery
[ ] no empty certification profile creates readiness
[ ] no insufficient progress creates improvement
[ ] no count exceeds its total
[ ] no NaN/Inf survives public semantic output
[ ] all 15 helper outputs strict JSON-safe
[ ] all 15 helper inputs remain unmutated
```

## Trace ownership

```text
[ ] RULE_RESULT = DomainRuleExecutionResult.id
[ ] RULE_RESULT != static rule_id
[ ] PERMISSION_DECISION = PermissionGateResult.decision_id
[ ] memory permission snapshot reuses gate decision ID
[ ] WORKFLOW_RUN = WorkflowRun.run_id
[ ] no WorkflowEvent.event_id trace refs
[ ] EVIDENCE uses real evidence IDs
[ ] MEMORY_PROPOSAL uses real proposal ID
[ ] MEMORY_BINDING uses real binding ID
[ ] PRESENTATION_RESULT uses real presentation result ID
[ ] selected profile mode preserved
[ ] expected inventory built before trace assembly
[ ] owner map proves each runtime identity
```

## Frozen architecture

```text
[ ] 16/15/14/15/9
[ ] 14 modules
[ ] progress_checkpoint preserved
[ ] nine workflows real
[ ] resolver/composer real
[ ] PermissionGate/ApprovalService real
[ ] Paternidad unchanged
[ ] no Nil architecture
[ ] no push
[ ] no merge
[ ] no closure before final independent audit
```

If every box is fresh green:

```text
READY_FOR_FINAL_INDEPENDENT_CLOSURE_AUDIT
```

Anything less:

```text
NOT_READY
```
