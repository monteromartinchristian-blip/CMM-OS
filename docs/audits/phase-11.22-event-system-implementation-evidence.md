# Phase 11.22 — Event System — implementation evidence for independent audit

**Status:** `REMEDIATED_AFTER_REAUDIT_V10_PENDING_INDEPENDENT_REAUDIT`
**Phase:** 11.22 — Event System
**Requirement:** `F11-022 — Canonical Platform Event System`
**Design Point:** `DP-122`
**Acceptance:** `AT-DP-122` — `tests/events/test_phase11_22_dp122_acceptance.py`
**Reference document:** [`docs/reference/phase-11-event-system.md`](../reference/phase-11-event-system.md)
**Design specification:** `docs/superpowers/specs/2026-09-26-phase-11.22-event-system-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-26-phase-11.22-event-system-implementation-plan.md`
**Independent Audit V1:** `docs/audits/phase-11.22-event-system-independent-audit-v1.md` (immutable historical evidence)
**Independent Re-audit V2:** `docs/audits/phase-11.22-event-system-independent-reaudit-v2.md` (immutable historical evidence)
**Independent Re-audit V3:** `docs/audits/phase-11.22-event-system-independent-reaudit-v3.md` (immutable historical evidence)
**Independent Re-audit V4:** `docs/audits/phase-11.22-event-system-independent-reaudit-v4.md` (immutable historical evidence)
**Independent Re-audit V5:** `docs/audits/phase-11.22-event-system-independent-reaudit-v5.md` (immutable historical evidence)
**Independent Re-audit V6:** `docs/audits/phase-11.22-event-system-independent-reaudit-v6.md` (immutable historical evidence)
**Independent Re-audit V7:** `docs/audits/phase-11.22-event-system-independent-reaudit-v7.md` (immutable historical evidence)
**Independent Re-audit V8:** `docs/audits/phase-11.22-event-system-independent-reaudit-v8.md` (immutable historical evidence)
**Independent Re-audit V9:** `docs/audits/phase-11.22-event-system-independent-reaudit-v9.md` (immutable historical evidence)
**Independent Re-audit V10:** `docs/audits/phase-11.22-event-system-independent-reaudit-v10.md` (immutable historical evidence)
**Remediation V1 prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v1-agent-prompt.md`
**Remediation V2 prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v2-agent-prompt.md`
**Remediation V3 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v3-agent-prompt.md`
**Remediation V4 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v4-agent-prompt.md`
**Remediation V5 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v5-agent-prompt.md`
**Remediation V6 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v6-agent-prompt.md`
**Remediation V7 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v7-agent-prompt.md`
**Remediation V8 prompt:** `docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v8-agent-prompt.md`
**Remediation V9 prompt:** `docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v9-agent-prompt.md`
**Remediation V10 prompt:** `docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v10-agent-prompt.md`

```text
DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-122=PASS_REPORTED
INDEPENDENT_AUDIT_V1=FAIL
REMEDIATION_V1=REMEDIATED_AFTER_AUDIT_V1_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V2=FAIL
AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED
REMEDIATION_V2=REMEDIATED_AFTER_REAUDIT_V2_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V3=FAIL
REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_VERIFIED
REMEDIATION_V3=REMEDIATED_AFTER_REAUDIT_V3_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V4=FAIL
REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_VERIFIED
REMEDIATION_V4=REMEDIATED_AFTER_REAUDIT_V4_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V5=FAIL
V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=279_PASS
REMEDIATION_V5=REMEDIATED_AFTER_REAUDIT_V5_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V6=FAIL
V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=350_PASS
REMEDIATION_V6=REMEDIATED_AFTER_REAUDIT_V6_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V7=FAIL
V6_CONCRETE_FINDINGS_FIXED=4/4_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=477_PASS
REMEDIATION_V7=REMEDIATED_AFTER_REAUDIT_V7_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V8=FAIL
V7_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=604_PASS
REMEDIATION_V8=REMEDIATED_AFTER_REAUDIT_V8_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V9=FAIL
V8_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=604_PASS
MAJOR_V9_001=WRAPPED_NON_AUTHORITY_FILE_URI_BYPASSES_FAIL_CLOSED_FILESYSTEM_CLASSIFIER
MAJOR_V9_002=SUPPORTED_RUNTIME_TIMESTAMP_SEMANTICS_REOPEN_PRIOR_V6_FINDING_AND_KEEP_GLOBAL_GATE_RED
MINOR_V9_001=REFERENCE_TEST_EVIDENCE_COUNTS_STALE_AFTER_FINAL_V8_AT_ADDITIONS
MAJOR_V9_001_STATUS=REMEDIATED_REPORTED
MAJOR_V9_002_STATUS=REMEDIATED_REPORTED
MINOR_V9_001_STATUS=REMEDIATED_REPORTED
REMEDIATION_V9=REMEDIATED_AFTER_REAUDIT_V9_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V10=FAIL
V9_FINDINGS_FIXED=3/3_VERIFIED
MAJOR_V10_001=WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCE_BYPASSES_PUBLIC_ROOT_FILESYSTEM_CLASSIFIER
MAJOR_V10_001_STATUS=REMEDIATED_REPORTED
REMEDIATION_V10=REMEDIATED_AFTER_REAUDIT_V10_PENDING_INDEPENDENT_REAUDIT
```

Phase 11.22 was **implemented**, **failed independent Audit V1**
(`BLOCKERS=0`, `MAJORS=4`, `MINORS=5`), was **remediated**, **passed the nine
Audit V1 findings on independent Re-audit V2** (`9/9_VERIFIED`) while **failing
that re-audit with four new majors** (`BLOCKERS=0`, `MAJORS=4`, `MINORS=0`), was
**remediated again**, and **failed independent Re-audit V3** (`BLOCKERS=0`,
`MAJORS=2`, `MINORS=1`) with those four V2 reproductions verified fixed
(`4/4_VERIFIED`). It was **remediated for the third time**, **passed the three V3
reproductions on independent Re-audit V4** (`3/3_VERIFIED`) and **failed that
re-audit with three new majors** (`BLOCKERS=0`, `MAJORS=3`, `MINORS=0`). It was
**remediated for the fourth time**, **passed the three V4 reproductions on
independent Re-audit V5** (`3/3_VERIFIED`) while **failing that re-audit with three
new majors** (`BLOCKERS=0`, `MAJORS=3`, `MINORS=0`,
`PRIOR_REMEDIATION_REGRESSIONS=279_PASS`). It was **remediated for the fifth
time**, **passed the three V5 reproductions on independent Re-audit V6**
(`3/3_VERIFIED`) while **failing that re-audit with three new majors and one new
minor** (`BLOCKERS=0`, `MAJORS=3`, `MINORS=1`,
`PRIOR_REMEDIATION_REGRESSIONS=350_PASS`). It has now been **remediated for the
sixth time**, **passed all four V6 findings on independent Re-audit V7**
(`4/4_VERIFIED`) while **failing that re-audit with two new majors and no
minors** (`BLOCKERS=0`, `MAJORS=2`, `MINORS=0`,
`PRIOR_REMEDIATION_REGRESSIONS=477_PASS`). It has now been **remediated for the
seventh time**, **passed both V7 findings on independent Re-audit V8**
(`2/2_VERIFIED`) while **failing that re-audit with two new majors and one new
minor** (`BLOCKERS=0`, `MAJORS=2`, `MINORS=1`,
`PRIOR_REMEDIATION_REGRESSIONS=604_PASS`). It has now been **remediated for the
eighth time**, **passed both V8 findings on independent Re-audit V9**
(`2/2_VERIFIED`) while **failing that re-audit with two new majors and one new
minor** (`BLOCKERS=0`, `MAJORS=2`, `MINORS=1`,
`MAJOR_V9_001=WRAPPED_NON_AUTHORITY_FILE_URI_BYPASSES_FAIL_CLOSED_FILESYSTEM_CLASSIFIER`,
`MAJOR_V9_002=SUPPORTED_RUNTIME_TIMESTAMP_SEMANTICS_REOPEN_PRIOR_V6_FINDING_AND_KEEP_GLOBAL_GATE_RED`,
`MINOR_V9_001=REFERENCE_TEST_EVIDENCE_COUNTS_STALE_AFTER_FINAL_V8_AT_ADDITIONS`).
It has now been **remediated for the ninth time**, **passed all three V9 findings on
independent Re-audit V10** (`3/3_VERIFIED`) while **failing that re-audit with one
new major, no minors and no blockers** (`BLOCKERS=0`, `MAJORS=1`, `MINORS=0`,
`MAJOR_V10_001=WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCE_BYPASSES_PUBLIC_ROOT_FILESYSTEM_CLASSIFIER`).
It is not closed, independently verified or complete. `DP-122=VERIFIED_EXISTING`
and `AT-DP-122=PASS` belong only to the independent audit of the V11 bundle.

Sections 1–9 record the original implementation evidence, §10 records Remediation
V1, §11 records Remediation V2, §12 records Remediation V3, §13 records
Remediation V4, §14 records Remediation V5, §15 records Remediation V6, §16
records Remediation V7, §17 records Remediation V8, §18 records Remediation V9 and
§19 records Remediation V10; the earlier sections are preserved as historical
record.

## 1. Exact repository state

```text
BRANCH=feature/phase-11-stable-integrated-platform
BASE_HEAD=744de6d996e0aa3dc3f9326fdb33fc38ab13ac8d
FROZEN_PRE_PROMPT_BASELINE=d691c753c25801d1957fc8dee917ef4e6fff4694
REQUIRED_STARTING_TREE=36255f0293ac23fe93c2c85c94b989dd91ca0ff2
WORKTREE=CLEAN
```

### 1.1 Recorded provenance deviation

The implementation agent prompt requests preflight `HEAD=d691c753…`. The actual
implementation starting HEAD was `744de6d996e0aa3dc3f9326fdb33fc38ab13ac8d`.

* `744de6d`'s parent is exactly `d691c753c25801d1957fc8dee917ef4e6fff4694`;
* `d691c753`'s tree is exactly the required `36255f0293ac23fe93c2c85c94b989dd91ca0ff2`;
* the **only** intervening change is the committed Phase 11.22 implementation-agent
  prompt document itself (`docs/superpowers/prompts/2026-09-26-phase-11.22-event-system-implementation-agent-prompt.md`);
* `git diff --name-only d691c753..744de6d -- '*.py'` is empty: **zero
  production-code differences**.

The user explicitly authorized proceeding from `744de6d` with `d691c753` treated
as the frozen pre-prompt baseline. No reset, checkout, stash, clean or worktree
operation was performed at any point.

## 2. Implementation commits

```text
0f6c04e test(phase11): install phase11.22 event-system architecture guards
8ba14f3 feat(agent_runtime): register the phase11.22 platform event catalog
a8ecb67 feat(events): add the phase11.22 catalog, payload gate and translation table
37707b2 feat(agent_runtime): add the durable phase11.22 event repository
812ef35 feat(events): compose the canonical event system with retry, DLQ and safe replay
8f2153d feat(events): add phase11.22 producer adapters and Phase 11.1 composition
ca8a88d test(phase11): add the dp122 connected acceptance and ordering gates
047dcab docs(phase11): record phase11.22 event system pending independent audit
```

## 3. Key files

Production, new — `cmm/events/`: `__init__.py`, `event_catalog.py`,
`event_payload_safety.py`, `event_translation.py`, `event_system.py`,
`orchestration_adapter.py`, `kernel_adapter.py`, `platform_module.py`,
`storage.py`.

Production, additive Phase 9 hardening — `cmm/agent_runtime/`:
`runtime_event_bus.py`, `runtime_event_contracts.py`, `runtime_event_factory.py`,
`runtime_event_repository.py`, `runtime_event_replay.py`,
`runtime_event_errors.py`, `runtime_event_types.py`.

Production, composition — `cmm/application/local_runtime.py`.

Tests, new — `tests/events/`: `test_phase11_22_architecture.py`,
`test_phase11_22_event_catalog.py`, `test_phase11_22_durable_repository.py`,
`test_phase11_22_event_system.py`, `test_phase11_22_replay.py`,
`test_phase11_22_orchestration_adapter.py`, `test_phase11_22_kernel_adapter.py`,
`test_phase11_22_producer_disposition.py`, `test_phase11_22_composition.py`,
`test_phase11_22_security.py`, `test_phase11_22_ordering.py`,
`test_phase11_22_dp122_acceptance.py`.

Tests, modified — `tests/conftest.py` (suite-wide application data-directory
isolation), `tests/agent_runtime/test_runtime_event_bus.py` (corrected replay
semantics), `tests/platform/test_architecture.py` (sanctioned `cmm.events`
consumer), `tests/application/test_architecture.py` (event-system imports confined
to the composition root), `tests/application/test_local_runtime.py` and
`tests/application/test_phase11_3_dp103_acceptance.py` (production graph now
carries the event-system services).

Documentation — `docs/reference/phase-11-event-system.md`,
`docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md`,
`docs/roadmap/phase-11-stable-integrated-platform.md`, `ROADMAP.md`.

## 4. Producer-disposition summary

```text
CONNECTED_EXISTING_OWNER=12
CANONICAL_EXISTING_RUNTIME_EVENT=2
REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE=6
CATALOG_TOTAL=20
```

Connected: `message.received`, `intent.resolved`, `domain.selected`,
`approval.requested` (orchestration adapter); `workflow.started`,
`workflow.paused`, `workflow.completed`, `workflow.failed`, `operation.executed`,
`validation.completed`, `approval.resolved`, `memory.updated` (kernel adapter).

Canonical runtime events: `goal.created`, `goal.updated`.

Reserved, never emitted: `session.created`, `reasoning.completed`,
`knowledge.updated`, `backup.created`, `plugin.failed`, `security.alert`.

No producer was fabricated for a reserved capability, and a gate proves no
Phase 11.22 mapping targets a reserved name.

## 5. Gate evidence

```text
PHASE11_22_FOCUSED_TESTS=489 passed
AT_DP_122=33 passed (PASS_REPORTED)
FOCUSED_EVENT_BASELINE=856 passed (frozen baseline 856)
EVENT_INVENTORY=1269 passed (frozen baseline 1204, +65)
CLOSED_PHASE_REGRESSIONS=16703 passed, 0 failed
GLOBAL_PYTEST=22558 passed, 1 warning, 0 failed (frozen baseline 22069, +489)
DP_033_DOMAIN_EVENTS=23/23 canonical contracts, acceptance PASS
AT_DP_102=PASS
AT_DP_103=PASS
AT_DP_105=PASS
PHASE11_21_REGRESSION=PASS
PHASE11_34_REGRESSION_IF_APPLICABLE=PASS
AT_DP_150=PASS
CHANGED_FILE_RUFF=PASS (0 violations)
GLOBAL_RUFF_COUNT=810 (frozen pre-existing baseline 811)
GLOBAL_RUFF_NO_NEW_DEBT=PASS (the single delta is one pre-existing violation removed)
FORMAT_CHECK=PASS (ruff format --check, phase delta)
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
ARCHITECTURE_GATES=PASS
SECURITY_GATES=PASS
```

The frozen global baseline was re-derived from
`d691c753c25801d1957fc8dee917ef4e6fff4694` in a clean extraction: `811` Ruff
violations and `22069` global tests (22068 passed plus one git-dependent
observation test that fails only inside a `git archive` extraction with no
`.git` directory). Per-file Ruff counts are identical between baseline and
implementation except for one pre-existing violation removed from
`tests/conftest.py`.

The one retained global warning is the pre-existing unrelated `starlette`
`anyio` `DeprecationWarning`.

## 6. Reserved event owners

`session.created`, `reasoning.completed`, `knowledge.updated`, `backup.created`,
`plugin.failed`, `security.alert` are registered and reserved. Each owning
subsystem either does not exist at Phase 11.22 or exposes no safe emission seam.

## 7. Known non-blocking limitations

* the durable store is a local append-only JSONL file with no compaction or
  rotation, and is not optimised for very high volume (local-first by design);
* the dead-letter queue remains the existing in-memory Phase 9 implementation and
  is not durable;
* the bounded retry policy is configured by composition and is not persisted
  across process restart;
* six catalog events remain reserved as listed in §6.

## 8. Bundle

```text
AUDIT_BRANCH=feature/phase-11-stable-integrated-platform
AUDIT_HEAD=<the HEAD this document is committed at>
AUDIT_TREE=<the tree of that HEAD>
AUDIT_BUNDLE=phase-11.22-event-system-audit-v1.tar.gz
AUDIT_BUNDLE_SHA256=<reported in the implementation handoff>
WORKTREE=CLEAN
```

The exact `AUDIT_HEAD`, `AUDIT_TREE` and `AUDIT_BUNDLE_SHA256` are reported in the
implementation handoff message rather than embedded here. A document cannot
contain the hash of a bundle that includes that same document, so embedding it
would make the record self-referential and stale by construction. The values in
the implementation handoff are authoritative.

The bundle is produced with `git archive` from the exact committed final HEAD and
contains no `.git`, `.venv`, `.env`, private-key or credential path. It is not
modified after hashing.

## 9. Next step (original implementation)

Independent ChatGPT audit of the exact bundle. Phase 11.22 must not be described
as closed, audited, verified or complete, and Phase 11.23 has not begun.

---

## 10. Remediation V1

## 10.1 Verdict being remediated

Independent Audit V1 — `docs/audits/phase-11.22-event-system-independent-audit-v1.md`
(immutable), audited implementation HEAD
`4e3bfa8067099e2efd3c2fb793a2e640f5d1859e`, tree
`64ac59c05ee0b16121e48d57c3e3e2985df650d5`, bundle SHA-256
`a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3`:

```text
INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=0
MAJORS=4
MINORS=5
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_AUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V1_ONLY
```

## 10.2 Preflight verification at remediation start

```text
REMEDIATION_START_HEAD=f083c62943027ee9a3c6856ec73705314f781309
REMEDIATION_START_PARENT=5d7be37a3d0e48f36a709b5564ed2a3fa7badbd9
TRACKED_DELTA_FROM_AUDIT_COMMIT=docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v1-agent-prompt.md (only)
PRODUCTION_CODE_DELTA_FROM_AUDIT_COMMIT=NONE
TRACKED_WORKTREE=CLEAN
STASH_LIST=EMPTY
V1_BUNDLE_SHA256=a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3 (unchanged)
```

## 10.3 Remediation commits

```text
b99eb1e test(phase11): reproduce phase11.22 audit v1 findings
b070174 fix(events): remediate phase11.22 audit v1 event integrity and safety
acff794 fix(events): remediate phase11.22 audit v1 publication and replay boundaries
<docs commit> docs(phase11): record phase11.22 remediation v1 pending reaudit
```

The historical Audit V1 commit `5d7be37` is preserved; no history was rewritten
and no reset, checkout, stash, clean, worktree, push or merge was performed.

## 10.4 Findings disposition

```text
MAJOR_001=REMEDIATED_REPORTED
MAJOR_002=REMEDIATED_REPORTED
MAJOR_003=REMEDIATED_REPORTED
MAJOR_004=REMEDIATED_REPORTED
MINOR_001=REMEDIATED_REPORTED
MINOR_002=REMEDIATED_REPORTED
MINOR_003=REMEDIATED_REPORTED
MINOR_004=REMEDIATED_REPORTED
MINOR_005=REMEDIATED_REPORTED
```

Each finding was handled as reproduce-with-a-test → verify red → minimum fix →
verify green → nearest regressions. The defect-by-defect detail is recorded in
`docs/reference/phase-11-event-system.md` §24.

## 10.5 Production files changed

```text
cmm/agent_runtime/runtime_event_bus.py      MINOR-001, MAJOR-003
cmm/agent_runtime/runtime_event_factory.py  MAJOR-001, MINOR-002
cmm/agent_runtime/runtime_event_replay.py   MAJOR-003
cmm/agent_runtime/runtime_event_repository.py MINOR-002
cmm/events/event_catalog.py                 MINOR-004 (documentation only)
cmm/events/event_payload_safety.py          MAJOR-002, MINOR-003 support
cmm/events/event_system.py                  MAJOR-002, MAJOR-003
cmm/events/kernel_adapter.py                MAJOR-004, MINOR-003
```

## 10.6 New and strengthened adversarial regressions

```text
tests/events/test_phase11_22_remediation_v1_regressions.py (new, 86 tests)
  MAJOR-001 fingerprint completeness, same-ID conflict, durable tamper
  MAJOR-002 direct publish_event() boundary
  MAJOR-003 subscriber-targeted dead-letter replay
  MAJOR-004 explicit source correlation/causation
  MINOR-001 retry_total counting
  MINOR-002 malformed persisted payload shapes

tests/events/test_phase11_22_kernel_adapter.py  MINOR-003 fail-closed source content
tests/events/test_phase11_22_event_catalog.py   MINOR-004 derived documentation count
tests/events/test_phase11_22_security.py        universal publication boundary
tests/events/test_phase11_22_dp122_acceptance.py 11 new connected scenarios
```

## 10.7 Gate evidence (Remediation V1)

```text
REMEDIATION_TESTS=86 passed
PHASE_SUITE=tests/events/ 625 passed
AT_DP_122=45 passed
FOCUSED_EVENT_BASELINE=972 passed
EVENT_INVENTORY=1270 passed
CLOSED_PHASE_REGRESSIONS_PHASE9_RUNTIME=3635 passed
CLOSED_PHASE_REGRESSIONS_DOMAINS=11824 passed (Phase 10.33 Domain Events)
CLOSED_PHASE_ACCEPTANCES=228 passed (AT-DP-102, AT-DP-103, AT-DP-105, Phase 11.21, Phase 11.34, AT-DP-150)
GLOBAL_PYTEST=22694 passed, 1 warning, 0 failed (V1 22558 passed; +136 remediation tests)
CHANGED_FILE_RUFF=PASS (0 violations)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; frozen pre-existing baseline 811; V1 HEAD 810)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS (ruff format --check, changed-file delta)
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
ARCHITECTURE_GATES=PASS
SECURITY_GATES=PASS
```

The adversarial failures were confirmed red before the fixes: 101 failed / 194
passed across the touched event suites and 12 failed / 33 passed in `AT-DP-122`
at the reproduction commit.

## 10.8 Preserved evidence

The immutable V1 audit report and the immutable V1 bundle are byte-identical to
their audited state. The V1 bundle remains untracked, as repository policy does
not track audit bundles.

## 10.9 Next step (as recorded at Remediation V1 — superseded, historical)

Fresh independent ChatGPT re-audit of the **V2** exact-HEAD bundle
(`phase-11.22-event-system-audit-v2.tar.gz`). The phase remained
`REMEDIATED_AFTER_AUDIT_V1_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete.

