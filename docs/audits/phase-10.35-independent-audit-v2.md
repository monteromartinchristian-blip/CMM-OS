# CMM OS — Phase 10.35 Domain SDK — Independent Audit V2

```text
FINAL_INDEPENDENT_AUDIT_V2=FAIL
BLOCKERS=0
MAJORS=1
MINORS=0
AUDITED_HEAD=018b98d44228c8c924a103b2dd234800e04d84a3
AUDIT_BUNDLE_SHA256=5d7b8df1a58938ee7b4067d09e09fba7f9306e51d2865ea3b20bd824d47e6c4e
DP_035=NOT_YET_VERIFIED
AT_DP_035=NOT_YET_PASS
CLOSURE_ELIGIBLE=NO
```

## 1. Artifact integrity

The uploaded V2 artifact was independently verified before source review.

```text
BUNDLE=phase-10.35-audit-v2.tar.gz
SHA256=5d7b8df1a58938ee7b4067d09e09fba7f9306e51d2865ea3b20bd824d47e6c4e
SHA256_MATCHES_AGENT_REPORT=YES
GZIP_INTEGRITY=PASS
EMBEDDED_GIT_HEAD=018b98d44228c8c924a103b2dd234800e04d84a3
EMBEDDED_HEAD_MATCHES_AGENT_REPORT=YES
ARCHIVE_MEMBERS=1936
UNSAFE_ABSOLUTE_OR_DOTDOT_MEMBERS=0
```

The tar PAX metadata is therefore bound to the exact claimed Git commit.

---

## 2. Independent verification performed

### 2.1 Phase 10.34 binding

The restored V10 validator itself matches its historical audited source hash exactly:

```text
tests/domains/domain_session_audit_evidence.py
CURRENT_SHA256=14ae126d53867bd3facafb179cf79329082b5637df933c7388d832db2a7cca87
V10_EXPECTED_SHA256=14ae126d53867bd3facafb179cf79329082b5637df933c7388d832db2a7cca87
MATCH=YES
```

The later Phase 10.35 source correctly does not pretend to match V10:

```text
cmm/__main__.py=POST_V10_SOURCE
cmm/domains/validation_context.py=POST_V10_SOURCE
```

The V10 regression module was independently executed:

```text
tests/domains/test_domain_session_audit_v10_binding_regressions.py
4 passed
```

A second independent mutation probe, outside the repository's test assertions, produced:

```text
mutate cmm/__main__.py
-> REJECTED: source hash mismatch

mutate cmm/domains/validation_context.py
-> REJECTED: source hash mismatch

mutate tests/domains/domain_session_audit_evidence.py
-> REJECTED: source hash mismatch
```

B1 from V1 is therefore remediated.

### 2.2 Domain Test Harness

Source inspection confirms:

```text
canonical FileSystemDomainDiscovery / JsonDomainManifestReader / validation reused
DeclarativeDomainLoader reused
real DomainPack returned in DomainHarnessContext
target registered in isolated DomainRegistry
DomainStatus.REGISTERED asserted
definition.enabled == False asserted
permission registry initially empty
two harnesses use independent registry instances
cmm domain test calls DomainTestHarness.prepare() before pytest
```

B2 from V1 is therefore remediated.

### 2.3 External pack identity

Verified in implementation and tests:

```text
ManifestBuilder default=DomainPackKind.EXTERNAL
basic_domain manifest pack_kind=external
explicit EXPERIMENTAL override preserved
```

M1 from V1 is therefore remediated.

### 2.4 Documentation and traceability

Verified:

```text
ROADMAP: Phase 10.35 implemented; independent re-audit pending
ROADMAP: Phase 10.35 remains current milestone until audit/closure
detailed Phase 10.35 roadmap: manifest.json canonical
detailed roadmap: create/validate/test/pack are delivered Phase 10.35 CLI
detailed roadmap: broader install/enable/publish/resolve/trace surface deferred
requirements matrix: DP-035 present
requirements matrix: AT-DP-035 present
status=IMPLEMENTED_PENDING_AUDIT
Phase 10.36 not started
```

M2 from V1 is therefore remediated.

