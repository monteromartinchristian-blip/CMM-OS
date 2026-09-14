# Phase 10.11 Domain Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement declarative Domain Profiles that compose global, primary, supporting and contextual constraints into one immutable, monotonic and fully audited resolved profile without executing cognitive logic.

**Architecture:** Phase 10.11 provides strict contracts, a deterministic in-memory registry, a pure composition engine and a resolver that validates contextual relevance, generates IDs/timestamps and returns a `DomainProfileResolution`. Typed policy objects merge through explicit monotonic rules; no generic dictionary merge or rule execution is allowed.

**Tech Stack:** Python 3.10+, frozen slotted dataclasses, protocols, `MappingProxyType`, pytest, Ruff.

## Global Constraints

- Base commit: `ae937ef`.
- Branch: `feature/phase-10-domain-intelligence`.
- Profiles remain declarative and do not execute reasoning.
- Do not implement concrete Domain Rules from Phase 10.12.
- No persistence, external I/O, runtime identity lookup, runtime authorization, memory operations, workflow execution, operation execution, model selection or prompt selection.
- No arbitrary callbacks or executable values.
- No generic `dict.update()` or recursive dictionary merge for typed policies.
- No broad `except Exception`.
- No public `str(exc)` or `repr(exc)` leakage.
- Strict serialization, deep immutability and deterministic ordering.
- No commit or push until audit approval.

---

## File Structure

Create:

- `cmm/domains/profile_contracts.py` — typed policy and profile contracts, strict validation and serialization.
- `cmm/domains/profile_registry.py` — registry protocol and deterministic in-memory registry.
- `cmm/domains/profile_composition.py` — pure typed merge functions and `DefaultDomainProfileComposer`.
- `cmm/domains/profile_resolver.py` — overlay relevance, ID/time generation and final resolution.

Modify:

- `cmm/domains/enums.py`
- `cmm/domains/errors.py`
- `cmm/domains/__init__.py`
- `tests/domains/test_domain_public_api.py`

Create tests:

- `tests/domains/test_domain_profile_contracts.py`
- `tests/domains/test_domain_profile_serialization.py`
- `tests/domains/test_domain_profile_registry.py`
- `tests/domains/test_domain_profile_composition.py`
- `tests/domains/test_domain_profile_resolver.py`
- `tests/domains/test_domain_profile_public_api.py`
- `tests/domains/test_domain_profile_boundaries.py`

---

### Task 1: Enums and errors

**Files:**
- Modify: `cmm/domains/enums.py`
- Modify: `cmm/domains/errors.py`
- Test: `tests/domains/test_domain_profile_contracts.py`

**Produces:**

```text
DomainProfileResolutionStatus
DomainProfileSource
DomainProfileDecisionCode
DomainProfileConflictSeverity
DomainReasoningDepth
```

Errors:

```text
DomainProfileError
DomainProfileContractError
DomainProfileSerializationError
DomainProfileConfigurationError
DomainProfileRegistryError
DomainProfileCompositionError
DomainProfileResolutionError
```

- [ ] Write failing tests for exact enum values, coercion rejection, hierarchy and stable error codes.
- [ ] Run focused tests and confirm failure.
- [ ] Implement enums and errors following existing domain patterns.
- [ ] Run focused tests and Ruff.

---

### Task 2: Typed policy contracts

**Files:**
- Create: `cmm/domains/profile_contracts.py`
- Test: `tests/domains/test_domain_profile_contracts.py`
- Test: `tests/domains/test_domain_profile_serialization.py`

**Produces:**

```text
DomainQuestionPolicy
DomainPresentationPolicy
DomainMemoryPolicy
DomainTemporalPolicy
DomainProductionPolicy
```

- [ ] Write failing invariant tests for strict booleans, positive/non-negative limits, finite values and closed enums/levels.
- [ ] Write strict serialization tests with unknown-field rejection and nested field paths.
- [ ] Implement frozen slotted dataclasses with explicit `to_dict()`/`from_dict()`.
- [ ] Ensure metadata is deeply immutable and JSON-safe.
- [ ] Run focused tests and Ruff.

