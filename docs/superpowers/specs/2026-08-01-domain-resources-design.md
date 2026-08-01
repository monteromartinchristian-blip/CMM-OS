# Phase 10.10 Domain Resources Design

## Status

Approved design for implementation planning.

## Objective

Implement a declarative Domain Resources layer that defines how shared resources are interpreted by one or more domains without creating incompatible resource models or duplicated resource copies.

Phase 10.10 reuses the common Cognitive Layer resource model: `Resource`, `ResourceProvenance`, `TemporalScope`, `Sensitivity`, `Permissions`, `KnowledgeItem`, `Entity`, and `KnowledgeRelation`.

## Architectural Boundary

```text
Common Resource Reference
        ↓
DomainResourceRegistry
        ↓
DomainResourceResolver
        ├── applicable definitions
        ├── permissions
        ├── sensitivity
        ├── temporality
        ├── source priority
        ├── reliability
        └── validators
        ↓
DomainResourceResolution
        ├── shared bindings
        ├── denials
        ├── validation issues
        └── decisions
```

Derived resources use explicit lineage:

```text
Source Resource
        ↓
DomainResourceDerivation
        ↓
Derived Resource Reference
```

The phase does not execute adapters or modify external systems.

## Responsibilities

Phase 10.10 must register domain resource definitions, associate adapters declaratively, declare relevant entity types, sensitivity, permissions, temporal policies, source priorities, reliability and validators, resolve applicable definitions, share one resource across several domains, prevent unauthorized bindings, and preserve derivation lineage.

It must not create a second `Resource` model, duplicate resource contents per domain, execute adapters, read files, call external services, persist resources, ingest data, perform OCR or embeddings, mutate the Knowledge Graph, infer runtime actor permissions, deduplicate semantically, or implement Domain Profiles.

## Core Principle

A resource exists once and may have several domain bindings:

```text
resource:calendar:event-123
    ├── domain:health
    ├── domain:university
    └── domain:oppositions
```

Bindings add interpretation metadata, never copies.

## Public Enums

### DomainResourceResolutionStatus

```text
RESOLVED
PARTIAL
BLOCKED
REJECTED
FAILED
```

- `RESOLVED`: all applicable and authorized requested domains received bindings.
- `PARTIAL`: at least one binding exists, but some requested or applicable definitions could not be used.
- `BLOCKED`: a required binding cannot proceed because of permissions, sensitivity, temporality or validation.
- `REJECTED`: no definition is applicable or authorized.
- `FAILED`: controlled registry/resolver failure only.

### DomainResourceDecisionCode

```text
DEFINITION_SELECTED
DEFINITION_SKIPPED
DOMAIN_NOT_APPLICABLE
PERMISSION_DENIED
SENSITIVITY_RESTRICTED
TEMPORAL_POLICY_FAILED
VALIDATION_FAILED
RESOURCE_SHARED
DERIVATION_RECORDED
SOURCE_PRIORITY_APPLIED
RELIABILITY_APPLIED
```

### DomainResourceValidationSeverity

```text
INFO
WARNING
ERROR
BLOCKING
```

## Public Contracts

### DomainResourceDefinition

Fields:

```text
id
kind
domain_id
adapter
entity_types
default_sensitivity
default_permissions
temporal_policy
source_priority
default_reliability
validation_rules
shareable
metadata
```

Rules:

- canonical non-empty identifiers;
- unique ordered entity types and permissions;
- strict non-negative source priority;
- strict finite reliability in `[0.0, 1.0]`;
- declarative validation rules only;
- deeply immutable JSON-safe metadata;
- strict serialization and unknown-field rejection.

### DomainResourceTemporalPolicy

```text
validity_window_seconds
staleness_policy
effective_date_required
expiration_required
historical_allowed
metadata
```

Rules:

- optional validity window is a strict positive integer;
- booleans are strict;
- no executable callbacks;
- no hidden clock access.

### DomainResourceValidationRule

```text
id
field
operator
expected
severity
message
metadata
```

Allowed operators remain explicit and minimal:

```text
exists
equals
not_equals
contains
in
minimum
maximum
```

No arbitrary expressions or code execution.

### DomainResourceContext

