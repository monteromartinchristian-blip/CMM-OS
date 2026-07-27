"""Tests to confirm and verify the status index consistency fix.

This test file specifically covers:
1. Status transitions should remove old status index and add new one.
2. No stale IDs or empty index buckets should remain.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone

from cmm.agent_runtime.agent_delegation_contracts import DelegatedGoal
from cmm.agent_runtime.agent_delegation_enums import DelegationStatus
from cmm.agent_runtime.agent_delegation_store import InMemoryAgentDelegationStore


def _make_delegation(
    delegation_id: str,
    parent_goal_id: str,
    child_goal_id: str,
    status: DelegationStatus,
) -> DelegatedGoal:
    return DelegatedGoal(
        id=delegation_id,
        parent_goal_id=parent_goal_id,
        child_goal_id=child_goal_id,
        source_agent_id="agent-source",
        target_agent_id="agent-target",
        source_agent_run_id=None,
        target_agent_run_id=None,
        expected_result={},
        constraints=(),
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        depth=0,
    )


class TestStatusIndexConsistency:
    """Confirm that status index stays consistent across state transitions."""

    def test_status_transition_updates_index(self) -> None:
        store = InMemoryAgentDelegationStore()
        delegation = _make_delegation(
            "del-1",
            "goal-parent",
            "goal-child",
            DelegationStatus.PROPOSED,
        )
        store.add(delegation)

        assert len(store.list_by_status(DelegationStatus.PROPOSED)) == 1
        assert len(store.list_by_status(DelegationStatus.ACCEPTED)) == 0

        # Update status to ACCEPTED
        updated = DelegatedGoal(
            **{
                **{f.name: getattr(delegation, f.name) for f in fields(delegation)},
                "expected_result": dict(delegation.expected_result),
                "status": DelegationStatus.ACCEPTED,
            }
        )
        store.update(updated)

        assert len(store.list_by_status(DelegationStatus.PROPOSED)) == 0
        assert len(store.list_by_status(DelegationStatus.ACCEPTED)) == 1

    def test_multiple_status_transitions_no_stale_ids(self) -> None:
        store = InMemoryAgentDelegationStore()
        delegation = _make_delegation(
            "del-1",
            "goal-parent",
            "goal-child",
            DelegationStatus.PROPOSED,
        )
        store.add(delegation)

        terminal_statuses = [
            DelegationStatus.ACCEPTED,
            DelegationStatus.ACTIVE,
            DelegationStatus.WAITING,
            DelegationStatus.COMPLETED,
        ]
        for status in terminal_statuses:
            updated = DelegatedGoal(
                **{
                    **{f.name: getattr(delegation, f.name) for f in fields(delegation)},
                    "expected_result": dict(delegation.expected_result),
                    "status": status,
                }
            )
            store.update(updated)

            for s in DelegationStatus:
                count = len(store.list_by_status(s))
                if s == status:
                    assert count == 1
                else:
                    assert count == 0

    def test_no_empty_index_buckets(self) -> None:
        store = InMemoryAgentDelegationStore()
        delegation = _make_delegation(
            "del-1",
            "goal-parent",
            "goal-child",
            DelegationStatus.PROPOSED,
        )
        store.add(delegation)

        # Transition to ACCEPTED and remove old status
        updated = DelegatedGoal(
            **{
                **{f.name: getattr(delegation, f.name) for f in fields(delegation)},
                "expected_result": dict(delegation.expected_result),
                "status": DelegationStatus.ACCEPTED,
            }
        )
        store.update(updated)

        # _by_status should not contain stale or empty mappings
        for ids in store._by_status.values():
            assert len(ids) > 0
            assert all(isinstance(dep_id, str) for dep_id in ids), (
                "All IDs must be strings"
            )

    def test_delete_cleans_status_index(self) -> None:
        store = InMemoryAgentDelegationStore()
        delegation = _make_delegation(
            "del-1",
            "goal-parent",
            "goal-child",
            DelegationStatus.PROPOSED,
        )
        store.add(delegation)
        assert len(store._by_status.get(DelegationStatus.PROPOSED, set())) == 1

        store.delete("del-1")
        assert DelegationStatus.PROPOSED not in store._by_status


class TestStoreIndexKeyTypes:
    """Verify that all index keys use the proper declared types."""

    def test_status_index_key_type_matches_declaration(self) -> None:
        store = InMemoryAgentDelegationStore()
        delegation = _make_delegation(
            "del-1",
            "goal-parent",
            "goal-child",
            DelegationStatus.PROPOSED,
        )
        store.add(delegation)

        # _by_status must use DelegationStatus keys, not strings
        for key in store._by_status:
            assert isinstance(key, DelegationStatus), (
                f"Index key must be DelegationStatus, found {type(key).__name__}"
            )
