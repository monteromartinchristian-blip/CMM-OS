# Phase 10.24 Reflection Domain — Audit V1 Remediation Plan

**Base:** `1a1048c`
**Target commit:** `fix(domains): remediate phase 10.24 audit v1 findings`

## Scope

Remediate:

```text
V1-I1 duplicate/conflict normalization
V1-I2 temporal ordering/equal-time ambiguity
V1-I3 source-grounded interest mapping
V1-I4 confirmed persistence binding
V1-I5 fail-closed presentation states
V1-I6 diagnosis/restricted-inference enforcement
V1-I7 no-forced-conclusion / certainty hardening
V1-I8 executable workflow validation gates
V1-I9 public helper normalization / strict JSON / no-exception
V1-M1 unreachable duplicate code
```

The only allowed shared production change is the minimal workflow-runtime change
required to make existing `VALIDATE` nodes executable and fail-closed.

No other shared-infrastructure refactor is permitted.

## Required TDD order

1. Public normalization / strict JSON foundation
2. Duplicate/conflict normalization
3. Temporal normalization
4. Interest source grounding
5. Shared confirmation binding for persistence
6. Presentation strict state handling
7. Diagnosis / restricted-inference enforcement
8. No-forced-conclusion / summary certainty
9. Shared workflow `VALIDATE` enforcement
10. Dead-code cleanup
11. V1 closure suite
12. Full verification
13. Single remediation commit

## Shared workflow constraint

Before changing shared runtime, verify the exact current execution path for
`VALIDATE` nodes.

The implementation must:

- use the existing shared workflow contracts;
- make `VALIDATE` executable rather than metadata-only;
- fail closed when a validation condition is absent, malformed, unknown, or
  evaluates false;
- preserve existing non-Reflection workflows;
- avoid a Reflection-specific workflow engine;
- add shared regression tests plus Reflection negative tests;
- avoid unrelated changes to scheduling, operation execution, or workflow
  persistence.

If the current shared contract cannot express executable validation without
breaking established semantics, stop and report the exact blocker instead of
inventing a parallel mechanism.

## V1 closure requirements

Permanent regression tests must prove:

```text
same hypothesis ID + incompatible statements => conflict/unresolved
same ambivalence ID + incompatible statements => conflict/ambivalence
supporting evidence + counterevidence => conflict/unresolved

equal normalized timestamp subgroup => no intra-group direction
timeline uses normalized timestamp order

unknown/case-variant/model/memory source kinds do not become independent grounded evidence
interest top-level evidence state reflects actual grounding

raw confirmation=True without valid shared confirmation/provenance => not confirmed
shared valid confirmation => eligible/confirmed according to shared contract
nonliteral confirmation => denied

"false", 1, arbitrary truthy objects cannot become adopted/confirmed in presentation
malformed presentation state => unknown/fail-closed

diagnostic or identity-classifying hypothesis wording cannot pass as safe non-diagnostic output
safe hypothesis form remains possible

unsupported certainty variants cannot convert unresolved reflection into resolved conclusion
summary cannot expose certainty amplification

VALIDATE nodes actually block false/malformed conditions under shared runtime
existing Domain Pack workflow behavior remains green

NaN/inf/non-iterable malformed inputs do not escape public Reflection helpers
all supported public outputs pass json.dumps(..., allow_nan=False)

unreachable duplicate implementation removed
```

## Verification ladder

Run, in order:

```text
targeted V1 closure tests
Reflection suite
shared workflow/runtime regression tests
Domains suite
Global suite
Ruff
Ruff py310
compileall
fresh import
diff check
clean-state verification after commit
```

Final status:

```text
Phase 10.24 — Implemented, pending independent audit V2
```

No push.
No merge.
