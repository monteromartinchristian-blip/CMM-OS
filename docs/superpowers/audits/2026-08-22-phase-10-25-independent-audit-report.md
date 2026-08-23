# Phase 10.25 — Concerns Domain — Independent Audit Report

**Date:** 2026-08-22
**Auditor:** ChatGPT — independent snapshot review
**Audit mode:** Read-only; no production code or tests modified
**Bundle SHA-256:** `f725311bc4c732a1b46ef899499e55b883807d7742fcfb6dc0e1b7a33d8b811c`
**Branch recorded in bundle:** `feature/phase-10-domain-intelligence`
**HEAD recorded in bundle:** `7a4cabaa505b768574430d7a35ec2019dad5128b` (`7a4caba`)
**Implementation base:** `aebf0ec7e1e2e24c7ebc68d341aceb27ec66fb83` (`aebf0ec`)

## Verdict

```text
AUDIT_VERDICT: FAIL — remediation required
INDEPENDENT_AUDIT_STATUS: NOT_READY_TO_CLOSE
```

The Phase 10.25 package is structurally mature and several important invariants are correctly implemented. However, the independent audit found multiple behavioral and contract-level defects in core Concerns semantics. Four are closure blockers because they directly undermine reassurance, workflow safety, operation executability, or the canonical AT-DP-025 acceptance proof.

Implementation-side green test results are not disputed; the problem is that several final tests do not prove the frozen requirement they are named after.

---

# Positive findings

The snapshot independently confirms:

- exactly 14 production Python modules under `cmm/domains/concerns/`;
- exactly 17 canonical entities;
- exactly 10 canonical resources;
- exactly 14 canonical rule IDs and 14 canonical rule names;
- exactly 13 canonical operations;
- exactly 8 canonical workflows;
- canonical profile identity `ConcernSupportProfile`;
- no obsolete canonical `ReassuranceLoopRule`, `ConcernFactScenarioRule`, `concerns.structure_concern`, `concerns.separate_fact_scenario`, or `concerns.generate_monitoring_plan`;
- no custom Concerns planner, Agent Runtime, workflow engine, memory store, Knowledge Store/Graph, question engine, confidence engine, or conversation engine;
- `compileall` succeeds on the Concerns package;
- the uploaded archive hash exactly matches the locally reported SHA-256;
- no trailing whitespace exists in added lines of `AUDIT_CHANGESET.patch`;
- the strict literal-`True` permission helper is implemented correctly;
- memory integration is proposal-only and uses shared binding/validation contracts;
- recurrence outputs consistently avoid psychiatric labels;
- Relationships fact/interpretation separation is preserved at the Concerns boundary.

---

# BLOCKER findings

## B-001 — Reassurance evidence polarity is not target-aware and can invert benign evidence

**Severity:** BLOCKER

**Files:**
- `cmm/domains/concerns/rules.py:589-637`
- `cmm/domains/concerns/rules.py:640-755`
- especially `681-696`, `710-730`

**Frozen requirement violated:**
- `EvidenceCalibratedReassuranceRule` must evaluate available facts, source quality, counterevidence, uncertainty, base plausibility, domain-specific evidence, temporal relevance and material negative signals.
- Reassurance must reflect evidence relative to the feared interpretation / actual concern.
- Duplicate evidence must not inflate certainty.

**Problem:**

The evaluator determines direction merely from whether a record contains `supports` or `against`:

```python
pro_concern = [
    item for item in (*supporting, *countering)
    if item["grounding"] and item["supports"] is not None
]

pro_reassurance = [
    item for item in (*supporting, *countering)
    if item["grounding"]
    and item["against"] is not None
    and item["supports"] is None
]
```

It does not identify the proposition being assessed. A record that **supports a benign explanation** is treated as evidence **for concern** merely because it uses the `supports` field.

The evaluator also does not implement the frozen dimensions `source quality`, `base plausibility`, or `temporal relevance`.

Duplicate collapse uses `(identity, grounding)`. Therefore the same grounding/provenance can be counted twice under two different IDs.

**Independent reproduction:**

```text
evaluate_reassurance(
  evidence=(
    {"identity":"e1","supports":"benign explanation","grounding":"source:1"},
    {"identity":"e2","supports":"benign explanation","grounding":"source:2"},
  )
)

=> assessment = CONCERN_SUPPORTED
```

This is the opposite of the evidence meaning.

Second reproduction:

```text
one grounded record against feared reading
=> REASSURANCE_PARTIAL

same grounding repeated under two different identity values
=> REASSURANCE_SUPPORTED
duplicate_count = 0
```

So re-labeling one source can cross the reassurance threshold.

