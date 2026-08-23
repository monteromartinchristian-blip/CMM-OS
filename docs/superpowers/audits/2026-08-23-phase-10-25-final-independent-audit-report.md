# Phase 10.25 — Concerns Domain — Final Independent Audit

**Date:** 2026-08-23
**Audit mode:** independent read-only audit of final tracked-HEAD snapshot
**Bundle:** `CMM-OS-phase-10.25-final-audit.tar.gz`
**Bundle SHA-256:** `0e79f73b6bcb583fc18731e8d62b24352622601f2f65743f84b60fc2e3d67877`
**Audited HEAD:** `45998f81ce8a50fe4a925ea24c5e2cdda863d120` (`45998f8`)
**Previous re-audit HEAD:** `f9e7f14c0e24b254774722442d0638cc08d45c5d`

## Verdict

```text
AUDIT_VERDICT: FAIL — closure remediation required
INDEPENDENT_AUDIT_STATUS: NOT_READY_TO_CLOSE
```

This final snapshot is materially stronger than the two earlier audited states. The frozen structural canon is intact, most previously reported behavioral defects are fixed, and the final remediation did not alter the canonical architecture.

However, the audit found three remaining closure blockers and one important presentation regression. The most serious issue is now at the **operation input-contract boundary**: several corrected semantic helpers cannot receive their required parameters through the operation schemas enforced by the shared Agent Runtime.

---

# What is independently confirmed

## Structural canon

```text
production modules = 14
entities           = 17
resources          = 10
rules              = 14
operations         = 13
workflows          = 8
profile            = ConcernSupportProfile
domain             = domain:concerns
```

Exact production modules:

```text
__init__.py
bootstrap.py
catalog.py
definition.py
integration.py
memory.py
operations.py
permissions.py
presentation.py
profile.py
resources.py
rules.py
trace.py
workflows.py
```

## Static architecture

Independently verified:

```text
zero direct imports from specialized sibling domains
zero obsolete ReassuranceLoopRule / ConcernFactScenarioRule semantics
zero concerns.generate_monitoring_plan
zero concerns.structure_concern
zero concerns.separate_fact_scenario
compileall PASS
```

## Previously audited behaviors now corrected

Direct independent helper probes confirm:

```text
authorized specialized result without probability -> no TypeError
subjective severity=low + no evidence            -> objective risk none
REASSURANCE_PARTIAL + acknowledged concern       -> not false reassurance
material + immaterial question candidates        -> immaterial suppressed,
                                                     emitted question material
canonical catastrophic transitions               -> detected and safely blocked
flat risk helper output                           -> risk preserved by presentation
CONCERN_SUPPORTED without facts                   -> not promoted to known_fact
```

The canonical counts in the agent's final prose report were wrong, but the actual tracked code is correct (`17/10/14/13/8`).

## Independent test execution available in audit runtime

The full repository cannot be collected normally in the audit runtime because `libcst` is absent.

Using an isolated import harness that bypasses unrelated package `__init__` side effects:

```text
tests/domains/test_concerns_domain_audit_r3.py
=> 2 passed

tests/domains/test_concerns_domain_audit_r8.py
=> 26 tests independently passed
```

Two R8 rule-builder tests cannot be certified in this shim because the Python 3.13 audit environment exposes a shared `dataclass(slots=True)`/zero-argument-`super()` compatibility problem in the pre-existing rule-contract layer. This is not used as a Phase 10.25 finding.

The implementation agent's reported full-suite totals therefore remain implementation-side evidence rather than independent certification.

---

# BLOCKER FB-001 — Canonical operation input schemas reject the semantics their helpers require

**Severity:** BLOCKER

**Files:**
- `cmm/domains/concerns/operations.py:100-162`
- `cmm/domains/concerns/operations.py:528-563`
- shared runtime enforcement: `cmm/agent_runtime/operation_registry.py:166-183`

## Frozen requirement violated

The 13 Concerns operations are real `DomainOperationDefinition` contracts executed through shared runtime infrastructure.

The frozen operations require, among other things:

```text
concerns.infer_support_need
concerns.evaluate_reassurance
concerns.evaluate_risk
concerns.prepare_next_step
concerns.prepare_professional_discussion
```

to carry the semantic inputs required for support need, target-aware reassurance, specialized-domain evidence/risk, proportional action, and professional-discussion preparation.

The shared Agent Runtime validates operation requests against `input_schema` before invocation.

## Defect

The final remediation aligned **output schemas**, but input schemas remain incompatible with the canonical result-helper signatures.

### `concerns.evaluate_reassurance`

Helper signature:

```text
target_claim
evidence
counterevidence
uncertainty
material_concerns
base_plausibility
specialized_domain_result
```

Declared input schema permits only:

```text
evidence
counterevidence
uncertainty
```

with `additionalProperties=False`.

Independent shared-validator reproduction:

```text
$.target_claim               additional_property
$.base_plausibility          additional_property
$.material_concerns          additional_property
$.specialized_domain_result  additional_property
```

This is especially serious because the R1 remediation made reassurance explicitly **target-relative**, yet the actual operation contract cannot receive the target.

### `concerns.evaluate_risk`

Helper supports:

```text
evidence
severity
immediacy
specialized_domain_result
```

Input schema permits only:

```text
severity
evidence
```

Therefore Health/specialized-domain red flags and immediacy cannot reach the real operation request without being rejected.

### `concerns.infer_support_need`

Input schema requires:

```text
{"inputs": {...}}
```

but `infer_support_need_result(**kwargs)` consumes:

```text
explicit_request
current_signal
session_context
historical_preference
```

Calling the helper with the schema-valid wrapper silently discards `inputs` and resolves from no support signals.

Independent validator reproduction for the helper-shaped request:

```text
$.inputs             required
$.explicit_request   additional_property
```

### Other mismatches

`concerns.prepare_next_step` schema omits:

```text
desired_outcome
grounded_options
specialized_recommendation
specialized_domain_result
```

`concerns.prepare_professional_discussion` schema omits:

```text
uncertainties
current_impact
decisions_required
```

## Why tests missed it

The R1 parity suite verifies:

```text
helper OUTPUT -> output_schema
```

for all 13 operations.

It does not verify:

```text
canonical helper INPUT -> input_schema -> helper invocation
```

`tests/domains/test_concerns_domain_operations.py` only checks that every input schema is a closed structured object.

## Required remediation

Add a canonical input-parity matrix for all 13 operations.

For every operation prove:

```text
representative canonical request
→ validate_operation_schema(input, definition.input_schema) == ()
→ deterministic helper/implementation can consume that validated shape
```

Do not merely make schemas permissive.

The input shape and helper invocation shape must be one contract.

For reassurance, `target_claim` must be part of the actual operation contract.

For risk, authorized `specialized_domain_result` and relevant immediacy must be representable.

For SupportNeed, either:
- expose the four canonical fields directly; or
- intentionally use an `inputs` object and update the helper/adapter to consume that exact wrapper.

Do not keep both shapes.

## Required regression tests

```text
test_all_13_operation_inputs_validate_and_invoke_canonical_helpers
test_evaluate_reassurance_input_schema_accepts_target_and_specialized_result
test_evaluate_risk_input_schema_accepts_specialized_result_and_immediacy
test_infer_support_need_schema_and_helper_use_one_shape
test_prepare_next_step_schema_preserves_canonical_semantic_inputs
test_prepare_professional_discussion_schema_preserves_canonical_semantic_inputs
```

---

# BLOCKER FB-002 — Reassurance still fails open when target/quality/temporal evidence is unknown

**Severity:** BLOCKER

**File:** `cmm/domains/concerns/rules.py:653-976`

## Frozen requirement violated

`EvidenceCalibratedReassuranceRule` must evaluate:

```text
facts
source quality
counterevidence
uncertainty
base plausibility
domain-specific evidence
temporal relevance
material negative signals
```

Malformed/unknown evidence must not increase certainty.

The final R1 design itself states that full reassurance requires:

```text
strong, current, well-sourced evidence
```

