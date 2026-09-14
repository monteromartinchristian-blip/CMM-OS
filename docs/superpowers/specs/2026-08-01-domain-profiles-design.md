# Phase 10.11 Domain Profiles Design

## Status

Approved design for implementation planning.

## Objective

Implement declarative Domain Profiles that configure the Phase 8 Cognitive Layer per domain without creating separate reasoning engines.

A domain profile defines constraints, thresholds, resources, inference boundaries, escalation behavior, memory rules, temporal rules, presentation rules, production rules and permissions. Runtime profile resolution composes a global profile, a primary-domain profile, supporting-domain profiles and contextual overlays into one immutable and auditable resolved profile.

## Architectural Boundary

```text
Global Cognitive Policy
        +
Primary Domain Profile
        +
Supporting Domain Profiles
        +
Workflow / Operation Overlays
        +
Risk / Actor / Autonomy / Explicit Request Overlays
        ↓
DomainProfileResolver
        ↓
ResolvedDomainProfile
        +
ProfileModification Trace
        +
Conflicts / Rejections / Decisions
```

Domain Profiles configure the Cognitive Layer. They do not execute reasoning or rules.

## Responsibilities

Phase 10.11 must define and resolve:

- mandatory rules;
- optional rules;
- prohibited rules;
- permitted, priority and prohibited resources;
- minimum confidence;
- reasoning depth;
- allowed and prohibited inferences;
- maximum questions;
- escalation criteria;
- prohibited actions;
- question policy;
- presentation policy;
- memory policy;
- temporal policy;
- production policy;
- permissions;
- complete modification trace.

Phase 10.11 must not:

- execute cognitive reasoning;
- execute Phase 8 rules;
- duplicate the Cognitive Layer;
- implement concrete rules from Phase 10.12;
- persist profiles;
- resolve runtime actor identity;
- perform runtime authorization;
- contain arbitrary Python logic in profiles;
- execute workflows or operations;
- load adapters;
- call external services.

## Core Principle

Profiles are declarative constraints.

Resolution is monotonic:

- global mandatory rules cannot be deactivated;
- prohibited actions prevail;
- prohibited inferences prevail;
- permissions only narrow;
- confidence thresholds never decrease;
- numeric limits become more restrictive;
- each modification is recorded.

## Public Enums

### DomainProfileResolutionStatus

```text
RESOLVED
PARTIAL
BLOCKED
FAILED
```

### DomainProfileSource

```text
GLOBAL_POLICY
PRIMARY_DOMAIN
SUPPORTING_DOMAIN
WORKFLOW
OPERATION
RISK
ACTOR
AUTONOMY
EXPLICIT_REQUEST
```

### DomainProfileDecisionCode

Minimum values:

```text
PROFILE_APPLIED
OVERLAY_APPLIED
OVERLAY_SKIPPED
MANDATORY_RULE_PRESERVED
PROHIBITED_RULE_PREVAILED
RESOURCE_RESTRICTED
CONFIDENCE_RAISED
LIMIT_RESTRICTED
INFERENCE_PROHIBITED
ACTION_PROHIBITED
PERMISSION_RESTRICTED
ESCALATION_ADDED
POLICY_RESTRICTED
CONFLICT_RECORDED
```

### DomainProfileConflictSeverity

```text
WARNING
ERROR
BLOCKING
```

### DomainReasoningDepth

Recommended ordered levels:

```text
SHALLOW
STANDARD
DEEP
EXHAUSTIVE
```

The merge rule must be explicit. When depth represents a maximum allowed depth, the most restrictive lower level wins. When the profile requires a minimum depth, that must be represented separately rather than overloading one field.

## Typed Policy Contracts

Generic `dict.update()` merging is forbidden.

### DomainQuestionPolicy

Fields:

```text
maximum_questions
allow_follow_up
require_deduplication
allow_clarification
stop_on_blocking_gap
metadata
```

