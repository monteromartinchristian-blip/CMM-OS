# Phase 10.26 — Languages Domain — Complete Redesign

**Date:** 2026-08-23
**Status:** PROPOSED FROZEN DESIGN — replaces the previous Phase 10.26 design before implementation
**Canonical domain:** `domain:languages`
**Canonical namespace:** `languages.*`
**Display name:** `Idiomas`
**Canonical reasoning profile:** `LanguageLearningProfile`

---

# 1. Purpose

Phase 10.26 adds the `domain:languages` specialization to CMM OS.

The Languages Domain exists to make CMM OS capable of acting as a **real language-learning tutor and a rigorous longitudinal learning system** without becoming a separate educational application, a second cognitive engine, or an isolated assistant.

Its purpose is to support the complete language-learning loop:

- onboarding a language intentionally and with explicit persistence choices;
- representing multiple languages at the same time;
- representing preferred language varieties without treating other valid varieties as errors;
- managing multiple simultaneous goals per language;
- assessing language samples through evidence;
- separating certified proficiency, estimated proficiency, and isolated observed performance;
- separating proficiency by skill instead of hiding differences behind one global label;
- generating adaptive lessons and exercises;
- supporting natural conversation practice;
- supporting structured roleplay;
- reviewing writing;
- reviewing speaking when adequate evidence exists;
- detecting observed errors;
- promoting errors to recurrent patterns only when evidence is sufficient;
- tracking vocabulary and grammar;
- applying spaced review;
- adapting workload to goals, time, energy, and recent performance;
- preparing official certifications;
- verifying temporally changing certification information through appropriate authoritative sources;
- reviewing progression over time;
- preserving uncertainty where evidence is insufficient;
- proposing persistent learning-state updates only under the applicable memory and consent policy;
- composing with University, Oppositions, General, Concerns, and Reflection without duplicating their responsibilities;
- preserving traceability, provenance, permissions, temporal validity, and user control.

The domain is intentionally balanced between two functions:

```text
ACTIVE LANGUAGE TUTOR
+
RIGOROUS PROGRESS / EVIDENCE SYSTEM
```

Neither function should erase the other.

Canonical invariants:

```text
language learning != certification only
language tutoring != generic chat
practice != assessment
assessment != permanent level
correction != error-pattern creation
progress tracking != silent surveillance
recommendation != authorization
```

---

# 2. Why the previous 10.26 design is replaced

The historical Phase 10.26 roadmap described a smaller domain centered on:

```text
language
skill
proficiency_level
exercise
mistake
vocabulary_item
grammar_topic
study_session
exam
certification
learning_goal
```

with ten resources, six rules, nine operations, and six workflows.

That design established useful foundations, especially:

- certified level versus estimated level versus point-in-time performance;
- skill separation;
- recurrent-error detection;
- spaced review;
- workload adaptation;
- temporal verification of certifications.

However, it is not sufficient for the actual accepted product intent.

The Phase 10 requirement corpus already assigns to `DP-026`:

```text
consented onboarding
evidenced proficiency assessment
lesson workflow
versioned progression
roleplay
writing review
periodic progress review
cultural context
pedagogical adaptation
communication-style separation
```

The historical design also leaves several semantic problems unresolved:

1. `proficiency_level` conflates evidence, inference, and certification;
2. `mistake` does not distinguish a point observation from a recurrent pattern;
3. `study_session` collides conceptually with University and Oppositions;
4. `exam` and `certification` do not adequately represent a sustained certification target;
5. there is no explicit model for language variety;
6. there is no explicit proficiency framework;
7. there is no explicit assessment-evidence entity;
8. there is no active lesson operation;
9. conversation practice is planned but not modeled as an interactive domain behavior;
10. roleplay is absent from the canonical catalog despite being required by the source corpus;
11. writing review is a workflow without a sufficiently explicit operation contract;
12. progression is under-modeled;
13. memory consent is mentioned externally but not made a first-class domain rule;
14. cultural-context evidence is not represented as a rule;
15. the design does not fully exploit the hardened Domain Intelligence infrastructure implemented by 10.19–10.25.

The redesigned domain therefore changes the center of gravity from:

```text
TRACK LANGUAGE STUDY
```

to:

```text
UNDERSTAND THE LANGUAGE + GOALS
↓
ASSESS EVIDENCE
↓
TEACH / PRACTICE / REVIEW
↓
ADAPT DIFFICULTY AND PRIORITIES
↓
TRACK PROGRESSION WITH CONSENT
↓
PREPARE REAL-WORLD OR CERTIFICATION GOALS
```

The previous 10.26 catalog is superseded once this design is frozen.

---

# 3. Design objective

The desired experience is:

> CMM OS should be able to accompany language learning over months or years as a patient, adaptive, evidence-aware tutor. It should converse, teach, correct, create practice, detect genuine recurrent weaknesses, prepare certifications, and show progress without inventing levels, overcorrecting natural conversation, silently persisting every mistake, or confusing exam performance with general proficiency.

The system must support both:

```text
"Let's practice English for twenty minutes."
```

and:

```text
"Build a six-month plan to reach C1 Catalan for an official certification."
```

without treating one as a degraded version of the other.

---

# 4. Architectural decision

Implement exactly one specialized Domain Pack:

```text
cmm/domains/languages/
```

using the hardened specialized-domain package boundary:

```text
__init__.py
bootstrap.py
catalog.py
definition.py
integration.py
memory.py
operations.py
permissions.py
presentation.py
profile.py
resources.py
rules.py
trace.py
workflows.py
```

No Languages-specific:

```text
planner
agent runtime
memory store
knowledge store
knowledge graph
workflow engine
permission engine
temporal engine
model gateway
calendar engine
conversation runtime
assessment database
spaced-repetition engine
```

may be introduced.

The implementation must reuse shared Phase 10 contracts for:

- `DomainDefinition`;
- domain registration;
- discovery and loading;
- profile registration and resolution;
- rule registration, selection, and execution;
- operation contracts and registry;
- workflow contracts, registry, resolution, and execution;
- permission contracts, registry, resolution, and evaluation;
- cross-domain composition;
- domain resources;
- presentation contracts and validation;
- trace assembly and validation;
- memory views and memory-update proposals;
- validation;
- rollback-safe bootstrap.

It must reuse earlier layers for:

- Knowledge Model / Store / Graph;
- Cognitive Layer;
- Agent Runtime;
- Planner;
- workflow runtime;
- operation execution;
- temporal reasoning;
- validation;
- shared memory;
- approval mechanisms.

`catalog.py` is the single canonical source of catalog membership.

---

# 5. Domain identity

Canonical identifier:

```text
domain:languages
```

Canonical slug:

```text
languages
```

Canonical operation namespace:

```text
languages.*
```

Display name:

```text
Idiomas
```

Canonical reasoning profile:

```text
LanguageLearningProfile
```

No alternative namespace such as:

```text
language.*
learning.*
tutor.*
linguistics.*
```

is canonical.

---

# 6. Domain role

Languages is the **language-learning and language-practice specialization**.

It becomes a strong candidate when the user's objective is principally about:

- learning a language;
- improving language competence;
- practicing one or more skills;
- receiving corrections;
- receiving adaptive instruction;
- understanding grammar or vocabulary for language-learning purposes;
- practicing a conversation;
- running a roleplay;
- reviewing writing;
- reviewing speaking;
- understanding recurring errors;
- maintaining vocabulary;
- preparing a language certification;
- estimating current proficiency;
- reviewing language-learning progress.

Typical requests:

```text
"Let's practice English."
"Correct this writing."
"Give me exercises on the present perfect."
"I want to reach C1 Catalan."
"How am I progressing?"
"Prepare me for the oral exam."
"Let's roleplay a job interview in English."
"Why do I keep making this mistake?"
"What should I review this week?"
```

Keyword matching alone is not sufficient.

The resolver must consider:

- the user's actual objective;
- whether the language is the object of learning or merely the medium;
- active University/Oppositions goals;
- current session context;
- requested operation;
- whether another domain owns the primary objective.

---

# 7. What Languages is not

Languages is not:

- a generic education domain;
- a replacement for General;
- a university planning domain;
- an opposition-planning domain;
- a generic translation service;
- a cultural-stereotype engine;
- a linguistic-diagnosis system;
- a personality or identity profiler;
- a fixed curriculum application;
- a mandatory daily-study system;
- an external calendar writer;
- an exam-registration service;
- a payment service;
- an autonomous external communicator;
- a private memory database;
- a separate spaced-repetition platform;
- a separate conversational agent;
- a communication-persona engine.

Translation may be used as:

- an exercise;
- a contrastive explanation;
- a learning aid;

but translation does not define the domain.

---

# 8. Separation from communication personality

Languages defines **pedagogical semantics**, not the final assistant persona.

The domain may determine:

- what to teach;
- what to practice;
- what to assess;
- how difficult an activity should be;
- how much correction is pedagogically appropriate;
- what constitutes sufficient evidence for a level update;
- what language variety is preferred;
- which learning objective has priority;
- whether the current activity is teaching, practice, assessment, review, certification preparation, or immersion;
- whether feedback should be immediate or delayed;
- what uncertainty must remain visible.