```text
resource_id
kind
applicable_domains
sensitivity
permissions
temporal_scope
source_type
provenance
entity_types
metadata
```

This is an immutable resolution context, not a second Resource object. Provenance is required. Applicable domains are relevance hints, never authorization.

### DomainResourceBinding

```text
id
resource_id
definition_id
domain_id
adapter
entity_types
sensitivity
permissions
temporal_scope
source_priority
reliability
validation_results
provenance
metadata
```

Rules:

- references one common resource and one definition;
- contains no resource payload;
- sensitivity can only become more restrictive;
- permissions are the restrictive intersection;
- provenance includes resource and definition lineage;
- strict serialization.

### DomainResourceValidationResult

```text
rule_id
passed
severity
message
field
observed
metadata
```

Blocking failed results prevent binding.

### DomainResourceRejection

```text
definition_id
domain_id
code
reason
blocking
metadata
```

### DomainResourceDecision

```text
code
resource_id
definition_id
domain_id
reason
blocking
metadata
```

### DomainResourceResolution

```text
id
resource_id
status
bindings
rejections
permission_denials
validation_issues
shared_domains
decisions
trace_id
resolved_at
metadata
```

Invariants:

- `RESOLVED` requires at least one binding and no unresolved required blocker;
- `PARTIAL` requires at least one binding plus an incomplete non-global condition;
- `BLOCKED` requires a blocking rejection or validation issue;
- `REJECTED` requires no bindings;
- shared domains correspond to accepted bindings;
- no resource duplication.

### DomainResourceChecksum

```text
algorithm
value
```

Supported algorithms:

```text
sha256
sha384
sha512
```

Checksums are validated but never computed internally.

### DomainResourceDerivation

```text
id
source_resource_id
derived_resource_id
definition_id
transformation
actor
created_at
version
permissions
sensitivity
checksum
provenance
metadata
```

Rules:

- source and derived IDs differ;
- actor, transformation and version are non-empty;
- created time is timezone-aware;
- derived permissions cannot widen source permissions;
- derived sensitivity cannot be lower;
- checksum is optional;
- no derived payload is stored.

## Registry

### DomainResourceRegistry Protocol

```python
class DomainResourceRegistry(Protocol):
    def register(self, definition: DomainResourceDefinition) -> DomainResourceDefinition: ...
    def get(self, definition_id: str) -> DomainResourceDefinition | None: ...
    def find_by_kind(self, kind: str) -> tuple[DomainResourceDefinition, ...]: ...
    def find_by_domain(self, domain_id: DomainId) -> tuple[DomainResourceDefinition, ...]: ...
    def list_all(self) -> tuple[DomainResourceDefinition, ...]: ...
```

### InMemoryDomainResourceRegistry

Responsibilities:

- register definitions;
- reject duplicate IDs;
- allow the same kind in several domains;
- return immutable tuples;
- expose no mutable state;
- provide no persistence or adapter loading.

Ordering:

- by kind: source priority descending, domain slug, definition ID;
- by domain: kind, source priority descending, definition ID;
- all: domain slug, kind, definition ID.

## Resolver

### DomainResourceResolver Protocol

```python
class DomainResourceResolver(Protocol):
    def resolve(
        self,
        *,
        context: DomainResourceContext,
        definitions: tuple[DomainResourceDefinition, ...],
        requested_domains: tuple[DomainId, ...],
        request_permissions: tuple[str, ...],
    ) -> DomainResourceResolution:
        ...
```

### DefaultDomainResourceResolver

```python
class DefaultDomainResourceResolver:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        trace_id_factory: Callable[[], str] | None = None,
        validator: DomainResourceValidator | None = None,
    ) -> None:
        ...
```

The resolver receives definitions explicitly and never accesses the registry.

## Resolution Flow

1. Validate all inputs.
2. Generate resolution and trace IDs.
3. Select matching resource kinds.
4. Restrict to requested domains.
5. Apply applicable-domain hints.
6. Reject non-shareable definitions when several domains require the resource.
7. Compute effective sensitivity.
8. Compute effective permissions.
9. Reject permission widening.
10. Evaluate temporal policy.
11. Evaluate validation rules.
12. Apply source priority deterministically.
13. Apply reliability.
14. Build one binding per accepted definition.
15. Record resource sharing.
16. Derive final status.
17. Return immutable resolution.

