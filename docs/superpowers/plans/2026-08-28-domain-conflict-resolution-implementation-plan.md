# Phase 10.32 Domain Conflict Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the pure, deterministic Phase 10.32 universal conflict-orchestration layer that normalizes existing Domain Intelligence conflicts, applies strict authority precedence, preserves unresolved disagreement, and fails closed on unresolved blocking conflicts.

**Architecture:** Keep every existing conflict-producing subsystem authoritative in its own scope. Add focused Phase 10.32 contracts, pure adapters, and one universal `DomainConflictResolver`; it consumes immutable references and returns a declarative `DomainConflictResolution` without executing actions, mutating sessions, persisting state, emitting events, or duplicating Phase 8 contradiction truth resolution.

**Tech Stack:** Python 3.12+, frozen `dataclasses`, `Enum`, `MappingProxyType`, pytest, Ruff, existing `cmm.domains` contract/serialization patterns.

**Spec:** `docs/superpowers/specs/2026-08-28-domain-conflict-resolution-policies-design.md`

## Global Constraints

- Phase 10.32 is a universal conflict orchestration layer; existing conflict contracts remain authoritative and are referenced, not replaced.
- Existing `DomainConflict` keeps its current meaning and existing `DomainConflictPolicy` remains composition-local.
- The universal aggregate is `DomainConflictCase`.
- Resolution is deterministic and pure: same immutable inputs + same policy => same output.
- No time reads, random IDs, network, filesystem, model/provider calls, memory writes, session mutation, workflow/operation execution, approval execution, event emission, or persistence inside conflict resolution.
- Authority order is strict: global safety → permissions → mandatory rules → highest-risk applicable domain → primary domain → evidence → reliability → temporal validity → user/qualified-human authority.
- Lower authority never weakens higher authority.
- Highest-risk precedence is structured-input-driven and must never hardcode domain slugs.
- Evidence/reliability/temporal comparison requires explicit structured comparable scores; ties or missing/incomparable scores preserve the conflict.
- `maintain_conflict` and `postpone_action` are not semantic resolution.
- An unresolved blocking conflict always has `can_proceed=False`.
- User confirmation applies only where the user is a legitimate authority; human review is declarative only.
- Phase 8 remains authoritative for semantic knowledge contradiction truth resolution.
- Phase 10.31 selection precedence and anti-score-tie-break invariants remain unchanged.
- Phase 10.33 owns events. Later phases own persistence/session continuity.
- Every public contract is immutable, strict, round-trippable, rejects unknown fields, rejects contradictory deserialized state, and deeply freezes caller-owned metadata.
- Every production behavior begins with observed RED and is followed by minimal GREEN.
- Do not advance top-level `ROADMAP.md` beyond 10.32 until the independent audit has passed.
- Do not push or merge.

---

## File Structure

### New production modules

- `cmm/domains/conflict_resolution_contracts.py`
  - Closed enums, public immutable contracts, strict validation, serialization, reason-code vocabulary.
- `cmm/domains/conflict_adapters.py`
  - Pure adapters from existing conflict contracts into Phase 10.32 normalized references.
- `cmm/domains/conflict_resolution.py`
  - `DomainConflictResolver`, authority ranking, strategy selection, deterministic resolution.

### Existing production modules modified

- `cmm/domains/errors.py`
  - Typed Phase 10.32 contract/serialization errors only.
- `cmm/domains/__init__.py`
  - Stable public exports only after implementation is complete.

### New tests

- `tests/domains/test_domain_conflict_resolution_contracts.py`
- `tests/domains/test_domain_conflict_adapters.py`
- `tests/domains/test_domain_conflict_resolution.py`
- `tests/domains/test_domain_conflict_resolution_adversarial.py`
- `tests/domains/test_domain_conflict_resolution_public_api.py`
- `tests/domains/test_domain_conflict_resolution_dp032_acceptance.py`

### Documentation modified after implementation

- `docs/roadmap/phase-10-domain-intelligence.md`
- `docs/reference/domain-intelligence-requirements-matrix.md`

Do not add Phase 10.32 production behavior to `cmm/domains/resolver.py`; Phase 10.31's resolver remains selection-focused.

---

### Task 1: Phase 10.32 error types, enums, and `DomainConflictReference`

**Files:**
- Modify: `cmm/domains/errors.py`
- Create: `cmm/domains/conflict_resolution_contracts.py`
- Create: `tests/domains/test_domain_conflict_resolution_contracts.py`

**Interfaces:**
- Consumes: `DomainId` from `cmm.domains.identifiers`; established deep-freeze/JSON-safe validation patterns from `selection_contracts.py` and `resolver_contracts.py`.
- Produces:
  - `DomainConflictResolutionContractError`
  - `DomainConflictResolutionSerializationError`
  - `DomainConflictSourceKind`
  - `DomainConflictKind`
  - `DomainConflictSeverity`
  - `DomainConflictStatus`
  - `DomainConflictStrategy`
  - `DomainConflictAuthority`
  - `DomainConflictReasonCode`
  - `DomainConflictReference`

- [ ] **Step 1: Add the first contract tests and observe RED**

Create the first section of `tests/domains/test_domain_conflict_resolution_contracts.py`:

```python
from types import MappingProxyType

import pytest

from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictReference,
    DomainConflictSeverity,
    DomainConflictSourceKind,
)
from cmm.domains.errors import (
    DomainConflictResolutionContractError,
    DomainConflictResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId


def test_reference_is_frozen_deeply_and_round_trips() -> None:
    metadata = {"classification": {"safe": True}, "labels": ["a", "b"]}
    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.PERMISSION_CONFLICT,
        source_id="permission-conflict-1",
        domain_id=DomainId(slug="project"),
        blocking=True,
        severity=DomainConflictSeverity.BLOCKING,
        authority_kind=DomainConflictAuthority.PERMISSION,
        evidence_refs=("evidence-1",),
        metadata=metadata,
    )

    metadata["classification"]["safe"] = False
    metadata["labels"].append("mutated")

    assert isinstance(ref.metadata, MappingProxyType)
    assert ref.metadata["classification"]["safe"] is True
    assert tuple(ref.metadata["labels"]) == ("a", "b")
    assert DomainConflictReference.from_dict(ref.to_dict()) == ref


def test_reference_rejects_non_strict_boolean() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictReference(
            source_kind="permission_conflict",
            source_id="permission-conflict-1",
            blocking=1,
        )


def test_reference_rejects_unknown_serialized_fields() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictReference.from_dict(
            {
                "source_kind": "permission_conflict",
                "source_id": "permission-conflict-1",
                "blocking": True,
                "unexpected": "no",
            }
        )


def test_reference_rejects_duplicate_evidence_refs() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictReference(
            source_kind="evidence_conflict",
            source_id="evidence-conflict-1",
            blocking=False,
            evidence_refs=("e1", "e1"),
        )
```

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_conflict_resolution_contracts.py
```

Expected: collection/import failure because Phase 10.32 contracts do not exist yet. Record this as the Task 1 RED evidence.

- [ ] **Step 2: Add typed errors**

In `cmm/domains/errors.py`, following the existing Domain error hierarchy, add:

```python
class DomainConflictResolutionContractError(DomainContractValidationError):
    """Raised when a Phase 10.32 conflict-resolution contract is invalid."""


class DomainConflictResolutionSerializationError(DomainConflictResolutionContractError):
    """Raised when serialized Phase 10.32 conflict data is invalid."""
