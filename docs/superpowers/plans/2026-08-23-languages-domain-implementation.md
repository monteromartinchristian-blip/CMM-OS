# Phase 10.26 — Languages Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete Phase 10.26 `domain:languages` Domain Pack so CMM OS can act as an adaptive, evidence-aware language tutor and longitudinal learning system while preserving proficiency epistemics, skill separation, variety validity, consent-gated progression, certification temporality, cross-domain minimization, and the shared Phase 10 architecture.

**Architecture:** Add exactly one 14-module `cmm/domains/languages/` specialization using the final hardened Domain Pack pattern. Reuse the existing `DomainDefinition`, Domain Resources, Domain Profiles, Reasoning Rules, Domain Operations, shared Workflow Engine, Domain Permissions, Domain Memory Integration, Domain Presentation, Domain Trace, resolver/composition, registries, validation-first registration, and snapshot/restore rollback. `catalog.py` is the single canonical catalog; semantic helpers are pure/deterministic; all operation helper outputs must satisfy their declared schemas; every workflow runtime gate must read an exact field emitted by a direct dependency.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing `cmm.cognitive`, `cmm.domains`, `cmm.agent_runtime`, `cmm.workflows`.

**Spec:** `docs/superpowers/specs/2026-08-23-languages-domain-design.md`

**Canonical acceptance:** `DP-026` / `AT-DP-026`

## Global Constraints

- Expected branch: `feature/phase-10-domain-intelligence`.
- Starting tracked worktree must be clean; known untracked `tmp/` may remain untouched.
- Canonical ID: `domain:languages`.
- Canonical namespace: `languages.*`.
- Version: `1.0.0`.
- Display name: `Idiomas`.
- Canonical profile: `LanguageLearningProfile`.
- Exactly 16 entities, 15 resources, 14 rules, 15 operations, 9 workflows.
- Exactly 14 production modules: `__init__.py`, `bootstrap.py`, `catalog.py`, `definition.py`, `integration.py`, `memory.py`, `operations.py`, `permissions.py`, `presentation.py`, `profile.py`, `resources.py`, `rules.py`, `trace.py`, `workflows.py`.
- `catalog.py` is the only canonical source for entity/resource/rule/operation/workflow membership and workflow display names.
- No parallel planner, Agent Runtime, memory store, Knowledge Store/Graph, workflow engine, permission engine, temporal engine, conversation engine, assessment engine, lesson engine, spaced-repetition engine, or calendar engine.
- No import-time registration, filesystem access, network access, model call, memory access, workflow execution, or registry mutation.
- Multi-language by design: there is no global user language level across languages.
- Multiple concurrent goals per language are valid.
- `certified proficiency != estimated proficiency != observed performance`.
- `global proficiency != proficiency by skill`.
- Canonical skill dimensions: `listening`, `speaking`, `reading`, `writing`, `grammar`, `vocabulary`, `pronunciation`, `interaction`.
- `preferred variety != only valid variety`.
- `different valid variety != error`.
- `observed_error != error_pattern`.
- `practice result != stable proficiency`.
- `better score once != stable progression`.
- `transcript alone != pronunciation evidence`.
- `certification readiness != general proficiency`.
- `framework mapping != framework identity`.
- Communicative usefulness takes priority over correction density.
- Assessment must not coach the user into stronger evidence.
- Session observations are not persistent memory.
- Longitudinal learning state is consent/policy gated through shared memory proposals.
- Calendar proposal is not calendar mutation.
- Certification preparation is not registration/payment/submission.
- External verification uses shared permission/source mechanisms only; no `languages.web_search`.
- Cross-domain sharing is purpose-minimized and authorization-bound.
- Domain owning the user objective is primary; Languages may be supporting.
- General remains fallback.
- Operations are UNAVAILABLE by default unless real implementations are explicitly injected.
- Public helper/operation outputs are strict JSON-safe; caller inputs are never mutated.
- Absent, malformed, unknown, conflicting, stale, and insufficient-evidence states remain distinct where material.
- Only literal boolean `True` authorizes boolean-gated behavior.
- Duplicate evidence must not inflate level, pattern, progression, or review priority.
- Equivalent semantic evidence sets must be order-invariant where ordering is not semantically meaningful.
- Operation helper output shape MUST equal declared operation output schema. Add runtime schema-parity tests for all 15 operations.
- Every `VALIDATE` node MUST read exact runtime fields emitted by a direct dependency. No runtime-derived safety/epistemic field may be pre-populated with a safe default in workflow metadata.
- Presentation must preserve epistemic kinds, missing evidence, variety validity, readiness/proficiency separation, permissions, and memory proposal state.
- Trace is reference-only; never persist chain-of-thought.
- Registration is validation-first and rollback restores exact prior registry snapshots.
- Strict TDD: RED → verify the expected failure → GREEN minimal implementation → verify GREEN → refactor only while green.
- Do not weaken a failing test to fit an implementation.
- No `TODO`, `TBD`, `FIXME`, placeholders, fake implementations, or deferred frozen requirements.
- Do not push.
- Do not merge to `main`.
- Phase 10.26 implementation completion status is **Implemented, pending independent audit**. Do not claim independent audit success.

---

# Canonical Catalog

## Entities — exactly 16

```text
language
language_variety
skill_dimension
language_goal
proficiency_framework
proficiency_record
assessment_evidence
practice_session
exercise
observed_error
error_pattern
vocabulary_item
grammar_topic
certification_target
review_item
learning_plan
```

## Resources — exactly 15

Canonical registered IDs:

```text
languages.user_message
languages.conversation
languages.writing_sample
languages.audio_transcript
languages.exercise_result
languages.assessment_result
languages.language_plan
languages.lesson_material
languages.vocabulary_list
languages.language_reference
languages.certification_guide
languages.official_certification_source
languages.calendar_event
languages.memory_entry
languages.domain_result
```

`LANGUAGES_RESOURCE_KINDS` is derived from these IDs by stripping the `languages.` prefix.

## Rule IDs / class names — exactly 14

```text
languages.language_level_evidence      -> LanguageLevelEvidenceRule
languages.skill_separation             -> SkillSeparationRule
languages.language_variety_validity    -> LanguageVarietyValidityRule
languages.proficiency_framework        -> ProficiencyFrameworkRule
languages.error_pattern_evidence       -> ErrorPatternEvidenceRule
languages.correction_priority          -> CorrectionPriorityRule
languages.adaptive_difficulty          -> AdaptiveDifficultyRule
languages.spaced_review                -> SpacedReviewRule
languages.learning_load                -> LearningLoadRule
languages.goal_alignment               -> GoalAlignmentRule
languages.progression_evidence         -> ProgressionEvidenceRule
languages.certification_temporal       -> CertificationTemporalRule
languages.cultural_context_evidence    -> CulturalContextEvidenceRule
languages.language_memory_consent      -> LanguageMemoryConsentRule
```

## Operations — exactly 15

```text
languages.assess_sample
languages.update_level_evidence
languages.create_learning_plan
languages.generate_lesson
languages.generate_exercises
languages.review_exercise
languages.review_writing
languages.generate_conversation_turn
languages.generate_roleplay_turn
languages.review_speaking
languages.review_errors
languages.track_vocabulary
languages.plan_review_schedule
languages.prepare_certification
languages.generate_progress_review
```

## Workflows — exactly 9

Canonical implementation IDs and display names:

```text
languages.language_onboarding                 -> Language Onboarding
languages.proficiency_assessment              -> Proficiency Assessment
languages.adaptive_language_lesson            -> Adaptive Language Lesson
languages.conversation_roleplay_practice      -> Conversation & Roleplay Practice
languages.writing_review                      -> Writing Review
languages.error_remediation                   -> Error Remediation
languages.vocabulary_spaced_review            -> Vocabulary & Spaced Review
languages.certification_preparation           -> Certification Preparation
languages.progress_checkpoint                 -> Progress Review
```

The first eight IDs are implementation identifiers derived deterministically from the frozen display names. `languages.progress_checkpoint` is already frozen by the Phase 10 preflight/spec and must not be renamed.

## Profile modes

```text
teach
practice
assess
review
certification
immersion
```

---

# File Map

## Production — create exactly

```text
cmm/domains/languages/__init__.py
cmm/domains/languages/bootstrap.py
cmm/domains/languages/catalog.py
cmm/domains/languages/definition.py
cmm/domains/languages/integration.py
cmm/domains/languages/memory.py
cmm/domains/languages/operations.py
cmm/domains/languages/permissions.py
cmm/domains/languages/presentation.py
cmm/domains/languages/profile.py
cmm/domains/languages/resources.py
cmm/domains/languages/rules.py
cmm/domains/languages/trace.py
cmm/domains/languages/workflows.py
```

## Focused tests — create

```text
tests/domains/test_languages_domain_catalog.py
tests/domains/test_languages_domain_definition.py
tests/domains/test_languages_domain_resources.py
tests/domains/test_languages_domain_profile.py
tests/domains/test_languages_domain_proficiency.py
tests/domains/test_languages_domain_variety_framework.py
tests/domains/test_languages_domain_error_correction.py
tests/domains/test_languages_domain_adaptation_progression.py
tests/domains/test_languages_domain_operations.py
tests/domains/test_languages_domain_workflows.py
tests/domains/test_languages_domain_permissions.py
tests/domains/test_languages_domain_memory.py
tests/domains/test_languages_domain_presentation.py
tests/domains/test_languages_domain_trace.py
tests/domains/test_languages_domain_cross_domain.py
tests/domains/test_languages_domain_integration.py
tests/domains/test_languages_domain_adversarial.py
tests/domains/test_languages_domain_dp026_acceptance.py
```

Do not create separate rollback/validation-first test files unless they materially improve reviewability. The final Concerns precedent keeps those guarantees inside its integration test module; Languages may do the same.

## Documentation — create/update only after implementation is green

```text
docs/reference/languages-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md
```

`ROADMAP.md` should only receive the minimal progress/status update required by implementation completion.

---

# Preflight — architecture and baseline gate

Before Task 1, execute and record:

```bash
cd "/Users/chris/CMM OS"

git branch --show-current
git rev-parse --short HEAD
git status --short --branch

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"

test ! -d cmm/domains/languages
test -f docs/superpowers/specs/2026-08-23-languages-domain-design.md
test -f docs/superpowers/plans/2026-08-23-languages-domain-implementation.md

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_concerns_domain_*.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/concerns \
  tests/domains/test_concerns_domain_*.py

git diff --check
```

Expected architectural conclusion:

```text
SHARED_INFRA_SUFFICIENT
```

If current shared contracts cannot express a frozen Languages requirement, STOP before modifying shared infrastructure and report:

```text
exact missing shared contract
why the frozen requirement cannot be expressed
which completed domains would use the primitive identically
minimal proposed shared change
```

Do not silently modify shared infrastructure.

---

# Task 1 — Canonical catalog + immutable DomainDefinition

**Files:**
- Create: `cmm/domains/languages/catalog.py`
- Create: `cmm/domains/languages/definition.py`
- Test: `tests/domains/test_languages_domain_catalog.py`
- Test: `tests/domains/test_languages_domain_definition.py`

**Interfaces:**
- Produces canonical catalog constants used by every later module.
- Produces `LANGUAGES_DOMAIN_ID`, `LANGUAGES_DOMAIN_VERSION`, `LANGUAGES_MANIFEST_ID`, `LANGUAGES_PROFILE_NAME`, catalog aliases, permission IDs, and `build_languages_domain_definition()`.

- [ ] **Step 1: RED catalog exactness**

Write tests asserting:

```python
assert len(CANONICAL_LANGUAGES_ENTITY_TYPES) == 16
assert len(CANONICAL_LANGUAGES_RESOURCE_IDS) == 15
assert len(CANONICAL_LANGUAGES_RULE_IDS) == 14
assert len(CANONICAL_LANGUAGES_OPERATION_IDS) == 15
assert len(CANONICAL_LANGUAGES_WORKFLOW_IDS) == 9

for values in (
    CANONICAL_LANGUAGES_ENTITY_TYPES,
    CANONICAL_LANGUAGES_RESOURCE_IDS,
    CANONICAL_LANGUAGES_RULE_IDS,
    CANONICAL_LANGUAGES_OPERATION_IDS,
    CANONICAL_LANGUAGES_WORKFLOW_IDS,
):
    assert len(values) == len(set(values))

assert all(value.startswith("languages.") for value in CANONICAL_LANGUAGES_RESOURCE_IDS)
assert all(value.startswith("languages.") for value in CANONICAL_LANGUAGES_RULE_IDS)
assert all(value.startswith("languages.") for value in CANONICAL_LANGUAGES_OPERATION_IDS)
assert all(value.startswith("languages.") for value in CANONICAL_LANGUAGES_WORKFLOW_IDS)
assert "languages.progress_checkpoint" in CANONICAL_LANGUAGES_WORKFLOW_IDS
```

Also assert exact workflow display names and exact rule class-name tuple.

- [ ] **Step 2: Verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_catalog.py
```

Expected: import/file-not-found failure caused by missing Languages package, not unrelated collection failure.

- [ ] **Step 3: GREEN catalog**

Implement:

```python
CANONICAL_LANGUAGES_ENTITY_TYPES: tuple[str, ...] = (...)
CANONICAL_LANGUAGES_RESOURCE_IDS: tuple[str, ...] = (...)
LANGUAGES_RESOURCE_KINDS = tuple(
    resource_id.split(".", 1)[1]
    for resource_id in CANONICAL_LANGUAGES_RESOURCE_IDS
)
CANONICAL_LANGUAGES_RULE_IDS: tuple[str, ...] = (...)
CANONICAL_LANGUAGES_RULE_NAMES: tuple[str, ...] = (...)
CANONICAL_LANGUAGES_OPERATION_IDS: tuple[str, ...] = (...)
CANONICAL_LANGUAGES_WORKFLOW_IDS: tuple[str, ...] = (...)
LANGUAGES_WORKFLOW_NAMES_BY_ID: dict[str, str] = {...}
CANONICAL_LANGUAGES_WORKFLOW_NAMES = tuple(
    LANGUAGES_WORKFLOW_NAMES_BY_ID[workflow_id]
    for workflow_id in CANONICAL_LANGUAGES_WORKFLOW_IDS
)
```

No second tuple in another production module may independently redefine catalog membership.

- [ ] **Step 4: RED definition**

Assert:

```python
definition = build_languages_domain_definition()

assert str(definition.id) == "domain:languages"
assert definition.name == "languages"
assert definition.display_name == "Idiomas"
assert definition.version == "1.0.0"
assert definition.kind is DomainKind.PERSONAL
assert definition.reasoning_profile == "LanguageLearningProfile"
assert tuple(definition.resources) == CANONICAL_LANGUAGES_RESOURCE_IDS
assert tuple(definition.rules) == CANONICAL_LANGUAGES_RULE_IDS
assert tuple(definition.operations) == CANONICAL_LANGUAGES_OPERATION_IDS
assert tuple(definition.workflows) == CANONICAL_LANGUAGES_WORKFLOW_IDS
assert definition.metadata.metadata["phase"] == "10.26"
assert build_languages_domain_definition().to_dict() == definition.to_dict()
```

Capabilities must be exactly:

```text
language_onboarding
proficiency_assessment
adaptive_language_teaching
language_practice
writing_review
speaking_review
error_remediation
spaced_review
progression_review
certification_preparation
```

- [ ] **Step 5: GREEN definition**

Use existing:

```python
from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
```

Set:

```python
LANGUAGES_DOMAIN_ID = "domain:languages"
LANGUAGES_DOMAIN_VERSION = "1.0.0"
LANGUAGES_MANIFEST_ID = "manifest:languages:1.0.0"
LANGUAGES_PROFILE_NAME = "LanguageLearningProfile"
LANGUAGES_PERMISSION_IDS = ("domain-permission:languages:1.0.0",)
```

- [ ] **Step 6: Verify GREEN + hygiene**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_catalog.py \
  tests/domains/test_languages_domain_definition.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/catalog.py \
  cmm/domains/languages/definition.py \
  tests/domains/test_languages_domain_catalog.py \
  tests/domains/test_languages_domain_definition.py

git diff --check
```

- [ ] **Step 7: Commit**

```bash
git add \
  cmm/domains/languages/catalog.py \
  cmm/domains/languages/definition.py \
  tests/domains/test_languages_domain_catalog.py \
  tests/domains/test_languages_domain_definition.py

git diff --cached --check
git commit -m "feat(domains): define languages domain catalog"
```

---

# Task 2 — Resources + LanguageLearningProfile

**Files:**
- Create: `cmm/domains/languages/resources.py`
- Create: `cmm/domains/languages/profile.py`
- Test: `tests/domains/test_languages_domain_resources.py`
- Test: `tests/domains/test_languages_domain_profile.py`

**Interfaces:**
- Produces `build_languages_resource_definitions()`.
- Produces `LANGUAGES_PROFILE_ID = "languages.profile"`, `LANGUAGES_PROFILE_NAME = "LanguageLearningProfile"`, `LANGUAGES_PEDAGOGICAL_MODES`, `LANGUAGES_PROHIBITED_ACTIONS`, `build_languages_profile()`.

## Resource mapping

Use the established `_resource(...) -> DomainResourceDefinition` pattern with shared adapters.

Canonical adapter/entity intent:

```text
languages.user_message
  adapter=cognitive.message
  entities=(language, language_goal, observed_error)

languages.conversation
  adapter=cognitive.conversation
  entities=(language, language_variety, practice_session, observed_error)

languages.writing_sample
  adapter=cognitive.note
  entities=(language, practice_session, assessment_evidence, observed_error)

languages.audio_transcript
  adapter=cognitive.note
  entities=(language, practice_session, assessment_evidence, observed_error)

languages.exercise_result
  adapter=cognitive.event
  entities=(exercise, assessment_evidence, observed_error)

languages.assessment_result
  adapter=cognitive.event
  entities=(proficiency_record, assessment_evidence, skill_dimension)

languages.language_plan
  adapter=cognitive.goal
  entities=(learning_plan, language_goal, certification_target)

languages.lesson_material
  adapter=cognitive.note
  entities=(exercise, grammar_topic, vocabulary_item)

languages.vocabulary_list
  adapter=cognitive.note
  entities=(vocabulary_item, review_item)

languages.language_reference
  adapter=cognitive.note
  entities=(language, language_variety, grammar_topic, vocabulary_item)

languages.certification_guide
  adapter=cognitive.note
  entities=(certification_target, proficiency_framework)

languages.official_certification_source
  adapter=cognitive.event
  entities=(certification_target, proficiency_framework)

languages.calendar_event
  adapter=cognitive.event
  entities=(practice_session, certification_target, language_goal)

languages.memory_entry
  adapter=cognitive.memory
  entities=(proficiency_record, language_goal, error_pattern, review_item, learning_plan)

languages.domain_result
  adapter=cognitive.event
  entities=(language_goal, proficiency_record, certification_target, assessment_evidence)
```

Sensitivity/reliability policy:

- user production/history: `SensitivityLevel.PERSONAL`;
- memory/cross-domain projections: at least `SensitivityLevel.PERSONAL`;
- public/official reference resources: `SensitivityLevel.INTERNAL`;
- `official_certification_source` has higher default reliability than `certification_guide`, but reliability alone never creates authority/currentness;
- `calendar_event`, `assessment_result`, `official_certification_source`, and `language_plan` require effective temporal grounding where the underlying contract supports it;
- `audio_transcript` metadata explicitly says transcript is not pronunciation evidence by itself;
- `domain_result` metadata explicitly says minimal authorized cross-domain projection;
- `memory_entry` metadata says provenance/proposal state, not automatic current truth.

- [ ] **Step 1: RED resources**

Assert exactly 15 definitions in canonical order, domain `domain:languages`, shared adapters only, deterministic `to_dict()`, correct kinds, and key metadata invariants:

```python
by_id = {resource.id: resource for resource in build_languages_resource_definitions()}

assert by_id["languages.audio_transcript"].metadata["pronunciation_evidence"] is False
assert by_id["languages.domain_result"].metadata["minimal_authorized_projection"] is True
assert by_id["languages.memory_entry"].metadata["provenance_not_truth"] is True
assert (
    by_id["languages.official_certification_source"].default_reliability
    > by_id["languages.certification_guide"].default_reliability
)
```