That re-audit has since been performed (Re-audit V2, immutable report
`docs/audits/phase-11.22-event-system-independent-reaudit-v2.md`): it verified all
nine Audit V1 findings as remediated and returned four new majors, which
Remediation V2 (§11) has now fixed. Only the independent audit of the V3 bundle may
write `BLOCKERS=0`, `MAJORS=0`, `DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`,
`CLOSURE_ELIGIBLE=YES`.

---

## 11. Remediation V2

### 11.1 Verdict being remediated

Independent Re-audit V2 —
`docs/audits/phase-11.22-event-system-independent-reaudit-v2.md` (immutable),
audited implementation HEAD `e67ab1ccea691fd8e76a0dfb8e4721c03b13b51d`, tree
`a93cce0db1eb094a5b29f9d1322b5351d232e2dc`, bundle SHA-256
`172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04`:

```text
INDEPENDENT_REAUDIT_V2=FAIL
AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED
BLOCKERS=0
MAJORS=4
MINORS=0
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V2_ONLY
```

### 11.2 Preflight verification at remediation start

```text
REMEDIATION_START_HEAD=681a96a8ab059c64a07f52eea3c21857311aa7ce
REMEDIATION_START_PARENT=879be0e89d745a2d40331774983d1f62462a85a1
TRACKED_DELTA_FROM_REAUDIT_COMMIT=docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v2-agent-prompt.md (only)
PRODUCTION_CODE_DELTA_FROM_REAUDIT_COMMIT=NONE
TRACKED_WORKTREE=CLEAN
STASH_LIST=EMPTY
V1_BUNDLE_SHA256=a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3 (unchanged)
V2_BUNDLE_SHA256=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04 (unchanged)
V1_AUDIT_REPORT_UNMODIFIED=YES
V2_REAUDIT_REPORT_UNMODIFIED=YES
BUNDLES_TRACKED=NO (untracked historical evidence, repository policy)
```

No reset, checkout, stash, clean, worktree, push or merge was performed at any
point.

### 11.3 TDD red evidence

Before any production change, the new Remediation V2 regression module reproduced
all four findings against the unmodified audited implementation:

```text
tests/events/test_phase11_22_remediation_v2_regressions.py
  initial: 101 failed, 20 passed
  MAJOR-V2-001  73 failed  (24 unsafe header cases x 3 public routes, + 1 durable)
  MAJOR-V2-002   6 failed
  MAJOR-V2-003   7 failed
  MAJOR-V2-004  13 failed
  persistence regression set  2 failed
```

Each finding was then fixed by the minimum change and re-verified green before the
next finding. The V2 security regression matrix later added during §12 hardening
exposed two further residual header-container cases (a credential-shaped
`metadata`/`permissions` *key*), which were fixed in the same canonical scan rather
than by weakening the assertion.

### 11.4 Remediation commits

```text
<tests commit>  test(phase11): reproduce phase11.22 reaudit v2 findings
<fix commit>    fix(events): close phase11.22 event safety and schema gaps
<fix commit>    fix(events): enforce canonical event immutability and domain bridge fidelity
<docs commit>   docs(phase11): record phase11.22 remediation v2 pending reaudit
```

The Audit V1, Re-audit V2 and Remediation V1 history is preserved; no history was
rewritten.

### 11.5 Findings disposition

```text
MAJOR_V2_001=REMEDIATED_REPORTED
MAJOR_V2_002=REMEDIATED_REPORTED
MAJOR_V2_003=REMEDIATED_REPORTED
MAJOR_V2_004=REMEDIATED_REPORTED
AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED
```

The defect-by-defect detail is recorded in
`docs/reference/phase-11-event-system.md` §25.

### 11.6 Production files changed

```text
cmm/agent_runtime/runtime_event_bus.py         MAJOR-V2-003 delivery/DLQ snapshots
cmm/agent_runtime/runtime_event_contracts.py   MAJOR-V2-003 `detached_event_copy`
cmm/agent_runtime/runtime_event_errors.py      MAJOR-V2-002 unsupported-schema error
cmm/agent_runtime/runtime_event_factory.py     MAJOR-V2-002 `supports_schema_version`
cmm/agent_runtime/runtime_event_repository.py  MAJOR-V2-002, MAJOR-V2-003
cmm/events/event_payload_safety.py             MAJOR-V2-001 (plus MAJOR-V2-004 support)
cmm/events/event_system.py                     MAJOR-V2-001, MAJOR-V2-002
cmm/events/event_translation.py                MAJOR-V2-004
cmm/events/kernel_adapter.py                   MAJOR-V2-004
```

No Phase 10.33 Domain Event contract, Phase 7 validation contract, workflow
contract or Phase 9 architectural authority was modified. `cmm/domains/` is
untouched.

### 11.7 New and strengthened adversarial regressions

```text
tests/events/test_phase11_22_remediation_v2_regressions.py (new, 126 tests)
  MAJOR-V2-001 24 unsafe header channels x 3 public routes, file-backed rejection,
               safe-value controls, channel-completeness and coverage gates
  MAJOR-V2-002 facade / direct-route / durable rejection, untouched-store proof,
               supported close-and-reopen round-trip, non-reopenable refusal
  MAJOR-V2-003 subscriber isolation, repository and publication-result stability,
               fingerprint stability, file live/reopen equality, read detachment,
               replay detachment, dead-letter detachment
  MAJOR-V2-004 real Domain execution/approval/memory fidelity, sensitivity table,
               nested fail-closed scanning, execution_id consistency, whitelist
  persistence regression set (unsupported-schema, supported round-trip, live/reopen)

tests/events/test_phase11_22_security.py            +119-case persisted-field matrix
                                                    and named V2 security invariants
tests/events/test_phase11_22_dp122_acceptance.py    +19 connected scenarios
tests/events/test_phase11_22_event_catalog.py       nested-fact coverage, vocabulary-derived
tests/events/test_phase11_22_replay.py              identity assertions strengthened to
                                                    canonical equality
```

### 11.8 Gate evidence (Remediation V2)

```text
REMEDIATION_V2_TESTS=126 passed
PHASE_SUITE=tests/events/ 893 passed
AT_DP_122=64 passed
V1_REGRESSIONS=86 passed (preserved)
FOCUSED_EVENT_SEQUENCE=277 passed (runtime factory/repository/bus/replay)
DOMAIN_DP033_REGRESSIONS=930 passed (DP-033 acceptance + Domain Event modules)
ORCHESTRATION_VALIDATION_EVENTS=33 passed
SECURITY_AND_ARCHITECTURE=294 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAINS_REGRESSIONS=tests/domains/ 11824 passed
CLOSED_PHASE_ACCEPTANCES=218 passed
  (AT-DP-102, AT-DP-103, AT-DP-105, Phase 11.21, Phase 11.34, AT-DP-150)
CLOSED_PHASE_SUPPORT=112 passed
  (validation kernel events, orchestration events, workflow subsystem, DP-101)
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
GLOBAL_PYTEST=22962 passed, 1 warning, 0 failed
CHANGED_FILE_RUFF=PASS (0 violations)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; V2 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS (ruff format --check, changed-file delta)
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
ARCHITECTURE_GATES=PASS
SECURITY_GATES=PASS
```

The one retained global warning is the pre-existing unrelated `starlette` `anyio`
`DeprecationWarning`, unchanged from the V2 baseline.

### 11.9 Preserved evidence

The immutable Audit V1 report, the immutable Re-audit V2 report and the immutable
V1 and V2 bundles are byte-identical to their audited state. Both bundles remain
untracked, as repository policy does not track audit bundles.

### 11.10 Next step

Fresh independent ChatGPT re-audit of the **V3** exact-HEAD bundle
(`phase-11.22-event-system-audit-v3.tar.gz`). The phase remains
`REMEDIATED_AFTER_REAUDIT_V2_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete. Only that re-audit may write
`BLOCKERS=0`, `MAJORS=0`, `DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`,
`CLOSURE_ELIGIBLE=YES`.

## 12. Remediation V3

### 12.1 Verdict being remediated

Independent Re-audit V3
(`docs/audits/phase-11.22-event-system-independent-reaudit-v3.md`) verified all
prior fixes and returned three new findings:

```text
INDEPENDENT_REAUDIT_V3=FAIL
AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED
REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_VERIFIED
BLOCKERS=0
MAJORS=2
MINORS=1
MAJOR_V3_001=FULL_PERSISTED_EVENT_SAFETY_AND_HEADER_TYPE_VALIDATION_INCOMPLETE
MAJOR_V3_002=STRUCTURED_PAYLOAD_CANONICALIZATION_AND_ROUNDTRIP_UNSTABLE
MINOR_V3_001=DLQ_SNAPSHOT_MUTABLE
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V3_ONLY
```

No architecture finding was raised: the one canonical bus, registry, repository
contract, replay owner and dead-letter authority were preserved.

### 12.2 Preflight verification at remediation start

```text
BRANCH=feature/phase-11-stable-integrated-platform
REMEDIATION_V3_START_HEAD=5fc8556a627271c36c4ab302561c76dce44229ca
REAUDIT_V3_COMMIT=822c40fbf13f60202f443cbf7e5f93baee53f55a
START_HEAD_PARENT=822c40fbf13f60202f443cbf7e5f93baee53f55a
TRACKED_DELTA_FROM_REAUDIT=docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v3-agent-prompt.md
CODE_DELTA_FROM_REAUDIT=none
TRACKED_WORKTREE=CLEAN
V1_BUNDLE_SHA256=a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3
V2_BUNDLE_SHA256=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04
V3_BUNDLE_SHA256=27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589
```

All three bundle hashes still equal the independently audited values; the V1, V2
and V3 independent reports were not modified.

### 12.3 TDD red evidence

The new adversarial regression module was written before any production edit and
run against the unmodified V3 production bytes:

```text
tests/events/test_phase11_22_remediation_v3_regressions.py
  initial: 34 failed, 10 passed
```

The ten initial passes are the module's own controls plus one fact the V3 code
already protected (an opaque value in `payload.data`). Per finding:

```text
MAJOR-V3-001  opaque/bytes/bytearray/NaN/inf metadata          9 failed
              SecretObject credential leak (file-backed)       2 failed
              non-canonical sensitivity                        6 failed
              supported-string sensitivity normalization       1 failed
              plain-string permissions coercion                1 failed
              manual publish_event metadata/sensitivity        2 failed
MAJOR-V3-002  nested result_reference / approval_refs           3 failed
              live vs reopened sequence shape                   3 failed
              nested caller-alias isolation                     2 failed
MINOR-V3-001  DLQ get/list/remove/EventSystem snapshots         5 failed
```

Each finding was fixed by the minimum change to the existing safety authority and
canonical contracts and re-verified green before the next finding.

### 12.4 Remediation commits

```text
<tests commit>  test(phase11): reproduce phase11.22 reaudit v3 findings
<fix commit>    fix(events): close phase11.22 persisted event safety gaps
<fix commit>    fix(events): canonicalize structured payloads and detach dlq snapshots
<docs commit>   docs(phase11): record phase11.22 remediation v3 pending reaudit
```

The Audit V1, Re-audit V2, Remediation V1, Remediation V2 and Re-audit V3 history is
preserved; no history was rewritten.

### 12.5 Findings disposition

```text
MAJOR_V3_001=REMEDIATED_REPORTED
MAJOR_V3_002=REMEDIATED_REPORTED
MINOR_V3_001=REMEDIATED_REPORTED
AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED
REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED
```

The defect-by-defect detail is recorded in
`docs/reference/phase-11-event-system.md` §26.

### 12.6 Production files changed

```text
cmm/events/event_payload_safety.py             MAJOR-V3-001 structural value type gate,
                                               canonical sensitivity, permissions shape;
                                               MAJOR-V3-002 `canonicalize_platform_payload`
cmm/events/event_system.py                     MAJOR-V3-001 sensitivity/permissions gates at
                                               `create_event`; MAJOR-V3-002 canonicalization
cmm/agent_runtime/runtime_event_factory.py     MAJOR-V3-002 canonical nested serialization
                                               without `default=str`, deep-detaching normalize
cmm/agent_runtime/runtime_event_contracts.py   MINOR-V3-001 `detached_dead_letter_copy`
cmm/agent_runtime/runtime_event_dead_letter.py MINOR-V3-001 detached queue snapshots
```

No `cmm/domains/`, `kernel/`, Phase 11.2 orchestration, Phase 7 validation, workflow
or Phase 11.1 platform file was modified, and no second bus, registry, repository
protocol, replayer, DLQ, container or event contract was created.

### 12.7 New and strengthened adversarial regressions

```text
tests/events/test_phase11_22_remediation_v3_regressions.py (new, 44 tests)
  MAJOR-V3-001 9 unsafe metadata value types (incl. nested), SecretObject credential
               non-leak on the file-backed path, 6 non-canonical sensitivities,
               supported-string normalization, canonical-enum controls,
               plain-string and bytes permissions, manual `publish_event` gates,
               finite/nested metadata controls
  MAJOR-V3-002 nested result_reference and approval_refs publication, JSON-compatible
               container shape, live/reopened sequence and event equality,
               real PlatformOrchestrationEventSink round-trip, nested caller-alias
               isolation through both public routes, nested forbidden/opaque controls
  MINOR-V3-001 dead-letter get/list/remove/EventSystem snapshot detachment, retained
               subscription identity, attempt and status, targeted-replay preservation

tests/events/test_phase11_22_dp122_acceptance.py  +19 connected V3 scenarios
```

### 12.8 Gate evidence (Remediation V3)

```text
REMEDIATION_V3_TESTS=44 passed (initial red 34 failed / 10 passed)
PHASE_SUITE=tests/events/ 956 passed
AT_DP_122=83 passed
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAINS_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_REGRESSIONS=186 passed (DP-033 acceptance + Domain Event modules)
CLOSED_PHASE_ACCEPTANCES=218 passed
  (AT-DP-102, AT-DP-103, AT-DP-105, Phase 11.21, Phase 11.34, AT-DP-150)
CLOSED_PHASE_SUPPORT=112 passed
  (validation kernel events, orchestration events, workflow subsystem, DP-101)
SECURITY_AND_ARCHITECTURE=294 passed (part of tests/events/)
GLOBAL_PYTEST=23025 passed, 1 warning, 0 failed (V3 baseline 22962, +63)
CHANGED_FILE_RUFF=PASS (0 violations)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; V3 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS (ruff format --check, changed-file delta)
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
ARCHITECTURE_GATES=PASS
SECURITY_GATES=PASS
```

The V3 production tree measured `893` in `tests/events/` and `22962` globally; the
V3 additions are exactly `+44` new regressions and `+19` strengthened acceptance
scenarios.

The one retained global warning is the pre-existing unrelated `starlette` `anyio`
`DeprecationWarning`, unchanged from the V3 baseline.

### 12.9 Preserved evidence

The immutable Audit V1 report, the immutable Re-audit V2 report, the immutable
Re-audit V3 report and the immutable V1, V2 and V3 bundles are byte-identical to
their audited state. All three bundles remain untracked, as repository policy does
not track audit bundles.

### 12.10 Next step (historical — superseded by §13.10)

Fresh independent ChatGPT re-audit of the **V4** exact-HEAD bundle
(`phase-11.22-event-system-audit-v4.tar.gz`). The phase remains
`REMEDIATED_AFTER_REAUDIT_V3_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete. Only that re-audit may write
`BLOCKERS=0`, `MAJORS=0`, `DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`,
`CLOSURE_ELIGIBLE=YES`.

## 13. Remediation V4

### 13.1 Verdict being remediated

Independent Re-audit V4
(`docs/audits/phase-11.22-event-system-independent-reaudit-v4.md`, immutable)
verified all three V3 reproductions fixed and returned three new findings:

```text
INDEPENDENT_REAUDIT_V4=FAIL
BLOCKERS=0
MAJORS=3
MINORS=0
REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_VERIFIED
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V4_ONLY
```

### 13.2 Exact start state

```text
BRANCH=feature/phase-11-stable-integrated-platform
REAUDIT_V4_COMMIT=9e939d5eb4e62aac3cd1d51fe682415334c7713f
REMEDIATION_V4_START_HEAD=2401c6338911d3fb3359aadabf45e1c759bf90dc
HEAD_IS_DIRECT_CHILD_OF_REAUDIT_V4=YES
TRACKED_DELTA_FROM_REAUDIT_V4=docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v4-agent-prompt.md
CODE_CHANGES_BETWEEN_REAUDIT_V4_AND_START_HEAD=NONE
TRACKED_WORKTREE=CLEAN
```

Audited V4 evidence retained byte-identical:

```text
V1  a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3
V2  172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04
V3  27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589
V4  18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f
```

### 13.3 TDD red evidence

The new adversarial module
`tests/events/test_phase11_22_remediation_v4_regressions.py` was written and run
against the **unmodified** V4 production bytes before any production edit:

```text
REMEDIATION_V4_TESTS initial red = 18 failed / 5 passed
```

Every finding was additionally re-confirmed in isolation against the unmodified
V4 production file that owned it:

```text
MAJOR-V4-001  memoryview bypass reproductions                8 failed / 3 passed
MAJOR-V4-002  manual sensitivity reproductions               5 failed / 1 passed
MAJOR-V4-003  unsafe DLQ class-name reproductions            5 failed / 1 passed
```

Each fix was then applied alone and its own reproductions turned green, proving no
finding was closed by an unrelated change.

### 13.4 Findings and remediation

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V4-001` | the V3 scalar binary rejection already listed `memoryview`, but the shared sequence predicate `_is_sequence()` excluded only `str`, `bytes` and `bytearray`. `memoryview` is a registered `collections.abc.Sequence`, so a binary buffer was treated as an ordinary descriptive sequence and recursively canonicalized into a plain integer list — raw binary bytes entered persisted `payload.data` and persisted header containers | the **one existing** sequence predicate now classifies `memoryview` as binary, so the already-existing scalar binary rejection is reachable for it. `_canonicalize_payload_value()` also refuses a binary container explicitly. `bytes`, `bytearray` and `memoryview` now all fail closed in every persisted Phase 11.22 content channel |
| `MAJOR-V4-002` | `validate_platform_event_facts()` called `canonicalize_platform_event_sensitivity()` and discarded its return value, and `AgentRuntimeEventNormalizer` copied `header.sensitivity` unchanged. A manually built event with `sensitivity="restricted"` therefore passed the public boundary and kept a `str`: accepted and stored by the in-memory repository, and `AttributeError: 'str' object has no attribute 'value'` for the file-backed one | `EventSystem._validate_platform_event()` now **normalizes** rather than merely validates: it applies the existing canonical sensitivity rule to the persisted fact and, when the result differs, replaces the header's sensitivity with the canonical member before normalization and persistence. Both public routes now produce one representation and both official repository implementations agree |
| `MAJOR-V4-003` | the DLQ derived `error_type`/`error` from `type(exc).__name__` unvalidated. Python permits `type("api_key=abcdef1234567890", (Exception,), {})`, so a credential-bearing (or private-marker) class name could enter canonical DLQ data with no raw exception message involved | one bounded safe DLQ error-category derivation now guards both exception-capture sites and the single DLQ write point. The transport-local bounded-name half lives in `cmm/agent_runtime/runtime_event_bus.py`; the credential/private-marker half is `category_for_delivery_error()` in the existing `cmm/events/event_payload_safety.py`, injected through `bind_error_categorizer()` by the composed `EventSystem`, because `cmm/agent_runtime` is architecturally forbidden from importing `cmm.domains`. An ordinary `RuntimeError` stays meaningfully categorized; every other name becomes the neutral bounded category `SubscriberDeliveryError` |

Sensitivity canonicalization decision: the preferred minimal rule was chosen — a
canonical string is accepted and normalized immediately to `EventSensitivity`,
consistent with the public `publish()` contract, with `create_event()` and with the
canonical repository contract.

DLQ error-category rule: store the class name only when it is both a bounded
Python-style identifier (`^[A-Za-z_][A-Za-z0-9_]{0,127}$`) **and** free of any
Phase 10.33 high-confidence credential and any forbidden private marker; otherwise
record `SubscriberDeliveryError`.

### 13.5 Production files changed

```text
cmm/events/event_payload_safety.py             MAJOR-V4-001 `_is_sequence` classifies
                                               `memoryview` as binary; explicit binary
                                               refusal in `_canonicalize_payload_value`;
                                               MAJOR-V4-003 `category_for_delivery_error`
cmm/events/event_system.py                     MAJOR-V4-002 canonical sensitivity
                                               normalization at the publication boundary;
                                               MAJOR-V4-003 categorizer injection
cmm/agent_runtime/runtime_event_bus.py         MAJOR-V4-003 bounded-name safe-category
                                               derivation, categorizer binding, defensive
                                               check at the single DLQ write point
```

`cmm/agent_runtime` still has **zero** `cmm.domains` imports
(`AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0`), so the Phase 10.42 architecture gates remain
green.

### 13.6 New adversarial regressions

```text
tests/events/test_phase11_22_remediation_v4_regressions.py   23 tests
  MAJOR-V4-001  payload/nested-payload/metadata/nested-metadata/permissions binary
                rejection for bytes, bytearray and memoryview; durable-store byte
                assertion; explicit "never an integer array" shape assertions
  MAJOR-V4-002  in-memory and file-backed canonical sensitivity, repository-independence
                parity, enum control, fingerprint identity with `create_event`, caller
                event left unmutated
  MAJOR-V4-003  credential-bearing and private-marker class names never reach any
                DLQ-facing field, neutral bounded fallback, unbounded class name,
                ordinary `RuntimeError` control, replay-path failure metadata

tests/events/test_phase11_22_dp122_acceptance.py             +12 connected V4 scenarios
  payload/bytes-control/bytearray-control binary rejection, nested payload memoryview,
  metadata memoryview, manual-event memoryview shape assertion, manual sensitivity
  against the real file-backed composition, repository-independence parity, enum
  control, credential/private-marker class names, ordinary `RuntimeError` control
