# Phase 10.24 — Reflection Domain — Frozen Design

Date: 2026-08-20
Status: **FROZEN DESIGN — implementation not started**

## 1. Purpose

Phase 10.24 adds the `domain:reflection` specialization to CMM OS.

The Reflection Domain exists to support complex reflection, hypothesis
exploration, organization of ideas, longitudinal comparison, decision review,
and preservation of genuine ambivalence without forcing a single conclusion.

The domain is not:

- a separate assistant;
- a second reasoning engine;
- a diagnostic system;
- a personality classifier;
- an identity classifier;
- a semantic-memory writer;
- an autonomous personal decision maker.

It is a Domain Pack over the shared Phase 10 infrastructure.

---

# 2. Canonical source requirements

The roadmap defines Phase 10.24 as:

```text
Objective:
Specialize CMM OS to develop complex reflections, explore hypotheses,
organize ideas and preserve ambivalence without requiring a unique conclusion.
```

DP-024 strengthens that objective:

```text
Reflection:
open-ended analysis,
prudent hypotheses,
interest mapping grounded in sources,
confirmed persistence.
```

Canonical acceptance identifier:

```text
DP-024
AT-DP-024
```

Implementation must satisfy both the roadmap package contract and DP-024.

---

# 3. Architectural decision

Implement exactly one specialized package:

```text
cmm/domains/reflection/
```

with the same 14-module package boundary established by the hardened Phase 10
Domain Packs:

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

No additional Reflection production module is permitted without an explicit
design change.

`catalog.py` is the single source of truth for canonical Reflection catalog
members.

The implementation must reuse shared contracts and infrastructure for:

- domain definition;
- domain registration;
- cognitive profiles;
- reasoning rules;
- permissions;
- operations;
- workflows;
- memory proposals;
- trace;
- cross-domain composition;
- resource handling;
- presentation;
- integration and rollback.

Do not create parallel Reflection infrastructure.

---

# 4. Domain identity and namespace

Canonical domain identifier:

```text
domain:reflection
```

Canonical domain slug:

```text
reflection
```

Therefore every canonical operation identifier must use:

```text
reflection.*
```

This is both the roadmap namespace and the namespace required by the shared
`DomainOperationDefinition` slug contract.

No `reflections.*` namespace.

No alias namespace unless the existing shared framework explicitly requires
one.

---

# 5. Canonical catalog

## 5.1 Entities — exactly 11

```text
reflection
belief
value
question
hypothesis
emotion
need
conflict
identity_narrative
decision
uncertainty
```

## 5.2 Resources — exactly 9

```text
user_message
conversation
note
journal_entry
memory_entry
relationship_event
life_event
goal
decision
```

## 5.3 Rules — exactly 6

```text
MultipleHypothesesRule
PreserveAmbivalenceRule
BeliefEvidenceRule
OpenQuestionRule
ReflectionTemporalEvolutionRule
NoForcedConclusionRule
```

## 5.4 Operations — exactly 9

```text
reflection.structure_reflection
reflection.extract_beliefs
reflection.compare_versions
reflection.identify_open_questions
reflection.generate_hypotheses
reflection.build_personal_timeline
reflection.prepare_notion_entry
reflection.generate_summary
reflection.review_decision
```

## 5.5 Workflows — exactly 6

```text
Structured Reflection
Belief Review
Personal Question Exploration
Decision Reflection
Identity Narrative Review
Longitudinal Reflection Review
```

Catalog counts are acceptance criteria.

---

# 6. Core semantic model

Reflection must preserve distinct epistemic levels.

Canonical reasoning pipeline:

```text
source / evidence
→ observation
→ interpretation
→ belief
→ hypothesis
→ counter-hypothesis
→ uncertainty
→ open question
```

These states are not interchangeable.

Mandatory distinctions:

```text
observation != interpretation
interpretation != belief
belief != fact
hypothesis != fact
plausibility != certainty
emotion != external evidence
experience != universal rule
memory != current truth
repetition != proof
correlation != cause
absence of contradiction != proof
```

