# Phase 10.24 Reflection — Audit V5 Compositional Closure Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close V5-I1 and V5-I2 by replacing phrase-enumerated free-text safety fallbacks with deterministic clause-level compositional classifiers, while preserving all accepted Phase 10.24 architecture.

**Architecture:** Keep all production changes in the existing `cmm/domains/reflection/rules.py`. Introduce private helper-level clause classifications only: diagnostic `{restricted, disclaimer, contextual, none}` and certainty `{affirmed, negated, none}`. Normalize case/accents/punctuation, decompose clauses, classify semantic operators and concept families, then aggregate conservatively. Do not add a new module, dependency, NLP service, workflow change, memory change, interest change, or temporal change.

**Tech Stack:** Python 3.10+, stdlib `re`/`unicodedata`, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-08-20-reflection-domain-design.md`

## Global Constraints

- Reflection remains exactly 14 production modules.
- Production behavior change limited to `cmm/domains/reflection/rules.py`.
- `cmm/workflows/engine.py` is frozen for this remediation.
- Persistence/memory contracts and validators are frozen.
- Interest and temporal logic are frozen.
- No dependency additions.
- No generic NLP or medical classifier.
- No phrase-list-only patch.
- Diagnostic tentative modality never sanitizes a restricted label.
- Diagnostic disclaimer never sanitizes a separate restricted clause.
- Contextual symptom hypotheses remain allowed.
- Certainty is conclusion-scoped and polarity-aware.
- Explicit uncertainty must not trigger forced conclusion.
- Any separate affirmative-certainty clause must still trigger forced conclusion.
- Global pytest must exit 0.
- Phase 10.24 Ruff + py310 must exit 0.
- `git diff --check` must exit 0.
- No push.
- No merge.
- Final status after remediation: `Phase 10.24 — Implemented, pending independent audit V6`.

---

## Task 1 — Build normalized clause primitives

**Files**
- Modify: `cmm/domains/reflection/rules.py`
- Create tests first in: `tests/domains/test_reflection_domain_audit_v5_closure.py`

### RED first

Add tests for case/accent/punctuation stability using examples that current code does not cover.

Diagnostic variants:

```text
"SU ESTILO DE APEGO ES PATOLÓGICO"
"Su estilo de apego es patologico."
"su estilo de apego es patológico"
```

All must classify identically.

Certainty variants:

```text
"SÉ CON TOTAL SEGURIDAD que fue eso."
"Se con total seguridad que fue eso"
"sé con total seguridad que fue eso"
```

All must classify identically.

### Implementation

Add a private normalization helper, for example:

```python
def _semantic_text(value: Any) -> str | None:
    ...
```

Requirements:

```text
casefold
Unicode NFKD accent folding for matching only
normalize punctuation/whitespace
preserve original statement in public output
JSON-safe
no mutation
```

Add one clause splitter shared by diagnostic/certainty helpers.

It must split at:

```text
sentence boundaries
semicolon
contrast connectors:
pero / aunque / sin embargo / no obstante
but / however / although / though
```

Do not split quoted evidence globally; these helpers receive only the specific
statement/conclusion string.

---

## Task 2 — V5-I1 compositional diagnostic clause classifier

**Files**
- Modify: `cmm/domains/reflection/rules.py`
- Test: `tests/domains/test_reflection_domain_audit_v5_closure.py`

### Private contract

Implement an internal classifier equivalent to:

```python
_DIAG_RESTRICTED = "restricted"
_DIAG_DISCLAIMER = "disclaimer"
_DIAG_CONTEXTUAL = "contextual"
_DIAG_NONE = "none"

def _diagnostic_clause_class(clause: str) -> str:
    ...
```

`_diagnostic_signal(statement)` then:

```text
split into clauses
classify each
if any restricted => True
else => False
```

A disclaimer does not globally neutralize another clause.

### Semantic components

Classify using combinations rather than exact sentences.

#### A. Attribution/operator families

Spanish:

```text
ser / es / eres / soy
tener / tiene / tienes / tenga
padecer / padece / padeces / padezca
sufrir / sufre / sufres
presentar / presenta / presentas
```

English:

```text
be / is / are
have / has
suffer from
present / exhibit
```

Tentative modals:

```text
podria / puede / tal vez / quiza
may / might / could / possibly
```

Tentative modality changes epistemic confidence, not restricted-label safety.

#### B. Restricted classification axes

Use normalized concept families:

```text
mental-health condition labels
stable personality labels
attachment labels/pathology
fixed moral character labels
essentialized motives
```

Do not require a single full phrase.

Attachment specifically must recognize compositional structures such as:

```text
su/tu estilo de apego ...
su/tu patron de apego ...
your/their attachment style/pattern ...
```

and restricted predicates such as:

```text
patologico
desorganizado
evitativo
ansioso
disordered
pathological
avoidant
disorganized
anxious
```

when used as fixed attachment classification.

#### C. Diagnostic disclaimer operators

Recognize polarity around diagnostic authority:

```text
no corresponde diagnosticar
no hay base para diagnosticar
no puedo diagnosticar
no es un diagnostico
sin diagnosticar
cannot diagnose
not a diagnosis
no basis to diagnose
```

A disclaimer clause is safe only if no independent restricted assertion remains
inside the same clause.

Examples:

```text
"No corresponde diagnosticar aquí"
=> disclaimer