Languages must not hard-code:

- global warmth;
- global formality;
- fixed sentence length;
- emoji behavior;
- a fictional tutor persona;
- general use of the user's name;
- global response verbosity;
- provider-specific style.

Those are presentation and, later, Phase 11 Communication Profile concerns.

Canonical invariant:

```text
pedagogical adaptation != communication persona
```

---

# 9. Foundational design principles

## 9.1 Multi-language by design

The system must support several languages concurrently.

Each language maintains independent state for:

```text
goals
preferred variety
certifications
estimated proficiency
certified proficiency
skill evidence
practice history
vocabulary
grammar
observed errors
error patterns
review state
learning plan
progression
```

There is no canonical:

```text
global_language_level_of_user
```

across different languages.

---

## 9.2 Multiple concurrent goals per language

A language may have several active goals.

Example:

```text
English
├── improve conversation fluency
├── improve listening to real content
└── reach C1

Catalan
├── obtain C1 certification
└── improve formal writing
```

The system must preserve:

```text
goal coexistence
goal priority
goal horizon
goal-specific skills
goal-specific evidence
```

without forcing one objective to erase another.

---

## 9.3 Preferred variety is not exclusive correctness

The system may represent:

```text
language = English
preferred_variety = American English
```

and use that preference to guide:

- vocabulary;
- pronunciation targets;
- spelling;
- examples;
- production guidance;
- register;
- learning materials.

But:

```text
preferred variety != only valid variety
```

A valid form from another recognized variety must not be marked wrong solely because it differs from the preferred variety.

Example:

```text
preferred: color
observed: colour
result: valid alternative, not error
```

The domain should distinguish:

```text
preferred_variety
observed_variety
assessment_standard
```

when relevant.

---

## 9.4 Proficiency is epistemically typed

The central proficiency invariant is:

```text
certified proficiency
!=
estimated proficiency
!=
observed performance
```

A certificate is an externally grounded achievement under a specified framework and date.

An estimated level is an inference supported by a body of evidence.

Observed performance is what happened in a specific sample or activity.

They may align.

They may diverge.

Neither divergence nor alignment is automatically a contradiction.

---

## 9.5 Proficiency is skill-specific

The minimum canonical skill dimensions are:

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

A global proficiency estimate may exist only as a derived summary when justified.

It must never erase skill-specific evidence.

Example:

```text
certified_level = B1
estimated_overall_level = B2
listening = B2
reading = B2+
writing = B1+
speaking = B1
```

is not inherently contradictory.

---

## 9.6 One error is not a pattern

Canonical invariant:

```text
observed_error != error_pattern
```

A point error may result from:

- a lapse;
- fatigue;
- misunderstanding the task;
- accidental production;
- unstable knowledge;
- recurrent weakness.

Only accumulated evidence may justify promotion to a recurrent pattern.

---

## 9.7 Practice does not silently change stable proficiency

A good or bad session may generate evidence.

It must not directly rewrite stable proficiency.

Canonical invariant:

```text
practice result != stable proficiency
```

---

## 9.8 Exam readiness is not general proficiency

The system must distinguish:

```text
certification readiness
!=
general language proficiency
```

A user may have strong language ability and poor exam-format preparation.

A user may also learn exam strategies that improve exam performance without equivalent improvement in broad proficiency.

---

## 9.9 Communicative usefulness takes priority over correction density

During fluency-oriented practice, the system should not interrupt every error.

Correction should be prioritized by:

1. errors that impede comprehension;
2. recurrent errors;
3. errors relevant to the current goal;
4. certification-critical errors;
5. high-value naturalness or register issues;
6. low-value stylistic refinements.

The tutor must remain useful as a conversational partner.

---

## 9.10 Progress requires comparable evidence

Canonical invariant:

```text
better score once != demonstrated progression
```

Progress judgments should distinguish:

```text
short_term_improvement
stable_improvement
plateau
possible_regression
insufficient_evidence
```

and should compare evidence that is meaningfully comparable.

---

## 9.11 Learning should adapt

Difficulty and workload should be adapted using:

- current goal;
- estimated proficiency;
- skill profile;
- recent performance;
- time available;
- energy;
- deadline;
- other active goals;
- review burden;
- certification target;
- user preference.

Adaptation must not become instability.

A single poor session should not collapse the learning plan.

---

## 9.12 Longitudinal tracking requires permission

Session-level pedagogical state may be used during the active session.

Long-term learning state is a separate concern.

Canonical invariant:

```text
session observation != persistent memory
```

Persistent progress tracking must follow shared memory policy and the consent requirements assigned to Languages.

---

# 10. Language-learning state model

Conceptually:

```text
Language
↓
Preferred variety
↓
Goals
↓
Frameworks / certification targets
↓
Current proficiency records
    ├── certified
    ├── estimated
    └── observed performance
↓
Evidence by skill
↓
Learning plan
↓
Practice / lessons / exercises
↓
Observed errors
↓
Evidence-backed error patterns
↓
Vocabulary / grammar / review items
↓
Progress reviews
↓
Proposed longitudinal state updates
```

The state is versioned through shared knowledge and memory mechanisms.

No domain-local state engine is created.

---

# 11. Skill model

Canonical skill dimensions:

```text
LISTENING
SPEAKING
READING
WRITING
GRAMMAR
VOCABULARY
PRONUNCIATION
INTERACTION
```

These dimensions are related but non-interchangeable.

Examples:

```text
strong reading != strong speaking
grammar exercise score != interaction ability
transcript quality != pronunciation evidence
vocabulary size != communicative competence
```

`INTERACTION` exists because conversational competence includes:

- turn-taking;
- responding appropriately;
- negotiation of meaning;
- clarification;
- conversational repair;
- real-time adaptation;

which is not identical to monologic speaking.

---

# 12. Proficiency model

A `proficiency_record` must identify at minimum:

```text
language
kind
framework
level_or_score
skill_scope
evidence_refs
confidence
observed_at / valid_at
source
```

Canonical kinds:

```text
CERTIFIED
ESTIMATED
OBSERVED_PERFORMANCE
```

## 12.1 Certified proficiency

Requires evidence equivalent to an authoritative certificate or recognized official result.

It must preserve:

- certification;
- framework;
- date;
- result;
- source;
- temporal status where relevant.

An estimate may not overwrite a certificate.

---

## 12.2 Estimated proficiency

An inference based on accumulated evidence.

It should preserve:

- evidence count and diversity;
- covered skills;
- missing skills;
- confidence;
- range when exact classification is not justified;
- date.

Example:

```text
writing evidence compatible with B1+/B2
speaking insufficiently evidenced
```

is preferable to inventing a precise global B2.

---

## 12.3 Observed performance

Bound to a concrete sample, task, or session.

It may be expressed as:

- framework-compatible range;
- task score;
- rubric outcome;
- qualitative performance.

It does not automatically become the user's stable level.

---

# 13. Canonical entity catalog — exactly 16

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

## 13.1 `language`

The language being learned, maintained, practiced, or assessed.

It is the primary partition for longitudinal learning state.

---

## 13.2 `language_variety`

A recognized variety, regional standard, or target usage preference.

Examples:

```text
American English
British English
Spain Spanish
Central Catalan
```

A variety is not automatically a separate language.

---

## 13.3 `skill_dimension`

A canonical language skill dimension.

The initial canonical dimensions are those defined in section 11.

---

## 13.4 `language_goal`

A language-specific objective.

Possible examples:

```text
reach CEFR C1
maintain conversation fluency
improve listening
prepare job interview
write formal Catalan
travel competence
pass certification
```

Several goals may be active concurrently.

---

## 13.5 `proficiency_framework`

A framework or scoring system used to interpret proficiency.

Examples:

```text
CEFR / MCER
IELTS
TOEFL
Cambridge English Scale
certification-specific rubric
```

The framework must be explicit whenever a level or score depends on it.

---

## 13.6 `proficiency_record`

An epistemically typed record representing:

```text
CERTIFIED
ESTIMATED
OBSERVED_PERFORMANCE
```

at global or skill-specific scope.

---

## 13.7 `assessment_evidence`

Evidence used to support a proficiency or progression judgment.

Examples:

- writing sample;
- speaking sample;
- conversation result;
- listening task;
- reading task;
- mock exam result;
- official certificate.

---

## 13.8 `practice_session`

A language-specific practice period.

This replaces the old generic `study_session` concept inside Languages to avoid semantic overlap with University and Oppositions.

A practice session may include:

- lesson;
- conversation;
- roleplay;
- exercise block;
- writing;
- certification practice;
- mixed practice.

---

## 13.9 `exercise`

A pedagogical unit.

Examples:

```text
grammar drill
vocabulary recall
reading task
listening task
writing prompt
transformation task
interaction prompt
```

---

## 13.10 `observed_error`

A point error observed in a concrete sample or activity.

