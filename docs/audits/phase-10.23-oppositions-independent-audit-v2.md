# Phase 10.23 Opposition Domain — Independent Audit V2

Date: 2026-08-14

## Scope

Independent re-audit of Phase 10.23 after Audit V1 remediation.

Repository candidate:

```text
branch: feature/phase-10-domain-intelligence
HEAD: 875d3a78d87c18c87c313a105b97aaeb117db059
```

Relevant commits:

```text
69ff719 docs(domains): freeze phase 10.23 oppositions design
6a876d8 feat(domains): implement phase 10.23 oppositions domain
6b352d9 docs(domains): reconcile phase 10.23 canonical namespace
49bff46 docs(domains): record phase 10.23 independent audit v1
875d3a7 fix(domains): remediate phase 10.23 audit v1 findings
```

Evidence bundle:

```text
cmm-phase-10.23-audit-v2-evidence-20260814-072402.tar.gz
SHA-256: ca259d278d4aa62fc740b61c901f65407e3f7e51711212ff8b2b4ab7bc775a63
```

The bundle's internal SHA-256 manifest was independently verified with zero mismatches.

---

# Executive verdict

**REMEDIATION REQUIRED**

Audit V1 remediation materially improved the domain and all seven collector-level V2 probes pass. However, deeper independent review of the exact remediated `rules.py`, the changed tests, canonical `Rule.evaluate(...)` paths, and additional adversarial inputs found six Important correctness/hardening defects.

No Critical finding was confirmed.

Current state must remain:

```text
Phase 10.23 — Implemented, remediation required after Independent Audit V2
```

It must not be marked audited, complete, or closed.

---

# Fresh verification reproduced from V2 bundle

All collector verification commands completed with exit code 0:

```text
pytest-oppositions=0
pytest-targeted-v2=0
pytest-domains=0
pytest-global=0
ruff-oppositions=0
ruff-oppositions-py310=0
syntax-compile-in-memory=0
fresh-import=0
git-diff-check-remediation=0
v2_adversarial_probe=0
```

Fresh totals:

```text
Opposition: 235 passed in 2.70s
Targeted hardened V2 group: 89 passed in 1.71s
Domains: 4761 passed in 15.54s
Global: 10272 passed in 69.47s
Ruff: PASS
Ruff py310: PASS
In-memory syntax compile: 14 modules
Fresh import: PASS
Remediation diff check: PASS
Tracked worktree parity: PASS
```

The seven collector V2 probes also returned:

```text
I1=PASS
I2=PASS
I3=PASS
I4=PASS
I5=PASS
I6=PASS
I7=PASS
ALL_PASS=true
```

Those probes establish that the exact V1 reproductions were improved. They do not establish complete closure of the surrounding contracts.

---

# What V1 remediation successfully fixed

## I1 — Health capacity widening

The effective capacity now uses the most restrictive known value:

```python
capacity = min(capacity, health_cap)
```

A Health cap greater than known primary availability no longer increases capacity.

**V1 finding status:** substantially fixed.

## I4 — conflicting / superseded temporal values

`conflicting` and `superseded` are now explicit closed states and are no longer normalized to `unknown`.

**V1 finding status:** fixed for the audited states.

## I5 — simple denominator mismatch and malformed chronology strings

Different denominators are no longer combined into one raw-score trend group, and arbitrary strings such as `"zzz"` no longer establish chronology.

**V1 finding status:** improved, but chronology handling introduced a new blocking edge case (V2-I3 below).

## I6 / I7 — duplicate identities

Conflicting mock and route identities are now detected and excluded from the direct trend/recommendation path.

**V1 findings:** improved, but conflict preservation is incomplete in public/canonical outputs (V2-I4 and V2-I5).

---

# Findings

## V2-I1 — Important — Invalid or missing target date still permits a definitive feasible result

### Requirement

Frozen design §13 and §39 require:

```text
validate evidence
→ hard constraints
→ available capacity
→ target-date feasibility
→ scenarios
```

and explicitly require tests for:

```text
target date missing
target date temporally invalid/unknown
```

Malformed/unknown decision-relevant evidence must fail closed.

### Code evidence

`cmm/domains/oppositions/rules.py`:

```text
1448: target = _parse_non_negative_int(target_days)

1449-1454:
malformed_numeric_any checks remaining/review/mock/available,
but does not include an invalid target_days value.

1543:
resolved = not (evidence_unknown or has_malformed_numeric or capacity_unknown)

1562:
only required_work > 0 and target == 0 is treated as
target_date_infeasible.

1575-1576:
all remaining resolved cases become feasibility = "feasible".
```

