# Phase 11.22 — Event System — Independent Re-audit V8

**Project:** CMM OS
**Phase:** 11.22 — Event System
**Audit:** Independent ChatGPT Re-audit V8
**Audited branch:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `aadf83c44104beb096811219bc330e6e613cb18d`
**Audited tree:** `d383ba1fb0b68bbade0d91a58f0ae5db36609a3f`
**Bundle:** `phase-11.22-event-system-audit-v8.tar.gz`
**Bundle SHA-256:** `9b46ed3f941ce63c8ff2249da5762fcfe0f156f073c9864f39d3dffdac3708e9`
**Design Point:** `DP-122`
**Connected acceptance:** `AT-DP-122`

## Verdict

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

Phase 11.22 remains open.

Phase 11.23 must not begin.

---

# 1. Exact V8 bundle provenance

Independent verification of the uploaded V8 archive:

```text
AUDIT_V8_SHA256=
9b46ed3f941ce63c8ff2249da5762fcfe0f156f073c9864f39d3dffdac3708e9

GZIP_INTEGRITY=PASS
TAR_INTEGRITY=PASS

PAX_COMMIT=
aadf83c44104beb096811219bc330e6e613cb18d

RECONSTRUCTED_TREE=
d383ba1fb0b68bbade0d91a58f0ae5db36609a3f

RECONSTRUCTED_TRACKED_FILE_COUNT=2557
ARCHIVE_ENTRY_COUNT=2688
SYMLINK_COUNT=0
PATH_TRAVERSAL_ARCHIVE_HITS=0
GIT_INTERNAL_PATH_HITS=0
```

The tree was independently reconstructed from a clean extraction using a fresh Git index and exactly matches the declared remediation tree.

Historical audit reports embedded in V8 remain byte-identical:

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

V7_REAUDIT_REPORT_SHA256=
c55b2ed1a9756996270b49c80342c3c44691d536c05c50ffea70f31ee665ea3e

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

# 2. V7 remediation scope review

The V7 remediation is architecturally narrow.

The V7 → V8 production delta is confined to:

```text
cmm/events/event_payload_safety.py
```

The remaining tracked changes are tests and current evidence/reference/roadmap documentation.

No second:

- event bus;
- registry;
- repository protocol;
- replay engine;
- DLQ authority;
- identifier/path safety subsystem;
- credential subsystem

was introduced.

Independent architecture/security gates:

```text
EVENT_ARCHITECTURE_AND_SECURITY_TESTS=294 passed
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
ARCHITECTURE_DIRECTION=PASS
REMEDIATION_SCOPE_CONTROL=PASS
```

---

# 3. Independent executable verification

The independent audit environment does not contain all repository development dependencies.

Unavailable:

```text
libcst
ruff
```

A minimal audit-only `libcst` import shim was used outside the audited tree to allow unrelated package imports while executing the event subsystem.

Independent evidence against the exact V8 bytes:

```text
V7_REMEDIATION_REGRESSIONS=127 passed
V1_TO_V7_REMEDIATION_REGRESSIONS=604 passed
EVENT_ARCHITECTURE_AND_SECURITY=294 passed
COMPILEALL=PASS
```

The full connected AT-DP-122 composition cannot be rerun unchanged in this audit container: the audit-only import shim perturbs unrelated domain-class identity during full application composition.

The committed V8 implementation evidence reports:

```text
AT-DP-122=250 passed
PHASE_SUITE=1471 passed
GLOBAL_PYTEST=23540 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
```

The V8 FAIL verdict below does **not** depend on the unavailable full composition. Both majors were independently reproduced through the public canonical `EventSystem` and the official file-backed repository.

---

# 4. V7 concrete findings are fixed — 2/2

## V7-001 — audited relative traversal

The exact V7 values:

```text
safe/../../etc/shadow
foo/../bar/../../private/var
```

now fail closed.

The V7 remediation regression module independently passes:

```text
127 passed
```

and covers the shared identifier channels.

Status:

```text
V7_001_EXACT_TRAVERSAL_REPRODUCTIONS=PASS
```

## V7-002 — top-level URI userinfo credentials

The exact V7 values:

```text
https://admin:hunter2hunter2@example.com/path
postgres://alice:supersecret@example.com/db
```

now fail closed.

Status:

```text
V7_002_EXACT_URI_USERINFO_REPRODUCTIONS=PASS
```

Therefore:

```text
V7_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED
```

The V8 findings below are broader uncovered forms of the same frozen privacy/security invariants.

---

# 5. MAJOR-V8-001 — filesystem reference classifier still accepts path-equivalent and unlisted sensitive paths

## Frozen requirement

The design requires rejection/redaction of:

```text
filesystem secrets/paths where not public-safe
```

