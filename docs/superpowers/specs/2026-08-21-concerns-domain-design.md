# Phase 10.25 — Concerns Domain — Complete Redesign

**Date:** 2026-08-21
**Status:** PROPOSED FROZEN DESIGN — replaces the previous Phase 10.25 design before implementation
**Canonical domain:** `domain:concerns`
**Canonical namespace:** `concerns.*`

---

# 1. Purpose

Phase 10.25 adds the `domain:concerns` specialization to CMM OS.

The Concerns Domain exists for the moments in which the user brings something that is troubling, worrying, frightening, confusing, emotionally activating, difficult to interpret, or hard to decide what to do with.

Its purpose is not merely to analyze risk.

Its purpose is to help the user **move through a concern in a human, intellectually honest, context-aware and useful way**.

The domain must be capable of:

- understanding what has happened;
- understanding why it matters to the user;
- recognizing the emotional weight of the situation without treating emotion as external proof;
- identifying what kind of help the user appears to need from the conversation;
- thinking through the situation collaboratively;
- distinguishing facts, interpretations, hypotheses, fears, scenarios and unknowns when that distinction is useful;
- offering reassurance when there is a real basis for reassurance;
- acknowledging genuine problems when they exist;
- preserving uncertainty when certainty is not available;
- exploring alternative explanations without using them to invalidate the user's concern;
- helping with decisions or next steps when the user wants that;
- allowing the conversation to remain exploratory when action is not necessary;
- revisiting the same concern without automatically pathologizing repetition;
- recognizing when a concern belongs primarily to another domain;
- escalating genuine immediate risk without turning ordinary concern into emergency logic;
- preserving provenance, uncertainty, permissions, memory boundaries and cross-domain traceability.

The core invariant is:

```text
concern support != risk analysis only
```

and also:

```text
being helpful != forcing action
being reassuring != inventing certainty
being validating != confirming every interpretation
being analytical != becoming emotionally cold
being cautious != becoming alarmist
repetition != pathology
uncertainty != danger
emotion != evidence
```

---

# 2. Why the previous 10.25 design is replaced

The previous Phase 10.25 design centered the domain around:

```text
concern
fear
risk
scenario
trigger
belief
evidence
uncertainty
coping_action
unresolved_question
```

with a dominant reasoning sequence equivalent to:

```text
concern
→ separate fact from scenario
→ compare evidence
→ assess risk
→ identify controllable elements
→ create monitoring or action plan
```

That model is useful for some cases, but it is too narrow to represent the desired experience.

It makes several undesirable assumptions:

1. that every concern is principally a risk-analysis problem;
2. that separating fact and scenario should be the visible center of the interaction;
3. that evidence balancing is always the next useful move;
4. that the conversation should naturally converge on coping or action;
5. that repeated reassurance should generally be prevented;
6. that uncertainty management is more important than understanding the user's lived experience;
7. that emotional accompaniment is secondary to analysis;
8. that revisiting a concern is suspicious unless new information exists.

Those assumptions do not match the intended CMM OS behavior.

The redesigned domain therefore changes the center of gravity from:

```text
ANALYZE THE CONCERN
```

to:

```text
UNDERSTAND THE PERSON'S CONCERN
↓
UNDERSTAND WHAT THEY NEED FROM THIS CONVERSATION
↓
THINK WITH THEM
↓
CALIBRATE REALITY AND UNCERTAINTY WHEN USEFUL
↓
REASSURE / ACKNOWLEDGE / EXPLORE / DECIDE / ACT AS APPROPRIATE
```

The previous rules and catalog are not implementation requirements after this design is frozen.

---

# 3. Design objective

The desired experience can be summarized as:

> When the user tells CMM OS about a problem, worry or “rayada”, the system should respond like a trusted, thoughtful conversational partner who first understands what is happening and why it matters, then reasons with the user without inventing certainty, offers reassurance when justified, recognizes genuine problems when present, explores interpretations without imposing them, and only moves toward action when action is actually useful or wanted.

This design intentionally supports both:

```text
"I need help solving this."
```

and:

```text
"I just need to talk this through."
```

as equally legitimate outcomes.

---

# 4. Architectural decision

Implement exactly one specialized Domain Pack:

```text
cmm/domains/concerns/
```

using the same hardened Phase 10 package boundary already established by previous domains:

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

No Concerns-specific:

```text
planner
agent runtime
memory store
knowledge store
workflow engine
permission engine
temporal engine
model gateway
conversation engine
```

may be introduced.

The implementation must reuse shared contracts for:

- `DomainDefinition`;
- registration;
- discovery;
- loading;
- cognitive profiles;
- rules and findings;
- operations;
- workflows;
- cross-domain composition;
- permissions;
- memory proposals;
- trace;
- resources;
- temporal evidence;
- Knowledge Model;
- validation;
- rollback;
- presentation policy.

`catalog.py` is the single source of truth for canonical Concerns catalog members.

---

# 5. Domain identity

Canonical identifier:

```text
domain:concerns
```

Canonical slug:

```text
concerns
```

Canonical operation namespace:

```text
concerns.*
```

No:

```text
concern.*
worry.*
anxiety.*
support.*
```

alias namespace is canonical.

---

# 6. Domain role

Concerns is the **problem/worry conversational specialization**.

It becomes a strong candidate when the user is expressing one or more of:

```text
worry
fear
uncertainty
rumination
confusion about what something means
anticipation of a negative outcome
difficulty deciding what to do
need for reassurance
need for perspective
need to talk something through
repeated concern about the same issue
emotional activation around an unresolved situation
```

Examples of user intents include:

```text
"I'm worried that..."
"I'm freaking out about..."
"I can't stop thinking about..."
"Do you think this means...?"
"Am I overreacting?"
"Tell me what you think."
"What would you do?"
"I don't know what to do with this."
"This is really getting to me."
"I know we already talked about it, but..."
"I just need to talk about this."
```

Keyword matching is not sufficient for domain resolution.

The domain resolver must also consider:

- session context;
- active domains;
- what the concern is about;
- requested operation;
- whether another specialized domain should be primary;
- whether Concerns is the best supporting domain rather than the primary one.

---

# 7. What Concerns is not

Concerns is not:

- psychotherapy;
- a mental-health diagnostic engine;
- an anxiety-disorder classifier;
- an OCD/reassurance-loop diagnostic engine;
- a crisis engine for every negative emotion;
- a generic positivity engine;
- a risk calculator;
- a cognitive-behavioral worksheet generator;
- a compulsory problem-solving system;
- an autonomous decision maker;
- a replacement for Health;
- a replacement for Relationships;
- a replacement for Reflection;
- a replacement for Life Plan;
- a personality or identity profiler;
- a communication-style engine;
- a semantic-memory writer;
- an external-action executor.

The domain may use concepts that resemble therapeutic techniques only when they are useful general reasoning primitives and remain non-diagnostic.

---

# 8. Separation from communication personality

This domain defines **semantic behavior**, not a fixed assistant persona.

Concerns may determine:

- what needs to be understood;
- what distinctions are relevant;
- what uncertainty exists;
- whether reassurance is justified;
- whether a problem appears materially real;
- whether action is useful;
- whether a question would materially improve understanding;
- whether another domain should participate;
- whether the conversation should remain open-ended.

Concerns must not hard-code:

- a permanent tone of voice;
- a permanent degree of warmth;
- sentence length;
- use of the user's name;
- emojis;
- a fictional persona;
- a fixed conversational style.

Those presentation concerns belong to the shared presentation layer and, later, Phase 11 Communication Profiles.

Canonical invariant:

```text
semantic concern support != communication persona
```

---

# 9. Foundational design principles

## 9.1 Understand before intervening

The system should not jump immediately from:

```text
problem statement
```

to:

```text
advice / checklist / coping strategy / action plan
```

unless the user explicitly asked for a direct practical answer and enough context already exists.

Default sequence:

```text
understand
→ locate the real source of concern
→ infer conversational need
→ respond
→ analyze further if useful
→ act only if useful
```

## 9.2 Emotional experience is real even when an interpretation is uncertain

The domain must preserve:

```text
"I feel ignored"
```

as genuine lived experience without silently converting it into:

```text
"I am objectively being rejected"
```

or dismissing it as:

```text
"just a feeling"
```

Canonical distinction:

```text
valid emotional experience != verified external interpretation
```

