# Phase 10.32 — Domain Conflict Resolution Policies

**Status:** Approved design specification
**Phase:** 10.32 — Domain Conflict Resolution
**Date:** 2026-08-28
**Predecessor:** Phase 10.31 — Domain Selection Policies, independently audited and closed
**Next phase boundary:** Phase 10.33 — Domain Events

## 1. Purpose

Phase 10.32 introduces the shared policy layer that coordinates conflicts already emitted by Domain Intelligence subsystems.

It must not create a second conflict model for every subsystem, replace existing conflict contracts, or duplicate the Cognitive Layer contradiction engine. Instead, it provides a deterministic orchestration layer that:

1. references existing conflict outputs;
2. normalizes only the minimum information required for cross-domain policy decisions;
3. classifies authority, severity, and blocking state;
4. applies a strict resolution precedence;
5. chooses a legitimate declarative resolution strategy;
6. preserves incompatible results and provenance when no legitimate winner exists;
7. blocks dependent continuation while a material blocking conflict remains unresolved.

The result of Phase 10.32 is a pure decision describing what must happen next. It does not perform that next action.

## 2. Architectural decision

Phase 10.32 uses a **conflict orchestration layer** above existing conflict-producing subsystems.

Existing contracts remain authoritative within their own scope, including but not limited to:

- `DomainConflict` for declared Domain Pack incompatibilities;
- `DomainCompositionConflict`;
- `DomainPermissionConflict`;
- `DomainProfileConflict`;
- `DomainRuleSelectionConflict`;
- `DomainPresentationConflict`;
- `CrossDomainContradiction`;
- Cognitive Layer `Contradiction`;
- domain-specific typed conflict outputs where applicable.

The new layer references these outputs instead of replacing or copying them.

### 2.1 Naming boundary

`DomainConflict` already exists and represents declared Domain Pack incompatibility. Phase 10.32 must not rename, repurpose, or overload that contract.

The canonical Phase 10.32 aggregate is named:

- `DomainConflictReference`
- `DomainConflictCase`
- `DomainConflictResolution`
- `DomainConflictResolutionPolicy`

A resolver/orchestrator implementation may be named `DomainConflictResolver` provided it remains a pure policy engine and does not collide semantically with Cognitive Layer contradiction resolution.

## 3. Ownership boundaries

### 3.1 Phase 10.32 owns

- cross-subsystem conflict normalization;
- `DomainConflictReference`;
- `DomainConflictCase`;
- `DomainConflictResolution`;
- `DomainConflictResolutionPolicy`;
- closed enums for conflict kind, severity, status, source kind, and resolution strategy;
- authority classification;
- policy precedence;
- resolution reason codes;
- deterministic decision logic;
- blocking versus continuation decisions;
- preservation of unresolved conflict references;
- declarative decisions to ask the user, request human review, or postpone a dependent action.

### 3.2 Phase 10.32 does not own

- underlying conflict detection logic already implemented elsewhere;
- Cognitive Layer knowledge contradiction truth resolution;
- permission enforcement implementation;
- workflow execution;
- operation execution;
- approval execution;
- human-review execution;
- conversational question delivery;
- persistence of conflict cases or resolutions;
- session mutation;
- cross-turn conflict continuity;
- event emission;
- provider/model/tool logic;
- rewriting or deleting upstream conflict outputs.

Phase 10.33 owns event emission for this capability.

Phase 10.34 owns persistent/session continuity behavior where the roadmap assigns it.

Phase 8 remains authoritative for semantic knowledge contradiction resolution.

Phase 9 remains authoritative for Agent Runtime side effects and approvals.

## 4. Core principle

> Phase 10.32 may decide **what must happen next**. It must not perform that next action.

The resolver must therefore be side-effect free.

For identical immutable inputs and policy, the output must be identical.

No clock read, random identifier generation, memory write, session update, operation execution, workflow transition, approval mutation, event emission, or external call may occur inside conflict resolution.

