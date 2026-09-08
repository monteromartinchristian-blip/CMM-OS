# Phase 10.45 — Integration with Interfaces

**Status:** Implemented — independent audit pending
**Requirement:** `DP-045` (`SRC-R10:R10-C45`)
**Acceptance Test:** `AT-DP-045=PASS` (`tests/domains/test_domain_interface_dp045_acceptance.py`; connected implementation evidence only — not yet independently verified)
**Specification:** `docs/superpowers/specs/2026-09-08-phase-10.45-integration-with-interfaces-design.md`
**Implementation Plan:** `docs/superpowers/plans/2026-09-08-phase-10.45-interface-integration-implementation-plan.md`

```text
DP-045=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-045=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
next action = exact-HEAD independent audit; not Phase 10.46
```

---

## 1. Architectural Mission & Boundary Constraints

Phase 10.45 establishes the canonical, interface-neutral integration boundary that lets future conversational and graphical interfaces present Domain Intelligence state (active domain, supporting domains, workflows, questions, approvals, sources, confidence, contradictions, results, reported memory, review items) consistently, without the interfaces owning domain state, reasoners, or alternative infrastructure.

The integration is intentionally **thin, stateless, and read-only**: it projects existing canonical Domain authority into immutable, serializable, reference-only views and delegates Domain Selector intents only to existing canonical authority. It introduces no interface runtime, no UI, no widget layer, no chat loop, and no second state store.

### Strict Architectural Invariants

1. **Interface-Neutral Output Only:**
   - Projections contain validated canonical references (IDs), categories, states, and confidence values — never raw user text, statements, secrets, prompts, or interface-specific payloads.
2. **Zero Store/Runtime Ownership:**
   - `DefaultDomainInterfaceIntegrator` and `DefaultDomainAPI.project_interface`/`submit_interface_intent` perform no registry mutation, no store writes, no session mutation, and no engine invocation.
3. **No Parallel Infrastructure:**
   - No Domain-owned store, repository, event bus, runtime, engine, registry, loader, trace, approval repository, or knowledge graph is introduced.
4. **No UI / No CMMChat:**
   - Phase 10.45 defines no chat loop, no renderer, no conversational state machine, and no CMMChat/Phase 11 seam. Anything the user sees later must be rendered by Phase 11 consumers from these projections.
5. **Authority Fail-Closed:**
   - Projection accepts only exact canonical objects whose types, IDs, and statuses are coherent (`type(x) is not` checks; duck-typed impostors fail closed).
6. **Permissions Are a Visibility Ceiling:**
   - The projections never grant or widen authority; authorized visibility is bounded by the canonical inputs (composition membership, presentation visibility, approval state, permission decisions).

---

## 2. Owner Boundary Table

| Concern | Canonical Owner | Integration Seam / Delegation |
|---|---|---|
| Domain resolution state | `cmm.domains.resolver` / `resolution_contracts` | Input `DomainResolutionResult` (RESOLVED only); selector view mirrors it verbatim |
| Domain composition state | `cmm.domains.composition` / `composition_contracts` | Input `DomainComposition` (COMPOSED or PARTIAL); membership binds every projection |
| Domain registry lifecycle | `cmm.domains.registry` | Read-only `DomainRegistry` input projected into `DomainCenterView` |
| Presentation visibility | `cmm.domains.presentation` (Phase 10.16) | Input `DomainPresentationPlan` decides conversational visibility |
| Session identity | `cmm.domains.session_contracts` (Phase 10.34) | Optional `DomainSessionContext` bound by `session_reference_id` |
| Memory/knowledge projection | `cmm.domains.memory_knowledge_integration` (Phase 10.44) | Optional `DomainMemoryKnowledgeProjection` cross-checked for coherence |
| Observability | `cmm.domains.observability_*` (Phase 10.37) | Optional `DomainObservabilityReport` supplies metric/error refs |
| Cross-domain authority | `cmm.domains.cross_domain_*` | Optional `CrossDomainResult` / `CrossDomainContextSnapshot` inputs |
| Approvals | `cmm.agent_runtime.approval_contracts` (Phase 9) | Read-only `ApprovalRequest` inputs projected into Review Center |
| Permissions | `cmm.domains.permission_resolution` / `permission_evaluator` | `DomainPermissionResolver` injected for `add_supporting` intent delegation |
| Resolver delegation | `cmm.domains.resolver` (canonical `DomainResolver`) | Injected for `auto_resolve` / `select_primary` intent delegation |
| Interface projection coordination | `cmm.domains.interface_integration` (Phase 10.45) | Stateless `DefaultDomainInterfaceIntegrator` |
| Public API Facade | `cmm.domains.api` (Phase 10.36 / 10.45) | Method seams `DefaultDomainAPI.project_interface` / `submit_interface_intent` |

