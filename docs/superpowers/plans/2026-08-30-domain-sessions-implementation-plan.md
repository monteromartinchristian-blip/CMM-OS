# Phase 10.34 — Domain Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement resumable, fail-closed Domain Intelligence session state on top of the existing Phase 8 Session Context lifecycle, with deterministic typed contracts, current-state revalidation, shared persistence, and complete Phase 10.34 acceptance evidence.

**Architecture:** Add a reference-first `DomainSessionContext` and resumption service inside `cmm.domains`. Phase 8 remains authoritative for session lifecycle and persistence; Phase 10.34 stores only domain-specialization state through that shared boundary. Resume reconstructs current domain state before continuation and never executes operations, grants approvals, or mutates memory/knowledge merely by loading a session.

**Tech Stack:** Python 3, frozen/slotted dataclasses and existing repository contracts, pytest, Ruff, compileall, existing Phase 8 Cognitive Layer session infrastructure, existing Phase 10 registries/resolver/composer/permissions/conflict/events.

**Spec:** `docs/superpowers/specs/2026-08-30-domain-sessions-design.md`

## Global Constraints

- Baseline design commit: `8d3ac8851daa932af10e2f2374161b46dbf743f9`.
- Work only on `feature/phase-10-domain-intelligence`.
- Preserve `stash@{0}: On feature/phase-10-domain-intelligence: quarantine: post-audit phase 10.32 uncommitted changes`.
- Never use `git stash`, `stash pop/apply/drop`, `git reset`, `git clean`, or worktrees unless explicitly authorized.
- No push and no merge.
- Phase 8 remains owner of shared `SessionContext` lifecycle/persistence.
- Do not introduce a `DomainSessionRepository` as an independent source of truth.
- Do not introduce a second memory, knowledge, workflow, approval, permission, planner, temporal, resolver, composition, or event subsystem.
- The exact Phase 10.33 general event catalog remains 23 events.
- Reuse `cmm/domains/credential_policy.py`; do not add a second credential detector.
- Persisted permissions and operation availability are historical snapshots, never current authorization.
- Resume alone must not execute operations, grant approvals, or mutate memory/knowledge.
- All production behavior follows strict RED → verify RED → GREEN → verify GREEN → refactor.
- Documentation before independent audit may say implemented/pending audit, never independently audited/complete/final PASS.
- Audit TAR.GZ is created only after the exact implementation HEAD is committed, using `git archive`, never the worktree.
- Manual artifacts go under `$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads/`.

---

## Locked File Structure

### New Phase 10.34 production files

- `cmm/domains/session_contracts.py` — immutable public contracts, enums, serialization and validation for Domain Session state and resume results.
- `cmm/domains/session_codec.py` — narrow codec/attachment boundary between `DomainSessionContext` and the existing shared Phase 8 Session Context persistence representation.
- `cmm/domains/session_revalidation.py` — pure current-state checks for domain/version/compatibility/resource-temporal/workflow/question/approval inventories.
- `cmm/domains/session_resumer.py` — orchestration of resume using existing Phase 8/Phase 10 services; no operation execution.
- `cmm/domains/session_acceptance.py` — executable `AT-DP-034` checkpoint inventory and gate helper, following current repository acceptance-test convention if an equivalent canonical module pattern exists.

### Existing Phase 10 files expected to be modified

- `cmm/domains/errors.py` — Domain Session error hierarchy only.
- `cmm/domains/__init__.py` — stable public exports only.
- `docs/roadmap/phase-10-domain-intelligence.md` — implementation status for 10.34, conservatively marked pending independent audit.
- `docs/reference/domain-intelligence-requirements-matrix.md` — add `DP-034` / `AT-DP-034`.
- `ROADMAP.md` — move next milestone to 10.35 only after implementation-side gates pass; do not claim independent audit.
- `docs/reference/domain-sessions.md` — canonical implementation boundary/reference document.

### New tests

- `tests/domains/test_domain_session_contracts.py`
- `tests/domains/test_domain_session_serialization.py`
- `tests/domains/test_domain_session_security.py`
- `tests/domains/test_domain_session_codec.py`
- `tests/domains/test_domain_session_revalidation.py`
- `tests/domains/test_domain_session_resumer.py`
- `tests/domains/test_domain_session_permissions.py`
- `tests/domains/test_domain_session_workflows.py`
- `tests/domains/test_domain_session_questions_approvals.py`
- `tests/domains/test_domain_session_events.py`
- `tests/domains/test_domain_session_public_api.py`
- `tests/domains/test_at_dp_034_domain_sessions.py`

### Existing tests expected to be extended only if needed

- `tests/domains/test_domain_public_api.py`
- Phase 8 session-context tests located by Task 0 if the shared generic persistence surface must be extended.

