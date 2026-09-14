# Phase 10.36 — Domain API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose one stable, typed, side-effect-bounded Python `DomainAPI` facade that coordinates the existing canonical Domain Intelligence components without creating a second runtime, registry, loader, resolver, executor, store, or policy system.

**Architecture:** Add `cmm.domains.api` containing a runtime-checkable `DomainAPI` protocol and a dependency-injected `DefaultDomainAPI`. Every public method delegates to an existing canonical owner: registry, discovery, validator, loader, resolver, operation orchestrator, workflow registry/executor, shared session adapter/resumer, pure conflict resolver, trace assembler, or trace validator. The facade owns no shadow runtime state and returns existing canonical contracts.

**Tech Stack:** Python 3.10+ typing/dataclasses/protocols, existing CMM OS Domain Intelligence contracts, pytest, Ruff, compileall.

**Spec:** `docs/superpowers/specs/2026-08-31-domain-api-design.md`

**Starting branch:** `feature/phase-10-domain-intelligence`

**Starting HEAD:** `7b31ec36aec5140c08dd853e9f97c81190deb117`

## Global Constraints

- `DomainAPI` is a thin coordination facade, not a new Domain Runtime.
- Do not create parallel registries, loaders, resolvers, validators, operation executors, workflow engines, session stores, trace stores, event buses, planners, permission systems, or memory systems.
- `install_domain(candidate)` means canonical runtime `DeclarativeDomainLoader.load(candidate)` only.
- `INSTALL != DURABLE FILESYSTEM INSTALLATION`.
- `INSTALL != PACKAGE PUBLICATION`.
- `INSTALL != ENABLE`.
- `INSTALL != AUTHORIZATION`.
- Operation execution MUST go through `DefaultDomainOperationOrchestrator`; never invoke a registered operation implementation directly from the API.
- Workflow execution MUST resolve through `InMemoryDomainWorkflowRegistry.resolve_active(...)` and execute through `DomainWorkflowExecutor`; the API must not execute workflow nodes.
- Session persistence remains owned by the shared `SessionStore` through `SharedSessionDomainAdapter`.
- `persisted domain snapshot != current authorization != current truth`.
- `DomainConflictResolver` remains pure and deterministic.
- `DomainTrace` remains reference-only and persistence-independent.
- No `TraceStore`, `DomainTraceRepository`, hidden trace cache, global session enumeration, or persistent package store is introduced.
- Canonical subsystem exceptions propagate unchanged; do not add a generic catch-all `DomainAPIError`.
- Fresh `import cmm.domains` and `import cmm.domains.api` must be side-effect free.
- General Domain event catalog remains exactly 23 unique general events.
- `domain.session.resumed` remains absent.
- No `push`, `merge`, `git stash`, `stash pop/apply/drop`, `git reset`, `git clean`, or `git worktree`.
- Preserve the quarantine stash exactly:
  `quarantine: post-audit phase 10.32 uncommitted changes`.
- Follow TDD for every behavioral block:
  `RED -> minimal implementation -> GREEN -> controlled refactor -> next block`.
- Keep commits narrowly scoped and leave the worktree clean at every major checkpoint.

---

## Planned File Structure

### Production

- Create `cmm/domains/api.py`
  - `DomainAPI` protocol.
  - `DefaultDomainAPI` implementation.
  - No persistence, caches, registries, loaders, resolvers, stores, or executors implemented here.
- Modify `cmm/domains/__init__.py`
  - Publicly export only the approved API symbols.

### Tests

- Create `tests/domains/test_domain_api_contracts.py`
  - protocol shape, construction, public exports, import side effects, canonical exception propagation.
- Create `tests/domains/test_domain_api_queries.py`
  - list/get/capabilities/resources/rules/operations/workflows; read-only mutation invariants.
- Create `tests/domains/test_domain_api_lifecycle.py`
  - discover/validate/install/enable/disable and `install != enable`.
- Create `tests/domains/test_domain_api_execution.py`
  - resolver delegation, authoritative operation orchestration, workflow registry/executor path.
- Create `tests/domains/test_domain_api_sessions.py`
  - shared-session lookup and fail-closed resumption.
- Create `tests/domains/test_domain_api_conflicts_traces.py`
  - pure conflict delegation, trace assembly and reference validation, no hidden persistence.
- Create `tests/domains/test_domain_api_dp036_acceptance.py`
  - connected `AT-DP-036` using canonical real/in-memory components.

### Documentation

- Create `docs/reference/domain-api.md`
- Modify `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify `docs/roadmap/phase-10-domain-intelligence.md`
- Modify `ROADMAP.md`

No other production file should change unless a RED test proves an existing canonical contract is missing or broken. If such a defect appears, stop that task, document the exact RED evidence, and make the smallest shared fix rather than solving it inside `DomainAPI`.

---

### Task 1: Establish the public facade contract and dependency wiring

**Files:**
- Create: `cmm/domains/api.py`
- Create: `tests/domains/test_domain_api_contracts.py`

**Interfaces:**

Produce a runtime-checkable protocol named exactly:

```python
@runtime_checkable
class DomainAPI(Protocol):
    ...