```

### 13.7 Gate evidence (Remediation V4)

```text
REMEDIATION_V4_TESTS=23 passed (initial red 18 failed / 5 passed)
PHASE_SUITE=tests/events/ 991 passed
AT_DP_122=95 passed
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAINS_REGRESSIONS=tests/domains/ 11824 passed
CLOSED_PHASE_ACCEPTANCES=218 passed
  (AT-DP-102, AT-DP-103, AT-DP-105, Phase 11.21, Phase 11.34, AT-DP-150)
CLOSED_PHASE_SUPPORT=112 passed
  (validation kernel events, orchestration events, workflow subsystem, DP-101)
ARCHITECTURE_AND_SECURITY_GATES=294 passed (part of tests/events/)
GLOBAL_PYTEST=23060 passed, 1 warning, 0 failed (V3 baseline 23025, +35)
CHANGED_FILE_RUFF=PASS (0 violations)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; V4 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS (ruff format --check, changed-file delta)
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
ARCHITECTURE_GATES=PASS
SECURITY_GATES=PASS
```

The V4 production tree measured `956` in `tests/events/` and `23025` globally; the
V4 additions are exactly `+23` new regressions and `+12` strengthened acceptance
scenarios, so both deltas are `+35` and are accounted for exactly.

The one retained global warning is the pre-existing unrelated `starlette` `anyio`
`DeprecationWarning`, unchanged from the V3 baseline.

### 13.8 Mandatory invariant evidence

```text
BINARY_MEMORYVIEW_REJECTED_EVERYWHERE=PASS
FULL_CANONICAL_EVENT_SECURITY=PASS
DLQ_SECRET_SAFETY=PASS
RAW_EXCEPTION_MESSAGE_NOT_STORED=PASS
UNSAFE_EXCEPTION_CLASS_NAME_NOT_STORED=PASS

MANUAL_PUBLISH_EVENT_SENSITIVITY_CANONICAL=PASS
IN_MEMORY_AND_FILE_REPOSITORY_PARITY=PASS
FINGERPRINT_STABILITY=PASS
```

### 13.9 Preserved evidence

The immutable Audit V1 report, the immutable Re-audit V2 report, the immutable
Re-audit V3 report, the immutable Re-audit V4 report and the immutable V1, V2, V3
and V4 bundles are byte-identical to their audited state. All four bundles remain
untracked, as repository policy does not track audit bundles.

### 13.10 Next step (historical — superseded by §14.11)

Fresh independent ChatGPT re-audit of the **V5** exact-HEAD bundle
(`phase-11.22-event-system-audit-v5.tar.gz`). The phase then stood at
`REMEDIATED_AFTER_REAUDIT_V4_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete. Only that re-audit may write
`BLOCKERS=0`, `MAJORS=0`, `DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`,
`CLOSURE_ELIGIBLE=YES`. That re-audit ran (Re-audit V5) and its result is
recorded in §14.

## 14. Remediation V5

### 14.1 Verdict being remediated

Independent Re-audit V5
(`docs/audits/phase-11.22-event-system-independent-reaudit-v5.md`, immutable,
`BUNDLE_INTEGRITY=PASS`, `EXACT_HEAD=PASS`, `EXACT_TREE=PASS`) returned:

```text
INDEPENDENT_REAUDIT_V5=FAIL
V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=279_PASS
BLOCKERS=0
MAJORS=3
MINORS=0
MAJOR_V5_001=ARRAY_BUFFER_BINARY_BYPASSES_CANONICAL_EVENT_SAFETY
MAJOR_V5_002=BOUNDED_PAYLOAD_SEMANTICS_DO_NOT_PREVENT_RAW_CONTENT_MIRRORING
MAJOR_V5_003=CANONICAL_BUS_DLQ_SECRET_SAFETY_DEPENDS_ON_EXTERNAL_CATEGORIZER_BINDING
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V5_ONLY
```

### 14.2 Exact start state

```text
BRANCH=feature/phase-11-stable-integrated-platform
PROMPT_COMMIT_HEAD=3a73e3a48d0e5daf420239486a06f5f5f79e4c6b
REAUDIT_V5_COMMIT=5a7a5ddc5486502f46e48dc9020045547021a238
REAUDIT_V5_TREE=74934b505fe24dd30076052630505fbc3a026b1b
AUDITED_V5_IMPLEMENTATION_HEAD=8187ec9064247ca3a26d764fa7386c241b21f302
AUDITED_V5_IMPLEMENTATION_TREE=1268d3f066e49632d25f5e0bce6ff76f2b97bcad
TRACKED_DELTA_FROM_REAUDIT_V5=docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v5-agent-prompt.md
PRODUCTION_CODE_DELTA_FROM_REAUDIT_V5=0
TRACKED_WORKTREE=CLEAN
GIT_DIFF_CHECK=PASS
QUARANTINE_STASH=NOT_MUTATED (inspected only; no stash entry created, applied or dropped)
HISTORICAL_BUNDLE_HASHES=EXACT
  V1=a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3
  V2=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04
  V3=27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589
  V4=18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f
  V5=105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10
```

Preflight passed before any production mutation; no `reset`, `stash`, `clean`,
`worktree`, `merge` or `push` operation was used.

### 14.3 TDD red evidence

Before any production change, `tests/events/test_phase11_22_remediation_v5_regressions.py`
was written to reproduce all three findings and its red state was recorded:

```text
REMEDIATION_V5_TESTS_INITIAL_RED=30 failed, 41 passed
```

Every failure was a genuine reproducer, not a helper artefact:

```text
array.array payload value accepted and canonicalized to [115, 101, 99, ...]
nested array.array in payload accepted
array.array in metadata accepted
manual publish_event with array.array accepted
durable file-backed publication of array.array succeeded
  -> ARRAY_BUFFER_ACCEPTED=True / ARRAY_BUFFER_PERSISTED=True

status="<raw user sentence>" accepted and durably persisted
request_id="<raw user sentence>" accepted and durably persisted
metadata={"note": "<raw user sentence>"} accepted and durably persisted
unknown metadata key accepted
nested metadata prose accepted
approved/duration_ms/count = "<raw sentence>" accepted

direct canonical bus + DLQ + bounded retry + no categorizer:
  error_type = "api_key_abcdef1234567890", error = "api_key_abcdef1234567890"
```

### 14.4 Findings and remediation

| Finding | Remediation |
| --- | --- |
| `MAJOR-V5-001` | binary/buffer classification is now semantic. `_is_binary_buffer()` performs one bounded buffer-protocol probe (a C-contiguous unsigned-byte view exists) and permanently rejects `bytes`, `bytearray`, `memoryview` and every `array.array` typecode. It is consulted before all generic sequence handling in `_is_sequence()`, `_reject_non_descriptive_value()`, `_canonicalize_payload_value()`, `_freeze()` and `validate_platform_permissions()`. `str`/`bool`/`int`/`float`/`None` are fast-pathed and never probed; the probe never reads, copies, resizes or exposes the buffer |
| `MAJOR-V5-002` | one canonical `PAYLOAD_KEY_CLASSES` specification assigns every allowed payload key exactly one explicit lifecycle value class, dispatched through `_validate_class()`. Identifiers are bounded single tokens, categories are bounded tokens narrower than identifiers, booleans require real booleans, numbers require real finite numbers, versions accept a bounded number or token, timestamps require the canonical ISO-8601 string form, and structured references are validated recursively against `STRUCTURED_REFERENCE_KEYS`. `METADATA_KEY_CLASSES` admits only bounded lifecycle metadata keys actually used by current producers/adapters/closed-phase contracts, with `METADATA_CONTAINER_KEYS` for the bounded container; an unknown metadata key fails closed. A `None` optional identifier remains accepted, matching the persisted header gate |
| `MAJOR-V5-003` | `safe_delivery_error_type()` returns the neutral bounded category `SubscriberDeliveryError` whenever no external categorizer is bound, so the canonical transport retains no attacker-influenced class name. The transport-local bounded-name predicate is still applied when a categorizer is bound, the composed `EventSystem` still binds the canonical credential/private-marker categorizer, and `cmm.agent_runtime` still imports `cmm.domains` zero times |

Binary/buffer classification decision (explicit): the **semantic buffer-protocol
rule** was chosen over extending the exact-class list, because the frozen invariant
is semantic and a longer list would leave the same defect class open for the next
standard buffer type. The RED suite proves rejection of `B`, `b`, `h`, `i`, `f` and
`d` typecodes while preserving ordinary `list`/`tuple` identifier containers and an
explicit `list[int]` structured reference. Banning all sequences was explicitly
rejected.

Lifecycle-fact semantic key/value classes (explicit):

```text
identifier/ reference : request_id session_id workflow_id run_id goal_id
                        operation_id approval_id domain_id agent_id task_id
                        validation_id event_id execution_id correlation_id
                        causation_id aggregate_id producer parent_run_id
                        root_run_id node_id plan_node_id decision_id
                        primary_domain capability_id reference_id
category / token      : status state intent route channel policy
                        policy_disposition error_category error_code
                        reason_code sensitivity event_type
boolean               : needs_clarification approved is_success
number                : duration_ms count attempts sequence
version               : version schema_version
timestamp             : occurred_at emitted_at
structured reference  : result_reference (recursive documented shape)
                        approval_refs (bounded sequence of documented shapes)
reference sequence    : supporting_domains related_domain_ids reason_codes
```

Metadata policy (explicit):

```text
status_code -> category        attempt -> number      origin -> category
reason      -> category        error_type -> identifier
category    -> category        replay -> boolean     flag -> boolean
label       -> category        ratio -> number       count -> number
detail      -> bounded metadata container {inner: bounded sequence,
                                           count: number,
                                           reference_id: identifier}
unknown key -> FAIL CLOSED
```

Direct-bus DLQ fail-safe rule (explicit): no categorizer bound → neutral bounded
category. The alternative "DLQ-enabled bounded retry cannot be activated without a
categorizer" was rejected because it would change canonical composition and
historical compatibility behaviour; the neutral default is fail-safe and minimally
invasive and preserves the legacy direct single-attempt shape exactly.

### 14.5 Remediation commits

```text
675802a test(phase11): reproduce phase11.22 reaudit v5 findings
40e0feb fix(events): close binary-buffer and lifecycle-fact semantic gaps
557313f fix(events): make canonical dlq categorization fail safe
0b7f151 test(phase11): strengthen at-dp-122 for the v5 lifecycle-fact contract
```

No history was rewritten, no historical audit or remediation commit was squashed,
and no bundle was overwritten.

### 14.6 Production files changed

```text
cmm/events/event_payload_safety.py        +602/-…  semantic buffer classifier,
                                                   payload value classes,
                                                   metadata value classes,
                                                   recursive structured shapes
cmm/agent_runtime/runtime_event_bus.py     +33/-…  fail-safe DLQ categorization
                                                   when no categorizer is bound
```

No second bus, registry, repository protocol, replayer, DLQ, event contract,
safety-policy module, payload registry, application container, service locator,
broker abstraction or generic event-schema engine was introduced, and
`AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0` still holds.

### 14.7 New and strengthened adversarial regressions

```text
tests/events/test_phase11_22_remediation_v5_regressions.py   NEW, 71 tests
  MAJOR-V5-001  array/b/c/h/i/f/d payload rejection, never becomes an integer
                array, public create_event path, nested array in payload,
                array inside a payload list, metadata array, nested metadata
                array, manual publish_event array, durable-file unchanged,
                signed/float typecodes
  MAJOR-V5-001 controls  ordinary list/tuple of safe identifiers, explicit
                list[int] inside a structured reference
  MAJOR-V5-002  raw sentence into status, into request_id, into metadata, into
                an unknown metadata key, into nested metadata, into boolean
                fields, into numeric fields, into categorical fields, unbounded
                10,000-character status, durable file unchanged, manual
                publish_event, structured-reference prose, reference-list prose
  MAJOR-V5-002 controls  every legitimate identifier/categorical/numeric/
                boolean/canonical-timestamp/structured fact, the documented safe
                metadata examples, bounded numeric metadata with safe nesting,
                every allowed key has a declared value class, identifier pattern
                narrowness
  MAJOR-V5-003  direct canonical bus + DLQ + retries with no categorizer:
                credential-shaped class name, private-marker class name, neutral
                category recorded, ordinary name neutralized, no DLQ-facing field
                carries the secret, shared helper fail-safe
  MAJOR-V5-003 controls  composed EventSystem RuntimeError stays useful,
                composed EventSystem still neutralizes a credential class name,
                legacy direct single-attempt bus shape unchanged

tests/events/test_phase11_22_dp122_acceptance.py    +29 connected scenarios (95 -> 124)
  array.array payload/nested/metadata/manual rejection, never durable as
  integers, raw text cannot relocate into request_id/status/metadata, boolean and
  numeric prose rejection, legitimate identifier/categorical/boolean/numeric
  facts persist, legitimate metadata persists, direct canonical bus + DLQ without
  categorizer has no credential and no private marker, composed RuntimeError
  stays useful, legacy direct single-attempt bus unchanged

tests/events/test_phase11_22_remediation_v3_regressions.py   3 controls updated
tests/events/test_phase11_22_security.py                     1 control updated
  The invented metadata key names in these two prior-regression controls are now
  carried by the declared bounded metadata vocabulary, so the same original
  invariants (finite scalars and safe JSON-compatible nesting; caller-alias
  isolation with nested metadata; event metadata never becomes an executable
  grant) are still proven on the clarified lifecycle-fact contract.
```

### 14.8 Gate evidence (Remediation V5)

```text
REMEDIATION_V5_TESTS=71 passed (initial red 30 failed / 41 passed)
V4_REGRESSIONS=23 passed (preserved)
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
PRIOR_REMEDIATION_REGRESSIONS=279 passed (V1-V4 preserved)
REMEDIATION_V1_TO_V5_REGRESSIONS=350 passed
PHASE_SUITE=tests/events/ 1091 passed
AT_DP_122=124 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_ACCEPTANCE=tests/domains/test_domain_events_dp033_acceptance.py 92 passed
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
CLOSED_PHASE_ACCEPTANCES=310 passed
  (AT-DP-102, AT-DP-103, AT-DP-105, Phase 11.21, Phase 11.34, AT-DP-150, AT-DP-033)
CLOSED_PHASE_SUPPORT=579 passed
  (validation kernel events, orchestration suite, workflow subsystem)
ARCHITECTURE_AND_SECURITY_GATES=294 passed (part of tests/events/)
ORCHESTRATION_VALIDATION_WORKFLOW=1077 passed
PHASE11_21_AND_11_34=116 passed
GLOBAL_PYTEST=23160 passed, 1 warning, 0 failed (V5 baseline 23060, +100)
CHANGED_FILE_RUFF=PASS (0 violations in every changed/created file)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; V5 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS (ruff format --check, changed-file delta)
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
ARCHITECTURE_GATES=PASS
SECURITY_GATES=PASS
```

The V4 production tree measured `991` in `tests/events/` and `23060` globally. The
V5 additions are exactly `+71` new adversarial regressions and `+29` strengthened
acceptance scenarios, so the global delta is `+100` and `tests/events/` moves
`991 → 1091` (`+100`); the two deltas are equal because the strengthened acceptance
scenarios live inside `tests/events/`.

Four repository files unrelated to Phase 11.22
(`cmm/agent_runtime/approval_repository.py`,
`cmm/agent_runtime/domain_permission_contracts.py`,
`cmm/agent_runtime/operation_registry.py`,
`cmm/agent_runtime/permission_restriction_contracts.py`) were already unformatted
under `ruff format --check` at the audited V4 HEAD and were left untouched; no
unrelated formatting churn was introduced. The one retained global warning is the
pre-existing unrelated `starlette` `anyio` `DeprecationWarning`.

### 14.9 Mandatory invariant evidence

```text
BINARY_BUFFER_VALUES_FAIL_CLOSED=PASS
BINARY_BUFFER_VALUES_NEVER_BECOME_INTEGER_ARRAYS=PASS
BINARY_BUFFER_VALUES_NEVER_ENTER_PERSISTENCE=PASS
RAW_USER_TEXT_CANNOT_BE_RELOCATED_INTO_LIFECYCLE_FIELDS=PASS
METADATA_IS_NOT_A_PROSE_SIDE_CHANNEL=PASS
IDENTIFIER_FIELDS_ARE_SEMANTICALLY_BOUNDED=PASS
CATEGORICAL_FIELDS_ARE_SEMANTICALLY_BOUNDED=PASS
BOOLEAN_FIELDS_REQUIRE_BOOLEAN_VALUES=PASS
NUMERIC_FIELDS_REQUIRE_NUMERIC_VALUES=PASS
DLQ_SECRET_SAFETY_FAILS_SAFE_WITHOUT_EXTERNAL_BINDING=PASS
RAW_EXCEPTION_MESSAGES_NEVER_ENTER_DLQ=PASS
UNSAFE_EXCEPTION_CLASS_NAMES_NEVER_ENTER_DLQ=PASS
FULL_CANONICAL_EVENT_SECURITY=PASS
LIFECYCLE_FACT_ONLY_POLICY=PASS

CONTENT_BOUND_FINGERPRINT=PASS
SAME_ID_DIFFERENT_CONTENT_FAIL_CLOSED=PASS
TAMPER_DETECTION=PASS
UNSUPPORTED_SCHEMA_REJECTED_BEFORE_APPEND=PASS
SUPPORTED_SCHEMA_REOPEN_ROUNDTRIP=PASS
SAFE_NESTED_MAPPING_PUBLICATION=PASS
SAFE_NESTED_SEQUENCE_PUBLICATION=PASS
FILE_LIVE_AND_REOPENED_FACTS_MATCH=PASS
PUBLICATION_RESULT_ALIAS_ISOLATION=PASS
SUBSCRIBER_MUTATION_ISOLATION=PASS
REPOSITORY_SNAPSHOT_ISOLATION=PASS
MANUAL_SENSITIVITY_CANONICALIZATION=PASS
IN_MEMORY_AND_FILE_REPOSITORY_PARITY=PASS

BINARY_MEMORYVIEW_REJECTED_EVERYWHERE=PASS
MANUAL_PUBLISH_EVENT_SENSITIVITY_CANONICAL=PASS
RAW_EXCEPTION_MESSAGE_NOT_STORED=PASS
UNSAFE_EXCEPTION_CLASS_NAME_NOT_STORED=PASS
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
```

### 14.10 Preserved evidence

The immutable Audit V1 report, the immutable Re-audit V2 report, the immutable
Re-audit V3 report, the immutable Re-audit V4 report, the immutable Re-audit V5
report and the immutable V1, V2, V3, V4 and V5 bundles are byte-identical to their
audited state. All five bundles remain untracked, as repository policy does not
track audit bundles. No stash was created, applied or dropped.

### 14.11 Next step (historical — superseded by §15.11)

Fresh independent ChatGPT re-audit of the **V6** exact-HEAD bundle
(`phase-11.22-event-system-audit-v6.tar.gz`). The phase remains
`REMEDIATED_AFTER_REAUDIT_V5_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete. Only that re-audit may write
`BLOCKERS=0`, `MAJORS=0`, `DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`,
`CLOSURE_ELIGIBLE=YES`.

## 15. Remediation V6

### 15.1 Verdict being remediated

Independent Re-audit V6
(`docs/audits/phase-11.22-event-system-independent-reaudit-v6.md`, immutable,
`BUNDLE_INTEGRITY=PASS`, `EXACT_HEAD=PASS`, `EXACT_TREE=PASS`) returned:

```text
INDEPENDENT_REAUDIT_V6=FAIL
V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=350_PASS
BLOCKERS=0
MAJORS=3
MINORS=1
MAJOR_V6_001=NUMERIC_LIFECYCLE_FACTS_ARE_NOT_ACTUALLY_BOUNDED_AND_REPOSITORY_PARITY_BREAKS
MAJOR_V6_002=FILESYSTEM_SECRET_PATHS_CAN_ENTER_PERSISTED_IDENTIFIER_FIELDS
MAJOR_V6_003=PAYLOAD_CAN_SHADOW_CANONICAL_HEADER_IDENTITY_AND_SENSITIVITY_FACTS
MINOR_V6_001=CANONICAL_TIMESTAMP_VALIDATION_ACCEPTS_INVALID_OR_AMBIGUOUS_TIMESTAMPS
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V6_ONLY
```

### 15.2 Exact start state

```text
BRANCH=feature/phase-11-stable-integrated-platform
PROMPT_COMMIT_HEAD=8f1ed9789f78513cd2340f9a713bc319ca0c585c
REAUDIT_V6_COMMIT=08776a640d7239d7cd3020defe22fd95232e0399
REAUDIT_V6_TREE=aad44263c27764a3b293ea576569d7a21baac015
AUDITED_V6_IMPLEMENTATION_HEAD=2b45244a0f1b73a46e4cf2b93db40b3fcf88b552
AUDITED_V6_IMPLEMENTATION_TREE=f28f95ed7ae2a4a2e37de03a618688bbdf343b3b
TRACKED_DELTA_FROM_REAUDIT_V6=docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v6-agent-prompt.md
PRODUCTION_CODE_DELTA_FROM_REAUDIT_V6=0
TRACKED_WORKTREE=CLEAN
GIT_DIFF_CHECK=PASS
QUARANTINE_STASH=NOT_MUTATED (no stash entry created, applied, popped or dropped)
HISTORICAL_BUNDLE_HASHES=EXACT
  V1=a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3
  V2=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04
  V3=27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589
  V4=18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f
  V5=105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10
  V6=67b27f6effa5297757453aba3021a7211fe4ee88e194a6d65eefa353060f1008
```

All six bundles were re-hashed from the working tree and matched the declared
values exactly. Preflight passed before any production mutation; no `reset`,
`stash`, `clean`, `worktree`, `merge` or `push` operation was used.

### 15.3 TDD red evidence

Before any production change, `tests/events/test_phase11_22_remediation_v6_regressions.py`
was written to reproduce all four findings and its red state was recorded:

```text
REMEDIATION_V6_TESTS_INITIAL_RED=90 failed, 37 passed (127 collected)

  MAJOR-V6-001 numeric bounds                30 failed /  50
  MAJOR-V6-002 filesystem path safety        25 failed /  38
  MAJOR-V6-003 canonical header authority    21 failed /  28
  MINOR-V6-001 timestamp semantics           17 failed /  18