---

### Task 0: Repository Alignment Gate

**Files:**
- Read only: `docs/superpowers/specs/2026-08-30-domain-sessions-design.md`
- Read only: `docs/roadmap/phase-10-domain-intelligence.md`
- Read only: `docs/reference/domain-intelligence-requirements-matrix.md`
- Read only: `cmm/domains/selection.py`
- Read only: `cmm/domains/resolver.py`
- Read only: `cmm/domains/conflict_resolution.py`
- Read only: `cmm/domains/conflict_resolution_contracts.py`
- Read only: `cmm/domains/event_contracts.py`
- Read only: `cmm/domains/event_adapters.py`
- Read only: `cmm/domains/event_publisher.py`
- Read only: `cmm/domains/credential_policy.py`
- Read only: Phase 8 files containing `SessionContext`, located by the commands below.

**Interfaces:**
- Consumes: committed Phase 10.34 design and current repository contracts.
- Produces: exact internal mapping from existing shared session API to Tasks 4–10; no code changes.

- [ ] **Step 1: Verify immutable starting state**

```bash
cd "/Users/chris/CMM OS"
test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
test "$(git rev-parse HEAD)" = "8d3ac8851daa932af10e2f2374161b46dbf743f9"
test -z "$(git status --porcelain)"
git stash list | grep -Fq "quarantine: post-audit phase 10.32 uncommitted changes"
```

- [ ] **Step 2: Locate the actual Phase 8 shared session implementation**

```bash
rg -n \
  'class SessionContext|SessionContext\(|session context|session_context|resume.*session|pause.*session' \
  cmm tests \
  --glob '*.py'
```

Record the exact production module(s), repository/store/service, serialization method, lifecycle states, update method, and existing tests.

- [ ] **Step 3: Locate current Phase 10 integration APIs**

```bash
rg -n \
  'DomainSelectionPolicy|DomainSelectionTransition|DefaultDomainResolver|DefaultDomainComposer|DomainPermission|DomainConflictResolver|DomainKernelEventPublisher|DomainEventFactory' \
  cmm/domains tests/domains \
  --glob '*.py'
```

- [ ] **Step 4: Enforce alignment decision**

The implementation must use the real Phase 8 session persistence/update surface discovered in Step 2. If extending that surface is necessary, extend the existing generic Session Context contract minimally rather than creating a domain-specific repository. Do not proceed if the only proposed implementation path duplicates shared persistence.

- [ ] **Step 5: Verify no mutation occurred**

```bash
git status --short
git diff --check
test -z "$(git status --porcelain)"
```

Expected: clean.

---

### Task 1: Domain Session Contracts

**Files:**
- Create: `cmm/domains/session_contracts.py`
- Modify: `cmm/domains/errors.py`
- Test: `tests/domains/test_domain_session_contracts.py`

**Interfaces:**
- Consumes: `DomainId` and repository-native identifier/serialization patterns.
- Produces: `DomainSessionContext`, `DomainSessionTransition`, `DomainSessionResumeRequest`, `DomainSessionResumeResult`, `DomainSessionResumeStatus`, `DomainSessionCheck`, `DomainSessionCheckStatus`, `DomainSessionContractError`, `DomainSessionSerializationError`.

- [ ] **Step 1: Write RED tests for immutable reference-first context**

Tests must prove:
- frozen/slotted behavior;
- primary/supporting domains;
- stored domain versions;
- composition/profile/rules/permissions;
- domain-grouped resource and knowledge refs;
- workflows/operations/questions/conflicts/approvals/partial results/traces;
- transitions;
- last resolution;
- next recommended step;
- positive revision and timezone-aware `updated_at`;
- deterministic duplicate elimination or explicit duplicate rejection according to existing Phase 10 convention.

Run:

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_contracts.py
```

Expected: RED because module/symbols do not yet exist.

- [ ] **Step 2: Implement minimal contracts**

Use frozen/slotted dataclasses and immutable nested state. No mutable caller-owned list/dict may remain aliased after construction.

A `DomainSessionTransition` must include:
- previous/new primary domain;
- previous/new supporting domains;
- grounded `reason_code`;
- resolution reference;
- composition reference;
- timezone-aware occurrence time.

- [ ] **Step 3: GREEN**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_contracts.py
.venv/bin/ruff check cmm/domains/session_contracts.py cmm/domains/errors.py tests/domains/test_domain_session_contracts.py
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add cmm/domains/session_contracts.py cmm/domains/errors.py tests/domains/test_domain_session_contracts.py
git diff --cached --check
git commit -m "feat(domains): add domain session contracts"
```

---

### Task 2: Strict Serialization and Schema Integrity

**Files:**
- Modify: `cmm/domains/session_contracts.py`
- Test: `tests/domains/test_domain_session_serialization.py`