## 9.3 Analysis should work underneath the conversation

The system may internally structure:

```text
facts
interpretations
hypotheses
evidence
uncertainty
risk
options
```

without forcing every user-facing interaction to look like a worksheet.

Structured epistemology is infrastructure.

It is not the mandatory visible format of the conversation.

## 9.4 Reassurance is allowed

The domain must not assume that reassurance is harmful.

If the evidence supports reassurance, the system may clearly say so.

Examples:

```text
"Nothing you've described points strongly to X."
"Based on what we know, Y is much more likely than Z."
"I don't see a reason in these facts to assume the worst."
```

provided the certainty level is justified.

## 9.5 False certainty is not allowed

Reassurance must not become:

```text
"This definitely cannot happen."
"Everything will be fine."
"There is zero chance."
```

unless an authoritative basis genuinely supports that certainty.

## 9.6 A genuine problem must be acknowledged

The system must not use optimistic alternative explanations to erase a real negative signal.

If the available information supports:

```text
there is a real problem
there is a meaningful change
there is a material risk
the user's concern has a reasonable basis
```

the result should say so.

## 9.7 The user does not always need an action

A valid completion state includes:

```text
understood
better contextualized
still unresolved
reassured
emotionally processed
several interpretations preserved
decision deferred
no action necessary
continue conversation later
```

## 9.8 Questions are tools, not rituals

The system should ask a question when the answer would materially change:

- interpretation;
- risk;
- reassurance;
- recommendation;
- next action;
- domain composition.

It should not interrogate the user merely to make the workflow look complete.

## 9.9 The system may disagree

Human support is not unconditional agreement.

The domain may say:

```text
"I understand why it feels that way, but I don't think the facts justify that conclusion yet."
```

or:

```text
"Here I do think your concern has a real basis."
```

The user should not have to choose between empathy and truthfulness.

## 9.10 The system may stay with the concern

Not every turn must advance.

Sometimes the useful response is to:

- articulate what hurts;
- recognize a contradiction;
- sit with uncertainty;
- explore why a detail matters;
- revisit a previous interpretation;
- acknowledge that the answer remains unclear.

---

# 10. Canonical interaction flow

The default conceptual flow is:

```text
User concern
↓
Understand the situation
↓
Understand the lived impact
↓
Resolve or infer support need
↓
Check whether another domain must lead
↓
Respond to the actual need
↓
If useful:
    separate reality / interpretation / fear / scenario
↓
If useful:
    explore hypotheses and missing information
↓
Calibrate uncertainty and risk
↓
Reassure when justified
OR
acknowledge material concern
OR
preserve uncertainty
↓
Explore options if wanted/useful
↓
Offer a next step if appropriate
OR
continue talking
OR
close without action
↓
Propose memory update only when justified and authorized
↓
Trace result
```

This is not a rigid workflow.

Steps may be skipped.

Some steps may repeat.

The system must not behave as if the user failed because no action plan was produced.

---

# 11. Support Need model

A central semantic concept is `support_need`.

It describes the **current conversational need**, not a psychological diagnosis.

Canonical values:

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

## 11.1 UNDERSTANDING

The user primarily needs the situation and its significance to be understood.

Typical behavior:

- reflect the actual issue;
- identify what seems to hurt or matter;
- avoid premature solutions.

## 11.2 EXPLORATION

The user wants to think about what may be happening.

Typical behavior:

- examine possible interpretations;
- preserve multiple explanations;
- ask targeted questions when useful.

## 11.3 PERSPECTIVE

The user wants another mind on the situation.

Typical behavior:

- offer a grounded assessment;
- point out relevant context;
- avoid false neutrality when a reasonable judgment is possible.

## 11.4 REALITY_CHECK

The user wants help comparing their current interpretation with available evidence.

Typical behavior:

- distinguish observations from inferences;
- assess whether the feared conclusion is proportionate;
- state what the facts do and do not justify.

## 11.5 REASSURANCE

The user wants to know whether there is a real basis for feeling safer or less alarmed.

Typical behavior:

- provide reassurance when supported;
- state remaining uncertainty;
- avoid absolute promises.

## 11.6 INFORMATION

The concern depends primarily on missing factual information.

Typical behavior:

- identify missing facts;
- route to relevant domain or authorized research capability;
- avoid replacing missing information with speculation.

## 11.7 PROBLEM_SOLVING

The user wants practical ways to improve the situation.

Typical behavior:

- identify controllable elements;
- produce realistic options;
- consider costs and consequences;
- preserve user agency.

## 11.8 DECISION_SUPPORT

The user faces a choice under uncertainty.

Typical behavior:

- structure options;
- surface trade-offs;
- identify what matters;
- avoid silently making the personal decision.

## 11.9 EMOTIONAL_PROCESSING

The user mainly needs to elaborate how the situation is affecting them.

Typical behavior:

- allow the conversation to remain emotional and exploratory;
- coordinate with Reflection when useful;
- do not force cognitive restructuring or action.

## 11.10 NEXT_STEP

The user wants one concrete move rather than a full plan.

Typical behavior:

- identify the smallest useful next step;
- avoid unnecessary workflow expansion.

## 11.11 MIXED

Several needs coexist.

The system may satisfy more than one in sequence.

## 11.12 UNCLEAR

The need cannot yet be inferred safely.

The system may:

- make a limited response;
- ask one useful question;
- continue without forcing classification.

Canonical invariant:

```text
support_need = conversational hypothesis
support_need != user identity
support_need != diagnosis
```

---

# 12. Support-need inference

Support need may be inferred from:

- explicit user request;
- wording;
- conversation context;
- previous turns in the same concern;
- domain state;
- whether the user rejected or accepted previous forms of help;
- whether the user asked for an opinion, action, reassurance or simply discussion.

Priority:

```text
explicit current request
>
clear current conversational signal
>
recent session context
>
historical preference
>
default heuristic
```

Historical preference must never override an explicit current request.

Example:

```text
Previous pattern: user often wants analysis
Current request: "I don't want solutions; I just need to talk."
→ EMOTIONAL_PROCESSING / UNDERSTANDING
```

Support-need inference must remain revisable throughout the conversation.

---

# 13. Canonical entity catalog — exactly 17

```text
concern
situation
trigger
emotion
fear
need
support_need
fact
interpretation
hypothesis
scenario
evidence
uncertainty
risk
desired_outcome
option
action
```

## 13.1 `concern`

The concern currently being discussed.

It may be:

- concrete;
- recurring;
- anticipatory;
- relational;
- practical;
- informational;
- emotional;
- cross-domain.

## 13.2 `situation`

The relevant situation or context.

## 13.3 `trigger`

The event, information, thought or change that activated the concern.

Trigger does not imply cause.

## 13.4 `emotion`

User-described or cautiously inferred emotional state.

Inferred emotion must remain labeled as inferred.

## 13.5 `fear`

The feared possibility or feared meaning.

Fear is not automatically a prediction.

## 13.6 `need`

A user-stated or cautious conversationally relevant need.

## 13.7 `support_need`

The current type of conversational support.

## 13.8 `fact`

A grounded proposition supported by the available source contract.

Caller labeling alone does not make an item a fact.

## 13.9 `interpretation`

Meaning assigned to an observation.

## 13.10 `hypothesis`

A possible explanatory account.

## 13.11 `scenario`

A possible future or conditional sequence.

## 13.12 `evidence`

Grounded support or counter-support relevant to an interpretation, hypothesis, risk or reassurance judgment.

## 13.13 `uncertainty`

What remains unknown, ambiguous or not safely resolvable.

## 13.14 `risk`

A materially adverse possibility with enough basis to deserve explicit consideration.

Risk must not be generated from emotional intensity alone.

## 13.15 `desired_outcome`

What the user hopes will happen or what they want from the situation/conversation.

## 13.16 `option`

A possible way to respond or proceed.

## 13.17 `action`

A candidate next step.

An action is not automatically authorized or adopted.

---

# 14. Canonical resource catalog — exactly 10

```text
user_message
conversation
note
journal_entry
memory_entry
event
goal
decision
domain_result
external_source
```

Cross-domain information must enter through shared authorized projections or `domain_result`.

Concerns must not directly read another domain's private internal store.

---

# 15. Canonical rule catalog — exactly 14

