# Phase 10.18 — Domain Memory Integration Reference

**Status:** Implemented (audit v4 corrections applied)
**Date:** 2026-08-03
**Subsystem:** Domain Intelligence (`cmm.domains`)

## Overview

Phase 10.18 integrates Domain Intelligence with the existing shared memory, knowledge, temporal, provenance, permission, approval, and update-proposal contracts established in Phase 8 (`cmm.cognitive`) and Phase 9 (`cmm.agent_runtime`).

The phase adds deterministic reference-only domain view resolution and reference-only proposal bindings. It does not introduce a secondary memory store, domain-specific graph, claim model, provenance system, temporal engine, or Knowledge Package.

---

## Non-Negotiable Architecture

1. **One Shared Memory**: All knowledge items, relations, evidence, resources, and temporal scopes reside in the shared Cognitive Layer (`cmm.cognitive`).
2. **Reference-Only Domain Views**: A `DomainMemoryView` contains references (`DomainMemoryReference`) to canonical memory items. It never duplicates claim text, raw resource contents, messages, prompts, reasoning/chain-of-thought, secrets, or PII.
3. **Reference-Only Proposal Bindings**: A `DomainMemoryProposalBinding` links domain executions (`domain_id`, `trace_id`, `view_id`, `view_digest`) to existing canonical Phase 8 `MemoryUpdateProposal` and/or Phase 9 `AgentKnowledgeUpdateProposal` objects by ID.
4. **Capability Separation**: Read, propose, approve, apply, invalidate, and delete are distinct capabilities (`READ != PROPOSE != APPROVE != APPLY != INVALIDATE != DELETE`). Read permission alone never authorizes proposals or memory modifications.
5. **Content-Bound IDs**: `view_id` and `binding_id` derive from canonical content digests. Two objects with different content cannot share an ID.
6. **Canonical Identity Uniqueness**: `canonical_id` maps to exactly one reference identity. Multiple `reference_id` values for the same `canonical_id` are rejected.
7. **Closed Metadata Vocabulary**: Metadata values are validated against closed per-key vocabularies. Free-text strings are rejected.
8. **Temporal Reference-Only Snapshot**: `DomainMemoryTemporalSnapshot` mirrors `cmm.cognitive.TemporalScope` without duplicating the temporal engine.
9. **Pure & Deterministic**: The resolver (`DefaultDomainMemoryViewResolver`) and validator (`DefaultDomainMemoryIntegrationValidator`) are pure algorithms that receive all candidate references and inventory explicitly. They perform no I/O, network requests, store queries, or state mutations.
10. **Dependency Direction**: Strictly `cmm.domains -> cmm.cognitive / cmm.agent_runtime`. No reverse dependencies exist.

---

## Public API & Exported Symbols

The following contracts, protocols, services, and errors are exported from `cmm.domains`:

### Enums
- `DomainMemoryCapability`: Closed enum of canonical domain memory capabilities (`READ`, `PROPOSE`, `APPROVE`, `APPLY`, `INVALIDATE`, `DELETE`).
- `DomainMemorySensitivityLevel`: Closed enum of sensitivity levels (`NORMAL`, `RESTRICTED`, `SECRET`, `HIGH`).
- `DomainMemoryProposalKind`: Closed enum of proposal kinds (`MEMORY_UPDATE`, `AGENT_KNOWLEDGE_UPDATE`).
- `DomainMemoryReferenceKind`: Closed enum of canonical reference kinds (`KNOWLEDGE_ITEM`, `KNOWLEDGE_RELATION`, `EVIDENCE`, `RESOURCE`, `CONTRADICTION`, `VERSION`, `RESOLUTION_MEMORY_ENTRY`, `KNOWLEDGE_PACKAGE`).
- `DomainMemoryTemporalKind`: Closed enum mirroring `cmm.cognitive.TemporalScopeKind` (`UNKNOWN`, `TIMELESS`, `POINT_IN_TIME`, `INTERVAL`, `SAFETY`).
- `DomainMemorySelectionDecisionCode`: Closed enum of view selection decision outcomes (`SELECTED`, `EXCLUDED_DOMAIN_INAPPLICABLE`, `EXCLUDED_PERMISSION_DENIED`, `EXCLUDED_PERMISSION_MISSING`, `EXCLUDED_PERMISSION_UNSCOPED`, `EXCLUDED_SENSITIVITY_RESTRICTED`, `EXCLUDED_TEMPORAL_INVALID`, `EXCLUDED_TEMPORAL_UNKNOWN`, `EXCLUDED_TEMPORAL_EXPIRED`, `EXCLUDED_SUPERSEDED`, `EXCLUDED_DUPLICATE`, `EXCLUDED_UNSUPPORTED_KIND`, `EXCLUDED_PROVENANCE_MISSING`, `EXCLUDED_EVIDENCE_MISSING`, `EXCLUDED_CONFIRMATION_REQUIRED`, `EXCLUDED_ORDERING_UNKNOWN`, `EXCLUDED_PRESERVED_CONFLICT`, `EXCLUDED_MISSING_REFERENCE`, `EXCLUDED_REFERENCE_MISMATCH`, `EXCLUDED_INVALIDATED`).
- `DomainMemoryValidationCode`: Closed enum of integration validation codes (`VALID`, `INVALID_REFERENCE_INTEGRITY`, `INVALID_PRIVACY_BREACH`, `INVALID_PERMISSION_DENIED`, `INVALID_PERMISSION_UNSCOPED`, `INVALID_APPROVAL_REQUIRED`, `INVALID_APPROVAL_COVERAGE_MISMATCH`, `INVALID_PROVENANCE_MISSING`, `INVALID_EVIDENCE_MISSING`, `INVALID_TEMPORAL_INVARIANT`, `INVALID_VERSION_INVARIANT`, `INVALID_PROPOSAL_COVERAGE`, `INVALID_PROPOSAL_KIND_MISMATCH`, `INVALID_DUPLICATE_PROPOSAL_CLASSIFICATION`, `INVALID_TRACE_VIEW_MISMATCH`, `INVALID_DIGEST_TAMPERED`, `INVALID_MISSING_REFERENCE`, `INVALID_REFERENCE_MISMATCH`, `INVALID_STRUCTURE`).

### Immutable Contracts & Snapshots
- `DomainMemoryReference`: Immutable reference descriptor containing IDs and policy metadata.
- `DomainMemoryTemporalSnapshot`: Frozen reference-only snapshot of a `cmm.cognitive.TemporalScope`.
- `DomainMemoryViewRequest`: Deterministic request containing primary/supporting domains, requested kinds, candidate references, permission decisions, and optional temporal reference.
- `DomainMemorySelectionDecision`: Selection or exclusion outcome for a candidate reference.
- `DomainMemoryView`: Reference-only result containing request and domain identity, required full canonical `request_digest` (SHA-256 of `DomainMemoryViewRequest`), optional trace and temporal context, selection decisions, and selected references. `view_id` is content-bound.
- `DomainMemoryProposalBinding`: Reference-only binding linking domain trace/view execution and the exact full `view_digest` to canonical update proposals. `binding_id` is content-bound.
- `DomainMemoryPermissionDecisionSnapshot`: Frozen reference-only snapshot of a permission decision.
- `DomainMemoryProposalSnapshot`: Frozen reference-only snapshot of a memory/knowledge proposal. Requires at least one explicit write capability; `READ` is never allowed.
- `DomainMemoryApprovalRequestSnapshot`: Frozen reference-only snapshot of an approval request.
- `DomainMemoryApprovalDecisionSnapshot`: Frozen reference-only snapshot of an approval decision.
- `DomainMemoryTraceSnapshot`: Frozen reference-only snapshot of a reasoning trace.
- `DomainMemoryViewSnapshot`: Frozen reference-only snapshot of a domain memory view. Includes `view_digest`.
- `DomainMemoryReferenceInventory`: Authoritative external inventory containing typed snapshot tuples supplied by caller for validator execution.
- `DomainMemoryValidationResult`: Structured non-PII diagnostic outcome of view or proposal binding validation.

### Services & Protocols
- `DomainMemoryViewResolver`: `@runtime_checkable` protocol for view resolution.
- `DefaultDomainMemoryViewResolver`: Pure, deterministic default view resolver implementation.
- `DomainMemoryIntegrationValidator`: `@runtime_checkable` protocol for integration validation.
- `DefaultDomainMemoryIntegrationValidator`: Pure, fail-closed default integration validator implementation.

### Error Hierarchy
- `DomainMemoryError` (inherits `DomainError`)
- `DomainMemoryContractError`
- `DomainMemorySerializationError`
- `DomainMemoryResolutionError`
- `DomainMemoryValidationError`
- `DomainMemoryPermissionError`
- `DomainMemoryProposalBindingError`
- `DomainMemoryPrivacyError`

