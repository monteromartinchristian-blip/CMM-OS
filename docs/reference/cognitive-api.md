# Cognitive Layer Public API Reference

This document describes the public surface exported by `cmm.cognitive`.

---

## 1. Resources

### `Resource`
Represents an external input document, message, or dataset.
- **Fields**: `id`, `domain`, `kind` (`ResourceKind`), `source` (`ResourceSourceKind`), `content`, `provenance` (`ResourceProvenance`), `reliability` (`Confidence`), `temporal_scope` (`ResourceTemporalScope`), `version`, `language`, `entity_ids`, `relationship_ids`, `sensitivity`, `permissions`, `integrity`, `created_at`, `updated_at`, `metadata`.
- **Methods**: `serialize()`, `to_dict()`, `from_mapping(payload)`, `from_dict(data)`.

### `ResourceInput`
Unprocessed input submitted for adaptation/extraction.

### `ResourceExtractionService`
Orchestrates adapter selection and knowledge extractor invocation.

---

## 2. Base Contracts & Identifiers

### `Confidence`
Epistemic certainty level attached to claims or evidence.
- **Fields**: `value` (float between 0.0 and 1.0), `source` (str | None), `reasons` (tuple[str, ...]), `metadata` (`MappingProxyType`).
- **Methods**: `to_dict()`.

### `CognitiveActor`
Entity taking an action or providing input.
- **Fields**: `id`, `kind` (`CognitiveActorKind`), `name`, `permissions`, `metadata`.

### `CognitiveFinding`
Diagnostic finding or warning during cognitive processing.

### `CognitiveResult`
Standard result wrapper containing status, confidence, findings, and metadata.

### `CognitiveIdentifier`
Namespace-qualified identifier structure (`namespace:kind:value`).
- **Methods**: `parse(raw)`, `generate(namespace, kind)`.

---

## 3. Knowledge Model

### `TemporalScope`
Temporal validity boundaries.
- **Fields**: `kind` (`TemporalScopeKind`), `observed_at`, `valid_from`, `valid_until`, `expires_at`, `last_verified_at`, `metadata`.
- **Methods**: `is_valid_at(moment)`, `validity_status`, `serialize()`, `from_mapping(payload)`.

### `Evidence`
Traceable proof linked to a resource.
- **Fields**: `id`, `resource_id`, `fragment`, `confidence`, `kind` (`EvidenceKind`), `polarity` (`EvidencePolarityKind`), `locator`, `section`, `page`, `char_start`, `char_end`, `actor_id`, `extraction_candidate_id`, `resource_provenance_id`, `observed_at`, `metadata`.

### `KnowledgeRelation`
Typed directional relationship between two items.
- **Fields**: `id`, `source_id`, `target_id`, `kind` (`KnowledgeRelationKind`), `confidence`, `actor_id`, `provenance`, `created_at`, `metadata`.

### `KnowledgeItem`
Canonical unit of knowledge in CMM OS.
- **Fields**: `id`, `statement`, `kind` (`KnowledgeKind`), `confidence`, `status` (`KnowledgeStatus`), `evidence`, `relations`, `temporal_scope`, `sensitivity`, `actor_id`, `resource_id`, `version`, `supersedes_id`, `superseded_by_id`, `invalidated_at`, `invalidation_reason`, `created_at`, `updated_at`, `metadata`.
- **Methods**: `is_active`, `invalidate(reason)`, `create_revision(...)`, `mark_superseded(by_id)`, `serialize()`, `from_mapping(payload)`.

### `Contradiction`
Explicit representation of conflict between two items.

### `KnowledgeBundle`
Immutable container grouping knowledge items, evidence, relations, and findings.

---

## 4. Knowledge Store

### `KnowledgeStoreProtocol`
Interface implemented by local knowledge stores.
- **Methods**: `transaction()`, `save_item`, `get_item`, `contains_item`, `delete_item`, `list_items`, `count_items`, `save_evidence`, `get_evidence`, `save_relation`, `get_relation`, `save_contradiction`, `get_contradiction`, `save_bundle`, `get_bundle`.

