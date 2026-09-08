# Phase 10.44 — Integration with Memory and Knowledge Graph

**Status:** `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT`
**Requirement:** `DP-044` (`SRC-R10:R10-C44`)
**Acceptance Test:** `AT-DP-044` (`tests/domains/test_domain_memory_knowledge_dp044_acceptance.py` — implementation marker `PASS_REPORTED`)
**Specification:** `docs/superpowers/specs/2026-09-07-phase-10.44-integration-with-memory-and-knowledge-graph-design.md`
**Implementation Plan:** `docs/superpowers/plans/2026-09-07-phase-10.44-memory-knowledge-graph-integration-implementation-plan.md`

```text
DP-044=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
AT-DP-044=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
V1 independent audit = FAIL (docs/audits/phase-10.44-independent-audit-v1.md)
V2 independent re-audit = FAIL (docs/audits/phase-10.44-independent-reaudit-v2.md)
V3 independent re-audit = FAIL (docs/audits/phase-10.44-independent-reaudit-v3.md)
V3 blockers remediated; independent V4 re-audit pending
independently audited closure boundary = 10.43 (Phase 10.44 not closed)
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
  - `request_id`, `primary_domain`, `supporting_domains`, `memory_view_id`, `memory_view_digest`, `resolution_reference_id`, `composition_reference_id`, `permission_decision_ids`, `requested_capabilities`, `trace_id`, `session_id`, `temporal_reference`.
  - Deterministic read-only `digest` property (SHA-256 over the canonical `to_dict()`); covers every authority/semantic field above. `trace_id`/`session_id` are context-bound identifiers carried into the digest, not independently verified authority proofs.

- **`DomainMemoryKnowledgeInventory`**: Read-only explicit inventory of:
  - `relations`: tuple of canonical `KnowledgeRelation`.
  - `contradictions`: tuple of canonical `Contradiction`.
  - `proposal_bindings`: tuple of `DomainMemoryProposalBinding`.

- **`DomainMemoryKnowledgeRelationRef`**: Immutable projection of a canonical relation hop:
  - `relation_id`, `source_reference_id`, `target_reference_id`, `kind`, `provenance_reference`.
  - `kind` must be a live canonical Phase 8 `KnowledgeRelationKind` value (`supports`, `contradicts`, `derived_from`, `refines`, `supersedes`, `equivalent_to`, `related_to`, `answers`, `raises_question`); any free-string/malformed kind fails closed. This vocabulary is distinct from the Phase 9 proposal `relation_type="depends_on"` (dependency-proposal semantics, not Cognitive relation truth).

- **`DomainMemoryKnowledgeContradictionRef`**: Immutable projection of a canonical contradiction:
  - `contradiction_id`, `reference_ids`, `resolution_reference_id`.

- **`DomainMemoryKnowledgePathHop`**: Explicit single hop in a path:
  - `relation_id`, `source_reference_id`, `target_reference_id`, `kind`.

- **`DomainMemoryKnowledgePath`**: Cycle-safe path over one or more connected hops (the public contract validates at least one hop; production dependency/impact derivation emits only paths of length >= 2):
  - `path_id`, `hops`, `content_digest` (`path_id` is content-bound to the ordered-hop digest; hop `kind` values obey the same canonical `KnowledgeRelationKind` boundary).

- **`DomainMemoryKnowledgeProjection`**: Complete deterministic projection output:
  - `projection_id`, `request_id`, `request_digest`, `memory_view_id`, `memory_view_digest`, `selected_reference_ids`, `shared_identity_reference_ids`, `relation_refs`, `timeline_reference_ids`, `unknown_ordering_reference_ids`, `contradiction_refs`, `dependency_paths`, `impact_paths`, `proposal_binding_ids`, `excluded_reference_ids`, `content_digest`.
  - `request_digest` is the exact `DomainMemoryKnowledgeProjectionRequest.digest` that produced the projection and is included in `content_digest`/`projection_id` derivation, `to_dict()`, `from_dict()`, and round-trip validation.

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
    ├── Verify primary_domain and request_id coherence
    ├── Verify supporting_domains coherence with the Phase 10.18 request
    ├── Verify temporal_reference coherence with the Phase 10.18 request
    ├── Require explicit caller-supplied canonical resolution + composition
    ├── Verify exact canonical DomainResolutionResult / DomainComposition types
    ├── Verify resolution.status == RESOLVED (only final authority projects; AMBIGUOUS/INSUFFICIENT_INFORMATION/BLOCKED/UNSUPPORTED/FAILED fail closed)
    ├── Verify resolution_reference_id == resolution.id
    ├── Verify composition_reference_id == composition.id
    ├── Verify composition.resolution_id == resolution.id
    ├── Verify memory_request.resolution_reference_id == resolution.id (Phase 10.18 view content-bound to the same canonical resolution identity)
    └── Verify resolution/composition primary domains match the request
    │
    ▼
2. Authority Coherence Validation
    └── Ensure requested permission_decision_ids exactly equal the validated memory request IDs (fail-closed on divergence)
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
    ├── Reject any relation whose kind is not a live `KnowledgeRelationKind` instance (fail-closed, no string fallback)
    └── Suppress fail-closed if either endpoint was excluded or missing
    │
    ▼
6. Chronological Timeline Projection
    ├── POINT_IN_TIME anchors on canonical observed_at only
    ├── INTERVAL anchors on canonical interval-start valid_from only (structurally valid intervals)
    ├── TIMELESS / UNKNOWN / domain-only safety kinds carry no chronology (unknown ordering)
    └── Sort deterministically by (canonical anchor, reference_id); ties imply no stronger semantics
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
    └── Compute sha256 content digest (including request_digest) and domain-memory-knowledge-projection ID
```