- [ ] **Step 2: GREEN resources**

Implement with `DomainResourceDefinition` and `DomainResourceTemporalPolicy`; do not import a sibling domain resource module.

## Profile semantics

Required profile mode tuple:

```python
LANGUAGES_PEDAGOGICAL_MODES = (
    "teach",
    "practice",
    "assess",
    "review",
    "certification",
    "immersion",
)
```

Required profile metadata:

```python
{
    "phase": "10.26",
    "pedagogical_modes": list(LANGUAGES_PEDAGOGICAL_MODES),
    "communicative_usefulness_priority": "high",
    "correction_density_default": "selective",
    "evidence_discipline": "high",
    "skill_separation": True,
    "multi_language": True,
    "multiple_goals_per_language": True,
    "adaptive_difficulty": True,
    "cross_domain_awareness": True,
}
```

Prohibited actions must include at minimum:

```text
direct_memory_write
silent_memory_persistence
unconfirmed_progress_persistence
unconfirmed_proficiency_persistence
unconfirmed_error_pattern_persistence
calendar_modification
schedule_modification
task_creation
external_communication
exam_registration
application_submission
payment
purchase
publication
permission_modification
shell_execution
```

Allowed inferences must include:

```text
observed_performance
estimated_proficiency
skill_specific_evidence
valid_language_variety
observed_error
candidate_error_pattern
supported_error_pattern
short_term_improvement
stable_improvement
plateau
possible_regression
insufficient_evidence
certification_readiness
```

Prohibited inferences must include:

```text
single_sample_to_certified
single_sample_to_stable_proficiency
cross_skill_inflation
variety_difference_to_error
transcript_to_pronunciation
single_score_to_stable_progression
exam_readiness_to_general_proficiency
silent_framework_identity
silent_memory_persistence
```

Presentation policy must require uncertainty/provenance and support sections equivalent to:

```text
objective
activity
feedback
evidence
uncertainty
next_practice
```

Memory policy:

Languages must leave the shared opt-in longitudinal path structurally possible.
The base profile therefore describes *eligibility*, not autonomous authorization:

```python
DomainMemoryPolicy(
    allow_read=True,
    allow_write=None,
    allow_long_term=True,
    allow_cross_domain=False,
    retention_scope="long_term",
    sensitivity_limit=SensitivityLevel.PERSONAL,
)
```

`allow_write=None` is deliberate: the profile itself does not grant writes and
does not impose a monotonic deny that would make a later scoped grant
impossible. Actual mutation remains governed by the Domain Permission layer,
the shared approval lifecycle, and the Domain Memory proposal/binding path.
The profile must prohibit direct/silent/unconfirmed persistence, not the
canonical approval-gated shared apply path.

Production policy for ordinary low-risk tutoring:

```python
DomainProductionPolicy(
    allow_draft=True,
    allow_final=True,
    allow_external_action=False,
    require_review=False,
    require_validation=True,
    maximum_output_items=128,
)
```

This allows completed pedagogical responses while keeping all external effects
outside Languages.

Profile-level `permissions` must be:

```python
permissions=None
```

This is deliberate. `DomainProfile.permissions` composes by restrictive
intersection; a fixed tuple that omitted a later approval-gated permission such
as memory write would make that valid permission impossible to recover.
`None` means the Languages profile imposes no additional permission grant-set
constraint. Runtime authorization still comes exclusively from the shared
Domain Permission / approval system.

- [ ] **Step 3: RED profile**

Assert all 14 rules required, all 15 resource kinds allowed, six modes present,
no external action, long-term learning is structurally eligible,
`permissions is None`, the profile does **not** itself grant memory mutation,
direct/silent/unconfirmed persistence is prohibited, deterministic
serialization, and no communication persona fields.

Also add a composition regression proving that the base profile does not make
a later valid scoped long-term memory grant impossible through monotonic
profile composition.

- [ ] **Step 4: GREEN profile**

Use only shared profile contracts.

- [ ] **Step 5: Verify**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_resources.py \
  tests/domains/test_languages_domain_profile.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/resources.py \
  cmm/domains/languages/profile.py \
  tests/domains/test_languages_domain_resources.py \
  tests/domains/test_languages_domain_profile.py

git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add \
  cmm/domains/languages/resources.py \
  cmm/domains/languages/profile.py \
  tests/domains/test_languages_domain_resources.py \
  tests/domains/test_languages_domain_profile.py

git commit -m "feat(domains): add languages resources and profile"
```

---

# Task 3 — Proficiency evidence, skill separation, language variety, framework semantics

**Files:**
- Create/start: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_proficiency.py`
- Test: `tests/domains/test_languages_domain_variety_framework.py`

**Interfaces produced:**

```python
normalize_json_value(value)

classify_proficiency_record(
    *,
    kind,
    framework=None,
    level_or_score=None,
    skill_scope=None,
    evidence=(),
    confidence=None,
)

evaluate_level_update(
    *,
    existing=None,
    evidence=(),
    target_skill=None,
)

separate_skill_evidence(*, evidence=())

classify_language_variety(
    *,
    preferred_variety=None,
    observed_variety=None,
    assessment_standard=None,
    form_status=None,
)

evaluate_framework_mapping(
    *,
    source_framework,
    source_value,
    target_framework,
    mapping_evidence=(),
)
```

Canonical proficiency kinds:

```text
CERTIFIED
ESTIMATED
OBSERVED_PERFORMANCE
```

Canonical skill dimensions:

```text
listening
speaking
reading
writing
grammar
vocabulary
pronunciation
interaction
```

Canonical variety outcomes:

```text
preferred
valid_alternative
register_difference
regional_difference
nonstandard
incorrect
uncertain
```

Framework mapping state must distinguish:

```text
identity_forbidden
grounded_approximate_mapping
insufficient_evidence
```

- [ ] **Step 1: RED proficiency-kind tests**

Required cases:

```text
certificate + official evidence -> CERTIFIED
assessment sample -> OBSERVED_PERFORMANCE
accumulated supported inference -> ESTIMATED
single strong sample -> no automatic stable estimate update
estimate -> cannot overwrite certificate
missing speaking evidence -> speaking remains insufficient_evidence
```

Representative:

```python
result = evaluate_level_update(
    existing={
        "kind": "ESTIMATED",
        "skill_scope": "writing",
        "level_or_score": "B1+",
    },
    evidence=(
        {"id": "sample-1", "skill": "writing", "observed": "B2"},
    ),
    target_skill="writing",
)
assert result["stable_update_supported"] is False
assert result["reason"] == "insufficient_comparable_evidence"
```

- [ ] **Step 2: RED skill separation**

Prove:

```text
reading B2 evidence -> does not set speaking
grammar score -> does not set interaction
transcript -> does not set pronunciation
global summary -> cannot erase explicit skill gaps
```

- [ ] **Step 3: RED variety**

At minimum:

```python
result = classify_language_variety(
    preferred_variety="American English",
    observed_variety="British English",
    assessment_standard="General English",
    form_status="valid",
)
assert result["classification"] == "valid_alternative"
assert result["error"] is False
```

Unknown caller strings must not silently become “valid”.

- [ ] **Step 4: RED framework mapping**

Prove CEFR/IELTS/TOEFL/Cambridge values are not identity-equivalent merely because caller says so. Mapping requires explicit evidence/provenance and is represented as approximate when applicable.

- [ ] **Step 5: Verify RED**

Run both files and confirm failure is due to missing helpers.

- [ ] **Step 6: GREEN helpers**

Implement pure deterministic helpers. Rules:
- no I/O;
- no clock;
- no mutation;
- duplicate evidence IDs/provenance do not inflate;
- malformed evidence cannot increase certainty;
- strict JSON-safe normalization;
- input-order invariance for evidence sets.

- [ ] **Step 7: GREEN first four rule classes**

Implement shared reasoning-rule wrappers:

```text
LanguageLevelEvidenceRule
SkillSeparationRule
LanguageVarietyValidityRule
ProficiencyFrameworkRule
```

Each class must use a `DomainReasoningRuleDefinition` with the exact catalog ID and delegate its semantic outcome to the helper rather than duplicate logic.

- [ ] **Step 8: Verify + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_proficiency.py \
  tests/domains/test_languages_domain_variety_framework.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/rules.py \
  tests/domains/test_languages_domain_proficiency.py \
  tests/domains/test_languages_domain_variety_framework.py

git diff --check

git add \
  cmm/domains/languages/rules.py \
  tests/domains/test_languages_domain_proficiency.py \
  tests/domains/test_languages_domain_variety_framework.py

git commit -m "feat(domains): add languages proficiency semantics"
```

---

# Task 4 — Error patterns, correction priority, adaptive difficulty

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_error_correction.py`

**Interfaces produced:**

```python
evaluate_error_pattern(
    *,
    observations=(),
    minimum_independent_occurrences=2,
)

prioritize_corrections(
    *,
    errors=(),
    mode="practice",
    active_goals=(),
    certification_relevance=(),
)

adapt_difficulty(
    *,
    current_difficulty,
    performance=(),
    stable_proficiency=None,
)
```

`minimum_independent_occurrences` is a testable default threshold, not a claim that two identical tokens in one copied sentence are independent observations. Independence/context comparability must be evaluated separately.

Error-pattern output must expose:

```text
pattern_state
eligible
independent_occurrences
comparable_contexts
lapse_possible
evidence_ids
```

Suggested states:

```text
insufficient_evidence
candidate
evidenced
improving
resolved
```

Correction priority ordering:

```text
comprehension_blocking
recurrent
goal_relevant
certification_relevant
naturalness_register
minor_style
```

Adaptive output:

```text
increase
maintain_and_advance
scaffold_reduce
insufficient_evidence
```

- [ ] **Step 1: RED error-pattern matrix**

Required cases:
- one error -> insufficient evidence;
- same copied sentence repeated -> not independent;
- same error in independent comparable samples -> candidate/evidenced;
- valid variety difference -> excluded from error evidence;
- resolved pattern + one later slip -> no automatic full regression;
- duplicate evidence ID/provenance -> no inflation;
- permutation invariance.

- [ ] **Step 2: RED correction density**

