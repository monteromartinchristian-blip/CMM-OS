# Phase 10.24 Reflection Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete Phase 10.24 `domain:reflection` Domain Pack and DP-024 acceptance surface on the existing shared Phase 10 infrastructure, ending in `Implemented, pending independent audit`.

**Architecture:** Add one 14-module `cmm/domains/reflection/` specialization that mirrors the current hardened Domain Pack contracts without introducing a Reflection-specific engine, store, resolver, planner, workflow runtime, memory system, trace system, or external connector. Reflection-specific semantics live in its catalog, profile, rules, operations, workflows, presentation, and adapters over shared contracts; DP-024 interest mapping and confirmed persistence are implemented as domain semantics, not new infrastructure.

**Tech Stack:** Python 3.10-compatible project code, existing CMM OS Phase 8/10 cognitive/domain contracts, pytest, Ruff, Git.

**Spec:** `docs/superpowers/specs/2026-08-20-reflection-domain-design.md`

## Global Constraints

- Expected starting branch: `feature/phase-10-domain-intelligence`.
- Expected starting HEAD: `563f7e2`.
- `domain_id` is exactly `domain:reflection`.
- Operation namespace is exactly `reflection.*`.
- Production package contains exactly 14 modules: `__init__.py`, `bootstrap.py`, `catalog.py`, `definition.py`, `integration.py`, `memory.py`, `operations.py`, `permissions.py`, `presentation.py`, `profile.py`, `resources.py`, `rules.py`, `trace.py`, `workflows.py`.
- Canonical counts are exactly 11 entities, 9 resources, 6 rules, 9 operations, 6 workflows.
- `catalog.py` is the single source of truth for canonical catalog members.
- Reuse shared Phase 10 contracts and infrastructure. No parallel Reflection engine/store/resolver/planner/workflow/memory/trace infrastructure.
- No direct dependency on `cmm.domains.concerns`.
- No direct internal state/store merge from Relationships.
- `reflection.prepare_notion_entry` prepares content only; it does not write to Notion.
- `reflection.review_decision` analyzes only; it does not adopt a decision.
- Psychological hypotheses must never be presented as diagnoses.
- Restricted identity inference remains hypothetical, grounded, reversible, and unpersisted without confirmation.
- Interest mapping must be source-grounded.
- Repetition does not establish confirmed persistence.
- Semantic-memory persistence requires valid shared confirmation; malformed/nonliteral authorization fails closed.
- Missing, malformed, unknown, conflicting, and temporally ambiguous states remain distinct where relevant.
- Only literal boolean `True` authorizes boolean-gated behavior.
- Public outputs must be JSON-safe through the supported shared serialization boundary.
- Inputs must not be mutated.
- Final implementation state is `Phase 10.24 — Implemented, pending independent audit`.
- Do not push.
- Do not merge.
- Use one final implementation commit after all dirty-tree verification is green: `feat(domains): implement phase 10.24 reflection domain`.

---

## File Structure

### Production — create exactly

- `cmm/domains/reflection/__init__.py` — public package surface only; no import-time registration.
- `cmm/domains/reflection/bootstrap.py` — validation-first bootstrap over General + Reflection.
- `cmm/domains/reflection/catalog.py` — canonical entities/resources/rules/operations/workflows and exact count validation.
- `cmm/domains/reflection/definition.py` — shared `DomainDefinition` construction for `domain:reflection`.
- `cmm/domains/reflection/integration.py` — atomic registration, snapshot, rollback, validation-first integration.
- `cmm/domains/reflection/memory.py` — shared-memory proposal/reference integration; no store.
- `cmm/domains/reflection/operations.py` — nine shared `DomainOperationDefinition` instances.
- `cmm/domains/reflection/permissions.py` — high-sensitivity and mutation/identity/persistence permission policy via shared contracts.
- `cmm/domains/reflection/presentation.py` — certainty-preserving Reflection presentation.
- `cmm/domains/reflection/profile.py` — shared cognitive/domain profile configuration.
- `cmm/domains/reflection/resources.py` — nine shared resource definitions.
- `cmm/domains/reflection/rules.py` — six canonical rules plus pure Reflection semantic helpers for DP-024.
- `cmm/domains/reflection/trace.py` — shared trace/reference integration only.
- `cmm/domains/reflection/workflows.py` — six shared workflow definitions with real gates/dependencies.

### Documentation — create/modify

- Create `docs/reference/reflection-domain.md`.
- Create this plan at `docs/superpowers/plans/2026-08-20-reflection-domain-implementation-plan.md`.
- Modify `docs/reference/domain-intelligence-requirements-matrix.md`.
- Modify `docs/roadmap/phase-10-domain-intelligence.md`.

### Tests — create

Use focused files rather than one monolithic test module:

- `tests/domains/test_reflection_domain_catalog.py`
- `tests/domains/test_reflection_domain_definition.py`
- `tests/domains/test_reflection_domain_resources.py`
- `tests/domains/test_reflection_domain_profile.py`
- `tests/domains/test_reflection_domain_permissions.py`
- `tests/domains/test_reflection_domain_rules.py`
- `tests/domains/test_reflection_domain_hypotheses.py`
- `tests/domains/test_reflection_domain_ambivalence.py`
- `tests/domains/test_reflection_domain_belief_evidence.py`
- `tests/domains/test_reflection_domain_open_questions.py`
- `tests/domains/test_reflection_domain_temporal_evolution.py`
- `tests/domains/test_reflection_domain_interest_mapping.py`
- `tests/domains/test_reflection_domain_persistence.py`
- `tests/domains/test_reflection_domain_operations.py`
- `tests/domains/test_reflection_domain_workflows.py`
- `tests/domains/test_reflection_domain_presentation.py`
- `tests/domains/test_reflection_domain_memory.py`
- `tests/domains/test_reflection_domain_trace.py`
- `tests/domains/test_reflection_domain_integration.py`
- `tests/domains/test_reflection_domain_rollback.py`
- `tests/domains/test_reflection_domain_cross_domain.py`
- `tests/domains/test_reflection_domain_dp024_acceptance.py`
- `tests/domains/test_reflection_domain_validation_first_matrix.py`
- `tests/domains/test_reflection_domain_adversarial.py`

Exact test-file consolidation is allowed only if existing hardened Domain Packs demonstrably use fewer files for the same boundaries; the behavioral coverage below is mandatory.

---

### Task 1: Preflight and Current-Contract Inventory

**Files:**
- Read: `docs/superpowers/specs/2026-08-20-reflection-domain-design.md`
- Read: `cmm/domains/oppositions/`
- Read: `cmm/domains/university/`
- Read: `cmm/domains/relationships/`
- Read: `cmm/domains/general/`
- Read: shared domain/cognitive contracts used by those packages
- Create: `docs/superpowers/plans/2026-08-20-reflection-domain-implementation-plan.md`

**Interfaces:**
- Consumes: current shared contracts and hardened Domain Pack patterns.
- Produces: a concrete inventory of exact shared types/builders/registries used by Reflection; no production code.

- [x] **Step 1: Verify repository state**

Run:

```bash
cd "/Users/chris/CMM OS"
git status --short --branch
git branch --show-current
git rev-parse --short HEAD
git log -8 --oneline --decorate
```

Expected:

```text
branch = feature/phase-10-domain-intelligence
HEAD = 563f7e2
tracked working tree clean
```

Observed: branch `feature/phase-10-domain-intelligence`, HEAD `563f7e2`, tracked tree clean
(only untracked plan file). This plan file was pre-seeded by the phase harness; it is the
canonical plan and is preserved/maintained here.

- [x] **Step 2: Read the frozen spec completely**

Run:

```bash
cat docs/superpowers/specs/2026-08-20-reflection-domain-design.md
```

Confirm the canonical counts and DP-024 requirements before touching code.

Read completely (1927 lines). Confirmed counts 11/9/6/9/6 and the four DP-024 dimensions.

- [x] **Step 3: Inventory current hardened package contracts**

Run targeted searches such as:

```bash
rg -n \
  'DomainDefinition|DomainResourceDefinition|DomainOperationDefinition|DomainProfileDefinition|ReasoningRule|Workflow|rollback|snapshot|permission|to_dict' \
  cmm/domains/oppositions \
  cmm/domains/university \
  cmm/domains/relationships \
  cmm/domains/general \
  cmm/domains
```

Record the exact shared types, builder naming conventions, registry APIs, permission composition API, rule-result/finding serializer, workflow contract, integration snapshot/rollback API, memory adapter, and trace adapter used by the current hardened packages.

Inventory recorded: `DomainDefinition`/`DomainCapability`/`DomainMetadata` (`cmm.domains.contracts`);
`DomainResourceDefinition`/`DomainResourceTemporalPolicy` (`cmm.domains.resource_contracts`);
`DomainProfileDefinition` + `DomainMemoryPolicy`/`DomainPresentationPolicy`/`DomainProductionPolicy`/
`DomainQuestionPolicy`/`DomainTemporalPolicy` (`cmm.domains.profile_contracts`);
`DomainOperationDefinition` (`cmm.domains.operation_contracts`, slug-prefix contract);
`DomainReasoningRuleDefinition`/`DomainRuleResult` (`cmm.domains.rule_contracts`);
`ReasoningRuleDefinition`/`ReasoningFinding`/`ReasoningGap`/`ReasoningRuleContext`/
`ReasoningRuleResult`/`ReasoningRuleTraceEntry` (`cmm.cognitive.reasoning_rule_contracts`);
`DomainWorkflowDefinition` (`cmm.domains.workflow_contracts`), `WorkflowNode`/`WorkflowNodeType`
(`cmm.workflows`); `DomainPermissionPolicy`/`DomainAutonomyLimits` (`cmm.domains.permission_contracts`)
+ `PermissionCapability` (`cmm.agent_runtime.domain_permission_contracts`);
`DomainMemoryProposalSnapshot`/`DomainMemoryView`/`DomainMemoryViewRequest`/
`DomainMemoryProposalBinding`/`sha256_digest` (`cmm.domains.memory_contracts`);
`DomainTrace`/`DomainTraceContribution`/`DomainTraceReference`/`DomainTraceAssemblyRequest`/
`DomainTraceReferences`/`DomainResultTraceReference` + `DomainTraceAssembler` (`cmm.domains.trace_*`);
registries with `snapshot_state`/`restore_state` (`cmm.domains.registry`, `registry_store`,
`profile_registry`, `resource_registry`, `operation_registry`, `workflow_registry`,
`permission_registry`, `cmm.cognitive.reasoning_rule_registry`, `cmm.workflows.registry`);
General bootstrap reuse + `DefaultDomainResolver(fallback_domain=domain:general)`; authorized
minimal cross-domain projection pattern (`value is True` literal gate, cf. Opposition
`_grants_trust` for Health/University projections); `to_dict()` + `json.dumps(allow_nan=False)`.