```

Every failure was a genuine reproducer, not a helper artefact. The audited
behaviours were independently re-observed against the unmodified start state
before the fix, exactly as the re-audit reported them:

```text
count = 10 ** 5000, official in-memory repository -> PUBLISHED, repository count 1
count = 10 ** 5000, official file repository      -> ValueError
  "Exceeds the limit (4300 digits) for integer string conversion", repository count 0
count=-1 / duration_ms=-5 / attempts=-1 / sequence=-1 / duration_ms=1e308 all ACCEPTED
metadata attempt=-1 ACCEPTED

request_id="file:///Users/alice/.ssh/id_rsa"  ACCEPTED, ".ssh" present in durable JSON
request_id="Users/alice/.ssh/id_rsa"         ACCEPTED
request_id="C:/Users/alice/.ssh/id_rsa"      ACCEPTED
producer="Users/alice/.ssh/id_rsa"           ACCEPTED and persisted
  (the three forms beginning with "/" or "\" were already refused by the
   single-token shape rule; the audited class as a whole was not)

header.event_id=header-event + payload.event_id=payload-event -> BOTH persisted
header.correlation_id/causation_id/producer likewise BOTH persisted
header.sensitivity=internal + payload.sensitivity=restricted -> BOTH persisted
payload.event_type="some.other.event" + header event_type="message.received" -> BOTH persisted

9999-99-99T99:99Z / 2026-02-31T12:00Z / 2026-09-27T25:61Z / 2026-09-27T12:00 all ACCEPTED
```

The red run also exposed that the audited huge integer cannot even be rendered as
a pytest parameter id — `pytest` itself raises the interpreter's 4300-digit
conversion error while collecting a `10 ** 5000` parameter — which is a second,
independent demonstration that the interpreter limit was the only boundary in
place.

### 15.4 Findings and remediation

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V6-001` | the V5 semantic numeric class checked only "is a finite Python number". It enforced no upper bound and none of the non-negative semantics its key names imply, so `count = 10 ** 5000` was accepted by the in-memory repository and crashed the file-backed repository during serialization — the same public event diverged across the two official repositories — while `count=-1`, `duration_ms=-5`, `attempts=-1`, `sequence=-1` and `duration_ms=1e308` were all accepted | one explicit bound `MAX_PLATFORM_NUMERIC_FACT = 2**63 - 1` plus one small semantic table `NUMERIC_FACT_SEMANTICS` in the **existing** safety authority. `count`/`attempt`/`attempts`/`sequence` are real integers in `[0, bound]`; `duration_ms` is a finite integer/float in `[0, bound]`; `ratio` is the normalized `[0.0, 1.0]` ratio current producers publish; every other numeric fact is finite and inside `[-bound, bound]`. Numeric versions are bounded by the same constant. The bound is enforced before any repository interaction, so no repository discovers an invalid platform number and the two official repositories cannot diverge |
| `MAJOR-V6-002` | the identifier character set kept `:`/`/`/`.` with no path-safety classification, so non-public local filesystem locations qualified as identifiers and were durably persisted, including in the canonical header `producer` fact — a direct violation of the frozen design's "filesystem secrets/paths where not public-safe" rule | one narrow, purely syntactic classifier in the **existing** identifier/header safety authority: a `file:` URI scheme, a Windows drive-root path, a UNC share, an absolute POSIX path or `~` shorthand, a user-home directory segment (`Users`/`home`/`Documents and Settings`), a known secret-bearing private directory segment (`.ssh`, `.aws`, `.gnupg`, `.kube`, `.docker`, `.azure`, `.netrc`, `.pgpass`, `.npmrc`, `.git-credentials`) or a private key material file name. No I/O, no path resolution, no content inspection. The rule runs on every persisted identifier channel: `payload.data` identifiers, header identifier facts, `permissions` entries and identifier-classified metadata facts |
| `MAJOR-V6-003` | payload keys equivalent to canonical header facts were validated independently and persisted alongside the header, so two contradictory versions of one event fact coexisted — including `header.sensitivity=internal` next to `payload.sensitivity=restricted`, a stricter classification hidden where the canonical authority would never see it | the payload keys that name a canonical header fact are declared once, as `CANONICAL_HEADER_PAYLOAD_KEYS` (the exact intersection of the bounded payload vocabulary with the canonical header fact names), and are consumed into the canonical header before persistence instead of being persisted twice. An unset header fact takes the payload value, an equal one is left alone, a contradictory one fails closed, and an explicit `None` optional reference is not a value. `sensitivity` is the one documented non-equal resolution: the header keeps the **stricter** class, so a stricter source value is promoted and a lower payload value can never downgrade it. Both the factory path (`create_event`/`publish`) and the manual `publish_event` path apply the same rule. The kernel adapter no longer mirrors the *source* event name into a payload `event_type` key |
| `MINOR-V6-001` | the "canonical ISO-8601" class validated text shape rather than civil time, so impossible months, days, hours and minutes (`9999-99-99T99:99Z`, `2026-02-31T12:00Z`, `2026-09-27T25:61Z`) reached durable evidence, as did a timezone-less `2026-09-27T12:00` despite the timezone-aware chronology contract | the existing shape rule is retained and the value must additionally parse as a real calendar/time value and carry an explicit UTC offset. The existing `datetime` and canonical serialization approach is reused — no second timestamp subsystem — and nothing is silently reinterpreted or normalized; an invalid value fails closed |

Numeric bound decision (explicit): one constant, the signed 64-bit
machine-integer range, rather than a per-field set of invented maxima. It is
nineteen decimal digits — far below every serializer and interpreter conversion
limit and far above every legitimate count, attempt, sequence, millisecond
duration or version this platform produces — so it is genuinely bounded without
being arbitrary. The per-key semantics table was chosen over a single "non-negative
number" rule because `ratio` is a normalized ratio in current usage while
`duration_ms` is an unbounded-in-principle (but now bounded) duration, and over
per-field maxima because a single machine-integer bound is easier to audit and
cannot drift per key.

Filesystem classifier decision (explicit): a bounded syntactic signature list, not
a ban on `/` or `:`. The audited reproduction proves the classification was
missing; the producer inventory proves legitimate references genuinely need those
characters (`workflow:123`, `domain:legal`, `provider/model`, `cmm.orchestration`,
`CORR-ORIGINAL`, `events:read`), and every one of them is asserted to still pass.
Banning every slash or colon was rejected as over-correction; performing real path
resolution or filesystem inspection was rejected because the frozen requirement is
about *public-safety of the token*, not about the host's filesystem.

Canonical header authority decision (explicit): the prompt's preferred design —
one authoritative representation — was implemented, not the equality-only
compatibility alternative. The consumed key set is the **intersection** with the
bounded payload vocabulary, so a payload key outside that vocabulary is still
rejected by the ordinary gate rather than becoming a new header channel and the
closed vocabulary stays closed. A non-equal `sensitivity` is the single documented
exception, because the frozen classification rule requires promotion of a stricter
source class rather than rejection. The alternative of simply deleting every
header-named payload key was rejected because it would silently discard a
legitimate identity fact; adopting an unset header field preserves the fact while
keeping one authority.

Timestamp decision (explicit): timezone-aware timestamps are **required** for
persisted platform lifecycle facts. No current producer publishes a legitimate
timezone-less platform timestamp, so no compatibility exception was needed and
none was added.

### 15.5 Remediation commits

```text
b18ca7b fix(events): bound numeric lifecycle facts and reject private filesystem paths
        (the V6 adversarial regression module, which reproduces all four findings
         first — initial red 90 failed / 37 passed — and the minimum fix)
89e7eba test(phase11): strengthen at-dp-122 for the v6 contract
        (the connected V6 acceptance scenarios and the four superseded V5 controls)
384454c docs(phase11): record phase11.22 remediation v6 pending reaudit
```

The four findings share one safety authority, one dispatch point and one
reconciliation path, so the reproduction suite and the minimum fix are committed
together rather than split into four artificially separated changes; the
strengthened acceptance and the superseded-control alignment follow as their own
test commit, and the documentation is recorded last. This is the prompt's
"coherent split" allowance.

No history was rewritten, no historical audit or remediation commit was squashed
and no bundle was overwritten. The three commits above are the complete
Remediation V6 delta from the committed prompt HEAD `8f1ed97`; the docs commit
cannot cite its own SHA for the same self-reference reason as the earlier
evidence records.

### 15.6 Production files changed

```text
cmm/events/event_payload_safety.py   +431/-8  explicit numeric bound and semantic
                                              table, syntactic private-filesystem
                                              classifier, canonical header fact
                                              vocabulary and reconciliation, and
                                              real civil-time validation
cmm/events/event_system.py            +69/-1  consumes canonical header facts on
                                              both the factory path and the manual
                                              publish_event path
cmm/events/kernel_adapter.py           +0/-1  stops mirroring the source event name
                                              into the payload `event_type` key
```

```text
tests/events/test_phase11_22_remediation_v6_regressions.py  NEW  +1157/-0
tests/events/test_phase11_22_dp122_acceptance.py                 +553/-2
tests/events/test_phase11_22_kernel_adapter.py                    +13/-2
tests/events/test_phase11_22_remediation_v5_regressions.py        +55/-4

ROADMAP.md                                                         +3/-3
docs/audits/phase-11.22-event-system-implementation-evidence.md  +376/-7
docs/reference/phase-11-event-system.md                          +260/-21
docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md  +16/-7
docs/roadmap/phase-11-stable-integrated-platform.md                +42/-2
```

No second bus, registry, repository protocol, replayer, DLQ, event contract,
safety-policy module, payload registry, numeric-policy registry, timestamp
subsystem, identity/sensitivity authority, application container, service locator,
broker abstraction or generic event-schema engine was introduced, and
`AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0` still holds.

### 15.7 New and strengthened adversarial regressions

```text
tests/events/test_phase11_22_remediation_v6_regressions.py   NEW, 127 tests
  MAJOR-V6-001  huge integer rejected by the official in-memory repository and by
                the official file-backed repository, repository-independent
                outcome for the same public event, negative count/attempts/
                sequence/duration in payload, structured reference and metadata,
                oversized finite float, oversized integer in metadata and nested
                metadata, count-like facts must be real integers, ratio outside
                [0,1], durable file untouched, retry_after_ms outside the bounded
                vocabulary, every numeric key has an explicit semantic bound
  MAJOR-V6-001 controls  count 0/1/bound, attempts, sequence, duration 0/125/1000/
                125.5, version 1/3, bounded metadata attempt/ratio/count
  MAJOR-V6-002  all six audited private locations rejected in payload identifiers,
                in a canonical header fact, in identifier-classified metadata, in
                permissions and in a manual event; durable bytes never contain
                ".ssh"
  MAJOR-V6-002 controls  eleven legitimate public references, every canonical
                header identifier channel
  MAJOR-V6-003  conflicting event_id/correlation_id/causation_id/producer/
                event_type/schema_version/occurred_at cannot persist, the exact
                audited five-fact conflict cannot persist, durable file untouched,
                no canonical header fact is persisted as a payload fact, an unset
                header fact is adopted once, stricter payload sensitivity is
                promoted, a lower payload sensitivity cannot downgrade the header,
                an equal duplicate is not persisted twice, manual `publish_event`
                conflict rejection and fold-in, durable reopen keeps one authority
  MAJOR-V6-003 controls  the consumed key set is exactly the header-named payload
                vocabulary, the real Domain bridge still maps source sensitivity to
                the canonical header
  MINOR-V6-001  invalid month/day/hour/minute/second rejected, timezone-ambiguous
                and date-only timestamps rejected, durable file untouched
  MINOR-V6-001 controls  UTC `Z`, `+02:00`, explicit `+00:00`, microseconds and a
                real leap day accepted

tests/events/test_phase11_22_dp122_acceptance.py    +53 connected scenarios (124 -> 177)
  huge numeric fact rejected before persistence, huge numeric fact identical across
  the two official repositories, negative/oversized numeric facts rejected with the
  durable file unchanged, negative metadata attempt rejected, legitimate bounded
  numeric and metadata facts persist, all six private locations rejected in payload
  and in the canonical header, legitimate references still accepted, payload/header
  conflict rejection for event_id/correlation_id/causation_id/producer/event_type/
  schema_version, canonical header facts never persisted twice, sensitivity never
  downgraded, real Domain bridge sensitivity still reaches the header, invalid civil
  timestamps rejected, timezone ambiguity rejected, valid timezone-aware timestamps
  accepted

tests/events/test_phase11_22_remediation_v5_regressions.py   1 control updated
tests/events/test_phase11_22_kernel_adapter.py               2 expectations updated
tests/events/test_phase11_22_dp122_acceptance.py             1 V5 control entry moved
  The V6 canonical-header authority rule supersedes four V5 *control* expectations
  that asserted a payload copy of a canonical header fact.  Each superseded
  expectation is preserved in stronger form: the same legitimate value is still
  exercised, the assertion now names the canonical header it reaches, and the
  conflicting case is proved to fail closed by the V6 adversarial suite.  The V5
  module count is unchanged at 71 (one parametrized control case relocated into a
  dedicated named control, so the module's gate count is preserved), and the fix
  each V5 finding proves — semantic buffer classification, lifecycle-fact value
  semantics, and fail-safe DLQ categorization — is untouched.
```

### 15.8 Gate evidence (Remediation V6)

```text
REMEDIATION_V6_TESTS=127 passed (initial red 90 failed / 37 passed)
V5_REGRESSIONS=71 passed (preserved)
V4_REGRESSIONS=23 passed (preserved)
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
PRIOR_REMEDIATION_REGRESSIONS=350 passed (V1-V5 preserved)
REMEDIATION_V1_TO_V6_REGRESSIONS=477 passed
PHASE_SUITE=tests/events/ 1271 passed
AT_DP_122=177 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_ACCEPTANCE=tests/domains/test_domain_events_dp033_acceptance.py 92 passed
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
CLOSED_PHASE_ACCEPTANCES=310 passed
  (AT-DP-102, AT-DP-103, AT-DP-105, Phase 11.21, Phase 11.34, AT-DP-150, AT-DP-033)
CLOSED_PHASE_SUPPORT=1077 passed
  (validation kernel events, orchestration suite, workflow subsystem)
ARCHITECTURE_AND_SECURITY_GATES=294 passed (part of tests/events/)
PHASE11_21_AND_11_34=106 passed
FOCUSED_COMBINED=17413 passed, 1 warning, 0 failed
  (tests/events + tests/orchestration + tests/domains + tests/agent_runtime +
   closed-phase acceptances)
GLOBAL_PYTEST=23340 passed, 1 warning, 0 failed
CHANGED_FILE_RUFF=PASS (0 violations in every changed/created file)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; V6 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS (changed and created files `ruff format --check`-clean; the six
  pre-existing changed files were format-clean at the audited HEAD, so no
  unrelated formatting churn was introduced)
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
ARCHITECTURE_GATES=PASS
SECURITY_GATES=PASS
```

The V5 production tree measured `1091` in `tests/events/` and `23160` globally. The
V6 additions are `+127` new adversarial regressions in a new module, `+53`
strengthened `AT-DP-122` connected scenarios and one relocated V5 control case
(which keeps the V5 module at `71` collected tests and removes no test). Both
deltas are therefore `+180` and they agree exactly: `tests/events/` moves
`1091 → 1271` and the global suite moves `23160 → 23340`. No previously passing
test was removed or weakened. `AT-DP-122` itself moves `124 → 177`. The
`GLOBAL_PYTEST_PASS_COUNT>=23160` requirement is met at `23340`.
`PRIOR_REMEDIATION_REGRESSIONS` is exactly `350`, byte-for-byte the figure the
independent Re-audit V6 reported.

The one retained global warning is the pre-existing unrelated `starlette` `anyio`
`DeprecationWarning`.

### 15.9 Mandatory invariant evidence

```text
NUMERIC_LIFECYCLE_FACTS_ARE_ACTUALLY_BOUNDED=PASS
NUMERIC_FACTS_REJECT_BEFORE_REPOSITORY_INTERACTION=PASS
IN_MEMORY_AND_FILE_REPOSITORY_PARITY=PASS
BOUND_MEANS_ACTUALLY_BOUNDED=PASS
OFFICIAL_REPOSITORY_PARITY=PASS
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
ONE_CANONICAL_HEADER_FACT_AUTHORITY=PASS
NO_CONFLICTING_HEADER_EQUIVALENT_PAYLOAD_FACTS=PASS
NO_HEADER_PAYLOAD_SENSITIVITY_CONFLICT=PASS
TIMESTAMP_SEMANTIC_VALIDITY=PASS
INVALID_CALENDAR_VALUES_REJECTED=PASS

BINARY_BUFFER_VALUES_FAIL_CLOSED=PASS (preserved)
RAW_USER_TEXT_CANNOT_BE_RELOCATED=PASS (preserved)
METADATA_IS_NOT_A_PROSE_SIDE_CHANNEL=PASS (preserved)
DLQ_SECRET_SAFETY_FAILS_SAFE_WITHOUT_EXTERNAL_BINDING=PASS (preserved)
RAW_EXCEPTION_MESSAGES_NEVER_ENTER_DLQ=PASS (preserved)
UNSAFE_EXCEPTION_CLASS_NAMES_NEVER_ENTER_DLQ=PASS (preserved)

CONTENT_BOUND_FINGERPRINT=PASS
SAME_ID_DIFFERENT_CONTENT_FAIL_CLOSED=PASS
TAMPER_DETECTION=PASS
UNSUPPORTED_SCHEMA_REJECTED_BEFORE_APPEND=PASS
SUPPORTED_SCHEMA_REOPEN_ROUNDTRIP=PASS
SAFE_NESTED_MAPPING_PUBLICATION=PASS
SAFE_NESTED_SEQUENCE_PUBLICATION=PASS
FILE_LIVE_AND_REOPENED_FACTS_MATCH=PASS
PUBLICATION_RESULT_ALIAS_ISOLATION=PASS
SUBSCRIBER_MUTATION_ISOLATION=PASS
REPOSITORY_SNAPSHOT_ISOLATION=PASS
MANUAL_SENSITIVITY_CANONICALIZATION=PASS
IN_MEMORY_AND_FILE_REPOSITORY_PARITY=PASS

REPLAY_DOES_NOT_REPERSIST=PASS
REPLAY_DEFAULT_DENY=PASS
TARGETED_DLQ_REPLAY=PASS
UNRELATED_SUBSCRIBER_CANNOT_RESOLVE_DLQ=PASS
DLQ_RETAINED_UNTIL_TARGET_SUCCESS=PASS
DETACHED_DLQ_INSPECTION_SNAPSHOTS=PASS
DIRECT_BUS_NEUTRAL_FALLBACK=PASS
COMPOSED_RUNTIME_ERROR_CATEGORY_REMAINS_USEFUL=PASS

AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
NO_SECOND_EVENT_AUTHORITY=PASS
```

### 15.10 Preserved evidence

The immutable Audit V1 report, the immutable Re-audit V2, V3, V4, V5 and V6
reports, and the immutable V1, V2, V3, V4, V5 and V6 bundles are byte-identical to
their audited state. All six bundles remain untracked, as repository policy does
not track audit bundles. The quarantine stash state was preserved; no stash was
created, inspected destructively, applied, popped or dropped, and no bundle was
overwritten.

### 15.11 Next step

Fresh independent ChatGPT re-audit of the **V7** exact-HEAD bundle
(`phase-11.22-event-system-audit-v7.tar.gz`). The phase remains
`REMEDIATED_AFTER_REAUDIT_V6_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete, and neither Phase 11.23 nor Phase 11.24 has
begun. Only that re-audit may write `BLOCKERS=0`, `MAJORS=0`,
`DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`, `CLOSURE_ELIGIBLE=YES`.

---

## 16. Remediation V7

### 16.1 Verdict being remediated

Independent Re-audit V7
(`docs/audits/phase-11.22-event-system-independent-reaudit-v7.md`, immutable,
`BUNDLE_INTEGRITY=PASS`, `EXACT_HEAD=PASS`, `EXACT_TREE=PASS`) returned:

```text
INDEPENDENT_REAUDIT_V7=FAIL
V6_CONCRETE_FINDINGS_FIXED=4/4_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=477_PASS
BLOCKERS=0
MAJORS=2
MINORS=0
MAJOR_V7_001=RELATIVE_PATH_TRAVERSAL_AND_SENSITIVE_FILESYSTEM_REFERENCES_BYPASS_PATH_SAFETY
MAJOR_V7_002=URI_USERINFO_CREDENTIALS_CAN_ENTER_PERSISTED_IDENTIFIER_FIELDS
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V7_ONLY
```

Re-audit V7 verified all four V6 findings fixed (`4/4_VERIFIED`) and preserved
`477` prior remediation regressions. Phase 11.22 remains open. Phase 11.23 and
Phase 11.24 must not begin.

### 16.2 Exact start state

```text
BRANCH=feature/phase-11-stable-integrated-platform
PROMPT_COMMIT_HEAD=a72abf4c1022465955c5e0d3aebc0ae2d4bf02c1
REAUDIT_V7_COMMIT=c0f4fb226f3c4a1fb7dcaf88b333ccda07144a5c
REAUDIT_V7_TREE=f7959aacaff9ae73c5715f5900d369cca6588314
AUDITED_V7_IMPLEMENTATION_HEAD=8caa4b922f674fd5ef4a3452c2a55ddaad13ca8d
AUDITED_V7_IMPLEMENTATION_TREE=b3dd2d510a1f3b0daae075ae6e56652f3432c521
TRACKED_DELTA_FROM_REAUDIT_V7=docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v7-agent-prompt.md
PRODUCTION_CODE_DELTA_FROM_REAUDIT_V7=0
TRACKED_WORKTREE=CLEAN
GIT_DIFF_CHECK=PASS
QUARANTINE_STASH=NOT_MUTATED (no stash entry created, applied, popped or dropped)
HISTORICAL_BUNDLE_HASHES=EXACT (all seven re-hashed from the working tree)
  V1=a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3
  V2=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04
  V3=27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589
  V4=18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f
  V5=105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10
  V6=67b27f6effa5297757453aba3021a7211fe4ee88e194a6d65eefa353060f1008
  V7=c388ea63ba885e415703ab771174f3413276092bf65358142b8e3a0c1c4bfe01
