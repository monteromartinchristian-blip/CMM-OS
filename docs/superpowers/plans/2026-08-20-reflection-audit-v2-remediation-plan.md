# Phase 10.24 Reflection Audit V2 Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the five Important findings from Phase 10.24 Independent Audit V2 without reopening the already-closed V1 surface.

**Architecture:** Keep the remediation narrow. Reflection fixes remain inside the existing 14-module package. The only approved shared production surface is the existing shared workflow runtime for V2-I1. Persistence must reuse an existing authoritative shared confirmation/approval contract; if no sufficient contract exists, stop and report the exact missing primitive rather than creating new shared infrastructure.

**Tech Stack:** Python 3.10+, pytest, Ruff, existing CMM OS domain/workflow/permission/memory contracts.

**Spec:** `docs/superpowers/specs/2026-08-20-reflection-domain-design.md`

## Global Constraints

- Domain ID remains exactly `domain:reflection`.
- Reflection package remains exactly 14 production modules.
- No new Reflection memory store, workflow engine, temporal engine, approval subsystem, or permission subsystem.
- No external Notion write.
- No automatic durable personal decision.
- No silent semantic-memory persistence.
- Literal booleans must not be widened by Python truthiness/equality.
- Conflicting evidence/state fails closed.
- Same source repetition does not become independent corroboration.
- Psychological/identity hypothesis must not be presented as diagnosis or stable classification.
- Open-ended unresolved Reflection must not be converted into a forced conclusion.
- No push.
- No merge.
- Final status after remediation: `Phase 10.24 — Implemented, pending independent audit V3`.

---

### Task 1: Close V2-I1 — strict shared VALIDATE semantics

**Files:**
- Modify: `cmm/workflows/engine.py`
- Modify: `tests/workflows/test_validate_gate_regression.py`
- Test: existing workflow/domain regression suites

**Interfaces:**
- Consumes: existing `WorkflowNode.wait_condition`, node dependency outputs, existing workflow run/failure model.
- Produces: fail-closed shared validation that is strict for booleans and conflict-aware across dependency outputs.

- [ ] **Step 1: Add RED test for strict boolean validation**

Add a regression equivalent to:

```python
def test_validate_rejects_numeric_one_for_expected_true():
    result = run_validate(
        wait_condition={"flag": True},
        dependency_outputs={"producer": {"flag": 1}},
    )
    assert result.run.status is not WorkflowRunStatus.COMPLETED
```

Run only this test and verify it fails on the pre-fix implementation because `1 == True`.

- [ ] **Step 2: Add RED test for conflicting dependency state**

Use two dependencies:

```text
A: {"safe": False}
Z: {"safe": True}
condition: {"safe": True}
```

Assert validation does not complete.

Run it and verify RED.

- [ ] **Step 3: Implement minimal strict comparison**

For boolean expectations:

```text
expected True  => actual must be `is True`
expected False => actual must be `is False`
```

Do not use ordinary equality for booleans.

Preserve existing equality semantics for non-boolean values only where the existing shared contract requires them.

- [ ] **Step 4: Implement conflict collection**

When the same validation key is found in multiple relevant dependency outputs:

```text
all observed values compatible with expected => may pass
any conflicting/malformed observed value => fail closed
missing everywhere => fail closed
```

Do not use first-match or last-match behavior.

- [ ] **Step 5: GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/workflows/test_validate_gate_regression.py
```

Then run all existing workflow runtime tests affected by `cmm/workflows/engine.py`.

---

### Task 2: Close V2-I2 — authoritative persistence confirmation

**Files:**
- Modify: `cmm/domains/reflection/rules.py`
- Test: `tests/domains/test_reflection_domain_audit_v2_closure.py`
- Inspect first: existing shared approval / confirmation / memory decision contracts

**Interfaces:**
- Consumes: an existing authoritative shared confirmation/approval object or reference.
- Produces: persistence classification that cannot be confirmed by an arbitrary caller-shaped mapping.

- [ ] **Step 1: Inventory the real shared contract before editing**

Search the repository for the canonical approval/confirmation path:

```bash
rg -n \
  'Approval|approval|Confirmation|confirmation|request_id|decision_id|approved|authoriz' \
  cmm tests