- [x] **Step 4: Verify no shared primitive is missing**

The conclusion must be one of:

```text
SHARED_INFRA_SUFFICIENT
```

or stop with a concrete blocker report containing:

```text
missing shared contract
why Reflection cannot express the frozen behavior without it
existing domains that would use the primitive identically
minimal shared change
```

Do not proceed with shared-infrastructure edits without human review.

Conclusion: `SHARED_INFRA_SUFFICIENT`. All frozen Reflection behavior maps onto existing
shared contracts: epistemic-level helpers are domain-local pure functions (like every prior
pack's rule helpers), chronology normalization is a domain-local pure helper (precedent:
Opposition `_parse_chronology_date`), and cross-domain relationship context is consumed as
a minimal authorized projection through the shared pattern. No shared edit is required.

- [x] **Step 5: Save the implementation plan**

Write this plan to:

```text
docs/superpowers/plans/2026-08-20-reflection-domain-implementation-plan.md
```

Do not commit yet; it will be included in the single implementation commit.

Plan present at that path (pre-seeded by the phase harness) and maintained here.

---

### Task 2: Catalog, Definition, Resources, Profile, and Package Boundary

**Files:**
- Create: `cmm/domains/reflection/catalog.py`
- Create: `cmm/domains/reflection/definition.py`
- Create: `cmm/domains/reflection/resources.py`
- Create: `cmm/domains/reflection/profile.py`
- Create: `cmm/domains/reflection/__init__.py`
- Test: catalog/definition/resources/profile tests

**Interfaces:**
- Consumes: exact shared types discovered in Task 1.
- Produces: canonical `domain:reflection` package metadata and builders used by all later tasks.

- [x] **Step 1: Write RED catalog tests**

Tests must assert exactly:

```python
ENTITIES == (
    "reflection",
    "belief",
    "value",
    "question",
    "hypothesis",
    "emotion",
    "need",
    "conflict",
    "identity_narrative",
    "decision",
    "uncertainty",
)
```

Resources exactly:

```python
(
    "user_message",
    "conversation",
    "note",
    "journal_entry",
    "memory_entry",
    "relationship_event",
    "life_event",
    "goal",
    "decision",
)
```

Rules exactly:

```python
(
    "MultipleHypothesesRule",
    "PreserveAmbivalenceRule",
    "BeliefEvidenceRule",
    "OpenQuestionRule",
    "ReflectionTemporalEvolutionRule",
    "NoForcedConclusionRule",
)
```

Operations exactly:

```python
(
    "reflection.structure_reflection",
    "reflection.extract_beliefs",
    "reflection.compare_versions",
    "reflection.identify_open_questions",
    "reflection.generate_hypotheses",
    "reflection.build_personal_timeline",
    "reflection.prepare_notion_entry",
    "reflection.generate_summary",
    "reflection.review_decision",
)
```

Workflows exactly:

```python
(
    "Structured Reflection",
    "Belief Review",
    "Personal Question Exploration",
    "Decision Reflection",
    "Identity Narrative Review",
    "Longitudinal Reflection Review",
)
```

Also assert counts `11/9/6/9/6`, no duplicates, and operation prefix `reflection.`.

- [x] **Step 2: Run RED**

Run only the new catalog tests. Confirm failure is due to missing Reflection package/catalog.

- [x] **Step 3: Implement `catalog.py` minimally**

Use immutable canonical collections consistent with current hardened packages.

`catalog.py` must be the source of truth. Other Reflection modules import from it rather than retyping canonical lists.

- [x] **Step 4: Add RED definition/resources/profile tests**

Assert:

```text
domain_id = domain:reflection
domain slug = reflection
resource kinds exactly match catalog
profile is high sensitivity
profile preserves multiple hypotheses/open questions
profile prohibits automatic personal decisions
profile restricts identity inference
profile requires confirmation-gated semantic persistence
```

