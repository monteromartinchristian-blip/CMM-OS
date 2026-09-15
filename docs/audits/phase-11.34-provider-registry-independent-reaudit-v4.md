# Phase 11.34 — Provider Registry — Independent Re-audit V4

**Independent verdict:** `FAIL`

**Audit date:** 2026-09-15
**Auditor:** ChatGPT independent audit
**Scope:** Phase 11.34 Provider Registry — Remediation V3 exact-HEAD bundle
**Branch claimed by manifest:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `46ef38ae477c801975b55b92c5f31f9137a3bc12`
**Audited tree:** `4f24aed198e86d702791bef46d71df7d281a767d`
**Bundle:** `cmm-os-phase11-34-remediation-v3-46ef38ae477c.tar.gz`
**Bundle SHA-256:** `d8a21eac304d56789ee54b08bc6e96fa4e7ed995ef829897e9e1c268771c4f64`
**Design Point:** `DP-134`
**Connected Acceptance:** `AT-DP-134`

## 1. Executive conclusion

Remediation V3 genuinely closes the three findings for which it was designed:

- the exact-object cross-authority component graph accepted in Re-audit V3 is now rejected at capture, coordinator construction and onboarding construction;
- successful same-route rediscovery at a newer timestamp is now persisted through the canonical coordinator and survives restart with a sanitized `route.refreshed` audit record;
- the three identified Phase 11.34 plan documents were changed only by formatter-style normalization, with no historical audit report rewritten.

Independent execution on the exact uploaded bundle also passes:

```text
AT-DP-134 = 44 passed
focused V3 suite = 200 passed
tests/llm = 640 passed
compileall = PASS
selected roadmap/lifecycle regressions = 17 passed
```

However, deeper connected adversarial review found three closure-blocking authority/coherence failures not exercised by the 44-test acceptance:

1. a completely coherent component graph can still be captured after its canonical provider has been removed while dependent models, connections and routes remain, producing an aggregate that canonical restore cannot rebuild;
2. `ProviderOnboardingService.accept()` treats a caller-created public `ConnectionProposal` as acceptance authority and can therefore connect canonical Codex with `requires_isolation=False`, an arbitrary endpoint and no CMM-owned profile;
3. `ProviderRegistryStateCoordinator.discover_models()` accepts any same-id `ProviderManifest` object supplied by the caller rather than requiring the active canonical manifest from its own bound manifest registry, allowing foreign activation policy to mutate canonical route state.

A further temporal defect is recorded as minor:

4. an older aware `seen_at` is accepted as a refresh, regressing durable `last_seen_at` and creating a later revision whose audit timestamp is earlier than the previous one.

Therefore:

```text
INDEPENDENT_REAUDIT_V4=FAIL
BLOCKERS=0
MAJORS=3
MINORS=1

MAJOR-V4-01=OPEN
MAJOR-V4-02=OPEN
MAJOR-V4-03=OPEN
MINOR-V4-01=OPEN

DP-134=NOT_VERIFIED
F11-014=NOT_VERIFIED
AT-DP-134_TEST_EXECUTION=PASS
AT-DP-134=FAIL_INDEPENDENT_ADEQUACY
CLOSURE_ELIGIBLE=NO
```

Phase 11.34 remains implemented and pending independent re-audit. It is not closure-eligible.

## 2. Artifact integrity

All artifact checks below were executed directly against the uploaded TAR.GZ.

### 2.1 SHA-256

Independent recomputation:

```text
d8a21eac304d56789ee54b08bc6e96fa4e7ed995ef829897e9e1c268771c4f64
```

This exactly matches the sidecar manifest.

```text
BUNDLE_SHA256=PASS
```

### 2.2 Gzip integrity

`gzip -t` completed successfully.

```text
GZIP_INTEGRITY=PASS
```

### 2.3 Exact commit binding

`git get-tar-commit-id` over the decompressed archive returned:

```text
46ef38ae477c801975b55b92c5f31f9137a3bc12
```

This exactly matches the manifest.

