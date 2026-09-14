# CMM OS — Phase 10.35 Domain SDK — Independent Audit V1

```text
FINAL_INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=2
MAJORS=2
MINORS=0
AUDITED_HEAD=07a7e32afc79725c0f1ca720edf3428b8ca9832f
AUDIT_BUNDLE_SHA256=1ee2c7287f9565b66f009125ee0a13b67fb108101a1e4a1b34ab1c5a4bbf6183
DP_035=NOT_YET_VERIFIED
AT_DP_035=NOT_YET_PASS
CLOSURE_ELIGIBLE=NO
```

## 1. Artifact verification

The uploaded artifact was independently checked before source review.

```text
BUNDLE=phase-10.35-audit-v1.tar.gz
SHA256=1ee2c7287f9565b66f009125ee0a13b67fb108101a1e4a1b34ab1c5a4bbf6183
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_PAX_COMMIT=07a7e32afc79725c0f1ca720edf3428b8ca9832f
ARCHIVE_MEMBERS=1934
UNSAFE_ABSOLUTE_OR_DOTDOT_MEMBERS=0
```

The SHA-256 matches the implementation agent's report.

`git get-tar-commit-id` recovered the exact audited commit from the tar PAX metadata, so the artifact is bound to a real Git commit rather than a mutable worktree snapshot.

The agent did not use the exact prefix/pipe form prescribed by Task 10, but the resulting gzip header has `mtime=0`, the archive carries the exact Git commit in PAX metadata, and no artifact-integrity defect is promoted from that procedural deviation.

## 2. Independent checks

Fresh independent checks performed against the extracted artifact:

```text
SDK_COMPILEALL=PASS
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
DOMAIN_SESSION_RESUMED_EVENT=ABSENT
```

The auditor sandbox does not contain the repository dependency `libcst`, and outbound package installation is unavailable, so a second full pytest execution could not be completed in the auditor environment. Attempts fail during import with:

```text
ModuleNotFoundError: No module named 'libcst'
```

This environment limitation is not a repository finding and is not counted below.

The implementation agent reported:

```text
tests/domains: 8340 passed
global suite: 13895 passed
```

Those counts are recorded as implementation-agent evidence, not as independently re-executed audit evidence.

The V1 failure instead rests on source inspection plus independently reproducible adversarial probes that do not depend on `libcst`.

---

# 3. Findings

## B1 — Phase 10.34 audit-source binding is explicitly bypassed for changed protected files

**Severity:** BLOCKER

### Affected code

`tests/domains/domain_session_audit_evidence.py`

The Phase 10.35 candidate changes the V10 source-binding logic in two ways.

First, `discover_source_hash_paths()` excludes all Phase 10.35 SDK implementation/tests:

```python
if not rel.startswith("cmm/domains/sdk/") and not rel.startswith(
    "tests/domains/test_domain_sdk_"
):
    paths.add(rel)
```

More seriously, `_validate_source_binding()` explicitly ignores hash mismatches for exactly these already-hashed files:

```python
if _sha256(path) != expected_file_digest:
    if relative in (
        "cmm/__main__.py",
        "cmm/domains/validation_context.py",
        "tests/domains/domain_session_audit_evidence.py",
    ):
        continue
    _fail(f"source hash mismatch: {relative}")
```

The committed Phase 10.34 V10 source manifest still contains hashes for all three files.

Therefore the validator now says the old V10 source binding remains valid even when those protected files no longer match the audited source.

The most severe exemption is the validator itself:

```text
tests/domains/domain_session_audit_evidence.py
```

A source-binding validator cannot safely exempt its own hash mismatch.

### Independent reproduction

On a temporary extracted copy of the V1 artifact:

```text
BASE_EVIDENCE=56
BASE_CLOSURE=True

# mutate cmm/__main__.py
AFTER_MAIN_MUTATION_EVIDENCE=56
AFTER_MAIN_MUTATION_CLOSURE=True

# mutate tests/domains/domain_session_audit_evidence.py
AFTER_VALIDATOR_MUTATION_EVIDENCE=56
AFTER_VALIDATOR_MUTATION_CLOSURE=True
```

This is a direct bypass of the Phase 10.34 V10 guarantee.

The V10 independent audit explicitly established:

```text
Protected change after PASS
→ current source manifest changes
→ CLOSURE_ELIGIBLE=NO
```

V1 reverses that property for selected files without a new audit binding.

### Required remediation

Do not add more exceptions.

Restore fail-closed source verification so a hashed protected file mismatch is never silently accepted.

Later-phase regression compatibility must be achieved through isolated/rebound temporary fixtures or another principled historical-evidence boundary, not by teaching the V10 validator to ignore the files changed by Phase 10.35.

