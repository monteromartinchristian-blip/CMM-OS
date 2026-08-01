# Phase 10.10 Domain Resources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a declarative Domain Resources layer that registers resource definitions, resolves one shared resource into several domain bindings, preserves provenance and derivation lineage, and never widens permissions or lowers sensitivity.

**Architecture:** Phase 10.10 wraps the common Cognitive Layer resource concepts with strict domain-specific definitions, bindings, registry lookup, deterministic resolution and derivation validation. Adapters remain declarative; no payload storage, external I/O, persistence or Knowledge Graph mutation is introduced.

**Tech Stack:** Python 3.10+, frozen slotted dataclasses, protocols, `MappingProxyType`, pytest, Ruff.

## Global Constraints

- Base commit: `790928b`.
- Branch: `feature/phase-10-domain-intelligence`.
- Reuse common resource concepts; do not create a second payload-bearing `Resource`.
- No adapter execution.
- No filesystem, network, persistence, OCR, embeddings, vector stores, events or Knowledge Graph mutation.
- No runtime actor authorization.
- No semantic deduplication.
- No broad `except Exception`.
- No public `str(exc)` or `repr(exc)` leakage.
- Strict serialization, deep immutability and deterministic ordering.
- No commit or push until audit approval.

---

## File Structure

Create:

- `cmm/domains/resource_contracts.py` — immutable public contracts, strict validation and serialization.
- `cmm/domains/resource_registry.py` — registry protocol and deterministic in-memory implementation.
- `cmm/domains/resource_resolver.py` — validator protocol/default implementation and deterministic resolver.
- `cmm/domains/resource_derivation.py` — derivation validation service.

Modify:

- `cmm/domains/enums.py` — resource statuses, decisions and validation severity.
- `cmm/domains/errors.py` — resource error hierarchy.
- `cmm/domains/__init__.py` — public exports.
- `tests/domains/test_domain_public_api.py` — aggregate export guard.

Create tests:

- `tests/domains/test_domain_resource_contracts.py`
- `tests/domains/test_domain_resource_serialization.py`
- `tests/domains/test_domain_resource_registry.py`
- `tests/domains/test_domain_resource_resolver.py`
- `tests/domains/test_domain_resource_derivation.py`
- `tests/domains/test_domain_resource_public_api.py`
- `tests/domains/test_domain_resource_boundaries.py`

---

### Task 1: Resource enums and errors

**Files:**
- Modify: `cmm/domains/enums.py`
- Modify: `cmm/domains/errors.py`
- Test: `tests/domains/test_domain_resource_contracts.py`

**Interfaces:**
- Produces: `DomainResourceResolutionStatus`, `DomainResourceDecisionCode`, `DomainResourceValidationSeverity`.
- Produces: `DomainResourceError`, `DomainResourceContractError`, `DomainResourceSerializationError`, `DomainResourceConfigurationError`, `DomainResourceRegistryError`, `DomainResourceResolutionError`, `DomainResourceDerivationError`.

- [ ] Write failing tests for exact enum values, coercion rejection, hierarchy and stable error codes.
- [ ] Run focused tests and confirm failure.
- [ ] Implement the enum and error definitions following existing domain patterns.
- [ ] Run focused tests and Ruff.

---

### Task 2: Temporal policy, validation rule and checksum contracts

**Files:**
- Create: `cmm/domains/resource_contracts.py`
- Test: `tests/domains/test_domain_resource_contracts.py`
- Test: `tests/domains/test_domain_resource_serialization.py`

**Interfaces:**
- Produces:
  - `DomainResourceTemporalPolicy`
  - `DomainResourceValidationRule`
  - `DomainResourceValidationResult`
  - `DomainResourceChecksum`

- [ ] Write failing invariant tests for strict booleans, positive validity windows, explicit validation operators, finite values and checksum algorithms.
- [ ] Write failing strict serialization tests, including unknown-field rejection and nested field paths.
- [ ] Implement immutable slotted dataclasses with `to_dict()` and `from_dict()`.
- [ ] Reject arbitrary expressions, callables and unsupported operators.
- [ ] Run focused tests and Ruff.

