"""Phase 8.14 – Cognitive Reflection Engine Implementation.

Provides deterministic, pure, side-effect-free historical analysis over cognitive decision memory.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from cmm.cognitive.contracts import utc_now
from cmm.cognitive.errors import (
    InvalidReflectionReportError,
    ReflectionAnalysisConflictError,
)
from cmm.cognitive.reflection_contracts import (
    CognitiveReflectionReport,
    ReflectionFinding,
    ReflectionQuery,
    generate_reflection_report_id,
)
from cmm.cognitive.resolution_contracts import ResolutionDecision
from cmm.cognitive.resolution_executor_contracts import ExecutionStatus
from cmm.cognitive.resolution_memory import ResolutionMemoryStore
from cmm.cognitive.resolution_memory_contracts import (
    ResolutionMemoryEntry,
    ResolutionMemoryResult,
)
from cmm.cognitive.resolution_policy_contracts import PolicyDecision


class CognitiveReflectionEngine:
    """Analytical engine for observing, aggregating, and explaining historical cognitive decisions.

    This engine is purely analytical and side-effect free:
    It NEVER writes to memory stores, alters KnowledgeItems, executes resolutions,
    or overrides cognitive policies.
    """

    def reflect(
        self,
        store_or_entries: ResolutionMemoryStore | Sequence[ResolutionMemoryEntry],
        query: ReflectionQuery | None = None,
        created_at: datetime | None = None,
    ) -> CognitiveReflectionReport:
        """Main entry point for generating a cognitive reflection report."""
        entries = self._resolve_entries(store_or_entries, query)
        return self.generate_report(entries, query=query, created_at=created_at)

    def _resolve_entries(
        self,
        store_or_entries: ResolutionMemoryStore | Sequence[ResolutionMemoryEntry],
        query: ReflectionQuery | None,
    ) -> list[ResolutionMemoryEntry]:
        """Extract and filter resolution memory entries."""
        raw_entries: Sequence[ResolutionMemoryEntry] = []

        if isinstance(store_or_entries, Sequence) and not isinstance(
            store_or_entries, (str, bytes)
        ):
            raw_entries = store_or_entries
        elif hasattr(store_or_entries, "list") and callable(store_or_entries.list):
            try:
                result = store_or_entries.list()
                if isinstance(result, ResolutionMemoryResult):
                    raw_entries = result.entries
                elif isinstance(result, Sequence):
                    raw_entries = result
                else:
                    raise ReflectionAnalysisConflictError(
                        f"Unexpected list() result type from memory store: {type(result).__name__}"
                    )
            except Exception as exc:
                if isinstance(
                    exc, (ReflectionAnalysisConflictError, InvalidReflectionReportError)
                ):
                    raise
                raise ReflectionAnalysisConflictError(
                    f"Failed to retrieve entries from memory store: {exc}"
                ) from exc
        else:
            raise InvalidReflectionReportError(
                "store_or_entries must be a ResolutionMemoryStore or a Sequence of ResolutionMemoryEntry"
            )

        filtered: list[ResolutionMemoryEntry] = []
        for entry in raw_entries:
            if not isinstance(entry, ResolutionMemoryEntry):
                raise InvalidReflectionReportError(
                    f"Expected ResolutionMemoryEntry, got {type(entry).__name__}"
                )
            if query is None or query.matches(entry):
                filtered.append(entry)

        return filtered

    def analyse_entries(
        self, entries: Sequence[ResolutionMemoryEntry]
    ) -> dict[str, Any]:
        """Calculate quantitative metrics over resolution memory entries."""
        analysed_count = len(entries)
        if analysed_count == 0:
            return {
                "analysed_entries": 0,
                "contradiction_count": 0,
                "resolution_count": 0,
                "human_review_count": 0,
                "auto_resolution_count": 0,
                "average_confidence": 0.0,
                "decision_distribution": {},
                "contradiction_distribution": {},
                "policy_distribution": {},
            }

        unique_contradiction_ids = {e.contradiction_id for e in entries}
        human_review_count = 0
        auto_resolution_count = 0
        total_confidence = 0.0

        dec_counter: Counter[str] = Counter()
        con_counter: Counter[str] = Counter()
        pol_counter: Counter[str] = Counter()

        for e in entries:
            total_confidence += float(e.confidence)

            # Counts
            if (
                e.policy_decision == PolicyDecision.HUMAN_REVIEW_REQUIRED
                or e.decision == ResolutionDecision.REQUEST_HUMAN_REVIEW
            ):
                human_review_count += 1

            if (
                e.policy_decision == PolicyDecision.AUTO_APPROVED
                or e.execution_status == ExecutionStatus.COMPLETED
            ):
                auto_resolution_count += 1

            # Distributions
            dec_counter[e.decision.value] += 1
            pol_counter[e.policy_decision.value] += 1

            kind = str(e.metadata.get("contradiction_kind", "direct")).strip().lower()
            con_counter[kind] += 1

        avg_confidence = round(total_confidence / analysed_count, 4)

        return {
            "analysed_entries": analysed_count,
            "contradiction_count": len(unique_contradiction_ids),
            "resolution_count": analysed_count,
            "human_review_count": human_review_count,
            "auto_resolution_count": auto_resolution_count,
            "average_confidence": avg_confidence,
            "decision_distribution": dict(dec_counter),
            "contradiction_distribution": dict(con_counter),
            "policy_distribution": dict(pol_counter),
        }

    def find_patterns(
        self, entries: Sequence[ResolutionMemoryEntry], metrics: dict[str, Any]
    ) -> tuple[tuple[ReflectionFinding, ...], tuple[str, ...]]:
        """Discover qualitative patterns, findings, and warnings from decision metrics."""
        findings: list[ReflectionFinding] = []
        warnings: list[str] = []

        analysed_count = metrics.get("analysed_entries", 0)
        if analysed_count == 0:
            return (), ()

        human_reviews = metrics.get("human_review_count", 0)
        avg_confidence = metrics.get("average_confidence", 1.0)
        pol_dist = metrics.get("policy_distribution", {})

        # Rule 1: High Human Review Dependency (> 50%)
        if human_reviews / analysed_count > 0.5:
            related_ids = tuple(
                e.id
                for e in entries
                if e.policy_decision == PolicyDecision.HUMAN_REVIEW_REQUIRED
                or e.decision == ResolutionDecision.REQUEST_HUMAN_REVIEW
            )
            findings.append(
                ReflectionFinding(
                    category="human_dependency",
                    severity="warning",
                    description="High human review dependency detected",
                    related_entry_ids=related_ids,
                    confidence=0.9,
                )
            )
            warnings.append("Over 50% of analyzed resolutions required human review.")

        # Rule 2: Low Confidence Resolution Pattern (< 0.60 average)
        if avg_confidence < 0.6:
            related_ids = tuple(e.id for e in entries if e.confidence < 0.6)
            findings.append(
                ReflectionFinding(
                    category="confidence",
                    severity="warning",
                    description="Low confidence resolution pattern detected",
                    related_entry_ids=related_ids,
                    confidence=round(max(0.1, 1.0 - avg_confidence), 2),
                )
            )
            warnings.append(
                f"Average resolution confidence ({avg_confidence:.2f}) is below threshold 0.60."
            )

        # Rule 3: Recurring Contradiction Pattern
        contradiction_counts: Counter[str] = Counter()
        entry_by_cid: dict[str, list[str]] = {}
        for e in entries:
            contradiction_counts[e.contradiction_id] += 1
            entry_by_cid.setdefault(e.contradiction_id, []).append(e.id)

        recurring_cids = [
            cid for cid, count in contradiction_counts.items() if count > 1
        ]
        if recurring_cids:
            recurring_entry_ids: list[str] = []
            for cid in recurring_cids:
                recurring_entry_ids.extend(entry_by_cid[cid])
            findings.append(
                ReflectionFinding(
                    category="recurrence",
                    severity="warning",
                    description="Recurring contradiction pattern detected",
                    related_entry_ids=tuple(recurring_entry_ids),
                    confidence=0.85,
                )
            )
            warnings.append(
                "Recurring contradiction pattern detected across resolution memory."
            )

        # Rule 4: Policy Blockage Pattern
        rejected_count = pol_dist.get("rejected", 0)
        escalated_count = pol_dist.get("escalate", 0)
        if rejected_count > 0 or escalated_count > 0:
            blocked_ids = tuple(
                e.id
                for e in entries
                if e.policy_decision.value in ("rejected", "escalate")
            )
            findings.append(
                ReflectionFinding(
                    category="policy_blockage",
                    severity="info",
                    description="Policy blockages or escalations observed in decision history",
                    related_entry_ids=blocked_ids,
                    confidence=0.8,
                )
            )

        return tuple(findings), tuple(warnings)

    def generate_report(
        self,
        entries: Sequence[ResolutionMemoryEntry],
        query: ReflectionQuery | None = None,
        created_at: datetime | None = None,
    ) -> CognitiveReflectionReport:
        """Assemble findings and metrics into an immutable CognitiveReflectionReport."""
        ts = created_at or utc_now()
        metrics = self.analyse_entries(entries)
        findings, warnings = self.find_patterns(entries, metrics)

        report_id = generate_reflection_report_id(
            analysed_entries=metrics["analysed_entries"],
            query=query,
            created_at=ts,
            decision_distribution=metrics["decision_distribution"],
            contradiction_distribution=metrics["contradiction_distribution"],
            policy_distribution=metrics["policy_distribution"],
        )

        return CognitiveReflectionReport(
            id=report_id,
            created_at=ts,
            analysed_entries=metrics["analysed_entries"],
            contradiction_count=metrics["contradiction_count"],
            resolution_count=metrics["resolution_count"],
            human_review_count=metrics["human_review_count"],
            auto_resolution_count=metrics["auto_resolution_count"],
            average_confidence=metrics["average_confidence"],
            decision_distribution=metrics["decision_distribution"],
            contradiction_distribution=metrics["contradiction_distribution"],
            policy_distribution=metrics["policy_distribution"],
            findings=findings,
            warnings=warnings,
            metadata={"query": query.serialize() if query else None},
        )