```text
EXACT_HEAD_BINDING=PASS
```

### 2.4 Exact tree reconstruction

The clean archive was imported into a fresh Git index and `git write-tree` returned:

```text
4f24aed198e86d702791bef46d71df7d281a767d
```

This exactly matches `AUDITED_TREE`.

```text
EXACT_TREE_BINDING=PASS
```

### 2.5 Archive file count

Independent enumeration found:

```text
ARCHIVE_REGULAR_FILE_COUNT=2280
```

A clean reconstructed Git tree also contained 2280 files.

```text
ARCHIVE_FILE_COUNT=PASS
```

## 3. Exact Remediation V3 delta

The audited V4 bundle was compared with the exact Re-audit V3 predecessor bundle:

```text
cmm-os-phase11-34-remediation-v2-b0ff1169d022.tar.gz
```

The clean tracked-file delta is:

```text
ADDED=3
REMOVED=0
CHANGED=15
```

Added:

```text
docs/audits/phase-11.34-provider-registry-independent-reaudit-v3.md
docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v3-implementation-plan.md
docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v3-design.md
```

Changed:

```text
ROADMAP.md
docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md
docs/roadmap/phase-11-stable-integrated-platform.md
docs/superpowers/plans/2026-09-13-cmm-provider-registry-core.md
docs/superpowers/plans/2026-09-14-phase-11.34-provider-registry-remediation-v1-implementation-plan.md
docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v2-implementation-plan.md
kernel/llm/model_catalog.py
kernel/llm/provider_onboarding.py
kernel/llm/provider_state_coordinator.py
kernel/llm/provider_state_repository.py
tests/llm/test_model_catalog_v2.py
tests/llm/test_provider_onboarding.py
tests/llm/test_provider_registry_dp134_acceptance.py
tests/llm/test_provider_state_coordinator.py
tests/llm/test_provider_state_repository.py
```

No unrelated production subsystem implementation was found.

```text
REMEDIATION_V3_FINDINGS_ONLY_SCOPE=PASS
```

## 4. Independent test execution

All tests in this section were executed from the extracted exact bundle.

### 4.1 Connected `AT-DP-134`

Command:

```text
python3 -m pytest -q tests/llm/test_provider_registry_dp134_acceptance.py
```

Result:

```text
44 passed
```

```text
AT-DP-134_TEST_EXECUTION=PASS
```

### 4.2 V3 focused suite

Executed:

```text
tests/llm/test_model_catalog_v2.py
tests/llm/test_provider_state_repository.py
tests/llm/test_provider_state_coordinator.py
tests/llm/test_provider_onboarding.py
tests/llm/test_provider_registry_dp134_acceptance.py
```

Result:

```text
200 passed
```

```text
FOCUSED_V3_INDEPENDENT=PASS
```

### 4.3 Full LLM subsystem

Command:

```text
python3 -m pytest -q tests/llm
```

Result:

```text
640 passed
```

```text
LLM_SUITE_INDEPENDENT=PASS
```

### 4.4 Selected roadmap/lifecycle regressions

Executed:

```text
tests/domains/test_domain_session_audit_v8_regressions.py
tests/domains/test_domain_session_lifecycle_fixture_compatibility.py
```

Result:

```text
17 passed
```

### 4.5 Compileall

Executed:

```text
python3 -m compileall -q cmm cmm_agent kernel tests
```

Result:

```text
COMPILEALL_INDEPENDENT=PASS
```

## 5. Independent-environment gate limitations

The audit container does not contain every development dependency from the implementation machine.

### 5.1 Phase 10.46

Attempting the canonical DP-046 acceptance reached repository imports and stopped during collection because the audit environment lacks `libcst`:

```text
ModuleNotFoundError: No module named 'libcst'
```

This is an audit-environment dependency limitation, not evidence of a bundle test failure.

The implementation-machine evidence supplied for Phase 10.46 is:

```text
14 passed
```

It is recorded but not described as independently replayed.

### 5.2 Ruff

The audit Python environment has no Ruff module:

```text
No module named ruff
```

