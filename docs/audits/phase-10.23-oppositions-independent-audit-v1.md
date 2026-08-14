# Phase 10.23 Opposition Domain — Independent Audit V1

Date: 2026-08-14

Audit candidate:

- Base: `69ff719` — `docs(domains): freeze phase 10.23 oppositions design`
- Implementation: `6a876d8` — `feat(domains): implement phase 10.23 oppositions domain`
- Namespace reconciliation: `6b352d9` — `docs(domains): reconcile phase 10.23 canonical namespace`
- Range audited: `69ff719..6b352d9`

## Verdict

**REMEDIATION REQUIRED**

No Critical findings were confirmed.

Seven Important findings were confirmed in semantic rule behavior / adversarial hardening. The implementation architecture, namespace reconciliation, external-side-effect boundaries, package boundary, and verification baseline are otherwise strong.

---

## Verification reproduced from the audit bundle

Fresh evidence captured by the read-only collector:

- Opposition suite: `224 passed in 7.32s`
- Domain suite: `4750 passed in 35.81s`
- Global suite: `10261 passed in 153.09s`
- Ruff Opposition: PASS
- Ruff Opposition with `--target-version py310`: PASS
- In-memory syntax compilation: PASS (`14` production modules)
- Fresh import: PASS
- Candidate `git diff --check`: PASS
- Repository tracked-state parity before/after collector: PASS

The collector's explicit `pytest-oppositions` command returned exit code 4 because the collector referenced a nonexistent test filename. This is a collector defect only. The canonical glob execution `tests/domains/test_oppositions_domain_*.py` ran all actual Opposition tests and passed 224/224.

---

# Architecture assessment

## PASS — package boundary

The candidate contains the expected 14-module specialized package:

- `__init__.py`
- `bootstrap.py`
- `catalog.py`
- `definition.py`
- `integration.py`
- `memory.py`
- `operations.py`
- `permissions.py`
- `presentation.py`
- `profile.py`
- `resources.py`
- `rules.py`
- `trace.py`
- `workflows.py`

No parallel Opposition kernel, memory store, planner, workflow engine, permission engine, scheduler, scraper, external connector, or model gateway was identified.

## PASS — canonical namespace reconciliation

The shared `DomainOperationDefinition` contract requires:

```python
slug = domain_id.removeprefix("domain:")
if operation_id.split(".", 1)[0] != slug:
    raise DomainOperationContractError(...)
```

For `domain:oppositions`, the valid registered namespace is therefore `oppositions.*`.

The documentation reconciliation in `6b352d9` is correct. The singular `opposition.*` operation namespace in the original frozen design was incompatible with the pre-existing shared contract.

## PASS — external verification boundary

The Opposition pack models official verification as read-only / official-only semantics and does not implement network, scraping, polling, scheduler, browser automation, or notification infrastructure.

## PASS — integration transaction structure

`integration.py` follows the intended validation-first / snapshot / mutate / rollback structure and uses registry `snapshot_state()` / `restore_state()` APIs.

Existing rollback tests compare full registry snapshots, not only absence of Opposition IDs.

---

# Findings

## I1 — Important — Health functional cap can widen available study capacity

### Requirement violated

Health → Oppositions is a **minimal restrictive functional constraint projection**. Supporting-domain information must not widen the primary domain's effective permission/constraint state. Hard constraints must precede preferences.

### Evidence

`cmm/domains/oppositions/rules.py`, `evaluate_study_feasibility`, approximately lines 1445–1463:

```python
capacity = available
...
if _grants_trust(health.get("authorized")):
    health_authorized = True
    health_cap = _parse_non_negative_number(
        health.get("functional_cap_hours")
    )
    if health_cap is not None:
        capacity = health_cap
        cap_source = "health"
```

The Health cap **replaces** existing capacity instead of narrowing it.

### Reproduction

Conceptually:

```python
evaluate_study_feasibility(
    remaining_hours=12,
    available_hours=10,
    health_constraint={
        "authorized": True,
        "functional_cap_hours": 15,
    },
)
```

Before Health projection:

```text
capacity = 10
remaining work = 12
=> infeasible
```

After current code:

```text
capacity = 15
=> feasible
```

A supporting-domain "cap" has increased the available capacity from 10 to 15.