```

Add both names to the module's exported symbols using the existing `__all__` pattern.

- [ ] **Step 3: Implement the closed vocabularies**

In `cmm/domains/conflict_resolution_contracts.py` create these exact enums:

```python
class DomainConflictSourceKind(str, Enum):
    DECLARED_DOMAIN_CONFLICT = "declared_domain_conflict"
    COMPOSITION_CONFLICT = "composition_conflict"
    PERMISSION_CONFLICT = "permission_conflict"
    PROFILE_CONFLICT = "profile_conflict"
    RULE_SELECTION_CONFLICT = "rule_selection_conflict"
    PRESENTATION_CONFLICT = "presentation_conflict"
    CROSS_DOMAIN_CONTRADICTION = "cross_domain_contradiction"
    KNOWLEDGE_CONTRADICTION = "knowledge_contradiction"
    SELECTION_CONFLICT = "selection_conflict"
    DOMAIN_SPECIFIC_CONFLICT = "domain_specific_conflict"


class DomainConflictKind(str, Enum):
    SAFETY = "safety"
    PERMISSION = "permission"
    MANDATORY_RULE = "mandatory_rule"
    DOMAIN_RISK = "domain_risk"
    DOMAIN_PRECEDENCE = "domain_precedence"
    EVIDENCE = "evidence"
    RELIABILITY = "reliability"
    TEMPORAL = "temporal"
    PREFERENCE = "preference"
    RECOMMENDATION = "recommendation"
    PRESENTATION = "presentation"
    COMPOSITION = "composition"
    KNOWLEDGE = "knowledge"
    SELECTION = "selection"
    OTHER = "other"


class DomainConflictSeverity(str, Enum):
    ADVISORY = "advisory"
    MATERIAL = "material"
    BLOCKING = "blocking"


class DomainConflictStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    BLOCKED = "blocked"
    AWAITING_USER = "awaiting_user"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    POSTPONED = "postponed"


class DomainConflictStrategy(str, Enum):
    MOST_RESTRICTIVE = "most_restrictive"
    HIGH_RISK_DOMAIN_PRECEDENCE = "high_risk_domain_precedence"
    PRIMARY_DOMAIN_PRECEDENCE = "primary_domain_precedence"
    EVIDENCE_WEIGHTED = "evidence_weighted"
    SEPARATE_RESULTS = "separate_results"
    ASK_USER = "ask_user"
    HUMAN_REVIEW = "human_review"
    POSTPONE_ACTION = "postpone_action"
    MAINTAIN_CONFLICT = "maintain_conflict"


class DomainConflictAuthority(str, Enum):
    GLOBAL_SAFETY = "global_safety"
    PERMISSION = "permission"
    MANDATORY_RULE = "mandatory_rule"
    HIGH_RISK_DOMAIN = "high_risk_domain"
    PRIMARY_DOMAIN = "primary_domain"
    EVIDENCE = "evidence"
    RELIABILITY = "reliability"
    TEMPORAL = "temporal"
    USER = "user"
    HUMAN_REVIEW = "human_review"
    UNCLASSIFIED = "unclassified"
```

Add this exact stable reason vocabulary:

```python
class DomainConflictReasonCode(str, Enum):
    SAFETY_PRECEDENCE = "DOMAIN_CONFLICT_SAFETY_PRECEDENCE"
    PERMISSION_PRECEDENCE = "DOMAIN_CONFLICT_PERMISSION_PRECEDENCE"
    MANDATORY_RULE_PRECEDENCE = "DOMAIN_CONFLICT_MANDATORY_RULE_PRECEDENCE"
    HIGH_RISK_PRECEDENCE = "DOMAIN_CONFLICT_HIGH_RISK_PRECEDENCE"
    PRIMARY_PRECEDENCE = "DOMAIN_CONFLICT_PRIMARY_PRECEDENCE"
    EVIDENCE_PRECEDENCE = "DOMAIN_CONFLICT_EVIDENCE_PRECEDENCE"
    RELIABILITY_PRECEDENCE = "DOMAIN_CONFLICT_RELIABILITY_PRECEDENCE"
    TEMPORAL_PRECEDENCE = "DOMAIN_CONFLICT_TEMPORAL_PRECEDENCE"
    USER_INPUT_REQUIRED = "DOMAIN_CONFLICT_USER_INPUT_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "DOMAIN_CONFLICT_HUMAN_REVIEW_REQUIRED"
    ACTION_POSTPONED = "DOMAIN_CONFLICT_ACTION_POSTPONED"
    SEPARATE_RESULTS = "DOMAIN_CONFLICT_SEPARATE_RESULTS"
    PRESERVED = "DOMAIN_CONFLICT_PRESERVED"
    BLOCKING_UNRESOLVED = "DOMAIN_CONFLICT_BLOCKING_UNRESOLVED"
    INSUFFICIENT_BASIS = "DOMAIN_CONFLICT_INSUFFICIENT_BASIS"
    STRATEGY_NOT_APPLICABLE = "DOMAIN_CONFLICT_STRATEGY_NOT_APPLICABLE"
```

- [ ] **Step 4: Implement `DomainConflictReference` minimally and strictly**

Use a frozen slots dataclass with this signature:

```python
@dataclass(frozen=True, slots=True)
class DomainConflictReference:
    source_kind: DomainConflictSourceKind
    source_id: str
    domain_id: DomainId | None = None
    blocking: bool = False
    severity: DomainConflictSeverity | None = None
    authority_kind: DomainConflictAuthority | None = None
    evidence_refs: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
```

Validation requirements:

```text
source_kind       => enum coercion, unknown rejected
source_id         => non-empty stripped string
domain_id         => DomainId/canonical string or None
blocking          => strict bool, never bool(1)
severity          => enum or None
authority_kind    => enum or None
evidence_refs     => tuple of unique non-empty strings
metadata          => JSON-safe, credential-key-safe, deeply frozen
unknown fields    => rejected by from_dict()
```

`to_dict()` must emit enum values and canonical `str(domain_id)`. `from_dict()` must round-trip without mutability leakage.

Do not read time or generate IDs.

- [ ] **Step 5: Turn Task 1 GREEN and run local quality gates**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_conflict_resolution_contracts.py

.venv/bin/ruff check \
  cmm/domains/conflict_resolution_contracts.py \
  cmm/domains/errors.py \
  tests/domains/test_domain_conflict_resolution_contracts.py

.venv/bin/ruff format --check \
  cmm/domains/conflict_resolution_contracts.py \
  cmm/domains/errors.py \
  tests/domains/test_domain_conflict_resolution_contracts.py

.venv/bin/python -m py_compile \
  cmm/domains/conflict_resolution_contracts.py
```

Expected: all PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add \
  cmm/domains/errors.py \
  cmm/domains/conflict_resolution_contracts.py \
  tests/domains/test_domain_conflict_resolution_contracts.py

git diff --cached --check
git commit -m "feat(domains): add conflict resolution base contracts"
```

---

### Task 2: `DomainConflictCase`, `DomainConflictResolution`, and policy invariants

**Files:**
- Modify: `cmm/domains/conflict_resolution_contracts.py`
- Modify: `tests/domains/test_domain_conflict_resolution_contracts.py`

**Interfaces:**
- Consumes: all Task 1 enums and `DomainConflictReference`.
- Produces:
  - `DomainConflictCase`
  - `DomainConflictResolution`
  - `DomainConflictResolutionPolicy`

- [ ] **Step 1: Add status/policy contradiction tests and observe RED**

Append these tests:

```python
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictResolution,
    DomainConflictResolutionPolicy,
    DomainConflictStatus,
    DomainConflictStrategy,
)


def _ref(
    source_id: str = "ref-1",
    *,
    blocking: bool = False,
    authority: DomainConflictAuthority | None = None,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        blocking=blocking,
        severity=(
            DomainConflictSeverity.BLOCKING
            if blocking
            else DomainConflictSeverity.MATERIAL
        ),
        authority_kind=authority,
    )


def test_case_rejects_blocking_flag_without_blocking_severity() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="case-1",
            domains=(DomainId(slug="project"),),
            kind=DomainConflictKind.COMPOSITION,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.OPEN,
            references=(_ref(blocking=True),),
            blocking=True,
        )


