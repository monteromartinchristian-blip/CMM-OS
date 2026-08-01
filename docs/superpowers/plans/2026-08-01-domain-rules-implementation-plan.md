# Phase 10.12 Domain Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and execute each task inline. Steps use checkbox (`- [ ]`) syntax for tracking. Do not commit or push; the implementation brief explicitly requires an uncommitted audit state.

**Goal:** Build one common cognitive rule registry and deterministic domain rule selection/execution pipeline that consumes Phase 10.11 profiles and preserves Phase 10.8 domain precedence.

**Architecture:** Common executable contracts, registry and explicit-sequence engine live in `cmm.cognitive`; domain definitions/results specialize those contracts and pure services turn an already-resolved profile into an immutable plan and execute it. All state, clocks, IDs, registries and permissions are explicit inputs; outputs are strict serialized audit records.

**Tech Stack:** Python 3.10+, frozen slotted dataclasses, runtime-checkable protocols, `MappingProxyType`, pytest, Ruff.

---

## Files

Create `cmm/cognitive/reasoning_rule_contracts.py`, `reasoning_rule_registry.py`, `reasoning_rule_engine.py`; create `cmm/domains/rule_contracts.py`, `rule_selection.py`, `rule_execution.py`, `rule_catalog.py`; update both error/enum/public API modules. Add the cognitive and domain test modules required by the brief and update existing public API tests.

### Task 1: Cognitive enums and errors

- [ ] Add failing tests for exact scope/category/status/result/risk/severity values and the five-error hierarchy/codes.
- [ ] Run the focused tests and verify missing imports are the expected RED failure.
- [ ] Add enums to `cmm/cognitive/enums.py` and typed errors to `cmm/cognitive/errors.py`; export them.
- [ ] Run focused tests and Ruff.

### Task 2: Common definition and audit element contracts

- [ ] Test canonical IDs, strict SemVer, scope/domain invariants, strict bounded integer priority, unique permissions, strict bool, finite values and JSON-safe metadata.
- [ ] Test `ReasoningFinding`, `ReasoningRecommendation`, `ReasoningEscalation`, `ReasoningGap` and `ReasoningRuleTraceEntry`, including strict `to_dict`/`from_dict`, field paths and deep immutability.
- [ ] Verify RED, implement minimal frozen slotted contracts in `reasoning_rule_contracts.py`, then verify GREEN.

### Task 3: Context and result contracts

- [ ] Test immutable `ReasoningRuleContext` using real `KnowledgeItem`/`Contradiction`, aware timestamps, domain alignment and explicit permissions.
- [ ] Test all result statuses, timestamps/duration, bounded confidence delta, typed outputs, exact round trip and result invariants.
- [ ] Verify RED; implement context/result/protocol and strict nested serialization; verify GREEN and Ruff.

### Task 4: Common registry

- [ ] Test runtime protocol, operational implementation validation, no evaluation during registration, duplicate/collision behavior, enabled/disabled versions, semantic active resolution, unregister/get/filter/list/inspect order, tuple isolation and independent instances.
- [ ] Verify RED; implement `ReasoningRuleRegistry` and `InMemoryReasoningRuleRegistry` keyed by ID/version with no domain import; verify GREEN.

### Task 5: Common engine

- [ ] Test explicit ordered execution, same context identity, applied/not-applicable results, controlled failure normalization, contract errors propagation and ID/name/version/domain mismatch rejection.
- [ ] Verify RED; implement `ReasoningRuleEngine`/`DefaultReasoningRuleEngine` without hidden registry or broad catch; verify GREEN.

### Task 6: Domain enums, errors and specializations

- [ ] Test exact selection/execution/source/decision/conflict enums and six domain errors/codes.
- [ ] Test `DomainReasoningRuleDefinition` and `DomainRuleResult` remain instances of common contracts and require a canonical domain.
- [ ] Verify RED; implement domain enums/errors and thin validating subclasses in `rule_contracts.py`; verify GREEN.

### Task 7: Selection contracts

- [ ] Test `DomainRuleSelectionPolicy`, source provenance, decision/conflict, selected rule and execution plan validation/serialization/status invariants.
- [ ] Cover unknown fields, duplicate IDs, tuples, aware datetimes, JSON safety, IDs/factories, missing permissions and blocked/omitted projections.
- [ ] Verify RED; implement contracts in `rule_contracts.py`; verify GREEN.

### Task 8: Pure selector and 10.11 integration

- [ ] Test required/optional/prohibited, missing/disabled/domain mismatch/permissions, fixed versions, global mandatory preservation, optional partial behavior and required conflicts.
- [ ] Test full group/priority/primary/supporting order, provenance-preserving deduplication, overlays already reflected by `ResolvedDomainProfile`, requested IDs, deterministic clock/ID and no profile-registry access.
- [ ] Verify RED; implement `DomainRuleSelector`/`DefaultDomainRuleSelector` in `rule_selection.py`, accepting `DomainComposition` only as already-composed provenance/order; verify GREEN.

### Task 9: Domain execution contracts and executor

- [ ] Test aggregate contract serialization, status invariants and ordered aggregation.
- [ ] Test blocked plans execute nothing; required failure stops; optional failure continues partial; not-applicable continues; empty/all-not-applicable yields `no_applicable_rules`; deltas clamp; traces and outputs preserve order.
- [ ] Test registry/plan/result mismatch, context non-mutation, no out-of-plan rules and injected clock/IDs.
- [ ] Verify RED; implement `DomainRuleExecutionPolicy`, result and `DomainRuleExecutor`/`DefaultDomainRuleExecutor`; verify GREEN.

### Task 10: Initial catalog

- [ ] Test all specified IDs and metadata, disabled conservative future-pack definitions, and enabled global/security reference implementations.
- [ ] Test reference behavior for global, security, primary/supporting, optional, not-applicable, gap, escalation and permission-blocked paths without free-text inference.
- [ ] Verify RED; implement deterministic catalog definitions/implementations and explicit `build_initial_reasoning_rule_catalog()` registration; verify GREEN.

### Task 11: Public APIs and boundaries

- [ ] Add failing tests for public symbols, internal exclusions, both import orders and `cmm.cognitive` source/import graph lacking `cmm.domains`.
- [ ] Add boundary tests excluding Agent Runtime, operations, workflows, I/O, subprocess, LLM, persistence, global registries, broad catches and exception leakage.
- [ ] Update `__init__.py` exports in deterministic sorted order and verify focused tests.

### Task 12: Integration and regression

- [ ] Add end-to-end tests combining one registry, global/security/domain rules, a real `ResolvedDomainProfile` and a real 10.8 `DomainComposition` without invoking their resolvers/composer.
- [ ] Cover all 16 profile integration and 10.8 precedence/provenance cases from the brief.
- [ ] Run all new Phase 10.12 tests, then `tests/cognitive`, `tests/domains`, `tests/validation`, `tests/agent_runtime`.

### Task 13: Documentation and audit

- [ ] Update technical/reference documentation only where public rule contracts need discovery.
- [ ] Run global pytest, scoped/global Ruff, compileall, `git diff --check`, Python 3.10 syntax/API review and `graphify update .`.
- [ ] Run required defect searches; inspect every hit and remove accidental artifacts.
- [ ] Review full diff, inventory each changed file, build the requirement/implementation/test/status audit table and confirm no commit/push occurred.
