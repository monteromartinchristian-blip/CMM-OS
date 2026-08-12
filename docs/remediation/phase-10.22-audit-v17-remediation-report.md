# Phase 10.22 University Domain — Audit V17 Remediation Report

**Branch:** `feature/phase-10-domain-intelligence`
**Starting HEAD:** `5f9c9ea fix(domains): close phase 10.22 audit v16 findings`
**Status:** `Implemented, pending audit`
**Closure authority:** Independent Audit V18

This remediation does not declare Phase 10.22 complete. It closes the V17
findings and performs the requested class-driven semantic-boundary sweep of
`cmm/domains/university/rules.py`.

## Preflight and baseline

- Branch and HEAD matched the required values.
- No tracked or staged changes existed at preflight.
- The only pre-existing untracked files were the permitted
  `phase-10.22-audit-v*.tar.gz` artifacts.
- `git diff --check`: clean.
- `git diff --cached --check`: clean.
- University baseline: `851 passed in 2.04s`.
- Domains baseline: `4409 passed in 7.02s`.
- Global baseline: `9920 passed in 31.44s`.

## A. V17-B1 — ECTS conflict collection members

### Root cause

At the pre-remediation `check_ects_consistency()` boundary, the outer
`double_counted` and `contradictory` containers were normalized, but their
members were not validated as usable scalar strings before
`dict.fromkeys(...)`. Nested lists therefore raised `TypeError`, while hashable
non-string members such as `7` could be exposed as semantic conflict IDs.

### RED

`tests/domains/test_university_domain_ects.py:779` and `:795` cover direct and
canonical list, tuple, Mapping, numeric, boolean, null and blank members. The
initial closure selector reproduced both unhashable exceptions and the
hashable-invalid-member acceptance.

### Fix

`rules.py:1726-1743` now separates outer-container normalization from strict
member normalization through `rules.py:185-209`. Member validation occurs
before deduplication. Malformed members are removed from the semantic ID tuple,
set the corresponding malformed flag, and block completion.

### GREEN

- Direct and canonical malformed-member cases pass.
- Flat string conflicts remain valid (`tests/.../test_university_domain_ects.py:814`).
- No malformed member reaches hash/set/deduplication unsafely.

## B. V17-B2 — legacy/public Workload identities

### Root cause

The legacy Workload path selected all Mapping preferences, generated scenario
IDs with `f"scenario-{pref.get('id')}"`, and returned `selected_scenario`
without scalar validation. Mapping shape was therefore mistaken for semantic
preference identity. The same branch also ignored malformed constraint IDs,
and the structured constraint helper used caller-controlled string coercion
and truthy alias fallback.

### RED

`tests/domains/test_university_domain_workload.py:858-993` covers:

- missing, null, blank, collection, Mapping, numeric and boolean preference IDs;
- malformed direct and canonical selected scenarios;
- malformed constraint IDs;
- a string-like constraint kind;
- present-malformed `field` with a valid lower-priority alias;
- `workload={}`;
- positive scalar preference and selected-scenario controls.

### Fix

- `rules.py:2520-2523` validates selection identity once.
- `rules.py:2540-2564` validates legacy constraint and preference Mapping
  completeness.
- `rules.py:2142-2206` removes kind coercion and truthy field-alias fallback.
- `rules.py:2208-2218` validates structured constraint identity/kind/carriers.
- `rules.py:2729-2736` builds generated scenario IDs only from already validated
  scalar preference IDs.
- `rules.py:4790-4818` classifies semantically empty Workload mappings as
  uncertainty rather than confident infeasibility.
- `rules.py:4828-4844` preserves canonical selected-scenario malformed state.

### GREEN

- Malformed IDs never appear as scenarios or proposals.
- Malformed selection never becomes a proposal.
- Strict integer rank parsing remains in `rules.py:1668-1677` and rejects bool
  and numeric-looking strings.
- Valid scalar IDs, scalar selections and valid empty hard-constraint
  collections retain their prior behavior.

## C. V17-B3 — Dependency target identity

### Root cause

`AcademicDependencyRule` used
`str(dependency.get("subject_id", "unknown"))`. An empty or malformed dependency
Mapping therefore fabricated a target identity and could reach
`DEPENDENCY_SATISFIED` when no prerequisites were present. The direct helper
also accepted the malformed target without validation.

### RED

`tests/domains/test_university_domain_dependencies.py:833-881` covers direct
and canonical missing, null, blank, collection, Mapping, numeric and boolean
target identities, `dependency={}`, and the positive valid-subject/no-prereq
case.

### Fix