Use the exact shared fields supported by the current profile/resource contracts.

- [x] **Step 5: Implement definition/resources/profile**

Mirror hardened current builder/contract usage; do not copy domain-specific semantics from Oppositions or University.

- [x] **Step 6: Package boundary test**

Assert production package has exactly the 14 frozen modules and clean import does not register globally.

- [x] **Step 7: Run focused GREEN**

Run all Reflection catalog/definition/resource/profile tests.

---

### Task 3: Permission Model and Fail-Closed Authorization

**Files:**
- Create: `cmm/domains/reflection/permissions.py`
- Test: `tests/domains/test_reflection_domain_permissions.py`
- Test: relevant portions of `test_reflection_domain_adversarial.py`

**Interfaces:**
- Consumes: shared permission contracts.
- Produces: Reflection permission policy used by rules, operations, workflows, memory, integration.

- [x] **Step 1: Write RED permission tests**

Cover:

```text
high sensitivity
restricted identity inference
semantic-memory mutation requires confirmation
no automatic personal decisions
no diagnostic presentation
external write denied by default
most restrictive composed permission wins
unknown permission denies
malformed permission denies
```

Literal-boolean matrix:

```python
for raw in ("true", "false", 1, 0, [], {}, None):
    assert authorizes(raw) is False
assert authorizes(True) is True
```

Do not implement a local generic authorization engine if shared contracts already provide the gate.

- [x] **Step 2: Run RED**

Confirm failures occur because Reflection permission policy is absent.

- [x] **Step 3: Implement permission definitions/adapters**

Use shared permission gates. Any Reflection helper that consumes an authorization projection must check literal `True` if the shared field is boolean.

- [x] **Step 4: Add composition tests**

Combine Reflection with stricter supporting-domain/global policy and assert the restrictive result remains.

- [x] **Step 5: Run focused GREEN**

---

### Task 4: Multiple Hypotheses and No-Forced-Conclusion Semantics

**Files:**
- Create/modify: `cmm/domains/reflection/rules.py`
- Test: `tests/domains/test_reflection_domain_hypotheses.py`
- Test: `tests/domains/test_reflection_domain_rules.py`
- Test: `tests/domains/test_reflection_domain_adversarial.py`

**Interfaces:**
- Produces pure helper semantics plus canonical `MultipleHypothesesRule` and `NoForcedConclusionRule`.

- [x] **Step 1: Define the public semantic result shape in tests**

For hypothesis evaluation, require JSON-safe fields equivalent to:

```python
{
    "hypotheses": [...],
    "supported_ids": [...],
    "conflicting_ids": [...],
    "unresolved": bool,
    "winner_selected": False,
    "forced_conclusion": False,
}
```

Use existing project tuple/list conventions rather than introducing a new serializer.

Each hypothesis projection must preserve, when supplied:

```text
identity
statement
supporting evidence references
counterevidence references
uncertainty
scope
temporal grounding
```

- [x] **Step 2: Write RED tests for multi-hypothesis preservation**

Cases:

```text
two compatible plausible hypotheses → both retained
equal support disagreement → no winner
one hypothesis stronger → may be marked stronger, never converted to fact
missing evidence → unresolved
conflicting evidence → unresolved
input permutations → same semantic result
exact duplicates → no evidence inflation
```

- [x] **Step 3: Write RED no-forced-conclusion tests**

Valid completion with:

```text
multiple hypotheses
open questions
ambivalence
no recommendation
no conclusion
```

must not be treated as rule failure.

- [x] **Step 4: Run RED**

- [x] **Step 5: Implement minimal pure helpers and both canonical rules**

Do not use first/last input order as tie-breaker.

Do not persist chain-of-thought.

- [x] **Step 6: Canonical Rule parity tests**

The shared `ReasoningFinding` output must preserve the same uncertainty/unresolved state as the helper.

For JSON, test the supported public serializer:

```python
json.dumps(finding.to_dict(), allow_nan=False)
```

Do not require raw immutable internal metadata to serialize directly.

- [x] **Step 7: Run focused GREEN**

---

### Task 5: Ambivalence and Belief/Evidence Separation

**Files:**
- Modify: `cmm/domains/reflection/rules.py`
- Test: `tests/domains/test_reflection_domain_ambivalence.py`
- Test: `tests/domains/test_reflection_domain_belief_evidence.py`
- Test: `tests/domains/test_reflection_domain_rules.py`

**Interfaces:**
- Produces `PreserveAmbivalenceRule` and `BeliefEvidenceRule`.

- [x] **Step 1: Write RED ambivalence tests**

Cases:

```text
want closeness + want distance → both retained
relief + sadness → both retained
belief + doubt → both retained
same context/time contradiction → conflict/ambivalence, not arbitrary winner
different contexts → preserve context distinction
different grounded times → preserve temporal distinction
duplicate identical emotion → no double weighting
```

Assert:

```text
ambivalence_present=True
forced_resolution=False
```

where appropriate.

- [x] **Step 2: Write RED belief/evidence tests**