### Independent reproduction

Using the exact `rules.py` from the V2 bundle:

```python
evaluate_study_feasibility(
    remaining_hours=10,
    available_hours=30,
    target_days="soon",
)
```

Actual:

```text
feasibility = feasible
feasible = True
unresolved = False
target_date_invalid = True
```

Canonical `StudyFeasibilityRule.evaluate(...)` consequently emits:

```text
message = "Study plan is feasible."
severity = INFO
```

The same fail-open pattern occurs for:

```text
target_days = -1
target_days = True
```

and a missing target (`None`) can also return a definitive feasible result.

### Expected

A malformed/unknown target date that is material to target-date feasibility must not coexist with a definitive `feasible=True`.

At minimum:

```text
target_date_invalid=True
→ feasible=False
→ unresolved=True or explicit infeasible state according to contract
```

### Impact

A malformed deadline dimension is detected but ignored when producing the final feasibility verdict. This violates validation-first and fail-closed semantics.

### Minimal remediation

Include target-date validity in the `resolved` gate, distinguish missing vs malformed/unknown where required, and add canonical Rule-path tests—not only helper flag tests.

---

## V2-I2 — Important — Syllabus duplicate identities still double-count depth and remain order-dependent

### Requirement

Frozen design §12 / §38 requires:

```text
duplicate topic identity must not double-count
deterministic order-invariant result
contradictory topic-level evidence must remain explicit
multidimensional coverage must preserve depth/revision/etc.
```

### Code evidence

`rules.py` around 1291-1302:

```python
if studied_state == "yes":
    ...
    studied.add(identity)
    studied_records += 1
    if depth_value is not None:
        depth_total += depth_value
        depth_count += 1
```

A duplicate `"yes"` record for an already-known identity enters this block again.

Conflict cleanup at 1319-1324 removes the identity from `studied`/`pending`, but does not roll back `depth_total` or `depth_count`.

### Independent reproduction A — identical duplicate double-counting

```python
topics = (
    {"id": "t1", "studied": "yes", "depth": 3},
    {"id": "t1", "studied": "yes", "depth": 3},
)
```

Actual:

```text
studied_count = 1
study_depth_total = 6
study_depth_records = 2
duplicate_double_counted = False
complete = True
```

The topic identity is deduplicated for studied count but **not** for depth.

### Independent reproduction B — conflicting duplicate order dependence

Forward:

```text
yes(depth=3), no(depth=1)
```

produces:

```text
conflicting_count = 1
study_depth_total = 3
study_depth_records = 1
```

Reverse:

```text
no(depth=1), yes(depth=3)
```

produces:

```text
conflicting_count = 1
study_depth_total = 0
study_depth_records = 0
```

### Expected

All dimensions for a topic identity must be normalized once, with conflicting evidence represented conservatively and independently of input order.

### Impact

The same semantic evidence set can report different study depth solely because record order changed, and exact duplicate topics inflate a multidimensional coverage component.

### Minimal remediation

Aggregate the entire topic evidence per identity before any dimension counters are updated. Identical duplicates deduplicate; incompatible evidence becomes a per-topic conflict. Compute depth/revision/mock/review dimensions from normalized identities only.

---

## V2-I3 — Important — Chronology fix crashes on mixed valid ISO timezone forms and leaks `datetime` objects

### Requirement

Mock trend chronology must be valid, deterministic, robust, and usable through structured public results. Public malformed/edge input must not leak an accidental exception.

### Code evidence

`rules.py`:

```text
1634-1643:
_parse_chronology_date returns datetime.fromisoformat(...)

1696-1697:
parsed datetime is stored in every timeline entry

1779:
best_group is sorted directly by entry["parsed_date"]

1806:
timeline (including parsed datetime objects) is returned publicly
```

### Independent reproduction A — valid mixed chronology crashes

```python
mocks = (
    {
        "id": "m1",
        "score": 5,
        "total": 10,
        "scoring": "standard",
        "format": "test",
        "date": "2026-01-01",
    },
    {
        "id": "m2",
        "score": 6,
        "total": 10,
        "scoring": "standard",
        "format": "test",
        "date": "2026-02-01T00:00:00+00:00",
    },
)
```

Both strings are valid ISO chronology.

Actual:

```text
TypeError:
can't compare offset-naive and offset-aware datetimes
```

because one parsed datetime is naive and the other timezone-aware.

### Independent reproduction B — public result is no longer JSON-serializable

For a normal valid date:

```python
result = evaluate_mock_performance(...)
json.dumps(result)
```

