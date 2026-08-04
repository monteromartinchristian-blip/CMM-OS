# Phase 10.18 — Domain Memory Integration Design

**Status:** Approved design
**Date:** 2026-08-03
**Phase:** 10.18 — Domain Memory Integration
**Branch:** `feature/phase-10-domain-intelligence`
**Base:** Phase 10.17 completed at `124621c`

## 1. Purpose

Phase 10.18 integrates Domain Intelligence with the existing shared memory, knowledge, temporal, provenance and update-proposal contracts from Phases 8 and 9.

A domain may:

* obtain an authorized view of shared memory;
* reuse knowledge, entities and relations;
* identify relevant versions, evidence and contradictions;
* propose updates, invalidations or cross-domain links;
* bind those proposals to permissions and approvals;
* preserve provenance, temporal history and domain attribution.

A domain must not create or own an independent memory store.

The phase introduces a domain-facing integration layer, not another memory system.

---

## 2. Core principle

CMM OS has one shared memory and one shared knowledge model.

The following structures are prohibited:

```text
HealthMemory
UniversityMemory
RelationshipsMemory
ProjectMemory
LifePlanMemory
DomainKnowledgeStore
DomainKnowledgeGraph
DomainClaim
DomainKnowledgePackage
```

Domains receive filtered, reference-only views over common knowledge.

A memory item may be relevant to several domains without being copied. Domain applicability is metadata and policy, not ownership.

```text
Shared memory
    ↓ filtered by domain, permission, sensitivity and time
DomainMemoryView
```

---

## 3. Existing contracts remain authoritative

Phase 10.18 must reuse existing contracts for:

* `KnowledgeItem`;
* `KnowledgeRelation`;
* entities;
* evidence;
* resources and provenance;
* temporal scope;
* versions and supersession;
* invalidation;
* contradictions;
* Knowledge Store;
* Knowledge Graph;
* `KnowledgePackage`;
* `MemoryUpdateProposal`;
* `AgentKnowledgeUpdateProposal`;
* permission decisions;
* approval requests and decisions;
* Domain Trace.

Phase 10.18 does not redefine their payloads, lifecycle or persistence semantics.

When an existing contract already represents a concept, the domain layer stores only its ID and the minimum typed information necessary to validate the association.

---

## 4. Scope

### 4.1 Included

Phase 10.18 implements:

1. immutable domain memory contracts;
2. reference-only memory views;
3. deterministic memory-view resolution;
4. typed inclusion and exclusion decisions;
5. bindings to existing memory-update proposals;
6. permission and approval linkage;
7. temporal and version-preservation validation;
8. provenance and evidence requirements;
9. multidomain deduplication invariants;
10. privacy and serialization safeguards;
11. public API and documentation;
12. focused, domain and global tests.

### 4.2 Excluded

Phase 10.18 does not implement:

* another Knowledge Store or Graph;
* memory persistence;
* automatic memory writes;
* proposal execution;
* deletion execution;
* external connectors;
* retrieval from Notion, conversations, calendars or web sources;
* PII redaction or provider egress;
* artifact invalidation execution;
* Model Gateway integration;
* UI approval flows;
* another provenance model;
* another temporal engine;
* another Knowledge Package;
* per-domain persistent copies;
* semantic extraction from raw content;
* domain-specific temporal rules such as clinical-series completeness.

These responsibilities remain in existing layers or Phase 11.

---

## 5. Architecture

### 5.1 Read flow

```text
Existing memory/knowledge candidate references
        +
Domain resolution and composition
        +
Domain memory policy
        +
permission decisions
        +
temporal reference
        ↓
DomainMemoryViewResolver
        ↓
DomainMemoryView
        ↓
DomainMemoryIntegrationValidator
        ↓
valid reference-only domain view
        ↓
KnowledgePackageBuilder / rules / workflows
```

The resolver is pure. It does not query databases, stores, graphs, files or remote services.

Candidates are supplied explicitly by the caller.

### 5.2 Proposal flow

```text
Domain result
        ↓
existing MemoryUpdateProposal
        +
existing AgentKnowledgeUpdateProposal
        ↓
DomainMemoryProposalBinding
        ↓
permission and approval linkage
        ↓
DomainMemoryIntegrationValidator
        ↓
eligible binding for later execution
```

