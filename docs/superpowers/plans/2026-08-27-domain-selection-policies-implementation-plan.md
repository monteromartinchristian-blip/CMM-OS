# Phase 10.31 — Domain Selection Policies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the frozen Phase 10.31 domain-selection policy so CMM OS selects primary/supporting domains deterministically, safely, audibly, and can represent pure before/after selection reevaluation.

**Architecture:** Add a first-class immutable `DomainSelectionPolicy` above the existing `DomainScoringPolicy`, keep `DomainResolutionPolicy` as the safety/authorization authority, and integrate selection semantics into the existing `DefaultDomainResolver` rather than creating a second engine. Session and active-goal ownership enter through structured builder-produced `DomainResolutionSignal` evidence; reevaluation is a pure typed comparison between two `DomainResolutionResult` objects.

**Tech Stack:** Python 3.10+, dataclasses, existing CMM OS domain contracts, pytest, Ruff, Git.

**Spec:** `docs/superpowers/specs/2026-08-27-domain-selection-policies-design.md`

## Global Constraints

- Safety / authorization / availability always dominate selection preference.
- No free-text classifier, LLM router, second resolver, new cross-domain engine, goal store, session store, or workflow persistence.
- Phase 10.31 must not pre-implement Phase 10.32 Domain Conflict Resolution, Phase 10.33 Domain Events, or Phase 10.34 persistent Domain Sessions.
- Default `minimum_primary_confidence = 0.70`.
- Default `minimum_supporting_confidence = 0.55`.
- Default `maximum_supporting_domains = 3`.
- Default `fallback_domain = domain:general`.
- Initial ambiguity strategy is exactly `clarify_or_fallback`.
- Existing General fail-closed fallback behavior must not weaken.
- High-impact routing uses the most restrictive applicable confidence floor.
- Reevaluation is pure and never executes operations or mutates session state.
- `DomainSelectionTransition` must bind `previous_resolution_id` and `new_resolution_id`.
- No push or merge during implementation.

---

## File Structure

### New files

- `cmm/domains/selection_contracts.py`
  - Owns `DomainSelectionPolicy` and `DomainSelectionTransition`.
  - Contains only immutable contract validation/serialization; no resolver execution.

- `cmm/domains/selection.py`
  - Owns pure selection/transition helpers reused by `DefaultDomainResolver`.
  - No registry, store, filesystem, network, LLM, workflow, or operation execution.

- `tests/domains/test_domain_selection_policy.py`
  - Contract defaults, strict validation, serialization, immutability.

- `tests/domains/test_domain_selection_transition.py`
  - Pure before/after reevaluation contract and reason ordering.

- `tests/domains/test_domain_selection_resolver.py`
  - Explicit/session/goal/confidence/multi-domain/high-impact/fallback integration.

- `tests/domains/test_domain_selection_policy_dp031_acceptance.py`
  - Connected AT-DP-031 acceptance gate.

- `tests/domains/test_domain_selection_policy_adversarial.py`
  - Adversarial boundaries: safety precedence, fallback bypass prevention, duplicate signal amplification, hard supporting cap, deterministic ties.

### Modified files

- `cmm/domains/resolution_builder.py`
  - Accepts `session_domain` and `active_goal_domain`.
  - Emits canonical structured `session` / `goal` signals without consulting live stores.

- `cmm/domains/resolver.py`
  - Consumes `DomainSelectionPolicy`.
  - Applies explicit-first, structured session/goal semantics, confidence gates, hard supporting limit, and most-restrictive high-impact confidence.

- `cmm/domains/__init__.py`
  - Public exports.

- `docs/reference/domain-intelligence-requirements-matrix.md`
  - Add DP-031 / AT-DP-031 implementation evidence only after tests are green.

- `docs/roadmap/phase-10-domain-intelligence.md`
  - Record final implemented status/evidence without changing later-phase scope.

- `ROADMAP.md`
  - Advance next milestone only after implementation verification and independent closure audit, not during normal implementation commits.

---

### Task 1: Immutable selection contracts

**Files:**
- Create: `cmm/domains/selection_contracts.py`
- Create: `tests/domains/test_domain_selection_policy.py`

**Interfaces:**

Produces:

```python
@dataclass(frozen=True, slots=True)
class DomainSelectionPolicy:
    name: str = "default"
    explicit_domain_priority: bool = True
    session_domain_priority: bool = True
    goal_domain_priority: bool = True
    allow_multi_domain: bool = True
    maximum_supporting_domains: int = 3
    minimum_primary_confidence: float = 0.70
    minimum_supporting_confidence: float = 0.55
    fallback_domain: DomainId = DomainId.from_str("domain:general")
    ambiguity_strategy: str = "clarify_or_fallback"
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DomainSelectionPolicy": ...
```

Validation requirements:

```text
name                         non-empty string
all policy flags             strict bool, bool-as-int rejected
maximum_supporting_domains   int >= 0, bool rejected
confidence values            finite float in [0, 1], bool rejected
fallback_domain              DomainId or canonical domain string
ambiguity_strategy           exactly "clarify_or_fallback"
metadata                     JSON-safe, deep-frozen, credential-like keys rejected
unknown serialized fields    rejected
```

- [ ] **Step 1: Write RED default-contract tests**

```python
def test_domain_selection_policy_defaults_are_canonical():
    policy = DomainSelectionPolicy()

    assert policy.name == "default"
    assert policy.explicit_domain_priority is True
    assert policy.session_domain_priority is True
    assert policy.goal_domain_priority is True
    assert policy.allow_multi_domain is True
    assert policy.maximum_supporting_domains == 3
    assert policy.minimum_primary_confidence == 0.70
    assert policy.minimum_supporting_confidence == 0.55
    assert str(policy.fallback_domain) == "domain:general"
    assert policy.ambiguity_strategy == "clarify_or_fallback"
```

- [ ] **Step 2: Write RED validation and round-trip tests**

Cover at minimum:

```python
@pytest.mark.parametrize(
    "field,value",
    [
        ("explicit_domain_priority", 1),
        ("session_domain_priority", 1),
        ("goal_domain_priority", 1),
        ("allow_multi_domain", 1),
        ("maximum_supporting_domains", True),
        ("minimum_primary_confidence", True),
        ("minimum_supporting_confidence", True),
    ],
)
def test_policy_rejects_bool_int_confusion(field, value):
    with pytest.raises(DomainContractValidationError):
        DomainSelectionPolicy(**{field: value})
```

Also prove:

```text
minimum_primary_confidence < 0 or > 1 -> reject
minimum_supporting_confidence < 0 or > 1 -> reject
maximum_supporting_domains < 0 -> reject
unknown ambiguity strategy -> reject
unknown from_dict field -> reject
credential-like metadata key at any depth -> reject
nested metadata cannot be mutated
to_dict -> from_dict -> equal canonical values
```

- [ ] **Step 3: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_policy.py
```

Expected: collection/import failure because `DomainSelectionPolicy` does not exist.

- [ ] **Step 4: Implement the minimal contract**

Follow the existing immutable contract patterns in:

```text
cmm/domains/resolver_contracts.py
cmm/domains/resolution_contracts.py
```

Reuse common validation helpers where dependency direction permits; do not duplicate a second serialization framework.

- [ ] **Step 5: Run GREEN + Ruff**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_policy.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/selection_contracts.py \
  tests/domains/test_domain_selection_policy.py

git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add \
  cmm/domains/selection_contracts.py \
  tests/domains/test_domain_selection_policy.py

git diff --cached --check
git commit -m "feat(domains): add domain selection policy contract"
```

---

### Task 2: Pure selection transition and exact resolution identity

**Files:**
- Modify: `cmm/domains/selection_contracts.py`
- Create: `cmm/domains/selection.py`
- Create: `tests/domains/test_domain_selection_transition.py`

**Interfaces:**

Produces:

```python
@dataclass(frozen=True, slots=True)
class DomainSelectionTransition:
    previous_resolution_id: str
    new_resolution_id: str
    previous_primary_domain: DomainId | None
    new_primary_domain: DomainId | None
    previous_supporting_domains: tuple[DomainId, ...] = ()
    new_supporting_domains: tuple[DomainId, ...] = ()
    primary_changed: bool = False
    supporting_changed: bool = False
    reason_codes: tuple[str, ...] = ()
    requires_recomposition: bool = False
    requires_session_update: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "DomainSelectionTransition": ...
```

Pure helper:

```python
def build_domain_selection_transition(
    previous: DomainResolutionResult,
    current: DomainResolutionResult,
) -> DomainSelectionTransition:
    ...
```

Stable reason order:

```text
DOMAIN_SELECTION_REEVALUATED
DOMAIN_SELECTION_PRIMARY_CHANGED
DOMAIN_SELECTION_COMPOSITION_CHANGED
```

Rules:

```text
no semantic domain change
  -> reason_codes=()
  -> requires_recomposition=False
  -> requires_session_update=False

primary change
  -> REEVALUATED + PRIMARY_CHANGED
  -> requires_recomposition=True
  -> requires_session_update=True

supporting-only change
  -> REEVALUATED + COMPOSITION_CHANGED
  -> requires_recomposition=True
  -> requires_session_update=True

primary + supporting change
  -> all three codes in the stable order above
```

- [ ] **Step 1: Write RED transition tests**

Use two real `DomainResolutionResult` fixtures with different IDs.

Mandatory assertion:

```python
transition = build_domain_selection_transition(previous, current)

assert transition.previous_resolution_id == previous.id
assert transition.new_resolution_id == current.id
```

Also prove serialization, immutability, strict IDs, no duplicate reason codes, and stable supporting-domain ordering according to the resolution result.

- [ ] **Step 2: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_transition.py
```

- [ ] **Step 3: Implement pure comparison**

Implementation must read only the two supplied `DomainResolutionResult` values. It must not:

```text
load a session
update a session
call a workflow
execute an operation
access registry/store/network/filesystem
generate a replacement resolution
```

- [ ] **Step 4: Run GREEN + Ruff**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_transition.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/selection.py \
  cmm/domains/selection_contracts.py \
  tests/domains/test_domain_selection_transition.py

git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add \
  cmm/domains/selection.py \
  cmm/domains/selection_contracts.py \
  tests/domains/test_domain_selection_transition.py

git diff --cached --check
git commit -m "feat(domains): add selection reevaluation transition"
```

---

### Task 3: Canonical structured session and active-goal signals

**Files:**
- Modify: `cmm/domains/resolution_builder.py`
- Create: `tests/domains/test_domain_selection_resolver.py`

**Interfaces:**

Extend:

```python
DomainResolutionContextBuilder.build(
    ...,
    session_domain: DomainId | None = None,
    active_goal_domain: DomainId | None = None,
    ...
) -> DomainResolutionContext
```

Canonical builder-generated signals use the existing contract:

```python
DomainResolutionSignal(
    kind="session",
    source="domain_resolution_context_builder",
    value="session_domain",
    domain_ids=(session_domain,),
    confidence=1.0,
    weight=10.0,
    provenance={"source": "explicit_session_domain"},
)
```

and:

```python
DomainResolutionSignal(
    kind="goal",
    source="domain_resolution_context_builder",
    value="active_goal_domain",
    domain_ids=(active_goal_domain,),
    confidence=1.0,
    weight=10.0,
    provenance={"source": "explicit_active_goal_domain"},
)
```

The exact builder signal is added only once for a semantically equivalent
`(kind, domain)` pair so caller-provided evidence cannot accidentally
double-amplify the canonical session/goal binding.

- [ ] **Step 1: Write RED builder tests**

Prove:

```text
session_domain -> one structured session signal
active_goal_domain -> one structured goal signal
both -> two signals
registry ACTIVE alone -> no canonical session-domain signal
goal_id alone -> no canonical goal-domain signal
duplicate equivalent supplied signal -> no double canonical amplification
builder remains snapshot-only
```

- [ ] **Step 2: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_resolver.py \
  -k 'builder or session_signal or goal_signal'
```

- [ ] **Step 3: Implement canonical signal synthesis**

Add a private pure helper in `resolution_builder.py`, for example:

```python
def _append_domain_signal_once(
    signals: tuple[DomainResolutionSignal, ...],
    *,
    kind: str,
    domain_id: DomainId | None,
    value: str,
    provenance_source: str,
) -> tuple[DomainResolutionSignal, ...]:
    ...