```

All seven bundles were re-hashed from the working tree and matched the declared
values exactly. Preflight passed before any production mutation; no `reset`,
`stash`, `clean`, `worktree`, `merge` or `push` operation was used, and no
historical audit report or bundle was modified.

### 16.3 TDD red evidence

Before any production change,
`tests/events/test_phase11_22_remediation_v7_regressions.py` was written to
reproduce both findings and its red state was recorded:

```text
REMEDIATION_V7_TESTS_INITIAL_RED=89 failed, 37 passed (126 collected)

  MAJOR-V7-001 relative traversal          ~44 failed
  MAJOR-V7-002 URI userinfo credentials    ~43 failed
  architecture guard / controls             37 passed
```

Every failure was a genuine reproducer, not a helper artefact. The audited
behaviours were independently re-observed against the unmodified start state
before the fix, exactly as the re-audit reported them:

```text
payload.request_id="safe/../../etc/shadow"                 ACCEPTED persisted=True count=1
producer="safe/../../etc/shadow"                           ACCEPTED persisted=True count=1
metadata.error_type="safe/../../etc/shadow"                ACCEPTED persisted=True count=1
permissions=["safe/../../etc/shadow"]                      ACCEPTED persisted=True count=1
result_reference.reference_id="safe/../../etc/shadow"      ACCEPTED persisted=True count=1
payload.request_id="foo/../bar/../../private/var"          ACCEPTED persisted=True count=1

payload.request_id="https://admin:hunter2hunter2@example.com/path"   ACCEPTED persisted=True count=1
producer="https://admin:hunter2hunter2@example.com/path"             ACCEPTED persisted=True count=1
payload.request_id="postgres://alice:supersecret@example.com/db"     ACCEPTED persisted=True count=1
producer="postgres://alice:supersecret@example.com/db"               ACCEPTED persisted=True count=1
```

Legitimate controls were confirmed accepted at the same start state, so the
red run separated the defect from the contract:
`workflow:123`, `domain:legal`, `provider/model`, `cmm.orchestration`,
`events:read`, `https://example.com/model`, `postgres://example.com/db`.

The red run also exposed a scope boundary that the V7 record states explicitly:
the identifier character set does not admit `%`, so a *percent-encoded* userinfo
was already refused through the identifier channels — but for the character-set
reason, not for the semantic reason. The V7 rule therefore decodes the userinfo
before the colon test and a dedicated regression proves the decoded-form
detection itself, so the semantic protection does not depend on the character
set staying as narrow as it is today.

### 16.4 Findings and remediation

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V7-001` | the V6 path classifier recognized strong *absolute* filesystem signatures but had no traversal-segment rule and no relative private-system-root signature. A producer reached a sensitive relative location merely by prefixing it with an apparently safe identifier segment: `safe/../../etc/shadow` and `foo/../bar/../../private/var` qualified as identifiers and were durably persisted through every shared identifier channel — payload identifiers, `header.producer`, `metadata.error_type`, `header.permissions[]` and nested structured references | the **existing** `_PRIVATE_FILESYSTEM_PATTERNS` classifier in the **existing** safety authority gains three patterns: a syntactic `..` traversal segment delimited by `/` or `\` (or bounding the whole token), a known sensitive system file in relative form (`etc/shadow`, `etc/passwd`, `etc/sudoers` — which also refuses the network spelling `nfs://server/etc/shadow`), and the macOS private system roots in relative form (`private/var`, `private/etc`, `private/tmp`, `private/root`). The rule matches the traversal *segment*, never a naive `".." in value` substring, so `cmm.orchestration`, `v1..2` and `provider/model` stay valid. It performs no filesystem I/O, resolves no host path and inspects no file. No second path-policy module was created |
| `MAJOR-V7-002` | the identifier grammar deliberately admits `:`, `/` and `@` because legitimate references need them, but the composed credential scanner recognized only token formats and explicit secret markers — not URI userinfo password *structure*. `https://admin:hunter2hunter2@example.com/path` and `postgres://alice:supersecret@example.com/db` therefore qualified as safe identifiers and were durably persisted, against the frozen rule that credentials never enter event persistence | one narrow `contains_uri_userinfo_credential()` check in the **existing** authority. It requires a real scheme, a `//` authority, userinfo terminated by `@`, and a colon inside that userinfo with a non-empty password component. The userinfo is percent-decoded (`urllib.parse.unquote`) before the colon test, so an encoded `%3A` that decodes to a password separator is refused as the same credential. Credential-free URIs (`https://example.com/model`, `postgres://example.com/db`) and bare-username userinfo are preserved. The function returns a boolean and the caller's rejection message is a static literal, so the refused secret is never echoed into a log, an error or a DLQ record. No second credential policy was created |

Traversal rule decision (explicit): the rule is segment-based, because a naive
substring test would refuse legitimate dotted references such as
`cmm.orchestration`. Both separator characters are accepted in any mix: the
identifier grammar only admits `/`, but a Windows spelling is a filesystem path
semantic too, and three of the audited traversal spellings are only refused by
the character set today — the classifier now refuses the segment itself, so the
protection does not depend on that coincidence. Real path resolution and
filesystem inspection were rejected for the same reason as in V6: the frozen
requirement is about the *public-safety of the token*, not about the host's
filesystem, and performing I/O at the event boundary would be both slower and
host-dependent.

URI userinfo rule decision (explicit): the check is structural, not
secret-guessing. The URI grammar itself names the component after the `:`;
requiring a non-empty password component and not requiring a non-empty username
refuses `https://:secret@example.com/db` (a password is still a password) while
leaving `https://alice@example.com/db` and `https://alice:@example.com/db`
valid. Percent-decoding before the colon test was chosen over raw-text matching
because the *semantic* content is what the invariant is about.
`urllib.parse` is used as an implementation detail inside the existing authority,
not as a new policy surface.

### 16.5 Remediation commits

```text
cec2b71 test(phase11): reproduce phase11.22 reaudit v7 findings
        (the V7 adversarial regression module, which reproduces both findings
         first — initial red 89 failed / 37 passed)
06c7903 fix(events): reject traversal and uri-userinfo credentials
        (the minimum fix, in the existing identifier/path safety authority)
dd5b3be test(phase11): strengthen at-dp-122 for v7 identifier safety
        (the connected V7 acceptance scenarios)
<docs>  docs(phase11): record phase11.22 remediation v7 pending reaudit
```

Both findings share one safety authority and one dispatch point, so the
reproduction suite and the minimum fix are committed as the prompt's suggested
two-step sequence; the strengthened acceptance follows as its own test commit and
the documentation is recorded last. This is the prompt's "coherent split"
allowance. No history was rewritten, no historical audit or remediation commit
was squashed and no bundle was overwritten. The docs commit cannot cite its own
SHA for the same self-reference reason as the earlier evidence records.

### 16.6 Production files changed

```text
cmm/events/event_payload_safety.py   +95/-9   traversal-segment, relative
                                              sensitive-system-path and URI
                                              userinfo credential rules in the
                                              one existing identifier/path safety
                                              authority
```

```text
tests/events/test_phase11_22_remediation_v7_regressions.py  NEW  +889/-0
tests/events/test_phase11_22_dp122_acceptance.py                 +345/-0
```

No second bus, registry, repository protocol, replayer, DLQ, event contract,
safety-policy module, path-policy module, credential-policy module, payload
registry, numeric-policy registry, timestamp subsystem, identity/sensitivity
authority, application container, service locator, broker abstraction or generic
event-schema engine was introduced, and `AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0`
still holds.

### 16.7 New and strengthened adversarial regressions

```text
tests/events/test_phase11_22_remediation_v7_regressions.py   NEW, 127 tests
  MAJOR-V7-001  safe/../../etc/shadow and foo/../bar/../../private/var rejected
                in the payload identifier, in the header producer, in an
                identifier-classified metadata fact, in permissions, in a nested
                structured reference, in a reference sequence and in a structured
                reference sequence; backslash, mixed-separator, trailing and
                relative-private-root spellings rejected; a manual event applies
                the same rule; the durable file is never created or appended and
                never contains ".."; the file-backed repository is not the safety
                boundary; one enumerable test drives all thirteen shared channels
  MAJOR-V7-001 controls  eleven legitimate public references persist with the
                exact value, every canonical header identifier channel keeps its
                real reference, and a bare separator (provider/model,
                cmm/orchestration/step) is not traversal
  MAJOR-V7-002  both audited URI userinfo credentials rejected in the payload
                identifier, in the header producer, in an identifier-classified
                metadata fact, in permissions, in a nested structured reference
                and in a reference sequence; percent-encoded userinfo rejected;
                the semantic decoded-form rule proved directly; a manual event
                applies the same rule; the durable file is never created or
                appended and never contains the audited passwords; the
                file-backed repository is not the safety boundary; the rejection
                message never echoes the secret; one enumerable test drives all
                thirteen shared channels
  MAJOR-V7-002 controls  credential-free URIs (https://example.com/model,
                postgres://example.com/db, http://localhost:8080/health,
                urn:cmm:event:message.received, mailto:ops@example.com) and the
                legitimate references persist unchanged; bare-username userinfo is
                not a credential
  architecture guards  the one shared authority is the point of enforcement for
                both rules, the public path classifier reports traversal, and no
                event_path_policy.py / event_credential_policy.py /
                identifier_policy.py module was added

tests/events/test_phase11_22_dp122_acceptance.py    +73 connected scenarios (177 -> 250)
  traversal and URI userinfo refused on every shared persisted identifier channel
  (payload identifier, payload workflow_id, payload aggregate_id, payload
  producer, header producer, header aggregate_id, header correlation_id,
  header source, permissions, metadata error_type, nested result reference,
  structured reference sequence, domain reference sequence); the real durable
  store is never created or appended and no audited secret appears in it; the
  real production PlatformOrchestrationEventSink refuses both shapes before
  persistence; the real Orchestrator's mandatory emission fails closed with
  ORCHESTRATION_EVENT_EMISSION_FAILED and leaves zero durable evidence rather
  than dropping the fact silently; the refusal message never echoes the secret;
  legitimate references and credential-free URIs still persist and reopen
  fingerprint-equal; the frozen V6 absolute-path rules are retained alongside
  the new relative rule
```

### 16.8 Gate evidence (Remediation V7)

```text
REMEDIATION_V7_TESTS=127 passed (initial red 89 failed / 37 passed)
V6_REGRESSIONS=127 passed (preserved)
V5_REGRESSIONS=71 passed (preserved)
V4_REGRESSIONS=23 passed (preserved)
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
PRIOR_REMEDIATION_REGRESSIONS=477 passed (V1-V6 preserved)
REMEDIATION_V1_TO_V7_REGRESSIONS=604 passed
PHASE_SUITE=tests/events/ 1471 passed
AT_DP_122=250 passed (177 prior + 73 V7)
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_ACCEPTANCE=tests/domains/test_domain_events_dp033_acceptance.py 92 passed
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
CLOSED_PHASE_ACCEPTANCES=310 passed, 1 warning
  (AT-DP-102, AT-DP-103, AT-DP-105, Phase 11.21, Phase 11.34, AT-DP-150, AT-DP-033)
CLOSED_PHASE_SUPPORT=1077 passed
  (validation kernel events, orchestration suite, workflow subsystem)
ORCHESTRATION_EVENT_TESTS=tests/orchestration/ 498 passed
PHASE11_21_AND_11_34=106 passed
ARCHITECTURE_AND_SECURITY_GATES=294 passed (part of tests/events/)
GLOBAL_PYTEST=23540 passed, 1 warning, 0 failed (V7 baseline 23340, +200)
CHANGED_FILE_RUFF=PASS (0 violations in every changed/created file)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; V7 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
ARCHITECTURE_GATES=PASS
SECURITY_GATES=PASS
```

The V7 production tree measured `1271` in `tests/events/` and `23340` globally.
The V7 additions are `+127` new adversarial regressions in a new module and `+73`
strengthened `AT-DP-122` connected scenarios. Both deltas are therefore `+200` and
they agree exactly: `tests/events/` moves `1271 -> 1471` and the global suite
moves `23340 -> 23540`. No previously passing test was removed or weakened.
`AT-DP-122` itself moves `177 -> 250`. The `GLOBAL_PYTEST_PASS_COUNT>=23340`
requirement is met at `23540`, and `GLOBAL_PYTEST_FAILURES=0`.
`PRIOR_REMEDIATION_REGRESSIONS` is exactly `477`, byte-for-byte the figure the
independent Re-audit V7 reported.

The one retained global warning is the pre-existing unrelated `starlette` `anyio`
`DeprecationWarning`.

### 16.9 Mandatory invariant evidence

```text
RELATIVE_PATH_TRAVERSAL_REJECTED_BEFORE_PERSISTENCE=PASS
URI_USERINFO_CREDENTIALS_REJECTED_BEFORE_PERSISTENCE=PASS
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE=PASS

ABSOLUTE_HOME_FILESYSTEM_PATH_REJECTION=PASS (preserved, V6)
NUMERIC_LIFECYCLE_FACTS_ARE_ACTUALLY_BOUNDED=PASS (preserved, V6)
OFFICIAL_REPOSITORY_PARITY=PASS (preserved, V6)
ONE_CANONICAL_HEADER_FACT_AUTHORITY=PASS (preserved, V6)
TIMESTAMP_SEMANTIC_VALIDITY=PASS (preserved, V6)
BINARY_BUFFER_VALUES_FAIL_CLOSED=PASS (preserved, V5)
RAW_USER_TEXT_CANNOT_BE_RELOCATED=PASS (preserved, V5)
METADATA_IS_NOT_A_PROSE_SIDE_CHANNEL=PASS (preserved, V5)
DLQ_SECRET_SAFETY_FAILS_SAFE_WITHOUT_EXTERNAL_BINDING=PASS (preserved, V5)
RAW_EXCEPTION_MESSAGES_NEVER_ENTER_DLQ=PASS (preserved, V4)
UNSAFE_EXCEPTION_CLASS_NAMES_NEVER_ENTER_DLQ=PASS (preserved, V4)
CONTENT_BOUND_FINGERPRINT=PASS (preserved, V1-V3)
SAME_ID_DIFFERENT_CONTENT_FAIL_CLOSED=PASS (preserved, V1-V3)
TAMPER_DETECTION=PASS (preserved, V1-V3)
UNSUPPORTED_SCHEMA_REJECTED_BEFORE_APPEND=PASS (preserved, V1-V3)
SUPPORTED_SCHEMA_REOPEN_ROUNDTRIP=PASS (preserved, V1-V3)
PUBLICATION_RESULT_ALIAS_ISOLATION=PASS (preserved, V1-V3)
SUBSCRIBER_MUTATION_ISOLATION=PASS (preserved, V1-V3)
REPOSITORY_SNAPSHOT_ISOLATION=PASS (preserved, V1-V3)
MANUAL_SENSITIVITY_CANONICALIZATION=PASS (preserved, V1-V3)
REPLAY_DOES_NOT_REPERSIST=PASS (preserved, V1-V3)
REPLAY_DEFAULT_DENY=PASS (preserved, V1-V3)
TARGETED_DLQ_REPLAY=PASS (preserved, V1-V3)
UNRELATED_SUBSCRIBER_CANNOT_RESOLVE_DLQ=PASS (preserved, V1-V3)
DLQ_RETAINED_UNTIL_TARGET_SUCCESS=PASS (preserved, V1-V3)
DETACHED_DLQ_INSPECTION_SNAPSHOTS=PASS (preserved, V1-V3)
DIRECT_BUS_NEUTRAL_FALLBACK=PASS (preserved, V1-V3)

AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
NO_SECOND_EVENT_AUTHORITY=PASS
NO_SECOND_PATH_POLICY_MODULE=PASS
NO_SECOND_CREDENTIAL_POLICY=PASS
```

### 16.10 Preserved evidence

The immutable Audit V1 report, the immutable Re-audit V2, V3, V4, V5, V6 and V7
reports, and the immutable V1, V2, V3, V4, V5, V6 and V7 bundles are byte-identical
to their audited state. All seven bundles remain untracked, as repository policy
does not track audit bundles. The quarantine stash state was preserved; no stash
was created, applied, popped or dropped, and no bundle was overwritten.

### 16.11 Next step

Fresh independent ChatGPT re-audit of the **V8** exact-HEAD bundle
(`phase-11.22-event-system-audit-v8.tar.gz`). The phase remains
`REMEDIATED_AFTER_REAUDIT_V7_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete, and neither Phase 11.23 nor Phase 11.24 has
begun. Only that re-audit may write `BLOCKERS=0`, `MAJORS=0`,
`DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`, `CLOSURE_ELIGIBLE=YES`.

---

## 17. Remediation V8

### 17.1 Verdict being remediated

Independent Re-audit V8
(`docs/audits/phase-11.22-event-system-independent-reaudit-v8.md`, immutable,
`BUNDLE_INTEGRITY=PASS`, `EXACT_HEAD=PASS`, `EXACT_TREE=PASS`) returned:

```text
INDEPENDENT_REAUDIT_V8=FAIL
V7_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=604_PASS
BLOCKERS=0
MAJORS=2
MINORS=1
MAJOR_V8_001=FILESYSTEM_REFERENCE_CLASSIFIER_STILL_ACCEPTS_PATH_EQUIVALENTS_AND_UNLISTED_SENSITIVE_PATHS
MAJOR_V8_002=WRAPPED_OR_NESTED_URI_USERINFO_CREDENTIALS_BYPASS_IDENTIFIER_SAFETY
MINOR_V8_001=ROADMAP_PHASE11_SUMMARY_OMITS_REAUDIT_V7
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V8_ONLY
```

Re-audit V8 verified both V7 findings fixed (`2/2_VERIFIED`) and preserved `604`
prior remediation regressions. Phase 11.22 remains open. Phase 11.23 and Phase
11.24 must not begin.

### 17.2 Exact start state

```text
BRANCH=feature/phase-11-stable-integrated-platform
PROMPT_COMMIT_HEAD=2f94f7482a05df75187b5ff7bc4c6d8710fe292a
PROMPT_COMMIT_TREE=0c17ff11b8f0ac8010c6e4da37a13a5491880bd0
REAUDIT_V8_COMMIT=93a1a7633cdc5a72e90e75bc885c2216f62294e5
REAUDIT_V8_TREE=ec23545398486261b0bbd3f8463782e22c6d8fe8
AUDITED_V8_IMPLEMENTATION_HEAD=aadf83c44104beb096811219bc330e6e613cb18d
AUDITED_V8_IMPLEMENTATION_TREE=d383ba1fb0b68bbade0d91a58f0ae5db36609a3f
REAUDIT_V8_REPORT_SHA256=a91ff62e19a62e2b787ad5f8c68df92c65ee9a8d8947f9122453aa3bf0da64e6
TRACKED_DELTA_FROM_REAUDIT_V8=docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v8-agent-prompt.md
PRODUCTION_CODE_DELTA_FROM_REAUDIT_V8=0
TRACKED_WORKTREE=CLEAN
GIT_DIFF_CHECK=PASS
QUARANTINE_STASH=NOT_MUTATED (no stash entry created, applied, popped or dropped; the stash list is unchanged)
HISTORICAL_BUNDLE_HASHES=EXACT (V1..V8 re-hashed from the working tree)
  V1=a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3
  V2=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04
  V3=27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589
  V4=18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f
  V5=105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10
  V6=67b27f6effa5297757453aba3021a7211fe4ee88e194a6d65eefa353060f1008
  V7=c388ea63ba885e415703ab771174f3413276092bf65358142b8e3a0c1c4bfe01
  V8=9b46ed3f941ce63c8ff2249da5762fcfe0f156f073c9864f39d3dffdac3708e9
HISTORICAL_AUDIT_REPORT_HASHES=EXACT (V1..V8 re-hashed; all match the declared values)
```

The eight historical bundles were re-hashed from the working tree and matched the
declared values exactly, and the eight audit reports were re-hashed and matched the
values the V8 re-audit itself declared. Preflight passed before any production
mutation; no `reset`, `stash`, `clean`, `worktree`, `merge` or `push` operation was
used, and no historical audit report or bundle was modified.

### 17.3 TDD red evidence

Before any production change,
`tests/events/test_phase11_22_remediation_v8_regressions.py` was written to
reproduce all three findings and its red state was recorded:

```text
REMEDIATION_V8_TESTS_INITIAL_RED=234 failed, 47 passed (281 collected)

  MAJOR-V8-001 path-equivalent spellings       ~104 failed
  MAJOR-V8-001 strong non-public paths         ~104 failed
  MAJOR-V8-002 wrapped URI userinfo            ~52 failed
  helper / architecture guard / controls         47 passed
```

Every failure was a genuine reproducer, not a helper artefact. The `47` passing
tests were exactly the intended controls: the legitimate references and
credential-free URIs, the credentials-free wrapped URIs, the "the classifier never
rewrites the persisted identifier" control, the preserved V6/V7 refusals and the
architecture guard. The audited behaviours were independently re-observed against
the unmodified start state before the fix, exactly as the re-audit reported them:

```text
payload.request_id="safe/etc//shadow"                      ACCEPTED persisted=True count=1
payload.request_id="safe/etc/./shadow"                     ACCEPTED persisted=True count=1
payload.request_id="safe/private//var/db/keychains"         ACCEPTED persisted=True count=1
payload.request_id="safe/private/./var/db/keychains"        ACCEPTED persisted=True count=1
payload.request_id="proc/self/environ"                     ACCEPTED persisted=True count=1
payload.request_id="etc/ssh/ssh_host_rsa_key"              ACCEPTED persisted=True count=1
payload.request_id="Windows/System32/config/SAM"           ACCEPTED persisted=True count=1
payload.request_id="Library/Keychains/login.keychain-db"   ACCEPTED persisted=True count=1

