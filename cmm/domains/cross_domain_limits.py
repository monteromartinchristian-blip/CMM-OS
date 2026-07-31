"""Phase 10.9 – Cross-Domain Limit Tracker.

Tracks consumption against the limits declared on a ``CrossDomainRequest``
and ``CrossDomainPolicy``, and reports which limits (if any) have been
reached. Reaching a limit is never raised as an exception — it becomes a
deterministic, orderable entry in ``CrossDomainLimits.reached_limits``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from cmm.domains.cross_domain_contracts import (
    REACHED_LIMIT_ORDER,
    CrossDomainLimits,
    CrossDomainPolicy,
    CrossDomainRequest,
)
from cmm.domains.errors import CrossDomainConfigurationError


class CrossDomainLimitTracker:
    """Mutable counter of consumed limits, evaluated against a fixed request/policy."""

    def __init__(
        self,
        *,
        request: CrossDomainRequest,
        policy: CrossDomainPolicy,
        clock: Callable[[], datetime],
    ) -> None:
        if not isinstance(request, CrossDomainRequest):
            raise CrossDomainConfigurationError(
                "request must be a CrossDomainRequest", field="request"
            )
        if not isinstance(policy, CrossDomainPolicy):
            raise CrossDomainConfigurationError(
                "policy must be a CrossDomainPolicy", field="policy"
            )
        self._request = request
        self._policy = policy
        self._clock = clock

        start = clock()
        if not isinstance(start, datetime) or start.tzinfo is None:
            raise CrossDomainConfigurationError(
                "clock must return a timezone-aware datetime", field="clock"
            )
        self._start = start

        self._domains_used = 0
        self._domain_hops_used = 0
        self._iterations_used = 0
        self._questions_used = 0
        self._operations_used = 0
        self._external_calls_used = 0
        self._estimated_cost = 0.0
        self._parallel_group_size_exceeded = False
        self._explicit_reached_limits: set[str] = set()

    # ── Recording consumption ───────────────────────────────────────────────

    def record_domain(self) -> None:
        """Record that one more domain has entered execution."""
        self._domains_used += 1

    def record_hop(self) -> None:
        """Record that one context transfer (hop) has occurred."""
        self._domain_hops_used += 1

    def record_iteration(self) -> None:
        """Record that one coordination-loop iteration has completed."""
        self._iterations_used += 1

    def record_question(self) -> None:
        """Record that one distinct cross-domain question was raised."""
        self._questions_used += 1

    def record_operations(self, count: int) -> None:
        """Record that ``count`` operations were coordinated."""
        self._operations_used += count

    def record_external_calls(self, count: int) -> None:
        """Record that ``count`` external calls were made."""
        self._external_calls_used += count

    def record_cost(self, amount: float) -> None:
        """Record additional estimated cost."""
        self._estimated_cost += amount

    # ── Elapsed time ─────────────────────────────────────────────────────────

    def elapsed_ms(self) -> int:
        """Milliseconds elapsed since tracker construction, per the injected clock."""
        now = self._clock()
        delta = now - self._start
        return max(0, int(delta.total_seconds() * 1000))

    # ── Capacity checks (before consuming) ──────────────────────────────────

    def has_capacity_for_domain(self) -> bool:
        """Whether one more domain can enter execution."""
        return self._domains_used < self._request.maximum_domains

    def has_capacity_for_hop(self) -> bool:
        """Whether one more context transfer can occur."""
        return self._domain_hops_used < self._request.maximum_domain_hops

    def has_capacity_for_iteration(self) -> bool:
        """Whether one more coordination-loop iteration can run."""
        return self._iterations_used < self._request.maximum_iterations

    def has_capacity_for_question(self) -> bool:
        """Whether one more distinct question can be raised."""
        return self._questions_used < self._request.maximum_questions

    def has_capacity_for_operations(self, count: int = 1) -> bool:
        """Whether ``count`` more operations can be coordinated."""
        return self._operations_used + count <= self._request.maximum_operations

    def remaining_operations(self) -> int:
        """How many more operations can still be coordinated (never negative)."""
        return max(0, self._request.maximum_operations - self._operations_used)

    def has_capacity_for_external_calls(self, count: int = 1) -> bool:
        """Whether ``count`` more external calls can be made."""
        return (
            "external_calls" not in self._explicit_reached_limits
            and self._external_calls_used + count
            <= self._request.maximum_external_calls
        )

    def remaining_external_calls(self) -> int:
        """How many external calls can still be accepted (never negative)."""
        return max(0, self._request.maximum_external_calls - self._external_calls_used)

    def has_capacity_for_cost(self, amount: float = 0.0) -> bool:
        """Whether ``amount`` more estimated cost can be incurred."""
        if "cost" in self._explicit_reached_limits:
            return False
        if self._request.maximum_cost is None:
            return True
        if amount > 0:
            return (self._estimated_cost + amount) <= self._request.maximum_cost
        return self._estimated_cost < self._request.maximum_cost

    def remaining_cost(self) -> float | None:
        """How much estimated cost can still be accepted, or ``None`` if unbounded."""
        if self._request.maximum_cost is None:
            return None
        return max(0.0, self._request.maximum_cost - self._estimated_cost)

    def can_accept_usage(
        self,
        *,
        external_calls: int,
        estimated_cost: float | None,
    ) -> bool:
        """Whether a complete port result can be accepted without exceeding limits."""
        return self.has_capacity_for_external_calls(external_calls) and (
            estimated_cost is None or self.has_capacity_for_cost(estimated_cost)
        )

    def has_time_remaining(self) -> bool:
        """Whether the execution is still within its maximum duration."""
        remaining = self.elapsed_ms() < self._request.maximum_duration_ms
        if not remaining:
            self._explicit_reached_limits.add("duration")
        return remaining

    def parallel_group_size_allowed(self, size: int) -> bool:
        """Whether a declarative parallel group of ``size`` respects policy."""
        return size <= self._policy.maximum_parallel_group_size

    def record_parallel_group_violation(self) -> None:
        """Record that a declarative parallel group exceeded policy's maximum size."""
        self._parallel_group_size_exceeded = True

    def mark_reached(self, limit: str) -> None:
        """Record a detected limit without modifying its consumption counter."""
        if limit not in REACHED_LIMIT_ORDER:
            raise ValueError(f"unknown limit: {limit}")
        self._explicit_reached_limits.add(limit)

    # ── Reached limits ───────────────────────────────────────────────────────

    def reached_limits(self) -> tuple[str, ...]:
        """The names of every limit currently at or beyond its maximum, ordered."""
        reached: list[str] = []
        if (
            self._domains_used >= self._request.maximum_domains
            or "domains" in self._explicit_reached_limits
        ):
            reached.append("domains")
        if (
            self._domain_hops_used >= self._request.maximum_domain_hops
            or "domain_hops" in self._explicit_reached_limits
        ):
            reached.append("domain_hops")
        if (
            self._iterations_used >= self._request.maximum_iterations
            or "iterations" in self._explicit_reached_limits
        ):
            reached.append("iterations")
        if (
            self._questions_used >= self._request.maximum_questions
            or "questions" in self._explicit_reached_limits
        ):
            reached.append("questions")
        if (
            self._operations_used >= self._request.maximum_operations
            or "operations" in self._explicit_reached_limits
        ):
            reached.append("operations")
        if (
            self._external_calls_used >= self._request.maximum_external_calls
            or "external_calls" in self._explicit_reached_limits
        ):
            reached.append("external_calls")
        if self._request.maximum_cost is not None and (
            self._estimated_cost >= self._request.maximum_cost
            or "cost" in self._explicit_reached_limits
        ):
            reached.append("cost")
        if (
            self.elapsed_ms() >= self._request.maximum_duration_ms
            or "duration" in self._explicit_reached_limits
        ):
            reached.append("duration")
        if (
            self._parallel_group_size_exceeded
            or "parallel_group_size" in self._explicit_reached_limits
        ):
            reached.append("parallel_group_size")
        rank = {name: i for i, name in enumerate(REACHED_LIMIT_ORDER)}
        return tuple(
            sorted(reached, key=lambda v: rank.get(v, len(REACHED_LIMIT_ORDER)))
        )

    def snapshot(self) -> CrossDomainLimits:
        """Produce an immutable ``CrossDomainLimits`` snapshot of current usage."""
        return CrossDomainLimits(
            domains_used=self._domains_used,
            domain_hops_used=self._domain_hops_used,
            iterations_used=self._iterations_used,
            questions_used=self._questions_used,
            operations_used=self._operations_used,
            external_calls_used=self._external_calls_used,
            estimated_cost=self._estimated_cost,
            elapsed_ms=self.elapsed_ms(),
            reached_limits=self.reached_limits(),
        )


__all__ = ["CrossDomainLimitTracker"]