An attempt to fetch Ruff 0.16.2 through the environment package runner also failed because outbound package DNS/network access is disabled.

Therefore the reported implementation-machine values:

```text
RUFF_BASELINE=839 -> 837
FORMAT_BASELINE=359 -> 358
```

cannot be independently recomputed in this container.

This limitation does not affect the FAIL verdict because all three majors below are independently reproducible with the exact bundle and standard Python only.

## 6. Disposition of Re-audit V3 findings

| Re-audit V3 finding | V4 disposition | Result |
| --- | --- | --- |
| `MAJOR-V3-01` exact component graph cross-wiring | `VERIFIED_REMEDIATED` | Capture, coordinator and onboarding now reject foreign component graphs by exact object identity. |
| `MAJOR-V3-02` refresh-only state not durably persisted | `VERIFIED_REMEDIATED` | Newer same-route refresh is persisted, audited as `route.refreshed`, restored at T1, and rolled back on save failure. |
| `MINOR-V3-01` `359 → 360` format gate discrepancy | `REMEDIATION_ARTIFACT_VERIFIED; GLOBAL_RUFF_REPLAY_UNAVAILABLE` | Exact predecessor/current diff confirms formatter-only changes to the three authorized plan docs and no audit rewrite; reported global `359 → 358` cannot be replayed because Ruff is absent from the audit environment. |

## 7. `MAJOR-V3-01` — verified remediated in its approved scope

The exact V3 defect was cross-wiring components belonging to different live authorities that happened to use the same provider id.

The audited code now requires:

```text
manifests.provider_registry is providers
models.provider_registry is providers
connections.provider_registry is providers
routes.connections is connections
```

at capture and coordinator construction.

Onboarding additionally requires its manifest/connection registries and optional coordinator to belong to its exact provider graph.

`ModelCatalog.provider_registry` is a read-only accessor.

The connected acceptance covers:

- foreign manifest registry;
- foreign model catalog;
- foreign connection registry;
- foreign route catalog;
- foreign coordinator;
- foreign onboarding graph.

Independent test execution passes.

The new `MAJOR-V4-01` and `MAJOR-V4-03` below are distinct layers:

- V4-01 occurs inside one correctly wired object graph after canonical-provider removal;
- V4-03 occurs at an operation boundary after graph construction by passing a noncanonical manifest value object.

Thus V3-01 is not being reopened; deeper authority invariants remain uncovered.

```text
MAJOR-V3-01=VERIFIED_REMEDIATED
```

## 8. `MAJOR-V3-02` — verified remediated

The coordinator now snapshots routes before administrative discovery, performs canonical reconciliation, derives lifecycle plus refresh records, and commits the mutation batch exactly once.

For a known available route whose `last_seen_at` changes without a lifecycle transition it emits:

```text
route.refreshed
```

with sanitized detail.

Independent exact-bundle execution proves:

```text
T0 first discovery -> persisted
T1 same-route discovery -> persisted
revision advances once
live last_seen_at = T1
persisted last_seen_at = T1
restored last_seen_at = T1
route.refreshed present
same T1 repeat = no-op
refresh save failure = exact rollback
```

```text
MAJOR-V3-02=VERIFIED_REMEDIATED
```

## 9. `MINOR-V3-01` — artifact remediation verified; global Ruff replay unavailable

The three authorized historical plan documents were independently compared against the exact predecessor V2 bundle.

Their changes are formatter-shaped only:

- blank-line normalization in Python fenced blocks;
- Python expression/parenthesis wrapping;
- compact function-signature normalization;
- one source-home metadata example changed from two comma-separated tuple expressions to the explicit enclosing tuple-of-tuples form, preserving the intended data structure.

No requirement, task sequence, path, commit hash, lifecycle state or audit verdict was found changed by this formatting pass.

No historical audit report was rewritten.

The final sidecar reports:

```text
GLOBAL_FORMAT_BASELINE=359
GLOBAL_FORMAT_CURRENT=358
GLOBAL_FORMAT_NO_REGRESSION=PASS
```

