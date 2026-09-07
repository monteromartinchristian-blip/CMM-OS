# Phase 10.44 — Integration with Memory and Knowledge Graph

**Status:** `IMPLEMENTED_PENDING_INDEPENDENT_AUDIT`
**Requirement:** `DP-044` (`SRC-R10:R10-C44`)
**Acceptance Test:** `AT-DP-044` (`tests/domains/test_domain_memory_knowledge_dp044_acceptance.py` — `PASS`)
**Specification:** `docs/superpowers/specs/2026-09-07-phase-10.44-integration-with-memory-and-knowledge-graph-design.md`
**Implementation Plan:** `docs/superpowers/plans/2026-09-07-phase-10.44-memory-knowledge-graph-integration-implementation-plan.md`

```text
DP-044=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
AT-DP-044=PASS
CLOSURE_ELIGIBLE=NOT_YET_ASSESSED
```

---

## 1. Architectural Mission & Boundary Constraints

Phase 10.44 establishes the canonical bridge between Domain Intelligence (`cmm.domains`) and the Cognitive Layer Knowledge and Memory infrastructure (established in Phase 8 and Phase 10.18).

The integration is intentionally thin, stateless, and read-only: Domain Intelligence does not own a Knowledge Graph, Knowledge Store, alternative memory repository, temporal engine, contradiction engine, or causal inference engine.

### Strict Architectural Invariants

1. **No Domain-Owned Graph or Knowledge Store:**
   - There is no Domain-owned Knowledge Graph, Knowledge Store, persistent memory engine, graph database, or alternative knowledge truth.
   - All underlying knowledge items, relations, contradictions, and evidence reside exclusively in canonical Phase 8 stores (`cmm.cognitive`).
2. **Zero Direct Store Writes:**
   - `DefaultDomainMemoryKnowledgeIntegrator` and `DefaultDomainAPI` perform zero writes, updates, deletes, or mutations on cognitive or memory stores.
3. **No Direct Import of `cmm.memory`:**
   - `cmm/domains/memory_knowledge_integration.py` and `cmm/domains/memory_knowledge_integration_contracts.py` have 0 imports of `cmm.memory` or `TechnicalMemory`. Memory access flows exclusively through Phase 10.18 contracts (`DomainMemoryView`, `DomainMemoryReference`).
4. **No Reverse Imports:**
   - `cmm.cognitive` and `cmm.agent_runtime` contain 0 imports of `cmm.domains.memory_knowledge_integration*`.
5. **No Causal Strengthening:**
   - Multi-hop paths and weaker relations (`supports`, `related_to`, `refines`) are never promoted to direct causal edges (`causes`).
6. **No Fake Contradictions:**
   - Temporal succession, version updates, and supersession are never emitted as contradictions.
7. **Privacy Fail-Closed:**
   - Projections contain structural references and IDs only. Raw statements, excerpts, reasoning tokens, prompts, secrets, and credentials are strictly excluded from projection contracts and serialization.

---

## 2. Owner Boundary Table

| Concern | Canonical Owner | Integration Seam / Delegation |
|---|---|---|
| Knowledge Items & Stores | `cmm.cognitive` (Phase 8) | Read-only input via `DomainMemoryKnowledgeInventory` |
| Knowledge Relations & Contradictions | `cmm.cognitive` (Phase 8) | Read-only input via `DomainMemoryKnowledgeInventory` |
| Memory Views & Reference Selection | `cmm.domains.memory_view` (Phase 10.18) | Input `DomainMemoryView` resolved by `DefaultDomainMemoryViewResolver` |
| Memory View & Binding Validation | `cmm.domains.memory_validation` (Phase 10.18) | Fail-closed validation via `DefaultDomainMemoryIntegrationValidator` |
| Knowledge Update Proposals | `cmm.agent_runtime` (Phase 9) | Created by `KnowledgeUpdateProposalEngine`, bound via `DomainMemoryProposalBinding` |
| Knowledge Projection Coordination | `cmm.domains.memory_knowledge_integration` (Phase 10.44) | Stateless coordinator `DefaultDomainMemoryKnowledgeIntegrator` |
| Public API Facade | `cmm.domains.api` (Phase 10.36 / 10.44) | Method seam `DefaultDomainAPI.project_memory_knowledge` |