Merge rules:

- maximum questions: minimum;
- booleans that grant capability: logical AND;
- booleans that impose safety behavior: logical OR;
- no field may silently broaden questioning.

### DomainPresentationPolicy

Fields:

```text
detail_level
include_uncertainty
include_provenance
include_alternatives
allow_speculation
require_disclaimers
metadata
```

Merge rules:

- include uncertainty/provenance/disclaimers: logical OR;
- allow speculation: logical AND;
- detail level uses an explicit restrictive order;
- alternatives may be disabled by a stricter source.

### DomainMemoryPolicy

Fields:

```text
allow_read
allow_write
allow_long_term
allow_cross_domain
retention_scope
sensitivity_limit
metadata
```

Merge rules:

- allow flags: logical AND;
- retention scope: most restrictive;
- sensitivity limit: most restrictive;
- no overlay may re-enable denied memory behavior.

### DomainTemporalPolicy

Fields:

```text
require_current_information
allow_historical_information
maximum_age_seconds
require_temporal_provenance
allow_future_projection
metadata
```

Merge rules:

- require flags: logical OR;
- allow flags: logical AND;
- maximum age: minimum non-null;
- no overlay may weaken temporal provenance requirements.

### DomainProductionPolicy

Fields:

```text
allow_draft
allow_final
allow_external_action
require_review
require_validation
maximum_output_items
metadata
```

Merge rules:

- allow flags: logical AND;
- require flags: logical OR;
- maximum output items: minimum non-null;
- external action cannot be enabled by an overlay if globally denied.

## Public Contracts

### DomainProfileDefinition

Fields:

```text
id
domain_id
profile_name
required_rules
optional_rules
prohibited_rules
allowed_resource_kinds
priority_resource_kinds
prohibited_resource_kinds
minimum_confidence
reasoning_depth
allowed_inferences
prohibited_inferences
maximum_questions
escalation_rules
prohibited_actions
question_policy
presentation_policy
memory_policy
temporal_policy
production_policy
permissions
metadata
```

Rules:

- canonical non-empty IDs;
- unique ordered rule/resource/inference/action/permission collections;
- minimum confidence is finite in `[0.0, 1.0]`;
- maximum questions is a strict positive integer;
- bool rejected where numeric values are required;
- priority resources must be allowed and not prohibited;
- required and prohibited rules may coexist only as an explicit conflict handled at resolution;
- allowed and prohibited inferences may coexist only as an explicit conflict handled at resolution;
- metadata is deeply immutable and JSON-safe;
- strict serialization and unknown-field rejection.

### DomainProfileOverlay

Fields:

```text
id
source
source_id
priority
required_rules
optional_rules
prohibited_rules
allowed_resource_kinds
priority_resource_kinds
prohibited_resource_kinds
minimum_confidence
reasoning_depth
allowed_inferences
prohibited_inferences
maximum_questions
escalation_rules
prohibited_actions
question_policy
presentation_policy
memory_policy
temporal_policy
production_policy
permissions
reason
metadata
```

Rules:

- overlays are partial;
- absent values mean no change;
- empty collections mean an explicit empty constraint only when the field semantics allow it;
- source is a closed enum;
- priority is a strict integer;
- overlays contain no executable callbacks;
- each applied field creates a modification record.

### DomainProfileResolutionRequest

Fields:

```text
id
primary_domain
supporting_domains
workflow_ids
operation_ids
risk_level
actor_context
autonomy_level
explicit_requirements
permissions
metadata
```

Rules:

- domains unique and ordered;
- primary excluded from supporting;
- workflow and operation IDs unique;
- no runtime identity lookup;
- actor context is immutable descriptive context only;
- permissions are explicit request constraints;
- strict serialization.

### DomainProfileModification

Fields:

```text
field
source
source_id
operation
previous_value
new_value
reason
restrictive
metadata
```

Rules:

- no silent modification;
- previous and new values are JSON-safe snapshots;
- restrictive is strict bool;
- deterministic order follows application order and field order.

### DomainProfileConflict

Fields:

```text
code
field
severity
sources
description
blocking
metadata
```

Minimum conflict classes:

```text
GLOBAL_MANDATORY_PROHIBITED
REQUIRED_AND_PROHIBITED_RULE
ALLOWED_AND_PROHIBITED_INFERENCE
PRIORITY_RESOURCE_PROHIBITED
EMPTY_PERMISSION_INTERSECTION
INCOMPATIBLE_POLICY
AMBIGUOUS_EXECUTION_MODE
```

### DomainProfileRejection

Fields:

```text
source
source_id
field
reason
blocking
metadata
```

### DomainProfileDecision

Fields:

```text
code
field
source
source_id
reason
blocking
metadata
```

### ResolvedDomainProfile

Fields:

```text
id
primary_domain
supporting_domains
profile_names
required_rules
optional_rules
prohibited_rules
allowed_resource_kinds
priority_resource_kinds
prohibited_resource_kinds
minimum_confidence
reasoning_depth
allowed_inferences
prohibited_inferences
maximum_questions
escalation_rules
prohibited_actions
question_policy
presentation_policy
memory_policy
temporal_policy
production_policy
permissions
modifications
trace_id
resolved_at
metadata
```

Invariants:

- required rules cannot be optional;
- prohibited rules cannot remain optional;
- global mandatory rules cannot disappear;
- prohibited inferences cannot remain allowed;
- priority resources must remain allowed and not prohibited;
- permissions reflect restrictive composition;
- minimum confidence is finite;
- maximum questions is positive;
- resolved time is timezone-aware;
- no executable values.

### DomainProfileResolution

Fields:

```text
id
status
profile
conflicts
rejections
decisions
trace_id
resolved_at
metadata
```

Status rules:

- `RESOLVED`: profile exists and no blocking conflict remains;
- `PARTIAL`: profile exists but one or more optional overlays were rejected or partially applied;
- `BLOCKED`: blocking conflict prevents a safe resolved profile;
- `FAILED`: controlled technical failure only;
- profile may be absent when blocked;
- all conflicts and rejections remain auditable.

## Registry

### DomainProfileRegistry Protocol

```python
class DomainProfileRegistry(Protocol):
    def register(
        self,
        profile: DomainProfileDefinition,
    ) -> DomainProfileDefinition:
        ...

    def get(
        self,
        profile_id: str,
    ) -> DomainProfileDefinition | None:
        ...

    def get_by_domain(
        self,
        domain_id: DomainId,
    ) -> DomainProfileDefinition | None:
        ...

    def list_all(
        self,
    ) -> tuple[DomainProfileDefinition, ...]:
        ...
```

### InMemoryDomainProfileRegistry

Responsibilities:

- register profile definitions;
- reject duplicate IDs;
- reject more than one active base profile per domain;
- return immutable tuples;
- deterministic ordering;
- no persistence;
- no profile execution.

Initial profile names are data, not classes:

```text
GeneralProfile
HealthProfile
RelationshipProfile
UniversityProfile
OppositionProfile
ReflectionProfile
ConcernProfile
LanguageProfile
NilProfile
SportProfile
LifePlanProfile
ProjectProfile
```

Phase 10.11 may provide empty/minimal definitions or fixtures, but exhaustive concrete rule content belongs to Phase 10.12.

## Composition Rules

### Application Order

1. global profile;
2. primary-domain profile;
3. supporting-domain profiles in request order;
4. overlays sorted by:
   - source precedence;
   - priority descending;
   - source ID;
   - overlay ID.

Recommended source precedence:

```text
GLOBAL_POLICY
PRIMARY_DOMAIN
SUPPORTING_DOMAIN
WORKFLOW
OPERATION
RISK
ACTOR
AUTONOMY
EXPLICIT_REQUEST
```