```

Deduplication key for this canonical synthesis is semantic:

```text
signal.kind == kind
and any(signal_domain.slug == domain_id.slug for signal_domain in signal.domain_ids)
```

Do not inspect free text.

- [ ] **Step 4: Run GREEN + existing builder regressions**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_resolver.py

BUILDER_TESTS=("${(@f)$(rg -l 'DomainResolutionContextBuilder' tests/domains --glob '*.py' | sort)}")
if (( ${#BUILDER_TESTS[@]} > 0 )); then
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
    -p no:cacheprovider -q "${BUILDER_TESTS[@]}"
fi

.venv/bin/ruff check --target-version py310 \
  cmm/domains/resolution_builder.py \
  tests/domains/test_domain_selection_resolver.py

git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add \
  cmm/domains/resolution_builder.py \
  tests/domains/test_domain_selection_resolver.py

git diff --cached --check
git commit -m "feat(domains): add structured session and goal signals"
```

---

### Task 4: Integrate DomainSelectionPolicy into DefaultDomainResolver

**Files:**
- Modify: `cmm/domains/resolver.py`
- Modify: `cmm/domains/selection.py`
- Modify: `tests/domains/test_domain_selection_resolver.py`

**Interfaces:**

Extend constructor without breaking the protocol:

```python
class DefaultDomainResolver:
    def __init__(
        self,
        *,
        scorer: DomainCandidateScorer | None = None,
        scoring_policy: DomainScoringPolicy | None = None,
        selection_policy: DomainSelectionPolicy | None = None,
        fallback_domain: DomainId | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        ...
```

Expose:

```python
@property
def selection_policy(self) -> DomainSelectionPolicy:
    ...
```

Backward compatibility:

```text
fallback_domain remains accepted
selection_policy=None -> canonical DomainSelectionPolicy()
fallback_domain supplied + selection_policy absent -> effective policy uses supplied fallback
fallback_domain supplied + selection_policy supplied with different fallback -> configuration error
fallback_domain property -> effective selection-policy fallback
```

- [ ] **Step 1: Write RED explicit-first tests**

Mandatory scenario:

```text
eligible explicit A has lower raw score than eligible inferred B
-> A is primary
```

Also:

```text
explicit denied/unauthorized A
-> explicit preference cannot bypass safety

two eligible explicit domains
-> AMBIGUOUS, requires_clarification=True
-> no alphabetical semantic winner
```

- [ ] **Step 2: Write RED session/goal tests**

Mandatory:

```text
single valid session-domain signal -> session candidate can become primary
single valid goal-domain signal -> goal candidate can become primary
same session+goal domain -> same primary, no duplicate-domain composition
session and goal disagree + no clear evidence lead -> ambiguous
session and goal disagree + one has clear normal evidence lead -> clear candidate may resolve
registry active domain without session signal -> not Session Continuity
```

- [ ] **Step 3: Write RED confidence-gate tests**

Mandatory:

```text
ordinary inferred primary confidence 0.69 -> cannot RESOLVE as inferred primary
ordinary inferred primary confidence 0.70+ -> may resolve
explicit eligible primary may win below 0.70 but retains recorded confidence
```

Use deterministic structured signals/weights; do not scan free text.

- [ ] **Step 4: Implement priority selection helpers**

Keep orchestration in the existing resolver, but move pure candidate-set logic into `selection.py`.

Required helper boundary:

```python
def domain_signal_candidates(
    context: DomainResolutionContext,
    eligible: Sequence[DomainCandidateScore],
    *,
    kind: str,
) -> tuple[DomainCandidateScore, ...]:
    ...
```

and an explicit-candidate helper equivalent to:

```python
def explicit_candidates(
    context: DomainResolutionContext,
    eligible: Sequence[DomainCandidateScore],
) -> tuple[DomainCandidateScore, ...]:
    ...
```

No helper may access stores or registry.

- [ ] **Step 5: Apply primary confidence gating**

Normal inferred resolution must filter/route candidates by:

```python
candidate.confidence >= selection_policy.minimum_primary_confidence
```

Do not remove the existing raw-score eligibility gate. Selection confidence is an additional gate, not a replacement for structural scoring.

- [ ] **Step 6: Run GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_resolver.py