**Interfaces:**
- Consumes: Task 1 contracts.
- Produces: strict `to_dict()` / `from_dict()` round-trip with a closed schema version.

- [ ] **Step 1: RED**

Cover:
- JSON serialization with `allow_nan=False`;
- exact round-trip equality;
- deterministic mapping/list order in serialized form;
- unknown top-level field rejection;
- unknown transition/check field rejection;
- unsupported schema version rejection;
- malformed DomainId/ref/version/revision/timestamp rejection;
- timezone-naive timestamp rejection;
- non-string map keys rejection;
- nested NaN/Infinity/non-JSON object rejection;
- caller mutation after `from_dict()` cannot mutate state.

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_serialization.py
```

- [ ] **Step 2: GREEN implementation**

Add one explicit schema version constant owned by Phase 10.34. Parse every field strictly. Do not use permissive `dict.get()` defaults for malformed required state.

- [ ] **Step 3: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_session_contracts.py \
  tests/domains/test_domain_session_serialization.py
```

- [ ] **Step 4: Commit**

```bash
git add cmm/domains/session_contracts.py tests/domains/test_domain_session_serialization.py
git diff --cached --check
git commit -m "feat(domains): serialize domain sessions strictly"
```

---

### Task 3: Credential and Sensitive-State Boundary

**Files:**
- Modify: `cmm/domains/session_contracts.py`
- Reuse: `cmm/domains/credential_policy.py`
- Test: `tests/domains/test_domain_session_security.py`

**Interfaces:**
- Consumes: canonical Phase 10.33 credential policy.
- Produces: session state that rejects credentials without leaking them in errors.

- [ ] **Step 1: RED credential regression matrix**

Dynamically consume the canonical credential-policy signatures/test-vector inventory. Test credential-shaped values in:
- metadata keys/values;
- next-step text if free text is permitted;
- transition reason metadata if any;
- resource/knowledge reference values;
- nested mappings.

For each canonical signature:
- construction/deserialization rejects it;
- exception string/details do not contain the credential;
- no persisted candidate is produced.

Also prove benign high-entropy data is not rejected generically.

- [ ] **Step 2: GREEN**

Reuse the existing canonical recursive credential/privacy helper or policy entrypoint. No copied signature list.

- [ ] **Step 3: Verify**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_security.py
```

- [ ] **Step 4: Commit**

```bash
git add cmm/domains/session_contracts.py tests/domains/test_domain_session_security.py
git diff --cached --check
git commit -m "fix(domains): protect domain session state"
```

---

### Task 4: Shared Phase 8 Session Attachment and Codec

**Files:**
- Create: `cmm/domains/session_codec.py`
- Modify only if Task 0 proves necessary: the existing generic Phase 8 Session Context persistence/serialization module discovered in Task 0.
- Test: `tests/domains/test_domain_session_codec.py`
- Extend only if necessary: the corresponding existing Phase 8 session test file discovered in Task 0.

**Interfaces:**
- Consumes: `DomainSessionContext`; actual Phase 8 Session Context read/update/persist API.
- Produces: `DomainSessionCodec` (or repository-convention equivalent) that attaches/loads one typed domain-session extension through shared session persistence.

- [ ] **Step 1: RED**

Prove:
- domain session state survives shared Session Context persist/reload;
- no separate durable repository/store exists;
- missing domain extension is handled as no prior Domain Session, not fabricated state;
- malformed extension fails closed;
- persistence update is atomic according to shared Phase 8 behavior;
- failed write leaves the prior persisted shared session recoverable.

- [ ] **Step 2: GREEN**

Implement only a narrow adapter/codec. If the existing Session Context already has a generic extension/payload mechanism, use it. If it lacks one, add the smallest generic typed-extension slot needed to the Phase 8 model and its existing serializer/store; do not make Phase 8 import `cmm.domains`.

Dependency direction must remain:

```text
cmm.domains -> shared Phase 8 session contracts
```

not:

```text
Phase 8 cognitive core -> cmm.domains
```

- [ ] **Step 3: Verify Phase 8 regressions**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_codec.py
# Then run the exact existing Phase 8 session-context test file(s) found in Task 0.
```

- [ ] **Step 4: Commit**

Stage only the codec, its tests, and any minimal generic Phase 8 extension required.

```bash
git diff --cached --check
git commit -m "feat(domains): attach domain state to shared sessions"
```

---

### Task 5: Pure Revalidation Contracts and Current-Domain Checks

**Files:**
- Create: `cmm/domains/session_revalidation.py`
- Test: `tests/domains/test_domain_session_revalidation.py`

