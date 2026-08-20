# Phase 10.24 Reflection — Final Audit V4 Micro-Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the final two semantic blockers and one diff-hygiene issue from Independent Audit V4 without changing the now-accepted VALIDATE, persistence, interest, temporal, or package architecture.

**Architecture:** Treat diagnosis/classification and certainty as polarity-sensitive semantic gates. Do not expand another flat phrase blacklist. Preserve strict structural safety markers, distinguish explicit diagnostic labels from contextual symptom hypotheses and diagnostic disclaimers, and distinguish affirmative certainty from explicit uncertainty. Keep all changes inside existing Reflection rules/tests except the EOF-only workflow test cleanup.

**Tech Stack:** Python 3.10+, pytest, Ruff, existing CMM OS Reflection contracts.

**Spec:** `docs/superpowers/specs/2026-08-20-reflection-domain-design.md`

## Global Constraints

- Reflection remains exactly 14 production modules.
- Do not change `cmm/workflows/engine.py` behavior.
- Do not change memory contracts, memory validator, or persistence architecture.
- Do not change interest/temporal architecture.
- No new NLP subsystem.
- No new dependency.
- Explicit diagnostic disclaimer must not become diagnosis merely because it contains `diagnos*`.
- Tentative wording must not sanitize an actual diagnostic/classification label.
- Explicit negation of certainty must remain uncertainty.
- A separate affirmative-certainty clause must still be detected.
- Global pytest must pass.
- Phase 10.24 changed-surface Ruff and Ruff py310 must pass.
- `git diff --check` must pass.
- No push.
- No merge.
- Final status after remediation: `Phase 10.24 — Implemented, pending independent audit V5`.

---

## Task 1 — V4-I1: diagnosis/classification polarity

**Files**
- Modify: `cmm/domains/reflection/rules.py`
- Add: `tests/domains/test_reflection_domain_audit_v4_closure.py`
- Extend neighboring Reflection safety tests only when necessary

### Root cause

Current tentative handling is:

```python
if is_tentative:
    return bool(
        "trastorno" in lowered
        or "disorder" in lowered
        or "diagnos" in lowered
        or "esquizofren" in lowered
    )
```

This makes `diagnos*` inside a disclaimer unsafe while allowing other tentative
diagnostic labels.

### Required classification model

Distinguish four classes:

```text
A. diagnostic/classification assertion
B. tentative diagnostic/classification assertion
C. contextual symptom/function hypothesis
D. explicit disclaimer/denial of diagnostic authority
```

Both A and B are restricted.

C and D remain prudent non-diagnostic hypotheses unless another structural
restriction independently applies.

### RED tests — exact V4 failures

Must fail before code changes:

```text
"Podría estar atravesando un periodo de tristeza; no hay base para diagnosticar"
=> non-diagnostic

"Podría ser bipolar"
=> restricted

"Could have depression"
=> restricted

"Puede que tenga ansiedad"
=> classify according to direct-condition semantics, not merely tentative token
```

### Required additional matrix

Safe disclaimers:

```text
"No hay base para diagnosticar depresión; solo describo tristeza"
"No puedo diagnosticar esto"
"This is not a diagnosis; one possibility is situational sadness"
"There is no basis to diagnose a disorder here"
```

Restricted tentative diagnoses:

```text
"Podría tener trastorno bipolar"
"Podría ser bipolar"
"Puede que tenga depresión mayor"
"Might have major depression"
"Could have an anxiety disorder"
"They may have an avoidant attachment disorder"
```

Safe contextual hypotheses:

```text
"Podría estar sintiendo ansiedad en esta situación"
"Puede que esta situación esté generando tristeza"
"May be feeling anxious because of this event"
"One possibility is temporary sadness after the loss"
```

Direct assertions remain restricted:

```text
"Padece depresión mayor"
"Tiene un trastorno de ansiedad"
"You have major depression"
```

### Implementation constraints

Prefer small helpers such as:

```text
diagnostic disclaimer detector
direct diagnostic-label detector
contextual symptom/tentative detector
```

Do not turn the entire statement into a bag-of-words classification.

A disclaimer may neutralize its own `diagnos*` token but must not neutralize a
separate affirmative diagnostic clause.

Example:

```text
"No puedo diagnosticar, pero eres bipolar"
=> restricted
```

Structural `diagnostic=True`, `restricted_inference=True`, and restricted
`classification_kind` remain stronger than lexical safe framing.

---

## Task 2 — V4-I2: certainty polarity

**Files**
- Modify: `cmm/domains/reflection/rules.py`
- Add/extend: `tests/domains/test_reflection_domain_audit_v4_closure.py`

### Root cause

Conclusion-scoped certainty detection is now correctly scoped, but marker
matching ignores polarity.

### RED exact reproductions

