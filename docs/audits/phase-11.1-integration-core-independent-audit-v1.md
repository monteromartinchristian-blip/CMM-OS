# Phase 11.1 — Integration Core — Independent Audit V1

**Audit verdict:** `FAIL`
**Audit date:** 2026-09-15
**Auditor:** ChatGPT independent audit
**Scope:** Phase 11.1 — Integration Core on `feature/phase-11-stable-integrated-platform`
**Requirement:** `F11-015 — Canonical Integration Core`
**Design Point:** `DP-101 — Canonical Application Composition Root`
**Connected acceptance:** `AT-DP-101`
**Inherited acceptance:** `AT-DP-134`

## 1. Audited artifact

- Bundle: `cmm-phase11-1-integration-core-audit-9f13da5cee6a.tar.gz`
- Audited HEAD: `9f13da5cee6ad62588437d4f4cc86cac68a47f35`
- Audited tree: `512d5a43eaf9b553fa31f2d05c3fc65163216d0e`
- SHA-256: `ca8f2637883fda61c867676d8f925ccde3612d4fc53d4495dc87e1ae1c7ed94d`
- Archive members: `2431`

Independent integrity checks:

- SHA-256 independently recomputed: `PASS`
- `gzip -t`: `PASS`
- `git get-tar-commit-id`: exact audited HEAD `9f13da5cee6ad62588437d4f4cc86cac68a47f35` — `PASS`
- Git tree independently reconstructed from the archive: `512d5a43eaf9b553fa31f2d05c3fc65163216d0e` — exact match: `PASS`
- unsafe absolute archive paths: `0`
- archive paths containing `..`: `0`
- unsafe extracted symlinks: `0`
- `compileall -q cmm cmm_agent kernel tests`: `PASS`

The TAR.GZ is a valid Git archive bound to the exact implementation commit and tree declared in the handoff.

## 2. Independent verification evidence

### Independently replayed

The auditor environment is Python `3.13.5`.

The Phase 11.1 tests that do not require the unavailable `libcst` dependency were replayed directly from the exact audit bundle:

```text
tests/platform/test_contracts.py
tests/platform/test_compatibility.py
tests/platform/test_service_registry.py
tests/platform/test_configuration.py
tests/platform/test_modules.py
tests/platform/test_inspection.py
tests/platform/test_container.py
```

Result:

```text
206 passed
```

The inherited Provider Registry acceptance was also replayed independently:

```text
pytest -q tests/llm/test_provider_registry_dp134_acceptance.py
67 passed
```

Therefore:

```text
AT-DP-134=PASS
```

### Auditor-environment limitation

Collecting the complete `tests/platform` suite in this sandbox imports the pre-existing execution stack through `cmm.agent_runtime`, which requires `libcst`. `libcst` is not installed in the auditor image and network access is unavailable, so it cannot be installed during the audit.

The resulting collection error is environmental:

```text
ModuleNotFoundError: No module named 'libcst'
```

This is not classified as a repository defect.

The implementation handoff reports `268 passed` for the complete platform suite and `18529 passed` globally. Those results are supporting implementation-machine evidence, but the three MAJOR findings below were independently reproduced without relying on those reports and therefore determine the V1 verdict.

## 3. Positive findings

The audit confirms several important properties of the implementation:

1. `cmm.platform` is a thin new package and does not implement Phase 11.2 orchestration.
2. No `Orchestrator`, `IntentResolver`, `ContextResolver`, `DomainRouter`, `AgentRouter`, `OrchestrationRequest` or `OrchestrationResult` is introduced in the Phase 11.1 production package.
3. No new `ProviderRegistry`, `DomainRegistry`, `AgentRuntime`, `WorkflowEngine`, `Planner`, `KnowledgeStore`, `KnowledgeGraph`, `ValidationEngine`, `EventBus` or `ToolRegistry` owner is defined under `cmm.platform`.
4. No canonical Phase 0–10 package imports `cmm.platform`; the dependency direction remains platform → canonical subsystems.
5. Import-time global registration was not introduced.
6. `IntegrationServiceRegistry` is the only new registry and is scoped to platform composition bindings.
7. The connected acceptance test uses real canonical components / official in-memory implementations rather than a mock-only graph.
8. The acceptance explicitly checks object identity for the Provider Registry, domain registry, Agent Runtime integration, validation, cognition, workflows and execution.
9. The Phase 11.34 Provider Registry remains intact; `AT-DP-134` independently replays as `67 passed`.
10. Dependency resolution, contract compatibility, cycles, duplicate authority, explicit replacement and freeze semantics have substantial focused test coverage.
11. Safe inspection is allowlisted and does not serialize raw implementation objects or arbitrary descriptor metadata.
12. `F11-015`, `DP-101`, `AT-DP-101` and the pre-audit state are mapped in the canonical Phase 11 requirements matrix.
13. The documented requirements-matrix path deviation is legitimate: the repository's canonical file is `docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md`.
14. The detailed Phase 11 roadmap correctly states `IMPLEMENTED_PENDING_INDEPENDENT_AUDIT` and does not claim closure.

These controls must be preserved during remediation.

# 4. Findings

## MAJOR-01 — Canonical binding builders do not enforce the canonical runtime implementation boundary

### Evidence

`cmm/platform/service_registry.py` contains runtime-contract enforcement through `ServiceBinding.runtime_contract`.

However, every canonical builder in `cmm/platform/canonical.py` accepts `Any`, and `_binding()` creates:

```python
ServiceBinding(
    descriptor=...,
    implementation=implementation,
)
```

without setting a `runtime_contract`.

The Provider Registry builder therefore accepts any Python object while assigning it the authoritative platform identity:

```text
service_id = provider.registry
owner      = kernel.llm
authority  = provider-registry
```

Independent reproduction against the exact audit bundle:

```text
RUNTIME_CONTRACT=None
IMPL_ID=builtins.object
READY_WITH_FAKE_PROVIDER=ready
IDENTITY_IS_FAKE=True
```

The reproducer used:

```python
fake = object()
binding = provider_registry_binding(fake)
module = StaticCompositionModule("core", (binding,))
config = CompositionConfiguration(
    required_services=("provider.registry",),
    enabled_modules=("core",),
)
container = ApplicationContainer.build(config, (module,))
```

The container reached `READY`.

### Contract violated

The approved design requires registration to fail closed when:

> an implementation object does not satisfy the required runtime/protocol boundary where this can be verified safely.

For canonical concrete classes such as the Phase 11.34 `ProviderRegistry`, the boundary is safely checkable.

`DP-101` also depends on preserving canonical subsystem authority rather than merely attaching canonical-looking metadata to an arbitrary object.

### Impact

An accidental or incorrect object can masquerade as a canonical subsystem and pass the application readiness gate.

For the most sensitive example, an arbitrary object can claim the singleton `provider-registry` authority and become the ready `provider.registry` service.

This means the Integration Core currently validates descriptor metadata but does not always validate the implementation that metadata describes.

### Required remediation

- Bind each canonical service with an enforceable runtime boundary where a concrete class or runtime-checkable protocol exists.
- At minimum, `provider_registry_binding()` must reject anything that is not the canonical `ProviderRegistry` implementation boundary.
- Apply the same rule to validation, cognition, domain registry, workflow registry, execution registry and Agent Runtime integration where safely checkable.
- Keep adapters possible by defining an explicit compatible protocol/interface where replacement by a different concrete class is intended; do not simply disable runtime checking.
- Add RED/GREEN tests proving each canonical builder rejects an unrelated object.
- Add an `AT-DP-101` fail-closed variant proving a fake canonical authority cannot reach `READY`.

---

## MAJOR-02 — `ServiceDescriptor.metadata` can contain secrets and mutable nested runtime state

### Evidence

The approved design states:

> Descriptors must not contain secrets, provider credentials, mutable runtime state or copied sensitive domain content.

The committed implementation uses:

```python
object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
```

This creates only a shallow read-only mapping. It does not validate the metadata shape, reject sensitive keys/values, or recursively freeze nested values.

Independent reproduction against the exact audit bundle:

```text
DESCRIPTOR_ACCEPTED_SECRET_METADATA={
  'token': 'sk-secret',
  'nested': {'password': 'p'}
}
TOP_LEVEL_MUTATION_BLOCKED=TypeError
NESTED_MUTATION_SUCCEEDED={'password': 'changed'}
```

Therefore the public descriptor can carry:

- secret-shaped values;
- password/token fields;
- arbitrary nested dictionaries/lists/objects;
- mutable runtime state reachable through an otherwise frozen dataclass.

### Contract violated

The approved plan requires:

> All new public platform values are immutable and serialization-safe.

The design separately prohibits secrets and mutable runtime state inside descriptors.

The current snapshot serializer correctly refuses to expose descriptor metadata, but hiding the metadata at inspection time does not make the descriptor itself secret-free or immutable.

### Impact

The platform boundary can retain sensitive or mutable state that the design explicitly forbids.

Nested mutation can also change descriptor-associated information after registration without changing the frozen dataclass identity, undermining deterministic boundary semantics.

### Required remediation

Choose one narrow, explicit strategy consistent with YAGNI:

1. Prefer removing arbitrary descriptor metadata if Phase 11.1 does not actually need it; or
2. restrict metadata to a small recursively immutable, secret-free descriptive value grammar.

If metadata remains:

- reject secret/credential/token/password/prompt/reasoning/provider-payload shaped keys and values;
- reject arbitrary runtime objects;
- recursively freeze permitted mappings/sequences, or normalize them to immutable tuples/scalars;
- add tests for nested mapping/list mutation;
- add tests for secret-shaped keys/values;
- keep inspection allowlisted exactly as it is.

Do not add a generic secrets-management subsystem in this remediation.

---

## MAJOR-03 — Invalid `ServiceMode` values can reach `READY` and produce a non-serializable inspection snapshot

### Evidence

`ServiceDescriptor.mode` is annotated as `ServiceMode`, but `ServiceDescriptor.__post_init__()` never validates it.

`ServiceInspection.__post_init__()` also does not validate `mode`.

`ApplicationContainer.build()` therefore accepts a descriptor created with an arbitrary string and marks the application ready.

Independent reproduction:

```text
CONTAINER_STATE=ready
SNAPSHOT_MODE_RAW=bogus
SNAPSHOT_SERIALIZATION_ERROR=ValueError 'bogus' is not a valid ServiceMode
```

The reproducer used:

```python
descriptor = ServiceDescriptor(
    service_id="svc",
    contract=ContractMetadata("svc", "1.0.0", "1", "owner"),
    implementation_id="impl",
    mode="bogus",
)
registry.register(ServiceBinding(descriptor, object()))
container = ApplicationContainer.build(
    CompositionConfiguration(required_services=("svc",)),
    registry=registry,
)
```

The container reached `READY`, but:

```python
container.snapshot().to_dict()
```

then failed.

### Contract violated

The approved plan requires:

> invalid configuration fail closed.

and:

> All new public platform values are immutable and serialization-safe.

The approved design says a container is `ready` only after all required composition validation has succeeded, and its ready inspection snapshot must be deterministic and safe.

### Impact

`READY` currently does not guarantee that the public inspection snapshot is valid/serializable.

This violates a central readiness guarantee of `DP-101`.

### Required remediation

- Validate `ServiceDescriptor.mode` at construction as a real `ServiceMode` value.
- Prefer rejecting malformed values rather than silently coercing arbitrary input.
- Defensively validate `ServiceInspection.mode` as well, because it is a public boundary value.
- Add RED/GREEN contract tests for invalid mode.
- Add an `ApplicationContainer` / `AT-DP-101` variant proving malformed mode cannot reach `READY`.
- Verify that every ready snapshot can always execute `to_dict()` successfully.