The domain must preserve the level at which each statement exists.

---

# 7. Open-ended analysis

Reflection must be able to complete successfully without converging on one
answer.

A valid result may contain:

```text
multiple hypotheses
unresolved tension
ambivalence
open questions
uncertain causal explanation
contradictory evidence
partial timeline
no recommendation
no conclusion
```

A workflow is not incomplete merely because it has no definitive conclusion.

The system must not invent certainty to make an output appear finished.

Canonical invariant:

```text
reflection completed != conclusion reached
```

---

# 8. Multiple hypotheses

`MultipleHypothesesRule` must preserve more than one plausible explanation
when the available evidence supports multiple interpretations.

Required behavior:

- preserve distinct hypotheses;
- preserve evidence for each;
- preserve evidence against each where available;
- preserve unknowns;
- avoid arbitrary winner selection;
- avoid first-input-wins semantics;
- avoid converting the highest-scored hypothesis into fact;
- permit "insufficient basis to rank" as a valid state.

A hypothesis may become relatively stronger than another only when the
evidence used for that comparison is explicit and traceable.

No opaque scalar may silently collapse multiple hypotheses unless such a
scoring policy already exists in shared infrastructure and is explicitly
traceable.

---

# 9. Preserve ambivalence

`PreserveAmbivalenceRule` must treat ambivalence as potentially valid
information.

Examples:

```text
"I want this and I also want distance."
"I believe X but part of me still doubts it."
"I am relieved and sad at the same time."
```

The rule must not force these into:

```text
one true emotion
one true need
one true belief
one final interpretation
```

Canonical invariant:

```text
ambivalence != inconsistency that must be eliminated
```

Where different positions depend on different contexts or times, those
conditions should remain explicit.

---

# 10. Belief / evidence separation

`BeliefEvidenceRule` must preserve five canonical dimensions:

```text
belief
evidence
counterevidence
experience
interpretation
```

The implementation must not silently promote:

```text
experience → general evidence
interpretation → observed fact
belief → verified fact
memory → verified current fact
```

Where the evidence basis is missing, malformed, unsupported, contradictory,
or only interpretive, that limitation must remain visible.

---

# 11. Open questions

`OpenQuestionRule` preserves questions that cannot be resolved from the
available basis.

A question may remain open because:

```text
evidence is missing
evidence conflicts
the relevant person has not stated their motive
the event is inherently ambiguous
the question concerns future behavior
the evidence is only interpretive
the source basis is too weak
the timeline is incomplete
```

The rule must not answer an open question merely because one hypothesis sounds
plausible.

Canonical invariant:

```text
open question != failed reasoning
```

---

# 12. Temporal evolution

`ReflectionTemporalEvolutionRule` compares how an idea, belief, value,
hypothesis, decision, uncertainty, or identity narrative changes over time.

The rule must preserve:

```text
version
observed_at / effective time where available
source
what changed
what remained stable
what is uncertain
contradictions
whether the comparison is actually temporally ordered
```

Required distinctions:

```text
current != newest-looking ungrounded record
changed != contradicted
rephrased != substantively changed
repeated != persistent
```

A longitudinal conclusion requires sufficiently grounded temporal evidence.

Malformed or incomparable dates must not establish direction.

Equal timestamps must not manufacture evolution.

Input order must not establish chronology.

---

# 13. No forced conclusion

`NoForcedConclusionRule` is a first-class Reflection safety rule.

It must permit successful completion states such as:

```text
structured but unresolved
multiple plausible explanations
ambivalence preserved
open question retained
decision not yet made
identity narrative not stabilized
insufficient basis
```

The rule must prevent:

```text
"therefore this proves..."
"the real reason is..."
"you are definitely..."
"the answer is clearly..."
```

when the evidence does not justify those claims.

---

# 14. DP-024 prudent hypotheses

DP-024 requires prudent hypotheses.

A prudent hypothesis must preserve:

```text
hypothesis status
source basis
supporting evidence
counterevidence
uncertainty
alternative explanations
scope
temporal grounding when relevant
```

