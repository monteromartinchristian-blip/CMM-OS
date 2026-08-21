# Phase 10.25 — Concerns Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `domain:concerns` so CMM OS can support worries, fears, uncertainty, recurring concerns, requests for reassurance/perspective, practical problem-solving, and open-ended “talk it through” conversations without collapsing them into risk analysis, forced action, false reassurance, or pathologization.

**Architecture:** Create exactly one 14-module `cmm/domains/concerns/` package using the hardened Phase 10 Domain Pack pattern. Reuse shared registries, Cognitive Layer contracts, Agent Runtime permission contracts, Workflow Engine contracts, Domain Memory Integration, Domain Presentation, Domain Trace, and cross-domain composition. `catalog.py` is the single source of truth; semantic helpers are pure/deterministic; registration is validation-first and atomic with complete rollback.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing `cmm.cognitive`, `cmm.domains`, `cmm.agent_runtime`, `cmm.workflows`.

**Spec:** `docs/superpowers/specs/2026-08-21-concerns-domain-design.md`

**Canonical acceptance:** `DP-025` / `AT-DP-025`

## Global Constraints

- Canonical ID: `domain:concerns`; namespace: `concerns.*`; version: `1.0.0`.
- Exactly 17 entities, 10 resources, 14 rules, 13 operations, 8 workflows.
- Exactly 14 production modules: `__init__.py`, `bootstrap.py`, `catalog.py`, `definition.py`, `integration.py`, `memory.py`, `operations.py`, `permissions.py`, `presentation.py`, `profile.py`, `resources.py`, `rules.py`, `trace.py`, `workflows.py`.
- `catalog.py` is the only canonical catalog source.
- Canonical profile: `ConcernSupportProfile`.
- No parallel planner, Agent Runtime, memory store, Knowledge Store/Graph, workflow engine, permission engine, temporal engine, question engine, confidence engine, or conversation engine.
- No import-time registration.
- Operations are UNAVAILABLE by default unless implementations are explicitly injected.
- Reassurance is allowed when evidence supports it; false certainty is forbidden.
- Repetition is not pathology; no automatic OCD/anxiety/compulsion classification.
- Emotional validation must not promote interpretation to fact.
- Risk is proportional and specialized risk remains owned by the specialized domain.
- Questions are only materially useful questions.
- No forced action, monitoring plan, or final conclusion.
- Concern/session state is not semantic memory.
- No direct memory write; shared proposal/binding contracts only.
- No direct private-store access from other domains.
- Unknown/malformed authorization fails closed.
- Duplicate/malformed evidence cannot inflate certainty, reassurance, risk, or hypothesis support.
- Equivalent evidence sets must be order invariant.
- Public outputs are strict JSON-safe and caller inputs are not mutated.
- Presentation never changes epistemic content, reassurance, risk, permissions, action state, or memory state.
- Trace is reference-only; never chain-of-thought.
- Standard bootstrap reuses the exact General registries; General remains fallback.
- Strict TDD: RED → verify RED → GREEN → verify GREEN → refactor.
- No `TODO`, `TBD`, `FIXME`, placeholders, or deferred semantic requirements.

---

# Canonical Catalog

