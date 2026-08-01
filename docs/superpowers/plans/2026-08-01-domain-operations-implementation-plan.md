# Phase 10.13 Domain Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` and execute each task inline. Steps use checkbox (`- [ ]`) syntax for tracking. Do not commit or push; the implementation brief requires an uncommitted audited working tree.

**Goal:** Implement strict domain-specialized operation registration, availability and execution through the existing Agent Runtime operational path, with 20 conservative catalog definitions.

**Architecture:** `cmm.domains` owns serializable domain contracts, a registry adapter, pure availability resolution and a coordinating orchestrator. The orchestrator delegates execution exclusively to an injected `AgentExecutionAdapter` and coordinates existing approval, validation, transaction and rollback services without duplicating them; common changes are permitted only when fully domain-neutral.

**Tech Stack:** Python 3.10+, frozen slotted dataclasses, runtime-checkable protocols, `MappingProxyType`, existing Agent Runtime contracts, pytest, Ruff.

---

## File Structure

- Create `cmm/domains/operation_contracts.py`: strict serializable contracts, structural implementation boundary, state transitions and common descriptor/request mapping.
- Create `cmm/domains/operation_registry.py`: adapter over injected `AgentOperationRegistry`, implementation isolation, SemVer resolution and deterministic queries.
- Create `cmm/domains/operation_schema.py`: domain-facing adapter to the reusable common schema validator; no independent schema engine.
- Create `cmm/domains/operation_availability.py`: pure availability/permission/approval resolver.
- Create `cmm/domains/operation_execution.py`: coordination-only orchestrator that delegates to `AgentExecutionAdapter`.
- Create `cmm/domains/operation_catalog.py`: 20 conservative definitions and pure common-delegate implementations.
- Modify `cmm/domains/enums.py`, `errors.py`, `__init__.py`: public Phase 10.13 enums, errors and exports.
- Modify common Agent Runtime files only if RED tests prove a generic gap: operation schema validation, typed operational failures and generic output transport.
- Create focused `tests/domains/test_domain_operation_*.py` modules for every required area.
- Create `docs/reference/domain-operations.md` after behavior is green.

### Task 1: Enums, errors and state transitions

- [ ] Add failing tests for all operation types, lifecycle states, valid transitions, invalid transitions and the requested error hierarchy/codes.
- [ ] Run the focused tests and confirm missing symbols are the expected RED failure.
- [ ] Add strict enums and typed errors using existing `DomainError` safe-detail behavior; implement a pure transition validator.
- [ ] Run focused tests and Ruff; keep all tests green before continuing.

### Task 2: Definition, request and context contracts

- [ ] Add failing tests for canonical IDs, strict SemVer, strict enums/bools, risk/reversibility/approval invariants, immutable schemas/metadata, JSON safety, unknown fields and exact round trips.
- [ ] Add failing tests integrating real `DomainComposition`, `ResolvedDomainProfile`, `PermissionComposition` and session/provenance fields without invoking their resolvers.
- [ ] Verify RED, implement minimal frozen contracts and deterministic conversion to `OperationDescriptor`/`AgentOperationRequest`, then verify GREEN.

### Task 3: Result, trace, event, error and rollback contracts

- [ ] Add failing tests for typed sanitized errors, trace/event ordering, timezone-aware timestamps, result ID/version matching, output/findings/knowledge/memory proposals, transaction/approval references and rollback results.
- [ ] Cover naive timestamps, reversed times, mutable nested values, NaN/Infinity, callable values and unknown serialized fields.
- [ ] Verify RED, implement strict contracts and nested round trips, then verify GREEN and Ruff.

### Task 4: Reusable operation-schema validation

- [ ] Add failing common-layer tests for object/property/required/additionalProperties handling, structured paths, missing versus null, nested arrays/objects, bool-as-number rejection and non-finite values.
- [ ] Verify the existing registry validator fails only for the missing generic behavior.
- [ ] Implement or extract a domain-neutral validator in `cmm.agent_runtime`; make `InMemoryAgentOperationRegistry.validate_request` use it without changing its public boolean/exception contract.
- [ ] Add the thin domain adapter, run Agent Runtime plus domain schema suites, and verify no common import points to `cmm.domains`.

### Task 5: Domain registry adapter

- [ ] Add failing tests for registration without execution, signature validation, atomic duplicate rejection, exact/active versions, `1.10.0 > 1.9.0`, enable/disable, deterministic listings and filters.
- [ ] Test definition-only serialization, isolated implementations, two domains with homonymous operations and independent registry instances.
- [ ] Verify RED; implement the adapter over injected `AgentOperationRegistry` using the existing SemVer parser; verify GREEN.

### Task 6: Pure availability and permission resolution