A hypothesis must not be presented as diagnosis, identity fact, or established
cause.

Canonical invariant:

```text
psychological hypothesis != diagnosis
```

The domain may analyze possible function, motive, pattern, or origin only as a
hypothesis unless independently established by an appropriate authoritative
source.

---

# 15. Identity inference restrictions

Reflection contains `identity_narrative`, but that does not authorize the
system to classify identity.

Restricted inferences include claims such as:

```text
stable personality labels
sexual identity labels
political identity labels
religious identity labels
mental-health diagnoses
fixed attachment labels
fixed moral character labels
essentialized motives
```

The domain may structure a user-provided identity narrative.

It may compare versions of a user-provided narrative.

It may generate hypotheses around identity only when:

```text
clearly labeled as hypothesis
grounded in user-provided sources
non-diagnostic
reversible
uncertainty preserved
not silently persisted
```

Canonical invariant:

```text
identity narrative != stable identity fact
```

---

# 16. Interest mapping grounded in sources

DP-024 explicitly requires:

```text
interest mapping grounded in sources
```

An interest must never be inferred solely because:

```text
a topic appears once
a topic is emotionally salient once
the model associates the user with a category
the topic occurs in model memory without source grounding
```

Interest evidence may include grounded instances such as:

```text
explicit user statement
repeated user-selected activity
repeated source-backed discussion
explicit goal
explicit reading / project / practice history
confirmed preference
```

The result must preserve:

```text
interest candidate
supporting sources
frequency where grounded
time span
recency where meaningful
context
counterevidence / disconfirming signals
confidence or uncertainty
```

Canonical distinctions:

```text
topic mentioned != interest
interest != identity
interest != commitment
repetition != persistence
```

---

# 17. Confirmed persistence

DP-024 explicitly requires:

```text
confirmed persistence
```

This requirement applies both to durable Reflection conclusions and semantic
memory proposals.

A candidate pattern must not become persistent merely because it:

```text
appeared repeatedly in one conversation
was inferred by the model
was summarized by a previous model
exists in memory_entry
was generated by a workflow
```

Confirmed persistence requires either:

1. explicit user confirmation through the existing memory/decision contract; or
2. an existing shared persistence rule that explicitly establishes confirmed
   persistence with traceable evidence and authorization.

Reflection itself must not invent a new persistence engine.

Canonical invariant:

```text
candidate persistent pattern != confirmed persistent pattern
```

---

# 18. Semantic memory boundary

Roadmap permission:

```text
confirmation for semantic memory
```

Reflection may produce a:

```text
memory update proposal
```

It may not silently commit a semantic-memory fact.

Memory behavior must reuse shared memory contracts.

Required states include at least the existing shared equivalents of:

```text
proposal
pending confirmation
confirmed
rejected / not persisted
```

Where the shared system uses different canonical names, reuse those names.

The Reflection package must not create:

```text
ReflectionMemoryStore
ReflectionMemoryRegistry
ReflectionMemoryEngine
```

A `memory_entry` input is evidence/provenance, not automatically current truth.

---

# 19. Decision boundary

Reflection may review decisions.

It may structure:

```text
options
values
tensions
reasons
uncertainties
trade-offs
what changed
what remains unresolved
```

It must not autonomously adopt a personal decision.

Canonical distinctions:

```text
decision discussed != decision made
decision candidate != decision adopted
recommendation != user decision
reviewed decision != changed decision
```

`reflection.review_decision` is analytical only.

Any durable strategy/decision state must use shared decision/memory mechanisms
and explicit user confirmation where required.

---

# 20. Operation semantics

All operations must use shared `DomainOperationDefinition`.

No operation may bypass permissions or shared execution boundaries.

## 20.1 `reflection.structure_reflection`

Produces a structured representation of:

```text
observations
beliefs
values
emotions
needs
conflicts
hypotheses
uncertainties
open questions
```

No persistence.

## 20.2 `reflection.extract_beliefs`

Extracts candidate beliefs from supplied grounded material.

