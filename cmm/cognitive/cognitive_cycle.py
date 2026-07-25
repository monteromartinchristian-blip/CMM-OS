"""Phase 8.15 – Cognitive Cycle Engine.

Orchestrates the end-to-end cognitive cycle across Knowledge Retrieval, Contradiction Detection,
Resolution Proposal, Policy Evaluation, Execution, Resolution Memory, and Cognitive Reflection.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any

from cmm.cognitive.cognitive_cycle_contracts import (
    CognitiveCycleRecord,
    CognitiveCycleStatus,
    generate_cognitive_cycle_id,
)
from cmm.cognitive.contracts import utc_now
from cmm.cognitive.contradiction_detection import KnowledgeContradictionDetector
from cmm.cognitive.contradiction_detection_contracts import ContradictionKind
from cmm.cognitive.contradiction_resolution import KnowledgeContradictionResolver
from cmm.cognitive.errors import (
    CognitiveCycleExecutionError,
    InvalidCognitiveCycleError,
)
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.query import KnowledgeQuery
from cmm.cognitive.reflection import CognitiveReflectionEngine
from cmm.cognitive.resolution_executor import ContradictionResolutionExecutor
from cmm.cognitive.resolution_memory import (
    ResolutionMemoryStore,
    memory_from_execution_result,
)
from cmm.cognitive.resolution_policy import ContradictionResolutionPolicyEngine
from cmm.cognitive.resolution_policy_contracts import PolicyDecision
from cmm.cognitive.retrieval import KnowledgeRetriever
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol


class CognitiveCycleEngine:
    """Orchestrator for the end-to-end cognitive cycle in CMM OS."""

    def __init__(
        self,
        store: KnowledgeStoreProtocol,
        retriever: KnowledgeRetriever,
        contradiction_detector: KnowledgeContradictionDetector,
        contradiction_resolver: KnowledgeContradictionResolver,
        policy_engine: ContradictionResolutionPolicyEngine,
        executor: ContradictionResolutionExecutor,
        memory_store: ResolutionMemoryStore,
        reflection_engine: CognitiveReflectionEngine,
    ) -> None:
        if store is None or not hasattr(store, "list_items"):
            raise InvalidCognitiveCycleError(
                "store must be a valid KnowledgeStoreProtocol instance"
            )
        if retriever is None or not hasattr(retriever, "get_items"):
            raise InvalidCognitiveCycleError(
                "retriever must be a valid KnowledgeRetriever instance"
            )
        if contradiction_detector is None or not hasattr(
            contradiction_detector, "compare"
        ):
            raise InvalidCognitiveCycleError(
                "contradiction_detector must be a valid KnowledgeContradictionDetector instance"
            )
        if contradiction_resolver is None or not hasattr(
            contradiction_resolver, "propose_resolutions"
        ):
            raise InvalidCognitiveCycleError(
                "contradiction_resolver must be a valid KnowledgeContradictionResolver instance"
            )
        if policy_engine is None or not hasattr(policy_engine, "evaluate"):
            raise InvalidCognitiveCycleError(
                "policy_engine must be a valid ContradictionResolutionPolicyEngine instance"
            )
        if executor is None or not hasattr(executor, "execute"):
            raise InvalidCognitiveCycleError(
                "executor must be a valid ContradictionResolutionExecutor instance"
            )
        if memory_store is None or not hasattr(memory_store, "save"):
            raise InvalidCognitiveCycleError(
                "memory_store must be a valid ResolutionMemoryStore instance"
            )
        if reflection_engine is None or not hasattr(reflection_engine, "reflect"):
            raise InvalidCognitiveCycleError(
                "reflection_engine must be a valid CognitiveReflectionEngine instance"
            )

        self._store = store
        self._retriever = retriever
        self._contradiction_detector = contradiction_detector
        self._contradiction_resolver = contradiction_resolver
        self._policy_engine = policy_engine
        self._executor = executor
        self._memory_store = memory_store
        self._reflection_engine = reflection_engine

    def run_cycle(
        self,
        item_ids: Sequence[str] | Iterable[str] | None = None,
        query: KnowledgeQuery | None = None,
        *,
        actor_id: str | None = None,
        created_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CognitiveCycleRecord:
        """Run a full, end-to-end cognitive cycle over target KnowledgeItems."""
        start_time = created_at or utc_now()
        if start_time.tzinfo is None:
            raise InvalidCognitiveCycleError("created_at must be timezone-aware")

        # ── Step 1 & 2: Retrieval ───────────────────────────────────────────
        try:
            if item_ids is not None:
                items = self._retriever.get_items(item_ids, ignore_missing=False)
            elif query is not None:
                items = self._retriever.query(query).items
            else:
                items = tuple(self._store.list_items(limit=None))

            if not items:
                raise InvalidCognitiveCycleError(
                    "No KnowledgeItems retrieved for cognitive cycle"
                )

            input_item_ids = tuple(item.id for item in items)
            init_cycle_id = generate_cognitive_cycle_id(
                input_item_ids=input_item_ids,
                created_at=start_time,
                status=CognitiveCycleStatus.CREATED,
            )

            record = CognitiveCycleRecord(
                cycle_id=init_cycle_id,
                created_at=start_time,
                input_item_ids=input_item_ids,
                contradiction_ids=(),
                resolution_proposal_ids=(),
                execution_ids=(),
                memory_entry_ids=(),
                reflection_report_id=None,
                status=CognitiveCycleStatus.CREATED,
                warnings=(),
                metadata=metadata or {},
            )

            record = replace(record, status=CognitiveCycleStatus.ANALYSING)
        except Exception as exc:
            if isinstance(
                exc, (InvalidCognitiveCycleError, CognitiveCycleExecutionError)
            ):
                raise
            raise CognitiveCycleExecutionError(
                f"Failed during Knowledge Retrieval step: {exc}"
            ) from exc

        try:
            # ── Step 3: Contradiction Detection ───────────────────────────────
            detected_pairs: list[tuple[str, Any, KnowledgeItem, KnowledgeItem]] = []
            n = len(items)
            for i in range(n):
                for j in range(i + 1, n):
                    det = self._contradiction_detector.compare(items[i], items[j])
                    if det.is_contradiction:
                        c_id: str | None = None
                        if det.existing_contradiction_id:
                            c_id = det.existing_contradiction_id
                        elif det.kind and det.kind != ContradictionKind.POSSIBLE:
                            registered = self._contradiction_detector.register(
                                det, actor_id=actor_id
                            )
                            c_id = registered.id

                        if c_id:
                            detected_pairs.append((c_id, det, items[i], items[j]))

            cntr_ids = tuple(sorted({c_id for c_id, _, _, _ in detected_pairs}))
            if cntr_ids:
                record = replace(
                    record,
                    contradiction_ids=cntr_ids,
                    status=CognitiveCycleStatus.CONTRADICTIONS_FOUND,
                )

            # ── Step 4: Resolution Proposals Generation ───────────────────────
            all_proposals = []
            for c_id, det, item_a, item_b in detected_pairs:
                props = self._contradiction_resolver.propose_resolutions(
                    contradiction=det,
                    item_a=item_a,
                    item_b=item_b,
                    actor_id=actor_id,
                    created_at=start_time,
                )
                all_proposals.extend(props)

            proposal_ids = tuple(p.id for p in all_proposals)
            if proposal_ids:
                record = replace(record, resolution_proposal_ids=proposal_ids)

            # ── Step 5: Policy Evaluation ────────────────────────────────────
            evaluations = []
            for prop in all_proposals:
                ev = self._policy_engine.evaluate(prop)
                evaluations.append((prop, ev))

            record = replace(record, status=CognitiveCycleStatus.AWAITING_POLICY)

            # ── Step 6: Execution ────────────────────────────────────────────
            record = replace(record, status=CognitiveCycleStatus.EXECUTING)
            execution_results = []
            for prop, ev in evaluations:
                if ev.allowed is True and ev.decision == PolicyDecision.AUTO_APPROVED:
                    exec_res = self._executor.execute(prop, ev, actor_id=actor_id)
                    execution_results.append((prop, ev, exec_res))

            exec_ids = tuple(res.execution_id for _, _, res in execution_results)
            if exec_ids:
                record = replace(record, execution_ids=exec_ids)

            # ── Step 7: Memory ───────────────────────────────────────────────
            saved_memory_ids = []
            for prop, ev, exec_res in execution_results:
                mem_entry = memory_from_execution_result(
                    execution_result=exec_res,
                    proposal=prop,
                    policy_evaluation=ev,
                )
                saved = self._memory_store.save(mem_entry)
                saved_memory_ids.append(saved.id)

            mem_ids = tuple(saved_memory_ids)
            if mem_ids:
                record = replace(record, memory_entry_ids=mem_ids)

            # ── Step 8: Cognitive Reflection ─────────────────────────────────
            reflection_report = self._reflection_engine.reflect(
                self._memory_store,
                created_at=start_time,
            )
            record = replace(record, reflection_report_id=reflection_report.id)

            # ── Step 9: Final Result ──────────────────────────────────────────
            completed_cycle_id = generate_cognitive_cycle_id(
                input_item_ids=record.input_item_ids,
                created_at=start_time,
                contradiction_ids=record.contradiction_ids,
                resolution_proposal_ids=record.resolution_proposal_ids,
                execution_ids=record.execution_ids,
                status=CognitiveCycleStatus.COMPLETED,
            )

            final_record = replace(
                record,
                cycle_id=completed_cycle_id,
                status=CognitiveCycleStatus.COMPLETED,
            )
            return final_record

        except Exception as exc:
            if isinstance(
                exc, (InvalidCognitiveCycleError, CognitiveCycleExecutionError)
            ):
                raise
            raise CognitiveCycleExecutionError(
                f"Cognitive cycle execution failed at phase {record.status.value}: {exc}"
            ) from exc