---

## 3. Public Contracts

Phase 10.45 introduces frozen, slotted, immutable contracts in `cmm/domains/interface_integration_contracts.py`:

- **`DomainInterfaceViewKind`**: `CONVERSATIONAL`, `SELECTOR`, `DOMAIN_CENTER`, `CROSS_DOMAIN`, `REVIEW_CENTER`.
- **`DomainInterfaceIntentKind`**: `SELECT_PRIMARY`, `AUTO_RESOLVE`, `ADD_SUPPORTING`, `WITHDRAW_SUPPORTING`, `EXPLAIN_SELECTION`, `REQUEST_POLICY_CHANGE`.
- **`DomainInterfaceStatus`**: `READY`, `PARTIAL`, `BLOCKED`, `DEGRADED`, `UNAVAILABLE`, `PENDING`.
- **`DomainInterfaceReference`**: one validated interface-neutral reference — `reference_id`, `category`, optional `domain_id`.
- **`DomainInterfaceProjectionRequest`**: `request_id`, `resolution_reference_id`, `composition_reference_id`, optional `session_reference_id`, `requested_views` (default: all five view kinds, deduplicated deterministically, never empty).
- **`DomainInterfaceProjection`**: immutable, content-bound projection — `projection_id` (`interface-projection:<request_id>`), `request_id`, `resolution_reference_id`, `composition_reference_id`, `session_reference_id`, the five optional views, and `content_digest`.
  - `content_digest` is a SHA-256 over the canonical JSON of the projection **content only**: the five view payloads plus `resolution_reference_id`, `composition_reference_id`, `session_reference_id`. It deliberately excludes `projection_id`, `request_id`, and `content_digest` itself so `to_dict()` → `from_dict()` round-trips preserve the digest exactly, and so the same content projected under different request IDs remains digest-identical (determinism).
- **`DomainInterfaceIntent`**: typed selector intent bound to canonical authority — `intent_id`, `kind`, `resolution_reference_id`, `composition_reference_id`, optional `target_domain` (required for `SELECT_PRIMARY` / `ADD_SUPPORTING` / `WITHDRAW_SUPPORTING`), optional `session_reference_id`, optional `reason`.
- **`DomainInterfaceIntentResult`**: `intent_id`, `accepted`, `status`, `resolution_reference_id`, `composition_reference_id`, `reason_code` (first blocking reason code, else first reason code, else an explicit interface-owned token — never a fabricated canonical ref).

Error additions in `cmm/domains/errors.py`: `DomainInterfaceIntegrationError` base with `DomainInterfaceContractError`, `DomainInterfaceSerializationError`, `DomainInterfaceAuthorityError`, `DomainInterfaceVisibilityError`, and `DomainInterfaceIntentError`.

---

## 4. Inputs and Outputs

### Inputs (projection)

`DefaultDomainInterfaceIntegrator.project(...)` consumes:

| Input | Canonical type | Role |
|---|---|---|
| `request` | `DomainInterfaceProjectionRequest` | Which views; which canonical resolution/composition/session |
| `resolution` | `DomainResolutionResult` | Primary/supporting domains, selection state |
| `composition` | `DomainComposition` | Final membership that every view respects |
| `presentation` | `DomainPresentationPlan?` | Conversational visibility of items/groups |
| `session` | `DomainSessionContext?` | Session identity binding |
| `memory_knowledge` | `DomainMemoryKnowledgeProjection?` | Phase 10.44 coherence cross-check |
| `registry` | `DomainRegistry?` | Domain Center lifecycle truth |
| `observability_report` | `DomainObservabilityReport?` | Metric/error references |
| `cross_domain_result` | `CrossDomainResult?` | Consolidated result truth |
| `cross_domain_snapshot` | `CrossDomainContextSnapshot?` | Transfers/dependencies/contradictions truth |
| `approvals` | `tuple[ApprovalRequest, ...]?` | Review Center truth |

