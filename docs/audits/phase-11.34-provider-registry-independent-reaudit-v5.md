# Phase 11.34 — Provider Registry — Independent Re-audit V5

**Independent verdict:** `FAIL`

**Audit date:** 2026-09-15
**Auditor:** ChatGPT independent audit
**Scope:** Phase 11.34 Provider Registry — Remediation V4 exact-HEAD bundle
**Claimed branch:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `30dec367279b0b80a9692ee0f067365c6e93b0a7`
**Audited tree:** `e058dca561efba5d9c0bc58165b12c19761e797c`
**Bundle:** `cmm-os-phase11-34-remediation-v4-30dec367279b.tar.gz`
**Bundle SHA-256:** `b72e03d78622b2927a9081bea4b180e1343ba9b8e2aea326bf44604ca3580d32`
**Design Point:** `DP-134`
**Connected Acceptance:** `AT-DP-134`

## 1. Executive conclusion

Remediation V4 materially improves Phase 11.34 and independently closes the exact defects reported as:

- `MAJOR-V4-01` — capture now rejects stale item-level provider/connection authority, including same-id replacement;
- `MAJOR-V4-02` — `ProviderOnboardingService.accept()` now revalidates public `ConnectionProposal` authority against the active canonical manifest before validator or side effects;
- `MAJOR-V4-03` — coordinator discovery now requires the exact active canonical manifest before consulting the discovery client.

Independent execution on the exact bundle passes:

```text
AT-DP-134 = 60 passed
focused V4 suite = 340 passed
tests/llm = 709 passed
selected roadmap/lifecycle regressions = 17 passed
compileall = PASS
```

The exact Remediation V4 delta is findings-focused:

```text
ADDED=3
REMOVED=0
CHANGED=16
```

and no CMM Usage, CMMChat or Phase 11.35 implementation was introduced.

However, deeper operation-boundary testing found two closure-blocking failures:

1. a `ProviderConnection` whose exact provider authority is stale can still drive an administrative discovery client call before the coordinator finally fails at capture/persistence;
2. the new discovery monotonicity guard uses only route `last_seen_at`, which is not advanced by every state-changing discovery pass. A newer disappearance/allowlist transition can therefore be followed by an older snapshot that is accepted, restores a route and persists stale availability.

The second failure demonstrates that `MINOR-V4-01` is only partially remediated. Its direct `T1 -> T0` case is blocked, but the connection-level monotonic snapshot invariant is not complete.

Therefore:

```text
INDEPENDENT_REAUDIT_V5=FAIL
BLOCKERS=0
MAJORS=2
MINORS=0

MAJOR-V5-01=OPEN
MAJOR-V5-02=OPEN

MAJOR-V4-01=VERIFIED_REMEDIATED
MAJOR-V4-02=VERIFIED_REMEDIATED
MAJOR-V4-03=VERIFIED_REMEDIATED
MINOR-V4-01=PARTIALLY_REMEDIATED
MINOR-V4-01_ESCALATION=MAJOR-V5-02

DP-134=NOT_VERIFIED
F11-014=NOT_VERIFIED
AT-DP-134_TEST_EXECUTION=PASS
AT-DP-134_TEST_COUNT=60
AT-DP-134=FAIL_INDEPENDENT_ADEQUACY
CLOSURE_ELIGIBLE=NO
```

Phase 11.34 remains implemented and pending independent re-audit. It is not closure-eligible.

## 2. Artifact integrity

All checks in this section were executed directly against the uploaded exact-HEAD TAR.GZ and sidecar manifest.

### 2.1 SHA-256

Independent recomputation:

```text
b72e03d78622b2927a9081bea4b180e1343ba9b8e2aea326bf44604ca3580d32
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
30dec367279b0b80a9692ee0f067365c6e93b0a7
```

This exactly matches the manifest.

```text
EXACT_HEAD_BINDING=PASS
```

### 2.4 Exact tree reconstruction

The archive was extracted and imported into a clean Git index using forced add so repository `.gitignore` rules could not hide tracked archive members.

`git write-tree` returned:

```text
e058dca561efba5d9c0bc58165b12c19761e797c
```

This exactly matches `AUDITED_TREE`.

```text
EXACT_TREE_BINDING=PASS
```

### 2.5 Archive file count

Independent archive enumeration and reconstructed Git index both produced:

```text
2283
```

