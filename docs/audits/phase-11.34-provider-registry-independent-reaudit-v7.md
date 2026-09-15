# Phase 11.34 — Provider Registry — Independent Re-audit V7

**Independent verdict:** `PASS`

**Audit date:** 2026-09-15
**Auditor:** ChatGPT independent audit
**Scope:** Phase 11.34 Provider Registry — Remediation V6 exact-HEAD bundle
**Claimed branch:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `a96468094d39f7bd8afe5a2d7a4daab67c0b55be`
**Audited tree:** `583a260596bdd5eef331be8b3d9a0017fb5628d7`
**Bundle:** `cmm-os-phase11-34-remediation-v6-a96468094d39.tar.gz`
**Bundle SHA-256:** `09fd8ae76a64a898a8dca6b1397749defe9145c1f7ca865228646a66c6364100`
**Design Point:** `DP-134`
**Connected Acceptance:** `AT-DP-134`
**Requirement:** `F11-014`

## 1. Executive conclusion

Independent Re-audit V7 passes.

The exact Remediation V6 bundle closes the sole finding left open by Independent Re-audit V6:

```text
MAJOR-V6-01
```

`ModelRouteCatalog.restore_all()` now makes the required authority distinction:

```text
same route_id + same connection_id
→ preserve the exact historical connection-registration marker

fresh route or changed connection_id
→ resolve through _current_connection_registration()
→ require current provider-bound connection authority
```

Independent execution confirms all five load-bearing V6 behaviors:

```text
fresh route under stale parent -> REJECT
current connection rebind -> COHERENT
stale target rebind -> REJECT
exact historical rollback -> PRESERVED
mixed valid/invalid batch -> ATOMIC
```

The correction is narrow. The Remediation V5 -> Remediation V6 archive delta contains:

```text
ADDED=3
REMOVED=0
CHANGED=6
```

with exactly one changed production file:

```text
kernel/llm/model_routes.py
```

No parallel registry, store, schema, authority generation, restore API, CMM Usage integration, CMMChat integration or Phase 11.35 implementation was introduced.

The connected acceptance and LLM subsystem pass independently on the exact bundle:

```text
AT-DP-134 = 67 passed
V6 focused suite = 245 passed
tests/llm = 731 passed
selected roadmap/lifecycle regressions = 17 passed
compileall = PASS
```

Therefore:

```text
INDEPENDENT_REAUDIT_V7=PASS
BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR-V6-01=VERIFIED_REMEDIATED
MAJOR-V5-01=VERIFIED_REMEDIATED
MAJOR-V5-02=VERIFIED_REMEDIATED

DP-134=VERIFIED_EXISTING
F11-014=VERIFIED_EXISTING
AT-DP-134=PASS
CLOSURE_ELIGIBLE=YES
```

Phase 11.34 is now **eligible for the separate docs-only closure commit**.

It is not marked `CLOSED` by this audit report itself.

## 2. Artifact integrity

### 2.1 SHA-256

Independent SHA-256:

```text
09fd8ae76a64a898a8dca6b1397749defe9145c1f7ca865228646a66c6364100
```

This exactly matches the supplied sidecar manifest.

```text
BUNDLE_SHA256=PASS
```

### 2.2 Gzip integrity

Independent:

```text
gzip -t
```

completed successfully.

```text
GZIP_INTEGRITY=PASS
```

### 2.3 Exact commit binding

Independent:

```text
gzip -dc <bundle> | git get-tar-commit-id
```

returned:

```text
a96468094d39f7bd8afe5a2d7a4daab67c0b55be
```

matching the sidecar.

```text
EXACT_HEAD_BINDING=PASS
```

### 2.4 Exact tree binding

The archive was extracted into a clean temporary Git index using forced add so ignored paths could not disappear from the reconstruction.

Independent `git write-tree` returned:

```text
583a260596bdd5eef331be8b3d9a0017fb5628d7
```

matching the sidecar.

```text
EXACT_TREE_BINDING=PASS
```

### 2.5 File count

Independent archive enumeration:

```text
2289 files
```

matching the implementation evidence.

```text
ARCHIVE_FILE_COUNT=PASS
ARCHIVE_FILE_LIST_MATCHES_HEAD=PASS
```

### 2.6 Archive safety

Independent TAR member inspection found:

```text
PATH_TRAVERSAL=0
SYMLINKS=0
SPECIAL_FILES=0
```

```text
ARCHIVE_MEMBER_SAFETY=PASS
```

## 3. Exact remediation delta

Compared against the exact Remediation V5 bundle audited by Independent Re-audit V6:

```text
cmm-os-phase11-34-remediation-v5-cd780e3b7d74.tar.gz
```

the V7 candidate contains:

```text
ADDED=3
REMOVED=0
CHANGED=6
```

### 3.1 Added

```text
docs/audits/phase-11.34-provider-registry-independent-reaudit-v6.md
docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v6-implementation-plan.md
docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v6-design.md
```

### 3.2 Changed

```text
ROADMAP.md
docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md
docs/roadmap/phase-11-stable-integrated-platform.md
kernel/llm/model_routes.py
tests/llm/test_model_routes.py
tests/llm/test_provider_registry_dp134_acceptance.py
```

No other production subsystem changed.

```text
REMEDIATION_V6_FINDINGS_ONLY_SCOPE=PASS
```

## 4. Historical audit integrity

The historical Independent Re-audit V6 report inside the new bundle has SHA-256:

```text
3dd883d3f856a61d3e85678d277c7f47b1114117b441e8fc6d5fb10310f6183d
```

which exactly matches the report generated and committed after V6.

```text
HISTORICAL_REAUDIT_V6_REPORT_UNCHANGED=PASS
```

No historical audit report was silently rewritten.

## 5. Approved V6 spec / plan integrity

The committed V6 spec and plan were compared with the originally approved downloadable artifacts.

Differences are formatting-only inside fenced Python examples, including line wrapping such as:

```text
multi-line call -> one-line call
```

and formatter wrapping of a test return annotation.

No requirement, authority rule, task, scope prohibition, acceptance condition or lifecycle rule changed.

```text
V6_SPEC_SEMANTIC_INTEGRITY=PASS
V6_PLAN_SEMANTIC_INTEGRITY=PASS
```

## 6. Production-code assessment

The entire V6 production delta is in:

```text
kernel/llm/model_routes.py
```

### 6.1 Prior defect

Before V6, `restore_all()`:

1. directly resolved `self._connections.registration(route.connection_id)`;
2. preserved `existing.registration` whenever `route_id` matched;
3. did not verify that the incoming route still declared the same `connection_id`.

That allowed:

```text
fresh route + stale parent
→ fresh stale-authority binding

same route id + changed connection id
→ incoming route value for connection B
→ historical marker from connection A
```

### 6.2 Final rule

The audited implementation now does:

```python
existing = self._routes.get(route.route_id)

if (
    existing is not None
    and existing.route.connection_id == route.connection_id
):
    registration = existing.registration
else:
    registration = self._current_connection_registration(
        route.connection_id
    )
```

The resulting `_RouteBinding` is built in a temporary dictionary and:

```python
self._routes = entries
```

occurs only after the whole iterable validates.

This exactly implements the approved V6 design.

## 7. Production caller inspection

Independent repository search found one production caller of:

```text
ModelRouteCatalog.restore_all()
```

at:

```text
kernel/llm/provider_state_coordinator.py
```

inside discovery rollback.

That caller snapshots:

```python
routes_before = self._routes.list()
```

and on failure restores:

```python
self._routes.restore_all(routes_before)
```

This is the exact rollback shape V6 intentionally preserves.

```text
RESTORE_ALL_PRODUCTION_CALLERS=1
COORDINATOR_ROLLBACK_CALLER_PRESERVED=PASS
```

## 8. `MAJOR-V6-01` independent reproduction

### 8.1 V6-A — fresh route under stale provider-bound parent

Independent setup:

```text
ProviderSpec A
x:main connection under A
empty route catalog

remove ProviderSpec A
register different ProviderSpec B with id=x
leave x:main registered
```

Observed:

```text
connection bound to current provider = False
```

Attempt:

```text
restore_all(new route -> x:main)
```

Result:

```text
ValueError
connection x:main is bound to a stale or missing ProviderSpec
```

and:

```text
catalog unchanged = True
```

```text
V6_01_FRESH_STALE_PARENT_REJECTED=PASS
```

### 8.2 V6-B — current coherent rebind

Independent setup:

```text
logical-route -> x:main
x:main current
y:main current
```

Incoming:

```text
logical-route -> y:main
```

Result:

```text
stored connection_id = y:main
is_bound_to_current_connection = True
```

The old `x:main` marker does not survive the connection change.

```text
V6_01_CURRENT_REBIND_COHERENT=PASS
```

### 8.3 V6-C — rebind to stale target

Independent setup:

```text
logical-route -> x:main
y:main exists
provider y replaced same-id
y:main is now provider-bound stale
```

Incoming:

```text
logical-route -> y:main
```

Result:

```text
ValueError
connection y:main is bound to a stale or missing ProviderSpec
```

and:

```text
original x route/binding unchanged = True
```

```text
V6_01_STALE_TARGET_REBIND_REJECTED=PASS
```

### 8.4 V6-D — exact historical rollback

Independent setup:

```text
logical-route -> x:main
snapshot taken
route last_seen value mutated
provider x replaced same-id
connection x:main becomes provider-bound stale
```

Incoming rollback:

```text
same route_id
same connection_id
original snapshot value
```

Result:

```text
rollback accepted
original route value restored
historical connection-registration marker preserved
```

Because only the parent `ProviderSpec` was replaced while the connection registration itself remained the same:

```text
is_bound_to_current_connection(restored) = True
is_bound_to_current_provider(connection) = False
```

This is the intended V4/V6 distinction.

A separate existing V4 regression test also confirms that if the connection registration itself is replaced same-id, exact rollback preserves the old marker and therefore remains visibly stale rather than silently rebinding.

```text
V6_01_EXACT_ROLLBACK_PRESERVED=PASS
```

### 8.5 V6-E — batch atomicity

Independent setup:

```text
valid exact rollback candidate
+
fresh route under stale provider-bound target
```

Result:

```text
ValueError
entire catalog unchanged
first valid candidate not partially applied
```

```text
V6_01_BATCH_ATOMICITY=PASS
```

## 9. Independent test execution

### 9.1 Connected `AT-DP-134`

Executed against the exact archive:

```text
67 passed
```

```text
AT-DP-134_TEST_EXECUTION=PASS
AT-DP-134_TEST_COUNT=67
```

### 9.2 V6 focused suite

Executed:

```text
tests/llm/test_model_routes.py
tests/llm/test_provider_state_repository.py
tests/llm/test_provider_state_coordinator.py
tests/llm/test_provider_registry_dp134_acceptance.py
```

Result:

```text
245 passed
```

```text
FOCUSED_V6_INDEPENDENT=PASS
FOCUSED_V6_TEST_COUNT=245
```

### 9.3 Full LLM subsystem

Executed:

```text
python3 -m pytest -q tests/llm
```

Result:

```text
731 passed
```

```text
LLM_SUITE_INDEPENDENT=PASS
LLM_SUITE_TEST_COUNT=731
```

### 9.4 V5/V6 connected adversaries

Executed:

```text
tests/llm/test_provider_registry_dp134_acceptance.py -k "v5_ or v6_"
```

Result:

```text
7 passed
```

```text
V5_V6_CONNECTED_ADVERSARIES=PASS
```

### 9.5 Route authority / rollback subset

Executed from `test_model_routes.py` for restore-all, stale-provider, exact-authority and status-transition coverage.

Result:

```text
18 passed
```

```text
ROUTE_AUTHORITY_ROLLBACK_SUBSET=PASS
```

### 9.6 Selected roadmap/lifecycle regressions

Executed:

```text
tests/domains/test_domain_session_audit_v8_regressions.py
tests/domains/test_domain_session_lifecycle_fixture_compatibility.py
```

Result:

```text
17 passed
```

```text
SELECTED_DOC_REGRESSIONS_INDEPENDENT=PASS
SELECTED_DOC_REGRESSIONS_TEST_COUNT=17
```

### 9.7 Compileall

Executed:

```text
python3 -m compileall -q cmm cmm_agent kernel tests
```

Result:

```text
COMPILEALL_INDEPENDENT=PASS
```

### 9.8 Diff hygiene

Independent no-index `git diff --check` across every changed tracked file produced no whitespace errors.

```text
DIFF_CHECK_INDEPENDENT=PASS
```

## 10. Independent-environment limitations

These limitations do not change the PASS verdict because the complete V6 authority fix and its preserved LLM subsystem behavior were independently executed from the exact bundle.

### 10.1 Phase 10.46 replay

The audit environment lacks:

```text
libcst
```

so the canonical DP-046 test cannot collect independently here.

The implementation evidence reports:

```text
14 passed
```

This is accepted as supporting implementation-machine evidence, not independent replay.

### 10.2 Ruff / format replay

The independent environment has no Ruff module.

The supplied manifest reports:

```text
RUFF_BASELINE=839
RUFF_CURRENT=837
FORMAT_BASELINE=359
FORMAT_CURRENT=359
RUFF_NO_REGRESSION=PASS
FORMAT_NO_REGRESSION=PASS
```

The implementation report states those baseline-aware counts were replayed using immutable `git archive` extracts.

They are supporting evidence, not independently recomputed in this container.

### 10.3 Global pytest

The independent environment cannot collect the full domain suite because of the same missing dependency path.

The implementation report states:

```text
18261 passed
```

and also states that the global suite was independently re-executed by the implementation harness.

The exact V7 bundle independently passes the complete LLM suite and the directly relevant lifecycle regressions.

## 11. Security assessment

### 11.1 Raw-secret boundary

No production secret-handling code changed.

The production delta contains no:

- raw secret persistence;
- credential getter;
- audit secret payload;
- token material;
- secret-bearing route state.

A pre-existing secret-shaped test fixture remains in the acceptance file and was not introduced by V6.

```text
RAW_SECRET_BOUNDARY=PASS
```

### 11.2 Authority fail-closed behavior

Independent evidence confirms:

```text
fresh stale-parent restore_all -> fail closed
stale-target rebind -> fail closed
current rebind -> exact current marker
historical rollback -> exact historical marker
```

```text
RESTORE_ALL_FRESH_AUTHORITY_FAIL_CLOSED=PASS
RESTORE_ALL_REBIND_COHERENCE=PASS
RESTORE_ALL_EXACT_ROLLBACK_PRESERVED=PASS
RESTORE_ALL_BATCH_ATOMICITY=PASS
```

## 12. Architecture assessment

The V6 delta introduces no:

- second route registry;
- rollback registry;
- new restore API;
- route/provider/connection generation id;
- authority epoch;
- persisted authority field;
- new Provider Registry store;
- `last_discovery_at`;
- `discovery.snapshot`;
- generic transaction/rollback framework;
- cascading teardown.

```text
NEW_ROUTE_REGISTRY=NOT_INTRODUCED
NEW_RESTORE_API=NOT_INTRODUCED
NEW_PERSISTED_AUTHORITY_FIELD=NOT_INTRODUCED
PERSISTENT_GENERATION_IDS=NOT_INTRODUCED
CASCADING_TEARDOWN=NOT_INTRODUCED
```

## 13. Deferred scope

No evidence of:

```text
CMM Usage integration
CMMChat integration
Phase 11.35 implementation
```

was introduced by the V6 delta.

```text
CMM_USAGE_INTEGRATION=NOT_PERFORMED
CMMCHAT=DEFERRED_BY_USER
PHASE11_35=NOT_IMPLEMENTED_BY_THIS_REMEDIATION
```

## 14. Preservation of prior findings

