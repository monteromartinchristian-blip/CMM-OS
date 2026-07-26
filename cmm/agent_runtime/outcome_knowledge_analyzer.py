"""Phase 9.17 – Outcome Knowledge Analyzer.

Analyzes acquired facts, inferences, resolved/new information gaps,
and remaining pending tasks resulting from goal execution.
"""

from __future__ import annotations

import uuid
from typing import Any

from cmm.agent_runtime.outcome_evaluation_contracts import (
    OutcomeEvidence,
    OutcomeGap,
    OutcomeKnowledgeAcquisition,
    OutcomeTaskStatus,
)


class OutcomeKnowledgeAnalyzer:
    """Identifies knowledge acquired, resolved/new gaps, and pending tasks during evaluation."""

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus

    def _publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, payload)
            except Exception:
                pass

    def analyze_knowledge_and_gaps(
        self,
        operation_results: tuple[Any, ...] = (),
        evidence: tuple[OutcomeEvidence, ...] = (),
        existing_gaps: tuple[OutcomeGap, ...] = (),
        tasks: tuple[OutcomeTaskStatus, ...] = (),
    ) -> tuple[
        tuple[OutcomeKnowledgeAcquisition, ...],
        tuple[OutcomeGap, ...],
        tuple[OutcomeTaskStatus, ...],
    ]:
        """Analyze evidence, operation outputs, and task progress to determine acquired knowledge and open gaps."""
        acquired_knowledge: list[OutcomeKnowledgeAcquisition] = []
        remaining_gaps: list[OutcomeGap] = []
        remaining_tasks: list[OutcomeTaskStatus] = list(tasks)

        # 1. Process evidence to identify new facts and inferences
        for ev in evidence:
            if "fact" in ev.description.lower():
                k = OutcomeKnowledgeAcquisition(
                    knowledge_id=f"know-{uuid.uuid4().hex[:8]}",
                    kind="fact",
                    statement=ev.description,
                    confidence=1.0,
                    evidence_ids=(ev.evidence_id,),
                    metadata=dict(ev.metadata),
                )
                acquired_knowledge.append(k)
                self._publish_event("OUTCOME_KNOWLEDGE_ACQUIRED", k.to_dict())

            elif (
                "inference" in ev.description.lower()
                or "deduction" in ev.description.lower()
            ):
                k = OutcomeKnowledgeAcquisition(
                    knowledge_id=f"know-{uuid.uuid4().hex[:8]}",
                    kind="inference",
                    statement=ev.description,
                    confidence=0.85,
                    evidence_ids=(ev.evidence_id,),
                    metadata=dict(ev.metadata),
                )
                acquired_knowledge.append(k)
                self._publish_event("OUTCOME_KNOWLEDGE_ACQUIRED", k.to_dict())

        # 2. Analyze operation outputs for new findings or facts
        for op in operation_results:
            op_data = getattr(op, "output", getattr(op, "result_data", {}))
            if isinstance(op_data, dict):
                findings = op_data.get("findings", [])
                for f in findings:
                    if isinstance(f, str):
                        k = OutcomeKnowledgeAcquisition(
                            knowledge_id=f"know-{uuid.uuid4().hex[:8]}",
                            kind="fact",
                            statement=f,
                            confidence=0.9,
                            metadata={
                                "source_operation": getattr(op, "operation_id", "")
                            },
                        )
                        acquired_knowledge.append(k)
                        self._publish_event("OUTCOME_KNOWLEDGE_ACQUIRED", k.to_dict())

        # 3. Analyze gaps status (resolve existing gaps if evidence acquired)
        acquired_statements = " ".join(k.statement.lower() for k in acquired_knowledge)

        for gap in existing_gaps:
            if not gap.resolved:
                # Check if evidence addresses this gap
                if gap.description.lower() in acquired_statements:
                    resolved_gap = OutcomeGap(
                        gap_id=gap.gap_id,
                        description=gap.description,
                        impact=gap.impact,
                        resolved=True,
                        metadata={**dict(gap.metadata), "resolved_by_evaluation": True},
                    )
                    remaining_gaps.append(resolved_gap)
                else:
                    remaining_gaps.append(gap)
                    self._publish_event("OUTCOME_GAP_IDENTIFIED", gap.to_dict())
            else:
                remaining_gaps.append(gap)

        return tuple(acquired_knowledge), tuple(remaining_gaps), tuple(remaining_tasks)
