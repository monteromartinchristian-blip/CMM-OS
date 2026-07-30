# Phase 10.8 Domain Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an immutable, deterministic and fully traceable `DomainComposer` that converts a resolved set of domain definitions into one declarative effective composition without executing runtime behavior.

**Architecture:** `DefaultDomainComposer` receives a valid `DomainResolutionResult`, an explicit collection of `DomainDefinition` objects and a `DomainCompositionPolicy`. Focused helper modules compose profiles, item references, permissions, presentation, dependencies and declared conflicts. The result is a strict `DomainComposition` contract containing provenance, decisions and conflicts.

**Tech Stack:** Python 3.10+, frozen slotted dataclasses, enums, protocols, `MappingProxyType`, pytest, Ruff.

## Global Constraints

- Base commit: `3f7cdc7`.
- Work on `feature/phase-10-domain-intelligence`.
- Do not access `DomainRegistry`, stores, filesystem, network, LLMs, cognitive runtime, agent runtime or workflow engine.
- Do not execute rules, operations or workflows.
- Do not implement Phase 10.9 cross-domain coordination.
- Use strict immutable and JSON-safe contracts with `to_dict()` / `from_dict()`.
- Reject unknown serialized fields.
- Require timezone-aware datetimes.
- Do not catch `Exception` broadly.
- Do not infer semantic equivalence from strings or keywords.
- Preserve deterministic ordering and complete provenance.
- Do not commit or push until the final audit is approved.

---

## File Structure

Create:

- `cmm/domains/composition_contracts.py` — enums-adjacent value contracts and final composition result.
- `cmm/domains/composition_items.py` — deterministic item/provenance and exact-reference deduplication helpers.
- `cmm/domains/composition_permissions.py` — declarative restrictive permission composition.
- `cmm/domains/composition_conflicts.py` — dependency and declared conflict analysis.
- `cmm/domains/composer.py` — `DomainComposer` protocol and `DefaultDomainComposer` orchestration.
- `tests/domains/test_domain_composition_contracts.py`
- `tests/domains/test_domain_composition_items.py`
- `tests/domains/test_domain_composition_permissions.py`
- `tests/domains/test_domain_composition_conflicts.py`
- `tests/domains/test_domain_composer.py`
- `tests/domains/test_domain_composition_serialization.py`
- `tests/domains/test_domain_composition_public_api.py`

Modify:

- `cmm/domains/enums.py`
- `cmm/domains/errors.py`
- `cmm/domains/__init__.py`
- `tests/domains/test_domain_public_api.py`

---

### Task 1: Composition enums and errors

**Files:**
- Modify: `cmm/domains/enums.py`
- Modify: `cmm/domains/errors.py`
- Test: `tests/domains/test_domain_composition_contracts.py`

**Interfaces:**
- Produces:
  - `DomainCompositionStatus`
  - `DomainConflictPolicy`
  - `DomainCompositionError`
  - `DomainCompositionContractError`
  - `DomainCompositionSerializationError`
  - `DomainCompositionConfigurationError`
  - `DomainCompositionExecutionError`

- [ ] **Step 1: Write failing enum and error tests**

Assert exact enum values:

```python
assert {item.value for item in DomainCompositionStatus} == {
    "composed", "partial", "blocked", "failed"
}
assert {item.value for item in DomainConflictPolicy} == {
    "most_restrictive", "primary_precedence", "block_on_conflict"
}
```

Assert every Phase 10.8 error inherits from `DomainCompositionError`, itself under the existing domain error hierarchy.

- [ ] **Step 2: Run the focused test**

```bash
python -m pytest tests/domains/test_domain_composition_contracts.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement enums and errors**

Add:

```python
class DomainCompositionStatus(str, Enum):
    COMPOSED = "composed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class DomainConflictPolicy(str, Enum):
    MOST_RESTRICTIVE = "most_restrictive"
    PRIMARY_PRECEDENCE = "primary_precedence"
    BLOCK_ON_CONFLICT = "block_on_conflict"
