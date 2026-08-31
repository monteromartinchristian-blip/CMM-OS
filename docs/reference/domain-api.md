# Domain API — Phase 10.36

**Status:** Phase 10.36 implementation complete — independent audit pending
**DP-036:** `IMPLEMENTED_PENDING_AUDIT`
**AT-DP-036:** `PASS`

## Purpose and non-goals

`cmm.domains.api` exposes one stable public coordination facade through which
callers can inspect and use Domain Intelligence capabilities while the existing
canonical Domain subsystems remain authoritative and all permission,
execution, persistence, conflict and trace boundaries remain intact.

The facade is a coordination boundary only. It is **not**:

- a new Domain Runtime, registry, loader, resolver, or validator;
- a new operation executor or workflow engine;
- a new session store or trace store;
- a new event bus, planner, memory system, or permission engine.

Existing canonical components own runtime truth. The facade owns coordination
and public ergonomics only.

## Public symbols

Exported from `cmm.domains` (and importable as `cmm.domains.api`):

```python
from cmm.domains import DomainAPI, DefaultDomainAPI
```

- `DomainAPI` — runtime-checkable `Protocol` defining the stable callable
  surface.
- `DefaultDomainAPI` — dependency-injected implementation coordinating
  injected canonical collaborators.

Fresh `import cmm.domains` / `import cmm.domains.api` is side-effect free: no
registry mutation, filesystem access, network access, model calls, workflow
execution, session creation, file creation, or runtime startup.

## Constructor collaborators

`DefaultDomainAPI` receives every collaborator explicitly (keyword-only). No
hidden runtime assembly, global singleton lookup, or import-time bootstrap:

```python
DefaultDomainAPI(
    domain_registry=DomainRegistry(...),
    discovery=FileSystemDomainDiscovery(...),
    validator=PipelineDomainValidator(...),
    loader=DeclarativeDomainLoader(...),
    resolver=DefaultDomainResolver(...),
    operation_orchestrator=DefaultDomainOperationOrchestrator(...),
    workflow_registry=InMemoryDomainWorkflowRegistry(...),
    workflow_executor=DomainWorkflowExecutor(...),
    session_adapter=SharedSessionDomainAdapter(...),
    session_resumer=DomainSessionResumer(...),
    conflict_resolver=DomainConflictResolver(),
    trace_assembler=DomainTraceAssembler(),
    trace_validator=DefaultDomainTraceReferenceValidator(),
)
```

Passing `None` for any collaborator raises `TypeError`. The facade retains
references to the injected collaborators and owns no independent mutable
domain state, no caches, and no shadow registries.

## Public methods and canonical owners

| Method | Signature | Canonical owner |
| --- | --- | --- |
| `list_domains` | `(query: DomainQuery \| None = None) -> tuple[DomainDefinition, ...]` | `DomainRegistry.list` |
| `get_domain` | `(domain_id: str, version: str \| None = None) -> DomainDefinition \| None` | `DomainRegistry.get` |
| `discover_domains` | `(sources: tuple[DomainSource, ...]) -> DomainDiscoveryResult` | `FileSystemDomainDiscovery.discover` |
| `validate_domain` | `(request: DomainValidationRequest) -> DomainValidationResult` | `PipelineDomainValidator.validate` |
| `install_domain` | `(candidate: DomainCandidate, *, allow_untrusted: bool = False) -> DomainLoadResult` | `DeclarativeDomainLoader.load` |
| `enable_domain` | `(domain_id: str, version: str \| None = None) -> DomainDefinition` | `DomainRegistry.enable` |
| `disable_domain` | `(domain_id: str, version: str \| None = None) -> DomainDefinition` | `DomainRegistry.disable` |
| `resolve_domain` | `(context: DomainResolutionContext) -> DomainResolutionResult` | `DefaultDomainResolver.resolve` |
| `get_capabilities` | `(domain_id: str, version: str \| None = None) -> tuple[DomainCapability, ...]` | `DomainDefinition.capabilities` via `DomainRegistry.get_required` |
| `get_resources` | `(domain_id: str, version: str \| None = None) -> tuple[str, ...]` | `DomainRegistry.list_resources` |
| `get_rules` | `(domain_id: str, version: str \| None = None) -> tuple[str, ...]` | `DomainRegistry.list_rules` |
| `get_operations` | `(domain_id: str, version: str \| None = None) -> tuple[str, ...]` | `DomainRegistry.list_operations` |
| `get_workflows` | `(domain_id: str, version: str \| None = None) -> tuple[str, ...]` | `DomainRegistry.list_workflows` |
| `execute_operation` | `(request: DomainOperationRequest) -> DomainOperationResult` | `DefaultDomainOperationOrchestrator.execute` |
| `start_workflow` | `(workflow_id: str, context: DomainWorkflowContext, inputs: Mapping[str, Any]) -> DomainWorkflowResult` | `InMemoryDomainWorkflowRegistry.resolve_active` + `DomainWorkflowExecutor.execute_result` |
| `get_session` | `(session_id: str) -> DomainSessionContext \| None` | `SharedSessionDomainAdapter.load_domain_session` |
| `resume_session` | `(request: DomainSessionResumeRequest) -> DomainSessionResumeResult` | `DomainSessionResumer.resume` |
| `resolve_conflict` | `(case, *, policy=None, primary_domain=None, highest_risk_domain=None, evidence_scores=None, reliability_scores=None, temporal_scores=None) -> DomainConflictResolution` | `DomainConflictResolver.resolve` |
| `assemble_trace` | `(request: DomainTraceAssemblyRequest) -> DomainTrace` | `DomainTraceAssembler.assemble` |
| `validate_trace` | `(trace: DomainTrace, inventory: DomainTraceReferenceInventory) -> DomainTraceValidationResult` | `DefaultDomainTraceReferenceValidator.validate` |