```

Produce:

```python
class DefaultDomainAPI:
    ...
```

`DefaultDomainAPI` receives explicit collaborators. The expected collaborator set is:

```python
domain_registry: DomainRegistry
discovery: DomainDiscovery
validator: PipelineDomainValidator
loader: DeclarativeDomainLoader
resolver: DomainResolver
operation_orchestrator: DefaultDomainOperationOrchestrator
workflow_registry: InMemoryDomainWorkflowRegistry
workflow_executor: DomainWorkflowExecutor
session_adapter: SharedSessionDomainAdapter
session_resumer: DomainSessionResumer
conflict_resolver: DomainConflictResolver
trace_assembler: DomainTraceAssembler
trace_validator: DomainTraceReferenceValidator
```

Do not instantiate hidden singleton collaborators inside the facade.

- [ ] **Step 1: Write RED protocol/constructor tests**

Assert:

```python
assert isinstance(api, DomainAPI)
```

and verify construction stores only collaborator references.

Use a test that rejects `None` for required collaborators with `TypeError` or `ValueError`, without introducing a new API error hierarchy.

- [ ] **Step 2: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_contracts.py
```

Expected: import/class failure because `cmm.domains.api` does not exist.

- [ ] **Step 3: Implement only protocol + constructor**

Create `cmm/domains/api.py` with imports from existing canonical modules and the approved 21 public method names:

```text
list_domains
get_domain
discover_domains
validate_domain
install_domain
enable_domain
disable_domain
resolve_domain
get_capabilities
get_resources
get_rules
get_operations
get_workflows
execute_operation
start_workflow
get_session
resume_session
resolve_conflict
assemble_trace
validate_trace
```

Methods may raise `NotImplementedError` only transiently during this local RED/GREEN cycle; remove all such placeholders before committing Task 1. Prefer implementing thin delegations as subsequent tasks rather than committing placeholder methods.

- [ ] **Step 4: GREEN constructor/protocol tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_contracts.py
```

- [ ] **Step 5: Ruff + diff hygiene**

```bash
.venv/bin/ruff check cmm/domains/api.py tests/domains/test_domain_api_contracts.py
.venv/bin/ruff format --check cmm/domains/api.py tests/domains/test_domain_api_contracts.py
git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/api.py \
  tests/domains/test_domain_api_contracts.py
git diff --cached --check
git commit -m "feat(domains): add domain api facade contract"
```

---

### Task 2: Implement read-only domain inspection

**Files:**
- Modify: `cmm/domains/api.py`
- Create: `tests/domains/test_domain_api_queries.py`

**Interfaces:**

Implement:

```python
def list_domains(
    self,
    query: DomainQuery | None = None,
) -> tuple[DomainDefinition, ...]:
    return self._domain_registry.list(query)

def get_domain(
    self,
    domain_id: str,
    version: str | None = None,
) -> DomainDefinition | None:
    return self._domain_registry.get(domain_id, version)
```

Implement `get_capabilities` from the canonical `DomainDefinition.capabilities`.

Implement the exact identifier-returning registry surfaces already available:

```python
DomainRegistry.list_resources(domain_id, version) -> tuple[str, ...]
DomainRegistry.list_rules(domain_id, version) -> tuple[str, ...]
DomainRegistry.list_operations(domain_id, version) -> tuple[str, ...]
DomainRegistry.list_workflows(domain_id, version) -> tuple[str, ...]
```

The API must not build a second catalog.

- [ ] **Step 1: Write RED query tests**

Use a real `DomainRegistry` and canonical `DomainDefinition` fixture.

Prove:

```text
list_domains delegates query filtering
get_domain returns canonical object identity
get_capabilities returns definition-declared capabilities
get_resources/rules/operations/workflows equal registry canonical tuples
```

- [ ] **Step 2: Snapshot mutation-sensitive state**

Before every read-only call, record:

```python
before = registry.snapshot_state()
```

After the call:

```python
assert registry.snapshot_state() == before
```

- [ ] **Step 3: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_queries.py
```

- [ ] **Step 4: Implement minimal delegations**

Do not sort, deduplicate, cache, infer, or transform canonical registry results unless the underlying contract already does so.

- [ ] **Step 5: GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_queries.py \
  tests/domains/test_domain_registry.py
```

If the exact registry regression filename differs, obtain it with:

```bash
rg -l 'class DomainRegistry|DomainRegistry\(' tests/domains --glob '*.py' | sort
```

and run the directly relevant existing registry tests.

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/api.py \
  tests/domains/test_domain_api_queries.py
git diff --cached --check
git commit -m "feat(domains): expose domain api queries"
```

---

### Task 3: Implement discovery, validation, install, enable and disable

