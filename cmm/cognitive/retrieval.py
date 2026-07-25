"""Phase 8.6 – Knowledge Retrieval Service.

Implements structured, deterministic, read-only retrieval capabilities over any
implementation of KnowledgeStoreProtocol.
"""

from __future__ import annotations

import functools
from collections.abc import Iterable
from typing import Any

from cmm.cognitive.enums import (
    ContradictionSeverity,
    ContradictionStatus,
    KnowledgeRelationKind,
    KnowledgeStatus,
    TemporalValidityStatus,
)
from cmm.cognitive.errors import (
    InvalidKnowledgeQueryError,
    KnowledgeRetrievalError,
    KnowledgeStoreNotFoundError,
)
from cmm.cognitive.knowledge import (
    Contradiction,
    KnowledgeBundle,
    KnowledgeItem,
    KnowledgeRelation,
)
from cmm.cognitive.query import (
    KnowledgeOrderField,
    KnowledgeQuery,
    KnowledgeQueryResult,
    SortDirection,
)
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol, validate_store_id


class KnowledgeRetriever:
    """Read-only retrieval layer over KnowledgeStoreProtocol."""

    def __init__(self, store: KnowledgeStoreProtocol) -> None:
        if not isinstance(store, KnowledgeStoreProtocol):
            raise KnowledgeRetrievalError(
                f"Expected KnowledgeStoreProtocol, got {type(store).__name__}"
            )
        self._store = store

    def query(self, query: KnowledgeQuery) -> KnowledgeQueryResult:
        """Query KnowledgeItems from the store using structured filters, order, and pagination."""
        if not isinstance(query, KnowledgeQuery):
            raise InvalidKnowledgeQueryError("query must be a KnowledgeQuery instance")

        # Native store filtering hint when single-valued
        k_hint = query.kinds[0] if len(query.kinds) == 1 else None
        s_hint = query.statuses[0] if len(query.statuses) == 1 else None
        r_hint = query.resource_ids[0] if len(query.resource_ids) == 1 else None
        a_hint = query.actor_ids[0] if len(query.actor_ids) == 1 else None
        sens_hint = query.sensitivities[0] if len(query.sensitivities) == 1 else None

        candidates = self._store.list_items(
            kind=k_hint,
            status=s_hint,
            resource_id=r_hint,
            actor_id=a_hint,
            sensitivity=sens_hint,
            limit=None,
            offset=0,
        )

        applied_filters: list[str] = []
        filtered: list[KnowledgeItem] = list(candidates)

        if query.kinds:
            applied_filters.append("kinds")
            filtered = [item for item in filtered if item.kind in query.kinds]

        if query.statuses:
            applied_filters.append("statuses")
            filtered = [item for item in filtered if item.status in query.statuses]

        if query.resource_ids:
            applied_filters.append("resource_ids")
            filtered = [
                item for item in filtered if item.resource_id in query.resource_ids
            ]

        if query.actor_ids:
            applied_filters.append("actor_ids")
            filtered = [item for item in filtered if item.actor_id in query.actor_ids]

        if query.sensitivities:
            applied_filters.append("sensitivities")
            filtered = [
                item for item in filtered if item.sensitivity in query.sensitivities
            ]

        if query.created_from is not None:
            applied_filters.append("created_from")
            filtered = [
                item for item in filtered if item.created_at >= query.created_from
            ]

        if query.created_until is not None:
            applied_filters.append("created_until")
            filtered = [
                item for item in filtered if item.created_at <= query.created_until
            ]

        if query.updated_from is not None:
            applied_filters.append("updated_from")
            filtered = [
                item for item in filtered if item.updated_at >= query.updated_from
            ]

        if query.updated_until is not None:
            applied_filters.append("updated_until")
            filtered = [
                item for item in filtered if item.updated_at <= query.updated_until
            ]

        if not query.include_expired:
            applied_filters.append("include_expired")
            filtered = [
                item
                for item in filtered
                if item.temporal_scope.validity_status != TemporalValidityStatus.EXPIRED
            ]

        if not query.include_superseded:
            applied_filters.append("include_superseded")
            filtered = [
                item for item in filtered if item.status != KnowledgeStatus.SUPERSEDED
            ]

        if not query.include_invalidated:
            applied_filters.append("include_invalidated")
            filtered = [
                item for item in filtered if item.status != KnowledgeStatus.INVALIDATED
            ]

        if query.valid_at is not None:
            applied_filters.append("valid_at")
            filtered = [
                item
                for item in filtered
                if item.temporal_scope.is_valid_at(query.valid_at)
            ]

        if query.has_evidence is not None:
            applied_filters.append("has_evidence")
            if query.has_evidence:
                filtered = [item for item in filtered if len(item.evidence) > 0]
            else:
                filtered = [item for item in filtered if len(item.evidence) == 0]

        if query.has_relations is not None or query.relation_kinds:
            # Helper cache for relations per item ID
            rel_cache: dict[str, tuple[KnowledgeRelation, ...]] = {}

            def _get_item_rels(item: KnowledgeItem) -> tuple[KnowledgeRelation, ...]:
                if item.id not in rel_cache:
                    rel_cache[item.id] = self._collect_item_relations(item)
                return rel_cache[item.id]

            if query.has_relations is not None:
                applied_filters.append("has_relations")
                if query.has_relations:
                    filtered = [
                        item for item in filtered if len(_get_item_rels(item)) > 0
                    ]
                else:
                    filtered = [
                        item for item in filtered if len(_get_item_rels(item)) == 0
                    ]

            if query.relation_kinds:
                applied_filters.append("relation_kinds")
                filtered = [
                    item
                    for item in filtered
                    if any(r.kind in query.relation_kinds for r in _get_item_rels(item))
                ]

        if query.text_contains is not None:
            applied_filters.append("text_contains")
            needle = query.text_contains.casefold()
            filtered = [
                item for item in filtered if needle in item.statement.casefold()
            ]

        applied_filters.append("order_by")
        applied_filters.append("order_direction")

        # Deterministic sorting with ID tie-breaker
        def _get_sort_val(item: KnowledgeItem, field_name: KnowledgeOrderField) -> Any:
            if field_name is KnowledgeOrderField.CREATED_AT:
                return item.created_at
            if field_name is KnowledgeOrderField.UPDATED_AT:
                return item.updated_at
            if field_name is KnowledgeOrderField.CONFIDENCE:
                return item.confidence.value
            if field_name is KnowledgeOrderField.KIND:
                return item.kind.value
            if field_name is KnowledgeOrderField.STATUS:
                return item.status.value
            if field_name is KnowledgeOrderField.ID:
                return item.id
            return item.created_at

        def _compare_items(a: KnowledgeItem, b: KnowledgeItem) -> int:
            val_a = _get_sort_val(a, query.order_by)
            val_b = _get_sort_val(b, query.order_by)
            if val_a != val_b:
                if val_a < val_b:
                    return -1 if query.order_direction is SortDirection.ASC else 1
                else:
                    return 1 if query.order_direction is SortDirection.ASC else -1

            if query.order_by is KnowledgeOrderField.ID:
                return 0
            # Tie-breaker on ID is always ASC
            if a.id < b.id:
                return -1
            elif a.id > b.id:
                return 1
            return 0

        filtered.sort(key=functools.cmp_to_key(_compare_items))

        total_count = len(filtered)
        offset = query.offset
        if offset > 0:
            applied_filters.append("offset")

        if query.limit is not None:
            applied_filters.append("limit")
            paged = filtered[offset : offset + query.limit]
        else:
            paged = filtered[offset:]

        returned_count = len(paged)
        has_more = (offset + returned_count) < total_count

        return KnowledgeQueryResult(
            query=query,
            items=tuple(paged),
            total_count=total_count,
            returned_count=returned_count,
            offset=offset,
            limit=query.limit,
            has_more=has_more,
            applied_filters=tuple(dict.fromkeys(applied_filters)),
            warnings=(),
        )

    def relations_for_item(
        self,
        item_id: str,
        *,
        kinds: tuple[KnowledgeRelationKind, ...] = (),
    ) -> tuple[KnowledgeRelation, ...]:
        """Retrieve all KnowledgeRelations where item_id is source or target."""
        validate_store_id(item_id, "item_id")

        kinds_norm: list[KnowledgeRelationKind] = []
        for k in kinds or ():
            if isinstance(k, KnowledgeRelationKind):
                kinds_norm.append(k)
            elif isinstance(k, str):
                try:
                    kinds_norm.append(KnowledgeRelationKind(k))
                except ValueError as exc:
                    raise InvalidKnowledgeQueryError(
                        f"Invalid KnowledgeRelationKind: {k}"
                    ) from exc

        # Create virtual item if store contains it, or pass dummy to collector
        if self._store.contains_item(item_id):
            item = self._store.get_item(item_id)
            all_rels = self._collect_item_relations(item)
        else:
            by_src = self._store.list_relations(source_id=item_id)
            by_tgt = self._store.list_relations(target_id=item_id)
            rels_map: dict[str, KnowledgeRelation] = {}
            for r in (*by_src, *by_tgt):
                rels_map[r.id] = r
            all_rels = tuple(rels_map.values())

        if kinds_norm:
            all_rels = tuple(r for r in all_rels if r.kind in kinds_norm)

        # Deterministic order: created_at ASC, id ASC
        return tuple(sorted(all_rels, key=lambda r: (r.created_at, r.id)))

    def contradictions_for_item(
        self,
        item_id: str,
        *,
        statuses: tuple[ContradictionStatus, ...] = (),
        severities: tuple[ContradictionSeverity, ...] = (),
    ) -> tuple[Contradiction, ...]:
        """Retrieve all Contradictions involving item_id as item_a or item_b."""
        validate_store_id(item_id, "item_id")

        statuses_norm: list[ContradictionStatus] = []
        for s in statuses or ():
            if isinstance(s, ContradictionStatus):
                statuses_norm.append(s)
            elif isinstance(s, str):
                try:
                    statuses_norm.append(ContradictionStatus(s))
                except ValueError as exc:
                    raise InvalidKnowledgeQueryError(
                        f"Invalid ContradictionStatus: {s}"
                    ) from exc

        severities_norm: list[ContradictionSeverity] = []
        for sev in severities or ():
            if isinstance(sev, ContradictionSeverity):
                severities_norm.append(sev)
            elif isinstance(sev, str):
                try:
                    severities_norm.append(ContradictionSeverity(sev))
                except ValueError as exc:
                    raise InvalidKnowledgeQueryError(
                        f"Invalid ContradictionSeverity: {sev}"
                    ) from exc

        raw_contradictions = self._store.list_contradictions(item_id=item_id)
        dedup_map: dict[str, Contradiction] = {c.id: c for c in raw_contradictions}
        contradictions = list(dedup_map.values())

        if statuses_norm:
            contradictions = [c for c in contradictions if c.status in statuses_norm]
        if severities_norm:
            contradictions = [
                c for c in contradictions if c.severity in severities_norm
            ]

        # Deterministic sort: created_at ASC, id ASC
        contradictions.sort(key=lambda c: (c.created_at, c.id))
        return tuple(contradictions)

    def bundles_for_item(
        self,
        item_id: str,
    ) -> tuple[KnowledgeBundle, ...]:
        """Retrieve all KnowledgeBundles containing item_id."""
        validate_store_id(item_id, "item_id")

        all_bundles = self._store.list_bundles()
        matching = [
            b for b in all_bundles if any(item.id == item_id for item in b.items)
        ]
        dedup_map: dict[str, KnowledgeBundle] = {b.id: b for b in matching}
        result = list(dedup_map.values())

        # Deterministic sort: created_at ASC, id ASC
        result.sort(key=lambda b: (b.created_at, b.id))
        return tuple(result)

    def get_items(
        self,
        item_ids: Iterable[str],
        *,
        ignore_missing: bool = False,
    ) -> tuple[KnowledgeItem, ...]:
        """Batch retrieve KnowledgeItems by ID, preserving first-occurrence input order."""
        if not isinstance(item_ids, Iterable) or isinstance(item_ids, (str, bytes)):
            raise InvalidKnowledgeQueryError("item_ids must be an iterable of strings")

        seen: set[str] = set()
        ordered_ids: list[str] = []
        for raw_id in item_ids:
            validated = validate_store_id(raw_id, "item_id")
            if validated not in seen:
                seen.add(validated)
                ordered_ids.append(validated)

        items: list[KnowledgeItem] = []
        for i_id in ordered_ids:
            if self._store.contains_item(i_id):
                items.append(self._store.get_item(i_id))
            elif not ignore_missing:
                raise KnowledgeStoreNotFoundError(
                    f"KnowledgeItem '{i_id}' not found in store"
                )

        return tuple(items)

    def _collect_item_relations(
        self, item: KnowledgeItem
    ) -> tuple[KnowledgeRelation, ...]:
        """Collect all relations embedded in item and stored in store for item."""
        rels_map: dict[str, KnowledgeRelation] = {r.id: r for r in item.relations}
        from_store_src = self._store.list_relations(source_id=item.id)
        from_store_tgt = self._store.list_relations(target_id=item.id)
        for r in (*from_store_src, *from_store_tgt):
            rels_map[r.id] = r
        return tuple(rels_map.values())
