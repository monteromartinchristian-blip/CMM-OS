# Phase 10.26 — Independent Audit V3

## Audit identity

- **Project:** CMM OS
- **Phase:** 10.26 — Languages Domain
- **Audit type:** independent V3 re-audit
- **Branch represented by bundle:** `feature/phase-10-domain-intelligence`
- **Candidate HEAD:** `13c8d5d705cd46d25028f55b217c0ec9bfcf6ec6`
- **V2 remediation baseline:** `a2833ea`
- **Bundle:** `phase-10-26-independent-v3-audit-bundle.tar.gz`
- **Observed SHA-256:** `b1c70355d71fb96b501305d0c2d163321905590cd9c37c08db9e9982c7e82ecf`
- **Checksum sidecar:** exact match
- **Repository modified by this audit:** NO
- **Push:** NO
- **Merge:** NO
- **Phase closure:** NO

# Verdict

```text
PHASE10_26_INDEPENDENT_AUDIT_V3=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0
CLOSURE=NO
```

The candidate is substantially stronger than both prior audited versions.

The V3 audit confirms that the V2 remediation genuinely fixes:

```text
V2-B-001 calendar mutation request / shared external boundary
V2-M-001 progress-review cross-skill fabrication
V2-M-002 named empty-evidence assessment/writing/speaking/certification cases
V2-M-003 malformed/non-finite exercise score handling
```

The trace remediation also fixes most of V2-B-002:

```text
real WorkflowRun.run_id references
no WorkflowEvent.event_id mislabeled as WORKFLOW_RESULT
typed EVIDENCE references
typed MEMORY_PROPOSAL references
typed MEMORY_BINDING references
typed PRESENTATION_RESULT references
presentation_result_ids shared carrier
independently assembled expected-id-to-kind map
```

However, V2-B-002 is **not fully closed** because the connected trace still uses identifiers that are not actual runtime result/decision IDs for some frozen categories.

The V3 source audit also found two residual semantic defects in operation result builders that the green suite does not detect.

---

# Bundle integrity and fresh evidence

## Integrity

Observed bundle checksum:

```text
b1c70355d71fb96b501305d0c2d163321905590cd9c37c08db9e9982c7e82ecf
```

The `.sha256` sidecar contains the same checksum.

Bundle manifest records:

```text
Branch: feature/phase-10-domain-intelligence
HEAD: 13c8d5d705cd46d25028f55b217c0ec9bfcf6ec6
V2 baseline: a2833ea
```

The bundle contains:

```text
frozen Phase 10.26 spec
original implementation plan
first independent audit
V2 independent audit
both remediation plans
current roadmap/reference documentation
14 Languages production modules
19 Languages test modules
shared Domain contracts
shared Workflow contracts
shared Permission/Approval contracts
shared trace contracts/tests
git diffs
remediation commit history
fresh verification evidence
```

## Fresh captured verification

The V3 bundle records:

```text
Languages focused                        165 passed
shared trace/workflow/permission         556 passed
all domains                             5820 passed
global suite                           11350 passed
Ruff                                      PASS
Ruff Python 3.10                          PASS
compileall                                PASS
fresh import                              PASS
canon                           16/15/14/15/9
Languages production modules                14
languages.progress_checkpoint              PASS
WorkflowEvent IDs in AT-DP-026                0
tracked worktree                          CLEAN
```

These results are credible regression evidence, but the V3 findings below are semantic gaps not asserted by those suites.

---

# Frozen canon

**PASS**

```text
domain:languages
Idiomas
LanguageLearningProfile

entities      16
resources     15
rules         14
operations    15
workflows      9
modules       14
```

`languages.progress_checkpoint` remains frozen.

No Phase 10.27 / Paternidad change is part of the V3 candidate.

---

# Authorized shared changes

## Typed DomainMetadata composer compatibility

Commit:

```text
b899502
```

**PASS**

The change remains narrow and does not alter scoring/ranking/primary/supporting semantics.

## Accumulated WorkflowRun outputs

Commits:

```text
8430794
8048abc
```

**PASS**

The adapter receives the accumulated output snapshot; scheduling/readiness/state semantics remain unchanged.

## Shared trace reference kinds

Commit:

```text
34d1d9b
```

Added:

```text
EVIDENCE
MEMORY_PROPOSAL
MEMORY_BINDING
PRESENTATION_RESULT
```

**PASS**

The additions are generic shared concepts, not Languages-specific kinds.

Ownership is correctly constrained:

```text
EVIDENCE            domain-owned
MEMORY_PROPOSAL     domain-owned
MEMORY_BINDING      domain-owned
PRESENTATION_RESULT global/shared
```