**Interfaces:**
- Consumes: `DomainSessionContext`, `DomainRegistry`, current Domain Definitions and compatibility contracts.
- Produces: deterministic `DomainSessionCheck` inventory and a candidate current-domain snapshot; performs no persistence and no execution.

- [ ] **Step 1: RED**

Cover:
- current primary/supporting domain active/enabled;
- missing primary;
- missing supporting domain;
- disabled/incompatible domain;
- unchanged version;
- changed but compatible version;
- changed incompatible version;
- deterministic check ordering;
- no mutation of registry/session.

- [ ] **Step 2: GREEN**

Implement pure functions/service. Version change alone is not a failure; existing compatibility contracts decide.

- [ ] **Step 3: Verify**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_revalidation.py
```

- [ ] **Step 4: Commit**

```bash
git add cmm/domains/session_revalidation.py tests/domains/test_domain_session_revalidation.py
git diff --cached --check
git commit -m "feat(domains): revalidate resumed domain state"
```

---

### Task 6: Resource, Knowledge, and Temporal Drift

**Files:**
- Modify: `cmm/domains/session_revalidation.py`
- Test: `tests/domains/test_domain_session_revalidation.py`

**Interfaces:**
- Consumes: existing resource/knowledge metadata, temporal/provenance contracts discovered in repo.
- Produces: drift checks classified without copying resource or knowledge bodies.

- [ ] **Step 1: RED**

Test current/changed/stale/missing/invalidated/unknown states where repository-native APIs support them. Prove:
- no source content is duplicated into Domain Session;
- high-impact missing/stale dependency can block;
- ordinary changed reference can require recomposition/replan without false blocking;
- temporal reference is timezone-aware and deterministic.

- [ ] **Step 2: GREEN**

Use existing metadata/version/temporal services. Do not invent a new temporal engine.

- [ ] **Step 3: Verify and commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_revalidation.py
git add cmm/domains/session_revalidation.py tests/domains/test_domain_session_revalidation.py
git diff --cached --check
git commit -m "feat(domains): detect resumed session drift"
```

---

### Task 7: Permission Re-evaluation and Operation Availability

**Files:**
- Create: `tests/domains/test_domain_session_permissions.py`
- Modify: `cmm/domains/session_revalidation.py`
- Modify: `cmm/domains/session_resumer.py` only after Task 8 creates it, or keep pure helper output ready for Task 8.

**Interfaces:**
- Consumes: existing restrictive domain permission composition and operation availability resolver.
- Produces: current effective permission refs + filtered available operation IDs.

- [ ] **Step 1: RED**

Required cases:
- persisted allow becomes current deny -> operation removed;
- persisted deny becomes current allow -> approval-gated operation still not auto-authorized;
- malformed authorization fails closed;
- cross-domain sensitive access remains restricted;
- old `available_operation_ids` never causes executor invocation;
- current permission intersection remains most restrictive.

- [ ] **Step 2: GREEN**

Call existing permission and availability contracts. Never interpret old permission snapshots as decision inputs except for audit/change comparison.

- [ ] **Step 3: Verify**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_permissions.py
```

Do not commit until Task 8 if `session_resumer.py` is not yet created; otherwise commit the pure revalidation delta now.

---

### Task 8: Domain Session Resumer Core

**Files:**
- Create: `cmm/domains/session_resumer.py`
- Modify: `cmm/domains/session_revalidation.py`
- Test: `tests/domains/test_domain_session_resumer.py`
- Include: `tests/domains/test_domain_session_permissions.py`

**Interfaces:**
- Consumes: shared Session Context codec; Domain Registry; resolver; composer; profile/rule/permission/operation services; conflict resolver; current temporal/resource/knowledge checks.
- Produces: `DomainSessionResumer.resume(request) -> DomainSessionResumeResult`.

- [ ] **Step 1: RED nominal resume**

A persisted unchanged session resumes with:
- current domains;
- reconstructed/current composition;
- current permission/operation state;
- preserved valid refs;
- deterministic next step;
- committed revision/history only after successful shared persistence;
- no operation execution.

- [ ] **Step 2: RED re-resolution/recomposition**

Cover:
- supporting domain disappeared -> recomposition;
- primary no longer usable but safe resolver yields replacement -> re-resolution;
- material/ambiguous high-risk replacement -> BLOCKED/clarification according to existing resolver policy;
- domain change creates exactly one transition and reevaluates profile/rules/questions/operations.

- [ ] **Step 3: GREEN orchestration**

Implement canonical order from the design spec. Keep collaborators injectable where current project style supports this, enabling deterministic tests.

- [ ] **Step 4: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_session_permissions.py \
  tests/domains/test_domain_session_resumer.py
```

- [ ] **Step 5: Commit**

