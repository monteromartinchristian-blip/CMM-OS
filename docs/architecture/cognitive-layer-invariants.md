# Cognitive Layer Invariants

The Cognitive Layer enforces 12 formal invariants across all contracts, stores, engines, and workflows.

---

## Invariante 1 — Epistemic preservation

**Definition**: No cognitive component or operation may delete historical knowledge automatically without explicit invalidation or supersession tracking.

- **Valid**: Marking an item `SUPERSEDED` with `superseded_by_id` pointing to the replacement, or `INVALIDATED` with `invalidation_reason` and `invalidated_at`.
- **Invalid**: Overwriting or deleting a `KnowledgeItem` from the store during resolution without maintaining lineage links.

---

## Invariante 2 — Detect before resolve

**Definition**: Resolution proposals and executions cannot occur without a preceding formal contradiction detection signal or explicit conflict context.

- **Valid**: A `ContradictionResolutionProposal` generated from a verified `ContradictionDetection` result.
- **Invalid**: Directly executing a preference or invalidation on arbitrary items without a registered contradiction.

---

## Invariante 3 — Propose before authorize

**Definition**: The resolution engine generates proposals (`ContradictionResolutionProposal`); it does not evaluate policies or mutate stores directly.

- **Valid**: `resolver.propose_resolutions(contradiction, item_a, item_b)` returning immutable proposal objects.
- **Invalid**: A resolver modifying item statuses or writing audit records directly to `KnowledgeStore`.

---

## Invariante 4 — Authorize before execute

**Definition**: The `ContradictionResolutionExecutor` requires a valid, matching `ResolutionPolicyEvaluation` with `allowed=True` and `decision=PolicyDecision.AUTO_APPROVED`.

- **Valid**: Executor checking `evaluation.proposal_id == proposal.id` and verifying `allowed` before modifying store state.
- **Invalid**: Executing a proposal that was flagged for `REQUEST_HUMAN_REVIEW`, `REJECTED`, or `DEFERRED`.

---

## Invariante 5 — Executor-only mutation

**Definition**: Only the `KnowledgeStore` methods and `ContradictionResolutionExecutor` (acting through store transactions) may mutate cognitive state.

- **Valid**: `executor.execute(proposal, evaluation)` updating items inside `store.transaction()`.
- **Invalid**: Policy engine or reflection engine altering item statuses or relations.

---

## Invariante 6 — Atomic mutation

**Definition**: Multi-operation changes (such as candidate consolidation or proposal execution) must be performed inside an atomic transaction block with TOCTOU checks.

- **Valid**: `with store.transaction():` verifying expected fingerprints before applying consolidation actions.
- **Invalid**: Applying item updates sequentially across separate un-transactioned calls where intermediate failure leaves store inconsistent.

---

## Invariante 7 — No silent information loss

**Definition**: When knowledge items are merged or superseded, all source evidence, relations, and provenance details must be preserved or re-linked.

- **Valid**: Merging items by creating a target item that combines evidence lists and maintains `supersedes_id` pointers.
- **Invalid**: Dropping evidence items or relation links during consolidation or preference execution.

---

## Invariante 8 — Immutable contracts

**Definition**: All public dataclass contracts are defensively immutable (`frozen=True`, `slots=True`, tuple fields, `MappingProxyType` metadata).

- **Valid**: `obj.metadata` returning a `MappingProxyType` that raises `TypeError` on attempted mutation.
- **Invalid**: Exposing internal mutable `dict` or `list` references that allow external code to modify state in-place.

---

## Invariante 9 — Deterministic identity

**Definition**: IDs and fingerprints are generated deterministically using SHA-256 digests over canonical JSON or explicit payload seeds, never Python `hash()`, random state, or unseeded wall timestamps when determinism is required.

- **Valid**: `generate_cognitive_cycle_id(...)` creating `cognitive-cycle:<sha256_hash>`.
- **Invalid**: Using `hash(statement)` or `uuid4()` for fingerprinting or candidate matching.

---

## Invariante 10 — Auditability

**Definition**: Every resolution applied produces a complete, deterministic audit trail (`ResolutionAuditRecord`, `ResolutionMemoryEntry`).

- **Valid**: Executor returning a `ResolutionExecutionResult` containing an explicit `ResolutionAuditRecord` with timestamps, proposal ID, and item IDs.
- **Invalid**: Updating knowledge item status without creating an execution log entry or memory record.

---

## Invariante 11 — Reflection is descriptive

**Definition**: Cognitive reflection is purely analytical and descriptive. It analyzes decision history to compute metrics and findings without modifying stores, rules, or policies.

- **Valid**: `CognitiveReflectionEngine.reflect(memory_store)` returning a `CognitiveReflectionReport`.
- **Invalid**: Reflection engine automatically altering policy parameters, deleting memory entries, or triggering resolution workflows.

---

## Invariante 12 — Agency separation

**Definition**: The Cognitive Layer processes knowledge, contradictions, and reflections when called. It does not initiate background tasks, pursue goals, or execute actions on its own initiative.

- **Valid**: Providing typed APIs for retrieval, detection, resolution, and cycle execution invoked by external orchestrators or CLI commands.
- **Invalid**: Spawning autonomous agent loops or background background threads within cognitive modules.