def test_case_rejects_resolved_with_blocking_reference() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="case-1",
            domains=(DomainId(slug="project"),),
            kind=DomainConflictKind.PERMISSION,
            severity=DomainConflictSeverity.BLOCKING,
            status=DomainConflictStatus.RESOLVED,
            references=(_ref(blocking=True),),
            blocking=True,
        )


def test_resolution_rejects_blocking_unresolved_can_proceed() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="case-1",
            status=DomainConflictStatus.BLOCKED,
            strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
            preserved_reference_ids=("ref-1",),
            reason_codes=(DomainConflictReasonCode.BLOCKING_UNRESOLVED,),
            conflict_preserved=True,
            can_proceed=True,
        )


def test_resolution_from_dict_rejects_contradictory_user_state() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictResolution.from_dict(
            {
                "conflict_id": "case-1",
                "status": "resolved",
                "strategy": "ask_user",
                "winning_reference_ids": [],
                "preserved_reference_ids": [],
                "rejected_reference_ids": [],
                "reason_codes": ["DOMAIN_CONFLICT_USER_INPUT_REQUIRED"],
                "requires_user_input": True,
                "requires_human_review": False,
                "action_postponed": False,
                "conflict_preserved": False,
                "can_proceed": True,
                "metadata": {},
            }
        )


def test_policy_rejects_primary_precedence_for_permission_conflicts() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolutionPolicy(
            permission_strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE
        )


def test_policy_rejects_disabled_human_review_strategy() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.HUMAN_REVIEW,
            allow_human_review=False,
        )
```

Run the focused file and record the expected RED because the three new contracts do not exist.

- [ ] **Step 2: Implement `DomainConflictCase`**

Use this exact signature:

```python
@dataclass(frozen=True, slots=True)
class DomainConflictCase:
    id: str
    domains: tuple[DomainId, ...]
    kind: DomainConflictKind
    severity: DomainConflictSeverity
    status: DomainConflictStatus
    references: tuple[DomainConflictReference, ...]
    affected_item_refs: tuple[str, ...] = ()
    candidate_strategies: tuple[DomainConflictStrategy, ...] = ()
    requires_human_review: bool = False
    blocking: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
```

Enforce:

```text
id                     => non-empty
domains                => unique deterministic tuple
references             => non-empty
reference source_ids   => unique within case
affected_item_refs     => unique non-empty strings
candidate_strategies   => unique enum values
requires_human_review  => strict bool
blocking               => strict bool
blocking=True          => severity must be BLOCKING
severity=BLOCKING      => blocking must be True
RESOLVED               => no blocking source may remain unresolved
BLOCKED                => blocking must be True
AWAITING_HUMAN_REVIEW  => requires_human_review must be True
OPEN/UNRESOLVED        => do not fabricate a winner
metadata               => same safe deep-freeze rules as Task 1
```

Do not require `domains` to be non-empty: a knowledge conflict can legitimately arrive without a domain-specific owner. Preserve deterministic input order after deduplication rather than alphabetical re-ranking if the caller intentionally supplied primary-first order.

- [ ] **Step 3: Implement `DomainConflictResolution`**

Use:

```python
@dataclass(frozen=True, slots=True)
class DomainConflictResolution:
    conflict_id: str
    status: DomainConflictStatus
    strategy: DomainConflictStrategy
    winning_reference_ids: tuple[str, ...] = ()
    preserved_reference_ids: tuple[str, ...] = ()
    rejected_reference_ids: tuple[str, ...] = ()
    reason_codes: tuple[DomainConflictReasonCode, ...] = ()
    requires_user_input: bool = False
    requires_human_review: bool = False
    action_postponed: bool = False
    conflict_preserved: bool = False
    can_proceed: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
```

Structural invariants independent of a source case:

```text
winner ∩ rejected = ∅
requires_user_input=True   <=> status == AWAITING_USER
requires_human_review=True <=> status == AWAITING_HUMAN_REVIEW
action_postponed=True      <=> status == POSTPONED
status == BLOCKED          => can_proceed=False
strategy == MAINTAIN_CONFLICT => conflict_preserved=True
strategy == POSTPONE_ACTION   => conflict_preserved=True
strategy == ASK_USER           => requires_user_input=True
strategy == HUMAN_REVIEW       => requires_human_review=True
```

The resolver in later tasks performs source-case membership validation before returning the object. `from_dict()` must still reject internally contradictory payloads.

- [ ] **Step 4: Implement `DomainConflictResolutionPolicy`**

Use:

```python
@dataclass(frozen=True, slots=True)
class DomainConflictResolutionPolicy:
    default_strategy: DomainConflictStrategy = DomainConflictStrategy.MAINTAIN_CONFLICT
    blocking_strategy: DomainConflictStrategy = DomainConflictStrategy.MAINTAIN_CONFLICT
    permission_strategy: DomainConflictStrategy = DomainConflictStrategy.MOST_RESTRICTIVE
    mandatory_rule_strategy: DomainConflictStrategy = DomainConflictStrategy.MOST_RESTRICTIVE
    high_risk_strategy: DomainConflictStrategy = DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE
    primary_strategy: DomainConflictStrategy = DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE
    evidence_strategy: DomainConflictStrategy = DomainConflictStrategy.EVIDENCE_WEIGHTED
    allow_separate_results: bool = True
    allow_user_confirmation: bool = True
    allow_human_review: bool = True
    allow_postpone: bool = True
    preserve_unresolved_conflicts: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
```

Reject incompatible configurations, including:

```python
_PERMISSION_ALLOWED = {
    DomainConflictStrategy.MOST_RESTRICTIVE,
    DomainConflictStrategy.HUMAN_REVIEW,
    DomainConflictStrategy.MAINTAIN_CONFLICT,
    DomainConflictStrategy.POSTPONE_ACTION,
}

_MANDATORY_ALLOWED = {
    DomainConflictStrategy.MOST_RESTRICTIVE,
    DomainConflictStrategy.HUMAN_REVIEW,
    DomainConflictStrategy.MAINTAIN_CONFLICT,
    DomainConflictStrategy.POSTPONE_ACTION,
}
```

Explicitly reject permission or mandatory-rule strategies of:

```text
primary_domain_precedence
high_risk_domain_precedence
evidence_weighted
separate_results
ask_user
```

Reject any configured `HUMAN_REVIEW`, `ASK_USER`, `POSTPONE_ACTION`, or `SEPARATE_RESULTS` strategy when its corresponding allow flag is false.

Reject `preserve_unresolved_conflicts=False`; Phase 10.32's initial version freezes preservation as a safety invariant rather than pretending unsupported destructive behavior exists.

- [ ] **Step 5: Add full round-trip and membership-shape tests**

Add tests proving:

```python
case = DomainConflictCase(...)
assert DomainConflictCase.from_dict(case.to_dict()) == case

policy = DomainConflictResolutionPolicy(...)
assert DomainConflictResolutionPolicy.from_dict(policy.to_dict()) == policy

resolution = DomainConflictResolution(...)
assert DomainConflictResolution.from_dict(resolution.to_dict()) == resolution
```

Also test unknown fields and retained caller-owned list/dict mutation for every new contract.

- [ ] **Step 6: Turn Task 2 GREEN**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_conflict_resolution_contracts.py

.venv/bin/ruff check \
  cmm/domains/conflict_resolution_contracts.py \
  tests/domains/test_domain_conflict_resolution_contracts.py

.venv/bin/ruff format --check \
  cmm/domains/conflict_resolution_contracts.py \
  tests/domains/test_domain_conflict_resolution_contracts.py

.venv/bin/python -m py_compile \
  cmm/domains/conflict_resolution_contracts.py
```

- [ ] **Step 7: Commit Task 2**

```bash
git add \
  cmm/domains/conflict_resolution_contracts.py \
  tests/domains/test_domain_conflict_resolution_contracts.py

git diff --cached --check
git commit -m "feat(domains): add conflict case and resolution policy"
```

---

### Task 3: Pure normalization adapters for existing conflict families