It must preserve context and evidence.

It does not imply recurrence.

---

## 13.11 `error_pattern`

An evidence-backed recurrent error or weakness.

Possible lifecycle:

```text
candidate
evidenced
active
improving
resolved
```

The lifecycle may be represented as state attributes rather than new entities.

---

## 13.12 `vocabulary_item`

A lexical learning unit.

It may represent:

```text
word
expression
collocation
chunk
phrasal verb
idiom
```

It should not be reduced to a mandatory one-to-one translation pair.

---

## 13.13 `grammar_topic`

A teachable or reviewable grammatical topic.

Examples:

```text
present perfect
conditionals
subjunctive
pronoms febles
article use
```

---

## 13.14 `certification_target`

A sustained target related to an official or recognized certification.

It may include:

- certification identifier;
- target level;
- planned date;
- official requirements;
- current readiness;
- skill gaps.

---

## 13.15 `review_item`

An item scheduled for pedagogical review.

It may reference:

- vocabulary;
- grammar;
- supported error pattern;
- other reviewable material.

Its state may include:

```text
new
learning
review
consolidated
needs_reinforcement
```

`review_item` is the entity.

`review_state` is not a separate canonical entity.

---

## 13.16 `learning_plan`

A language-specific adaptive plan.

It may include:

- active goals;
- priorities;
- target skills;
- workload;
- learning sequence;
- practice balance;
- review burden;
- certification milestones;
- next focus.

---

# 14. Canonical resource catalog — exactly 15

```text
user_message
conversation
writing_sample
audio_transcript
exercise_result
assessment_result
language_plan
lesson_material
vocabulary_list
language_reference
certification_guide
official_certification_source
calendar_event
memory_entry
domain_result
```

## 14.1 `user_message`

User-provided current-turn input.

---

## 14.2 `conversation`

Conversation context used for language practice or assessment.

---

## 14.3 `writing_sample`

User-produced written language.

---

## 14.4 `audio_transcript`

Transcript derived from oral language.

Important invariant:

```text
transcript != pronunciation evidence
```

unless the relevant pronunciation information is separately represented.

---

## 14.5 `exercise_result`

Result of a concrete exercise.

---

## 14.6 `assessment_result`

Structured result created specifically for proficiency or skill assessment.

---

## 14.7 `language_plan`

Resource representation of the current language-learning plan.

The canonical entity remains `learning_plan`.

---

## 14.8 `lesson_material`

Material used or produced for an adaptive lesson.

---

## 14.9 `vocabulary_list`

Structured vocabulary material.

---

## 14.10 `language_reference`

Reference material such as:

- grammar references;
- dictionaries;
- authoritative usage guidance;
- corpora-derived evidence;
- pronunciation references.

---

## 14.11 `certification_guide`

Preparation-oriented information about a certification.

It is not automatically authoritative for current official requirements.

---

## 14.12 `official_certification_source`

Authoritative or official source for temporally sensitive certification facts such as:

- dates;
- fees;
- accepted levels;
- registration rules;
- exam structure;
- current requirements.

---

## 14.13 `calendar_event`

Authorized shared calendar context.

Languages may use it for planning when permitted.

It must not mutate calendar state directly.

---

## 14.14 `memory_entry`

Authorized memory projection.

Languages does not receive unrestricted memory-store access.

---

## 14.15 `domain_result`

Authorized projection from another domain.

This is the primary cross-domain bridge for specialized results.

---

# 15. Canonical rule catalog — exactly 14

```text
LanguageLevelEvidenceRule
SkillSeparationRule
LanguageVarietyValidityRule
ProficiencyFrameworkRule
ErrorPatternEvidenceRule
CorrectionPriorityRule
AdaptiveDifficultyRule
SpacedReviewRule
LearningLoadRule
GoalAlignmentRule
ProgressionEvidenceRule
CertificationTemporalRule
CulturalContextEvidenceRule
LanguageMemoryConsentRule
```

---

# 16. `LanguageLevelEvidenceRule`

Purpose:

Preserve the distinction between certified proficiency, estimated proficiency, and isolated performance.

Required behavior:

```text
certificate -> CERTIFIED
evidence-based inference -> ESTIMATED
single task/session -> OBSERVED_PERFORMANCE
```

The rule must prevent:

- single-sample promotion to stable proficiency;
- estimate promotion to certificate;
- certificate rewriting from informal evidence;
- confidence inflation when skill coverage is incomplete.

The result should be allowed to say:

```text
insufficient evidence
```

---

# 17. `SkillSeparationRule`

Purpose:

Prevent unrelated skills from collapsing into one score.

Required distinctions:

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

The rule must prevent:

```text
excellent reading -> inferred excellent speaking
good grammar drills -> inferred conversational fluency
good transcript -> inferred pronunciation quality
```

without supporting evidence.

---

# 18. `LanguageVarietyValidityRule`

Purpose:

Respect recognized language varieties while still supporting a preferred learning target.

Canonical invariant:

```text
different valid variety != error
```

The rule may classify an item as:

```text
preferred
valid_alternative
register_difference
regional_difference
nonstandard
incorrect
uncertain
```

when evidence supports that distinction.

It must not treat the user's preferred variety as an exclusive truth source.

---

# 19. `ProficiencyFrameworkRule`

Purpose:

Prevent silent equivalence between incompatible or merely approximate scales.

Examples:

```text
CEFR B2
IELTS 6.5
TOEFL score
Cambridge scale score
```

Mappings may be used only when their provenance and approximate nature are preserved.

Canonical invariant:

```text
mapping != identity
```

---

# 20. `ErrorPatternEvidenceRule`

Purpose:

Promote point errors to recurrent patterns only when sufficient evidence exists.

The rule should consider:

- recurrence;
- independent samples;
- context comparability;
- time;
- task type;
- possible lapses;
- variety differences;
- correction history.

A single observation cannot establish a recurrent pattern.

---

# 21. `CorrectionPriorityRule`

Purpose:

Control correction density and pedagogical priority.

Priority order:

```text
comprehension-blocking
>
recurrent
>
goal-critical
>
certification-critical
>
high-value naturalness / register
>
minor stylistic refinement
```

The exact output may be structured as categories/ranks rather than numerical values.

The rule must support delayed feedback during fluency practice.

---

# 22. `AdaptiveDifficultyRule`

Purpose:

Adjust lesson or practice challenge without destabilizing long-term state.

Conceptual behavior:

```text
too_easy -> increase challenge
appropriate -> consolidate + progress
too_hard -> reduce complexity / increase scaffolding
```

The rule must preserve:

```text
temporary difficulty != proficiency regression
```

---

# 23. `SpacedReviewRule`

Purpose:

Prioritize temporally distributed review.

Inputs may include:

- last review;
- recall performance;
- item importance;
- goal relevance;
- recurrence;
- active certification;
- user workload.

The domain must not implement a second scheduler engine.

The rule computes review semantics for the shared workflow/runtime.

---

# 24. `LearningLoadRule`

Purpose:

Adapt learning burden to real constraints.

Inputs may include:

```text
available time
energy
priority
other goals
deadline
recent workload
review backlog
difficulty
```

Languages may recommend load.

It does not own the user's global agenda.

---

# 25. `GoalAlignmentRule`

Purpose:

Ensure activities serve one or more active goals.

Examples:

```text
C1 certification
→ formal writing + exam tasks

travel
→ interaction + functional vocabulary

conversation fluency
→ speaking + interaction + listening
```

Certification must not silently dominate unrelated language goals.

---

# 26. `ProgressionEvidenceRule`

Purpose:

Classify progression from comparable evidence.

Possible outcomes:

```text
short_term_improvement
stable_improvement
stable
plateau
possible_regression
insufficient_evidence
```

The rule must preserve:

- prior version;
- current evidence;
- comparability;
- confidence;
- missing evidence.

---

# 27. `CertificationTemporalRule`

Purpose:

Protect against stale certification information.

When an outcome depends on current facts such as:

- dates;
- fees;
- accepted certificates;
- exam format;
- registration;
- official recognition;
- scoring;
- required documentation;

the rule must prefer current authoritative sources.

Canonical precedence:

```text
current official source
>
current authoritative secondary source
>
historical memory
>
unverified guide
```

Languages may request shared external verification.

It must not introduce a private web-search engine.

---

# 28. `CulturalContextEvidenceRule`

Purpose:

Support pragmatic and cultural teaching without turning cultural generalizations into universal claims.

The rule may support:

- register;
- politeness conventions;
- situational usage;
- regional context;
- pragmatic expectations.

It must preserve:

```text
common tendency != universal rule
cultural context != stereotype
```

---

# 29. `LanguageMemoryConsentRule`

Purpose:

Bind longitudinal tracking to shared memory policy and user permission.

The rule must distinguish:

```text
session observation
candidate longitudinal state
persistent longitudinal state
```

No point observation is silently persisted merely because it may be pedagogically useful later.

Persistent state may include, when authorized:

- estimated proficiency;
- skill profile;
- learning goals;
- learning plan;
- supported error patterns;
- vocabulary review state;
- grammar review state;
- certification target;
- progress history.

---

# 30. Canonical reasoning profile

Canonical profile:

```text
LanguageLearningProfile
```

Exactly one Languages-specific reasoning profile is required.

The profile expresses pedagogical reasoning behavior.

It is not a communication persona.

Core priorities:

```text
communicative usefulness > correction density
evidence > intuition about level
adaptation > fixed curriculum
goal relevance > generic completeness
progress over time > isolated score
```

---

# 31. Pedagogical modes

`LanguageLearningProfile` supports these modes:

```text
teach
practice
assess
review
certification
immersion
```

These are modes of one profile, not separate Domain Profiles.

---

## 31.1 `teach`

Behavior:

- explain;
- scaffold;
- demonstrate;
- generate examples;
- check understanding;
- guide practice.

---

## 31.2 `practice`

Behavior:

- prioritize active use;
- preserve flow;
- correct selectively;
- provide structured feedback after useful interaction units.

---

## 31.3 `assess`

Behavior:

- reduce coaching that would contaminate evidence;
- observe;
- classify evidence;
- preserve uncertainty;
- avoid helping the user into an artificially stronger result.

---

## 31.4 `review`

Behavior:

- retrieve prior authorized state;
- compare evidence;
- reinforce weak material;
- identify progression and unresolved gaps.

---

## 31.5 `certification`

Behavior:

- use certification-specific criteria;
- distinguish exam readiness from broad proficiency;
- preserve current official requirements;
- practice relevant task formats.

---

## 31.6 `immersion`

Behavior:

- maximize appropriate target-language use;
- reduce fallback-language dependence;
- preserve comprehensibility;
- allow user-controlled fallback when needed.

---

# 32. Target-language ratio

The profile may resolve pedagogical parameters equivalent to:

```text
target_language_ratio
explanation_language
fallback_language
correction_language
```

These are not new entities.

Example conceptual progression:

```text
A2
→ substantial fallback-language explanation

B1
→ mixed explanation and target language

B2/C1
→ target language increasingly dominant
```

This must remain adaptable by user preference and task.

---

# 33. Correction timing policy

Canonical behavior:

```text
during fluency practice:
    correct high-value errors selectively

after a practice segment:
    provide structured feedback

during explicit exercise:
    immediate correction is allowed

during assessment:
    avoid coaching that contaminates evidence
```

The system should not interrupt natural practice for every low-value error.

---

# 34. Canonical operation catalog — exactly 15

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

All operations must use shared operation contracts.

They must not perform hidden external actions.

---

# 35. `languages.assess_sample`

Purpose:

Assess a concrete language sample.

Possible inputs:

```text
writing_sample
audio_transcript
conversation
exercise_result
assessment_result
```

Possible outputs:

```text
observed performance
skill-specific evidence
strengths
observed errors
uncertainties
possible framework-compatible range
missing evidence
```

It must not directly persist a stable level.

---

# 36. `languages.update_level_evidence`

Purpose:

Integrate new validated evidence into the proficiency model.

Conceptual flow:

```text
existing proficiency evidence
+
new assessment evidence
↓
validate comparability / scope
↓
propose updated estimated proficiency
```

It may produce:

```text
no_change
increase_supported
decrease_signal
range_narrowed
confidence_changed
insufficient_evidence
```

It must not alter certified proficiency.

Persistence remains governed by memory policy.

---

# 37. `languages.create_learning_plan`

Purpose:

Create or revise an adaptive language plan.

Inputs may include:

- active goals;
- skill profile;
- time;
- energy;
- certification target;
- review burden;
- recent progression;
- user preferences.

Output is a proposal/plan object.

It does not write calendar events.

---

# 38. `languages.generate_lesson`

Purpose:

Generate an adaptive pedagogical lesson.

Canonical structure may include:

```text
objective
warm-up
input / explanation
guided practice
active production
feedback
review
next step
```

The structure may adapt to the mode and task.

This is content/semantic generation.

It does not introduce a new lesson runtime.

---

# 39. `languages.generate_exercises`

Purpose:

Generate target-specific exercises.

Possible categories:

```text
grammar
vocabulary
reading
listening
writing
transformation
interaction
certification task
```

Exercises should be aligned with:

- language;
- variety;
- skill;
- goal;
- difficulty;
- review need;
- supported error pattern.

---

# 40. `languages.review_exercise`

Purpose:

Review a concrete exercise result.

Output may include:

```text
correct / incorrect / partial
explanation
observed error
importance
reinforcement suggestion
```

A failed item does not automatically create an `error_pattern`.

---

# 41. `languages.review_writing`

Purpose:

Provide structured writing feedback.

Canonical dimensions may include:

```text
task achievement
clarity
coherence
grammar
vocabulary
register
naturalness
corrections
alternative formulations
skill evidence
```

When certification mode is active, certification-specific rubric dimensions may be added.

Canonical invariant:

```text
exam-specific writing score != general proficiency
```

---

# 42. `languages.generate_conversation_turn`

Purpose:

Generate one pedagogically appropriate turn within conversation practice.

Possible practice modes:

```text
free
guided
topic_focused
skill_focused
exam_style
```

The operation is turn-level deliberately.

The shared Workflow Engine owns the multi-turn process.

---

# 43. `languages.generate_roleplay_turn`

Purpose:

Generate one turn inside a structured roleplay.

Possible scenarios:

```text
hotel
airport
restaurant
job interview
doctor
university
formal meeting
oral exam
travel problem
```

The roleplay must preserve scenario constraints and learning goals.

It must not impersonate a real external person or perform an external action.

---

# 44. `languages.review_speaking`

Purpose:

Review oral production when adequate evidence exists.

Dimensions may include:

```text
fluency
grammar
vocabulary
interaction
comprehensibility
register
pronunciation
```

Pronunciation must only be assessed when pronunciation-relevant evidence exists.

Canonical invariant:

```text
audio transcript alone != pronunciation assessment
```

---

# 45. `languages.review_errors`

Purpose:

Analyze observed errors across evidence.

Capabilities:

- classify;
- compare;
- identify recurrence;
- propose candidate pattern;
- rank pedagogical priority;
- recommend targeted practice.

Pattern promotion remains governed by `ErrorPatternEvidenceRule`.

---

# 46. `languages.track_vocabulary`

Purpose:

Manage authorized vocabulary learning state.

Possible states:

```text
new
learning
review
consolidated
needs_reinforcement
```

It may operate on words, expressions, collocations, chunks, phrasal verbs, and idioms.

Persistence is consent-gated.

---

# 47. `languages.plan_review_schedule`

Purpose:

Determine what should be reviewed and when.

The name is intentionally:

```text
plan_review_schedule
```

rather than:

```text
schedule_review
```

to preserve:

```text
pedagogical schedule proposal != calendar mutation
```

The operation may generate a review plan.

Any actual calendar mutation must go through shared authorized operations.

---

# 48. `languages.prepare_certification`

Purpose:

Prepare for a language certification.

Capabilities may include:

- identify certification target;
- verify current requirements;
- map required skills;
- compare current evidence;
- identify gaps;
- generate preparation plan;
- generate mock tasks;
- interpret performance;
- estimate readiness;
- adapt the plan.

No registration, payment, or external submission occurs directly.

---

# 49. `languages.generate_progress_review`

Purpose:

Generate a longitudinal progress review.

Possible output:

```text
period
evidence considered
skill evolution
goal progress
strengths
supported difficulties
vocabulary / grammar state
review burden
certification readiness
next focus
confidence
evidence quality
```

It is not restricted to weekly cadence.

---

# 50. Canonical workflow catalog — exactly 9

```text
Language Onboarding
Proficiency Assessment
Adaptive Language Lesson
Conversation & Roleplay Practice
Writing Review
Error Remediation
Vocabulary & Spaced Review
Certification Preparation
Progress Review
```

The canonical workflow ID for Progress Review is:

```text
languages.progress_checkpoint
```

This preserves the workflow identifier already reserved by the Phase 10 preflight.

---

# 51. Workflow — Language Onboarding

Purpose:

Start managed learning for one language.

Conceptual flow:

```text
select language
↓
resolve preferred variety if desired
↓
collect active goals
↓
collect relevant prior experience
↓
record existing certificates as evidence if provided
↓
identify priority skills
↓
resolve desired workload / constraints
↓
resolve longitudinal tracking consent
↓
propose initial assessment
↓
create initial learning-state proposal
```

The workflow must not invent a level from self-description alone.

---

# 52. Workflow — Proficiency Assessment

Purpose:

Build an evidence-backed current proficiency view.

Conceptual flow:

```text
select framework / target
↓
collect appropriate evidence
↓
assess by skill
↓
classify observed performance
↓
identify missing skills
↓
estimate proficiency only where justified
↓
preserve uncertainty
↓
propose level evidence update
```

Valid outcome:

```text
speaking = insufficient_evidence
```

---

# 53. Workflow — Adaptive Language Lesson