Actual:

```text
TypeError: Object of type datetime is not JSON serializable
```

because `parsed_date` is included in the public `timeline`.

### Expected

Normalize all chronological values to a common comparable representation, and keep internal parsed objects out of the public structured result.

### Impact

Valid chronology can crash the rule instead of producing a structured result. The remediation also introduced a non-JSON-safe public output.

### Minimal remediation

Normalize to a single timeline basis, e.g. a consistently timezone-normalized value or a sortable scalar, use it only internally, and return only JSON-safe temporal representations.

Add naive+aware, `Z`, offset, and serialization regression tests.

---

## V2-I4 — Important — Conflicting mock identity still produces first-wins public timeline and canonical Rule path hides the conflict

### Requirement

V1 I6 required conflicting duplicate mock identities to stop being first-wins/order-dependent. Phase 10 presentation/trace requirements require contradictions and uncertainty to remain visible.

### Code evidence

`rules.py`:

```text
1730-1737:
duplicates are grouped and a conflict is detected.

1738:
observation = dict(unique[0])

1748:
that first observation is still appended to timeline.

1788:
only conflicting_identity_count is returned; no conflicting identity list.

1806:
the first-wins timeline is returned.

2474-2481:
MockExamInterpretationRule metadata does not propagate
conflicting_identity_count or conflict identities at all.
```

### Independent reproduction

Same `m1` identity:

```text
A1 = score 5, date 2026-01-01
A2 = score 8, date 2026-03-01
B  = stable second mock
```

Both permutations correctly yield:

```text
trend_inferred=False
conflicting_identity_count=1
```

but public timeline differs:

```text
A1,A2,B → timeline shows m1 score=5/date=2026-01-01
A2,A1,B → timeline shows m1 score=8/date=2026-03-01
```

Canonical `MockExamInterpretationRule.evaluate(...)` then emits an INFO finding with only:

```text
observation_count
trend_state
trend_inferred
one_mock_is_trend
capacity_inferred
pass_guaranteed
```

The duplicate conflict is absent from canonical rule metadata.

### Expected

A conflicting mock identity should not expose an arbitrary representative as if it were the normalized observation. Canonical Rule output must preserve the conflict/uncertainty.

### Impact

The direct trend decision is now safe, but downstream presentation or consumers can still see a first-wins observation and the normal Rule path can hide the contradiction entirely.

### Minimal remediation

Represent conflicting identity explicitly (e.g. conflict IDs / unresolved observation) and make timeline deterministic or exclude unresolved conflicting observations. Propagate conflict information through `MockExamInterpretationRule`.

---

## V2-I5 — Important — Conflicting alternative route is marked `resolved=True` and the canonical Rule path suppresses the conflict

### Requirement

V1 I7 remediation contract requires:

```text
conflicting duplicate route
→ unresolved/blocked
→ never automatically recommended
→ order invariant
```

Phase 10 presentation must preserve contradictions and uncertainty.

### Code evidence

`rules.py`:

```text
1912-1915:
conflicting route ID is detected and excluded.

1972:
resolved = not malformed_route_member

1974-1991:
result can therefore have:
  resolved=True
  conflicting_route_ids=(...)
  recommendation=None

2513-2522:
AlternativeRouteRule treats resolved=True as a successful INFO comparison.

2525-2532:
canonical finding metadata omits conflicting_route_ids entirely.
```

### Independent reproduction

Only one alternative identity, with two incompatible observations:

```text
alt x: eligibility=eligible, overlap=.9
alt x: eligibility=ineligible, overlap=.1
```

Actual helper result:

```text
resolved = True
conflicting_route_ids = ("x",)
trade_offs = ()
recommendation = None
```

Canonical Rule result:

```text
message = "Alternative routes compared; the primary target is unchanged."
severity = INFO
metadata does not include the conflict.
```

### Expected

The affected comparison must be unresolved/conditional, or at minimum canonical Rule output must explicitly preserve that an alternative identity is conflicting and cannot be resolved.

### Impact

The fix prevents automatic recommendation of the conflicting route, but canonical reasoning can still report the comparison as resolved and hide the actual contradiction.

### Minimal remediation

Make conflict participate in resolution/gap semantics and propagate `conflicting_route_ids` through the Rule finding. Add helper + canonical Rule-path tests.

---

## V2-I6 — Important — Malformed authorized University workload projection is silently ignored

### Requirement

Frozen design §43 requires University → Oppositions:

```text
only authorized availability/load/deadline projection consumed
malformed projection remains invalid
most-restrictive/fail-closed semantics
```