---

# 5. Severity summary

```text
BLOCKERS=0
MAJORS=3
MINORS=0
```

The findings are localized and remediable inside the Phase 11.1 boundary. No architecture rewrite is required.

No finding requires:

- reopening Phase 11.34;
- creating another registry/runtime/store;
- implementing Phase 11.2;
- changing CMMChat;
- changing the global platform architecture.

## 6. Requirement / Design Point verdict

### F11-015

The implementation substantially exists, but the readiness and canonical-authority guarantees are not yet strong enough for independent verification because of MAJOR-01 through MAJOR-03.

```text
F11-015=IMPLEMENTED_REMEDIATION_REQUIRED
```

### DP-101

The intended canonical composition root is present and correctly scoped, but an arbitrary object can currently masquerade as a canonical subsystem and invalid public values can reach `READY`.

```text
DP-101=NOT_VERIFIED
```

### AT-DP-101

The connected acceptance test exists and is structurally strong. The implementation machine reports it passing as part of `tests/platform`.

The auditor could not replay the complete file solely because the sandbox lacks the pre-existing `libcst` dependency. More importantly, the current acceptance does not cover the three independently reproduced failure cases above.

```text
AT-DP-101=PASS_REPORTED_REMEDIATION_COVERAGE_REQUIRED
```

### AT-DP-134

Independently replayed:

```text
67 passed
AT-DP-134=PASS
```

## 7. Documentation verdict

Documentation status and traceability are generally correct:

- `F11-015` is mapped in the canonical Phase 11 requirements matrix.
- `DP-101` and `AT-DP-101` are mapped.
- 11.34 is reused rather than reopened.
- the detailed roadmap says `IMPLEMENTED_PENDING_INDEPENDENT_AUDIT`;
- `ROADMAP.md` remaining unchanged pre-audit is consistent with the documented repository convention;
- the alternate requirements-matrix path is correctly documented.

No documentation-only blocker was found in V1.

The remediation must update the implementation/reference evidence as needed but must continue to avoid closure wording before a PASS re-audit.

# 8. Independent re-audit requirements

A remediation bundle must be generated from a new exact committed HEAD.

The re-audit must verify at minimum:

1. all MAJOR-01 runtime-boundary tests pass;
2. a fake Provider Registry cannot bind/reach readiness;
3. compatible approved adapters still work through explicit replacement;
4. descriptor metadata cannot carry secret-shaped or mutable nested state;
5. invalid `ServiceMode` values fail before readiness;
6. every ready inspection snapshot is serializable;
7. `tests/platform` passes;
8. `AT-DP-101` passes with the new fail-closed variants;
9. `AT-DP-134` remains green;
10. relevant subsystem and global regressions remain green;
11. scoped Ruff/format policy remains clean;
12. `compileall` and `git diff --check` pass;
13. worktree is clean;
14. quarantine stash is preserved;
15. the new bundle's HEAD/tree/SHA-256 are exact and independently reproducible.

# 9. Final V1 verdict

```text
INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=0
MAJORS=3
MINORS=0

MAJOR_01=CANONICAL_RUNTIME_BOUNDARY_NOT_ENFORCED
MAJOR_02=DESCRIPTOR_METADATA_SECRET_AND_MUTABILITY_GAP
MAJOR_03=INVALID_SERVICE_MODE_CAN_REACH_READY

F11_015=IMPLEMENTED_REMEDIATION_REQUIRED
DP_101=NOT_VERIFIED
AT_DP_101=PASS_REPORTED_REMEDIATION_COVERAGE_REQUIRED
AT_DP_134=PASS

CLOSURE_ELIGIBLE=NO
NEXT=PHASE11_1_REMEDIATION_V1
```

Phase 11.1 must not receive a docs-only closure commit yet.