Must preserve whether each item is:

```text
explicit
inferred
uncertain
contradicted
```

No inferred belief becomes a user fact.

## 20.3 `reflection.compare_versions`

Compares temporally grounded versions.

Must not infer direction from input order or malformed chronology.

## 20.4 `reflection.identify_open_questions`

Returns unresolved questions and why each remains unresolved.

No invented answer.

## 20.5 `reflection.generate_hypotheses`

Produces multiple prudent hypotheses where appropriate.

Must include uncertainty and alternatives.

No diagnosis.

## 20.6 `reflection.build_personal_timeline`

Builds a proposal/representation of grounded events and versions.

Does not mutate shared timeline state.

Does not invent dates.

Does not treat approximate ordering as precise ordering.

## 20.7 `reflection.prepare_notion_entry`

Produces content suitable for a Notion entry.

This is **PREPARATION**, not an external write.

Canonical invariant:

```text
prepare_notion_entry != write_to_notion
```

The operation must not call a Notion connector, mutate an external page, or
claim that a note has been saved.

Actual external writes belong to shared connector/action infrastructure and
require the normal authorization contract.

## 20.8 `reflection.generate_summary`

Summarizes the structured reflection while preserving:

```text
uncertainty
ambivalence
open questions
source distinctions
hypothesis status
decision status
```

A summary must not increase certainty.

## 20.9 `reflection.review_decision`

Reviews a decision or candidate decision.

Returns analysis/proposal only.

No autonomous personal decision.

---

# 21. Workflows

All workflows must run through the shared workflow infrastructure.

No Reflection-specific workflow engine.

## 21.1 Structured Reflection

Purpose:

```text
organize a complex reflection without forcing convergence
```

Expected stages:

```text
collect grounded material
separate observation / interpretation
extract beliefs / values / emotions / needs
identify tensions
generate prudent hypotheses if justified
retain open questions
produce structured result
```

## 21.2 Belief Review

Purpose:

```text
review a belief against evidence, counterevidence, experience and interpretation
```

Must not convert lack of counterevidence into proof.

## 21.3 Personal Question Exploration

Purpose:

```text
explore an unresolved personal question using multiple hypotheses
```

Successful completion may have no answer.

## 21.4 Decision Reflection

Purpose:

```text
review a decision, values, tensions, alternatives and uncertainty
```

No automatic adoption.

## 21.5 Identity Narrative Review

Purpose:

```text
compare and structure user-provided identity narratives
```

Restricted identity inference applies.

No identity diagnosis/classification.

## 21.6 Longitudinal Reflection Review

Purpose:

```text
compare reflection versions over time
```

Requires grounded chronology.

No input-order timeline.

No persistence claim from repetition alone.

---

# 22. Permissions

Reflection is a high-sensitivity domain.

Canonical roadmap permissions:

```text
high sensitivity
restricted identity inference
confirmation for semantic memory
no automatic personal decisions
no psychological hypothesis presented as diagnosis
```

The implementation must map these to existing shared permission contracts.

Most restrictive permission wins under composition.

Unknown permission state denies.

Malformed authorization denies.

Only literal boolean `True` authorizes where the shared contract uses a boolean
authorization field.

Strings and numerics do not authorize:

```text
"true" != True
1 != True
```

---

# 23. External-action boundary

Phase 10.24 does not implement external connectors.

No operation may directly:

```text
write to Notion
send messages
send email
modify calendar
modify task manager
publish content
modify semantic memory
make purchases
submit forms
make personal decisions
```

Preparation is allowed.

Mutation requires shared external-action infrastructure and authorization.

Canonical invariant:

```text
PREPARATION != EXTERNAL COMMUNICATION
PROPOSAL != MUTATION
```

---

# 24. Source and provenance model

Reflection is often based on subjective material.

That does not eliminate source discipline.

Every decision-relevant reflective statement should preserve available
provenance such as:

```text
user_message
conversation
note
journal_entry
memory_entry
relationship_event
life_event
goal
decision
```

Required distinctions:

```text
provenance != truth
memory provenance != current truth
user interpretation != external observation
model inference != user statement
```

A caller-provided label such as:

```text
"confirmed": true
"fact": true
"official": true
```

must not bypass source validation if the shared infrastructure does not ground
that label.

---

# 25. Malformed / missing / conflicting evidence

Reflection must preserve distinct evidence states.

At minimum, logic must distinguish the shared equivalents of:

```text
absent
valid empty
malformed
unknown
conflicting
grounded
ungrounded
temporally ambiguous
```

Do not collapse all falsy values into one state.

Do not treat arbitrary mappings as valid semantic evidence merely because they
implement `Mapping`.

Malformed supporting evidence must never increase certainty.

Conflicting evidence must remain conflicting unless resolved by an explicit,
grounded rule.

---

# 26. Determinism and order invariance

Semantic results must not depend on input order where the evidence is
semantically equivalent.

Required areas:

```text
hypothesis sets
belief evidence
interest evidence
timeline/version comparison
duplicate source records
conflicting records
open-question aggregation
```

No first-wins conflict resolution.

No last-wins conflict resolution.

Duplicates must not inflate evidence strength silently.

Equal-authority / equal-grounding disagreement remains unresolved unless a
shared deterministic resolution rule applies.

---

# 27. Longitudinal evidence

Reflection may compare changes over time but must not create a new temporal
engine.

Reuse existing shared temporal/evidence contracts.

Required safety:

```text
date string != valid chronology
newer record != automatically truer record
same timestamp != temporal progression
elapsed time alone != persistence
repeated model summary != longitudinal corroboration
```

Malformed dates fail closed for directional claims.

---

# 28. Interest persistence and longitudinal confirmation

Interest mapping is a DP-024-specific acceptance surface.

The implementation must test at least:

```text
one mention → candidate only
repeated source-backed mentions → stronger candidate, not automatically persistent
contradictory evidence → uncertainty retained
same source duplicated → no evidence inflation
model-generated memory repetition → no independent corroboration
explicit confirmation → eligible for confirmed persistence proposal
```

The exact persistence mutation remains shared and confirmation-gated.

---

# 29. Psychological hypothesis safety

Reflection may explore possible psychological explanations but may not present
them as diagnoses.

Forbidden transforms include:

```text
possible insecurity → diagnosed disorder
possible avoidance → fixed attachment diagnosis
repeated reaction → personality disorder
emotion → pathology
identity uncertainty → identity diagnosis
```

The output must preserve:

```text
possible
plausible
uncertain
insufficient evidence
alternative explanation
```

where appropriate.

The domain is not a clinical diagnostic engine.

---

# 30. Relationship-event boundary

`relationship_event` is a Reflection resource.

Reflection may consume an authorized, minimal representation of a relationship
event.

It must not import or merge internal Relationships-domain store/state directly.

Where cross-domain context is used:

```text
shared cross-domain contract only
minimal relevant projection
authorization respected
provenance preserved
```

Relationships-domain psychological interpretations remain interpretations
unless independently grounded.

---

# 31. General fallback

Reflection must compose with General Domain using the existing shared
composition mechanism.

No Reflection-specific fallback engine.

If Reflection cannot safely resolve a reflective question, a valid result may
contain:

```text
open question
insufficient basis
request for clarification
General fallback
```

depending on existing shared contracts.

---

# 32. Concerns Domain boundary

Phase 10.25 — Concerns Domain is not yet implemented at the start of 10.24.

Reflection must not introduce a direct dependency on:

```text
cmm.domains.concerns
```

Do not pre-build Concerns infrastructure.

The roadmap cross-domain example may later compose:

```text
Relationships
→ Concerns
→ Reflection
```

through shared cross-domain infrastructure once 10.25 exists.

10.24 must remain independently valid before that package exists.

---

# 33. No new shared infrastructure by default

The preflight architectural assumption for 10.24 is:

```text
existing shared Phase 10 infrastructure is sufficient
```

Do not extract new shared primitives merely because Reflection resembles
Relationships or General.

