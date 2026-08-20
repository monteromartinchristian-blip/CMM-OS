# Phase 10.24 Reflection — Audit V3 Definitive Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all Phase 10.24 Independent Audit V3 findings at their root cause and leave a pre-V4 closure surface strong enough for final independent audit.

**Architecture:** Keep Reflection inside the frozen 14-module boundary. The only shared runtime change is the existing `cmm/workflows/engine.py` VALIDATE implementation. Persistence confirmation must reuse the already-existing Phase 10.18 memory binding/inventory validator; a standalone approval snapshot is schema-only evidence and can never authorize persistence. Diagnosis and forced-conclusion protection must become structural-first, with narrow bilingual lexical backstops rather than growing whole-tree phrase blacklists.

**Tech Stack:** Python 3.10+, pytest, Ruff, existing CMM OS domain memory/workflow contracts.

**Spec:** `docs/superpowers/specs/2026-08-20-reflection-domain-design.md`

## Global Constraints

- Domain ID remains exactly `domain:reflection`.
- Reflection package remains exactly 14 production modules.
- No new Reflection memory store, approval registry, workflow engine, temporal engine, permission engine, or persistence engine.
- No modification to shared memory contracts or shared memory validator unless an actually missing primitive is demonstrated and human approval is obtained first.
- `DomainMemoryApprovalDecisionSnapshot` is reference-only and is NOT sufficient confirmation by itself.
- Valid persistence confirmation must pass the existing shared binding/inventory validator.
- Shared VALIDATE may read metadata/run inputs and declared dependency outputs only; unrelated node outputs must not affect a gate.
- Literal boolean semantics remain strict.
- Diagnosis/restricted-inference safety must not rely exclusively on a finite disease-word list.
- NoForcedConclusion must inspect conclusion/system assertion surfaces structurally; quoted/source/evidence text must not trigger it.
- All public outputs remain strict JSON-safe and non-mutating.
- Global suite must be green on committed HEAD.
- Ruff and Ruff py310 must be green.
- No push.
- No merge.
- Final status after remediation: `Phase 10.24 — Implemented, pending independent audit V4`.

---

## Task 1 — V3-I1: scope shared VALIDATE to declared dependencies

**Files**
- Modify: `cmm/workflows/engine.py`
- Modify: `tests/workflows/test_validate_gate_regression.py`
- Add V3 closure coverage: `tests/domains/test_reflection_domain_audit_v3_closure.py`

### Root cause

`_evaluate_validate_node()` currently iterates over every accumulated workflow output:

```python
for node_id, node_output in outputs.items():
```

and therefore unrelated nodes can satisfy or conflict with a condition.

### RED matrix

Add tests proving all of these before implementation:

```text
A. unrelated=True, declared dependency missing field, expected=True
   => FAIL/CLOSED, unrelated node cannot satisfy

B. unrelated=False, declared dependency=True, expected=True
   => PASS, unrelated node cannot manufacture conflict

C. declared A=False, declared Z=True, expected=True
   => FAIL condition_conflict

D. declared A=True, declared Z=True, expected=True
   => PASS

E. declared A=1, expected=True
   => FAIL

F. metadata has static allowed=True, declared dependency does not define allowed,
   and workflow contract intentionally uses metadata condition
   => preserve current valid metadata semantics where applicable

G. declared dependency output overrides conflicting metadata default
   => runtime declared dependency remains authoritative
```

Do not write tests using only Reflection workflow metadata. Exercise the common workflow engine directly.

### GREEN implementation

Collect dynamic observations only from:

```python
node.dependencies
```

not all `outputs`.

A robust outline is:

```text
dependency_ids = set(node.dependencies)

for dependency_id in node.dependencies:
    dependency_output = outputs.get(dependency_id)
    if Mapping:
        collect only condition fields
```

Preserve:

```text
metadata
run.inputs
node_id keyed dependency output
```

where current contracts need them.

Do not let a completed unrelated node override or conflict with the validation state.

### Verification

Run:

```bash
.venv/bin/python -m pytest -q tests/workflows/test_validate_gate_regression.py
```

Then all workflow tests.

---

## Task 2 — V3-I2: replace snapshot-shaped persistence authorization with validated shared binding chain