**Files:**
- Create: `cmm/domains/conflict_adapters.py`
- Create: `tests/domains/test_domain_conflict_adapters.py`

**Interfaces:**
- Consumes:
  - `DomainConflict`
  - `DomainCompositionConflict`
  - `DomainPermissionConflict`
  - `DomainProfileConflict`
  - `DomainRuleSelectionConflict`
  - `DomainPresentationConflict`
  - `CrossDomainContradiction`
  - Cognitive `Contradiction`
  - `DomainResolutionResult` when status is `AMBIGUOUS`
- Produces these functions:

```python
def adapt_declared_domain_conflict(
    conflict: DomainConflict,
    *,
    source_id: str,
    owner_domain_id: DomainId | None = None,
    authority_kind: DomainConflictAuthority | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]: ...

def adapt_composition_conflict(
    conflict: DomainCompositionConflict,
    *,
    source_id: str,
    authority_kind: DomainConflictAuthority | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]: ...

def adapt_permission_conflict(
    conflict: DomainPermissionConflict,
    *,
    source_id: str,
    domain_id: DomainId | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]: ...

def adapt_profile_conflict(
    conflict: DomainProfileConflict,
    *,
    source_id: str,
    domain_id: DomainId | None = None,
    authority_kind: DomainConflictAuthority | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]: ...

def adapt_rule_selection_conflict(
    conflict: DomainRuleSelectionConflict,
    *,
    source_id: str,
    domain_id: DomainId | None = None,
    authority_kind: DomainConflictAuthority | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]: ...

def adapt_presentation_conflict(
    conflict: DomainPresentationConflict,
    *,
    source_id: str,
    domain_id: DomainId | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]: ...

def adapt_cross_domain_contradiction(
    contradiction: CrossDomainContradiction,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]: ...

def adapt_knowledge_contradiction(
    contradiction: Contradiction,
    *,
    domain_ids: tuple[DomainId, ...] = (),
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]: ...

def adapt_selection_conflict(
    result: DomainResolutionResult,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]: ...
```

The `(reference, domains)` return shape preserves multi-domain participation without overloading the singular `DomainConflictReference.domain_id`.

- [ ] **Step 1: Write connected adapter tests and observe RED**

Create tests that instantiate real upstream contracts, not mocks.

Core cases:

```python
def test_permission_adapter_is_fail_closed_and_does_not_copy_source_lists() -> None:
    source = DomainPermissionConflict(
        action="cross_domain_transfer",
        allowing_sources=("primary:project:1.0.0",),
        denying_sources=("supporting:general:1.0.0",),
        resolution="deny",
        reason_code="allow_deny_conflict",
    )

    ref, domains = adapt_permission_conflict(
        source,
        source_id="perm-1",
        domain_id=DomainId(slug="project"),
    )

    assert ref.source_kind is DomainConflictSourceKind.PERMISSION_CONFLICT
    assert ref.authority_kind is DomainConflictAuthority.PERMISSION
    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING
    assert domains == (DomainId(slug="project"),)
    assert "allowing_sources" not in ref.metadata
    assert "denying_sources" not in ref.metadata


def test_composition_adapter_preserves_all_domain_participation() -> None:
    conflict = DomainCompositionConflict(
        code="TEST_CONFLICT",
        category="declared_conflicts",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        severity="blocking",
        message="incompatible",
        blocking=True,
    )

    ref, domains = adapt_composition_conflict(
        conflict,
        source_id="composition-1",
    )

    assert ref.source_kind is DomainConflictSourceKind.COMPOSITION_CONFLICT
    assert ref.blocking is True
    assert domains == (
        DomainId(slug="project"),
        DomainId(slug="general"),
    )


def test_selection_adapter_only_accepts_real_ambiguity() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        adapt_selection_conflict(resolved_result)
```

Also add one test for every adapter function listed above.

Run:

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_conflict_adapters.py
```

Expected RED because adapter module does not exist.

- [ ] **Step 2: Implement common adapter helpers**

Implement only explicit mappings; do not infer authority from prose.

```python
def _severity_from_blocking(blocking: bool) -> DomainConflictSeverity:
    return (
        DomainConflictSeverity.BLOCKING
        if blocking
        else DomainConflictSeverity.MATERIAL
    )
```

Map known enum severities conservatively:

```text
DomainProfileConflictSeverity.BLOCKING -> BLOCKING
DomainProfileConflictSeverity.ERROR    -> MATERIAL
DomainProfileConflictSeverity.WARNING  -> ADVISORY

DomainRuleConflictSeverity.BLOCKING    -> BLOCKING
DomainRuleConflictSeverity.ERROR       -> MATERIAL
DomainRuleConflictSeverity.WARNING     -> ADVISORY

CrossDomainSeverity.CRITICAL/HIGH      -> BLOCKING only when unresolved/review-required behavior makes it blocking;
otherwise MATERIAL. Never downgrade an upstream explicit blocking fact.
```

For contracts without explicit blocking semantics, use `blocking=False` unless the adapter has an authoritative structured reason to block. Do not treat words inside `message`, `reason`, `description`, `subject`, or free-text metadata as authority.

- [ ] **Step 3: Implement each adapter with purpose-minimized metadata**

Required safe metadata examples:

```python
# permission
{
    "action": conflict.action.value,
    "resolution": conflict.resolution.value,
    "reason_code": conflict.reason_code,
}

# composition
{
    "code": conflict.code,
    "category": conflict.category,
    "resolved_upstream": conflict.resolved,
    "resolution": conflict.resolution,
}

# profile
{
    "code": conflict.code,
    "field": conflict.field,
}

# rule selection
{
    "code": conflict.code,
    "rule_id": conflict.rule_id,
}

# presentation
{
    "code": conflict.code.value,
    "related_ids": conflict.related_ids,
}

# cross-domain contradiction
{
    "resolved_upstream": contradiction.resolved,
    "requires_review": contradiction.requires_review,
}

# cognitive contradiction
{
    "status": contradiction.status.value,
    "preferred_id": contradiction.preferred_id,
}
```

Do not copy:

```text
free-form messages
statements
explanations
private prompt content
full evidence payloads
permission source lists
profile source payloads
chain-of-thought
credentials/secrets
```

For Cognitive `Contradiction`, use `contradiction.id` as `source_id`, include only evidence IDs if the `Evidence` contract exposes stable identifiers; otherwise leave `evidence_refs=()`.

For selection adaptation, require:

```python
result.status is DomainResolutionStatus.AMBIGUOUS
len(result.ambiguous_domains) >= 2
```

Use `result.id` as `source_id`. Do not copy `candidate_scores`; 10.32 must not reintroduce forbidden score tie-breaking.

- [ ] **Step 4: Verify adapters do not mutate sources**

Add a parametrized test that serializes or snapshots each upstream object before adaptation and proves it remains equal afterward.

- [ ] **Step 5: Turn Task 3 GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_conflict_adapters.py

.venv/bin/ruff check \
  cmm/domains/conflict_adapters.py \
  tests/domains/test_domain_conflict_adapters.py

.venv/bin/ruff format --check \
  cmm/domains/conflict_adapters.py \
  tests/domains/test_domain_conflict_adapters.py

.venv/bin/python -m py_compile cmm/domains/conflict_adapters.py
```

- [ ] **Step 6: Commit Task 3**

```bash
git add \
  cmm/domains/conflict_adapters.py \
  tests/domains/test_domain_conflict_adapters.py

git diff --cached --check
git commit -m "feat(domains): normalize conflict references"
```

---

### Task 4: Universal resolver core and strict authority precedence

**Files:**
- Create: `cmm/domains/conflict_resolution.py`
- Create: `tests/domains/test_domain_conflict_resolution.py`

**Interfaces:**
- Consumes: `DomainConflictCase`, `DomainConflictResolutionPolicy`, Task 1 enums.
- Produces:

```python
class DomainConflictResolver:
    def resolve(
        self,
        case: DomainConflictCase,
        *,
        policy: DomainConflictResolutionPolicy | None = None,
        primary_domain: DomainId | None = None,
        highest_risk_domain: DomainId | None = None,
        evidence_scores: Mapping[str, float] | None = None,
        reliability_scores: Mapping[str, float] | None = None,
        temporal_scores: Mapping[str, float] | None = None,
    ) -> DomainConflictResolution:
        ...
```

No constructor state is required in the initial implementation.

- [ ] **Step 1: Freeze authority precedence with failing tests**

Create tests for this exact rank:

```python
_AUTHORITY_RANK = {
    DomainConflictAuthority.GLOBAL_SAFETY: 0,
    DomainConflictAuthority.PERMISSION: 1,
    DomainConflictAuthority.MANDATORY_RULE: 2,
    DomainConflictAuthority.HIGH_RISK_DOMAIN: 3,
    DomainConflictAuthority.PRIMARY_DOMAIN: 4,
    DomainConflictAuthority.EVIDENCE: 5,
    DomainConflictAuthority.RELIABILITY: 6,
    DomainConflictAuthority.TEMPORAL: 7,
    DomainConflictAuthority.USER: 8,
    DomainConflictAuthority.HUMAN_REVIEW: 8,
    DomainConflictAuthority.UNCLASSIFIED: 9,
}
```

Required behavioral tests:

```python
def test_permission_beats_primary_even_when_primary_has_stronger_evidence() -> None:
    ...


def test_mandatory_rule_beats_high_risk_and_primary() -> None:
    ...


def test_high_risk_beats_primary_when_structured_risk_domain_is_supplied() -> None:
    ...


def test_primary_beats_evidence_only_when_primary_strategy_is_legitimate() -> None:
    ...


def test_unresolved_blocking_conflict_never_can_proceed() -> None:
    ...
```

Run and record RED because resolver does not exist.

- [ ] **Step 2: Implement deterministic input normalization**

At the top of `conflict_resolution.py`, implement:

```python
_AUTHORITY_RANK: Mapping[DomainConflictAuthority, int] = MappingProxyType({...})
```

Validate score maps with one helper:

```python
def _validated_scores(
    raw: Mapping[str, float] | None,
    *,
    allowed_ids: frozenset[str],
    field_name: str,
) -> MappingProxyType[str, float]:
    ...
```

Rules:

```text
None => empty immutable mapping
keys => non-empty source IDs that exist in this case
values => finite int/float, bool rejected
unknown source ID => contract error
duplicate keys impossible by Mapping
```

Never normalize missing scores to zero: missing means incomparable/insufficient.

- [ ] **Step 3: Implement authority selection before strategies**

The resolver must first determine the highest applicable authority represented by references:

```python
def _highest_authority(
    references: tuple[DomainConflictReference, ...],
) -> DomainConflictAuthority:
    return min(
        (
            ref.authority_kind or DomainConflictAuthority.UNCLASSIFIED
            for ref in references
        ),
        key=_AUTHORITY_RANK.__getitem__,
    )
```

Then filter the decisive authority group:

```python
decisive_refs = tuple(
    ref
    for ref in case.references
    if (ref.authority_kind or DomainConflictAuthority.UNCLASSIFIED)
    is authority
)
```

A lower authority group is never allowed to reverse this group's outcome.

If the case is `blocking=True` and no legitimate strategy can resolve it, return a preserved `BLOCKED` result.

- [ ] **Step 4: Implement authority-to-strategy routing**

Use this routing:

```text
GLOBAL_SAFETY   -> MOST_RESTRICTIVE
PERMISSION      -> policy.permission_strategy
MANDATORY_RULE  -> policy.mandatory_rule_strategy
HIGH_RISK_DOMAIN-> policy.high_risk_strategy
PRIMARY_DOMAIN  -> policy.primary_strategy
EVIDENCE        -> policy.evidence_strategy
RELIABILITY     -> EVIDENCE_WEIGHTED using reliability_scores
TEMPORAL        -> EVIDENCE_WEIGHTED using temporal_scores
USER            -> ASK_USER
HUMAN_REVIEW    -> HUMAN_REVIEW
UNCLASSIFIED    -> policy.blocking_strategy if case.blocking else policy.default_strategy
```

Candidate-strategy constraint:

```python
if case.candidate_strategies and strategy not in case.candidate_strategies:
    return _preserve(
        case,
        reason_codes=(
            DomainConflictReasonCode.STRATEGY_NOT_APPLICABLE,
            DomainConflictReasonCode.BLOCKING_UNRESOLVED
            if case.blocking
            else DomainConflictReasonCode.INSUFFICIENT_BASIS,
        ),
    )
```

Never fall through to a lower authority just because the higher-authority strategy was inapplicable. That would violate the frozen precedence.

- [ ] **Step 5: Implement one shared preservation result**

Use one helper with no time/random behavior:

```python
def _preserve(
    case: DomainConflictCase,
    *,
    strategy: DomainConflictStrategy = DomainConflictStrategy.MAINTAIN_CONFLICT,
    reason_codes: tuple[DomainConflictReasonCode, ...],
) -> DomainConflictResolution:
    return DomainConflictResolution(
        conflict_id=case.id,
        status=(
            DomainConflictStatus.BLOCKED
            if case.blocking
            else DomainConflictStatus.UNRESOLVED
        ),
        strategy=strategy,
        preserved_reference_ids=tuple(ref.source_id for ref in case.references),
        reason_codes=reason_codes,
        conflict_preserved=True,
        can_proceed=False,
    )
```

This deliberately chooses `can_proceed=False` for unresolved non-blocking conflicts in the universal resolver. A later caller may continue unrelated work, but Phase 10.32 must not assert that an action dependent on the case can proceed.

- [ ] **Step 6: Turn precedence core GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_conflict_resolution.py
```

Expected: all current Task 4 cases PASS.

- [ ] **Step 7: Commit Task 4**

```bash
git add \
  cmm/domains/conflict_resolution.py \
  tests/domains/test_domain_conflict_resolution.py

git diff --cached --check
git commit -m "feat(domains): enforce conflict authority precedence"
```

---

### Task 5: Implement all resolution strategies and fail-closed edge behavior

**Files:**
- Modify: `cmm/domains/conflict_resolution.py`
- Modify: `tests/domains/test_domain_conflict_resolution.py`
- Create: `tests/domains/test_domain_conflict_resolution_adversarial.py`

**Interfaces:**
- Consumes: Task 4 resolver.
- Produces complete behavior for every `DomainConflictStrategy`.

- [ ] **Step 1: Add RED tests for `most_restrictive`**

Required behavior:

```python
def test_most_restrictive_selects_blocking_authoritative_refs() -> None:
    ...


def test_permission_deny_cannot_be_overridden_by_primary_precedence() -> None:
    ...


def test_blocking_case_without_decisive_restrictive_ref_stays_blocked() -> None:
    ...
```

For `MOST_RESTRICTIVE`, authoritative blocking references may be placed in `winning_reference_ids` only to mean "this restriction governs", not "the semantic disagreement disappeared". If competing authoritative refs remain incompatible, preserve all refs and keep the case blocked.

- [ ] **Step 2: Add RED tests and implementation for high-risk precedence**

Test:

```python
def test_high_risk_requires_explicit_structured_domain() -> None:
    ...


def test_high_risk_never_uses_slug_name_heuristics() -> None:
    ...


def test_high_risk_unique_match_resolves_non_blocking_case() -> None:
    ...
```

Implementation requirements:

```python
matches = tuple(
    ref for ref in decisive_refs
    if ref.domain_id is not None and ref.domain_id == highest_risk_domain
)
```

Resolution is legitimate only when:

```text
highest_risk_domain is supplied
exactly one decisive reference matches it
case is not blocking OR higher authority semantics explicitly make the restriction decisive
```

If no unique match: preserve conflict with `INSUFFICIENT_BASIS`.

Do not search metadata or slug strings for words such as `health`, `legal`, or `finance`.

- [ ] **Step 3: Add RED tests and implementation for primary precedence**

Test:

```python
def test_primary_precedence_requires_primary_participation() -> None:
    ...