**Why tests did not catch it:**

`tests/domains/test_concerns_domain_reassurance.py:129-170` largely assumes that every `supports` record supports the feared meaning and every `against` record opposes it.

The duplicate test at `232-254` starts from a case already containing other strong counterevidence and therefore does not test the threshold-crossing case where one provenance is duplicated under distinct IDs.

No test proves target-relative claim polarity, source quality, base plausibility, or temporal relevance.

**Smallest safe remediation:**

1. Make reassurance evidence explicitly target-relative:
   - pass a canonical `target_claim` / `feared_claim`, or
   - require an explicit stance such as `supports_target` / `opposes_target`.
2. Never infer stance solely from the verb/key `supports` or `against`.
3. Deduplicate by provenance/source identity plus substantive claim/stance, not caller-controlled record ID.
4. Incorporate the frozen evidence dimensions, at least as explicit structured inputs with fail-closed handling.

**Required regression tests:**

```text
test_benign_explanation_support_is_not_concern_evidence
test_reassurance_stance_is_relative_to_target_claim
test_same_provenance_with_different_record_ids_does_not_inflate
test_source_quality_can_limit_reassurance
test_temporally_stale_evidence_cannot_upgrade_reassurance
test_base_plausibility_is_preserved_not_invented
```

---

## B-002 — `concerns.evaluate_reassurance` declares an output schema incompatible with its canonical helper

**Severity:** BLOCKER

**Files:**
- `cmm/domains/concerns/operations.py:228-230`
- `cmm/domains/concerns/operations.py:470-498`

**Frozen requirement violated:**
- the 13 operations must be real shared `DomainOperationDefinition` contracts;
- helper parity must ensure operation semantics and canonical rule semantics agree;
- injected real implementations must be executable through the shared runtime;
- strict schemas must validate real operation output.

**Problem:**

The operation declares:

```python
"concerns.evaluate_reassurance": _schema(
    ("assessment",),
    {"reassurance": _REASSURANCE_PAYLOAD},
)
```

The schema therefore:
- requires top-level `assessment`;
- does **not** define an `assessment` property;
- permits only `reassurance` because `_schema` sets `additionalProperties=False`.

The canonical helper returns a flat record:

```python
{
    "assessment": ...,
    "supporting": ...,
    "counterevidence": ...,
    "remaining_uncertainty": ...,
    ...
    "false_reassurance_detected": ...,
    "corrected_assessment": ...,
}
```

**Independent reproduction using the repository's own `validate_operation_schema`:**

A helper-shaped reassurance result against the declared schema produces:

```text
$.assessment additional_property
$.supporting additional_property
$.counterevidence additional_property
$.remaining_uncertainty additional_property
$.acknowledged_concerns additional_property
$.material_concern additional_property
$.absolute_certainty additional_property
$.false_reassurance_detected additional_property
$.corrected_assessment additional_property
```

So an injected implementation returning the canonical helper output can be rejected by the runtime.

**Why tests did not catch it:**

`tests/domains/test_concerns_domain_operations.py` checks that schemas are structured objects and checks semantic helper parity, but never validates **the actual helper output against its operation output schema**.

**Smallest safe remediation:**

Choose one contract and make every layer use it:

Option A:
- keep flat helper output;
- declare every canonical flat field in the output schema.

Option B:
- make operation output `{ "assessment": ..., "reassurance": {...} }`;
- adapt the helper and every workflow/presentation consumer consistently.

Do not maintain two shapes.

**Required regression test:**

```python
def test_evaluate_reassurance_helper_output_satisfies_declared_operation_schema():
    op = ...
    output = evaluate_reassurance_result(...)
    assert validate_operation_schema(output, op.output_schema) == ()
```

Also run the same schema-parity test for all 13 canonical operation helpers.

---

## B-003 — Several workflow safety gates are metadata-only/inert because condition fields do not match producer outputs

**Severity:** BLOCKER

**Files:**
- `cmm/domains/concerns/workflows.py:104-147`
- `cmm/domains/concerns/workflows.py:150-198`
- `cmm/domains/concerns/workflows.py:300-338`
- `cmm/domains/concerns/workflows.py:347-393`
- shared engine: `cmm/workflows/engine.py:107-164`
- operation outputs: `cmm/domains/concerns/operations.py:470-498`, `525-559`, `600-657`

**Frozen requirement violated:**
- missing/malformed/conflicting validation evidence must fail closed;
- workflow gates must have real dependencies;
- no false reassurance, catastrophic escalation, ritual questioning, external execution, or semantic promotion may be masked by static defaults.

**Shared-engine semantics:**

The engine starts validation state from workflow metadata, then only direct dependency outputs can override condition fields:

```python
state = dict(self._definition.metadata or {})

for dep_id in node.dependencies:
    dep_output = outputs.get(dep_id)
    ...
    if field in condition:
        observed[field].append(value)

# runtime values override static metadata only if observed
```

Concerns workflow metadata pre-populates safety conditions with safe values:

```python
"external_action_executed": False,
"false_reassurance": False,
"catastrophic_escalation_present": False,
"ritual_questioning_allowed": False,
...
```

This is safe only if the real producer emits **the exact same condition field** and is a declared dependency. Several do not.

### B-003a — false reassurance gate

Workflow:

```python
honesty_gate
dependencies=("reassurance",)
wait_condition={"false_reassurance": False}
```

Canonical helper emits:

```text
false_reassurance_detected
```

not `false_reassurance`.

The operation output schema does not permit `false_reassurance` either.

Therefore the runtime sees no producer value and accepts static metadata `False`.

### B-003b — catastrophic escalation gate

`proportionality_gate` waits on:

```text
catastrophic_escalation_present = False
```

but depends only on `honesty_gate`, whose output is merely:

```text
{"validated": True}
```

No direct dependency can emit `catastrophic_escalation_present`.

### B-003c — material-question gate

`material_question_gate` waits on:

```text
ritual_questioning_allowed = False
```

but `identify_open_questions_result()` emits:

```text
ritual_questions_suppressed
```

not `ritual_questioning_allowed`.

### B-003d — no-execution gate

`no_execution_gate` waits on:

```text
external_action_executed = False
```

but depends only on `agency_gate`, not on the `next_step` producer that emits `external_action_executed`.

**Independent shared-engine reproduction:**

Using the repository's actual WorkflowEngine semantics:

```text
metadata false_reassurance=False
dependency output false_reassurance_detected=True
gate expects false_reassurance=False

=> workflow gate COMPLETES
```

Likewise:

```text
metadata ritual_questioning_allowed=False
dependency output ritual_questions_suppressed=0

=> workflow gate COMPLETES
```

When the producer emits the correctly named violation:

```text
false_reassurance=True
=> gate FAILS with validate.condition_false
```

The engine itself is working correctly; the Concerns graph/contract is mismatched.

**Why tests did not catch it:**

The test named:

```text
test_reassurance_review_blocks_false_reassurance_gate_violation
```

at `tests/domains/test_concerns_domain_workflows.py:183-189` actually passes:

```python
{"concerns.evaluate_reassurance": {"false_reassurance": False}}
```

and asserts completion. It never supplies a violation.

The practical problem-solving test verifies `decision_adopted=True` blocks, but never verifies `external_action_executed=True` from `next_step` blocks.

The final tests also use a custom adapter that may key operation outputs by operation ID or node ID; this helped expose the shared-engine contract during implementation but the final test matrix does not prove all real producer→gate links.

**Smallest safe remediation:**

For every `VALIDATE` node:

1. identify the exact producer field;
2. make that field part of the producer's declared output schema;
3. declare the actual producing node as a direct dependency;
4. remove static metadata defaults for runtime-derived safety evidence, so absence yields `validate.condition_unknown`;
5. retain metadata defaults only for genuine immutable workflow policy, never evidence.

**Required regression tests:**

```text
test_reassurance_workflow_blocks_actual_false_reassurance_helper_output
test_reassurance_workflow_fails_closed_when_false_reassurance_field_missing
test_reassurance_workflow_blocks_catastrophic_escalation_from_actual_producer
test_open_concern_workflow_fails_closed_when_question_materiality_evidence_missing
test_practical_problem_solving_blocks_external_action_from_next_step_output
test_every_validate_condition_has_a_direct_dependency_schema_property
```

The final test should statically reconcile every condition field against at least one direct dependency output schema.

---

## B-004 — `AT-DP-025 — PASS` is not an end-to-end acceptance proof

**Severity:** BLOCKER

**File:**
- `tests/domains/test_concerns_domain_dp025_acceptance.py:48-380`

**Frozen requirement violated:**
- spec §115: **“AT-DP-025 minimum end-to-end scenario”**;
- the acceptance sequence must include Resolver selection with Concerns + supporting domain and culminate in a trace of the actual semantic states.

**Problem:**

`_Scenario` is a sequence of mostly disconnected direct helper calls.

Examples:

- Steps 1–2 comment states that resolution is “proven elsewhere”; no Resolver/composition is executed.
- Step 7 proves only `ready_for_substantive_response=True`; it does not produce a substantive response/result.
- Step 8 separately tests a material and immaterial question but does not drive the prior conversation state.
- Steps 9–10 create new information, but Step 12 does not consume that result; it creates a new hand-built evidence set.
- Step 12 partial reassurance is therefore not a reassessment of the prior scenario state.
- Step 25 creates symbolic reference IDs such as:
  - `support-need:PERSPECTIVE`
  - `evidence:msg:1`
  - `uncertainty:intent`
  - `rule:reassurance`
  rather than tracing actual IDs/results produced by earlier steps.
- No supporting domain participates in the assembled trace.

The test checks a narrative ordering in Python methods, not one connected end-to-end execution.

**Why tests did not catch it:**

The acceptance test itself is the weakened proof. Its module docstring labels the sequence as AT-DP-025 evidence, but individual steps are not state-linked.

**Smallest safe remediation:**

Build one connected acceptance harness using public shared contracts:

```text
request
→ Resolver (Concerns + supporting domain)
→ authorized domain_result projection
→ Concerns workflow / operation implementations
→ semantic outputs carried forward
→ recurrence on prior output/evidence
→ action proposal
→ memory proposal state
→ trace assembled using actual IDs/results
```

It may use deterministic test adapters; it does not need an LLM. But every step must consume the prior scenario state.

**Required regression test:**

```text
test_at_dp025_executes_connected_resolver_workflow_and_trace_sequence
```

The test must assert that Step 25 references IDs created by the actual prior steps and records the actual supporting domain.

Until this exists, `AT-DP-025 — PASS` is implementation-side partial evidence, not independent acceptance.

---

# IMPORTANT findings

## I-001 — SupportNeed lower-precedence signals override explicit current intent by forcing `MIXED`

**Severity:** IMPORTANT

**File:**
- `cmm/domains/concerns/rules.py:1493-1622`

**Frozen requirement violated:**

```text
explicit current request
>
clear current conversational signal
>
recent session context
>
historical preference
>
default heuristic
```

**Problem:**

The implementation appends components from explicit request, current signal and session context into one list and returns `MIXED` whenever more than one distinct component exists.

Thus lower-priority evidence can modify an explicit request.

**Independent reproductions:**

```text
explicit_request = "Can you reassure me"
current_signal    = "Tell me what you think"

=> support_need = MIXED
   components = (REASSURANCE, PERSPECTIVE)
```

More seriously:

```text
explicit_request = "No advice, I just need to talk"
current_signal    = "What can I do?"

=> support_need = MIXED
   problem_solving_allowed = True
```

This directly violates the intended explicit-current-request precedence.

**Why tests did not catch it:**

`tests/domains/test_concerns_domain_support_need.py` verifies explicit request beats **historical preference**, but not explicit request vs current signal or session context.

**Smallest safe remediation:**

Resolve one precedence tier at a time.

`MIXED` may be returned when **the highest-precedence source itself** clearly contains multiple concurrent needs, but lower-precedence sources must not add components once a higher-precedence tier is usable.

**Regression tests:**

```text
test_explicit_reassurance_beats_conflicting_current_signal
test_explicit_no_advice_beats_problem_solving_current_signal
test_explicit_request_beats_conflicting_session_context
test_mixed_is_allowed_only_within_highest_precedence_source
```

---

## I-002 — Same-question recurrence fabricates the required “pursuit of impossible certainty” dimension

**Severity:** IMPORTANT

**Files:**
- `cmm/domains/concerns/rules.py:1143-1198`
- weakened test: `tests/domains/test_concerns_domain_recurrence.py:105-127`

**Frozen requirement violated:**

A repetitive certainty pattern requires all independent grounded dimensions:

```text
same unresolved question
+ same evidence state
+ repeated pursuit of impossible certainty
+ temporary relief followed by renewed checking
+ multiple turns
```

**Problem:**

The implementation marks impossible-certainty pursuit when:

```python
pursuing_certainty is True
OR impossible_certainty is True
OR same_question is True
```

So the `same_question` dimension manufactures the separate `impossible_certainty_pursuit` dimension.

**Independent reproduction:**

Four turns containing:
- same question;
- unchanged evidence;
- one relief-followed-by-checking marker;
- multiple turns;
- **no pursuing-certainty or impossible-certainty marker**

produce:

```text
pattern_detected = True
dimensions_present includes impossible_certainty_pursuit
```

**Why tests did not catch it:**

The test named `test_multi_turn_impossible_certainty_requires_all_grounds` builds its “complete” case **without any explicit certainty-pursuit marker**, then expects `pattern_detected=True`.

The test therefore codifies the weakened requirement.

**Smallest safe remediation:**

`same_question` must never imply `impossible_certainty_pursuit`.

Require an independent grounded field/event for certainty pursuit and preserve `pattern_detected=False` if it is absent.