```text
ARCHIVE_FILE_COUNT=PASS
ARCHIVE_FILE_LIST_MATCHES_HEAD=PASS
```

## 3. Exact Remediation V4 scope delta

The V5 bundle was compared with the exact predecessor bundle audited by Independent Re-audit V4:

```text
cmm-os-phase11-34-remediation-v3-46ef38ae477c.tar.gz
```

Result:

```text
ADDED=3
REMOVED=0
CHANGED=16
```

### 3.1 Added

```text
docs/audits/phase-11.34-provider-registry-independent-reaudit-v4.md
docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v4-implementation-plan.md
docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v4-design.md
```

### 3.2 Changed

```text
ROADMAP.md
docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md
docs/roadmap/phase-11-stable-integrated-platform.md
kernel/llm/model_catalog.py
kernel/llm/model_routes.py
kernel/llm/provider_connections.py
kernel/llm/provider_onboarding.py
kernel/llm/provider_state_coordinator.py
kernel/llm/provider_state_repository.py
tests/llm/test_model_catalog_v2.py
tests/llm/test_model_routes.py
tests/llm/test_provider_connections.py
tests/llm/test_provider_onboarding.py
tests/llm/test_provider_registry_dp134_acceptance.py
tests/llm/test_provider_state_coordinator.py
tests/llm/test_provider_state_repository.py
```

All production changes are inside the expected six Provider Registry files.

No unrelated production subsystem implementation was found.

```text
REMEDIATION_V4_FINDINGS_ONLY_SCOPE=PASS
```

## 4. Independent test execution

### 4.1 Connected `AT-DP-134`

Executed from the exact bundle:

```text
python3 -m pytest -q tests/llm/test_provider_registry_dp134_acceptance.py
```

Result:

```text
60 passed
```

```text
AT-DP-134_TEST_EXECUTION=PASS
```

### 4.2 V4 focused suite

Executed:

```text
tests/llm/test_model_catalog_v2.py
tests/llm/test_provider_connections.py
tests/llm/test_model_routes.py
tests/llm/test_provider_state_repository.py
tests/llm/test_provider_onboarding.py
tests/llm/test_provider_state_coordinator.py
tests/llm/test_provider_registry_dp134_acceptance.py
```

Result:

```text
340 passed
```

```text
FOCUSED_V4_INDEPENDENT=PASS
```

### 4.3 Full LLM subsystem

Executed:

```text
python3 -m pytest -q tests/llm
```

Result:

```text
709 passed
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

These limitations do not affect the FAIL verdict because both open majors below are independently reproducible using the exact bundle and the standard Python environment.

### 5.1 Phase 10.46

The canonical DP-046 acceptance could not collect because the audit environment lacks `libcst`:

```text
ModuleNotFoundError: No module named 'libcst'
```

The implementation-machine evidence reports:

```text
14 passed
```

but that result is not labeled independently replayed here.

### 5.2 Ruff

The audit environment has no Ruff module.

The manifest reports:

```text
RUFF_BASELINE=839
RUFF_CURRENT=837
FORMAT_BASELINE=359
FORMAT_CURRENT=359
RUFF_NO_REGRESSION=PASS
FORMAT_NO_REGRESSION=PASS
```

Those counts cannot be independently replayed in this audit container.

### 5.3 Global pytest

A full `pytest -q` run exceeded the independent audit command window before producing a usable terminal result.

The implementation-machine evidence reports:

```text
18239 passed
```

but that full-suite count is not described as independently replayed by ChatGPT.

## 6. Disposition of Re-audit V4 findings

| Re-audit V4 finding | V5 disposition | Result |
| --- | --- | --- |
| `MAJOR-V4-01` item-level stale authority capture | `VERIFIED_REMEDIATED` | Model/provider, connection/provider and route/connection bindings now survive same-id replacement correctly and capture fails closed. |
| `MAJOR-V4-02` forged/stale `ConnectionProposal` authority | `VERIFIED_REMEDIATED` | Canonical display/billing/endpoint/isolation are revalidated before validator and side effects. |
| `MAJOR-V4-03` foreign discovery manifest | `VERIFIED_REMEDIATED` | Exact active manifest identity is required before client call or route mutation. |
| `MINOR-V4-01` monotonic discovery snapshot | `PARTIALLY_REMEDIATED` | Direct older-than-current-route timestamp is rejected, but state-changing passes that do not advance `last_seen_at` leave a temporal hole reproduced in §10. |

## 7. `MAJOR-V4-01` — verified remediated in its approved scope

The V4 implementation adds exact in-memory authority bindings:

```text
ModelCatalog item -> exact ProviderSpec
ProviderConnectionRegistry registration -> exact ProviderSpec
ModelRouteCatalog item -> stable connection-registration identity
```

Capture now validates every enumerated model, connection and route against those bindings.

Independent suite execution includes the new same-id replacement adversaries.

The original V4 reproductions are no longer possible:

```text
provider removed + dependents -> capture reject
same-id provider replacement + old dependents -> capture reject
same-id connection replacement + old route -> capture reject
coherent restore -> fresh coherent recapture
```

### 7.1 Accepted implementation ruling: stable registration marker

The frozen design described routes as bound to the exact `ProviderConnection` object.

The final implementation instead binds routes to a private stable `_ConnectionRegistration.marker`.

This is an architectural deviation, but the audit accepts the ruling because:

- `ProviderConnection` is frozen and normal status updates replace the value object;
- binding to that transient value would make a valid status transition falsely stale;
- the marker is a bare in-memory `object`;
- it has no id, counter, UUID or persisted representation;
- there is still only one `ProviderConnectionRegistry`;
- route capture still proves same-registration identity;
- remove/re-register creates a fresh marker, so same-id revival fails.

This preserves the load-bearing authority invariant without introducing a parallel registry or persistent generation system.

```text
V4_RULING_CONNECTION_REGISTRATION_MARKER=ACCEPTED
MAJOR-V4-01=VERIFIED_REMEDIATED
```

## 8. `MAJOR-V4-02` — verified remediated

`ProviderOnboardingService.accept()` now:

1. type-checks the public proposal;
2. resolves the current canonical provider;
3. resolves the active canonical manifest;
4. rejects display-name, billing-class and endpoint contradiction;
5. rejects isolation weakening;
6. only then proceeds to duplicate/credential/profile preflight and side effects.

The final accepted `ProviderConnection` is built from canonical manifest metadata.

Independent exact-bundle tests pass for:

```text
Codex requires_isolation=True + proposal False -> reject
foreign endpoint -> reject
wrong billing class -> reject
wrong display name -> reject
stale proposal after authority replacement -> reject
proposal isolation strengthening -> not rejected as authority mismatch
```

The authority helper runs before the injected validator and operation-owned writes.

```text
MAJOR-V4-02=VERIFIED_REMEDIATED
```

## 9. `MAJOR-V4-03` — verified remediated

At coordinator discovery:

```text
registered = canonical connection registry lookup
canonical_manifest = manifest registry lookup for registered.provider_id
```

and:

```text
canonical_manifest is manifest
```

is required.

The manifest check occurs before:

```text
client.list_models()
route mutation
audit mutation
revision increment
repository save
```

Foreign same-id and formerly active stale manifests are rejected by the focused and connected acceptance suites.

```text
MAJOR-V4-03=VERIFIED_REMEDIATED
```

## 10. MAJOR-V5-01 — stale provider-bound connection can still authorize external discovery work

### 10.1 Requirement violated

`F11-014` requires:

> provider identity is authoritative through `ProviderRegistry`, manifests/connections/models/routes are referentially coherent, and the Provider Registry is fail-closed.

`DP-134` requires accepted provider connections and provider-specific routes to remain referentially bound to the canonical authority.

Remediation V4 correctly added exact item-level binding and made capture fail closed, but discovery does not revalidate that the registered connection still belongs to the current canonical provider before invoking the external administrative client.

### 10.2 Relevant final implementation

`ProviderRegistryStateCoordinator.discover_models()` currently performs:

```text
registered = self._connections.get(connection.connection_id)
canonical_manifest = self._manifests.get(registered.provider_id)
require canonical_manifest is manifest
latest_seen temporal check
client discovery
...
_commit()
```

It does **not** perform:

```text
self._connections.is_bound_to_current_provider(registered)
```

before the external client call.

By contrast, `update_connection_status()` explicitly performs that item-level authority preflight before mutation.

### 10.3 Independent reproduction

A canonical provider/manifest/connection was created under ProviderSpec A.

Then:

```text
remove ProviderSpec A
register ProviderSpec B with same provider_id
register fresh active manifest B
leave accepted connection A in ProviderConnectionRegistry
```

The final registry correctly reports:

```text
connection_bound_current=False
```

The auditor then called:

```text
coordinator.discover_models(
    stale_connection_A,
    active_manifest_B,
    recording_client,
    seen_at=...
)
```

Independent output:

```text
connection_bound_current=False
exception=ProviderStateCoherenceError
connection x:main is bound to a stale or missing ProviderSpec
client_calls=1
routes=()
revision=0
repo=None
```

The eventual persistence guard works: `_commit()` reaches capture, capture rejects the stale connection, the route catalog rolls back, and no revision is published.

But the fail-closed decision happens **after**:

```text
client.list_models()
```

has already executed.

### 10.4 Supporting route-boundary reproduction

With the same stale provider-bound connection still present, direct route registration currently succeeds:

```text
CONNECTION_CURRENT=False
ROUTE_REGISTER_ACCEPTED=True
ROUTE_CURRENT_CONNECTION=True
```

The new route is bound to the same accepted connection registration marker even though that registration is no longer bound to the current canonical provider.

Capture later rejects the parent connection, but the in-memory operation was still authorized by stale connection state.

### 10.5 Impact

This is not a persistence-corruption defect: capture still protects durable state.

It is an operation-authority defect.

Administrative discovery can perform external I/O under an accepted connection whose canonical provider authority has been removed/replaced.

In the real integration, a discovery client can be configured from that stale connection's old endpoint/auth context. A retired provider connection therefore remains operational long enough to perform a network request before the registry detects incoherence.

That contradicts a fail-closed canonical authority boundary.

### 10.6 Acceptance gap

The 60-test `AT-DP-134` proves:

```text
stale connection -> capture fails
stale connection -> status transition fails before mutation
foreign manifest -> client not called
```

but does not combine:

```text
stale provider-bound registered connection
+
fresh active same-id manifest
+
discovery operation
```

and assert zero client calls.

### 10.7 Required Remediation V5 direction

Do not add another connection authority or client registry.

The minimal operational guard is:

```text
registered = self._connections.get(connection.connection_id)