### `InMemoryKnowledgeStore`
In-memory implementation with snapshot-based transaction rollback.

### `SQLiteKnowledgeStore` (`LocalKnowledgeStore`)
SQLite-backed persistent store with Acid transactions and JSON serialization.

---

## 5. Knowledge Retrieval

### `KnowledgeQuery` / `KnowledgeQueryResult`
Query parameters for filtering items by kind, status, resource ID, actor ID, sensitivity, text, and temporal validity.

### `KnowledgeRetriever`
Query engine that executes queries against any `KnowledgeStoreProtocol` implementation.

---

## 6. Knowledge Consolidation

### `KnowledgeConsolidator`
Detects potential duplicates and constructs/applies consolidation plans.
- **Methods**: `find_candidates(query=None)`, `build_plan(candidates, actor_id, dry_run=True)`, `preview_plan(plan)`, `apply_plan(plan)`.

---

## 7. Contradiction Detection & Resolution

### `KnowledgeContradictionDetector`
Compares items using conservative heuristics to detect direct opposition, negation, quantitative mismatch, and temporal conflict.

### `KnowledgeContradictionResolver`
Generates proposals (`ContradictionResolutionProposal`) for resolving contradictions without mutating the store.

### `ContradictionResolutionPolicyEngine`
Evaluates proposals against safety policies (`ResolutionPolicyEvaluation`).

### `ContradictionResolutionExecutor`
Executes authorized proposals atomically (`ResolutionExecutionResult`, `ResolutionAuditRecord`).

---

## 8. Resolution Memory & Reflection

### `ResolutionMemoryStore` / `InMemoryResolutionMemoryStore`
Stores non-destructive historical decision entries (`ResolutionMemoryEntry`).

### `CognitiveReflectionEngine`
Analyzes resolution memory to produce analytical reports (`CognitiveReflectionReport`, `ReflectionFinding`).

---

## 9. Cognitive Integration Cycle

### `CognitiveCycleEngine`
End-to-end cycle orchestrator.
- **Methods**: `run_cycle(item_ids=None, query=None, actor_id=None, created_at=None, metadata=None) -> CognitiveCycleRecord`.

---

## 10. Errors Hierarchy

Root error: `CognitiveError`
- `InvalidConfidenceError`
- `InvalidCognitiveIdentifierError`
- `InvalidCognitiveContractError`
- `InvalidResourceError`
- `KnowledgeStoreError` (`KnowledgeStoreNotFoundError`, `KnowledgeStoreConflictError`, `KnowledgeStoreCorruptionError`, `KnowledgeStoreSchemaError`, `KnowledgeStoreSerializationError`)
- `KnowledgeRetrievalError` (`InvalidKnowledgeQueryError`, `UnsupportedKnowledgeQueryError`)
- `KnowledgeConsolidationError` (`InvalidConsolidationCandidateError`, `InvalidConsolidationPlanError`, `KnowledgeConsolidationConflictError`, `KnowledgeConsolidationApplicationError`, `ManualReviewRequiredError`)
- `KnowledgeContradictionDetectionError` (`InvalidContradictionSignalError`, `InvalidContradictionDetectionError`, `KnowledgeContradictionConflictError`, `ContradictionRegistrationError`)
- `KnowledgeContradictionResolutionError` (`InvalidResolutionProposalError`, `ResolutionConflictError`)
- `KnowledgeResolutionPolicyError` (`InvalidResolutionPolicyEvaluationError`, `ResolutionPolicyConflictError`)
- `KnowledgeResolutionExecutionError` (`InvalidResolutionExecutionError`, `ResolutionExecutionConflictError`, `ResolutionExecutionRollbackError`)
- `KnowledgeResolutionMemoryError` (`InvalidResolutionMemoryEntryError`, `ResolutionMemoryConflictError`)
- `KnowledgeReflectionError` (`InvalidReflectionReportError`, `ReflectionAnalysisConflictError`)
- `KnowledgeCognitiveCycleError` (`InvalidCognitiveCycleError`, `CognitiveCycleExecutionError`)