The binding does not contain additions, updates, invalidations or claims by value. Those remain inside the existing canonical proposal.

### 5.3 Dependency direction

Allowed:

```text
domains → cognitive
domains → agent_runtime
domains → existing permission/approval contracts
```

Forbidden:

```text
cognitive → domains
agent_runtime → domains
memory store → domains
```

Phase 8 and Phase 9 remain usable without Domain Intelligence.

---

## 6. Public contracts

All public contracts must be:

* frozen;
* deeply immutable;
* deterministic;
* strictly typed;
* serializable through `to_dict()` and `from_dict()`;
* JSON-safe;
* compatible with Python 3.10;
* reject unknown fields;
* reject implicit coercion;
* reject non-finite floats;
* free of inline memory content.

### 6.1 `DomainMemoryReferenceKind`

Closed enum identifying the existing object referenced by a view.

Actual values:

```text
KNOWLEDGE_ITEM = "knowledge_item"
KNOWLEDGE_RELATION = "knowledge_relation"
EVIDENCE = "evidence"
RESOURCE = "resource"
CONTRADICTION = "contradiction"
VERSION = "version"
RESOLUTION_MEMORY_ENTRY = "resolution_memory_entry"
KNOWLEDGE_PACKAGE = "knowledge_package"
```

### 6.2 `DomainMemoryReference`

Represents one reference to an existing memory or knowledge object.

Actual fields:

```text
reference_id: str
kind: DomainMemoryReferenceKind
canonical_id: str
domain_id: DomainId
applicable_domains: tuple[DomainId, ...]
sensitivity_level: str | None
version: int | None
superseded_by_id: str | None
evidence_ids: tuple[str, ...]
resource_ids: tuple[str, ...]
has_unresolved_conflict: bool
has_unknown_ordering: bool
temporal: DomainMemoryTemporalSnapshot | None
metadata: MappingProxyType[str, Any]
```

Rules:

* it never stores claim text or resource content;
* `reference_id` must identify an existing object;
* applicable domains are normalized and do not imply ownership;
* evidence and resource IDs are references only;
* sensitivity reuses the canonical sensitivity enum when available;
* temporal status reuses existing temporal contracts when possible;
* metadata cannot contain payloads or sensitive content.

This contract is an input descriptor for selection. It is not a replacement for `KnowledgeItem`.

### 6.3 `DomainMemoryViewRequest`

Represents a request for an authorized memory view.

Actual fields:

```text
request_id: str
primary_domain: DomainId
supporting_domains: tuple[DomainId, ...]
trace_id: str | None
resolution_reference_id: str | None
requested_kinds: tuple[DomainMemoryReferenceKind, ...]
candidates: tuple[DomainMemoryReference, ...]
permission_decision_ids: tuple[str, ...]
temporal_reference: str | None
```

Rules:

* no objective text;
* no user message;
* no prompt;
* no memory payload;
* exactly one primary `domain_id`;
* primary cannot appear among supporting domains;
* candidate references must be unique;
* permission decisions must be explicit;
* ordering must be deterministic.

### 6.4 `DomainMemorySelectionDecisionCode`

Closed enum recording why a candidate was included or excluded.

Actual values:

```text
SELECTED = "selected"
EXCLUDED_DOMAIN_INAPPLICABLE = "excluded_domain_inapplicable"
EXCLUDED_PERMISSION_DENIED = "excluded_permission_denied"
EXCLUDED_PERMISSION_MISSING = "excluded_permission_missing"
EXCLUDED_PERMISSION_UNSCOPED = "excluded_permission_unscoped"
EXCLUDED_SENSITIVITY_RESTRICTED = "excluded_sensitivity_restricted"
EXCLUDED_TEMPORAL_INVALID = "excluded_temporal_invalid"
EXCLUDED_TEMPORAL_UNKNOWN = "excluded_temporal_unknown"
EXCLUDED_TEMPORAL_EXPIRED = "excluded_temporal_expired"
EXCLUDED_SUPERSEDED = "excluded_superseded"
EXCLUDED_DUPLICATE = "excluded_duplicate"
EXCLUDED_UNSUPPORTED_KIND = "excluded_unsupported_kind"
EXCLUDED_PROVENANCE_MISSING = "excluded_provenance_missing"
EXCLUDED_EVIDENCE_MISSING = "excluded_evidence_missing"
EXCLUDED_CONFIRMATION_REQUIRED = "excluded_confirmation_required"
EXCLUDED_ORDERING_UNKNOWN = "excluded_ordering_unknown"
EXCLUDED_PRESERVED_CONFLICT = "excluded_preserved_conflict"
EXCLUDED_MISSING_REFERENCE = "excluded_missing_reference"
EXCLUDED_REFERENCE_MISMATCH = "excluded_reference_mismatch"
EXCLUDED_INVALIDATED = "excluded_invalidated"
```