```

Identify:

```text
canonical type/object
how validity/authenticity is represented
how request/decision identity is bound
how approval state is read
whether a shared registry/store/reference check exists
```

If no existing shared contract can distinguish an authoritative confirmation from:

```python
{"decision_id": "fake", "request_id": "fake", "approved": True}
```

**STOP** and report:

```text
SHARED_CONFIRMATION_PRIMITIVE_MISSING
```

with the exact missing contract and the minimal shared proposal required.

Do not invent a Reflection-local approval system.

- [ ] **Step 2: Add RED fake-mapping regression**

Exact class:

```python
confirmation = {
    "decision_id": "fake-decision",
    "request_id": "fake-request",
    "approved": True,
}
```

Assert:

```text
confirmed = false
authorization_accepted = false
```

Run and verify RED.

- [ ] **Step 3: Add RED authoritative-confirmation test**

Using the actual canonical shared contract found in Step 1, construct a genuinely valid approved confirmation and prove it can authorize the persistence transition when the grounded basis is otherwise sufficient.

Do not mock authenticity away.

- [ ] **Step 4: Implement minimal binding**

Reflection may translate/read the shared object, but must not recreate its validity rules locally.

Required:

```text
raw True => insufficient
arbitrary mapping => insufficient
wrong/missing reference => insufficient
nonliteral approved state => insufficient
authoritative valid shared approval => eligible
```

- [ ] **Step 5: GREEN**

Run the targeted V2 tests plus existing Reflection memory/persistence tests.

---

### Task 3: Close V2-I3 — interest uncertainty based on independent grounded sources

**Files:**
- Modify: `cmm/domains/reflection/rules.py`
- Test: `tests/domains/test_reflection_domain_audit_v2_closure.py`

**Interfaces:**
- Consumes: normalized/deduplicated grounded source identities already produced by `map_interests()`.
- Produces: uncertainty/relative-strength state driven by independent grounded sources rather than mention count.

- [ ] **Step 1: RED one-source-many-mentions**

Input:

```python
(
    {
        "interest": "photography",
        "source": "msg:one",
        "source_kind": "user_statement",
        "recording": "I like photography",
    },
    {
        "interest": "photography",
        "source": "msg:one",
        "source_kind": "user_statement",
        "recording": "Photography interests me",
    },
)
```

Assert:

```text
mention_count = 2
grounded_evidence_count = 1
independent_grounded_count = 1
uncertainty = true
```

Run and verify RED.

- [ ] **Step 2: RED two-independent-source contrast**

Use two genuinely different grounded source IDs and assert the implementation can distinguish that case from one-source repetition.

Do not automatically make `persistent_confirmed=true`.

- [ ] **Step 3: Implement minimal confidence calculation**

Use:

```text
independent_grounded_count
counterevidence
grounding validity
```

for confidence/uncertainty.

`mention_count` remains descriptive only.

- [ ] **Step 4: GREEN**

Run targeted interest tests and existing DP-024 interest tests.

---

### Task 4: Close V2-I4 — Spanish diagnosis / restricted-inference boundary

**Files:**
- Modify: `cmm/domains/reflection/rules.py`
- Modify if needed: `cmm/domains/reflection/presentation.py`
- Test: `tests/domains/test_reflection_domain_audit_v2_closure.py`

**Interfaces:**
- Consumes: hypothesis statement + existing structural safety metadata.
- Produces: deterministic safe representation that does not present direct diagnostic/stable identity classification as an ordinary prudent hypothesis.

- [ ] **Step 1: RED Spanish cases**

At minimum:

```text
"Eres narcisista"
"Tienes trastorno bipolar"
"Tienes un trastorno de apego"
"Eres una persona manipuladora"
```

Assert each direct classification is marked diagnostic/restricted as appropriate and is not presented verbatim as a safe `diagnosis=false` hypothesis.

Run and verify RED.

- [ ] **Step 2: Protect legitimate hypotheses**

Add safe contrast cases such as:

```text
"Una posibilidad es que esta situación te genere ambivalencia"
"Podría haber varias explicaciones y no hay base para concluir una"
```

Assert these remain usable as hypotheses.

- [ ] **Step 3: Implement narrow bilingual safety boundary**

Prefer existing structural markers.

Where free-text detection is unavoidable, use a small deterministic normalized English/Spanish restricted vocabulary/pattern set consistent with the frozen spec.

Do **not** build a medical classifier or general NLP subsystem.

- [ ] **Step 4: Presentation parity**

A restricted/diagnostic hypothesis must remain restricted at presentation.

The user-facing statement must not contradict its metadata.

- [ ] **Step 5: GREEN**

Run targeted diagnosis/restricted-inference tests and all existing Reflection safety tests.

---

### Task 5: Close V2-I5 — Spanish unsupported certainty / forced conclusion

**Files:**
- Modify: `cmm/domains/reflection/rules.py`
- Modify if required: `cmm/domains/reflection/operations.py`
- Modify if required: `cmm/domains/reflection/presentation.py`
- Test: `tests/domains/test_reflection_domain_audit_v2_closure.py`

**Interfaces:**
- Consumes: unresolved state, conclusion/certainty metadata, free-text conclusion only as a secondary safety signal.
- Produces: unresolved Reflection that cannot be silently treated as resolved by unsupported certainty wording.

- [ ] **Step 1: RED Spanish forced-certainty cases**

At minimum:

```text
"Es evidente que soy narcisista"
"Está claro que todo se debe a un trauma"
"Esto demuestra que él nunca me quiso"
```

with:

```text
unresolved = true
```

Assert:

```text
forced_conclusion = true
valid_unresolved_completion = false
```

Run and verify RED.

- [ ] **Step 2: Add tentative contrast**

Examples:

```text
"Una posibilidad es que haya influido el contexto"
"No puedo concluirlo, pero esta hipótesis merece consideración"
```

Assert they do not become forced conclusions.

- [ ] **Step 3: Implement structural-first enforcement**

The primary rule must use the structural state:

```text
unresolved
certainty/provenance state
conclusion adoption status
```

Free-text markers are a secondary backstop.

Add minimal English/Spanish certainty markers only where needed.

- [ ] **Step 4: Preserve summary/presentation parity**

No summary or presentation layer may turn the blocked conclusion back into a resolved assertion.

- [ ] **Step 5: GREEN**

Run targeted rule + operation + presentation tests.

---

### Task 6: Permanent V2 closure suite and documentation

**Files:**
- Create: `tests/domains/test_reflection_domain_audit_v2_closure.py`
- Modify: `docs/reference/reflection-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Include: `docs/superpowers/plans/2026-08-20-reflection-audit-v2-remediation-plan.md`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: permanent regression evidence and status `pending independent audit V3`.