Identifiers needed by the contracts must be supplied by the caller or derived deterministically from stable input identifiers if an existing project pattern explicitly supports that.

## 5. DomainConflictReference

`DomainConflictReference` is a minimal immutable pointer to an upstream conflict or contradiction.

Canonical semantic fields:

```text
DomainConflictReference
- source_kind
- source_id
- domain_id?
- blocking
- severity?
- authority_kind?
- evidence_refs[]
- metadata
```

### 5.1 Rules

- `source_kind` is a closed enum.
- `source_id` is mandatory and non-empty.
- `domain_id` is optional because not every upstream conflict belongs to exactly one domain.
- `blocking` is a strict boolean.
- `severity` may be normalized where the upstream source exposes a compatible severity.
- `authority_kind` may be supplied by a trusted adapter or derived by the orchestrator from `source_kind`.
- `evidence_refs` contains identifiers only, never copied evidence payloads.
- metadata is immutable, deeply frozen, purpose-minimized, and credential-safe.
- unknown serialization fields are rejected.
- no chain-of-thought, prompt content, secret, private reasoning payload, or unnecessary sensitive value may be copied into the reference.

### 5.2 Initial source kinds

The initial closed vocabulary must cover at least:

- `declared_domain_conflict`
- `composition_conflict`
- `permission_conflict`
- `profile_conflict`
- `rule_selection_conflict`
- `presentation_conflict`
- `cross_domain_contradiction`
- `knowledge_contradiction`
- `selection_conflict`
- `domain_specific_conflict`

Adding a source kind later is an additive contract change and must not silently reinterpret existing values.

## 6. DomainConflictCase

`DomainConflictCase` is the immutable normalized aggregate on which the Phase 10.32 policy operates.

Canonical semantic fields:

```text
DomainConflictCase
- id
- domains[]
- kind
- severity
- status
- references[]
- affected_item_refs[]
- candidate_strategies[]
- requires_human_review
- blocking
- metadata
```

### 6.1 Conflict kinds

The initial closed conflict-kind vocabulary should be general and mechanism-oriented rather than domain-slug-specific. It must support at least:

- `safety`
- `permission`
- `mandatory_rule`
- `domain_risk`
- `domain_precedence`
- `evidence`
- `reliability`
- `temporal`
- `preference`
- `recommendation`
- `presentation`
- `composition`
- `knowledge`
- `selection`
- `other`

A conflict kind describes the decision mechanism, not a hardcoded domain.

### 6.2 Severity

Phase 10.32 must use a small closed severity vocabulary sufficient to distinguish advisory, material, and blocking behavior.

Recommended canonical levels:

- `advisory`
- `material`
- `blocking`

`blocking=True` must be consistent with blocking severity. Contradictory serialized combinations are rejected.

### 6.3 Status

Canonical statuses:

- `OPEN`
- `RESOLVED`
- `UNRESOLVED`
- `BLOCKED`
- `AWAITING_USER`
- `AWAITING_HUMAN_REVIEW`
- `POSTPONED`

Status represents the state of the conflict case after policy evaluation, not persistence lifecycle.

### 6.4 Case invariants

- at least one reference is required;
- referenced IDs must be unique within a case;
- domains are deduplicated deterministically;
- a `RESOLVED` case cannot retain an unresolved blocking condition;
- `BLOCKED` requires a blocking unresolved condition;
- `AWAITING_USER` requires a strategy that legitimately delegates to user authority;
- `AWAITING_HUMAN_REVIEW` requires human review to be permitted and necessary;
- `POSTPONED` means the dependent action is deferred, not that the semantic conflict disappeared;
- `UNRESOLVED` preserves the discrepancy and must not claim a winner;
- caller-supplied status must never override contradictions derivable from the case contents.

## 7. DomainConflictResolution

`DomainConflictResolution` is the immutable decision output.

Canonical semantic fields:

```text
DomainConflictResolution
- conflict_id
- status
- strategy
- winning_reference_ids[]
- preserved_reference_ids[]
- rejected_reference_ids[]
- reason_codes[]
- requires_user_input
- requires_human_review
- action_postponed
- conflict_preserved
- can_proceed
- metadata
```

No `resolved_at` field belongs in the initial Phase 10.32 contract because the pure resolver must not own time.

If Phase 10.33 or later needs event timestamps, those phases add time to their own event/persistence records rather than making Phase 10.32 impure.

### 7.1 Resolution invariants

- every winning, preserved, or rejected ID must belong to the source case;
- one reference ID cannot simultaneously be winner and rejected;
- an unresolved blocking conflict requires `can_proceed=False`;
- `requires_user_input=True` requires `status=AWAITING_USER`;
- `requires_human_review=True` requires `status=AWAITING_HUMAN_REVIEW`;
- `action_postponed=True` requires `status=POSTPONED`;
- `conflict_preserved=True` must retain the relevant upstream reference IDs;
- no strategy may silently discard an upstream result;
- a resolution that rejects a reference must record an auditable reason code;
- `maintain_conflict` must never masquerade as semantic resolution;
- contradictory `from_dict()` payloads must be rejected.

## 8. DomainConflictResolutionPolicy

`DomainConflictResolutionPolicy` is immutable and validates strategy compatibility at construction time.

Canonical semantic fields:

```text
DomainConflictResolutionPolicy
- default_strategy
- blocking_strategy
- permission_strategy
- mandatory_rule_strategy
- high_risk_strategy
- primary_strategy
- evidence_strategy
- allow_separate_results
- allow_user_confirmation
- allow_human_review
- allow_postpone
- preserve_unresolved_conflicts
- metadata
```

Exact implementation field names may vary slightly if an existing repository convention makes another spelling materially clearer, but the semantics and invariants are frozen by this spec.

### 8.1 Policy defaults

Safe initial defaults:

- default unresolved behavior preserves the conflict;
- blocking conflicts fail closed;
- permission conflicts use most-restrictive authority;
- mandatory-rule conflicts use most-restrictive authority;
- high-risk conflicts prefer the most restrictive applicable risk authority;
- primary-domain precedence is permitted only after higher authority layers do not decide;
- evidence-weighted decisions require comparable structured evidence;
- separate results are permitted only when coexistence is safe;
- unresolved conflicts are preserved;
- user confirmation, human review, and postponement are declarative options, not actions.

### 8.2 Invalid policy configurations

The constructor must reject combinations that could weaken higher authority, including at least:

- `primary_domain_precedence` for blocking permission conflicts;
- evidence weighting that can override a denial or mandatory safety restriction;
- disabling preservation while allowing unresolved blocking conflicts;
- a blocking strategy that permits continuation without legitimate resolution;
- human-review strategy while human review is disabled;
- user-confirmation strategy while user confirmation is disabled;
- postponement strategy while postponement is disabled.

Unknown strategy strings and unknown serialization fields must be rejected.

## 9. Authority precedence

Conflict resolution uses strict layered precedence.

```text
HARD AUTHORITY
1. global safety
2. permissions
3. mandatory rules

DOMAIN AUTHORITY
4. highest-risk applicable domain
5. primary domain

EPISTEMIC AUTHORITY
6. evidence strength
7. source / claim reliability
8. temporal validity

HUMAN AUTHORITY
9. user confirmation / qualified human review
```

This is not an ordinary weighted score.

A lower layer cannot cancel a restriction already imposed by a higher layer.

Examples:

- stronger evidence cannot turn an authoritative permission `DENY` into `ALLOW`;
- primary-domain precedence cannot override a mandatory global rule;
- user preference cannot override global safety;
- temporal freshness can choose between otherwise comparable evidence but cannot widen permissions;
- human review may be required because the platform lacks authority; it is not an escape hatch for bypassing safety restrictions.

## 10. Highest-risk domain precedence