```

Use stable error codes and no arbitrary exception text.

- [ ] **Step 4: Run focused tests and Ruff**

```bash
python -m pytest tests/domains/test_domain_composition_contracts.py -q
python -m ruff check cmm/domains/enums.py cmm/domains/errors.py tests/domains/test_domain_composition_contracts.py
```

---

### Task 2: Core immutable composition contracts

**Files:**
- Create: `cmm/domains/composition_contracts.py`
- Test: `tests/domains/test_domain_composition_contracts.py`
- Test: `tests/domains/test_domain_composition_serialization.py`

**Interfaces:**
- Produces:
  - `DomainCompositionPolicy`
  - `DomainCompositionItem`
  - `DomainCompositionDecision`
  - `DomainCompositionConflict`
  - `EffectiveReasoningProfile`
  - `PermissionComposition`
  - `PresentationComposition`
  - `DomainComposition`

Use these signatures:

```python
@dataclass(frozen=True, slots=True)
class DomainCompositionPolicy:
    conflict_policy: DomainConflictPolicy = DomainConflictPolicy.MOST_RESTRICTIVE
    blocking_severities: tuple[str, ...] = ("critical", "high", "blocking")
    partial_severities: tuple[str, ...] = ("medium", "warning")
    denied_permission_prefixes: tuple[str, ...] = ("deny:", "prohibit:")
    required_permission_prefixes: tuple[str, ...] = ("require:",)
    granted_permission_prefixes: tuple[str, ...] = ("allow:", "grant:")
    metadata: MappingProxyType[str, Any] = ...


@dataclass(frozen=True, slots=True)
class DomainCompositionItem:
    category: str
    identifier: str
    contributing_domains: tuple[DomainId, ...]
    primary_contributor: DomainId
    precedence: int
    metadata: MappingProxyType[str, Any] = ...


@dataclass(frozen=True, slots=True)
class DomainCompositionDecision:
    code: str
    category: str
    identifier: str | None
    action: str
    domains: tuple[DomainId, ...] = ()
    reason: str | None = None
    blocking: bool = False
    metadata: MappingProxyType[str, Any] = ...


@dataclass(frozen=True, slots=True)
class DomainCompositionConflict:
    code: str
    category: str
    domains: tuple[DomainId, ...]
    severity: str
    message: str
    blocking: bool
    resolved: bool = False
    resolution: str | None = None
    metadata: MappingProxyType[str, Any] = ...


@dataclass(frozen=True, slots=True)
class EffectiveReasoningProfile:
    base_profile: str | None
    contributing_profiles: tuple[str, ...] = ()
    contributing_domains: tuple[DomainId, ...] = ()
    added_rules: tuple[str, ...] = ()
    required_rules: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    minimum_confidence: float | None = None
    maximum_inference_depth: int | None = None
    maximum_questions_per_turn: int | None = None
    metadata: MappingProxyType[str, Any] = ...


@dataclass(frozen=True, slots=True)
class PermissionComposition:
    required_permissions: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()
    denied_permissions: tuple[str, ...] = ()
    unresolved_permissions: tuple[str, ...] = ()
    provenance: MappingProxyType[str, Any] = ...
    metadata: MappingProxyType[str, Any] = ...


@dataclass(frozen=True, slots=True)
class PresentationComposition:
    values: MappingProxyType[str, Any]
    provenance: MappingProxyType[str, Any]
    conflicts: tuple[DomainCompositionConflict, ...] = ()
    metadata: MappingProxyType[str, Any] = ...


@dataclass(frozen=True, slots=True)
class DomainComposition:
    id: str
    resolution_id: str
    status: DomainCompositionStatus
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...] = ()
    effective_profile: EffectiveReasoningProfile | None = None
    rules: tuple[DomainCompositionItem, ...] = ()
    resources: tuple[DomainCompositionItem, ...] = ()
    operations: tuple[DomainCompositionItem, ...] = ()
    workflows: tuple[DomainCompositionItem, ...] = ()
    validators: tuple[DomainCompositionItem, ...] = ()
    capabilities: tuple[DomainCompositionItem, ...] = ()
    permissions: PermissionComposition | None = None
    presentation: PresentationComposition | None = None
    decisions: tuple[DomainCompositionDecision, ...] = ()
    conflicts: tuple[DomainCompositionConflict, ...] = ()
    policy: DomainCompositionPolicy = ...
    composed_at: datetime = ...
    metadata: MappingProxyType[str, Any] = ...