### 2.5 Additional invariant checks

Independent source-level verification:

```text
COMPILEALL_FULL_TREE=PASS
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
DOMAIN_SESSION_RESUMED_EVENT=ABSENT
SDK_PARALLEL_REGISTRY_SCAN=CLEAN
SDK_PARALLEL_RESOLVER_SCAN=CLEAN
SDK_PARALLEL_WORKFLOW_ENGINE_SCAN=CLEAN
SDK_PARALLEL_PERMISSION_ENGINE_SCAN=CLEAN
SDK_SHELL_TRUE_SCAN=CLEAN
SDK_OS_SYSTEM_SCAN=CLEAN
SDK_PLACEHOLDER_SCAN=CLEAN
```

### 2.6 Sandbox dependency limitation

The independent auditor environment does not contain repository dependency `libcst`.

Focused SDK pytest collection therefore fails before SDK tests execute with:

```text
ModuleNotFoundError: No module named 'libcst'
```

This is an auditor-environment limitation and is not counted as a repository finding.

The implementation-agent counts:

```text
FOCUSED_SDK_TESTS=54 passed
PHASE10_34_BINDING_REGRESSIONS=156 passed
DOMAIN_SUITE=8353 passed
FULL_SUITE=13908 passed
RUFF=PASS
FORMAT=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
```

are recorded as implementation evidence, not misrepresented as independently rerun global-suite evidence.

---

# 3. V1 finding disposition

```text
V1_B1_AUDIT_BINDING=REMEDIATED
V1_B2_REAL_HARNESS_PREPARATION=REMEDIATED
V1_M1_EXTERNAL_PACK_KIND=REMEDIATED
V1_M2_DOCS_TRACEABILITY=REMEDIATED
```

No V1 finding remains open.

---

# 4. New V2 finding

## V2-M1 — DomainPackager can overwrite unrelated existing files and even destroy source-pack files

**Severity:** MAJOR

### Affected code

```text
cmm/domains/sdk/packager.py
```

Current output handling:

```python
if output is not None:
    out_path = Path(output).resolve()
else:
    out_path = (root.parent / f"{root.name}.tar.gz").resolve()

out_path.parent.mkdir(parents=True, exist_ok=True)
temp_out = out_path.with_suffix(f"{out_path.suffix}.tmp")

collected_items = self._collect_items(
    root,
    excluded_paths=frozenset({out_path, temp_out}),
)

...
temp_out.replace(out_path)
```

There is no protection against an existing unrelated destination and no requirement that the output path actually be a `.tar.gz` path.

### Independent reproduction A — unrelated file overwrite

The audited `DomainPackager` module was executed directly in an isolated stubbed environment so the missing `libcst` dependency could not mask its filesystem behavior.

Input:

```text
pack_root=<valid temporary source directory>
output=<existing important-not-an-archive.txt>
existing bytes="DO NOT OVERWRITE"
```

Result:

```text
OVERWROTE_EXISTING_UNRELATED=True
OLD_BYTES=b'DO NOT OVERWRITE'
NEW_PREFIX=1f 8b ...  # gzip
```

The existing unrelated file is silently replaced.

### Independent reproduction B — source pack corruption

Input:

```text
output=<pack_root>/manifest.json
```

Result:

```text
MANIFEST_NOW_GZIP=True
ARCHIVE_NAMES=['README.md']
MANIFEST_INCLUDED=False
```

The packager:

1. validates the pack while `manifest.json` is still valid;
2. excludes `manifest.json` from the archive because it is the selected output;
3. writes the gzip archive over the source manifest;
4. returns success with an archive that no longer contains the required manifest;
5. leaves the source Domain Pack corrupted.

This is a direct filesystem safety defect.

### Contract violated

The approved Phase 10.35 design requires:

```text
Developer tooling accepts filesystem paths and therefore MUST treat them as untrusted input.

At minimum Phase 10.35 MUST protect against:
- overwrite of unrelated existing files;
...
Filesystem safety specific to scaffolding and packaging remains the SDK's responsibility.
```

The definition of done also requires relevant overwrite/archive-safety tests to pass.

### Required remediation