```python
CANONICAL_CONCERNS_ENTITY_TYPES = (
    "concern", "situation", "trigger", "emotion", "fear", "need",
    "support_need", "fact", "interpretation", "hypothesis", "scenario",
    "evidence", "uncertainty", "risk", "desired_outcome", "option", "action",
)

CANONICAL_CONCERNS_RESOURCE_IDS = (
    "concerns.user_message", "concerns.conversation", "concerns.note",
    "concerns.journal_entry", "concerns.memory_entry", "concerns.event",
    "concerns.goal", "concerns.decision", "concerns.domain_result",
    "concerns.external_source",
)

CANONICAL_CONCERNS_RULE_IDS = (
    "concerns.understand_before_intervene",
    "concerns.emotional_validation",
    "concerns.experience_reality_separation",
    "concerns.support_need_calibration",
    "concerns.contextual_question",
    "concerns.uncertainty_preservation",
    "concerns.evidence_calibrated_reassurance",
    "concerns.proportional_risk",
    "concerns.no_catastrophic_escalation",
    "concerns.no_false_reassurance",
    "concerns.repetition_without_pathologizing",
    "concerns.agency_without_pressure",
    "concerns.directness_without_harshness",
    "concerns.immediate_risk_escalation",
)

CANONICAL_CONCERNS_RULE_NAMES = (
    "UnderstandBeforeInterveneRule",
    "EmotionalValidationRule",
    "ExperienceRealitySeparationRule",
    "SupportNeedCalibrationRule",
    "ContextualQuestionRule",
    "UncertaintyPreservationRule",
    "EvidenceCalibratedReassuranceRule",
    "ProportionalRiskRule",
    "NoCatastrophicEscalationRule",
    "NoFalseReassuranceRule",
    "RepetitionWithoutPathologizingRule",
    "AgencyWithoutPressureRule",
    "DirectnessWithoutHarshnessRule",
    "ImmediateRiskEscalationRule",
)

CANONICAL_CONCERNS_OPERATION_IDS = (
    "concerns.understand_concern",
    "concerns.infer_support_need",
    "concerns.map_lived_experience",
    "concerns.separate_reality_interpretation",
    "concerns.explore_hypotheses",
    "concerns.calibrate_uncertainty",
    "concerns.evaluate_reassurance",
    "concerns.evaluate_risk",
    "concerns.identify_open_questions",
    "concerns.explore_options",
    "concerns.prepare_next_step",
    "concerns.review_recurring_concern",
    "concerns.prepare_professional_discussion",
)

CANONICAL_CONCERNS_WORKFLOW_IDS = (
    "concerns.open_concern_conversation",
    "concerns.talk_it_through",
    "concerns.reality_check",
    "concerns.reassurance_review",
    "concerns.practical_problem_solving",
    "concerns.decision_under_uncertainty",
    "concerns.recurring_concern_review",
    "concerns.professional_discussion_preparation",
)
```

Workflow display names:
`Open Concern Conversation`, `Talk It Through`, `Reality Check`, `Reassurance Review`, `Practical Problem Solving`, `Decision Under Uncertainty`, `Recurring Concern Review`, `Professional Discussion Preparation`.

---

# File Map

## Production

Create:

```text
cmm/domains/concerns/__init__.py
cmm/domains/concerns/bootstrap.py
cmm/domains/concerns/catalog.py
cmm/domains/concerns/definition.py
cmm/domains/concerns/integration.py
cmm/domains/concerns/memory.py
cmm/domains/concerns/operations.py
cmm/domains/concerns/permissions.py
cmm/domains/concerns/presentation.py
cmm/domains/concerns/profile.py
cmm/domains/concerns/resources.py
cmm/domains/concerns/rules.py
cmm/domains/concerns/trace.py
cmm/domains/concerns/workflows.py
```

## Focused tests

Create:

```text
tests/domains/test_concerns_domain_catalog.py
tests/domains/test_concerns_domain_definition.py
tests/domains/test_concerns_domain_profile.py
tests/domains/test_concerns_domain_resources.py
tests/domains/test_concerns_domain_understanding.py
tests/domains/test_concerns_domain_support_need.py
tests/domains/test_concerns_domain_epistemics.py
tests/domains/test_concerns_domain_reassurance.py
tests/domains/test_concerns_domain_recurrence.py
tests/domains/test_concerns_domain_risk_agency.py
tests/domains/test_concerns_domain_operations.py
tests/domains/test_concerns_domain_workflows.py
tests/domains/test_concerns_domain_permissions.py
tests/domains/test_concerns_domain_memory.py
tests/domains/test_concerns_domain_presentation.py
tests/domains/test_concerns_domain_trace.py
tests/domains/test_concerns_domain_cross_domain.py
tests/domains/test_concerns_domain_integration.py
tests/domains/test_concerns_domain_rollback.py
tests/domains/test_concerns_domain_validation_first_matrix.py
tests/domains/test_concerns_domain_adversarial.py
tests/domains/test_concerns_domain_dp025_acceptance.py
```

---

# Task 1 — Catalog + immutable DomainDefinition

**Files:** `catalog.py`, `definition.py`, catalog/definition tests.