During `practice`, minor style errors do not become immediate correction priority when higher-value communication is intact.

During explicit `assess`, feedback is deferred until evidence capture is complete.

- [ ] **Step 3: RED adaptive difficulty**

Required:
- repeated too-easy comparable performance -> increase;
- adequate performance -> consolidate/advance;
- too-hard performance -> scaffold/reduce;
- one bad session -> stable proficiency unchanged;
- malformed performance -> insufficient evidence.

- [ ] **Step 4: GREEN helpers + rule classes**

Implement:

```text
ErrorPatternEvidenceRule
CorrectionPriorityRule
AdaptiveDifficultyRule
```

- [ ] **Step 5: Verify + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_error_correction.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/rules.py \
  tests/domains/test_languages_domain_error_correction.py

git diff --check

git add \
  cmm/domains/languages/rules.py \
  tests/domains/test_languages_domain_error_correction.py

git commit -m "feat(domains): add languages error and correction semantics"
```

---

# Task 5 — Spaced review, learning load, goal alignment, progression, certification temporal, cultural context, memory consent

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_adaptation_progression.py`

**Interfaces produced:**

```python
plan_spaced_review(
    *,
    items=(),
    active_goals=(),
)

evaluate_learning_load(
    *,
    available_time=None,
    energy=None,
    priorities=(),
    deadlines=(),
    recent_load=None,
    review_backlog=(),
)

align_activity_to_goals(
    *,
    activity,
    goals=(),
)

evaluate_progression(
    *,
    previous_evidence=(),
    current_evidence=(),
    skill=None,
)

evaluate_certification_source(
    *,
    sources=(),
    decision_critical=False,
)

evaluate_cultural_context(
    *,
    claim,
    evidence=(),
    universal_claim=False,
)

evaluate_language_memory_consent(
    *,
    content_kind,
    session_only=True,
    consent=None,
    permission_chain_valid=False,
)
```

Progression outcomes:

```text
short_term_improvement
stable_improvement
stable
plateau
possible_regression
insufficient_evidence
```

Certification source authority:

```text
current official
>
current authoritative secondary
>
historical memory
>
unverified guide
```

The helper must preserve conflicting equivalent-authority sources as unresolved.

Memory consent:
- session-only use is allowed when otherwise authorized;
- long-term proficiency/error-pattern/vocabulary/grammar/goal/plan/progress state requires shared policy/consent;
- raw booleans/strings/mappings are not a substitute for the shared approval/memory chain where the chain is required;
- no helper applies persistence.

- [ ] **Step 1: RED spaced-review semantics**

Prove review priority responds to mastery, recall, importance, goal relevance, and active patterns; not a fixed interval-only schedule.

- [ ] **Step 2: RED load semantics**

Hard constraints/time/energy precede preferences. Languages proposes learning load but does not mutate the global calendar.

- [ ] **Step 3: RED goal alignment**

Certification, travel, conversation, and writing goals can coexist; one certification goal does not silently replace other goals.

- [ ] **Step 4: RED progression**

Required:
- one better result -> short-term only;
- repeated comparable improvement -> stable improvement may be supported;
- incomparable tasks -> insufficient evidence;
- one poor session -> no stable regression;
- writing improvement -> no speaking inflation.

- [ ] **Step 5: RED certification temporality**

Current official source outranks stale guide/memory for changing facts. Missing current official evidence on a decision-critical fact returns `needs_verification=True`, not a guessed result.

- [ ] **Step 6: RED cultural context**

General tendencies remain qualified; universal stereotypes are not created from weak evidence.

- [ ] **Step 7: RED memory consent**

Session observation does not become durable state. Repetition does not equal consent. Candidate persistent state remains a proposal.

- [ ] **Step 8: GREEN helpers + remaining rule classes**

Implement:

```text
SpacedReviewRule
LearningLoadRule
GoalAlignmentRule
ProgressionEvidenceRule
CertificationTemporalRule
CulturalContextEvidenceRule
LanguageMemoryConsentRule
```

Then implement:

```python
def build_languages_rules() -> tuple[...]:
    ...
```

and assert exactly 14 rules in catalog order.

- [ ] **Step 9: Verify + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_proficiency.py \
  tests/domains/test_languages_domain_variety_framework.py \
  tests/domains/test_languages_domain_error_correction.py \
  tests/domains/test_languages_domain_adaptation_progression.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/rules.py \
  tests/domains/test_languages_domain_*progression.py \
  tests/domains/test_languages_domain_proficiency.py \
  tests/domains/test_languages_domain_variety_framework.py \
  tests/domains/test_languages_domain_error_correction.py

git diff --check

git add \
  cmm/domains/languages/rules.py \
  tests/domains/test_languages_domain_adaptation_progression.py

git commit -m "feat(domains): complete languages reasoning rules"
```

---

# Task 6 — Operation contracts and first semantic operation group

**Files:**
- Create: `cmm/domains/languages/operations.py`
- Test: `tests/domains/test_languages_domain_operations.py`

**Interfaces:**
- Produces `build_languages_operation_definitions()`.
- Produces 15 pure result builders.
- No operation implementation object is embedded; registry implementations are injected later.

## Operation type mapping

Use existing `DomainOperationType` values:

```text
ANALYSIS:
  languages.assess_sample
  languages.update_level_evidence
  languages.review_exercise
  languages.review_writing
  languages.review_speaking
  languages.review_errors
  languages.track_vocabulary
  languages.generate_progress_review

PLANNING:
  languages.create_learning_plan
  languages.plan_review_schedule

PREPARATION:
  languages.generate_lesson
  languages.generate_exercises
  languages.generate_conversation_turn
  languages.generate_roleplay_turn
  languages.prepare_certification
```

No canonical Languages operation is `EXTERNAL`, `DESTRUCTIVE`, or a direct memory mutation.

## Required resource mapping

Use strict AND semantics only when the operation structurally requires a resource:

```text
languages.assess_sample
  writing_sample OR audio_transcript/conversation cannot be represented as AND alternatives in required_resources.
  Therefore required_resources=() and input schema identifies sample kind/ref.
  Resource availability is validated by the caller/workflow where applicable.

languages.update_level_evidence
  required_resources=()
  # The new assessment is runtime input produced by an upstream operation or
  # supplied by the caller. Requiring assessment_result here would incorrectly
  # turn an upstream operation result into a mandatory external resource.

languages.create_learning_plan
  required_resources=()

languages.generate_lesson
  required_resources=()

languages.generate_exercises
  required_resources=()

languages.review_exercise
  required_resources=("languages.exercise_result",)

languages.review_writing
  required_resources=("languages.writing_sample",)

languages.generate_conversation_turn
  required_resources=("languages.conversation",)

languages.generate_roleplay_turn
  required_resources=("languages.conversation",)

languages.review_speaking
  required_resources=()

languages.review_errors
  required_resources=()

languages.track_vocabulary
  required_resources=("languages.vocabulary_list",)

languages.plan_review_schedule
  required_resources=()

languages.prepare_certification
  required_resources=()

languages.generate_progress_review
  required_resources=()
```

Do not pad required resources to “look complete”; the shared contract interprets them as AND.

## Required result builders

```python
assess_sample_result(...)
update_level_evidence_result(...)
create_learning_plan_result(...)
generate_lesson_result(...)
generate_exercises_result(...)
review_exercise_result(...)
review_writing_result(...)
generate_conversation_turn_result(...)
generate_roleplay_turn_result(...)
review_speaking_result(...)
review_errors_result(...)
track_vocabulary_result(...)
plan_review_schedule_result(...)
prepare_certification_result(...)
generate_progress_review_result(...)
```

- [ ] **Step 1: RED definition exactness**

Assert 15 IDs, domain, version, `PolicyRiskLevel.LOW` for every Languages
operation, proposal-only/no-direct-side-effect metadata, and the exact
operation-type mapping.

- [ ] **Step 2: RED schema closure**

Every input/output schema is:

```python
{
    "type": "object",
    "required": [...],
    "properties": {...},
    "additionalProperties": False,
}
```

unless the existing operation-schema validator requires a narrower exact variant.

- [ ] **Step 3: RED helper ↔ output schema parity**

This is mandatory from the first operation implementation.

Use the real shared validator:

```python
from cmm.agent_runtime.operation_schema import validate_operation_schema
```

Map each operation ID to a minimal valid helper invocation.

Representative invariant:

```python
for operation in build_languages_operation_definitions():
    output = _representative_helper_output(operation.operation_id)
    errors = validate_operation_schema(output, operation.output_schema)
    assert errors == ()
```

Do not create a second “helper shape” and “runtime shape”.

- [ ] **Step 4: GREEN first builders**

Implement at least:

```text
assess_sample_result
update_level_evidence_result
create_learning_plan_result
generate_lesson_result
generate_exercises_result
review_exercise_result
```

Semantics:
- `assess_sample_result` delegates to proficiency/skill/variety helpers and returns OBSERVED_PERFORMANCE plus missing evidence;
- `update_level_evidence_result` never alters certified record and returns proposal semantics;
- `create_learning_plan_result` preserves multiple goals and emits
  `tracking_choice`, `tracking_choice_resolved`,
  `memory_proposal_required`, and `persistence_applied=False`;
- `generate_lesson_result` emits objective/warm-up/input/guided practice/active production/feedback/review/next step;
- `generate_exercises_result` is goal/skill/difficulty aligned;
- `review_exercise_result` emits observed errors, never automatic patterns.

- [ ] **Step 5: Verify RED→GREEN focused**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_operations.py
```

- [ ] **Step 6: Commit first operations block**

```bash
git add \
  cmm/domains/languages/operations.py \
  tests/domains/test_languages_domain_operations.py

git commit -m "feat(domains): add languages core operations"
```

---

# Task 7 — Practice, correction, review, certification operation semantics

**Files:**
- Modify: `cmm/domains/languages/operations.py`
- Modify: `tests/domains/test_languages_domain_operations.py`

- [ ] **Step 1: RED remaining builders**

Implement tests for:

```text
review_writing_result
generate_conversation_turn_result
generate_roleplay_turn_result
review_speaking_result
review_errors_result
track_vocabulary_result
plan_review_schedule_result
prepare_certification_result
generate_progress_review_result
```

Required invariants:

### Writing

```text
wrong
awkward/unnatural
register mismatch
valid alternative
preferred variety
```

remain distinct.

### Conversation / roleplay

Output contains one turn only. No loop/runtime/state engine inside the helper.

### Speaking

```text
transcript-only input -> pronunciation_assessed=False
pronunciation-specific evidence -> may assess pronunciation
```

### Errors

`observed_error` collection is preserved; pattern candidates are delegated to `evaluate_error_pattern`.

### Vocabulary

Produces candidate review-state changes; does not persist them.

### Review schedule

Outputs a pedagogical review proposal and:

```text
calendar_modified=False
external_action_executed=False
```

### Certification

Outputs:
- target;
- current-source status;
- required skills;
- gaps;
- readiness;
- verification need;
- `registration_performed=False`;
- `payment_performed=False`;
- `submission_performed=False`.

Readiness remains distinct from general proficiency.

### Progress review

Outputs:
- period;
- skill evidence;
- progression classifications;
- goals;
- patterns;
- review state;
- certification readiness;
- uncertainty;
- recommended next focus.

- [ ] **Step 2: Full schema parity**

All 15 actual helper results must satisfy the exact declared output schema.

Also assert every declared input property needed by a helper is present in its input schema. This prevents the Phase 10.25 “helper parameter unreachable through runtime schema” defect.

- [ ] **Step 3: Malformed/JSON/non-mutation matrix**

For representative helpers:
- `None`;
- bool;
- int/float;
- strings;
- malformed mappings;
- duplicate IDs;
- NaN/Inf where numeric values are accepted.

No public helper may leak accidental `KeyError`, `TypeError`, or `AttributeError`.

- [ ] **Step 4: Verify + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_operations.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/operations.py \
  tests/domains/test_languages_domain_operations.py

git diff --check

git add \
  cmm/domains/languages/operations.py \
  tests/domains/test_languages_domain_operations.py

git commit -m "feat(domains): complete languages operations"
```

---

# Task 8 — Shared Workflow Engine definitions

**Files:**
- Create: `cmm/domains/languages/workflows.py`
- Test: `tests/domains/test_languages_domain_workflows.py`

**Interfaces:**
- Consumes canonical operations.
- Produces exactly nine `DomainWorkflowDefinition` instances.
- Uses `WorkflowNode` and existing `WorkflowNodeType`; no private runner.

Use the final Concerns helper pattern:

```python
def _node(
    node_id,
    node_type,
    name,
    *,
    dependencies=(),
    operation_id=None,
    approval_gate=None,
    wait_condition=None,
    metadata=None,
) -> WorkflowNode:
    return WorkflowNode(
        node_id=node_id,
        node_type=node_type,
        name=name,
        dependencies=dependencies,
        operation_id=operation_id,
        operation_version="1.0.0" if operation_id else None,
        approval_gate=approval_gate,
        wait_condition=wait_condition,
        metadata=metadata or {},
    )
```

Every workflow begins with the strict dependency chain:

```text
load -> profile -> reason
```

Every `COMPLETE` node transitively depends on at least one `VALIDATE` node.

## Workflow graphs

### `languages.language_onboarding`

```text
load
→ profile
→ reason
→ create_plan (languages.create_learning_plan)
→ validate_tracking_boundary
→ complete
```

`languages.create_learning_plan` must expose these runtime fields in both its
helper output and declared output schema:

```text
tracking_choice              # opt_in | opt_out | unresolved
tracking_choice_resolved     # strict bool
memory_proposal_required     # strict bool
persistence_applied          # always False inside the domain operation
```

`validate_tracking_boundary` reads **directly** from `create_plan`:

```text
tracking_choice_resolved == True
persistence_applied == False
```

Both explicit opt-in and explicit opt-out are valid onboarding outcomes.
`opt_in` means a later shared Domain Memory proposal/approval path may be used;
it does not mean the plan operation itself validated a grant or persisted
anything. `unresolved` fails the tracking-choice gate when longitudinal
tracking is requested.

Initial proficiency is not required for completion.

### `languages.proficiency_assessment`

```text
load
→ profile
→ reason
→ assess (languages.assess_sample)
→ level_update (languages.update_level_evidence)
→ evidence_gate
→ complete
```

`evidence_gate` must read exact output fields proving:
- no certificate overwritten;
- stable update only if supported;
- missing skills preserved.

### `languages.adaptive_language_lesson`

```text
load
→ profile
→ reason
→ lesson (languages.generate_lesson)
→ exercises (languages.generate_exercises)
→ review (languages.review_exercise)
→ difficulty_gate
→ complete
```

Gate proves no direct stable-proficiency mutation from one session.

### `languages.conversation_roleplay_practice`

```text
load
→ profile
→ reason
→ conversation_turn (languages.generate_conversation_turn)
→ roleplay_turn (languages.generate_roleplay_turn)
→ speaking_review (languages.review_speaking)
→ error_review (languages.review_errors)
→ practice_gate
→ complete
```

The workflow represents a reusable practice segment. Multi-turn continuation is workflow/session state in shared infrastructure; neither turn operation implements a loop.

### `languages.writing_review`

```text
load
→ profile
→ reason
→ review (languages.review_writing)
→ variety_gate
→ evidence_gate
→ complete
```

Valid alternatives must survive.

### `languages.error_remediation`

```text
load
→ profile
→ reason
→ error_review (languages.review_errors)
→ exercises (languages.generate_exercises)
→ review (languages.review_exercise)
→ pattern_gate
→ complete
```

Pattern gate reads the actual pattern-evidence field.

### `languages.vocabulary_spaced_review`

```text
load
→ profile
→ reason
→ vocabulary (languages.track_vocabulary)
→ review_plan (languages.plan_review_schedule)
→ no_calendar_mutation_gate
→ complete
```

Gate directly reads `calendar_modified=False` from `review_plan`.

### `languages.certification_preparation`

```text
load
→ profile
→ reason
→ certification (languages.prepare_certification)
→ temporal_gate
→ external_action_gate
→ complete
```

`temporal_gate` reads `needs_verification` / `official_source_status` in a way consistent with the output schema; do not mark unknown verification as success.

`external_action_gate` directly reads:
- `registration_performed=False`;
- `payment_performed=False`;
- `submission_performed=False`.

### `languages.progress_checkpoint`

```text
load
→ profile
→ reason
→ progress (languages.generate_progress_review)
→ progression_gate
→ complete
```

One isolated improvement cannot be marked as stable progression.

- [ ] **Step 1: RED catalog + shared-node tests**

Assert exact 9, exact names, known operations, acyclic dependencies, shared node types.

- [ ] **Step 2: RED direct dependency gate audit**

For every `VALIDATE` node:
1. extract each `wait_condition` field;
2. assert at least one direct dependency is an `EXECUTE_OPERATION` node or other direct producer whose declared output schema contains that exact field;
3. assert workflow metadata does not pre-populate that runtime-derived field.

This test is mandatory.

- [ ] **Step 3: RED real shared-engine violations**

Use the actual Workflow Engine adapter pattern from Concerns tests.

Required failures:
- `stable_update_supported=True` where gate expects false in an insufficient-evidence scenario;
- valid variety incorrectly marked error -> writing gate fails;
- `pronunciation_assessed=True` from transcript-only semantics -> practice gate fails where applicable;
- `calendar_modified=True` -> vocabulary/review workflow fails;
- `registration_performed=True` -> certification workflow fails;
- `payment_performed=True` -> certification workflow fails;
- missing required runtime gate field -> `validate.condition_unknown` / equivalent fail-closed outcome.

- [ ] **Step 4: GREEN workflows**

Build `LANGUAGES_WORKFLOW_NAMES_BY_ID` from catalog only; no duplicated display-name tuple.

- [ ] **Step 5: Verify + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_workflows.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/workflows.py \
  tests/domains/test_languages_domain_workflows.py

git diff --check

git add \
  cmm/domains/languages/workflows.py \
  tests/domains/test_languages_domain_workflows.py

git commit -m "feat(domains): add languages workflows"
```

---

# Task 9 — Permissions + consent-gated Domain Memory Integration

**Files:**
- Create: `cmm/domains/languages/permissions.py`
- Create: `cmm/domains/languages/memory.py`
- Test: `tests/domains/test_languages_domain_permissions.py`
- Test: `tests/domains/test_languages_domain_memory.py`

## Permission policy

Canonical policy ID:

```text
domain-permission:languages:1.0.0
```

Baseline allowed capabilities:

```text
RESOURCE_READ
MEMORY_READ
OPERATION_EXECUTE
WORKFLOW_EXECUTE
MEMORY_WRITE
```

`MEMORY_WRITE` is **eligibility for the shared approved apply path**, not
autonomous permission. It must be approval-gated. Configure the policy using
the current shared contract so that an unapproved write cannot resolve to
ALLOW:

```text
MEMORY_WRITE ∈ allowed_capabilities
MEMORY_WRITE ∈ approval_capabilities
allow_memory_write = True
```

If the shared mandatory-approval table already includes `MEMORY_WRITE`, retain
the explicit Languages approval requirement unless the contract rejects
duplication. The implementation test must prove the effective resolver/gate
behavior, not rely on tuple membership alone.

Directly prohibited capabilities include:

```text
COMMUNICATION_EXTERNAL
FILE_MODIFY
TASK_CREATE
SCHEDULE_MODIFY
GOAL_UPDATE
PUBLICATION
IRREVERSIBLE_CHANGE
KNOWLEDGE_DELETE
PERMISSION_MODIFY
FINANCIAL_ACTION
FINANCIAL_SPEND
```

Do **not** place `MEMORY_WRITE` in `prohibited_capabilities`: the shared
permission evaluator gives explicit prohibition DENY precedence, which would
make the frozen 10.15 Languages opt-in persistence requirement impossible.

Also prohibit direct external-model use unless existing global/session policy explicitly composes otherwise.

External search:
- Languages itself does not implement search.
- Current certification verification is a shared read-only external capability.
- Express it using the existing permission/source-requirement mechanism, not a Languages operation.
- If the current DomainPermissionPolicy contract cannot represent “conditionally approved read-only official verification” without widening ordinary Languages access, STOP and report the exact shared-contract limitation instead of setting `allow_external_search=True` broadly.