---

### Task 3: Definition and context contracts

**Files:**
- Extend: `cmm/domains/resource_contracts.py`
- Test: `tests/domains/test_domain_resource_contracts.py`
- Test: `tests/domains/test_domain_resource_serialization.py`

**Interfaces:**
- Produces:
  - `DomainResourceDefinition`
  - `DomainResourceContext`

- [ ] Write failing tests for canonical IDs, unique entity types and permissions, source priority, reliability, sensitivity, provenance and JSON-safe metadata.
- [ ] Test that `DomainResourceContext` is not payload-bearing and requires provenance.
- [ ] Test strict round trips and no implicit type coercion.
- [ ] Implement both contracts with deep freeze.
- [ ] Run focused tests and Ruff.

---

### Task 4: Binding, rejection, decision and resolution contracts

**Files:**
- Extend: `cmm/domains/resource_contracts.py`
- Test: `tests/domains/test_domain_resource_contracts.py`
- Test: `tests/domains/test_domain_resource_serialization.py`

**Interfaces:**
- Produces:
  - `DomainResourceBinding`
  - `DomainResourceRejection`
  - `DomainResourceDecision`
  - `DomainResourceResolution`

- [ ] Write failing tests for no payload duplication, binding provenance, restrictive permissions, sensitivity monotonicity and status invariants.
- [ ] Test `RESOLVED`, `PARTIAL`, `BLOCKED`, `REJECTED` and `FAILED` invariants.
- [ ] Test deterministic tuple normalization and strict serialization.
- [ ] Implement the contracts.
- [ ] Run focused tests and Ruff.

---

### Task 5: Derivation contract

**Files:**
- Extend: `cmm/domains/resource_contracts.py`
- Test: `tests/domains/test_domain_resource_derivation.py`
- Test: `tests/domains/test_domain_resource_serialization.py`

**Interfaces:**
- Produces: `DomainResourceDerivation`.

- [ ] Write failing tests for distinct source/derived IDs, actor, transformation, version, aware timestamps, checksum and provenance.
- [ ] Test strict serialization and unknown fields.
- [ ] Implement the immutable contract.
- [ ] Run focused tests and Ruff.

---

### Task 6: Registry protocol and implementation

**Files:**
- Create: `cmm/domains/resource_registry.py`
- Test: `tests/domains/test_domain_resource_registry.py`

**Interfaces:**
- Produces:
  - `DomainResourceRegistry`
  - `InMemoryDomainResourceRegistry`

```python
class DomainResourceRegistry(Protocol):
    def register(
        self,
        definition: DomainResourceDefinition,
    ) -> DomainResourceDefinition: ...

    def get(
        self,
        definition_id: str,
    ) -> DomainResourceDefinition | None: ...

    def find_by_kind(
        self,
        kind: str,
    ) -> tuple[DomainResourceDefinition, ...]: ...

    def find_by_domain(
        self,
        domain_id: DomainId,
    ) -> tuple[DomainResourceDefinition, ...]: ...

    def list_all(self) -> tuple[DomainResourceDefinition, ...]: ...
```

- [ ] Write failing runtime-checkable protocol tests.
- [ ] Write failing tests for duplicate IDs, same kind across domains and immutable return values.
- [ ] Test exact deterministic ordering for each query.
- [ ] Implement without persistence or adapter loading.
- [ ] Run focused tests and Ruff.

---

### Task 7: Declarative validator

**Files:**
- Create: `cmm/domains/resource_resolver.py`
- Test: `tests/domains/test_domain_resource_resolver.py`

**Interfaces:**
- Produces:
  - `DomainResourceValidator`
  - `DefaultDomainResourceValidator`

```python
class DomainResourceValidator(Protocol):
    def validate(
        self,
        *,
        context: DomainResourceContext,
        definition: DomainResourceDefinition,
    ) -> tuple[DomainResourceValidationResult, ...]: ...
```