Purpose:

Run a structured learning lesson through shared workflow execution.

Conceptual flow:

```text
load active goals + relevant authorized evidence
↓
select focus
↓
generate lesson
↓
guided practice
↓
active production
↓
review exercises
↓
collect observations
↓
adapt difficulty / next focus
↓
propose session result
```

A single lesson must not directly redefine stable proficiency.

---

# 54. Workflow — Conversation & Roleplay Practice

Purpose:

Support interactive language use.

Conceptual flow:

```text
select objective / scenario
↓
resolve target-language ratio
↓
generate turn
↓
user responds
↓
generate next turn
↓
repeat through shared workflow state
↓
provide selective correction
↓
review speaking / interaction when justified
↓
review observed errors
↓
produce practice summary
```

Conversation and roleplay remain separate operations because they have different turn semantics, but they share one workflow family.

---

# 55. Workflow — Writing Review

Purpose:

Review user writing as a full pedagogical process.

Conceptual flow:

```text
receive task + writing sample
↓
resolve objective / rubric
↓
review content and structure
↓
review grammar / vocabulary / register
↓
identify corrections
↓
explain high-value findings
↓
provide valid alternatives
↓
produce skill evidence
↓
recommend focused practice
```

---

# 56. Workflow — Error Remediation

Purpose:

Turn evidence-backed recurrent weakness into targeted improvement.

Conceptual flow:

```text
collect observed errors
↓
evaluate recurrence
↓
create / update candidate pattern
↓
prioritize pattern
↓
explain relevant cause or distinction
↓
generate targeted practice
↓
review new performance
↓
confirm / weaken / resolve pattern
```

No error pattern may exist solely because the workflow wants a remediation target.

---

# 57. Workflow — Vocabulary & Spaced Review

Purpose:

Run active review over vocabulary and other reviewable language material.

Conceptual flow:

```text
select due review items
↓
prioritize by goal + recall + importance
↓
active recall / contextual use
↓
review result
↓
update proposed review state
↓
plan next review
```

Grammar or supported error patterns may participate where appropriate.

---

# 58. Workflow — Certification Preparation

Purpose:

Maintain a certification-preparation loop.

Conceptual flow:

```text
identify certification
↓
verify current official requirements when needed
↓
map required skills
↓
compare current evidence
↓
identify gaps
↓
create / adapt plan
↓
generate certification tasks
↓
review performance
↓
estimate readiness
↓
update priorities
```

Certification readiness remains separate from general proficiency.

---

# 59. Workflow — Progress Review

Canonical workflow ID:

```text
languages.progress_checkpoint
```

Display name:

```text
Progress Review
```

Purpose:

Review versioned learning progression.

Conceptual flow:

```text
collect comparable period evidence
↓
review each skill
↓
review active goals
↓
review supported error patterns
↓
review vocabulary / grammar state
↓
review workload
↓
classify progression / plateau / uncertainty
↓
recommend next focus
↓
propose plan updates
```

Possible invocation contexts:

```text
weekly
monthly
on_demand
after_learning_block
before_certification
after_certification
```

No additional workflow is required for each cadence.

---

# 60. Permissions model

Languages is a low-risk pedagogical domain by default.

## 60.1 Low-risk internal operations

Normally permitted under standard domain policy:

```text
assess_sample
generate_lesson
generate_exercises
review_exercise
review_writing
generate_conversation_turn
generate_roleplay_turn
review_speaking
review_errors
create_learning_plan
prepare_certification
generate_progress_review
plan_review_schedule
```

provided they remain internal and do not mutate protected external state.

---

## 60.2 Consent-gated longitudinal state

Persistence of longitudinal language-learning state is governed by shared memory policy and consent.

Examples:

```text
estimated proficiency
skill profile
recurrent error patterns
vocabulary tracking
grammar review state
learning goals
learning plan
progress history
certification target
```

Session use does not imply permanent storage.

---

## 60.3 Shared approval for external actions

Languages may propose but must not directly execute:

```text
calendar write
email send
message send
exam registration
application submission
purchase
payment
external publishing
contacting academy / teacher / certification body
```

Any such action must use the shared operation and permission/approval path.

---

## 60.4 Prohibited direct behavior

Languages must not:

- bypass shared permissions;
- authorize itself;
- silently persist long-term learning state;
- write external calendars directly;
- send communications;
- register for exams;
- spend money;
- broaden cross-domain access because it is pedagogically convenient.

---

# 61. Memory model

Languages needs useful longitudinal memory without turning every interaction into permanent tracking.

The design therefore separates four levels.

---

## 61.1 Ephemeral session state

Examples:

```text
answer given two turns ago
current exercise difficulty
error made in the current roleplay
temporary vocabulary used in the current conversation
current correction context
```

This may be used to adapt the active session.

It is not automatically persisted.

---

## 61.2 Candidate observation

Example:

```text
"Since/for was confused twice in this writing sample."
```

This may be represented as assessment evidence or observation.

It does not yet mean:

```text
"User has a recurrent since/for weakness."
```

---

## 61.3 Consented pedagogical longitudinal state

Examples:

```text
estimated proficiency
skill-specific profile
active goals
learning plan
supported error patterns
vocabulary review state
grammar review state
certification target
progress history
```

These may be proposed for persistence when the applicable shared policy permits it.

---

## 61.4 Purpose-minimized cross-domain state

Only the minimal information needed by another domain should be projected.

Examples potentially useful to Oppositions:

```text
required certification target
certification status
estimated readiness
blocking language gap
recommended workload
```

Examples normally unnecessary to export:

```text
full vocabulary history
complete list of observed errors
all conversation transcripts
detailed writing corrections
full Languages memory
```

Canonical invariant:

```text
cross-domain relevance != permission to share everything
```

---

# 62. Memory promotion flow

Observed error:

```text
observed_error
↓
accumulated evidence
↓
candidate pattern
↓
ErrorPatternEvidenceRule
↓
memory update proposal
↓
permission / consent
↓
persistent error_pattern
```

Not:

```text
observed_error -> permanent error_pattern
```

Estimated level:

```text
assessment evidence
↓
proficiency inference
↓
confidence + gaps
↓
proposed proficiency update
↓
permission / consent
↓
persistent estimated state
```

---

# 63. Correction, forgetting, and invalidation

The domain must support semantic requests equivalent to:

```text
"That is no longer a recurring problem."
"Do not retain my pronunciation errors."
"Forget my French progress."
"My certificate is recorded incorrectly."
```

Languages does not implement the memory backend.

It must create or validate the appropriate shared correction / invalidation / forgetting proposal.

---

# 64. Presentation policy

Languages determines **pedagogically relevant presentation semantics**.

It does not own global wording personality.

Possible presentation requirements include:

```text
current objective
activity / task
user production
correction / feedback
explanation
examples
strengths
observed errors
supported recurrent patterns
skill evidence
proficiency interpretation
uncertainty
missing evidence
recommended next practice
progress context
```

Not every field appears in every response.

---

# 65. Presentation during conversation practice

Priority:

```text
natural interaction
↓
selective high-value correction
↓
brief feedback
↓
detailed review at an appropriate boundary
```

The response should not become a worksheet after every user sentence.

---

# 66. Presentation during teaching

Preferred semantic order:

```text
objective
explanation / input
example
practice
feedback
next step
```

---

# 67. Presentation during assessment

Preferred semantic order:

```text
evidence
skill assessed
observed performance
strengths / errors
confidence
estimated range if justified
missing evidence
```

Prohibited semantic shortcut:

```text
single sample -> definitive stable level
```

---

# 68. Presentation during writing review

The presentation layer should be able to distinguish:

```text
what works
correction
why
more natural alternative
priority error
register issue
valid variety
style preference
overall evidence
next practice
```

The system must distinguish:

```text
wrong
awkward / unnatural
register mismatch
valid alternative
preferred variety
```

---

# 69. Presentation during progress review

A progress review may show skill-by-skill state.

Example:

```text
speaking      B1+   improving
listening     B2    stable
reading       B2    improving
writing       B1+   improving
grammar       ...
vocabulary    ...
interaction   ...
```

But any compact indicator must remain traceable to evidence and confidence.

The domain must not create decorative certainty.

---

# 70. Cross-domain composition principle

Canonical ownership rule:

```text
domain owning the objective -> primary
domain providing specialized supporting competence -> supporting
```

The mere appearance of a language name must not automatically make Languages primary.

---

# 71. Languages + University

Example:

```text
"I need to give a presentation in English for a university subject."
```

Ownership:

```text
University
→ academic task
→ deadline
→ course requirements
→ university assessment context

Languages
→ English production
→ speaking/writing
→ vocabulary
→ correction
→ practice
```

Neither domain duplicates the other.

---

# 72. Languages + Oppositions

Example:

```text
"I need C1 Catalan for the opposition."
```

Ownership:

```text
Oppositions primary
→ requirement
→ consequences
→ deadline
→ opposition strategy

Languages supporting
→ current competence
→ C1 preparation
→ practice
→ certification readiness
```