`high_risk_domain_precedence` is generic.

The engine must not contain hardcoded domain slugs such as Health, Legal, Finance, Mental Health, or any future pack name.

Risk authority must come from structured policy/profile/composition metadata already supplied by trusted contracts.

If the highest-risk applicable domain cannot be determined deterministically from structured inputs, this strategy cannot invent one. The conflict proceeds to the next legitimate strategy or remains unresolved/blocked.

## 11. Resolution strategies

The initial closed strategy vocabulary is:

### 11.1 `most_restrictive`

Default for:

- safety restrictions;
- permission conflicts;
- mandatory constraints;
- equivalent conflicts where conservative intersection is defined.

It must not manufacture a more permissive outcome than any authoritative higher-layer restriction.

### 11.2 `high_risk_domain_precedence`

Permitted only when:

- the conflict is domain-authority eligible;
- structured risk metadata exists;
- the highest-risk applicable authority is unique or otherwise deterministically resolvable;
- higher authority layers have not already blocked or decided the conflict.

### 11.3 `primary_domain_precedence`

Permitted only for non-blocking conflicts when:

- the primary domain participates in the conflict;
- no safety, permission, mandatory-rule, or higher-risk authority has already decided it;
- the conflict kind legitimately permits primary objective authority.

It must not resolve blocking declared incompatibilities merely because one side is primary.

### 11.4 `evidence_weighted`

Permitted only where:

- evidence is structurally comparable;
- evidence references are available;
- authority class is compatible;
- the comparison does not bypass a higher authority restriction.

A tie, incomparable evidence, or insufficient evidence produces no invented winner.

### 11.5 `separate_results`

Preserves multiple incompatible results when both may safely coexist.

It is forbidden when the dependent action requires one mutually exclusive decision or when coexistence could weaken safety, permission, mandatory-rule, or high-risk constraints.

### 11.6 `ask_user`

Used only when the user is a legitimate authority for the disputed preference or choice.

It must not delegate factual truth, safety policy, permission enforcement, or reserved professional decisions to user preference.

The output is declarative:

- `status=AWAITING_USER`
- `requires_user_input=True`
- `can_proceed=False` when the dependent decision cannot safely continue.

Phase 10.32 does not ask the question itself.

### 11.7 `human_review`

Used when a qualified or authorized human must decide.

The output is declarative:

- `status=AWAITING_HUMAN_REVIEW`
- `requires_human_review=True`

Phase 10.32 does not create, route, or complete the approval/review request.

### 11.8 `postpone_action`

Defers the action that depends on the unresolved conflict.

The conflict remains preserved.

`POSTPONED` is not semantic conflict resolution.

### 11.9 `maintain_conflict`

Explicitly preserves disagreement when there is no legitimate basis to choose a winner.

For blocking conflicts:

- status must remain `BLOCKED` or otherwise clearly unresolved-blocking;
- `can_proceed=False`.

For non-blocking conflicts:

- status may be `UNRESOLVED`;
- safe independent work may continue only if it does not depend on the disputed outcome.

## 12. Universal invariants

The implementation must enforce all of the following:

```text
unresolved blocking conflict => can_proceed = False

lower authority never weakens higher authority

personal preference conflict =>
    never auto-resolve from confidence or scoring alone

no strategy may discard an upstream result
without retaining its reference and reason

maintain_conflict != semantic resolution

postpone_action != semantic resolution

same immutable inputs + same policy => same output

Phase 10.32 decides; it does not execute
```

## 13. Adapters and normalization

Phase 10.32 uses small pure adapters.

Each adapter maps an existing conflict contract into one or more `DomainConflictReference` values without changing the source contract.

Initial adapter coverage must include at least:

1. declared `DomainConflict`;
2. `DomainCompositionConflict`;
3. `DomainPermissionConflict`;
4. `DomainProfileConflict`;
5. `DomainRuleSelectionConflict`;
6. `DomainPresentationConflict`;
7. `CrossDomainContradiction`;
8. Cognitive `Contradiction` by reference;
9. Phase 10.31 selection ambiguity/conflict where applicable.