## Defect A — target claim is optional while evidence stance is target-relative

Independent reproduction:

```python
evaluate_reassurance(
    evidence=(
        {
            "claim": "warm reply",
            "stance": "opposes_target",
            "grounding": "m1",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
        {
            "claim": "invited me",
            "stance": "opposes_target",
            "grounding": "m2",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
    )
)
```

Result:

```text
assessment = REASSURANCE_SUPPORTED
target_claim = None
```

Without a target claim, `opposes_target` has no defined proposition to oppose.

Target-relative evidence must fail closed when the target is absent.

## Defect B — missing or arbitrary quality is treated as strong evidence

`_is_current_and_grounded()` currently checks only:

```python
source_quality not in known_weak_values
and
temporal_relevance not in known_stale_values
```

Therefore `None` or an unknown string is treated as strong/current.

Independent reproductions:

```text
2 grounded records
source_quality = None
temporal_relevance = current
=> REASSURANCE_SUPPORTED

2 grounded records
source_quality = grounded
temporal_relevance = None
=> REASSURANCE_SUPPORTED

2 grounded records
source_quality = "banana"
temporal_relevance = "nonsense"
=> REASSURANCE_SUPPORTED
```

This is fail-open calibration.

## Why tests missed it

Final tests prove:
- explicit `"weak"` does not fully reassure;
- explicit `"stale"` does not fully reassure;
- explicit `"grounded"` + `"current"` can fully reassure.

They do not test:
- missing target claim;
- missing source quality;
- missing temporal relevance;
- unknown quality/relevance values.

## Required remediation

Use closed evidence-quality and temporal-relevance vocabularies.

A record may count as **strong/current** only with explicit recognized values.

Unknown/missing quality or temporal relevance may remain visible, but cannot contribute to `REASSURANCE_SUPPORTED`.

Target-relative directional evidence must not produce full reassurance without a usable target claim.

Safe result for missing target/quality context may be:

```text
REASSURANCE_PARTIAL
UNCERTAIN
INSUFFICIENT_BASIS
```

depending on the remaining grounded state, but never full support due to unknown metadata.

## Required regression tests

```text
test_missing_target_claim_cannot_produce_reassurance_supported
test_missing_source_quality_cannot_upgrade_to_full_reassurance
test_missing_temporal_relevance_cannot_upgrade_to_full_reassurance
test_unknown_source_quality_fails_closed
test_unknown_temporal_relevance_fails_closed
test_explicit_grounded_current_records_can_still_support_full_reassurance
```

---

# BLOCKER FB-003 — AT-DP-025 is improved but still not a fully connected 25-step acceptance proof

**Severity:** BLOCKER

**File:** `tests/domains/test_concerns_domain_audit_r3.py:161-597`

## What is fixed

The re-audit confirms genuine improvements:

```text
standard DefaultDomainResolver policy is used
supporting_margin remains production default 15
resolver selects Concerns primary + Relationships supporting
a real DomainWorkflowExecutor executes Open Concern Conversation
Step 12 now asserts exact REASSURANCE_PARTIAL
trace validates against the shared inventory
```

`test_concerns_domain_audit_r3.py` independently runs green in the audit harness (`2 passed`).

## Remaining connectivity defects

### 1. The workflow operation adapter does not consume dependency state

For the Open Concern workflow the adapter returns hard-coded operation results.

Examples:

```text
understand_concern -> hard-coded concern_material
infer_support_need -> hard-coded explicit_request/current_signal
map_lived_experience -> hard-coded material
identify_open_questions -> hard-coded question candidates
```

The adapter receives `(node, run)` but does not use prior dependency outputs from `run`.

Therefore the Workflow Engine proves execution order/gates, but not semantic state propagation between the workflow operations.

### 2. The supporting projection is not actually consumed by the executed workflow

`relationships_projection` is inserted into:

```text
concern_material["specialized_domain_result"]
workflow inputs["specialized_domain_result"]
```

but `understand_concern()` does not read `specialized_domain_result`, and the adapter does not read `run.inputs`.

The projection is later consumed by a direct `evaluate_reassurance_result()` call **outside** the executed Open Concern workflow.

