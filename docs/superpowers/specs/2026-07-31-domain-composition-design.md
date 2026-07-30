# Phase 10.8 — Domain Composition

## Objective

Compose a resolved set of domains into one immutable, declarative effective configuration without executing workflows, mixing runtime engines, duplicating enforcement, or hiding conflicts.

## Inputs

The composer receives a `DomainResolutionResult`, the corresponding immutable `DomainDefinition` instances, an explicit composition policy, and optional injected clock and identifier factory.

It does not access the registry, filesystem, stores, network, LLMs, cognitive runtime, agent runtime, or workflow engine.

## Architecture

```text
DomainResolutionResult
        +
DomainDefinition collection
        +
DomainCompositionPolicy
        ↓
DomainComposer
        ↓
DomainComposition
```

## Scope

Phase 10.8 implements immutable composition contracts, deterministic domain composition, effective reasoning profile, rule/resource/operation/workflow composition, permission intersection, presentation composition, deduplication decisions, conflict detection, provenance, public API and tests.

It does not implement execution, runtime authorization, agent-runtime integration, cognitive integration, cross-domain coordination, persistence, registry lookup, events, memory updates, approval workflows, LLMs or network access.

## Primary and supporting semantics

The primary domain determines the main objective, base reasoning profile, central workflow precedence, presentation baseline and priority rules.

Supporting domains may add resources, rules, restrictions, auxiliary operations, workflows, validators and complementary presentation properties. They may restrict the primary domain but cannot silently replace its identity.

## Composition status

`DomainCompositionStatus`:

- `COMPOSED`
- `PARTIAL`
- `BLOCKED`
- `FAILED`

`COMPOSED` means all selected domains were found and no unresolved blocking conflict exists.

`PARTIAL` means composition is safe but optional elements were excluded or degraded with explicit decisions.

`BLOCKED` means a required domain, dependency, permission or conflict prevents safe composition.

`FAILED` is reserved for controlled internal failures and must not hide contract or programming errors.

## Conflict policy

Default: `MOST_RESTRICTIVE`.

Supported:

- `MOST_RESTRICTIVE`
- `PRIMARY_PRECEDENCE`
- `BLOCK_ON_CONFLICT`

A supporting domain may not silently weaken a primary-domain prohibition. Every conflict decision must be represented in the result.

## Effective reasoning profile

Composition produces one `EffectiveReasoningProfile`, not parallel cognitive engines.

The primary domain profile becomes the base. Supporting profiles are contributors. Only structured domain definitions or explicit policy may affect the result. No free-text inference is allowed.

## Rules

Deterministic order:

1. mandatory global rules;
2. security rules;
3. primary-domain rules;
4. supporting-domain rules;
5. optional rules;
6. presentation rules.

Exact duplicate references are collapsed while preserving all contributing domains. Non-equivalent conflicts are reported rather than semantically interpreted.

## Resources, operations and workflows

Resources are composed as a deterministic union of references with provenance.

Operations are composed as a union and filtered declaratively by effective permissions, composition policy, declared conflicts and structured approval requirements. Nothing is executed.

Primary workflows receive precedence. Supporting workflows remain auxiliary. Exact duplicates are collapsed. Semantic equivalence requires explicit metadata.

## Permissions

Permission composition is restrictive by default:

- required permissions accumulate;
- denied permissions prevail;
- operations requiring denied or absent permissions are excluded;
- every exclusion produces a decision.

The result distinguishes required, granted/common, denied and unresolved permissions. Runtime actor authorization remains outside this phase.

## Presentation

The primary domain provides the baseline. Supporting domains may fill missing properties but cannot silently overwrite primary values. Conflicts follow the selected policy and are recorded.

## Dependencies and conflicts

Missing required dependencies block composition. Missing optional dependencies produce `PARTIAL`. Cycles are reported deterministically. No domain is loaded automatically.

Declared domain conflicts are evaluated only among selected domains. Blocking/high-severity incompatibilities produce `BLOCKED`; non-blocking incompatibilities produce explicit conflict records and may produce `PARTIAL`.

## Deduplication

Detect exact duplicate rules, resources, operations, workflows, validators, capabilities and presentation entries. Preserve complete provenance. Do not infer duplicate entities, questions, memory writes or runtime effects.

## Public contracts

Expected:

- `DomainCompositionStatus`
- `DomainConflictPolicy`
- `DomainCompositionPolicy`
- `DomainCompositionItem`
- `DomainCompositionDecision`
- `DomainCompositionConflict`
- `EffectiveReasoningProfile`
- `PermissionComposition`
- `PresentationComposition`
- `DomainComposition`
- `DomainComposer`
- `DefaultDomainComposer`

All contracts are immutable, deeply frozen, JSON-safe and support strict `to_dict()` / `from_dict()` round trips. Unknown fields are rejected. Datetimes must be timezone-aware. Boolean and numeric validation is strict.

## Determinism

Identical resolution, definitions, policy, clock and ID factory must produce identical composition content and ordering.

Order by primary domain, resolver supporting order, category priority, domain precedence and identifier. Conflicts and decisions use stable deterministic ordering.

## Error handling

Contract errors propagate as domain composition contract or serialization errors. Configuration errors use dedicated composition errors. The composer must not catch `Exception` broadly or leak arbitrary exception text.

## Testing

Cover contracts, serialization, immutability, precedence, profile composition, restrictive permissions, rule ordering, deduplication, provenance, presentation conflicts, dependencies, cycles, declared conflicts, partial/blocked outcomes, determinism, clock/ID validation, public API, no runtime/registry imports and all regression suites.