### Outputs

- `DomainInterfaceProjection` — immutable, digest-bound, JSON-safe (`to_dict()`/`from_dict()` round-trip).
- `DomainInterfaceIntentResult` — reference-bound outcome of one delegated intent.

---

## 5. The Five Views

1. **`ConversationalDomainView`** (conversational UI context): `primary_domain`, `supporting_domains`, `workflow_refs`, `question_refs`, `approval_refs`, `source_refs`, `contradiction_refs`, `result_refs`, `memory_proposal_refs`, `confidence`, `warning_refs`, `status`.
   - **Visibility rule:** an item appears only if it is visible AND placed in at least one visible presentation group; hidden items (e.g., a hidden finding) never leak.
   - Supporting domains are filtered to tokens backed by visible content; no visible-content token, no domain listed.
   - `confidence` = minimum confidence over the visible items (not the hidden ones); no visible items with confidence → `None`.
   - `memory_proposal_refs` come only from the presentation plan's memory-proposal group; Phase 10.44 `memory_knowledge` is cross-checked for coherence but is not the source of conversational refs.
   - `result_refs` mirror the presentation plan's result items.
   - `status`: `READY` when the composition is complete; `PARTIAL` when the composition is partial.
2. **`DomainSelectorView`** (Domain Selector state): `primary_domain`, `supporting_domains`, `rejected_domains`, `ambiguous_domains`, `reason_refs`, `requires_clarification`, `status`.
   - A **verbatim mirror** of the canonical resolution result — no reinterpretation. Only a `RESOLVED` canonical resolution produces `status=READY`; anything else keeps the canonical state (e.g., requires clarification) and never claims readiness.
3. **`DomainCenterView`** (installed domains): deterministic entries sorted by `domain_id`, each with `domain_id`, `status`, `enabled`, `version`, `capability_refs`, `permission_refs`, `operation_refs`, `workflow_refs`, `metric_refs`, `error_refs`, `update_status`.
   - Registry lifecycle state (active/disabled/degraded, enabled flag, version) is projected verbatim from the canonical registry records.
   - `capability_refs`/`permission_refs`/`operation_refs`/`workflow_refs` come from canonical registry manifests; `metric_refs`/`error_refs` come from the observability report only.
   - `update_status` is always `"unknown"` — Phase 10.45 owns no update-check authority and never fabricates one.
4. **`CrossDomainInterfaceView`** (cross-domain coordination): `primary_domain`, `supporting_domains`, `transfer_refs`, `dependency_refs`, `conflict_refs`, `consolidated_result_ref`, `status`.
   - **Transfers:** only authorized transfers whose target domain is a composed (non-primary) member and whose source domain is not private to the primary domain are projected; a private transfer never crosses the boundary.
   - **Dependencies:** canonical dependency references `dependency:<source.slug>:<target.slug>:<kind>` projected verbatim from the snapshot when result and snapshot agree, with result-first precedence (`_canonical_dependencies`); dependencies among non-member domains or unresolvable contradictions never fabricate a dependency.
   - **Contradictions:** unresolved, membership-bound contradictions; result-first precedence (`_canonical_contradictions`); resolved contradictions never resurface.
   - **Status:** `PARTIAL` when the composition is partial (or the result is PARTIAL); `PENDING` when there is no consolidated result yet; `READY` when the result is COMPLETED; `PARTIAL` when the result is PARTIAL or LIMIT_REACHED; else `BLOCKED`.
5. **`DomainReviewCenterView`** (Review Center): items sorted by `review_ref`, each with `review_ref`, `category`, `state`, optional `domain_id`, `operation_ref`, `workflow_ref`, `session_ref`, `reason_ref`.
   - Only **open** approval requests (`PENDING`, `POSTPONED`) are projected; terminal approvals are not review items.
   - Category mapping is strict: `DOMAIN_CROSS_ACCESS` approvals → `cross_domain_access`; operation approvals require reason codes starting with `domain_operation.` plus operation metadata scope `domain_operation` → `operation_approval`; the canonical `sensitive_persistence` / `external_action` categories are recognized through the mapping table. Requests whose category cannot be canonically determined are suppressed.
   - Every item is membership-bound: a review item whose domain is not the primary or a composed supporting domain is suppressed.

---

