"""Phase 9.18 – Knowledge and Memory Update Manager.

Lifecycle manager supporting proposal, evaluation, approval, decision-making, and safe execution
of knowledge and memory updates. Delegates actual store mutations to external writer adapters.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from cmm.agent_runtime.enums import (
    KnowledgeProposalStatus,
    KnowledgeWriteDecisionKind,
    MemoryWriteDecisionKind,
)
from cmm.agent_runtime.errors import (
    KnowledgeApprovalRequiredError,
    KnowledgeUpdateExecutionError,
    KnowledgeWriteError,
)
from cmm.agent_runtime.knowledge_update_contracts import (
    AgentKnowledgeUpdateProposal,
    KnowledgeUpdateContext,
    KnowledgeUpdateDecision,
    KnowledgeUpdateResult,
    MemoryUpdateProposal,
    MemoryUpdateResult,
)
from cmm.agent_runtime.knowledge_update_proposal_engine import (
    KnowledgeUpdateProposalEngine,
)
from cmm.agent_runtime.knowledge_update_repository import (
    InMemoryKnowledgeUpdateRepository,
    KnowledgeUpdateRepository,
)


class KnowledgeMemoryUpdateManager:
    """Manages the full proposal, approval, decision, and application lifecycle."""

    def __init__(
        self,
        repository: KnowledgeUpdateRepository | None = None,
        integrations: Mapping[str, Any] | None = None,
    ) -> None:
        self.repository = repository or InMemoryKnowledgeUpdateRepository()
        self.integrations = dict(integrations or {})
        self.proposal_engine = KnowledgeUpdateProposalEngine(
            repository=self.repository, integrations=self.integrations
        )

    def _publish_event(
        self,
        event_type: str,
        proposal_id: str,
        run_id: str,
        goal_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Helper publishing structured domain events to EventBus with trace metadata."""
        event_bus = self.integrations.get("event_bus")
        if not event_bus or not hasattr(event_bus, "publish"):
            return

        event_payload = {
            "event_id": f"evt-knw-{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "agent_run_id": run_id,
            "goal_id": goal_id,
            "proposal_id": proposal_id,
            "correlation_id": proposal_id,
            "metadata": payload,
        }
        try:
            event_bus.publish(event_type, event_payload)
        except Exception:  # noqa: BLE001
            return

    def propose(
        self,
        context: KnowledgeUpdateContext,
        outcome_eval: Any | None = None,
        completion_decision: Any | None = None,
        goal: Any | None = None,
        operation_results: Sequence[Any] | None = None,
        validations: Sequence[Any] | None = None,
        recovery_history: Sequence[Any] | None = None,
        checkpoints: Sequence[Any] | None = None,
        transaction_results: Sequence[Any] | None = None,
        side_effects: Sequence[Any] | None = None,
        regressions: Sequence[Any] | None = None,
        debt_items: Sequence[Any] | None = None,
        acquired_knowledge: Sequence[Any] | None = None,
        remaining_gaps: Sequence[Any] | None = None,
        user_confirmed_preferences: Sequence[Any] | None = None,
        generated_artifacts: Sequence[Any] | None = None,
        existing_knowledge: Sequence[Any] | None = None,
    ) -> AgentKnowledgeUpdateProposal:
        """Generate and persist a knowledge update proposal."""
        return self.proposal_engine.create_proposal(
            context=context,
            outcome_eval=outcome_eval,
            completion_decision=completion_decision,
            goal=goal,
            operation_results=operation_results,
            validations=validations,
            recovery_history=recovery_history,
            checkpoints=checkpoints,
            transaction_results=transaction_results,
            side_effects=side_effects,
            regressions=regressions,
            debt_items=debt_items,
            acquired_knowledge=acquired_knowledge,
            remaining_gaps=remaining_gaps,
            user_confirmed_preferences=user_confirmed_preferences,
            generated_artifacts=generated_artifacts,
            existing_knowledge=existing_knowledge,
        )

    def decide(
        self,
        proposal_id: str,
        approved: bool = True,
        approved_by: str | None = None,
        rejection_reason: str | None = None,
    ) -> KnowledgeUpdateDecision:
        """Make an explicit decision to approve, reject, or mark pending a proposal."""
        proposal = self.repository.get_proposal(proposal_id)
        if not proposal:
            raise KnowledgeUpdateExecutionError(f"Proposal '{proposal_id}' not found")

        status = (
            KnowledgeProposalStatus.APPROVED
            if approved
            else KnowledgeProposalStatus.REJECTED
        )

        item_decisions: dict[str, KnowledgeWriteDecisionKind] = {}
        for add in proposal.additions:
            item_decisions[add.addition_id] = (
                KnowledgeWriteDecisionKind.ADD
                if approved
                else KnowledgeWriteDecisionKind.REJECT
            )
        for upd in proposal.updates:
            is_merge = upd.metadata.get("operation") == "merge"
            item_decisions[upd.update_id] = (
                (
                    KnowledgeWriteDecisionKind.MERGE
                    if is_merge
                    else KnowledgeWriteDecisionKind.UPDATE
                )
                if approved
                else KnowledgeWriteDecisionKind.REJECT
            )
        for inv in proposal.invalidations:
            item_decisions[inv.invalidation_id] = (
                KnowledgeWriteDecisionKind.INVALIDATE
                if approved
                else KnowledgeWriteDecisionKind.REJECT
            )
        for rel in proposal.relations:
            item_decisions[rel.relation_id] = (
                KnowledgeWriteDecisionKind.LINK
                if approved
                else KnowledgeWriteDecisionKind.REJECT
            )

        decision = KnowledgeUpdateDecision(
            decision_id=f"dec-knw-{uuid.uuid4().hex[:8]}",
            proposal_id=proposal_id,
            status=status,
            item_decisions=item_decisions,
            approved_by=approved_by,
            rejection_reason=rejection_reason,
        )

        self.repository.save_decision(decision)
        self._publish_event(
            "KNOWLEDGE_UPDATE_DECISION_MADE",
            proposal_id,
            proposal.agent_run_id,
            proposal.goal_id,
            {"status": status.value},
        )
        return decision

    def apply(
        self,
        proposal_id: str,
        memory_proposal: MemoryUpdateProposal | None = None,
    ) -> tuple[KnowledgeUpdateResult, MemoryUpdateResult | None]:
        """Apply approved knowledge and memory updates via external writers."""
        proposal = self.repository.get_proposal(proposal_id)
        if not proposal:
            raise KnowledgeUpdateExecutionError(f"Proposal '{proposal_id}' not found")

        decision = self.repository.get_decision(proposal_id)

        # Require approval check
        if proposal.requires_approval and (
            not decision or decision.status != KnowledgeProposalStatus.APPROVED
        ):
            raise KnowledgeApprovalRequiredError(
                f"Proposal '{proposal_id}' requires explicit approval before application"
            )

        # Check writer integration
        knowledge_writer = self.integrations.get("knowledge_writer")
        if not knowledge_writer:
            raise KnowledgeWriteError(
                "Missing required 'knowledge_writer' integration. Cannot simulate write success."
            )

        self._publish_event(
            "KNOWLEDGE_UPDATE_APPLY_STARTED",
            proposal_id,
            proposal.agent_run_id,
            proposal.goal_id,
            {},
        )

        applied_additions: list[str] = []
        applied_updates: list[str] = []
        applied_invalidations: list[str] = []
        applied_relations: list[str] = []
        applied_facts: list[str] = []
        applied_lessons: list[str] = []
        failed_items: list[str] = []
        failure_causes: dict[str, str] = {}

        def _record_failure(item_id: str, cause: str) -> None:
            failed_items.append(item_id)
            failure_causes[item_id] = cause

        def _item_decision(item_id: str) -> KnowledgeWriteDecisionKind | None:
            if not decision:
                return None
            return decision.item_decisions.get(item_id)

        def _apply_item(
            item_id: str,
            allowed: set[KnowledgeWriteDecisionKind],
            apply_fn: Any,
            success_store: list[str],
            success_event: str,
            event_key: str,
            extra_metadata: dict[str, Any] | None = None,
        ) -> None:
            item_decision = _item_decision(item_id)
            if item_decision is None:
                _record_failure(item_id, "MISSING_ITEM_DECISION")
                return
            if item_decision in (
                KnowledgeWriteDecisionKind.REJECT,
                KnowledgeWriteDecisionKind.DEFER,
                KnowledgeWriteDecisionKind.REQUIRE_APPROVAL,
            ):
                _record_failure(item_id, f"ITEM_DECISION_{item_decision.value.upper()}")
                return
            if item_decision not in allowed:
                _record_failure(
                    item_id, f"ITEM_DECISION_NOT_ALLOWED_{item_decision.value}"
                )
                return
            try:
                apply_fn()
                success_store.append(item_id)
                self._publish_event(
                    success_event,
                    proposal_id,
                    proposal.agent_run_id,
                    proposal.goal_id,
                    {event_key: item_id, **(extra_metadata or {})},
                )
            except Exception as exc:  # noqa: BLE001
                _record_failure(item_id, str(exc))

        def _write_merge(upd: Any) -> None:
            """Delegate a merge write to a dedicated writer method, or fall back
            to a versioned-update writer that can safely accept the merge payload
            (it already carries combined fields, provenance, and version lineage).
            A writer offering neither must fail the item, never fake success."""
            if hasattr(knowledge_writer, "write_merge"):
                knowledge_writer.write_merge(upd)
            elif hasattr(knowledge_writer, "write_update"):
                knowledge_writer.write_update(upd)
            else:
                raise KnowledgeWriteError(
                    "knowledge_writer supports neither write_merge nor write_update "
                    f"for merge '{upd.update_id}'"
                )

        for add in proposal.additions:
            _apply_item(
                add.addition_id,
                {KnowledgeWriteDecisionKind.ADD},
                lambda add=add: (
                    knowledge_writer.write_addition(add)
                    if hasattr(knowledge_writer, "write_addition")
                    else None
                ),
                applied_additions,
                "KNOWLEDGE_ITEM_ADDED",
                "item_id",
            )

        for upd in proposal.updates:
            if upd.metadata.get("operation") == "merge":
                _apply_item(
                    upd.update_id,
                    {KnowledgeWriteDecisionKind.MERGE},
                    lambda upd=upd: _write_merge(upd),
                    applied_updates,
                    "KNOWLEDGE_ITEM_UPDATED",
                    "item_id",
                    extra_metadata={"operation": "merge"},
                )
            else:
                _apply_item(
                    upd.update_id,
                    {KnowledgeWriteDecisionKind.UPDATE},
                    lambda upd=upd: (
                        knowledge_writer.write_update(upd)
                        if hasattr(knowledge_writer, "write_update")
                        else None
                    ),
                    applied_updates,
                    "KNOWLEDGE_ITEM_UPDATED",
                    "item_id",
                )

        for inv in proposal.invalidations:
            _apply_item(
                inv.invalidation_id,
                {KnowledgeWriteDecisionKind.INVALIDATE},
                lambda inv=inv: (
                    knowledge_writer.write_invalidation(inv)
                    if hasattr(knowledge_writer, "write_invalidation")
                    else None
                ),
                applied_invalidations,
                "KNOWLEDGE_ITEM_INVALIDATED",
                "item_id",
            )

        for rel in proposal.relations:
            _apply_item(
                rel.relation_id,
                {KnowledgeWriteDecisionKind.LINK, KnowledgeWriteDecisionKind.MERGE},
                lambda rel=rel: (
                    knowledge_writer.write_relation(rel)
                    if hasattr(knowledge_writer, "write_relation")
                    else None
                ),
                applied_relations,
                "KNOWLEDGE_RELATION_CREATED",
                "relation_id",
            )

        for les in proposal.lessons:
            try:
                if hasattr(knowledge_writer, "write_lesson"):
                    knowledge_writer.write_lesson(les)
                applied_lessons.append(les.lesson_id)
                self._publish_event(
                    "OPERATIONAL_LESSON_CREATED",
                    proposal_id,
                    proposal.agent_run_id,
                    proposal.goal_id,
                    {"lesson_id": les.lesson_id},
                )
            except Exception as exc:  # noqa: BLE001
                _record_failure(les.lesson_id, str(exc))

        applied_total = (
            len(applied_additions)
            + len(applied_updates)
            + len(applied_invalidations)
            + len(applied_relations)
            + len(applied_lessons)
        )
        failed_total = len(failed_items)
        if applied_total == 0 and failed_total > 0:
            status = KnowledgeProposalStatus.FAILED
        elif applied_total > 0 and failed_total > 0:
            status = KnowledgeProposalStatus.PARTIALLY_APPLIED
        else:
            status = KnowledgeProposalStatus.APPLIED

        mem_result: MemoryUpdateResult | None = None
        memory_failed_keys: list[str] = []
        if memory_proposal:
            memory_writer = self.integrations.get("memory_writer")
            if not memory_writer:
                raise KnowledgeWriteError(
                    "Missing required 'memory_writer' integration for memory proposal application."
                )
            self.repository.save_memory_proposal(memory_proposal)
            self._publish_event(
                "MEMORY_UPDATE_PROPOSED",
                proposal_id,
                proposal.agent_run_id,
                proposal.goal_id,
                {"memory_proposal_id": memory_proposal.memory_proposal_id},
            )
            self._publish_event(
                "MEMORY_UPDATE_APPLY_STARTED",
                proposal_id,
                proposal.agent_run_id,
                proposal.goal_id,
                {"memory_proposal_id": memory_proposal.memory_proposal_id},
            )
            written_keys: list[str] = []
            updated_keys: list[str] = []
            rejected_keys: list[str] = []

            decision_by_candidate = {
                d.candidate_id: d for d in memory_proposal.decisions
            }
            for cand in memory_proposal.candidates:
                cand_decision = decision_by_candidate.get(cand.candidate_id)
                if cand_decision is None:
                    rejected_keys.append(cand.key)
                    self._publish_event(
                        "MEMORY_UPDATE_REJECTED",
                        proposal_id,
                        proposal.agent_run_id,
                        proposal.goal_id,
                        {"key": cand.key, "reason": "MISSING_DECISION"},
                    )
                    continue

                if (
                    cand_decision.decision
                    == MemoryWriteDecisionKind.ALLOW_WITH_CONFIRMATION
                ):
                    rejected_keys.append(cand.key)
                    self._publish_event(
                        "MEMORY_UPDATE_CONFIRMATION_REQUESTED",
                        proposal_id,
                        proposal.agent_run_id,
                        proposal.goal_id,
                        {"key": cand.key},
                    )
                    continue

                if cand_decision.decision in (
                    MemoryWriteDecisionKind.REJECT,
                    MemoryWriteDecisionKind.DEFER,
                    MemoryWriteDecisionKind.ESCALATE,
                ):
                    rejected_keys.append(cand.key)
                    self._publish_event(
                        "MEMORY_UPDATE_REJECTED",
                        proposal_id,
                        proposal.agent_run_id,
                        proposal.goal_id,
                        {"key": cand.key, "reason": cand_decision.decision.value},
                    )
                    continue

                metadata = {
                    "source_run_id": getattr(cand.provenance, "source_run_id", None),
                    "source_goal_id": getattr(cand.provenance, "source_goal_id", None),
                    "evidence_ids": getattr(cand.provenance, "evidence_ids", ()),
                    "agent_run_id": proposal.agent_run_id,
                    "goal_id": proposal.goal_id,
                    "proposal_id": proposal.proposal_id,
                    "version": cand.metadata.get("version", 1),
                    "confidence": cand.confidence,
                    "expiration": (
                        cand.expiration.ttl_seconds if cand.expiration else None
                    ),
                }
                try:
                    if not hasattr(memory_writer, "write_memory_item"):
                        raise KnowledgeWriteError(
                            "memory_writer must implement write_memory_item(candidate, metadata). "
                            "Use an explicit adapter for key/value writers."
                        )
                    memory_writer.write_memory_item(cand, metadata)
                    if cand.metadata.get("operation") == "update":
                        updated_keys.append(cand.key)
                        self._publish_event(
                            "MEMORY_ITEM_UPDATED",
                            proposal_id,
                            proposal.agent_run_id,
                            proposal.goal_id,
                            {"key": cand.key},
                        )
                    else:
                        written_keys.append(cand.key)
                        self._publish_event(
                            "MEMORY_ITEM_WRITTEN",
                            proposal_id,
                            proposal.agent_run_id,
                            proposal.goal_id,
                            {"key": cand.key},
                        )
                except Exception as exc:  # noqa: BLE001
                    memory_failed_keys.append(cand.key)
                    self._publish_event(
                        "MEMORY_UPDATE_REJECTED",
                        proposal_id,
                        proposal.agent_run_id,
                        proposal.goal_id,
                        {"key": cand.key, "reason": str(exc)},
                    )

            mem_result = MemoryUpdateResult(
                result_id=f"res-mem-{uuid.uuid4().hex[:8]}",
                memory_proposal_id=memory_proposal.memory_proposal_id,
                written_keys=tuple(written_keys + updated_keys),
                rejected_keys=tuple(rejected_keys),
                failed_keys=tuple(memory_failed_keys),
            )
            self.repository.save_memory_result(mem_result)

        if memory_failed_keys and status == KnowledgeProposalStatus.APPLIED:
            status = KnowledgeProposalStatus.PARTIALLY_APPLIED
        elif memory_failed_keys and status == KnowledgeProposalStatus.FAILED:
            status = KnowledgeProposalStatus.FAILED

        knw_result = KnowledgeUpdateResult(
            result_id=f"res-knw-{uuid.uuid4().hex[:8]}",
            proposal_id=proposal_id,
            status=status,
            applied_additions=tuple(applied_additions),
            applied_updates=tuple(applied_updates),
            applied_invalidations=tuple(applied_invalidations),
            applied_relations=tuple(applied_relations),
            applied_facts=tuple(applied_facts),
            applied_lessons=tuple(applied_lessons),
            failed_item_ids=tuple(failed_items),
            metadata={"failure_causes": failure_causes},
        )
        self.repository.save_result(knw_result)

        if status == KnowledgeProposalStatus.APPLIED:
            event_name = "KNOWLEDGE_UPDATE_APPLIED"
        elif status == KnowledgeProposalStatus.PARTIALLY_APPLIED:
            event_name = "KNOWLEDGE_UPDATE_PARTIALLY_APPLIED"
        else:
            event_name = "KNOWLEDGE_UPDATE_FAILED"
        self._publish_event(
            event_name,
            proposal_id,
            proposal.agent_run_id,
            proposal.goal_id,
            {"failed_items": tuple(failed_items)},
        )

        return knw_result, mem_result

    def propose_and_apply(
        self,
        context: KnowledgeUpdateContext,
        outcome_eval: Any | None = None,
        completion_decision: Any | None = None,
        goal: Any | None = None,
        operation_results: Sequence[Any] | None = None,
        validations: Sequence[Any] | None = None,
        recovery_history: Sequence[Any] | None = None,
        checkpoints: Sequence[Any] | None = None,
        transaction_results: Sequence[Any] | None = None,
        side_effects: Sequence[Any] | None = None,
        regressions: Sequence[Any] | None = None,
        debt_items: Sequence[Any] | None = None,
        acquired_knowledge: Sequence[Any] | None = None,
        remaining_gaps: Sequence[Any] | None = None,
        user_confirmed_preferences: Sequence[Any] | None = None,
        generated_artifacts: Sequence[Any] | None = None,
        existing_knowledge: Sequence[Any] | None = None,
        memory_proposal: MemoryUpdateProposal | None = None,
        auto_approve: bool = True,
    ) -> tuple[
        AgentKnowledgeUpdateProposal,
        KnowledgeUpdateDecision,
        KnowledgeUpdateResult,
        MemoryUpdateResult | None,
    ]:
        """Propose, decide, and apply in a single composition pipeline."""
        proposal = self.propose(
            context=context,
            outcome_eval=outcome_eval,
            completion_decision=completion_decision,
            goal=goal,
            operation_results=operation_results,
            validations=validations,
            recovery_history=recovery_history,
            checkpoints=checkpoints,
            transaction_results=transaction_results,
            side_effects=side_effects,
            regressions=regressions,
            debt_items=debt_items,
            acquired_knowledge=acquired_knowledge,
            remaining_gaps=remaining_gaps,
            user_confirmed_preferences=user_confirmed_preferences,
            generated_artifacts=generated_artifacts,
            existing_knowledge=existing_knowledge,
        )

        should_approve = auto_approve and not proposal.requires_approval
        decision = self.decide(
            proposal.proposal_id,
            approved=should_approve,
            approved_by="auto_policy" if should_approve else None,
        )

        if not should_approve:
            raise KnowledgeApprovalRequiredError(
                f"Proposal '{proposal.proposal_id}' requires explicit human approval"
            )

        knw_res, mem_res = self.apply(
            proposal.proposal_id, memory_proposal=memory_proposal
        )
        return proposal, decision, knw_res, mem_res
