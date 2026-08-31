# Phase 10.36 — Domain API — Independent Audit V1

## Verdict

**Result:** FAIL — remediation required
**BLOCKERS:** 0
**MAJORS:** 1
**MINORS:** 0
**DP-036:** NOT VERIFIED
**AT-DP-036:** PRESENT, NOT INDEPENDENTLY RE-EXECUTED IN AUDIT SANDBOX
**CLOSURE_ELIGIBLE:** NO

## Audited artifact

- Bundle: `phase-10.36-domain-api-audit-v1.tar.gz`
- SHA-256: `4317d59830fbe63691e25acda8eae159494b7b62747bffea07f7615c6fa949ac`
- Exact embedded `git archive` commit: `f85f0e8b57ba695bc8ba9daa74701401c775cad9`
- Archive integrity: PASS
- Archive path safety: PASS
- Special TAR entries: 0
- Python `compileall` over `cmm/domains` and `tests/domains`: PASS
- No parallel Domain API registry/loader/resolver/workflow engine/session store/trace store found in `cmm/domains/api.py`
- Canonical general event catalog remains 23 entries and `domain.session.resumed` is absent from the canonical catalog.

## Architecture assessment

The implementation is structurally faithful to the approved Phase 10.36 architecture.

Verified from the audited artifact:

- `DomainAPI` and `DefaultDomainAPI` exist in `cmm/domains/api.py`.
- The approved surface contains 20 explicitly enumerated methods and both protocol and implementation expose those 20 methods.
- `list_domains`, `get_domain`, resources/rules/operations/workflows delegate to `DomainRegistry`.
- discovery delegates to canonical discovery;
- validation delegates to `PipelineDomainValidator`;
- `install_domain` delegates to `DeclarativeDomainLoader.load`;
- install and enable remain separate;
- resolution delegates to the canonical resolver;
- operation execution delegates to `DefaultDomainOperationOrchestrator`;
- workflow execution resolves through `InMemoryDomainWorkflowRegistry.resolve_active` and executes through `DomainWorkflowExecutor.execute_result`;
- session lookup uses `SharedSessionDomainAdapter`;
- session resume uses `DomainSessionResumer`;
- conflict resolution delegates to pure `DomainConflictResolver`;
- trace assembly/validation use canonical reference-only trace components;
- no trace store or Domain-specific session store was introduced;
- no generic `DomainAPIError` hierarchy exists;
- documentation correctly remains at implementation-complete / independent-audit-pending status.

The shared `DomainMetadata.from_dict` fix is scope-justified: the new connected session path exposed a real canonical deserialization defect, and the change restores the existing empty-mapping default rather than adding API-local workaround logic.

## MAJOR-01 — Public typed dependency contract diverges from approved canonical protocols

### Severity

**MAJOR**

Phase 10.36 exists specifically to establish a stable public Domain API contract. The runtime behavior is correct, but the published type boundary is narrower and less canonical than the approved spec/plan.

### Evidence

Approved implementation plan requires explicit collaborators typed against the existing canonical protocols:

- `discovery: DomainDiscovery`
- `resolver: DomainResolver`
- `trace_validator: DomainTraceReferenceValidator`

The audited implementation instead declares concrete implementations in `cmm/domains/api.py`:

- `discovery: FileSystemDomainDiscovery`
- `resolver: DefaultDomainResolver`
- `trace_validator: DefaultDomainTraceReferenceValidator`

This unnecessarily couples the stable public facade to current implementations even though the repository already contains the canonical protocols:

- `cmm.domains.discovery.DomainDiscovery`
- `cmm.domains.resolver.DomainResolver`
- `cmm.domains.trace_validation.DomainTraceReferenceValidator`

The same public typing drift appears in capability queries:

```python
def get_capabilities(...) -> tuple[Any, ...]
```

while the canonical contract is:

```python
DomainDefinition.capabilities: tuple[DomainCapability, ...]
```