## Presentation result trace carrier

Commit:

```text
ec21c30
```

Added:

```text
DomainTraceReferences.presentation_result_ids
```

**PASS**

Normalization, serialization, deserialization, `all_references()` and backward compatibility are covered.

The V3 fresh-import probe confirms round-trip behavior.

---

# Disposition of V2 findings

| V2 finding | V3 disposition |
|---|---|
| V2-B-001 calendar external-action path absent | **RESOLVED** |
| V2-B-002 trace incomplete/mis-typed | **PARTIALLY RESOLVED — still BLOCKING** |
| V2-M-001 fabricated progress/cross-skill state | **RESOLVED** |
| V2-M-002 named empty-evidence helpers fabricated judgments | **RESOLVED for audited named cases** |
| V2-M-003 malformed/non-finite exercise score path | **RESOLVED** |

---

# Confirmed V3 improvements

## Exact frozen 45 semantic checkpoints

**PASS**

`tests/domains/test_languages_domain_dp026_acceptance.py` now defines the actual frozen semantic sequence, including:

```text
34 review schedule proposal
35 no calendar mutation
36 user calendar request
37 shared external/permission boundary
38 memory proposal
39 consent/permission
40 minimal Oppositions projection
41 no full learning-history export
42 presentation distinction
43 unassessed pronunciation gap
44 actual trace provenance
45 no parallel infrastructure
```

The test now checks:

```python
tuple(scenario.checkpoints) == FROZEN_SEMANTIC_CHECKPOINTS
```

Therefore an implementation-only diagnostic checkpoint can no longer replace a frozen semantic checkpoint while retaining a count of 45.

## Calendar boundary

**PASS**

The connected scenario now creates a user-requested calendar action with:

```text
PermissionCapability.SCHEDULE_MODIFY
```

and routes a shared external operation through the real:

```text
DomainPermissionResolver
DomainPermissionGate
```

The shared policy denies the operation and no calendar state is mutated.

For the frozen Languages requirement this is valid fail-closed behavior:

```text
review proposal != calendar mutation
Languages != direct schedule writer
```

The spec does not require Languages to obtain a successful schedule write; it requires the write request to leave the Languages domain and enter the shared authorization/external-action boundary.

## Progress payload semantics

**PASS**

`generate_progress_review_result()` no longer returns unconditional:

```text
writing=improving
reading=consolidated
active_patterns_count=1
readiness=in_progress
```

The output is now evidence-derived.

No-evidence cases remain insufficient, and writing-only evidence does not create unrelated reading progress.

## Empty assessment / writing / speaking / certification profile

**PASS for the V2 cases**

The V3 source confirms:

```text
empty assessment -> unknown / confidence 0 / no strengths
empty writing -> unknown / score 0 / no strengths
empty speaking -> fluency 0 / pronunciation unassessed
absent certification profile -> no invented readiness/gaps
```

The additional pronunciation-evidence fix (`73a9086`) also rejects non-empty but unusable pronunciation evidence.

## Malformed exercise numerics

**PASS**

NaN, ±Inf, booleans, malformed strings/objects and other invalid score values are normalized through a finite-number boundary and no longer escape into strict JSON or raise the previously audited accidental coercion errors.

---

# V3-B-001 — BLOCKER
# Connected trace still does not use actual runtime IDs for every frozen result/decision category

## Frozen requirement

The frozen design states:

```text
Trace must reference actual runtime result IDs.
Do not fabricate semantic-looking IDs from response text.
```

Required trace tests include:

```text
selected primary/supporting domains
profile mode
actual operation/workflow result IDs
evidence refs
proficiency kind
skill scope
rule decisions
permission decisions
memory proposal state
cross-domain result refs
```

Frozen AT-DP-026 checkpoint 44 requires:

```text
actual resolver, workflow, operation, evidence,
rule, permission, and memory-proposal result IDs
```

## A. Static rule IDs are labeled as RULE_RESULT

Current connected acceptance:

```python
for result in selected_rule_results:
    expect(result.rule_id, DomainTraceReferenceKind.RULE_RESULT)
```

The values inserted as `RULE_RESULT` are therefore canonical rule definition IDs such as:

```text
languages.error_pattern_evidence
languages.progression_evidence
languages.certification_temporal
```

They are **not unique runtime result IDs**.

### Why this is semantically wrong

The selected rules are currently executed directly:

```python
rules[rule_id].evaluate(context)
```

The resulting `DomainRuleResult` contains the static:

```text
rule_id
rule_name
rule_version
...
```

but no unique execution-result identifier.