---

### Task 3: Definition and overlay contracts

**Files:**
- Extend: `cmm/domains/profile_contracts.py`
- Test: `tests/domains/test_domain_profile_contracts.py`
- Test: `tests/domains/test_domain_profile_serialization.py`

**Produces:**

```text
DomainProfileDefinition
DomainProfileOverlay
```

- [ ] Test canonical IDs, unique ordered collections, confidence, reasoning depth, maximum questions and typed policies.
- [ ] Test overlay partial-field semantics and strict source/priority validation.
- [ ] Test no callbacks, executable values or implicit coercion.
- [ ] Implement both contracts.
- [ ] Run focused tests and Ruff.

---

### Task 4: Resolution request, trace and result contracts

**Files:**
- Extend: `cmm/domains/profile_contracts.py`
- Test: `tests/domains/test_domain_profile_contracts.py`
- Test: `tests/domains/test_domain_profile_serialization.py`

**Produces:**

```text
DomainProfileResolutionRequest
DomainProfileModification
DomainProfileConflict
DomainProfileRejection
DomainProfileDecision
ResolvedDomainProfile
DomainProfileCompositionResult
DomainProfileResolution
```

- [ ] Test request-domain alignment, unique workflow/operation IDs and strict descriptive actor context.
- [ ] Test modification snapshots, conflict/rejection/decision invariants and timezone-aware datetimes.
- [ ] Test resolved-profile invariants and status invariants.
- [ ] Implement strict round trips for all contracts.
- [ ] Run focused tests and Ruff.

---

### Task 5: Registry protocol and in-memory registry

**Files:**
- Create: `cmm/domains/profile_registry.py`
- Test: `tests/domains/test_domain_profile_registry.py`

**Produces:**

```text
DomainProfileRegistry
InMemoryDomainProfileRegistry
```

- [ ] Write runtime-checkable protocol tests.
- [ ] Test duplicate profile ID rejection.
- [ ] Test one active base profile per domain.
- [ ] Test deterministic `get`, `get_by_domain` and `list_all`.
- [ ] Test immutable return values and no persistence.
- [ ] Implement registry.
- [ ] Run focused tests and Ruff.

---

### Task 6: Core collection merge helpers

**Files:**
- Create: `cmm/domains/profile_composition.py`
- Test: `tests/domains/test_domain_profile_composition.py`

**Produces private pure helpers for:**

```text
ordered union
restrictive intersection
explicit deny permission merge
rule precedence
resource precedence
inference precedence
action/escalation merge
modification recording
```

- [ ] Write failing tests for first-appearance ordering.
- [ ] Test required/optional/prohibited rule interactions.
- [ ] Test allowed/prohibited inference interactions.
- [ ] Test resource allowed/priority/prohibited interactions.
- [ ] Test permissions only narrow and explicit deny wins.
- [ ] Implement pure deterministic helpers.
- [ ] Run focused tests and Ruff.

---

### Task 7: Typed policy merge functions

**Files:**
- Extend: `cmm/domains/profile_composition.py`
- Test: `tests/domains/test_domain_profile_composition.py`

**Produces:**

```text
merge_question_policy
merge_presentation_policy
merge_memory_policy
merge_temporal_policy
merge_production_policy
```

- [ ] Write failing tests for every field-specific monotonic rule.
- [ ] Test capability booleans with AND and safety requirements with OR.
- [ ] Test minimum numeric limits and restrictive levels/scopes.
- [ ] Test every changed field creates a `DomainProfileModification`.
- [ ] Implement without generic dictionary merge.
- [ ] Run focused tests and Ruff.

---

### Task 8: DefaultDomainProfileComposer

**Files:**
- Extend: `cmm/domains/profile_composition.py`
- Test: `tests/domains/test_domain_profile_composition.py`

**Produces:**

```text
DomainProfileComposer
DefaultDomainProfileComposer
```

