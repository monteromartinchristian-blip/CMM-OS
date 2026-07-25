"""Phase 8.12 – Contradiction Resolution Executor.

Implements controlled execution of cognitive contradiction resolutions over KnowledgeStoreProtocol.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any

from cmm.cognitive.contracts import Confidence, utc_now
from cmm.cognitive.errors import (
    InvalidResolutionExecutionError,
    ResolutionExecutionConflictError,
)
from cmm.cognitive.identifiers import generate_cognitive_id
from cmm.cognitive.knowledge import Evidence, KnowledgeItem, KnowledgeRelation
from cmm.cognitive.resolution_contracts import (
    ContradictionResolutionProposal,
    ResolutionDecision,
)
from cmm.cognitive.resolution_executor_contracts import (
    ExecutionStatus,
    ResolutionAuditRecord,
    ResolutionExecutionResult,
)
from cmm.cognitive.resolution_policy_contracts import (
    PolicyDecision,
    ResolutionPolicyEvaluation,
)
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol


def _merge_evidence(
    target: tuple[Evidence, ...],
    sources: Sequence[tuple[Evidence, ...]],
) -> tuple[Evidence, ...]:
    """Merge evidence items safely without duplicate IDs or conflicting evidence payload."""
    by_id: dict[str, Evidence] = {ev.id: ev for ev in target}
    for source_evs in sources:
        for ev in source_evs:
            if ev.id in by_id:
                existing = by_id[ev.id]
                if existing.serialize() != ev.serialize():
                    raise ResolutionExecutionConflictError(
                        f"Evidence conflict on ID '{ev.id}': differing content between target and source"
                    )
            else:
                by_id[ev.id] = ev
    result = list(by_id.values())
    result.sort(key=lambda e: (e.observed_at, e.id))
    return tuple(result)


def _merge_relations(
    target: tuple[KnowledgeRelation, ...],
    sources: Sequence[tuple[KnowledgeRelation, ...]],
) -> tuple[KnowledgeRelation, ...]:
    """Merge relations safely without duplicate IDs or conflicting relation payload."""
    by_id: dict[str, KnowledgeRelation] = {rel.id: rel for rel in target}
    for source_rels in sources:
        for rel in source_rels:
            if rel.id in by_id:
                existing = by_id[rel.id]
                if existing.serialize() != rel.serialize():
                    raise ResolutionExecutionConflictError(
                        f"KnowledgeRelation conflict on ID '{rel.id}': differing content between target and source"
                    )
            else:
                by_id[rel.id] = rel
    result = list(by_id.values())
    result.sort(key=lambda r: (r.created_at, r.id))
    return tuple(result)


def _merge_resolution_metadata(
    target_item: KnowledgeItem,
    source_item: KnowledgeItem,
    proposal_id: str,
) -> dict[str, Any]:
    """Merge metadata non-destructively, preserving lineage and source history."""
    merged = dict(target_item.metadata)
    entry = {
        "proposal_id": proposal_id,
        "merged_source_id": source_item.id,
        "source_metadata": dict(source_item.metadata),
    }
    if "resolution_merge" in merged:
        existing = merged["resolution_merge"]
        if isinstance(existing, list):
            merged["resolution_merge"] = [*existing, entry]
        else:
            merged["resolution_merge"] = [existing, entry]
    else:
        merged["resolution_merge"] = entry
    return merged


class ContradictionResolutionExecutor:
    """Controlled executor of contradiction resolution proposals."""

    def __init__(self, store: KnowledgeStoreProtocol) -> None:
        if store is None or not hasattr(store, "transaction"):
            raise InvalidResolutionExecutionError(
                "store must be a valid KnowledgeStoreProtocol instance"
            )
        self._store = store

    def create_audit_record(
        self,
        execution_id: str,
        proposal: ContradictionResolutionProposal,
        evaluation: ResolutionPolicyEvaluation,
        applied: bool,
        created_item_ids: tuple[str, ...],
        updated_item_ids: tuple[str, ...],
        superseded_item_ids: tuple[str, ...],
        timestamp: datetime,
        actor_id: str | None = None,
    ) -> ResolutionAuditRecord:
        """Create a deterministic ResolutionAuditRecord for a completed execution."""
        audit_payload = f"{execution_id}:{proposal.id}:{proposal.decision.value}:{actor_id or ''}:{timestamp.isoformat()}"
        audit_hash = hashlib.sha256(audit_payload.encode("utf-8")).hexdigest()[:16]
        audit_id = f"audit:resolution:{audit_hash}"

        return ResolutionAuditRecord(
            audit_id=audit_id,
            execution_id=execution_id,
            proposal_id=proposal.id,
            actor_id=actor_id,
            action=f"execute:{proposal.decision.value}",
            timestamp=timestamp,
            details={
                "decision": proposal.decision.value,
                "policy_decision": evaluation.decision.value,
                "applied": applied,
                "created_item_ids": list(created_item_ids),
                "updated_item_ids": list(updated_item_ids),
                "superseded_item_ids": list(superseded_item_ids),
                "contradiction_id": proposal.contradiction_id,
                "item_a_id": proposal.item_a_id,
                "item_b_id": proposal.item_b_id,
            },
        )

    def execute(
        self,
        proposal: ContradictionResolutionProposal,
        evaluation: ResolutionPolicyEvaluation,
        *,
        actor_id: str | None = None,
    ) -> ResolutionExecutionResult:
        """Execute a contradiction resolution proposal atomically after policy verification."""
        if not isinstance(proposal, ContradictionResolutionProposal):
            raise InvalidResolutionExecutionError(
                "proposal must be a ContradictionResolutionProposal instance"
            )
        if not isinstance(evaluation, ResolutionPolicyEvaluation):
            raise InvalidResolutionExecutionError(
                "evaluation must be a ResolutionPolicyEvaluation instance"
            )

        if evaluation.proposal_id != proposal.id:
            raise InvalidResolutionExecutionError(
                f"evaluation.proposal_id '{evaluation.proposal_id}' does not match proposal.id '{proposal.id}'"
            )

        if (
            evaluation.decision != PolicyDecision.AUTO_APPROVED
            or evaluation.allowed is not True
        ):
            raise InvalidResolutionExecutionError(
                f"Proposal '{proposal.id}' is not approved for execution: decision={evaluation.decision.value}, allowed={evaluation.allowed}"
            )

        if proposal.decision == ResolutionDecision.REQUEST_HUMAN_REVIEW:
            raise InvalidResolutionExecutionError(
                "Decision REQUEST_HUMAN_REVIEW cannot be executed automatically"
            )

        started_at = utc_now()
        execution_id = generate_cognitive_id("resolution-exec", "cognitive")
        effective_actor_id = actor_id if actor_id is not None else proposal.actor_id

        created_ids: tuple[str, ...] = ()
        updated_ids: tuple[str, ...] = ()
        superseded_ids: tuple[str, ...] = ()
        applied = False

        try:
            with self._store.transaction():
                if proposal.decision in (
                    ResolutionDecision.KEEP_BOTH,
                    ResolutionDecision.DEFER,
                ):
                    applied = False

                elif proposal.decision == ResolutionDecision.PREFER_ITEM_A:
                    item_a = self._store.get_item(proposal.item_a_id)
                    item_b = self._store.get_item(proposal.item_b_id)

                    ts = utc_now()
                    superseded_b = item_b.mark_superseded(
                        proposal.item_a_id, superseded_at=ts
                    )
                    updated_a = replace(
                        item_a, supersedes_id=proposal.item_b_id, updated_at=ts
                    )

                    self._store.save_item(superseded_b)
                    self._store.save_item(updated_a)

                    applied = True
                    updated_ids = (updated_a.id,)
                    superseded_ids = (superseded_b.id,)

                elif proposal.decision == ResolutionDecision.PREFER_ITEM_B:
                    item_a = self._store.get_item(proposal.item_a_id)
                    item_b = self._store.get_item(proposal.item_b_id)

                    ts = utc_now()
                    superseded_a = item_a.mark_superseded(
                        proposal.item_b_id, superseded_at=ts
                    )
                    updated_b = replace(
                        item_b, supersedes_id=proposal.item_a_id, updated_at=ts
                    )

                    self._store.save_item(superseded_a)
                    self._store.save_item(updated_b)

                    applied = True
                    updated_ids = (updated_b.id,)
                    superseded_ids = (superseded_a.id,)

                elif proposal.decision == ResolutionDecision.MARK_ONE_INVALID:
                    invalid_item_id = proposal.metadata.get(
                        "invalid_item_id", proposal.item_b_id
                    )
                    target_item = self._store.get_item(invalid_item_id)
                    reason = (
                        proposal.metadata.get("invalidation_reason")
                        or f"Invalidated by contradiction resolution proposal '{proposal.id}'"
                    )

                    ts = utc_now()
                    invalidated_item = target_item.invalidate(
                        reason=reason, invalidated_at=ts
                    )
                    self._store.save_item(invalidated_item)

                    applied = True
                    updated_ids = (invalidated_item.id,)

                elif proposal.decision == ResolutionDecision.MERGE_INFORMATION:
                    target_id = proposal.metadata.get(
                        "target_item_id", proposal.item_a_id
                    )
                    source_id = (
                        proposal.item_b_id
                        if target_id == proposal.item_a_id
                        else proposal.item_a_id
                    )

                    target_item = self._store.get_item(target_id)
                    source_item = self._store.get_item(source_id)

                    ts = utc_now()
                    merged_ev = _merge_evidence(
                        target_item.evidence, [source_item.evidence]
                    )
                    merged_rel = _merge_relations(
                        target_item.relations, [source_item.relations]
                    )
                    merged_meta = _merge_resolution_metadata(
                        target_item, source_item, proposal.id
                    )

                    min_conf = min(
                        target_item.confidence.value, source_item.confidence.value
                    )
                    merged_conf = Confidence(
                        value=min_conf,
                        source=f"resolution:{proposal.id}",
                        reasons=(f"Merged from proposal {proposal.id}",),
                    )

                    updated_target = replace(
                        target_item,
                        evidence=merged_ev,
                        relations=merged_rel,
                        metadata=merged_meta,
                        confidence=merged_conf,
                        updated_at=ts,
                    )
                    superseded_source = source_item.mark_superseded(
                        target_id, superseded_at=ts
                    )

                    self._store.save_item(updated_target)
                    self._store.save_item(superseded_source)

                    applied = True
                    updated_ids = (target_id,)
                    superseded_ids = (source_id,)

                else:
                    raise InvalidResolutionExecutionError(
                        f"Unsupported resolution decision: {proposal.decision}"
                    )

        except Exception as exc:  # noqa: BLE001
            finished_at = utc_now()
            return ResolutionExecutionResult(
                execution_id=execution_id,
                proposal_id=proposal.id,
                status=ExecutionStatus.ROLLED_BACK,
                applied=False,
                created_item_ids=(),
                updated_item_ids=(),
                superseded_item_ids=(),
                warnings=evaluation.warnings,
                errors=(str(exc),),
                started_at=started_at,
                finished_at=finished_at,
                metadata={"error_type": exc.__class__.__name__},
            )

        finished_at = utc_now()
        audit_record = self.create_audit_record(
            execution_id=execution_id,
            proposal=proposal,
            evaluation=evaluation,
            applied=applied,
            created_item_ids=created_ids,
            updated_item_ids=updated_ids,
            superseded_item_ids=superseded_ids,
            timestamp=finished_at,
            actor_id=effective_actor_id,
        )

        res_metadata = dict(proposal.metadata)
        res_metadata["audit_record"] = audit_record.serialize()
        res_metadata["audit_id"] = audit_record.audit_id

        return ResolutionExecutionResult(
            execution_id=execution_id,
            proposal_id=proposal.id,
            status=ExecutionStatus.COMPLETED,
            applied=applied,
            created_item_ids=created_ids,
            updated_item_ids=updated_ids,
            superseded_item_ids=superseded_ids,
            warnings=evaluation.warnings,
            errors=(),
            started_at=started_at,
            finished_at=finished_at,
            metadata=res_metadata,
        )