A decision describes selection only. It does not mutate memory.

### 6.5 `DomainMemorySelectionDecision`

Actual fields:

```text
reference_id: str
code: DomainMemorySelectionDecisionCode
related_reference_ids: tuple[str, ...]
permission_decision_ids: tuple[str, ...]
```

The reason is a closed code, not unrestricted explanatory text.

### 6.6 `DomainMemoryView`

Represents the resolved view.

Actual fields:

```text
view_id: str
request_id: str
primary_domain: DomainId
request_digest: str
trace_id: str | None
temporal_reference: str | None
selection_decisions: tuple[DomainMemorySelectionDecision, ...]
selected_references: tuple[DomainMemoryReference, ...]
```

Rules:

* strictly reference-only;
* contains required `request_digest`, which is the full 64-character canonical SHA-256 of `DomainMemoryViewRequest`;
* `view_id` is content-bound to `request_id`, `primary_domain`, `request_digest`, optional `trace_id`, optional `temporal_reference`, `selection_decisions`, and `selected_references`;
* changes in `supporting_domains`, `resolution_reference_id`, `requested_kinds`, `permission_decision_ids`, `trace_id`, or `temporal_reference` alter `request_digest` and produce a distinct `view_id`;
* `validate_view` demands exact equality between `view.request_digest` and `request.digest`;
* no copied claims, entities, relations, evidence or resources;
* selected and excluded sets are disjoint;
* every candidate has exactly one final decision;
* every selected reference resolves to an existing canonical object;
* IDs and digest are deterministic;
* collection ordering is canonical;
* the same shared item keeps the same ID across domains;
* the view does not persist itself as a domain memory store.

### 6.7 `DomainMemoryProposalBinding`

Links a domain execution to existing memory proposals.

Actual fields:

```text
binding_id: str
domain_id: DomainId
trace_id: str
view_id: str
view_digest: str
memory_proposal_ids: tuple[str, ...]
agent_knowledge_proposal_ids: tuple[str, ...]
affected_reference_ids: tuple[str, ...]
permission_decision_ids: tuple[str, ...]
approval_request_ids: tuple[str, ...]
approval_decision_ids: tuple[str, ...]
```

Rules:

* at least one canonical proposal ID is required;
* no additions, updates or invalidations appear inline;
* affected references must match the canonical proposal inventory supplied to validation;
* read permission does not satisfy propose or write permission;
* approval is required whenever demanded by the canonical proposal, sensitivity or policy;
* the binding does not execute or persist the proposal;
* the binding does not own a parallel proposal lifecycle;
* proposal status remains authoritative in the existing Phase 8/9 contract.

The old conceptual `DomainMemoryUpdateProposal` is not implemented as a payload-bearing model.

### 6.8 `DomainMemoryReferenceInventory`

Typed external inventory used by the validator.

Actual fields:

```text
references: tuple[DomainMemoryReference, ...]
proposals: tuple[DomainMemoryProposalSnapshot, ...]
permission_decisions: tuple[DomainMemoryPermissionDecisionSnapshot, ...]
approval_requests: tuple[DomainMemoryApprovalRequestSnapshot, ...]
approval_decisions: tuple[DomainMemoryApprovalDecisionSnapshot, ...]
traces: tuple[DomainMemoryTraceSnapshot, ...]
views: tuple[DomainMemoryViewSnapshot, ...]
```

