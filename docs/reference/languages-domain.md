# Languages Domain (`domain:languages`)

**Phase:** 10.26
**Status:** Implemented — pending independent audit
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
| Entities | 16 | language, language_variety, proficiency_record, skill_profile, language_goal, learning_plan, lesson, exercise, exercise_result, error_observation, error_pattern, vocabulary_item, grammar_topic, spaced_review_schedule, certification_target, progress_checkpoint |
| Resources | 15 | user_message, conversation, language_sample, writing_sample, audio_transcript, pronunciation_assessment, vocabulary_list, exercise_result, learning_goal, study_schedule, journal_entry, note, memory_entry, domain_result, external_source |
| Rules | 14 | LanguageLevelEvidence, SkillSeparation, LanguageVarietyValidity, ProficiencyFramework, ErrorPatternEvidence, CorrectionPriority, AdaptiveDifficulty, SpacedReview, LearningLoad, GoalAlignment, ProgressionEvidence, CertificationTemporal, CulturalContextEvidence, LanguageMemoryConsent |
| Operations | 15 | assess_sample, update_level_evidence, create_learning_plan, generate_lesson, generate_exercises, review_exercise, review_writing, generate_conversation_turn, generate_roleplay_turn, review_speaking, review_errors, track_vocabulary, plan_review_schedule, prepare_certification, generate_progress_review |
| Workflows | 9 | Language Onboarding, Proficiency Assessment, Adaptive Language Lesson, Conversation & Roleplay Practice, Writing Review, Error Remediation, Vocabulary & Spaced Review, Certification Preparation, Progress Review |

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