RESOLVER_TESTS=("${(@f)$(rg -l 'DefaultDomainResolver|DomainCandidateScorer|DomainScoringPolicy' tests/domains --glob '*.py' | sort)}")
if (( ${#RESOLVER_TESTS[@]} > 0 )); then
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
    -p no:cacheprovider -q "${RESOLVER_TESTS[@]}"
fi

.venv/bin/ruff check --target-version py310 \
  cmm/domains/resolver.py \
  cmm/domains/selection.py \
  tests/domains/test_domain_selection_resolver.py

git diff --check
```

- [ ] **Step 7: Commit**

```bash
git add \
  cmm/domains/resolver.py \
  cmm/domains/selection.py \
  tests/domains/test_domain_selection_resolver.py

git diff --cached --check
git commit -m "feat(domains): enforce domain selection precedence"
```

---

### Task 5: High-impact confidence and hard multi-domain boundaries

**Files:**
- Modify: `cmm/domains/resolver.py`
- Modify: `cmm/domains/selection.py`
- Modify: `tests/domains/test_domain_selection_resolver.py`
- Create: `tests/domains/test_domain_selection_policy_adversarial.py`

**Interfaces:**

Effective high-impact primary threshold:

```python
effective_minimum = max(
    selection_policy.minimum_primary_confidence,
    scoring_policy.high_impact_minimum_confidence,
    context.system_policy.minimum_confidence
        if context.system_policy
        and context.system_policy.minimum_confidence is not None
        else 0.0,
)
```

Supporting eligibility:

```text
eligible
not rejected
not primary
score >= scoring_policy.minimum_resolution_score
confidence >= selection_policy.minimum_supporting_confidence
within existing supporting_margin
allow_multi_domain == True
```

Hard bound:

```text
len(supporting_domains) <= selection_policy.maximum_supporting_domains
```

Required domains may not overflow this bound silently.

- [ ] **Step 1: Write RED high-impact tests**

Prove:

```text
selection floor 0.70 + scoring high-impact 0.80 -> effective 0.80
system minimum 0.90 -> effective 0.90
system minimum 0.60 does NOT lower 0.80
low-confidence high-impact domain -> clarification/fallback using existing safe semantics
```

- [ ] **Step 2: Write RED multi-domain tests**

Prove:

```text
allow_multi_domain=False -> ()
supporting confidence 0.54 -> excluded
supporting confidence 0.55+ -> eligible when margin/score pass
default hard maximum -> 3
configured hard maximum 1 -> <=1
primary never appears in supporting
deterministic supporting order
```

- [ ] **Step 3: Write RED required-domain overflow adversarial test**

Construct more eligible required supporting domains than the configured hard maximum.

Expected behavior:

```text
no overflow
no silent truncation pretending policy success
explicit fail-closed policy-conflict result/reason
```

Use stable reason code:

```text
DOMAIN_SELECTION_REQUIRED_DOMAIN_LIMIT_CONFLICT
```

Do not implement general Phase 10.32 conflict resolution.

- [ ] **Step 4: Implement minimal behavior**

Preserve existing General fail-closed guards exactly. Do not hardcode Health, Legal, or Financial slugs.

- [ ] **Step 5: Run focused + fallback regression**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_resolver.py \
  tests/domains/test_domain_selection_policy_adversarial.py

FALLBACK_TESTS=("${(@f)$(rg -l 'DOMAIN_FALLBACK_SELECTED|fallback_used|General Domain|domain:general' tests/domains --glob '*.py' | sort)}")
if (( ${#FALLBACK_TESTS[@]} > 0 )); then
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
    -p no:cacheprovider -q "${FALLBACK_TESTS[@]}"
fi

.venv/bin/ruff check --target-version py310 \
  cmm/domains/resolver.py \
  cmm/domains/selection.py \
  tests/domains/test_domain_selection_resolver.py \
  tests/domains/test_domain_selection_policy_adversarial.py

git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add \
  cmm/domains/resolver.py \
  cmm/domains/selection.py \
  tests/domains/test_domain_selection_resolver.py \
  tests/domains/test_domain_selection_policy_adversarial.py

git diff --cached --check
git commit -m "feat(domains): enforce selection confidence boundaries"
```

---

### Task 6: Public API, composer/downstream compatibility, and reevaluation proof

**Files:**
- Modify: `cmm/domains/__init__.py`
- Modify: `tests/domains/test_domain_selection_transition.py`
- Modify: `tests/domains/test_domain_selection_resolver.py`

**Interfaces:**

Public exports at minimum:

```python
DomainSelectionPolicy
DomainSelectionTransition
build_domain_selection_transition
```

- [ ] **Step 1: Write RED public-import tests**

```python
from cmm.domains import (
    DomainSelectionPolicy,
    DomainSelectionTransition,
    build_domain_selection_transition,
)
```

All must import in a fresh interpreter.

- [ ] **Step 2: Write downstream recomposition proof**

Build:

```text
previous resolution -> composition A
new resolution -> composition B
DomainSelectionTransition(previous,new)
```

Assert:

```text
transition links exact previous/new resolution IDs
transition requires recomposition
new composition drives profile inputs
new composition drives permission inputs
new composition drives rule-selection inputs
no operation execution occurs during transition construction
```

Use actual existing composer/profile/rule/permission APIs rather than fake strings where a shared contract already exists.

- [ ] **Step 3: Implement exports only**

No additional engine or adapter.

- [ ] **Step 4: Run integration regressions**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_transition.py \
  tests/domains/test_domain_selection_resolver.py

DOWNSTREAM_TESTS=("${(@f)$(rg -l 'DefaultDomainComposer|DomainPermissionResolver|DefaultDomainProfileResolver|rule_selection' tests/domains --glob '*.py' | sort)}")
if (( ${#DOWNSTREAM_TESTS[@]} > 0 )); then
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
    -p no:cacheprovider -q "${DOWNSTREAM_TESTS[@]}"
fi

.venv/bin/python -c \
  'from cmm.domains import DomainSelectionPolicy, DomainSelectionTransition, build_domain_selection_transition; print("selection_public_api=OK")'

.venv/bin/ruff check --target-version py310 \
  cmm/domains/__init__.py \
  cmm/domains/selection.py \
  cmm/domains/selection_contracts.py

git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add \
  cmm/domains/__init__.py \
  tests/domains/test_domain_selection_transition.py \
  tests/domains/test_domain_selection_resolver.py

git diff --cached --check
git commit -m "feat(domains): expose selection policy public api"
```

---

### Task 7: Connected AT-DP-031 acceptance

**Files:**
- Create: `tests/domains/test_domain_selection_policy_dp031_acceptance.py`
- Modify only if a real defect is exposed:
  - `cmm/domains/resolver.py`
  - `cmm/domains/selection.py`
  - `cmm/domains/resolution_builder.py`

**Connected acceptance chain:**

```text
registry snapshot
-> DomainResolutionContextBuilder
-> explicit/session/goal structured evidence
-> DefaultDomainResolver
-> DomainResolutionResult
-> DefaultDomainComposer
-> downstream profile/permission/rule inputs
-> new structured information
-> second DomainResolutionContext
-> second DomainResolutionResult
-> DomainSelectionTransition
-> exact previous_resolution_id/new_resolution_id
-> recomposition requirement
-> session-update requirement only as declarative output
-> no operation replay
```

- [ ] **Step 1: Write the connected acceptance test**

The test must prove all 22 frozen AT-DP-031 checkpoints from the design spec.

At minimum use actual public/shared contracts for:

```text
DomainResolutionContextBuilder
DomainResolutionSignal
DomainSelectionPolicy
DefaultDomainResolver
DefaultDomainComposer
DomainSelectionTransition
```

- [ ] **Step 2: Add named acceptance markers**

The test output/assertions must make failures localizable for:

```text
AT_DP_031_01_POLICY_CONTRACT
AT_DP_031_02_EXPLICIT_PRIORITY
AT_DP_031_03_SAFETY_PRECEDENCE
AT_DP_031_04_EXPLICIT_AMBIGUITY
AT_DP_031_05_SESSION_CONTINUITY
AT_DP_031_06_GOAL_PRIORITY
AT_DP_031_07_SESSION_GOAL_CONFLICT
AT_DP_031_08_PRIMARY_CONFIDENCE
AT_DP_031_09_HIGH_IMPACT_CONFIDENCE
AT_DP_031_10_SUPPORTING_CONFIDENCE
AT_DP_031_11_MULTI_DOMAIN_DISABLE
AT_DP_031_12_HARD_SUPPORTING_LIMIT
AT_DP_031_13_GENERAL_FALLBACK
AT_DP_031_14_FAIL_CLOSED_FALLBACK
AT_DP_031_15_AMBIGUITY_STRATEGY
AT_DP_031_16_TRANSITION_IDENTITY_AND_CHANGE
AT_DP_031_17_TRANSITION_REASONS
AT_DP_031_18_RECOMPOSITION_REQUIRED
AT_DP_031_19_SESSION_UPDATE_DECLARATIVE
AT_DP_031_20_NO_OPERATION_REPLAY
AT_DP_031_21_SHARED_REGRESSIONS
AT_DP_031_22_GLOBAL_QUALITY_GATE
```

Do not fake PASS constants disconnected from execution; each marker must be backed by a real assertion/path.

- [ ] **Step 3: Run RED/GREEN until connected acceptance passes**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_policy_dp031_acceptance.py
```

- [ ] **Step 4: Run adversarial gate**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_policy_adversarial.py
```

- [ ] **Step 5: Commit acceptance**

```bash
git add \
  tests/domains/test_domain_selection_policy_dp031_acceptance.py \
  tests/domains/test_domain_selection_policy_adversarial.py \
  cmm/domains/resolver.py \
  cmm/domains/selection.py \
  cmm/domains/resolution_builder.py

git diff --cached --check
git diff --cached --name-status
git commit -m "test(domains): connect DP-031 selection acceptance"
```

Only stage production files above if this task actually changed them.

---

### Task 8: Documentation evidence and full pre-audit verification

**Files:**
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Do not advance `ROADMAP.md` next milestone until independent closure audit passes.

**Documentation evidence to add:**

```text
DP-031 — implemented
AT-DP-031 — PASS
selection policy contract
explicit-first safety precedence
structured session continuity
structured goal priority
0.70 primary confidence
0.55 supporting confidence
hard max 3 supporting domains
most-restrictive high-impact confidence
fail-closed General fallback
typed reevaluation transition
previous_resolution_id/new_resolution_id binding
no operation replay
```

- [ ] **Step 1: Run focused Phase 10.31 suite**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_selection_policy.py \
  tests/domains/test_domain_selection_transition.py \
  tests/domains/test_domain_selection_resolver.py \
  tests/domains/test_domain_selection_policy_dp031_acceptance.py \
  tests/domains/test_domain_selection_policy_adversarial.py
```

- [ ] **Step 2: Run all domain tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains
```

- [ ] **Step 3: Run global suite**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q
```

- [ ] **Step 4: Run lint / format / syntax gates**

```bash
.venv/bin/ruff check --target-version py310 \
  cmm/domains \
  tests/domains

.venv/bin/ruff format --check \
  cmm/domains \
  tests/domains

.venv/bin/python - <<'PY'
from pathlib import Path

count = 0
for root in (Path("cmm"), Path("tests")):
    for path in sorted(root.rglob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
        count += 1
print(f"compiled_in_memory={count}")
PY

git diff --check
```

- [ ] **Step 5: Update canonical docs with exact observed counts/results**

Write only observed test counts and commit hashes. Do not invent counts in advance.

- [ ] **Step 6: Verify scope**

```bash
git status --short
git diff --check
git diff --stat
```

- [ ] **Step 7: Commit implementation evidence**

```bash
git add \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md

git diff --cached --check
git commit -m "docs(domains): record phase 10.31 implementation evidence"
```

---

## Final Implementation Gate Before Independent Audit

The implementation worker must finish with all of these true:

```text
PHASE10_31_IMPLEMENTATION=COMPLETE
DP_031=IMPLEMENTED
AT_DP_031=PASS
ADVERSARIAL_GATE=PASS
DOMAIN_TESTS=PASS
GLOBAL_TESTS=PASS
RUFF=PASS
FORMAT_CHECK=PASS
SYNTAX_COMPILE=PASS
TRACKED_WORKTREE=CLEAN
PUSH=NO
MERGE=NO
NEXT=BUILD_PHASE10_31_AUDIT_BUNDLE
```

Do **not** mark Phase 10.31 closed yet.

Closure sequence remains:

```text
implementation complete
-> generate full-HEAD TAR.GZ audit bundle
-> independent ChatGPT audit
-> remediate findings if any
-> re-audit until PASS
-> closure documentation
-> closure commit
-> only then advance ROADMAP next milestone
```