### Expected

```python
capacity = min(capacity, health_cap)
```

when both values are known.

### Actual

Health projection replaces `capacity`.

### Impact

A plan that was infeasible under the user's known availability can become feasible solely because Health supplied a looser cap. This reverses the intended most-restrictive constraint semantics.

### Minimal remediation

Use the minimum of current capacity and authorized Health cap. Add a regression test where the Health cap is greater than existing availability.

---

## I2 — Important — Target-date feasibility is not actually enforced

### Requirement violated

Frozen design §13 requires the canonical pipeline:

```text
validate evidence
→ resolve hard constraints
→ resolve available capacity
→ check target-date feasibility
→ build valid scenarios
→ compare trade-offs
→ emit proposal
```

The rule must evaluate whether a study strategy is realistic under a target date.

### Evidence

`evaluate_study_feasibility` parses `target_days`:

```python
target = _parse_non_negative_int(target_days)
```

but feasibility is decided only by:

```python
if not resolved or capacity is None:
    feasibility = "unresolved"
elif required_work > capacity:
    feasibility = "infeasible"
else:
    feasibility = "feasible"
```

`target` is used only afterwards to calculate:

```python
daily_hours = required_work / target
```

It does not constrain feasibility.

### Reproduction

Conceptually:

```python
evaluate_study_feasibility(
    remaining_hours=20,
    available_hours=30,
    target_days=0,
)
```

`0` is accepted by `_parse_non_negative_int`, so:

```text
required_work = 20
capacity = 30
20 <= 30
=> feasible
```

A positive workload with zero target days is classified feasible.

More broadly, two inputs with the same `remaining_hours` and `available_hours` but radically different target dates receive the same feasibility outcome.

### Expected

Target-date feasibility must participate in the hard feasibility decision. A zero-day target with remaining work must be infeasible or unresolved. Target-date capacity must be calculated under explicit semantics.

### Actual

Target date is largely presentational.

### Impact

The rule can call a study plan realistic while ignoring the deadline dimension it is explicitly required to reason about.

### Minimal remediation

Define whether `available_hours` is total-through-target or per-period capacity, then enforce target-date feasibility accordingly. Reject or block `target_days == 0` when required work is positive. Add boundary tests.

---

## I3 — Important — Conflicting duplicate syllabus topics can be collapsed into false completeness

### Requirement violated

Syllabus coverage must preserve contradictory structured evidence. Duplicate IDs must not double-count, and aggregate/normalization logic must not erase conflicts.

### Evidence

`evaluate_syllabus_coverage`, approximately lines 1247–1314:

```python
studied: set[str] = set()
pending: set[str] = set()
...
if studied_state == "yes":
    studied.add(identity)
elif studied_state == "no":
    pending.add(identity)
...
known_identities = studied | pending
pending = pending - studied
...
complete = bool(
    studied_have_identity
    and not malformed
    and pending_count == 0
    and unknown_topic_count == 0
    ...
)
```

### Reproduction

Conceptually:

```python
topics = (
    {"id": "t1", "studied": "yes"},
    {"id": "t1", "studied": "no"},
)
```

Current behavior:

```text
studied = {"t1"}
pending = {"t1"}
pending = pending - studied
pending = {}
```

With current syllabus metadata, the contradictory topic can contribute to `complete=True`.

Reversing the two records does not fix the semantic conflict because both sets still contain `t1`; the conflict is simply discarded.

### Expected

A duplicate identity with incompatible structured states must produce an explicit conflict/unresolved condition and block completeness.

### Actual

"studied" wins implicitly over "pending" through set subtraction.

### Impact

The domain can assert complete syllabus coverage despite direct contradictory topic-level evidence.

### Minimal remediation

Aggregate each topic identity into a normalized per-topic evidence state. If incompatible states exist for one identity, mark that topic conflicting/unknown and block `complete`.

Add tests for:

- yes + no duplicate;
- revision done + pending duplicate;
- conflicting depth/state combinations.

---

## I4 — Important — Temporal rule does not preserve the advertised `superseded` and `conflicting` states

### Requirement violated

The frozen design and rule docstring require distinctions including:

```text
current
stale/expired
superseded
future
unknown
conflicting
missing
malformed
```

