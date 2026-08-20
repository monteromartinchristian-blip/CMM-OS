# Phase 10.24 — Reflection Domain — Independent Audit V3

Date: 2026-08-20

## Candidate

```text
branch: feature/phase-10-domain-intelligence

candidate:
1d1543998e743ebf249641c4f2bb26944f168825
1d15439 fix(domains): remediate phase 10.24 audit v2 findings

audit V2:
0d251d33c35a2c9f288f506fd1c4a47133196dd3
0d251d3 docs(domains): record phase 10.24 independent audit v2

V2 remediation base:
6e146902f7f59f2df8f55dcbcbb30933d37ceec2
6e14690 fix(domains): remediate phase 10.24 audit v1 findings
```

Evidence bundle:

```text
cmm-phase-10.24-audit-v3-evidence-20260820-205414.tar.gz
SHA-256:
19895abc7bcd30e049a525377efadb32992d9fff02488a6db4762474086e91ee
```

Bundle manifest:

```text
declared entries: 85
substantive entries verified: 84
hash mismatches: 0
collector-only missing entry: .DS_Store
```

The missing `.DS_Store` is an evidence-packaging artifact, not repository
product evidence. The tracked repository snapshot and every substantive
evidence file used by this audit verified against the manifest.

---

# Verdict

## REMEDIATION REQUIRED

```text
Critical: 0
Important: 4
Minor: 1
```

Phase status:

```text
Phase 10.24 — Implemented, remediation required
DP-024 — NOT YET VERIFIED
AT-DP-024 — NOT YET PASS
```

The V2 remediation closes the exact runtime probes that motivated Audit V2 and
the repository now has a fully green test baseline. However, independent source
inspection exposes four material residual contract gaps, and the required Ruff
gate is not clean.

Do not mark Phase 10.24 Complete or independently audited.

---

# 1. Fresh verification

The evidence bundle records the following on committed HEAD `1d15439`.

## V1 + V2 closure

```text
73 passed
exit=0
```

## Reflection

```text
299 passed
exit=0
```

## Domains + Workflows

```text
5159 passed
exit=0
```

## Domains

```text
5119 passed
exit=0
```

## Global

```text
10643 passed
exit=0
```

## Previously reported nine global failures

Together:

```text
9 passed
exit=0
```

Individually:

```text
isolated-1 = 1 passed
isolated-2 = 1 passed
isolated-3 = 1 passed
isolated-4 = 1 passed
isolated-5 = 1 passed
isolated-6 = 1 passed
isolated-7 = 1 passed
isolated-8 = 1 passed
isolated-9 = 1 passed
```

Therefore the earlier nine-failure observation is not present on the committed
V2 remediation candidate. No global regression is currently demonstrated.

## Static / import

```text
compileall = PASS
fresh import = PASS
diff check = PASS
repository parity = PASS

Ruff = FAIL
Ruff py310 = FAIL
```

Both Ruff failures are the same `I001` import-order defect described in V3-M1.

---

# 2. Collector V3 independent probe

Collector probe result:

```text
VALIDATE_NUMERIC_TRUE_GATE=PASS
VALIDATE_CONFLICT_GATE=PASS
VALIDATE_COMPATIBLE_GATE=PASS
PERSISTENCE_FAKE_MAPPING_GATE=PASS
INTEREST_ONE_SOURCE_GATE=PASS
DIAGNOSIS_ES_GATE=PASS
FORCED_CONCLUSION_ES_GATE=PASS
ALL_V3_GATES_PASS=true
```

This proves:

```text
1 != True at VALIDATE boundary
declared-field conflicting outputs fail
compatible outputs pass
raw fake mapping no longer confirms persistence
one-source interest repetition remains uncertain
the specific tested Spanish diagnosis phrase is restricted
the specific tested Spanish certainty phrase is blocked
```

It does **not** by itself establish full V2 closure because:

1. the persistence probe uses a fake `Mapping`, not a caller-created shared
   snapshot object;
2. the diagnosis and forced-conclusion values overlap the permanent V2
   regression vocabulary;
3. the VALIDATE probe does not test an unrelated completed node that exposes a
   condition field.

The findings below come from inspection of the exact committed snapshot and the
shared contracts it reuses.

---

# 3. Findings

## V3-I1 — Shared VALIDATE reads all accumulated node outputs, not only declared dependencies

**Severity:** Important

**Location:**

```text
cmm/workflows/engine.py
WorkflowEngine._evaluate_validate_node()
```

The V2 requirement was to detect conflicts across the relevant dependency
outputs of the `VALIDATE` node.

Current implementation:

```python
observed = {}

for node_id, node_output in outputs.items():
    if isinstance(node_output, Mapping):
        ...
        for field, value in node_output.items():
            if field in condition:
                observed[field].append(value)
```

The loop is over every accumulated workflow output. It never restricts
`node_id` to:

```text
node.dependencies
```

Consequences:

### A. Unrelated output can satisfy a missing dependency condition

Example workflow state:

```text
unrelated node:
  {"safe": True}

declared dependency:
  {"other": "value"}

VALIDATE depends only on declared dependency
wait_condition:
  {"safe": True}
```

Current state collection sees `safe=True` from the unrelated node and can pass
the gate even though the declared dependency supplied no `safe` state.

That is a fail-open dependency violation.

### B. Unrelated output can manufacture a conflict

Example:

```text
unrelated node:
  {"safe": False}

declared dependency:
  {"safe": True}

wait_condition:
  {"safe": True}
```

The current implementation sees both values and returns:

```text
validate.condition_conflict
```

even though the unrelated node is not part of the gate's dependency contract.

That is a false failure.

The function's own documentation says:

```text
"across multiple dependency outputs"
```

but the implementation uses all completed outputs.

**Impact:** the shared workflow runtime can authorize or reject a validation gate
based on nodes that are outside that gate's declared dependency graph. Because
this is shared infrastructure, the defect is broader than Reflection.

**Required remediation:**

- collect condition-field observations only from `node.dependencies`;
- dependency missing its required field must not be rescued by an unrelated
  output;
- conflicting declared dependencies fail closed;
- unrelated nodes must not affect the gate;
- preserve strict literal boolean matching;
- add positive and negative shared regression tests.

---

## V3-I2 — A caller-created reference-only approval snapshot is still treated as authoritative confirmation

**Severity:** Important

**Locations:**

```text
cmm/domains/reflection/rules.py
_resolve_shared_confirmation()
classify_persistence()

cmm/domains/memory_contracts.py
DomainMemoryApprovalDecisionSnapshot

cmm/domains/memory_validation.py
DefaultDomainMemoryIntegrationValidator.validate_binding()
```

The frozen Reflection specification requires:

```text
explicit user confirmation through the existing memory/decision contract

or

an existing shared persistence rule with traceable evidence and authorization
```

and AT-DP-024 requires:

```text
only valid confirmation can authorize persistence
```

The V2 remediation now rejects arbitrary `dict` objects. That part is fixed.

However it treats:

```python
isinstance(
    confirmation,
    DomainMemoryApprovalDecisionSnapshot,
)
```

as sufficient proof that the approval is authoritative.

The shared contract itself describes this type as:

```text
"Frozen reference-only snapshot of an approval decision."
```

Its constructor validates only:

```text
decision_id format
request_id format
approved is bool
```

Any caller can therefore construct:

```python
DomainMemoryApprovalDecisionSnapshot(
    decision_id="fake-decision",
    request_id="fake-request",
    approved=True,
)
```

The Reflection V2 closure suite does exactly this in its helper named
`_authoritative_approval()` and then expects persistence to become confirmed.

Type identity proves schema validity. It does **not** prove:

```text
the request exists
the request belongs to the relevant proposal
the decision exists in the authoritative inventory
the decision belongs to that request
the approval covers the Reflection persistence proposal
the proposal/view/trace/binding chain validates
```

The repository already has the shared mechanism that performs those checks:

```text
DomainMemoryReferenceInventory
DefaultDomainMemoryIntegrationValidator.validate_binding()
```

That validator explicitly verifies the one-to-one chain:

```text
proposal
→ approval request
→ approval decision
```

and rejects unknown/unlinked approval coverage.

Therefore the current Reflection helper bypasses the meaningful part of the
existing memory/decision confirmation contract.

**Impact:** a caller that can construct a valid snapshot object can promote a
candidate pattern to:

```text
persistence_state = confirmed
confirmed = true
```

without a validated user-confirmation chain.

This directly blocks DP-024 confirmed persistence.

**Required remediation:**

- do not call a bare `DomainMemoryApprovalDecisionSnapshot` authoritative;
- consume a shared validation result / validated binding / authoritative
  inventory-backed confirmation path already provided by Phase 10.18;
- bind confirmation to the relevant proposal/request/decision chain;
- raw mappings and standalone snapshots must be insufficient;
- do not create a Reflection-local approval registry or persistence engine.

---

## V3-I3 — Diagnosis/restricted-inference safety still depends on an incomplete closed vocabulary

**Severity:** Important

**Location:**

```text
cmm/domains/reflection/rules.py
_diagnostic_signal()
```

V2 adds Spanish stems and prefixes and correctly closes the exact tested cases.

