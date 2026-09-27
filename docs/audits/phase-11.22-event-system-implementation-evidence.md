# Phase 11.22 — Event System — implementation evidence for independent audit

**Status:** `REMEDIATED_AFTER_REAUDIT_V7_PENDING_INDEPENDENT_REAUDIT`
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
**Remediation V1 prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v1-agent-prompt.md`
**Remediation V2 prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v2-agent-prompt.md`
**Remediation V3 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v3-agent-prompt.md`
**Remediation V4 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v4-agent-prompt.md`
**Remediation V5 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v5-agent-prompt.md`
**Remediation V6 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v6-agent-prompt.md`
**Remediation V7 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v7-agent-prompt.md`

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
`PRIOR_REMEDIATION_REGRESSIONS=477_PASS`). It is not closed, independently
verified or complete. `DP-122=VERIFIED_EXISTING` and `AT-DP-122=PASS` belong only
to the independent audit of the V8 bundle.

Sections 1–9 record the original implementation evidence, §10 records Remediation
V1, §11 records Remediation V2, §12 records Remediation V3, §13 records
Remediation V4, §14 records Remediation V5, §15 records Remediation V6 and §16
records Remediation V7; the earlier sections are preserved as historical record.

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
