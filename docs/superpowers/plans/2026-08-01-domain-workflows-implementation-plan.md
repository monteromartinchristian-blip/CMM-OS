# Fase 10.14 — Domain Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` and execute each task task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not commit or push; the approved request requires an uncommitted working tree.

**Goal:** Implement a minimal domain-neutral `cmm.workflows` layer and a thin `cmm.domains` specialization for versioned, validated, resolvable and executable domain workflows.

**Architecture:** `cmm.workflows` owns immutable common contracts, separate availability/run statuses, pure graph validation, an in-memory order-independent registry, and a small adapter-driven engine. `cmm.domains` owns domain context, operation/resource/permission resolution, domain result provenance and the four declarative catalog workflows. Common code never imports `cmm.domains`.

**Tech Stack:** Python 3.10+, frozen slotted dataclasses, immutable JSON-safe mappings, protocols, pytest, Ruff.

---

## File Structure

- Create `cmm/workflows/__init__.py`, `enums.py`, `errors.py`, `contracts.py`, `graph.py`, `registry.py`, `engine.py`: the minimal common layer.
- Create `tests/workflows/test_contracts.py`, `test_graph.py`, `test_registry.py`, `test_engine.py`, `test_public_api.py`: isolated common-layer tests.
- Create `cmm/domains/workflow_contracts.py`, `workflow_errors.py`, `workflow_validation.py`, `workflow_registry.py`, `workflow_resolution.py`, `workflow_execution.py`, `workflow_catalog.py`: domain contracts and adapters.
- Create `tests/domains/test_domain_workflow_*.py`: focused domain tests and integration tests.
- Create `docs/reference/domain-workflows.md`: user-facing architecture and behavior documentation.
- Modify `cmm/domains/__init__.py` only for public exports and existing domain enum/error exports only when required by tests.
- Do not modify `cmm.agent_runtime` unless a failing test proves a domain-neutral generic gap that cannot be solved in adapters.

## Task 1: Common contracts and separated statuses

**Files:** `cmm/workflows/enums.py`, `cmm/workflows/errors.py`, `cmm/workflows/contracts.py`, `tests/workflows/test_contracts.py`.

- [ ] Write tests showing `WorkflowAvailabilityStatus` and `WorkflowRunStatus` are distinct, closed string enums and no availability value is accepted as a run status.
- [ ] Write tests for immutable JSON-safe `WorkflowNode`, `WorkflowDependency`, `WorkflowDefinition`, `WorkflowRun`, `WorkflowNodeResult`, `WorkflowResult`, `WorkflowEvent`, `WorkflowCheckpoint`, `WaitRequest`, `RetryPolicy`, `OperationReference` and `SubworkflowReference`.
- [ ] Write tests for unknown fields, NaN/Infinity, bool-as-number, callable values, naive datetimes, reversed timestamps, invalid status invariants and exact `to_dict()`/`from_dict()` round trips.
- [ ] Run `python -m pytest -q tests/workflows/test_contracts.py`; confirm the missing-package failure is the intended RED state.
- [ ] Implement only the fields used by 10.14, using recursive JSON validation and deep freezing. Keep domain IDs, profiles and rules out of all common types.
- [ ] Implement safe error codes/details without raw exception text and run the focused test file until GREEN.

## Task 2: Common graph validation

**Files:** `cmm/workflows/graph.py`, `tests/workflows/test_graph.py`.

- [ ] Write failing tests for duplicate node IDs, missing dependencies, duplicate dependencies, self-dependency, cycles, unreachable required nodes, terminal nodes with successors, operation nodes without operation references, subworkflow nodes without references, approval nodes without gates, wait nodes without conditions and invalid bindings.
- [ ] Add positive tests for a branching DAG, optional unreachable node where policy permits, and deterministic topological ready-node ordering.
- [ ] Run the focused graph tests and observe RED.
- [ ] Implement a pure validator using adjacency maps and deterministic DFS/topological traversal; it must not import registry, domain or runtime services.
- [ ] Run `python -m pytest -q tests/workflows/test_graph.py`; refactor only after GREEN.

## Task 3: Common registry and explicit global validation

**Files:** `cmm/workflows/registry.py`, `tests/workflows/test_registry.py`.