def test_primary_precedence_never_resolves_blocking_case() -> None:
    ...


def test_primary_precedence_resolves_eligible_non_blocking_case() -> None:
    ...
```

Requirements:

```text
primary_domain supplied
case.blocking is False
exactly one decisive reference has domain_id == primary_domain
higher authority already handled before this method
```

If not: preserve.

- [ ] **Step 4: Add RED tests and implementation for evidence/reliability/temporal weighting**

Use one helper:

```python
def _unique_score_winner(
    references: tuple[DomainConflictReference, ...],
    scores: Mapping[str, float],
) -> DomainConflictReference | None:
    ...
```

It must require a score for **every** decisive reference. Missing score => no winner. Tied maximum => no winner. Unique maximum => winner.

Tests:

```python
def test_evidence_unique_maximum_wins() -> None:
    ...


def test_evidence_tie_preserves_conflict() -> None:
    ...


def test_evidence_missing_score_preserves_conflict() -> None:
    ...


def test_reliability_cannot_override_permission() -> None:
    ...


def test_temporal_cannot_override_mandatory_rule() -> None:
    ...
```

Use distinct reason codes for evidence, reliability, and temporal outcomes.

- [ ] **Step 5: Add RED tests and implementation for `separate_results`**

Rules:

```text
policy.allow_separate_results must be True
case.blocking must be False
authority cannot be GLOBAL_SAFETY, PERMISSION, or MANDATORY_RULE
all references preserved
winning_reference_ids=()
rejected_reference_ids=()
status=UNRESOLVED
strategy=SEPARATE_RESULTS
reason=SEPARATE_RESULTS
conflict_preserved=True
can_proceed=True
```

`can_proceed=True` means coexistence itself is the safe declared output, not that one incompatible action may be executed.

- [ ] **Step 6: Add RED tests and implementation for `ask_user`**

Allowed only if:

```text
policy.allow_user_confirmation is True
case.kind in {PREFERENCE, DOMAIN_PRECEDENCE, RECOMMENDATION, SELECTION}
case.blocking is False
no higher authority has already blocked
```

Return:

```python
DomainConflictResolution(
    conflict_id=case.id,
    status=DomainConflictStatus.AWAITING_USER,
    strategy=DomainConflictStrategy.ASK_USER,
    preserved_reference_ids=all_ids,
    reason_codes=(DomainConflictReasonCode.USER_INPUT_REQUIRED,),
    requires_user_input=True,
    conflict_preserved=True,
    can_proceed=False,
)
```

Add adversarial tests proving ASK_USER is forbidden for safety, permission, mandatory-rule, or knowledge-truth conflicts.

- [ ] **Step 7: Add RED tests and implementation for `human_review`**

Allowed only when `policy.allow_human_review=True`.

Return AWAITING_HUMAN_REVIEW, preserve every reference, `can_proceed=False`, and emit `HUMAN_REVIEW_REQUIRED`.

Do not import Agent Runtime approval services.

- [ ] **Step 8: Add RED tests and implementation for postponement**

Return POSTPONED, preserve all references, `action_postponed=True`, `can_proceed=False`, reason `ACTION_POSTPONED`.

Do not call `approval_service.postpone()` or any runtime service.

- [ ] **Step 9: Add RED tests and implementation for maintain-conflict**

Blocking => BLOCKED. Non-blocking => UNRESOLVED. Both preserve all references and `can_proceed=False`.

Use reasons:

```text
PRESERVED
BLOCKING_UNRESOLVED when blocking
INSUFFICIENT_BASIS when no legitimate resolver exists
```

- [ ] **Step 10: Add source-case membership validation**

Before returning any resolved decision, assert all IDs in winners/preserved/rejected exist in the case and are disjoint where required.

Implement an internal `_validate_resolution_against_case(case, resolution)` and call it for every exit path.

- [ ] **Step 11: Add purity/adversarial tests**

In `tests/domains/test_domain_conflict_resolution_adversarial.py`, monkeypatch or sentinel-patch these sources so any accidental use fails:

```text
time.time
datetime.now where patchable in the new module
uuid.uuid4
secrets.token_hex
random.random
```

Also assert the new module imports none of:

```text
cmm.agent_runtime.approval_service
cmm.agent_runtime.workflow*
cmm.domains.*operation execution services
cmm.cognitive.store_*
network libraries
```

A static import-source test may read `cmm/domains/conflict_resolution.py` and reject those forbidden import substrings.

- [ ] **Step 12: Run full Phase 10.32 focused tests**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_conflict_resolution_contracts.py \
  tests/domains/test_domain_conflict_adapters.py \
  tests/domains/test_domain_conflict_resolution.py \
  tests/domains/test_domain_conflict_resolution_adversarial.py
```

- [ ] **Step 13: Commit Task 5**

```bash
git add \
  cmm/domains/conflict_resolution.py \
  tests/domains/test_domain_conflict_resolution.py \
  tests/domains/test_domain_conflict_resolution_adversarial.py

git diff --cached --check
git commit -m "feat(domains): implement conflict resolution strategies"
```

---

### Task 6: Public API and backward-compatibility boundary

**Files:**
- Modify: `cmm/domains/__init__.py`
- Create: `tests/domains/test_domain_conflict_resolution_public_api.py`
- Modify only if necessary for exports: `cmm/domains/conflict_resolution_contracts.py`, `cmm/domains/conflict_adapters.py`, `cmm/domains/conflict_resolution.py`

**Interfaces:**
- Produces stable `cmm.domains` imports for Phase 10.32.
- Preserves existing `DomainConflict` and `DomainConflictPolicy`.

- [ ] **Step 1: Write RED public API tests**

```python
import cmm.domains as domains


def test_phase_1032_public_symbols_are_exported() -> None:
    expected = {
        "DomainConflictReference",
        "DomainConflictCase",
        "DomainConflictResolution",
        "DomainConflictResolutionPolicy",
        "DomainConflictSourceKind",
        "DomainConflictKind",
        "DomainConflictSeverity",
        "DomainConflictStatus",
        "DomainConflictStrategy",
        "DomainConflictAuthority",
        "DomainConflictReasonCode",
        "DomainConflictResolver",
    }
    assert expected <= set(domains.__all__)
    for name in expected:
        assert hasattr(domains, name)


def test_existing_conflict_symbols_keep_identity() -> None:
    from cmm.domains.contracts import DomainConflict as ExistingDomainConflict
    from cmm.domains.enums import DomainConflictPolicy as ExistingConflictPolicy

    assert domains.DomainConflict is ExistingDomainConflict
    assert domains.DomainConflictPolicy is ExistingConflictPolicy
```

Also test direct imports of every adapter function from its module, but do not expose all adapters at top-level unless the current package style strongly favors doing so. The required top-level public API is contracts + resolver.

- [ ] **Step 2: Update exports minimally**

Modify `cmm/domains/__init__.py` to import and export the symbols above. Do not reorder unrelated legacy exports or perform cleanup refactors.

- [ ] **Step 3: Run public API and historical compatibility tests**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_conflict_resolution_public_api.py \
  tests/domains/test_domain_public_api.py \
  tests/domains/test_domain_composition_public_api.py
```

- [ ] **Step 4: Commit Task 6**

```bash
git add \
  cmm/domains/__init__.py \
  tests/domains/test_domain_conflict_resolution_public_api.py