Because Ruff 0.16.2 is unavailable in the independent audit container, that global count is not independently replayed here.

No V4 remediation finding is opened solely for this tooling limitation. The baseline-aware Ruff/format gates must be rerun again before the next audit bundle.

## 10. MAJOR-V4-01 — capture can persist item-level orphan references that canonical restore rejects

### 10.1 Requirement violated

`F11-014` requires:

> manifests/connections/models/routes are referentially coherent

`DP-134` requires:

> `ModelCatalog`, accepted provider connections and provider-specific model routes referentially bound to the canonical `ProviderRegistry`

The state repository's own capture contract states that a captured aggregate is intended to be one canonical restore can rebuild.

### 10.2 Why V3 graph guards are insufficient

The V3 guards prove that the component objects belong to one graph.

They do not prove that every item still refers to an entity currently present in that graph.

Current capture validates only active manifests against current provider ids before returning:

```text
providers.list()
manifests.list()
models.list()
connections.list()
routes.list()
```

There is no equivalent capture-time referential validation for:

```text
ModelSpec.provider_id
ProviderConnection.provider_id
ModelRoute.connection_id
```

### 10.3 Independent reproduction

A single, correctly wired graph was built:

```text
ProviderRegistry:
  x

ModelCatalog:
  model m -> provider x

ProviderConnectionRegistry:
  x:main -> provider x

ModelRouteCatalog:
  x:main:m -> connection x:main
```

Then only the canonical provider was removed:

```text
providers.remove("x")
```

All catalogs remain bound to the exact same object graph.

Independent result:

```text
ORPHAN_CAPTURE_ACCEPTED=True
COUNTS providers=0 manifests=0 models=1 connections=1 routes=1
```

The resulting aggregate was then passed to the canonical restore path.

Result:

```text
ORPHAN_RESTORE_FAILS=True
RESTORE_EXCEPTION=ProviderError Unknown registered provider: x
```

Therefore capture can emit a supposedly coherent persistent envelope that canonical restore itself refuses.

### 10.4 Impact

This breaks a load-bearing persistence invariant.

A runtime can successfully save an aggregate that cannot survive restart.

That is not merely defensive validation of an impossible hand-built state: `ProviderRegistry.remove()` is a real canonical mutation seam, while dependent catalogs retain their items.

### 10.5 Acceptance gap

The current V3 acceptance tests provider removal for manifest non-divergence, but intentionally avoids dependent model/connection/route state.

It therefore proves:

```text
removed provider -> stale manifest hidden
```

but not:

```text
removed provider + dependent canonical state -> capture remains restorable/fails closed
```

### 10.6 Required Remediation V4 direction

Do not introduce cascading registries or a generic teardown engine merely for this finding.

At minimum, capture must fail closed before state construction when:

```text
any model.provider_id is absent from current providers
any connection.provider_id is absent from current providers
any route.connection_id is absent from current connections
```

Use a focused coherence error.

Do not silently drop dependent state unless Remediation V4 design can prove silent omission is the already-canonical teardown policy.

Connected acceptance must:

1. create one real canonical provider;
2. create a dependent model, connection and route;
3. remove only the provider;
4. prove capture cannot produce an unrestorable aggregate;
5. prove repository revision/state does not advance if a coordinated save reaches this incoherence.

A same-id remove/re-register scenario should also be inspected during Remediation V4 design because id reuse can mask stale dependent records even when the orphan-id check no longer fires.

```text
MAJOR-V4-01=OPEN
```

## 11. MAJOR-V4-02 — caller-created `ConnectionProposal` bypasses canonical isolation and endpoint authority

### 11.1 Requirement violated

`DP-134` requires:

> subscription providers requiring isolation cannot become connected without a validated CMM-owned isolation outcome

The Phase 11.34 onboarding design also says:

```text
Detection is evidence, not authority.
The connection endpoint always comes from the canonical manifest.
For any provider/manifest with requires_isolation=True:
failed/missing isolation => MUST NOT become CONNECTED.
```