- [ ] **Step 1: V2 closure matrix**

Permanent tests must cover:

```text
VALIDATE_LITERAL_BOOL_GATE
VALIDATE_CONFLICT_GATE
PERSISTENCE_SHARED_CONTRACT_GATE
INTEREST_SINGLE_SOURCE_UNCERTAINTY_GATE
DIAGNOSIS_SPANISH_GATE
NO_FORCED_CONCLUSION_SPANISH_GATE
```

Also include positive contrasts so a fail-closed fix does not simply disable valid behavior.

- [ ] **Step 2: Update documentation**

Document V2 remediation concisely.

Final docs status:

```text
Phase 10.24 — Implemented, pending independent audit V3
DP-024 — pending independent audit V3
```

Do not mark Complete.

- [ ] **Step 3: Run full verification ladder**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_reflection_domain_audit_v1_closure.py \
  tests/domains/test_reflection_domain_audit_v2_closure.py

.venv/bin/python -m pytest -q tests/workflows/test_validate_gate_regression.py

.venv/bin/python -m pytest -q tests/domains/test_reflection_domain_*.py

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

- [ ] **Step 4: Review scope**

Allowed shared production change:

```text
cmm/workflows/engine.py
```

Any additional shared production file requires explicit justification and human approval, except use/import of an already-existing shared confirmation contract without modifying it.

Reject new subsystem/module creation.

- [ ] **Step 5: Commit once**

After all tests are green:

```bash
git add <intended files>
git diff --cached --check
git diff --cached --stat
git diff --cached

git commit -m "fix(domains): remediate phase 10.24 audit v2 findings"
```

No amend. No push. No merge.

- [ ] **Step 6: Clean-state verification after commit**

Rerun the full ladder on committed HEAD and verify:

```text
working tree clean
Phase 10.24 — Implemented, pending independent audit V3
```