git diff --cached --check
git commit -m "feat(domains): expose conflict resolution public API"
```

---

### Task 7: Connected subsystem integration and Phase 10.31 boundary regression suite

**Files:**
- Modify: `tests/domains/test_domain_conflict_resolution_adversarial.py`
- Modify: `tests/domains/test_domain_conflict_adapters.py`
- Test existing:
  - `tests/domains/test_domain_permission_resolution.py`
  - `tests/domains/test_domain_composition_conflicts.py`
  - `tests/domains/test_domain_profile_resolver.py`
  - `tests/domains/test_domain_rule_selection.py`
  - `tests/domains/test_domain_presentation_multidomain.py`
  - `tests/domains/test_cross_domain_engine.py`
  - `tests/domains/test_domain_selection_policy_dp031_acceptance.py`

**Interfaces:**
- No new production interface unless a test exposes a real missing normalization boundary.
- Any production change found here must follow RED → minimal GREEN and stay within `conflict_adapters.py` or `conflict_resolution.py`.

- [ ] **Step 1: Add real composition → universal resolution case**

Build a real `DomainCompositionConflict`, adapt it, construct a `DomainConflictCase`, resolve it, and assert:

```text
blocking source remains blocking
all source IDs remain auditable
PRIMARY_DOMAIN_PRECEDENCE cannot erase blocking incompatibility
can_proceed=False
```

- [ ] **Step 2: Add real permission → universal fail-closed case**

Create `DomainPermissionConflict` with DENY resolution and prove universal conflict resolution cannot produce `can_proceed=True`, even when:

```text
primary_domain points to the allowing side
evidence score favors the allowing side
reliability score favors the allowing side
temporal score favors the allowing side
```

- [ ] **Step 3: Add profile and rule-selection connected cases**

For a blocking `DomainProfileConflict` and a blocking `DomainRuleSelectionConflict`, prove:

```text
blocking preserved
no silent downgrade to advisory/material
no lower-level strategy reverses it
```

Do not infer `MANDATORY_RULE` merely from free-text code. Where the test needs mandatory-rule authority, pass it explicitly through the trusted adapter argument.

- [ ] **Step 4: Add presentation connected case**

Presentation terminology conflict may be preserved/separated only if non-blocking. Prove no semantic result content is rewritten by Phase 10.32.

- [ ] **Step 5: Add CrossDomainContradiction boundary**

Use a real `CrossDomainContradiction`. Verify:

```text
contradiction.id becomes source_id
domains preserved separately by adapter
statements are NOT copied into Phase 10.32 metadata
resolved_upstream/requires_review categorical state may be copied
```

- [ ] **Step 6: Add Cognitive Contradiction boundary**

Use a real `cmm.cognitive.knowledge.Contradiction`. Verify:

```text
source ID preserved
item_a/item_b truth is not re-decided
preferred_id may be referenced only as existing upstream state
Phase 10.32 does not import/use ContradictionResolutionPolicyEngine
no cognitive store writes
```

- [ ] **Step 7: Add Phase 10.31 ambiguity boundary**

Create or obtain a real `DomainResolutionResult` with `AMBIGUOUS` status, adapt it, and prove:

```text
candidate_scores are not copied into Phase 10.32 reference metadata
ordinary score cannot choose a winner
ASK_USER or preserved conflict is legitimate
the original 22 AT-DP-031 checkpoints remain green
```

- [ ] **Step 8: Run connected historical suites**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_conflict_resolution_contracts.py \
  tests/domains/test_domain_conflict_adapters.py \
  tests/domains/test_domain_conflict_resolution.py \
  tests/domains/test_domain_conflict_resolution_adversarial.py \
  tests/domains/test_domain_permission_resolution.py \
  tests/domains/test_domain_composition_conflicts.py \
  tests/domains/test_domain_profile_resolver.py \
  tests/domains/test_domain_rule_selection.py \
  tests/domains/test_domain_presentation_multidomain.py \
  tests/domains/test_cross_domain_engine.py \
  tests/domains/test_domain_selection_policy_dp031_acceptance.py
```

Record exact pass count from fresh output; do not predeclare it.

- [ ] **Step 9: Commit Task 7**

If only tests changed:

```bash
git add \
  tests/domains/test_domain_conflict_adapters.py \
  tests/domains/test_domain_conflict_resolution_adversarial.py

git diff --cached --check
git commit -m "test(domains): harden conflict resolution boundaries"
```

If a genuine implementation defect required a minimal fix, include exactly the affected Phase 10.32 production file in the same commit and describe the fixed invariant in the commit body.

---

### Task 8: Connected `AT-DP-032` acceptance gate

**Files:**
- Create: `tests/domains/test_domain_conflict_resolution_dp032_acceptance.py`

**Interfaces:**
- Consumes only public/stable Phase 10.32 APIs plus real upstream conflict contracts.
- Produces the canonical connected acceptance gate for DP-032.

- [ ] **Step 1: Write the complete acceptance suite**

Use individually named checkpoints. Cover at least these normative outcomes:

```text
AT-DP-032-01  public immutable contracts
AT-DP-032-02  existing DomainConflict meaning preserved
AT-DP-032-03  existing DomainConflictPolicy meaning preserved
AT-DP-032-04  permission adapter connected
AT-DP-032-05  composition adapter connected
AT-DP-032-06  profile adapter connected
AT-DP-032-07  rule-selection adapter connected
AT-DP-032-08  presentation adapter connected
AT-DP-032-09  cross-domain contradiction connected
AT-DP-032-10  cognitive contradiction is reference-only
AT-DP-032-11  selection ambiguity does not regain score tie-break
AT-DP-032-12  safety beats all lower authority
AT-DP-032-13  permission beats mandatory/lower authority as ordered by spec
AT-DP-032-14  mandatory rule beats domain/evidence authority
AT-DP-032-15  high-risk precedence uses explicit structured domain only
AT-DP-032-16  primary precedence limited to eligible non-blocking conflict
AT-DP-032-17  evidence unique winner only
AT-DP-032-18  evidence tie preserves conflict
AT-DP-032-19  reliability cannot widen higher authority
AT-DP-032-20  temporal validity cannot widen higher authority
AT-DP-032-21  separate-results safe non-blocking behavior
AT-DP-032-22  ask-user legitimate authority boundary
AT-DP-032-23  human-review declarative boundary
AT-DP-032-24  postpone is not semantic resolution
AT-DP-032-25  maintain-conflict is not semantic resolution
AT-DP-032-26  unresolved blocking => can_proceed False
AT-DP-032-27  no upstream reference silently disappears
AT-DP-032-28  deterministic identical-input output
AT-DP-032-29  resolver input immutability
AT-DP-032-30  no side effects / events / persistence
AT-DP-032-31  strict serialization rejects contradiction
AT-DP-032-32  lower authority never reverses higher authority
```

Thirty-two checkpoints are the planned minimum because each listed requirement is independently auditable. If implementation legitimately needs additional checkpoints, add them; never reduce coverage merely to preserve the number 32.

- [ ] **Step 2: Observe RED before any acceptance-specific production change**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_conflict_resolution_dp032_acceptance.py
```

If it fails, classify each failure:

```text
test defect
missing required implementation
real production bug
```

Only real missing/incorrect production behavior may trigger a Phase 10.32 production edit, and that edit starts from this observed RED.

- [ ] **Step 3: Repair only genuine gaps and reach GREEN**

Re-run until every AT-DP-032 checkpoint passes.

Record exact checkpoint count from pytest output.

- [ ] **Step 4: Commit acceptance gate**

```bash
git add \
  tests/domains/test_domain_conflict_resolution_dp032_acceptance.py \
  cmm/domains/conflict_resolution_contracts.py \
  cmm/domains/conflict_adapters.py \
  cmm/domains/conflict_resolution.py \
  cmm/domains/__init__.py \
  cmm/domains/errors.py

git diff --cached --check
```

Before committing, unstage any production file that did not actually change:

```bash
git diff --cached --name-only
```

Then commit only the real scope:

```bash
git commit -m "feat(domains): connect conflict resolution acceptance gate"
```

---

### Task 9: Full verification, documentation, and audit-ready handoff

**Files:**
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Do not modify top-level `ROADMAP.md` to advance the milestone yet.

**Interfaces:**
- Produces fresh verification evidence and an audit-ready Git HEAD.
- Final independent audit remains external to the implementation agent.

- [ ] **Step 1: Establish exact Phase 10.32 Python delta**

Use the spec commit as the base:

```bash
BASE=79fd145