payload.request_id="jdbc:postgresql://alice:supersecret@example.com/db"  ACCEPTED persisted=True count=1
payload.request_id="jdbc:mysql://root:hunter2hunter2@example.com/db"     ACCEPTED persisted=True count=1
producer="provider/https://alice:supersecret@example.com/db"             ACCEPTED persisted=True count=1
provider="foo:https://alice:supersecret@example.com/db"                  ACCEPTED persisted=True count=1
```

The red run also proved the *classification* defect directly rather than only by
example — the pre-fix classifier returned **different** answers for lexically
equivalent spellings of one location:

```text
etc/shadow                     REJECTED (filesystem=True)
etc//shadow                    ACCEPTED (filesystem=False)   <- same location
etc/./shadow                   ACCEPTED (filesystem=False)   <- same location
ETC/SHADOW                     REJECTED (filesystem=True)
Etc/./Shadow                   ACCEPTED (filesystem=False)   <- same location
private/var/db/keychains       REJECTED (filesystem=True)
private//var/db/keychains      ACCEPTED (filesystem=False)   <- same location
private/./var/db/keychains     ACCEPTED (filesystem=False)   <- same location
```

Legitimate controls were confirmed accepted at the same start state, so the red run
separated the defect from the contract: `workflow:123`, `domain:legal`,
`provider/model`, `cmm.orchestration`, `events:read`,
`https://example.com/model`, `postgres://example.com/db`,
`http://localhost:8080/health`, `urn:cmm:event:message.received`,
`mailto:ops@example.com`, `cmm/orchestration/step` and the credential-free wrapped
URIs `jdbc:postgresql://example.com/db` and `provider/https://example.com/db`.

A fifth family was found by follow-up adversarial review during this remediation
rather than by the re-audit: a non-public path that merely *contains* an authority
marker (`proc/self/environ://x`, `etc/shadow://x`,
`Windows/System32/config/SAM://x`) was initially exempted for "being a URI". Under
POSIX path semantics `a://x` names `a/x`, so those are path-equivalent spellings of
a non-public location. Eight further tests were written first and were
independently red (`8 failed`) before the residue rule below closed them.

### 17.4 Findings and remediation

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V8-001` | the V6/V7 classifier matched the **raw identifier text**, so it was a list of selected spellings rather than a classification. Lexically equivalent forms of one location disagreed — `etc/shadow` was refused while `etc//shadow` and `etc/./shadow` were durably persisted, `private/var/db/keychains` was refused while `safe/private/./var/db/keychains` was persisted — and unmistakable system locations no pattern named (`proc/self/environ`, `etc/ssh/ssh_host_rsa_key`, `Windows/System32/config/SAM`, `Library/Keychains/login.keychain-db`) were durably persisted through every shared identifier channel | one **pure lexical canonical analysis form** — `_analyze_lexical_path()` normalizes `\`/`/` to one separator, collapses repeated separators, elides `.` segments and *detects* `..` before any elision, performs no I/O, calls no `Path.resolve()` and never mutates the persisted value — plus a **fail-closed public-reference allowlist**. The retained V6/V7 pattern tuple is unchanged in content and is now evaluated against the canonical form. A slash-bearing reference is public-safe only when the path-shaped **residue** left after removing every authority-bearing URI reference is empty or is rooted in a declared public logical namespace. `PUBLIC_SLASH_REFERENCE_ROOTS = {cmm, provider}` is the complete set a real inventory of every identifier value the whole suite routes through this authority found in use (`provider/model`, `cmm/orchestration/step`). Every other slash-bearing spelling fails closed, so an unlisted local/system path cannot enter persistence because no pattern was appended for it — and a `://` cannot launder one, because the residue is classified too |
| `MAJOR-V8-002` | the V7 userinfo rule recognized a password-bearing authority only when the URI began at character zero, so `jdbc:postgresql://alice:supersecret@example.com/db`, `jdbc:mysql://root:hunter2hunter2@example.com/db`, `provider/https://alice:supersecret@example.com/db` and `foo:https://alice:supersecret@example.com/db` qualified as safe identifiers and were durably persisted | the same `contains_uri_userinfo_credential()` check made **occurrence-independent**: every authority-bearing `://` occurrence is visited, each authority is split at its last `@`, the userinfo is percent-decoded and split at the first `:`, and a non-empty password component refuses the reference. A password appearing only in a *later* authority is seen. Credential-free URIs, credential-free wrapped URIs, bare-username userinfo and an empty password stay valid. Returns a boolean; the rejection message is a static literal, so the secret is never echoed. No second credential policy |
| `MINOR-V8-001` | the high-level Phase 11 row in `ROADMAP.md` summarized the Phase 11.22 audit history only through Re-audit V6 and "all six", contradicting the detailed Phase 11.22 line, the detailed Phase 11 roadmap, the requirements matrix, the implementation evidence and the committed immutable V7 re-audit report | the high-level row now states Re-audits `V2/V3/V4/V5/V6/V7` and "was remediated after all seven", and additionally records the Re-audit V8 failure and the Remediation V8 state. The detailed Phase 11.22 line, the detailed Phase 11 roadmap, the requirements matrix and the reference document were brought to the same V8 state. No historical audit artifact was rewritten |

Lexical path algorithm (exact):

```text
1. normalized = value.replace("\\", "/")
2. raw_segments = normalized.split("/")
3. has_traversal = any(segment == ".." for segment in raw_segments)   # BEFORE elision
4. is_absolute   = normalized.startswith("/")
5. segments      = [s for s in raw_segments if s not in ("", ".")]     # collapse + elide
6. canonical     = ("/" if is_absolute else "") + "/".join(segments)
7. schemes       = every [A-Za-z][A-Za-z0-9+.\-]* scheme of a "scheme://authority"
                   occurrence in the ORIGINAL value, lowercased
```

Classification order (exact):

```text
has_traversal or is_absolute                                      -> reject
any retained V6/V7 pattern matches `canonical`                    -> reject
any scheme == "file"                                              -> reject
masked = value with every "scheme://…" URI reference removed
if masked carries no separator                                    -> accept (a URI reference, or not path-shaped)
residue = lexical analysis of masked
root = first residue segment (lowercased)
root in PUBLIC_SLASH_REFERENCE_ROOTS                              -> accept
otherwise                                                         -> reject
```

Actual public-safe slash-bearing forms retained, established by a **real
inventory** rather than by assumption. Two independent inventories were run:

```text
dynamic   all 1223 distinct identifier values the full test suite routes through
          validate_platform_identifier(), capturing accept/reject per value
static    an AST scan of every `cmm/**/*.py` for slash-bearing string literals
          assigned to any identifier-class channel
```

The dynamic inventory found exactly five accepted slash-bearing values —
`provider/model`, `cmm/orchestration/step`, `https://example.com/model`,
`postgres://example.com/db`, `http://localhost:8080/health` — and the static
inventory found **zero** slash-bearing identifier literals in the production
package. The retained public-safe classes are therefore exactly: credential-free
authority-bearing URI references (plus credential-free wrapped URIs such as
`jdbc:postgresql://example.com/db`, which the identifier grammar already admitted
and which stay accepted), and logical references rooted in `cmm` or `provider`.

URI authority scanning algorithm (exact):

```text
1. pattern  = (?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*)://(?P<authority>[^/?#]*)
2. finditer over the value: EVERY occurrence is inspected, not only offset zero
3. userinfo, sep, host = authority.rpartition("@")
4. no "@" -> not userinfo, continue to the next occurrence
5. name, password_sep, secret = unquote(userinfo).partition(":")
6. password_sep and secret -> the reference is credential material -> reject
```

Percent-decoding behaviour: the userinfo is `urllib.parse.unquote`-decoded before
the colon test, so `jdbc:postgresql://alice%3Asupersecret@example.com/db` and
`provider/https://alice%3Asupersecret@example.com/db` are refused as the same
credential rather than trusted because the raw text has no literal colon. The outer
identifier grammar excludes `%`, so those spellings never reach persistence through
the identifier channels — that is a defence, not the rule, and a helper-level
regression keeps the semantic detection itself proven independently of the
character set. `https://alice%40example.com/db` (an encoded `@`, no password)
stays credential-free.

ROADMAP correction (exact): `ROADMAP.md` line 69 now reads "11.22 Event System
failed Independent Audit V1 and Re-audits V2/V3/V4/V5/V6/V7, was remediated after
all seven, then failed Re-audit V8 and is remediated after it pending independent
re-audit (`AT_DP_122=PASS_REPORTED`, `CLOSURE_ELIGIBLE=NO`)". The detailed Phase
11.22 line, the detailed Phase 11 roadmap, the requirements matrix, this evidence
record and `docs/reference/phase-11-event-system.md` all carry the V8 state.

### 17.5 Remediation commits

```text
2b92d6f test(phase11): reproduce phase11.22 reaudit v8 findings
        (the V8 adversarial regression module, which reproduces all three
         findings first — initial red 234 failed / 47 passed on the 281-case
         module, plus 8 independently red URI-suffix residue reproductions)
334c5bc fix(events): harden canonical identifier filesystem and uri safety
        (the minimum fix, in the existing identifier/path/credential authority)
4460ba3 test(phase11): strengthen at-dp-122 for v8 identifier safety
        (the connected V8 acceptance scenarios)
<docs>  docs(phase11): record phase11.22 remediation v8 pending reaudit
```

Both production findings share one safety authority and one dispatch point, so the
reproduction suite and the minimum fix are committed as the prompt's suggested
two-step sequence; the strengthened acceptance follows as its own test commit and
the documentation is recorded last. This is the prompt's "coherent split"
allowance. No history was rewritten, no historical audit or remediation commit was
squashed and no bundle was overwritten. The docs commit cannot cite its own SHA for
the same self-reference reason as the earlier evidence records.

### 17.6 Production files changed

```text
cmm/events/event_payload_safety.py   +193/-58  the one existing identifier/path
                                               safety authority gains a pure
                                               lexical canonical analysis form,
                                               a fail-closed public-reference
                                               allowlist with residue
                                               classification, and an
                                               occurrence-independent URI userinfo
                                               credential rule
```

```text
tests/events/test_phase11_22_remediation_v8_regressions.py  NEW  +1290/-0 (289 tests)
tests/events/test_phase11_22_dp122_acceptance.py                 +520/-0  (237 connected scenarios)
```

No second bus, registry, repository protocol, replayer, DLQ, event contract,
safety-policy module, path-policy module, credential-policy module, URI registry,
path-canonicalization module, identifier subsystem, payload registry,
numeric-policy registry, timestamp subsystem, identity/sensitivity authority,
application container, service locator, broker abstraction or generic event-schema
engine was introduced, and `AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0` still holds.

### 17.7 New and strengthened adversarial regressions

```text
tests/events/test_phase11_22_remediation_v8_regressions.py   NEW, 289 tests
  MAJOR-V8-001  safe/etc//shadow, safe/etc/./shadow, safe/private//var/db/keychains
                and safe/private/./var/db/keychains rejected in the payload
                identifier, in the header producer, in an identifier-classified
                metadata fact, in permissions, in a nested structured reference, in
                a reference sequence and in a structured reference sequence; the
                four strong V8 probes rejected; one enumerable test drives all
                thirteen shared channels for both families; the durable file is
                never created or appended and never contains "shadow", "keychain",
                "environ", "SAM" or "host_rsa"; a manual event applies the same rule
  MAJOR-V8-001  the pure lexical analysis form proved directly (separator
                normalization, repeat collapsing, "." elision, ".." detected before
                any elision, absoluteness, dotted names not traversal); six
                equivalence families all receive one identical verdict; four
                legitimate equivalence families also share one verdict in the
                accepting direction; a monkeypatched-probe test proves classification
                performs no filesystem I/O and never calls Path.resolve; the
                classifier never rewrites the persisted identifier; and the
                fail-closed rule is proved not to be a spelling denylist by refusing
                unlisted system roots (proc, Windows, Library, sys, dev, boot, srv)
                that no pattern names
  MAJOR-V8-002  the four audited wrapped/prefixed credentials rejected in the
                payload identifier, in the header producer, in an
                identifier-classified metadata fact, in permissions, in a nested
                structured reference and in a reference sequence; a credential in a
                LATER authority rejected; percent-encoded userinfo proved detected
                at helper level for both top-level and wrapped spellings; a manual
                event applies the same rule; the durable file never contains the
                audited passwords; the rejection message never echoes the secret;
                one enumerable test drives all thirteen shared channels
  controls      credential-free URIs, credential-free wrapped URIs, bare-username
                userinfo, an empty password, dotted/colon references and the
                provider/model and cmm/orchestration/step logical references all
                persist unchanged
  architecture  the one shared authority is the point of enforcement for both
                rules, the public path classifier reports every V8 and V7
                non-public reference, and no event_path_policy.py /
                event_credential_policy.py / identifier_policy.py /
                path_canonicalization.py module was added

tests/events/test_phase11_22_dp122_acceptance.py    +237 connected scenarios (250 -> 487)
  path-equivalent spellings and the strong non-public probes refused on every
  shared persisted identifier channel (payload identifier, payload workflow_id,
  payload aggregate_id, payload producer, header producer, header aggregate_id,
  header correlation_id, header source, permissions, metadata error_type, nested
  result reference, structured reference sequence, domain reference sequence);
  wrapped, prefixed and later-authority URI credentials refused on every shared
  channel; seven path-equivalence families — including the URI-suffix residue
  families — driven through the real durable store and proven to leave zero
  durable evidence; the real production PlatformOrchestrationEventSink refuses
  every shape before persistence; the real Orchestrator's mandatory emission fails
  closed with ORCHESTRATION_EVENT_EMISSION_FAILED and leaves zero durable evidence
  rather than dropping the fact silently; the refusal message never echoes the
  secret; legitimate references, credential-free URIs and credential-free wrapped
  URIs still persist and reopen fingerprint-equal; the frozen V7 traversal and
  top-level URI-userinfo rules are retained alongside the new ones
```

### 17.8 Gate evidence (Remediation V8)

Run with the canonical repository environment named by `CONTRIBUTING.md`
(`.venv/bin/python -m pytest`, CPython 3.14.7, `pytest 9.1.1`):

```text
REMEDIATION_V8_TESTS=289 passed (initial red 234 failed / 47 passed on the
  281-case module; the 8 URI-suffix residue reproductions added under TDD were
  independently red — 8 failed — before their fix)
V7_REGRESSIONS=127 passed (preserved)
V6_REGRESSIONS=126 passed, 1 pre-existing interpreter-dependent failure (preserved)
V5_REGRESSIONS=71 passed (preserved)
V4_REGRESSIONS=23 passed (preserved)
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
PRIOR_REMEDIATION_REGRESSIONS=604 collected, 603 passed, 1 pre-existing failure
REMEDIATION_V1_TO_V8_REGRESSIONS=893 collected, 892 passed, 1 pre-existing failure
PHASE_SUITE=tests/events/ 1997 collected, 1996 passed, 1 pre-existing failure
AT_DP_122=487 passed (250 prior + 237 V8)
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_ACCEPTANCE=tests/domains/test_domain_events_dp033_acceptance.py 92 passed
ORCHESTRATION_EVENT_TESTS=tests/orchestration/ 498 passed
VALIDATION_EVENT_TESTS=tests/validation/ 533 passed
WORKFLOW_EVENT_TESTS=tests/workflows/ 46 passed
KERNEL_ADAPTER_TESTS=76 passed
CLOSED_PHASE_ACCEPTANCES=185 passed, 1 warning
  (AT-DP-103, AT-DP-105, Phase 11.21/AT-DP-121, Phase 11.34/AT-DP-134, AT-DP-150)
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
ARCHITECTURE_AND_SECURITY_GATES=294 passed (part of tests/events/)
GLOBAL_PYTEST=24066 collected, 24065 passed, 1 warning, 1 pre-existing failure
CHANGED_FILE_RUFF=PASS (0 violations in every changed/created file)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; V8 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
ARCHITECTURE_GATES=PASS
SECURITY_GATES=PASS
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
```

The V7 production tree measured `1471` tests in `tests/events/` and `23540`
globally. The V8 additions are `+289` adversarial regressions in a new module and
`+237` strengthened `AT-DP-122` connected scenarios, so `tests/events/` moves
`1471 -> 1997` and the global collected count moves `23540 -> 24066`, exactly
`+526`. `AT-DP-122` itself moves `250 -> 487`. No
previously passing test was removed or weakened, and `PRIOR_REMEDIATION_REGRESSIONS`
is exactly `604`, byte-for-byte the figure the independent Re-audit V8 reported.

Two pre-existing, mutually exclusive interpreter-dependent failures exist in this
repository. Neither is a V8 finding, neither is touched by this remediation, and
both were reproduced at the Remediation V8 start HEAD before any production
mutation:

```text
CANONICAL_ENV (repo .venv, CPython 3.14.7)
  tests/events/test_phase11_22_remediation_v6_regressions.py
      ::test_invalid_civil_timestamps_are_rejected[2026-09-27T24:00:00Z]
  FAILS: CPython 3.11-3.13 reject ISO end-of-day "24:00", CPython 3.14
         datetime.fromisoformat() accepts it and normalizes to next-day midnight
  The other seven cases in that test (99:99, month 99, 25:61, 24:00:00-minute,
  second 61, ...) still fail closed, and every production timestamp rule is
  unchanged by Remediation V8.

CPYTHON 3.13.15 CROSS-CHECK
  tests/cli/test_phase11_4_parser.py
      ::test_registering_twice_is_a_parser_defect_not_a_silent_success
  FAILS: CPython 3.14 changed argparse's conflicting-subparser error from
         argparse.ArgumentError to ValueError, and the test asserts ValueError
  CPython 3.11 and 3.12 additionally cannot collect two tests/domains/ modules at
  all (@dataclass(slots=True) with a zero-arg super() call is broken below 3.13).
```

No available interpreter yields a zero-failure global run, so
`GLOBAL_PYTEST_FAILURES=0` is **not met in this environment** and is not claimed.
`GLOBAL_PYTEST_PASS_COUNT>=23540` **is** met, at `24065`. Both statements are
recorded rather than waived. The single canonical-environment failure is inside
`tests/events/`, so it also appears in `PHASE_SUITE` and
`PRIOR_REMEDIATION_REGRESSIONS`; every gate that does not include that one
interpreter-dependent case passes in full.

Superseded by Remediation V9: independent Re-audit V9 classified that remaining
canonical-environment failure as a **current Phase 11.22 contract defect**
(MAJOR-V9-002), not a pre-existing environment quirk. Remediation V9 fixed it, and
§18.8 records the resulting `GLOBAL_PYTEST_FAILURES=0` at `24604` passed. The V8
figures above are preserved unchanged as the V8 cycle's own record; the
"not met in this environment" statement is **not** a current-state claim.

### 17.9 Mandatory invariant evidence

```text
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION=PASS
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_PREFIX_OR_WRAPPER=PASS
CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
LEXICAL_PATH_ANALYSIS_PERFORMS_NO_FILESYSTEM_IO=PASS
PERSISTED_IDENTIFIER_IS_NEVER_REWRITTEN_BY_CANONICALIZATION=PASS

V7_URI_USERINFO_CREDENTIAL_REJECTION=PASS (preserved)
V7_RELATIVE_PATH_TRAVERSAL_REJECTION=PASS (preserved)
ABSOLUTE_HOME_FILESYSTEM_PATH_REJECTION=PASS (preserved, V6)
NUMERIC_LIFECYCLE_FACTS_ARE_ACTUALLY_BOUNDED=PASS (preserved, V6)
OFFICIAL_REPOSITORY_PARITY=PASS (preserved, V6)
ONE_CANONICAL_HEADER_FACT_AUTHORITY=PASS (preserved, V6)
TIMESTAMP_SEMANTIC_VALIDITY=PASS for every value the production rule decides
  (preserved, V6; one pre-existing interpreter-dependent test case noted in 17.8)
BINARY_BUFFER_VALUES_FAIL_CLOSED=PASS (preserved, V5)
RAW_USER_TEXT_CANNOT_BE_RELOCATED=PASS (preserved, V5)
METADATA_IS_NOT_A_PROSE_SIDE_CHANNEL=PASS (preserved, V5)
DLQ_SECRET_SAFETY_FAILS_SAFE_WITHOUT_EXTERNAL_BINDING=PASS (preserved, V5)
RAW_EXCEPTION_MESSAGES_NEVER_ENTER_DLQ=PASS (preserved, V4)
UNSAFE_EXCEPTION_CLASS_NAMES_NEVER_ENTER_DLQ=PASS (preserved, V4)
CONTENT_BOUND_FINGERPRINT=PASS (preserved, V1-V3)
SAME_ID_DIFFERENT_CONTENT_FAIL_CLOSED=PASS (preserved, V1-V3)
TAMPER_DETECTION=PASS (preserved, V1-V3)
UNSUPPORTED_SCHEMA_REJECTED_BEFORE_APPEND=PASS (preserved, V1-V3)
SUPPORTED_SCHEMA_REOPEN_ROUNDTRIP=PASS (preserved, V1-V3)
PUBLICATION_RESULT_ALIAS_ISOLATION=PASS (preserved, V1-V3)
SUBSCRIBER_MUTATION_ISOLATION=PASS (preserved, V1-V3)
REPOSITORY_SNAPSHOT_ISOLATION=PASS (preserved, V1-V3)
MANUAL_SENSITIVITY_CANONICALIZATION=PASS (preserved, V1-V3)
REPLAY_DOES_NOT_REPERSIST=PASS (preserved, V1-V3)
REPLAY_DEFAULT_DENY=PASS (preserved, V1-V3)
TARGETED_DLQ_REPLAY=PASS (preserved, V1-V3)
UNRELATED_SUBSCRIBER_CANNOT_RESOLVE_DLQ=PASS (preserved, V1-V3)
DLQ_RETAINED_UNTIL_TARGET_SUCCESS=PASS (preserved, V1-V3)
DETACHED_DLQ_INSPECTION_SNAPSHOTS=PASS (preserved, V1-V3)
DIRECT_BUS_NEUTRAL_FALLBACK=PASS (preserved, V1-V3)

NO_SECOND_EVENT_AUTHORITY=PASS
NO_SECOND_PATH_POLICY_MODULE=PASS
NO_SECOND_CREDENTIAL_POLICY=PASS
```