Do not refactor University/Oppositions/Relationships into new abstractions
preemptively.

If implementation proves a genuinely missing shared primitive that cannot be
implemented correctly inside the existing contracts, stop and report:

```text
exact missing contract
why current shared contract cannot express required behavior
which existing domains would use the primitive identically
minimal proposed shared change
```

Do not silently change shared infrastructure.

---

# 34. Profile

Reflection must use the shared domain/cognitive profile mechanism.

The profile should configure reflective behavior such as:

```text
high sensitivity
prudent inference depth
multiple hypotheses
open questions allowed
no forced conclusion
restricted identity inference
confirmation-gated persistence
```

It must not create:

```text
ReflectionReasoningEngine
ReflectionPlanner
ReflectionCognitiveRuntime
```

The profile configures shared cognition; it does not replace it.

---

# 35. Resources

Resources must use shared resource contracts.

Reflection resource definitions must express:

```text
resource kind
required/optional semantics
sensitivity
read/write boundary
provenance expectations
```

where supported by existing infrastructure.

Required-resource semantics must remain meaningful.

If an operation requires resources A and B, missing either required resource
must not be silently treated as success unless the shared contract explicitly
models an OR requirement.

---

# 36. Presentation

Reflection presentation must preserve:

```text
observations
interpretations
beliefs
values
emotions
needs
hypotheses
counter-hypotheses
evidence
counterevidence
uncertainty
ambivalence
open questions
temporal evolution
interest evidence
persistence status
decision status
source/provenance
```

The presentation layer must not increase certainty.

It must distinguish:

```text
observed
user-stated
inferred
hypothetical
unknown
conflicting
confirmed
pending confirmation
```

where those states are available.

---

# 37. Trace

Use shared trace infrastructure.

Reflection trace may preserve:

```text
rule IDs
operation IDs
workflow steps
source references
permission decisions
memory proposal references
uncertainty state
```

Do not persist private chain-of-thought.

Do not create a Reflection trace store.

---

# 38. Memory

Use shared memory infrastructure.

Reflection memory integration is proposal/reference-only.

It must not:

```text
silently commit semantic memory
treat a previous memory summary as independent evidence
turn hypothesis into persistent fact
turn interest candidate into confirmed persistent interest
turn reviewed decision into adopted decision
```

---

# 39. Integration and bootstrap

Integration must follow the hardened validation-first pattern from prior Domain
Packs.

Required behavior:

```text
validate full Reflection pack
snapshot relevant shared registration state
register atomically through existing contracts
rollback exactly on failure
no partial registration
no import-time side effects
```

Bootstrap must compose:

```text
General + Reflection
```

through shared mechanisms.

No implicit global registration on import.

---

# 40. Error / unknown-state policy

Fail closed on decision-relevant uncertainty.

Required examples:

```text
unknown identity inference permission → deny
malformed memory confirmation → do not persist
unknown decision adoption → not adopted
unknown source grounding → do not claim fact
unknown chronology → no directional evolution
conflicting hypothesis evidence → remain unresolved
unknown interest persistence → not confirmed persistent
unknown operation → block
unknown workflow → block
missing implementation → fail closed
```

Malformed evidence may reduce confidence or make a result unresolved.

It must never widen authority, permission, certainty, or persistence.

---

# 41. Canonical rule expectations

## MultipleHypothesesRule

Must verify:

```text
multiple viable hypotheses retained
alternatives explicit
no arbitrary winner
uncertainty retained
counterevidence retained
order invariance
```

## PreserveAmbivalenceRule

Must verify:

```text
simultaneous conflicting emotions/needs/beliefs preserved
no forced reduction
context/time distinctions retained
```

## BeliefEvidenceRule

Must verify:

```text
belief/evidence/counterevidence/experience/interpretation separated
no type promotion
malformed evidence fail-closed
duplicates do not inflate support
```

## OpenQuestionRule

Must verify:

```text
insufficient basis leaves question open
plausible hypothesis does not close question
conflicting evidence leaves question open
```