---

## 5. Phase 10.18 and Phase 9 Reuse

- **Phase 10.18 Memory Views:** The projection operates exclusively over an already-resolved `DomainMemoryView`. Candidates, exclusions, and sensitivity restrictions are respected without modification.
- **Phase 10.18 View Validator:** `DefaultDomainMemoryIntegrationValidator.validate_view(...)` is invoked to enforce structural integrity, authority coverage, and temporal validity before any projection logic runs.
- **Phase 10.18 Proposal Bindings:** `DomainMemoryProposalBinding` connects agent knowledge update proposals to domain views, traces, affected references, and permission decisions.
- **Phase 9 Knowledge Update Proposals:** The proposal engine (`KnowledgeUpdateProposalEngine`) and repository (`InMemoryKnowledgeUpdateRepository`) remain the sole proposal creators and containers. No proposals are applied or mutated during projection. The relation-proposal checkpoint exercises the real LINK path (checkpoint with `dependencies` → `KnowledgeCandidateKind.DEPENDENCY` → `LINK` → `AgentKnowledgeUpdateProposal.relations` with `relation_type="depends_on"`), binds the exact proposal ID through `DefaultDomainMemoryIntegrationValidator.validate_binding(...)`, and proves the proposal stays pending with Cognitive stores unchanged.
- **Phase 10.18 Temporal Authority:** The old/current incompatible-period adversarial branch resolves history vs current through the real `DefaultDomainMemoryViewResolver` (superseded, invalidated, and expired references excluded upstream and preserved in inventory history, never merged or reintroduced by Phase 10.44).

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

- `tests/domains/test_domain_memory_knowledge_integration_contracts.py`: 53 unit contract tests (validation, immutability, serialization, round-trips).
- `tests/domains/test_domain_memory_knowledge_integration.py`: 42 integration tests covering view validation, canonical authority binding (exact canonical `DomainResolutionResult`/`DomainComposition` types with coherent supporting domains; duck-typed impostors fail closed; only `RESOLVED` resolution status is final authority — `AMBIGUOUS`, `INSUFFICIENT_INFORMATION`, and `BLOCKED` real canonical resolutions fail closed; the Phase 10.18 memory request must carry the same canonical resolution reference as the projection request/resolution/composition, so a stale or unbound memory view is rejected; COMPOSED/PARTIAL accepted, BLOCKED/FAILED rejected), authority coherence, shared identities, relation projection, fail-closed suppression, timelines, contradictions, multi-hop paths, proposal bindings, and DomainAPI delegation.
- `tests/domains/test_domain_memory_knowledge_architecture.py`: 10 boundary tests verifying 0 AST imports of `cmm.memory`, 0 reverse imports from cognitive/agent_runtime, no parallel owners, no store mutation, and no sensitive leakage.
- `tests/domains/test_domain_memory_knowledge_dp044_acceptance.py`: Connected end-to-end acceptance test verifying all 24 positive checkpoints, real `DomainResolutionResult.status == RESOLVED` and the connected resolution chain (`mem_req.resolution_reference_id == req.resolution_reference_id == resolution.id == composition.resolution_id`; `view.request_digest == mem_req.digest`), the real Phase 9 relation-proposal checkpoint (non-empty `relations` with expected `depends_on` target semantics), the identical proposal binding replayed under downgraded (denied/absent) `PROPOSE` authority with no binding projected and proposal repository decisions/results unchanged, downgraded READ-suppression authority adversarial branch, causal adversarial branch, and the genuine old/current incompatible-period temporal adversarial branch (history preserved, current-only truth, canonical supersession lineage exclusion pointing at the current reference identity, no merge, succession not contradiction).
- **Connected Acceptance Output:** `AT-DP-044=PASS_REPORTED` (implementation evidence only; V1 independent audit `FAIL`, V2 independent re-audit `FAIL`, and V3 independent re-audit `FAIL` recorded; V3 blockers remediated; independent verification remains pending V4 re-audit).