At minimum add adversarial tests proving:

```text
mutate cmm/__main__.py                  -> source binding fails
mutate cmm/domains/validation_context.py -> source binding fails
mutate domain_session_audit_evidence.py -> source binding fails
```

If current-head Phase 10.34 tests need to exercise the old evidence machinery after later phases evolve, move those tests onto explicit temporary fixture state. Do not make the immutable V10 binding claim that mismatching current files still match V10.

---

## B2 — DomainTestHarness does not load the Domain Pack, and `cmm domain test` bypasses harness preparation

**Severity:** BLOCKER

### Affected code

`cmm/domains/sdk/harness.py`

`DomainTestHarness.prepare()` validates the path and allocates fresh registry objects, but never discovers/parses/loads the pack into those registries.

The returned context is hard-coded to:

```python
domain_pack=None
```

There is no `DeclarativeDomainLoader` use and no registration of the tested Domain Pack.

The registries are therefore isolated but empty.

`cmm/domains/sdk/cli.py` has the second half of the defect.

`_handle_test()` performs:

```text
validate_domain_path
→ check tests/
→ subprocess pytest
```

but never calls:

```text
DomainTestHarness.prepare(...)
```

or an equivalent isolated canonical runtime preparation.

### Why this blocks Phase 10.35

The approved spec requires:

```text
cmm domain test
1. resolve target safely
2. validate canonically
3. prepare isolated canonical runtime/test state
4. execute Domain Pack tests
5. propagate failure
```

It also defines the final lifecycle as:

```text
cmm domain test
→ isolated canonical runtime semantics
```

Current V1 only proves that empty canonical registry instances can be created.

It does not prove that the external Domain Pack is loaded into them or that its runtime identity is represented in the harness.

The DP-035 acceptance test masks this gap by asserting only that registry objects are non-`None`; it never requires `harness_ctx.domain_pack` to exist or the isolated `DomainRegistry` to contain the tested pack.

### Required remediation

Make `DomainTestHarness.prepare()` prepare the actual pack.

At minimum:

```text
canonical discovery / parsing
→ construct real DomainPack
→ isolated canonical DomainRegistry
→ canonical DeclarativeDomainLoader when loading is required
→ return context containing the actual DomainPack
→ prove registration without implicit enable/authorization
```

`cmm domain test` must invoke this preparation before launching the pack-owned pytest suite.

Add tests proving:

```text
ctx.domain_pack is not None
ctx.domain_pack.manifest/domain identity matches target pack
isolated registry contains target domain after canonical load
domain is not implicitly enabled/authorized
two harness instances remain isolated
invalid pack cannot prepare
cmm domain test actually invokes/prepares the harness
```

Do not build a second runtime or SDK registry to fix this.

---

## M1 — SDK-created external packs are labeled `pack_kind="internal"`

**Severity:** MAJOR

### Affected code

`cmm/domains/sdk/scaffold.py`

The mandatory `basic_domain` scaffold emits:

```json
"pack_kind": "internal"
```

`ManifestBuilder` also defaults to:

```python
DomainPackKind.INTERNAL
```

But the canonical enum defines `DomainPackKind` as:

> how a Domain Pack is distributed and what initial trust level it has

with explicit values:

```text
INTERNAL
EXTERNAL
EXPERIMENTAL
```

Phase 10.35's defining acceptance boundary is an external/local developer-owned pack outside `cmm/domains/<name>`.

The default SDK scaffold therefore advertises the wrong distribution/trust classification.

This is especially undesirable for a public SDK because future trust enforcement must not inherit an unsafe default in which third-party packs self-identify as internal.

### Required remediation

The external SDK scaffold and public builder default used for external developer packs must use:

```text
DomainPackKind.EXTERNAL
```

unless the caller explicitly selects a different supported kind.

Add tests proving the generated `manifest.json` parses canonically as `EXTERNAL`.

Keep `DomainKind` separate from `DomainPackKind`.

---

## M2 — Phase 10.35 implementation documentation and requirement traceability were not completed

**Severity:** MAJOR

### Evidence

`docs/roadmap/phase-10-domain-intelligence.md` still presents the historical Phase 10.35 scaffold as:

```text
manifest.yaml
```

and still lists the entire original CLI set, including installation, enablement, publication, resolution and trace commands that the approved 10.35 spec deliberately moved outside the required 10.35 boundary.

`ROADMAP.md` still states:

```text
Next milestone: Phase 10.35 — Domain SDK
```

and says implementation is only through 10.34.