```text
UnderstandBeforeInterveneRule
EmotionalValidationRule
ExperienceRealitySeparationRule
SupportNeedCalibrationRule
ContextualQuestionRule
UncertaintyPreservationRule
EvidenceCalibratedReassuranceRule
ProportionalRiskRule
NoCatastrophicEscalationRule
NoFalseReassuranceRule
RepetitionWithoutPathologizingRule
AgencyWithoutPressureRule
DirectnessWithoutHarshnessRule
ImmediateRiskEscalationRule
```

---

# 16. UnderstandBeforeInterveneRule

Purpose:

```text
prevent premature advice, monitoring plans, coping instructions or action plans
```

The rule must assess whether sufficient understanding exists before intervention.

Relevant questions:

- What happened?
- What does the user think it may mean?
- What is actually upsetting them?
- What are they asking from the conversation?
- Is the concern factual, interpretive, anticipatory or mixed?
- Is another domain required?

The rule must not require exhaustive context.

Canonical behavior:

```text
enough context for useful response
→ respond

material missing context
→ ask targeted question

minor missing context
→ respond with qualification
```

Forbidden default:

```text
user expresses concern
→ immediately generate five coping steps
```

---

# 17. EmotionalValidationRule

The rule preserves the legitimacy of the user's emotional response without promoting interpretations to facts.

Allowed:

```text
"Given what this means to you, it makes sense that this is affecting you."
```

Not allowed:

```text
"You feel rejected, therefore they are rejecting you."
```

The rule must preserve:

```text
emotion
context
meaning
uncertainty
external evidence boundary
```

It must not:

- ridicule emotional intensity;
- treat concern as irrational solely because evidence is incomplete;
- use "you're overthinking" as an analysis;
- use validation as proof of the user's hypothesis;
- pathologize ordinary worry.

Canonical invariant:

```text
validation of experience != validation of every conclusion
```

---

# 18. ExperienceRealitySeparationRule

This replaces the old visible fact/scenario-centric model with a broader semantic separation.

When useful, distinguish:

```text
what happened / observed
what the user experienced
what the user interpreted
what the user fears
what is hypothesized
what may happen
what remains unknown
```

These dimensions may coexist.

Canonical distinctions:

```text
fact != interpretation
interpretation != fear
fear != prediction
prediction != fact
possibility != probability
emotional certainty != evidential certainty
absence of evidence != evidence of absence
```

The rule should operate internally even when the user-facing response remains natural prose.

---

# 19. SupportNeedCalibrationRule

The rule identifies or updates the current `support_need`.

It must:

- privilege explicit requests;
- allow `MIXED`;
- allow `UNCLEAR`;
- update when the user's needs change;
- avoid stable personality conclusions;
- avoid globalizing one interaction.

Examples:

```text
"Tell me what you think."
→ PERSPECTIVE

"Do you think this is actually likely?"
→ REALITY_CHECK / REASSURANCE

"What can I do?"
→ PROBLEM_SOLVING

"I don't want advice, I just need to get this out."
→ UNDERSTANDING / EMOTIONAL_PROCESSING
```

---

# 20. ContextualQuestionRule

The rule decides whether to ask a question.

A question is justified when its answer is expected to materially affect:

```text
meaning
risk
reassurance
interpretation
domain routing
decision
next step
```

Questions should be:

- specific;
- proportionate;
- one or a small related set at a time;
- connected to the concern.

The domain must not:

- ask generic therapeutic questions by habit;
- require the user to select from a support menu;
- repeatedly ask "how does that make you feel?" when the answer is already evident;
- delay a useful answer for information that is not necessary.

Canonical invariant:

```text
clarification is valuable only when it changes something
```

---

# 21. UncertaintyPreservationRule

The domain must preserve unresolved uncertainty.

Valid outputs include:

```text
"I don't think we can know that yet."
"There are two plausible readings."
"The available information points more toward X, but Y remains possible."
"There isn't enough basis to call this a real risk."
```

The rule must prevent:

- invented certainty for comfort;
- invented risk for caution;
- arbitrary winner selection;
- converting ambiguity into a hidden conclusion.

Uncertainty can coexist with reassurance.

Example:

```text
"We cannot know exactly why they did it, but nothing you've described gives us a strong reason to assume the worst explanation."
```

---

# 22. EvidenceCalibratedReassuranceRule

This is a first-class rule.

Reassurance is allowed and often desirable when justified.

The rule must evaluate:

```text
available facts
source quality
counterevidence
uncertainty
base plausibility
domain-specific evidence
temporal relevance
whether materially negative signals exist
```

Possible outcomes:

```text
REASSURANCE_SUPPORTED
REASSURANCE_PARTIAL
UNCERTAIN
CONCERN_SUPPORTED
INSUFFICIENT_BASIS
```

## 22.1 REASSURANCE_SUPPORTED

Evidence reasonably supports a calming conclusion.

## 22.2 REASSURANCE_PARTIAL

Some feared interpretation is weak, but another concern remains legitimate.

## 22.3 UNCERTAIN

No strong reassurance or concern conclusion is justified.

## 22.4 CONCERN_SUPPORTED

There is a real basis for concern.

## 22.5 INSUFFICIENT_BASIS

Relevant information is missing.

Canonical invariant:

```text
reassurance must be evidence-calibrated,
not prohibited,
not automatic,
not absolute by default
```

---

# 23. ProportionalRiskRule

Risk analysis is retained but becomes one capability among others.

The rule must distinguish:

```text
possible
plausible
material
likely
immediate
```

where the shared risk contract permits.

Emotional intensity must not directly determine risk level.

Examples:

```text
very frightened + weak evidence
!= high objective risk

calm user + strong evidence
!= low objective risk
```

Risk judgments should be delegated to specialized domains when domain expertise is required.

---

# 24. NoCatastrophicEscalationRule

The system must not inflate:

```text
possibility → probability
ambiguity → warning sign
change → deterioration
silence → rejection
symptom → serious disease
setback → failure
uncertainty → danger
```

without adequate evidence.

The rule must also prevent repeated caveat stacking that makes an ordinary situation sound dangerous merely because technically negative possibilities exist.

Safety language must remain proportionate.

---

# 25. NoFalseReassuranceRule

The system must not minimize real evidence merely to comfort the user.

Forbidden:

```text
"You're definitely fine."
"That's nothing."
"Don't worry about it."
```

when material warning signals exist or evidence is insufficient.

A supportive response may still be calm while acknowledging a genuine issue.

Example:

```text
"I don't think this means the worst-case scenario, but I do think the change itself is real and worth taking seriously."
```

---

# 26. RepetitionWithoutPathologizingRule

This rule fully replaces the previous `ReassuranceLoopRule`.

Returning to the same concern is not automatically a harmful loop.

Canonical distinctions:

```text
same topic != same question
same question != pathological repetition
repetition != compulsion
continued distress != irrationality
need for further understanding != reassurance seeking
```

The domain may revisit a concern and provide reassurance again.

A possible repetitive reassurance pattern may be identified only when several grounded signals coexist, for example:

```text
substantially same unresolved question
+
same evidence state
+
repeated pursuit of impossible certainty
+
temporary relief followed by renewed checking
+
pattern demonstrated across multiple turns
```

Even then, the response must not become punitive or withholding.

Required behavior:

```text
restate what remains supported
+
state what has not changed
+
identify the unresolved uncertainty
+
offer to explore the distress / uncertainty itself
```

The rule must not:

- diagnose OCD;
- label the user as reassurance-seeking;
- refuse ordinary reassurance;
- claim that repetition is harmful without a grounded pattern;
- use safety policy as a conversational punishment.

---

# 27. AgencyWithoutPressureRule

The system may propose action without pressuring the user.

Possible states:

```text
NO_ACTION_NEEDED
ACTION_OPTIONAL
ACTION_USEFUL
ACTION_RECOMMENDED
DOMAIN_ESCALATION_NEEDED
USER_DECISION_REQUIRED
```

The result must preserve the difference.

Canonical distinctions:

```text
option != recommendation
recommendation != adopted action
adopted action != authorized execution
```

The user may legitimately choose:

- to wait;
- to observe;
- to think;
- to talk;
- to act later;
- to take no action.

---

# 28. DirectnessWithoutHarshnessRule

The domain should not hide a grounded judgment behind artificial neutrality.

If the system has a reasonable basis, it may say:

```text
"I think you're reading too much into this particular detail."
```

or:

```text
"Here I do think your concern is justified."
```

provided:

- the basis is explicit or traceable;
- uncertainty remains where relevant;
- the user's emotional experience is not mocked or dismissed;
- no unsupported certainty is added.

This rule exists because truthful support sometimes requires disagreement.

---

# 29. ImmediateRiskEscalationRule

The domain must detect when the concern contains credible immediate risk requiring another domain, safety policy or urgent workflow.

Examples include:

- immediate physical danger;
- severe acute medical warning signs;
- imminent self-harm or harm risk;
- active abuse or violence;
- immediately destructive external action.

This rule must not make Concerns a general crisis classifier.

Required behavior:

```text
credible immediate risk
→ escalate through existing shared/specialized contracts

ordinary distress or fear
→ do not silently escalate
```

Concerns must not create its own clinical or emergency protocol.

---

# 30. Internal semantic model

The canonical reasoning structure is:

```text
concern
├── situation
├── trigger
├── lived experience
│   ├── emotion
│   ├── fear
│   └── need
├── support need
├── reality model
│   ├── facts
│   ├── interpretations
│   ├── hypotheses
│   ├── scenarios
│   ├── evidence
│   └── uncertainty
├── assessment
│   ├── reassurance basis
│   ├── material concern
│   └── risk
├── desired outcome
├── options
└── possible action
```

The model must support partial population.

Missing fields are not failures.

---

# 31. ConcernSupportResult

No new global result contract is required.

Concerns should use the shared `DomainResult` and existing structured reasoning contracts.

The domain-specific structured payload should be capable of representing the equivalent of:

```python
ConcernSupportPayload(
    concern_summary="...",
    lived_experience={...},
    support_need="PERSPECTIVE",
    facts=[],
    interpretations=[],
    hypotheses=[],
    scenarios=[],
    uncertainty=[],
    reassurance_assessment="REASSURANCE_PARTIAL",
    material_concerns=[],
    risk_findings=[],
    open_questions=[],
    desired_outcome=None,
    options=[],
    next_step=None,
    action_state="NO_ACTION_NEEDED",
    supporting_domains=[],
    memory_proposals=[],
    metadata={},
)
```

This is a conceptual domain payload.

If existing shared contracts provide equivalent fields, reuse them rather than creating a parallel type.

---

# 32. Canonical profile

The domain should bind one default specialized cognitive profile:

```text
ConcernSupportProfile
```

The profile should configure reasoning toward:

```text
high contextual sensitivity
high epistemic discipline
high tolerance for uncertainty
high emotional-context awareness
moderate-to-high interpretive openness
low default action pressure
low default alarm
evidence-calibrated reassurance
willingness to state a grounded opinion
targeted questioning
cross-domain awareness
```

The profile must not hard-code a conversational persona.

The profile must not:

- force positivity;
- force neutrality;
- force action;
- force a conclusion;
- force a clinical lens.

---

# 33. Canonical operations — exactly 13

```text
concerns.understand_concern
concerns.infer_support_need
concerns.map_lived_experience
concerns.separate_reality_interpretation
concerns.explore_hypotheses
concerns.calibrate_uncertainty
concerns.evaluate_reassurance
concerns.evaluate_risk
concerns.identify_open_questions
concerns.explore_options
concerns.prepare_next_step
concerns.review_recurring_concern
concerns.prepare_professional_discussion
```

---

# 34. `concerns.understand_concern`

Purpose:

```text
construct the minimal coherent representation of what is troubling the user
```

May identify:

- situation;
- trigger;
- what appears to matter;
- feared meaning;
- relevant context;
- missing material context.

Must not automatically produce advice.

---

# 35. `concerns.infer_support_need`

Purpose:

```text
infer the current conversational support need
```

Output must preserve:

- explicit vs inferred;
- confidence/uncertainty;
- possible mixed need;
- current-turn scope.

No persistence.

---

# 36. `concerns.map_lived_experience`

Purpose:

```text
represent how the concern is affecting the user
```

May structure:

- emotion;
- fear;
- need;
- perceived meaning;
- desired outcome.

It must not infer diagnosis or stable identity.

---

# 37. `concerns.separate_reality_interpretation`

Purpose:

```text
separate observations, experience, interpretations, fears, hypotheses and scenarios
```

This is an internal analytical capability.

It must not imply that emotions are errors.

It must not promote caller-labeled facts without source grounding.

---

# 38. `concerns.explore_hypotheses`

Purpose:

```text
develop plausible explanations when ambiguity matters
```

Requirements:

- preserve alternatives;
- preserve evidence;
- preserve counterevidence;
- preserve uncertainty;
- avoid motive certainty;
- no psychological diagnosis;
- no arbitrary winner.

Reflection shared semantics may be reused through cross-domain composition when appropriate.

---

# 39. `concerns.calibrate_uncertainty`

Purpose:

```text
state what can, cannot and may reasonably be concluded
```

Possible output:

- established;
- reasonably supported;
- plausible;
- possible;
- unresolved;
- unsupported.

Do not invent a numerical probability unless supported by an appropriate domain model/source.

---

# 40. `concerns.evaluate_reassurance`

Purpose:

```text
determine whether the available basis supports reassurance
```

Canonical outputs:

```text
REASSURANCE_SUPPORTED
REASSURANCE_PARTIAL
UNCERTAIN
CONCERN_SUPPORTED
INSUFFICIENT_BASIS
```

The operation should explain what supports the result.

It must not generate a final communication style.

---

# 41. `concerns.evaluate_risk`

Purpose:

```text
identify material or immediate risk when relevant
```

This operation must:

- respect domain limits;
- delegate specialized risk judgment where needed;
- avoid turning mere possibility into risk;
- preserve uncertainty;
- identify immediate escalation if justified.

---

# 42. `concerns.identify_open_questions`

Purpose:

```text
identify unresolved questions that materially affect understanding
```

Each question should include why it matters.

Questions that do not affect the outcome should not be elevated merely because information is incomplete.

---

# 43. `concerns.explore_options`

Purpose:

```text
generate realistic options when the user wants or needs problem solving
```

Each option may preserve:

- expected benefit;
- cost;
- reversibility;
- uncertainty;
- dependencies;
- user control.

No option is automatically adopted.

---

# 44. `concerns.prepare_next_step`

Purpose:

```text
identify one or a small number of useful next steps
```

This is not a generic productivity planner.

It should prefer proportionate action.

Valid output includes:

```text
no next step required
wait and observe
ask one question
seek information
have a conversation
make a decision
consult a professional
perform an authorized domain operation
```

Actual external action remains outside this operation.

---

# 45. `concerns.review_recurring_concern`

Purpose:

```text
compare the current concern with previous grounded iterations
```

It may identify:

- what is genuinely new;
- what is unchanged;
- whether evidence changed;
- whether interpretation changed;
- whether distress changed;
- whether the concern is becoming clearer;
- whether a repeated certainty-seeking pattern is plausibly present.

It must not diagnose.

It must not assume recurrence is maladaptive.

---

# 46. `concerns.prepare_professional_discussion`

Purpose:

```text
prepare a concise, structured discussion for an appropriate professional
```

May be used with:

- Health;
- legal/professional contexts;
- academic support;
- administrative matters;
- other authorized domains.

Preparation is not transmission.

---

# 47. Canonical workflows — exactly 8

```text
Open Concern Conversation
Talk It Through
Reality Check
Reassurance Review
Practical Problem Solving
Decision Under Uncertainty
Recurring Concern Review
Professional Discussion Preparation
```

---

# 48. Open Concern Conversation

Default flexible workflow.

Purpose:

```text
handle a concern without assuming what type of support is needed
```

Possible flow:

```text
understand concern
→ map lived experience
→ infer support need
→ route supporting domains
→ perform only useful reasoning operations
→ return structured support result
```

This workflow may finish without:

- risk analysis;
- options;
- action;
- conclusion.

---

# 49. Talk It Through

Purpose:

```text
support open-ended elaboration of a concern
```

Expected behavior:

- understand;
- reflect meaning;
- explore;
- preserve uncertainty;
- coordinate with Reflection if helpful;
- avoid compulsory solutions.

Successful outcome:

```text
better understood
not necessarily solved
```

---

# 50. Reality Check

Purpose:

```text
compare feared or interpreted meaning with available reality
```

Expected flow:

```text
identify feared conclusion
→ identify facts
→ identify interpretations
→ identify missing information
→ calibrate uncertainty
→ give grounded assessment
```

May produce reassurance.

May also conclude that the concern has a real basis.

---

# 51. Reassurance Review

Purpose:

```text
evaluate whether reassurance is justified and communicate the semantic basis
```

This workflow must not presume reassurance is either good or bad.

Possible outcomes:

```text
supported reassurance
partial reassurance
uncertain
material concern
additional information needed
```

---

# 52. Practical Problem Solving

Purpose:

```text
help the user improve a situation when action is desired
```

Expected flow:

```text
understand problem
→ identify desired outcome
→ identify controllable elements
→ generate options
→ compare practical consequences
→ propose proportionate next step
```

No automatic execution.

---

# 53. Decision Under Uncertainty

Purpose:

```text
help the user make sense of a decision when uncertainty and concern coexist
```

Expected flow:

```text
clarify decision
→ clarify desired outcome / values
→ separate known / unknown
→ explore options
→ identify trade-offs
→ preserve remaining uncertainty
→ provide decision support
```

No automatic personal decision.

---

# 54. Recurring Concern Review

Purpose:

```text
revisit an ongoing concern without treating repetition as pathology
```

Expected flow:

```text
load authorized previous concern context
→ identify changed evidence
→ identify unchanged uncertainty
→ compare interpretations
→ update reassurance/risk assessment
→ consider whether the unresolved issue is informational, practical or emotional
→ continue appropriately
```

---

# 55. Professional Discussion Preparation

Purpose:

```text
turn a concern into a useful professional discussion
```

Output may include:

- concise chronology;
- key facts;
- questions;
- uncertainties;
- current impact;
- documents/sources to bring;
- decisions required.

No external send.

---

# 56. Conversation posture selection

The domain should maintain a structured `response_direction` equivalent to one or more of:

```text
ACKNOWLEDGE
EXPLORE
CLARIFY
GIVE_PERSPECTIVE
REASSURE
NAME_REAL_CONCERN
PROBLEM_SOLVE
SUPPORT_DECISION
SUGGEST_NEXT_STEP
ROUTE_DOMAIN
CONTINUE_OPEN_ENDED
```

This is not a new global contract if existing fields can represent it.

The direction may change turn by turn.

---

# 57. First-response behavior

The first response to a concern is especially important.

Default behavior:

1. identify the core issue;
2. show that the system understood why it matters;
3. give useful perspective immediately if enough context exists;
4. ask a question only if materially necessary;
5. avoid dumping a framework on the user.

Forbidden default shape:

```text
I understand.
Here are 7 steps:
1...
2...
3...
```

unless the user explicitly asked for steps.

The domain must support immediate substantive responses.

---

# 58. Advice behavior

Advice should be:

- contextual;
- proportionate;
- optional unless urgent;
- grounded in the user's objective;
- explicit about trade-offs;
- minimal when one step is enough.

The system must not confuse:

```text
being useful
```

with:

```text
producing many suggestions
```

---

# 59. No forced positive reframing

The system must not automatically convert every negative interpretation into an optimistic one.

Forbidden pattern:

```text
negative event
→ generate positive alternative
→ declare concern resolved
```

Alternative explanations are useful only when plausible and relevant.

The system may say:

```text
"There are less negative explanations."
```

without saying:

```text
"Therefore the positive explanation is true."
```

---

# 60. No forced cognitive correction

The domain must not assume:

```text
distress = distorted thought
```

A concern may be:

- accurate;
- partly accurate;
- inaccurate;
- unresolved;
- emotionally disproportionate but factually grounded;
- emotionally understandable under uncertainty.

The domain is not built around detecting cognitive distortions.

---

# 61. Distinguishing concern from reflection

Primary Concerns when:

```text
there is an active worry/problem/fear
+
the user needs support around what it means or what to do
```

Primary Reflection when:

```text
the main task is broader self-exploration, beliefs, identity narrative,
values, ambivalence or open-ended personal meaning
```

Composition example:

```text
Concern:
"Why am I so affected by this?"
↓
Concerns primary
Reflection supporting
```

or:

```text
Reflection:
"What does this pattern say about what I value in friendship?"
↓
Reflection primary
Concerns supporting if active distress is central
```

No direct dependency.

Use shared cross-domain composition.

---

# 62. Relationships boundary

When the concern depends on another person's behavior, history or relationship pattern:

```text
Relationships may become primary or supporting.
```

Concerns may reason about:

- the user's fear;
- perceived meaning;
- uncertainty;
- reassurance;
- support need;
- possible action.

Relationships owns domain-specific semantics such as:

- relationship events;
- boundaries;
- patterns;
- communication dynamics;
- relational decisions.

Third-party motives remain hypotheses.

No third-party diagnosis.

---

# 63. Health boundary

If the core issue is medical, medication-related, symptoms, treatment or clinical risk:

```text
Health should provide medical semantics.
Concerns may provide support around worry and uncertainty.
```

Concerns must not:

- diagnose;
- determine medical urgency from generic heuristics when Health can resolve it;
- minimize red flags;
- inflate benign symptoms into serious conditions.

Composition example:

```text
symptom worry
↓
Health: clinical evidence / red flags / next medical step
+
Concerns: fear / uncertainty / reassurance / support need
```

---

# 64. Life Plan boundary

If the concern is primarily about long-term direction, career, family project or major life choice:

```text
Life Plan may become primary.
Concerns supports uncertainty, fear and decision pressure.
```

---

# 65. Project / University / Oppositions boundary

A concern about:

- code;
- project failures;
- exams;
- grades;
- academic deadlines;
- opposition calls;
- study performance;

should use the specialized domain for factual/operational semantics.

Concerns should not recreate those rules.

It supports:

- interpretation;
- worry;
- uncertainty;
- perspective;
- action pressure;
- reassurance.

---

# 66. General Domain boundary

General remains fallback.

Concerns must not create its own generic factual engine.

Where specialization is insufficient:

```text
Concerns + General
```

may continue with a limited result or ask a useful question.

---

# 67. Source and provenance model

Decision-relevant claims must preserve provenance where available.

Possible sources:

```text
user_message
conversation
note
journal_entry
memory_entry
event
goal
decision
domain_result
external_source
```

Canonical distinctions:

```text
provenance != truth
user statement != independently verified fact
memory != current truth
model inference != user statement
interpretation != observation
third-party account != verified motive
```

Caller-provided labels such as:

```text
fact=true
confirmed=true
risk=high
```

do not bypass shared source validation.

---

# 68. Evidence states

The domain must preserve at least the shared equivalents of:

```text
absent
grounded
ungrounded
malformed
conflicting
temporally_ambiguous
unknown
duplicate
```

Malformed evidence must not increase:

- certainty;
- reassurance;
- risk;
- hypothesis support.

Duplicates must not inflate support.

---

# 69. Temporal semantics

Concerns often evolve across time.

The domain may compare:

- repeated concerns;
- new evidence;
- changed interpretations;
- changed emotional impact;
- resolved questions;
- persistent unknowns;
- changed desired outcomes.

It must reuse shared temporal contracts.

Required distinctions:

```text
later input != later event
newer memory != truer fact
same concern twice != worsening
repeated worry != persistent disorder
elapsed time != proof of significance
```

---

# 70. Recurrence semantics

A recurring concern may be meaningfully different because:

- new facts appeared;
- no expected event occurred;
- the user's interpretation changed;
- emotional impact increased;
- circumstances changed;
- another domain produced new information.

`review_recurring_concern` must compare actual state, not merely topic labels.

---

# 71. Memory policy

Concerns has high sensitivity because worries may contain:

- health information;
- relationship information;
- fears;
- vulnerabilities;
- private interpretations;
- family information;
- identity-related concerns.

The domain may produce memory proposals through shared contracts.

It must not silently persist:

```text
fear
support need
inferred emotional pattern
recurring concern pattern
psychological interpretation
risk interpretation
third-party motive
```

Durable user facts or preferences require the applicable shared confirmation/persistence policy.

Canonical invariant:

```text
conversation state != semantic memory
```

---

# 72. Temporary concern state

A concern may remain in session/episodic state without becoming durable semantic memory.

Useful temporary state includes:

- current concern;
- unresolved question;
- current support need;
- current interpretation;
- current action under consideration;
- current reassurance assessment.

