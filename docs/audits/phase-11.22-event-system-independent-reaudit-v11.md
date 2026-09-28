# CMM OS — Phase 11.22 Event System — Independent Re-audit V11

**Audit type:** Independent ChatGPT re-audit  
**Phase:** 11.22 — Event System  
**Design Point:** DP-122  
**Acceptance:** AT-DP-122  
**Audited exact HEAD:** `820c8c03fbed169d46be969935f0377bfa8d0464`  
**Audited exact tree:** `1ea7db9be17802e7cec4d35c3e4248a1dbaea34e`  
**Audited bundle:** `phase-11.22-event-system-audit-v11.tar.gz`  
**Audited bundle SHA-256:** `e53b7942f264aaf47045d6c4a7566dc68a796ce0b99488d8561f2c34b8d03a59`  
**Result:** **FAIL — Remediation V11 required**

---

## 1. Executive verdict

Remediation V10 correctly fixes the single finding from Independent Re-audit V10.

The raw Windows **drive-root** family is now structurally rejected at a path-segment boundary:

```text
C:/Windows/System32/config/SAM
provider/C:/Windows/System32/config/SAM
cmm/C:/Windows/System32/config/SAM
provider//C:/Windows/System32/config/SAM
provider/./C:/Windows/System32/config/SAM
```

The V10 remediation regression module independently runs:

```text
475 passed
```

and all retained Phase 11.22 remediation regression modules V1–V10 independently run:

```text
1765 passed
```

However, V11 is **not closure-eligible**.

A fresh adversarial audit found a second Windows path syntax that bypasses the same canonical filesystem-reference authority: **drive-relative paths** of the form `C:name`.

Unlike a drive-root path (`C:/name`), Windows drive-relative syntax does not require a separator immediately after the colon. The current classifier therefore treats values such as:

```text
C:Windows
C:id_rsa
D:ProgramData
```

as ordinary identifiers rather than local filesystem references.

`C:id_rsa` is especially decisive: `id_rsa` is already a sensitive private-file marker in the canonical policy, but placing it behind a Windows drive designator prevents the existing filename boundary pattern from seeing it. The exact value is accepted and durably persisted.

The bypass was independently reproduced through all 13 shared identifier-bearing channels using both official repository implementations, and through manual `publish_event(...)`.

Therefore:

```text
BLOCKERS=0
MAJORS=1
MINORS=0
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
```

Phase 11.23 and Phase 11.24 must not begin.

---

## 2. Exact bundle provenance and integrity

The uploaded V11 archive was inspected directly.

Verified:

```text
BUNDLE_SHA256=e53b7942f264aaf47045d6c4a7566dc68a796ce0b99488d8561f2c34b8d03a59
GZIP_TEST=PASS
ARCHIVE_MEMBERS=2697
REGULAR_TRACKED_FILES=2566
SYMLINKS=0
ABSOLUTE_ARCHIVE_PATHS=0
TRAVERSAL_MEMBERS=0
GIT_INTERNALS=0
PAX_COMMENT=820c8c03fbed169d46be969935f0377bfa8d0464
RECONSTRUCTED_TREE=1ea7db9be17802e7cec4d35c3e4248a1dbaea34e
TREE_MATCH=PASS
```

The tree was reconstructed independently from a fresh extraction using Git object semantics and matches the declared remediation tree exactly.

### Non-finding handoff note

The implementation handoff stated `2563 files`; the actual V11 archive contains `2566` regular tracked files. The difference is the three expected tracked additions relative to V10:

```text
docs/audits/phase-11.22-event-system-independent-reaudit-v10.md
docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v10-agent-prompt.md
tests/events/test_phase11_22_remediation_v10_regressions.py
```

Because the archive reconstructs exactly to the declared Git tree, this is treated as a handoff count typo, **not** an integrity finding.

---

## 3. V10 → V11 tracked scope

Direct comparison of the exact V10 and V11 bundles gives:

```text
V10_TRACKED_FILES=2563
V11_TRACKED_FILES=2566
ADDED=3
REMOVED=0
MODIFIED=7
```

Added:

```text
docs/audits/phase-11.22-event-system-independent-reaudit-v10.md
docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v10-agent-prompt.md
tests/events/test_phase11_22_remediation_v10_regressions.py
```

