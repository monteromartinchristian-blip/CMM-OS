"""Unit tests for Phase 7.11 — ValidationHistoryQuery and ValidationHistoryPage.

Covers filters, pagination, ordering, limits, offset, status/policy/actor/
branch/temporal/gate/commit filtering.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cmm.validation.observability.history import (
    ValidationHistoryPage,
    ValidationHistoryQuery,
)
from cmm.validation.observability.models import (
    CURRENT_SCHEMA_VERSION,
    ValidationExecutionRecord,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dt(offset_seconds: int = 0) -> datetime:
    return datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(
        seconds=offset_seconds
    )


def _make_record(**kwargs) -> ValidationExecutionRecord:
    defaults: dict = {
        "id": "validation-hist-001",
        "schema_version": CURRENT_SCHEMA_VERSION,
        "status": "passed",
        "completed_at": _now(),
        "started_at": _now(),
    }
    defaults.update(kwargs)
    return ValidationExecutionRecord(**defaults)


# ---------------------------------------------------------------------------
# ValidationHistoryQuery — validation
# ---------------------------------------------------------------------------


def test_query_default_limit() -> None:
    q = ValidationHistoryQuery()
    assert q.limit == 50
    assert q.offset == 0


def test_query_custom_limit() -> None:
    q = ValidationHistoryQuery(limit=10)
    assert q.limit == 10


def test_query_zero_limit_raises() -> None:
    with pytest.raises(ValueError, match="limit must be a positive integer"):
        ValidationHistoryQuery(limit=0)


def test_query_negative_limit_raises() -> None:
    with pytest.raises(ValueError, match="limit must be a positive integer"):
        ValidationHistoryQuery(limit=-1)


def test_query_exceeds_max_raises() -> None:
    with pytest.raises(ValueError, match="limit cannot exceed"):
        ValidationHistoryQuery(limit=999999)


def test_query_negative_offset_raises() -> None:
    with pytest.raises(ValueError, match="offset must be a non-negative integer"):
        ValidationHistoryQuery(offset=-1)


def test_query_zero_offset_ok() -> None:
    q = ValidationHistoryQuery(offset=0)
    assert q.offset == 0


# ---------------------------------------------------------------------------
# ValidationHistoryQuery.matches
# ---------------------------------------------------------------------------


def _rec(
    id: str = "validation-x",
    status: str = "passed",
    policy: str | None = None,
    actor: str | None = None,
    branch: str | None = None,
    started_at: datetime | None = None,
    gate_result: dict | None = None,
    commit_hash: str | None = None,
) -> ValidationExecutionRecord:
    now = _now()
    completed_at = (
        now
        if status in ("passed", "failed", "warning", "error", "cancelled", "timed_out")
        else None
    )
    return ValidationExecutionRecord(
        id=id,
        schema_version=CURRENT_SCHEMA_VERSION,
        status=status,
        policy=policy,
        actor=actor,
        branch=branch,
        started_at=started_at or now,
        completed_at=completed_at,
        gate_result=gate_result,
        commit_hash=commit_hash,
    )


def test_matches_no_filters() -> None:
    q = ValidationHistoryQuery()
    r = _rec()
    assert q.matches(r) is True


def test_matches_status_filter() -> None:
    q = ValidationHistoryQuery(status="passed")
    assert q.matches(_rec(status="passed")) is True
    assert q.matches(_rec(id="v2", status="failed")) is False


def test_matches_policy_filter() -> None:
    q = ValidationHistoryQuery(policy="small_change")
    assert q.matches(_rec(policy="small_change")) is True
    assert q.matches(_rec(policy="full")) is False
    assert q.matches(_rec(policy=None)) is False


def test_matches_actor_filter() -> None:
    q = ValidationHistoryQuery(actor="human:christian")
    assert q.matches(_rec(actor="human:christian")) is True
    assert q.matches(_rec(actor="ci:github")) is False


def test_matches_branch_filter() -> None:
    q = ValidationHistoryQuery(branch="feature/test")
    assert q.matches(_rec(branch="feature/test")) is True
    assert q.matches(_rec(branch="main")) is False


def test_matches_started_after() -> None:
    base = _dt(0)
    q = ValidationHistoryQuery(started_after=base + timedelta(seconds=10))
    # Record started before the cutoff → excluded
    assert q.matches(_rec(started_at=base + timedelta(seconds=5))) is False
    # Record started after → included
    assert q.matches(_rec(started_at=base + timedelta(seconds=20))) is True


def test_matches_started_before() -> None:
    base = _dt(0)
    q = ValidationHistoryQuery(started_before=base + timedelta(seconds=10))
    assert q.matches(_rec(started_at=base + timedelta(seconds=5))) is True
    assert q.matches(_rec(started_at=base + timedelta(seconds=20))) is False


def test_matches_gate_allowed_true() -> None:
    q = ValidationHistoryQuery(gate_allowed=True)
    assert q.matches(_rec(gate_result={"allowed": True})) is True
    assert q.matches(_rec(gate_result={"allowed": False})) is False
    assert q.matches(_rec(gate_result=None)) is False


def test_matches_gate_allowed_false() -> None:
    q = ValidationHistoryQuery(gate_allowed=False)
    assert q.matches(_rec(gate_result={"allowed": False})) is True
    assert q.matches(_rec(gate_result={"allowed": True})) is False


def test_matches_has_commit_true() -> None:
    q = ValidationHistoryQuery(has_commit=True)
    assert q.matches(_rec(commit_hash="abc123")) is True
    assert q.matches(_rec(commit_hash=None)) is False


def test_matches_has_commit_false() -> None:
    q = ValidationHistoryQuery(has_commit=False)
    assert q.matches(_rec(commit_hash=None)) is True
    assert q.matches(_rec(commit_hash="abc123")) is False


# ---------------------------------------------------------------------------
# ValidationHistoryPage
# ---------------------------------------------------------------------------


def test_page_defaults() -> None:
    page = ValidationHistoryPage()
    assert page.items == ()
    assert page.total == 0
    assert page.has_more is False


def test_page_items_are_tuple() -> None:
    r = _rec()
    page = ValidationHistoryPage(items=[r], total=1)  # type: ignore[arg-type]
    assert isinstance(page.items, tuple)
    assert page.items[0] is r


def test_page_has_more_true() -> None:
    page = ValidationHistoryPage(
        items=(_rec(),),
        total=10,
        limit=1,
        offset=0,
        has_more=True,
    )
    assert page.has_more is True


def test_page_pagination_fields() -> None:
    page = ValidationHistoryPage(
        items=(),
        total=100,
        limit=20,
        offset=40,
        has_more=True,
    )
    assert page.limit == 20
    assert page.offset == 40
    assert page.total == 100