```bash
git add \
  cmm/domains/session_resumer.py \
  cmm/domains/session_revalidation.py \
  tests/domains/test_domain_session_permissions.py \
  tests/domains/test_domain_session_resumer.py
git diff --cached --check
git commit -m "feat(domains): resume domain sessions safely"
```

---

### Task 9: Workflow Compatibility and Migration State

**Files:**
- Modify: `cmm/domains/session_revalidation.py`
- Modify: `cmm/domains/session_resumer.py`
- Test: `tests/domains/test_domain_session_workflows.py`

**Interfaces:**
- Consumes: existing Domain Workflow registry/contracts and shared Workflow Engine references.
- Produces: current workflow ref classification and resume status.

- [ ] **Step 1: RED**

Cover:
- CURRENT workflow;
- explicitly MIGRATED compatible workflow;
- REPLAN_REQUIRED;
- INCOMPATIBLE;
- MISSING required workflow;
- COMPLETED/CANCELLED no longer treated as active;
- required incompatible/missing workflow cannot disappear silently while result says RESUMED.

- [ ] **Step 2: GREEN**

Keep workflow runtime authority outside Domain Session. Store/reference only IDs and compatible migration evidence.

- [ ] **Step 3: Commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_workflows.py
git add \
  cmm/domains/session_revalidation.py \
  cmm/domains/session_resumer.py \
  tests/domains/test_domain_session_workflows.py
git diff --cached --check
git commit -m "feat(domains): reconcile resumed workflows"
```

---

### Task 10: Pending Questions, Approvals, Conflicts, Partial Results, and Traces

**Files:**
- Modify: `cmm/domains/session_resumer.py`
- Test: `tests/domains/test_domain_session_questions_approvals.py`

**Interfaces:**
- Consumes: existing question/approval/conflict/result/trace reference contracts.
- Produces: deduplicated still-valid resumable inventories.

- [ ] **Step 1: RED questions**

Prove answered/resolved questions disappear, still-pending remain, changed domain/composition can invalidate or regenerate question refs, and duplicates never accumulate.

- [ ] **Step 2: RED approvals**

Prove resolved/expired/invalidated approvals are not recovered as live authorization. A still-valid pending approval may be surfaced by reference only.

- [ ] **Step 3: RED conflicts/results/traces**

Blocking conflict prevents continuation. Partial results/traces survive as audit continuity but are not treated as fresh conclusions after relevant drift.

- [ ] **Step 4: GREEN and commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_questions_approvals.py
git add cmm/domains/session_resumer.py tests/domains/test_domain_session_questions_approvals.py
git diff --cached --check
git commit -m "feat(domains): recover pending domain session state"
```

---

### Task 11: Atomicity, Idempotency, and Failure Recovery

**Files:**
- Modify: `cmm/domains/session_resumer.py`
- Modify as required by shared API: `cmm/domains/session_codec.py`
- Test: `tests/domains/test_domain_session_resumer.py`
- Test: `tests/domains/test_domain_session_codec.py`

**Interfaces:**
- Consumes: shared atomic Session Context persistence.
- Produces: no partial committed resume state.

- [ ] **Step 1: RED mandatory revalidation failure**

Assert:
- prior persisted context unchanged;
- candidate discarded/uncommitted;
- no operation, approval, memory or knowledge mutation;
- structured blocking findings.

- [ ] **Step 2: RED persistence failure**

A valid candidate followed by persistence failure returns FAILED and cannot claim `resumed_revision` committed.

- [ ] **Step 3: RED idempotency**

Two unchanged resumes with same authoritative state and temporal reference:
- do not duplicate transitions/questions/approvals/workflows/operations;
- do not manufacture drift;
- do not create an endless revision loop from retry after failed persistence.

- [ ] **Step 4: GREEN and commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_session_codec.py \
  tests/domains/test_domain_session_resumer.py
git add \
  cmm/domains/session_codec.py \
  cmm/domains/session_resumer.py \
  tests/domains/test_domain_session_codec.py \
  tests/domains/test_domain_session_resumer.py
git diff --cached --check
git commit -m "fix(domains): make session resume atomic"
```

---

### Task 12: Existing Domain Event Integration Without Catalog Expansion

**Files:**
- Modify only if necessary: `cmm/domains/session_resumer.py`
- Reuse: `cmm/domains/event_adapters.py`
- Reuse: `cmm/domains/event_publisher.py`
- Test: `tests/domains/test_domain_session_events.py`

**Interfaces:**
- Consumes: existing 23 general events and lifecycle adapters.
- Produces: events only for actual existing lifecycle changes caused by resume.

- [ ] **Step 1: RED**

Prove:
- mere loading/resume creates no invented `domain.session.resumed`;
- catalog count remains exactly 23;
- a real new resolution may emit existing resolution lifecycle event only after authoritative resolution exists;
- a real composition semantic update may emit `domain.composition.updated`;
- identical recomposition emits no update event;
- publication occurs only after shared session persistence commits when event claims committed transition;
- credential rejection still prevents Kernel publication.

- [ ] **Step 2: GREEN**

Use existing adapters/factory/publisher. Do not modify `DomainConflictResolver` purity.

- [ ] **Step 3: Verify**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_events.py
```