- [ ] RED: tests asserting exact counts, no duplicates, exact `concerns.` prefixes, exact workflow names, and exactly 14 package modules after package completion.
- [ ] Verify RED: `pytest -q tests/domains/test_concerns_domain_catalog.py`.
- [ ] GREEN: implement `catalog.py`; derive `CONCERNS_RESOURCE_KINDS` and workflow-name tuple from catalog data, never redeclare.
- [ ] RED: definition tests for `domain:concerns`, `DomainKind.PERSONAL`, `ConcernSupportProfile`, phase `10.25`, deterministic definition and exact catalog reconciliation.
- [ ] GREEN: implement `build_concerns_domain_definition()` using shared `DomainDefinition`, `DomainMetadata`, `DomainCapability`.
- [ ] Capabilities: `concern_understanding`, `support_need_resolution`, `reality_check`, `evidence_calibrated_reassurance`, `uncertainty_support`, `risk_calibration`, `problem_solving`, `decision_support`, `recurring_concern_review`, `professional_discussion_preparation`.
- [ ] Verify GREEN + Ruff + `git diff --check`.
- [ ] Commit: `feat(domains): define concerns domain catalog`.

Representative test:

```python
def test_definition_reconciles_catalog_exactly():
    definition = build_concerns_domain_definition()
    assert tuple(definition.resources) == CANONICAL_CONCERNS_RESOURCE_IDS
    assert tuple(definition.rules) == CANONICAL_CONCERNS_RULE_IDS
    assert tuple(definition.operations) == CANONICAL_CONCERNS_OPERATION_IDS
    assert tuple(definition.workflows) == CANONICAL_CONCERNS_WORKFLOW_IDS
```

---

# Task 2 — Resources + ConcernSupportProfile

**Files:** `resources.py`, `profile.py`, resource/profile tests.

Produce:
- `build_concerns_resource_definitions()`
- `CONCERNS_PROFILE_ID = "concerns.profile"`
- `CONCERNS_PROFILE_NAME = "ConcernSupportProfile"`
- `build_concerns_profile()`

- [ ] RED resources: exactly 10, deterministic, shared contracts, `domain_result` as cross-domain projection boundary, `memory_entry` as provenance not truth, `external_source` not external-search authorization.
- [ ] GREEN resources: follow Reflection resource-factory pattern; no import of another specialized domain's resource module.
- [ ] RED profile: all 14 required rules, high sensitivity, uncertainty allowed, low default action pressure/alarm, no automatic decisions, no memory mutation, no persona engine.
- [ ] GREEN profile metadata:

```python
{
    "contextual_sensitivity": "high",
    "epistemic_discipline": "high",
    "uncertainty_tolerance": "high",
    "emotional_context_awareness": "high",
    "interpretive_openness": "moderate_high",
    "default_action_pressure": "low",
    "default_alarm": "low",
    "reassurance_policy": "evidence_calibrated",
    "grounded_opinion_allowed": True,
    "question_policy": "material_only",
    "cross_domain_awareness": True,
}
```

- [ ] Verify focused tests.
- [ ] Commit: `feat(domains): add concerns resources and profile`.

---

# Task 3 — Understanding, lived experience, support need, question materiality

**Files:** begin `rules.py`; understanding/support-need tests.

Required helper API:

```python
normalize_json_value(value)
understand_concern(material)
map_lived_experience(material)
infer_support_need(
    *,
    explicit_request=None,
    current_signal=None,
    session_context=None,
    historical_preference=None,
)
evaluate_question_materiality(*, question, changes=())
```

Support values:

```text
UNDERSTANDING
EXPLORATION
PERSPECTIVE
REALITY_CHECK
REASSURANCE
INFORMATION
PROBLEM_SOLVING
DECISION_SUPPORT
EMOTIONAL_PROCESSING
NEXT_STEP
MIXED
UNCLEAR
```

Priority:

```text
explicit current request
> clear current signal
> recent session context
> historical preference
> UNCLEAR
```