Calendar:
- `allow_schedule_modification=False`;
- review planning remains internal proposal-only;
- shared calendar mutation requires the external/shared operation approval path.

Cross-domain:
- outbound cross-domain access is not default broad access;
- inbound minimal authorized domain-result projections are allowed according to shared composition policy;
- most-restrictive wins.

Autonomy:

```python
DomainAutonomyLimits(
    maximum_autonomy_level=0,
    allow_reversible_changes=False,
    allow_irreversible_changes=False,
)
```

## Memory helper API

Mirror the hardened shared proposal/binding path:

```python
build_languages_memory_view_request(...)
build_languages_memory_view(...)
build_languages_memory_proposal(...)
build_languages_memory_binding(...)
validate_languages_memory_binding(...)
```

`build_languages_memory_proposal()` always produces a proposal with:

```text
DomainMemoryProposalKind.MEMORY_UPDATE
required_capabilities=(DomainMemoryCapability.PROPOSE,)
requires_confirmation=True
```

No override may silently turn confirmation off.

Define a deterministic classifier for candidate longitudinal kinds:

```text
estimated_proficiency
skill_profile
language_goal
learning_plan
error_pattern
vocabulary_review_state
grammar_review_state
certification_target
progress_history
```

Session-only observations do not require persistence.

- [ ] **Step 1: RED permission identity and deny defaults**

- [ ] **Step 2: RED literal authorization**

`True` is distinct from `"true"`, `1`, `{}`, and arbitrary caller labels.

- [ ] **Step 3: RED memory proposal + real permission lifecycle**

Prove with the actual Phase 10.15 permission resolver/gate and ApprovalService
contracts:

- building a proposal is allowed without applying a mutation;
- proposal construction does not consume a write grant;
- no grant/approval means the apply/write path is not ALLOW and no persistence occurs;
- proposal requires confirmation;
- binding digest matches view/proposal refs;
- malformed/incomplete approval chain fails closed;
- a valid scoped approval/grant bound to the correct actor, session, domain,
  action and proposal purpose can authorize the shared apply path;
- a one-shot grant cannot authorize a second mutation;
- an expired grant fails;
- an out-of-scope grant fails;
- a supporting domain cannot widen the effective permission;
- Languages helper itself never applies mutation.

This is the implementation proof of the Phase 10.15 requirement:
`Languages memory opt-in: no grant -> no persistence; scoped grant -> allowed
through the canonical lifecycle`.

- [ ] **Step 4: RED repetition-not-consent**

Repeated vocabulary/error observations do not authorize persistence.

- [ ] **Step 5: GREEN permissions/memory**

Use the exact shared contracts already used by Concerns.

- [ ] **Step 6: Verify + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_permissions.py \
  tests/domains/test_languages_domain_memory.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/permissions.py \
  cmm/domains/languages/memory.py \
  tests/domains/test_languages_domain_permissions.py \
  tests/domains/test_languages_domain_memory.py

git diff --check

git add \
  cmm/domains/languages/permissions.py \
  cmm/domains/languages/memory.py \
  tests/domains/test_languages_domain_permissions.py \
  tests/domains/test_languages_domain_memory.py

git commit -m "feat(domains): add languages permissions and memory"
```

---

# Task 10 — Presentation parity + reference-only trace

**Files:**
- Create: `cmm/domains/languages/presentation.py`
- Create: `cmm/domains/languages/trace.py`
- Test: `tests/domains/test_languages_domain_presentation.py`
- Test: `tests/domains/test_languages_domain_trace.py`

## Presentation contract

`present_languages_result(result)` must preserve semantic fields from actual operation outputs, not only synthetic presentation-shaped fixtures.

Presentation states must preserve at minimum:

```text
certified
estimated
observed_performance
valid_alternative
observed_error
supported_pattern
insufficient_evidence
needs_verification
candidate_memory_update
```

Output sections:

```text
objective
activity
feedback
strengths
observed_errors
supported_patterns
skill_evidence
proficiency_interpretation
uncertainty
missing_evidence
next_practice
progress_context
external_action_state
memory_state
```

Not every section must be populated, but no semantic state may be upgraded.

Required parity tests pass the **actual outputs** of all 15 helper functions through `present_languages_result()`.

Examples:

```python
actual = assess_sample_result(...)
presented = present_languages_result(actual)
assert presented["proficiency_kind"] == "OBSERVED_PERFORMANCE"

actual = review_writing_result(... valid British alternative ...)
presented = present_languages_result(actual)
assert presented["valid_alternatives"]
assert not presented["errors_from_valid_variety"]

actual = review_speaking_result(transcript=..., pronunciation_evidence=())
presented = present_languages_result(actual)
assert presented["pronunciation_assessed"] is False
```

## Trace wrapper

Mirror final Concerns trace wrapper capabilities:

```python
build_languages_trace_reference(...)
build_languages_trace_contribution(...)
build_supporting_trace_contribution(...)
assemble_languages_trace(
    ...,
    supporting_domains=(),
    contributions=(),
    cross_domain_results=(),
)
validate_languages_trace(...)
```

Trace must be able to reference actual IDs for:

```text
language / goal resolution
profile mode
resource resolution
assessment evidence
proficiency kind/result
skill scope
rule results
operation results
workflow result
permission decisions
memory proposal/approval
certification source/verification
cross-domain result
presentation result
```

No symbolic IDs invented from prose inside acceptance tests.

- [ ] **Step 1: RED presentation actual-helper parity**

- [ ] **Step 2: RED certainty non-amplification**

Observed performance never presents as stable estimate/certification.

- [ ] **Step 3: RED variety and pronunciation preservation**

- [ ] **Step 4: RED trace supporting-domain support**

Use `DomainTraceReferenceInventory` with non-empty expected supporting domains, as the remediated Concerns precedent does.

- [ ] **Step 5: RED strict JSON**

```python
json.dumps(presented, allow_nan=False)
json.dumps(trace.to_dict(), allow_nan=False)
```

- [ ] **Step 6: GREEN presentation/trace**

- [ ] **Step 7: Verify + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_presentation.py \
  tests/domains/test_languages_domain_trace.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/presentation.py \
  cmm/domains/languages/trace.py \
  tests/domains/test_languages_domain_presentation.py \
  tests/domains/test_languages_domain_trace.py

git diff --check

git add \
  cmm/domains/languages/presentation.py \
  cmm/domains/languages/trace.py \
  tests/domains/test_languages_domain_presentation.py \
  tests/domains/test_languages_domain_trace.py

git commit -m "feat(domains): add languages presentation and trace"
```

---

# Task 11 — Validation-first integration, rollback, bootstrap, public API

**Files:**
- Create: `cmm/domains/languages/integration.py`
- Create: `cmm/domains/languages/bootstrap.py`
- Create: `cmm/domains/languages/__init__.py`
- Test: `tests/domains/test_languages_domain_integration.py`

**Interfaces:**

```python
class LanguagesDomainIntegrationResult:
    definition
    profile
    resources
    rules
    operations
    workflows
    permission_policy

register_languages_domain(...)

@dataclass(frozen=True, slots=True)
class LanguagesDomainBootstrap:
    domain_registry
    profile_registry
    resource_registry
    rule_registry
    operation_registry
    workflow_registry
    permission_registry
    resolver

build_standard_languages_domain_bootstrap(
    *,
    operation_implementations: dict | None = None,
)
```

## Registration algorithm

Copy the proven pattern structurally, not domain semantics:

```text
build all components
↓
_validate_all against every target registry
↓
validate injected operation implementations
↓
validate duplicate domain/profile/resources/rules/operations/workflows/permission
↓
capture snapshot_state() for every provided mutable registry
↓
register in deterministic order
↓
on any exception after mutation:
    restore_state() every snapshot in reverse dependency order
↓
return LanguagesDomainIntegrationResult
```

Missing implementations register operations UNAVAILABLE by default.

## RED cases

1. complete pack registers;
2. exactly 15 resources, 14 rules, 15 operations, 9 workflows;
3. profile and permission registered;
4. all operations unavailable by default;
5. unknown injected operation implementation fails before first mutation;
6. implementation-definition mismatch fails before first mutation;
7. duplicate domain;
8. duplicate profile;
9. duplicate resource;
10. duplicate rule;
11. duplicate operation including common registry collision;
12. duplicate workflow including common registry collision;
13. duplicate permission policy;
14. injected failure after each meaningful registration stage restores exact snapshots;
15. unrelated pre-existing entries survive rollback;
16. retry after rollback succeeds;
17. bootstrap starts from `build_standard_general_domain_bootstrap()` and reuses the exact registry objects;
18. General remains fallback;
19. fresh bootstrap calls are independent/deterministic;
20. importing `cmm.domains.languages` does not register anything.

## Fresh import gate

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import cmm.domains.languages
from cmm.domains.registry import DomainRegistry

assert DomainRegistry().get("domain:languages") is None
print("LANGUAGES_FRESH_IMPORT=PASS")
PY
```

## Package-boundary test

At final package completion:

```python
expected = {
    "__init__.py",
    "bootstrap.py",
    "catalog.py",
    "definition.py",
    "integration.py",
    "memory.py",
    "operations.py",
    "permissions.py",
    "presentation.py",
    "profile.py",
    "resources.py",
    "rules.py",
    "trace.py",
    "workflows.py",
}
assert {p.name for p in Path("cmm/domains/languages").glob("*.py")} == expected
```

## Public API

`__init__.py` exports Languages package surface only. It must not execute registration.

- [ ] **Step 1: RED integration/rollback**
- [ ] **Step 2: GREEN integration**
- [ ] **Step 3: RED bootstrap/fallback/import**
- [ ] **Step 4: GREEN bootstrap/public API**
- [ ] **Step 5: Verify + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_integration.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/integration.py \
  cmm/domains/languages/bootstrap.py \
  cmm/domains/languages/__init__.py \
  tests/domains/test_languages_domain_integration.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import cmm.domains.languages
from cmm.domains.registry import DomainRegistry
assert DomainRegistry().get("domain:languages") is None
print("LANGUAGES_FRESH_IMPORT=PASS")
PY

git diff --check

git add \
  cmm/domains/languages/integration.py \
  cmm/domains/languages/bootstrap.py \
  cmm/domains/languages/__init__.py \
  tests/domains/test_languages_domain_integration.py

git commit -m "feat(domains): integrate languages domain pack"
```