Domain-specific conflicts may use a generic adapter only when they expose enough trusted structured metadata. Phase 10.32 must not parse arbitrary prose to infer authority or severity.

### 13.1 Adapter rules

Adapters must:

- be pure;
- preserve source identity;
- preserve blocking semantics;
- preserve domain participation where known;
- copy only safe categorical metadata;
- never mutate the source object;
- never downgrade source severity;
- never upgrade authority based on untrusted free text;
- reject malformed or contradictory inputs fail-closed.

## 14. Resolution flow

Canonical flow:

```text
existing conflict outputs
        ↓
normalize references
        ↓
build DomainConflictCase
        ↓
classify authority / severity / blocking
        ↓
apply DomainConflictResolutionPolicy
        ↓
evaluate precedence layers in order
        ↓
select first legitimate decisive strategy
        ↓
DomainConflictResolution
        ↓
continue | block | await user | await human | postpone
```

No downstream strategy is evaluated as a way to reverse a decision already made by a higher authority layer.

## 15. Relationship with Phase 10.31

Phase 10.31 owns domain selection policy and ordinary ambiguity handling.

Phase 10.32 owns richer conflict policy after a conflict requiring cross-authority resolution exists.

Phase 10.32 must not change the frozen 10.31 selection precedence:

1. safety/authorization/availability;
2. explicit;
3. session continuity;
4. active goal;
5. ordinary structured evidence;
6. primary confidence;
7. supporting confidence;
8. General fallback.

Selection ambiguity may be adapted into a conflict case where appropriate, but 10.32 must not reintroduce score-based arbitrary tie breaking prohibited by 10.31.

## 16. Relationship with Domain Composition

Existing `DomainConflictPolicy` remains a Domain Composition policy and is not promoted into the universal Phase 10.32 policy.

Existing composition behavior such as:

- `MOST_RESTRICTIVE`;
- `PRIMARY_PRECEDENCE`;
- `BLOCK_ON_CONFLICT`;

remains valid within composition.

Phase 10.32 may consume resulting `DomainCompositionConflict` records and decide what the wider platform must do next.

The universal resolver must not silently rewrite composition results.

## 17. Relationship with permissions

Permissions remain authoritative.

A Phase 10.32 conflict resolution:

- cannot convert permission denial into allowance;
- cannot bypass required approval;
- cannot treat a supporting domain's allowance as stronger than a denial;
- must preserve the permission conflict reference and outcome;
- may declare human review/approval required only through existing authorization boundaries.

Permission conflicts default to fail-closed most-restrictive behavior.

## 18. Relationship with Cognitive Layer contradictions

Knowledge truth resolution remains owned by Phase 8.

When Phase 10.32 receives a cognitive contradiction reference:

- it may decide that dependent domain work must block, continue partially, await review, or preserve separate results;
- it may use the already-resolved Cognitive Layer outcome;
- it must not independently decide which claim is factually true;
- it must not mutate `Contradiction`;
- it must not create a second persistent contradiction store.

## 19. Reason codes and auditability

Every non-trivial decision must emit stable reason codes.

The initial family should include equivalents of:

- `DOMAIN_CONFLICT_SAFETY_PRECEDENCE`
- `DOMAIN_CONFLICT_PERMISSION_PRECEDENCE`
- `DOMAIN_CONFLICT_MANDATORY_RULE_PRECEDENCE`
- `DOMAIN_CONFLICT_HIGH_RISK_PRECEDENCE`
- `DOMAIN_CONFLICT_PRIMARY_PRECEDENCE`
- `DOMAIN_CONFLICT_EVIDENCE_PRECEDENCE`
- `DOMAIN_CONFLICT_RELIABILITY_PRECEDENCE`
- `DOMAIN_CONFLICT_TEMPORAL_PRECEDENCE`
- `DOMAIN_CONFLICT_USER_INPUT_REQUIRED`
- `DOMAIN_CONFLICT_HUMAN_REVIEW_REQUIRED`
- `DOMAIN_CONFLICT_ACTION_POSTPONED`
- `DOMAIN_CONFLICT_SEPARATE_RESULTS`
- `DOMAIN_CONFLICT_PRESERVED`
- `DOMAIN_CONFLICT_BLOCKING_UNRESOLVED`
- `DOMAIN_CONFLICT_INSUFFICIENT_BASIS`
- `DOMAIN_CONFLICT_STRATEGY_NOT_APPLICABLE`