Scope note added by Remediation V9: the
`PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION` and
`NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE` claims above were
established against the **V8 corpus only** and did not cover a *wrapped
non-authority* `file:` reference reached through a public logical wrapper.
Independent Re-audit V9 falsified
`NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE` for exactly that
family (`provider/file:C:/Windows/System32/config/SAM` and its relatives were
durably persisted). Remediation V9 closes the family and §18.9 re-establishes both
invariants for the complete corpus. The V8 figures above are preserved unchanged as
the V8 cycle's own record; the statements are **not** a current-state claim.

### 17.10 Warnings

The one retained global warning is the pre-existing unrelated `starlette`
`anyio`/`httpx` `DeprecationWarning`. No new warning was introduced by Remediation
V8. No pre-existing warning was suppressed, and no warning filter was added.

### 17.11 Preserved evidence

The immutable Audit V1 report, the immutable Re-audit V2, V3, V4, V5, V6, V7 and V8
reports, and the immutable V1, V2, V3, V4, V5, V6, V7 and V8 bundles are
byte-identical to their audited state; each was re-hashed and matched the declared
value. All eight bundles remain untracked, as repository policy does not track
audit bundles. The quarantine stash state was preserved; no stash was created,
applied, popped or dropped, and no bundle was overwritten. `ROADMAP.md` and the
current evidence/reference/roadmap documents were updated for Remediation V8; no
historical audit report was rewritten.

### 17.12 Next step

Fresh independent ChatGPT re-audit of the **V9** exact-HEAD bundle
(`phase-11.22-event-system-audit-v9.tar.gz`). The phase remains
`REMEDIATED_AFTER_REAUDIT_V8_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete, and neither Phase 11.23 nor Phase 11.24 has
begun. Only that re-audit may write `BLOCKERS=0`, `MAJORS=0`,
`DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`, `CLOSURE_ELIGIBLE=YES`.

That re-audit has since been performed and returned `FAIL`
(`INDEPENDENT_REAUDIT_V9=FAIL`, `BLOCKERS=0`, `MAJORS=2`, `MINORS=1`). Section 18
records the resulting Remediation V9 and supersedes this next-step statement.

## 18. Remediation V9

### 18.1 Verdict being remediated

Independent Re-audit V9
(`docs/audits/phase-11.22-event-system-independent-reaudit-v9.md`, immutable,
report SHA-256
`f398ff360c33b8f6287b0d767e23c9557b726e54e11f1a408e91721cee05fdaf`) verified both
V8 findings fixed (`2/2_VERIFIED`) and preserved the prior remediation regressions,
while failing the phase with two new majors and one new minor:

```text
INDEPENDENT_REAUDIT_V9=FAIL
V8_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED
BLOCKERS=0
MAJORS=2
MINORS=1
MAJOR_V9_001=WRAPPED_NON_AUTHORITY_FILE_URI_BYPASSES_FAIL_CLOSED_FILESYSTEM_CLASSIFIER
MAJOR_V9_002=SUPPORTED_RUNTIME_TIMESTAMP_SEMANTICS_REOPEN_PRIOR_V6_FINDING_AND_KEEP_GLOBAL_GATE_RED
MINOR_V9_001=REFERENCE_TEST_EVIDENCE_COUNTS_STALE_AFTER_FINAL_V8_AT_ADDITIONS
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V9_ONLY
EXPECTED_NEXT_BUNDLE=phase-11.22-event-system-audit-v10.tar.gz
```

### 18.2 Exact start state

```text
BRANCH=feature/phase-11-stable-integrated-platform
REMEDIATION_V9_START_HEAD=f0fbbb2d5ce8f5a5850165687d95e2bab1cbb7e0
REMEDIATION_V9_START_TREE=42c5f45b235ebdb5698042e40427f02485bd39e4
START_HEAD_PARENT=ca40bf659da4035acc75c87f5cc77a25bbd2b83b
  (tree 8496faeb19011865ec5d49daa17bf89ee43a9fa8, the prompt's declared
   remediation-start HEAD and tree — exact match)
AUDITED_V9_IMPLEMENTATION_HEAD=487f200979604c1f648ad8a429ba531182333a40
  (tree 1b917f696d7f98795aad1b52bc4c3bcecb34954f — exact match; it is the
   parent of the declared remediation-start HEAD)
