# Phase 10.31 — Domain Selection Policies Design

**Date:** 2026-08-27
**Phase:** 10.31 — Domain Selection Policies
**Status:** Design approved; implementation not started
**Branch:** `feature/phase-10-domain-intelligence`

## 1. Objective

Phase 10.31 defines explicit, deterministic, auditable policies for selecting
the primary and supporting domains from the structured evidence already
available to the shared Domain Resolution subsystem.

The phase must extend the existing resolver architecture rather than create a
parallel classifier, resolver, orchestration engine, session subsystem, event
subsystem, or conflict-resolution subsystem.

The design preserves the existing separation between:

- scoring evidence;
- authorization and safety policy;
- domain selection policy;
- domain composition;
- profile, permission, and rule resolution;
- workflow/session persistence implemented by later phases.

## 2. Existing Architecture Reused

Phase 10.31 builds on the existing shared components:

- `DomainResolutionContext`
- `DomainResolutionContextBuilder`
- `DomainScoringPolicy`
- `DomainCandidateScorer`
- `DefaultDomainResolver`
- `DomainResolutionResult`
- `DomainResolutionReason`
- `DomainResolutionPolicy`
- `DomainCompositionPolicy`
- `DefaultDomainComposer`
- profile resolution/composition
- permission resolution/gating
- rule selection
- domain trace contracts and validation
- Cross-Domain Engine integration

The existing resolver already provides:

- structured candidate scoring;
- explicit-domain evidence;
- session and goal signal kinds;
- active-domain evidence;
- ambiguity detection;
- high-impact confidence protection;
- supporting-domain selection;
- bounded supporting-domain counts;
- General Domain fallback;
- fail-closed fallback protection;
- deterministic sorting;
- structured reasons;
- candidate score traceability.

Phase 10.31 formalizes the missing selection semantics around these mechanisms.

## 3. Architectural Decision

Introduce a first-class immutable `DomainSelectionPolicy` consumed by the
existing `DefaultDomainResolver`.

The architecture becomes:

```text
DomainScoringPolicy
    |
    |  determines evidence contribution
    v
DomainCandidateScorer
    |
    v
DomainResolutionPolicy
    |
    |  authorization / availability / safety constraints
    v
DomainSelectionPolicy
    |
    |  selection precedence and confidence requirements
    v
DefaultDomainResolver
    |
    v
DomainResolutionResult
    |
    v
DefaultDomainComposer
```

`DomainScoringPolicy` remains responsible only for scoring evidence.

`DomainResolutionPolicy` remains responsible for safety, authorization,
allowed/denied domains, statuses, and high-impact constraints.

`DomainSelectionPolicy` owns how eligible evidence is converted into primary
and supporting domain choices.

No new domain resolver or selection engine is introduced.

## 4. DomainSelectionPolicy Contract

The canonical contract is:

```python
DomainSelectionPolicy(
    name="default",
    explicit_domain_priority=True,
    session_domain_priority=True,
    goal_domain_priority=True,
    allow_multi_domain=True,
    maximum_supporting_domains=3,
    minimum_primary_confidence=0.70,
    minimum_supporting_confidence=0.55,
    fallback_domain="domain:general",
    ambiguity_strategy="clarify_or_fallback",
    metadata={},
)
```

The contract is:

- immutable;
- JSON-serializable;
- strict about unknown fields;
- strict about booleans;
- confidence values constrained to `[0.0, 1.0]`;
- `maximum_supporting_domains >= 0`;
- metadata JSON-safe and deep-frozen;
- credential-like metadata keys rejected following existing domain contract
  conventions.

The fallback domain is represented canonically as a `DomainId`.

The initial supported ambiguity strategy is:

```text
clarify_or_fallback
```

Additional strategies are out of scope until required by a later phase.

## 5. Separation of Scoring and Selection

The existing scoring system remains unchanged in responsibility.

For example:

```text
explicit_weight
session_weight
goal_weight
resource_weight
entity_weight
objective_weight
...
```

continue to express the strength of evidence.

They must not be relied upon to provide hard policy precedence.

Selection policy is applied after eligibility and safety filtering.

This distinction prevents a large accumulation of unrelated evidence from
silently overriding an explicit user selection when the explicit domain is
otherwise eligible.

## 6. Selection Precedence

The resolver applies the following precedence:

```text
1. safety / authorization / availability
2. explicit domain policy
3. session continuity policy
4. active-goal policy
5. normal structured evidence
6. primary confidence gate
7. supporting-domain confidence gate
8. General fallback
```

Safety always dominates selection preference.

Selection policy cannot make an unavailable, unauthorized, denied, invalid,
disabled-disallowed, degraded-disallowed, or otherwise fail-closed domain
eligible.