Exact string names may be normalized to the repository's existing reason-code style, but tests must freeze the chosen public values.

Reason codes record decisions, not private reasoning.

## 20. Serialization and immutability

All new public Phase 10.32 contracts must follow established Domain Intelligence contract quality:

- frozen dataclasses or equivalent immutable structures;
- strict type validation;
- strict booleans;
- closed enums;
- deterministic tuple ordering where semantic order is not caller-significant;
- deeply frozen metadata;
- `to_dict()` / `from_dict()` round-trip;
- unknown field rejection;
- contradictory deserialized state rejection;
- no credential-like metadata keys where existing project safety helpers prohibit them;
- no mutation through retained caller-owned dictionaries/lists.

## 21. Public API

The final public API should expose the stable user-facing Phase 10.32 contracts and resolver from `cmm.domains`.

At minimum:

- `DomainConflictReference`
- `DomainConflictCase`
- `DomainConflictResolution`
- `DomainConflictResolutionPolicy`
- conflict status/kind/source/strategy enums selected by implementation
- the pure resolver/orchestrator

Existing `DomainConflict` and `DomainConflictPolicy` exports must remain backward compatible.

No public symbol from previous completed phases may be renamed or semantically repurposed.

## 22. Error handling

Invalid contracts raise typed Domain conflict-resolution contract errors consistent with existing `cmm.domains.errors` patterns.

Runtime policy evaluation should prefer structured blocked/unresolved outputs over exceptions for legitimate conflicts.

Exceptions are reserved for invalid programmer inputs, malformed contracts, impossible invariant combinations, unsupported enum values, or corrupted serialized payloads.

A real conflict is data, not an exceptional crash condition.

## 23. Testing strategy

Implementation must be TDD.

Every production behavior change begins with an observed failing test.

### 23.1 Contract tests

Cover:

- valid construction;
- immutability;
- strict booleans;
- enums;
- deep metadata freezing;
- unknown fields;
- round-trip;
- malformed references;
- duplicate references;
- contradictory status/flags;
- contradictory resolution payloads.

### 23.2 Adapter tests

At minimum one connected adapter test for every required upstream conflict family.

Verify:

- source identity preserved;
- blocking preserved;
- domains preserved where available;
- no source mutation;
- no sensitive payload copying;
- malformed source fails closed.

### 23.3 Precedence tests

Freeze the exact authority order:

1. safety;
2. permissions;
3. mandatory rules;
4. highest-risk applicable domain;
5. primary domain;
6. evidence;
7. reliability;
8. temporal validity;
9. user/human authority.

Adversarial cases must prove lower layers cannot reverse higher layers.

### 23.4 Strategy tests

Cover every strategy and invalid cross-strategy use.

Especially:

- permission deny cannot be defeated by primary precedence;
- blocking declared conflict cannot be resolved by primary precedence;
- evidence tie preserves conflict;
- incomparable evidence preserves conflict;
- separate results forbidden when unsafe;
- ask-user only for legitimate user authority;
- human review declarative only;
- postpone preserves conflict;
- maintain-conflict keeps blocking state blocking.

### 23.5 Purity tests

Verify resolver does not:

- mutate inputs;
- read time;
- generate random values;
- modify sessions;
- execute workflows;
- execute operations;
- emit events;
- invoke approvals;
- write memory.