**Files:**
- Modify: `cmm/domains/api.py`
- Create: `tests/domains/test_domain_api_lifecycle.py`

**Interfaces:**

Implement direct canonical delegation:

```python
def discover_domains(
    self,
    sources: tuple[DomainSource, ...],
) -> DomainDiscoveryResult:
    return self._discovery.discover(sources)

def validate_domain(
    self,
    request: DomainValidationRequest,
) -> DomainValidationResult:
    return self._validator.validate(request)

def install_domain(
    self,
    candidate: DomainCandidate,
) -> DomainLoadResult:
    return self._loader.load(candidate)

def enable_domain(
    self,
    domain_id: str,
    version: str | None = None,
) -> DomainDefinition:
    return self._domain_registry.enable(domain_id, version)

def disable_domain(
    self,
    domain_id: str,
    version: str | None = None,
) -> DomainDefinition:
    return self._domain_registry.disable(domain_id, version)
```

Do not expose durable filesystem install behavior.

- [ ] **Step 1: Write RED lifecycle tests with real canonical discovery/validation/loader**

Reuse existing loader fixture helpers under `tests/domains/` instead of inventing a second package builder.

Create a temporary valid Domain Pack candidate and prove:

```text
discover -> candidate returned
validate -> canonical result returned
install -> DeclarativeDomainLoader.load path used
registry contains installed definition
installed definition is not implicitly enabled
```

- [ ] **Step 2: Write RED negative invariants**

Prove:

```text
validate does not register
discover does not register
install does not authorize
untrusted candidate remains blocked by canonical loader default
enable is a separate explicit call
disable is a separate explicit call
```

Use the canonical loader exception/result behavior; do not normalize it.

- [ ] **Step 3: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_lifecycle.py
```

- [ ] **Step 4: Implement minimal delegation**

No copying, extracting, publishing, package repository, filesystem install root, hidden reload, or API-side rollback logic.

- [ ] **Step 5: GREEN + lifecycle regressions**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_lifecycle.py \
  tests/domains/test_domain_loader.py \
  tests/domains/test_domain_discovery.py \
  tests/domains/test_domain_validation.py
```

If an exact filename differs, resolve it with `rg -l` and run the canonical test file; do not skip the regression category.

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/api.py \
  tests/domains/test_domain_api_lifecycle.py
git diff --cached --check
git commit -m "feat(domains): expose domain api lifecycle"
```

---

### Task 4: Implement canonical resolution

**Files:**
- Modify: `cmm/domains/api.py`
- Modify: `tests/domains/test_domain_api_execution.py` (create in this task)

**Interfaces:**

Implement exactly:

```python
def resolve_domain(
    self,
    context: DomainResolutionContext,
) -> DomainResolutionResult:
    return self._resolver.resolve(context)
```

No scoring or selection logic belongs in `api.py`.

- [ ] **Step 1: Write RED resolution delegation test**

Use a real `DefaultDomainResolver` with deterministic `clock` and `id_factory`.

Compare:

```python
expected = resolver.resolve(context)
actual = api.resolve_domain(context)
assert actual == expected
```

Use distinct resolver instances or fixed factories if the canonical result includes generated identifiers.

- [ ] **Step 2: Prove facade cannot override safety**

Use an existing blocked/ambiguous resolver scenario and assert the API preserves the canonical status, rejected/ambiguous domains, confidence and reason codes unchanged.

- [ ] **Step 3: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_execution.py -k resolve
```

- [ ] **Step 4: Implement delegation and GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_execution.py -k resolve
```

- [ ] **Step 5: Commit**

```bash
git add -- \
  cmm/domains/api.py \
  tests/domains/test_domain_api_execution.py
git diff --cached --check
git commit -m "feat(domains): expose canonical domain resolution"
```

---

### Task 5: Route operation execution only through the authoritative orchestrator

**Files:**
- Modify: `cmm/domains/api.py`
- Modify: `tests/domains/test_domain_api_execution.py`

**Interfaces:**

Consume canonical:

```python
DefaultDomainOperationOrchestrator.execute(
    request: DomainOperationRequest,
) -> DomainOperationResult
```

Expose:

```python
def execute_operation(
    self,
    request: DomainOperationRequest,
) -> DomainOperationResult:
    return self._operation_orchestrator.execute(request)
```

- [ ] **Step 1: Write RED no-bypass test**

Build the existing real stack:

```text
InMemoryAgentOperationRegistry
InMemoryDomainOperationRegistry
DomainOperationExecutionDelegate
AgentExecutionAdapter
DefaultDomainOperationOrchestrator
DomainPermissionGate
ApprovalService
TransactionManager
```

Reuse the established Project/operation transaction test helpers where practical.

Call only:

```python
api.execute_operation(domain_request)
```

Assert the underlying implementation execution counter remains `0` when permission/approval blocks execution.

- [ ] **Step 2: Write RED approved execution test**

Use a low-risk permitted operation or a correctly bound real approval.

Assert:

```text
api.execute_operation(...)
-> DefaultDomainOperationOrchestrator
-> canonical permission/approval evaluation
-> delegate
-> implementation exactly once
-> canonical DomainOperationResult
```

Do not call the implementation directly anywhere in the accepted positive path.

- [ ] **Step 3: Canonical exception propagation**

Cause an established operation contract error and assert the exact canonical exception type escapes unchanged.

Do not catch/re-wrap it in `DomainAPI`.

- [ ] **Step 4: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_execution.py -k operation
```