## 6. Selector Intent Delegation

`DefaultDomainInterfaceIntegrator.submit_intent(...)` delegates each typed `DomainInterfaceIntent` only to canonical authority and **never mutates** resolution, composition, or session state:

| Intent | Behavior | Verdict semantics |
|---|---|---|
| `EXPLAIN_SELECTION` | Read-only: canonical resolution already carries authoritative reasons | `accepted=True`, `status=READY`, reason code from canonical reasons |
| `AUTO_RESOLVE` / `SELECT_PRIMARY` | Delegated to the injected canonical `DomainResolver.resolve(resolution_context)`; result must be an exact canonical `DomainResolutionResult` | RESOLVED → `READY`/accepted (for `SELECT_PRIMARY`, accepted only when the canonical primary domain equals the intent target); UNSUPPORTED → `UNAVAILABLE`; BLOCKED/FAILED/blocking-reason → `BLOCKED`; otherwise `PENDING` |
| `ADD_SUPPORTING` | Requires canonical `CrossDomainPermissionRequest` bound to intent target + composed primary domain, delegated to the injected canonical `DomainPermissionResolver.resolve_cross_domain` | DENY → `BLOCKED` (reason = decision's first canonical reason); APPROVAL_REQUIRED → `PENDING`; ALLOW → `UNAVAILABLE` (`domain_selector_supporting_application_unavailable`: Phase 10.45 owns no composition-mutation seam) |
| `WITHDRAW_SUPPORTING` | Requires the target to be a composed supporting domain; no canonical withdrawal seam exists in Phase 10 | `UNAVAILABLE` with `domain_selector_withdrawal_unavailable` |
| `REQUEST_POLICY_CHANGE` | No canonical policy-change mutation seam exists in Phase 10 | `UNAVAILABLE` with `domain_selector_policy_change_requires_later_platform` |

Interface-owned reason tokens (`domain_selector_*`) are used only where no canonical authority produced a reason, and explicitly state the missing later-platform seam rather than pretending to be canonical references. Missing delegations (no injected resolver/permission resolver) yield `UNAVAILABLE` with `domain_selector_resolver_unavailable` / `domain_selector_permission_evaluator_unavailable` — never a silent grant. Selector targeting restrictions are enforced fail-closed (`SELECT_PRIMARY` requires the target to be in the canonical resolution context's `explicit_domains`; permission evidence must bind to the actual source/target pair; otherwise `DomainInterfaceAuthorityError`).

---

## 7. Authority Binding

`project()` verifies, before any view is built:

- exact canonical types (`type(x) is not`) for `resolution`, `composition`, and every non-`None` optional input — duck-typed impostors fail closed;
- `resolution.status == RESOLVED` and composition status `COMPOSED` or `PARTIAL` (AMBIGUOUS / INSUFFICIENT_INFORMATION / BLOCKED / UNSUPPORTED / FAILED fail closed);
- `request.resolution_reference_id == resolution.id`, `request.composition_reference_id == composition.id`, and `composition.resolution_id == resolution.id`;
- resolution/composition primary domains agree and supporting-domain sets agree exactly;
- when present: `presentation.composition_id == composition.id`; `session.session_id == request.session_reference_id` (a provided session without a request session reference fails closed); exact canonical types for `memory_knowledge`, `registry`, `observability_report`; `cross_domain_result`/`cross_domain_snapshot` declare a `composition_id` equal to `composition.id`; `approvals` contain only exact canonical `ApprovalRequest` entries.

`submit_intent()` validates the same core resolution/composition/reference coherence plus intent-specific bindings (target-domain requirements, explicit-domain membership, permission-request source/target binding) before delegating.

---

## 8. Permissions and Visibility

- The projections expose references only for domains and items that canonical authority already made visible: composition membership for selector/cross-domain/review-center content, presentation visibility for conversational content, approval state for review content, registry state for Domain Center content.
- Phase 10.45 never computes, grants, or widens permissions; `ADD_SUPPORTING` is the only permission-consuming path and it forwards the caller-supplied canonical request to the canonical permission resolver, presenting the decision verbatim.
- Private-domain transfers and hidden items are suppressed outright (fail-closed), never partially projected.
- No sensitive payload is projected: refs and state tokens only — raw text, statements, excerpts, prompts, secrets, credentials are outside the contract surface.

---

## 9. Determinism and Serialization

- Views are assembled from ordered canonical inputs; domain-center and review-center entries are deterministically sorted (`domain_id`, `review_ref`); tuple fields are normalized/deduplicated deterministically.
- `content_digest` = SHA-256 over the canonical JSON of projection content; `DomainInterfaceProjection.__post_init__` recomputes it and rejects a supplied digest that does not match, so serialization tampering fails closed.
- `to_dict()` / `from_dict()` round-trip is exact (including digest preservation), making projections safe to hand to any future interface layer.

---

## 10. Side-Effect Boundary

- `project()` performs zero store lookups, zero writes, zero registry/session/approval mutations.
- `submit_intent()` performs zero mutations; delegation is confined to the injected canonical `DomainResolver` (pure re-resolution) and `DomainPermissionResolver` (pure permission evaluation), and the returned verdict never applies a membership change.
- No Domain Events are published, no approval repository is touched, and no session state changes as a consequence of Phase 10.45 calls.

---

## 11. CMMChat / Phase 11 Boundary

Phase 10.45 deliberately stops at interface-*neutral* projections and typed intents. Rendering, chat loops, UI widgets, navigation, and human-in-the-loop interaction remain CMMChat / Phase 11 consumers. Phase 10.45 provides them with:

- permission- and visibility-filtered reference sets they can render consistently;
- typed selector intents they can submit without owning domain logic;
- deterministic serialization for transport and persistence by a later platform.

Anything not present in the five views (update availability, policy change mutation, composition application) is explicitly reported as `UNAVAILABLE`/`unknown` with a reason token, never invented.

---

## 12. Verification Evidence

- `tests/domains/test_domain_interface_integration_contracts.py`: 37 contract tests — enums, immutability (frozen/slotted), reference normalization, confidence validation, requested-views deduplication/emptiness, Domain Center ordering, serialization round-trips, and projection content-digest semantics.
- `tests/domains/test_domain_interface_integration.py`: 73 integration tests — authority binding (exact canonical types; duck-typed impostors, non-RESOLVED resolutions, non-COMPOSED/PARTIAL compositions, reference mismatches, session/presentation/cross-domain binding mismatches fail closed), projection purity (no mutation), requested-view kinds, conversational projection (visibility, supporting-domain filtering, confidence floor over visible items, stale-reference exclusion), Domain Center projection (verbatim lifecycle incl. disabled/degraded entries, `update_status="unknown"`), cross-domain projection (authorized transfer refs, canonical dependency refs with result-first precedence, unresolved contradiction refs, status derivation), Review Center projection (open-state filtering, category mapping, membership suppression), selector view mirroring, and selector intent submission verdicts.
- `tests/domains/test_domain_interface_integration_api.py`: 10 tests — `DefaultDomainAPI.project_interface` / `submit_interface_intent` delegation and canonical error propagation through the facade.
- `tests/domains/test_domain_interface_integration_architecture.py`: 8 AST boundary tests — no forbidden infrastructure classes, no UI/framework imports, no direct memory/cognitive access, no reverse dependencies from cognitive/agent_runtime into Phase 10.45 modules.
- `tests/domains/test_domain_interface_dp045_acceptance.py`: 1 connected acceptance test (`AT-DP-045`) — real canonical resolution/composition over four real Domain Packs (university primary; health, oppositions, life-plan supporting), real registry lifecycle (enabled, disabled, degraded), real session context, real observability report, real cross-domain snapshot + COMPLETED result, real Phase 9 approvals repository, real Phase 10.18 memory view + Phase 10.44 memory-knowledge projection, real presentation plan (visible and hidden items), real permission policies, and the `DefaultDomainAPI` facade — asserting all five views, digest round-trip, determinism, forbidden-payload absence, adversarial branches (authority mismatch, denied/pending cross-domain support, disabled/degraded registry entries, explicit-domain enforcement, proposal/intent non-mutation, visibility confidence semantics, stale-reference exclusion, canonical dependency kinds, partial-composition status propagation), and ending state immutability.
- **Connected acceptance output:** `AT-DP-045=PASS` as implementation evidence only. Status markers: `DP-045=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION`; `AT-DP-045=PASS_REPORTED`; `CLOSURE_ELIGIBLE=NO` — independent exact-HEAD audit still pending; Phase 10.46 has not started.