The inventory is supplied by the caller. The validator does not query stores.

### 6.9 `DomainMemoryValidationCode`

Closed enum covering integration validation outcomes:

```text
VALID = "valid"
INVALID_REFERENCE_INTEGRITY = "invalid_reference_integrity"
INVALID_PRIVACY_BREACH = "invalid_privacy_breach"
INVALID_PERMISSION_DENIED = "invalid_permission_denied"
INVALID_PERMISSION_UNSCOPED = "invalid_permission_unscoped"
INVALID_APPROVAL_REQUIRED = "invalid_approval_required"
INVALID_APPROVAL_COVERAGE_MISMATCH = "invalid_approval_coverage_mismatch"
INVALID_PROVENANCE_MISSING = "invalid_provenance_missing"
INVALID_EVIDENCE_MISSING = "invalid_evidence_missing"
INVALID_TEMPORAL_INVARIANT = "invalid_temporal_invariant"
INVALID_VERSION_INVARIANT = "invalid_version_invariant"
INVALID_PROPOSAL_COVERAGE = "invalid_proposal_coverage"
INVALID_PROPOSAL_KIND_MISMATCH = "invalid_proposal_kind_mismatch"
INVALID_DUPLICATE_PROPOSAL_CLASSIFICATION = "invalid_duplicate_proposal_classification"
INVALID_TRACE_VIEW_MISMATCH = "invalid_trace_view_mismatch"
INVALID_DIGEST_TAMPERED = "invalid_digest_tampered"
INVALID_MISSING_REFERENCE = "invalid_missing_reference"
INVALID_REFERENCE_MISMATCH = "invalid_reference_mismatch"
INVALID_STRUCTURE = "invalid_structure"
```

### 6.10 `DomainMemoryValidationResult`

Actual fields:

```text
is_valid: bool
code: DomainMemoryValidationCode
codes: tuple[DomainMemoryValidationCode, ...]
affected_reference_ids: tuple[str, ...]
affected_object_ids: tuple[str, ...]
```

Rules:

* `is_valid=True` requires `code=VALID` and `codes=(VALID,)`;
* `is_valid=False` requires non-VALID code and codes.

### 6.11 Explicit `DomainMemoryTemporalKind` Semantics

```text
UNKNOWN: Always excluded with EXCLUDED_TEMPORAL_UNKNOWN (even if temporal_reference is provided).
TIMELESS: Selected unless expires_at is present and temporal_reference is missing (EXCLUDED_TEMPORAL_INVALID) or expired (EXCLUDED_TEMPORAL_EXPIRED).
POINT_IN_TIME: Selected if temporal_reference is provided and observed_at == temporal_reference, else EXCLUDED_TEMPORAL_INVALID.
INTERVAL: Selected if temporal_reference is provided and valid_from <= temporal_reference <= valid_to, else EXCLUDED_TEMPORAL_INVALID.
SAFETY: Always excluded in Phase 10.18 reference views with EXCLUDED_TEMPORAL_INVALID (safety-restricted scopes require explicit safety clearance).
```
* `valid=False` requires at least one code;
* diagnostics are sanitized and reference-only;
* validation never raises accidental `KeyError`, `TypeError` or `AttributeError` for manipulated contracts.

---

## 7. Services

### 7.1 `DomainMemoryViewResolver`

Protocol:

```python
class DomainMemoryViewResolver(Protocol):
    def resolve(
        self,
        request: DomainMemoryViewRequest,
        inventory: DomainMemoryReferenceInventory,
    ) -> DomainMemoryView: ...
```

Default implementation:

```text
DefaultDomainMemoryViewResolver
```

Responsibilities:

1. validate request structure;
2. normalize candidates;
3. filter by domain applicability;
4. apply explicit read permissions;
5. apply sensitivity constraints;
6. apply temporal validity without inventing chronology;
7. preserve relevant contradictions;
8. identify superseded versions without deleting history;
9. deduplicate by canonical reference ID;
10. emit one decision per candidate;
11. calculate deterministic ID and digest;
12. return a reference-only view.

It must not:

* query memory;
* query the graph;
* infer new claims;
* select a “latest” version when ordering is unknown;
* mutate permissions;
* create a Knowledge Package;
* write memory;
* perform approval.

