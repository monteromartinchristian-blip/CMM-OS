# CMM OS — Phase 11.22 Event System — Independent Re-audit V13

**Audit type:** Independent ChatGPT re-audit  
**Phase:** 11.22 — Event System  
**Design Point:** DP-122  
**Acceptance:** AT-DP-122  
**Audited exact HEAD:** `d6294daf4e9c90a5cc0cf246181b1089cc606cb0`  
**Audited exact tree:** `b6ffd03fb7136f49a6b85f5439da2ccceaceb7a8`  
**Audited bundle:** `phase-11.22-event-system-audit-v13.tar.gz`  
**Audited bundle SHA-256:** `21006a0e92ae57773a6eafc4b6a7aab3ef15722d83a51d3ddaa143b4f8b8e930`  
**Result:** **FAIL — Remediation V13 required**

---

## 1. Executive verdict

Remediation V12 correctly fixes the single finding from Independent Re-audit V12.

The canonical filesystem/identifier authority now rejects the audited sensitive-private-filename equivalence family:

```text
ID_RSA
KNOWN_HOSTS
Id_Ed25519.pub
id_rsa:stream
known_hosts:ads
id_ed25519:foo
id_ecdsa:data
provider/ID_RSA
provider/id_rsa:stream
cmm/known_hosts:ads
```

while preserving the narrow positive controls, including:

```text
workflow:123
domain:legal
events:read
provider/a:1/model
cmm/v2:3/detail
foo.txt:stream
provider/foo.txt:stream
provider/model
https://example.com/model
provider/https://example.com/model
jdbc:postgresql://example.com/db
```

Independent execution confirms:

```text
REMEDIATION_V12_REGRESSIONS=916 passed
PRIOR_REMEDIATION_REGRESSIONS_V1_V12=3389 passed
ARCHITECTURE_AND_SECURITY=294 passed
AT_DP_122_COLLECTION=1039
COMPILEALL=PASS
```

However, V13 is **not closure-eligible**.

A fresh adversarial audit found one new structural bypass in the same canonical filesystem-reference authority:

> **Windows trailing-period path-component normalization is not represented by the lexical classifier.**

The classifier already declares directory components such as `.ssh`, `.aws`, `.gnupg`, `.kube`, `.docker`, `.azure`, `Users`, and `home` private/sensitive. But under ordinary Win32 path normalization, trailing periods on a path segment are stripped. Therefore a spelling such as:

```text
provider/.ssh./config
```

is a Windows-equivalent spelling of the already-sensitive:

```text
provider/.ssh/config
```

Yet V13 gives them opposite safety verdicts:

```text
provider/.ssh/config   -> REJECT
provider/.ssh./config  -> ACCEPT + persist
```

The accepted spelling was independently persisted through all **13 shared identifier-bearing channels**, in both official repositories, and through manual/prebuilt `publish_event(...)`.

Fresh direct probes show the same structural gap for multiple already-canonical sensitive path families:

```text
provider/.aws./config
provider/.gnupg./trustdb.gpg
provider/.kube./config
provider/.docker./config.json
provider/.azure./profile
provider/Users./alice/config
provider/home./alice/config
cmm/.ssh./config
cmm/Users./alice/config
```

A second, documentary finding is also present: `ROADMAP.md`'s current next-action line still points to a V11 re-audit and the Phase 11 summary table omits the V12 failure/remediation state.

Therefore:

```text
BLOCKERS=0
MAJORS=1
MINORS=1
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
```

Phase 11.23 and Phase 11.24 must not begin.

---

## 2. Exact bundle provenance and integrity

The uploaded V13 archive was inspected directly.

Verified:

```text
BUNDLE_SHA256=21006a0e92ae57773a6eafc4b6a7aab3ef15722d83a51d3ddaa143b4f8b8e930
GZIP_TEST=PASS
ARCHIVE_MEMBERS=2703
REGULAR_TRACKED_FILES=2572
SYMLINKS=0
HARDLINKS=0
ABSOLUTE_ARCHIVE_PATHS=0
TRAVERSAL_MEMBERS=0
GIT_INTERNALS=0
PAX_COMMENT=d6294daf4e9c90a5cc0cf246181b1089cc606cb0
RECONSTRUCTED_TREE=b6ffd03fb7136f49a6b85f5439da2ccceaceb7a8
TREE_MATCH=PASS
```