Require distinct projections for:

```text
belief
evidence
counterevidence
experience
interpretation
```

Cases:

```text
experience alone cannot become external fact
interpretation cannot become observation
memory_entry cannot become current fact automatically
duplicate evidence does not inflate support
conflicting evidence remains conflict
malformed evidence fails closed
```

- [x] **Step 3: Run RED**

- [x] **Step 4: Implement minimal semantics and canonical rules**

- [x] **Step 5: Order-invariance and input-nonmutation tests**

Deep-copy supplied records and compare after evaluation.

- [x] **Step 6: Run focused GREEN**

---

### Task 6: Open Questions and Temporal Evolution

**Files:**
- Modify: `cmm/domains/reflection/rules.py`
- Test: `tests/domains/test_reflection_domain_open_questions.py`
- Test: `tests/domains/test_reflection_domain_temporal_evolution.py`
- Test: `tests/domains/test_reflection_domain_rules.py`

**Interfaces:**
- Produces `OpenQuestionRule` and `ReflectionTemporalEvolutionRule`.

- [x] **Step 1: Write RED open-question tests**

A question remains open when:

```text
evidence missing
evidence conflicting
only a plausible hypothesis exists
future behavior is unknowable
motive was not stated
timeline incomplete
source basis ungrounded
```

Assert a plausible hypothesis alone cannot close the question.

- [x] **Step 2: Write RED chronology tests**

Use different values from Phase 10.23 tests:

```text
valid ordered dates → directional evolution allowed
same exact timestamp via Z/+offset → no directional evolution
same date-only value → no directional evolution
malformed date → no directional evolution
missing date → chronology unknown
input order permutations → identical semantic result
```

Also test:

```text
rephrased wording != substantive change
repetition != persistence
newer ungrounded record != current truth
```

- [x] **Step 3: Run RED**

- [x] **Step 4: Implement with existing shared temporal primitives**

No new temporal engine.

Normalize chronology conservatively. Equal normalized timestamps cannot establish before/after.

- [x] **Step 5: Canonical Rule parity + JSON tests**

- [x] **Step 6: Run focused GREEN**

---

### Task 7: DP-024 Interest Mapping

**Files:**
- Modify: `cmm/domains/reflection/rules.py` or the existing Reflection semantic module permitted by the frozen 14-file boundary
- Test: `tests/domains/test_reflection_domain_interest_mapping.py`
- Test: `tests/domains/test_reflection_domain_dp024_acceptance.py`

**Interfaces:**
- Produces a pure source-grounded interest-mapping helper consumed by operations/presentation; it is not a seventh canonical rule.

- [x] **Step 1: Write RED source-grounding tests**

Cases:

```text
one explicit mention → interest candidate only
explicit repeated user-selected activity across grounded sources → stronger candidate
duplicate copy of same source → no extra corroboration
model-generated summary repeating earlier evidence → no independent corroboration
contradictory user evidence → uncertainty retained
unrelated topic mention → not silently classified as interest
```

Result must preserve:

```text
interest candidate
source IDs / provenance
grounded evidence count
time span when valid
context
counterevidence
uncertainty
persistent_confirmed=False unless separately confirmed
```

- [x] **Step 2: Write RED identity-boundary tests**

Assert:

```text
interest != identity
interest != commitment
topic mentioned != interest
```

No automatic sensitive identity label from interest evidence.

- [x] **Step 3: Run RED**

- [x] **Step 4: Implement deterministic source identity normalization**

Exact duplicates must not inflate evidence.

Conflicting records remain conflicting.

No first-wins behavior.

- [x] **Step 5: Permutation and strict JSON tests**

- [x] **Step 6: Run focused GREEN**

---

### Task 8: DP-024 Confirmed Persistence and Memory Boundary

**Files:**
- Create: `cmm/domains/reflection/memory.py`
- Modify: `cmm/domains/reflection/rules.py` if a pure persistence classifier is needed
- Test: `tests/domains/test_reflection_domain_persistence.py`
- Test: `tests/domains/test_reflection_domain_memory.py`
- Test: `tests/domains/test_reflection_domain_dp024_acceptance.py`

**Interfaces:**
- Consumes: shared memory proposal/confirmation contracts.
- Produces: proposal/reference behavior only; no Reflection memory store.

- [x] **Step 1: Write RED persistence-state tests**

Require distinct behavior:

```text
candidate pattern → not confirmed persistent
repeated model inference → not confirmed persistent
repeated evidence in one conversation → not confirmed persistent
duplicate memory summaries → no corroboration
explicit valid confirmation → eligible for confirmed persistence proposal
rejection → not persisted
missing confirmation → not persisted
```

- [x] **Step 2: Write RED authorization primitive matrix**

For any boolean confirmation field:

```python
True        -> valid authorization if all other shared conditions hold
False       -> no persistence
"true"      -> no persistence
"false"     -> no persistence
1           -> no persistence
0           -> no persistence
None        -> no persistence
{} / []     -> no persistence
```