### 23.6 Integration tests

Connected integration must exercise at least:

- composition conflict → universal case → resolution;
- permission conflict → universal case → fail-closed decision;
- profile/rule conflict → universal case;
- cross-domain contradiction → preserved reference;
- cognitive contradiction reference → no duplicate truth resolution;
- Phase 10.31 selection ambiguity → no forbidden score tie-break.

### 23.7 Acceptance gate

Create `AT-DP-032` as a connected acceptance suite.

It must verify all normative Phase 10.32 boundaries, not merely constructor coverage.

The final checkpoint count is determined by implementation coverage and must be reported from fresh test output rather than predeclared in this spec.

## 24. Non-goals

Phase 10.32 does not:

- create a universal persistence store;
- create conflict events;
- implement session continuity;
- replace `DomainConflict`;
- replace `DomainConflictPolicy`;
- replace `Contradiction`;
- replace Cognitive Layer resolution;
- infer high-risk domains from hardcoded slugs;
- parse arbitrary prose to determine authority;
- ask the user directly;
- perform human review;
- create approval requests;
- execute or retry actions;
- rewrite prior operation results;
- auto-resolve personal preferences from model confidence;
- hide incompatible recommendations;
- discard losing results without traceability.

## 25. Expected implementation shape

The implementation should prefer small focused modules.

A likely shape is:

```text
cmm/domains/
├── conflict_resolution_contracts.py
├── conflict_resolution.py
├── conflict_adapters.py
└── __init__.py
```

This is guidance, not a requirement to force files when existing module boundaries suggest a cleaner minimal arrangement.

Do not place the entire feature into `resolver.py` or another already large unrelated module merely to reduce file count.

## 26. Definition of done

Phase 10.32 implementation is complete only when:

1. all approved contracts exist and are immutable/strict;
2. required upstream conflict families have pure normalization adapters;
3. layered precedence is implemented exactly;
4. all approved strategies are implemented with compatibility guards;
5. blocking unresolved conflicts always fail closed;
6. upstream results remain referenced and auditable;
7. Phase 8 contradiction ownership is preserved;
8. Phase 10.31 behavior remains intact;
9. no side effects occur in the resolver;
10. public API is stable and backward compatible;
11. AT-DP-032 is connected and passing;
12. focused, Domain, and global suites pass;
13. changed Python delta passes Ruff, format, and syntax gates;
14. documentation and requirements matrix are updated without marking independent audit complete;
15. a full-HEAD TAR.GZ audit bundle is generated;
16. ChatGPT performs the independent closure audit;
17. only a clean independent audit may advance the roadmap to Phase 10.33.

## 27. Frozen design decisions

The following are frozen for implementation:

1. Phase 10.32 is a universal conflict orchestration layer.
2. Existing conflict contracts remain authoritative and are referenced, not replaced.
3. Existing `DomainConflict` keeps its current meaning.
4. The universal aggregate is `DomainConflictCase`.
5. Resolution is deterministic and pure.
6. Authority uses strict layered precedence, not weighted scoring.
7. Lower authority never weakens higher authority.
8. Most-restrictive behavior is the safe default for safety/permissions/mandatory constraints.
9. Highest-risk precedence is metadata-driven and domain-slug-agnostic.
10. Primary-domain precedence is limited to eligible non-blocking conflicts.
11. Evidence weighting requires comparable structured evidence.
12. Ties and insufficient evidence preserve ambiguity/conflict.
13. User confirmation applies only where the user is a legitimate authority.
14. Human review is declarative and does not execute review.
15. Postponement does not semantically resolve a conflict.
16. Maintaining a conflict is a valid policy outcome but not semantic resolution.
17. An unresolved blocking conflict always prevents dependent continuation.
18. No upstream result may disappear without retained reference and reason.
19. Phase 8 remains the knowledge contradiction truth authority.
20. Phase 10.33 owns events; later phases own persistence/session continuity.
