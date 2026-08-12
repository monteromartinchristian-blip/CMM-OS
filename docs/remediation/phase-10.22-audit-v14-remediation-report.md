# PHASE 10.22 UNIVERSITY DOMAIN — AUDIT V14 → V15 CLOSURE REMEDIATION

**Phase:** 10.22 University Domain
**Audit:** Independent Audit V14 → Independent Audit V15
**Date:** 2026-08-12
**Status:** V14 blockers remediated — **READY FOR INDEPENDENT AUDIT V15**
**Production scope:** `cmm/domains/university/rules.py`
**Test scope:**
- `tests/domains/test_university_domain_source_authority.py`
- `tests/domains/test_university_domain_contradiction.py`
- `tests/domains/test_university_domain_deadlines.py`
- `tests/domains/test_university_domain_rules.py`

**Roadmap:** unchanged — `Implemented, pending audit`. Independent Audit V15 decides closure.

This report records the surgical remediation of the two blocker clusters raised by Independent Audit V14.

The implementation was verified with a real RED → GREEN cycle by running the new V14 adversarial tests against the pre-remediation production code in an isolated temporary checkout and then against the remediated working tree.

---

## 1. V14 blocker summary

Independent Audit V14 raised two clusters:

### V14-B1 — Singular scalar identities/references accepted implicit collection coercion

Collection-shaped values such as:

```text
source_id=["junk"]
claim id=["junk"]
deadline source_reference=["d1"]
deadline value=["2026-09-01"]
performance ref=["r1"]
performance outcome=["below_average"]
```

could be implicitly reduced to a scalar string by generic reference normalization.

The same cluster also included a related identity-preservation defect: malformed or missing source/claim identities could disappear from authority competition, allowing a referenced sibling to win a conflict with unjustified confidence.

### V14-B2 — Base Source Authority collapsed relation-unknown evidence into safely irrelevant evidence

Evidence such as:

```text
{"source_id":"junk","value":9.0}
{"source_id":"junk","supplied_attributes":None}
{"source_id":"junk","attribute":None,"value":9.0}
```

could be ignored while a valid sibling source resolved confidently.

The resolver therefore still conflated:

```text
VALID_RELEVANT
VALID_IRRELEVANT
RELATION_UNKNOWN / MALFORMED
```

at the base helper boundary.

---

# 2. Core invariants restored

The remediation enforces:

```text
singular scalar != plural collection
```

```text
["x"] != "x"
("x",) != "x"
```

```text
missing identity != usable identity
```

```text
malformed identity != evidence allowed to disappear
```

```text
valid relevant evidence
!=
valid irrelevant evidence
!=
relation-unknown evidence
```

```text
field absent != field present with None
```

```text
no implicit coercion
```

---

# 3. V14-B1 — Strict singular scalar/reference semantics

## Root cause

A generic reference helper was permissive enough to unwrap collection-shaped inputs and return the first usable scalar string.

That behavior can be valid for genuinely plural reference containers, but it was also used at fields whose contract is singular.

The affected semantic boundary included:

```text
source_id
claim id
deadline value
deadline source_reference
performance observation ref
performance observation outcome
```

This allowed malformed collection-shaped runtime values to become usable scalar evidence.

A second consequence was that unusable source/claim identity could exclude a competing evidence member from authority resolution instead of preserving that member as uncertainty.

## Production remediation

`cmm/domains/university/rules.py` now separates strict singular scalar/reference validation from permissive plural-reference normalization.

Singular fields accept a usable scalar string only.

Conceptually:

```text
non-empty string
→ usable singular scalar

list / tuple / mapping / number / bool
→ malformed
→ never unwrapped into a scalar identity/reference/value
```

The hardened identity semantics are applied across the affected Source Authority, Contradiction, Deadline and Performance paths.

Evidence that otherwise participates in a target fact but carries a missing or malformed source/claim identity is preserved as epistemic uncertainty rather than silently disappearing from the candidate set.

---

## RED evidence — V14-B1

The new V14 tests were overlaid onto an isolated checkout of the production code at the pre-remediation HEAD and executed without the production fix.

The combined V14-B1/B2 adversarial run produced:

```text
49 failed
16 passed
198 deselected
exit code = 1
```

The failures included the exact V14-B1 reproductions:

```text
source_id list/tuple → authority_resolved=True
adapter source_id list/tuple → authority_resolved=True
canonical source_id list/tuple → authority_resolved=True

claim id list/tuple/int/bool → resolved=True
adapter claim id malformed → resolved=True
canonical malformed claim id → CONTRADICTION_STATE

conflicting source with absent/blank/None/list/int id
→ valid sibling resolved confidently

conflicting claim with absent/blank/None/list/int id
→ contradiction resolved=True

deadline source_reference list/tuple
→ confirmed_official

deadline value list/tuple
→ confirmed_official

performance ref/outcome list/tuple
→ performance_observed=True
```

These are genuine assertion failures against the old production behavior, not import or collection errors.

---

## GREEN coverage — V14-B1

The remediation adds direct, adapter and canonical regression coverage for:

### Source Authority

```text
source_id=["junk"]
source_id=("junk",)
source_id=7
source_id=True
```

Expected:

```text
authority_resolved=False
fact_resolved=False
authority_unknown=True
```

where the malformed member participates in the target fact.

Positive scalar source IDs remain supported.

### Conflicting Source Authority

A conflicting same-level source with:

```text
source_id absent
source_id=""
source_id="   "
source_id=None
source_id=[]
source_id=7
```

must not disappear while a referenced sibling resolves.

Expected:

```text
no confident fact resolution
authority_unknown=True
```

Canonical equivalents are covered.

### Contradiction

Malformed claim identities:

```text
id=["junk"]
id=("junk",)
id=7
id=True
```

must remain:

```text
resolved=False
unresolved=True
```

Direct, exported-adapter and canonical paths are covered.

A conflicting claim with unusable identity cannot automatically lose to a referenced sibling.

### Deadline

Collection-shaped singular fields no longer confirm an official deadline:

```text
source_reference=["d1"]
source_reference=("d1",)

value=["2026-09-01"]
value=("2026-09-01",)
```

Proper scalar values/references remain supported.

### Performance

Malformed collection-shaped observation fields no longer become observed performance:

```text
ref=["r1"]
outcome=["below_average"]

ref=("r1",)
outcome=("below_average",)
```

Expected:

```text
performance_observed=False
performance_evidence_unknown=True
capacity_inferred=False
```

Proper scalar `ref` and `outcome` remain valid.

---

# 4. V14-B2 — Complete relation-unknown Source Authority classification

## Root cause

The base Source Authority path still treated some evidence members as safely unrelated when their relationship to the requested attribute was actually unknown.

The previous binary distinction:

```text
speaks about target?
True / False
```

was insufficient because `False` could mean either:

```text
valid known unrelated evidence
```

or:

```text
malformed / relation-unknown evidence
```

Key-presence semantics also remained incomplete for explicit null carriers:

```text
"supplied_attributes" not present
```

was not sufficiently distinguished from:

```text
"supplied_attributes": None
```

and likewise for:

```text
"attribute": None
```

## Production remediation

The Source Authority boundary now preserves the three semantic classes:

```text
VALID_RELEVANT
VALID_IRRELEVANT
RELATION_UNKNOWN / MALFORMED
```

Relationship-unknown evidence is no longer filtered away as irrelevant.

Key-presence-aware validation distinguishes absent fields from explicit malformed/null carriers.

Known unrelated evidence remains non-poisoning.

---

## RED evidence — V14-B2

Against the pre-remediation production code, the new tests demonstrated that these cases incorrectly allowed confident resolution:

```text
valid grade source
+
{"source_id":"junk","value":9.0}
```

```text
valid grade source
+
{
  "source_id":"junk",
  "value":9.0,
  "source_class":"official_academic_record",
  "provenance":"grounded",
  "temporal":"valid",
  "specificity":"general"
}
```

```text
valid grade source
+
{"source_id":"junk","supplied_attributes":None}
```

```text
valid grade source
+
{"source_id":"junk","attribute":None,"value":9.0}
```

The exported adapter also reproduced the unsafe base-helper semantics.

These cases appeared among the 49 genuine RED failures.

---

## GREEN coverage — V14-B2

The remediated behavior requires:

```text
source with value but no usable attribute carrier
→ relation unknown
→ no confident target resolution
```

```text
supplied_attributes=None
→ malformed carrier
→ not equivalent to field absence
```

```text
attribute=None
→ malformed / relation unknown
→ not safely irrelevant
```

Adapter behavior now matches the hardened base helper.

Positive controls preserve:

```text
valid explicitly unrelated source
→ does not poison target
```

and:

```text
supplied_attributes=[]
→ explicit known empty carrier set
```

according to the existing contract.

---

# 5. Real RED → GREEN verification

## RED against pre-remediation production

The V14 tests were executed in an isolated temporary checkout using the repository production state before the remediation and the new test files from the working tree.

Result:

```text
49 failed
16 passed
198 deselected
exit code = 1
```

The failures were the intended V14-B1/B2 assertion failures.

No import or collection failure invalidated the RED proof.

## Adversarial GREEN

On the remediated working tree:

```text
65 passed
198 deselected
```

## Focal GREEN

Affected owners:

```text
test_university_domain_source_authority.py
test_university_domain_contradiction.py
test_university_domain_deadlines.py
test_university_domain_rules.py
```

Result:

```text
263 passed
```

---

# 6. Full regression verification

All verification was executed after the final production/test edits.

## University

```text
700 passed in 1.89s
```

## Domains

```text
4258 passed in 5.62s
```

## Global

```text
9769 passed in 29.92s
```

## Static / structural

```text
Ruff default                     PASS
Ruff --target-version py310      PASS
compileall -q cmm tests          PASS
dependency direction             1 passed
fresh import                     fresh_import=OK
placeholder scan                 clean
git diff --check                 clean
git diff --cached --check        clean
```

---

# 7. Regression closure

The following previously closed behavior remains covered by the full green suites:

```text
V13 malformed source scope                CLOSED
V13 malformed claim scope                 CLOSED
V13 malformed requested scope             CLOSED
V13 malformed supplied_attributes         CLOSED
V13 provenance="garbage"                 CLOSED
V13 missing/blank/non-string attribute    CLOSED

V12 strict boolean composition            CLOSED
V12 partial same-attribute evidence       CLOSED

V11 adapter malformed boundaries          CLOSED
V11 Workload strict booleans              CLOSED
V11 Performance malformed Mapping         CLOSED

V10 regressions                           CLOSED
V9 regressions                            CLOSED
```

Positive behavior remains supported:

```text
valid scalar source identities
valid scalar claim identities
valid scalar deadline values/references
valid scalar Performance observations
valid known unrelated evidence
coherent authority-only sources
absent scope semantics
valid string scope semantics
```

---

# 8. Scope review

Production changes remain limited to:

```text
cmm/domains/university/rules.py
```

Test changes:

```text
tests/domains/test_university_domain_source_authority.py
tests/domains/test_university_domain_contradiction.py
tests/domains/test_university_domain_deadlines.py
tests/domains/test_university_domain_rules.py
```

No production changes were required in:

```text
cmm/domains/permission_gate.py
cmm/domains/permission_resolution.py
cmm/domains/university/operations.py
cmm/domains/university/workflows.py
cmm/domains/university/catalog.py
other domains
```

Canonical counts remain:

```text
entities   = 14
resources  = 12
rules      = 10
operations = 11
workflows  = 7
```

The permission architecture remains untouched.

---

# 9. Git / roadmap state

The remediation was developed with changes left unstaged for human review.

The repository HEAD at verification time also contains two independent documentation-only commits made after the V13 remediation:

```text
544aedd docs(dev): define VS Code agent customization architecture
2e7c7ab docs(dev): plan VS Code customization inventory
```

`401d380` remains an ancestor of the current branch.

These commits affect only:

```text
docs/superpowers/specs/2026-08-12-vscode-agent-customization-design.md
docs/superpowers/plans/2026-08-12-vscode-customization-inventory-implementation-plan.md
```

and are unrelated to University Domain production behavior.

The Phase 10.22 roadmap state remains:

```text
Implemented, pending audit
```

No Independent Audit report is added to version control.

---

# 10. Critical assertions

```text
Collection-shaped source_id never becomes scalar authority identity: YES

Collection-shaped claim id never becomes scalar claim identity: YES

Collection-shaped deadline value/reference never confirms official deadline: YES

Collection-shaped Performance ref/outcome never means observed performance: YES

Unreferenced conflicting source never silently disappears: YES

Unreferenced conflicting claim never resolves automatically: YES

Source with unknown attribute relationship never becomes safely irrelevant: YES

supplied_attributes=None is distinguished from field absence: YES

attribute=None is distinguished from field absence: YES

Valid explicitly unrelated evidence remains safe: YES

Positive scalar identities/references remain supported: YES

V13 regressions remain closed: YES
V12 regressions remain closed: YES
V11 regressions remain closed: YES
V10 regressions remain closed: YES
V9 regressions remain closed: YES

Public helpers remain exception-safe: YES

Canonical counts remain 14/12/10/11/7: YES

Permission architecture untouched: YES
```

---

# Final recommendation

```text
READY FOR INDEPENDENT AUDIT V15
```

Phase 10.22 is **not** declared complete.

Independent Audit V15 decides closure.