## 7. Explicit First Policy

When `explicit_domain_priority=True`:

### Single eligible explicit domain

A single explicitly requested eligible domain becomes primary regardless of
ordinary candidate score ordering.

Normal scoring remains available for:

- audit evidence;
- confidence;
- supporting-domain selection;
- diagnostics.

### Explicit safety conflict

An explicit domain does not override:

- authorization;
- denied-domain policy;
- availability;
- incompatible or failed status;
- disabled/degraded restrictions;
- required fail-closed safety rules.

The resolver returns the existing blocked/rejected semantics.

### Multiple eligible explicit domains

Two or more eligible explicit domains are not resolved by arbitrary ordering.

They enter ambiguity handling unless a later conflict-resolution phase
provides a stronger deterministic rule.

Phase 10.31 must not implement Phase 10.32 Domain Conflict Resolution.

## 8. Session Continuity Policy

When `session_domain_priority=True`, a canonical structured session-domain
signal may influence selection while that domain remains:

- available;
- authorized;
- relevant;
- sufficiently confident;
- compatible with safety constraints.

Phase 10.31 does not implement persistent Domain Sessions.

Instead, `DomainResolutionContextBuilder` gains an explicit input capable of
representing the current session domain and translates that input into the
existing structured domain-resolution evidence model.

The session domain must not be inferred merely from registry
`active_domains`.

Registry activation and conversational/session continuity remain distinct
concepts.

Phase 10.34 will own persistent session state.

## 9. Goal Priority Policy

When `goal_domain_priority=True`, the active goal domain is a strong structured
selection signal.

Phase 10.31 does not implement persistent goal ownership or a new goal store.

`DomainResolutionContextBuilder` accepts an explicitly supplied active goal
domain and converts it into the existing structured `goal` evidence path.

The resolver therefore remains independent from live goal stores.

The existing `goal_id` remains correlation information and is not sufficient
by itself to infer a goal domain.

## 10. Session and Goal Disagreement

Phase 10.31 must not silently invent a conflict policy that belongs to Phase
10.32.

When session-domain and active-goal-domain evidence materially conflict and no
higher-precedence explicit selection resolves the situation:

- normal evidence may resolve the result when one candidate clearly satisfies
  the configured selection requirements;
- otherwise the result is ambiguous and clarification is required.

No slug-based or alphabetical policy may decide semantic conflicts.

## 11. Primary Confidence Policy

An inferred primary domain must satisfy:

```text
minimum_primary_confidence = 0.70
```

unless a stricter safety/high-impact rule applies.

Explicit-domain selection still remains subject to safety constraints.
Confidence remains recorded even where explicit precedence selects the primary
domain.

A candidate that fails the required primary confidence cannot become an
ordinary inferred primary merely because its raw score is highest.

## 12. High-Risk Conservative Policy

Phase 10.31 reuses the existing generic high-impact-domain mechanism.

No hardcoded medical, legal, or financial slug checks are added to the
resolver.

High-impact domains are supplied through canonical resolution policy and
remain subject to the stricter confidence requirement already supported by
the resolver.

The effective confidence floor is the most restrictive applicable threshold.

Conceptually:

```text
effective minimum confidence
    =
max(
    selection minimum,
    high-impact minimum when applicable,
    system-policy minimum when applicable,
)
```

This preserves domain-agnostic shared infrastructure.

## 13. Multi-Domain Limited Policy

When `allow_multi_domain=False`:

```text
supporting_domains = ()
```

When `allow_multi_domain=True`, supporting candidates must:

- be eligible;
- not equal the primary;
- satisfy safety and authorization policy;
- satisfy `minimum_supporting_confidence`;
- satisfy existing supporting relevance/margin rules where applicable;
- fit within `maximum_supporting_domains`.

Canonical default:

```text
maximum_supporting_domains = 3
minimum_supporting_confidence = 0.55
```

The configured limit is a hard upper bound.

Required-domain policy must not silently overflow the selection-policy bound.
An impossible required-domain composition fails closed or surfaces an explicit
policy conflict rather than violating the configured maximum.

Detailed conflict semantics remain Phase 10.32 territory.

## 14. General Fallback Policy

The canonical default fallback is:

```text
domain:general
```

The existing fail-closed fallback semantics are preserved.

General may be selected when specialized evidence is insufficient and General
itself is:

- available;
- authorized where authorization is required;
- allowed by policy;
- status-compatible.

General must never hide the failure of an explicitly or structurally signaled
specialized domain that is unavailable, denied, unauthorized, disabled,
disallowed, or otherwise rejected for a fail-closed reason.

Fallback does not broaden permissions.

Fallback does not become an automatic supporting domain.

## 15. Ambiguity Policy