before persistence.

## Affected authority

Primary area:

```text
cmm/events/event_payload_safety.py
```

Current path safety is implemented as a tuple of regex signatures.

The V7 remediation correctly added:

- `..` traversal-segment detection;
- selected relative `etc/*` sensitive files;
- selected `private/*` roots.

But the classifier operates on the raw identifier text rather than a lexical path representation.

Equivalent path spellings therefore bypass individual regexes.

## Independent durable reproductions

The following identifiers are accepted:

```text
safe/etc//shadow
safe/etc/./shadow
safe/private//var/db/keychains
safe/private/./var/db/keychains
```

Every one was independently persisted through the official file-backed repository.

For example:

```text
payload.request_id = safe/etc//shadow
```

produced:

```text
ACCEPTED
repository.count() == 1
exact value present in durable JSON == True
```

The same value was independently accepted and persisted through:

```text
payload identifier
header producer
metadata.error_type
permissions[]
nested result_reference.reference_id
```

So the issue is in the shared identifier authority, not one producer.

## Independent broader sensitive-path probes

Additional unmistakably filesystem-oriented sensitive/system references still pass the current validator, for example:

```text
proc/self/environ
etc/ssh/ssh_host_rsa_key
Windows/System32/config/SAM
Library/Keychains/login.keychain-db
```

This demonstrates that the current approach is still a denylist of selected spellings rather than a fail-closed classification of non-public filesystem references.

## Why this is major

This is a direct privacy invariant.

V7 fixed the audited `..` spelling but not the semantic class.

A producer can still place a non-public filesystem reference into durable event evidence by using:

- repeated separators;
- `.` current-directory segments;
- another strong sensitive filesystem path absent from the current regex list.

The official durable repository then faithfully persists it.

## Required Remediation V8

Fix this inside the **existing identifier/path safety authority**.

Do not create a second path policy.

At minimum, classification must be performed on a **pure lexical canonical form** used only for safety analysis:

```text
normalize repeated path separators
elide `.` current-directory segments
detect/reject `..` traversal segments before any elision
do not touch the host filesystem
do not call Path.resolve()
do not perform I/O
```

Then apply the private-filesystem classification to that canonical form.

Required permanent regressions:

```text
safe/etc//shadow -> reject
safe/etc/./shadow -> reject
safe/private//var/db/keychains -> reject
safe/private/./var/db/keychains -> reject

same cases in producer -> reject
same cases in metadata identifier -> reject
same cases in permissions -> reject
same cases in nested structured references -> reject

durable repository remains unchanged on rejection
```

The remediation must also address the broader fail-closed problem rather than only add four more exact regexes.

After a real inventory of current producers, either:

1. define/document the small set of slash-bearing **public-safe logical reference forms** actually needed by CMM OS and reject other path-like references; or
2. implement an equivalently fail-closed classifier that proves strong local/system paths such as the independently observed examples cannot persist.

Legitimate current controls must remain valid:

```text
workflow:123
domain:legal
provider/model
cmm.orchestration
events:read
credential-free supported URI references
```

Required invariant:

```text
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION
```

---

# 6. MAJOR-V8-002 — wrapped or nested URI userinfo credentials bypass identifier safety

## Frozen requirement

The security invariant is unconditional:

```text
secrets and credentials never enter event persistence or DLQ data
```

## Affected authority

Primary area:

```text
cmm/events/event_payload_safety.py
```

The V7 remediation introduced:

```text
contains_uri_userinfo_credential()
```

using an anchored pattern equivalent to:

```text
^[scheme]://userinfo@
```

This correctly closes the exact V7 top-level URI cases.

But the credential structure is only recognized when the authority-bearing URI starts at character zero.

## Independent durable reproduction

A common wrapped connection URL:

```text
jdbc:postgresql://alice:supersecret@example.com/db
```

passes the identifier validator.

It was independently persisted through every tested shared identifier channel:

```text
payload.request_id
header.producer
metadata.error_type
permissions[]
nested result_reference.reference_id
```

Result for each:

```text
ACCEPTED
repository.count() == 1
credential-bearing value present in durable JSON == True
```

A second common connection URL also passes:

```text
jdbc:mysql://root:hunter2hunter2@example.com/db
```

Additional structurally equivalent forms accepted by the current detector include prefixed/nested authority-bearing values such as:

```text
provider/https://alice:supersecret@example.com/db
foo:https://alice:supersecret@example.com/db
```

The exact top-level control remains correctly rejected:

```text
postgresql://alice:supersecret@example.com/db
```

## Why this is major

The frozen invariant is about credentials, not only RFC URIs beginning at offset zero.

The structural credential signal remains explicit:

```text
:// username : password @ authority
```