### 7.2 `DomainMemoryIntegrationValidator`

Protocol:

```python
class DomainMemoryIntegrationValidator(Protocol):
    def validate_view(
        self,
        view: DomainMemoryView,
        request: DomainMemoryViewRequest,
        inventory: DomainMemoryReferenceInventory,
    ) -> DomainMemoryValidationResult: ...

    def validate_binding(
        self,
        binding: DomainMemoryProposalBinding,
        inventory: DomainMemoryReferenceInventory,
    ) -> DomainMemoryValidationResult: ...
```

Default implementation:

```text
DefaultDomainMemoryIntegrationValidator
```

The validator is pure, deterministic and fail-closed.

---

## 8. Selection semantics

### 8.1 Domain applicability

A reference is selectable when:

* it explicitly applies to the primary domain;
* it applies to an authorized supporting domain;
* it is general reusable knowledge allowed by policy;
* a valid cross-domain permission authorizes its use.

Applicability does not create a copy or change ownership.

### 8.2 Permissions

Memory capabilities are separate:

```text
READ
PROPOSE
APPROVE
APPLY
INVALIDATE
DELETE
```

The phase must reuse existing permission-operation concepts where available.

Rules:

* READ does not imply PROPOSE;
* PROPOSE does not imply APPROVE;
* APPROVE does not imply APPLY;
* APPLY does not imply DELETE;
* cross-domain access requires source and target authorization;
* missing permission fails closed.

### 8.3 Sensitivity

A domain view cannot lower the sensitivity of an item.

The resolver may exclude an item or require confirmation, but may not:

* reclassify it as less sensitive;
* copy it into metadata;
* expose its content;
* widen its permitted domains.

### 8.4 Provenance and evidence

A persistent knowledge item must retain references to its existing evidence and provenance.

The integration layer does not create evidence.

A candidate may be excluded when:

* required evidence is absent;
* required provenance is absent;
* the referenced resource cannot be resolved;
* a domain policy requires stronger support.

### 8.5 Temporal semantics

The resolver and validator must preserve:

* `valid_from`;
* `valid_to`;
* observed time;
* version;
* supersession;
* invalidation;
* unknown relative ordering.

Rules:

1. updating a value does not erase the previous value;
2. supersession is not equivalent to contradiction;
3. contradiction is preserved when authority or chronology cannot resolve it;
4. unknown order cannot be converted into “newest”;
5. matching the current value does not prove temporal completeness;
6. `NOT_FOUND` does not mean confirmed absence;
7. domain-specific completeness requirements belong to Domain Rules.

### 8.6 Episodic and semantic memory

Phase 10.18 preserves the distinction already present in the memory architecture.

Episodic references represent:

* what occurred;
* who or what produced the event;
* when it occurred;
* session or execution context;
* state transitions.

Semantic references represent:

* reusable confirmed knowledge;
* preferences;
* goals;
* constraints;
* entities;
* relations;
* consolidated versions;
* open contradictions.

The domain layer does not create separate episodic or semantic stores.

---

## 9. Proposal binding semantics

### 9.1 Canonical proposal authority

`MemoryUpdateProposal` and `AgentKnowledgeUpdateProposal` remain authoritative for:

* additions;
* updates;
* invalidations;
* relations;
* rejected candidates;
* confidence;
* reasons;
* confirmation requirement;
* proposal status.

`DomainMemoryProposalBinding` only adds domain integration references and an exact full digest binding to the referenced view.

### 9.2 Coverage

The validator must ensure:

```text
binding.affected_reference_ids
==
references affected by the canonical proposal inventory
```

It must reject:

* omitted affected references;
* introduced references;
* proposal IDs not found;
* mismatched domain;
* mismatched memory view;
* mismatched Domain Trace;
* inconsistent confirmation requirement.

### 9.3 Confirmation and approval

User confirmation or explicit approval is required when demanded by:

* the canonical proposal;
* sensitive inference policy;
* invalidation of user-provided information;
* modification of an important preference;
* material ambiguity;
* domain policy;
* Phase 10.15 permission policy.

The binding records references to approval objects; it does not create an alternative approval engine.

