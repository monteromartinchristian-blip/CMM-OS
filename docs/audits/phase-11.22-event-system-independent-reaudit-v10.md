# CMM OS — Phase 11.22 Event System — Independent Re-audit V10

**Audit type:** Independent ChatGPT re-audit  
**Phase:** 11.22 — Event System  
**Design Point:** DP-122  
**Acceptance:** AT-DP-122  
**Audited exact HEAD:** `81a3a65e2b4edb3d9f2e89ead98aaf9e785cc2ef`  
**Audited exact tree:** `43d1b2efb12f71fa6dc215598074318038172849`  
**Audited bundle:** `phase-11.22-event-system-audit-v10.tar.gz`  
**Audited bundle SHA-256:** `cd594b857a0882cbc4059afbc01eb1f5d3f760c5ca7aacc1c4e9643bbae35840`  
**Result:** **FAIL — remediation V10 required**

---

## 1. Executive verdict

Remediation V9 successfully fixes both findings from Independent Re-audit V9:

- the wrapped non-authority `file:` family is now rejected through the existing canonical identifier/filesystem-safety authority;
- the frozen Phase 11.22 civil-hour contract is now interpreter-independent for `24:00` and rejects the retained V6 regression before persistence.

The V10 exact-HEAD bundle is nevertheless **not closure-eligible**.

A fresh adversarial audit found one new structural bypass in the same filesystem-reference authority: a **raw Windows drive-root reference can still be carried behind an allowlisted public slash root** and then durably persisted unchanged.

The canonical examples:

```text
provider/C:/Windows/System32/config/SAM
cmm/C:/Windows/System32/config/SAM
```

are classified as public-safe by `is_private_filesystem_reference`, accepted by `validate_platform_identifier`, and persisted by the canonical `EventSystem`.

The bypass was independently reproduced through **all 13 shared identifier-bearing channels** with the official in-memory repository and again with the official file-backed repository.

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

The uploaded V10 archive was audited directly.

Verified:

```text
BUNDLE_SHA256=cd594b857a0882cbc4059afbc01eb1f5d3f760c5ca7aacc1c4e9643bbae35840
GZIP_TEST=PASS
ARCHIVE_MEMBERS=2694
TRACKED_FILES_RECONSTRUCTED=2563
SYMLINKS=0
ABSOLUTE_ARCHIVE_PATHS=0
TRAVERSAL_MEMBERS=0
GIT_INTERNALS=0
PAX_COMMENT=81a3a65e2b4edb3d9f2e89ead98aaf9e785cc2ef
RECONSTRUCTED_TREE=43d1b2efb12f71fa6dc215598074318038172849
TREE_MATCH=PASS
```

The PAX exact-HEAD marker matches the declared remediation HEAD.

The Git tree was reconstructed independently from the archive's file bytes and executable modes using Git object hashing. It matches the declared exact tree byte-for-byte.

---

## 3. Immutable evidence verification

Verified independently:

```text
DESIGN_SPEC_SHA256=d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40
V9_AUDIT_REPORT_SHA256=f398ff360c33b8f6287b0d767e23c9557b726e54e11f1a408e91721cee05fdaf
V9_REMEDIATION_PROMPT_SHA256=0bf5e47cae6497315dff6aa4473fcd9b75ae9b79456eb866b44776f19ff0911e
```

No historical audit artifact inside the V10 tracked tree was modified by this independent audit.

The disclosed start-point detail is acceptable: `f0fbbb2d...` is the docs-only prompt commit after `ca40bf65...`. It does not alter the audited implementation lineage or invalidate the V10 provenance chain.

---

## 4. Independent execution environment

The audit environment provides CPython 3.13.5 and does not include the repository's `libcst` dependency.

To exercise the canonical Event System without modifying the audited tree, an audit-only external `libcst` import shim was placed outside the extracted archive. It exists only to unblock unrelated import-time code and is not part of the audited product tree.

Independent executable evidence:

```text
REMEDIATION_V9_REGRESSIONS=397 passed
PRIOR_REMEDIATION_REGRESSIONS_V1_V9=1290 passed
COMPILEALL=PASS
```

The full connected AT-DP-122 was not used as the basis of this verdict because the audit container does not reproduce the canonical repository dependency/runtime environment cleanly. The FAIL below is based on independently executed public canonical Event System behavior.

The implementation handoff reports the canonical CPython 3.14.7 run as:

```text
GLOBAL_PYTEST=24604 collected, 24604 passed, 1 warning, 0 failed
```

