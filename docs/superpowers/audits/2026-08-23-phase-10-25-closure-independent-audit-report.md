# Phase 10.25 — Closure Independent Audit Report

**Date:** 2026-08-23  
**Audit mode:** independent read-only audit of the closure snapshot  
**Bundle:** `CMM-OS-phase-10.25-closure-audit.tar.gz`  
**Bundle SHA-256:** `b60c764b8a6a228a5dcb981cdbc17527f9931113042e3bbbdb4db71b226dad1b`  
**Audited HEAD:** `a3e505c3ec2005bd9077e4d6a4d389f4b726ac23` (`a3e505c`)

## Verdict

```text
AUDIT_VERDICT: FAIL — one evidence-calibration remediation remains
INDEPENDENT_AUDIT_STATUS: NOT_READY_TO_CLOSE
```

The closure remediation materially fixed the four findings from the preceding audit. Three are independently accepted as closed, and the fourth is closed for its original reassurance-side failure mode. One new asymmetric evidence-calibration defect remains.

---

# Closure findings disposition

```text
FB-001 Operation input contract parity: PASS
FB-002 Reassurance target/quality/temporal fail-closed: PASS for reassurance direction
FB-003 Connected AT-DP-025 acceptance: PASS
FI-001 Presentation semantic preservation: PASS
FM-001 Documentation status: PASS
```

## Independent evidence

### Operation input contracts

The tracked snapshot exposes canonical semantic input fields for all relevant operations.

The independent audit executed `test_concerns_domain_audit_r9.py`:

```text
18 passed
```

It also validated actual registered `OperationDescriptor` requests through `InMemoryAgentOperationRegistry.validate_request()` for:

```text
concerns.evaluate_reassurance
concerns.evaluate_risk
concerns.infer_support_need
concerns.prepare_next_step
concerns.prepare_professional_discussion
```

All accepted the canonical request shape with operation version `1.0.0`.

### Reassurance fail-closed

Independent direct probes:

```text
missing target claim                  -> REASSURANCE_PARTIAL
missing source_quality               -> REASSURANCE_PARTIAL
unknown source_quality               -> REASSURANCE_PARTIAL
missing temporal_relevance           -> REASSURANCE_PARTIAL
unknown temporal_relevance           -> REASSURANCE_PARTIAL
explicit grounded + current evidence -> REASSURANCE_SUPPORTED
```

So arbitrary/missing metadata no longer produces full reassurance.

### Objective risk

Independent probes:

```text
severity=low    + evidence=() -> risk_level=none
severity=medium + evidence=() -> risk_level=none
severity=high   + evidence=() -> risk_level=none
```

Subjective severity no longer manufactures objective risk.

### Presentation

Independent probe with:

```text
ordinary scenario
+ remote caveat
```

preserves the ordinary scenario and removes the remote caveat.

Actual operation-specific presentation regressions also pass the R9 closure suite.

### AT-DP-025

The final acceptance now:
- uses the standard resolver/default policy;
- resolves Concerns primary + Relationships supporting;
- executes a real `DomainWorkflowExecutor`;
- consumes the supporting projection in the executed workflow path;
- produces a substantive semantic response;
- carries Step 8/9 state into separation and reassurance;
- asserts exact `REASSURANCE_PARTIAL`;
- preserves a real concern;
- compares recurrence against prior evidence state;
- keeps the next step proposal-only;
- performs no external action or silent persistence;
- validates a typed shared trace.

Independent execution:

```text
tests/domains/test_concerns_domain_audit_r3.py
2 passed
```

This satisfies the frozen §115 25-step acceptance at the deterministic Domain Pack level.

---

# CB-001 — Unknown evidence metadata can still manufacture `CONCERN_SUPPORTED`

**Severity:** IMPORTANT / closure-blocking core semantic defect

**File:**
`cmm/domains/concerns/rules.py:824-849, 937-950`

## Defect

The final remediation correctly uses a closed allowlist for evidence that can produce full reassurance:

```python
def _is_current_and_grounded(record):
    return (
        source_quality in _STRONG_SOURCE_QUALITIES
        and temporal_relevance in _CURRENT_TEMPORAL_RELEVANCE
        ...
    )
```

But concern-supporting evidence uses a different fail-open predicate:

```python
pro_concern_valid = [
    item
    for item in pro_concern_all
    if item["source_quality"] not in _WEAK_SOURCE_QUALITIES
    and item["temporal_relevance"] not in _STALE_TEMPORAL_RELEVANCE
]
```

Unknown or missing metadata is therefore treated as valid concern evidence simply because it is not on the denylist.

Two such records trigger:

```python
len(pro_concern_valid) >= 2
→ CONCERN_SUPPORTED
```

## Independent reproductions

### Missing quality/relevance

```text
target_claim = "decline"

2 records:
stance = supports_target
grounding = s1 / s2
source_quality = missing
temporal_relevance = missing

=> CONCERN_SUPPORTED
=> malformed_count = 0
```

### Arbitrary invalid metadata