### 9.4 Application

Phase 10.18 does not apply changes.

Execution remains:

```text
proposal
→ authorization
→ approval
→ apply
→ refetch
→ verify
```

The final application and operational persistence remain outside this phase.

---

## 10. Privacy and serialization

Contracts must reject inline fields or metadata keys representing:

```text
content
claim
claim_text
payload
resource_content
message
user_message
prompt
system_prompt
developer_prompt
reasoning
chain_of_thought
secret
credential
token
password
api_key
provider_request
provider_response
tool_arguments
tool_response
```

Normalization must detect:

* snake_case;
* kebab-case;
* spaces;
* camelCase;
* PascalCase;
* sensitive prefixes or suffixes.

Reference identifiers such as these remain allowed:

```text
knowledge_item_id
evidence_id
resource_id
reasoning_trace_id
knowledge_package_id
permission_decision_id
```

Metadata rules:

* string keys only;
* finite floats only;
* `allow_nan=False`;
* bounded depth;
* bounded string length;
* bounded collection size;
* no unknown objects;
* errors must not repeat sensitive rejected values.

---

## 11. Determinism

The following collections are semantically unordered and must be canonicalized:

* supporting domains;
* requested kinds;
* candidate references;
* selected references;
* excluded references;
* selection decisions;
* permission IDs;
* approval IDs;
* affected references.

IDs and digests derive from canonical representations.

Equivalent inputs in different orders must produce identical:

```text
DomainMemoryView.id
DomainMemoryView.digest
DomainMemoryProposalBinding.id
DomainMemoryProposalBinding.digest
to_dict()
```

---

## 12. Error hierarchy

Add domain-specific errors following `cmm.domains.errors`:

```text
DomainMemoryError
DomainMemoryContractError
DomainMemorySerializationError
DomainMemoryResolutionError
DomainMemoryValidationError
DomainMemoryPermissionError
DomainMemoryProposalBindingError
DomainMemoryPrivacyError
```

Messages must:

* contain stable error codes;
* avoid payload values;
* avoid PII;
* avoid `repr()` of complete mappings;
* be deterministic.

---

## 13. File structure

Create:

```text
cmm/domains/memory_contracts.py
cmm/domains/memory_view.py
cmm/domains/memory_validation.py
```

Create tests:

```text
tests/domains/test_domain_memory_contracts.py
tests/domains/test_domain_memory_view.py
tests/domains/test_domain_memory_proposals.py
tests/domains/test_domain_memory_validation.py
tests/domains/test_domain_memory_privacy.py
tests/domains/test_domain_memory_public_api.py
tests/domains/test_domain_memory_audit.py
```

Create documentation:

```text
docs/reference/domain-memory-integration.md
docs/superpowers/specs/2026-08-03-domain-memory-integration-design.md
docs/superpowers/plans/2026-08-03-domain-memory-integration-implementation-plan.md
```

Modify only when required:

```text
cmm/domains/__init__.py
cmm/domains/errors.py
tests/domains/test_domain_public_api.py
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md
```

No unrelated refactoring is included.

---

## 14. Acceptance tests

### AT-M18-01 — One shared memory

The same knowledge item selected for two domains retains one canonical ID.

No persistent domain copy is produced.

### AT-M18-02 — Authorized view

A domain view contains only references authorized by:

* domain applicability;
* permission;
* sensitivity;
* temporal validity.

Excluded references receive typed decisions.

### AT-M18-03 — Provenance and evidence

A persistent candidate requiring provenance or evidence is rejected when those references are missing.

No evidence is invented.

### AT-M18-04 — Episodic and semantic distinction

Existing episodic and semantic references retain their canonical kinds and identities.

The domain layer does not convert one into the other.

### AT-M18-05 — Version preservation

A correction or update:

* retains the prior version;
* references supersession or invalidation;
* preserves evidence and provenance;
* never overwrites history.

### AT-M18-06 — Temporal uncertainty

When relative ordering is unknown, the resolver:

* does not select a supposed latest version;
* preserves both references or the conflict;
* emits `ORDERING_UNKNOWN`.

### AT-M18-07 — Existing proposal binding

A domain proposal binding references existing:

```text
MemoryUpdateProposal
AgentKnowledgeUpdateProposal
```

It does not contain an alternative claim or proposal model.

### AT-M18-08 — Permission separation

Tests prove independently:

```text
READ
PROPOSE
APPROVE
APPLY
INVALIDATE
DELETE
```

Read authorization alone never permits writing.

### AT-M18-09 — Approval requirement

Sensitive inference, important preference modification, user-information invalidation or material ambiguity requires confirmation or approval.

### AT-M18-10 — Multidomain deduplication

Two domain views may reference the same entity, event, goal or knowledge item.

They must not create separate canonical identities.

### AT-M18-11 — Cross-domain access

A supporting domain cannot access a source-domain memory reference without effective bilateral permission.

### AT-M18-12 — Knowledge Package boundary

A `KnowledgePackage` may consume references selected by a memory view.

The view is not itself a Knowledge Package and does not duplicate its contents.

### AT-M18-13 — Proposal coverage

The binding’s affected references exactly match the canonical proposal inventory.

Omissions and introduced references fail validation.

### AT-M18-14 — Privacy

Serialized views and bindings contain no:

* claims by value;
* resource contents;
* messages;
* prompts;
* reasoning text;
* secrets;
* credentials;
* PII payloads.

### AT-M18-15 — Determinism

Equivalent inputs in different order produce identical IDs, digests and serialized output.

### AT-M18-16 — Fail-closed validation

Manipulated contracts return invalid typed results and never leak accidental exceptions.

### AT-M18-17 — Dependency direction

No dependency is introduced from Cognitive Layer or Agent Runtime back to `cmm.domains`.

### AT-M18-18 — Public API

All intended public contracts and protocols are exported from `cmm.domains`, and internal helpers remain private.

---

## 15. Required verification

Focused tests:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_memory_contracts.py \
  tests/domains/test_domain_memory_view.py \
  tests/domains/test_domain_memory_proposals.py \
  tests/domains/test_domain_memory_validation.py \
  tests/domains/test_domain_memory_privacy.py \
  tests/domains/test_domain_memory_public_api.py \
  tests/domains/test_domain_memory_audit.py
```

Regression tests:

```bash
.venv/bin/python -m pytest -q tests/domains
.venv/bin/python -m pytest -q
```

Static validation:

```bash
.venv/bin/python -m ruff check \
  cmm/domains/memory_contracts.py \
  cmm/domains/memory_view.py \
  cmm/domains/memory_validation.py \
  tests/domains/test_domain_memory_*.py

.venv/bin/python -m ruff check --target-version py310 \
  cmm/domains/memory_contracts.py \
  cmm/domains/memory_view.py \
  cmm/domains/memory_validation.py \
  tests/domains/test_domain_memory_*.py

.venv/bin/python -m compileall -q cmm tests
git diff --check
git diff --cached --check
```

Dependency-direction tests from Cognitive Layer and Agent Runtime must also remain green.

---

## 16. Completion criteria

Phase 10.18 is complete only when:

* one shared-memory principle is enforced;
* views are reference-only;
* no domain-specific store exists;
* proposals bind to existing Phase 8/9 proposals;
* read/propose/approve/apply permissions remain separate;
* provenance and evidence are preserved;
* versions and supersession preserve history;
* unknown temporal order remains unknown;
* multidomain references do not duplicate canonical identity;
* cross-domain access requires explicit permission;
* privacy scans are green;
* deterministic serialization is proven;
* focused tests pass;
* all domain tests pass;
* global tests pass;
* Ruff and compileall pass;
* dependency direction remains valid;
* documentation and roadmaps are updated;
* the final staged diff passes an independent audit.

---

## 17. Deferred responsibilities

Phase 11 remains responsible for:

* retrieving data from external systems;
* applying approved memory updates;
* refetching and verifying writes;
* operational memory persistence beyond existing stores;
* secrets and PII transformation;
* provider egress;
* UI approval surfaces;
* artifact invalidation execution;
* connector-specific temporal completeness;
* audit of provider/model/tool use.

Phase 10.18 only creates the deterministic, typed and permission-aware bridge between domains and the existing shared memory architecture.
