"""Phase 10.44 — Domain Memory and Knowledge Graph Integration.

Stateless, reference-only Domain-owned integration boundary over Phase 10.18
memory views, Phase 8 Cognitive Layer knowledge semantics, and Phase 9
Agent Runtime update proposals.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.errors import (
    DomainMemoryKnowledgeAuthorizationError,
    DomainMemoryKnowledgeProjectionError,
)
from cmm.domains.memory_contracts import (
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryTemporalKind,
    DomainMemoryView,
    DomainMemoryViewRequest,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeContradictionRef,
    DomainMemoryKnowledgeIntegrator,
    DomainMemoryKnowledgeInventory,
    DomainMemoryKnowledgePath,
    DomainMemoryKnowledgePathHop,
    DomainMemoryKnowledgeProjection,
    DomainMemoryKnowledgeProjectionCapability,
    DomainMemoryKnowledgeProjectionRequest,
    DomainMemoryKnowledgeRelationRef,
)
from cmm.domains.memory_validation import (
    DefaultDomainMemoryIntegrationValidator,
    DomainMemoryIntegrationValidator,
)

DEFAULT_DEPENDENCY_RELATION_KINDS: frozenset[str] = frozenset(
    {
        "depends_on",
        "part_of",
        "blocks",
        "enables",
        "derived_from",
        "supports",
    }
)

DEFAULT_IMPACT_RELATION_KINDS: frozenset[str] = frozenset(
    {
        "depends_on",
        "part_of",
        "blocks",
        "enables",
        "derived_from",
        "supports",
        "correlated_with",
        "caused_by",
        "refines",
        "supersedes",
    }
)

DEFAULT_MAX_PATH_DEPTH = 10


def _is_shared_identity(
    ref: DomainMemoryReference,
    request: DomainMemoryKnowledgeProjectionRequest,
) -> bool:
    """Determine if a canonical reference is shared across domains."""
    if len(ref.applicable_domains) >= 2:
        return True
    participating = {str(request.primary_domain)} | {
        str(d) for d in request.supporting_domains
    }
    ref_domains = {str(ref.domain_id)} | {str(d) for d in ref.applicable_domains}
    return len(ref_domains & participating) >= 2


def _derive_knowledge_paths(
    relation_refs: tuple[DomainMemoryKnowledgeRelationRef, ...],
    allowed_kinds: frozenset[str],
    max_depth: int = DEFAULT_MAX_PATH_DEPTH,
) -> tuple[DomainMemoryKnowledgePath, ...]:
    """Pure, cycle-safe derivation of multi-hop knowledge paths.

    Operates strictly over already-projected relation references with no hidden store
    lookups or graph object creation. Emits deterministic paths of length >= 2.
    """
    eligible_rels = [r for r in relation_refs if r.kind in allowed_kinds]
    if not eligible_rels:
        return ()

    adj: dict[str, list[DomainMemoryKnowledgeRelationRef]] = {}
    for r in eligible_rels:
        adj.setdefault(r.source_reference_id, []).append(r)

    for rel_list in adj.values():
        rel_list.sort(key=lambda r: (r.target_reference_id, r.relation_id))

    paths: list[DomainMemoryKnowledgePath] = []
    start_nodes = sorted(adj.keys())

    for start_node in start_nodes:

        def dfs(
            current_node: str,
            current_hops: list[DomainMemoryKnowledgePathHop],
            used_relation_ids: set[str],
        ) -> None:
            if len(current_hops) >= 2:
                paths.append(DomainMemoryKnowledgePath.create(current_hops))

            if len(current_hops) >= max_depth:
                return

            for rel in adj.get(current_node, ()):
                if rel.relation_id in used_relation_ids:
                    continue

                hop = DomainMemoryKnowledgePathHop(
                    relation_id=rel.relation_id,
                    source_reference_id=rel.source_reference_id,
                    target_reference_id=rel.target_reference_id,
                    kind=rel.kind,
                )
                used_relation_ids.add(rel.relation_id)
                current_hops.append(hop)

                dfs(rel.target_reference_id, current_hops, used_relation_ids)

                current_hops.pop()
                used_relation_ids.remove(rel.relation_id)

        dfs(start_node, [], set())

    # Deterministic ordering of emitted paths
    return tuple(
        sorted(
            paths,
            key=lambda p: (
                p.hops[0].source_reference_id,
                p.hops[-1].target_reference_id,
                p.path_id,
            ),
        )
    )


class DefaultDomainMemoryKnowledgeIntegrator(DomainMemoryKnowledgeIntegrator):
    """Default implementation of DomainMemoryKnowledgeIntegrator.

    Stateless coordination over Phase 10.18 memory views and explicit canonical
    inventories. Performs no hidden store lookups and no direct store writes.
    """

    def __init__(
        self,
        *,
        memory_validator: DomainMemoryIntegrationValidator | None = None,
        dependency_relation_kinds: frozenset[str] | None = None,
        impact_relation_kinds: frozenset[str] | None = None,
        max_path_depth: int = DEFAULT_MAX_PATH_DEPTH,
    ) -> None:
        self._memory_validator = (
            memory_validator
            if memory_validator is not None
            else DefaultDomainMemoryIntegrationValidator()
        )
        self._dependency_relation_kinds = (
            dependency_relation_kinds
            if dependency_relation_kinds is not None
            else DEFAULT_DEPENDENCY_RELATION_KINDS
        )
        self._impact_relation_kinds = (
            impact_relation_kinds
            if impact_relation_kinds is not None
            else DEFAULT_IMPACT_RELATION_KINDS
        )
        self._max_path_depth = max_path_depth

    def project(
        self,
        request: DomainMemoryKnowledgeProjectionRequest,
        *,
        memory_request: DomainMemoryViewRequest,
        view: DomainMemoryView,
        memory_inventory: DomainMemoryReferenceInventory,
        inventory: DomainMemoryKnowledgeInventory,
    ) -> DomainMemoryKnowledgeProjection:
        """Project authorized canonical knowledge over an authorized Phase 10.18 view."""
        # 1. Structural request / view / memory_request coherence
        if request.memory_view_id != view.view_id:
            raise DomainMemoryKnowledgeProjectionError(
                f"memory_view_id mismatch: request={request.memory_view_id}, view={view.view_id}"
            )
        if request.memory_view_digest != view.digest:
            raise DomainMemoryKnowledgeProjectionError(
                f"memory_view_digest mismatch: request={request.memory_view_digest}, view={view.digest}"
            )
        if str(request.primary_domain) != str(view.primary_domain):
            raise DomainMemoryKnowledgeProjectionError(
                f"primary_domain mismatch: request={request.primary_domain}, view={view.primary_domain}"
            )
        if memory_request.request_id != view.request_id:
            raise DomainMemoryKnowledgeProjectionError(
                f"memory_request request_id mismatch: mem_req={memory_request.request_id}, view={view.request_id}"
            )

        # 2. Authority coherence: requested permission decisions must be covered by memory_request
        if not set(request.permission_decision_ids).issubset(
            set(memory_request.permission_decision_ids)
        ):
            raise DomainMemoryKnowledgeAuthorizationError(
                "Requested permission decisions not present in validated memory request"
            )

        # 3. Phase 10.18 view validation
        val_result = self._memory_validator.validate_view(
            view, memory_request, memory_inventory
        )
        if not val_result.is_valid:
            raise DomainMemoryKnowledgeProjectionError(
                f"DomainMemoryView failed validation: {val_result.code}"
            )

        # 4. Identity selection: only view.selected_references
        selected_refs = view.selected_references
        selected_ref_ids = tuple(sorted({r.reference_id for r in selected_refs}))
        excluded_ref_ids = tuple(
            sorted({d.reference_id for d in view.excluded_decisions})
        )

        # Shared identities
        shared_ref_ids: tuple[str, ...] = ()
        if (
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES
            in request.requested_capabilities
        ):
            shared_ref_ids = tuple(
                sorted(
                    {
                        r.reference_id
                        for r in selected_refs
                        if _is_shared_identity(r, request)
                    }
                )
            )

        # 5. Canonical relation projection
        ref_by_canonical_id = {r.canonical_id: r for r in selected_refs}
        relation_refs_list: list[DomainMemoryKnowledgeRelationRef] = []
        needs_relations = bool(
            {
                DomainMemoryKnowledgeProjectionCapability.RELATIONS,
                DomainMemoryKnowledgeProjectionCapability.DEPENDENCIES,
                DomainMemoryKnowledgeProjectionCapability.IMPACT_PATHS,
            }
            & set(request.requested_capabilities)
        )
        if needs_relations:
            for rel in inventory.relations:
                src_ref = ref_by_canonical_id.get(rel.source_id)
                tgt_ref = ref_by_canonical_id.get(rel.target_id)
                if src_ref is None or tgt_ref is None:
                    # Endpoint hidden or unavailable -> suppress relation fail-closed
                    continue
                if src_ref.reference_id == tgt_ref.reference_id:
                    continue
                kind_val = (
                    rel.kind.value if hasattr(rel.kind, "value") else str(rel.kind)
                )
                prov = rel.provenance if rel.provenance else None
                relation_refs_list.append(
                    DomainMemoryKnowledgeRelationRef(
                        relation_id=rel.id,
                        source_reference_id=src_ref.reference_id,
                        target_reference_id=tgt_ref.reference_id,
                        kind=kind_val,
                        provenance_reference=prov,
                    )
                )

        all_relation_refs = tuple(
            sorted(relation_refs_list, key=lambda r: r.relation_id)
        )
        relation_refs = (
            all_relation_refs
            if DomainMemoryKnowledgeProjectionCapability.RELATIONS
            in request.requested_capabilities
            else ()
        )

        # 6. Timeline and unknown ordering projection
        timeline_ref_ids: tuple[str, ...] = ()
        unknown_ordering_ids: tuple[str, ...] = ()
        if (
            DomainMemoryKnowledgeProjectionCapability.TIMELINE
            in request.requested_capabilities
        ):
            timeline_items: list[tuple[datetime, str]] = []
            unknown_set: set[str] = set()

            for r in selected_refs:
                if r.has_unknown_ordering:
                    unknown_set.add(r.reference_id)
                    continue

                if (
                    r.temporal is None
                    or r.temporal.kind == DomainMemoryTemporalKind.UNKNOWN
                ):
                    if r.temporal is not None or r.has_unknown_ordering:
                        unknown_set.add(r.reference_id)
                    continue

                anchor_str = (
                    r.temporal.valid_from
                    or r.temporal.observed_at
                    or r.temporal.last_verified_at
                    or r.temporal.valid_to
                    or r.temporal.expires_at
                )
                if not anchor_str:
                    unknown_set.add(r.reference_id)
                    continue

                try:
                    dt = datetime.fromisoformat(anchor_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    timeline_items.append((dt, r.reference_id))
                except (ValueError, TypeError):
                    unknown_set.add(r.reference_id)

            for d in view.excluded_decisions:
                if d.code.value in (
                    "excluded_ordering_unknown",
                    "excluded_temporal_unknown",
                ):
                    unknown_set.add(d.reference_id)

            timeline_items.sort(key=lambda item: (item[0], item[1]))
            timeline_ref_ids = tuple(item[1] for item in timeline_items)
            unknown_ordering_ids = tuple(sorted(unknown_set))

        # 7. Canonical contradiction projection
        contradiction_refs: tuple[DomainMemoryKnowledgeContradictionRef, ...] = ()
        if (
            DomainMemoryKnowledgeProjectionCapability.CONTRADICTIONS
            in request.requested_capabilities
        ):
            c_refs_list: list[DomainMemoryKnowledgeContradictionRef] = []
            for c in inventory.contradictions:
                src_ref = ref_by_canonical_id.get(c.item_a_id)
                tgt_ref = ref_by_canonical_id.get(c.item_b_id)
                if src_ref is None or tgt_ref is None:
                    # Partial participant missing / hidden -> fail closed
                    continue
                if src_ref.reference_id == tgt_ref.reference_id:
                    continue

                res_ref_id: str | None = None
                if (
                    getattr(c, "preferred_id", None)
                    and c.preferred_id in ref_by_canonical_id
                ):
                    res_ref_id = ref_by_canonical_id[c.preferred_id].reference_id
                elif getattr(c, "resolution_reference_id", None) is not None:
                    res_ref_id = c.resolution_reference_id

                c_refs_list.append(
                    DomainMemoryKnowledgeContradictionRef(
                        contradiction_id=c.id,
                        reference_ids=tuple(
                            sorted([src_ref.reference_id, tgt_ref.reference_id])
                        ),
                        resolution_reference_id=res_ref_id,
                    )
                )
            contradiction_refs = tuple(
                sorted(c_refs_list, key=lambda x: x.contradiction_id)
            )

        # 8. Dependency and impact paths
        dependency_paths: tuple[DomainMemoryKnowledgePath, ...] = ()
        if (
            DomainMemoryKnowledgeProjectionCapability.DEPENDENCIES
            in request.requested_capabilities
        ):
            dependency_paths = _derive_knowledge_paths(
                all_relation_refs,
                self._dependency_relation_kinds,
                self._max_path_depth,
            )

        impact_paths: tuple[DomainMemoryKnowledgePath, ...] = ()
        if (
            DomainMemoryKnowledgeProjectionCapability.IMPACT_PATHS
            in request.requested_capabilities
        ):
            impact_paths = _derive_knowledge_paths(
                all_relation_refs,
                self._impact_relation_kinds,
                self._max_path_depth,
            )

        # 9. Proposal bindings
        proposal_binding_ids: tuple[str, ...] = ()
        if (
            DomainMemoryKnowledgeProjectionCapability.RELATION_PROPOSALS
            in request.requested_capabilities
        ):
            valid_binding_ids: list[str] = []
            for b in inventory.proposal_bindings:
                if b.view_id != view.view_id or b.view_digest not in (
                    view.digest,
                    view.content_digest,
                ):
                    continue
                val_res = self._memory_validator.validate_binding(b, memory_inventory)
                if val_res.is_valid:
                    valid_binding_ids.append(b.binding_id)
            proposal_binding_ids = tuple(sorted(set(valid_binding_ids)))

        return DomainMemoryKnowledgeProjection.create(
            request_id=request.request_id,
            memory_view_id=view.view_id,
            memory_view_digest=view.digest,
            selected_reference_ids=selected_ref_ids,
            shared_identity_reference_ids=shared_ref_ids,
            relation_refs=relation_refs,
            timeline_reference_ids=timeline_ref_ids,
            unknown_ordering_reference_ids=unknown_ordering_ids,
            contradiction_refs=contradiction_refs,
            dependency_paths=dependency_paths,
            impact_paths=impact_paths,
            proposal_binding_ids=proposal_binding_ids,
            excluded_reference_ids=excluded_ref_ids,
        )