### Evidence

Closed temporal values in `rules.py` are only:

```python
TEMPORAL_VALID = "valid"
TEMPORAL_EXPIRED = "expired"
TEMPORAL_FUTURE = "future"
TEMPORAL_UNKNOWN = "unknown"
TEMPORAL_TIMELESS = "timeless"
```

`_normalize_temporal()` maps every other value to `unknown`.

`classify_opposition_temporal()` can emit:

```text
missing
malformed
stale
future
unknown
current
undergrounded
```

but there is no branch that emits `superseded` or `conflicting`.

Existing temporal tests label conflict cases but pass `temporal="unknown"` and assert `unknown`.

### Reproduction

Conceptually:

```python
classify_opposition_temporal(
    fact={
        "temporal": "conflicting",
        "grounded": True,
        "source_reference": "ref",
    },
    decision_critical=True,
)
```

normalizes `"conflicting"` to `TEMPORAL_UNKNOWN`.

Likewise `"superseded"` becomes unknown.

### Expected

The semantic distinction must survive into the result, or the API must receive an explicit conflict/supersession field and emit those states.

### Actual

Distinct temporal states collapse to `unknown`.

### Impact

Downstream monitoring, presentation, and strategy-review logic cannot distinguish conflict from unknown evidence or explicit supersession.

### Minimal remediation

Add explicit closed temporal states / structured input fields and regression tests for both `conflicting` and `superseded`.

---

## I5 — Important — Mock trend comparability is insufficient: denominator and chronology are not validated

### Requirement violated

A trend may be inferred only from comparable mocks with chronologically grounded evidence. Different scoring bases must not be naively combined.

### Evidence

Grouping key:

```python
key = (scoring, mock_format)
```

`total` is not part of comparability.

A record becomes trend-eligible when:

```python
score is not None
and total is not None
and total > 0
and scoring != MOCK_SCORING_MISSING
and date is not None
```

`date` is merely a nonblank string from `_usable_scalar_string`.

Chronology is then:

```python
ordered = sorted(best_group, key=lambda entry: str(entry["date"]))
trend_slope = ordered[-1]["score"] - ordered[0]["score"]
```

No date parser or temporal validation is applied.

### Reproduction A — incompatible denominators

```text
m1: score=40, total=50
m2: score=50, total=100
same format/scoring
```

These are placed in the same comparable group and raw score slope is `+10`, even though normalized performance falls from 80% to 50%.

### Reproduction B — malformed chronology

```text
m1.date = "zzz"
m2.date = "2026-02-01"
```

Both dates are nonblank strings, so both can establish a trend. Lexicographic sorting is treated as chronology.

### Expected

Comparability must incorporate denominator / normalized scoring basis, and dates must be syntactically and temporally validated before chronological trend inference.

### Actual

Same scoring label + format + nonblank date is sufficient.

### Impact

The system can infer a positive or negative performance trend from incomparable or temporally invalid mocks.

### Minimal remediation

Normalize score to a common comparable metric or require identical denominators/scoring configuration. Parse and validate dates; unknown/malformed chronology must block trend inference.

---

## I6 — Important — Conflicting duplicate mock IDs are first-wins and can make trend semantics input-order dependent

### Requirement violated

Duplicate identities must not silently erase contradictory evidence. Mock semantics are required to be input-order invariant.

### Evidence

`evaluate_mock_performance`:

```python
if identity is not None:
    if identity in seen:
        duplicates += 1
        continue
    seen.add(identity)
```

The second occurrence of the same mock ID is discarded without checking whether the records agree.

### Reproduction

Consider:

```text
A1: id=m1, date=2026-01-01, score=5, total=10
A2: id=m1, date=2026-03-01, score=5, total=10
B : id=m2, date=2026-02-01, score=10, total=10
```

Order:

```text
A1, A2, B
```

keeps A1 and produces an increasing slope.

Order:

```text
A2, A1, B
```

keeps A2 and produces a decreasing slope after chronological sort.

The duplicate conflict is never represented.

Existing `test_order_invariance` uses distinct IDs and therefore does not exercise this case.

### Expected

Conflicting duplicates should make the evidence unresolved/malformed or be explicitly represented as a conflict; they must not select a record based on input order.