```

- [ ] **Step 1: Add failing invariant tests**

Cover:
- strict enum coercion;
- non-empty identifiers;
- unique domains;
- primary excluded from supporting;
- finite confidence;
- positive integer limits;
- blocked requires at least one blocking conflict;
- composed cannot contain unresolved blocking conflict;
- deep freeze;
- naive datetime rejection;
- bool rejected as int/float;
- unknown serialized fields;
- nested field paths;
- full JSON round trip.

- [ ] **Step 2: Run tests to confirm failure**

```bash
python -m pytest \
  tests/domains/test_domain_composition_contracts.py \
  tests/domains/test_domain_composition_serialization.py -q
```

- [ ] **Step 3: Implement contracts**

Reuse established Phase 10 validation/freeze patterns without importing private helpers from unrelated modules when that would create coupling. Keep error messages stable.

- [ ] **Step 4: Run focused tests and Ruff**

```bash
python -m pytest \
  tests/domains/test_domain_composition_contracts.py \
  tests/domains/test_domain_composition_serialization.py -q
python -m ruff check cmm/domains/composition_contracts.py tests/domains/test_domain_composition_contracts.py tests/domains/test_domain_composition_serialization.py
```

---

### Task 3: Exact-reference item composition

**Files:**
- Create: `cmm/domains/composition_items.py`
- Test: `tests/domains/test_domain_composition_items.py`

**Interfaces:**
- Consumes: ordered `tuple[DomainDefinition, ...]`.
- Produces:

```python
def compose_reference_items(
    *,
    category: str,
    definitions: tuple[DomainDefinition, ...],
    value_getter: Callable[[DomainDefinition], tuple[str, ...]],
) -> tuple[tuple[DomainCompositionItem, ...], tuple[DomainCompositionDecision, ...]]:
    ...
```

- [ ] **Step 1: Write failing tests**

Cover:
- primary items precede supporting items;
- exact duplicates collapse;
- complete contributor provenance retained;
- first contributor remains `primary_contributor`;
- no semantic keyword equivalence;
- input order after primary/supporting normalization does not affect output;
- rules, resources, operations, workflows and validators use the same helper;
- capability identity uses explicit stable key `(kind, name, version)`, not free text.

- [ ] **Step 2: Run focused tests**

```bash
python -m pytest tests/domains/test_domain_composition_items.py -q
```

- [ ] **Step 3: Implement deterministic composition**

For string references, key by the exact normalized identifier only. Do not lowercase or rewrite identifiers unless existing contracts already do so.

Create one `DOMAIN_COMPOSITION_DUPLICATE_COLLAPSED` decision for each collapsed identifier with all contributing domains.

- [ ] **Step 4: Verify**

```bash
python -m pytest tests/domains/test_domain_composition_items.py -q
python -m ruff check cmm/domains/composition_items.py tests/domains/test_domain_composition_items.py
```

---

### Task 4: Restrictive permission composition

**Files:**
- Create: `cmm/domains/composition_permissions.py`
- Test: `tests/domains/test_domain_composition_permissions.py`

**Interfaces:**
- Produces:

```python
def compose_permissions(
    definitions: tuple[DomainDefinition, ...],
    policy: DomainCompositionPolicy,
) -> tuple[
    PermissionComposition,
    tuple[DomainCompositionDecision, ...],
    tuple[DomainCompositionConflict, ...],
]:
    ...