- [ ] RED: enough context + direct request gives substantive-response-ready state with no mandatory action plan.
- [ ] RED: materially missing context asks a targeted question; immaterial missing detail does not.
- [ ] RED: `"I don't want advice; I just need to talk"` cannot become problem solving.
- [ ] RED: emotional experience remains valid without external interpretation becoming fact.
- [ ] GREEN: pure deterministic helpers; no input mutation.
- [ ] Implement rule classes: `UnderstandBeforeInterveneRule`, `EmotionalValidationRule`, `SupportNeedCalibrationRule`, `ContextualQuestionRule`.
- [ ] Malformed truthy primitives must not mean “material question”.
- [ ] Commit: `feat(domains): add concerns support calibration`.

---

# Task 4 — Epistemics, uncertainty, reassurance, proportional risk

**Files:** extend `rules.py`; epistemics/reassurance/risk tests.

Required levels:

```text
fact
experience
interpretation
fear
hypothesis
scenario
uncertainty
unknown
```

Required helpers:

```python
classify_concern_statement(value)
evaluate_uncertainty(records=())
evaluate_reassurance(*, evidence=(), counterevidence=(), uncertainty=(), material_concerns=())
evaluate_proportional_risk(*, evidence=(), severity=None, immediacy=None, specialized_domain_result=None)
detect_catastrophic_escalation(*, source_state, proposed_state)
detect_false_reassurance(*, reassurance_state, material_concerns=())
```

Reassurance states:

```text
REASSURANCE_SUPPORTED
REASSURANCE_PARTIAL
UNCERTAIN
CONCERN_SUPPORTED
INSUFFICIENT_BASIS
```

- [ ] RED epistemic gates: fact != interpretation; interpretation != fear; fear != prediction; possibility != probability; emotional certainty != evidential certainty.
- [ ] Caller `fact=True` cannot bypass grounding.
- [ ] Duplicates do not inflate; malformed evidence does not inflate; conflict stays conflict.
- [ ] RED reassurance matrix for all five canonical states.
- [ ] Reassurance can coexist with uncertainty.
- [ ] No numerical probability unless supplied by an authorized specialized source.
- [ ] RED catastrophic promotions: possibility→probability, ambiguity→warning sign, change→deterioration, silence→rejection, symptom→serious disease, setback→failure, uncertainty→danger.
- [ ] RED real concern must not be erased by benign alternatives.
- [ ] RED proportional risk: emotional intensity alone cannot make high risk; grounded specialized red flag cannot be downgraded because wording is calm.
- [ ] GREEN rule classes: `ExperienceRealitySeparationRule`, `UncertaintyPreservationRule`, `EvidenceCalibratedReassuranceRule`, `ProportionalRiskRule`, `NoCatastrophicEscalationRule`, `NoFalseReassuranceRule`.
- [ ] Commit: `feat(domains): add concerns reassurance and risk semantics`.

---

# Task 5 — Recurrence, agency, directness, immediate escalation

**Files:** finish `rules.py`; recurrence/risk-agency tests.

Required helpers:

```python
review_recurring_concern_state(*, current, previous=())
evaluate_repetitive_certainty_pattern(*, turns=())
evaluate_action_state(*, options=(), urgency=None, user_request=None)
evaluate_grounded_directness(*, assessment, evidence=(), uncertainty=())
evaluate_immediate_risk_escalation(*, risk_state, specialized_domain_result=None)
build_concerns_rules()
```

Action states:

```text
NO_ACTION_NEEDED
ACTION_OPTIONAL
ACTION_USEFUL
ACTION_RECOMMENDED
DOMAIN_ESCALATION_NEEDED
USER_DECISION_REQUIRED
```

- [ ] RED recurrence: same topic/different question; same question/new evidence; same question/same evidence; changed impact; one repeat; multiple turns pursuing impossible certainty.
- [ ] A repetitive certainty pattern requires all grounded dimensions from the frozen spec; missing relief/checking evidence cannot be invented.
- [ ] Result always preserves `pathology_inferred=False`.
- [ ] Reassurance remains allowed unless independent evidence changes the assessment.
- [ ] RED no psychiatric labels inferred from repetition.
- [ ] RED agency: no action is valid; option != recommendation != adopted decision != authorized execution.
- [ ] RED directness: system may disagree when evidence is weak, acknowledge real concern when evidence is strong, and preserve uncertainty when balanced.
- [ ] RED escalation: ordinary sadness/fear/conflict/repetition is not immediate-risk escalation.
- [ ] GREEN remaining four classes: `RepetitionWithoutPathologizingRule`, `AgencyWithoutPressureRule`, `DirectnessWithoutHarshnessRule`, `ImmediateRiskEscalationRule`.
- [ ] `build_concerns_rules()` returns exactly 14 in catalog order.
- [ ] Commit: `feat(domains): complete concerns reasoning rules`.