The original atomic onboarding design requires:

```text
normalize + validate proposal
preflight provider existence
...
prepare/validate required isolation
```

### 11.2 Public proposal contract

`ConnectionProposal` is:

- a public dataclass;
- exported through `kernel.llm.__init__`;
- directly constructible by callers.

Its own documentation describes it as evidence, not state.

### 11.3 Acceptance implementation gap

`ProviderOnboardingService.accept()` currently begins with:

```text
type-check proposal
derive connection_id from proposal
duplicate/credential/profile preflights
perform isolation only if proposal.requires_isolation
validator(proposal)
construct ProviderConnection directly from proposal fields
```

It does not re-resolve or revalidate the proposal against the current active canonical manifest.

Consequently the caller controls, at acceptance time:

```text
endpoint
billing_class
display_name
requires_isolation
```

subject only to dataclass shape validation.

### 11.4 Independent Codex reproduction

Canonical production bootstrap was used.

The active Codex manifest reports:

```text
CANONICAL_REQUIRES_ISOLATION=True
```

The auditor directly constructed:

```text
provider_id=codex
endpoint=https://evil.example/v1
requires_isolation=False
billing_class=subscription
source_home=None
```

with a validator returning success.

Independent output:

```text
FORGED_ACCEPTED=True
STATUS=connected
ENDPOINT=https://evil.example/v1
ISOLATION_REF=None
PROFILE_EXISTS=False
```

Thus canonical Codex became `CONNECTED`:

- without CMM-owned isolation;
- without source-home isolation evidence;
- using a noncanonical endpoint.

### 11.5 Why this is not merely misuse

The design explicitly separates:

```text
propose()
accept()
```

and exports `ConnectionProposal` as a public value object.

If `accept()` relies on a proposal having been minted by the same service, that provenance is neither encoded nor checked.

More importantly, the module-level authority rule claims that neither candidate nor proposal evidence can override canonical endpoint/isolation authority; the implementation does exactly that when `accept()` receives a directly built or stale proposal.

### 11.6 Impact

This reopens the security invariant at the final authority boundary.

The safe behavior of `propose()` is insufficient if `accept()` can be called with an untrusted or stale proposal that suppresses isolation.

### 11.7 Required Remediation V4 direction

Do not create a token/signature framework unless inspection proves it is necessary.

The minimal fail-closed direction is acceptance-time canonical revalidation.

Before any side effect, `accept()` must resolve the active canonical provider/manifest and ensure that proposal-controlled authority fields cannot weaken canonical policy.

At minimum inspect/freeze rules for:

```text
provider exists canonically
active manifest exists
proposal.endpoint matches canonical manifest endpoint
proposal.billing_class does not contradict canonical manifest
proposal.requires_isolation cannot be false when canonical manifest requires true
display-name authority remains deterministic
```

Observed external-risk isolation carried by a legitimate proposal must not be accidentally weakened.

Connected acceptance must directly construct/tamper a Codex proposal and prove:

```text
requires_isolation=False -> rejected before side effects
foreign endpoint -> rejected before side effects
validator success cannot override rejection
no credential/profile/connection/revision mutation
```

```text
MAJOR-V4-02=OPEN
```

## 12. MAJOR-V4-03 — coordinator discovery accepts noncanonical manifest policy

### 12.1 Requirement violated

`F11-014` requires one canonical Provider Registry with referentially coherent manifest/model/connection/route state.

The Remediation V3 architecture strengthened exact graph identity precisely so same-id metadata from another authority cannot affect canonical behavior.

### 12.2 Operation-boundary gap

`ProviderRegistryStateCoordinator` owns:

```text
self._manifests
```

and its constructor proves that this manifest registry belongs to the exact canonical ProviderRegistry.

But:

```text
coordinator.discover_models(connection, manifest, client, seen_at=...)
```

accepts an arbitrary caller-supplied `ProviderManifest`.

The method:

- verifies only that `manifest` is a `ProviderManifest`;
- canonicalizes the connection by looking up `connection_id`;
- passes the caller's manifest directly into canonical `discover_models()`.