- [ ] **Step 5: Implement one-line delegation**

No API-side permission, approval, transaction, rollback, implementation lookup, or result assembly.

- [ ] **Step 6: GREEN + operation regressions**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_execution.py \
  tests/domains/test_domain_operation_transactions.py \
  tests/domains/test_domain_permission_gate.py
```

- [ ] **Step 7: Commit**

```bash
git add -- \
  cmm/domains/api.py \
  tests/domains/test_domain_api_execution.py
git diff --cached --check
git commit -m "feat(domains): route domain api operations"
```

---

### Task 6: Route workflow start through canonical registry and executor

**Files:**
- Modify: `cmm/domains/api.py`
- Modify: `tests/domains/test_domain_api_execution.py`

**Interfaces:**

Canonical registry:

```python
InMemoryDomainWorkflowRegistry.resolve_active(
    workflow_id: str,
) -> DomainWorkflowDefinition
```

Canonical executor:

```python
DomainWorkflowExecutor.execute_result(
    definition: DomainWorkflowDefinition,
    context: DomainWorkflowContext,
    inputs: dict[str, Any],
) -> DomainWorkflowResult
```

Expose:

```python
def start_workflow(
    self,
    workflow_id: str,
    context: DomainWorkflowContext,
    inputs: Mapping[str, Any],
) -> DomainWorkflowResult:
    definition = self._workflow_registry.resolve_active(workflow_id)
    return self._workflow_executor.execute_result(
        definition,
        context,
        dict(inputs),
    )
```

Use the exact existing accepted mapping type if static typing requires `dict[str, Any]`; do not create a new workflow request DTO.

- [ ] **Step 1: Write RED registry authority test**

Register two versions or one active canonical workflow using `InMemoryDomainWorkflowRegistry`.

Assert the API obtains the definition through `resolve_active`; it must not use caller-provided workflow definitions.

- [ ] **Step 2: Write RED real workflow execution test**

Reuse an existing simple domain workflow definition and `DomainWorkflowExecutor` with deterministic IDs.

Assert returned object is canonical `DomainWorkflowResult`.

- [ ] **Step 3: Permission fail-closed test**

Use a workflow context requiring permissions with no suitable gate and assert the existing canonical workflow failure behavior remains unchanged.

- [ ] **Step 4: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_execution.py -k workflow
```

- [ ] **Step 5: Implement minimal registry + executor coordination**

No workflow node loop, state machine, permission logic, retries, or engine logic in `api.py`.

- [ ] **Step 6: GREEN + workflow regressions**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_execution.py \
  tests/domains/test_domain_workflow_execution.py \
  tests/domains/test_domain_workflow_registry.py
```

Resolve exact existing filenames with `rg -l 'DomainWorkflowExecutor|InMemoryDomainWorkflowRegistry' tests/domains` if necessary.

- [ ] **Step 7: Commit**

```bash
git add -- \
  cmm/domains/api.py \
  tests/domains/test_domain_api_execution.py
git diff --cached --check
git commit -m "feat(domains): route domain api workflows"
```

---

### Task 7: Implement shared-session lookup and safe resumption

**Files:**
- Modify: `cmm/domains/api.py`
- Create: `tests/domains/test_domain_api_sessions.py`

**Interfaces:**

Implement:

```python
def get_session(
    self,
    session_id: str,
) -> DomainSessionContext | None:
    return self._session_adapter.load_domain_session(session_id)

def resume_session(
    self,
    request: DomainSessionResumeRequest,
) -> DomainSessionResumeResult:
    return self._session_resumer.resume(request)
```

Do not add `list_sessions` or `search_sessions`.

- [ ] **Step 1: Write RED session lookup test**

Reuse the shared session test store/support already present in:

```text
tests/domains/domain_session_test_support.py
tests/domains/session lifecycle/resumer tests
```

Save a canonical `DomainSessionContext` through `SharedSessionDomainAdapter`.

Assert:

```python
api.get_session(session_id) == adapter.load_domain_session(session_id)
```

- [ ] **Step 2: Missing session test**

Assert missing ID returns the canonical `None` behavior and creates no session.

- [ ] **Step 3: Write RED resume test**

Use a real `DomainSessionResumer` wired the same way as existing session tests.

Prove current registry/permission/runtime state is re-evaluated; do not treat persisted context as current authorization.

- [ ] **Step 4: Explicitly reject invented enumeration**

Contract tests must assert `DomainAPI`/`DefaultDomainAPI` do not expose:

```text
list_all_domain_sessions
search_domain_sessions
```

- [ ] **Step 5: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_sessions.py
```