### Actual

First record wins.

### Impact

Trend direction can depend on input ordering for semantically identical evidence sets.

### Minimal remediation

Canonicalize duplicate IDs. Identical duplicates may deduplicate. Incompatible duplicates must create a conflict and block trend inference.

---

## I7 — Important — Alternative-route duplicate IDs are also first-wins and violate the stated order-invariance contract

### Requirement violated

`AlternativeRouteRule` explicitly states that input order must not change semantics and malformed/conflicting route identity must not merge routes.

### Evidence

`compare_alternative_routes`:

```python
if route_id in route_ids:
    continue
route_ids.add(route_id)
```

No compatibility comparison is performed between duplicate records.

Recommendation is then computed from whichever record for that ID appeared first.

Existing `test_order_invariance` only permutes two distinct route IDs.

### Reproduction

Two records share `id="alt1"`:

```text
record A: eligibility=eligible, syllabus_overlap=0.9
record B: eligibility=ineligible, syllabus_overlap=0.1
```

If A comes first, `alt1` may be recommended.

If B comes first, `alt1` is blocked as ineligible.

### Expected

Conflicting duplicate identities must produce an unresolved/conflicting route state independent of input order.

### Actual

First record wins.

### Impact

The recommendation can change purely from input ordering, contrary to the rule contract.

### Minimal remediation

Group alternatives by route ID before evaluation. Deduplicate compatible copies; mark incompatible copies conflicting/unresolved. Add full semantic permutation tests.

---

# Additional observations

## N1 — Note — Existing test suite is broad but several order-invariance tests are too weak

Examples:

- mock order test only checks `trend_inferred`, not normalized semantic output or conflicting duplicate identities;
- alternative-route order test only compares `alternatives_considered`, not recommendation/trade-off semantics;
- syllabus duplicate test checks only double-counting of identical `studied=yes` records, not incompatible duplicate records;
- temporal tests use `unknown` in tests whose names refer to conflicts rather than exercising an actual conflict representation.

These weaknesses explain why 224 Opposition tests remain green despite the findings above.

## N2 — Note — `rules.py` is disproportionately large

`rules.py` is roughly 2,587 lines and contains six rules plus many normalization helpers and DP-023 helpers.

This is not itself a Phase 10.23 correctness failure, but it increases the chance that semantic normalization behavior drifts between rules. A later refactor may be justified after audit closure; it should not be mixed into remediation unless necessary for correctness.

## N3 — Note — Collector artifact includes macOS AppleDouble `._*` files

The tar archive contains `._*.py` metadata files generated by macOS archive behavior. Git status parity shows they are not repository files. They were ignored for semantic audit.

---

# Requirements coverage assessment

## Strong / no blocking finding found

- one shared Domain Intelligence infrastructure;
- exact specialized package boundary;
- canonical `domain:oppositions`;
- correct `oppositions.*` operation namespace after reconciliation;
- 14 entities / 11 resources / 6 rules / 10 operations / 7 workflows surface;
- no Opposition-local memory store;
- no external connector/scheduler/scraper;
- official-only read-only verification model;
- proposal ≠ adoption invariant in strategy helper;
- alternative comparison does not directly mutate target;
- one mock is not considered a trend;
- strict boolean authorization helper uses literal `True`;
- Health/University direct store imports absent;
- registration uses validation-first + snapshots + rollback;
- import is side-effect free under captured verification;
- global suite remains green;
- Ruff/py310 clean.

## Blocking semantic hardening gaps

- most-restrictive Health capacity constraint;
- real target-date feasibility;
- syllabus duplicate conflict preservation;
- temporal state fidelity;
- mock comparability/chronology;
- mock duplicate conflict/order invariance;
- alternative duplicate conflict/order invariance.

---

# Test coverage assessment

The 224-test Opposition suite provides strong nominal and malformed-input coverage, but the adversarial matrix is incomplete in exactly the places where set/dedup/grouping logic can erase contradictions.

Required remediation tests should be added before code changes for every Important finding.

At minimum add:

1. Health cap greater than existing capacity cannot widen capacity.
2. Positive remaining work + zero target days cannot be feasible.
3. Same syllabus topic `yes` + `no` blocks completeness.
4. Temporal `conflicting` and `superseded` remain distinct.
5. Same format/scoring but different denominators cannot create a raw-score trend.
6. Malformed/non-chronological date cannot establish trend.
7. Conflicting duplicate mock IDs are unresolved and permutation-invariant.
8. Conflicting duplicate route IDs are unresolved and permutation-invariant.

---

# Documentation assessment

Namespace reconciliation is correct and should remain.

However, Phase 10.23 must remain:

```text
Implemented, pending independent audit
```

until these Important findings are remediated and re-audited.

`DP-023` must not be promoted to audited/closed based solely on the current green suite.

---

# Finding totals

- Critical: **0**
- Important: **7**
- Minor: **0**
- Notes: **3**

---

# Final verdict

**REMEDIATION REQUIRED**

The Phase 10.23 architecture is sound and the implementation has a strong verification baseline, but independent inspection found multiple cases where contradictory or restrictive evidence can be collapsed incorrectly:

- a Health cap can widen capacity;
- target-date feasibility is not enforced;
- duplicate syllabus conflicts can disappear;
- temporal conflict/supersession states collapse;
- mock comparability and chronology are too permissive;
- conflicting duplicate mocks are input-order dependent;
- conflicting duplicate alternatives are input-order dependent.

These are exactly the kind of adversarial semantic defects that the Phase 10 hardening standard is intended to reject.

Do not close the independent audit yet.

Recommended next state:

```text
Phase 10.23 — Implemented, remediation required after Independent Audit V1
```

---

# Remediation V1

Strict remediation pass for the seven Important findings in the original audit
above.  The original findings, evidence, and verdict are preserved unchanged.

Date: 2026-08-14

Method: for each finding, a RED regression test was written first and observed
failing for the expected semantic reason; a minimal production fix made it GREEN;
nearby regressions were re-run.

Verification after remediation:

- Opposition suite: `235 passed`
- Hardened targeted regression group: `89 passed`
- Relevant precedent/security regression group: `484 passed`
- Domain suite: `4761 passed`
- Ruff: PASS
- Ruff `--target-version py310`: PASS
- `compileall`: PASS
- Fresh import: PASS
- `git diff --check`: PASS

## I1 — Health functional cap can widen available study capacity

Status: FIXED IN REMEDIATION V1

- Test added: `test_health_cap_cannot_widen_known_availability` and
  `test_health_cap_can_narrow_capacity` in
  `tests/domains/test_oppositions_domain_health_projection.py`.
- Root cause: an authorized Health `functional_cap_hours` **replaced** the known
  primary-domain capacity instead of narrowing it.
- Fix: `evaluate_study_feasibility` now applies `capacity = min(capacity, cap)`
  when both are known, and only adopts the Health cap when no primary-domain
  capacity is known. A supporting-domain cap can never widen a known capacity.
- Verification: RED observed (widen case produced capacity `15`); GREEN after
  fix (capacity `10`, plan infeasible); boundary case capacity `6` passes.

## I2 — Target-date feasibility is not actually enforced

Status: FIXED IN REMEDIATION V1

- Tests added: `test_zero_day_target_with_remaining_work_not_feasible` and
  `test_target_date_constraints_affect_feasibility` in
  `tests/domains/test_oppositions_domain_study_feasibility.py`.
- Root cause: `target_days` was parsed but feasibility was decided only by
  `required_work > capacity`; a zero-day target with positive work was feasible.
- Fix: under the interpretation already supported by current contracts —
  `available_hours` is total available capacity through the study horizon, and
  `target_days` is the deadline dimension — a positive workload with a zero-day
  target window now yields `infeasible` with a `target_date_infeasible` hard
  constraint. Target-date feasibility is a real stage in the canonical pipeline.
- Verification: RED observed (a zero-day target was `feasible`); GREEN after
  fix; target-date constraints now demonstrably gate feasibility.

## I3 — Conflicting duplicate syllabus topics can be collapsed into false completeness

Status: FIXED IN REMEDIATION V1

- Test added: `test_conflicting_duplicate_topic_blocks_completeness` in
  `tests/domains/test_oppositions_domain_syllabus_coverage.py` (both `yes,no`
  and `no,yes` permutations normalize identically).