Temporary concern state should expire or follow shared session-retention rules.

---

# 73. Permissions

Concerns is a high-sensitivity personal domain.

Canonical permission intentions:

```text
high sensitivity
cross-domain access only through authorized projections
no diagnosis
no third-party diagnosis
no automatic personal decisions
no automatic external communication
no automatic semantic-memory persistence
no autonomous monitoring by default
no hidden risk escalation
no unrestricted external research
```

Most restrictive permission wins under composition.

Unknown authorization fails closed.

Malformed authorization fails closed.

Where boolean authorization is required:

```text
True authorizes
"true" does not
1 does not
```

unless the shared contract explicitly defines otherwise.

---

# 74. External-action boundary

Concerns operations may prepare, recommend or propose.

They must not directly:

- send a message;
- contact another person;
- contact a professional;
- modify a calendar;
- create a purchase;
- submit a form;
- make an appointment;
- publish anything;
- modify another domain's store;
- write semantic memory;
- start continuous monitoring;
- execute a personal decision.

Canonical invariant:

```text
PREPARE != SEND
PROPOSE != EXECUTE
RECOMMEND != DECIDE
```

---

# 75. Monitoring boundary

The previous design contained a `generate_monitoring_plan` operation.

The redesigned domain does not make monitoring a canonical operation.

Monitoring may be useful in specific domains, but:

```text
concern
!=
thing that should automatically be monitored
```

If monitoring is genuinely appropriate:

- the specialized domain should define what matters;
- shared scheduling/automation infrastructure should handle execution;
- authorization is required where applicable.

---

# 76. Professional escalation

Professional consultation may be suggested when:

- specialized knowledge is required;
- risk cannot be resolved conversationally;
- the issue is materially impairing and relevant professional support exists;
- the user explicitly wants preparation;
- another domain determines consultation is appropriate.

Concerns should not use "talk to a professional" as a generic escape hatch.

If the system can still provide useful analysis or support, it should do so within its limits.

---

# 77. Safety without defensive overreach

Safety behavior must be proportionate.

The system must not:

- convert sadness into suicide screening automatically;
- convert health worry into emergency advice automatically;
- convert relationship conflict into abuse classification automatically;
- convert repeated worry into psychiatric interpretation automatically;
- flood ordinary concerns with warnings.

Where a credible safety signal exists, use the appropriate shared policy.

Canonical invariant:

```text
safety != defensive conversational withdrawal
```

---

# 78. Presentation policy

Concerns presentation should preserve semantic priorities without defining a fixed persona.

Default content-order preferences:

1. address the actual concern rather than reciting policy;
2. acknowledge relevant lived impact where useful;
3. give substantive perspective early when enough context exists;
4. expose fact/interpretation distinctions only to the degree useful;
5. make uncertainty visible without drowning the answer in caveats;
6. present reassurance clearly when justified;
7. present genuine concern clearly when justified;
8. keep action proportional;
9. avoid default checklist formatting for emotional discussion;
10. avoid clinical/therapeutic jargon unless context requires it.

The exact tone, warmth, register and verbosity remain shared presentation/communication-profile concerns.

---

# 79. Structured response preservation

Regardless of surface rendering, the underlying result should preserve:

- what the system treated as fact;
- what it treated as interpretation;
- what it treated as hypothesis;
- what it treated as fear/scenario;
- what remained uncertain;
- what reassurance basis existed;
- what material concerns existed;
- what cross-domain evidence was used;
- what action state was produced;
- what memory proposal was made;
- which rules fired;
- which permissions applied.

This enables later Phase 11 response rendering without semantic drift.

---

# 80. Trace requirements

Concerns trace must be able to explain:

```text
why Concerns was selected
which supporting domains participated
what support need was inferred
whether it was explicit or inferred
which resources were used
which facts were considered
which interpretations/hypotheses were preserved
what uncertainty remained
whether reassurance was supported
whether material concern was supported
whether risk escalation occurred
why a question was asked
why action was or was not proposed
what memory proposal was produced
what permissions constrained the result
```

No hidden personality inference is required.

No private chain-of-thought storage is required.

Structured reasoning trace is sufficient.

---

# 81. Determinism and order invariance

Semantic outputs must not depend on arbitrary input order where evidence is equivalent.

Required areas:

- fact aggregation;
- evidence aggregation;
- duplicate evidence;
- hypothesis sets;
- reassurance assessment;
- risk findings;
- open questions;
- recurring concern comparison.

No first-wins or last-wins semantic resolution.

Equal-authority conflict remains conflict unless a shared deterministic rule resolves it.

---

# 82. Malformed-input behavior

Malformed data must fail closed for certainty-changing semantics.

Examples:

```text
malformed fact
→ cannot increase reassurance or concern certainty

malformed date
→ cannot establish temporal progression

malformed risk level
→ cannot trigger high-risk state

malformed authorization
→ cannot authorize operation

malformed support_need
→ UNKNOWN/validation failure, not arbitrary fallback
```

The domain should prefer a limited result over silent coercion.

---

# 83. Cross-domain composition

Recommended composition precedence:

```text
specialized factual/risk domain
>
Concerns support semantics
>
Reflection open-ended meaning semantics
>
General fallback
```

This is not a global hard-coded precedence if shared composition contracts already define precedence.

The intent is:

- Health owns medical meaning;
- Relationships owns relationship-specific semantics;
- University/Oppositions own academic semantics;
- Life Plan owns long-term planning;
- Concerns owns concern support;
- Reflection owns broader reflective exploration;
- General fills remaining gaps.

No domain may silently overwrite another domain's grounded fact.

---

# 84. Cross-domain example — relationship worry

Input:

```text
"They haven't suggested meeting for two weeks and I feel like I'm becoming just another friend."
```

Desired semantic behavior:

```text
Relationships:
- relevant relationship events / pattern context

Concerns:
- lived impact
- feared meaning
- support need
- reality check
- reassurance or material concern
- options if wanted

Reflection:
- deeper meaning only if useful
```

Important result:

```text
observable decrease in initiative
!=
proof of loss of importance

user's hurt
=
real lived experience

possible relational change
=
may remain a legitimate concern
```

---

# 85. Cross-domain example — health worry

Input:

```text
"I've had this symptom and I'm scared it means something serious."
```

Desired semantic behavior:

```text
Health:
- symptom semantics
- red flags
- medical next step

Concerns:
- feared meaning
- uncertainty
- reassurance based on Health result
- support around waiting/next step
```

Concerns must not invent medical probabilities.

---

# 86. Cross-domain example — academic worry

Input:

```text
"I failed one exam and now I feel like I'm going to ruin the whole year."
```

Desired semantic behavior:

```text
University:
- actual academic consequences

Concerns:
- separate current result from projected catastrophe
- validate impact
- reality check
- practical next step if desired
```

No generic "failure is a learning opportunity" requirement.

---

# 87. Cross-domain example — vague “rayada”

Input:

```text
"I don't know, this whole thing is really messing with my head."
```

Desired behavior:

```text
do not demand immediate categorization
do not produce risk matrix
identify what "this whole thing" refers to from session context
respond to emotional meaning
ask one clarifying question only if necessary
allow open conversation
```

---

# 88. Anti-patterns

The domain must explicitly reject these behaviors.

## 88.1 Premature checklist

```text
User: "I'm worried."
System: "Here are 10 things you can do..."
```

## 88.2 Therapy-script reflex

```text
"What emotion is coming up for you?"
"Try grounding."
"Take a deep breath."
```

when not contextually useful or requested.

## 88.3 Reassurance refusal

```text
"I can't reassure you because that would reinforce the cycle."
```

without a grounded pattern and without addressing the actual concern.

## 88.4 Catastrophic caveat stacking

```text
"This is probably fine, BUT..."
```

followed by a long list of remote dangers.

## 88.5 Invalidating rationalization

```text
"Maybe they're just busy."
```

used as if it disproves a meaningful pattern.

## 88.6 Agreement as empathy

```text
"You are absolutely right about their motive."
```

when motive is unknown.

## 88.7 Forced action

```text
"You need to confront them now."
```

where action is optional.

## 88.8 Forced closure

```text
"So the conclusion is..."
```

when the concern remains genuinely unresolved.

## 88.9 Pathologizing recurrence

```text
"You're asking again because of anxiety/OCD."
```

without diagnostic authority and grounded evidence.

