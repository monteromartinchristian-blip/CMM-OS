# Phase 10.24 — Reflection Domain — Independent Audit V5

Date: 2026-08-20

## Candidate

```text
branch: feature/phase-10-domain-intelligence

candidate:
9fdbc273e965ca7157096e658ade4d2c96f2a549
9fdbc27 fix(domains): close phase 10.24 audit v4 findings

audit V4:
cde9d07368c513c7ea7e2e172eb7a406a1fa9862
cde9d07 docs(domains): record phase 10.24 independent audit v4

pre-V4 remediation:
f3585d86d37d68b7520f898d313964b109b28129
f3585d8 fix(domains): close phase 10.24 audit v3 findings
```

Evidence bundle:

```text
cmm-phase-10.24-final-audit-v5-evidence-20260820-234249.tar.gz
```

Bundle integrity:

```text
manifest entries: 85
verified: 85
mismatches: 0
manifest verification: PASS
```

Repository state:

```text
HEAD = 9fdbc27
branch = feature/phase-10-domain-intelligence
tracked/staged state = clean
Reflection package boundary = exactly 14 modules
repository parity = PASS
```

---

# Verdict

## REMEDIATION REQUIRED

```text
Critical: 0
Important: 2
Minor: 0
```

Phase status:

```text
Phase 10.24 — Implemented, remediation required
DP-024 — NOT YET VERIFIED
AT-DP-024 — NOT YET PASS
```

The V4 remediation closes the exact V4 reproductions and preserves the accepted
workflow, persistence, interest, JSON, and package invariants. Independent V5
variants nevertheless show that the two remaining text-safety helpers are still
implemented as enumerated phrase coverage rather than robust clause/polarity
classification.

No architecture outside those two Reflection safety helpers needs to be reopened.

---

# 1. Fresh verification

The committed candidate is broadly healthy.

## V1 + V2 + V3 + V4 closure

```text
120 passed
exit=0
```

## V4 closure

```text
15 passed
exit=0
```

## Reflection

```text
342 passed
exit=0
```

## Workflows

```text
44 passed
exit=0
```

## Domains + Workflows

```text
5206 passed
exit=0
```

## Domains

```text
5162 passed
exit=0
```

## Global

```text
10690 passed
exit=0
```

## VALIDATE regression

```text
17 passed
exit=0
```

## Persistence validated-chain regression

```text
10 passed
18 deselected
exit=0
```

## Ruff Phase 10.24 surface

```text
PASS
exit=0
```

## Ruff py310 Phase 10.24 surface

```text
PASS
exit=0
```

## compileall / fresh import / diff / package boundary

```text
compileall = PASS
fresh import = PASS
git diff --check = PASS
package boundary = 14/14 PASS
repository parity = PASS
```

---

# 2. Collector issue dismissed

The collector command intended to select interest-specific V2 tests returned:

```text
16 deselected
exit=5
```

This is a selector mistake:

```text
-k 'interest'
```

did not match the test names in that file.

This is not a product failure. The full V2 closure suite and full Reflection
suite both pass, and V5 source inspection does not reopen interest mapping.

---

# 3. Independent V5 semantic probe

The new V5 probe deliberately used wording absent from the V4 closure tests.

Observed:

```text
DIAG_SAFE_DISCLAIMER_GATE=PASS
DIAG_CONTEXTUAL_SYMPTOM_GATE=PASS
DIAG_TENTATIVE_LABEL_ES_GATE=PASS
DIAG_TENTATIVE_LABEL_EN_GATE=PASS
DIAG_MIXED_DISCLAIMER_ASSERTION_GATE=PASS
DIAG_DIRECT_ATTACHMENT_GATE=FAIL

CERTAINTY_NEGATED_ES_GATE=FAIL
CERTAINTY_NEGATED_EN_GATE=PASS
CERTAINTY_AFFIRMATIVE_ES_GATE=FAIL
CERTAINTY_AFFIRMATIVE_EN_GATE=FAIL
CERTAINTY_NO_DOUBT_IDIOM_GATE=PASS
CERTAINTY_MIXED_GATE=FAIL
CERTAINTY_QUOTED_EVIDENCE_GATE=PASS
CERTAINTY_STRUCTURAL_WINS_GATE=PASS

STRICT_JSON_GATE=PASS

ALL_V5_SEMANTIC_GATES_PASS=false
```

The failures were traced to the exact committed source.

---

# 4. Previously accepted architecture remains accepted