The tree was independently reconstructed from the archive bytes and executable modes using Git object semantics.

A fresh repository reconstruction required `git add -f` because one tracked archive member is ignored by repository ignore rules; with tracked-ignore semantics preserved, the reconstructed tree matches the declared exact tree.

---

## 3. V12 → V13 tracked scope

Direct comparison of the exact V12 and V13 audit bundles gives:

```text
V12_TRACKED_FILES=2569
V13_TRACKED_FILES=2572
ADDED=3
REMOVED=0
MODIFIED=7
```

Added:

```text
docs/audits/phase-11.22-event-system-independent-reaudit-v12.md
docs/superpowers/prompts/2026-09-29-phase-11.22-remediation-v12-agent-prompt.md
tests/events/test_phase11_22_remediation_v12_regressions.py
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

The production delta is narrow and matches the declared V12 remediation: the existing sensitive-private-filename signature now uses `re.IGNORECASE` and accepts `:` as a suffix boundary.

No parallel path, ADS, URI, identifier, event-bus, repository, replay, or policy subsystem was introduced.

---

## 4. Immutable evidence verification

Verified independently:

```text
DESIGN_SPEC_SHA256=d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40
V12_AUDIT_REPORT_SHA256=926a9fb3ca1df72c8f8c27b5746aac9001147d262f2bb762e96576f9130204b8
V12_REMEDIATION_PROMPT_SHA256=f82164fa76749c844c2629077fe3fe1d08817de6e9d877b17c19acc548ffa533
```

Historical independent audit reports were not rewritten by this independent audit.

The V12 bundle available in the audit environment also re-hashes exactly to:

```text
c46e717a916c80cd6ffce7ba54e08896cc3826ba6d4b5a1a4ac460d46330bd2a
```

and the V11 bundle available in the environment re-hashes exactly to:

```text
e53b7942f264aaf47045d6c4a7566dc68a796ce0b99488d8561f2c34b8d03a59
```

---

## 5. Independent execution environment

The independent audit environment provides:

```text
CPYTHON=3.13.5
RUFF=UNAVAILABLE
LIBCST=NOT_INSTALLED
```

The repository's unrelated Python-editing import chain requires `libcst`. To execute the canonical Event System tests without mutating the audited tree, an **audit-only external `libcst` import shim** was placed outside the extracted archive.

The shim is not part of the product tree and does not implement or replace Event System behavior.

Independently executed:

```text
tests/events/test_phase11_22_remediation_v12_regressions.py
  916 passed

all tests/events/test_phase11_22_remediation_v*_regressions.py
  3389 passed

tests/events/test_phase11_22_architecture.py
tests/events/test_phase11_22_security.py
  294 passed

tests/events/test_phase11_22_dp122_acceptance.py --collect-only
  1039 collected

compileall cmm kernel
  PASS