### Code evidence

`rules.py`:

```text
1523:
uni_available = parse(...available_hours)

1524:
uni_workload = parse(...workload_hours)

1525-1530:
malformed available_hours can set capacity_unknown.

1531-1532:
workload is subtracted only if successfully parsed.
```

There is no corresponding fail-closed branch when `workload_hours` was supplied but parsing returns `None`.

### Independent reproduction

```python
evaluate_study_feasibility(
    remaining_hours=8,
    available_hours=10,
    university_projection={
        "authorized": True,
        "workload_hours": "many",
    },
)
```

Actual:

```text
university_authorized = True
capacity_unknown = False
capacity_hours = 10
feasibility = feasible
feasible = True
```

Canonical `StudyFeasibilityRule` reports:

```text
"Study plan is feasible."
severity = INFO
```

### Expected

A supplied malformed authorized workload constraint must remain invalid/unknown and cannot be silently dropped before feasibility.

### Impact

A decision-critical supporting-domain workload can disappear from the effective constraints, widening apparent study capacity.

### Minimal remediation

If an authorized University constraint field is present but malformed, mark the relevant feasibility state unresolved/fail-closed. Add malformed `workload_hours` and mixed valid/malformed projection tests.

---

# Minor findings

## V2-M1 — Capacity provenance is incorrect when a non-binding Health cap is wider

Code:

```python
capacity = min(capacity, health_cap)
cap_source = "health"
```

Example:

```text
user capacity = 8
health cap = 20
effective capacity = 8
capacity_source = "health"
```

The numeric fix is correct, but provenance says Health determined a value actually determined by the existing user constraint.

This does not currently widen feasibility, so it is non-blocking, but it weakens traceability.

Recommended fix: preserve the source of the binding constraint, or represent multiple candidate sources and the selected minimum.

---

## V2-M2 — Documentation/comment reconciliation has two stale statements

### Reference typo

`docs/reference/oppositions-domain.md` around lines 131-132 says:

```text
such supporting-domain caps may
ever widen a known primary-domain capacity
```

The intended statement is clearly:

```text
may never widen
```

### Catalog comment

`cmm/domains/oppositions/catalog.py` still says the original singular namespace was sanctioned by spec §7 as a "mechanically different canonical form".

The canonical plural namespace is correct, but the final reconciliation established that the actual justification is the pre-existing `DomainOperationDefinition` contract, not a §7 exception.

Non-functional, but documentation should be made internally consistent.

---

# Findings summary

```text
Critical: 0
Important: 6
Minor: 2
Notes: 0
```

Blocking findings:

```text
V2-I1 target-date invalid/missing fails open
V2-I2 syllabus duplicate dimensions still double-count/order-vary
V2-I3 mock chronology mixed-timezone crash + non-JSON output
V2-I4 mock duplicate conflict still first-wins in timeline / hidden by Rule
V2-I5 alternative conflict marked resolved / hidden by Rule
V2-I6 malformed University workload projection silently ignored
```

---

# Test coverage assessment

The remediation tests correctly test the examples they were written for, but several assertions are narrower than the frozen semantic contract:

- target-date tests cover only `0`, not malformed/missing/unknown target values;
- syllabus duplicate tests compare studied/pending/conflict counts but not depth/revision/mock dimensions;
- mock chronology tests cover an unparseable string but not valid mixed timezone forms or JSON serialization;
- mock duplicate test compares trend fields but not the returned timeline or canonical Rule finding;
- alternative duplicate test checks recommendation/conflict IDs but not `resolved` or canonical Rule propagation;
- University projection tests do not exercise malformed `workload_hours`.

This explains why all 235 Opposition tests and the seven collector probes can pass while the defects above remain reproducible.

---

# Documentation status

Current documentation correctly keeps Phase 10.23 at:

```text
Implemented, pending Independent Audit V2
```

After this V2 verdict, the correct state is:

```text
Implemented, remediation required after Independent Audit V2
```

Do not mark DP-023 independently audited/closed yet.

---

# Final verdict

**REMEDIATION REQUIRED**

The V1 remediation is directionally correct and fixed several core failure modes. However, it is not yet safe to close Phase 10.23 because malformed constraints can still produce definitive feasibility, duplicate syllabus dimensions are not fully normalized, chronology can crash on valid ISO inputs, and duplicate conflicts are not consistently preserved through canonical Rule paths.

The next remediation should be narrow:

```text
V2-I1 .. V2-I6
+
V2-M1 .. V2-M2 while touching the same areas
```

No architectural redesign or shared-infrastructure refactor is required.