---

# Task 6 — Thirteen analysis/preparation operations

**Files:** `operations.py`, operation tests.

Produce:
- `build_concerns_operation_definitions()`
- result helpers named from all 13 operation suffixes.

- [ ] RED exact 13 IDs and catalog order.
- [ ] Shared `DomainOperationDefinition`; domain `domain:concerns`; schemas are structured objects.
- [ ] Operations UNAVAILABLE without injected implementations.
- [ ] Every helper delegates to canonical rule semantics rather than reimplementing competing logic.
- [ ] `prepare_professional_discussion` is PREPARATION only; no send/book/contact state.
- [ ] Public helper matrix is JSON-safe and non-mutating.
- [ ] GREEN implementation.
- [ ] Commit: `feat(domains): add concerns operations`.

Representative parity:

```python
assert evaluate_reassurance_result(
    evidence=evidence,
    uncertainty=uncertainty,
)["assessment"] == evaluate_reassurance(
    evidence=evidence,
    uncertainty=uncertainty,
)["assessment"]
```

---

# Task 7 — Eight workflows on shared Workflow Engine

**Files:** `workflows.py`, workflow tests.

Produce `build_concerns_workflow_definitions()`.

Required workflows and minimum semantic paths:

```text
Open Concern Conversation:
load → profile → understand → support need → gaps → material question if needed
→ selected reasoning → validate → optional memory proposal → complete

Talk It Through:
load → understand → lived experience → exploration → gaps
→ material question if needed → validate unresolved completion → complete

Reality Check:
understand → reality/interpretation separation → uncertainty
→ reassurance → validate → complete

Reassurance Review:
understand → reassurance → no false reassurance
→ no catastrophic escalation → validate → complete

Practical Problem Solving:
understand → desired outcome → options → next step
→ agency gate → validate → complete

Decision Under Uncertainty:
understand → uncertainty → options → preserve user decision
→ validate → complete

Recurring Concern Review:
authorized prior context → recurrence comparison → evidence comparison
→ reassurance if useful → non-pathologizing gate → validate → complete

Professional Discussion Preparation:
understand → open questions → prepare discussion
→ preparation-only gate → validate → complete
```

- [ ] RED exact 8 IDs/names; no custom workflow engine; acyclic dependencies.
- [ ] RED no workflow requires action plan, risk matrix, monitoring plan, adopted decision, or resolved conclusion.
- [ ] RED literal-boolean validation gates; malformed/missing/conflicting dependencies fail closed.
- [ ] GREEN using existing `WorkflowNode`, `WorkflowNodeType`.
- [ ] Commit: `feat(domains): add concerns workflows`.

---

# Task 8 — Sensitive permissions + proposal-only memory

**Files:** `permissions.py`, `memory.py`, permission/memory tests.

Produce:
- `CONCERNS_PERMISSION_POLICY_ID = "domain-permission:concerns:1.0.0"`
- `CONCERNS_PROHIBITED_CAPABILITIES`
- `permission_authorization_allows`
- `build_concerns_permission_policy`
- memory view/proposal/binding/validation helpers matching shared Domain Memory contracts.

- [ ] RED high-sensitivity identity and literal-True authorization.
- [ ] Deny by default: memory write, file/schedule/task modification, external communication, sensitive-inference persistence, export, irreversible change, deletion, permission modification, and high-impact domain decision/action capabilities exposed by shared enum.
- [ ] External search/model capability must not become implicitly authorized by the domain.
- [ ] RED: no Concerns memory store.
- [ ] Fear/support need/recurrence/psychological interpretation/third-party motive cannot silently persist.
- [ ] Raw booleans or arbitrary “confirmed” mappings cannot bypass complete shared confirmation/binding requirements.
- [ ] Most restrictive composed policy wins.
- [ ] GREEN using Reflection/Health shared patterns.
- [ ] Commit: `feat(domains): secure concerns permissions and memory`.

