# Phase 10.34 — Domain Sessions — Independent Audit V5

## Independent Audit V5

**Date:** 2026-08-30
**Auditor:** ChatGPT (independent project auditor)
**Audited phase:** Phase 10.34 — Domain Sessions
**Audited bundle:** `phase-10.34-audit-v5.tar.gz`
**Bundle SHA256:** `0afaa0b3083b525c09362b6bb31307173c759c4b28353d33ae70846781047c53`
**Audited Git HEAD:** `76ec1ec441f6d9d2701b45a7723efb8b734319a9`

```text
FINAL_INDEPENDENT_AUDIT_V5=FAIL
BLOCKERS=0
MAJORS=2
MINORS=1

DP_034=NOT_VERIFIED
AT_DP_034=FAIL
CLOSURE_ALLOWED=NO

NEXT=PHASE10_34_REMEDIATION_V6
PUSH=NO
MERGE=NO
```

---

## 1. Artifact identity and packaging

Independent artifact verification:

```text
SHA256=0afaa0b3083b525c09362b6bb31307173c759c4b28353d33ae70846781047c53
ARCHIVE_HEAD=76ec1ec441f6d9d2701b45a7723efb8b734319a9
ARCHIVE_PREFIX=CMM-OS-phase-10.34/
MEMBERS=1882
FORBIDDEN_GIT_VENV_PYC=0
```

Required V5 files are present:

```text
cmm/domains/resource_authority.py
cmm/domains/knowledge_authority.py
cmm/domains/session_resumer.py
cmm/domains/session_revalidation.py
tests/domains/test_domain_session_audit_v4_regressions.py
docs/audits/evidence/phase-10.34-at-dp-034-manifest.json
docs/audits/evidence/phase-10.34-v5-gates.json
```

Packaging is correct.

---

## 2. Independent execution evidence

The exact audited source compiled successfully:

```text
COMPILEALL=PASS
```

Independent Phase 10.33 event-catalog probe:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
DOMAIN_SESSION_RESUMED_PRESENT=NO
```

The audit environment does not contain the repository's historical `.git`
objects or project `.venv`, both correctly excluded from the `git archive`.

Using an isolated package-loading harness that avoids eager package
initializers, the auditor directly executed the V5 functional regression
functions covering:

- no synthetic `DomainResolutionResult` during recomposition;
- preservation of genuine canonical resolver results;
- expired native resource rejection;
- valid native resource acceptance;
- missing resource authority fail-closed;
- missing knowledge authority fail-closed;
- version snapshots not overriding native expiration;
- resource drift continuity invalidation;
- knowledge invalidation continuity handling;
- current-clock temporal fallback;
- canonical re-resolution replacing historical supporting domains.

Those targeted V5 regressions passed.

Two additional adversarial probes exposed the remaining findings below.

---

# 3. Positive V5 remediation confirmed

## 3.1 Synthetic resolution authority is fixed

No `DomainResolutionResult(...)` construction remains in the Domain Session
recomposition path.

Recomposition now uses:

```text
DomainCompositionInput
composer.recompose(...)
resolution_authoritative=False
```

when there is no genuine resolver result.

A real canonical resolver result is still passed through `compose()` and
retained in resolution lineage.

Independent V5 probes for both paths passed.

Therefore Audit V4 MAJOR-01 is fixed.

## 3.2 Missing resource/knowledge authority is now fail-closed

Persisted resource or knowledge references without a current authority no
longer become warning-only `RESUMED` state.

The V5 revalidation path produces blocking checks.

## 3.3 Version snapshots no longer override native resource expiration

When a native resource authority is present, the current authoritative verdict
wins over `current_resource_versions`.

The V4 fail-open `"v1" means current` behavior is fixed.

## 3.4 Stale derived continuity handling remains improved

Resource / knowledge drift and material domain changes invalidate current
execution continuity rather than trusting old partials/traces as fresh.

## 3.5 V3 blockers remain fixed

The previously audited protections remain present:

```text
stale durable rollback = fixed
workflow/conflict status downgrade = fixed
strict JSON contracts = fixed
```

---

# 4. MAJOR-01 — Native resource/knowledge authority is still semantically incomplete

Audit V4 required Phase 10.34 current truth to be bound to the repository-native
resource/knowledge semantics.

V5 improves this substantially, but two independent probes show that the
default authorities do not yet preserve the native semantics they claim to
adapt.

---

## 4.1 Resource authority overrides native `historical_allowed=True`

`DefaultDomainResourceAuthority` correctly calls the existing native:

```text
resource_resolver._evaluate_temporal_policy(...)
```

However, after that native evaluator returns valid, the authority performs a
second unconditional check:

```python
valid_until = ctx.temporal_scope.get("valid_until")
if valid_until is not None and valid_until < now:
    return BLOCKING