require registered exists

require
  self._connections.is_bound_to_current_provider(registered)
before:
  manifest resolution
  temporal check
  client.list_models()
```

Raise the existing:

```text
ProviderStateCoherenceError
```

with the same stale/missing ProviderSpec language already used by capture/status transitions.

During Remediation V5 read-only inspection, also decide whether the direct `ModelRouteCatalog.register()/restore()` boundary must reject a stale provider-bound connection, or whether the coordinator preflight plus capture is the correct canonical operational boundary.

Do not introduce cascading teardown.

Connected acceptance must prove:

```text
same-id provider replacement
old accepted connection survives
fresh active manifest exists
discovery rejects before client call
routes unchanged
revision unchanged
audit unchanged
repository unchanged
```

```text
MAJOR-V5-01=OPEN
```

## 11. MAJOR-V5-02 — connection-level temporal guard can be bypassed after a newer state-changing pass

### 11.1 Relationship to `MINOR-V4-01`

The direct V4 adversary:

```text
route at T1
then discovery at T0 < T1
```

is now rejected.

That is genuine progress.

However, Remediation V4 defines discovery as a **connection-level snapshot** and intends older snapshots to be rejected before reconciliation.

The implementation computes the temporal floor only as:

```text
max(route.last_seen_at for routes of this connection)
```

That works only if every state-changing discovery pass advances at least one route's `last_seen_at`.

The canonical reconciler intentionally does not do that for every transition.

### 11.2 Existing canonical behavior that creates the hole

For an existing model excluded by `activation_allowlist`:

```text
discover_models()
```

does not call:

```text
mark_seen()
```

when the route remains deferred.

Likewise, a route marked unavailable because it disappeared keeps the timestamp of the last pass in which the provider advertised it.

This behavior is deliberately pinned by existing tests.

Therefore a newer state-changing pass can emit a durable `route.unavailable` audit event at `T1` while **all** route `last_seen_at` values remain at `T0`.

### 11.3 Independent reproduction

Canonical setup:

```text
activation_allowlist=("a",)