---

# Task 9 — Semantic presentation + reference-only trace

**Files:** `presentation.py`, `trace.py`, tests.

Produce:
- `build_concerns_presentation_policy`
- `present_concerns_result`
- trace reference/contribution/assemble/validate helpers.

- [ ] RED presentation preserves facts, interpretations, hypotheses, fears/scenarios, uncertainty, support need, reassurance assessment, material concerns, risk, action state, permissions, memory state.
- [ ] Presentation cannot upgrade uncertainty, hide concern, adopt action, or turn inference into user fact.
- [ ] No fixed ChatGPT/Claude persona semantics.
- [ ] GREEN semantic ordering: actual concern → lived impact → substantive perspective → useful epistemic distinctions → uncertainty → reassurance/material concern → proportional action.
- [ ] RED trace uses `DomainTraceAssembler`, references only, no chain-of-thought.
- [ ] Trace references support need, evidence, uncertainty, reassurance, risk/material concern, question rationale, action state, memory proposal, permission decisions.
- [ ] Commit: `feat(domains): add concerns presentation and trace`.

---

# Task 10 — Atomic integration + standard bootstrap + public API

**Files:** `integration.py`, `bootstrap.py`, `__init__.py`; integration/rollback/validation-first tests.

Produce:
- `ConcernsDomainIntegrationResult`
- `register_concerns_domain(...)`
- `CONCERNS_BOOTSTRAP_NAME = "ConcernsDomainBootstrap"`
- `ConcernsDomainBootstrap`
- `build_standard_concerns_domain_bootstrap(*, operation_implementations: dict | None = None)`

- [ ] RED complete registration.
- [ ] RED duplicate resources/rules/operations/workflows, unknown implementations, malformed workflows fail before mutation.
- [ ] GREEN validation-first integration.
- [ ] Snapshot every mutable registry and restore exact prior state on failure.
- [ ] RED rollback failure points: definition, resources, rules, operations, workflows, permissions.
- [ ] Preserve unrelated pre-existing entries; retry after rollback succeeds.
- [ ] RED bootstrap starts from `build_standard_general_domain_bootstrap()` and reuses exact registry objects.
- [ ] General remains fallback.
- [ ] RED fresh import registers nothing.
- [ ] GREEN public `__init__.py`, definitions only.
- [ ] Commit: `feat(domains): integrate concerns domain pack`.

Fresh-import gate:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import cmm.domains.concerns
from cmm.domains.registry import DomainRegistry
assert DomainRegistry().get("domain:concerns") is None
print("CONCERNS_FRESH_IMPORT=PASS")
PY
```

---

# Task 11 — Cross-domain boundaries

**Files:** cross-domain test file; production changes only if an existing shared extension point requires them.

Test:
- General fallback.
- explicit Concerns resolution.
- Relationships projection: observed behavior remains fact; motive remains unknown; interpretation remains interpretation.
- Health projection: Concerns does not invent/downgrade medical risk; Health red flags/provenance survive; reassuring Health result can support reassurance.
- Reflection: broader meaning remains Reflection responsibility; no private dependency.
- University/Oppositions/Life Plan/Project projections preserve specialized factual ownership.
- No direct private-store import.
- Most restrictive permissions survive composition.

Do **not** create direct imports among specialized domains to satisfy tests.

Commit: `test(domains): enforce concerns cross-domain boundaries`.

---

# Task 12 — DP-025 + adversarial gates

**Files:** `test_concerns_domain_adversarial.py`, `test_concerns_domain_dp025_acceptance.py`.

Implement the 25-step AT-DP-025 scenario from the frozen spec.

Required named gates:

```text
UNDERSTAND_BEFORE_ACTION_GATE
EXPERIENCE_FACT_SEPARATION_GATE
SUPPORT_NEED_GATE
QUESTION_MATERIALITY_GATE
REASSURANCE_ALLOWED_GATE
NO_FALSE_REASSURANCE_GATE
NO_CATASTROPHIC_ESCALATION_GATE
REAL_CONCERN_ACKNOWLEDGEMENT_GATE
REPETITION_NOT_PATHOLOGY_GATE
RECURRING_PATTERN_GROUNDING_GATE
DIRECTNESS_GATE
NO_FORCED_ACTION_GATE
CROSS_DOMAIN_HEALTH_GATE
CROSS_DOMAIN_REFLECTION_GATE
MEMORY_CONFIRMATION_GATE
PERMISSION_LITERAL_TRUE_GATE
INPUT_ORDER_INVARIANCE_GATE
DUPLICATE_EVIDENCE_GATE
MALFORMED_EVIDENCE_GATE
INPUT_NON_MUTATION_GATE
STRICT_JSON_GATE
PACKAGE_BOUNDARY_GATE
```

Adversarial input matrix: `None`, bool, ints/floats, strings, empty/malformed mappings, nested unexpected values, duplicates, NaN/Inf where accepted.

Requirements:
- no accidental exception;
- no fail-open;
- no certainty inflation;
- no authorization widening;
- strict JSON;
- no input mutation;
- equivalent set permutations produce identical semantics.

Focused suite:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_concerns_domain_*.py
```

