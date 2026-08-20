# Phase 10.24 — Reflection Domain — Independent Audit V2

Date: 2026-08-20

## Candidate

```text
branch: feature/phase-10-domain-intelligence
candidate: 6e14690
base audit V1 commit: 1a1048c
implementation commit: 212da44
frozen design commit: 563f7e2
```

Evidence bundle:

```text
cmm-phase-10.24-audit-v2-evidence-20260820-191543.tar.gz
```

Bundle integrity was independently verified:

```text
manifest entries: 72
manifest verification: PASS
candidate HEAD: 6e14690
```

The collector's own first `v2-smoke-probe` exit failure was investigated and
dismissed as a probe-construction error: it called a keyword-only Reflection
helper positionally. That collector error is not a product finding.

A corrected focused V2 probe was then executed in the user's real project
`.venv` against committed candidate `6e14690`.

---

# Verdict

## REMEDIATION REQUIRED

```text
Critical: 0
Important: 5
Minor: 0
```

Phase status:

```text
Phase 10.24 — Implemented, remediation required
DP-024 — NOT YET VERIFIED
AT-DP-024 — NOT YET PASS
```

The V1 remediation materially improved the implementation and closed the
previously identified V1 defects. However, five adversarial edge classes remain
open and are blocking Phase 10.24 closure.

---

# 1. Fresh baseline

The V2 evidence bundle reports the remediation candidate with clean repository
state and green committed suites, including the V1 closure suite, Reflection,
Domains, Global, Ruff, py310, compileall, fresh import, diff check, and package
boundary verification.

The focused V2 probe nevertheless produced:

```text
VALIDATE_LITERAL_BOOL=FAIL
VALIDATE_CONFLICT=FAIL
PERSISTENCE_SHARED_CONTRACT=FAIL
INTEREST_SINGLE_SOURCE_UNCERTAINTY=FAIL
DIAGNOSIS_SPANISH=FAIL
NO_FORCED_CONCLUSION_SPANISH=FAIL

ALL_FOCUSED_V2_GATES_PASS=false
```

These are real runtime observations from the committed candidate.

---

# 2. V1 status

The V2 audit does not reopen the whole V1 set.

The V1 remediation remains accepted for the previously reproduced classes
except where the new V2 probes expose a narrower residual edge.

Accepted V1 closures include:

```text
same-ID hypothesis collision handling
same-ID ambivalence collision handling
counterevidence bypass repair
equal-time subgroup chronology hardening
normalized personal timeline ordering
unsupported/model/memory source-kind grounding hardening
strict truthiness presentation repair for known tested primitives
diagnostic English-path hardening
no-forced-conclusion English-path hardening
strict JSON/no-exception broad helper hardening
dead-code cleanup
shared VALIDATE execution path introduction
```

V2 findings are new residual defects at the edges of those fixes.

---

# 3. Findings

## V2-I1 — Shared VALIDATE evaluator still fails open on malformed boolean values and conflicting dependency states

**Severity:** Important

**Shared surface:**

```text
cmm/workflows/engine.py
```

### A. Numeric `1` satisfies expected boolean `True`

Focused probe:

```text
wait_condition = {"flag": True}
producer output = {"flag": 1}
```

Observed:

```text
status = completed
error = None
VALIDATE_LITERAL_BOOL_GATE=FAIL
```

Root cause class:

```text
Python equality:
1 == True
0 == False
```

A boolean validation gate must use strict boolean-state comparison when the
condition value is boolean.

Expected:

```text
expected True
actual 1
→ malformed/nonliteral
→ validation fails closed
```

### B. Conflicting dependency values can still complete

Focused probe:

```text
dependency A output = {"safe": False}
dependency Z output = {"safe": True}
wait_condition = {"safe": True}
```

Observed:

```text
status = completed
error = None
VALIDATE_CONFLICT_GATE=FAIL
```

The shared validator accepts a matching dependency output while not treating
the contradictory dependency value as an unresolved/conflicting state.

Expected:

```text
same validation key appears with conflicting dependency values
→ conflict
→ validation fails closed
```

**Impact:** shared workflow safety gates can approve malformed or contradictory
state, including Reflection's decision/identity/chronology validations.

**Required remediation:**