- [ ] **Step 6: Implement delegation and GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_sessions.py \
  tests/domains/test_domain_session_resumer.py
```

Also run the shared session persistence test file returned by:

```bash
rg -l 'SharedSessionDomainAdapter' tests/domains --glob '*.py' | sort
```

- [ ] **Step 7: Commit**

```bash
git add -- \
  cmm/domains/api.py \
  tests/domains/test_domain_api_sessions.py
git diff --cached --check
git commit -m "feat(domains): expose domain api sessions"
```

---

### Task 8: Implement pure conflict resolution and trace coordination

**Files:**
- Modify: `cmm/domains/api.py`
- Create: `tests/domains/test_domain_api_conflicts_traces.py`

**Interfaces:**

Expose conflict resolution using the exact canonical parameters supported by `DomainConflictResolver.resolve(...)`.

At minimum preserve:

```python
case: DomainConflictCase
policy: DomainConflictResolutionPolicy | None = None
primary_domain: DomainId | None = None
highest_risk_domain: DomainId | None = None
```

If the canonical method has additional optional authority parameters at implementation HEAD, mirror them explicitly rather than forwarding arbitrary `**kwargs`.

Trace methods:

```python
def assemble_trace(
    self,
    request: DomainTraceAssemblyRequest,
) -> DomainTrace:
    return self._trace_assembler.assemble(request)

def validate_trace(
    self,
    trace: DomainTrace,
    inventory: DomainTraceReferenceInventory,
) -> DomainTraceValidationResult:
    return self._trace_validator.validate(trace, inventory)
```

- [ ] **Step 1: Write RED conflict delegation test**

Create immutable `DomainConflictCase`.

Record:

```python
before = case.to_dict()
result = api.resolve_conflict(case, ...)
assert case.to_dict() == before
```

Compare with direct `DomainConflictResolver.resolve(...)`.

- [ ] **Step 2: Write RED trace assembly equivalence test**

Use canonical `DomainTraceAssemblyRequest`.

With identical deterministic request:

```python
assert api.assemble_trace(request) == assembler.assemble(request)
```

- [ ] **Step 3: Write RED trace validation test**

Build a matching `DomainTraceReferenceInventory`.

Assert API result equals `DefaultDomainTraceReferenceValidator.validate(...)`.

- [ ] **Step 4: No hidden persistence test**

After `assemble_trace`, assert the facade has not gained fields such as:

```text
_traces
_trace_store
_trace_cache
_trace_repository
```

and has no `get_trace`/`list_traces` API.

- [ ] **Step 5: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_conflicts_traces.py
```

- [ ] **Step 6: Implement minimal delegations and GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_conflicts_traces.py \
  tests/domains/test_domain_conflict_resolution.py
```

Also run trace assembler/validation regressions returned by:

```bash
rg -l 'DomainTraceAssembler|DefaultDomainTraceReferenceValidator' \
  tests/domains --glob '*.py' | sort
```

- [ ] **Step 7: Commit**

```bash
git add -- \
  cmm/domains/api.py \
  tests/domains/test_domain_api_conflicts_traces.py
git diff --cached --check
git commit -m "feat(domains): expose conflicts and traces via domain api"
```

---

### Task 9: Publish the stable Domain API surface and prove import safety

**Files:**
- Modify: `cmm/domains/__init__.py`
- Modify: `tests/domains/test_domain_api_contracts.py`
- Modify: `tests/domains/test_domain_public_api.py` only if the repository's canonical public-API inventory requires it

**Interfaces:**

Publicly export:

```python
DomainAPI
DefaultDomainAPI
```

No import-time construction.

- [ ] **Step 1: Write RED public export test**

```python
import cmm.domains as domains

assert domains.DomainAPI is DomainAPI
assert domains.DefaultDomainAPI is DefaultDomainAPI
```

- [ ] **Step 2: Fresh-import side-effect test**

In a subprocess, execute:

```python
import cmm.domains
import cmm.domains.api
```

Prove:

```text
return code = 0
no filesystem creation
no registry mutation
no network/model/runtime execution
```

Use a temporary current directory and compare its file inventory before/after.

- [ ] **Step 3: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_contracts.py \
  tests/domains/test_domain_public_api.py
```

- [ ] **Step 4: Export symbols only**

Modify imports and `__all__` consistently.

Do not add default global `DefaultDomainAPI()` or bootstrap state.

- [ ] **Step 5: GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_contracts.py \
  tests/domains/test_domain_public_api.py
```

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/__init__.py \
  tests/domains/test_domain_api_contracts.py \
  tests/domains/test_domain_public_api.py
git diff --cached --check
git commit -m "feat(domains): publish stable domain api"
```