- [ ] Write failing tests for `exists`, `equals`, `not_equals`, `contains`, `in`, `minimum` and `maximum`.
- [ ] Test missing fields, incompatible observed types and unsupported operators.
- [ ] Test warning/error/blocking behavior.
- [ ] Implement field lookup only over explicit context fields and metadata; no arbitrary expression evaluation.
- [ ] Run focused tests and Ruff.

---

### Task 8: Permission, sensitivity and temporal helpers

**Files:**
- Extend: `cmm/domains/resource_resolver.py`
- Test: `tests/domains/test_domain_resource_resolver.py`

**Interfaces:**
- Produces private deterministic helpers for:
  - permission intersection;
  - explicit deny precedence;
  - sensitivity maximum;
  - temporal policy evaluation;
  - source-priority ordering.

- [ ] Write failing tests proving definitions never widen permissions.
- [ ] Test empty permission sets conservatively.
- [ ] Test explicit deny precedence.
- [ ] Test sensitivity can rise but not fall.
- [ ] Test effective date, expiration, staleness, validity window and historical use.
- [ ] Implement using injected clock only.
- [ ] Run focused tests and Ruff.

---

### Task 9: Resolver protocol and default resolver

**Files:**
- Extend: `cmm/domains/resource_resolver.py`
- Test: `tests/domains/test_domain_resource_resolver.py`

**Interfaces:**
- Produces:
  - `DomainResourceResolver`
  - `DefaultDomainResourceResolver`

```python
class DomainResourceResolver(Protocol):
    def resolve(
        self,
        *,
        context: DomainResourceContext,
        definitions: tuple[DomainResourceDefinition, ...],
        requested_domains: tuple[DomainId, ...],
        request_permissions: tuple[str, ...],
    ) -> DomainResourceResolution: ...
```

- [ ] Write failing tests for matching kind, requested-domain filtering and applicable-domain hints.
- [ ] Test shared resource bindings without resource duplication.
- [ ] Test non-shareable definitions across several domains.
- [ ] Test permission denial, sensitivity restriction, temporal failure and blocking validation.
- [ ] Test source priority and reliability.
- [ ] Test deterministic decisions, rejections and binding order.
- [ ] Test status derivation.
- [ ] Implement the full resolution flow without registry access.
- [ ] Run focused tests and Ruff.

---

### Task 10: Derivation service

**Files:**
- Create: `cmm/domains/resource_derivation.py`
- Test: `tests/domains/test_domain_resource_derivation.py`

**Interfaces:**
- Produces: `DomainResourceDerivationService`.

```python
class DomainResourceDerivationService:
    def record(
        self,
        *,
        derivation: DomainResourceDerivation,
        source_permissions: tuple[str, ...],
        source_sensitivity: Sensitivity,
    ) -> DomainResourceDerivation: ...
```

- [ ] Write failing tests for permission narrowing and sensitivity monotonicity.
- [ ] Test complete lineage retention and checksum preservation.
- [ ] Test no payload, persistence or source fetch.
- [ ] Implement validation and canonical return only.
- [ ] Run focused tests and Ruff.

---

### Task 11: Public API and boundaries

**Files:**
- Modify: `cmm/domains/__init__.py`
- Modify: `tests/domains/test_domain_public_api.py`
- Create: `tests/domains/test_domain_resource_public_api.py`
- Create: `tests/domains/test_domain_resource_boundaries.py`

**Interfaces:**
- Exports all Phase 10.10 public contracts, protocols, implementations and errors.

- [ ] Add exact public API tests.
- [ ] Assert fake adapters and internal helpers are not exported.
- [ ] Assert no imports or direct use of filesystem, network, OCR, embeddings, vector stores, Knowledge Graph mutation or adapter execution.
- [ ] Assert no broad exception handling.
- [ ] Assert prior Phase 10 APIs remain stable.
- [ ] Run focused API and boundary tests.