"No puedo diagnosticar, pero tienes depresión mayor"
=> clauses: disclaimer + restricted
=> overall restricted
```

#### D. Contextual symptom framing

Recognize situational/experiential predicates such as:

```text
estar sintiendo
estar experimentando
sentirse
feeling
experiencing
```

combined with contextual scope:

```text
esta situacion
este episodio
ahora
temporalmente
because of this event
in this situation
after the loss
temporarily
```

These remain contextual unless a separate restricted diagnosis/classification
is asserted.

### Mandatory RED/GREEN matrix

Restricted:

```text
Su estilo de apego es patológico
Tu patrón de apego podría ser evitativo
Tal vez padezca un episodio depresivo mayor
They might have clinical depression
Your attachment pattern may be disordered
No puedo diagnosticar, pero tienes depresión mayor
This is not a diagnosis, but you have bipolar disorder
```

Safe:

```text
No corresponde diagnosticar aquí; solo describo malestar pasajero
No hay base para diagnosticar con estos datos
Podría estar sintiendo ansiedad en esta situación
Quizá esté experimentando nervios por este episodio concreto
May be feeling anxious because of this event
One possibility is temporary sadness after the loss
```

### Metamorphic tests

For each restricted base statement:

```text
+ tentative modal             => remains restricted
+ case changes                => unchanged
+ accent removal              => unchanged
+ terminal punctuation        => unchanged
+ disclaimer in other clause  => remains restricted
```

For contextual safe statements:

```text
case/accent/punctuation variants remain safe
```

Do not test only enumerated fixture strings; parameterize families.

---

## Task 3 — V5-I2 compositional certainty stance

**Files**
- Modify: `cmm/domains/reflection/rules.py`
- Test: `tests/domains/test_reflection_domain_audit_v5_closure.py`

### Private contract

Implement an internal helper equivalent to:

```python
_CERT_AFFIRMED = "affirmed"
_CERT_NEGATED = "negated"
_CERT_NONE = "none"

def _certainty_clause_stance(clause: str) -> str:
    ...
```

`_certainty_signal(text)` must aggregate clauses:

```text
if any clause affirmed => return affirmative marker
else => None
```

A negated clause does not suppress a separate affirmed clause.

### Certainty concepts

Spanish normalized concepts:

```text
certeza
seguridad
seguro
convencido
conviccion
duda
hecho
evidente
claro
demostrar
probar
definitivo
```

English:

```text
certain / certainty
sure
conviction / convinced
doubt
fact
evident
clear
prove / proven
demonstrate
definite / definitely
know for certain
```

### Polarity/operator families

Explicit uncertainty:

```text
no tengo
no estoy
no hay certeza
sin
carezco de
falta de
no puedo
no se puede
uncertain
unsure
not certain
not sure
lack
without
cannot
```

Affirmative certainty:

```text
tengo
estoy
se / sé
con total
absoluta
definitivamente
for certain
know
certainly
definitely
```

Special affirmative negation idioms remain affirmative:

```text
no hay duda
no cabe duda
sin duda
there is no doubt
there can be no doubt
```

### Mandatory RED/GREEN matrix

Safe uncertainty:

```text
Carezco de certeza suficiente para atribuirlo al rechazo
No tengo certeza de que esa sea la causa
No estoy seguro de que esa sea la causa
No hay ninguna certeza sobre la causa
I am unsure whether that was really the cause
I cannot be certain from the evidence
There is insufficient certainty to conclude
```

Forced certainty:

```text
Sé con total seguridad que esa fue la causa
Tengo certeza absoluta de que esa fue la causa
Estoy completamente convencido de que esa fue la causa
I know for certain that this explains everything
I am completely convinced this was the cause
There can be no doubt that this was the cause
No cabe duda de que esa fue la causa
```

Mixed — forced:

```text
No puedo asegurar todos los detalles, pero sé con total seguridad que él actuó por celos
No tengo certeza sobre todo, aunque estoy completamente convencido de que fue por rechazo
I'm unsure about the details, but I know for certain this caused it
```

Quoted evidence remains irrelevant:

```text
evidence contains "I know for certain..."
system conclusion = "No puedo determinar la causa"
=> safe
```

Structural certainty remains stronger:

```text
certainty_state="certain"
conclusion text tentative
=> forced
```

### Metamorphic tests

For each certainty family:

```text
affirmative form                    => forced
same concept with explicit negation => safe
case variation                      => unchanged
accent variation                    => unchanged
punctuation variation               => unchanged
prepend separate uncertainty clause + contrast + affirmative
                                      => forced