### 14.1 `MAJOR-V5-01`

Independent Re-audit V6 had held this only partially remediated because the residual `restore_all()` route-authority bypass remained.

V7 independently verifies that residual bypass is now closed.

The earlier coordinator pre-I/O guard, `register()` boundary and `restore()` boundary remain covered by the green LLM/acceptance suites.

```text
MAJOR-V5-01=VERIFIED_REMEDIATED
```

### 14.2 `MAJOR-V5-02`

The independently verified V5 durable route/audit watermark remains unchanged by V6.

The V5 connected adversaries remain green.

```text
MAJOR-V5-02=VERIFIED_REMEDIATED
```

### 14.3 V4, V3 and V2 invariants

No relevant production owner outside `model_routes.py` changed.

The full LLM suite and focused authority/rollback subsets remain green.

```text
V4_INVARIANTS=PRESERVED
V3_INVARIANTS=PRESERVED
V2_INVARIANTS=PRESERVED
```

## 15. Non-scored temporal limitation

Independent Re-audit V6 documented:

```text
NOOP_DISCOVERY_MONOTONICITY=
KNOWN_DESIGN_LIMITATION_NOT_SCORED
```

Remediation V6 does not touch discovery temporal semantics.

The limitation remains outside the approved Phase 11.34 closure contract and does not affect this V7 verdict.

```text
NOOP_DISCOVERY_MONOTONICITY=
KNOWN_DESIGN_LIMITATION_NOT_SCORED
```

## 16. Documentary state before this audit

The audited bundle correctly remains pre-verdict:

```text
PHASE11_34=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V6=FAIL
REMEDIATION_V6=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
F11-014=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
DP-134=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
AT-DP-134=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
AUDIT_STATUS=PENDING_INDEPENDENT_REAUDIT_V7
```

The requirements matrix contains the future closure tokens only in a clearly labelled:

```text
Future closure criteria — post-Independent-Re-audit-V7 only; not current state
```

block.

No premature current-state closure was found.

```text
PREAUDIT_DOCUMENTARY_STATE=PASS
```

## 17. `AT-DP-134` assessment

The connected acceptance now includes:

- canonical provider replacement + stale fresh `restore_all()` rejection;
- same-route-id rebind to a different current canonical connection;
- exact rollback under stale parent authority;
- V5 stale discovery authority;
- V5 durable runtime/restart watermark;
- V4 exact graph/capture authority;
- earlier persistence, isolation and onboarding invariants.

The connected suite runs against canonical in-memory implementations rather than replacing the authority graph with isolated mocks.

Independent execution:

```text
67 passed
```

Therefore:

```text
AT-DP-134=PASS
```

## 18. `DP-134` assessment

`DP-134` requires one canonical, persistent and fail-closed Provider Registry whose provider-specific routes remain referentially bound to accepted canonical connection/provider authority.

The final public route mutation/restoration surfaces now behave coherently:

```text
register()
→ new relation requires current parent authority

restore()
→ persisted fresh relation requires current parent authority

restore_all()
→ exact existing relationship preserves historical marker
→ fresh/rebound relationship requires current parent authority

field-only mutations
→ preserve exact historical marker

capture
→ rejects stale aggregate state
```

The V6 `restore_all()` residual identified in Re-audit V6 is closed.

No parallel authority infrastructure exists.

Therefore:

```text
DP-134=VERIFIED_EXISTING
```

## 19. `F11-014` assessment

`F11-014` requires one canonical, persistent, auditable and fail-closed Provider Registry with:

- canonical provider identity;
- referentially coherent manifests/models/connections/routes;
- explicit isolation policy;
- ownership-safe onboarding;
- administrative non-inference discovery;
- persistent versioned state;
- sanitized audit history;
- connected `DP-134` acceptance.

The exact bundle satisfies those requirements and all open closure findings have been independently resolved.

Therefore:

```text
F11-014=VERIFIED_EXISTING
```

## 20. Final verdict