```

- [ ] **Step 1: Write failing tests**

Cover:
- required permissions accumulate;
- denied wins over granted under `MOST_RESTRICTIVE`;
- exact duplicate permission references collapse;
- provenance includes all domains;
- `PRIMARY_PRECEDENCE` chooses the primary declaration but records a resolved conflict;
- `BLOCK_ON_CONFLICT` emits unresolved blocking conflict;
- absent prefixes are treated as required opaque permission references, not guessed;
- no actor authorization is performed;
- no runtime imports.

- [ ] **Step 2: Run focused tests**

```bash
python -m pytest tests/domains/test_domain_composition_permissions.py -q
```

- [ ] **Step 3: Implement declarative parser and composer**

Interpret prefixes only from `DomainCompositionPolicy`. Strip exactly one configured prefix. Reject empty resulting permission names.

The composer must distinguish:
- required;
- granted;
- denied;
- unresolved.

- [ ] **Step 4: Verify**

```bash
python -m pytest tests/domains/test_domain_composition_permissions.py -q
python -m ruff check cmm/domains/composition_permissions.py tests/domains/test_domain_composition_permissions.py
```

---

### Task 5: Presentation composition

**Files:**
- Extend: `cmm/domains/composition_items.py`
- Test: `tests/domains/test_domain_composition_items.py`

**Interfaces:**
- Produces:

```python
def compose_presentation(
    definitions: tuple[DomainDefinition, ...],
    policy: DomainCompositionPolicy,
) -> tuple[
    PresentationComposition,
    tuple[DomainCompositionDecision, ...],
    tuple[DomainCompositionConflict, ...],
]:
    ...
```

- [ ] **Step 1: Add failing tests**

Cover:
- primary baseline retained;
- supporting fills missing keys;
- equal values merge provenance;
- conflicting values under `MOST_RESTRICTIVE` do not guess semantic restrictiveness and therefore preserve primary plus explicit partial conflict;
- `PRIMARY_PRECEDENCE` records resolved conflict;
- `BLOCK_ON_CONFLICT` blocks;
- nested mappings compose recursively;
- lists/tuples are atomic unless exactly equal;
- deterministic key ordering;
- deep immutability.

- [ ] **Step 2: Run focused tests**

```bash
python -m pytest tests/domains/test_domain_composition_items.py -q
```

- [ ] **Step 3: Implement recursive structured composition**

Never infer that one arbitrary presentation value is “more restrictive” than another. Use primary value unless policy blocks, and always record the conflict.

- [ ] **Step 4: Verify**

```bash
python -m pytest tests/domains/test_domain_composition_items.py -q
```

---

### Task 6: Profile composition

**Files:**
- Extend: `cmm/domains/composition_items.py`
- Test: `tests/domains/test_domain_composition_items.py`

**Interfaces:**
- Produces:

```python
def compose_reasoning_profile(
    definitions: tuple[DomainDefinition, ...],
) -> tuple[EffectiveReasoningProfile, tuple[DomainCompositionDecision, ...]]:
    ...
```

- [ ] **Step 1: Add failing tests**

Cover:
- primary `reasoning_profile` is base;
- supporting profiles are contributors;
- exact duplicates collapse;
- no secondary engine objects;
- structured limits may only come from explicit `metadata["reasoning_profile"]` mappings;
- minimum confidence takes maximum;
- maximum inference depth takes minimum positive value;
- maximum questions per turn takes minimum positive value;
- prohibited actions use union;
- required rules use union;
- invalid structured metadata produces contract error, not guessing.

- [ ] **Step 2: Run focused tests**

```bash
python -m pytest tests/domains/test_domain_composition_items.py -q
```

- [ ] **Step 3: Implement profile composition**

Treat the primary profile identifier as identity. Supporting profile identifiers are explanatory contributors only.

- [ ] **Step 4: Verify**

```bash
python -m pytest tests/domains/test_domain_composition_items.py -q
```

---

### Task 7: Dependency and declared conflict analysis

**Files:**
- Create: `cmm/domains/composition_conflicts.py`
- Test: `tests/domains/test_domain_composition_conflicts.py`

**Interfaces:**
- Produces:

```python
def analyze_dependencies(
    definitions: tuple[DomainDefinition, ...],
) -> tuple[
    tuple[DomainCompositionDecision, ...],
    tuple[DomainCompositionConflict, ...],
]:
    ...


def analyze_declared_conflicts(
    definitions: tuple[DomainDefinition, ...],
    policy: DomainCompositionPolicy,
) -> tuple[
    tuple[DomainCompositionDecision, ...],
    tuple[DomainCompositionConflict, ...],
]:
    ...
