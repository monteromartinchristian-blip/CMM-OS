# Concerns Domain (`domain:concerns`)

**Phase:** 10.25
**Status:** Implemented — pending independent audit
**Canonical identity:** `domain:concerns` · namespace `concerns.*` · version `1.0.0`
**Canonical profile:** `ConcernSupportProfile`
**Design (frozen):** `docs/superpowers/specs/2026-08-21-concerns-domain-design.md`
**Acceptance:** `DP-025` / `AT-DP-025`

---

## 1. Purpose

Concerns is CMM OS's **problem/worry conversational specialization**. It
supports the user through problems, worries, fears, uncertainty, recurring
concerns, difficult decisions, requests for reassurance or perspective, and
open-ended talk-it-through conversations.

Its behavioral center is not risk analysis:

```text
understand concern
→ understand lived significance
→ resolve/infer current support need
→ give useful substantive support
→ calibrate reality / interpretation / fear / hypothesis / scenario when useful
→ reassure when evidence supports reassurance
OR acknowledge real concern
OR preserve uncertainty
→ explore action only when useful or wanted
→ allow continued conversation without forced resolution
```

## 2. Package boundary

Exactly fourteen production modules — no parallel planner, agent runtime,
memory store, knowledge store/graph, workflow engine, permission engine,
question engine, confidence engine, or conversation engine:

```text
cmm/domains/concerns/
├── __init__.py      # public surface, definitions only, no import side effects
├── bootstrap.py     # ConcernsDomainBootstrap (General + Concerns)
├── catalog.py       # single source of truth for canonical members
├── definition.py    # immutable DomainDefinition
├── integration.py   # atomic validation-first registration + rollback
├── memory.py        # proposal-only shared memory contracts
├── operations.py    # 13 analysis/preparation operations
├── permissions.py   # fail-closed high-sensitivity policy
├── presentation.py  # semantics-preserving projection (no persona)
├── profile.py       # ConcernSupportProfile
├── resources.py     # 10 resource definitions over shared adapters
├── rules.py         # deterministic helpers + 14 reasoning rules
├── trace.py         # reference-only Phase 10.17 trace composition
└── workflows.py     # 8 workflows on the shared Workflow Engine
```

Importing `cmm.domains.concerns` has zero registration side effects; fresh
import leaves every registry untouched.

## 3. Canonical catalog

| Surface | Count | Members |
|---|---|---|
| Entities | 17 | concern, situation, trigger, emotion, fear, need, support_need, fact, interpretation, hypothesis, scenario, evidence, uncertainty, risk, desired_outcome, option, action |
| Resources | 10 | user_message, conversation, note, journal_entry, memory_entry, event, goal, decision, domain_result, external_source |
| Rules | 14 | UnderstandBeforeIntervene, EmotionalValidation, ExperienceRealitySeparation, SupportNeedCalibration, ContextualQuestion, UncertaintyPreservation, EvidenceCalibratedReassurance, ProportionalRisk, NoCatastrophicEscalation, NoFalseReassurance, RepetitionWithoutPathologizing, AgencyWithoutPressure, DirectnessWithoutHarshness, ImmediateRiskEscalation |
| Operations | 13 | understand_concern, infer_support_need, map_lived_experience, separate_reality_interpretation, explore_hypotheses, calibrate_uncertainty, evaluate_reassurance, evaluate_risk, identify_open_questions, explore_options, prepare_next_step, review_recurring_concern, prepare_professional_discussion |
| Workflows | 8 | Open Concern Conversation, Talk It Through, Reality Check, Reassurance Review, Practical Problem Solving, Decision Under Uncertainty, Recurring Concern Review, Professional Discussion Preparation |

`catalog.py` is the single canonical source: resource kinds and workflow names
are derived from it and never redeclared.

## 4. Core semantics

### Support need (conversational hypothesis, never a diagnosis)

```text
UNDERSTANDING EXPLORATION PERSPECTIVE REALITY_CHECK REASSURANCE INFORMATION
PROBLEM_SOLVING DECISION_SUPPORT EMOTIONAL_PROCESSING NEXT_STEP MIXED UNCLEAR
```

Inference precedence is strict and revisable:

```text
explicit current request > clear current signal > recent session context
> historical preference > UNCLEAR
```

Historical preference never overrides an explicit current request.

### Reassurance (allowed, evidence-calibrated)

```text
REASSURANCE_SUPPORTED | REASSURANCE_PARTIAL | UNCERTAIN
| CONCERN_SUPPORTED | INSUFFICIENT_BASIS
```

Reassurance may coexist with visible uncertainty. Absolute certainty is never
manufactured; false reassurance (minimizing material concerns or claiming
certainty) is detected and corrected. Concerns itself never assigns a numeric
probability; an authorized specialized probability is preserved with
provenance.

### Epistemic levels

```text
fact | experience | interpretation | fear | hypothesis | scenario
| uncertainty | unknown
```

Caller labels (`fact=true`, `confirmed=true`) never bypass grounding: a fact
requires a usable evidence reference. Fear is never a prediction; scenario
never claims probability; emotional certainty is not evidential certainty.
Duplicates collapse deterministically; malformed evidence increases neither
certainty nor concern nor risk; equivalent sets are order-invariant.

### Recurrence without pathologizing

Returning to the same concern is compared by actual state (topic, question,
grounded evidence set, impact), never topic labels alone. A repetitive
impossible-certainty pattern requires **all five** grounded dimensions across
multiple turns. Even then: `pathology_inferred=False` always, no psychiatric
label, reassurance remains allowed, unchanged evidence and unresolved
uncertainty stay visible.