**Files**
- Modify: `cmm/domains/reflection/rules.py`
- Use existing: `cmm/domains/reflection/memory.py`
- Use existing: `cmm/domains/memory_contracts.py`
- Use existing: `cmm/domains/memory_validation.py`
- Modify existing Reflection persistence/DP-024/adversarial tests
- Add: `tests/domains/test_reflection_domain_audit_v3_closure.py`

### Existing authoritative path

The repository already provides:

```text
DomainMemoryProposalBinding
DomainMemoryReferenceInventory
validate_reflection_memory_binding(...)
DefaultDomainMemoryIntegrationValidator.validate_binding(...)
```

The shared validator checks:

```text
view
trace
proposal coverage
proposal kind
affected references
permissions
proposal.requires_confirmation
approval request belongs to proposal
approval decision belongs to request
approved is literal True
no extra/unlinked approval request/decision
```

Use it. Do not recreate those checks inside `rules.py`.

### Required API behavior

Preserve backward compatibility only to fail closed.

A standalone:

```python
DomainMemoryApprovalDecisionSnapshot(...)
```

must no longer authorize.

A raw mapping or raw boolean must remain denied.

The persistence classifier must receive enough existing shared objects to validate the confirmation chain. Preferred minimal interface:

```python
classify_persistence(
    record,
    *,
    confirmation=None,              # legacy input; never sufficient alone
    confirmation_binding=None,      # DomainMemoryProposalBinding
    confirmation_inventory=None,    # DomainMemoryReferenceInventory
)
```

Equivalent naming is acceptable only if it remains explicit and typed.

### Binding to the exact Reflection proposal

A valid confirmation must be tied to the relevant proposal, not merely any approved Reflection proposal.

Require a proposal identity in the persistence input, for example:

```text
record["proposal_id"]
```

and verify:

```text
exactly one relevant Reflection memory proposal
record proposal_id is bound by confirmation_binding
binding.domain_id == domain:reflection
binding has no unrelated agent-knowledge proposal
shared validate_reflection_memory_binding(...).is_valid is True
```

Do not infer proposal identity from the approval decision alone.

If current calling surfaces cannot supply the proposal ID, leave the persistence state at candidate/pending; do not invent a fallback.

### RED matrix

Permanent tests must prove:

```text
1. raw True => denied
2. arbitrary Mapping approved=True => denied
3. standalone DomainMemoryApprovalDecisionSnapshot approved=True => denied
4. binding without inventory => denied
5. inventory without binding => denied
6. invalid binding => denied
7. wrong proposal_id => denied
8. approval request for different proposal => denied
9. decision for different request => denied
10. approved=False => denied/rejected
11. unlinked extra approval => denied
12. wrong domain binding => denied
13. valid Reflection proposal→request→approved decision chain + valid inventory/binding => accepted
14. same valid chain but insufficient evidence basis => not confirmed
15. valid confirmation never writes memory
```

Build the valid fixture using the real Reflection memory builders and the real shared inventory snapshots, modeled after existing Phase 10.18 validation tests.

### Implementation

`rules.py` may import the existing Reflection memory validation helper locally to avoid cycles.

Do not change:

```text
cmm/domains/memory_contracts.py
cmm/domains/memory_validation.py
```

unless you first STOP and report a genuinely missing contract.

---

## Task 3 — V3-I3: structural-first diagnosis / restricted-inference safety

**Files**
- Modify: `cmm/domains/reflection/rules.py`
- Modify if required: `cmm/domains/reflection/presentation.py`
- Modify if required: `cmm/domains/reflection/operations.py`
- Add V3 closure tests

### Root cause

`_diagnostic_signal()` is currently a finite substring/prefix vocabulary. That catches examples already known to tests but does not express the semantic boundary.

### Required model

Determine restriction in this order:

```text
1. explicit structural safety markers
2. direct stable-person/condition classification shape
3. narrow normalized bilingual diagnostic lexical backstop
4. otherwise tentative hypothesis remains allowed
```

Preserve safe user-provided identity narratives as narratives; do not silently promote them to facts.

### Structural fields

When present, honor strict literal values such as:

```text
diagnostic
restricted_inference
classification_kind
identity_claim
```

Nonliteral truthy values must not widen safety.

Suggested restricted `classification_kind` values:

```text
diagnosis
mental_health_diagnosis
personality_classification
attachment_classification
stable_identity_classification
fixed_motive_classification
moral_character_classification
```

Do not require these fields for safety; they are the strongest signal when present.

### Direct-assertion backstop

Direct second-/first-person stable assertions without tentative framing should be conservative, for example:

```text
You are ...
You have ...
You suffer from ...
You are definitely ...
Eres ...
Soy ...
Tienes ...
Padeces ...
Sufres de ...
```

when the statement is classifying a psychological condition, stable personality, attachment, identity, motive, or moral character.

Tentative forms remain allowed:

```text
may
might
could
possibly
one possibility
podría
puede que
quizá
tal vez
una posibilidad
no hay base para concluir
```

### RED diagnostic variants not used in V2/V3

Use at least:

```text
"Padeces depresión mayor"
"Eres depresivo"
"Sufres de ansiedad"
"Tienes dependencia emocional"
"Tu apego es evitativo"
"Es una persona tóxica por naturaleza"
"Su motivo real es manipular"
"You suffer from major depression"
"You have an avoidant attachment style"
"You are emotionally dependent"
```

Positive controls:

```text
"Podría estar sintiendo ansiedad en esta situación"
"Una posibilidad es que evite el conflicto aquí"
"Puede que esta relación active inseguridad; no hay base para concluir una causa"
```

### Presentation invariant

Restricted/diagnostic input must not emerge as:

```text
diagnosis=false
restricted_inference=false
verbatim assertive classification
```

The safe output can redact/reframe the statement, but must preserve enough provenance to explain that the input was restricted.

Do not build a medical classifier.

---

## Task 4 — V3-I4: make NoForcedConclusion structural and conclusion-scoped

**Files**
- Modify: `cmm/domains/reflection/rules.py`
- Modify if required: `cmm/domains/reflection/operations.py`
- Modify if required: `cmm/domains/reflection/presentation.py`
- Add V3 closure tests

### Root cause

`no_forced_conclusion_policy()` recursively scans every string in the entire result. This simultaneously:

```text
misses certainty outside the phrase list
and
flags certainty quoted in evidence/source text
```

### Replace whole-tree scan

Do not call `_collect_text(result)` as the basis of forced-conclusion safety.

Define a narrow set of actual system conclusion surfaces, based on existing Reflection result contracts, for example:

```text
conclusion
final_conclusion
summary_conclusion
asserted_conclusion
recommendation
decision
```

Only include a field if it semantically expresses the system's conclusion. Do not scan:

```text
source
evidence
counterevidence
observation
quote
user_message
journal_entry
hypothesis text
memory provenance
```

### Structural-first state

When `unresolved is True`, treat structural certainty/adoption as forced if present:

```text
conclusion_status in {final, resolved, certain, fact}
certainty_state in {certain, definitive, absolute}
certainty_level in equivalent canonical states
fact is True
winner_selected is True
decision_adopted is True
conclusion_adopted is True
```

Use exact values from existing contracts if names differ.

Nonliteral truthy forms fail closed but must not be treated as valid adoption.

### Lexical backstop only on conclusion text

Add normalized bilingual certainty concepts broad enough for obvious assertions:

```text
certainty / certain / definitely / definitively / proven / proves
certeza / completamente seguro / definitivamente / demostrado / prueba que
sin duda / indudablemente / necesariamente
```

Do not simply add the exact V3 sentence.

### RED matrix

False negatives:

```text
"Tengo la certeza absoluta de que todo fue por rechazo"
"Definitivamente él actuó por celos"
"No hay ninguna duda: esa es la causa"
"This proves beyond doubt that rejection caused everything"
```

False positives that MUST remain valid unresolved reflection:

```text
evidence = "La otra persona dijo: 'obviamente no iba a venir'"
observation = "Escribió literalmente: 'está claro que no quiero hablar'"
counterevidence = "Un amigo aseguró que era definitivamente imposible"
```

with no system conclusion.

Tentative controls:

```text
"Una posibilidad es que influyera el rechazo"
"No puedo concluir una causa"
"Podría ser una explicación, pero hay incertidumbre"
```

### Parity

Rule, summary and presentation must preserve the blocked/open state consistently.

---

## Task 5 — V3-M1 and static hygiene

**Files**
- Fix import ordering in: `tests/domains/test_reflection_domain_audit_v1_closure.py`
- Run Ruff over entire changed surface

Use:

```bash
.venv/bin/ruff check --fix tests/domains/test_reflection_domain_audit_v1_closure.py
```

only if the resulting diff is import-order-only and reviewed.

Then:

```bash
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
```

Both must exit 0.

---

## Task 6 — Definitive V3 closure suite