```text
unresolved=True
conclusion="No tengo certeza de que fuera por rechazo"
=> forced_conclusion=False

"No estoy seguro de que esa sea la causa"
=> false

"No hay ninguna certeza sobre la causa"
=> false
```

### Affirmative controls

Must remain forced:

```text
"Tengo certeza de que fue por rechazo"
"Estoy seguro de que esa fue la causa"
"Sin duda esa fue la causa"
"No hay ninguna duda: esa es la causa"
"There can be no doubt that this was the cause"
```

### Mixed-polarity controls

These MUST remain forced:

```text
"No estoy seguro, pero sin duda esa fue la causa"
"No tengo certeza sobre todo, aunque definitivamente él lo hizo por celos"
"I'm not certain about everything, but there can be no doubt this caused it"
```

### Tentative controls

Must remain valid unresolved completion:

```text
"No puedo concluir una causa"
"Puede ser una posibilidad, pero no estoy seguro"
"I cannot be certain; the evidence is incomplete"
```

### Implementation constraints

Do not globally short-circuit on the presence of an uncertainty phrase.

Preferred model:

```text
1. structural final/certain/adopted state remains strongest
2. inspect conclusion text only
3. identify affirmative-certainty spans/clauses
4. suppress certainty markers only when the same semantic occurrence is explicitly negated
5. preserve affirmative-certainty idioms whose surface contains negation:
   "no hay duda"
   "no cabe duda"
   "there is no doubt"
```

A small deterministic uncertainty-marker set is acceptable.

Do not reintroduce whole-result scanning.

---

## Task 3 — V4-M1: diff hygiene

**Files**
- Modify only EOF formatting: `tests/workflows/test_validate_gate_regression.py`

Required:

```text
exactly one terminating newline
no extra blank line at EOF
```

Run:

```bash
git diff --check
```

Expected: exit 0.

No semantic workflow changes.

---

## Task 4 — Permanent V4 closure suite

**Create**
- `tests/domains/test_reflection_domain_audit_v4_closure.py`

Required minimum groups:

```text
DIAGNOSIS POLARITY
- 4 safe diagnostic disclaimers
- 6 tentative direct diagnoses restricted
- 4 contextual symptom hypotheses safe
- 3 direct diagnoses restricted
- mixed disclaimer + affirmative diagnosis restricted
- structural restriction wins

CERTAINTY POLARITY
- 3 negated certainty conclusions safe
- 5 affirmative certainty conclusions blocked
- 3 mixed uncertainty + affirmative certainty blocked
- 3 tentative conclusions safe
- quoted evidence remains irrelevant
- structural certainty remains blocked

REGRESSION
- V3 unseen diagnosis examples still blocked
- V3 quoted-evidence behavior stays safe
- strict JSON
- input non-mutation
```

---

## Task 5 — Pre-V5 independent-style gauntlet

Create `/tmp/phase-10.24-pre-v5-probe.py`, never commit it.

Use phrases absent from V4 closure tests.

Mandatory gates:

```text
PRE_V5_DIAG_DISCLAIMER
PRE_V5_DIAG_TENTATIVE_LABEL
PRE_V5_DIAG_CONTEXTUAL
PRE_V5_DIAG_MIXED
PRE_V5_CERTAINTY_NEGATED
PRE_V5_CERTAINTY_AFFIRMATIVE
PRE_V5_CERTAINTY_MIXED
PRE_V5_QUOTED_EVIDENCE
PRE_V5_VALIDATE_REGRESSION
PRE_V5_PERSISTENCE_REGRESSION
PRE_V5_STRICT_JSON
PRE_V5_NON_MUTATION
ALL_PRE_V5_GATES_PASS=true
```

Persistence regression must use the real validated binding/inventory fixture,
not a standalone snapshot.

---

## Task 6 — Full verification and commit

Update status docs:

```text
docs/reference/reflection-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
docs/superpowers/plans/2026-08-20-reflection-audit-v4-final-micro-remediation-plan.md
```

Set:

```text
Phase 10.24 — Implemented, pending independent audit V5
DP-024 — pending independent audit V5
```

### Mandatory verification

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_reflection_domain_audit_v1_closure.py \
  tests/domains/test_reflection_domain_audit_v2_closure.py \
  tests/domains/test_reflection_domain_audit_v3_closure.py \
  tests/domains/test_reflection_domain_audit_v4_closure.py \
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

Do not require unrelated repository-wide Ruff debt to be fixed; report global
Ruff separately if run.

### Commit

One commit:

```bash
git commit -m "fix(domains): close phase 10.24 audit v4 findings"
```

No amend.
No push.
No merge.

### Post-commit

Rerun all commands above plus the pre-V5 gauntlet.

Working tree must be clean.

Final status:

```text
Phase 10.24 — Implemented, pending independent audit V5
```
