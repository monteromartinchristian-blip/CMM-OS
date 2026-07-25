"""Phase 9.4 – Observation Engine.

Coordinates observers, validates observation requests, enforces timeout, permissions,
and item limits, aggregates results, and produces deterministic ObservationSnapshots.
Does not mutate the observed system.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from cmm.agent_runtime.enums import (
    ObservationStatus,
    ObserverStatus,
)
from cmm.agent_runtime.errors import (
    InvalidObservationContractError,
)
from cmm.agent_runtime.observation_contracts import (
    Observation,
    ObservationError,
    ObservationRequest,
    ObservationResult,
    ObservationSnapshot,
    ObservationSourceVersion,
    ObservedChange,
)
from cmm.agent_runtime.observer_registry import ObserverRegistry


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ObservationEngine:
    """Core coordinator for autonomous state observation runs."""

    def __init__(self, registry: ObserverRegistry | None = None) -> None:
        self.registry = registry or ObserverRegistry()

    def execute(self, request: ObservationRequest) -> ObservationSnapshot:
        """Execute observers matching the request and produce a unified ObservationSnapshot."""

        # 1. Validate request invariants
        if request.maximum_items <= 0:
            raise InvalidObservationContractError(
                "maximum_items must be positive (> 0)"
            )

        if request.timeout_seconds <= 0.0:
            raise InvalidObservationContractError(
                "timeout_seconds must be positive (> 0)"
            )

        started_at = _utc_now()
        start_time = time.perf_counter()

        all_observations: list[Observation] = []
        all_changes: list[ObservedChange] = []
        all_warnings: list[str] = []
        all_errors: list[ObservationError] = []
        observer_results: list[ObservationResult] = []
        source_versions: dict[str, ObservationSourceVersion] = {}

        # 2. Resolve observers
        if request.observer_names:
            target_names = list(request.observer_names)
        else:
            target_names = [obs.name for obs in self.registry.list_all()]

        required_set = set(request.required_observers)
        has_required_failure = False

        # 3. Process each requested observer
        for name in target_names:
            elapsed = time.perf_counter() - start_time
            if elapsed >= request.timeout_seconds:
                timeout_msg = f"ObservationEngine timed out after {elapsed:.2f}s (limit: {request.timeout_seconds}s)"
                all_warnings.append(timeout_msg)
                all_errors.append(
                    ObservationError(
                        observer_name=name,
                        error_type="ObservationTimeoutError",
                        message=timeout_msg,
                        is_fatal=name in required_set,
                    )
                )
                if name in required_set:
                    has_required_failure = True
                continue

            observer = self.registry.get(name)
            if observer is None:
                err_msg = f"Requested observer '{name}' not found in registry."
                all_warnings.append(err_msg)
                all_errors.append(
                    ObservationError(
                        observer_name=name,
                        error_type="ObserverNotFoundError",
                        message=err_msg,
                        is_fatal=name in required_set,
                    )
                )
                if name in required_set:
                    has_required_failure = True
                continue

            # Check if observer is enabled in registry
            if not self.registry.is_available(name):
                err_msg = f"Observer '{name}' is disabled or unavailable."
                all_warnings.append(err_msg)
                all_errors.append(
                    ObservationError(
                        observer_name=name,
                        error_type="ObserverDisabledError",
                        message=err_msg,
                        is_fatal=name in required_set,
                    )
                )
                if name in required_set:
                    has_required_failure = True
                continue

            # Check permissions if required by observer
            req_perms = getattr(observer, "required_permissions", ())
            if req_perms and request.permissions:
                missing = [p for p in req_perms if p not in request.permissions]
                if missing:
                    err_msg = f"Observer '{name}' requires permissions {missing} which were not granted."
                    all_warnings.append(err_msg)
                    all_errors.append(
                        ObservationError(
                            observer_name=name,
                            error_type="ObservationPermissionError",
                            message=err_msg,
                            is_fatal=name in required_set,
                        )
                    )
                    if name in required_set:
                        has_required_failure = True
                    continue

            # Execute observer with safety error trapping
            try:
                result = observer.observe(request)
                observer_results.append(result)

                all_observations.extend(result.observations)
                all_changes.extend(result.changes)
                all_warnings.extend(result.warnings)
                all_errors.extend(result.errors)

                if result.source_version:
                    source_versions[result.source_version.source_name] = (
                        result.source_version
                    )

                if result.status == ObserverStatus.FAILED and name in required_set:
                    has_required_failure = True

            except Exception as exc:  # noqa: BLE001
                err_msg = f"Observer '{name}' failed during execution: {exc}"
                all_warnings.append(err_msg)
                all_errors.append(
                    ObservationError(
                        observer_name=name,
                        error_type="ObserverExecutionError",
                        message=err_msg,
                        is_fatal=name in required_set,
                    )
                )
                if name in required_set:
                    has_required_failure = True

        # 4. Limit items to maximum_items
        if len(all_observations) > request.maximum_items:
            all_warnings.append(
                f"Observations count ({len(all_observations)}) exceeded maximum_items ({request.maximum_items}). Truncated."
            )
            all_observations = all_observations[: request.maximum_items]

        # 5. Deterministic sorting
        all_observations.sort(key=lambda o: (o.subject_id, o.id))
        all_changes.sort(key=lambda c: (c.subject_id, c.id))

        completed_at = _utc_now()
        duration_ms = (time.perf_counter() - start_time) * 1000

        # 6. Determine final snapshot status
        if has_required_failure:
            snapshot_status = ObservationStatus.FAILED
        elif all_errors or any(
            r.status == ObserverStatus.DEGRADED for r in observer_results
        ):
            snapshot_status = ObservationStatus.DEGRADED
        elif len(observer_results) < len(target_names):
            snapshot_status = ObservationStatus.PARTIAL
        else:
            snapshot_status = ObservationStatus.COMPLETED

        return ObservationSnapshot(
            id=f"observation-snapshot:{uuid.uuid4().hex[:12]}",
            goal_id=request.goal_id,
            agent_run_id=request.agent_run_id,
            observations=tuple(all_observations),
            changes=tuple(all_changes),
            warnings=tuple(all_warnings),
            errors=tuple(all_errors),
            observer_results=tuple(observer_results),
            source_versions=source_versions,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            status=snapshot_status,
            metadata={"request_id": request.id},
        )