T0 = 01:00
TM = 01:30
T1 = 02:00
```

#### Pass 1 — T0

Provider advertises:

```text
a
b
```

Result:

```text
a: available=True,  last_seen_at=T0
b: available=False, last_seen_at=T0   # deferred by allowlist
revision=1
```

#### Pass 2 — T1

Provider advertises only:

```text
b
```

Because `b` is already deferred, it is not marked seen.

`a` disappeared, so it becomes unavailable.

Result:

```text
a: available=False, last_seen_at=T0
b: available=False, last_seen_at=T0
revision=2
audit: route.unavailable(a) occurred_at=T1
```

The newest durable connection snapshot is T1, but:

```text
max(route.last_seen_at) == T0
```

#### Pass 3 — stale TM

A stale snapshot from:

```text
TM=01:30
```

advertises:

```text
a
b
```

Because:

```text
TM > max(last_seen_at)=T0
```

the V4 monotonicity guard accepts it even though:

```text
TM < T1
```

Independent output:

```text
stale accepted
client_calls=1

after TM:
a: available=True,  last_seen_at=TM
b: available=False, last_seen_at=T0
revision=3
```

Persisted audit sequence:

```text
revision 1 route.discovered a @ T0
revision 1 route.discovered b @ T0
revision 1 route.unavailable b @ T0
revision 2 route.unavailable a @ T1
revision 3 route.restored a @ TM
```

Thus a **later revision at an older snapshot time** reverses the availability state established by the newer T1 discovery.

### 11.4 Impact

This is more serious than the original simple timestamp regression.

An out-of-order administrative snapshot can now:

- restore a route that a newer snapshot declared absent;
- persist that route as available;
- create a durable audit record whose observation time is older than the state it supersedes;
- expose stale route availability to later routing phases.

Because the stale snapshot changes persistent routing inventory, this is classified `MAJOR`, not `MINOR`.

### 11.5 Why `last_seen_at` alone cannot be the connection snapshot watermark

`last_seen_at` means:

```text
last pass in which this provider model was advertised
```

It deliberately does **not** mean:

```text
last successful connection discovery snapshot
```

Those concepts diverge on:

- disappearance;
- repeated allowlist deferral;
- other state-changing passes where no route is marked seen.

Therefore the monotonicity watermark must come from a source that advances whenever a discovery pass durably changes connection route state.

### 11.6 Required Remediation V5 direction

Do not add a generic time store until existing persisted evidence has been inspected.

The existing sanitized audit log is a likely canonical source:

```text
route.discovered
route.unavailable
route.restored
route.refreshed
```

already carry:

```text
occurred_at
connection_id
```

and are persisted/restored with coordinator state.

A narrow V5 design should inspect whether the coordinator can derive:

```text
latest durable discovery snapshot time for connection
```

from:

```text
relevant route audit records
+
route last_seen_at where necessary
```

before invoking the client.

The rule must survive restart.

A purely in-memory watermark is insufficient.

Connected acceptance must include the exact three-pass adversary:

```text
T0: a,b
T1: only deferred b -> a becomes unavailable
TM where T0 < TM < T1: a,b
```

and require:

```text
TM rejected before client call
a remains unavailable
revision remains 2
audit unchanged
repository unchanged
```

The existing direct `T1 -> older T0` adversary must remain green.

```text
MAJOR-V5-02=OPEN
MINOR-V4-01=PARTIALLY_REMEDIATED
MINOR-V4-01_ESCALATION=MAJOR-V5-02
```

## 12. `AT-DP-134` independent adequacy

Execution quality is strong:

```text
AT-DP-134_TEST_EXECUTION=PASS
AT-DP-134_TEST_COUNT=60
```

but adequacy is insufficient for closure.

Missing connected adversaries:

```text
stale provider-bound registered connection
+
fresh same-id active manifest
+
discovery
-> zero external client calls

and

