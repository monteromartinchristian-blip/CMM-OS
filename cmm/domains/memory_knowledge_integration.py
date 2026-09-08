"""Phase 10.44 — Domain Memory and Knowledge Graph Integration.

Stateless, reference-only Domain-owned integration boundary over Phase 10.18
memory views, Phase 8 Cognitive Layer knowledge semantics, and Phase 9
Agent Runtime update proposals.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import KnowledgeRelationKind
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import DomainCompositionStatus, DomainResolutionStatus
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
from cmm.domains.resolver_contracts import DomainResolutionResult

DEFAULT_DEPENDENCY_RELATION_KINDS: frozenset[str] = frozenset(
    {
        KnowledgeRelationKind.DERIVED_FROM.value,
        KnowledgeRelationKind.SUPPORTS.value,
        KnowledgeRelationKind.REFINES.value,
        KnowledgeRelationKind.SUPERSEDES.value,
    }
)

DEFAULT_IMPACT_RELATION_KINDS: frozenset[str] = frozenset(
    {
        KnowledgeRelationKind.SUPPORTS.value,
        KnowledgeRelationKind.DERIVED_FROM.value,
        KnowledgeRelationKind.REFINES.value,
        KnowledgeRelationKind.SUPERSEDES.value,
        KnowledgeRelationKind.RELATED_TO.value,
        KnowledgeRelationKind.EQUIVALENT_TO.value,
    }
)

DEFAULT_MAX_PATH_DEPTH = 10


def _canonical_temporal_anchor(ref: DomainMemoryReference) -> str | None:
    temporal = ref.temporal
    if temporal is None:
        return None
    if temporal.kind == DomainMemoryTemporalKind.POINT_IN_TIME:
        return temporal.observed_at
    if temporal.kind == DomainMemoryTemporalKind.INTERVAL:
        if temporal.valid_from is None or temporal.valid_to is None:
            return None
        return temporal.valid_from
    return None


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
        canonical_values = frozenset(item.value for item in KnowledgeRelationKind)
        if dependency_relation_kinds is not None and not set(
            dependency_relation_kinds
        ).issubset(canonical_values):
            raise DomainMemoryKnowledgeProjectionError(
                "dependency_relation_kinds must be canonical KnowledgeRelationKind values"
            )
        if impact_relation_kinds is not None and not set(
            impact_relation_kinds
        ).issubset(canonical_values):
            raise DomainMemoryKnowledgeProjectionError(
                "impact_relation_kinds must be canonical KnowledgeRelationKind values"
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
        resolution: DomainResolutionResult | None = None,
        composition: DomainComposition | None = None,
    ) -> DomainMemoryKnowledgeProjection:
        """Project authorized canonical knowledge over an authorized Phase 10.18 view."""
        # 1. Structural request / view / memory_request coherence
        if request.memory_view_id != view.view_id:
            raise DomainMemoryKnowledgeProjectionError("memory_view_id mismatch")
        if request.memory_view_digest != view.digest:
            raise DomainMemoryKnowledgeProjectionError("memory_view_digest mismatch")
        if str(request.primary_domain) != str(view.primary_domain):
            raise DomainMemoryKnowledgeProjectionError("primary_domain mismatch")
        if memory_request.request_id != view.request_id:
            raise DomainMemoryKnowledgeProjectionError(
                "memory_request request_id mismatch"
            )
        if str(request.primary_domain) != str(memory_request.primary_domain):
            raise DomainMemoryKnowledgeProjectionError("primary_domain mismatch")
        if tuple(request.supporting_domains) != tuple(
            memory_request.supporting_domains
        ):
            raise DomainMemoryKnowledgeAuthorizationError(
                "supporting domains diverge from Phase 10.18 request"
            )
        if request.temporal_reference != memory_request.temporal_reference:
            raise DomainMemoryKnowledgeAuthorizationError(
                "temporal reference diverges from Phase 10.18 request"
            )

        if resolution is None or composition is None:
            raise DomainMemoryKnowledgeAuthorizationError(
                "resolution and composition authority required"
            )
        # Canonical authority binding: duck-typed or parallel authority objects
        # fail closed even when every attribute superficially matches.
        if type(resolution) is not DomainResolutionResult:
            raise DomainMemoryKnowledgeAuthorizationError(
                "resolution must be a canonical DomainResolutionResult"
            )
        # Final authority requires the canonical RESOLVED status; the exact
        # type alone also legitimately represents unresolved states.
        if resolution.status is not DomainResolutionStatus.RESOLVED:
            raise DomainMemoryKnowledgeAuthorizationError(
                "resolution must be RESOLVED for domain memory knowledge projection"
            )
        if type(composition) is not DomainComposition:
            raise DomainMemoryKnowledgeAuthorizationError(
                "composition must be a canonical DomainComposition"
            )
        if request.resolution_reference_id != resolution.id:
            raise DomainMemoryKnowledgeAuthorizationError(
                "resolution reference mismatch"
            )
        if request.composition_reference_id != composition.id:
            raise DomainMemoryKnowledgeAuthorizationError(
                "composition reference mismatch"
            )
        if composition.resolution_id != resolution.id:
            raise DomainMemoryKnowledgeAuthorizationError(
                "composition resolution mismatch"
            )
        if composition.status not in (
            DomainCompositionStatus.COMPOSED,
            DomainCompositionStatus.PARTIAL,
        ):
            raise DomainMemoryKnowledgeAuthorizationError(
                "composition status must be COMPOSED or PARTIAL"
            )
        if resolution.primary_domain is None or str(resolution.primary_domain) != str(
            request.primary_domain
        ):
            raise DomainMemoryKnowledgeAuthorizationError(
                "resolution primary domain mismatch"
            )
        if str(composition.primary_domain) != str(request.primary_domain):
            raise DomainMemoryKnowledgeAuthorizationError(
                "composition primary domain mismatch"
            )
        request_supporting = frozenset(str(d) for d in request.supporting_domains)
        if frozenset(str(d) for d in resolution.supporting_domains) != (
            request_supporting
        ):
            raise DomainMemoryKnowledgeAuthorizationError(
                "resolution supporting domains diverge from request"
            )
        if frozenset(str(d) for d in composition.supporting_domains) != (
            request_supporting
        ):
            raise DomainMemoryKnowledgeAuthorizationError(
                "composition supporting domains diverge from request"
            )

        # 2. Authority coherence: requested permission decisions must be covered by memory_request
        if set(request.permission_decision_ids) != set(
            memory_request.permission_decision_ids
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
                if not isinstance(rel.kind, KnowledgeRelationKind):
                    continue
                kind_val = rel.kind.value
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

                anchor_str = _canonical_temporal_anchor(r)
                if anchor_str is None:
                    if r.temporal is not None or r.has_unknown_ordering:
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
            request_digest=request.digest,
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