---

## 3. Public Contracts

Phase 10.44 introduces frozen, slotted, immutable contracts in `cmm/domains/memory_knowledge_integration_contracts.py`:

- **`DomainMemoryKnowledgeProjectionCapability`**: Enum representing requested capabilities:
  - `SHARED_IDENTITIES`: cross-domain reference reuse.
  - `RELATIONS`: canonical relations between selected references.
  - `TIMELINE`: chronological timeline of temporal references.
  - `CONTRADICTIONS`: canonical contradictions between selected references.
  - `DEPENDENCIES`: multi-hop dependency paths.
  - `IMPACT_PATHS`: multi-hop impact paths.
  - `RELATION_PROPOSALS`: validated Phase 10.18 proposal bindings.

- **`DomainMemoryKnowledgeProjectionRequest`**: Immutable input request specifying:
  - `request_id`, `primary_domain`, `supporting_domains`, `memory_view_id`, `memory_view_digest`, `resolution_reference_id`, `composition_reference_id`, `permission_decision_ids`, `requested_capabilities`.

- **`DomainMemoryKnowledgeInventory`**: Read-only explicit inventory of:
  - `relations`: tuple of canonical `KnowledgeRelation`.
  - `contradictions`: tuple of canonical `Contradiction`.
  - `proposal_bindings`: tuple of `DomainMemoryProposalBinding`.

- **`DomainMemoryKnowledgeRelationRef`**: Immutable projection of a canonical relation hop:
  - `relation_id`, `source_reference_id`, `target_reference_id`, `kind`, `confidence`.

- **`DomainMemoryKnowledgeContradictionRef`**: Immutable projection of a canonical contradiction:
  - `contradiction_id`, `reference_ids`, `resolution_reference_id`.

- **`DomainMemoryKnowledgePathHop`**: Explicit single hop in a path:
  - `relation_id`, `source_reference_id`, `target_reference_id`, `kind`.

- **`DomainMemoryKnowledgePath`**: Cycle-safe multi-hop path (length >= 2):
  - `path_id`, `hops`, `length`.

- **`DomainMemoryKnowledgeProjection`**: Complete deterministic projection output:
  - `projection_id`, `request_id`, `primary_domain`, `supporting_domains`, `memory_view_id`, `selected_reference_ids`, `excluded_reference_ids`, `shared_identity_reference_ids`, `relation_refs`, `timeline_reference_ids`, `unknown_ordering_reference_ids`, `contradiction_refs`, `dependency_paths`, `impact_paths`, `proposal_binding_ids`, `content_digest`.

---

## 4. Projection Pipeline

`DefaultDomainMemoryKnowledgeIntegrator.project(...)` executes an 11-step pure projection pipeline:

```text
DomainMemoryKnowledgeProjectionRequest
    │
    ▼
1. Request / View / MemoryRequest Coherence Check
    ├── Verify memory_view_id == view.view_id
    ├── Verify memory_view_digest == view.digest
    └── Verify primary_domain and request_id coherence
    │
    ▼
2. Authority Coherence Validation
    └── Ensure requested permission_decision_ids ⊆ memory_request.permission_decision_ids
    │
    ▼
3. Phase 10.18 View Validation
    └── DefaultDomainMemoryIntegrationValidator.validate_view(...) must be valid
    │
    ▼
4. Identity Selection & Shared Identity Detection
    ├── selected_reference_ids = view.selected_references
    └── Detect references where len(applicable_domains) >= 2 or active in >= 2 domains
    │
    ▼
5. Canonical Relation Projection
    ├── Filter inventory relations where source and target are both in selected_references
    └── Suppress fail-closed if either endpoint was excluded or missing
    │
    ▼
6. Chronological Timeline Projection
    ├── Separate references with known aware timestamps from unknown_ordering
    └── Sort deterministically by (valid_from/observed_at, reference_id)
    │
    ▼
7. Canonical Contradiction Projection
    ├── Filter inventory contradictions where both items are in selected_references
    └── Fail closed (suppress) if either participant is missing from view
    │
    ▼
8. Multi-Hop Dependency and Impact Path Derivation
    ├── Pure DFS traversal over projected relations, cycle-safe, max-depth bounded
    └── Emit only paths with length >= 2; preserve exact hop relation IDs and kinds
    │
    ▼
9. Proposal Binding Validation
    ├── Validate each proposal binding via DefaultDomainMemoryIntegrationValidator.validate_binding(...)
    └── Fail closed if binding does not validate against view and inventory
    │
    ▼
10. Anti-Fragmentation & Sensitive Payload Sanitization
    └── Prohibit raw statements, reasoning text, excerpts, secrets, credentials
    │
    ▼
11. Content Digest & Deterministic Projection Assembly
    └── Compute sha256 content digest and domain-memory-knowledge-projection ID
```

