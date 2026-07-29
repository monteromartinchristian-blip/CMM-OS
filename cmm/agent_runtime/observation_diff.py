"""Phase 9.4 – Change Detection between Observation Snapshots.

Provides deterministic snapshot comparison without causal inference or system mutation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from cmm.agent_runtime.enums import (
    ObservationKind,
    ObservationSignificance,
    ObservedChangeKind,
)
from cmm.agent_runtime.observation_contracts import (
    Observation,
    ObservationSnapshot,
    ObservedChange,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _map_kind_to_change_kind(obs_kind: ObservationKind | str) -> ObservedChangeKind:
    kind_str = (
        obs_kind.value if isinstance(obs_kind, ObservationKind) else str(obs_kind)
    )
    if kind_str == "validation":
        return ObservedChangeKind.VALIDATION_CHANGED
    if kind_str == "metric":
        return ObservedChangeKind.METRIC_CHANGED
    if kind_str == "configuration":
        return ObservedChangeKind.CONFIGURATION_CHANGED
    if kind_str == "external":
        return ObservedChangeKind.EXTERNAL_STATE_CHANGED
    return ObservedChangeKind.MODIFIED


def compare_snapshots(
    previous: ObservationSnapshot,
    current: ObservationSnapshot,
) -> tuple[ObservedChange, ...]:
    """Compare two ObservationSnapshots and detect structural and state changes.

    Detects:
        - New observations (created)
        - Disappeared observations (deleted)
        - Modified value or statement changes (modified / status_changed / specific kind)
        - Source version changes (external_state_changed)
    """
    changes: list[ObservedChange] = []
    now = _utc_now()

    prev_map: dict[str, Observation] = {
        obs.subject_id: obs for obs in previous.observations
    }
    curr_map: dict[str, Observation] = {
        obs.subject_id: obs for obs in current.observations
    }

    # 1. Detect new observations
    for subject_id, curr_obs in sorted(curr_map.items()):
        if subject_id not in prev_map:
            change_kind = (
                ObservedChangeKind.CREATED
                if curr_obs.kind != ObservationKind.VALIDATION
                else ObservedChangeKind.VALIDATION_CHANGED
            )
            changes.append(
                ObservedChange(
                    id=f"observed-change:{uuid.uuid4().hex[:12]}",
                    subject_id=subject_id,
                    kind=change_kind,
                    previous_value=None,
                    current_value=curr_obs.value,
                    detected_at=now,
                    significance=ObservationSignificance.INFO,
                    related_goal_ids=tuple(filter(None, [current.goal_id])),
                    source_observer=curr_obs.observer,
                    metadata={"statement": curr_obs.statement},
                )
            )

    # 2. Detect deleted observations
    for subject_id, prev_obs in sorted(prev_map.items()):
        if subject_id not in curr_map:
            changes.append(
                ObservedChange(
                    id=f"observed-change:{uuid.uuid4().hex[:12]}",
                    subject_id=subject_id,
                    kind=ObservedChangeKind.DELETED,
                    previous_value=prev_obs.value,
                    current_value=None,
                    detected_at=now,
                    significance=ObservationSignificance.MEDIUM,
                    related_goal_ids=tuple(filter(None, [current.goal_id])),
                    source_observer=prev_obs.observer,
                    metadata={"previous_statement": prev_obs.statement},
                )
            )

    # 3. Detect modified observations
    for subject_id in sorted(set(prev_map.keys()) & set(curr_map.keys())):
        prev_obs = prev_map[subject_id]
        curr_obs = curr_map[subject_id]

        if prev_obs.value != curr_obs.value or prev_obs.statement != curr_obs.statement:
            change_kind = _map_kind_to_change_kind(curr_obs.kind)
            sig = ObservationSignificance.MEDIUM
            if curr_obs.kind in (ObservationKind.VALIDATION, ObservationKind.HEALTH):
                sig = ObservationSignificance.HIGH

            changes.append(
                ObservedChange(
                    id=f"observed-change:{uuid.uuid4().hex[:12]}",
                    subject_id=subject_id,
                    kind=change_kind,
                    previous_value=prev_obs.value,
                    current_value=curr_obs.value,
                    detected_at=now,
                    significance=sig,
                    related_goal_ids=tuple(filter(None, [current.goal_id])),
                    source_observer=curr_obs.observer,
                    metadata={
                        "previous_statement": prev_obs.statement,
                        "current_statement": curr_obs.statement,
                    },
                )
            )

    # 4. Detect source version changes
    prev_sources = previous.source_versions
    curr_sources = current.source_versions
    for src_name in sorted(set(prev_sources.keys()) | set(curr_sources.keys())):
        p_ver = prev_sources.get(src_name)
        c_ver = curr_sources.get(src_name)

        if p_ver != c_ver:
            changes.append(
                ObservedChange(
                    id=f"observed-change:{uuid.uuid4().hex[:12]}",
                    subject_id=f"source_version:{src_name}",
                    kind=ObservedChangeKind.EXTERNAL_STATE_CHANGED,
                    previous_value=p_ver.version_identifier if p_ver else None,
                    current_value=c_ver.version_identifier if c_ver else None,
                    detected_at=now,
                    significance=ObservationSignificance.LOW,
                    related_goal_ids=tuple(filter(None, [current.goal_id])),
                    source_observer="ObservationEngine",
                    metadata={"source_name": src_name},
                )
            )

    # Deterministic ordering by subject_id then kind
    changes.sort(key=lambda c: (c.subject_id, str(c.kind)))
    return tuple(changes)