```

- [ ] **Step 1: Write failing tests**

Dependencies:
- selected required dependency present;
- missing required dependency blocks;
- missing optional dependency produces partial conflict;
- no automatic loading;
- cycle detection is deterministic;
- self-dependency rejected or reported safely;
- duplicate declarations collapse.

Declared conflicts:
- only conflicts between selected domains count;
- blocking severity follows exact configured sets;
- medium/warning produces partial;
- unknown severity is explicit non-blocking unresolved conflict, never guessed;
- bilateral duplicate declarations collapse with provenance;
- policy can block all declared conflicts under `BLOCK_ON_CONFLICT`.

- [ ] **Step 2: Run focused tests**

```bash
python -m pytest tests/domains/test_domain_composition_conflicts.py -q
```

- [ ] **Step 3: Implement graph and conflict analysis**

Use stable domain-slug ordering for traversal. Do not consult registry or load dependencies.

- [ ] **Step 4: Verify**

```bash
python -m pytest tests/domains/test_domain_composition_conflicts.py -q
python -m ruff check cmm/domains/composition_conflicts.py tests/domains/test_domain_composition_conflicts.py
```

---

### Task 8: DefaultDomainComposer orchestration

**Files:**
- Create: `cmm/domains/composer.py`
- Test: `tests/domains/test_domain_composer.py`

**Interfaces:**
- Produces:

```python
class DomainComposer(Protocol):
    def compose(
        self,
        resolution: DomainResolutionResult,
        definitions: Iterable[DomainDefinition],
    ) -> DomainComposition:
        ...