- strict type-aware equality for boolean condition values;
- gather all relevant dependency values for a validation key;
- conflicting dependency values fail closed;
- missing/unknown/malformed still fail closed;
- regression tests for literal bool and multi-dependency conflict;
- rerun existing workflow/domain regressions.

---

## V2-I2 — Persistence confirmation accepts an arbitrary shape instead of a verified shared confirmation

**Severity:** Important

**Reflection surface:**

```text
cmm/domains/reflection/rules.py
classify_persistence()
```

Focused input:

```python
confirmation = {
    "decision_id": "fake-decision",
    "request_id": "fake-request",
    "approved": True,
}
```

with:

```text
pattern = fixed identity claim
sources = ["attacker:1"]
```

Observed:

```text
persistence_state = confirmed
confirmed = true
eligible_for_confirmation = true
authorization_accepted = true
authorization_malformed = false
basis_sufficient = true

PERSISTENCE_SHARED_CONTRACT_GATE=FAIL
```

The object has the *shape* of a confirmation but there is no evidence in the
observed result that it is a canonical shared approval/confirmation object
validated against a real shared contract/repository/trace.

Expected:

```text
arbitrary mapping with approved=True
!= verified shared confirmation
→ not confirmed
```

**Impact:** sensitive semantic persistence can be promoted to confirmed based on
caller-supplied shaped data rather than an authoritative shared confirmation.

**Required remediation:**

- require the exact canonical shared confirmation/approval representation;
- validate identity/reference/provenance through the existing shared contract;
- do not authorize merely by dictionary keys;
- preserve literal `True` only inside the verified shared object;
- raw/fake mappings fail closed;
- no new Reflection approval subsystem.

---

## V2-I3 — Multiple mentions from one grounded source remove uncertainty even though independent corroboration remains one

**Severity:** Important

**Reflection surface:**

```text
cmm/domains/reflection/rules.py
map_interests()
```

Focused input:

```text
interest = photography
source = msg:one
source_kind = user_statement
two different recordings
same source
```

Observed:

```text
sources = ["msg:one"]
grounded_evidence_count = 1
independent_grounded_count = 1
mention_count = 2
uncertainty = false
relative_strength = stronger

INTEREST_SINGLE_SOURCE_UNCERTAINTY_GATE=FAIL
```

The implementation correctly deduplicates the source count but still allows
multiple mentions inside that one source to remove uncertainty/strengthen the
candidate as though independent corroboration existed.

Frozen DP-024 distinction:

```text
repetition != persistence
duplicate/same source != corroboration
```

Expected:

```text
one independent grounded source
→ candidate may exist
→ uncertainty remains true
→ repetition in same source may be recorded as mention_count
  but cannot substitute for independent corroboration
```

**Impact:** source-grounded interest mapping can overstate confidence from one
source.

**Required remediation:**

- uncertainty/strength must be based on independent grounded source evidence,
  not raw mention count;
- preserve mention count as descriptive only;
- add one-source-many-mentions vs two-independent-sources regression tests.

---

## V2-I4 — Diagnosis / restricted-inference safety is English-token dependent and fails in Spanish

**Severity:** Important

**Reflection surfaces:**

```text
cmm/domains/reflection/rules.py
evaluate_hypotheses()

cmm/domains/reflection/presentation.py
present_reflection_result()
```

Focused input:

```text
"Eres narcisista"
```

Observed hypothesis:

```text
status = hypothesis
fact = false
diagnostic = false
restricted_inference = false
relative_strength = stronger
no_diagnosis = true
```

Observed presentation preserves verbatim:

```text
statement = "Eres narcisista"
diagnosis = false
restricted_inference = false
```

Focused gate:

```text
DIAGNOSIS_SPANISH_GATE=FAIL
```

The remediation catches tested English diagnostic/classification forms but does
not enforce the underlying semantic restriction robustly across the project's
Spanish-language use.

Expected:

```text
identity/personality/diagnostic classification claim
→ restricted/unsafe regardless of English vs Spanish wording
→ cannot be presented verbatim as a safe non-diagnostic hypothesis
```

**Impact:** the high-sensitivity identity/diagnosis boundary can be bypassed by
language choice.

**Required remediation:**

- make the restricted-inference boundary language-appropriate for supported
  project usage;
- at minimum cover canonical Spanish diagnostic/personality/attachment/identity
  forms as well as English;
- prefer structural classification markers where available instead of relying
  exclusively on phrase matching;