Precedence determines deterministic application order, not permission to weaken earlier restrictions.

### Rules

- required rules: ordered union;
- prohibited rules: ordered union;
- optional rules: ordered union minus required and prohibited;
- prohibited prevails over optional;
- global mandatory plus prohibited creates a blocking conflict;
- non-global required plus prohibited creates an explicit conflict whose severity follows source and policy;
- no silent deletion.

### Resources

- prohibited kinds: ordered union;
- allowed kinds: restrictive intersection when more than one non-empty source constrains the field;
- an unconstrained source is represented by `None`, not an empty tuple;
- empty allowed set means explicitly allow none;
- priority kinds: ordered union filtered to effective allowed and non-prohibited kinds;
- secondary and overlay sources never re-enable globally or primarily prohibited resources.

### Confidence

Effective minimum confidence:

```text
maximum(all specified minimum_confidence values)
```

No source may lower it.

Every increase creates `CONFIDENCE_RAISED`.

### Reasoning Depth

The contract must explicitly define whether the field is a maximum or required depth.

Recommended Phase 10.11 meaning:

```text
reasoning_depth = maximum permitted depth
```

Therefore the most restrictive lower depth wins.

If future phases need minimum required depth, add a separate field.

### Inferences

- prohibited inferences: ordered union;
- allowed inferences: restrictive intersection of explicit constraints;
- prohibited removes allowed;
- global prohibition cannot be reactivated;
- overlap creates a conflict and `INFERENCE_PROHIBITED` decision.

### Questions

- effective maximum questions is the minimum of profile-level and question-policy limits;
- question policy merges monotonically;
- an overlay may reduce but never increase the effective limit.

### Escalation

- escalation rules: ordered union;
- overlays may add escalation criteria;
- no overlay may remove global escalation;
- escalation rules are declarative identifiers/descriptors, not callbacks.

### Actions

- prohibited actions: ordered union;
- prohibited always prevails;
- no source may re-enable an action.

### Permissions

Effective permissions:

```text
global
∩ primary
∩ supporting
∩ overlays
∩ request permissions
```

Rules:

- empty/unconstrained must be represented explicitly to avoid accidental denial;
- explicit deny wins;
- no source may expand permissions;
- empty effective permission intersection may block resolution when permissions are required;
- request permissions only restrict.

### Typed Policies

Each typed policy has a dedicated merge function.

No generic recursive dict merge is allowed.

Every changed field produces a `DomainProfileModification`.

## Composition Component

### DomainProfileComposer Protocol

```python
class DomainProfileComposer(Protocol):
    def compose(
        self,
        *,
        global_profile: DomainProfileDefinition,
        primary_profile: DomainProfileDefinition,
        supporting_profiles: tuple[DomainProfileDefinition, ...],
        overlays: tuple[DomainProfileOverlay, ...],
        request_permissions: tuple[str, ...],
    ) -> DomainProfileCompositionResult:
        ...
```

### DomainProfileCompositionResult

Fields:

```text
profile
conflicts
rejections
decisions
modifications
metadata
```

The composer performs pure deterministic composition. It does not generate IDs or timestamps and has no registry access.

## Resolver

### DomainProfileResolver Protocol

```python
class DomainProfileResolver(Protocol):
    def resolve(
        self,
        *,
        request: DomainProfileResolutionRequest,
        global_profile: DomainProfileDefinition,
        primary_profile: DomainProfileDefinition,
        supporting_profiles: tuple[DomainProfileDefinition, ...],
        overlays: tuple[DomainProfileOverlay, ...],
    ) -> DomainProfileResolution:
        ...
```

### DefaultDomainProfileResolver

Constructor:

```python
class DefaultDomainProfileResolver:
    def __init__(
        self,
        *,
        composer: DomainProfileComposer | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        profile_id_factory: Callable[[], str] | None = None,
        trace_id_factory: Callable[[], str] | None = None,
    ) -> None:
        ...
```