**Regression test:**

```text
test_same_question_unchanged_evidence_and_relief_is_not_certainty_pattern_without_certainty_pursuit
```

---

## I-003 — Explicit “wait / no advice” intent is detected and then discarded

**Severity:** IMPORTANT

**Files:**
- `cmm/domains/concerns/rules.py:1201-1297`
- weakened test: `tests/domains/test_concerns_domain_recurrence.py:165-170`
- weakened acceptance gate: `tests/domains/test_concerns_domain_dp025_acceptance.py:544-551`

**Frozen requirement violated:**
- action only when useful or wanted;
- no action is a valid outcome;
- explicit wish to wait must be respected unless credible immediate risk changes the safety boundary.

**Problem:**

The helper computes:

```python
wants_no_advice = ...
```

including `"just need to talk"`, `"no advice"`, and `"wait"`.

It then never uses that variable and explicitly deletes it:

```python
del urgent, wants_no_advice
```

If any option exists, the result becomes `ACTION_OPTIONAL`.

**Independent reproduction:**

```text
options=("contact them now",)
user_request="I want to wait."

=> ACTION_OPTIONAL
```

and:

```text
user_request="No advice, I just need to talk."

=> ACTION_OPTIONAL
```

**Why tests did not catch it:**

The wait test allows either:

```text
NO_ACTION_NEEDED
or ACTION_OPTIONAL
```

so it permits the bug.

The rule-class test only verifies `decision_adopted=False` and `action_forced=False`; it does not verify that action is suppressed when explicitly unwanted.

**Smallest safe remediation:**

Before candidate-option logic:

```text
if explicit no-advice/wait and no credible immediate specialized escalation:
    NO_ACTION_NEEDED
```

Keep options internally if useful, but do not surface an action state that invites action against explicit current intent.

**Regression tests:**

```text
test_explicit_wait_yields_no_action_needed_without_immediate_risk
test_explicit_no_advice_yields_no_action_needed
test_immediate_specialized_risk_can_override_wait_only_for_domain_escalation
```

---

## I-004 — Concerns directly imports Reflection's private domain helper

**Severity:** IMPORTANT

**Files:**
- `cmm/domains/concerns/operations.py:375-398`
- weakened tests: `tests/domains/test_concerns_domain_cross_domain.py:175-211`

**Frozen requirement violated:**
- cross-domain behavior through shared contracts / authorized projections;
- no direct specialized-domain private dependency;
- Reflection remains a sibling Domain Pack, not a library used by Concerns.

**Problem:**

`explore_hypotheses_result()` imports:

```python
from cmm.domains.reflection.rules import evaluate_hypotheses
```

A scan of `cmm/domains/concerns/` found this as the only direct specialized-domain import.

**Why tests did not catch it:**

`test_reflection_meaning_stays_with_reflection()` deliberately removes the literal string `"cmm.domains.reflection.rules"` before checking for a Reflection import:

```python
assert "from cmm.domains.reflection" not in source.replace(
    "cmm.domains.reflection.rules", ""
) ...
```

Then `test_hypothesis_exploration_composes_shared_contract()` directly imports the same Reflection helper and asserts parity.

This does not test the frozen boundary; it legitimizes the dependency.

**Smallest safe remediation:**

Move genuinely shared hypothesis evaluation into a shared Cognitive/Domain utility contract, or consume Reflection output through a shared `domain_result` projection.

Concerns must not import `cmm.domains.reflection.rules`.

**Regression test:**

```text
test_concerns_package_has_no_import_from_any_specialized_domain_package
```

Perform AST import scanning across all 14 Concerns modules.

---

## I-005 — Catastrophic caveat stacking from the frozen design is not implemented

**Severity:** IMPORTANT

**Files:**
- `cmm/domains/concerns/rules.py:877-913`
- no corresponding implementation/test for caveat stacking

**Frozen requirement violated:**

Spec explicitly requires:

> prevent repeated caveat stacking that makes an ordinary situation sound dangerous merely because technically negative possibilities exist.

The adversarial matrix also requires remote negative possibilities not to be listed merely as safety caveats.

**Problem:**

`detect_catastrophic_escalation()` only compares one `source_kind` and one `proposed_kind` against seven known promotion pairs.

There is no structure for:
- multiple remote negative possibilities;
- cumulative caveat count;
- materiality of caveats;
- evidence basis for each caveat;
- “probably fine, BUT...” stacking.

A source scan for caveat/stack behavior finds the requirement in docs, but not a Concerns implementation/test.

**Why tests did not catch it:**

Tests cover the seven single-transition promotions, not response-plan/list-level caveat accumulation.