The shared Domain Rule infrastructure already has a canonical runtime carrier:

```python
DomainRuleExecutionResult
```

with:

```python
id: str
plan_id: str
rule_results: tuple[ReasoningRuleResult, ...]
```

and `DefaultDomainRuleExecutor` creates a fresh:

```python
execution_id = self._id()
```

before returning `DomainRuleExecutionResult(id=execution_id, ...)`.

Therefore:

```text
rule definition identity
!=
runtime rule-execution result identity
```

The trace currently labels the former as the latter.

This is the same semantic class of defect as the V2 `WorkflowEvent.event_id -> WORKFLOW_RESULT` mislabel, although the workflow side is now correctly fixed.

## B. Profile mode is still not present as a selected runtime trace fact

The trace contains:

```text
PROFILE -> languages.profile
```

but the profile object contains only the allowed-mode catalog:

```text
teach
practice
assess
review
certification
immersion
```

The connected scenario never establishes and traces a concrete **selected** `LanguageLearningProfile` mode.

The frozen required trace tests explicitly require:

```text
profile mode
```

A reference to the profile definition is not equivalent to the runtime selected mode.

## C. Permission decision provenance is still manually minted for the traced memory permission

The connected scenario does execute a real `DomainPermissionGate + ApprovalService` lifecycle for `MEMORY_WRITE`.

However, the object traced as:

```text
PERMISSION_DECISION
```

is separately created:

```python
permission_id = self.ids()

memory_permission = DomainMemoryPermissionDecisionSnapshot(
    decision_id=permission_id,
    allowed=True,
    capabilities=(DomainMemoryCapability.PROPOSE,),
    ...
)
```

The trace then records:

```python
permission_decision.decision_id
```

This identifier is not emitted by `DomainPermissionGate`.

The real `PermissionGateResult` currently has no runtime `decision_id`.

The snapshot is a valid memory-contract object, but in this acceptance it is a newly minted declaration of permission state rather than a typed projection of a concrete shared gate decision.

Therefore the trace does not yet prove the frozen requirement:

```text
actual permission result ID
```

## Why the expected-kind map does not close this gap

The V3 acceptance now does something materially better:

```python
expected_id_to_kind
```

is built before trace assembly and compared exactly against the resulting trace.

That closes the previous self-inventory weakness.

But it cannot prove semantic provenance when the independent map itself is seeded with:

```text
static rule definition IDs as RULE_RESULT
manually minted permission snapshot ID as PERMISSION_DECISION
```

Kind parity is correct **relative to the chosen map**, but the map does not yet contain the canonical runtime result identities required by the frozen spec.

## Severity

**BLOCKER**

This is the only remaining blocker because AT-DP-026 is the formal closure acceptance for Phase 10.26 and checkpoint 44 is explicitly part of the frozen scenario.

The majority of the connected path is now genuine; this finding is narrowly about final trace provenance.

## Required remediation

Do not fabricate replacements.

### Rule results

Use the canonical shared Domain Rule execution path and trace a real runtime result identity.

Preferred direction:

```text
DomainRuleExecutionPlan
→ DefaultDomainRuleExecutor
→ DomainRuleExecutionResult.id
```

If `RULE_RESULT` is intended to reference a different per-rule runtime object and the shared contracts lack a usable ID, STOP and request the smallest shared-contract decision.

Do not use `rule_id` as `RULE_RESULT`.

### Profile mode

Select an actual pedagogical mode for the connected scenario and preserve that selected runtime state in the trace using an existing semantically correct shared carrier/metadata path.

If the shared trace contract cannot faithfully represent selected profile mode, STOP rather than adding a Languages-only workaround.

### Permission decision

Do not mint an arbitrary `decision_id` and present it as provenance from the gate.

Either:

- use a canonical existing bridge from the real permission result into a traceable permission decision; or
- if the shared PermissionGate contract genuinely has no traceable result identity, STOP for a minimal shared-contract decision.

The existing real approval request/decision IDs must remain real.

## Required regression

The connected trace test should fail if:

```text
RULE_RESULT ref == static rule definition ID

or

PERMISSION_DECISION ref was not derived from an actual authorization decision path

or

selected profile mode is absent
```

---

# V3-M-001 — MAJOR
# `review_exercise_result()` treats missing exercise evidence as a perfect correct result

## Production source

`cmm/domains/languages/operations.py`

Current logic:

```python
er = dict(exercise_result or {})
is_correct = er.get("is_correct", True) is True

if "score" not in er:
    score = 1.0 if is_correct else 0.0
```

and:

```python
"feedback": "Great job!" if is_correct else ...
"difficulty_adjustment": "maintain" if is_correct else ...
```