- [ ] **Step 4: Commit**

```bash
git add cmm/domains/session_resumer.py tests/domains/test_domain_session_events.py
git diff --cached --check
git commit -m "feat(domains): publish resumed lifecycle events"
```

---

### Task 13: Public API and Import Boundary

**Files:**
- Modify: `cmm/domains/__init__.py`
- Test: `tests/domains/test_domain_session_public_api.py`
- Modify if required by established package test: `tests/domains/test_domain_public_api.py`

**Interfaces:**
- Consumes: completed public contracts/services.
- Produces: stable `cmm.domains` exports with no import-time side effects.

- [ ] **Step 1: RED**

Assert expected public symbols exist and are in `__all__`. Do not export private codec internals or credential helpers unless existing convention explicitly requires them.

- [ ] **Step 2: GREEN exports**

- [ ] **Step 3: Fresh import**

```bash
.venv/bin/python - <<'PY'
import subprocess
import sys

proc = subprocess.run(
    [sys.executable, "-c", "import cmm.domains; print('IMPORT_OK')"],
    text=True,
    capture_output=True,
    check=True,
)
assert proc.stdout.strip() == "IMPORT_OK"
assert proc.stderr == ""
print("FRESH_IMPORT=PASS")
PY
```

- [ ] **Step 4: Verify public regressions**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_session_public_api.py \
  tests/domains/test_domain_public_api.py
```

- [ ] **Step 5: Commit**

```bash
git add \
  cmm/domains/__init__.py \
  tests/domains/test_domain_session_public_api.py \
  tests/domains/test_domain_public_api.py
git diff --cached --check
git commit -m "feat(domains): expose domain session API"
```

---

### Task 14: AT-DP-034 Acceptance Gate

**Files:**
- Create: `cmm/domains/session_acceptance.py`
- Create: `tests/domains/test_at_dp_034_domain_sessions.py`

**Interfaces:**
- Consumes: all Task 1–13 capabilities.
- Produces: explicit acceptance accounting tied to `DP-034` with every design-spec checkpoint connected to executable evidence.

- [ ] **Step 1: Define canonical checkpoint inventory**

Encode all 56 design checkpoints with stable names/categories. If current Phase 10 acceptance convention uses tests only rather than a production acceptance module, follow that established convention and keep the inventory in the test module; do not create unnecessary production machinery.

- [ ] **Step 2: RED accounting**

Test:
- checkpoint count matches canonical inventory;
- no duplicate checkpoint name;
- every checkpoint has executable assertion coverage;
- missing new checkpoint/test linkage fails gate.

- [ ] **Step 3: GREEN full acceptance**

Acceptance must cover architecture, contracts, persistence, resume checks, drift, permissions, workflows, questions/approvals, events, atomicity, security, import boundary, docs-state constraints, and audit-package preconditions.

- [ ] **Step 4: Verify**

```bash
.venv/bin/python -m pytest -q tests/domains/test_at_dp_034_domain_sessions.py
```

Print explicit logical checkpoint count and pytest case count.

- [ ] **Step 5: Commit**

```bash
git add cmm/domains/session_acceptance.py tests/domains/test_at_dp_034_domain_sessions.py 2>/dev/null || true
git add tests/domains/test_at_dp_034_domain_sessions.py
git diff --cached --check
git commit -m "test(domains): add phase 10.34 acceptance gate"
```

Do not stage a nonexistent `session_acceptance.py`; use the repository-native acceptance convention determined in Step 1.

---

### Task 15: Documentation Before Audit

**Files:**
- Create: `docs/reference/domain-sessions.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `ROADMAP.md`

**Interfaces:**
- Consumes: verified implementation facts only.
- Produces: conservative implementation documentation, pending independent audit.

- [ ] **Step 1: Write implementation reference**

Document:
- shared Session Context ownership;
- reference-first state;
- schema and serialization boundary;
- resume algorithm;
- current-state authority;
- drift/permissions/workflows/questions/approvals;
- atomicity/idempotency;
- event boundary;
- security/privacy;
- explicit non-goals.

- [ ] **Step 2: Add `DP-034` / `AT-DP-034` to requirements matrix**

State implementation-side gate evidence only.

- [ ] **Step 3: Update roadmap status conservatively**

Permitted wording:

```text
Phase 10.34 — Domain Sessions: implemented; independent audit pending.
Next implementation milestone: Phase 10.35 — Domain SDK.
```