**Smallest safe remediation:**

Add a structured caveat/proportionality helper that receives proposed warnings/scenarios plus evidence/materiality and rejects remote, unsupported negative possibilities from being appended as safety padding.

**Regression tests:**

```text
test_remote_negative_possibilities_are_not_stacked_as_safety_caveats
test_one_material_warning_is_preserved_without_remote_caveat_expansion
test_caveat_count_does_not_grow_from_technical_possibility_alone
```

---

## I-006 — `evaluate_proportional_risk()` accepts `evidence` but never uses it

**Severity:** IMPORTANT

**File:**
- `cmm/domains/concerns/rules.py:781-874`

**Frozen requirement violated:**
- objective risk must be evidence-calibrated;
- emotional intensity is not objective risk;
- specialized domains own specialized risk semantics.

**Problem:**

The function signature includes:

```python
evidence=()
```

but the variable is never read.

Subjective/free-text severity maps directly to risk level. In particular:

**Independent reproduction:**

```text
evaluate_proportional_risk(
    evidence=(),
    severity="medium"
)

=> risk_level = "medium"
```

No evidence was supplied and no specialized domain result exists.

High subjective severity is specially prevented from creating high risk, but medium severity still creates an objective-looking `medium` risk state without grounding.

**Why tests did not catch it:**

Tests cover severe emotional wording and authorized Health red flags, but not medium/no-evidence or evidence-sensitive risk calibration.

**Smallest safe remediation:**

Separate:
- subjective severity / lived impact;
- grounded risk evidence;
- authorized specialized risk.

Without grounded risk evidence or specialized semantics, objective risk should remain `none`/`unresolved` rather than be inferred from subjective severity.

**Regression tests:**

```text
test_medium_subjective_severity_without_evidence_does_not_create_medium_objective_risk
test_grounded_risk_evidence_changes_risk_state
test_emotional_intensity_changes_lived_impact_not_objective_risk
```

---

## I-007 — Presentation drops the actual reassurance assessment and remaining uncertainty from canonical helper output

**Severity:** IMPORTANT

**Files:**
- `cmm/domains/concerns/presentation.py:182-206`
- `cmm/domains/concerns/presentation.py:218-267`
- tests use synthetic aggregate keys rather than canonical helper output

**Frozen requirement violated:**
- presentation may reorder/label semantics but must not alter facts, uncertainty, reassurance basis, risk, permissions, action or memory state.

**Problem:**

Canonical reassurance helper emits:

```text
assessment
remaining_uncertainty
acknowledged_concerns
```

Presentation looks for:

```text
uncertainty
reassurance_assessment
or nested reassurance.assessment
material_concerns
```

Therefore directly presenting a canonical reassurance result loses both its assessment and uncertainty.

**Independent reproduction with actual helper-shaped data:**

Input:

```python
{
    "assessment": "REASSURANCE_SUPPORTED",
    "remaining_uncertainty": ["exact motive unknown"],
    "acknowledged_concerns": [],
    "material_concern": False,
    "absolute_certainty": False,
}
```

Presentation output:

```text
uncertainty = ()
reassurance_assessment = INSUFFICIENT_BASIS
unresolved = False
conclusion_presented = True
presentation_state = known_fact
```

This is semantic drift.

**Why tests did not catch it:**

Presentation tests construct synthetic input using the keys presentation already expects (`uncertainty`, `reassurance_assessment`) rather than passing the actual result of `evaluate_reassurance_result()`.

**Smallest safe remediation:**

Define one canonical aggregate Concerns result contract or add a strict adapter from each operation result.

At minimum presentation must preserve:
- `assessment`;
- `remaining_uncertainty`;
- `acknowledged_concerns`;
when presented from reassurance output.

**Regression test:**

```text
test_presenting_actual_reassurance_helper_output_preserves_assessment_and_uncertainty
```

Prefer a parity matrix passing all 13 operation-helper outputs through the presentation adapter.

---

## I-008 — Concerns trace API cannot represent supporting domains despite claiming it can

**Severity:** IMPORTANT

**Files:**
- `cmm/domains/concerns/trace.py:75-117`
- weakened test: `tests/domains/test_concerns_domain_trace.py:83-99`

**Frozen requirement violated:**

Concerns trace must explain:

```text
which supporting domains participated
```

AT-DP-025 also requires a supporting domain in Step 2.

**Problem:**

`assemble_concerns_trace()` has no `supporting_domains` argument and hardcodes:

```python
supporting_domains=()
```

It also only creates the Concerns primary `DomainResultTraceReference`.

The test named:

```text
test_supporting_domains_are_preserved_when_supplied
```