## Input contract

The declared operation input requires:

```text
exercise_result: object
```

but does not require any inner outcome field.

Therefore:

```python
exercise_result={}
```

is a structurally valid minimal object at the operation boundary.

## Independent exact-source reproduction

The V3 auditor extracted and executed the exact bundled `_finite_number()` and `review_exercise_result()` functions.

Input:

```python
review_exercise_result(exercise_result={})
```

Actual result:

```text
is_correct=True
score=1.0
feedback="Great job!"
difficulty_adjustment="maintain"
observed_errors=[]
```

The same occurs with:

```python
review_exercise_result()
```

## Why this matters

Missing evidence becomes the strongest possible positive exercise outcome.

That violates the Phase 10.26 evidence discipline:

```text
absent / malformed / insufficient evidence
must not increase certainty
```

and the operation's stated purpose:

```text
Review a concrete exercise result.
```

No concrete result was provided.

## Why the current suite misses it

The V2 numeric tests correctly prove:

```text
explicit malformed score -> score 0 / is_correct False
```

but they do not test **missing outcome fields**.

The adversarial minimal-output matrix calls:

```python
review_exercise_result()
```

but checks only:

```text
strict JSON serialization
output schema parity
```

It does not inspect semantic correctness.

Thus the exact false-positive result is currently part of the green minimal-output test set.

## Required remediation

Missing exercise outcome must remain unknown/not-assessed, not automatically correct or incorrect.

Preferred semantic shape:

```text
score -> neutral/unknown according to schema
correctness -> unknown/not_assessed
feedback -> insufficient evidence / not assessed
observed_errors -> []
difficulty adjustment -> none/hold/not_assessed
stable proficiency unchanged
pattern unchanged
```

If the current output schema cannot represent unknown correctness faithfully, narrow the output contract rather than encoding unknown as `True`.

## Required tests

At minimum:

```text
exercise_result={}
exercise_result={"user_answer":"..."}
exercise_result missing is_correct
exercise_result missing score
```

must prove that absence does not produce:

```text
is_correct=True
score=1.0
Great job!
```

---

# V3-M-002 — MAJOR
# `track_vocabulary_result()` contains a hard-coded impossible mastery state and ignores review evidence

## Production source

`cmm/domains/languages/operations.py`

Current return includes:

```python
"total_items": len(items),
...
"mastery_summary": {
    "mastered": 5,
    "learning": len(items),
},
```

The `mastered` count is the constant `5`.

The public parameter:

```python
review_results
```

is not used to derive mastery or candidate state changes.

## Independent exact-source reproduction

The V3 auditor executed the exact bundled helper with its exact normalization and spaced-review helper dependencies.

### No vocabulary

Input:

```python
track_vocabulary_result()
```

Actual:

```text
total_items=0
due_items=0
mastery_summary={
    "mastered": 5,
    "learning": 0
}
candidate_updates=[]
```

### Explicit empty vocabulary list

Input:

```python
track_vocabulary_result(
    vocabulary_list={"items":[]}
)
```

Actual:

```text
total_items=0
mastered=5
learning=0
```

### One vocabulary item

Input:

```python
{"items":[{"id":"v1","term":"x"}]}
```

Actual:

```text
total_items=1
mastered=5
learning=1
```

The summary is impossible in every case.

## Frozen requirement

`languages.track_vocabulary` exists to:

```text
Manage authorized vocabulary learning state.
```

Possible states include:

```text
new
learning
review
consolidated
needs_reinforcement
```

The implementation plan requires:

```text
Produces candidate review-state changes;
does not persist them.
```

and globally forbids:

```text
placeholders
fake implementations
deferred frozen requirements
```

A constant `mastered=5` is not a candidate learning-state calculation.

## Why the current suite misses it

The adversarial tests already call:

```python
track_vocabulary_result(vocabulary_list={"items": ()})
```

and:

```python
track_vocabulary_result()
```

but only assert JSON safety/schema shape.

There is no semantic assertion such as:

```text
mastered <= total_items
mastered + learning <= total_items
no items -> mastered=0
```

## Required remediation

Derive vocabulary state only from actual item/review evidence.

At minimum:

```text
empty items -> mastered=0, learning=0
```

For non-empty items, calculate counts from canonical item/review state.

`review_results` must either:

- participate in candidate state derivation; or
- be removed from the public helper/input contract if the frozen semantics truly do not use it.

Do not leave a declared runtime input silently ignored while outputting fabricated state.

No persistence should be added.

## Required tests

