# Phase 11.34 — Provider Registry — Independent Audit V1

**Audit verdict:** `FAIL`
**Audit date:** 2026-09-14
**Auditor:** ChatGPT independent audit
**Scope:** Phase 11.34 Provider Registry implementation integrated into `feature/phase-11-stable-integrated-platform`
**CMM Usage integration:** explicitly deferred; not part of this audit closure scope
**CMMChat integration:** explicitly deferred; not part of this audit closure scope

## 1. Audited artifact

- Bundle: `cmm-os-phase11-provider-registry-audit-574d59e-20260914-182640.tar.gz`
- Manifest: `cmm-os-phase11-provider-registry-audit-574d59e-20260914-182640.manifest.txt`
- Audited HEAD: `574d59e7a69919dd7545a9a3a9ed1f64d4f89f1b`
- Audited tree claimed by manifest: `3d8c2c1a5499d1a62d5c2cc9696ec42e8ad80eda`
- SHA-256: `6d5a1792faa4bee487b6549c9e65cdd68ce51a23ff1cc9fd5fa74e9473916357`
- Base HEAD: `b580c02b48e0e5db9d081cb9ba2d9b7cf0c7d2cd`
- Merge HEAD: `3a77d43a856faf30711800bf6383c74e5c5712ef`
- Provider Registry program HEAD: `25f349f0935bc1a35b325803973cfd58ed6098a3`

Independent integrity checks:

- SHA-256 independently recomputed: `PASS`
- `gzip -t`: `PASS`
- `git get-tar-commit-id`: `574d59e7a69919dd7545a9a3a9ed1f64d4f89f1b` — exact audited HEAD binding: `PASS`
- archive roots: one
- regular archived files: `2263`
- archive members: `2379`
- unsafe absolute / `..` paths: `0`
- `.git` directory absent from archive
- independent `compileall -q cmm cmm_agent kernel tests`: `PASS`

The bundle itself is valid and correctly bound to the audited commit.

## 2. Verification evidence

Implementation-machine evidence supplied with the audit handoff reports:

- `tests/llm`: `345 passed`
- global suite: `17875 passed`
- changed-file Ruff: `PASS`
- changed-file Ruff format: `PASS`
- baseline-aware global Ruff/format: `PASS`
- global Ruff debt: `839 -> 837`
- global format debt: `359 -> 358`
- `compileall`: `PASS`
- `git diff --check`: `PASS`
- worktree clean
- quarantine stash preserved
- CMM Usage integration not performed
- CMM Usage bridge preserved at `5a1bffac2599cfd6a3090fd191399d6b5148f544`
- CMMChat deferred

Independent auditor environment:

- Python `3.13.5`
- pytest `9.0.2`
- Ruff unavailable in the audit environment

Independent test replay:

- `tests/llm`: `344 passed, 1 failed`
- focused Provider Registry/security subset excluding the Python-version-sensitive immutability assertion: `255 passed, 1 deselected`
- public Provider Registry export smoke: `PASS`
- static no-inference scan over `model_discovery.py`, `provider_detectors.py`, `provider_onboarding.py`, and `first_wave_providers.py`: no generation/inference entry point found

The single independent LLM-suite failure is recorded below as `MINOR-01`; none of the MAJOR findings relies on it.

## 3. Positive findings

The implementation contains several strong controls that are preserved by this audit:

1. Detection is separated from connection authority through `ProviderCandidate`.
2. Provider model discovery is administrative and does not call inference.
3. Missing discovered routes are retained and marked unavailable rather than deleted.
4. Qwen Token Plan and Qwen Cloud PAYG are modeled as separate provider/account surfaces.
5. Provider model IDs remain provider-specific and are not silently collapsed.
6. Credential references use an opaque Keychain-oriented namespace rather than inline secrets.
7. `MacOSKeychainCredentialStore.put()` sends the secret through stdin rather than argv.
8. Candidate metadata rejects multiple secret-shaped markers.
9. Provider inventory snapshots omit credential refs, profile paths, endpoints, and raw external metadata.
10. CMM Usage and CMMChat were not silently integrated during this Provider Registry audit cycle.