**Files**
- Create: `tests/domains/test_reflection_domain_audit_v3_closure.py`

This suite must not merely repeat one test per finding.

Minimum permanent matrix:

```text
VALIDATE_DEPENDENCY_SCOPE:
  unrelated cannot satisfy
  unrelated cannot conflict
  declared conflict fails
  declared agreement passes
  literal bool remains strict
  metadata/input semantics preserved

PERSISTENCE_AUTHENTICITY:
  mapping denied
  snapshot alone denied
  invalid binding denied
  wrong proposal denied
  wrong request denied
  wrong decision denied
  false decision denied
  extra/unlinked approval denied
  valid inventory-backed chain accepted
  insufficient basis still not confirmed
  no memory mutation

DIAGNOSIS_RESTRICTION:
  ≥5 Spanish unseen direct classifications
  ≥3 English unseen direct classifications
  ≥3 tentative safe controls
  explicit structural restricted marker
  malformed structural marker fail-closed
  presentation parity

NO_FORCED_CONCLUSION:
  ≥4 unseen certainty conclusions
  ≥3 quoted/source certainty false-positive controls
  ≥3 tentative conclusion controls
  structural final/certain/fact flags
  malformed nonliteral flags
  presentation/summary parity

STRICT_JSON / NON_MUTATION:
  all new outputs `json.dumps(..., allow_nan=False)`
  representative inputs deep-copy equal after execution
```

---

## Task 7 — Independent-style temporary pre-V4 gauntlet

Before commit, create a temporary probe under `/tmp`, do not commit it.

It must use values absent from all committed V1/V2/V3 closure tests.

Required gates:

```text
V4_PRE_VALIDATE_UNRELATED_SATISFY
V4_PRE_VALIDATE_UNRELATED_CONFLICT
V4_PRE_VALIDATE_DECLARED_CONFLICT
V4_PRE_PERSISTENCE_STANDALONE_SNAPSHOT
V4_PRE_PERSISTENCE_WRONG_CHAIN
V4_PRE_PERSISTENCE_VALID_CHAIN
V4_PRE_DIAGNOSIS_UNSEEN_ES
V4_PRE_DIAGNOSIS_UNSEEN_EN
V4_PRE_DIAGNOSIS_TENTATIVE
V4_PRE_CONCLUSION_UNSEEN_CERTAINTY
V4_PRE_CONCLUSION_QUOTED_EVIDENCE
V4_PRE_CONCLUSION_TENTATIVE
V4_PRE_STRICT_JSON
V4_PRE_INPUT_NON_MUTATION
ALL_PRE_V4_GATES_PASS
```

The probe must derive PASS from assertions/actual results. No printed hard-coded success.

If any gate fails, remediation is not complete.

---

## Task 8 — Full verification, docs and single commit

Update:

```text
docs/reference/reflection-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
docs/superpowers/plans/2026-08-20-reflection-audit-v3-definitive-remediation-plan.md
```

Do not rewrite historical audit V1/V2/V3 artifacts.

Status:

```text
Phase 10.24 — Implemented, pending independent audit V4
DP-024 — pending independent audit V4
```

### Mandatory full ladder before commit

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_reflection_domain_audit_v1_closure.py \
  tests/domains/test_reflection_domain_audit_v2_closure.py \
  tests/domains/test_reflection_domain_audit_v3_closure.py \
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

.venv/bin/python -m compileall -q \
  cmm/domains/reflection \
  cmm/workflows/engine.py

.venv/bin/python - <<'PY'
import cmm.domains.reflection
import cmm.workflows.engine
print("fresh_import=OK")
PY

git diff --check
```

No known-failure exemption. Global must exit 0.

### Scope review

Reject:

```text
new Reflection production module
shared memory contract change
shared memory validator change
new approval registry
new workflow engine
new NLP/medical classifier subsystem
unrelated refactor
automatic memory mutation
external write
premature Complete/audited status
```

### Commit

One remediation commit:

```bash
git commit -m "fix(domains): close phase 10.24 audit v3 findings"
```

No amend.
No push.
No merge.

### Mandatory clean-state rerun

After commit, rerun:

```text
V1+V2+V3 closure
pre-V4 temporary gauntlet
Reflection
Workflows
Domains+Workflows
Domains
Global
Ruff
Ruff py310
compileall
fresh import
diff check
git status
```

Only then report:

```text
Phase 10.24 — Implemented, pending independent audit V4
```