Modified:

```text
ROADMAP.md
cmm/events/event_payload_safety.py
docs/audits/phase-11.22-event-system-implementation-evidence.md
docs/reference/phase-11-event-system.md
docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md
docs/roadmap/phase-11-stable-integrated-platform.md
tests/events/test_phase11_22_dp122_acceptance.py
```

No additional production file changed.

The production delta in `cmm/events/event_payload_safety.py` is the expected narrow V10 change: the existing Windows drive-root regex moved from whole-value start anchoring to a path-segment boundary.

No parallel filesystem/identifier subsystem was introduced.

---

## 4. Immutable evidence verification

Verified independently:

```text
DESIGN_SPEC_SHA256=d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40
V10_AUDIT_REPORT_SHA256=ffe8c5e7d96836643362796c5ccfae29461aaa2d1293cc9ce0a6c210f86d7a8c
V10_REMEDIATION_PROMPT_SHA256=6ad10e84b9617da955cf00727e5f9d1e987aacbab6949f8554b6692bdc28dee5
```

Historical independent audit artifacts inside the tracked V11 tree were not rewritten by this audit.

---

## 5. Independent execution evidence

The independent audit environment provides CPython 3.13.5 and does not include the repository's `libcst` dependency.

An audit-only external `libcst` import shim was used outside the extracted archive solely to unblock unrelated import-time code. It is not part of the audited tree.

Independently executed:

```text
REMEDIATION_V10_REGRESSIONS=475 passed
PRIOR_REMEDIATION_REGRESSIONS_V1_V10=1765 passed
COMPILEALL=PASS
```

The audit environment is not treated as authoritative for the reported canonical CPython 3.14 global suite or Ruff count. The implementation handoff reports:

```text
GLOBAL_PYTEST=25200 collected, 25200 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
```

Those reported gates do not override the fresh canonical persistence bypass reproduced below.

The full connected AT-DP-122 was not used as the basis of this verdict because the audit container does not reproduce the repository's full canonical dependency/runtime environment. The FAIL rests on directly executable canonical Event System behavior.

---

## 6. Verification of Independent Re-audit V10 finding

### MAJOR-V10-001 — wrapped Windows drive-root reference

The current classifier now rejects the exact reported family and structural variants.

Verified examples:

```text
C:/Windows/System32/config/SAM
D:/private/example
provider/C:/Windows/System32/config/SAM
cmm/C:/Windows/System32/config/SAM
provider//C:/Windows/System32/config/SAM
provider/./C:/Windows/System32/config/SAM
provider/D:/private/example
cmm/Z:/tmp/example
provider/c:/Windows/System32/config/SAM
```

The canonical production rule is now:

```python
re.compile(r"(?:^|/)[A-Za-z]:[\\/]")
```

rather than the V10-audited:

```python
re.compile(r"^[A-Za-z]:[\\/]")
```

Positive controls in the retained regression suite remain green.

**Verdict:**

```text
MAJOR_V10_001=FIX_VERIFIED
V10_FINDINGS_FIXED=1/1_VERIFIED
```

---

## 7. MAJOR-V11-001 — Windows drive-relative references bypass the canonical filesystem classifier

### Severity

**MAJOR**

### Violated frozen design rule

The Phase 11.22 design explicitly requires rejection/redaction of:

```text
filesystem secrets/paths where not public-safe
```

The inherited invariant currently claimed by the requirements matrix is:

```text
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
```

V11 still violates that invariant.

### Windows drive-relative syntax

Windows distinguishes:

```text
C:/name     drive-root path
C:name      drive-relative path
```

The second form is still a drive-qualified local filesystem reference; it is relative to that drive's current directory rather than rooted at its root.

Python's standard-library Windows path parser confirms the syntax independently:

```text
ntpath.splitdrive("C:Windows") = ("C:", "Windows")
ntpath.splitdrive("C:id_rsa")  = ("C:", "id_rsa")
```

The canonical Phase 11.22 classifier currently recognizes only the rooted form because the Windows pattern requires a slash/backslash after the colon.

### Exact canonical reproductions

Fresh independent probes:

```text
C:Windows
C:id_rsa
C:.ssh
D:ProgramData
Z:tmp
```

Current results include:

```text
is_private_filesystem_reference("C:Windows") = False
validate_platform_identifier("C:Windows") = ACCEPT

is_private_filesystem_reference("C:id_rsa") = False
validate_platform_identifier("C:id_rsa") = ACCEPT
```

This is not merely a naming ambiguity. `id_rsa` is already a sensitive private-file marker in `_PRIVATE_FILESYSTEM_PATTERNS`; the drive-designator colon prevents the existing `(?:^|/)id_rsa...` boundary from recognizing it.

### Canonical Event System persistence

Using:

```text
reference=C:id_rsa
```

the real canonical `EventSystem` accepted and persisted the value through **all 13 shared identifier-bearing channels**:

```text
payload_request_id             ACCEPT persisted=True
payload_workflow_id            ACCEPT persisted=True
payload_aggregate_id           ACCEPT persisted=True
payload_producer               ACCEPT persisted=True
header_producer                ACCEPT persisted=True
header_aggregate_id            ACCEPT persisted=True
header_correlation_id          ACCEPT persisted=True
header_source                  ACCEPT persisted=True
permissions                    ACCEPT persisted=True
metadata_error_type            ACCEPT persisted=True
nested_result_reference        ACCEPT persisted=True
structured_reference_sequence  ACCEPT persisted=True
domain_reference_sequence      ACCEPT persisted=True
```

### Official file-backed repository

The same 13/13 channel family was repeated with the official file-backed repository.

Every case appended durable bytes and reopened with the exact `C:id_rsa` value present.

### Manual/prebuilt canonical event

A manually constructed canonical event passed to:

```text
EventSystem.publish_event(...)
```

with `request_id=C:id_rsa` was also accepted:

```text
MANUAL_PUBLISH=ACCEPT
persisted=True
repository_count=1
subscriber_received=1
```

This proves the defect is in the shared canonical identifier authority rather than only one safe factory path.

---

## 8. Root cause

The current classifier has two assumptions that are individually reasonable for POSIX-style references but incomplete for Windows drive-relative syntax.

First, the Windows drive rule requires a separator:

```python
re.compile(r"(?:^|/)[A-Za-z]:[\\/]")
```

so:

```text
C:/Windows
```

is classified, but:

```text
C:Windows
```

is not.

Second, the final fail-closed path-shape branch says that a value carrying no separator is not path-shaped:

```text
if "/" not in masked.replace("\\", "/"):
    return False
```

That is false for Windows drive-relative references: `C:Windows` is path syntax even though it contains no slash.

The sensitive filename patterns have the same boundary blind spot:

```text
C:id_rsa
```

does not begin with `id_rsa` and does not contain `/id_rsa`, so the retained private-key filename rule never sees it.

This is a structural Windows path-classification defect, not a missing `id_rsa` literal.

---

## 9. Required Remediation V11

Remediation V11 must remain narrow and stay inside the existing canonical identifier/filesystem-safety authority.

Add and prove an invariant equivalent to:

```text
WINDOWS_DRIVE_RELATIVE_REFERENCES_NEVER_ENTER_EVENT_PERSISTENCE
```

or:

```text
WINDOWS_DRIVE_DESIGNATOR_PATHS_ARE_CLASSIFIED_BEFORE_SEPARATOR_HEURISTICS
```

### Required RED reproductions

Before production mutation, reproduce at minimum:

```text
C:Windows
C:id_rsa
C:.ssh
D:ProgramData
Z:tmp
```

through:

- direct `is_private_filesystem_reference`;
- direct `validate_platform_identifier`;
- canonical `EventSystem.publish(...)`;
- canonical manual/prebuilt `publish_event(...)`;
- official in-memory repository;
- official file-backed repository;
- all 13 shared identifier-bearing channels;
- durable-store-zero/byte-identical assertion after the eventual rejection.

### Required implementation behavior

Use the existing lexical/identifier authority only.

The implementation must structurally recognize **whole-value Windows drive-relative syntax** before the generic "no separator means not path-shaped" escape.

Do not fix this by adding:

```text
Windows
ProgramData
id_rsa
.ssh
```

or other reproduced names to a new denylist.

Do not create a second Windows-path parser/policy module.

Do not use filesystem I/O or `Path.resolve()`.

### Positive controls / inventory