So the test statement:

```text
"Real supporting projection consumed by Concerns workflow"
```

is not proven.

### 3. Step 7 still proves readiness, not an initial substantive response

The acceptance asserts:

```text
ready_for_substantive_response is True
```

The frozen AT-DP-025 step is:

```text
7. It provides an initial substantive response.
```

No actual semantic/presentation response is produced at that point.

### 4. Steps after the first workflow are still manually chained helper calls

Separation, hypotheses, reassurance, recurrence, options and next-step are direct calls with newly constructed arguments.

Some prior IDs are reused, but the sequence is not driven from workflow outputs.

### 5. Several trace “actual IDs” are still synthetic labels

The test manually creates:

```text
op-res-<node>-<counter>
rule:reassurance:<assessment>
recurrence:<state>
action:proposal-only
```

The first category is stored in a side dictionary in the adapter but is not an ID emitted by a shared operation result contract.

The later IDs are semantic strings created at trace-build time.

The frozen requirement does not require every trace reference to be an operation-result UUID, but an acceptance described as tracing the actual prior states should reference identifiers that existed in the connected execution state before trace construction.

## Required remediation

Do not create another test-only architecture.

Use a deterministic acceptance harness built on public shared contracts:

```text
resolver
→ supporting domain result/projection
→ real Concerns workflow execution
→ operation adapter reads dependency/run state
→ semantic output/presentation for initial response
→ user-answer/new-information state
→ reality/reassurance path consuming that state
→ recurrence consuming prior evidence state
→ problem-solving/action path
→ trace over IDs already present in executed state
```

It is acceptable to use multiple canonical Concerns workflows if one workflow does not cover all 25 steps.

The test must prove the data moves, not merely that calls occur in narrative order.

## Required regression assertions

```text
changing Step 3 output changes a downstream operation input
supporting domain_result is read by the workflow operation that needs it
Step 7 contains a non-empty substantive semantic response/projection
Step 9 consumes a simulated answer/new fact from Step 8
Step 12 consumes Step 9-11 state
Step 15 recurrence consumes the exact prior evidence state
Step 19-22 consume the user's actual "what can I do?" transition
trace references identifiers recorded before the trace-builder call
```

---

# IMPORTANT FI-001 — Presentation still alters/drops semantics; caveat integration introduces a new deletion regression

**Severity:** IMPORTANT

**File:** `cmm/domains/concerns/presentation.py:82-349`

## Frozen requirement violated

The reference contract says:

```text
present_concerns_result preserves semantics verbatim
```

and the frozen design requires preserving:

```text
facts
interpretations
hypotheses
fear/scenario
uncertainty
reassurance basis
material concerns
cross-domain evidence
action state
memory proposal
permission decisions
```

## Defect A — caveats delete unrelated scenarios

Final F3 integration does:

```python
if caveats_input:
    retained_texts = ...
    scenarios = tuple(
        s for s in scenarios
        if s.get("statement") in retained_texts
        or s.get("caveat") in retained_texts
    )
```

This filters **all** scenarios against the retained caveat list.

Independent reproduction:

Input:

```text
scenario 1 = "maybe they are busy"          # ordinary hypothesis/scenario
scenario 2 = "building collapse"            # remote caveat
caveats    = ["building collapse" remote]
```

Output:

```text
scenarios = ()
```

The remote caveat is correctly removed, but the unrelated ordinary scenario is also erased.

The caveat policy should remove only scenarios/caveats that are actually identified as suppressed caveats.

## Defect B — several operation outputs are still not semantically preserved

Independent actual-helper projection shows:

### `understand_concern`

Input contains:

```text
core_issue
situation
trigger
```

Presentation produces:

```text
actual_concern = ()
presentation_state = unknown
```

The actual concern is lost.

### `calibrate_uncertainty`

Input contains structured:

```text
calibrations
conflict_present
```

Presentation produces:

```text
uncertainty = ()
presentation_state = unknown
```

The uncertainty calibration is lost.

### `identify_open_questions`

Input contains:

```text
questions
why_it_matters
```

Presentation exposes neither.

The F6 “all 13 parity” test only asserts `section_order` for several operations, so it does not prove semantic parity.

## Defect C — default values can manufacture semantic conclusions

For operation results that never evaluated reassurance, presentation defaults:

```text
reassurance_assessment = INSUFFICIENT_BASIS
```

For operation results that never evaluated risk, it defaults:

```text
risk_level = none
```

These are not necessarily equivalent to **not evaluated**.

This is especially sensitive because the domain explicitly forbids inventing risk or certainty.

## Required remediation

Presentation should distinguish:

```text
not evaluated
from
evaluated as none / insufficient basis
```

Preserve actual operation semantics instead of filling semantic defaults.

For caveats:
- identify suppressed caveat texts/IDs;
- remove only matching suppressed caveat-derived scenarios;
- preserve unrelated scenarios.

For operation parity:
- add meaningful semantic assertions for all 13 canonical helpers;
- no `section_order`-only placeholders.

## Required regression tests

```text
test_caveat_filter_preserves_unrelated_scenarios
test_understand_concern_presentation_preserves_actual_issue
test_uncertainty_calibration_survives_presentation
test_material_questions_and_rationale_survive_presentation
test_non_reassurance_result_does_not_invent_reassurance_assessment
test_non_risk_result_does_not_invent_objective_risk_none
test_all_13_presentation_parity_tests_assert_semantic_fields
```

---

# MINOR FM-001 — Reference documentation still says independent audit has not been performed

**Severity:** MINOR

**File:** `docs/reference/concerns-domain.md`

Current text still states:

```text
Independent audit: not yet performed
```

Two independent audits and this final audit now exist.

Do not change the phase to audited/closed while blockers remain, but update wording after remediation to something accurate such as:

```text
Independent audits performed; latest audit findings remediated; final closure audit pending.
```

---

# Gate table

```text
PACKAGE_BOUNDARY: PASS
CATALOG_RECONCILIATION: PASS
CANON_COUNTS_17_10_14_13_8: PASS
SUPPORT_NEED_PRECEDENCE: PASS
EXPERIENCE_FACT_SEPARATION: PASS
QUESTION_MATERIALITY_HELPER: PASS
REPETITION_NOT_PATHOLOGY: PASS
RECURRING_PATTERN_GROUNDING: PASS
NO_FORCED_ACTION: PASS
REFLECTION_BOUNDARY: PASS
RELATIONSHIPS_BOUNDARY: PASS
PERMISSION_LITERAL_TRUE: PASS
MEMORY_CONFIRMATION: PASS
TRACE_SUPPORTING_DOMAINS: PASS
COMPILEALL: PASS
SIBLING_IMPORT_SCAN: PASS
OBSOLETE_SEMANTICS_SCAN: PASS

OPERATION_INPUT_CONTRACT_PARITY: FAIL
REASSURANCE_TARGET_FAIL_CLOSED: FAIL
REASSURANCE_QUALITY_FAIL_CLOSED: FAIL
PRESENTATION_SEMANTIC_PRESERVATION: FAIL
AT_DP_025_CONNECTED_ACCEPTANCE: FAIL

FOCUSED_TESTS_FULL_NATIVE_ENV: NOT_PROVEN
DOMAIN_REGRESSIONS_FULL_NATIVE_ENV: NOT_PROVEN
ALL_DOMAIN_TESTS_FULL_NATIVE_ENV: NOT_PROVEN
GLOBAL_TESTS_FULL_NATIVE_ENV: NOT_PROVEN
RUFF_NATIVE_ENV: NOT_PROVEN
CLEAN_IMPORT_NATIVE_ENV: NOT_PROVEN
```

## Status

```text
PHASE10_25_FINAL_AUDIT_STATUS:
CLOSURE_REMEDIATION_REQUIRED

AUDIT_VERDICT:
FAIL — closure remediation required

INDEPENDENT_AUDIT_STATUS:
NOT_READY_TO_CLOSE
```

The remaining work is narrow and does not require any architectural redesign or canonical-count change.