and `docs/reference/domain-api.md` already advertises:

```text
-> tuple[DomainCapability, ...]
```

Therefore production code and public documentation disagree on the return contract.

### Why this matters

Python duck typing means alternate implementations may happen to work at runtime, but Phase 10.36 is explicitly a **stable public typed facade**. Consumers, IDEs, static analysis, future application composition and replacement implementations should depend on the canonical interfaces rather than concrete defaults.

This is a public-contract defect, not a request to redesign the facade.

### Required remediation

Change only the public typing/wiring contract:

1. In `cmm/domains/api.py`, import and use:
   - `DomainDiscovery`
   - `DomainResolver`
   - `DomainTraceReferenceValidator`
   - `DomainCapability`
2. Change `DefaultDomainAPI.__init__` annotations:
   - `discovery: DomainDiscovery`
   - `resolver: DomainResolver`
   - `trace_validator: DomainTraceReferenceValidator`
3. Change both `DomainAPI.get_capabilities` and `DefaultDomainAPI.get_capabilities` to:
   - `-> tuple[DomainCapability, ...]`
4. Keep the actual default production examples free to instantiate:
   - `FileSystemDomainDiscovery`
   - `DefaultDomainResolver`
   - `DefaultDomainTraceReferenceValidator`
5. Update `docs/reference/domain-api.md` and the Phase 10.36 roadmap wording so canonical ownership is described at the protocol boundary where appropriate, while examples may still show concrete default implementations.
6. Add focused contract tests proving:
   - the public annotations expose the canonical protocol types;
   - alternative objects satisfying `DomainDiscovery`, `DomainResolver`, and `DomainTraceReferenceValidator` can be injected without changing `DefaultDomainAPI`;
   - `get_capabilities` is typed as `tuple[DomainCapability, ...]`.
7. Do not add a new API-specific protocol, registry, wrapper, container, runtime or error hierarchy.

## Acceptance review

`tests/domains/test_domain_api_dp036_acceptance.py` is a genuine connected acceptance rather than a mock-only facade test. It connects discovery, validation, loader/registry, explicit activation, canonical resolution, operation orchestration, workflow execution, shared session persistence/resumption, conflict resolution and trace assembly/validation.

The adversarial/focused tests also cover the main required boundaries, including:

- install != enable;
- untrusted load fail-closed;
- discovery/validation non-registration;
- operation permission blocking;
- workflow fail-closed behavior;
- missing session non-creation;
- stale persisted session state not conferring current authority;
- conflict input immutability;
- no trace persistence;
- no invented session/trace/public lifecycle APIs.

However, the independent audit sandbox could not execute the pytest suite because the sandbox lacks the project dependency `libcst`. Ruff is also not installed in the audit sandbox. This is an auditor-environment limitation, not classified as a repository defect.

For V2, provide fresh local gate evidence after remediation together with the new exact-HEAD bundle.

## Audit notes

The implementation plan contains an editorial reference to “21 approved methods”, while the actual enumerated approved surface in the spec and plan contains **20 methods**. The audited implementation exposes all 20 enumerated methods. This is treated as a planning-document counting typo, not an implementation finding.

## V1 closure status

```text
BLOCKERS=0
MAJORS=1
MINORS=0
DP-036=NOT_VERIFIED
AT-DP-036=NOT_INDEPENDENTLY_REEXECUTED
CLOSURE_ELIGIBLE=NO
```

Required next step:

```text
REMEDIATE MAJOR-01 ONLY
→ RUN FOCUSED + RELEVANT REGRESSIONS + DOMAIN + GLOBAL GATES
→ COMMIT REMEDIATION
→ WORKTREE CLEAN
→ CREATE phase-10.36-domain-api-audit-v2.tar.gz FROM EXACT HEAD
→ RECORD SHA-256
→ INDEPENDENT REAUDIT V2
```