- `rules.py:2909-2910` normalizes the target with the strict scalar validator.
- `rules.py:3064-3117` carries `target_identity_malformed` and includes it in
  dependency blocking.
- `rules.py:4998-5008` passes validated identity into the helper and no longer
  creates `"unknown"` or string representations.

### GREEN

- `dependency={}` produces `DEPENDENCY_BLOCKED` with `subject_id=None`.
- A valid scalar subject with an explicitly empty prerequisite collection
  remains `DEPENDENCY_SATISFIED`.

## Semantic closure sweep

### 1. Public API inventory

The exported/dynamic helper surface reviewed was:

| Location | Boundary | Classification |
|---|---|---|
| `rules.py:1165` | `resolve_source_authority_by_attribute` | public adapter |
| `rules.py:1231` | `evaluate_academic_contradiction` | public adapter |
| `rules.py:1689` | `check_ects_consistency` | public helper |
| `rules.py:1957` | `evaluate_exam_attempt` | public helper |
| `rules.py:2469` | `evaluate_academic_workload` | public helper |
| `rules.py:2891` | `evaluate_academic_dependency` | public helper |
| `rules.py:3121` | `evaluate_academic_integrity` | public helper |
| `rules.py:3367` | `conditional_verification_trigger` | public helper |
| `rules.py:3436` | `evaluate_performance_capacity` | public helper |
| `rules.py:3485` | `evaluate_deadline` | public adapter |
| `rules.py:783`, `:1463`, `:3556` | authority, conflict and deadline classifiers | public deterministic boundaries |
| `rules.py:3833-5404` | ten canonical rule classes | canonical wrappers |

All ten canonical classes and all callable boundaries in `__all__` were
reviewed. `build_university_rules()` remains deterministic and count-preserving.

### 2. `str()` / f-string coercion inventory

| Location | Field/site | Classification | Result and reason |
|---|---|---|---|
| `rules.py:1200` | legacy `source_type` | fixed caller coercion | strict scalar; a string-like object cannot fabricate authority |
| `rules.py:1395` | claim attribute | safe guarded conversion | executes only after `isinstance(value, str)` |
| `rules.py:1625-1628` | conflict sort keys | safe internal diagnostic ordering | IDs are already normalized to string-or-None; no semantic identity is created |
| `rules.py:1770`, `:1797` | ECTS state/recognition | fixed caller coercion | strict scalar enum values |
| `rules.py:2172` | workload constraint kind | fixed caller coercion | strict scalar before `.lower()` |
| `rules.py:2719`, `:2735` | tradeoff/scenario f-strings | safe derived | operands are parsed integers or validated scalar IDs |
| `rules.py:2832`, `:2972`, `:3025` | dependency record state/kind/status | fixed caller coercion | strict scalar enums |
| `rules.py:3140`, `:3207-3210` | integrity mode/source/temporal | fixed caller coercion | strict scalar values; wrapper cannot re-coerce |
| `rules.py:3175`, `:3187` | integrity reason strings | safe diagnostic | mode has already passed scalar normalization |
| `rules.py:3414-3419` | verification fact state | fixed caller coercion | non-string becomes unknown/missing verification posture |
| `rules.py:3593-3595` | deadline provenance state | fixed caller value | non-string maps to `none`; no unhashable membership |
| `rules.py:3686` and canonical messages | rule/message f-strings | safe internal | operands are definitions or normalized result data, not identity construction |

**ALL CALLER-CONTROLLED str/f-string coercions reviewed: YES.**
**No caller-controlled semantic ID is produced via `str(...)`: YES.**
**No caller-controlled semantic ID is produced via f-string repr: YES.**

### 3. bool / truthiness inventory

| Location | Field/site | Classification | Reason |
|---|---|---|---|
| `rules.py:456-489` | trust and caller booleans | strict caller boolean | only literal `True` grants trust/state |
| `rules.py:605`, `:652`, `:754` | stripped strings / normalized authority / supersession | derived internal | operands are type-guarded or normalized |
| `rules.py:1622`, `:1646` | conflict presence/blocking | derived internal | tuple/list and derived flags only |
| `rules.py:1894`, `:1910`, `:2007` | ECTS/regulation decisions | derived internal | parsed numerics and normalized evidence |
| `rules.py:2104`, `:2259`, `:2408`, `:2443`, `:2453` | count/list feasibility flags | derived internal | normalized collections/IDs only |
| `rules.py:2818`, `:3017` | source-reference presence | derived internal | `_scalar_reference_from` result; no caller truthiness grants authority |
| `rules.py:3065`, `:3111` | dependency blocked | derived internal | normalized block lists and malformed flags |
| `rules.py:3246`, `:3331` | integrity policy/remembered diagnostics | derived internal plus `_boolean_true` | malformed booleans never apply a restriction |
| canonical wrappers | `critical`, `required`, `remembered`, `grounded` | strict caller boolean | `_boolean_true` / `_grants_trust` only |