The following are not reopened by V5:

```text
shared VALIDATE dependency scoping
strict literal boolean validation
conflicting dependency fail-closed behavior

validated proposal/request/decision persistence binding
DomainMemoryProposalBinding + DomainMemoryReferenceInventory
validate_reflection_memory_binding()
standalone snapshot denial

same-source interest uncertainty
temporal normalization
strict JSON/no-exception hardening
presentation literal-state hardening
14-module package boundary
no external writes
no autonomous decision adoption
no silent memory mutation
```

---

# 5. Findings

## V5-I1 — Diagnostic restriction still depends on enumerated assertion shapes and misses a fixed attachment classification

**Severity:** Important

**Location:**

```text
cmm/domains/reflection/rules.py
_diagnostic_signal()
```

V4 improved polarity handling substantially. It now distinguishes many
disclaimers, tentative labels, and contextual symptom hypotheses correctly.

However the implementation still decides restricted classification from
enumerated phrase lists:

```text
_DIAGNOSTIC_DISCLAIMER_PATTERNS
_RESTRICTED_DIAGNOSTIC_CONDITIONS
_DIRECT_IDENTITY_PATTERNS
_TENTATIVE_ATTRIBUTIONS
```

Independent V5 runtime input:

```text
"Su estilo de apego es patológico"
```

Observed:

```text
diagnostic = false
restricted_inference = false
relative_strength = stronger
statement preserved verbatim
```

V5 gate:

```text
DIAG_DIRECT_ATTACHMENT_GATE=FAIL
```

The frozen specification explicitly restricts:

```text
fixed attachment labels
stable personality labels
mental-health diagnoses
fixed moral character labels
essentialized motives
```

and requires:

```text
psychological hypothesis != diagnosis
```

The missed statement is a direct fixed attachment-pathology classification,
not a merely contextual symptom observation.

### Root cause class

The parser recognizes:

```text
tu apego es
su apego es
your attachment is
your attachment style is
```

but not the compositional Spanish form:

```text
su estilo de apego es ...
su patrón de apego es ...
```

This demonstrates that the safety boundary remains tied to exact phrase
enumeration rather than the structural relation:

```text
subject/person
+
attachment/identity/personality axis
+
copular/classifying predicate
```

### Required remediation

Do not add only:

```text
"su estilo de apego es"
```

to another tuple.

Refactor diagnostic free-text fallback into a deterministic **clause
classification** with explicit outcomes:

```text
restricted
disclaimer
contextual
none
```

The classifier must compose:

```text
subject/person reference
classification axis
attribution/copular operator
restricted condition/trait predicate
tentative modality
diagnostic disclaimer polarity
contextual symptom framing
```

Tentative modality must never sanitize a restricted diagnostic/classification
predicate.

A disclaimer clause must not neutralize a separate restricted clause.

Contextual symptom exploration must remain allowed.

Required metamorphic invariants:

```text
direct restricted label                 => restricted
same label + tentative modal            => still restricted
disclaimer + separate restricted clause => still restricted
case/accent/punctuation variation       => same classification
contextual feeling + situational scope  => safe
```

No generic medical NLP subsystem is required.

---

## V5-I2 — Certainty polarity is still phrase-enumerated and fails common certainty/uncertainty constructions

**Severity:** Important

**Location:**

```text
cmm/domains/reflection/rules.py
_certainty_signal()
```

V4 correctly moved certainty inspection to system-conclusion surfaces and added
clause-level negation handling.

The remaining implementation still uses enumerated phrase tuples:

```text
_AFFIRMATIVE_CERTAINTY_IDIOMS
_DIRECT_AFFIRMATIVE_CERTAINTY
_NEGATED_CERTAINTY_PATTERNS
```

Independent V5 runtime observations:

### A. Explicit uncertainty false positive

Input:

```text
"Carezco de certeza suficiente para atribuirlo al rechazo"
```

Observed:

```text
forced_conclusion = true
valid_unresolved_completion = false
unsupported_certainty = ["certeza"]

CERTAINTY_NEGATED_ES_GATE=FAIL
```

The phrase is explicitly uncertain.

Root cause:

```text
"certeza" is an affirmative marker
"carezco de certeza" is not in the enumerated negation patterns
```

### B. Clear affirmative certainty false negatives

Input:

```text
"Sé con total seguridad que esa fue la causa"
```

Observed:

```text
forced_conclusion = false
valid_unresolved_completion = true
```

Input:

```text
"I know for certain that this explains everything"
```

Observed:

```text
forced_conclusion = false
valid_unresolved_completion = true
```

Both are clear unsupported-certainty constructions.

Root cause:

```text
"seguridad" is absent from the affirmative certainty concepts
"for certain" is absent from the affirmative English concepts
```

### C. Mixed-polarity false negative

Input:

```text
"No puedo asegurar todos los detalles, pero sé con total seguridad que él actuó por celos"
```

Observed:

```text
forced_conclusion = false
valid_unresolved_completion = true

CERTAINTY_MIXED_GATE=FAIL
```

The first clause correctly expresses uncertainty, but the second clause is an
independent affirmative-certainty claim and must still force the gate closed.

### Contract impact

The frozen specification requires:

```text
plausibility != certainty
reflection completed != conclusion reached
```

and explicitly requires successful unresolved completion.

The current implementation can still:

```text
reject genuine uncertainty
and
accept unsupported certainty
```

depending on synonym choice.

### Required remediation

Do not fix this by appending the four V5 strings.

Implement a deterministic **clause certainty stance**:

```text
affirmed
negated
none
```

Compose certainty from normalized concepts rather than whole-sentence entries.

At minimum cover concept families such as:

```text
Spanish:
certeza
seguridad
seguro
convencido
duda
hecho
demostrar/probar
claridad

English:
certain/certainty
sure
know for certain
conviction/convinced
doubt
fact
prove/demonstrate
clearly/definitely
```

Then apply polarity/operators:

```text
negated uncertainty:
no
sin
carecer de
falta de
no poder
uncertain / unsure / cannot / lack

affirmative certainty:
tener
estar
saber
con total
absoluta
for certain
definitely
no-doubt idioms
```

Special affirmative idioms that contain surface negation remain affirmative:

```text
no hay duda
no cabe duda
there is no doubt
```

Clause combination invariant:

```text
any independent affirmed certainty clause
=> forced conclusion

unless that exact certainty occurrence is negated
```

Do not globally suppress an affirmative clause because a different clause
expresses uncertainty.

Required metamorphic invariants:

```text
affirmative certainty                => forced
same certainty explicitly negated    => safe
uncertainty clause + contrast + certainty clause
                                       => forced
certainty only in evidence/quote      => irrelevant
structural certain/final marker       => forced regardless of text
case/punctuation variation            => same result
```

---

# 6. DP-024 V5 assessment

## Open-ended analysis

**REMEDIATION REQUIRED**

V5-I2 still rejects genuine uncertainty and accepts some clear certainty.

## Prudent hypotheses

**REMEDIATION REQUIRED**

V5-I1 leaves a fixed attachment classification as an ordinary stronger
hypothesis.

## Source-grounded interest mapping

**PASS**

No residual V5 finding.

## Confirmed persistence

**PASS**

No residual V5 finding.

Therefore:

```text
DP-024 = NOT YET VERIFIED
AT-DP-024 = NOT YET PASS
```

---

# 7. Required final remediation strategy

This is not another phrase-list patch.

The final remediation must replace the two free-text fallbacks with small,
compositional, testable classifiers inside the existing `rules.py`:

```text
_diagnostic_clause_class(...)
    -> restricted | disclaimer | contextual | none

_certainty_clause_stance(...)
    -> affirmed | negated | none
```

The public behavior remains unchanged.

No new production module.
No new dependency.
No new model/classifier service.

The important change is architectural at the helper level:

```text
whole phrase enumeration
→ normalized clause decomposition + semantic operator/concept composition
```

---

# 8. Required closure verification

The final remediation must preserve:

```text
all V1/V2/V3/V4 closures
VALIDATE
persistence binding
interest
temporal
JSON
presentation safety
package boundary
global pytest
Ruff Phase 10.24
py310
compileall
fresh import
diff check
```

It must add permanent V5 closure tests and an independent-style pre-V6
**metamorphic** gauntlet.

The gauntlet should vary:

```text
wording
modal presence
negation
clause order
contrast connectors
case
accent
punctuation
Spanish/English
```

without merely copying committed fixtures.

---

# 9. Final V5 status

```text
Phase 10.24 — Implemented, remediation required

Critical: 0
Important: 2
Minor: 0

Independent Audit V5: REMEDIATION REQUIRED
DP-024: NOT YET VERIFIED
AT-DP-024: NOT YET PASS
```

No remediation was performed during this audit.
No push.
No merge.