- [x] **Step 3: Run RED**

- [x] **Step 4: Implement via shared memory contracts**

No direct memory mutation from helper/rule.

No `ReflectionMemoryStore`.

- [x] **Step 5: Test `memory_entry` provenance**

A prior memory entry may be used as provenance but cannot silently establish a current fact, current identity, adopted decision, or confirmed persistent interest.

- [x] **Step 6: Run focused GREEN**

---

### Task 9: Operations

**Files:**
- Create: `cmm/domains/reflection/operations.py`
- Test: `tests/domains/test_reflection_domain_operations.py`

**Interfaces:**
- Consumes: catalog/resources/permissions/rule helpers/shared `DomainOperationDefinition`.
- Produces: exactly nine `reflection.*` operation definitions.

- [x] **Step 1: Write RED operation contract tests**

For all nine operations assert:

```text
domain ID matches domain:reflection
operation ID prefix matches reflection
resource requirements are meaningful
permissions are attached through shared contracts
unknown operation blocks
missing required resource blocks
```

- [x] **Step 2: Write operation-specific RED tests**

`reflection.structure_reflection`:

```text
returns structured observations/beliefs/values/emotions/needs/conflicts/hypotheses/uncertainties/open questions
does not persist
```

`reflection.extract_beliefs`:

```text
explicit vs inferred vs uncertain vs contradicted preserved
```

`reflection.compare_versions`:

```text
no malformed/input-order chronology
```

`reflection.identify_open_questions`:

```text
returns unresolved questions and reasons
```

`reflection.generate_hypotheses`:

```text
multiple prudent hypotheses
no diagnosis
no forced winner
```

`reflection.build_personal_timeline`:

```text
no invented dates
no mutation
```

`reflection.prepare_notion_entry`:

```text
returns prepared content
external_write_performed=False
no connector call
```

`reflection.generate_summary`:

```text
does not increase certainty
```

`reflection.review_decision`:

```text
decision_adopted=False
proposal_only=True
```

- [x] **Step 3: Run RED**

- [x] **Step 4: Implement definitions/adapters using current operation infrastructure**

- [x] **Step 5: Run focused GREEN**

---

### Task 10: Workflows

**Files:**
- Create: `cmm/domains/reflection/workflows.py`
- Test: `tests/domains/test_reflection_domain_workflows.py`

**Interfaces:**
- Consumes: shared workflow engine and Reflection operations.
- Produces: exactly six workflow definitions.

- [x] **Step 1: Write RED workflow catalog tests**

Exact names:

```text
Structured Reflection
Belief Review
Personal Question Exploration
Decision Reflection
Identity Narrative Review
Longitudinal Reflection Review
```

- [x] **Step 2: Write RED dependency/gating tests**

Every workflow must have real dependencies/gates; no inert metadata-only workflow.

- [x] **Step 3: Write unresolved-completion RED**

At least one workflow must complete successfully with:

```text
no final conclusion
open questions present
unresolved=True or equivalent
```

and not be classified as execution failure.

- [x] **Step 4: Write ambivalence-preservation RED**

At least one workflow must carry ambivalence through to final output.

- [x] **Step 5: Write permission/resource failure tests**

Unknown/malformed authorization and missing required resources block according to shared engine contracts.

- [x] **Step 6: Implement and run GREEN**

No Reflection-specific workflow engine.

---

### Task 11: Presentation, Trace, and Supported Serialization

**Files:**
- Create: `cmm/domains/reflection/presentation.py`
- Create: `cmm/domains/reflection/trace.py`
- Test: `tests/domains/test_reflection_domain_presentation.py`
- Test: `tests/domains/test_reflection_domain_trace.py`

**Interfaces:**
- Consumes: shared presentation and trace contracts.
- Produces: certainty-preserving user-facing projections and trace references.

- [x] **Step 1: Write RED presentation tests**

Presentation must distinguish available states:

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

It must preserve:

```text
hypothesis status
counterevidence
ambivalence
open questions
temporal ambiguity
interest provenance
persistence status
decision status
```

- [x] **Step 2: Write RED certainty-nonamplification tests**

A helper result with `unresolved=True` cannot be presented as resolved.

A hypothesis cannot be worded/presented as fact or diagnosis.

- [x] **Step 3: Write RED trace tests**

Trace stores rule/operation/workflow/source/permission references, not private chain-of-thought.

- [x] **Step 4: Run RED**

- [x] **Step 5: Implement shared adapters and run GREEN**

- [x] **Step 6: Supported serializer gate**

For representative findings/results:

```python
json.dumps(finding.to_dict(), allow_nan=False)
json.dumps(public_result, allow_nan=False)
```

must pass.

---

### Task 12: Integration, Bootstrap, Rollback, and General Fallback