**No caller-controlled boolean-bearing field uses Python truthiness: YES.**

### 4. Numeric-boundary inventory

| Location | Boundary | Classification |
|---|---|---|
| `rules.py:1668-1677` | ECTS integers, attempts, rank, thresholds | strict native int; bool/string/float rejected |
| `rules.py:1680-1686` | workload numeric values | strict finite non-negative int/float; bool/string/NaN/inf rejected |
| `rules.py:1878-1923` | ECTS totals/output conversion | safe internal after parsing |
| `rules.py:1994-2025` | exam maximum attempts | strict parser |
| `rules.py:2182-2205` | constraint minimum/maximum/limit | strict finite numeric parser |
| `rules.py:2288-2395` | scenario ranking values | strict finite numeric parser; incomplete ranking on malformed values |
| `rules.py:2695-2719` | legacy preference rank/tradeoff | strict integer parser; bool and numeric strings rejected |
| `rules.py:2830-2870`, `:2975-3008` | dependency credits/thresholds | strict integer parser and deduplicated identities |
| canonical ECTS/Workload/Exam wrappers | aggregates/defaults | strict parse before helper; malformed state explicitly carried |

**No bool-as-int numeric acceptance remains on audited boundaries: YES.**
**No numeric-looking strings are silently treated as numeric where prohibited: YES.**
**ALL CALLER-CONTROLLED NUMERIC BOUNDARIES REVIEWED: YES.**

### 5. Mapping semantic-validity inventory

| Boundary | Minimum semantic content | Empty/opaque behavior |
|---|---|---|
| source authority source/claim | usable carrier plus value or coherent grounded authority identity; usable source ID for facts | unknown/malformed; never authority |
| contradiction claim | usable attribute, usable ID and present value | unresolved |
| ECTS record | usable identity, strict ECTS amount/state, literal grounding, scalar reference, current temporal | unknown record; completion blocked |
| degree requirement | strict positive requirement, literal grounding, scalar source, current temporal | requirement unknown; completion blocked |
| exam attempt | scalar id/exam/date/source/kind/status plus literal grounding | attempt evidence unknown |
| exam regulation | recognized class, literal grounding, scalar reference, current temporal, strict limit | regulation/limit unknown |
| workload preference (legacy) | usable preference ID and strict rank/default | malformed uncertainty |
| workload preference (structured) | usable dimension; optional ID must be scalar | malformed uncertainty |
| workload hard constraint | usable ID plus branch-specific semantic fields | malformed/unresolved, never confident feasible/infeasible |
| workload scenario | usable scenario ID | malformed scenario set |
| dependency | usable target subject ID | blocked |
| prerequisite | usable prerequisite ID plus interpretable kind/status | anonymous/unknown prerequisite; blocked |
| academic record | usable identity, source, current state and strict credit amount where used | unknown evidence; cannot satisfy |
| integrity restriction | prohibited status, literal grounding, scalar source, recognized class/temporal, valid policy collections and matching scope | cannot apply restriction |
| deadline | usable scalar value; confirmation additionally requires class/provenance/temporal/reference | unknown and verification needed |
| performance | usable scalar `ref` and `outcome` | not observed; capacity never inferred |
| decision support | Mapping presence only; rule is non-adoption invariant | no decision adopted |

**All Mapping boundaries reviewed for semantic completeness: YES.**

### 6. Empty-Mapping audit

| Canonical metadata | Classification | Observed result |
|---|---|---|
| `dependency={}` | UNKNOWN/BLOCKED | `DEPENDENCY_BLOCKED`, no target identity |
| `workload={}` | UNKNOWN | `WORKLOAD_FEASIBILITY_UNCERTAIN`, no proposal |
| `ects={}` | UNKNOWN/BLOCKED | `ECTS_COMPLETION_BLOCKED`; requirement and grounded records missing |
| `exam_attempt={}` | UNKNOWN | regulation verification required |
| `integrity={}` | VALID EMPTY SEMANTICS | Mode C permissive-by-default; no restriction fabricated |
| `deadline={}` | UNKNOWN | verification needed; never confirmed |
| `performance_observation={}` | UNKNOWN | performance not observed; capacity not inferred |
| `decision_support={}` | VALID EMPTY SAFETY SEMANTICS | decision remains unadopted and requires confirmation |
| source-authority/contradiction member `{}` | MALFORMED MEMBER | authority/conflict remains unknown/unresolved |