- Root cause: `studied`/`pending` were sets; `pending = pending - studied`
  silently discarded a topic present as both studied and pending.
- Fix: topics are now aggregated per identity; an identity with incompatible
  studied states becomes a conflict (`conflicting_count`, `conflicting_topics`),
  is excluded from denominators, and blocks `complete=True`. Existing weak
  `test_order_invariance` was strengthened to compare normalized semantic meaning.
- Verification: RED observed (complete was `True` for the conflict); GREEN after
  fix (complete `False`, `conflicting_count == 1`).

## I4 — Temporal rule does not preserve the advertised `superseded` and `conflicting` states

Status: FIXED IN REMEDIATION V1

- Tests added: `test_conflicting_temporal_state_preserved` and
  `test_superseded_temporal_state_preserved` in
  `tests/domains/test_oppositions_domain_temporal_validity.py`.
- Root cause: closed temporal values lacked `conflicting`/`superseded`;
  `_normalize_temporal` mapped them to `unknown`.
- Fix: added `TEMPORAL_CONFLICTING` and `TEMPORAL_SUPERSEDED` closed states; they
  normalize and classify distinctly. `superseded` is never made current, and
  decision-critical `conflicting`/`superseded` facts preserve a verification need.
- Verification: RED observed (both mapped to `unknown`); GREEN after fix
  (`conflicting` → `conflicting`, `superseded` → `superseded`).

## I5 — Mock trend comparability is insufficient: denominator and chronology are not validated

Status: FIXED IN REMEDIATION V1

- Tests added: `test_different_denominators_prevent_raw_score_trend` and
  `test_malformed_chronology_blocks_trend` in
  `tests/domains/test_oppositions_domain_mock_exam.py`.
- Root cause: comparability grouped by `(scoring, format)` only, and dates were
  treated as orderable by lexical string.
- Fix: comparability now includes the scoring base/denominator
  `(scoring, format, total)`, and chronology is parsed with stdlib ISO handling
  (`datetime.fromisoformat`); unparseable dates block trend inference.
- Verification: RED observed (raw-score trend inferred from different
  denominators; `"zzz"` treated as chronology); GREEN after fix (no trend in
  both cases).

## I6 — Conflicting duplicate mock IDs are first-wins and input-order dependent

Status: FIXED IN REMEDIATION V1

- Test added: `test_conflicting_duplicate_mock_order_invariance` in
  `tests/domains/test_oppositions_domain_mock_exam.py`.
- Root cause: duplicate identity records were discarded first-wins without a
  compatibility check.
- Fix: observations are aggregated by mock identity first; incompatible duplicate
  observations become conflicting evidence (`conflicting_identity_count`) that
  never participates in trend inference. `test_order_invariance` was strengthened
  to compare normalized semantic meaning.
- Verification: RED observed (trend inferred and order-dependent); GREEN after
  fix (no trend; identical normalized result across permutations).

## I7 — Conflicting duplicate alternative-route IDs are first-wins and input-order dependent

Status: FIXED IN REMEDIATION V1

- Test added: `test_conflicting_duplicate_route_order_invariance` in
  `tests/domains/test_oppositions_domain_alternative_routes.py`.
- Root cause: duplicate route ids were skipped first-wins; the recommendation
  depended on which duplicate appeared first.
- Fix: routes are grouped by route id; incompatible duplicate observations become
  conflicting/unresolved routes (`conflicting_route_ids`) that can never be
  automatically recommended. `test_order_invariance` was strengthened to compare
  recommendations and trade-offs.
- Verification: RED observed (recommendation `alt1` vs `alt2` depending on
  order); GREEN after fix (conflict blocked, recommendation order-invariant).

## Adversarial self-audit (post-remediation probes)

```text
I1 Health cap cannot widen capacity                 PASS
I2 target-date feasibility actually gates           PASS
I3 syllabus duplicate conflict preserved            PASS
I4 conflicting/superseded temporal states preserved PASS
I5 mock denominator/chronology safe                 PASS
I6 duplicate mock order-invariant                   PASS
I7 duplicate alternative order-invariant            PASS
```

Phase 10.23 state after Remediation V1:

```text
Implemented, pending Independent Audit V2
```

Independent re-audit (V2) is a later workflow and is **not** claimed here.
