# Phase 10.25 — Concerns Domain — Independent Re-Audit Report

**Date:** 2026-08-23  
**Audit mode:** independent read-only review of fresh tracked-HEAD snapshot  
**Bundle:** `CMM-OS-phase-10.25-reaudit.tar.gz`  
**Bundle SHA-256:** `5f50fd5203b9799133513c64c699beae1b42bfd62e1ffa9f8d53db4154bb5eb3`  
**Audited HEAD:** `f9e7f14c0e24b254774722442d0638cc08d45c5d`  
**Previous implementation HEAD:** `7a4cabaa505b768574430d7a35ec2019dad5128b`

## Verdict

```text
AUDIT_VERDICT: FAIL — final remediation required
INDEPENDENT_AUDIT_STATUS: NOT_READY_TO_CLOSE
```

The first remediation materially improved the implementation. In particular, SupportNeed precedence, recurrence grounding, explicit no-advice/wait behavior, sibling-domain decoupling, operation schema tuple support, trace supporting-domain capacity, and the canonical package boundary are substantially improved.

However, the re-audit found remaining closure defects in reassurance runtime safety, workflow semantics, AT-DP-025 acceptance, caveat/risk enforcement, and presentation preservation.

---

# BLOCKER findings

## RB-001 — Authorized specialized reassurance result without `probability` crashes

**Severity:** BLOCKER  
**File:** `cmm/domains/concerns/rules.py:787-795`

### Defect

```python
if specialized_authorized:
    probability = specialized_domain_result.get("probability")
    numeric = _finite_number(probability)
    specialized_probability = numeric if 0.0 <= numeric <= 1.0 else None
```

`_finite_number(None)` returns `None`, then `0.0 <= None` raises `TypeError`.

An authorized specialized `domain_result` is not required to contain a numeric probability. A Health/Relationships/etc. result containing grounded semantics but no probability is a normal input.

### Independent reproduction

```text
evaluate_reassurance(
    target_claim="safe",
    evidence=(),
    specialized_domain_result={
        "authorized": True,
        "red_flags": ["danger"]
    }
)

=> TypeError:
   '<=' not supported between instances of 'float' and 'NoneType'
```

### Why current tests missed it

The specialized reassurance test covers an authorized result **with** `probability=0.02`; it does not probe an authorized specialized result where probability is absent, malformed, or null.

### Minimum remediation

```python
if numeric is not None and 0.0 <= numeric <= 1.0:
    specialized_probability = numeric
else:
    specialized_probability = None
```

Then add a matrix for:
- missing probability;
- `None`;
- string;
- NaN/Inf;
- valid 0/1;
- out-of-range finite values.

No malformed optional probability may raise.

---

## RB-002 — Workflow safety gates are field-reconciled but semantically wrong

**Severity:** BLOCKER  
**Files:**
- `cmm/domains/concerns/operations.py:581-616`
- `cmm/domains/concerns/operations.py:785-815`
- `cmm/domains/concerns/workflows.py:175-190`
- `cmm/domains/concerns/workflows.py:315-337`

The R2 remediation fixed direct dependency wiring, but two gates now validate the wrong semantic signal.

### RB-002a — material-question gate blocks correct suppression

`identify_open_questions_result()` correctly filters immaterial questions:

```python
if materiality["materiality"] != QUESTION_MATERIAL:
    ritual_suppressed += 1
    continue
```

A mixed candidate set can therefore validly return:

```text
1 material question
+ 1 immaterial question suppressed
=> ritual_questions_suppressed = 1
```

But Open Concern Conversation requires:

```python
wait_condition={"ritual_questions_suppressed": 0}
```

So the workflow blocks precisely when the operation successfully suppresses an immaterial/ritual question.

### Independent reproduction of producer output

Input:

```text
"Has this happened before?" -> material
"What font?"                 -> not material
```

Output:

```text
questions = 1 material question
ritual_questions_suppressed = 1
```

The workflow gate expects `0`.

### Correct invariant

The gate should prove:

```text
every emitted question is material
```

not:

```text
nothing ever had to be suppressed
```

A suppression count >0 is evidence the filter worked, not a violation.

---

### RB-002b — catastrophic-escalation gate does not evaluate canonical catastrophic promotions

`separate_reality_interpretation_result()` sets:

```python
catastrophic_escalation_present = bool(
    promotions_blocked_total or interpretation_promoted_to_fact
)
```

But `promotions_blocked_total` comes from `classify_concern_statement()`'s fact-grounding promotion guard, not from the canonical catastrophic taxonomy:

```text
possibility -> probability
ambiguity -> warning sign
change -> deterioration
silence -> rejection
symptom -> serious disease
setback -> failure
uncertainty -> danger
```

The real taxonomy lives in `detect_catastrophic_escalation()`, which the reassurance workflow does not execute.

Worse, a successfully blocked fact-label promotion yields:

```text
promotion_blocked=True
catastrophic_escalation_present=True
```

so the workflow can fail after the epistemic helper safely blocked the promotion.

### Independent producer reproduction

Input:

```python
{
    "statement": "they reject me",
    "level": "interpretation",
    "fact": True
}
```

Output:

```text
promotion_blocked = True
interpretation_promoted_to_fact = False
catastrophic_escalation_present = True
```

That is internally contradictory to the comment claiming the field means catastrophic escalation “survives” separation.

### Minimum remediation

Create/route a producer that evaluates the canonical transition pairs with `detect_catastrophic_escalation()` and returns a field with unambiguous semantics, e.g.:

```text
catastrophic_escalation_violation = True/False
```

The workflow gate should consume that actual result.

Do not reuse “blocked safely” as “unsafe still present”.

---

## RB-003 — AT-DP-025 is still not a production-path end-to-end acceptance proof

**Severity:** BLOCKER  
**File:** `tests/domains/test_concerns_domain_audit_r3.py:128-...`

The new test is substantially better than the first acceptance test, but it still does not prove the real end-to-end path.

### Problem 1 — resolver outcome is forced by a test-only scoring policy

The test constructs:

```python
DomainScoringPolicy(
    explicit_weight=300.0,
    supporting_margin=400.0
)
```

Production defaults are:

```text
explicit_weight = 100
supporting_margin = 15
```

The test also sets:

```python
explicit_domains=("domain:concerns",)
```

This is a hand-tuned context specifically chosen to force Concerns primary + Relationships supporting.

The acceptance therefore does not prove the standard configured resolver path required by the frozen scenario.

### Problem 2 — supporting projection is not consumed

The test creates:

```python
relationships_projection = {...}
```

but that variable is used only for two assertions:

```python
assert relationships_projection["authorized"] is True
assert relationships_projection["motive_unknown"] is True
```

No later Concerns operation consumes the projection.

So Step 2b is structurally disconnected from the semantic chain.

### Problem 3 — no Concerns workflow is executed

Despite the test name:

```text
test_at_dp025_executes_connected_resolver_workflow_and_trace_sequence
```

the test invokes direct helper/operation functions sequentially. It does not execute an actual Concerns workflow through `DomainWorkflowExecutor`.

### Problem 4 — trace IDs remain constructed test strings

Examples:

```text
support-need:<value>
rule:reassurance:<assessment>
action:proposal-only
```

They are derived from values, not IDs emitted by a workflow/operation execution trace.

### Minimum remediation

The acceptance must use:
1. standard resolver policy/configuration;
2. real context signals sufficient to produce Concerns + supporting domain without widening scoring margins artificially;
3. a real authorized supporting `domain_result` object/projection that is actually consumed by Concerns;
4. an actual shared Workflow Engine execution with injected deterministic operation implementations;
5. outputs from that execution carried into recurrence/action/trace;
6. trace references tied to actual operation/workflow result IDs.

If the standard resolver cannot produce the required composition from a legitimate canonical scenario, that is a real integration defect to fix — do not tune the test policy around it.

---

# IMPORTANT findings

## RI-001 — Caveat stacking remediation exists only as dead helper code

**Severity:** IMPORTANT  
**File:** `cmm/domains/concerns/rules.py:1076-1143`

`evaluate_caveat_policy()` was added and unit-tested, but it is not referenced by:
- any canonical rule class;
- any canonical operation;
- any workflow;
- presentation.

Repository scan:

```text
production uses of evaluate_caveat_policy:
only its own definition
```

Therefore the frozen requirement:

> prevent repeated caveat stacking that makes an ordinary situation sound dangerous merely because technically negative possibilities exist

is not enforced by the actual Domain Pack.

### Minimum remediation

Integrate the caveat policy into the canonical `NoCatastrophicEscalationRule` / relevant operation-result path and ensure workflow/presentation consumes the filtered/validated structure.

Add an integration test proving a remote caveat cannot reach the resulting domain output, not merely that a standalone helper can filter one.

---

## RI-002 — Proportional risk still lets subjective `low` severity create objective risk without evidence

**Severity:** IMPORTANT  
**File:** `cmm/domains/concerns/rules.py:951-991`

R6 corrected medium/high subjective severity, but low remains:

```python
elif mapped_severity == _RISK_LOW:
    base_risk = _RISK_LOW
```

Later, with no evidence:

```python
risk_level = base_risk
```

### Independent reproduction

```text
evaluate_proportional_risk(
    severity="low",
    evidence=()
)

=> risk_level = "low"
=> grounded_risk_evidence = False
```

This conflicts with the function's own frozen invariant:

```text
subjective severity never creates objective risk
```

### Minimum remediation

Subjective severity/lived impact must never create an objective risk state at any level.

With no grounded risk evidence and no authorized specialized risk:
- objective risk should remain `none` or `unresolved`;
- subjective impact should be preserved separately.

---

## RI-003 — Reassurance still does not actually evaluate all frozen evidence dimensions

**Severity:** IMPORTANT  
**File:** `cmm/domains/concerns/rules.py:701-854`

Target-relative stance and provenance dedupe are materially improved, but several frozen dimensions are only partially implemented.

### Base plausibility is echoed, not evaluated

```python
base_plausibility_value = _usable_scalar_string(base_plausibility)
```

It does not participate in the decision ladder.

Independent reproduction:

```text
same evidence + base_plausibility="high"
=> REASSURANCE_SUPPORTED

same evidence + base_plausibility="low"
=> REASSURANCE_SUPPORTED
```

### Authorized domain-specific evidence is not integrated into the assessment

The function only reads:

```text
authorized
probability
```

and merely preserves the probability.

Grounded specialized findings/red flags/outcomes do not affect reassurance assessment.

### Weak/stale evidence is silently removed from output

The comment says:

> weak/stale opposing records stay visible but cannot upgrade reassurance

but `pro_reassurance_all` already filters them through `_is_current_and_grounded`, and `pro_reassurance_strong` applies the exact same test again.

A weak reassurance record therefore becomes:

```text
assessment = INSUFFICIENT_BASIS
supporting = ()
malformed_count = 0
```

The evidence disappears instead of remaining visible as weak/stale evidence.

### Duplicate normalization remains caller-text sensitive

Dedupe key:

```python
(grounding, claim, stance)
```

does not normalize substantive claim text.

Independent reproduction:

```text
same source + "Warm reply"
same source + "warm reply"
```

counts as two independent records and can upgrade to `REASSURANCE_SUPPORTED`.

### Minimum remediation

- define a closed base-plausibility contract and make it influence confidence/assessment proportionally;
- consume authorized specialized reassurance/concern semantics explicitly;
- preserve weak/stale evidence in structured output while preventing it from upgrading;
- canonicalize claim text for dedupe (at least whitespace/case normalization) while preserving original wording.

---

## RI-004 — `REASSURANCE_PARTIAL + material concern` is incorrectly classified as false reassurance

**Severity:** IMPORTANT  
**File:** `cmm/domains/concerns/rules.py:1147-1185`

Frozen definition of `REASSURANCE_PARTIAL`:

> Some feared interpretation is weak, but another concern remains legitimate.

Yet `detect_false_reassurance()` does:

```python
if has_material_concern and assessment in (
    REASSURANCE_SUPPORTED,
    REASSURANCE_PARTIAL,
):
    false_reassurance = True
    corrected = CONCERN_SUPPORTED
```

### Independent reproduction

```text
assessment = REASSURANCE_PARTIAL
material_concerns = ("real issue",)

=> false_reassurance = True
=> corrected_assessment = CONCERN_SUPPORTED
```

That destroys the canonical purpose of partial reassurance.

`evaluate_reassurance_result()` avoids this path by selectively hiding material concerns from the false-check unless assessment is fully supported, but the standalone `NoFalseReassuranceRule` still consumes `detect_false_reassurance()` directly.

### Minimum remediation

Only flag `REASSURANCE_PARTIAL` when the material concern is actually hidden/minimized by the represented state.

A correct partial reassurance that explicitly preserves the concern must remain valid.

Add rule-class-level regression coverage, not only helper coverage.

---

## RI-005 — Presentation still drops canonical flat risk semantics and may mark non-fact conclusions `known_fact`

**Severity:** IMPORTANT  
**File:** `cmm/domains/concerns/presentation.py:182-279`

R7 fixed the actual reassurance helper shape, but not the other semantic outputs it claims to preserve.

### Flat risk output is lost

Canonical `evaluate_risk_result()` is flat:

```text
risk_level
specialized_domain_id
specialized_red_flags
...
```

Presentation only reads:

```python
risk_value = result.get("risk")
```

Therefore presenting an actual risk helper result with `risk_level="high"` produces:

```text
risk = {"risk_level": "none"}
```

### Independent reproduction

Input:

```python
{
  "risk_level": "high",
  "specialized_domain_id": "domain:health",
  "specialized_red_flags": ("x",)
}
```

