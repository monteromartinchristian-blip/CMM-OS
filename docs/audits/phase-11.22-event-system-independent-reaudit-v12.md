# CMM OS — Phase 11.22 Event System — Independent Re-audit V12

**Audit type:** Independent ChatGPT re-audit  
**Phase:** 11.22 — Event System  
**Design Point:** DP-122  
**Acceptance:** AT-DP-122  
**Audited exact HEAD:** `3799118cf0a0af40520cfd268e4eaafca502d6d2`  
**Audited exact tree:** `1105b4be2973f34a164156a9317576b52228c5dc`  
**Audited bundle:** `phase-11.22-event-system-audit-v12.tar.gz`  
**Audited bundle SHA-256:** `c46e717a916c80cd6ffce7ba54e08896cc3826ba6d4b5a1a4ac460d46330bd2a`  
**Result:** **FAIL — Remediation V12 required**

---

## 1. Executive verdict

Remediation V11 correctly fixes the finding from Independent Re-audit V11.

The canonical identifier/filesystem authority now rejects the audited Windows drive-relative family:

```text
C:Windows
C:id_rsa
C:.ssh
D:ProgramData
Z:tmp
C:
c:id_rsa
X:foo.bar
```

while preserving the audited positive controls, including:

```text
workflow:123
domain:legal
events:read
provider/a:1/model
cmm/v2:3/detail
provider/model
cmm/orchestration/step
https://example.com/model
provider/https://example.com/model
jdbc:postgresql://example.com/db
```

Independent execution confirms:

```text
REMEDIATION_V11_REGRESSIONS=708 passed
PRIOR_REMEDIATION_REGRESSIONS_V1_V11=2473 passed
ARCHITECTURE_AND_SECURITY=294 passed
COMPILEALL=PASS
```

However, V12 is **not closure-eligible**.

A fresh adversarial audit found a new structural gap in the same canonical filesystem-reference authority: the known sensitive private-key filename signature is **case-sensitive and not aware of Windows NTFS alternate-data-stream (`filename:stream`) suffixes**.

Consequently, references such as:

```text
ID_RSA
KNOWN_HOSTS
Id_Ed25519.pub
id_rsa:stream
known_hosts:ads
provider/id_rsa:stream
cmm/known_hosts:ads
```

are accepted as identifiers and can enter durable event persistence.

The `id_rsa:stream` form was independently persisted through **all 13 shared identifier-bearing channels**, with both official repositories, and through manual/prebuilt `publish_event(...)`.

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

The uploaded V12 archive was inspected directly.

Verified:

```text
BUNDLE_SHA256=c46e717a916c80cd6ffce7ba54e08896cc3826ba6d4b5a1a4ac460d46330bd2a
GZIP_TEST=PASS
ARCHIVE_MEMBERS=2700
REGULAR_TRACKED_FILES=2569
SYMLINKS=0
ABSOLUTE_ARCHIVE_PATHS=0
TRAVERSAL_MEMBERS=0
GIT_INTERNALS=0
PAX_COMMENT=3799118cf0a0af40520cfd268e4eaafca502d6d2
RECONSTRUCTED_TREE=1105b4be2973f34a164156a9317576b52228c5dc
TREE_MATCH=PASS
```

The tree was independently reconstructed using Git object semantics from the archive bytes and executable modes. It matches the declared remediation tree exactly.

---

## 3. V11 → V12 tracked scope

Direct comparison of the exact V11 and V12 audit bundles gives:

```text
V11_TRACKED_FILES=2566
V12_TRACKED_FILES=2569
ADDED=3
REMOVED=0
MODIFIED=7
```

Added:

```text
docs/audits/phase-11.22-event-system-independent-reaudit-v11.md
docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v11-agent-prompt.md
tests/events/test_phase11_22_remediation_v11_regressions.py
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

The production delta is narrow: one whole-value Windows drive-designator signature was added to the existing canonical `_PRIVATE_FILESYSTEM_PATTERNS` authority.

---

## 4. Immutable evidence verification

Verified independently:

```text
DESIGN_SPEC_SHA256=d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40
V11_AUDIT_REPORT_SHA256=2936efb2a17a45838379c586b9ba34d31c158a14091b99d30b9bb6f3094534e2
V11_REMEDIATION_PROMPT_SHA256=5c6d6b16dc5f9cfbcfba3db101c94f30484982b8cd4af6fe47d87db5a649ef19
```

Historical independent audit artifacts were not rewritten by this audit.

---

## 5. Independent execution environment

The independent audit environment provides CPython 3.13.5 and does not contain the repository's `libcst` dependency.

An audit-only external `libcst` import shim was used outside the extracted archive solely to unblock unrelated import-time code. It is not part of the audited product tree.

Independently executed:

```text
tests/events/test_phase11_22_remediation_v11_regressions.py
  708 passed

all remediation regression modules V1–V11
  2473 passed

tests/events/test_phase11_22_architecture.py
tests/events/test_phase11_22_security.py
  294 passed

AT-DP-122 collection
  889 collected

compileall
  PASS
```

A complete `tests/events/` run is not considered authoritative in this audit container because a root-user filesystem-permission test cannot reproduce macOS permission denial and the connected AT hits the previously observed environment-specific domain-definition identity failure.

The implementation handoff reports the canonical project environment as:

```text
GLOBAL_PYTEST=26048 collected, 26048 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
```

Those reported gates do not override the fresh canonical persistence bypass reproduced below.

---

## 6. Verification of Independent Re-audit V11 finding

### MAJOR-V11-001 — Windows drive-relative reference

The exact reported family is now rejected by the shared canonical authority.

Independent public-surface probes confirm:

```text
C:Windows     REJECT
C:id_rsa      REJECT
C:.ssh        REJECT
D:ProgramData REJECT
Z:tmp         REJECT
C:            REJECT
c:id_rsa      REJECT
X:foo.bar     REJECT
```

The canonical production rule is:

```python
re.compile(r"^[A-Za-z]:")
```

and the prior V10 wrapped drive-root rule remains:

```python
re.compile(r"(?:^|/)[A-Za-z]:[\\/]")
```

The real inventory claim was also checked independently: no Python string literal matching a top-level single-letter-colon form occurs in `cmm/` or `kernel/`; the `scripts/` hits are Ruff-code-prefix strings rather than event identifiers.

Positive controls remain accepted and persist normally.

**Verdict:**

```text
MAJOR_V11_001=FIX_VERIFIED
V11_FINDINGS_FIXED=1/1_VERIFIED
```

---

## 7. MAJOR-V12-001 — Windows private-filename equivalents bypass the canonical classifier

### Severity

**MAJOR**

### Violated frozen invariant

The Phase 11.22 design requires the platform event path to reject/redact:

```text
filesystem secrets/paths where not public-safe
```

The current requirements matrix additionally claims:

```text
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
```

V12 still violates that invariant.

### Existing sensitive-filename authority

The canonical filesystem policy already treats these as sensitive private filenames:

```text
id_rsa
id_dsa
id_ecdsa
id_ed25519
known_hosts
```

through this retained pattern:

```python
re.compile(
    r"(?:^|[\\/])(?:id_rsa|id_dsa|id_ecdsa|id_ed25519|known_hosts)(?:$|\.)"
)
```

The pattern has two Windows-semantic blind spots:

1. it is case-sensitive;
2. its terminal boundary recognizes end-of-string or `.` but not the NTFS named-stream separator `:`.

### Case-equivalent bypass

Fresh independent probes:

```text
ID_RSA
KNOWN_HOSTS
Id_Ed25519.pub
provider/ID_RSA
cmm/KNOWN_HOSTS
```

Current canonical results:

```text
is_private_filesystem_reference(...) = False
validate_platform_identifier(...) = ACCEPT
EventSystem.publish(...) = ACCEPT
persisted=True
```

On ordinary Windows filesystem semantics, filename matching is case-insensitive by default. The safety classifier therefore gives different safety verdicts to spellings that identify the same sensitive basename.

For example:

```text
id_rsa  -> REJECT
ID_RSA  -> ACCEPT + persist
```

### NTFS alternate-data-stream bypass

Windows/NTFS also admits a named stream attached to a file via:

```text
filename:stream
```

Fresh independent probes:

```text
id_rsa:stream
known_hosts:ads
id_ed25519:foo
id_ecdsa:data
provider/id_rsa:stream
cmm/known_hosts:ads
```

Current results include:

```text
is_private_filesystem_reference("id_rsa:stream") = False
validate_platform_identifier("id_rsa:stream") = ACCEPT
EventSystem.publish(...) = ACCEPT
persisted=True
```

The colon is already legal in the platform identifier grammar, so the unsafe reference survives all later syntax validation.

### All 13 shared identifier-bearing channels

Using:

```text
reference=id_rsa:stream
```

the real canonical `EventSystem` independently accepted and persisted the value in all **13/13** shared channels:

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

The same `id_rsa:stream` probe was repeated through all 13 shared channels using the official file-backed repository.

Every case appended durable bytes.

A file-backed event was then reopened from disk and preserved the exact unsafe value:

```text
REOPENED_REQUEST_ID=id_rsa:stream
```

### Manual/prebuilt canonical event

A directly constructed canonical event passed through:

```text
EventSystem.publish_event(...)
```

with:

```text
request_id=id_rsa:stream
```

was independently accepted and persisted:

```text
MANUAL_PUBLISH=ACCEPT
repository_count=1
subscriber_received=1
```

This proves the defect is in the shared canonical identifier/filesystem authority and is not limited to one event factory.

---

## 8. Root cause

The V12 drive-relative remediation is correct and is not the source of this finding.

The fresh bypass is in the older sensitive private-filename signature:

```python
re.compile(
    r"(?:^|[\\/])(?:id_rsa|id_dsa|id_ecdsa|id_ed25519|known_hosts)(?:$|\.)"
)
```

The signature models a case-sensitive POSIX-style basename boundary but the shared safety authority is explicitly cross-platform and already contains Windows drive and UNC semantics.

As a result:

```text
id_rsa            classified private
ID_RSA            classified public