It does not require:

```text
self._manifests.get(registered.provider_id) is manifest
```

or an equivalent canonical-manifest check.

### 12.3 Independent reproduction

A coherent canonical DeepSeek graph was built.

Its active manifest had:

```text
CANONICAL_ALLOWLIST=()
```

The auditor separately constructed a same-id manifest:

```text
provider_id=deepseek
default_base_url=https://foreign.example/v1
activation_allowlist=("deepseek-chat",)
```

The discovery client returned:

```text
deepseek-chat
deepseek-reasoner
```

Independent result:

```text
FOREIGN_MANIFEST_OPERATION_ACCEPTED=True
REASONER_AVAILABLE=False
RESULT_UNAVAILABLE=('deepseek:main:deepseek-reasoner',)
```

The canonical coordinator also persisted audit events derived from the foreign policy:

```text
route.discovered deepseek:main:deepseek-chat
route.discovered deepseek:main:deepseek-reasoner
route.unavailable deepseek:main:deepseek-reasoner
```

### 12.4 Impact

The V3 construction guard can prove the runtime was built over one authority, yet a later operation can inject a different metadata authority into that graph.

A foreign same-id allowlist can therefore change:

- route availability;
- durable Provider Registry state;
- audit history;
- subsequent routing inventory.

### 12.5 Required Remediation V4 direction

Do not introduce another manifest registry.

Prefer one of two narrow designs, to be chosen after read-only inspection:

1. coordinator resolves the canonical manifest internally from `self._manifests` using the canonical registered connection's provider id; or
2. retain the parameter for compatibility but require exact active-manifest identity and fail closed before route mutation.

The operation must also prove the manifest corresponds to the canonical connection provider.

Connected acceptance must pass a separately constructed same-id manifest with a different allowlist and prove:

```text
operation rejected
routes unchanged
revision unchanged
audit log unchanged
repository unchanged
```

```text
MAJOR-V4-03=OPEN
```

## 13. MINOR-V4-01 — older discovery timestamps regress `last_seen_at`

### 13.1 V3 design intent

The approved V3 design defines refresh as a route advertised again at:

```text
a newer aware timestamp
```

and says a durable mutation occurs when:

```text
last_seen_at advances
```

### 13.2 Implementation behavior

The refresh detector checks only:

```text
previous.last_seen_at != current.last_seen_at
```

while `ModelRouteCatalog.mark_seen()` stores the caller's aware timestamp directly.

No monotonicity guard exists.

### 13.3 Independent reproduction

The auditor first discovered a route at:

```text
T1 = 2026-09-15T02:00:00+00:00
```

and then called discovery with:

```text
T0 = 2026-09-15T01:00:00+00:00
```

Independent result:

```text
LAST_SEEN_AFTER_OLDER=2026-09-15T01:00:00+00:00
REVISION=2
```

Audit sequence:

```text
revision 1 route.discovered occurred_at=02:00
revision 2 route.refreshed occurred_at=01:00
```

The latest revision therefore contains an older "last seen" value and an earlier audit timestamp.

### 13.4 Impact

This does not by itself create a second authority or an unrestorable aggregate, so it is classified minor.

But it violates the intended meaning of:

```text
last_seen_at
route.refreshed
```

under out-of-order administrative discovery timestamps.

### 13.5 Required Remediation V4 direction

Freeze one deterministic monotonic policy during Remediation V4 design.

Acceptable narrow outcomes include:

- reject an older `seen_at` before mutation; or
- treat an older observation as non-advancing/no-op while preserving the current later timestamp.

Do not silently regress `last_seen_at`.

Acceptance must cover:

```text
T1 then older T0
last_seen_at remains T1
no misleading backward refresh revision/event
```

```text
MINOR-V4-01=OPEN
```

## 14. `AT-DP-134` independent adequacy

Execution is healthy:

```text
AT-DP-134_TEST_EXECUTION=PASS
AT-DP-134_TEST_COUNT=44
```

But adequacy is still insufficient for closure because the connected acceptance does not cover:

```text
provider removal while dependent models/connections/routes remain
direct caller-created proposal bypassing canonical isolation/endpoint policy
foreign same-id manifest injected into coordinator discovery
older seen_at after a newer persisted route observation
```

All four are independently reproducible through public/canonical Phase 11.34 surfaces.

Therefore:

```text
AT-DP-134=FAIL_INDEPENDENT_ADEQUACY
```

## 15. `F11-014` assessment

`F11-014` requires one canonical, persistent, auditable and fail-closed Provider Registry in which:

```text
provider identity is authoritative through ProviderRegistry
manifests/connections/models/routes are referentially coherent
subscription isolation policy is explicit
onboarding side effects are ownership-safe
discovery remains non-inference
DP-134 is verified through AT-DP-134
```

The new majors violate the first three load-bearing clauses:

- V4-01: dependent items are not capture-time referentially coherent after provider removal;
- V4-02: canonical isolation/endpoint authority can be bypassed at acceptance;
- V4-03: canonical manifest authority can be bypassed at discovery.

Therefore:

```text
F11-014=NOT_VERIFIED
```

## 16. `DP-134` assessment

`DP-134` is not satisfied because all of the following must hold simultaneously:

- exactly one authoritative provider identity inventory;
- models/connections/routes referentially bound to it;
- persistent state is restorable through the canonical repository boundary;
- required-isolation providers cannot connect without validated CMM isolation;
- detection/proposal evidence is not authority;
- discovery is administrative but canonical;
- no parallel inventory/runtime exists.

Re-audit V4 independently disproves three of those requirements.

Therefore:

```text
DP-134=NOT_VERIFIED
```

## 17. Security assessment

No new raw-secret persistence path was found in the V3 code delta.

The V3 production changes do not introduce:

- secret getters;
- raw API-key persistence;
- new credential stores;
- external command secret argv handling;
- CMM Usage integration;
- CMMChat integration;
- Phase 11.35.

However, `MAJOR-V4-02` is itself a security/authority defect because it allows fail-closed isolation policy to be bypassed.

Therefore the audit does not issue a blanket phase-level security PASS despite the raw-secret boundary remaining intact.

```text
RAW_SECRET_BOUNDARY=PASS
FAIL_CLOSED_ISOLATION_AUTHORITY=FAIL
```

## 18. Scope / architecture review

Remediation V3 itself stayed within its approved scope.

No:

- `ProviderRegistryGraph`;
- second provider inventory;
- generic transaction framework;
- generic persistence framework;
- routing engine;
- usage catalog;
- CMMChat integration;
- Phase 11.35 implementation

was introduced.

```text
REMEDIATION_V3_SCOPE=PASS
CMM_USAGE_INTEGRATION=NOT_PERFORMED
CMMCHAT=DEFERRED_BY_USER
PHASE11_35=NOT_IMPLEMENTED_BY_THIS_REMEDIATION
```

## 19. Final verdict

