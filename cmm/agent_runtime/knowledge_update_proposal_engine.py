"""Phase 9.18 – Knowledge Update Proposal Engine.

Orchestrates candidate extraction, relevance evaluation, confidence evaluation, sensitivity filtering,
deduplication, contradiction resolution, operational lesson extraction, memory policy evaluation,
proposal building, repository persistence, and domain event emission.
Does not directly apply write operations to underlying stores.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from cmm.agent_runtime.enums import (
    KnowledgeCandidateKind,
    KnowledgeRejectionReason,
    KnowledgeSensitivityLevel,
    KnowledgeWriteDecisionKind,
    Outcome,
)
from cmm.agent_runtime.errors import (
    KnowledgeUpdateContextError,
)
from cmm.agent_runtime.knowledge_candidate_extractor import KnowledgeCandidateExtractor
from cmm.agent_runtime.knowledge_confidence_evaluator import (
    KnowledgeConfidenceEvaluator,
)
from cmm.agent_runtime.knowledge_contradiction_resolver import (
    KnowledgeContradictionResolver,
)
from cmm.agent_runtime.knowledge_deduplicator import KnowledgeDeduplicator
from cmm.agent_runtime.knowledge_relevance_evaluator import KnowledgeRelevanceEvaluator
from cmm.agent_runtime.knowledge_sensitivity_policy import (
    KnowledgeSensitivityPolicyAdapter,
)
from cmm.agent_runtime.knowledge_update_contracts import (
    AgentDecisionRecord,
    AgentKnowledgeUpdateProposal,
    KnowledgeAddition,
    KnowledgeInvalidation,
    KnowledgeProvenance,
    KnowledgeRelation,
    KnowledgeSensitivityAssessment,
    KnowledgeUpdate,
    KnowledgeUpdateContext,
    KnowledgeVersionReference,
    OperationFact,
    RejectedKnowledgeItem,
)
from cmm.agent_runtime.knowledge_update_policy_adapter import (
    KnowledgeUpdatePolicyAdapter,
)
from cmm.agent_runtime.knowledge_update_repository import (
    InMemoryKnowledgeUpdateRepository,
    KnowledgeUpdateRepository,
)
from cmm.agent_runtime.memory_update_policy_adapter import MemoryUpdatePolicyAdapter
from cmm.agent_runtime.operational_lesson_extractor import OperationalLessonExtractor


class KnowledgeUpdateProposalEngine:
    """Autonomous engine for composing audit-ready knowledge and memory update proposals."""

    def __init__(
        self,
        repository: KnowledgeUpdateRepository | None = None,
        integrations: Mapping[str, Any] | None = None,
    ) -> None:
        self.repository = repository or InMemoryKnowledgeUpdateRepository()
        self.integrations = dict(integrations or {})
        self.candidate_extractor = KnowledgeCandidateExtractor()
        self.relevance_evaluator = KnowledgeRelevanceEvaluator()
        self.confidence_evaluator = KnowledgeConfidenceEvaluator()
        self.sensitivity_policy = KnowledgeSensitivityPolicyAdapter()
        self.deduplicator = KnowledgeDeduplicator()
        self.contradiction_resolver = KnowledgeContradictionResolver()
        self.lesson_extractor = OperationalLessonExtractor()
        self.memory_policy = MemoryUpdatePolicyAdapter()
        self.knowledge_policy = KnowledgeUpdatePolicyAdapter()

    @staticmethod
    def _normalize_outcome(outcome_eval: Any | None) -> str:
        if outcome_eval is None:
            return Outcome.SUCCESS.value
        raw = getattr(outcome_eval, "outcome", Outcome.SUCCESS)
        return getattr(raw, "value", str(raw))

    @staticmethod
    def _contains_internal_reasoning(payload: Any) -> bool:
        keys = {
            "chain_of_thought",
            "internal_reasoning",
            "hidden_reasoning",
            "private_reasoning",
            "scratchpad",
        }
        if isinstance(payload, dict):
            for key, value in payload.items():
                if str(key).strip().lower() in keys:
                    return True
                if KnowledgeUpdateProposalEngine._contains_internal_reasoning(value):
                    return True
            return False
        if isinstance(payload, (list, tuple, set)):
            return any(
                KnowledgeUpdateProposalEngine._contains_internal_reasoning(item)
                for item in payload
            )
        return False

    @staticmethod
    def _candidate_allowed_for_outcome(
        kind: KnowledgeCandidateKind, outcome: str
    ) -> bool:
        if outcome == Outcome.SUCCESS.value:
            return True
        if outcome == Outcome.PARTIAL_SUCCESS.value:
            return kind in {
                KnowledgeCandidateKind.COMPLETED_GOAL,
                KnowledgeCandidateKind.OPERATION_RESULT,
                KnowledgeCandidateKind.VALIDATED_STATE,
                KnowledgeCandidateKind.CONSTRAINT,
                KnowledgeCandidateKind.REPRODUCIBLE_ERROR,
                KnowledgeCandidateKind.FAILED_STRATEGY,
                KnowledgeCandidateKind.CONTRADICTION,
                KnowledgeCandidateKind.TECHNICAL_DEBT,
            }
        if outcome == Outcome.INCONCLUSIVE.value:
            return kind in {
                KnowledgeCandidateKind.CONSTRAINT,
                KnowledgeCandidateKind.CONTRADICTION,
            }
        if outcome == Outcome.FAILURE.value:
            return kind in {
                KnowledgeCandidateKind.REPRODUCIBLE_ERROR,
                KnowledgeCandidateKind.FAILED_STRATEGY,
                KnowledgeCandidateKind.CONTRADICTION,
                KnowledgeCandidateKind.TECHNICAL_DEBT,
                KnowledgeCandidateKind.CONSTRAINT,
            }
        if outcome == Outcome.REGRESSION.value:
            return kind in {
                KnowledgeCandidateKind.CONTRADICTION,
                KnowledgeCandidateKind.REPRODUCIBLE_ERROR,
                KnowledgeCandidateKind.FAILED_STRATEGY,
                KnowledgeCandidateKind.TECHNICAL_DEBT,
            }
        if outcome == Outcome.CANCELLED.value:
            return kind in {
                KnowledgeCandidateKind.CONSTRAINT,
                KnowledgeCandidateKind.TECHNICAL_DEBT,
            }
        return True

    @staticmethod
    def _lesson_allowed_for_outcome(kind: str, outcome: str) -> bool:
        if outcome == Outcome.SUCCESS.value:
            return True
        if outcome == Outcome.PARTIAL_SUCCESS.value:
            return kind != "success_pattern"
        if outcome == Outcome.INCONCLUSIVE.value:
            return kind in ("failure_pattern", "recovery_pattern")
        if outcome == Outcome.FAILURE.value:
            return kind in ("failure_pattern", "recovery_pattern")
        if outcome == Outcome.REGRESSION.value:
            return kind in ("failure_pattern", "recovery_pattern")
        if outcome == Outcome.CANCELLED.value:
            return kind != "success_pattern"
        return True

    @staticmethod
    def _resolve_existing_version(
        existing_knowledge: Sequence[Any] | None, existing_item_id: str
    ) -> tuple[Any | None, int, str | None, str | None]:
        """Locate the matched existing item and derive its version lineage.

        Returns (existing_item, next_version, previous_version_id, previous_provenance_fingerprint).
        """
        existing_item = None
        for candidate_item in existing_knowledge or ():
            existing_id = getattr(
                candidate_item,
                "addition_id",
                getattr(
                    candidate_item,
                    "item_id",
                    getattr(candidate_item, "candidate_id", None),
                ),
            )
            if existing_id == existing_item_id:
                existing_item = candidate_item
                break

        existing_version = 1
        previous_version_id = None
        previous_provenance = None
        if existing_item is not None:
            version_ref = getattr(existing_item, "version_ref", None)
            existing_version = (
                getattr(version_ref, "version", 1) + 1 if version_ref is not None else 2
            )
            previous_version_id = (
                getattr(version_ref, "item_id", None)
                if version_ref is not None
                else existing_item_id
            )
            existing_provenance = getattr(existing_item, "provenance", None)
            if existing_provenance is not None:
                previous_provenance = getattr(existing_provenance, "fingerprint", None)
        return existing_item, existing_version, previous_version_id, previous_provenance

    def _publish_event(
        self,
        event_type: str,
        proposal_id: str,
        context: KnowledgeUpdateContext,
        payload: dict[str, Any],
    ) -> None:
        """Helper publishing structured domain events to EventBus with trace metadata."""
        event_bus = self.integrations.get("event_bus")
        if not event_bus or not hasattr(event_bus, "publish"):
            return

        event_payload = {
            "event_id": f"evt-knw-{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "agent_run_id": context.agent_run_id,
            "goal_id": context.goal_id,
            "workflow_id": context.workflow_id,
            "iteration_id": context.iteration_id,
            "outcome_evaluation_id": context.outcome_evaluation_id,
            "proposal_id": proposal_id,
            "correlation_id": proposal_id,
            "causation_id": context.context_id,
            "metadata": payload,
        }
        try:
            event_bus.publish(event_type, event_payload)
        except Exception:  # noqa: BLE001
            return

    def create_proposal(
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
        """Run the 20-step proposal generation pipeline."""
        # 1. Validate context
        if not context or not context.agent_run_id or not context.goal_id:
            raise KnowledgeUpdateContextError("Invalid KnowledgeUpdateContext provided")

        proposal_id = f"prop-knw-{uuid.uuid4().hex[:12]}"
        self._publish_event(
            "KNOWLEDGE_UPDATE_CONTEXT_CREATED", proposal_id, context, {}
        )

        # 2. Extract candidates
        raw_candidates = self.candidate_extractor.extract_candidates(
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
            source_run_id=context.agent_run_id,
            source_goal_id=context.goal_id,
            workflow_id=context.workflow_id,
            iteration_id=context.iteration_id,
        )

        additions: list[KnowledgeAddition] = []
        updates: list[KnowledgeUpdate] = []
        invalidations: list[KnowledgeInvalidation] = []
        relations: list[KnowledgeRelation] = []
        operation_facts: list[OperationFact] = []
        decisions: list[AgentDecisionRecord] = []
        rejected_items: list[RejectedKnowledgeItem] = []
        requires_approval = False
        proposal_reasons: list[str] = []

        base_prov = KnowledgeProvenance(
            source_run_id=context.agent_run_id,
            source_goal_id=context.goal_id,
            workflow_id=context.workflow_id,
            iteration_id=context.iteration_id,
            outcome_evaluation_id=context.outcome_evaluation_id,
        )

        outcome_value = self._normalize_outcome(outcome_eval)

        # 2a. Reject existing knowledge items carrying prohibited internal reasoning
        for existing_item in existing_knowledge or ():
            if not (
                self._contains_internal_reasoning(
                    getattr(existing_item, "content", None)
                )
                or self._contains_internal_reasoning(
                    getattr(existing_item, "metadata", None)
                )
            ):
                continue
            existing_id = getattr(
                existing_item,
                "candidate_id",
                getattr(
                    existing_item,
                    "addition_id",
                    getattr(existing_item, "item_id", "unknown"),
                ),
            )
            existing_kind = getattr(existing_item, "kind", None)
            rejected_items.append(
                RejectedKnowledgeItem(
                    rejection_id=f"rej-{uuid.uuid4().hex[:8]}",
                    candidate_id=existing_id,
                    candidate_kind=existing_kind
                    if isinstance(existing_kind, KnowledgeCandidateKind)
                    else KnowledgeCandidateKind.DECISION,
                    reason_code=KnowledgeRejectionReason.INTERNAL_REASONING,
                    justification="Existing knowledge item contains prohibited internal reasoning fields",
                    raw_summary=str(
                        getattr(
                            existing_item, "title", getattr(existing_item, "topic", "")
                        )
                    ),
                )
            )
            self._publish_event(
                "KNOWLEDGE_CANDIDATE_REJECTED",
                proposal_id,
                context,
                {"candidate_id": existing_id, "reason": "INTERNAL_REASONING"},
            )

        # Process candidates
        for cand in raw_candidates:
            self._publish_event(
                "KNOWLEDGE_CANDIDATE_EXTRACTED",
                proposal_id,
                context,
                {"candidate_id": cand.candidate_id},
            )

            if not self._candidate_allowed_for_outcome(cand.kind, outcome_value):
                rejected_items.append(
                    RejectedKnowledgeItem(
                        rejection_id=f"rej-{uuid.uuid4().hex[:8]}",
                        candidate_id=cand.candidate_id,
                        candidate_kind=cand.kind,
                        reason_code=KnowledgeRejectionReason.INVALIDATED_RESULT,
                        justification=f"Candidate kind '{cand.kind.value}' blocked by outcome gate '{outcome_value}'",
                        raw_summary=cand.title,
                    )
                )
                self._publish_event(
                    "KNOWLEDGE_CANDIDATE_REJECTED",
                    proposal_id,
                    context,
                    {"candidate_id": cand.candidate_id, "reason": "OUTCOME_GATE"},
                )
                continue

            if self._contains_internal_reasoning(
                cand.content
            ) or self._contains_internal_reasoning(cand.metadata):
                rejected_items.append(
                    RejectedKnowledgeItem(
                        rejection_id=f"rej-{uuid.uuid4().hex[:8]}",
                        candidate_id=cand.candidate_id,
                        candidate_kind=cand.kind,
                        reason_code=KnowledgeRejectionReason.INTERNAL_REASONING,
                        justification="Candidate contains prohibited internal reasoning fields",
                        raw_summary=cand.title,
                    )
                )
                self._publish_event(
                    "KNOWLEDGE_CANDIDATE_REJECTED",
                    proposal_id,
                    context,
                    {
                        "candidate_id": cand.candidate_id,
                        "reason": "INTERNAL_REASONING",
                    },
                )
                continue

            # 3. Evaluate relevance
            rel_assessment = self.relevance_evaluator.evaluate_relevance(cand)
            self._publish_event(
                "KNOWLEDGE_RELEVANCE_EVALUATED",
                proposal_id,
                context,
                {"relevant": rel_assessment.relevant},
            )
            if not rel_assessment.relevant:
                rejected_items.append(
                    RejectedKnowledgeItem(
                        rejection_id=f"rej-{uuid.uuid4().hex[:8]}",
                        candidate_id=cand.candidate_id,
                        candidate_kind=cand.kind,
                        reason_code=KnowledgeRejectionReason.TEMPORARY_LOW_UTILITY,
                        justification="Evaluated as low future utility or trivial attempt",
                        raw_summary=cand.title,
                    )
                )
                self._publish_event(
                    "KNOWLEDGE_CANDIDATE_REJECTED",
                    proposal_id,
                    context,
                    {
                        "candidate_id": cand.candidate_id,
                        "reason": "TEMPORARY_LOW_UTILITY",
                    },
                )
                continue

            # 4. Evaluate confidence
            conf_assessment = self.confidence_evaluator.evaluate_confidence(cand)
            self._publish_event(
                "KNOWLEDGE_CONFIDENCE_EVALUATED",
                proposal_id,
                context,
                {"score": conf_assessment.confidence_score},
            )
            if conf_assessment.confidence_score < 0.5:
                rejected_items.append(
                    RejectedKnowledgeItem(
                        rejection_id=f"rej-{uuid.uuid4().hex[:8]}",
                        candidate_id=cand.candidate_id,
                        candidate_kind=cand.kind,
                        reason_code=KnowledgeRejectionReason.LOW_CONFIDENCE,
                        justification=f"Confidence score {conf_assessment.confidence_score} below minimum threshold 0.5",
                        raw_summary=cand.title,
                    )
                )
                self._publish_event(
                    "KNOWLEDGE_CANDIDATE_REJECTED",
                    proposal_id,
                    context,
                    {"candidate_id": cand.candidate_id, "reason": "LOW_CONFIDENCE"},
                )
                continue

            # 5. Classify sensitivity
            sens_assessment = self.sensitivity_policy.evaluate_candidate(cand)
            self._publish_event(
                "KNOWLEDGE_SENSITIVITY_EVALUATED",
                proposal_id,
                context,
                {"level": sens_assessment.level.value},
            )
            if sens_assessment.contains_secrets:
                rejected_items.append(
                    RejectedKnowledgeItem(
                        rejection_id=f"rej-{uuid.uuid4().hex[:8]}",
                        candidate_id=cand.candidate_id,
                        candidate_kind=cand.kind,
                        reason_code=KnowledgeRejectionReason.SECRET,
                        justification="Contains secret key, password, or token pattern",
                        raw_summary=cand.title,
                    )
                )
                self._publish_event(
                    "KNOWLEDGE_CANDIDATE_REJECTED",
                    proposal_id,
                    context,
                    {"candidate_id": cand.candidate_id, "reason": "SECRET"},
                )
                continue

            # 6. Check permissions
            self._publish_event(
                "KNOWLEDGE_PERMISSION_CHECKED",
                proposal_id,
                context,
                {"candidate_id": cand.candidate_id},
            )

            # 7. Deduplicate
            dedup_res = self.deduplicator.evaluate_candidate(
                cand, existing_items=existing_knowledge
            )
            if (
                dedup_res.is_duplicate
                and dedup_res.action == KnowledgeWriteDecisionKind.REJECT
            ):
                self._publish_event(
                    "KNOWLEDGE_DUPLICATE_DETECTED",
                    proposal_id,
                    context,
                    {"existing_id": dedup_res.existing_item_id},
                )
                rejected_items.append(
                    RejectedKnowledgeItem(
                        rejection_id=f"rej-{uuid.uuid4().hex[:8]}",
                        candidate_id=cand.candidate_id,
                        candidate_kind=cand.kind,
                        reason_code=KnowledgeRejectionReason.DUPLICATE,
                        justification=f"Duplicate of existing knowledge item {dedup_res.existing_item_id}",
                        raw_summary=cand.title,
                    )
                )
                self._publish_event(
                    "KNOWLEDGE_CANDIDATE_REJECTED",
                    proposal_id,
                    context,
                    {"candidate_id": cand.candidate_id, "reason": "DUPLICATE"},
                )
                continue

            # 8. Detect contradictions
            contra_res = self.contradiction_resolver.resolve_contradiction(
                cand, existing_items=existing_knowledge
            )
            if contra_res.conflict_detected:
                self._publish_event(
                    "KNOWLEDGE_CONTRADICTION_DETECTED",
                    proposal_id,
                    context,
                    {"target_id": contra_res.target_item_id},
                )
                if contra_res.requires_human_review:
                    requires_approval = True
                    proposal_reasons.append(
                        f"Contradiction detected for candidate '{cand.title}' requiring human review"
                    )

            # 9-12. Generate Additions / Updates / Invalidations / Relations
            write_action = self.knowledge_policy.evaluate_candidate(
                cand,
                relevance_relevant=rel_assessment.relevant,
                confidence_level=conf_assessment.level.value,
                sensitivity_level=sens_assessment.level.value,
                dedup_action=dedup_res.action,
                contradiction_strategy=contra_res.resolution_strategy,
                granted_permissions=context.permissions,
            )

            if write_action == KnowledgeWriteDecisionKind.REQUIRE_APPROVAL:
                requires_approval = True
                proposal_reasons.append(
                    f"Candidate '{cand.title}' requires approval (sensitivity or policy rule)"
                )

            if write_action == KnowledgeWriteDecisionKind.ADD:
                additions.append(
                    KnowledgeAddition(
                        addition_id=f"add-{uuid.uuid4().hex[:8]}",
                        candidate_id=cand.candidate_id,
                        topic=cand.title,
                        content=cand.content,
                        provenance=cand.provenance,
                        confidence=conf_assessment.confidence_score,
                        sensitivity_level=sens_assessment.level,
                        permissions=context.permissions,
                    )
                )
            elif (
                write_action == KnowledgeWriteDecisionKind.UPDATE
                and dedup_res.existing_item_id
            ):
                _, existing_version, previous_version_id, previous_provenance = (
                    self._resolve_existing_version(
                        existing_knowledge, dedup_res.existing_item_id
                    )
                )

                updates.append(
                    KnowledgeUpdate(
                        update_id=f"upd-{uuid.uuid4().hex[:8]}",
                        target_item_id=dedup_res.existing_item_id,
                        candidate_id=cand.candidate_id,
                        updated_fields=cand.content,
                        version_ref=KnowledgeVersionReference(
                            item_id=dedup_res.existing_item_id,
                            version=existing_version,
                            previous_version_id=previous_version_id,
                        ),
                        provenance=cand.provenance,
                        confidence=conf_assessment.confidence_score,
                        metadata={
                            "previous_provenance_fingerprint": previous_provenance,
                        },
                    )
                )
            elif (
                write_action == KnowledgeWriteDecisionKind.MERGE
                and dedup_res.existing_item_id
            ):
                (
                    existing_item,
                    existing_version,
                    previous_version_id,
                    previous_provenance,
                ) = self._resolve_existing_version(
                    existing_knowledge, dedup_res.existing_item_id
                )
                existing_provenance_obj = (
                    getattr(existing_item, "provenance", None)
                    if existing_item is not None
                    else None
                )
                existing_confidence = (
                    getattr(
                        existing_item, "confidence", conf_assessment.confidence_score
                    )
                    if existing_item is not None
                    else conf_assessment.confidence_score
                )
                existing_top_level_evidence = (
                    tuple(getattr(existing_item, "evidence_ids", ()))
                    if existing_item is not None
                    else ()
                )
                existing_provenance_evidence = tuple(
                    getattr(existing_provenance_obj, "evidence_ids", ())
                )
                combined_evidence_ids = tuple(
                    dict.fromkeys(
                        (
                            *cand.evidence_ids,
                            *existing_top_level_evidence,
                            *existing_provenance_evidence,
                        )
                    )
                )
                merged_provenance = KnowledgeProvenance(
                    source_run_id=cand.provenance.source_run_id,
                    source_goal_id=cand.provenance.source_goal_id,
                    workflow_id=cand.provenance.workflow_id,
                    iteration_id=cand.provenance.iteration_id,
                    outcome_evaluation_id=cand.provenance.outcome_evaluation_id,
                    evidence_ids=combined_evidence_ids,
                    source_reliability=min(
                        cand.provenance.source_reliability,
                        getattr(existing_provenance_obj, "source_reliability", 1.0),
                    ),
                )

                updates.append(
                    KnowledgeUpdate(
                        update_id=f"upd-merge-{uuid.uuid4().hex[:8]}",
                        target_item_id=dedup_res.existing_item_id,
                        candidate_id=cand.candidate_id,
                        updated_fields=dedup_res.merged_content or cand.content,
                        version_ref=KnowledgeVersionReference(
                            item_id=dedup_res.existing_item_id,
                            version=existing_version,
                            previous_version_id=previous_version_id,
                        ),
                        provenance=merged_provenance,
                        confidence=min(
                            conf_assessment.confidence_score, existing_confidence
                        ),
                        metadata={
                            "operation": "merge",
                            "merge_reason": ", ".join(dedup_res.reasons)
                            or "COMPLEMENTARY_NON_CONFLICTING_FIELDS",
                            "previous_provenance_fingerprint": previous_provenance,
                        },
                    )
                )
            elif (
                write_action == KnowledgeWriteDecisionKind.INVALIDATE
                and contra_res.target_item_id
            ):
                invalidations.append(
                    KnowledgeInvalidation(
                        invalidation_id=f"inv-{uuid.uuid4().hex[:8]}",
                        target_item_id=contra_res.target_item_id,
                        reason=contra_res.invalidation_reason
                        or "Superseded by new validated candidate",
                        provenance=cand.provenance,
                        superseded_by_item_id=cand.candidate_id,
                    )
                )
            elif write_action == KnowledgeWriteDecisionKind.LINK:
                dependency_items = []
                if isinstance(cand.content, dict):
                    raw_dependencies = cand.content.get("dependencies", [])
                    if isinstance(raw_dependencies, list):
                        dependency_items = [str(dep) for dep in raw_dependencies if dep]
                if not dependency_items:
                    dependency_items = [cand.candidate_id]
                for dep in dependency_items:
                    relations.append(
                        KnowledgeRelation(
                            relation_id=f"rel-{uuid.uuid4().hex[:8]}",
                            source_item_id=cand.candidate_id,
                            target_item_id=dep,
                            relation_type="depends_on",
                            provenance=cand.provenance,
                        )
                    )
            elif write_action == KnowledgeWriteDecisionKind.REJECT:
                # A candidate that reaches this point (relevance/confidence/secrecy
                # already passed) can still be blocked by the permission policy or a
                # dedup rule that resolves to REJECT outside the earlier duplicate
                # check. It must never vanish without an explicit audit record.
                rejected_items.append(
                    RejectedKnowledgeItem(
                        rejection_id=f"rej-{uuid.uuid4().hex[:8]}",
                        candidate_id=cand.candidate_id,
                        candidate_kind=cand.kind,
                        reason_code=KnowledgeRejectionReason.OUTSIDE_PERMISSION,
                        justification="Candidate blocked by permission policy or deduplication rule",
                        raw_summary=cand.title,
                    )
                )
                self._publish_event(
                    "KNOWLEDGE_CANDIDATE_REJECTED",
                    proposal_id,
                    context,
                    {"candidate_id": cand.candidate_id, "reason": "REJECTED_BY_POLICY"},
                )

        # 13. Extract operation facts
        if operation_results and outcome_value in (
            Outcome.SUCCESS.value,
            Outcome.PARTIAL_SUCCESS.value,
        ):
            for op in operation_results:
                summary = str(
                    getattr(op, "summary", getattr(op, "operation_type", "op"))
                )
                success = bool(
                    getattr(
                        op,
                        "success",
                        getattr(op, "status", "") in ("success", "completed"),
                    )
                )
                if outcome_value == Outcome.PARTIAL_SUCCESS.value and not success:
                    continue
                operation_facts.append(
                    OperationFact(
                        fact_id=f"fact-op-{uuid.uuid4().hex[:8]}",
                        operation_type=str(getattr(op, "operation_type", "operation")),
                        target=str(getattr(op, "target", "system")),
                        summary=summary,
                        success=success,
                        evidence_ids=(str(getattr(op, "execution_id", "op-1")),),
                        provenance=base_prov,
                    )
                )

        # 14. Register decisions
        if completion_decision is not None:
            decisions.append(
                AgentDecisionRecord(
                    decision_record_id=f"dec-rec-{uuid.uuid4().hex[:8]}",
                    decision_type="goal_completion",
                    context_summary=f"Completion decision for goal {context.goal_id}",
                    rationale_summary=getattr(
                        completion_decision, "rationale", "Goal evaluation finished"
                    ),
                    selected_option=getattr(
                        completion_decision, "decision_kind", "complete"
                    ),
                    confidence=getattr(completion_decision, "confidence", 1.0),
                    provenance=base_prov,
                )
            )

        # 15. Extract lessons
        lessons = self.lesson_extractor.extract_lessons(
            outcome_eval=outcome_eval,
            completion_decision=completion_decision,
            recovery_history=recovery_history,
            operation_results=operation_results,
            validations=validations,
            user_confirmed_preferences=user_confirmed_preferences,
            source_run_id=context.agent_run_id,
            source_goal_id=context.goal_id,
        )
        lessons = tuple(
            lesson
            for lesson in lessons
            if self._lesson_allowed_for_outcome(lesson.kind.value, outcome_value)
        )

        overall_confidence = 0.9 if additions or lessons else 1.0

        overall_sens = KnowledgeSensitivityAssessment(
            assessment_id=f"sens-prop-{uuid.uuid4().hex[:8]}",
            level=KnowledgeSensitivityLevel.RESTRICTED
            if requires_approval
            else KnowledgeSensitivityLevel.PUBLIC,
            contains_secrets=False,
            contains_personal_data=False,
            contains_credentials=False,
            requires_redaction=False,
        )

        proposal = AgentKnowledgeUpdateProposal(
            proposal_id=proposal_id,
            agent_run_id=context.agent_run_id,
            goal_id=context.goal_id,
            workflow_id=context.workflow_id,
            iteration_id=context.iteration_id,
            outcome_evaluation_id=context.outcome_evaluation_id,
            completion_decision_id=context.completion_decision_id,
            additions=tuple(additions),
            updates=tuple(updates),
            invalidations=tuple(invalidations),
            relations=tuple(relations),
            operation_facts=tuple(operation_facts),
            decisions=tuple(decisions),
            lessons=tuple(lessons),
            rejected_items=tuple(rejected_items),
            requires_approval=requires_approval,
            confidence=overall_confidence,
            reasons=tuple(proposal_reasons),
            source_evidence_ids=(),
            validation_result_ids=(),
            permissions=context.permissions,
            sensitivity=overall_sens,
        )

        # 19. Persist proposal in repository
        self.repository.save_proposal(proposal)

        # 20. Emit events
        self._publish_event(
            "KNOWLEDGE_UPDATE_PROPOSAL_CREATED",
            proposal_id,
            context,
            {"requires_approval": requires_approval},
        )
        if requires_approval:
            self._publish_event(
                "KNOWLEDGE_UPDATE_APPROVAL_REQUESTED", proposal_id, context, {}
            )

        return proposal
