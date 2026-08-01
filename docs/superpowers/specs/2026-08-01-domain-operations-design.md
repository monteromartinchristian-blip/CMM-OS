# Phase 10.13 Domain Operations Design

## Status

Approved by the Phase 10.13 implementation brief and the user on 2026-08-01. The user additionally requires that common-layer additions remain domain-neutral and reusable, and that domain orchestration never invokes an implementation directly or reproduces `AgentExecutionAdapter` logic.

## Objective

Provide strict, deterministic domain-operation contracts and services that register, discover, authorize, execute, validate and audit domain-specialized operations through CMM OS's existing operational infrastructure. Phase 10.13 adds no persistence, network, subprocess, LLM, CLI, API, workflow engine or direct memory writes.

## Existing Contracts and Ownership

The repository has no `cmm.operations`, `cmm.security` or `cmm.workflows` package. Names in the roadmap map to these real contracts:

| Concept | Existing contract | Owner |
|---|---|---|
| Common operation definition | `OperationDescriptor` | `cmm.agent_runtime.operation_execution_contracts` |
| Common execution request/context | `AgentOperationRequest`, `ValidationExecutionContext` | `cmm.agent_runtime` |
| Common execution result | `AgentOperationExecutionResult` | `cmm.agent_runtime.operation_execution_contracts` |
| Common operation registry | `AgentOperationRegistry`, `InMemoryAgentOperationRegistry` | `cmm.agent_runtime.operation_registry` |
| Common execution path | `AgentExecutionAdapter` and its injected execution delegate | `cmm.agent_runtime.operation_execution_adapter` |
| Semantic envelope/runtime | `SemanticOperation`, `SemanticExecutor`, `SemanticRuntime` | `kernel.semantic` |
| Transformation execution | `OperationExecutor`, `OperationExecutorRegistry` | `cmm.execution` |
| Permission context/decision | `AgentPermissionContext`, `PermissionDecision`, `PermissionEffect` | `cmm.agent_runtime.agent_security_*` |
| Composed domain permissions | `PermissionComposition` | `cmm.domains.composition_contracts` |
| Approval | `ApprovalRequirement`, `ApprovalRequest`, `ApprovalService`, `ApprovalRequestStatus` | `cmm.agent_runtime` |
| Validation | `ValidationPolicy`, `AgentValidationAdapter`, validation request/result contracts | `cmm.validation`, `cmm.agent_runtime` |
| Transaction | `TransactionManager`, `TransactionBoundary`, `TransactionOperation` | `cmm.agent_runtime` |
| Rollback | `RollbackPolicy`, `RollbackPolicyEvaluator`, checkpoint restoration | `cmm.agent_runtime` |
| Events and trace | `AgentRuntimeEvent`, event bus contracts, agent trace contracts | `cmm.agent_runtime` |
| Sessions | `AgentRun.reasoning_session_id`, cognitive session references | `cmm.agent_runtime` |
| Memory proposals | `MemoryUpdateProposal` | `cmm.agent_runtime.knowledge_update_contracts` |
| Domain context | `DomainComposition`, `ResolvedDomainProfile`, domain resources/rules | `cmm.domains` |

`AgentExecutionAdapter` is the required common operational path because it owns registry resolution, idempotency, gates, pre/post validation and delegation. `SemanticRuntime` remains a lower-level generic semantic facility and is not sufficient by itself for Phase 10.13 authorization or transaction requirements. The domain layer therefore delegates to an injected `AgentExecutionAdapter`; it does not invoke an operation implementation.

## Approaches Considered

1. **Thin domain specialization over Agent Runtime (selected).** A domain registry adapts definitions to `OperationDescriptor`; a pure resolver handles domain availability; a domain orchestrator coordinates injected approval/transaction/rollback services and delegates execution to `AgentExecutionAdapter`. This preserves one operational engine.
2. **Use only `SemanticRuntime`.** Rejected because it has no approval, permission, validation-policy or transaction integration and broadly normalizes executor errors.
3. **Create a domain-local execution engine.** Rejected because it would duplicate registry, gate, transaction and execution behavior and violate dependency ownership.

## Architecture

```text
ResolvedDomainProfile + optional DomainComposition
                + DomainOperationRequest
                + effective permissions/resources/capabilities
                              |
                              v
                DomainOperationRegistry
           (definition -> OperationDescriptor)
                              |
                              v
              DomainOperationAvailabilityResolver
                              |
                blocked / unavailable / approval
                              |
                              v
                DomainOperationOrchestrator
       approval + transaction + validation coordination
                              |
                              v
                  AgentExecutionAdapter
                              |
                    injected common delegate
                              |
                              v
                 DomainOperationResult
```

Dependencies point from `cmm.domains` to common layers only. Common modules never import `cmm.domains`.

## Contracts

`DomainOperationDefinition` is the serializable domain specialization. It contains canonical operation/domain IDs, strict SemVer, display fields, `DomainOperationType`, strict input/output schemas, required resources/permissions, existing `PolicyRiskLevel`, reversibility, approval/validation/rollback policy references, enabled state and immutable metadata. Its conversion to `OperationDescriptor` is deterministic and contains no callable or runtime dependency.

The executable implementation contract is structural: implementations expose an exact `definition` and a single `execute(AgentOperationRequest)` method compatible with the common delegate boundary. The registry validates identity and signature without executing implementations and stores definitions separately from isolated implementation references.

