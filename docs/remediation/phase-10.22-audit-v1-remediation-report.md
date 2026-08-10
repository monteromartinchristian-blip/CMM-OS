# Phase 10.22 — University Domain: Audit V1 Remediation Report

**Branch:** `feature/phase-10-domain-intelligence`
**HEAD:** `410bb1c` (unchanged)
**Date:** 2026-08-10
**Method:** TDD (RED → GREEN → REFACTOR) for every remediation item. No re-implementation of already-good areas.

---

## 1. Findings Status

| Finding | Area | Status | Evidence |
|---|---|---|---|
| **B1** | Source authority | **FIXED** | `tests/domains/test_university_domain_source_authority.py` |
| **B2** | Contradiction | **FIXED** | `tests/domains/test_university_domain_contradiction.py` |
| **B3** | Deadlines | **FIXED** | `tests/domains/test_university_domain_deadlines.py` |
| **B4** | ECTS | **FIXED** | `tests/domains/test_university_domain_ects.py` |
| **B5** | Exam attempts | **FIXED** | `tests/domains/test_university_domain_exam_attempts.py` |
| **B6** | Workload | **FIXED** | `tests/domains/test_university_domain_workload.py`, `test_university_domain_health_projection.py` |
| **B6** | Dependencies | **FIXED** | `tests/domains/test_university_domain_dependencies.py` |
| **B7** | Academic integrity (Mode C) | **FIXED** | `tests/domains/test_university_domain_integrity.py` |
| **M1** | `update_subject_status` in reassessment workflow | **FIXED** | `tests/domains/test_university_domain_workflows.py` |
| **M2** | `academic_state` gloss | **FIXED** | `tests/domains/test_university_domain_rules.py` + `profile.py:167` |
| **M3** | Conditional verification trigger | **FIXED** | `tests/domains/test_university_domain_verification.py` |
| **M4** | Permission positive-path lifecycle | **FIXED** | `tests/domains/test_university_domain_permission_lifecycle.py` |
| **N1** | DP-022 reconcile with REQ-DP22-001/002/003 | **FIXED** | `docs/reference/domain-intelligence-requirements-matrix.md` |

**Result: 13/13 FIXED.** No NOT FIXED findings.

---

## 2. Rule semantics summary (per remediated area)

### B1 — Source authority
- Authority resolution is **attribute-specific** (per field, not per-document).
- **Recency never wins** a direct authority conflict; it only breaks ties among equal authorities.
- The internal `source_class` is the source of truth; the caller **cannot fabricate "official"** without a matching official source class.
- **Supersession preserves history** — the superseded record persists, it is not overwritten.
- **Equal-authority conflict → UNRESOLVED** (fails closed), never silently resolved by the caller.

### B2 — Contradiction
- Contradiction is **derived from concrete claims** (real attribute/value/source_class), never from caller booleans.
- Only **dependent conclusions** block on a contradiction; unrelated facts of the same quality are not blocked.
- Decision-critical equal-authority conflict → **BLOCKED** with no unknown reference emitted.

### B3 — Deadlines
- Deadline handling uses real semantics (day-level precision, grounding required).
- Official-source confirmation gates trust; verification is flagged when grounding is missing.
- Added `_DEADLINE_OFFICIAL_SOURCE_CLASSES` frozenset to centralize which source classes confirm a deadline.

### B4 — ECTS
- Buckets are used (no double-counting); **no silent summation** across incompatible metrics.
- Completion is **blocked when a critical ECTS figure is uncertain** (§31).

### B5 — Exam attempts
- **Ordinary ≠ reassessment** attempt; **failed ≠ consumed** attempt — distinct states preserved.
- Attempts must be **grounded** before they constrain.
- Regulation applicability is **temporality-aware** (current vs. non-current regulation).

### B6 — Workload
- Staged pipeline: **HARD → FEASIBILITY → PREFERENCES → TRADEOFFS → SCENARIOS → PROPOSAL**.
- An **authorized Health functional cap** affects feasibility (constraint projection), but **clinical detail is never consumed**.
- The workload helper emits a scalar planning signal; `adopted_decision` stays `False` (no hidden adoption).

