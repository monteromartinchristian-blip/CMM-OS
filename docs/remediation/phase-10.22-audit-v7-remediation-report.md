# Phase 10.22 University Domain — Audit V7 Remediation

Date: 2026-08-10

This remediation is limited to the four Independent Audit V7 blockers plus the
single non-blocking auditability observation. The roadmap remains
**Implemented, pending audit**; Independent Audit V8 decides closure. Phase
10.22 is **not** declared complete by this patch.

## V7-B1 — Decision-critical deadline context propagates when a deadline payload exists — FIXED

- Cause: when a deadline payload was present, criticality was derived only from
  `bool(deadline.get("critical"))`; the context-level
  `context.metadata.deadline_decision_critical` (and the already-canonical
  `deadline_required` signal) were ignored, so a decision-critical
  under-grounded deadline payload produced no verification need.
- Production change: `AcademicDeadlineRule.evaluate()` now computes a single
  effective criticality once,
  `context_critical or bool(deadline.get("critical"))`, and passes that same
  value into both `classify_deadline_grounding(...)` and
  `conditional_verification_trigger(...)`. No second verification path was
  created.
- Canonical rule path: `AcademicDeadlineRule.evaluate()` through
  `university.academic_deadline` in `build_university_rules()`.
- Adversarial tests: context-level decision-critical remembered, reported, and
  inferred deadlines all require verification; a payload-level `critical` alone
  still verifies an under-grounded deadline; a non-critical remembered deadline
  stays non-confirmed without inventing criticality; a confirmed referenced
  official critical deadline stays confirmed without a fabricated verification
  need.
- Behavior proven: criticality no longer disappears merely because a
  non-confirmed deadline value is present.

## V7-B2 — Scoped integrity restriction fails closed when current scope is unknown — FIXED

- Cause: scope matching treated a missing current course/assessment as
  compatible (`current_course is None ... or course_scope == current_course`),
  so a course/assessment-specific restriction could prohibit assistance even
  when the exact scope could not be established.
- Production change: `evaluate_academic_integrity()` now requires the current
  scope to be present *and* equal before a scoped restriction applies. A
  restriction carrying a concrete course/assessment scope with a missing
  current scope yields `restriction_applies=False` and assistance remains
  permitted under Mode C. A `scope_applicability` diagnostic distinguishes
  `matched` / `unresolved` / `mismatched`. The grounded restriction is
  preserved diagnostically — `restriction_grounded` remains distinct from
  `restriction_applies`.
- Canonical rule path: `AcademicIntegrityRule.evaluate()` through
  `university.academic_integrity` in `build_university_rules()`.
- Adversarial tests: course-scoped and assessment-scoped restrictions with a
  missing current course/assessment cannot prohibit; matching course/assessment
  still prohibits the exact requested action; a mismatched scope remains
  non-applicable; an unscoped general restriction may still apply without a
  current course.
- Behavior proven: unknown applicability is no longer treated as proven
  applicability under the permissive-by-default Mode C.

## V7-B3 — Dependency credit thresholds deduplicate and contradiction-check by identity — FIXED

- Cause: the strict dependency path summed every qualifying academic record by
  amount without deduplicating by canonical credit identity or detecting
  contradictory same-identity states, allowing a duplicate 90-credit identity
  (or a completed+failed 180-credit identity) to satisfy a 180 threshold.
- Production change: `_resolve_dependency_credit_evidence(...)` now groups
  current grounded referenced credit evidence by canonical identity
  (`subject_id` / `credit_id` / `id`). Compatible duplicate evidence counts the
  identity once; contradictory same-identity states (completed + failed) and
  conflicting same-identity credit amounts make the credit evidence unknown and
  do not establish a definitive threshold; identityless records cannot
  establish a threshold. Pending-recognition semantics are preserved. The rule
  surfaces `credit_evidence_unknown`, `unknown_credit_identities`,
  `contradictory_credit_identities`, and `amount_conflict_credit_identities`
  as sorted diagnostics.
- Canonical rule path: `AcademicDependencyRule.evaluate()` through
  `university.academic_dependency` in `build_university_rules()`.
- Adversarial tests: duplicate identical 90-credit records count once and
  cannot satisfy 180; same-identity completed + failed leaves the threshold
  unknown/blocked; same-identity conflicting credit amounts fail closed; two
  genuinely distinct 90-credit identities may satisfy 180; the valid
  six × 30-credit positive regression remains green; identityless 180-credit
  records still cannot satisfy.
- Behavior proven: a TFG/credit prerequisite no longer bypasses the ECTS
  no-double-count and no-silent-contradiction semantics.

## V7-B4 — Collection-shaped canonical metadata normalizes safely (no TypeError leak) — FIXED

- Cause: canonical wrappers used direct tuple coercion
  (`tuple(ects.get("records", ()) or ())`, etc.), which raised `TypeError` for
  scalar or `None` collection-shaped metadata.
- Production change: the existing `_seq(...)` safe-sequence helper is now
  applied consistently at every collection-shaped read site —
  `EctsConsistencyRule` (`records`, `double_counted`, `contradictory`),
  `ExamAttemptRule` (`attempts`), `AcademicWorkloadRule` (`hard_constraints`,
  `preferences`, `scenarios`), and `AcademicDependencyRule` (`prerequisites`,
  `academic_records`). Malformed/non-collection values normalize to an empty
  tuple and the rule degrades to a structured conservative result; scalars are
  never silently converted into one-element evidence lists.
- Canonical rule path: all four wrapper `.evaluate()` methods through their
  rules in `build_university_rules()`.
- Adversarial tests: scalar `records`/`double_counted`/`contradictory` (ECTS),
  scalar `attempts` (ExamAttempt), scalar `hard_constraints`/`preferences`/
  `scenarios` (Workload), and scalar `prerequisites`/`academic_records`
  (Dependency) produce no `TypeError` and a structured conservative result,
  while valid list/tuple positive paths are preserved.
- Behavior proven: malformed collection-shaped runtime metadata fails closed
  with no accidental runtime exception.

## Optional auditability cleanup — restriction source + temporal evidence preserved in Deadline/Integrity findings — DONE

- Cause: confirmed deadlines and applied integrity restrictions omitted the
  actual source reference and temporal/source-class evidence from finding
  metadata/references, so downstream auditability was incomplete.
- Production change: the deadline finding now carries `source_class`, `temporal`,
  `provenance`, the usable `source_reference` (also attached to `references`),
  and the effective `critical`. The integrity finding now carries the grounded
  restriction's `source_class`, `temporal`, `provenance`, and
  `source_reference` (also attached to `references`).
- Canonical rule path: `AcademicDeadlineRule.evaluate()` and
  `AcademicIntegrityRule.evaluate()` through their rules in
  `build_university_rules()`.
- Test: an applied integrity restriction preserves `official_regulation` /
  `current` / `integrity-regulation-1` in the finding metadata and references.

## Verification evidence

- Focal remediation tests (six files): `147 passed`.
- University suite (`test_university_domain_*.py`): `420 passed`.
- Domains suite (`tests/domains/`): `3,978 passed`.
- Global suite (`tests/`): `9,489 passed`.
- Ruff (default target) on `cmm/domains/university/rules.py`: clean.
- `compileall` on `cmm/domains/university/rules.py`: pass.
- Canonical counts unchanged: entities 14 / resources 12 / rules 10 /
  operations 11 / workflows 7.
- No new rules, operations, or workflows were added; no other domain and no
  permission file was modified.

No files were staged. No commit was created. No push was performed.

Final recommendation: **READY FOR INDEPENDENT AUDIT V8**.