- [ ] Write failing tests for duplicate ID/version, SemVer ordering (`1.10.0 > 1.9.0`), active version, enable/disable, deterministic listing and neutral filters by node type/operation/subworkflow/metadata.
- [ ] Write tests proving registration never calls an adapter or handler and that domain fields are not required by common registration.
- [ ] Write tests proving A can register before B when A references B, `validate_registry()` succeeds after B is registered, and global cycle/self-reference checks fail only when explicitly invoked.
- [ ] Run RED, then implement an injected in-memory registry with no module discovery, filesystem access or domain imports.
- [ ] Run `python -m pytest -q tests/workflows/test_registry.py` and `python -m pytest -q tests/workflows`.

## Task 4: Common engine lifecycle and adapters

**Files:** `cmm/workflows/engine.py`, `tests/workflows/test_engine.py`.

- [ ] Write failing tests for pending→running, ready-node execution through an injected adapter, node result recording, completion, required-node failure, optional-node failure, event creation and output validation.
- [ ] Write tests for pause, resume without repeating completed nodes, waiting for input/resource/approval, cancel from pending/running/paused/waiting, rejection of cancel after completion, retry attempt limits, retryable classification, recovery requiring a checkpoint and rolled-back result state.
- [ ] Add spies that prove the engine never imports or invokes operation implementations, never sleeps, and uses injected clock/ID/checkpoint/approval/subworkflow adapters.
- [ ] Run RED; implement the smallest orchestration loop over common contracts. Keep side effects behind protocols and return new immutable run/result values.
- [ ] Run `python -m pytest -q tests/workflows/test_engine.py` and the complete isolated common suite.

## Task 5: Common public API and boundary audit

**Files:** `cmm/workflows/__init__.py`, `tests/workflows/test_public_api.py`.

- [ ] Write tests for individual imports, `__all__`, both import orders and absence of internal symbols from the public API.
- [ ] Add an AST/import test asserting no file under `cmm/workflows` imports `cmm.domains`, filesystem, subprocess, socket/http clients, LLM providers or persistence repositories.
- [ ] Implement only intentional public exports and run `python -m pytest -q tests/workflows`.

## Task 6: Domain workflow contracts and validation adapter

**Files:** `cmm/domains/workflow_contracts.py`, `cmm/domains/workflow_errors.py`, `cmm/domains/workflow_validation.py`, `tests/domains/test_domain_workflow_contracts.py`, `test_domain_workflow_validation.py`.

- [ ] Write failing tests for canonical workflow IDs, domain IDs, SemVer, schemas, permissions/resources, node declarations, approval gates, completion criteria, memory/session policies, strict unknown fields and deep immutability.
- [ ] Write tests proving domain run/result are thin wrappers/extensions over common `WorkflowRun`/`WorkflowResult`, use common `WorkflowRunStatus`, and preserve provenance without duplicating a state machine.
- [ ] Write tests for input/output schema validation using the existing common `validate_operation_schema` path and for invalid bindings/references.
- [ ] Run RED, implement minimal domain contracts and adapter errors with stable codes/details, then run focused tests.

## Task 7: Domain registry adapter and order-independent resolution

**Files:** `cmm/domains/workflow_registry.py`, `tests/domains/test_domain_workflow_registry.py`.

- [ ] Write failing tests for domain registration over the common registry, version activation, enabled/disabled definitions, deterministic domain-local filters, duplicate rejection and no execution during registration.
- [ ] Write tests that domain-specific filtering handles primary/supporting domains while common registry remains unaware of them.
- [ ] Write tests that operation/subworkflow existence is checked at resolution time, not registration time, and that registration order does not change outcomes.
- [ ] Implement the adapter over the common registry; expose explicit `validate_registry()` delegation for global workflow cycles.
- [ ] Run the domain registry tests and both common/domain registry suites.

## Task 8: Domain resolution, permissions, resources and approvals

**Files:** `cmm/domains/workflow_resolution.py`, `tests/domains/test_domain_workflow_resolution.py`, `test_domain_workflow_approval.py`.

- [ ] Write failing tests for enabled/disabled, primary/supporting domain compatibility, missing required resources, allow/missing/deny+allow permissions, optional unavailable operations, required unavailable operations, pending/approved/denied/expired approvals and cross-domain authorization.
- [ ] Write tests proving deny-wins, supporting domains never add permissions, no auto-approval, no profile/composition re-resolution and deterministic reasons/traces.
- [ ] Implement a pure resolver consuming already-resolved `DomainComposition`, `ResolvedDomainProfile`, operation registry, effective permissions/resources and injected capabilities.
- [ ] Run focused tests and check `cmm.workflows` remains domain-free.