```text
0 items -> 0 mastered
1 learning item -> 0 mastered / 1 learning
1 consolidated item -> grounded mastered/consolidated count
review evidence changes candidate state only when evidence supports it
mastered <= total_items
candidate updates remain proposal-only
persistence_applied=False
```

---

# Trace / memory note

The V3 audit is **not** opening a separate memory architecture finding.

The shared memory contracts intentionally use reference-only permission snapshots and proposal bindings.

The remaining issue is narrower:

```text
a trace labeled PERMISSION_DECISION must point to a semantically grounded
runtime authorization decision, not merely an independently minted snapshot ID.
```

This is included under V3-B-001 because it is a trace-provenance defect.

---

# Calendar decision note

The calendar shared boundary returning `DENY` is **not a finding**.

The frozen Languages invariant is:

```text
review scheduling proposal != calendar mutation
```

and the permission section requires:

```text
calendar write -> not directly authorized by Languages
```

The connected scenario now sends `SCHEDULE_MODIFY` through the shared gate and proves no mutation.

A successful calendar mutation belongs to a separately authorized shared external-action path, not to the Languages domain acceptance itself.

---

# V3 regression quality finding

The V3 suite is strong structurally, but the two MAJOR findings show a residual testing pattern:

```text
JSON-safe + schema-valid
!=
semantically valid
```

The final remediation should add generic payload invariants to the minimal-output matrix.

Recommended:

```text
review_exercise:
  missing outcome cannot become positive correctness

vocabulary:
  mastered <= total_items
  learning <= total_items
  no impossible state totals
```

The trace suite should likewise validate **semantic ownership of the ID**, not only equality to a pre-built `expected_id_to_kind` map.

---

# Documentation status

Current pre-V3 documentation correctly does not claim independent closure.

Because this V3 audit fails, Phase 10.26 must remain:

```text
implemented
V2 remediation completed
independent V3 audit FAIL
DP-026 = REQUIRES_PHASE_INSPECTION
closure = NO
```

Do not mark `AT-DP-026` independently audited until V3-B-001 is remediated and re-audited.

---

# Final V3 disposition

## Passed

```text
bundle integrity
canon 16/15/14/15/9
14-module package boundary
Languages focused regression suite
shared trace/workflow/permission regression suite
all-domain suite
global suite
Ruff
Ruff py310
compileall
fresh import
typed DomainMetadata shared fix
accumulated WorkflowRun outputs shared fix
trace EVIDENCE kind
trace MEMORY_PROPOSAL kind
trace MEMORY_BINDING kind
trace PRESENTATION_RESULT kind
presentation_result_ids carrier
exact frozen 45 checkpoint sequence
real calendar request/shared boundary
real resolver/composer
all 9 real Languages workflows
real accumulated run.outputs
real ApprovalService one-shot lifecycle
progress review evidence grounding
empty assessment fail-closed
empty writing fail-closed
empty speaking fail-closed
empty certification profile fail-closed
unusable pronunciation evidence fail-closed
NaN/Inf/malformed exercise score fail-closed
minimal cross-domain projection structure
WorkflowEvent IDs absent from trace
Paternidad non-regression
```

## Not passed

```text
V3-B-001  actual runtime trace provenance for rule/permission/profile-mode
V3-M-001  missing exercise outcome becomes perfect/correct
V3-M-002  vocabulary mastery is hard-coded/impossible
```

# Verdict markers

```text
PHASE10_26_INDEPENDENT_AUDIT_V3=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0

V2_B001_CALENDAR=RESOLVED
V2_B002_TRACE=PARTIALLY_RESOLVED_STILL_BLOCKING
V2_M001_PROGRESS=RESOLVED
V2_M002_NAMED_EMPTY_EVIDENCE=RESOLVED
V2_M003_NUMERIC_FAIL_CLOSED=RESOLVED

AUTHORIZED_SHARED_COMPOSITION_FIX=PASS
AUTHORIZED_SHARED_WORKFLOW_FIX=PASS
AUTHORIZED_SHARED_TRACE_KINDS=PASS
AUTHORIZED_PRESENTATION_RESULT_CARRIER=PASS

FROZEN_CHECKPOINTS=45_PASS
REAL_WORKFLOWS=9_PASS
WORKFLOW_EVENT_TRACE_IDS=0_PASS

CANON=16_15_14_15_9
PACKAGE_BOUNDARY=14_PASS
GLOBAL_TEST_EVIDENCE=11350_PASS
PARENTHOOD_REGRESSION=PASS

REPO_MODIFIED=NO
PUSH=NO
MERGE=NO
CLOSURE=NO
NEXT_GATE=FOCUSED_V3_REMEDIATION_AND_FINAL_REAUDIT
```