```

---

## Task 4 — Permanent V5 closure suite

**Create**
- `tests/domains/test_reflection_domain_audit_v5_closure.py`

The suite must be matrix/property-oriented, not a list of audit sentences.

Required groups:

```text
diagnostic_normalization
diagnostic_restricted_axes
diagnostic_tentative_invariance
diagnostic_disclaimer_scope
diagnostic_contextual_safe
diagnostic_mixed_clause
diagnostic_presentation_parity

certainty_normalization
certainty_affirmed
certainty_negated
certainty_special_no_doubt_idioms
certainty_mixed_clause
certainty_quoted_evidence
certainty_structural_override

strict_json
input_non_mutation
```

Use parametrization.

---

## Task 5 — Pre-V6 metamorphic gauntlet

Create `/tmp/phase-10.24-pre-v6-metamorphic.py`, never commit it.

It must generate combinations rather than only fixed examples.

### Diagnosis generation

Combine:

```text
modal:
"", "quizá ", "tal vez ", "podría ", "may ", "might "

subjects/frames:
"tu estilo de apego", "su patrón de apego", "your attachment pattern"

restricted predicates:
"es patológico", "es evitativo", "may be disordered"
```

Verify restricted across appropriate grammatical combinations.

Generate contextual safe variants with:

```text
sintiendo / experimentando / feeling
+
situational scope
```

### Certainty generation

Generate:

```text
affirmative operator
+
certainty concept
+
conclusion
```

and corresponding explicit-negation forms.

Also generate:

```text
uncertainty clause + contrast connector + affirmative certainty clause
```

which must always force.

### Mandatory output

```text
PRE_V6_DIAG_METAMORPHIC_GATE
PRE_V6_DIAG_DISCLAIMER_SCOPE_GATE
PRE_V6_DIAG_CONTEXT_GATE
PRE_V6_CERT_POLARITY_GATE
PRE_V6_CERT_MIXED_GATE
PRE_V6_CERT_QUOTED_GATE
PRE_V6_VALIDATE_REGRESSION_GATE
PRE_V6_PERSISTENCE_REGRESSION_GATE
PRE_V6_STRICT_JSON_GATE
PRE_V6_NON_MUTATION_GATE

ALL_PRE_V6_GATES_PASS=true
```

No hard-coded PASS.

---

## Task 6 — Preserve accepted architecture

Rerun:

```text
V1/V2/V3/V4/V5 closure
VALIDATE regression
persistence validated-chain regression
interest behavior via full V2 closure/full Reflection
Reflection
Workflows
Domains+Workflows
Domains
Global
```

Do not modify accepted subsystems to make tests pass.

---

## Task 7 — Documentation and single commit

Update:

```text
docs/reference/reflection-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
docs/superpowers/plans/2026-08-20-reflection-audit-v5-compositional-closure-remediation-plan.md
```

Historical audits are immutable.

Set:

```text
Phase 10.24 — Implemented, pending independent audit V6
DP-024 — pending independent audit V6
```

### Verification before commit

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_reflection_domain_audit_v1_closure.py \
  tests/domains/test_reflection_domain_audit_v2_closure.py \
  tests/domains/test_reflection_domain_audit_v3_closure.py \
  tests/domains/test_reflection_domain_audit_v4_closure.py \
  tests/domains/test_reflection_domain_audit_v5_closure.py \
  tests/workflows/test_validate_gate_regression.py

.venv/bin/python -m pytest -q tests/domains/test_reflection_domain_*.py
.venv/bin/python -m pytest -q tests/workflows
.venv/bin/python -m pytest -q tests/domains tests/workflows
.venv/bin/python -m pytest -q tests/domains
.venv/bin/python -m pytest -q

.venv/bin/ruff check \
  cmm/domains/reflection \
  cmm/workflows/engine.py \
  tests/domains/test_reflection_domain_*.py \
  tests/workflows/test_validate_gate_regression.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/reflection \
  cmm/workflows/engine.py \
  tests/domains/test_reflection_domain_*.py \
  tests/workflows/test_validate_gate_regression.py

.venv/bin/python -m compileall -q cmm/domains/reflection cmm/workflows/engine.py

.venv/bin/python - <<'PY'
import cmm.domains.reflection
import cmm.workflows.engine
print("fresh_import=OK")
PY

git diff --check
```

Global pytest must exit 0.

### Commit

```bash
git commit -m "fix(domains): close phase 10.24 audit v5 findings"
```

No amend.
No push.
No merge.

### Post-commit

Rerun the full ladder and the pre-V6 metamorphic gauntlet.

Working tree clean.

Final status:

```text
Phase 10.24 — Implemented, pending independent audit V6
```