Stage `tests/domains/test_domain_public_api.py` only if changed.

---

### Task 10: Build connected AT-DP-036 acceptance

**Files:**
- Create: `tests/domains/test_domain_api_dp036_acceptance.py`

**Interfaces:**

The acceptance must prove the facade against real canonical or official in-memory components, not behavior-replacing mocks.

Required connected checkpoints:

```text
1. discover valid test Domain Pack
2. validate candidate
3. install via DeclarativeDomainLoader
4. prove installed != enabled
5. list/get through API
6. explicitly enable
7. inspect capabilities
8. inspect resources
9. inspect rules
10. inspect operations
11. inspect workflows
12. resolve through canonical resolver
13. execute operation through DefaultDomainOperationOrchestrator
14. start workflow through workflow registry + DomainWorkflowExecutor
15. persist and get DomainSessionContext through SharedSessionDomainAdapter
16. resume through DomainSessionResumer
17. resolve DomainConflictCase through pure DomainConflictResolver
18. assemble reference-only DomainTrace
19. validate trace with canonical reference inventory
20. explicitly disable
```

- [ ] **Step 1: Build one canonical runtime state**

Use the same `DomainRegistry` instance throughout lifecycle/query/session-resolution portions.

Use canonical in-memory operation/workflow registries.

Do not silently bootstrap a second registry to make a checkpoint pass.

- [ ] **Step 2: Use an actual discovered/loaded candidate**

Reuse existing loader test fixture machinery to create a small valid Domain Pack in `tmp_path`.

The proof must pass through:

```text
FileSystemDomainDiscovery
PipelineDomainValidator
DeclarativeDomainLoader
```

not through a fake loader.

- [ ] **Step 3: Connect operation execution**

Register an official test implementation through `InMemoryDomainOperationRegistry` and execute only through the real `DefaultDomainOperationOrchestrator`.

Prove the API cannot execute when the canonical gate blocks.

Then provide the legitimate canonical authority needed for the positive path and prove exactly one implementation invocation.

- [ ] **Step 4: Connect workflow execution**

Resolve the installed/registered workflow through `InMemoryDomainWorkflowRegistry.resolve_active(...)` and execute through `DomainWorkflowExecutor`.

No direct node execution.

- [ ] **Step 5: Connect shared session persistence/resumption**

Use `SharedSessionDomainAdapter` over the existing shared SessionStore test implementation and a real `DomainSessionResumer`.

The persisted state must not bypass current registry/authorization checks.

- [ ] **Step 6: Connect conflict and trace**

Use canonical `DomainConflictResolver`, `DomainTraceAssembler`, and `DefaultDomainTraceReferenceValidator`.

Trace remains reference-only.

- [ ] **Step 7: Assert structural anti-fragmentation**

Inspect the API object and production module:

```text
no owned DomainRegistry created by DefaultDomainAPI
no second loader/resolver/executor
no session store
no trace store
no cache
no event bus
```

- [ ] **Step 8: Run AT-DP-036**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_dp036_acceptance.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add -- tests/domains/test_domain_api_dp036_acceptance.py
git diff --cached --check
git commit -m "test(domains): connect phase 10.36 domain api acceptance"
```

---

### Task 11: Run adversarial facade boundary coverage

**Files:**
- Modify the most appropriate existing Phase 10.36 test files only

**Required adversarial cases:**

- [ ] install does not implicitly enable;
- [ ] install does not implicitly authorize;
- [ ] untrusted load remains fail-closed;
- [ ] discovery does not mutate registry;
- [ ] validation does not mutate registry;
- [ ] read-only queries do not mutate registry;
- [ ] operation cannot bypass permission/approval;
- [ ] workflow cannot bypass canonical executor/gate behavior;
- [ ] missing session does not create one;
- [ ] persisted session state does not confer current authorization;
- [ ] conflict resolver input remains unchanged;
- [ ] trace assembly creates no store/cache;
- [ ] canonical exceptions retain exact subsystem type;
- [ ] no global session enumeration API;
- [ ] no persistent trace lookup API;
- [ ] no durable package installation API;
- [ ] no generic `DomainAPIError`;
- [ ] fresh import is side-effect free.

- [ ] **Step 1: Run all focused API tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_contracts.py \
  tests/domains/test_domain_api_queries.py \
  tests/domains/test_domain_api_lifecycle.py \
  tests/domains/test_domain_api_execution.py \
  tests/domains/test_domain_api_sessions.py \
  tests/domains/test_domain_api_conflicts_traces.py \
  tests/domains/test_domain_api_dp036_acceptance.py
```

- [ ] **Step 2: Run focused Ruff/format**