Presentation output:

```text
risk_level = none
```

### Non-fact result can become `known_fact`

A flat:

```text
assessment = CONCERN_SUPPORTED
material_concern = True
no remaining uncertainty
```

produces top-level:

```text
presentation_state = known_fact
```

A concern assessment is not automatically an epistemic fact.

### Why current R7 matrix missed it

The 13-operation parity test checks only:

```text
does not raise
is JSON-safe
returns dict
```

It does not assert semantic preservation for risk or most operation shapes.

### Minimum remediation

Create operation-specific semantic adapters or one canonical aggregate result contract.

Add parity assertions for:
- risk;
- uncertainty calibration;
- separation statements;
- support need;
- action;
- recurrence;
not only reassurance.

---

# Findings confirmed FIXED from the first audit

The re-audit independently confirms the following prior defects are materially corrected:

```text
I-001 SupportNeed precedence                  FIXED
I-002 recurrence certainty grounding          FIXED
I-003 explicit wait/no-advice                 FIXED
I-004 direct Reflection private dependency    FIXED
I-008 trace supporting-domain capability      FIXED structurally
B-002 operation schema tuple-union support    FIXED
```

Independent pure-helper probes:

```text
explicit "No advice, I just need to talk"
+ lower-priority "What can I do?"
=> EMOTIONAL_PROCESSING

same question + unchanged evidence + relief/checking
without impossible-certainty marker
=> pattern_detected=False

"I want to wait" + available option
=> NO_ACTION_NEEDED
```

Structural re-audit:

```text
Concerns production modules: 14
sibling specialized-domain imports: 0
parallel Concerns-specific engine/store classes: 0
compileall: PASS
remediation patch added-line whitespace: clean
```

---

# Verification limitations

The independent runtime does not have repository dependency `libcst`, so the full repository pytest collection cannot run in this audit environment.

Attempting focused remediation tests reaches:

```text
ModuleNotFoundError: No module named 'libcst'
```

Therefore these agent-reported results are **not independently certified**:

```text
360 focused
757 sibling regressions
5586 all domains
11114 global
Ruff clean
fresh import
```

They are not marked failed; they remain implementation-side evidence.

Pure helper behavior, source-level contracts, compileall, archive integrity, package structure, and the findings above were independently verified from the uploaded tracked-HEAD snapshot.

---

# Re-audit gate table

```text
PACKAGE_BOUNDARY: PASS
CATALOG_RECONCILIATION: PASS
SUPPORT_NEED_PRECEDENCE: PASS
EXPERIENCE_FACT_SEPARATION: PASS
QUESTION_MATERIALITY: FAIL
REASSURANCE_ALLOWED: FAIL
NO_FALSE_REASSURANCE: FAIL
NO_CATASTROPHIC_ESCALATION: FAIL
REPETITION_NOT_PATHOLOGY: PASS
RECURRING_PATTERN_GROUNDING: PASS
NO_FORCED_ACTION: PASS
HEALTH_HANDOFF: NOT_PROVEN
REFLECTION_BOUNDARY: PASS
RELATIONSHIPS_BOUNDARY: PASS
PERMISSION_LITERAL_TRUE: PASS (unchanged from first audit)
MEMORY_CONFIRMATION: PASS (unchanged from first audit)
WORKFLOW_DEPENDENCY_INTEGRITY: FAIL
PRESENTATION_SEMANTIC_PRESERVATION: FAIL
TRACE_REFERENCE_ONLY: PASS
TRACE_SUPPORTING_DOMAINS: PASS
ROLLBACK: NOT_PROVEN
INPUT_ORDER_INVARIANCE: NOT_PROVEN
INPUT_NON_MUTATION: NOT_PROVEN
STRICT_JSON: NOT_PROVEN
CLEAN_IMPORT: NOT_PROVEN
AT_DP_025: FAIL
FOCUSED_TESTS: NOT_PROVEN
DOMAIN_REGRESSIONS: NOT_PROVEN
ALL_DOMAIN_TESTS: NOT_PROVEN
GLOBAL_TESTS: NOT_PROVEN
RUFF: NOT_PROVEN
COMPILEALL: PASS
DIFF_HYGIENE: PASS
```

## Final status

```text
PHASE10_25_REAUDIT_STATUS:
FINAL_REMEDIATION_REQUIRED

AUDIT_VERDICT:
FAIL — final remediation required

INDEPENDENT_AUDIT_STATUS:
NOT_READY_TO_CLOSE
```

The remaining scope is narrow enough for one final TDD remediation pass. Do not redesign the domain or reopen canonical counts/architecture.