Do not say complete/audited/final PASS.

- [ ] **Step 4: Verify docs**

```bash
git diff --check
rg -n "10\.34|DP-034|AT-DP-034|Domain Sessions" \
  ROADMAP.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/reference/domain-sessions.md
```

- [ ] **Step 5: Commit**

```bash
git add \
  ROADMAP.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/reference/domain-sessions.md
git diff --cached --check
git commit -m "docs(domains): document phase 10.34 implementation"
```

---

### Task 16: Adversarial and Architecture Regression Gate

**Files:**
- Extend: relevant Phase 10.34 tests created above.
- No unrelated production changes unless a newly failing test demonstrates a real 10.34 defect.

**Interfaces:**
- Consumes: complete candidate implementation.
- Produces: adversarial evidence before final implementation commit/amendment.

- [ ] **Step 1: Add adversarial cases before any remediation**

Required probes include:
- malformed serialized authorization objects;
- truthy strings/integers where booleans/enums are expected;
- duplicate references with Unicode/confusable edge cases according to existing identifier policy;
- stale approval reused after permission/domain change;
- stale operation availability;
- missing/disabled primary high-risk domain;
- incompatible version;
- resource invalidation;
- persistence exception after candidate computation;
- event publisher failure after committed state according to existing error policy;
- credential vectors from canonical registry;
- caller-owned nested mutation;
- naive datetimes;
- unknown schema version;
- malicious/unexpected metadata key shapes;
- no `AgentRuntimeEventBus`, repository, replay, DLQ, or direct storage dependency.

- [ ] **Step 2: Run focused suite**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_session_*.py tests/domains/test_at_dp_034_domain_sessions.py
```

- [ ] **Step 3: Architecture grep**

```bash
! rg -n \
  'AgentRuntimeEventBus|DomainSessionRepository|dead.?letter|DLQ|event replay|durable event queue' \
  cmm/domains/session_*.py
```

- [ ] **Step 4: Commit test/remediation delta if any**

Use TDD for every remediation and a focused commit message.

---

### Task 17: Final Implementation Verification

**Files:**
- All Phase 10.34 changed production/test/docs files.

**Interfaces:**
- Produces: exact independently auditable committed implementation HEAD.

- [ ] **Step 1: Focused Phase 10.34**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_session_*.py \
  tests/domains/test_at_dp_034_domain_sessions.py
```

- [ ] **Step 2: Phase 10 domain suite**

```bash
.venv/bin/python -m pytest -q tests/domains
```

- [ ] **Step 3: Global suite**

```bash
.venv/bin/python -m pytest -q
```

- [ ] **Step 4: Ruff and format on changed Python files**

Resolve the implementation baseline as the commit immediately before the first Phase 10.34 production-code commit, then:

```bash
BASE="$(git merge-base HEAD 8d3ac8851daa932af10e2f2374161b46dbf743f9)"
mapfile -t CHANGED_PY < <(
  git diff --name-only --diff-filter=ACMR "$BASE"..HEAD -- '*.py' | sort -u
)

.venv/bin/ruff check "${CHANGED_PY[@]}"
.venv/bin/ruff format --check "${CHANGED_PY[@]}"
```

On zsh, use an equivalent array construction if `mapfile` is unavailable.

- [ ] **Step 5: Compile and diff hygiene**

```bash
.venv/bin/python -m compileall -q cmm/domains tests/domains
git diff --check
test -z "$(git status --porcelain)"
git stash list | grep -Fq "quarantine: post-audit phase 10.32 uncommitted changes"
```

- [ ] **Step 6: Verify historical 10.33 invariants**

```bash
.venv/bin/python - <<'PY'
from cmm.domains.event_catalog import CANONICAL_DOMAIN_EVENTS
assert len(CANONICAL_DOMAIN_EVENTS) == 23
assert len(set(CANONICAL_DOMAIN_EVENTS)) == 23
print("GENERAL_EVENT_COUNT=23")
PY
```

Run the current Phase 10.33 targeted event/credential regression tests as identified by `rg -l 'DP-033|credential_policy|DomainKernelEventPublisher' tests/domains`.

- [ ] **Step 7: Ensure a clean committed implementation HEAD**

If final verification required no changes, current HEAD is the implementation HEAD.

If final verification required code/test/doc changes, commit them with an accurate focused message and rerun Steps 1–6 from that new HEAD.

Record:

```bash
IMPLEMENTATION_HEAD="$(git rev-parse HEAD)"
echo "IMPLEMENTATION_HEAD=$IMPLEMENTATION_HEAD"
test -z "$(git status --porcelain)"
```

---

### Task 18: Build Exact `git archive` Audit Bundle