```bash
.venv/bin/ruff check \
  cmm/domains/api.py \
  tests/domains/test_domain_api_contracts.py \
  tests/domains/test_domain_api_queries.py \
  tests/domains/test_domain_api_lifecycle.py \
  tests/domains/test_domain_api_execution.py \
  tests/domains/test_domain_api_sessions.py \
  tests/domains/test_domain_api_conflicts_traces.py \
  tests/domains/test_domain_api_dp036_acceptance.py

.venv/bin/ruff format --check \
  cmm/domains/api.py \
  tests/domains/test_domain_api_contracts.py \
  tests/domains/test_domain_api_queries.py \
  tests/domains/test_domain_api_lifecycle.py \
  tests/domains/test_domain_api_execution.py \
  tests/domains/test_domain_api_sessions.py \
  tests/domains/test_domain_api_conflicts_traces.py \
  tests/domains/test_domain_api_dp036_acceptance.py

git diff --check
```

- [ ] **Step 3: Commit only if this task added/changed tests**

```bash
git add -- tests/domains/test_domain_api_*.py
git diff --cached --check
git commit -m "test(domains): harden domain api boundaries"
```

Skip the commit if no files changed.

---

### Task 12: Document the public API and implementation-pending-audit state

**Files:**
- Create: `docs/reference/domain-api.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `ROADMAP.md`

**Interfaces / required status:**

Document only:

```text
Phase 10.36 implementation complete — independent audit pending
DP-036 = IMPLEMENTED_PENDING_AUDIT
AT-DP-036 = PASS
```

Do not claim independent audit or closure.

`docs/reference/domain-api.md` must document:

```text
purpose and non-goals
DomainAPI / DefaultDomainAPI
constructor collaborators
all 21 public methods
canonical owner of every method
install semantics
read-only vs mutating methods
operation/workflow authorization boundaries
shared session persistence boundary
pure conflict boundary
reference-only trace boundary
error propagation
no session enumeration
no trace store
examples of direct Python usage
```

- [ ] **Step 1: Write docs after symbols/tests exist**

Cross-check every documented method signature against `cmm/domains/api.py`.

- [ ] **Step 2: Add DP-036 / AT-DP-036 to requirements matrix**

The matrix must point to actual production/test symbols and state:

```text
DP-036 = IMPLEMENTED_PENDING_AUDIT
AT-DP-036 = PASS
```

- [ ] **Step 3: Update detailed roadmap and root roadmap**

Phase 10.35 remains closed.

Phase 10.36 becomes implementation-complete / audit-pending.

Do not advance to Phase 10.37 as started.

- [ ] **Step 4: Verify no premature closure wording**

```bash
if rg -n \
  'Phase 10\.36.*(closed|independently audited|final audit.*PASS)|DP-036=VERIFIED_EXISTING' \
  ROADMAP.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/reference/domain-api.md
then
  echo "PREMATURE_CLOSURE_WORDING=FAIL"
  exit 1
fi

echo "PREMATURE_CLOSURE_WORDING=PASS"
```

- [ ] **Step 5: Commit docs**

```bash
git add -- \
  docs/reference/domain-api.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  ROADMAP.md
git diff --cached --check
git commit -m "docs(domains): document phase 10.36 domain api"
```

---

### Task 13: Full regression and quality gates

**Files:**
- No intended production changes.

- [ ] **Step 1: Focused Phase 10.36 suite**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/domains/test_domain_api_contracts.py \
  tests/domains/test_domain_api_queries.py \
  tests/domains/test_domain_api_lifecycle.py \
  tests/domains/test_domain_api_execution.py \
  tests/domains/test_domain_api_sessions.py \
  tests/domains/test_domain_api_conflicts_traces.py \
  tests/domains/test_domain_api_dp036_acceptance.py
```

- [ ] **Step 2: Canonical subsystem regressions**

Run tests covering:

```text
registry
discovery
validation
loader
resolver/selection
permission gate
operation orchestration/transactions/rollback
workflow registry/execution
session persistence/resumption
conflict resolution
trace assembly/validation
Phase 10.35 SDK
```

Resolve exact existing files with `rg -l` where filenames differ; no category may be silently omitted.

- [ ] **Step 3: Domain suite**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/domains
```

- [ ] **Step 4: Full repository suite**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q
```

- [ ] **Step 5: Ruff**

```bash
.venv/bin/ruff check cmm/domains tests/domains
```

- [ ] **Step 6: Format**

```bash
.venv/bin/ruff format --check cmm/domains tests/domains
```

- [ ] **Step 7: Compileall**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q \
  cmm/domains \
  tests/domains
```

- [ ] **Step 8: Diff hygiene**

```bash
git diff --check
test -z "$(git status --porcelain)"
```

If tests create caches ignored by Git, cleanliness is determined by Git status.

- [ ] **Step 9: Invariant gate — general events**

Use the canonical event registry/catalog APIs already exercised by Phase 10 tests and prove:

```text
GENERAL_EVENTS=23
UNIQUE_GENERAL_EVENTS=23
domain.session.resumed absent
```

- [ ] **Step 10: Invariant gate — conflict purity / no parallel architecture**

```bash
rg -n \
  'class (DomainAPIRegistry|DomainAPILoader|DomainAPIResolver|DomainAPIWorkflowEngine|DomainAPISessionStore|DomainAPITraceStore)|class .*TraceStore|class .*SessionStore' \
  cmm/domains/api.py