## Task 9: Domain execution adapter and result aggregation

**Files:** `cmm/domains/workflow_execution.py`, `tests/domains/test_domain_workflow_execution.py`.

- [ ] Write failing tests proving the domain orchestrator validates input, resolves availability, instantiates a common run and delegates execution through `WorkflowEngine` exactly once.
- [ ] Add an operation spy proving `execute_operation` reaches only the existing 10.13 orchestrator/adapter and never calls a registered implementation directly.
- [ ] Cover successful output, invalid output, approval wait/denial, input wait, resource wait, cancellation, required/optional node failures, sanitized operational errors and propagation of programming/contract errors.
- [ ] Implement only translation/coordination; keep transaction, approval, checkpoint and recovery behavior in injected/common services.
- [ ] Run the focused domain execution suite and common engine suite.

## Task 10: Subworkflows, cross-domain behavior and completion criteria

**Files:** `cmm/domains/workflow_resolution.py`, `workflow_execution.py`, `tests/domains/test_domain_workflow_subworkflows.py`, `test_domain_workflow_cross_domain.py`, `test_domain_workflow_completion.py`.

- [ ] Write failing tests for valid/missing/version-invalid subworkflows, A→B→A cycles, self-reference, maximum depth, input/output mapping, parent/root IDs, parent cancellation, required/optional child failure and permission intersection.
- [ ] Write tests for primary/supporting domains, authorized/unauthorized supporting operations, explicit cross-domain subworkflow authorization, deny-wins and provenance preservation.
- [ ] Write tests for all required completion criteria and rejection of completion with pending approval, unresolved resource, failed required node, invalid output or unfinished required subworkflow.
- [ ] Implement deterministic checks using the common registry and engine adapters; do not add a second engine or future permission request system.
- [ ] Run all focused domain workflow tests.

## Task 11: Four-workflow catalog

**Files:** `cmm/domains/workflow_catalog.py`, `tests/domains/test_domain_workflow_catalog.py`.

- [ ] Write failing tests asserting the four exact IDs and their declared node sequences, required/optional flags and references.
- [ ] Write tests that catalog registration performs no filesystem, subprocess, network, LLM, memory write, calendar write, task creation, diagnosis or code modification.
- [ ] Implement declarative definitions only. Nodes without injected capability resolve to `unavailable`, `waiting` or `not_applicable`; no implementation claims deep work succeeded.
- [ ] Run the catalog suite and boundary audit.

## Task 12: Documentation and verification

**Files:** `docs/reference/domain-workflows.md`, all new/modified files.

- [ ] Write focused documentation tests only if the repository's documentation checks require them; otherwise document architecture, ownership, contracts, registry, graph, resolution, lifecycle, adapters, waits, approvals, recovery, subworkflows, cross-domain behavior, completion criteria, catalog and deliberate limits.
- [ ] Run focused suites:

```bash
python -m pytest -q tests/workflows
python -m pytest -q tests/domains
```

- [ ] Run available subsystem suites, documenting nonexistent paths: `tests/planning`, `tests/execution`, `tests/cognitive`, `tests/validation`, `tests/agent_runtime`.
- [ ] Run the full suite: `python -m pytest -q`.
- [ ] Run Ruff on all changed Python files with `python -m ruff check --target-version py310 <changed-files>`.
- [ ] Run `python -m compileall -q cmm tests` and `git diff --check`.
- [ ] Run AST/grep audits for forbidden imports/effects, dynamic imports, mutable singletons, broad catches, `BaseException`, public `str(exc)`/`repr(exc)`, `eval`/`exec`, TODO/FIXME, chain-of-thought and generated artifacts.
- [ ] Review the complete diff, list files and ownership, verify no commit/push/branch/history mutation, and record `git status --short`.

## Verification checklist

- [ ] Common layer has no `cmm.domains` import.
- [ ] Availability status and run status are separate types and machines.
- [ ] Registry filters are domain-neutral; domain filters live in `cmm.domains`.
- [ ] Registration order does not affect resolution; global validation is explicit.
- [ ] Domain run/result use common state/result as source of truth.
- [ ] Operations execute only through the 10.13 adapter path.
- [ ] No persistence, scheduler, API, CLI, workers, queues, network, subprocess, LLM or external communication was added.
- [ ] No commit, push, merge, rebase, branch switch or history rewrite was performed.