T0 state
-> newer T1 state change with no last_seen advance
-> stale intermediate TM snapshot
-> reject before client / no stale route restoration
```

Both operate through canonical Phase 11.34 components.

Therefore:

```text
AT-DP-134=FAIL_INDEPENDENT_ADEQUACY
```

## 13. `F11-014` assessment

`F11-014` requires one canonical, persistent, auditable and fail-closed Provider Registry in which provider identity is authoritative, dependent catalogs are coherent, onboarding is ownership-safe, and discovery remains canonical/non-inference.

Remediation V4 now protects persistence from stale item authority and prevents proposal/manifest metadata from overriding canonical authority.

But:

- V5-01 allows an operational discovery call under a stale provider-bound connection before fail-closed rejection;
- V5-02 allows an older connection snapshot to overwrite newer route availability durably.

Thus provider/discovery authority is not yet fail-closed end to end.

```text
F11-014=NOT_VERIFIED
```

## 14. `DP-134` assessment

`DP-134` requires all load-bearing properties to hold simultaneously:

```text
one authoritative provider identity inventory
referentially bound models/connections/routes
persistent restorable state
sanitized auditable mutation history
required isolation cannot be weakened
onboarding proposal evidence is not authority
discovery metadata is canonical
administrative discovery state is fail-closed
no parallel inventory/runtime
```

V5 independently disproves the final operational closure through two public/canonical discovery paths.

Therefore:

```text
DP-134=NOT_VERIFIED
```

## 15. Security assessment

### 15.1 Raw-secret boundary

No V4 delta introduced:

- raw secret persistence;
- secret getters;
- new credential stores;
- secret-bearing audit records.

Provider connection persistence still contains only opaque credential refs.

```text
RAW_SECRET_BOUNDARY=PASS
```

### 15.2 Proposal authority

Forged endpoint/isolation/billing/display proposals fail before validator and side effects.

```text
PROPOSAL_AUTHORITY_FAIL_CLOSED=PASS
```

### 15.3 Manifest authority

Foreign/stale discovery manifests fail before the discovery client.

```text
DISCOVERY_MANIFEST_AUTHORITY_FAIL_CLOSED=PASS
```

### 15.4 Connection operation authority

A stale provider-bound accepted connection can still reach the discovery client before capture rejects it.

```text
DISCOVERY_CONNECTION_AUTHORITY_FAIL_CLOSED=FAIL
```

## 16. Architecture / scope assessment

Remediation V4 itself remains findings-focused.

No:

- CMM Usage integration;
- CMMChat integration;
- Phase 11.35 implementation;
- second provider/model/connection/route registry;
- `ProviderRegistryGraph`;
- persistent generation id;
- proposal-signing system;
- generic transaction framework;
- generic persistence framework

was introduced.

The private connection registration marker is accepted as a nonpersistent identity seam rather than a parallel authority.

```text
REMEDIATION_V4_SCOPE=PASS
PERSISTENT_GENERATION_IDS=NOT_INTRODUCED
CASCADING_TEARDOWN=NOT_INTRODUCED
CMM_USAGE_INTEGRATION=NOT_PERFORMED
CMMCHAT=DEFERRED_BY_USER
PHASE11_35=NOT_IMPLEMENTED_BY_THIS_REMEDIATION
```

## 17. Documentary state

The current machine-readable status remains correctly non-closure:

```text
PHASE11_34=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
REMEDIATION_V4=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
F11-014=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
DP-134=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
AT-DP-134=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
AUDIT_STATUS=PENDING_INDEPENDENT_REAUDIT_V5
```

The requirements matrix explicitly explains that `PASS_REPORTED` is not independent verification and reserves closure tokens as future criteria.

The prose phrase:

```text
Remediation V4 closes exactly the four Re-audit V4 findings
```

is stronger than ideal before independent audit, but the same paragraph and all machine-readable lifecycle markers clearly say pending independent re-audit. No separate documentary finding is opened because current state is unambiguous and non-closure.

Future remediation documentation should prefer:

```text
implements the intended remediation for
```

rather than:

```text
closes
```

before independent PASS.

## 18. Final verdict

```text
INDEPENDENT_REAUDIT_V5=FAIL
BLOCKERS=0
MAJORS=2
MINORS=0

MAJOR-V5-01=OPEN
MAJOR-V5-02=OPEN

MAJOR-V4-01=VERIFIED_REMEDIATED
MAJOR-V4-02=VERIFIED_REMEDIATED
MAJOR-V4-03=VERIFIED_REMEDIATED
MINOR-V4-01=PARTIALLY_REMEDIATED
MINOR-V4-01_ESCALATION=MAJOR-V5-02

BUNDLE_SHA256=PASS
GZIP_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
EXACT_TREE_BINDING=PASS
ARCHIVE_FILE_COUNT=PASS
REMEDIATION_V4_SCOPE=PASS