## 88.10 Over-defensive safety response

The system stops engaging with the concern because a sensitive topic appeared.

---

# 89. Required user-facing capabilities

The domain must be able to support interactions equivalent to:

```text
"Listen to me."
"Help me understand why this bothers me."
"Tell me what you think."
"Do you think I'm exaggerating?"
"Is there actually reason to worry?"
"Can you reassure me?"
"What else could explain this?"
"What am I missing?"
"What can I do?"
"What would be a reasonable next step?"
"Should I wait?"
"I know we discussed this already, but I'm still thinking about it."
"Help me prepare to talk to someone about it."
```

No single workflow is mandatory for all.

---

# 90. Memory/update examples

Allowed:

```text
"I have a concern about X in this session."
→ session state

"User explicitly confirms this is an ongoing priority they want remembered."
→ memory proposal through shared contract
```

Not allowed:

```text
"User asked for reassurance three times."
→ persistent anxiety trait

"User repeatedly worries about relationships."
→ stable attachment/mental-health inference

"User fears X."
→ durable semantic fact without confirmation
```

---

# 91. Catalog integration

`catalog.py` must define exactly:

```text
17 entities
10 resources
14 rules
13 operations
8 workflows
```

Those counts become Phase 10.25 acceptance criteria after this redesign is frozen.

Any prior 10.25 count from the old roadmap section is superseded.

The roadmap and requirements matrix must be updated before implementation so they do not contain two competing canonical catalogs.

---

# 92. Definition requirements

`definition.py` must expose one canonical `DomainDefinition` for:

```text
domain:concerns
```

It must reference:

- `ConcernSupportProfile`;
- canonical catalog members;
- shared dependencies;
- capabilities;
- permissions;
- presentation policy;
- validators.

Suggested capabilities:

```text
concern_understanding
support_need_resolution
reality_check
evidence_calibrated_reassurance
uncertainty_support
risk_calibration
problem_solving
decision_support
recurring_concern_review
professional_discussion_preparation
```

---

# 93. Bootstrap requirements

Bootstrap must:

1. validate all Concerns components before mutation;
2. detect deterministic registry collisions;
3. register atomically;
4. preserve previous shared state on failure;
5. avoid import-time registration side effects;
6. support fresh-interpreter import;
7. use existing rollback patterns.

No partial domain installation.

---

# 94. Integration requirements

`integration.py` must use shared composition infrastructure.

Required cases:

```text
General + Concerns
Relationships + Concerns
Health + Concerns
Reflection + Concerns
University + Concerns
Oppositions + Concerns
Life Plan + Concerns
Project + Concerns
```

Not every combination needs specialized bespoke logic.

The tests must prove that cross-domain projection and permissions remain intact.

---

# 95. Operation boundaries

All operations are analytical or preparatory.

No operation may:

- execute external communication;
- mutate a user decision;
- persist memory directly;
- modify other domain state;
- perform a medical/legal/financial act;
- bypass Agent Runtime / shared execution contracts.

Operations should return structured results suitable for later rendering.

---

# 96. Workflow boundaries

All workflows use the shared workflow runtime.

No Concerns-specific:

```text
WorkflowEngine
ConversationLoop
ConcernAgent
SupportAgent
```

may be created.

A workflow may suspend or complete with unresolved uncertainty.

---

# 97. Validation requirements

The Phase 10 validation pipeline must verify:

```text
manifest
contracts
catalog integrity
profile
rules
operations
workflows
permissions
presentation
cross-domain composition
memory boundary
trace
rollback
fresh import
serialization
no fragmentation
```

Semantic validation must go beyond name/count tests.

---

# 98. Adversarial test matrix — understanding

Test at least:

```text
short vague concern with sufficient session context
short vague concern without sufficient context
explicit request for advice
explicit request for no advice
explicit request for opinion
explicit request for reassurance
explicit request merely to talk
mixed support need
support need changes mid-session
```

Verify:

- no unnecessary interrogation;
- explicit current intent wins;
- no default action plan.

---

# 99. Adversarial test matrix — validation vs truth

Cases:

```text
strong emotion + weak evidence
weak emotion + strong evidence
valid experience + unsupported interpretation
valid experience + supported interpretation
conflicting evidence
missing evidence
malformed evidence
duplicate evidence
```

Verify:

```text
emotion remains valid
facts remain facts
interpretation remains interpretation
duplicates do not inflate certainty
malformed evidence does not increase certainty
```

---

# 100. Adversarial test matrix — reassurance

Cases:

```text
clear reassuring evidence
partial reassuring evidence
material concern
true uncertainty
missing information
repeated reassurance request
reassurance request after new evidence
same request with no new evidence
```

Verify:

- reassurance can be returned repeatedly where appropriate;
- no false certainty;
- no automatic refusal;
- recurrence is not automatically pathologized;
- material concern is not minimized.

---

# 101. Adversarial test matrix — catastrophic escalation

Cases:

```text
remote possibility only
ambiguous event
single negative event
real repeated negative pattern
medical worry with Health reassurance
medical worry with Health red flag
```

Verify:

- remote possibility is not promoted;
- real pattern is not erased;
- Health semantics dominate medical judgment;
- caveats remain proportional.

---

# 102. Adversarial test matrix — questions

Cases:

```text
answerable without question
one missing fact changes interpretation
missing fact does not change likely answer
many missing details but only one material
user explicitly asks for immediate opinion
```

Verify:

- only material questions are asked;
- a useful partial answer may precede/replace clarification;
- no interview ritual.

---

# 103. Adversarial test matrix — action

Cases:

```text
no action needed
optional action
useful action
recommended action
user wants to wait
user wants one next step
user asks system to decide for them
```

Verify:

- action state remains explicit;
- user agency preserved;
- candidate != adopted;
- no external execution.

---

# 104. Adversarial test matrix — recurrence

Cases:

```text
same topic, different question
same question, new evidence
same question, same evidence
same concern with changed emotional impact
multi-turn pursuit of impossible certainty
single repeated reassurance request
```

Verify:

- no diagnosis;
- no automatic "loop" label;
- repeated reassurance remains possible;
- pattern detection requires multiple grounded signals;
- user is not punished for repetition.

---

# 105. Adversarial test matrix — directness

Cases:

```text
user is likely over-interpreting one detail
user has a materially grounded concern
evidence genuinely balanced
user asks "tell me what you think"
```

Verify:

- system can give a grounded opinion;
- empathy does not require agreement;
- neutrality is not forced;
- uncertainty survives.

---

# 106. Adversarial test matrix — cross-domain

Test:

```text
Relationships primary + Concerns supporting
Concerns primary + Reflection supporting
Health primary + Concerns supporting
University primary + Concerns supporting
Life Plan primary + Concerns supporting
```

Verify:

- no private store access;
- shared projection only;
- provenance preserved;
- most restrictive permission wins;
- no domain silently overwrites another's grounded fact.

---

# 107. Adversarial test matrix — memory

Cases:

```text
one concern mention
repeated concern in one session
repeated concern across sessions
explicit user confirmation for persistence
model-inferred emotional pattern
third-party motive inference
```

Verify:

- no direct semantic persistence;
- inference is not durable fact;
- explicit confirmation uses shared mechanism;
- session state remains distinct.

---

# 108. Adversarial test matrix — malformed inputs

Test:

```text
truthy authorization strings
numeric authorization
malformed dates
malformed support_need
malformed risk
malformed evidence maps
duplicate semantic records with conflicting IDs
```

Fail closed.

No accidental authorization.

No silent certainty increase.

---

# 109. Deterministic tests

Run input permutations for:

- facts;
- evidence;
- hypotheses;
- reassurance basis;
- risk findings;
- open questions.

Equivalent semantic sets must produce equivalent semantic decisions.

---

# 110. Rollback tests

Use counting/spying registries and independent pre-existing records.

Prove:

```text
collision before registration
→ zero mutation

mid-bootstrap failure
→ previous shared state restored

workflow registration failure
→ operations/rules/resources restored

permission failure
→ no partially active Concerns domain
```

---

# 111. Fresh import test

Required:

```bash
.venv/bin/python - <<'PY'
import cmm.domains.concerns
print("fresh_import=OK")
PY
```

Import must not:

- mutate registries;
- read unauthorized user data;
- execute workflows;
- make model calls;
- write files;
- perform network requests.

---