```text
2 records:
source_quality = "banana"
temporal_relevance = "nonsense"

=> CONCERN_SUPPORTED
=> malformed_count = 0
```

### Control

```text
2 records:
source_quality = "speculation"
temporal_relevance = "current"

=> INSUFFICIENT_BASIS
```

So an arbitrary unrecognized value bypasses the weak-evidence guard, while a correctly labelled weak value does not. This is a classic denylist fail-open.

## Why this violates the frozen design

`EvidenceCalibratedReassuranceRule` must evaluate:

```text
source quality
temporal relevance
counterevidence
material negative signals
```

and the global design explicitly rejects catastrophic escalation / unsupported concern inflation.

The final C2 remediation introduced closed quality/relevance vocabularies specifically so unknown metadata cannot strengthen an epistemic conclusion. That rule needs to apply to the `CONCERN_SUPPORTED` direction as well as to `REASSURANCE_SUPPORTED`.

CMM OS must not be asymmetric in a way that prevents weak evidence from calming the user while allowing equally unknown evidence to create an objective-looking concern conclusion.

## Minimum remediation

Do not remove or hide the records.

Keep all target-supporting records visible in `counterevidence`, but require recognized strong/current evidence before they may upgrade the assessment to `CONCERN_SUPPORTED`.

For example, use an explicitly closed subset:

```python
pro_concern_strong = [
    item for item in pro_concern_all
    if _is_current_and_grounded(item)
]
```

and use this subset for the concern-strength decision ladder.

Unknown/weak/stale records may contribute to uncertainty, but may not independently produce `CONCERN_SUPPORTED`.

Do not require this change to erase a separately supplied `material_concern` or an authorized specialized-domain concern; those are distinct grounded bases.

## Required regression tests

```text
test_missing_quality_target_support_cannot_produce_concern_supported
test_unknown_quality_target_support_cannot_produce_concern_supported
test_missing_temporal_target_support_cannot_produce_concern_supported
test_unknown_temporal_target_support_cannot_produce_concern_supported
test_weak_target_support_remains_visible_but_does_not_upgrade_concern
test_two_strong_current_target_support_records_can_produce_concern_supported
test_material_concern_still_produces_concern_supported_without_erasure
test_authorized_specialized_concern_still_preserved
```

Also verify input-order invariance and duplicate provenance behavior for the new concern-strength subset.

---

# Independent verification summary

The audit runtime lacks `libcst`, so the repository's full native pytest collection cannot be independently reproduced exactly.

A package-isolation harness was used only to avoid unrelated package import side effects.

Independently executed green:

```text
test_concerns_domain_audit_r9.py         18 passed
test_concerns_domain_audit_r3.py          2 passed
R8 tests not requiring shared rule builder 26 passed
test_concerns_domain_operations.py       18 passed
test_concerns_domain_reassurance.py      38 passed
test_concerns_domain_presentation.py     14 passed
test_concerns_domain_workflows.py        16 passed
test_concerns_domain_dp025_acceptance.py 24 passed
test_concerns_domain_epistemics.py       12 passed
test_concerns_domain_recurrence.py       23 passed
```

The remaining isolated-suite failures are caused by the audit runtime's Python/shared dataclass package-loading behavior around `DomainReasoningRuleDefinition`, and are not used as Phase 10.25 findings.

Implementation-agent results remain:

```text
Concerns: 407 passed
Domains: 5633 passed
Global: 11161 passed
Ruff: clean
compileall: clean
fresh import: PASS
diff check: clean
```

Those are implementation-side evidence, not substituted for the independent semantic probes above.

---

# Gate status

```text
PACKAGE_BOUNDARY: PASS
CANON_17_10_14_13_8: PASS
OPERATION_INPUT_CONTRACT_PARITY: PASS
REASSURANCE_TARGET_FAIL_CLOSED: PASS
REASSURANCE_QUALITY_FAIL_CLOSED: PASS
REASSURANCE_TEMPORAL_FAIL_CLOSED: PASS
OBJECTIVE_RISK_GROUNDING: PASS
PRESENTATION_SEMANTIC_PRESERVATION: PASS
CAVEAT_NON_DELETION: PASS
AT_DP_025: PASS
TRACE_SUPPORTING_DOMAINS: PASS
RECURRING_PATTERN_GROUNDING: PASS
NO_FORCED_ACTION: PASS

CONCERN_EVIDENCE_QUALITY_FAIL_CLOSED: FAIL
CONCERN_EVIDENCE_TEMPORAL_FAIL_CLOSED: FAIL

COMPILEALL: PASS
DIFF_HYGIENE: PASS
```

## Final status

```text
PHASE10_25_CLOSURE_AUDIT_STATUS:
ONE_MICRO_REMEDIATION_REQUIRED

AUDIT_VERDICT:
FAIL — one evidence-calibration remediation remains

INDEPENDENT_AUDIT_STATUS:
NOT_READY_TO_CLOSE
```

No architectural redesign, new operation, new rule, new workflow, or canonical-count change is required.
