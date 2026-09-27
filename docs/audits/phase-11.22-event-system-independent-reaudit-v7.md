# Phase 11.22 — Event System — Independent Re-audit V7

**Project:** CMM OS
**Phase:** 11.22 — Event System
**Audit:** Independent ChatGPT Re-audit V7
**Audited branch:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `8caa4b922f674fd5ef4a3452c2a55ddaad13ca8d`
**Audited tree:** `b3dd2d510a1f3b0daae075ae6e56652f3432c521`
**Bundle:** `phase-11.22-event-system-audit-v7.tar.gz`
**Bundle SHA-256:** `c388ea63ba885e415703ab771174f3413276092bf65358142b8e3a0c1c4bfe01`
**Design Point:** `DP-122`
**Connected acceptance:** `AT-DP-122`

## Verdict

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

Phase 11.22 remains open.

Phase 11.23 must not begin.

---

# 1. Exact V7 bundle provenance

Independent verification of the uploaded V7 archive:

```text
AUDIT_V7_SHA256=
c388ea63ba885e415703ab771174f3413276092bf65358142b8e3a0c1c4bfe01

GZIP_INTEGRITY=PASS
TAR_INTEGRITY=PASS

PAX_COMMIT=
8caa4b922f674fd5ef4a3452c2a55ddaad13ca8d

RECONSTRUCTED_TREE=
b3dd2d510a1f3b0daae075ae6e56652f3432c521

RECONSTRUCTED_TRACKED_FILE_COUNT=2554
ARCHIVE_ENTRY_COUNT=2685
SYMLINK_COUNT=0
PATH_TRAVERSAL_ARCHIVE_HITS=0
GIT_INTERNAL_PATH_HITS=0
```

The tree was independently reconstructed from the archive using a fresh Git index and exactly matches the declared remediation tree.

Historical independent reports embedded in V7 remain byte-identical:

```text
V1_AUDIT_REPORT_SHA256=
3d259b8ee9dd56d00da35d19d53670d625b399c35bff70e3ccd76e681beb1cb1

V2_REAUDIT_REPORT_SHA256=
20357eb6da9890900c8e8dc86c104d8b0559e8504c18afb67846147f51e5b771

V3_REAUDIT_REPORT_SHA256=
34969a29b49630e42762f17667383c3e05d3c7bafa4666bc430602723c1bf0c8

V4_REAUDIT_REPORT_SHA256=
ca025aae4896a629f5d9acd2904622b8282036228ff905b856feb41647afb0f9

V5_REAUDIT_REPORT_SHA256=
26baac2bd57055543a00abe8d37078ae14ce39c8a231e0134ca006922be6e98c

V6_REAUDIT_REPORT_SHA256=
1a4174bc4623e2f2d25d6a02988927cfafc2de0b5b63bd6c214d458f3563c1ab

DESIGN_SPEC_SHA256=
d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
HISTORICAL_AUDIT_EVIDENCE_PRESERVED=PASS
```

---

# 2. V6 remediation scope review

The V6 remediation remains architecturally narrow.

Production changes are confined to the existing Phase 11.22 authorities:

```text
cmm/events/event_payload_safety.py
cmm/events/event_system.py
cmm/events/kernel_adapter.py
```

No second event bus, registry, repository protocol, replay engine, DLQ authority, payload-safety subsystem, identity authority or timestamp subsystem was introduced.

Independent architecture/dependency checks:

```text
EVENT_ARCHITECTURE_AND_DEPENDENCY_TESTS=38 passed
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
ARCHITECTURE_DIRECTION=PASS
REMEDIATION_SCOPE_CONTROL=PASS
```

---

# 3. Independent executable verification

The independent audit environment does not contain all project development dependencies.

Unavailable:

```text
libcst
ruff
```

A minimal audit-only `libcst` import shim was used solely to allow unrelated package imports while exercising the event subsystem. It was outside the audited tree and did not modify the archive.

Independent executable evidence:

```text
V6_REMEDIATION_REGRESSIONS=127 passed
V1_TO_V6_REMEDIATION_REGRESSIONS=477 passed
PHASE9_RUNTIME_EVENT_BUS=222 passed
EVENT_ARCHITECTURE_AND_DEPENDENCY=38 passed
EVENT_SUITE_WITHOUT_CONNECTED_DP_ACCEPTANCE=
  1092 passed
  2 audit-environment permission failures
COMPILEALL=PASS
```

The two event-suite failures were the existing tests that expect a chmod-0500 directory to be unwritable. The independent container executes with root-like filesystem privileges, so those tests cannot reproduce normal-user macOS permission semantics.

The connected `AT-DP-122` composition could not be rerun unchanged in this environment because the audit-only import shim interacts with unrelated domain package import identity. The committed V7 implementation evidence reports:

```text
AT-DP-122=177 passed
GLOBAL_PYTEST=23340 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
```

The FAIL verdict below does not rely on any unavailable dependency, shim artifact or unexecuted acceptance. Both V7 findings were reproduced directly through the public canonical `EventSystem` and official file-backed repository.

---

# 4. V6 concrete findings are fixed — 4/4

## V6-001 — numeric lifecycle bounds / repository parity

Independent checks confirmed:

```text
count=10**5000 -> rejected in-memory
count=10**5000 -> rejected file-backed
count=-1 -> rejected
duration_ms=-5 -> rejected
attempts=-1 -> rejected
sequence=-1 -> rejected
duration_ms=1e308 -> rejected
count=2**63-1 -> accepted
count=2**63 -> rejected
```

Result:

```text
V6_001_NUMERIC_BOUNDS=PASS
V6_001_REPOSITORY_PARITY=PASS
```

## V6-002 — audited filesystem path cases

The exact V6 path reproductions (`file://`, absolute POSIX home paths, Windows drive paths, user-home / `.ssh` paths) now fail closed through the tested identifier channels.

Result:

```text
V6_002_EXACT_PATH_REPRODUCTIONS=PASS
```

The fresh V7 finding below is a separate uncovered relative/traversal path shape.

## V6-003 — canonical header authority

Independent checks confirmed conflicts now fail closed for:

```text
event_id
correlation_id
causation_id
producer
event_type
schema_version
```

Sensitivity behavior is canonical:

```text
header internal + payload restricted -> header restricted
header restricted + payload internal -> header restricted
payload duplicate removed
```

Result:

```text
V6_003_CANONICAL_HEADER_AUTHORITY=PASS
```

## V6 minor — civil timestamp validity

Independent checks confirmed:

```text
9999-99-99T99:99Z -> rejected
2026-02-31T12:00Z -> rejected
2026-09-27T25:61Z -> rejected
2026-09-27T12:00 -> rejected

2026-09-27T12:00:00Z -> accepted
2026-09-27T12:00:00+02:00 -> accepted
```

Result:

```text
V6_MINOR_TIMESTAMP_VALIDITY=PASS
```

Therefore:

```text
V6_CONCRETE_FINDINGS_FIXED=4/4_VERIFIED
```

---

# 5. MAJOR-V7-001 — relative path traversal and sensitive filesystem references bypass path safety

## Frozen requirement

The Phase 11.22 design requires the platform event boundary to reject/redact:

```text
filesystem secrets/paths where not public-safe
```

The V6 remediation added a syntactic filesystem classifier covering several strong path signatures.

## Affected authority

Primary area:

```text
cmm/events/event_payload_safety.py
```

The current private-filesystem patterns detect:

```text
file: URI
Windows drive-root
UNC share
absolute POSIX path
~ path
Users/home/Documents and Settings segments
selected private directories such as .ssh
selected private-key filenames
```

But they do not recognize path traversal segments or a broader relative sensitive path shape.

## Independent reproduction

The identifier:

```text
safe/../../etc/shadow
```

passes `validate_platform_identifier()`.

It was then independently published through the public Phase 11.22 path and durably stored through **every tested persisted identifier channel**:

```text
payload.request_id
header.producer
metadata.error_type
header.permissions[]
```

Independent result:

```text
payload      ACCEPTED  count=1  persisted=True
producer     ACCEPTED  count=1  persisted=True
metadata     ACCEPTED  count=1  persisted=True
permissions  ACCEPTED  count=1  persisted=True
```

Additional relative/network-path-shaped references such as:

```text
private/var/db/keychains
nfs://server/etc/shadow
smb://server/share/private
```

also pass the current identifier safety gate.

The traversal reproduction is sufficient to establish the defect: `../` is a filesystem path semantic, not a legitimate platform identifier separator.

## Why this is major

V6's path hardening is correct for its exact cases, but the invariant remains incomplete.

A producer can avoid the path classifier merely by prefixing a sensitive relative traversal with an apparently safe identifier segment.

The exact sensitive path string then enters durable event evidence.

This violates a frozen privacy rule and affects all persisted identifier channels because they intentionally share one authority.

## Required Remediation V7

Extend the **existing** identifier/path safety authority.

Do not add a second path-policy module.

At minimum reject:

```text
slash-delimited or backslash-delimited `..` traversal segments
relative traversal that resolves toward a local/system path
strong relative sensitive-system path signatures where unambiguous
```

Required permanent regressions:

```text
safe/../../etc/shadow -> reject
foo/../bar/../../private/var -> reject
same traversal in producer -> reject
same traversal in metadata identifier -> reject
same traversal in permissions -> reject
same traversal in structured reference identifiers -> reject
durable file remains unchanged
```

Preserve legitimate references already demonstrated by current producers, including:

```text
workflow:123
domain:legal
provider/model
cmm.orchestration
events:read
```