- add Spanish regression cases.

---

## V2-I5 — NoForcedConclusion safety is language-dependent and fails on obvious Spanish unsupported certainty

**Severity:** Important

**Reflection surface:**

```text
cmm/domains/reflection/rules.py
no_forced_conclusion_policy()
```

Focused input:

```text
unresolved = true
conclusion = "Es evidente que soy narcisista"
```

Observed:

```text
forced_conclusion = false
valid_unresolved_completion = true
unsupported_certainty = []
unresolved = true
evaluated = true

NO_FORCED_CONCLUSION_SPANISH_GATE=FAIL
```

The system accepts an obviously forced, identity-classifying conclusion while
the reflection is explicitly unresolved.

Expected:

```text
unresolved reflection + unsupported certainty/classification
→ forced/unsupported conclusion detected
→ not accepted as valid unresolved completion with conclusion intact
```

**Impact:** unsupported certainty can bypass the Reflection contract in the
project's primary user language.

**Required remediation:**

- stop relying on an English-only certainty phrase set;
- use structural unresolved/certainty state first;
- add Spanish certainty/classification markers as a minimal language-safe
  boundary where free text must be inspected;
- ensure presentation/summary cannot amplify the bypassed conclusion.

---

# 4. DP-024 V2 assessment

## Open-ended analysis

**Remediation required**

V2-I5 shows unresolved analysis can still coexist with an unsupported forced
Spanish conclusion without being flagged.

## Prudent hypotheses

**Remediation required**

V2-I4 allows identity/personality classification wording to pass as a safe,
stronger hypothesis.

## Source-grounded interest mapping

**Remediation required**

V2-I3 overstates certainty from repeated mentions inside one independent source.

## Confirmed persistence

**Remediation required**

V2-I2 accepts caller-shaped confirmation instead of verified shared
confirmation.

Therefore:

```text
DP-024 = NOT YET VERIFIED
AT-DP-024 = NOT YET PASS
```

---

# 5. Shared workflow V2 assessment

The V1 remediation correctly moved `VALIDATE` from inert metadata toward an
executable shared gate.

That architectural direction is retained.

However V2-I1 proves the validator still requires one additional fail-closed
hardening step:

```text
strict boolean type
conflicting multi-dependency state
```

No evidence currently justifies reverting the shared `VALIDATE` change.

---

# 6. Non-findings / dismissed concerns

## Collector V2 smoke-probe exit

Dismissed.

The collector called `evaluate_hypotheses()` positionally even though the
function is keyword-only. That failure occurred before the intended gate logic
and is not a candidate defect.

## V1 counterevidence defect

The focused V2 probe did not reopen the V1 counterevidence finding.

## Presentation `"false"` truthiness defect

The focused V2 probe confirms the V1 remediation fixed the previously observed
presentation truthiness case.

## Broad public-helper JSON/no-exception defect

The remediation added wider permanent coverage and no new V2 failure was
observed for that class in the focused probe.

---

# 7. Required V2 remediation

The remediation is intentionally small.

Required order:

```text
1. V2-I1 shared VALIDATE strict bool + conflict semantics
2. V2-I2 canonical shared confirmation verification
3. V2-I3 interest confidence based on independent sources
4. V2-I4 Spanish diagnosis/restricted inference
5. V2-I5 Spanish unsupported-certainty / forced conclusion
```

Each must start with a RED regression test reproducing the exact V2 input.

No broad refactor.

No new subsystem.

---

# 8. Required verification after V2 remediation

At minimum:

```text
V1 closure suite
new V2 closure suite
Reflection suite
shared workflow VALIDATE regressions
Domains suite
Global suite
Ruff
Ruff py310
compileall
fresh import
diff check
clean-state verification
```

Independent V3 should then attack:

```text
shared VALIDATE nested/conflicting states
confirmation object authenticity/provenance
one-source-many-mentions vs independent sources
Spanish/English restricted-inference variants
Spanish/English certainty variants
```

---

# 9. Final V2 status

```text
Phase 10.24 — Implemented, remediation required

Critical: 0
Important: 5
Minor: 0

Independent Audit V2: REMEDIATION REQUIRED
DP-024: NOT YET VERIFIED
AT-DP-024: NOT YET PASS
```

No remediation was performed during this audit.
No push.
No merge.