```

A full connected AT-DP-122 run is not treated as authoritative in this container. The real-composition fixture fails before Phase 11.22 behavior is exercised because this audit environment reproduces the previously observed unrelated `DomainReasoningRuleDefinition` class-identity/super error:

```text
TypeError:
super(type, obj): obj (instance of DomainReasoningRuleDefinition)
is not an instance or subtype of type (DomainReasoningRuleDefinition)
```

The implementation handoff reports the canonical repository environment as:

```text
GLOBAL_PYTEST=27114 collected, 27114 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
```

Those reported gates are consistent with the retained test suite, but they cannot override the fresh canonical persistence bypass below.

---

## 6. Verification of Independent Re-audit V12 finding

### MAJOR-V12-001 — Windows-sensitive private-filename equivalents

The exact audited V12 family is fixed.

Independent direct probes:

```text
ID_RSA                    REJECT
KNOWN_HOSTS               REJECT
Id_Ed25519.pub            REJECT
id_rsa:stream             REJECT
known_hosts:ads           REJECT
provider/ID_RSA           REJECT
provider/id_rsa:stream    REJECT
```

Positive controls remain accepted:

```text
foo.txt:stream
provider/foo.txt:stream
workflow:123
```

The canonical production signature is now:

```python
re.compile(
    r"(?:^|[\\/])(?:id_rsa|id_dsa|id_ecdsa|id_ed25519|known_hosts)(?:$|[.:])",
    re.IGNORECASE,
)
```

The dedicated V12 remediation suite independently runs:

```text
916 passed
```

and the entire retained remediation family V1–V12 independently runs:

```text
3389 passed
```

**Verdict:**

```text
MAJOR_V12_001=FIX_VERIFIED
V12_FINDINGS_FIXED=1/1_VERIFIED
```

---

## 7. MAJOR-V13-001 — Win32 trailing-period path-component equivalents bypass the canonical filesystem classifier

### Severity

**MAJOR**

### Violated inherited invariants

The frozen design requires rejection/redaction of:

```text
filesystem secrets/paths where not public-safe
```

The current Phase 11.22 evidence additionally claims:

```text
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION=PASS
```

V13 violates both.

### External platform-semantic check

Microsoft's Win32 path documentation confirms that ordinary Windows path normalization removes trailing periods/spaces from path segments unless normalization is explicitly disabled through extended/opt-out path semantics.

Microsoft's Windows file/folder naming guidance likewise records that file/folder names ending in an ASCII period are handled without the trailing period in normal Windows naming behavior.

The Phase 11.22 classifier already models Win32 drive, UNC, case-insensitive filename and NTFS named-stream semantics, so this is not an unrelated platform expansion: it is another path-equivalence rule inside the platform semantics the authority already claims to classify.

### Existing canonical sensitive path families

The current canonical policy already classifies these directory/path segments as private or sensitive:

```text
.ssh
.aws
.gnupg
.kube
.docker
.azure
Users
home
Documents and Settings
```

Representative signatures include:

```python
re.compile(
    r"(?:^|[\\/])(?:\.ssh|\.aws|\.gnupg|\.kube|\.docker|\.azure|\.netrc"
    r"|\.pgpass|\.npmrc|\.git-credentials)(?:[\\/]|$)",
    re.IGNORECASE,
)

re.compile(
    r"(?:^|[\\/])(?:Users|home|Documents and Settings)[\\/]",
    re.IGNORECASE,
)
```

The canonical lexical analysis collapses repeated separators and exact `.` segments, but it does **not** fold a trailing period off an otherwise named path segment.

### Exact contradictory verdicts

Fresh direct probes:

```text
provider/.ssh/config       private=True   REJECT
provider/.ssh./config      private=False  ACCEPT