**Files:**
- Create: `cmm/domains/reflection/integration.py`
- Create: `cmm/domains/reflection/bootstrap.py`
- Test: `tests/domains/test_reflection_domain_integration.py`
- Test: `tests/domains/test_reflection_domain_rollback.py`
- Test: `tests/domains/test_reflection_domain_cross_domain.py`
- Test: `tests/domains/test_reflection_domain_validation_first_matrix.py`

**Interfaces:**
- Consumes: complete validated Reflection pack and shared registries/bootstrap contracts.
- Produces: atomic registration and General + Reflection composition.

- [x] **Step 1: Write RED validation-first tests**

Malformed pack member must fail before partial registration.

Missing implementation must fail closed.

Unknown workflow/operation must block.

- [x] **Step 2: Write RED rollback test**

Take shared registry snapshots, inject failure at each supported registration boundary, and assert exact restoration.

- [x] **Step 3: Write RED clean-import test**

```python
import cmm.domains.reflection
```

must not mutate global registration state.

- [x] **Step 4: Write RED General fallback test**

Reflection composes with General through shared mechanisms.

- [x] **Step 5: Write RED Relationships boundary test**

If relationship context is accepted, only a minimal authorized projection through shared cross-domain contracts is consumed.

Assert no direct import:

```text
cmm.domains.relationships.<store/state module>
```

- [x] **Step 6: Write Concerns nondependency test**

Static/import test must prove no dependency on `cmm.domains.concerns`.

- [x] **Step 7: Implement integration/bootstrap minimally and run GREEN**

---

### Task 13: DP-024 Acceptance Matrix

**Files:**
- Create/complete: `tests/domains/test_reflection_domain_dp024_acceptance.py`
- Modify: Reflection production only if RED exposes a genuine spec gap

**Interfaces:**
- Consumes all completed Reflection boundaries.
- Produces direct executable evidence for `AT-DP-024`.

- [x] **Step 1: Open-ended analysis acceptance tests**

Prove:

```text
successful unresolved output
multiple hypotheses retained
ambivalence retained
open questions retained
no forced conclusion
```

- [x] **Step 2: Prudent-hypothesis acceptance tests**

Prove:

```text
hypothesis != fact
counterevidence preserved
alternative explanations preserved
psychological hypothesis != diagnosis
identity inference remains restricted/hypothetical
```

- [x] **Step 3: Source-grounded interest acceptance tests**

Prove:

```text
one mention != confirmed interest persistence
duplicate source != independent corroboration
model inference != source evidence
contradiction remains visible
grounded repeated source-backed activity may strengthen candidate
```

- [x] **Step 4: Confirmed-persistence acceptance tests**

Prove:

```text
candidate != persistent confirmed
proposal != memory mutation
only valid confirmation permits confirmed-persistence proposal
malformed/nonliteral authorization fails closed
```

- [x] **Step 5: Run `AT-DP-024` focused GREEN**

Do not mark matrix status audited; implementation only establishes candidate evidence pending independent audit.

---

### Task 14: Adversarial Closure Gate Before Commit

**Files:**
- Create/complete: `tests/domains/test_reflection_domain_adversarial.py`
- Optional one-off probe under `/tmp`; do not commit temporary probe artifacts

**Interfaces:**
- Consumes all Reflection public helpers/rules.
- Produces pre-audit hardening evidence.

- [x] **Step 1: Primitive no-exception matrix**

Exercise relevant public helpers with:

```python
None, True, False, 0, 1, -1, 1.5,
float("nan"), float("inf"), -float("inf"),
"", "unknown", "arbitrary", {}, [], (), [{}]
```

Expected:

```text
no accidental exception
no permission widening
no certainty widening
no persistence widening
supported output JSON-safe
```

- [x] **Step 2: Permutation matrix**

Permute:

```text
hypotheses
duplicate/conflicting evidence
ambivalence records
interest evidence
temporal versions
```

Equivalent semantic input must produce equivalent public result.

- [x] **Step 3: Duplicate identity matrix**

Exact duplicates do not inflate evidence or persistence.

Conflicting duplicate identities remain unresolved.

- [x] **Step 4: Same-time chronology gate**

Equal normalized timestamps cannot establish evolution/persistence.

- [x] **Step 5: Input non-mutation gate**

Deep-copy representative nested inputs and assert equality after evaluation.

- [x] **Step 6: Supported strict JSON gate**

Use:

```python
json.dumps(result, allow_nan=False)
json.dumps(finding.to_dict(), allow_nan=False)
```

- [x] **Step 7: Print a one-off adversarial summary**

The implementation agent's probe should report at least:

```text
OPEN_ENDED_GATE=PASS
HYPOTHESIS_GATE=PASS
AMBIVALENCE_GATE=PASS
BELIEF_EVIDENCE_GATE=PASS
OPEN_QUESTION_GATE=PASS
TEMPORAL_GATE=PASS
INTEREST_GROUNDING_GATE=PASS
PERSISTENCE_GATE=PASS
IDENTITY_SAFETY_GATE=PASS
PERMISSION_GATE=PASS
PERMUTATION_GATE=PASS
INPUT_NON_MUTATION_GATE=PASS
STRICT_JSON_GATE=PASS
NO_EXCEPTION_GATE=PASS
ALL_PASS=true
```