---

### Task 12: Full verification and audit

**Files:**
- All Phase 10.10 files.

- [ ] Format and lint only Phase 10.10 files.
- [ ] Scan for forbidden test patterns and broad exception handling.
- [ ] Run focused Domain Resources tests.
- [ ] Run all domain tests.
- [ ] Run validation tests.
- [ ] Run the global suite.
- [ ] Run `compileall`.
- [ ] Run `git diff --check`.
- [ ] Confirm only expected files changed.
- [ ] Create `/Users/chris/Desktop/phase-10.10-audit.tar.gz`.
- [ ] Stop before commit and push.

## Verification Commands

```zsh
cd "/Users/chris/CMM OS"

PHASE_1010_FILES=(
  cmm/domains/resource_contracts.py
  cmm/domains/resource_registry.py
  cmm/domains/resource_resolver.py
  cmm/domains/resource_derivation.py
  cmm/domains/enums.py
  cmm/domains/errors.py
  cmm/domains/__init__.py
  tests/domains/test_domain_resource_contracts.py
  tests/domains/test_domain_resource_serialization.py
  tests/domains/test_domain_resource_registry.py
  tests/domains/test_domain_resource_resolver.py
  tests/domains/test_domain_resource_derivation.py
  tests/domains/test_domain_resource_public_api.py
  tests/domains/test_domain_resource_boundaries.py
  tests/domains/test_domain_public_api.py
)

python -m ruff format "${PHASE_1010_FILES[@]}"
python -m ruff check "${PHASE_1010_FILES[@]}"
python -m ruff format --check "${PHASE_1010_FILES[@]}"

if rg -n 'pytest\.raises\(Exception\)|^\s*pass$' \
  tests/domains/test_domain_resource_*.py; then
  echo "FORBIDDEN TEST PATTERN FOUND"
  exit 1
else
  echo "NO FORBIDDEN TEST PATTERNS"
fi

if rg -n 'except Exception|str\(exc\)|repr\(exc\)' \
  cmm/domains/resource_*.py; then
  echo "FORBIDDEN EXCEPTION PATTERN FOUND"
  exit 1
else
  echo "NO FORBIDDEN EXCEPTION PATTERNS"
fi

python -m pytest tests/domains/test_domain_resource_*.py -q
python -m pytest tests/domains -q
python -m pytest tests/validation -q
python -m pytest -q

python -m compileall -q cmm/domains tests/domains
git diff --check
git diff --stat
git diff --numstat
git status --short
```

## Audit Archive

```bash
COPYFILE_DISABLE=1 tar \
  --exclude='._*' \
  -czf "/Users/chris/Desktop/phase-10.10-audit.tar.gz" \
  cmm/domains/resource_contracts.py \
  cmm/domains/resource_registry.py \
  cmm/domains/resource_resolver.py \
  cmm/domains/resource_derivation.py \
  cmm/domains/enums.py \
  cmm/domains/errors.py \
  cmm/domains/__init__.py \
  tests/domains/test_domain_resource_contracts.py \
  tests/domains/test_domain_resource_serialization.py \
  tests/domains/test_domain_resource_registry.py \
  tests/domains/test_domain_resource_resolver.py \
  tests/domains/test_domain_resource_derivation.py \
  tests/domains/test_domain_resource_public_api.py \
  tests/domains/test_domain_resource_boundaries.py \
  tests/domains/test_domain_public_api.py
```

## Self-Review

- Spec coverage: definitions, shared bindings, registry, resolver, permissions, sensitivity, temporality, source priority, reliability, validators, derivation lineage and boundaries are assigned.
- Placeholder scan: no deferred requirements remain.
- Type consistency: resolver, validator, registry and derivation signatures use the contracts defined in earlier tasks.
- Scope: adapter execution, persistence, I/O, ingestion, OCR, embeddings, vector stores, events, Knowledge Graph mutation and Domain Profiles remain excluded.