class DefaultDomainComposer:
    def __init__(
        self,
        *,
        policy: DomainCompositionPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        ...

    def compose(
        self,
        resolution: DomainResolutionResult,
        definitions: Iterable[DomainDefinition],
    ) -> DomainComposition:
        ...
```

- [ ] **Step 1: Write failing orchestration tests**

Cover:
- only `RESOLVED` results with primary domain compose normally;
- ambiguous/blocked/unsupported resolution rejected with stable configuration/contract error;
- exact selected definitions required;
- extra definitions ignored or rejected according to one explicit policy; choose rejection to prevent accidental composition;
- duplicate definition IDs rejected;
- definition order normalized to primary then resolver supporting order;
- missing primary blocks;
- missing supporting blocks because resolver selected it;
- disabled selected definition blocks;
- components composed through helpers;
- `COMPOSED`, `PARTIAL`, `BLOCKED` derived from conflicts;
- all decisions and conflicts retained;
- clock and ID factory validated;
- identical inputs produce identical output with fixed factories;
- no broad exception catch;
- no registry/store/runtime imports;
- no mutation.

- [ ] **Step 2: Run focused test**

```bash
python -m pytest tests/domains/test_domain_composer.py -q
```

- [ ] **Step 3: Implement orchestration**

Flow:

1. Validate argument types and acceptable resolution status.
2. Normalize definitions by selected domain IDs.
3. Validate exact coverage and enabled state.
4. Compose profile and exact-reference categories.
5. Compose permissions and presentation.
6. Analyze dependencies and declared conflicts.
7. Aggregate and semantically deduplicate decisions/conflicts.
8. Derive status:
   - unresolved blocking conflict → `BLOCKED`;
   - otherwise any unresolved non-blocking conflict or exclusion → `PARTIAL`;
   - otherwise `COMPOSED`.
9. Validate factories in one result-construction path.
10. Return immutable `DomainComposition`.

Do not construct `FAILED` by catching programming errors.

- [ ] **Step 4: Verify**

```bash
python -m pytest tests/domains/test_domain_composer.py -q
python -m ruff check cmm/domains/composer.py tests/domains/test_domain_composer.py
```

---

### Task 9: Public API and regression boundaries

**Files:**
- Modify: `cmm/domains/__init__.py`
- Modify: `tests/domains/test_domain_public_api.py`
- Create: `tests/domains/test_domain_composition_public_api.py`

**Interfaces:**
- Export all Phase 10.8 public contracts, errors and services.

- [ ] **Step 1: Write failing API tests**

Assert exports:

```text
DomainCompositionStatus
DomainConflictPolicy
DomainCompositionPolicy
DomainCompositionItem
DomainCompositionDecision
DomainCompositionConflict
EffectiveReasoningProfile
PermissionComposition
PresentationComposition
DomainComposition
DomainComposer
DefaultDomainComposer
DomainCompositionError
DomainCompositionContractError
DomainCompositionSerializationError
DomainCompositionConfigurationError
DomainCompositionExecutionError
```

Assert Phase 10.8 does not export:
- `CrossDomainEngine`;
- runtime executor;
- registry-backed composer;
- workflow executor;
- cognitive engine.

- [ ] **Step 2: Run focused API tests**

```bash
python -m pytest tests/domains/test_domain_composition_public_api.py tests/domains/test_domain_public_api.py -q
```

- [ ] **Step 3: Add imports and `__all__` entries**

Keep Phase 10 comments grouped and sorted consistently with the existing package.

- [ ] **Step 4: Verify**

```bash
python -m pytest tests/domains/test_domain_composition_public_api.py tests/domains/test_domain_public_api.py -q
python -m ruff check cmm/domains/__init__.py tests/domains/test_domain_composition_public_api.py tests/domains/test_domain_public_api.py
```

---

### Task 10: Full verification and audit package

**Files:**
- All Phase 10.8 production and test files.

- [ ] **Step 1: Format and lint all changed Python files**

```zsh
cd "/Users/chris/CMM OS"

CHANGED_PY_FILES=(
  ${(f)"$(
    {
      git diff --name-only --diff-filter=ACMR 3f7cdc7 -- 'cmm/**/*.py' 'tests/**/*.py'
      git ls-files --others --exclude-standard -- 'cmm/**/*.py' 'tests/**/*.py'
    } | sort -u
  )"}
)

python -m ruff format "${CHANGED_PY_FILES[@]}"
python -m ruff check "${CHANGED_PY_FILES[@]}"
python -m ruff format --check "${CHANGED_PY_FILES[@]}"
```

- [ ] **Step 2: Run focused and subsystem suites**

```bash
python -m pytest tests/domains/test_domain_composition_*.py tests/domains/test_domain_composer.py -q
python -m pytest tests/domains -q
python -m pytest tests/validation -q
```

- [ ] **Step 3: Run global verification**

```bash
python -m pytest -q
python -m compileall -q cmm/domains tests/domains
git diff --check
```

- [ ] **Step 4: Produce complete diff accounting**

```bash
git add -N cmm/domains tests/domains
git diff --stat
git diff --numstat
git status --short
```

- [ ] **Step 5: Build audit archive**

```bash
tar -czf "/Users/chris/Desktop/phase-10.8-audit.tar.gz" \
  cmm/domains/composition_contracts.py \
  cmm/domains/composition_items.py \
  cmm/domains/composition_permissions.py \
  cmm/domains/composition_conflicts.py \
  cmm/domains/composer.py \
  cmm/domains/enums.py \
  cmm/domains/errors.py \
  cmm/domains/__init__.py \
  tests/domains/test_domain_composition_contracts.py \
  tests/domains/test_domain_composition_items.py \
  tests/domains/test_domain_composition_permissions.py \
  tests/domains/test_domain_composition_conflicts.py \
  tests/domains/test_domain_composer.py \
  tests/domains/test_domain_composition_serialization.py \
  tests/domains/test_domain_composition_public_api.py \
  tests/domains/test_domain_public_api.py
```

- [ ] **Step 6: Stop before commit**

Do not commit or push. Deliver literal command outputs, the archive and deliberate limitations for audit.

## Self-review

- Spec coverage: contracts, profiles, references, permissions, presentation, dependencies, conflicts, deduplication, provenance, statuses, determinism, errors, public API and regression verification are assigned.
- Scope: no runtime execution, registry access, persistence, LLMs or Phase 10.9 behavior.
- Type consistency: all helper signatures consume existing `DomainDefinition` and produce Phase 10.8 contracts.
- Placeholder scan: no `TBD`, `TODO` or deferred implementation requirements remain.