**All empty Mapping canonical boundaries reviewed: YES.**

### 7. Collection member-validation inventory

| Location | Collection | Validation/deduplication result |
|---|---|---|
| `rules.py:185-227` | references, supersession, integrity policy | flat usable scalar strings only; key-presence-aware null handling |
| `rules.py:1726-1743` | ECTS conflict IDs | members validated before `dict.fromkeys` |
| `rules.py:1707-1850` | ECTS records | Mapping container/member plus semantic record validation |
| `rules.py:1987-2088` | attempts | Mapping members and strict scalar fields; no unhashable set membership |
| `rules.py:2220-2465` | workload constraints/preferences/scenarios | structural and semantic member flags preserved |
| `rules.py:2779-3117` | dependency records/prerequisites | identity, grounding, numeric and status validation before grouping/dedupe |
| `rules.py:3755-3822` | generic collection normalization | absent, valid empty, malformed container and malformed member remain distinct |

**ALL CALLER-CONTROLLED COLLECTION MEMBERS REVIEWED: YES.**
**No malformed collection member can reach hash/set/dedupe unsafely: YES.**

### 8. Key-presence audit

| Location | Site | Result |
|---|---|---|
| `rules.py:159-174` | ordered scalar reference aliases | first present malformed alias fails closed; it cannot fall through |
| `rules.py:212-227` | plural relation/policy fields | missing is clean absence; present `None` is malformed |
| `rules.py:709-716`, `:1339-1346` | source/claim scope | missing remains unscoped; present null/blank/non-string is malformed |
| `rules.py:2148-2161` | workload `field` / `scenario_field` | first present malformed carrier returns unknown; no truthy fallback |
| `rules.py:2520-2523`, `:4828-4844` | selected scenario | wrapper distinguishes absent from present invalid/null |
| `rules.py:3225-3236` | integrity policy collections | missing remains optional; present null is malformed |
| `rules.py:3264-3271` | integrity exact course/assessment | established contract retained: `None` means genuinely global/unscoped; malformed non-null values fail closed |
| canonical mapping/collection normalizers | top-level keys | absent, present malformed and present Mapping/collection are distinct |

**Absent != malformed preserved where contract requires it: YES.**
**Explicit None != absent preserved where contract requires it: YES.**
**ALL KEY-PRESENCE-SENSITIVE SITES REVIEWED: YES.**

### 9. Canonical-wrapper re-coercion audit

| Wrapper | Result |
|---|---|
| Source authority | claim IDs/references and legacy source type remain strict; malformed relations remain unresolved |
| Contradiction | references and conflict IDs use strict scalar identities; rejected IDs are not re-exposed |
| Deadline | strict scalar references and provenance; malformed payload remains verification-needed |
| ECTS | conflict-member malformed flags survive wrapper delegation |
| Exam | malformed kind/status becomes unknown, never an exception or clean limit result |
| Workload | selection presence/malformed state and all collection flags survive delegation |
| Dependency | target passes through `_usable_scalar_string`; no `str(...)` fallback |
| Performance | scalar ref/outcome only |
| Integrity | raw mode/source/temporal is never passed through `str(...)`; policy malformed flags survive |
| Decision preservation | malformed Mapping cannot adopt a decision |

**Canonical wrappers cannot re-coerce rejected helper input: YES.**

### 10. Public exception-safety audit

The post-fix field-mutation matrix exercised Mapping members across ECTS,
degree requirements, attempts, regulations, legacy/structured workload,
dependencies, academic records, integrity restrictions, deadlines, authority
sources and contradiction claims with:

`None`, `[]`, `()`, `{}`, nested list, nested tuple, `7`, `True`, and blank
string.

Result: `public_exception_count=0`.

- No public malformed payload leaks `KeyError`: YES.
- No public malformed payload leaks `AttributeError`: YES.
- No public malformed payload leaks `TypeError`: YES.
- No public malformed payload leaks `ValueError`: YES.

## Additional closure findings fixed

1. Legacy `source_type` string coercion could fabricate official authority.
2. ECTS and Dependency state fields accepted arbitrary string-like objects.
3. Exam kind/status with unhashable values leaked `TypeError`.
4. Deadline provenance with unhashable values leaked `TypeError`.
5. Integrity mode/source/temporal wrappers could re-coerce rejected values.
6. Verification fact state could be fabricated through `str()`.
7. Present-null source/claim scope and supersession were collapsed into absence.
8. Numeric-valued contradiction claims with malformed IDs could resolve and
   expose invalid conflict IDs.