Current enforcement is still:

```python
for stem in _DIAGNOSTIC_TOKEN_STEMS:
    if stem in lowered:
        return True

for prefix in _IDENTITY_CLASSIFICATION_PREFIXES:
    if prefix in lowered:
        return True

return False
```

The frozen contract is semantic:

```text
psychological hypothesis != diagnosis
stable personality labels are restricted
mental-health diagnoses are restricted
fixed attachment labels are restricted
```

It is not limited to the current word list.

A direct Spanish diagnosis such as:

```text
"Padeces depresión mayor"
```

does not match the committed Spanish diagnostic stems:

```text
trastorno
narcisista
narcisismo
psicopata
sociopata
esquizofrenia
psicotico
manipulador
...
```

and does not match the current identity prefixes.

The deterministic source path therefore returns no diagnostic signal for a
plain diagnosis outside the vocabulary.

Equivalent uncovered direct classifications exist without requiring exotic
wording, for example:

```text
"Eres depresivo"
"Padeces depresión mayor"
```

The V2 fix is therefore a useful backstop but not yet a sufficient boundary for:

```text
no diagnosis
restricted identity inference
```

**Impact:** a direct psychological diagnosis/classification can still be
represented as an ordinary prudent hypothesis with `diagnostic=false`.

**Required remediation:**

- prefer a structural safety signal where the generating operation/rule already
  knows that a candidate is a psychological/identity classification;
- keep lexical detection only as a secondary backstop;
- extend Spanish normalization for obvious direct diagnostic forms needed by
  the project's supported language;
- add independent variants not copied from the V2 test list;
- preserve safe tentative psychological hypotheses.

Do not build a general medical NLP classifier.

---

## V3-I4 — NoForcedConclusion remains a whole-result phrase scanner rather than a structural conclusion gate

**Severity:** Important

**Location:**

```text
cmm/domains/reflection/rules.py
_collect_text()
no_forced_conclusion_policy()
```

The V1/V2 remediation requirement explicitly called for structural-first
certainty enforcement rather than solving the issue through an expanding
phrase blacklist.

Current implementation recursively collects every string anywhere in the input:

```python
texts = _collect_text(result)
```

and sets a forced conclusion only when one of the committed certainty phrases
is found.

This produces two residual failure classes.

### A. False negative: unsupported certainty outside the vocabulary

Example:

```text
unresolved = true
conclusion = "Tengo la certeza absoluta de que todo fue por rechazo"
```

The current committed Spanish certainty vocabulary includes forms such as:

```text
es evidente que
está claro que
es indudable que
sin lugar a dudas
esto demuestra que
la causa real es
la única explicación es
```

but not the general state:

```text
certeza absoluta
```

The policy therefore has no structural field that identifies the conclusion as
unsupported certainty once the phrase list misses it.

### B. False positive: certainty wording inside evidence is treated as a forced conclusion

Because `_collect_text()` scans all nested text, a source observation such as:

```text
observation:
  "La otra persona dijo: 'obviamente no iba a venir'"
```

can trip the `"obviamente"` marker even when:

```text
there is no final conclusion
the reflection remains explicitly unresolved
```

The rule is supposed to prevent unsupported conclusions. It should not classify
quoted/source certainty as a system conclusion merely because the word occurs
somewhere in the structured result.

**Impact:** open-ended Reflection can both miss unsupported conclusions and reject
valid unresolved reflections based on source text.

**Required remediation:**

- evaluate conclusion/adoption/certainty fields structurally first;
- scope lexical backstops to actual conclusion/assertion surfaces, not every
  nested evidence string;
- distinguish quoted/source certainty from system certainty;
- add both false-negative and false-positive regression tests;
- keep valid tentative conclusions/hypotheses possible.

---

## V3-M1 — Required Ruff gates fail on import ordering introduced in V2 remediation

**Severity:** Minor

**Location:**

```text
tests/domains/test_reflection_domain_audit_v1_closure.py
```

Fresh collector output for both:

```text
Ruff
Ruff py310
```

is:

```text
I001 Import block is un-sorted or un-formatted
```

The V2 remediation added:

```python
from cmm.domains.memory_contracts import DomainMemoryApprovalDecisionSnapshot
```

after the `cmm.domains.reflection.*` imports, while Ruff expects the canonical
import order.

Observed:

```text
ruff exit = 1
ruff-py310 exit = 1
```

**Required remediation:** reorder the imports and rerun both lint gates.

This is non-semantic but blocks the required verification ladder.

---

# 4. V2 finding reconciliation

## V2-I1 — shared VALIDATE

**Partially closed / residual V3-I1**