The resolver:

1. validates request and profile/domain alignment;
2. validates overlay source relevance;
3. invokes the pure composer;
4. derives status;
5. generates resolution/profile/trace IDs;
6. captures timezone-aware time;
7. returns immutable resolution.

No registry access occurs inside the resolver.

## Overlay Relevance

Overlay source must correspond to request context:

- workflow overlay source ID must appear in `workflow_ids`;
- operation overlay source ID must appear in `operation_ids`;
- risk overlay must match risk level;
- autonomy overlay must match autonomy level;
- supporting-domain overlay must refer to a supporting domain;
- primary-domain overlay must refer to the primary domain;
- explicit-request overlay may reference the request ID;
- global-policy overlay is always relevant;
- actor overlay uses descriptive actor context only.

Irrelevant optional overlays are rejected and may yield `PARTIAL`.

Irrelevant mandatory/global overlays produce a blocking conflict.

## Error Hierarchy

```text
DomainProfileError
DomainProfileContractError
DomainProfileSerializationError
DomainProfileConfigurationError
DomainProfileRegistryError
DomainProfileCompositionError
DomainProfileResolutionError
```

Requirements:

- stable codes;
- safe messages;
- structured field/details;
- no broad `except Exception`;
- no `str(exc)` or `repr(exc)` leakage;
- functional conflicts remain result states.

## Determinism

Ordering:

- supporting profiles: request order;
- overlays: source precedence, priority descending, source ID, overlay ID;
- rules/resources/inferences/actions/escalations: first appearance;
- conflicts: blocking first, severity, field, code, sources;
- rejections: blocking first, source, source ID, field;
- decisions: blocking first, application order, field, code;
- modifications: exact application order and stable field order;
- profile names: global, primary, supporting order, applied overlays.

No output depends on set iteration order.

## Serialization and Immutability

All public contracts require:

- frozen slotted dataclasses;
- strict `to_dict()` and `from_dict()`;
- unknown-field rejection;
- strict bool/numeric/enum parsing;
- bool rejected as integer;
- finite float validation;
- timezone-aware datetimes;
- canonical Domain IDs;
- nested field paths;
- deeply immutable JSON-safe metadata;
- exact round trips;
- no implicit coercion.

## Files

Create:

```text
cmm/domains/profile_contracts.py
cmm/domains/profile_registry.py
cmm/domains/profile_composition.py
cmm/domains/profile_resolver.py
```

Modify:

```text
cmm/domains/enums.py
cmm/domains/errors.py
cmm/domains/__init__.py
```

Tests:

```text
tests/domains/test_domain_profile_contracts.py
tests/domains/test_domain_profile_serialization.py
tests/domains/test_domain_profile_registry.py
tests/domains/test_domain_profile_composition.py
tests/domains/test_domain_profile_resolver.py
tests/domains/test_domain_profile_public_api.py
tests/domains/test_domain_profile_boundaries.py
tests/domains/test_domain_public_api.py
```

## Deliberate Exclusions

Phase 10.11 does not include:

- cognitive execution;
- concrete Domain Rules from 10.12;
- profile persistence;
- runtime identity lookup;
- runtime authorization;
- actual memory operations;
- workflow or operation execution;
- adapter loading;
- model selection;
- prompt selection;
- external I/O.

## Success Criteria

Phase 10.11 is complete only when:

- profiles remain declarative;
- global mandatory rules cannot be deactivated;
- prohibited rules/actions/inferences prevail;
- confidence never decreases;
- limits become only more restrictive;
- resources and permissions never widen;
- typed policies merge explicitly;
- every modification is traced;
- conflicts and rejections remain auditable;
- no cognitive execution or 10.12 rule implementation exists;
- all contracts are immutable and strictly serializable;
- focused, domains, validation and global suites pass;
- Ruff, compileall and diff checks pass.
