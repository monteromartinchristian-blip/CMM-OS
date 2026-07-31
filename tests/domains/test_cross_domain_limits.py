"""Phase 10.9 – Tests for CrossDomainLimitTracker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cmm.domains.cross_domain_contracts import CrossDomainPolicy, CrossDomainRequest
from cmm.domains.cross_domain_limits import CrossDomainLimitTracker
from cmm.domains.errors import CrossDomainConfigurationError

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)


def _tracker(**overrides) -> CrossDomainLimitTracker:
    req = CrossDomainRequest(
        id="r1",
        objective="obj",
        primary_domain="domain:health",
        maximum_domains=2,
        maximum_domain_hops=2,
        maximum_iterations=2,
        maximum_questions=2,
        maximum_operations=2,
        maximum_external_calls=2,
        maximum_cost=10.0,
        maximum_duration_ms=1000,
        **overrides,
    )
    return CrossDomainLimitTracker(
        request=req, policy=CrossDomainPolicy(), clock=lambda: NOW
    )


class TestConstruction:
    def test_requires_request_type(self) -> None:
        with pytest.raises(CrossDomainConfigurationError):
            CrossDomainLimitTracker(
                request=object(), policy=CrossDomainPolicy(), clock=lambda: NOW
            )

    def test_requires_aware_clock(self) -> None:
        req = CrossDomainRequest(
            id="r1", objective="obj", primary_domain="domain:health"
        )
        with pytest.raises(CrossDomainConfigurationError):
            CrossDomainLimitTracker(
                request=req,
                policy=CrossDomainPolicy(),
                clock=lambda: datetime.fromisoformat("2026-01-01T00:00:00"),
            )


class TestEachLimit:
    def test_domains(self) -> None:
        t = _tracker()
        assert t.has_capacity_for_domain()
        t.record_domain()
        t.record_domain()
        assert not t.has_capacity_for_domain()
        assert "domains" in t.reached_limits()

    def test_domain_hops(self) -> None:
        t = _tracker()
        t.record_hop()
        t.record_hop()
        assert "domain_hops" in t.reached_limits()

    def test_iterations(self) -> None:
        t = _tracker()
        t.record_iteration()
        t.record_iteration()
        assert "iterations" in t.reached_limits()

    def test_questions(self) -> None:
        t = _tracker()
        t.record_question()
        t.record_question()
        assert "questions" in t.reached_limits()

    def test_operations(self) -> None:
        t = _tracker()
        assert t.has_capacity_for_operations(2)
        t.record_operations(2)
        assert not t.has_capacity_for_operations(1)
        assert "operations" in t.reached_limits()

    def test_external_calls(self) -> None:
        t = _tracker()
        t.record_external_calls(2)
        assert "external_calls" in t.reached_limits()

    def test_cost(self) -> None:
        t = _tracker()
        assert t.has_capacity_for_cost(5.0)
        t.record_cost(10.0)
        assert "cost" in t.reached_limits()

    def test_cost_unbounded_when_none(self) -> None:
        req = CrossDomainRequest(
            id="r1", objective="obj", primary_domain="domain:health"
        )
        t = CrossDomainLimitTracker(
            request=req, policy=CrossDomainPolicy(), clock=lambda: NOW
        )
        assert t.has_capacity_for_cost(1_000_000.0)

    def test_duration(self) -> None:
        clock_values = iter([NOW, NOW + timedelta(seconds=2)])
        req = CrossDomainRequest(
            id="r1",
            objective="obj",
            primary_domain="domain:health",
            maximum_duration_ms=1000,
        )
        t = CrossDomainLimitTracker(
            request=req, policy=CrossDomainPolicy(), clock=lambda: next(clock_values)
        )
        assert "duration" in t.reached_limits()

    def test_parallel_group_size(self) -> None:
        req = CrossDomainRequest(
            id="r1", objective="obj", primary_domain="domain:health"
        )
        t = CrossDomainLimitTracker(
            request=req,
            policy=CrossDomainPolicy(maximum_parallel_group_size=2),
            clock=lambda: NOW,
        )
        assert t.parallel_group_size_allowed(2)
        assert not t.parallel_group_size_allowed(3)


class TestDeterministicOrder:
    def test_reached_limits_canonical_order(self) -> None:
        t = _tracker()
        t.record_domain()
        t.record_domain()
        t.record_external_calls(2)
        t.record_cost(10.0)
        reached = t.reached_limits()
        assert reached == ("domains", "external_calls", "cost")


class TestNeverFailsOnLimit:
    def test_reaching_limit_returns_normally(self) -> None:
        t = _tracker()
        t.record_domain()
        t.record_domain()
        # No exception raised; snapshot reflects the reached limit.
        snapshot = t.snapshot()
        assert "domains" in snapshot.reached_limits

    def test_mark_reached_does_not_increment_counters(self) -> None:
        t = _tracker()
        t.mark_reached("external_calls")
        t.mark_reached("cost")
        assert t.remaining_external_calls() == 2
        assert t.remaining_cost() == 10.0
        assert t.snapshot().external_calls_used == 0
        assert t.snapshot().estimated_cost == 0.0
        assert t.reached_limits() == ("external_calls", "cost")

    def test_can_accept_usage_requires_complete_result_budget(self) -> None:
        t = _tracker()
        assert t.remaining_external_calls() == 2
        assert t.remaining_cost() == 10.0
        assert t.can_accept_usage(external_calls=2, estimated_cost=10.0)
        assert not t.can_accept_usage(external_calls=3, estimated_cost=0.0)
        assert not t.can_accept_usage(external_calls=0, estimated_cost=11.0)


class TestSnapshot:
    def test_snapshot_matches_usage(self) -> None:
        t = _tracker()
        t.record_domain()
        t.record_hop()
        t.record_cost(3.0)
        snap = t.snapshot()
        assert snap.domains_used == 1
        assert snap.domain_hops_used == 1
        assert snap.estimated_cost == 3.0