# 112. Non-goals

Phase 10.25 does not implement:

- UI;
- mobile app;
- voice interface;
- model routing;
- provider selection;
- ChatGPT/Claude personality cloning;
- therapy;
- diagnosis;
- OCD detection;
- anxiety-disorder detection;
- emotion classifier service;
- sentiment provider;
- crisis service;
- external messaging;
- reminders;
- scheduled monitoring;
- calendar writes;
- Notion writes;
- professional appointment booking;
- semantic-memory backend;
- new Knowledge Graph;
- new temporal engine;
- new planner;
- new agent;
- new workflow runtime;
- autonomous personal decision making.

---

# 113. Documentation requirements

Create/update:

```text
docs/superpowers/specs/2026-08-21-concerns-domain-design.md
docs/reference/concerns-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
```

The roadmap 10.25 section must be replaced, not merely appended.

The requirements matrix must update `DP-025` / `AT-DP-025` to the redesigned semantics.

The old catalog must not remain as a competing acceptance source.

---

# 114. Redesigned DP-025

Canonical acceptance intent:

```text
DP-025 — Concern Support

CMM OS must be able to support a user through a problem, worry or fear by:

- understanding the situation and its lived significance;
- resolving or cautiously inferring the current support need;
- preserving emotional experience without promoting interpretation to fact;
- distinguishing reality, interpretation, hypothesis, fear, scenario and uncertainty when relevant;
- giving evidence-calibrated reassurance when justified;
- acknowledging material concern when justified;
- avoiding catastrophic escalation and false reassurance;
- revisiting recurring concerns without automatically pathologizing repetition;
- asking only materially useful questions;
- supporting action and decisions without forcing them;
- coordinating with specialized domains for factual/risk semantics;
- preserving provenance, permissions, uncertainty and memory boundaries.
```

Canonical acceptance identifier remains:

```text
DP-025
AT-DP-025
```

This redesigned DP-025 supersedes the previous narrow risk/scenario formulation.

---

# 115. AT-DP-025 minimum end-to-end scenario

The acceptance test should prove at least this sequence:

```text
1. User presents an emotionally meaningful ambiguous concern.
2. Domain Resolver selects Concerns and one relevant supporting domain.
3. Concerns identifies the actual issue without forcing an action plan.
4. The user's emotional experience is represented as valid experience.
5. One external interpretation remains unverified.
6. The system identifies the current support need.
7. It provides an initial substantive response.
8. A materially relevant question is asked only if needed.
9. New information is incorporated.
10. Facts and interpretations remain distinct.
11. Multiple hypotheses remain where appropriate.
12. Reassurance is returned because the evidence supports partial reassurance.
13. One real concern remains acknowledged.
14. No absolute certainty is invented.
15. The user revisits the same worry.
16. The system responds again without labeling the repetition pathological.
17. The evidence state is compared with the prior turn.
18. No new risk is invented from repetition.
19. The user asks what they can do.
20. Options are generated.
21. One proportionate next step is proposed.
22. The next step remains a proposal, not an adopted decision.
23. No external action occurs.
24. No sensitive inference is silently persisted.
25. Domain trace records support need, evidence, uncertainty, reassurance and action state.
```

---

# 116. Required behavioral invariants

Implementation must prove:

```text
emotion != fact
interpretation != fact
fear != prediction
possibility != probability
uncertainty != danger
reassurance != false certainty
validation != agreement
empathy != truth inflation
directness != harshness
repetition != pathology
concern != disorder
support != therapy
option != decision
recommendation != authorization
preparation != external action
session state != semantic memory
```

---

# 117. Self-audit requirements

Before declaring Phase 10.25 ready for independent audit, inspect for:

- old `ReassuranceLoopRule` semantics accidentally retained;
- action-first default behavior;
- mandatory monitoring plan behavior;
- default risk-matrix behavior;
- reassurance blocked merely because it was previously provided;
- recurrence pathologized;
- emotion converted into fact;
- interpretation converted into fact;
- user-provided `fact=true` trusted without grounding;
- possible scenario promoted to likely outcome;
- negative possibility listed merely as a safety caveat;
- genuine negative evidence minimized by positive alternatives;
- support need persisted as personality preference;
- user explicitly asks for no advice but receives action plan;
- user explicitly asks for opinion but receives only neutral possibilities;
- unnecessary clarifying questions;
- every workflow forced to reach a conclusion;
- every workflow forced to produce action;
- third-party motive presented as fact;
- medical risk assessed without Health support where required;
- psychological diagnosis or OCD/anxiety-loop labeling;
- direct external communication;
- direct calendar/task/Notion writes;
- direct memory persistence;
- hidden domain-store access;
- shared-contract duplication;
- import-time side effects;
- partial registration;
- rollback defects;
- order-dependent semantic result;
- malformed permission fail-open;
- malformed evidence increasing certainty;
- duplicate evidence inflation.

No required behavior may be postponed through placeholder markers or deferred implementation notes.

---

# 118. Verification expectations

At implementation completion, run at least:

```text
focused Concerns tests
relevant Reflection regressions
relevant Relationships regressions
relevant Health regressions
relevant General regressions
all domain tests
global pytest suite
Ruff on changed/new Python
Ruff with repository target version
compileall
dependency-direction tests
fresh-interpreter import
git diff --check
git diff --cached --check before commit
```

Do not hard-code historical test totals as acceptance criteria.

---

# 119. Independent-audit focus

The independent audit must attack semantics, not only names/counts.

Minimum independent gates:

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
ROLLBACK_GATE
INPUT_NON_MUTATION_GATE
STRICT_JSON_GATE
PACKAGE_BOUNDARY_GATE
```

Audit findings should be classified using the existing Phase 10 audit severity conventions.

---

# 120. Acceptance criteria

Phase 10.25 is acceptable when:

- `domain:concerns` exists as one complete canonical Domain Pack;
- the package follows the shared hardened 14-module boundary;
- exactly 17 canonical entities exist;
- exactly 10 canonical resources exist;
- exactly 14 canonical rules exist;
- exactly 13 canonical operations exist;
- exactly 8 canonical workflows exist;
- `catalog.py` is the single source of truth;
- `ConcernSupportProfile` is bound through shared profile infrastructure;
- shared contracts and registries are reused;
- no parallel planner, agent, memory, store, workflow or permission infrastructure exists;
- understanding precedes intervention unless direct action is explicitly requested and context is sufficient;
- emotional experience can be validated without becoming external fact;
- support need is explicit/inferred/revisable and never a diagnosis;
- questions are materially useful rather than ritual;
- uncertainty is preserved;
- reassurance is allowed when supported;
- reassurance never requires invented certainty;
- real concerns are not minimized;
- catastrophic escalation is prevented;
- recurrence is not automatically pathologized;
- repeated reassurance remains possible;
- any repeated certainty-seeking pattern requires multiple grounded signals;
- the system can give a grounded opinion and disagree respectfully;
- no action is forced;
- no personal decision is adopted automatically;
- no external action occurs directly;
- no sensitive concern state is silently persisted;
- cross-domain composition works with at least General, Reflection, Relationships and Health;
- domain-specific facts/risk semantics remain owned by specialized domains;
- source provenance is preserved;
- duplicate/malformed evidence cannot inflate certainty;
- permissions fail closed;
- bootstrap is atomic;
- rollback is complete;
- fresh import is side-effect free;
- focused and global suites are green;
- documentation and DP-025 matrix are updated;
- an independent audit produces no unresolved blocking finding.

---

# 121. Phase outcome

After Phase 10.25, CMM OS should be able to handle:

```text
a problem
a fear
a "rayada"
an ambiguous event
a repeated worry
a difficult uncertainty
a request for reassurance
a request for perspective
a decision under pressure
a need simply to talk
```

without collapsing all of them into:

```text
risk analysis
coping plan
clinical framing
reassurance refusal
automatic action
```

The intended behavior is:

```text
understand me
↓
understand what matters here
↓
think with me
↓
tell me what you genuinely think
↓
keep facts and interpretations straight
↓
reassure me when there is a basis
↓
tell me when there really is a problem
↓
do not invent certainty
↓
do not alarm me unnecessarily
↓
do not pathologize me for coming back to the same thing
↓
help me act if action is useful
↓
or simply keep talking if that is what I need
```

That is the canonical purpose of the redesigned Concerns Domain.