```

That second check ignores:

```text
DomainResourceTemporalPolicy.historical_allowed
```

### Independent reproduction

A real native resource was constructed with:

```text
valid_until = one hour in the past
expiration_required=True
historical_allowed=True
```

The repository-native temporal evaluator returned:

```text
NATIVE_POLICY=(True, "")
```

The new V5 resource authority returned:

```text
AUTHORITY_STATUS=BLOCKING
BLOCKING=True
MESSAGE=Resource ... is expired
```

So the adapter contradicts the native policy.

### Test gap

The V5 regression helper always constructs:

```text
historical_allowed=False
```

No V5 regression covers the required:

```text
expired historical resource allowed when native policy allows
```

case.

---

## 4.2 Knowledge authority does not consume the canonical cognitive knowledge model

The repository already contains canonical knowledge contracts:

```text
cmm.cognitive.knowledge.KnowledgeItem
cmm.cognitive.enums.KnowledgeStatus
cmm.cognitive.knowledge.TemporalScope
cmm.cognitive.store_contracts.KnowledgeStoreProtocol
```

`KnowledgeItem` explicitly represents states including:

```text
ACTIVE
UNVERIFIED
DISPUTED
SUPERSEDED
INVALIDATED
```

plus temporal scope and invalidation metadata.

The new:

```text
DefaultDomainKnowledgeAuthority
```

does not import or interpret these native contracts.

It is backed by:

```python
Mapping[str, Any]
```

and only treats a few **string values** such as `"INVALIDATED"` as non-current.

Any non-string object stored under the ID is treated as current.

### Independent native-contract reproduction

The auditor created a genuine canonical:

```text
KnowledgeItem(id="know:native")
```

and invalidated it through its own native API.

Observed:

```text
KNOWLEDGE_STATUS=invalidated
```

That canonical invalidated `KnowledgeItem` was supplied to
`DefaultDomainKnowledgeAuthority`.

The authority returned:

```text
AUTHORITY_STATUS=PASS
BLOCKING=False
MESSAGE=Knowledge 'know:native' is current
```

### Session-level reproduction

The same invalidated canonical knowledge item was then referenced by a real
`DomainSessionContext`.

Observed:

```text
RESULT_STATUS=RESUMED
RECORDED=True
KNOWLEDGE_CHECK=PASS
blocking=False
```

Therefore Phase 10.34 can still durably resume while treating a canonical
`INVALIDATED` knowledge object as current.

This directly contradicts:

```text
persisted snapshot != current truth
```

and means the claimed `NATIVE_KNOWLEDGE_AUTHORITY_GATE=PASS` is not valid.

---

## Required remediation for MAJOR-01

### Resource

1. Treat `_evaluate_temporal_policy()` as authoritative.
2. Do not apply a second expiration rule that contradicts
   `historical_allowed=True`.
3. If basic fallback temporal handling remains necessary, use it only when no
   native definition/policy exists.
4. Add explicit E2E tests:
   - expired + historical_allowed=False -> blocked;
   - expired + historical_allowed=True -> accepted according to native policy;
   - stale validity window -> drift/replan.

### Knowledge

1. Adapt the authority to the canonical cognitive knowledge layer.
2. Accept or resolve actual `KnowledgeItem` / `KnowledgeStoreProtocol` state.
3. At minimum:
   - `INVALIDATED` -> fail closed;
   - `SUPERSEDED` -> not current;
   - temporal scope expired/future/unknown -> conservative native verdict;
   - active/current knowledge -> current;
   - missing ID -> fail closed.
4. Do not infer currentness merely because a mapping contains a non-string
   object.
5. Add session-level E2E regressions with real `KnowledgeItem` objects.

---

# 5. MAJOR-02 — AT-DP-034 evidence is not independently verifiable from the audit bundle

V5 finally introduces a real 56-entry evidence manifest and a much stronger
validator.

That is a major improvement over V4.

However, the committed validator cannot validate the exact artifact supplied to
the independent auditor.

## 5.1 Evidence manifest structure is real

The bundle contains:

```text
docs/audits/evidence/phase-10.34-at-dp-034-manifest.json
```

with exactly 56 checkpoint IDs.

Checkpoints 1–47 bind to real pytest node IDs.

Checkpoints 48–56 bind to:

```text
focused_tests
domain_tests
global_tests
quality_gates
manifest_inventory_56_resolved
phase10_33_regression
git_archive_v5
pre_audit_gates
closure_guard
```

This is substantially better than V4's proxy assertions.

## 5.2 Gate artifact is tree-bound in the developer repository

The V5 gate artifact records:

```text
verified_source_commit=bf035667d70153a3834226c004a19e95ffb72406
verified_source_tree=16d4e3276869c3bf7985986ce328e9c568e09de7
```

and the validator calls:

```text
git rev-parse <verified_source_commit>^{tree}
git diff --quiet <verified_source_commit> -- cmm tests pyproject.toml
```

This can work inside the original developer Git repository.

## 5.3 It cannot work from the independent `git archive`

The audit artifact intentionally contains:

```text
.git = absent
.venv = absent
```

The evidence validator nevertheless requires both.

### Default validation from exact extracted V5 bundle

Observed:

```text
FileNotFoundError:
.../CMM-OS-phase-10.34/.venv/bin/python
```

because `collect_pytest_nodes()` hard-codes:

```text
repo_root/.venv/bin/python
```

### Validation with pre-collected pytest nodes

Even when collection is supplied externally, the validator then fails:

```text
EvidenceValidationError:
verified_source_commit cannot be resolved:
bf035667d70153a3834226c004a19e95ffb72406
```

because a `git archive` does not contain historical Git objects.

## Impact

The exact artifact sent to the independent auditor cannot machine-verify:

```text
AT_DP_034_EVIDENCE_RESOLVED=56/56
AT_DP_034_VERIFIED_TREE=...
```

without access to an external clone containing the same commit history and the
developer's virtual environment.

That makes the closure evidence non-self-contained and prevents independent
artifact verification.

This is not the old V4 false-positive design: V5 is materially better.
The remaining problem is portability / independent verifiability.

## Required remediation for MAJOR-02

Make the evidence bundle-verifiable without embedding `.git` or `.venv`.

Recommended design:

1. Keep the external-gate evidence artifact.
2. Record deterministic hashes for the verified paths, for example:
   - Git-compatible subtree hashes for `cmm/` and `tests/`;
   - blob/hash for `pyproject.toml`;
   - or one canonical manifest of `path -> sha256`.
3. Let the validator recompute those hashes directly from the current extracted
   files.
4. Do not require historical Git objects to prove that final source/test files
   equal the files that were tested.
5. Use `sys.executable` / a supplied collector command for pytest-node
   resolution, not a hard-coded `.venv/bin/python`.
6. The developer repo may additionally verify the source commit/tree, but the
   audit artifact must be independently verifiable on its own.
7. Add an acceptance test executed from a temporary `git archive` extraction
   with:
   - no `.git`;
   - no `.venv`;
   proving the 56/56 validator can still validate the committed evidence.

The external command results themselves remain recorded evidence; the
important missing property is cryptographically binding those results to the
actual source/test files present in the audit artifact.

---

# 6. MINOR-01 — one current documentation count is inconsistent

The stale V2/V3/V4 current-status references were fixed.

Current docs correctly say:

```text
IMPLEMENTED_PENDING_AUDIT
independent re-audit V5 pending
394 focused domain session tests
```

However:

```text
docs/reference/domain-sessions.md
```

states:

```text
Audit V4 regression suite: 32 tests passing
```

while the committed regression module contains:

```text
34 test functions
```

and the V5 remediation report also records:

```text
AUDIT_V4_REGRESSION_TESTS=34 PASS
```

Update the current reference to the actual verified count.

Historical audit reports must remain untouched.

---

# 7. V4 finding disposition

```text
V4 MAJOR-01 synthetic DomainResolutionResult authority
FIXED

