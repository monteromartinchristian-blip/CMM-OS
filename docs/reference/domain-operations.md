# Domain Operations

Phase 10.13 adds domain-specialized operations without adding another execution runtime. Definitions, discovery and domain-aware availability live in `cmm.domains`; execution, approval, validation and transactions remain owned by Agent Runtime.

## Architecture and ownership

```text
DomainOperationDefinition / DomainOperationRequest
                     |
          InMemoryDomainOperationRegistry
          (adapts OperationDescriptor into the
           injected AgentOperationRegistry)
                     |
      DomainOperationAvailabilityResolver
                     |
      DefaultDomainOperationOrchestrator
                     |
             AgentExecutionAdapter
                     |
       DomainOperationExecutionDelegate
                     |
       registered domain implementation
```

The orchestrator never retrieves or calls an implementation. `DomainOperationExecutionDelegate` is the injected delegate called by `AgentExecutionAdapter`, so the common adapter remains the mandatory execution path. `cmm.agent_runtime` and `cmm.execution` do not import `cmm.domains`.

The common layer supplies:

- `OperationDescriptor`, `AgentOperationRequest` and `AgentOperationExecutionResult`;
- `AgentOperationRegistry` and `AgentExecutionAdapter`;
- `AgentPermissionContext` and permission decisions;
- `ApprovalRequirement`, `ApprovalRequest` and `ApprovalService`;
- `ValidationPolicy` and `AgentValidationAdapter`;
- `TransactionManager`, checkpoint contracts and `RollbackPolicy`;
- runtime events, traces, sessions and `MemoryUpdateProposal`.

Phase 10.13 adds only two domain-neutral common capabilities: safe nested operation-schema validation and generic structured output/error transport on `AgentOperationExecutionResult`.

## Definition and implementation

`DomainOperationDefinition` is the only serializable registration artifact. It contains a canonical operation ID, canonical domain ID, strict SemVer, type, input/output schemas, resources, permissions, risk, reversibility, approval and policy references. It contains no callable, registry or service.

An implementation exposes a matching `definition` and `execute(AgentOperationRequest)` method. The domain registry validates the method signature without calling it and keeps implementation references separate from definition inspection.

The closed operation types are `read`, `analysis`, `preparation`, `memory`, `planning`, `external`, `sensitive` and `destructive`. Destructive definitions require explicit approval at construction time.

## Registry and version resolution

`InMemoryDomainOperationRegistry` wraps an injected common registry. It supports exact ID/version lookup, active enabled-version resolution, enable/disable, definition-only inspection and deterministic filters by domain, type, risk and resolved availability. Versions use SemVer precedence, so `1.10.0` is newer than `1.9.0` and stable releases outrank prereleases with the same core version.

Registration is explicit. There is no module discovery, filesystem access, plugin import or mutable global registry.

## Schemas

`validate_operation_schema` is a safe domain-neutral subset used by the common registry for both nested input validation and domain output validation. It supports objects, arrays, required fields, strict additional properties, primitive/null types, enums and basic size/range limits. Errors contain a stable code and JSON path such as `$.items[0].name`.

The validator distinguishes a missing property from a present `None`, rejects booleans as integers/numbers, rejects NaN and Infinity, and rejects unsupported keywords including remote `$ref`. It never evaluates code.

## Availability, permissions and approval

`DomainOperationAvailabilityResolver` is pure. It receives a definition and `DomainOperationAvailabilityContext`; it does not resolve profiles or compose domains. Its deterministic result is one of `available`, `unavailable`, `blocked` or `waiting_for_approval` and includes required/granted/denied permissions, available/missing resources, effective policies, risk and structured trace entries.

Explicit denial wins over grants. Missing permissions block. Missing resources or capabilities make an operation unavailable. A destructive or approval-required operation cannot become available until an approval is approved and bound to the exact operation version, normalized inputs and domain context.

`build_domain_operation_approval_requirement()` creates an `ApprovalRequirement`; it does not persist or grant approval. `ApprovalService` remains responsible for creating and resolving the actual request.

## Effective domain context