Do not perform filesystem I/O or path resolution against the host.

This remains syntactic safety classification.

---

# 6. MAJOR-V7-002 — URI userinfo credentials can enter persisted identifier fields

## Frozen requirement

Phase 11.22 requires:

```text
secrets and credentials never enter event persistence or DLQ data
```

and inherits the canonical credential/private-content policy.

## Problem

The identifier grammar deliberately permits characters needed by URI/reference forms:

```text
:
/
@
```

The existing high-confidence credential scanner catches explicit secret markers and known token formats, but it does not treat **URI userinfo password syntax** as a credential structure.

Therefore a URI containing:

```text
scheme://username:password@host
```

can qualify as a safe identifier even though the password component is explicit credential material.

## Independent durable reproductions

Both of these references were accepted:

```text
https://admin:hunter2hunter2@example.com/path
postgres://alice:supersecret@example.com/db
```

and were durably persisted unchanged.

Independent results:

```text
payload request_id:
https://admin:hunter2hunter2@example.com/path
ACCEPTED=True
PERSISTED=True

header producer:
https://admin:hunter2hunter2@example.com/path
ACCEPTED=True
PERSISTED=True

payload request_id:
postgres://alice:supersecret@example.com/db
ACCEPTED=True
PERSISTED=True

header producer:
postgres://alice:supersecret@example.com/db
ACCEPTED=True
PERSISTED=True
```

The same shared identifier authority is also used by permissions, metadata identifier facts and nested structured references.

## Why this is major

This is not an arbitrary-secret guessing problem.

URI userinfo syntax gives the platform a strong structural signal that a string contains an explicit password/credential:

```text
scheme://user:secret@host
```

Persisting that value directly contradicts the closure-critical security invariant that credentials never enter event persistence.

The generic high-confidence credential detector is not sufficient by itself for identifier/reference syntax that explicitly admits `:`, `/` and `@`.

## Required Remediation V7

Extend the **existing** identifier/reference safety authority with a narrow URI-userinfo credential check.

Do not create a second credential policy.

At minimum reject accepted identifier strings matching the semantic form:

```text
<scheme>://<userinfo-name>:<userinfo-secret>@<host-or-authority>
```

before persistence.

Required regressions:

```text
https://admin:hunter2hunter2@example.com/path -> reject
postgres://alice:supersecret@example.com/db -> reject
same value in producer -> reject
same value in permissions -> reject
same value in metadata identifier -> reject
same value in nested reference -> reject
durable file remains unchanged
```

Control legitimate references without embedded credentials:

```text
https://example.com/model
provider/model
workflow:123
domain:legal
```

if supported by the current producer inventory.

Do not log or echo the detected credential value in a persisted rejection artifact.

---

# 7. Security/privacy assessment

Positive V7 results:

```text
binary buffer policy = PASS
raw prose relocation exact V5 reproduction = PASS
bounded numeric facts = PASS
exact V6 absolute/home filesystem cases = PASS
canonical header conflict handling = PASS
timestamp semantic validity = PASS
DLQ fail-safe category = PASS
raw exception text excluded from canonical DLQ = PASS
```

Fresh failures:

```text
RELATIVE_FILESYSTEM_TRAVERSAL_SAFETY=FAIL
URI_USERINFO_CREDENTIAL_SAFETY=FAIL
```

Therefore:

```text
FULL_CANONICAL_EVENT_SECURITY=FAIL
FILESYSTEM_PRIVACY_INVARIANT=FAIL
CREDENTIAL_PERSISTENCE_INVARIANT=FAIL
```

---

# 8. Persistence/canonicalization assessment

Positive:

```text
official repository numeric parity = PASS
structured payload canonicalization = PASS
content-bound fingerprint = PASS
same-ID/different-content fail closed = PASS
manual sensitivity normalization = PASS
canonical header semantic uniqueness = PASS
supported-schema gate = PASS
snapshot/alias isolation regressions = PASS
```

The two V7 findings are public-boundary classification failures: the file-backed repository correctly persists values that should have been rejected earlier.

---

# 9. Replay and DLQ assessment

No fresh replay/DLQ defect was found.

The V5 direct-bus fail-safe remains fixed.

Prior targeted replay and detached-DLQ regression suites remain green in the independent remediation run.

Result:

```text
REPLAY_AUTHORITY=PASS
DLQ_AUTHORITY=PASS
DIRECT_BUS_FAIL_SAFE=PASS
```

---

# 10. DP-122 assessment

DP-122 requires the one canonical event path to preserve privacy and prevent secret/path material from entering durable lifecycle evidence.

V7 closes all four V6 findings.

However independent V7 execution proves that:

1. a sensitive relative filesystem traversal remains acceptable and durable through the shared identifier authority;
2. explicit URI userinfo credentials remain acceptable and durable through that same authority.