```

Expected: no matches.

Run existing conflict purity regression tests.

- [ ] **Step 11: Record exact evidence**

Capture actual pass counts and command outputs for the implementation report/audit preparation. Do not invent or predeclare counts.

---

### Task 14: Prepare committed implementation for independent audit

**Files:**
- No code changes unless a gate failed and was remediated first.

- [ ] **Step 1: Verify all implementation/docs commits are present**

```bash
git log --oneline --decorate -20
git status --short --branch
```

- [ ] **Step 2: Verify clean worktree and quarantine stash**

```bash
test -z "$(git status --porcelain)"
git stash list | grep -Fq \
  "quarantine: post-audit phase 10.32 uncommitted changes"
```

- [ ] **Step 3: Record exact implementation HEAD**

```bash
AUDITED_HEAD="$(git rev-parse HEAD)"
echo "AUDITED_HEAD=$AUDITED_HEAD"
```

The implementation HEAD must include code, tests, DP/AT evidence and pre-audit documentation.

- [ ] **Step 4: Create exact-HEAD audit bundle using `git archive`**

Output under iCloud Downloads:

```bash
OUT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads/phase-10.36-domain-api-audit-v1.tar.gz"

git archive \
  --format=tar.gz \
  --prefix="phase-10.36-domain-api/" \
  -o "$OUT" \
  "$AUDITED_HEAD"
```

Never create the audit bundle from a dirty filesystem `tar`.

- [ ] **Step 5: Calculate SHA-256**

```bash
shasum -a 256 "$OUT"
```

Record:

```text
AUDITED_HEAD=<exact commit>
AUDIT_BUNDLE=<path>
AUDIT_BUNDLE_SHA256=<sha256>
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
PUSH=NO
MERGE=NO
```

- [ ] **Step 6: Stop**

Do not mark Phase 10.36 closed.

Do not create a docs-only closure commit.

Upload the exact bundle to ChatGPT for independent audit.

---

## Acceptance Checklist

Before handing the bundle to the independent auditor, all must be true:

```text
DomainAPI exists
DefaultDomainAPI exists
21 approved methods exposed
all methods use canonical owners
install == canonical runtime load/register
install != enable
install != authorization
no durable package store
queries are mutation-free
resolution delegates to DomainResolver
operation execution delegates to DefaultDomainOperationOrchestrator
workflow start uses resolve_active + DomainWorkflowExecutor
session lookup uses SharedSessionDomainAdapter
session resume uses DomainSessionResumer
no session enumeration invented
conflict resolver remains pure
trace assembly uses DomainTraceAssembler
trace validation uses canonical validator
no trace persistence invented
canonical errors propagate
fresh import side-effect free
DP-036 = IMPLEMENTED_PENDING_AUDIT
AT-DP-036 = PASS
general event catalog = 23/23 unique
domain.session.resumed absent
focused tests PASS
canonical regressions PASS
tests/domains PASS
full suite PASS
Ruff PASS
format PASS
compileall PASS
git diff --check PASS
worktree clean
quarantine stash preserved
exact-HEAD audit TAR.GZ created
SHA-256 recorded
```

## Expected Commit Sequence

A clean implementation will normally produce commits equivalent to:

```text
feat(domains): add domain api facade contract
feat(domains): expose domain api queries
feat(domains): expose domain api lifecycle
feat(domains): expose canonical domain resolution
feat(domains): route domain api operations
feat(domains): route domain api workflows
feat(domains): expose domain api sessions
feat(domains): expose conflicts and traces via domain api
feat(domains): publish stable domain api
test(domains): connect phase 10.36 domain api acceptance
test(domains): harden domain api boundaries       # only if needed
docs(domains): document phase 10.36 domain api
```

Do not squash unless explicitly requested.

## Self-Review

- Spec coverage: all Sections 4–30 of the approved design map to Tasks 1–14.
- Public surface coverage: all 21 approved methods have an implementation/test owner.
- Install semantics: explicitly bound to `DeclarativeDomainLoader.load`.
- Execution safety: operation and workflow paths reuse authoritative existing orchestrators/executors.
- Persistence boundaries: shared SessionStore only; no trace/package store.
- Error model: canonical errors remain visible.
- DP/AT: connected acceptance explicitly planned.
- Auditability: exact committed HEAD and SHA-bound `git archive` bundle required.
- Placeholder scan: no `TBD`, `TODO`, `FIXME`, or “implement later” instructions remain.
- Scope: Phase 10.36 does not implement HTTP/REST/MCP/CLI expansion, persistent package installation, trace storage, session search, approval-response endpoints, permission administration, or memory-proposal APIs beyond the approved 10.36 design.