## ReflectionTemporalEvolutionRule

Must verify:

```text
grounded chronology
same-time ambiguity
malformed chronology
version comparison
input-order invariance
no repetition→persistence shortcut
```

## NoForcedConclusionRule

Must verify:

```text
workflow can complete without conclusion
uncertainty remains visible
ambivalence remains visible
no unsupported certainty
```

---

# 42. Canonical operation tests

Every operation must prove:

```text
correct domain ID
correct reflection.* namespace
shared DomainOperationDefinition usage
required-resource enforcement
permission enforcement
no unauthorized mutation
JSON-safe public result
deterministic semantics where order should not matter
```

Additional operation-specific gates:

```text
prepare_notion_entry → preparation only
review_decision → no decision adoption
build_personal_timeline → no invented chronology
generate_hypotheses → multiple prudent hypotheses / no diagnosis
generate_summary → no certainty amplification
```

---

# 43. Workflow tests

Every workflow must prove:

```text
shared workflow engine
real dependency/gating
no local workflow runtime
no forced conclusion
permission propagation
resource gating
clean unresolved completion where valid
```

At least one workflow must end successfully with:

```text
no final conclusion
open questions present
```

At least one must preserve ambivalence.

---

# 44. DP-024 acceptance matrix

`AT-DP-024` must explicitly cover all four DP-024 dimensions.

## A. Open-ended analysis

Tests must prove:

```text
successful unresolved result
multiple hypotheses
open questions
ambivalence preservation
no forced conclusion
```

## B. Prudent hypotheses

Tests must prove:

```text
hypothesis != fact
alternative explanations retained
counterevidence retained
no diagnosis
no unsupported identity certainty
```

## C. Interest mapping grounded in sources

Tests must prove:

```text
source-backed interest candidate
one mention not enough for persistence
duplicates do not inflate evidence
contradictory evidence retained
model inference not treated as source
```

## D. Confirmed persistence

Tests must prove:

```text
candidate pattern != confirmed persistence
memory proposal != memory mutation
only valid confirmation can authorize persistence
malformed/nonliteral authorization fails closed
```

---

# 45. Primitive adversarial matrix

Public helper and canonical Rule surfaces should be tested against malformed
primitive values where relevant:

```text
None
True
False
0
1
-1
floats
NaN
infinity
empty string
arbitrary string
{}
[]
()
nested malformed mappings
```

The objective is not to accept all values.

The objective is:

```text
no accidental exception
no permission widening
no certainty widening
no persistence widening
strict JSON-safe output
```

---

# 46. JSON safety

All public helper results, operation results, workflow results, and serialized
Rule findings must be JSON-safe through the shared supported serialization
boundary.

Use:

```python
json.dumps(..., allow_nan=False)
```

against the supported public representation.

Do not require raw internal immutable metadata structures to serialize
directly if the shared contract exposes a canonical `to_dict()` serializer.

---

# 47. Input non-mutation

Reflection helpers/rules must not mutate caller-provided evidence.

Adversarial tests should deep-copy representative:

```text
messages
belief evidence
hypothesis records
timeline records
interest records
memory confirmation records
decision records
```

and prove they remain unchanged.

---

# 48. Duplicate / conflict policy

Duplicate semantic records must not automatically become independent evidence.

Required behavior:

```text
exact duplicate → no evidence inflation
compatible partial records → deterministic merge only where safe
incompatible duplicate → conflict / unresolved
```

No first-wins.

No last-wins.

Conflict identity/order must be deterministic.

---

# 49. Security and sensitivity

Reflection is high sensitivity.

The implementation must not leak sensitive Reflection data across domains
without shared authorization.

High-sensitivity permission composition must be at least as restrictive as
General and any supporting domain.

No sensitive result should broaden permissions merely because Reflection is
the primary domain.

---

# 50. Non-goals

Phase 10.24 does not implement:

```text
clinical diagnosis
therapy system
personality classifier
identity classifier
interest recommendation engine
external Notion connector
external write runtime
new semantic-memory store
new knowledge graph
new vector store
new temporal engine
new source authority engine
new cognitive engine
new planner
new workflow engine
new resolver
new permission engine
new trace store
new scheduler
new notification service
Concerns Domain
Life Plan Domain
```

---

# 51. Documentation

Implementation must add/update the existing canonical Phase 10 documentation
pattern.

Expected Reflection reference:

```text
docs/reference/reflection-domain.md
```

Required documentation should preserve:

```text
catalog
rules
operations
workflows
permissions
DP-024 mapping
memory boundary
identity inference boundary
interest grounding
confirmed persistence
cross-domain boundary
known deferrals
implementation status
```

Before independent audit, status must be:

```text
Phase 10.24 — Implemented, pending independent audit
```

Never mark Complete merely because implementation tests pass.

---

# 52. Implementation status lifecycle

Allowed states during this phase:

```text
Frozen design
Implemented, pending independent audit
Remediation required
Implemented, pending next independent audit
Complete — independently audited
```

Only an independent audit may move the phase to:

```text
Complete — independently audited
```

---

# 53. Expected implementation scope

Expected production package:

```text
cmm/domains/reflection/
```

exactly 14 modules.

Expected tests should follow established Phase 10 naming:

```text
tests/domains/test_reflection_domain_*.py
```

Expected documentation:

```text
docs/reference/reflection-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
```

Shared infrastructure should remain unchanged unless a proven missing primitive
requires human review first.

---

# 54. Pre-implementation architecture gate

Before writing Reflection production code, implementation must inspect:

```text
cmm/domains/general/
cmm/domains/relationships/
cmm/domains/university/
cmm/domains/oppositions/
```

and the shared contracts actually used by those packages.

The implementation should follow the most hardened current patterns rather than
copying an older Domain Pack blindly.

Priority precedent:

```text
Oppositions final hardened infrastructure usage
University validation/rollback hardening
Relationships sensitive-inference boundary
General fallback behavior
```

Do not copy domain-specific semantics across boundaries.

---

# 55. Acceptance summary

Phase 10.24 is implementation-ready when the implementation plan can satisfy
all of the following without architectural ambiguity:

```text
[ ] domain:reflection
[ ] exact 14-module package
[ ] exact 11 entities
[ ] exact 9 resources
[ ] exact 6 rules
[ ] exact 9 reflection.* operations
[ ] exact 6 workflows

[ ] open-ended analysis
[ ] multiple prudent hypotheses
[ ] ambivalence preserved
[ ] belief/evidence separation
[ ] open questions retained
[ ] temporal evolution grounded
[ ] no forced conclusion

[ ] identity inference restricted
[ ] psychological hypothesis != diagnosis
[ ] interest mapping grounded in sources
[ ] repetition != confirmed persistence
[ ] semantic-memory persistence requires confirmation
[ ] personal decisions not automated

[ ] proposal != mutation
[ ] prepare_notion_entry != external Notion write
[ ] review_decision != adopted decision

[ ] no direct Relationships state merge
[ ] no dependency on Concerns Domain
[ ] General fallback reused
[ ] shared cross-domain contracts reused

[ ] no parallel reasoning/planning/workflow/memory/trace infrastructure
[ ] validation-first integration
[ ] exact rollback
[ ] clean import / no side effects
[ ] malformed/unknown fail closed
[ ] most restrictive permissions win
[ ] deterministic duplicate/conflict handling
[ ] JSON-safe supported public outputs
[ ] caller inputs not mutated

[ ] AT-DP-024 covers all four DP-024 dimensions
[ ] implementation ends pending independent audit
```

---

# 56. Frozen decision

The approved architecture for Phase 10.24 is:

```text
standalone Reflection Domain Pack
over existing shared Phase 10 infrastructure
with no new shared subsystem
```

The implementation must preserve Reflection as an epistemically cautious,
open-ended specialization rather than turning it into a diagnosis,
classification, persistence, or decision engine.

Any implementation need that contradicts this frozen design requires an
explicit design amendment before production changes.