### Action states (agency preserved)

```text
NO_ACTION_NEEDED | ACTION_OPTIONAL | ACTION_USEFUL | ACTION_RECOMMENDED
| DOMAIN_ESCALATION_NEEDED | USER_DECISION_REQUIRED
```

No action is a valid outcome. `option != recommendation != adopted decision !=
authorized execution`. Asking "decide for me" yields `USER_DECISION_REQUIRED`.
Nothing external is ever executed from a Concerns operation.

### Risk proportionality

Emotional intensity alone can never elevate risk ("very frightened" stays
unresolved). Authorized specialized red flags survive calm wording unchanged
(`downgraded=False`) and route escalation through the specialized domain;
Concerns creates no clinical/emergency protocol of its own.

### Catastrophic-promotion boundary

Blocked unsupported promotions: possibility→probability, ambiguity→warning
sign, change→deterioration, silence→rejection, symptom→serious disease,
setback→failure, uncertainty→danger.

### Questions are tools, not rituals

A question is materially required only if its answer can change meaning, risk,
reassurance, interpretation, domain routing, decision, or next step.
Non-material questions are suppressed (`ritual_questions_suppressed`).

## 5. Profile — `ConcernSupportProfile`

```text
contextual_sensitivity=high        epistemic_discipline=high
uncertainty_tolerance=high         emotional_context_awareness=high
interpretive_openness=moderate_high
default_action_pressure=low        default_alarm=low
reassurance_policy=evidence_calibrated
grounded_opinion_allowed=True      question_policy=material_only
cross_domain_awareness=True
```

All 14 rules required; maximum 3 deduplicated targeted questions; memory
read-only with `HIGHLY_SENSITIVE` limit; external action prohibited; no
persona semantics of any kind.

## 6. Permissions — fail-closed

Policy id `domain-permission:concerns:1.0.0`. Autonomous surface:
`resource.read`, `memory.read`, `operation.execute`, `workflow.execute`.

Denied by default: memory write, sensitive inference (+persist), file/task/
schedule/goal modification, external communication/search/models, export,
publication, irreversible change, knowledge delete, permission modify,
medical/legal/financial decisions/actions/spend, external domain activation.

Boolean authorization accepts only literal `True`; `"true"`, `1`, mappings,
and arbitrary objects fail closed. Most-restrictive policy wins under
composition; inbound cross-domain projections remain allowed.

## 7. Memory — proposal-only

Shared Phase 10.18 contracts only: `DomainMemoryProposalSnapshot`
(requires_confirmation=True, no override), view requests/views/bindings, and
shared validation. Session concern state is distinct from semantic memory.
The following content kinds can never be silently persisted regardless of any
authorization chain:

```text
fear · support_need · inferred_emotional_pattern · recurring_concern_pattern
· psychological_interpretation · risk_interpretation · third_party_motive
```

Repetition count is never authorization. A standalone approval snapshot is
reference data, not a complete contract.

## 8. Presentation & trace

`present_concerns_result` preserves semantics verbatim: facts stay facts,
interpretations stay interpretations (never user facts), hypotheses stay
hypothetical, fears/scenarios never become predictions/probabilities,
reassurance/material-concern/risk/action/memory/permission states pass through
unchanged. Section order is fixed:

```text
actual_concern → lived_impact → perspective → epistemic_distinctions
→ uncertainty → reassurance_or_material_concern → proportional_action
```

No tone/warmth/emoji/style/persona surface exists in this domain (Phase 11
Communication Profiles own those).

Trace composes caller-supplied typed references through the shared Phase 10.17
assembler: support need, evidence, uncertainty, reassurance/material concern,
risk, question rationale, action state, memory proposals, and permission
decisions are all referenceable; contributions carry only their own domain's
references; strict JSON; no chain-of-thought.

## 9. Cross-domain boundaries

Cross-domain information enters only via authorized minimal projections or
`domain_result` (metadata pins `cross_domain_projection`,
`minimal_authorized_projection`, `no_private_store_merge`,
`specialized_ownership_preserved`). Ownership:

```text
General            fallback
Relationships      relationship events/patterns/boundaries; motive stays hypothesis
Health             clinical red flags/urgency; reassuring results may ground reassurance
Reflection         broader meaning/values/identity narrative
University/Oppositions/Life Plan/Project   specialized factual semantics
Concerns           support need, concern framing, reassurance calibration,
                   uncertainty support, action pressure, recurring-concern review
```

Hypothesis exploration composes with the shared Reflection evaluator instead of
duplicating it. No direct private-store imports exist in either direction.

## 10. Verification

```bash
# focused suite
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/domains/test_concerns_domain_*.py

# fresh-import gate
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import cmm.domains.concerns
from cmm.domains.registry import DomainRegistry
assert DomainRegistry().get("domain:concerns") is None
print("CONCERNS_FRESH_IMPORT=PASS")
PY

.venv/bin/ruff check cmm/domains/concerns tests/domains/test_concerns_domain_*.py
.venv/bin/python -m compileall -q cmm/domains/concerns
git diff --check
```

Test modules: catalog, definition, profile, resources, understanding,
support_need (rules), epistemics, reassurance, recurrence, risk_agency,
operations, workflows, permissions, memory, presentation, trace,
cross_domain, integration, adversarial, dp025_acceptance.

## 11. Acceptance status

- `DP-025`: implemented per the frozen redesigned semantics.
- `AT-DP-025`: executable acceptance matrix green (25-step scenario + 22
  named gates), recorded as implementation-side candidate evidence.
- Independent audit: **not yet performed** — the phase must not be described
  as independently audited until that audit closes without blocking findings.