Example:

```text
"Let's practice the oral part of the C1 exam."
```

Ownership:

```text
Languages primary
Oppositions supporting only if relevant context is needed
```

---

# 73. Languages + General

Example:

```text
"Explain the French Revolution."
```

Result:

```text
General primary
```

Example:

```text
"Explain the French Revolution in B1 English so I can practice reading."
```

Result:

```text
Languages primary
General supporting
```

General owns non-linguistic content knowledge.

Languages owns linguistic adaptation and pedagogical objective.

---

# 74. Languages + Concerns

Example:

```text
"I'm worried I'll never be able to speak English well."
```

Ownership:

```text
Concerns
→ worry
→ uncertainty
→ reassurance / perspective

Languages
→ actual evidence
→ progress
→ difficulty
→ learning plan
```

Canonical invariant:

```text
language evidence != automatic reassurance
```

Concerns must not alter proficiency to reassure.

Languages must not treat emotional distress as proficiency evidence.

---

# 75. Languages + Reflection

Example:

```text
"I feel embarrassed speaking Catalan because it doesn't feel like me."
```

Ownership:

```text
Reflection
→ meaning
→ identity experience
→ ambivalence

Languages
→ practice
→ competence
→ linguistic strategy
```

Languages must not convert an identity reflection into a pedagogical deficit.

Reflection must not invent language ability.

---

# 76. Cross-domain inputs

Languages may consume authorized projections such as:

```text
certification deadline
academic requirement
opposition requirement
available workload constraint
relevant concern context
explicit shared goal
authorized calendar availability
```

It must not read sibling domain internals directly.

---

# 77. Cross-domain outputs

Languages may expose purpose-minimized results such as:

```text
certification status
estimated readiness
relevant proficiency
progress toward shared goal
recommended workload
blocking language gap
```

It should not expose unnecessary detailed learning history.

---

# 78. Domain resolution examples

```text
"Teach me English phrasal verbs."
→ Languages primary

"Prepare me for Catalan C1."
→ Languages primary

"When must I have C1 for the opposition?"
→ Oppositions primary

"Help me plan my university semester, including English class."
→ University primary

"I'm scared I'll fail the C1."
→ Concerns primary + Languages supporting

"Why does speaking Catalan feel tied to my identity?"
→ Reflection primary + Languages supporting if needed

"Explain contract law in English B2 so I can practice."
→ Languages primary + General/University supporting depending context
```

---

# 79. Source authority

The domain must preserve source authority by type.

A user statement may ground:

- preferences;
- goals;
- lived experience;
- self-reported study history.

A user statement alone does not automatically ground:

- an official certification requirement;
- a current examination date;
- the equivalence between two proficiency frameworks;
- a certified result unless supported by adequate evidence.

Official certification sources have special authority for current official facts.

---

# 80. Temporal semantics

Temporally sensitive language-learning information includes:

```text
certification date
registration deadline
fees
exam format
accepted certificates
recognition rules
current official rubric
```

When a conclusion depends materially on such information, historical memory is not sufficient.

The result must preserve:

```text
current
historical
unknown
stale
needs_verification
```

as appropriate.

---

# 81. No private external-search capability

Languages may identify that current external information is needed.

It may request or consume a shared authorized external-research result.

It must not implement:

```text
languages.web_search
languages.browser
languages.scraper
```

as domain-private infrastructure.

---

# 82. Trace requirements

Languages traces must preserve, where applicable:

- resolved primary/supporting domains;
- selected `LanguageLearningProfile` mode;
- language;
- preferred variety;
- active goal refs;
- evidence refs;
- skill scope;
- proficiency kind;
- framework;
- uncertainty;
- selected rules;
- operation results;
- workflow state;
- observed errors;
- pattern decisions;
- progression decisions;
- certification-source authority;
- permission decisions;
- memory proposal state;
- cross-domain result refs;
- presentation requirements.

Trace must reference actual runtime result IDs.

Do not fabricate semantic-looking IDs from response text.

---

# 83. Trace epistemic invariants

Trace must preserve:

```text
certificate != estimate
estimate != observed performance
error != pattern
valid alternative != error
progression != isolated score change
exam readiness != proficiency
proposal != action
session state != memory
```

No presentation step may upgrade these categories silently.

---

# 84. Resource mapping

`resources.py` must map the 15 canonical resource kinds onto existing Cognitive Layer resource contracts.

The implementation must preserve:

- provenance;
- temporal validity;
- sensitivity;
- source identity;
- authorized projection;
- domain ownership.

No resource kind may become a hidden bypass around permissions.

---

# 85. Catalog reconciliation

`catalog.py` is the single canonical source for exactly:

```text
16 entities
15 resources
14 rules
15 operations
9 workflows
```

All other modules must derive or reconcile against this catalog.

Tests must fail when:

- a canonical member is missing;
- an undeclared production member is silently added;
- duplicate IDs exist;
- operation/workflow namespaces drift;
- an old 10.26 member remains as a competing canonical contract where incompatible.

---

# 86. Definition requirements

`definition.py` must declare `domain:languages` using existing domain contracts.

It must expose:

- ID;
- version;
- display name;
- kind;
- capabilities;
- profile refs;
- resource refs;
- rule refs;
- operation refs;
- workflow refs;
- permission profile refs;
- compatibility metadata.

No load-time execution is allowed.

---

# 87. Profile requirements

`profile.py` must define exactly the required Languages profile behavior using shared profile contracts.

At minimum it must represent:

```text
LanguageLearningProfile
```

and allow the six pedagogical modes without creating six independent profile registries.

Profile selection must remain compatible with multi-domain composition.

---

# 88. Rules requirements

`rules.py` must implement the 14 canonical rules through shared rule contracts.

Rules must:

- consume structured inputs;
- produce structured findings/decisions;
- preserve deterministic behavior where inputs are equivalent;
- fail closed on invalid evidence where safety/epistemic correctness depends on it;
- avoid string-only fake semantic authority where shared typed evidence exists.

---

# 89. Operations requirements

`operations.py` must register exactly the 15 canonical operations.

Each operation must declare:

- input schema;
- output schema;
- required resources;
- permission level;
- side-effect classification;
- profile/rule integration;
- trace requirements.

No operation may hide:

- memory mutation;
- calendar mutation;
- network access;
- payment;
- external communication.

---

# 90. Workflow requirements

`workflows.py` must declare the nine canonical workflows through the shared Workflow System.

Workflows must use:

- real operation IDs;
- real dependencies;
- shared validation gates;
- shared approval/pause semantics where needed;
- structured state.

No private workflow runner is allowed.

---

# 91. Permission requirements

`permissions.py` must express Languages permissions using the shared permission framework.

It must cover:

```text
low-risk internal pedagogy
consent-gated longitudinal tracking
shared approval for external mutations
fail-closed unauthorized cross-domain access
```

It must not define a parallel evaluator.

---

# 92. Memory requirements

`memory.py` must use shared memory view and proposal contracts.

It must support:

- authorized retrieval of relevant language state;
- candidate updates;
- confirmation/permission binding;
- no silent persistence;
- purpose-minimized cross-domain sharing;
- correction/invalidation proposals.

It must not own a database.

---

# 93. Presentation requirements

`presentation.py` must use shared presentation contracts.

It must preserve semantic output from operations/rules/workflows.

It must not:

- promote an estimate to certificate;
- promote observed performance to stable level;
- turn valid variety into error;
- hide insufficient evidence;
- remove approval/consent state;
- invent progress;
- silently alter risk/uncertainty supplied by supporting domains.

---

# 94. Integration requirements

`integration.py` must connect Languages to existing shared registries and composition paths.

It must not import sibling specialized implementation internals.

Cross-domain interaction must happen through shared contracts, domain results, profile composition, and permitted projections.

---

# 95. Bootstrap requirements

`bootstrap.py` must register the Languages pack atomically.

Required properties:

```text
preflight validation
collision detection
all-or-nothing registration
rollback on mid-bootstrap failure
idempotent behavior according to shared contract
no import-time registration
```

Failure must not leave:

- partial operations;
- partial rules;
- partial workflows;
- partial permissions;
- half-active domain state.

---

# 96. Public package boundary

The exact initial production package is:

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

Exactly 14 production modules.

A new production module requires a demonstrated design need, not convenience.

---

# 97. Import boundary

The Languages package must not directly depend on implementation internals of:

```text
cmm.domains.university
cmm.domains.oppositions
cmm.domains.concerns
cmm.domains.reflection
cmm.domains.relationships
cmm.domains.health
```

Shared contracts are allowed.

Sibling-domain outputs must arrive through supported composition mechanisms.

---

# 98. Determinism requirements

Equivalent semantic inputs should produce equivalent decisions for at least:

- proficiency-kind classification;
- skill-scope separation;
- variety validity classification;
- pattern eligibility;
- correction priority;
- progression classification;
- memory consent decision;
- certification-source authority.

Input ordering must not change semantic outcome when the underlying evidence set is equivalent.