9. Workload constraint kind/carrier and mapping completeness could create a
   confident feasibility posture from malformed evidence.

Every item above received a RED regression before production was modified and
is included in the `v18_closure` gate.

## Adversarial and positive gates

- Initial complete RED selector: `113 failed, 6 passed, 851 deselected`.
- Final selector after removing two invalid over-hardening expectations:
  `117 passed, 851 deselected in 1.00s`.
- Nine full focal owners: `718 passed in 1.41s`.
- Positive controls preserved:
  - flat ECTS conflict IDs;
  - scalar Workload preference IDs and selected scenario;
  - valid subject with empty prerequisites;
  - V16 nested members and literal `True` behavior;
  - V15 scalar IDs/references;
  - valid empty collections;
  - unrelated evidence remains non-poisoning;
  - global Integrity scope expressed by null exact scopes.

## Regression self-audit V9–V17

| Regression family | Result |
|---|---|
| V17-B1 ECTS collection members | fixed: YES |
| V17-B2 Workload legacy IDs/proposal | fixed: YES |
| V17-B3 Dependency target identity | fixed: YES |
| V16 nested-member family | remains closed: YES |
| V16 strict ECTS boolean | remains closed: YES |
| V15 singular scalar/reference | remains closed: YES |
| V15 relation-unknown | remains closed: YES |
| V14 | remains closed: YES |
| V13 | remains closed: YES |
| V12 | remains closed: YES |
| V11 | remains closed: YES |
| V10 | remains closed: YES |
| V9 | remains closed: YES |

Evidence is the final University run (`968 passed`) plus the focal and closure
selectors above.

## Final verification

All commands were run after the last production-code change.

| Gate | Result |
|---|---|
| University | `968 passed in 2.34s` |
| Domains | `4526 passed in 6.97s` |
| Global | `10037 passed in 31.92s` |
| Ruff default | all checks passed |
| Ruff `--target-version py310` | all checks passed |
| `compileall -q cmm tests` | passed |
| dependency direction | `1 passed in 0.52s` |
| fresh University import | `fresh_import=OK` |
| placeholder scan | no findings |
| `git diff --check` | clean after EOF-format correction |
| `git diff --cached --check` | clean |

## Architecture and scope

- Canonical counts: `14 / 12 / 10 / 11 / 7`: YES.
- Permission architecture untouched: YES.
- `catalog.py`, `operations.py`, and `workflows.py` untouched: YES.
- No parallel University engine/store/resolver/runtime introduced: YES.
- No direct Health-domain import introduced: YES.
- Roadmap remains `Implemented, pending audit`: YES.
- Tarballs untouched: YES.
- Graphify not run: YES.

## Final assertions

| Assertion | Result |
|---|---|
| V17-B1 ECTS collection members strict | YES |
| V17-B2 legacy Workload IDs strict | YES |
| V17-B2 malformed selected scenario cannot become proposal | YES |
| V17-B3 Dependency target identity strict | YES |
| `dependency={}` cannot mean satisfied | YES |
| No caller-controlled semantic ID via `str(...)` | YES |
| No caller-controlled semantic ID via f-string repr | YES |
| No caller-controlled boolean-bearing field uses truthiness | YES |
| No bool-as-int numeric acceptance remains | YES |
| No prohibited numeric-string coercion remains | YES |
| All Mapping boundaries reviewed for semantic completeness | YES |
| All empty Mapping canonical boundaries reviewed | YES |
| All collection boundaries reviewed for member validity | YES |
| No malformed member reaches unsafe hash/set/dedupe | YES |
| Absent vs malformed preserved where required | YES |
| Explicit None vs absent preserved where required | YES |
| Canonical wrappers cannot re-coerce rejected input | YES |
| No public KeyError/AttributeError/TypeError/ValueError leak | YES |
| Malformed evidence never expands authority | YES |
| Malformed evidence never expands factual confidence | YES |
| Malformed evidence never expands completion | YES |
| Malformed evidence never expands feasibility | YES |
| Malformed evidence never expands restriction | YES |
| All risky semantic coercion sites reviewed | YES |
| All caller-controlled collection members reviewed | YES |
| All caller-controlled numeric boundaries reviewed | YES |
| All key-presence-sensitive sites reviewed | YES |
| V9–V17 regressions remain closed | YES |
| Canonical counts remain 14/12/10/11/7 | YES |
| Permission architecture untouched | YES |

## Git actions

- No files staged.
- No commit created.
- No push performed.
- Graphify not run.

## Recommendation

**READY FOR INDEPENDENT AUDIT V18**

Phase 10.22 remains **Implemented, pending audit**. Independent Audit V18
decides closure.