Do not solve this by weakening the spec or removing the in-root output tests.

Before any archive write:

1. validate the requested output path as an archive destination;
2. require the effective output filename to end in `.tar.gz`;
3. reject an output path that aliases an existing source-pack member, including through symlinks;
4. prevent silent overwrite of unrelated existing files;
5. use a deliberate policy for an existing archive destination:
   - safest Phase 10.35 default: fail closed if it already exists;
   - do not add a broad `--force` mode unless separately justified;
6. keep the temporary output outside the source inventory;
7. wrap expected filesystem `OSError`/`PermissionError` conditions into a narrow SDK `DomainPackagingError` so CLI users get a concise non-zero error rather than a traceback;
8. preserve atomic replacement only after all destination safety checks pass.

Add RED tests for at least:

```text
output path = existing unrelated .txt -> rejected, bytes unchanged
output path = pack_root/manifest.json -> rejected, manifest unchanged
output path = symlink resolving to pack_root/manifest.json -> rejected
output path = directory -> rejected cleanly
output suffix != .tar.gz -> rejected
pre-existing destination policy -> explicit, fail-closed and tested
PermissionError/OSError -> DomainPackagingError / clean CLI failure
fresh valid .tar.gz output -> PASS
fresh .tar.gz inside pack root -> remains excluded from its own inventory
determinism -> PASS
safe symlink tests -> PASS
unpack + revalidation -> PASS
```

The existing test that expects silent replacement of a pre-existing output archive should be changed if the fail-closed destination policy is adopted.

---

# 5. Non-promoted documentation hardening

This is not counted as a separate V2 finding.

`docs/reference/domain-sdk.md` currently says:

```text
Running validation, fixture loading, test execution, or packaging never mutates the global DomainRegistry, runtime sessions, or event bus.
```

SDK-owned harness preparation is isolated, but pack-owned pytest files are executable Python and are not a process sandbox.

During V2-M1 remediation, tighten this sentence so it does not imply that arbitrary third-party test code is incapable of mutating process/system state.

Suggested semantic distinction:

```text
SDK-owned validation, fixture loading, harness preparation and packaging do not mutate production Domain state.
`cmm domain test` executes developer-owned Python tests; isolation guarantees apply to the harness-provided canonical state, not to arbitrary test-code side effects.
```

No new sandbox is required by this finding.

---

# 6. Required remediation order

```text
1. RED tests for destination overwrite/source collision
2. harden DomainPackager output path policy
3. wrap expected filesystem errors as DomainPackagingError
4. update misleading test-execution isolation wording
5. focused packager + CLI tests
6. all 54+ SDK tests
7. Phase 10.34 binding regressions
8. Domain Sessions regressions
9. Event / Conflict Resolver regressions
10. tests/domains
11. full pytest suite
12. Ruff / format / compileall / diff check
13. coherent remediation commit(s)
14. clean worktree + quarantine stash preserved
15. exact-HEAD phase-10.35-audit-v3.tar.gz
```

Do not overwrite V2.

Do not start Phase 10.36.

---

# 7. V3 audit focus

The V3 auditor will independently attack:

```text
output existing unrelated file
output manifest.json
output symlink aliasing source member
output directory
invalid output extension
existing archive policy
PermissionError/OSError handling
fresh output inside/outside pack root
deterministic repeated packaging
safe and escaping symlinks
safe unpack + canonical revalidation

plus regression confirmation:
B1 V10 binding still fail-closed
B2 real harness load still intact
M1 external pack kind still intact
M2 pending-audit docs still truthful
events remain 23/23
domain.session.resumed absent
```

---

# 8. Final V2 status

```text
PHASE10_35_STATUS=REMEDIATION_REQUIRED
FINAL_INDEPENDENT_AUDIT_V2=FAIL
BLOCKERS=0
MAJORS=1
MINORS=0
DP_035=NOT_YET_VERIFIED
AT_DP_035=NOT_YET_PASS
CLOSURE_ELIGIBLE=NO
NEXT=REMEDIATE_V2_M1_AND_BUILD_V3
```

No remediation was performed during this independent audit.
No push.
No merge.
Phase 10.36 was not started.