```text
INDEPENDENT_REAUDIT_V7=PASS
BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR-V6-01=VERIFIED_REMEDIATED
MAJOR-V5-01=VERIFIED_REMEDIATED
MAJOR-V5-02=VERIFIED_REMEDIATED

BUNDLE_SHA256=PASS
GZIP_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
EXACT_TREE_BINDING=PASS
ARCHIVE_FILE_COUNT=PASS
ARCHIVE_MEMBER_SAFETY=PASS
REMEDIATION_V6_SCOPE=PASS
HISTORICAL_REAUDIT_V6_REPORT_UNCHANGED=PASS

AT-DP-134_TEST_EXECUTION=PASS
AT-DP-134_TEST_COUNT=67
FOCUSED_V6_INDEPENDENT=PASS
FOCUSED_V6_TEST_COUNT=245
LLM_SUITE_INDEPENDENT=PASS
LLM_SUITE_TEST_COUNT=731
V5_V6_CONNECTED_ADVERSARIES=PASS
ROUTE_AUTHORITY_ROLLBACK_SUBSET=PASS
SELECTED_DOC_REGRESSIONS_INDEPENDENT=PASS
SELECTED_DOC_REGRESSIONS_TEST_COUNT=17
COMPILEALL_INDEPENDENT=PASS
DIFF_CHECK_INDEPENDENT=PASS

PHASE10_46_INDEPENDENT_REPLAY=UNAVAILABLE_MISSING_LIBCST
RUFF_INDEPENDENT_REPLAY=UNAVAILABLE_MISSING_RUFF
GLOBAL_PYTEST_INDEPENDENT_REPLAY=UNAVAILABLE_ENVIRONMENT_DEPENDENCIES

RAW_SECRET_BOUNDARY=PASS
RESTORE_ALL_FRESH_AUTHORITY_FAIL_CLOSED=PASS
RESTORE_ALL_REBIND_COHERENCE=PASS
RESTORE_ALL_EXACT_ROLLBACK_PRESERVED=PASS
RESTORE_ALL_BATCH_ATOMICITY=PASS

V4_INVARIANTS=PRESERVED
V3_INVARIANTS=PRESERVED
V2_INVARIANTS=PRESERVED

NOOP_DISCOVERY_MONOTONICITY=KNOWN_DESIGN_LIMITATION_NOT_SCORED

DP-134=VERIFIED_EXISTING
F11-014=VERIFIED_EXISTING
AT-DP-134=PASS
CLOSURE_ELIGIBLE=YES

AUDITED_HEAD=a96468094d39f7bd8afe5a2d7a4daab67c0b55be
AUDITED_TREE=583a260596bdd5eef331be8b3d9a0017fb5628d7
AUDITED_BUNDLE_SHA256=09fd8ae76a64a898a8dca6b1397749defe9145c1f7ca865228646a66c6364100

CMM_USAGE_INTEGRATION=NOT_PERFORMED
CMMCHAT=DEFERRED_BY_USER
PHASE11_35=NOT_IMPLEMENTED_BY_THIS_REMEDIATION
PUSH=NO
MERGE=NO
```

## 21. Closure eligibility

The canonical Phase 11.34 closure threshold is now satisfied:

```text
BLOCKERS=0
MAJORS=0
DP-134=VERIFIED_EXISTING
AT-DP-134=PASS
F11-014=VERIFIED_EXISTING
CLOSURE_ELIGIBLE=YES
```

No further code remediation is required for Phase 11.34.

The next action is a **separate docs-only closure commit**.

That commit must not add or modify production code.

Until that separate commit is made and verified:

```text
PHASE11_34=CLOSED
```

must not yet be claimed as repository current state.

## 22. Next canonical cycle

```text
COMMIT INDEPENDENT RE-AUDIT V7 PASS REPORT
→ VERIFY CLEAN WORKTREE / QUARANTINE STASH
→ DOCS-ONLY PHASE 11.34 CLOSURE COMMIT
→ VERIFY CLOSURE COMMIT / CLEAN WORKTREE
→ ONLY THEN BEGIN NEXT PHASE 11 SUBPHASE
```