Closed:

```text
1 does not satisfy True
0 does not satisfy False
declared conflicting observed values fail
```

Residual:

```text
gate observation scope is all accumulated outputs, not declared dependencies
```

## V2-I2 — persistence confirmation

**Not fully closed / residual V3-I2**

Closed:

```text
raw fake Mapping no longer authorizes
```

Residual:

```text
caller-created reference-only shared snapshot is still treated as authoritative
without inventory/binding validation
```

## V2-I3 — same-source interest uncertainty

**CLOSED**

Independent V3 evidence:

```text
INTEREST_ONE_SOURCE_GATE=PASS
```

and source inspection shows uncertainty is now driven by independent grounded
source count rather than raw mention count.

## V2-I4 — Spanish diagnosis boundary

**Partially closed / residual V3-I3**

Closed:

```text
committed Spanish direct-classification examples
```

Residual:

```text
semantic safety remains dependent on incomplete lexical vocabulary
```

## V2-I5 — Spanish forced conclusion

**Partially closed / residual V3-I4**

Closed:

```text
committed Spanish certainty examples
```

Residual:

```text
whole-result lexical scanning remains both bypassable and overbroad
```

---

# 5. DP-024 V3 assessment

## Open-ended analysis

**Remediation required**

V3-I4 can reject valid unresolved evidence or miss an unsupported conclusion.

## Prudent hypotheses

**Remediation required**

V3-I3 leaves direct diagnoses outside the closed vocabulary untreated.

## Source-grounded interest mapping

**PASS for the V2 residual under audit**

One-source repetition remains uncertain and independent-source counting is
preserved.

## Confirmed persistence

**Remediation required**

V3-I2 does not yet establish a validated shared confirmation chain.

Therefore:

```text
DP-024 = NOT YET VERIFIED
AT-DP-024 = NOT YET PASS
```

---

# 6. Shared workflow assessment

The shared `VALIDATE` direction remains correct and should not be reverted.

V3 confirms:

```text
literal boolean comparison = PASS
declared conflict detection = PASS
compatible values = PASS
```

Required final hardening is only:

```text
scope runtime observation to declared dependencies
```

No new workflow engine is needed.

---

# 7. Non-findings / investigated concerns

## Global-suite regression

Dismissed.

Current committed candidate:

```text
10643 passed
```

The previously reported nine tests also pass together and individually.

No current global regression is demonstrated.

## V3 collector smoke probe

The collector V3 probe itself exits 0 and all declared gates pass.

Its diagnosis/forced-conclusion values do not provide independent coverage
beyond the permanent vocabulary, which is why source inspection was continued.

## V2 interest uncertainty

Closed.

No new evidence inflation from same-source mention count was found.

## V1 JSON/no-exception hardening

No V3 regression demonstrated.

## `.DS_Store` manifest entry

Collector packaging issue only.

It is not part of the tracked repository candidate and is not promoted to a
Phase 10.24 finding.

---

# 8. Required V3 remediation order

```text
1. V3-I1 — dependency-scoped VALIDATE
2. V3-I2 — inventory/binding-validated confirmation chain
3. V3-I3 — structural diagnosis/restricted-inference hardening
4. V3-I4 — structural/scoped NoForcedConclusion
5. V3-M1 — Ruff import order
```

Use TDD RED → GREEN for every behavioral finding.

Do not broaden shared infrastructure.

---

# 9. Required Independent Audit V4 focus

After V3 remediation, independently attack:

```text
VALIDATE:
- unrelated node cannot satisfy condition
- unrelated node cannot manufacture conflict
- conflicting declared dependencies still fail
- literal bool semantics preserved

Persistence:
- arbitrary Mapping denied
- standalone caller-created snapshot denied
- wrong request/decision/proposal chain denied
- validated binding/inventory approval accepted
- approval remains tied to exact proposal

Diagnosis:
- new Spanish diagnosis variants
- English variants
- safe tentative psychological explanation
- user-provided identity narrative remains structurable without being promoted

NoForcedConclusion:
- unsupported certainty outside committed phrase list
- certainty quoted in source/evidence does not become system conclusion
- tentative conclusion remains allowed
- unresolved no-conclusion remains valid

Static:
- Ruff
- Ruff py310
```

Then rerun the complete clean-state verification ladder.

---

# 10. Final V3 status

```text
Phase 10.24 — Implemented, remediation required

Critical: 0
Important: 4
Minor: 1

Independent Audit V3: REMEDIATION REQUIRED
DP-024: NOT YET VERIFIED
AT-DP-024: NOT YET PASS
```

No remediation was performed during this audit.
No push.
No merge.