provider/Users/alice/config   private=True   REJECT
provider/Users./alice/config  private=False  ACCEPT
```

The same bypass occurs under both public logical roots:

```text
provider/.ssh./config   ACCEPT
cmm/.ssh./config        ACCEPT
provider/Users./alice/config  ACCEPT
cmm/Users./alice/config       ACCEPT
```

### Fresh structural family

The issue is not specific to `.ssh`.

Fresh independent probes accepted by V13:

```text
provider/.ssh./config
provider/.SSH./config
provider/.aws./config
provider/.gnupg./trustdb.gpg
provider/.kube./config
provider/.docker./config.json
provider/.azure./profile
provider/Users./alice/config
provider/users./alice/config
provider/home./alice/config
provider/.ssh../config
provider/Users../alice/config
```

The equivalent canonical spellings without the trailing period remain rejected.

### All 13 shared identifier-bearing channels

Using the canonical reference:

```text
provider/.ssh./config
```

the real canonical `EventSystem` independently accepted and persisted the value in all **13/13** shared identifier-bearing channels:

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

The same 13/13 shared-channel probe was repeated with the official file-backed repository.

Every case appended durable bytes.

Representative result:

```text
reference=provider/.ssh./config
repository_count=1
durable_bytes_added>0
```

### Manual/prebuilt canonical event

A directly constructed canonical event passed through:

```text
EventSystem.publish_event(...)
```

with:

```text
request_id=provider/.ssh./config
```

was independently accepted and persisted.

The file-backed store was reopened and retained the exact unsafe value:

```text
REOPENED_REQUEST_ID=provider/.ssh./config
```

This is therefore a real shared-authority persistence defect, not a theoretical path-classifier discrepancy.

---

## 8. Root cause

The V12 private-filename remediation is correct and is not the source of this finding.

The root cause is in the canonical lexical path analysis.

V8 introduced one pure analysis form that currently performs:

- `\` → `/`;
- repeated-separator collapse;
- exact `.` segment elision;
- `..` detection before elision;
- no filesystem I/O;
- no `Path.resolve()`.

That analysis does not model Win32 trailing-period segment normalization.

Therefore:

```text
provider/.ssh./config
```

retains a canonical segment:

```text
.ssh.
```

rather than the Windows-equivalent sensitive segment:

```text
.ssh
```

The private-directory pattern does not match `.ssh.`, and the final slash-root allowlist sees only the outer root `provider`, so it declares the entire reference public-safe.

The same mechanism affects `Users.` / `home.` and other already-declared sensitive directory components.

This is a structural canonicalization gap, not a missing filename or directory literal.

---

## 9. Required Remediation V13

Remediation V13 must remain inside the existing canonical filesystem/identifier authority.

Add and prove an invariant equivalent to:

```text
WINDOWS_TRAILING_PERIOD_PATH_COMPONENT_EQUIVALENTS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION
```

and preserve:

```text
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
```

### Required RED reproductions

Before production mutation, reproduce at minimum:

```text
provider/.ssh./config
cmm/.ssh./config
provider/.aws./config
provider/.kube./config
provider/Users./alice/config
cmm/Users./alice/config
provider/.ssh../config
provider/Users../alice/config
```

through:

- direct `is_private_filesystem_reference`;
- direct `validate_platform_identifier`;
- canonical `EventSystem.publish(...)`;
- manual/prebuilt `EventSystem.publish_event(...)`;
- official in-memory repository;
- official file-backed repository;
- all 13 shared identifier-bearing channels;
- durable store unchanged / byte-identical after the eventual rejection;
- reopened file-backed repository contains no rejected value.

### Required implementation behavior

Use the existing `_analyze_lexical_path()` / canonical filesystem safety authority.

Do not create a second Win32 normalizer or path-policy module.

The smallest structural repair should make the **analysis-only canonical form** account for trailing ASCII periods on path components before sensitive-path pattern evaluation / public-root classification, while preserving the existing rule that traversal is detected from the raw segment sequence before normalization can hide it.

Do not mutate accepted persisted identifiers.

Do not use filesystem I/O.

Do not use `Path.resolve()`.

Do not add audited literals such as:

```text
.ssh.
Users.
.aws.
.kube.
```

to the pattern tuple.

Do not broaden the public-root allowlist.

The safe identifier grammar already rejects ASCII spaces, so this finding does not require widening the grammar to handle trailing-space spellings.

### Positive controls

Preserve at minimum:

```text
provider/model
cmm/orchestration/step
provider/release./v1
cmm/version./node
provider/.sshx./config
provider/Usersx./alice/config
workflow:123
domain:legal
events:read
foo.txt:stream
provider/foo.txt:stream
https://example.com/model
provider/https://example.com/model
jdbc:postgresql://example.com/db
```

Also preserve every V1–V12 rejection.

---

## 10. MINOR-V13-001 — ROADMAP.md current Phase 11.22 navigation remains stale

### Severity

**MINOR**

The detailed Phase 11.22 line in `ROADMAP.md` was updated through Re-audit V12 and the V13 bundle.

Two current navigation surfaces were not synchronized:

```text
ROADMAP.md:30
```

still says:

```text
the next step is a fresh independent ChatGPT re-audit of the exact-HEAD
Phase 11.22 V11 bundle
```

although V13 is the bundle under audit.

And:

```text
ROADMAP.md:69
```

still summarizes Phase 11.22 as failed only through Re-audit V11 and remediated after those audits, omitting the V12 failure/remediation state.

This does not change runtime behavior, but it makes the current top-level project roadmap internally inconsistent.

Required remediation:

- update current `ROADMAP.md` navigation/summary only;
- do not rewrite any historical independent audit report;
- after Remediation V13, point the current state to the V14 independent re-audit handoff.

---

## 11. AT-DP-122 strengthening

Strengthen only the existing connected acceptance:

```text
tests/events/test_phase11_22_dp122_acceptance.py
```

The audited V13 state reports:

```text
AT_DP_122=1039 passed
```

Add connected acceptance proving:

- `.ssh.` Windows-equivalent segment rejects behind `provider/` and `cmm/`;
- `Users.` / `home.` Windows-equivalent segment rejects behind the public roots;
- repeated trailing-period forms are classified identically where ordinary Win32 normalization removes those trailing periods;
- all 13 shared identifier channels inherit the same verdict;
- official in-memory repository remains unchanged after rejection;
- official file-backed repository remains byte-identical;
- reopened store contains no rejected value;
- manual/prebuilt `publish_event(...)` cannot bypass the authority;
- nearby non-equivalent logical identifiers remain valid;
- V1–V12 safety regressions remain green.

AT-DP-122 remains pending independent verification after local GREEN.

---

## 12. Required remediation scope

Remediation V13 may address only:

- `MAJOR-V13-001`;
- `MINOR-V13-001`;
- directly connected regression tests;
- AT-DP-122 strengthening;
- current non-historical documentation/evidence needed to record the remediation;
- exact-head V14 bundle metadata.

It must preserve every V1–V12 fix.

It must not:

- begin Phase 11.23;
- begin Phase 11.24;
- close Phase 11.22;
- redesign the Event System;
- create parallel path/Win32 normalization infrastructure;
- rewrite historical audit reports;
- overwrite V1–V13 bundles;
- weaken positive controls or suppress tests;
- perform unrelated repository cleanup.

Expected next artifact:

```text
phase-11.22-event-system-audit-v14.tar.gz
```

generated from the exact fully committed remediation HEAD.

---

## 13. Gate expectations for the next cycle

At minimum preserve and extend the V12 baseline:

```text
PRIOR_REMEDIATION_REGRESSIONS>=3389_PASS
PHASE_SUITE>=5045_PASS
AT_DP_122>=1039_PASS
GLOBAL_PYTEST_FAILURES=0
GLOBAL_PYTEST_PASS_COUNT>=27114
GLOBAL_RUFF_COUNT<=810
CHANGED_FILE_RUFF=PASS
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
```

Actual counts should increase with the new V13 regression/acceptance cases.

---

## 14. Architecture review

No evidence was found that Remediation V12 introduced:

- a second event bus;
- a second mutable event registry;
- a second repository contract;
- a second replay owner;
- a second DLQ;
- a second filesystem policy module;
- a second identifier validator;
- an ADS registry/parser;
- a new composition container.

The production change remains confined to:

```text
cmm/events/event_payload_safety.py
```

The V13 FAIL is therefore a correctness gap inside the existing shared lexical safety authority, not a request for architectural replacement.

---

## 15. DP-122 and acceptance disposition

The implementation handoff reports:

```text
AT_DP_122=1039 passed
GLOBAL_PYTEST=27114 passed, 0 failed
```

and independent execution verifies:

```text
V12_REMEDIATION_TESTS=916 passed
PRIOR_REMEDIATION_REGRESSIONS_V1_V12=3389 passed
ARCHITECTURE_AND_SECURITY=294 passed
```

Those results cannot independently verify DP-122 while the canonical identifier authority still gives opposite verdicts to Windows-equivalent spellings of already-private filesystem components and persists the unsafe equivalent through every shared channel.

Therefore:

```text
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
```

---

## 16. Final audit markers

```text
INDEPENDENT_REAUDIT_V13=FAIL
V12_FINDINGS_FIXED=1/1_VERIFIED

BLOCKERS=0
MAJORS=1
MINORS=1

MAJOR_V13_001=WIN32_TRAILING_PERIOD_PATH_COMPONENT_EQUIVALENTS_BYPASS_CANONICAL_FILESYSTEM_CLASSIFIER_AND_PERSIST
MINOR_V13_001=ROADMAP_CURRENT_PHASE11_22_NAVIGATION_STALE_AFTER_REAUDIT_V12

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V13_ONLY
EXPECTED_NEXT_BUNDLE=phase-11.22-event-system-audit-v14.tar.gz
```