AT-DP-134_TEST_EXECUTION=PASS
AT-DP-134_TEST_COUNT=60
FOCUSED_V4_INDEPENDENT=PASS
FOCUSED_V4_TEST_COUNT=340
LLM_SUITE_INDEPENDENT=PASS
LLM_SUITE_TEST_COUNT=709
SELECTED_DOC_REGRESSIONS_INDEPENDENT=PASS
SELECTED_DOC_REGRESSIONS_TEST_COUNT=17
COMPILEALL_INDEPENDENT=PASS

PHASE10_46_INDEPENDENT_REPLAY=UNAVAILABLE_MISSING_LIBCST
RUFF_INDEPENDENT_REPLAY=UNAVAILABLE_MISSING_RUFF
GLOBAL_PYTEST_INDEPENDENT_REPLAY=UNAVAILABLE_AUDIT_TIMEOUT

RAW_SECRET_BOUNDARY=PASS
PROPOSAL_AUTHORITY_FAIL_CLOSED=PASS
DISCOVERY_MANIFEST_AUTHORITY_FAIL_CLOSED=PASS
DISCOVERY_CONNECTION_AUTHORITY_FAIL_CLOSED=FAIL
DISCOVERY_SNAPSHOT_MONOTONICITY=FAIL

DP-134=NOT_VERIFIED
F11-014=NOT_VERIFIED
AT-DP-134=FAIL_INDEPENDENT_ADEQUACY
CLOSURE_ELIGIBLE=NO

AUDITED_HEAD=30dec367279b0b80a9692ee0f067365c6e93b0a7
AUDITED_TREE=e058dca561efba5d9c0bc58165b12c19761e797c
AUDITED_BUNDLE_SHA256=b72e03d78622b2927a9081bea4b180e1343ba9b8e2aea326bf44604ca3580d32

CMM_USAGE_INTEGRATION=NOT_PERFORMED
CMMCHAT=DEFERRED_BY_USER
PHASE11_35=NOT_IMPLEMENTED_BY_THIS_REMEDIATION
PUSH=NO
MERGE=NO
```

## 19. Required Remediation V5 scope

Remediation V5 must remain findings-only.

Authorized findings:

```text
MAJOR-V5-01
MAJOR-V5-02
```

Do not reopen the independently verified V4 proposal/manifest/capture fixes except where necessary to preserve them.

### 19.1 V5-01 — stale connection operation authority

Read-only inspection must freeze the smallest canonical preflight for a registered connection whose bound `ProviderSpec` is stale.

At minimum inspect:

```text
ProviderRegistryStateCoordinator.discover_models()
ProviderConnectionRegistry.is_bound_to_current_provider()
ModelRouteCatalog.register()/restore()
```

Recommended starting direction:

```text
resolve registered connection
require exact provider binding current
then resolve canonical manifest
then temporal check
then client call
```

Do not add a new connection registry or cascading teardown.

### 19.2 V5-02 — persistent connection discovery watermark

Read-only inspection must identify a restart-stable source of the latest durable discovery snapshot time.

The current route-only floor is insufficient.

Prefer reuse of existing persisted state, especially sanitized audit history, over a new store or schema field.

Inspect all discovery record types:

```text
route.discovered
route.unavailable
route.restored
route.refreshed
```

and confirm a state-changing discovery always emits enough persisted evidence to derive a connection watermark.

The exact allowlist/deferred three-pass adversary from §11 must be connected to `AT-DP-134`.

### 19.3 Preserve V4 fixes

Must remain green:

```text
stale capture rejection
same-id provider/connection replacement rejection
coherent restore/recapture
forged/stale proposal rejection
canonical isolation minimum
foreign/stale manifest rejection
direct older-than-current-route rejection
```

### 19.4 No new DP

Keep:

```text
DP-134
AT-DP-134
F11-014
```

No new design point or requirement id.

## 20. Next canonical cycle

```text
COMMIT INDEPENDENT RE-AUDIT V5 REPORT
→ REMEDIATION V5 READ-ONLY INSPECTION
→ REMEDIATION V5 DESIGN SPEC
→ COMMIT SPEC
→ REMEDIATION V5 IMPLEMENTATION PLAN
→ COMMIT PLAN
→ AUTONOMOUS IMPLEMENTATION PROMPT
→ TDD IMPLEMENTATION
→ FULL GATES
→ PENDING-REAUDIT DOCUMENTATION
→ CLEAN EXACT-HEAD BUNDLE
→ INDEPENDENT RE-AUDIT V6
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