These positive controls do not offset the closure-blocking findings below.

# 4. Findings

## MAJOR-01 — Provider identity is fragmented across parallel provider registries

### Evidence

The pre-existing canonical provider registry remains:

- `kernel/llm/provider_registry.py:78-130`
- `ProviderRegistry`
- internal provider inventory: `self._providers`

The new implementation adds a second independent provider-ID catalog:

- `kernel/llm/provider_manifests.py:187-214`
- `ProviderManifestRegistry`
- internal provider inventory: `self._items`

`ProviderOnboardingService` consumes `ProviderManifestRegistry` directly and does not bind provider identity to the canonical `ProviderRegistry`.

Independent reproduction from the exact audit bundle:

```text
PROVIDER_REGISTRY_COUNT=0
MANIFEST_REGISTRY_COUNT=8
MANIFEST_IDS=commandcode,deepseek,kira,nvidia-nim,opencode-zen,openrouter,qwen-cloud,qwen-token-plan
CAN_DIVERGE=True
```

The implementation plan itself states:

> Evolve CMM OS's existing `ProviderRegistry` + `ModelCatalog` into a route-aware provider inventory.

and:

> Reuse the current CMM OS LLM kernel (`ProviderRegistry`, `ModelCatalog`, `ProviderFactory`, `OpenAICompatibleProvider`) and add focused domain types around them rather than replacing them.

### Impact

Provider definitions/manifests can diverge from the registry that was already canonical. This violates the permanent anti-fragmentation invariant and the program's own architecture goal. A consumer can observe one provider inventory through `ProviderRegistry` and a different provider inventory through `ProviderManifestRegistry`.

### Required remediation

Perform a fresh repository inspection of canonical storage/registry infrastructure, then redesign the manifest relationship so there is one authoritative provider identity/inventory. A manifest may remain a declarative transport/configuration facet, but it must not be an independently divergent provider catalog.

Do not fix this by adding synchronization between two authoritative registries.

---

## MAJOR-02 — Phase 11.34 durable, versioned, auditable local-first persistence is not implemented

### Evidence

The approved design states in §16:

> Registry persistence must be local-first.

and requires persistence of:

- ProviderDefinitions/manifests
- accepted ProviderConnections
- credential references
- model routes
- capability metadata
- discovery timestamps
- connection validation state

The Phase 11.34 roadmap objective is:

> Maintain a dynamic, versioned, and auditable registry of providers and models.

The current core stores are explicitly in-memory:

- `kernel/llm/provider_manifests.py:187-191` — `ProviderManifestRegistry`: `"In-memory catalog"`
- `kernel/llm/provider_connections.py:107-111` — `ProviderConnectionRegistry`: `"In-memory catalog"`
- `kernel/llm/model_routes.py:103-107` — `ModelRouteCatalog`: `"In-memory route catalog"`

No canonical persistence/repository adapter, persisted registry schema version, migration path, or durable audit-history owner for these records is present in the audited Provider Registry implementation.

### Impact

Accepted connections and discovered route history disappear on process restart. The claimed durable identity is only in-process durability. The implementation therefore cannot yet satisfy Phase 11.34's stable, versioned, auditable registry contract.

### Required remediation

Before creating any new store, inspect and reuse existing canonical Phase 11 persistence/storage infrastructure where appropriate. Add the minimum canonical persistence boundary required by the approved design, preserving secret isolation:

- persist references, never raw secrets;
- persist accepted connections/routes/capability state/discovery timestamps;
- define schema/version semantics;
- provide deterministic load/round-trip behavior;
- preserve route identity/history across restart;
- add connected persistence acceptance coverage.

---

## MAJOR-03 — Claude and Antigravity isolation can fail open into `CONNECTED`

### Evidence

Detectors correctly report provider-specific home metadata:

- `ClaudeCodeDetector`: `("claude_home", ...)` at `kernel/llm/provider_detectors.py:250-270`
- `AntigravityDetector`: `("antigravity_home", ...)` at `kernel/llm/provider_detectors.py:302-322`