---

## 5. Phase 10.18 and Phase 9 Reuse

- **Phase 10.18 Memory Views:** The projection operates exclusively over an already-resolved `DomainMemoryView`. Candidates, exclusions, and sensitivity restrictions are respected without modification.
- **Phase 10.18 View Validator:** `DefaultDomainMemoryIntegrationValidator.validate_view(...)` is invoked to enforce structural integrity, authority coverage, and temporal validity before any projection logic runs.
- **Phase 10.18 Proposal Bindings:** `DomainMemoryProposalBinding` connects agent knowledge update proposals to domain views, traces, affected references, and permission decisions.
- **Phase 9 Knowledge Update Proposals:** The proposal engine (`KnowledgeUpdateProposalEngine`) and repository (`InMemoryKnowledgeUpdateRepository`) remain the sole proposal creators and containers. No proposals are applied or mutated during projection.

---

## 6. Permissions, Privacy, and Fail-Closed Suppression

- **Permission Bounds:** The integrator requires permission decision coverage for the projection. If authority is downgraded or revoked, affected references are excluded upstream by the Phase 10.18 view resolver.
- **Fail-Closed Endpoint Suppression:** Relations and contradictions whose endpoints include an excluded reference are completely suppressed from the projection. They are never exposed in partial or dangling state.
- **No Sensitive Leakage:** `FORBIDDEN_PAYLOAD_FIELDS` strictly prohibits serializing `statement`, `excerpt`, `raw_content`, `prompt`, `reasoning_text`, `chain_of_thought`, `source_payload`, `resource_content`, `secret`, or `credential`.

---

## 7. Relation Semantics and No Causal Strengthening

- Multi-hop paths preserve the exact canonical relation ID and kind of every hop.
- Traversal of an impact path containing weaker non-causal edges (such as `related_to` or `supports`) never synthesizes a new direct causal edge (`causes`) between the origin and destination nodes.
- Direct edges in `relation_refs` are strictly 1:1 projections of canonical relations present in the input inventory.

---

## 8. Verification Evidence

- `tests/domains/test_domain_memory_knowledge_integration_contracts.py`: 32 unit contract tests (validation, immutability, serialization, round-trips).
- `tests/domains/test_domain_memory_knowledge_integration.py`: 26 integration tests covering view validation, authority coherence, shared identities, relation projection, fail-closed suppression, timelines, contradictions, multi-hop paths, proposal bindings, and DomainAPI delegation.
- `tests/domains/test_domain_memory_knowledge_architecture.py`: 7 boundary tests verifying 0 AST imports of `cmm.memory`, 0 reverse imports from cognitive/agent_runtime, no parallel owners, no store mutation, and no sensitive leakage.
- `tests/domains/test_domain_memory_knowledge_dp044_acceptance.py`: Connected end-to-end acceptance test verifying all 24 positive checkpoints, downgraded authority adversarial branch, causal adversarial branch, and temporal adversarial branch.
- **Total Phase 10.44 Test Suite:** **66 passed locally in 1.50s**.
- **Connected Acceptance Output:** `AT-DP-044=PASS`.
