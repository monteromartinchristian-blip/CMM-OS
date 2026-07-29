"""Phase 9.4 – Cognitive Layer Resource Adapter for Observation Engine.

Converts ObservationSnapshot, Observation, and ObservedChange instances into
Cognitive Layer Resource objects (Phase 8), preserving provenance, timestamps,
confidence, sensitivity, and metadata.
Does not mutate cognitive stores or execute cognitive extraction.
"""

from __future__ import annotations

from cmm.agent_runtime.observation_contracts import (
    Observation,
    ObservationSnapshot,
    ObservedChange,
)
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import (
    ResourceKind,
    ResourceSourceKind,
    SensitivityLevel,
)
from cmm.cognitive.resources import (
    Resource,
    ResourceProvenance,
    ResourceTemporalScope,
)


def _map_sensitivity(level_str: str) -> SensitivityLevel:
    try:
        return SensitivityLevel(level_str.lower())
    except ValueError:
        return SensitivityLevel.INTERNAL


class ObservationResourceAdapter:
    """Lightweight adapter converting Observation objects into Cognitive Layer Resources."""

    @staticmethod
    def from_observation(
        observation: Observation,
        domain: str = "agent_runtime",
    ) -> Resource:
        """Convert a single Observation into a Cognitive Layer Resource."""
        provenance = ResourceProvenance(
            source_type=ResourceSourceKind.SYSTEM,
            source_id=f"observer:{observation.observer}",
            author=observation.observer,
            retrieved_at=observation.observed_at,
        )

        temporal_scope = ResourceTemporalScope(
            observed_at=observation.observed_at,
        )

        reliability = Confidence(
            value=observation.confidence,
            source=observation.observer,
            reasons=(f"Observation by {observation.observer}",),
        )

        meta = dict(observation.metadata)
        meta.update(
            {
                "observation_id": observation.id,
                "subject_id": observation.subject_id,
                "statement": observation.statement,
                "kind": observation.kind.value
                if hasattr(observation.kind, "value")
                else str(observation.kind),
            }
        )

        return Resource(
            domain=domain,
            kind=ResourceKind.STRUCTURED_DATASET,
            source=ResourceSourceKind.SYSTEM,
            content=observation.value,
            provenance=provenance,
            reliability=reliability,
            temporal_scope=temporal_scope,
            sensitivity=_map_sensitivity(observation.sensitivity),
            metadata=meta,
        )

    @staticmethod
    def from_change(
        change: ObservedChange,
        domain: str = "agent_runtime",
    ) -> Resource:
        """Convert an ObservedChange into a Cognitive Layer Resource."""
        provenance = ResourceProvenance(
            source_type=ResourceSourceKind.SYSTEM,
            source_id=f"observer:{change.source_observer}",
            author=change.source_observer,
            retrieved_at=change.detected_at,
        )

        temporal_scope = ResourceTemporalScope(
            observed_at=change.detected_at,
        )

        reliability = Confidence(
            value=0.9,
            source=change.source_observer,
            reasons=(f"Detected change kind {change.kind}",),
        )

        meta = dict(change.metadata)
        meta.update(
            {
                "change_id": change.id,
                "subject_id": change.subject_id,
                "change_kind": change.kind.value
                if hasattr(change.kind, "value")
                else str(change.kind),
                "significance": (
                    change.significance.value
                    if hasattr(change.significance, "value")
                    else str(change.significance)
                ),
                "related_goal_ids": list(change.related_goal_ids),
            }
        )

        content_payload = {
            "previous_value": change.previous_value,
            "current_value": change.current_value,
        }

        return Resource(
            domain=domain,
            kind=ResourceKind.STRUCTURED_DATASET,
            source=ResourceSourceKind.SYSTEM,
            content=content_payload,
            provenance=provenance,
            reliability=reliability,
            temporal_scope=temporal_scope,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata=meta,
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ObservationSnapshot,
        domain: str = "agent_runtime",
    ) -> tuple[Resource, ...]:
        """Convert an entire ObservationSnapshot into Cognitive Layer Resources."""
        resources: list[Resource] = []

        # 1. Main snapshot summary resource
        provenance = ResourceProvenance(
            source_type=ResourceSourceKind.SYSTEM,
            source_id="ObservationEngine",
            author="ObservationEngine",
            retrieved_at=snapshot.completed_at,
        )

        temporal_scope = ResourceTemporalScope(
            event_start=snapshot.started_at,
            event_end=snapshot.completed_at,
            observed_at=snapshot.completed_at,
        )

        meta = dict(snapshot.metadata)
        meta.update(
            {
                "snapshot_id": snapshot.id,
                "goal_id": snapshot.goal_id,
                "agent_run_id": snapshot.agent_run_id,
                "status": snapshot.status.value
                if hasattr(snapshot.status, "value")
                else str(snapshot.status),
                "observation_count": len(snapshot.observations),
                "change_count": len(snapshot.changes),
                "warnings": list(snapshot.warnings),
            }
        )

        summary_resource = Resource(
            domain=domain,
            kind=ResourceKind.STRUCTURED_DATASET,
            source=ResourceSourceKind.SYSTEM,
            content=snapshot.to_dict(),
            provenance=provenance,
            reliability=Confidence(value=1.0, source="ObservationEngine"),
            temporal_scope=temporal_scope,
            sensitivity=SensitivityLevel.INTERNAL,
            metadata=meta,
        )
        resources.append(summary_resource)

        # 2. Individual observation resources
        for obs in snapshot.observations:
            resources.append(cls.from_observation(obs, domain=domain))

        # 3. Individual change resources
        for chg in snapshot.changes:
            resources.append(cls.from_change(chg, domain=domain))

        return tuple(resources)
