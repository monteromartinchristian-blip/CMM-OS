"""Phase 10.9 – Cross-Domain Context Builder.

Accumulates cross-domain execution state (transfers, merged findings,
entities, timelines, questions, dependencies, contradictions, gaps,
partial results, and decisions) and exposes it only as immutable
``CrossDomainContextSnapshot`` instances. Internal state is never exposed
directly — callers can only read a frozen snapshot.

Deduplication always merges provenance (and, for findings/questions,
source/requesting domains) deterministically via
``cmm.domains.cross_domain_aggregation`` — it never keeps only the first
occurrence's provenance.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from cmm.domains.cross_domain_aggregation import (
    merge_two_contradictions,
    merge_two_dependencies,
    merge_two_findings,
    merge_two_gaps,
    merge_two_questions,
)
from cmm.domains.cross_domain_contracts import (
    CrossDomainContextSnapshot,
    CrossDomainContextTransfer,
    CrossDomainContradiction,
    CrossDomainDecision,
    CrossDomainDependency,
    CrossDomainDomainResult,
    CrossDomainFinding,
    CrossDomainGap,
    CrossDomainKnowledgeResult,
    CrossDomainOperationResult,
    CrossDomainQuestion,
    CrossDomainWorkflowResult,
)
from cmm.domains.errors import CrossDomainConfigurationError
from cmm.domains.identifiers import DomainId


def _append_unique_str(existing: list[str], new_items: tuple[str, ...]) -> None:
    """Append strings not already present, preserving first-appearance order."""
    seen = set(existing)
    for item in new_items:
        if item not in seen:
            seen.add(item)
            existing.append(item)


def _append_unique_domain(existing: list[DomainId], new_item: DomainId) -> None:
    """Append a DomainId not already present, preserving first-appearance order."""
    if new_item.slug not in {d.slug for d in existing}:
        existing.append(new_item)


class CrossDomainContextBuilder:
    """Mutable accumulator for cross-domain execution state.

    Every mutation happens through an explicit method; the only way to read
    state back out is :meth:`snapshot`, which returns a frozen,
    deeply-immutable ``CrossDomainContextSnapshot``.
    """

    def __init__(
        self,
        *,
        request_id: str,
        composition_id: str | None,
        clock: Callable[[], datetime],
    ) -> None:
        if not isinstance(request_id, str) or not request_id.strip():
            raise CrossDomainConfigurationError(
                "request_id must be a non-empty string", field="request_id"
            )
        self._request_id = request_id
        self._composition_id = composition_id
        self._clock = clock

        start = clock()
        if not isinstance(start, datetime) or start.tzinfo is None:
            raise CrossDomainConfigurationError(
                "clock must return a timezone-aware datetime", field="clock"
            )
        self._started_at = start

        self._active_domains: list[DomainId] = []
        self._visited_domains: list[DomainId] = []
        self._domain_hops = 0
        self._iteration = 0
        self._shared_entities: list[str] = []
        self._shared_timelines: list[str] = []
        self._shared_findings: list[CrossDomainFinding] = []
        self._open_questions: list[CrossDomainQuestion] = []
        self._answered_questions: list[CrossDomainQuestion] = []
        self._dependencies: list[CrossDomainDependency] = []
        self._contradictions: list[CrossDomainContradiction] = []
        self._gaps: list[CrossDomainGap] = []
        self._partial_results: list[CrossDomainDomainResult] = []
        self._transfers: list[CrossDomainContextTransfer] = []
        self._decisions: list[CrossDomainDecision] = []
        self._consumed_operations = 0
        self._consumed_external_calls = 0
        self._estimated_cost = 0.0

        self._finding_index: dict[str, CrossDomainFinding] = {}
        self._dependency_index: dict[tuple, CrossDomainDependency] = {}
        self._contradiction_index: dict[tuple, CrossDomainContradiction] = {}
        self._gap_index: dict[tuple, CrossDomainGap] = {}
        self._question_index: dict[tuple, CrossDomainQuestion] = {}

    # ── Setup ────────────────────────────────────────────────────────────────

    def set_active_domains(self, domains: tuple[DomainId | str, ...]) -> None:
        """Set the currently active domain set (called once after composition)."""
        self._active_domains = [
            d if isinstance(d, DomainId) else DomainId.from_str(d) for d in domains
        ]

    def set_composition_id(self, composition_id: str | None) -> None:
        """Attach the composition ID once composition has completed."""
        self._composition_id = composition_id

    def mark_visited(self, domain_id: DomainId) -> None:
        """Record that a domain has been visited during this execution."""
        _append_unique_domain(self._visited_domains, domain_id)

    def advance_iteration(self) -> None:
        """Advance the coordination-loop iteration counter."""
        self._iteration += 1

    @property
    def iteration(self) -> int:
        """The current iteration number."""
        return self._iteration

    @property
    def distinct_question_count(self) -> int:
        """The number of structurally-distinct questions recorded so far."""
        return len(self._question_index)

    def question_identity_keys(self) -> frozenset[tuple]:
        """The structural identity keys of every question recorded so far."""
        return frozenset(self._question_index.keys())

    # ── Consumption tracking ─────────────────────────────────────────────────

    def consume_operations(self, count: int) -> None:
        """Record that ``count`` operations were coordinated."""
        self._consumed_operations += count

    def consume_external_calls(self, count: int) -> None:
        """Record that ``count`` external calls were made."""
        self._consumed_external_calls += count

    def add_cost(self, amount: float) -> None:
        """Record additional estimated cost."""
        self._estimated_cost += amount

    def consume_port_usage(
        self, external_calls: int, estimated_cost: float | None
    ) -> None:
        """Reflect accepted port consumption in the execution snapshot."""
        self.consume_external_calls(external_calls)
        if estimated_cost is not None:
            self.add_cost(estimated_cost)

    # ── Findings ─────────────────────────────────────────────────────────────

    def _record_finding(self, finding: CrossDomainFinding) -> None:
        """Merge a finding by identifier, unioning source domains and provenance."""
        existing = self._finding_index.get(finding.identifier)
        merged = finding if existing is None else merge_two_findings(existing, finding)
        self._finding_index[finding.identifier] = merged
        if existing is None:
            self._shared_findings.append(merged)
        else:
            self._shared_findings[self._shared_findings.index(existing)] = merged

    # ── Questions ────────────────────────────────────────────────────────────

    def _record_question(self, question: CrossDomainQuestion) -> None:
        """Merge a question by structural identity, unioning domains and provenance."""
        key = question.identity_key()
        existing = self._question_index.get(key)
        merged = (
            question if existing is None else merge_two_questions(existing, question)
        )
        self._question_index[key] = merged
        if existing is not None:
            if existing in self._open_questions:
                self._open_questions.remove(existing)
            if existing in self._answered_questions:
                self._answered_questions.remove(existing)
        if merged.answered:
            self._answered_questions.append(merged)
        else:
            self._open_questions.append(merged)

    # ── Dependencies / contradictions / gaps ────────────────────────────────

    def _record_dependency(self, dependency: CrossDomainDependency) -> None:
        key = dependency.identity_key()
        existing = self._dependency_index.get(key)
        merged = (
            dependency
            if existing is None
            else merge_two_dependencies(existing, dependency)
        )
        self._dependency_index[key] = merged
        if existing is None:
            self._dependencies.append(merged)
        else:
            self._dependencies[self._dependencies.index(existing)] = merged

    def _record_contradiction(self, contradiction: CrossDomainContradiction) -> None:
        key = contradiction.identity_key()
        existing = self._contradiction_index.get(key)
        merged = (
            contradiction
            if existing is None
            else merge_two_contradictions(existing, contradiction)
        )
        self._contradiction_index[key] = merged
        if existing is None:
            self._contradictions.append(merged)
        else:
            self._contradictions[self._contradictions.index(existing)] = merged

    def _record_gap(self, gap: CrossDomainGap) -> None:
        key = gap.identity_key()
        existing = self._gap_index.get(key)
        merged = gap if existing is None else merge_two_gaps(existing, gap)
        self._gap_index[key] = merged
        if existing is None:
            self._gaps.append(merged)
        else:
            self._gaps[self._gaps.index(existing)] = merged

    # ── Merges ───────────────────────────────────────────────────────────────

    def merge_domain_result(self, result: CrossDomainDomainResult) -> None:
        """Merge a domain's contribution into the shared context.

        The result is always retained in ``partial_results``, regardless of
        its status, so partial work is never silently dropped. Repeated
        results for the same domain are consolidated (not overwritten) at
        final aggregation time.
        """
        self._partial_results.append(result)
        self.consume_port_usage(result.external_calls_used, result.estimated_cost)
        for f in result.findings:
            self._record_finding(f)
        _append_unique_str(self._shared_entities, result.entities)
        _append_unique_str(self._shared_timelines, result.timelines)
        for q in result.questions:
            self._record_question(q)
        for dep in result.dependencies:
            self._record_dependency(dep)
        for c in result.contradictions:
            self._record_contradiction(c)
        for g in result.gaps:
            self._record_gap(g)

    def merge_knowledge_result(self, result: CrossDomainKnowledgeResult) -> None:
        """Merge shared knowledge retrieved through the Knowledge port."""
        for f in result.findings:
            self._record_finding(f)
        _append_unique_str(self._shared_entities, result.entities)
        _append_unique_str(self._shared_timelines, result.timelines)
        for dep in result.dependencies:
            self._record_dependency(dep)
        for c in result.contradictions:
            self._record_contradiction(c)
        for g in result.gaps:
            self._record_gap(g)
        self.consume_external_calls(result.external_calls_used)
        if result.estimated_cost is not None:
            self.add_cost(result.estimated_cost)

    def merge_workflow_result(self, result: CrossDomainWorkflowResult) -> None:
        """Merge findings and blockers produced by coordinating workflows."""
        for f in result.findings:
            self._record_finding(f)
        for dep in result.dependencies:
            self._record_dependency(dep)
        for c in result.contradictions:
            self._record_contradiction(c)
        for g in result.gaps:
            self._record_gap(g)
        self.consume_external_calls(result.external_calls_used)
        if result.estimated_cost is not None:
            self.add_cost(result.estimated_cost)

    def merge_operation_result(self, result: CrossDomainOperationResult) -> None:
        """Merge findings and blockers produced by coordinating operations."""
        for f in result.findings:
            self._record_finding(f)
        for dep in result.dependencies:
            self._record_dependency(dep)
        for c in result.contradictions:
            self._record_contradiction(c)
        for g in result.gaps:
            self._record_gap(g)
        self.consume_external_calls(result.external_calls_used)
        if result.estimated_cost is not None:
            self.add_cost(result.estimated_cost)

    # ── Transfers ────────────────────────────────────────────────────────────

    def add_transfer(self, transfer: CrossDomainContextTransfer) -> bool:
        """Record a context transfer if it satisfies structural eligibility rules.

        Returns ``True`` if the transfer was accepted and recorded, ``False``
        otherwise. Quantity-based limits (hops, iterations) are enforced by
        the caller via ``CrossDomainLimitTracker`` before this is invoked.
        """
        active_slugs = {d.slug for d in self._active_domains}
        if transfer.target_domain.slug not in active_slugs:
            return False
        if transfer.private or not transfer.transferable:
            return False
        self._transfers.append(transfer)
        self._domain_hops += 1
        return True

    # ── Decisions ────────────────────────────────────────────────────────────

    def add_decision(self, decision: CrossDomainDecision) -> None:
        """Record a coordination decision."""
        self._decisions.append(decision)

    # ── Snapshot ─────────────────────────────────────────────────────────────

    def snapshot(self) -> CrossDomainContextSnapshot:
        """Produce an immutable snapshot of the current execution state."""
        return CrossDomainContextSnapshot(
            request_id=self._request_id,
            composition_id=self._composition_id,
            active_domains=tuple(self._active_domains),
            visited_domains=tuple(self._visited_domains),
            domain_hops=self._domain_hops,
            iteration=self._iteration,
            shared_entities=tuple(self._shared_entities),
            shared_timelines=tuple(self._shared_timelines),
            shared_findings=tuple(self._shared_findings),
            open_questions=tuple(self._open_questions),
            answered_questions=tuple(self._answered_questions),
            dependencies=tuple(self._dependencies),
            contradictions=tuple(self._contradictions),
            gaps=tuple(self._gaps),
            partial_results=tuple(self._partial_results),
            transfers=tuple(self._transfers),
            decisions=tuple(self._decisions),
            consumed_operations=self._consumed_operations,
            consumed_external_calls=self._consumed_external_calls,
            estimated_cost=self._estimated_cost,
            started_at=self._started_at,
        )


__all__ = ["CrossDomainContextBuilder"]