```python
class DomainProfileComposer(Protocol):
    def compose(
        self,
        *,
        global_profile: DomainProfileDefinition,
        primary_profile: DomainProfileDefinition,
        supporting_profiles: tuple[DomainProfileDefinition, ...],
        overlays: tuple[DomainProfileOverlay, ...],
        request_permissions: tuple[str, ...],
    ) -> DomainProfileCompositionResult:
        ...
```

- [ ] Test deterministic application order.
- [ ] Test global mandatory rules cannot disappear.
- [ ] Test confidence maximum, maximum-questions minimum and restrictive depth.
- [ ] Test prohibited actions/inferences/resources prevail.
- [ ] Test permissions and typed policies remain monotonic.
- [ ] Test conflicts, decisions, rejections and complete modifications.
- [ ] Implement the pure composer with no IDs, clocks or registry access.
- [ ] Run focused tests and Ruff.

---

### Task 9: Overlay relevance validation

**Files:**
- Create: `cmm/domains/profile_resolver.py`
- Test: `tests/domains/test_domain_profile_resolver.py`

**Produces private deterministic relevance validation for:**

```text
global policy
primary domain
supporting domain
workflow
operation
risk
actor
autonomy
explicit request
```

- [ ] Test every source against the corresponding request field.
- [ ] Test irrelevant optional overlays become rejections.
- [ ] Test irrelevant mandatory/global overlays produce blocking conflict.
- [ ] Test source IDs and domains strictly.
- [ ] Implement without runtime identity lookup.
- [ ] Run focused tests and Ruff.

---

### Task 10: DefaultDomainProfileResolver

**Files:**
- Extend: `cmm/domains/profile_resolver.py`
- Test: `tests/domains/test_domain_profile_resolver.py`

**Produces:**

```text
DomainProfileResolver
DefaultDomainProfileResolver
```

```python
class DefaultDomainProfileResolver:
    def __init__(
        self,
        *,
        composer: DomainProfileComposer | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        profile_id_factory: Callable[[], str] | None = None,
        trace_id_factory: Callable[[], str] | None = None,
    ) -> None:
        ...
```

- [ ] Test constructor protocol/callable validation.
- [ ] Test profile-domain alignment and supporting-profile order.
- [ ] Test factory outputs and aware clock.
- [ ] Test composer invocation and final status derivation.
- [ ] Test optional overlay rejection yields `PARTIAL`.
- [ ] Test blocking conflict yields `BLOCKED`.
- [ ] Test factory errors propagate.
- [ ] Implement resolver with no registry access.
- [ ] Run focused tests and Ruff.

---

### Task 11: Initial profile-name fixtures

**Files:**
- Extend: `cmm/domains/profile_registry.py`
- Test: `tests/domains/test_domain_profile_registry.py`

**Produces a declarative constant or factory for names only:**

```text
GeneralProfile
HealthProfile
RelationshipProfile
UniversityProfile
OppositionProfile
ReflectionProfile
ConcernProfile
LanguageProfile
NilProfile
SportProfile
LifePlanProfile
ProjectProfile
```

- [ ] Test exact profile names and deterministic order.
- [ ] Ensure no concrete Phase 10.12 rules are embedded.
- [ ] Ensure no classes are generated per profile.
- [ ] Implement minimal definitions/factory only if needed by the public API.
- [ ] Run focused tests and Ruff.

---

### Task 12: Public API and boundaries

**Files:**
- Modify: `cmm/domains/__init__.py`
- Modify: `tests/domains/test_domain_public_api.py`
- Create: `tests/domains/test_domain_profile_public_api.py`
- Create: `tests/domains/test_domain_profile_boundaries.py`

- [ ] Export all approved enums, contracts, protocols, implementations and errors.
- [ ] Assert internal helpers and fixtures are not unintentionally exported.
- [ ] Assert no Cognitive Layer execution, rule execution, persistence, network, filesystem, memory operations, workflow/operation execution, model or prompt selection.
- [ ] Assert no broad exception handling or generic policy dict merge.
- [ ] Assert previous Phase 10 public APIs remain stable.
- [ ] Run focused API and boundary tests.

