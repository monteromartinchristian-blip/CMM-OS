"""Phase 8.10 – Knowledge Contradiction Resolution Engine.

Implements a deterministic, auditable, rule-based engine that generates
resolution proposals (ContradictionResolutionProposal) for detected contradictions.

Crucial Architectural Guarantees:
- Propose, do not decide: Generates options with rationale and confidence.
- Non-mutating: Does NOT modify KnowledgeItems, delete records, or alter store state.
- Pure determinism: Same input yields identical proposals, ordering, and IDs.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from cmm.cognitive.contracts import utc_now
from cmm.cognitive.contradiction_detection_contracts import (
    ContradictionDetection,
    ContradictionKind,
)
from cmm.cognitive.enums import (
    ContradictionSeverity,
    KnowledgeStatus,
    TemporalValidityStatus,
)
from cmm.cognitive.errors import (
    InvalidResolutionProposalError,
    KnowledgeStoreNotFoundError,
    ResolutionConflictError,
)
from cmm.cognitive.knowledge import (
    Contradiction,
    KnowledgeItem,
)
from cmm.cognitive.resolution_contracts import (
    ContradictionResolutionProposal,
    ResolutionDecision,
    ResolutionStatus,
)
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol


def generate_resolution_proposal_id(
    contradiction_id: str,
    decision: ResolutionDecision | str,
    item_a_id: str,
    item_b_id: str,
) -> str:
    """Generate a deterministic cognitive identifier for a resolution proposal."""
    if not isinstance(contradiction_id, str) or not contradiction_id.strip():
        raise InvalidResolutionProposalError(
            "contradiction_id must be a non-empty string"
        )
    if not isinstance(item_a_id, str) or not item_a_id.strip():
        raise InvalidResolutionProposalError("item_a_id must be a non-empty string")
    if not isinstance(item_b_id, str) or not item_b_id.strip():
        raise InvalidResolutionProposalError("item_b_id must be a non-empty string")

    dec_val = (
        decision.value if isinstance(decision, ResolutionDecision) else str(decision)
    )
    if not dec_val.strip():
        raise InvalidResolutionProposalError("decision must be a valid non-empty value")

    sorted_items = f"{min(item_a_id.strip(), item_b_id.strip())}:{max(item_a_id.strip(), item_b_id.strip())}"
    seed = f"{contradiction_id.strip()}:{sorted_items}:{dec_val.strip()}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"resolution-proposal:cognitive:{digest}"


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise InvalidResolutionProposalError(
            f"{field_name} must be timezone-aware when provided"
        )


class KnowledgeContradictionResolver:
    """Deterministic engine for evaluating contradictions and proposing resolutions."""

    def __init__(self, store: KnowledgeStoreProtocol | None = None) -> None:
        self._store = store

    @property
    def store(self) -> KnowledgeStoreProtocol | None:
        """The optional backing store attached to this resolver."""
        return self._store

    def propose_resolutions(
        self,
        contradiction: Contradiction | ContradictionDetection | None,
        item_a: KnowledgeItem,
        item_b: KnowledgeItem,
        *,
        actor_id: str | None = None,
        created_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[ContradictionResolutionProposal, ...]:
        """Generate structured resolution proposals for a pair of conflicting items."""
        if not isinstance(item_a, KnowledgeItem):
            raise InvalidResolutionProposalError("item_a must be a valid KnowledgeItem")
        if not isinstance(item_b, KnowledgeItem):
            raise InvalidResolutionProposalError("item_b must be a valid KnowledgeItem")
        if item_a.id == item_b.id:
            raise InvalidResolutionProposalError(
                "item_a and item_b must be distinct items"
            )

        if created_at is not None:
            _require_aware(created_at, "created_at")
        ts = created_at or utc_now()

        contradiction_id: str
        severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
        cntr_kind: ContradictionKind | None = None
        preferred_id: str | None = None
        preference_reason: str | None = None

        if contradiction is not None:
            if isinstance(contradiction, Contradiction):
                pair_set = {item_a.id, item_b.id}
                if {contradiction.item_a_id, contradiction.item_b_id} != pair_set:
                    raise ResolutionConflictError(
                        f"Contradiction item IDs ({contradiction.item_a_id}, {contradiction.item_b_id}) "
                        f"do not match provided KnowledgeItems ({item_a.id}, {item_b.id})"
                    )
                contradiction_id = contradiction.id
                severity = contradiction.severity
                preferred_id = contradiction.preferred_id
                preference_reason = contradiction.preference_reason
            elif isinstance(contradiction, ContradictionDetection):
                pair_set = {item_a.id, item_b.id}
                if {contradiction.item_a_id, contradiction.item_b_id} != pair_set:
                    raise ResolutionConflictError(
                        f"ContradictionDetection item IDs ({contradiction.item_a_id}, {contradiction.item_b_id}) "
                        f"do not match provided KnowledgeItems ({item_a.id}, {item_b.id})"
                    )
                contradiction_id = (
                    contradiction.existing_contradiction_id
                    or f"cntr-{min(item_a.id, item_b.id)}-{max(item_a.id, item_b.id)}"
                )
                severity = contradiction.severity
                cntr_kind = contradiction.kind
            else:
                raise InvalidResolutionProposalError(
                    f"Unsupported contradiction type: {type(contradiction)}"
                )
        else:
            contradiction_id = (
                f"cntr-{min(item_a.id, item_b.id)}-{max(item_a.id, item_b.id)}"
            )

        # Collect evidence IDs
        ev_ids_set: set[str] = set()
        for ev in item_a.evidence:
            ev_ids_set.add(ev.id)
        for ev in item_b.evidence:
            ev_ids_set.add(ev.id)
        if isinstance(contradiction, Contradiction):
            for ev in contradiction.supporting_evidence:
                ev_ids_set.add(ev.id)
        elif isinstance(contradiction, ContradictionDetection):
            for sig in contradiction.signals:
                ev_ids_set.update(sig.evidence_ids)
            ev_ids_set.update(contradiction.shared_evidence_ids)

        evidence_ids = tuple(sorted(ev_ids_set))

        # Evaluate Candidate Proposals
        candidates: list[ContradictionResolutionProposal] = []

        # 1. REQUEST_HUMAN_REVIEW (Always a candidate for resolution governance)
        human_rationale: list[str] = []
        if contradiction is not None:
            if isinstance(contradiction, Contradiction):
                human_rationale.append(
                    f"Contradiction between items requires human or policy approval (severity: {severity.value})."
                )
            else:
                human_rationale.append(
                    f"Detected contradiction ({cntr_kind.value if cntr_kind else 'general'}, "
                    f"severity: {severity.value}) requires human or policy review."
                )
        else:
            human_rationale.append(
                "Conflicting statements between KnowledgeItems require human or policy approval before application."
            )

        if severity in (ContradictionSeverity.HIGH, ContradictionSeverity.CRITICAL):
            human_conf = 0.95
        elif severity == ContradictionSeverity.MEDIUM:
            human_conf = 0.85
        else:
            human_conf = 0.75

        prop_human_id = generate_resolution_proposal_id(
            contradiction_id,
            ResolutionDecision.REQUEST_HUMAN_REVIEW,
            item_a.id,
            item_b.id,
        )
        candidates.append(
            ContradictionResolutionProposal(
                id=prop_human_id,
                contradiction_id=contradiction_id,
                item_a_id=item_a.id,
                item_b_id=item_b.id,
                decision=ResolutionDecision.REQUEST_HUMAN_REVIEW,
                status=ResolutionStatus.PROPOSED,
                confidence=human_conf,
                rationale=tuple(human_rationale),
                evidence_ids=evidence_ids,
                actor_id=actor_id,
                created_at=ts,
                metadata=dict(metadata or {}),
            )
        )

        # 2. KEEP_BOTH (Applicable when temporal scopes or contexts differ)
        temporal_diff = (
            item_a.temporal_scope.valid_from != item_b.temporal_scope.valid_from
            or item_a.temporal_scope.valid_until != item_b.temporal_scope.valid_until
            or item_a.temporal_scope.kind != item_b.temporal_scope.kind
        )
        resource_diff = item_a.resource_id != item_b.resource_id
        actor_diff = item_a.actor_id != item_b.actor_id

        if (
            temporal_diff
            or resource_diff
            or actor_diff
            or cntr_kind
            in (
                ContradictionKind.TEMPORAL,
                ContradictionKind.POSSIBLE,
                ContradictionKind.RELATIONAL,
            )
        ):
            keep_rationale: list[str] = []
            if temporal_diff or cntr_kind == ContradictionKind.TEMPORAL:
                keep_rationale.append(
                    "Items may represent valid statements under distinct temporal scopes or non-overlapping periods."
                )
            if resource_diff or actor_diff:
                keep_rationale.append(
                    "Items originate from different resources or actors and may represent coexisting contextual truths."
                )
            if not keep_rationale:
                keep_rationale.append(
                    "Both items may be preserved under scoped context definitions."
                )

            if (
                temporal_diff
                and item_a.temporal_scope.kind == item_b.temporal_scope.kind
            ):
                keep_conf = 0.90
            elif resource_diff or actor_diff:
                keep_conf = 0.75
            else:
                keep_conf = 0.65

            prop_keep_id = generate_resolution_proposal_id(
                contradiction_id, ResolutionDecision.KEEP_BOTH, item_a.id, item_b.id
            )
            candidates.append(
                ContradictionResolutionProposal(
                    id=prop_keep_id,
                    contradiction_id=contradiction_id,
                    item_a_id=item_a.id,
                    item_b_id=item_b.id,
                    decision=ResolutionDecision.KEEP_BOTH,
                    status=ResolutionStatus.PROPOSED,
                    confidence=keep_conf,
                    rationale=tuple(keep_rationale),
                    evidence_ids=evidence_ids,
                    actor_id=actor_id,
                    created_at=ts,
                    metadata=dict(metadata or {}),
                )
            )

        # 3. PREFER_ITEM_A
        pref_a_rationale: list[str] = []
        conf_a = item_a.confidence.value
        conf_b = item_b.confidence.value
        ev_cnt_a = len(item_a.evidence)
        ev_cnt_b = len(item_b.evidence)

        if conf_a > conf_b:
            pref_a_rationale.append(
                f"Item A has higher epistemic confidence ({conf_a:.2f} vs {conf_b:.2f})."
            )
        if ev_cnt_a > ev_cnt_b:
            pref_a_rationale.append(
                f"Item A is supported by more evidence entries ({ev_cnt_a} vs {ev_cnt_b})."
            )
        if item_a.updated_at > item_b.updated_at:
            pref_a_rationale.append(
                f"Item A is more recently updated than Item B ({item_a.updated_at.isoformat()} vs {item_b.updated_at.isoformat()})."
            )
        if item_a.supersedes_id == item_b.id:
            pref_a_rationale.append("Item A explicitly supersedes Item B in lineage.")
        if preferred_id == item_a.id:
            pref_a_rationale.append(
                f"Item A nominated as preferred in contradiction record ({preference_reason or 'nominated'})."
            )

        if pref_a_rationale or conf_a > conf_b:
            base_conf_a = 0.50
            if conf_a - conf_b >= 0.20:
                base_conf_a += 0.25
            elif conf_a > conf_b:
                base_conf_a += 0.15

            if ev_cnt_a > ev_cnt_b:
                base_conf_a += 0.10
            if item_a.updated_at > item_b.updated_at:
                base_conf_a += 0.10
            if preferred_id == item_a.id or item_a.supersedes_id == item_b.id:
                base_conf_a += 0.15

            pref_a_conf = min(0.95, max(0.20, base_conf_a))

            prop_pref_a_id = generate_resolution_proposal_id(
                contradiction_id, ResolutionDecision.PREFER_ITEM_A, item_a.id, item_b.id
            )
            candidates.append(
                ContradictionResolutionProposal(
                    id=prop_pref_a_id,
                    contradiction_id=contradiction_id,
                    item_a_id=item_a.id,
                    item_b_id=item_b.id,
                    decision=ResolutionDecision.PREFER_ITEM_A,
                    status=ResolutionStatus.PROPOSED,
                    confidence=pref_a_conf,
                    rationale=tuple(
                        pref_a_rationale
                        or ["Item A exhibits higher epistemic priority."]
                    ),
                    evidence_ids=evidence_ids,
                    actor_id=actor_id,
                    created_at=ts,
                    metadata=dict(metadata or {}),
                )
            )

        # 4. PREFER_ITEM_B
        pref_b_rationale: list[str] = []
        if conf_b > conf_a:
            pref_b_rationale.append(
                f"Item B has higher epistemic confidence ({conf_b:.2f} vs {conf_a:.2f})."
            )
        if ev_cnt_b > ev_cnt_a:
            pref_b_rationale.append(
                f"Item B is supported by more evidence entries ({ev_cnt_b} vs {ev_cnt_a})."
            )
        if item_b.updated_at > item_a.updated_at:
            pref_b_rationale.append(
                f"Item B is more recently updated than Item A ({item_b.updated_at.isoformat()} vs {item_a.updated_at.isoformat()})."
            )
        if item_b.supersedes_id == item_a.id:
            pref_b_rationale.append("Item B explicitly supersedes Item A in lineage.")
        if preferred_id == item_b.id:
            pref_b_rationale.append(
                f"Item B nominated as preferred in contradiction record ({preference_reason or 'nominated'})."
            )

        if pref_b_rationale or conf_b > conf_a:
            base_conf_b = 0.50
            if conf_b - conf_a >= 0.20:
                base_conf_b += 0.25
            elif conf_b > conf_a:
                base_conf_b += 0.15

            if ev_cnt_b > ev_cnt_a:
                base_conf_b += 0.10
            if item_b.updated_at > item_a.updated_at:
                base_conf_b += 0.10
            if preferred_id == item_b.id or item_b.supersedes_id == item_a.id:
                base_conf_b += 0.15

            pref_b_conf = min(0.95, max(0.20, base_conf_b))

            prop_pref_b_id = generate_resolution_proposal_id(
                contradiction_id, ResolutionDecision.PREFER_ITEM_B, item_a.id, item_b.id
            )
            candidates.append(
                ContradictionResolutionProposal(
                    id=prop_pref_b_id,
                    contradiction_id=contradiction_id,
                    item_a_id=item_a.id,
                    item_b_id=item_b.id,
                    decision=ResolutionDecision.PREFER_ITEM_B,
                    status=ResolutionStatus.PROPOSED,
                    confidence=pref_b_conf,
                    rationale=tuple(
                        pref_b_rationale
                        or ["Item B exhibits higher epistemic priority."]
                    ),
                    evidence_ids=evidence_ids,
                    actor_id=actor_id,
                    created_at=ts,
                    metadata=dict(metadata or {}),
                )
            )

        # 5. MERGE_INFORMATION
        if item_a.kind == item_b.kind or cntr_kind in (
            ContradictionKind.QUANTITATIVE,
            ContradictionKind.LINEAGE,
            ContradictionKind.RELATIONAL,
        ):
            merge_rationale = (
                f"Items share the same epistemic kind ('{item_a.kind.value}') and can be consolidated "
                "into a merged knowledge item unifying evidence.",
            )
            merge_conf = (
                0.85
                if cntr_kind
                in (ContradictionKind.QUANTITATIVE, ContradictionKind.LINEAGE)
                else 0.70
            )
            prop_merge_id = generate_resolution_proposal_id(
                contradiction_id,
                ResolutionDecision.MERGE_INFORMATION,
                item_a.id,
                item_b.id,
            )
            candidates.append(
                ContradictionResolutionProposal(
                    id=prop_merge_id,
                    contradiction_id=contradiction_id,
                    item_a_id=item_a.id,
                    item_b_id=item_b.id,
                    decision=ResolutionDecision.MERGE_INFORMATION,
                    status=ResolutionStatus.PROPOSED,
                    confidence=merge_conf,
                    rationale=merge_rationale,
                    evidence_ids=evidence_ids,
                    actor_id=actor_id,
                    created_at=ts,
                    metadata=dict(metadata or {}),
                )
            )

        # 6. MARK_ONE_INVALID
        expired_a = (
            item_a.temporal_scope.validity_status == TemporalValidityStatus.EXPIRED
        )
        expired_b = (
            item_b.temporal_scope.validity_status == TemporalValidityStatus.EXPIRED
        )
        superseded_a = item_a.status == KnowledgeStatus.SUPERSEDED
        superseded_b = item_b.status == KnowledgeStatus.SUPERSEDED
        invalid_a = item_a.status == KnowledgeStatus.INVALIDATED
        invalid_b = item_b.status == KnowledgeStatus.INVALIDATED

        if (
            expired_a
            or expired_b
            or superseded_a
            or superseded_b
            or invalid_a
            or invalid_b
            or abs(conf_a - conf_b) >= 0.50
        ):
            inv_rationale: list[str] = []
            if expired_a or superseded_a or invalid_a:
                inv_rationale.append(
                    f"Item A ({item_a.id}) is expired, superseded, or invalidated."
                )
            if expired_b or superseded_b or invalid_b:
                inv_rationale.append(
                    f"Item B ({item_b.id}) is expired, superseded, or invalidated."
                )
            if abs(conf_a - conf_b) >= 0.50:
                inv_rationale.append(
                    f"Significant confidence disparity ({conf_a:.2f} vs {conf_b:.2f}) indicates potential item invalidation."
                )

            inv_conf = (
                0.90
                if (expired_a or expired_b or superseded_a or superseded_b)
                else 0.75
            )
            prop_inv_id = generate_resolution_proposal_id(
                contradiction_id,
                ResolutionDecision.MARK_ONE_INVALID,
                item_a.id,
                item_b.id,
            )
            candidates.append(
                ContradictionResolutionProposal(
                    id=prop_inv_id,
                    contradiction_id=contradiction_id,
                    item_a_id=item_a.id,
                    item_b_id=item_b.id,
                    decision=ResolutionDecision.MARK_ONE_INVALID,
                    status=ResolutionStatus.PROPOSED,
                    confidence=inv_conf,
                    rationale=tuple(inv_rationale),
                    evidence_ids=evidence_ids,
                    actor_id=actor_id,
                    created_at=ts,
                    metadata=dict(metadata or {}),
                )
            )

        # 7. DEFER (Applicable when confidence is low or evidence is lacking)
        if (
            conf_a < 0.50
            and conf_b < 0.50
            or (not item_a.evidence and not item_b.evidence)
        ):
            defer_rationale = (
                "Insufficient evidence or low confidence on both sides to recommend immediate resolution preference.",
            )
            prop_defer_id = generate_resolution_proposal_id(
                contradiction_id, ResolutionDecision.DEFER, item_a.id, item_b.id
            )
            candidates.append(
                ContradictionResolutionProposal(
                    id=prop_defer_id,
                    contradiction_id=contradiction_id,
                    item_a_id=item_a.id,
                    item_b_id=item_b.id,
                    decision=ResolutionDecision.DEFER,
                    status=ResolutionStatus.PROPOSED,
                    confidence=0.70,
                    rationale=defer_rationale,
                    evidence_ids=evidence_ids,
                    actor_id=actor_id,
                    created_at=ts,
                    metadata=dict(metadata or {}),
                )
            )

        # Deterministic sorting: Descending confidence, then ascending decision value
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (-c.confidence, c.decision.value),
        )
        return tuple(sorted_candidates)

    def propose_for_contradiction(
        self,
        contradiction: Contradiction,
        store: KnowledgeStoreProtocol | None = None,
        *,
        actor_id: str | None = None,
        created_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[ContradictionResolutionProposal, ...]:
        """Fetch items from store and generate resolution proposals for a Contradiction record."""
        target_store = store or self._store
        if target_store is None:
            raise KnowledgeStoreNotFoundError(
                "A KnowledgeStore is required to fetch items for a Contradiction record"
            )

        item_a = target_store.get_item(contradiction.item_a_id)
        item_b = target_store.get_item(contradiction.item_b_id)

        if item_a is None:
            raise KnowledgeStoreNotFoundError(
                f"KnowledgeItem item_a ({contradiction.item_a_id}) not found in store"
            )
        if item_b is None:
            raise KnowledgeStoreNotFoundError(
                f"KnowledgeItem item_b ({contradiction.item_b_id}) not found in store"
            )

        return self.propose_resolutions(
            contradiction=contradiction,
            item_a=item_a,
            item_b=item_b,
            actor_id=actor_id,
            created_at=created_at,
            metadata=metadata,
        )

    def propose_for_detection(
        self,
        detection: ContradictionDetection,
        item_a: KnowledgeItem,
        item_b: KnowledgeItem,
        *,
        actor_id: str | None = None,
        created_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[ContradictionResolutionProposal, ...]:
        """Convenience method to generate proposals directly from a ContradictionDetection record."""
        return self.propose_resolutions(
            contradiction=detection,
            item_a=item_a,
            item_b=item_b,
            actor_id=actor_id,
            created_at=created_at,
            metadata=metadata,
        )

    def propose_batch(
        self,
        items: Sequence[
            tuple[
                Contradiction | ContradictionDetection | None,
                KnowledgeItem,
                KnowledgeItem,
            ]
            | Contradiction
            | ContradictionDetection
        ],
        store: KnowledgeStoreProtocol | None = None,
        *,
        actor_id: str | None = None,
        created_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[ContradictionResolutionProposal, ...]:
        """Generate resolution proposals for a batch of contradictions/detections."""
        all_proposals: list[ContradictionResolutionProposal] = []

        for entry in items:
            if isinstance(entry, Contradiction):
                props = self.propose_for_contradiction(
                    contradiction=entry,
                    store=store,
                    actor_id=actor_id,
                    created_at=created_at,
                    metadata=metadata,
                )
            elif isinstance(entry, ContradictionDetection):
                target_store = store or self._store
                if target_store is None:
                    raise KnowledgeStoreNotFoundError(
                        "A KnowledgeStore is required to fetch items for a ContradictionDetection record"
                    )
                item_a = target_store.get_item(entry.item_a_id)
                item_b = target_store.get_item(entry.item_b_id)
                if item_a is None or item_b is None:
                    raise KnowledgeStoreNotFoundError(
                        f"Items for ContradictionDetection ({entry.item_a_id}, {entry.item_b_id}) not found"
                    )
                props = self.propose_for_detection(
                    detection=entry,
                    item_a=item_a,
                    item_b=item_b,
                    actor_id=actor_id,
                    created_at=created_at,
                    metadata=metadata,
                )
            elif isinstance(entry, tuple) and len(entry) == 3:
                cntr, item_a, item_b = entry
                props = self.propose_resolutions(
                    contradiction=cntr,
                    item_a=item_a,
                    item_b=item_b,
                    actor_id=actor_id,
                    created_at=created_at,
                    metadata=metadata,
                )
            else:
                raise InvalidResolutionProposalError(
                    f"Unsupported batch entry format: {entry}"
                )

            all_proposals.extend(props)

        # Sort batch proposals deterministically: contradiction_id, -confidence, decision.value
        all_proposals.sort(
            key=lambda p: (p.contradiction_id, -p.confidence, p.decision.value)
        )
        return tuple(all_proposals)


# Alias for architectural naming equivalence
ContradictionResolutionEngine = KnowledgeContradictionResolver