A wrapper such as JDBC does not make the password safe to persist.

This is especially important because connection URLs are a normal real-world credential container.

## Required Remediation V8

Extend the **existing identifier/reference safety authority**.

Do not create a second credential subsystem.

The safety check must inspect authority-bearing URI structures occurring inside accepted identifier/reference forms, not only a URI anchored at the first character.

At minimum reject:

```text
jdbc:postgresql://alice:supersecret@example.com/db
jdbc:mysql://root:hunter2hunter2@example.com/db
provider/https://alice:supersecret@example.com/db
```

where the nested/wrapped authority contains non-empty password userinfo.

A robust implementation may lexically locate each `://` authority component and inspect its authority/userinfo, or use an equivalent deterministic standard-library-assisted approach.

Requirements:

```text
credential-free URI references remain accepted where currently supported
password-bearing userinfo always rejects before persistence
percent-decoded password separators remain fail-closed
rejection messages never echo the secret
shared identifier channels all use the same one authority
```

Do not broaden into heuristic guessing of arbitrary unlabeled secrets.

This finding is specifically about explicit userinfo password structure.

Required invariant:

```text
URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_WRAPPER_OR_PREFIX
CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE
```

---

# 7. MINOR-V8-001 — ROADMAP phase summary omits Re-audit V7

The detailed Phase 11.22 roadmap state is current, but the high-level Phase 11 row in:

```text
ROADMAP.md
```

still says:

```text
11.22 Event System failed Independent Audit V1 and Re-audits V2/V3/V4/V5/V6,
and is remediated after all six pending independent re-audit
```

That is stale.

At V8 it must acknowledge Re-audit V7 as well.

This does not affect runtime correctness, but it makes the top-level roadmap inconsistent with:

- the detailed Phase 11.22 line in the same file;
- the Phase 11 detailed roadmap;
- the requirements matrix;
- the implementation evidence;
- the committed immutable V7 re-audit report.

Required correction during Remediation V8:

```text
V2/V3/V4/V5/V6/V7
all seven
```

or equivalent accurate wording.

Do not rewrite historical audit artifacts.

---

# 8. Security/privacy assessment

Positive V8 results:

```text
exact V7 traversal cases = PASS
exact V7 URI-userinfo cases = PASS
binary/buffer policy = PASS through accumulated regressions
raw-prose relocation = PASS through accumulated regressions
numeric bounds/repository parity = PASS through accumulated regressions
canonical header authority = PASS through accumulated regressions
timestamp semantic validity = PASS through accumulated regressions
DLQ fail-safe behavior = PASS through accumulated regressions
```

Fresh failures:

```text
PATH_EQUIVALENT_FILESYSTEM_SAFETY=FAIL
FAIL_CLOSED_NON_PUBLIC_PATH_CLASSIFICATION=FAIL
WRAPPED_URI_USERINFO_CREDENTIAL_SAFETY=FAIL
```

Therefore:

```text
FULL_CANONICAL_EVENT_SECURITY=FAIL
FILESYSTEM_PRIVACY_INVARIANT=FAIL
CREDENTIAL_PERSISTENCE_INVARIANT=FAIL
```

---

# 9. Persistence/canonicalization assessment

The durable repository is not the source of either V8 defect.

It correctly stores the canonical event it receives.

The failure occurs earlier: the public safety boundary classifies unsafe identifiers as safe.

Therefore:

```text
DURABLE_REPOSITORY_BEHAVIOR=CONSISTENT_WITH_INPUT
PUBLIC_IDENTIFIER_SAFETY_BOUNDARY=FAIL
```

---

# 10. Architecture/replay/DLQ assessment

No fresh architecture, replay or DLQ defect was found.

Independent architecture/security tests:

```text
294 passed
```

Result:

```text
ARCHITECTURE_DIRECTION=PASS
REPLAY_AUTHORITY=PASS
DLQ_AUTHORITY=PASS
NO_PARALLEL_EVENT_INFRASTRUCTURE_FOUND=PASS
```

---

# 11. DP-122 assessment

DP-122 requires the one canonical event path to preserve privacy and prevent secrets/non-public paths from entering durable lifecycle evidence.

V8 closes both concrete V7 findings.

However the same shared identifier authority still durably accepts:

1. semantically equivalent spellings of sensitive filesystem paths;
2. explicit password-bearing connection URLs when the URI is wrapped/prefixed.

Therefore:

```text
DP-122=NOT_VERIFIED
```

---

# 12. AT-DP-122 assessment

The committed V8 evidence reports:

```text
AT-DP-122=250 passed
```

and covers the V7 cases.

But acceptance does not establish:

```text
equivalent filesystem spellings after lexical normalization
wrapped/nested URI authority credentials
```