That reported gate is consistent with the V9-002 remediation, but this independent audit does not treat a reported local run as sufficient to override a fresh persistence bypass.

---

## 5. Verification of Re-audit V9 findings

### MAJOR-V9-001 — wrapped non-authority `file:` reference

Verified fixed for the reported structural family.

The current canonical classifier rejects, among others:

```text
provider/file:C:/Windows/System32/config/SAM
cmm/file:C:/Windows/System32/config/SAM
provider/file:/etc/shadow
provider//file:C:/Windows/System32/config/SAM
provider/./file:C:/Windows/System32/config/SAM
PROVIDER/FILE:C:/Windows/System32/config/SAM
```

Positive controls remain accepted:

```text
provider/model
cmm/orchestration/step
https://example.com/model
provider/https://example.com/model
jdbc:postgresql://example.com/db
workflow:file:123
req:file:mod
```

The V9 regression module independently runs:

```text
397 passed
```

**Verdict:** `MAJOR_V9_001=FIX_VERIFIED`

### MAJOR-V9-002 — interpreter-dependent `24:00`

Verified fixed in the canonical timestamp authority.

The current validator explicitly rejects:

```text
2026-09-27T24:00:00Z
```

before relying on `datetime.fromisoformat`.

Positive controls remain valid:

```text
2026-09-27T23:59:59Z
2026-09-28T00:00:00Z
```

A retained invalid-date control such as:

```text
2026-02-31T12:00:00Z
```

also remains rejected.

**Verdict:** `MAJOR_V9_002=FIX_VERIFIED`

### MINOR-V9-001 — stale current evidence

Current non-historical Phase 11.22 documentation now records the final V9 figures:

```text
tests/events/ = 2535 passed
AT-DP-122 = 628 passed
GLOBAL_PYTEST = 24604 passed, 0 failed
```

Earlier counts still appear only where the documents are narrating historical V8/V9 evidence.

**Verdict:** `MINOR_V9_001=FIX_VERIFIED`

Overall:

```text
V9_FINDINGS_FIXED=3/3_VERIFIED
```

---

## 6. MAJOR-V10-001 — Embedded Windows drive-root reference bypasses public-root classifier

### Severity

**MAJOR**

### Violated invariant

The frozen design prohibits:

> filesystem secrets/paths where not public-safe

The inherited remediation invariant is:

```text
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
```

The V10 implementation still violates that invariant.

### Independent canonical reproduction

Fresh probe:

```text
provider/C:/Windows/System32/config/SAM
```

Current classifier result:

```text
is_private_filesystem_reference(...) = False
```

Current canonical identifier result:

```text
validate_platform_identifier(...) = ACCEPT
```

Canonical Event System result:

```text
publish("message.received", {"request_id": ...}) = ACCEPT
repository.count(): 0 -> 1
persisted=True
```

The same result occurs for:

```text
cmm/C:/Windows/System32/config/SAM
provider//C:/Windows/System32/config/SAM
provider/./C:/Windows/System32/config/SAM
```

The exact spelling supplied by the producer is persisted.

### All 13 shared identifier channels

Using the real canonical `EventSystem` and official in-memory repository, the same reference was independently accepted and persisted in **13/13** shared channels:

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

The same 13/13 channel probe was repeated using the official file-backed repository.

Every case was durably appended:

```text
payload_request_id             ACCEPT count=1 durable_bytes_added
payload_workflow_id            ACCEPT count=1 durable_bytes_added
payload_aggregate_id           ACCEPT count=1 durable_bytes_added
payload_producer               ACCEPT count=1 durable_bytes_added
header_producer                ACCEPT count=1 durable_bytes_added
header_aggregate_id            ACCEPT count=1 durable_bytes_added
header_correlation_id          ACCEPT count=1 durable_bytes_added
header_source                  ACCEPT count=1 durable_bytes_added
permissions                    ACCEPT count=1 durable_bytes_added
metadata_error_type            ACCEPT count=1 durable_bytes_added
nested_result_reference        ACCEPT count=1 durable_bytes_added
structured_reference_sequence  ACCEPT count=1 durable_bytes_added
domain_reference_sequence      ACCEPT count=1 durable_bytes_added
```

This is therefore a real persistence defect, not a classifier-only theoretical concern.

### Root cause

The existing Windows drive-root rule remains anchored only at the start of the entire canonical reference:

```python
re.compile(r"^[A-Za-z]:[\\/]")
```

Remediation V9 correctly moved the `file:` rule from whole-value start to a **path-segment boundary**:

```python
re.compile(r"(?:^|/)file:", re.IGNORECASE)
```

but the structurally equivalent drive-root case was not given equivalent treatment.

Because `provider` and `cmm` are public slash roots, the current flow becomes:

```text
provider/C:/Windows/...
        ↓
not traversal
not absolute at whole-value start
drive-root regex misses because "C:/" is not at character zero
public root = provider
        ↓
accepted as public-safe
        ↓
persisted
```

The defect is not the literal filename `SAM`. It is the ability for an allowlisted logical wrapper to carry an embedded raw drive-root filesystem reference.

### Additional structural evidence

The same public-root mechanism also admits path-shaped suffixes such as:

```text
provider/proc/self/environ
provider/Windows/System32/config/SAM
provider/Library/Keychains/login.keychain-db
```

Those examples reinforce that the allowlist applies to the outer root and does not by itself prove the suffix is public-safe.

The mandatory remediation finding, however, does **not** require classifying every slash-bearing provider identifier as private. The concrete major can be closed by making raw local-drive semantics impossible to hide behind a public wrapper while preserving the real product reference inventory.

### Required remediation

Remediation V10 must stay inside the existing canonical identifier/filesystem safety authority.

At minimum add and prove:

```text
WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_DRIVE_ROOT_REFERENCES
```

Required behavior:

```text
C:/Windows/System32/config/SAM                         REJECT
provider/C:/Windows/System32/config/SAM                REJECT
cmm/C:/Windows/System32/config/SAM                     REJECT
provider//C:/Windows/System32/config/SAM               REJECT
provider/./C:/Windows/System32/config/SAM              REJECT
```

Do not fix this by adding `SAM`, `Windows/System32`, or other audited filenames/directories to a denylist.

The remediation should structurally recognize a Windows drive-root token at a valid path-segment boundary, analogous to the V9 `file:` fix, or use an equally narrow canonical rule in the existing authority.

Preserve:

```text
provider/model
cmm/orchestration/step
workflow:123
domain:legal
https://example.com/model
provider/https://example.com/model
jdbc:postgresql://example.com/db
```

Do not widen the identifier grammar.

Do not create a second filesystem policy.

Do not mutate the persisted spelling of accepted identifiers.

No filesystem I/O or `Path.resolve()`.

### Required TDD proof

Before production mutation, add RED tests that demonstrate the exact fresh bypass.

Required surfaces:

- direct filesystem classifier;
- direct canonical identifier validator;
- canonical `EventSystem`;
- official in-memory repository;
- official file-backed repository;
- manual/prebuilt `publish_event(...)` if the existing V9 pattern used that surface;
- all 13 shared identifier-bearing channels;
- durable store remains byte-identical on rejection;
- positive controls remain accepted.

Strengthen the existing AT-DP-122 rather than creating a new acceptance system.

---

## 7. Architecture review

No evidence was found that Remediation V9 introduced a second event bus, registry, repository, replay owner, identifier subsystem, URI registry, filesystem-policy module, or timestamp parser.

The production remediation remains centered on:

```text
cmm/events/event_payload_safety.py
```

The V10 FAIL is therefore a correctness defect in the existing shared safety authority, not an architecture replacement request.

---

## 8. DP-122 and AT-DP-122 disposition

The local implementation evidence reports:

```text
AT_DP_122=628 passed
```

and the prior remediation regression family independently executes as:

```text
1290 passed
```

Nevertheless, DP-122 cannot be independently verified while a non-public local filesystem reference can still enter canonical durable event persistence through the shared identifier authority.

Therefore:

```text
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
```

The acceptance result is not being dismissed; it is incomplete because the fresh adversarial path is absent from the current AT.

---

## 9. Required scope for Remediation V10

Remediation V10 must be narrow.

It may address only:

- `MAJOR-V10-001`;
- directly connected regression tests;
- AT-DP-122 coverage;
- current implementation evidence/reference/roadmap state necessary to record the remediation;
- exact-head V11 bundle metadata.

It must preserve all V1–V9 fixes.

It must not:

- begin Phase 11.23;
- begin Phase 11.24;
- close Phase 11.22;
- redesign the Event System;
- create a parallel path/URI/identifier authority;
- rewrite historical audit reports;
- overwrite V1–V10 audit bundles;
- use unrelated repository cleanup as part of this remediation;
- suppress or weaken existing tests.

Expected next bundle:

```text
phase-11.22-event-system-audit-v11.tar.gz
```

generated from the fully committed exact remediation HEAD.

---

## 10. Final audit markers

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