---

### Task 13: Full verification and audit

**Files:**
- All Phase 10.11 files.

- [ ] Format and lint only Phase 10.11 files.
- [ ] Scan forbidden test and exception patterns.
- [ ] Run focused Domain Profile tests.
- [ ] Run all domain tests.
- [ ] Run validation tests.
- [ ] Run global suite.
- [ ] Run `compileall`.
- [ ] Run `git diff --check`.
- [ ] Confirm exact file scope.
- [ ] Create `/Users/chris/Desktop/phase-10.11-audit.tar.gz`.
- [ ] Stop before commit and push.

## Verification Commands

```zsh
cd "/Users/chris/CMM OS"

PHASE_1011_FILES=(
  cmm/domains/profile_contracts.py
  cmm/domains/profile_registry.py
  cmm/domains/profile_composition.py
  cmm/domains/profile_resolver.py
  cmm/domains/enums.py
  cmm/domains/errors.py
  cmm/domains/__init__.py
  tests/domains/test_domain_profile_contracts.py
  tests/domains/test_domain_profile_serialization.py
  tests/domains/test_domain_profile_registry.py
  tests/domains/test_domain_profile_composition.py
  tests/domains/test_domain_profile_resolver.py
  tests/domains/test_domain_profile_public_api.py
  tests/domains/test_domain_profile_boundaries.py
  tests/domains/test_domain_public_api.py
)

python -m ruff format "${PHASE_1011_FILES[@]}"
python -m ruff check "${PHASE_1011_FILES[@]}"
python -m ruff format --check "${PHASE_1011_FILES[@]}"

if rg -n 'pytest\.raises\(Exception\)|^\s*pass$' \
  tests/domains/test_domain_profile_*.py; then
  echo "FORBIDDEN TEST PATTERN FOUND"
  exit 1
else
  echo "NO FORBIDDEN TEST PATTERNS"
fi

if rg -n 'except Exception|str\(exc\)|repr\(exc\)|dict\.update\(' \
  cmm/domains/profile_*.py; then
  echo "FORBIDDEN IMPLEMENTATION PATTERN FOUND"
  exit 1
else
  echo "NO FORBIDDEN IMPLEMENTATION PATTERNS"
fi

python -m pytest tests/domains/test_domain_profile_*.py -q
python -m pytest tests/domains -q
python -m pytest tests/validation -q
python -m pytest -q

python -m compileall -q cmm/domains tests/domains
git diff --check
git diff --name-only
git diff --stat
git diff --numstat
git status --short
```

## Audit Archive

```bash
COPYFILE_DISABLE=1 tar \
  --exclude='._*' \
  -czf "/Users/chris/Desktop/phase-10.11-audit.tar.gz" \
  cmm/domains/profile_contracts.py \
  cmm/domains/profile_registry.py \
  cmm/domains/profile_composition.py \
  cmm/domains/profile_resolver.py \
  cmm/domains/enums.py \
  cmm/domains/errors.py \
  cmm/domains/__init__.py \
  tests/domains/test_domain_profile_contracts.py \
  tests/domains/test_domain_profile_serialization.py \
  tests/domains/test_domain_profile_registry.py \
  tests/domains/test_domain_profile_composition.py \
  tests/domains/test_domain_profile_resolver.py \
  tests/domains/test_domain_profile_public_api.py \
  tests/domains/test_domain_profile_boundaries.py \
  tests/domains/test_domain_public_api.py
```

## Self-Review

- Spec coverage: typed policies, definitions, overlays, registry, composition, relevance, resolver, conflicts, decisions, modifications, permissions and boundaries are assigned.
- Placeholder scan: no deferred requirements remain.
- Type consistency: composer and resolver signatures use contracts defined in earlier tasks.
- Scope: cognitive execution, concrete 10.12 rules, persistence, runtime identity, memory operations, workflow/operation execution, model/prompt selection and external I/O remain excluded.