Therefore:

```text
DP-122=NOT_VERIFIED
```

---

# 11. AT-DP-122 assessment

The committed V7 evidence reports:

```text
AT-DP-122=177 passed
```

and the V6 cases are represented.

But the connected acceptance does not establish the newly reproduced cases:

```text
relative `..` filesystem traversal in persisted identifiers
URI userinfo credentials in persisted identifiers
```

Because direct independent behavior still contradicts frozen DP-122 privacy/security invariants:

```text
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
```

This does not assert that the 177 committed tests themselves fail.

It means the acceptance remains incomplete relative to the frozen design point.

---

# 12. Required Remediation V7 scope

Remediation V7 must fix **only**:

```text
MAJOR-V7-001
MAJOR-V7-002
```

Preserve all V1–V6 fixes.

Do not redesign Phase 11.22.

Do not begin Phase 11.23 or 11.24.

---

# 13. Required new regressions

At minimum:

```text
safe/../../etc/shadow rejected before persistence
relative traversal rejected in producer
relative traversal rejected in metadata identifier
relative traversal rejected in permissions
relative traversal rejected in structured reference identifiers

https://admin:hunter2hunter2@example.com/path rejected
postgres://alice:supersecret@example.com/db rejected
URI userinfo credential rejected in producer
URI userinfo credential rejected in permissions
URI userinfo credential rejected in metadata identifier
URI userinfo credential rejected in structured reference identifiers

legitimate workflow/domain/provider references remain accepted
legitimate credential-free URI reference remains accepted if current contract supports it
```

Retain every V1–V6 remediation regression.

---

# 14. Required gates after Remediation V7

Before another independent audit:

1. new V7 regressions;
2. all V1 remediation regressions;
3. all V2 remediation regressions;
4. all V3 remediation regressions;
5. all V4 remediation regressions;
6. all V5 remediation regressions;
7. all V6 remediation regressions;
8. full `tests/events/`;
9. strengthened `AT-DP-122`;
10. Phase 9 runtime-event suite;
11. Phase 10.33 Domain Event suite/acceptance;
12. Orchestration/Validation/Workflow connected regressions;
13. closed Phase 11 acceptance gates;
14. complete event inventory;
15. global pytest;
16. changed-file Ruff;
17. global Ruff no-new-debt relative to `810`;
18. format;
19. compileall;
20. `git diff --check`;
21. architecture anti-fragmentation gates;
22. event-security gates;
23. tracked worktree clean.

No unrelated cleanup.

---

# 15. Historical artifacts remain immutable

Do not modify or overwrite:

```text
phase-11.22-event-system-audit-v1.tar.gz
phase-11.22-event-system-audit-v2.tar.gz
phase-11.22-event-system-audit-v3.tar.gz
phase-11.22-event-system-audit-v4.tar.gz
phase-11.22-event-system-audit-v5.tar.gz
phase-11.22-event-system-audit-v6.tar.gz
phase-11.22-event-system-audit-v7.tar.gz

docs/audits/phase-11.22-event-system-independent-audit-v1.md
docs/audits/phase-11.22-event-system-independent-reaudit-v2.md
docs/audits/phase-11.22-event-system-independent-reaudit-v3.md
docs/audits/phase-11.22-event-system-independent-reaudit-v4.md
docs/audits/phase-11.22-event-system-independent-reaudit-v5.md
docs/audits/phase-11.22-event-system-independent-reaudit-v6.md
```

Historical bundle hashes:

```text
V1=a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3
V2=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04
V3=27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589
V4=18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f
V5=105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10
V6=67b27f6effa5297757453aba3021a7211fe4ee88e194a6d65eefa353060f1008
V7=c388ea63ba885e415703ab771174f3413276092bf65358142b8e3a0c1c4bfe01
```

This V7 report becomes immutable historical evidence once committed.

---

# 16. Next bundle

After Remediation V7 create:

```text
phase-11.22-event-system-audit-v8.tar.gz
```

from the exact committed remediation HEAD using `git archive`.

Report:

```text
HEAD
TREE
SHA-256
TRACKED_WORKTREE=CLEAN
```

Do not overwrite V7.

---

# 17. Final V7 audit markers

```text
PHASE=11.22
INDEPENDENT_REAUDIT_V7=FAIL

AUDIT_HEAD=8caa4b922f674fd5ef4a3452c2a55ddaad13ca8d
AUDIT_TREE=b3dd2d510a1f3b0daae075ae6e56652f3432c521
AUDIT_BUNDLE=phase-11.22-event-system-audit-v7.tar.gz
AUDIT_BUNDLE_SHA256=c388ea63ba885e415703ab771174f3413276092bf65358142b8e3a0c1c4bfe01

BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
ARCHITECTURE_DIRECTION=PASS

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