git diff --name-only "$BASE"...HEAD -- '*.py' | sort
```

Save the exact file count. The expected logical delta should be limited to Phase 10.32 production/test files plus `cmm/domains/errors.py` and `cmm/domains/__init__.py`. Investigate any unrelated Python delta before continuing.

- [ ] **Step 2: Run the focused Phase 10.32 suite**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_conflict_resolution_contracts.py \
  tests/domains/test_domain_conflict_adapters.py \
  tests/domains/test_domain_conflict_resolution.py \
  tests/domains/test_domain_conflict_resolution_adversarial.py \
  tests/domains/test_domain_conflict_resolution_public_api.py \
  tests/domains/test_domain_conflict_resolution_dp032_acceptance.py
```

Record exact count from fresh output.

- [ ] **Step 3: Re-run Phase 10.31 acceptance**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_selection_policy_dp031_acceptance.py
```

Expected: exactly the historical 22 checkpoints still pass.

- [ ] **Step 4: Run the complete Domain suite**

```bash
.venv/bin/python -m pytest -q tests/domains
```

The Phase 10.31 audited baseline was 6684 domain tests. The new result must be greater than or equal to that baseline and fully green. Record the new exact count; do not hardcode an expected new total.

- [ ] **Step 5: Run the complete global suite**

```bash
.venv/bin/python -m pytest -q
```

The Phase 10.31 audited baseline was 12224 global tests. The new result must be greater than or equal to that baseline and fully green. Record the new exact count.

- [ ] **Step 6: Run delta quality gates**

Capture the changed Python files:

```bash
mapfile -t PY_DELTA < <(
  git diff --name-only "$BASE"...HEAD -- '*.py' | sort
)
```

If the shell is zsh, use:

```zsh
PY_DELTA=("${(@f)$(git diff --name-only "$BASE"...HEAD -- '*.py' | sort)}")
```

Then:

```bash
.venv/bin/ruff check "${PY_DELTA[@]}"
.venv/bin/ruff format --check "${PY_DELTA[@]}"
.venv/bin/python -m py_compile "${PY_DELTA[@]}"
git diff --check
```

Every gate must PASS.

- [ ] **Step 7: Update the detailed Phase 10 roadmap**

In `docs/roadmap/phase-10-domain-intelligence.md`, update only the Phase 10.32 section with factual fresh evidence:

```text
Implementation status: Complete — independent audit pending
DP-032: implemented
AT-DP-032: PASS — <fresh checkpoint count>
Focused Phase 10.32 tests: <fresh count> passed
Domain suite: <fresh count> passed
Global suite: <fresh count> passed
Phase 10.32 Python delta: <fresh file count>; Ruff PASS; format PASS; syntax PASS
Independent audit: pending full-HEAD audit bundle
```

Document the architecture boundary in concise form:

```text
universal orchestration references existing conflicts
strict authority precedence
blocking unresolved conflicts fail closed
Phase 8 keeps contradiction truth ownership
10.33 owns events
no side effects/persistence/session mutation
```

Do **not** write "independently audited", "closed", or advance to 10.33.

- [ ] **Step 8: Update the requirements matrix**

Add `DP-032` and `AT-DP-032` to `docs/reference/domain-intelligence-requirements-matrix.md`.

The DP-032 row must state:

```text
Domain Conflict Resolution: universal immutable conflict references/cases/resolutions;
strict safety/permission/mandatory-rule/risk/primary/evidence/reliability/temporal/human
precedence; fail-closed unresolved blocking behavior; pure declarative user/human/postpone
decisions; upstream conflict preservation; no duplicate Cognitive contradiction resolution.
```

Mapping status at this point:

```text
VERIFIED_EXISTING
```

only for symbols actually implemented and verified. Audit state remains "independent audit pending".

- [ ] **Step 9: Verify documentation scope and commit**

Before staging:

```bash
git status --short
git diff --check
```

Expected documentation worktree scope:

```text
docs/roadmap/phase-10-domain-intelligence.md
docs/reference/domain-intelligence-requirements-matrix.md
```

Stage and commit:

```bash
git add \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md

git diff --cached --check
git commit -m "docs(domains): document phase 10.32 implementation"
```

- [ ] **Step 10: Verify clean audit HEAD**

```bash
test -z "$(git status --porcelain)"
git log -10 --oneline --decorate
git status --short --branch
```

Do not push or merge.

- [ ] **Step 11: Generate the full-HEAD audit bundle**

From repository root:

```bash
OUT_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads"
OUT="$OUT_DIR/phase-10.32-audit-v1.tar.gz"
HEAD_FULL="$(git rev-parse HEAD)"

rm -f "$OUT"

COPYFILE_DISABLE=1 git archive \
  --format=tar \
  --prefix="CMM-OS-phase-10.32/" \
  HEAD \
  | gzip -9 > "$OUT"

gzip -t "$OUT"
tar -tzf "$OUT" > /tmp/phase-10.32-audit-v1.contents.txt

if grep -E \
  '(^|/)\.git(/|$)|(^|/)\.venv(/|$)|(^|/)__pycache__(/|$)|(^|/)\.pytest_cache(/|$)|(^|/)\.ruff_cache(/|$)|\.py[co]$|(^|/)\._|\.tar\.gz$|(^|/)node_modules(/|$)' \
  /tmp/phase-10.32-audit-v1.contents.txt
then
  echo "ERROR: forbidden content found in audit bundle"
  exit 1
fi

shasum -a 256 "$OUT"
wc -l /tmp/phase-10.32-audit-v1.contents.txt
test -z "$(git status --porcelain)"
```

Report:

```text
AUDIT_HEAD=<full HEAD>
AUDIT_BUNDLE=<path>
AUDIT_BUNDLE_SHA256=<sha256>
ARCHIVE_ENTRIES=<count>
TRACKED_WORKTREE=CLEAN
```

- [ ] **Step 12: Stop for independent audit**

The implementation agent must stop here.

It must **not**:

```text
self-certify the independent audit
mark Phase 10.32 independently audited
advance top-level ROADMAP.md to 10.33
push
merge
```

The next actor is ChatGPT independent audit of the generated `phase-10.32-audit-v1.tar.gz`.

---

## Final Implementation-Agent Report Contract

When Task 9 is complete, the agent must return a concise evidence report containing:

```text
PHASE10_32_IMPLEMENTATION=COMPLETE_AUDIT_PENDING
SPEC_COMMIT=79fd145
IMPLEMENTATION_HEAD=<git HEAD>
AT_DP_032=PASS
AT_DP_032_CHECKPOINTS=<fresh exact count>
PHASE10_32_FOCUSED_TESTS=<fresh exact count>
PHASE10_31_AT_DP_031=22_PASS
DOMAIN_TESTS=<fresh exact count>
GLOBAL_TESTS=<fresh exact count>
PHASE10_32_PYTHON_DELTA_FILES=<fresh exact count>
PHASE10_32_RUFF=PASS
PHASE10_32_FORMAT_CHECK=PASS
PHASE10_32_SYNTAX_COMPILE=PASS
AUDIT_BUNDLE=<absolute path>
AUDIT_BUNDLE_SHA256=<sha256>
ARCHIVE_ENTRIES=<count>
TRACKED_WORKTREE=CLEAN
INDEPENDENT_AUDIT=PENDING
PUSH=NO
MERGE=NO
NEXT=UPLOAD_PHASE10_32_AUDIT_V1_TO_CHATGPT
```

If any test or quality gate is not green, do not emit this success contract. Report the exact failing command, root-cause status, current worktree scope, and stop after the smallest coherent diagnostic checkpoint.