---

# 99. Fresh import requirements

Required verification pattern:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import cmm.domains.languages
print("fresh_import=PASS")
PY
```

Fresh import must not:

- mutate registries;
- access user memory;
- execute workflows;
- make model calls;
- make network calls;
- write files;
- register external actions.

---

# 100. TDD strategy

Implementation must proceed test-first in small vertical units.

Recommended sequence:

```text
catalog / definition
↓
resources
↓
profile
↓
rules
↓
operations
↓
workflows
↓
permissions
↓
memory
↓
presentation
↓
trace
↓
integration / bootstrap
↓
connected acceptance
↓
adversarial audit
```

Tests should prove semantics, not merely object construction.

---

# 101. Required unit-test surface

At minimum include permanent tests for:

```text
catalog exactness
definition validity
resource mapping
profile modes
each canonical rule
each canonical operation contract
workflow definitions
permission classes
memory consent behavior
presentation semantic preservation
trace validation
bootstrap rollback
fresh import
```

---

# 102. Required proficiency tests

Prove:

```text
certificate remains CERTIFIED
estimate remains ESTIMATED
single task remains OBSERVED_PERFORMANCE

single strong sample
-> no automatic stable-level promotion

missing speaking evidence
-> no speaking estimate fabricated

skill-specific evidence
-> no unrelated-skill inflation

framework mapping
-> preserves approximate/non-identity semantics
```

---

# 103. Required variety tests

Prove at minimum:

```text
preferred American English + "color"
-> preferred

preferred American English + valid British "colour"
-> valid alternative, not error

regional/register difference
-> not automatically incorrect

unsupported/nonstandard production
-> may be flagged only with adequate grounding
```

---

# 104. Required error-pattern tests

Prove:

```text
one error -> observed_error only
repeated equivalent errors across adequate evidence -> candidate/evidenced pattern
same surface form with different semantics -> not blindly merged
valid variety difference -> not pattern
resolved pattern + later isolated slip -> no automatic full regression
```

---

# 105. Required correction-priority tests

Prove:

```text
fluency practice + minor style issue
-> does not interrupt unnecessarily

comprehension-blocking error
-> high priority

certification-critical repeated error
-> high priority in certification mode

assessment mode
-> feedback does not contaminate evidence before assessment completion
```

---

# 106. Required progression tests

Prove:

```text
one better result -> not stable progression
comparable repeated improvement -> stable improvement may be supported
non-comparable tasks -> insufficient evidence / qualified result
one poor session -> not automatic regression
skill improvement -> does not inflate all skills
```

---

# 107. Required speaking-evidence tests

Prove:

```text
text transcript only
-> pronunciation not assessed

audio/pronunciation-specific evidence
-> pronunciation may be assessed

speaking review
-> interaction and fluency remain distinguishable
```

---

# 108. Required certification tests

Prove:

```text
historical guide conflicts with current official source
-> official current source wins

stale official information
-> needs verification when materially relevant

readiness improves
-> does not automatically change general proficiency

exam registration request
-> proposal / shared external action path, no direct execution
```

---

# 109. Required memory tests

Prove:

```text
session observation
-> usable in-session
-> not automatically persistent

observed error
-> not silently stored as recurrent pattern

authorized progress tracking
-> may create a shared memory proposal

no consent / permission
-> persistence fails closed

cross-domain projection
-> shares only authorized minimal state
```

---

# 110. Required workflow tests

Test every workflow through the shared workflow contracts.

At minimum:

```text
Language Onboarding
Proficiency Assessment
Adaptive Language Lesson
Conversation & Roleplay Practice
Writing Review
Error Remediation
Vocabulary & Spaced Review
Certification Preparation
languages.progress_checkpoint
```

The tests must prove real operation references and valid dependencies.

---

# 111. Required cross-domain tests

At minimum:

```text
Oppositions primary + Languages supporting
for certification requirement

Languages primary + Oppositions supporting
for active language practice

University primary + Languages supporting
for university language task

Languages primary + General supporting
for content adapted to language practice

Concerns primary + Languages supporting
for worry about progress

Reflection primary + Languages supporting
for meaning/identity around language use
```

No sibling internal-store access.

---

# 112. Required permission tests

Prove:

```text
internal lesson generation -> low-risk path
progress persistence -> consent/policy path
calendar proposal -> allowed as proposal
calendar write -> not directly authorized by Languages
exam registration -> no direct action
external communication -> shared approval path
unauthorized domain_result -> fail closed
```

---

# 113. Required presentation parity tests

For each canonical operation result, verify that presentation preserves its key semantics.

At minimum:

```text
assess_sample
-> observed performance remains observed

update_level_evidence
-> estimate remains estimate

review_writing
-> valid alternative remains valid alternative

review_speaking
-> unassessed pronunciation remains unassessed

review_errors
-> observed error does not become recurrent pattern

prepare_certification
-> readiness remains distinct from proficiency

generate_progress_review
-> uncertainty / insufficient evidence remains visible
```

---

# 114. Required trace tests

Trace must use actual IDs from the connected execution path.

At minimum test:

- selected primary/supporting domains;
- profile mode;
- actual operation/workflow result IDs;
- evidence refs;
- proficiency kind;
- skill scope;
- rule decisions;
- permission decisions;
- memory proposal state;
- cross-domain result refs.

No fabricated IDs.

---

# 115. Required bootstrap rollback tests

Use shared registries with pre-existing unrelated entries.

Prove:

```text
collision before registration
-> zero mutation

mid-bootstrap rule failure
-> previous shared state restored

workflow registration failure
-> operations/rules/resources restored

permission registration failure
-> no partially active Languages domain
```

---

# 116. Required adversarial tests

The independent-style adversarial suite should include cases such as:

1. one excellent writing sample is presented as proof of C1;
2. a valid British spelling is submitted under American-English preference;
3. a transcript is used to claim pronunciation quality;
4. a user makes the same error twice inside one copied sentence;
5. two proficiency frameworks are treated as exactly interchangeable;
6. exam readiness is promoted to global proficiency;
7. a single bad session is treated as regression;
8. a low-energy week triggers permanent difficulty downgrade;
9. a correction preference is treated as objective correctness;
10. historical certification information is presented as current;
11. a calendar proposal attempts direct mutation;
12. session-level errors are silently persisted;
13. Oppositions requirement imports full language-learning history;
14. worry about speaking is treated as evidence of poor speaking;
15. identity reflection is treated as proficiency deficit;
16. high grammar score is used to infer high interaction;
17. current certification source conflicts with memory;
18. no speaking sample exists but a global exact CEFR result is produced.

Every unsafe promotion must fail closed or remain explicitly qualified.

---

# 117. Non-goals

Phase 10.26 does not implement:

- UI;
- voice interface;
- speech-to-text engine;
- text-to-speech engine;
- pronunciation-recognition provider;
- model routing;
- provider selection;
- custom LLM;
- new Cognitive Layer;
- new memory backend;
- new Knowledge Graph;
- new planner;
- new Agent Runtime;
- new workflow engine;
- new permission engine;
- new calendar integration;
- web browser;
- private web search;
- email sending;
- exam registration;
- payment;
- automatic certification booking;
- generic translation platform;
- generic university tutoring;
- generic opposition planning;
- therapy;
- psychological diagnosis;
- cultural profiling;
- hidden long-term surveillance.

---

# 118. Documentation requirements

Implementation/closure must create or update:

```text
docs/superpowers/specs/2026-08-23-languages-domain-design.md
docs/reference/languages-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
```

The roadmap Phase 10.26 section must be replaced, not merely appended.

The requirements matrix must update `DP-026` / `AT-DP-026` to the frozen semantics.

The historical 10.26 catalog must not remain as a competing canonical acceptance source.

---

# 119. Redesigned DP-026

Canonical acceptance intent:

```text
DP-026 — Language Learning and Progress

CMM OS must be able to support sustained language learning by:

- onboarding one or more languages with explicit longitudinal-tracking consent;
- representing preferred language variety without invalidating other correct varieties;
- supporting multiple concurrent language goals;
- separating certified proficiency, estimated proficiency, and observed performance;
- evaluating proficiency by skill from grounded evidence;
- preserving uncertainty when evidence is insufficient;
- generating adaptive lessons and exercises;
- supporting conversation and roleplay practice;
- reviewing writing and speaking through evidence-appropriate criteria;
- distinguishing observed errors from evidence-backed recurrent patterns;
- prioritizing corrections without destroying communicative flow;
- tracking vocabulary, grammar, and review items under shared memory policy;
- adapting difficulty and learning load;
- preparing certifications while separating readiness from general proficiency;
- verifying temporally sensitive official certification information;
- reviewing versioned progression through comparable evidence;
- composing with other domains through minimal authorized projections;
- preserving permissions, provenance, temporal validity, traceability, and user control.
```

Canonical acceptance identifiers remain:

```text
DP-026
AT-DP-026
```

This redesigned DP-026 supersedes the previous narrow roadmap formulation.

---

# 120. AT-DP-026 minimum connected end-to-end scenario

The acceptance test should prove one connected deterministic scenario equivalent to:

```text
1. User starts onboarding English.
2. Domain Resolver selects Languages as primary.
3. User chooses American English as preferred variety.
4. A valid British-English form is retained as a valid alternative.
5. User provides two concurrent goals:
   conversation fluency
   and C1 preparation.