- [ ] Add failing tests for disabled, missing resources, incompatible primary/supporting domain, permission allow/missing/deny/allow+deny, extra permissions, sensitive/destructive policy, external capability, validation, transaction and rollback support.
- [ ] Add exact status/reason/permission/resource/policy/trace serialization assertions and deterministic ordering.
- [ ] Verify RED; implement the pure resolver with deny-wins precedence and no service mutation; verify GREEN.

### Task 7: Approval binding

- [ ] Add failing tests for no approval, pending, approved, denied, expired and mismatched operation/version/input/context fingerprints.
- [ ] Test destructive operations always wait for explicit approval and no approval is granted automatically.
- [ ] Verify RED; implement deterministic approval requirements/fingerprints using `ApprovalRequest`/`ApprovalService` adapters; verify GREEN.

### Task 8: Common execution output and controlled-error boundary

- [ ] Add failing Agent Runtime tests proving generic JSON-safe delegate output survives in `AgentOperationExecutionResult`, controlled operational failures normalize and programming/contract errors propagate.
- [ ] Verify RED against current broad delegate normalization.
- [ ] Add only domain-neutral result/error fields and narrow exception handling while preserving existing successful execution behavior and explicit legacy operational-error expectations.
- [ ] Run the full operation-execution adapter suite and Ruff.

### Task 9: Coordination-only domain execution

- [ ] Add failing tests proving the orchestrator resolves/validates/coordinates and calls `AgentExecutionAdapter.execute` exactly once while never obtaining or invoking the implementation.
- [ ] Cover unregistered, input invalid, unavailable, blocked, approval pending/denied, cancellation, common result mismatch, invalid return type, output invalid and successful output.
- [ ] Verify RED; implement minimal orchestration and common request/result mapping; verify GREEN.

### Task 10: Transactions and rollback

- [ ] Add failing tests for read without transaction, reversible transaction start/register/commit, failure before execution, execution failure, invalid output, successful rollback, failed rollback, irreversible execution and cancellation.
- [ ] Assert successful rollback ends `rolled_back`; failed rollback preserves both typed failures and never reports completion.
- [ ] Verify RED; coordinate only injected `TransactionManager`, rollback policy/evaluator and restoration port; verify GREEN.

### Task 11: Initial catalog

- [ ] Add failing tests for exactly the 20 requested IDs, canonical domains/types/risks, unique versions, safe schemas and conservative enabled states.
- [ ] Add tests that executable demonstrations are pure/deterministic and that capability-dependent entries are unavailable/not-applicable or disabled rather than false successes.
- [ ] Verify RED; implement the catalog and explicit registration builder; verify GREEN.

### Task 12: Profile/composition/rule integration

- [ ] Add failing end-to-end tests for already-resolved `ResolvedDomainProfile` and `DomainComposition`, primary/supporting domains, composed permissions, operation provenance and selected-rule references.
- [ ] Assert profile resolver, composer and rule executor are never called by operation resolution/execution.
- [ ] Verify RED; add only mapping logic to the existing context/availability/orchestration components; verify GREEN.

### Task 13: Public API and boundaries

- [ ] Add failing tests for individual imports, `__all__`, internal exclusions, both import orders and Python 3.10-compatible syntax.
- [ ] Add AST/import boundary tests excluding common-to-domain imports, filesystem, network, subprocess, LLM, persistence, direct memory writes, mutable singletons, broad catches and direct implementation execution.
- [ ] Update `cmm.domains.__init__` exports and verify focused boundary suites.

### Task 14: Reference documentation

- [ ] Write `docs/reference/domain-operations.md` from the green public behavior, covering ownership, contracts, registry, availability, schemas, permissions, approvals, transactions, rollback, catalog, profile/composition integration, examples and deliberate limits.
- [ ] Search documentation for claims not backed by tests and remove them.

### Task 15: Focused and regression validation

- [ ] Run every new Phase 10.13 focused module and fix failures.
- [ ] Run `tests/cognitive`, `tests/domains`, `tests/operations` if present, `tests/execution`, `tests/validation` and `tests/agent_runtime`; record absent paths.
- [ ] Run the global pytest suite and separate any pre-existing failures from Phase 10.13 regressions.
- [ ] Run Ruff on all changed files and `--target-version py310` on new files, then compileall and `git diff --check`.

### Task 16: Security, architecture and final audit

- [ ] Run import/AST searches for forbidden dependencies and effects, broad catches, exception leakage, TODO/FIXME/pass, temporary artifacts and bytecode.
- [ ] Run `graphify update .`, then review the complete diff and every created/modified file for Phase 10.13 ownership.
- [ ] Recheck round trips, state transitions, permissions, approval, transactions, rollback, conservative catalog behavior and future-phase boundaries.
- [ ] Run `git status --short`, confirm the branch/HEAD are unchanged and report explicitly that no commit, push, merge, rebase or branch change occurred.