---

# Task 12 — Cross-domain ownership and purpose-minimized composition

**Files:**
- Test: `tests/domains/test_languages_domain_cross_domain.py`
- Production changes: only inside `cmm/domains/languages/` if an existing shared extension point must be configured. Do not modify sibling domain internals.

Required ownership cases:

```text
"Prepare me for Catalan C1."
→ Languages primary

"I need C1 Catalan because the opposition requires it."
→ Oppositions primary + Languages supporting

"Let's practice the oral C1."
→ Languages primary; Oppositions context optional/supporting

"Organize my university English presentation."
→ University primary + Languages supporting

"Explain the French Revolution in B1 English so I can practice reading."
→ Languages primary + General supporting

"I'm worried I'll never speak English well."
→ Concerns primary + Languages supporting

"Why does speaking Catalan feel tied to my identity?"
→ Reflection primary + Languages supporting
```

## Projection minimization

Allowed exported examples:

```text
certification_status
estimated_readiness
relevant_proficiency
progress_toward_shared_goal
recommended_workload
blocking_language_gap
```

Denied/unnecessary by default:

```text
complete_vocabulary_history
all_observed_errors
all_conversation_transcripts
all_writing_corrections
full_languages_memory
```

## Required tests

- no direct import from `cmm.domains.university`, `oppositions`, `concerns`, `reflection`, `relationships`, or `health` inside Languages production;
- `domain_result` is the shared cross-domain boundary;
- supporting domain cannot widen permissions;
- malformed authorization fails closed;
- outbound projection contains only requested/authorized kinds;
- a concern about language does not become evidence of low proficiency;
- identity reflection does not become language deficit;
- academic/opposition requirement does not become language proficiency evidence;
- Languages evidence does not automatically become emotional reassurance.

Use the real resolver/composition contracts where available. Do not fake primary/supporting ownership only with comments.

- [ ] **Step 1: RED boundary tests**
- [ ] **Step 2: GREEN only if package configuration is required**
- [ ] **Step 3: Verify**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_cross_domain.py \
  tests/domains/test_cross_domain_*.py \
  tests/domains/test_domain_composition_*.py

git diff --check
```

- [ ] **Step 4: Commit**

```bash
git add \
  tests/domains/test_languages_domain_cross_domain.py \
  cmm/domains/languages

git diff --cached --check
git commit -m "test(domains): enforce languages cross-domain boundaries"
```

The `git add cmm/domains/languages` line is allowed only for actual Languages package changes from this task; inspect staged diff before committing.

---

# Task 13 — DP-026 connected acceptance + adversarial gates

**Files:**
- Create: `tests/domains/test_languages_domain_dp026_acceptance.py`
- Create: `tests/domains/test_languages_domain_adversarial.py`

## Connected AT-DP-026 scenario

Implement one state-linked deterministic acceptance harness equivalent to the frozen 45-step scenario.

It must execute public/shared contracts, not a narrative sequence of disconnected helper calls.

Required chain:

```text
request
→ real resolver selects Languages primary
→ onboarding state
→ preferred variety
→ two concurrent goals
→ explicit longitudinal tracking authorization state
→ certified prior evidence
→ real assess_sample helper/operation implementation
→ observed writing performance
→ explicit missing speaking evidence
→ update_level_evidence proposal
→ learning-plan result
→ Adaptive Language Lesson workflow
→ real exercise result
→ first observed error
→ no recurrent pattern yet
→ Conversation & Roleplay Practice workflow
→ later comparable error evidence
→ ErrorPatternEvidenceRule
→ writing review
→ valid variety alternative preserved
→ languages.progress_checkpoint
→ one isolated better score does not become stable progression
→ comparable accumulated evidence updates progression only as justified
→ certification target
→ stale guide conflicts with current official source
→ current official source wins / unresolved if authority tied
→ certification readiness remains distinct from proficiency
→ review schedule proposal
→ no calendar mutation
→ shared approval boundary for calendar mutation request
→ memory proposal
→ permission/consent chain
→ Oppositions supporting/primary composition scenario
→ minimal domain_result projection
→ presentation
→ trace using actual IDs/results from the connected execution
```

The test harness may use deterministic operation implementations injected through the existing registry mechanism. It does not need an LLM.

Do not handcraft symbolic trace IDs like `"rule:some-result"` unless that exact ID was produced by a real preceding test adapter/contract.

## Required named gates

```text
MULTI_LANGUAGE_STATE_GATE
MULTI_GOAL_GATE
PROFICIENCY_KIND_GATE
SKILL_SEPARATION_GATE
VARIETY_VALIDITY_GATE
FRAMEWORK_NON_IDENTITY_GATE
OBSERVED_ERROR_NOT_PATTERN_GATE
ERROR_PATTERN_EVIDENCE_GATE
CORRECTION_PRIORITY_GATE
ADAPTIVE_DIFFICULTY_GATE
ONE_SESSION_NOT_LEVEL_GATE
TRANSCRIPT_NOT_PRONUNCIATION_GATE
PROGRESSION_EVIDENCE_GATE
CERTIFICATION_TEMPORAL_GATE
READINESS_NOT_PROFICIENCY_GATE
CULTURAL_CONTEXT_GATE
SESSION_NOT_MEMORY_GATE
MEMORY_CONSENT_GATE
CALENDAR_PROPOSAL_NOT_WRITE_GATE
EXTERNAL_ACTION_BOUNDARY_GATE
CROSS_DOMAIN_MINIMIZATION_GATE
PRESENTATION_PARITY_GATE
TRACE_ACTUAL_REFERENCE_GATE
INPUT_ORDER_INVARIANCE_GATE
DUPLICATE_EVIDENCE_GATE
MALFORMED_EVIDENCE_GATE
INPUT_NON_MUTATION_GATE
STRICT_JSON_GATE
PACKAGE_BOUNDARY_GATE
```

## Adversarial matrix

At minimum:

1. one excellent writing sample presented as C1 proof;
2. one bad session presented as regression;
3. grammar score used to infer interaction;
4. transcript used to infer pronunciation;
5. valid British spelling under American preference marked error;
6. arbitrary variety string trusted as valid;
7. same error duplicated under different caller IDs with same provenance;
8. repeated same sentence treated as independent error recurrence;
9. CEFR/IELTS equivalence asserted without mapping evidence;
10. stale certification guide overriding current official source;
11. equivalent official sources conflict;
12. readiness promoted to general proficiency;
13. progress update persisted without valid consent chain;
14. `"true"` / `1` used as authorization;
15. review scheduling mutates calendar;
16. certification preparation registers/pays/submits;
17. Oppositions receives full language memory;
18. Concerns worry becomes proficiency evidence;
19. Reflection identity narrative becomes linguistic deficit;
20. malformed numeric confidence/difficulty values including NaN/Inf;
21. operation helper output violates declared schema;
22. workflow gate field absent from direct dependency;
23. workflow metadata tries to mask a runtime violation;
24. input-order permutations change semantic result;
25. input mutation.

## Focused suite

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_*.py
```

- [ ] **Step 1: RED connected acceptance**
- [ ] **Step 2: GREEN only through existing real package/shared contracts**
- [ ] **Step 3: RED adversarial matrix**
- [ ] **Step 4: GREEN real defects only**
- [ ] **Step 5: Full focused suite**
- [ ] **Step 6: Commit**

```bash
git add \
  tests/domains/test_languages_domain_dp026_acceptance.py \
  tests/domains/test_languages_domain_adversarial.py \
  cmm/domains/languages

git diff --cached --check
git commit -m "test(domains): add DP-026 acceptance gates"
```

Inspect staged production changes and reject unrelated refactors.

---

# Task 14 — Reference documentation + implementation status

**Files:**
- Create: `docs/reference/languages-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify minimally: `ROADMAP.md`
- Test: add structural documentation assertions to `tests/domains/test_languages_domain_catalog.py` or acceptance file if useful.

Only do this after all implementation tests are green.

## `docs/reference/languages-domain.md`

Write an operational technical reference, not a copy of the 4,535-line spec.

Must include:
- identity/version/profile;
- exact 16/15/14/15/9 catalog;
- skill model;
- certified/estimated/observed distinction;
- variety policy;
- error-pattern threshold semantics;
- correction priority;
- adaptive difficulty;
- progression;
- certification temporal policy;
- permission/memory boundaries;
- cross-domain ownership;
- workflow IDs;
- package boundary;
- test/acceptance entry points;
- limitations/non-goals.

## Requirements matrix

Update `DP-026` mapping from:

```text
frozen canonical design; implementation pending
REQUIRES_PHASE_INSPECTION
```

to implementation-side repository mapping/status equivalent to:

```text
implemented; pending independent audit
REQUIRES_PHASE_INSPECTION
```

Set `AT-DP-026` implementation evidence to PASS **only if the connected acceptance test actually passes**, while making clear that independent audit closure is separate.

Do not mark the domain independently audited.

## Phase 10 roadmap

Change only 10.26 status from:

```text
Design frozen. Implementation pending.
```

to:

```text
Implemented, pending independent audit.
```

Preserve 10.27 Paternidad untouched.

## General roadmap

Update Phase 10 current progress minimally:

```text
Phase 10.19–10.25 complete and audited.
Phase 10.26 implemented, pending independent audit.
Phase 10.27–10.30 pending.
```

- [ ] **Step 1: RED/document consistency assertions**
- [ ] **Step 2: Update docs**
- [ ] **Step 3: Verify no Paternidad/Nil regression**

```bash
git grep -n -I -E 'domain:nil|nil\.|(^|[^[:alnum:]_])Nil([^[:alnum:]_]|$)' \
  -- ROADMAP.md docs cmm tests \
  && exit 1 || true

git grep -n -E 'domain:parenthood|parenthood\.journey|parenthood\.child:<child_id>' \
  -- ROADMAP.md docs/roadmap docs/reference
```

- [ ] **Step 4: Verify focused tests + diff**
- [ ] **Step 5: Commit**

```bash
git add \
  ROADMAP.md \
  docs/reference/languages-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  tests/domains/test_languages_domain_catalog.py \
  tests/domains/test_languages_domain_dp026_acceptance.py