The initial strategy is:

```text
clarify_or_fallback
```

When ambiguity is material:

- the resolver records the ambiguous domains;
- clarification is requested;
- a deterministic recommended question is produced;
- General may be used only if existing fail-closed fallback rules permit it.

No arbitrary tie-breaking is introduced.

Domain slug ordering may only provide deterministic serialization/sorting,
never semantic preference.

## 16. Reevaluation Policy

A domain composition may change when new structured information arrives during
a workflow.

Phase 10.31 introduces a pure immutable transition contract:

```text
DomainSelectionTransition
```

It compares the previous resolution/composition with the new one.

The transition records at minimum:

- previous resolution ID (`previous_resolution_id`);
- new resolution ID (`new_resolution_id`);
- previous primary domain;
- new primary domain;
- previous supporting domains;
- new supporting domains;
- whether the primary changed;
- whether supporting composition changed;
- structured change reason codes;
- whether downstream recomposition is required;
- whether a session-state update is required.

The transition does not mutate session state.

The transition does not execute operations.

The transition does not persist data.

## 17. Domain Change Lifecycle

When the primary domain changes:

1. the reason is recorded;
2. user/workflow context is preserved;
3. domain composition is recalculated;
4. profiles are recalculated;
5. permissions are recalculated;
6. rules are recalculated;
7. unresolved clarification requirements are recalculated;
8. already-completed operations are not automatically executed again;
9. a session-update requirement is emitted for the future session owner.

Phase 10.31 establishes the typed selection transition and recomposition
requirement.

It does not implement the Phase 10.34 persistent session-update mechanism.

## 18. Duplicate Operation Boundary

Domain reevaluation itself is pure.

It must never execute or replay operations.

Therefore a change from one domain composition to another cannot directly
duplicate an already-executed operation.

The workflow/runtime layer remains responsible for execution identity and
idempotency.

The transition contract makes the domain change explicit so downstream
workflow logic can decide whether pending work must be replanned.

## 19. Traceability

Every selection remains auditable through existing:

- candidate scores;
- structured resolution reasons;
- primary/supporting domain fields;
- resolution IDs;
- context IDs;
- trace references.

Phase 10.31 adds stable reason codes for policy decisions where existing reason
codes are insufficient.

Expected policy-level reasons include equivalents of:

```text
DOMAIN_SELECTION_EXPLICIT_PRIORITY
DOMAIN_SELECTION_SESSION_PRIORITY
DOMAIN_SELECTION_GOAL_PRIORITY
DOMAIN_SELECTION_PRIMARY_CONFIDENCE_REJECTED
DOMAIN_SELECTION_SUPPORTING_CONFIDENCE_REJECTED
DOMAIN_SELECTION_MULTI_DOMAIN_DISABLED
DOMAIN_SELECTION_REEVALUATED
DOMAIN_SELECTION_PRIMARY_CHANGED
DOMAIN_SELECTION_COMPOSITION_CHANGED
```

Exact names may be adjusted during implementation only if they remain stable,
namespaced, deterministic, and covered by acceptance tests.

## 20. Public API

The public domain package must export the new canonical contracts required by
consumers, including at minimum:

```python
DomainSelectionPolicy
DomainSelectionTransition
```

The existing public exports remain backward compatible.

Existing callers that construct `DefaultDomainResolver` without an explicit
selection policy receive the canonical default selection policy.

## 21. Compatibility

Phase 10.31 must preserve:

- existing resolver protocol;
- existing domain bootstrap behavior;
- existing General fallback guarantees;
- existing Health/high-impact fail-closed behavior;
- existing composition contracts;
- existing domain registration;
- existing trace integrity;
- existing serialized contracts unless intentionally extended.

No migration of stored mutable state is required because the new selection
contracts are immutable configuration/result contracts.

## 22. Expected Implementation Surface

Primary new modules:

```text
cmm/domains/selection_contracts.py
cmm/domains/selection.py
```

Focused integration changes:

```text
cmm/domains/resolver.py
cmm/domains/resolution_builder.py
cmm/domains/__init__.py
```

Expected dedicated tests:

```text
tests/domains/test_domain_selection_policy.py
tests/domains/test_domain_selection_transition.py
tests/domains/test_domain_selection_policy_dp031_acceptance.py
```

Additional existing resolver/composer tests may be extended where that is
clearer than creating duplicate test scaffolding.

The exact file surface may shrink during implementation if existing modules
provide a cleaner canonical home.

## 23. Non-Goals

Phase 10.31 explicitly does not implement:

- free-text classification;
- LLM-based routing;
- a second resolver;
- a new cross-domain engine;
- Phase 10.32 Domain Conflict Resolution;
- Phase 10.33 Domain Events;
- Phase 10.34 persistent Domain Sessions;
- a new goal store;
- operation execution;
- workflow persistence;
- broad refactors unrelated to selection policy;
- domain-specific medical/legal/financial slug conditionals.

## 24. Failure Semantics

Selection remains fail-closed.

Invalid policy configuration fails during contract construction.

Impossible selection constraints do not silently relax themselves.

Blocked specialized-domain evidence is not degraded into General merely to
produce a result.

Unknown ambiguity strategies are rejected.

Unsafe or unauthorized explicit requests remain blocked.

Required-domain constraints that cannot coexist with the configured hard
selection limit surface an explicit failure/conflict rather than overflow.

## 25. Testing Strategy

Testing follows TDD and must cover five levels.

### Contract tests

Validate:

- defaults;
- immutability;
- strict bool handling;
- confidence ranges;
- maximum supporting-domain bounds;
- fallback DomainId coercion;
- metadata freezing;
- serialization round trips;
- unknown-field rejection;
- invalid ambiguity strategies.

### Resolver policy tests

Validate:

- eligible explicit domain wins;
- explicit domain never overrides safety;
- multiple explicit domains become ambiguous;
- session continuity works only when valid;
- goal priority works only when valid;
- registry-active is not treated as synonymous with session domain;
- session/goal conflict is deterministic;
- primary confidence gate;
- high-impact stricter confidence;
- General fallback;
- blocked specialized domain cannot degrade to General.

### Multi-domain tests

Validate:

- `allow_multi_domain=False`;
- supporting confidence floor;
- maximum supporting domains equals three by default;
- configured lower limits;
- deterministic supporting order;
- no duplicate primary/supporting domain;
- impossible required-domain overflow fails closed.

### Reevaluation tests

Validate:

- unchanged resolution produces no change;
- primary-domain change is detected;
- supporting-only change is detected;
- reason codes are deterministic;
- recomposition requirement is emitted;
- session-update requirement is emitted on relevant change;
- transition never executes operations.

### Regression / integration tests

Run:

- focused selection tests;
- existing resolver tests;
- composition tests;
- profile/rule/permission integration tests;
- General fallback tests;
- Health/high-impact tests;
- domain suite;
- global suite;
- Ruff;
- format check;
- compileall.

## 26. Design Point

### DP-031 — Domain Selection Policies

> CMM OS provides a first-class, immutable and auditable domain selection
> policy that deterministically applies safety-first explicit-domain
> precedence, structured session continuity, active-goal priority,
> confidence-gated primary and supporting selection, conservative high-impact
> routing, bounded multi-domain composition, fail-closed General fallback, and
> typed domain-selection reevaluation without introducing a parallel resolver
> or prematurely implementing later conflict, event, or session phases.

## 27. Acceptance Test

### AT-DP-031 — Domain Selection Policies Acceptance

AT-DP-031 passes only when automated acceptance coverage proves all of the
following:

1. the canonical `DomainSelectionPolicy` contract exists and round-trips;
2. explicit eligible user selection has deterministic precedence;
3. safety and authorization override explicit preference;
4. multiple explicit candidates never resolve by arbitrary tie-break;
5. structured session-domain continuity is supported independently of registry
   activation;
6. structured active-goal-domain priority is supported;
7. session/goal disagreement is deterministic and does not pre-implement
   Phase 10.32;
8. inferred primary domains satisfy the configured primary confidence floor;
9. high-impact domains use the most restrictive applicable confidence floor;
10. supporting domains satisfy their confidence floor;
11. multi-domain selection can be disabled;
12. supporting domains never exceed the configured hard maximum;
13. General is a real insufficient-evidence fallback;
14. General never bypasses a fail-closed specialized-domain rejection;
15. ambiguity supports clarification and safe fallback behavior;
16. reevaluation detects primary and supporting composition changes;
17. reevaluation emits stable reasons;
18. a primary change requires downstream recomposition;
19. a relevant composition change can request session-state update without
    mutating session state;
20. reevaluation itself never executes or duplicates operations;
21. existing resolver, composition, permission, profile, rule, trace,
    General-fallback, and high-impact invariants remain green;
22. the full Phase 10/domain/global quality gates remain green.

## 28. Completion Criterion

Phase 10.31 is implementation-complete only when:

- DP-031 is implemented;
- AT-DP-031 is connected and passing;
- dedicated adversarial tests pass;
- shared-domain regressions pass;
- documentation and requirements matrix contain the final implementation
  evidence;
- an audit TAR.GZ is generated from the final HEAD;
- independent audit by ChatGPT returns PASS with no unresolved blockers,
  majors, or minors;
- closure documentation is committed.

Push and merge remain separate explicit decisions.