Before choosing the final rule, inventory actual legitimate top-level single-letter-colon identifiers.

Preserve established canonical identifiers such as:

```text
workflow:123
domain:legal
events:read
provider/model
cmm/orchestration/step
https://example.com/model
provider/https://example.com/model
jdbc:postgresql://example.com/db
```

The V10 suite also intentionally preserves wrapped segment-colon logical references such as:

```text
provider/a:1/model
```

Do not broaden the fix to those wrapped logical forms unless the real repository inventory and canonical contract independently justify changing them.

The smallest likely correction is therefore at the **whole-value Windows drive-designator boundary**, but the implementation agent must inspect the actual authority and inventory before coding.

---

## 10. AT-DP-122 strengthening

Strengthen the existing connected acceptance:

```text
tests/events/test_phase11_22_dp122_acceptance.py
```

Do not create a replacement acceptance system.

The local V11 bundle reports the pre-remediation acceptance size as:

```text
AT_DP_122=749 passed
```

Add connected cases proving:

- top-level `C:name` drive-relative references reject;
- sensitive `C:id_rsa` rejects;
- ordinary multi-letter colon identifiers remain valid;
- in-memory persistence remains zero after rejection;
- file-backed persistence remains byte-identical after rejection;
- manual `publish_event(...)` cannot bypass the authority;
- all 13 shared channels inherit the same verdict;
- identity/correlation/causation behavior for accepted events remains unchanged.

AT-DP-122 remains **pending independent verification** after local GREEN.

---

## 11. Documentation correction required with the major

Current non-historical documentation claims:

```text
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
```

That statement is not true in the audited V11 tree because `C:id_rsa` and other drive-relative references enter durable event persistence.

Do not create a separate historical rewrite.

During Remediation V11, update current implementation evidence/reference/requirements/roadmap state only after the fix and gates are complete.

Historical independent audit reports V1–V11 remain immutable.

---

## 12. Required remediation scope

Remediation V11 may address only:

- `MAJOR-V11-001`;
- directly connected regression tests;
- AT-DP-122 strengthening;
- current non-historical documentation/evidence needed to record the remediation;
- exact-head V12 bundle metadata.

It must preserve all V1–V10 fixes.

It must not:

- begin Phase 11.23;
- begin Phase 11.24;
- close Phase 11.22;
- redesign the Event System;
- create parallel identifier/path/Windows-path infrastructure;
- rewrite historical audit reports;
- overwrite V1–V11 bundles;
- weaken positive controls or suppress tests merely to obtain green gates;
- perform unrelated repository cleanup.

Expected next artifact:

```text
phase-11.22-event-system-audit-v12.tar.gz
```

generated from the exact fully committed remediation HEAD.

---

## 13. Gate expectations for the next cycle

At minimum preserve and extend the V10 gate baseline:

```text
PRIOR_REMEDIATION_REGRESSIONS>=1765_PASS
PHASE_SUITE>=3131_PASS
AT_DP_122>=749_PASS
GLOBAL_PYTEST_FAILURES=0
GLOBAL_PYTEST_PASS_COUNT>=25200
GLOBAL_RUFF_COUNT<=810
CHANGED_FILE_RUFF=PASS
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
```

The actual passing counts should increase with the new V11 regressions.

---

## 14. DP-122 and acceptance disposition

The implementation handoff reports:

```text
AT_DP_122=749 passed
GLOBAL_PYTEST=25200 passed, 0 failed
```

and the independent audit verifies the full retained V1–V10 remediation regression family:

```text
1765 passed
```

Those results are valuable but cannot verify DP-122 while the canonical shared identifier authority still permits a non-public Windows filesystem reference into durable persistence.

Therefore:

```text
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
```

---

## 15. Final audit markers

```text
INDEPENDENT_REAUDIT_V11=FAIL
V10_FINDINGS_FIXED=1/1_VERIFIED

BLOCKERS=0
MAJORS=1
MINORS=0

MAJOR_V11_001=WINDOWS_DRIVE_RELATIVE_REFERENCE_BYPASSES_CANONICAL_FILESYSTEM_CLASSIFIER_AND_PERSISTS

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V11_ONLY
EXPECTED_NEXT_BUNDLE=phase-11.22-event-system-audit-v12.tar.gz
```