Commit: `test(domains): add DP-025 acceptance gates`.

---

# Task 13 — Reference documentation + status

**Files:**
- Create `docs/reference/concerns-domain.md`
- Modify roadmap Phase 10.25 status
- Modify requirements matrix DP-025 mapping/status

Only after implementation tests are green:
- document actual package and verification;
- change “Design frozen. Implementation pending” to implemented/complete;
- set repository mapping to concrete `cmm/domains/concerns/`;
- set `VERIFIED_EXISTING` only after AT-DP-025 passes;
- record `AT-DP-025 — PASS` only with actual evidence.

Obsolete-semantics scan must return zero:

```bash
rg -n \
  "ReassuranceLoopRule|ConcernFactScenarioRule|concerns\.structure_concern|concerns\.separate_fact_scenario|concerns\.generate_monitoring_plan" \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/reference/concerns-domain.md \
  cmm/domains/concerns \
  tests/domains/test_concerns_domain_*.py
```

Commit: `docs(domains): document concerns domain implementation`.

---

# Task 14 — Full verification + audit readiness

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_concerns_domain_*.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_reflection_domain_*.py \
  tests/domains/test_relationships_domain_*.py \
  tests/domains/test_health_domain_*.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q

.venv/bin/ruff check cmm/domains/concerns tests/domains/test_concerns_domain_*.py
.venv/bin/python -m compileall -q cmm/domains/concerns
git diff --check
```

Also:
- run repository target-version Ruff command if CI uses one;
- confirm exactly 14 `*.py` files in package;
- scan for custom planner/runtime/store/engine/database dependencies;
- run fresh import;
- record fresh pytest totals (never hard-code old totals);
- do not declare “independently audited” yet.

Independent audit must attack:
support-need precedence, reassurance under uncertainty, false reassurance, catastrophic caveat stacking, recurrence/pathologization, impossible-certainty grounding, action pressure, question materiality, directness, Health handoff, Reflection boundary, Relationships boundary, literal-True permission semantics, memory confirmation, rollback, strict JSON, input non-mutation, order invariance, package boundary, clean import.

---

# Required End State

```text
domain:concerns
├── 17 entities
├── 10 resources
├── ConcernSupportProfile
├── 14 rules
├── 13 operations
├── 8 workflows
├── sensitive fail-closed permissions
├── proposal-only memory
├── semantic presentation
├── reference-only trace
├── atomic validation-first registration
├── General + Concerns bootstrap
├── cross-domain boundaries
└── AT-DP-025 PASS
```

Semantic target:

```text
understand me
→ understand what matters
→ infer what kind of support I need now
→ think with me
→ tell me what the evidence supports
→ reassure me when there is a basis
→ acknowledge a real problem when there is one
→ preserve uncertainty when unknown
→ do not pathologize me for returning to it
→ help me act when useful
→ or keep talking when that is what I need
```

Catalog/count tests alone are not completion. Behavioral/adversarial gates are authoritative.