V4 MAJOR-02 native resource/knowledge authority
PARTIALLY_FIXED
- missing authority fail-closed: fixed
- version snapshots not current truth: fixed
- native resource integration: partial
- native knowledge integration: not complete
- historical_allowed semantic regression remains

V4 MAJOR-03 AT-DP-034 false-positive evidence gate
PARTIALLY_FIXED
- real 56-entry manifest: fixed
- real external gate records: fixed
- mutation tests: added
- bundle-independent verification: not fixed

V4 MINOR-01 stale documentation
PARTIALLY_FIXED
- old V2/V4 status references fixed
- one current regression count remains inconsistent
```

---

# 8. Final verdict

V5 is the strongest Phase 10.34 implementation audited so far.

Confirmed fixed:

```text
synthetic resolution authority
stale durable rollback
status precedence
strict JSON
missing resource authority fail-closed
missing knowledge authority fail-closed
version snapshot precedence
continuity invalidation
archive packaging
23-event boundary
```

The remaining work is narrow but closure-relevant:

1. finish the native current resource/knowledge semantics;
2. make AT-DP-034 evidence independently verifiable from the exact audit
   artifact;
3. correct one documentation count.

```text
FINAL_INDEPENDENT_AUDIT_V5=FAIL

BLOCKERS=0
MAJORS=2
MINORS=1

DP_034=NOT_VERIFIED
AT_DP_034=FAIL

GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
DOMAIN_SESSION_RESUMED_EVENT=ABSENT

AUDITED_HEAD=76ec1ec441f6d9d2701b45a7723efb8b734319a9
AUDIT_BUNDLE_SHA256=0afaa0b3083b525c09362b6bb31307173c759c4b28353d33ae70846781047c53
AUDIT_BUNDLE_PREFIX=CMM-OS-phase-10.34/

CLOSURE_ALLOWED=NO
NEXT=PHASE10_34_REMEDIATION_V6
PUSH=NO
MERGE=NO
```