### B6 — Dependencies
- Dependencies are **grounded**; the caller's `passed` flag is **not authoritative**.
- TFG sequencing is handled; **unknown status → unresolved** (fails closed).

### B7 — Academic integrity — Mode C
- **Permissive by default** in Mode C.
- `ai_forbidden` set by the caller **without grounding cannot fabricate a prohibition**.
- A grounded restriction (status `prohibited` + grounded + `official_regulation` source + temporal `current`) applies with **exact scope**.

### M3 — Conditional verification trigger (by design, NOT an 11th rule / 12th op)
- Implemented as a **deterministic helper** returning a structured result, not a rule or operation.
- Verification is always **READ-ONLY** and **OFFICIAL_ONLY**; the helper **never authorizes an action**, never performs I/O.
- Triggers when an academic fact is **missing, stale, conflicting, or decision-critical and insufficiently grounded** (spec §32).

### N1 — DP-022 reconcile
- DP-022 now references `REQ-DP22-001`, `REQ-DP22-002`, `REQ-DP22-003` as **sub-requirements of one canonical unit** — no invented canonical IDs.
- Status corrected to `REQUIRES_PHASE_INSPECTION` (pre-audit correct state), **not** set to "Complete and audited".

---

## 3. Verification results

| Check | Result |
|---|---|
| Full test suite | **9354 passed**, 28.06s, no regressions |
| Remediated-area tests | **58 passed** in 0.83s |
| Canonical counts | **14 entities / 12 resources / 10 rules / 11 operations / 7 workflows** intact |
| ruff (default + py310) | Clean |
| mypy | New helpers clean (no new errors; 575 pre-existing project-wide errors unchanged — not regressions) |
| bandit | No issues |
| compileall | OK |
| Stub/placeholder scan | Clean |
| Dependency direction | Clean — no health/parallel-store imports; University composes with General only for fallback |
| Roadmap status | Unchanged — **"Implemented, pending audit (2026-08-09)"** (NOT "Complete and audited") |

---

## 4. Git status (left unstaged for human review — NO COMMIT)

**Branch:** `feature/phase-10-domain-intelligence` · **HEAD:** `410bb1c`

**Modified (8):**
```
M cmm/domains/university/profile.py
M cmm/domains/university/rules.py
M cmm/domains/university/workflows.py
M docs/reference/domain-intelligence-requirements-matrix.md
M tests/domains/test_university_domain_health_projection.py
M tests/domains/test_university_domain_remediation.py
M tests/domains/test_university_domain_rules.py
M tests/domains/test_university_domain_workflows.py
```

**New test files (10):**
```
?? tests/domains/test_university_domain_source_authority.py
?? tests/domains/test_university_domain_contradiction.py
?? tests/domains/test_university_domain_deadlines.py
?? tests/domains/test_university_domain_ects.py
?? tests/domains/test_university_domain_exam_attempts.py
?? tests/domains/test_university_domain_workload.py
?? tests/domains/test_university_domain_dependencies.py
?? tests/domains/test_university_domain_integrity.py
?? tests/domains/test_university_domain_verification.py
?? tests/domains/test_university_domain_permission_lifecycle.py
```

**Untracked artifact (pre-existing, NOT created by this remediation):**
```
?? phase-10.22-audit-v1.tar.gz
```

Per the explicit git constraint, **no `git add` / `git commit` / `git push` was performed.** All changes remain unstaged for human review.

---

## 5. Closure recommendation

**RECOMMEND FIXED → CLOSE.** All 13 audit findings (B1–B7, M1–M4, N1) are remediated via TDD and verified. The full suite passes (9354), canonical counts are intact, quality gates are clean, and the roadmap status correctly remains **"Implemented, pending audit"** — it has NOT been advanced to "Complete and audited."

The changes are staged for human review only (unstaged on disk). Recommend the human reviewer:
1. Review the unstaged diff (8 modified + 10 new test files).
2. Confirm the roadmap status is left as "Implemented, pending audit" until the Phase 10.22 closure review.
3. Commit when satisfied — the engineer intentionally did not commit per the task constraint.