`docs/reference/domain-intelligence-requirements-matrix.md` contains `DP-034` and then jumps to `DP-052` / `DP-053`.

There is no `DP-035` row and no `AT-DP-035` traceability row despite the implementation agent reporting:

```text
DP_035_ACCEPTANCE=PASS
```

The new `docs/reference/domain-sdk.md` is useful, but it does not satisfy the explicit Task 8 requirement to reconcile the canonical roadmap/matrix state.

### Required remediation

After the functional blockers are fixed and verified:

1. update the detailed 10.35 section to mark the historical YAML tree as conceptual and the implemented format as `manifest.json`;
2. make the 10.35/10.36 CLI boundary explicit;
3. update `ROADMAP.md` to `Phase 10.35 implementation complete — independent re-audit pending`, not closed;
4. add `DP-035` and `AT-DP-035` rows using the existing matrix convention;
5. do not claim `PASS`, `VERIFIED_EXISTING`, independent audit success, or closure before V2.

---

# 4. Non-promoted observations for V2 focus

These are not V1 findings but must be attacked in re-audit.

## Validation mode

`validate_domain_path()` currently constructs:

```python
DomainValidationRequest(
    ...
    strict=False,
    run_tests=False,
)
```

This is a real canonical validation mode, so V1 does not call it a second validator.

However V2 must verify that callers cannot use the non-strict structural validation result to bypass the separate test/readiness gate, especially packaging or future installation/publication paths.

## Packager output edge cases

V2 should test:

```text
output archive inside pack root
pre-existing output archive inside pack root
escaping symlinks
safe in-root symlink behavior
```

and confirm deterministic packaging remains truthful.

## Expected CLI errors

V2 should exercise filesystem `OSError` paths and confirm expected developer-facing errors do not leak avoidable tracebacks.

---

# 5. Preserved invariants independently observed

The audited source still has:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
DOMAIN_SESSION_RESUMED_EVENT=ABSENT
```

No second Domain Registry, Resolver, Workflow Engine or Permission Engine was found inside `cmm/domains/sdk`.

The audit failure is therefore not a rejection of the overall thin-SDK direction. It is caused by the two blocking implementation/evidence defects plus two major contract/documentation defects above.

---

# 6. Required remediation order

```text
1. B1 — restore Phase 10.34 evidence binding; remove hash bypasses
2. B2 — make DomainTestHarness load/prepare the real pack and wire cmm domain test through it
3. M1 — classify SDK-created external packs as EXTERNAL
4. focused adversarial tests for B1/B2/M1
5. M2 — reconcile roadmap + requirements matrix
6. focused SDK suite
7. Phase 10.34 artifact-binding regressions
8. Domain Sessions regressions
9. Domain Events / Conflict Resolver regressions
10. full tests/domains
11. full global suite
12. Ruff / format / compileall / diff check
13. commit all remediation coherently
14. clean worktree + stash preserved
15. generate exact-HEAD phase-10.35-audit-v2.tar.gz
```

Do not modify the V1 bundle.

Do not declare Phase 10.35 closed.

Do not start Phase 10.36.

---

# 7. V2 independent audit focus

The V2 auditor will independently attack:

```text
Phase 10.34 binding:
- arbitrary mutation of cmm/__main__.py must fail binding
- arbitrary mutation of validation_context.py must fail binding
- arbitrary mutation of audit validator itself must fail binding
- no exact-file mismatch allowlist
- historical fixture isolation remains usable

Harness:
- actual DomainPack present in context
- target Domain identity registered in isolated canonical registry
- no implicit enable/authorization
- cmm domain test prepares the harness
- two harnesses do not share mutable state
- invalid pack cannot prepare

Pack identity:
- scaffold manifest pack_kind=external
- builder default for external SDK use is external
- explicit experimental/internal choice remains possible only when requested

Docs:
- manifest.json canonical
- 10.35/10.36 boundary correct
- ROADMAP says implementation complete / audit pending
- DP-035 and AT-DP-035 traceability present
- no premature PASS/closure claim

Readiness:
- non-strict validation cannot become a path around required test/readiness checks

Packaging:
- determinism
- traversal/symlink safety
- output-path edge cases
```

---

# 8. Final V1 status

```text
PHASE10_35_STATUS=IMPLEMENTED_REMEDIATION_REQUIRED
FINAL_INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=2
MAJORS=2
MINORS=0
DP_035=NOT_YET_VERIFIED
AT_DP_035=NOT_YET_PASS
CLOSURE_ELIGIBLE=NO
NEXT=REMEDIATE_V1_FINDINGS_AND_BUILD_V2
```

No remediation was performed during this independent audit.
No push.
No merge.
Phase 10.36 was not started.