does not supply a supporting domain at all. It merely verifies two Concerns-owned contribution reference IDs.

**Why tests did not catch it:**

During implementation the test was changed after discovering the shared trace contract's DOMAIN_RESULT ownership rule, but the final replacement no longer verifies the original requirement.

This is a concrete example of a test being adjusted to the contract while losing the behavior it was supposed to prove.

**Smallest safe remediation:**

Extend the trace assembler wrapper to accept:
- `supporting_domains`;
- supporting domain-result references / cross-domain result references as required by shared contracts.

Pass them into `DomainTraceAssemblyRequest`.

**Regression test:**

```text
test_assemble_concerns_trace_preserves_real_supporting_domains_and_cross_domain_results
```

Validate against an inventory with non-empty `expected_supporting_domains`.

---

# MINOR findings

## M-001 — Implementation report says 22 Concerns test files; snapshot contains 20

**Severity:** MINOR

The implementation plan named 22 focused test files, including dedicated:

```text
test_concerns_domain_rollback.py
test_concerns_domain_validation_first_matrix.py
```

The snapshot contains 20 `test_concerns_domain_*.py` files.

Rollback and validation-first coverage is present inside `test_concerns_domain_integration.py`, so this is not itself a missing semantic gate. The issue is traceability/reporting: the implementation report states “22 files, 287 tests,” which does not match the tracked snapshot.

**Remediation:**

No new files are required solely for naming consistency. Correct future reports to reflect actual tracked files, or split the tests if strict plan-file mapping is desired.

---

# Mandatory test-strength audit

The implementation history specifically required checking whether tests changed to model the real shared contract or were weakened to make implementation pass.

## Correct/acceptable adjustment

### Reflection's old “Concerns package must not exist” guard

`tests/domains/test_reflection_domain_cross_domain.py:78-102`

The old pre-10.25 assumption had genuinely become stale. The replacement correctly tests the real invariant: Reflection must not depend on Concerns.

This adjustment is valid.

## Weakened or incomplete adjustments

### Workflow output/dependency behavior

The agent correctly discovered that validation sees **declared dependency outputs keyed by node ID**. However, the final graph still contains mismatched producer fields/dependencies and final tests do not systematically verify producer-schema → gate-condition reconciliation.

**Result:** weakened/incomplete; BLOCKER B-003.

### Permission/memory assertions

The final literal-True and complete binding-chain semantics are structurally strict. No weakening defect was identified in the audited paths.

**Result:** acceptable.

### Trace DOMAIN_RESULT ownership

The agent correctly learned that cross-domain/domain-result references have shared ownership constraints. But the replacement test no longer proves supporting-domain preservation and `assemble_concerns_trace()` hardcodes no supporting domains.

**Result:** weakened; IMPORTANT I-008.

### Adversarial helper invocation

The implementation log fixed test invocation syntax/keyword-only issues. No semantic weakening was identified solely from that change.

**Result:** acceptable.

### DP-025 trace reference kind

Changing an action-state reference away from a conflicting explicit DOMAIN_RESULT kind fixed a shared-contract mismatch, but the final AT-DP trace remains symbolic rather than linked to prior scenario outputs.

**Result:** contract correction plus incomplete acceptance; BLOCKER B-004.

### Recurrence pattern

The final test explicitly treats repeated `same_question=True` as sufficient to create `impossible_certainty_pursuit`, contrary to the frozen design.

**Result:** weakened; IMPORTANT I-002.

### Explicit wait/no-advice

The final test permits `ACTION_OPTIONAL` for “I want to wait,” contrary to the frozen action semantics.

**Result:** weakened; IMPORTANT I-003.

### Reflection boundary from Concerns

The final Concerns cross-domain test deliberately removes `cmm.domains.reflection.rules` from its static source check and then imports Reflection's rule helper to test parity.

**Result:** weakened; IMPORTANT I-004.

---

# Independent reproductions summary

The following were executed directly against pure helper code extracted from the uploaded snapshot, without using the implementation agent's reported test results:

```text
1. explicit reassurance + lower-priority perspective signal
   => MIXED

2. explicit "No advice, I just need to talk" + action signal
   => MIXED
   => problem_solving_allowed=True

3. repeated same question + unchanged evidence + relief/checking,
   with no certainty-pursuit marker
   => pattern_detected=True
   => impossible_certainty_pursuit fabricated

4. "I want to wait" + one option
   => ACTION_OPTIONAL

5. "No advice, I just need to talk" + one option
   => ACTION_OPTIONAL

6. two grounded records supporting "benign explanation"
   => CONCERN_SUPPORTED

7. one reassurance record from source:1
   => REASSURANCE_PARTIAL

8. same source:1 repeated under two IDs
   => REASSURANCE_SUPPORTED
   => duplicate_count=0

9. severity="medium", evidence=()
   => risk_level="medium"

10. actual reassurance-helper-shaped data through presentation
    => uncertainty=()
    => reassurance_assessment=INSUFFICIENT_BASIS
    => presentation_state=known_fact

11. workflow validation:
    metadata false_reassurance=False
    dependency false_reassurance_detected=True
    => COMPLETED

12. same engine with correctly named false_reassurance=True
    => FAILED / validate.condition_false
```