## Permission Model

Effective permissions:

```text
resource permissions
∩ definition default permissions
∩ request permissions
```

Rules:

- empty resource permissions do not imply public access;
- explicit deny wins;
- definitions only restrict;
- supporting domains cannot lift a deny;
- missing required permission rejects the binding;
- denial is a result state, not an exception.

## Sensitivity Model

Effective sensitivity is the most restrictive of resource, definition and derivation sensitivity. Definitions may raise sensitivity, never lower it.

## Temporal Policy

Evaluate required effective date, required expiration, validity window, staleness and historical use using only resource temporal scope, definition policy and injected clock.

## Source Priority and Reliability

Filter invalid definitions first, then order by source priority. Preserve all valid definitions unless an explicit contract requires one preferred interpretation. Never discard provenance or resolve contradictions silently.

Reliability never authorizes access or overrides sensitivity.

## Validation

### DomainResourceValidator Protocol

```python
class DomainResourceValidator(Protocol):
    def validate(
        self,
        *,
        context: DomainResourceContext,
        definition: DomainResourceDefinition,
    ) -> tuple[DomainResourceValidationResult, ...]:
        ...
```

### DefaultDomainResourceValidator

Supports only declarative operators. Unsupported operators are configuration errors. Warning and non-blocking errors remain visible.

## Derivation

### DomainResourceDerivationService

```python
class DomainResourceDerivationService:
    def record(
        self,
        derivation: DomainResourceDerivation,
    ) -> DomainResourceDerivation:
        ...
```

The service validates and returns an immutable canonical record. It does not persist or fetch resources.

## Errors

```text
DomainResourceError
DomainResourceContractError
DomainResourceSerializationError
DomainResourceConfigurationError
DomainResourceRegistryError
DomainResourceResolutionError
DomainResourceDerivationError
```

No broad `except Exception`, `str(exc)` or `repr(exc)` leakage.

## Determinism

- definitions: source priority descending, domain slug, definition ID;
- bindings: requested-domain order, source priority descending, definition ID;
- rejections: blocking first, domain slug, definition ID, code;
- validation issues: blocking severity first, rule ID, field;
- shared domains: requested-domain order;
- decisions: blocking first, domain slug, definition ID, code;
- provenance: first appearance with exact-reference deduplication.

## Serialization and Immutability

All public contracts use frozen slotted dataclasses, strict `to_dict()` and `from_dict()`, unknown-field rejection, strict enums and booleans, finite numeric validation, timezone-aware datetimes, canonical domain IDs, nested field paths, deep immutable metadata and exact round trips.

No implicit coercion with `str()`, `bool()`, `int()` or `float()` during deserialization.

## Files

Create:

```text
cmm/domains/resource_contracts.py
cmm/domains/resource_registry.py
cmm/domains/resource_resolver.py
cmm/domains/resource_derivation.py
```

Modify:

```text
cmm/domains/enums.py
cmm/domains/errors.py
cmm/domains/__init__.py
```

Tests:

```text
tests/domains/test_domain_resource_contracts.py
tests/domains/test_domain_resource_serialization.py
tests/domains/test_domain_resource_registry.py
tests/domains/test_domain_resource_resolver.py
tests/domains/test_domain_resource_derivation.py
tests/domains/test_domain_resource_public_api.py
tests/domains/test_domain_resource_boundaries.py
tests/domains/test_domain_public_api.py
```

## Deliberate Exclusions

- adapter execution;
- resource payload storage;
- filesystem and network access;
- ingestion, OCR, embeddings and vector stores;
- synchronization and persistence;
- events;
- Knowledge Graph mutation;
- semantic deduplication;
- runtime actor authorization;
- Domain Profiles from Phase 10.11.

## Success Criteria

Phase 10.10 is complete only when one resource can bind to several domains without duplication, permissions never widen, sensitivity never decreases, provenance and derivation lineage are preserved, temporal and validation policies are deterministic, adapters remain declarative, no external I/O occurs, all contracts are immutable and strictly serializable, and all focused, domains, validation, global, Ruff, compileall and diff checks pass.
