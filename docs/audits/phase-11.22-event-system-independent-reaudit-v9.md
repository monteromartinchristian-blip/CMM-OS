# CMM OS — Phase 11.22 Event System — Independent Re-audit V9

**Audit type:** Independent ChatGPT re-audit  
**Phase:** 11.22 — Event System  
**Design Point:** DP-122  
**Acceptance:** AT-DP-122  
**Audited exact HEAD:** `487f200979604c1f648ad8a429ba531182333a40`  
**Audited exact tree:** `1b917f696d7f98795aad1b52bc4c3bcecb34954f`  
**Audited bundle:** `phase-11.22-event-system-audit-v9.tar.gz`  
**Audited bundle SHA-256:** `1f5908e63a728d440cec6f62607d89fd6b4d9add8d77c941d967c3be139488fa`  
**Result:** **FAIL — remediation V9 required**

---

## 1. Executive verdict

Remediation V8 materially fixed both concrete findings from Independent Re-audit V8. The previously demonstrated path-equivalent spelling bypasses and wrapped/nested `scheme://userinfo` credential bypasses no longer persist through the canonical Event System, including the shared identifier-bearing channels exercised independently.

However, the V9 exact-HEAD bundle is **not closure-eligible**.

A fresh adversarial audit found a new structural bypass in the same filesystem-reference authority: wrapped **non-authority `file:` URIs** under an allowlisted public slash root are accepted and durably persisted. In addition, the mandatory global pytest zero-failure gate remains red on the repository's canonical CPython 3.14 environment because the timestamp validator delegates a frozen civil-time rule to interpreter-dependent `datetime.fromisoformat()` semantics. This is not merely an unrelated repository failure: it reopens the Phase 11.22 V6 regression that explicitly requires `2026-09-27T24:00:00Z` to be rejected before persistence.

A documentation minor also remains: two current reference documents report stale Phase 11.22 test/AT counts after the final V8 acceptance additions.

Therefore:

- `BLOCKERS=0`
- `MAJORS=2`
- `MINORS=1`
- `DP-122=NOT_VERIFIED`
- `AT-DP-122=FAIL_INDEPENDENT_REAUDIT`
- `CLOSURE_ELIGIBLE=NO`

Phase 11.23 and Phase 11.24 must not begin.

---

## 2. Provenance and archive integrity

The uploaded V9 archive was inspected directly rather than trusting the remediation handoff.

Verified:

- SHA-256 = `1f5908e63a728d440cec6f62607d89fd6b4d9add8d77c941d967c3be139488fa`
- `gzip -t` = PASS
- archive entries = `2691`
- symlinks = `0`
- path-traversal entries = `0`
- `.git` internals = `0`
- PAX global `comment` = `487f200979604c1f648ad8a429ba531182333a40`
- reconstructed tracked files = `2560`
- reconstructed executable tracked files = `16`
- reconstructed Git tree = `1b917f696d7f98795aad1b52bc4c3bcecb34954f`

The reconstructed tree matches the declared `REMEDIATION_TREE`. The PAX exact-HEAD marker matches the declared `REMEDIATION_HEAD`.

### V8 → V9 tracked scope

Compared with the independently retained V8 exact bundle, V9 contains no tracked removals.

Added:

- `docs/audits/phase-11.22-event-system-independent-reaudit-v8.md`
- `docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v8-agent-prompt.md`
- `tests/events/test_phase11_22_remediation_v8_regressions.py`

Modified:

- `ROADMAP.md`
- `cmm/events/event_payload_safety.py`
- `docs/audits/phase-11.22-event-system-implementation-evidence.md`
- `docs/reference/phase-11-event-system.md`
- `docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md`
- `docs/roadmap/phase-11-stable-integrated-platform.md`
- `tests/events/test_phase11_22_dp122_acceptance.py`

No tracked production file other than `cmm/events/event_payload_safety.py` changed.

This is consistent with the declared remediation scope and does not introduce a second event authority.

---

## 3. Historical evidence integrity

The design spec and tracked historical independent audit reports were re-hashed independently.

Verified exact design spec:

- `docs/superpowers/specs/2026-09-26-phase-11.22-event-system-design.md`
- SHA-256 = `d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40`

Verified historical report hashes:

- V1 = `3d259...` — exact retained report matched
- V2 = `20357...` — exact retained report matched
- V3 = `34969...` — exact retained report matched
- V4 = `ca025...` — exact retained report matched
- V5 = `26baac...` — exact retained report matched
- V6 = `1a4174...` — exact retained report matched
- V7 = `c55b2ed1...` — exact retained report matched
- V8 = `a91ff62e19a62e2b787ad5f8c68df92c65ee9a8d8947f9122453aa3bf0da64e6`

The audit did not rewrite or mutate historical audit artifacts.

---

## 4. Independent execution environment and reproducibility limits

The independent audit environment provided CPython 3.13.5. It did not contain repository development dependencies `libcst` or `ruff`.

To exercise the Event System without modifying the audited tree, an **audit-only external import shim** for `libcst` was placed outside the extracted repository. It was used only to unblock unrelated package imports. It is not part of the audited tree and is not evidence of repository correctness.

Independent executions:

- `tests/events/test_phase11_22_remediation_v8_regressions.py` → **289 passed**
- Phase 11.22 remediation regression modules V1–V8 → **893 passed**
- Phase 11.22 architecture + security tests → **294 passed**
- representative core Event System suites → **193 passed**, with one root-user filesystem-permission artifact
- Phase 11.22 composition suite → **23 passed**, with one root-user filesystem-permission artifact
- `pytest --collect-only tests/events/test_phase11_22_dp122_acceptance.py` → **487 collected**
- `pytest --collect-only tests/events/` → **1997 collected**
- `compileall` → **PASS**

The two permission-test failures observed only under the audit container's root user are not treated as Phase 11.22 defects because `chmod 0500` cannot reliably make a path unwritable to root.

### Full connected AT limitation

The full connected AT-DP-122 could not be rerun unchanged in the independent container. Composition reached an unrelated domain-definition identity failure:

`TypeError: super(type, obj): obj (instance of DomainReasoningRuleDefinition) is not an instance or subtype...`

This is an audit-environment limitation and is **not** the basis of the FAIL verdict below. The FAIL is based on independently executable canonical public-surface persistence bypasses plus the unmet mandatory canonical-runtime gate.

`ruff` was unavailable in the independent audit container, so the reported global Ruff count `810` could not be independently recalculated here.

---

## 5. Verification of V8 findings

### MAJOR-V8-001 — verified fixed for its concrete reproductions

The exact V8 filesystem-reference reproductions were exercised against the current canonical Event System / file-backed repository:

- `safe/etc//shadow`
- `safe/etc/./shadow`
- `safe/private//var/db/keychains`
- `safe/private/./var/db/keychains`
- `proc/self/environ`
- `etc/ssh/ssh_host_rsa_key`
- `Windows/System32/config/SAM`
- `Library/Keychains/login.keychain-db`

All exact V8 examples were rejected before persistence.

A manually authored shared-channel probe using `safe/etc//shadow` was rejected cleanly on all **13/13** identifier-bearing channels exercised, with repository count remaining zero.

**Verdict:** `MAJOR_V8_001=FIX_VERIFIED_FOR_REPORTED_FINDING`

### MAJOR-V8-002 — verified fixed for its concrete reproductions

The exact wrapped/nested userinfo credential examples were exercised:

- `jdbc:postgresql://alice:supersecret@example.com/db`
- `jdbc:mysql://root:hunter2hunter2@example.com/db`
- `provider/https://alice:supersecret@example.com/db`
- `foo:https://alice:supersecret@example.com/db`

All were rejected before persistence.

A manually authored shared-channel probe using `provider/https://alice:supersecret@example.com/db` was rejected cleanly on all **13/13** exercised channels, with repository count remaining zero.

**Verdict:** `MAJOR_V8_002=FIX_VERIFIED_FOR_REPORTED_FINDING`

### MINOR-V8-001 — verified fixed

The high-level `ROADMAP.md` summary now records Re-audits V2 through V7, remediation after all seven, then Re-audit V8 and remediation pending independent re-audit.

**Verdict:** `MINOR_V8_001=FIX_VERIFIED`

Overall:

`V8_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED`

---

## 6. MAJOR-V9-001 — Wrapped non-authority `file:` URI bypasses fail-closed filesystem classifier

### Severity

**MAJOR**

### Canonical invariant violated

- `NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE`
- the V8 remediation's own stated fail-closed filesystem-reference classification contract

### Independent reproduction

Fresh adversarial probes found that wrapped non-authority `file:` URI forms under an allowlisted public slash root are classified as safe.

Examples independently accepted by the identifier authority include:

- `provider/file:C:/Windows/System32/config/SAM`
- `cmm/file:C:/Windows/System32/config/SAM`
- `provider/file:C:/Windows/System32/config/SECURITY`
- `provider/file:/Windows/System32/config/SAM`
- `provider/file:C:/ProgramData/Microsoft/Crypto/RSA/MachineKeys`

For `provider/file:C:/Windows/System32/config/SAM`:

- `is_private_filesystem_reference(...)` returned false
- `validate_platform_identifier(...)` accepted the exact value
- the canonical public `EventSystem` accepted and durably persisted the exact string

The persistence reproduction was then repeated independently across all **13/13** shared identifier-bearing channels exercised:

1. payload request ID
2. payload workflow ID
3. payload aggregate ID
4. payload producer
5. header producer
6. header aggregate ID
7. header correlation ID
8. header source
9. permissions
10. metadata error type
11. nested result reference
12. structured reference sequence
13. domain reference sequence

Each case produced one persisted record containing the exact unsafe reference.

A manually constructed canonical event passed directly to `publish_event(...)` also accepted/persisted this wrapped `file:` value with both the in-memory and official file-backed repository paths.

### Root cause

The current classifier structurally recognizes authority-bearing URI forms through `scheme://authority`, while the retained `file:` rejection is anchored at the beginning of the complete identifier.

This leaves a gap for **non-authority file URI syntax** such as:

- `file:C:/...`
- `file:/...`

when it occurs after an allowlisted wrapper such as `provider/` or `cmm/`.

The public slash-root allowlist then treats the outer identifier as a permitted logical reference even though its retained inner component denotes a local filesystem resource.

This is a structural bypass, not an uncovered single filename.

### Required remediation

Remediation V9 must remain inside the existing canonical identifier/filesystem-safety authority. It must not create a parallel scanner, URI registry, path policy, or event subsystem.

Required behavior:

- detect local `file:` scheme occurrences at valid embedded reference boundaries even when `//` is absent;
- cover at least `file:/...` and `file:C:/...` wrapped forms;
- reject before Event System persistence on every shared identifier-bearing channel;
- preserve the persisted spelling of accepted values; analysis-only normalization remains analysis-only;
- do not solve this by appending the reproduced Windows filenames to a denylist;
- prove that top-level and wrapped `file:` references receive the same unsafe classification;
- preserve legitimate public slash references and credential-free network URI references already supported;
- add direct identifier-authority, canonical EventSystem, in-memory/file-backed repository, manual-publish, shared-channel, durable-zero, and AT-DP-122 regressions.

Recommended explicit invariant:

`WRAPPED_FILE_URI_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_FILE_URI_REFERENCES`

---

## 7. MAJOR-V9-002 — Supported canonical runtime reopens V6 timestamp safety finding and leaves mandatory global gate red

### Severity

**MAJOR**

### Gates/invariants violated

The committed Remediation V8 prompt required:

- `GLOBAL_PYTEST_FAILURES=0`
- `GLOBAL_PYTEST_PASS_COUNT>=23540`

The V9 handoff truthfully reports:

- `GLOBAL_PYTEST=24066 collected, 24065 passed, 1 warning, 1 pre-existing failure`

Therefore the mandatory zero-failure gate is not met.

This would already prevent closure. More importantly, the remaining failure belongs to the Phase 11.22 event timestamp safety contract and reopens a previously remediated V6 regression.

### Exact failing Phase 11.22 contract

The retained Phase 11.22 regression explicitly requires:

`2026-09-27T24:00:00Z`

to be rejected as an invalid civil timestamp before persistence.

The current validator's timestamp grammar admits a generic two-digit hour and then delegates civil-time semantic validation to `datetime.fromisoformat()`.

On CPython 3.14, `datetime.fromisoformat()` gained support for ISO-8601 `24:00` as the end-of-day representation of midnight on the next day. Thus the repository's frozen Phase 11.22 safety rule changes with interpreter version.

The repository declares Python `>=3.10`, and the user's canonical repository `.venv` is CPython 3.14.7. On that canonical environment, the retained Phase 11.22 V6 regression fails.

### Why this is not treated as an unrelated pre-existing failure

The failure is inside the Phase 11.22 Event System test suite and tests a prior independent audit remediation requirement. It directly contradicts the phase's committed invariant on timestamp acceptance.

The underlying behavior is therefore a current Phase 11.22 compatibility/safety defect, not merely red unrelated repository debt.