`DomainOperationRequest`, `DomainOperationContext`, `DomainOperationAvailability`, `DomainOperationResult`, structured reasons/errors/events/traces and rollback results are frozen, slotted, deeply immutable and exactly round-trippable. Unknown serialized fields are rejected. IDs are non-empty, datetimes are timezone-aware and ordered, values are JSON-safe, floats are finite and strict enums remain closed.

`DomainOperationStatus` covers `registered`, `available`, `unavailable`, `blocked`, `waiting_for_approval`, `running`, `completed`, `failed`, `rolled_back` and `cancelled`. A pure transition function enforces the explicit state graph; terminal states cannot transition.

## Common-Layer Additions

Only domain-neutral gaps may change common code:

- The common schema validator may be hardened or extracted only as a reusable operation-schema facility used by `AgentOperationRegistry`, covering nested JSON-safe validation, strict unknown fields, missing versus `None`, bool/number separation, finite floats and structured paths.
- Common execution results may transport a generic JSON-safe output and typed safe operational error only if their names and semantics are independent of domains.
- A common controlled operational-error boundary may be added so expected failures are normalized while programming/contract exceptions propagate.

No common type may mention domain IDs, domain profiles, domain composition, domain operation types or Phase 10.13.

## Registry and Versioning

`DomainOperationRegistry` is an adapter over an injected `AgentOperationRegistry`. Registration atomically validates the domain definition/implementation pair, converts the definition to a common descriptor, registers that descriptor, and then records the implementation reference. A failure leaves neither side partially registered.

It supports exact versions, active enabled version, explicit enable/disable replacement, deterministic filtering by domain/type/risk/availability and inspection of definitions only. Active versions use the existing strict SemVer parser from `cmm.domains.registry_contracts`, including prerelease precedence. Duplicate ID/version pairs are rejected and same short names in different canonical domains remain distinct.

## Availability, Permissions and Approval

The pure availability resolver consumes only a registered definition and an already-effective context. It does not resolve profiles or compose domains. It evaluates, in deterministic order: enabled state, primary/supporting-domain compatibility, required resources, explicit deny-wins permissions, sensitivity/destructive restrictions, external executor capability, validation policy, transaction support, rollback policy and approval status.

Missing resources yield `unavailable`; explicit policy or permission denial yields `blocked`; approval required without a matching approved request yields `waiting_for_approval`. Destructive operations always require explicit approval. Approval fingerprints bind canonical operation ID, version, normalized inputs and relevant context, preventing reuse for changed inputs.

## Execution and Error Handling

The orchestrator resolves the registered definition, validates inputs, obtains availability, prepares or checks approval, starts a common transaction when required, and builds an `AgentOperationRequest`. It then calls only `AgentExecutionAdapter.execute`. It neither looks up nor invokes the registered implementation and does not reproduce the adapter's gates, idempotency or delegate execution.

After delegation it verifies operation ID/version, validates generic output, coordinates result validation, commits the common transaction and returns the domain aggregate. Controlled operational failures become typed sanitized results. Contract errors, signature mismatches, programmer errors and unexpected return types propagate. No `BaseException`, raw `repr(exc)` or public `str(exc)` is used.

Cancellation is represented when supplied common capabilities indicate cancellation before execution or return a cancelled common result. No new active cancellation runtime is introduced.

## Transactions and Rollback

Read-only operations may execute without a transaction. Reversible operations requiring transactional protection use the injected `TransactionManager`; non-reversible operations cannot advertise rollback. On execution failure or invalid output after execution, the orchestrator uses only injected common rollback/checkpoint services and the resolved `RollbackPolicy`. Successful rollback yields `rolled_back`; failed rollback preserves the original typed failure and adds a separate rollback failure record.

No domain transaction manager, checkpoint store or rollback engine is created.

## Events, Trace and Memory

Results can contain immutable domain-aware event and trace entries with stable event/reason codes, state transitions, contributing domain, provenance and timestamps. They contain decisions and auditable state only, never chain-of-thought. Phase 10.13 returns these entries in the result and does not add event publication or persistence.

Memory-producing operations return `MemoryUpdateProposal` values or conservative proposal-shaped output. They never call a memory repository or writer. Direct-memory-write effects are rejected by the domain boundary.

## Initial Catalog

The catalog contains exactly the 20 requested definitions. Two safe general operations are pure deterministic structure builders. Every deeper demonstration returns `not_applicable` with `capability_not_configured`; runtime availability can also reject an entry when required permissions, approval or capabilities are missing. No catalog operation contacts services, changes code, executes validation, writes memory or claims a deep action succeeded.

## Integration Boundaries

`DomainOperationContext` accepts already-resolved `ResolvedDomainProfile` and optional `DomainComposition`. It verifies that the requested operation belongs to the primary or supporting domains and preserves operation items, contributing domains, permission composition, profile provenance and selected rule references. It never invokes profile resolution, domain composition or rule execution.

Phase 10.14 workflows and Phases 10.15–10.25 remain out of scope. Agent Runtime integration is the narrow adapter required for execution, not the deep runtime orchestration planned for Phase 10.41.

## Testing

TDD suites cover contracts, serialization, state transitions, registry, schema validation, availability, permissions, approval fingerprints, common-engine delegation, transaction/rollback outcomes, catalog, profile/composition integration, public API and forbidden dependency/effect boundaries. Every production behavior begins with an observed failing test. Focused suites precede the required subsystem and global suites, Ruff, Python 3.10 checks, compileall, diff checks, AST/import audits and full diff review.