id_rsa.pub        classified private
Id_Rsa.pub        classified public

id_rsa:stream     classified public
known_hosts:ads   classified public
```

This is a structural boundary/case-semantics defect in an existing canonical pattern, not a missing literal.

---

## 9. Required Remediation V12

Remediation V12 must stay inside the existing canonical `event_payload_safety` identifier/filesystem authority.

Add and prove an invariant equivalent to:

```text
WINDOWS_SENSITIVE_PRIVATE_FILENAME_EQUIVALENTS_NEVER_ENTER_EVENT_PERSISTENCE
```

### Required RED reproductions

Before production mutation, reproduce at minimum:

```text
ID_RSA
KNOWN_HOSTS
Id_Ed25519.pub
id_rsa:stream
known_hosts:ads
provider/ID_RSA
provider/id_rsa:stream
cmm/known_hosts:ads
```

through:

- direct `is_private_filesystem_reference`;
- direct `validate_platform_identifier`;
- canonical `EventSystem.publish(...)`;
- manual/prebuilt `EventSystem.publish_event(...)`;
- official in-memory repository;
- official file-backed repository;
- all 13 shared identifier-bearing channels;
- durable store unchanged after the eventual rejection.

### Required implementation behavior

Use the existing sensitive private-filename signature only.

The remediation should make that canonical filename family:

- case-insensitive where the safety policy models Windows filesystem semantics;
- aware of the `:` named-stream boundary for those already-sensitive basenames;
- still aware of the existing `.` suffix behavior;
- structurally independent of any audited literal stream name.

Do not add new literals such as:

```text
stream
ads
ID_RSA
KNOWN_HOSTS
```

Do not create a second ADS parser, Windows-path subsystem, registry or policy module.

Do not broadly reject every colon-bearing identifier.

Preserve legitimate controls such as:

```text
workflow:123
domain:legal
events:read
provider/a:1/model
cmm/v2:3/detail
foo.txt:stream
provider/model
https://example.com/model
provider/https://example.com/model
jdbc:postgresql://example.com/db
```

The point is not to prohibit generic colon syntax. The point is that an already-sensitive private filename cannot become public-safe merely by case variation or by attaching a Windows named-stream suffix.

No filesystem I/O. No `Path.resolve()`. No grammar widening. No rewriting of accepted identifiers.

---

## 10. AT-DP-122 strengthening

Strengthen the existing connected acceptance only:

```text
tests/events/test_phase11_22_dp122_acceptance.py
```

The audited V12 state reports:

```text
AT_DP_122=889 passed
```

Add connected coverage proving:

- case-varied sensitive private filenames reject;
- `id_rsa:stream` / `known_hosts:ads` reject;
- all 13 shared channels inherit the verdict;
- both official repositories remain unchanged after rejection;
- manual `publish_event(...)` cannot bypass it;
- generic colon identifiers remain valid;
- generic non-sensitive `filename:stream` identifiers remain unchanged unless an existing policy independently forbids them;
- V1–V11 path/URI/credential/timestamp protections remain green.

---

## 11. Documentation correction required with the major

Current non-historical documentation claims:

```text
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
```

That statement is not true in the audited V12 tree because sensitive Windows filename equivalents can still enter durable persistence.

During Remediation V12, update only current implementation evidence/reference/requirements/roadmap state after the fix and gates are complete.

Historical independent audit reports V1–V12 remain immutable.

---

## 12. Required remediation scope

Remediation V12 may address only:

- `MAJOR-V12-001`;
- directly connected regression tests;
- AT-DP-122 strengthening;
- current non-historical documentation/evidence needed to record the remediation;
- exact-head V13 bundle metadata.

It must preserve every V1–V11 fix.

It must not:

- begin Phase 11.23;
- begin Phase 11.24;
- close Phase 11.22;
- redesign the Event System;
- create parallel identifier/path/ADS infrastructure;
- rewrite historical audit reports;
- overwrite V1–V12 bundles;
- broadly ban colon identifiers;
- perform unrelated repository cleanup.

Expected next artifact:

```text
phase-11.22-event-system-audit-v13.tar.gz
```

generated from the exact fully committed remediation HEAD.

---

## 13. Gate expectations for the next cycle

At minimum preserve and extend the V11 baseline:

```text
PRIOR_REMEDIATION_REGRESSIONS>=2473_PASS
PHASE_SUITE>=3979_PASS
AT_DP_122>=889_PASS
GLOBAL_PYTEST_FAILURES=0
GLOBAL_PYTEST_PASS_COUNT>=26048
GLOBAL_RUFF_COUNT<=810
CHANGED_FILE_RUFF=PASS
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
```

Actual counts should increase with the new V12 regressions.

---

## 14. DP-122 and acceptance disposition

The implementation handoff reports:

```text
AT_DP_122=889 passed
GLOBAL_PYTEST=26048 passed, 0 failed
```

and independent execution verifies the retained remediation family and architecture/security suites.

Those results cannot verify DP-122 while the canonical shared identifier authority still allows a known sensitive Windows private-file reference into durable event persistence.

Therefore:

```text
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
```

---

## 15. Final audit markers

```text
INDEPENDENT_REAUDIT_V12=FAIL
V11_FINDINGS_FIXED=1/1_VERIFIED

BLOCKERS=0
MAJORS=1
MINORS=0

MAJOR_V12_001=WINDOWS_SENSITIVE_PRIVATE_FILENAME_EQUIVALENTS_BYPASS_CANONICAL_FILESYSTEM_CLASSIFIER_AND_PERSIST

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V12_ONLY
EXPECTED_NEXT_BUNDLE=phase-11.22-event-system-audit-v13.tar.gz
```