### Required remediation

Use the existing timestamp validation authority only. Do not create a parallel parser or broaden scope to unrelated interpreter-version failures.

The smallest acceptable fix should:

- make the frozen civil-time contract explicit and interpreter-independent;
- reject hour `24` where the existing Phase 11.22 contract requires rejection, before persistence;
- preserve all currently valid timestamp forms required by the phase;
- retain the V6 regression and add a runtime-compatibility regression if needed;
- demonstrate the canonical CPython 3.14 environment reaches `GLOBAL_PYTEST_FAILURES=0`;
- keep `GLOBAL_PYTEST_PASS_COUNT>=23540`;
- rerun Phase 11.22 timestamp/privacy/event regressions plus global suite.

Do not change project Python support metadata merely to evade the regression unless an independently justified platform decision is made outside this remediation cycle.

Recommended explicit invariant:

`PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT`

---

## 8. MINOR-V9-001 — Current reference test evidence is stale after final V8 AT additions

### Severity

**MINOR**

Independent collection establishes current exact counts:

- `tests/events/` → `1997`
- `tests/events/test_phase11_22_dp122_acceptance.py` → `487`

The implementation evidence records these current figures.

However:

- `docs/reference/phase-11-event-system.md` still reports `1984 collected / 1983 passed` and `474 passed (250 prior + 224 V8)`;
- `docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md` repeats those stale counts.

The requirements matrix also contains a security-gate statement that currently claims `NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS`, which cannot remain true while MAJOR-V9-001 is open.

### Required remediation

Synchronize current, non-historical documentation with the exact V9 remediation state after rerunning the final gates.

At minimum:

- update Phase 11 event reference counts;
- update requirements matrix counts;
- update current security-gate status/evidence after MAJOR-V9-001 is fixed;
- keep historical audit reports immutable;
- keep phase status as remediated/pending independent re-audit, never closed.

---

## 9. Architecture and authority review

The V9 remediation did not introduce a second event bus, event registry, event repository, replay engine, identifier subsystem, URI registry, or filesystem-policy module.

Verified architecture/security suite:

- `294 passed`

Static inspection confirms the production delta remains centered on:

- `cmm/events/event_payload_safety.py`

No Agent Runtime → Domain reverse dependency was introduced in the inspected tree.

The canonical Event System architecture therefore remains structurally intact; the V9 FAIL concerns correctness of the shared safety authority and a retained timestamp invariant, not a need for architectural replacement.

---

## 10. DP-122 and AT-DP-122 disposition

The remediation handoff reports:

- `DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION`
- `AT-DP-122=PASS_REPORTED`
- `AT_DP_122=487 passed`

Independent collection confirms the AT now contains 487 cases.

However, independent verification cannot elevate DP-122 while a canonical EventSystem persistence path still admits a non-public local filesystem reference, and while the mandatory global zero-failure gate is red on the canonical supported runtime because of a retained Phase 11.22 timestamp regression.

The full connected AT also could not be executed unchanged in the independent container due an unrelated domain-definition runtime identity issue. That limitation does not change the verdict because MAJOR-V9-001 was independently reproduced through the canonical public EventSystem and official repository implementations.

Therefore:

`DP-122=NOT_VERIFIED`

`AT-DP-122=FAIL_INDEPENDENT_REAUDIT`

This does not mean the reported 487-case local run is disregarded; it means the acceptance evidence is insufficient for closure in the presence of independently demonstrated invariant failures.

---

## 11. Required scope for Remediation V9

Remediation V9 must be narrow.

It may address only:

- `MAJOR-V9-001`
- `MAJOR-V9-002`
- `MINOR-V9-001`
- directly connected tests, AT evidence, and current documentation needed to prove those fixes

It must preserve all V1–V8 fixes and all canonical Event System architecture/invariants.

It must not:

- begin Phase 11.23 or 11.24;
- create parallel event/identifier/path/URI/timestamp infrastructure;
- rewrite historical audit reports;
- close Phase 11.22 before a fresh independent V10 PASS;
- use the remediation cycle to fix unrelated repository compatibility issues;
- suppress or xfail the canonical timestamp regression merely to obtain green gates.

The next exact audit artifact must be a new bundle, expected as:

`phase-11.22-event-system-audit-v10.tar.gz`

generated from the fully committed exact remediation HEAD.

---

## 12. Final audit markers

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