Use probe values different from committed tests.

---

### Task 15: Documentation and Status

**Files:**
- Create: `docs/reference/reflection-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Include: `docs/superpowers/plans/2026-08-20-reflection-domain-implementation-plan.md`

**Interfaces:**
- Consumes final implementation behavior.
- Produces canonical implementation documentation pending audit.

- [x] **Step 1: Write Reflection reference**

Document:

```text
purpose
14-module boundary
11/9/6/9/6 catalog
rules
operations
workflows
permissions
DP-024 mapping
interest grounding
confirmed persistence
identity/diagnosis restrictions
memory boundary
external-action boundary
cross-domain boundary
known Phase 11 deferrals
```

- [x] **Step 2: Update matrix**

`DP-024` implementation state should become the project's established equivalent of:

```text
implemented, pending independent audit
```

Do not mark `AT-DP-024` PASS/Complete unless project convention explicitly distinguishes implementation evidence from independent audit. Preserve the frozen lifecycle.

- [x] **Step 3: Update roadmap**

10.24 statement:

```text
Implemented, pending independent audit.
```

Do not alter 10.23 closure.

- [x] **Step 4: Documentation consistency scan**

Run:

```bash
rg -n \
  '10\.24|DP-024|AT-DP-024|Reflection Domain|pending independent audit|Complete|audited' \
  docs/reference/reflection-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md
```

Confirm no premature closure claim.

---

### Task 16: Full Verification and Single Implementation Commit

**Files:**
- All intended Phase 10.24 production/tests/docs only.

**Interfaces:**
- Produces clean committed implementation candidate for independent audit.

- [x] **Step 1: Focused Reflection suite**

Run:

```bash
.venv/bin/python -m pytest -q tests/domains/test_reflection_domain_*.py
```

- [x] **Step 2: Relevant precursor/security/cross-domain tests**

Discover and run the actual current hardened tests for:

```text
General domain
Relationships sensitive inference
University/Health projection boundaries
cross-domain contracts
permission composition
operation integration
workflow integration
rollback
memory
trace
```

- [x] **Step 3: Full domain suite**

```bash
.venv/bin/python -m pytest -q tests/domains
```

- [x] **Step 4: Global suite**

```bash
.venv/bin/python -m pytest -q
```

If VS Code reports an environment-generated interruption such as `^C`,
`KeyboardInterrupt`, or `turn interrupted`, treat the interruption itself as
neither PASS nor FAIL; rerun or split. Real test failures printed before an
interruption remain real failures.

- [x] **Step 5: Static checks**

```bash
.venv/bin/ruff check \
  cmm/domains/reflection \
  tests/domains/test_reflection_domain_*.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/reflection \
  tests/domains/test_reflection_domain_*.py

.venv/bin/python -m compileall -q cmm/domains/reflection

.venv/bin/python - <<'PY'
import cmm.domains.reflection
print("fresh_import=OK")
PY

git diff --check
```

- [x] **Step 6: Production package boundary check**

Assert exactly 14 `.py` production modules under `cmm/domains/reflection/`.

- [x] **Step 7: Diff audit**

Run:

```bash
git status --short
git diff --stat
git diff
git diff --check
```

Reject:

```text
unrelated refactor
shared-infrastructure edit without prior human approval
direct Concerns dependency
direct Relationships store/state import
external connector use
Notion write
silent memory mutation
automatic personal decision
diagnostic wording
premature Complete/audited status
```

- [x] **Step 8: Stage intended scope**

```bash
git add \
  cmm/domains/reflection \
  tests/domains/test_reflection_domain_*.py \
  docs/superpowers/plans/2026-08-20-reflection-domain-implementation-plan.md \
  docs/reference/reflection-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md
```

Then:

```bash
git diff --cached --check
git diff --cached --stat
git diff --cached
```

- [x] **Step 9: Commit once**

```bash
git commit -m "feat(domains): implement phase 10.24 reflection domain"
```

No amend.

No push.

No merge.

- [x] **Step 10: Mandatory clean-state verification**

On the committed clean state, rerun:

```bash
.venv/bin/python -m pytest -q tests/domains/test_reflection_domain_*.py
.venv/bin/python -m pytest -q tests/domains
.venv/bin/python -m pytest -q
.venv/bin/ruff check cmm/domains/reflection tests/domains/test_reflection_domain_*.py
.venv/bin/ruff check --target-version py310 cmm/domains/reflection tests/domains/test_reflection_domain_*.py
.venv/bin/python -m compileall -q cmm/domains/reflection
.venv/bin/python - <<'PY'
import cmm.domains.reflection
print("fresh_import=OK")
PY
git diff --check HEAD^ HEAD
git status --short --branch
```

- [x] **Step 11: Final state**

Report only:

```text
Phase 10.24 — Implemented, pending independent audit
```

Do not perform the independent audit yourself.