`DomainOperationContext.from_effective()` consumes an already-created `ResolvedDomainProfile` and optional `DomainComposition`. It preserves primary/supporting domains, profile and composition IDs, composed operations, selected rule IDs, effective permissions and provenance. It validates alignment but never invokes a profile resolver, composer or rule executor.

## Execution, validation and errors

`DefaultDomainOperationOrchestrator.execute()` performs these coordination steps:

1. resolve the exact registered definition;
2. validate input with the common schema validator;
3. resolve domain availability and approval binding;
4. start an injected common transaction when required;
5. build `AgentOperationRequest` and call `AgentExecutionAdapter.execute()` exactly once;
6. verify result identity and validate output;
7. commit or coordinate rollback through injected common services;
8. return immutable `DomainOperationResult` with structured trace and errors.

Expected `DomainOperationExecutionError` values cross the delegate boundary as `ControlledOperationExecutionError` and become sanitized common failures. Programming and contract errors such as `TypeError`, invalid implementation return types and identity mismatches propagate. Public results never contain raw exception text.

The domain boundary rejects a returned `memory_write` effect. Memory operations may return proposals but cannot write memory directly.

## Transactions and rollback

Read-only/non-reversible operations may run without a transaction. Reversible operations become available only with transaction and rollback capabilities and a resolvable rollback policy when one is declared. The orchestrator uses the injected `TransactionManager`; it does not create its own transaction state.

Successful output validation precedes transaction commit. Execution or output-validation failure triggers the injected rollback executor. A successful rollback produces `rolled_back`. A failed rollback leaves the operation `failed`, preserves the original error and records a distinct rollback error.

## Results and states

Definitions, requests, effective contexts, availability decisions, trace entries, rollback results and domain results are immutable and JSON-safe. Datetimes are timezone-aware and final completion cannot precede start. Serialized constructors reject unknown fields where provided.

The lifecycle states are `registered`, `available`, `unavailable`, `blocked`, `waiting_for_approval`, `running`, `completed`, `failed`, `rolled_back` and `cancelled`. `validate_domain_operation_transition()` rejects impossible and terminal-state transitions.

## Initial catalog

`build_initial_domain_operation_catalog(common_registry)` registers exactly 20 definitions across general, health, university, relationships and project domains. Only `general.read_resources` and `general.prepare_structured_summary` perform a small deterministic structural transformation. The remaining demonstrations return `not_applicable` with `capability_not_configured`; they do not pretend to plan, validate, diagnose, contact services, modify code or write memory.

## Side-effect-free example

```python
from cmm.agent_runtime import AgentExecutionAdapter, InMemoryAgentOperationRegistry
from cmm.domains import (
    DefaultDomainOperationOrchestrator,
    DomainOperationExecutionDelegate,
    DomainOperationRequest,
    build_initial_domain_operation_catalog,
)

common_registry = InMemoryAgentOperationRegistry()
domain_registry = build_initial_domain_operation_catalog(common_registry)
adapter = AgentExecutionAdapter(
    registry=common_registry,
    execution_delegate=DomainOperationExecutionDelegate(domain_registry),
)
orchestrator = DefaultDomainOperationOrchestrator(domain_registry, adapter)

result = orchestrator.execute(
    DomainOperationRequest(
        request_id="request:summary:1",
        operation_id="general.prepare_structured_summary",
        operation_version="1.0.0",
        inputs={"items": ["fact", "question"]},
        agent_run_id="run:1",
        workflow_id="workflow:compatibility",
        task_id="task:1",
        primary_domain_id="domain:general",
        idempotency_key="summary:1",
        capabilities=("execute",),
    )
)
```

This example uses only in-memory injected components and performs no filesystem, network, subprocess, model or persistence operation.

## Deliberate limits

Phase 10.13 does not implement Domain Workflows, full Domain Permission policy, presentation rendering, persistent Domain Trace, full Domain Packs, multimodal operations, model selection, advanced privacy/budgets, session orchestration, auto-extension or deep Agent Runtime integration. It provides compatibility seams for later phases without implementing them early.