**Files:**
- No repository mutation.
- Output: `$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads/phase-10.34-audit-v1.tar.gz`
- Output manifest/checksum text may also be written in the same Downloads directory, but must not be committed as implementation evidence unless explicitly requested later.

**Interfaces:**
- Consumes: exact clean committed implementation HEAD from Task 17.
- Produces: immutable audit bundle for independent ChatGPT audit.

- [ ] **Step 1: Precheck exact committed state**

```bash
cd "/Users/chris/CMM OS"
test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
test -z "$(git status --porcelain)"
git stash list | grep -Fq "quarantine: post-audit phase 10.32 uncommitted changes"

IMPLEMENTATION_HEAD="$(git rev-parse HEAD)"
OUT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads/phase-10.34-audit-v1.tar.gz"
rm -f "$OUT"
```

Removing an old bundle at the output path is allowed; do not remove repository files.

- [ ] **Step 2: Create bundle from Git object database, never worktree**

```bash
git archive \
  --format=tar.gz \
  --prefix="CMM-OS-phase-10.34/" \
  -o "$OUT" \
  "$IMPLEMENTATION_HEAD"
```

- [ ] **Step 3: SHA256**

```bash
SHA256="$(shasum -a 256 "$OUT" | awk '{print $1}')"
echo "AUDIT_BUNDLE=$OUT"
echo "AUDIT_BUNDLE_SHA256=$SHA256"
```

- [ ] **Step 4: Verify archive identity/content**

```bash
test -s "$OUT"
tar -tzf "$OUT" > /tmp/phase-10.34-audit-v1.contents.txt

grep -Fq "CMM-OS-phase-10.34/docs/superpowers/specs/2026-08-30-domain-sessions-design.md" \
  /tmp/phase-10.34-audit-v1.contents.txt
grep -Fq "CMM-OS-phase-10.34/cmm/domains/session_contracts.py" \
  /tmp/phase-10.34-audit-v1.contents.txt
grep -Fq "CMM-OS-phase-10.34/cmm/domains/session_resumer.py" \
  /tmp/phase-10.34-audit-v1.contents.txt
grep -Fq "CMM-OS-phase-10.34/tests/domains/test_at_dp_034_domain_sessions.py" \
  /tmp/phase-10.34-audit-v1.contents.txt

! grep -E '(^|/)\.git(/|$)|(^|/)\.venv(/|$)|__pycache__|\.pyc$' \
  /tmp/phase-10.34-audit-v1.contents.txt
```

- [ ] **Step 5: Verify repository still untouched**

```bash
test "$(git rev-parse HEAD)" = "$IMPLEMENTATION_HEAD"
test -z "$(git status --porcelain)"
git stash list | grep -Fq "quarantine: post-audit phase 10.32 uncommitted changes"
```

- [ ] **Step 6: Stop for independent audit**

Do not create an audit report, closure commit, push, merge, or start Phase 10.35.

Return:
- branch;
- exact `IMPLEMENTATION_HEAD`;
- all focused/domain/global test counts;
- AT-DP-034 logical checkpoint count and pytest case count;
- Ruff/format/compile/diff results;
- 10.33 regression/event catalog result;
- worktree status;
- quarantine stash preservation;
- exact TAR.GZ path;
- SHA256;
- archive verification result.

The TAR.GZ is then supplied to ChatGPT in this project for the independent Phase 10.34 audit.

---

## Self-Review

### Spec coverage

Tasks 1–3 cover the immutable, strict, credential-safe public state contract. Task 4 binds it to Phase 8 shared persistence. Tasks 5–11 cover every mandatory resumption gate and atomic/idempotent behavior. Task 12 preserves the exact 10.33 event boundary. Tasks 13–14 cover public API and `AT-DP-034`. Tasks 15–17 cover conservative documentation and verification. Task 18 produces the required exact-HEAD `git archive` bundle.

### Architectural boundary

No task creates an independent Domain Session repository, planner, workflow engine, approval system, permission engine, cognitive session, knowledge store, memory store, temporal engine, resolver, composer, event bus, replay queue, or DLQ.

### Type consistency

The plan consistently uses:
- `DomainSessionContext`;
- `DomainSessionTransition`;
- `DomainSessionResumeRequest`;
- `DomainSessionResumeResult`;
- `DomainSessionResumeStatus`;
- `DomainSessionCheck`;
- `DomainSessionCheckStatus`;
- `DomainSessionResumer`.

Task 0 requires repository-native Phase 8/Phase 10 APIs to be discovered before integration rather than guessing their names.

### Audit boundary

Implementation documentation remains explicitly pending independent audit. Audit packaging is performed only from a clean exact committed HEAD using `git archive`. Independent audit, audit-report commit, remediation/re-audit, and final closure remain outside the implementation agent's authority.