TRACKED_WORKTREE=CLEAN (only untracked historical audit bundles present)
V9_AUDIT_REPORT_SHA256=f398ff360c33b8f6287b0d767e23c9557b726e54e11f1a408e91721cee05fdaf
  (exact match to the prompt's declared value)
V9_BUNDLE_SHA256=1f5908e63a728d440cec6f62607d89fd6b4d9add8d77c941d967c3be139488fa
  (exact match to the prompt's declared value; not modified)
```

Provenance note, recorded rather than hidden: the actual start HEAD
`f0fbbb2d` is **one docs-only commit ahead** of the prompt's declared
`REMEDIATION_START_HEAD=ca40bf65`. The only tracked delta between them is the
addition of this remediation cycle's own committed prompt document
(`docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v9-agent-prompt.md`,
`+776` lines, `A` in `--name-status`), and the only tracked delta between the
audited V9 implementation HEAD `487f2009` and `ca40bf65` is the immutable V9 audit
report — exactly as the prompt states. Every substantive provenance artifact
(branch, tree, parent chain, audit-report hash, bundle hash, clean tracked
worktree) matched exactly, and the user explicitly named `f0fbbb2d`/`42c5f45b` as
the mandatory starting point. This matches the established pattern of the earlier
cycles, where the cycle's own prompt commit precedes its red-test commit (for
example `2f94f74`, the V8 prompt commit, precedes `2b92d6f`, the V8 red tests). No
forbidden Git operation was used: no `git stash`, `stash pop`, `stash apply`,
`stash drop`, `git reset`, `git clean` or `git worktree`, and no push or merge.

### 18.3 TDD red evidence

Red was established on the canonical `.venv` / CPython 3.14.7 **before** any
production mutation, in a commit that contains only the new adversarial module
(`601fb7a`, `test(phase11): reproduce phase11.22 reaudit v9 findings`):

```text
tests/events/test_phase11_22_remediation_v9_regressions.py
    168 failed, 229 passed
tests/events/test_phase11_22_remediation_v6_regressions.py
    1 failed, 126 passed   (the retained V6 case 2026-09-27T24:00:00Z)
```

All 168 failures were V9 targets; every positive control and every retained V1–V8
control passed in the same run. Reproduced before their own fixes: the wrapped
non-authority `file:` bypass through the classifier, the shared identifier
authority, canonical `EventSystem` publication, both official repositories, the
manual `publish_event(...)` boundary and all 13 shared identifier-bearing channels;
and the interpreter-dependent end-of-day timestamp acceptance. After the V9-001
production fix the module measured `373 passed / 24 failed`, with every remaining
failure belonging to MAJOR-V9-002. One control was then narrowed (`b03d28c`) because
it over-claimed that the authority asserts every civil bound, whereas only the hour
bound is asserted by the authority itself — the delegated bounds stay covered
against the real parser by the frozen verdict table.

### 18.4 Findings and remediation

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V9-001` | the shared identifier/filesystem safety authority recognized a `file:` reference only as an authority-bearing URI (`scheme://authority`) or at character zero (`^file:`). The outer identifier grammar admits a public logical wrapper such as `provider/` or `cmm/`, and the V8 slash-root allowlist accepted it, so a **non-authority** `file:` reference reached through that wrapper was never classified: `provider/file:C:/Windows/System32/config/SAM`, `cmm/file:C:/Windows/System32/config/SAM`, `provider/file:C:/Windows/System32/config/SECURITY`, `provider/file:/Windows/System32/config/SAM` and `provider/file:C:/ProgramData/Microsoft/Crypto/RSA/MachineKeys` each returned non-private from `is_private_filesystem_reference()`, passed `validate_platform_identifier()`, passed canonical `EventSystem` publication and were durably persisted — across all 13 shared identifier-bearing channels, through both official repositories and through a manual `publish_event(...)` call. `cmm/file:…`, `provider/file:/Library/Keychains/login.keychain-db` and `provider/file:/etc/hosts` behaved the same way | the **existing** `file:` signature inside `_PRIVATE_FILESYSTEM_PATTERNS` is anchored at a path *segment* boundary instead of at character zero: `re.compile(r"(?:^|/)file:", re.IGNORECASE)`. Because the pattern is evaluated against the canonical lexical analysis form whose segments are joined by `/`, a segment boundary is exactly where the identifier grammar can carry a scheme token, and `file` is a case-insensitive URI scheme — so `provider//file:`, `provider/./file:`, `PROVIDER/FILE:`, `File:` and the trailing-separator spelling all receive the identical verdict. No literal was appended for any audited filename or location, so an unnamed wrapped location (`provider/file:/boot/grub/grub.cfg`, `cmm/file:/Applications/Secrets.app/Contents/Resources/key`) is refused by the same structural rule. Analysis-only: no filesystem I/O, no host resolution, no `Path.resolve()`, no rewriting of an accepted persisted identifier, and no second path or URI policy module. Top-level `file:` refusals, credential-free network URIs, `provider/model`, `cmm/orchestration/step` and colon-bearing logical identifiers whose `file` token does not begin a path segment (`workflow:file:123`, `req:file:mod`) keep their verdicts. Windows-backslash spellings remain refused earlier by the identifier character set — recorded as a positive fail-closed fact; the grammar was not widened for them |
| `MAJOR-V9-002` | the canonical Phase 11.22 timestamp authority delegated the civil-hour bound to `datetime.fromisoformat()`. CPython 3.14 widened that parser to accept the ISO end-of-day spelling `24:00` and roll it into the next day, so on the canonical `.venv` the retained V6 regression case `2026-09-27T24:00:00Z` (and `…T24:00Z`, `…T24:00:00+00:00`, `…T24:00:00-05:00`, the space-separator form and the zero-fraction form) was accepted and durably persisted although the frozen contract admits only hours `00..23`. `GLOBAL_PYTEST_FAILURES=0` could therefore not be met on the canonical runtime | the frozen `00..23` hour range is asserted explicitly by the same authority, on the value's own text and **before** the parser is consulted: `MAX_PLATFORM_CIVIL_HOUR = 23` plus `_TIMESTAMP_CIVIL_TIME_PATTERN` and a guard in `_parse_canonical_timestamp()`. The guard is deliberately limited to the hour because that is the only civil bound the parser demonstrably widened — hour `25`, minute `60`, second `60`, month `13`, day `32`, a fractional end-of-day value and an out-of-range UTC offset are all still refused by `fromisoformat()` itself — so no wider parser rewrite was undertaken. No second timestamp parser, no accepted-form change, no normalization or timezone-semantics change, no Python support-metadata change, and the pre-existing `emitted_at >= occurred_at` chronology rule is untouched |
| `MINOR-V9-001` | current non-historical references were stale after the final V8 `AT-DP-122` additions: `tests/events/` was recorded as `1984 collected / 1983 passed` and `AT-DP-122` as `474 passed (250 prior + 224 V8)` although independent collection measured `1997` and `487`. Additionally a current statement claimed `NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS` while the V9-001 bypass was live | the current documents are synchronized to the final V9 counts (`tests/events/` `2535`, `AT-DP-122` `628`, global `24604`, failures `0`), the invariant is stated with its scope and only after the V9-001 remediation actually made it true, the V9 audit history and the V10 next step are recorded, and every current-state marker reads `REMEDIATED_AFTER_REAUDIT_V9_PENDING_INDEPENDENT_REAUDIT`. No historical audit report was rewritten and no V1–V9 bundle was overwritten |

Both production rules live in the authorities the phase already had
(`is_private_filesystem_reference()` reached through `validate_platform_identifier()`,
and `_parse_canonical_timestamp()`), so no channel can be patched alone and no
second authority was introduced.

### 18.5 Remediation commits

```text
601fb7a test(phase11): reproduce phase11.22 reaudit v9 findings
b03d28c test(phase11): scope the v9 interpreter-independence control to the hour bound
8287e1a fix(events): reject wrapped file uri references
0a453c7 fix(events): make event timestamp contract interpreter independent
a1e3a1c test(phase11): strengthen at-dp-122 for v9 regressions
<docs>  docs(phase11): record phase11.22 remediation v9 pending reaudit
```

The red-test commit precedes every production mutation. The docs commit and the
exact Remediation V9 HEAD, tree and V10 bundle SHA-256 are reported in the
remediation handoff rather than embedded here, for the same self-reference reason
as the earlier cycles.

### 18.6 Production files changed

```text
cmm/events/event_payload_safety.py   (only production file changed)
```

Exact deltas, both inside the existing canonical authority:

```text
1. _PRIVATE_FILESYSTEM_PATTERNS:  re.compile(r"^file:", re.IGNORECASE)
                              ->  re.compile(r"(?:^|/)file:", re.IGNORECASE)
   plus the accompanying V9 provenance comments and the
   is_private_filesystem_reference() docstring sentence.

2. new MAX_PLATFORM_CIVIL_HOUR = 23 and _TIMESTAMP_CIVIL_TIME_PATTERN
   = re.compile(r"^\d{4}-\d{2}-\d{2}[T ](?P<hour>\d{2}):"),
   and an explicit civil-hour guard in _parse_canonical_timestamp()
   placed after the unchanged _SAFE_TIMESTAMP_PATTERN shape check and
   before datetime.fromisoformat().
```

`_SAFE_TIMESTAMP_PATTERN`, the accepted timestamp shape and every other identifier,
credential, numeric and path rule are byte-identical to the V8 state. No new module,
class, registry, resolver, loader, engine, container or policy file was added, and
`cmm/events/` still contains exactly the same nine modules.

### 18.7 New and strengthened adversarial regressions

```text
tests/events/test_phase11_22_remediation_v9_regressions.py   NEW, 397 tests
tests/events/test_phase11_22_dp122_acceptance.py             +141 connected cases
```

The new module covers, for MAJOR-V9-001: the direct classifier, the direct
identifier authority, the canonical `EventSystem`, the official in-memory
repository, the official file-backed repository (byte-identical durable store on
rejection) and the manual `publish_event(...)` boundary; all 13 shared
identifier-bearing channels, each asserted both through the in-memory system and
against the durable store; the reported, sensitive-location and fresh wrapped
corpora; four separator/case equivalence families that must share one verdict;
positive controls proving the refusal is not a spelling denylist; the
`\`-spelling refusal by the character set; a no-filesystem-I/O proof that runs the
whole corpus with `Path.resolve`, `Path.stat`, `os.path.realpath`, `os.lstat` and
friends replaced by assertions; the static refusal message; and an architecture
guard that no second path/URI policy module exists. For MAJOR-V9-002: the retained
V6 case and its adjacent end-of-day spellings rejected by both canonical timestamp
entry points and by the connected publication path, before persistence, with the
durable store byte-identical and no `24:00` residue; a frozen
`(timestamp, accepted)` verdict table; a control that subrogates the parser with a
*wider* hypothetical interpreter and proves the hour bound is not delegated; a
control that makes the parser explode and proves the bound is applied without
consulting it; and controls that every admitted timestamp, every retained invalid
civil-time bound and the canonical normalization behaviour are unchanged.

`AT-DP-122` grew `487 -> 628` (`+141`) through the same connected acceptance file —
the real Phase 11.1 composition, the real file-backed canonical repository, the
canonical registry/bus/DLQ, the real production `PlatformOrchestrationEventSink`
and the real Orchestrator. No replacement acceptance system was created and no
previously passing case was removed or weakened.

### 18.8 Gate evidence (Remediation V9)

Run with the canonical repository environment named by `CONTRIBUTING.md`
(`.venv/bin/python -m pytest`, CPython 3.14.7, `pytest 9.1.1`):

```text
REMEDIATION_V9_TESTS=397 passed (initial red 168 failed / 229 passed, plus the retained V6 civil-time case)
V8_REGRESSIONS=289 passed (preserved)
V7_REGRESSIONS=127 passed (preserved)
V6_REGRESSIONS=127 passed (preserved; the retained civil-time case is now green)
V5_REGRESSIONS=71 passed (preserved)
V4_REGRESSIONS=23 passed (preserved)
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
PRIOR_REMEDIATION_REGRESSIONS=1290 passed (V1-V9, no failure)
PHASE_SUITE=tests/events/ 2535 passed, 0 failed
AT_DP_122=628 passed (487 prior + 141 V9)
KERNEL_ADAPTER_TESTS=76 passed
ARCHITECTURE_AND_SECURITY_GATES=294 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
AGENT_RUNTIME_DEPENDENCY_DIRECTION=tests/agent_runtime/test_dependency_direction.py 1 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_ACCEPTANCE=tests/domains/test_domain_events_dp033_acceptance.py 92 passed
ORCHESTRATION_EVENT_TESTS=tests/orchestration/ 498 passed
VALIDATION_EVENT_TESTS=tests/validation/ 533 passed
WORKFLOW_EVENT_TESTS=tests/workflows/ 46 passed
CLOSED_PHASE_ACCEPTANCES=185 passed, 1 warning
  (AT-DP-103, AT-DP-105, Phase 11.21/AT-DP-121, Phase 11.34/AT-DP-134, AT-DP-150)
PLATFORM_ARCHITECTURE=tests/platform/test_architecture.py 69 passed
IMPORTS=tests/test_imports.py 1 passed
EVENT_INVENTORY=tests/**/*event*.py 1270 passed (22 files, unchanged)
GLOBAL_PYTEST=24604 collected, 24604 passed, 1 warning, 0 failed
CHANGED_FILE_RUFF=PASS (0 violations in every changed/created file)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; V9 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS (every changed/created file `ruff format --check`-clean)
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
```

The V8 production tree measured `1997` tests in `tests/events/` and `24066`
collected globally, with `24065` passing and the retained V6 civil-time case
failing. The V9 additions are `+397` adversarial regressions in a new module and
`+141` strengthened `AT-DP-122` connected scenarios, and the retained V6 case is
repaired by the V9-002 fix, so `tests/events/` moves `1997 -> 2535` (`+538`) and the
global collected count moves `24066 -> 24604` (`+538`), with the pass count moving
`24065 -> 24604` (`+539`, including the repaired case).

`GLOBAL_PYTEST_FAILURES=0` is therefore **met** on the canonical CPython 3.14.7
runtime, and `GLOBAL_PYTEST_PASS_COUNT=24604` is **at or above** the `24066` floor
(and above it by `538`). No test was deleted, skipped or xfailed to obtain this: the
retained V6 regression case is fixed in production code, and the pass count rose by
exactly the number of tests added plus that one repaired case. The build was
re-run clean and uncontended; the previously observed cross-interpreter
`tests/cli/test_phase11_4_parser.py` argparse case is **not** part of the canonical
environment and does not appear in the canonical global run.

### 18.9 Mandatory invariant evidence

```text
WRAPPED_FILE_URI_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_FILE_URI_REFERENCES=PASS
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION=PASS
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS (complete corpus, top-level and wrapped)
PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT=PASS
URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_PREFIX_OR_WRAPPER=PASS
CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
LEXICAL_PATH_ANALYSIS_PERFORMS_NO_FILESYSTEM_IO=PASS
PERSISTED_IDENTIFIER_IS_NEVER_REWRITTEN_BY_CANONICALIZATION=PASS

V8_FILESYSTEM_REFERENCE_CLASSIFICATION=PASS (preserved)
V8_OCCURRENCE_INDEPENDENT_URI_USERINFO=PASS (preserved)
V7_URI_USERINFO_CREDENTIAL_REJECTION=PASS (preserved)
V7_RELATIVE_PATH_TRAVERSAL_REJECTION=PASS (preserved)
ABSOLUTE_HOME_FILESYSTEM_PATH_REJECTION=PASS (preserved, V6)
NUMERIC_LIFECYCLE_FACTS_ARE_ACTUALLY_BOUNDED=PASS (preserved, V6)
OFFICIAL_REPOSITORY_PARITY=PASS (preserved, V6)
ONE_CANONICAL_HEADER_FACT_AUTHORITY=PASS (preserved, V6)
TIMESTAMP_SEMANTIC_VALIDITY=PASS (preserved, V6; the interpreter-dependent case is repaired)
BINARY_BUFFER_VALUES_FAIL_CLOSED=PASS (preserved, V5)
RAW_USER_TEXT_CANNOT_BE_RELOCATED=PASS (preserved, V5)
METADATA_IS_NOT_A_PROSE_SIDE_CHANNEL=PASS (preserved, V5)
DLQ_SECRET_SAFETY_FAILS_SAFE_WITHOUT_EXTERNAL_BINDING=PASS (preserved, V5)
RAW_EXCEPTION_MESSAGES_NEVER_ENTER_DLQ=PASS (preserved, V4)
UNSAFE_EXCEPTION_CLASS_NAMES_NEVER_ENTER_DLQ=PASS (preserved, V4)
CONTENT_BOUND_FINGERPRINT=PASS (preserved, V1-V3)
SAME_ID_DIFFERENT_CONTENT_FAIL_CLOSED=PASS (preserved, V1-V3)
TAMPER_DETECTION=PASS (preserved, V1-V3)
UNSUPPORTED_SCHEMA_REJECTED_BEFORE_APPEND=PASS (preserved, V1-V3)
SUPPORTED_SCHEMA_REOPEN_ROUNDTRIP=PASS (preserved, V1-V3)
PUBLICATION_RESULT_ALIAS_ISOLATION=PASS (preserved, V1-V3)
SUBSCRIBER_MUTATION_ISOLATION=PASS (preserved, V1-V3)
REPOSITORY_SNAPSHOT_ISOLATION=PASS (preserved, V1-V3)
MANUAL_SENSITIVITY_CANONICALIZATION=PASS (preserved, V1-V3)
REPLAY_DOES_NOT_REPERSIST=PASS (preserved, V1-V3)
REPLAY_DEFAULT_DENY=PASS (preserved, V1-V3)
TARGETED_DLQ_REPLAY=PASS (preserved, V1-V3)
UNRELATED_SUBSCRIBER_CANNOT_RESOLVE_DLQ=PASS (preserved, V1-V3)
DLQ_RETAINED_UNTIL_TARGET_SUCCESS=PASS (preserved, V1-V3)
DETACHED_DLQ_INSPECTION_SNAPSHOTS=PASS (preserved, V1-V3)
DIRECT_BUS_NEUTRAL_FALLBACK=PASS (preserved, V1-V3)

NO_SECOND_EVENT_AUTHORITY=PASS
NO_SECOND_PATH_POLICY_MODULE=PASS
NO_SECOND_CREDENTIAL_POLICY=PASS
NO_SECOND_TIMESTAMP_PARSER=PASS
NO_SECOND_EVENT_SYSTEM_INFRASTRUCTURE=PASS
```

Failure-path expectations were re-proved for the new refusals: a rejected value
never reaches a durable repository file, the durable bytes are asserted unchanged on
every rejection, the DLQ count stays `0`, no adversarial location marker appears in
the refusal text or in the store, and the refusal messages remain static
categorical literals that echo neither a credential nor a filesystem location.
The MAJOR-V9-002 rejection occurs before persistence, leaves the store
byte-identical, and writes no `24:00` residue.

### 18.10 Warnings

The one retained global warning is the pre-existing unrelated `starlette`
`anyio`/`httpx` `DeprecationWarning`. No new warning was introduced by Remediation
V9. No pre-existing warning was suppressed, and no warning filter was added.

### 18.11 Preserved evidence

The immutable Audit V1 report, the immutable Re-audit V2, V3, V4, V5, V6, V7, V8 and
V9 reports, and the immutable V1, V2, V3, V4, V5, V6, V7, V8 and V9 bundles are
byte-identical to their audited state; each was re-hashed and matched the declared
value. All nine bundles remain untracked, as repository policy does not track audit
bundles, and none was overwritten. The quarantine stash state was preserved; no
stash was created, applied, popped or dropped. `ROADMAP.md` and the current
evidence/reference/roadmap documents were updated for Remediation V9; no historical
audit report was rewritten and no historical bundle was touched.

### 18.12 Next step

Fresh independent ChatGPT re-audit of the **V10** exact-HEAD bundle
(`phase-11.22-event-system-audit-v10.tar.gz`). The phase remains
`REMEDIATED_AFTER_REAUDIT_V9_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete, and neither Phase 11.23 nor Phase 11.24 has
begun. Only that re-audit may write `BLOCKERS=0`, `MAJORS=0`,
`DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`, `CLOSURE_ELIGIBLE=YES`.

That re-audit has since been performed and returned `FAIL`
(`INDEPENDENT_REAUDIT_V10=FAIL`, `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`). Section 19
records the resulting Remediation V10 and supersedes this next-step statement.

## 19. Remediation V10

### 19.1 Verdict being remediated

Independent Re-audit V10
(`docs/audits/phase-11.22-event-system-independent-reaudit-v10.md`, immutable,
report SHA-256
`ffe8c5e7d96836643362796c5ccfae29461aaa2d1293cc9ce0a6c210f86d7a8c`) verified all
three V9 findings fixed (`3/3_VERIFIED`) and preserved the prior remediation
regressions, while failing the phase with one new major, no minors and no blockers:

```text
INDEPENDENT_REAUDIT_V10=FAIL
V9_FINDINGS_FIXED=3/3_VERIFIED
BLOCKERS=0
MAJORS=1
MINORS=0
MAJOR_V10_001=WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCE_BYPASSES_PUBLIC_ROOT_FILESYSTEM_CLASSIFIER
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V10_ONLY
EXPECTED_NEXT_BUNDLE=phase-11.22-event-system-audit-v11.tar.gz
```

### 19.2 Exact start state

```text
BRANCH=feature/phase-11-stable-integrated-platform
REMEDIATION_V10_START_HEAD=a41eb4906ecc464c25e042d2cf0268e291b37abb
REMEDIATION_V10_START_TREE=6eab976eed4df755a32095806c3e900f0e5af3e9
START_HEAD_PARENT=3cd26ff4f4f3f20dfa524e48f876357e972c0073
  (tree cd0796063d50ecdd070d4e168f22c069b459b294, the prompt's declared
   remediation-start HEAD and tree — exact match)
AUDITED_V10_IMPLEMENTATION_HEAD=81a3a65e2b4edb3d9f2e89ead98aaf9e785cc2ef
  (tree 43d1b2efb12f71fa6dc215598074318038172849 — exact match)
TRACKED_WORKTREE=CLEAN (only untracked historical audit bundles present)
V10_AUDIT_REPORT_SHA256=ffe8c5e7d96836643362796c5ccfae29461aaa2d1293cc9ce0a6c210f86d7a8c
  (exact match to the prompt's declared value)
V10_BUNDLE_SHA256=cd594b857a0882cbc4059afbc01eb1f5d3f760c5ca7aacc1c4e9643bbae35840
  (exact match to the prompt's declared value; not modified)
```

Provenance was verified before any change: the current HEAD is exactly the
**prompt-only child** of `3cd26ff4`, whose only tracked delta is the addition of
this cycle's own committed prompt document
(`docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v10-agent-prompt.md`,
`A` in `--name-status`), and whose tree is exactly the declared
`cd0796063d50ecdd070d4e168f22c069b459b294`. Unlike the V9 cycle, no provenance
deviation arose: the user named `a41eb49`/`6eab976` as the mandatory starting point
and both matched exactly, so no compensating note is required. No forbidden Git
operation was used: no `git stash`, `stash pop`, `stash apply`, `stash drop`,
`git reset`, `git clean` or `git worktree`, and no push or merge.

### 19.3 TDD red evidence

Red was established on the canonical `.venv` / CPython 3.14.7 **before** any
production mutation, in a commit that contains only the new adversarial module
(`27b2aca`, `test(phase11): reproduce phase11.22 reaudit v10 finding`):

```text
tests/events/test_phase11_22_remediation_v10_regressions.py
    227 failed, 248 passed
```

All 227 failures were V10 targets; every positive control and every retained
V1–V9 control passed in the same run. Reproduced before their own fix, for the exact
audited reference `provider/C:/Windows/System32/config/SAM` and its family: the
direct classifier returning `False`, the direct identifier validator accepting, the
canonical `EventSystem` persisting (repository count `0 -> 1`), the official
in-memory repository, the official file-backed repository, the manual
`publish_event(...)` boundary and all 13 shared identifier-bearing channels. After
the single production change the module measured `475 passed` in the same run.

The failing counts were evenly structural, not literal-driven: 78 failures on the
fresh wrapped corpus across the 13 channels, 65 on the reported wrapped corpus
across the 13 channels, 14 on the equivalence spellings, 13 on the per-channel
durable-store proof, 11 each on the direct classifier, the direct identifier
authority, the file-backed repository and the manual boundary, and the remainder on
the structural controls that assert the rule exists at all.

### 19.4 Finding and remediation

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V10-001` | the canonical identifier/filesystem safety authority detected a raw Windows drive-root path only when the drive token sat at **character zero** of the whole reference: `re.compile(r"^[A-Za-z]:[\\/]")`. Remediation V9 had already moved the `file:` signature to a path-*segment* boundary, but the structurally equivalent raw drive-root token was left whole-value-anchored. Because `provider` and `cmm` are declared public slash roots (`PUBLIC_SLASH_REFERENCE_ROOTS`), the writer path was `provider/C:/Windows/System32/config/SAM` → not traversal, not whole-value absolute, drive-root pattern misses, public root `provider` → accepted as public-safe → persisted. `cmm/C:/Windows/System32/config/SAM`, `provider//C:/Windows/System32/config/SAM`, `provider/./C:/Windows/System32/config/SAM` and `provider/C:/Windows/System32/config/SECURITY` behaved identically, and the same value was durably appended through all 13 shared identifier-bearing channels in both official repositories and through a manual `publish_event(...)` call. The defect was not the literal filename `SAM`; it was the ability of an allowlisted logical wrapper to carry an embedded raw drive-root filesystem reference | the **existing** raw Windows drive-root signature inside `_PRIVATE_FILESYSTEM_PATTERNS` is anchored at a path *segment* boundary instead of at character zero: `re.compile(r"^[A-Za-z]:[\\/]")` → `re.compile(r"(?:^|/)[A-Za-z]:[\\/]")` — the same structural repair V9 applied to the structurally identical `file:` token, not a second scanner or a new Windows-path subsystem. Because the pattern is evaluated against the canonical lexical analysis form whose segments are joined by `/`, a segment boundary is exactly where the identifier grammar can carry a drive token, so `provider//C:/`, `provider/./C:/`, `Provider/C:/`, `PROVIDER/C:/`, `C://Windows/` and the lowercase `provider/c:/` all receive the identical verdict. The rule still requires real drive-root syntax — a letter, a colon and a path separator — so ordinary colon identifiers (`workflow:123`, `domain:legal`), segment-boundary non-drive colons (`provider/a:1/model`, `cmm/v2:3/detail`) and credential-free URIs (`https://example.com/model`, `http://localhost:8080/health`, `jdbc:postgresql://example.com/db`, `provider/https://example.com/model`) keep their verdicts. No literal was appended for `SAM`, `SECURITY`, `Windows`, `System32`, `ProgramData`, `MachineKeys` or any audited drive letter, so the fresh wrapped probes are refused by the same structural rule. Analysis-only: no filesystem I/O, no `Path.resolve()`, no host-dependent resolution, no rewriting of an accepted persisted identifier, and no second path/URI/identifier policy module. The Windows-backslash spelling (`C:\Windows\…`) is refused earlier by the identifier character set — a positive fail-closed fact recorded by test, so the grammar did not have to be widened |

The single production rule lives in the authority the phase already had
(`is_private_filesystem_reference()`, reached by every persisted identifier channel
through `validate_platform_identifier()`), so no channel can be patched alone and no
second authority was introduced.

### 19.5 Remediation commits

```text
27b2aca test(phase11): reproduce phase11.22 reaudit v10 finding
7ce59c2 fix(events): reject wrapped windows drive-root references
f7c44e0 test(phase11): strengthen at-dp-122 for v10 drive-root safety
<docs>  docs(phase11): record phase11.22 remediation v10 pending reaudit
```

The red-test commit precedes the single production mutation. The docs commit and the
exact Remediation V10 HEAD, tree and V11 bundle SHA-256 are reported in the
remediation handoff rather than embedded here, for the same self-reference reason as
the earlier cycles.

### 19.6 Production files changed

```text
cmm/events/event_payload_safety.py   (only production file changed)
```

Exact delta, inside the existing canonical authority:

```text
_PRIVATE_FILESYSTEM_PATTERNS:
    re.compile(r"^[A-Za-z]:[\\/]")
 -> re.compile(r"(?:^|/)[A-Za-z]:[\\/]")

plus the accompanying V10 provenance comments on that entry and on the
classifier's module-level comment block, and one sentence in the
is_private_filesystem_reference() docstring.
```

No new constant, pattern, module, class, registry, resolver, loader, engine,
container or policy file was added, and `cmm/events/` still contains exactly the
same nine modules. Every other identifier, credential, numeric, timestamp and path
rule is byte-identical to the V9 state.

### 19.7 New and strengthened adversarial regressions

```text
tests/events/test_phase11_22_remediation_v10_regressions.py   NEW, 475 tests
tests/events/test_phase11_22_dp122_acceptance.py             +121 connected cases
```

The new module covers: the direct classifier and the direct identifier authority for
the retained top-level controls, the five reported wrapped spellings and six fresh
wrapped probes (other drive letters, lowercase drive letter, unnamed locations); the
canonical `EventSystem`; the official in-memory repository; the official file-backed
repository, with the durable store asserted byte-identical on every rejection; the
manual `publish_event(...)` boundary; all 13 shared identifier-bearing channels, each
asserted both through the in-memory system and against the durable store; four
separator/case equivalence families that must share one verdict; positive controls
proving the refusal is not a spelling denylist (including segment-boundary non-drive
colons such as `provider/a:1/model`); the `\`-spelling refusal by the identifier
character set; a structural control proving one of the *existing* patterns matches
the canonical form at a segment boundary rather than at offset zero; a
no-filesystem-I/O proof that runs the whole corpus with `Path.resolve`, `Path.stat`,
`os.path.realpath`, `os.lstat` and friends replaced by assertions; the static refusal
message; an identity/correlation/causation-unchanged control for every accepted
reference; and an architecture guard that no second path/URI policy module exists.

`AT-DP-122` grew `628 -> 749` (`+121`) through the same connected acceptance file —
the real Phase 11.1 composition, the real file-backed canonical repository, the
canonical registry/bus/DLQ, the real production `PlatformOrchestrationEventSink`
and the real Orchestrator. The additions re-derive MAJOR-V10-001 in both directions:
top-level and wrapped drive roots refused, the four equivalence families receiving one
connected verdict, the reported corpus refused on all 13 shared channels, both
official repositories agreeing, and the real Orchestrator failing closed with
`ORCHESTRATION_EVENT_EMISSION_FAILED` and no durable bytes added — while every
legitimate reference persists and reopens with `workflow_id`, `aggregate_id`,
`producer`, `permissions`, `correlation_id` and `causation_id` intact and a matching
fingerprint. No replacement acceptance system was created and no previously passing
case was removed or weakened.

### 19.8 Gate evidence (Remediation V10)

Run with the canonical repository environment named by `CONTRIBUTING.md`
(`.venv/bin/python -m pytest`, CPython 3.14.7, `pytest 9.1.1`):

```text
REMEDIATION_V10_TESTS=475 passed (initial red 227 failed / 248 passed)
V9_REGRESSIONS=397 passed (preserved)
V8_REGRESSIONS=289 passed (preserved)
V7_REGRESSIONS=127 passed (preserved)
V6_REGRESSIONS=127 passed (preserved)
V5_REGRESSIONS=71 passed (preserved)
V4_REGRESSIONS=23 passed (preserved)
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
PRIOR_REMEDIATION_REGRESSIONS=1765 passed (V1-V10, no failure)
PHASE_SUITE=tests/events/ 3131 passed, 0 failed
AT_DP_122=749 passed (628 prior + 121 V10)
EVENT_SYSTEM_COMPOSITION_AND_INTEGRATION=323 passed
KERNEL_ADAPTER_TESTS=76 passed
ARCHITECTURE_AND_SECURITY_GATES=294 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
AGENT_RUNTIME_DEPENDENCY_DIRECTION=tests/agent_runtime/test_dependency_direction.py 1 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_ACCEPTANCE=tests/domains/test_domain_events_dp033_acceptance.py 92 passed
ORCHESTRATION_EVENT_TESTS=tests/orchestration/ 498 passed
VALIDATION_EVENT_TESTS=tests/validation/ 533 passed
WORKFLOW_EVENT_TESTS=tests/workflows/ 46 passed
CLOSED_PHASE_ACCEPTANCES=185 passed, 1 warning
  (AT-DP-103, AT-DP-105, Phase 11.21/AT-DP-121, Phase 11.34/AT-DP-134, AT-DP-150)
PLATFORM_ARCHITECTURE=tests/platform/test_architecture.py 69 passed
IMPORTS=tests/test_imports.py 1 passed
EVENT_INVENTORY=tests/**/*event*.py 1270 passed (22 files, unchanged)
GLOBAL_PYTEST=25200 collected, 25200 passed, 1 warning, 0 failed
CHANGED_FILE_RUFF=PASS (0 violations in every changed/created file)
GLOBAL_RUFF_COUNT=810 (`ruff check cmm kernel tests`; V10 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS (every changed/created file `ruff format --check`-clean)
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
```

The V9 production tree measured `2535` tests in `tests/events/` and `24604`
collected globally, all passing. The V10 additions are `+475` adversarial
regressions in a new module and `+121` strengthened `AT-DP-122` connected scenarios,
with no production-repair case needed this cycle, so `tests/events/` moves
`2535 -> 3131` (`+596`) and the global collected count moves `24604 -> 25200`
(`+596`), the pass count moving with it.

`GLOBAL_PYTEST_FAILURES=0` is therefore **met** on the canonical CPython 3.14.7
runtime, and `GLOBAL_PYTEST_PASS_COUNT=25200` is **at or above** the `24604` floor
(and above it by `596`). No test was deleted, skipped or xfailed to obtain this: the
pass count rose by exactly the number of tests added. The build was re-run clean and
uncontended; the previously observed cross-interpreter
`tests/cli/test_phase11_4_parser.py` argparse case is **not** part of the canonical
environment and does not appear in the canonical global run.

### 19.9 Mandatory invariant evidence

```text
WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_DRIVE_ROOT_REFERENCES=PASS
WRAPPED_FILE_URI_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_FILE_URI_REFERENCES=PASS
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION=PASS
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS (complete corpus, top-level and wrapped)
PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT=PASS
URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_PREFIX_OR_WRAPPER=PASS
CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
LEXICAL_PATH_ANALYSIS_PERFORMS_NO_FILESYSTEM_IO=PASS
PERSISTED_IDENTIFIER_IS_NEVER_REWRITTEN_BY_CANONICALIZATION=PASS

V9_WRAPPED_FILE_URI_REFUSAL=PASS (preserved)
V9_INTERPRETER_INDEPENDENT_CIVIL_HOUR=PASS (preserved)
V8_FILESYSTEM_REFERENCE_CLASSIFICATION=PASS (preserved)
V8_OCCURRENCE_INDEPENDENT_URI_USERINFO=PASS (preserved)
V7_URI_USERINFO_CREDENTIAL_REJECTION=PASS (preserved)
V7_RELATIVE_PATH_TRAVERSAL_REJECTION=PASS (preserved)
ABSOLUTE_HOME_FILESYSTEM_PATH_REJECTION=PASS (preserved, V6)
NUMERIC_LIFECYCLE_FACTS_ARE_ACTUALLY_BOUNDED=PASS (preserved, V6)
OFFICIAL_REPOSITORY_PARITY=PASS (preserved, V6)
ONE_CANONICAL_HEADER_FACT_AUTHORITY=PASS (preserved, V6)
TIMESTAMP_SEMANTIC_VALIDITY=PASS (preserved, V6)
BINARY_BUFFER_VALUES_FAIL_CLOSED=PASS (preserved, V5)
RAW_USER_TEXT_CANNOT_BE_RELOCATED=PASS (preserved, V5)
METADATA_IS_NOT_A_PROSE_SIDE_CHANNEL=PASS (preserved, V5)
DLQ_SECRET_SAFETY_FAILS_SAFE_WITHOUT_EXTERNAL_BINDING=PASS (preserved, V5)
RAW_EXCEPTION_MESSAGES_NEVER_ENTER_DLQ=PASS (preserved, V4)
UNSAFE_EXCEPTION_CLASS_NAMES_NEVER_ENTER_DLQ=PASS (preserved, V4)
CONTENT_BOUND_FINGERPRINT=PASS (preserved, V1-V3)
SAME_ID_DIFFERENT_CONTENT_FAIL_CLOSED=PASS (preserved, V1-V3)
TAMPER_DETECTION=PASS (preserved, V1-V3)
UNSUPPORTED_SCHEMA_REJECTED_BEFORE_APPEND=PASS (preserved, V1-V3)
SUPPORTED_SCHEMA_REOPEN_ROUNDTRIP=PASS (preserved, V1-V3)
PUBLICATION_RESULT_ALIAS_ISOLATION=PASS (preserved, V1-V3)
SUBSCRIBER_MUTATION_ISOLATION=PASS (preserved, V1-V3)
REPOSITORY_SNAPSHOT_ISOLATION=PASS (preserved, V1-V3)
MANUAL_SENSITIVITY_CANONICALIZATION=PASS (preserved, V1-V3)
REPLAY_DOES_NOT_REPERSIST=PASS (preserved, V1-V3)
REPLAY_DEFAULT_DENY=PASS (preserved, V1-V3)
TARGETED_DLQ_REPLAY=PASS (preserved, V1-V3)
UNRELATED_SUBSCRIBER_CANNOT_RESOLVE_DLQ=PASS (preserved, V1-V3)
DLQ_RETAINED_UNTIL_TARGET_SUCCESS=PASS (preserved, V1-V3)
DETACHED_DLQ_INSPECTION_SNAPSHOTS=PASS (preserved, V1-V3)
DIRECT_BUS_NEUTRAL_FALLBACK=PASS (preserved, V1-V3)

NO_SECOND_EVENT_AUTHORITY=PASS
NO_SECOND_PATH_POLICY_MODULE=PASS
NO_SECOND_DRIVE_ROOT_POLICY_MODULE=PASS
NO_SECOND_CREDENTIAL_POLICY=PASS
NO_SECOND_TIMESTAMP_PARSER=PASS
NO_SECOND_EVENT_SYSTEM_INFRASTRUCTURE=PASS
```

Failure-path expectations were re-proved for the new refusals: a rejected drive-root
reference never reaches a durable repository file, the durable bytes are asserted
unchanged on every rejection, the DLQ count stays `0`, no adversarial location marker
appears in the refusal text or in the store, and the refusal messages remain static
categorical literals that echo neither a credential nor a filesystem location. The
official in-memory repository is asserted unchanged beside the official file-backed
one, so no repository is treated as the safety boundary.

### 19.10 Warnings

The one retained global warning is the pre-existing unrelated `starlette`
`anyio`/`httpx` `DeprecationWarning`. No new warning was introduced by Remediation
V10. No pre-existing warning was suppressed, and no warning filter was added.

### 19.11 Preserved evidence

The immutable Audit V1 report, the immutable Re-audit V2, V3, V4, V5, V6, V7, V8, V9
and V10 reports, and the immutable V1, V2, V3, V4, V5, V6, V7, V8, V9 and V10 bundles
are byte-identical to their audited state; each was re-hashed and matched the declared
value. All ten bundles remain untracked, as repository policy does not track audit
bundles, and none was overwritten. No stash was created, applied, popped or dropped,
and no `git reset`, `git clean` or `git worktree` was used. `ROADMAP.md` and the
current evidence/reference/roadmap documents were updated for Remediation V10; no
historical audit report was rewritten and no historical bundle was touched.

### 19.12 Next step

Fresh independent ChatGPT re-audit of the **V11** exact-HEAD bundle
(`phase-11.22-event-system-audit-v11.tar.gz`). The phase remains
`REMEDIATED_AFTER_REAUDIT_V10_PENDING_INDEPENDENT_REAUDIT`: not closed, not
independently verified, not complete, and neither Phase 11.23 nor Phase 11.24 has
begun. Only that re-audit may write `BLOCKERS=0`, `MAJORS=0`,
`DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS`, `CLOSURE_ELIGIBLE=YES`.