## Install semantics

```text
install_domain(candidate) == DeclarativeDomainLoader.load(candidate)
```

Therefore:

```text
INSTALL  = CANONICAL RUNTIME LOAD + REGISTRATION
INSTALL != DURABLE FILESYSTEM INSTALLATION
INSTALL != PACKAGE PUBLICATION
INSTALL != ENABLE
INSTALL != AUTHORIZATION
```

The API does not copy, extract, or publish archives into a persistent
installation directory and does not create a package repository. The canonical
loader remains responsible for transactional registry mutation and rollback.
Untrusted candidates remain fail-closed by default; `allow_untrusted=True` is
the same explicit loader opt-in with the same default (`False`) and semantics.

## Read-only vs mutating methods

Observational/read-only with respect to canonical state:

```text
list_domains, get_domain, discover_domains, validate_domain,
get_capabilities, get_resources, get_rules, get_operations, get_workflows,
get_session, validate_trace
```

Mutating/executing (semantics owned by canonical collaborators):

```text
install_domain, enable_domain, disable_domain,
execute_operation, start_workflow, resume_session
```

`resolve_domain`, `resolve_conflict`, and `assemble_trace` produce derived
canonical results without mutating unrelated runtime state. The facade keeps
no mutation history and no shadow state.

## Operation and workflow authorization boundaries

`execute_operation` delegates to the authoritative
`DefaultDomainOperationOrchestrator`. The orchestrator continues to own
availability, permission evaluation, approval requirements, execution
dispatch, transaction handling, rollback, and result construction. A blocked
permission or missing approval still blocks execution through the API; the
facade cannot bypass permission or approval machinery.

`start_workflow` resolves the active definition through
`InMemoryDomainWorkflowRegistry.resolve_active(workflow_id)` and executes
through `DomainWorkflowExecutor.execute_result(definition, context,
dict(inputs))`. The facade executes no workflow nodes, implements no state
transitions, permission logic, or retries, and never bypasses nested
operation semantics.

## Shared session persistence boundary

`get_session(session_id)` loads through
`SharedSessionDomainAdapter.load_domain_session`; the shared `SessionStore`
remains the single persistence authority. `resume_session(request)` delegates
to `DomainSessionResumer.resume`, which revalidates current registry,
permission, and runtime state fail-closed. Persisted session state is never
treated as current authorization or current truth. There is no Domain-specific
session store and no global session enumeration
(`list_all_domain_sessions` / `search_domain_sessions` do not exist).

## Pure conflict boundary

`resolve_conflict` delegates to the pure, deterministic
`DomainConflictResolver` without mutating the case. All canonical authority
precedence, policies, and score parameters are forwarded unchanged; the API
introduces no conflict policy of its own.

## Reference-only trace boundary

`assemble_trace` delegates to `DomainTraceAssembler.assemble`;
`validate_trace` delegates to `DefaultDomainTraceReferenceValidator.validate`.
`DomainTrace` remains reference-only, immutable, and persistence-independent.
No `TraceStore`, `DomainTraceRepository`, trace cache, trace lookup by ID, or
trace listing exists, and no credentials or private payloads are copied into
trace metadata.

## Error propagation

Canonical subsystem errors propagate with their existing type and semantics —
for example `DomainRegistryError`, `DomainLoaderError` /
`DomainSourceUntrusted`, `DomainResolutionError`,
`DomainOperationContractError`, `DomainOperationValidationError`,
`DomainSessionResumeError`, and `DomainConflictResolutionContractError`. The
facade never catches a canonical error to re-wrap it in a generic
`DomainAPIError`; no such hierarchy exists. Construction wiring errors use
ordinary `TypeError`.

## Example

```python
from cmm.domains import DefaultDomainAPI
from cmm.domains.discovery import FileSystemDomainDiscovery
from cmm.domains.discovery_contracts import DomainSource
from cmm.domains.enums import DomainSourceKind
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.validation import PipelineDomainValidator

registry = DomainRegistry()
api = DefaultDomainAPI(
    domain_registry=registry,
    discovery=FileSystemDomainDiscovery(),
    validator=PipelineDomainValidator(),
    loader=DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    ),
    resolver=DefaultDomainResolver(),
    operation_orchestrator=orchestrator,      # canonical orchestrator
    workflow_registry=workflow_registry,      # canonical registry
    workflow_executor=workflow_executor,      # canonical executor
    session_adapter=session_adapter,          # SharedSessionDomainAdapter
    session_resumer=session_resumer,          # DomainSessionResumer
    conflict_resolver=DomainConflictResolver(),
    trace_assembler=DomainTraceAssembler(),
    trace_validator=DefaultDomainTraceReferenceValidator(),
)

for definition in api.list_domains():
    print(definition.id.slug, definition.enabled)

definition = api.enable_domain("greeter")   # explicit activation
capabilities = api.get_capabilities("greeter")
```

## Inherited invariants preserved

```text
persisted domain snapshot != current authorization != current truth
install != enable
load != authorization
proposal != mutation
preparation != external communication
```

Canonical permission gates and approval requirements remain authoritative;
operation rollback remains owned by canonical operation infrastructure;
workflow execution remains owned by canonical workflow infrastructure; Domain
Sessions remain extensions of the shared session boundary;
`DomainConflictResolver` remains pure; traces remain reference-only; no API
cache overrides registry truth. The general Domain event catalog remains
exactly 23/23 unique and `domain.session.resumed` remains absent.
