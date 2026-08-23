# Languages Domain (`domain:languages`)

**Phase:** 10.26
**Status:** V2 findings remediated — independent V3 audit pending
**Canonical identity:** `domain:languages` · namespace `languages.*` · version `1.0.0`
**Canonical profile:** `LanguageLearningProfile`
**Design (frozen):** `docs/superpowers/specs/2026-08-23-languages-domain-design.md`
**Acceptance:** `DP-026` / `AT-DP-026`

---

## 1. Purpose

Languages is CMM OS's **language learning, practice, and proficiency domain pack**. It provides structured language pedagogy, diagnostic assessment, error correction, adaptive difficulty, spaced review, and certification preparation.

Its behavioral center respects critical epistemic boundaries:

```text
certified proficiency != estimated proficiency != observed performance
global proficiency != proficiency by skill
preferred variety != only valid variety
valid variety difference != error
transcript != pronunciation evidence
observed error != error pattern
```

## 2. Package boundary

Exactly fourteen production modules — no parallel planner, agent runtime, memory store, knowledge store/graph, workflow engine, permission engine, lesson engine, or spaced repetition engine:

```text
cmm/domains/languages/
├── __init__.py      # public surface, definitions only, no import side effects
├── bootstrap.py     # LanguagesDomainBootstrap (General + Languages)
├── catalog.py       # single source of truth for canonical members
├── definition.py    # immutable DomainDefinition
├── integration.py   # atomic validation-first registration + rollback
├── memory.py        # proposal-only shared memory contracts (consent-gated)
├── operations.py    # 15 analysis/planning/preparation operations
├── permissions.py   # fail-closed policy (MEMORY_WRITE approval-gated)
├── presentation.py  # semantics-preserving projection (epistemic badges)
├── profile.py       # LanguageLearningProfile (6 pedagogical modes)
├── resources.py     # 15 resource definitions over shared adapters
├── rules.py         # deterministic helpers + 14 reasoning rules
├── trace.py         # reference-only Phase 10.17 trace composition
└── workflows.py     # 9 workflows on the shared Workflow Engine
```

Importing `cmm.domains.languages` has zero registration side effects; fresh import leaves every registry untouched.

## 3. Canonical catalog

| Surface | Count | Members |
|---|---|---|
| Entities | 16 | `language`, `language_variety`, `skill_dimension`, `language_goal`, `proficiency_framework`, `proficiency_record`, `assessment_evidence`, `practice_session`, `exercise`, `observed_error`, `error_pattern`, `vocabulary_item`, `grammar_topic`, `certification_target`, `review_item`, `learning_plan` |
| Resources | 15 | `languages.user_message`, `languages.conversation`, `languages.writing_sample`, `languages.audio_transcript`, `languages.exercise_result`, `languages.assessment_result`, `languages.language_plan`, `languages.lesson_material`, `languages.vocabulary_list`, `languages.language_reference`, `languages.certification_guide`, `languages.official_certification_source`, `languages.calendar_event`, `languages.memory_entry`, `languages.domain_result` |
| Rules | 14 | `LanguageLevelEvidenceRule`, `SkillSeparationRule`, `LanguageVarietyValidityRule`, `ProficiencyFrameworkRule`, `ErrorPatternEvidenceRule`, `CorrectionPriorityRule`, `AdaptiveDifficultyRule`, `SpacedReviewRule`, `LearningLoadRule`, `GoalAlignmentRule`, `ProgressionEvidenceRule`, `CertificationTemporalRule`, `CulturalContextEvidenceRule`, `LanguageMemoryConsentRule` |
| Operations | 15 | `languages.assess_sample`, `languages.update_level_evidence`, `languages.create_learning_plan`, `languages.generate_lesson`, `languages.generate_exercises`, `languages.review_exercise`, `languages.review_writing`, `languages.generate_conversation_turn`, `languages.generate_roleplay_turn`, `languages.review_speaking`, `languages.review_errors`, `languages.track_vocabulary`, `languages.plan_review_schedule`, `languages.prepare_certification`, `languages.generate_progress_review` |
| Workflows | 9 | `languages.language_onboarding`, `languages.proficiency_assessment`, `languages.adaptive_language_lesson`, `languages.conversation_roleplay_practice`, `languages.writing_review`, `languages.error_remediation`, `languages.vocabulary_spaced_review`, `languages.certification_preparation`, `languages.progress_checkpoint` |

## 4. Core Semantics & Epistemic Boundaries

### Epistemic Separation
- `CERTIFIED`: Authorized credential/official certificate evidence. Cannot be overwritten by single performance samples.
- `ESTIMATED`: Longitudinal accumulated comparable evidence across sessions.
- `OBSERVED_PERFORMANCE`: Single-sample task result.

### Valid Varieties vs Errors
- Regional language varieties (e.g., Mexican Spanish vs Peninsular Spanish, British English vs American English) are preserved as valid alternatives and never marked as grammatical errors.

### Pronunciation Evidence
- Written transcripts cannot evaluate phoneme pronunciation. If audio evidence is absent, `pronunciation_assessed` is explicitly `False`.

### Error Patterns
- 1 occurrence is an isolated slip / insufficient evidence.
- >= 2 independent comparable occurrences form a candidate or evidenced pattern.

### Consent-Gated Longitudinal Memory
- Session-only observations remain ephemeral.
- Durable persistence of learner profile, goals, vocabulary state, and error patterns requires explicit literal `True` consent and valid shared approval chain.

## 5. Operations & Workflows

All 15 operations are low-risk internal operations (`PolicyRiskLevel.LOW`).
No operation mutates external calendars, makes payments, submits exam registrations, or alters persistent memory directly.
All 9 workflows run on the shared Workflow Engine with direct producer-to-gate validation.

## 6. Independent-audit remediation status

The first independent Phase 10.26 audit returned `FAIL` with two blockers and
five major findings. Independent re-audit V2 also returned `FAIL`, with two
remaining blockers and three remaining major findings. The V2 remediation
candidate addresses those `2 BLOCKER + 3 MAJOR` findings; independent V3 audit
is still `PENDING`.

`AT-DP-026` now passes as one connected 45-checkpoint scenario over the real
shared resolver, composer, Workflow Engine, permission gate, memory contracts,
projection, presentation, and typed trace contracts. Its 45 checkpoints now
match the frozen semantic sequence exactly, including the real shared calendar
permission boundary. Its trace inventory is derived from runtime objects before
assembly, and `WorkflowEvent.event_id` is not represented as a workflow result.

The remediation includes explicitly authorized minimal shared changes:
typed `DomainMetadata.metadata` extraction in domain composition; accumulated
workflow-output visibility at the ready-node adapter boundary; shared Domain
Trace kinds for evidence, memory proposal/binding and presentation result; and
the global `presentation_result_ids` carrier. These changes do not alter domain
scoring/ranking, workflow scheduling/ordering/readiness/status semantics, or
existing public payload shapes.

This is candidate remediation evidence only. `DP-026` remains
`REQUIRES_PHASE_INSPECTION`; candidate `AT-DP-026` is `PASS`, independent V3
audit is `PENDING`, and final closure has not been claimed.