git diff --cached --check
git commit -m "docs(domains): document phase 10.26 languages implementation"
```

Only stage test files if this task actually modified them.

---

# Task 15 — Final self-audit and verification ladder

No production behavior should be added in this task unless a real failing gate is reproduced first with a RED regression.

## A. Scope audit

```bash
git status --short --branch
git diff --stat HEAD~14..HEAD 2>/dev/null || true
```

Review actual implementation range rather than assuming exactly 14 commits.

Expected production package is exactly 14 modules.

No unexpected shared production file should have changed. Any shared change requires an explicit previously approved architectural blocker.

## B. Placeholder scan

```bash
rg -n \
  'TODO|FIXME|TBD|PLACEHOLDER|XXX|NotImplemented|raise NotImplementedError' \
  cmm/domains/languages \
  tests/domains/test_languages_domain_*.py \
  docs/reference/languages-domain.md \
  docs/superpowers/plans/2026-08-23-languages-domain-implementation.md \
  || true
```

No required behavior may remain deferred.

## C. Forbidden architecture/dependency scan

```bash
find cmm/domains/languages -maxdepth 1 -type f -name '*.py' | sort

rg -n \
  'from cmm\.domains\.(university|oppositions|concerns|reflection|relationships|health)\.|import cmm\.domains\.(university|oppositions|concerns|reflection|relationships|health)\.' \
  cmm/domains/languages \
  && exit 1 || true

rg -n \
  'Language(Agent|Planner|WorkflowEngine|MemoryStore|KnowledgeStore|KnowledgeGraph|ConversationEngine|AssessmentEngine|LessonEngine|Scheduler)' \
  cmm/domains/languages \
  && exit 1 || true
```

## D. Focused Languages

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_*.py
```

## E. Relevant sibling/shared regressions

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_concerns_domain_*.py \
  tests/domains/test_reflection_domain_*.py \
  tests/domains/test_university_domain_*.py \
  tests/domains/test_oppositions_domain_*.py \
  tests/domains/test_cross_domain_*.py \
  tests/domains/test_domain_composition_*.py \
  tests/domains/test_domain_permission_*.py \
  tests/domains/test_domain_memory_*.py \
  tests/domains/test_domain_operation_*.py \
  tests/domains/test_domain_profile_*.py \
  tests/domains/test_domain_presentation_*.py \
  tests/domains/test_domain_trace_*.py \
  tests/domains/test_domain_workflow_*.py
```

If a glob has no matches in the current shell, use actual existing file names rather than weakening coverage.

## F. Entire Domain suite

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains
```

## G. Global suite

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q
```

Do not hard-code expected test totals. Exit code 0 and complete collection/execution are required.

## H. Ruff

```bash
.venv/bin/ruff check \
  cmm/domains/languages \
  tests/domains/test_languages_domain_*.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages \
  tests/domains/test_languages_domain_*.py
```

## I. Compile / fresh import

```bash
.venv/bin/python -m compileall -q cmm/domains/languages

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
from pathlib import Path

before = set()

import cmm.domains.languages
from cmm.domains.registry import DomainRegistry

assert DomainRegistry().get("domain:languages") is None

expected = sorted([
    "__init__.py",
    "bootstrap.py",
    "catalog.py",
    "definition.py",
    "integration.py",
    "memory.py",
    "operations.py",
    "permissions.py",
    "presentation.py",
    "profile.py",
    "resources.py",
    "rules.py",
    "trace.py",
    "workflows.py",
])
actual = sorted(path.name for path in Path("cmm/domains/languages").glob("*.py"))

assert actual == expected, (actual, expected)
print("LANGUAGES_FRESH_IMPORT=PASS")
print("LANGUAGES_PACKAGE_BOUNDARY=PASS")
PY
```

## J. Canonical counts runtime probe

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_ENTITY_TYPES,
    CANONICAL_LANGUAGES_OPERATION_IDS,
    CANONICAL_LANGUAGES_RESOURCE_IDS,
    CANONICAL_LANGUAGES_RULE_IDS,
    CANONICAL_LANGUAGES_WORKFLOW_IDS,
)

assert len(CANONICAL_LANGUAGES_ENTITY_TYPES) == 16
assert len(CANONICAL_LANGUAGES_RESOURCE_IDS) == 15
assert len(CANONICAL_LANGUAGES_RULE_IDS) == 14
assert len(CANONICAL_LANGUAGES_OPERATION_IDS) == 15
assert len(CANONICAL_LANGUAGES_WORKFLOW_IDS) == 9

print("LANGUAGES_CANON=16_15_14_15_9")
PY
```

## K. Diff hygiene

```bash
git diff --check
git status --short --branch
```

Expected after implementation commits:

```text
tracked worktree clean
known untracked tmp/ only
```

## L. Final semantic self-audit

Explicitly inspect for:

```text
single sample -> stable level
estimate -> certificate
certificate overwritten
global level hiding skill gap
cross-skill inflation
valid variety -> error
preferred variety -> exclusive correctness
framework mapping -> identity
one error -> pattern
duplicate evidence inflation
same sentence -> independent recurrence
one better score -> stable progression
one bad session -> stable regression
transcript -> pronunciation
exam readiness -> general proficiency
stale guide -> current official truth
cultural tendency -> universal stereotype
session state -> persistent memory
profile-level monotonic deny -> blocks valid opt-in long-term memory path
MEMORY_WRITE prohibited -> makes scoped grant impossible
repetition -> consent
calendar proposal -> calendar mutation
certification preparation -> registration/payment/submission
supporting domain -> permission widening
cross-domain relevance -> full-history sharing
language worry -> proficiency evidence
identity reflection -> deficit
helper output != operation schema
workflow gate field missing from direct producer
runtime safety default hidden in workflow metadata
fake trace IDs
import-time side effect
partial registry state after failure
```

If a real defect is found: reproduce → RED → minimal fix → rerun full affected verification → follow-up commit. Do not bury it in a final cleanup.

---

# Definition of Done

All items must be true:

```text
[ ] domain:languages registered through existing Domain Registry
[ ] display name Idiomas
[ ] LanguageLearningProfile registered
[ ] six pedagogical modes represented
[ ] exactly 14 production modules
[ ] exactly 16 entities
[ ] exactly 15 resources
[ ] exactly 14 rules
[ ] exactly 15 operations
[ ] exactly 9 workflows
[ ] catalog.py is the only canonical catalog source
[ ] multi-language independent state semantics
[ ] multiple concurrent goals per language
[ ] certified / estimated / observed proficiency preserved
[ ] skill-specific proficiency preserved
[ ] language varieties handled without false errors
[ ] framework mappings non-identity
[ ] one error does not become pattern
[ ] correction priority protects fluency
[ ] difficulty adapts without unstable level mutation
[ ] spaced review semantics implemented
[ ] workload semantics implemented
[ ] goal alignment implemented
[ ] stable progression requires comparable evidence
[ ] certification temporal authority implemented
[ ] cultural context remains evidence-qualified
[ ] longitudinal memory is structurally eligible but consent/policy/approval gated
[ ] all operation helper outputs satisfy declared output schema
[ ] all helper-required inputs are expressible by operation input schema
[ ] all workflow gates consume exact fields from direct dependencies
[ ] no runtime-derived safety/epistemic safe defaults in workflow metadata
[ ] conversation/roleplay operations are turn-level
[ ] transcript alone never proves pronunciation
[ ] review schedule never writes calendar
[ ] certification prep never registers/pays/submits
[ ] permissions fail closed
[ ] memory uses shared proposals/bindings only
[ ] presentation preserves semantic distinctions using actual helper outputs
[ ] trace uses actual reference IDs and supports supporting domains
[ ] cross-domain projections are purpose-minimized
[ ] General remains fallback
[ ] registration validation-first
[ ] rollback exact snapshot parity
[ ] operations unavailable by default without implementations
[ ] fresh import has zero registration side effects
[ ] AT-DP-026 is one connected execution, not disconnected helper narration
[ ] adversarial matrix green
[ ] focused Languages suite green
[ ] relevant shared/sibling regressions green
[ ] tests/domains green
[ ] global pytest green
[ ] Ruff green
[ ] Ruff py310 green
[ ] compileall green
[ ] diff hygiene green
[ ] tracked worktree clean
[ ] docs say Implemented, pending independent audit
[ ] no claim of independent audit success
[ ] no push
[ ] no merge
```

---

# Expected Implementation Commit Sequence

The exact number may change only when a real RED defect requires a follow-up fix.

```text
feat(domains): define languages domain catalog
feat(domains): add languages resources and profile
feat(domains): add languages proficiency semantics
feat(domains): add languages error and correction semantics
feat(domains): complete languages reasoning rules
feat(domains): add languages core operations
feat(domains): complete languages operations
feat(domains): add languages workflows
feat(domains): add languages permissions and memory
feat(domains): add languages presentation and trace
feat(domains): integrate languages domain pack
test(domains): enforce languages cross-domain boundaries
test(domains): add DP-026 acceptance gates
docs(domains): document phase 10.26 languages implementation
```

A final follow-up `fix(domains): ...` is preferable to amending history if post-commit verification exposes a real defect.

---

# Final Implementation Report Required

Return exact fresh evidence:

1. starting HEAD and branch;
2. commits created;
3. production files created/modified;
4. test files created/modified;
5. canonical `16/15/14/15/9` counts;
6. `LanguageLearningProfile` and modes;
7. focused Languages result;
8. relevant sibling/shared regression result;
9. all-domain result;
10. global-suite result;
11. Ruff normal;
12. Ruff py310;
13. compileall;
14. fresh import;
15. package boundary;
16. helper/output schema parity;
17. workflow direct-producer gate audit;
18. DP-026 connected acceptance status;
19. permission/memory consent status;
20. cross-domain minimization status;
21. documentation/matrix/roadmap status;
22. `git diff --check`;
23. final `git status --short --branch`;
24. residual risks/findings, if any;
25. confirmation that no push/merge occurred.

End with:

```text
PHASE10_26_IMPLEMENTATION_STATUS:
IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
```

only if every implementation-side gate above passes.

Do not say Phase 10.26 is independently audited or closed.