```text
INDEPENDENT_REAUDIT_V4=FAIL
BLOCKERS=0
MAJORS=3
MINORS=1

MAJOR-V4-01=OPEN
MAJOR-V4-02=OPEN
MAJOR-V4-03=OPEN
MINOR-V4-01=OPEN

MAJOR-V3-01=VERIFIED_REMEDIATED
MAJOR-V3-02=VERIFIED_REMEDIATED
MINOR-V3-01=REMEDIATION_ARTIFACT_VERIFIED
GLOBAL_RUFF_FORMAT_REPLAY=UNAVAILABLE_IN_AUDIT_ENVIRONMENT

BUNDLE_SHA256=PASS
GZIP_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
EXACT_TREE_BINDING=PASS
ARCHIVE_FILE_COUNT=PASS
REMEDIATION_V3_SCOPE=PASS

AT-DP-134_TEST_EXECUTION=PASS
AT-DP-134_TEST_COUNT=44
FOCUSED_V3_INDEPENDENT=PASS
FOCUSED_V3_TEST_COUNT=200
LLM_SUITE_INDEPENDENT=PASS
LLM_SUITE_TEST_COUNT=640
COMPILEALL_INDEPENDENT=PASS

PHASE10_46_INDEPENDENT_REPLAY=UNAVAILABLE_MISSING_LIBCST
RUFF_INDEPENDENT_REPLAY=UNAVAILABLE_MISSING_RUFF

RAW_SECRET_BOUNDARY=PASS
FAIL_CLOSED_ISOLATION_AUTHORITY=FAIL

DP-134=NOT_VERIFIED
F11-014=NOT_VERIFIED
AT-DP-134=FAIL_INDEPENDENT_ADEQUACY
CLOSURE_ELIGIBLE=NO

AUDITED_HEAD=46ef38ae477c801975b55b92c5f31f9137a3bc12
AUDITED_TREE=4f24aed198e86d702791bef46d71df7d281a767d
AUDITED_BUNDLE_SHA256=d8a21eac304d56789ee54b08bc6e96fa4e7ed995ef829897e9e1c268771c4f64

CMM_USAGE_INTEGRATION=NOT_PERFORMED
CMMCHAT=DEFERRED_BY_USER
PHASE11_35=NOT_IMPLEMENTED_BY_THIS_REMEDIATION
PUSH=NO
MERGE=NO
```

## 20. Required Remediation V4 scope

Remediation V4 must remain findings-only.

Authorized findings:

```text
MAJOR-V4-01
MAJOR-V4-02
MAJOR-V4-03
MINOR-V4-01
```

### 20.1 V4-01 — capture referential coherence

Inspect and freeze the smallest fail-closed capture policy for:

```text
ModelSpec.provider_id -> current ProviderRegistry
ProviderConnection.provider_id -> current ProviderRegistry
ModelRoute.connection_id -> current ProviderConnectionRegistry
```

Also inspect same-id provider replacement with surviving dependent entries before deciding whether id-presence checks alone are sufficient.

Do not introduce automatic global cascading teardown unless existing contracts prove it is canonical.

### 20.2 V4-02 — acceptance-time proposal authority

Inspect the public `ConnectionProposal` contract and freeze acceptance-time canonical revalidation.

A forged/stale proposal must never weaken:

```text
canonical endpoint
canonical billing/provider identity
canonical requires_isolation=True
```

Rejection must happen before credential/profile/connection/revision side effects.

Do not add proposal cryptography/signatures unless inspection proves simple canonical revalidation is insufficient.

### 20.3 V4-03 — discovery-time manifest authority

Inspect whether the least disruptive API is:

```text
coordinator internally resolves canonical manifest
```

or:

```text
manifest parameter retained but exact active-manifest identity required
```

Whichever is chosen must reject same-id foreign policy before route mutation.

### 20.4 V4-01 minor — monotonic discovery time

Freeze deterministic older-timestamp behavior.

No older discovery may regress durable `last_seen_at`.

### 20.5 Connected acceptance

Keep the same:

```text
DP-134
AT-DP-134
```

Add connected adversaries for all V4 findings.

Do not create a new DP.

## 21. Next canonical cycle

```text
COMMIT INDEPENDENT RE-AUDIT V4 REPORT
→ REMEDIATION V4 READ-ONLY INSPECTION
→ REMEDIATION V4 DESIGN SPEC
→ COMMIT SPEC
→ REMEDIATION V4 IMPLEMENTATION PLAN
→ COMMIT PLAN
→ AUTONOMOUS IMPLEMENTATION PROMPT
→ TDD IMPLEMENTATION
→ FULL GATES
→ PENDING-REAUDIT DOCUMENTATION
→ CLEAN EXACT-HEAD BUNDLE
→ INDEPENDENT RE-AUDIT V5
```

No docs-only closure commit is permitted until a later independent audit reaches:

```text
BLOCKERS=0
MAJORS=0
DP-134=VERIFIED_EXISTING
AT-DP-134=PASS
F11-014=VERIFIED_EXISTING
CLOSURE_ELIGIBLE=YES
```
