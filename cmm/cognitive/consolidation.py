"""Phase 8.7 – Knowledge Consolidation Service.

Implements KnowledgeConsolidator for deterministic comparison, candidate discovery,
plan construction, preview, and atomic execution over KnowledgeStoreProtocol.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from cmm.cognitive.consolidation_contracts import (
    ConsolidationAction,
    ConsolidationCandidate,
    ConsolidationDecision,
    ConsolidationMatchKind,
    ConsolidationPlan,
    ConsolidationResult,
    knowledge_fingerprint,
    normalize_statement,
)
from cmm.cognitive.contracts import Confidence, utc_now
from cmm.cognitive.enums import KnowledgeRelationKind, KnowledgeStatus
from cmm.cognitive.errors import (
    InvalidConsolidationCandidateError,
    InvalidConsolidationPlanError,
    KnowledgeConsolidationConflictError,
    ManualReviewRequiredError,
)
from cmm.cognitive.identifiers import generate_cognitive_id
from cmm.cognitive.knowledge import KnowledgeItem, KnowledgeRelation
from cmm.cognitive.query import KnowledgeQuery
from cmm.cognitive.retrieval import KnowledgeRetriever
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol, validate_store_id


def _token_set(text: str) -> set[str]:
    """Tokenize normalized text into simple Unicode token set."""
    norm = normalize_statement(text)
    return set(norm.split())


class KnowledgeConsolidator:
    """Pure, auditable consolidation service operating on KnowledgeStoreProtocol."""

    def __init__(
        self,
        store: KnowledgeStoreProtocol,
        retriever: KnowledgeRetriever | None = None,
    ) -> None:
        if not isinstance(store, KnowledgeStoreProtocol):
            raise TypeError("store must implement KnowledgeStoreProtocol")
        self._store = store
        self._retriever = (
            retriever if retriever is not None else KnowledgeRetriever(store)
        )

    def compare(
        self,
        item_a: KnowledgeItem,
        item_b: KnowledgeItem,
    ) -> ConsolidationCandidate:
        """Compare two KnowledgeItems deterministically and return a ConsolidationCandidate."""
        if not isinstance(item_a, KnowledgeItem) or not isinstance(
            item_b, KnowledgeItem
        ):
            raise InvalidConsolidationCandidateError(
                "compare() requires two valid KnowledgeItem instances"
            )
        if item_a.id == item_b.id:
            raise InvalidConsolidationCandidateError(
                f"Cannot compare KnowledgeItem '{item_a.id}' with itself"
            )

        # 1. Version Successor Lineage Check
        if item_b.supersedes_id == item_a.id or item_a.superseded_by_id == item_b.id:
            predecessor, successor = item_a, item_b
            return ConsolidationCandidate(
                item_a_id=predecessor.id,
                item_b_id=successor.id,
                match_kind=ConsolidationMatchKind.VERSION_SUCCESSOR,
                recommended_decision=ConsolidationDecision.SUPERSEDE,
                confidence=Confidence(value=1.0),
                matching_fields=("supersedes_id", "superseded_by_id"),
                reasons=(
                    f"Item '{successor.id}' explicitly supersedes item '{predecessor.id}'",
                ),
            )

        if item_a.supersedes_id == item_b.id or item_b.superseded_by_id == item_a.id:
            predecessor, successor = item_b, item_a
            return ConsolidationCandidate(
                item_a_id=predecessor.id,
                item_b_id=successor.id,
                match_kind=ConsolidationMatchKind.VERSION_SUCCESSOR,
                recommended_decision=ConsolidationDecision.SUPERSEDE,
                confidence=Confidence(value=1.0),
                matching_fields=("supersedes_id", "superseded_by_id"),
                reasons=(
                    f"Item '{successor.id}' explicitly supersedes item '{predecessor.id}'",
                ),
            )

        # Canonize ID order for symmetric comparisons
        if item_a.id > item_b.id:
            first, second = item_b, item_a
        else:
            first, second = item_a, item_b

        matching_fields: list[str] = []
        differing_fields: list[str] = []

        # Compare individual fields
        if first.kind == second.kind:
            matching_fields.append("kind")
        else:
            differing_fields.append("kind")

        if first.status == second.status:
            matching_fields.append("status")
        else:
            differing_fields.append("status")

        if first.confidence.value == second.confidence.value:
            matching_fields.append("confidence")
        else:
            differing_fields.append("confidence")

        if normalize_statement(first.statement) == normalize_statement(
            second.statement
        ):
            matching_fields.append("statement_normalized")
        else:
            differing_fields.append("statement_normalized")

        if first.resource_id is not None and first.resource_id == second.resource_id:
            matching_fields.append("resource_id")
        elif first.resource_id != second.resource_id:
            differing_fields.append("resource_id")

        if first.actor_id is not None and first.actor_id == second.actor_id:
            matching_fields.append("actor_id")
        elif first.actor_id != second.actor_id:
            differing_fields.append("actor_id")

        if first.sensitivity == second.sensitivity:
            matching_fields.append("sensitivity")
        else:
            differing_fields.append("sensitivity")

        if first.temporal_scope == second.temporal_scope:
            matching_fields.append("temporal_scope")
        else:
            differing_fields.append("temporal_scope")

        # Shared evidence and relation IDs
        ev_a = {e.id for e in first.evidence}
        ev_b = {e.id for e in second.evidence}
        shared_ev = tuple(sorted(ev_a.intersection(ev_b)))

        rel_a = {r.id for r in first.relations}
        rel_b = {r.id for r in second.relations}
        shared_rel = tuple(sorted(rel_a.intersection(rel_b)))

        # 2. Exact Duplicate Check
        is_exact = (
            first.kind == second.kind
            and first.status == second.status
            and first.confidence.value == second.confidence.value
            and first.statement == second.statement
            and first.temporal_scope == second.temporal_scope
            and first.sensitivity == second.sensitivity
            and first.actor_id == second.actor_id
            and first.resource_id == second.resource_id
            and [e.serialize() for e in first.evidence]
            == [e.serialize() for e in second.evidence]
            and [r.serialize() for r in first.relations]
            == [r.serialize() for r in second.relations]
        )

        if is_exact:
            return ConsolidationCandidate(
                item_a_id=first.id,
                item_b_id=second.id,
                match_kind=ConsolidationMatchKind.EXACT_DUPLICATE,
                recommended_decision=ConsolidationDecision.MERGE,
                confidence=Confidence(value=1.0),
                matching_fields=tuple(matching_fields),
                differing_fields=(),
                shared_evidence_ids=shared_ev,
                shared_relation_ids=shared_rel,
                reasons=("Exact duplicate: all semantic fields match identically",),
            )

        # 3. Normalized Duplicate Check
        if "statement_normalized" in matching_fields and "kind" in matching_fields:
            # Check if all other critical fields match for automatic merge proposal
            substantially_identical = (
                first.confidence.value == second.confidence.value
                and first.temporal_scope == second.temporal_scope
                and first.sensitivity == second.sensitivity
            )
            rec_decision = (
                ConsolidationDecision.MANUAL_REVIEW
                if not substantially_identical
                else ConsolidationDecision.MERGE
            )
            return ConsolidationCandidate(
                item_a_id=first.id,
                item_b_id=second.id,
                match_kind=ConsolidationMatchKind.NORMALIZED_DUPLICATE,
                recommended_decision=rec_decision,
                confidence=Confidence(value=0.9),
                matching_fields=tuple(matching_fields),
                differing_fields=tuple(differing_fields),
                shared_evidence_ids=shared_ev,
                shared_relation_ids=shared_rel,
                reasons=(
                    "Normalized duplicate: normalized statements and kinds match",
                ),
            )

        # 4. Structural Overlap Check
        tokens_a = _token_set(first.statement)
        tokens_b = _token_set(second.statement)
        jaccard = (
            len(tokens_a.intersection(tokens_b)) / len(tokens_a.union(tokens_b))
            if tokens_a or tokens_b
            else 0.0
        )

        has_overlap = (
            ("resource_id" in matching_fields and first.resource_id is not None)
            or len(shared_ev) > 0
            or len(shared_rel) > 0
            or jaccard >= 0.6
        )

        if has_overlap:
            reasons_list: list[str] = []
            if "resource_id" in matching_fields and first.resource_id is not None:
                reasons_list.append(f"Shared resource_id '{first.resource_id}'")
            if shared_ev:
                reasons_list.append(f"Shared evidence IDs: {shared_ev}")
            if shared_rel:
                reasons_list.append(f"Shared relation IDs: {shared_rel}")
            if jaccard >= 0.6:
                reasons_list.append(f"Text token overlap Jaccard index {jaccard:.2f}")

            return ConsolidationCandidate(
                item_a_id=first.id,
                item_b_id=second.id,
                match_kind=ConsolidationMatchKind.STRUCTURAL_OVERLAP,
                recommended_decision=ConsolidationDecision.MANUAL_REVIEW,
                confidence=Confidence(value=0.7),
                matching_fields=tuple(matching_fields),
                differing_fields=tuple(differing_fields),
                shared_evidence_ids=shared_ev,
                shared_relation_ids=shared_rel,
                reasons=tuple(reasons_list),
            )

        # 5. Related Check
        # Check if there is an explicit relation in store or item between first and second
        explicit_rel = any(
            r.source_id == first.id
            and r.target_id == second.id
            or r.source_id == second.id
            and r.target_id == first.id
            for r in (*first.relations, *second.relations)
        )
        if explicit_rel or (
            "actor_id" in matching_fields and first.actor_id is not None
        ):
            reasons_rel: list[str] = []
            if explicit_rel:
                reasons_rel.append("Explicit relation connects items")
            if "actor_id" in matching_fields:
                reasons_rel.append(f"Shared actor_id '{first.actor_id}'")
            return ConsolidationCandidate(
                item_a_id=first.id,
                item_b_id=second.id,
                match_kind=ConsolidationMatchKind.RELATED,
                recommended_decision=ConsolidationDecision.LINK,
                confidence=Confidence(value=0.5),
                matching_fields=tuple(matching_fields),
                differing_fields=tuple(differing_fields),
                shared_evidence_ids=shared_ev,
                shared_relation_ids=shared_rel,
                reasons=tuple(reasons_rel),
            )

        # 6. Distinct
        return ConsolidationCandidate(
            item_a_id=first.id,
            item_b_id=second.id,
            match_kind=ConsolidationMatchKind.DISTINCT,
            recommended_decision=ConsolidationDecision.KEEP_SEPARATE,
            confidence=Confidence(value=0.0),
            matching_fields=tuple(matching_fields),
            differing_fields=tuple(differing_fields),
            shared_evidence_ids=shared_ev,
            shared_relation_ids=shared_rel,
            reasons=("Items are distinct",),
        )

    def find_candidates(
        self,
        query: KnowledgeQuery | None = None,
    ) -> tuple[ConsolidationCandidate, ...]:
        """Find candidate pairs for consolidation deterministically without mutating the store."""
        if query is not None:
            res = self._retriever.query(query)
            items = res.items
        else:
            items = self._store.list_items()

        if len(items) < 2:
            return ()

        # Deterministic sorting of items by ID
        sorted_items = sorted(items, key=lambda it: it.id)
        candidates_map: dict[str, ConsolidationCandidate] = {}

        for i in range(len(sorted_items)):
            for j in range(i + 1, len(sorted_items)):
                item_a = sorted_items[i]
                item_b = sorted_items[j]
                candidate = self.compare(item_a, item_b)
                if candidate.match_kind is not ConsolidationMatchKind.DISTINCT:
                    key = f"{candidate.item_a_id}:{candidate.item_b_id}"
                    candidates_map[key] = candidate

        # Sort candidates deterministically
        sorted_candidates = sorted(
            candidates_map.values(),
            key=lambda c: (c.item_a_id, c.item_b_id, c.match_kind.value),
        )
        return tuple(sorted_candidates)

    def build_plan(
        self,
        candidates: Iterable[ConsolidationCandidate],
        *,
        actor_id: str,
        dry_run: bool = True,
    ) -> ConsolidationPlan:
        """Construct an explicit ConsolidationPlan from candidates."""
        validate_store_id(actor_id, "actor_id")

        candidates_list = list(candidates)
        if not candidates_list:
            raise InvalidConsolidationPlanError(
                "Cannot build ConsolidationPlan with zero candidates"
            )

        actions: list[ConsolidationAction] = []
        candidate_refs: list[str] = []
        expected_fps: dict[str, str] = {}

        for cand in candidates_list:
            if not isinstance(cand, ConsolidationCandidate):
                raise InvalidConsolidationPlanError(
                    f"Expected ConsolidationCandidate, got {type(cand).__name__}"
                )

            cand_ref = f"{cand.item_a_id}:{cand.item_b_id}"
            candidate_refs.append(cand_ref)

            # Record expected fingerprints for concurrency verification
            for item_id in (cand.item_a_id, cand.item_b_id):
                if item_id not in expected_fps and self._store.contains_item(item_id):
                    it = self._store.get_item(item_id)
                    expected_fps[item_id] = knowledge_fingerprint(it)

            decision = cand.recommended_decision
            if decision == ConsolidationDecision.MERGE:
                act = ConsolidationAction(
                    decision=ConsolidationDecision.MERGE,
                    source_item_ids=(cand.item_a_id, cand.item_b_id),
                    target_item_id=cand.item_a_id,
                    preserve_sources=True,
                    result_status=KnowledgeStatus.ACTIVE,
                    actor_id=actor_id,
                    reason="; ".join(cand.reasons),
                )
            elif decision == ConsolidationDecision.SUPERSEDE:
                act = ConsolidationAction(
                    decision=ConsolidationDecision.SUPERSEDE,
                    source_item_ids=(cand.item_a_id,),
                    target_item_id=cand.item_b_id,
                    preserve_sources=True,
                    result_status=KnowledgeStatus.SUPERSEDED,
                    actor_id=actor_id,
                    reason="; ".join(cand.reasons),
                )
            elif decision == ConsolidationDecision.LINK:
                act = ConsolidationAction(
                    decision=ConsolidationDecision.LINK,
                    source_item_ids=(cand.item_a_id, cand.item_b_id),
                    target_item_id=cand.item_a_id,
                    relation_kind=KnowledgeRelationKind.EQUIVALENT_TO,
                    actor_id=actor_id,
                    reason="; ".join(cand.reasons),
                )
            elif decision == ConsolidationDecision.MANUAL_REVIEW:
                act = ConsolidationAction(
                    decision=ConsolidationDecision.MANUAL_REVIEW,
                    source_item_ids=(cand.item_a_id, cand.item_b_id),
                    actor_id=actor_id,
                    reason="; ".join(cand.reasons),
                )
            elif decision in (
                ConsolidationDecision.KEEP_SEPARATE,
                ConsolidationDecision.SKIP,
            ):
                act = ConsolidationAction(
                    decision=decision,
                    source_item_ids=(cand.item_a_id, cand.item_b_id),
                    actor_id=actor_id,
                    reason="; ".join(cand.reasons),
                )
            else:
                raise InvalidConsolidationPlanError(f"Unsupported decision: {decision}")

            actions.append(act)

        return ConsolidationPlan(
            actions=tuple(actions),
            candidate_ids=tuple(candidate_refs),
            actor_id=actor_id,
            dry_run=dry_run,
            expected_fingerprints=expected_fps,
        )

    def preview_plan(self, plan: ConsolidationPlan) -> ConsolidationResult:
        """Simulate plan execution and return predicted ConsolidationResult without mutating store."""
        if not isinstance(plan, ConsolidationPlan):
            raise TypeError("plan must be ConsolidationPlan")

        started_at = utc_now()
        created: list[str] = []
        updated: list[str] = []
        superseded: list[str] = []
        linked: list[str] = []
        unchanged: list[str] = []
        warnings: list[str] = list(plan.warnings)

        for act in plan.actions:
            if act.decision == ConsolidationDecision.MERGE:
                if act.target_item_id:
                    updated.append(act.target_item_id)
                for sid in act.source_item_ids:
                    if sid != act.target_item_id:
                        superseded.append(sid)
            elif act.decision == ConsolidationDecision.SUPERSEDE:
                superseded.extend(act.source_item_ids)
                if act.target_item_id:
                    updated.append(act.target_item_id)
            elif act.decision == ConsolidationDecision.LINK:
                dummy_rel_id = generate_cognitive_id("preview-rel", "relation")
                linked.append(dummy_rel_id)
            elif act.decision in (
                ConsolidationDecision.KEEP_SEPARATE,
                ConsolidationDecision.SKIP,
                ConsolidationDecision.MANUAL_REVIEW,
            ):
                unchanged.extend(act.source_item_ids)

        return ConsolidationResult(
            plan_id=plan.id,
            applied=False,
            created_item_ids=tuple(dict.fromkeys(created)),
            updated_item_ids=tuple(dict.fromkeys(updated)),
            superseded_item_ids=tuple(dict.fromkeys(superseded)),
            linked_relation_ids=tuple(dict.fromkeys(linked)),
            unchanged_item_ids=tuple(dict.fromkeys(unchanged)),
            warnings=tuple(warnings),
            started_at=started_at,
            finished_at=utc_now(),
        )

    def apply_plan(self, plan: ConsolidationPlan) -> ConsolidationResult:
        """Apply a ConsolidationPlan atomically to the store."""
        if not isinstance(plan, ConsolidationPlan):
            raise TypeError("plan must be ConsolidationPlan")

        if plan.dry_run:
            return self.preview_plan(plan)

        # 1. Pre-condition validations
        for act in plan.actions:
            if act.decision == ConsolidationDecision.MANUAL_REVIEW:
                raise ManualReviewRequiredError(
                    f"ConsolidationPlan '{plan.id}' contains actions requiring manual review"
                )

        started_at = utc_now()

        # Validate existence and fingerprints of expected items
        for item_id, expected_fp in plan.expected_fingerprints.items():
            if not self._store.contains_item(item_id):
                raise KnowledgeConsolidationConflictError(
                    f"Item '{item_id}' referenced in plan no longer exists in store"
                )
            current_item = self._store.get_item(item_id)
            current_fp = knowledge_fingerprint(current_item)
            if current_fp != expected_fp:
                raise KnowledgeConsolidationConflictError(
                    f"Stale fingerprint for item '{item_id}': expected {expected_fp}, got {current_fp}"
                )

        created_ids: list[str] = []
        updated_ids: list[str] = []
        superseded_ids: list[str] = []
        linked_rel_ids: list[str] = []
        unchanged_ids: list[str] = []
        warnings_list: list[str] = list(plan.warnings)

        # 2. Atomic execution
        with self._store.transaction():
            for act in plan.actions:
                if act.decision == ConsolidationDecision.MERGE:
                    target_id = act.target_item_id
                    if target_id is None or not self._store.contains_item(target_id):
                        raise KnowledgeConsolidationConflictError(
                            f"Target item '{target_id}' for merge action not found in store"
                        )
                    target_item = self._store.get_item(target_id)
                    source_items: list[KnowledgeItem] = []

                    for sid in act.source_item_ids:
                        if sid == target_id:
                            continue
                        if not self._store.contains_item(sid):
                            raise KnowledgeConsolidationConflictError(
                                f"Source item '{sid}' for merge action not found in store"
                            )
                        source_items.append(self._store.get_item(sid))

                    # Combine evidence
                    ev_map = {e.id: e for e in target_item.evidence}
                    for s_item in source_items:
                        for e in s_item.evidence:
                            if e.id not in ev_map:
                                ev_map[e.id] = e
                    merged_ev = tuple(ev_map.values())

                    # Combine relations
                    rel_map = {r.id: r for r in target_item.relations}
                    for s_item in source_items:
                        for r in s_item.relations:
                            if r.id not in rel_map:
                                rel_map[r.id] = r
                    merged_rel = tuple(rel_map.values())

                    # Combine metadata
                    merged_meta = dict(target_item.metadata)
                    merged_meta["consolidated_sources"] = list(act.source_item_ids)
                    merged_meta["consolidation_plan_id"] = plan.id

                    # Conservative confidence calculation
                    all_conf_vals = [target_item.confidence.value] + [
                        s.confidence.value for s in source_items
                    ]
                    merged_conf_val = min(all_conf_vals)
                    merged_conf = Confidence(
                        value=merged_conf_val,
                        source=f"consolidation:{plan.id}",
                        reasons=(
                            f"Merged {len(source_items) + 1} items via plan {plan.id}",
                        ),
                    )

                    # Update target item
                    updated_target = replace(
                        target_item,
                        evidence=merged_ev,
                        relations=merged_rel,
                        confidence=merged_conf,
                        updated_at=started_at,
                        metadata=merged_meta,
                    )
                    self._store.save_item(updated_target)
                    updated_ids.append(target_id)

                    # Update sources to SUPERSEDE status
                    if act.preserve_sources:
                        for s_item in source_items:
                            superseded_source = replace(
                                s_item,
                                status=KnowledgeStatus.SUPERSEDED,
                                superseded_by_id=target_id,
                                updated_at=started_at,
                            )
                            self._store.save_item(superseded_source)
                            superseded_ids.append(s_item.id)

                elif act.decision == ConsolidationDecision.SUPERSEDE:
                    for pred_id in act.source_item_ids:
                        if not self._store.contains_item(pred_id):
                            raise KnowledgeConsolidationConflictError(
                                f"Predecessor item '{pred_id}' for supersede action not found"
                            )
                        if act.target_item_id is None or not self._store.contains_item(
                            act.target_item_id
                        ):
                            raise KnowledgeConsolidationConflictError(
                                f"Successor item '{act.target_item_id}' for supersede action not found"
                            )

                        predecessor = self._store.get_item(pred_id)
                        successor = self._store.get_item(act.target_item_id)

                        # Prevent self-supersession or circular supersession
                        if predecessor.id == successor.id:
                            raise InvalidConsolidationPlanError(
                                f"Item '{predecessor.id}' cannot supersede itself"
                            )
                        if predecessor.supersedes_id == successor.id:
                            raise InvalidConsolidationPlanError(
                                f"Circular supersession detected between '{predecessor.id}' and '{successor.id}'"
                            )

                        # Mark predecessor as SUPERSEDE
                        updated_pred = replace(
                            predecessor,
                            status=KnowledgeStatus.SUPERSEDED,
                            superseded_by_id=successor.id,
                            updated_at=started_at,
                        )
                        self._store.save_item(updated_pred)
                        superseded_ids.append(pred_id)

                        # Link successor to predecessor if not already linked
                        if successor.supersedes_id != pred_id:
                            updated_succ = replace(
                                successor,
                                supersedes_id=pred_id,
                                updated_at=started_at,
                            )
                            self._store.save_item(updated_succ)
                            updated_ids.append(successor.id)

                elif act.decision == ConsolidationDecision.LINK:
                    if len(act.source_item_ids) < 2:
                        raise InvalidConsolidationPlanError(
                            "LINK action requires at least two source_item_ids"
                        )
                    src_id = act.source_item_ids[0]
                    tgt_id = act.source_item_ids[1]

                    rel_kind = (
                        act.relation_kind
                        if act.relation_kind is not None
                        else KnowledgeRelationKind.EQUIVALENT_TO
                    )
                    rel_id = generate_cognitive_id("rel", "consolidation")

                    relation = KnowledgeRelation(
                        id=rel_id,
                        source_id=src_id,
                        target_id=tgt_id,
                        kind=rel_kind,
                        confidence=Confidence(value=1.0),
                        actor_id=plan.actor_id,
                        created_at=started_at,
                        metadata={"consolidation_plan_id": plan.id},
                    )
                    self._store.save_relation(relation)
                    linked_rel_ids.append(relation.id)

                elif act.decision in (
                    ConsolidationDecision.KEEP_SEPARATE,
                    ConsolidationDecision.SKIP,
                ):
                    unchanged_ids.extend(act.source_item_ids)

        return ConsolidationResult(
            plan_id=plan.id,
            applied=True,
            created_item_ids=tuple(dict.fromkeys(created_ids)),
            updated_item_ids=tuple(dict.fromkeys(updated_ids)),
            superseded_item_ids=tuple(dict.fromkeys(superseded_ids)),
            linked_relation_ids=tuple(dict.fromkeys(linked_rel_ids)),
            unchanged_item_ids=tuple(dict.fromkeys(unchanged_ids)),
            warnings=tuple(warnings_list),
            started_at=started_at,
            finished_at=utc_now(),
        )