These reproductions demonstrate that the findings are behavioral, not style opinions.

---

# Audit gates

Allowed values: `PASS`, `FAIL`, `NOT_PROVEN`.

```text
AUDIT_GATES
- PACKAGE_BOUNDARY: PASS
- CATALOG_RECONCILIATION: PASS
- UNDERSTAND_BEFORE_ACTION: PASS
- SUPPORT_NEED_PRECEDENCE: FAIL
- EXPERIENCE_FACT_SEPARATION: PASS
- QUESTION_MATERIALITY: FAIL
- REASSURANCE_ALLOWED: FAIL
- NO_FALSE_REASSURANCE: FAIL
- NO_CATASTROPHIC_ESCALATION: FAIL
- REAL_CONCERN_ACKNOWLEDGEMENT: PASS
- REPETITION_NOT_PATHOLOGY: PASS
- RECURRING_PATTERN_GROUNDING: FAIL
- DIRECTNESS: PASS
- NO_FORCED_ACTION: FAIL
- HEALTH_HANDOFF: PASS
- REFLECTION_BOUNDARY: FAIL
- RELATIONSHIPS_BOUNDARY: PASS
- PERMISSION_LITERAL_TRUE: PASS
- MEMORY_CONFIRMATION: PASS
- WORKFLOW_DEPENDENCY_INTEGRITY: FAIL
- PRESENTATION_SEMANTIC_PRESERVATION: FAIL
- TRACE_REFERENCE_ONLY: PASS
- ROLLBACK: NOT_PROVEN
- INPUT_ORDER_INVARIANCE: NOT_PROVEN
- INPUT_NON_MUTATION: NOT_PROVEN
- STRICT_JSON: NOT_PROVEN
- CLEAN_IMPORT: NOT_PROVEN
- AT_DP_025: FAIL
- FOCUSED_TESTS: NOT_PROVEN
- DOMAIN_REGRESSIONS: NOT_PROVEN
- ALL_DOMAIN_TESTS: NOT_PROVEN
- GLOBAL_TESTS: NOT_PROVEN
- RUFF: NOT_PROVEN
- COMPILEALL: PASS
- DIFF_HYGIENE: PASS
```

## Why some verification gates are `NOT_PROVEN`

The snapshot's normal import path requires the repository dependency `libcst`, which is not installed in the independent audit runtime. Network installation is unavailable in this environment.

Therefore the auditor did **not** claim fresh independent pytest/Ruff/clean-import results based on the implementation agent's report.

This does **not** mean those suites fail. It means:

```text
implementation agent reported them green
!=
independent runtime proof
```

The semantic failures above were independently reproduced without needing that dependency.

---

# Remediation order

Do not remediate all findings at once.

Recommended order:

```text
R1 — Reassurance contract
     B-001 + B-002

R2 — Workflow gate integrity
     B-003

R3 — Connected AT-DP-025 + trace
     B-004 + I-008

R4 — Support/recurrence/agency
     I-001 + I-002 + I-003

R5 — Cross-domain architecture
     I-004

R6 — Safety calibration
     I-005 + I-006

R7 — Presentation parity
     I-007

R8 — Full regression + fresh independent re-audit
```

Each remediation block should:
1. add a failing regression test;
2. verify RED;
3. implement the minimum correction;
4. verify focused GREEN;
5. run Concerns + relevant sibling regressions;
6. commit separately;
7. only then proceed.

---

# Closure status

```text
PHASE10_25_IMPLEMENTATION_STATUS:
IMPLEMENTED_WITH_AUDIT_FINDINGS

PHASE10_25_DOCUMENTATION_STATUS:
IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
(current wording remains correct)

AT_DP_025_STATUS:
IMPLEMENTATION_SIDE_TEST_PRESENT
INDEPENDENT_ACCEPTANCE_FAIL

INDEPENDENT_AUDIT_STATUS:
NOT_READY_TO_CLOSE
```

Do not change the roadmap to “independently audited” or close Phase 10.25 until all BLOCKER and IMPORTANT findings are remediated and the independent audit is rerun.