6. Longitudinal progress tracking is explicitly authorized.
7. User provides a real prior certificate at a lower level.
8. Certificate is represented as CERTIFIED evidence.
9. System performs an initial writing assessment.
10. Writing result is represented as OBSERVED_PERFORMANCE.
11. System does not overwrite the certificate.
12. Speaking evidence is missing.
13. System explicitly preserves the speaking gap.
14. System proposes an estimated writing range only where justified.
15. An adaptive learning plan is created.
16. Adaptive Language Lesson workflow runs.
17. The user completes a real exercise.
18. One error is observed.
19. The error is not promoted to a recurrent pattern.
20. Conversation & Roleplay Practice runs through real turn operations.
21. Another comparable occurrence of a target error is observed later.
22. ErrorPatternEvidenceRule evaluates the accumulated evidence.
23. Only sufficiently supported recurrence becomes a candidate/evidenced pattern.
24. CorrectionPriorityRule chooses selective feedback rather than correcting every low-value issue.
25. A writing review produces structured feedback.
26. Valid variety differences remain non-errors.
27. A Progress Review executes through `languages.progress_checkpoint`.
28. One better isolated score does not become stable progression.
29. Comparable accumulated evidence supports only the progression actually justified.
30. User adds an official certification target.
31. A historical preparation guide conflicts with a current official source.
32. CertificationTemporalRule gives authority to the current official source.
33. Certification Preparation estimates readiness separately from general proficiency.
34. Languages proposes a review schedule.
35. No calendar mutation occurs.
36. The user asks to add a calendar event.
37. Languages routes this to the shared approval/external-operation path rather than performing the write itself.
38. A persistent proficiency/progress update is proposed through shared memory contracts.
39. Consent and permission are validated before persistence.
40. A cross-domain Oppositions scenario receives only the minimal authorized certification/readiness projection.
41. Full vocabulary/error history is not exported.
42. Presentation preserves certified/estimated/observed distinctions.
43. Presentation preserves unassessed speaking/pronunciation gaps.
44. Domain trace references actual resolver, workflow, operation, evidence, rule, permission, and memory-proposal result IDs.
45. No parallel planner, runtime, store, workflow engine, permission engine, or calendar engine is introduced.
```

The acceptance harness does not require an LLM.

It must exercise the real shared contracts.

---

# 121. Connected acceptance requirements

`AT-DP-026` must not be a disconnected sequence of helper calls with unrelated fixtures.

The connected path must prove:

```text
resolver
→ Languages profile
→ authorized resources
→ assessment
→ evidence typing
→ learning plan
→ lesson workflow
→ exercise result
→ error observation
→ conversation / roleplay workflow
→ error-pattern evidence
→ writing review
→ progress checkpoint
→ certification temporal verification
→ review proposal
→ permission boundary
→ memory proposal
→ cross-domain projection
→ presentation
→ trace
```

Later steps must consume actual results from earlier steps.

---

# 122. Behavioral invariants

Implementation must prove:

```text
language A != language B

preferred variety != exclusive correct variety
valid variety difference != error

certified proficiency != estimated proficiency
estimated proficiency != observed performance
global proficiency != skill-specific proficiency

one error != recurrent error pattern
practice result != stable proficiency
better score once != stable progression

transcript != pronunciation evidence

certification readiness != general proficiency
framework mapping != framework identity

teaching != assessment
assessment != coaching
practice != constant interruption

review proposal != calendar write
recommendation != authorization
certification preparation != registration

session observation != persistent memory
candidate memory update != confirmed persistence

cross-domain relevance != unrestricted sharing

pedagogical semantics != communication persona
```

---

# 123. Self-audit requirements

Before declaring Phase 10.26 ready for independent audit, inspect for:

- old `proficiency_level` semantics retained as one undifferentiated level;
- old `mistake` model retained without observed/pattern separation;
- `study_session` copied from University/Oppositions instead of `practice_session`;
- `exam` treated as equivalent to sustained `certification_target`;
- American/British or other recognized variety differences marked as errors;
- exact framework equivalences without provenance;
- single-sample stable-level promotion;
- cross-skill inference inflation;
- transcript-only pronunciation assessment;
- exam readiness promoted to general proficiency;
- one better score promoted to stable progression;
- one poor session promoted to regression;
- pattern creation from insufficient recurrence;
- correction density that destroys conversation flow;
- lesson workflow implemented as a private engine;
- multi-turn conversation implemented as a private agent runtime;
- review schedule implemented as direct calendar mutation;
- progress tracking persisted without consent;
- sibling-domain internal imports;
- unrestricted cross-domain data sharing;
- stale certification data treated as current;
- presentation promotion of estimates/observations;
- trace built from fake IDs;
- import-time registry mutation;
- bootstrap partial state after failure;
- undeclared catalog drift.

---

# 124. Static and quality gates

The implementation plan must include, at minimum:

```text
targeted Languages tests
shared Domain Intelligence regression tests
cross-domain regression tests
workflow regression tests
permission/memory regression tests
global pytest
Ruff
Ruff with supported Python target
compileall
fresh import
git diff --check
package-boundary verification
tracked-worktree verification
```

Do not hard-code historical global test totals.

Use the repository's current green baseline at execution time.

---

# 125. Independent audit expectations

Independent audit should evaluate:

- exact catalog;
- package boundary;
- shared-contract reuse;
- no sibling internals;
- epistemic proficiency separation;
- skill separation;
- variety handling;
- framework handling;
- error-pattern evidence;
- correction priority;
- adaptive difficulty;
- spaced review;
- progression evidence;
- certification temporal validity;
- memory consent;
- permissions;
- cross-domain minimization;
- presentation semantic preservation;
- actual connected `AT-DP-026`;
- trace provenance;
- bootstrap rollback;
- global regressions.

The audit should include metamorphic and adversarial probes rather than only replaying permanent tests.

---

# 126. Canonical summary

```text
DOMAIN
domain:languages

DISPLAY NAME
Idiomas

PROFILE
LanguageLearningProfile

MODES
teach
practice
assess
review
certification
immersion

ENTITIES = 16
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

RESOURCES = 15
user_message
conversation
writing_sample
audio_transcript
exercise_result
assessment_result
language_plan
lesson_material
vocabulary_list
language_reference
certification_guide
official_certification_source
calendar_event
memory_entry
domain_result

RULES = 14
LanguageLevelEvidenceRule
SkillSeparationRule
LanguageVarietyValidityRule
ProficiencyFrameworkRule
ErrorPatternEvidenceRule
CorrectionPriorityRule
AdaptiveDifficultyRule
SpacedReviewRule
LearningLoadRule
GoalAlignmentRule
ProgressionEvidenceRule
CertificationTemporalRule
CulturalContextEvidenceRule
LanguageMemoryConsentRule

OPERATIONS = 15
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

WORKFLOWS = 9
Language Onboarding
Proficiency Assessment
Adaptive Language Lesson
Conversation & Roleplay Practice
Writing Review
Error Remediation
Vocabulary & Spaced Review
Certification Preparation
Progress Review

CANONICAL PROGRESS WORKFLOW ID
languages.progress_checkpoint

PACKAGE MODULES = 14
__init__.py
bootstrap.py
catalog.py
definition.py
integration.py
memory.py
operations.py
permissions.py
presentation.py
profile.py
resources.py
rules.py
trace.py
workflows.py
```

---

# 127. Freeze statement

Once approved and committed, this document becomes the canonical Phase 10.26 implementation design.

Implementation must not silently change:

```text
domain identity
catalog counts
catalog names
profile identity
pedagogical modes
permission boundaries
memory-consent semantics
cross-domain ownership rules
core behavioral invariants
AT-DP-026 intent
```

If implementation reveals a real contradiction or a missing requirement, update this design explicitly before changing the canonical contract.

No implementation should begin from the superseded historical 10.26 roadmap catalog.

---

# 128. Phase outcome

After Phase 10.26 is implemented and independently audited, CMM OS should be able to function as a coherent language-learning companion that:

- learns alongside the user without pretending to know more than the evidence supports;
- teaches actively;
- supports natural practice;
- adapts to goals and difficulty;
- handles several languages at once;
- respects preferred varieties;
- distinguishes certified, estimated, and observed competence;
- understands skill asymmetry;
- detects genuine recurrent weaknesses without pathologizing isolated mistakes;
- uses spaced review;
- prepares certifications without becoming exam-only;
- tracks progress only under the proper consent model;
- composes safely with University, Oppositions, General, Concerns, and Reflection;
- preserves provenance, temporal validity, permissions, and traceability;
- remains one Domain Pack inside the shared CMM OS architecture rather than a separate tutor application.