---

## ID & Digest Formats

### View ID
```
view:<request_id>:<content_digest_prefix>
```
The content digest is computed from the view's canonical content (`request_id`, `primary_domain`, required `request_digest`, optional `trace_id`, optional `temporal_reference`, `selection_decisions`, and `selected_references`). `request_digest` is the complete 64-character SHA-256 digest of the `DomainMemoryViewRequest`. Any change in `supporting_domains`, `resolution_reference_id`, `requested_kinds`, `permission_decision_ids`, `trace_id`, or `temporal_reference` changes `request.digest` and produces a distinct `view_id`. `validate_view` demands exact equality between `view.request_digest` and `request.digest`.

### Binding ID
```
binding:<domain_id>:<trace_id>:<view_id>:<content_digest_prefix>
```
The content digest is computed from the binding's canonical content (`domain_id`, `trace_id`, `view_id`, full `view_digest`, proposal IDs, affected references, permissions, and approvals). Two bindings with different content produce different IDs.

### Digest
All digests are SHA-256 hex digests of canonical JSON serialization (sorted keys, no NaN).

---

## Core Invariants & Rules

1. **Exact Coverage & Disjointness**: For every candidate in a view request, the resolver produces exactly one decision. The set of selected references and excluded decisions in a `DomainMemoryView` are disjoint and cover all request candidates exactly.
2. **Proposal Affected-Reference Coverage**: `DefaultDomainMemoryIntegrationValidator.validate_binding` verifies that `binding.affected_reference_ids` matches the exact set of target reference IDs extracted from canonical proposal objects in `inventory`. Omissions or introduced references fail validation.
3. **Capability Separation**: `DomainMemoryProposalSnapshot` requires at least one explicit write capability (`PROPOSE`, `APPROVE`, `APPLY`, `INVALIDATE`, `DELETE`). `READ` is never allowed in `required_capabilities`. The validator has no implicit fallback to `PROPOSE`.
4. **Content-Bound IDs**: `view_id` and `binding_id` include canonical digest prefixes. `DomainMemoryViewSnapshot` and `DomainMemoryProposalBinding` require full SHA-256 `view_digest` values. The validator requires exact equality between both digests.
5. **Canonical Identity Uniqueness**: `DomainMemoryViewRequest` and `DomainMemoryReferenceInventory` reject multiple `reference_id` values for the same `canonical_id`. A single canonical item can be applicable to multiple domains through `applicable_domains`.
6. **Closed Metadata Vocabulary**: Metadata values are validated against closed per-key vocabularies (`category`, `status`, `tag`, `priority`, `source_type`, `domain_tag`). Free-text strings, PII tokens, DNI/phone patterns, and unrecognized values are rejected with sanitized error messages.
7. **Temporal Reference-Only**: `DomainMemoryTemporalSnapshot` preserves `kind`, `observed_at`, `valid_from`, `valid_to`, `expires_at`, `last_verified_at`, `invalidated`, `invalidation_reason`, and `superseded_by`. The resolver filters candidates by temporal validity against the request's `temporal_reference`.
8. **History Preservation**: Superseded versions (`superseded_by_id`) are excluded with `EXCLUDED_SUPERSEDED` without erasing historical items. Unresolved conflicts (`has_unresolved_conflict=True`) are preserved with `EXCLUDED_PRESERVED_CONFLICT`. Unknown temporal order (`has_unknown_ordering=True`) is preserved as `EXCLUDED_ORDERING_UNKNOWN`. Invalidated items are excluded with `EXCLUDED_INVALIDATED`.
9. **Strict Privacy Boundary**: All metadata dictionary keys and values are checked recursively against forbidden markers and closed vocabularies. Breaches raise `DomainMemoryPrivacyError` with sanitized error messages that never echo rejected keys or values.
10. **Strict Serialization**: `from_dict` methods reject unknown fields, legacy aliases, and ambiguous payloads. `DomainMemoryValidationResult.from_dict` rejects `diagnostics`. `DomainMemoryView.from_dict` rejects `excluded_decisions`. `DomainMemoryReferenceInventory.from_dict` rejects `memory_proposals`/`agent_knowledge_proposals` aliases.

---

## Boundary with Phase 11

Phase 10.18 provides the reference-only view resolution, proposal binding, and integration validation for Domain Intelligence. Persistent execution, live state persistence, autonomous memory update application, and system-wide orchestration remain governed by Phase 11.