But `ProviderOnboardingService.propose()` only recognizes:

- `kernel/llm/provider_onboarding.py:138-141`
- metadata key `codex_home`

`accept()` permits validator success to set `CONNECTED` regardless of whether an isolation profile was actually created:

- `kernel/llm/provider_onboarding.py:166-177`

Independent reproduction from the exact bundle:

```text
claude-code proposal.source_home=None requires_isolation=True status=connected isolation_profile_ref=None
claude-code CONNECTED_WITHOUT_ISOLATION=True

antigravity proposal.source_home=None requires_isolation=True status=connected isolation_profile_ref=None
antigravity CONNECTED_WITHOUT_ISOLATION=True
```

### Impact

A provider explicitly marked as requiring isolation can become routable/connected with no CMM-owned isolation profile. This violates the approved rule that external configuration is evidence, not authority, and the Plan 3 constraint that Claude/Antigravity subscription traffic remain isolated.

### Required remediation

Make isolation requirements provider-aware and fail closed:

- preserve the correct provider-specific source/profile evidence;
- require an isolation outcome before a `requires_isolation=True` proposal may become `CONNECTED`;
- ensure validation success cannot override a missing/failed isolation prerequisite;
- add connected regression tests for Codex, Claude, and Antigravity.

---

## MAJOR-04 — Failed duplicate onboarding can overwrite an existing credential

### Evidence

`ProviderOnboardingService.accept()` writes the credential before registering the connection:

- `kernel/llm/provider_onboarding.py:161-165` — `CredentialStore.put(...)`
- `kernel/llm/provider_onboarding.py:188` — `ProviderConnectionRegistry.register(...)`

`ProviderConnectionRegistry.register()` rejects a duplicate connection ID only after the credential write has happened.

Independent reproduction from the exact bundle:

```text
FIRST_SECRET=secret-one
SECOND_ACCEPT_EXCEPTION=ValueError duplicate connection_id: deepseek:main
CONNECTION_COUNT=1
SECRET_AFTER_FAILED_ACCEPT=secret-two
OVERWRITE_OCCURRED=True
```

### Impact

An onboarding operation that reports failure can still mutate the credential used by the already-existing connection. With the macOS backend, `security add-generic-password ... -U` is an upsert, so the same ordering can silently rotate/replace the existing Keychain secret before the duplicate error is raised.

This is a fail-closed and transactional-integrity violation.

### Required remediation

Make acceptance atomic from the caller's perspective:

- preflight connection identity before secret mutation;
- define safe credential-update semantics separately from new-connection creation;
- if any downstream step can fail after a new secret/profile side effect, roll it back or use an existing canonical transaction/checkpoint facility;
- add a regression proving a failed duplicate acceptance leaves the original credential unchanged.

---

## MAJOR-05 — Mandatory Design Point / connected Acceptance Test and lifecycle status are absent

### Evidence

No Provider Registry `DP-0XX` / `AT-DP-0XX` pair is defined in:

- the Provider Registry design spec;
- the four Provider Registry implementation plans;
- the Phase 11.34 roadmap section;
- the Provider Registry test suite.

The plan has textual acceptance gates, but they are not the canonical connected Design Point acceptance required by the project workflow.

The repository's top-level roadmap is also stale for the current implementation state:

- `ROADMAP.md:572-574` — Phase 11 remains `Status: Planned`
- older status text still states `PHASE11=NOT_STARTED`
- Phase 11.34 has no `implemented and pending independent audit` status block

### Impact

The mandatory closure contract cannot be evaluated. There is no auditable mapping from Phase 11.34 requirements to one canonical Design Point and connected Acceptance Test using canonical/official components.

### Required remediation

Define a unique, non-colliding Phase 11.34 Design Point and connected acceptance test. Do not reuse a historical DP identifier.

The acceptance must exercise real canonical/official components and prove, at minimum:

- one authoritative provider inventory;
- provider connection identity and route identity;
- Qwen subscription/PAYG separation;
- detect != connect;
- isolation fail-closed;
- no-secret persistence;
- durable persistence/round-trip and route-history preservation;
- discovery without inference;
- provider-specific capability filtering;
- failed onboarding produces no unauthorized side effects.

Update the Phase 11 roadmap / requirements mapping to `implemented and pending independent re-audit` only. Do not mark the DP verified or the AT PASS until the next independent audit.

---

## MINOR-01 — Supported-Python immutability test is version-sensitive

### Evidence

`pyproject.toml:15` declares:

```text
requires-python = ">=3.10"
```

The independent auditor uses Python `3.13.5`.

Full `tests/llm` replay on the exact bundle:

```text
344 passed, 1 failed
```

Failure:

- `tests/llm/test_provider_events.py:235-243`
- the loop assigns `provider_id` to every snapshot, including `ProviderInventorySnapshot`, which has no `provider_id` field;
- on Python 3.13.5 this produces `TypeError`, not the asserted `FrozenInstanceError`.

The object remains immutable. Independent probing shows assignments to real fields produce `FrozenInstanceError` for all three snapshot types:

```text
ProviderConnectionSnapshot.provider_id -> FrozenInstanceError
ModelRouteSnapshot.provider_id -> FrozenInstanceError
ProviderInventorySnapshot.generated_at -> FrozenInstanceError
```

### Impact

The production immutability property is preserved, but the declared supported Python range contains an interpreter on which the LLM suite is red.

### Required remediation

Make the test mutate a real field belonging to each frozen snapshot type, or otherwise assert immutability without depending on assignment to a nonexistent slotted field. Re-run the supported Python matrix. Do not narrow `requires-python` merely to avoid the test unless that is a separately approved compatibility decision.

# 5. Deferred integrations

The following are explicitly preserved as out of this remediation scope unless a finding directly requires them:

- CMM Usage active branch remains outside this bundle.
- CMM Usage Registry bridge remains preserved/deferred at `5a1bffac2599cfd6a3090fd191399d6b5148f544`.
- CMM Usage integration must not be performed while CMM Usage is unfinished.
- CMMChat provider projection remains deferred by user.
- No push or merge is authorized.

The Provider Registry remediation must not use CMM Usage or CMMChat integration as a shortcut for fixing the canonical CMM OS architecture.

# 6. Audit verdict

```text
INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=0
MAJORS=5
MINORS=1
DP_STATUS=NOT_DEFINED
AT_STATUS=NOT_DEFINED
DP-0XX=NOT_VERIFIED
AT-DP-0XX=NOT_PASS
CLOSURE_ELIGIBLE=NO
AUDITED_HEAD=574d59e7a69919dd7545a9a3a9ed1f64d4f89f1b
AUDITED_BUNDLE_SHA256=6d5a1792faa4bee487b6549c9e65cdd68ce51a23ff1cc9fd5fa74e9473916357
CMM_USAGE_INTEGRATION=NOT_PERFORMED
CMM_USAGE_BRIDGE_STATE=PRESERVED_DEFERRED
CMMCHAT=DEFERRED_BY_USER
PUSH=NO
```

Phase 11.34 is **not closure-eligible**.

# 7. Required next cycle

1. Commit this V1 audit report as a dedicated docs-only historical artifact.
2. Perform a fresh read-only remediation inspection from the post-audit-report HEAD.
3. Produce a Remediation V1 architectural design and implementation plan covering only the findings above.
4. Commit design and plan separately.
5. Prepare the remediation implementation-agent prompt.
6. Execute TDD:
   `RED -> minimal implementation -> GREEN -> controlled refactor`.
7. Re-run focused Provider Registry tests, inherited LLM regressions, global suite, changed-file Ruff/format, baseline-aware global quality gate, compileall, diff-check, DP/AT and persistence/security gates.
8. Commit all remediation implementation and documentation; leave worktree clean.
9. Generate a **new** exact-HEAD TAR.GZ via `git archive`; do not mutate this V1 bundle.
10. Submit the new bundle for independent Re-audit V2.