Direct independent public-path behavior still contradicts frozen DP-122 invariants.

Therefore:

```text
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
```

This does not assert that the 250 committed tests themselves fail.

It means the connected acceptance is still incomplete relative to the frozen design point.

---

# 13. Required Remediation V8 scope

Remediation V8 must fix **only**:

```text
MAJOR-V8-001
MAJOR-V8-002
MINOR-V8-001
```

Preserve all V1–V7 fixes.

Do not redesign Phase 11.22.

Do not begin Phase 11.23 or Phase 11.24.

---

# 14. Required new regressions

At minimum:

```text
safe/etc//shadow rejected
safe/etc/./shadow rejected
safe/private//var/db/keychains rejected
safe/private/./var/db/keychains rejected

path-equivalent cases rejected in producer
path-equivalent cases rejected in metadata identifier
path-equivalent cases rejected in permissions
path-equivalent cases rejected in nested structured references

strong non-public filesystem controls from fresh V8 probing cannot persist

jdbc:postgresql://alice:supersecret@example.com/db rejected
jdbc:mysql://root:hunter2hunter2@example.com/db rejected
provider/https://alice:supersecret@example.com/db rejected

wrapped URI credentials rejected in producer
wrapped URI credentials rejected in metadata identifier
wrapped URI credentials rejected in permissions
wrapped URI credentials rejected in nested structured references

credential-free top-level URI remains accepted where supported
legitimate workflow/domain/provider logical references remain accepted

ROADMAP high-level Phase 11 row accurately includes Re-audit V7
```

Retain every V1–V7 remediation regression.

---

# 15. Required gates after Remediation V8

Before another independent audit:

1. new V8 regressions;
2. all V1 remediation regressions;
3. all V2 remediation regressions;
4. all V3 remediation regressions;
5. all V4 remediation regressions;
6. all V5 remediation regressions;
7. all V6 remediation regressions;
8. all V7 remediation regressions;
9. full `tests/events/`;
10. strengthened `AT-DP-122`;
11. Phase 9 runtime-event suite;
12. Phase 10.33 Domain Event suite/acceptance;
13. Orchestration/Validation/Workflow connected regressions;
14. closed Phase 11 acceptance gates;
15. complete event inventory;
16. global pytest;
17. changed-file Ruff;
18. global Ruff no-new-debt relative to `810`;
19. format;
20. compileall;
21. `git diff --check`;
22. architecture anti-fragmentation gates;
23. event-security gates;
24. documentation consistency checks;
25. tracked worktree clean.

No unrelated cleanup.

---

# 16. Historical artifacts remain immutable

Do not modify or overwrite:

```text
phase-11.22-event-system-audit-v1.tar.gz
phase-11.22-event-system-audit-v2.tar.gz
phase-11.22-event-system-audit-v3.tar.gz
phase-11.22-event-system-audit-v4.tar.gz
phase-11.22-event-system-audit-v5.tar.gz
phase-11.22-event-system-audit-v6.tar.gz
phase-11.22-event-system-audit-v7.tar.gz
phase-11.22-event-system-audit-v8.tar.gz

docs/audits/phase-11.22-event-system-independent-audit-v1.md
docs/audits/phase-11.22-event-system-independent-reaudit-v2.md
docs/audits/phase-11.22-event-system-independent-reaudit-v3.md
docs/audits/phase-11.22-event-system-independent-reaudit-v4.md
docs/audits/phase-11.22-event-system-independent-reaudit-v5.md
docs/audits/phase-11.22-event-system-independent-reaudit-v6.md
docs/audits/phase-11.22-event-system-independent-reaudit-v7.md
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
V8=9b46ed3f941ce63c8ff2249da5762fcfe0f156f073c9864f39d3dffdac3708e9
```

This V8 report becomes immutable historical evidence once committed.

---

# 17. Next bundle

After Remediation V8 create:

```text
phase-11.22-event-system-audit-v9.tar.gz
```

from the exact committed remediation HEAD using `git archive`.

Report:

```text
HEAD
TREE
SHA-256
TRACKED_WORKTREE=CLEAN
```

Do not overwrite V8.

---

# 18. Final V8 audit markers

```text
PHASE=11.22
INDEPENDENT_REAUDIT_V8=FAIL

AUDIT_HEAD=aadf83c44104beb096811219bc330e6e613cb18d
AUDIT_TREE=d383ba1fb0b68bbade0d91a58f0ae5db36609a3f
AUDIT_BUNDLE=phase-11.22-event-system-audit-v8.tar.gz
AUDIT_BUNDLE_SHA256=9b46ed3f941ce63c8ff2249da5762fcfe0f156f073c9864f39d3dffdac3708e9

BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
ARCHITECTURE_DIRECTION=PASS

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
